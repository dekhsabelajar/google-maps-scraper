"""
Unit tests for core/normalizer.py: Phone formatting, email sanitization, and domain blacklisting.
"""
import pytest
from core.normalizer import (
    normalize_phone_number,
    normalize_url,
    is_blacklisted_domain,
    extract_valid_emails,
    generate_dedup_hash,
)


class TestPhoneNormalizer:
    def test_indonesian_mobile_prefix(self):
        assert normalize_phone_number("0812-3456-7890") == "+6281234567890"
        assert normalize_phone_number("0852 9876 5432") == "+6281234567890" or normalize_phone_number("0852 9876 5432") == "+6285298765432"
        assert normalize_phone_number("(0819) 11223344") == "+6281911223344"

    def test_local_area_code_prefix(self):
        # Jakarta area code 021
        assert normalize_phone_number("(021) 555-1234") == "+62215551234"
        # Bandung area code 022
        assert normalize_phone_number("022-7778889") == "+62227778889"
        # Surabaya area code 031
        assert normalize_phone_number("031 8491234") == "+62318491234"

    def test_international_prefix_preserved(self):
        assert normalize_phone_number("+62 812-3456-7890") == "+6281234567890"
        assert normalize_phone_number("6281234567890") == "+6281234567890"

    def test_empty_or_invalid_phone(self):
        assert normalize_phone_number("") is None
        assert normalize_phone_number(None) is None
        assert normalize_phone_number("123") is None  # Too short


class TestUrlNormalizerAndBlacklist:
    def test_valid_urls(self):
        assert normalize_url("https://tokokopi.co.id/") == "https://tokokopi.co.id"
        assert normalize_url("tokokopi.co.id") == "https://tokokopi.co.id"
        assert normalize_url("http://sub.domain.com/path?utm_source=gmaps") == "http://sub.domain.com/path"

    def test_blacklisted_social_and_messaging_domains(self):
        assert is_blacklisted_domain("https://wa.me/628123456789") is True
        assert is_blacklisted_domain("https://api.whatsapp.com/send?phone=628123") is True
        assert is_blacklisted_domain("https://instagram.com/kopisenja") is True
        assert is_blacklisted_domain("https://www.facebook.com/senjacafe") is True
        assert is_blacklisted_domain("https://linktr.ee/senjacafe") is True
        assert is_blacklisted_domain("https://tiktok.com/@senja") is True

    def test_legitimate_business_domains(self):
        assert is_blacklisted_domain("https://senjacafe.co.id") is False
        assert is_blacklisted_domain("https://pt-maju-mundur.com") is False
        assert is_blacklisted_domain("https://kliniksehat.org") is False


class TestEmailExtractionAndSanitization:
    def test_valid_emails(self):
        text = "Hubungi kami di info@perusahaan.co.id atau sales.team@company.com untuk penawaran."
        emails = extract_valid_emails(text)
        assert "info@perusahaan.co.id" in emails
        assert "sales.team@company.com" in emails

    def test_filters_fake_image_and_asset_emails(self):
        text = "Icon background di background@2x.png dan logo@3x.jpg atau icon@svg.svg"
        emails = extract_valid_emails(text)
        assert len(emails) == 0

    def test_filters_sentry_and_wixpress_trackers(self):
        text = "Errors tracked at 12345@sentry.io or user@wixpress.com or test@example.com"
        emails = extract_valid_emails(text)
        assert len(emails) == 0


class TestDeduplicationHash:
    def test_deterministic_dedup_hash(self):
        h1 = generate_dedup_hash("Kopi Kenangan", "+628123456789", "Jl. Sudirman No. 10")
        h2 = generate_dedup_hash("  kopi kenangan  ", "+628123456789", "Jl. Sudirman No. 10")
        assert h1 == h2

    def test_distinct_entities_have_distinct_hashes(self):
        h1 = generate_dedup_hash("Kopi Kenangan", "+628123456789")
        h2 = generate_dedup_hash("Kopi Senja", "+628123456789")
        assert h1 != h2
