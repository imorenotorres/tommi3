"""Practice texts: every key the practice pages build from a value the server sends exists in both languages.

The page tests find the keys written out in the pages. These are put together at run time
('practice_level_' + level, ...), so they are listed here from the server's own values.
"""

import pytest

from UltiR.ai_quiz import exercise_types, exercises, feedback, practice, progress

from .test_pages import load_strings

DISCARD_REASONS = ("passage_not_found", "numeric_mismatch", "check_no_value", "check_invalid", "check_timeout",
                   "check_error", "invalid_json", "invalid_exercise", "timeout", "model_error", "no_assignment_key_point",
                   "claim_unsupported", "mistake_contradicts", "claim_check_invalid", "claim_check_timeout", "claim_check_error")


def built_keys() -> set[str]:
    return ({f"practice_level_{level}" for level in practice.LEVELS}
            | {f"practice_type_{kind}" for kind in (*exercise_types.TYPES, "programado")}
            | {f"practice_status_{status}" for status in (*feedback.STATUSES, feedback.UNSURE)}
            | {f"practice_verdict_{verdict}" for verdict in feedback.VERDICTS}
            | {f"admin_status_{status}" for status in exercises.STATUSES}
            | {f"report_{reason}" for reason in exercises.REPORT_REASONS}
            | {f"reject_{reason}" for reason in DISCARD_REASONS}
            | {"err_bad_value_decimal", "err_bad_value_integer"}
            | {"practice_aim_key_point", "practice_aim_mistake", "practice_aim_mistake_last", "practice_suggest_subir",
               "practice_suggest_bajar"})


@pytest.mark.parametrize("language", ["en", "es"])
def test_every_key_built_from_a_value_of_the_server_has_a_text(client, language):
    strings = load_strings(client)[language]

    assert sorted(k for k in built_keys() if k not in strings) == []


@pytest.mark.parametrize("language, words", [
    ("en", {"info_ai_text": ("programmed tutors", "written once", "instructor reviews", "no model is called",
                             "off by default", "labelled as written by AI", "without review", "report", "retire"),
            "info_how_5": ("programmed tutor", "No language model takes part"),
            "practice_entry_text": ("whether a program or an AI made it",),
            "info_know_privacy": ("does not leave the server", "off by default", "answer sent to the language model",
                                  "without the name or any id", "not stored")}),
    ("es", {"info_ai_text": ("tutores programados", "una sola vez", "revisa el docente", "no se llama a ningún modelo",
                             "desactivada por defecto", "marca", "sin revisión", "reportarlos", "retirar"),
            "info_how_5": ("tutor programado", "Ningún modelo de lenguaje interviene"),
            "practice_entry_text": ("si lo ha generado un programa o una IA",),
            "info_know_privacy": ("no sale del servidor", "desactivada por defecto",
                                  "se envía al modelo de lenguaje el texto de la respuesta",
                                  "sin el nombre ni ningún identificador", "no se guarda")}),
])
def test_the_info_page_says_practice_uses_no_model_and_what_the_off_option_would_send(client, language, words):
    """Practice comes from programmed tutors by default (no model while students answer); the model-written option
    is off by default, and the page still says what it sends and what it is exempt from where it is switched on."""
    strings = load_strings(client)[language]

    for key, phrases in words.items():
        assert [phrase for phrase in phrases if phrase not in strings[key]] == [], key


def test_the_info_page_has_the_practice_texts():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "static" / "info.html").read_text(encoding="utf-8")

    assert 'data-i18n="info_how_5"' in html and 'data-i18n="info_students_practice"' in html


def test_the_levels_are_the_same_in_practice_and_in_the_record():
    assert practice.LEVELS == progress.LEVELS


def test_every_reason_a_discard_can_have_is_listed_above():
    import inspect
    import re

    found = set(re.findall(r'_reject\([^)]*?"([a-z_]+)', inspect.getsource(exercises)))
    found |= set(re.findall(r'return "([a-z_]+)"', inspect.getsource(exercise_types.Numeric.check)))
    found |= set(re.findall(r'why = "([a-z_]+)"', inspect.getsource(exercises)))
    found |= set(re.findall(r'return "([a-z_]+)"', inspect.getsource(exercises.check_claims)))
    found |= {"numeric_mismatch", "invalid_exercise"}             # written with details after a colon

    assert found and found <= set(DISCARD_REASONS)
