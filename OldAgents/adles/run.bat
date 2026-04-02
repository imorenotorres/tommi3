@echo off
cd /d "%~dp0"

REM Puerto configurable (por defecto 8000)
if "%PORT%"=="" set PORT=8000

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
echo Iniciando servidor en http://localhost:%PORT%
set PORT=%PORT%
python app.py
