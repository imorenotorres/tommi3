"""
AI Quiz Generator — LTI 1.1 Tool

An instructor uploads course material, the LLM drafts multiple-choice
questions, the instructor reviews and publishes them, students practise from
Moodle and the server grades. No question the model writes reaches students
before an instructor approves it. Practice ("Practicar", practice.py) comes
from programmed tutors (tutors/, programmed.py): programs written once and
reviewed by the instructor, which make the exercise, diagnose the answer and
give feedback with no model call. Model-written practice is kept behind
AI_QUIZ_PRACTICE_MODEL, off by default; where it is on, its exercises reach
students live, behind checks in code, labelled as written by AI, with a way
to report them and an instructor's list to retire them. See README.md.

Configuration (web/.env):
    AI_QUIZ_LTI_SECRET=<shared_secret>    required, no default
    AI_QUIZ_ID_KEY=<random_secret>        required, no default; keys the hash
                                          of the user id stored with attempts
    AI_QUIZ_LTI_KEY=ai_quiz_uma           optional, this is the default
    AI_QUIZ_LTI_KEY_2=<another_key>       optional: one more Moodle installation,
    AI_QUIZ_LTI_SECRET_2=<its_secret>     with a key and a secret of its own (_3 ...)
    AI_QUIZ_DEV_TEST=1                    optional, local machines only: opens
                                          /lti/ai-quiz/test
    AI_QUIZ_MIN_GROUP=3                   optional, this is the default: how many
                                          students must have answered a question
                                          before the instructor sees totals for it
    AI_QUIZ_PRACTICE_ENABLED=1            optional, off unless exactly "1": offers
                                          practice; each course then has its own switch
    AI_QUIZ_PRACTICE_DAILY=30             optional, this is the default: exercises per
                                          student and day
    AI_QUIZ_PRACTICE_TIMEOUT=60           optional, this is the default: seconds per
                                          model call of practice
    AI_QUIZ_PRACTICE_MODEL=1              optional, off unless exactly "1": practice may ask
                                          a model at run time (write exercises, check them,
                                          give feedback). Off: programmed tutors only

One consumer key and secret per Moodle installation, never shared: the key is
part of the id under which a course and its users are kept, because every
Moodle numbers its courses 1, 2, 3 ...

Until every required setting has a valid value the tool answers 503 everywhere
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
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from UltiR.ai_quiz import (
    analysis, attempts, config, documents, generation, ingestion, limits, moodle_xml, practice, review, storage,
)
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
    "expired.js": "text/javascript",
    "denied.js": "text/javascript",
    "instructor.js": "text/javascript",
    "student.js": "text/javascript",
    "practice.js": "text/javascript",
    "practice_admin.js": "text/javascript",
    "math.js": "text/javascript",
    "app.css": "text/css",
    # KaTeX 0.19.0 draws the formulas. It is shipped in static/vendor/katex with its licence, so
    # that no page asks another host for anything.
    "vendor/katex/katex.min.js": "text/javascript",
    "vendor/katex/katex.min.css": "text/css",
    "vendor/katex/LICENSE": "text/plain",
    **{f"vendor/katex/fonts/KaTeX_{font}.woff2": "font/woff2" for font in (
        "AMS-Regular", "Caligraphic-Bold", "Caligraphic-Regular", "Fraktur-Bold", "Fraktur-Regular", "Main-Bold",
        "Main-BoldItalic", "Main-Italic", "Main-Regular", "Math-BoldItalic", "Math-Italic", "SansSerif-Bold",
        "SansSerif-Italic", "SansSerif-Regular", "Script-Regular", "Size1-Regular", "Size2-Regular", "Size3-Regular",
        "Size4-Regular", "Typewriter-Regular")},
}


# ── Guards ────────────────────────────────────────────────────────────────────
# The platform's login middleware does not cover /lti/ paths: these two
# functions are the only access control this tool has.

def require_session(request: Request) -> dict:
    config.require_configured()
    session = sessions.require(request)
    # A session belongs to the Moodle installation it was launched from. One that names none, or one
    # whose installation is no longer registered, is not a session.
    if session.get("consumer") not in config.consumers():
        raise HTTPException(401, "Sesion no valida. Accede desde Moodle.")
    return session


def require_instructor(request: Request) -> dict:
    session = require_session(request)
    if not is_instructor(session):
        raise HTTPException(403, "Instructors only")
    return session


def _page(name: str) -> HTMLResponse:
    return HTMLResponse((_STATIC_DIR / name).read_text(encoding="utf-8"))


# What a person is shown when a page is refused. The refusal itself does not change: same status,
# and nothing of the page that was asked for.
_REFUSAL_PAGES = {
    401: "expired.html",    # no session: open the activity again from the course
    403: "denied.html",     # a session, but not an instructor's: this page is for instructors
}


def _page_behind(guard, request: Request, name: str) -> HTMLResponse:
    """A page for whoever passes `guard`. Who does not gets a page of the tool that says why, in the
    reader's language, not the bare JSON of the check: a person who reloads the tab after a restart
    of the server, or a student who opens the instructors' address. A tool that is not configured
    answers as before.
    """
    try:
        guard(request)
    except HTTPException as refusal:
        told = _REFUSAL_PAGES.get(refusal.status_code)
        if told is None:
            raise
        return HTMLResponse((_STATIC_DIR / told).read_text(encoding="utf-8"), status_code=refusal.status_code,
                            headers={"Cache-Control": "no-store"})
    return _page(name)


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


def _bind(response, consumer_key: str):
    """Tie the session a launch has just created to the Moodle installation it came from.

    The shared launch code names the course by Moodle's own course id, a small number that every
    Moodle uses. Here the consumer key is put in front of it, so everything this tool keeps for the
    session (the course folder, and the stored user, whose hash includes the course id) belongs to
    one installation. A refused launch created no session, and its response passes through unchanged.
    """
    session = sessions.get(_session_token(response))
    if session is not None:
        session["course_id"] = config.course_id(consumer_key, session["course_id"])
        session["consumer"] = consumer_key
    return response


def _session_token(response) -> str:
    """The token of the session a launch has just created, or "" when the launch was refused."""
    location = response.headers.get("location", "") if response.status_code == 303 else ""
    return parse_qs(urlparse(location).query).get("token", [""])[0]


# Shown when a correctly signed launch names no course. In both languages at once: at this point
# there is no session and no page script that could choose one.
_NO_COURSE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Quiz Generator</title>
<link rel="stylesheet" href="/lti/ai-quiz/assets/app.css">
</head>
<body>
<header class="band"><div class="title"><h1>AI Quiz Generator</h1></div></header>
<main class="narrow">
  <section class="card">
    <h2>Error: the launch names no course</h2>
    <p>Moodle sent no course id (context_id), so the tool cannot tell which course this is. Open the tool
      from an activity inside a course.</p>
  </section>
  <section class="card" lang="es">
    <h2>Error: el lanzamiento no indica ningún curso</h2>
    <p>Moodle no ha enviado ningún identificador de curso (context_id), así que la herramienta no puede saber
      de qué curso se trata. Abre la herramienta desde una actividad dentro de un curso.</p>
  </section>
</main>
</body>
</html>
"""


@router.post(BASE)
async def ai_quiz_launch(request: Request):
    config.require_configured()
    registered = config.consumers()
    form = await request.form()                # the shared code reads the same parsed form again
    consumer_key = str(form.get("oauth_consumer_key", ""))
    if consumer_key not in registered:
        # Not one of ours. The shared code refuses it in its own words when it is given another key.
        consumer_key = next(iter(registered))
    response = await lti_launch(
        request, consumer_key, registered[consumer_key], sessions,
        redirect_instructor=f"{BASE}/instructor",
        redirect_learner=f"{BASE}/student",
    )
    token = _session_token(response)
    if token and not str(form.get("context_id", "")).strip():
        # Signed correctly, but it names no course. The shared code has put it into a course it calls
        # "default", which every such launch would share. That session is withdrawn before anyone
        # is given its token, and the launch is refused. (A course whose id really is "default" is
        # not affected: the check is on what Moodle sent.)
        sessions.revoke(token)
        return HTMLResponse(_NO_COURSE, status_code=400)
    return _bind(response, consumer_key)


@router.get(f"{BASE}/test")
async def ai_quiz_test(role: str = "learner"):
    """Local test launch without Moodle. Does not exist unless AI_QUIZ_DEV_TEST=1."""
    if not config.dev_test_enabled():
        raise HTTPException(404)
    config.require_configured()
    response = await lti_test_launch(
        sessions,
        redirect_instructor=f"{BASE}/instructor",
        redirect_learner=f"{BASE}/student",
        role="instructor" if role.lower() == "instructor" else "learner",
    )
    return _bind(response, config.lti_key())


# ── Pages and assets ──────────────────────────────────────────────────────────

@router.get(f"{BASE}/info")
async def ai_quiz_info():
    return _page("info.html")


@router.get(f"{BASE}/instructor")
async def ai_quiz_instructor(request: Request):
    return _page_behind(require_instructor, request, "instructor.html")


@router.get(f"{BASE}/student")
async def ai_quiz_student(request: Request):
    return _page_behind(require_session, request, "student.html")


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


# ── Figures ───────────────────────────────────────────────────────────────────

@router.get(f"{BASE}/api/documents/{{doc_id}}/figures")
async def ai_quiz_list_figures(doc_id: str, request: Request):
    """Every figure of a document, for the instructor: id, page, caption. The images come from the route below."""
    session = require_instructor(request)
    figures = documents.list_figures(session["course_id"], doc_id)
    if figures is None:
        _refuse(404, "not_found")
    return {"figures": figures}


@router.get(f"{BASE}/api/figures/{{doc_id}}/{{figure_id}}")
async def ai_quiz_figure(doc_id: str, figure_id: str, request: Request):
    """One figure as an image.

    The course is the one of the session. An instructor gets any figure of
    the course. A student gets a figure only while a published question of
    the course shows it. Every refusal is the same 404, so the answer does
    not tell whether a figure exists.
    """
    session = require_session(request)
    course_id = session["course_id"]
    allowed = is_instructor(session) or attempts.figure_is_published(course_id, doc_id, figure_id)
    found = documents.figure_file(course_id, doc_id, figure_id) if allowed else None
    if found is None:
        _refuse(404, "not_found")
    path, media_type = found
    return FileResponse(path, media_type=media_type,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"})


def _figure_note(course_id: str, doc_id: str, figure_id) -> dict | None:
    """What a question keeps about a figure it shows: id, caption and page, from the stored record."""
    record = documents.get_figure(course_id, doc_id, figure_id) if doc_id else None
    if record is None:
        return None
    return {"figure_id": record["figure_id"], "caption": record.get("caption") or "", "page": record.get("page")}


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
        {"doc_id": d["doc_id"], "doc_label": d["label"], "mode": d["mode"], **chunk}
        for d in chosen for chunk in documents.load_chunks(course_id, d["doc_id"])
    ]
    existing = [q["question"] for q in quiz["questions"]] if quiz else []
    try:
        result = await generation.generate(chunks, count, difficulty, topic, existing)
        for question in result["questions"]:
            # The generator names a figure by id. The stored question carries what was found under that id.
            notes = [_figure_note(course_id, question["source"]["doc_id"], named["figure_id"])
                     for named in question["figures"]]
            question["figures"] = [note for note in notes if note]
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
async def ai_quiz_change_quiz(quiz_id: str, request: Request):
    """The settings of a quiz: its title, and whether students are asked how sure they are. One or both."""
    session = require_instructor(request)
    body = await _json_object(request)
    title = confidence = None
    if "title" in body:
        title = _text_field(body, "title", limits.MAX_TITLE_CHARS) if isinstance(body["title"], str) else ""
        if not title:
            _refuse(400, "bad_request", field="title")
    if "confidence" in body:
        confidence = body["confidence"]
        if not isinstance(confidence, bool):            # true or false, not 1, "yes" or null
            _refuse(400, "bad_request", field="confidence")
    if title is None and confidence is None:
        _refuse(400, "bad_request", field="title")
    return _reviewed(review.change_quiz, session["course_id"], quiz_id, title, confidence)


@router.put(f"{BASE}/api/quizzes/{{quiz_id}}/questions/{{question_id}}")
async def ai_quiz_update_question(quiz_id: str, question_id: str, request: Request):
    session = require_instructor(request)
    course_id = session["course_id"]
    body = await _json_object(request)
    figures = None                              # None: the request does not touch the figure
    if "figure_id" in body:
        # The browser names a figure by id or sends null for "none". What is stored comes from
        # the record of that figure in the question's own source document, and from nowhere else.
        quiz = review.load_quiz(course_id, quiz_id)
        question = next((q for q in quiz["questions"] if q["question_id"] == question_id), None) if quiz else None
        if question is None:
            _refuse(404, "question_not_found")
        figures = []
        if body["figure_id"] is not None:
            note = _figure_note(course_id, (question.get("source") or {}).get("doc_id"), body["figure_id"])
            if note is None:
                _refuse(400, "unknown_figure")
            figures = [note]
    return _reviewed(review.update_question, course_id, quiz_id, question_id, body, figures)


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


@router.get(f"{BASE}/api/quizzes/{{quiz_id}}/analysis")
async def ai_quiz_read_analysis(quiz_id: str, request: Request):
    """The stored analysis of the published version, if there is one, and whether one can be made. Asks no model."""
    session = require_instructor(request)
    try:
        return analysis.read(session["course_id"], quiz_id)
    except analysis.AnalysisFailed as failed:
        _refuse(failed.status, failed.code)


@router.post(f"{BASE}/api/quizzes/{{quiz_id}}/analysis")
async def ai_quiz_make_analysis(quiz_id: str, request: Request):
    """Ask the model for an analysis of the class summary and store it. One model run, counted like a generation.

    The model gets totals, question and option texts and source passages (see analysis.py), and
    nothing of the session: not who asks, and not which course this is.
    """
    session = require_instructor(request)
    course_id = session["course_id"]
    body = await _json_object(request)
    language = body.get("language", "en")               # the language the page is shown in
    if not isinstance(language, str) or language not in analysis.LANGUAGES:
        _refuse(400, "bad_request", field="language")
    try:
        analysis.require_available(course_id, quiz_id)   # refused here, before a run is counted
        wait = generation.take_generation_slot(course_id)
        if wait:
            _refuse(429, "rate_limited", retry_after_seconds=wait)
        made = await analysis.make(course_id, quiz_id, language)
    except analysis.AnalysisFailed as failed:
        _refuse(failed.status, failed.code)
    return JSONResponse({"analysis": made}, status_code=201)


@router.get(f"{BASE}/api/quizzes/{{quiz_id}}/export.xml")
async def ai_quiz_export(quiz_id: str, request: Request):
    """The questions of the last published version as a Moodle XML file, for Moodle's question bank.

    Only what was published: a draft, a rejected question and an edit that has not been published
    are not in it. A quiz that was withdrawn from students can still be exported.
    """
    session = require_instructor(request)
    quiz = review.load_quiz(session["course_id"], quiz_id)
    if quiz is None:
        _refuse(404, "quiz_not_found")
    revision = review.load_revision(session["course_id"], quiz_id, quiz["meta"]["current_revision"])
    if revision is None:
        _refuse(409, "never_published")
    return Response(moodle_xml.export(revision), media_type="application/xml", headers={
        # A download, never a page: the file holds text typed by people and written by a model.
        "Content-Disposition": f'attachment; filename="{moodle_xml.file_name(revision)}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


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


# ── Practice ("Practicar") ────────────────────────────────────────────────────
# A server that does not offer practice answers 404 on every route below, as if it had none.

def _practice_session(request: Request, guard) -> dict:
    session = guard(request)
    if not practice.server_offers_practice():
        _refuse(404, "not_found")
    return session


def _practised(action, *args):
    try:
        return action(*args)
    except practice.PracticeError as error:
        _refuse(error.status, error.code, **error.extra)


@router.get(f"{BASE}/api/practice/settings")
async def ai_quiz_practice_settings(request: Request):
    session = _practice_session(request, require_instructor)
    return practice.instructor_settings(session["course_id"])


@router.put(f"{BASE}/api/practice/settings")
async def ai_quiz_practice_change_settings(request: Request):
    """Practice on or off for the course; topics on or off, and their names."""
    session = _practice_session(request, require_instructor)
    body = await _json_object(request)
    return _practised(practice.change_settings, session["course_id"], body)


@router.get(f"{BASE}/api/practice/topics")
async def ai_quiz_practice_topics(request: Request):
    """The topics a student can choose, and the levels. 409 while the course has practice off."""
    session = _practice_session(request, require_session)
    return {"topics": _practised(practice.student_topics, session["course_id"]), "levels": list(practice.LEVELS)}


async def _practised_async(action, *args):
    try:
        return await action(*args)
    except practice.PracticeError as error:
        _refuse(error.status, error.code, **error.extra)


@router.post(f"{BASE}/api/practice/exercise")
async def ai_quiz_practice_exercise(request: Request):
    """One exercise for the student: of the topic and level they chose, or chosen for them. From the pool, or
    written now and checked. The answer to it, its key points and its passage are not in the response."""
    session = _practice_session(request, require_session)
    body = await _json_object(request)
    got = await _practised_async(practice.next_exercise, session["course_id"], session.get("user_id", ""),
                                 is_instructor(session), body)
    return JSONResponse(got, status_code=201)


@router.get(f"{BASE}/api/practice/open")
async def ai_quiz_practice_open(request: Request):
    """The student's last unfinished exercise, to go on with it after the window was closed."""
    session = _practice_session(request, require_session)
    return _practised(practice.open_exercise, session["course_id"], session.get("user_id", ""))


@router.post(f"{BASE}/api/practice/exercises/{{exercise_id}}/report")
async def ai_quiz_practice_report(exercise_id: str, request: Request):
    """"Report a problem": the exercise leaves the pool until the instructor has looked at it."""
    session = _practice_session(request, require_session)
    body = await _json_object(request)
    return _practised(practice.report, session["course_id"], session.get("user_id", ""), exercise_id, body)


@router.post(f"{BASE}/api/practice/exercises/{{exercise_id}}/answer")
async def ai_quiz_practice_answer(exercise_id: str, request: Request):
    """Feedback on one try. The verdict is decided here in code; the model's text only explains it.
    The answer is sent to the model with no name, id or course, and is not stored."""
    session = _practice_session(request, require_session)
    body = await _json_object(request)
    got = await _practised_async(practice.answer, session["course_id"], session.get("user_id", ""), exercise_id, body)
    return JSONResponse(got, status_code=201)


@router.get(f"{BASE}/api/practice/exercises/{{exercise_id}}/solution")
async def ai_quiz_practice_solution(exercise_id: str, request: Request):
    """The reference solution, once the answer was right or both tries are used."""
    session = _practice_session(request, require_session)
    return _practised(practice.solution, session["course_id"], session.get("user_id", ""), exercise_id)


@router.get(f"{BASE}/api/practice/pool")
async def ai_quiz_practice_pool(request: Request):
    """Every exercise of the course with everything it holds, and every exercise the checks discarded."""
    session = _practice_session(request, require_instructor)
    return practice.pool(session["course_id"])


@router.post(f"{BASE}/api/practice/pool/{{exercise_id}}/retire")
async def ai_quiz_practice_retire(exercise_id: str, request: Request):
    session = _practice_session(request, require_instructor)
    return _practised(practice.retire, session["course_id"], exercise_id)


@router.post(f"{BASE}/api/practice/pool/{{exercise_id}}/approve")
async def ai_quiz_practice_approve(exercise_id: str, request: Request):
    """A reported exercise goes back into use."""
    session = _practice_session(request, require_instructor)
    return _practised(practice.approve, session["course_id"], exercise_id)


@router.get(f"{BASE}/api/practice/tutors")
async def ai_quiz_practice_tutors(request: Request):
    """The programmed tutors: each spec to review, where its sentences are in the handout, and how often each
    mistake was recognised (totals only, nothing for fewer than the minimum group)."""
    session = _practice_session(request, require_instructor)
    return practice.tutors_review(session["course_id"])


@router.get(f"{BASE}/api/practice/summary")
async def ai_quiz_practice_summary(request: Request):
    """Totals of practice in the course. No names, no single answer, nothing for fewer than the minimum group."""
    session = _practice_session(request, require_instructor)
    return practice.class_summary(session["course_id"])
