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
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter

from database import execute_query

# Lazy import — LLM_services requires boto3 + Bedrock IAM; gracefully optional
try:
    from LLM_services import explain_recall as _explain_recall
except Exception:
    _explain_recall = None
from user_alerts import generate_alerts_for_new_recalls
from LLM_services import llm_get_upc as _llm_get_upc
from LLM_services import llm_get_location as _llm_get_location

log = logging.getLogger(__name__)

router = APIRouter()

# ── Constants ──────────────────────────────────────────────────────────────────

FDA_ENFORCEMENT_URL = "https://api.fda.gov/food/enforcement.json"
REQUEST_TIMEOUT     = 15   # seconds
RECALL_PAGE_LIMIT   = 100  # records per FDA API page (max 1000)

# ── Field mappers ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

#extract UPC formulaically
def get_upc(text):
    #get upc indices
    start = 0
    indices = []
    while True:
        start = text.lower().find('upc', start)
        if start == -1:
            break
        indices.append(start)
        start += len('upc')

    upc_list = []
    for i in indices:
        n = 0
        c = 0
        upc = ""

        #get the upcs
        while (n < 12) & ((i + c) < len(text)):
            char = text[i+c]
            c = c + 1
            if char.isdigit():
                n = n + 1
                upc = upc + char
        if len(upc) == 12:
          upc_list.append(upc)
    return upc_list


def combined_upc(brand_product, code_information):
    brand_product_upc = get_upc(brand_product)
    code_information_upc = get_upc(code_information)

    #use formulaic UPC extraction first, LLM extraction later
    if len(brand_product_upc) != 0:
        upc = brand_product_upc
    elif len(code_information_upc) != 0:
        upc = code_information_upc
    else:
        brand_product_upc_llm_clean = _llm_get_upc(str(brand_product)).replace("'","").split(",")
        code_information_upc_llm_clean = _llm_get_upc(str(code_information)).replace("'","").split(",")
        if brand_product_upc_llm_clean[0] != '' and len(brand_product_upc_llm_clean[0]) < 13:
            upc = brand_product_upc_llm_clean
        elif code_information_upc_llm_clean[0] != '' and len(code_information_upc_llm_clean[0]) < 13:
            upc = code_information_upc_llm_clean
        else:
            upc = []
    upc = list(set(upc)) #remove duplicates
    return upc


# ── FDA fetch ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

# def fetch_fda_recalls(limit: int = RECALL_PAGE_LIMIT, skip: int = 0) -> list[dict]:
#     """
#     Fetch food recall enforcement records from the openFDA API.

#     Reference: https://open.fda.gov/apis/food/enforcement/
#     Returns raw list of FDA enforcement records (dicts).

#     To paginate all results, call repeatedly with increasing `skip`:
#         page 1: skip=0,   limit=100
#         page 2: skip=100, limit=100
#         ...until results is shorter than limit.
#     """
#     try:
#         resp = req.get(
#             FDA_ENFORCEMENT_URL,
#             params={
#                 "limit": limit,
#                 "skip":  skip,
#                 # Optional: filter to voluntary recalls only
#                 # "search": "voluntary_mandated:Voluntary",
#             },
#             headers={"User-Agent": "FoodRecallAlert/0.2"},
#             timeout=REQUEST_TIMEOUT,
#         )
#         resp.raise_for_status()
#         data = resp.json()
#         return data.get("results", [])
#     except Exception as exc:
#         log.error("FDA API fetch error (skip=%d): %s", skip, exc)
#         return []

def fetch_new_recall_initiation():
    from datetime import date, timedelta
    dt1 = (date.today() - timedelta(days = 50)).strftime("%Y%m%d")
    dt2 = (date.today()).strftime("%Y%m%d")
    fda_initiated_url = f"https://api.fda.gov/food/enforcement.json?search=recall_initiation_date:[{dt1}+TO+{dt2}]+AND+status:'Ongoing'&limit=1000"
    fda_initiated = req.get(fda_initiated_url).json()

    initiated_items = []
    
    #convert API output into dataframe
    if fda_initiated == {'error': {'code': 'NOT_FOUND', 'message': 'No matches found!'}}:
        item_dict = ''
        initiated_items.append('')
    else:
        for i in np.arange(0, len(fda_initiated['results'])):
            date = datetime.strptime(fda_initiated['results'][i]['recall_initiation_date'], '%Y%m%d').date()
            brand_product = fda_initiated['results'][i]['recalling_firm'][:100] + ' ' + fda_initiated['results'][i]['product_description'][:400]
            code_information = fda_initiated['results'][i]['code_info'][:500]
            
            distribution_pattern = fda_initiated['results'][i]['distribution_pattern']
            distribution_pattern_str = _llm_get_location(distribution_pattern).replace("'","").strip()


            upc_list = combined_upc(brand_product, code_information)
            seen = set()
            for upc_individual in upc_list:
                key = (upc_individual, fda_initiated['results'][i]['product_description'][:255])
                if key in seen:
                    continue
                seen.add(key)
                item_dict = {"upc":upc_individual,
                             "product_name":fda_initiated['results'][i]['product_description'][:255],
                             "brand_name":fda_initiated['results'][i]['recalling_firm'],
                             "recall_date":date,
                             "reason":fda_initiated['results'][i]['reason_for_recall'],
                             "severity":fda_initiated['results'][i]['classification'],
                             "distribution_pattern":distribution_pattern_str,
                             "source":"fda"}
                initiated_items.append(item_dict)
    return initiated_items

def fetch_new_recall_termination():
    from datetime import date, timedelta
    dt1 = (date.today() - timedelta(days = 14)).strftime("%Y%m%d")
    dt2 = (date.today()).strftime("%Y%m%d")
    fda_terminated_url = f"https://api.fda.gov/food/enforcement.json?search=termination_date:[{dt1}+TO+{dt2}]+AND+status:'Terminated'&limit=1000"
    fda_terminated = req.get(fda_terminated_url).json()

    terminated_items = []
    
    if fda_terminated == {'error': {'code': 'NOT_FOUND', 'message': 'No matches found!'}}:
        item_dict = ''
        terminated_items.append('')
    else:
        for i in np.arange(0, len(fda_terminated['results'])):
            item_dict = {"product_name":fda_terminated['results'][i]['product_description'][:500],
                         "brand_name":fda_terminated['results'][i]['recalling_firm']}
            terminated_items.append(item_dict)
    return terminated_items

# ── Field mappers ─────────────────────────────────────────────────────────────────────────────────────

# def _extract_upc_from_code_info(code_info: str) -> Optional[str]:
#     """
#     Try to pull a 12- or 13-digit UPC/EAN from FDA's free-text code_info field.
#     Returns the first match, or None if none found.
#     """
#     if not code_info:
#         return None
#     match = re.search(r"\b(\d{12,13})\b", code_info)
#     return match.group(1) if match else None

# def map_fda_to_db(record: dict) -> Optional[dict]:
#     """
#     Map a raw FDA enforcement record to our recalls table schema.

#     FDA fields used:
#       product_description  → product_name
#       recalling_firm        → firm_name
#       recall_initiation_date → recall_date   (format: YYYYMMDD → YYYY-MM-DD)
#       reason_for_recall     → reason
#       classification        → severity       (Class I / II / III)
#       distribution_pattern  → distribution_pattern
#       code_info             → UPC extraction attempt
#       status                → filter: skip "Terminated" recalls

#     Returns None if the record is missing critical fields.
#     """
#     # Skip terminated / archived recalls
#     if (record.get("status") or "").lower() in ("terminated", "completed", "closed"):
#         return None

#     product_name = (record.get("product_description") or "").strip()
#     if not product_name:
#         return None

#     # Parse YYYYMMDD → YYYY-MM-DD
#     raw_date = record.get("recall_initiation_date") or ""
#     try:
#         recall_date = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
#     except ValueError:
#         recall_date = raw_date or datetime.now().strftime("%Y-%m-%d")

#     upc = _extract_upc_from_code_info(record.get("code_info") or "")

#     # If no UPC found, use the recall number as a synthetic key
#     # so the upsert still has something unique to ON CONFLICT on.
#     if not upc:
#         recall_number = (record.get("recall_number") or "").strip()
#         upc = f"FDA-{recall_number}" if recall_number else None

#     if not upc:
#         return None

#     return {
#         "upc":                 upc,
#         "product_name":        product_name[:500],   # match column width
#         "brand_name":          (record.get("recalling_firm") or "")[:200],
#         "recall_date":         recall_date,
#         "reason":              (record.get("reason_for_recall") or "")[:1000],
#         "severity":            (record.get("classification") or "")[:50],
#         "firm_name":           (record.get("recalling_firm") or "")[:200],
#         "distribution_pattern":(record.get("distribution_pattern") or "")[:500],
#         "source":              "FDA",
#     }


# ── DB upsert ──────────────────────────────────────────────────────────────────────────────────────────────

def add_item_recall(record: dict) -> bool:
    try:
        result = execute_query(
            """
            INSERT INTO recalls
              (upc, product_name, brand_name, recall_date, reason,
               severity, distribution_pattern, source)
            VALUES
              (%(upc)s, %(product_name)s, %(brand_name)s, %(recall_date)s,
               %(reason)s, %(severity)s, %(distribution_pattern)s, %(source)s)
            ON CONFLICT (upc, recall_date)
            DO UPDATE SET
                reason              = EXCLUDED.reason,
                severity            = EXCLUDED.severity,
                distribution_pattern = EXCLUDED.distribution_pattern,
                source              = EXCLUDED.source
            RETURNING (xmax = 0) AS inserted;
            """,
            record
        )
        # xmax = 0 means the row was freshly inserted (not updated)
        return bool(result and result[0].get("inserted"))
    except Exception as exc:
        log.error("upsert_recall error for product_name=%s: %s", record.get("product_name"), exc)
        return False




def remove_item_recall(record: dict) -> bool:
    try:
        result = execute_query(
            """
            DELETE FROM recalls
            WHERE product_name = %(product_name)s AND brand_name = %(brand_name)s
            """,
            record
        )
        # xmax = 0 means the row was freshly inserted (not updated)
        return True
    except Exception as exc:
        log.error("remove_item_recall error for product_name=%s: %s", record.get("product_name"), exc)
        return False
    
# def upsert_recall(record: dict) -> bool:
#     """
#     Insert a recall record, or update it if (upc, recall_date) already exists.
#     Returns True if a new row was inserted, False if it was an update/no-op.

#     Requires the unique constraint:
#       ALTER TABLE recalls
#         ADD CONSTRAINT recalls_upc_date_unique UNIQUE (upc, recall_date);
#     """
#     try:
#         result = execute_query(
#             """
#             INSERT INTO recalls
#               (upc, product_name, brand_name, recall_date, reason,
#                severity, firm_name, distribution_pattern, source)
#             VALUES
#               (%(upc)s, %(product_name)s, %(brand_name)s, %(recall_date)s,
#                %(reason)s, %(severity)s, %(firm_name)s, %(distribution_pattern)s,
#                %(source)s)
#             ON CONFLICT (upc, recall_date)
#             DO UPDATE SET
#               product_name        = EXCLUDED.product_name,
#               brand_name          = EXCLUDED.brand_name,
#               reason              = EXCLUDED.reason,
#               severity            = EXCLUDED.severity,
#               firm_name           = EXCLUDED.firm_name,
#               distribution_pattern = EXCLUDED.distribution_pattern,
#               source              = EXCLUDED.source
#             RETURNING (xmax = 0) AS inserted;
#             """,
#             record,
#         )
#         # xmax = 0 means the row was freshly inserted (not updated)
#         return bool(result and result[0].get("inserted"))
#     except Exception as exc:
#         log.error("upsert_recall error for upc=%s: %s", record.get("upc"), exc)
#         return False


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
            brand_name=recall_record.get("brand_name", ""),
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
    removed = 0
    removed_skipped = 0
    errors   = []

    # ── FDA ───────────────────────────────────────────────────────────────────
    initiated_items = fetch_new_recall_initiation()
    log.info("FDA: fetched %d raw records.", len(initiated_items))
    for fda_item in initiated_items:
        was_inserted = add_item_recall(fda_item)
        if was_inserted:
            inserted += 1
            _generate_recall_summary(fda_item)
        else:
            skipped += 1

    terminated_items = fetch_new_recall_termination()
    for fda_item in terminated_items:
        was_removed = remove_item_recall(fda_item)
        if was_removed:
            removed += 1
        else:
            removed_skipped += 1
    
    # fda_raw = fetch_fda_recalls()
    # log.info("FDA: fetched %d raw records.", len(fda_raw))

    # for raw in fda_raw:
    #     mapped = map_fda_to_db(raw)
    #     if not mapped:
    #         skipped += 1
    #         continue
    #     was_inserted = upsert_recall(mapped)
    #     if was_inserted:
    #         inserted += 1
    #         # ── Generate plain-language summary via LLM ───────────────
    #         #    Called once per NEW recall only (not updates).
    #         #    Result stored in recalls.plain_language_summary JSONB.
    #         #    If Bedrock is unavailable, the raw FDA text is still there.
    #         #    See llm_service.py → explain_recall() for full docs.
    #         _generate_recall_summary(mapped)
    #     else:
    #         skipped += 1

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts_generated = generate_alerts_for_new_recalls()

    summary = {
        "inserted":         inserted,
        "skipped":          skipped,
        "alerts_generated": alerts_generated,
        "sources":          ["fda"],
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
        hours=24,
        id="recall_refresh",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    _scheduler.start()
    log.info("Recall scheduler started – refresh every 24 hours.")

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