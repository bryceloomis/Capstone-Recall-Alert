"""
recall_update.py – FDA/USDA recall data refresh + APScheduler.

Teammates: fill in the TODO sections for USDA FSIS and any other sources.
The FDA openFDA enforcement endpoint is fully wired up.

Scheduler: runs run_recall_refresh() every 6 hours automatically when
           the FastAPI app starts (started by app.py via start_recall_scheduler()).

Manual trigger: POST /api/admin/refresh-recalls
  Returns: { inserted, skipped, alerts_generated, sources, errors }

Database requirement:
  The upsert logic uses ON CONFLICT (upc, recall_date) – if that constraint
  doesn't exist yet on your recalls table, add it once:

    ALTER TABLE recalls
      ADD CONSTRAINT recalls_upc_date_unique UNIQUE (upc, recall_date);

  (Safe to run even if data already exists – Postgres will error only if there
   are existing duplicate rows; fix those first with:
   DELETE FROM recalls a USING recalls b
   WHERE a.id < b.id AND a.upc = b.upc AND a.recall_date = b.recall_date;)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import requests as req
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter

from database import execute_query

log = logging.getLogger(__name__)

router = APIRouter()

# ── Constants ──────────────────────────────────────────────────────────────────

FDA_ENFORCEMENT_URL = "https://api.fda.gov/food/enforcement.json"
REQUEST_TIMEOUT     = 15   # seconds
RECALL_PAGE_LIMIT   = 100  # records per FDA API page (max 1000)

# ── FDA fetch ──────────────────────────────────────────────────────────────────

def fetch_fda_recalls(limit: int = RECALL_PAGE_LIMIT, skip: int = 0) -> list[dict]:
    """
    Fetch food recall enforcement records from the openFDA API.

    Reference: https://open.fda.gov/apis/food/enforcement/
    Returns raw list of FDA enforcement records (dicts).

    To paginate all results, call repeatedly with increasing `skip`:
        page 1: skip=0,   limit=100
        page 2: skip=100, limit=100
        ...until results is shorter than limit.
    """
    try:
        resp = req.get(
            FDA_ENFORCEMENT_URL,
            params={
                "limit": limit,
                "skip":  skip,
                # Optional: filter to voluntary recalls only
                # "search": "voluntary_mandated:Voluntary",
            },
            headers={"User-Agent": "FoodRecallAlert/0.2"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as exc:
        log.error("FDA API fetch error (skip=%d): %s", skip, exc)
        return []


# ── USDA stub ──────────────────────────────────────────────────────────────────

def fetch_usda_recalls() -> list[dict]:
    """
    TODO: Fetch food recall data from USDA FSIS.

    Reference: https://www.fsis.usda.gov/recalls
    The FSIS recall data is available at:
      https://www.fsis.usda.gov/fsis/api/recall/v/1
    or as an RSS feed:
      https://www.fsis.usda.gov/rss/recalls.xml

    Return format should match map_usda_to_db() output below.
    Replace this stub and implement map_usda_to_db() when ready.
    """
    # TODO: implement USDA fetch
    log.info("USDA fetch not yet implemented – skipping.")
    return []


# ── Field mappers ──────────────────────────────────────────────────────────────

def _extract_upc_from_code_info(code_info: str) -> Optional[str]:
    """
    Try to pull a 12- or 13-digit UPC/EAN from FDA's free-text code_info field.
    Returns the first match, or None if none found.
    """
    if not code_info:
        return None
    match = re.search(r"\b(\d{12,13})\b", code_info)
    return match.group(1) if match else None


def map_fda_to_db(record: dict) -> Optional[dict]:
    """
    Map a raw FDA enforcement record to our recalls table schema.

    FDA fields used:
      product_description  → product_name
      recalling_firm        → firm_name
      recall_initiation_date → recall_date   (format: YYYYMMDD → YYYY-MM-DD)
      reason_for_recall     → reason
      classification        → severity       (Class I / II / III)
      distribution_pattern  → distribution_pattern
      code_info             → UPC extraction attempt
      status                → filter: skip "Terminated" recalls

    Returns None if the record is missing critical fields.
    """
    # Skip terminated / archived recalls
    if (record.get("status") or "").lower() in ("terminated", "completed", "closed"):
        return None

    product_name = (record.get("product_description") or "").strip()
    if not product_name:
        return None

    # Parse YYYYMMDD → YYYY-MM-DD
    raw_date = record.get("recall_initiation_date") or ""
    try:
        recall_date = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        recall_date = raw_date or datetime.now().strftime("%Y-%m-%d")

    upc = _extract_upc_from_code_info(record.get("code_info") or "")

    # If no UPC found, use the recall number as a synthetic key
    # so the upsert still has something unique to ON CONFLICT on.
    if not upc:
        recall_number = (record.get("recall_number") or "").strip()
        upc = f"FDA-{recall_number}" if recall_number else None

    if not upc:
        return None

    return {
        "upc":                 upc,
        "product_name":        product_name[:500],   # match column width
        "brand_name":          (record.get("recalling_firm") or "")[:200],
        "recall_date":         recall_date,
        "reason":              (record.get("reason_for_recall") or "")[:1000],
        "severity":            (record.get("classification") or "")[:50],
        "firm_name":           (record.get("recalling_firm") or "")[:200],
        "distribution_pattern":(record.get("distribution_pattern") or "")[:500],
        "source":              "FDA",
    }


def map_usda_to_db(record: dict) -> Optional[dict]:
    """
    TODO: Map a USDA FSIS record to our recalls table schema.
    Implement once fetch_usda_recalls() is done.
    """
    # TODO: implement USDA field mapping
    return None


# ── DB upsert ──────────────────────────────────────────────────────────────────

def upsert_recall(record: dict) -> bool:
    """
    Insert a recall record, or update it if (upc, recall_date) already exists.
    Returns True if a new row was inserted, False if it was an update/no-op.

    Requires the unique constraint:
      ALTER TABLE recalls
        ADD CONSTRAINT recalls_upc_date_unique UNIQUE (upc, recall_date);
    """
    try:
        result = execute_query(
            """
            INSERT INTO recalls
              (upc, product_name, brand_name, recall_date, reason,
               severity, firm_name, distribution_pattern, source)
            VALUES
              (%(upc)s, %(product_name)s, %(brand_name)s, %(recall_date)s,
               %(reason)s, %(severity)s, %(firm_name)s, %(distribution_pattern)s,
               %(source)s)
            ON CONFLICT (upc, recall_date)
            DO UPDATE SET
              product_name        = EXCLUDED.product_name,
              brand_name          = EXCLUDED.brand_name,
              reason              = EXCLUDED.reason,
              severity            = EXCLUDED.severity,
              firm_name           = EXCLUDED.firm_name,
              distribution_pattern = EXCLUDED.distribution_pattern,
              source              = EXCLUDED.source
            RETURNING (xmax = 0) AS inserted;
            """,
            record,
        )
        # xmax = 0 means the row was freshly inserted (not updated)
        return bool(result and result[0].get("inserted"))
    except Exception as exc:
        log.error("upsert_recall error for upc=%s: %s", record.get("upc"), exc)
        return False


# ── Alert generation ──────────────────────────────────────────────────────────

def generate_alerts_for_new_recalls() -> int:
    """
    After importing new recalls, find users whose saved grocery items
    match a recalled product and create alert rows for them.

    Matches on product_upc (exact UPC) from user_carts vs recalls.upc.
    Skips users who already have an alert for that recall.

    Returns the number of new alert rows created.
    """
    try:
        # Find (user_id, recall_id) pairs that don't have an alert yet
        new_pairs = execute_query(
            """
            SELECT DISTINCT
                uc.user_id,
                r.id         AS recall_id,
                uc.product_upc,
                uc.product_name
            FROM user_carts uc
            JOIN recalls r
                ON uc.product_upc = r.upc
            LEFT JOIN alerts a
                ON a.user_id = uc.user_id AND a.recall_id = r.id
            WHERE a.id IS NULL;
            """
        )

        count = 0
        for pair in new_pairs:
            try:
                execute_query(
                    """
                    INSERT INTO alerts (user_id, recall_id, product_upc, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING;
                    """,
                    (pair["user_id"], pair["recall_id"], pair["product_upc"]),
                )
                count += 1
            except Exception as exc:
                log.warning(
                    "Could not insert alert for user=%s recall=%s: %s",
                    pair["user_id"], pair["recall_id"], exc,
                )

        if count:
            log.info("Generated %d new alerts.", count)
        return count

    except Exception as exc:
        log.error("generate_alerts_for_new_recalls error: %s", exc)
        return 0


# ── Main refresh pipeline ─────────────────────────────────────────────────────

def run_recall_refresh() -> dict:
    """
    Full recall refresh pipeline:
      1. Fetch from all sources (FDA + USDA stub)
      2. Map to DB schema
      3. Upsert each record
      4. Generate alerts for affected users

    Called automatically by APScheduler every 6 hours,
    and manually via POST /api/admin/refresh-recalls.

    Returns a summary dict.
    """
    log.info("Starting recall refresh...")
    inserted = 0
    skipped  = 0
    errors   = []

    # ── FDA ───────────────────────────────────────────────────────────────────
    fda_raw = fetch_fda_recalls()
    log.info("FDA: fetched %d raw records.", len(fda_raw))

    for raw in fda_raw:
        mapped = map_fda_to_db(raw)
        if not mapped:
            skipped += 1
            continue
        was_inserted = upsert_recall(mapped)
        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    # ── USDA (stub) ────────────────────────────────────────────────────────────
    usda_raw = fetch_usda_recalls()
    log.info("USDA: fetched %d raw records (stub).", len(usda_raw))
    for raw in usda_raw:
        mapped = map_usda_to_db(raw)
        if not mapped:
            skipped += 1
            continue
        was_inserted = upsert_recall(mapped)
        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts_generated = generate_alerts_for_new_recalls()

    summary = {
        "inserted":          inserted,
        "skipped":           skipped,
        "alerts_generated":  alerts_generated,
        "sources":           ["FDA", "USDA (stub)"],
        "errors":            errors,
        "timestamp":         datetime.now().isoformat(),
    }
    log.info("Recall refresh complete: %s", summary)
    return summary


# ── Scheduler ─────────────────────────────────────────────────────────────────

_scheduler: Optional[BackgroundScheduler] = None


def start_recall_scheduler():
    """
    Start a background thread that calls run_recall_refresh() every 6 hours.
    Safe to call multiple times – will not start a second scheduler.
    Called from app.py's @app.on_event("startup").
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        log.info("Recall scheduler already running – skipping start.")
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_recall_refresh,
        trigger="interval",
        hours=6,
        id="recall_refresh",
        replace_existing=True,
        max_instances=1,           # don't stack if a run takes >6 hours
        misfire_grace_time=300,    # 5-minute grace window if server is busy
    )
    _scheduler.start()
    log.info("Recall scheduler started – refresh every 6 hours.")

    # Run once immediately on startup so the DB is fresh right away
    # (comment out if you don't want an immediate run on every deploy)
    try:
        run_recall_refresh()
    except Exception as exc:
        log.error("Initial recall refresh failed: %s", exc)


# ── Manual trigger endpoint ────────────────────────────────────────────────────

@router.post("/api/admin/refresh-recalls")
async def manual_refresh_recalls():
    """
    Manually trigger a full recall refresh.
    Useful for testing or forcing an immediate update without waiting 6 hours.

    Returns: { inserted, skipped, alerts_generated, sources, errors, timestamp }
    """
    import asyncio
    # run_recall_refresh is synchronous (psycopg2 + requests); run in thread
    summary = await asyncio.to_thread(run_recall_refresh)
    return summary
