"""
UNINOVIS Holiday Tracker — shared calendar for superusers to log their own
holidays and personal days. Purely self-reported; no external sync (Agora
or otherwise) and no data beyond who logged which day(s) as what.
"""

import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "directory", "data.json")

router = APIRouter(prefix="/holiday-tracker", tags=["holiday_tracker"])

EVENT_TYPES = {"holiday", "personal_day"}


def _display_name(username: str) -> str:
    """Best-effort lookup of a friendly name from the Directory app; falls
    back to the raw username/email if no match is found."""
    try:
        with open(DIRECTORY_DATA_PATH, "r", encoding="utf-8") as f:
            directory = json.load(f)
    except Exception:
        return username
    uname = username.strip().lower()
    for u in directory.get("users", []):
        emails = [e.strip().lower() for e in (u.get("email") or "").split(";")]
        if uname in emails:
            full = f"{u.get('first_name', '')} {u.get('family_name', '')}".strip()
            return full or username
    return username


# ── Auth helpers ─────────────────────────────────────────────────────

from auth import get_session, user_roles as _user_roles


def _get_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.query_params.get("token")


def _require_auth(request: Request) -> dict:
    token = _get_token(request)
    if not token:
        return {"username": "guest", "role": "public", "roles": ["public"]}
    session = get_session(token)
    if not session:
        return {"username": "guest", "role": "public", "roles": ["public"]}
    return session


def _require_superuser(session: dict = Depends(_require_auth)) -> dict:
    if "superuser" not in _user_roles(session):
        raise HTTPException(status_code=403, detail="Superuser access only")
    return session


# ── Data I/O ─────────────────────────────────────────────────────────

DEFAULT_DATA = {"events": []}


def load_data():
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA.copy())
        return DEFAULT_DATA.copy()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Routes ───────────────────────────────────────────────────────────

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    return {
        "username": session["username"],
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "is_superuser": "superuser" in _user_roles(session),
    }


@router.get("/api/events")
def list_events(session: dict = Depends(_require_superuser)):
    """All superusers see everyone's logged holidays/personal days."""
    return [{**e, "display_name": _display_name(e["username"])} for e in load_data()["events"]]


class EventBody(BaseModel):
    type: str
    start_date: str  # "YYYY-MM-DD"
    end_date: str    # "YYYY-MM-DD"

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v):
        if v not in EVENT_TYPES:
            raise ValueError(f"type must be one of {sorted(EVENT_TYPES)}")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("dates must be in YYYY-MM-DD format")
        return v


@router.post("/api/events")
def create_event(body: EventBody, session: dict = Depends(_require_superuser)):
    """A superuser logs a holiday/personal day for themselves only."""
    if body.end_date < body.start_date:
        raise HTTPException(400, "end_date cannot be before start_date")
    data = load_data()
    event = {
        "id": "hol" + uuid.uuid4().hex[:8],
        "username": session["username"],
        "type": body.type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    data["events"].append(event)
    save_data(data)
    return {**event, "display_name": _display_name(event["username"])}


@router.put("/api/events/{event_id}")
def update_event(event_id: str, body: EventBody, session: dict = Depends(_require_superuser)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "end_date cannot be before start_date")
    data = load_data()
    for ev in data["events"]:
        if ev["id"] == event_id:
            if ev["username"] != session["username"]:
                raise HTTPException(403, "You can only edit your own entries")
            ev["type"] = body.type
            ev["start_date"] = body.start_date
            ev["end_date"] = body.end_date
            save_data(data)
            return {**ev, "display_name": _display_name(ev["username"])}
    raise HTTPException(404, "Event not found")


@router.delete("/api/events/{event_id}")
def delete_event(event_id: str, session: dict = Depends(_require_superuser)):
    data = load_data()
    ev = next((e for e in data["events"] if e["id"] == event_id), None)
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev["username"] != session["username"]:
        raise HTTPException(403, "You can only delete your own entries")
    data["events"] = [e for e in data["events"] if e["id"] != event_id]
    save_data(data)
    return {"ok": True}
