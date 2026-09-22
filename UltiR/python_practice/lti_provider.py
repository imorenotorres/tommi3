"""
Python Practice — LTI 1.1 Tool

Interactive Python coding exercises. Teachers create exercises with automatic
test cases; students write code that runs client-side via Pyodide (WebAssembly)
— no server-side code execution, no sandbox needed.

Configuration (web/.env):
    PYTHON_PRACTICE_LTI_KEY=python_uma
    PYTHON_PRACTICE_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/python
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

router = APIRouter(tags=["lti_python"])

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"
_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

LTI_KEY = os.environ.get("PYTHON_PRACTICE_LTI_KEY", "python_uma")
LTI_SECRET = os.environ.get("PYTHON_PRACTICE_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()

DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"]


# ── Data helpers ──────────────────────────────────────────────────────────────

def _course_path(course_id: str) -> Path:
    safe = "".join(c for c in course_id if c.isalnum() or c in "-_")[:64] or "default"
    return _DATA_DIR / f"{safe}.json"


def _progress_path(course_id: str, user_id: str) -> Path:
    safe_c = "".join(c for c in course_id if c.isalnum() or c in "-_")[:64] or "default"
    safe_u = "".join(c for c in user_id if c.isalnum() or c in "-_")[:64] or "anonymous"
    d = _DATA_DIR / "progress" / safe_c
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe_u}.json"


def _load_exercises(course_id: str) -> list:
    path = _course_path(course_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_exercises(course_id: str, exercises: list):
    exercises.sort(key=lambda e: (
        DIFFICULTY_ORDER.index(e.get("difficulty", "beginner"))
        if e.get("difficulty") in DIFFICULTY_ORDER else 99,
        e.get("title", "").lower(),
    ))
    _course_path(course_id).write_text(
        json.dumps(exercises, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _load_progress(course_id: str, user_id: str) -> dict:
    path = _progress_path(course_id, user_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_progress(course_id: str, user_id: str, progress: dict):
    _progress_path(course_id, user_id).write_text(
        json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── LTI Launch ────────────────────────────────────────────────────────────────

@router.get("/lti/python")
async def python_get():
    return RedirectResponse("/lti/python/info", status_code=303)


@router.post("/lti/python")
async def python_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/python/viewer",
        redirect_learner="/lti/python/viewer",
    )


@router.get("/lti/python/test")
async def python_test(role: str = "instructor"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/python/viewer",
        redirect_learner="/lti/python/viewer",
        role=role,
    )


# ── Pages ─────────────────────────────────────────────────────────────────────

@router.get("/lti/python/info")
async def python_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/python/viewer")
async def python_viewer(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "viewer.html").read_text(encoding="utf-8"))


# ── API ───────────────────────────────────────────────────────────────────────

@router.get("/lti/python/api/session")
async def python_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_id": session.get("course_id", "default"),
        "course_name": session.get("course_name", ""),
        "is_instructor": is_instructor(session),
        "user_id": session.get("user_id", ""),
    }


@router.get("/lti/python/api/exercises")
async def python_list(request: Request):
    session = sessions.require(request)
    course_id = session.get("course_id", "default")
    user_id = session.get("user_id", "")
    return {
        "exercises": _load_exercises(course_id),
        "progress": _load_progress(course_id, user_id),
    }


@router.post("/lti/python/api/exercises")
async def python_add(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes pueden añadir ejercicios")
    body = await request.json()
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(400, "El título es obligatorio")
    course_id = session.get("course_id", "default")
    exercises = _load_exercises(course_id)
    exercises.append({
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "difficulty": body.get("difficulty", "beginner"),
        "description": body.get("description", ""),
        "starter_code": body.get("starter_code", ""),
        "solution": body.get("solution", ""),
        "tests": body.get("tests", []),
        "hints": body.get("hints", []),
    })
    _save_exercises(course_id, exercises)
    return {"ok": True, "exercises": exercises}


@router.delete("/lti/python/api/exercises/{ex_id}")
async def python_delete(ex_id: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes pueden eliminar ejercicios")
    course_id = session.get("course_id", "default")
    exercises = [e for e in _load_exercises(course_id) if e["id"] != ex_id]
    _save_exercises(course_id, exercises)
    return {"ok": True, "exercises": exercises}


@router.patch("/lti/python/api/exercises/{ex_id}")
async def python_update(ex_id: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes pueden editar ejercicios")
    body = await request.json()
    course_id = session.get("course_id", "default")
    exercises = _load_exercises(course_id)
    for e in exercises:
        if e["id"] == ex_id:
            for field in ("title", "difficulty", "description", "starter_code", "solution", "tests", "hints"):
                if field in body:
                    e[field] = body[field]
            break
    else:
        raise HTTPException(404, "Ejercicio no encontrado")
    _save_exercises(course_id, exercises)
    return {"ok": True, "exercises": exercises}


@router.post("/lti/python/api/progress/{ex_id}")
async def python_progress(ex_id: str, request: Request):
    session = sessions.require(request)
    body = await request.json()
    course_id = session.get("course_id", "default")
    user_id = session.get("user_id", "anonymous")
    progress = _load_progress(course_id, user_id)
    progress[ex_id] = {
        "passed": body.get("passed", 0),
        "total": body.get("total", 0),
        "completed": body.get("completed", False),
        "at": body.get("at", ""),
    }
    _save_progress(course_id, user_id, progress)
    return {"ok": True}
