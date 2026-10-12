"""The tool looks like the other nine UltiR tools, and still passes what it passed before.

The common look: a navy band with the trail "UltiR › Tool", the tool's name, and "user — course";
a light page, white cards with round corners, borderless buttons in the accent colour. What the tool
keeps of its own: real buttons and labels, a visible focus, texts dark enough to read, two languages.
"""

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from .test_browser import answer_all, approve_all_and_publish, draft, upload  # noqa: E402

NAVY = "rgb(45, 56, 118)"          # #2D3876, the band of seven of the nine tools
PAGE = "rgb(248, 250, 252)"        # #f8fafc
TEXT = "rgb(30, 41, 59)"           # #1e293b
LINE = "rgb(226, 232, 240)"        # #e2e8f0
BOOK_FONTS = ("Iowan", "Palatino", "Georgia", "Book Antiqua")
RULE_RED = "rgb(194, 65, 58)"      # the margin rule of the old question sheet


def style(page, selector, *properties):
    return page.evaluate("""([selector, properties]) => { const s = getComputedStyle(document.querySelector(selector));
                            return properties.map(p => s.getPropertyValue(p)); }""", [selector, list(properties)])


def one_line(locator) -> str:
    return " ".join(locator.inner_text().split())


# ── The band ────────────────────────────────────────────────────────────────

def test_the_instructor_page_has_the_band_of_the_family(site):
    page = site.instructor(name="Synthetic Teacher", context_title="Computer Vision (synthetic)")

    assert style(page, "header.band", "background-color") == [NAVY]
    assert one_line(page.locator("header.band nav.trail")) == "UltiR › AI Quiz Generator › Instructor"
    expect(page.locator("header.band nav.trail a")).to_have_attribute("href", "/ultir")
    assert style(page, "header.band h1", "font-size", "font-weight", "color") == ["18px", "800", "rgb(255, 255, 255)"]
    assert one_line(page.locator("#session")) == "Synthetic Teacher — Computer Vision (synthetic)"
    expect(page.locator("#lang-switch")).to_be_visible()             # the language button stays


def test_the_student_page_has_the_same_band_without_the_instructor_item(site):
    page = site.student(name="Synthetic Student", context_title="Computer Vision (synthetic)")

    assert style(page, "header.band", "background-color") == [NAVY]
    assert one_line(page.locator("header.band nav.trail")) == "UltiR › AI Quiz Generator"
    assert one_line(page.locator("#session")) == "Synthetic Student — Computer Vision (synthetic)"


def test_the_trail_keeps_ultir_and_instructor_as_they_are_in_spanish(site):
    page = site.instructor(name="Synthetic Teacher", context_title="Visión por Computador")

    page.locator("#lang-switch").click()

    trail = one_line(page.locator("header.band nav.trail"))
    assert trail.startswith("UltiR › ") and trail.endswith(" › Instructor")
    assert one_line(page.locator("#session")) == "Synthetic Teacher — Visión por Computador"


def test_the_who_line_of_a_launch_without_a_name_is_the_course_alone(site):
    page = site.student(name="", context_title="Computer Vision (synthetic)")

    assert one_line(page.locator("#session")) == "Computer Vision (synthetic)"


# ── Page, cards, buttons ────────────────────────────────────────────────────

def test_page_cards_and_buttons_have_the_colours_and_shapes_of_the_family(site):
    page = site.instructor()

    assert style(page, "body", "background-color", "color") == [PAGE, TEXT]
    assert style(page, "#upload-form", "background-color", "border-top-color", "border-top-left-radius") == \
        ["rgb(255, 255, 255)", LINE, "12px"]
    assert style(page, "#upload-button", "background-color", "color", "border-top-width", "border-top-left-radius",
                 "font-size", "font-weight") == [NAVY, "rgb(255, 255, 255)", "0px", "8px", "14px", "600"]
    upload(page)
    quiet = page.locator("#documents button").first                   # "Delete" in the list: a secondary button
    assert quiet.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color, getComputedStyle(e).borderTopWidth]") \
        == [LINE, "rgb(71, 85, 105)", "0px"]


def test_questions_are_set_in_the_page_font_and_have_no_red_rule(site):
    """Decided 2026-10-11: the serif question sheet and its red margin rule go."""
    page = site.instructor()
    upload(page)
    draft(page)
    approve_all_and_publish(page)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    answer_all(student, 0)
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#score")).to_be_visible()

    for view in (page, student):
        fonts = view.evaluate("() => [...new Set([...document.querySelectorAll('body *')].map(e => getComputedStyle(e).fontFamily))]")
        assert [f for f in fonts if any(book in f for book in BOOK_FONTS)] == []
        borders = view.evaluate("""() => [...document.querySelectorAll('.sheet, .sheet-mark, .paper')].flatMap(e => {
            const s = getComputedStyle(e); return [s.borderLeftColor, s.borderRightColor, s.borderBottomColor]; })""")
        assert borders and RULE_RED not in borders


# ── The info page ───────────────────────────────────────────────────────────

def test_the_info_page_is_laid_out_like_the_newer_info_pages(site):
    page = site.open("/info")

    assert page.title() == "AI Quiz Generator — Info"
    assert style(page, "header.band", "background-color") == [NAVY]
    assert one_line(page.locator("header.band nav.trail")) == "UltiR › AI Quiz Generator"
    expect(page.locator("header.band h1")).to_have_text("AI Quiz Generator")
    expect(page.locator("header.band .sub")).to_contain_text("practice quizzes")      # one line saying what the tool is
    assert page.locator("main section.card > h2").all_inner_texts() == [
        "What this tool does", "About the AI", "For students", "For teachers", "Moodle setup (administrator)", "Status"]
    assert style(page, "main section.card", "border-top-left-radius", "background-color") == ["12px", "rgb(255, 255, 255)"]
    expect(page.locator("footer")).to_contain_text("UltiR")

    page.locator("#lang-switch").click()

    assert page.title().endswith("— Información")
    assert page.locator("main section.card > h2").all_inner_texts()[2:4] == ["Para estudiantes", "Para docentes"]


def test_the_page_for_an_ended_session_has_the_band_too(site):
    page = site.open("/student", "0" * 64)

    assert style(page, "header.band", "background-color") == [NAVY]
    assert one_line(page.locator("header.band nav.trail")) == "UltiR › AI Quiz Generator"


# ── What the tool passed before must still pass ─────────────────────────────

TEXTS = """() => {
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); const p = m[1].split(',').map(Number);
                       return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const over = (top, under) => ({r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a),
                                 b: top.b * top.a + under.b * (1 - top.a), a: 1});
  const part = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const light = c => 0.2126 * part(c.r) + 0.7152 * part(c.g) + 0.0722 * part(c.b);
  const behind = el => { const layers = [];
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor);
      if (c.a > 0) { layers.push(c); if (c.a === 1) break; } }
    return layers.reverse().reduce((bg, c) => over(c, bg), {r: 255, g: 255, b: 255, a: 1}); };
  const found = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent.trim(), el = node.parentElement;
    if (!text || !el || el.closest('[hidden], script, style, :disabled')) continue;
    const s = getComputedStyle(el), box = el.getBoundingClientRect();
    if (s.visibility === 'hidden' || !box.width || !box.height) continue;
    let opacity = 1;
    for (let e = el; e; e = e.parentElement) opacity *= Number(getComputedStyle(e).opacity);
    const bg = behind(el), ink = parse(s.color), fg = over({r: ink.r, g: ink.g, b: ink.b, a: ink.a * opacity}, bg);
    const a = light(fg), b = light(bg);
    found.push({text: text.slice(0, 40), contrast: Math.round((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) * 100) / 100,
                size: parseFloat(s.fontSize)});
  }
  return found;
}"""


def hard_to_read(page) -> list[dict]:
    """Every visible piece of text that is below 4.5 : 1 against what is behind it, or smaller than 12 px."""
    texts = page.evaluate(TEXTS)
    assert len(texts) > 5
    return [t for t in texts if t["contrast"] < 4.5 or t["size"] < 12]


def small_buttons(page) -> list[str]:
    return page.evaluate("""() => [...document.querySelectorAll('button')].filter(b => b.getBoundingClientRect().height > 0)
        .filter(b => b.getBoundingClientRect().height < 38).map(b => b.outerHTML.slice(0, 80))""")


def test_every_text_can_be_read_and_every_button_is_large_enough_on_every_page(site):
    teacher = site.instructor(name="Synthetic Teacher", context_title="Computer Vision (synthetic)")
    assert hard_to_read(teacher) == []                               # empty overview
    upload(teacher)
    assert hard_to_read(teacher) == [] and small_buttons(teacher) == []   # with a document in the list
    draft(teacher)
    assert hard_to_read(teacher) == [] and small_buttons(teacher) == []   # review, drafts
    teacher.locator(".sheet").nth(2).get_by_role("button", name="Reject", exact=True).click()
    expect(teacher.locator(".sheet").nth(2)).to_have_attribute("data-status", "rejected")
    for i in range(2):
        teacher.locator(".sheet").nth(i).get_by_role("button", name="Approve", exact=True).click()
        expect(teacher.locator(".sheet").nth(i)).to_have_attribute("data-status", "approved")
    teacher.get_by_role("button", name="Publish approved questions").click()
    expect(teacher.locator("#status")).to_contain_text("Published as version 1")
    assert hard_to_read(teacher) == []                               # review: approved, rejected, the "published" notice

    student = site.student(name="Synthetic Student")
    assert hard_to_read(student) == [] and small_buttons(student) == []   # list of quizzes
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(2)
    assert hard_to_read(student) == [] and small_buttons(student) == []   # a quiz being taken
    answer_all(student, 0)                                           # option A: wrong in every fake question
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#score")).to_be_visible()
    assert hard_to_read(student) == [] and small_buttons(student) == []   # results, with "not correct"

    for path, token in (("/info", ""), ("/student", "0" * 64), ("/instructor", site.token("Learner"))):
        public = site.open(path, token)                              # info; session ended; not an instructor
        assert hard_to_read(public) == [] and small_buttons(public) == []


@pytest.mark.parametrize("path", ["/instructor", "/student", "/info"])
def test_the_first_tab_stop_is_the_skip_link_and_every_stop_shows_where_it_is(site, path):
    page = site.open(path, site.token("Instructor") if path != "/info" else "")

    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip"
    for _ in range(8):
        if page.evaluate("document.activeElement === document.body"):
            break                                                    # past the last stop of a short page
        outline = page.evaluate("""() => { const s = getComputedStyle(document.activeElement);
                                   return [s.outlineStyle, parseFloat(s.outlineWidth)]; }""")
        assert outline[0] == "solid" and outline[1] >= 2, page.evaluate("document.activeElement.outerHTML.slice(0, 80)")
        page.keyboard.press("Tab")


@pytest.mark.parametrize("path", ["/instructor", "/student", "/info"])
def test_a_page_has_one_h1_one_main_and_one_place_for_messages(site, path):
    page = site.open(path, site.token("Instructor") if path != "/info" else "")

    expect(page.locator("h1")).to_have_count(1)
    expect(page.locator("main")).to_have_count(1)
    if path != "/info":
        expect(page.locator('[role="status"][aria-live="polite"]')).to_have_count(1)
