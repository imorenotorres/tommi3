"""
UNINOVIS Matomo Analytics — Proxy for Matomo Reporting API.

Proxies requests to Matomo Cloud so the API token stays server-side.
The frontend never sees the token.
"""

import json
import os
import urllib.parse
import urllib.request
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

router = APIRouter(prefix="/matomo-analytics", tags=["matomo_analytics"])

MATOMO_URL = "https://uninovis.matomo.cloud"
MATOMO_TOKEN = os.environ.get("MATOMO_TOKEN", "00695d820f1c1acf2a546d91ef60a825")
MATOMO_SITE_ID = "3"
MATOMO_SITES = {
    "1": "uninovis.eu",
    "2": "UNINOVIS Agora",
    "3": "gloria.uma.es",
}


@router.get("/api/sites")
def get_sites():
    """Return available Matomo sites."""
    return {"sites": [{"id": k, "name": v} for k, v in MATOMO_SITES.items()]}


@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/proxy")
def matomo_proxy(
    method: str = Query(..., description="Matomo API method, e.g. VisitsSummary.get"),
    period: str = Query("day"),
    date: str = Query("last30"),
    segment: str = Query(""),
    flat: str = Query("1"),
    filter_limit: str = Query("100"),
    idSite: str = Query(MATOMO_SITE_ID),
):
    """Proxy a Matomo Reporting API call. Token is injected server-side."""
    params = {
        "module": "API",
        "method": method,
        "idSite": idSite,
        "period": period,
        "date": date,
        "format": "JSON",
        "token_auth": MATOMO_TOKEN,
        "flat": flat,
        "filter_limit": filter_limit,
    }
    if segment:
        params["segment"] = segment

    try:
        post_data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(MATOMO_URL + "/", data=post_data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        return JSONResponse(status_code=502, content={"detail": f"Matomo API error: {e}"})
