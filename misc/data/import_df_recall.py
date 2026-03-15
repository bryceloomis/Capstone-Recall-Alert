"""
import_df_recall.py — Load misc/data/df_recall.csv into the recalls table.

Usage (from EC2, inside the backend venv):
    cd ~/Capstone-Recall-Alert
    source backend/venv/bin/activate
    python misc/data/import_df_recall.py

Handles:
  - UPC column is a stringified list: ['upc1', 'upc2'] or []
    → one DB row per UPC; placeholder for empty-UPC rows
  - Date format M/D/YY → YYYY-MM-DD
  - ON CONFLICT (upc, recall_date) DO NOTHING — safe to re-run
"""

import ast
import csv
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load .env from backend/
load_dotenv(Path(__file__).parent.parent.parent / "backend" / ".env")

DB_CONFIG = {
    "host":     os.environ["DB_HOST"],
    "port":     os.environ.get("DB_PORT", 5432),
    "dbname":   os.environ["DB_NAME"],
    "user":     os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "sslmode":  "require",
}

CSV_PATH = Path(__file__).parent / "df_recall.csv"

SEVERITY_MAP = {
    "class i":   "CLASS_I",
    "class ii":  "CLASS_II",
    "class iii": "CLASS_III",
}


def parse_date(raw: str) -> str | None:
    """Convert M/D/YY or M/D/YYYY to YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_upcs(raw: str) -> list[str]:
    """Parse stringified list '['upc1', 'upc2']' → list of clean UPC strings."""
    raw = raw.strip()
    if not raw or raw in ("[]", "['']", '[""]'):
        return []
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(u).strip() for u in parsed if str(u).strip()]
    except Exception:
        # Might be a bare UPC string
        if raw.isdigit():
            return [raw]
    return []


def placeholder_upc(product_name: str, recall_date: str) -> str:
    """Generate a stable placeholder UPC for recalls with no UPC."""
    key = f"{product_name}|{recall_date}"
    return "NOUPCSN_" + hashlib.md5(key.encode()).hexdigest()[:12].upper()


def build_rows(csv_path: Path) -> list[tuple]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            recall_date = parse_date(line.get("date", ""))
            if not recall_date:
                continue  # skip rows with unparseable dates

            product_name = (line.get("product_description") or "").strip()[:255]
            reason       = (line.get("product_reason") or "").strip()
            firm_name    = (line.get("recalling_firm") or "").strip()[:200]
            dist_pattern = (line.get("distribution_pattern") or "").strip()[:500]
            sev_raw      = (line.get("classification_type") or "").strip().lower()
            severity     = SEVERITY_MAP.get(sev_raw)

            if not product_name or not reason:
                continue  # skip incomplete rows

            upcs = parse_upcs(line.get("upc", ""))
            if not upcs:
                upcs = [placeholder_upc(product_name, recall_date)]

            for upc in upcs:
                rows.append((
                    upc[:50],
                    product_name,
                    "",           # brand_name — not cleanly separable in this CSV
                    recall_date,
                    reason,
                    "FDA",        # source
                    severity,
                    firm_name or None,
                    dist_pattern or None,
                ))
    return rows


def main():
    rows = build_rows(CSV_PATH)
    print(f"Parsed {len(rows)} rows from CSV (after UPC expansion)")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO recalls
                        (upc, product_name, brand_name, recall_date, reason,
                         source, severity, firm_name, distribution_pattern)
                    VALUES %s
                    ON CONFLICT (upc, recall_date) DO NOTHING
                    """,
                    rows,
                    page_size=200,
                )
                print(f"Done. Rows affected: {cur.rowcount}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
