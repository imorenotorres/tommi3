#!/bin/bash
# Liberar un puerto que está siendo usado
# Uso: ./liberar-puerto.sh 8000

if [ -z "$1" ]; then
    echo "Uso: $0 <puerto>"
    echo "Ejemplo: $0 8000"
    exit 1
fi

PORT=$1
PIDS=$(lsof -ti :$PORT 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "Puerto $PORT está libre."
else
    echo "Procesos usando el puerto $PORT:"
    lsof -i :$PORT
    echo ""
    echo "Terminando procesos: $PIDS"
    kill -9 $PIDS
    echo "Puerto $PORT liberado."
fi
