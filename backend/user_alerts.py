
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
 
     Both strategies filter by distribution_pattern so users only receive
     alerts relevant to their state. A recall is considered relevant when:
       - distribution_pattern contains 'USA' (nationwide)
       - distribution_pattern contains the user's two-letter state code
       - distribution_pattern is NULL or empty (unknown → show to everyone)
 
  2. send_alert_email() — stub for emailing users when a new alert is created.
 
API endpoints:
  GET   /api/alerts/{user_id}        – return all alerts for a user (with recall details)
  PATCH /api/alerts/{alert_id}/viewed – mark an alert as viewed
"""
 
import logging
import os
import re

from fastapi import APIRouter, HTTPException

from database import execute_query

# Lazy SES import — requires boto3 + IAM ses:SendEmail permission
try:
    import boto3
    from botocore.exceptions import ClientError as _BotoClientError
    _SES_CLIENT = boto3.client("ses", region_name="us-east-1")
    _SES_AVAILABLE = True
except Exception:
    _SES_CLIENT = None
    _SES_AVAILABLE = False

SES_SENDER = os.environ.get("SES_SENDER", "capstone.recallalert@gmail.com")
 
log = logging.getLogger(__name__)
 
router = APIRouter()
 
 
# ── Distribution pattern helpers ──────────────────────────────────────────────
 
def _state_matches_distribution(state: str | None, distribution_pattern: str | None) -> bool:
    """
    Return True if a recall's distribution_pattern is relevant to the user's state.
 
    distribution_pattern is the raw string returned by llm_get_location(), e.g.:
      '[CA, WA, OR]'   → specific states
      '[USA]'          → nationwide
      ''  or  None     → unknown; show to everyone (conservative)
 
    A recall is relevant when:
      - pattern is empty / None  (unknown coverage)
      - pattern contains 'USA'   (nationwide)
      - pattern contains the user's exact two-letter state code
      - user has no state set    (show everything)
    """
    if not state:
        return True  # no state preference → see all alerts
 
    if not distribution_pattern or not distribution_pattern.strip():
        return True  # unknown distribution → conservative, show to everyone
 
    dp = distribution_pattern.upper()
 
    if "USA" in dp:
        return True
 
    # Match whole state tokens only (avoid 'CA' matching 'SCAN', etc.)
    # LLM output format: '[CA, WA, OR]'  or  'CA, WA'
    tokens = re.findall(r'\b([A-Z]{2})\b', dp)
    return state.upper() in tokens
 
 
def _build_distribution_sql_filter(state_column: str) -> str:
    """
    Return a SQL snippet (to be AND-ed into a WHERE clause) that mirrors
    _state_matches_distribution() but runs entirely in Postgres.
 
    state_column  – the fully-qualified column reference for the user's state,
                    e.g. 'u.state' or 'user_state'.
    """
    return f"""(
        r.distribution_pattern IS NULL
        OR r.distribution_pattern = ''
        OR r.distribution_pattern ILIKE '%USA%'
        OR {state_column} IS NULL
        OR {state_column} = ''
        OR r.distribution_pattern ILIKE '%' || {state_column} || '%'
    )"""
 
 
# ── Alert generation ───────────────────────────────────────────────────────────
 
def _insert_alert(user_id: int, recall_id: int, product_upc: str, product_name: str) -> bool:
    """Insert a single alert row, then fire the email. Returns True if a new row was created."""
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
        if result:
            send_alert_email(user_id, recall_id, product_name)
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
 
    Joins barcode-scanned cart items (product_upc IS NOT NULL) against recalls.upc,
    then filters so a user only receives an alert when the recall's distribution_pattern
    covers their state (or is nationwide / unknown).
 
    Skips pairs that already have an alert row.
    """
    distribution_filter = _build_distribution_sql_filter("u.state")
 
    try:
        new_pairs = execute_query(
            f"""
            SELECT DISTINCT
                uc.user_id,
                r.id            AS recall_id,
                uc.product_upc,
                uc.product_name
            FROM user_carts uc
            JOIN recalls r
                ON uc.product_upc = r.upc
            JOIN users u
                ON uc.user_id = u.id
            LEFT JOIN alerts a
                ON a.user_id = uc.user_id AND a.recall_id = r.id
            WHERE uc.product_upc IS NOT NULL
              AND a.id IS NULL
              AND {distribution_filter};
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
    return count
 
 
def _generate_fuzzy_alerts() -> int:
    """
    Strategy B: fuzzy name match for receipt-sourced cart items.
 
    Loads all receipt items (product_upc IS NULL) together with the user's state,
    then uses TFIDFHybridRecallMatcher to find recall matches above the 0.60 threshold.
 
    After a fuzzy match is found, _state_matches_distribution() verifies that the
    recall's distribution_pattern covers the user's state before inserting an alert.
 
    Skips pairs that already have an alert row.
    """
    from fuzzy_recall_matcher import RecallCandidate, get_matcher
 
    # Load receipt cart items + the user's state in one query
    try:
        receipt_items = execute_query(
            """
            SELECT DISTINCT
                uc.user_id,
                uc.product_name,
                u.state         AS user_state
            FROM user_carts uc
            JOIN users u ON uc.user_id = u.id
            WHERE uc.product_upc IS NULL
              AND uc.source = 'receipt';
            """
        )
    except Exception as exc:
        log.error("_generate_fuzzy_alerts: error loading receipt cart items: %s", exc)
        return 0
 
    if not receipt_items:
        return 0
 
    # Load all recall candidates (including distribution_pattern for state filtering)
    try:
        rows = execute_query(
            """
            SELECT id, upc, product_name, brand_name,
                   recall_date, reason, severity, source,
                   distribution_pattern
            FROM recalls
            ORDER BY recall_date DESC;
            """
        )
    except Exception as exc:
        log.error("_generate_fuzzy_alerts: error loading recalls: %s", exc)
        return 0
 
    if not rows:
        return 0
 
    # Build a lookup so we can retrieve distribution_pattern after a fuzzy match
    distribution_by_id: dict[int, str | None] = {
        int(r["id"]): r.get("distribution_pattern") for r in rows
    }
 
    candidates = [
        RecallCandidate(
            id=int(r["id"]),
            upc=str(r.get("upc") or ""),
            product_name=r.get("product_name") or "",
            brand_name=r.get("brand_name") or "",
            recall_date=str(r.get("recall_date") or ""),
            reason=r.get("reason") or "",
            severity=r.get("severity") or "",
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
 
        # ── State / distribution filter ──────────────────────────────────────
        user_state = item.get("user_state")
        dist_pattern = distribution_by_id.get(match.candidate.id)
        if not _state_matches_distribution(user_state, dist_pattern):
            log.debug(
                "Skipping fuzzy alert: user=%s state=%s not in distribution '%s' "
                "for recall_id=%s",
                item["user_id"], user_state, dist_pattern, match.candidate.id,
            )
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
                "Fuzzy recall alert: user=%s state=%s product='%s' → "
                "recall_id=%s score=%.2f dist='%s'",
                item["user_id"], user_state, item["product_name"],
                match.candidate.id, match.score, dist_pattern,
            )
 
    return count
 
 
def generate_alerts_for_new_recalls() -> int:
    """
    After importing new recalls, find users whose saved grocery items
    match a recalled product and create alert rows for them.
 
    Runs two strategies:
      A) Exact UPC match  — barcode cart items (fast, SQL join + distribution filter)
      B) Fuzzy name match — receipt cart items (TF-IDF + RapidFuzz + distribution filter)
 
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
 
 
# ── Email notification ─────────────────────────────────────────────────────────

def send_alert_email(user_id: int, recall_id: int, product_name: str) -> None:
    """
    Send a recall alert email to the user via AWS SES.
    Marks email_sent=TRUE on the alert row after a successful send.
    Silently skips if SES is unavailable or the user has no email address.
    """
    if not _SES_AVAILABLE:
        log.debug("SES not available — skipping email for user=%s", user_id)
        return

    # Fetch user email + recall details in one shot
    try:
        user_rows = execute_query(
            "SELECT name, email FROM users WHERE id = %s;", (user_id,)
        )
        recall_rows = execute_query(
            "SELECT product_name, brand_name, recall_date, reason, severity FROM recalls WHERE id = %s;",
            (recall_id,),
        )
    except Exception as exc:
        log.warning("send_alert_email: DB lookup failed user=%s: %s", user_id, exc)
        return

    if not user_rows or not user_rows[0].get("email"):
        log.debug("send_alert_email: no email for user=%s — skipping", user_id)
        return

    user = user_rows[0]
    recall = recall_rows[0] if recall_rows else {}

    recall_product = recall.get("product_name") or product_name
    brand          = recall.get("brand_name") or ""
    recall_date    = str(recall.get("recall_date") or "")
    reason         = recall.get("reason") or "See FDA website for details."
    severity       = recall.get("severity") or ""

    subject = f"Recall Alert: A product you bought may be affected"

    body_html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background:#b91c1c; padding:20px; border-radius:8px 8px 0 0;">
        <h1 style="color:white; margin:0; font-size:20px;">⚠️ Recall Alert</h1>
      </div>
      <div style="border:1px solid #e5e7eb; border-top:none; padding:24px; border-radius:0 0 8px 8px;">
        <p>Hi {user.get('name') or 'there'},</p>
        <p>A product you recently scanned may be affected by an FDA recall.</p>

        <div style="background:#fef2f2; border-left:4px solid #b91c1c; padding:16px; margin:16px 0; border-radius:4px;">
          <p style="margin:0 0 8px 0;"><strong>Your item:</strong> {product_name}</p>
          <p style="margin:0 0 8px 0;"><strong>Recalled product:</strong> {recall_product}{(' — ' + brand) if brand else ''}</p>
          {'<p style="margin:0 0 8px 0;"><strong>Recall date:</strong> ' + recall_date + '</p>' if recall_date else ''}
          {'<p style="margin:0 0 8px 0;"><strong>Severity:</strong> ' + severity + '</p>' if severity else ''}
          <p style="margin:0;"><strong>Reason:</strong> {reason}</p>
        </div>

        <p>If this product matches what you bought, stop using it and check the
        <a href="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts">FDA recall page</a>
        for return/disposal instructions.</p>

        <p>If this doesn't match your product, you can dismiss this alert in the app.</p>

        <a href="http://54.210.208.14"
           style="display:inline-block; background:#111827; color:white; padding:12px 24px;
                  border-radius:6px; text-decoration:none; margin-top:8px;">
          View in Recall Alert App
        </a>

        <p style="margin-top:24px; color:#6b7280; font-size:12px;">
          You received this because you have a Recall Alert account.
          This alert was generated automatically — if it's a false match, dismiss it in the app.
        </p>
      </div>
    </body></html>
    """

    body_text = (
        f"Recall Alert for {user.get('name') or 'you'}\n\n"
        f"Your item: {product_name}\n"
        f"Recalled product: {recall_product}{(' — ' + brand) if brand else ''}\n"
        f"Reason: {reason}\n\n"
        f"If this matches your product, check: https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts\n"
        f"You can dismiss this alert in the app if it doesn't match."
    )

    try:
        _SES_CLIENT.send_email(
            Source=SES_SENDER,
            Destination={"ToAddresses": [user["email"]]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html,  "Charset": "UTF-8"},
                },
            },
        )
        # Mark email_sent on the alert row
        execute_query(
            "UPDATE alerts SET email_sent = TRUE WHERE user_id = %s AND recall_id = %s;",
            (user_id, recall_id),
        )
        log.info("Recall alert email sent to user=%s (%s)", user_id, user["email"])
    except Exception as exc:
        log.warning("SES send failed for user=%s: %s", user_id, exc)
 
 
# ── Helpers ───────────────────────────────────────────────────────────────────
 
def _parse_user_id(user_id: str):
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
            a.dismissed,
            r.id            AS recall_id,
            r.product_name  AS recall_product_name,
            r.brand_name,
            r.recall_date,
            r.reason,
            r.severity,
            r.distribution_pattern,
            r.source
        FROM alerts a
        JOIN recalls r ON a.recall_id = r.id
        WHERE a.user_id = %s
          AND (a.dismissed IS NULL OR a.dismissed = FALSE)
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
            "dismissed":    r.get("dismissed") or False,
            "created_at":   str(r["created_at"]),
            "recall": {
                "recall_id":    r["recall_id"],
                "product_name": r["recall_product_name"],
                "brand_name":   r["brand_name"] or "",
                "recall_date":  str(r["recall_date"]),
                "reason":       r["reason"],
                "severity":     r["severity"] or "",
                "distribution": r["distribution_pattern"] or "",
                "source":       r["source"] or "",
            },
        }
        for r in rows
    ]
 
    return {
        "user_id":        user_id,
        "alerts":         alerts,
        "count":          len(alerts),
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


@router.patch("/api/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: int):
    """
    User says 'that's not my product' — marks the alert as dismissed.
    Dismissed alerts are hidden from the main alerts view but not deleted.
    """
    result = execute_query(
        """
        UPDATE alerts
        SET dismissed = TRUE, viewed = TRUE
        WHERE id = %s
        RETURNING id, dismissed;
        """,
        (alert_id,),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"alert_id": result[0]["id"], "dismissed": result[0]["dismissed"]}


@router.post("/api/admin/test-recall")
async def inject_test_recall(product_name: str, reason: str = "Test recall for demo purposes", severity: str = "Class II"):
    """
    Admin endpoint: insert a fake recall matching a product name, then run alert generation.
    Use this to demo/test the full recall → alert → email pipeline without waiting for FDA.

    Example:
      POST /api/admin/test-recall?product_name=Organic+Spinach
    """
    from datetime import date
    result = execute_query(
        """
        INSERT INTO recalls (product_name, brand_name, recall_date, reason, severity, source)
        VALUES (%s, 'TEST', %s, %s, %s, 'TEST')
        RETURNING id;
        """,
        (product_name, date.today().isoformat(), reason, severity),
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to insert test recall.")

    recall_id = result[0]["id"]
    from user_alerts import generate_alerts_for_new_recalls
    alerts_created = generate_alerts_for_new_recalls()

    return {
        "recall_id":      recall_id,
        "product_name":   product_name,
        "alerts_created": alerts_created,
        "message":        f"Test recall inserted (id={recall_id}). {alerts_created} alert(s) generated.",
    }