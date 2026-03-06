"""
app.py – FastAPI entry point for the Food Recall Alert API.

This file is intentionally thin. All route logic lives in sub-modules:

  barcode_routes.py  – POST /api/search, POST /api/products,
                       GET  /api/recalls, GET /api/recalls/check/{upc}
  user_routes.py     – Auth (register/login with allergens + diets),
                       profile CRUD, grocery cart
  receipt_scan.py    – POST /api/receipt/scan
  recall_update.py   – POST /api/admin/refresh-recalls  (+ APScheduler, FDA only)
  risk_routes.py     – GET /api/risk/scan/{upc} (primary barcode scan endpoint)
  llm_service.py     – Bedrock Claude Haiku: ingredient disambiguator + recall explainer
  user_alerts.py     – GET /api/alerts/{user_id}, PATCH /api/alerts/{alert_id}/viewed,
                       alert generation + email notification stub

To add a new area of functionality, create a new *_routes.py file with an
APIRouter, then register it below with app.include_router().
"""

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import test_connection, execute_query

# Sub-module routers
from barcode_routes import router as barcode_router
from receipt_scan   import router as receipt_router
from recall_update  import router as recall_router, start_recall_scheduler
from risk_routes    import router as risk_router
from user_routes    import router as user_router
from user_alerts    import router as user_alerts_router


# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Food Recall Alert API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(barcode_router)
app.include_router(user_router)
app.include_router(receipt_router)
app.include_router(recall_router)
app.include_router(risk_router)
app.include_router(user_alerts_router)


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    """Start the recall refresh background scheduler when the server launches."""
    start_recall_scheduler()


# ── Core / utility endpoints ───────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "message": "Food Recall Alert API",
        "version": "0.3.0",
        "modules": {
            "barcode_routes.py": "Product search, manual submit, recall listing",
            "user_routes.py":    "Auth (register/login), allergen & diet profile, cart",
            "receipt_scan.py":   "Receipt OCR + product matching",
            "recall_update.py":  "FDA recall refresh (auto every 6h + manual trigger)",
            "risk_routes.py":    "Barcode scan with full risk analysis + LLM disambiguation",
            "llm_service.py":    "AWS Bedrock Claude Haiku: ingredient disambiguator + recall explainer",
            "user_alerts.py":    "User alerts"

        },
        "endpoints": {
            # ── Primary scan workflow ─────────────────────────────────
            "/api/risk/scan/{upc}":         "GET  – barcode scan → verdict + explanation (main endpoint)",
            # ── User auth & profile ───────────────────────────────────
            "/api/users/register":          "POST – create account (with allergens & diets)",
            "/api/users/login":             "POST – sign in (returns full profile)",
            "/api/users/{user_id}/profile": "GET/PATCH – fetch or update allergen & diet profile",
            # ── Product & recall data ─────────────────────────────────
            "/api/search":                  "POST – search by UPC or name",
            "/api/products":                "POST – manually submit a product",
            "/api/recalls":                 "GET  – all recalls (newest first)",
            "/api/recalls/check/{upc}":     "GET  – recall status for one UPC",
            # ── Cart ──────────────────────────────────────────────────
            "/api/user/cart/{user_id}":     "GET  – user's saved grocery list",
            "/api/user/cart":               "POST – add item to grocery list",
            # ── Receipt & admin ───────────────────────────────────────
            "/api/receipt/scan":            "POST – receipt photo OCR + matching",
            "/api/admin/refresh-recalls":   "POST – manual recall refresh",
            # ── Health ────────────────────────────────────────────────
            "/api/health":                  "GET  – health check (live DB counts)",
            # Alerts
            "/api/alerts/{user_id}":        "GET  – user's recall alerts",
            "/api/alerts/{alert_id}/viewed":"PATCH – mark alert as viewed",
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


@app.get("/api/db-test")
async def db_test():
    """Verify RDS connection and return row counts. Remove before production."""
    if not test_connection():
        raise HTTPException(status_code=503, detail="Cannot connect to database.")

    tables  = ["users", "products", "recalls", "user_carts"]
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
        "database":     "food_recall",
        "tables":       summary,
    }


# ── Run locally ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)