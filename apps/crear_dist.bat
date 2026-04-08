@echo off
setlocal enabledelayedexpansion

REM =============================================================================
REM TOMMI - Script to create distribution files
REM =============================================================================
REM Creates zip (Windows) files for distribution
REM =============================================================================

cd /d "%~dp0.."

REM Current date for filename
for /f "tokens=1-3 delims=/" %%a in ('echo %date%') do (
    set DAY=%%a
    set MONTH=%%b
    set YEAR=%%c
)
for /f "tokens=1-3 delims=-" %%a in ('echo %date%') do (
    set YEAR=%%a
    set MONTH=%%b
    set DAY=%%c
)
set DATE=%YEAR%-%MONTH%-%DAY%

REM Output directory
set DIST_DIR=dist

REM File names (default)
set ZIP_FILE=tommi-%DATE%-windows.zip

echo ==============================================
echo     TOMMI - Create distribution files
echo ==============================================
echo.

REM Create dist directory if it doesn't exist
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

REM -----------------------------------------------------------------------------
REM Detect available agents in agents/
REM -----------------------------------------------------------------------------
echo Available agents:
set AGENT_COUNT=0
set AVAILABLE_AGENTS=

if exist "agents" (
    for /d %%d in (agents\*) do (
        if exist "%%d\app.py" (
            if exist "%%d\agent.py" (
                echo   - %%d
                set /a AGENT_COUNT+=1
                set AVAILABLE_AGENTS=!AVAILABLE_AGENTS! %%d
            )
        )
    )
)
echo.

REM -----------------------------------------------------------------------------
REM Ask which agents to include
REM -----------------------------------------------------------------------------
echo Do you want to include agents in the distribution?
echo   1) Yes - Include all agents
echo   2) No - Base files only (no agents)
echo.
set /p AGENT_OPTION="Select an option [1-2] (default: 1): "

if "%AGENT_OPTION%"=="" set AGENT_OPTION=1

set AGENTS_TO_INCLUDE=

if "%AGENT_OPTION%"=="2" (
    set AGENTS_TO_INCLUDE=
    echo   OK - No agents will be included
    set ZIP_FILE=tommi-%DATE%-base-windows.zip
) else (
    set AGENTS_TO_INCLUDE=%AVAILABLE_AGENTS%
    echo   OK - All agents will be included:%AVAILABLE_AGENTS%
)
echo.

REM -----------------------------------------------------------------------------
REM Create .env.template files for text2sql agents
REM -----------------------------------------------------------------------------
echo Creating .env.template files for text2sql agents...

set CREATED_TEMPLATES=

for %%a in (%AGENTS_TO_INCLUDE%) do (
    if exist "%%a\app.py" (
        findstr /C:"\"type\": \"text2sql\"" "%%a\app.py" >nul 2>&1
        if !errorlevel!==0 (
            echo   - Creating .env.template for %%a ^(text2sql^)
            (
                echo # ============================================
                echo # Text2SQL Agent - Dual LLM Configuration
                echo # ============================================
                echo # This agent uses TWO LLMs:
                echo #   1. Main LLM ^(cloud^) - to convert text to SQL
                echo #   2. Local LLM ^(Ollama^) - to format results
                echo.
                echo # ----- MAIN LLM ^(text to SQL^) -----
                echo LLM_PROVIDER=mistral
                echo MISTRAL_API_KEY=YOUR_API_KEY_HERE
                echo MISTRAL_MODEL=mistral-large-latest
                echo.
                echo # ----- LOCAL LLM ^(format results^) -----
                echo # Always uses local Ollama for formatting
                echo LOCAL_LLM_BASE_URL=http://localhost:11434
                echo LOCAL_LLM_MODEL=mistral
            ) > "%%a\.env.template"
            set CREATED_TEMPLATES=!CREATED_TEMPLATES! %%a
        )
    )
)
echo.

REM -----------------------------------------------------------------------------
REM Verify base files
REM -----------------------------------------------------------------------------
echo Verifying files...
set MISSING=0

for %%f in (howto.md HOWTO.html README_INSTALL.md README_INSTALL.html tommi_frontend.png .dockerignore) do (
    if not exist "%%f" (
        echo   MISSING: %%f
        set MISSING=1
    )
)

for %%d in (apps web .github prompts scripts agents\base) do (
    if not exist "%%d\" (
        echo   MISSING directory: %%d
        set MISSING=1
    )
)

REM Verify selected agents
for %%a in (%AGENTS_TO_INCLUDE%) do (
    if not exist "%%a\" (
        echo   MISSING agent: %%a
        set MISSING=1
    )
)

if %MISSING%==1 (
    echo.
    echo ERROR: Required files are missing
    goto :cleanup
)
echo   OK - All files found

REM -----------------------------------------------------------------------------
REM Create zip for Windows
REM -----------------------------------------------------------------------------
echo.
echo Creating %ZIP_FILE%...

REM Remove previous zip if exists
if exist "%DIST_DIR%\%ZIP_FILE%" del "%DIST_DIR%\%ZIP_FILE%"

REM Build directory list for PowerShell
set PS_DIRS='apps', 'prompts', 'scripts', 'agents\base', 'web', '.github'
for %%a in (%AGENTS_TO_INCLUDE%) do (
    set PS_DIRS=!PS_DIRS!, '%%a'
)

REM Use PowerShell to create the zip
powershell -Command "& { $files = @('howto.md', 'HOWTO.html', 'README_INSTALL.md', 'README_INSTALL.html', 'tommi_frontend.png', '.dockerignore'); $dirs = @(%PS_DIRS%); $tempDir = 'dist\_temp_tommi'; if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }; New-Item -ItemType Directory -Path $tempDir | Out-Null; foreach ($f in $files) { Copy-Item $f $tempDir -Force }; foreach ($d in $dirs) { if (Test-Path $d) { Copy-Item $d $tempDir -Recurse -Force } }; Get-ChildItem $tempDir -Recurse -Include '.venv','.env','__pycache__','.claude','venv','*.pyc','logs','chroma_db','audit_log.jsonl','authorships_cache.json' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Compress-Archive -Path \"$tempDir\*\" -DestinationPath 'dist\%ZIP_FILE%' -Force; Remove-Item $tempDir -Recurse -Force }"

if exist "%DIST_DIR%\%ZIP_FILE%" (
    echo   OK - %ZIP_FILE% created
) else (
    echo   ERROR - Could not create zip file
    goto :cleanup
)

REM -----------------------------------------------------------------------------
REM Clean up temporary .env.template files
REM -----------------------------------------------------------------------------
:cleanup
echo.
echo Cleaning up temporary files...
for %%a in (%CREATED_TEMPLATES%) do (
    if exist "%%a\.env.template" (
        del "%%a\.env.template"
        echo   - Removed %%a\.env.template
    )
)

if %MISSING%==1 (
    exit /b 1
)

echo.
echo ==============================================
echo            Distribution completed
echo ==============================================
echo.
echo File created in %DIST_DIR%\:
dir /b "%DIST_DIR%\%ZIP_FILE%"
echo.

endlocal
