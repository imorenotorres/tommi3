#!/bin/bash
# Script para instalar python-dotenv en el entorno virtual del proyecto

VENV_PATH="/Users/ignaciomoreno-torres/Library/CloudStorage/OneDrive-UniversidaddeMálaga/agentes/tommi3/.venv"

echo "Instalando python-dotenv en el entorno virtual..."
"$VENV_PATH/bin/pip" install python-dotenv

if [ $? -eq 0 ]; then
    echo "python-dotenv instalado correctamente en el venv"
else
    echo "Error al instalar"
    exit 1
fi
