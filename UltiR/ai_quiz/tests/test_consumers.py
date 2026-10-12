"""Several Moodle installations on one server: one consumer key and secret each, and the key is part of
the course and of the stored user (rule A3).

Moodle numbers its courses and users 1, 2, 3 ...: course 2 of one Moodle and course 2 of another are
different courses. Seen on 2026-10-11 with a local Moodle, when the course was named by the number alone.
"""

import logging

import pytest

from UltiR.ai_quiz import attempts, storage

from .conftest import BASE, KEY, KEY_2, SECRET, SECRET_2, cid
from .test_attempts import ATTEMPTS, DOCS, PUBLISHED, QUIZZES, Course

SESSION = f"{BASE}/api/session"


def answers_for(quiz, option="A"):
    return {"revision": quiz["current_revision"], "answers": {q["question_id"]: option for q in quiz["questions"]}}


# ── Each installation launches with its own key and secret ──────────────────

def test_a_second_moodle_launches_with_its_own_key_and_secret(client, launch, second_moodle):
    token = second_moodle.token(role="Instructor", course="2")

    assert client.get(SESSION, params={"token": token}).json()["is_instructor"] is True
    assert launch.post(launch.form()).status_code == 303          # the first one still works


@pytest.mark.parametrize("key, secret", [(KEY_2, SECRET), (KEY, SECRET_2)])
def test_a_key_is_accepted_only_with_its_own_secret(launch, second_moodle, key, secret):
    response = launch.post(launch.form(key=key, secret=secret))

    assert response.status_code == 403
    assert "token=" not in response.headers.get("location", "")


def test_a_key_that_is_not_registered_is_refused_when_two_are(launch, second_moodle):
    assert launch.post(launch.form(key="third_moodle", secret=SECRET_2)).status_code == 403


def test_the_second_key_is_unknown_until_it_is_registered(client):
    from .conftest import Launcher
    stranger = Launcher(client, KEY_2, SECRET_2)

    assert stranger.post(stranger.form()).status_code == 403


# ── A registration that is not complete or not separate stops the tool ──────

@pytest.mark.parametrize("settings", [
    {"AI_QUIZ_LTI_KEY_2": KEY_2},                                                   # a key without a secret
    {"AI_QUIZ_LTI_SECRET_2": SECRET_2},                                             # a secret without a key
    {"AI_QUIZ_LTI_KEY_2": KEY_2, "AI_QUIZ_LTI_SECRET_2": "   "},                    # a blank secret
    {"AI_QUIZ_LTI_KEY_2": KEY_2, "AI_QUIZ_LTI_SECRET_2": "change_this_secret_in_env"},   # the other tools' placeholder
    {"AI_QUIZ_LTI_KEY_2": KEY, "AI_QUIZ_LTI_SECRET_2": SECRET_2},                   # the first Moodle's key again
    {"AI_QUIZ_LTI_KEY_2": KEY_2, "AI_QUIZ_LTI_SECRET_2": SECRET},                   # the first Moodle's secret again
    {"AI_QUIZ_LTI_KEY_2": "second:moodle", "AI_QUIZ_LTI_SECRET_2": SECRET_2},       # a key with the separator in it
    {"AI_QUIZ_LTI_KEY_2": "second moodle", "AI_QUIZ_LTI_SECRET_2": SECRET_2},
    {"AI_QUIZ_LTI_KEY_2": "k" * 65, "AI_QUIZ_LTI_SECRET_2": SECRET_2},
])
def test_a_faulty_second_registration_stops_the_tool_for_everyone(client, launch, monkeypatch, settings):
    token = launch.token()
    for name, value in settings.items():
        monkeypatch.setenv(name, value)

    assert launch.post(launch.form()).status_code == 503
    assert client.get(SESSION, params={"token": token}).status_code == 503


def test_no_key_is_handed_out_while_a_registration_is_faulty(monkeypatch):
    from UltiR.ai_quiz import config
    assert config.consumers() == {KEY: SECRET}

    monkeypatch.setenv("AI_QUIZ_LTI_KEY_2", KEY_2)                 # no secret for it

    assert config.consumers() == {}


def test_a_first_key_with_the_separator_in_it_stops_the_tool(launch, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_LTI_KEY", "uma:test")

    assert launch.post(launch.form(key="uma:test")).status_code == 503


def test_a_faulty_registration_is_logged_by_name_and_never_by_value(launch, monkeypatch, caplog):
    monkeypatch.setenv("AI_QUIZ_LTI_KEY_2", KEY_2)
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET_3", SECRET_2)

    with caplog.at_level(logging.WARNING):
        launch.post(launch.form())

    assert "AI_QUIZ_LTI_SECRET_2" in caplog.text and "AI_QUIZ_LTI_KEY_3" in caplog.text
    assert SECRET not in caplog.text and SECRET_2 not in caplog.text


def test_registrations_may_be_numbered_with_gaps(client, monkeypatch):
    from .conftest import Launcher
    monkeypatch.setenv("AI_QUIZ_LTI_KEY_7", KEY_2)
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET_7", SECRET_2)
    seventh = Launcher(client, KEY_2, SECRET_2)

    assert seventh.post(seventh.form()).status_code == 303


# ── The same course number in two Moodles is two courses ────────────────────

def test_the_second_moodle_does_not_see_the_first_ones_documents(client, launch, second_moodle):
    first = Course(client, launch, course="2")                     # uploads handout.pdf
    teacher_2 = second_moodle.token(role="Instructor", course="2", user="teacher-1")

    assert client.get(DOCS, params={"token": teacher_2}).json()["documents"] == []
    assert client.get(f"{DOCS}/{first.doc['doc_id']}", params={"token": teacher_2}).status_code == 404
    assert client.delete(f"{DOCS}/{first.doc['doc_id']}", params={"token": teacher_2}).status_code == 404
    drafted = client.post(f"{BASE}/api/generate", params={"token": teacher_2},
                          json={"doc_ids": [first.doc["doc_id"]], "count": 2})
    assert drafted.status_code in (400, 404)
    # ... and the first one still has it.
    assert [d["doc_id"] for d in client.get(DOCS, params={"token": first.instructor}).json()["documents"]] == [first.doc["doc_id"]]


def test_the_second_moodle_does_not_see_the_first_ones_quizzes(client, launch, second_moodle):
    first = Course(client, launch, course="2")
    quiz = first.published_quiz(2, title="Week 7")
    teacher_2 = second_moodle.token(role="Instructor", course="2", user="teacher-1")
    student_2 = second_moodle.token(role="Learner", course="2", user="5")

    assert client.get(QUIZZES, params={"token": teacher_2}).json()["quizzes"] == []
    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": teacher_2}).status_code == 404
    assert client.post(f"{QUIZZES}/{quiz['quiz_id']}/unpublish", params={"token": teacher_2}).status_code == 404
    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": teacher_2}).status_code == 404
    assert client.get(PUBLISHED, params={"token": student_2}).json()["quizzes"] == []
    assert client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": student_2}).status_code == 404
    assert client.post(f"{QUIZZES}/{quiz['quiz_id']}/attempts", params={"token": student_2},
                       json=answers_for(quiz)).status_code == 404
    # ... and the first one's student still does.
    student_1 = first.learner(user="5")
    assert [q["quiz_id"] for q in client.get(PUBLISHED, params={"token": student_1}).json()["quizzes"]] == [quiz["quiz_id"]]


def test_the_second_moodle_does_not_see_the_first_ones_attempts(client, launch, second_moodle):
    first = Course(client, launch, course="2")
    quiz = first.published_quiz(2, title="Week 7")
    student_1 = first.learner(user="5")
    attempt = client.post(f"{QUIZZES}/{quiz['quiz_id']}/attempts", params={"token": student_1}, json=answers_for(quiz)).json()

    # User 5 of the other Moodle, and its teacher, ask for that attempt by its id.
    student_2 = second_moodle.token(role="Learner", course="2", user="5")
    teacher_2 = second_moodle.token(role="Instructor", course="2", user="teacher-1")
    assert client.get(f"{ATTEMPTS}/{attempt['attempt_id']}", params={"token": student_2}).status_code == 404
    assert client.get(f"{ATTEMPTS}/{attempt['attempt_id']}", params={"token": teacher_2}).status_code == 404
    # The first one's student still reads it.
    assert client.get(f"{ATTEMPTS}/{attempt['attempt_id']}", params={"token": student_1}).status_code == 200


def test_user_5_of_two_moodles_is_two_people(client, launch, second_moodle):
    """Each Moodle publishes its own quiz in its course 2; user 5 of each has tried only their own."""
    first = Course(client, launch, course="2")
    second = Course(client, second_moodle, course="2")
    quiz_1, quiz_2 = first.published_quiz(2, title="First"), second.published_quiz(2, title="Second")
    student_1, student_2 = first.learner(user="5"), second.learner(user="5")
    client.post(f"{QUIZZES}/{quiz_1['quiz_id']}/attempts", params={"token": student_1}, json=answers_for(quiz_1))

    listing_1 = client.get(PUBLISHED, params={"token": student_1}).json()["quizzes"]
    listing_2 = client.get(PUBLISHED, params={"token": student_2}).json()["quizzes"]
    assert [(q["title"], q["my_attempts"]) for q in listing_1] == [("First", 1)]
    assert [(q["title"], q["my_attempts"]) for q in listing_2] == [("Second", 0)]
    assert attempts.owner_key(cid("2"), "5") != attempts.owner_key(cid("2", KEY_2), "5")


def test_each_moodle_has_a_folder_of_its_own_for_course_2(client, launch, second_moodle):
    Course(client, launch, course="2")
    Course(client, second_moodle, course="2")

    folders = sorted(p.name for p in storage.data_root().iterdir())
    assert len(folders) == 2
    assert folders[0].startswith(f"{KEY}-2-") and folders[1].startswith(f"{KEY_2}-2-")
    assert storage.course_dir(cid("2")).name == folders[0]


def test_the_course_id_never_reaches_a_page(client, launch):
    token = launch.token(course="2")

    assert KEY not in client.get(SESSION, params={"token": token}).text


# ── A session belongs to the registration it was launched with ──────────────

def test_a_session_stops_working_when_its_moodle_is_no_longer_registered(client, launch, second_moodle, monkeypatch):
    token = second_moodle.token(role="Instructor", course="2")
    assert client.get(DOCS, params={"token": token}).status_code == 200

    monkeypatch.delenv("AI_QUIZ_LTI_KEY_2")
    monkeypatch.delenv("AI_QUIZ_LTI_SECRET_2")

    assert client.get(DOCS, params={"token": token}).status_code == 401
    assert client.get(SESSION, params={"token": launch.token()}).status_code == 200


def test_a_session_that_was_not_bound_to_a_registration_is_not_a_session(client):
    """Defence in depth: only the launch route binds; a session created any other way names no Moodle."""
    from UltiR.ai_quiz import lti_provider
    token = lti_provider.sessions.create({"user_id": "5", "name": "", "email": "", "role": "Instructor",
                                          "course_id": "2", "course_name": "", "resource_link_id": ""})

    assert client.get(DOCS, params={"token": token}).status_code == 401


def test_the_local_test_route_gets_a_bound_session_too(client, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_DEV_TEST", "1")
    token = client.get(f"{BASE}/test", params={"role": "instructor"}).headers["location"].split("token=")[1]

    assert client.get(DOCS, params={"token": token}).status_code == 200
    assert [p.name for p in storage.data_root().iterdir()][0].startswith(f"{KEY}-test-")
