"""The instructor's "Práctica" tab in a browser: the switch, the topics, the exercises, the discards, the totals."""

import httpx
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from ..conftest import BASE  # noqa: E402
from ..fake_practice import check_reply, exercise_reply, feedback_reply  # noqa: E402
from ..practice_helpers import SECTION_TITLES, sectioned_pdf  # noqa: E402
from .test_browser import unlabelled_controls  # noqa: E402
from .test_family import hard_to_read, small_buttons  # noqa: E402

API = f"{BASE}/api/practice"


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


def with_document(site):
    token = site.token("Instructor", user="teacher-1")
    assert httpx.post(f"{site.url}{BASE}/api/documents", params={"token": token},
                      files={"file": ("unit4.pdf", sectioned_pdf(), "application/pdf")}).status_code == 201
    return token


def practise(site, users, reply=None, fake_llm=None):
    """Each user gets the same exercise of section 2 and answers it."""
    for user in users:
        token = site.token("Learner", user=user)
        got = httpx.post(f"{site.url}{API}/exercise", params={"token": token},
                         json={"topic_id": topic_ids(site)[1], "level": "intermedio", "language": "es"}).json()
        if reply:
            fake_llm.queue(reply)
        assert httpx.post(f"{site.url}{API}/exercises/{got['exercise']['exercise_id']}/answer", params={"token": token},
                          json={"answer": "Minimal samples are small and so more likely free of outliers."}).status_code == 201


def topic_ids(site):
    token = site.token("Instructor", user="teacher-1")
    return [t["topic_id"] for t in httpx.get(f"{site.url}{API}/settings", params={"token": token}).json()["topics"]]


def practice_tab(site):
    page = site.open("/instructor", site.token("Instructor", user="teacher-1"), locale="es-ES")
    expect(page.locator("#tabs")).to_be_visible()
    page.get_by_role("tab", name="Práctica").click()
    expect(page.locator("#practice-panel")).to_be_visible()
    expect(page.locator("#overview")).to_be_hidden()
    return page


def test_the_instructor_switches_practice_on_and_sees_the_topics_found(site):
    with_document(site)
    page = practice_tab(site)

    expect(page.locator("#practice-state")).to_have_text("La práctica está desactivada en este curso.")
    page.get_by_label("El estudiantado puede practicar").check()

    expect(page.locator("#status")).to_have_text("La práctica queda activada en este curso.")
    expect(page.locator("#practice-state")).to_have_text("La práctica está activada en este curso.")
    names = page.locator("#practice-topics tbody input[type=text]")
    expect(names).to_have_count(3)
    assert [names.nth(i).input_value() for i in range(3)] == SECTION_TITLES
    expect(page.locator("#practice-topics tbody tr").nth(1)).to_contain_text("2–3")
    assert unlabelled_controls(page) == [] and small_buttons(page) == [] and hard_to_read(page) == []


def test_a_topic_is_renamed_and_switched_off_from_the_tab(site):
    with_document(site)
    page = practice_tab(site)
    row = page.locator("#practice-topics tbody tr").first

    row.locator("input[type=text]").fill("Muestras mínimas")
    row.get_by_role("button", name="Guardar nombre").click()
    expect(page.locator("#status")).to_have_text("Nombre guardado: «Muestras mínimas».")
    page.get_by_label("Práctica sobre «Muestras mínimas»").uncheck()
    expect(page.locator("#status")).to_have_text("«Muestras mínimas» está desactivado.")

    token = site.token("Instructor", user="teacher-1")
    first = httpx.get(f"{site.url}{API}/settings", params={"token": token}).json()["topics"][0]
    assert (first["name"], first["enabled"], first["title"]) == ("Muestras mínimas", False, SECTION_TITLES[0])
    expect(page.locator("#practice-topics tbody tr").first).to_contain_text("Encontrado como: Sampling a model")


def test_the_exercises_and_the_discards_are_listed_and_an_exercise_can_be_retired(site, fake_llm):
    token = with_document(site)
    httpx.put(f"{site.url}{API}/settings", params={"token": token}, json={"enabled": True})
    practise(site, ["s-1"])
    student = site.token("Learner", user="s-1")
    fake_llm.queue(lambda m: exercise_reply(m, value=5), lambda m: check_reply(m, value=17))
    httpx.post(f"{site.url}{API}/exercise", params={"token": student},
               json={"topic_id": topic_ids(site)[1], "level": "intermedio", "language": "es"})
    page = practice_tab(site)

    sheets = page.locator("#practice-pool details")
    expect(sheets).to_have_count(2)
    expect(page.locator("#practice-pool-count")).to_contain_text("2 ejercicios generados")
    expect(sheets.nth(1).locator("summary")).to_contain_text("En uso")
    sheets.nth(1).locator("summary").click()
    expect(sheets.nth(1)).to_contain_text("Solución de referencia")
    expect(sheets.nth(1)).to_contain_text("dado 1 veces")
    expect(page.locator("#practice-rejections")).to_contain_text("Un segundo cálculo dio otro valor: 5 frente a 17")

    sheets.nth(1).get_by_role("button", name="Retirar").click()

    expect(page.locator("#status")).to_contain_text("El ejercicio queda retirado")
    retired = page.locator("#practice-pool details").nth(1)
    expect(retired.locator("summary")).to_contain_text("Retirado")
    retired.locator("summary").click()
    expect(retired.get_by_role("button")).to_have_count(0)               # nothing more to do with a retired one


def test_a_reported_exercise_can_be_put_back(site):
    token = with_document(site)
    httpx.put(f"{site.url}{API}/settings", params={"token": token}, json={"enabled": True})
    student = site.token("Learner", user="s-1")
    got = httpx.post(f"{site.url}{API}/exercise", params={"token": student}, json={"language": "es"}).json()
    httpx.post(f"{site.url}{API}/exercises/{got['exercise']['exercise_id']}/report", params={"token": student},
               json={"reason": "enunciado_confuso"})
    page = practice_tab(site)
    sheet = page.locator("#practice-pool details").first
    expect(sheet.locator("summary")).to_contain_text("Reportado")
    sheet.locator("summary").click()
    expect(sheet).to_contain_text("Reportado 1 veces: El enunciado no se entiende")

    sheet.get_by_role("button", name="Aprobar y volver a usar").click()

    expect(page.locator("#practice-pool details").first.locator("summary")).to_contain_text("En uso")


def test_the_totals_show_nothing_for_two_students_and_numbers_for_three(site, fake_llm):
    token = with_document(site)
    httpx.put(f"{site.url}{API}/settings", params={"token": token}, json={"enabled": True})
    missed = lambda m: feedback_reply(m, statuses={"K2": "falta"}, mistake="M1")    # noqa: E731
    practise(site, ["s-1", "s-2"], missed, fake_llm)
    page = practice_tab(site)

    expect(page.locator("#practice-summary tbody tr")).to_contain_text("Todavía hay muy pocas respuestas.")
    expect(page.locator("#practice-summary")).to_contain_text("Todavía no se muestra ninguno")

    practise(site, ["s-3"], missed, fake_llm)
    page.get_by_role("tab", name="Cuestionarios").click()
    page.get_by_role("tab", name="Práctica").click()

    row = page.locator("#practice-summary tbody tr").first
    expect(row).to_contain_text("Counting iterations")
    expect(row).to_contain_text("Intermedio")
    expect(row).to_contain_text("0 · 3 · 0")
    expect(page.locator("#practice-summary")).to_contain_text("Typical mistake 1.1")
    expect(page.locator("#practice-summary")).to_contain_text("Key point 1.2 of the rubric")
    for private in ("s-1", "s-2", "s-3", "Minimal samples are small"):
        expect(page.locator("#practice-panel")).not_to_contain_text(private)


def test_without_practice_on_the_server_there_is_no_tab(site, monkeypatch):
    monkeypatch.delenv("AI_QUIZ_PRACTICE_ENABLED")

    page = site.open("/instructor", site.token("Instructor", user="teacher-1"), locale="es-ES")

    expect(page.locator("#docs-heading")).to_be_visible()
    expect(page.locator("#tabs")).to_be_hidden()
