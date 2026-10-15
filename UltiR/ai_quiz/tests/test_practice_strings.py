"""Practice texts: every key the practice pages build from a value the server sends exists in both languages.

The page tests find the keys written out in the pages. These are put together at run time
('practice_level_' + level, ...), so they are listed here from the server's own values.
"""

import pytest

from UltiR.ai_quiz import exercise_types, exercises, feedback, practice, progress

from .test_pages import load_strings

DISCARD_REASONS = ("passage_not_found", "numeric_mismatch", "check_no_value", "check_invalid", "check_timeout",
                   "check_error", "invalid_json", "invalid_exercise", "timeout", "model_error")


def built_keys() -> set[str]:
    return ({f"practice_level_{level}" for level in practice.LEVELS}
            | {f"practice_type_{kind}" for kind in exercise_types.TYPES}
            | {f"practice_status_{status}" for status in (*feedback.STATUSES, feedback.UNSURE)}
            | {f"practice_verdict_{verdict}" for verdict in feedback.VERDICTS}
            | {f"admin_status_{status}" for status in exercises.STATUSES}
            | {f"report_{reason}" for reason in exercises.REPORT_REASONS}
            | {f"reject_{reason}" for reason in DISCARD_REASONS}
            | {"practice_aim_key_point", "practice_aim_mistake", "practice_suggest_subir", "practice_suggest_bajar"})


@pytest.mark.parametrize("language", ["en", "es"])
def test_every_key_built_from_a_value_of_the_server_has_a_text(client, language):
    strings = load_strings(client)[language]

    assert sorted(k for k in built_keys() if k not in strings) == []


@pytest.mark.parametrize("language, words", [
    ("en", {"info_ai_text": ("Practice is the exception", "without review", "labelled as written by AI", "report", "retire"),
            "info_know_privacy": ("answer is sent to the language model", "without the name or any id", "not stored")}),
    ("es", {"info_ai_text": ("La práctica es la excepción", "sin revisión", "marca", "reportar", "retirar"),
            "info_know_privacy": ("se envía al modelo de lenguaje el texto de la respuesta",
                                  "sin el nombre ni ningún identificador", "no se guarda")}),
])
def test_the_info_page_says_how_practice_differs_and_what_is_sent_to_the_model(client, language, words):
    strings = load_strings(client)[language]

    for key, phrases in words.items():
        assert all(phrase in strings[key] for phrase in phrases), key


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
    found |= set(re.findall(r'return "([a-z_]+)"', inspect.getsource(exercise_types)))
    found |= set(re.findall(r'why = "([a-z_]+)"', inspect.getsource(exercises)))
    found |= {"numeric_mismatch", "invalid_exercise"}             # written with details after a colon

    assert found and found <= set(DISCARD_REASONS)
