"""Instructor review: edit, approve, publish, revisions (rules A3, A4, A8, A9, A14)."""

import json

import pytest

from UltiR.ai_quiz import limits, storage

from .conftest import BASE, cid
from .fake_llm import question, sources_in
from .pdfs import handout_pdf

DOCS = f"{BASE}/api/documents"
QUIZZES = f"{BASE}/api/quizzes"


def code(response) -> str:
    return response.json()["detail"]["code"]


@pytest.fixture
def instructor(launch):
    return launch.token(role="Instructor", course="course-A")


@pytest.fixture
def doc(client, instructor):
    return client.post(DOCS, params={"token": instructor}, files={"file": ("handout.pdf", handout_pdf())}).json()


def new_quiz(client, token, doc, count=3, **body):
    response = client.post(f"{BASE}/api/generate", params={"token": token},
                           json={"doc_ids": [doc["doc_id"]], "count": count, **body})
    assert response.status_code == 201, response.text
    return response.json()["quiz"]


@pytest.fixture
def quiz(client, instructor, doc):
    return new_quiz(client, instructor, doc, count=3, title="Week 7")


def get(client, token, quiz_id):
    return client.get(f"{QUIZZES}/{quiz_id}", params={"token": token})


def put_question(client, token, quiz_id, qid, /, **changes):
    return client.put(f"{QUIZZES}/{quiz_id}/questions/{qid}", params={"token": token}, json=changes)


def approve(client, token, quiz, *indexes):
    for i in indexes:
        response = put_question(client, token, quiz["quiz_id"], quiz["questions"][i]["question_id"],
                                review_status="approved")
        assert response.status_code == 200, response.text


def publish(client, token, quiz_id):
    return client.post(f"{QUIZZES}/{quiz_id}/publish", params={"token": token})


def unpublish(client, token, quiz_id):
    return client.post(f"{QUIZZES}/{quiz_id}/unpublish", params={"token": token})


def revision_file(quiz_id, number, course="course-A"):
    return storage.course_dir(cid(course)) / "quizzes" / quiz_id / f"rev-{number:04d}.json"


def ungrounded_quiz(client, token, doc, fake_llm):
    """A one-question draft whose excerpt is nowhere in the material."""
    def reply(messages):
        (sid, text), *_ = sources_in(messages).items()
        return json.dumps({"questions": [question(sid, text, 1, excerpt="An invented passage that the handout "
                                                                        "does not contain anywhere at all.")]})
    fake_llm.queue(reply)
    return new_quiz(client, token, doc, count=1)


# ── Listing and reading ─────────────────────────────────────────────────────

def test_quizzes_are_listed_newest_first_with_counts_by_status(client, instructor, doc):
    first = new_quiz(client, instructor, doc, count=2, title="First")
    second = new_quiz(client, instructor, doc, count=3, title="Second")
    approve(client, instructor, second, 0)

    listed = client.get(QUIZZES, params={"token": instructor}).json()["quizzes"]

    assert [(q["quiz_id"], q["title"]) for q in listed] == [(second["quiz_id"], "Second"), (first["quiz_id"], "First")]
    assert listed[0]["counts"] == {"draft": 2, "approved": 1, "rejected": 0}
    assert listed[0]["published"] is False
    assert "questions" not in listed[0]


def test_the_instructor_sees_the_whole_draft_including_the_key(client, instructor, quiz):
    body = get(client, instructor, quiz["quiz_id"]).json()

    assert body == quiz
    assert all(q["correct_option_id"] == "B" for q in body["questions"])


# ── Renaming ────────────────────────────────────────────────────────────────

def test_a_quiz_can_be_renamed(client, instructor, quiz):
    response = client.put(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": instructor}, json={"title": "  Matching  "})

    assert response.status_code == 200
    assert get(client, instructor, quiz["quiz_id"]).json()["title"] == "Matching"


@pytest.mark.parametrize("title", ["", "   ", "t" * 201, 7, None, ["x"]])
def test_a_title_that_is_empty_too_long_or_not_text_is_refused(client, instructor, quiz, title):
    response = client.put(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": instructor}, json={"title": title})

    assert (response.status_code, code(response)) == (400, "bad_request")
    assert get(client, instructor, quiz["quiz_id"]).json()["title"] == "Week 7"


# ── Editing a question ──────────────────────────────────────────────────────

def test_an_instructor_can_rewrite_a_question(client, instructor, quiz):
    qid = quiz["questions"][0]["question_id"]
    new_options = [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"},
                   {"id": "C", "text": "Three"}, {"id": "D", "text": "Four"}]

    response = put_question(client, instructor, quiz["quiz_id"], qid, question="What does the ratio test compare?",
                            options=new_options, correct_option_id="D", explanation="Because.", difficulty="basic")

    assert response.status_code == 200
    q = get(client, instructor, quiz["quiz_id"]).json()["questions"][0]
    assert (q["question"], q["options"], q["correct_option_id"], q["explanation"], q["difficulty"]) == (
        "What does the ratio test compare?", new_options, "D", "Because.", "basic")
    assert q["edited"] is True
    assert q["question_id"] == qid


INVALID_EDITS = {
    "three options": {"options": [{"id": "A", "text": "1"}, {"id": "B", "text": "2"}, {"id": "C", "text": "3"}]},
    "two identical options": {"options": [{"id": "A", "text": "same"}, {"id": "B", "text": " SAME "},
                                          {"id": "C", "text": "3"}, {"id": "D", "text": "4"}]},
    "an option id twice": {"options": [{"id": "A", "text": "1"}, {"id": "A", "text": "2"},
                                       {"id": "C", "text": "3"}, {"id": "D", "text": "4"}]},
    "a key that is not an option": {"correct_option_id": "E"},
    "an empty question": {"question": "   "},
    "a question that is not text": {"question": 5},
    "a question that is far too long": {"question": "word " * 500},
    "an explanation that is far too long": {"explanation": "word " * 500},
    "an unknown difficulty": {"difficulty": "nightmare"},
    "an unknown status": {"review_status": "published"},
    "a flag that is not true or false": {"accept_ungrounded": "yes"},
}


@pytest.mark.parametrize("name", sorted(INVALID_EDITS))
def test_an_edit_that_breaks_the_question_is_refused_and_changes_nothing(client, instructor, quiz, name):
    qid = quiz["questions"][0]["question_id"]

    response = put_question(client, instructor, quiz["quiz_id"], qid, **INVALID_EDITS[name])

    assert response.status_code == 400
    assert code(response) in ("invalid_question", "bad_request")
    assert get(client, instructor, quiz["quiz_id"]).json() == quiz


def test_an_edit_cannot_touch_the_source_the_grounding_or_the_id(client, instructor, doc, fake_llm):
    quiz = ungrounded_quiz(client, instructor, doc, fake_llm)
    q = quiz["questions"][0]

    response = put_question(client, instructor, quiz["quiz_id"], q["question_id"], grounded=True, question_id="q_" + "0" * 16,
                            source={"page": 99, "excerpt": "forged"}, explanation="Only this may change.")

    assert response.status_code == 200
    after = get(client, instructor, quiz["quiz_id"]).json()["questions"][0]
    assert after["explanation"] == "Only this may change."
    assert (after["grounded"], after["source"], after["question_id"]) == (False, q["source"], q["question_id"])


def test_an_edit_that_repeats_another_question_of_the_quiz_is_refused(client, instructor, quiz):
    first, second = quiz["questions"][0], quiz["questions"][1]

    response = put_question(client, instructor, quiz["quiz_id"], second["question_id"],
                            question=first["question"].upper())

    assert (response.status_code, code(response)) == (409, "duplicate_question")


# ── Approving and rejecting ─────────────────────────────────────────────────

def test_a_grounded_question_can_be_approved_rejected_and_returned_to_draft(client, instructor, quiz):
    qid = quiz["questions"][0]["question_id"]

    for status in ("approved", "rejected", "draft"):
        assert put_question(client, instructor, quiz["quiz_id"], qid, review_status=status).status_code == 200
        assert get(client, instructor, quiz["quiz_id"]).json()["questions"][0]["review_status"] == status


def test_a_question_without_a_located_passage_cannot_be_approved_silently(client, instructor, doc, fake_llm):
    quiz = ungrounded_quiz(client, instructor, doc, fake_llm)
    qid = quiz["questions"][0]["question_id"]

    response = put_question(client, instructor, quiz["quiz_id"], qid, review_status="approved")

    assert (response.status_code, code(response)) == (409, "needs_acceptance")
    assert get(client, instructor, quiz["quiz_id"]).json()["questions"][0]["review_status"] == "draft"


def test_the_instructor_can_accept_it_explicitly_and_then_approve(client, instructor, doc, fake_llm):
    quiz = ungrounded_quiz(client, instructor, doc, fake_llm)
    qid = quiz["questions"][0]["question_id"]

    response = put_question(client, instructor, quiz["quiz_id"], qid, review_status="approved", accept_ungrounded=True)

    assert response.status_code == 200
    q = get(client, instructor, quiz["quiz_id"]).json()["questions"][0]
    assert (q["review_status"], q["grounded"], q["ungrounded_accepted"]) == ("approved", False, True)


def test_withdrawing_the_acceptance_takes_the_approval_with_it(client, instructor, doc, fake_llm):
    quiz = ungrounded_quiz(client, instructor, doc, fake_llm)
    qid = quiz["questions"][0]["question_id"]
    put_question(client, instructor, quiz["quiz_id"], qid, review_status="approved", accept_ungrounded=True)

    put_question(client, instructor, quiz["quiz_id"], qid, accept_ungrounded=False)

    q = get(client, instructor, quiz["quiz_id"]).json()["questions"][0]
    assert (q["review_status"], q["ungrounded_accepted"]) == ("draft", False)


# ── Publishing ──────────────────────────────────────────────────────────────

def test_a_quiz_with_nothing_approved_cannot_be_published(client, instructor, quiz):
    response = publish(client, instructor, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (409, "nothing_approved")
    assert get(client, instructor, quiz["quiz_id"]).json()["published"] is False
    assert not revision_file(quiz["quiz_id"], 1).exists()


def test_publishing_writes_a_revision_with_the_approved_questions_only(client, instructor, quiz):
    approve(client, instructor, quiz, 0, 2)
    put_question(client, instructor, quiz["quiz_id"], quiz["questions"][1]["question_id"], review_status="rejected")

    response = publish(client, instructor, quiz["quiz_id"])

    assert response.status_code == 200
    body = response.json()
    assert (body["published"], body["current_revision"]) == (True, 1)
    revision = storage.read_json(revision_file(quiz["quiz_id"], 1))
    assert revision["revision"] == 1
    assert revision["title"] == "Week 7"
    assert [q["question_id"] for q in revision["questions"]] == [quiz["questions"][0]["question_id"],
                                                                 quiz["questions"][2]["question_id"]]


def test_a_later_publication_is_a_new_revision_and_the_old_one_is_untouched(client, instructor, quiz):
    approve(client, instructor, quiz, 0)
    publish(client, instructor, quiz["quiz_id"])
    first = revision_file(quiz["quiz_id"], 1)
    before = (first.read_bytes(), first.stat().st_mtime_ns)

    put_question(client, instructor, quiz["quiz_id"], quiz["questions"][0]["question_id"],
                 question="A reworded question about the same passage?", correct_option_id="A")
    approve(client, instructor, quiz, 1)
    client.put(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": instructor}, json={"title": "Renamed"})
    response = publish(client, instructor, quiz["quiz_id"])

    assert response.json()["current_revision"] == 2
    assert (first.read_bytes(), first.stat().st_mtime_ns) == before
    second = storage.read_json(revision_file(quiz["quiz_id"], 2))
    assert second["title"] == "Renamed"
    assert len(second["questions"]) == 2
    assert second["questions"][0]["question"] == "A reworded question about the same passage?"


def test_editing_the_draft_does_not_change_what_is_published(client, instructor, quiz):
    approve(client, instructor, quiz, 0)
    publish(client, instructor, quiz["quiz_id"])
    before = revision_file(quiz["quiz_id"], 1).read_bytes()

    put_question(client, instructor, quiz["quiz_id"], quiz["questions"][0]["question_id"],
                 question="Changed after publication?", review_status="rejected")

    assert revision_file(quiz["quiz_id"], 1).read_bytes() == before
    assert get(client, instructor, quiz["quiz_id"]).json()["current_revision"] == 1


def test_publishing_again_without_changes_is_refused(client, instructor, quiz):
    approve(client, instructor, quiz, 0)
    publish(client, instructor, quiz["quiz_id"])

    response = publish(client, instructor, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (409, "no_changes")
    assert not revision_file(quiz["quiz_id"], 2).exists()


def test_unpublishing_hides_the_quiz_and_republishing_unchanged_reuses_the_revision(client, instructor, quiz):
    approve(client, instructor, quiz, 0)
    publish(client, instructor, quiz["quiz_id"])

    assert unpublish(client, instructor, quiz["quiz_id"]).json()["published"] is False
    again = publish(client, instructor, quiz["quiz_id"])

    assert (again.json()["published"], again.json()["current_revision"]) == (True, 1)
    assert not revision_file(quiz["quiz_id"], 2).exists()


def test_a_quiz_that_is_not_published_cannot_be_unpublished(client, instructor, quiz):
    response = unpublish(client, instructor, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (409, "not_published")


def test_a_revision_another_process_wrote_first_is_never_overwritten(client, instructor, quiz, monkeypatch):
    """Two server processes publish the same quiz at the same moment. The per-course lock is per
    process, so both may get as far as writing revision 1. The second must fail, not replace it."""
    from UltiR.ai_quiz import review

    approve(client, instructor, quiz, 0)
    path = revision_file(quiz["quiz_id"], 1)
    other_process_wrote = {"quiz_id": quiz["quiz_id"], "revision": 1, "title": "From the other process",
                           "published_at": "2026-01-01T00:00:00+00:00", "questions": [{"question_id": "q_theirs"}]}
    real_now = review._now

    def now_while_the_other_process_publishes():
        if not path.exists():
            storage.write_json(path, other_process_wrote)       # it gets there first, mid-way through ours
        return real_now()
    monkeypatch.setattr(review, "_now", now_while_the_other_process_publishes)

    response = publish(client, instructor, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (409, "revision_exists")
    assert storage.read_json(path) == other_process_wrote
    assert [p.name for p in path.parent.iterdir() if p.name.startswith(("rev-", "."))] == ["rev-0001.json"]


def test_a_flagged_question_cannot_reach_a_revision_even_if_the_draft_file_says_approved(
        client, instructor, doc, fake_llm):
    quiz = ungrounded_quiz(client, instructor, doc, fake_llm)
    draft = storage.course_dir(cid("course-A")) / "quizzes" / quiz["quiz_id"] / "draft.json"
    questions = storage.read_json(draft)
    questions[0]["review_status"] = "approved"          # as if written around the API
    storage.write_json(draft, questions)

    response = publish(client, instructor, quiz["quiz_id"])

    assert (response.status_code, code(response)) == (409, "needs_acceptance")
    assert not revision_file(quiz["quiz_id"], 1).exists()


# ── Another course, unknown ids (A4) ────────────────────────────────────────

def test_another_course_cannot_see_or_change_the_quiz(client, launch, instructor, quiz):
    other = launch.token(role="Instructor", course="course-B")
    approve(client, instructor, quiz, 0)
    quiz_id, qid = quiz["quiz_id"], quiz["questions"][0]["question_id"]

    assert client.get(QUIZZES, params={"token": other}).json()["quizzes"] == []
    assert get(client, other, quiz_id).status_code == 404
    assert client.put(f"{QUIZZES}/{quiz_id}", params={"token": other}, json={"title": "Mine now"}).status_code == 404
    assert put_question(client, other, quiz_id, qid, review_status="rejected").status_code == 404
    assert publish(client, other, quiz_id).status_code == 404
    assert unpublish(client, other, quiz_id).status_code == 404
    unchanged = get(client, instructor, quiz_id).json()
    assert (unchanged["title"], unchanged["published"], unchanged["questions"][0]["review_status"]) == (
        "Week 7", False, "approved")


@pytest.mark.parametrize("quiz_id", ["z_0000000000000000", "nonsense", "..", "d_0123456789abcdef", "z_../../x"])
def test_an_unknown_or_malformed_quiz_id_is_not_found(client, instructor, quiz, quiz_id):
    assert get(client, instructor, quiz_id).status_code == 404
    assert publish(client, instructor, quiz_id).status_code == 404
    assert put_question(client, instructor, quiz_id, quiz["questions"][0]["question_id"],
                        review_status="approved").status_code == 404


@pytest.mark.parametrize("question_id", ["q_0000000000000000", "nonsense", "q_..%2F..%2Fdraft", "z_0123456789abcdef"])
def test_an_unknown_question_id_is_not_found(client, instructor, quiz, question_id):
    response = put_question(client, instructor, quiz["quiz_id"], question_id, review_status="approved")

    assert response.status_code == 404
    assert get(client, instructor, quiz["quiz_id"]).json() == quiz


def test_the_number_of_quizzes_per_course_is_capped(client, instructor, doc, monkeypatch):
    monkeypatch.setattr(limits, "MAX_QUIZZES_PER_COURSE", 1)
    new_quiz(client, instructor, doc, count=1)

    response = client.post(f"{BASE}/api/generate", params={"token": instructor},
                           json={"doc_ids": [doc["doc_id"]], "count": 1})

    assert (response.status_code, code(response)) == (409, "too_many_quizzes")
