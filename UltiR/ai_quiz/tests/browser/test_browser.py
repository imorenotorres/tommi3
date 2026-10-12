"""The pages in a real browser (rules A12 and A15), with the fake model behind the server."""

import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from ..fake_llm import question, sources_in  # noqa: E402
from ..pdfs import GARBLED_PASSAGE, evaluation_pdf, handout_pdf  # noqa: E402
from ..readers import SlowReader, install, install_recorded_docling  # noqa: E402

PAYLOAD = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>'


# ── Steps shared by the tests ───────────────────────────────────────────────

def upload(page, name="handout.pdf", data=None, mime="application/pdf"):
    page.set_input_files("#upload-file", files=[{"name": name, "mimeType": mime,
                                                 "buffer": handout_pdf() if data is None else data}])
    page.get_by_role("button", name="Upload document").click()
    expect(page.locator("#documents table")).to_be_visible()


def draft(page, count=3, title="Week 7"):
    page.fill("#gen-count", str(count))
    page.fill("#gen-title", title)
    page.get_by_role("button", name="Draft questions").click()
    expect(page.locator(".sheet")).to_have_count(count)


def approve_all_and_publish(page, count=3):
    for i in range(count):
        page.locator(".sheet").nth(i).get_by_role("button", name="Approve", exact=True).click()
        expect(page.locator(".sheet").nth(i)).to_have_attribute("data-status", "approved")
    page.get_by_role("button", name="Publish approved questions").click()
    expect(page.locator("#status")).to_contain_text("Published as version 1")


def published_by_instructor(site, **launch):
    page = site.instructor(**launch)
    upload(page)
    draft(page)
    approve_all_and_publish(page)
    return page


def answer_all(page, option_index):
    papers = page.locator("#quiz-view fieldset.paper")
    for i in range(papers.count()):
        papers.nth(i).get_by_role("radio").nth(option_index).check()


def no_markup_was_created(page):
    """Nothing from the payload became an element or ran."""
    assert page.evaluate("window.__pwned") is None
    assert page.locator("img").count() == 0
    assert page.evaluate("document.scripts.length") == 5          # the five script files of the page itself


def unlabelled_controls(page) -> list[str]:
    return page.evaluate("""() => Array.from(document.querySelectorAll('input, select, textarea, button'))
        .filter(e => !e.closest('[hidden]'))
        .filter(e => !((e.labels && e.labels.length) || e.getAttribute('aria-label')
                       || (e.tagName === 'BUTTON' && e.textContent.trim())))
        .map(e => e.outerHTML.slice(0, 90))""")


def focused(page) -> dict:
    return page.evaluate("""() => { const e = document.activeElement;
        return {tag: e.tagName, id: e.id, cls: e.className, type: e.type || '', text: (e.textContent || '').trim()}; }""")


def tab_to(page, wanted, limit=40):
    """Press Tab until `wanted(focused element)` is true. Fails if the element cannot be reached by keyboard."""
    for _ in range(limit):
        page.keyboard.press("Tab")
        if wanted(focused(page)):
            return
    raise AssertionError(f"not reachable with the Tab key within {limit} presses")


# ── The whole loop ──────────────────────────────────────────────────────────

def test_an_instructor_publishes_a_quiz_and_a_student_takes_it(site):
    page = site.instructor(context_title="Computer Vision (synthetic)", name="Synthetic Teacher")
    expect(page.locator("#course-name")).to_have_text("Computer Vision (synthetic)")
    expect(page.locator("header nav.trail")).to_contain_text("Instructor")

    upload(page)
    expect(page.locator("#documents")).to_contain_text("handout.pdf")
    draft(page, count=3, title="Week 7")
    expect(page.locator("#review-heading")).to_have_text("Week 7")
    expect(page.locator(".sheet-source").first).to_contain_text("handout.pdf, page 1")
    expect(page.locator("#questions")).not_to_contain_text("read by machine")     # no formula in this handout: no warning
    expect(page.locator("#publish-state")).to_contain_text("Not published.")

    first = page.locator(".sheet").first
    first.locator("textarea").first.fill("What does a local feature differ from?")
    first.get_by_role("button", name="Save changes").click()
    expect(page.locator(".sheet").first.locator(".sheet-mark")).to_contain_text("Edited")
    approve_all_and_publish(page)
    expect(page.locator("#publish-state")).to_contain_text("Published (version 1).")

    student = site.student(name="Synthetic Student")
    expect(student.locator("header nav.trail")).not_to_contain_text("Instructor")
    expect(student.locator("#quizzes")).to_contain_text("Week 7")
    expect(student.locator("#quizzes")).to_contain_text("Not tried yet")
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    expect(student.locator("#quiz-view")).to_contain_text("What does a local feature differ from?")
    answer_all(student, 1)                                   # option B is the key in every fake question
    student.get_by_role("button", name="Check my answers").click()

    expect(student.locator("#score")).to_have_text("3 of 3 correct")
    expect(student.locator("#results")).to_contain_text("From handout.pdf, page 2")
    expect(student.locator("#results")).to_contain_text("Why:")
    student.locator("#result-view [data-back]").click()
    expect(student.locator("#quizzes")).to_contain_text("1 tried, best 3 of 3")


def test_nothing_the_browser_receives_before_submitting_holds_the_key(site):
    published_by_instructor(site)
    received = []
    student = site.student()
    student.on("response", lambda r: received.append(r.text()) if "/api/" in r.url else None)
    student.reload()
    student.wait_for_load_state("networkidle")
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)

    everything = "\n".join(received) + student.content()

    assert len(received) >= 3                                  # session, list, quiz
    for private in ("correct_option_id", "Explanation", "excerpt", "handout.pdf"):
        assert private not in everything


# ── A12: nothing from the model, an upload or the launch becomes markup ─────

def test_markup_in_questions_documents_titles_and_names_is_shown_as_text(site, fake_llm):
    def hostile(messages):
        (sid, text), *_ = sources_in(messages).items()
        return json.dumps({"questions": [question(
            sid, text, 1,
            question=f"Which statement is right? {PAYLOAD}",
            options=[{"id": "A", "text": f"First {PAYLOAD}"}, {"id": "B", "text": "Second"},
                     {"id": "C", "text": "Third"}, {"id": "D", "text": "Fourth"}],
            explanation=f"Because {PAYLOAD}")]})
    fake_llm.queue(hostile)

    page = site.instructor(name=f"Teacher {PAYLOAD}", context_title=f"Course {PAYLOAD}")
    expect(page.locator("#user-name")).to_have_text(f"Teacher {PAYLOAD}")
    document_text = f"{PAYLOAD} is quoted in this handout as an example of text that must stay text in every page."
    upload(page, f"notes {PAYLOAD}.txt", document_text.encode("utf-8"), "text/plain")
    draft(page, count=1, title=f"Quiz {PAYLOAD}")

    sheet = page.locator(".sheet").first
    assert PAYLOAD in sheet.locator("textarea").first.input_value()
    # the located passage starts at its first letter, so the leading "<" is not part of it
    expect(sheet.locator(".sheet-source blockquote")).to_contain_text('onerror="window.__pwned=1"><script>')
    expect(page.locator("#review-heading")).to_have_text(f"Quiz {PAYLOAD}")
    no_markup_was_created(page)

    approve_all_and_publish(page, count=1)
    page.get_by_role("button", name="Back to documents and quizzes").click()
    expect(page.locator("#quizzes")).to_contain_text("<img src=x")
    expect(page.locator("#documents")).to_contain_text("script_.txt")     # the server had already cleaned the file name
    no_markup_was_created(page)

    student = site.student(name=f"Student {PAYLOAD}")
    expect(student.locator("#quizzes")).to_contain_text("<script>")
    no_markup_was_created(student)
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_contain_text("<img src=x")
    no_markup_was_created(student)
    answer_all(student, 0)
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#results")).to_contain_text("Because <img src=x")
    expect(student.locator("#results .cite")).to_contain_text("<script>")
    no_markup_was_created(student)


# ── A15: keyboard, labels, state not by colour alone ────────────────────────

def test_a_student_can_take_a_quiz_with_the_keyboard_alone(site):
    published_by_instructor(site)
    student = site.student()
    expect(student.locator("#quizzes table")).to_be_visible()

    student.keyboard.press("Tab")
    assert focused(student)["cls"] == "skip"                                  # first stop: skip to content
    tab_to(student, lambda e: e["tag"] == "BUTTON" and e["text"] == "Start")
    student.keyboard.press("Enter")
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    assert focused(student)["id"] == "quiz-heading"                           # focus follows the view

    for _ in range(3):
        tab_to(student, lambda e: e["type"] == "radio")
        student.keyboard.press("Space")
        student.keyboard.press("ArrowDown")                                   # move the choice from A to B
    tab_to(student, lambda e: e["id"] == "submit-button")
    student.keyboard.press("Enter")

    expect(student.locator("#score")).to_have_text("3 of 3 correct")
    assert focused(student)["id"] == "result-heading"


def test_results_are_stated_in_words_not_only_in_colour(site):
    published_by_instructor(site)
    student = site.student()
    student.locator("#quizzes button").first.click()
    papers = student.locator("#quiz-view fieldset.paper")
    papers.nth(0).get_by_role("radio").nth(1).check()        # right
    papers.nth(1).get_by_role("radio").nth(0).check()        # wrong; the third is left unanswered
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#status")).to_contain_text("Questions still unanswered: 1.")
    student.get_by_role("button", name="Check my answers").click()

    results = student.locator("#results article")
    expect(student.locator("#score")).to_have_text("1 of 3 correct")
    expect(results.nth(0).locator(".verdict")).to_contain_text("Correct.")
    expect(results.nth(1).locator(".verdict")).to_contain_text("Not correct.")
    expect(results.nth(2).locator(".verdict")).to_contain_text("Not answered.")
    expect(results.nth(1)).to_contain_text("(your answer)")
    expect(results.nth(1)).to_contain_text("(correct answer)")


def test_every_control_has_a_name_a_screen_reader_can_announce(site):
    page = site.instructor()
    upload(page)
    assert unlabelled_controls(page) == []                    # overview: upload, generation, lists
    draft(page)
    assert unlabelled_controls(page) == []                    # review: every field of every question
    expect(page.locator(".sheet-mark .mark").first).to_have_text("Draft")
    approve_all_and_publish(page)
    expect(page.locator(".sheet-mark .mark").first).to_have_text("Approved")

    student = site.student()
    assert unlabelled_controls(student) == []
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    assert unlabelled_controls(student) == []


def test_an_instructor_can_review_and_publish_with_the_keyboard_alone(site):
    page = site.instructor()
    upload(page)
    draft(page, count=1)
    assert focused(page)["id"] == "review-heading"

    tab_to(page, lambda e: e["tag"] == "BUTTON" and e["text"] == "Approve")
    page.keyboard.press("Enter")
    expect(page.locator(".sheet").first).to_have_attribute("data-status", "approved")
    page.locator("#review-heading").focus()
    tab_to(page, lambda e: e["id"] == "publish-button")
    page.keyboard.press("Enter")

    expect(page.locator("#status")).to_contain_text("Published as version 1")


# ── A passage that text reading garbled ─────────────────────────────────────

def test_a_garbled_passage_is_flagged_for_the_instructor_and_not_quoted_to_the_student(site, fake_llm):
    def quoting_the_formula(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if "harmonic mean" in text)
        return json.dumps({"questions": [question(sid, sources[sid], 1, excerpt=GARBLED_PASSAGE)]})
    fake_llm.queue(quoting_the_formula)

    page = site.instructor()
    upload(page, "evaluation.pdf", evaluation_pdf())
    draft(page, count=1)
    sheet = page.locator(".sheet").first
    expect(sheet.locator(".flags")).to_contain_text("Students will see only the page number")
    expect(sheet.locator(".flags")).to_contain_text("formulas, which were read by machine.")
    expect(sheet.locator(".flags")).to_contain_text("against page 2 of the document.")   # the page the passage is on
    expect(sheet.locator(".sheet-source")).to_contain_text("F1 = 21 P + 1R")       # the instructor still sees it
    expect(sheet.locator(".sheet-source")).to_contain_text("Not shown to students.")
    approve_all_and_publish(page, count=1)

    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(1)
    answer_all(student, 1)
    student.get_by_role("button", name="Check my answers").click()

    expect(student.locator("#results .cite")).to_have_text("From evaluation.pdf, page 2.")
    expect(student.locator("#results")).not_to_contain_text("21 P")


def test_the_formula_warning_names_no_page_for_a_document_that_has_none(site):
    page = site.instructor()
    notes = ("The harmonic mean of precision and recall is dominated by the smaller of the two values, "
             "and it is written F1 = 2 P R / (P + R). ") * 3
    upload(page, "notes.txt", notes.encode("utf-8"), "text/plain")            # a text file has no pages
    draft(page, count=1)

    warning = page.locator(".sheet").first.locator(".flags li").filter(has_text="read by machine")
    expect(warning).to_have_count(1)
    expect(warning).to_contain_text("in the question against the document.")
    expect(warning).not_to_contain_text("page")


# ── The public info page ────────────────────────────────────────────────────

def test_the_info_page_shows_the_tool_url_and_switches_language(site):
    page = site.open("/info")

    expect(page.locator("#tool-url")).to_have_text(f"{site.url}/lti/ai-quiz")
    expect(page.locator("h1")).to_have_text("AI Quiz Generator")
    expect(page.locator("main")).to_contain_text("What this tool does")
    page.locator("#lang-switch").click()
    expect(page.locator("main")).to_contain_text("Qué hace esta herramienta")


def test_the_info_page_gives_the_setup_for_moodle_field_by_field(site):
    """What the local Moodle 4.5 taught on 2026-10-11: who registers, the ten fields, and four things to know."""
    page = site.open("/info")
    setup = page.locator("#moodle-setup")

    expect(setup.locator("#setup-fields tbody tr")).to_have_count(10)
    row = lambda field: setup.locator("#setup-fields tbody tr").filter(has=page.get_by_role("rowheader", name=field, exact=True))  # noqa: E731
    expect(row("Tool URL")).to_contain_text(f"{site.url}/lti/ai-quiz")
    expect(row("Default launch container")).to_contain_text("New window")
    expect(row("Share launcher's name with tool")).to_contain_text("Always")
    expect(row("Share launcher's email with tool")).to_contain_text("Never")
    expect(row("Accept grades from the tool")).to_contain_text("Never")
    expect(row("Consumer key")).to_contain_text("One for each Moodle site")
    for fact in ("A Moodle administrator registers the tool", "One key and secret per Moodle site", "uma.es",
                 "non-editing teachers", "Consumer key no reconocido", "Firma OAuth no valida"):
        expect(setup).to_contain_text(fact)

    page.locator("#lang-switch").click()

    expect(setup).to_contain_text("Nueva ventana")
    expect(setup).to_contain_text("Una clave y un secreto por cada sitio Moodle")
    expect(setup).to_contain_text("profesorado sin permiso de edición")


# ── A launch without a name, and a page without a session ───────────────────

def test_the_header_of_a_launch_without_a_name_names_the_course_and_nothing_dangling(site):
    """Moodle sends no name when the tool is registered with "Share launcher's name: Never"."""
    page = site.instructor(name="", context_title="Computer Vision (synthetic)")

    # What a person sees and what a screen reader reads: the hidden part of the line does not count.
    expect(page.locator("#session")).to_have_text("Computer Vision (synthetic)", use_inner_text=True)
    expect(page.locator("#user-name")).to_be_hidden()
    page.locator("#lang-switch").click()
    expect(page.locator("#session")).to_have_text("Computer Vision (synthetic)", use_inner_text=True)


def test_the_header_of_a_launch_with_a_name_shows_it(site):
    page = site.student(name="Zoë D'Alençon Muñoz")

    expect(page.locator("#user-name")).to_be_visible()
    expect(page.locator("#session")).to_have_text("Zoë D'Alençon Muñoz — Synthetic course", use_inner_text=True)


@pytest.mark.parametrize("path", ["/instructor", "/student"])
def test_a_reload_without_a_session_shows_a_page_that_says_what_to_do_in_both_languages(site, path):
    page = site.open(path, "0" * 64)

    expect(page.locator("h1")).to_have_text("AI Quiz Generator")
    expect(page.locator("main h2")).to_have_text("Open this tool from your course in Moodle")
    expect(page.locator("main")).to_contain_text("open the activity again")
    expect(page.locator("main")).not_to_contain_text("detail")
    assert page.evaluate("document.documentElement.lang") == "en"
    page.locator("#lang-switch").click()
    expect(page.locator("main h2")).to_have_text("Abre esta herramienta desde tu curso en Moodle")
    expect(page.locator("main")).to_contain_text("abre de nuevo la actividad")
    assert page.evaluate("document.documentElement.lang") == "es"
    assert unlabelled_controls(page) == []


def test_a_spanish_browser_reads_the_page_for_an_ended_session_in_spanish(site):
    page = site.open("/student", "0" * 64, locale="es-ES")

    expect(page.locator("main h2")).to_have_text("Abre esta herramienta desde tu curso en Moodle")


# ── Two languages ───────────────────────────────────────────────────────────

def test_the_page_can_be_switched_to_spanish_and_back(site):
    page = site.instructor()
    expect(page.locator("#docs-heading")).to_have_text("Course documents")

    page.locator("#lang-switch").click()

    expect(page.locator("#docs-heading")).to_have_text("Documentos del curso")
    expect(page.locator("header h1")).to_have_text("Generador de cuestionarios con IA")
    assert page.evaluate("document.documentElement.lang") == "es"
    page.locator("#lang-switch").click()
    expect(page.locator("#docs-heading")).to_have_text("Course documents")


def test_a_spanish_browser_starts_in_spanish(site):
    page = site.open("/student", site.token("Learner"), locale="es-ES")

    expect(page.locator("#list-heading")).to_have_text("Cuestionarios de práctica")
    expect(page.locator("#lang-switch")).to_have_text("English")


# ── What a person sees when something is wrong ──────────────────────────────

def test_a_refused_upload_is_explained_in_the_page(site):
    page = site.instructor()

    page.set_input_files("#upload-file", files=[{"name": "fake.pdf", "mimeType": "application/pdf",
                                                 "buffer": b"this is not a pdf"}])
    page.get_by_role("button", name="Upload document").click()

    expect(page.locator("#status")).to_have_text("The file has a .pdf name but is not a PDF.")
    expect(page.locator("#documents")).to_contain_text("No documents yet")


def test_a_question_without_a_located_passage_needs_the_tick_before_it_can_be_approved(site, fake_llm):
    def invented(messages):
        (sid, text), *_ = sources_in(messages).items()
        return json.dumps({"questions": [question(sid, text, 1, excerpt="A passage that the handout does not "
                                                                       "contain anywhere, invented by the model.")]})
    fake_llm.queue(invented)
    page = site.instructor()
    upload(page)
    draft(page, count=1)
    sheet = page.locator(".sheet").first
    expect(sheet.locator(".flags")).to_contain_text("was not found in the document")

    sheet.get_by_role("button", name="Approve", exact=True).click()
    expect(page.locator("#status")).to_contain_text("Tick the box")
    expect(page.locator(".sheet").first).to_have_attribute("data-status", "draft")

    page.locator(".sheet").first.get_by_role("checkbox").check()
    page.locator(".sheet").first.get_by_role("button", name="Approve", exact=True).click()
    expect(page.locator(".sheet").first).to_have_attribute("data-status", "approved")


# ── Full reading: a background job the page follows ─────────────────────────

def choose_file(page, name="handout.pdf", data=None):
    page.set_input_files("#upload-file", files=[{"name": name, "mimeType": "application/pdf",
                                                 "buffer": handout_pdf() if data is None else data}])


def test_the_reading_mode_is_not_offered_when_the_server_has_no_full_reader(site):
    page = site.instructor()

    expect(page.locator("#upload-button")).to_be_visible()
    expect(page.locator("#reading-mode-field")).to_be_hidden()


def test_a_full_reading_is_followed_in_the_page_until_the_document_is_ready(site, monkeypatch):
    reader = install(monkeypatch, SlowReader())
    page = site.instructor()
    expect(page.locator("#reading-mode-field")).to_be_visible()
    assert unlabelled_controls(page) == []

    page.locator("#mode-full").check()
    choose_file(page)
    page.get_by_role("button", name="Upload document").click()

    row = page.locator("#documents tbody tr").first
    expect(row.locator(".reading")).to_have_text("Being read…")
    expect(page.locator("#status")).to_contain_text("is being read")
    expect(page.locator("#generate-documents")).to_contain_text("Add a document first.")
    expect(page.locator("#generate-button")).to_be_disabled()

    reader.release()                                          # the page finds out by asking again, without a reload

    expect(page.locator("#documents tbody tr").first.locator(".reading")).to_have_text("Full")
    expect(page.locator("#status")).to_contain_text("has been read and is ready")
    expect(page.locator("#generate-button")).to_be_enabled()
    draft(page, count=1)
    expect(page.locator(".sheet-source").first).to_contain_text("handout.pdf, page")


def test_a_reading_that_fails_is_reported_in_words(site, monkeypatch):
    reader = install(monkeypatch, SlowReader(error=RuntimeError("engine details that stay in the log")))
    page = site.instructor()
    page.locator("#mode-full").check()
    choose_file(page)
    page.get_by_role("button", name="Upload document").click()
    expect(page.locator("#documents tbody tr").first.locator(".reading")).to_have_text("Being read…")

    reader.release()

    expect(page.locator("#documents tbody tr").first.locator(".reading")).to_have_text(
        "Not read. The document could not be read in full. Try text only.")
    expect(page.locator("#status")).to_contain_text("could not be read")
    expect(page.locator("#content")).not_to_contain_text("engine details")
    expect(page.locator("#generate-button")).to_be_disabled()


# ── Figures of a full reading ───────────────────────────────────────────────

def naming_figure(figure_id):
    """A model reply with one question that rests on the caption of this figure and names it."""
    def reply(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if f"[FIGURE {figure_id}]" in text)
        return json.dumps({"questions": [question(sid, sources[sid].split("] ", 1)[1], 1, figure=figure_id)]})
    return reply


def upload_full(page):
    page.locator("#mode-full").check()
    choose_file(page)
    page.get_by_role("button", name="Upload document").click()
    expect(page.locator("#documents tbody tr").first.locator(".reading")).to_have_text("Full, 3 figures")


def eventually(condition, seconds=5.0):
    import time

    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "did not happen in time"
        time.sleep(0.05)


def loaded_images(scope) -> list[str]:
    """The alternative texts of the images inside `scope` that the browser really loaded."""
    return scope.evaluate("""node => Array.from(node.querySelectorAll('img'))
        .filter(img => img.complete && img.naturalWidth > 0).map(img => img.alt)""")


def test_an_instructor_sees_every_figure_and_chooses_the_one_shown_with_a_question(site, monkeypatch, fake_llm):
    install_recorded_docling(monkeypatch)
    fake_llm.queue(naming_figure("f0001"))
    page = site.instructor()
    upload_full(page)
    page.fill("#gen-topic", "scale-space pyramid octaves")
    draft(page, count=1)
    sheet = page.locator(".sheet").first

    # the figure the model named is attached, shown, and flagged for a check
    expect(sheet.locator("select[id^='f-']")).to_have_value("f0001")
    expect(sheet.locator(".figure figcaption")).to_contain_text("Figure 1: Scale-space pyramid")
    expect(sheet.locator(".flags")).to_contain_text("A figure is shown with this question.")
    eventually(lambda: len(loaded_images(sheet)) == 1)
    assert unlabelled_controls(page) == []

    # every figure of the document can be looked through
    expect(page.locator("#gallery-heading")).to_have_text("Figures in the source documents (3)")
    page.locator("#gallery-heading").click()
    expect(page.locator("#gallery-figures .figure")).to_have_count(3)
    expect(page.locator("#gallery-figures")).to_contain_text("handout.pdf, page 7")
    eventually(lambda: len(loaded_images(page.locator("#gallery-figures"))) == 3)

    # another figure is chosen with the keyboard, then none
    sheet.locator("select[id^='f-']").focus()
    sheet.locator("select[id^='f-']").select_option("f0003")
    sheet.get_by_role("button", name="Save changes").click()
    expect(page.locator(".sheet").first.locator(".figure figcaption")).to_contain_text("Figure 5: Construction")
    page.locator(".sheet").first.locator("select[id^='f-']").select_option("")
    page.locator(".sheet").first.get_by_role("button", name="Save changes").click()
    expect(page.locator(".sheet").first.locator(".figure")).to_have_count(0)
    expect(page.locator(".sheet").first.locator(".flags")).not_to_contain_text("A figure is shown")


def test_a_student_sees_the_figure_of_a_published_question_and_no_other(site, monkeypatch, fake_llm):
    install_recorded_docling(monkeypatch)
    fake_llm.queue(naming_figure("f0001"))
    page = site.instructor()
    upload_full(page)
    page.fill("#gen-topic", "scale-space pyramid octaves")
    draft(page, count=1)
    approve_all_and_publish(page, count=1)

    student = site.student()
    requested = []
    student.on("request", lambda r: requested.append(r.url.split("?")[0]) if "/api/figures/" in r.url else None)
    student.locator("#quizzes button").first.click()
    paper = student.locator("#quiz-view fieldset.paper").first
    expect(paper.locator(".figure figcaption")).to_contain_text("Figure 1: Scale-space pyramid")
    caption = paper.locator(".figure figcaption").inner_text()
    eventually(lambda: loaded_images(paper) == [caption])              # the caption is the image's alternative text
    answer_all(student, 1)
    student.get_by_role("button", name="Check my answers").click()
    result = student.locator("#results article").first
    eventually(lambda: len(loaded_images(result)) == 1)

    assert requested and all(url.endswith("/f0001") for url in requested)
    other = student.evaluate("""async url => (await fetch(url)).status""",
                             student.evaluate("document.querySelector('.figure img').src").replace("/f0001", "/f0002"))
    assert other == 404


def test_a_figure_that_is_gone_is_replaced_by_a_line_of_text(site, monkeypatch, fake_llm):
    install_recorded_docling(monkeypatch)
    fake_llm.queue(naming_figure("f0001"))
    page = site.instructor()
    upload_full(page)
    page.fill("#gen-topic", "scale-space pyramid octaves")
    draft(page, count=1)
    approve_all_and_publish(page, count=1)
    page.get_by_role("button", name="Back to documents and quizzes").click()
    page.locator("#documents").get_by_role("button", name="Delete").first.click()
    page.locator("#documents").get_by_role("button", name="Delete").first.click()      # the confirmation
    expect(page.locator("#documents")).to_contain_text("No documents yet")

    student = site.student()
    student.locator("#quizzes button").first.click()

    paper = student.locator("#quiz-view fieldset.paper").first
    expect(paper.locator(".figure")).to_contain_text("This figure is no longer available.")
    expect(paper.locator(".figure img")).to_have_count(0)


def test_a_student_on_the_instructor_address_is_told_so_and_led_to_the_quizzes_in_both_languages(site):
    token = site.token("Learner", user="student-1", context_title="Computer Vision (synthetic)")
    page = site.open("/instructor", token)

    expect(page.locator("h1")).to_have_text("AI Quiz Generator")
    expect(page.locator("main h2")).to_have_text("This page is for instructors")
    expect(page.locator("main")).to_contain_text("You opened the tool as a student")
    expect(page.locator("main")).not_to_contain_text("detail")
    assert unlabelled_controls(page) == []
    page.locator("#lang-switch").click()
    expect(page.locator("main h2")).to_have_text("Esta página es para docentes")
    assert page.evaluate("document.documentElement.lang") == "es"
    page.locator("#lang-switch").click()

    page.get_by_role("link", name="Go to the practice quizzes").click()

    expect(page.locator("#list-heading")).to_have_text("Practice quizzes")      # the student page, same session
    expect(page.locator("#session")).to_contain_text("Computer Vision (synthetic)")
