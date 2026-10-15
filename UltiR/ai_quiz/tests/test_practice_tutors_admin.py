"""The programmed tutors in the instructor's Práctica tab: each spec to review, where its sentences are in the
course's handout, and how often each mistake was recognised, in totals that leave out groups below the minimum."""

import pytest

from UltiR.ai_quiz import generation, tutors

from .practice_helpers import PRACTICE, PracticeCourse, tutor_pdf
from .test_practice_programmed import PR_TOPIC, Student, stored, written


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")

    def refuse(*args, **kwargs):
        raise AssertionError("a model was called")
    monkeypatch.setattr(generation, "call_model", refuse)


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch, pdf=tutor_pdf(), name="handout.pdf")


def review(course):
    response = course.client.get(f"{PRACTICE}/tutors", params={"token": course.instructor})
    assert response.status_code == 200, response.text
    return response.json()


def by_name(found):
    return {t["tutor"]: t for t in found["tutors"]}


def answered(course, user, mistake=None, right=False):
    """One student's try at a basic precision exercise: the given mistake, the right value, or a stray value."""
    student = Student(course, user)
    exercise = student.exercise(PR_TOPIC, "basico")["exercise"]
    kept = stored(exercise)
    if right:
        value = kept["solution_value"]
    elif mistake:
        value = kept["wrong"][mistake]
    else:
        value = next(v / 1000 for v in range(1, 1000) if all(abs(v / 1000 - w) > 0.01 for w in
                                                               [kept["solution_value"], *kept["wrong"].values()]))
    return student.answer(exercise, written(value, exercise))


def test_each_tutor_is_shown_with_the_texts_of_its_spec_in_both_languages(course):
    found = by_name(review(course))

    assert list(found) == list(tutors.NAMES)
    pr, spec = found["precision_recall"], tutors.spec("precision_recall")
    assert pr["title"] == {"es": spec["skill"]["title_es"], "en": spec["skill"]["title_en"]}
    assert pr["formula"] == spec["skill"]["formula"] and pr["file"] == "tutors/precision_recall.toml"
    assert [m["id"] for m in pr["mistakes"]] == [m["id"] for m in spec["mistakes"]]
    swapped = pr["mistakes"][0]
    assert swapped["why"]["es"] == spec["mistakes"][0]["why_es"] and swapped["next"]["en"] == spec["mistakes"][0]["next_en"]
    assert pr["unknown"]["text"]["es"] == spec["unknown"]["es"] and pr["right"]["next"]["es"] == spec["right"]["next_es"]
    assert [level["level"] for level in pr["levels"]] == list(tutors.LEVELS)


def test_where_each_text_rests_in_the_handout_is_found_in_this_course(course):
    found = by_name(review(course))

    ransac = found["ransac_iterations"]
    assert ransac["topic"] == "RANSAC and its iteration count" and ransac["where"]["page"] == 2
    assert ransac["where"]["doc_label"] == "handout.pdf"
    pages = {m["id"]: m["where"]["page"] for m in ransac["mistakes"]}
    assert pages["round_down"] == 3 and pages["w_not_ws"] == 2
    assert {m["where"]["page"] for m in found["precision_recall"]["mistakes"]} == {4}


def test_a_course_whose_handout_lacks_the_sentences_shows_the_tutors_found_nowhere(client, launch):
    from .pdfs import handout_pdf
    other = PracticeCourse(client, launch, course="course-B", pdf=handout_pdf(), name="other.pdf")

    for tutor in review(other)["tutors"]:
        assert tutor["topic"] is None and tutor["where"] is None
        assert all(m["where"] is None for m in tutor["mistakes"])


def test_nothing_is_counted_before_anyone_answers(course):
    pr = by_name(review(course))["precision_recall"]

    assert pr["answered"] is None and pr["right"]["detected"] is None
    assert all(m["detected"] is None for m in pr["mistakes"])


def test_a_mistake_found_in_three_students_is_counted_and_one_in_two_is_not_shown(course):
    for user in ("s1", "s2", "s3"):
        answered(course, user, "swapped")
    for user in ("s4", "s5"):
        answered(course, user, "complement")
    for user in ("s6", "s7", "s8"):
        answered(course, user, right=True)

    found = review(course)
    pr = by_name(found)["precision_recall"]
    mistakes = {m["id"]: m["detected"] for m in pr["mistakes"]}

    assert found["min_group"] == 3
    assert mistakes["swapped"] == {"tries": 3, "students": 3}
    assert mistakes["complement"] == {"too_few": True}
    assert pr["right"]["detected"] == {"tries": 3, "students": 3}
    assert pr["answered"] == {"tries": 8, "students": 8} and pr["unknown"]["detected"] is None


def test_a_wrong_value_no_mistake_gives_is_counted_apart(course):
    for user in ("s1", "s2", "s3"):
        assert answered(course, user)["mistake"] is None

    pr = by_name(review(course))["precision_recall"]

    assert pr["unknown"]["detected"] == {"tries": 3, "students": 3}


def test_every_try_counts_and_a_student_counts_once(course):
    student = Student(course, "s1")
    exercise = student.exercise(PR_TOPIC, "basico")["exercise"]
    student.answer(exercise, written(stored(exercise)["wrong"]["swapped"], exercise))
    student.answer(exercise, written(stored(exercise)["wrong"]["swapped"], exercise))
    for user in ("s2", "s3"):
        answered(course, user, "swapped")

    pr = by_name(review(course))["precision_recall"]

    assert pr["mistakes"][0]["detected"] == {"tries": 4, "students": 3}


def test_the_minimum_group_is_the_courses_setting(course, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_MIN_GROUP", "2")
    for user in ("s4", "s5"):
        answered(course, user, "complement")

    pr = by_name(review(course))["precision_recall"]

    assert {m["id"]: m["detected"] for m in pr["mistakes"]}["complement"] == {"tries": 2, "students": 2}


def test_a_tutors_mistakes_do_not_reach_the_list_of_model_mistakes(course):
    for user in ("s1", "s2", "s3"):
        answered(course, user, "swapped")

    summary = course.client.get(f"{PRACTICE}/summary", params={"token": course.instructor}).json()

    assert summary["mistakes"] == [] and summary["hidden_mistakes"] == 0


def test_a_learner_may_not_see_the_tutors(course):
    response = course.client.get(f"{PRACTICE}/tutors", params={"token": course.learner()})

    assert response.status_code == 403


def test_a_preview_by_the_instructor_is_not_counted(course):
    preview = Student(course)
    preview.token = course.instructor                       # the instructor trying the student's view
    exercise = preview.exercise(PR_TOPIC, "basico")["exercise"]
    preview.answer(exercise, written(stored(exercise)["wrong"]["swapped"], exercise))

    assert by_name(review(course))["precision_recall"]["answered"] is None
