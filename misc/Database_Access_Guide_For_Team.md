# Food Recall Alert - Database Access Guide

**Last Updated:** February 23, 2026
**For:** Capstone Team Members
**Purpose:** Access our PostgreSQL database using DBeaver

---

## What You're Getting Access To

Our project uses **AWS RDS PostgreSQL** to store:
- Product information (UPCs, names, brands)
- Food recall data (FDA/USDA recalls)
- User accounts and shopping carts
- Alert history

---

## Step 1: Download and Install DBeaver

### For Mac Users:
1. Go to https://dbeaver.io/download/
2. Click **"macOS"**
3. Download the `.dmg` file
4. Open the `.dmg` file
5. Drag DBeaver to your Applications folder
6. Open DBeaver from Applications

### For Windows Users:
1. Go to https://dbeaver.io/download/
2. Click **"Windows (installer)"**
3. Download and run the installer
4. Follow installation prompts (just click Next/Install)
5. Launch DBeaver

### For Linux Users:
1. Go to https://dbeaver.io/download/
2. Choose your distribution (Ubuntu/Debian/Fedora)
3. Follow the installation instructions for your distro

---

## Step 2: Get the Required Files from the Team Lead

You'll need **two things** from Bryce before you can connect:

| What | Details |
|------|---------|
| **SSH key file** | `food-recall-keypair.pem` — the private key for the EC2 server |
| **DB password** | The PostgreSQL password for the `postgres` user |

**⚠️ IMPORTANT:** Keep both of these secure! Never commit them to GitHub or share publicly.

---

## Step 3: Connect to Database in DBeaver

> Our RDS database lives inside a **private AWS network** — it cannot be reached directly from your laptop. DBeaver must tunnel through our EC2 server first. The setup has two parts: the SSH tunnel, then the database credentials.

### 3a. Create a New Connection

1. **Open DBeaver**
2. **Create New Connection:**
   - Click **Database** → **New Database Connection**
   - OR click the plug icon (🔌) in the toolbar
3. **Select PostgreSQL** and click **Next**
4. **Enter Connection Details** on the **Main** tab:

   | Field | Value |
   |-------|-------|
   | Host | `food-recall-db.cqjm48os4obt.us-east-1.rds.amazonaws.com` |
   | Port | `5432` |
   | Database | `food_recall` |
   | Username | `postgres` |
   | Password | *(ask team lead)* |

   **☑️ Check** "Save password locally"

---

### 3b. Configure the SSH Tunnel ⬅️ *Required — don't skip this!*

> Without this step the connection will time out. The database is in a private network only reachable through the EC2 server.

1. In the same connection dialog, click the **SSH** tab at the top
2. **Check** "Use SSH Tunnel"
3. Fill in the SSH settings:

   | Field | Value |
   |-------|-------|
   | Host/IP | `54.210.208.14` |
   | Port | `22` |
   | Username | `ubuntu` |
   | Authentication | **Public Key** |
   | Private Key | Click **Browse** → select your `food-recall-keypair.pem` file |

4. Click **Test tunnel configuration** — it should say **Connected** ✅

   > **Mac/Linux note:** If you get a "bad permissions" error on the `.pem` file, open Terminal and run:
   > ```bash
   > chmod 600 ~/Downloads/food-recall-keypair.pem
   > ```
   > Then try the tunnel test again.

---

### 3c. Test and Finish

1. Go back to the **Main** tab
2. Click **Test Connection**
   - If prompted to download PostgreSQL drivers, click **Download**, wait, then test again
   - Should say **"Connected"** ✅
3. Click **Finish**

You should now see the database in the left sidebar!

---

## Step 4: Explore the Database

In the left sidebar, expand:
```
PostgreSQL
  └─ food_recall
      └─ Schemas
          └─ public
              └─ Tables
                  ├─ alerts
                  ├─ products
                  ├─ recalls
                  ├─ user_carts
                  └─ users
```

**Double-click any table** to see its data!

---

## Step 5: Run Your First Query

### Open SQL Editor:
- Click the **SQL Editor** button (top toolbar)
- OR press **Ctrl + `** (Mac: **Cmd + `**)

### Try These Queries:

**1. View all recalls:**
```sql
SELECT * FROM recalls;
```

**2. Count how many products we have:**
```sql
SELECT COUNT(*) as total_products FROM products;
```

**3. Find recalls from a specific brand:**
```sql
SELECT * FROM recalls
WHERE brand_name = '365 Everyday Value';
```

**4. See database statistics:**
```sql
SELECT
    'Recalls' as table_name, COUNT(*) as count FROM recalls
UNION ALL
SELECT 'Products', COUNT(*) FROM products
UNION ALL
SELECT 'Users', COUNT(*) FROM users
UNION ALL
SELECT 'User Carts', COUNT(*) FROM user_carts;
```

**To run a query:**
- Highlight the SQL code
- Press **Ctrl + Enter** (Mac: **Cmd + Enter**)
- Results appear below!

---

## Common Tasks

### View Data
- Double-click any table → see all rows
- Use filters on columns to search

### Edit Data (Be Careful!)
- Double-click a cell to edit
- Press **Ctrl + S** to save changes
- ⚠️ Changes are permanent!

### Add New Data
```sql
-- Example: Add a new recall
INSERT INTO recalls (upc, product_name, brand_name, recall_date, reason, source)
VALUES ('123456789012', 'Test Product', 'Test Brand', '2026-02-17', 'Testing', 'FDA');
```

### Export Data
- Right-click a table
- Select **Export Data**
- Choose format (CSV, Excel, JSON)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| SSH tunnel test fails | Make sure you're using `food-recall-keypair.pem` (not `UCB.pem` or another key). On Mac/Linux run `chmod 600 food-recall-keypair.pem` first. |
| Connection times out after SSH succeeds | Double-check the RDS hostname and database name are spelled exactly as shown |
| "Password authentication failed" | Ask Bryce for the current password — don't guess |
| "Bad permissions" on .pem file | Run `chmod 600 ~/path/to/food-recall-keypair.pem` in Terminal |
| DBeaver asks to download drivers | Click Download and wait — this is normal on first use |
| Drivers won't download | Click **Database** → **Driver Manager** → find PostgreSQL → click **Download/Update** |

---

## Security Best Practices

✅ **DO:**
- Save password in DBeaver (it's encrypted locally)
- Test queries on small datasets first
- Use `WHERE` clauses to limit changes
- Ask before making major changes

❌ **DON'T:**
- Share the password or `.pem` file publicly
- Commit connection details or keys to GitHub
- Delete data without checking with the team
- Run `DELETE` or `UPDATE` without a `WHERE` clause

---

## Useful SQL Cheat Sheet

### Select/Filter
```sql
-- Get all records
SELECT * FROM recalls;

-- Filter by condition
SELECT * FROM recalls WHERE brand_name = 'Whole Foods';

-- Search with pattern
SELECT * FROM products WHERE product_name LIKE '%Almond%';

-- Sort results
SELECT * FROM recalls ORDER BY recall_date DESC;

-- Limit results
SELECT * FROM products LIMIT 10;
```

### Join Tables
```sql
-- Find users with recalled items in their cart
SELECT u.email, uc.product_name, r.reason
FROM users u
JOIN user_carts uc ON u.id = uc.user_id
JOIN recalls r ON uc.product_upc = r.upc;
```

### Count/Group
```sql
-- Count by brand
SELECT brand_name, COUNT(*) as count
FROM products
GROUP BY brand_name
ORDER BY count DESC;
```

---

## Our Database Schema

### users
| Column | Type | Notes |
|--------|------|-------|
| id | integer | Primary key |
| email | text | Unique |
| name | text | |
| created_at | timestamp | |

### products
| Column | Type | Notes |
|--------|------|-------|
| id | integer | Primary key |
| upc | text | Unique |
| product_name | text | |
| brand_name | text | |
| category | text | |
| ingredients | text[] | Array |
| image_url | text | |

### recalls
| Column | Type | Notes |
|--------|------|-------|
| id | integer | Primary key |
| upc | text | |
| product_name | text | |
| brand_name | text | |
| recall_date | date | |
| reason | text | |
| source | text | FDA or USDA |

### user_carts
| Column | Type | Notes |
|--------|------|-------|
| id | integer | Primary key |
| user_id | integer | → users(id) |
| product_upc | text | |
| product_name | text | |
| brand_name | text | |
| added_date | timestamp | |

### alerts
| Column | Type | Notes |
|--------|------|-------|
| id | integer | Primary key |
| user_id | integer | → users(id) |
| recall_id | integer | → recalls(id) |
| product_upc | text | |
| sent_at | timestamp | |
| viewed | boolean | |
| email_sent | boolean | |

---

## Getting Help

**Database / SSH Access Issues:**
- Contact: Bryce (team lead)

**DBeaver Issues:**
- Official docs: https://dbeaver.com/docs/
- Community forum: https://github.com/dbeaver/dbeaver/issues

**SQL Help:**
- PostgreSQL docs: https://www.postgresql.org/docs/
- Quick reference: https://www.postgresqltutorial.com/

---

## Next Steps

Once connected:
1. ✅ Explore the tables
2. ✅ Run some test queries
3. ✅ Familiarize yourself with the data
4. ✅ Let the team know you're connected!

---

**Questions? Ask in the team Slack/Discord!**
