@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
:: TOMMI - Script de configuración para Windows
:: =============================================================================

echo.
echo ==============================================
echo        TOMMI - Configuracion inicial
echo ==============================================
echo.

:: Obtener directorio del script y cambiar al directorio raíz del proyecto
cd /d "%~dp0.."

:: -----------------------------------------------------------------------------
:: 1. Detectar version de Python compatible
:: -----------------------------------------------------------------------------
echo [1/7] Detectando version de Python compatible...

:: Detectar si hay agentes RAG (requieren Python 3.11-3.13)
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

:: Obtener version de Python
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYTHON_VERSION=%%V
echo   - Python detectado: %PYTHON_VERSION%

:: Verificar compatibilidad con RAG
if "!HAS_RAG_AGENTS!"=="true" (
    echo   - Detectados agentes RAG ^(requieren Python 3.11-3.13^)
    echo %PYTHON_VERSION% | findstr /r "^3\.14\." >nul
    if not errorlevel 1 (
        echo.
        echo   ADVERTENCIA: Python 3.14+ detectado
        echo   Los agentes RAG no funcionaran con esta version
        echo   ChromaDB requiere Python 3.11-3.13
        echo.
        set /p CONTINUE="  Continuar de todos modos? [s/N]: "
        if /i not "!CONTINUE!"=="s" (
            echo Cancelado.
            pause
            exit /b 1
        )
    )
)

:: -----------------------------------------------------------------------------
:: 2. Crear entorno virtual
:: -----------------------------------------------------------------------------
echo [2/7] Creando entorno virtual .venv...

if exist "web\.venv" (
    echo   - El entorno virtual ya existe en web\.venv
) else (
    python -m venv web\.venv
    if errorlevel 1 (
        echo   ERROR: No se pudo crear el entorno virtual
        echo   Asegurate de tener Python 3.10 o superior instalado
        pause
        exit /b 1
    )
    echo   - Entorno virtual creado en web\.venv
)

:: -----------------------------------------------------------------------------
:: 3. Activar entorno virtual
:: -----------------------------------------------------------------------------
echo [3/7] Activando entorno virtual...
call web\.venv\Scripts\activate.bat
echo   - Entorno activado

:: -----------------------------------------------------------------------------
:: 4. Instalar dependencias
:: -----------------------------------------------------------------------------
echo [4/7] Instalando dependencias...

:: Actualizar pip
python -m pip install --upgrade pip -q

:: Instalar requirements de web
if exist "web\requirements.txt" (
    echo   - Instalando requirements de web...
    pip install -r web\requirements.txt -q
    echo   - Requirements de web instalados
)

:: -----------------------------------------------------------------------------
:: 5. Configurar logging de conversaciones
:: -----------------------------------------------------------------------------
echo [5/7] Configurando logging de conversaciones...
echo.
echo   Deseas habilitar el registro de conversaciones?
echo   (Util para pruebas. Los logs se guardan en web/logs/conversations.log)
echo.
set /p ENABLE_LOG="  Habilitar logging [s/N]: "

:: Guardar preferencia de logging para escribir al final
if /i "!ENABLE_LOG!"=="s" (
    set "LOGGING_VALUE=true"
    echo   - Logging habilitado
) else (
    set "LOGGING_VALUE=false"
    echo   - Logging deshabilitado
)

:: -----------------------------------------------------------------------------
:: 6. Configurar API key para los agentes
:: -----------------------------------------------------------------------------
echo [6/7] Configurando API key de Mistral...
echo.

:: Detectar carpetas de agentes en agents/
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
    echo   - No se encontraron carpetas de agentes
) else (
    echo   Agentes detectados:!AGENTS!
    echo.
    echo   Introduce tu API key de Mistral:
    echo   (Puedes obtenerla en https://console.mistral.ai/api-keys^)
    echo.
    set /p API_KEY="  MISTRAL_API_KEY: "

    if "!API_KEY!"=="" (
        echo.
        echo   - No se proporciono API key. Puedes configurarla manualmente mas tarde.
    ) else (
        for /d %%D in (agents\*) do (
            if exist "%%D\agent.py" (
                echo MISTRAL_API_KEY=!API_KEY!> "%%D\.env"
                echo   - Configurado: %%D\.env
            )
        )
        echo.
        echo   - API key configurada en los agentes
    )
)

:: -----------------------------------------------------------------------------
:: 7. Crear archivo web/.env con configuracion completa
:: -----------------------------------------------------------------------------
echo [7/7] Creando archivo de configuracion web\.env...

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

echo   - Archivo web\.env creado

:: -----------------------------------------------------------------------------
:: Resumen final
:: -----------------------------------------------------------------------------
echo.
echo ==============================================
echo         Configuracion completada
echo ==============================================
echo.
echo Para iniciar el servidor web:
echo   cd ..
echo   cd web
echo   run_html_server.bat
echo.

pause
