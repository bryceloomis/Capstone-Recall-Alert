# Team Access Guide — Recall Alert

This guide covers how to SSH into the EC2 instance and access JupyterLab.
**Never commit the `.pem` key file to the repo.**

---

## 1. SSH into the EC2 Instance

### Prerequisites
- The `.pem` key file — download it here (UC Berkeley Google account required):
  **[⬇ Download food-recall-keypair.pem](https://drive.google.com/file/d/1GyEW8VgK9Uc8H7Rp8y4_1K4FazIZYPuV/view?usp=sharing)**
- On **Mac/Linux**: no extra software needed
- On **Windows**: use [Git Bash](https://gitforwindows.org/) or [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) — both support the same commands below

### One-time setup (Mac/Linux)
```bash
# Fix permissions on the key file (required — SSH will refuse to use it otherwise)
chmod 400 ~/Downloads/food-recall-keypair.pem
```

### Connect
```bash
ssh -i ~/Downloads/food-recall-keypair.pem ubuntu@54.210.208.14
```

If you saved the `.pem` somewhere other than `~/Downloads`, replace the path accordingly.

### What you'll see
Once connected, your prompt will change to something like:
```
ubuntu@ip-172-31-xx-xx:~$
```
You're now on the EC2 server. The project lives at:
```
~/Capstone-Recall-Alert/
```

---

## 2. Project Layout on EC2

```
~/Capstone-Recall-Alert/
├── backend/
│   ├── app.py              ← FastAPI main app (running via gunicorn on :8000)
│   ├── database.py         ← DB connection helpers
│   ├── recall_update.py    ← FDA recall fetch + alert pipeline
│   ├── receipt_scan.py     ← AWS Textract receipt scanner
│   ├── requirements.txt
│   └── venv/               ← Python virtual environment (all packages here)
├── frontend/               ← React/TypeScript source
├── official-prototype/     ← Current working prototype
└── data/                   ← CSVs, test data
```

---

## 3. Access JupyterLab (via SSH Tunnel)

JupyterLab runs on the EC2 at `localhost:8888` — it is **not** exposed to the internet.
You access it by forwarding the port through your SSH connection.

### Step 1 — Open the SSH tunnel
In a terminal, run:
```bash
ssh -i ~/Downloads/food-recall-keypair.pem -L 8888:localhost:8888 ubuntu@54.210.208.14
```
The `-L 8888:localhost:8888` flag forwards port 8888 from the EC2 to your machine.
**Keep this terminal open** — closing it closes the tunnel.

### Step 2 — Open JupyterLab in your browser
While the SSH tunnel is open, go to:
```
http://localhost:8888
```
Enter the password when prompted:
```
recall2026
```

### Step 3 — Done
You'll see the JupyterLab interface with the full `Capstone-Recall-Alert/` project folder.

> **Note:** If JupyterLab isn't running (e.g. after a server restart), SSH in normally and run:
> ```bash
> bash ~/start_jupyter.sh
> ```

---

## 4. Running Code on the EC2 (Virtual Environment)

All Python packages (FastAPI, psycopg2, boto3, Pillow, etc.) are in the project venv.
Always activate it before running Python scripts:

```bash
source ~/Capstone-Recall-Alert/backend/venv/bin/activate
```

Your prompt will change to show `(venv)`. Then run scripts normally:
```bash
python recall_update.py
python receipt_scan.py
```

To deactivate when done:
```bash
deactivate
```

### Install a new package
```bash
source ~/Capstone-Recall-Alert/backend/venv/bin/activate
pip install <package-name>
pip freeze > ~/Capstone-Recall-Alert/backend/requirements.txt   # update requirements
```

---

## 5. Checking the Live Backend

The FastAPI backend is served by gunicorn and accessible at:
```
http://54.210.208.14:8000
```
Or internally on EC2:
```
http://localhost:8000
```

### Useful commands
```bash
# Check if gunicorn is running
ps aux | grep gunicorn

# View backend logs (if using journald)
journalctl -u gunicorn -f

# Restart gunicorn (if you changed app.py)
kill $(cat /tmp/gunicorn.pid) && sleep 1
cd ~/Capstone-Recall-Alert/backend
source venv/bin/activate
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app \
  --bind 0.0.0.0:8000 --daemon --pid /tmp/gunicorn.pid
```

### Manually trigger a recall refresh
```bash
curl -X POST http://localhost:8000/api/admin/refresh-recalls
```

---

## 6. Database Access (RDS)

The backend connects automatically using environment variables. If you need direct DB access (e.g. DBeaver or psql):

| Setting  | Value |
|----------|-------|
| Host     | `food-recall-db.cqjm48os4obt.us-east-1.rds.amazonaws.com` |
| Port     | `5432` |
| Database | `food_recall` |
| Username | `postgres` |
| Password | **Ask Bryce** — never commit this |

Your IP may need to be added to the RDS security group. Ask Bryce to add it.

```bash
# Connect via psql from inside EC2 (already whitelisted)
source ~/Capstone-Recall-Alert/backend/venv/bin/activate
python -c "from database import test_connection; test_connection()"
```

---

## 7. Quick Reference

| Task | Command |
|------|---------|
| SSH into EC2 | `ssh -i ~/Downloads/food-recall-keypair.pem ubuntu@54.210.208.14` |
| SSH + Jupyter tunnel | `ssh -i ~/Downloads/food-recall-keypair.pem -L 8888:localhost:8888 ubuntu@54.210.208.14` |
| Start JupyterLab | `bash ~/start_jupyter.sh` |
| Activate venv | `source ~/Capstone-Recall-Alert/backend/venv/bin/activate` |
| Trigger recall refresh | `curl -X POST http://localhost:8000/api/admin/refresh-recalls` |
| Check running services | `ps aux | grep -E 'gunicorn|jupyter'` |
| View tmux sessions | `tmux ls` |
| Attach to Jupyter tmux | `tmux attach -t jupyter` |
