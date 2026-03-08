"""
user_alerts.py – Alert generation and email notifications for Recall Alert.

Two responsibilities:
  1. generate_alerts_for_new_recalls() — called by recall_update.py after each
     recall refresh. Finds users whose cart items match recalled products and
     writes rows to the alerts table.

     Two matching strategies:
       a) Exact UPC match — for barcode-scanned cart items (product_upc IS NOT NULL)
       b) Fuzzy name match — for receipt-scanned cart items (product_upc IS NULL,
          source='receipt'), using TFIDFHybridRecallMatcher from fuzzy_recall_matcher

  2. send_alert_email() — stub for emailing users when a new alert is created.
     TODO: implement with AWS SES or SendGrid.

API endpoints (Bryce's area):
  GET   /api/alerts/{user_id}        – return all alerts for a user (with recall details)
  PATCH /api/alerts/{alert_id}/viewed – mark an alert as viewed
"""

import logging

from fastapi import APIRouter, HTTPException

from database import execute_query

log = logging.getLogger(__name__)

router = APIRouter()


# ── Alert generation ───────────────────────────────────────────────────────────

def _insert_alert(user_id: int, recall_id: int, product_upc: str, product_name: str) -> bool:
    """Insert a single alert row. Returns True if a new row was created."""
    try:
        result = execute_query(
            """
            INSERT INTO alerts (user_id, recall_id, product_upc, product_name, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
            RETURNING id;
            """,
            (user_id, recall_id, product_upc, product_name),
        )
        return bool(result)
    except Exception as exc:
        log.warning(
            "Could not insert alert user=%s recall=%s: %s",
            user_id, recall_id, exc,
        )
        return False


def _generate_upc_alerts() -> int:
    """
    Strategy A: exact UPC match.
    Joins barcode-scanned cart items (product_upc IS NOT NULL) against recalls.upc.
    Skips pairs that already have an alert row.
    """
    try:
        new_pairs = execute_query(
            """
            SELECT DISTINCT
                uc.user_id,
                r.id            AS recall_id,
                uc.product_upc,
                uc.product_name
            FROM user_carts uc
            JOIN recalls r
                ON uc.product_upc = r.upc
            LEFT JOIN alerts a
                ON a.user_id = uc.user_id AND a.recall_id = r.id
            WHERE uc.product_upc IS NOT NULL
              AND a.id IS NULL;
            """
        )
    except Exception as exc:
        log.error("_generate_upc_alerts query error: %s", exc)
        return 0

    count = 0
    for pair in new_pairs:
        if _insert_alert(
            pair["user_id"], pair["recall_id"],
            pair["product_upc"], pair.get("product_name") or "",
        ):
            count += 1
            # TODO: send_alert_email(pair["user_id"], pair.get("product_name"))
    return count


def _generate_fuzzy_alerts() -> int:
    """
    Strategy B: fuzzy name match for receipt-sourced cart items.

    Loads all receipt items (product_upc IS NULL) and all recall candidates,
    then uses TFIDFHybridRecallMatcher to find matches above the 0.60 threshold.
    Skips pairs that already have an alert row.

    This mirrors the matching logic in receipt_scan.py but runs on a schedule
    so that items added to carts BEFORE a recall was published are still caught.
    """
    from fuzzy_recall_matcher import RecallCandidate, get_matcher

    # Load all receipt cart items that don't yet have ANY alert
    try:
        receipt_items = execute_query(
            """
            SELECT DISTINCT
                uc.user_id,
                uc.product_name
            FROM user_carts uc
            WHERE uc.product_upc IS NULL
              AND uc.source = 'receipt';
            """
        )
    except Exception as exc:
        log.error("_generate_fuzzy_alerts: error loading receipt cart items: %s", exc)
        return 0

    if not receipt_items:
        return 0

    # Load all recall candidates
    try:
        rows = execute_query(
            """
            SELECT id, upc, product_name, brand_name,
                   recall_date, reason, severity, firm_name, source
            FROM recalls
            ORDER BY recall_date DESC;
            """
        )
    except Exception as exc:
        log.error("_generate_fuzzy_alerts: error loading recalls: %s", exc)
        return 0

    if not rows:
        return 0

    candidates = [
        RecallCandidate(
            id=int(r["id"]),
            upc=str(r.get("upc") or ""),
            product_name=r.get("product_name") or "",
            brand_name=r.get("brand_name") or "",
            recall_date=str(r.get("recall_date") or ""),
            reason=r.get("reason") or "",
            severity=r.get("severity") or "",
            firm_name=r.get("firm_name") or "",
            source=r.get("source") or "FDA",
        )
        for r in rows
    ]

    try:
        matcher = get_matcher("tfidf_hybrid", candidates)
    except Exception as exc:
        log.error("_generate_fuzzy_alerts: could not build matcher: %s", exc)
        return 0

    count = 0
    for item in receipt_items:
        match = matcher.best_match(item["product_name"], threshold=0.60)
        if match is None:
            continue

        # Skip if this user already has an alert for this recall
        try:
            existing = execute_query(
                "SELECT id FROM alerts WHERE user_id = %s AND recall_id = %s;",
                (item["user_id"], match.candidate.id),
            )
            if existing:
                continue
        except Exception:
            continue

        if _insert_alert(
            item["user_id"],
            match.candidate.id,
            match.candidate.upc,
            item["product_name"],
        ):
            count += 1
            log.info(
                "Fuzzy recall alert: user=%s product='%s' → recall_id=%s score=%.2f",
                item["user_id"], item["product_name"],
                match.candidate.id, match.score,
            )

    return count


def generate_alerts_for_new_recalls() -> int:
    """
    After importing new recalls, find users whose saved grocery items
    match a recalled product and create alert rows for them.

    Runs two strategies:
      A) Exact UPC match  — barcode cart items (fast, SQL join)
      B) Fuzzy name match — receipt cart items (in-memory, TF-IDF + RapidFuzz)

    Called by recall_update.run_recall_refresh() after each refresh.
    Returns the total number of new alert rows created.
    """
    upc_count   = _generate_upc_alerts()
    fuzzy_count = _generate_fuzzy_alerts()
    total = upc_count + fuzzy_count

    if total:
        log.info(
            "Generated %d new alerts (%d UPC-match, %d fuzzy-match).",
            total, upc_count, fuzzy_count,
        )
    return total


# ── Email notification stub ────────────────────────────────────────────────────

def send_alert_email(user_id: int, product_name: str) -> None:
    """
    TODO: Send an email to the user notifying them of a new recall alert.

    Options:
      - AWS SES:    boto3.client("ses").send_email(...)
      - SendGrid:   sendgrid.SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))

    Steps to implement:
      1. Look up the user's email from the users table
      2. Build a message with the product name and recall details
      3. Send via SES or SendGrid
      4. Mark alerts.email_sent = TRUE on success

    Example SES skeleton:
        import boto3, os
        ses = boto3.client("ses", region_name="us-east-1")
        ses.send_email(
            Source=os.getenv("ALERT_FROM_EMAIL"),
            Destination={"ToAddresses": [user_email]},
            Message={
                "Subject": {"Data": f"Recall Alert: {product_name}"},
                "Body":    {"Text": {"Data": "One of your saved items has been recalled."}},
            },
        )
    """
    # TODO: implement email delivery
    log.info("send_alert_email called for user_id=%s product=%s (not yet implemented)", user_id, product_name)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_user_id(user_id: str):
    """Parse user_id string → int. Returns None for guest ids like 'test_user'."""
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


# ── API Endpoints ──────────────────────────────────────────────────────────────

@router.get("/api/alerts/{user_id}")
async def get_user_alerts(user_id: str):
    """
    Return all alerts for a user, joined with recall details.
    Unviewed alerts come first, then sorted by created_at descending.
    """
    uid = _parse_user_id(user_id)
    if uid is None:
        return {"user_id": user_id, "alerts": [], "count": 0}

    rows = execute_query(
        """
        SELECT
            a.id            AS alert_id,
            a.product_upc,
            a.product_name,
            a.created_at,
            a.viewed,
            a.email_sent,
            r.id            AS recall_id,
            r.product_name  AS recall_product_name,
            r.brand_name,
            r.recall_date,
            r.reason,
            r.severity,
            r.firm_name,
            r.distribution_pattern,
            r.source
        FROM alerts a
        JOIN recalls r ON a.recall_id = r.id
        WHERE a.user_id = %s
        ORDER BY a.viewed ASC, a.created_at DESC;
        """,
        (uid,),
    )

    alerts = [
        {
            "alert_id":     r["alert_id"],
            "product_upc":  r["product_upc"],
            "product_name": r["product_name"] or r["recall_product_name"],
            "viewed":       r["viewed"],
            "created_at":   str(r["created_at"]),
            "recall": {
                "recall_id":    r["recall_id"],
                "product_name": r["recall_product_name"],
                "brand_name":   r["brand_name"] or "",
                "recall_date":  str(r["recall_date"]),
                "reason":       r["reason"],
                "severity":     r["severity"] or "",
                "firm_name":    r["firm_name"] or "",
                "distribution": r["distribution_pattern"] or "",
                "source":       r["source"] or "",
            },
        }
        for r in rows
    ]

    return {
        "user_id":       user_id,
        "alerts":        alerts,
        "count":         len(alerts),
        "unviewed_count": sum(1 for a in alerts if not a["viewed"]),
    }


@router.patch("/api/alerts/{alert_id}/viewed")
async def mark_alert_viewed(alert_id: int):
    """Mark a single alert as viewed."""
    result = execute_query(
        """
        UPDATE alerts
        SET viewed = TRUE
        WHERE id = %s
        RETURNING id, viewed;
        """,
        (alert_id,),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"alert_id": result[0]["id"], "viewed": result[0]["viewed"]}
