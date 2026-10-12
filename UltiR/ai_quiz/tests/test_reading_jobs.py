"""Full reading runs as a background job: status, one job per course, time limit, restart, cleaning up."""

import time

import pytest

from UltiR.ai_quiz import ingestion, jobs, limits, storage

from .conftest import BASE, cid
from .pdfs import handout_pdf, make_pdf, scanned_pdf
from .readers import SlowReader, install
from .test_documents import DOCS, error_code, stored_files, upload

OTHER_PDF = make_pdf([["A second handout about camera calibration, with enough words on its only page to be read."]])


@pytest.fixture
def instructor(launch):
    return launch.token(role="Instructor", course="course-A")


@pytest.fixture
def reader(monkeypatch):
    return install(monkeypatch, SlowReader())


def fetch(client, token, doc_id) -> dict:
    return client.get(f"{DOCS}/{doc_id}", params={"token": token}).json()


def wait_until(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("did not happen in time")


def settled(client, token, doc_id) -> dict:
    """The document once its reading is over, one way or the other."""
    wait_until(lambda: fetch(client, token, doc_id)["status"] != "processing")
    return fetch(client, token, doc_id)


def files_of(doc_id) -> list:
    return [p for p in stored_files() if doc_id in str(p)]


# ── Status ──────────────────────────────────────────────────────────────────

def test_a_full_reading_upload_answers_at_once_and_becomes_ready_when_the_reader_is_done(client, instructor, reader):
    response = upload(client, instructor, mode="full")

    assert response.status_code == 202
    doc = response.json()
    assert (doc["mode"], doc["status"], doc["n_chunks"]) == ("full", "processing", 0)
    assert reader.started.wait(5)
    assert fetch(client, instructor, doc["doc_id"])["status"] == "processing"

    reader.release()
    done = settled(client, instructor, doc["doc_id"])

    assert (done["status"], done["engine"], done["n_pages"]) == ("ready", "fake", 2)
    assert done["n_chunks"] >= 2
    chunks = storage.read_json(storage.course_dir(cid("course-A")) / "docs" / doc["doc_id"] / "chunks.json")
    assert [c["page"] for c in chunks] == [1, 2]


def test_text_reading_still_happens_inside_the_request(client, instructor, reader):
    response = upload(client, instructor)

    assert response.status_code == 201
    assert (response.json()["status"], response.json()["mode"]) == ("ready", "text")
    assert reader.calls == 0


def test_the_session_offers_full_reading_when_a_reader_for_it_exists(client, instructor, reader):
    body = client.get(f"{BASE}/api/session", params={"token": instructor}).json()

    assert body["reading_modes"] == {"text": True, "full": True}


# ── One job per course ──────────────────────────────────────────────────────

def test_a_second_full_reading_in_the_same_course_is_refused_while_the_first_runs(client, launch, instructor, reader):
    first = upload(client, instructor, mode="full").json()
    assert reader.started.wait(5)

    second = upload(client, instructor, "other.pdf", OTHER_PDF, mode="full")
    text_upload = upload(client, instructor, "notes.txt", b"Plain notes that are long enough to be read as a document.")
    elsewhere = upload(client, launch.token(role="Instructor", course="course-B"), "other.pdf", OTHER_PDF, mode="full")

    assert (second.status_code, error_code(second)) == (409, "reading_in_progress")
    assert text_upload.status_code == 201                      # text reading is not held up
    assert elsewhere.status_code == 202                        # another course has its own turn
    listed = client.get(DOCS, params={"token": instructor}).json()["documents"]
    assert sorted(d["label"] for d in listed) == ["handout.pdf", "notes.txt"]
    reader.release()
    assert settled(client, instructor, first["doc_id"])["status"] == "ready"


def test_after_a_reading_has_ended_the_course_can_start_another(client, instructor, reader):
    first = upload(client, instructor, mode="full").json()
    reader.release()
    settled(client, instructor, first["doc_id"])

    assert upload(client, instructor, "other.pdf", OTHER_PDF, mode="full").status_code == 202


# ── Time limit ──────────────────────────────────────────────────────────────

def test_a_reader_that_takes_too_long_is_stopped_and_the_document_is_marked_failed(client, instructor, reader, monkeypatch):
    monkeypatch.setattr(limits, "FULL_READING_SECONDS", 0.15)

    doc = upload(client, instructor, mode="full").json()
    done = settled(client, instructor, doc["doc_id"])

    assert (done["status"], done["error"]) == ("failed", "reading_timeout")
    assert reader.finished.wait(5) and reader.was_stopped     # the reader was told to stop, and did
    assert files_of(doc["doc_id"]) == []


def test_a_result_that_arrives_after_the_time_limit_is_thrown_away(client, instructor, monkeypatch):
    reader = install(monkeypatch, SlowReader(obeys_stop=False))   # an engine that does not react to the stop signal
    monkeypatch.setattr(limits, "FULL_READING_SECONDS", 0.15)
    doc = upload(client, instructor, mode="full").json()
    assert settled(client, instructor, doc["doc_id"])["status"] == "failed"

    reader.release()                                           # now it finishes, far too late
    assert reader.finished.wait(5)
    wait_until(lambda: not jobs.is_running(jobs.key_of(doc["doc_id"])))

    assert fetch(client, instructor, doc["doc_id"])["status"] == "failed"
    assert files_of(doc["doc_id"]) == []


# ── Failure ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("error, code", [
    (ingestion.Unreadable("no_text"), "no_text"),
    (ingestion.ReaderUnavailable("the engine went away"), "full_reading_unavailable"),
    (RuntimeError("anything else, with details that must not reach the page"), "reading_failed"),
])
def test_a_failed_reading_says_why_and_leaves_none_of_its_files(client, instructor, monkeypatch, error, code):
    reader = install(monkeypatch, SlowReader(error=error))
    doc = upload(client, instructor, mode="full").json()
    reader.release()

    done = settled(client, instructor, doc["doc_id"])

    assert (done["status"], done["error"]) == ("failed", code)
    assert "details" not in str(done)
    assert files_of(doc["doc_id"]) == []


def test_the_same_file_can_be_uploaded_again_after_its_reading_failed(client, instructor, monkeypatch):
    reader = install(monkeypatch, SlowReader(error=RuntimeError("boom")))
    failed = upload(client, instructor, mode="full").json()
    reader.release()
    settled(client, instructor, failed["doc_id"])

    again = upload(client, instructor)                          # this time as text

    assert again.status_code == 201
    listed = client.get(DOCS, params={"token": instructor}).json()["documents"]
    assert [d["doc_id"] for d in listed] == [again.json()["doc_id"]]     # the failed entry made way


# ── Restart ─────────────────────────────────────────────────────────────────

def test_a_reading_cut_short_by_a_restart_shows_as_failed_not_as_processing_for_ever(client, instructor, monkeypatch):
    reader = install(monkeypatch, SlowReader(obeys_stop=False))
    doc = upload(client, instructor, mode="full").json()
    assert reader.started.wait(5)

    monkeypatch.setattr(jobs, "_jobs", {})                     # a new server process knows no job

    listed = client.get(DOCS, params={"token": instructor}).json()["documents"]
    assert [(d["status"], d["error"]) for d in listed] == [("failed", "reading_interrupted")]
    assert files_of(doc["doc_id"]) == []
    reader.release()
    assert reader.finished.wait(5)
    time.sleep(0.05)
    assert fetch(client, instructor, doc["doc_id"])["status"] == "failed"   # the orphan's result changes nothing
    assert files_of(doc["doc_id"]) == []


# ── What is refused before a job starts ─────────────────────────────────────

def test_full_reading_is_for_pdf_files_only(client, instructor, reader):
    response = upload(client, instructor, "notes.txt", b"Plain notes that are long enough to be read.", mode="full")

    assert (response.status_code, error_code(response)) == (400, "full_reading_pdf_only")
    assert stored_files() == [] and reader.calls == 0


def test_a_scan_is_refused_at_once_in_full_reading_too(client, instructor, reader):
    response = upload(client, instructor, "scan.pdf", scanned_pdf(), mode="full")

    assert (response.status_code, error_code(response)) == (422, "no_text")
    assert stored_files() == [] and reader.calls == 0
    assert client.get(DOCS, params={"token": instructor}).json()["documents"] == []


def test_full_reading_has_its_own_page_limit(client, instructor, reader, monkeypatch):
    monkeypatch.setattr(limits, "MAX_FULL_READING_PAGES", 2)

    response = upload(client, instructor, mode="full")          # the handout has three pages

    assert (response.status_code, error_code(response)) == (422, "too_many_pages_for_full_reading")
    assert stored_files() == [] and reader.calls == 0
    assert upload(client, instructor).status_code == 201        # text reading takes it


# ── A document that is not ready ────────────────────────────────────────────

def generate(client, token, doc_id):
    return client.post(f"{BASE}/api/generate", params={"token": token}, json={"doc_ids": [doc_id], "count": 1})


def test_questions_cannot_be_drafted_from_a_document_that_is_still_being_read_or_failed(client, instructor, reader, fake_llm, monkeypatch):
    monkeypatch.setattr(limits, "FULL_READING_SECONDS", 0.3)
    doc = upload(client, instructor, mode="full").json()

    while_reading = generate(client, instructor, doc["doc_id"])
    settled(client, instructor, doc["doc_id"])                  # runs into the time limit
    after_failing = generate(client, instructor, doc["doc_id"])

    assert (while_reading.status_code, error_code(while_reading)) == (409, "document_not_ready")
    assert (after_failing.status_code, error_code(after_failing)) == (409, "document_not_ready")
    assert fake_llm.calls == []


def test_deleting_a_document_that_is_being_read_stops_the_reading(client, instructor, reader):
    doc = upload(client, instructor, mode="full").json()
    assert reader.started.wait(5)

    response = client.delete(f"{DOCS}/{doc['doc_id']}", params={"token": instructor})

    assert response.status_code == 200
    assert reader.finished.wait(5) and reader.was_stopped
    assert client.get(DOCS, params={"token": instructor}).json()["documents"] == []
    assert files_of(doc["doc_id"]) == []


def test_another_course_cannot_follow_or_stop_the_reading(client, launch, instructor, reader):
    doc = upload(client, instructor, mode="full").json()
    other = launch.token(role="Instructor", course="course-B")
    learner = launch.token(role="Learner", course="course-A")

    assert client.get(f"{DOCS}/{doc['doc_id']}", params={"token": other}).status_code == 404
    assert client.delete(f"{DOCS}/{doc['doc_id']}", params={"token": other}).status_code == 404
    assert client.get(f"{DOCS}/{doc['doc_id']}", params={"token": learner}).status_code == 403
    assert fetch(client, instructor, doc["doc_id"])["status"] == "processing"
    reader.release()
    assert settled(client, instructor, doc["doc_id"])["status"] == "ready"


def test_the_chunks_of_a_document_are_not_handed_out_unless_it_is_ready(client, instructor):
    from UltiR.ai_quiz import documents

    doc = upload(client, instructor).json()
    assert documents.load_chunks(cid("course-A"), doc["doc_id"]) != []
    index = storage.course_dir(cid("course-A")) / "documents.json"
    records = storage.read_json(index)
    records[0]["status"] = "failed"                            # its files are still there: only the status says no
    storage.write_json(index, records)

    assert documents.load_chunks(cid("course-A"), doc["doc_id"]) == []
