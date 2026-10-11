"""Review: drafts, instructor decisions and published revisions of a quiz.

This seam does not care how a draft item was produced. It stores drafts,
applies instructor edits and decisions, and turns approved items into
immutable published revisions.

Layout inside a course folder:

    quizzes/<quiz_id>/meta.json       title, activity, published flag, current revision
    quizzes/<quiz_id>/draft.json      working copy: every question with its key, source and review status
    quizzes/<quiz_id>/rev-0001.json   a published revision; written once, never changed
"""

from datetime import datetime, timezone
from pathlib import Path

from UltiR.ai_quiz import limits, schema, storage
from UltiR.ai_quiz.mathflag import has_math_notation

STATUSES = ("draft", "approved", "rejected")
CONTENT_FIELDS = ("question", "options", "correct_option_id", "explanation", "difficulty")


class QuizError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _now() -> str:
    # microseconds, so that "newest first" is well defined for quizzes made in the same second
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _quizzes_dir(course_id: str) -> Path:
    return storage.course_dir(course_id) / "quizzes"


def _quiz_dir(course_id: str, quiz_id: str) -> Path:
    return _quizzes_dir(course_id) / quiz_id


def quiz_ids(course_id: str) -> list[str]:
    folder = _quizzes_dir(course_id)
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_dir() and storage.is_id(p.name, "z"))


def load_quiz(course_id: str, quiz_id: str) -> dict | None:
    """{"meta": ..., "questions": [...]} for a quiz of this course, or None."""
    if not storage.is_id(quiz_id, "z"):
        return None
    meta = storage.read_json(_quiz_dir(course_id, quiz_id) / "meta.json")
    if meta is None:
        return None
    questions = storage.read_json(_quiz_dir(course_id, quiz_id) / "draft.json", default=[])
    return {"meta": meta, "questions": questions}


def create_quiz(course_id: str, title: str, questions: list[dict]) -> dict:
    """A new unpublished quiz holding these draft questions."""
    with storage.locked(course_id):
        if len(quiz_ids(course_id)) >= limits.MAX_QUIZZES_PER_COURSE:
            raise QuizError(409, "too_many_quizzes")
        quiz_id = storage.new_id("z")
        now = _now()
        meta = {"quiz_id": quiz_id, "title": title, "activity": "quiz", "created_at": now, "updated_at": now,
                "published": False, "current_revision": None}
        storage.write_json(_quiz_dir(course_id, quiz_id) / "draft.json", questions)
        storage.write_json(_quiz_dir(course_id, quiz_id) / "meta.json", meta)
        return {"meta": meta, "questions": questions}


def add_questions(course_id: str, quiz_id: str, questions: list[dict]) -> dict:
    """Append draft questions to an existing quiz of this course."""
    with storage.locked(course_id):
        quiz = load_quiz(course_id, quiz_id)
        if quiz is None:
            raise QuizError(404, "quiz_not_found")
        quiz["questions"] = quiz["questions"] + questions
        quiz["meta"]["updated_at"] = _now()
        storage.write_json(_quiz_dir(course_id, quiz_id) / "draft.json", quiz["questions"])
        storage.write_json(_quiz_dir(course_id, quiz_id) / "meta.json", quiz["meta"])
        return quiz


def passage_for_students(question: dict) -> str:
    """Whether students are shown the source passage of a question after answering.

    "shown"            the passage was located in the document and reads as plain prose
    "hidden_math"      located, but it carries mathematical notation that text reading may
                       have garbled: students get the page number only
    "hidden_unlocated" the server could not locate it: it is the model's claim, not a
                       quotation, and students get the page number only

    Worked out when asked, from the stored passage, so a better flag also covers revisions
    that were published before it.
    """
    if not question.get("grounded"):
        return "hidden_unlocated"
    if has_math_notation((question.get("source") or {}).get("excerpt") or ""):
        return "hidden_math"
    return "shown"


def instructor_view(quiz: dict) -> dict:
    """Everything about a quiz, for instructors only: it includes the answer key.

    Each question also says what students will see of its source passage, so the page can
    warn the instructor. That field is derived here and never stored.
    """
    questions = [{**q, "passage_for_students": passage_for_students(q)} for q in quiz["questions"]]
    return {**quiz["meta"], "questions": questions}


def list_quizzes(course_id: str) -> list[dict]:
    """Quiz summaries for instructors, newest first. No questions, only counts by review status."""
    summaries = []
    for quiz_id in quiz_ids(course_id):
        quiz = load_quiz(course_id, quiz_id)
        if quiz is None:
            continue
        counts = {status: 0 for status in STATUSES}
        for question in quiz["questions"]:
            counts[question.get("review_status", "draft")] = counts.get(question.get("review_status", "draft"), 0) + 1
        summaries.append({**quiz["meta"], "counts": counts})
    return sorted(summaries, key=lambda s: (s["created_at"], s["quiz_id"]), reverse=True)


def _save(course_id: str, quiz: dict) -> dict:
    quiz["meta"]["updated_at"] = _now()
    folder = _quiz_dir(course_id, quiz["meta"]["quiz_id"])
    storage.write_json(folder / "draft.json", quiz["questions"])
    storage.write_json(folder / "meta.json", quiz["meta"])
    return quiz


def _require(course_id: str, quiz_id: str) -> dict:
    quiz = load_quiz(course_id, quiz_id)
    if quiz is None:
        raise QuizError(404, "quiz_not_found")
    return quiz


def rename_quiz(course_id: str, quiz_id: str, title: str) -> dict:
    with storage.locked(course_id):
        quiz = _require(course_id, quiz_id)
        quiz["meta"]["title"] = title
        return _save(course_id, quiz)


def update_question(course_id: str, quiz_id: str, question_id: str, changes: dict) -> dict:
    """Apply an instructor's edit or decision to one draft question.

    Only the content fields, the review status and the acceptance flag can
    change. The source, the grounding result and the ids cannot: they were
    established by the server and an edit does not get to rewrite them.
    """
    with storage.locked(course_id):
        quiz = _require(course_id, quiz_id)
        question = next((q for q in quiz["questions"] if q["question_id"] == question_id), None)
        if question is None:
            raise QuizError(404, "question_not_found")

        if any(field in changes for field in CONTENT_FIELDS):
            merged = {field: changes.get(field, question[field]) for field in CONTENT_FIELDS}
            try:
                content = schema.validate_question(merged, default_difficulty=None)
            except schema.InvalidQuestion:
                raise QuizError(400, "invalid_question") from None
            others = {schema.same(q["question"]) for q in quiz["questions"] if q["question_id"] != question_id}
            if schema.same(content["question"]) in others:
                raise QuizError(409, "duplicate_question")
            if any(content[field] != question[field] for field in CONTENT_FIELDS):
                question.update(content)
                question["edited"] = True

        if "accept_ungrounded" in changes:
            if not isinstance(changes["accept_ungrounded"], bool):
                raise QuizError(400, "bad_request")
            question["ungrounded_accepted"] = changes["accept_ungrounded"] and not question["grounded"]

        status = changes.get("review_status", question["review_status"])
        if status not in STATUSES:
            raise QuizError(400, "bad_request")
        if status == "approved" and not _may_be_published(question):
            if "review_status" in changes:
                raise QuizError(409, "needs_acceptance")
            status = "draft"            # the acceptance was withdrawn: the approval goes with it
        question["review_status"] = status
        return _save(course_id, quiz)


def _may_be_published(question: dict) -> bool:
    """A question whose passage was not located needs the instructor's explicit acceptance."""
    return bool(question.get("grounded")) or bool(question.get("ungrounded_accepted"))


# ── Publishing ────────────────────────────────────────────────────────────────

def _revision_path(course_id: str, quiz_id: str, number: int) -> Path:
    return _quiz_dir(course_id, quiz_id) / f"rev-{number:04d}.json"


def load_revision(course_id: str, quiz_id: str, number) -> dict | None:
    if not storage.is_id(quiz_id, "z") or isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return None
    return storage.read_json(_revision_path(course_id, quiz_id, number))


def publish(course_id: str, quiz_id: str) -> dict:
    """Make the approved questions available to learners.

    A revision file is written once and never opened for writing again, so an
    attempt that refers to it keeps its meaning whatever happens to the draft
    later. Publishing changed content creates the next revision.
    """
    with storage.locked(course_id):
        quiz = _require(course_id, quiz_id)
        meta = quiz["meta"]
        approved = [q for q in quiz["questions"] if q["review_status"] == "approved"]
        if not approved:
            raise QuizError(409, "nothing_approved")
        if not all(_may_be_published(q) for q in approved):
            raise QuizError(409, "needs_acceptance")
        content = {"title": meta["title"], "questions": approved}

        current = load_revision(course_id, quiz_id, meta["current_revision"])
        if current and {"title": current["title"], "questions": current["questions"]} == content:
            if meta["published"]:
                raise QuizError(409, "no_changes")
            meta["published"] = True        # published again unchanged: same revision
            return _save(course_id, quiz)

        number = (meta["current_revision"] or 0) + 1
        revision = {"quiz_id": quiz_id, "revision": number, "published_at": _now(), **content}
        try:
            # Exclusive create: if another server process published this number a moment ago,
            # this fails instead of replacing what that process wrote.
            storage.write_json_new(_revision_path(course_id, quiz_id, number), revision)
        except FileExistsError:
            raise QuizError(409, "revision_exists") from None
        meta["current_revision"] = number
        meta["published"] = True
        return _save(course_id, quiz)


def unpublish(course_id: str, quiz_id: str) -> dict:
    """Hide the quiz from learners. Revisions and attempts stay."""
    with storage.locked(course_id):
        quiz = _require(course_id, quiz_id)
        if not quiz["meta"]["published"]:
            raise QuizError(409, "not_published")
        quiz["meta"]["published"] = False
        return _save(course_id, quiz)
