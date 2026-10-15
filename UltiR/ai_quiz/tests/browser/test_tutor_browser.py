"""A programmed tutor's exercise in a browser: the value only, a mistake named with its page, the next exercise
aimed at it. No model: one that fails the test if it is called stands in for it."""

import httpx
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from UltiR.ai_quiz import exercises, generation, tutors  # noqa: E402

from ..conftest import BASE, cid  # noqa: E402
from ..practice_helpers import tutor_pdf  # noqa: E402
from .test_browser import unlabelled_controls  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")

    def refuse(*args, **kwargs):
        raise AssertionError("a model was called during programmed practice")
    monkeypatch.setattr(generation, "call_model", refuse)


def tutor_course(site):
    token = site.token("Instructor", user="teacher-1")
    response = httpx.post(f"{site.url}{BASE}/api/documents", params={"token": token},
                          files={"file": ("handout.pdf", tutor_pdf(), "application/pdf")})
    assert response.status_code == 201, response.text
    assert httpx.put(f"{site.url}{BASE}/api/practice/settings", params={"token": token},
                     json={"enabled": True}).status_code == 200


def tutor_exercise(page, topic="Evaluation with precision and recall", level="Básico"):
    option = page.locator("#practice-topic option", has_text=topic)
    page.get_by_label("Tema").select_option(option.get_attribute("value"))
    page.get_by_label(level, exact=True).check()
    page.get_by_role("button", name="Generar ejercicio").click()
    expect(page.locator("#practice-exercise")).to_be_visible()


def shown_exercise(page):
    """The stored exercise the page shows: the newest one in the course."""
    return exercises.all_exercises(cid("course-A"))[-1]


def test_a_swap_is_named_with_its_page_the_right_value_is_said_and_the_next_exercise_comes_back_to_it(site):
    tutor_course(site)
    page = site.open("/student", site.token("Learner", user="student-1"), locale="es-ES")
    page.get_by_role("button", name="Practicar").click()
    assert [o.inner_text() for o in page.locator("#practice-topic option").all()][1:] == [
        "RANSAC and its iteration count (págs. 2–3)", "Evaluation with precision and recall (página 4)"]

    tutor_exercise(page)

    expect(page.locator("#practice-ai-label")).to_have_text("Ejercicio programado a partir del apunte · pág. 4")
    expect(page.locator("#practice-meta")).to_have_text("Evaluation with precision and recall · Básico · Calculado")
    expect(page.locator("#practice-note")).to_contain_text("sin modelo de lenguaje")
    expect(page.locator("#practice-answer-field")).to_be_hidden()
    expect(page.locator("#practice-value-field")).to_be_visible()
    assert unlabelled_controls(page) == [] and small_buttons(page) == []
    kept = shown_exercise(page)
    page.get_by_label("Tu resultado").fill(tutors.number(kept["wrong"]["swapped"], "es", 3))
    page.get_by_role("button", name="Enviar respuesta").click()

    expect(page.locator("#practice-verdict")).to_have_text("Incorrecto")
    expect(page.locator("#practice-mistake-text")).to_have_text("Intercambiar precisión y exhaustividad")
    expect(page.locator("#practice-comment")).to_contain_text("(pág. 4)")
    expect(page.locator("#practice-next-step")).to_be_visible()
    expect(page.locator("#practice-points")).to_be_hidden()
    expect(page.locator("#practice-fallback")).to_be_hidden()
    expect(page.locator("#practice-review-heading")).to_have_text("Qué repasar: pág. 4")
    page.get_by_role("button", name="Intentar de nuevo").click()
    right = tutors.number(kept["solution_value"], "es", 3)
    page.get_by_label("Tu resultado").fill(right)
    page.get_by_role("button", name="Enviar respuesta").click()

    expect(page.locator("#practice-verdict")).to_have_text("Correcto")
    expect(page.locator("#practice-numeric")).to_have_text(f"Tu resultado, {right}, es correcto.")
    assert hard_to_read(page) == []
    page.get_by_role("button", name="Siguiente ejercicio").click()

    expect(page.locator("#practice-aim")).to_have_text("Este ejercicio vuelve sobre el error de tu último intento.")
    assert shown_exercise(page)["params"]["asks"] in ("P", "R")


def test_the_instructor_reviews_each_tutor_and_sees_how_often_a_mistake_was_found(site):
    tutor_course(site)
    for user, mistake in (("s1", "swapped"), ("s2", "swapped"), ("s3", "swapped"), ("s4", "complement"), ("s5", "complement")):
        token = site.token("Learner", user=user)
        topic = next(t["topic_id"] for t in httpx.get(f"{site.url}{BASE}/api/practice/topics", params={"token": token}).json()["topics"]
                     if t["name"] == "Evaluation with precision and recall")
        got = httpx.post(f"{site.url}{BASE}/api/practice/exercise", params={"token": token},
                         json={"topic_id": topic, "level": "basico", "language": "es"}).json()["exercise"]
        wrong = exercises.load(cid("course-A"), got["exercise_id"])["wrong"][mistake]
        assert httpx.post(f"{site.url}{BASE}/api/practice/exercises/{got['exercise_id']}/answer", params={"token": token},
                          json={"value": tutors.number(wrong, "es", 3)}).status_code == 201
    page = site.open("/instructor", site.token("Instructor", user="teacher-1"), locale="es-ES")
    page.get_by_role("tab", name="Práctica").click()

    pr = page.get_by_role("article", name="Precisión, exhaustividad (recall) y F1")
    expect(pr).to_be_visible()
    expect(pr).to_contain_text("Sirve el tema «Evaluation with precision and recall». Especificación: tutors/precision_recall.toml.")
    expect(pr).to_contain_text("Se apoya en handout.pdf, pág. 4:")
    expect(pr).to_contain_text("5 ejercicios respondidos por 5 estudiantes.")
    swapped_row = pr.get_by_role("row", name="Intercambiar precisión y exhaustividad")
    expect(swapped_row).to_contain_text("(pág. {page})")
    expect(swapped_row).to_contain_text("página 4")
    expect(swapped_row).to_contain_text("3 veces, 3 estudiantes")
    expect(pr.get_by_role("row", name="Calcular la parte que falla")).to_contain_text("Todavía hay muy pocas respuestas.")
    expect(pr.get_by_role("row", name="Dividir aciertos entre fallos")).to_contain_text("Todavía no")
    expect(pr.get_by_role("row", name="Incorrecta, sin error catalogado")).to_contain_text("Revisa las definiciones")
    ransac = page.get_by_role("article", name="Número de iteraciones de RANSAC")
    expect(ransac.get_by_role("row", name="Redondear hacia abajo")).to_contain_text("página 3")
    assert unlabelled_controls(page) == [] and hard_to_read(page) == []

    page.locator("#lang-switch").click()
    expect(page.get_by_role("article", name="Precision, recall and F1")).to_contain_text("Swapping precision and recall")
