"""The whole loop in full reading, in a real browser: what the M3 browser checks cover for text reading,
repeated for a document with formulas and figures (rules A12 and A15)."""

import copy
import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from UltiR.ai_quiz import docling_reader  # noqa: E402

from ..docling_recorded import RAW, images  # noqa: E402
from ..fake_llm import question, sources_in  # noqa: E402
from ..readers import install_recorded_docling  # noqa: E402
from .test_browser import (  # noqa: E402
    PAYLOAD, answer_all, approve_all_and_publish, choose_file, draft, eventually, focused, loaded_images, tab_to,
    unlabelled_controls, upload_full,
)

STEM = r"Which function does subtracting two neighbouring levels $L(x, y, k\sigma)$ and $L(x, y, \sigma)$ give?"


def about_figure_1(messages):
    """One question that rests on the caption of Figure 1, names the figure and carries LaTeX."""
    sources = sources_in(messages)
    sid = next(s for s, text in sources.items() if "[FIGURE f0001]" in text)
    return json.dumps({"questions": [question(
        sid, sources[sid].split("] ", 1)[1], 1, figure="f0001", question=STEM,
        options=[{"id": "A", "text": r"the Laplacian $\nabla^{2} G$ itself"},
                 {"id": "B", "text": r"the difference of Gaussians $D(x, y, \sigma)$"},
                 {"id": "C", "text": "the scale-space pyramid"}, {"id": "D", "text": "an octave"}],
        explanation=r"Because $D = L(k\sigma) - L(\sigma)$.")]})


def drafted(site, monkeypatch, fake_llm, **launch):
    install_recorded_docling(monkeypatch)
    fake_llm.queue(about_figure_1)
    page = site.instructor(**launch)
    upload_full(page)
    page.fill("#gen-topic", "scale-space pyramid octaves")
    draft(page, count=1, title="Scale space")
    return page


# ── The whole loop ──────────────────────────────────────────────────────────

def test_from_a_full_reading_upload_to_a_student_s_result(site, monkeypatch, fake_llm):
    page = drafted(site, monkeypatch, fake_llm, context_title="Computer Vision (synthetic)")

    # the document: how it was read, and what the reader had to report, in words
    page.get_by_role("button", name="Back to documents and quizzes").click()
    row = page.locator("#documents tbody tr").first
    expect(row.locator(".reading")).to_have_text("Full, 3 figures")
    expect(row).to_contain_text("Some formulas on page 15 could not be recognised and are kept as plain text.")
    expect(row).to_contain_text("A table on page 8 was not recognised as a table")
    page.locator("#quizzes button").first.click()

    # review: the page of the passage, the figure, the formulas as students will see them, the warnings
    sheet = page.locator(".sheet").first
    expect(page.locator("#review-heading")).to_have_text("Scale space")
    expect(sheet.locator(".sheet-source .where")).to_have_text("handout.pdf, page 3")
    expect(sheet.locator(".figure figcaption")).to_contain_text("Figure 1: Scale-space pyramid")
    expect(sheet.locator(".preview .preview-stem .katex")).to_have_count(2)
    expect(sheet.locator(".preview .preview-options .katex")).to_have_count(2)
    expect(sheet.locator(".flags")).to_contain_text("A figure is shown with this question.")
    expect(sheet.locator(".flags")).to_contain_text("contains formulas, which were read by machine.")
    expect(sheet.locator(".flags")).to_contain_text("bold letters and function names can come out wrong")
    expect(sheet.locator(".flags")).to_contain_text("against page 3 of the document.")
    assert sheet.locator("textarea").first.input_value() == STEM                 # the field holds the LaTeX as written
    approve_all_and_publish(page, count=1)

    # the student: figure and formulas before answering, and again in the result, with the page as the citation
    student = site.student(name="Synthetic Student")
    expect(student.locator("#quizzes")).to_contain_text("Scale space")
    student.locator("#quizzes button").first.click()
    paper = student.locator("#quiz-view fieldset.paper").first
    expect(paper.locator("legend .katex")).to_have_count(2)
    expect(paper.locator(".figure figcaption")).to_contain_text("Figure 1: Scale-space pyramid")
    eventually(lambda: len(loaded_images(paper)) == 1)
    paper.get_by_role("radio").nth(1).check()
    student.get_by_role("button", name="Check my answers").click()

    result = student.locator("#results article").first
    expect(student.locator("#score")).to_have_text("1 of 1 correct")
    expect(result.locator(".because .katex")).to_have_count(1)
    expect(result.locator(".cite")).to_contain_text("From handout.pdf, page 3")
    eventually(lambda: len(loaded_images(result)) == 1)
    student.locator("#result-view [data-back]").click()
    expect(student.locator("#quizzes")).to_contain_text("1 tried, best 1 of 1")


def test_nothing_the_student_receives_before_submitting_holds_the_key_in_full_reading_either(site, monkeypatch, fake_llm):
    page = drafted(site, monkeypatch, fake_llm)
    approve_all_and_publish(page, count=1)
    received = []
    student = site.student()
    student.on("response", lambda r: received.append(r.text()) if "/api/" in r.url and "/figures/" not in r.url else None)
    student.reload()
    student.wait_for_load_state("networkidle")
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(1)

    everything = "\n".join(received) + student.content()

    assert len(received) >= 3
    for private in ("correct_option_id", "Because $D", "excerpt", "handout.pdf", "chunk_id", '"page"'):
        assert private not in everything


# ── A15: keyboard and names ─────────────────────────────────────────────────

def test_the_new_controls_can_be_used_with_the_keyboard_alone(site, monkeypatch, fake_llm):
    install_recorded_docling(monkeypatch)
    fake_llm.queue(about_figure_1)
    page = site.instructor()
    expect(page.locator("#reading-mode-field")).to_be_visible()

    # choose full reading: Tab to the choice, arrow to the second option
    choose_file(page)                                                            # (a file dialog cannot be driven by keys in a test)
    page.locator("#upload-file").focus()
    tab_to(page, lambda e: e["id"] == "mode-text")
    page.keyboard.press("ArrowDown")
    assert focused(page)["id"] == "mode-full" and page.locator("#mode-full").is_checked()
    tab_to(page, lambda e: e["id"] == "upload-button")
    page.keyboard.press("Enter")
    expect(page.locator("#documents tbody tr").first.locator(".reading")).to_have_text("Full, 3 figures")

    page.fill("#gen-topic", "scale-space pyramid octaves")
    page.fill("#gen-count", "1")
    page.locator("#generate-button").focus()
    page.keyboard.press("Enter")
    expect(page.locator(".sheet")).to_have_count(1)
    assert focused(page)["id"] == "review-heading"

    # open the gallery of figures, then choose another figure for the question and save
    tab_to(page, lambda e: e["tag"] == "SUMMARY")
    page.keyboard.press("Enter")
    expect(page.locator("#gallery-figures .figure").first).to_be_visible()
    tab_to(page, lambda e: e["tag"] == "SELECT" and e["id"].startswith("f-"))
    page.keyboard.press("ArrowDown")                                             # from Figure 1 to Figure 2
    tab_to(page, lambda e: e["tag"] == "BUTTON" and e["text"] == "Save changes")
    page.keyboard.press("Enter")
    expect(page.locator(".sheet").first.locator(".figure figcaption")).to_contain_text("Figure 2: Response")

    tab_to(page, lambda e: e["tag"] == "BUTTON" and e["text"] == "Approve")
    page.keyboard.press("Enter")
    expect(page.locator(".sheet").first).to_have_attribute("data-status", "approved")


def test_every_new_control_and_image_has_a_name_a_screen_reader_can_announce(site, monkeypatch, fake_llm):
    page = drafted(site, monkeypatch, fake_llm)
    page.locator("#gallery-heading").click()
    expect(page.locator("#gallery-figures .figure")).to_have_count(3)

    assert unlabelled_controls(page) == []
    assert page.evaluate("Array.from(document.images).filter(i => !i.alt.trim()).length") == 0
    assert page.locator("#gallery-heading").inner_text().strip() == "Figures in the source documents (3)"
    assert page.locator(".preview").get_attribute("aria-label") == "As students will see it"
    expect(page.locator(".preview .katex-mathml math").first).to_be_attached()   # KaTeX's version for screen readers

    approve_all_and_publish(page, count=1)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(1)
    assert unlabelled_controls(student) == []
    assert student.evaluate("Array.from(document.images).filter(i => !i.alt.trim()).length") == 0


def test_a_student_can_take_a_full_reading_quiz_with_the_keyboard_alone(site, monkeypatch, fake_llm):
    page = drafted(site, monkeypatch, fake_llm)
    approve_all_and_publish(page, count=1)
    student = site.student()
    expect(student.locator("#quizzes table")).to_be_visible()

    tab_to(student, lambda e: e["tag"] == "BUTTON" and e["text"] == "Start")
    student.keyboard.press("Enter")
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(1)
    tab_to(student, lambda e: e["type"] == "radio")
    student.keyboard.press("Space")
    student.keyboard.press("ArrowDown")
    tab_to(student, lambda e: e["id"] == "submit-button")
    student.keyboard.press("Enter")

    expect(student.locator("#score")).to_have_text("1 of 1 correct")
    assert focused(student)["id"] == "result-heading"


# ── Two languages ───────────────────────────────────────────────────────────

def test_the_full_reading_parts_of_the_page_are_in_spanish_too(site, monkeypatch, fake_llm):
    page = drafted(site, monkeypatch, fake_llm)
    page.locator("#lang-switch").click()

    sheet = page.locator(".sheet").first
    expect(sheet).to_contain_text("Figura que se muestra con la pregunta")
    expect(sheet.locator(".preview h4")).to_have_text("Como lo verá el alumnado")
    expect(sheet.locator(".flags")).to_contain_text("Esta pregunta se muestra con una figura.")
    expect(sheet.locator(".flags")).to_contain_text("fórmulas, que han sido leídas por una máquina.")
    expect(sheet.locator(".flags")).to_contain_text("con la página 3 del documento.")
    expect(page.locator("#gallery-heading")).to_have_text("Figuras de los documentos de origen (3)")
    expect(sheet.locator(".preview .preview-stem .katex")).to_have_count(2)      # the formulas are still drawn
    page.get_by_role("button", name="Volver a documentos y cuestionarios").click()
    expect(page.locator("#reading-mode-field legend")).to_have_text("Cómo leer el documento")
    expect(page.locator("#documents tbody tr").first.locator(".reading")).to_have_text("Completa, 3 figuras")


# ── A12: what Docling found in a document stays text ────────────────────────

def test_markup_in_captions_formulas_and_text_of_a_full_reading_is_shown_as_text(site, monkeypatch, fake_llm):
    raw = copy.deepcopy(RAW)
    for item in raw["items"]:
        if item["kind"] == "text" and item["text"].startswith("Figure 1:"):
            item["text"] = item["orig"] = f"Figure 1: A pyramid {PAYLOAD} with three octaves and three intervals per octave."
        if item["kind"] == "picture" and item["caption"].startswith("Figure 1:"):
            item["caption"] = f"Figure 1: A pyramid {PAYLOAD} with three octaves and three intervals per octave."
        if item["kind"] == "formula" and item["orig"].endswith("(8)"):
            item["text"] = r"D = \href{javascript:window.__pwned=1}{L} - \text{<img src=x onerror=window.__pwned=1>}"
    monkeypatch.setattr(docling_reader, "unavailable_reason", lambda: None)
    monkeypatch.setattr(docling_reader, "run_worker", lambda pdf, stop=None: (copy.deepcopy(raw), images()))

    def quoting_it_all(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if "[FIGURE f0001]" in text)
        passage = sources[sid][sources[sid].index("Figure 1:"):]
        return json.dumps({"questions": [question(sid, passage, 1, figure="f0001", excerpt=passage[:500])]})
    fake_llm.queue(quoting_it_all)
    page = site.instructor()
    upload_full(page)
    page.fill("#gen-topic", "pyramid octaves intervals")
    draft(page, count=1)
    sheet = page.locator(".sheet").first
    page.locator("#gallery-heading").click()

    def nothing_ran(view, figures):
        assert view.evaluate("window.__pwned") is None
        assert view.locator("a[href^='javascript'], [onerror], [onclick]").count() == 0
        assert view.locator("img").count() == figures                            # the figures, and no image from the payload
        assert view.evaluate("document.scripts.length") == 5

    expect(sheet.locator(".figure figcaption")).to_contain_text("<img src=x onerror=")
    expect(sheet.locator(".sheet-source blockquote")).to_contain_text("<script>window.__pwned=1</script>")
    expect(sheet.locator("select[id^='f-'] option").nth(1)).to_contain_text("<img src=x")
    expect(page.locator("#gallery-figures")).to_contain_text("<script>")
    nothing_ran(page, figures=4)                                                 # one on the question, three in the gallery

    approve_all_and_publish(page, count=1)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view .figure figcaption")).to_contain_text("<img src=x onerror=")
    nothing_ran(student, figures=1)
    answer_all(student, 1)
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#results article")).to_have_count(1)
    expect(student.locator("#results .figure figcaption")).to_contain_text("<img src=x onerror=")
    nothing_ran(student, figures=2)                                              # in the result, and in the quiz view behind it


# ── The public info page ────────────────────────────────────────────────────

def test_the_info_page_explains_the_two_ways_of_reading_and_gives_the_licence_of_katex(site):
    page = site.open("/info")

    expect(page.locator("main")).to_contain_text("Reading documents")
    expect(page.locator("main")).to_contain_text("Formulas are drawn with KaTeX 0.19.0")
    with page.expect_response(lambda r: r.url.endswith("/assets/vendor/katex/LICENSE")) as licence:
        page.get_by_role("link", name="licence text").click()
    assert licence.value.status == 200
    page.go_back()
    page.locator("#lang-switch").click()
    expect(page.locator("main")).to_contain_text("Lectura de documentos")
