"""Commit first, in a browser: the instructor's switch, the student's "How sure are you?", the counts."""

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from .test_browser import approve_all_and_publish, draft, focused, tab_to, unlabelled_controls, upload  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402


def asking_quiz(site):
    """An instructor page on which a three-question quiz that asks "how sure" has just been published."""
    page = site.instructor()
    upload(page)
    draft(page)
    switch = page.get_by_label("Ask students how sure they are")
    expect(switch).not_to_be_checked()                                # off by default
    switch.check()
    expect(page.locator("#status")).to_contain_text("Students will be asked how sure they are")
    approve_all_and_publish(page)
    return page


def answer(student, picks, levels):
    """Tick option `picks[i]` and, where given, the level `levels[i]` for question i."""
    papers = student.locator("#quiz-view fieldset.paper")
    for i, pick in enumerate(picks):
        papers.nth(i).get_by_role("radio").nth("ABCD".index(pick)).check()
        if levels[i]:
            papers.nth(i).locator(".confidence").get_by_label(levels[i], exact=True).check()


def test_a_student_says_how_sure_before_checking_and_sees_what_became_of_it(site, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", "1")                       # one student here; small groups have their own tests
    teacher = asking_quiz(site)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)

    expect(student.locator("#confidence-note")).to_contain_text("It does not change your score")
    expect(student.locator("#quiz-view fieldset.confidence")).to_have_count(3)
    expect(student.locator("#quiz-view fieldset.confidence").first).to_contain_text("How sure are you?")
    assert student.locator("#quiz-view fieldset.confidence").first.get_by_role("radio").count() == 3
    assert unlabelled_controls(student) == [] and hard_to_read(student) == [] and small_buttons(student) == []

    # Answers without "how sure": nothing is checked, the page says what is missing and goes there.
    answer(student, "ABB", (None, None, None))                         # the key is B in every fake question
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#status")).to_contain_text("Say how sure you are for every question you answered. Still missing: 3.")
    expect(student.locator("#result-view")).to_be_hidden()
    assert focused(student)["id"].startswith("sure-") and focused(student)["id"].endswith("-sure")

    answer(student, "ABB", ("I know this", "I know this", "I am guessing"))
    student.get_by_role("button", name="Check my answers").click()

    expect(student.locator("#score")).to_have_text("2 of 3 correct")   # being sure changed nothing
    expect(student.locator("#calibration")).to_have_text(
        "Answers you marked “I know this”: 2. Wrong among them: 1. These are the ones to look at again.")
    said = student.locator("#results .said")
    assert said.all_inner_texts() == ["You said: I know this.", "You said: I know this.", "You said: I am guessing."]
    assert hard_to_read(student) == []

    # The instructor: per question, how many answers, how many right, and how many were sure and wrong.
    teacher.reload()
    teacher.get_by_role("button", name="Review “Week 7”").click()
    expect(teacher.locator("#class-summary")).to_be_visible()
    rows = teacher.locator("#class-table tbody tr")
    expect(rows).to_have_count(3)
    assert [rows.nth(i).locator("td").all_inner_texts()[:3] for i in range(3)] == [
        ["1", "0", "1"], ["1", "1", "0"], ["1", "1", "0"]]
    expect(teacher.locator("#class-summary")).to_contain_text("no names.")
    expect(teacher.get_by_label("Ask students how sure they are")).to_be_checked()
    assert unlabelled_controls(teacher) == [] and hard_to_read(teacher) == []


def test_a_quiz_that_was_not_switched_on_asks_nothing(site):
    teacher = site.instructor()
    upload(teacher)
    draft(teacher)
    approve_all_and_publish(teacher)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)

    expect(student.locator("#quiz-view fieldset.confidence")).to_have_count(0)
    expect(student.locator("#confidence-note")).to_be_hidden()
    answer(student, "ABB", (None, None, None))
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#score")).to_have_text("2 of 3 correct")
    expect(student.locator("#calibration")).to_be_hidden()
    expect(student.locator("#results .said")).to_have_count(0)
    teacher.reload()
    teacher.get_by_role("button", name="Review “Week 7”").click()
    expect(teacher.locator("#summary-line")).to_contain_text("1 attempts")
    expect(teacher.locator("#class-summary")).to_be_visible()
    assert "Sure and wrong" not in teacher.locator("#class-table thead").inner_text()   # this version did not ask


def test_all_sure_answers_right_is_said_too(site):
    asking_quiz(site)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)

    answer(student, "BBA", ("I know this", "I know this", "I think so"))
    student.get_by_role("button", name="Check my answers").click()

    expect(student.locator("#calibration")).to_have_text("Answers you marked “I know this”: 2. All of them were right.")


def test_the_switch_can_be_turned_off_again_and_says_when_it_applies(site):
    page = asking_quiz(site)

    page.get_by_label("Ask students how sure they are").uncheck()

    expect(page.locator("#status")).to_contain_text("Students will no longer be asked, from the next version you publish.")
    expect(page.get_by_label("Ask students how sure they are")).not_to_be_checked()
    page.get_by_role("button", name="Publish approved questions").click()
    expect(page.locator("#status")).to_contain_text("Published as version 2")


def test_how_sure_is_asked_in_spanish_and_keeps_what_was_ticked_when_the_language_changes(site):
    asking_quiz(site)
    student = site.student()
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    answer(student, "ABB", ("I know this", "I think so", "I am guessing"))

    student.locator("#lang-switch").click()

    first = student.locator("#quiz-view fieldset.confidence").first
    expect(first).to_contain_text("¿Qué seguridad tienes?")
    expect(first.get_by_label("Lo sé", exact=True)).to_be_checked()
    expect(student.locator("#quiz-view fieldset.confidence").nth(1).get_by_label("Creo que sí", exact=True)).to_be_checked()
    expect(student.locator("#quiz-view fieldset.confidence").nth(2).get_by_label("Lo intento adivinar", exact=True)).to_be_checked()
    student.get_by_role("button", name="Comprobar mis respuestas").click()
    expect(student.locator("#calibration")).to_contain_text("Respuestas que marcaste con «Lo sé»: 1. Incorrectas entre ellas: 1.")
    expect(student.locator("#results .said").first).to_have_text("Dijiste: Lo sé.")


def test_a_student_can_say_how_sure_with_the_keyboard_alone(site):
    asking_quiz(site)
    student = site.student()
    expect(student.locator("#quizzes table")).to_be_visible()

    student.keyboard.press("Tab")
    tab_to(student, lambda e: e["tag"] == "BUTTON" and e["text"] == "Start")
    student.keyboard.press("Enter")
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(3)
    for _ in range(3):
        tab_to(student, lambda e: e["type"] == "radio" and e["id"].startswith("answer-"))
        student.keyboard.press("Space")
        student.keyboard.press("ArrowDown")                            # from A to B, the key
        tab_to(student, lambda e: e["type"] == "radio" and e["id"].startswith("sure-"))
        student.keyboard.press("Space")                                # "I know this"
    tab_to(student, lambda e: e["id"] == "submit-button")
    student.keyboard.press("Enter")

    expect(student.locator("#score")).to_have_text("3 of 3 correct")
    expect(student.locator("#calibration")).to_have_text("Answers you marked “I know this”: 3. All of them were right.")
    assert focused(student)["id"] == "result-heading"
