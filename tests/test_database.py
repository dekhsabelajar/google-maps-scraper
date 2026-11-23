"""
Unit tests for storage/database.py: Schema, deduplication accuracy, and state transitions.
"""
import pytest
from storage.database import DatabaseManager, EnrichmentStatus


@pytest.fixture
def test_db():
    # Use isolated in-memory SQLite database for testing
    return DatabaseManager("sqlite:///:memory:")


class TestDatabaseOperations:
    def test_insert_entity(self, test_db):
        entity, is_new = test_db.insert_or_update_entity(
            search_keyword="digital agency",
            business_name="Agency Kreatif",
            category="Advertising agency",
            address="Jl. Thamrin No. 5",
            phone_number="+62215551234",
            website_url="https://agencykreatif.id",
        )
        assert is_new is True
        assert entity.business_name == "Agency Kreatif"
        assert entity.enrichment_status == EnrichmentStatus.PENDING

    def test_deduplication_zero_percent_duplicate(self, test_db):
        # Insert entity 1st time
        e1, is_new1 = test_db.insert_or_update_entity(
            search_keyword="cafe jakarta",
            business_name="Cafe Batavia",
            phone_number="+62216915531",
            address="Kota Tua Jakarta",
        )
        assert is_new1 is True

        # Insert same business 2nd time with slight variation in whitespace
        e2, is_new2 = test_db.insert_or_update_entity(
            search_keyword="cafe jakarta",
            business_name="  Cafe Batavia  ",
            phone_number="+62216915531",
            address="Kota Tua Jakarta",
        )
        assert is_new2 is False
        assert e1.id == e2.id
        assert test_db.count_entities() == 1

    def test_status_transitions(self, test_db):
        entity, _ = test_db.insert_or_update_entity(
            search_keyword="hotel",
            business_name="Grand Hotel",
            website_url="https://grandhotel.com",
        )
        assert entity.enrichment_status == EnrichmentStatus.PENDING

        # Update enrichment result
        test_db.update_enrichment_result(
            entity.id,
            emails=["reservation@grandhotel.com"],
            status=EnrichmentStatus.SUCCESS,
        )

        all_items = test_db.get_all_entities_as_dicts()
        saved = all_items[0]
        assert saved["enrichment_status"] == "SUCCESS"
        assert "reservation@grandhotel.com" in saved["extracted_emails"]

    def test_resume_mode_fetches_only_pending(self, test_db):
        # 1 with website -> PENDING
        test_db.insert_or_update_entity(
            search_keyword="resto",
            business_name="Resto 1",
            website_url="https://resto1.com",
            enrichment_status=EnrichmentStatus.PENDING,
        )
        # 1 already SUCCESS
        test_db.insert_or_update_entity(
            search_keyword="resto",
            business_name="Resto 2",
            website_url="https://resto2.com",
            enrichment_status=EnrichmentStatus.SUCCESS,
        )
        # 1 without website -> NO_WEBSITE
        test_db.insert_or_update_entity(
            search_keyword="resto",
            business_name="Resto 3",
            website_url=None,
            enrichment_status=EnrichmentStatus.NO_WEBSITE,
        )

        pending = test_db.get_pending_enrichment_entities()
        assert len(pending) == 1
        assert pending[0].business_name == "Resto 1"
