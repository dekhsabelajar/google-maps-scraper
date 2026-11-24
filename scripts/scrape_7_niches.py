"""
Batch Scraper for 7 B2B Micro-SaaS Niches across DIY (Yogyakarta, Sleman, Bantul), Magelang, and Klaten.
Extracts business entities, phone numbers, websites, ratings, and total review counts into structured CSVs.
"""
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any

from core.maps_worker import MapsWorker
from storage.database import DatabaseManager
from storage.exporter import export_to_csv, export_to_json

logger = logging.getLogger("batch_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NICHES = [
    {
        "id": 1,
        "niche": "Kost Eksklusif",
        "keywords": [
            "Kost eksklusif Jogja",
            "Kost eksklusif Sleman",
            "Kost eksklusif Magelang",
            "Kost eksklusif Klaten",
        ]
    },
    {
        "id": 2,
        "niche": "Gym & Pusat Kebugaran",
        "keywords": [
            "Gym Yogyakarta",
            "Fitness Sleman",
            "Gym Magelang",
            "Gym Klaten",
        ]
    },
    {
        "id": 3,
        "niche": "Rental Kendaraan & Kamera",
        "keywords": [
            "Rental kamera Jogja",
            "Rental mobil motor Sleman",
            "Rental mobil Magelang",
            "Rental mobil Klaten",
        ]
    },
    {
        "id": 4,
        "niche": "Barbershop & Salon",
        "keywords": [
            "Barbershop Jogja",
            "Salon kecantikan Sleman",
            "Barbershop Magelang",
            "Barbershop Klaten",
        ]
    },
    {
        "id": 5,
        "niche": "Percetakan Digital",
        "keywords": [
            "Percetakan digital Jogja",
            "Digital printing Sleman",
            "Percetakan Magelang",
            "Percetakan Klaten",
        ]
    },
    {
        "id": 6,
        "niche": "Car Wash",
        "keywords": [
            "Car wash Jogja",
            "Cuci mobil Sleman",
            "Car wash Magelang",
            "Cuci mobil Klaten",
        ]
    },
    {
        "id": 7,
        "niche": "Pet Shop, Grooming, & Vet",
        "keywords": [
            "Pet shop Jogja",
            "Grooming hewan Sleman",
            "Klinik hewan Magelang",
            "Pet shop Klaten",
        ]
    },
]


async def run_batch_scrape(limit_per_keyword: int = 15):
    db = DatabaseManager()
    worker = MapsWorker(db_manager=db, headless=True)
    summary_data = []

    print("======================================================================")
    print("STARTING BATCH SCRAPER FOR 7 B2B NICHE (DIY, MAGELANG, KLATEN)")
    print("======================================================================")

    for item in NICHES:
        niche_name = item["niche"]
        keywords = item["keywords"]
        print(f"\n>>> Memproses Niche #{item['id']}: {niche_name}")
        niche_entities: List[Dict[str, Any]] = []

        for kw in keywords:
            print(f"  -> Scraping: '{kw}' (target: {limit_per_keyword})...")
            try:
                results = await worker.search_and_extract(
                    keyword=kw,
                    limit=limit_per_keyword
                )
                niche_entities.extend(results)
            except Exception as e:
                logger.error(f"Error scraping '{kw}': {e}")

        # Export per niche
        safe_name = "".join(c if c.isalnum() else "_" for c in niche_name).lower()
        csv_path = Path("exports") / f"leads_niche_{item['id']}_{safe_name}.csv"
        json_path = Path("exports") / f"leads_niche_{item['id']}_{safe_name}.json"
        
        # Get all unique entities from DB matching keywords
        niche_all = []
        seen_ids = set()
        for kw in keywords:
            for ent in db.get_all_entities_as_dicts(keyword=kw):
                if ent["id"] not in seen_ids:
                    seen_ids.add(ent["id"])
                    niche_all.append(ent)

        if niche_all:
            export_to_csv(niche_all, output_path=csv_path)
            export_to_json(niche_all, output_path=json_path)

        avg_reviews = 0
        rev_list = [e.get("reviews_count") for e in niche_all if e.get("reviews_count")]
        if rev_list:
            avg_reviews = sum(rev_list) / len(rev_list)

        summary_data.append({
            "niche": niche_name,
            "total_entities": len(niche_all),
            "avg_reviews": round(avg_reviews, 1),
            "csv_file": str(csv_path)
        })

    print("\n======================================================================")
    print("RINGKASAN HASIL SCRAPING 7 NICHE")
    print("======================================================================")
    for s in summary_data:
        print(f"- {s['niche']}: {s['total_entities']} entitas | Rata-rata review: {s['avg_reviews']} | File: {s['csv_file']}")


if __name__ == "__main__":
    asyncio.run(run_batch_scrape(limit_per_keyword=15))
