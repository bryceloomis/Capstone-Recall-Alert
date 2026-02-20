# Official Prototype

This folder contains the **official prototype** for the Food Recall Alert app: the React frontend and backend integration snippets, kept separate from the main repo layout so the team can review and merge when ready.

## Structure

| Folder | Contents |
|--------|----------|
| **`frontend/`** | React 18 + TypeScript + Vite app. MVP (search, scan, My Groceries, Settings) and V2: Ingredient preferences step-through demo. Run with `npm install` then `npm run dev` from inside `frontend/`. |
| **`backend/`** | Snippets to merge into the existing FastAPI app: FDA recall API (`fda_recalls.py`), S3 upload (`s3_upload.py`). See `backend/README.md`. |

## Quick start (frontend)

**Run the app from inside the frontend folder** (the repo root no longer contains the app):

```bash
cd official-prototype/frontend
npm install
npm run dev
```

Then open the URL Vite prints (e.g. **http://localhost:5173**). Set `VITE_API_URL` in `.env` if your backend is elsewhere (default `http://localhost:8000`).

## Connections (RDS, S3, Food Recall API)

The prototype is designed to work with the team’s **AWS RDS** (`food_recall` DB), **S3** bucket (`recallguard-dev-data`), and FastAPI backend. For how each piece connects and how our types map to the DB schema, see **[DATABASE_AND_CONNECTIONS.md](DATABASE_AND_CONNECTIONS.md)**. Never commit DB passwords or API keys; get credentials from the team lead. The app uses **ingredient preferences** (ingredients to avoid) only; it does not give medical or allergy advice—see the disclaimer on the Home page.

## Pushing to the team repo

This folder is intended to live inside the main **Capstone-Recall-Alert** repo (e.g. at the root level as `official-prototype/`). Clone the team repo, add this folder, commit, and push. The existing `backend/`, `data/`, and `frontend/` at repo root stay as-is; this prototype sits alongside them.
