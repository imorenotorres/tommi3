"""Does a passage carry mathematical notation that text reading may have garbled?

Text reading flattens formulas: exponents, subscripts and fraction bars are lost,
so "F1 = 2 / (1/P + 1/R)" arrives as "F1 = 21 P + 1R". A passage like that must
not be shown to students as a quotation. The cases marked "real run" are taken
from the model run of 2026-10-10 on the synthetic handout.
"""

import pytest

from UltiR.ai_quiz.mathflag import has_math_notation

# Draft 9 of the real run: the located source passage of a question about the F1 score.
DRAFT_9_PASSAGE = "Both are combined in the harmonic mean F1 = 21 P + 1R = 2P RP + R"


def test_the_garbled_passage_from_the_real_run_is_flagged():
    assert has_math_notation(DRAFT_9_PASSAGE) is True


@pytest.mark.parametrize("passage", [
    "repeatability = |C|min(n1, n2) . (47) The matching score evaluates detector and descriptor together",   # real run
    ", j = 0, 1, . . . ,35. (17) The highest bin of the histogram defines the dominant orientation.",         # real run
    "are defined as P = T PT P+ F P, (43) R = T PT P+ F N. (44) Precision is the fraction",                   # real run
    "which contains three set bits, so dH(a, b) = 3.",
    "2: while c < N do",
    "if |I| > |I*| then keep the hypothesis",
    "The probability that a sample contains only inliers is w^s.",
    "and their squared Euclidean distance is 0 .22 + 0.22, which is small",                                    # real run
    "The probability is approximately ws, with Pgood = ∏ (nin − i)/(n − i) ≈ ws.",
    "so that ∥a − b∥2 = 2 − 2 a⊤b for unit vectors",
    "N ← ⌈log(1 − p)/ log(1 − ws)⌉",
    "the blur σ of the next level",
    "a threshold of −0.5 on the response",
    "la desviación típica es √n/2",
])
def test_passages_with_formulas_are_flagged(passage):
    assert has_math_notation(passage) is True


@pytest.mark.parametrize("passage", [
    "The ratio test compares two distances and accepts the match below a threshold.",
    "The detector was published in 2004 and uses 128 dimensions.",
    "At a threshold of 0.8 the test accepts 550 matches, of which 528 are correct and 22 are incorrect.",
    "See section 3.2 (page 14) and the steps (1) to (3) for details.",
    "The well-known trade-off between speed and accuracy is state-of-the-art, e.g. in real-time use.",
    "La prueba de la razón compara dos distancias: ¿cuál es menor?",
    "Results\n=======\nA heading underlined in a plain text file.",
    "> A line quoted in a Markdown file.\n>> And a nested one.",
    "| Descriptor | Dimension | Type |\n|---|---|---|\n| SIFT | 128 | real-valued |",
    "C++ and C# are programming languages, and A+ is a grade.",
    "Use the arrow keys -> and <- to move; press Ctrl+C to copy.",
    "Email the team at vision@example.invalid or visit https://example.invalid/a?b=1&c=2 for the slides.",
    "",
])
def test_ordinary_text_is_not_flagged(passage):
    assert has_math_notation(passage) is False
