"""
Export routines: CSV and JSON exporters for extracted Google Maps and business contact data.
"""
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import settings


def export_to_csv(entities: List[Dict[str, Any]], output_path: Optional[Path] = None, keyword: str = "data") -> Path:
    """
    Exports business entities list to a standard CSV file (FR-08).
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_kw = "".join(c if c.isalnum() else "_" for c in keyword)
        output_path = settings.EXPORT_DIR / f"leads_{safe_kw}_{timestamp}.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "search_keyword",
        "business_name",
        "category",
        "rating",
        "reviews_count",
        "address",
        "phone_number",
        "website_url",
        "extracted_emails",
        "enrichment_status",
        "scraped_at",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for e in entities:
            row = dict(e)
            # Format emails as comma-separated string
            emails = row.get("extracted_emails", [])
            if isinstance(emails, list):
                row["extracted_emails"] = ", ".join(emails)
            writer.writerow(row)

    return output_path


def export_to_json(entities: List[Dict[str, Any]], output_path: Optional[Path] = None, keyword: str = "data") -> Path:
    """
    Exports business entities list to a structured JSON file (FR-08).
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_kw = "".join(c if c.isalnum() else "_" for c in keyword)
        output_path = settings.EXPORT_DIR / f"leads_{safe_kw}_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)

    return output_path
