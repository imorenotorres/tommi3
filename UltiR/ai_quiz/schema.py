"""The shape of a multiple-choice question, checked the same way wherever it comes from.

Model output and instructor edits both pass through `validate_question`, so
nothing malformed is stored by either route.
"""

import re

from UltiR.ai_quiz import limits

DIFFICULTIES = ("basic", "intermediate", "advanced")
OPTION_IDS = ("A", "B", "C", "D")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class InvalidQuestion(Exception):
    pass


def clean_text(value, max_chars: int, required: bool = True) -> str:
    """Untrusted text as one clean line, or InvalidQuestion.

    Line breaks and tabs become spaces, other control characters are removed.
    Text that is too long is refused, never cut: a silently shortened question
    would not be the question that was written.
    """
    if not isinstance(value, str):
        if required or value is not None:
            raise InvalidQuestion("not text")
        return ""
    flat = " ".join(value.split())
    cleaned = " ".join(_CONTROL.sub("", flat).split())
    if required and not cleaned:
        raise InvalidQuestion("empty")
    if len(cleaned) > max_chars:
        raise InvalidQuestion("too long")
    return cleaned


def same(text: str) -> str:
    """Comparison form for "is this the same text": case and spacing ignored, signs kept."""
    return " ".join(text.casefold().split())


def validate_question(raw, default_difficulty: str | None = "intermediate") -> dict:
    """The five content fields of a question, clean, or InvalidQuestion. Unknown fields are not copied.

    With `default_difficulty=None` an unknown difficulty is an error (instructor
    edits); otherwise it is replaced by the default (model output).
    """
    if not isinstance(raw, dict):
        raise InvalidQuestion("not an object")
    question = clean_text(raw.get("question"), limits.MAX_QUESTION_CHARS)

    options_in = raw.get("options")
    if not isinstance(options_in, list) or len(options_in) != 4 or not all(isinstance(o, dict) for o in options_in):
        raise InvalidQuestion("options")
    options = {}
    for option in options_in:
        if option.get("id") not in OPTION_IDS or option["id"] in options:
            raise InvalidQuestion("option ids")
        options[option["id"]] = clean_text(option.get("text"), limits.MAX_OPTION_CHARS)
    if len({same(t) for t in options.values()}) != 4:
        raise InvalidQuestion("options not distinct")

    correct = raw.get("correct_option_id")
    if correct not in OPTION_IDS:
        raise InvalidQuestion("correct option")

    difficulty = raw.get("difficulty")
    if difficulty not in DIFFICULTIES:
        if default_difficulty is None:
            raise InvalidQuestion("difficulty")
        difficulty = default_difficulty if default_difficulty in DIFFICULTIES else "intermediate"

    return {
        "question": question,
        "options": [{"id": i, "text": options[i]} for i in OPTION_IDS],
        "correct_option_id": correct,
        "explanation": clean_text(raw.get("explanation"), limits.MAX_EXPLANATION_CHARS, required=False),
        "difficulty": difficulty,
    }
