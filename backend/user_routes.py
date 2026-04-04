"""
user_routes.py – FastAPI APIRouter for user auth, profile, and grocery cart.

Endpoints:
  POST   /api/users/register                     – create account (with allergens + diets)
  POST   /api/users/login                        – sign in (returns profile incl. allergens)
  GET    /api/users/{user_id}/profile            – fetch current allergen & diet profile
  PATCH  /api/users/{user_id}/profile            – update allergens, diets, state
  GET    /api/user/cart/{user_id}                – fetch user's grocery list
  POST   /api/user/cart                          – add item to list (barcode or receipt)
  DELETE /api/user/cart/{user_id}/{upc}          – remove a barcode item by UPC
  DELETE /api/user/cart/{user_id}/receipt/{name} – remove a receipt item by name
"""

import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import execute_query

router = APIRouter()


# ── Data Models ────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name:             str
    email:            str
    password:         str
    state:            Optional[str]       = None   # e.g. "CA"
    allergens:        Optional[list[str]] = []     # e.g. ["Peanuts", "Soy"]
    diet_preferences: Optional[list[str]] = []    # e.g. ["Vegan", "Gluten-Free"]


class UserLogin(BaseModel):
    email:    str
    password: str


class UserCartItem(BaseModel):
    user_id:      str
    upc:          Optional[str] = None   # None for receipt-sourced items
    product_name: str
    brand_name:   str = ""
    added_date:   str = ""
    source:       str = "barcode"        # 'barcode' | 'receipt' | 'manual'


class ProfileUpdate(BaseModel):
    """Payload for updating a user's allergen and diet profile."""
    allergens:        Optional[list[str]] = None
    diet_preferences: Optional[list[str]] = None
    state:            Optional[str]       = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_user_id(user_id: str) -> Optional[int]:
    """Parse user_id string → int. Returns None for guest ids like 'test_user'."""
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


# ── Auth ───────────────────────────────────────────────────────────────────────

@router.post("/api/users/register")
async def register_user(user: UserRegister):
    """
    Create a new user account with a bcrypt-hashed password.
    Persists allergens and diet_preferences so the risk engine
    can personalise results from the first scan onward.
    """
    existing = execute_query("SELECT id FROM users WHERE email = %s;", (user.email,))
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    password_hash = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

    result = execute_query(
        """
        INSERT INTO users (name, email, password_hash, state, allergens, diet_preferences)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, name, email, state, allergens, diet_preferences, created_at;
        """,
        (
            user.name,
            user.email,
            password_hash,
            user.state,
            user.allergens or [],
            user.diet_preferences or [],
        ),
    )
    new_user = result[0]
    return {
        "message": "Account created successfully.",
        "user": {
            "id":               new_user["id"],
            "name":             new_user["name"],
            "email":            new_user["email"],
            "state":            new_user.get("state"),
            "allergens":        new_user.get("allergens") or [],
            "diet_preferences": new_user.get("diet_preferences") or [],
            "created_at":       str(new_user["created_at"]),
        },
    }


@router.post("/api/users/login")
async def login_user(credentials: UserLogin):
    """Verify email + password and return the user record including profile."""
    result = execute_query(
        """
        SELECT id, name, email, password_hash, state,
               allergens, diet_preferences, created_at
        FROM users WHERE email = %s;
        """,
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
            "id":               user["id"],
            "name":             user["name"],
            "email":            user["email"],
            "state":            user.get("state"),
            "allergens":        user.get("allergens") or [],
            "diet_preferences": user.get("diet_preferences") or [],
            "created_at":       str(user["created_at"]),
        },
    }


# ── Profile ────────────────────────────────────────────────────────────────────

@router.get("/api/users/{user_id}/profile")
async def get_user_profile(user_id: int):
    """Return the user's current allergen and diet profile."""
    rows = execute_query(
        """
        SELECT id, name, email, state, allergens, diet_preferences
        FROM users WHERE id = %s LIMIT 1;
        """,
        (user_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found.")
    u = rows[0]
    return {
        "id":               u["id"],
        "name":             u["name"],
        "email":            u["email"],
        "state":            u.get("state"),
        "allergens":        u.get("allergens") or [],
        "diet_preferences": u.get("diet_preferences") or [],
    }


@router.patch("/api/users/{user_id}/profile")
async def update_user_profile(user_id: int, update: ProfileUpdate):
    """
    Update allergens, diet_preferences, and/or state for a user.
    Only supplied fields are changed; omitted (None) fields are left as-is.
    """
    existing = execute_query("SELECT id FROM users WHERE id = %s LIMIT 1;", (user_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="User not found.")

    set_clauses: list[str] = []
    params: list = []

    if update.allergens is not None:
        set_clauses.append("allergens = %s")
        params.append(update.allergens)

    if update.diet_preferences is not None:
        set_clauses.append("diet_preferences = %s")
        params.append(update.diet_preferences)

    if update.state is not None:
        set_clauses.append("state = %s")
        params.append(update.state)

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No fields to update.")

    params.append(user_id)
    query = f"""
        UPDATE users SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING id, name, email, state, allergens, diet_preferences;
    """
    result = execute_query(query, tuple(params))
    u = result[0]
    return {
        "message": "Profile updated.",
        "user": {
            "id":               u["id"],
            "name":             u["name"],
            "email":            u["email"],
            "state":            u.get("state"),
            "allergens":        u.get("allergens") or [],
            "diet_preferences": u.get("diet_preferences") or [],
        },
    }


# ── Cart ───────────────────────────────────────────────────────────────────────

@router.get("/api/user/cart/{user_id}")
async def get_user_cart(user_id: str):
    """Return all items in a user's saved grocery list from RDS."""
    uid = _parse_user_id(user_id)
    if uid is None:
        return {"user_id": user_id, "cart": [], "count": 0}

    rows = execute_query(
        """
        SELECT product_upc AS upc, product_name, brand_name, added_date, source, store_name
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
            "source":       r.get("source", "barcode"),
            "store_name":   r.get("store_name"),
        }
        for r in rows
    ]
    return {"user_id": user_id, "cart": cart, "count": len(cart)}


@router.post("/api/user/cart")
async def add_to_cart(item: UserCartItem):
    """
    Add an item to the user's grocery list in RDS.

    Barcode items (upc provided):
      Deduplicated by (user_id, product_upc).

    Receipt items (upc omitted / None):
      Deduplicated by (user_id, product_name) via partial unique index.
      source is set to 'receipt'.
    """
    uid = _parse_user_id(item.user_id)
    if uid is None:
        raise HTTPException(status_code=401, detail="Must be signed in to save items.")

    if item.upc:
        # Barcode/manual-scanned item — has a real UPC
        source = item.source if item.source in ('barcode', 'manual') else 'barcode'
        result = execute_query(
            """
            INSERT INTO user_carts (user_id, product_upc, product_name, brand_name, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, product_upc) DO NOTHING
            RETURNING product_upc AS upc, product_name, brand_name, added_date, source;
            """,
            (uid, item.upc, item.product_name, item.brand_name, source),
        )
    else:
        # Receipt-sourced item — no UPC
        result = execute_query(
            """
            INSERT INTO user_carts (user_id, product_upc, product_name, brand_name, source)
            VALUES (%s, NULL, %s, %s, 'receipt')
            ON CONFLICT (user_id, product_name) WHERE product_upc IS NULL DO NOTHING
            RETURNING product_upc AS upc, product_name, brand_name, added_date, source;
            """,
            (uid, item.product_name, item.brand_name),
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
            "source":       row["source"],
        },
    }


@router.delete("/api/user/cart/{user_id}/{upc}")
async def remove_from_cart(user_id: str, upc: str):
    """Remove a barcode-scanned item from the user's grocery list by UPC."""
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


@router.delete("/api/user/cart/{user_id}/receipt/{product_name:path}")
async def remove_receipt_item(user_id: str, product_name: str):
    """
    Remove a receipt-sourced item from the user's grocery list by name.
    Used for items that have no UPC (source='receipt').
    The product_name in the URL should be URL-encoded by the caller.
    """
    uid = _parse_user_id(user_id)
    if uid is None:
        raise HTTPException(status_code=401, detail="Must be signed in to modify your list.")

    execute_query(
        """
        DELETE FROM user_carts
        WHERE user_id = %s AND product_upc IS NULL AND product_name = %s;
        """,
        (uid, product_name),
    )
    count_result = execute_query(
        "SELECT COUNT(*) AS total FROM user_carts WHERE user_id = %s;",
        (uid,),
    )
    return {
        "message":    "Item removed",
        "cart_count": count_result[0]["total"] if count_result else 0,
    }
