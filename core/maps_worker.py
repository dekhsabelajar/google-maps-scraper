"""
Google Maps Scraper Worker (Stage 1):
Automates Chromium using Playwright to search, scroll, and extract business details.
Adheres strictly to PRD:
- Controlled concurrency (1-2 browsers)
- Humanized scrolling with randomized delays (1.5s - 4.0s)
- Accessibility & semantic-first selectors (aria-label, role, data-item-id)
- Resilient null-safety
- Immediate persistence to DB with PENDING or NO_WEBSITE status
"""
import asyncio
import random
import logging
import sys
import subprocess
import re
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config.settings import settings
from storage.database import DatabaseManager, EnrichmentStatus
from core.normalizer import (
    normalize_phone_number,
    normalize_url,
    is_blacklisted_domain,
)

logger = logging.getLogger("maps_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class MapsWorker:
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        headless: Optional[bool] = None,
        proxy_url: Optional[str] = None,
    ):
        self.db = db_manager or DatabaseManager()
        self.headless = settings.DEFAULT_HEADLESS if headless is None else headless
        self.proxy_url = proxy_url or settings.PROXY_SERVER

    async def _random_delay(self, min_s: Optional[float] = None, max_s: Optional[float] = None):
        low = min_s or settings.MIN_SCROLL_DELAY
        high = max_s or settings.MAX_SCROLL_DELAY
        duration = random.uniform(low, high)
        await asyncio.sleep(duration)

    async def _handle_consent(self, page: Page):
        """Dismiss Google Cookie/Consent popup if present."""
        try:
            consent_selectors = [
                "button[aria-label*='Accept all']",
                "button[aria-label*='Setuju semua']",
                "button[aria-label*='I agree']",
                "form[action*='consent'] button",
                "button:has-text('Accept all')",
                "button:has-text('Setuju semua')",
            ]
            for sel in consent_selectors:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    await self._random_delay(1.0, 2.0)
                    break
        except Exception:
            pass

    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 100,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes Google Maps business discovery and extraction for a given keyword.
        """
        results: List[Dict[str, Any]] = []
        target_limit = min(limit, 500)
        logger.info(f"Starting Maps extraction for keyword: '{keyword}' (target: {target_limit})")

        async with async_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,800",
            ]
            proxy_config = {"server": self.proxy_url} if self.proxy_url else None

            try:
                browser: Browser = await p.chromium.launch(
                    headless=self.headless,
                    args=launch_args,
                    proxy=proxy_config,
                )
            except Exception as launch_err:
                err_str = str(launch_err)
                if "Executable doesn't exist" in err_str or "playwright install" in err_str:
                    logger.warning("Playwright Chromium binary not found. Automatically downloading browser...")
                    sub_proc = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True)
                    if sub_proc.returncode != 0:
                        logger.error(f"Auto-install failed: {sub_proc.stderr}")
                    browser = await p.chromium.launch(
                        headless=self.headless,
                        args=launch_args,
                        proxy=proxy_config,
                    )
                else:
                    raise launch_err

            context: BrowserContext = await browser.new_context(
                user_agent=settings.USER_AGENT,
                viewport={"width": 1280, "height": 800},
                locale="id-ID",
            )

            page: Page = await context.new_page()

            try:
                # Navigate directly to Maps search URL
                search_url = f"https://www.google.com/maps/search/{quote_plus(keyword)}?hl=id"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=settings.MAPS_NAVIGATION_TIMEOUT)
                await self._handle_consent(page)
                await self._random_delay(2.0, 3.5)

                feed_selector = "div[role='feed']"
                try:
                    await page.wait_for_selector(feed_selector, timeout=12000)
                except Exception:
                    logger.warning("Feed container role='feed' not found immediately, checking direct single result...")
                    # Sometimes Maps opens a single business profile directly
                    single_item = await self._extract_single_profile(page, keyword)
                    if single_item:
                        results.append(single_item)
                        if on_progress:
                            on_progress(single_item)
                    await browser.close()
                    return results

                feed_locator = page.locator(feed_selector)

                # Phase 1: Scroll feed to load candidate place links
                logger.info(f"Scrolling feed to load candidate places for keyword '{keyword}' (target: {target_limit})...")
                last_link_count = 0
                unchanged_cycles = 0

                for scroll_step in range(40):
                    # Check candidate link count
                    place_links = await page.locator("div[role='feed'] a[href*='/maps/place/']").all()
                    current_count = len(place_links)
                    
                    if current_count >= target_limit:
                        logger.info(f"Reached target candidate count ({current_count} >= {target_limit}). Proceeding to extraction.")
                        break

                    # Check for end of list text
                    end_indicators = [
                        "You've reached the end of the list",
                        "Anda telah mencapai akhir daftar",
                        "Tidak ada hasil lain",
                    ]
                    page_text = await page.content()
                    if any(indicator in page_text for indicator in end_indicators):
                        logger.info(f"Reached end of Google Maps feed. Total candidates loaded: {current_count}")
                        break

                    if current_count == last_link_count and current_count > 0:
                        unchanged_cycles += 1
                        if unchanged_cycles >= 4:
                            logger.info(f"Feed did not expand after 4 scrolls. Total candidates: {current_count}")
                            break
                    else:
                        unchanged_cycles = 0
                        last_link_count = current_count

                    # Smooth direct feed scroll
                    try:
                        await page.evaluate("const f = document.querySelector('div[role=\"feed\"]'); if(f) f.scrollBy(0, 3500);")
                    except Exception:
                        await page.keyboard.press("PageDown")

                    await self._random_delay(1.0, 1.8)

                # Phase 2: Extract details for each candidate link
                place_links = await page.locator("div[role='feed'] a[href*='/maps/place/']").all()
                if not place_links:
                    place_links = await page.locator("a[href*='/maps/place/']").all()

                logger.info(f"Beginning detail extraction for {len(place_links)} places (target: {target_limit})...")
                processed_place_urls = set()

                for link in place_links:
                    if len(results) >= target_limit:
                        break

                    try:
                        href = await link.get_attribute("href")
                        card_id = (href or "").split("?")[0]
                        if card_id and card_id in processed_place_urls:
                            continue

                        link_name = await link.get_attribute("aria-label")
                        if not link_name or link_name.strip() in ["Hasil", "Results", ""]:
                            continue

                        # Click link directly to open detail pane
                        await link.click(timeout=3000, force=True)
                        if card_id:
                            processed_place_urls.add(card_id)

                        await self._random_delay(0.8, 1.4)

                        # Extract detail pane
                        item_data = await self._extract_detail_pane(page, keyword, fallback_name=link_name.strip())
                        if item_data and item_data.get("business_name"):
                            results.append(item_data)
                            if on_progress:
                                on_progress(item_data)
                            logger.info(f"[{len(results)}/{target_limit}] Extracted: {item_data.get('business_name')} (Rating: {item_data.get('rating')}, Reviews: {item_data.get('reviews_count')})")

                    except Exception as e:
                        logger.warning(f"Failed to process place link: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error during Google Maps extraction: {e}", exc_info=True)
            finally:
                await context.close()
                await browser.close()

        logger.info(f"Extraction completed. Total extracted: {len(results)} entities for keyword '{keyword}'.")
        return results

    async def _extract_detail_pane(
        self,
        page: Page,
        keyword: str,
        fallback_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts business fields from the active detail panel.
        Resilient against dynamic CSS class changes using semantic ARIA attributes.
        """
        try:
            # 1. Business Name (fallback_name from aria-label or h1 in detail pane)
            name = fallback_name
            if not name:
                name_locators = ["h1.DUwDvf", "div[role='main'] h1", "h1"]
                for sel in name_locators:
                    els = await page.locator(sel).all()
                    for el in els:
                        if await el.is_visible(timeout=500):
                            text = await el.text_content()
                            if text and text.strip() and text.strip() not in ["Hasil", "Results"]:
                                name = text.strip()
                                break
                    if name:
                        break

            if not name:
                return None

            # 2. Category
            category = None
            cat_locators = ["button[jsaction*='category']", "button[class*='DkEaL']", "span.fontBodyMedium"]
            for sel in cat_locators:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.text_content()
                    if text and text.strip():
                        category = text.strip()
                        break

            # 3. Address
            address = None
            addr_locators = [
                "button[data-item-id='address']",
                "button[aria-label*='Alamat:']",
                "button[aria-label*='Address:']",
                "[data-tooltip*='Copy address']",
            ]
            for sel in addr_locators:
                el = page.locator(sel).first
                if await el.count() > 0:
                    aria = await el.get_attribute("aria-label")
                    if aria and (":" in aria):
                        address = aria.split(":", 1)[1].strip()
                    else:
                        text = await el.text_content()
                        if text:
                            address = text.strip()
                    if address:
                        break

            # 4. Phone Number
            phone_raw = None
            phone_locators = [
                "button[data-item-id^='phone:']",
                "button[aria-label*='Telepon:']",
                "button[aria-label*='Phone:']",
                "[data-tooltip*='Copy phone number']",
            ]
            for sel in phone_locators:
                el = page.locator(sel).first
                if await el.count() > 0:
                    aria = await el.get_attribute("aria-label")
                    if aria and (":" in aria):
                        phone_raw = aria.split(":", 1)[1].strip()
                    else:
                        text = await el.text_content()
                        if text:
                            phone_raw = text.strip()
                    if phone_raw:
                        break

            # 5. Website URL
            website_raw = None
            web_locators = [
                "a[data-item-id='authority']",
                "a[aria-label*='Situs web:']",
                "a[aria-label*='Website:']",
                "a[data-tooltip*='Open website']",
            ]
            for sel in web_locators:
                el = page.locator(sel).first
                if await el.count() > 0:
                    href = await el.get_attribute("href")
                    if href:
                        website_raw = href.strip()
                        break

            # 6. Rating & Total Reviews
            rating = None
            reviews_count = None
            try:
                # Rating score
                r_el = page.locator("div.F7nice span[aria-hidden='true']").first
                if await r_el.count() > 0:
                    r_text = await r_el.text_content()
                    if r_text:
                        try:
                            rating = float(r_text.strip().replace(",", "."))
                        except ValueError:
                            pass
                
                if rating is None:
                    star_el = page.locator("span[aria-label*='bintang'], span[aria-label*='stars']").first
                    if await star_el.count() > 0:
                        star_label = await star_el.get_attribute("aria-label")
                        if star_label:
                            m = re.search(r"(\d+([.,]\d+)?)", star_label)
                            if m:
                                try:
                                    rating = float(m.group(1).replace(",", "."))
                                except ValueError:
                                    pass

                # Total reviews count
                rev_locators = [
                    "div.F7nice span[aria-label*='ulasan']",
                    "div.F7nice span[aria-label*='review']",
                    "span[aria-label*='ulasan']",
                    "span[aria-label*='reviews']",
                    "button[jsaction*='pane.reviewChart.moreReviews']",
                ]
                for rev_sel in rev_locators:
                    rev_elem = page.locator(rev_sel).first
                    if await rev_elem.count() > 0:
                        aria = await rev_elem.get_attribute("aria-label") or ""
                        txt = await rev_elem.text_content() or ""
                        combined_rev = f"{aria} {txt}"
                        m_rev = re.search(r"([\d\.,]+)\s*(?:ulasan|reviews|review)?", combined_rev, re.IGNORECASE)
                        if m_rev:
                            clean_cnt = m_rev.group(1).replace(".", "").replace(",", "").strip()
                            if clean_cnt.isdigit():
                                reviews_count = int(clean_cnt)
                                break
            except Exception as e_rev:
                logger.debug(f"Error extracting reviews/rating: {e_rev}")

            # Standardize & Normalize
            phone_normalized = normalize_phone_number(phone_raw)
            website_normalized = normalize_url(website_raw)

            # Determine initial enrichment status
            if not website_normalized or is_blacklisted_domain(website_normalized):
                enrich_status = EnrichmentStatus.NO_WEBSITE
            else:
                enrich_status = EnrichmentStatus.PENDING

            # Atomic database insertion & deduplication (FR-07, NFR-2)
            entity, is_new = self.db.insert_or_update_entity(
                search_keyword=keyword,
                business_name=name,
                category=category,
                address=address,
                phone_number=phone_normalized,
                website_url=website_normalized,
                rating=rating,
                reviews_count=reviews_count,
                enrichment_status=enrich_status,
            )

            return entity.to_dict()

        except Exception as e:
            logger.warning(f"Error extracting detail pane: {e}")
            return None

    async def _extract_single_profile(self, page: Page, keyword: str) -> Optional[Dict[str, Any]]:
        """Handles cases where Maps navigates directly to a single business profile."""
        try:
            await page.wait_for_selector("h1", timeout=5000)
            return await self._extract_detail_pane(page, keyword)
        except Exception:
            return None
