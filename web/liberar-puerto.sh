#!/bin/bash

if [ -z "$1" ]; then
    echo "Uso: $0 <puerto>"
    echo "Ejemplo: $0 3000"
    exit 1
fi

PORT=$1

# Buscar el proceso que usa el puerto
PID=$(lsof -ti :$PORT)

if [ -z "$PID" ]; then
    echo "No hay ningún proceso usando el puerto $PORT"
    exit 0
fi

echo "Proceso(s) usando el puerto $PORT: $PID"
echo "Terminando proceso(s)..."

kill -9 $PID

if [ $? -eq 0 ]; then
    echo "Puerto $PORT liberado correctamente"
else
    echo "Error al liberar el puerto $PORT"
    exit 1
fi
