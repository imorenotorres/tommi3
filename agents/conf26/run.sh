#!/bin/bash
cd "$(dirname "$0")"

# Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi

# Activar entorno
source .venv/bin/activate

# Instalar dependencias
pip install -q -r requirements.txt

# Ejecutar servidor
echo "Iniciando servidor en http://localhost:8000"
python app.py
