# Food Recall Alert — React Frontend

A React + TypeScript app for checking food recalls. Users can search or scan product barcodes, see recall status, and manage a grocery list. Connects to a FastAPI backend for search/cart and falls back to Open Food Facts when a product isn’t in the local database.

---

## Quick start

```bash
npm install
npm run dev
```

Open **http://localhost:5173**. Set `VITE_API_URL` in `.env` if your backend runs elsewhere (default: `http://localhost:8000`).

---

## Project structure (for teammates)

All app code lives in the **project root** (no `src/` folder). Here’s what each part does:

| What | Where | Purpose |
|------|--------|--------|
| **Routes & shell** | `App.tsx` | Defines all routes. MVP routes (`/`, `/scan`, `/groceries`, `/settings`) and V2 routes (`/v2`, `/v2/demo/...`). |
| **Layout** | `Layout.tsx` | Wraps every page: top nav, main content, sidebar (MVP only), bottom nav (MVP only), footer. |
| **Top nav** | `TopNav.tsx` | Black bar with logo, nav links (or step arrows in V2 flow), Sign in, and mode dropdown (MVP vs V2: Ingredient preferences). |
| **API layer** | `api.ts` | All backend calls: `searchProduct`, `checkRecallByUPC` (backend + Open Food Facts fallback), cart, health, FDA recalls. |
| **Data types** | `types.ts` | Shared TypeScript types: `Product`, `RecallInfo`, `CartItem`, `SearchRequest`, etc. |
| **Global state** | `store.ts` | Zustand store (persisted): `userId`, `hasSeenOnboarding`, cart, ingredient preferences, etc. |
| **API hooks** | `useProduct.ts` | React Query hooks: `useSearchProduct`, `useCart`, `useAddToCart`, `useRemoveFromCart`. |
| **Pages (MVP)** | `Home.tsx`, `Scan.tsx`, `MyGroceries.tsx`, `Settings.tsx` | Main app screens. |
| **Pages (V2)** | `V2Home.tsx`, `V2Scan.tsx`, … | Static V2 demo pages. The **V2: Ingredient preferences** flow is a step-through demo under `/v2/demo/*`. |
| **Shared UI** | `ProductCard.tsx`, `RecallAlert.tsx`, `CartList.tsx`, `ManualInput.tsx`, `BarcodeScanner.tsx` | Reusable components. |
| **Onboarding** | `Onboarding.tsx` | First-time screen (create account / try it out). Shown when `hasSeenOnboarding` is false. |

**Backend snippets** (to merge into your FastAPI app) live in **`backend/`**: `fda_recalls.py`, `s3_upload.py`. See `backend/README.md`.

---

## MVP vs V2

- **MVP** (dropdown: “MVP”): Full app — Home (search), Scan (camera barcode + recall check), My Groceries (cart from API + mock “frequently purchased”), Settings. Uses sidebar + bottom nav.
- **V2: Ingredient preferences** (dropdown: “V2: Ingredient preferences”): Step-through demo only. No sidebar/bottom nav; top bar shows “Step 1 of 5” and arrows. Steps: Intro → Cart results → Recommendations → Ingredient preferences → Ingredients to avoid. All static/mock.

---

## Environment

- **`.env`** (create from `.env.example`): `VITE_API_URL=http://localhost:8000` (or your backend URL).
- **Vite proxy**: In dev, `/api/*` is proxied to the same target so you can use relative URLs if you prefer.

---

## Scan flow (for reference)

1. User opens **Scan** → clicks “Start camera” → `BarcodeScanner` opens (ZXing).
2. On successful decode, `onScan(barcode)` is called with the UPC string.
3. **Scan** calls `searchMutation.mutateAsync({ upc: barcode })` → `api.searchProduct({ upc })` → **`checkRecallByUPC(upc)`** in `api.ts`.
4. Backend is tried first; if the product isn’t found, **Open Food Facts** is used. Result is shown in `ProductCard` (recall badge + optional “Add to My Groceries”).

---

## Build & deploy

```bash
npm run build
```

Output is in **`dist/**`. For deployment options (EC2, S3 static hosting, Vercel), see **SETUP_INSTRUCTIONS.md**.
