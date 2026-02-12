# Food Recall Alert - AWS EC2 Deployment Guide

**What this does:** Deploys your Food Recall Alert app to AWS EC2 so it's accessible 24/7 from anywhere.

**Prerequisites:**
- AWS account with EC2 access
- GitHub repository cloned locally
- SSH key pair downloaded from AWS

**Estimated time:** 30-45 minutes

---

## Step 1: Launch EC2 Instance

1. **Log into AWS Console** → Navigate to **EC2**
2. Click **Launch Instance**

### Configure Instance:
- **Name:** `food-recall-app-production`
- **AMI (OS):** Ubuntu Server 24.04 LTS (Free tier eligible)
- **Instance Type:** `t2.micro` (Free tier)
- **Key Pair:**
  - Click "Create new key pair"
  - Name: `food-recall-keypair`
  - Type: RSA
  - Format: `.pem` (Mac/Linux) or `.ppk` (Windows)
  - **Download and save this file!** You'll need it
- **Network Settings:**
  - ✅ Allow SSH traffic from Anywhere
  - ✅ Allow HTTP traffic from the internet
  - ✅ Allow HTTPS traffic from the internet
- **Storage:** 8 GB (default is fine)

3. **Click "Launch Instance"**
4. **Note the Public IPv4 address** (e.g., `3.17.57.39`)

---

## Step 2: Connect to EC2 Instance

### On Mac/Linux:

```bash
# Move key to safe location
mv ~/Downloads/food-recall-keypair.pem ~/.ssh/
chmod 400 ~/.ssh/food-recall-keypair.pem

# Connect (replace with YOUR IP)
ssh -i ~/.ssh/food-recall-keypair.pem ubuntu@YOUR-EC2-IP
```

**Note:** When it asks about authenticity, type `yes` and press Enter.

You should see: `ubuntu@ip-xxx:~$`

---

## Step 3: Install System Dependencies

Copy and paste these commands:

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install Python, git, nginx
sudo apt install python3-pip python3-venv git nginx -y
```

**Wait for it to finish** (takes 2-3 minutes).

---

## Step 4: Clone Your Code from GitHub

### Option A: If Repository is Public

```bash
cd ~
git clone https://github.com/bryceloomis/Capstone-Recall-Alert.git
cd Capstone-Recall-Alert
```

### Option B: If Repository is Private

You'll need a Personal Access Token:

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Copy the token (starts with `ghp_...`)

```bash
cd ~
git clone https://YOUR-TOKEN@github.com/bryceloomis/Capstone-Recall-Alert.git
cd Capstone-Recall-Alert
```

---

## Step 5: Set Up Python Backend

```bash
# Navigate to backend
cd ~/Capstone-Recall-Alert/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install gunicorn (production server)
pip install gunicorn

# Test if backend works
python3 app.py
```

**You should see:**
```
Loaded 50 recalls and 224 products
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Press Ctrl+C to stop it.** Don't leave it running.

---

## Step 6: Create Systemd Service (Auto-Run Backend)

```bash
sudo nano /etc/systemd/system/food-recall-api.service
```

**Paste this exactly:**

```ini
[Unit]
Description=Food Recall Alert API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Capstone-Recall-Alert/backend
Environment="PATH=/home/ubuntu/Capstone-Recall-Alert/backend/venv/bin"
ExecStart=/home/ubuntu/Capstone-Recall-Alert/backend/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000

[Install]
WantedBy=multi-user.target
```

**Save and exit:**
- Press `Ctrl+O`, then `Enter` (save)
- Press `Ctrl+X` (exit)

**Start the service:**

```bash
sudo systemctl start food-recall-api
sudo systemctl enable food-recall-api
sudo systemctl status food-recall-api
```

**Look for:** `active (running)` in green. Press `q` to exit.

---

## Step 7: Configure Nginx (Web Server)

```bash
sudo nano /etc/nginx/sites-available/food-recall-app
```

**Paste this exactly:**

```nginx
server {
    listen 80;
    server_name _;

    # Serve frontend
    location / {
        root /home/ubuntu/Capstone-Recall-Alert/frontend;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Save and exit:** `Ctrl+O`, `Enter`, `Ctrl+X`

**Enable the configuration:**

```bash
sudo ln -s /etc/nginx/sites-available/food-recall-app /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
```

**Should see:** `test is successful`

**Restart nginx:**

```bash
sudo systemctl restart nginx
```

---

## Step 8: Fix File Permissions

**IMPORTANT:** Nginx needs permission to read your files.

```bash
chmod +x /home/ubuntu
chmod -R o+rX /home/ubuntu/Capstone-Recall-Alert
sudo systemctl restart nginx
```

---

## Step 9: Update Frontend Code (Do This On Your Local Computer)

**Exit SSH** (type `exit` or close terminal) and work on your local machine:

### Edit `frontend/index.html`:

Find this line (around line 134):
```javascript
const API_URL = 'http://localhost:8000';
```

Change to:
```javascript
const API_URL = '';
```

### Edit `frontend/scan.html`:

Find this line (around line 99):
```javascript
const API_URL = 'http://localhost:8000';
```

Change to:
```javascript
const API_URL = '';
```

### Commit and Push:

```bash
cd ~/path/to/food-recall-app
git add frontend/index.html frontend/scan.html
git commit -m "Update API URL for production deployment"
git push
```

---

## Step 10: Pull Changes on EC2

**SSH back into EC2:**

```bash
ssh -i ~/.ssh/food-recall-keypair.pem ubuntu@YOUR-EC2-IP
```

**Pull the changes:**

```bash
cd ~/Capstone-Recall-Alert
git pull
sudo systemctl restart nginx
```

---

## Step 11: Test Your Live App! 🎉

**Find your public IP:**

```bash
curl ifconfig.me
```

**Open in your browser:**
```
http://YOUR-PUBLIC-IP
```

**Test these:**
- Main app: `http://YOUR-IP`
- Barcode scanner: `http://YOUR-IP/scan.html`
- API: `http://YOUR-IP/api/health`

---

## Troubleshooting

### Backend Not Running:

```bash
sudo systemctl status food-recall-api
sudo journalctl -u food-recall-api -n 50 --no-pager
```

**Restart it:**
```bash
sudo systemctl restart food-recall-api
```

### Nginx Not Working:

```bash
sudo systemctl status nginx
sudo tail -n 30 /var/log/nginx/error.log
```

**Restart it:**
```bash
sudo systemctl restart nginx
```

### 500 Error:

```bash
# Check both logs
sudo journalctl -u food-recall-api -n 50 --no-pager
sudo tail -n 30 /var/log/nginx/error.log
```

### Permission Denied Errors:

```bash
chmod +x /home/ubuntu
chmod -R o+rX /home/ubuntu/Capstone-Recall-Alert
sudo systemctl restart nginx
```

---

## Updating Code After Deployment

**When you make changes to your code:**

1. **On your local computer:**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push
   ```

2. **On EC2:**
   ```bash
   ssh -i ~/.ssh/food-recall-keypair.pem ubuntu@YOUR-EC2-IP
   cd ~/Capstone-Recall-Alert
   git pull
   sudo systemctl restart food-recall-api
   sudo systemctl restart nginx
   ```

---

## Stopping/Starting the Instance

**To stop (save money when not using):**
- AWS Console → EC2 → Select instance → Instance State → Stop

**To start (wake it up):**
- AWS Console → EC2 → Select instance → Instance State → Start
- **Note:** Public IP may change unless you use an Elastic IP

**Everything auto-starts!** No need to SSH in or run commands.

---

## Cost Information

- **Free tier:** 750 hours/month of t2.micro (covers 24/7 for one instance)
- **After free tier:** ~$8.50/month
- **For 9-week capstone:** Likely $0 if within first year of AWS account

**Set up billing alerts!**
1. AWS Console → Billing Dashboard → Budgets
2. Create zero-spend or $5/month budget

---

## Team Access

**Share with your team:**
- The `.pem` key file (via Google Drive or Slack - keep it secure!)
- The public IP address
- This deployment guide

**Anyone with the key can SSH in:**
```bash
ssh -i ~/.ssh/food-recall-keypair.pem ubuntu@EC2-IP
```

---

## Quick Reference

**Public App URL:** `http://YOUR-EC2-IP`

**Common Commands:**
```bash
# Restart backend
sudo systemctl restart food-recall-api

# Restart nginx
sudo systemctl restart nginx

# Check backend logs
sudo journalctl -u food-recall-api -n 50 --no-pager

# Check nginx logs
sudo tail -n 30 /var/log/nginx/error.log

# Pull latest code
cd ~/Capstone-Recall-Alert && git pull
```

---

**You're done! Your app is live on the internet! 🚀**
