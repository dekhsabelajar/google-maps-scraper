"""
Email Enricher Worker (Stage 2):
High-speed asynchronous HTTP crawling using httpx and BeautifulSoup4.
Extracts emails from homepage and up to 2 internal contact/about pages.
"""
import asyncio
import logging
import re
from typing import List, Set, Optional, Callable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config.settings import settings
from storage.database import DatabaseManager, BusinessEntity, EnrichmentStatus
from core.normalizer import (
    extract_valid_emails,
    is_blacklisted_domain,
)

logger = logging.getLogger("email_enricher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class EmailEnricher:
    """
    Asynchronous web crawler for business email enrichment.
    """
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        concurrency: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self.db = db_manager or DatabaseManager()
        self.concurrency = concurrency or settings.EMAIL_CONCURRENCY
        self.timeout = timeout or settings.HTTP_TIMEOUT
        self.semaphore = asyncio.Semaphore(self.concurrency)

    async def enrich_entities(
        self,
        entities: Optional[List[BusinessEntity]] = None,
        on_progress: Optional[Callable[[BusinessEntity, List[str], EnrichmentStatus], None]] = None,
    ) -> List[BusinessEntity]:
        """
        Enriches a batch of entities or pulls all PENDING entities from database.
        """
        if entities is None:
            entities = self.db.get_pending_enrichment_entities()

        if not entities:
            logger.info("No pending entities found for email enrichment.")
            return []

        logger.info(f"Starting Stage 2 Email Enrichment for {len(entities)} entities (concurrency: {self.concurrency})")

        # Custom transport to handle SSL issues gracefully
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=self.concurrency)
        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        async with httpx.AsyncClient(
            verify=settings.HTTP_VERIFY_SSL,
            timeout=self.timeout,
            limits=limits,
            headers=headers,
            follow_redirects=True,
        ) as client:
            tasks = [
                self._process_single_entity(client, entity, on_progress)
                for entity in entities
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Email enrichment finished for {len(entities)} entities.")
        return entities

    async def _process_single_entity(
        self,
        client: httpx.AsyncClient,
        entity: BusinessEntity,
        on_progress: Optional[Callable[[BusinessEntity, List[str], EnrichmentStatus], None]] = None,
    ):
        async with self.semaphore:
            website = entity.website_url
            if not website or is_blacklisted_domain(website):
                status = EnrichmentStatus.NO_WEBSITE
                self.db.update_enrichment_result(entity.id, [], status)
                if on_progress:
                    on_progress(entity, [], status)
                return

            try:
                emails = await self._crawl_website_for_emails(client, website)
                if emails:
                    status = EnrichmentStatus.SUCCESS
                else:
                    # Successfully crawled but no email listed on website
                    status = EnrichmentStatus.SUCCESS
                
                self.db.update_enrichment_result(entity.id, emails, status)
                if on_progress:
                    on_progress(entity, emails, status)

            except Exception as e:
                logger.debug(f"Failed enriching {entity.business_name} ({website}): {e}")
                status = EnrichmentStatus.FAILED
                self.db.update_enrichment_result(entity.id, [], status)
                if on_progress:
                    on_progress(entity, [], status)

    async def _crawl_website_for_emails(self, client: httpx.AsyncClient, base_url: str) -> List[str]:
        """
        Crawls homepage and at most 2 internal contact/about pages to extract emails.
        """
        all_emails: Set[str] = set()

        # 1. Fetch Homepage
        try:
            resp = await client.get(base_url)
            if resp.status_code >= 400:
                return []
            
            html = resp.text
            all_emails.update(extract_valid_emails(html))

            # 2. Find Internal Contact Links (max 2)
            contact_links = self._discover_contact_links(base_url, html, max_links=settings.MAX_CONTACT_LINKS)

            # 3. Fetch each internal contact page
            for sub_url in contact_links:
                try:
                    sub_resp = await client.get(sub_url)
                    if sub_resp.status_code < 400:
                        all_emails.update(extract_valid_emails(sub_resp.text))
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Error fetching {base_url}: {e}")
            raise e

        return sorted(list(all_emails))

    def _discover_contact_links(self, base_url: str, html: str, max_links: int = 2) -> List[str]:
        """
        Parses HTML to find up to max_links internal links pointing to contact or about pages.
        """
        discovered: List[str] = []
        seen_urls: Set[str] = {base_url.rstrip("/")}

        try:
            soup = BeautifulSoup(html, "html.parser")
            base_parsed = urlparse(base_url)
            base_domain = base_parsed.netloc.lower()

            patterns = re.compile(r"contact|kontak|about|tentang|hubungi", re.IGNORECASE)

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("tel:"):
                    continue

                # Check text or href for contact/about keywords
                link_text = a.get_text(strip=True)
                if patterns.search(href) or patterns.search(link_text):
                    full_url = urljoin(base_url, href)
                    parsed_sub = urlparse(full_url)

                    # Ensure it is an internal domain
                    if parsed_sub.netloc.lower() == base_domain:
                        clean_sub = full_url.split("?")[0].rstrip("/")
                        if clean_sub not in seen_urls:
                            seen_urls.add(clean_sub)
                            discovered.append(clean_sub)
                            if len(discovered) >= max_links:
                                break

        except Exception as e:
            logger.debug(f"Error parsing contact links: {e}")

        return discovered
