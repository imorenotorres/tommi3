#!/bin/bash

# =============================================================================
# TOMMI - Script de configuración
# =============================================================================
# Este script configura el entorno después de descomprimir el archivo de instalación
# Compatible con Linux (Debian/Ubuntu, RHEL/CentOS, Arch) y macOS
# =============================================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Obtener directorio del script y cambiar al directorio raíz del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# =============================================================================
# Auto-corrección para archivos que pasaron por Windows
# =============================================================================
fix_line_endings_and_permissions() {
    local fixed_crlf=false
    local fixed_perms=false

    # Buscar todos los scripts .sh en el proyecto
    while IFS= read -r -d '' script; do
        # Ignorar venv y __pycache__
        if [[ "$script" == *"/venv/"* ]] || [[ "$script" == *"__pycache__"* ]]; then
            continue
        fi

        # Verificar y corregir finales de línea CRLF
        if file "$script" 2>/dev/null | grep -q "CRLF"; then
            # Usar perl que funciona igual en macOS y Linux
            if command -v perl &> /dev/null; then
                perl -pi -e 's/\r$//' "$script" 2>/dev/null
                fixed_crlf=true
            fi
        fi

        # Restaurar permisos de ejecución si no los tiene
        if [ ! -x "$script" ]; then
            chmod +x "$script" 2>/dev/null || true
            fixed_perms=true
        fi
    done < <(find . -name "*.sh" -type f -print0 2>/dev/null)

    # Mostrar mensaje solo si se hicieron correcciones
    if [ "$fixed_crlf" = true ] || [ "$fixed_perms" = true ]; then
        echo -e "${YELLOW}Auto-corrección aplicada:${NC}"
        [ "$fixed_crlf" = true ] && echo -e "  → Finales de línea CRLF corregidos"
        [ "$fixed_perms" = true ] && echo -e "  → Permisos de ejecución restaurados"
        echo ""
    fi
}

# Ejecutar auto-corrección silenciosamente
fix_line_endings_and_permissions

echo -e "${BLUE}"
echo "=============================================="
echo "       TOMMI - Configuración inicial         "
echo "=============================================="
echo -e "${NC}"

# Detectar sistema operativo
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "redhat"
    elif [[ -f /etc/arch-release ]]; then
        echo "arch"
    else
        echo "linux"
    fi
}

OS_TYPE=$(detect_os)
echo -e "  Sistema detectado: ${GREEN}$OS_TYPE${NC}"

# -----------------------------------------------------------------------------
# 0. Verificar dependencias del sistema
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[0/7] Verificando dependencias del sistema...${NC}"

# Verificar que Python3 existe
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  ✗ Python3 no está instalado${NC}"
    case $OS_TYPE in
        debian)
            echo -e "${YELLOW}    Instala con: sudo apt update && sudo apt install python3 python3-pip python3-venv${NC}"
            ;;
        redhat)
            echo -e "${YELLOW}    Instala con: sudo dnf install python3 python3-pip${NC}"
            ;;
        arch)
            echo -e "${YELLOW}    Instala con: sudo pacman -S python python-pip${NC}"
            ;;
        macos)
            echo -e "${YELLOW}    Instala con: brew install python3${NC}"
            ;;
    esac
    exit 1
fi

# Verificar que el módulo venv está disponible
if ! python3 -c "import venv" 2>/dev/null; then
    echo -e "${RED}  ✗ El módulo 'venv' no está instalado${NC}"
    case $OS_TYPE in
        debian)
            echo -e "${YELLOW}    Instala con: sudo apt install python3-venv${NC}"
            ;;
        redhat)
            echo -e "${YELLOW}    Instala con: sudo dnf install python3-libs${NC}"
            ;;
        arch)
            echo -e "${YELLOW}    El módulo venv debería estar incluido en python${NC}"
            ;;
        macos)
            echo -e "${YELLOW}    El módulo venv debería estar incluido en python3${NC}"
            ;;
    esac
    exit 1
fi

echo -e "${GREEN}  ✓ Dependencias del sistema verificadas${NC}"

# -----------------------------------------------------------------------------
# 1. Detectar versión de Python compatible
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/7] Detectando versión de Python compatible...${NC}"

# Detectar si hay agentes RAG (requieren Python 3.11-3.13)
HAS_RAG_AGENTS=false
if [ -d "agents" ]; then
    for dir in agents/*/; do
        if [ -f "${dir}agent.py" ]; then
            if grep -q "chromadb" "${dir}agent.py" 2>/dev/null; then
                HAS_RAG_AGENTS=true
                break
            fi
        fi
    done
fi

# Buscar Python compatible
PYTHON_CMD=""
if [ "$HAS_RAG_AGENTS" = true ]; then
    echo -e "  → Detectados agentes RAG (requieren Python 3.11-3.13)"
    # RAG agents: buscar Python 3.11-3.13 (ChromaDB no compatible con 3.14+)
    for cmd in python3.12 python3.13 python3.11; do
        if command -v $cmd &> /dev/null; then
            PYTHON_CMD=$cmd
            break
        fi
    done
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}  ⚠️  ADVERTENCIA: No se encontró Python 3.11-3.13${NC}"
        echo -e "${RED}     Los agentes RAG no funcionarán con Python 3.14+${NC}"
        case $OS_TYPE in
            debian)
                echo -e "${YELLOW}     Instala Python 3.12: sudo apt install python3.12 python3.12-venv${NC}"
                ;;
            redhat)
                echo -e "${YELLOW}     Instala Python 3.12: sudo dnf install python3.12${NC}"
                ;;
            macos)
                echo -e "${YELLOW}     Instala Python 3.12: brew install python@3.12${NC}"
                ;;
            *)
                echo -e "${YELLOW}     Instala Python 3.12 desde tu gestor de paquetes${NC}"
                ;;
        esac
        echo ""
        read -p "  ¿Continuar con python3 de todos modos? [s/N]: " CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Ss]$ ]]; then
            echo "Cancelado."
            exit 1
        fi
        PYTHON_CMD="python3"
    fi
else
    PYTHON_CMD="python3"
fi

echo -e "${GREEN}  → Usando: $PYTHON_CMD ($(${PYTHON_CMD} --version 2>&1))${NC}"

# -----------------------------------------------------------------------------
# 2. Crear entorno virtual
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/7] Creando entorno virtual venv...${NC}"

if [ -d "venv" ]; then
    echo -e "${GREEN}  → El entorno virtual ya existe en venv/${NC}"
else
    echo "  → Creando entorno virtual con $PYTHON_CMD..."
    if ! $PYTHON_CMD -m venv venv; then
        echo -e "${RED}  ✗ Error creando entorno virtual${NC}"
        # Determinar el paquete venv correcto según la versión de Python
        PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        case $OS_TYPE in
            debian)
                echo -e "${YELLOW}    Prueba: sudo apt install python${PYTHON_VERSION}-venv${NC}"
                ;;
            *)
                echo -e "${YELLOW}    Verifica que el módulo venv esté instalado para Python ${PYTHON_VERSION}${NC}"
                ;;
        esac
        exit 1
    fi
    echo -e "${GREEN}  → Entorno virtual creado en venv/${NC}"
fi

# -----------------------------------------------------------------------------
# 3. Activar entorno virtual
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/7] Activando entorno virtual...${NC}"

if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED}  ✗ No se encontró venv/bin/activate${NC}"
    echo -e "${YELLOW}    Elimina venv/ y ejecuta el script de nuevo${NC}"
    exit 1
fi

source venv/bin/activate
echo -e "${GREEN}  → Entorno activado: $(which python)${NC}"

# -----------------------------------------------------------------------------
# 4. Instalar dependencias
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/7] Instalando dependencias...${NC}"

# Actualizar pip (usar python del venv, no python3 del sistema)
echo "  → Actualizando pip..."
python -m pip install --upgrade pip -q 2>/dev/null || {
    echo -e "${YELLOW}  → Instalando pip en el entorno virtual...${NC}"
    python -m ensurepip --upgrade 2>/dev/null || true
    python -m pip install --upgrade pip -q
}

# Instalar requirements de web
if [ -f "web/requirements.txt" ]; then
    echo "  → Instalando requirements de web..."
    if ! python -m pip install -r web/requirements.txt -q; then
        echo -e "${RED}  ✗ Error instalando dependencias${NC}"
        echo -e "${YELLOW}    Algunas dependencias pueden requerir compilación.${NC}"
        PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        case $OS_TYPE in
            debian)
                echo -e "${YELLOW}    Prueba: sudo apt install build-essential python${PYTHON_VERSION}-dev${NC}"
                ;;
            redhat)
                echo -e "${YELLOW}    Prueba: sudo dnf install gcc python${PYTHON_VERSION}-devel${NC}"
                ;;
        esac
        exit 1
    fi
    echo -e "${GREEN}  → Requirements de web instalados${NC}"
else
    echo -e "${YELLOW}  → No se encontró web/requirements.txt${NC}"
fi

# -----------------------------------------------------------------------------
# 5. Configurar logging de conversaciones
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/7] Configurando logging de conversaciones...${NC}"
echo ""
echo -e "  ${BLUE}¿Deseas habilitar el registro de conversaciones?${NC}"
echo -e "  (Útil para pruebas. Los logs se guardan en web/logs/conversations.log)"
echo ""
read -p "  Habilitar logging [s/N]: " ENABLE_LOG

# Guardar preferencia de logging para escribir al final
if [[ "$ENABLE_LOG" =~ ^[Ss]$ ]]; then
    LOGGING_VALUE="true"
    echo -e "${GREEN}  → Logging habilitado${NC}"
else
    LOGGING_VALUE="false"
    echo -e "${GREEN}  → Logging deshabilitado${NC}"
fi

# -----------------------------------------------------------------------------
# 6. Configurar API key de Mistral (se guarda solo en web/.env)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[6/7] Configurando API key de Mistral...${NC}"
echo ""

# Detectar carpetas de agentes para mostrar información
AGENT_DIRS=()
if [ -d "agents" ]; then
    for dir in agents/*/; do
        dir_name="${dir%/}"
        # Verificar que tiene agent.py (es un agente válido)
        if [ -f "$dir_name/agent.py" ]; then
            AGENT_DIRS+=("$dir_name")
        fi
    done
fi

API_KEY=""
if [ ${#AGENT_DIRS[@]} -eq 0 ]; then
    echo -e "${YELLOW}  → No se encontraron carpetas de agentes${NC}"
else
    echo "  Agentes detectados: ${#AGENT_DIRS[@]}"
    echo ""

    # Pedir API key
    echo -e "${BLUE}  Introduce tu API key de Mistral:${NC}"
    echo -e "  (Puedes obtenerla en https://console.mistral.ai/api-keys)"
    echo ""
    read -p "  MISTRAL_API_KEY: " API_KEY

    if [ -z "$API_KEY" ]; then
        echo -e "${YELLOW}  → No se proporcionó API key. Puedes configurarla manualmente en web/.env${NC}"
    else
        echo -e "${GREEN}  → API key configurada (se guardará en web/.env)${NC}"
    fi
fi

# NOTA: Todos los agentes usan la configuración por defecto de web/.env.
# Los agentes pueden sobrescribir esta configuración en su propio .env si es necesario.

# -----------------------------------------------------------------------------
# 7. Crear archivo web/.env con configuración completa
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[7/7] Creando archivo de configuración web/.env...${NC}"

cat > web/.env << EOF
ENABLE_LOGGING=$LOGGING_VALUE

# ============================================
# DEFAULT LLM Provider Configuration
# ============================================
# This is the DEFAULT configuration for all agents.
# Individual agents can override by adding LLM_PROVIDER to their own .env

# --- Cloud LLM (Mistral) - DEFAULT ---
LLM_PROVIDER=mistral
MISTRAL_API_KEY=$API_KEY
MISTRAL_MODEL=mistral-large-latest

# --- To use Local LLM (Ollama) as default, comment above and uncomment below ---
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=mistral
EOF

echo -e "${GREEN}  → Archivo web/.env creado${NC}"

# -----------------------------------------------------------------------------
# Resumen final
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}=============================================="
echo "            Configuración completada          "
echo "==============================================${NC}"
echo ""
echo "Para iniciar el servidor web:"
echo -e "  ${GREEN}cd ..${NC}"
echo -e "  ${GREEN}cd web${NC}"
echo -e "  ${GREEN}./run_html_server.sh${NC}"
echo ""
