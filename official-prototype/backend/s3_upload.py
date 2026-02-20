"""
Merge this into your existing app.py (FastAPI backend).

Use for: product/scan images, or any file uploads.
Install: pip install boto3 python-multipart
Set AWS credentials (env vars or IAM role). Bucket must exist (e.g. recallguard-dev-data).
"""

import os
from datetime import datetime
import boto3
from fastapi import UploadFile

# Use your team's bucket; default matches recallguard-dev-data (us-east-1).
S3_BUCKET = os.environ.get("S3_BUCKET", "recallguard-dev-data")
S3_REGION = os.environ.get("AWS_REGION", "us-east-1")
s3 = boto3.client("s3", region_name=S3_REGION)


async def upload_scan_image(file: UploadFile) -> dict:
    """
    Upload a file to S3 and return its public URL.
    Add to your app like:

        @app.post("/api/upload-image")
        async def api_upload_image(file: UploadFile = File(...)):
            return await upload_scan_image(file)
    """
    key = f"scans/{datetime.now().isoformat()}_{file.filename}"
    contents = await file.read()
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=contents, ContentType=file.content_type or "application/octet-stream")
    return {"url": f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"}


# Example: add to your app.py
#
# from fastapi import File, UploadFile
# from s3_upload import upload_scan_image
#
# @app.post("/api/upload-image")
# async def api_upload_image(file: UploadFile = File(...)):
#     return await upload_scan_image(file)
