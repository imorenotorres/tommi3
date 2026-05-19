"""
UNINOVIS Event Calendar — Calendar app with category and university filters.

Manages events with role-based editing (tester+).
Designed to be mounted on the TOMMI FastAPI server.
"""

import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "directory", "data.json")

router = APIRouter(prefix="/event-calendar", tags=["event_calendar"])


# -- Auth helpers -------------------------------------------------------------

from auth import get_session, ROLES


def _get_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.query_params.get("token")


def _require_auth(request: Request) -> dict:
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def _require_editor(session: dict = Depends(_require_auth)) -> dict:
    if ROLES.get(session["role"], 0) < ROLES.get("tester", 99):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


# -- Data I/O -----------------------------------------------------------------

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_directory():
    with open(DIRECTORY_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# -- Routes -------------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    can_edit = ROLES.get(session["role"], 0) >= ROLES.get("tester", 99)
    return {"username": session["username"], "role": session["role"], "can_edit": can_edit}


@router.get("/api/events")
def get_events(session: dict = Depends(_require_auth)):
    """Return all events."""
    data = load_data()
    return data["events"]


@router.get("/api/config")
def get_config(session: dict = Depends(_require_auth)):
    """Return categories and universities."""
    data = load_data()
    return {
        "categories": data["categories"],
        "universities": data.get("universities", []),
    }


@router.get("/api/directory")
def get_directory(session: dict = Depends(_require_auth)):
    """Return directory groups and users for participant selection."""
    directory = load_directory()
    groups = []
    for g in directory.get("groups", []):
        groups.append({
            "id": g["id"],
            "name": g["name"],
            "subgroups": g.get("subgroups", []),
        })
    users = []
    for u in directory.get("users", []):
        users.append({
            "id": u["id"],
            "first_name": u["first_name"],
            "family_name": u["family_name"],
            "email": u["email"],
            "university": u.get("university", ""),
            "groups": u.get("groups", []),
            "subgroups": u.get("subgroups", []),
        })
    return {"groups": groups, "users": users}


# -- Event CRUD ---------------------------------------------------------------

class EventBody(BaseModel):
    name: str
    description: str = ""
    category: str
    university: str = ""
    event_type: str = "Physical"
    place: str = ""
    meeting_url: str = ""
    start_date: str
    end_date: str
    registration_link: str = ""
    image: str = ""
    participants: list[str] = []
    participant_groups: list[str] = []


@router.post("/api/events")
def create_event(body: EventBody, session: dict = Depends(_require_editor)):
    data = load_data()
    if body.category not in data["categories"]:
        raise HTTPException(400, f"Unknown category: {body.category}")
    if body.university and body.university not in data.get("universities", []):
        raise HTTPException(400, f"Unknown university: {body.university}")
    if body.event_type not in ("Virtual", "Physical"):
        raise HTTPException(400, "event_type must be 'Virtual' or 'Physical'")
    event = {
        "id": "evt" + str(uuid.uuid4())[:8],
        "name": body.name,
        "description": body.description,
        "category": body.category,
        "university": body.university,
        "event_type": body.event_type,
        "place": body.place,
        "meeting_url": body.meeting_url,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "registration_link": body.registration_link,
        "image": body.image,
        "participants": body.participants,
        "participant_groups": body.participant_groups,
        "created_by": session["username"],
    }
    data["events"].append(event)
    save_data(data)
    return event


@router.put("/api/events/{event_id}")
def update_event(event_id: str, body: EventBody, session: dict = Depends(_require_editor)):
    data = load_data()
    if body.category not in data["categories"]:
        raise HTTPException(400, f"Unknown category: {body.category}")
    if body.university and body.university not in data.get("universities", []):
        raise HTTPException(400, f"Unknown university: {body.university}")
    if body.event_type not in ("Virtual", "Physical"):
        raise HTTPException(400, "event_type must be 'Virtual' or 'Physical'")
    for ev in data["events"]:
        if ev["id"] == event_id:
            ev["name"] = body.name
            ev["description"] = body.description
            ev["category"] = body.category
            ev["university"] = body.university
            ev["event_type"] = body.event_type
            ev["place"] = body.place
            ev["meeting_url"] = body.meeting_url
            ev["start_date"] = body.start_date
            ev["end_date"] = body.end_date
            ev["registration_link"] = body.registration_link
            ev["image"] = body.image
            ev["participants"] = body.participants
            ev["participant_groups"] = body.participant_groups
            save_data(data)
            return ev
    raise HTTPException(404, "Event not found")


@router.delete("/api/events/{event_id}")
def delete_event(event_id: str, session: dict = Depends(_require_editor)):
    data = load_data()
    before = len(data["events"])
    data["events"] = [ev for ev in data["events"] if ev["id"] != event_id]
    if len(data["events"]) == before:
        raise HTTPException(404, "Event not found")
    save_data(data)
    return {"ok": True}
