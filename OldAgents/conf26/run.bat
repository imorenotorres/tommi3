@echo off
cd /d "%~dp0"

REM Crear entorno virtual si no existe
if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
)

REM Activar entorno
call .venv\Scripts\activate

REM Instalar dependencias
pip install -q -r requirements.txt

REM Ejecutar servidor
echo Iniciando servidor en http://localhost:8000
python app.py
