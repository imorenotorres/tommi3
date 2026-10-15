"""Programmed tutor: the number of RANSAC iterations (sample.pdf, pp. 15–16), and what every tutor shares.

The solver is checked against an independent way of getting N (the smallest k whose failure probability is at
most 1 − p), every catalogued mistake is recognised on the value it gives and on nothing else, no exercise is
ambiguous, and the student's number is read as people write it.
"""

import re

import pytest

from UltiR.ai_quiz import tutors
from UltiR.ai_quiz.tutors import ransac_iterations as ransac

NAME = "ransac_iterations"
SEEDS = range(300)


def independent_n(p: float, w: float, s: int) -> int:
    """The smallest number of samples k with (1 − wˢ)ᵏ ≤ 1 − p, counted, not computed with logarithms."""
    k, fail = 0, 1.0
    while fail > 1 - p + 1e-12:
        k += 1
        fail *= 1 - w ** s
    return k


def instances(level):
    return [tutors.make(NAME, level, seed) for seed in SEEDS]


# ── The answer ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", tutors.LEVELS)
def test_the_answer_is_the_smallest_number_of_samples_that_reaches_the_confidence(level):
    for instance in instances(level):
        p, w, s = (instance.params[k] for k in ("p", "w", "s"))
        assert instance.answer == independent_n(p, w, s), instance.params


def test_the_worked_example_of_the_handout():
    # p. 16: 200 matches, 100 correct, a homography, p = 0.99: 72 iterations; the eight-point algorithm 1177.
    homography = {"model": "homography", "s": 4, "n": 200, "n_in": 100, "w": 0.5, "p": 0.99, "counts": True}
    eight = {**homography, "model": "fundamental8", "s": 8}

    assert ransac.solve(homography) == 72 and ransac.solve(eight) == 1177


@pytest.mark.parametrize("level, given", [("basico", {"w", "s", "p"}), ("intermedio", {"n", "n_in", "p"}),
                                          ("avanzado", {"n", "n_in", "p"})])
def test_each_level_gives_what_its_spec_says(level, given):
    for instance in instances(level)[:30]:
        assert instance.params["counts"] is (level != "basico")
        if level == "avanzado":
            assert instance.params["p"] in (0.95, 0.999)
        else:
            assert instance.params["p"] == 0.99
        text = tutors.statement(instance, "en")
        for key in given:
            assert tutors.shown_value(instance.params[key], "en") in text


def test_the_basic_level_says_the_sample_size_and_the_others_only_name_the_model():
    basic, middle = tutors.make(NAME, "basico", 3), tutors.make(NAME, "intermedio", 3)

    assert f"s = {basic.params['s']}" in tutors.statement(basic, "es")
    assert "s = " not in tutors.statement(middle, "es")


# ── The mistakes ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", tutors.LEVELS)
def test_every_mistake_is_recognised_on_its_own_value_and_on_nothing_else(level):
    seen = set()
    for instance in instances(level):
        assert tutors.diagnose(instance.answer, instance.wrong, instance.form, instance.answer) == ("correcto", None)
        for mistake, value in instance.wrong.items():
            assert tutors.diagnose(instance.answer, instance.wrong, instance.form, value) == ("incorrecto", mistake)
            seen.add(mistake)
    expected = {"w_not_ws", "round_down", "outlier_fraction", "log_p"} | ({"sample_size"} if level != "basico" else set())
    assert seen == expected


def test_each_mistake_computes_what_its_name_says():
    params = {"model": "homography", "s": 4, "n": 200, "n_in": 120, "w": 0.6, "p": 0.99, "counts": True}
    wrong = ransac.mistakes(params)

    assert wrong["w_not_ws"] == independent_n(0.99, 0.6, 1)
    assert wrong["round_down"] == independent_n(0.99, 0.6, 4) - 1
    assert wrong["sample_size"] == independent_n(0.99, 0.6, 8)          # the 8 degrees of freedom of a homography
    assert wrong["outlier_fraction"] == independent_n(0.99, 0.4, 4)
    assert ransac.mistakes({**params, "model": "fundamental7", "s": 7})["sample_size"] == independent_n(0.99, 0.6, 8)
    assert ransac.mistakes({**params, "model": "fundamental8", "s": 8})["sample_size"] == independent_n(0.99, 0.6, 7)


def test_a_mistake_that_cannot_happen_is_not_in_the_catalogue_of_the_exercise():
    basic = {"model": "homography", "s": 4, "w": 0.5, "p": 0.99, "counts": False}

    wrong = ransac.mistakes(basic)

    assert wrong["sample_size"] is None                   # s is given at this level
    assert wrong["outlier_fraction"] is None              # with w = 0.5 the two fractions are the same


def test_a_quotient_that_is_a_whole_number_has_no_rounding_mistake():
    # w^s = 0.9 and 1 − p = 0.01 = 0.1²: exactly 2 samples, so rounding down changes nothing.
    exact = {"model": "line", "s": 1, "w": 0.9, "p": 0.99, "counts": False}

    assert ransac.solve(exact) == 2 and ransac.mistakes(exact)["round_down"] is None


def test_two_mistakes_with_one_value_give_no_diagnosis():
    assert tutors.diagnose(72.0, {"w_not_ws": 9.0, "log_p": 9.0}, "integer", 9.0) == ("incorrecto", None)


def test_the_worked_solution_starts_from_the_counts_where_they_are_given():
    instance = tutors.make(NAME, "intermedio", 7)

    assert tutors.solution(instance, "es").startswith("La fracción de inliers es w = n_in / n = 108 / 180 = 0,6.")
    assert not tutors.solution(tutors.make(NAME, "basico", 7), "es").startswith("La fracción")


def test_a_value_no_mistake_explains_gets_no_diagnosis():
    instance = tutors.make(NAME, "intermedio", 11)
    stray = next(v for v in range(1, 100000) if v != instance.answer and v not in instance.wrong.values())

    assert tutors.diagnose(instance.answer, instance.wrong, instance.form, float(stray)) == ("incorrecto", None)


@pytest.mark.parametrize("level", tutors.LEVELS)
def test_no_exercise_is_ambiguous(level):
    for instance in instances(level):
        values = [instance.answer, *instance.wrong.values()]
        assert len({round(v) for v in values}) == len(values), instance.params


def test_parameters_that_would_be_ambiguous_are_drawn_again(monkeypatch):
    draws = []
    real = ransac.mistakes

    def first_ambiguous(params):
        draws.append(params)
        wrong = real(params)
        if len(draws) == 1:
            wrong["log_p"] = ransac.solve(params)         # the first draw: a mistake that gives the right answer
        return wrong

    monkeypatch.setattr(ransac, "mistakes", first_ambiguous)

    instance = tutors.make(NAME, "basico", 5)

    assert len(draws) >= 2 and instance.wrong["log_p"] != instance.answer


def test_a_seed_gives_the_same_exercise_every_time():
    assert tutors.make(NAME, "avanzado", 42) == tutors.make(NAME, "avanzado", 42)
    assert tutors.make(NAME, "avanzado", 42) != tutors.make(NAME, "avanzado", 43)


# ── What the student typed ──────────────────────────────────────────────────

@pytest.mark.parametrize("typed, value", [("72", 72), (" 72 ", 72), ("1177", 1177), ("1 177", 1177), ("1.177", 1177),
                                          ("12.345.678", 12345678), (72, 72), ("72,0", 72)])
def test_a_whole_number_is_read_as_people_write_it(typed, value):
    assert tutors.parse(typed, "integer") == value


@pytest.mark.parametrize("typed", ["72,5", "0.125", "70 %", "setenta", "", "1.17", True, None, "1.1770"])
def test_what_is_not_a_whole_number_is_refused(typed):
    with pytest.raises(ValueError):
        tutors.parse(typed, "integer")


@pytest.mark.parametrize("level", tutors.LEVELS)
def test_every_answer_and_mistake_survives_being_written_and_read_back(level):
    for instance in instances(level)[:50]:
        for value in [instance.answer, *instance.wrong.values()]:
            for language in ("es", "en"):
                assert tutors.parse(tutors.shown_value(value, language), "integer") == value


# ── The spec ────────────────────────────────────────────────────────────────

def test_the_spec_and_the_module_name_the_same_mistakes():
    spec = tutors.spec(NAME)
    ids = [m["id"] for m in spec["mistakes"]]

    assert sorted(ids) == sorted(ransac.mistakes({"model": "homography", "s": 4, "w": 0.6, "p": 0.99, "counts": True,
                                                   "n": 100, "n_in": 60}))
    assert len(ids) == len(set(ids))


def test_every_text_of_the_spec_has_both_languages_and_every_placeholder_is_known():
    spec = tutors.spec(NAME)
    texts = [spec["right"], spec["unknown"], *spec["mistakes"], spec["solution"], *spec["levels"].values()]
    for instance in [tutors.make(NAME, level, seed) for level in tutors.LEVELS for seed in range(5)]:
        for block in texts:
            for key, text in block.items():
                if not re.search(r"_(es|en)$|^(es|en)$", key):
                    continue
                filled = tutors.fill(NAME, text, instance.params, key[-2:], value=instance.answer, page=15)
                assert "{" not in filled, (key, filled)
    for block in texts:
        keys = {k[:-3] if k[-3:] in ("_es", "_en") else k for k in block if re.search(r"_(es|en)$|^(es|en)$", k)}
        for key in keys:
            name_es, name_en = (f"{key}_es", f"{key}_en") if key not in ("es", "en") else ("es", "en")
            assert name_es in block and name_en in block, (block.get("id"), key)


def test_spanish_texts_write_a_decimal_comma():
    instance = tutors.make(NAME, "basico", 7)               # w = 0.6

    assert "w = 0,6" in tutors.statement(instance, "es") and "w = 0.6" in tutors.statement(instance, "en")
    assert "= 162,2" in tutors.solution(instance, "es")


# ── Pages from the handout ──────────────────────────────────────────────────

# The sentences the spec rests on, as text reading writes them (a hyphen for the minus sign the PDF has).
HANDOUT = [
    {"chunk_id": "c_0038", "page": 14, "text": "9 RANSAC and its iteration count Least-squares estimation fails"},
    {"chunk_id": "c_0040", "page": 15, "text": (
        "The sample size is the smallest number of matches that determines the model: four for a homography. "
        "How many samples are needed? Let nin of the n matches be inliers, so that the inlier fraction is w = nin/n. "
        "The probability that a sample of s different matches contains only inliers is Pgood. The probability that "
        "N independent samples all contain at least one outlier is (1 - ws)N. Requiring that this failure "
        "probability is at most 1 - p gives")},
    {"chunk_id": "c_0042", "page": 16, "text": "therefore N >= 71.4. Rounding up gives 72 iterations for the homography."},
]


def test_every_anchor_of_the_spec_is_found_and_gives_its_page():
    spec = tutors.spec(NAME)

    assert tutors.locate(spec["skill"]["anchor"], HANDOUT)["page"] == 15
    pages = {m["id"]: tutors.locate(m["anchor"], HANDOUT)["page"] for m in spec["mistakes"]}
    assert pages == {"w_not_ws": 15, "round_down": 16, "sample_size": 15, "outlier_fraction": 15, "log_p": 15}


def test_a_handout_without_the_sentence_gives_no_page():
    assert tutors.locate(tutors.spec(NAME)["skill"]["anchor"], HANDOUT[:1]) is None


def test_the_passage_shown_is_the_handouts_own_wording():
    found = tutors.locate("the inlier fraction is w = nin/n", HANDOUT)

    assert found["excerpt"] is not None and found["chunk_id"] == "c_0040"
