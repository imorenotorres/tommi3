"""Practice without a model at run time (Ignacio, 2026-10-15): AI_QUIZ_PRACTICE_MODEL is off unless it is "1".

With it off, nothing a student does in practice asks a model: no exercise is written, no feedback is given by a
model, and an exercise a model wrote earlier is neither served, nor reopened, nor answered.
"""

import pytest

from UltiR.ai_quiz import config

from .practice_helpers import PRACTICE, PracticeCourse


def code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch)


@pytest.mark.parametrize("value, on", [("1", True), ("", False), ("0", False), ("true", False), ("yes", False)])
def test_run_time_model_use_is_off_unless_the_setting_is_one(monkeypatch, value, on):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_MODEL", value)

    assert config.practice_model_enabled() is on


def test_it_is_off_when_the_setting_is_missing():
    assert config.practice_model_enabled() is False


def test_with_the_model_off_no_topic_without_a_tutor_is_offered_and_no_model_is_asked(client, course, fake_llm):
    token = course.learner()

    assert course.topics(token) == []
    response = client.post(f"{PRACTICE}/exercise", params={"token": token}, json={"language": "es"})

    assert (response.status_code, code(response)) == (409, "no_topics")
    assert fake_llm.calls == []


def test_a_model_exercise_given_while_it_was_on_is_not_answered_or_reopened_once_it_is_off(client, course, fake_llm,
                                                                                         monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_MODEL", "1")
    token = course.learner()
    topic = course.topics(token)[1]["topic_id"]
    exercise = client.post(f"{PRACTICE}/exercise", params={"token": token}, json={"topic_id": topic}).json()["exercise"]
    calls = len(fake_llm.calls)
    monkeypatch.delenv("AI_QUIZ_PRACTICE_MODEL")

    response = client.post(f"{PRACTICE}/exercises/{exercise['exercise_id']}/answer", params={"token": token},
                           json={"answer": "Minimal samples are small."})

    assert (response.status_code, code(response)) == (409, "model_practice_off")
    assert client.get(f"{PRACTICE}/open", params={"token": token}).json() == {"exercise": None}
    assert len(fake_llm.calls) == calls


def test_the_teacher_still_sees_and_sets_the_topics(client, course):
    settings = client.get(f"{PRACTICE}/settings", params={"token": course.instructor}).json()

    assert settings["enabled"] is True and len(settings["topics"]) == 3
