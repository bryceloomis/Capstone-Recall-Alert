# Project Breakdown — Recall Alert Capstone

**Timeline:** ~6–7 weeks remaining
**Team size:** 5
**Stack:** FastAPI (Python) backend · React/TypeScript frontend · PostgreSQL (AWS RDS) · AWS EC2 · AWS S3 · AWS Textract

---

## System Overview

```
User (mobile/browser)
        │
        ▼
  React Frontend  ──►  FastAPI Backend (EC2 :8000)
                              │
                   ┌──────────┼──────────────┐
                   ▼          ▼              ▼
                  RDS        S3         FDA API
              (PostgreSQL) (images)  (recall data)
                   │
              AWS Textract
             (receipt OCR)
```

**Data flow for a recall alert:**
1. Daily scheduler pulls FDA recall data → stores in `recalls` table
2. Joins against `user_carts` → writes rows to `alerts` table
3. Frontend polls `/api/alerts` → shows user their affected items

---

## Work Areas (Suggested Team Split)

---

### 🟢 Area 1 — Receipt Scanning Pipeline (1–2 people)
**Files:** `backend/receipt_scan.py` · `frontend/ReceiptScan.tsx` · `frontend/ReceiptReviewModal.tsx`

**What exists:**
- Basic Textract call to extract text from a receipt photo
- Early-stage fuzzy matching against Open Food Facts

**What needs to be built:**
- [ ] Improve fuzzy matching accuracy (e.g. RapidFuzz, better tokenization)
- [ ] Handle edge cases: store-brand items, abbreviations, multi-line items
- [ ] Let the user review + confirm matched items before adding to cart (`ReceiptReviewModal.tsx` already has a skeleton)
- [ ] Wire the confirmed items to `POST /api/user/cart` to save them to the DB
- [ ] Write 2–3 test receipts + expected output to validate matching

**Good starting point:**
```bash
# On EC2, activate venv and run the scanner manually
source ~/Capstone-Recall-Alert/backend/venv/bin/activate
python -c "from receipt_scan import scan_receipt; print(scan_receipt('test_receipt.jpg'))"
```

---

### 🔵 Area 2 — Recall Update Pipeline (1 person)
**Files:** `backend/recall_update.py`

**What exists:**
- Full FDA enforcement API fetch + upsert to `recalls` table
- Alert generation (joins `user_carts` vs `recalls`, writes to `alerts`)
- APScheduler running every 6 hours inside the FastAPI process
- USDA stub with `TODO` placeholders

**What needs to be built:**
- [ ] Implement `fetch_usda_recalls()` — USDA FSIS API: `https://www.fsis.usda.gov/fsis/api/recall/v/1`
- [ ] Implement `map_usda_to_db()` to normalize USDA records to our schema
- [ ] Add email notifications when alerts are generated (AWS SES or SendGrid)
- [ ] Verify the unique constraint exists on the DB:
  ```sql
  ALTER TABLE recalls
    ADD CONSTRAINT recalls_upc_date_unique UNIQUE (upc, recall_date);
  ```
- [ ] Test end-to-end: trigger refresh → check `recalls` table → check `alerts` table

**Manual trigger to test:**
```bash
curl -X POST http://localhost:8000/api/admin/refresh-recalls
```

---

### 🟡 Area 3 — Frontend / User Experience (1–2 people)
**Files:** `frontend/` — especially `V2*.tsx` components, `store.ts`, `api.ts`

**What exists:**
- Barcode scanning (working)
- Cart view, Home, Settings, Onboarding screens
- V2 components started (`V2Home`, `V2Scan`, `V2Groceries`, `V2Settings`, `V2Allergens`)

**What needs to be built:**
- [ ] Alert display: show users which cart items have been recalled (connect to `GET /api/alerts/:userId`)
- [ ] Finalize the receipt scanning UI: review modal → confirm → add to cart flow
- [ ] Allergen filtering UI (`V2Allergens.tsx` — let users flag allergens, warn them during scan)
- [ ] Polish V2 screens and make them the default (replace V1 components)
- [ ] Settings: manage allergen preferences, notification opt-in/out

**API endpoints to connect to:**
| Action | Endpoint |
|--------|----------|
| Get user alerts | `GET /api/alerts/{user_id}` |
| Mark alert viewed | `PATCH /api/alerts/{alert_id}/viewed` |
| Get cart | `GET /api/user/cart/{user_id}` |
| Add to cart | `POST /api/user/cart` |
| Remove from cart | `DELETE /api/user/cart/{user_id}/{upc}` |

---

### 🟠 Area 4 — Backend API & Database (1 person, likely Bryce)
**Files:** `backend/app.py` · `backend/database.py`

**What exists:**
- FastAPI app with barcode search, cart CRUD, recall refresh trigger
- Clean `database.py` with `execute_query()` helper

**What needs to be built / maintained:**
- [ ] `GET /api/alerts/{user_id}` endpoint (returns alerts with recall details joined)
- [ ] `PATCH /api/alerts/{alert_id}/viewed` endpoint
- [ ] Allergen filtering endpoint (or add filter params to search)
- [ ] Keep gunicorn running after any backend changes (see restart command in `TEAM_ACCESS_GUIDE.md`)
- [ ] Add the USDA recall constraint migration when Area 2 is ready

**DB Schema (current):**
```
users        → id, email, name, created_at
products     → id, upc, product_name, brand_name, category, ingredients, image_url
recalls      → id, upc, product_name, brand_name, recall_date, reason, severity, source
user_carts   → id, user_id, product_upc, product_name, brand_name, added_date
alerts       → id, user_id, recall_id, product_upc, created_at, viewed, email_sent
```

---

## Suggested 6-Week Timeline

| Week | Focus |
|------|-------|
| 1 | Everyone SSH in + set up local dev. Area 2: add USDA + test refresh. Area 3: wire alert display. |
| 2 | Area 1: improve fuzzy matching, test with real receipts. Area 3: receipt review UI. Area 4: alerts API. |
| 3 | Area 1: finalize receipt → cart flow. Area 2: email notifications. Area 3: allergen UI. |
| 4 | Integration: all pieces talking to each other end-to-end. Bug fixes. |
| 5 | User testing, edge cases, polish. Demo prep. |
| 6 | Final demo + writeup. |

---

## Shared Conventions

- **Never commit** `.env`, `*.pem`, or any file with DB passwords/API keys
- **Always work in the venv** on EC2: `source ~/Capstone-Recall-Alert/backend/venv/bin/activate`
- **Branch naming:** `feature/<your-name>/<short-description>` (e.g. `feature/alex/usda-recalls`)
- **PRs to `main`** — don't push directly to main
- **DB password and AWS creds** → ask Bryce

---

## Key Resources

| Resource | Link / Location |
|----------|----------------|
| SSH + JupyterLab setup | `official-prototype/TEAM_ACCESS_GUIDE.md` |
| DB schema & connections | `official-prototype/DATABASE_AND_CONNECTIONS.md` |
| FDA openFDA API docs | https://open.fda.gov/apis/food/enforcement/ |
| USDA FSIS API | https://www.fsis.usda.gov/fsis/api/recall/v/1 |
| Open Food Facts API | https://wiki.openfoodfacts.org/API |
| AWS Textract docs | https://docs.aws.amazon.com/textract/latest/dg/what-is.html |
