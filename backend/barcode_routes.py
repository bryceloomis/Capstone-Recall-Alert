"""
barcode_routes.py – FastAPI APIRouter for barcode scanning and product lookup.

Barcode scan flow:
  1. Check RDS products cache (fast, no API call)
  2. If not cached → query Open Food Facts API by UPC
  3. If found in OFF → save to products table for future lookups
  4. If not found anywhere → return found=False so frontend can show manual entry form
  5. Always cross-reference recalls table on the UPC

Endpoints:
  POST /api/search                – product search by UPC or name
  POST /api/products              – manually submit a product not found in Open Food Facts
  GET  /api/recalls               – all recalls (newest first)
  GET  /api/recalls/check/{upc}   – recall status for a single UPC
"""

import logging
from typing import Optional

import requests as req
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import execute_query

log = logging.getLogger(__name__)

router = APIRouter()

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{upc}.json"
OFF_HEADERS     = {"User-Agent": "RecallAlert/0.2 (capstone@berkeley.edu)"}


# ── Data Models ────────────────────────────────────────────────────────────────

class ProductSearch(BaseModel):
    upc:  Optional[str] = None
    name: Optional[str] = None


class ManualProduct(BaseModel):
    """Payload for manually submitting a product that wasn't found in Open Food Facts."""
    upc:          str
    product_name: str
    brand_name:   Optional[str] = None
    category:     Optional[str] = None
    ingredients:  Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def format_recall(row: dict) -> dict:
    """Map a DB recalls row to the shape the frontend expects."""
    severity = (row.get("severity") or "").lower()
    if "iii" in severity:
        hazard = "Class III"
    elif "ii" in severity:
        hazard = "Class II"
    else:
        hazard = "Class I"
    return {
        "id":                    row["id"],
        "upc":                   row["upc"],
        "product_name":          row["product_name"],
        "brand_name":            row.get("brand_name") or "",
        "recall_date":           str(row["recall_date"]),
        "reason":                row["reason"],
        "hazard_classification": hazard,
        "source":                row.get("source") or "",
        "firm_name":             row.get("firm_name") or "",
        "distribution":          row.get("distribution_pattern") or "",
    }


def _lookup_off(upc: str) -> Optional[dict]:
    """
    Fetch a product from Open Food Facts by UPC.
    Tries the raw UPC first, then zero-padded to 13 digits (EAN-13),
    since most US 12-digit UPC-A barcodes are stored as EAN-13 in OFF.
    Returns a dict ready to INSERT into the products table, or None if not found.
    """
    candidates = [upc]
    if len(upc) == 12:
        candidates.append("0" + upc)    # UPC-A → EAN-13
    elif len(upc) == 13 and upc.startswith("0"):
        candidates.append(upc[1:])      # EAN-13 → UPC-A fallback

    try:
        for candidate in candidates:
            resp = req.get(
                OFF_PRODUCT_URL.format(upc=candidate),
                headers=OFF_HEADERS,
                timeout=8,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get("status") != 1:
                continue
            p = data["product"]
            product_name = (p.get("product_name") or "").strip()
            if not product_name:
                continue
            return {
                "upc":          upc,   # store under the original UPC the user scanned
                "product_name": product_name[:255],
                "brand_name":   (p.get("brands") or "").split(",")[0].strip()[:255],
                "category":     (p.get("categories") or "").split(",")[0].strip()[:100],
                "ingredients":  (p.get("ingredients_text") or "")[:5000],
                "image_url":    (p.get("image_url") or "")[:500],
            }
        return None
    except Exception as exc:
        log.warning("Open Food Facts lookup failed for upc=%s: %s", upc, exc)
        return None


def _cache_product(product: dict) -> None:
    """Save an Open Food Facts product to our DB for future lookups."""
    try:
        execute_query(
            """
            INSERT INTO products (upc, product_name, brand_name, category, ingredients, image_url)
            VALUES (%(upc)s, %(product_name)s, %(brand_name)s, %(category)s, %(ingredients)s, %(image_url)s)
            ON CONFLICT (upc) DO NOTHING;
            """,
            product,
        )
    except Exception as exc:
        log.warning("Failed to cache product upc=%s: %s", product.get("upc"), exc)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/api/search")
async def search_product(search: ProductSearch):
    """Search for a product by UPC (exact) or name (fuzzy). Returns product + recall status."""

    if search.upc:
        upc = search.upc.strip()

        # 1. Check our DB cache first
        rows = execute_query("SELECT * FROM products WHERE upc = %s LIMIT 1;", (upc,))
        product = rows[0] if rows else None

        # 2. Not cached → try Open Food Facts
        if not product:
            off_data = _lookup_off(upc)
            if off_data:
                _cache_product(off_data)   # save for next time
                product = off_data

        # 3. Still not found → tell frontend to show manual entry form
        if not product:
            return {
                "found":   False,
                "upc":     upc,
                "message": "Product not found. Please enter the product details manually.",
            }

        # 4. Check recalls on this UPC
        recall_rows = execute_query(
            "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
            (upc,),
        )
        recall_info = format_recall(recall_rows[0]) if recall_rows else None

        ingredients_raw = product.get("ingredients") or ""
        ingredients = [i.strip() for i in ingredients_raw.replace("|", ",").split(",") if i.strip()]

        return {
            "found":        True,
            "upc":          product["upc"],
            "product_name": product["product_name"],
            "brand_name":   product.get("brand_name") or "",
            "category":     product.get("category") or "Unknown",
            "ingredients":  ingredients,
            "image_url":    product.get("image_url") or "",
            "is_recalled":  recall_info is not None,
            "recall_info":  recall_info,
        }

    elif search.name:
        pattern = f"%{search.name.lower()}%"
        rows = execute_query(
            """
            SELECT * FROM products
            WHERE LOWER(product_name) LIKE %s OR LOWER(brand_name) LIKE %s
            ORDER BY product_name
            LIMIT 10;
            """,
            (pattern, pattern),
        )
        if not rows:
            raise HTTPException(status_code=404, detail="No products found")

        results = []
        for product in rows:
            recall_rows = execute_query(
                "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
                (product["upc"],),
            )
            recall_info = format_recall(recall_rows[0]) if recall_rows else None
            results.append({
                "upc":          product["upc"],
                "product_name": product["product_name"],
                "brand_name":   product["brand_name"],
                "category":     product.get("category") or "Unknown",
                "is_recalled":  recall_info is not None,
                "recall_info":  recall_info,
            })

        return {"count": len(results), "results": results}

    else:
        raise HTTPException(status_code=400, detail="Must provide either UPC or name")


@router.post("/api/products")
async def submit_product(product: ManualProduct):
    """
    Manually submit a product that wasn't found in Open Food Facts.
    Saves to our products table and immediately checks against recalls.
    Frontend should call this after the user fills in the manual entry form.
    """
    upc = product.upc.strip()

    # Don't overwrite if it already exists
    existing = execute_query("SELECT upc FROM products WHERE upc = %s LIMIT 1;", (upc,))
    if not existing:
        execute_query(
            """
            INSERT INTO products (upc, product_name, brand_name, category, ingredients)
            VALUES (%(upc)s, %(product_name)s, %(brand_name)s, %(category)s, %(ingredients)s)
            ON CONFLICT (upc) DO NOTHING;
            """,
            {
                "upc":          upc,
                "product_name": product.product_name.strip()[:255],
                "brand_name":   (product.brand_name or "").strip()[:255],
                "category":     (product.category or "").strip()[:100],
                "ingredients":  (product.ingredients or "").strip(),
            },
        )

    # Check recalls immediately so user knows if what they just entered is recalled
    recall_rows = execute_query(
        "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
        (upc,),
    )
    recall_info = format_recall(recall_rows[0]) if recall_rows else None

    return {
        "saved":        True,
        "upc":          upc,
        "product_name": product.product_name,
        "brand_name":   product.brand_name or "",
        "is_recalled":  recall_info is not None,
        "recall_info":  recall_info,
    }


@router.get("/api/recalls")
async def get_all_recalls():
    """Return all recalls from RDS, newest first."""
    rows = execute_query("SELECT * FROM recalls ORDER BY recall_date DESC;")
    return {
        "count":   len(rows),
        "recalls": [format_recall(r) for r in rows],
    }


@router.get("/api/recalls/check/{upc}")
async def check_recall_for_upc(upc: str):
    """Check whether a specific UPC has an active recall."""
    rows = execute_query(
        "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
        (upc,),
    )
    if rows:
        return {"is_recalled": True, "recall_info": format_recall(rows[0])}
    return {"is_recalled": False, "recall_info": None}
