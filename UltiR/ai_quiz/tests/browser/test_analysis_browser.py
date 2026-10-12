""""Analyse the answers" on the instructor's page, in a browser, with the fake model behind the server."""

import json
import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from .test_browser import unlabelled_controls  # noqa: E402
from .test_class_summary_browser import review_again, take  # noqa: E402
from .test_confidence_browser import asking_quiz  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402

CLASS = (("student-1", "ABB", "ssg"), ("student-2", "ABA", "sfs"), ("student-3", "BBA", "sss"))


def answered(site, students=CLASS):
    """An instructor page with a published quiz that asks "how sure", answered by these students."""
    teacher = asking_quiz(site)
    for user, picks, levels in students:
        take(site, user, picks, levels)
    review_again(teacher)
    return teacher


def test_below_the_minimum_group_the_button_is_off_and_says_why(site, fake_llm):
    teacher = answered(site, CLASS[:1])
    before = len(fake_llm.calls)

    button = teacher.get_by_role("button", name="Analyse the answers")

    expect(button).to_be_disabled()
    expect(teacher.locator("#analysis-note")).to_have_text("Available once at least 3 students have answered a question.")
    expect(teacher.locator("#analysis-result")).to_be_hidden()
    assert len(fake_llm.calls) == before
    assert unlabelled_controls(teacher) == [] and hard_to_read(teacher) == []


def test_the_instructor_asks_once_and_the_suggestion_stays_until_it_is_made_again(site, fake_llm):
    teacher = answered(site)
    before = len(fake_llm.calls)
    button = teacher.locator("#analysis-button")
    expect(button).to_be_enabled()
    expect(button).to_have_text("Analyse the answers")
    expect(teacher.locator("#analysis-note")).to_contain_text("It is sent no names and no single answers.")

    button.click()

    expect(teacher.locator("#status")).to_have_text("The suggestion is below the class summary.")
    result = teacher.locator("#analysis-result")
    expect(result).to_be_visible()
    expect(result.locator("h4")).to_have_text("AI suggestion")                      # said in words, above the points
    made = result.locator("#analysis-made").inner_text()
    assert re.fullmatch(r"Made on \d{1,2} \w+ \d{4},? (at )?\d\d:\d\d from 3 attempts\. "
                        r"A model wrote it: check it against the table above\.", made), made
    points = result.locator("#analysis-points li")
    expect(points).to_have_count(2)
    expect(points.nth(0)).to_contain_text("Point 1: many students chose the same wrong option in Q1.")
    expect(points.nth(0).locator(".cite")).to_contain_text("Question 1 · handout.pdf, page 1:")
    assert len(points.nth(0).locator(".cite q").inner_text()) > 30                   # the stored passage
    # Everybody was right on question 2, so the model was not told about it: the second point is about question 3.
    expect(points.nth(1)).to_contain_text("Point 2: many students chose the same wrong option in Q3.")
    expect(points.nth(1).locator(".cite")).to_contain_text("Question 3 · handout.pdf, page 3:")
    expect(teacher.locator("#analysis-note")).to_contain_text("the questions in which at least a third of the answers were wrong")
    expect(button).to_have_text("Regenerate")
    assert len(fake_llm.calls) == before + 1
    assert unlabelled_controls(teacher) == [] and hard_to_read(teacher) == [] and small_buttons(teacher) == []

    review_again(teacher)                                                            # the page is opened again
    expect(teacher.locator("#analysis-result")).to_be_visible()
    expect(teacher.locator("#analysis-points li")).to_have_count(2)
    expect(teacher.locator("#analysis-button")).to_have_text("Regenerate")
    assert len(fake_llm.calls) == before + 1                                         # and no model was asked

    teacher.locator("#analysis-button").click()
    expect(teacher.locator("#status")).to_have_text("The suggestion is below the class summary.")
    assert len(fake_llm.calls) == before + 2


def test_the_suggestion_says_when_more_students_have_answered_since(site):
    teacher = answered(site)
    teacher.locator("#analysis-button").click()
    expect(teacher.locator("#analysis-result")).to_be_visible()
    take(site, "student-4", "BBB", "sss")

    review_again(teacher)

    expect(teacher.locator("#analysis-made")).to_contain_text("from 3 attempts.")
    expect(teacher.locator("#analysis-made")).to_contain_text("There are 4 attempts now.")


def test_what_the_model_wrote_is_shown_as_text(site, fake_llm):
    payload = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>'
    teacher = answered(site)
    fake_llm.queue(json.dumps({"points": [{"question": "Q1", "text": f"Look at {payload} this."}]}))

    teacher.locator("#analysis-button").click()

    point = teacher.locator("#analysis-points li").first
    expect(point).to_contain_text(f"Look at {payload} this.")
    assert teacher.evaluate("window.__pwned") is None
    assert teacher.locator("#analysis-result img").count() == 0


def test_the_page_says_when_points_were_left_out_for_contradicting_the_answer_key(site, fake_llm):
    teacher = answered(site)                                         # the key is B in every fake question
    bad = json.dumps({"points": [{"question": "Q1", "text": "The correct option (A) was chosen twice."},
                                 {"question": "Q3", "text": "Two of three missed this one."}]})
    fake_llm.queue(bad, bad)

    teacher.locator("#analysis-button").click()

    expect(teacher.locator("#analysis-result")).to_be_visible()
    expect(teacher.locator("#analysis-points li")).to_have_count(1)
    expect(teacher.locator("#analysis-points li")).to_contain_text("Two of three missed this one.")
    expect(teacher.locator("#analysis-result")).not_to_contain_text("The correct option (A)")
    expect(teacher.locator("#analysis-dropped")).to_be_visible()
    expect(teacher.locator("#analysis-dropped")).to_have_text(
        "Points left out: 1. Each called a wrong option correct, or the correct one wrong; "
        "the tool checks that against the answer key.")
    assert hard_to_read(teacher) == []

    teacher.locator("#analysis-button").click()                      # made again, this time without such a point
    expect(teacher.locator("#analysis-points li")).to_have_count(2)
    expect(teacher.locator("#analysis-dropped")).to_be_hidden()


def test_a_model_that_fails_is_reported_and_the_button_can_be_pressed_again(site, fake_llm):
    teacher = answered(site)
    fake_llm.queue("not json", "not json")

    teacher.locator("#analysis-button").click()

    expect(teacher.locator("#status")).to_contain_text("The model did not return a usable analysis")
    expect(teacher.locator("#analysis-result")).to_be_hidden()
    expect(teacher.locator("#analysis-button")).to_be_enabled()


def test_in_spanish_the_button_is_analizar_respuestas_and_the_model_is_asked_for_spanish(site, fake_llm):
    teacher = answered(site)
    teacher.locator("#lang-switch").click()
    expect(teacher.locator("#class-summary h3")).to_have_text("Resumen de la clase")

    button = teacher.get_by_role("button", name="Analizar respuestas")
    expect(teacher.locator("#analysis-note")).to_contain_text("No se le envían nombres ni respuestas individuales.")
    button.click()

    result = teacher.locator("#analysis-result")
    expect(result.locator("h4")).to_have_text("Sugerencia de IA")
    expect(result.locator("#analysis-made")).to_contain_text("a partir de 3 intentos. La escribió un modelo")
    expect(result.locator("#analysis-points li").first.locator(".cite")).to_contain_text("Pregunta 1 · handout.pdf, página 1:")
    expect(teacher.locator("#analysis-button")).to_have_text("Regenerar")
    assert "Write the points in Spanish." in fake_llm.calls[-1]["messages"][0]["content"]
