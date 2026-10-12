"""The class summary for the instructor: totals per published question, and nothing about one person.

Per question: how many answers, how many right, how many "sure and wrong", the wrong option that
was chosen most, and the passage of the document the question rests on, with its page. A question
shows no number at all until enough students have answered it (AI_QUIZ_MIN_GROUP, default 3).
"""

import pytest

from UltiR.ai_quiz import config

from .test_attempts import QUIZZES, Course, submit
from .test_confidence import asking_quiz, ids, summary

NUMBERS = {"answered", "correct", "chosen", "top_wrong", "sure", "sure_wrong"}


@pytest.fixture
def course(client, launch):
    return Course(client, launch)


def answer(client, course, quiz, user, picks, levels=None):
    """One attempt by `user`. `picks` is a letter per question, "-" leaves the question out."""
    answers = {q: pick for q, pick in zip(ids(quiz), picks) if pick != "-"}
    said = {"confidence": {q: level for q, level in zip(ids(quiz), levels) if q in answers}} if levels else {}
    response = submit(client, course.learner(user=user), quiz, answers, **said)
    assert response.status_code == 201, response.text


# ── The setting ─────────────────────────────────────────────────────────────

def test_the_minimum_group_is_three_unless_the_setting_says_otherwise(monkeypatch):
    assert config.min_group() == 3
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", "5")
    assert config.min_group() == 5
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", " 1 ")
    assert config.min_group() == 1


@pytest.mark.parametrize("value", ["0", "-2", "2.5", "three", "", "1e3", "٥", "5 students"])
def test_a_setting_that_is_not_a_whole_number_of_at_least_one_counts_as_three(monkeypatch, value):
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", value)

    assert config.min_group() == 3


# ── Too few answers ─────────────────────────────────────────────────────────

def test_with_two_students_no_question_shows_a_number(client, course):
    quiz = course.published_quiz(2, title="Week 7")
    answer(client, course, quiz, "s-1", "AB")
    answer(client, course, quiz, "s-2", "AA")

    report = summary(client, course, quiz)

    assert (report["attempts"], report["learners"], report["min_group"]) == (2, 2, 3)
    assert report["average_percent"] is None                       # two students: an average would say too much
    for question in report["questions"]:
        assert question["too_few"] is True
        assert not NUMBERS & set(question)


def test_with_three_students_the_numbers_are_there(client, course):
    quiz = course.published_quiz(2, title="Week 7")
    for user, picks in (("s-1", "AB"), ("s-2", "AA"), ("s-3", "BC")):
        answer(client, course, quiz, user, picks)

    report = summary(client, course, quiz)

    assert report["average_percent"] == 33                         # 1 of 2, 0 of 2, 1 of 2
    first, second = report["questions"]
    assert "too_few" not in first and "too_few" not in second
    assert (first["answered"], first["correct"], first["chosen"]) == (3, 1, {"A": 2, "B": 1, "C": 0, "D": 0})
    assert (second["answered"], second["correct"], second["chosen"]) == (3, 1, {"A": 1, "B": 1, "C": 1, "D": 0})


def test_the_minimum_is_counted_per_question(client, course):
    quiz = course.published_quiz(2)
    for user, picks in (("s-1", "AB"), ("s-2", "A-"), ("s-3", "BB")):   # the second question has two answers only
        answer(client, course, quiz, user, picks)

    first, second = summary(client, course, quiz)["questions"]

    assert first["answered"] == 3
    assert second["too_few"] is True and not NUMBERS & set(second)


def test_the_minimum_counts_students_not_attempts(client, course):
    quiz = course.published_quiz(2)
    for _ in range(4):
        answer(client, course, quiz, "s-1", "AA")                  # one student, four tries
    answer(client, course, quiz, "s-2", "BB")

    report = summary(client, course, quiz)

    assert (report["attempts"], report["learners"]) == (5, 2)
    assert report["average_percent"] is None
    assert all(q["too_few"] is True for q in report["questions"])


def test_an_instructors_own_try_does_not_count_towards_the_minimum(client, course):
    quiz = course.published_quiz(2)
    answer(client, course, quiz, "s-1", "AB")
    answer(client, course, quiz, "s-2", "AB")
    submit(client, course.instructor, quiz, dict.fromkeys(ids(quiz), "B"))

    assert all(q["too_few"] is True for q in summary(client, course, quiz)["questions"])


def test_answers_to_an_earlier_version_do_not_count_towards_the_minimum(client, course):
    quiz = course.published_quiz(2)
    for user in ("s-1", "s-2", "s-3"):
        answer(client, course, quiz, user, "AB")
    course.edit(quiz, 0, question="A rewritten first question?")
    course.edit(quiz, 0, review_status="approved")
    again = course.publish(quiz)
    answer(client, course, again, "s-1", "AB")

    assert all(q["too_few"] is True for q in summary(client, course, again)["questions"])


def test_the_setting_one_shows_the_numbers_after_the_first_student(client, course, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", "1")
    quiz = course.published_quiz(2)
    answer(client, course, quiz, "s-1", "AB")

    report = summary(client, course, quiz)

    assert (report["min_group"], report["average_percent"]) == (1, 50)
    assert [q["answered"] for q in report["questions"]] == [1, 1]


def test_a_question_nobody_answered_shows_no_number_whatever_the_setting(client, course, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", "1")
    quiz = course.published_quiz(2)
    answer(client, course, quiz, "s-1", "A-")

    first, second = summary(client, course, quiz)["questions"]

    assert first["answered"] == 1 and second["too_few"] is True


# ── What a question shows once there are enough answers ─────────────────────

def test_the_wrong_option_chosen_most_is_named_with_its_text_and_its_count(client, course):
    quiz = course.published_quiz(3)
    for user, picks in (("s-1", "CAB"), ("s-2", "CDB"), ("s-3", "BDB"), ("s-4", "AAB")):
        answer(client, course, quiz, user, picks)

    first, second, third = summary(client, course, quiz)["questions"]

    option = {o["id"]: o["text"] for o in quiz["questions"][0]["options"]}
    assert first["top_wrong"] == {"id": "C", "text": option["C"], "count": 2}
    assert second["top_wrong"]["id"] == "A" and second["top_wrong"]["count"] == 2     # A and D tie: the first letter
    assert third["top_wrong"] is None                                                # everybody was right
    assert first["correct_option_id"] == "B"


def test_the_key_is_never_the_most_chosen_wrong_option(client, course):
    quiz = course.published_quiz(1)
    for user, pick in (("s-1", "B"), ("s-2", "B"), ("s-3", "B"), ("s-4", "D")):
        answer(client, course, quiz, user, pick)

    (question,) = summary(client, course, quiz)["questions"]

    assert question["top_wrong"] == {"id": "D", "text": quiz["questions"][0]["options"][3]["text"], "count": 1}


def test_each_question_comes_with_its_source_passage_and_page(client, course):
    quiz = course.published_quiz(2)

    report = summary(client, course, quiz)                         # the passage needs no answers: it is the instructor's own document

    for shown, stored in zip(report["questions"], quiz["questions"], strict=True):
        assert shown["source"] == {"doc_label": "handout.pdf", "page": stored["source"]["page"],
                                   "excerpt": stored["source"]["excerpt"], "mode": "text", "located": True}
        assert stored["source"]["page"] >= 1 and len(stored["source"]["excerpt"]) > 30


def test_a_passage_the_server_did_not_locate_is_marked_as_such(client, course, fake_llm):
    from .fake_llm import good_reply

    fake_llm.queue(lambda messages: good_reply(messages, 1, excerpt="words the document does not contain " * 3))
    quiz = course.draft(1)
    course.edit(quiz, 0, accept_ungrounded=True, review_status="approved")
    published = course.publish(quiz)

    (question,) = summary(client, course, published)["questions"]

    assert len(fake_llm.calls) == 1
    assert question["source"]["located"] is False


def test_sure_and_wrong_is_counted_once_there_are_enough_answers(client, course):
    quiz = asking_quiz(course, 2)
    for user, picks, levels in (("s-1", "AB", ("sure", "sure")), ("s-2", "AA", ("sure", "fairly")),
                                ("s-3", "BA", ("sure", "sure"))):
        answer(client, course, quiz, user, picks, levels)

    first, second = summary(client, course, quiz)["questions"]

    assert (first["sure"], first["sure_wrong"]) == (3, 2)
    assert (second["sure"], second["sure_wrong"]) == (2, 1)


def test_sure_and_wrong_is_not_shown_below_the_minimum(client, course):
    quiz = asking_quiz(course, 2)
    answer(client, course, quiz, "s-1", "AA", ("sure", "sure"))

    assert all(q["too_few"] is True and not NUMBERS & set(q) for q in summary(client, course, quiz)["questions"])


def test_the_summary_holds_totals_and_nothing_of_a_person(client, course):
    quiz = asking_quiz(course, 2)
    for number in (1, 2, 3):
        learner = course.learner(user=f"student-471{number}", name=f"Synthetic Student {number}",
                                 email=f"s{number}@example.invalid")
        assert submit(client, learner, quiz, dict.fromkeys(ids(quiz), "A"),
                      confidence=dict.fromkeys(ids(quiz), "sure")).status_code == 201

    response = client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": course.instructor})

    assert set(response.json()) == {"quiz_id", "title", "current_revision", "confidence", "attempts", "learners",
                                    "average_percent", "min_group", "questions"}
    for question in response.json()["questions"]:
        assert set(question) == {"question_id", "question", "correct_option_id", "source", "answered", "correct",
                                 "chosen", "top_wrong", "sure", "sure_wrong"}
    for private in ("student-471", "Synthetic Student", "example.invalid", "owner", "attempt_id", "submitted_at"):
        assert private not in response.text
