"""Access rules checked over the whole router (rules A2, A3).

These tests walk every registered route, so a route added later without a
guard fails here instead of shipping open. A new route has to be placed on
purpose: in PUBLIC, in LEARNER_ALLOWED, or (by default) instructor-only.
"""

import re

import pytest

from .conftest import BASE

# Reachable without a session. Nothing here may return course data.
PUBLIC = {
    ("GET", BASE),                           # redirect to the info page
    ("POST", BASE),                          # the signed launch itself
    ("GET", f"{BASE}/info"),
    ("GET", f"{BASE}/test"),                 # 404 unless AI_QUIZ_DEV_TEST=1
    ("GET", f"{BASE}/assets/{{name:path}}"), # strings and scripts, no course data
}

# Reachable with a learner session. Everything else is instructor-only.
LEARNER_ALLOWED = {
    ("GET", f"{BASE}/student"),
    ("GET", f"{BASE}/api/session"),
    ("GET", f"{BASE}/api/published"),                       # published quizzes, safe fields only
    ("GET", f"{BASE}/api/published/{{quiz_id}}"),            # questions and options, no key
    ("POST", f"{BASE}/api/quizzes/{{quiz_id}}/attempts"),    # submit answers; the server grades
    ("GET", f"{BASE}/api/attempts/{{attempt_id}}"),          # own result
    ("GET", f"{BASE}/api/figures/{{doc_id}}/{{figure_id}}"), # a figure, only while a published question shows it
    ("GET", f"{BASE}/api/practice/topics"),                 # practice: the topics that are on, and the levels
    ("POST", f"{BASE}/api/practice/exercise"),              # one exercise, without its solution
    ("POST", f"{BASE}/api/practice/exercises/{{exercise_id}}/report"),   # "report a problem"
}


@pytest.fixture(autouse=True)
def practice_offered(monkeypatch):
    """The server offers practice, so that its routes are walked with everything else. (Without it they answer 404.)"""
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


def registered_routes():
    from UltiR.ai_quiz.lti_provider import router

    return sorted(
        (method, route.path)
        for route in router.routes
        for method in route.methods
        if method not in ("HEAD", "OPTIONS")
    )


def concrete(path: str) -> str:
    """Fill path parameters with a harmless value."""
    return re.sub(r"\{[^}]+\}", "x", path)


def guarded_routes():
    return [r for r in registered_routes() if r not in PUBLIC]


def test_the_lists_above_name_only_routes_that_exist():
    routes = set(registered_routes())

    assert PUBLIC <= routes
    assert LEARNER_ALLOWED <= routes
    assert ("GET", f"{BASE}/instructor") in routes


def test_every_route_outside_the_public_list_needs_a_session(client):
    open_routes = [
        (method, path) for method, path in guarded_routes()
        if client.request(method, concrete(path)).status_code != 401
    ]

    assert open_routes == []


def test_a_made_up_token_is_not_a_session(client):
    open_routes = [
        (method, path) for method, path in guarded_routes()
        if client.request(method, concrete(path), params={"token": "0" * 64}).status_code != 401
    ]

    assert open_routes == []


def test_every_route_outside_the_learner_list_refuses_a_learner(client, launch):
    token = launch.token(role="Learner")
    instructor_only = [r for r in guarded_routes() if r not in LEARNER_ALLOWED]

    allowed_anyway = [
        (method, path) for method, path in instructor_only
        if client.request(method, concrete(path), params={"token": token}).status_code != 403
    ]

    assert instructor_only != []
    assert allowed_anyway == []


def test_a_learner_is_let_into_the_learner_routes(client, launch):
    token = launch.token(role="Learner")

    refused = [
        (method, path) for method, path in sorted(LEARNER_ALLOWED)
        if client.request(method, concrete(path), params={"token": token}).status_code in (401, 403)
    ]

    assert refused == []


def test_an_instructor_is_let_into_every_guarded_route(client, launch):
    token = launch.token(role="Instructor")

    refused = [
        (method, path) for method, path in guarded_routes()
        if client.request(method, concrete(path), params={"token": token}).status_code in (401, 403)
    ]

    assert refused == []


@pytest.mark.parametrize("missing", ["AI_QUIZ_LTI_SECRET", "AI_QUIZ_ID_KEY"])
def test_every_guarded_route_answers_503_when_a_required_setting_is_missing(client, launch, monkeypatch, missing):
    token = launch.token(role="Instructor")
    monkeypatch.delenv(missing)

    still_working = [
        (method, path) for method, path in guarded_routes()
        if client.request(method, concrete(path), params={"token": token}).status_code != 503
    ]

    assert still_working == []


def test_teaching_assistant_is_not_treated_as_instructor(client, launch):
    token = launch.token(role="urn:lti:role:ims/lis/TeachingAssistant")

    assert client.get(f"{BASE}/instructor", params={"token": token}).status_code == 403


def test_moodle_style_instructor_role_string_is_recognised(client, launch):
    token = launch.token(role="Instructor,urn:lti:sysrole:ims/lis/Administrator")

    assert client.get(f"{BASE}/instructor", params={"token": token}).status_code == 200
