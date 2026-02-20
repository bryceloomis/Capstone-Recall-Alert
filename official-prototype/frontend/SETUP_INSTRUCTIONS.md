# Food Recall Alert - Modern Frontend Setup

## Overview
This guide will help you create a modern React + TypeScript frontend that works with your existing backend while implementing your PRD vision.

## Prerequisites
- Node.js 18+ installed
- Your backend running (or accessible via AWS)
- Cursor IDE

## Quick Start

### 1. Create New React + TypeScript Project

```bash
# Create new Vite + React + TypeScript project
npm create vite@latest food-recall-frontend -- --template react-ts
cd food-recall-frontend

# Install dependencies
npm install

# Install additional packages
npm install @tanstack/react-query axios zustand react-router-dom
npm install -D tailwindcss postcss autoprefixer
npm install @zxing/library @zxing/browser
npm install lucide-react

# Initialize Tailwind
npx tailwindcss init -p
```

### 2. Project Structure

Create this folder structure:
```
src/
├── components/
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Layout.tsx
│   │   └── Navigation.tsx
│   ├── scanner/
│   │   ├── BarcodeScanner.tsx
│   │   └── ManualInput.tsx
│   ├── product/
│   │   ├── ProductCard.tsx
│   │   ├── RecallAlert.tsx
│   │   └── AllergenAlert.tsx
│   └── cart/
│       ├── CartList.tsx
│       └── CartItem.tsx
├── pages/
│   ├── Home.tsx
│   ├── Scan.tsx
│   ├── MyGroceries.tsx
│   └── Settings.tsx
├── lib/
│   ├── api.ts
│   ├── types.ts
│   └── store.ts
├── hooks/
│   ├── useProduct.ts
│   └── useCart.ts
└── App.tsx
```

### 3. Environment Setup

Create `.env` file:
```env
VITE_API_URL=http://localhost:8000
# OR for production:
# VITE_API_URL=http://YOUR-EC2-IP:8000
```

### 4. Configuration Files

I'll provide all the code files below that you can copy directly into Cursor.

---

## Development Workflow

1. **Run backend** (from your partner's code):
   ```bash
   cd backend
   source venv/bin/activate
   python app.py
   ```

2. **Run frontend** (new React app):
   ```bash
   cd food-recall-frontend
   npm run dev
   ```

3. **Access app**: http://localhost:5173

---

## Deployment Options

### Option A: Deploy with Existing EC2 (Recommended)

Your frontend will be served alongside the backend on the same EC2 instance.

1. **Build frontend**:
   ```bash
   npm run build
   # Creates dist/ folder with static files
   ```

2. **Copy to EC2**:
   ```bash
   # From your local machine
   scp -r dist/* ubuntu@YOUR-EC2-IP:/home/ubuntu/Capstone-Recall-Alert/frontend/
   ```

3. **Update API URL** in `.env.production`:
   ```env
   VITE_API_URL=
   ```
   Then rebuild: `npm run build`

### Option B: Deploy to Vercel (Separate Frontend)

1. Push code to GitHub
2. Import to Vercel
3. Set environment variable: `VITE_API_URL=http://YOUR-EC2-IP:8000`
4. Update backend CORS to allow Vercel domain

### Option C: Deploy to Netlify

Same as Vercel - push to GitHub, connect to Netlify, set env vars.

---

## Key Differences from Partner's Code

**What you're keeping:**
- Backend API endpoints (`/api/search`, `/api/user/cart`, etc.)
- CSV data loading
- Recall checking logic

**What you're replacing:**
- HTML/CSS/Vanilla JS → React + TypeScript + Tailwind
- No component architecture → Proper React components
- Inline styles → Tailwind utility classes
- Manual DOM manipulation → React state management
- No routing → React Router
- Basic UX → Modern, mobile-first design from your PRD

---

## Before merging to team repo

- **Remove agent log / debug code:** Search for `// #region agent log`, `#endregion`, and any `fetch` calls to `127.0.0.1:7242` (Cursor agent logging). Remove those blocks so production doesn’t make failed network requests. (If none exist, no change needed.)

---

## Next Steps After Setup

1. **Test API connection**: Make sure `api.ts` can reach your backend
2. **Implement barcode scanning**: Use ZXing library in `BarcodeScanner.tsx`
3. **Build out UC-1.1 → UC-1.5**: Core scanning and cart functionality
4. **Add state management**: User cart, ingredient preferences
5. **Implement notifications**: For recall alerts

---

## Troubleshooting

**CORS errors?**
- Make sure backend has CORS enabled for your frontend domain
- Check `app.py` has `allow_origins=["*"]` or specific domain

**API not connecting?**
- Verify backend is running on port 8000
- Check `VITE_API_URL` in `.env`
- Try accessing `http://localhost:8000/api/health` directly

**Build errors?**
- Run `npm install` again
- Clear node_modules: `rm -rf node_modules && npm install`

---

Ready to proceed? I'll provide all the code files next.
