"""
receipt_scan.py – FastAPI APIRouter for receipt scanning.

Pipeline:
  1. Receive image upload → normalize to JPEG (Textract requires JPEG/PNG)
  2. AWS Textract AnalyzeExpense → structured line-item names
     Fallback: DetectDocumentText if AnalyzeExpense finds nothing
  3. Regex cleaner → human-readable search terms  (LLM upgrade stub included)
  4. Product lookup: search our RDS products table first (fast, free)
     → fall back to Open Food Facts v2 API with proper User-Agent header
     NOTE: The old cgi/search.pl endpoint times out from EC2 AWS IPs.
           The v2 search endpoint + User-Agent header is reliable.
  5. Recall check: cross-reference matched UPCs against recalls table
  6. Return { matched: [...], unmatched: [...], total_lines: N }
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional
import asyncio
import io
import re

import boto3
import requests as req
from PIL import Image

from database import execute_query

router = APIRouter()

# ── Textract helpers ───────────────────────────────────────────────────────────

def _parse_textract_expense(response: dict) -> list[str]:
    """Extract product line-item names from Textract AnalyzeExpense response."""
    items = []
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


# ── Item name cleaner ──────────────────────────────────────────────────────────

def clean_receipt_item(raw: str) -> str:
    """
    Clean a raw receipt line item into a search-friendly product name.

    # TODO: Upgrade to LLM for much better accuracy when an API key is available:
    #
    #   import anthropic, os
    #   client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    #   msg = client.messages.create(
    #       model="claude-haiku-20240307",
    #       max_tokens=40,
    #       messages=[{"role": "user", "content":
    #           f"Receipt line item: '{raw}'. What food product is this? "
    #           "Reply with just the clean product name, nothing else."}]
    #   )
    #   return msg.content[0].text.strip()
    """
    text = raw.strip()
    # Remove prices: $3.99 or 3.99
    text = re.sub(r"\$?\d+\.\d{2}", "", text)
    # Remove quantity prefix: "2 @ ", "3x ", "1 X "
    text = re.sub(r"^\d+\s*[xX@]\s*", "", text)
    text = re.sub(r"^\d+\s+", "", text)
    # Remove trailing weight/count units
    text = re.sub(
        r"\s+\d+(\.\d+)?\s*(LB|OZ|EA|CT|PK|LT|ML|G|KG)?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Drop short all-caps SKU tokens (e.g. "F3A", "BOGO", "PLU", "TJ")
    words = [
        w for w in text.split()
        if not (re.match(r"^[A-Z0-9]{2,6}$", w) and len(w) <= 5)
    ]
    return " ".join(words).strip()


# ── Product lookup ─────────────────────────────────────────────────────────────

def _search_our_db(query: str) -> Optional[dict]:
    """
    Search the local `products` table with ILIKE.
    This is fast, costs nothing, and works offline.
    Returns a dict with upc/product_name/brand_name/ingredients, or None.
    """
    if not query or len(query) < 3:
        return None
    try:
        pattern = f"%{query.lower()}%"
        rows = execute_query(
            """
            SELECT upc, product_name, brand_name, ingredients
            FROM products
            WHERE LOWER(product_name) LIKE %s OR LOWER(brand_name) LIKE %s
            ORDER BY product_name
            LIMIT 1;
            """,
            (pattern, pattern),
        )
        if not rows:
            return None
        row = rows[0]
        ingredients_raw = row.get("ingredients") or ""
        ingredients = [i.strip() for i in ingredients_raw.split("|") if i.strip()][:15]
        return {
            "upc":          row["upc"],
            "product_name": row["product_name"],
            "brand_name":   row.get("brand_name") or "",
            "ingredients":  ingredients,
            "source":       "db",
        }
    except Exception:
        return None


def _search_off_sync(query: str) -> Optional[dict]:
    """
    Search Open Food Facts v2 API by product name (blocking – run in thread).

    Key fixes vs. the old cgi/search.pl endpoint:
      • Uses /api/v2/search  — not blocked on AWS IPs
      • Sends a User-Agent header — OFF rejects requests without one
      • 8-second timeout with a 2-second connect timeout
    """
    if not query or len(query) < 3:
        return None
    try:
        resp = req.get(
            "https://world.openfoodfacts.org/api/v2/search",
            params={
                "search_terms": query,
                "page_size":    "3",
                "fields":       "code,product_name,brands,ingredients_text",
            },
            headers={
                # OFF blocks requests without a User-Agent
                "User-Agent": "FoodRecallAlert/0.2 (capstone-project; contact@example.com)"
            },
            timeout=(2, 8),   # (connect timeout, read timeout)
        )
        data = resp.json()
        products = data.get("products", [])
        if not products:
            return None
        p = products[0]
        name = (p.get("product_name") or "").strip()
        if not name:
            return None
        brand = (p.get("brands") or "").split(",")[0].strip()
        ingredients_raw = p.get("ingredients_text") or ""
        ingredients = [i.strip() for i in ingredients_raw.split(",") if i.strip()][:15]
        return {
            "upc":          p.get("code", ""),
            "product_name": name,
            "brand_name":   brand,
            "ingredients":  ingredients,
            "source":       "off",
        }
    except Exception:
        return None


def _search_product_sync(query: str) -> Optional[dict]:
    """
    Try our DB first (fast), then fall back to Open Food Facts.
    Returns None only if both fail.
    """
    result = _search_our_db(query)
    if result:
        return result
    return _search_off_sync(query)


# ── Recall check ──────────────────────────────────────────────────────────────

def _check_recall(upc: str) -> Optional[dict]:
    """Return the most recent recall for a UPC, or None."""
    if not upc:
        return None
    try:
        rows = execute_query(
            "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
            (upc,),
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "id":           r["id"],
            "reason":       r.get("reason") or "",
            "recall_date":  str(r["recall_date"]),
            "severity":     r.get("severity") or "",
            "firm_name":    r.get("firm_name") or "",
        }
    except Exception:
        return None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/api/receipt/scan")
async def scan_receipt(file: UploadFile = File(...)):
    """
    Process a receipt photo and return matched products + recall status.

    Steps:
      1. Read & normalize image to JPEG (handles WebP, HEIC, etc.)
      2. Textract AnalyzeExpense → structured item names
         Fallback: DetectDocumentText if AnalyzeExpense finds nothing
      3. Clean item names with regex (LLM upgrade stub in clean_receipt_item)
      4. Parallel product lookup: local DB → OFF v2
      5. Recall check for each matched UPC
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # ── Step 1: Normalize image ────────────────────────────────────────────────
    # Textract only accepts JPEG and PNG.
    # Phones often save images as WebP even with a .jpg extension.
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.format not in ("JPEG", "PNG"):
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=90)
            image_bytes = buf.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read image: {exc}")

    # ── Step 2: Textract ──────────────────────────────────────────────────────
    try:
        textract = boto3.client("textract", region_name="us-east-1")
        expense_response = textract.analyze_expense(Document={"Bytes": image_bytes})
        raw_items = _parse_textract_expense(expense_response)

        if not raw_items:
            # Fallback: plain text detection (less structured but catches more)
            text_response = textract.detect_document_text(Document={"Bytes": image_bytes})
            raw_items = _parse_textract_text_fallback(text_response)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Textract error: {exc}. "
                "Check EC2 IAM role has textract:AnalyzeExpense permission."
            ),
        )

    # ── Step 3: Clean item names ───────────────────────────────────────────────
    cleaned_items = []
    for raw in raw_items[:20]:   # cap at 20 to limit external API calls
        cleaned = clean_receipt_item(raw)
        if cleaned and len(cleaned) >= 3:
            cleaned_items.append({"raw": raw, "cleaned": cleaned})

    if not cleaned_items:
        return {"matched": [], "unmatched": [], "total_lines": len(raw_items)}

    # ── Steps 4–5: Parallel product lookup + recall check ─────────────────────
    async def lookup(entry: dict) -> tuple[dict, Optional[dict]]:
        product = await asyncio.to_thread(_search_product_sync, entry["cleaned"])
        return entry, product

    results = await asyncio.gather(*[lookup(e) for e in cleaned_items], return_exceptions=True)

    matched: list[dict]   = []
    unmatched: list[str]  = []

    for result in results:
        if isinstance(result, Exception):
            continue
        entry, product = result
        if product and product.get("product_name"):
            upc = product.get("upc") or ""
            recall_info = _check_recall(upc) if upc else None
            matched.append({
                "raw_text":     entry["raw"],
                "cleaned_text": entry["cleaned"],
                "upc":          upc,
                "product_name": product["product_name"],
                "brand_name":   product["brand_name"],
                "ingredients":  product["ingredients"],
                "is_recalled":  recall_info is not None,
                "recall_info":  recall_info,
                "source":       product.get("source", "unknown"),
            })
        else:
            unmatched.append(entry["raw"])

    return {
        "matched":     matched,
        "unmatched":   unmatched,
        "total_lines": len(raw_items),
    }
