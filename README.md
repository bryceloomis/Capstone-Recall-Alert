# 🍎 Food Recall Alert - MVP Starter Kit

A mobile-friendly web app that checks food products against FDA and USDA recall databases. Users can search by UPC barcode or product name to see if items are currently recalled.

## 📋 Project Overview

**Team:** UC Berkeley MIDS Capstone  
**Timeline:** 9 weeks  
**Tech Stack:** FastAPI (Python) backend, Progressive Web App (PWA) frontend  
**Data Sources:** FDA & USDA Recall APIs (simulated with fake data for now)

## 🏗️ Project Structure

```
food-recall-app/
├── backend/
│   ├── app.py              # FastAPI application
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── index.html         # Main search page
│   ├── scan.html          # Barcode scanning page (stub)
│   └── style.css          # Styles
├── data/
│   ├── fake_recalls.csv   # 50 sample recalled products
│   └── fake_products.csv  # 200 sample products
└── README.md
```

## 🚀 Quick Start

### 1. Clone or Download This Project

Download all files and place them in a folder called `food-recall-app`.

### 2. Set Up Backend

```bash
cd food-recall-app/backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

The API will start at `http://localhost:8000`

### 3. Open Frontend

Simply open `frontend/index.html` in your web browser. You can:
- Double-click the file, or
- Use a local server: `python -m http.server 8080` in the frontend directory

### 4. Test the App

Try these UPCs from the fake data:
- **Recalled:** `041190468935` (Organic Almond Butter - Salmonella)
- **Recalled:** `070038640196` (Peanut Butter Cups - Undeclared tree nuts)
- **Safe:** `041190468831` (Organic Granola)
- **Safe:** `070038349228` (Peanut Butter)

Or search by name: "granola", "yogurt", "pizza", etc.

## 📡 API Endpoints

### Health Check
```
GET /api/health
```
Returns API status and data counts.

### Search Product
```
POST /api/search
Body: { "upc": "041190468831" }
      OR
      { "name": "granola" }
```
Returns product details and recall status.

### Get All Recalls
```
GET /api/recalls
```
Returns list of all recalled products.

### User Cart Operations
```
GET  /api/user/cart/{user_id}     # Get cart items
POST /api/user/cart                # Add item
DELETE /api/user/cart/{user_id}/{upc}  # Remove item
```

## 🎯 Current Features (v0)

✅ Search by UPC (exact match)  
✅ Search by product name (fuzzy search)  
✅ Display recall status and details  
✅ User cart management  
✅ Fake data for testing (50 recalls, 200 products)  
✅ Mobile-friendly PWA design  
✅ In-memory database (no AWS needed yet)

## 🔜 Next Steps for Team

### Week 1-2: Infrastructure Setup
- [ ] Create GitHub repository and add team as collaborators
- [ ] Set up AWS RDS PostgreSQL database
- [ ] Replace CSV data loading with database queries
- [ ] Test database connections from local machines

### Week 3-4: External Integrations
- [ ] Integrate real FDA Recall API
- [ ] Integrate real USDA Recall API
- [ ] Set up product database API (Olivia's responsibility)
- [ ] Implement fuzzy UPC matching algorithm

### Week 5-6: Barcode Scanning
- [ ] Research QuaggaJS or ZXing library
- [ ] Implement camera access on mobile
- [ ] Add barcode detection to scan.html
- [ ] Test on iOS and Android devices

### Week 7-8: Polish & Deploy
- [ ] User authentication (optional but recommended)
- [ ] Email/SMS alert system
- [ ] Daily recall refresh background job
- [ ] Deploy backend to AWS EC2
- [ ] Deploy frontend to AWS S3 or with backend
- [ ] Set up HTTPS/SSL certificates

### Week 9: Testing & Documentation
- [ ] End-to-end testing
- [ ] User acceptance testing
- [ ] Documentation and demo prep
- [ ] Presentation materials

## 👥 Team Work Distribution (Suggested)

### Backend Engineer (2 people)
- AWS RDS setup and database schema
- FDA/USDA API integration
- Recall refresh job (cron/scheduled task)
- Fuzzy matching algorithm

### Frontend Engineer (1-2 people)
- Barcode scanning implementation (QuaggaJS)
- UI/UX improvements
- Mobile responsiveness
- User experience flow

### DevOps/Infrastructure (1 person)
- AWS organization and IAM setup
- EC2 deployment
- Environment management
- CI/CD if time permits

## 🗃️ Database Schema (To Be Implemented)

### recalls_table
```sql
CREATE TABLE recalls (
    id SERIAL PRIMARY KEY,
    upc VARCHAR(20) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255) NOT NULL,
    recall_date DATE NOT NULL,
    reason TEXT NOT NULL,
    source VARCHAR(50),  -- 'FDA' or 'USDA'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### products_table
```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    upc VARCHAR(20) UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    ingredients TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### user_carts_table
```sql
CREATE TABLE user_carts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    upc VARCHAR(20) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255) NOT NULL,
    added_date TIMESTAMP DEFAULT NOW()
);
```

## 📚 Resources

### Barcode Scanning
- [QuaggaJS](https://serratus.github.io/quaggaJS/) - JavaScript barcode reader
- [ZXing](https://github.com/zxing-js/library) - Alternative barcode library

### Product Databases
- [Open Food Facts API](https://world.openfoodfacts.org/data) - Free food product database
- [UPCitemdb](https://www.upcitemdb.com/) - UPC lookup API

### FDA/USDA APIs
- [FDA Recalls API](https://open.fda.gov/apis/food/enforcement/)
- [USDA Food Safety API](https://www.fsis.usda.gov/recalls)

### AWS Resources
- [AWS RDS Getting Started](https://docs.aws.amazon.com/rds/latest/userguide/CHAP_GettingStarted.html)
- [Deploying FastAPI on EC2](https://www.digitalocean.com/community/tutorials/how-to-deploy-fastapi-applications-with-gunicorn-and-nginx-on-ubuntu-20-04)

## 🐛 Troubleshooting

**CORS errors when calling API from frontend:**
- Make sure the backend is running on `localhost:8000`
- Check that CORS is enabled in `app.py` (it is by default)

**CSV file not found errors:**
- Make sure you're running `python app.py` from the `backend/` directory
- The code expects CSV files at `../data/` relative to the backend folder

**Can't install dependencies:**
- Use Python 3.8 or higher
- Create a virtual environment first
- On Windows, you might need to run as administrator

## 📝 Notes

- This is a **starter scaffold** with fake data
- Current version uses in-memory storage (data resets when you restart)
- Next step is connecting to AWS RDS for persistent storage
- Barcode scanning page is a stub - needs implementation
- User authentication is not yet implemented

## 🙋 Questions?

Contact your team members or check the GitHub repository's Issues section!

---

**Good luck with your capstone project! 🚀**
