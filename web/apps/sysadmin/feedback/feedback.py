"""
UNINOVIS User Feedback — collects feedback sent from the speech-bubble widget
that nav.js adds to every intranet app, and lists it for superusers in the
System Administration section.

Any logged-in user can submit; only users with access to the "feedback" tool
(superuser by default, see TOOL_ACCESS) can list, update or delete entries.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import can_access_tool, require_login

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

MAX_MESSAGE_LEN = 5000

router = APIRouter(prefix="/feedback", tags=["feedback"])

_lock = threading.Lock()


def _require_tool_access(session: dict = Depends(require_login)) -> dict:
    if not can_access_tool(session, "feedback"):
        raise HTTPException(status_code=403, detail="Access to user feedback not granted")
    return session


def _load() -> list:
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(entries: list) -> None:
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_PATH)


def _display_name(username: str) -> str:
    # Imported lazily: app.py imports this module, so a top-level import
    # would be circular.
    try:
        from app import resolve_display_name
        return resolve_display_name(username)
    except Exception:
        return username


class FeedbackIn(BaseModel):
    app: str = Field(..., min_length=1, max_length=200)
    page_url: Optional[str] = Field(None, max_length=1000)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LEN)


class FeedbackUpdate(BaseModel):
    status: Literal["new", "read", "resolved"]


@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.post("/api/submit")
def submit_feedback(body: FeedbackIn, session: dict = Depends(require_login)):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Feedback cannot be empty")
    # page_url is rendered as a link in the admin list, so only keep
    # same-site paths (no "javascript:", no "//host" or "/\host").
    page_url = body.page_url
    if not page_url or not page_url.startswith("/") or page_url[1:2] in ("/", "\\"):
        page_url = None
    entry = {
        "id": uuid.uuid4().hex,
        "username": session["username"],
        "name": _display_name(session["username"]),
        "app": body.app.strip(),
        "page_url": page_url,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "new",
    }
    with _lock:
        entries = _load()
        entries.append(entry)
        _save(entries)
    return {"status": "ok", "id": entry["id"]}


@router.get("/api/list")
def list_feedback(
    app: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: dict = Depends(_require_tool_access),
):
    entries = _load()
    apps = sorted({e["app"] for e in entries})
    if app:
        entries = [e for e in entries if e["app"] == app]
    if status:
        entries = [e for e in entries if e["status"] == status]
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return {"entries": entries, "apps": apps}


@router.get("/api/count")
def count_new(session: dict = Depends(_require_tool_access)):
    return {"new": sum(1 for e in _load() if e["status"] == "new")}


@router.patch("/api/{entry_id}")
def update_feedback(entry_id: str, body: FeedbackUpdate, session: dict = Depends(_require_tool_access)):
    with _lock:
        entries = _load()
        for e in entries:
            if e["id"] == entry_id:
                e["status"] = body.status
                _save(entries)
                return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Feedback not found")


@router.delete("/api/{entry_id}")
def delete_feedback(entry_id: str, session: dict = Depends(_require_tool_access)):
    with _lock:
        entries = _load()
        remaining = [e for e in entries if e["id"] != entry_id]
        if len(remaining) == len(entries):
            raise HTTPException(status_code=404, detail="Feedback not found")
        _save(remaining)
    return {"status": "ok"}
