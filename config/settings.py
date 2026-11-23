"""
Configuration module for Google Maps Scraper and Email Enricher.
Includes delay settings, concurrency limits, proxies, timeouts, and domain blacklists.
"""
from pathlib import Path
from typing import Set, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    EXPORT_DIR: Path = BASE_DIR / "exports"
    DATABASE_PATH: Path = BASE_DIR / "data.db"
    
    # Stage 1: Maps Worker Settings
    DEFAULT_HEADLESS: bool = True
    MIN_SCROLL_DELAY: float = Field(default=1.5, description="Min random delay between actions in seconds")
    MAX_SCROLL_DELAY: float = Field(default=4.0, description="Max random delay between actions in seconds")
    MAX_BROWSER_INSTANCES: int = Field(default=1, ge=1, le=2, description="Max browser instances in Stage 1")
    MAPS_NAVIGATION_TIMEOUT: int = Field(default=30000, description="Navigation timeout in milliseconds")
    DEFAULT_RESULT_LIMIT: int = Field(default=100, description="Target number of results per keyword")

    # Stage 2: Email Enricher Settings
    EMAIL_CONCURRENCY: int = Field(default=15, ge=1, le=25, description="Async worker concurrency limit")
    HTTP_TIMEOUT: float = Field(default=10.0, description="HTTP request timeout in seconds")
    HTTP_VERIFY_SSL: bool = Field(default=False, description="Disable SSL verification for legacy websites")
    MAX_CONTACT_LINKS: int = Field(default=2, description="Max internal contact links to crawl per domain")

    # Proxy Configuration (Optional HTTP/SOCKS5)
    PROXY_SERVER: Optional[str] = Field(default=None, description="e.g. http://user:pass@host:port or socks5://host:port")
    
    # Blacklisted domains for Stage 2 email enrichment (FR-05 & Edge Cases)
    DOMAIN_BLACKLIST: Set[str] = {
        "wa.me",
        "api.whatsapp.com",
        "web.whatsapp.com",
        "chat.whatsapp.com",
        "whatsapp.com",
        "instagram.com",
        "www.instagram.com",
        "facebook.com",
        "www.facebook.com",
        "m.facebook.com",
        "fb.com",
        "linktr.ee",
        "twitter.com",
        "www.twitter.com",
        "x.com",
        "www.x.com",
        "tiktok.com",
        "www.tiktok.com",
        "t.me",
        "telegram.me",
        "linkedin.com",
        "www.linkedin.com",
        "youtube.com",
        "www.youtube.com",
        "pinterest.com",
        "maps.google.com",
        "goo.gl",
        "google.com",
        "bit.ly",
        "s.id",
    }

    # Contact discovery keywords in links (anchor text or href)
    CONTACT_URL_PATTERNS: List[str] = [
        "contact",
        "kontak",
        "about",
        "tentang",
        "hubungi",
        "reach-us",
        "contact-us",
        "about-us",
    ]

    # Email false positive extensions & patterns
    EMAIL_INVALID_EXTENSIONS: Set[str] = {
        "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "tiff",
        "css", "js", "woff", "woff2", "ttf", "eot", "mp4", "webm", "pdf"
    }

    # Fake/tracker email substrings to ignore
    EMAIL_IGNORE_SUBSTRINGS: List[str] = [
        "sentry",
        "wixpress",
        "example.com",
        "domain.com",
        "email.com",
        "yourdomain",
        "webpack",
        "cloudflare",
        "schema.org",
        "test@",
    ]

    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )


settings = Settings()
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
