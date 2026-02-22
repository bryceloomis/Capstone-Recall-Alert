from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import csv
import logging
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()  # Load .env file (DB_PASSWORD, JWT_SECRET, etc.)

from database import init_db, is_db_available, get_cursor
from auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Food Recall Alert API")

# Enable CORS for frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

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

# Auth models (match frontend types.ts)
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserPreferencesRequest(BaseModel):
    state_location: str
    allergies: List[str] = []
    diet_preferences: List[str] = []

# ---------------------------------------------------------------------------
# In-memory data stores (CSV-based product/recall data)
# ---------------------------------------------------------------------------
recalls_db = []
products_db = []
user_carts = {}  # {user_id: [items]}

# In-memory fallback for auth when DB is unavailable
_mem_users: dict = {}          # {username: {id, username, password_hash, created_at}}
_mem_user_prefs: dict = {}     # {user_id: {state_location, allergies, diet_preferences}}
_mem_next_id = 1


def load_csv_data():
    global recalls_db, products_db

    # Load recalls
    with open('../data/fake_recalls.csv', 'r') as f:
        reader = csv.DictReader(f)
        recalls_db = list(reader)

    # Load products
    with open('../data/fake_products.csv', 'r') as f:
        reader = csv.DictReader(f)
        products_db = list(reader)

    print(f"Loaded {len(recalls_db)} recalls and {len(products_db)} products")


@app.on_event("startup")
async def startup_event():
    load_csv_data()
    db_ok = init_db()
    if db_ok:
        logger.info("Connected to RDS – auth data will be persisted.")
    else:
        logger.info("No DB connection – using in-memory auth (data resets on restart).")


# ---------------------------------------------------------------------------
# Helper functions (product / recall lookup from CSV data)
# ---------------------------------------------------------------------------

def check_if_recalled(upc: str) -> Optional[dict]:
    """Check if a UPC is in the recall database"""
    for recall in recalls_db:
        if recall['upc'] == upc:
            return recall
    return None

def find_product_by_upc(upc: str) -> Optional[dict]:
    """Find product in products database by UPC"""
    for product in products_db:
        if product['upc'] == upc:
            return product
    return None

def fuzzy_search_by_name(name: str) -> List[dict]:
    """Fuzzy search products by name (simple version)"""
    name_lower = name.lower()
    results = []
    for product in products_db:
        if name_lower in product['product_name'].lower() or name_lower in product['brand_name'].lower():
            results.append(product)
    return results[:10]  # Return max 10 results


# ===================================================================
# EXISTING API ENDPOINTS (unchanged)
# ===================================================================

@app.get("/")
async def root():
    return {
        "message": "Food Recall Alert API",
        "version": "0.2.0",
        "endpoints": {
            "/api/health": "Health check",
            "/api/search": "Search for product by UPC or name",
            "/api/recalls": "Get all recalls",
            "/api/user/cart/{user_id}": "Get user's cart",
            "/api/user/cart": "Add item to cart",
            "/api/auth/register": "Create a new account",
            "/api/auth/login": "Log in",
            "/api/user/profile/{user_id}": "Get or update user profile",
        }
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "recalls_count": len(recalls_db),
        "products_count": len(products_db),
        "database_connected": is_db_available(),
    }

@app.post("/api/search")
async def search_product(search: ProductSearch):
    """
    Search for a product by UPC or name.
    Returns product info and recall status.
    """
    if search.upc:
        # Search by UPC (exact match)
        product = find_product_by_upc(search.upc)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Check if recalled
        recall_info = check_if_recalled(search.upc)

        return {
            "upc": product['upc'],
            "product_name": product['product_name'],
            "brand_name": product['brand_name'],
            "category": product.get('category', 'Unknown'),
            "ingredients": product.get('ingredients', '').split('|'),
            "is_recalled": recall_info is not None,
            "recall_info": recall_info if recall_info else None
        }

    elif search.name:
        # Fuzzy search by name
        results = fuzzy_search_by_name(search.name)
        if not results:
            raise HTTPException(status_code=404, detail="No products found")

        # Add recall status to each result
        products_with_recall_status = []
        for product in results:
            recall_info = check_if_recalled(product['upc'])
            products_with_recall_status.append({
                "upc": product['upc'],
                "product_name": product['product_name'],
                "brand_name": product['brand_name'],
                "category": product.get('category', 'Unknown'),
                "is_recalled": recall_info is not None,
                "recall_info": recall_info if recall_info else None
            })

        return {
            "count": len(products_with_recall_status),
            "results": products_with_recall_status
        }

    else:
        raise HTTPException(status_code=400, detail="Must provide either UPC or name")

@app.get("/api/recalls")
async def get_all_recalls():
    """Get all current recalls"""
    return {
        "count": len(recalls_db),
        "recalls": recalls_db
    }

@app.get("/api/user/cart/{user_id}")
async def get_user_cart(user_id: str):
    """Get all items in a user's cart"""
    if user_id not in user_carts:
        return {"user_id": user_id, "cart": [], "count": 0}

    return {
        "user_id": user_id,
        "cart": user_carts[user_id],
        "count": len(user_carts[user_id])
    }

@app.post("/api/user/cart")
async def add_to_cart(item: UserCartItem):
    """Add an item to user's cart"""
    user_id = item.user_id

    if user_id not in user_carts:
        user_carts[user_id] = []

    # Check if item already in cart
    for cart_item in user_carts[user_id]:
        if cart_item['upc'] == item.upc:
            return {
                "message": "Item already in cart",
                "item": cart_item
            }

    # Add to cart
    cart_item = {
        "upc": item.upc,
        "product_name": item.product_name,
        "brand_name": item.brand_name,
        "added_date": datetime.now().isoformat()
    }
    user_carts[user_id].append(cart_item)

    return {
        "message": "Item added to cart",
        "item": cart_item,
        "cart_count": len(user_carts[user_id])
    }

@app.delete("/api/user/cart/{user_id}/{upc}")
async def remove_from_cart(user_id: str, upc: str):
    """Remove an item from user's cart"""
    if user_id not in user_carts:
        raise HTTPException(status_code=404, detail="User cart not found")

    # Find and remove item
    user_carts[user_id] = [item for item in user_carts[user_id] if item['upc'] != upc]

    return {
        "message": "Item removed from cart",
        "cart_count": len(user_carts[user_id])
    }


# ===================================================================
# AUTH ENDPOINTS  (POST /api/auth/register, POST /api/auth/login)
# ===================================================================

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    """
    Create a new user account.
    Returns { user_id, username, token } on success.
    Frontend: Onboarding.tsx → registerUser()
    """
    username = req.username.strip()
    if not username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    pw_hash = hash_password(req.password)

    if is_db_available():
        try:
            with get_cursor(commit=True) as cur:
                # Check for duplicate username
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Username already taken.")

                cur.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id, created_at",
                    (username, pw_hash),
                )
                row = cur.fetchone()
                user_id = row["id"]
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("DB error during registration: %s", exc)
            raise HTTPException(status_code=500, detail="Registration failed. Please try again.")
    else:
        # In-memory fallback
        global _mem_next_id
        if username in _mem_users:
            raise HTTPException(status_code=409, detail="Username already taken.")
        user_id = _mem_next_id
        _mem_next_id += 1
        _mem_users[username] = {
            "id": user_id,
            "username": username,
            "password_hash": pw_hash,
            "created_at": datetime.now().isoformat(),
        }

    token = create_token(user_id, username)
    return {"user_id": user_id, "username": username, "token": token}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """
    Authenticate an existing user.
    Returns { user_id, username, token } on success.
    Frontend: Onboarding.tsx → loginUser()
    """
    username = req.username.strip()

    if is_db_available():
        try:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT id, username, password_hash FROM users WHERE username = %s",
                    (username,),
                )
                row = cur.fetchone()
        except Exception as exc:
            logger.error("DB error during login: %s", exc)
            raise HTTPException(status_code=500, detail="Login failed. Please try again.")

        if not row or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        user_id = row["id"]
        username = row["username"]
    else:
        # In-memory fallback
        user_data = _mem_users.get(username)
        if not user_data or not verify_password(req.password, user_data["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        user_id = user_data["id"]

    token = create_token(user_id, username)
    return {"user_id": user_id, "username": username, "token": token}


# ===================================================================
# PROFILE / PREFERENCES ENDPOINTS
# (GET & PUT /api/user/profile/{user_id})
# ===================================================================

@app.get("/api/user/profile/{user_id}")
async def get_profile(user_id: int, _user: dict = Depends(get_current_user)):
    """
    Return the full user profile including preferences.
    Requires a valid Bearer token.
    Frontend: ProfileSetup.tsx → getUserProfile()
    """
    if is_db_available():
        try:
            with get_cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id AS user_id, u.username, u.created_at,
                           COALESCE(p.state_location, '') AS state_location,
                           COALESCE(p.allergies, '{}') AS allergies,
                           COALESCE(p.diet_preferences, '{}') AS diet_preferences
                    FROM users u
                    LEFT JOIN user_preferences p ON p.user_id = u.id
                    WHERE u.id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        except Exception as exc:
            logger.error("DB error fetching profile: %s", exc)
            raise HTTPException(status_code=500, detail="Could not load profile.")

        if not row:
            raise HTTPException(status_code=404, detail="User not found.")

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "state_location": row["state_location"] or None,
            "allergies": list(row["allergies"]),
            "diet_preferences": list(row["diet_preferences"]),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
    else:
        # In-memory fallback
        user = None
        for u in _mem_users.values():
            if u["id"] == user_id:
                user = u
                break
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        prefs = _mem_user_prefs.get(user_id, {})
        return {
            "user_id": user["id"],
            "username": user["username"],
            "state_location": prefs.get("state_location"),
            "allergies": prefs.get("allergies", []),
            "diet_preferences": prefs.get("diet_preferences", []),
            "created_at": user["created_at"],
        }


@app.put("/api/user/profile/{user_id}")
async def update_profile(
    user_id: int,
    prefs: UserPreferencesRequest,
    _user: dict = Depends(get_current_user),
):
    """
    Create or update user preferences (state, allergies, diet).
    Requires a valid Bearer token.
    Frontend: ProfileSetup.tsx → updateUserPreferences()
    """
    if is_db_available():
        try:
            with get_cursor(commit=True) as cur:
                # Verify user exists
                cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found.")

                # Upsert preferences
                cur.execute(
                    """
                    INSERT INTO user_preferences (user_id, state_location, allergies, diet_preferences)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        state_location   = EXCLUDED.state_location,
                        allergies        = EXCLUDED.allergies,
                        diet_preferences = EXCLUDED.diet_preferences
                    """,
                    (user_id, prefs.state_location, prefs.allergies, prefs.diet_preferences),
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("DB error updating profile: %s", exc)
            raise HTTPException(status_code=500, detail="Could not save preferences.")
    else:
        # In-memory fallback
        _mem_user_prefs[user_id] = {
            "state_location": prefs.state_location,
            "allergies": prefs.allergies,
            "diet_preferences": prefs.diet_preferences,
        }

    # Return the full profile (re-use the GET handler logic)
    return await get_profile(user_id, _user)


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
