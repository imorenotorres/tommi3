"""The class summary on the instructor's page, in a browser."""

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from .test_browser import approve_all_and_publish, draft, unlabelled_controls, upload  # noqa: E402
from .test_confidence_browser import answer, asking_quiz  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402

LEVEL = {"s": "I know this", "f": "I think so", "g": "I am guessing"}


def published(site):
    """An instructor page on which a three-question quiz that does not ask "how sure" has just been published."""
    page = site.instructor()
    upload(page)
    draft(page)
    approve_all_and_publish(page)
    return page


def take(site, user, picks, levels=None):
    """One student answers the only published quiz: a letter per question, and a level per question if it asks."""
    student = site.student(user=user)
    student.locator("#quizzes button").first.click()
    expect(student.locator("#quiz-view fieldset.paper")).to_have_count(len(picks))
    answer(student, picks, [LEVEL[level] for level in levels] if levels else [None] * len(picks))
    student.get_by_role("button", name="Check my answers").click()
    expect(student.locator("#score")).to_be_visible()
    student.close()


def review_again(teacher):
    teacher.reload()
    teacher.get_by_role("button", name="Review “Week 7”").click()
    expect(teacher.locator("#class-summary")).to_be_visible()
    return teacher.locator("#class-table tbody tr")


def test_nothing_is_shown_before_anybody_has_answered(site):
    teacher = published(site)

    expect(teacher.locator("#summary-line")).to_have_text("No student has tried this quiz yet.")
    expect(teacher.locator("#class-summary")).to_be_hidden()


def test_with_one_student_the_page_says_too_few_answers_and_shows_no_number(site):
    teacher = published(site)
    take(site, "student-1", "ABB")

    rows = review_again(teacher)

    expect(teacher.locator("#summary-line")).to_have_text(
        "So far: 1 attempts by 1 students. Totals appear once at least 3 students have answered.")
    expect(teacher.locator("#class-summary h3")).to_have_text("Class summary")
    expect(teacher.locator("#class-hint")).to_contain_text("Totals only, no names.")
    expect(teacher.locator("#class-hint")).to_contain_text("at least 3 students")
    expect(rows).to_have_count(3)
    for i in range(3):
        assert rows.nth(i).locator("td").all_inner_texts() == ["Too few answers yet."]
        expect(rows.nth(i).locator("th")).to_contain_text("handout.pdf, page")      # the passage is the instructor's own
    assert unlabelled_controls(teacher) == [] and hard_to_read(teacher) == [] and small_buttons(teacher) == []


def test_with_three_students_each_question_shows_its_totals_its_most_chosen_wrong_option_and_its_passage(site):
    teacher = published(site)
    for user, picks in (("student-1", "ABB"), ("student-2", "ABC"), ("student-3", "BBC")):   # the key is B everywhere
        take(site, user, picks)

    rows = review_again(teacher)

    expect(teacher.locator("#summary-line")).to_contain_text("3 attempts by 3 students, 56 % correct on average.")
    headers = teacher.locator("#class-table thead th").all_inner_texts()
    assert headers == ["Question", "Answers", "Correct", "Most chosen wrong option"]       # this version does not ask "how sure"
    cells = [rows.nth(i).locator("td").all_inner_texts() for i in range(3)]
    assert [c[:2] for c in cells] == [["3", "1"], ["3", "3"], ["3", "1"]]
    assert cells[0][2] == "A. Statement 1.1 that the material does not make (chosen 2 times)"
    assert cells[1][2] == "None: every answer was right."
    assert cells[2][2] == "C. Statement 3.3 that the material does not make (chosen 2 times)"
    first = rows.nth(0).locator("th")
    expect(first).to_contain_text("1. Question 1 about source S1")
    expect(first.locator(".cite")).to_contain_text("handout.pdf, page 1:")
    assert len(first.locator(".cite q").inner_text()) > 30                                  # the passage itself
    # The question and its passage are running text and get most of the width; the counts stay narrow.
    widths = teacher.evaluate("""() => { const row = document.querySelector('#class-table tbody tr');
        const table = document.querySelector('#class-table table').getBoundingClientRect().width;
        return {question: row.querySelector('th').getBoundingClientRect().width / table,
                count: row.querySelector('td.num').getBoundingClientRect().width / table,
                weight: getComputedStyle(row.querySelector('th')).fontWeight,
                layout: getComputedStyle(document.querySelector('#class-table table')).tableLayout}; }""")
    assert 0.40 < widths["question"] < 0.44 and widths["count"] < 0.15 and widths["weight"] == "400", widths
    assert widths["layout"] == "fixed"             # so that a long option cannot take the room from the question
    assert unlabelled_controls(teacher) == [] and hard_to_read(teacher) == [] and small_buttons(teacher) == []


def test_a_version_that_asks_how_sure_has_the_sure_and_wrong_column(site):
    teacher = asking_quiz(site)
    for user, picks, levels in (("student-1", "ABB", "ssg"), ("student-2", "ABA", "sfs"), ("student-3", "BBA", "sss")):
        take(site, user, picks, levels)

    rows = review_again(teacher)

    headers = teacher.locator("#class-table thead th").all_inner_texts()
    assert headers == ["Question", "Answers", "Correct", "Sure and wrong", "Most chosen wrong option"]
    assert [rows.nth(i).locator("td").all_inner_texts()[:3] for i in range(3)] == [
        ["3", "1", "2"], ["3", "3", "0"], ["3", "1", "2"]]


def test_the_class_summary_is_in_spanish_too(site):
    teacher = published(site)
    for user in ("student-1", "student-2", "student-3"):
        take(site, user, "ABB")
    review_again(teacher)

    teacher.locator("#lang-switch").click()

    expect(teacher.locator("#class-summary h3")).to_have_text("Resumen de la clase")
    expect(teacher.locator("#class-hint")).to_contain_text("Solo totales, sin nombres.")
    assert teacher.locator("#class-table thead th").all_inner_texts() == [
        "Pregunta", "Respuestas", "Correctas", "Opción incorrecta más elegida"]
    expect(teacher.locator("#class-table tbody tr").first.locator("td").last).to_contain_text("(elegida 3 veces)")
