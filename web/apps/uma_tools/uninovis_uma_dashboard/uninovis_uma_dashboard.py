"""
UNINOVIS-UMA Dashboard — a personal to-do manager for UMA/UNINOVIS staff.

Each task can be linked to a unit (from dashboard_units.json) and assigned to
at most one directory person. The assignee tracks their own status, chosen
from the configurable list in status.json; superusers may also update the
status of any task or contact. Both status.json and dashboard_units.json
are editable only by superusers with a @uma.es login.
"""

import json
import os
import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "tasks.json")
CONTACTS_PATH = os.path.join(os.path.dirname(__file__), "contacts.json")
STATUS_PATH = os.path.join(os.path.dirname(__file__), "status.json")
UNITS_PATH = os.path.join(os.path.dirname(__file__), "dashboard_units.json")
ASSIGNEES_PATH = os.path.join(os.path.dirname(__file__), "dashboard_assignees.json")

router = APIRouter(prefix="/uninovis-uma-dashboard", tags=["uninovis_uma_dashboard"])

VISIBILITIES = {"private", "public"}
_SLUG_RE = re.compile(r"^[a-z0-9_]{1,40}$")


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


def _require_superuser_uma(session: dict = Depends(_require_auth)) -> dict:
    """Editing statuses/units is restricted to superusers with a @uma.es login."""
    if "superuser" not in set(user_roles(session)) or not _is_uma_email(session["username"]):
        raise HTTPException(status_code=403, detail="superuser (UMA) access only")
    return session


def _is_senior_editor(session: dict) -> bool:
    return bool({"tester", "content_manager", "superuser"} & set(user_roles(session)))


# -- Data I/O ---------------------------------------------------------------

DEFAULT_DATA = {"tasks": []}
DEFAULT_CONTACTS = {"contacts": []}
DEFAULT_STATUSES = {
    "statuses": [
        {"id": "new", "label": "New", "color": "#757575"},
        {"id": "in_progress", "label": "In progress", "color": "#0277bd"},
        {"id": "completed", "label": "Completed", "color": "#2e7d32"},
    ]
}
DEFAULT_UNITS = {"units": []}
DEFAULT_ASSIGNEES = {"assignees": []}


def load_data() -> dict:
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA.copy())
        return json.loads(json.dumps(DEFAULT_DATA))
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_contacts() -> dict:
    if not os.path.exists(CONTACTS_PATH):
        save_contacts(DEFAULT_CONTACTS.copy())
        return json.loads(json.dumps(DEFAULT_CONTACTS))
    with open(CONTACTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_contacts(data: dict):
    with open(CONTACTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_statuses() -> dict:
    if not os.path.exists(STATUS_PATH):
        save_statuses(DEFAULT_STATUSES.copy())
        return json.loads(json.dumps(DEFAULT_STATUSES))
    with open(STATUS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_statuses(data: dict):
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _status_ids() -> set:
    return {s["id"] for s in load_statuses()["statuses"]}


def _default_status_id() -> str:
    statuses = load_statuses()["statuses"]
    return statuses[0]["id"] if statuses else "new"


def load_units() -> dict:
    if not os.path.exists(UNITS_PATH):
        save_units(DEFAULT_UNITS.copy())
        return json.loads(json.dumps(DEFAULT_UNITS))
    with open(UNITS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_units(data: dict):
    with open(UNITS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_assignees() -> dict:
    if not os.path.exists(ASSIGNEES_PATH):
        save_assignees(DEFAULT_ASSIGNEES.copy())
        return json.loads(json.dumps(DEFAULT_ASSIGNEES))
    with open(ASSIGNEES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_assignees(data: dict):
    with open(ASSIGNEES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -- Models ---------------------------------------------------------------

class AssigneeInput(BaseModel):
    person_id: int
    name: str = ""
    email: str = ""
    status: Optional[str] = None  # honored on create, and on update only for
    # the current assignee or a superuser — see _resolve_assignee_status


class TaskBody(BaseModel):
    title: str
    description: str = ""
    unit_id: Optional[int] = None
    deadline: str = ""  # "YYYY-MM-DD" or ""
    visibility: str = "public"  # "private" | "public"
    assignee: Optional[AssigneeInput] = None
    link: str = ""  # must start with "http://" or "https://" if set


class StatusBody(BaseModel):
    status: str


class StatusEntryBody(BaseModel):
    id: str
    label: str
    color: str = "#757575"


class StatusUpdateBody(BaseModel):
    label: str
    color: str = "#757575"


class StatusOrderBody(BaseModel):
    order: List[str]


class UnitBody(BaseModel):
    name: str


class AssigneeConfigBody(BaseModel):
    name: str
    email: str = ""


class AssigneeConfigOrderBody(BaseModel):
    order: List[int]


# A "contact" carries every task field plus everything tracked for an
# exploratory contact in the Collaboration Dashboard app — except that
# app's own status, which is replaced here by the shared status.json list.
class ContactCollaborator(BaseModel):
    name: str
    email: str = ""
    institution: str = ""
    area_of_interest: str = ""


class ContactMobilityVisit(BaseModel):
    collaborator_name: str = ""
    start_date: str = ""  # "YYYY-MM-DD"
    end_date: str = ""    # "YYYY-MM-DD"
    notes: str = ""


class ContactVirtualMeeting(BaseModel):
    date: str = ""  # "YYYY-MM-DD"
    notes: str = ""


class ContactBody(BaseModel):
    title: str
    description: str = ""
    unit_id: Optional[int] = None
    deadline: str = ""
    visibility: str = "public"
    assignee: Optional[AssigneeInput] = None
    link: str = ""  # must start with "http://" or "https://" if set
    goal: str = ""
    collaborators: List[ContactCollaborator] = []
    physical_mobility: bool = False
    mobility_visits: List[ContactMobilityVisit] = []
    virtual_meetings_held: bool = False
    virtual_meetings: List[ContactVirtualMeeting] = []


def _validate_visibility(visibility: str):
    if visibility not in VISIBILITIES:
        raise HTTPException(400, f"visibility must be one of {sorted(VISIBILITIES)}")


def _validate_status(status: str):
    if status not in _status_ids():
        raise HTTPException(400, f"status must be one of {sorted(_status_ids())}")


def _validate_link(link: str):
    if link and not link.startswith(("http://", "https://")):
        raise HTTPException(400, "Link must start with http:// or https://")


def _validate_assignee(assignee: Optional[AssigneeInput]):
    if assignee is None:
        return
    assignable_ids = {a["id"] for a in load_assignees()["assignees"]}
    if assignee.person_id not in assignable_ids:
        raise HTTPException(400, "Unknown assignee id")


def _resolve_assignee_status(old_assignee: Optional[dict], body_assignee: AssigneeInput, session: dict, now: str):
    """Decide the status/updated_at for an assignee on a task/contact PUT.

    A status included in the request body is only honored when the caller
    is the person currently assigned (and stays assigned) or a superuser —
    the same rule as the dedicated .../status endpoints. Anyone else's
    submitted status is silently ignored so they can't bump someone else's
    progress just by resubmitting the edit form.
    """
    username = session["username"].strip().lower()
    is_admin = "superuser" in set(user_roles(session))
    keep_progress = bool(old_assignee) and old_assignee["person_id"] == body_assignee.person_id
    is_current_assignee = keep_progress and old_assignee.get("email", "").lower() == username
    if body_assignee.status is not None and keep_progress and (is_admin or is_current_assignee):
        _validate_status(body_assignee.status)
        return body_assignee.status, now
    if keep_progress:
        return old_assignee["status"], old_assignee["updated_at"]
    return _default_status_id(), now


def _find_task(data: dict, task_id: str) -> dict:
    entry = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not entry:
        raise HTTPException(404, "Task not found")
    return entry


def _find_contact(data: dict, contact_id: str) -> dict:
    entry = next((c for c in data["contacts"] if c["id"] == contact_id), None)
    if not entry:
        raise HTTPException(404, "Contact not found")
    return entry


def _email_for_person_id(person_id) -> str:
    """Look up the stored email for a dashboard assignee by their id."""
    person = next(
        (p for p in load_assignees().get("assignees", []) if p["id"] == person_id),
        None
    )
    return (person.get("email", "") if person else "").lower()


def _is_assignee(entry: dict, username: str) -> bool:
    a = entry.get("assignee")
    if not a:
        return False
    if a.get("email", "").lower() == username:
        return True
    # Also match by person_id for tasks assigned via the dropdown (email may be empty)
    user_person = next(
        (p for p in load_assignees().get("assignees", []) if p.get("email", "").lower() == username),
        None
    )
    return user_person is not None and a.get("person_id") == user_person["id"]


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
    users = {u["username"]: u for u in list_users()}
    user_name = users.get(session["username"], {}).get("name", "")
    return {
        "username": session["username"],
        "name": user_name,
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "has_access": has_access,
        "can_edit": has_access,
        "is_senior": _is_senior_editor(session),
        "is_admin": has_access and "superuser" in set(user_roles(session)),
    }


@router.get("/api/assignable-people")
def get_assignable_people(session: dict = Depends(_require_staff)):
    return load_assignees()["assignees"]


@router.get("/api/data")
def get_data(session: dict = Depends(_require_staff)):
    data = load_data()
    contacts_data = load_contacts()
    username = session["username"].strip().lower()
    tasks_mine = [t for t in data["tasks"] if _is_assignee(t, username)]
    tasks_all = [t for t in data["tasks"] if _is_visible_in_all(t, username)]
    contacts_mine = [c for c in contacts_data["contacts"] if _is_assignee(c, username)]
    contacts_all = [c for c in contacts_data["contacts"] if _is_visible_in_all(c, username)]
    institutions = sorted({
        p.get("institution", "").strip()
        for c in contacts_data["contacts"]
        for p in c.get("collaborators", [])
        if p.get("institution", "").strip()
    })
    areas_of_interest = sorted({
        p.get("area_of_interest", "").strip()
        for c in contacts_data["contacts"]
        for p in c.get("collaborators", [])
        if p.get("area_of_interest", "").strip()
    })
    return {
        "tasks_mine": tasks_mine,
        "tasks_all": tasks_all,
        "contacts_mine": contacts_mine,
        "contacts_all": contacts_all,
        "contact_institutions": institutions,
        "contact_areas_of_interest": areas_of_interest,
    }


@router.post("/api/tasks")
def create_task(body: TaskBody, session: dict = Depends(_require_staff)):
    _validate_visibility(body.visibility)
    _validate_assignee(body.assignee)
    _validate_link(body.link)
    data = load_data()
    now = datetime.utcnow().isoformat() + "Z"
    assignee = None
    if body.assignee:
        status_id = body.assignee.status or _default_status_id()
        _validate_status(status_id)
        assignee = {
            "person_id": body.assignee.person_id,
            "name": body.assignee.name,
            "email": body.assignee.email.strip().lower() or _email_for_person_id(body.assignee.person_id),
            "status": status_id,
            "updated_at": now,
        }
    entry = {
        "id": "task" + uuid.uuid4().hex[:8],
        "kind": "task",
        "title": body.title,
        "description": body.description,
        "unit_id": body.unit_id,
        "deadline": body.deadline,
        "visibility": body.visibility,
        "link": body.link,
        "created_by": session["username"].strip().lower(),
        "created_at": now,
        "updated_at": now,
        "assignee": assignee,
    }
    data["tasks"].append(entry)
    save_data(data)
    return entry


@router.put("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskBody, session: dict = Depends(_require_staff)):
    _validate_visibility(body.visibility)
    _validate_assignee(body.assignee)
    _validate_link(body.link)
    data = load_data()
    entry = _find_task(data, task_id)
    if not _can_edit_task(entry, session):
        raise HTTPException(403, "You can only edit tasks you created or are assigned to")
    now = datetime.utcnow().isoformat() + "Z"
    old_assignee = entry.get("assignee")
    new_assignee = None
    if body.assignee:
        status, status_updated_at = _resolve_assignee_status(old_assignee, body.assignee, session, now)
        new_assignee = {
            "person_id": body.assignee.person_id,
            "name": body.assignee.name,
            "email": body.assignee.email.strip().lower() or _email_for_person_id(body.assignee.person_id),
            "status": status,
            "updated_at": status_updated_at,
        }

    entry.update({
        "title": body.title,
        "description": body.description,
        "unit_id": body.unit_id,
        "deadline": body.deadline,
        "visibility": body.visibility,
        "link": body.link,
        "assignee": new_assignee,
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
    assignee = entry.get("assignee")
    is_admin = "superuser" in set(user_roles(session))
    if not assignee or (assignee.get("email", "").lower() != username and not is_admin):
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


# -- Contacts ---------------------------------------------------------------

def _contact_dict(body: ContactBody, assignee: Optional[dict]) -> dict:
    return {
        "unit_id": body.unit_id,
        "deadline": body.deadline,
        "visibility": body.visibility,
        "assignee": assignee,
        "title": body.title,
        "description": body.description,
        "link": body.link,
        "goal": body.goal,
        "collaborators": [c.model_dump() for c in body.collaborators],
        "physical_mobility": body.physical_mobility,
        "mobility_visits": [m.model_dump() for m in body.mobility_visits],
        "virtual_meetings_held": body.virtual_meetings_held,
        "virtual_meetings": [m.model_dump() for m in body.virtual_meetings],
    }


@router.post("/api/contacts")
def create_contact(body: ContactBody, session: dict = Depends(_require_staff)):
    _validate_visibility(body.visibility)
    _validate_assignee(body.assignee)
    _validate_link(body.link)
    data = load_contacts()
    now = datetime.utcnow().isoformat() + "Z"
    assignee = None
    if body.assignee:
        status_id = body.assignee.status or _default_status_id()
        _validate_status(status_id)
        assignee = {
            "person_id": body.assignee.person_id,
            "name": body.assignee.name,
            "email": body.assignee.email.strip().lower() or _email_for_person_id(body.assignee.person_id),
            "status": status_id,
            "updated_at": now,
        }
    entry = _contact_dict(body, assignee)
    entry.update({
        "id": "contact" + uuid.uuid4().hex[:8],
        "kind": "contact",
        "created_by": session["username"].strip().lower(),
        "created_at": now,
        "updated_at": now,
    })
    data["contacts"].append(entry)
    save_contacts(data)
    return entry


@router.put("/api/contacts/{contact_id}")
def update_contact(contact_id: str, body: ContactBody, session: dict = Depends(_require_staff)):
    _validate_visibility(body.visibility)
    _validate_assignee(body.assignee)
    _validate_link(body.link)
    data = load_contacts()
    entry = _find_contact(data, contact_id)
    if not _can_edit_task(entry, session):
        raise HTTPException(403, "You can only edit contacts you created or are assigned to")

    now = datetime.utcnow().isoformat() + "Z"
    old_assignee = entry.get("assignee")
    new_assignee = None
    if body.assignee:
        status, status_updated_at = _resolve_assignee_status(old_assignee, body.assignee, session, now)
        new_assignee = {
            "person_id": body.assignee.person_id,
            "name": body.assignee.name,
            "email": body.assignee.email.strip().lower() or _email_for_person_id(body.assignee.person_id),
            "status": status,
            "updated_at": status_updated_at,
        }

    entry.update(_contact_dict(body, new_assignee))
    entry["updated_at"] = now
    save_contacts(data)
    return entry


@router.put("/api/contacts/{contact_id}/status")
def update_my_contact_status(contact_id: str, body: StatusBody, session: dict = Depends(_require_staff)):
    _validate_status(body.status)
    data = load_contacts()
    entry = _find_contact(data, contact_id)
    username = session["username"].strip().lower()
    assignee = entry.get("assignee")
    is_admin = "superuser" in set(user_roles(session))
    if not assignee or (assignee.get("email", "").lower() != username and not is_admin):
        raise HTTPException(403, "You are not assigned to this contact")
    assignee["status"] = body.status
    assignee["updated_at"] = datetime.utcnow().isoformat() + "Z"
    entry["updated_at"] = assignee["updated_at"]
    save_contacts(data)
    return entry


@router.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: str, session: dict = Depends(_require_staff)):
    data = load_contacts()
    entry = _find_contact(data, contact_id)
    if not _can_delete_task(entry, session):
        raise HTTPException(403, "You can only delete contacts you created")
    data["contacts"] = [c for c in data["contacts"] if c["id"] != contact_id]
    save_contacts(data)
    return {"ok": True}


# -- Statuses (superuser/UMA editable) ---------------------------------------------------------------

@router.get("/api/statuses")
def get_statuses(session: dict = Depends(_require_staff)):
    return load_statuses()["statuses"]


@router.post("/api/statuses")
def create_status(body: StatusEntryBody, session: dict = Depends(_require_superuser_uma)):
    status_id = body.id.strip().lower()
    if not _SLUG_RE.match(status_id):
        raise HTTPException(400, "id must be lowercase letters, digits, or underscores")
    data = load_statuses()
    if any(s["id"] == status_id for s in data["statuses"]):
        raise HTTPException(400, "A status with this id already exists")
    data["statuses"].append({"id": status_id, "label": body.label.strip() or status_id, "color": body.color})
    save_statuses(data)
    return data["statuses"]


@router.put("/api/statuses/order")
def reorder_statuses(body: StatusOrderBody, session: dict = Depends(_require_superuser_uma)):
    data = load_statuses()
    current_ids = {s["id"] for s in data["statuses"]}
    if set(body.order) != current_ids or len(body.order) != len(data["statuses"]):
        raise HTTPException(400, "Order must include exactly the current status ids")
    by_id = {s["id"]: s for s in data["statuses"]}
    data["statuses"] = [by_id[i] for i in body.order]
    save_statuses(data)
    return data["statuses"]


@router.put("/api/statuses/{status_id}")
def update_status(status_id: str, body: StatusUpdateBody, session: dict = Depends(_require_superuser_uma)):
    data = load_statuses()
    entry = next((s for s in data["statuses"] if s["id"] == status_id), None)
    if not entry:
        raise HTTPException(404, "Status not found")
    entry["label"] = body.label.strip() or entry["label"]
    entry["color"] = body.color
    save_statuses(data)
    return data["statuses"]


@router.delete("/api/statuses/{status_id}")
def delete_status(status_id: str, session: dict = Depends(_require_superuser_uma)):
    status_data = load_statuses()
    if len(status_data["statuses"]) <= 1:
        raise HTTPException(400, "At least one status must remain")
    if not any(s["id"] == status_id for s in status_data["statuses"]):
        raise HTTPException(404, "Status not found")
    task_data = load_data()
    contact_data = load_contacts()
    in_use = (
        any(t.get("assignee") and t["assignee"].get("status") == status_id for t in task_data["tasks"])
        or any(c.get("assignee") and c["assignee"].get("status") == status_id for c in contact_data["contacts"])
    )
    if in_use:
        raise HTTPException(400, "Cannot delete a status that is currently in use by a task or contact")
    status_data["statuses"] = [s for s in status_data["statuses"] if s["id"] != status_id]
    save_statuses(status_data)
    return status_data["statuses"]


# -- Units (superuser/UMA editable) ---------------------------------------------------------------

@router.get("/api/dashboard-units")
def get_dashboard_units(session: dict = Depends(_require_staff)):
    return sorted(load_units()["units"], key=lambda u: u["name"].lower())


@router.post("/api/dashboard-units")
def create_dashboard_unit(body: UnitBody, session: dict = Depends(_require_superuser_uma)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Unit name is required")
    data = load_units()
    new_id = max([u["id"] for u in data["units"]], default=0) + 1
    entry = {"id": new_id, "name": name}
    data["units"].append(entry)
    save_units(data)
    return entry


@router.put("/api/dashboard-units/{unit_id}")
def update_dashboard_unit(unit_id: int, body: UnitBody, session: dict = Depends(_require_superuser_uma)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Unit name is required")
    data = load_units()
    entry = next((u for u in data["units"] if u["id"] == unit_id), None)
    if not entry:
        raise HTTPException(404, "Unit not found")
    entry["name"] = name
    save_units(data)
    return entry


@router.delete("/api/dashboard-units/{unit_id}")
def delete_dashboard_unit(unit_id: int, session: dict = Depends(_require_superuser_uma)):
    data = load_units()
    if not any(u["id"] == unit_id for u in data["units"]):
        raise HTTPException(404, "Unit not found")
    data["units"] = [u for u in data["units"] if u["id"] != unit_id]
    save_units(data)

    task_data = load_data()
    changed = False
    for t in task_data["tasks"]:
        if t.get("unit_id") == unit_id:
            t["unit_id"] = None
            changed = True
    if changed:
        save_data(task_data)

    contact_data = load_contacts()
    contacts_changed = False
    for c in contact_data["contacts"]:
        if c.get("unit_id") == unit_id:
            c["unit_id"] = None
            contacts_changed = True
    if contacts_changed:
        save_contacts(contact_data)

    return {"ok": True}


# -- Dashboard assignees (superuser/UMA editable) ---------------------------------------------------------------

@router.get("/api/dashboard-assignees")
def get_dashboard_assignees(session: dict = Depends(_require_staff)):
    return load_assignees()["assignees"]


@router.post("/api/dashboard-assignees")
def create_dashboard_assignee(body: AssigneeConfigBody, session: dict = Depends(_require_superuser_uma)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Assignee name is required")
    data = load_assignees()
    new_id = max([a["id"] for a in data["assignees"]], default=0) + 1
    entry = {"id": new_id, "name": name, "email": body.email.strip().lower()}
    data["assignees"].append(entry)
    save_assignees(data)
    return entry


@router.put("/api/dashboard-assignees/order")
def reorder_dashboard_assignees(body: AssigneeConfigOrderBody, session: dict = Depends(_require_superuser_uma)):
    data = load_assignees()
    current_ids = {a["id"] for a in data["assignees"]}
    if set(body.order) != current_ids or len(body.order) != len(data["assignees"]):
        raise HTTPException(400, "Order must include exactly the current assignee ids")
    by_id = {a["id"]: a for a in data["assignees"]}
    data["assignees"] = [by_id[i] for i in body.order]
    save_assignees(data)
    return data["assignees"]


@router.put("/api/dashboard-assignees/{assignee_id}")
def update_dashboard_assignee(assignee_id: int, body: AssigneeConfigBody, session: dict = Depends(_require_superuser_uma)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Assignee name is required")
    data = load_assignees()
    entry = next((a for a in data["assignees"] if a["id"] == assignee_id), None)
    if not entry:
        raise HTTPException(404, "Assignee not found")
    entry["name"] = name
    entry["email"] = body.email.strip().lower()
    save_assignees(data)
    return entry


@router.delete("/api/dashboard-assignees/{assignee_id}")
def delete_dashboard_assignee(assignee_id: int, session: dict = Depends(_require_superuser_uma)):
    data = load_assignees()
    if not any(a["id"] == assignee_id for a in data["assignees"]):
        raise HTTPException(404, "Assignee not found")
    task_data = load_data()
    contact_data = load_contacts()
    in_use = (
        any(t.get("assignee") and t["assignee"].get("person_id") == assignee_id for t in task_data["tasks"])
        or any(c.get("assignee") and c["assignee"].get("person_id") == assignee_id for c in contact_data["contacts"])
    )
    if in_use:
        raise HTTPException(400, "Cannot delete an assignee that is currently assigned to a task or contact")
    data["assignees"] = [a for a in data["assignees"] if a["id"] != assignee_id]
    save_assignees(data)
    return {"ok": True}
