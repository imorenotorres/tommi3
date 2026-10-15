"""Practice for the student, in a browser: choose, get an exercise, answer, read the feedback, try again,
see the solution. In Spanish, as students in Moodle see it, and in English after the switch."""

import httpx
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from ..conftest import BASE  # noqa: E402
from ..fake_practice import feedback_reply  # noqa: E402
from ..practice_helpers import sectioned_pdf  # noqa: E402
from .test_browser import unlabelled_controls  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402

ANSWER = "Minimal samples are small, so they are more likely to contain only inliers."


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")
    monkeypatch.setenv("AI_QUIZ_PRACTICE_MODEL", "1")       # the model-written path, switched on


def course_with_practice(site, on=True):
    token = site.token("Instructor", user="teacher-1")
    response = httpx.post(f"{site.url}{BASE}/api/documents", params={"token": token},
                          files={"file": ("unit4.pdf", sectioned_pdf(), "application/pdf")})
    assert response.status_code == 201, response.text
    if on:
        assert httpx.put(f"{site.url}{BASE}/api/practice/settings", params={"token": token},
                         json={"enabled": True}).status_code == 200


def practice_page(site, user="student-1"):
    page = site.open("/student", site.token("Learner", user=user), locale="es-ES")
    expect(page.locator("#practice-entry")).to_be_visible()
    page.get_by_role("button", name="Practicar").click()
    expect(page.locator("#practice-view")).to_be_visible()
    return page


def get_exercise(page, topic="Counting iterations", level="Intermedio"):
    page.get_by_label("Tema").select_option(label=f"{topic} (págs. 2–3)")
    page.get_by_label(level, exact=True).check()
    page.get_by_role("button", name="Generar ejercicio").click()
    expect(page.locator("#practice-exercise")).to_be_visible()


def send(page, text=ANSWER):
    page.get_by_label("Tu respuesta").fill(text)
    page.get_by_role("button", name="Enviar respuesta").click()
    expect(page.locator("#practice-feedback")).to_be_visible()


def test_a_student_chooses_gets_an_exercise_with_its_page_answers_and_reads_the_feedback(site):
    course_with_practice(site)
    page = practice_page(site)

    get_exercise(page)

    expect(page.locator("#practice-ai-label")).to_have_text("Ejercicio generado por IA a partir del apunte · pág. 2")
    expect(page.locator("#practice-meta")).to_have_text("Counting iterations · Intermedio · Respuesta abierta")
    expect(page.locator("#practice-statement")).to_contain_text("Exercise")
    expect(page.locator("#practice-value-field")).to_be_hidden()
    page.get_by_label("Tu respuesta").fill(ANSWER)
    expect(page.locator("#practice-count")).to_have_text(f"{len(ANSWER)} de 1500 caracteres")
    assert page.get_by_label("Tu respuesta").get_attribute("maxlength") == "1500"
    assert unlabelled_controls(page) == [] and small_buttons(page) == []

    page.get_by_role("button", name="Enviar respuesta").click()

    expect(page.locator("#practice-verdict")).to_have_text("Correcto")
    rows = page.locator("#practice-points tbody tr")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("Cumplido")
    expect(rows.nth(0).locator("q")).to_have_text("Minimal samples are small, so")
    expect(page.locator("#practice-comment")).to_be_visible()
    expect(page.locator("#practice-review-heading")).to_have_text("Qué repasar: pág. 2")
    expect(page.locator("#practice-review q")).to_contain_text("1.1 Why minimal samples")
    expect(page.locator("#practice-retry")).to_be_hidden()
    page.get_by_role("button", name="Ver solución").click()
    expect(page.locator("#practice-solution-text")).to_contain_text("Reference solution")
    assert hard_to_read(page) == []


def test_a_partial_answer_offers_one_more_try_and_then_the_solution(site, fake_llm):
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)
    fake_llm.queue(lambda m: feedback_reply(m, statuses={"K2": "falta"}), lambda m: feedback_reply(m, statuses={"K2": "parcial"}))

    send(page)

    expect(page.locator("#practice-verdict")).to_have_text("Parcial")
    expect(page.locator("#practice-try")).to_have_text("Intento 1 de 2")
    expect(page.locator("#practice-points tbody tr").nth(1)).to_contain_text("Falta")
    expect(page.locator("#practice-show-solution")).to_be_hidden()
    page.get_by_role("button", name="Intentar de nuevo").click()
    expect(page.locator("#practice-answer-form")).to_be_visible()

    send(page, ANSWER + " Each extra point raises the chance of an outlier.")

    expect(page.locator("#practice-try")).to_have_text("Intento 2 de 2")
    expect(page.locator("#practice-retry")).to_be_hidden()
    page.get_by_role("button", name="Ver solución").click()
    expect(page.locator("#practice-solution")).to_be_visible()


def test_feedback_that_fails_its_checks_shows_the_key_points_and_the_passage_only(site, fake_llm):
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)
    fake_llm.queue("not json", "still not json")

    send(page)

    expect(page.locator("#practice-verdict")).to_have_text("Sin valorar")
    expect(page.locator("#practice-fallback")).to_be_visible()
    expect(page.locator("#practice-comment")).to_be_hidden()
    expect(page.locator("#practice-points tbody tr")).to_have_count(2)
    expect(page.locator("#practice-review q")).to_be_visible()


def test_a_point_the_two_gradings_disagree_on_is_shown_as_to_be_checked_without_a_comment(site, fake_llm):
    from ..fake_practice import Grading, grading_reply
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)
    fake_llm.queue(Grading(lambda m: grading_reply(m, statuses={"K2": "falta"})))

    send(page)

    expect(page.locator("#practice-verdict")).to_have_text("Parcial")
    expect(page.locator("#practice-uncertain")).to_be_visible()
    expect(page.locator("#practice-comment")).to_be_hidden()
    row = page.locator("#practice-points tbody tr").nth(1)
    expect(row).to_contain_text("Revisar")
    expect(row).to_contain_text("No se ha podido valorar con seguridad")
    expect(page.locator("#practice-points tbody tr").nth(0).locator("q")).to_be_visible()


def test_a_numerical_exercise_asks_for_the_value_and_says_whether_it_is_right(site):
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)
    send(page)
    page.get_by_role("button", name="Siguiente ejercicio").click()
    expect(page.locator("#practice-meta")).to_contain_text("Numérico")

    expect(page.locator("#practice-value-field")).to_be_visible()
    page.get_by_label("Tu resultado").fill("17")
    page.get_by_label("Tu respuesta").fill("I read it in the table.")
    page.get_by_role("button", name="Enviar respuesta").click()

    expect(page.locator("#practice-verdict")).to_have_text("Incorrecto")
    expect(page.locator("#practice-numeric")).to_have_text("Tu resultado, 17, no es correcto.")


def test_a_value_is_shown_as_typed_and_an_unfinished_exercise_comes_back(site, fake_llm):
    from ..fake_practice import check_reply, exercise_reply
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)
    send(page)
    fake_llm.queue(lambda m: exercise_reply(m, value=0.7), lambda m: check_reply(m, value=0.7))
    page.get_by_role("button", name="Siguiente ejercicio").click()
    expect(page.locator("#practice-value-field")).to_be_visible()
    statement = page.locator("#practice-statement").inner_text()

    again = site.open("/student", page.url.split("token=")[1].split("&")[0], locale="es-ES")     # the window closed
    again.get_by_role("button", name="Practicar").click()

    expect(again.locator("#practice-statement")).to_have_text(statement)
    expect(again.locator("#status")).to_have_text("No habías terminado este ejercicio: aquí lo tienes de nuevo.")
    again.get_by_label("Tu resultado").fill("0,7")
    again.get_by_label("Tu respuesta").fill("I read it in the table.")
    again.get_by_role("button", name="Enviar respuesta").click()
    expect(again.locator("#practice-numeric")).to_have_text("Tu resultado, 0,7, es correcto.")


def test_a_student_reports_an_exercise_with_one_of_four_reasons(site):
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)

    page.get_by_role("button", name="Reportar un problema").click()
    page.get_by_label("La respuesta esperada parece incorrecta").check()
    page.get_by_role("button", name="Enviar el aviso").click()

    expect(page.locator("#status")).to_contain_text("queda retirado hasta que lo revise el docente")
    expect(page.locator("#practice-exercise")).to_be_hidden()


def test_the_view_is_in_english_after_the_switch(site):
    course_with_practice(site)
    page = practice_page(site)
    get_exercise(page)
    send(page)

    page.locator("#lang-switch").click()

    expect(page.locator("#practice-ai-label")).to_have_text("Exercise generated by AI from the handout · p. 2")
    expect(page.locator("#practice-verdict")).to_have_text("Correct")
    expect(page.get_by_role("button", name="See the solution")).to_be_visible()


def test_the_exercise_is_asked_for_in_the_language_of_the_page(site, fake_llm):
    course_with_practice(site)
    page = site.open("/student", site.token("Learner"), locale="en-GB")
    page.get_by_role("button", name="Practise").click()

    page.get_by_role("button", name="Get an exercise").click()
    expect(page.locator("#practice-exercise")).to_be_visible()

    assert "Write the exercise in English" in fake_llm.calls[0]["messages"][0]["content"]


def test_with_practice_on_but_no_document_there_is_no_entry(site):
    token = site.token("Instructor", user="teacher-1")
    assert httpx.put(f"{site.url}{BASE}/api/practice/settings", params={"token": token},
                     json={"enabled": True}).status_code == 200

    page = site.open("/student", site.token("Learner"), locale="es-ES")

    expect(page.locator("#list-heading")).to_be_visible()
    expect(page.locator("#practice-entry")).to_be_hidden()


def test_without_practice_in_the_course_there_is_no_entry(site):
    course_with_practice(site, on=False)

    page = site.open("/student", site.token("Learner"), locale="es-ES")

    expect(page.locator("#list-heading")).to_be_visible()
    expect(page.locator("#practice-entry")).to_be_hidden()
