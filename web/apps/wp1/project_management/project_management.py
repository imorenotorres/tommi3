"""
UNINOVIS Project Management — task tracker connected to the Event Tracker.

Tasks are created by hand, or automatically whenever an event is created in
the Event Tracker (see the on_event_* hooks below, called from
apps/wp1/event_tracker/event_tracker.py):

  - "Complete Event information" — when a new event has missing fields, for
    the content manager(s) of the organising university.
  - "Review New Event" — when a new event is related to a work package
    (a WPn category, or a WPn UNINOVIS group), for that WP's leader(s).

Assignees are taken from the Directory (apps/wp1/directory/data.json) and
cross-checked against the platform's user accounts (the content_manager /
wp_leader roles in web/data/users.json). Each assignee keeps a record of
which sources confirmed them, so an unverified or missing assignment is
visible in the UI instead of being silently dropped.

Data is stored in the local data.json next to this file.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "directory", "data.json")

router = APIRouter(prefix="/project-management", tags=["project_management"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

from auth import (
    require_login as _require_login, can_edit as _can_edit_check,
    user_roles as _user_roles, list_users as _list_users,
    can_access_tool as _can_access_tool,
)

TOOL_ID = "project_management"


def _require_auth(session: dict = Depends(_require_login)) -> dict:
    """Logged in AND granted this tool in the Tool Visibility panel. With no
    entry there yet, can_access_tool() allows superusers only."""
    if not _can_access_tool(session, TOOL_ID):
        raise HTTPException(403, "You do not have access to Project Management")
    return session

# Roles that may create manual tasks and see the whole team's workload.
# wp_leader is included (unlike EDITOR_ROLES) since WP leaders are the
# people "Review New Event" tasks are addressed to.
_MANAGER_ROLES = {"content_manager", "superuser"}


def _can_create(session: dict) -> bool:
    return _can_edit_check(session) or "wp_leader" in set(_user_roles(session))


def _is_manager(session: dict) -> bool:
    return bool(_MANAGER_ROLES & set(_user_roles(session)))


def _username(session: dict) -> str:
    return (session.get("username") or "").strip().lower()


def _can_update_status(session: dict, task: dict) -> bool:
    """Assignees, the task's creator, and content managers/superusers may move a task."""
    if _is_manager(session):
        return True
    me = _username(session)
    return me in task.get("assignees", []) or me == (task.get("created_by") or "").lower()


def _can_edit_task(session: dict, task: dict) -> bool:
    """Editing a task's title/assignees/etc.: its creator or a content manager/superuser.
    Auto-generated tasks (created_by "system") are editable by managers only."""
    if _is_manager(session):
        return True
    return _username(session) == (task.get("created_by") or "").lower()


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------

STATUSES = ["todo", "in_progress", "done", "cancelled"]
PRIORITIES = ["low", "normal", "high"]

KIND_COMPLETE_INFO = "complete_event_info"
KIND_REVIEW_EVENT = "review_event"
KIND_MANUAL = "manual"

DEFAULT_DATA = {"tasks": []}


def load_data() -> dict:
    if not os.path.exists(DATA_PATH):
        save_data({"tasks": []})
        return {"tasks": []}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _new_task(**fields) -> dict:
    task = {
        "id": "tsk" + str(uuid.uuid4())[:8],
        "title": "",
        "description": "",
        "kind": KIND_MANUAL,
        "status": "todo",
        "priority": "normal",
        "due_date": "",
        "assignees": [],
        "assignee_checks": [],
        "assignment_note": "",
        "event_id": "",
        "series_id": "",
        "event_name": "",
        "university": "",
        "wp": "",
        "missing_fields": [],
        "created_by": "system",
        "created_at": _now(),
        "updated_at": _now(),
        "completed_at": "",
        "history": [],
    }
    task.update(fields)
    return task


def _log(task: dict, who: str, text: str):
    task.setdefault("history", []).append({"at": _now(), "by": who, "text": text})
    task["updated_at"] = _now()


def _set_status(task: dict, status: str, who: str, reason: str = ""):
    if task.get("status") == status:
        return
    old = task.get("status", "")
    task["status"] = status
    task["auto_closed"] = False
    task["completed_at"] = _now() if status == "done" else ""
    _log(task, who, f"Status {old} → {status}" + (f" ({reason})" if reason else ""))


# ---------------------------------------------------------------------------
# Directory lookup + cross-check against platform accounts
# ---------------------------------------------------------------------------

_WP_RE = re.compile(r"^\s*WP\s*(\d+)\b", re.IGNORECASE)
_CONTENT_MANAGER_RE = re.compile(r"content\s*manager", re.IGNORECASE)
_LEADER_RE = re.compile(r"\blead(er)?\b", re.IGNORECASE)


def _wp_code(name: str) -> str:
    """'WP3', 'wp 3 – Research', 'WP3: Research & Innovation' -> 'WP3'; anything else -> ''."""
    m = _WP_RE.match(name or "")
    return f"WP{int(m.group(1))}" if m else ""


def _load_directory() -> dict:
    if not os.path.exists(DIRECTORY_DATA_PATH):
        return {"people": [], "units": [], "memberships": []}
    with open(DIRECTORY_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _platform_roles() -> dict:
    """Lower-cased username/email -> set of platform roles."""
    try:
        return {u["username"].strip().lower(): set(u.get("roles") or [u.get("role")]) for u in _list_users()}
    except Exception:
        logger.exception("Could not read platform users for assignee cross-check")
        return {}


def _person_label(person: dict | None, email: str) -> str:
    if not person:
        return email
    name = f"{person.get('first_name', '')} {person.get('family_name', '')}".strip()
    return name or email


def _check_entry(email: str, person: dict | None, directory_ok: bool, platform_roles: set, required_role: str) -> dict:
    platform_ok = required_role in platform_roles
    return {
        "email": email,
        "name": _person_label(person, email),
        "university": (person or {}).get("university", ""),
        "in_directory": person is not None,
        "directory_role": directory_ok,
        "platform_account": bool(platform_roles),
        "platform_role": platform_ok,
        "verified": person is not None and directory_ok and platform_ok,
    }


def _resolve(candidates: dict, label: str) -> tuple[list, list, str]:
    """Turn {email: check} into (assignees, checks, note).

    Verified candidates (confirmed by both the Directory and the platform
    account) are preferred. If nobody is verified, every candidate found by
    either source is assigned, and the note says why, so a manager can fix
    the Directory or the account and re-check."""
    checks = sorted(candidates.values(), key=lambda c: (not c["verified"], c["name"].lower()))
    verified = [c["email"] for c in checks if c["verified"]]
    if verified:
        unverified = [c for c in checks if not c["verified"]]
        note = ""
        if unverified:
            note = f"{len(unverified)} other possible {label}(s) not assigned: " + "; ".join(
                f"{c['name']} ({_missing_sources(c)})" for c in unverified
            )
        return verified, [c for c in checks if c["verified"]] + unverified, note
    if checks:
        note = f"No fully verified {label} found — assigned to unverified candidates: " + "; ".join(
            f"{c['name']} ({_missing_sources(c)})" for c in checks
        )
        return [c["email"] for c in checks], checks, note
    return [], [], f"No {label} found in the Directory."


def _missing_sources(check: dict) -> str:
    missing = []
    if not check["in_directory"]:
        missing.append("not in Directory")
    elif not check["directory_role"]:
        missing.append("role not recorded in Directory")
    if not check["platform_account"]:
        missing.append("no platform account")
    elif not check["platform_role"]:
        missing.append("platform account lacks the role")
    return ", ".join(missing) or "ok"


def find_content_managers(university: str) -> tuple[list, list, str]:
    """Content managers of `university`.

    Directory side: people of that university who are members of a
    "Content Managers" unit, or whose unit role mentions "content manager".
    Platform side: people of that university (per the Directory) whose
    account has the content_manager role. Verified = both sides agree."""
    if not university:
        return [], [], "The event has no organising university, so no content manager could be identified."
    directory = _load_directory()
    roles_by_user = _platform_roles()
    units_by_id = {u["id"]: u for u in directory.get("units", [])}
    people = [p for p in directory.get("people", []) if p.get("university") == university and p.get("email")]

    cm_person_ids = set()
    for m in directory.get("memberships", []):
        unit = units_by_id.get(m.get("unit_id"))
        if _CONTENT_MANAGER_RE.search(m.get("role", "") or "") or (unit and _CONTENT_MANAGER_RE.search(unit.get("name", ""))):
            cm_person_ids.add(m["person_id"])

    candidates = {}
    for p in people:
        email = p["email"].strip().lower()
        platform = roles_by_user.get(email, set())
        directory_ok = p["id"] in cm_person_ids
        if directory_ok or "content_manager" in platform:
            candidates[email] = _check_entry(email, p, directory_ok, platform, "content_manager")
    assignees, checks, note = _resolve(candidates, f"{university} content manager")
    if not candidates:
        note = f"No content manager for {university} found in the Directory."
    return assignees, checks, note


def find_wp_leaders(wp: str) -> tuple[list, list, str]:
    """Leaders of work package `wp` (e.g. "WP3").

    Directory side: the leaders listed on the WP's unit (a unit whose name
    starts with the WP code, top-level units first), plus members of that
    unit whose role there mentions "leader". Platform side: the account has
    the wp_leader role. Verified = listed in the Directory, has a Directory
    entry, and has the wp_leader role."""
    directory = _load_directory()
    roles_by_user = _platform_roles()
    units = [u for u in directory.get("units", []) if _wp_code(u.get("name", "")) == wp]
    if not units:
        return [], [], f"No {wp} unit found in the Directory."
    # A WP's own unit is normally top-level; nested units that happen to
    # share the prefix (e.g. "WP3 Task 1" under WP3) only count if no
    # top-level unit matches.
    top = [u for u in units if u.get("parent_id") is None]
    unit_ids = {u["id"] for u in (top or units)}
    people_by_email = {p["email"].strip().lower(): p for p in directory.get("people", []) if p.get("email")}
    people_by_id = {p["id"]: p for p in directory.get("people", [])}

    leader_emails = set()
    for u in directory.get("units", []):
        if u["id"] in unit_ids:
            leader_emails |= {e.strip().lower() for e in u.get("leaders", []) if e.strip()}
    for m in directory.get("memberships", []):
        if m.get("unit_id") in unit_ids and _LEADER_RE.search(m.get("role", "") or ""):
            p = people_by_id.get(m["person_id"])
            if p and p.get("email"):
                leader_emails.add(p["email"].strip().lower())

    candidates = {
        email: _check_entry(email, people_by_email.get(email), True, roles_by_user.get(email, set()), "wp_leader")
        for email in leader_emails
    }
    assignees, checks, note = _resolve(candidates, f"{wp} leader")
    if not candidates:
        note = f"The {wp} unit in the Directory has no leader listed."
    return assignees, checks, note


# ---------------------------------------------------------------------------
# Event rules
# ---------------------------------------------------------------------------

def _event_universities(ev: dict) -> list:
    return ev.get("universities") or ([ev["university"]] if ev.get("university") else [])


def _event_categories(ev: dict) -> list:
    return ev.get("categories") or ([ev["category"]] if ev.get("category") else [])


def missing_event_fields(ev: dict) -> list[str]:
    """Human-readable names of the fields a new event still needs."""
    missing = []
    if not (ev.get("description") or "").strip():
        missing.append("Description")
    if not _event_universities(ev):
        missing.append("Organising university")
    if ev.get("date_tbc") or not ev.get("start_date") or not ev.get("end_date"):
        missing.append("Confirmed dates")
    if ev.get("event_type", "Physical") == "Physical":
        if not (ev.get("place") or "").strip():
            missing.append("Place")
    elif not (ev.get("meeting_url") or "").strip():
        missing.append("Meeting URL")
    return missing


def event_wps(ev: dict) -> list[str]:
    """Work packages an event relates to: WPn categories and a WPn UNINOVIS group."""
    wps = [_wp_code(c) for c in _event_categories(ev)] + [_wp_code(ev.get("uninovis_group", ""))]
    return sorted({w for w in wps if w}, key=lambda w: int(w[2:]))


def _event_summary(ev: dict) -> str:
    when = "TBC" if ev.get("date_tbc") or not ev.get("start_date") else ev["start_date"][:10]
    unis = ", ".join(_event_universities(ev)) or "no organising university"
    cats = ", ".join(_event_categories(ev)) or "no category"
    return f"“{ev.get('name', '')}” ({cats}; {unis}; {when})"


def _complete_info_description(ev: dict, missing: list) -> str:
    return (
        f"The event {_event_summary(ev)} was created in the Event Tracker with missing information. "
        f"Please complete: {', '.join(missing)}."
    )


def _build_event_tasks(ev: dict, created_by: str) -> list[dict]:
    tasks = []
    link = {
        "event_id": ev.get("id", ""),
        "series_id": ev.get("series_id", "") or "",
        "event_name": ev.get("name", ""),
    }

    missing = missing_event_fields(ev)
    if missing:
        university = (_event_universities(ev) or [""])[0]
        assignees, checks, note = find_content_managers(university)
        tasks.append(_new_task(
            title="Complete Event information",
            description=_complete_info_description(ev, missing),
            kind=KIND_COMPLETE_INFO,
            priority="high" if "Confirmed dates" in missing else "normal",
            assignees=assignees,
            assignee_checks=checks,
            assignment_note=note,
            university=university,
            missing_fields=missing,
            **link,
        ))

    for wp in event_wps(ev):
        assignees, checks, note = find_wp_leaders(wp)
        tasks.append(_new_task(
            title="Review New Event",
            description=f"A new {wp} event {_event_summary(ev)} was created in the Event Tracker by {created_by}. Please review it.",
            kind=KIND_REVIEW_EVENT,
            assignees=assignees,
            assignee_checks=checks,
            assignment_note=note,
            university=(_event_universities(ev) or [""])[0],
            wp=wp,
            **link,
        ))

    for t in tasks:
        _log(t, "system", f"Created automatically for new event (by {created_by})")
    return tasks


def _tasks_for_event(tasks: list, ev: dict) -> list:
    """Tasks linked to this event, or to the series it belongs to."""
    sid = ev.get("series_id") or ""
    return [t for t in tasks if t.get("event_id") == ev.get("id") or (sid and t.get("series_id") == sid)]


# ---------------------------------------------------------------------------
# Hooks called by the Event Tracker. They never raise: a failure here must
# not stop an event from being saved.
# ---------------------------------------------------------------------------

def on_event_created(ev: dict, created_by: str) -> int:
    """Create the automatic tasks for a new event. For a recurring series,
    call this once with the first occurrence. Returns the number of tasks created."""
    try:
        if ev.get("source") == "catalogue" or ev.get("linked_event"):
            return 0
        new_tasks = _build_event_tasks(ev, created_by)
        if new_tasks:
            data = load_data()
            data.setdefault("tasks", []).extend(new_tasks)
            save_data(data)
        return len(new_tasks)
    except Exception:
        logger.exception("Project management: could not create tasks for event %s", ev.get("id"))
        return 0


def on_event_updated(ev: dict, updated_by: str):
    """Keep open "Complete Event information" tasks in sync with the event:
    refresh the list of missing fields, and close the task once nothing is missing."""
    try:
        data = load_data()
        changed = False
        for t in _tasks_for_event(data.get("tasks", []), ev):
            t["event_name"] = ev.get("name", t.get("event_name", ""))
            if t.get("kind") != KIND_COMPLETE_INFO or t.get("status") == "cancelled":
                continue
            missing = missing_event_fields(ev)
            if missing != t.get("missing_fields"):
                t["missing_fields"] = missing
                if missing:
                    t["description"] = _complete_info_description(ev, missing)
                _log(t, updated_by, "Event updated — missing: " + (", ".join(missing) or "nothing"))
            if not missing and t["status"] != "done":
                _set_status(t, "done", "system", "all event information completed")
                t["auto_closed"] = True
            elif missing and t["status"] == "done" and t.get("auto_closed"):
                # Only reopen a task the system itself closed, never one a person marked done.
                _set_status(t, "todo", "system", "event information is incomplete again")
            changed = True
        if changed:
            save_data(data)
    except Exception:
        logger.exception("Project management: could not sync tasks for event %s", ev.get("id"))


def on_events_deleted(event_ids: list[str], series_id: str, deleted_by: str):
    """Cancel open tasks for events (or a whole series) that no longer exist."""
    try:
        ids = set(event_ids)
        data = load_data()
        changed = False
        for t in data.get("tasks", []):
            linked = t.get("event_id") in ids or (series_id and t.get("series_id") == series_id)
            if linked and t.get("status") in ("todo", "in_progress"):
                _set_status(t, "cancelled", deleted_by, "event deleted")
                changed = True
        if changed:
            save_data(data)
    except Exception:
        logger.exception("Project management: could not cancel tasks for deleted events")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers={"Cache-Control": "no-store"})


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    return {
        "username": session["username"],
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "can_create": _can_create(session),
        "is_manager": _is_manager(session),
    }


@router.get("/api/tasks")
def get_tasks(session: dict = Depends(_require_auth), event_id: str = Query("")):
    tasks = load_data().get("tasks", [])
    if event_id:
        tasks = [t for t in tasks if t.get("event_id") == event_id]
    return tasks


@router.get("/api/people")
def get_people(session: dict = Depends(_require_auth)):
    """Directory people, for the assignee picker."""
    directory = _load_directory()
    return [
        {
            "email": p["email"].strip().lower(),
            "name": _person_label(p, p["email"]),
            "university": p.get("university", ""),
        }
        for p in directory.get("people", []) if p.get("email")
    ]


class TaskBody(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "normal"
    due_date: str = ""
    assignees: list[str] = []
    event_id: str = ""


def _validate_body(body: TaskBody):
    if not body.title.strip():
        raise HTTPException(400, "Title is required")
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    if body.priority not in PRIORITIES:
        raise HTTPException(400, f"priority must be one of {PRIORITIES}")
    if body.due_date:
        try:
            datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(400, "due_date must be an ISO date (YYYY-MM-DD)")


def _manual_checks(emails: list[str]) -> list[dict]:
    """For hand-picked assignees, record only whether they are in the Directory."""
    people = {p["email"].strip().lower(): p for p in _load_directory().get("people", []) if p.get("email")}
    return [
        {
            "email": e, "name": _person_label(people.get(e), e),
            "university": people.get(e, {}).get("university", ""),
            "in_directory": e in people,
        }
        for e in emails
    ]


def _clean_emails(emails: list[str]) -> list[str]:
    return sorted({e.strip().lower() for e in emails if e.strip()})


@router.post("/api/tasks")
def create_task(body: TaskBody, session: dict = Depends(_require_auth)):
    if not _can_create(session):
        raise HTTPException(403, "You do not have permission to create tasks")
    _validate_body(body)
    assignees = _clean_emails(body.assignees)
    task = _new_task(
        title=body.title.strip(),
        description=body.description.strip(),
        status=body.status,
        priority=body.priority,
        due_date=body.due_date,
        assignees=assignees,
        assignee_checks=_manual_checks(assignees),
        event_id=body.event_id.strip(),
        created_by=_username(session),
    )
    if task["status"] == "done":
        task["completed_at"] = _now()
    _log(task, _username(session), "Created")
    data = load_data()
    data.setdefault("tasks", []).append(task)
    save_data(data)
    return task


def _find_task(data: dict, task_id: str) -> dict:
    task = next((t for t in data.get("tasks", []) if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.put("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskBody, session: dict = Depends(_require_auth)):
    data = load_data()
    task = _find_task(data, task_id)
    if not _can_edit_task(session, task):
        raise HTTPException(403, "Only the task's creator or a content manager can edit it")
    _validate_body(body)
    who = _username(session)
    assignees = _clean_emails(body.assignees)
    if assignees != task.get("assignees"):
        # Keep the cross-check records of assignees who stay on the task.
        kept = {c["email"]: c for c in task.get("assignee_checks", []) if c["email"] in assignees}
        added = [e for e in assignees if e not in kept]
        task["assignee_checks"] = list(kept.values()) + _manual_checks(added)
        task["assignees"] = assignees
        _log(task, who, "Assignees: " + (", ".join(assignees) or "none"))
    task["title"] = body.title.strip()
    task["description"] = body.description.strip()
    task["priority"] = body.priority
    task["due_date"] = body.due_date
    task["event_id"] = body.event_id.strip() or task.get("event_id", "")
    _set_status(task, body.status, who)
    task["updated_at"] = _now()
    save_data(data)
    return task


class StatusBody(BaseModel):
    status: str


@router.put("/api/tasks/{task_id}/status")
def update_status(task_id: str, body: StatusBody, session: dict = Depends(_require_auth)):
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    data = load_data()
    task = _find_task(data, task_id)
    if not _can_update_status(session, task):
        raise HTTPException(403, "Only the task's assignees, creator, or a content manager can change its status")
    _set_status(task, body.status, _username(session))
    save_data(data)
    return task


class CommentBody(BaseModel):
    text: str


@router.post("/api/tasks/{task_id}/comments")
def add_comment(task_id: str, body: CommentBody, session: dict = Depends(_require_auth)):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Comment is empty")
    data = load_data()
    task = _find_task(data, task_id)
    if not _can_update_status(session, task):
        raise HTTPException(403, "Only the task's assignees, creator, or a content manager can comment")
    _log(task, _username(session), "Comment: " + text[:2000])
    save_data(data)
    return task


@router.post("/api/tasks/{task_id}/recheck-assignees")
def recheck_assignees(task_id: str, session: dict = Depends(_require_auth)):
    """Re-resolve an automatic task's assignees from the current Directory and
    platform accounts — e.g. after a content manager or WP leader was added."""
    if not _is_manager(session):
        raise HTTPException(403, "content_manager or superuser role required")
    data = load_data()
    task = _find_task(data, task_id)
    if task.get("kind") == KIND_COMPLETE_INFO:
        assignees, checks, note = find_content_managers(task.get("university", ""))
    elif task.get("kind") == KIND_REVIEW_EVENT:
        assignees, checks, note = find_wp_leaders(task.get("wp", ""))
    else:
        raise HTTPException(400, "Only automatically created tasks can be re-checked against the Directory")
    task["assignees"] = assignees
    task["assignee_checks"] = checks
    task["assignment_note"] = note
    _log(task, _username(session), "Assignees re-checked against the Directory: " + (", ".join(assignees) or "none found"))
    save_data(data)
    return task


@router.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, session: dict = Depends(_require_auth)):
    data = load_data()
    task = _find_task(data, task_id)
    if not _can_edit_task(session, task):
        raise HTTPException(403, "Only the task's creator or a content manager can delete it")
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    save_data(data)
    return {"ok": True}
