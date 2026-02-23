from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import csv
from datetime import datetime
import bcrypt
from database import test_connection, execute_query

app = FastAPI(title="Food Recall Alert API")

# Enable CORS for frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Models
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

# In-memory data stores (will be replaced with RDS later)
recalls_db = []
products_db = []
user_carts = {}  # {user_id: [items]}

# Load data from CSV files on startup
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

# Helper functions
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

# API Endpoints

@app.get("/")
async def root():
    return {
        "message": "Food Recall Alert API",
        "version": "0.1.0",
        "endpoints": {
            "/api/health": "Health check",
            "/api/search": "Search for product by UPC or name",
            "/api/recalls": "Get all recalls",
            "/api/user/cart/{user_id}": "Get user's cart",
            "/api/user/cart": "Add item to cart"
        }
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "recalls_count": len(recalls_db),
        "products_count": len(products_db)
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

@app.post("/api/users/register")
async def register_user(user: UserRegister):
    """Create a new user account with a hashed password."""
    # Check if email already exists
    existing = execute_query(
        "SELECT id FROM users WHERE email = %s;",
        (user.email,)
    )
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    # Hash the password
    password_hash = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

    # Insert user into DB
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
            "id": new_user["id"],
            "name": new_user["name"],
            "email": new_user["email"],
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
    password_matches = bcrypt.checkpw(
        credentials.password.encode(),
        user["password_hash"].encode()
    )
    if not password_matches:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "created_at": str(user["created_at"]),
        }
    }


@app.get("/api/db-test")
async def db_test():
    """
    Test endpoint: verifies RDS connection and returns row counts + first 5 rows
    from each table. Remove or restrict access before going to production.
    """
    connected = test_connection()
    if not connected:
        raise HTTPException(status_code=503, detail="Cannot connect to database. Check .env credentials and RDS security group.")

    tables = ["users", "products", "recalls", "user_carts", "alerts"]
    summary = {}
    for table in tables:
        try:
            rows = execute_query(f"SELECT * FROM {table} LIMIT 5;")
            count_result = execute_query(f"SELECT COUNT(*) AS total FROM {table};")
            summary[table] = {
                "total_rows": count_result[0]["total"] if count_result else 0,
                "sample_rows": rows,
            }
        except Exception as e:
            summary[table] = {"error": str(e)}

    return {
        "db_connected": True,
        "rds_host": "food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com",
        "database": "food_recall",
        "tables": summary,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
