# Database & Connections Reference

This doc aligns the **official prototype** with the team’s real infrastructure. **Never commit DB passwords or secrets to the repo.** Get credentials from the team lead (Bryce).

---

## 1. PostgreSQL (AWS RDS)

The backend connects to **AWS RDS PostgreSQL** for products, recalls, users, and carts.

| Setting   | Value (for backend config only) |
|----------|----------------------------------|
| Host     | `food-recall-db.cqjm48os4obt.us-east-1.rds.amazonaws.com` |
| Port     | `5432` |
| Database | `food_recall` |
| Username | `postgres` |
| Password | **Ask team lead** — do not put in code or commit |

- Direct access (e.g. DBeaver): see the team’s **Database Access Guide**; your IP may need to be added to the RDS security group.
- The **FastAPI backend** (not this React app) holds the connection; the frontend only talks to the backend via `VITE_API_URL`.

### Tables (from team schema)

| Table       | Purpose |
|------------|---------|
| `users`    | id, email, name, created_at |
| `products` | id, upc, product_name, brand_name, category, ingredients, image_url |
| `recalls`  | id, upc, product_name, brand_name, recall_date, reason, source (FDA/USDA) |
| `user_carts` | id, user_id, product_upc, product_name, brand_name, added_date |
| `alerts`   | id, user_id, recall_id, product_upc, sent_at, viewed, email_sent |

### How the prototype maps to the DB

| Frontend type / API      | Backend / DB |
|--------------------------|--------------|
| `Product`                | `products` row + recall join → `is_recalled`, `recall_info` |
| `RecallInfo`            | `recalls` (reason, recall_date, etc.); hazard class can be derived or stored |
| `CartItem`              | `user_carts` row (upc → product_upc, etc.) |
| `UserCart`              | `user_carts` for a given `user_id` |
| `POST /api/search`      | Look up `products` (by upc/name), join `recalls` |
| `GET /api/user/cart/:id`| Query `user_carts` by user_id |
| `POST /api/user/cart`   | Insert into `user_carts` |
| `DELETE /api/user/cart/:userId/:upc` | Delete from `user_carts` |

---

## 2. S3 (recallguard-dev-data)

- **Bucket:** `recallguard-dev-data` (us-east-1).
- **Use:** Scan/product images (e.g. under `scans/`). Backend snippet: `backend/s3_upload.py` (uses env `S3_BUCKET`, default `recallguard-dev-data`).
- **Frontend:** No direct S3 access; uploads go through the backend (`POST /api/upload-image` when you add that route).

---

## 3. Food Recall API (backend → FDA/USDA)

- **Frontend** calls the **FastAPI backend** at `VITE_API_URL` (e.g. `http://localhost:8000` or your EC2 URL).
- **Backend** is responsible for:
  - Reading/writing **RDS** (products, recalls, user_carts).
  - Optionally calling **FDA openFDA** (snippet: `backend/fda_recalls.py` → `GET /api/recalls/fda`).
- **Frontend** uses:
  - `POST /api/search` — product lookup (backend + Open Food Facts fallback in this repo).
  - `GET /api/recalls` — list recalls.
  - `GET /api/recalls/fda` — if backend exposes it.
  - Cart: `GET/POST/DELETE /api/user/cart/...`

---

## 4. Checklist: “Is the prototype connected?”

| Check | Where |
|-------|--------|
| Backend uses RDS | Backend config: host, db `food_recall`, user, **password from team lead**. |
| Backend uses S3  | Backend env `S3_BUCKET=recallguard-dev-data` (or default in snippet). |
| Frontend talks to backend | In `frontend`, set `.env`: `VITE_API_URL=<your FastAPI URL>`. |
| FDA recalls (optional) | Backend merges `fda_recalls.py` and exposes `GET /api/recalls/fda`. |

**Security:** Do not commit `.env` or any file containing the DB password or API keys. Use `.env.example` with placeholders only.
