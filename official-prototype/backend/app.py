from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import csv
import os
from datetime import datetime

import httpx
import boto3

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

# In-memory data stores (will be replaced with RDS later)
recalls_db = []
products_db = []
user_carts = {}  # {user_id: [items]}

# Load data from CSV files on startup
def load_csv_data():
    global recalls_db, products_db
    
    # Try multiple paths for CSV files (works locally and on EC2)
    data_paths = [
        '../data',           # from backend-app/ folder
        '../../data',        # fallback
        '../official-prototype/data',  # from repo root
    ]
    
    data_dir = None
    for path in data_paths:
        if os.path.exists(os.path.join(path, 'fake_recalls.csv')):
            data_dir = path
            break
    
    if data_dir is None:
        print("WARNING: Could not find data directory with CSV files!")
        print("Looked in:", data_paths)
        return
    
    # Load recalls
    with open(os.path.join(data_dir, 'fake_recalls.csv'), 'r') as f:
        reader = csv.DictReader(f)
        recalls_db = list(reader)
    
    # Load products
    with open(os.path.join(data_dir, 'fake_products.csv'), 'r') as f:
        reader = csv.DictReader(f)
        products_db = list(reader)
    
    print(f"Loaded {len(recalls_db)} recalls and {len(products_db)} products from {data_dir}")

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

# ──────────────────────────────────────────────
# API Endpoints (from teammate's working backend)
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "message": "Food Recall Alert API",
        "version": "0.2.0",
        "endpoints": {
            "/api/health": "Health check",
            "/api/search": "Search for product by UPC or name",
            "/api/recalls": "Get all recalls",
            "/api/recalls/fda": "Query FDA openFDA enforcement API",
            "/api/user/cart/{user_id}": "Get user's cart",
            "/api/user/cart": "Add item to cart",
            "/api/upload-image": "Upload scan/product image to S3",
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

# ──────────────────────────────────────────────
# FDA Recall API (Akshita's integration)
# ──────────────────────────────────────────────

@app.get("/api/recalls/fda")
async def api_recalls_fda(upc: str = None, product_name: str = None):
    """Query FDA openFDA enforcement API for recall data."""
    base = "https://api.fda.gov/food/enforcement.json"
    if product_name:
        params = {"search": f'product_description:"{product_name}"', "limit": 10}
    elif upc:
        params = {"search": f'upc:"{upc}"', "limit": 5}
    else:
        return {"results": []}

    async with httpx.AsyncClient() as client:
        resp = await client.get(base, params=params)
        if resp.status_code != 200:
            return {"results": []}
        return resp.json()

# ──────────────────────────────────────────────
# S3 Upload (Akshita's integration)
# ──────────────────────────────────────────────

S3_BUCKET = os.environ.get("S3_BUCKET", "recallguard-dev-data")
S3_REGION = os.environ.get("AWS_REGION", "us-east-1")

@app.post("/api/upload-image")
async def api_upload_image(file: UploadFile = File(...)):
    """Upload a scan/product image to S3."""
    try:
        s3 = boto3.client("s3", region_name=S3_REGION)
        key = f"scans/{datetime.now().isoformat()}_{file.filename}"
        contents = await file.read()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=contents,
            ContentType=file.content_type or "application/octet-stream",
        )
        return {"url": f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
