"""Test harness for the AI Quiz tool.

Mounts only this tool's router on a bare FastAPI app (importing web/app.py
would load every agent). Launches go through the real signed LTI path.
"""

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


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """A fully configured tool, with the local test route off (the default)."""
    monkeypatch.setenv("AI_QUIZ_LTI_KEY", KEY)
    monkeypatch.setenv("AI_QUIZ_LTI_SECRET", SECRET)
    monkeypatch.setenv("AI_QUIZ_ID_KEY", ID_KEY)
    monkeypatch.delenv("AI_QUIZ_DEV_TEST", raising=False)


@pytest.fixture
def client():
    from UltiR.ai_quiz.lti_provider import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, follow_redirects=False)


class Launcher:
    def __init__(self, client):
        self.client = client

    def form(self, role="Instructor", course="course-A", user="user-1", *, key=KEY, secret=SECRET, **extra):
        return sign_launch(LAUNCH_URL, key, secret, roles=role, context_id=course, user_id=user, **extra)

    def post(self, form):
        return self.client.post(BASE, data=form)

    def token(self, role="Instructor", course="course-A", user="user-1", **extra):
        response = self.post(self.form(role, course, user, **extra))
        assert response.status_code == 303, response.text
        return parse_qs(urlparse(response.headers["location"]).query)["token"][0]


@pytest.fixture
def launch(client):
    return Launcher(client)
