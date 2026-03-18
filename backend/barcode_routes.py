"""
barcode_routes.py – FastAPI APIRouter for barcode scanning and product lookup.

Barcode scan flow:
  1. Check RDS products cache (fast, no API call)
  2. If not cached → query Open Food Facts API by UPC
  3. If found in OFF → save to products table for future lookups
  4. If not found anywhere → return found=False so frontend can show manual entry form
  5. Always cross-reference recalls table on the UPC
  6. If user_id provided → run ingredient risk analysis against user profile

Endpoints:
  POST /api/search                – product search by UPC or name (+ inline risk)
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
from ingredient_risk_engine import analyse_product_risk
from state_matcher import is_state_affected

log = logging.getLogger(__name__)

router = APIRouter()

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{upc}.json"
OFF_HEADERS     = {"User-Agent": "RecallAlert/0.2 (capstone@berkeley.edu)"}


# ── Data Models ────────────────────────────────────────────────────────────────

class ProductSearch(BaseModel):
    upc:     Optional[str] = None
    name:    Optional[str] = None
    user_id: Optional[int] = None   # NEW: enables personalised risk analysis


class ManualProduct(BaseModel):
    """Payload for manually submitting a product that wasn't found in Open Food Facts."""
    upc:          str
    product_name: str
    brand_name:   Optional[str] = None
    category:     Optional[str] = None
    ingredients:  Optional[str] = None
    user_id:      Optional[int] = None   # NEW: run risk on submission


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

import re
from typing import Optional

def normalize_product_name(name: str) -> str:
    """Normalize product names for fuzzy comparison."""
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r"[®™©]", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def word_overlap_score(a: str, b: str) -> float:
    """
    Return proportion of words in the shorter phrase that appear in the longer phrase.
    Example:
      'ritz crackers' vs 'nabisco ritz original crackers' -> 1.0
    """
    words_a = set(re.findall(r"[a-z0-9]+", normalize_product_name(a)))
    words_b = set(re.findall(r"[a-z0-9]+", normalize_product_name(b)))

    noise = {
        "oz", "fl", "ct", "pk", "lb", "g", "kg", "ml",
        "the", "and", "or", "of", "in", "a"
    }
    words_a -= noise
    words_b -= noise

    if not words_a or not words_b:
        return 0.0

    shorter, longer = (words_a, words_b) if len(words_a) <= len(words_b) else (words_b, words_a)
    return len(shorter & longer) / len(shorter)

def check_recall(upc: str, product_name: str = "", brand_name: str = "") -> Optional[dict]:
    """
    Check if a product has an active recall.

    Matching strategy:
      Step 1 — Exact UPC match
      Step 2 — Fuzzy product-name match:
          similarity >= 0.35
          OR substring match
          OR word overlap >= 1.0

    Returns formatted recall dict with match metadata, or None.
    """
    # ── Step 1: Exact UPC match ───────────────────────────────────────────
    rows = execute_query(
        "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
        (upc,),
    )
    if rows:
        result = format_recall(rows[0])
        result["match_method"] = "exact_upc"
        result["match_confidence"] = 1.0
        return result

    # ── Step 2: Fuzzy product name match ──────────────────────────────────
    if not product_name:
        return None

    normalized_input = normalize_product_name(product_name)
    if not normalized_input:
        return None

    try:
        # Pull a candidate set using pg_trgm and substring.
        # Then score word overlap in Python.
        rows = execute_query(
            """
            SELECT *,
                   similarity(LOWER(product_name), LOWER(%s)) AS name_sim
            FROM recalls
            WHERE similarity(LOWER(product_name), LOWER(%s)) >= 0.35
               OR LOWER(product_name) LIKE '%%' || LOWER(%s) || '%%'
               OR LOWER(%s) LIKE '%%' || LOWER(product_name) || '%%'
            ORDER BY
                similarity(LOWER(product_name), LOWER(%s)) DESC,
                recall_date DESC
            LIMIT 25;
            """,
            (product_name, product_name, product_name, product_name, product_name),
        )

        best_match = None
        best_score = -1.0

        for row in rows:
            recall_name = row.get("product_name") or ""
            normalized_recall = normalize_product_name(recall_name)

            sim = float(row.get("name_sim", 0.0))
            substring_hit = (
                normalized_input in normalized_recall
                or normalized_recall in normalized_input
            )
            overlap = word_overlap_score(normalized_input, normalized_recall)

            matched = (
                sim >= 0.40
                or substring_hit
                or overlap >= 1.0
            )

            if not matched:
                continue

            # Rank candidates:
            # exact-ish substring/overlap first, then trigram, then recent recall_date
            rank_score = max(
                1.0 if substring_hit else 0.0,
                overlap,
                sim,
            )

            if rank_score > best_score:
                best_score = rank_score
                best_match = (row, sim, substring_hit, overlap)

        if best_match:
            row, sim, substring_hit, overlap = best_match
            result = format_recall(row)

            if substring_hit:
                result["match_method"] = "substring"
                result["match_confidence"] = 1.0
            elif overlap >= 1.0:
                result["match_method"] = "word_overlap"
                result["match_confidence"] = 1.0
            else:
                result["match_method"] = "fuzzy_name"
                result["match_confidence"] = round(sim, 2)

            result["name_similarity"] = round(sim, 3)
            result["word_overlap"] = round(overlap, 3)
            return result

    except Exception as exc:
        log.warning("Fuzzy recall check failed (pg_trgm may not be enabled): %s", exc)

        # Fallback if pg_trgm is unavailable:
        # use substring + Python word overlap only
        try:
            rows = execute_query(
                """
                SELECT * FROM recalls
                WHERE LOWER(product_name) LIKE '%%' || LOWER(%s) || '%%'
                   OR LOWER(%s) LIKE '%%' || LOWER(product_name) || '%%'
                ORDER BY recall_date DESC
                LIMIT 25;
                """,
                (product_name, product_name),
            )

            best_match = None
            for row in rows:
                recall_name = row.get("product_name") or ""
                normalized_recall = normalize_product_name(recall_name)

                substring_hit = (
                    normalized_input in normalized_recall
                    or normalized_recall in normalized_input
                )
                overlap = word_overlap_score(normalized_input, normalized_recall)

                if substring_hit or overlap >= 1.0:
                    best_match = (row, substring_hit, overlap)
                    break

            if best_match:
                row, substring_hit, overlap = best_match
                result = format_recall(row)
                result["match_method"] = "substring" if substring_hit else "word_overlap"
                result["match_confidence"] = 1.0
                result["word_overlap"] = round(overlap, 3)
                return result

        except Exception as fallback_exc:
            log.warning("Fallback fuzzy recall check failed: %s", fallback_exc)

    return None

# def check_recall(upc: str, product_name: str = "", brand_name: str = "") -> Optional[dict]:
#     """
#     Check if a product has an active recall.

#     Two-step strategy (most FDA recalls don't include UPC barcodes):

#       Step 1 — Exact UPC match.
#         Works for the ~20% of FDA records that contain a barcode in code_info.

#       Step 2 — Fuzzy product name match (fallback).
#         Uses pg_trgm similarity to compare the product name (from Open Food
#         Facts) against recall product_name.  Falls back to ILIKE substring
#         if pg_trgm isn't installed.

#     Returns formatted recall dict with match_method field, or None.
#     """
#     # ── Step 1: Exact UPC match ───────────────────────────────────────────
#     rows = execute_query(
#         "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
#         (upc,),
#     )
#     if rows:
#         result = format_recall(rows[0])
#         result["match_method"] = "exact_upc"
#         return result

#     # ── Step 2: Fuzzy product name match ──────────────────────────────────
#     if not product_name:
#         return None

#     try:
#         # pg_trgm similarity — requires CREATE EXTENSION pg_trgm
#         rows = execute_query(
#             """
#             SELECT *,
#                    similarity(LOWER(product_name), LOWER(%s)) AS name_sim
#             FROM recalls
#             WHERE similarity(LOWER(product_name), LOWER(%s)) > 0.35
#                OR LOWER(product_name) LIKE '%%' || LOWER(%s) || '%%'
#             ORDER BY
#                 similarity(LOWER(product_name), LOWER(%s)) DESC,
#                 recall_date DESC
#             LIMIT 1;
#             """,
#             (product_name, product_name, product_name, product_name),
#         )
#         if rows:
#             result = format_recall(rows[0])
#             result["match_method"] = "fuzzy_name"
#             result["match_confidence"] = round(float(rows[0].get("name_sim", 0)), 2)
#             return result

#     except Exception as exc:
#         log.warning("Fuzzy recall check failed (pg_trgm may not be enabled): %s", exc)

#         # Fallback: simple ILIKE substring if pg_trgm not installed
#         try:
#             rows = execute_query(
#                 """
#                 SELECT * FROM recalls
#                 WHERE LOWER(product_name) LIKE '%%' || LOWER(%s) || '%%'
#                 ORDER BY recall_date DESC LIMIT 1;
#                 """,
#                 (product_name,),
#             )
#             if rows:
#                 result = format_recall(rows[0])
#                 result["match_method"] = "substring"
#                 return result
#         except Exception:
#             pass

#     return None


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


def _load_user_profile(user_id: int) -> dict:
    """Load allergens, diet_preferences, and state from users table."""
    rows = execute_query(
        "SELECT allergens, diet_preferences, state FROM users WHERE id = %s LIMIT 1;",
        (user_id,),
    )
    if not rows:
        return {"allergens": [], "diets": [], "state": None}
    row = rows[0]
    allergens = row.get("allergens") or []
    diets     = row.get("diet_preferences") or []
    if isinstance(allergens, str):
        allergens = [a.strip() for a in allergens.split(",") if a.strip()]
    if isinstance(diets, str):
        diets = [d.strip() for d in diets.split(",") if d.strip()]
    return {"allergens": allergens, "diets": diets, "state": row.get("state")}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/api/search")
async def search_product(search: ProductSearch):
    """
    Search for a product by UPC (exact) or name (fuzzy).
    Returns product + recall status + ingredient risk analysis.

    If user_id is provided, allergen and diet preferences are loaded from the
    user's profile for personalised risk scoring.
    """

    # Load user profile once if user_id provided
    allergens: list[str] = []
    diets: list[str] = []
    user_state: Optional[str] = None
    if search.user_id:
        profile = _load_user_profile(search.user_id)
        allergens  = profile["allergens"]
        diets      = profile["diets"]
        user_state = profile["state"]

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

        # 4. Check recalls (exact UPC → fuzzy product name fallback)
        recall_info = check_recall(
            upc,
            product_name=product.get("product_name") or "",
            brand_name=product.get("brand_name") or "",
        )
        if recall_info:
            recall_info["state_relevant"] = is_state_affected(
                user_state, recall_info.get("distribution")
            )

        ingredients_raw = product.get("ingredients") or ""
        ingredients = [i.strip() for i in ingredients_raw.replace("|", ",").split(",") if i.strip()]

        # 5. Run ingredient risk analysis (two-layer verdict)
        risk_report = analyse_product_risk(
            ingredients_text=ingredients_raw,
            user_allergens=allergens,
            user_diets=diets,
            is_recalled=recall_info is not None,
            recall_date=recall_info.get("recall_date") if recall_info else None,
        )

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
            "verdict":      risk_report.verdict,
            "explanation":  risk_report.explanation,
            "risk":         risk_report.to_dict(),
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
            recall_info = check_recall(
                product["upc"],
                product_name=product.get("product_name") or "",
                brand_name=product.get("brand_name") or "",
            )
            if recall_info:
                recall_info["state_relevant"] = is_state_affected(
                    user_state, recall_info.get("distribution")
                )

            ingredients_raw = product.get("ingredients") or ""
            risk_report = analyse_product_risk(
                ingredients_text=ingredients_raw,
                user_allergens=allergens,
                user_diets=diets,
                is_recalled=recall_info is not None,
                recall_date=recall_info.get("recall_date") if recall_info else None,
            )

            results.append({
                "upc":          product["upc"],
                "product_name": product["product_name"],
                "brand_name":   product["brand_name"],
                "category":     product.get("category") or "Unknown",
                "is_recalled":  recall_info is not None,
                "recall_info":  recall_info,
                "verdict":      risk_report.verdict,
                "explanation":  risk_report.explanation,
                "risk":         risk_report.to_dict(),
            })

        return {"count": len(results), "results": results}

    else:
        raise HTTPException(status_code=400, detail="Must provide either UPC or name")


@router.post("/api/products")
async def submit_product(product: ManualProduct):
    """
    Manually submit a product that wasn't found in Open Food Facts.
    Saves to our products table and immediately checks against recalls
    and runs risk analysis if user_id provided.
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

    # Check recalls immediately (exact UPC → fuzzy name fallback)
    recall_info = check_recall(
        upc,
        product_name=product.product_name,
        brand_name=product.brand_name or "",
    )

    # Run risk analysis
    allergens: list[str] = []
    diets: list[str] = []
    user_state: Optional[str] = None
    if product.user_id:
        profile = _load_user_profile(product.user_id)
        allergens  = profile["allergens"]
        diets      = profile["diets"]
        user_state = profile["state"]

    if recall_info:
        recall_info["state_relevant"] = is_state_affected(
            user_state, recall_info.get("distribution")
        )

    risk_report = analyse_product_risk(
        ingredients_text=product.ingredients or "",
        user_allergens=allergens,
        user_diets=diets,
        is_recalled=recall_info is not None,
        recall_date=recall_info.get("recall_date") if recall_info else None,
    )

    return {
        "saved":        True,
        "upc":          upc,
        "product_name": product.product_name,
        "brand_name":   product.brand_name or "",
        "is_recalled":  recall_info is not None,
        "recall_info":  recall_info,
        "verdict":      risk_report.verdict,
        "explanation":  risk_report.explanation,
        "risk":         risk_report.to_dict(),
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
    recall_info = check_recall(upc)
    if recall_info:
        return {"is_recalled": True, "recall_info": recall_info}
    return {"is_recalled": False, "recall_info": None}