"""
Scalable Mass Review Scraper for Google Maps Businesses.
Iterates over scraped business entities, extracts customer reviews via Playwright,
deduplicates into SQLite, and exports to CSV.
"""

import asyncio
import csv
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from urllib.parse import quote_plus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from storage.database import DatabaseManager

logger = logging.getLogger("mass_review_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EXPORTS_DIR = PROJECT_ROOT / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class ReviewWorker:
    def __init__(self, db_manager: Optional[DatabaseManager] = None, headless: bool = True):
        self.db = db_manager or DatabaseManager()
        self.headless = headless

    async def scrape_reviews_for_places(
        self,
        places: List[Dict[str, Any]],
        max_reviews_per_place: int = 15,
        skip_already_reviewed: bool = True,
        on_review_saved: Optional[Any] = None,
    ) -> int:
        already_reviewed_names: Set[str] = set()
        if skip_already_reviewed:
            already_reviewed_names = self.db.get_reviewed_business_names()
            logger.info(f"Database already contains reviews for {len(already_reviewed_names)} businesses.")

        to_process = [p for p in places if p.get("business_name") not in already_reviewed_names]
        logger.info(f"Total businesses scheduled for review extraction: {len(to_process)}")

        if not to_process:
            logger.info("All targeted businesses already have reviews scraped.")
            return 0

        total_extracted_reviews = 0

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--enable-webgl",
                    "--use-gl=swiftshader",
                    "--window-size=1920,1080",
                    "--no-sandbox",
                ]
            )
            context: BrowserContext = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="id-ID"
            )
            page: Page = await context.new_page()

            for idx, place in enumerate(to_process, 1):
                name = place.get("business_name", "").strip()
                niche = place.get("niche", "Umum")
                b_id = place.get("id")
                addr = place.get("address", "") or ""
                
                # Determine clean search query
                clean_name = re.sub(r"[\(\)\[\]]", " ", name).strip()
                clean_name = re.sub(r"\s+", " ", clean_name)

                city_hint = "Jogja"
                addr_lower = addr.lower()
                if "magelang" in addr_lower:
                    city_hint = "Magelang"
                elif "klaten" in addr_lower:
                    city_hint = "Klaten"
                elif "sleman" in addr_lower:
                    city_hint = "Sleman"
                elif "bantul" in addr_lower:
                    city_hint = "Bantul"

                if city_hint.lower() in clean_name.lower():
                    search_query = clean_name
                else:
                    search_query = f"{clean_name} {city_hint}"

                logger.info(f"[{idx}/{len(to_process)}] Extracting reviews for: '{name}' ({niche})")

                saved_for_place = 0
                try:
                    search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}?hl=id"
                    await page.goto(search_url, wait_until="commit", timeout=12000)
                    await asyncio.sleep(2.0)

                    # 1. If in search results feed list, select best matching place
                    if "/maps/place/" not in page.url:
                        feed_links = await page.locator("a.hfpxzc, div[role='feed'] a[href*='/maps/place/']").all()
                        if feed_links:
                            target_link = None
                            tokens = [t for t in clean_name.lower().split() if len(t) > 2]
                            for l in feed_links:
                                aria = (await l.get_attribute("aria-label") or "").lower()
                                if any(t in aria for t in tokens):
                                    target_link = l
                                    break
                            if not target_link:
                                target_link = feed_links[0]

                            try:
                                href = await target_link.get_attribute("href")
                                if href and "/maps/place/" in href:
                                    await page.goto(href, wait_until="commit", timeout=12000)
                                else:
                                    await target_link.click(force=True, timeout=3000)
                                await asyncio.sleep(1.8)
                            except Exception:
                                pass

                    # 2. Click the Ulasan tab or review count button
                    rev_tab = page.locator(
                        "button[role='tab']:has-text('Ulasan'), button[aria-label*='Ulasan'], div.F7nice button, div.F7nice, button[jsaction*='moreReviews']"
                    ).first
                    if await rev_tab.count() > 0:
                        try:
                            await rev_tab.click(timeout=3000)
                            await asyncio.sleep(2.0)
                        except Exception:
                            pass

                    # 3. Wait briefly for cards to populate
                    try:
                        await page.wait_for_selector("div.jftiEf", timeout=3500)
                    except Exception:
                        pass

                    # 4. Scroll container if more reviews requested
                    if max_reviews_per_place > 5:
                        cycles = min(4, (max_reviews_per_place - 5) // 5 + 1)
                        for _ in range(cycles):
                            await page.evaluate("""() => {
                                const containers = document.querySelectorAll("div.m6QErb.DxyBCb, div.m6QErb[aria-label*='Ulasan'], div[role='main']");
                                containers.forEach(c => {
                                    c.scrollTop = c.scrollHeight;
                                    c.scrollBy(0, 2500);
                                });
                            }""")
                            await asyncio.sleep(1.0)

                    # 5. Extract review cards
                    cards = await page.locator("div.jftiEf").all()
                    if not cards:
                        logger.warning(f"No review cards found for: {name}")
                        continue

                    logger.info(f"Found {len(cards)} cards on page for '{name}'. Processing up to {max_reviews_per_place}...")

                    for c_idx, card in enumerate(cards[:max_reviews_per_place]):
                        try:
                            # Author
                            author_el = card.locator(".d4r55").first
                            author = (await author_el.text_content()).strip() if await author_el.count() > 0 else "Pengguna Google"

                            # Rating
                            rating_val = 5.0
                            rating_el = card.locator(".kvMYJc").first
                            if await rating_el.count() > 0:
                                aria = await rating_el.get_attribute("aria-label") or ""
                                m = re.search(r"(\d+([.,]\d+)?)", aria)
                                if m:
                                    rating_val = float(m.group(1).replace(",", "."))

                            # Date
                            date_el = card.locator(".rsqaWe").first
                            date_str = (await date_el.text_content()).strip() if await date_el.count() > 0 else "-"

                            # Expand 'Lainnya' if present
                            more_btn = card.locator("button.w8nwRe, button:has-text('Lainnya')").first
                            if await more_btn.count() > 0:
                                try:
                                    await more_btn.click(timeout=800)
                                except Exception:
                                    pass

                            # Full card inner text for fallback parsing
                            full_card_text = await card.inner_text()
                            lines = [l.strip() for l in full_card_text.split("\n") if l.strip()]

                            # Owner response detection
                            owner_resp = ""
                            has_resp = False
                            resp_lines = []
                            for l in lines:
                                if "Tanggapan dari pemilik" in l:
                                    has_resp = True
                                    continue
                                if has_resp:
                                    resp_lines.append(l)
                            if resp_lines:
                                owner_resp = " ".join(resp_lines).strip()

                            # Customer comment text
                            comment = ""
                            comment_el = card.locator(".MyEned .wiI7m, span.wiI7m").first
                            if await comment_el.count() > 0:
                                comment = (await comment_el.text_content()).strip()

                            if not comment:
                                pre_resp = []
                                for l in lines:
                                    if "Tanggapan dari pemilik" in l:
                                        break
                                    if l not in [author, date_str, "BARU", "Lainnya", "Suka", "Bagikan", "", "", "", "+1", "+2", "+3", "+4", ""]:
                                        if not any(f"{n} ulasan" in l for n in range(1, 1000)) and "Local Guide" not in l and "foto" not in l:
                                            pre_resp.append(l)
                                if pre_resp:
                                    comment = " ".join(pre_resp).strip()

                            if not comment or comment in ["", ""]:
                                comment = "Memberikan rating bintang tanpa teks ulasan."

                            # Sentiment Classification
                            if rating_val >= 4.0:
                                sentiment = "Positif"
                            elif rating_val == 3.0:
                                sentiment = "Netral"
                            else:
                                sentiment = "Masalah / Keluhan"

                            # Insert into SQLite (0% duplication via SHA-256 hash)
                            _, is_new = self.db.insert_review(
                                business_name=name,
                                business_id=b_id,
                                niche=niche,
                                author=author,
                                rating=rating_val,
                                review_date=date_str,
                                review_text=comment,
                                sentiment=sentiment,
                                owner_response=owner_resp,
                            )
                            if is_new:
                                saved_for_place += 1
                                total_extracted_reviews += 1
                                if on_review_saved:
                                    on_review_saved(name, author, rating_val)

                        except Exception as e_card:
                            logger.debug(f"Card parse error on {name}: {e_card}")
                            continue

                    logger.info(f"Saved {saved_for_place} new reviews for '{name}'. (Cumulative: {total_extracted_reviews})")

                except Exception as e_place:
                    logger.warning(f"Error scraping reviews for '{name}': {e_place}")
                    continue

                # Auto-flush database to CSV every 4 businesses
                if idx % 4 == 0:
                    self.export_all_reviews_csv()

                # Short cooldown between businesses
                await asyncio.sleep(0.8)

            await browser.close()

        # Final CSV export
        total_in_db = self.export_all_reviews_csv()
        logger.info(f"Review scraping session finished. Added {total_extracted_reviews} new reviews. Total in DB: {total_in_db}.")
        return total_extracted_reviews

    def export_all_reviews_csv(self) -> int:
        output_csv = EXPORTS_DIR / "scraped_business_reviews.csv"
        reviews = self.db.get_all_reviews_as_dicts()
        if reviews:
            fieldnames = [
                "id",
                "business_id",
                "business_name",
                "niche",
                "author",
                "rating",
                "review_date",
                "review_text",
                "sentiment",
                "owner_response",
                "scraped_at",
            ]
            with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in reviews:
                    writer.writerow(r)
            logger.info(f"[SUCCESS] Exported {len(reviews)} reviews to {output_csv.name}")
        return len(reviews)
