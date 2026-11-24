"""
Batch Scraper for 7 B2B Micro-SaaS Niches across DIY (Yogyakarta, Sleman, Bantul), Magelang, and Klaten.
Extracts business entities, phone numbers, websites, ratings, and total review counts into structured CSVs.
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.maps_worker import MapsWorker
from storage.database import DatabaseManager
from storage.exporter import export_to_csv, export_to_json

logger = logging.getLogger("batch_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NICHES = [
    {
        "id": 1,
        "niche": "Kost Eksklusif",
        "slug": "kost_eksklusif",
        "keywords": [
            "Kost eksklusif Jogja",
            "Kost eksklusif Sleman",
            "Kost eksklusif Bantul",
            "Kost eksklusif Magelang",
            "Kost eksklusif Klaten",
        ]
    },
    {
        "id": 2,
        "niche": "Gym & Pusat Kebugaran",
        "slug": "gym_kebugaran",
        "keywords": [
            "Gym Yogyakarta",
            "Gym Sleman",
            "Fitness center Jogja",
            "Gym Magelang",
            "Gym Klaten",
        ]
    },
    {
        "id": 3,
        "niche": "Rental Kendaraan & Kamera",
        "slug": "rental_kendaraan_kamera",
        "keywords": [
            "Rental kamera Jogja",
            "Rental mobil Jogja",
            "Rental motor Sleman",
            "Rental mobil Magelang",
            "Rental mobil Klaten",
        ]
    },
    {
        "id": 4,
        "niche": "Barbershop & Salon",
        "slug": "barbershop_salon",
        "keywords": [
            "Barbershop Jogja",
            "Barbershop Sleman",
            "Salon kecantikan Jogja",
            "Barbershop Magelang",
            "Barbershop Klaten",
        ]
    },
    {
        "id": 5,
        "niche": "Percetakan Digital",
        "slug": "percetakan_digital",
        "keywords": [
            "Percetakan digital Jogja",
            "Digital printing Sleman",
            "Percetakan Bantul",
            "Percetakan Magelang",
            "Percetakan Klaten",
        ]
    },
    {
        "id": 6,
        "niche": "Car Wash",
        "slug": "car_wash",
        "keywords": [
            "Car wash Jogja",
            "Cuci mobil Sleman",
            "Cuci mobil Bantul",
            "Car wash Magelang",
            "Cuci mobil Klaten",
        ]
    },
    {
        "id": 7,
        "niche": "Pet Shop, Grooming, & Vet",
        "slug": "pet_shop_vet",
        "keywords": [
            "Pet shop Jogja",
            "Pet shop Sleman",
            "Klinik hewan Jogja",
            "Klinik hewan Magelang",
            "Pet shop Klaten",
        ]
    },
]


EXPORTS_DIR = PROJECT_ROOT / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def rebuild_all_summaries(db: DatabaseManager):
    """
    Scans all 7 niches across database, regenerates individual niche CSVs,
    master aggregated contacts CSV, and master summary CSV.
    """
    summary_data = []
    all_combined_entities = []
    seen_global_ids = set()

    for item in NICHES:
        niche_name = item["niche"]
        slug = item["slug"]
        keywords = item["keywords"]

        niche_entities = []
        seen_ids = set()
        for kw in keywords:
            for ent in db.get_all_entities_as_dicts(keyword=kw):
                if ent["id"] not in seen_ids:
                    seen_ids.add(ent["id"])
                    ent["niche"] = niche_name
                    niche_entities.append(ent)
                if ent["id"] not in seen_global_ids:
                    seen_global_ids.add(ent["id"])
                    all_combined_entities.append(ent)

        csv_path = EXPORTS_DIR / f"niche_{item['id']}_{slug}.csv"
        json_path = EXPORTS_DIR / f"niche_{item['id']}_{slug}.json"
        if niche_entities:
            export_to_csv(niche_entities, output_path=csv_path)
            export_to_json(niche_entities, output_path=json_path)

        ratings = [e["rating"] for e in niche_entities if e.get("rating")]
        reviews = [e["reviews_count"] for e in niche_entities if e.get("reviews_count")]

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        avg_reviews = round(sum(reviews) / len(reviews), 1) if reviews else 0.0
        max_reviews = max(reviews) if reviews else 0

        top_business = "-"
        if reviews:
            sorted_by_rev = sorted(niche_entities, key=lambda x: (x.get("reviews_count") or 0), reverse=True)
            top_business = f"{sorted_by_rev[0]['business_name']} ({sorted_by_rev[0].get('reviews_count')} reviews)"

        diy_count = sum(1 for e in niche_entities if any(loc in (e.get("address") or "") + (e.get("search_keyword") or "") for loc in ["Jogja", "Yogyakarta", "Sleman", "Bantul"]))
        magelang_count = sum(1 for e in niche_entities if "Magelang" in (e.get("address") or "") + (e.get("search_keyword") or ""))
        klaten_count = sum(1 for e in niche_entities if "Klaten" in (e.get("address") or "") + (e.get("search_keyword") or ""))

        summary_data.append({
            "niche_id": item["id"],
            "niche_name": niche_name,
            "total_sample_scraped": len(niche_entities),
            "avg_rating": avg_rating,
            "avg_reviews": avg_reviews,
            "max_reviews": max_reviews,
            "top_active_business": top_business,
            "diy_sample": diy_count,
            "magelang_sample": magelang_count,
            "klaten_sample": klaten_count,
            "csv_path": str(csv_path),
        })

    # Export master aggregated CSV
    if all_combined_entities:
        all_csv = EXPORTS_DIR / "all_7_niches_contacts.csv"
        export_to_csv(all_combined_entities, output_path=all_csv)
        print(f"[SUCCESS] Aggregated dataset ({len(all_combined_entities)} entities) saved to: {all_csv}")

    # Export master summary CSV
    import csv
    summary_csv = EXPORTS_DIR / "master_7_niches_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "niche_id", "niche_name", "total_sample_scraped",
            "avg_rating", "avg_reviews", "max_reviews",
            "top_active_business", "diy_sample", "magelang_sample", "klaten_sample", "csv_path"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_data:
            writer.writerow(row)

    print(f"[SUCCESS] Master summary saved to: {summary_csv}")
    print("\n======================================================================")
    print("RINGKASAN BENCHMARK TERKINI SELURUH 7 NICHE")
    print("======================================================================")
    for s in summary_data:
        print(f"#{s['niche_id']} {s['niche_name']}: {s['total_sample_scraped']} entitas | Rata-rata Review: {s['avg_reviews']} | Top: {s['top_active_business']}")
    return summary_data


async def run_batch_scrape(limit_per_keyword: int = 25, target_niche_id: int = None):
    db = DatabaseManager()
    worker = MapsWorker(db_manager=db, headless=True)

    print("======================================================================")
    print(f"STARTING COMPREHENSIVE BATCH SCRAPER (LIMIT: {limit_per_keyword}/KW)")
    print("======================================================================")

    niches_to_run = [n for n in NICHES if target_niche_id is None or n["id"] == target_niche_id]

    for item in niches_to_run:
        niche_name = item["niche"]
        keywords = item["keywords"]
        print(f"\n>>> Memproses Niche #{item['id']}: {niche_name}")

        for kw in keywords:
            print(f"  -> Scraping: '{kw}' (target: {limit_per_keyword})...")
            try:
                await worker.search_and_extract(
                    keyword=kw,
                    limit=limit_per_keyword
                )
            except Exception as e:
                logger.error(f"Error scraping '{kw}': {e}")

    # Always rebuild all summaries across all 7 niches after scraping
    rebuild_all_summaries(db)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch scrape 7 niches")
    parser.add_argument("--limit", type=int, default=25, help="Limit candidates per keyword")
    parser.add_argument("--niche", type=int, default=None, help="Scrape specific niche ID (1-7)")
    args = parser.parse_args()
    asyncio.run(run_batch_scrape(limit_per_keyword=args.limit, target_niche_id=args.niche))
