"""Practice, part three: giving a student an exercise. The pool, the daily limit, "Report a problem".

An exercise that passed its checks is kept and given to the next student who asks for the same
topic, level and language, so a class does not wait for the model each time. A student is never
given the same exercise twice. A reported exercise leaves the pool until the instructor has
looked at it.
"""

import pytest

from UltiR.ai_quiz import exercises, progress

from .conftest import BASE, cid
from .fake_practice import kind_of
from .practice_helpers import PRACTICE, PracticeCourse

LEARNER_EXERCISE_KEYS = {"exercise_id", "type", "level", "statement", "page", "doc_label", "topic_id"}


def code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch)


def ask(client, token, expect=201, **body):
    response = client.post(f"{PRACTICE}/exercise", params={"token": token}, json={"language": "es", **body})
    assert response.status_code == expect, response.text
    return response.json()


def exercise_calls(fake_llm) -> int:
    return sum(kind_of(c["messages"]) == "exercise" for c in fake_llm.calls)


def ids(course):
    return [t["topic_id"] for t in course.topics()]


# ── Choosing ────────────────────────────────────────────────────────────────

def test_a_student_gets_one_exercise_of_the_topic_and_level_they_chose(client, course):
    topic = ids(course)[2]

    got = ask(client, course.learner(), topic_id=topic, level="avanzado")

    assert set(got["exercise"]) == LEARNER_EXERCISE_KEYS
    assert (got["exercise"]["topic_id"], got["exercise"]["level"]) == (topic, "avanzado")
    assert got["topic"] == {"topic_id": topic, "name": "Scoring a model", "pages": [3, 4]}
    assert got["chosen"] == {"topic": "yours", "level": "yours"} and got["aim"] is None


def test_with_only_a_topic_the_level_starts_at_basic(client, course):
    got = ask(client, course.learner(), topic_id=ids(course)[1])

    assert got["exercise"]["level"] == "basico" and got["chosen"] == {"topic": "yours", "level": "for_you"}


def test_with_only_a_level_a_topic_not_yet_practised_is_chosen(client, course):
    token = course.learner()
    first = ask(client, token, level="intermedio")["exercise"]["topic_id"]
    second = ask(client, token, level="intermedio")

    assert second["chosen"] == {"topic": "for_you", "level": "yours"}
    assert second["exercise"]["topic_id"] != first


def test_with_nothing_chosen_both_are_chosen(client, course):
    got = ask(client, course.learner())

    assert got["chosen"] == {"topic": "for_you", "level": "for_you"} and got["exercise"]["level"] == "basico"


def test_open_and_numerical_exercises_take_turns_where_the_passages_have_numbers(client, course):
    token = course.learner()

    kinds = [ask(client, token, topic_id=ids(course)[1], level="intermedio")["exercise"]["type"] for _ in range(3)]

    assert kinds == ["abierta", "numerica", "abierta"]


@pytest.mark.parametrize("body, field", [
    ({"level": "experto"}, "level"), ({"language": "fr"}, "language"), ({"topic_id": 5}, "topic_id"),
])
def test_a_wrong_choice_is_refused(client, course, body, field):
    response = client.post(f"{PRACTICE}/exercise", params={"token": course.learner()}, json=body)

    assert response.status_code == 400 and response.json()["detail"]["field"] == field


def test_a_topic_that_is_off_or_unknown_is_refused(client, course):
    first = ids(course)[0]
    course.settings(topics={first: {"enabled": False}})

    assert code(client.post(f"{PRACTICE}/exercise", params={"token": course.learner()},
                            json={"topic_id": first})) == "unknown_topic"
    assert code(client.post(f"{PRACTICE}/exercise", params={"token": course.learner()},
                            json={"topic_id": "t_0000000000000000"})) == "unknown_topic"


def test_with_practice_off_no_exercise_is_given(client, course, fake_llm):
    course.settings(enabled=False)

    assert code(client.post(f"{PRACTICE}/exercise", params={"token": course.learner()}, json={})) == "practice_off"
    assert fake_llm.calls == []


# ── The pool ────────────────────────────────────────────────────────────────

def test_the_next_student_gets_the_same_exercise_from_the_pool_without_a_model_call(client, course, fake_llm):
    topic = ids(course)[1]
    first = ask(client, course.learner("s-1"), topic_id=topic, level="intermedio")["exercise"]
    calls = len(fake_llm.calls)

    second = ask(client, course.learner("s-2"), topic_id=topic, level="intermedio")["exercise"]

    assert second["exercise_id"] == first["exercise_id"] and len(fake_llm.calls) == calls
    assert exercises.load(cid("course-A"), first["exercise_id"])["served"] == 2
    assert exercises.run_log(cid("course-A"))[-1]["outcome"] == "pool"


def test_a_student_never_gets_the_same_exercise_twice(client, course, fake_llm):
    token, topic = course.learner(), ids(course)[1]

    got = [ask(client, token, topic_id=topic, level="intermedio")["exercise"]["exercise_id"] for _ in range(3)]

    assert len(set(got)) == 3 and exercise_calls(fake_llm) == 3


def test_the_pool_is_kept_apart_by_level_and_by_language(client, course, fake_llm):
    topic = ids(course)[1]
    ask(client, course.learner("s-1"), topic_id=topic, level="intermedio")

    ask(client, course.learner("s-2"), topic_id=topic, level="avanzado")
    ask(client, course.learner("s-3"), topic_id=topic, level="intermedio", language="en")

    assert exercise_calls(fake_llm) == 3


def test_the_statements_that_exist_are_given_to_the_model_to_avoid(client, course, fake_llm):
    token, topic = course.learner(), ids(course)[1]
    first = ask(client, token, topic_id=topic, level="intermedio")["exercise"]["statement"]

    ask(client, token, topic_id=topic, level="intermedio")

    written = [prompt for call, prompt in zip(fake_llm.calls, fake_llm.prompts) if kind_of(call["messages"]) == "exercise"]
    assert f"- {first}" in written[-1]


def test_a_retired_exercise_is_not_given_again(client, course, fake_llm):
    topic = ids(course)[1]
    first = ask(client, course.learner("s-1"), topic_id=topic, level="intermedio")["exercise"]
    exercises.set_status(cid("course-A"), first["exercise_id"], "retirado")

    second = ask(client, course.learner("s-2"), topic_id=topic, level="intermedio")["exercise"]

    assert second["exercise_id"] != first["exercise_id"]


# ── Reporting ───────────────────────────────────────────────────────────────

def report(client, token, exercise, reason="solucion_incorrecta"):
    return client.post(f"{PRACTICE}/exercises/{exercise['exercise_id']}/report", params={"token": token},
                       json={"reason": reason})


def test_a_reported_exercise_is_hidden_until_the_instructor_looks_at_it(client, course):
    topic, first_student = ids(course)[1], course.learner("s-1")
    first = ask(client, first_student, topic_id=topic, level="intermedio")["exercise"]

    assert report(client, first_student, first).status_code == 200

    stored = exercises.load(cid("course-A"), first["exercise_id"])
    assert stored["status"] == "reportado" and [r["reason"] for r in stored["reports"]] == ["solucion_incorrecta"]
    second = ask(client, course.learner("s-2"), topic_id=topic, level="intermedio")["exercise"]
    assert second["exercise_id"] != first["exercise_id"]


def test_a_report_has_one_of_the_fixed_reasons_and_no_text(client, course):
    token = course.learner()
    exercise = ask(client, token, topic_id=ids(course)[1])["exercise"]

    for reason in ("it is wrong!", "", None, ["otro"]):
        assert report(client, token, exercise, reason).status_code == 400


def test_a_student_reports_only_an_exercise_they_were_given_and_only_once(client, course):
    token = course.learner("s-1")
    exercise = ask(client, token, topic_id=ids(course)[1])["exercise"]

    assert code(report(client, course.learner("s-2"), exercise)) == "exercise_not_found"
    report(client, token, exercise)
    report(client, token, exercise)
    assert len(exercises.load(cid("course-A"), exercise["exercise_id"])["reports"]) == 1


# ── Limits ──────────────────────────────────────────────────────────────────

def test_a_student_gets_at_most_the_daily_number_of_exercises(client, course, monkeypatch, fake_llm):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_DAILY", "2")
    token = course.learner()
    ask(client, token)
    ask(client, token)

    response = client.post(f"{PRACTICE}/exercise", params={"token": token}, json={})

    assert (response.status_code, code(response), response.json()["detail"]["limit"]) == (429, "daily_limit", 2)
    assert exercise_calls(fake_llm) == 2
    ask(client, course.learner("s-2"))                     # another student is not affected


def test_an_exercise_that_could_not_be_written_is_not_counted(client, course, monkeypatch, fake_llm):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_DAILY", "1")
    token = course.learner()
    fake_llm.queue("bad", "bad", "bad")

    failed = client.post(f"{PRACTICE}/exercise", params={"token": token}, json={})

    assert (failed.status_code, code(failed)) == (502, "exercise_failed")
    ask(client, token)


@pytest.mark.parametrize("value, limit", [("", 30), ("0", 30), ("x", 30), ("5", 5), ("1001", 30)])
def test_the_daily_limit_is_thirty_unless_set(monkeypatch, value, limit):
    from UltiR.ai_quiz import config
    monkeypatch.setenv("AI_QUIZ_PRACTICE_DAILY", value)

    assert config.practice_daily_limit() == limit


@pytest.mark.parametrize("value, seconds", [("", 60), ("0", 60), ("301", 60), ("20", 20)])
def test_the_model_time_limit_is_sixty_seconds_unless_set(monkeypatch, value, seconds):
    from UltiR.ai_quiz import config
    monkeypatch.setenv("AI_QUIZ_PRACTICE_TIMEOUT", value)

    assert config.practice_timeout() == seconds


def test_the_course_has_an_hourly_cap_on_practice_runs(client, course, monkeypatch):
    from UltiR.ai_quiz import limits
    monkeypatch.setattr(limits, "MAX_PRACTICE_RUNS_PER_HOUR", 1)
    ask(client, course.learner("s-1"), topic_id=ids(course)[1])

    response = client.post(f"{PRACTICE}/exercise", params={"token": course.learner("s-2")}, json={"topic_id": ids(course)[2]})

    assert (response.status_code, code(response)) == (429, "practice_busy")


# ── Who ─────────────────────────────────────────────────────────────────────

def test_an_instructor_may_practise_and_is_kept_out_of_the_totals(client, course):
    ask(client, course.instructor)

    record = progress.load(cid("course-A"), progress.owner(cid("course-A"), "teacher-1"))
    assert record["preview"] is True


def test_without_a_session_there_is_no_exercise(client, course):
    assert client.post(f"{PRACTICE}/exercise", json={}).status_code == 401


def test_the_quizzes_do_not_change(client, course):
    ask(client, course.learner())

    assert client.get(f"{BASE}/api/published", params={"token": course.learner()}).json() == {"quizzes": []}
