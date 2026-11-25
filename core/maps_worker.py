"""
Google Maps Scraper Worker (Stage 1):
Fast feed-HTML scraping modeled after google-maps-scrapping-app:
- Navigates to Google Maps search URL
- Scrolls div[role='feed'] in-browser until target limit or end of feed
- Captures page HTML once and parses all business cards in-memory with BeautifulSoup
- Falls back to single-place detail extraction when Maps opens a single profile directly
- Normalizes phone numbers & URLs and persists atomically to DatabaseManager
"""
import asyncio
import logging
import re
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config.settings import settings
from core.normalizer import (
    is_blacklisted_domain,
    normalize_phone_number,
    normalize_url,
)
from storage.database import DatabaseManager, EnrichmentStatus

logger = logging.getLogger("maps_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_PHONE_PATTERN = re.compile(r"(?:\+62|62|0|\(0)\s*[\d\s\-().]{6,}")


def _parse_rating_and_reviews(
    rating_text: Optional[str],
    fallback_rating_text: Optional[str] = None,
    fallback_reviews_text: Optional[str] = None,
) -> tuple[Optional[float], Optional[int]]:
    """Parse rating (float) and reviews_count (int) from Google Maps aria-label or fallback spans."""
    rating: Optional[float] = None
    reviews_count: Optional[int] = None

    if rating_text:
        m_rat = re.search(r"(\d+(?:[.,]\d+)?)", rating_text)
        if m_rat:
            try:
                val = float(m_rat.group(1).replace(",", "."))
                if 0.0 <= val <= 5.0:
                    rating = val
            except ValueError:
                pass

        m_rev = re.search(r"(?:bintang|stars?)\s*([\d.,]+)", rating_text, re.IGNORECASE)
        if not m_rev:
            m_rev = re.search(r"([\d.,]+)\s*(?:ulasan|reviews?)", rating_text, re.IGNORECASE)
        if m_rev:
            digits = re.sub(r"[.,\s]", "", m_rev.group(1))
            if digits.isdigit():
                reviews_count = int(digits)

    if rating is None and fallback_rating_text:
        m_rat = re.search(r"(\d+(?:[.,]\d+)?)", fallback_rating_text)
        if m_rat:
            try:
                val = float(m_rat.group(1).replace(",", "."))
                if 0.0 <= val <= 5.0:
                    rating = val
            except ValueError:
                pass

    if reviews_count is None and fallback_reviews_text:
        digits = re.sub(r"\D", "", fallback_reviews_text)
        if digits:
            reviews_count = int(digits)

    return rating, reviews_count


def _extract_phone_candidate(text: str) -> Optional[str]:
    """Extract a plausible phone number substring from a feed metadata line."""
    if not text:
        return None
    for part in text.split("·"):
        part_clean = part.strip()
        if _PHONE_PATTERN.search(part_clean) and len(re.sub(r"\D", "", part_clean)) >= 7:
            return part_clean
    return None


def parse_feed_html(html: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fast in-memory parser for Google Maps search feed HTML.
    Mirrors the Cheerio card extraction strategy in google-maps-scrapping-app.
    When `limit` is None or <= 0, returns all extracted businesses without truncation.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    place_links = [
        a for a in soup.find_all("a", href=True)
        if "/maps/place/" in a["href"]
    ]

    businesses: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    has_limit = limit is not None and limit > 0

    for a_tag in place_links:
        if has_limit and len(businesses) >= limit:
            break

        parent = a_tag.parent
        if parent is None:
            continue

        headline = parent.select_one("div.fontHeadlineSmall")
        store_name = headline.get_text(" ", strip=True) if headline else ""
        if not store_name:
            store_name = (a_tag.get("aria-label") or "").strip()

        if not store_name or store_name in ("Hasil", "Results") or store_name in seen_names:
            continue
        seen_names.add(store_name)

        first_a = parent.find("a", href=True)
        google_url = first_a["href"] if first_a else a_tag["href"]

        website_el = parent.select_one('a[data-value="Website"]')
        website_raw = website_el.get("href", "").strip() if website_el else ""

        rating_span = parent.select_one("span.fontBodyMedium > span")
        rating_text = rating_span.get("aria-label") if rating_span else None
        if not rating_text:
            img_span = parent.select_one('span[role="img"][aria-label]')
            rating_text = img_span.get("aria-label") if img_span else None

        mw_span = parent.select_one("span.MW4etd")
        uy_span = parent.select_one("span.UY7F9")
        rating, reviews_count = _parse_rating_and_reviews(
            rating_text,
            fallback_rating_text=mw_span.get_text(strip=True) if mw_span else None,
            fallback_reviews_text=uy_span.get_text(strip=True) if uy_span else None,
        )

        category = ""
        address = ""
        phone_raw = ""

        body_div = parent.select_one("div.fontBodyMedium")
        if body_div:
            children = [c for c in body_div.children if getattr(c, "name", None)]
            if children:
                last_child = children[-1]
                last_children = [c for c in last_child.children if getattr(c, "name", None)]
                if last_children:
                    first_of_last = re.sub(r"[\uE000-\uF8FF]+", "", last_children[0].get_text(" ", strip=True)).strip()
                    parts_first = [p.strip() for p in first_of_last.split("·") if p.strip()]
                    if parts_first:
                        category = parts_first[0]
                    if len(parts_first) > 1:
                        # Avoid accidentally treating a price symbol (e.g. Rp...) as address
                        for candidate_part in parts_first[1:]:
                            if not candidate_part.startswith("Rp") and not candidate_part.startswith("$"):
                                address = candidate_part
                                break

                    last_of_last = re.sub(r"[\uE000-\uF8FF]+", "", last_children[-1].get_text(" ", strip=True)).strip()
                    phone_raw = (
                        _extract_phone_candidate(last_of_last)
                        or _extract_phone_candidate(re.sub(r"[\uE000-\uF8FF]+", "", last_child.get_text(" ", strip=True)))
                        or ""
                    )

        place_id = ""
        if "ChI" in google_url:
            place_id = "ChI" + google_url.split("?")[0].split("ChI", 1)[1].split("!")[0]

        businesses.append({
            "business_name": store_name,
            "place_id": place_id,
            "category": category or None,
            "address": address or None,
            "phone_raw": phone_raw or None,
            "website_raw": website_raw or None,
            "google_url": google_url,
            "rating": rating,
            "reviews_count": reviews_count,
        })

    return businesses


def parse_single_place_html(html: str, current_url: str = "") -> Optional[Dict[str, Any]]:
    """Fallback parser when Google Maps opens a single business profile directly."""
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    store_name = h1.get_text(" ", strip=True) if h1 else ""
    if not store_name or store_name in ("Hasil", "Results"):
        return None

    addr_btn = soup.select_one('button[data-item-id="address"]')
    raw_addr = addr_btn.get_text(" ", strip=True) if addr_btn else ""
    address = re.sub(r"^[\s\uE000-\uF8FF]+", "", raw_addr).strip()

    phone_btn = soup.select_one('button[data-item-id*="phone"]')
    raw_phone = phone_btn.get_text(" ", strip=True) if phone_btn else ""
    phone_raw = re.sub(r"^[\s\uE000-\uF8FF]+", "", raw_phone).strip()

    web_el = soup.select_one('a[data-item-id="authority"]')
    website_raw = web_el.get("href", "").strip() if web_el else ""

    cat_btn = soup.select_one('button[jsaction*="category"]')
    category = cat_btn.get_text(" ", strip=True) if cat_btn else ""

    rating_el = soup.select_one('span[role="img"][aria-label]')
    rating_text = rating_el.get("aria-label") if rating_el else ""
    f7_rating = soup.select_one("div.F7nice span[aria-hidden='true']")
    f7_reviews = soup.select_one("div.F7nice span[aria-label*='ulasan'], div.F7nice span[aria-label*='review']")
    rating, reviews_count = _parse_rating_and_reviews(
        rating_text,
        fallback_rating_text=f7_rating.get_text(strip=True) if f7_rating else None,
        fallback_reviews_text=f7_reviews.get("aria-label") if f7_reviews else None,
    )

    place_id = ""
    if "ChI" in current_url:
        place_id = "ChI" + current_url.split("?")[0].split("ChI", 1)[1].split("!")[0]

    return {
        "business_name": store_name,
        "place_id": place_id,
        "category": category or None,
        "address": address or None,
        "phone_raw": phone_raw or None,
        "website_raw": website_raw or None,
        "google_url": current_url,
        "rating": rating,
        "reviews_count": reviews_count,
    }


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

    async def _handle_consent(self, page: Page) -> None:
        """Dismiss Google Cookie/Consent popup if present."""
        consent_selectors = [
            "button[aria-label*='Accept all']",
            "button[aria-label*='Setuju semua']",
            "button[aria-label*='I agree']",
            "form[action*='consent'] button",
            "button:has-text('Accept all')",
            "button:has-text('Setuju semua')",
        ]
        for sel in consent_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await asyncio.sleep(0.8)
                    break
            except Exception:
                continue

    async def _launch_browser(self, playwright) -> Browser:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1280,900",
        ]
        proxy_config = {"server": self.proxy_url} if self.proxy_url else None

        try:
            return await playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
                proxy=proxy_config,
            )
        except Exception as launch_err:
            err_str = str(launch_err)
            if "Executable doesn't exist" in err_str or "playwright install" in err_str:
                logger.warning("Playwright Chromium binary not found. Automatically downloading browser...")
                sub_proc = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True,
                )
                if sub_proc.returncode != 0:
                    logger.error(f"Auto-install failed: {sub_proc.stderr}")
                return await playwright.chromium.launch(
                    headless=self.headless,
                    args=launch_args,
                    proxy=proxy_config,
                )
            raise

    async def _enrich_details_pool(
        self,
        context: BrowserContext,
        items: List[Dict[str, Any]],
        concurrency: int = 12,
    ) -> None:
        """
        Fetch phone, website, and full address for items using a reusable pool of lightweight tabs.
        Avoids per-item tab creation/destruction overhead and skips items already cached in DB.
        """
        pending_items: List[Dict[str, Any]] = []
        for it in items:
            if it.get("phone_raw") and it.get("website_raw"):
                continue
            if it.get("google_url"):
                pending_items.append(it)

        if not pending_items:
            return

        item_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        for it in pending_items:
            item_queue.put_nowait(it)

        worker_count = min(concurrency, len(pending_items))

        async def _worker():
            page = await context.new_page()
            try:
                await page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ("image", "media", "font", "stylesheet")
                    else route.continue_(),
                )
                while not item_queue.empty():
                    try:
                        item = item_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    url = item.get("google_url", "")
                    if not url:
                        continue
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                        try:
                            await page.wait_for_selector(
                                'button[data-item-id^="phone:"], a[data-item-id="authority"], button[data-item-id="address"]',
                                timeout=2200,
                            )
                        except Exception:
                            pass
                        html = await page.content()
                        detail = parse_single_place_html(html, url)
                        if detail:
                            if not item.get("phone_raw") and detail.get("phone_raw"):
                                item["phone_raw"] = detail["phone_raw"]
                            if not item.get("website_raw") and detail.get("website_raw"):
                                item["website_raw"] = detail["website_raw"]
                            if detail.get("address") and (
                                not item.get("address") or len(detail["address"]) > len(item["address"])
                            ):
                                item["address"] = detail["address"]
                            if not item.get("category") and detail.get("category"):
                                item["category"] = detail["category"]
                    except Exception as exc:
                        logger.debug(f"[FastScraper] Detail fetch failed for {item.get('business_name')}: {exc}")
            finally:
                await page.close()

        await asyncio.gather(*(_worker() for _ in range(worker_count)))

    async def _scrape_single_query_with_context(
        self,
        context: BrowserContext,
        keyword: str,
        limit: Optional[int] = 0,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        fetch_details: bool = False,
        detail_concurrency: int = 12,
    ) -> List[Dict[str, Any]]:
        """Run fast feed-HTML scraping for one search query. If limit is 0/None, scrolls until end of feed."""
        results: List[Dict[str, Any]] = []
        target_limit = limit if (limit is not None and limit > 0) else 0
        page: Page = await context.new_page()

        try:
            search_url = f"https://www.google.com/maps/search/{quote_plus(keyword)}?hl=id"
            logger.info(f"[FastScraper] Navigating to: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=settings.MAPS_NAVIGATION_TIMEOUT)
            await self._handle_consent(page)

            has_feed = True
            try:
                await page.wait_for_selector("div[role='feed']", timeout=8000)
            except Exception:
                has_feed = False

            if has_feed:
                max_scrolls = 120 if target_limit == 0 else max(15, min(120, (target_limit // 5) + 10))
                logger.info(
                    f"[FastScraper] Feed detected for '{keyword}'. Scrolling "
                    f"(target={'ALL' if target_limit == 0 else target_limit}, max_scrolls={max_scrolls})..."
                )
                await page.evaluate(
                    """async ({ targetLimit, maxScrolls }) => {
                        const wrapper = document.querySelector('div[role="feed"]');
                        if (!wrapper) return;

                        const endTexts = [
                            "Anda telah mencapai akhir daftar",
                            "You've reached the end of the list",
                            "Tidak ada hasil lain"
                        ];

                        await new Promise((resolve) => {
                            let totalHeight = 0;
                            const distance = 1500;
                            const scrollDelay = 1000;
                            let scrolls = 0;
                            let stalledChecks = 0;

                            const timer = setInterval(async () => {
                                scrolls++;
                                const linkCount = wrapper.querySelectorAll('a[href*="/maps/place/"]').length;
                                if ((targetLimit > 0 && linkCount >= targetLimit) || scrolls >= maxScrolls) {
                                    clearInterval(timer);
                                    resolve();
                                    return;
                                }

                                const text = wrapper.innerText || "";
                                if (endTexts.some((t) => text.includes(t))) {
                                    clearInterval(timer);
                                    resolve();
                                    return;
                                }

                                const scrollHeightBefore = wrapper.scrollHeight;
                                wrapper.scrollBy(0, distance);
                                totalHeight += distance;

                                if (totalHeight >= scrollHeightBefore) {
                                    totalHeight = 0;
                                    await new Promise((r) => setTimeout(r, scrollDelay));
                                    const scrollHeightAfter = wrapper.scrollHeight;
                                    if (scrollHeightAfter <= scrollHeightBefore) {
                                        stalledChecks++;
                                        if (stalledChecks >= 2) {
                                            clearInterval(timer);
                                            resolve();
                                        }
                                    } else {
                                        stalledChecks = 0;
                                    }
                                }
                            }, 350);
                        });
                    }""",
                    {"targetLimit": target_limit, "maxScrolls": max_scrolls},
                )
                await asyncio.sleep(0.6)
            else:
                logger.info(f"[FastScraper] No feed found for '{keyword}'. Checking single place detail...")
                await asyncio.sleep(1.0)

            current_url = page.url
            html = await page.content()
        finally:
            await page.close()

        raw_items = parse_feed_html(html, limit=target_limit if target_limit > 0 else None)
        if not raw_items and not has_feed:
            single = parse_single_place_html(html, current_url)
            if single:
                raw_items = [single]

        if fetch_details and raw_items:
            logger.info(f"[FastScraper] Fetching phone & website for {len(raw_items)} places (pool={detail_concurrency})...")
            await self._enrich_details_pool(context, raw_items, concurrency=detail_concurrency)

        for item in raw_items:
            phone_normalized = normalize_phone_number(item.get("phone_raw"))
            website_normalized = normalize_url(item.get("website_raw"))

            if not website_normalized or is_blacklisted_domain(website_normalized):
                enrich_status = EnrichmentStatus.NO_WEBSITE
            else:
                enrich_status = EnrichmentStatus.PENDING

            entity, _ = self.db.insert_or_update_entity(
                search_keyword=keyword,
                business_name=item["business_name"],
                category=item.get("category"),
                address=item.get("address"),
                phone_number=phone_normalized,
                website_url=website_normalized,
                rating=item.get("rating"),
                reviews_count=item.get("reviews_count"),
                enrichment_status=enrich_status,
            )
            entity_dict = entity.to_dict()
            results.append(entity_dict)
            if on_progress:
                on_progress(entity_dict)

        logger.info(f"[FastScraper] Extracted {len(results)} businesses for '{keyword}'.")
        return results

    async def search_and_extract(
        self,
        keyword: str,
        limit: int = 100,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        fetch_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """Executes fast Google Maps business discovery and extraction for a given keyword."""
        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context = await browser.new_context(
                user_agent=settings.USER_AGENT,
                viewport={"width": 1280, "height": 900},
                locale="id-ID",
            )
            try:
                return await self._scrape_single_query_with_context(
                    context=context,
                    keyword=keyword,
                    limit=limit,
                    on_progress=on_progress,
                    fetch_details=fetch_details,
                )
            finally:
                await context.close()
                await browser.close()

    async def search_multiple_locations(
        self,
        keyword: str,
        locations: List[str],
        limit_per_location: int = 100,
        on_location_start: Optional[Callable[[str, int, int], None]] = None,
        on_location_done: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
        fetch_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Scrapes `keyword` across multiple location tags using a single shared browser instance,
        then combines and deduplicates all results.
        """
        return await self.search_batch(
            keywords=[keyword],
            locations=locations,
            limit_per_location=limit_per_location,
            on_task_start=(
                (lambda _kw, loc, idx, total: on_location_start(loc, idx, total))
                if on_location_start
                else None
            ),
            on_task_done=(
                (lambda _kw, loc, items: on_location_done(loc, items))
                if on_location_done
                else None
            ),
            fetch_details=fetch_details,
        )

    async def search_batch(
        self,
        keywords: List[str],
        locations: List[str],
        limit_per_location: int = 100,
        on_task_start: Optional[Callable[[str, str, int, int], None]] = None,
        on_task_done: Optional[Callable[[str, str, List[Dict[str, Any]]], None]] = None,
        fetch_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Scrapes up to 10 keywords across multiple location tags using a shared browser
        with a fresh BrowserContext per keyword (prevents memory bloat & session throttling),
        automatic retry on empty results, and per-task error isolation.
        """
        clean_keywords = [kw.strip() for kw in keywords if kw and kw.strip()][:10]
        clean_locations = [loc.strip() for loc in locations if loc and loc.strip()]

        if not clean_keywords or not clean_locations:
            return []

        combined: List[Dict[str, Any]] = []
        seen_hashes: set[str] = set()
        total_tasks = len(clean_keywords) * len(clean_locations)
        task_idx = 0

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            try:
                for kw in clean_keywords:
                    # Fresh BrowserContext per keyword to avoid session throttling & tab/memory accumulation
                    context = await browser.new_context(
                        user_agent=settings.USER_AGENT,
                        viewport={"width": 1280, "height": 900},
                        locale="id-ID",
                    )
                    try:
                        async def _run_loc(loc: str, cur_idx: int) -> tuple[str, List[Dict[str, Any]]]:
                            if on_task_start:
                                on_task_start(kw, loc, cur_idx, total_tasks)

                            query = f"{kw} {loc}".strip()
                            loc_results: List[Dict[str, Any]] = []

                            for attempt in range(2):
                                try:
                                    loc_results = await self._scrape_single_query_with_context(
                                        context=context,
                                        keyword=query,
                                        limit=limit_per_location,
                                        fetch_details=fetch_details,
                                    )
                                    if loc_results:
                                        break
                                    if attempt == 0:
                                        logger.warning(f"[FastScraper] Empty result for '{query}', retrying...")
                                        await asyncio.sleep(1.5)
                                except Exception as task_err:
                                    logger.warning(f"[FastScraper] Attempt {attempt + 1} failed for '{query}': {task_err}")
                                    if attempt == 0:
                                        await asyncio.sleep(1.5)

                            return loc, loc_results

                        # Run up to 3 locations in parallel for the current keyword
                        loc_batches = []
                        for loc in clean_locations:
                            task_idx += 1
                            loc_batches.append(_run_loc(loc, task_idx))

                        # Execute location feeds concurrently (capped at 3 at a time)
                        for start_i in range(0, len(loc_batches), 3):
                            chunk = loc_batches[start_i:start_i + 3]
                            chunk_outputs = await asyncio.gather(*chunk)
                            for loc, loc_results in chunk_outputs:
                                unique_for_task: List[Dict[str, Any]] = []
                                for item in loc_results:
                                    item["niche"] = kw
                                    item["region"] = loc
                                    d_hash = item.get("dedup_hash") or f"{item.get('business_name', '')}::{item.get('address', '')}"
                                    if d_hash not in seen_hashes:
                                        seen_hashes.add(d_hash)
                                        combined.append(item)
                                        unique_for_task.append(item)

                                if on_task_done:
                                    on_task_done(kw, loc, unique_for_task)
                    finally:
                        await context.close()
            finally:
                await browser.close()

        return combined
