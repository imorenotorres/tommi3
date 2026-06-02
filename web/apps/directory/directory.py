"""
UNINOVIS Directory — Internal staff directory for UNINOVIS partner universities.

Manages users, groups, and subgroups with role-based editing.
Designed to be mounted on the TOMMI FastAPI server.
"""

import base64
import json
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/directory", tags=["directory"])


# ── Auth helpers ─────────────────────────────────────────────────────

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
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def _require_editor(session: dict = Depends(_require_auth)) -> dict:
    if not _can_edit_check(session):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


# ── Data I/O ─────────────────────────────────────────────────────────

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Routes ───────────────────────────────────────────────────────────

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/data")
def get_all_data():
    """Return all directory data (public read)."""
    return load_data()


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    can_edit = _can_edit_check(session)
    return {"username": session["username"], "role": session["role"], "roles": session.get("roles", [session["role"]]), "can_edit": can_edit}


# ── User CRUD ────────────────────────────────────────────────────────

class UserBody(BaseModel):
    university: str
    first_name: str
    family_name: str
    role: str = ""
    email: str
    telephone: str = ""
    notes: str = ""
    groups: list[str] = []
    subgroups: list[str] = []
    custom: dict = {}  # custom field values keyed by field id


@router.post("/api/users")
def create_user(body: UserBody, session: dict = Depends(_require_editor)):
    data = load_data()
    if body.university not in data["universities"]:
        raise HTTPException(400, f"Unknown university: {body.university}")
    user = {
        "id": str(uuid.uuid4())[:8],
        "university": body.university,
        "first_name": body.first_name,
        "family_name": body.family_name,
        "role": body.role,
        "email": body.email,
        "telephone": body.telephone,
        "notes": body.notes,
        "groups": body.groups,
        "subgroups": body.subgroups,
        "custom": body.custom,
    }
    data["users"].append(user)
    save_data(data)
    return user


@router.put("/api/my-profile")
def update_my_profile(body: UserBody, session: dict = Depends(_require_auth)):
    """Any authenticated user can edit their own directory profile (matched by email)."""
    data = load_data()
    username = session["username"].lower()
    for u in data["users"]:
        emails = [e.strip().lower() for e in (u.get("email") or "").split(";")]
        if username in emails:
            u["first_name"] = body.first_name
            u["family_name"] = body.family_name
            u["telephone"] = body.telephone
            u["notes"] = body.notes
            u["custom"] = body.custom
            save_data(data)
            return u
    raise HTTPException(404, "Your profile was not found in the directory")


@router.put("/api/users/{user_id}")
def update_user(user_id: str, body: UserBody, session: dict = Depends(_require_editor)):
    data = load_data()
    for u in data["users"]:
        if u["id"] == user_id:
            u["university"] = body.university
            u["first_name"] = body.first_name
            u["family_name"] = body.family_name
            u["role"] = body.role
            u["email"] = body.email
            u["telephone"] = body.telephone
            u["notes"] = body.notes
            u["groups"] = body.groups
            u["subgroups"] = body.subgroups
            u["custom"] = body.custom
            save_data(data)
            return u
    raise HTTPException(404, "User not found")


@router.delete("/api/users/{user_id}")
def delete_user(user_id: str, session: dict = Depends(_require_editor)):
    data = load_data()
    data["users"] = [u for u in data["users"] if u["id"] != user_id]
    # Also remove from group leaders
    for g in data["groups"]:
        if g["leader"] == user_id:
            g["leader"] = ""
    save_data(data)
    return {"ok": True}


# ── Group CRUD ───────────────────────────────────────────────────────

class SubgroupBody(BaseModel):
    id: str
    name: str


class GroupBody(BaseModel):
    id: str
    name: str
    leader: str = ""
    verified: bool = False
    subgroups: list[SubgroupBody] = []


@router.post("/api/groups")
def create_group(body: GroupBody, session: dict = Depends(_require_editor)):
    data = load_data()
    for g in data["groups"]:
        if g["id"] == body.id:
            raise HTTPException(400, f"Group '{body.id}' already exists")
    group = {
        "id": body.id,
        "name": body.name,
        "leader": body.leader,
        "verified": body.verified,
        "subgroups": [sg.model_dump() for sg in body.subgroups],
    }
    data["groups"].append(group)
    save_data(data)
    return group


@router.put("/api/groups/{group_id}")
def update_group(group_id: str, body: GroupBody, session: dict = Depends(_require_editor)):
    data = load_data()
    for g in data["groups"]:
        if g["id"] == group_id:
            old_subgroup_ids = {sg["id"] for sg in g.get("subgroups", [])}
            new_subgroup_ids = {sg.id for sg in body.subgroups}
            removed_subgroups = old_subgroup_ids - new_subgroup_ids

            g["name"] = body.name
            g["leader"] = body.leader
            g["verified"] = body.verified
            g["subgroups"] = [sg.model_dump() for sg in body.subgroups]

            # Clean removed subgroups from users
            if removed_subgroups:
                for u in data["users"]:
                    u["subgroups"] = [s for s in u.get("subgroups", []) if s not in removed_subgroups]

            save_data(data)
            return g
    raise HTTPException(404, "Group not found")


@router.delete("/api/groups/{group_id}")
def delete_group(group_id: str, session: dict = Depends(_require_editor)):
    data = load_data()
    group = next((g for g in data["groups"] if g["id"] == group_id), None)
    if not group:
        raise HTTPException(404, "Group not found")
    subgroup_ids = {sg["id"] for sg in group.get("subgroups", [])}
    data["groups"] = [g for g in data["groups"] if g["id"] != group_id]
    # Clean group/subgroup refs from users
    for u in data["users"]:
        u["groups"] = [gid for gid in u.get("groups", []) if gid != group_id]
        u["subgroups"] = [sid for sid in u.get("subgroups", []) if sid not in subgroup_ids]
    save_data(data)
    return {"ok": True}


# ── Batch add/remove members to group/subgroup ──────────────────────

class MembershipBody(BaseModel):
    user_ids: list[str]


@router.post("/api/groups/{group_id}/members")
def add_group_members(group_id: str, body: MembershipBody, session: dict = Depends(_require_editor)):
    data = load_data()
    if not any(g["id"] == group_id for g in data["groups"]):
        raise HTTPException(404, "Group not found")
    for u in data["users"]:
        if u["id"] in body.user_ids and group_id not in u.get("groups", []):
            u.setdefault("groups", []).append(group_id)
    save_data(data)
    return {"ok": True}


@router.delete("/api/groups/{group_id}/members")
def remove_group_members(group_id: str, body: MembershipBody, session: dict = Depends(_require_editor)):
    data = load_data()
    for u in data["users"]:
        if u["id"] in body.user_ids:
            u["groups"] = [gid for gid in u.get("groups", []) if gid != group_id]
    save_data(data)
    return {"ok": True}


@router.post("/api/groups/{group_id}/subgroups/{subgroup_id}/members")
def add_subgroup_members(group_id: str, subgroup_id: str, body: MembershipBody, session: dict = Depends(_require_editor)):
    data = load_data()
    group = next((g for g in data["groups"] if g["id"] == group_id), None)
    if not group:
        raise HTTPException(404, "Group not found")
    if not any(sg["id"] == subgroup_id for sg in group.get("subgroups", [])):
        raise HTTPException(404, "Subgroup not found")
    for u in data["users"]:
        if u["id"] in body.user_ids:
            if group_id not in u.get("groups", []):
                u.setdefault("groups", []).append(group_id)
            if subgroup_id not in u.get("subgroups", []):
                u.setdefault("subgroups", []).append(subgroup_id)
    save_data(data)
    return {"ok": True}


@router.delete("/api/groups/{group_id}/subgroups/{subgroup_id}/members")
def remove_subgroup_members(group_id: str, subgroup_id: str, body: MembershipBody, session: dict = Depends(_require_editor)):
    data = load_data()
    for u in data["users"]:
        if u["id"] in body.user_ids:
            u["subgroups"] = [sid for sid in u.get("subgroups", []) if sid != subgroup_id]
    save_data(data)
    return {"ok": True}


# ── Settings ─────────────────────────────────────────────────────────

class CustomFieldDef(BaseModel):
    id: str
    label: str
    type: str  # "text", "dropdown", "checkbox", "image"
    options: list[str] = []  # for dropdown type


class SettingsBody(BaseModel):
    roles: list[str] = []
    custom_fields: list[CustomFieldDef] = []


@router.get("/api/settings")
def get_settings():
    data = load_data()
    return data.get("settings", {"roles": [], "custom_fields": []})


@router.put("/api/settings")
def update_settings(body: SettingsBody, session: dict = Depends(_require_editor)):
    data = load_data()
    data["settings"] = {
        "roles": body.roles,
        "custom_fields": [cf.model_dump() for cf in body.custom_fields],
    }
    save_data(data)
    return {"ok": True}


# ── Image upload for custom image fields ─────────────────────────────

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(IMAGES_DIR, exist_ok=True)


@router.post("/api/users/{user_id}/image/{field_id}")
async def upload_user_image(
    user_id: str,
    field_id: str,
    file: UploadFile = File(...),
    session: dict = Depends(_require_editor),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")
    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:  # 2MB limit
        raise HTTPException(400, "Image must be under 2MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{user_id}_{field_id}.{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    # Store reference in user data
    data = load_data()
    for u in data["users"]:
        if u["id"] == user_id:
            u.setdefault("custom", {})[field_id] = filename
            save_data(data)
            return {"ok": True, "filename": filename}
    raise HTTPException(404, "User not found")


@router.get("/api/images/{filename}")
def get_image(filename: str):
    filepath = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "Image not found")
    ext = filename.rsplit(".", 1)[-1].lower()
    ct = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
    with open(filepath, "rb") as f:
        return Response(content=f.read(), media_type=ct)
