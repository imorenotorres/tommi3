@echo off
REM Sonic Pi Bridge — double-click to start (Windows)
cd /d "%~dp0"

echo.
echo   ===============================
echo    Sonic Pi Bridge
echo   ===============================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found. Install it from python.org
    echo.
    pause
    exit /b 1
)

REM Create venv if needed
if not exist ".venv" (
    echo   Creating virtual environment (first time only^)...
    python -m venv .venv
)

REM Install python-sonic if needed
.venv\Scripts\python -c "import psonic" 2>nul
if errorlevel 1 (
    echo   Installing python-sonic...
    .venv\Scripts\pip install python-sonic --quiet
)

echo   Starting bridge...
echo.
.venv\Scripts\python sonic_bridge.py
pause
