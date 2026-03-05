"""
user_alerts.py – Alert generation and email notifications for Recall Alert.

Two responsibilities:
  1. generate_alerts_for_new_recalls() — called by recall_update.py after each
     recall refresh. Finds users whose cart items match recalled products and
     writes rows to the alerts table.

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

def generate_alerts_for_new_recalls() -> int:
    """
    After importing new recalls, find users whose saved grocery items
    match a recalled product and create alert rows for them.

    Matches on product_upc (exact UPC) from user_carts vs recalls.upc.
    Skips users who already have an alert for that recall.

    Called by recall_update.run_recall_refresh() after each refresh.
    Returns the number of new alert rows created.
    """
    try:
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
                # TODO: call send_alert_email() here once implemented
                # send_alert_email(pair["user_id"], pair["product_name"])
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
