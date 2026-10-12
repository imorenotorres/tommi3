"""Commit first: before submitting, the student says how sure they are (rule A15).

A switch per quiz, off by default, fixed in the published revision. What the student states is
stored with the attempt, under the same keyed hash as the attempt and nothing else of the person.
It never changes the score. The instructor gets counts per question: how many answers were marked
"I know this", and how many of those were wrong.
"""

import json

import pytest

from UltiR.ai_quiz import storage

from .conftest import BASE, cid
from .test_attempts import ATTEMPTS, PUBLISHED, QUIZZES, Course, code, submit

LEVELS = ("sure", "fairly", "guess")


@pytest.fixture
def course(client, launch):
    return Course(client, launch)


def switch(client, course, quiz, value=True):
    return client.put(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.instructor}, json={"confidence": value})


def asking_quiz(course, count=3):
    """A published quiz of `count` questions that asks how sure the student is. The key is B everywhere."""
    quiz = course.draft(count, title="Week 7")
    assert switch(course.client, course, quiz).status_code == 200
    for i in range(count):
        course.edit(quiz, i, review_status="approved")
    return course.publish(quiz)


def ids(quiz):
    return [q["question_id"] for q in quiz["questions"]]


def summary(client, course, quiz):
    return client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": course.instructor}).json()


def stored_attempts(quiz):
    folder = storage.course_dir(cid("course-A")) / "attempts" / quiz["quiz_id"]
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("a_*.json"))] if folder.is_dir() else []


# ── The switch ──────────────────────────────────────────────────────────────

def test_a_new_quiz_does_not_ask(client, course):
    quiz = course.draft(2)

    assert quiz["confidence"] is False
    published = course.published_quiz(2)
    assert client.get(f"{PUBLISHED}/{published['quiz_id']}", params={"token": course.learner()}).json()["confidence"] is False


def test_the_instructor_turns_it_on_and_off_for_one_quiz(client, course):
    quiz, other = course.draft(2, title="One"), course.draft(2, title="Other")

    assert switch(client, course, quiz, True).json()["confidence"] is True
    assert client.get(f"{QUIZZES}/{other['quiz_id']}", params={"token": course.instructor}).json()["confidence"] is False
    assert switch(client, course, quiz, False).json()["confidence"] is False


@pytest.mark.parametrize("value", ["yes", 1, 0, None, "true", [], {}])
def test_the_switch_takes_true_or_false_and_nothing_else(client, course, value):
    quiz = course.draft(2)

    response = switch(client, course, quiz, value)

    assert response.status_code == 400
    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.instructor}).json()["confidence"] is False


def test_the_title_can_still_be_changed_alone_and_together_with_the_switch(client, course):
    quiz = course.draft(2)
    put = lambda body: client.put(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.instructor}, json=body)  # noqa: E731

    assert put({"title": "Renamed"}).json()["title"] == "Renamed"
    both = put({"title": "Again", "confidence": True}).json()
    assert (both["title"], both["confidence"]) == ("Again", True)
    assert put({}).status_code == 400
    assert put({"title": "", "confidence": True}).status_code == 400
    assert put({"title": 5}).status_code == 400


def test_a_learner_cannot_touch_the_switch(client, course):
    quiz = course.draft(2)

    response = client.put(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.learner()}, json={"confidence": True})

    assert response.status_code == 403
    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.instructor}).json()["confidence"] is False


def test_the_switch_belongs_to_the_published_version(client, course):
    """Turning it on after publishing changes nothing for students until the quiz is published again."""
    quiz = course.published_quiz(2)
    learner = course.learner()
    assert switch(client, course, quiz, True).status_code == 200

    assert client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": learner}).json()["confidence"] is False

    again = course.publish(quiz)                       # the switch alone is a change worth a new version
    assert again["current_revision"] == 2
    now = client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": learner}).json()
    assert (now["revision"], now["confidence"]) == (2, True)
    first = storage.read_json(storage.course_dir(cid("course-A")) / "quizzes" / quiz["quiz_id"] / "rev-0001.json")
    assert not first.get("confidence")                 # the first version is as it was written


def test_a_quiz_published_before_the_switch_existed_does_not_ask(client, course):
    quiz = course.published_quiz(2)
    folder = storage.course_dir(cid("course-A")) / "quizzes" / quiz["quiz_id"]
    for name in ("meta.json", "rev-0001.json"):                    # as such files were written before
        stored = storage.read_json(folder / name)
        del stored["confidence"]
        (folder / name).write_text(json.dumps(stored), encoding="utf-8")
    learner = course.learner()

    assert client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": learner}).json()["confidence"] is False
    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.instructor}).json()["confidence"] is False
    assert submit(client, learner, quiz, dict.fromkeys(ids(quiz), "B")).status_code == 201
    response = client.post(f"{QUIZZES}/{quiz['quiz_id']}/publish", params={"token": course.instructor})
    assert (response.status_code, code(response)) == (409, "no_changes")


def test_publishing_unchanged_with_the_switch_as_it_was_is_still_no_change(client, course):
    quiz = asking_quiz(course, 2)

    response = client.post(f"{QUIZZES}/{quiz['quiz_id']}/publish", params={"token": course.instructor})

    assert (response.status_code, code(response)) == (409, "no_changes")


# ── Submitting ──────────────────────────────────────────────────────────────

def test_what_the_student_states_is_stored_and_comes_back_with_the_result(client, course):
    quiz = asking_quiz(course, 3)
    a, b, c = ids(quiz)
    learner = course.learner()

    response = submit(client, learner, quiz, {a: "B", b: "A", c: "B"}, confidence={a: "sure", b: "sure", c: "guess"})

    assert response.status_code == 201
    result = response.json()
    assert [r["confidence"] for r in result["results"]] == ["sure", "sure", "guess"]
    assert result["calibration"] == {"sure": {"answered": 2, "correct": 1}, "fairly": {"answered": 0, "correct": 0},
                                     "guess": {"answered": 1, "correct": 1}}
    later = client.get(f"{ATTEMPTS}/{result['attempt_id']}", params={"token": learner}).json()
    assert [r["confidence"] for r in later["results"]] == ["sure", "sure", "guess"]


@pytest.mark.parametrize("levels", [("sure", "sure", "sure"), ("guess", "guess", "guess"), ("fairly", "sure", "guess")])
def test_being_sure_or_not_never_changes_the_score(client, course, levels):
    quiz = asking_quiz(course, 3)
    answers = dict(zip(ids(quiz), ("B", "A", "B")))

    result = submit(client, course.learner(), quiz, answers, confidence=dict(zip(ids(quiz), levels))).json()

    assert (result["score"], result["total"]) == (2, 3)


def test_every_answered_question_needs_its_confidence(client, course):
    quiz = asking_quiz(course, 3)
    a, b, c = ids(quiz)

    for stated in ({a: "sure", b: "sure"}, {}, None):
        extra = {} if stated is None else {"confidence": stated}
        response = submit(client, course.learner(), quiz, {a: "B", b: "B", c: "B"}, **extra)
        assert (response.status_code, code(response)) == (400, "confidence_missing")
    assert stored_attempts(quiz) == []                 # nothing was kept of the refused attempts


def test_a_question_left_unanswered_needs_none_and_keeps_none(client, course):
    quiz = asking_quiz(course, 3)
    a, b, c = ids(quiz)

    result = submit(client, course.learner(), quiz, {a: "B"}, confidence={a: "fairly", c: "sure"}).json()

    assert [r["confidence"] for r in result["results"]] == ["fairly", None, None]
    assert stored_attempts(quiz)[0]["confidence"] == {a: "fairly"}


@pytest.mark.parametrize("bad", ["certain", "SURE", "", 3, None, True, ["sure"], {"level": "sure"}])
def test_a_confidence_that_is_not_one_of_the_three_is_refused(client, course, bad):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)

    response = submit(client, course.learner(), quiz, {a: "B", b: "B"}, confidence={a: "sure", b: bad})

    assert (response.status_code, code(response)) == (400, "bad_request")
    assert stored_attempts(quiz) == []


@pytest.mark.parametrize("stated", ["sure", ["sure", "sure"], 1])
def test_confidence_must_be_given_per_question(client, course, stated):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)

    response = submit(client, course.learner(), quiz, {a: "B", b: "B"}, confidence=stated)

    assert (response.status_code, code(response)) == (400, "bad_request")


def test_confidence_for_a_question_that_is_not_in_the_quiz_is_refused(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)

    response = submit(client, course.learner(), quiz, {a: "B", b: "B"},
                      confidence={a: "sure", b: "sure", "q_0123456789abcdef": "sure"})

    assert (response.status_code, code(response)) == (400, "bad_request")


def test_a_quiz_that_does_not_ask_ignores_a_confidence_that_is_sent(client, course):
    quiz = course.published_quiz(2)
    a, b = ids(quiz)

    result = submit(client, course.learner(), quiz, {a: "B", b: "A"}, confidence={a: "sure", b: "sure"}).json()

    assert "calibration" not in result and all("confidence" not in r for r in result["results"])
    assert "confidence" not in stored_attempts(quiz)[0]
    report = summary(client, course, quiz)
    assert report["confidence"] is False and all("sure" not in q for q in report["questions"])


def test_the_attempt_file_holds_the_confidence_under_the_keyed_hash_and_nothing_of_the_person(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)
    learner = course.learner(user="student-4711", name="Synthetic Student", email="student@example.invalid")
    submit(client, learner, quiz, {a: "B", b: "A"}, confidence={a: "guess", b: "sure"})

    folder = storage.course_dir(cid("course-A")) / "attempts" / quiz["quiz_id"]
    text = next(folder.glob("a_*.json")).read_text(encoding="utf-8")
    attempt = json.loads(text)

    assert attempt["confidence"] == {a: "guess", b: "sure"}
    assert set(attempt) == {"attempt_id", "quiz_id", "revision", "owner", "preview", "answers", "confidence",
                            "score", "total", "submitted_at"}
    assert len(attempt["owner"]) == 40
    for private in ("student-4711", "Synthetic Student", "student@example.invalid", learner):
        assert private not in text


def test_nothing_before_submitting_tells_what_others_stated(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)
    submit(client, course.learner(user="student-1"), quiz, {a: "A", b: "A"}, confidence={a: "sure", b: "sure"})
    other = course.learner(user="student-2")

    text = client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": other}).text
    listing = client.get(PUBLISHED, params={"token": other}).text

    assert '"confidence":true' in text.replace(" ", "")
    for word in ("sure", "guess", "calibration"):
        assert word not in text and word not in listing


def test_another_student_cannot_read_what_one_stated(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)
    mine = submit(client, course.learner(user="student-1"), quiz, {a: "B", b: "B"}, confidence={a: "sure", b: "guess"}).json()

    response = client.get(f"{ATTEMPTS}/{mine['attempt_id']}", params={"token": course.learner(user="student-2")})

    assert response.status_code == 404


# ── The instructor's summary ────────────────────────────────────────────────

def test_the_summary_counts_per_question_who_was_sure_and_wrong(client, course):
    quiz = asking_quiz(course, 3)
    a, b, c = ids(quiz)
    submit(client, course.learner(user="s-1"), quiz, {a: "A", b: "B", c: "A"}, confidence={a: "sure", b: "sure", c: "guess"})
    submit(client, course.learner(user="s-2"), quiz, {a: "A", b: "A", c: "B"}, confidence={a: "sure", b: "fairly", c: "sure"})
    submit(client, course.learner(user="s-3"), quiz, {a: "B", b: "B"}, confidence={a: "sure", b: "sure"})

    report = summary(client, course, quiz)

    assert report["confidence"] is True
    assert [(q["answered"], q["correct"], q["sure"], q["sure_wrong"]) for q in report["questions"]] == [
        (3, 1, 3, 2),      # a: all three were sure, two of them wrong
        (3, 2, 2, 0),      # b: the one who was wrong was not sure
        (2, 1, 1, 0),      # c: one guessed wrong, one was sure and right
    ]


def test_the_summary_names_nobody(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)
    learner = course.learner(user="student-4711", name="Synthetic Student")
    submit(client, learner, quiz, {a: "A", b: "A"}, confidence={a: "sure", b: "sure"})

    text = client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": course.instructor}).text

    for private in ("student-4711", "Synthetic Student", "owner", "attempt_id"):
        assert private not in text


def test_an_instructors_own_try_is_not_counted_among_the_sure_and_wrong(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)
    submit(client, course.instructor, quiz, {a: "A", b: "A"}, confidence={a: "sure", b: "sure"})

    assert [(q["sure"], q["sure_wrong"]) for q in summary(client, course, quiz)["questions"]] == [(0, 0), (0, 0)]


def test_answers_to_an_earlier_version_are_not_counted_for_the_current_one(client, course):
    quiz = asking_quiz(course, 2)
    a, b = ids(quiz)
    submit(client, course.learner(), quiz, {a: "A", b: "A"}, confidence={a: "sure", b: "sure"})
    course.edit(quiz, 0, question="A rewritten first question?")
    course.edit(quiz, 0, review_status="approved")
    course.publish(quiz)

    assert [(q["sure"], q["sure_wrong"]) for q in summary(client, course, quiz)["questions"]] == [(0, 0), (0, 0)]


def test_a_learner_cannot_read_the_summary(client, course):
    quiz = asking_quiz(course, 2)

    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": course.learner()}).status_code == 403


# ── Both languages ──────────────────────────────────────────────────────────

def test_the_three_levels_and_the_question_have_a_text_in_both_languages(client):
    from .test_pages import load_strings
    strings = load_strings(client)

    for language in ("en", "es"):
        for key in ("confidence_legend", "review_confidence", "student_confidence_missing", "err_confidence_missing",
                    *[f"confidence_{level}" for level in LEVELS]):
            assert strings[language].get(key), (language, key)


def test_the_levels_the_server_accepts_are_the_levels_the_page_offers():
    from UltiR.ai_quiz import schema
    from .test_pages import MODULE_DIR

    assert schema.CONFIDENCE_LEVELS == LEVELS
    page_script = (MODULE_DIR / "static" / "student.js").read_text(encoding="utf-8")
    assert "['sure', 'fairly', 'guess']" in page_script
