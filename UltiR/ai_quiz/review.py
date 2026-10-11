"""Review: drafts, instructor decisions and published revisions of a quiz.

This seam does not care how a draft item was produced. It stores drafts, and
(from the next step on) applies instructor edits and turns approved items
into immutable published revisions.

Layout inside a course folder:

    quizzes/<quiz_id>/meta.json     title, activity, published flag, current revision
    quizzes/<quiz_id>/draft.json    working copy: every question with its key, source and review status
"""

from datetime import datetime, timezone
from pathlib import Path

from UltiR.ai_quiz import limits, storage


class QuizError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def instructor_view(quiz: dict) -> dict:
    """Everything about a quiz, for instructors only: it includes the answer key."""
    return {**quiz["meta"], "questions": quiz["questions"]}
