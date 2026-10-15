"""Programmed tutor: precision, recall and F1 from matching counts (sample.pdf, p. 17).

The solver is checked against an independent count over a list of matches, every catalogued mistake (swapped
precision and recall above all) is recognised on its own value and on nothing else, and a decimal is read as
people write it: "0,750", "75 %".
"""

import re
from fractions import Fraction

import pytest

from UltiR.ai_quiz import tutors
from UltiR.ai_quiz.tutors import precision_recall as pr

NAME = "precision_recall"
SEEDS = range(300)


def independent(params: dict) -> dict:
    """The three measures counted over an explicit list of returned matches and true correspondences, in fractions."""
    returned = ["right"] * params["tp"] + ["wrong"] * params["fp"]
    true = ["found"] * params["tp"] + ["missed"] * params["fn"]
    precision = Fraction(returned.count("right"), len(returned))
    recall = Fraction(true.count("found"), len(true))
    return {"P": precision, "R": recall, "F1": 2 * precision * recall / (precision + recall)}


def instances(level):
    return [tutors.make(NAME, level, seed) for seed in SEEDS]


# ── The answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", tutors.LEVELS)
def test_the_answer_is_the_measure_counted_over_the_matches(level):
    for instance in instances(level):
        exact = independent(instance.params)[instance.params["asks"]]
        assert abs(instance.answer - float(exact)) < 1e-12, instance.params


def test_the_worked_example_of_the_handout():
    # p. 17: 200 matches returned, 150 correct, 250 true correspondences: P 0.75, R 0.60, F1 0.667.
    params = {"tp": 150, "fp": 50, "fn": 100, "counts": True, "returned": 200, "correct": 150, "true": 250}

    assert [round(pr.solve({**params, "asks": a}), 3) for a in ("P", "R", "F1")] == [0.75, 0.6, 0.667]


@pytest.mark.parametrize("level, asks", [("basico", {"P", "R"}), ("intermedio", {"P", "R"}), ("avanzado", {"F1"})])
def test_each_level_asks_what_its_spec_says(level, asks):
    got = {instance.params["asks"] for instance in instances(level)}

    assert got == asks


def test_the_counts_of_the_middle_levels_are_those_of_the_handouts_example():
    instance = tutors.make(NAME, "intermedio", 3)
    params = instance.params

    assert (params["returned"], params["correct"], params["true"]) == (params["tp"] + params["fp"], params["tp"],
                                                                       params["tp"] + params["fn"])
    text = tutors.statement(instance, "es")
    assert f"devuelve {params['returned']} correspondencias, de las que {params['correct']} son correctas" in text


# ── The mistakes ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", tutors.LEVELS)
def test_every_mistake_is_recognised_on_its_own_value_and_on_nothing_else(level):
    seen = set()
    for instance in instances(level):
        assert tutors.diagnose(instance.answer, instance.wrong, instance.form, scales=instance.scales, value= round(instance.answer, 3)) == ("correcto", None)
        for mistake, value in instance.wrong.items():
            typed = round(value, 3)                              # as a student writes it: three places
            assert tutors.diagnose(instance.answer, instance.wrong, instance.form, scales=instance.scales, value= typed) == ("incorrecto", mistake)
            seen.add(mistake)
    if level == "avanzado":
        assert seen == {"arithmetic_mean", "no_two", "percent"}
    else:
        assert seen == {"swapped", "complement", "ratio", "percent"}


def test_swapped_precision_and_recall_is_the_other_measure():
    params = {"tp": 150, "fp": 50, "fn": 100, "asks": "P", "counts": False}

    assert pr.mistakes(params)["swapped"] == pytest.approx(0.6)
    assert pr.mistakes({**params, "asks": "R"})["swapped"] == pytest.approx(0.75)
    assert pr.mistakes({**params, "asks": "F1"})["swapped"] is None          # F1 is the same either way


def test_each_other_mistake_computes_what_its_name_says():
    params = {"tp": 150, "fp": 50, "fn": 100, "asks": "P", "counts": False}

    assert pr.mistakes(params)["complement"] == pytest.approx(0.25)
    assert pr.mistakes(params)["ratio"] == pytest.approx(3.0)
    assert pr.mistakes(params)["percent"] == pytest.approx(75.0)
    f1 = {**params, "asks": "F1"}
    assert pr.mistakes(f1)["arithmetic_mean"] == pytest.approx(0.675)
    assert pr.mistakes(f1)["no_two"] == pytest.approx(0.75 * 0.6 / 1.35)


def test_a_value_no_mistake_explains_gets_no_diagnosis():
    instance = tutors.make(NAME, "basico", 11)
    stray = 0.001 if instance.answer > 0.01 else 0.999

    assert tutors.diagnose(instance.answer, instance.wrong, instance.form, scales=instance.scales, value= stray) == ("incorrecto", None)


@pytest.mark.parametrize("level", tutors.LEVELS)
def test_no_exercise_is_ambiguous_at_three_places(level):
    for instance in instances(level):
        values = [round(v, 3) for v in [instance.answer, *instance.wrong.values()]]
        assert all(abs(a - b) > 0.001 for i, a in enumerate(values) for b in values[i + 1:]), instance.params


def test_a_percentage_mistake_is_told_apart_at_its_own_precision():
    # 50.03 would be read as the percentage 50.0 written to one decimal: the two cannot both be in an exercise.
    assert not tutors.distinct(0.5, {"percent": 50.0, "ratio": 50.03}, "fraction3", {"percent": 100})
    assert tutors.distinct(0.5, {"percent": 50.0, "ratio": 50.3}, "fraction3", {"percent": 100})


def test_three_decimal_places_are_the_precision_asked():
    assert tutors.diagnose(0.75, {}, "fraction3", 0.7504) == ("correcto", None)
    assert tutors.diagnose(0.75, {}, "fraction3", 0.754) == ("incorrecto", None)


def test_the_next_exercise_after_a_swap_asks_precision_or_recall():
    assert {tutors.make(NAME, "avanzado", seed, aim="swapped").params["asks"] for seed in range(40)} <= {"P", "R"}
    assert {tutors.make(NAME, "basico", seed, aim="no_two").params["asks"] for seed in range(10)} == {"F1"}


# ── What the student typed ──────────────────────────────────────────────────

@pytest.mark.parametrize("typed, value", [("0,750", 0.75), ("0.75", 0.75), (".75", 0.75), ("75 %", 0.75), ("75%", 0.75),
                                          ("75", 75.0), (0.75, 0.75)])
def test_a_decimal_is_read_as_people_write_it(typed, value):
    assert tutors.parse(typed, "fraction3") == pytest.approx(value)


@pytest.mark.parametrize("typed", ["tres cuartos", "", "0,7,5", None, [0.75]])
def test_what_is_not_a_number_is_refused(typed):
    with pytest.raises(ValueError):
        tutors.parse(typed, "fraction3")


def test_a_percentage_with_its_sign_is_right_and_without_it_is_the_catalogued_mistake():
    instance = tutors.make(NAME, "basico", 4)
    percent = tutors.shown_value(round(instance.answer * 100, 1), "es")

    assert tutors.diagnose(instance.answer, instance.wrong, instance.form, scales=instance.scales, value= tutors.parse(percent + " %", "fraction3"))[0] == "correcto"
    assert tutors.diagnose(instance.answer, instance.wrong, instance.form, scales=instance.scales, value= tutors.parse(percent, "fraction3")) == ("incorrecto", "percent")


@pytest.mark.parametrize("level", tutors.LEVELS)
def test_every_answer_survives_being_written_and_read_back(level):
    for instance in instances(level)[:50]:
        for language in ("es", "en"):
            typed = tutors.number(instance.answer, language, 3)
            assert tutors.diagnose(instance.answer, instance.wrong, instance.form, scales=instance.scales, value=
                                   tutors.parse(typed, "fraction3"))[0] == "correcto"


# ── The spec ────────────────────────────────────────────────────────────────

def test_the_spec_and_the_module_name_the_same_mistakes():
    ids = [m["id"] for m in tutors.spec(NAME)["mistakes"]]

    assert sorted(ids) == sorted(pr.mistakes({"tp": 10, "fp": 5, "fn": 5, "asks": "P", "counts": False}))


def test_every_text_has_both_languages_and_every_placeholder_is_known():
    spec = tutors.spec(NAME)
    blocks = [spec["right"], spec["unknown"], *spec["mistakes"], spec["solution"], *spec["levels"].values()]
    for instance in [tutors.make(NAME, level, seed) for level in tutors.LEVELS for seed in range(5)]:
        for block in blocks:
            for key, text in block.items():
                if re.search(r"_(es|en)$|^(es|en)$", key):
                    assert "{" not in tutors.fill(NAME, text, instance.params, key[-2:], value=0.5, page=17), key


def test_the_measure_asked_is_named_in_both_languages():
    instance = tutors.make(NAME, "avanzado", 1)

    assert "la medida F1" in tutors.statement(instance, "es") and "the F1 score" in tutors.statement(instance, "en")


HANDOUT = [{"chunk_id": "c_0044", "page": 17, "text": (
    "10 Evaluation with precision and recall. Let T Pbe the number of correct matches that are returned, F Pthe "
    "number of incorrect matches. Precision is the fraction of returned matches that are correct, and recall is the "
    "fraction of all true correspondences that are returned. Precision answers how trustworthy the output is, while "
    "recall answers how complete it is. The harmonic mean is dominated by the smaller of the two values, so a high "
    "score requires both. As an example, a matcher that returns 200 matches of which 150 are correct, for an image "
    "pair with 250 true correspondences, has a precision of 0.75 and a recall of 0.60.")}]


def test_every_anchor_is_found_in_the_text_reading_of_page_17():
    spec = tutors.spec(NAME)

    assert tutors.locate(spec["skill"]["anchor"], HANDOUT)["page"] == 17
    assert {m["id"]: tutors.locate(m["anchor"], HANDOUT)["page"] for m in spec["mistakes"]} == {
        "swapped": 17, "complement": 17, "ratio": 17, "arithmetic_mean": 17, "no_two": 17, "percent": 17}
