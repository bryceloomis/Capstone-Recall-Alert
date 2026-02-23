from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import asyncio
import io
import re
import bcrypt
import boto3
import requests as req
from PIL import Image
from database import test_connection, execute_query

app = FastAPI(title="Food Recall Alert API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Data Models ───────────────────────────────────────────────────────────────

class ProductSearch(BaseModel):
    upc: Optional[str] = None
    name: Optional[str] = None

class Product(BaseModel):
    upc: str
    product_name: str
    brand_name: str
    category: Optional[str] = None
    ingredients: Optional[str] = None
    is_recalled: bool = False
    recall_info: Optional[dict] = None

class UserCartItem(BaseModel):
    user_id: str
    upc: str
    product_name: str
    brand_name: str
    added_date: str

class UserRegister(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

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
        "id":                   row["id"],
        "upc":                  row["upc"],
        "product_name":         row["product_name"],
        "brand_name":           row.get("brand_name") or "",
        "recall_date":          str(row["recall_date"]),
        "reason":               row["reason"],
        "hazard_classification": hazard,
        "source":               row.get("source") or "",
        "firm_name":            row.get("firm_name") or "",
        "distribution":         row.get("distribution_pattern") or "",
    }

def _parse_user_id(user_id: str) -> Optional[int]:
    """Parse user_id string to int; return None for non-numeric ids like 'test_user'."""
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "message": "Food Recall Alert API",
        "version": "0.2.0",
        "endpoints": {
            "/api/health":                  "Health check (live DB counts)",
            "/api/search":                  "POST – search by UPC or name",
            "/api/recalls":                 "GET  – all recalls (newest first)",
            "/api/user/cart/{user_id}":     "GET  – user's saved grocery list",
            "/api/user/cart":               "POST – add item to grocery list",
            "/api/users/register":          "POST – create account",
            "/api/users/login":             "POST – sign in",
        }
    }


@app.get("/api/health")
async def health_check():
    try:
        products_count = execute_query("SELECT COUNT(*) AS total FROM products;")[0]["total"]
        recalls_count  = execute_query("SELECT COUNT(*) AS total FROM recalls;")[0]["total"]
    except Exception:
        products_count = recalls_count = 0
    return {
        "status":          "healthy",
        "timestamp":       datetime.now().isoformat(),
        "products_count":  products_count,
        "recalls_count":   recalls_count,
    }


@app.post("/api/search")
async def search_product(search: ProductSearch):
    """Search for a product by UPC (exact) or name (fuzzy). Returns product + recall status."""

    if search.upc:
        rows = execute_query(
            "SELECT * FROM products WHERE upc = %s LIMIT 1;",
            (search.upc,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Product not found")

        product = rows[0]
        recall_rows = execute_query(
            "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
            (search.upc,)
        )
        recall_info = format_recall(recall_rows[0]) if recall_rows else None

        ingredients_raw = product.get("ingredients") or ""
        ingredients = [i.strip() for i in ingredients_raw.split("|") if i.strip()]

        return {
            "upc":           product["upc"],
            "product_name":  product["product_name"],
            "brand_name":    product["brand_name"],
            "category":      product.get("category") or "Unknown",
            "ingredients":   ingredients,
            "is_recalled":   recall_info is not None,
            "recall_info":   recall_info,
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
            (pattern, pattern)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="No products found")

        results = []
        for product in rows:
            recall_rows = execute_query(
                "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
                (product["upc"],)
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
    """Check whether a specific UPC has an active recall.
    Called by the barcode scanner so every scan gets a recall check
    even if the product isn't in our products table.
    """
    rows = execute_query(
        "SELECT * FROM recalls WHERE upc = %s ORDER BY recall_date DESC LIMIT 1;",
        (upc,)
    )
    if rows:
        return {"is_recalled": True, "recall_info": format_recall(rows[0])}
    return {"is_recalled": False, "recall_info": None}


@app.get("/api/user/cart/{user_id}")
async def get_user_cart(user_id: str):
    """Return all items in a user's saved grocery list from RDS."""
    uid = _parse_user_id(user_id)
    if uid is None:
        # Guest / not logged in — return empty so frontend uses local Zustand state
        return {"user_id": user_id, "cart": [], "count": 0}

    rows = execute_query(
        """
        SELECT product_upc AS upc, product_name, brand_name, added_date
        FROM user_carts
        WHERE user_id = %s
        ORDER BY added_date DESC;
        """,
        (uid,)
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
        (uid, item.upc, item.product_name, item.brand_name)
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
        (uid, upc)
    )
    count_result = execute_query(
        "SELECT COUNT(*) AS total FROM user_carts WHERE user_id = %s;",
        (uid,)
    )
    return {
        "message":    "Item removed",
        "cart_count": count_result[0]["total"] if count_result else 0,
    }


# ── Auth ──────────────────────────────────────────────────────────────────────

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
        (user.name, user.email, password_hash)
    )
    new_user = result[0]
    return {
        "message": "Account created successfully.",
        "user": {
            "id":         new_user["id"],
            "name":       new_user["name"],
            "email":      new_user["email"],
            "created_at": str(new_user["created_at"]),
        }
    }


@app.post("/api/users/login")
async def login_user(credentials: UserLogin):
    """Verify email + password and return the user record."""
    result = execute_query(
        "SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s;",
        (credentials.email,)
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
        }
    }


# ── Receipt Scanning ──────────────────────────────────────────────────────────

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


def clean_receipt_item(raw: str) -> str:
    """
    Clean a raw receipt line item into a search-friendly product name.

    # TODO: Upgrade to LLM for much better accuracy when an API key is available:
    #
    #   import anthropic
    #   client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    #   msg = client.messages.create(
    #       model="claude-haiku-20240307",
    #       max_tokens=40,
    #       messages=[{"role": "user", "content":
    #           f"Receipt line item: '{raw}'. What food product is this? Reply with just the clean product name."}]
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
    text = re.sub(r"\s+\d+(\.\d+)?\s*(LB|OZ|EA|CT|PK|LT|ML|G|KG)?\s*$", "", text, flags=re.IGNORECASE)
    # Drop short all-caps SKU tokens (e.g. "F3A", "BOGO", "PLU")
    words = [
        w for w in text.split()
        if not (re.match(r"^[A-Z0-9]{2,6}$", w) and len(w) <= 5)
    ]
    return " ".join(words).strip()


def _search_off_sync(query: str) -> Optional[dict]:
    """Search Open Food Facts by product name (blocking – run in thread)."""
    if not query or len(query) < 3:
        return None
    try:
        resp = req.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={
                "search_terms": query,
                "json": "1",
                "page_size": "3",
                "fields": "code,product_name,brands,ingredients_text",
            },
            timeout=7,
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
            "upc": p.get("code", ""),
            "product_name": name,
            "brand_name": brand,
            "ingredients": ingredients,
        }
    except Exception:
        return None


@app.post("/api/receipt/scan")
async def scan_receipt(file: UploadFile = File(...)):
    """
    Process a receipt photo:
      1. AWS Textract AnalyzeExpense  → structured line items
      2. Regex cleaner (LLM-ready stub) → human-readable product names
      3. Open Food Facts search (parallel) → product matches
    Returns: { matched: [...], unmatched: [...], total_lines: N }
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # Normalize to JPEG — Textract only accepts JPEG and PNG.
    # Many phones save images as WebP (even with .jpg extension), HEIC, etc.
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.format not in ("JPEG", "PNG"):
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=90)
            image_bytes = buf.getvalue()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read image: {e}")

    # 1. AWS Textract – uses EC2 IAM role, no credentials in code
    try:
        textract = boto3.client("textract", region_name="us-east-1")
        expense_response = textract.analyze_expense(Document={"Bytes": image_bytes})
        raw_items = _parse_textract_expense(expense_response)

        # Fallback: if AnalyzeExpense found no line items, try plain text detection
        if not raw_items:
            text_response = textract.detect_document_text(Document={"Bytes": image_bytes})
            raw_items = _parse_textract_text_fallback(text_response)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Textract error: {str(e)}. Check EC2 IAM role has textract:AnalyzeExpense permission."
        )

    # 2. Clean item names (regex stub; swap in LLM call here)
    cleaned_items = []
    for raw in raw_items[:20]:   # Cap at 20 items to limit API calls
        cleaned = clean_receipt_item(raw)
        if cleaned:
            cleaned_items.append({"raw": raw, "cleaned": cleaned})

    if not cleaned_items:
        return {"matched": [], "unmatched": [], "total_lines": len(raw_items)}

    # 3. Search Open Food Facts in parallel (asyncio.to_thread wraps sync requests)
    async def lookup(entry: dict) -> tuple[dict, Optional[dict]]:
        result = await asyncio.to_thread(_search_off_sync, entry["cleaned"])
        return entry, result

    search_tasks = [lookup(entry) for entry in cleaned_items]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    matched = []
    unmatched = []

    for result in results:
        if isinstance(result, Exception):
            continue
        entry, product = result
        if product and product.get("product_name"):
            matched.append({
                "raw_text":     entry["raw"],
                "cleaned_text": entry["cleaned"],
                "upc":          product["upc"],
                "product_name": product["product_name"],
                "brand_name":   product["brand_name"],
                "ingredients":  product["ingredients"],
            })
        else:
            unmatched.append(entry["raw"])

    return {
        "matched":     matched,
        "unmatched":   unmatched,
        "total_lines": len(raw_items),
    }


# ── Dev / debug ───────────────────────────────────────────────────────────────

@app.get("/api/db-test")
async def db_test():
    """Verify RDS connection and return row counts. Remove before production."""
    if not test_connection():
        raise HTTPException(status_code=503, detail="Cannot connect to database.")

    tables = ["users", "products", "recalls", "user_carts", "alerts"]
    summary = {}
    for table in tables:
        try:
            rows        = execute_query(f"SELECT * FROM {table} LIMIT 5;")
            count_row   = execute_query(f"SELECT COUNT(*) AS total FROM {table};")
            summary[table] = {
                "total_rows":  count_row[0]["total"] if count_row else 0,
                "sample_rows": rows,
            }
        except Exception as e:
            summary[table] = {"error": str(e)}

    return {
        "db_connected": True,
        "rds_host":     "food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com",
        "database":     "food_recall",
        "tables":       summary,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
