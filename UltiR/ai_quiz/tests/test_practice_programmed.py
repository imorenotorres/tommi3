"""Practice with programmed tutors, end to end: topics, exercises, answers, feedback, with no model at all.

The model is replaced by one that fails the test if it is ever called. The handout holds the sentences the two
tutors rest on, on known pages, so every page the feedback names can be checked.
"""

import json

import pytest

from UltiR.ai_quiz import exercises, generation, progress, storage, tutors

from .conftest import cid
from .practice_helpers import PRACTICE, PracticeCourse, tutor_pdf

RANSAC_TOPIC, PR_TOPIC = "RANSAC and its iteration count", "Evaluation with precision and recall"


def code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a model was called during programmed practice")
    monkeypatch.setattr(generation, "call_model", refuse)


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch, pdf=tutor_pdf(), name="handout.pdf")


class Student:
    def __init__(self, course, user="student-1"):
        self.course, self.client, self.token = course, course.client, course.learner(user)

    def topic(self, name):
        return next(t["topic_id"] for t in self.course.topics(self.token) if t["name"] == name)

    def exercise(self, name=RANSAC_TOPIC, level="intermedio", language="es"):
        response = self.client.post(f"{PRACTICE}/exercise", params={"token": self.token},
                                    json={"topic_id": self.topic(name), "level": level, "language": language})
        assert response.status_code == 201, response.text
        return response.json()

    def answer(self, exercise, value, expect=201, **body):
        response = self.client.post(f"{PRACTICE}/exercises/{exercise['exercise_id']}/answer", params={"token": self.token},
                                    json={"value": value, "language": "es", **body})
        assert response.status_code == expect, response.text
        return response.json()


@pytest.fixture
def student(course):
    return Student(course)


def stored(exercise):
    return exercises.load(cid("course-A"), exercise["exercise_id"])


def written(value, exercise):
    return tutors.number(value, "es", 3 if stored(exercise)["form"] == "fraction3" else None)


# ── What is offered ─────────────────────────────────────────────────────────

def test_without_the_model_the_topics_a_tutor_serves_are_offered_and_only_those(student, course):
    assert [t["name"] for t in course.topics(student.token)] == [RANSAC_TOPIC, PR_TOPIC]


def test_an_exercise_is_made_by_the_tutor_with_its_page_and_no_model(student):
    got = student.exercise()

    exercise = got["exercise"]
    assert exercise["type"] == "programado" and exercise["page"] == 2 and exercise["level"] == "intermedio"
    assert exercise["statement"].startswith("Entre dos imágenes hay")
    kept = stored(exercise)
    assert kept["tutor"] == "ransac_iterations" and kept["solution_value"] == tutors.make(
        "ransac_iterations", "intermedio", kept["seed"]).answer
    for private in ("solution_value", "wrong", "params", "seed", "reference_solution"):
        assert private not in json.dumps(exercise)


def test_the_statement_is_in_the_language_of_the_page(student):
    assert student.exercise(language="en")["exercise"]["statement"].startswith("Two images have")


def test_with_the_model_on_a_topic_with_a_tutor_is_still_served_by_the_tutor(student, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_MODEL", "1")

    assert student.exercise(PR_TOPIC)["exercise"]["type"] == "programado"


def test_a_handout_without_the_tutors_sentences_has_no_tutor(client, launch):
    from .pdfs import handout_pdf
    other = PracticeCourse(client, launch, course="course-B", pdf=handout_pdf(), name="other.pdf")

    assert other.topics() == []


# ── Answers and feedback ────────────────────────────────────────────────────

def test_the_right_value_is_correct_and_said_so_from_the_spec(student):
    exercise = student.exercise()["exercise"]
    answer = stored(exercise)["solution_value"]

    got = student.answer(exercise, written(answer, exercise))

    assert (got["verdict"], got["mistake"], got["programmed"], got["ai"]) == ("correcto", None, True, False)
    assert got["feedback"].startswith(f"Correcto: hacen falta N = {int(answer)} iteraciones")
    assert got["review"]["page"] == 2 and got["key_points"] == [] and got["can_see_solution"] is True
    assert got["numeric"] == {"given": answer, "given_text": written(answer, exercise), "right": True}


@pytest.mark.parametrize("mistake, page", [("w_not_ws", 2), ("round_down", 3), ("sample_size", 2),
                                           ("outlier_fraction", 2), ("log_p", 2)])
def test_each_catalogued_mistake_is_named_with_its_why_and_the_page_of_its_sentence(course, mistake, page):
    for user in range(30):                                  # until an exercise in which the mistake applies
        student = Student(course, f"s-{mistake}-{user}")
        exercise = student.exercise()["exercise"]
        wrong = stored(exercise)["wrong"]
        if mistake in wrong:
            break
    got = student.answer(exercise, written(wrong[mistake], exercise))

    spec = tutors.mistake_spec("ransac_iterations", mistake)
    assert got["verdict"] == "incorrecto" and got["mistake"] == {"id": mistake, "text": spec["title_es"]}
    assert f"(pág. {page})" in got["feedback"] and got["review"]["page"] == page
    assert got["next_step"] == spec["next_es"] and got["can_retry"] is True


def test_swapped_precision_and_recall_is_named(student):
    exercise = student.exercise(PR_TOPIC, "basico")["exercise"]
    swapped = stored(exercise)["wrong"]["swapped"]

    got = student.answer(exercise, written(swapped, exercise))

    assert got["mistake"]["text"] == "Intercambiar precisión y exhaustividad"
    assert "(pág. 4)" in got["feedback"]


def test_a_mistake_the_catalogue_does_not_know_is_said_honestly_with_the_page(student):
    exercise = student.exercise()["exercise"]
    kept = stored(exercise)
    stray = next(v for v in range(2, 100000) if v != kept["solution_value"] and v not in kept["wrong"].values())

    got = student.answer(exercise, str(stray))

    assert (got["verdict"], got["mistake"]) == ("incorrecto", None)
    assert got["feedback"].startswith("Incorrecto. Tu resultado no corresponde a ninguno de los errores típicos")
    assert "pág. 2" in got["feedback"]


@pytest.mark.parametrize("value, error", [("setenta", "bad_value_integer"), ("72,5", "bad_value_integer"),
                                          ("", "value_missing"), (None, "value_missing")])
def test_what_is_not_a_whole_number_is_refused_and_no_try_is_used(student, value, error):
    exercise = student.exercise()["exercise"]

    response = student.client.post(f"{PRACTICE}/exercises/{exercise['exercise_id']}/answer",
                                   params={"token": student.token}, json={"value": value})

    assert (response.status_code, code(response)) == (400, error)
    assert student.client.get(f"{PRACTICE}/open", params={"token": student.token}).json()["tries"] == 0


@pytest.mark.parametrize("value", ["275/396", "0,59,2", "cero coma seis"])
def test_what_is_not_a_decimal_is_refused_as_such_and_no_try_is_used(student, value):
    exercise = student.exercise(PR_TOPIC, "basico")["exercise"]

    response = student.client.post(f"{PRACTICE}/exercises/{exercise['exercise_id']}/answer",
                                   params={"token": student.token}, json={"value": value})

    assert (response.status_code, code(response)) == (400, "bad_value_decimal")
    assert student.client.get(f"{PRACTICE}/open", params={"token": student.token}).json()["tries"] == 0


def test_a_percentage_with_its_sign_is_read_as_a_fraction(student):
    exercise = student.exercise(PR_TOPIC, "basico")["exercise"]
    answer = stored(exercise)["solution_value"]

    got = student.answer(exercise, tutors.number(round(answer * 100, 1), "es") + " %")

    assert got["verdict"] == "correcto" and got["numeric"]["given_text"].endswith(" %")


def test_a_text_sent_with_the_value_is_neither_read_nor_kept(student):
    exercise = student.exercise()["exercise"]

    student.answer(exercise, "1", answer="Una frase muy particular de este estudiante.")

    for path in storage.data_root().rglob("*.json"):
        assert "muy particular" not in path.read_text(encoding="utf-8"), path


def test_a_try_is_kept_with_its_verdict_and_mistake_and_nothing_else(student):
    exercise = student.exercise()["exercise"]
    wrong = stored(exercise)["wrong"]
    student.answer(exercise, written(wrong["round_down"], exercise))

    record = progress.load(cid("course-A"), progress.owner(cid("course-A"), "student-1"))
    [kept] = record["exercises"][exercise["exercise_id"]]["tries"]
    assert (kept["verdict"], kept["mistake"], kept["programmed"], kept["statuses"]) == ("incorrecto", "round_down", True, {})


# ── Tries, solution, the next exercise ──────────────────────────────────────

def test_two_tries_then_the_worked_solution(student):
    exercise = student.exercise()["exercise"]
    kept = stored(exercise)
    student.answer(exercise, written(kept["wrong"]["w_not_ws"], exercise))
    second = student.answer(exercise, written(kept["wrong"]["log_p"], exercise))
    assert (second["try"], second["can_retry"], second["can_see_solution"]) == (2, False, True)

    shown = student.client.get(f"{PRACTICE}/exercises/{exercise['exercise_id']}/solution",
                               params={"token": student.token}).json()

    assert shown["value_text"] == str(int(kept["solution_value"]))
    assert "Redondeando hacia arriba" in shown["reference_solution"] and "La fracción de inliers es w" in shown["reference_solution"]


def test_the_next_exercise_comes_back_to_the_mistake_made(student):
    exercise = student.exercise(PR_TOPIC, "avanzado")["exercise"]
    student.answer(exercise, written(stored(exercise)["wrong"]["arithmetic_mean"], exercise))

    following = student.exercise(PR_TOPIC, "avanzado")

    assert following["aim"] == "mistake_last" and stored(following["exercise"])["params"]["asks"] == "F1"


def test_after_a_swap_the_next_exercise_asks_precision_or_recall(student):
    exercise = student.exercise(PR_TOPIC, "basico")["exercise"]
    student.answer(exercise, written(stored(exercise)["wrong"]["swapped"], exercise))

    following = student.exercise(PR_TOPIC, "avanzado")

    assert following["aim"] == "mistake_last" and stored(following["exercise"])["params"]["asks"] in ("P", "R")


def test_an_unfinished_programmed_exercise_is_opened_again(student):
    exercise = student.exercise()["exercise"]

    opened = student.client.get(f"{PRACTICE}/open", params={"token": student.token}).json()

    assert opened["exercise"]["exercise_id"] == exercise["exercise_id"] and opened["exercise"]["type"] == "programado"


def test_the_daily_limit_counts_programmed_exercises_too(student, monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_DAILY", "1")
    student.exercise()

    response = student.client.post(f"{PRACTICE}/exercise", params={"token": student.token},
                                   json={"topic_id": student.topic(RANSAC_TOPIC)})

    assert (response.status_code, code(response)) == (429, "daily_limit")


def test_the_instructors_list_of_model_exercises_leaves_programmed_ones_out(client, student, course):
    student.exercise()

    assert client.get(f"{PRACTICE}/pool", params={"token": course.instructor}).json()["exercises"] == []
