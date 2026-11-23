"""
Normalizer module: Phone number normalization, URL cleaning, domain blacklist filtering,
sanitized email regex extraction, and entity deduplication hashing.
"""
import re
import hashlib
from typing import Optional, List, Set
from urllib.parse import urlparse, urlunparse

from config.settings import settings


# Email regex complying with FR-06
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    re.IGNORECASE
)


def normalize_phone_number(raw_phone: Optional[str]) -> Optional[str]:
    """
    Normalizes Indonesian phone numbers (FR-04):
    - Cleans spaces, dashes, parentheses, non-digit chars (except leading +).
    - Converts '08...' to '+628...'
    - Converts local area codes like '021...', '022...', '031...' to '+6221...', '+6222...', '+6231...'
    - Adds '+' if starts with '62...'
    - Preserves '+62...'
    Returns None if empty or invalid.
    """
    if not raw_phone:
        return None

    s = raw_phone.strip()
    if not s:
        return None

    # Keep leading + if present, remove all other non-digits
    has_plus = s.startswith("+")
    digits_only = re.sub(r"\D", "", s)

    if not digits_only or len(digits_only) < 6:
        return None

    # Handle prefixes
    if digits_only.startswith("62"):
        normalized = f"+{digits_only}"
    elif digits_only.startswith("0"):
        # e.g. 08123456789 -> +628123456789
        # or 0215551234 -> +62215551234
        normalized = f"+62{digits_only[1:]}"
    elif has_plus:
        normalized = f"+{digits_only}"
    else:
        # Default assume local without leading 0 or international
        normalized = f"+62{digits_only}"

    return normalized


def normalize_url(raw_url: Optional[str]) -> Optional[str]:
    """
    Cleans and standardizes web URL format.
    Ensures scheme (http/https) and strips trailing slashes/fragments.
    """
    if not raw_url:
        return None

    url = raw_url.strip()
    if not url or url.startswith("javascript:") or url.startswith("mailto:"):
        return None

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        # Rebuild without fragments and query parameters
        clean = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            ""
        ))
        return clean if clean else None
    except Exception:
        return None


def is_blacklisted_domain(url: Optional[str]) -> bool:
    """
    Checks if a URL belongs to a social media / messaging platform (FR-05 & Edge Cases).
    e.g. wa.me, instagram.com, facebook.com, linktr.ee, tiktok.com.
    """
    if not url:
        return True

    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.netloc.lower().split(":")[0]
        if not host:
            return True

        # Check exact or parent domain match
        for blacklisted in settings.DOMAIN_BLACKLIST:
            if host == blacklisted or host.endswith(f".{blacklisted}"):
                return True
        return False
    except Exception:
        return True


def extract_valid_emails(text: str) -> List[str]:
    """
    Extracts valid email addresses from raw text/HTML (FR-06):
    - Filters out false positives (images ending with @2x.png, svg, js, css).
    - Filters out dummy/error tracking emails (sentry, wixpress, example.com).
    - Returns a deduplicated, sorted list of lowercased emails.
    """
    if not text:
        return []

    raw_matches = EMAIL_REGEX.findall(text)
    valid_emails: Set[str] = set()

    for match in raw_matches:
        candidate = match.strip().lower()

        # Remove trailing dots or commas
        candidate = candidate.rstrip(".,;:)")

        if "@" not in candidate:
            continue

        local_part, domain_part = candidate.split("@", 1)
        if not local_part or not domain_part:
            continue

        # Check for fake image or code asset extensions (e.g., logo@2x.png)
        parts = domain_part.split(".")
        if len(parts) < 2:
            continue

        last_ext = parts[-1].lower()
        if last_ext in settings.EMAIL_INVALID_EXTENSIONS:
            continue

        # Check if any part contains image extension
        if any(ext in domain_part for ext in settings.EMAIL_INVALID_EXTENSIONS):
            continue

        # Check ignored substrings (sentry, example.com, wixpress)
        if any(ignored in candidate for ignored in settings.EMAIL_IGNORE_SUBSTRINGS):
            continue

        # TLD must be alphabetic and at least 2 chars
        if not re.match(r"^[a-zA-Z]{2,15}$", last_ext):
            continue

        # Local part sanity check
        if len(local_part) > 64 or len(candidate) > 254:
            continue

        valid_emails.add(candidate)

    return sorted(list(valid_emails))


def generate_dedup_hash(business_name: str, phone: Optional[str] = None, address: Optional[str] = None) -> str:
    """
    Generates a deterministic hash for deduplication (FR-07):
    Combines normalized business name with normalized phone or address.
    """
    clean_name = re.sub(r"\s+", " ", business_name.strip().lower())
    clean_phone = (phone or "").strip()
    clean_address = re.sub(r"\s+", " ", (address or "").strip().lower())

    # Secondary identifier is phone if available, else address
    secondary = clean_phone if clean_phone else clean_address
    payload = f"{clean_name}::{secondary}"
    
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
