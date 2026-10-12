"""Export to Moodle, in a browser: where the instructor finds it, and that a file arrives."""

from xml.etree import ElementTree as ET

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from .test_browser import approve_all_and_publish, draft, unlabelled_controls, upload  # noqa: E402
from .test_family import hard_to_read  # noqa: E402


def downloaded(page, link):
    with page.expect_download() as caught:
        link.click()
    download = caught.value
    return download.suggested_filename, ET.parse(download.path()).getroot()


def test_a_draft_has_no_export_and_a_published_quiz_has_one_that_downloads_a_file(site):
    page = site.instructor()
    upload(page)
    draft(page, count=2, title="Week 7")

    expect(page.locator("#export-link")).to_be_hidden()                # nothing published, nothing to export
    expect(page.locator("#export-hint")).to_be_hidden()

    approve_all_and_publish(page, count=2)
    link = page.get_by_role("link", name="Export to Moodle")
    expect(link).to_be_visible()
    expect(link).to_have_accessible_name("Export to Moodle: “Week 7”, version 1, as a Moodle XML file")
    expect(page.locator("#export-hint")).to_contain_text("Question bank → Import → Moodle XML format")
    assert link.bounding_box()["height"] >= 38                          # as large as the buttons beside it
    assert unlabelled_controls(page) == [] and hard_to_read(page) == []

    name, root = downloaded(page, link)
    assert name == "ai-quiz-week-7-v1.xml"
    assert [q.get("type") for q in root.findall("question")] == ["category", "multichoice", "multichoice"]
    assert site.problems == []                                           # the page stayed where it was, no error


def test_the_list_of_quizzes_offers_the_export_per_quiz_and_only_for_published_ones(site):
    page = site.instructor()
    upload(page)
    draft(page, count=2, title="Published one")
    approve_all_and_publish(page, count=2)
    page.get_by_role("button", name="Back to documents and quizzes").click()
    draft(page, count=1, title="Only a draft")
    page.get_by_role("button", name="Back to documents and quizzes").click()

    rows = page.locator("#quizzes tbody tr")
    expect(rows).to_have_count(2)
    published = rows.filter(has_text="Published one")
    expect(rows.filter(has_text="Only a draft").get_by_role("link")).to_have_count(0)
    expect(published.get_by_role("link", name="Export to Moodle")).to_have_count(1)
    assert hard_to_read(page) == []

    name, root = downloaded(page, published.get_by_role("link"))
    assert name == "ai-quiz-published-one-v1.xml"
    assert root.find("question[@type='category']/category/text").text == "$course$/top/Published one"


def test_the_export_is_offered_in_spanish_too(site):
    page = site.open("/instructor", site.token("Instructor", user="teacher-1"), locale="es-ES")
    upload_es(page)
    page.fill("#gen-count", "1")
    page.fill("#gen-title", "Semana 7")
    page.locator("#generate-button").click()
    expect(page.locator(".sheet")).to_have_count(1)
    page.locator(".sheet button.primary").first.click()
    expect(page.locator(".sheet").first).to_have_attribute("data-status", "approved")
    page.locator("#publish-button").click()

    link = page.get_by_role("link", name="Exportar a Moodle")
    expect(link).to_have_accessible_name("Exportar a Moodle: «Semana 7», versión 1, como archivo Moodle XML")
    expect(page.locator("#export-hint")).to_contain_text("Banco de preguntas → Importar → Formato Moodle XML")


def upload_es(page):
    from ..pdfs import handout_pdf

    page.set_input_files("#upload-file", files=[{"name": "handout.pdf", "mimeType": "application/pdf", "buffer": handout_pdf()}])
    page.locator("#upload-button").click()
    expect(page.locator("#documents table")).to_be_visible()
