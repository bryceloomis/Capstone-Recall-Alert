"""
user_routes.py – FastAPI APIRouter for user auth and grocery cart.

Endpoints:
  POST   /api/users/register                   – create account
  POST   /api/users/login                      – sign in
  GET    /api/user/cart/{user_id}              – fetch user's grocery list
  POST   /api/user/cart                        – add item to list (barcode scan)
  DELETE /api/user/cart/{user_id}/{upc}        – remove a barcode item by UPC
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
    name:     str
    email:    str
    password: str


class UserLogin(BaseModel):
    email:    str
    password: str


class UserCartItem(BaseModel):
    user_id:      str
    upc:          Optional[str] = None   # None for receipt-sourced items
    product_name: str
    brand_name:   str = ""
    added_date:   str = ""
    source:       str = "barcode"        # 'barcode' | 'receipt'


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


@router.post("/api/users/login")
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


# ── Cart ───────────────────────────────────────────────────────────────────────

@router.get("/api/user/cart/{user_id}")
async def get_user_cart(user_id: str):
    """Return all items in a user's saved grocery list from RDS."""
    uid = _parse_user_id(user_id)
    if uid is None:
        return {"user_id": user_id, "cart": [], "count": 0}

    rows = execute_query(
        """
        SELECT product_upc AS upc, product_name, brand_name, added_date, source
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
      source will be set to 'receipt'.
    """
    uid = _parse_user_id(item.user_id)
    if uid is None:
        raise HTTPException(status_code=401, detail="Must be signed in to save items.")

    if item.upc:
        # Barcode-scanned item — has a real UPC
        result = execute_query(
            """
            INSERT INTO user_carts (user_id, product_upc, product_name, brand_name, source)
            VALUES (%s, %s, %s, %s, 'barcode')
            ON CONFLICT (user_id, product_upc) DO NOTHING
            RETURNING product_upc AS upc, product_name, brand_name, added_date, source;
            """,
            (uid, item.upc, item.product_name, item.brand_name),
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
