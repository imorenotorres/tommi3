"""The learner side: what a learner may see of a published quiz, attempts, and grading.

The server holds the key. A learner gets questions and options, sends back
the options they chose, and the score is computed here from the published
revision. Nothing the browser says about a score, a result or an owner is
read.

An attempt is stored with a keyed hash of the Moodle user id (never the id,
a name or an email) and with the number of the revision it was graded
against, so its result keeps its meaning when the quiz changes later.

    attempts/<quiz_id>/<attempt_id>.json
"""

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path

from UltiR.ai_quiz import config, limits, review, schema, storage


class AttemptError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def owner_key(course_id: str, user_id: str) -> str:
    """A stable pseudonym for one person in one course.

    HMAC rather than a plain hash: Moodle user ids are small numbers, so a
    plain hash could be reversed by trying every number. Changing
    AI_QUIZ_ID_KEY detaches every stored attempt from its owner.
    """
    message = f"{course_id}\x00{user_id}".encode("utf-8", "replace")
    return hmac.new(config.id_key().encode("utf-8"), message, hashlib.sha256).hexdigest()[:40]


def _attempts_dir(course_id: str, quiz_id: str) -> Path:
    return storage.course_dir(course_id) / "attempts" / quiz_id


def _attempts(course_id: str, quiz_id: str) -> list[dict]:
    folder = _attempts_dir(course_id, quiz_id)
    if not folder.is_dir():
        return []
    found = (storage.read_json(p) for p in sorted(folder.glob("a_*.json")))
    return [a for a in found if a]


def _published(course_id: str, quiz_id: str) -> dict | None:
    """The quiz, if it belongs to this course and is published right now."""
    quiz = review.load_quiz(course_id, quiz_id)
    if quiz is None or not quiz["meta"]["published"]:
        return None
    return quiz


# ── What a learner may see before submitting ──────────────────────────────────
# Built field by field. Anything not named here does not leave the server.

def _learner_question(question: dict) -> dict:
    view = {
        "question_id": question["question_id"],
        "question": question["question"],
        "options": [{"id": o["id"], "text": o["text"]} for o in question["options"]],
        "difficulty": question["difficulty"],
    }
    # A figure the instructor published with the question: where to fetch it and its caption.
    doc_id = (question.get("source") or {}).get("doc_id")
    figures = [{"doc_id": doc_id, "figure_id": f["figure_id"], "caption": f.get("caption") or ""}
               for f in question.get("figures") or [] if doc_id]
    if figures:
        view["figures"] = figures
    if question.get("math") == "latex":
        view["math"] = "latex"                  # the page draws what stands between dollar signs as formulas
    return view


def figure_is_published(course_id: str, doc_id: str, figure_id: str) -> bool:
    """Whether a question that learners can see right now shows this figure.

    Only the current revision of a quiz that is published counts. A draft, an
    approved question that has not been published and an unpublished quiz do not.
    """
    for quiz_id in review.quiz_ids(course_id):
        quiz = _published(course_id, quiz_id)
        revision = review.load_revision(course_id, quiz_id, quiz["meta"]["current_revision"]) if quiz else None
        for question in (revision or {}).get("questions", []):
            if (question.get("source") or {}).get("doc_id") != doc_id:
                continue
            if any(f.get("figure_id") == figure_id for f in question.get("figures") or []):
                return True
    return False


def published_quizzes(course_id: str, user_id: str) -> list[dict]:
    mine = owner_key(course_id, user_id) if user_id else None
    listing = []
    for summary in review.list_quizzes(course_id):
        if not summary["published"]:
            continue
        revision = review.load_revision(course_id, summary["quiz_id"], summary["current_revision"])
        if revision is None:
            continue
        own = [a for a in _attempts(course_id, summary["quiz_id"]) if mine and a["owner"] == mine]
        listing.append({
            "quiz_id": summary["quiz_id"],
            "title": revision["title"],
            "revision": revision["revision"],
            "n_questions": len(revision["questions"]),
            "my_attempts": len(own),
            "my_best": max((a["score"] for a in own), default=None),
        })
    return listing


def learner_quiz(course_id: str, quiz_id: str) -> dict | None:
    quiz = _published(course_id, quiz_id)
    if quiz is None:
        return None
    revision = review.load_revision(course_id, quiz_id, quiz["meta"]["current_revision"])
    if revision is None:
        return None
    return {
        "quiz_id": quiz_id,
        "title": revision["title"],
        "revision": revision["revision"],
        "questions": [_learner_question(q) for q in revision["questions"]],
    }


# ── Submitting and reading an attempt ─────────────────────────────────────────

def _result(attempt: dict, revision: dict) -> dict:
    """An attempt with its feedback. Only ever built for the owner or the course instructor, after submission."""
    results = []
    for question in revision["questions"]:
        selected = attempt["answers"].get(question["question_id"])
        source = question.get("source") or {}
        quoted = review.passage_for_students(question) == "shown"
        results.append({
            **_learner_question(question),
            "selected": selected,
            "correct_option_id": question["correct_option_id"],
            "correct": selected == question["correct_option_id"],
            "explanation": question["explanation"],
            # Where in the document the question comes from. The passage itself is quoted only when
            # the server located it and it reads as plain prose; otherwise the page number is all.
            "source": {"doc_label": source.get("doc_label"), "page": source.get("page"),
                       "excerpt": source.get("excerpt") if quoted else None} if source.get("doc_id") else None,
        })
    return {
        "attempt_id": attempt["attempt_id"],
        "quiz_id": attempt["quiz_id"],
        "title": revision["title"],
        "revision": attempt["revision"],
        "score": attempt["score"],
        "total": attempt["total"],
        "submitted_at": attempt["submitted_at"],
        "results": results,
    }


def submit(course_id: str, quiz_id: str, user_id: str, is_instructor: bool, body: dict) -> dict:
    """Grade and store one attempt. Reads `revision` and `answers` from the body and nothing else."""
    quiz = _published(course_id, quiz_id)
    if quiz is None:
        raise AttemptError(404, "quiz_not_found")
    if not user_id:
        raise AttemptError(400, "no_user")

    number = body.get("revision")
    revision = review.load_revision(course_id, quiz_id, number)
    if revision is None:
        raise AttemptError(400, "bad_request")

    given = body.get("answers")
    question_ids = {q["question_id"] for q in revision["questions"]}
    if not isinstance(given, dict) or not set(given) <= question_ids:
        raise AttemptError(400, "bad_request")
    answers = {}
    for question_id, option in given.items():
        if option is None:
            continue                          # left unanswered
        if not isinstance(option, str) or option not in schema.OPTION_IDS:
            raise AttemptError(400, "bad_request")
        answers[question_id] = option

    owner = owner_key(course_id, user_id)
    with storage.locked(course_id):
        taken = sum(1 for a in _attempts(course_id, quiz_id) if a["owner"] == owner)
        if taken >= limits.MAX_ATTEMPTS_PER_QUIZ:
            raise AttemptError(429, "too_many_attempts")
        attempt = {
            "attempt_id": storage.new_id("a"),
            "quiz_id": quiz_id,
            "revision": revision["revision"],
            "owner": owner,
            "preview": bool(is_instructor),     # an instructor trying the quiz; kept out of the summary
            "answers": answers,
            "score": sum(1 for q in revision["questions"] if answers.get(q["question_id"]) == q["correct_option_id"]),
            "total": len(revision["questions"]),
            "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        storage.write_json(_attempts_dir(course_id, quiz_id) / f"{attempt['attempt_id']}.json", attempt)
    return _result(attempt, revision)


def read(course_id: str, attempt_id: str, user_id: str, is_instructor: bool) -> dict | None:
    """The attempt with its feedback, for its owner or an instructor of the course. Otherwise None."""
    if not storage.is_id(attempt_id, "a"):
        return None
    matches = list((storage.course_dir(course_id) / "attempts").glob(f"*/{attempt_id}.json"))
    attempt = storage.read_json(matches[0]) if matches else None
    if not attempt:
        return None
    if not is_instructor and (not user_id or attempt["owner"] != owner_key(course_id, user_id)):
        return None
    revision = review.load_revision(course_id, attempt["quiz_id"], attempt["revision"])
    if revision is None:
        return None
    return _result(attempt, revision)


# ── The instructor's summary ──────────────────────────────────────────────────

def summary(course_id: str, quiz_id: str) -> dict | None:
    """Counts for one quiz. Aggregates only: no owner, no single attempt."""
    quiz = review.load_quiz(course_id, quiz_id)
    if quiz is None:
        return None
    attempts = [a for a in _attempts(course_id, quiz_id) if not a.get("preview")]
    percents = [100 * a["score"] / a["total"] for a in attempts if a["total"]]
    revision = review.load_revision(course_id, quiz_id, quiz["meta"]["current_revision"])
    questions = []
    for question in (revision or {}).get("questions", []):
        chosen = [a["answers"][question["question_id"]] for a in attempts
                  if a["revision"] == revision["revision"] and question["question_id"] in a["answers"]]
        questions.append({
            "question_id": question["question_id"],
            "question": question["question"],
            "answered": len(chosen),
            "correct": sum(1 for option in chosen if option == question["correct_option_id"]),
        })
    return {
        "quiz_id": quiz_id,
        "title": quiz["meta"]["title"],
        "current_revision": quiz["meta"]["current_revision"],
        "attempts": len(attempts),
        "learners": len({a["owner"] for a in attempts}),
        "average_percent": round(sum(percents) / len(percents)) if percents else None,
        "questions": questions,
    }
