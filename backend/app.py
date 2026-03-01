"""
app.py – FastAPI entry point for the Food Recall Alert API.

Sub-modules (teammates can edit independently):
  receipt_scan.py  – receipt photo OCR → product matching → recall check
  recall_update.py – FDA/USDA recall fetch, DB upsert, alert generation,
                     APScheduler (every 6 hours)

Core endpoints live here:
  GET  /                              – API overview
  GET  /api/health                    – live DB counts
  POST /api/search                    – product search by UPC or name
  POST /api/products                  – manually submit a product not found in Open Food Facts
  GET  /api/recalls                   – all recalls
  GET  /api/recalls/check/{upc}       – recall status for a single UPC
  GET  /api/user/cart/{user_id}       – user's grocery list
  POST /api/user/cart                 – add item to list
  DEL  /api/user/cart/{user_id}/{upc} – remove item
  POST /api/users/register            – create account
  POST /api/users/login               – sign in
  GET  /api/db-test                   – dev: DB health + row counts

Sub-module endpoints (imported via router):
  POST /api/receipt/scan              – receipt_scan.py
  POST /api/admin/refresh-recalls     – recall_update.py

Barcode scan flow:
  1. Check RDS products cache (fast, no API call)
  2. If not cached → query Open Food Facts API by UPC
  3. If found in OFF → save to products table for future lookups
  4. If not found anywhere → return found=False so frontend can show manual entry form
  5. Always cross-reference recalls table on the UPC
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
import bcrypt
import requests as req

log = logging.getLogger(__name__)

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{upc}.json"
OFF_HEADERS     = {"User-Agent": "RecallAlert/0.2 (capstone@berkeley.edu)"}

from database import test_connection, execute_query

# Sub-module routers
from receipt_scan  import router as receipt_router
from recall_update import router as recall_router, start_recall_scheduler

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Food Recall Alert API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register sub-module routes
app.include_router(receipt_router)
app.include_router(recall_router)


# ── Startup event ──────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    """Start the recall refresh background scheduler when the server launches."""
    start_recall_scheduler()


# ── Data Models ───────────────────────────────────────────────────────────────

class ProductSearch(BaseModel):
    upc:  Optional[str] = None
    name: Optional[str] = None

class Product(BaseModel):
    upc:          str
    product_name: str
    brand_name:   str
    category:     Optional[str] = None
    ingredients:  Optional[str] = None
    is_recalled:  bool = False
    recall_info:  Optional[dict] = None

class UserCartItem(BaseModel):
    user_id:      str
    upc:          str
    product_name: str
    brand_name:   str
    added_date:   str

class UserRegister(BaseModel):
    name:     str
    email:    str
    password: str

class UserLogin(BaseModel):
    email:    str
    password: str

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
    Returns a dict ready to INSERT into the products table, or None if not found.
    """
    try:
        resp = req.get(
            OFF_PRODUCT_URL.format(upc=upc),
            headers=OFF_HEADERS,
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != 1:
            return None
        p = data["product"]
        product_name = (p.get("product_name") or "").strip()
        if not product_name:
            return None
        return {
            "upc":          upc,
            "product_name": product_name[:255],
            "brand_name":   (p.get("brands") or "").split(",")[0].strip()[:255],
            "category":     (p.get("categories") or "").split(",")[0].strip()[:100],
            "ingredients":  (p.get("ingredients_text") or "")[:5000],
            "image_url":    (p.get("image_url") or "")[:500],
        }
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


def _parse_user_id(user_id: str) -> Optional[int]:
    """Parse user_id string → int. Returns None for guest ids like 'test_user'."""
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


# ── Core Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "message":   "Food Recall Alert API",
        "version":   "0.2.0",
        "endpoints": {
            "/api/health":                  "Health check (live DB counts)",
            "/api/search":                  "POST – search by UPC or name",
            "/api/recalls":                 "GET  – all recalls (newest first)",
            "/api/recalls/check/{upc}":     "GET  – recall status for one UPC",
            "/api/user/cart/{user_id}":     "GET  – user's saved grocery list",
            "/api/user/cart":               "POST – add item to grocery list",
            "/api/receipt/scan":            "POST – receipt photo OCR + matching",
            "/api/admin/refresh-recalls":   "POST – manual recall refresh",
            "/api/users/register":          "POST – create account",
            "/api/users/login":             "POST – sign in",
        },
    }


@app.get("/api/health")
async def health_check():
    try:
        products_count = execute_query("SELECT COUNT(*) AS total FROM products;")[0]["total"]
        recalls_count  = execute_query("SELECT COUNT(*) AS total FROM recalls;")[0]["total"]
    except Exception:
        products_count = recalls_count = 0
    return {
        "status":         "healthy",
        "timestamp":      datetime.now().isoformat(),
        "products_count": products_count,
        "recalls_count":  recalls_count,
    }


@app.post("/api/search")
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


@app.post("/api/products")
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


@app.get("/api/recalls")
async def get_all_recalls():
    """Return all recalls from RDS, newest first."""
    rows = execute_query("SELECT * FROM recalls ORDER BY recall_date DESC;")
    return {
        "count":   len(rows),
        "recalls": [format_recall(r) for r in rows],
    }


@app.get("/api/recalls/check/{upc}")
async def check_recall_for_upc(upc: str):
    """Check whether a specific UPC has an active recall."""
    rows = execute_query(
        "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
        (upc,),
    )
    if rows:
        return {"is_recalled": True, "recall_info": format_recall(rows[0])}
    return {"is_recalled": False, "recall_info": None}


# ── Cart ───────────────────────────────────────────────────────────────────────

@app.get("/api/user/cart/{user_id}")
async def get_user_cart(user_id: str):
    """Return all items in a user's saved grocery list from RDS."""
    uid = _parse_user_id(user_id)
    if uid is None:
        return {"user_id": user_id, "cart": [], "count": 0}

    rows = execute_query(
        """
        SELECT product_upc AS upc, product_name, brand_name, added_date
        FROM user_carts
        WHERE user_id = %s
        ORDER BY added_date DESC;
        """,
        (uid,),
    )
    cart = [
        {
            "upc":          r["upc"],
            "product_name": r["product_name"],
            "brand_name":   r["brand_name"],
            "added_date":   str(r["added_date"]),
        }
        for r in rows
    ]
    return {"user_id": user_id, "cart": cart, "count": len(cart)}


@app.post("/api/user/cart")
async def add_to_cart(item: UserCartItem):
    """Add an item to the user's grocery list in RDS."""
    uid = _parse_user_id(item.user_id)
    if uid is None:
        raise HTTPException(status_code=401, detail="Must be signed in to save items.")

    result = execute_query(
        """
        INSERT INTO user_carts (user_id, product_upc, product_name, brand_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, product_upc) DO NOTHING
        RETURNING product_upc AS upc, product_name, brand_name, added_date;
        """,
        (uid, item.upc, item.product_name, item.brand_name),
    )

    if not result:
        return {"message": "Item already in your list"}

    row = result[0]
    return {
        "message": "Item added to your grocery list",
        "item": {
            "upc":          row["upc"],
            "product_name": row["product_name"],
            "brand_name":   row["brand_name"],
            "added_date":   str(row["added_date"]),
        },
    }


@app.delete("/api/user/cart/{user_id}/{upc}")
async def remove_from_cart(user_id: str, upc: str):
    """Remove an item from the user's grocery list in RDS."""
    uid = _parse_user_id(user_id)
    if uid is None:
        raise HTTPException(status_code=401, detail="Must be signed in to modify your list.")

    execute_query(
        "DELETE FROM user_carts WHERE user_id = %s AND product_upc = %s;",
        (uid, upc),
    )
    count_result = execute_query(
        "SELECT COUNT(*) AS total FROM user_carts WHERE user_id = %s;",
        (uid,),
    )
    return {
        "message":    "Item removed",
        "cart_count": count_result[0]["total"] if count_result else 0,
    }


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.post("/api/users/register")
async def register_user(user: UserRegister):
    """Create a new user account with a bcrypt-hashed password."""
    existing = execute_query("SELECT id FROM users WHERE email = %s;", (user.email,))
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    password_hash = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
    result = execute_query(
        """
        INSERT INTO users (name, email, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id, name, email, created_at;
        """,
        (user.name, user.email, password_hash),
    )
    new_user = result[0]
    return {
        "message": "Account created successfully.",
        "user": {
            "id":         new_user["id"],
            "name":       new_user["name"],
            "email":      new_user["email"],
            "created_at": str(new_user["created_at"]),
        },
    }


@app.post("/api/users/login")
async def login_user(credentials: UserLogin):
    """Verify email + password and return the user record."""
    result = execute_query(
        "SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s;",
        (credentials.email,),
    )
    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user = result[0]
    if not bcrypt.checkpw(credentials.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "message": "Login successful.",
        "user": {
            "id":         user["id"],
            "name":       user["name"],
            "email":      user["email"],
            "created_at": str(user["created_at"]),
        },
    }


# ── Dev / debug ────────────────────────────────────────────────────────────────

@app.get("/api/db-test")
async def db_test():
    """Verify RDS connection and return row counts. Remove before production."""
    if not test_connection():
        raise HTTPException(status_code=503, detail="Cannot connect to database.")

    tables  = ["users", "products", "recalls", "user_carts", "alerts"]
    summary = {}
    for table in tables:
        try:
            rows      = execute_query(f"SELECT * FROM {table} LIMIT 5;")
            count_row = execute_query(f"SELECT COUNT(*) AS total FROM {table};")
            summary[table] = {
                "total_rows":  count_row[0]["total"] if count_row else 0,
                "sample_rows": rows,
            }
        except Exception as exc:
            summary[table] = {"error": str(exc)}

    return {
        "db_connected": True,
        "rds_host":     "food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com",
        "database":     "food_recall",
        "tables":       summary,
    }


# ── Run locally ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
