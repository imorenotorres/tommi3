"""
Personal Dashboard — a personal to-do manager for UMA/UNINOVIS staff.

Each task can be linked to a directory unit/subunit and assigned to one or
more directory people. Every assignee tracks their own status ("new",
"in_progress", "completed") independently, so a task shared by two people can
be complete for one of them while still pending for the other.
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "new_directory", "data.json")

router = APIRouter(prefix="/personal-dashboard", tags=["personal_dashboard"])

STATUSES = {"new", "in_progress", "completed"}
VISIBILITIES = {"private", "public"}


# -- Auth helpers ---------------------------------------------------------------

from auth import require_login as _require_auth, user_roles, list_users


def _is_uma_email(username: str) -> bool:
    """Usernames are the login email; UMA accounts use the @uma.es domain."""
    return username.strip().lower().rsplit("@", 1)[-1] == "uma.es"


_ALLOWED_ROLES = {"uninovis_staff", "content_manager", "superuser"}


def _require_staff(session: dict = Depends(_require_auth)) -> dict:
    """UMA internal tool — requires BOTH the uninovis_staff (or superuser)
    role AND a @uma.es login."""
    if not (_ALLOWED_ROLES & set(user_roles(session))) or not _is_uma_email(session["username"]):
        raise HTTPException(status_code=403, detail="uninovis_staff (UMA) access only")
    return session


def _is_senior_editor(session: dict) -> bool:
    return bool({"tester", "content_manager", "superuser"} & set(user_roles(session)))


# -- Data I/O ---------------------------------------------------------------

DEFAULT_DATA = {"tasks": []}


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

class AssigneeInput(BaseModel):
    person_id: int
    name: str = ""
    email: str = ""


class TaskBody(BaseModel):
    title: str
    description: str = ""
    unit_id: Optional[int] = None
    deadline: str = ""  # "YYYY-MM-DD" or ""
    visibility: str = "public"  # "private" | "public"
    assignees: List[AssigneeInput] = []


class StatusBody(BaseModel):
    status: str  # "new" | "in_progress" | "completed"


def _validate_visibility(visibility: str):
    if visibility not in VISIBILITIES:
        raise HTTPException(400, f"visibility must be one of {sorted(VISIBILITIES)}")


def _validate_status(status: str):
    if status not in STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")


def _assignable_accounts() -> set:
    """Usernames (emails) of accounts that could themselves pass
    _require_staff — i.e. can actually open this app."""
    return {
        u["username"].strip().lower()
        for u in list_users()
        if (_ALLOWED_ROLES & set(u.get("roles") or [u.get("role")])) and _is_uma_email(u["username"])
    }


def _assignable_people() -> list:
    """Directory people who hold an account that can access this app —
    only they may be chosen as assignees."""
    try:
        with open(DIRECTORY_DATA_PATH, "r", encoding="utf-8") as f:
            directory = json.load(f)
    except Exception:
        return []
    accounts = _assignable_accounts()
    people = []
    for p in directory.get("people", []):
        emails = {e.strip().lower() for e in (p.get("email") or "").split(";") if e.strip()}
        if emails & accounts:
            people.append(p)
    return people


def _validate_assignees(assignees: List[AssigneeInput]):
    assignable_ids = {p["id"] for p in _assignable_people()}
    for a in assignees:
        if a.person_id not in assignable_ids:
            raise HTTPException(400, "Tasks can only be assigned to people who can access this app")


def _find_task(data: dict, task_id: str) -> dict:
    entry = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not entry:
        raise HTTPException(404, "Task not found")
    return entry


def _is_assignee(entry: dict, username: str) -> bool:
    return any(a.get("email", "").lower() == username for a in entry.get("assignees", []))


def _can_edit_task(entry: dict, session: dict) -> bool:
    username = session["username"].strip().lower()
    is_creator = entry.get("created_by", "").lower() == username
    return is_creator or _is_assignee(entry, username) or _is_senior_editor(session)


def _can_delete_task(entry: dict, session: dict) -> bool:
    username = session["username"].strip().lower()
    is_creator = entry.get("created_by", "").lower() == username
    return is_creator or _is_senior_editor(session)


def _is_visible_in_all(entry: dict, username: str) -> bool:
    if entry.get("visibility") == "public":
        return True
    is_creator = entry.get("created_by", "").lower() == username
    return is_creator or _is_assignee(entry, username)


# -- Routes ---------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers={"Cache-Control": "no-store"})


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    has_access = bool(_ALLOWED_ROLES & set(user_roles(session))) and _is_uma_email(session["username"])
    return {
        "username": session["username"],
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "has_access": has_access,
        "can_edit": has_access,
        "is_senior": _is_senior_editor(session),
    }


@router.get("/api/assignable-people")
def get_assignable_people(session: dict = Depends(_require_staff)):
    return [
        {
            "id": p["id"],
            "name": f"{p.get('first_name', '')} {p.get('family_name', '')}".strip(),
            "email": (p.get("email") or "").split(";")[0].strip(),
        }
        for p in _assignable_people()
    ]


@router.get("/api/data")
def get_data(session: dict = Depends(_require_staff)):
    data = load_data()
    username = session["username"].strip().lower()
    tasks_mine = [t for t in data["tasks"] if _is_assignee(t, username)]
    tasks_all = [t for t in data["tasks"] if _is_visible_in_all(t, username)]
    return {"tasks_mine": tasks_mine, "tasks_all": tasks_all}


@router.post("/api/tasks")
def create_task(body: TaskBody, session: dict = Depends(_require_staff)):
    _validate_visibility(body.visibility)
    _validate_assignees(body.assignees)
    data = load_data()
    now = datetime.utcnow().isoformat() + "Z"
    assignees = [
        {
            "person_id": a.person_id,
            "name": a.name,
            "email": a.email.strip().lower(),
            "status": "new",
            "updated_at": now,
        }
        for a in body.assignees
    ]
    entry = {
        "id": "task" + uuid.uuid4().hex[:8],
        "title": body.title,
        "description": body.description,
        "unit_id": body.unit_id,
        "deadline": body.deadline,
        "visibility": body.visibility,
        "created_by": session["username"].strip().lower(),
        "created_at": now,
        "updated_at": now,
        "assignees": assignees,
    }
    data["tasks"].append(entry)
    save_data(data)
    return entry


@router.put("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskBody, session: dict = Depends(_require_staff)):
    _validate_visibility(body.visibility)
    _validate_assignees(body.assignees)
    data = load_data()
    entry = _find_task(data, task_id)
    if not _can_edit_task(entry, session):
        raise HTTPException(403, "You can only edit tasks you created or are assigned to")

    now = datetime.utcnow().isoformat() + "Z"
    existing_by_person = {a["person_id"]: a for a in entry.get("assignees", [])}
    new_assignees = []
    for a in body.assignees:
        old = existing_by_person.get(a.person_id)
        new_assignees.append({
            "person_id": a.person_id,
            "name": a.name,
            "email": a.email.strip().lower(),
            "status": old["status"] if old else "new",
            "updated_at": old["updated_at"] if old else now,
        })

    entry.update({
        "title": body.title,
        "description": body.description,
        "unit_id": body.unit_id,
        "deadline": body.deadline,
        "visibility": body.visibility,
        "assignees": new_assignees,
        "updated_at": now,
    })
    save_data(data)
    return entry


@router.put("/api/tasks/{task_id}/status")
def update_my_status(task_id: str, body: StatusBody, session: dict = Depends(_require_staff)):
    _validate_status(body.status)
    data = load_data()
    entry = _find_task(data, task_id)
    username = session["username"].strip().lower()
    assignee = next((a for a in entry.get("assignees", []) if a.get("email", "").lower() == username), None)
    if not assignee:
        raise HTTPException(403, "You are not assigned to this task")
    assignee["status"] = body.status
    assignee["updated_at"] = datetime.utcnow().isoformat() + "Z"
    entry["updated_at"] = assignee["updated_at"]
    save_data(data)
    return entry


@router.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, session: dict = Depends(_require_staff)):
    data = load_data()
    entry = _find_task(data, task_id)
    if not _can_delete_task(entry, session):
        raise HTTPException(403, "You can only delete tasks you created")
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    save_data(data)
    return {"ok": True}
