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


# ── A page asked for without a session ──────────────────────────────────────
# Seen from Moodle on 2026-10-11: after a restart of the server, a reload showed the bare text
# {"detail":"Sesion no valida. Accede desde Moodle."}. The pages now answer with a page of the tool.

def is_the_tools_own_page(response) -> bool:
    return (response.status_code == 401
            and response.headers["content-type"].startswith("text/html")
            and 'data-i18n="expired_title"' in response.text
            and '"detail"' not in response.text
            and response.headers.get("cache-control") == "no-store")


@pytest.mark.parametrize("path", ["/instructor", "/student"])
@pytest.mark.parametrize("params", [None, {"token": ""}, {"token": "0" * 64}])
def test_a_page_opened_without_a_session_is_a_page_of_the_tool_not_bare_json(client, path, params):
    assert is_the_tools_own_page(client.get(f"{BASE}{path}", params=params))


@pytest.mark.parametrize("path, role", [("/instructor", "Instructor"), ("/student", "Learner")])
def test_a_reload_after_the_session_has_ended_is_a_page_of_the_tool(client, launch, path, role):
    from UltiR.ai_quiz.lti_provider import sessions
    token = launch.token(role=role)
    assert client.get(f"{BASE}{path}", params={"token": token}).status_code == 200

    sessions.revoke(token)                          # what a restart of the server does to every session

    assert is_the_tools_own_page(client.get(f"{BASE}{path}", params={"token": token}))


def test_the_page_for_an_ended_session_holds_nothing_of_the_tool_but_its_name(client):
    text = client.get(f"{BASE}/instructor").text

    for private in ("upload", "api/", "token"):
        assert private not in text.lower()


def test_the_api_still_answers_in_json_when_there_is_no_session(client):
    response = client.get(f"{BASE}/api/session", params={"token": "0" * 64})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")


def test_a_learner_on_the_instructor_page_is_refused_not_told_the_session_ended(client, launch):
    response = client.get(f"{BASE}/instructor", params={"token": launch.token(role="Learner")})

    assert response.status_code == 403
    assert "expired_title" not in response.text


@pytest.mark.parametrize("role", ["Learner", "urn:lti:role:ims/lis/TeachingAssistant", ""])
def test_who_is_not_an_instructor_gets_a_page_of_the_tool_on_the_instructor_address(client, launch, role):
    """Until 2026-10-11 the answer was the bare text {"detail":"Instructors only"}."""
    response = client.get(f"{BASE}/instructor", params={"token": launch.token(role=role)})

    assert response.status_code == 403                      # still refused
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-i18n="denied_title"' in response.text
    assert '"detail"' not in response.text
    assert response.headers.get("cache-control") == "no-store"
    for private in ("upload", "api/", "generate"):          # nothing of the instructor's page comes with it
        assert private not in response.text.lower()


def test_the_instructor_api_still_answers_a_learner_in_json(client, launch):
    response = client.get(f"{BASE}/api/documents", params={"token": launch.token(role="Learner")})

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/json")


def test_an_instructor_is_not_shown_the_page_for_learners(client, launch):
    response = client.get(f"{BASE}/instructor", params={"token": launch.token(role="Instructor")})

    assert response.status_code == 200 and "denied_title" not in response.text


@pytest.mark.parametrize("language, words", [("en", ("instructors", "student")), ("es", ("docentes", "estudiante"))])
def test_the_page_for_learners_says_whose_page_it_is_and_where_to_go(client, language, words):
    strings = load_strings(client)[language]

    assert all(word in strings["denied_title"] + " " + strings["denied_text"] for word in words)
    assert strings["denied_link"]


def test_a_page_of_an_unconfigured_tool_says_so_and_not_that_the_session_ended(client, launch, monkeypatch):
    token = launch.token()
    monkeypatch.delenv("AI_QUIZ_ID_KEY")

    assert client.get(f"{BASE}/instructor", params={"token": token}).status_code == 503


@pytest.mark.parametrize("language, words", [("en", ("Moodle", "open the activity again")),
                                             ("es", ("Moodle", "abre de nuevo la actividad"))])
def test_both_messages_about_an_ended_session_say_to_open_the_activity_again(client, language, words):
    strings = load_strings(client)[language]

    for key in ("expired_text", "error_session"):
        assert all(word in strings[key] for word in words), key


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
    ("expired.js", "text/javascript"),
    ("denied.js", "text/javascript"),
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
    assert PAGES == ["denied.html", "expired.html", "info.html", "instructor.html", "student.html"]


class HeadingFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.levels: list[int] = []

    def handle_starttag(self, tag, attrs):
        if re.fullmatch(r"h[1-6]", tag):
            self.levels.append(int(tag[1]))


def heading_levels(html: str) -> list[int]:
    finder = HeadingFinder()
    finder.feed(html)
    return finder.levels


@pytest.mark.parametrize("page", PAGES)
def test_the_headings_of_a_page_go_down_one_level_at_a_time(page):
    """One h1, the tool's name, first; after that no level is skipped on the way down."""
    levels = heading_levels((MODULE_DIR / "static" / page).read_text(encoding="utf-8"))

    assert levels[0] == 1 and levels.count(1) == 1
    assert [(a, b) for a, b in zip(levels, levels[1:]) if b > a + 1] == []


def test_the_heading_check_itself_sees_a_skipped_level():
    assert heading_levels("<h1>a</h1><h3>b</h3><h2>c</h2>") == [1, 3, 2]


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
        codes |= set(re.findall(r'(?:_refuse|UploadRejected|QuizError|GenerationFailed|AttemptError|PracticeError|ExerciseFailed|AnswerRefused)\(\s*\d+,\s*"([a-z_]+)"', source))
        codes |= set(re.findall(r'Unreadable\("([a-z_]+)"\)', source))
        codes |= set(re.findall(r'_fail\(course_id, doc_id, "([a-z_]+)"\)', source))    # why a reading failed
        codes |= set(re.findall(r'error="([a-z_]+)"', source))

    assert len(codes) > 20
    assert sorted(c for c in codes if f"err_{c}" not in strings["en"] or f"err_{c}" not in strings["es"]) == []


@pytest.mark.parametrize("language", ["en", "es"])
def test_the_formula_warning_is_two_sentences_and_names_the_page_to_check(client, language):
    strings = load_strings(client)[language]
    with_page, without = strings["flag_math"], strings["flag_math_no_page"]

    for text in (with_page, without):
        assert len(re.findall(r"\.(?=\s|$)", text)) == 2, text          # two sentences, no more
    assert "{n}" in with_page and "{n}" not in without                  # the page of the passage, when there is one
    assert with_page.split(":")[0] == without.split(":")[0]             # the same text up to what to check it against
    for word in {"en": ("read by machine", "bold", "function names"),
                 "es": ("leídas por una máquina", "negrita", "nombres de funciones")}[language]:
        assert word in with_page and word in without


def test_every_interface_text_exists_in_spanish_and_in_english(client):
    strings = load_strings(client)

    assert set(strings) == {"en", "es"}
    assert set(strings["en"]) == set(strings["es"])
    assert strings["en"], "no interface texts at all"
    untranslated = sorted(k for k in strings["en"] if not strings["en"][k].strip() or not strings["es"][k].strip())
    assert untranslated == []
