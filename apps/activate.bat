@echo off
REM Activates the tommi3 virtual environment
REM Usage: activate.bat

set "VENV_PATH=%~dp0..\.venv"

if exist "%VENV_PATH%\Scripts\activate.bat" (
    call "%VENV_PATH%\Scripts\activate.bat"
    echo Virtual environment activated: %VIRTUAL_ENV%
) else (
    echo Virtual environment not found at: %VENV_PATH%
    exit /b 1
)
