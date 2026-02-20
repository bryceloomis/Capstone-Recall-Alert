# Backend integration

This folder holds snippets to **merge into your existing FastAPI app** (App 1).

## FDA Recall API (`fda_recalls.py`)

Add the route from `fda_recalls.py` so the React frontend can query FDA openFDA enforcement data (by UPC or product name). Run server-side so you can cache/refresh daily.

**Merge:** `pip install httpx`, then copy the `check_fda_recalls` function and add `@app.get("/api/recalls/fda")` as shown in the file. Optionally add caching (e.g. 24h TTL).

## S3 upload (`s3_upload.py`)

Use for product/scan images or other file uploads. Uploads go to bucket `food-recall-app-data` under `scans/`.

**Merge:** `pip install boto3 python-multipart`, set AWS credentials (env or IAM), create the bucket, then add the `upload_scan_image` helper and `@app.post("/api/upload-image")` with `File(...)` as in the snippet.

**Static frontend hosting:** After `npm run build`, upload the contents of `dist/` to an S3 bucket with **static website hosting** enabled. Point your domain or bucket URL to the app.
