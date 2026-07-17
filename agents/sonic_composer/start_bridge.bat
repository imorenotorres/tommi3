@echo off
REM Sonic Pi Bridge — double-click to start (Windows)
cd /d "%~dp0"

echo.
echo   Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found. Install it from python.org
    echo.
    pause
    exit /b 1
)

echo   Checking python-sonic...
python -c "import psonic" 2>nul || python -m pip install python-sonic --quiet

echo   Starting bridge...
echo.
python sonic_bridge.py
pause
