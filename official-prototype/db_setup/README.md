# Database Setup

Run these two files in order on any fresh PostgreSQL database to get up and running.

## Steps

### 1. Create the RDS instance (AWS Console)
- Engine: **PostgreSQL 17**
- DB name: `food_recall`
- Master username: `postgres`
- Choose a strong password and save it — update the `.env` file on EC2 with the new host + password

### 2. Run the schema
Connect to your new RDS (from EC2 or DBeaver) and run:
```bash
psql -h <new-rds-host> -U postgres -d food_recall -f create_tables.sql
```

### 3. Load the seed data
```bash
psql -h <new-rds-host> -U postgres -d food_recall -f seed_data.sql
```

### 4. Update the EC2 `.env`
```bash
# On EC2:
nano ~/Capstone-Recall-Alert/backend/.env
# Update DB_HOST and DB_PASSWORD to the new RDS values
```

### 5. Restart gunicorn
```bash
kill $(cat /tmp/gunicorn.pid) && sleep 1
cd ~/Capstone-Recall-Alert/backend && source venv/bin/activate
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app \
  --bind 0.0.0.0:8000 --daemon --pid /tmp/gunicorn.pid
```

### 6. Verify
```bash
curl http://localhost:8000/api/health
```

---

## Schema Changes from Original (bugs fixed)

| Table | Change | Reason |
|-------|--------|--------|
| `users` | Added `password_hash` | Required for login — was missing from original |
| `recalls` | Added `firm_name`, `distribution_pattern` | `recall_update.py` inserts these — missing caused silent failures |
| `recalls` | Added `UNIQUE(upc, recall_date)` constraint | Required for `ON CONFLICT` upsert in `recall_update.py` |
| `recalls` | `upc` widened to `VARCHAR(50)` | FDA synthetic keys like `FDA-R-001-2024` exceed 13 chars |
| `alerts` | Renamed `sent_at` → `created_at` | `recall_update.py` inserts into `created_at` — mismatch caused silent failures |
