"""Figures of a full reading: stored per course, served through one guarded route, attached to questions."""

import hashlib
import json

import pytest

from UltiR.ai_quiz import documents, generation, storage

from .conftest import BASE, cid
from .docling_recorded import images
from .fake_llm import question, sources_in
from .readers import install_recorded_docling, upload_full
from .test_documents import DOCS, stored_files, upload

FIGURES = f"{BASE}/api/figures"


@pytest.fixture(autouse=True)
def docling(monkeypatch):
    install_recorded_docling(monkeypatch)


@pytest.fixture
def instructor(launch):
    return launch.token(role="Instructor", course="course-A")


@pytest.fixture
def learner(launch):
    return launch.token(role="Learner", course="course-A", user="student-1")


@pytest.fixture
def doc(client, instructor) -> dict:
    return upload_full(client, instructor)


def figure(client, token, doc_id, figure_id):
    return client.get(f"{FIGURES}/{doc_id}/{figure_id}", params={"token": token})


def about_figure(figure_id, **changes):
    """A model reply: one question about the source that holds this figure, naming it."""
    def reply(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if f"[FIGURE {figure_id}]" in text)
        text = sources[sid].split("] ", 1)[1]                 # quote the caption, after the mark
        return json.dumps({"questions": [question(sid, text, 1, **{"figure": figure_id, **changes})]})
    return reply


def draft(client, token, doc_id, count=1, **body):
    response = client.post(f"{BASE}/api/generate", params={"token": token},
                           json={"doc_ids": [doc_id], "count": count, "topic": "scale-space pyramid octaves", **body})
    assert response.status_code == 201, response.text
    return response.json()["quiz"]


def approve(client, token, quiz, index=0, **changes):
    q = quiz["questions"][index]
    response = client.put(f"{BASE}/api/quizzes/{quiz['quiz_id']}/questions/{q['question_id']}",
                          params={"token": token}, json={"review_status": "approved", **changes})
    assert response.status_code == 200, response.text
    return response.json()


def publish(client, token, quiz):
    response = client.post(f"{BASE}/api/quizzes/{quiz['quiz_id']}/publish", params={"token": token})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def published(client, instructor, doc, fake_llm) -> dict:
    """A published quiz with one question, to which Figure 1 (f0001) is attached."""
    fake_llm.queue(about_figure("f0001"))
    quiz = draft(client, instructor, doc["doc_id"])
    assert [f["figure_id"] for f in quiz["questions"][0]["figures"]] == ["f0001"]
    approve(client, instructor, quiz)
    return publish(client, instructor, quiz)


# ── Stored with the document ────────────────────────────────────────────────

def test_the_figures_of_a_full_reading_are_stored_in_the_course_folder_under_our_names(doc):
    folder = storage.course_dir(cid("course-A")) / "docs" / doc["doc_id"]

    assert doc["n_figures"] == 3
    assert sorted(p.name for p in (folder / "figures").iterdir()) == ["f0001.png", "f0002.png", "f0003.png"]
    assert (folder / "figures" / "f0001.png").read_bytes() == images()["p0004.png"]
    records = storage.read_json(folder / "figures.json")
    assert [(r["figure_id"], r["page"], r["file"], r["media_type"]) for r in records] == [
        ("f0001", 3, "f0001.png", "image/png"), ("f0002", 4, "f0002.png", "image/png"), ("f0003", 7, "f0003.png", "image/png")]


def test_a_text_reading_has_no_figures(client, instructor):
    doc = upload(client, instructor).json()

    assert doc["n_figures"] == 0
    assert client.get(f"{DOCS}/{doc['doc_id']}/figures", params={"token": instructor}).json() == {"figures": []}


def test_deleting_the_document_removes_its_figures(client, instructor, doc):
    assert figure(client, instructor, doc["doc_id"], "f0001").status_code == 200

    client.delete(f"{DOCS}/{doc['doc_id']}", params={"token": instructor})

    assert [p for p in stored_files() if doc["doc_id"] in str(p)] == []
    assert figure(client, instructor, doc["doc_id"], "f0001").status_code == 404


# ── The instructor sees every figure ────────────────────────────────────────

def test_an_instructor_gets_the_list_of_figures_without_any_file_name(client, instructor, doc):
    body = client.get(f"{DOCS}/{doc['doc_id']}/figures", params={"token": instructor}).json()

    assert [(f["figure_id"], f["page"]) for f in body["figures"]] == [("f0001", 3), ("f0002", 4), ("f0003", 7)]
    assert body["figures"][2]["caption"].startswith("Figure 5: Construction of a gradient histogram descriptor")
    assert set(body["figures"][0]) == {"figure_id", "page", "caption", "width", "height"}
    assert ".png" not in json.dumps(body)


def test_an_instructor_gets_every_figure_of_the_course_as_an_image(client, instructor, doc):
    for figure_id, file in (("f0001", "p0004.png"), ("f0002", "p0006.png"), ("f0003", "p0012.png")):
        response = figure(client, instructor, doc["doc_id"], figure_id)

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.content == images()[file]


def test_figures_are_not_served_without_a_session(client, doc):
    assert figure(client, "", doc["doc_id"], "f0001").status_code == 401
    assert client.get(f"{DOCS}/{doc['doc_id']}/figures").status_code == 401


# ── Another course ──────────────────────────────────────────────────────────

def test_another_course_cannot_list_or_fetch_the_figures(client, launch, published, doc):
    for role in ("Instructor", "Learner"):
        other = launch.token(role=role, course="course-B")

        assert figure(client, other, doc["doc_id"], "f0001").status_code == 404
        assert client.get(f"{DOCS}/{doc['doc_id']}/figures", params={"token": other}).status_code in (403, 404)


# ── A student sees a figure only with a published question ──────────────────

def test_a_student_gets_no_figure_before_a_question_with_it_is_published(client, instructor, learner, doc, fake_llm):
    fake_llm.queue(about_figure("f0001"))
    quiz = draft(client, instructor, doc["doc_id"])
    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 404      # drafted

    approve(client, instructor, quiz)
    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 404      # approved, not published

    publish(client, instructor, quiz)
    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 200


def test_a_student_gets_only_the_figure_that_is_attached_not_the_others_of_the_document(client, learner, published, doc):
    assert figure(client, learner, doc["doc_id"], "f0001").content == images()["p0004.png"]
    assert figure(client, learner, doc["doc_id"], "f0002").status_code == 404
    assert figure(client, learner, doc["doc_id"], "f0003").status_code == 404
    assert client.get(f"{DOCS}/{doc['doc_id']}/figures", params={"token": learner}).status_code == 403


def test_unpublishing_the_quiz_takes_the_figure_away_from_students_again(client, instructor, learner, published, doc):
    client.post(f"{BASE}/api/quizzes/{published['quiz_id']}/unpublish", params={"token": instructor})

    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 404
    assert figure(client, instructor, doc["doc_id"], "f0001").status_code == 200


def test_a_figure_detached_in_the_draft_stays_visible_until_the_change_is_published(client, instructor, learner, published, doc):
    q = published["questions"][0]
    url = f"{BASE}/api/quizzes/{published['quiz_id']}/questions/{q['question_id']}"
    client.put(url, params={"token": instructor}, json={"figure_id": None, "review_status": "approved"})
    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 200      # students still have revision 1

    publish(client, instructor, published)

    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 404


# ── Names never come from the request ───────────────────────────────────────

@pytest.mark.parametrize("figure_id", [
    "f0004", "f0000", "f001", "f00001", "F0001", "f0001.png", "figures", "source.pdf", "..", "f000a",
    "..%2Fsource.pdf", "%2e%2e%2fsource.pdf", "f0001%00.png", "f0001%2F..%2Fsource.pdf", "..%2F..%2F..%2Fdocuments.json",
])      # (a plain "/../" in the address is resolved by the client before it is sent, so it cannot be tried here)
def test_anything_but_the_id_of_a_stored_figure_is_not_found(client, instructor, doc, figure_id):
    assert figure(client, instructor, doc["doc_id"], figure_id).status_code == 404


@pytest.mark.parametrize("doc_id", ["d_0000000000000000", "..", "nonsense", "d_..%2F..%2F"])
def test_an_unknown_or_malformed_document_id_has_no_figures(client, instructor, doc, doc_id):
    assert figure(client, instructor, doc_id, "f0001").status_code == 404
    assert client.get(f"{DOCS}/{doc_id}/figures", params={"token": instructor}).status_code == 404


@pytest.mark.parametrize("file", ["../source.pdf", "../../../documents.json", "/etc/passwd", "f0002.png/../../source.pdf", "f0001.svg", ""])
def test_even_a_tampered_record_cannot_make_the_route_serve_another_file(client, instructor, doc, file):
    path = storage.course_dir(cid("course-A")) / "docs" / doc["doc_id"] / "figures.json"
    records = storage.read_json(path)
    records[0]["file"] = file
    storage.write_json(path, records)

    assert figure(client, instructor, doc["doc_id"], "f0001").status_code == 404
    assert figure(client, instructor, doc["doc_id"], "f0002").status_code == 200


def test_a_document_that_is_not_ready_serves_no_figures(client, instructor, doc):
    index = storage.course_dir(cid("course-A")) / "documents.json"
    records = storage.read_json(index)
    records[0].update(status="failed", error="reading_failed")
    storage.write_json(index, records)

    assert figure(client, instructor, doc["doc_id"], "f0001").status_code == 404
    assert documents.list_figures(cid("course-A"), doc["doc_id"]) is None


# ── A figure named by the model ─────────────────────────────────────────────

def test_a_figure_the_model_names_from_its_source_is_attached_with_caption_and_page(client, instructor, doc, fake_llm):
    fake_llm.queue(about_figure("f0001"))

    q = draft(client, instructor, doc["doc_id"])["questions"][0]

    assert len(q["figures"]) == 1
    assert (q["figures"][0]["figure_id"], q["figures"][0]["page"]) == ("f0001", 3)
    assert q["figures"][0]["caption"].startswith("Figure 1: Scale-space pyramid")
    assert set(q["figures"][0]) == {"figure_id", "page", "caption"}


@pytest.mark.parametrize("named", ["f0002", "f0009", "F0001", "f0001.png", "../f0001", 1, ["f0001"], {"id": "f0001"}, None, ""])
def test_a_figure_the_model_cannot_have_seen_or_names_wrongly_is_not_attached(client, instructor, doc, fake_llm, named):
    fake_llm.queue(about_figure("f0001", figure=named))        # f0002 exists, but its mark is not in the question's source

    quiz = draft(client, instructor, doc["doc_id"], topic="scale-space pyramid octaves intervals")

    assert len(fake_llm.calls) == 1                            # this very reply was read, not a second one
    assert quiz["questions"][0]["figures"] == []
    assert quiz["questions"][0]["grounded"]                    # the question itself is kept


def test_the_model_is_given_the_caption_and_never_the_image(client, instructor, doc, fake_llm):
    draft(client, instructor, doc["doc_id"])

    prompt = fake_llm.prompts[0]
    assert "[FIGURE f0001] Figure 1: Scale-space pyramid" in prompt
    assert "PNG" not in prompt and "base64" not in prompt
    assert '"figure"' in prompt                                # the prompt for a full reading explains the field


# ── A figure chosen by the instructor ───────────────────────────────────────

def change(client, token, quiz, **body):
    q = quiz["questions"][0]
    return client.put(f"{BASE}/api/quizzes/{quiz['quiz_id']}/questions/{q['question_id']}",
                      params={"token": token}, json=body)


def test_an_instructor_can_attach_another_figure_of_the_source_document_or_none(client, instructor, doc):
    quiz = draft(client, instructor, doc["doc_id"])
    assert quiz["questions"][0]["figures"] == []

    attached = change(client, instructor, quiz, figure_id="f0003").json()["questions"][0]
    kept = change(client, instructor, quiz, explanation="A new explanation.").json()["questions"][0]
    detached = change(client, instructor, quiz, figure_id=None).json()["questions"][0]

    assert [(f["figure_id"], f["page"]) for f in attached["figures"]] == [("f0003", 7)]
    assert kept["figures"] == attached["figures"]              # an edit that does not mention the figure keeps it
    assert detached["figures"] == []


@pytest.mark.parametrize("figure_id", ["f0009", "f0001.png", "../f0001", "", 3, ["f0001"], {"figure_id": "f0001"}])
def test_a_figure_that_does_not_exist_in_the_source_document_cannot_be_attached(client, instructor, doc, figure_id):
    quiz = draft(client, instructor, doc["doc_id"])

    response = change(client, instructor, quiz, figure_id=figure_id)

    assert (response.status_code, response.json()["detail"]["code"]) == (400, "unknown_figure")


def test_a_figure_record_sent_by_the_browser_is_not_stored(client, instructor, doc):
    quiz = draft(client, instructor, doc["doc_id"])

    response = change(client, instructor, quiz, explanation="Changed.",
                      figures=[{"figure_id": "f0002", "caption": "<b>made up</b>", "page": 99, "doc_id": "d_0000000000000000"}])

    assert response.status_code == 200
    assert response.json()["questions"][0]["figures"] == []


def test_a_question_from_a_text_reading_cannot_get_a_figure(client, instructor, doc):
    text_doc = upload(client, instructor, "notes.txt", b"Plain notes about feature matching, long enough to be read. " * 4).json()
    quiz = draft(client, instructor, text_doc["doc_id"], topic="")

    response = change(client, instructor, quiz, figure_id="f0001")     # exists, but in the other document

    assert (response.status_code, response.json()["detail"]["code"]) == (400, "unknown_figure")


def test_a_learner_cannot_attach_a_figure(client, instructor, learner, doc):
    quiz = draft(client, instructor, doc["doc_id"])

    assert change(client, learner, quiz, figure_id="f0001").status_code == 403


# ── What the student is told about the figure ───────────────────────────────

def test_the_published_question_tells_the_student_which_figure_to_show_and_nothing_else_new(client, learner, published, doc):
    quiz = client.get(f"{BASE}/api/published/{published['quiz_id']}", params={"token": learner}).json()

    q = quiz["questions"][0]
    assert set(q) == {"question_id", "question", "options", "difficulty", "figures", "math"}   # math: see test_formulas.py
    assert len(q["figures"]) == 1
    assert set(q["figures"][0]) == {"doc_id", "figure_id", "caption"}
    assert (q["figures"][0]["doc_id"], q["figures"][0]["figure_id"]) == (doc["doc_id"], "f0001")


def test_a_question_without_a_figure_looks_to_the_student_as_it_did_before(client, instructor, learner):
    text_doc = upload(client, instructor, "notes.txt", b"Plain notes about feature matching, long enough to be read. " * 4).json()
    quiz = draft(client, instructor, text_doc["doc_id"], topic="")
    approve(client, instructor, quiz)
    publish(client, instructor, quiz)

    seen = client.get(f"{BASE}/api/published/{quiz['quiz_id']}", params={"token": learner}).json()

    assert set(seen["questions"][0]) == {"question_id", "question", "options", "difficulty"}


def test_the_result_names_the_figure_too(client, learner, published, doc):
    result = client.post(f"{BASE}/api/quizzes/{published['quiz_id']}/attempts", params={"token": learner},
                         json={"revision": 1, "answers": {}}).json()

    assert [f["figure_id"] for f in result["results"][0]["figures"]] == ["f0001"]


# ── The prompt ──────────────────────────────────────────────────────────────

# SHA-256 of the system prompt as it was when M3 was accepted (commit 66a5d48).
TEXT_PROMPT = "f691bc8b7299541057c2752a9997d224509c402f7eb38afd8c96a0f545de2810"


def system_prompt(fake_llm) -> str:
    return fake_llm.calls[-1]["messages"][0]["content"]


def test_the_prompt_for_a_text_reading_is_exactly_what_it_was(client, instructor, fake_llm):
    text_doc = upload(client, instructor, "notes.txt", b"Plain notes about feature matching, long enough to be read. " * 4).json()

    draft(client, instructor, text_doc["doc_id"], topic="")

    assert hashlib.sha256(system_prompt(fake_llm).encode("utf-8")).hexdigest() == TEXT_PROMPT
    assert '"figure"' not in system_prompt(fake_llm)


def test_the_prompt_for_a_full_reading_has_the_rule_about_figures(client, instructor, doc, fake_llm):
    draft(client, instructor, doc["doc_id"])

    assert system_prompt(fake_llm) == generation.SYSTEM_PROMPTS["full"]
    assert sum("[FIGURE" in line for line in system_prompt(fake_llm).split("\n")) == 1
    # (how exactly the two prompts differ is checked in test_formulas.py)


# ── Second lines of defence ─────────────────────────────────────────────────

def test_a_record_whose_id_is_not_of_our_shape_is_never_served(doc):
    folder = storage.course_dir(cid("course-A")) / "docs" / doc["doc_id"]
    records = storage.read_json(folder / "figures.json")
    records.append({"figure_id": "x0001", "page": 1, "caption": "", "file": "x0001.png", "media_type": "image/png"})
    storage.write_json(folder / "figures.json", records)
    (folder / "figures" / "x0001.png").write_bytes(images()["p0004.png"])

    assert documents.figure_file(cid("course-A"), doc["doc_id"], "x0001") is None
    assert documents.figure_file(cid("course-A"), doc["doc_id"], "f0001") is not None


def test_a_figure_named_by_the_model_is_dropped_if_its_record_is_gone(client, instructor, doc, fake_llm):
    path = storage.course_dir(cid("course-A")) / "docs" / doc["doc_id"] / "figures.json"
    storage.write_json(path, [r for r in storage.read_json(path) if r["figure_id"] != "f0001"])
    fake_llm.queue(about_figure("f0001"))                       # its mark is still in the text

    assert draft(client, instructor, doc["doc_id"])["questions"][0]["figures"] == []


def test_a_published_figure_does_not_open_the_figure_with_the_same_id_in_another_document(client, instructor, learner, published, doc):
    from .pdfs import make_pdf

    second = upload_full(client, instructor, "second.pdf", make_pdf([["Another handout of the same course, read in full."]]))
    assert second["doc_id"] != doc["doc_id"]

    assert figure(client, learner, doc["doc_id"], "f0001").status_code == 200
    assert figure(client, learner, second["doc_id"], "f0001").status_code == 404
    assert figure(client, instructor, second["doc_id"], "f0001").status_code == 200
