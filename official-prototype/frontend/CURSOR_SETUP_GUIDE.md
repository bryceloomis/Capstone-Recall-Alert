# 🎯 COMPLETE SETUP - COPY THIS TO CURSOR

## Step 1: Create Project

```bash
# Create new project
npm create vite@latest food-recall-frontend -- --template react-ts
cd food-recall-frontend

# Install all dependencies
npm install
npm install @tanstack/react-query axios zustand react-router-dom
npm install -D tailwindcss postcss autoprefixer
npm install @zxing/library @zxing/browser lucide-react

# Initialize Tailwind
npx tailwindcss init -p
```

## Step 2: Copy All Files

After running the above, replace/create these files with the code provided:

### Configuration Files (Root Directory)
- `tailwind.config.js` - Tailwind configuration
- `postcss.config.js` - PostCSS configuration  
- `tsconfig.json` - TypeScript configuration
- `vite.config.ts` - Vite configuration
- `package.json` - Dependencies
- `index.html` - HTML template
- `.env` - Create from `.env.example`

### Source Files (src/ directory)
**Core:**
- `src/main.tsx` - Entry point
- `src/App.tsx` - Main app with routing
- `src/index.css` - Global styles

**Library:**
- `src/lib/types.ts` - TypeScript types
- `src/lib/api.ts` - API client
- `src/lib/store.ts` - Zustand store

**Hooks:**
- `src/hooks/useProduct.ts` - React Query hooks

**Components - Layout:**
- `src/components/layout/Layout.tsx` - Main layout with nav

**Components - Product:**
- `src/components/product/ProductCard.tsx` - Product display card
- `src/components/product/RecallAlert.tsx` - Recall alert UI

**Components - Scanner:**
- `src/components/scanner/ManualInput.tsx` - Manual UPC/name input
- `src/components/scanner/BarcodeScanner.tsx` - Camera scanner

**Components - Cart:**
- `src/components/cart/CartList.tsx` - Cart items list

**Pages:**
- `src/pages/Home.tsx` - Home page with search
- `src/pages/Scan.tsx` - Barcode scanning page
- `src/pages/MyGroceries.tsx` - Saved groceries list
- `src/pages/Settings.tsx` - User settings

## Step 3: Create .env File

```bash
# Create .env in root directory
cat > .env << 'EOF'
VITE_API_URL=http://localhost:8000
EOF
```

## Step 4: Verify Backend is Running

Make sure your partner's backend is running:

```bash
# In separate terminal
cd path/to/Capstone-Recall-Alert/backend
source venv/bin/activate
python app.py

# Should see: "Uvicorn running on http://0.0.0.0:8000"
```

## Step 5: Start Development Server

```bash
npm run dev
# Opens at http://localhost:5173
```

## Step 6: Test Everything

1. ✅ Open http://localhost:5173
2. ✅ Try searching by UPC: `041190468831`
3. ✅ Try searching by name: `granola`
4. ✅ Add item to My Groceries
5. ✅ Check "My Groceries" tab
6. ✅ Try "Scan" page (camera placeholder for now)

## Step 7: Build for Production

```bash
# Build static files
npm run build

# Preview production build
npm run preview
```

## Step 8: Deploy to EC2 (Same Server as Backend)

```bash
# 1. Build frontend
npm run build

# 2. Copy to EC2 (from your local machine)
scp -r dist/* ubuntu@YOUR-EC2-IP:/home/ubuntu/Capstone-Recall-Alert/frontend-react/

# 3. SSH into EC2 and update Nginx config
ssh -i ~/.ssh/food-recall-keypair.pem ubuntu@YOUR-EC2-IP

# 4. Update nginx config to serve React app
sudo nano /etc/nginx/sites-available/food-recall-app

# Replace content with:
server {
    listen 80;
    server_name _;

    # Serve React frontend
    location / {
        root /home/ubuntu/Capstone-Recall-Alert/frontend-react;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Save and restart nginx
sudo nginx -t
sudo systemctl restart nginx
```

## Alternative: Deploy to Vercel (Separate from Backend)

```bash
# 1. Push to GitHub
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR-GITHUB-REPO
git push -u origin main

# 2. Import to Vercel
# - Go to vercel.com
# - Import your GitHub repo
# - Set environment variable: VITE_API_URL=http://YOUR-EC2-IP:8000
# - Deploy

# 3. Update backend CORS
# Edit backend/app.py:
allow_origins=["https://your-vercel-app.vercel.app"]
```

## Troubleshooting

### "Cannot find module" errors
```bash
rm -rf node_modules package-lock.json
npm install
```

### API not connecting
```bash
# Check backend is running
curl http://localhost:8000/api/health

# Check .env file exists
cat .env
```

### Tailwind styles not working
```bash
# Make sure index.css is imported in main.tsx
# Restart dev server
npm run dev
```

### Build fails
```bash
# Check TypeScript errors
npm run lint

# Ignore if just warnings
npm run build -- --force
```

## Next Steps After Setup

1. **Implement real barcode scanning** in `BarcodeScanner.tsx` using ZXing
2. **Add ingredient preferences tracking** (V2 feature from PRD)
3. **Implement receipt scanning** using OCR
4. **Add notification system** for recall alerts
5. **Create onboarding flow** for first-time users

## Key Differences from Partner's Code

**Before (Partner's Code):**
- ❌ Vanilla HTML/CSS/JS
- ❌ No component architecture
- ❌ Inline styles and DOM manipulation
- ❌ No routing
- ❌ No state management

**After (Your Code):**
- ✅ React + TypeScript + Tailwind
- ✅ Reusable components
- ✅ Modern styling with utility classes
- ✅ React Router for navigation
- ✅ Zustand for state, React Query for API

## File Checklist

Make sure you have all these files:

**Root:**
- [ ] package.json
- [ ] tsconfig.json
- [ ] vite.config.ts
- [ ] tailwind.config.js
- [ ] postcss.config.js
- [ ] index.html
- [ ] .env

**src/:**
- [ ] main.tsx
- [ ] App.tsx
- [ ] index.css

**src/lib/:**
- [ ] types.ts
- [ ] api.ts
- [ ] store.ts

**src/hooks/:**
- [ ] useProduct.ts

**src/components/layout/:**
- [ ] Layout.tsx

**src/components/product/:**
- [ ] ProductCard.tsx
- [ ] RecallAlert.tsx

**src/components/scanner/:**
- [ ] ManualInput.tsx
- [ ] BarcodeScanner.tsx

**src/components/cart/:**
- [ ] CartList.tsx

**src/pages/:**
- [ ] Home.tsx
- [ ] Scan.tsx
- [ ] MyGroceries.tsx
- [ ] Settings.tsx

## Quick Commands Reference

```bash
# Development
npm run dev              # Start dev server
npm run build            # Build for production
npm run preview          # Preview production build
npm run lint             # Check TypeScript errors

# Deployment
npm run build            # Create dist/ folder
scp -r dist/* user@ec2   # Copy to server

# Backend
cd backend && source venv/bin/activate && python app.py
```

---

**You're all set!** 🚀

The app connects to your partner's backend API and provides a modern, mobile-first interface following your PRD specifications.
