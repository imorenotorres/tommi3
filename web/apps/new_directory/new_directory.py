"""
UNINOVIS New Directory — read-only staff directory synced from the Agora
Directory API (Directory Person / Directory Unit / Directory Membership
models), mirroring https://uninovis.widening.eu/directory.

Follows the same sync pattern as apps/event_tracker's Event Catalogue sync:
a token-authenticated Agora API is pulled on demand via POST /api/sync and
the normalised result is cached locally in data.json.

Field mapping confirmed against a live token scoped to agora_directory.person/
.unit/.membership: person affiliation lives on affiliation_partner_id /
affiliation_names_display, and membership links use person_id / unit_id (see
_agora_item_to_person/_unit/_membership). The Agora API paginates at 50 items
per page, so _fetch_all_items walks every page via ?page=N before mapping.
"""

import ast
import os
from datetime import datetime

import httpx
import json
from dotenv import dotenv_values
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

router = APIRouter(prefix="/new-directory", tags=["new_directory"])

# ---------------------------------------------------------------------------
# Auth helpers (same pattern as apps/directory and apps/event_tracker)
# ---------------------------------------------------------------------------

from auth import get_session, can_edit as _can_edit_check


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
# Agora Directory API config
# ---------------------------------------------------------------------------

DIRECTORY_API_BASE = "https://uninovis.widening.eu/catalogue-api/v2"
DIRECTORY_PERSON_MODEL = os.getenv("DIRECTORY_PERSON_MODEL", "alliance_directory_app.directoryperson")
DIRECTORY_UNIT_MODEL = os.getenv("DIRECTORY_UNIT_MODEL", "alliance_directory_app.directoryunit")
DIRECTORY_MEMBERSHIP_MODEL = os.getenv("DIRECTORY_MEMBERSHIP_MODEL", "alliance_directory_app.directorymembership")


def _directory_token() -> str:
    token = os.getenv("DIRECTORY_API_TOKEN") or os.getenv("EVENT_CATALOGUE_API_TOKEN", "")
    if not token:
        env = dotenv_values(ENV_PATH)
        token = env.get("DIRECTORY_API_TOKEN") or env.get("EVENT_CATALOGUE_API_TOKEN", "")
    return token


# University name → internal code (same mapping used by apps/event_tracker)
_UNI_NAME_TO_CODE = {
    "KAUNO KOLEGIJA": "KK",
    "UNIVERSIDAD DE MÁLAGA": "UMA",
    "UNIVERSITE PARIS 13": "USPN",
    "TAMPEREEN AMMATTIKORKEAKOULU OY": "TAMK",
    "THE HAGUE UNIVERSITY OF APPLIED SCIENCES": "THUAS",
    "UNIVERSITA DEGLI STUDI DELLA CAMPANIA LUIGI VANVITELLI": "UDCLV",
    "TECHNISCHE HOCHSCHULE WUERZBURG-SCHWEINFURT": "THWS",
    "UNIVERSITETI I TIRANËS": "UT",
}

# Static university reference data (website links to be filled in once known)
UNIVERSITIES = {
    "USPN": {"name": "Université Sorbonne Paris Nord", "country": "FR", "website": ""},
    "UDCLV": {"name": "University of Campania \"Luigi Vanvitelli\"", "country": "IT", "website": ""},
    "UMA": {"name": "Universidad de Málaga", "country": "ES", "website": ""},
    "KK": {"name": "Kauno kolegija Higher Education Institution", "country": "LT", "website": ""},
    "UT": {"name": "University of Tirana", "country": "AL", "website": ""},
    "THWS": {"name": "Technical University of Applied Sciences Würzburg-Schweinfurt", "country": "DE", "website": ""},
    "TAMK": {"name": "Tampere University of Applied Sciences", "country": "FI", "website": ""},
    "THUAS": {"name": "The Hague University of Applied Sciences", "country": "NL", "website": ""},
}


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------

DEFAULT_DATA = {
    "people": [],
    "units": [],
    "memberships": [],
    "last_sync": None,
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


# ---------------------------------------------------------------------------
# Agora field parsing (same helpers as apps/event_tracker)
# ---------------------------------------------------------------------------

def _parse_agora_field(raw_value):
    """Parse Agora string-serialised Python dict/list/tuple, or None for 'False'/'[]'."""
    if not raw_value or raw_value == "False" or raw_value == "[]":
        return None
    if isinstance(raw_value, (list, dict, tuple)):
        return raw_value
    try:
        return ast.literal_eval(str(raw_value))
    except Exception:
        return None


def _clean(value):
    if not value or value == "False":
        return ""
    return str(value)


def _odoo_ref(raw):
    """Parse an Odoo-style relational field: False, [id, 'Name'], or {'id':.., 'name':..}.
    Returns (id, name) or (None, None)."""
    parsed = _parse_agora_field(raw) if isinstance(raw, str) else raw
    if not parsed:
        return None, None
    if isinstance(parsed, dict):
        return parsed.get("id"), parsed.get("name") or parsed.get("display_name")
    if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
        return parsed[0], parsed[1]
    return None, None


def _agora_item_to_person(item: dict) -> dict:
    f = item.get("fields", {})
    first = _clean(f.get("first_name") or f.get("x_first_name"))
    last = _clean(f.get("family_name") or f.get("last_name") or f.get("x_family_name"))
    full_name = _clean(f.get("name") or f.get("display_name"))
    if not first and not last and full_name:
        parts = full_name.split(" ", 1)
        first, last = parts[0], (parts[1] if len(parts) > 1 else "")
    # Real Agora field for the person's home institution is affiliation_partner_id
    # (an Odoo res.partner ref); affiliation_names_display already gives the short code.
    uni_id, uni_name = _odoo_ref(f.get("affiliation_partner_id"))
    uni_code = _clean(f.get("affiliation_names_display")) or _UNI_NAME_TO_CODE.get((uni_name or "").strip().upper(), "")
    return {
        "id": item.get("id"),
        "first_name": first,
        "family_name": last,
        "email": _clean(f.get("email") or f.get("x_email")),
        "phone": _clean(f.get("phone") or f.get("mobile") or f.get("x_phone")),
        "position": _clean(f.get("position_titles_display") or f.get("position") or f.get("job_title")),
        "university": uni_code,
        "university_name": uni_name or "",
    }


def _agora_item_to_unit(item: dict) -> dict:
    f = item.get("fields", {})
    parent_id, _parent_name = _odoo_ref(f.get("parent_unit") or f.get("x_parent_unit") or f.get("parent_id"))
    uni_id, uni_name = _odoo_ref(f.get("university") or f.get("x_university"))
    uni_code = _UNI_NAME_TO_CODE.get((uni_name or "").strip().upper(), "")
    return {
        "id": item.get("id"),
        "name": _clean(f.get("name") or f.get("display_name")) or "(Unnamed unit)",
        "parent_id": parent_id,
        "university": uni_code,
        "university_name": uni_name or "",
    }


def _agora_item_to_membership(item: dict) -> dict:
    f = item.get("fields", {})
    person_id, _ = _odoo_ref(f.get("person_id") or f.get("person") or f.get("x_person"))
    unit_id, _ = _odoo_ref(f.get("unit_id") or f.get("unit") or f.get("x_unit"))
    return {
        "person_id": person_id,
        "unit_id": unit_id,
        "role": _clean(f.get("position_title_display") or f.get("position_description") or f.get("role")),
    }


async def _fetch_model(client: httpx.AsyncClient, model: str, token: str):
    return await client.get(f"{DIRECTORY_API_BASE}/{model}", headers={"Authorization": f"Bearer {token}"})


async def _fetch_all_items(client: httpx.AsyncClient, label: str, model: str, token: str) -> list:
    """Fetch every page for a model (the Agora API paginates at 50 items/page) and
    return the combined list of raw items."""
    items = []
    page = 1
    while True:
        resp = await client.get(
            f"{DIRECTORY_API_BASE}/{model}",
            headers={"Authorization": f"Bearer {token}"},
            params={"page": page},
        )
        if resp.status_code == 401:
            raise HTTPException(401, f"Agora API returned 401 for the {label} model — the token may be expired. Generate a new token at uninovis.widening.eu and update DIRECTORY_API_TOKEN in web/.env")
        if resp.status_code == 403:
            raise HTTPException(403, f"Agora API returned 403 for the {label} model ({model}) — the token is not scoped to this model, or the model name is wrong. Check GET /new-directory/api/sync/raw-sample")
        if resp.status_code != 200:
            raise HTTPException(502, f"Agora API returned {resp.status_code} for the {label} model: {resp.text[:200]}")
        body = resp.json()
        items.extend(body.get("items", []))
        total_pages = body.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
    return items


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------

def _build_unit_tree(units: list, memberships: list, people_by_id: dict, university: str | None = None) -> list:
    """Build the unit/subunit hierarchy with members attached.

    UNINOVIS units (WP3, Content Managers, etc.) are cross-institutional working
    groups — they are not owned by a single university, so unit["university"] is
    always empty. Filtering by university therefore happens per-member: when
    `university` is given, each node keeps only members from that university,
    and any branch left with no qualifying members anywhere below it is pruned.
    """
    people_by_unit: dict = {}
    for m in memberships:
        if m["unit_id"] is not None:
            people_by_unit.setdefault(m["unit_id"], []).append(m["person_id"])

    units_by_id = {u["id"]: u for u in units}
    children: dict = {}
    roots = []
    for u in units:
        pid = u.get("parent_id")
        if pid and pid in units_by_id:
            children.setdefault(pid, []).append(u["id"])
        else:
            roots.append(u["id"])

    def node(uid):
        u = units_by_id[uid]
        members = [people_by_id[pid] for pid in people_by_unit.get(uid, []) if pid in people_by_id]
        if university:
            members = [p for p in members if p.get("university") == university]
        members.sort(key=lambda p: (p.get("family_name", ""), p.get("first_name", "")))
        subunits = [n for n in (node(cid) for cid in children.get(uid, [])) if n is not None]
        if university and not members and not subunits:
            return None
        return {
            "id": u["id"],
            "name": u["name"],
            "university": u["university"],
            "university_name": u["university_name"],
            "members": members,
            "subunits": subunits,
        }

    return [n for n in (node(rid) for rid in roots) if n is not None]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    return {
        "username": session["username"],
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "can_edit": _can_edit_check(session),
    }


@router.get("/api/status")
def status(session: dict = Depends(_require_auth)):
    data = load_data()
    return {
        "last_sync": data.get("last_sync"),
        "people": len(data.get("people", [])),
        "units": len(data.get("units", [])),
        "memberships": len(data.get("memberships", [])),
        "token_configured": bool(_directory_token()),
    }


@router.get("/api/people")
def get_people(session: dict = Depends(_require_auth)):
    data = load_data()
    units_by_id = {u["id"]: u for u in data.get("units", [])}
    units_by_person: dict = {}
    for m in data.get("memberships", []):
        if m["person_id"] is not None:
            units_by_person.setdefault(m["person_id"], []).append(m["unit_id"])

    result = []
    for p in data.get("people", []):
        unit_names = [units_by_id[uid]["name"] for uid in units_by_person.get(p["id"], []) if uid in units_by_id]
        result.append({**p, "units": unit_names})
    return result


@router.get("/api/units")
def get_units(session: dict = Depends(_require_auth), university: str = Query("")):
    data = load_data()
    people_by_id = {p["id"]: p for p in data.get("people", [])}
    return _build_unit_tree(data.get("units", []), data.get("memberships", []), people_by_id, university or None)


@router.get("/api/universities")
def get_universities(session: dict = Depends(_require_auth)):
    data = load_data()
    counts: dict = {}
    for p in data.get("people", []):
        if p.get("university"):
            counts[p["university"]] = counts.get(p["university"], 0) + 1
    return [
        {
            "code": code,
            "name": info["name"],
            "country": info["country"],
            "website": info["website"],
            "staff_count": counts.get(code, 0),
        }
        for code, info in sorted(UNIVERSITIES.items())
    ]


@router.post("/api/sync")
async def sync(session: dict = Depends(_require_editor)):
    """Fetch Person/Unit/Membership records from the Agora Directory API and cache them locally."""
    token = _directory_token()
    if not token:
        raise HTTPException(400, "DIRECTORY_API_TOKEN is not configured in web/.env")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            person_items = await _fetch_all_items(client, "person", DIRECTORY_PERSON_MODEL, token)
            unit_items = await _fetch_all_items(client, "unit", DIRECTORY_UNIT_MODEL, token)
            membership_items = await _fetch_all_items(client, "membership", DIRECTORY_MEMBERSHIP_MODEL, token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Could not reach Agora API: {e}")

    people = [_agora_item_to_person(i) for i in person_items]
    units = [_agora_item_to_unit(i) for i in unit_items]
    memberships = [_agora_item_to_membership(i) for i in membership_items]
    memberships = [m for m in memberships if m["person_id"] is not None and m["unit_id"] is not None]

    data = load_data()
    data["people"] = people
    data["units"] = units
    data["memberships"] = memberships
    data["last_sync"] = datetime.utcnow().isoformat() + "Z"
    save_data(data)

    return {
        "ok": True,
        "people": len(people),
        "units": len(units),
        "memberships": len(memberships),
        "last_sync": data["last_sync"],
    }


@router.get("/api/sync/raw-sample")
async def sync_raw_sample(session: dict = Depends(_require_editor)):
    """Return one raw (unmapped) Agora item per model, to verify/correct the
    provisional field-name mapping once a real Directory-scoped token exists."""
    token = _directory_token()
    if not token:
        raise HTTPException(400, "DIRECTORY_API_TOKEN is not configured in web/.env")

    sample = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for key, model in (
            ("person", DIRECTORY_PERSON_MODEL),
            ("unit", DIRECTORY_UNIT_MODEL),
            ("membership", DIRECTORY_MEMBERSHIP_MODEL),
        ):
            resp = await _fetch_model(client, model, token)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                sample[key] = items[0] if items else None
            else:
                sample[key] = {"error": resp.status_code, "body": resp.text[:200]}
    return sample
