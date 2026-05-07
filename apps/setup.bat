@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
:: TOMMI - Setup Script for Windows
:: =============================================================================
:: This script configures the environment after extracting the installation file
:: =============================================================================
:: Usage: setup.bat [config_file]
:: If a config file is provided, values are read from it instead of prompting.
:: Example: setup.bat ..\tommi_setup_server.txt
::
:: Expected variables in config file:
::   ENABLE_LOGGING=y          (y/n)
::   MISTRAL_API_KEY=...       (API key or empty)
::   ADMIN_USER=admin          (superuser username)
::   ADMIN_PASSWORD=...        (superuser password)
::   SMTP_HOST=...             (optional)
::   SMTP_PORT=587             (optional)
::   SMTP_USER=...             (optional)
::   SMTP_PASSWORD=...         (optional)
::   SMTP_FROM=...             (optional)
::   SMTP_USE_TLS=true         (optional)
:: =============================================================================

echo.
echo ==============================================
echo        TOMMI - Initial Setup
echo ==============================================
echo.

:: Get script directory and change to project root directory
cd /d "%~dp0.."

:: =============================================================================
:: Configuration file support
:: =============================================================================
set "UNATTENDED=false"
set "CONFIG_FILE=%~1"

if not "%CONFIG_FILE%"=="" (
    if not exist "%CONFIG_FILE%" (
        echo   ERROR: Configuration file not found: %CONFIG_FILE%
        pause
        exit /b 1
    )
    echo   Reading configuration from: %CONFIG_FILE%
    for /f "usebackq tokens=1,* delims==" %%A in ("%CONFIG_FILE%") do (
        set "%%A=%%B"
    )
    set "UNATTENDED=true"
)

:: -----------------------------------------------------------------------------
:: 0. Verify system dependencies
:: -----------------------------------------------------------------------------
echo [0/8] Verifying system dependencies...

where python >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python is not installed or not in PATH
    echo   Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import venv" 2>nul
if errorlevel 1 (
    echo   ERROR: The 'venv' module is not available
    echo   Reinstall Python with the 'pip' and 'venv' options checked
    pause
    exit /b 1
)

echo   - System dependencies verified

:: -----------------------------------------------------------------------------
:: 1. Detect compatible Python version
:: -----------------------------------------------------------------------------
echo [1/8] Detecting compatible Python version...

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
        if "!UNATTENDED!"=="true" (
            echo   Unattended mode: continuing anyway
        ) else (
            set /p CONTINUE="  Continue anyway? [y/N]: "
            if /i not "!CONTINUE!"=="y" (
                echo Cancelled.
                pause
                exit /b 1
            )
        )
    )
)

:: -----------------------------------------------------------------------------
:: 2. Create virtual environment
:: -----------------------------------------------------------------------------
echo [2/8] Creating virtual environment .venv...

if exist ".venv" (
    echo   - Virtual environment already exists in .venv\
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo   ERROR: Could not create virtual environment
        echo   Make sure you have Python 3.10 or higher installed
        pause
        exit /b 1
    )
    echo   - Virtual environment created in .venv\
)

:: -----------------------------------------------------------------------------
:: 3. Activate virtual environment
:: -----------------------------------------------------------------------------
echo [3/8] Activating virtual environment...

if not exist ".venv\Scripts\activate.bat" (
    echo   ERROR: .venv\Scripts\activate.bat not found
    echo   Delete .venv\ and run the script again
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo   - Environment activated

:: -----------------------------------------------------------------------------
:: 4. Install dependencies
:: -----------------------------------------------------------------------------
echo [4/8] Installing dependencies...

:: Update pip
echo   - Updating pip...
python -m pip install --upgrade pip -q 2>nul
if errorlevel 1 (
    python -m ensurepip --upgrade 2>nul
    python -m pip install --upgrade pip -q
)

:: Install web requirements
if exist "web\requirements.txt" (
    echo   - Installing web requirements...
    python -m pip install -r web\requirements.txt -q
    if errorlevel 1 (
        echo   ERROR: Error installing dependencies
        echo   Some dependencies may require Microsoft Visual C++ Build Tools
        echo   Download from https://visualstudio.microsoft.com/visual-cpp-build-tools/
        pause
        exit /b 1
    )
    echo   - Web requirements installed
) else (
    echo   - web\requirements.txt not found
)

:: -----------------------------------------------------------------------------
:: 5. Configure conversation logging
:: -----------------------------------------------------------------------------
echo [5/8] Configuring conversation logging...
echo.

if "!UNATTENDED!"=="true" (
    set "ENABLE_LOG=!ENABLE_LOGGING!"
    if "!ENABLE_LOG!"=="" set "ENABLE_LOG=n"
) else (
    echo   Do you want to enable conversation logging?
    echo   ^(Useful for testing. Logs are saved to web/logs/conversations.log^)
    echo.
    set /p ENABLE_LOG="  Enable logging [y/N]: "
)

if /i "!ENABLE_LOG!"=="y" (
    set "LOGGING_VALUE=true"
    echo   - Logging enabled
) else (
    set "LOGGING_VALUE=false"
    echo   - Logging disabled
)

:: -----------------------------------------------------------------------------
:: 6. Configure Mistral API key
:: -----------------------------------------------------------------------------
echo [6/8] Configuring Mistral API key...
echo.

:: Detect agent folders
set "AGENT_COUNT=0"
if exist "agents" (
    for /d %%D in (agents\*) do (
        if exist "%%D\agent.py" (
            set /a AGENT_COUNT+=1
        )
    )
)

set "API_KEY="
if !AGENT_COUNT! equ 0 (
    echo   - No agent folders found
) else (
    echo   Agents detected: !AGENT_COUNT!

    if "!UNATTENDED!"=="true" (
        set "API_KEY=!MISTRAL_API_KEY!"
    ) else (
        echo.
        echo   Enter your Mistral API key:
        echo   ^(You can get it at https://console.mistral.ai/api-keys^)
        echo.
        set /p API_KEY="  MISTRAL_API_KEY: "
    )

    if "!API_KEY!"=="" (
        echo   - No API key provided. You can configure it manually in web\.env
    ) else (
        echo   - API key configured ^(will be saved to web\.env^)
    )
)

:: -----------------------------------------------------------------------------
:: 7. Create web/.env configuration file
:: -----------------------------------------------------------------------------
echo [7/8] Creating web\.env configuration file...

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
echo.
echo # --- Optional: restrict which models appear in the UI selector ---
echo # AVAILABLE_MODELS=mistral-large-latest,mistral-small-latest
) > "web\.env"

:: Append SMTP configuration if provided
if not "!SMTP_HOST!"=="" (
    if "!SMTP_PORT!"=="" set "SMTP_PORT=587"
    if "!SMTP_FROM!"=="" set "SMTP_FROM=!SMTP_USER!"
    if "!SMTP_USE_TLS!"=="" set "SMTP_USE_TLS=true"
    (
    echo.
    echo # ============================================
    echo # SMTP Configuration ^(for user invitations^)
    echo # ============================================
    echo SMTP_HOST=!SMTP_HOST!
    echo SMTP_PORT=!SMTP_PORT!
    echo SMTP_USER=!SMTP_USER!
    echo SMTP_PASSWORD=!SMTP_PASSWORD!
    echo SMTP_FROM=!SMTP_FROM!
    echo SMTP_USE_TLS=!SMTP_USE_TLS!
    ) >> "web\.env"
    echo   - SMTP configuration added to web\.env
)

echo   - web\.env file created

:: -----------------------------------------------------------------------------
:: 8. Create superuser account
:: -----------------------------------------------------------------------------
echo [8/8] Creating superuser account...
echo.

:: Check if superuser already exists
python -c "import json; users=json.load(open('web/data/users.json')); exit(0 if any(u.get('role')=='superuser' for u in users.values()) else 1)" 2>nul
if not errorlevel 1 (
    echo   - Superuser already exists
    goto :after_superuser
)

if "!UNATTENDED!"=="true" (
    if "!ADMIN_USER!"=="" set "ADMIN_USER=admin"
    if "!ADMIN_PASSWORD!"=="" (
        echo   ERROR: ADMIN_PASSWORD not set in config file
        pause
        exit /b 1
    )
    set "ADMIN_PASS=!ADMIN_PASSWORD!"
) else (
    echo   Set up the administrator account for Tommi.
    echo   Password requirements: min. 8 chars, uppercase, lowercase, digit, special character
    echo.
    set /p ADMIN_USER="  Admin username [admin]: "
    if "!ADMIN_USER!"=="" set "ADMIN_USER=admin"

    :password_loop
    set /p ADMIN_PASS="  Admin password: "
    if "!ADMIN_PASS!"=="" (
        echo   - Password cannot be empty
        goto :password_loop
    )
)

:: Validate password via Python
python -c "import sys; p='!ADMIN_PASS!'; errs=[]; len(p)<8 and errs.append('min 8 chars'); not any(c.isupper() for c in p) and errs.append('need uppercase'); not any(c.islower() for c in p) and errs.append('need lowercase'); not any(c.isdigit() for c in p) and errs.append('need digit'); all(c.isalnum() for c in p) and errs.append('need special char'); errs and (print('Password error: '+', '.join(errs)), sys.exit(1))" 2>nul
if errorlevel 1 (
    if "!UNATTENDED!"=="true" (
        echo   ERROR: Password does not meet complexity requirements
        pause
        exit /b 1
    ) else (
        goto :password_loop
    )
)

:: Create superuser via Python
python -c "import sys; sys.path.insert(0,'web'); from auth import create_user; create_user('!ADMIN_USER!','!ADMIN_PASS!','superuser',provisional=False); print('OK')"
if not errorlevel 1 (
    echo   - Superuser '!ADMIN_USER!' created
) else (
    echo   ERROR: Could not create superuser
)

:after_superuser

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
