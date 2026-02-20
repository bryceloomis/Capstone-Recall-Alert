"""
Merge this into your existing app.py (FastAPI + vanilla HTML backend).

Install: pip install httpx
"""

import httpx

# Add this route to your FastAPI app (e.g. app.get(...)).


async def check_fda_recalls(upc: str = None, product_name: str = None):
    """
    Query FDA openFDA enforcement API.
    Call from your app like:

        @app.get("/api/recalls/fda")
        async def api_recalls_fda(upc: str = None, product_name: str = None):
            return await check_fda_recalls(upc=upc, product_name=product_name)
    """
    base = "https://api.fda.gov/food/enforcement.json"
    if product_name:
        params = {"search": f'product_description:"{product_name}"', "limit": 10}
    elif upc:
        params = {"search": f'upc:"{upc}"', "limit": 5}
    else:
        return {"results": []}

    async with httpx.AsyncClient() as client:
        resp = await client.get(base, params=params)
        if resp.status_code != 200:
            return {"results": []}
        return resp.json()


# Example: add to your app.py
#
# from fastapi import FastAPI
# from fda_recalls import check_fda_recalls
#
# app = FastAPI()
#
# @app.get("/api/recalls/fda")
# async def api_recalls_fda(upc: str = None, product_name: str = None):
#     return await check_fda_recalls(upc=upc, product_name=product_name)
