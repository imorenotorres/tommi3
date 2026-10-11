"""Signs that a passage of extracted text carries mathematical notation.

Text reading flattens formulas: exponents, subscripts and fraction bars are
lost, so 0.2² + 0.2² arrives as "0.22 + 0.22" and F1 = 2/(1/P + 1/R) as
"F1 = 21 P + 1R". Such a passage is still "in the document" for the excerpt
rule, but it must not be quoted to students, and the instructor should check
any question written from it.

This is a heuristic with known limits:
- it cannot see a flattened exponent or subscript on its own ("ws" for w^s,
  "t2" for t², "nin" for n_in): there is nothing left to recognise;
- it flags any typeset minus sign, which also appears in the tick labels of
  plots, so text extracted from a figure can be flagged without a formula;
- a formula typed without spaces around its signs ("x=5", "a+b") is not seen.
It errs towards flagging: the cost of a wrong flag is that a student sees a
page number instead of a quotation.
"""

import re

# Characters that ordinary prose in English or Spanish does not use. The last one is the
# typeset minus sign (U+2212), which is what a PDF's mathematics uses instead of a hyphen.
_SYMBOLS = frozenset("∑∏∫√∞≈≠≤≥±×÷∈∉⊂⊆∪∩∥⊤⊥←→↔⇒⇔∂∇⌈⌉⌊⌋∅∗′−")

_PATTERNS = re.compile(
    r"\S\s(?<!=)=(?!=)\s?\S|\S\s?(?<!=)=(?!=)\s\S"    # an equals sign set off by a space: "F1 = 21", "j = 0"; not "=====", not "?b=1"
    r"|[\w|)\]] [<>] [\w|(]"                          # a comparison: "c < N", "|I| > |I*|"; not "<b>", not "> quoted"
    r"|\w \+ \w"                                      # a sum: "P + 1R"; not "C++", "A+", "Ctrl+C"
    r"|\w\^[\w{(]"                                    # a caret exponent: "w^s"; not a "[^1]" footnote mark
)


def has_math_notation(text: str) -> bool:
    if not text:
        return False
    # 0x0391 to 0x03C9 are the Greek capital and small letters, alpha to omega
    if any(c in _SYMBOLS or 0x0391 <= ord(c) <= 0x03C9 for c in text):
        return True
    return _PATTERNS.search(text) is not None
