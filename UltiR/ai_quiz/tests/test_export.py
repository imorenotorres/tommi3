"""Export to Moodle's question bank: the published questions of a quiz as a Moodle XML file.

Instructor only, the course of the session only, and only what was published. Every text in the
file was typed by a person or written by a model, so none of it may become markup of the file.
"""

import html
from xml.etree import ElementTree as ET

import pytest

from UltiR.ai_quiz import moodle_xml

from .test_attempts import QUIZZES, Course, code


@pytest.fixture
def course(client, launch):
    return Course(client, launch)


def export(client, token, quiz_id):
    return client.get(f"{QUIZZES}/{quiz_id}/export.xml", params={"token": token})


def questions_in(content: bytes) -> list:
    return ET.fromstring(content).findall("question[@type='multichoice']")


def field(node, name: str) -> str:
    return node.find(f"{name}/text").text or ""


def revision(*questions, title="Week 7", number=1) -> dict:
    return {"quiz_id": "z_0000000000000001", "revision": number, "title": title, "questions": list(questions)}


def a_question(stem="What does the ratio test compare?", key="B", **more) -> dict:
    return {"question_id": "q_0000000000000001", "question": stem,
            "options": [{"id": i, "text": f"Option {i}"} for i in "ABCD"],
            "correct_option_id": key, "explanation": "Because the handout says so.", "difficulty": "basic", **more}


# ── The route ───────────────────────────────────────────────────────────────

def test_an_instructor_downloads_the_published_questions_as_a_moodle_xml_file(client, course):
    quiz = course.published_quiz(3, title="Week 7")

    response = export(client, course.instructor, quiz["quiz_id"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.headers["content-disposition"] == 'attachment; filename="ai-quiz-week-7-v1.xml"'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    root = ET.fromstring(response.content)
    assert root.tag == "quiz"
    assert [q.get("type") for q in root.findall("question")] == ["category"] + ["multichoice"] * 3
    assert root.find("question[@type='category']/category/text").text == "$course$/top/Week 7"


def test_each_question_carries_its_options_its_key_and_its_explanation(client, course):
    quiz = course.published_quiz(2, title="Week 7")

    exported = questions_in(export(client, course.instructor, quiz["quiz_id"]).content)

    for number, (node, stored) in enumerate(zip(exported, quiz["questions"], strict=True), start=1):
        assert field(node, "name") == f"Week 7 {number:02d}"
        assert node.find("questiontext").get("format") == "html"
        assert field(node, "questiontext") == f"<p>{html.escape(stored['question'], quote=False)}</p>"
        assert field(node, "generalfeedback") == f"<p>{html.escape(stored['explanation'], quote=False)}</p>"
        assert (node.find("single").text, node.find("shuffleanswers").text) == ("true", "false")
        assert node.find("answernumbering").text == "ABCD"
        answers = node.findall("answer")
        assert [a.find("text").text for a in answers] == [html.escape(o["text"], quote=False) for o in stored["options"]]
        assert [a.get("fraction") for a in answers] == ["0", "100", "0", "0"]      # the key of a fake question is B


def test_only_what_was_published_is_exported(client, course):
    draft = course.draft(3, title="Week 7")
    course.edit(draft, 0, review_status="approved")
    course.edit(draft, 1, review_status="rejected")
    course.publish(draft)                                                # question 3 stays a draft
    course.edit(draft, 0, question="A stem that was rewritten after publishing?")

    exported = questions_in(export(client, course.instructor, draft["quiz_id"]).content)

    assert [field(q, "questiontext") for q in exported] == [f"<p>{html.escape(draft['questions'][0]['question'], quote=False)}</p>"]


def test_a_quiz_that_was_never_published_has_nothing_to_export(client, course):
    quiz = course.draft(2)
    course.edit(quiz, 0, review_status="approved")

    response = export(client, course.instructor, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (409, "never_published")
    assert b"<quiz" not in response.content


def test_a_quiz_withdrawn_from_students_can_still_be_exported(client, course):
    quiz = course.published_quiz(2)
    client.post(f"{QUIZZES}/{quiz['quiz_id']}/unpublish", params={"token": course.instructor})

    response = export(client, course.instructor, quiz["quiz_id"])

    assert response.status_code == 200 and len(questions_in(response.content)) == 2


def test_a_learner_cannot_export(client, course):
    quiz = course.published_quiz(2)

    response = export(client, course.learner(), quiz["quiz_id"])

    assert response.status_code == 403
    assert b"<quiz" not in response.content and b"fraction" not in response.content


def test_nobody_exports_without_a_session(client, course):
    quiz = course.published_quiz(2)

    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}/export.xml").status_code == 401
    assert export(client, "0" * 64, quiz["quiz_id"]).status_code == 401


def test_the_quiz_of_another_course_is_not_found(client, launch, course):
    quiz = course.published_quiz(2)
    other = launch.token(role="Instructor", course="course-B", user="teacher-9")

    response = export(client, other, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (404, "quiz_not_found")


@pytest.mark.parametrize("quiz_id", ["z_0000000000000000", "nope", "..%2F..%2Fmeta", "z_123"])
def test_an_id_that_names_no_quiz_is_not_found(client, course, quiz_id):
    assert export(client, course.instructor, quiz_id).status_code == 404


def test_text_of_a_question_cannot_become_markup_of_the_file(client, course):
    hostile = '</text></questiontext></question><question type="essay"><name><text>x ]]> & <script>alert(1)</script>'
    quiz = course.draft(2, title="Week 7")
    course.edit(quiz, 0, question=hostile + "?", explanation=hostile,
                options=[{"id": i, "text": f"{hostile} {i}"} for i in "ABCD"])
    for index in range(2):
        course.edit(quiz, index, review_status="approved")
    course.publish(quiz)

    content = export(client, course.instructor, quiz["quiz_id"]).content
    root = ET.fromstring(content)                                        # still one well-formed file

    assert [q.get("type") for q in root.findall("question")] == ["category", "multichoice", "multichoice"]
    first = root.findall("question")[1]
    assert field(first, "questiontext") == f"<p>{html.escape(hostile + '?', quote=False)}</p>"
    assert "<script" not in field(first, "questiontext") and "<script" not in field(first, "generalfeedback")
    assert all("<" not in (a.find("text").text or "") for a in first.findall("answer"))
    assert b"<script" not in content and b"<question type=\"essay\"" not in content


# ── The file itself ─────────────────────────────────────────────────────────

def test_formulas_of_a_full_reading_get_the_delimiters_of_moodles_mathjax_filter():
    question = a_question("If a<b & $w^s$ with $a<b$ then $$\\frac{n}{2}$$ costs $5 or $6 & <more>.", math="latex",
                          explanation="See $\\sqrt{n}$.")
    question["options"][0]["text"] = "$x_1$"

    node = questions_in(moodle_xml.export(revision(question)))[0]

    assert field(node, "questiontext") == (
        "<p>If a&lt;b &amp; \\(w^s\\) with \\(a&lt;b\\) then \\[\\frac{n}{2}\\] costs $5 or $6 &amp; &lt;more&gt;.</p>")
    assert field(node, "generalfeedback") == "<p>See \\(\\sqrt{n}\\).</p>"
    assert node.findall("answer")[0].find("text").text == "\\(x_1\\)"


def test_dollar_signs_of_a_text_reading_are_left_as_they_are():
    node = questions_in(moodle_xml.export(revision(a_question("Is $w^s$ a formula here?"))))[0]

    assert field(node, "questiontext") == "<p>Is $w^s$ a formula here?</p>"


def test_the_key_is_the_only_option_that_scores_whichever_it_is():
    for key in "ABCD":
        node = questions_in(moodle_xml.export(revision(a_question(key=key))))[0]

        assert [a.get("fraction") for a in node.findall("answer")] == ["100" if i == key else "0" for i in "ABCD"]


def test_a_question_without_an_explanation_has_empty_feedback():
    node = questions_in(moodle_xml.export(revision(a_question(explanation=""))))[0]

    assert field(node, "generalfeedback") == ""


def test_a_slash_in_the_title_does_not_open_a_sub_category():
    root = ET.fromstring(moodle_xml.export(revision(a_question(), title="Unit 3/4: matching")))

    assert root.find("question[@type='category']/category/text").text == "$course$/top/Unit 3//4: matching"


def test_characters_an_xml_file_cannot_hold_are_left_out():
    content = moodle_xml.export(revision(a_question("Bell \x07 and ￾ and a lone \udc00 surrogate?"), title="T\x0b1"))

    node = questions_in(content)[0]                                      # parses: nothing forbidden was written
    assert field(node, "questiontext") == "<p>Bell  and  and a lone  surrogate?</p>"
    assert field(node, "name") == "T1 01"


@pytest.mark.parametrize("title, name", [
    ("Visión por Computador: detección", "ai-quiz-vision-por-computador-deteccion-v3.xml"),
    ('a"b\r\nSet-Cookie: x=1', "ai-quiz-a-b-set-cookie-x-1-v3.xml"),
    ("../../etc/passwd", "ai-quiz-etc-passwd-v3.xml"),
    ("¿¡!?", "ai-quiz-quiz-v3.xml"),
    ("x" * 300, "ai-quiz-" + "x" * 60 + "-v3.xml"),
])
def test_the_name_of_the_download_is_plain_whatever_the_title_is(title, name):
    assert moodle_xml.file_name(revision(title=title, number=3)) == name
