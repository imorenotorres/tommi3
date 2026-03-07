#!/usr/bin/env python3
"""
Helper to automatically activate the tommi3 virtual environment.

Usage: Import at the beginning of the script BEFORE any other import that depends on the venv.

    from apps.venv_helper import ensure_venv
    ensure_venv()

    # Now you can import venv dependencies
    import ollama
"""

import os
import sys
from pathlib import Path

# Path to tommi3 venv (relative to project root)
TOMMI3_ROOT = Path(__file__).parent.parent
VENV_PATH = TOMMI3_ROOT / ".venv"
VENV_PYTHON = VENV_PATH / "bin" / "python"


def is_venv_active() -> bool:
    """Check if the tommi3 venv is active."""
    # Most reliable method: check sys.prefix
    current_prefix = Path(sys.prefix).resolve()
    venv_path_resolved = VENV_PATH.resolve()

    return current_prefix == venv_path_resolved


def ensure_venv():
    """
    Ensure the script runs with the tommi3 venv.
    If not active, re-executes the script with the venv Python.
    """
    if is_venv_active():
        return  # Already in the correct venv

    if not VENV_PYTHON.exists():
        print(f"Error: venv not found at {VENV_PATH}")
        print("Run: python3 -m venv .venv")
        sys.exit(1)

    # Re-execute the script with the venv Python
    print(f"[venv] Activating virtual environment: {VENV_PATH}")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)


def get_venv_python() -> str:
    """Returns the path to the venv Python."""
    return str(VENV_PYTHON)


if __name__ == "__main__":
    # Test
    print(f"TOMMI3_ROOT: {TOMMI3_ROOT}")
    print(f"VENV_PATH: {VENV_PATH}")
    print(f"VENV_PYTHON: {VENV_PYTHON}")
    print(f"Current Python: {sys.executable}")
    print(f"Venv active: {is_venv_active()}")
