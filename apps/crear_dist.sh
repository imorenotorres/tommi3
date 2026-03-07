#!/bin/bash

# =============================================================================
# TOMMI - Script para crear archivos de distribución
# =============================================================================
# Crea los archivos tar.gz (Linux/Mac) y zip (Windows) para distribución
# =============================================================================

set -e

# Variable para rastrear templates creados (para limpieza)
CREATED_TEMPLATES=()

# Función de limpieza en caso de error o salida
cleanup() {
    if [ ${#CREATED_TEMPLATES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Limpiando archivos temporales...${NC}"
        for template in "${CREATED_TEMPLATES[@]}"; do
            if [ -f "$template" ]; then
                rm -f "$template"
                echo -e "  → Eliminado $template"
            fi
        done
    fi
}

# Ejecutar limpieza en caso de error o salida
trap cleanup EXIT

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Obtener directorio del script y cambiar al directorio raíz del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Fecha actual para el nombre del archivo
DATE=$(date +%Y-%m-%d)

# Directorio de salida
DIST_DIR="dist"

# Nombres de los archivos
TAR_FILE="tommi-${DATE}-linux-mac.tar.gz"
ZIP_FILE="tommi-${DATE}-windows.zip"

echo -e "${BLUE}"
echo "=============================================="
echo "    TOMMI - Crear archivos de distribución   "
echo "=============================================="
echo -e "${NC}"

# Crear directorio dist si no existe
mkdir -p "$DIST_DIR"

# -----------------------------------------------------------------------------
# Detectar agentes disponibles en agents/
# -----------------------------------------------------------------------------
AVAILABLE_AGENTS=()
if [ -d "agents" ]; then
    for dir in agents/*/; do
        dir_name="${dir%/}"
        # Un agente es un directorio con app.py y agent.py
        if [ -f "${dir_name}/app.py" ] && [ -f "${dir_name}/agent.py" ]; then
            AVAILABLE_AGENTS+=("$dir_name")
        fi
    done
fi

echo -e "${YELLOW}Agentes disponibles:${NC}"
for agent in "${AVAILABLE_AGENTS[@]}"; do
    echo "  - $agent"
done
echo ""

# -----------------------------------------------------------------------------
# Preguntar qué agentes incluir
# -----------------------------------------------------------------------------
echo -e "${YELLOW}¿Desea incluir agentes en la distribución?${NC}"
echo "  1) Sí - Incluir todos los agentes"
echo "  2) No - Solo archivos base (sin agentes)"
echo ""
read -p "Seleccione una opción [1-2] (por defecto: 1): " AGENT_OPTION

AGENTS_TO_INCLUDE=()
case "$AGENT_OPTION" in
    2)
        AGENTS_TO_INCLUDE=()
        echo -e "${GREEN}  ✓ No se incluirán agentes${NC}"
        TAR_FILE="tommi-${DATE}-base-linux-mac.tar.gz"
        ZIP_FILE="tommi-${DATE}-base-windows.zip"
        ;;
    *)
        AGENTS_TO_INCLUDE=("${AVAILABLE_AGENTS[@]}")
        echo -e "${GREEN}  ✓ Se incluirán todos los agentes: ${AGENTS_TO_INCLUDE[*]}${NC}"
        ;;
esac
echo ""

# -----------------------------------------------------------------------------
# Crear archivos .env.template para agentes text2sql
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Creando archivos .env.template para agentes text2sql...${NC}"

for agent in "${AGENTS_TO_INCLUDE[@]}"; do
    if [ -f "$agent/app.py" ]; then
        # Detectar si es un agente text2sql
        if grep -q '"type": "text2sql"' "$agent/app.py" 2>/dev/null; then
            echo -e "  → Creando .env.template para $agent (text2sql)"
            cat > "$agent/.env.template" << 'ENVTEMPLATE'
# ============================================
# Text2SQL Agent - Dual LLM Configuration
# ============================================
# Este agente usa DOS LLMs:
#   1. LLM Principal (cloud) - para convertir texto a SQL
#   2. LLM Local (Ollama) - para formatear resultados

# ----- LLM PRINCIPAL (texto a SQL) -----
LLM_PROVIDER=mistral
MISTRAL_API_KEY=TU_API_KEY_AQUI
MISTRAL_MODEL=mistral-large-latest

# ----- LLM LOCAL (formatear resultados) -----
# Siempre usa Ollama local para formatear
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_LLM_MODEL=mistral
ENVTEMPLATE
            # Registrar para limpieza automática
            CREATED_TEMPLATES+=("$agent/.env.template")
        fi
    fi
done

# -----------------------------------------------------------------------------
# Archivos a incluir
# -----------------------------------------------------------------------------
FILES_TO_INCLUDE=(
    "apps/"
    "howto.md"
    "HOWTO.html"
    "README_INSTALL.md"
    "README_INSTALL.html"
    "tommi_frontend.png"
    "web/"
    ".github/"
    ".dockerignore"
)

# Añadir los agentes seleccionados
for agent in "${AGENTS_TO_INCLUDE[@]}"; do
    FILES_TO_INCLUDE+=("$agent")
done

# Verificar que los archivos existen
echo -e "${YELLOW}Verificando archivos...${NC}"
MISSING_FILES=()
for file in "${FILES_TO_INCLUDE[@]}"; do
    if [ ! -e "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}Error: Los siguientes archivos no existen:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
fi
echo -e "${GREEN}  ✓ Todos los archivos encontrados${NC}"

# -----------------------------------------------------------------------------
# Crear tar.gz para Linux/Mac
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Creando ${TAR_FILE}...${NC}"

# Usar sintaxis compatible con BSD tar (macOS) y GNU tar (Linux)
if tar -czvf "${DIST_DIR}/${TAR_FILE}" \
    --exclude '.venv' \
    --exclude '.env' \
    --exclude '__pycache__' \
    --exclude '.claude' \
    --exclude '.DS_Store' \
    --exclude 'venv' \
    --exclude '*.pyc' \
    --exclude 'logs' \
    "${FILES_TO_INCLUDE[@]}"; then
    echo -e "${GREEN}  ✓ ${TAR_FILE} creado${NC}"
else
    echo -e "${RED}  ✗ Error al crear ${TAR_FILE}${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Crear zip para Windows
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Creando ${ZIP_FILE}...${NC}"

# Eliminar zip anterior si existe
rm -f "${DIST_DIR}/${ZIP_FILE}"

if zip -r "${DIST_DIR}/${ZIP_FILE}" \
    "${FILES_TO_INCLUDE[@]}" \
    -x "*.venv*" \
    -x "*/.venv/*" \
    -x "*.env" \
    -x "*/.env" \
    -x "*__pycache__*" \
    -x "*.claude*" \
    -x "*/.claude/*" \
    -x ".DS_Store" \
    -x "*/.DS_Store" \
    -x "*/venv/*" \
    -x "*.pyc" \
    -x "*/logs/*"; then
    echo -e "${GREEN}  ✓ ${ZIP_FILE} creado${NC}"
else
    echo -e "${RED}  ✗ Error al crear ${ZIP_FILE}${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Resumen final
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}=============================================="
echo "           Distribución completada           "
echo "==============================================${NC}"
echo ""
echo "Archivos creados en ${DIST_DIR}/:"
echo ""
ls -lh "${DIST_DIR}/${TAR_FILE}" "${DIST_DIR}/${ZIP_FILE}" 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo ""

# La limpieza de .env.template se hace automáticamente via trap EXIT
