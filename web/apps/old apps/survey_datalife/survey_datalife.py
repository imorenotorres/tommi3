"""
UNINOVIS DATA FOR L.I.F.E. — Survey on Data & AI Competences

Collects survey responses and stores them as JSON files.
Each response is saved as a separate timestamped file.
"""

import json
import os
import time
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_DIR = os.path.join(os.path.dirname(__file__), "responses")
os.makedirs(DATA_DIR, exist_ok=True)

router = APIRouter(prefix="/survey-datalife", tags=["survey_datalife"])


@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.post("/api/submit")
async def submit_response(request: Request):
    """Save a survey response."""
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"detail": "Invalid data"})

    # Add metadata
    body["_submitted_at"] = datetime.utcnow().isoformat() + "Z"
    body["_ip"] = request.client.host if request.client else "unknown"

    # Save as individual JSON file
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"response_{ts}_{os.urandom(4).hex()}.json"
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)

    return {"ok": True, "id": filename}


@router.get("/api/responses")
async def list_responses():
    """List all responses (for admin/analysis). No auth for now."""
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
    responses = []
    for fn in files:
        with open(os.path.join(DATA_DIR, fn), encoding="utf-8") as f:
            data = json.load(f)
            data["_file"] = fn
            responses.append(data)
    return {"count": len(responses), "responses": responses}


@router.get("/api/export")
async def export_responses():
    """Export all responses as a single JSON array."""
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
    responses = []
    for fn in files:
        with open(os.path.join(DATA_DIR, fn), encoding="utf-8") as f:
            responses.append(json.load(f))
    return responses
