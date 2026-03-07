@echo off
setlocal enabledelayedexpansion

REM =============================================================================
REM TOMMI - Script para crear archivos de distribucion
REM =============================================================================
REM Crea los archivos zip (Windows) para distribucion
REM =============================================================================

cd /d "%~dp0.."

REM Fecha actual para el nombre del archivo
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

REM Directorio de salida
set DIST_DIR=dist

REM Nombres de los archivos (por defecto)
set ZIP_FILE=tommi-%DATE%-windows.zip

echo ==============================================
echo     TOMMI - Crear archivos de distribucion
echo ==============================================
echo.

REM Crear directorio dist si no existe
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

REM -----------------------------------------------------------------------------
REM Detectar agentes disponibles en agents/
REM -----------------------------------------------------------------------------
echo Agentes disponibles:
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
REM Preguntar que agentes incluir
REM -----------------------------------------------------------------------------
echo Desea incluir agentes en la distribucion?
echo   1) Si - Incluir todos los agentes
echo   2) No - Solo archivos base (sin agentes)
echo.
set /p AGENT_OPTION="Seleccione una opcion [1-2] (por defecto: 1): "

if "%AGENT_OPTION%"=="" set AGENT_OPTION=1

set AGENTS_TO_INCLUDE=

if "%AGENT_OPTION%"=="2" (
    set AGENTS_TO_INCLUDE=
    echo   OK - No se incluiran agentes
    set ZIP_FILE=tommi-%DATE%-base-windows.zip
) else (
    set AGENTS_TO_INCLUDE=%AVAILABLE_AGENTS%
    echo   OK - Se incluiran todos los agentes:%AVAILABLE_AGENTS%
)
echo.

REM -----------------------------------------------------------------------------
REM Crear archivos .env.template para agentes text2sql
REM -----------------------------------------------------------------------------
echo Creando archivos .env.template para agentes text2sql...

set CREATED_TEMPLATES=

for %%a in (%AGENTS_TO_INCLUDE%) do (
    if exist "%%a\app.py" (
        findstr /C:"\"type\": \"text2sql\"" "%%a\app.py" >nul 2>&1
        if !errorlevel!==0 (
            echo   - Creando .env.template para %%a ^(text2sql^)
            (
                echo # ============================================
                echo # Text2SQL Agent - Dual LLM Configuration
                echo # ============================================
                echo # Este agente usa DOS LLMs:
                echo #   1. LLM Principal ^(cloud^) - para convertir texto a SQL
                echo #   2. LLM Local ^(Ollama^) - para formatear resultados
                echo.
                echo # ----- LLM PRINCIPAL ^(texto a SQL^) -----
                echo LLM_PROVIDER=mistral
                echo MISTRAL_API_KEY=TU_API_KEY_AQUI
                echo MISTRAL_MODEL=mistral-large-latest
                echo.
                echo # ----- LLM LOCAL ^(formatear resultados^) -----
                echo # Siempre usa Ollama local para formatear
                echo LOCAL_LLM_BASE_URL=http://localhost:11434
                echo LOCAL_LLM_MODEL=mistral
            ) > "%%a\.env.template"
            set CREATED_TEMPLATES=!CREATED_TEMPLATES! %%a
        )
    )
)
echo.

REM -----------------------------------------------------------------------------
REM Verificar archivos base
REM -----------------------------------------------------------------------------
echo Verificando archivos...
set MISSING=0

for %%f in (howto.md HOWTO.html README_INSTALL.md README_INSTALL.html tommi_frontend.png .dockerignore) do (
    if not exist "%%f" (
        echo   FALTA: %%f
        set MISSING=1
    )
)

for %%d in (apps web .github) do (
    if not exist "%%d\" (
        echo   FALTA directorio: %%d
        set MISSING=1
    )
)

REM Verificar agentes seleccionados
for %%a in (%AGENTS_TO_INCLUDE%) do (
    if not exist "%%a\" (
        echo   FALTA agente: %%a
        set MISSING=1
    )
)

if %MISSING%==1 (
    echo.
    echo ERROR: Faltan archivos necesarios
    goto :cleanup
)
echo   OK - Todos los archivos encontrados

REM -----------------------------------------------------------------------------
REM Crear zip para Windows
REM -----------------------------------------------------------------------------
echo.
echo Creando %ZIP_FILE%...

REM Eliminar zip anterior si existe
if exist "%DIST_DIR%\%ZIP_FILE%" del "%DIST_DIR%\%ZIP_FILE%"

REM Construir lista de directorios para PowerShell
set PS_DIRS='apps', 'web', '.github'
for %%a in (%AGENTS_TO_INCLUDE%) do (
    set PS_DIRS=!PS_DIRS!, '%%a'
)

REM Usar PowerShell para crear el zip
powershell -Command "& { $files = @('howto.md', 'HOWTO.html', 'README_INSTALL.md', 'README_INSTALL.html', 'tommi_frontend.png', '.dockerignore'); $dirs = @(%PS_DIRS%); $tempDir = 'dist\_temp_tommi'; if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }; New-Item -ItemType Directory -Path $tempDir | Out-Null; foreach ($f in $files) { Copy-Item $f $tempDir -Force }; foreach ($d in $dirs) { if (Test-Path $d) { Copy-Item $d $tempDir -Recurse -Force } }; Get-ChildItem $tempDir -Recurse -Include '.venv','.env','__pycache__','.claude','venv','*.pyc','logs' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Compress-Archive -Path \"$tempDir\*\" -DestinationPath 'dist\%ZIP_FILE%' -Force; Remove-Item $tempDir -Recurse -Force }"

if exist "%DIST_DIR%\%ZIP_FILE%" (
    echo   OK - %ZIP_FILE% creado
) else (
    echo   ERROR - No se pudo crear el archivo zip
    goto :cleanup
)

REM -----------------------------------------------------------------------------
REM Limpiar archivos .env.template temporales
REM -----------------------------------------------------------------------------
:cleanup
echo.
echo Limpiando archivos temporales...
for %%a in (%CREATED_TEMPLATES%) do (
    if exist "%%a\.env.template" (
        del "%%a\.env.template"
        echo   - Eliminado %%a\.env.template
    )
)

if %MISSING%==1 (
    exit /b 1
)

echo.
echo ==============================================
echo            Distribucion completada
echo ==============================================
echo.
echo Archivo creado en %DIST_DIR%\:
dir /b "%DIST_DIR%\%ZIP_FILE%"
echo.

endlocal
