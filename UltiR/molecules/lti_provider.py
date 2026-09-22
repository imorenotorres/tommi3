"""
Molecule Viewer — LTI 1.1 Tool

Interactive 3D molecular visualization for biology and chemistry courses.
Teachers curate a molecule list per course (by PDB ID); students explore
them in a 3Dmol.js viewer. No LLM needed — all rendering is client-side.

Configuration (web/.env):
    MOLECULES_LTI_KEY=molecules_uma
    MOLECULES_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/molecules
"""

import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_molecules"])

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"
_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

LTI_KEY = os.environ.get("MOLECULES_LTI_KEY", "molecules_uma")
LTI_SECRET = os.environ.get("MOLECULES_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()


# ── Data helpers ──────────────────────────────────────────────────────────────

def _course_path(course_id: str) -> Path:
    safe = "".join(c for c in course_id if c.isalnum() or c in "-_")[:64] or "default"
    return _DATA_DIR / f"{safe}.json"


def _load_molecules(course_id: str) -> list:
    path = _course_path(course_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_molecules(course_id: str, molecules: list):
    molecules.sort(key=lambda m: m.get("label", "").lower())
    _course_path(course_id).write_text(
        json.dumps(molecules, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── LTI Launch ────────────────────────────────────────────────────────────────

@router.get("/lti/molecules")
async def molecules_get():
    return RedirectResponse("/lti/molecules/info", status_code=303)


@router.post("/lti/molecules")
async def molecules_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/molecules/viewer",
        redirect_learner="/lti/molecules/viewer",
    )


@router.get("/lti/molecules/test")
async def molecules_test(role: str = "instructor"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/molecules/viewer",
        redirect_learner="/lti/molecules/viewer",
        role=role,
    )


# ── Pages ─────────────────────────────────────────────────────────────────────

@router.get("/lti/molecules/info")
async def molecules_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/molecules/viewer")
async def molecules_viewer(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "viewer.html").read_text(encoding="utf-8"))


# ── API ───────────────────────────────────────────────────────────────────────

@router.get("/lti/molecules/api/session")
async def molecules_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_id": session.get("course_id", "default"),
        "course_name": session.get("course_name", ""),
        "is_instructor": is_instructor(session),
    }


@router.get("/lti/molecules/api/molecules")
async def molecules_list(request: Request):
    session = sessions.require(request)
    return {"molecules": _load_molecules(session.get("course_id", "default"))}


@router.post("/lti/molecules/api/molecules")
async def molecules_add(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes pueden añadir moléculas")
    body = await request.json()
    pdb_id = body.get("pdb_id", "").strip().upper()
    if not pdb_id or not pdb_id.replace("-", "").isalnum():
        raise HTTPException(400, "PDB ID inválido")
    course_id = session.get("course_id", "default")
    molecules = _load_molecules(course_id)
    if any(m["pdb_id"] == pdb_id for m in molecules):
        raise HTTPException(409, f"{pdb_id} ya está en la lista")
    molecules.append({
        "id": str(uuid.uuid4())[:8],
        "pdb_id": pdb_id,
        "label": body.get("label", "") or pdb_id,
        "description": body.get("description", ""),
        "default_style": body.get("default_style", "cartoon"),
    })
    _save_molecules(course_id, molecules)
    return {"ok": True, "molecules": molecules}


@router.delete("/lti/molecules/api/molecules/{mol_id}")
async def molecules_delete(mol_id: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes pueden eliminar moléculas")
    course_id = session.get("course_id", "default")
    molecules = [m for m in _load_molecules(course_id) if m["id"] != mol_id]
    _save_molecules(course_id, molecules)
    return {"ok": True, "molecules": molecules}


@router.patch("/lti/molecules/api/molecules/{mol_id}")
async def molecules_update(mol_id: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes pueden editar moléculas")
    body = await request.json()
    course_id = session.get("course_id", "default")
    molecules = _load_molecules(course_id)
    for m in molecules:
        if m["id"] == mol_id:
            for field in ("label", "description", "default_style", "highlights"):
                if field in body:
                    m[field] = body[field]
            break
    else:
        raise HTTPException(404, "Molécula no encontrada")
    _save_molecules(course_id, molecules)
    return {"ok": True, "molecules": molecules}
