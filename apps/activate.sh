#!/bin/bash
# Activates the tommi3 virtual environment
# Usage: source activate.sh

VENV_PATH="/Users/ignaciomoreno-torres/Library/CloudStorage/OneDrive-UniversidaddeMálaga/agentes/tommi3/.venv"

if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Virtual environment not found at: $VENV_PATH"
    exit 1
fi
