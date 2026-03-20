"""
receipt_scan.py – FastAPI APIRouter for receipt scanning.

Production workflow:
  1. Receive image upload and normalize to JPEG/PNG for Textract
  2. Run AWS Textract AnalyzeExpense to extract structured item names
     Fallback to DetectDocumentText if AnalyzeExpense returns no line items
  3. Clean OCR text into search-friendly receipt item names
  4. Save ALL cleaned items to the user's cart (source='receipt', no UPC)
  5. Load recall candidates from the PostgreSQL `recalls` table
  6. Match each cleaned receipt item against recall candidates
     using the matcher in fuzzy_recall_matcher.py
  7. Return:
       - matched_recalls  = items with a strong recall match (is_recalled=true)
       - safe_items       = items added to cart with no current recall
       - cart_items_added = count of rows inserted/already-present in user_carts
       - total_lines      = raw OCR line count
"""

from __future__ import annotations

import asyncio
import io
import re
from typing import Optional

import boto3
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC/HEIF support so iPhone photos work out of the box
register_heif_opener()

from database import execute_query
from fuzzy_recall_matcher import RecallCandidate, get_matcher

router = APIRouter()

NON_ITEM_KEYWORDS = {
    "subtotal", "total", "tax", "cash", "visa", "mastercard", "change",
    "payment", "approved", "debit", "credit", "balance", "receipt",
    "thank", "cashier", "bag", "carrier", "discount", "savings",
    "rounding", "tender", "auth", "store", "phone"
}


# ── Textract helpers ───────────────────────────────────────────────────────────

def _parse_textract_expense(response: dict) -> list[str]:
    """Extract product line-item names from Textract AnalyzeExpense response."""
    items: list[str] = []
    for doc in response.get("ExpenseDocuments", []):
        for group in doc.get("LineItemGroups", []):
            for line in group.get("LineItems", []):
                for field in line.get("LineItemExpenseFields", []):
                    if field.get("Type", {}).get("Text") == "ITEM":
                        text = (field.get("ValueDetection") or {}).get("Text", "").strip()
                        if text:
                            items.append(text)
    return items


def _parse_textract_text_fallback(response: dict) -> list[str]:
    """Fallback: extract all text lines from DetectDocumentText response."""
    return [
        b["Text"]
        for b in response.get("Blocks", [])
        if b.get("BlockType") == "LINE" and b.get("Text", "").strip()
    ]


# ── Cleaning / filtering helpers ──────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def _is_non_item_line(text: str) -> bool:
    tokens = set(_tokenize(text))
    if not tokens:
        return True
    return bool(tokens & NON_ITEM_KEYWORDS)


def clean_receipt_item(raw: str) -> str:
    """
    Clean a raw receipt line item into recall-matching-friendly text.
    """
    text = raw.strip()

    # Remove prices: $3.99 or 3.99
    text = re.sub(r"\$?\d+\.\d{2}", "", text)

    # Remove leading quantity prefix: "2 @ ", "3x ", "1 X "
    text = re.sub(r"^\d+\s*[xX@]\s*", "", text)
    text = re.sub(r"^\d+\s+", "", text)

    # Remove trailing size/weight/count units like "125ML", "16 OZ", "2 KG"
    text = re.sub(
        r"\s+\d+(\.\d+)?\s*(LB|OZ|EA|CT|PK|LT|ML|G|KG)?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove short slash codes like F/L
    text = re.sub(r"\b[A-Z]/[A-Z]\b", " ", text)

    # Drop only code-like tokens that contain digits
    words = [
        w for w in text.split()
        if not re.match(r"^(?=.*\d)[A-Z0-9]{2,8}$", w)
    ]

    cleaned = " ".join(words).strip()

    # Remove a few retail descriptors that usually hurt matching
    cleaned = re.sub(r"\b(LOOSE|TUB|BAG)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


# ── Cart helpers ───────────────────────────────────────────────────────────────

def _parse_user_id(user_id: Optional[str]) -> Optional[int]:
    """Return integer user_id or None for guests / invalid strings."""
    if not user_id:
        return None
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


def _save_receipt_items_to_cart(uid: int, items: list[dict]) -> int:
    """
    Upsert all receipt items into user_carts with source='receipt'.

    Each item dict must have 'cleaned' (the display name).
    Uses the partial unique index (user_id, product_name) WHERE product_upc IS NULL
    for conflict detection, so duplicate receipt items are silently skipped.

    Returns the number of rows actually inserted.
    """
    inserted = 0
    for item in items:
        name = item["cleaned"][:255]  # match column width
        try:
            result = execute_query(
                """
                INSERT INTO user_carts
                    (user_id, product_upc, product_name, brand_name, source)
                VALUES
                    (%s, NULL, %s, '', 'receipt')
                ON CONFLICT (user_id, product_name) WHERE product_upc IS NULL
                DO NOTHING
                RETURNING id;
                """,
                (uid, name),
            )
            if result:
                inserted += 1
        except Exception as e:
            log.warning("Failed to save receipt item '%s' for user %s: %s", name, uid, e)
    return inserted


# ── Recall candidate loading ──────────────────────────────────────────────────

def _load_recall_candidates() -> list[RecallCandidate]:
    """
    Load recall candidates from the PostgreSQL recalls table.
    """
    rows = execute_query(
        """
        SELECT
            id,
            upc,
            product_name,
            brand_name,
            recall_date,
            reason,
            severity,

            source
        FROM recalls
        ORDER BY recall_date DESC;
        """
    )

    candidates: list[RecallCandidate] = []
    for r in rows:
        candidates.append(
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
        )
    return candidates


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/api/receipt/scan")
async def scan_receipt(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
):
    """
    Process a receipt photo, save ALL items to the user's cart, and
    return which items match active recalls.

    Multipart form fields:
      file    — the receipt image (JPEG, PNG, HEIC, etc.)
      user_id — (optional) the signed-in user's integer ID.
                If omitted or not a valid integer (e.g. 'test_user'),
                the cart-save step is skipped.

    Response format:
    {
      "matched_recalls": [
        {
          "raw_text": ...,
          "cleaned_text": ...,
          "upc": ...,
          "product_name": ...,
          "brand_name": ...,
          "is_recalled": true,
          "recall_info": { "id", "reason", "recall_date", "severity",
                           "source" },
          "match_score": 0.83,
          "matcher": "tfidf_hybrid"
        },
        ...
      ],
      "safe_items": [
        { "raw_text": ..., "cleaned_text": ..., "is_recalled": false },
        ...
      ],
      "cart_items_added": N,
      "total_lines": N
    }
    """
    uid = _parse_user_id(user_id)

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # Step 1: Normalize image
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.format not in ("JPEG", "PNG"):
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=90)
            image_bytes = buf.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read image: {exc}")

    # Step 2: Textract OCR
    try:
        textract = boto3.client("textract", region_name="us-east-1")
        expense_response = textract.analyze_expense(Document={"Bytes": image_bytes})
        raw_items = _parse_textract_expense(expense_response)

        if not raw_items:
            text_response = textract.detect_document_text(Document={"Bytes": image_bytes})
            raw_items = _parse_textract_text_fallback(text_response)

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Textract error: {exc}. "
                "Check AWS credentials or IAM permissions for textract:AnalyzeExpense."
            ),
        )

    # Step 3: Clean/filter OCR lines
    cleaned_items: list[dict] = []
    for raw in raw_items[:25]:
        cleaned = clean_receipt_item(raw)
        if not cleaned or len(cleaned) < 3:
            continue
        if _is_non_item_line(cleaned):
            continue
        cleaned_items.append({"raw": raw, "cleaned": cleaned})

    if not cleaned_items:
        return {
            "matched_recalls": [],
            "safe_items": [],
            "cart_items_added": 0,
            "total_lines": len(raw_items),
        }

    # Step 4: Save ALL items to the user's cart (skip for guests)
    cart_items_added = 0
    if uid is not None:
        try:
            cart_items_added = _save_receipt_items_to_cart(uid, cleaned_items)
        except Exception as e:
            log.warning("Cart save failed for user %s: %s", uid, e)

    # Step 5: Load recall candidates and initialize matcher
    try:
        recall_candidates = _load_recall_candidates()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not load recall candidates: {exc}",
        )

    matcher_name = "tfidf_hybrid"
    matcher_threshold = 0.60

    try:
        matcher = get_matcher(matcher_name, recall_candidates)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid recall matcher configuration: {exc}",
        )

    # Step 6: Run recall matching concurrently
    semaphore = asyncio.Semaphore(6)

    async def lookup(entry: dict):
        async with semaphore:
            match = await asyncio.to_thread(
                matcher.best_match,
                entry["cleaned"],
                matcher_threshold,
            )
            return entry, match

    results = await asyncio.gather(
        *[lookup(e) for e in cleaned_items],
        return_exceptions=True,
    )

    matched_recalls: list[dict] = []
    safe_items: list[dict] = []

    for result in results:
        if isinstance(result, Exception):
            continue

        entry, match = result

        if match is None:
            safe_items.append({
                "raw_text":    entry["raw"],
                "cleaned_text": entry["cleaned"],
                "is_recalled": False,
            })
            continue

        c = match.candidate
        matched_recalls.append(
            {
                "raw_text":     entry["raw"],
                "cleaned_text": entry["cleaned"],
                "upc":          c.upc,
                "product_name": c.product_name,
                "brand_name":   c.brand_name,
                "is_recalled":  True,
                "recall_info": {
                    "id":          c.id,
                    "reason":      c.reason,
                    "recall_date": c.recall_date,
                    "severity":    c.severity,
                    "source":      c.source,
                },
                "match_score": round(match.score, 4),
                "matcher":     match.algorithm,
            }
        )

    return {
        "matched_recalls":  matched_recalls,
        "safe_items":       safe_items,
        "cart_items_added": cart_items_added,
        "total_lines":      len(raw_items),
    }
