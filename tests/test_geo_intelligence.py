import pandas as pd

from core.geo_intelligence import (
    build_whitespace_summary,
    enrich_geo_and_scale_df,
    extract_admin_region,
    extract_coords_from_url,
)


def test_extract_coords_prefers_pin_markers():
    url = (
        "https://www.google.com/maps/place/Test/@-7.700000,110.300000,15z/"
        "data=!4m6!3m5!1s0x2e7a59!8m2!3d-7.7743444!4d110.4092875"
    )
    lat, lon = extract_coords_from_url(url)
    assert lat == -7.774344
    assert lon == 110.409288


def test_extract_coords_fallback_to_viewport():
    url = "https://www.google.com/maps/place/Test/@-7.765432,110.389123,17z"
    lat, lon = extract_coords_from_url(url)
    assert lat == -7.765432
    assert lon == 110.389123


def test_extract_admin_region_parses_kecamatan_and_kabupaten():
    addr = "Jl. Kaliurang KM 7, Kec. Depok, Kabupaten Sleman, Daerah Istimewa Yogyakarta 55281"
    kec, kota = extract_admin_region(addr)
    assert kec == "Depok"
    assert kota == "Sleman"


def test_enrich_geo_and_scale_detects_chains_and_umkm():
    df = pd.DataFrame([
        {
            "business_name": "Kopi Kenangan Seturan",
            "address": "Jl. Seturan, Kec. Depok, Kabupaten Sleman",
            "website_url": "https://kopikenangan.com",
            "google_url": "https://www.google.com/maps/place/A/@-7.77,110.41,17z",
            "reviews_count": 250,
            "rating": 4.7,
        },
        {
            "business_name": "Kopi Kenangan Malioboro",
            "address": "Jl. Malioboro, Kec. Danurejan, Kota Yogyakarta",
            "website_url": "https://kopikenangan.com",
            "google_url": "https://www.google.com/maps/place/B/@-7.79,110.36,17z",
            "reviews_count": 400,
            "rating": 4.8,
        },
        {
            "business_name": "Warung Kopi Mandiri",
            "address": "Jl. Palagan, Kec. Ngaglik, Kabupaten Sleman",
            "website_url": "",
            "google_url": "https://www.google.com/maps/place/C/@-7.72,110.38,17z",
            "reviews_count": 120,
            "rating": 4.6,
        },
    ])

    enriched = enrich_geo_and_scale_df(df)
    assert enriched.loc[0, "business_scale"] == "Jaringan / Multi-Cabang"
    assert enriched.loc[0, "branch_count"] == 2
    assert enriched.loc[2, "business_scale"] == "UMKM Tunggal"
    assert enriched.loc[2, "kecamatan"] == "Ngaglik"
    assert enriched.loc[0, "latitude"] == -7.77

    ws = build_whitespace_summary(enriched)
    assert not ws.empty
    assert set(["kecamatan", "whitespace_score", "status_pasar"]).issubset(ws.columns)
