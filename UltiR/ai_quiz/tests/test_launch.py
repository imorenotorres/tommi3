"""The signed launch, the configuration gate and the local test route (rules A1, A2)."""

import logging
import time

import pytest

from .conftest import BASE, ID_KEY, SECRET


def session_of(client, token):
    return client.get(f"{BASE}/api/session", params={"token": token})


# ── A correctly signed launch ───────────────────────────────────────────────

def test_instructor_launch_opens_the_instructor_page_with_an_instructor_session(client, launch):
    response = launch.post(launch.form(role="Instructor"))

    assert response.status_code == 303
    assert response.headers["location"].startswith(f"{BASE}/instructor?token=")
    token = response.headers["location"].split("token=")[1]
    assert session_of(client, token).json()["is_instructor"] is True


def test_learner_launch_opens_the_student_page_with_a_learner_session(client, launch):
    response = launch.post(launch.form(role="Learner"))

    assert response.status_code == 303
    assert response.headers["location"].startswith(f"{BASE}/student?token=")
    token = response.headers["location"].split("token=")[1]
    assert session_of(client, token).json()["is_instructor"] is False


# ── Launches that must not create a session ─────────────────────────────────

def test_launch_signed_with_another_secret_is_rejected(launch):
    response = launch.post(launch.form(secret="some-other-secret"))

    assert response.status_code == 403
    assert "token=" not in response.headers.get("location", "")


def test_launch_whose_role_was_changed_after_signing_is_rejected(launch):
    form = launch.form(role="Learner")
    form["roles"] = "Instructor"

    assert launch.post(form).status_code == 403


def test_launch_signed_an_hour_ago_is_rejected(launch):
    form = launch.form(timestamp=int(time.time()) - 3600)

    assert launch.post(form).status_code == 403


def test_launch_with_an_unknown_consumer_key_is_rejected(launch):
    assert launch.post(launch.form(key="someone_elses_key")).status_code == 403


# ── A1: no secret, no launch; no placeholder ────────────────────────────────

def test_launch_is_refused_when_the_lti_secret_is_not_set(launch, monkeypatch):
    monkeypatch.delenv("AI_QUIZ_LTI_SECRET")
    # A form signed with the empty secret verifies against an empty secret,
    # so only an explicit refusal stops it.
    response = launch.post(launch.form(secret=""))

    assert response.status_code == 503


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_lti_secret_counts_as_not_set(launch, monkeypatch, blank):
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET", blank)

    assert launch.post(launch.form(secret=blank)).status_code == 503


def test_the_placeholder_secret_of_the_other_tools_is_not_accepted(launch, monkeypatch):
    placeholder = "change_this_secret_in_env"
    # Neither as a silent default ...
    monkeypatch.delenv("AI_QUIZ_LTI_SECRET")
    assert launch.post(launch.form(secret=placeholder)).status_code == 503
    # ... nor when someone copies it into the configuration.
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET", placeholder)
    assert launch.post(launch.form(secret=placeholder)).status_code == 503


def test_launch_is_refused_when_the_id_key_is_not_set(launch, monkeypatch):
    monkeypatch.delenv("AI_QUIZ_ID_KEY")

    assert launch.post(launch.form()).status_code == 503


def test_an_existing_session_stops_working_when_the_id_key_disappears(client, launch, monkeypatch):
    token = launch.token()
    monkeypatch.delenv("AI_QUIZ_ID_KEY")

    assert session_of(client, token).status_code == 503


def test_a_missing_setting_is_logged_by_name_and_never_by_value(launch, monkeypatch, caplog):
    monkeypatch.delenv("AI_QUIZ_ID_KEY")

    with caplog.at_level(logging.WARNING):
        launch.post(launch.form())

    assert "AI_QUIZ_ID_KEY" in caplog.text
    assert SECRET not in caplog.text
    assert ID_KEY not in caplog.text


# ── A2: the local test route ────────────────────────────────────────────────

def test_test_route_does_not_exist_by_default(client):
    assert client.get(f"{BASE}/test", params={"role": "instructor"}).status_code == 404


@pytest.mark.parametrize("value", ["0", "true", "yes", "on", "11", " 1"])
def test_test_route_stays_closed_unless_the_flag_is_exactly_1(client, monkeypatch, value):
    monkeypatch.setenv("AI_QUIZ_DEV_TEST", value)

    assert client.get(f"{BASE}/test", params={"role": "instructor"}).status_code == 404


def test_test_route_gives_an_instructor_session_when_the_flag_is_on(client, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_DEV_TEST", "1")

    response = client.get(f"{BASE}/test", params={"role": "instructor"})

    assert response.status_code == 303
    assert response.headers["location"].startswith(f"{BASE}/instructor?token=")
    token = response.headers["location"].split("token=")[1]
    assert session_of(client, token).json()["is_instructor"] is True


def test_test_route_gives_a_learner_session_by_default_when_the_flag_is_on(client, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_DEV_TEST", "1")

    response = client.get(f"{BASE}/test")

    assert response.headers["location"].startswith(f"{BASE}/student?token=")
    token = response.headers["location"].split("token=")[1]
    assert session_of(client, token).json()["is_instructor"] is False


def test_test_route_is_refused_when_the_tool_is_not_configured(client, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_DEV_TEST", "1")
    monkeypatch.delenv("AI_QUIZ_LTI_SECRET")

    assert client.get(f"{BASE}/test").status_code == 503


# ── Inherited from the shared LTI code, not fixed here ──────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="Security report finding #17: UltiR/lti_common.py checks the timestamp but never "
           "stores the nonce, so a signed launch can be replayed for ten minutes. Shared code; "
           "to be fixed in its own PR. When that lands this test passes and the marker goes.",
)
def test_the_same_signed_launch_cannot_be_used_twice(launch):
    form = launch.form()

    assert launch.post(form).status_code == 303
    assert launch.post(form).status_code == 403
