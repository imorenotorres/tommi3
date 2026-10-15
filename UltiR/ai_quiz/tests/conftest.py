"""Test harness for the AI Quiz tool.

Mounts only this tool's router on a bare FastAPI app (importing web/app.py
would load every agent). Launches go through the real signed LTI path.
"""

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for _p in (REPO_ROOT, REPO_ROOT / "web"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from .lti_sign import sign_launch  # noqa: E402

BASE = "/lti/ai-quiz"
LAUNCH_URL = "http://testserver" + BASE

# Throwaway values that exist only in the test process.
KEY = "ai_quiz_test_key"
SECRET = "test-only-lti-secret"
ID_KEY = "test-only-id-key"
# A second Moodle installation has a key and a secret of its own.
KEY_2 = "second_moodle_test_key"
SECRET_2 = "test-only-lti-secret-of-the-second-moodle"


def cid(course: str, key: str = KEY) -> str:
    """The id under which the tool keeps the course that Moodle calls `course`: the consumer key is part of it."""
    return f"{key}:{course}"


@pytest.fixture(autouse=True)
def configured(monkeypatch, tmp_path):
    """A fully configured tool, the local test route off (the default), data in a temp folder."""
    monkeypatch.setenv("AI_QUIZ_LTI_KEY", KEY)
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET", SECRET)
    monkeypatch.setenv("AI_QUIZ_ID_KEY", ID_KEY)
    monkeypatch.delenv("AI_QUIZ_DEV_TEST", raising=False)
    monkeypatch.delenv("AI_QUIZ_PRACTICE_MODEL", raising=False)     # off unless a test switches it on
    for name in [n for n in os.environ if n.startswith(("AI_QUIZ_LTI_KEY_", "AI_QUIZ_LTI_SECRET_"))]:
        monkeypatch.delenv(name)                     # one Moodle unless a test adds a second
    for name in ("AI_QUIZ_DOCLING_PYTHON", "AI_QUIZ_DOCLING_MODELS", "AI_QUIZ_DOCLING_DEVICE"):
        monkeypatch.delenv(name, raising=False)      # no full reading unless a test sets it up
    monkeypatch.setenv("AI_QUIZ_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """Every test talks to the fake model. Nothing in the suite can reach a real one."""
    from UltiR.ai_quiz import generation

    from .fake_llm import FakeLLM

    fake = FakeLLM()
    monkeypatch.setattr(generation, "call_model", fake)
    return fake


@pytest.fixture(autouse=True)
def no_job_outlives_its_test():
    """A reading job still running when a test ends would write into the next test's folder."""
    yield
    from UltiR.ai_quiz import jobs

    jobs.stop_all()


@pytest.fixture
def client():
    from UltiR.ai_quiz.lti_provider import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, follow_redirects=False)


class Launcher:
    """Launches as one Moodle installation would send them: signed with that installation's key and secret."""

    def __init__(self, client, key=KEY, secret=SECRET):
        self.client, self.key, self.secret = client, key, secret

    def form(self, role="Instructor", course="course-A", user="user-1", *, key=None, secret=None, **extra):
        return sign_launch(LAUNCH_URL, self.key if key is None else key, self.secret if secret is None else secret,
                           roles=role, context_id=course, user_id=user, **extra)

    def post(self, form):
        return self.client.post(BASE, data=form)

    def token(self, role="Instructor", course="course-A", user="user-1", **extra):
        response = self.post(self.form(role, course, user, **extra))
        assert response.status_code == 303, response.text
        return parse_qs(urlparse(response.headers["location"]).query)["token"][0]


@pytest.fixture
def launch(client):
    return Launcher(client)


@pytest.fixture
def second_moodle(client, monkeypatch):
    """A second Moodle installation is registered with the tool, with a key and a secret of its own."""
    monkeypatch.setenv("AI_QUIZ_LTI_KEY_2", KEY_2)
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET_2", SECRET_2)
    return Launcher(client, KEY_2, SECRET_2)
