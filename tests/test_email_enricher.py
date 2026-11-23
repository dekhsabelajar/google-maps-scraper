"""
Unit tests for core/email_enricher.py: Link parsing and crawler logic.
"""
import pytest
from core.email_enricher import EmailEnricher
from storage.database import DatabaseManager


class TestEmailEnricherParser:
    def test_discover_contact_links(self):
        enricher = EmailEnricher(db_manager=DatabaseManager("sqlite:///:memory:"))
        base_url = "https://kreatifcorp.com"
        sample_html = """
        <html>
            <body>
                <header>
                    <a href="/about-us">Tentang Kami</a>
                    <a href="/contact">Hubungi Kami</a>
                    <a href="/products">Produk</a>
                    <a href="https://instagram.com/kreatif">Instagram</a>
                </header>
            </body>
        </html>
        """
        links = enricher._discover_contact_links(base_url, sample_html, max_links=2)
        assert len(links) <= 2
        assert "https://kreatifcorp.com/about-us" in links
        assert "https://kreatifcorp.com/contact" in links
        assert "https://instagram.com/kreatif" not in links  # External domain excluded
