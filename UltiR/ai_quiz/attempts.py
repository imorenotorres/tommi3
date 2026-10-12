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
        "confidence": review.asks_confidence(revision),     # the page then asks how sure, per question
        "questions": [_learner_question(q) for q in revision["questions"]],
    }


# ── Submitting and reading an attempt ─────────────────────────────────────────

def _result(attempt: dict, revision: dict) -> dict:
    """An attempt with its feedback. Only ever built for the owner or the course instructor, after submission."""
    asks = review.asks_confidence(revision)
    stated = attempt.get("confidence") or {}
    results = []
    for question in revision["questions"]:
        selected = attempt["answers"].get(question["question_id"])
        source = question.get("source") or {}
        quoted = review.passage_for_students(question) == "shown"
        results.append({
            **_learner_question(question),
            **({"confidence": stated.get(question["question_id"])} if asks else {}),
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
        # In a quiz that asks: per level, how many answers were given at it and how many were right.
        **({"calibration": {level: {
            "answered": sum(1 for r in results if r["confidence"] == level),
            "correct": sum(1 for r in results if r["confidence"] == level and r["correct"]),
        } for level in schema.CONFIDENCE_LEVELS}} if asks else {}),
    }


def _stated_confidence(body: dict, answers: dict, question_ids: set) -> dict:
    """How sure the student said they were, for each answered question of a quiz that asks.

    One of the three levels for every answer, or the attempt is refused: the quiz asks before it
    checks. What is stated for a question that was left unanswered is dropped.
    """
    stated = body.get("confidence", {})
    if not isinstance(stated, dict) or not set(stated) <= question_ids:
        raise AttemptError(400, "bad_request")
    if any(not isinstance(level, str) or level not in schema.CONFIDENCE_LEVELS for level in stated.values()):
        raise AttemptError(400, "bad_request")
    if not set(answers) <= set(stated):
        raise AttemptError(400, "confidence_missing")
    return {question_id: stated[question_id] for question_id in answers}


def submit(course_id: str, quiz_id: str, user_id: str, is_instructor: bool, body: dict) -> dict:
    """Grade and store one attempt. Reads `revision` and `answers` from the body and, in a quiz
    that asks how sure the student is, `confidence`. Nothing else: no score, no identity."""
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
    # Stored with the attempt, so under the same keyed hash as the answers. Never part of the score.
    # A quiz that does not ask keeps nothing of a confidence that is sent anyway.
    confidence = _stated_confidence(body, answers, question_ids) if review.asks_confidence(revision) else None

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
            **({} if confidence is None else {"confidence": confidence}),
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

def _question_totals(question: dict, given: list[dict], asks: bool) -> dict:
    """The totals of one question over the attempts that answered it. Never built for a group that is too small."""
    qid, key = question["question_id"], question["correct_option_id"]
    chosen = [a["answers"][qid] for a in given]
    per_option = {option: chosen.count(option) for option in schema.OPTION_IDS}
    # The wrong option that was chosen most; of two that were chosen equally often, the first.
    wrong = max((o for o in schema.OPTION_IDS if o != key and per_option[o]), key=lambda o: per_option[o], default=None)
    text = {o["id"]: o["text"] for o in question["options"]}
    totals = {
        "answered": len(chosen),
        "correct": per_option[key],
        "chosen": per_option,
        "top_wrong": {"id": wrong, "text": text[wrong], "count": per_option[wrong]} if wrong else None,
    }
    if asks:
        # The answers marked "I know this", and how many of those were wrong: where students
        # are mistaken without knowing it.
        sure = [a["answers"][qid] for a in given if (a.get("confidence") or {}).get(qid) == "sure"]
        totals["sure"] = len(sure)
        totals["sure_wrong"] = sum(1 for option in sure if option != key)
    return totals


def summary(course_id: str, quiz_id: str) -> dict | None:
    """The class summary of one quiz, for instructors. Totals only: no owner, no single attempt.

    Per question of the current version: the question, its key, the passage of the document it rests
    on with its page, and, once enough students have answered it, how many answers, how many right,
    how often each option was chosen, the wrong option chosen most and (in a version that asks) how
    many answers were sure and wrong. "Enough" is config.min_group(), counted in students, not in
    attempts: below it a question carries `too_few` and no number at all, because a total over one
    or two students says what a person did. The average follows the same rule.
    """
    quiz = review.load_quiz(course_id, quiz_id)
    if quiz is None:
        return None
    minimum = config.min_group()
    attempts = [a for a in _attempts(course_id, quiz_id) if not a.get("preview")]
    learners = len({a["owner"] for a in attempts})
    percents = [100 * a["score"] / a["total"] for a in attempts if a["total"]]
    revision = review.load_revision(course_id, quiz_id, quiz["meta"]["current_revision"])
    asks = review.asks_confidence(revision)
    questions = []
    for question in (revision or {}).get("questions", []):
        qid = question["question_id"]
        source = question.get("source") or {}
        given = [a for a in attempts if a["revision"] == revision["revision"] and qid in a["answers"]]
        enough = len({a["owner"] for a in given}) >= minimum
        questions.append({
            "question_id": qid,
            "question": question["question"],
            "correct_option_id": question["correct_option_id"],
            **({"math": "latex"} if question.get("math") == "latex" else {}),
            # The instructor's own document: shown whatever the number of answers.
            "source": {"doc_label": source.get("doc_label"), "page": source.get("page"), "excerpt": source.get("excerpt"),
                       "mode": source.get("mode") or "text", "located": bool(question.get("grounded"))}
                      if source.get("doc_id") else None,
            **(_question_totals(question, given, asks) if enough else {"too_few": True}),
        })
    return {
        "quiz_id": quiz_id,
        "title": quiz["meta"]["title"],
        "current_revision": quiz["meta"]["current_revision"],
        "confidence": asks,
        "attempts": len(attempts),
        "learners": learners,
        "min_group": minimum,
        "average_percent": round(sum(percents) / len(percents)) if percents and learners >= minimum else None,
        "questions": questions,
    }
