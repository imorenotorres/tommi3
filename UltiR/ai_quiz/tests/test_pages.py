"""Pages, the session endpoint and the static assets."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from .conftest import BASE


# ── Public entry points ─────────────────────────────────────────────────────

def test_opening_the_tool_url_in_a_browser_leads_to_the_info_page(client):
    response = client.get(BASE)

    assert response.status_code == 303
    assert response.headers["location"] == f"{BASE}/info"


def test_info_page_is_public_and_still_loads_when_the_tool_is_not_configured(client, monkeypatch):
    monkeypatch.delenv("AI_QUIZ_LTI_SECRET")
    monkeypatch.delenv("AI_QUIZ_ID_KEY")

    response = client.get(f"{BASE}/info")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


# ── Role pages ──────────────────────────────────────────────────────────────

def test_instructor_page_loads_for_an_instructor(client, launch):
    response = client.get(f"{BASE}/instructor", params={"token": launch.token(role="Instructor")})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_student_page_loads_for_a_learner_and_for_an_instructor(client, launch):
    for role in ("Learner", "Instructor"):
        response = client.get(f"{BASE}/student", params={"token": launch.token(role=role)})
        assert response.status_code == 200, role


# ── Session endpoint ────────────────────────────────────────────────────────

def test_session_endpoint_describes_the_launch(client, launch):
    token = launch.token(role="Instructor", course="course-A",
                         name="Synthetic Teacher", context_title="Computer Vision (synthetic)")

    body = client.get(f"{BASE}/api/session", params={"token": token}).json()

    assert body == {
        "name": "Synthetic Teacher",
        "course_name": "Computer Vision (synthetic)",
        "is_instructor": True,
        "reading_modes": {"text": True, "full": False},
    }


def test_session_endpoint_gives_out_no_email_and_no_ids(client, launch):
    token = launch.token(user="user-42", course="course-A", email="someone@example.invalid")

    text = client.get(f"{BASE}/api/session", params={"token": token}).text

    assert "someone@example.invalid" not in text
    assert "user-42" not in text
    assert "course-A" not in text
    assert token not in text


def test_each_token_sees_its_own_course(client, launch):
    token_a = launch.token(course="course-A", context_title="Course A")
    token_b = launch.token(course="course-B", context_title="Course B")

    assert client.get(f"{BASE}/api/session", params={"token": token_a}).json()["course_name"] == "Course A"
    assert client.get(f"{BASE}/api/session", params={"token": token_b}).json()["course_name"] == "Course B"


# ── Static assets ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, content_type", [
    ("strings.js", "text/javascript"),
    ("app.js", "text/javascript"),
    ("info.js", "text/javascript"),
    ("instructor.js", "text/javascript"),
    ("student.js", "text/javascript"),
    ("app.css", "text/css"),
])
def test_assets_are_served_with_their_content_type(client, name, content_type):
    response = client.get(f"{BASE}/assets/{name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


@pytest.mark.parametrize("name", [
    "nothing.js",
    "info.html",                    # exists in static/, but is not an asset
    "../lti_provider.py",
    "..%2Flti_provider.py",
    "%2e%2e/%2e%2e/lti_common.py",
    "strings.js/../../config.py",
    "/etc/passwd",
    "",
])
def test_asset_route_serves_nothing_outside_its_list(client, name):
    assert client.get(f"{BASE}/assets/{name}").status_code == 404


def load_strings(client) -> dict:
    """strings.js is `window.AI_QUIZ_STRINGS = {...};` with a JSON object literal."""
    source = client.get(f"{BASE}/assets/strings.js").text
    return json.loads(source[source.index("{"): source.rindex("}") + 1])


MODULE_DIR = Path(__file__).resolve().parents[1]


# ── No inline code in the pages ─────────────────────────────────────────────

class InlineCodeFinder(HTMLParser):
    """Collects everything in a page that a policy without 'unsafe-inline' would block."""

    def __init__(self):
        super().__init__()
        self.found: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        attrs = dict(attrs)
        if tag == "script":
            self._in_script = True
            if not attrs.get("src"):
                self.found.append(f"line {line}: <script> without src")
        if tag == "style":
            self.found.append(f"line {line}: <style> element")
        for name, value in attrs.items():
            if name == "style":
                self.found.append(f"line {line}: style attribute on <{tag}>")
            elif name.startswith("on"):
                self.found.append(f"line {line}: {name} handler on <{tag}>")
            elif name in ("href", "src", "action", "formaction") and (value or "").strip().lower().startswith("javascript:"):
                self.found.append(f"line {line}: javascript: URL in {name} on <{tag}>")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script and data.strip():
            self.found.append(f"line {self.getpos()[0]}: script code inside the page")


def inline_code_in(html: str) -> list[str]:
    finder = InlineCodeFinder()
    finder.feed(html)
    return finder.found


PAGES = sorted(p.name for p in (MODULE_DIR / "static").glob("*.html"))


def test_the_tool_has_pages_to_check():
    assert PAGES == ["info.html", "instructor.html", "student.html"]


@pytest.mark.parametrize("page", PAGES)
def test_a_page_has_no_inline_script_style_or_event_handler(page):
    """So the pages keep working if the platform's policy stops allowing inline code."""
    html = (MODULE_DIR / "static" / page).read_text(encoding="utf-8")

    assert inline_code_in(html) == []


@pytest.mark.parametrize("html, expected", [
    ("<script>go()</script>", ["<script> without src", "script code inside the page"]),
    ('<script src="/a.js">go()</script>', ["script code inside the page"]),
    ('<p style="color:red">x</p>', ["style attribute on <p>"]),
    ("<style>p{}</style>", ["<style> element"]),
    ('<button onclick="go()">x</button>', ["onclick handler on <button>"]),
    ('<body onload="go()">', ["onload handler on <body>"]),
    ('<a href=" JavaScript:go()">x</a>', ["javascript: URL in href on <a>"]),
    ('<script src="/a.js"></script><link rel="stylesheet" href="/a.css"><p class="x">ok</p>', []),
])
def test_the_inline_code_check_itself_finds_what_it_should(html, expected):
    found = inline_code_in(html)

    assert len(found) == len(expected)
    assert all(any(e in f for f in found) for e in expected)


def test_every_text_key_the_pages_use_is_defined(client):
    strings = load_strings(client)["en"]
    used = set()
    for path in sorted((MODULE_DIR / "static").glob("*")):
        if path.suffix in (".html", ".js") and path.name != "strings.js":
            source = path.read_text(encoding="utf-8")
            used |= set(re.findall(r'data-i18n(?:-label)?="([a-z0-9_]+)"', source))
            used |= set(re.findall(r"""\bt\(\s*'([a-z0-9_]+)'\s*[,)]""", source))   # not 'prefix_' + variable
            # keys passed around as plain strings: 'review_saved', 'gen_done', ...
            used |= {k for k in re.findall(r"'([a-z]+_[a-z0-9_]+)'", source) if k in strings}

    assert used, "found no text keys in the pages at all"
    assert sorted(used - set(strings)) == []


def test_every_error_code_the_server_can_send_has_a_text_in_both_languages(client):
    strings = load_strings(client)
    codes = set()
    for path in sorted(MODULE_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        codes |= set(re.findall(r'(?:_refuse|UploadRejected|QuizError|GenerationFailed|AttemptError)\(\s*\d+,\s*"([a-z_]+)"', source))
        codes |= set(re.findall(r'Unreadable\("([a-z_]+)"\)', source))

    assert len(codes) > 20
    assert sorted(c for c in codes if f"err_{c}" not in strings["en"] or f"err_{c}" not in strings["es"]) == []


def test_every_interface_text_exists_in_spanish_and_in_english(client):
    strings = load_strings(client)

    assert set(strings) == {"en", "es"}
    assert set(strings["en"]) == set(strings["es"])
    assert strings["en"], "no interface texts at all"
    untranslated = sorted(k for k in strings["en"] if not strings["en"][k].strip() or not strings["es"][k].strip())
    assert untranslated == []
