"""Practice, part one: the topics found in a document, and the instructor's settings for them.

Topics come from the document itself: numbered headings, then Markdown headings, then ranges of
pages. Nothing about a subject is written into the code.
"""

import pytest

from UltiR.ai_quiz import topics

from .conftest import BASE
from .pdfs import handout_pdf
from .practice_helpers import PRACTICE, SECTION_TITLES, PracticeCourse


def code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch)


def pages(*texts):
    return [{"page": n, "text": text} for n, text in enumerate(texts, start=1)]


# ── Finding headings ────────────────────────────────────────────────────────

def test_numbered_headings_are_found_in_order_with_their_page():
    found = topics.numbered_headings(pages(
        "Notes\n1 What local features are\ntext", "more text\n2 Gaussian scale space\ntext", "3 Keypoints"))

    assert [(h["number"], h["title"], h["page"]) for h in found] == [
        (1, "What local features are", 1), (2, "Gaussian scale space", 2), (3, "Keypoints", 3)]


def test_a_heading_may_carry_a_dot_after_its_number():
    found = topics.numbered_headings(pages("1. Elementos del contrato\ntexto\n2. La forma del contrato"))

    assert [h["title"] for h in found] == ["Elementos del contrato", "La forma del contrato"]


@pytest.mark.parametrize("line", [
    "2 + L(x, y+ 1) − L(x, y− 1)2, (15)",      # a formula
    "2 4 8 16 32",                             # a row of a table
    "2. Call the two transformations T and T′.",   # an item of a numbered list
    "2 Descriptors, as before,",               # a sentence that goes on
    "2 R = det M",                             # an equation
    "2 x",                                     # too short
    "2 Homography 4 5 17 72 567",              # a row of a table that starts with a word
    "2 This line of ordinary prose runs on and on, well beyond the length that any heading has",
])
def test_a_line_that_is_not_a_title_is_no_heading(line):
    found = topics.numbered_headings(pages(f"1 Introduction\n{line}"))

    assert [h["number"] for h in found] == [1]


def test_a_number_out_of_order_is_no_heading():
    found = topics.numbered_headings(pages("1 Introduction\n3 Not yet\n2 Second part\n7 Too far\n3 Third part"))

    assert [h["title"] for h in found] == ["Introduction", "Second part", "Third part"]


def test_a_subsection_stays_inside_its_section():
    found = topics.numbered_headings(pages("1 Introduction\n1.1 Detail\n2 Next part"))

    assert [h["title"] for h in found] == ["Introduction", "Next part"]


def test_markdown_headings_of_the_top_level_when_it_repeats():
    text = "# Part A\n## a1\n## a2\n# Part B\n## b1"

    assert [h["title"] for h in topics.markdown_headings([{"page": None, "text": text}])] == ["Part A", "Part B"]


def test_markdown_headings_of_the_shallowest_level_that_repeats():
    text = "# Course notes\nintro\n## First part\ntext\n## Second part\ntext\n### Detail"

    assert [h["title"] for h in topics.markdown_headings([{"page": None, "text": text}])] == ["First part", "Second part"]


# ── Topics of a document ────────────────────────────────────────────────────

def test_the_sections_of_a_handout_are_its_topics(course):
    found = topics.course_topics(_course_id(course))

    assert [t["title"] for t in found] == SECTION_TITLES
    assert [t["kind"] for t in found] == ["heading"] * 3
    assert [t["pages"] for t in found] == [[1, 2], [2, 3], [3, 4]]


def test_a_chunk_in_which_a_section_starts_belongs_to_the_section_before_it_too(course):
    first, second, third = topics.course_topics(_course_id(course))

    assert first["chunk_ids"] == ["c_0001", "c_0002"]
    assert second["chunk_ids"] == ["c_0002", "c_0003"]
    assert third["chunk_ids"] == ["c_0003", "c_0004"]


def test_a_topic_keeps_its_id_when_it_is_found_again(course):
    once = [t["topic_id"] for t in topics.course_topics(_course_id(course))]
    again = [t["topic_id"] for t in topics.course_topics(_course_id(course))]

    assert once == again and len(set(once)) == 3
    assert all(t.startswith("t_") and len(t) == 18 for t in once)


def test_a_document_without_headings_is_cut_into_ranges_of_three_pages(client, launch):
    pdf_pages = [[f"Plain page {n} with ordinary prose and no heading of any kind at all."] for n in range(1, 8)]
    from .pdfs import make_pdf
    plain = PracticeCourse(client, launch, pdf=make_pdf(pdf_pages), name="plain.pdf")

    found = topics.course_topics(_course_id(plain))

    assert [t["pages"] for t in found] == [[1, 3], [4, 6], [7, 7]]
    assert {t["kind"] for t in found} == {"pages"} and {t["title"] for t in found} == {None}


def test_a_text_file_without_pages_or_headings_is_cut_into_runs_of_chunks(client, launch):
    text = "\n\n".join(f"Paragraph {n}. " + "Ordinary prose without any heading. " * 30 for n in range(10))
    plain = PracticeCourse(client, launch, pdf=text.encode(), name="notes.txt")

    found = topics.course_topics(_course_id(plain))

    assert len(found) >= 2 and {t["kind"] for t in found} == {"chunks"}
    assert all(t["pages"] is None and 1 <= len(t["chunk_ids"]) <= topics.CHUNKS_PER_TOPIC for t in found)


def test_a_markdown_file_is_cut_at_its_headings(client, launch):
    text = "# Unit\n\n## The offer\n\n" + "An offer states terms. " * 20 + "\n\n## The acceptance\n\n" + "Acceptance agrees. " * 20
    notes = PracticeCourse(client, launch, pdf=text.encode(), name="notes.md")

    assert [t["title"] for t in topics.course_topics(_course_id(notes))] == ["The offer", "The acceptance"]


def _course_id(course):
    from .conftest import cid
    return cid(course.course)


# ── The instructor's settings ───────────────────────────────────────────────

def test_practice_starts_switched_off_in_a_course(client, launch):
    fresh = PracticeCourse(client, launch, switch_on=False)

    got = client.get(f"{PRACTICE}/settings", params={"token": fresh.instructor}).json()

    assert got["enabled"] is False
    assert [t["name"] for t in got["topics"]] == SECTION_TITLES and all(t["enabled"] for t in got["topics"])
    assert code(client.get(f"{PRACTICE}/topics", params={"token": fresh.learner()})) == "practice_off"


def test_with_practice_on_a_student_sees_the_topics_and_the_levels(client, course):
    response = client.get(f"{PRACTICE}/topics", params={"token": course.learner()})

    assert response.status_code == 200
    body = response.json()
    assert body["levels"] == ["basico", "intermedio", "avanzado"]
    assert [set(t) for t in body["topics"]] == [{"topic_id", "name", "doc_label", "pages"}] * 3
    assert [t["name"] for t in body["topics"]] == SECTION_TITLES


def test_a_topic_switched_off_is_not_offered(course):
    first = course.topics()[0]["topic_id"]

    course.settings(topics={first: {"enabled": False}})

    assert [t["name"] for t in course.topics()] == SECTION_TITLES[1:]


def test_a_topic_can_be_renamed_and_given_its_own_name_back(course):
    first = course.topics()[0]["topic_id"]

    course.settings(topics={first: {"name": "  Muestras   mínimas "}})
    assert course.topics()[0]["name"] == "Muestras mínimas"

    course.settings(topics={first: {"name": ""}})
    assert course.topics()[0]["name"] == SECTION_TITLES[0]


@pytest.mark.parametrize("body", [
    {}, {"enabled": "yes"}, {"enabled": 1}, {"topics": []}, {"topics": {"x": "on"}},
])
def test_a_malformed_change_is_refused(client, course, body):
    response = client.put(f"{PRACTICE}/settings", params={"token": course.instructor}, json=body)

    assert response.status_code == 400


def test_a_change_to_a_topic_with_a_wrong_value_is_refused(client, course):
    first = course.topics()[0]["topic_id"]
    for change in ({"enabled": "no"}, {"name": 5}, {"name": "x" * 81}):
        response = client.put(f"{PRACTICE}/settings", params={"token": course.instructor}, json={"topics": {first: change}})
        assert response.status_code == 400, change


def test_a_topic_of_another_course_is_unknown_here(client, launch, course):
    other = PracticeCourse(client, launch, course="course-B", pdf=handout_pdf(), name="other.pdf")
    theirs = client.get(f"{PRACTICE}/settings", params={"token": other.instructor}).json()["topics"][0]["topic_id"]

    response = client.put(f"{PRACTICE}/settings", params={"token": course.instructor},
                          json={"topics": {theirs: {"enabled": False}}})

    assert (response.status_code, code(response)) == (404, "unknown_topic")


def test_the_settings_of_one_course_do_not_reach_another(client, launch, course):
    other = PracticeCourse(client, launch, course="course-B", switch_on=False)

    assert code(client.get(f"{PRACTICE}/topics", params={"token": other.learner()})) == "practice_off"


# ── Who may do what ─────────────────────────────────────────────────────────

def test_a_student_may_not_read_or_change_the_settings(client, course):
    student = course.learner()

    assert client.get(f"{PRACTICE}/settings", params={"token": student}).status_code == 403
    assert client.put(f"{PRACTICE}/settings", params={"token": student}, json={"enabled": False}).status_code == 403
    assert course.topics()                          # still on


def test_without_a_session_nothing_is_answered(client, course):
    for method, path in (("get", "settings"), ("put", "settings"), ("get", "topics")):
        assert getattr(client, method)(f"{PRACTICE}/{path}").status_code == 401


def test_a_server_that_does_not_offer_practice_has_no_practice_routes(client, course, monkeypatch):
    for value in ("", "0", "true", "yes"):
        monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", value)
        assert client.get(f"{PRACTICE}/settings", params={"token": course.instructor}).status_code == 404
        assert client.put(f"{PRACTICE}/settings", params={"token": course.instructor},
                          json={"enabled": True}).status_code == 404
        assert client.get(f"{PRACTICE}/topics", params={"token": course.learner()}).status_code == 404
    monkeypatch.delenv("AI_QUIZ_PRACTICE_ENABLED")
    assert client.get(f"{PRACTICE}/topics", params={"token": course.learner()}).status_code == 404


def test_the_quizzes_of_the_course_are_not_touched(client, course):
    assert client.get(f"{BASE}/api/published", params={"token": course.learner()}).json() == {"quizzes": []}
