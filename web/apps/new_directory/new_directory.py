"""
UNINOVIS New Directory — read-only staff directory for UNINOVIS partner
universities, mirroring https://uninovis.widening.eu/directory.

Data is served entirely from the local data.json snapshot; there is no
live API call at request time.
"""

import os

import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/new-directory", tags=["new_directory"])

# ---------------------------------------------------------------------------
# Auth helpers (same pattern as apps/directory and apps/event_tracker)
# ---------------------------------------------------------------------------

from auth import get_session, can_edit as _can_edit_check, user_roles as _user_roles


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


# Creating people/units is restricted to content_manager and superuser —
# a narrower set than the general EDITOR_ROLES used for read/write elsewhere.
_CONTENT_MANAGER_ROLES = {"content_manager", "superuser"}


def _require_content_manager(session: dict = Depends(_require_auth)) -> dict:
    if not (_CONTENT_MANAGER_ROLES & set(_user_roles(session))):
        raise HTTPException(status_code=403, detail="content_manager or superuser role required")
    return session


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


# ---------------------------------------------------------------------------
# Create person / unit — content_manager and superuser only
# ---------------------------------------------------------------------------

class PersonUnitAssignment(BaseModel):
    unit_id: int
    role: str = ""


class PersonCreate(BaseModel):
    first_name: str
    family_name: str
    email: str = ""
    phone: str = ""
    position: str = ""
    university: str = ""
    units: list[PersonUnitAssignment] = []


class UnitCreate(BaseModel):
    name: str
    parent_id: int | None = None
    university: str = ""


@router.post("/api/people")
def create_person(body: PersonCreate, session: dict = Depends(_require_content_manager)):
    first_name = body.first_name.strip()
    family_name = body.family_name.strip()
    if not first_name or not family_name:
        raise HTTPException(status_code=400, detail="First name and family name are required")
    if body.university and body.university not in UNIVERSITIES:
        raise HTTPException(status_code=400, detail=f"Unknown university: {body.university}")

    data = load_data()
    unit_ids = {u["id"] for u in data.get("units", [])}
    for assignment in body.units:
        if assignment.unit_id not in unit_ids:
            raise HTTPException(status_code=400, detail=f"Unknown unit: {assignment.unit_id}")

    new_id = max([p["id"] for p in data.get("people", [])], default=0) + 1
    person = {
        "id": new_id,
        "first_name": first_name,
        "family_name": family_name,
        "email": body.email.strip(),
        "phone": body.phone.strip(),
        "position": body.position.strip(),
        "university": body.university,
        "university_name": UNIVERSITIES.get(body.university, {}).get("name", ""),
    }
    data.setdefault("people", []).append(person)
    seen_units = set()
    for assignment in body.units:
        if assignment.unit_id in seen_units:
            continue
        seen_units.add(assignment.unit_id)
        data.setdefault("memberships", []).append({
            "person_id": new_id,
            "unit_id": assignment.unit_id,
            "role": assignment.role.strip(),
        })
    save_data(data)
    return {"ok": True, "id": new_id}


@router.post("/api/units")
def create_unit(body: UnitCreate, session: dict = Depends(_require_content_manager)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Unit name is required")
    if body.university and body.university not in UNIVERSITIES:
        raise HTTPException(status_code=400, detail=f"Unknown university: {body.university}")

    data = load_data()
    if body.parent_id is not None and not any(u["id"] == body.parent_id for u in data.get("units", [])):
        raise HTTPException(status_code=400, detail="Unknown parent unit")

    new_id = max([u["id"] for u in data.get("units", [])], default=0) + 1
    unit = {
        "id": new_id,
        "name": name,
        "parent_id": body.parent_id,
        "university": body.university,
        "university_name": UNIVERSITIES.get(body.university, {}).get("name", ""),
    }
    data.setdefault("units", []).append(unit)
    save_data(data)
    return {"ok": True, "id": new_id}


# ---------------------------------------------------------------------------
# Self-service profile — any authenticated user can view/edit their OWN
# directory entry, matched by email == login username. No role restriction:
# this is not the content_manager/superuser create-anyone flow above.
# ---------------------------------------------------------------------------

class MyProfileUpdate(BaseModel):
    first_name: str
    family_name: str
    phone: str = ""
    position: str = ""
    university: str = ""
    units: list[PersonUnitAssignment] = []


def _find_person_by_email(data: dict, email: str) -> dict | None:
    email_lower = email.lower()
    return next((p for p in data.get("people", []) if p.get("email", "").lower() == email_lower), None)


@router.get("/api/my-profile")
def get_my_profile(session: dict = Depends(_require_auth)):
    username = session.get("username", "")
    if not username or username == "guest":
        raise HTTPException(status_code=404, detail="No directory profile found")

    data = load_data()
    person = _find_person_by_email(data, username)
    if not person:
        raise HTTPException(status_code=404, detail="No directory profile found")

    memberships = [
        {"unit_id": m["unit_id"], "role": m.get("role", "")}
        for m in data.get("memberships", [])
        if m["person_id"] == person["id"]
    ]
    return {**person, "memberships": memberships}


@router.put("/api/my-profile")
def update_my_profile(body: MyProfileUpdate, session: dict = Depends(_require_auth)):
    username = session.get("username", "")
    if not username or username == "guest":
        raise HTTPException(status_code=403, detail="Authentication required")

    first_name = body.first_name.strip()
    family_name = body.family_name.strip()
    if not first_name or not family_name:
        raise HTTPException(status_code=400, detail="First name and family name are required")
    if body.university and body.university not in UNIVERSITIES:
        raise HTTPException(status_code=400, detail=f"Unknown university: {body.university}")

    data = load_data()
    person = _find_person_by_email(data, username)
    if not person:
        raise HTTPException(status_code=404, detail="No directory profile found for your account")

    unit_ids = {u["id"] for u in data.get("units", [])}
    for assignment in body.units:
        if assignment.unit_id not in unit_ids:
            raise HTTPException(status_code=400, detail=f"Unknown unit: {assignment.unit_id}")

    person["first_name"] = first_name
    person["family_name"] = family_name
    person["phone"] = body.phone.strip()
    person["position"] = body.position.strip()
    person["university"] = body.university
    person["university_name"] = UNIVERSITIES.get(body.university, {}).get("name", "")

    # Replace this person's memberships wholesale with the submitted set
    data["memberships"] = [m for m in data.get("memberships", []) if m["person_id"] != person["id"]]
    seen_units = set()
    for assignment in body.units:
        if assignment.unit_id in seen_units:
            continue
        seen_units.add(assignment.unit_id)
        data["memberships"].append({
            "person_id": person["id"],
            "unit_id": assignment.unit_id,
            "role": assignment.role.strip(),
        })

    save_data(data)
    return {"ok": True, "id": person["id"]}
