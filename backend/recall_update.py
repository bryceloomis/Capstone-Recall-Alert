"""
recall_update.py – FDA recall data refresh + APScheduler.

The FDA openFDA enforcement endpoint is fully wired up.

Alert generation and email notifications live in user_alerts.py.

Scheduler: runs run_recall_refresh() every 6 hours automatically when
           the FastAPI app starts (started by app.py via start_recall_scheduler()).

Manual trigger: POST /api/admin/refresh-recalls
  Returns: { inserted, skipped, alerts_generated, sources, errors }

Database requirement:
  The upsert logic uses ON CONFLICT (product_name, recall_date) – if that
  constraint doesn't exist yet on your recalls table, add it once:

    ALTER TABLE recalls
      ADD CONSTRAINT recalls_product_date_unique UNIQUE (product_name, recall_date);

  (Safe to run even if data already exists – Postgres will error only if there
   are existing duplicate rows; fix those first with:
   DELETE FROM recalls a USING recalls b
   WHERE a.id < b.id AND a.product_name = b.product_name
     AND a.recall_date = b.recall_date;)
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

# Lazy import — LLM_services requires boto3 + Bedrock IAM; gracefully optional
try:
    from LLM_services import explain_recall as _explain_recall
except Exception:
    _explain_recall = None
from user_alerts import generate_alerts_for_new_recalls


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
        "distribution_pattern":(record.get("distribution_pattern") or "")[:500],
        "source":              "FDA",
    }


# ── DB upsert ──────────────────────────────────────────────────────────────────

def upsert_recall(record: dict) -> bool:
    """
    Insert a recall record, or update it if (product_name, recall_date) already exists.
    Returns True if a new row was inserted, False if it was an update/no-op.

    Requires the unique constraint:
      ALTER TABLE recalls
        ADD CONSTRAINT recalls_product_date_unique UNIQUE (product_name, recall_date);
    """
    try:
        result = execute_query(
            """
            INSERT INTO recalls
              (upc, product_name, brand_name, recall_date, reason,
               severity, distribution_pattern, source)
            VALUES
              (%(upc)s, %(product_name)s, %(brand_name)s, %(recall_date)s,
               %(reason)s, %(severity)s, %(distribution_pattern)s,
               %(source)s)
            ON CONFLICT (product_name, recall_date)
            DO UPDATE SET
              upc                 = COALESCE(EXCLUDED.upc, recalls.upc),
              brand_name          = EXCLUDED.brand_name,
              reason              = EXCLUDED.reason,
              severity            = EXCLUDED.severity,
              distribution_pattern = EXCLUDED.distribution_pattern,
              source              = EXCLUDED.source
            RETURNING (xmax = 0) AS inserted;
            """,
            record,
        )
        # xmax = 0 means the row was freshly inserted (not updated)
        return bool(result and result[0].get("inserted"))
    except Exception as exc:
        log.error("upsert_recall error for product=%s: %s", record.get("product_name"), exc)
        return False


# ── LLM recall explainer ───────────────────────────────────────────────────

def _generate_recall_summary(recall_record: dict) -> None:
    """
    Generate a plain-language recall explanation and store it in the DB.

    ┌────────────────────────────────────────────────────────────────┐
    │  INTEGRATION POINT: llm_service.py → explain_recall()          │
    │                                                                │
    │  Called from: run_recall_refresh() after each new INSERT.      │
    │  Writes to:  recalls.plain_language_summary (JSONB column)     │
    │  Read by:    risk_routes.py → _load_recall_summary()           │
    │                                                                │
    │  Failure mode: logs a warning and moves on. The raw FDA        │
    │  reason text is always available as fallback.                   │
    └────────────────────────────────────────────────────────────────┘
    """
    if _explain_recall is None:
        return  # Bedrock not configured — skip silently

    try:
        import json

        explanation = _explain_recall(
            product_name=recall_record.get("product_name", ""),
            reason=recall_record.get("reason", ""),
            severity=recall_record.get("severity", ""),
            distribution=recall_record.get("distribution_pattern", ""),
        )
        if explanation:
            execute_query(
                """UPDATE recalls
                   SET plain_language_summary = %s
                   WHERE product_name = %s AND recall_date = %s;""",
                (
                    json.dumps(explanation.to_dict()),
                    recall_record["product_name"],
                    recall_record["recall_date"],
                ),
            )
            log.info("Generated recall summary for product=%s", recall_record["product_name"])
    except ImportError:
        log.debug("llm_service not available — skipping recall summary.")
    except Exception as exc:
        log.warning("Failed to generate recall summary for product=%s: %s",
                    recall_record.get("product_name"), exc)


# ── Main refresh pipeline ─────────────────────────────────────────────────────

def run_recall_refresh() -> dict:
    """
    Full recall refresh pipeline:
      1. Fetch from FDA
      2. Map to DB schema
      3. Upsert each record
      4. Generate alerts for affected users (via user_alerts.py)

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
            # ── Generate plain-language summary via LLM ───────────────
            #    Called once per NEW recall only (not updates).
            #    Result stored in recalls.plain_language_summary JSONB.
            #    If Bedrock is unavailable, the raw FDA text is still there.
            #    See llm_service.py → explain_recall() for full docs.
            _generate_recall_summary(mapped)
        else:
            skipped += 1

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts_generated = generate_alerts_for_new_recalls()

    summary = {
        "inserted":         inserted,
        "skipped":          skipped,
        "alerts_generated": alerts_generated,
        "sources":          ["FDA"],
        "errors":           errors,
        "timestamp":        datetime.now().isoformat(),
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