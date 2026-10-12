"""Settings of the AI Quiz tool, read from the environment (web/.env).

Read on every use rather than once at import, so a missing value never stops
the server from starting: the tool answers 503 until it is configured, and the
rest of the platform is unaffected.
"""

import logging
import os
import re

from fastapi import HTTPException

log = logging.getLogger("ultir.ai_quiz")

DEFAULT_LTI_KEY = "ai_quiz_uma"

# The other UltiR tools fall back to this value when their secret is unset.
# This tool has no fallback, and does not accept the value if it is configured.
_PLACEHOLDER = "change_this_secret_in_env"


def _secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    return "" if value == _PLACEHOLDER else value


def lti_key() -> str:
    return os.environ.get("AI_QUIZ_LTI_KEY", "").strip() or DEFAULT_LTI_KEY


def lti_secret() -> str:
    return _secret("AI_QUIZ_LTI_SECRET")


# ── One consumer key and secret per Moodle installation ──────────────────────
# Moodle numbers its courses and users 1, 2, 3 ..., so "course 2" means something only inside one
# Moodle. The consumer key says which Moodle a launch comes from, and it is part of the id under
# which a course is kept. AI_QUIZ_LTI_KEY / AI_QUIZ_LTI_SECRET register the first installation;
# AI_QUIZ_LTI_KEY_2 / AI_QUIZ_LTI_SECRET_2 (then _3 ...) register one more each.

COURSE_SEPARATOR = ":"                                 # between consumer key and Moodle's course id
_KEY_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")          # so a key can never contain the separator
_NUMBERED = re.compile(r"AI_QUIZ_LTI_(?:KEY|SECRET)_(\d+)")


def _registrations() -> tuple[dict[str, str], list[str]]:
    """Every registered consumer key with its secret, and the names of the settings that are missing or wrong.

    Wrong means: a key without a secret or a secret without a key, a blank or placeholder secret, a key
    with other characters than letters, digits, "_", "." and "-", a key that is registered twice, or a
    secret that two registrations share. Two Moodles with one secret are not two registrations.
    """
    numbers = sorted({int(m.group(1)) for name in os.environ if (m := _NUMBERED.fullmatch(name))})
    pairs = [("AI_QUIZ_LTI_KEY", "AI_QUIZ_LTI_SECRET", lti_key(), lti_secret())]
    pairs += [(f"AI_QUIZ_LTI_KEY_{n}", f"AI_QUIZ_LTI_SECRET_{n}",
               os.environ.get(f"AI_QUIZ_LTI_KEY_{n}", "").strip(), _secret(f"AI_QUIZ_LTI_SECRET_{n}")) for n in numbers]
    consumers, faulty = {}, []
    for key_name, secret_name, key, secret in pairs:
        key_ok = bool(_KEY_RE.fullmatch(key)) and key not in consumers
        secret_ok = bool(secret) and secret not in consumers.values()
        if key_ok and secret_ok:
            consumers[key] = secret
        faulty += ([] if key_ok else [key_name]) + ([] if secret_ok else [secret_name])
    return consumers, faulty


def consumers() -> dict[str, str]:
    """Consumer key -> secret for every registered Moodle. Empty when any registration is faulty."""
    registered, faulty = _registrations()
    return {} if faulty else registered


def course_id(consumer_key: str, context_id: str) -> str:
    """The id under which this tool keeps a course: which Moodle it is in, then that Moodle's own course id."""
    return f"{consumer_key}{COURSE_SEPARATOR}{context_id}"


def id_key() -> str:
    return _secret("AI_QUIZ_ID_KEY")


def dev_test_enabled() -> bool:
    """The local test launch exists only when the flag is exactly "1"."""
    return os.environ.get("AI_QUIZ_DEV_TEST", "") == "1"


DEFAULT_MIN_GROUP = 3


def min_group() -> int:
    """How many students must have answered a question before the instructor is shown totals for it.

    AI_QUIZ_MIN_GROUP, a whole number of at least 1; anything else counts as the default, 3.
    With fewer answers a total says what one student did. (1 switches the rule off.)
    """
    value = os.environ.get("AI_QUIZ_MIN_GROUP", "").strip()
    return int(value) if re.fullmatch(r"[1-9][0-9]{0,3}", value) else DEFAULT_MIN_GROUP


def docling_python() -> str:
    """The interpreter of a Python environment that has Docling. Unset means: no full reading."""
    return os.environ.get("AI_QUIZ_DOCLING_PYTHON", "").strip()


def docling_models() -> str:
    """The folder that holds Docling's models. They must be there already; nothing is fetched."""
    return os.environ.get("AI_QUIZ_DOCLING_MODELS", "").strip() or os.path.expanduser("~/.cache/docling/models")


def docling_device() -> str:
    value = os.environ.get("AI_QUIZ_DOCLING_DEVICE", "").strip().lower()
    return value if value in ("auto", "cpu", "cuda") else "auto"


def missing_settings() -> list[str]:
    """The names of the settings that are missing or not valid."""
    return _registrations()[1] + ([] if id_key() else ["AI_QUIZ_ID_KEY"])


def require_configured() -> None:
    """Raise 503 unless every required setting has a valid value. Logs names, never values."""
    missing = missing_settings()
    if missing:
        log.error("AI Quiz is not configured: %s missing or not valid in web/.env", ", ".join(missing))
        raise HTTPException(503, "AI Quiz is not configured")
