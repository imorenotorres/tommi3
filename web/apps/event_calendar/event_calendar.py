"""
UNINOVIS Event Calendar — Calendar app with category and university filters.

Manages events with role-based editing (tester+).
Supports periodic (recurring) and punctual (one-off) events.
Designed to be mounted on the TOMMI FastAPI server.
"""

import base64
import csv
import hashlib
import io
import json
import os
import uuid
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
PERSONAL_DIR = os.path.join(os.path.dirname(__file__), "personal")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "directory", "data.json")

os.makedirs(PERSONAL_DIR, exist_ok=True)

router = APIRouter(prefix="/event-calendar", tags=["event_calendar"])


# -- Auth helpers -------------------------------------------------------------

from auth import get_session, ROLES, can_edit as _can_edit_check


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
        # Invalid/expired token — fall back to guest instead of blocking
        return {"username": "guest", "role": "public", "roles": ["public"]}
    return session


def _require_editor(session: dict = Depends(_require_auth)) -> dict:
    if not _can_edit_check(session):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


# -- Data I/O -----------------------------------------------------------------

DEFAULT_DATA = {
    "events": [],
    "categories": ["WP1", "WP2", "WP3", "WP4", "WP5", "BoP", "ExecCouncil", "BIP", "Hackathon", "Other public events"],
    "universities": ["KK", "UMA", "USPN", "TAMK", "THUAS", "UDCLV", "UT", "THWS"],
}


def load_data():
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


_PERSONAL_KEY_SALT = "uninovis-event-calendar-personal-2026"


def _personal_path(username: str) -> str:
    """Safe filename for a user's encrypted personal events."""
    safe = username.replace("@", "_at_").replace("/", "_").replace("\\", "_")
    return os.path.join(PERSONAL_DIR, f"{safe}.enc")


def _derive_key(username: str) -> bytes:
    """Derive a Fernet key from the username + salt (deterministic per user)."""
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        (username + _PERSONAL_KEY_SALT).encode(),
        b"uninovis-fixed-salt",
        100_000,
    )
    return base64.urlsafe_b64encode(raw[:32])


def load_personal(username: str) -> list:
    p = _personal_path(username)
    if not os.path.exists(p):
        return []
    key = _derive_key(username)
    f = Fernet(key)
    with open(p, "rb") as fh:
        encrypted = fh.read()
    try:
        decrypted = f.decrypt(encrypted)
        return json.loads(decrypted)
    except Exception:
        return []


def save_personal(username: str, events: list):
    key = _derive_key(username)
    f = Fernet(key)
    plaintext = json.dumps(events, ensure_ascii=False).encode("utf-8")
    encrypted = f.encrypt(plaintext)
    with open(_personal_path(username), "wb") as fh:
        fh.write(encrypted)


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
    can_edit = _can_edit_check(session)
    return {"username": session["username"], "role": session["role"], "roles": session.get("roles", [session["role"]]), "can_edit": can_edit}


@router.get("/api/events")
def get_events(session: dict = Depends(_require_auth)):
    """Return shared events + user's personal events."""
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    personal = load_personal(session["username"])
    return shared + personal


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
    start_date: str = ""
    end_date: str = ""
    registration_link: str = ""
    image: str = ""
    participants: list[str] = []
    participant_groups: list[str] = []
    visibility: str = "shared"  # "shared" or "personal"
    date_tbc: bool = False  # True = date is tentative / to be confirmed
    date_tbc_label: str = ""  # Original text hint, e.g. "October 2026", "TBC"
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
        "visibility": body.visibility,
        "date_tbc": body.date_tbc,
        "date_tbc_label": body.date_tbc_label,
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
    if not body.date_tbc and (not body.start_date or not body.end_date):
        raise HTTPException(400, "Start and end dates are required unless date_tbc is true")


def _require_auth_or_editor(body_visibility: str, session: dict):
    """Personal events: any user. Shared events: tester+."""
    if body_visibility == "personal":
        return
    if not _can_edit_check(session):
        raise HTTPException(403, "Only testers can create shared events")


def _store_event(ev: dict, username: str):
    """Append event to the correct store based on visibility."""
    if ev.get("visibility") == "personal":
        personal = load_personal(username)
        personal.append(ev)
        save_personal(username, personal)
    else:
        data = load_data()
        data["events"].append(ev)
        save_data(data)


@router.post("/api/events")
def create_event(body: EventBody, session: dict = Depends(_require_auth)):
    _require_auth_or_editor(body.visibility, session)
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
            occ_start = occ_start.replace(hour=start_dt.hour, minute=start_dt.minute, second=0)
            occ_end = occ_start + duration
            ev = _build_event(body, occ_start.isoformat(), occ_end.isoformat(), series_id, session["username"])
            created.append(ev)

        if body.visibility == "personal":
            personal = load_personal(session["username"])
            personal.extend(created)
            save_personal(session["username"], personal)
        else:
            for ev in created:
                data["events"].append(ev)
            save_data(data)
        return {"series_id": series_id, "count": len(created), "events": created}
    else:
        ev = _build_event(body, body.start_date, body.end_date, "", session["username"])
        _store_event(ev, session["username"])
        return ev


def _update_ev_fields(ev: dict, body: EventBody):
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
    ev["visibility"] = body.visibility
    ev["date_tbc"] = body.date_tbc
    ev["date_tbc_label"] = body.date_tbc_label


@router.put("/api/events/{event_id}")
def update_event(event_id: str, body: EventBody, session: dict = Depends(_require_auth)):
    data = load_data()
    _validate_event(body, data)

    # Try personal events first
    personal = load_personal(session["username"])
    for ev in personal:
        if ev["id"] == event_id:
            _update_ev_fields(ev, body)
            save_personal(session["username"], personal)
            return ev

    # Try shared events
    if not _can_edit_check(session):
        raise HTTPException(403, "Insufficient permissions")
    for ev in data["events"]:
        if ev["id"] == event_id:
            _update_ev_fields(ev, body)
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
def delete_event(event_id: str, session: dict = Depends(_require_auth)):
    # Try personal events first
    personal = load_personal(session["username"])
    before_p = len(personal)
    personal = [ev for ev in personal if ev["id"] != event_id]
    if len(personal) < before_p:
        save_personal(session["username"], personal)
        return {"ok": True}

    # Try shared events (tester+)
    if not _can_edit_check(session):
        raise HTTPException(403, "Insufficient permissions")
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


# -- Export / Import ----------------------------------------------------------

TSV_FIELDS = [
    "id", "name", "description", "category", "university", "event_type",
    "timezone", "place", "meeting_url", "start_date", "end_date",
    "registration_link", "date_tbc", "date_tbc_label", "series_id", "created_by",
]


# -- iCalendar feed -----------------------------------------------------------

TZ_OFFSETS = {
    "CET": "+0100", "CEST": "+0200", "EET": "+0200", "EEST": "+0300",
    "WET": "+0000", "WEST": "+0100", "GMT": "+0000", "UTC": "+0000",
}


def _ical_escape(s: str) -> str:
    """Escape text for iCalendar fields."""
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _to_ical_dt(iso_str: str) -> str:
    """Convert ISO datetime to iCal format: 20260615T140000"""
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y%m%dT%H%M%S")


def _generate_ics(events_list: list) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UNINOVIS//Event Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:UNINOVIS Event Tracker",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]
    for ev in events_list:
        if not ev.get("start_date") or not ev.get("end_date"):
            continue  # Skip TBC events without dates
        tz = ev.get("timezone", "CEST")
        tzid = "Europe/Berlin"  # Default TZID for most UNINOVIS partners
        tbc_prefix = "[TBC] " if ev.get("date_tbc") else ""
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev['id']}@uninovis.event-calendar")
        lines.append(f"DTSTART;TZID={tzid}:{_to_ical_dt(ev['start_date'])}")
        lines.append(f"DTEND;TZID={tzid}:{_to_ical_dt(ev['end_date'])}")
        lines.append(f"SUMMARY:{_ical_escape(tbc_prefix + ev['name'])}")
        desc_parts = []
        if ev.get("date_tbc"):
            desc_parts.append(f"Date: To Be Confirmed ({ev.get('date_tbc_label', 'TBC')})")
        if ev.get("description"):
            desc_parts.append(ev["description"])
        if ev.get("category"):
            desc_parts.append(f"Category: {ev['category']}")
        if ev.get("university"):
            desc_parts.append(f"Organizing university: {ev['university']}")
        if ev.get("event_type") == "Virtual" and ev.get("meeting_url"):
            desc_parts.append(f"Meeting URL: {ev['meeting_url']}")
        if ev.get("registration_link"):
            desc_parts.append(f"Registration: {ev['registration_link']}")
        desc_parts.append(f"Timezone: {tz}")
        lines.append(f"DESCRIPTION:{_ical_escape(chr(10).join(desc_parts))}")
        if ev.get("event_type") == "Physical" and ev.get("place"):
            lines.append(f"LOCATION:{_ical_escape(ev['place'])}")
        if ev.get("event_type") == "Virtual" and ev.get("meeting_url"):
            lines.append(f"URL:{ev['meeting_url']}")
        cat = ev.get("category", "")
        if cat:
            lines.append(f"CATEGORIES:{_ical_escape(cat)}")
        lines.append(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


@router.get("/api/feed/ical")
def ical_feed(token: str = Query("")):
    """iCalendar feed URL for calendar subscriptions (Apple Calendar, Google, Outlook).
    Auth via query param so it works as a subscription URL."""
    session = get_session(token) if token else None
    if not session:
        raise HTTPException(401, "Invalid or expired token")
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    personal = load_personal(session["username"])
    ics = _generate_ics(shared + personal)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": "inline; filename=uninovis_events.ics",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get("/api/export/ical")
def export_ical(session: dict = Depends(_require_auth)):
    """Download .ics file (shared + personal)."""
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    personal = load_personal(session["username"])
    ics = _generate_ics(shared + personal)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=uninovis_events.ics"},
    )


def _filter_events(events: list, date_from: str, date_to: str,
                    university: str, category: str) -> list:
    """Filter events by date range, university, and category."""
    result = events
    if date_from:
        result = [ev for ev in result if ev.get("start_date", "") >= date_from]
    if date_to:
        # Include events that start on or before end of date_to
        to_dt = date_to + "T23:59:59" if "T" not in date_to else date_to
        result = [ev for ev in result if ev.get("start_date", "") <= to_dt]
    if university:
        unis = [u.strip() for u in university.split(",")]
        result = [ev for ev in result if ev.get("university", "") in unis]
    if category:
        cats = [c.strip() for c in category.split(",")]
        result = [ev for ev in result if ev.get("category", "") in cats]
    return result


@router.get("/api/export/json")
def export_json(
    session: dict = Depends(_require_auth),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
    university: str = Query(""),
    category: str = Query(""),
):
    """Export shared events as JSON with optional filters."""
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    filtered = _filter_events(shared, date_from, date_to, university, category)
    content = json.dumps(filtered, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=uninovis_events.json"},
    )


@router.get("/api/export/tsv")
def export_tsv(
    session: dict = Depends(_require_auth),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
    university: str = Query(""),
    category: str = Query(""),
):
    """Export shared events as TSV with optional filters."""
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    filtered = _filter_events(shared, date_from, date_to, university, category)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TSV_FIELDS, extrasaction="ignore", delimiter="\t")
    writer.writeheader()
    for ev in filtered:
        writer.writerow(ev)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": "attachment; filename=uninovis_events.tsv"},
    )


class ImportResult(BaseModel):
    added: int = 0
    updated: int = 0
    errors: list[str] = []


@router.post("/api/import/json")
async def import_json(file: UploadFile = File(...), session: dict = Depends(_require_editor)):
    """Import events from a JSON file. Existing events with the same id are updated."""
    content = await file.read()
    try:
        imported = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    if not isinstance(imported, list):
        raise HTTPException(400, "JSON must be an array of event objects")

    data = load_data()
    existing_ids = {ev["id"] for ev in data["events"]}
    result = ImportResult()

    for i, item in enumerate(imported):
        if not isinstance(item, dict):
            result.errors.append(f"Row {i}: not an object")
            continue
        name = item.get("name", "").strip()
        if not name:
            result.errors.append(f"Row {i}: missing name")
            continue
        cat = item.get("category", "")
        if cat and cat not in data["categories"]:
            result.errors.append(f"Row {i}: unknown category '{cat}'")
            continue

        eid = item.get("id", "")
        if eid and eid in existing_ids:
            # Update existing
            for ev in data["events"]:
                if ev["id"] == eid:
                    for k in ["name", "description", "category", "university",
                              "event_type", "timezone", "place", "meeting_url",
                              "start_date", "end_date", "registration_link",
                              "date_tbc", "date_tbc_label", "series_id"]:
                        if k in item:
                            ev[k] = item[k]
                    break
            result.updated += 1
        else:
            # Add new
            ev = {
                "id": eid or ("evt" + str(uuid.uuid4())[:8]),
                "name": name,
                "description": item.get("description", ""),
                "category": cat,
                "university": item.get("university", ""),
                "event_type": item.get("event_type", "Physical"),
                "timezone": item.get("timezone", "CEST"),
                "place": item.get("place", ""),
                "meeting_url": item.get("meeting_url", ""),
                "start_date": item.get("start_date", ""),
                "end_date": item.get("end_date", ""),
                "registration_link": item.get("registration_link", ""),
                "image": item.get("image", ""),
                "date_tbc": item.get("date_tbc", False),
                "date_tbc_label": item.get("date_tbc_label", ""),
                "participants": item.get("participants", []),
                "participant_groups": item.get("participant_groups", []),
                "series_id": item.get("series_id", ""),
                "created_by": session["username"],
            }
            data["events"].append(ev)
            existing_ids.add(ev["id"])
            result.added += 1

    save_data(data)
    return result


@router.post("/api/import/tsv")
async def import_tsv(file: UploadFile = File(...), session: dict = Depends(_require_editor)):
    """Import events from a TSV file. Existing events with the same id are updated."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")

    data = load_data()
    existing_ids = {ev["id"] for ev in data["events"]}
    result = ImportResult()

    for i, row in enumerate(reader):
        name = row.get("name", "").strip()
        if not name:
            result.errors.append(f"Row {i + 2}: missing name")
            continue
        cat = row.get("category", "")
        if cat and cat not in data["categories"]:
            result.errors.append(f"Row {i + 2}: unknown category '{cat}'")
            continue

        eid = row.get("id", "").strip()
        if eid and eid in existing_ids:
            for ev in data["events"]:
                if ev["id"] == eid:
                    for k in TSV_FIELDS:
                        if k in row and k != "id" and row[k]:
                            ev[k] = row[k]
                    break
            result.updated += 1
        else:
            ev = {
                "id": eid or ("evt" + str(uuid.uuid4())[:8]),
                "name": name,
                "description": row.get("description", ""),
                "category": cat,
                "university": row.get("university", ""),
                "event_type": row.get("event_type", "Physical"),
                "timezone": row.get("timezone", "CEST"),
                "place": row.get("place", ""),
                "meeting_url": row.get("meeting_url", ""),
                "start_date": row.get("start_date", ""),
                "end_date": row.get("end_date", ""),
                "registration_link": row.get("registration_link", ""),
                "image": "",
                "date_tbc": row.get("date_tbc", "").lower() in ("true", "1", "yes"),
                "date_tbc_label": row.get("date_tbc_label", ""),
                "participants": [],
                "participant_groups": [],
                "series_id": row.get("series_id", ""),
                "created_by": session["username"],
            }
            data["events"].append(ev)
            existing_ids.add(ev["id"])
            result.added += 1

    save_data(data)
    return result
