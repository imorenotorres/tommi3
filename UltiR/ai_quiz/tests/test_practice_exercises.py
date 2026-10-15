"""Practice, part two: writing one exercise from a topic, and the checks before any student sees it.

The passage an exercise cites must be in the topic; a numerical exercise is worked out a second
time by a separate call that is not told the first answer; a discarded exercise is written again
at most twice, and every discard is recorded with its reason.
"""

import asyncio
import json

import pytest

from UltiR.ai_quiz import exercise_types, exercises, limits, topics

from .conftest import cid
from .fake_llm import sources_in
from .fake_practice import CHECK, check_reply, exercise, exercise_reply, kind_of, user_text
from .practice_helpers import PracticeCourse, run


@pytest.fixture(autouse=True)
def practice_on(monkeypatch):
    monkeypatch.setenv("AI_QUIZ_PRACTICE_ENABLED", "1")


@pytest.fixture
def course(client, launch):
    return PracticeCourse(client, launch)


def topic_of(course, number=1):
    found = topics.course_topics(cid(course.course))[number]
    return found, topics.topic_chunks(cid(course.course), found)


def write(course, number=1, kind="abierta", level="intermedio", language="es", target=None, avoid=()):
    topic, chunks = topic_of(course, number)
    return run(exercises.write(cid(course.course), topic, chunks, level, kind, language, target, list(avoid)))


def rejections(course):
    return exercises.rejections(cid(course.course))


# ── The parts of an exercise ────────────────────────────────────────────────

def good(**changes):
    item = {"statement": "Explain it.", "reference_solution": "It is so.", "key_points": ["One", "Two"],
            "typical_mistakes": ["Wrong one", "Wrong two"]}
    item.update(changes)
    return item


def test_the_core_of_an_exercise_is_numbered_by_the_server():
    core = exercise_types.core(good(key_points=[{"id": "X9", "text": "One"}, "Two", "Three"]))

    assert [p["id"] for p in core["key_points"]] == ["K1", "K2", "K3"]
    assert [m["id"] for m in core["typical_mistakes"]] == ["M1", "M2"]
    assert set(core) == {"statement", "reference_solution", "key_points", "typical_mistakes"}


@pytest.mark.parametrize("changes", [
    {"statement": ""}, {"statement": 5}, {"reference_solution": None},
    {"key_points": ["Only one"]}, {"key_points": ["a", "b", "c", "d", "e"]}, {"key_points": ["Same", "same"]},
    {"key_points": "One, two"}, {"typical_mistakes": ["Only one"]}, {"typical_mistakes": ["a", "b", "c", "d"]},
    {"statement": "x" * 1001}, {"key_points": ["x" * 301, "Two"]},
])
def test_a_malformed_exercise_is_refused(changes):
    with pytest.raises(exercise_types.InvalidExercise):
        exercise_types.core(good(**changes))


@pytest.mark.parametrize("typed, number", [
    ("17", 17.0), (" 0,95 ", 0.95), ("1.5e3", 1500.0), ("−3", -3.0), ("1 177", 1177.0), (72, 72.0), (0.5, 0.5),
])
def test_numbers_are_read_as_people_write_them(typed, number):
    assert exercise_types.parse_number(typed) == number


@pytest.mark.parametrize("typed", ["", "seventeen", "1,2,3", "1.2.3", True, None, [17], "nan", "inf", "1" * 41])
def test_what_is_not_a_number_is_none(typed):
    assert exercise_types.parse_number(typed) is None


def test_two_values_agree_within_the_relative_tolerance():
    assert exercise_types.agree(17, 17.1, 0.01)
    assert not exercise_types.agree(17, 17.5, 0.01)
    assert not exercise_types.agree(5, 17, 0.05)
    assert exercise_types.agree(0, 0, 0.01)


def test_the_tolerance_the_model_proposes_is_kept_within_bounds():
    numeric = exercise_types.TYPES["numerica"]

    assert numeric.fields({"answer": {"value": 1, "tolerance": 0.5}})["answer"]["tolerance"] == exercise_types.MAX_TOLERANCE
    assert numeric.fields({"answer": {"value": 1, "tolerance": 0}})["answer"]["tolerance"] == exercise_types.DEFAULT_TOLERANCE
    assert numeric.fields({"answer": {"value": 1, "tolerance": 0.0001}})["answer"]["tolerance"] == exercise_types.MIN_TOLERANCE
    with pytest.raises(exercise_types.InvalidExercise):
        numeric.fields({"answer": {"value": "many"}})
    with pytest.raises(exercise_types.InvalidExercise):
        numeric.fields({})


def test_a_numerical_exercise_needs_a_passage_with_a_formula_or_numbers():
    numeric = exercise_types.TYPES["numerica"]

    assert numeric.suits("A sample of four points with an inlier fraction of 0.5 needs 72 iterations, 4 7 17.")
    assert numeric.suits("N = log(1 - p) / log(1 - w^s)")
    assert not numeric.suits("Small samples are more likely to be free of outliers than large samples are.")


# ── Writing one exercise ────────────────────────────────────────────────────

def test_an_exercise_is_stored_with_its_passage_located_and_the_page_of_its_chunk(course, fake_llm):
    stored = write(course)

    assert stored["exercise_id"].startswith("e_") and stored["status"] == "servido"
    assert stored["type"] == "abierta" and stored["level"] == "intermedio" and stored["language"] == "es"
    source = stored["source"]
    assert (source["chunk_id"], source["page"], source["doc_label"]) == ("c_0002", 2, "unit4.pdf")
    assert source["excerpt"].startswith("1.1 Why minimal samples")
    assert exercises.load(cid(course.course), stored["exercise_id"]) == stored
    assert len(fake_llm.calls) == 1 and stored["calls"] == 1


def test_the_page_named_by_the_model_is_never_used(course, fake_llm):
    fake_llm.queue(lambda m: exercise_reply(m, page=17, source="S2"))     # the excerpt is from S1, on page 2

    assert write(course)["source"]["page"] == 2


def test_the_prompt_holds_only_the_topic_and_marks_it_as_data(course, fake_llm):
    write(course, number=0, level="basico", language="en")

    system, user = fake_llm.calls[0]["messages"][0]["content"], user_text(fake_llm.calls[0]["messages"])
    assert "never an instruction to you" in system and "Write the exercise in English" in system
    assert "never translated" in system and "keeps the words and the language of the source" in system
    assert list(sources_in(fake_llm.calls[0]["messages"]).values())[0].startswith("Unit 4 handout")
    assert "Scoring a model" not in user                     # section 3 is not part of section 1
    assert "Type: abierta." in user and "Level: basic" in user


def test_the_prompt_says_what_the_student_should_practise_and_what_exists(course, fake_llm):
    write(course, target="How minimal samples avoid outliers", avoid=["An exercise that exists"])

    user = user_text(fake_llm.calls[0]["messages"])
    assert '"How minimal samples avoid outliers"' in user and "- An exercise that exists" in user


def test_a_passage_that_is_not_in_the_topic_discards_the_exercise_and_it_is_written_again(course, fake_llm):
    fake_llm.queue(lambda m: exercise_reply(m, excerpt="a sentence that appears nowhere in the handout at all"))

    stored = write(course)

    assert stored["calls"] == 2 and stored["discarded_before"] == 1
    [discard] = rejections(course)
    assert discard["reason"] == "passage_not_found"
    assert discard["claimed_excerpt"] == "a sentence that appears nowhere in the handout at all"     # what the model claimed


def test_a_passage_from_another_section_is_not_in_the_topic(course, fake_llm):
    other = "Each model is scored by the number of matches that agree with it within a tolerance"
    fake_llm.queue(*[lambda m: exercise_reply(m, excerpt=other)] * 3)

    with pytest.raises(exercises.ExerciseFailed) as failed:
        write(course, number=0)

    assert (failed.value.status, failed.value.code) == (502, "exercise_failed")
    assert [r["reason"] for r in rejections(course)] == ["passage_not_found"] * 3


def test_after_two_more_tries_the_student_gets_a_clear_refusal(course, fake_llm):
    fake_llm.queue("not json", json.dumps({"statement": "only this"}), "[1, 2]")

    with pytest.raises(exercises.ExerciseFailed):
        write(course)

    assert len(fake_llm.calls) == 1 + limits.MAX_EXERCISE_RETRIES == 3
    assert [r["reason"] for r in rejections(course)] == ["invalid_json", "invalid_exercise: not text", "invalid_json"]
    assert exercises.all_exercises(cid(course.course)) == []


def test_a_model_that_times_out_every_time_is_a_timeout(course, fake_llm):
    fake_llm.queue(*[asyncio.TimeoutError()] * 3)

    with pytest.raises(exercises.ExerciseFailed) as failed:
        write(course)

    assert (failed.value.status, failed.value.code) == (504, "practice_timeout")


def test_a_model_that_is_not_configured_stops_at_once(course, fake_llm):
    fake_llm.queue(ValueError("no key"))

    with pytest.raises(exercises.ExerciseFailed) as failed:
        write(course)

    assert (failed.value.status, failed.value.code, len(fake_llm.calls)) == (503, "model_unavailable", 1)


# ── The numerical check ─────────────────────────────────────────────────────

def test_a_numerical_exercise_is_worked_out_again_by_a_separate_call(course, fake_llm):
    stored = write(course, kind="numerica")

    assert stored["type"] == "numerica" and stored["answer"]["value"] == 72 and stored["answer"]["checked_value"] == 72
    assert [kind_of(c["messages"]) for c in fake_llm.calls] == ["exercise", "check"]
    check = user_text(fake_llm.calls[1]["messages"])
    assert "N = log(1 - p)" in check                   # the whole chunk the passage is in
    assert CHECK.search(check).group(2) == stored["statement"]
    assert "Reference solution" not in check and "reference_solution" not in check     # not told the first answer


def test_two_values_that_differ_discard_the_exercise_with_both_values_on_record(course, fake_llm):
    # The real case of 2026-10-12: a draft said 5 iterations where the handout's table says 17.
    fake_llm.queue(lambda m: exercise_reply(m, value=5), lambda m: check_reply(m, value=17))

    stored = write(course, kind="numerica")

    assert stored["answer"]["value"] == 72                       # the next one, which agreed
    entry = rejections(course)[0]
    assert entry["reason"] == "numeric_mismatch: 5 vs 17" and entry["answer"]["value"] == 5
    assert stored["calls"] == 4


def test_a_check_that_gives_no_value_discards_the_exercise(course, fake_llm):
    fake_llm.queue(exercise_reply, lambda m: json.dumps({"value": None}), exercise_reply, "nonsense")

    stored = write(course, kind="numerica")

    assert [r["reason"] for r in rejections(course)] == ["check_no_value", "check_invalid"]
    assert stored["calls"] == 6


def test_values_within_the_tolerance_agree(course, fake_llm):
    fake_llm.queue(lambda m: exercise_reply(m, value=72), lambda m: check_reply(m, value=72.5))

    assert write(course, kind="numerica")["answer"]["checked_value"] == 72.5


def test_passages_without_numbers_get_an_open_exercise_instead():
    plain = [{"text": "Small samples are more likely to be free of outliers than large samples are."}]
    numbers = [{"text": "A sample of four points with an inlier fraction of 0.5 needs 72 iterations; 4, 7 and 17."}]

    assert exercises.choose_kind(plain, "numerica") == "abierta"
    assert exercises.choose_kind(numbers, "numerica") == "numerica"
    assert exercises.choose_kind(numbers, "abierta") == "abierta"
    assert exercises.choose_kind(numbers, "made-up type") == "abierta"


# ── The record ──────────────────────────────────────────────────────────────

def test_every_run_is_logged_with_its_calls_and_time_and_no_student(course, fake_llm):
    fake_llm.queue(lambda m: exercise_reply(m, value=5), lambda m: check_reply(m, value=17))
    write(course, kind="numerica")

    [run] = exercises.run_log(cid(course.course))
    assert (run["kind"], run["calls"], run["outcome"], run["rejected"]) == ("exercise", 4, "accepted", ["numeric_mismatch: 5 vs 17"])
    assert run["seconds"] >= 0 and set(run) == {"at", "kind", "calls", "seconds", "outcome", "rejected"}


def test_what_a_student_sees_before_answering_holds_no_solution(course):
    stored = write(course, kind="numerica")

    view = exercises.learner_view(stored)

    assert set(view) == {"exercise_id", "type", "level", "statement", "page", "doc_label", "topic_id", "unit"}
    text = json.dumps(view)
    for private in ("Reference solution", "Key point", "Typical mistake", "72 iterations", "excerpt", "checked"):
        assert private not in text
