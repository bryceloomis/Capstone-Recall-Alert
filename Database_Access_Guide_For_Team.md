# Food Recall Alert - Database Access Guide

**Last Updated:** February 17, 2026  
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

## Step 2: Get Database Connection Information

**You'll need these credentials from Bryce (or whoever set up the database):**

```
Host: food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com
Port: 5432
Database: food_recall
Username: postgres
Password: [ASK TEAM LEAD FOR PASSWORD]
```

**⚠️ IMPORTANT:** Keep the password secure! Don't commit it to GitHub or share publicly.

---

## Step 3: Connect to Database in DBeaver

### First Time Setup:

1. **Open DBeaver**

2. **Create New Connection:**
   - Click **Database** → **New Database Connection**
   - OR click the plug icon (🔌) in the toolbar

3. **Select PostgreSQL:**
   - Find and click **PostgreSQL** 
   - Click **Next**

4. **Enter Connection Details:**
   ```
   Host: food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com
   Port: 5432
   Database: food_recall
   Username: postgres
   Password: [enter password here]
   ```
   
   **☑️ Check** "Save password locally"

5. **Download Drivers (First Time Only):**
   - Click **Test Connection**
   - If prompted, click **Download** to get PostgreSQL drivers
   - Wait for download to complete
   - Click **Test Connection** again
   - Should say **"Connected"** ✅

6. **Finish Setup:**
   - Click **Finish**
   - You should now see the database in the left sidebar!

---

## Step 4: Explore the Database

### View Tables:

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
- Click **SQL Editor** button (top toolbar)
- OR press **Ctrl + ]** (Mac: **Cmd + ]**)

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

### "Connection timeout" or "Can't connect"
**Solution:** Ask your team lead to add your IP address to the AWS security group.

Send them this message:
```
Hey! I'm trying to connect to the database but getting a timeout. 
Can you add my IP to the security group?

My IP address is: [Go to https://whatismyipaddress.com/ and copy it here]
```

### "Authentication failed"
**Solution:** Double-check your password. Make sure you got the correct one from your team lead.

### "Database does not exist"
**Solution:** Make sure the database name is exactly `food_recall` (with underscore, not hyphen)

### Drivers won't download
**Solution:** 
1. Click **Database** → **Driver Manager**
2. Find **PostgreSQL**
3. Click **Download/Update**

---

## Security Best Practices

✅ **DO:**
- Save password in DBeaver (it's encrypted locally)
- Test queries on small datasets first
- Use `WHERE` clauses to limit changes
- Ask before making major changes

❌ **DON'T:**
- Share the password publicly
- Commit connection details to GitHub
- Delete data without checking with team
- Run `DELETE` or `UPDATE` without `WHERE` clause

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
-- Find users with recalled items
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

### Tables Overview:

**users**
- id (Primary Key)
- email
- name
- created_at

**products**
- id (Primary Key)
- upc (Unique)
- product_name
- brand_name
- category
- ingredients
- image_url

**recalls**
- id (Primary Key)
- upc
- product_name
- brand_name
- recall_date
- reason
- source (FDA/USDA)

**user_carts**
- id (Primary Key)
- user_id → references users(id)
- product_upc
- product_name
- brand_name
- added_date

**alerts**
- id (Primary Key)
- user_id → references users(id)
- recall_id → references recalls(id)
- product_upc
- sent_at
- viewed
- email_sent

---

## Getting Help

**Database Access Issues:**
- Contact: Bryce (team lead)
- Need: Your IP address added to security group

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
