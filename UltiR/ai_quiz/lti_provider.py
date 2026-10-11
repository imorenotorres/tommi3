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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from UltiR.ai_quiz import config, documents, ingestion, limits
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


def _refuse(status: int, code: str, **extra):
    """Errors carry a code, not a sentence: the page shows the text in the user's language."""
    raise HTTPException(status, {"code": code, **extra})


# Handlers take the raw request and call a guard before they read the body, so
# an unauthenticated request is refused before any of it is parsed.


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
        "reading_modes": {"text": True, "full": ingestion.full_reading_available()},
    }


# ── Documents (instructor only) ───────────────────────────────────────────────

# Room for the multipart envelope around the file itself.
_FORM_OVERHEAD = 64 * 1024


@router.post(f"{BASE}/api/documents")
async def ai_quiz_upload_document(request: Request):
    session = require_instructor(request)
    try:
        declared = int(request.headers.get("content-length", ""))
    except ValueError:
        _refuse(411, "length_required")
    if declared > limits.MAX_UPLOAD_BYTES + _FORM_OVERHEAD:
        _refuse(413, "file_too_large")

    form = await request.form(max_files=1, max_fields=4)
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        _refuse(400, "no_file")
    mode = form.get("reading_mode") or "text"
    if not isinstance(mode, str):
        _refuse(400, "bad_mode")
    data = await upload.read(limits.MAX_UPLOAD_BYTES + 1)

    try:
        # Reading a PDF is slow, blocking work: keep it off the event loop.
        document = await run_in_threadpool(
            documents.add_document, session["course_id"], upload.filename or "", data, mode)
    except documents.UploadRejected as rejected:
        _refuse(rejected.status, rejected.code, **rejected.extra)
    return JSONResponse(document, status_code=201)


@router.get(f"{BASE}/api/documents")
async def ai_quiz_list_documents(request: Request):
    session = require_instructor(request)
    return {"documents": documents.list_documents(session["course_id"])}


@router.get(f"{BASE}/api/documents/{{doc_id}}")
async def ai_quiz_get_document(doc_id: str, request: Request):
    session = require_instructor(request)
    document = documents.get_document(session["course_id"], doc_id)
    if document is None:
        _refuse(404, "not_found")
    return document


@router.delete(f"{BASE}/api/documents/{{doc_id}}")
async def ai_quiz_delete_document(doc_id: str, request: Request):
    session = require_instructor(request)
    if not documents.delete_document(session["course_id"], doc_id):
        _refuse(404, "not_found")
    return {"ok": True}
