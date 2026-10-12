""""What to review" on the student's result page, in a browser."""

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from .test_browser import approve_all_and_publish, draft, unlabelled_controls, upload  # noqa: E402
from .test_confidence_browser import answer, asking_quiz  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402


def result_of(site, picks, levels=None):
    """A student answers the only published quiz and lands on the result."""
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(len(picks))
    answer(student, picks, levels or [None] * len(picks))
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#score")).to_be_visible()
    return student


def test_the_result_lists_what_to_review_the_sure_and_wrong_first_each_with_its_passage_and_page(site):
    asking_quiz(site)

    student = result_of(site, "AAB", ("I am guessing", "I know this", "I know this"))     # the key is B everywhere

    box = student.locator("#review-box")
    expect(box).to_be_visible()
    expect(box.locator("h3")).to_have_text("What to review")
    items = box.locator("li")
    expect(items).to_have_count(2)
    expect(items.nth(0)).to_contain_text("Question 2")                     # sure and wrong: first
    expect(items.nth(0)).to_contain_text("You said “I know this”, and it was not correct.")
    expect(items.nth(1)).to_contain_text("Question 1")
    expect(items.nth(1)).to_contain_text("Not correct.")
    expect(items.nth(0).locator(".cite")).to_contain_text("handout.pdf, page 2:")
    expect(items.nth(1).locator(".cite")).to_contain_text("handout.pdf, page 1:")
    assert len(items.nth(0).locator(".cite q").inner_text()) > 30           # the passage itself
    expect(box.locator("#review-box-none")).to_be_hidden()
    expect(box.locator("#review-box-intro")).to_be_visible()
    expect(box.locator("#review-box-intro")).to_contain_text("The ones you said you knew come first.")
    assert unlabelled_controls(student) == [] and hard_to_read(student) == [] and small_buttons(student) == []


def test_with_every_answer_right_the_box_is_one_line(site):
    page = site.instructor()
    upload(page)
    draft(page)
    approve_all_and_publish(page)

    student = result_of(site, "BBB")

    box = student.locator("#review-box")
    expect(box).to_be_visible()
    expect(box.locator("#review-box-none")).to_be_visible()
    expect(box.locator("#review-box-none")).to_have_text("Nothing to review: every answer was right.")
    expect(box.locator("#review-box-intro")).to_be_hidden()
    expect(box.locator("li")).to_have_count(0)
    assert hard_to_read(student) == []


def test_an_unanswered_question_is_listed_last(site):
    page = site.instructor()
    upload(page)
    draft(page)
    approve_all_and_publish(page)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    papers = student.locator("#quiz-view fieldset.paper")
    papers.nth(1).get_by_role("radio").nth(1).check()                       # question 2 right, 1 skipped, 3 wrong
    papers.nth(2).get_by_role("radio").nth(0).check()
    student.get_by_role("button", name="Check my answers").click()          # says one is unanswered
    student.get_by_role("button", name="Check my answers").click()          # a second press submits as it is
    expect(student.locator("#score")).to_be_visible()

    items = student.locator("#review-box li")

    expect(items).to_have_count(2)
    expect(items.nth(0)).to_contain_text("Question 3")
    expect(items.nth(1)).to_contain_text("Question 1")
    expect(items.nth(1)).to_contain_text("Not answered.")


def test_the_box_is_in_spanish_too_and_is_gone_when_a_new_attempt_starts(site):
    asking_quiz(site)
    student = result_of(site, "ABB", ("I know this", "I know this", "I know this"))

    student.locator("#lang-switch").click()

    box = student.locator("#review-box")
    expect(box.locator("h3")).to_have_text("Qué repasar")
    expect(box.locator("li").first).to_contain_text("Pregunta 1")
    expect(box.locator("li").first).to_contain_text("Dijiste «Lo sé» y no era correcta.")
    expect(box.locator("li").first.locator(".cite")).to_contain_text("handout.pdf, página 1:")
    student.locator("#again-button").click()
    expect(student.locator("#quiz-view")).to_be_visible()
    expect(box).to_be_hidden()
