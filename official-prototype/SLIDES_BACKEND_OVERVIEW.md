# Recall Alert — Backend Overview
### Slide Deck Content

---

## Slide 1 — Title

**Recall Alert**
Backend Architecture & Core Processes

*How the app works under the hood*

---

## Slide 2 — System Architecture (diagram slide)

```
 User (browser / phone)
         │
         ▼  HTTPS (port 443)
    ┌─────────────┐
    │    nginx    │  ← serves built React app + proxies /api/* to FastAPI
    └──────┬──────┘
           │ port 8000
           ▼
    ┌─────────────┐        ┌───────────────────┐
    │   FastAPI   │ ──────▶│  AWS RDS Postgres │
    │  (gunicorn) │        │  (food_recall DB) │
    └──────┬──────┘        └───────────────────┘
           │
     ┌─────┼──────────┐
     ▼     ▼          ▼
  AWS S3  FDA API  AWS Textract
(images) (recalls) (receipt OCR)
```

**Key point:** The frontend never touches the database directly. Everything goes through the FastAPI backend.

---

## Slide 3 — What Happens When the Server Starts

When gunicorn starts `app.py`, three things happen immediately:

1. **Routes are registered** — core endpoints + receipt_scan.py + recall_update.py routers all mount onto the app
2. **CORS is enabled** — allows the React frontend to call the API from any origin
3. **Recall scheduler fires** — `start_recall_scheduler()` is called on startup:
   - Runs a **full FDA recall refresh immediately**
   - Then schedules it to repeat **every 6 hours** in a background thread

> The server is never "stale" — the first thing it does on boot is pull fresh recall data.

---

## Slide 4 — The Five Database Tables

| Table | What it stores |
|-------|---------------|
| `users` | Accounts — email, name, hashed password |
| `products` | Product catalog — UPC, name, brand, ingredients |
| `recalls` | FDA/USDA recall records — UPC, reason, severity, date |
| `user_carts` | Each user's saved grocery list (UPC + product info) |
| `alerts` | When a user's cart item matches a recall — triggers notification |

**How they connect:**
- A recall is matched to a cart item via **UPC**
- An alert is created when `recalls.upc` = `user_carts.product_upc` for the same user
- Alerts track whether the user has **seen** it (`viewed`) and whether an **email was sent** (`email_sent`)

---

## Slide 5 — Barcode Scanning Flow

```
User scans barcode
       │
       ▼
POST /api/search  { upc: "037600437301" }
       │
       ├─▶ SELECT * FROM products WHERE upc = ?
       │         └─ Found: return product info
       │         └─ Not found: 404
       │
       └─▶ SELECT * FROM recalls WHERE upc = ?
                 └─ Match found: is_recalled = true + recall details
                 └─ No match:   is_recalled = false
```

**Response includes:**
- Product name, brand, category, ingredients
- `is_recalled: true/false`
- If recalled: reason, severity (Class I/II/III), recall date, firm name

**The frontend** shows a green ✅ or red ⚠️ based on `is_recalled`.

---

## Slide 6 — Receipt Scanning Flow

```
User photographs receipt
         │
         ▼
POST /api/receipt/scan  (image upload)
         │
         ▼
1. PIL converts image → JPEG  (Textract only accepts JPEG/PNG)
         │
         ▼
2. AWS Textract AnalyzeExpense
   → extracts structured line items (ITEM fields)
   → fallback: DetectDocumentText if no line items found
         │
         ▼
3. Regex cleaner strips prices, quantities, store codes
   → turns "ORG ALM BTR 16OZ $6.99" → "ORG ALM BTR"
         │
         ▼
4. Product lookup (for each cleaned item):
   a) Search RDS products table first  (fast, free)
   b) Fall back to Open Food Facts v2 API if not in DB
         │
         ▼
5. Recall check: matched UPCs → cross-reference recalls table
         │
         ▼
Response: { matched: [...], unmatched: [...], total_lines: N }
   → Frontend shows review modal → user confirms → items added to cart
```

**Current status:** Steps 1–5 are built. The review → confirm → save to cart flow in the frontend is in progress.

---

## Slide 7 — Recall Update Pipeline (the daily job)

```
Runs on startup + every 6 hours (APScheduler background thread)
Also triggerable manually: POST /api/admin/refresh-recalls

          ┌─────────────────────────┐
          │   fetch_fda_recalls()   │  ← hits openFDA enforcement API
          │   fetch_usda_recalls()  │  ← USDA FSIS (stub — TODO)
          └────────────┬────────────┘
                       │ raw records
                       ▼
              map_fda_to_db()  /  map_usda_to_db()
              → normalize fields, extract UPC from code_info
                       │
                       ▼
              upsert_recall()
              → INSERT ... ON CONFLICT (upc, recall_date) DO UPDATE
              → no duplicates, existing recalls get updated
                       │
                       ▼
         generate_alerts_for_new_recalls()
         → JOIN user_carts vs recalls ON upc
         → INSERT into alerts for any new matches
         → (email notification goes here — in progress)
```

**Result:** Every 6 hours, the DB has fresh recall data and affected users have alerts waiting for them.

---

## Slide 8 — User Cart & Alerts

**Adding to cart:**
```
POST /api/user/cart  { user_id, upc, product_name, brand_name }
→ INSERT INTO user_carts ... ON CONFLICT DO NOTHING
```

**Reading the cart:**
```
GET /api/user/cart/{user_id}
→ returns all saved items with add date
```

**How alerts are generated (automatic):**
- Every recall refresh, `generate_alerts_for_new_recalls()` runs a JOIN:
  ```sql
  SELECT uc.user_id, r.id AS recall_id
  FROM user_carts uc
  JOIN recalls r ON uc.product_upc = r.upc
  LEFT JOIN alerts a ON a.user_id = uc.user_id AND a.recall_id = r.id
  WHERE a.id IS NULL   -- only new matches
  ```
- Creates an alert row for every user who has a recalled product in their cart

**What's still needed:**
- `GET /api/alerts/{user_id}` endpoint (reads alerts back to the frontend)
- Email notification when the alert is created

---

## Slide 9 — Auth (Login & Registration)

**Simple session-less auth:**

```
POST /api/users/register  { name, email, password }
→ bcrypt hashes the password
→ INSERT INTO users (name, email, password_hash)
→ returns user id + name + email

POST /api/users/login  { email, password }
→ fetch user by email
→ bcrypt.checkpw(submitted_password, stored_hash)
→ returns user object (id, name, email)
```

**The frontend** stores the `user_id` locally and passes it with every cart request.

> ⚠️ Note: There's no JWT or session token — anyone who knows a `user_id` can read that cart. Fine for a capstone demo, worth noting for a production system.

---

## Slide 10 — What's Running on the Server Right Now

| Process | How it runs | What it does |
|---------|-------------|--------------|
| **nginx** | systemd service | Serves React app on port 443 (HTTPS), proxies `/api/*` to FastAPI |
| **gunicorn** (4 workers) | daemon, PID at `/tmp/gunicorn.pid` | Runs FastAPI app on port 8000 |
| **APScheduler** | background thread inside gunicorn | Triggers recall refresh every 6 hours |
| **JupyterLab** | tmux session (`jupyter`) | Port 8888, SSH tunnel only |

**Restart gunicorn after a backend change:**
```bash
kill $(cat /tmp/gunicorn.pid) && sleep 1
cd ~/Capstone-Recall-Alert/backend && source venv/bin/activate
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app \
  --bind 0.0.0.0:8000 --daemon --pid /tmp/gunicorn.pid
```

---

## Slide 11 — What's Left to Build

| Feature | Who | Status |
|---------|-----|--------|
| `GET /api/alerts/{user_id}` endpoint | Backend | ❌ Not built |
| Frontend alert display | Frontend | ❌ Not built |
| Receipt review → confirm → save to cart | Frontend | 🔶 In progress |
| USDA recall source | Backend | 🔶 Stub only |
| Email notifications (AWS SES) | Backend | ❌ Not built |
| Allergen filtering UI | Frontend | 🔶 In progress |

---

## Slide 12 — Live App

| | |
|-|-|
| **App URL** | https://54.210.208.14 *(click through SSL warning)* |
| **API health** | https://54.210.208.14/api/health |
| **API docs** | http://54.210.208.14:8000/docs |
| **Trigger recall refresh** | `curl -X POST http://54.210.208.14/api/admin/refresh-recalls` |

