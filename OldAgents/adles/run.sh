#!/bin/bash
cd "$(dirname "$0")"

# Puerto configurable (por defecto 8000)
PORT=${PORT:-8000}

# RAG agents requieren Python <= 3.13 (ChromaDB incompatible con 3.14+)
# Buscar Python compatible
PYTHON_CMD=""
for cmd in python3.12 python3.13 python3.11; do
    if command -v $cmd &> /dev/null; then
        PYTHON_CMD=$cmd
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Se requiere Python 3.11, 3.12 o 3.13 para agentes RAG"
    echo "       ChromaDB no es compatible con Python 3.14+"
    echo "       Instala Python 3.12: brew install python@3.12"
    exit 1
fi

echo "Usando $PYTHON_CMD"

# Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual con $PYTHON_CMD..."
    $PYTHON_CMD -m venv .venv
fi

# Activar entorno
source .venv/bin/activate

# Instalar dependencias
pip install -q -r requirements.txt

# Ejecutar servidor
echo "Iniciando servidor en http://localhost:$PORT"
PORT=$PORT python app.py
