"""Course-scoped storage: one folder per course, atomic JSON, no lost updates (rule A4 groundwork)."""

import json
import threading

import pytest

from UltiR.ai_quiz import storage


# ── One folder per course, always inside the data folder ────────────────────

@pytest.mark.parametrize("a, b", [
    ("course-1", "course-2"),
    ("course/1", "course1"),          # differ only in a character that is not kept
    ("Course1", "course1"),           # differ only in case
    ("", "default"),                  # an empty id is not the same course as "default"
    ("a" * 80, "a" * 81),             # differ only beyond the length that is kept
    ("curso-ñ", "curso-n"),
])
def test_two_different_course_ids_never_share_a_folder(a, b):
    assert storage.course_dir(a) != storage.course_dir(b)


def test_the_same_course_id_always_gets_the_same_folder():
    assert storage.course_dir("course-1") == storage.course_dir("course-1")


@pytest.mark.parametrize("hostile", [
    "../../etc",
    "..",
    "/etc/passwd",
    "a/../../b",
    "C:\\Windows",
    "course\x00id",
    "x" * 5000,
    ".",
    " ",
])
def test_a_hostile_course_id_still_lands_directly_inside_the_data_folder(hostile):
    folder = storage.course_dir(hostile)

    assert folder.parent == storage.data_root()
    assert folder.is_dir()
    assert len(folder.name) <= 64


# ── Ids that come back in URLs ──────────────────────────────────────────────

def test_new_ids_are_unique_and_valid_for_their_kind():
    ids = {storage.new_id("d") for _ in range(200)}

    assert len(ids) == 200
    assert all(storage.is_id(i, "d") for i in ids)


@pytest.mark.parametrize("value", [
    "", "x", "d_", "d_../../etc", "d_ZZZZZZZZZZZZZZZZ", "q_0123456789abcdef",
    "d_0123456789abcdef0", "d_0123456789ABCDEF", "../d_0123456789abcdef", None, 7,
])
def test_anything_else_is_not_a_document_id(value):
    assert storage.is_id(value, "d") is False


# ── JSON files ──────────────────────────────────────────────────────────────

def test_json_written_is_json_read_back(tmp_path):
    path = tmp_path / "sub" / "file.json"

    storage.write_json(path, {"título": "visión", "n": 3})

    assert storage.read_json(path) == {"título": "visión", "n": 3}
    assert json.loads(path.read_text(encoding="utf-8")) == {"título": "visión", "n": 3}


def test_reading_a_missing_file_gives_the_default(tmp_path):
    assert storage.read_json(tmp_path / "nothing.json", default=[]) == []


def test_a_failed_write_leaves_the_old_content_and_no_leftovers(tmp_path):
    path = tmp_path / "file.json"
    storage.write_json(path, {"version": 1})

    with pytest.raises(TypeError):
        storage.write_json(path, {"version": 2, "bad": object()})

    assert storage.read_json(path) == {"version": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["file.json"]


def test_concurrent_updates_in_one_course_are_not_lost():
    course = "course-1"
    path = storage.course_dir(course) / "counter.json"

    def bump():
        for _ in range(40):
            with storage.locked(course):
                data = storage.read_json(path, default={"n": 0})
                data["n"] += 1
                storage.write_json(path, data)

    threads = [threading.Thread(target=bump) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert storage.read_json(path) == {"n": 320}


def test_the_course_lock_can_be_taken_again_by_the_code_that_holds_it():
    with storage.locked("course-1"):
        with storage.locked("course-1"):
            pass
