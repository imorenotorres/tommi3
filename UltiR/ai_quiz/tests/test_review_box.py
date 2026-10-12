""""What to review": after an attempt, the questions the student got wrong, the ones they were sure of first.

Worked out by the server from the graded attempt. No model is asked, and the list says nothing
the result does not already say: it is an order, with a reason per question.
"""

import pytest

from .test_attempts import ATTEMPTS, Course, submit
from .test_confidence import asking_quiz, ids


@pytest.fixture
def course(client, launch):
    return Course(client, launch)


def attempt(client, course, quiz, picks, levels=None, user="student-1"):
    """Submit one attempt. `picks` is a letter per question ("-" leaves it out); the key is B in every fake question."""
    answers = {q: pick for q, pick in zip(ids(quiz), picks) if pick != "-"}
    said = {"confidence": {q: level for q, level in zip(ids(quiz), levels) if q in answers}} if levels else {}
    response = submit(client, course.learner(user=user), quiz, answers, **said)
    assert response.status_code == 201, response.text
    return response.json()


def listed(result):
    return [(item["number"], item["reason"]) for item in result["review"]]


def test_with_every_answer_right_there_is_nothing_to_review(client, course):
    quiz = course.published_quiz(3)

    assert attempt(client, course, quiz, "BBB")["review"] == []


def test_wrong_answers_are_listed_in_the_order_of_the_quiz_and_unanswered_ones_last(client, course):
    quiz = course.published_quiz(4)

    result = attempt(client, course, quiz, "-ABC")

    assert listed(result) == [(2, "wrong"), (4, "wrong"), (1, "skipped")]


def test_in_a_quiz_that_asks_the_answers_that_were_sure_and_wrong_come_first(client, course):
    quiz = asking_quiz(course, 5)

    result = attempt(client, course, quiz, "AB-CD", ("guess", "sure", None, "sure", "fairly"))

    assert listed(result) == [(4, "sure_wrong"), (1, "wrong"), (5, "wrong"), (3, "skipped")]


def test_an_answer_that_was_sure_and_right_is_not_listed(client, course):
    quiz = asking_quiz(course, 2)

    result = attempt(client, course, quiz, "BA", ("sure", "guess"))

    assert listed(result) == [(2, "wrong")]


def test_each_entry_names_a_question_of_the_result_and_holds_nothing_else(client, course):
    quiz = asking_quiz(course, 3)

    result = attempt(client, course, quiz, "ABA", ("sure", "sure", "guess"))

    by_id = {item["question_id"]: number for number, item in enumerate(result["results"], start=1)}
    for entry in result["review"]:
        assert set(entry) == {"question_id", "number", "reason"}
        assert by_id[entry["question_id"]] == entry["number"]
        assert not result["results"][entry["number"] - 1]["correct"]


def test_reading_the_attempt_again_gives_the_same_list(client, course):
    quiz = asking_quiz(course, 3)
    first = attempt(client, course, quiz, "AAB", ("fairly", "sure", "sure"))

    again = client.get(f"{ATTEMPTS}/{first['attempt_id']}", params={"token": course.learner()}).json()

    assert again["review"] == first["review"] and listed(again) == [(2, "sure_wrong"), (1, "wrong")]


def test_no_model_is_asked_for_it(client, course, fake_llm):
    quiz = asking_quiz(course, 3)
    before = len(fake_llm.calls)

    result = attempt(client, course, quiz, "AAA", ("sure", "sure", "sure"))
    client.get(f"{ATTEMPTS}/{result['attempt_id']}", params={"token": course.learner()})

    assert len(result["review"]) == 3
    assert len(fake_llm.calls) == before
