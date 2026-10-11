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

Full reading (formulas, figures) is optional and needs Docling in a Python
environment of its own; see docling_reader.py. Without it the tool offers
text-only reading and everything else works.
    AI_QUIZ_DOCLING_PYTHON=/path/to/env/bin/python   full path of that interpreter
    AI_QUIZ_DOCLING_MODELS=/path/to/models           default ~/.cache/docling/models
    AI_QUIZ_DOCLING_DEVICE=auto                      auto, cpu or cuda

Moodle setup:
    Tool URL: https://<host>/lti/ai-quiz
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from UltiR.ai_quiz import attempts, config, documents, generation, ingestion, limits, review, storage
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
    "info.js": "text/javascript",
    "instructor.js": "text/javascript",
    "student.js": "text/javascript",
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

_MAX_JSON_BYTES = 256 * 1024


async def _json_object(request: Request) -> dict:
    """The request body as a JSON object, or 400. Call only after a guard."""
    raw = await request.body()
    if len(raw) > _MAX_JSON_BYTES:
        _refuse(413, "request_too_large")
    try:
        body = json.loads(raw)
    except ValueError:
        _refuse(400, "bad_request", field="body")
    if not isinstance(body, dict):
        _refuse(400, "bad_request", field="body")
    return body


def _text_field(body: dict, name: str, max_chars: int) -> str:
    """An optional short text field from untrusted input: trimmed, bounded, or 400."""
    value = body.get(name, "")
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > max_chars:
        _refuse(400, "bad_request", field=name)
    return " ".join(value.split())


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


class _BodyTooLarge(Exception):
    pass


def _capped(request: Request, limit: int) -> Request:
    """The same request, except that reading its body stops once more than `limit` bytes have arrived.

    The count is of the bytes actually received. What the request declares
    as its length plays no part: it can be missing or wrong.
    """
    received = 0

    async def receive():
        nonlocal received
        message = await request.receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > limit:
                raise _BodyTooLarge()
        return message

    return Request(request.scope, receive)


@router.post(f"{BASE}/api/documents")
async def ai_quiz_upload_document(request: Request):
    session = require_instructor(request)
    limit = limits.MAX_UPLOAD_BYTES + _FORM_OVERHEAD
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        _refuse(413, "file_too_large")      # an honest oversized request is refused before any of it is read

    try:
        form = await _capped(request, limit).form(max_files=1, max_fields=4)
    except _BodyTooLarge:
        _refuse(413, "file_too_large")
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
    # 202: stored, and still being read in the background. The page asks again with GET.
    return JSONResponse(document, status_code=202 if document["status"] == "processing" else 201)


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


# ── Generation (instructor only) ──────────────────────────────────────────────

@router.post(f"{BASE}/api/generate")
async def ai_quiz_generate(request: Request):
    """Draft questions from course documents. The result is always an unpublished draft."""
    session = require_instructor(request)
    course_id = session["course_id"]
    body = await _json_object(request)

    count = body.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= limits.MAX_QUESTIONS_PER_REQUEST:
        _refuse(400, "bad_request", field="count")
    difficulty = body.get("difficulty", "mixed")
    if difficulty not in ("mixed", *generation.DIFFICULTIES):
        _refuse(400, "bad_request", field="difficulty")
    topic = _text_field(body, "topic", limits.MAX_TOPIC_CHARS)
    title = _text_field(body, "title", limits.MAX_TITLE_CHARS)
    doc_ids = body.get("doc_ids")
    if (not isinstance(doc_ids, list) or not 1 <= len(doc_ids) <= limits.MAX_DOCS_PER_REQUEST
            or not all(storage.is_id(d, "d") for d in doc_ids)):
        _refuse(400, "bad_request", field="doc_ids")
    quiz_id = body.get("quiz_id")
    if quiz_id is not None and not storage.is_id(quiz_id, "z"):
        _refuse(400, "bad_request", field="quiz_id")

    # Everything is looked up inside the course of the session.
    chosen = []
    for doc_id in dict.fromkeys(doc_ids):
        document = documents.get_document(course_id, doc_id)
        if document is None:
            _refuse(404, "document_not_found")
        if document["status"] != "ready":
            _refuse(409, "document_not_ready")
        chosen.append(document)
    quiz = None
    if quiz_id is not None:
        quiz = review.load_quiz(course_id, quiz_id)
        if quiz is None:
            _refuse(404, "quiz_not_found")
        if len(quiz["questions"]) + count > limits.MAX_QUESTIONS_PER_QUIZ:
            _refuse(409, "quiz_full")
    elif len(review.quiz_ids(course_id)) >= limits.MAX_QUIZZES_PER_COURSE:
        _refuse(409, "too_many_quizzes")

    wait = generation.take_generation_slot(course_id)
    if wait:
        _refuse(429, "rate_limited", retry_after_seconds=wait)

    chunks = [
        {"doc_id": d["doc_id"], "doc_label": d["label"], **chunk}
        for d in chosen for chunk in documents.load_chunks(course_id, d["doc_id"])
    ]
    existing = [q["question"] for q in quiz["questions"]] if quiz else []
    try:
        result = await generation.generate(chunks, count, difficulty, topic, existing)
        if quiz is None:
            quiz = review.create_quiz(course_id, title or chosen[0]["label"], result["questions"])
        else:
            quiz = review.add_questions(course_id, quiz_id, result["questions"])
    except (generation.GenerationFailed, review.QuizError) as failed:
        _refuse(failed.status, failed.code)
    return JSONResponse({"quiz": review.instructor_view(quiz), "stats": result["stats"]}, status_code=201)


# ── Review and publishing (instructor only) ───────────────────────────────────

def _reviewed(action, *args) -> dict:
    """Run a review action and answer with the instructor's view of the quiz."""
    try:
        return review.instructor_view(action(*args))
    except review.QuizError as error:
        _refuse(error.status, error.code)


@router.get(f"{BASE}/api/quizzes")
async def ai_quiz_list_quizzes(request: Request):
    session = require_instructor(request)
    return {"quizzes": review.list_quizzes(session["course_id"])}


@router.get(f"{BASE}/api/quizzes/{{quiz_id}}")
async def ai_quiz_get_quiz(quiz_id: str, request: Request):
    session = require_instructor(request)
    quiz = review.load_quiz(session["course_id"], quiz_id)
    if quiz is None:
        _refuse(404, "quiz_not_found")
    return review.instructor_view(quiz)


@router.put(f"{BASE}/api/quizzes/{{quiz_id}}")
async def ai_quiz_rename_quiz(quiz_id: str, request: Request):
    session = require_instructor(request)
    body = await _json_object(request)
    title = _text_field(body, "title", limits.MAX_TITLE_CHARS) if isinstance(body.get("title"), str) else ""
    if not title:
        _refuse(400, "bad_request", field="title")
    return _reviewed(review.rename_quiz, session["course_id"], quiz_id, title)


@router.put(f"{BASE}/api/quizzes/{{quiz_id}}/questions/{{question_id}}")
async def ai_quiz_update_question(quiz_id: str, question_id: str, request: Request):
    session = require_instructor(request)
    body = await _json_object(request)
    return _reviewed(review.update_question, session["course_id"], quiz_id, question_id, body)


@router.post(f"{BASE}/api/quizzes/{{quiz_id}}/publish")
async def ai_quiz_publish(quiz_id: str, request: Request):
    session = require_instructor(request)
    return _reviewed(review.publish, session["course_id"], quiz_id)


@router.post(f"{BASE}/api/quizzes/{{quiz_id}}/unpublish")
async def ai_quiz_unpublish(quiz_id: str, request: Request):
    session = require_instructor(request)
    return _reviewed(review.unpublish, session["course_id"], quiz_id)


@router.get(f"{BASE}/api/quizzes/{{quiz_id}}/summary")
async def ai_quiz_summary(quiz_id: str, request: Request):
    """Aggregate results of one quiz. No names, no single attempts."""
    session = require_instructor(request)
    summary = attempts.summary(session["course_id"], quiz_id)
    if summary is None:
        _refuse(404, "quiz_not_found")
    return summary


# ── Practising (any session of the course) ────────────────────────────────────
# Identity and course come from the session. The responses of the first two
# routes are built from an allow-list and carry no key, explanation or source.

@router.get(f"{BASE}/api/published")
async def ai_quiz_published(request: Request):
    session = require_session(request)
    return {"quizzes": attempts.published_quizzes(session["course_id"], session.get("user_id", ""))}


@router.get(f"{BASE}/api/published/{{quiz_id}}")
async def ai_quiz_published_quiz(quiz_id: str, request: Request):
    session = require_session(request)
    quiz = attempts.learner_quiz(session["course_id"], quiz_id)
    if quiz is None:
        _refuse(404, "quiz_not_found")
    return quiz


@router.post(f"{BASE}/api/quizzes/{{quiz_id}}/attempts")
async def ai_quiz_submit_attempt(quiz_id: str, request: Request):
    """Grade an attempt on the server. Any score the browser sends is not read."""
    session = require_session(request)
    body = await _json_object(request)
    try:
        result = attempts.submit(session["course_id"], quiz_id, session.get("user_id", ""),
                                 is_instructor(session), body)
    except attempts.AttemptError as error:
        _refuse(error.status, error.code)
    return JSONResponse(result, status_code=201)


@router.get(f"{BASE}/api/attempts/{{attempt_id}}")
async def ai_quiz_get_attempt(attempt_id: str, request: Request):
    session = require_session(request)
    result = attempts.read(session["course_id"], attempt_id, session.get("user_id", ""), is_instructor(session))
    if result is None:
        _refuse(404, "attempt_not_found")
    return result
