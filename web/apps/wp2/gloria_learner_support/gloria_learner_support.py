"""
Gloria Learner Support — the private (login-only) section of the UNINOVIS
Learning Support site (WP2, T2.4). The public pages (landing, framework,
open partner pages) live on www.uninovis.eu; this app holds the catalogue
of support services behind login.

Structure, following the Learning Support Framework in D2.1:
  - support types (Academic / Non-Academic / Mixed), learner groups
    (Starters / Pros / Graduates) and target groups (International /
    National / Both) are shared alliance-wide and edited by superusers only;
  - each of the 8 partners has a page (intro, coordinator, Excellence Hub)
    and a list of services ("fields") under those types;
  - cross-alliance support rooms (Central Support Room, Language Confidence,
    Starters/Pros/Graduates rooms) with their own services.

Editing rights:
  - superuser: everything;
  - content_manager: their OWN university's page and services (university
    taken from their Directory entry, matched on login email), plus the
    cross-alliance rooms;
  - everyone else with access to the tool: read-only, published services only.

Storage is a local data.json (gitignored), created from seed_data.py on first run.
"""

import datetime
import json
import os
import re
import threading
import uuid
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import require_login as _require_auth, user_roles as _user_roles, can_access_tool as _can_access_tool
from apps.wp1.directory.directory import UNIVERSITIES, load_data as _load_directory
from apps.wp2.gloria_learner_support.seed_data import build_seed_data

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

TOOL_ID = "gloria_learner_support"
ALLIANCE = "ALLIANCE"  # scope of services that belong to a cross-alliance room
TAXONOMIES = ("types", "learner_groups", "target_groups")

router = APIRouter(prefix="/gloria-learner-support", tags=["gloria-learner-support"])


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _require_viewer(session: dict = Depends(_require_auth)) -> dict:
    if not _can_access_tool(session, TOOL_ID):
        raise HTTPException(status_code=403, detail="You do not have access to Gloria Learner Support")
    return session


def _is_superuser(session: dict) -> bool:
    return "superuser" in set(_user_roles(session))


def _is_content_manager(session: dict) -> bool:
    return "content_manager" in set(_user_roles(session))


def _own_university(session: dict) -> str | None:
    """The university of the Directory entry matching this user's login email.
    A person's email field may hold several addresses separated by ';'."""
    username = session.get("username", "").strip().lower()
    if not username:
        return None
    for p in _load_directory().get("people", []):
        emails = [e.strip().lower() for e in (p.get("email") or "").split(";")]
        if username in emails:
            return p.get("university") or None
    return None


def _can_edit_scope(session: dict, scope: str, own_uni: str | None) -> bool:
    if _is_superuser(session):
        return True
    if not _is_content_manager(session):
        return False
    if scope == ALLIANCE:
        return True
    return bool(own_uni) and scope == own_uni


def _require_scope(session: dict, scope: str) -> None:
    if not _can_edit_scope(session, scope, _own_university(session)):
        if scope == ALLIANCE:
            raise HTTPException(status_code=403, detail="content_manager or superuser role required")
        raise HTTPException(status_code=403, detail="You can only edit the services of your own university")


def _require_superuser(session: dict = Depends(_require_viewer)) -> dict:
    if not _is_superuser(session):
        raise HTTPException(status_code=403, detail="superuser role required")
    return session


def _require_content_editor(session: dict = Depends(_require_viewer)) -> dict:
    if not (_is_superuser(session) or _is_content_manager(session)):
        raise HTTPException(status_code=403, detail="content_manager or superuser role required")
    return session


# ---------------------------------------------------------------------------
# Data I/O — every read-modify-write runs under _LOCK, and writes go through
# a temp file so a crash mid-write can't leave a truncated data.json.
# ---------------------------------------------------------------------------

_LOCK = threading.RLock()


def load_data() -> dict:
    with _LOCK:
        if not os.path.exists(DATA_PATH):
            data = build_seed_data()
            save_data(data)
            return data
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)


def save_data(data: dict) -> None:
    with _LOCK:
        tmp = DATA_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA_PATH)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _stamp(session: dict) -> dict:
    return {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "updated_by": session.get("username", ""),
    }


def _find(items: list, item_id: str) -> dict | None:
    return next((x for x in items if x.get("id") == item_id), None)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# These rules are mirrored in static/index.html (FIELD_CHECKS) so the form can
# explain a problem before saving; the server checks again because the page
# can be bypassed.
_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_HTML_RE = re.compile(r"<\s*[a-zA-Z/!][^>]*>")
_LINK_LIKE_RE = re.compile(r"^(https?://|www\.|mailto:)", re.IGNORECASE)
_PHONE_RE = re.compile(r"^\+?[0-9 ()./-]{5,30}$")
_LANGUAGES_RE = re.compile(r"^(?:[^\W\d_]|[\s,;/()'\-])*$")


def _invalid(detail: str):
    raise HTTPException(status_code=422, detail=detail)


def _check_link(link: str) -> str:
    """Empty, an http(s) web address with a real host, or mailto:<email>."""
    link = link.strip()
    if not link:
        return link
    if link.lower().startswith("mailto:"):
        if not _EMAIL_RE.match(link[7:]):
            _invalid("Link: after mailto: there must be one valid email address")
        return link
    parsed = urlparse(link)
    if parsed.scheme.lower() not in ("http", "https") or "." not in parsed.netloc or re.search(r"\s", link):
        _invalid("Link must be a full web address starting with https:// (e.g. https://www.uma.es/...) or mailto:")
    return link


def _check_email(email: str, label: str) -> str:
    email = email.strip()
    if email.lower().startswith("mailto:"):
        _invalid(f"{label}: write only the address, without mailto:")
    if email and not _EMAIL_RE.match(email):
        _invalid(f"{label} must be one valid email address, e.g. office@university.eu")
    return email


def _check_text(value: str, label: str, short: bool = False) -> str:
    """Plain text: no HTML markup. Short fields (names, titles) must also not be
    a bare link or email address — those belong in their own fields."""
    value = value.strip()
    if _HTML_RE.search(value):
        _invalid(f"{label} must be plain text (no HTML tags)")
    if short and (_LINK_LIKE_RE.match(value) or _EMAIL_RE.match(value)):
        _invalid(f"{label} must be text, not a link or email address — use the link/email field for that")
    return value


def _check_phone(phone: str) -> str:
    phone = phone.strip()
    if phone and (not _PHONE_RE.match(phone) or sum(ch.isdigit() for ch in phone) < 5):
        _invalid("Contact phone may only contain digits, spaces, + ( ) . - / (e.g. +34 952 13 10 00)")
    return phone


def _check_languages(languages: str) -> str:
    languages = _check_text(languages, "Languages offered", short=True)
    if not _LANGUAGES_RE.match(languages):
        _invalid("Languages offered must be language names separated by commas, e.g. English, German")
    return languages


class ServiceIn(BaseModel):
    scope: str
    type_id: str = ""
    room_id: str = ""
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=3000)
    link: str = Field("", max_length=500)
    contact_name: str = Field("", max_length=200)
    contact_email: str = Field("", max_length=200)
    contact_phone: str = Field("", max_length=60)
    languages: str = Field("", max_length=200)
    learner_group_ids: list[str] = []
    target_group_id: str = ""
    access: Literal["own", "alliance"] = "own"
    status: Literal["draft", "published"] = "draft"


class PartnerIn(BaseModel):
    tagline: str = Field("", max_length=500)
    intro: str = Field("", max_length=5000)
    coordinator: str = Field("", max_length=200)
    coordinator_email: str = Field("", max_length=200)
    excellence_hub: str = Field("", max_length=200)
    excellence_hub_email: str = Field("", max_length=200)


class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    intro: str = Field("", max_length=5000)
    order: int = Field(0, ge=0, le=999)


class TaxonomyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=1000)
    color: str = ""
    order: int = Field(0, ge=0, le=999)


def _validate_service(body: ServiceIn, data: dict) -> dict:
    if body.scope != ALLIANCE and body.scope not in UNIVERSITIES:
        raise HTTPException(status_code=422, detail="Unknown university")
    if body.scope == ALLIANCE:
        if not _find(data["rooms"], body.room_id):
            raise HTTPException(status_code=422, detail="Choose a cross-alliance room")
        if body.type_id and not _find(data["types"], body.type_id):
            raise HTTPException(status_code=422, detail="Unknown support type")
    elif not _find(data["types"], body.type_id):
        raise HTTPException(status_code=422, detail="Choose a support type")
    group_ids = {g["id"] for g in data["learner_groups"]}
    if any(g not in group_ids for g in body.learner_group_ids):
        raise HTTPException(status_code=422, detail="Unknown learner group")
    if body.target_group_id and not _find(data["target_groups"], body.target_group_id):
        raise HTTPException(status_code=422, detail="Unknown target group")

    fields = body.model_dump()
    fields["name"] = _check_text(body.name, "Name", short=True)
    if not fields["name"]:
        _invalid("Name is required")
    fields["description"] = _check_text(body.description, "Description")
    fields["contact_name"] = _check_text(body.contact_name, "Contact person / office", short=True)
    fields["languages"] = _check_languages(body.languages)
    fields["link"] = _check_link(body.link)
    fields["contact_email"] = _check_email(body.contact_email, "Contact email")
    fields["contact_phone"] = _check_phone(body.contact_phone)
    fields["learner_group_ids"] = list(dict.fromkeys(body.learner_group_ids))
    if body.scope == ALLIANCE:
        # Cross-alliance rooms are by definition open to every UNINOVIS learner.
        fields["access"] = "alliance"
    else:
        fields["room_id"] = ""
    return fields


# ---------------------------------------------------------------------------
# Routes — page and read access
# ---------------------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers={"Cache-Control": "no-store"})


@router.get("/api/me")
def me(session: dict = Depends(_require_viewer)):
    own_uni = _own_university(session)
    scopes = [ALLIANCE, *UNIVERSITIES]
    return {
        "username": session["username"],
        "roles": _user_roles(session),
        "own_university": own_uni,
        "is_superuser": _is_superuser(session),
        "is_content_manager": _is_content_manager(session),
        "editable_scopes": [s for s in scopes if _can_edit_scope(session, s, own_uni)],
    }


@router.get("/api/catalogue")
def catalogue(session: dict = Depends(_require_viewer)):
    """Everything the page needs in one call. Drafts are only included for the
    scopes the caller is allowed to edit."""
    data = load_data()
    own_uni = _own_university(session)
    editable = {s for s in [ALLIANCE, *UNIVERSITIES] if _can_edit_scope(session, s, own_uni)}
    universities = [
        {"code": code, "name": info["name"], "country": info["country"], **data["partners"].get(code, {})}
        for code, info in UNIVERSITIES.items()
    ]
    services = [
        s for s in data["services"]
        if s.get("status") == "published" or s.get("scope") in editable
    ]
    return {
        "types": sorted(data["types"], key=lambda x: x.get("order", 0)),
        "learner_groups": sorted(data["learner_groups"], key=lambda x: x.get("order", 0)),
        "target_groups": sorted(data["target_groups"], key=lambda x: x.get("order", 0)),
        "rooms": sorted(data["rooms"], key=lambda x: x.get("order", 0)),
        "universities": sorted(universities, key=lambda u: u["code"]),
        "services": sorted(services, key=lambda s: (s.get("scope", ""), s.get("order", 0), s.get("name", "").lower())),
    }


# ---------------------------------------------------------------------------
# Partner pages
# ---------------------------------------------------------------------------

@router.put("/api/partners/{code}")
def update_partner(code: str, body: PartnerIn, session: dict = Depends(_require_content_editor)):
    if code not in UNIVERSITIES:
        raise HTTPException(status_code=404, detail="Unknown university")
    _require_scope(session, code)
    fields = {
        "tagline": _check_text(body.tagline, "Tagline"),
        "intro": _check_text(body.intro, "Introduction"),
        "coordinator": _check_text(body.coordinator, "Institutional Coordinator", short=True),
        "excellence_hub": _check_text(body.excellence_hub, "Excellence Hub contact", short=True),
    }
    fields["coordinator_email"] = _check_email(body.coordinator_email, "Coordinator email")
    fields["excellence_hub_email"] = _check_email(body.excellence_hub_email, "Excellence Hub email")
    with _LOCK:
        data = load_data()
        data["partners"][code] = {**data["partners"].get(code, {}), **fields, **_stamp(session)}
        save_data(data)
    return data["partners"][code]


@router.post("/api/scopes/{scope}/publish-drafts")
def publish_drafts(scope: str, session: dict = Depends(_require_content_editor)):
    if scope != ALLIANCE and scope not in UNIVERSITIES:
        raise HTTPException(status_code=404, detail="Unknown university")
    _require_scope(session, scope)
    with _LOCK:
        data = load_data()
        count = 0
        for s in data["services"]:
            if s.get("scope") == scope and s.get("status") != "published":
                s.update(status="published", **_stamp(session))
                count += 1
        save_data(data)
    return {"published": count}


# ---------------------------------------------------------------------------
# Services ("fields")
# ---------------------------------------------------------------------------

@router.post("/api/services")
def create_service(body: ServiceIn, session: dict = Depends(_require_content_editor)):
    _require_scope(session, body.scope)
    with _LOCK:
        data = load_data()
        fields = _validate_service(body, data)
        same_scope = [s.get("order", 0) for s in data["services"] if s.get("scope") == body.scope]
        service = {"id": _new_id(), "order": max(same_scope, default=-1) + 1, **fields, **_stamp(session)}
        data["services"].append(service)
        save_data(data)
    return service


@router.put("/api/services/{service_id}")
def update_service(service_id: str, body: ServiceIn, session: dict = Depends(_require_content_editor)):
    with _LOCK:
        data = load_data()
        service = _find(data["services"], service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        # Both checks: a content_manager can't edit another university's service,
        # nor move one of their own services to another university.
        _require_scope(session, service["scope"])
        _require_scope(session, body.scope)
        service.update(**_validate_service(body, data), **_stamp(session))
        save_data(data)
    return service


@router.delete("/api/services/{service_id}")
def delete_service(service_id: str, session: dict = Depends(_require_content_editor)):
    with _LOCK:
        data = load_data()
        service = _find(data["services"], service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        _require_scope(session, service["scope"])
        data["services"].remove(service)
        save_data(data)
    return {"deleted": service_id}


# ---------------------------------------------------------------------------
# Cross-alliance rooms — any content_manager or superuser
# ---------------------------------------------------------------------------

def _room_fields(body: RoomIn) -> dict:
    name = _check_text(body.name, "Room name", short=True)
    if not name:
        _invalid("Room name is required")
    return {"name": name, "intro": _check_text(body.intro, "Introduction"), "order": body.order}


@router.post("/api/rooms")
def create_room(body: RoomIn, session: dict = Depends(_require_content_editor)):
    with _LOCK:
        data = load_data()
        room = {"id": _new_id(), **_room_fields(body), **_stamp(session)}
        data["rooms"].append(room)
        save_data(data)
    return room


@router.put("/api/rooms/{room_id}")
def update_room(room_id: str, body: RoomIn, session: dict = Depends(_require_content_editor)):
    with _LOCK:
        data = load_data()
        room = _find(data["rooms"], room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        room.update(**_room_fields(body), **_stamp(session))
        save_data(data)
    return room


@router.delete("/api/rooms/{room_id}")
def delete_room(room_id: str, session: dict = Depends(_require_content_editor)):
    with _LOCK:
        data = load_data()
        room = _find(data["rooms"], room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        in_use = sum(1 for s in data["services"] if s.get("room_id") == room_id)
        if in_use:
            raise HTTPException(status_code=409, detail=f"This room still has {in_use} service(s). Move or delete them first.")
        data["rooms"].remove(room)
        save_data(data)
    return {"deleted": room_id}


# ---------------------------------------------------------------------------
# Shared taxonomies (support types, learner groups, target groups) — superuser
# ---------------------------------------------------------------------------

_TAXONOMY_FIELD = {"types": "type_id", "learner_groups": "learner_group_ids", "target_groups": "target_group_id"}


def _check_taxonomy(kind: str) -> None:
    if kind not in TAXONOMIES:
        raise HTTPException(status_code=404, detail="Unknown list")


def _taxonomy_fields(kind: str, body: TaxonomyIn) -> dict:
    name = _check_text(body.name, "Name", short=True)
    if not name:
        _invalid("Name is required")
    fields = {"name": name, "description": _check_text(body.description, "Description"), "order": body.order}
    if kind == "learner_groups":
        if body.color and not _COLOR_RE.match(body.color):
            raise HTTPException(status_code=422, detail="Colour must look like #1e88e5")
        fields["color"] = body.color or "#5c6b7a"
    return fields


@router.post("/api/taxonomy/{kind}")
def create_taxonomy_item(kind: str, body: TaxonomyIn, session: dict = Depends(_require_superuser)):
    _check_taxonomy(kind)
    with _LOCK:
        data = load_data()
        item = {"id": _new_id(), **_taxonomy_fields(kind, body)}
        data[kind].append(item)
        save_data(data)
    return item


@router.put("/api/taxonomy/{kind}/{item_id}")
def update_taxonomy_item(kind: str, item_id: str, body: TaxonomyIn, session: dict = Depends(_require_superuser)):
    _check_taxonomy(kind)
    with _LOCK:
        data = load_data()
        item = _find(data[kind], item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        item.update(_taxonomy_fields(kind, body))
        save_data(data)
    return item


@router.delete("/api/taxonomy/{kind}/{item_id}")
def delete_taxonomy_item(kind: str, item_id: str, session: dict = Depends(_require_superuser)):
    _check_taxonomy(kind)
    with _LOCK:
        data = load_data()
        item = _find(data[kind], item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        field = _TAXONOMY_FIELD[kind]

        def uses(s: dict) -> bool:
            if field == "learner_group_ids":
                return item_id in s.get(field, [])
            return s.get(field) == item_id

        in_use = sum(1 for s in data["services"] if uses(s))
        if in_use and kind == "types":
            raise HTTPException(status_code=409, detail=f"{in_use} service(s) still use this type. Change their type first.")
        # Learner/target groups are optional tags: deleting one just untags its services.
        for s in data["services"]:
            if field == "learner_group_ids":
                s["learner_group_ids"] = [g for g in s.get("learner_group_ids", []) if g != item_id]
            elif s.get(field) == item_id:
                s[field] = ""
        data[kind].remove(item)
        save_data(data)
    return {"deleted": item_id, "untagged_services": in_use}
