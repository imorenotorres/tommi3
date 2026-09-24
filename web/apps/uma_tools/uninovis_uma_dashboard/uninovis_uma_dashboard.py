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
    # name/email are never taken from the client — see _directory_display_name
    # and _email_for_person_id — so they can't go stale here either.
    status: Optional[str] = None  # honored on create, and on update only for
    # the current assignee or a superuser — see _resolve_assignee_status


class TaskBody(BaseModel):
    title: str
    description: str = ""
    unit_id: Optional[int] = None
    # On PUT, omitting `unit_id` leaves the existing unit untouched; this is
    # the only way to explicitly remove it. Same rationale as
    # clear_assignee below — a stale/out-of-date unit dropdown must not be
    # able to silently clear a task's unit.
    clear_unit: bool = False
    deadline: str = ""  # "YYYY-MM-DD" or ""
    visibility: str = "public"  # "private" | "public"
    assignee: Optional[AssigneeInput] = None
    # On PUT, omitting `assignee` leaves the existing assignee untouched;
    # this is the only way to explicitly remove it. Prevents a stale client
    # (e.g. an out-of-date assignee dropdown) from silently unassigning a
    # task just because it couldn't resolve the assignee to resend.
    clear_assignee: bool = False
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
    # name is never accepted from the client — see _directory_display_name.
    email: str


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
    clear_unit: bool = False  # see TaskBody.clear_unit
    deadline: str = ""
    visibility: str = "public"
    assignee: Optional[AssigneeInput] = None
    clear_assignee: bool = False  # see TaskBody.clear_assignee
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


def _directory_display_name(email: str) -> str:
    """Resolve a person's display name from the WP1 staff directory by
    email, falling back to a title-cased guess from the email's local part
    when they're not listed there.

    A dashboard assignee's name is never stored — it's always resolved this
    way, on every read, so editing someone's entry in the directory is
    immediately reflected everywhere they're shown (settings, the "choose
    other" filter, "assigned to" on tasks/contacts) without anyone having to
    touch the dashboard's own assignee list.
    """
    if not email:
        return ""
    from app import _check_directory_email  # see auth_check for why this is a local import
    name = _check_directory_email(email)
    if name:
        return name
    local = email.split("@", 1)[0]
    words = [w for w in re.split(r"[._-]+", local) if w]
    return " ".join(w.capitalize() for w in words) or email


def _is_eligible_assignee_email(email: str) -> bool:
    """Whether `email` belongs to a platform account with actual dashboard
    access (uninovis_staff/content_manager/superuser + @uma.es) — the only
    people allowed to be added as a dashboard assignee."""
    email = email.strip().lower()
    user = next((u for u in list_users() if u["username"].lower() == email), None)
    if not user:
        return False
    return bool(_ALLOWED_ROLES & set(user.get("roles", [user.get("role")]))) and _is_uma_email(email)


def _hydrate_assignee(assignee: Optional[dict]) -> Optional[dict]:
    """Return a copy of a stored assignee sub-object with `name` freshly
    resolved from the directory instead of trusting whatever was persisted."""
    if not assignee:
        return assignee
    out = dict(assignee)
    out["name"] = _directory_display_name(assignee.get("email", ""))
    return out


def _hydrate_entry(entry: dict) -> dict:
    """Return a copy of a task/contact with its assignee's name refreshed
    from the directory before it's sent to the client."""
    out = dict(entry)
    out["assignee"] = _hydrate_assignee(entry.get("assignee"))
    return out


def _assignees_with_names() -> list:
    """The dashboard-assignee directory (id/email) with each person's name
    freshly resolved — never the other way around, see _directory_display_name."""
    return [
        {"id": a["id"], "email": a.get("email", ""), "name": _directory_display_name(a.get("email", ""))}
        for a in load_assignees()["assignees"]
    ]


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
    # Imported lazily: app.py imports this router at module load time, so a
    # top-level `from app import ...` here would be a circular import.
    from app import resolve_display_name

    has_access = bool(_ALLOWED_ROLES & set(user_roles(session))) and _is_uma_email(session["username"])
    return {
        "username": session["username"],
        "name": resolve_display_name(session["username"]),
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "has_access": has_access,
        "can_edit": has_access,
        "is_senior": _is_senior_editor(session),
        "is_admin": has_access and "superuser" in set(user_roles(session)),
    }


@router.get("/api/assignable-people")
def get_assignable_people(session: dict = Depends(_require_staff)):
    return _assignees_with_names()


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
        "tasks_mine": [_hydrate_entry(t) for t in tasks_mine],
        "tasks_all": [_hydrate_entry(t) for t in tasks_all],
        "contacts_mine": [_hydrate_entry(c) for c in contacts_mine],
        "contacts_all": [_hydrate_entry(c) for c in contacts_all],
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
            "email": _email_for_person_id(body.assignee.person_id),
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
    return _hydrate_entry(entry)


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
    if body.assignee:
        status, status_updated_at = _resolve_assignee_status(old_assignee, body.assignee, session, now)
        new_assignee = {
            "person_id": body.assignee.person_id,
            "email": _email_for_person_id(body.assignee.person_id),
            "status": status,
            "updated_at": status_updated_at,
        }
    elif body.clear_assignee:
        new_assignee = None
    else:
        new_assignee = old_assignee

    if body.unit_id:
        new_unit_id = body.unit_id
    elif body.clear_unit:
        new_unit_id = None
    else:
        new_unit_id = entry.get("unit_id")

    entry.update({
        "title": body.title,
        "description": body.description,
        "unit_id": new_unit_id,
        "deadline": body.deadline,
        "visibility": body.visibility,
        "link": body.link,
        "assignee": new_assignee,
        "updated_at": now,
    })
    save_data(data)
    return _hydrate_entry(entry)


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
    return _hydrate_entry(entry)


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

def _contact_dict(body: ContactBody, assignee: Optional[dict], unit_id: Optional[int]) -> dict:
    return {
        "unit_id": unit_id,
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
            "email": _email_for_person_id(body.assignee.person_id),
            "status": status_id,
            "updated_at": now,
        }
    entry = _contact_dict(body, assignee, body.unit_id)
    entry.update({
        "id": "contact" + uuid.uuid4().hex[:8],
        "kind": "contact",
        "created_by": session["username"].strip().lower(),
        "created_at": now,
        "updated_at": now,
    })
    data["contacts"].append(entry)
    save_contacts(data)
    return _hydrate_entry(entry)


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
    if body.assignee:
        status, status_updated_at = _resolve_assignee_status(old_assignee, body.assignee, session, now)
        new_assignee = {
            "person_id": body.assignee.person_id,
            "email": _email_for_person_id(body.assignee.person_id),
            "status": status,
            "updated_at": status_updated_at,
        }
    elif body.clear_assignee:
        new_assignee = None
    else:
        new_assignee = old_assignee

    if body.unit_id:
        new_unit_id = body.unit_id
    elif body.clear_unit:
        new_unit_id = None
    else:
        new_unit_id = entry.get("unit_id")

    entry.update(_contact_dict(body, new_assignee, new_unit_id))
    entry["updated_at"] = now
    save_contacts(data)
    return _hydrate_entry(entry)


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
    return _hydrate_entry(entry)


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
#
# An assignee entry stores only {id, email} — never a name. Every read
# resolves the name fresh from the WP1 staff directory (see
# _directory_display_name), so editing someone's directory entry is
# reflected everywhere immediately, with nothing to keep in sync by hand.
# Entries can only be added (from the pool of staff who actually have
# dashboard access) or removed — never renamed/re-emailed in place.

@router.get("/api/dashboard-assignees")
def get_dashboard_assignees(session: dict = Depends(_require_staff)):
    return _assignees_with_names()


@router.get("/api/eligible-assignee-users")
def get_eligible_assignee_users(session: dict = Depends(_require_superuser_uma)):
    """Platform accounts that could be added as a dashboard assignee: UMA
    staff (uninovis_staff/content_manager/superuser) with a @uma.es login,
    minus anyone already in the assignee directory. Backs the "add from
    directory" dropdown so only people with actual dashboard access can be
    assigned tasks."""
    existing_emails = {a["email"].lower() for a in load_assignees()["assignees"] if a.get("email")}
    eligible = [
        {"username": u["username"], "name": _directory_display_name(u["username"])}
        for u in list_users()
        if (_ALLOWED_ROLES & set(u.get("roles", [u.get("role")])))
        and _is_uma_email(u["username"])
        and u["username"].lower() not in existing_emails
    ]
    eligible.sort(key=lambda u: u["name"].lower())
    return eligible


@router.post("/api/dashboard-assignees")
def create_dashboard_assignee(body: AssigneeConfigBody, session: dict = Depends(_require_superuser_uma)):
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(400, "Assignee email is required")
    if not _is_eligible_assignee_email(email):
        raise HTTPException(400, "Only uninovis_staff (UMA) accounts can be added as assignees")
    data = load_assignees()
    if any(a.get("email", "").lower() == email for a in data["assignees"]):
        raise HTTPException(400, "This person is already an assignee")
    new_id = max([a["id"] for a in data["assignees"]], default=0) + 1
    entry = {"id": new_id, "email": email}
    data["assignees"].append(entry)
    save_assignees(data)
    return {"id": new_id, "email": email, "name": _directory_display_name(email)}


@router.put("/api/dashboard-assignees/order")
def reorder_dashboard_assignees(body: AssigneeConfigOrderBody, session: dict = Depends(_require_superuser_uma)):
    data = load_assignees()
    current_ids = {a["id"] for a in data["assignees"]}
    if set(body.order) != current_ids or len(body.order) != len(data["assignees"]):
        raise HTTPException(400, "Order must include exactly the current assignee ids")
    by_id = {a["id"]: a for a in data["assignees"]}
    data["assignees"] = [by_id[i] for i in body.order]
    save_assignees(data)
    return _assignees_with_names()


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
