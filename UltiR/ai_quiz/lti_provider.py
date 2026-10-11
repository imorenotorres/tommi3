"""
AI Quiz Generator — LTI 1.1 Tool

An instructor uploads course material, the LLM drafts multiple-choice
questions, the instructor reviews and publishes them, students practise from
Moodle and the server grades. Nothing the model writes reaches students
before an instructor approves it.

Configuration (web/.env):
    AI_QUIZ_LTI_SECRET=<shared_secret>    required, no default
    AI_QUIZ_ID_KEY=<random_secret>        required, no default; keys the hash
                                          of the user id stored with attempts
    AI_QUIZ_LTI_KEY=ai_quiz_uma           optional, this is the default
    AI_QUIZ_DEV_TEST=1                    optional, local machines only: opens
                                          /lti/ai-quiz/test

Until both required settings have a value the tool answers 503 everywhere
except its info page. It never falls back to a placeholder secret.

Moodle setup:
    Tool URL: https://<host>/lti/ai-quiz
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from UltiR.ai_quiz import config
from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_ai_quiz"])

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"
BASE = "/lti/ai-quiz"

sessions = LTISessionStore()

# Only these files are served as assets. They hold no course data, so the
# route is public; the name from the URL is a key here and never a path.
_ASSETS = {
    "strings.js": "text/javascript",
    "app.js": "text/javascript",
    "app.css": "text/css",
}


# ── Guards ────────────────────────────────────────────────────────────────────
# The platform's login middleware does not cover /lti/ paths: these two
# functions are the only access control this tool has.

def require_session(request: Request) -> dict:
    config.require_configured()
    return sessions.require(request)


def require_instructor(request: Request) -> dict:
    session = require_session(request)
    if not is_instructor(session):
        raise HTTPException(403, "Instructors only")
    return session


def _page(name: str) -> HTMLResponse:
    return HTMLResponse((_STATIC_DIR / name).read_text(encoding="utf-8"))


# ── LTI launch ────────────────────────────────────────────────────────────────

@router.get(BASE)
async def ai_quiz_get():
    return RedirectResponse(f"{BASE}/info", status_code=303)


@router.post(BASE)
async def ai_quiz_launch(request: Request):
    config.require_configured()
    return await lti_launch(
        request, config.lti_key(), config.lti_secret(), sessions,
        redirect_instructor=f"{BASE}/instructor",
        redirect_learner=f"{BASE}/student",
    )


@router.get(f"{BASE}/test")
async def ai_quiz_test(role: str = "learner"):
    """Local test launch without Moodle. Does not exist unless AI_QUIZ_DEV_TEST=1."""
    if not config.dev_test_enabled():
        raise HTTPException(404)
    config.require_configured()
    return await lti_test_launch(
        sessions,
        redirect_instructor=f"{BASE}/instructor",
        redirect_learner=f"{BASE}/student",
        role="instructor" if role.lower() == "instructor" else "learner",
    )


# ── Pages and assets ──────────────────────────────────────────────────────────

@router.get(f"{BASE}/info")
async def ai_quiz_info():
    return _page("info.html")


@router.get(f"{BASE}/instructor")
async def ai_quiz_instructor(request: Request):
    require_instructor(request)
    return _page("instructor.html")


@router.get(f"{BASE}/student")
async def ai_quiz_student(request: Request):
    require_session(request)
    return _page("student.html")


@router.get(f"{BASE}/assets/{{name:path}}")
async def ai_quiz_asset(name: str):
    media_type = _ASSETS.get(name)
    if not media_type:
        raise HTTPException(404, "Not found")
    return FileResponse(_STATIC_DIR / name, media_type=media_type,
                        headers={"Cache-Control": "no-cache"})


# ── API ───────────────────────────────────────────────────────────────────────

@router.get(f"{BASE}/api/session")
async def ai_quiz_session(request: Request):
    session = require_session(request)
    # Display fields only: no email, no user id, no course id.
    return {
        "name": session["name"],
        "course_name": session["course_name"],
        "is_instructor": is_instructor(session),
    }
