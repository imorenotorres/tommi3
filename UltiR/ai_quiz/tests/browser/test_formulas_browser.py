"""Formulas in a real browser, under the strict policy: drawn by the KaTeX the tool ships, nothing from outside."""

import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from ..fake_llm import question, sources_in  # noqa: E402
from ..readers import install_recorded_docling  # noqa: E402
from .test_browser import (  # noqa: E402
    answer_all, approve_all_and_publish, draft, eventually, unlabelled_controls, upload, upload_full,
)

LATEX = dict(
    question=r"What does $\frac{\partial G}{\partial \sigma}$ approximate?",
    options=[{"id": "A", "text": r"$\sigma \nabla^{2} G$"}, {"id": "B", "text": r"$\sqrt{k}$ pixels"},
             {"id": "C", "text": "nothing at all"}, {"id": "D", "text": r"$$\sum_{i=1}^{n} 2^{i-1}$$"}],
    correct_option_id="A",
    explanation=r"Because $\nabla^{2} G$ is the Laplacian of the Gaussian.",
)
FORMULA_8 = r"$$D ( x , y , \sigma ) = L ( x , y , k \sigma ) - L ( x , y , \sigma ) .$$"


def saying(**fields):
    """A model reply: one question with these texts, about the first source."""
    def reply(messages):
        (sid, text), *_ = sources_in(messages).items()
        return json.dumps({"questions": [question(sid, text, 1, **fields)]})
    return reply


def drafted_from_a_full_reading(site, monkeypatch, fake_llm, **fields):
    """The instructor's page with one drafted question from a full reading, its texts as given."""
    install_recorded_docling(monkeypatch)
    fake_llm.queue(saying(**fields))
    page = site.instructor()
    upload_full(page)
    draft(page, count=1)
    return page


def student_at_the_quiz(site):
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(1)
    return student


# ── Drawn for the student ───────────────────────────────────────────────────

def test_formulas_are_drawn_in_the_question_the_options_and_the_explanation(site, monkeypatch, fake_llm):
    page = drafted_from_a_full_reading(site, monkeypatch, fake_llm, **LATEX)
    approve_all_and_publish(page, count=1)

    student = student_at_the_quiz(site)
    paper = student.locator("#quiz-view fieldset.paper").first
    expect(paper.locator("legend .katex")).to_have_count(1)
    expect(paper.locator("label.choice .katex")).to_have_count(3)
    expect(paper.locator("label.choice .katex-display")).to_have_count(1)        # the one written between $$ and $$
    expect(paper.locator(".formula-source")).to_have_count(0)                    # nothing fell back to its source
    expect(paper.locator("label.choice").nth(1)).to_contain_text("pixels")       # the text around a formula stays
    # a drawn formula has a size: it is not an empty box
    assert student.evaluate("document.querySelector('legend .katex-html').getBoundingClientRect().width") > 10

    answer_all(student, 0)
    student.get_by_role("button", name="Check my answers").click()
    result = student.locator("#results article").first
    expect(result.locator(".stem .katex")).to_have_count(1)
    expect(result.locator("ul.choices .katex")).to_have_count(3)
    expect(result.locator(".because .katex")).to_have_count(1)
    expect(student.locator("#score")).to_have_text("1 of 1 correct")


def test_katex_and_its_fonts_come_from_the_tool_and_nothing_is_asked_of_any_other_host(site, monkeypatch, fake_llm):
    page = drafted_from_a_full_reading(site, monkeypatch, fake_llm, **LATEX)
    approve_all_and_publish(page, count=1)
    student = site.student()
    answers = []
    student.on("response", lambda r: answers.append((r.url.split("?")[0], r.status)))
    student.reload()
    student.wait_for_load_state("networkidle")
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view .katex")).to_have_count(4)
    eventually(lambda: student.evaluate("document.fonts.check('16px KaTeX_Main')"))   # the formula font is in use
    student.wait_for_load_state("networkidle")

    assert all(url.startswith(site.url + "/lti/ai-quiz/") for url, _ in answers)
    assert (f"{site.url}/lti/ai-quiz/assets/vendor/katex/katex.min.js", 200) in answers
    assert (f"{site.url}/lti/ai-quiz/assets/vendor/katex/katex.min.css", 200) in answers
    fonts = [(url, status) for url, status in answers if "/fonts/" in url]
    assert fonts and all(url.endswith(".woff2") and status == 200 for url, status in fonts)


def test_bold_symbols_boxes_colours_and_matrices_are_drawn_without_breaking_the_strict_policy(site, monkeypatch, fake_llm):
    # the commands for which KaTeX sets styles on elements; the `site` fixture fails the test on any violation
    page = drafted_from_a_full_reading(
        site, monkeypatch, fake_llm,
        question=r"Is $\boldsymbol{\theta}^{\ast} = \mathbf{x}^{\top} \hat{\mathbf{h}}$ boxed as $\fbox{a}$ or $\boxed{b}$?",
        options=[{"id": "A", "text": r"$\textcolor{red}{c} + \colorbox{yellow}{d}$"},
                 {"id": "B", "text": r"$$\begin{pmatrix} a & b \\ c & d \end{pmatrix} \vec{v} = \left\lceil \frac{\log(1-p)}{\log(1-w^{s})} \right\rceil$$"},
                 {"id": "C", "text": r"$\sqrt[3]{x} \leq \overline{y} \underline{z} \cancel{q}$"},
                 {"id": "D", "text": r"$\mathcal{I} \in \mathbb{R}^{n} \;\text{with}\; \|\mathbf{v}\|_2 = 1$"}])
    sheet = page.locator(".sheet").first

    expect(sheet.locator(".preview .katex")).to_have_count(7)
    expect(sheet.locator(".preview .formula-source")).to_have_count(0)
    # KaTeX's version for screen readers (MathML) is there for every formula
    expect(sheet.locator(".preview .katex-mathml math")).to_have_count(7)
    # the styles KaTeX wanted to write as attributes were applied all the same
    assert page.evaluate("""() => Array.from(document.querySelectorAll('.preview svg'))
        .filter(svg => svg.style.width).length""") > 0
    assert page.evaluate("document.querySelectorAll('.preview [style]').length") > 0
    # and the page's own way of setting attributes is back in place
    assert page.evaluate("Element.prototype.setAttribute.toString().includes('[native code]')")


# ── A formula that cannot be drawn ──────────────────────────────────────────

def test_a_formula_that_cannot_be_drawn_is_shown_as_written_and_the_instructor_is_told(site, monkeypatch, fake_llm):
    page = drafted_from_a_full_reading(
        site, monkeypatch, fake_llm,
        question=r"Which value does $\frac{1}{$ take, compared with $x^2$?",
        explanation=r"It is $\notacommand{3}$ by definition.")
    sheet = page.locator(".sheet").first

    expect(sheet.locator(".preview .formula-source")).to_have_count(2)
    expect(sheet.locator(".preview .formula-source").first).to_have_text(r"$\frac{1}{$")
    expect(sheet.locator(".preview .katex")).to_have_count(1)                    # the good one beside it is drawn
    expect(sheet.locator(".preview .formula-problem")).to_contain_text("Formulas that could not be displayed: 2.")

    approve_all_and_publish(page, count=1)
    student = student_at_the_quiz(site)
    expect(student.locator("legend .formula-source")).to_have_text(r"$\frac{1}{$")
    expect(student.locator("legend .katex")).to_have_count(1)


# ── A formula is not a way in ───────────────────────────────────────────────

HOSTILE = (r"Open $\href{javascript:window.__pwned=1}{this}$ or $\url{javascript:window.__pwned=2}$ or "
           r"$\includegraphics{http://outside.invalid/x.png}$ or $\htmlData{onclick=window.__pwned=4}{x}$ or "
           r"$\htmlId{status}{y}$ <img src=x onerror=window.__pwned=3>")


def test_a_formula_cannot_carry_a_link_an_image_address_or_markup(site, monkeypatch, fake_llm):
    page = drafted_from_a_full_reading(site, monkeypatch, fake_llm, question=HOSTILE,
                                       explanation=r"See $\href{https://outside.invalid/}{there}$.")
    asked = []
    page.on("request", lambda r: asked.append(r.url))
    expect(page.locator(".sheet .preview")).to_be_visible()
    approve_all_and_publish(page, count=1)
    student = student_at_the_quiz(site)
    student.on("request", lambda r: asked.append(r.url))
    answer_all(student, 0)
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#results article")).to_have_count(1)

    for view in (page, student):
        assert view.evaluate("window.__pwned") is None
        # (the only images on these pages are the figures of the document, in the instructor's gallery)
        assert view.locator("a[href^='javascript'], a[href*='outside.invalid'], [onclick], img:not(.figure > img)").count() == 0
        assert view.locator("#status").count() == 1                              # no second element took that id
        for link in view.locator(".katex a").all():                              # if KaTeX drew any link at all, it leads nowhere
            assert not link.get_attribute("href")
    assert not [url for url in asked if "outside.invalid" in url]
    expect(student.locator("#results")).to_contain_text("<img src=x onerror=window.__pwned=3>")   # markup stays text


# ── Dollar signs that are not formulas ──────────────────────────────────────

def test_a_question_from_a_text_reading_shows_its_dollar_signs_as_they_are(site, fake_llm):
    fake_llm.queue(saying(question="Is $x^2$ what the licence costs, or $5?"))
    page = site.instructor()
    upload(page)
    draft(page, count=1)
    expect(page.locator(".sheet .preview")).to_have_count(0)                     # nothing to preview: it is plain text
    approve_all_and_publish(page, count=1)

    student = student_at_the_quiz(site)

    expect(student.locator("legend")).to_contain_text("Is $x^2$ what the licence costs, or $5?")
    expect(student.locator(".katex")).to_have_count(0)


def test_prices_are_not_taken_for_formulas(site, monkeypatch, fake_llm):
    page = drafted_from_a_full_reading(
        site, monkeypatch, fake_llm,
        question=r"A seat costs $5-$10 and a site $70, so is $x^2$ the total for $x$ seats?")
    approve_all_and_publish(page, count=1)

    student = student_at_the_quiz(site)

    expect(student.locator("legend .katex")).to_have_count(2)
    expect(student.locator("legend")).to_contain_text("A seat costs $5-$10 and a site $70, so is")
    expect(student.locator("legend .formula-source")).to_have_count(0)


# ── The instructor's side ───────────────────────────────────────────────────

def test_the_preview_follows_what_the_instructor_types(site, monkeypatch, fake_llm):
    page = drafted_from_a_full_reading(site, monkeypatch, fake_llm, **LATEX)
    sheet = page.locator(".sheet").first
    expect(sheet.locator(".preview .preview-stem .katex")).to_have_count(1)
    expect(sheet.locator(".preview .formula-problem")).to_be_hidden()
    assert unlabelled_controls(page) == []

    sheet.locator("textarea").first.fill(r"Is $a^2 + b^2$ equal to $c^2$, or to $\frac{c}{$?")

    expect(sheet.locator(".preview .preview-stem .katex")).to_have_count(2)
    expect(sheet.locator(".preview .formula-problem")).to_contain_text("could not be displayed: 1.")
    sheet.locator("textarea").first.fill(r"Is $a^2 + b^2$ equal to $c^2$?")
    expect(sheet.locator(".preview .formula-problem")).to_be_hidden()
    sheet.locator("input[type=text]").nth(2).fill(r"only for $\theta = 90$ degrees")
    expect(sheet.locator(".preview .preview-options li").nth(2).locator(".katex")).to_have_count(1)


def test_a_passage_with_a_recognised_formula_is_drawn_for_the_instructor_and_withheld_from_students(site, monkeypatch, fake_llm):
    install_recorded_docling(monkeypatch)

    def quoting_formula_8(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if FORMULA_8 in text)
        return json.dumps({"questions": [question(
            sid, sources[sid], 1, excerpt="gives the difference-of-Gaussians function " + FORMULA_8)]})
    fake_llm.queue(quoting_formula_8)
    page = site.instructor()
    upload_full(page)
    page.fill("#gen-topic", "difference of Gaussians neighbouring levels pyramid")
    draft(page, count=1)
    sheet = page.locator(".sheet").first

    expect(sheet.locator(".sheet-source blockquote .katex-display")).to_have_count(1)
    expect(sheet.locator(".sheet-source")).to_contain_text("Not shown to students.")
    expect(sheet.locator(".flags")).to_contain_text("Students will see only the page number")

    approve_all_and_publish(page, count=1)
    student = student_at_the_quiz(site)
    answer_all(student, 1)
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#results .cite")).to_have_text("From handout.pdf, page 3.")


# ── Every command KaTeX knows, under the strict policy ──────────────────────

def katex_vocabulary() -> tuple[list[str], list[str]]:
    """The command and environment names in the shipped KaTeX script."""
    import re
    from pathlib import Path

    script = (Path(__file__).resolve().parents[2] / "static" / "vendor" / "katex" / "katex.min.js").read_text(encoding="utf-8")
    commands = sorted(set(re.findall(r'"\\\\([A-Za-z]+)"', script)))      # in the script a name is written "\\frac"
    in_name_lists = {name for names in re.findall(r"names:\[([^\]]*)\]", script) for name in re.findall(r'"([A-Za-z*]+)"', names)}
    return commands, sorted(in_name_lists)


def test_no_command_katex_knows_makes_it_write_a_style_the_strict_policy_blocks(site):
    """A net under the check in test_katex.py: whatever KaTeX does for any of its commands, drawn the way the
    pages draw, the browser must have nothing to block. The `site` fixture fails the test on any violation."""
    commands, environments = katex_vocabulary()
    assert len(commands) > 500 and "frac" in commands and "pmb" in commands and "fcolorbox" in commands
    assert "pmatrix" in environments and "cases" in environments
    tries = [[name, form.replace("NAME", name)] for name in commands for form in (
        r"\NAME", r"\NAME{a}", r"\NAME{a}{b}", r"\NAME{red}{a}", r"\NAME{red}{blue}{a}", r"\NAME[b]{a}",
        r"a \NAME b", r"\left\NAME a \right\NAME", r"\NAME{3em}", r"\NAME x^2_i")]
    tries += [[name, rf"\begin{{{name}}} a & b \\ c & d \end{{{name}}}"] for name in environments]
    tries += [[name, rf"\begin{{{name}}}{{cc}} a & b \\ c & d \end{{{name}}}"] for name in environments]
    page = site.instructor()

    drawn = page.evaluate("""tries => {
        const box = document.createElement('div');
        document.body.appendChild(box);
        let drawn = 0, names = new Set();
        for (const [name, tex] of tries) {
            if (window.AiQuiz.math.fill(box, '$$' + tex + '$$') === 0) { drawn += 1; names.add(name); }
        }
        box.remove();
        return {drawn, names: names.size, native: Element.prototype.setAttribute.toString().includes('[native code]')};
    }""", tries)

    # On 2026-10-11, with KaTeX 0.19.0: 1022 commands and 33 environments, 10,286 tries, about 8,000 of them drawn.
    assert drawn["drawn"] > 6000 and drawn["names"] > 850, drawn    # most of the vocabulary was really drawn
    assert drawn["native"]                                          # also after the many tries that could not be drawn
