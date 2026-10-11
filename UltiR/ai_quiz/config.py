"""Settings of the AI Quiz tool, read from the environment (web/.env).

Read on every use rather than once at import, so a missing value never stops
the server from starting: the tool answers 503 until it is configured, and the
rest of the platform is unaffected.
"""

import logging
import os

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


def id_key() -> str:
    return _secret("AI_QUIZ_ID_KEY")


def dev_test_enabled() -> bool:
    """The local test launch exists only when the flag is exactly "1"."""
    return os.environ.get("AI_QUIZ_DEV_TEST", "") == "1"


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
    required = {"AI_QUIZ_LTI_SECRET": lti_secret(), "AI_QUIZ_ID_KEY": id_key()}
    return [name for name, value in required.items() if not value]


def require_configured() -> None:
    """Raise 503 unless every required setting has a value. Logs names, never values."""
    missing = missing_settings()
    if missing:
        log.error("AI Quiz is not configured: %s not set in web/.env", ", ".join(missing))
        raise HTTPException(503, "AI Quiz is not configured")
