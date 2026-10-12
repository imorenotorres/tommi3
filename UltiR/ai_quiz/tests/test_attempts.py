"""The learner side: published quizzes, attempts, server grading (rules A4, A5, A6, A13, A14)."""

import json

import pytest

from UltiR.ai_quiz import limits, storage

from .conftest import BASE
from .fake_llm import question, sources_in
from .pdfs import CLEAN_PASSAGE, GARBLED_PASSAGE, evaluation_pdf, handout_pdf

DOCS = f"{BASE}/api/documents"
QUIZZES = f"{BASE}/api/quizzes"
PUBLISHED = f"{BASE}/api/published"
ATTEMPTS = f"{BASE}/api/attempts"

LEARNER_QUIZ_KEYS = {"quiz_id", "title", "revision", "confidence", "questions"}
LEARNER_QUESTION_KEYS = {"question_id", "question", "options", "difficulty"}
LISTING_KEYS = {"quiz_id", "title", "revision", "n_questions", "my_attempts", "my_best"}
PRIVATE_WORDS = ("correct_option_id", "explanation", "Explanation", "excerpt", "grounded", '"source"',
                 "review_status", "doc_id", "chunk_id", "handout.pdf")


def code(response) -> str:
    return response.json()["detail"]["code"]


class Course:
    """One course with an instructor, a document and helpers to drive a quiz to publication."""

    def __init__(self, client, launch, course="course-A"):
        self.client, self.launch, self.course = client, launch, course
        self.instructor = launch.token(role="Instructor", course=course, user="teacher-1")
        doc = client.post(DOCS, params={"token": self.instructor}, files={"file": ("handout.pdf", handout_pdf())})
        self.doc = doc.json()

    def learner(self, user="student-1", **extra):
        return self.launch.token(role="Learner", course=self.course, user=user, **extra)

    def draft(self, count=3, **body):
        response = self.client.post(f"{BASE}/api/generate", params={"token": self.instructor},
                                    json={"doc_ids": [self.doc["doc_id"]], "count": count, **body})
        assert response.status_code == 201, response.text
        return response.json()["quiz"]

    def edit(self, quiz, index, **changes):
        qid = quiz["questions"][index]["question_id"]
        response = self.client.put(f"{QUIZZES}/{quiz['quiz_id']}/questions/{qid}",
                                   params={"token": self.instructor}, json=changes)
        assert response.status_code == 200, response.text
        return response.json()

    def publish(self, quiz):
        response = self.client.post(f"{QUIZZES}/{quiz['quiz_id']}/publish", params={"token": self.instructor})
        assert response.status_code == 200, response.text
        return response.json()

    def published_quiz(self, count=3, **body):
        quiz = self.draft(count, **body)
        for i in range(count):
            self.edit(quiz, i, review_status="approved")
        return self.publish(quiz)


@pytest.fixture
def course(client, launch):
    return Course(client, launch)


@pytest.fixture
def quiz(course):
    return course.published_quiz(3, title="Week 7")


def submit(client, token, quiz, answers, revision=None, **extra):
    body = {"revision": quiz["current_revision"] if revision is None else revision, "answers": answers, **extra}
    return client.post(f"{QUIZZES}/{quiz['quiz_id']}/attempts", params={"token": token}, json=body)


def all_answers(quiz, option="B"):
    return {q["question_id"]: option for q in quiz["questions"]}


def attempt_files():
    return sorted(p for p in storage.data_root().rglob("*.json") if "attempts" in p.parts)


# ── A5: what a learner can see before submitting ────────────────────────────

def test_a_learner_sees_published_quizzes_only_and_no_more_than_a_listing(client, course, quiz):
    course.draft(2, title="Still a draft")
    hidden = course.published_quiz(1, title="Published then withdrawn")
    client.post(f"{QUIZZES}/{hidden['quiz_id']}/unpublish", params={"token": course.instructor})

    listed = client.get(PUBLISHED, params={"token": course.learner()}).json()["quizzes"]

    assert [(q["quiz_id"], q["title"], q["revision"], q["n_questions"]) for q in listed] == [(quiz["quiz_id"], "Week 7", 1, 3)]
    assert set(listed[0]) == LISTING_KEYS


def test_the_quiz_a_learner_receives_has_questions_and_options_and_nothing_else(client, course, quiz):
    response = client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": course.learner()})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == LEARNER_QUIZ_KEYS
    assert len(body["questions"]) == 3
    for q in body["questions"]:
        assert set(q) == LEARNER_QUESTION_KEYS
        assert [set(o) for o in q["options"]] == [{"id", "text"}] * 4
    for private in PRIVATE_WORDS:
        assert private not in response.text


def test_only_approved_questions_are_in_what_a_learner_receives(client, course):
    draft = course.draft(3)
    course.edit(draft, 0, review_status="approved")
    course.edit(draft, 1, review_status="rejected")
    course.publish(draft)

    body = client.get(f"{PUBLISHED}/{draft['quiz_id']}", params={"token": course.learner()}).json()

    assert [q["question_id"] for q in body["questions"]] == [draft["questions"][0]["question_id"]]


@pytest.mark.parametrize("state", ["draft", "unpublished"])
def test_a_quiz_that_is_not_published_does_not_exist_for_a_learner(client, course, state):
    quiz = course.draft(1) if state == "draft" else course.published_quiz(1)
    if state == "unpublished":
        client.post(f"{QUIZZES}/{quiz['quiz_id']}/unpublish", params={"token": course.instructor})
    learner = course.learner()

    assert client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": learner}).status_code == 404
    attempt = client.post(f"{QUIZZES}/{quiz['quiz_id']}/attempts", params={"token": learner},
                          json={"revision": 1, "answers": {}})
    assert attempt.status_code == 404
    assert attempt_files() == []


def test_the_instructor_routes_stay_closed_to_a_learner_who_knows_the_quiz_id(client, course, quiz):
    learner = course.learner()

    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": learner}).status_code == 403
    assert client.get(QUIZZES, params={"token": learner}).status_code == 403
    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": learner}).status_code == 403


# ── A6: the server grades ───────────────────────────────────────────────────

def test_all_correct_answers_score_full_marks_and_the_feedback_arrives_only_now(client, course, quiz):
    response = submit(client, course.learner(), quiz, all_answers(quiz, "B"))

    assert response.status_code == 201
    body = response.json()
    assert (body["score"], body["total"], body["revision"], body["title"]) == (3, 3, 1, "Week 7")
    assert storage.is_id(body["attempt_id"], "a")
    for result in body["results"]:
        assert (result["selected"], result["correct_option_id"], result["correct"]) == ("B", "B", True)
        assert result["explanation"].startswith("Explanation")
        assert result["source"]["doc_label"] == "handout.pdf"
        assert result["source"]["page"] in (1, 2, 3)
        assert result["source"]["excerpt"]
    assert sorted(r["source"]["page"] for r in body["results"]) == [1, 2, 3]


def test_wrong_and_missing_answers_are_counted_as_wrong(client, course, quiz):
    ids = [q["question_id"] for q in quiz["questions"]]

    body = submit(client, course.learner(), quiz, {ids[0]: "B", ids[1]: "C"}).json()

    assert (body["score"], body["total"]) == (1, 3)
    assert [(r["selected"], r["correct"]) for r in body["results"]] == [("B", True), ("C", False), (None, False)]


def test_a_score_sent_by_the_browser_changes_nothing(client, course, quiz):
    forged = {"score": 3, "total": 3, "passed": True, "completed": True, "correct": True,
              "results": [{"correct": True}] * 3, "owner": "someone-else", "attempt_id": "a_" + "0" * 16}

    body = submit(client, course.learner(), quiz, all_answers(quiz, "A"), **forged).json()

    assert (body["score"], body["total"]) == (0, 3)
    assert body["attempt_id"] != forged["attempt_id"]
    stored = storage.read_json(attempt_files()[0])
    assert (stored["score"], stored["total"]) == (0, 3)
    assert "passed" not in stored and "completed" not in stored
    assert stored["owner"] != "someone-else"


@pytest.mark.parametrize("answers", [
    {"q_0000000000000000": "A"},          # a question that is not in this quiz
    "B",
    ["B", "B", "B"],
    None,
    42,
])
def test_answers_that_do_not_belong_to_the_quiz_are_refused_and_nothing_is_stored(client, course, quiz, answers):
    response = submit(client, course.learner(), quiz, answers)

    assert (response.status_code, code(response)) == (400, "bad_request")
    assert attempt_files() == []


@pytest.mark.parametrize("option", ["E", "b", "", 2, True, ["B"], {"id": "B"}])
def test_an_answer_that_is_not_one_of_the_four_options_is_refused(client, course, quiz, option):
    answers = all_answers(quiz)
    answers[quiz["questions"][0]["question_id"]] = option

    response = submit(client, course.learner(), quiz, answers)

    assert (response.status_code, code(response)) == (400, "bad_request")
    assert attempt_files() == []


@pytest.mark.parametrize("revision", [0, 2, -1, "1", 1.0, True, None])
def test_an_attempt_must_name_a_revision_that_exists(client, course, quiz, revision):
    response = client.post(f"{QUIZZES}/{quiz['quiz_id']}/attempts", params={"token": course.learner()},
                           json={"revision": revision, "answers": all_answers(quiz)})

    assert (response.status_code, code(response)) == (400, "bad_request")
    assert attempt_files() == []


def test_the_number_of_attempts_per_learner_and_quiz_is_capped(client, course, quiz, monkeypatch):
    monkeypatch.setattr(limits, "MAX_ATTEMPTS_PER_QUIZ", 2)
    first, second = course.learner("student-1"), course.learner("student-2")
    for _ in range(2):
        assert submit(client, first, quiz, all_answers(quiz)).status_code == 201

    third = submit(client, first, quiz, all_answers(quiz))

    assert (third.status_code, code(third)) == (429, "too_many_attempts")
    assert submit(client, second, quiz, all_answers(quiz)).status_code == 201


# ── A13: who an attempt belongs to ──────────────────────────────────────────

def test_a_stored_attempt_holds_a_keyed_hash_and_nothing_that_identifies_the_person(client, course, quiz):
    learner = course.learner("student-4711", name="Synthetic Student", email="student@example.invalid")

    submit(client, learner, quiz, all_answers(quiz))

    (path,) = attempt_files()
    text = path.read_text(encoding="utf-8")
    for private in ("student-4711", "Synthetic Student", "student@example.invalid", learner, "course-A"):
        assert private not in text
    owner = json.loads(text)["owner"]
    assert len(owner) >= 32 and owner != "student-4711"


def test_the_owner_hash_is_stable_per_person_distinct_across_people_and_courses_and_depends_on_the_key(
        client, launch, course, quiz, monkeypatch):
    def owner_of(token, target=quiz):
        attempt_id = submit(client, token, target, all_answers(target)).json()["attempt_id"]
        return next(storage.read_json(p)["owner"] for p in attempt_files() if attempt_id in p.name)

    same_again = owner_of(course.learner("student-1"))
    assert owner_of(course.learner("student-1")) == same_again
    assert owner_of(course.learner("student-2")) != same_again

    other = Course(client, launch, course="course-B")
    assert owner_of(other.learner("student-1"), other.published_quiz(1)) != same_again

    monkeypatch.setenv("AI_QUIZ_ID_KEY", "a-different-key")
    assert owner_of(course.learner("student-1")) != same_again


def test_an_attempt_without_a_user_id_is_refused(client, course, quiz):
    response = submit(client, course.learner(user=""), quiz, all_answers(quiz))

    assert (response.status_code, code(response)) == (400, "no_user")
    assert attempt_files() == []


# ── Reading an attempt back ─────────────────────────────────────────────────

def test_an_attempt_can_be_read_by_its_owner_and_by_the_course_instructor_only(client, launch, course, quiz):
    owner = course.learner("student-1")
    submitted = submit(client, owner, quiz, all_answers(quiz)).json()
    url = f"{ATTEMPTS}/{submitted['attempt_id']}"

    assert client.get(url, params={"token": owner}).json() == submitted
    assert client.get(url, params={"token": course.learner("student-1")}).json() == submitted   # a later session
    assert client.get(url, params={"token": course.instructor}).json() == submitted
    assert client.get(url, params={"token": course.learner("student-2")}).status_code == 404
    assert client.get(url, params={"token": launch.token(role="Instructor", course="course-B")}).status_code == 404
    assert client.get(url, params={"token": launch.token(role="Learner", course="course-B", user="student-1")}).status_code == 404


@pytest.mark.parametrize("attempt_id", ["a_0000000000000000", "nonsense", "z_0123456789abcdef", "a_..%2F..%2Fmeta"])
def test_an_unknown_or_malformed_attempt_id_is_not_found(client, course, quiz, attempt_id):
    submit(client, course.learner(), quiz, all_answers(quiz))

    assert client.get(f"{ATTEMPTS}/{attempt_id}", params={"token": course.learner()}).status_code == 404


def test_the_listing_shows_a_learner_their_own_attempts_and_best_score(client, course, quiz):
    mine, other = course.learner("student-1"), course.learner("student-2")
    ids = [q["question_id"] for q in quiz["questions"]]
    submit(client, mine, quiz, {ids[0]: "B"})
    submit(client, mine, quiz, {ids[0]: "B", ids[1]: "B"})
    submit(client, other, quiz, all_answers(quiz))

    listing = client.get(PUBLISHED, params={"token": mine}).json()["quizzes"][0]
    fresh = client.get(PUBLISHED, params={"token": course.learner("student-3")}).json()["quizzes"][0]

    assert (listing["my_attempts"], listing["my_best"]) == (2, 2)
    assert (fresh["my_attempts"], fresh["my_best"]) == (0, None)


# ── A14: a past attempt keeps its meaning ───────────────────────────────────

def test_editing_and_republishing_does_not_change_a_past_attempt(client, course, quiz):
    learner = course.learner()
    before = submit(client, learner, quiz, all_answers(quiz, "B")).json()
    url = f"{ATTEMPTS}/{before['attempt_id']}"

    course.edit(quiz, 0, question="A rewritten first question?", correct_option_id="A", explanation="New reasoning.")
    course.edit(quiz, 1, review_status="rejected")
    republished = course.publish(quiz)

    assert republished["current_revision"] == 2
    assert client.get(url, params={"token": learner}).json() == before
    # the new revision is what learners get now, graded with the new key
    now = client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": learner}).json()
    assert (now["revision"], len(now["questions"]), now["questions"][0]["question"]) == (2, 2, "A rewritten first question?")
    after = submit(client, learner, republished, {quiz["questions"][0]["question_id"]: "B"}).json()
    assert (after["revision"], after["results"][0]["correct"], after["results"][0]["correct_option_id"]) == (2, False, "A")


def test_an_attempt_started_on_the_old_revision_is_graded_by_the_old_revision(client, course, quiz):
    learner = course.learner()
    course.edit(quiz, 0, correct_option_id="A")
    course.publish(quiz)

    old = submit(client, learner, quiz, all_answers(quiz, "B"), revision=1).json()

    assert (old["revision"], old["score"]) == (1, 3)


# ── A4: another course ──────────────────────────────────────────────────────

def test_a_learner_of_another_course_cannot_see_or_take_the_quiz(client, launch, course, quiz):
    outsider = launch.token(role="Learner", course="course-B", user="student-1")

    assert client.get(PUBLISHED, params={"token": outsider}).json()["quizzes"] == []
    assert client.get(f"{PUBLISHED}/{quiz['quiz_id']}", params={"token": outsider}).status_code == 404
    assert submit(client, outsider, quiz, all_answers(quiz)).status_code == 404
    assert attempt_files() == []


# ── What a student sees as the source ───────────────────────────────────────
# A clean, located passage is quoted. A passage that carries flattened mathematics, or that
# the server could not locate, is never quoted: the student gets the page number only.

# The test document and its two passages are in pdfs.py: page 2 is the passage behind draft 9
# of the real model run, where text reading had flattened the F1 formula.
GARBLED, CLEAN = GARBLED_PASSAGE, CLEAN_PASSAGE


def quiz_quoting(client, course, fake_llm, excerpt, accept=False):
    """A published one-question quiz on the math document whose question quotes `excerpt`."""
    doc = client.post(DOCS, params={"token": course.instructor},
                      files={"file": ("evaluation.pdf", evaluation_pdf())}).json()

    def reply(messages):
        sources = sources_in(messages)
        sid = next(s for s, text in sources.items() if "harmonic mean" in text)
        return json.dumps({"questions": [question(sid, sources[sid], 1, excerpt=excerpt)]})
    fake_llm.queue(reply)
    response = client.post(f"{BASE}/api/generate", params={"token": course.instructor},
                           json={"doc_ids": [doc["doc_id"]], "count": 1})
    draft = response.json()["quiz"]
    changes = {"review_status": "approved", **({"accept_ungrounded": True} if accept else {})}
    course.edit(draft, 0, **changes)
    return course.publish(draft)


def instructor_question(client, course, quiz):
    return client.get(f"{QUIZZES}/{quiz['quiz_id']}", params={"token": course.instructor}).json()["questions"][0]


def test_a_clean_located_passage_is_quoted_to_the_student_with_its_page(client, course, fake_llm):
    quiz = quiz_quoting(client, course, fake_llm, CLEAN)

    response = submit(client, course.learner(), quiz, all_answers(quiz))

    assert response.json()["results"][0]["source"] == {"doc_label": "evaluation.pdf", "page": 2, "excerpt": CLEAN}
    assert instructor_question(client, course, quiz)["passage_for_students"] == "shown"


def test_a_passage_with_a_flattened_formula_is_never_quoted_to_the_student(client, course, fake_llm):
    quiz = quiz_quoting(client, course, fake_llm, GARBLED)

    response = submit(client, course.learner(), quiz, all_answers(quiz))

    assert response.status_code == 201
    assert response.json()["results"][0]["source"] == {"doc_label": "evaluation.pdf", "page": 2, "excerpt": None}
    assert "21 P + 1R" not in response.text
    again = client.get(f"{ATTEMPTS}/{response.json()['attempt_id']}", params={"token": course.learner()})
    assert "21 P + 1R" not in again.text


def test_the_instructor_is_told_that_students_will_not_see_that_passage(client, course, fake_llm):
    quiz = quiz_quoting(client, course, fake_llm, GARBLED)

    q = instructor_question(client, course, quiz)

    assert q["grounded"] is True                          # it is in the document, as the reader extracted it
    assert q["source"]["excerpt"] == GARBLED              # the instructor still sees it, to check against the PDF
    assert q["passage_for_students"] == "hidden_math"


def test_a_question_from_a_mathematical_part_of_the_document_can_still_quote_clean_prose(client, course, fake_llm):
    quiz = quiz_quoting(client, course, fake_llm, CLEAN)

    q = instructor_question(client, course, quiz)

    assert q["math_in_source"] is True                    # the chunk it was written from holds a formula
    assert q["passage_for_students"] == "shown"           # but the passage it quotes does not


def test_an_unverified_passage_is_never_shown_to_a_learner_as_the_source(client, course, fake_llm):
    invented = "An invented passage that the handout does not contain anywhere at all."

    def reply(messages):
        (sid, text), *_ = sources_in(messages).items()
        return json.dumps({"questions": [question(sid, text, 1, excerpt=invented)]})
    fake_llm.queue(reply)
    draft = course.draft(1)
    course.edit(draft, 0, review_status="approved", accept_ungrounded=True)
    published = course.publish(draft)

    response = submit(client, course.learner(), published, all_answers(published))

    assert response.status_code == 201
    # the page of the part of the document the question was written from, and no passage
    assert response.json()["results"][0]["source"] == {"doc_label": "handout.pdf", "page": 1, "excerpt": None}
    assert invented not in response.text
    assert instructor_question(client, course, published)["passage_for_students"] == "hidden_unlocated"


# ── The instructor's summary ────────────────────────────────────────────────

def test_the_summary_counts_attempts_without_naming_anyone(client, course, quiz):
    ids = [q["question_id"] for q in quiz["questions"]]
    submit(client, course.learner("student-1", name="Ada Synthetic"), quiz, all_answers(quiz, "B"))       # 3 of 3
    submit(client, course.learner("student-1", name="Ada Synthetic"), quiz, {ids[0]: "B"})                # 1 of 3
    submit(client, course.learner("student-2", name="Bo Synthetic"), quiz, {ids[0]: "B", ids[1]: "A"})    # 1 of 3
    submit(client, course.instructor, quiz, all_answers(quiz, "A"))                                       # a preview

    response = client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": course.instructor})

    assert response.status_code == 200
    body = response.json()
    assert (body["attempts"], body["learners"]) == (3, 2)
    assert body["average_percent"] == 56                       # (100 + 33.3 + 33.3) / 3
    assert [(q["question_id"], q["answered"], q["correct"]) for q in body["questions"]] == [
        (ids[0], 3, 3), (ids[1], 2, 1), (ids[2], 1, 1)]
    for private in ("Ada", "Bo Synthetic", "student-1", "student-2", "owner"):
        assert private not in response.text


def test_the_summary_of_another_courses_quiz_is_not_found(client, launch, course, quiz):
    other = launch.token(role="Instructor", course="course-B")

    assert client.get(f"{QUIZZES}/{quiz['quiz_id']}/summary", params={"token": other}).status_code == 404
