"""Browser tests: a real HTTP server in this process, driven by headless Chromium.

The server is the tool's router on a bare FastAPI app, exactly as in the other
tests, so the fake model, the temp data folder and the throwaway settings of
the parent conftest apply here too. Sessions come from real signed launches.

Needs the dev-only packages `playwright` (and its Chromium). Without them
these tests are skipped.
"""

import socket
import threading
import time
from urllib.parse import parse_qs, urlparse

import pytest

from ..conftest import BASE, KEY, SECRET
from ..lti_sign import sign_launch


@pytest.fixture(scope="session")
def live_server():
    import httpx
    import uvicorn
    from fastapi import FastAPI

    from UltiR.ai_quiz.lti_provider import router

    app = FastAPI()
    app.include_router(router)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}{BASE}/info", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        raise RuntimeError("test server did not start")
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def chromium():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


class Site:
    """Opens pages of the tool as a given person, and fails the test on any dialog or script error."""

    def __init__(self, url, browser):
        self.url, self.browser = url, browser
        self.contexts, self.problems = [], []

    def token(self, role, course="course-A", user="user-1", **extra) -> str:
        import httpx

        launch_url = self.url + BASE
        form = sign_launch(launch_url, KEY, SECRET, roles=role, context_id=course, user_id=user, **extra)
        response = httpx.post(launch_url, data=form, follow_redirects=False)
        assert response.status_code == 303, response.text
        return parse_qs(urlparse(response.headers["location"]).query)["token"][0]

    def open(self, path, token="", locale="en-GB"):
        context = self.browser.new_context(locale=locale)
        self.contexts.append(context)
        page = context.new_page()
        page.on("dialog", lambda dialog: (self.problems.append(f"dialog: {dialog.message}"), dialog.dismiss()))
        page.on("pageerror", lambda error: self.problems.append(f"script error: {error}"))
        page.goto(f"{self.url}{BASE}{path}" + (f"?token={token}" if token else ""))
        page.wait_for_load_state("networkidle")
        return page

    def instructor(self, **extra):
        return self.open("/instructor", self.token("Instructor", user="teacher-1", **extra))

    def student(self, user="student-1", **extra):
        return self.open("/student", self.token("Learner", user=user, **extra))


@pytest.fixture
def site(live_server, chromium):
    site = Site(live_server, chromium)
    yield site
    for context in site.contexts:
        context.close()
    assert site.problems == []
