"""
Collaboration Dashboard — WP3 log of all collaborations within UNINOVIS.

Tracks, per collaboration: the collaborators involved (name, email,
institution, area of interest), whether it has included a physical mobility
(with past or projected dates) and/or virtual meetings, the goal of the
collaboration, and its status (preparing, confirmed, or already happened).
"""

import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/collaboration-dashboard", tags=["collaboration_dashboard"])

STATUSES = {"preparing", "confirmed", "happened"}


# -- Auth helpers ---------------------------------------------------------------

from auth import get_session, user_roles


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


def _is_uma_email(username: str) -> bool:
    """Usernames are the login email; UMA accounts use the @uma.es domain."""
    return username.strip().lower().rsplit("@", 1)[-1] == "uma.es"


_ALLOWED_ROLES = {"uninovis_staff", "superuser"}


def _require_staff(session: dict = Depends(_require_auth)) -> dict:
    """UMA internal tool — requires BOTH the uninovis_staff (or superuser)
    role AND a @uma.es login."""
    if not (_ALLOWED_ROLES & set(user_roles(session))) or not _is_uma_email(session["username"]):
        raise HTTPException(status_code=403, detail="uninovis_staff (UMA) access only")
    return session


def _is_senior_editor(session: dict) -> bool:
    return bool({"tester", "superuser"} & set(user_roles(session)))


# -- Data I/O ---------------------------------------------------------------

DEFAULT_DATA = {"collaborations": []}


def load_data() -> dict:
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA.copy())
        return DEFAULT_DATA.copy()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -- Models ---------------------------------------------------------------

class Collaborator(BaseModel):
    name: str
    email: str = ""
    institution: str = ""
    area_of_interest: str = ""


class MobilityVisit(BaseModel):
    collaborator_name: str = ""
    start_date: str = ""  # "YYYY-MM-DD"
    end_date: str = ""    # "YYYY-MM-DD"
    notes: str = ""


class VirtualMeeting(BaseModel):
    date: str = ""  # "YYYY-MM-DD"
    notes: str = ""


class CollaborationBody(BaseModel):
    title: str
    goal: str = ""
    status: str = "preparing"  # preparing | confirmed | happened
    collaborators: list[Collaborator] = []
    physical_mobility: bool = False
    mobility_visits: list[MobilityVisit] = []
    virtual_meetings_held: bool = False
    virtual_meetings: list[VirtualMeeting] = []
    notes: str = ""


def _validate_status(status: str):
    if status not in STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")


# -- Routes ---------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    has_access = bool(_ALLOWED_ROLES & set(user_roles(session))) and _is_uma_email(session["username"])
    return {
        "username": session["username"],
        "role": session["role"],
        "has_access": has_access,
        "can_edit": has_access,
    }


@router.get("/api/data")
def get_all_data(session: dict = Depends(_require_staff)):
    data = load_data()
    institutions = sorted({
        c.get("institution", "").strip()
        for entry in data["collaborations"]
        for c in entry.get("collaborators", [])
        if c.get("institution", "").strip()
    })
    areas_of_interest = sorted({
        c.get("area_of_interest", "").strip()
        for entry in data["collaborations"]
        for c in entry.get("collaborators", [])
        if c.get("area_of_interest", "").strip()
    })
    return {
        "collaborations": data["collaborations"],
        "institutions": institutions,
        "areas_of_interest": areas_of_interest,
    }


@router.post("/api/collaborations")
def create_collaboration(body: CollaborationBody, session: dict = Depends(_require_staff)):
    _validate_status(body.status)
    data = load_data()
    now = datetime.utcnow().isoformat() + "Z"
    entry = body.model_dump()
    entry.update({
        "id": "col" + uuid.uuid4().hex[:8],
        "linked_username": session["username"].lower(),
        "created_at": now,
        "updated_at": now,
    })
    data["collaborations"].append(entry)
    save_data(data)
    return entry


@router.put("/api/collaborations/{collab_id}")
def update_collaboration(collab_id: str, body: CollaborationBody, session: dict = Depends(_require_staff)):
    _validate_status(body.status)
    data = load_data()
    username = session["username"].lower()
    is_editor = _is_senior_editor(session)
    for entry in data["collaborations"]:
        if entry["id"] == collab_id:
            is_owner = entry.get("linked_username", "").lower() == username
            if not is_editor and not is_owner:
                raise HTTPException(403, "You can only edit collaborations you logged")
            updated = body.model_dump()
            updated.update({
                "id": entry["id"],
                "linked_username": entry["linked_username"],
                "created_at": entry["created_at"],
                "updated_at": datetime.utcnow().isoformat() + "Z",
            })
            data["collaborations"][data["collaborations"].index(entry)] = updated
            save_data(data)
            return updated
    raise HTTPException(404, "Collaboration not found")


@router.delete("/api/collaborations/{collab_id}")
def delete_collaboration(collab_id: str, session: dict = Depends(_require_staff)):
    data = load_data()
    username = session["username"].lower()
    is_editor = _is_senior_editor(session)
    entry = next((e for e in data["collaborations"] if e["id"] == collab_id), None)
    if not entry:
        raise HTTPException(404, "Collaboration not found")
    is_owner = entry.get("linked_username", "").lower() == username
    if not is_editor and not is_owner:
        raise HTTPException(403, "You can only delete collaborations you logged")
    data["collaborations"] = [e for e in data["collaborations"] if e["id"] != collab_id]
    save_data(data)
    return {"ok": True}
