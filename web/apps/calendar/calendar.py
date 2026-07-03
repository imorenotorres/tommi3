"""
UNINOVIS Calendar — mirrors the Event Tracker and adds sync with the
Agora Event Catalogue API (https://uninovis.widening.eu/catalogue-api/v2/).

Catalogue token is read from the CATALOGUE_API_TOKEN environment variable
(or web/.env).  Catalogue events are cached locally and updated on demand
via POST /api/catalogue/sync.
"""

import ast
import base64
import csv
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timedelta

import httpx
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional

STATIC_DIR  = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH   = os.path.join(os.path.dirname(__file__), "data.json")
PERSONAL_DIR = os.path.join(os.path.dirname(__file__), "personal")
DIRECTORY_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "directory", "data.json")
ENV_PATH    = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

os.makedirs(PERSONAL_DIR, exist_ok=True)

router = APIRouter(prefix="/calendar", tags=["calendar"])

# ---------------------------------------------------------------------------
# Catalogue API config
# ---------------------------------------------------------------------------

CATALOGUE_API_BASE = "https://uninovis.widening.eu/catalogue-api/v2"
CATALOGUE_MODEL    = "alliance_catalogue_app.eventcatalogue"

def _catalogue_token() -> str:
    token = os.getenv("CATALOGUE_API_TOKEN") or os.getenv("EVENT_CATALOGUE_API_TOKEN", "")
    if not token:
        env = dotenv_values(ENV_PATH)
        token = env.get("CATALOGUE_API_TOKEN") or env.get("EVENT_CATALOGUE_API_TOKEN", "")
    return token

# University name → internal code
_UNI_NAME_TO_CODE = {
    "KAUNO KOLEGIJA":                                           "KK",
    "UNIVERSIDAD DE MÁLAGA":                                    "UMA",
    "UNIVERSITE PARIS 13":                                      "USPN",
    "TAMPEREEN AMMATTIKORKEAKOULU OY":                          "TAMK",
    "THE HAGUE UNIVERSITY OF APPLIED SCIENCES":                 "THUAS",
    "UNIVERSITA DEGLI STUDI DELLA CAMPANIA LUIGI VANVITELLI":   "UDCLV",
    "TECHNISCHE HOCHSCHULE WUERZBURG-SCHWEINFURT":              "THWS",
    "UNIVERSITETI I TIRANËS":                                   "UT",
}

# Agora event type → our category
_EVENT_TYPE_MAP = {
    "Blended Intensive Programme": "BIP",
    "Conference":    "Conference",
    "Hackathon":     "Hackathon",
    "Staff Week":    "Staff Week",
    "Summer School": "Summer School",
    "Workshop":      "Workshop",
}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

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
        return {"username": "guest", "role": "public", "roles": ["public"]}
    return session


def _require_editor(session: dict = Depends(_require_auth)) -> dict:
    if not _can_edit_check(session):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------

DEFAULT_DATA = {
    "events": [],
    "catalogue_events": [],
    "catalogue_last_sync": None,
    "categories": [
        "WP1", "WP2", "WP3", "WP4", "WP5", "BoP", "ExecCouncil",
        "BIP", "Hackathon", "Conference", "Staff Week", "Summer School",
        "Workshop", "Other public events",
    ],
    "universities": ["KK", "UMA", "USPN", "TAMK", "THUAS", "UDCLV", "UT", "THWS"],
}


def load_data():
    if not os.path.exists(DATA_PATH):
        save_data(DEFAULT_DATA.copy())
        return DEFAULT_DATA.copy()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


_PERSONAL_KEY_SALT = "uninovis-calendar-personal-2026"


def _personal_path(username: str) -> str:
    safe = username.replace("@", "_at_").replace("/", "_").replace("\\", "_")
    return os.path.join(PERSONAL_DIR, f"{safe}.enc")


def _derive_key(username: str) -> bytes:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        (username + _PERSONAL_KEY_SALT).encode(),
        b"uninovis-calendar-fixed-salt",
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
        return json.loads(f.decrypt(encrypted))
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


# ---------------------------------------------------------------------------
# Recurrence helpers (identical to event_calendar)
# ---------------------------------------------------------------------------

def _nth_weekday_of_month(year, month, weekday, nth):
    from calendar import monthrange
    if nth == -1:
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
    return None


def generate_occurrences(rule, start_dt, end_dt, until_dt):
    dates = []
    rtype = rule.get("type", "weekly")
    weekday = rule.get("weekday", 0)

    if rtype in ("weekly", "biweekly"):
        interval = 7 if rtype == "weekly" else 14
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
            month += 1
            if month > 12:
                month = 1
                year += 1
            if datetime(year, month, 1) > until_dt:
                break
    return dates


# ---------------------------------------------------------------------------
# Catalogue helpers
# ---------------------------------------------------------------------------

def _parse_agora_field(raw_value):
    """Parse Agora string-serialised Python dict/list, or return None for 'False'/'[]'."""
    if not raw_value or raw_value == "False" or raw_value == "[]":
        return None
    if isinstance(raw_value, (list, dict)):
        return raw_value
    try:
        return ast.literal_eval(str(raw_value))
    except Exception:
        return None


def _agora_date(value) -> str:
    """Convert Agora datetime string "2026-10-22 06:00:00" to ISO "2026-10-22T06:00:00"."""
    if not value or value == "False":
        return ""
    try:
        return str(value).replace(" ", "T")
    except Exception:
        return ""


def _extract_unis(raw_partners) -> list[str]:
    """Return list of internal university codes from Agora x_partners field."""
    parsed = _parse_agora_field(raw_partners)
    if not parsed:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    codes = []
    for p in parsed:
        name = p.get("name", "").strip().upper()
        code = _UNI_NAME_TO_CODE.get(name)
        if code:
            codes.append(code)
        else:
            # Unknown university — use a short derived code
            short = re.sub(r'[^A-Z]', '', name)[:5]
            if short and short not in codes:
                codes.append(short)
    return codes


def _extract_event_type(raw_event_type) -> str:
    parsed = _parse_agora_field(raw_event_type)
    if not parsed:
        return "Other public events"
    name = parsed.get("name", "") if isinstance(parsed, dict) else ""
    return _EVENT_TYPE_MAP.get(name, "Other public events")


def _html_to_plain(html: str) -> str:
    """Strip HTML tags for plain text description preview."""
    if not html or html == "False":
        return ""
    return re.sub(r'<[^>]+>', ' ', html).replace('&nbsp;', ' ').strip()


def _agora_item_to_event(item: dict) -> dict:
    """Convert one Agora catalogue item to our event format."""
    fields = item.get("fields", {})
    catalogue_id = item.get("id")
    name = fields.get("name") or fields.get("display_name") or "(Untitled)"
    category = _extract_event_type(fields.get("x_event_type"))
    unis = _extract_unis(fields.get("x_partners"))
    description_html = fields.get("x_description", "")
    if not description_html or description_html == "False":
        description_html = ""
    reg_link = fields.get("x_link", "")
    if not reg_link or reg_link == "False":
        reg_link = ""
    image = fields.get("x_image", "")
    if not image or image == "False":
        image = ""

    # BIP component dates: virtual (mandatory-ish) + physical + posterior (optional)
    virt_start = _agora_date(fields.get("x_virtualcomponentdatestart"))
    virt_end   = _agora_date(fields.get("x_virtualcomponentdateend"))
    phys_start = _agora_date(fields.get("x_physicaldatebipstart"))
    phys_end   = _agora_date(fields.get("x_physicaldatebipend"))
    post_start = _agora_date(fields.get("x_posteriorcomponentstart"))
    post_end   = _agora_date(fields.get("x_posteriorcomponentend"))

    component_starts = [d for d in (virt_start, phys_start, post_start) if d]
    component_ends = [d for d in (virt_end, phys_end, post_end) if d]
    if component_starts or component_ends:
        # BIP component fields take priority over x_date/x_end_date
        start = min(component_starts) if component_starts else None
        end = max(component_ends) if component_ends else start
    else:
        start = _agora_date(fields.get("x_date"))
        end   = _agora_date(fields.get("x_end_date"))

    # Discrete date ranges the event actually occupies (so the calendar can
    # highlight just those days instead of filling the gap between components).
    date_segments = []
    if virt_start:
        date_segments.append({"start": virt_start, "end": virt_end or virt_start, "label": "Virtual component"})
    if phys_start:
        date_segments.append({"start": phys_start, "end": phys_end or phys_start, "label": "Physical component"})
    if post_start:
        date_segments.append({"start": post_start, "end": post_end or post_start, "label": "Posterior component"})
    if not date_segments and start:
        date_segments.append({"start": start, "end": end or start, "label": ""})

    # Determine if physical or virtual (BIPs have both components)
    if phys_start and virt_start:
        event_type = "Physical"  # main event is physical; virtual component noted in description
    elif virt_start:
        event_type = "Virtual"
    else:
        event_type = "Physical"

    place = ""
    meeting_url = ""

    return {
        "id": f"cat{catalogue_id}",
        "catalogue_id": catalogue_id,
        "source": "catalogue",
        "name": name,
        "description": description_html,
        "category": category,
        "university": unis[0] if unis else "",
        "universities": unis,
        "uninovis_group": "",
        "event_type": event_type,
        "place": place,
        "meeting_url": meeting_url,
        "timezone": "CEST",
        "start_date": start,
        "end_date": end if end else start,
        "date_segments": date_segments,
        "registration_link": reg_link,
        "image": image,
        "visibility": "shared",
        "date_tbc": not bool(start),
        "date_tbc_label": "" if start else "TBC",
        "participants": [],
        "participant_groups": [],
        "series_id": "",
        "created_by": "agora_catalogue",
        # Extra Agora-specific info
        "x_virtual_start": virt_start,
        "x_virtual_end":   virt_end,
        "x_physical_start": phys_start,
        "x_physical_end":   phys_end,
        "x_posterior_start": post_start,
        "x_posterior_end":   post_end,
        "x_programme": fields.get("x_programme", ""),
        "x_target_group": _parse_agora_field(fields.get("x_target_group")),
        "x_number_of_participants": fields.get("x_numberofparticipants", "0"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    can_edit = _can_edit_check(session)
    return {
        "username": session["username"],
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "can_edit": can_edit,
    }


@router.get("/api/events")
def get_events(session: dict = Depends(_require_auth)):
    """Return shared events + user's personal events + cached catalogue events."""
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    catalogue = data.get("catalogue_events", [])
    personal = load_personal(session["username"])
    return shared + catalogue + personal


@router.get("/api/config")
def get_config(session: dict = Depends(_require_auth)):
    data = load_data()
    return {
        "categories": data["categories"],
        "universities": data.get("universities", []),
    }


@router.get("/api/directory")
def get_directory(session: dict = Depends(_require_auth)):
    directory = load_directory()
    groups = [{"id": g["id"], "name": g["name"], "subgroups": g.get("subgroups", [])} for g in directory.get("groups", [])]
    users = [
        {
            "id": u["id"],
            "first_name": u["first_name"],
            "family_name": u["family_name"],
            "email": u["email"],
            "university": u.get("university", ""),
            "groups": u.get("groups", []),
            "subgroups": u.get("subgroups", []),
        }
        for u in directory.get("users", [])
    ]
    return {"groups": groups, "users": users}


# ---------------------------------------------------------------------------
# Catalogue sync
# ---------------------------------------------------------------------------

@router.get("/api/catalogue/status")
def catalogue_status(session: dict = Depends(_require_auth)):
    """Return last sync time and count of cached catalogue events."""
    data = load_data()
    return {
        "last_sync": data.get("catalogue_last_sync"),
        "count": len(data.get("catalogue_events", [])),
        "token_configured": bool(_catalogue_token()),
    }


@router.post("/api/catalogue/sync")
async def catalogue_sync(session: dict = Depends(_require_editor)):
    """Fetch all events from the Agora catalogue API and cache them locally."""
    token = _catalogue_token()
    if not token:
        raise HTTPException(400, "CATALOGUE_API_TOKEN is not configured in web/.env")

    url = f"{CATALOGUE_API_BASE}/{CATALOGUE_MODEL}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    except Exception as e:
        raise HTTPException(502, f"Could not reach Agora API: {e}")

    if resp.status_code == 401:
        raise HTTPException(401, "Agora API returned 401 — the token may be expired. Generate a new token at uninovis.widening.eu and update CATALOGUE_API_TOKEN in web/.env")
    if resp.status_code != 200:
        raise HTTPException(502, f"Agora API returned {resp.status_code}: {resp.text[:200]}")

    payload = resp.json()
    items = payload.get("items", [])

    # Only import validated events
    validated = [i for i in items if str(i.get("fields", {}).get("validated", "")).lower() == "true"]

    converted = [_agora_item_to_event(i) for i in validated]

    data = load_data()
    data["catalogue_events"] = converted
    data["catalogue_last_sync"] = datetime.utcnow().isoformat() + "Z"
    save_data(data)

    return {
        "ok": True,
        "synced": len(converted),
        "total_in_api": len(items),
        "last_sync": data["catalogue_last_sync"],
    }


# ---------------------------------------------------------------------------
# Event CRUD (identical to event_calendar)
# ---------------------------------------------------------------------------

class EventBody(BaseModel):
    name: str
    description: str = ""
    category: str
    university: str = ""
    universities: list[str] = []
    uninovis_group: str = ""
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
    visibility: str = "shared"
    date_tbc: bool = False
    date_tbc_label: str = ""
    recurrence: Optional[dict] = None
    series_id: Optional[str] = None
    virtual_pre_name: str = ""
    virtual_pre_start: str = ""
    virtual_pre_end: str = ""
    virtual_pre_url: str = ""
    virtual_post_name: str = ""
    virtual_post_start: str = ""
    virtual_post_end: str = ""
    virtual_post_url: str = ""


def _build_event(body: EventBody, start_date: str, end_date: str, series_id: str, username: str) -> dict:
    unis = body.universities if body.universities else ([body.university] if body.university else [])
    return {
        "id": "evt" + str(uuid.uuid4())[:8],
        "name": body.name,
        "description": body.description,
        "category": body.category,
        "university": unis[0] if unis else "",
        "universities": unis,
        "uninovis_group": body.uninovis_group,
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


def _build_virtual_components(body: EventBody, parent_id: str, username: str) -> list:
    components = []
    unis = body.universities if body.universities else ([body.university] if body.university else [])
    if body.virtual_pre_name and body.virtual_pre_start:
        components.append({
            "id": "evt" + str(uuid.uuid4())[:8],
            "name": body.virtual_pre_name,
            "description": f"Virtual component (before {body.name})",
            "category": body.category,
            "university": unis[0] if unis else "",
            "universities": unis,
            "event_type": "Virtual",
            "place": "",
            "meeting_url": body.virtual_pre_url,
            "timezone": body.timezone,
            "start_date": body.virtual_pre_start,
            "end_date": body.virtual_pre_end or body.virtual_pre_start,
            "registration_link": body.registration_link,
            "image": "",
            "visibility": body.visibility,
            "date_tbc": False,
            "date_tbc_label": "",
            "participants": body.participants,
            "participant_groups": body.participant_groups,
            "series_id": "",
            "created_by": username,
            "linked_event": parent_id,
            "component_type": "pre",
        })
    if body.virtual_post_name and body.virtual_post_start:
        components.append({
            "id": "evt" + str(uuid.uuid4())[:8],
            "name": body.virtual_post_name,
            "description": f"Virtual component (after {body.name})",
            "category": body.category,
            "university": unis[0] if unis else "",
            "universities": unis,
            "event_type": "Virtual",
            "place": "",
            "meeting_url": body.virtual_post_url,
            "timezone": body.timezone,
            "start_date": body.virtual_post_start,
            "end_date": body.virtual_post_end or body.virtual_post_start,
            "registration_link": body.registration_link,
            "image": "",
            "visibility": body.visibility,
            "date_tbc": False,
            "date_tbc_label": "",
            "participants": body.participants,
            "participant_groups": body.participant_groups,
            "series_id": "",
            "created_by": username,
            "linked_event": parent_id,
            "component_type": "post",
        })
    return components


def _validate_event(body: EventBody, data: dict):
    if body.category not in data["categories"]:
        raise HTTPException(400, f"Unknown category: {body.category}")
    if body.event_type not in ("Virtual", "Physical"):
        raise HTTPException(400, "event_type must be 'Virtual' or 'Physical'")
    if not body.date_tbc and (not body.start_date or not body.end_date):
        raise HTTPException(400, "Start and end dates are required unless date_tbc is true")


def _require_auth_or_editor(visibility: str, session: dict):
    if visibility == "personal":
        return
    if not _can_edit_check(session):
        raise HTTPException(403, "Only editors can create shared events")


def _store_event(ev: dict, username: str):
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
        components = _build_virtual_components(body, ev["id"], session["username"])
        for comp in components:
            _store_event(comp, session["username"])
        return ev


def _update_ev_fields(ev: dict, body: EventBody):
    ev["name"] = body.name
    ev["description"] = body.description
    ev["category"] = body.category
    unis = body.universities if body.universities else ([body.university] if body.university else [])
    ev["university"] = unis[0] if unis else ""
    ev["universities"] = unis
    ev["uninovis_group"] = body.uninovis_group
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

    personal = load_personal(session["username"])
    for ev in personal:
        if ev["id"] == event_id:
            _update_ev_fields(ev, body)
            save_personal(session["username"], personal)
            return ev

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
    personal = load_personal(session["username"])
    before_p = len(personal)
    personal = [ev for ev in personal if ev["id"] != event_id]
    if len(personal) < before_p:
        save_personal(session["username"], personal)
        return {"ok": True}

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
    data = load_data()
    before = len(data["events"])
    data["events"] = [ev for ev in data["events"] if ev.get("series_id") != series_id]
    deleted = before - len(data["events"])
    if deleted == 0:
        raise HTTPException(404, "Series not found")
    save_data(data)
    return {"ok": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

TSV_FIELDS = [
    "id", "name", "description", "category", "university", "event_type",
    "timezone", "place", "meeting_url", "start_date", "end_date",
    "registration_link", "date_tbc", "date_tbc_label", "series_id", "created_by",
]

TZ_OFFSETS = {
    "CET": "+0100", "CEST": "+0200", "EET": "+0200", "EEST": "+0300",
    "WET": "+0000", "WEST": "+0100", "GMT": "+0000", "UTC": "+0000",
}


def _ical_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _to_ical_dt(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y%m%dT%H%M%S")


def _generate_ics(events_list: list) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UNINOVIS//Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:UNINOVIS Calendar",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]
    for ev in events_list:
        if not ev.get("start_date") or not ev.get("end_date"):
            continue
        tz = ev.get("timezone", "CEST")
        tzid = "Europe/Berlin"
        tbc_prefix = "[TBC] " if ev.get("date_tbc") else ""
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev['id']}@uninovis.calendar")
        lines.append(f"DTSTART;TZID={tzid}:{_to_ical_dt(ev['start_date'])}")
        lines.append(f"DTEND;TZID={tzid}:{_to_ical_dt(ev['end_date'])}")
        lines.append(f"SUMMARY:{_ical_escape(tbc_prefix + ev['name'])}")
        desc_parts = []
        if ev.get("date_tbc"):
            desc_parts.append(f"Date: To Be Confirmed ({ev.get('date_tbc_label', 'TBC')})")
        if ev.get("description"):
            # Strip HTML tags for iCal
            plain = re.sub(r'<[^>]+>', ' ', ev["description"])
            desc_parts.append(plain[:500])
        if ev.get("category"):
            desc_parts.append(f"Category: {ev['category']}")
        if ev.get("registration_link"):
            desc_parts.append(f"Registration: {ev['registration_link']}")
        if ev.get("source") == "catalogue":
            desc_parts.append("Source: UNINOVIS Event Catalogue")
        lines.append(f"DESCRIPTION:{_ical_escape(chr(10).join(desc_parts))}")
        if ev.get("event_type") == "Physical" and ev.get("place"):
            lines.append(f"LOCATION:{_ical_escape(ev['place'])}")
        if ev.get("registration_link"):
            lines.append(f"URL:{ev['registration_link']}")
        if ev.get("category"):
            lines.append(f"CATEGORIES:{_ical_escape(ev['category'])}")
        lines.append(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


@router.get("/api/feed/ical")
def ical_feed(token: str = Query("")):
    session = get_session(token) if token else None
    if not session:
        raise HTTPException(401, "Invalid or expired token")
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    catalogue = data.get("catalogue_events", [])
    personal = load_personal(session["username"])
    ics = _generate_ics(shared + catalogue + personal)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": "inline; filename=uninovis_calendar.ics",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get("/api/export/ical")
def export_ical(session: dict = Depends(_require_auth)):
    data = load_data()
    shared = [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
    catalogue = data.get("catalogue_events", [])
    personal = load_personal(session["username"])
    ics = _generate_ics(shared + catalogue + personal)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=uninovis_calendar.ics"},
    )


def _filter_events(events: list, date_from: str, date_to: str, university: str, category: str) -> list:
    result = events
    if date_from:
        result = [ev for ev in result if ev.get("start_date", "") >= date_from]
    if date_to:
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
    data = load_data()
    all_events = (
        [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
        + data.get("catalogue_events", [])
    )
    filtered = _filter_events(all_events, date_from, date_to, university, category)
    content = json.dumps(filtered, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=uninovis_calendar.json"},
    )


@router.get("/api/export/tsv")
def export_tsv(
    session: dict = Depends(_require_auth),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
    university: str = Query(""),
    category: str = Query(""),
):
    data = load_data()
    all_events = (
        [ev for ev in data["events"] if ev.get("visibility", "shared") == "shared"]
        + data.get("catalogue_events", [])
    )
    filtered = _filter_events(all_events, date_from, date_to, university, category)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TSV_FIELDS, extrasaction="ignore", delimiter="\t")
    writer.writeheader()
    for ev in filtered:
        writer.writerow(ev)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": "attachment; filename=uninovis_calendar.tsv"},
    )


class ImportResult(BaseModel):
    added: int = 0
    updated: int = 0
    errors: list[str] = []


@router.post("/api/import/json")
async def import_json(file: UploadFile = File(...), session: dict = Depends(_require_editor)):
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
