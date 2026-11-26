from core.outreach import (
    DEFAULT_WA_TEMPLATE_1,
    build_whatsapp_link,
    format_wa_phone,
)
from storage.database import DatabaseManager


def test_format_wa_phone_indonesia():
    assert format_wa_phone("+62 812-3456-7890") == "6281234567890"
    assert format_wa_phone("081234567890") == "6281234567890"
    assert format_wa_phone("81234567890") == "6281234567890"
    assert format_wa_phone("123") == ""


def test_build_whatsapp_link_substitutes_business_name():
    link = build_whatsapp_link("+6281234567890", DEFAULT_WA_TEMPLATE_1, "Kopi Jogja")
    assert link is not None
    assert link.startswith("https://wa.me/6281234567890?text=")
    assert "Kopi%20Jogja" in link


def test_database_outreach_persistence(tmp_path):
    db_file = tmp_path / "test_outreach.db"
    db = DatabaseManager(db_url=f"sqlite:///{db_file}")

    entity, created = db.insert_or_update_entity(
        search_keyword="Cafe",
        business_name="Cafe Nusantara",
        category="Kafe",
        address="Jl. Kaliurang, Kec. Depok, Kabupaten Sleman",
        phone_number="+6281234567890",
        rating=4.8,
        reviews_count=120,
        google_url="https://www.google.com/maps/place/Cafe+Nusantara/@-7.75,110.38,17z",
    )
    assert created is True
    assert entity.is_replied is False
    assert entity.google_url is not None

    updated = db.update_outreach_batch([
        {
            "id": entity.id,
            "is_replied": True,
            "reply_notes": "Tertarik demo hari Jumat jam 10.",
        }
    ])
    assert updated == 1

    rows = db.get_all_entities_as_dicts()
    assert len(rows) == 1
    assert rows[0]["is_replied"] is True
    assert rows[0]["reply_notes"] == "Tertarik demo hari Jumat jam 10."
    assert rows[0]["google_url"].startswith("https://www.google.com/maps/place/")
