"""
UNINOVIS Event Calendar — Calendar app with category and university filters.

Manages events with role-based editing (tester+).
Supports periodic (recurring) and punctual (one-off) events.
Designed to be mounted on the TOMMI FastAPI server.
"""

import json
import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

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


# -- Recurrence helpers -------------------------------------------------------

def _nth_weekday_of_month(year, month, weekday, nth):
    """Return the nth occurrence of weekday in the given month.
    weekday: 0=Mon .. 6=Sun.  nth: 1=first, 2=second, ... -1=last."""
    from calendar import monthrange
    if nth == -1:
        # Last occurrence
        last_day = monthrange(year, month)[1]
        d = datetime(year, month, last_day)
        while d.weekday() != weekday:
            d -= timedelta(days=1)
        return d
    d = datetime(year, month, 1)
    count = 0
    while d.month == month:
        if d.weekday() == weekday:
            count += 1
            if count == nth:
                return d
        d += timedelta(days=1)
    return None  # nth occurrence doesn't exist


def generate_occurrences(rule, start_dt, end_dt, until_dt):
    """Generate occurrence start dates from a recurrence rule.
    rule: {type, weekday, nth, interval}
      type: 'weekly' | 'biweekly' | 'monthly_nth'
      weekday: 0=Mon..6=Sun
      nth: 1..5 or -1 (for monthly_nth: 1st, 2nd, ... last)
    Returns list of datetime objects.
    """
    dates = []
    rtype = rule.get("type", "weekly")
    weekday = rule.get("weekday", 0)

    if rtype in ("weekly", "biweekly"):
        interval = 7 if rtype == "weekly" else 14
        # Find first occurrence on or after start_dt's weekday
        d = start_dt
        while d.weekday() != weekday:
            d += timedelta(days=1)
        while d <= until_dt:
            dates.append(d)
            d += timedelta(days=interval)
    elif rtype == "monthly_nth":
        nth = rule.get("nth", 1)
        d = start_dt
        year, month = d.year, d.month
        while True:
            occ = _nth_weekday_of_month(year, month, weekday, nth)
            if occ and occ >= start_dt and occ <= until_dt:
                dates.append(occ)
            # Next month
            month += 1
            if month > 12:
                month = 1
                year += 1
            if datetime(year, month, 1) > until_dt:
                break
    return dates


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
    timezone: str = "CEST"
    start_date: str
    end_date: str
    registration_link: str = ""
    image: str = ""
    participants: list[str] = []
    participant_groups: list[str] = []
    recurrence: Optional[dict] = None  # {type, weekday, nth, until}
    series_id: Optional[str] = None


def _build_event(body: EventBody, start_date: str, end_date: str, series_id: str, username: str) -> dict:
    return {
        "id": "evt" + str(uuid.uuid4())[:8],
        "name": body.name,
        "description": body.description,
        "category": body.category,
        "university": body.university,
        "event_type": body.event_type,
        "place": body.place,
        "meeting_url": body.meeting_url,
        "timezone": body.timezone,
        "start_date": start_date,
        "end_date": end_date,
        "registration_link": body.registration_link,
        "image": body.image,
        "participants": body.participants,
        "participant_groups": body.participant_groups,
        "series_id": series_id,
        "created_by": username,
    }


def _validate_event(body: EventBody, data: dict):
    if body.category not in data["categories"]:
        raise HTTPException(400, f"Unknown category: {body.category}")
    if body.university and body.university not in data.get("universities", []):
        raise HTTPException(400, f"Unknown university: {body.university}")
    if body.event_type not in ("Virtual", "Physical"):
        raise HTTPException(400, "event_type must be 'Virtual' or 'Physical'")


@router.post("/api/events")
def create_event(body: EventBody, session: dict = Depends(_require_editor)):
    data = load_data()
    _validate_event(body, data)

    recurrence = body.recurrence
    if recurrence and recurrence.get("type"):
        # Create a series of recurring events
        series_id = "ser" + str(uuid.uuid4())[:8]
        start_dt = datetime.fromisoformat(body.start_date)
        end_dt = datetime.fromisoformat(body.end_date)
        duration = end_dt - start_dt
        until_str = recurrence.get("until", "")
        if not until_str:
            raise HTTPException(400, "Recurrence requires an 'until' date")
        until_dt = datetime.fromisoformat(until_str)

        occurrences = generate_occurrences(recurrence, start_dt, end_dt, until_dt)
        if not occurrences:
            raise HTTPException(400, "No occurrences generated for the given rule")

        created = []
        for occ_start in occurrences:
            # Preserve original time from start_date
            occ_start = occ_start.replace(hour=start_dt.hour, minute=start_dt.minute, second=0)
            occ_end = occ_start + duration
            ev = _build_event(body, occ_start.isoformat(), occ_end.isoformat(), series_id, session["username"])
            data["events"].append(ev)
            created.append(ev)
        save_data(data)
        return {"series_id": series_id, "count": len(created), "events": created}
    else:
        # Single (punctual) event
        ev = _build_event(body, body.start_date, body.end_date, "", session["username"])
        data["events"].append(ev)
        save_data(data)
        return ev


@router.put("/api/events/{event_id}")
def update_event(event_id: str, body: EventBody, session: dict = Depends(_require_editor)):
    data = load_data()
    _validate_event(body, data)
    for ev in data["events"]:
        if ev["id"] == event_id:
            ev["name"] = body.name
            ev["description"] = body.description
            ev["category"] = body.category
            ev["university"] = body.university
            ev["event_type"] = body.event_type
            ev["place"] = body.place
            ev["meeting_url"] = body.meeting_url
            ev["timezone"] = body.timezone
            ev["start_date"] = body.start_date
            ev["end_date"] = body.end_date
            ev["registration_link"] = body.registration_link
            ev["image"] = body.image
            ev["participants"] = body.participants
            ev["participant_groups"] = body.participant_groups
            save_data(data)
            return ev
    raise HTTPException(404, "Event not found")


@router.put("/api/events/series/{series_id}")
def update_series(series_id: str, body: EventBody, session: dict = Depends(_require_editor)):
    """Update all events in a series (name, description, category, etc.) keeping individual dates."""
    data = load_data()
    _validate_event(body, data)
    updated = 0
    for ev in data["events"]:
        if ev.get("series_id") == series_id:
            ev["name"] = body.name
            ev["description"] = body.description
            ev["category"] = body.category
            ev["university"] = body.university
            ev["event_type"] = body.event_type
            ev["place"] = body.place
            ev["meeting_url"] = body.meeting_url
            ev["timezone"] = body.timezone
            ev["registration_link"] = body.registration_link
            ev["image"] = body.image
            ev["participants"] = body.participants
            ev["participant_groups"] = body.participant_groups
            updated += 1
    if updated == 0:
        raise HTTPException(404, "Series not found")
    save_data(data)
    return {"ok": True, "updated": updated}


@router.delete("/api/events/{event_id}")
def delete_event(event_id: str, session: dict = Depends(_require_editor)):
    data = load_data()
    before = len(data["events"])
    data["events"] = [ev for ev in data["events"] if ev["id"] != event_id]
    if len(data["events"]) == before:
        raise HTTPException(404, "Event not found")
    save_data(data)
    return {"ok": True}


@router.delete("/api/events/series/{series_id}")
def delete_series(series_id: str, session: dict = Depends(_require_editor)):
    """Delete all events in a series."""
    data = load_data()
    before = len(data["events"])
    data["events"] = [ev for ev in data["events"] if ev.get("series_id") != series_id]
    deleted = before - len(data["events"])
    if deleted == 0:
        raise HTTPException(404, "Series not found")
    save_data(data)
    return {"ok": True, "deleted": deleted}
