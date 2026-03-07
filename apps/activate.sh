#!/bin/bash
# Activa el entorno virtual de tommi3
# Uso: source activate.sh

VENV_PATH="/Users/ignaciomoreno-torres/Library/CloudStorage/OneDrive-UniversidaddeMálaga/agentes/tommi3/venv"

if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "✅ Entorno virtual activado: $VIRTUAL_ENV"
else
    echo "❌ No se encontró el entorno virtual en: $VENV_PATH"
    exit 1
fi
