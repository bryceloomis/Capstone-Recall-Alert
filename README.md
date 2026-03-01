# Recall Alert

A mobile-friendly web app that lets users scan grocery barcodes and receipt photos to check for FDA food recalls. Users get alerts when something in their saved grocery list is recalled.

**Live app:** https://54.210.208.14 *(click through SSL warning)*  
**API docs:** http://54.210.208.14:8000/docs

---

## Repo Structure

```
Capstone-Recall-Alert/
├── backend/        FastAPI app (app.py, database.py, recall_update.py, receipt_scan.py)
├── frontend/       React + TypeScript (Vite) — the mobile UI
└── misc/           Docs, DB setup scripts, sample data
    ├── db_setup/   create_tables.sql, seed_data.sql
    ├── data/       sample CSVs and receipt images
    └── *.md        Team guides and architecture notes
```

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + gunicorn (uvicorn workers) |
| Frontend | React + TypeScript + Vite + Tailwind |
| Database | PostgreSQL on AWS RDS |
| File storage | AWS S3 |
| OCR | AWS Textract (receipt scanning) |
| Product data | Open Food Facts API (with RDS cache) |
| Recall data | openFDA enforcement API (refreshed every 6 hrs) |
| Server | AWS EC2 (Ubuntu) + nginx |

---

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DB creds
uvicorn app:app --reload
```

API runs at http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI runs at http://localhost:5173

---

## Team & Docs

- `misc/TEAM_ACCESS_GUIDE.md` — SSH access, JupyterLab tunnel, EC2 details
- `misc/PROJECT_BREAKDOWN.md` — 4 work areas and 6-week timeline
- `misc/SLIDES_BACKEND_OVERVIEW.md` — architecture slide deck content
- `misc/DATABASE_AND_CONNECTIONS.md` — RDS connection details
- `misc/db_setup/` — schema SQL and seed data
