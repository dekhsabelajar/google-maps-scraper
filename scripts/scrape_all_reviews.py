"""
Mass Customer Reviews Harvester CLI.
Extracts customer reviews across all Google Maps business entities in DIY, Magelang, and Klaten.
Saves data directly to SQLite and exports to exports/scraped_business_reviews.csv.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from core.review_worker import ReviewWorker
from storage.database import DatabaseManager

logger = logging.getLogger("mass_review_cli")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run():
    parser = argparse.ArgumentParser(description="Scrape customer reviews across Google Maps business entities")
    parser.add_argument("--limit-places", type=int, default=None, help="Total businesses to process in this run")
    parser.add_argument("--limit-per-niche", type=int, default=None, help="Number of businesses per niche (1-7)")
    parser.add_argument("--max-reviews", type=int, default=10, help="Max reviews to extract per business")
    parser.add_argument("--niche", type=str, default=None, help="Filter by niche name substring")
    parser.add_argument("--min-reviews", type=int, default=1, help="Only process places with >= N reviews on Maps")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    parser.add_argument("--re-scrape", action="store_true", default=False, help="Do not skip already reviewed places")
    args = parser.parse_args()

    contacts_csv = PROJECT_ROOT / "exports" / "all_7_niches_contacts.csv"
    if not contacts_csv.exists():
        print(f"Error: {contacts_csv} not found.")
        sys.exit(1)

    df = pd.read_csv(contacts_csv)
    print(f"Loaded {len(df)} total business contacts from {contacts_csv.name}")

    # Accurate Niche Mapping
    kw_map = {
        "kost": "Kost Eksklusif",
        "gym": "Gym & Pusat Kebugaran",
        "fitness": "Gym & Pusat Kebugaran",
        "rental": "Rental Kendaraan & Kamera",
        "kamera": "Rental Kendaraan & Kamera",
        "barbershop": "Barbershop & Salon",
        "salon": "Barbershop & Salon",
        "percetakan": "Percetakan Digital",
        "printing": "Percetakan Digital",
        "car wash": "Car Wash & Detailing",
        "cuci": "Car Wash & Detailing",
        "pet": "Pet Shop, Grooming, & Vet",
        "hewan": "Pet Shop, Grooming, & Vet",
    }

    def resolve_niche(row):
        k = str(row.get("search_keyword", "")).lower()
        for key, n in kw_map.items():
            if key in k:
                return n
        return "Bisnis Terpilih"

    df["niche"] = df.apply(resolve_niche, axis=1)

    # Filter by specific niche if requested
    if args.niche:
        df = df[df["niche"].str.lower().str.contains(args.niche.lower())]
        print(f"Filtered for niche matching '{args.niche}': {len(df)} businesses found.")

    # Filter minimum reviews count and sort descending (highest active first)
    if "reviews_count" in df.columns and args.min_reviews > 0:
        df = df[df["reviews_count"] >= args.min_reviews]
        df = df.sort_values(by="reviews_count", ascending=False)

    # Filter per-niche limit if specified
    if args.limit_per_niche:
        selected_dfs = []
        for n_name, group in df.groupby("niche"):
            selected_dfs.append(group.head(args.limit_per_niche))
        df = pd.concat(selected_dfs).reset_index(drop=True)
        print(f"Selected {len(df)} businesses ({args.limit_per_niche} per niche across {df['niche'].nunique()} niches).")

    places = df.to_dict(orient="records")
    if args.limit_places and not args.limit_per_niche:
        places = places[:args.limit_places]

    print(f"\nTargeting {len(places)} businesses for customer review harvesting...")
    print(f"Settings: Max {args.max_reviews} reviews/place | Min {args.min_reviews} reviews on Maps | Headless: {args.headless}\n")

    db = DatabaseManager()
    worker = ReviewWorker(db_manager=db, headless=args.headless)
    
    new_reviews = asyncio.run(worker.scrape_reviews_for_places(
        places=places,
        max_reviews_per_place=args.max_reviews,
        skip_already_reviewed=not args.re_scrape,
    ))

    total_in_db = worker.export_all_reviews_csv()
    print("\n" + "=" * 70)
    print(f"HARVEST SELESAI: Berhasil menambahkan {new_reviews} ulasan baru.")
    print(f"Total kumulatif ulasan di basis data SQLite & CSV: {total_in_db} ulasan.")
    print(f"Lokasi CSV: {PROJECT_ROOT / 'exports' / 'scraped_business_reviews.csv'}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
