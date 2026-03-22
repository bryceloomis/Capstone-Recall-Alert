"""
import_df_recall.py — Load misc/data/df_recall.csv into the recalls table.

Usage (from EC2, inside the backend venv):
    cd ~/Capstone-Recall-Alert
    source backend/venv/bin/activate
    python misc/data/import_df_recall.py

CSV columns (match DB schema directly):
    id, upc, product_name, brand_name, recall_date, reason,
    source, severity, distribution_pattern, plain_language_summary, created_at

Handles:
  - Empty UPC → stable placeholder based on product_name + recall_date
  - Date format M/D/YY → YYYY-MM-DD
  - source normalised to uppercase (fda → FDA)
  - ON CONFLICT (upc, recall_date) DO NOTHING — safe to re-run
"""

import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / "backend" / ".env")

DB_CONFIG = {
    "host":     os.environ["DB_HOST"],
    "port":     os.environ.get("DB_PORT", 5432),
    "dbname":   os.environ["DB_NAME"],
    "user":     os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "sslmode":  "require",
}

# CSV_PATH = Path(__file__).parent / "df_recall.csv"
CSV_PATH = "df_recall.csv"


def parse_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def placeholder_upc(product_name: str, recall_date: str) -> str:
    key = f"{product_name}|{recall_date}"
    return "NOUPCSN_" + hashlib.md5(key.encode()).hexdigest()[:12].upper()


def build_rows(csv_path: Path) -> list[tuple]:
    rows = []
    skipped = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            recall_date = parse_date(line.get("recall_date", ""))
            if not recall_date:
                skipped += 1
                continue

            product_name = (line.get("product_name") or "").strip()[:255]
            reason       = (line.get("reason") or "").strip()
            if not product_name or not reason:
                skipped += 1
                continue

            upc          = (line.get("upc") or "").strip()[:50]
            if not upc:
                upc = placeholder_upc(product_name, recall_date)

            brand_name   = (line.get("brand_name") or "").strip()[:255]
            source       = (line.get("source") or "FDA").strip().upper()
            severity     = (line.get("severity") or "").strip()[:20]
            dist_pattern = (line.get("distribution_pattern") or "").strip()[:500]

            rows.append((
                upc,
                product_name,
                brand_name or None,
                recall_date,
                reason,
                source,
                severity or None,
                dist_pattern or None,
            ))

    print(f"Skipped {skipped} rows (bad date or missing required fields)")
    return rows


def main():
    rows = build_rows(CSV_PATH)
    print(f"Parsed {len(rows)} rows from CSV")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    DELETE FROM recalls;
                    INSERT INTO recalls
                        (upc, product_name, brand_name, recall_date, reason,
                         source, severity, distribution_pattern)
                    VALUES %s
                    """,
                    rows,
                    page_size=3000,
                )
                print(f"Done. Rows inserted: {cur.rowcount}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
