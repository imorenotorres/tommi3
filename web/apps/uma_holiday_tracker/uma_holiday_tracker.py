"""
UMA Holiday Tracker — shared calendar for UMA-based uninovis_staff (and
superusers) to log their own holidays and personal days. Access requires both
the uninovis_staff role AND a @uma.es login. Saturdays, Sundays and UMA
local festivities are automatically greyed in the calendar.
"""

import json
import os
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator, model_validator

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "directory", "data.json")
FESTIVITIES_PATH = os.path.join(os.path.dirname(__file__), "festivities.json")

router = APIRouter(prefix="/holiday-tracker", tags=["holiday_tracker"])

EVENT_TYPES = {"holiday", "personal_day", "comision_servicio", "teletrabajo", "formacion"}


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


def _is_uma_email(username: str) -> bool:
    """Usernames are the login email; UMA accounts use the @uma.es domain."""
    return username.strip().lower().rsplit("@", 1)[-1] == "uma.es"


_ALLOWED_ROLES = {"uninovis_staff", "content_manager", "superuser"}


def _require_uma_staff(session: dict = Depends(_require_auth)) -> dict:
    """Requires BOTH the uninovis_staff (or superuser) role AND a @uma.es
    login — the role alone isn't enough, since uninovis_staff is usable
    alliance-wide and this app is UMA-only."""
    if not (_ALLOWED_ROLES & set(_user_roles(session))) or not _is_uma_email(session["username"]):
        raise HTTPException(status_code=403, detail="uninovis_staff (UMA) access only")
    return session


_FESTIVITY_MANAGER_ROLES = {"content_manager", "superuser"}


def _require_festivity_manager(session: dict = Depends(_require_auth)) -> dict:
    """Managing the official UMA festivities calendar (not personal entries)
    is narrower than general app access: content_manager/superuser only,
    still gated to a @uma.es login since this app is UMA-only."""
    if not (_FESTIVITY_MANAGER_ROLES & set(_user_roles(session))) or not _is_uma_email(session["username"]):
        raise HTTPException(status_code=403, detail="content_manager or superuser (UMA) access only")
    return session


def _is_editable(ev: dict) -> bool:
    """An entry can only be changed before it happens — once its start date
    has arrived (today) or passed, it's locked."""
    return ev["start_date"] > date.today().isoformat()


# ── Data I/O ─────────────────────────────────────────────────────────

DEFAULT_DATA = {"events": [], "allowances": [], "colors": []}


def load_data():
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA.copy())
        return DEFAULT_DATA.copy()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("events", [])
    data.setdefault("allowances", [])
    data.setdefault("colors", [])
    return data


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
        "has_access": bool(_ALLOWED_ROLES & set(_user_roles(session))) and _is_uma_email(session["username"]),
    }


@router.get("/api/events")
def list_events(session: dict = Depends(_require_uma_staff)):
    """All UMA-based uninovis_staff/superusers see everyone's logged holidays/personal days."""
    return [
        {**e, "display_name": _display_name(e["username"]), "is_editable": _is_editable(e)}
        for e in load_data()["events"]
    ]


FULL_DAY_HOURS = 7.0


class EventBody(BaseModel):
    type: str
    start_date: str  # "YYYY-MM-DD"
    end_date: str    # "YYYY-MM-DD"
    destination: str = ""  # For comision_servicio
    description: str = ""  # For comision_servicio
    hours: float | None = None  # formacion only: hours taken (0, 7]; omitted = full day

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

    @model_validator(mode="after")
    def _validate_single_day_hours(self):
        # Asuntos propios are always a full day; Formación can be logged by the hour.
        if self.type == "personal_day":
            if self.start_date != self.end_date:
                raise ValueError("Personal days (asuntos propios) are logged one day at a time")
            self.hours = FULL_DAY_HOURS
        elif self.type == "formacion":
            if self.start_date != self.end_date:
                raise ValueError("Formación entries are logged one day at a time")
            hours = self.hours if self.hours is not None else FULL_DAY_HOURS
            if not (0 < hours <= FULL_DAY_HOURS):
                raise ValueError(f"Hours must be greater than 0 and at most {FULL_DAY_HOURS:g}")
            self.hours = hours
        else:
            self.hours = None
        return self


@router.post("/api/events")
def create_event(body: EventBody, session: dict = Depends(_require_uma_staff)):
    """A UMA-based uninovis_staff member/superuser logs a holiday/personal day for themselves only."""
    if body.end_date < body.start_date:
        raise HTTPException(400, "end_date cannot be before start_date")
    data = load_data()
    event = {
        "id": "hol" + uuid.uuid4().hex[:8],
        "username": session["username"],
        "type": body.type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "destination": body.destination,
        "description": body.description,
        "hours": body.hours,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    data["events"].append(event)
    save_data(data)
    return {**event, "display_name": _display_name(event["username"]), "is_editable": _is_editable(event)}


@router.put("/api/events/{event_id}")
def update_event(event_id: str, body: EventBody, session: dict = Depends(_require_uma_staff)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "end_date cannot be before start_date")
    data = load_data()
    for ev in data["events"]:
        if ev["id"] == event_id:
            if ev["username"] != session["username"]:
                raise HTTPException(403, "You can only edit your own entries")
            if not _is_editable(ev):
                raise HTTPException(400, "It is not possible to change a past holiday.")
            ev["type"] = body.type
            ev["start_date"] = body.start_date
            ev["end_date"] = body.end_date
            ev["destination"] = body.destination
            ev["description"] = body.description
            ev["hours"] = body.hours
            save_data(data)
            return {**ev, "display_name": _display_name(ev["username"]), "is_editable": _is_editable(ev)}
    raise HTTPException(404, "Event not found")


@router.delete("/api/events/{event_id}")
def delete_event(event_id: str, session: dict = Depends(_require_uma_staff)):
    data = load_data()
    ev = next((e for e in data["events"] if e["id"] == event_id), None)
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev["username"] != session["username"]:
        raise HTTPException(403, "You can only delete your own entries")
    if not _is_editable(ev):
        raise HTTPException(400, "It is not possible to change a past holiday.")
    data["events"] = [e for e in data["events"] if e["id"] != event_id]
    save_data(data)
    return {"ok": True}


# ── Personal allowances ──────────────────────────────────────────────
# How many vacation days / asuntos propios days each person has for a given
# year. Self-reported by each user (roles alone don't tell us their amount).
# Vacaciones must be used within that same calendar year; asuntos propios
# allow a capped carryover into the following January/February. That
# used-vs-left accounting happens client-side in the calendar, which
# already has every event and festivity loaded.


class AllowanceBody(BaseModel):
    year: int
    vacation_days: float = 0
    personal_days: float = 0
    formacion_days: float = 0

    @field_validator("year")
    @classmethod
    def _validate_year(cls, v):
        if not (2000 <= v <= 2100):
            raise ValueError("year must be between 2000 and 2100")
        return v

    @field_validator("vacation_days", "personal_days", "formacion_days")
    @classmethod
    def _validate_nonnegative(cls, v):
        if v < 0:
            raise ValueError("days cannot be negative")
        return v


@router.get("/api/allowances")
def list_allowances(session: dict = Depends(_require_uma_staff)):
    """A user's own allowances only — everyone's numbers are personal."""
    return [a for a in load_data()["allowances"] if a["username"] == session["username"]]


@router.post("/api/allowances")
def upsert_allowance(body: AllowanceBody, session: dict = Depends(_require_uma_staff)):
    """Create or update the caller's allowance for the given year."""
    data = load_data()
    for a in data["allowances"]:
        if a["username"] == session["username"] and a["year"] == body.year:
            a["vacation_days"] = body.vacation_days
            a["personal_days"] = body.personal_days
            a["formacion_days"] = body.formacion_days
            a["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_data(data)
            return a
    entry = {
        "id": "allw" + uuid.uuid4().hex[:8],
        "username": session["username"],
        "year": body.year,
        "vacation_days": body.vacation_days,
        "personal_days": body.personal_days,
        "formacion_days": body.formacion_days,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    data["allowances"].append(entry)
    save_data(data)
    return entry


@router.delete("/api/allowances/{allowance_id}")
def delete_allowance(allowance_id: str, session: dict = Depends(_require_uma_staff)):
    data = load_data()
    a = next((x for x in data["allowances"] if x["id"] == allowance_id), None)
    if not a:
        raise HTTPException(404, "Allowance not found")
    if a["username"] != session["username"]:
        raise HTTPException(403, "You can only delete your own allowance")
    data["allowances"] = [x for x in data["allowances"] if x["id"] != allowance_id]
    save_data(data)
    return {"ok": True}


# ── Personal calendar colors ─────────────────────────────────────────
# Each person's chip/legend color is normally derived from their username by
# a deterministic hash (kept in sync client-side so it needs no storage).
# Choosing a color manually overrides that for everyone's view, so it has
# to be shared, not just remembered locally — hence this tiny per-user
# color registry, visible to every UMA staff member the same way events are.


class ColorBody(BaseModel):
    hue: int  # degrees, 0-359 — paired with a fixed saturation/lightness client-side

    @field_validator("hue")
    @classmethod
    def _validate_hue(cls, v):
        if not (0 <= v < 360):
            raise ValueError("hue must be between 0 and 359")
        return v


@router.get("/api/colors")
def list_colors(session: dict = Depends(_require_uma_staff)):
    """Every manually-chosen color, keyed by username — needed by everyone's
    calendar so a chosen color renders the same for every viewer."""
    return {c["username"]: c["hue"] for c in load_data()["colors"]}


@router.post("/api/color")
def set_my_color(body: ColorBody, session: dict = Depends(_require_uma_staff)):
    """Set (or replace) the caller's own manually-chosen color."""
    data = load_data()
    for c in data["colors"]:
        if c["username"] == session["username"]:
            c["hue"] = body.hue
            c["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_data(data)
            return {"username": session["username"], "hue": c["hue"]}
    data["colors"].append({
        "username": session["username"],
        "hue": body.hue,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    })
    save_data(data)
    return {"username": session["username"], "hue": body.hue}


@router.delete("/api/color")
def reset_my_color(session: dict = Depends(_require_uma_staff)):
    """Drop the caller's manual color choice, reverting to the automatic one."""
    data = load_data()
    data["colors"] = [c for c in data["colors"] if c["username"] != session["username"]]
    save_data(data)
    return {"ok": True}


# ── UMA festivities ─────────────────────────────────────────────────
# National + regional + local holidays for the University of Málaga.
# Loaded from festivities.json (recurring "MM-DD" entries + per-year
# "YYYY-MM-DD" entries); update that file yearly, no code changes needed.


def _load_festivities():
    try:
        with open(FESTIVITIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"recurring": [], "by_year": {}}


def _save_festivities(festivities: dict):
    with open(FESTIVITIES_PATH, "w", encoding="utf-8") as f:
        json.dump(festivities, f, indent=2, ensure_ascii=False)


def _iter_days(start_str: str, end_str: str):
    """Yield 'YYYY-MM-DD' strings from start to end inclusive."""
    d = datetime.strptime(start_str, "%Y-%m-%d").date()
    last = datetime.strptime(end_str, "%Y-%m-%d").date()
    while d <= last:
        yield d.isoformat()
        d += timedelta(days=1)


@router.get("/api/festivities")
def get_festivities(year: int = None):
    """Return UMA festivities for a given year (or current year), one row per day."""
    if year is None:
        year = date.today().year
    festivities = _load_festivities()
    result = []

    # Recurring holidays — "MM-DD" range projected onto the requested year
    for entry in festivities.get("recurring", []):
        start_mmdd = entry["date"]
        end_mmdd = entry.get("end_date", start_mmdd)
        for day_str in _iter_days(f"{year}-{start_mmdd}", f"{year}-{end_mmdd}"):
            result.append({"id": entry.get("id"), "date": day_str, "name": entry["name"], "icon": entry.get("icon", "🔴")})

    # Year-specific — check this year's bucket and the previous year's, since a
    # range can start in December and spill into January of the next year.
    for bucket_year in (str(year - 1), str(year)):
        for entry in festivities.get("by_year", {}).get(bucket_year, []):
            start_str = entry["date"]
            end_str = entry.get("end_date", start_str)
            for day_str in _iter_days(start_str, end_str):
                if day_str.startswith(f"{year}-"):
                    result.append({"id": entry.get("id"), "date": day_str, "name": entry["name"], "icon": entry.get("icon", "🔴")})
    return result


@router.get("/api/festivities/manage")
def list_festivities_for_management(session: dict = Depends(_require_festivity_manager)):
    """Full raw festivities structure (recurring + every year), for editing."""
    return _load_festivities()


class FestivityBody(BaseModel):
    date: str  # "MM-DD" if recurring, "YYYY-MM-DD" otherwise — start of the range
    end_date: str | None = None  # same format; inclusive end of the range (omit for a single day)
    name: str
    icon: str = "🔴"
    recurring: bool = False


def _validate_festivity_dates(body: "FestivityBody") -> str:
    """Validates date/end_date format and ordering. Returns the normalized end_date."""
    fmt = "%m-%d" if body.recurring else "%Y-%m-%d"
    kind = "MM-DD" if body.recurring else "YYYY-MM-DD"
    try:
        datetime.strptime(body.date, fmt)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Date must be in {kind} format")

    end_date = body.end_date or body.date
    try:
        datetime.strptime(end_date, fmt)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"End date must be in {kind} format")

    if end_date < body.date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    return end_date


@router.post("/api/festivities")
def create_festivity(body: FestivityBody, session: dict = Depends(_require_festivity_manager)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    end_date = _validate_festivity_dates(body)

    festivities = _load_festivities()
    entry = {
        "id": "fest" + uuid.uuid4().hex[:8],
        "date": body.date,
        "end_date": end_date,
        "name": name,
        "icon": body.icon.strip() or "🔴",
    }
    if body.recurring:
        festivities.setdefault("recurring", []).append(entry)
    else:
        year = body.date[:4]
        festivities.setdefault("by_year", {}).setdefault(year, []).append(entry)

    _save_festivities(festivities)
    return entry


def _remove_festivity_by_id(festivities: dict, festivity_id: str) -> dict | None:
    """Find and remove a festivity entry wherever it lives; returns the removed entry, or None."""
    recurring = festivities.get("recurring", [])
    for i, entry in enumerate(recurring):
        if entry.get("id") == festivity_id:
            return recurring.pop(i)
    by_year = festivities.get("by_year", {})
    for year, entries in list(by_year.items()):
        for i, entry in enumerate(entries):
            if entry.get("id") == festivity_id:
                removed = entries.pop(i)
                if not entries:
                    del by_year[year]
                return removed
    return None


@router.put("/api/festivities/{festivity_id}")
def update_festivity(festivity_id: str, body: FestivityBody, session: dict = Depends(_require_festivity_manager)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    end_date = _validate_festivity_dates(body)

    festivities = _load_festivities()
    if _remove_festivity_by_id(festivities, festivity_id) is None:
        raise HTTPException(status_code=404, detail="Festivity not found")

    entry = {"id": festivity_id, "date": body.date, "end_date": end_date, "name": name, "icon": body.icon.strip() or "🔴"}
    if body.recurring:
        festivities.setdefault("recurring", []).append(entry)
    else:
        year = body.date[:4]
        festivities.setdefault("by_year", {}).setdefault(year, []).append(entry)

    _save_festivities(festivities)
    return entry


@router.delete("/api/festivities/{festivity_id}")
def delete_festivity(festivity_id: str, session: dict = Depends(_require_festivity_manager)):
    festivities = _load_festivities()
    if _remove_festivity_by_id(festivities, festivity_id) is None:
        raise HTTPException(status_code=404, detail="Festivity not found")
    _save_festivities(festivities)
    return {"ok": True}
