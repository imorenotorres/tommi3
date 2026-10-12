"""Uploading, listing and deleting course documents through the API (rules A3, A4, A7)."""

from pathlib import Path

import pytest

from UltiR.ai_quiz import limits, storage

from .conftest import BASE, cid
from .pdfs import handout_pdf, scanned_pdf

DOCS = f"{BASE}/api/documents"


def upload(client, token, name="handout.pdf", data=None, mode=None):
    fields = {} if mode is None else {"reading_mode": mode}
    return client.post(DOCS, params={"token": token}, data=fields,
                       files={"file": (name, handout_pdf() if data is None else data)})


def stored_files() -> list[Path]:
    return sorted(p for p in storage.data_root().rglob("*") if p.is_file())


def error_code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture
def instructor(launch):
    return launch.token(role="Instructor", course="course-A")


# ── Upload ──────────────────────────────────────────────────────────────────

def test_an_uploaded_pdf_is_stored_read_and_described(client, instructor):
    response = upload(client, instructor, "Lecture 7.pdf")

    assert response.status_code == 201
    doc = response.json()
    assert storage.is_id(doc["doc_id"], "d")
    assert doc["label"] == "Lecture 7.pdf"
    assert (doc["mode"], doc["engine"], doc["status"]) == ("text", "pypdf", "ready")
    assert doc["n_pages"] == 3
    assert doc["n_chunks"] >= 3
    assert doc["size"] == len(handout_pdf())


@pytest.mark.parametrize("name, content", [
    ("notes.txt", "Feature matching links the same physical point across images. " * 5),
    ("apuntes.md", "# Correspondencia\n\nLa prueba de la razón compara dos distancias. " * 5),
])
def test_text_and_markdown_files_are_accepted(client, instructor, name, content):
    response = upload(client, instructor, name, content.encode("utf-8"))

    assert response.status_code == 201
    assert response.json()["engine"] == "plain"
    assert response.json()["n_pages"] == 1


def test_uploaded_documents_are_listed_newest_first_and_can_be_fetched(client, instructor):
    first = upload(client, instructor, "one.pdf").json()
    second = upload(client, instructor, "two.txt", b"A different document with enough text to be read properly.").json()

    listed = client.get(DOCS, params={"token": instructor}).json()["documents"]
    fetched = client.get(f"{DOCS}/{first['doc_id']}", params={"token": instructor})

    assert [d["doc_id"] for d in listed] == [second["doc_id"], first["doc_id"]]
    assert fetched.status_code == 200
    assert fetched.json() == first


def test_page_numbers_reach_the_stored_chunks(client, instructor):
    doc = upload(client, instructor).json()
    course_dir = storage.course_dir(cid("course-A"))

    chunks = storage.read_json(course_dir / "docs" / doc["doc_id"] / "chunks.json")

    by_page = {c["page"]: c["text"] for c in chunks}
    assert sorted(by_page) == [1, 2, 3]
    assert "ratio test" in by_page[2]
    assert "RANSAC" in by_page[3]


# ── What is refused, and that a refusal leaves nothing behind ───────────────

@pytest.mark.parametrize("name, data, status, code", [
    ("malware.exe", b"MZ\x90\x00 not a document", 415, "unsupported_type"),
    ("slides.docx", b"PK\x03\x04 a zip in disguise", 415, "unsupported_type"),
    ("noextension", b"some text", 415, "unsupported_type"),
    ("fake.pdf", b"This is plain text with a .pdf name.", 400, "not_a_pdf"),
    ("binary.txt", b"abc\x00\x01\x02def", 400, "not_text"),
    ("latin1.txt", "visi\xf3n por computador".encode("latin-1"), 400, "not_text"),
    ("empty.txt", b"", 400, "empty_file"),
    ("scan.pdf", scanned_pdf(), 422, "no_text"),
    ("broken.pdf", b"%PDF-1.4\nnot really a pdf at all\n", 422, "corrupt"),
])
def test_unsuitable_files_are_refused_with_a_reason_and_nothing_is_kept(client, instructor, name, data, status, code):
    response = upload(client, instructor, name, data)

    assert (response.status_code, error_code(response)) == (status, code)
    assert stored_files() == []
    assert client.get(DOCS, params={"token": instructor}).json()["documents"] == []


def test_a_file_over_the_size_limit_is_refused_and_nothing_is_kept(client, instructor, monkeypatch):
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 1000)

    response = upload(client, instructor, "big.txt", b"x" * 5000)

    assert (response.status_code, error_code(response)) == (413, "file_too_large")
    assert stored_files() == []


def test_a_request_without_a_file_is_refused(client, instructor):
    response = client.post(DOCS, params={"token": instructor}, data={"reading_mode": "text"})

    assert (response.status_code, error_code(response)) == (400, "no_file")


def test_full_reading_is_refused_on_a_server_that_is_not_set_up_for_it(client, instructor):
    response = upload(client, instructor, mode="full")

    assert (response.status_code, error_code(response)) == (409, "full_reading_unavailable")
    assert stored_files() == []


def test_an_unknown_reading_mode_is_refused(client, instructor):
    response = upload(client, instructor, mode="magic")

    assert (response.status_code, error_code(response)) == (400, "bad_mode")


def test_the_same_file_twice_is_refused_and_points_at_the_first(client, instructor):
    first = upload(client, instructor, "a.pdf").json()

    again = upload(client, instructor, "renamed.pdf")

    assert (again.status_code, error_code(again)) == (409, "duplicate_document")
    assert again.json()["detail"]["doc_id"] == first["doc_id"]
    assert len(client.get(DOCS, params={"token": instructor}).json()["documents"]) == 1


def test_the_number_of_documents_per_course_is_capped(client, instructor, monkeypatch):
    monkeypatch.setattr(limits, "MAX_DOCUMENTS_PER_COURSE", 2)
    for i in range(2):
        assert upload(client, instructor, f"{i}.txt", f"Document number {i} has its own text. ".encode() * 4).status_code == 201

    response = upload(client, instructor, "third.txt", b"A third document with enough text in it to read.")

    assert (response.status_code, error_code(response)) == (409, "too_many_documents")


@pytest.mark.parametrize("name", [
    "../../outside.txt",
    "..\\..\\outside.txt",
    "/etc/cron.d/job.txt",
    "C:\\Windows\\system32\\evil.txt",
    "....//....//x.txt",
    "\x00hidden.txt",
    ".txt",
    "<img src=x onerror=alert(1)>.txt",
])
def test_a_hostile_file_name_cannot_place_a_file_outside_the_course_folder(client, instructor, name):
    response = upload(client, instructor, name, b"Harmless text that is long enough to be read as a document.")

    course_dir = storage.course_dir(cid("course-A"))
    assert response.status_code == 201
    assert stored_files() != []
    assert all(course_dir in p.parents for p in stored_files())
    label = response.json()["label"]
    assert label and "/" not in label and "\\" not in label and ".." not in label and "\x00" not in label


@pytest.mark.parametrize("name, label", [
    ("../../outside.txt", "outside.txt"),
    ("C:\\Users\\teacher\\Lecture 7.txt", "Lecture 7.txt"),
    ("/home/teacher/notes.txt", "notes.txt"),
])
def test_only_the_last_part_of_a_file_path_is_kept_as_the_label(client, instructor, name, label):
    response = upload(client, instructor, name, b"Harmless text that is long enough to be read as a document.")

    assert response.json()["label"] == label


def test_a_very_long_file_name_is_shortened_for_display(client, instructor):
    response = upload(client, instructor, "a" * 400 + ".txt", b"Enough text for the reader to accept this document.")

    assert response.status_code == 201
    assert len(response.json()["label"]) <= limits.MAX_LABEL_CHARS


# ── Roles ───────────────────────────────────────────────────────────────────

def test_a_learner_cannot_upload_and_nothing_is_stored(client, launch):
    response = upload(client, launch.token(role="Learner", course="course-A"))

    assert response.status_code == 403
    assert stored_files() == []


def test_an_upload_without_a_session_is_refused_and_nothing_is_stored(client):
    response = upload(client, "")

    assert response.status_code == 401
    assert stored_files() == []


# ── One course cannot see or touch another course's documents (A4) ──────────

def test_another_course_cannot_list_fetch_or_delete_the_document(client, launch, instructor):
    doc = upload(client, instructor).json()
    other = launch.token(role="Instructor", course="course-B")

    assert client.get(DOCS, params={"token": other}).json()["documents"] == []
    assert client.get(f"{DOCS}/{doc['doc_id']}", params={"token": other}).status_code == 404
    assert client.delete(f"{DOCS}/{doc['doc_id']}", params={"token": other}).status_code == 404
    assert client.get(f"{DOCS}/{doc['doc_id']}", params={"token": instructor}).status_code == 200


def test_the_same_file_can_exist_in_two_courses(client, launch, instructor):
    other = launch.token(role="Instructor", course="course-B")

    assert upload(client, instructor).status_code == 201
    assert upload(client, other).status_code == 201


# ── Delete ──────────────────────────────────────────────────────────────────

def test_deleting_a_document_removes_its_files_and_its_entry(client, instructor):
    keep = upload(client, instructor, "keep.txt", b"This document stays in the course after the other is deleted.").json()
    gone = upload(client, instructor, "gone.pdf").json()

    response = client.delete(f"{DOCS}/{gone['doc_id']}", params={"token": instructor})

    assert response.status_code == 200
    assert [d["doc_id"] for d in client.get(DOCS, params={"token": instructor}).json()["documents"]] == [keep["doc_id"]]
    assert not any(gone["doc_id"] in str(p) for p in stored_files())
    assert client.get(f"{DOCS}/{gone['doc_id']}", params={"token": instructor}).status_code == 404


@pytest.mark.parametrize("doc_id", ["d_0000000000000000", "nonsense", "..", "d_../../../etc", "q_0123456789abcdef"])
def test_an_unknown_or_malformed_document_id_is_not_found(client, instructor, doc_id):
    upload(client, instructor)

    assert client.get(f"{DOCS}/{doc_id}", params={"token": instructor}).status_code == 404
    assert client.delete(f"{DOCS}/{doc_id}", params={"token": instructor}).status_code == 404
    assert len(client.get(DOCS, params={"token": instructor}).json()["documents"]) == 1


# ── The session tells the page which reading modes exist ────────────────────

def test_the_session_says_that_only_text_reading_is_available(client, instructor):
    body = client.get(f"{BASE}/api/session", params={"token": instructor}).json()

    assert body["reading_modes"] == {"text": True, "full": False}
