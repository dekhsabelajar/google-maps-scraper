"""
Enhanced Review Scraper for Google Maps Business Entities.
Extracts individual customer reviews with accurate separation between customer text and owner response.
"""

import asyncio
import csv
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger("review_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EXPORTS_DIR = PROJECT_ROOT / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


TARGET_SAMPLE_ENTITIES = [
    # Niche 1: Kost Eksklusif
    {"niche": "Kost Eksklusif", "name": "Pinnacle Co-Living Kost Exclusive", "query": "Pinnacle Co-Living Kost Exclusive Yogyakarta"},
    {"niche": "Kost Eksklusif", "name": "Kost M - Executive Residence Jogja", "query": "Kost M Executive Residence Jogja"},
    
    # Niche 2: Gym & Pusat Kebugaran
    {"niche": "Gym & Pusat Kebugaran", "name": "One Time Pilates", "query": "One Time Pilates Jogja"},
    {"niche": "Gym & Pusat Kebugaran", "name": "WGYM Jogja", "query": "WGYM Jogja"},
    
    # Niche 3: Rental Kendaraan & Kamera
    {"niche": "Rental Kendaraan & Kamera", "name": "Global Rental Motor", "query": "Global Rental Motor Jogja"},
    {"niche": "Rental Kendaraan & Kamera", "name": "JOGJAKAMERA | Sewa Kamera", "query": "JOGJAKAMERA Sewa Kamera Multimedia Jogja"},
    
    # Niche 4: Barbershop & Salon
    {"niche": "Barbershop & Salon", "name": "Daisy Beauty Salon By Debby", "query": "Daisy Beauty Salon By Debby Jogja"},
    {"niche": "Barbershop & Salon", "name": "BarberKing Barbershop Klaten", "query": "BarberKing Barbershop Klaten"},
    
    # Niche 5: Percetakan Digital
    {"niche": "Percetakan Digital", "name": "Mangrove Printing", "query": "Mangrove Printing Gejayan Jogja"},
    
    # Niche 6: Car Wash
    {"niche": "Car Wash & Detailing", "name": "DK (DeKa) Car Wash & Coffee Corner", "query": "DK Car Wash and Coffee Corner Jogja"},
    
    # Niche 7: Pet Shop, Grooming, & Vet
    {"niche": "Pet Shop, Grooming, & Vet", "name": "Klinik Hewan Jogja", "query": "Klinik Hewan Jogja"},
]


async def extract_reviews_for_entity(page: Page, query: str, niche: str, business_name: str, max_reviews: int = 10) -> List[Dict[str, Any]]:
    reviews = []
    logger.info(f"Navigating to: '{query}'")
    
    search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}?hl=id"
    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2.5)

    # Click first candidate place if in feed
    first_place = page.locator("div[role='feed'] a[href*='/maps/place/']").first
    if await first_place.count() > 0:
        await first_place.click(force=True)
        await asyncio.sleep(2)

    # Click Ulasan tab
    rev_tab = page.locator("button[role='tab']:has-text('Ulasan'), button[aria-label*='Ulasan']").first
    if await rev_tab.count() > 0:
        await rev_tab.click()
        await asyncio.sleep(2)
    else:
        logger.warning(f"No Ulasan tab found for {query}")
        return reviews

    cards = await page.locator("div.jftiEf").all()
    logger.info(f"Loaded {len(cards)} review elements for {business_name}")

    for idx, c in enumerate(cards[:max_reviews]):
        try:
            # Author
            author_el = c.locator(".d4r55").first
            author = (await author_el.text_content()).strip() if await author_el.count() > 0 else "Pengguna Google"

            # Rating
            rating_el = c.locator(".kvMYJc").first
            rating_val = 5.0
            if await rating_el.count() > 0:
                aria = await rating_el.get_attribute("aria-label") or ""
                m = re.search(r"(\d+([.,]\d+)?)", aria)
                if m:
                    rating_val = float(m.group(1).replace(",", "."))

            # Date
            date_el = c.locator(".rsqaWe").first
            date_str = (await date_el.text_content()).strip() if await date_el.count() > 0 else "-"

            # Click 'Lainnya' if present
            more_btn = c.locator("button.w8nwRe, button:has-text('Lainnya')").first
            if await more_btn.count() > 0:
                try:
                    await more_btn.click(timeout=1000)
                except Exception:
                    pass

            # Extract full text
            full_card_text = await c.inner_text()
            lines = [l.strip() for l in full_card_text.split("\n") if l.strip()]

            # Extract owner response
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

            # Extract customer comment text
            comment = ""
            comment_el = c.locator(".MyEned .wiI7m, span.wiI7m").first
            if await comment_el.count() > 0:
                comment = (await comment_el.text_content()).strip()

            if not comment:
                # Parse lines before 'Tanggapan'
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

            # Sentiment Tag
            if rating_val >= 4.0:
                sentiment = "Positif"
            elif rating_val == 3.0:
                sentiment = "Netral"
            else:
                sentiment = "Masalah / Keluhan"

            reviews.append({
                "niche": niche,
                "business_name": business_name,
                "author": author,
                "rating": rating_val,
                "review_date": date_str,
                "review_text": comment,
                "sentiment": sentiment,
                "owner_response": owner_resp,
            })
        except Exception as e:
            logger.warning(f"Error parsing review card {idx}: {e}")
            continue

    return reviews


async def run_review_scraper():
    output_csv = EXPORTS_DIR / "scraped_business_reviews.csv"
    all_reviews = []

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--window-size=1920,1080", "--no-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="id-ID"
        )
        page = await context.new_page()

        for ent in TARGET_SAMPLE_ENTITIES:
            try:
                res = await extract_reviews_for_entity(
                    page=page,
                    query=ent["query"],
                    niche=ent["niche"],
                    business_name=ent["name"],
                    max_reviews=10
                )
                all_reviews.extend(res)
                logger.info(f"Extracted {len(res)} reviews for {ent['name']}")
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"Failed to scrape reviews for {ent['name']}: {e}")

        await browser.close()

    if all_reviews:
        fieldnames = ["niche", "business_name", "author", "rating", "review_date", "review_text", "sentiment", "owner_response"]
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_reviews:
                writer.writerow(r)
        logger.info(f"[SUCCESS] Saved {len(all_reviews)} reviews to {output_csv}")

    return len(all_reviews)


if __name__ == "__main__":
    count = asyncio.run(run_review_scraper())
    print(f"Total reviews saved: {count}")
