# Backend App (Merged)

This is the **complete working backend** — teammate's original FastAPI app + Akshita's FDA recall and S3 upload integrations.

## What's included

| Source | What |
|--------|------|
| Teammate's `backend/app.py` | Core API: search, cart, recalls, health check |
| Akshita's `fda_recalls.py` | `GET /api/recalls/fda` — queries FDA openFDA |
| Akshita's `s3_upload.py` | `POST /api/upload-image` — uploads to S3 |

## Run locally

```bash
cd official-prototype/backend-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Server starts at **http://localhost:8000**. The app looks for CSV data files in `../data/`.

## Then run the frontend

```bash
cd official-prototype/frontend
npm install
npm run dev
```

Opens at **http://localhost:5173**, proxies `/api/*` to the backend.
