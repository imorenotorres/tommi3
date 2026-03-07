#!/usr/bin/env python3
"""
Helper para activar automáticamente el entorno virtual de tommi3.

Uso: Importar al inicio del script ANTES de cualquier otra importación que dependa del venv.

    from apps.venv_helper import ensure_venv
    ensure_venv()

    # Ahora ya puedes importar dependencias del venv
    import ollama
"""

import os
import sys
from pathlib import Path

# Ruta al venv de tommi3 (relativa a la raíz del proyecto)
TOMMI3_ROOT = Path(__file__).parent.parent
VENV_PATH = TOMMI3_ROOT / "venv"
VENV_PYTHON = VENV_PATH / "bin" / "python"


def is_venv_active() -> bool:
    """Verifica si el venv de tommi3 está activo."""
    # Método más fiable: verificar sys.prefix
    current_prefix = Path(sys.prefix).resolve()
    venv_path_resolved = VENV_PATH.resolve()

    return current_prefix == venv_path_resolved


def ensure_venv():
    """
    Asegura que el script se ejecute con el venv de tommi3.
    Si no está activo, re-ejecuta el script con el Python del venv.
    """
    if is_venv_active():
        return  # Ya estamos en el venv correcto

    if not VENV_PYTHON.exists():
        print(f"Error: No se encontró el venv en {VENV_PATH}")
        print(f"Ejecuta: python3 -m venv {VENV_PATH}")
        sys.exit(1)

    # Re-ejecutar el script con el Python del venv
    print(f"[venv] Activando entorno virtual: {VENV_PATH}")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)


def get_venv_python() -> str:
    """Retorna la ruta al Python del venv."""
    return str(VENV_PYTHON)


if __name__ == "__main__":
    # Test
    print(f"TOMMI3_ROOT: {TOMMI3_ROOT}")
    print(f"VENV_PATH: {VENV_PATH}")
    print(f"VENV_PYTHON: {VENV_PYTHON}")
    print(f"Current Python: {sys.executable}")
    print(f"Venv active: {is_venv_active()}")
