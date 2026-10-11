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


# Stricter than the platform's own policy, which allows inline scripts and styles. Every page
# is served with this, and any violation fails the test: the tool must not depend on inline code.
STRICT_POLICY = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
                 "connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'self'")

RECORD_VIOLATIONS = """window.__blocked = [];
document.addEventListener('securitypolicyviolation', function (e) {
  window.__blocked.push(e.violatedDirective + ' blocked ' + (e.blockedURI || 'inline') + ' in ' +
                        (e.sourceFile || 'the page') + ':' + e.lineNumber);
});"""


@pytest.fixture(scope="session")
def live_server():
    import httpx
    import uvicorn
    from fastapi import FastAPI

    from UltiR.ai_quiz.lti_provider import router

    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def strict_policy(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = STRICT_POLICY
        return response

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
        self.contexts, self.pages, self.problems = [], [], []

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
        context.add_init_script(RECORD_VIOLATIONS)
        page = context.new_page()
        page.on("dialog", lambda dialog: (self.problems.append(f"dialog: {dialog.message}"), dialog.dismiss()))
        page.on("pageerror", lambda error: self.problems.append(f"script error: {error}"))
        # The browser also reports a policy violation on the console. (Other console errors, such as
        # the 4xx answers some tests provoke on purpose, are not problems.)
        page.on("console", lambda message: self.problems.append(f"console: {message.text[:200]}")
                if "Content Security Policy" in message.text or message.text.startswith("Refused to") else None)
        response = page.goto(f"{self.url}{BASE}{path}" + (f"?token={token}" if token else ""))
        assert response.headers.get("content-security-policy") == STRICT_POLICY
        page.wait_for_load_state("networkidle")
        self.pages.append(page)
        return page

    def blocked_by_policy(self) -> list[str]:
        """What the strict policy blocked on the pages that are still open."""
        return [f"{page.url.split('?')[0]}: {v}" for page in self.pages if not page.is_closed()
                for v in page.evaluate("window.__blocked || []")]

    def instructor(self, **extra):
        return self.open("/instructor", self.token("Instructor", user="teacher-1", **extra))

    def student(self, user="student-1", **extra):
        return self.open("/student", self.token("Learner", user=user, **extra))


@pytest.fixture
def site(live_server, chromium):
    site = Site(live_server, chromium)
    yield site
    blocked = site.blocked_by_policy()
    for context in site.contexts:
        context.close()
    assert blocked == []
    assert site.problems == []
