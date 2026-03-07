@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
:: TOMMI - Setup Script for Windows
:: =============================================================================

echo.
echo ==============================================
echo        TOMMI - Initial Setup
echo ==============================================
echo.

:: Get script directory and change to project root directory
cd /d "%~dp0.."

:: -----------------------------------------------------------------------------
:: 1. Detect compatible Python version
:: -----------------------------------------------------------------------------
echo [1/7] Detecting compatible Python version...

:: Detect if there are RAG agents (require Python 3.11-3.13)
set "HAS_RAG_AGENTS=false"
if exist "agents" (
    for /d %%D in (agents\*) do (
        if exist "%%D\agent.py" (
            findstr /c:"chromadb" "%%D\agent.py" >nul 2>&1
            if not errorlevel 1 (
                set "HAS_RAG_AGENTS=true"
            )
        )
    )
)

:: Get Python version
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYTHON_VERSION=%%V
echo   - Python detected: %PYTHON_VERSION%

:: Check RAG compatibility
if "!HAS_RAG_AGENTS!"=="true" (
    echo   - RAG agents detected ^(require Python 3.11-3.13^)
    echo %PYTHON_VERSION% | findstr /r "^3\.14\." >nul
    if not errorlevel 1 (
        echo.
        echo   WARNING: Python 3.14+ detected
        echo   RAG agents will not work with this version
        echo   ChromaDB requires Python 3.11-3.13
        echo.
        set /p CONTINUE="  Continue anyway? [y/N]: "
        if /i not "!CONTINUE!"=="y" (
            echo Cancelled.
            pause
            exit /b 1
        )
    )
)

:: -----------------------------------------------------------------------------
:: 2. Create virtual environment
:: -----------------------------------------------------------------------------
echo [2/7] Creating virtual environment .venv...

if exist "web\.venv" (
    echo   - Virtual environment already exists in web\.venv
) else (
    python -m venv web\.venv
    if errorlevel 1 (
        echo   ERROR: Could not create virtual environment
        echo   Make sure you have Python 3.10 or higher installed
        pause
        exit /b 1
    )
    echo   - Virtual environment created in web\.venv
)

:: -----------------------------------------------------------------------------
:: 3. Activate virtual environment
:: -----------------------------------------------------------------------------
echo [3/7] Activating virtual environment...
call web\.venv\Scripts\activate.bat
echo   - Environment activated

:: -----------------------------------------------------------------------------
:: 4. Install dependencies
:: -----------------------------------------------------------------------------
echo [4/7] Installing dependencies...

:: Update pip
python -m pip install --upgrade pip -q

:: Install web requirements
if exist "web\requirements.txt" (
    echo   - Installing web requirements...
    pip install -r web\requirements.txt -q
    echo   - Web requirements installed
)

:: -----------------------------------------------------------------------------
:: 5. Configure conversation logging
:: -----------------------------------------------------------------------------
echo [5/7] Configuring conversation logging...
echo.
echo   Do you want to enable conversation logging?
echo   (Useful for testing. Logs are saved to web/logs/conversations.log)
echo.
set /p ENABLE_LOG="  Enable logging [y/N]: "

:: Save logging preference to write at the end
if /i "!ENABLE_LOG!"=="y" (
    set "LOGGING_VALUE=true"
    echo   - Logging enabled
) else (
    set "LOGGING_VALUE=false"
    echo   - Logging disabled
)

:: -----------------------------------------------------------------------------
:: 6. Configure API key for agents
:: -----------------------------------------------------------------------------
echo [6/7] Configuring Mistral API key...
echo.

:: Detect agent folders in agents/
set "AGENTS="
if exist "agents" (
    for /d %%D in (agents\*) do (
        if exist "%%D\agent.py" (
            set "AGENTS=!AGENTS! %%D"
        )
    )
)

set "API_KEY="
if "!AGENTS!"=="" (
    echo   - No agent folders found
) else (
    echo   Agents detected:!AGENTS!
    echo.
    echo   Enter your Mistral API key:
    echo   (You can get it at https://console.mistral.ai/api-keys^)
    echo.
    set /p API_KEY="  MISTRAL_API_KEY: "

    if "!API_KEY!"=="" (
        echo.
        echo   - No API key provided. You can configure it manually later.
    ) else (
        for /d %%D in (agents\*) do (
            if exist "%%D\agent.py" (
                echo MISTRAL_API_KEY=!API_KEY!> "%%D\.env"
                echo   - Configured: %%D\.env
            )
        )
        echo.
        echo   - API key configured in agents
    )
)

:: -----------------------------------------------------------------------------
:: 7. Create web/.env configuration file
:: -----------------------------------------------------------------------------
echo [7/7] Creating web\.env configuration file...

(
echo ENABLE_LOGGING=!LOGGING_VALUE!
echo.
echo # ============================================
echo # DEFAULT LLM Provider Configuration
echo # ============================================
echo # This is the DEFAULT configuration for all agents.
echo # Individual agents can override by adding LLM_PROVIDER to their own .env
echo.
echo # --- Cloud LLM ^(Mistral^) - DEFAULT ---
echo LLM_PROVIDER=mistral
echo MISTRAL_API_KEY=!API_KEY!
echo MISTRAL_MODEL=mistral-large-latest
echo.
echo # --- To use Local LLM ^(Ollama^) as default, comment above and uncomment below ---
echo # LLM_PROVIDER=ollama
echo # OLLAMA_BASE_URL=http://localhost:11434
echo # OLLAMA_MODEL=mistral
) > "web\.env"

echo   - web\.env file created

:: -----------------------------------------------------------------------------
:: Final summary
:: -----------------------------------------------------------------------------
echo.
echo ==============================================
echo         Setup completed
echo ==============================================
echo.
echo To start the web server:
echo   cd ..
echo   cd web
echo   run_html_server.bat
echo.

pause
