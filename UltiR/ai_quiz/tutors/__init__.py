"""Programmed tutors: practice whose answers, diagnoses and feedback come from a program, not from a model.

A tutor is a Python module and a TOML spec beside it, both in this folder. The spec is what an instructor
reviews: the skill, a sentence of the handout it rests on, the formula, the levels with their statements, the
worked solution, and the catalogue of typical mistakes with the feedback for each, in Spanish and English. The
module holds what a program has to compute:

    draw(level, rng, aim)  the parameters of one exercise (aim: a mistake the student made before, or None)
    solve(params)          the exact answer
    mistakes(params)       per catalogued mistake, the wrong answer it gives (None where it does not apply)
    values(params)         the numbers the statement and the solution are written with

This package does the rest, the same for every tutor:

- it draws parameters again until the answer and every mistake's value are told apart at the precision the
  statement asks for, so that a diagnosis is never ambiguous (`make`);
- it reads what the student typed: a decimal comma, "70 %", "1.177" for 1177 where a whole number is asked
  (`parse`);
- it diagnoses: right, one catalogued mistake, or wrong in a way it does not know, which is said as such and
  never guessed (`diagnose`);
- it finds the pages: every page shown comes from locating a sentence of the spec in the course's own copy of
  the handout (`locate`); a tutor whose handout is not in the course is not offered.

No model is asked at any point, and the student's answer never leaves the server.
"""

import importlib
import math
import random
import re
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from UltiR.ai_quiz import exercise_types

_HERE = Path(__file__).parent
NAMES = ("ransac_iterations",)
LEVELS = ("basico", "intermedio", "avanzado")
MAX_DRAWS = 500                 # parameter draws before a tutor gives up on telling every mistake apart
FORMS = ("integer", "fraction3")


class TutorError(Exception):
    pass


# ── Specs and modules ─────────────────────────────────────────────────────────

def spec(name: str) -> dict:
    if name not in NAMES:
        raise TutorError(f"no tutor {name!r}")
    with open(_HERE / f"{name}.toml", "rb") as handle:
        return tomllib.load(handle)


def module(name: str):
    if name not in NAMES:
        raise TutorError(f"no tutor {name!r}")
    return importlib.import_module(f"UltiR.ai_quiz.tutors.{name}")


# ── One exercise ──────────────────────────────────────────────────────────────

@dataclass
class Instance:
    tutor: str
    level: str
    seed: int
    params: dict
    answer: float
    form: str                   # "integer" (a whole number) or "fraction3" (a decimal, three places)
    wrong: dict                 # mistake id -> the value it gives, for the mistakes that apply


def tolerance(form: str) -> float:
    """How far from the exact answer a value may be and still be right: half the last place the statement asks."""
    return 0.0 if form == "integer" else 0.0005 + 1e-9


def _same(a: float, b: float, form: str) -> bool:
    if form == "integer":
        return round(a) == round(b)
    return abs(a - b) <= 2 * tolerance(form)       # two values this close could not be told apart


def distinct(answer: float, wrong: dict, form: str) -> bool:
    """Whether the answer and every mistake's value are told apart from one another at the stated precision."""
    values = [answer, *wrong.values()]
    if any(not math.isfinite(v) for v in values):
        return False
    return all(not _same(a, b, form) for i, a in enumerate(values) for b in values[i + 1:])


def make(name: str, level: str, seed: int, aim: str | None = None) -> Instance:
    """One exercise of a tutor at a level, from a seed. Parameters are drawn again until no diagnosis is ambiguous."""
    if level not in LEVELS:
        raise TutorError(f"no level {level!r}")
    tutor, rng = module(name), random.Random(seed)
    for _draw in range(MAX_DRAWS):
        params = tutor.draw(level, rng, aim)
        answer, form = tutor.solve(params), tutor.form(params)
        wrong = {mid: value for mid, value in tutor.mistakes(params).items() if value is not None}
        if distinct(answer, wrong, form):
            return Instance(name, level, seed, params, answer, form, wrong)
    raise TutorError(f"{name}: no unambiguous parameters in {MAX_DRAWS} draws")


# ── What the student typed ────────────────────────────────────────────────────

def parse(raw, form: str) -> float:
    """The student's value, or ValueError when it is not a number of the kind asked for.

    "0,75", "0.75" and "75 %" are 0.75 where a decimal between 0 and 1 is asked; "75" stays 75 (that is a
    mistake the catalogue knows: a percentage given where a fraction was asked). Where a whole number is asked,
    "1177", "1 177" and "1.177" are 1177, and "72,5" is not a whole number.
    """
    if not isinstance(raw, (str, int, float)) or isinstance(raw, bool):
        raise ValueError("not a value")
    text = str(raw).strip()
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    if form == "integer":
        if percent:
            raise ValueError("a percentage where a whole number is asked")
        compact = text.replace(" ", "").replace(" ", "").replace(" ", "")
        groups = compact.split(".")
        if len(groups) > 1 and re.fullmatch(r"[1-9]\d{0,2}", groups[0]) and all(re.fullmatch(r"\d{3}", g) for g in groups[1:]):
            compact = "".join(groups)                       # "1.177": a thousands point, as written in Spanish
        value = exercise_types.parse_number(compact)
        if value is None or value != int(value):
            raise ValueError("not a whole number")
        return float(value)
    value = exercise_types.parse_number(text)
    if value is None:
        raise ValueError("not a number")
    return value / 100 if percent else value


# ── Diagnosis ─────────────────────────────────────────────────────────────────

def diagnose(instance_answer: float, wrong: dict, form: str, value: float) -> tuple[str, str | None]:
    """("correcto", None), ("incorrecto", mistake id) or ("incorrecto", None) for a mistake the catalogue does not know."""
    if form == "integer":
        if round(value) == round(instance_answer) and value == int(value):
            return "correcto", None
        matches = [mid for mid, v in wrong.items() if round(v) == round(value)]
    else:
        if abs(value - instance_answer) <= tolerance(form):
            return "correcto", None
        matches = [mid for mid, v in wrong.items() if abs(v - value) <= tolerance(form)]
    return "incorrecto", matches[0] if len(matches) == 1 else None


# ── Pages from the handout ────────────────────────────────────────────────────

def _letters(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def locate(anchor: str, chunks: list[dict]) -> dict | None:
    """The chunk of the course's handout a sentence of a spec is in, with its page and the handout's own wording.

    Compared on letters and digits only, as the passage check does. None when the sentence is not in any chunk:
    then the handout is not the one the tutor was written for.
    """
    from UltiR.ai_quiz import generation

    for chunk in chunks:
        if _letters(anchor) in _letters(chunk["text"]):
            found = generation.locate_excerpt(anchor, chunk["text"])
            return {"doc_id": chunk.get("doc_id"), "doc_label": chunk.get("doc_label"), "chunk_id": chunk["chunk_id"],
                    "page": chunk.get("page"), "excerpt": found or anchor}
    return None


# ── The texts of a spec ───────────────────────────────────────────────────────

def shown_value(value, language: str) -> str:
    """A value in a text: whole numbers as they are, others to four significant digits, with the page's decimal mark."""
    if value is None:
        return "–"
    if isinstance(value, str):
        return value
    value = float(value)
    if value == int(value) and abs(value) < 1e12:
        return str(int(value))
    return number(float(f"{value:.4g}"), language)


def fill(name: str, text: str, params: dict, language: str, **extra) -> str:
    """A text of the spec with its placeholders filled from the exercise. An unknown placeholder is an error."""
    values = {key: shown_value(value, language) for key, value in module(name).values(params).items()}
    # [labels.<placeholder>]: the words for a parameter, e.g. {model} for params["model"] = "homography"
    for placeholder, table in spec(name).get("labels", {}).items():
        if params.get(table["param"]) in table:
            values[placeholder] = table[params[table["param"]]][language]
    values.update({key: shown_value(value, language) for key, value in extra.items()})
    return text.format_map(values)


def statement(instance: Instance, language: str) -> str:
    return fill(instance.tutor, spec(instance.tutor)["levels"][instance.level][f"statement_{language}"],
                instance.params, language)


def solution(instance: Instance, language: str) -> str:
    worked = spec(instance.tutor)["solution"]
    prefix = worked.get(f"counts_{language}", "") if instance.params.get("counts") else ""
    return fill(instance.tutor, prefix + worked[language], instance.params, language)


def mistake_spec(name: str, mistake_id: str) -> dict:
    return next(m for m in spec(name)["mistakes"] if m["id"] == mistake_id)


# ── Writing numbers ───────────────────────────────────────────────────────────

def number(value: float, language: str, places: int | None = None) -> str:
    """A number as the page writes it: a decimal comma in Spanish, no trailing zeros unless places are fixed."""
    if places is None:
        text = exercise_types.shown(value) if value == int(value) else f"{value:.6g}"
    else:
        text = f"{value:.{places}f}"
    return text.replace(".", ",") if language == "es" else text
