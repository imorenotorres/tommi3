#!/bin/bash

# =============================================================================
# TOMMI - Script to create distribution files
# =============================================================================
# Creates tar.gz (Linux/Mac) and zip (Windows) files for distribution
# =============================================================================

set -e

# Variable to track created templates (for cleanup)
CREATED_TEMPLATES=()

# Cleanup function in case of error or exit
cleanup() {
    if [ ${#CREATED_TEMPLATES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Cleaning up temporary files...${NC}"
        for template in "${CREATED_TEMPLATES[@]}"; do
            if [ -f "$template" ]; then
                rm -f "$template"
                echo -e "  → Removed $template"
            fi
        done
    fi
}

# Run cleanup on error or exit
trap cleanup EXIT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory and change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Current date for filename
DATE=$(date +%Y-%m-%d)

# Output directory
DIST_DIR="dist"

# File names
TAR_FILE="tommi-${DATE}-linux-mac.tar.gz"
ZIP_FILE="tommi-${DATE}-windows.zip"

echo -e "${BLUE}"
echo "=============================================="
echo "    TOMMI - Create distribution files        "
echo "=============================================="
echo -e "${NC}"

# Create dist directory if it doesn't exist
mkdir -p "$DIST_DIR"

# -----------------------------------------------------------------------------
# Detect available agents in agents/
# -----------------------------------------------------------------------------
AVAILABLE_AGENTS=()
if [ -d "agents" ]; then
    for dir in agents/*/; do
        dir_name="${dir%/}"
        # An agent is a directory with app.py and agent.py
        if [ -f "${dir_name}/app.py" ] && [ -f "${dir_name}/agent.py" ]; then
            AVAILABLE_AGENTS+=("$dir_name")
        fi
    done
fi

echo -e "${YELLOW}Available agents:${NC}"
for agent in "${AVAILABLE_AGENTS[@]}"; do
    echo "  - $agent"
done
echo ""

# -----------------------------------------------------------------------------
# Ask which agents to include
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Do you want to include agents in the distribution?${NC}"
echo "  1) Yes - Include all agents"
echo "  2) No - Base files only (no agents)"
echo ""
read -p "Select an option [1-2] (default: 1): " AGENT_OPTION

AGENTS_TO_INCLUDE=()
case "$AGENT_OPTION" in
    2)
        AGENTS_TO_INCLUDE=()
        echo -e "${GREEN}  ✓ No agents will be included${NC}"
        TAR_FILE="tommi-${DATE}-base-linux-mac.tar.gz"
        ZIP_FILE="tommi-${DATE}-base-windows.zip"
        ;;
    *)
        AGENTS_TO_INCLUDE=("${AVAILABLE_AGENTS[@]}")
        echo -e "${GREEN}  ✓ All agents will be included: ${AGENTS_TO_INCLUDE[*]}${NC}"
        ;;
esac
echo ""

# -----------------------------------------------------------------------------
# Create .env.template files for text2sql agents
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Creating .env.template files for text2sql agents...${NC}"

for agent in "${AGENTS_TO_INCLUDE[@]}"; do
    if [ -f "$agent/app.py" ]; then
        # Detect if it's a text2sql agent
        if grep -q '"type": "text2sql"' "$agent/app.py" 2>/dev/null; then
            echo -e "  → Creating .env.template for $agent (text2sql)"
            cat > "$agent/.env.template" << 'ENVTEMPLATE'
# ============================================
# Text2SQL Agent - Dual LLM Configuration
# ============================================
# This agent uses TWO LLMs:
#   1. Main LLM (cloud) - to convert text to SQL
#   2. Local LLM (Ollama) - to format results

# ----- MAIN LLM (text to SQL) -----
LLM_PROVIDER=mistral
MISTRAL_API_KEY=YOUR_API_KEY_HERE
MISTRAL_MODEL=mistral-large-latest

# ----- LOCAL LLM (format results) -----
# Always uses local Ollama for formatting
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_LLM_MODEL=mistral
ENVTEMPLATE
            # Register for automatic cleanup
            CREATED_TEMPLATES+=("$agent/.env.template")
        fi
    fi
done

# -----------------------------------------------------------------------------
# Files to include
# -----------------------------------------------------------------------------
FILES_TO_INCLUDE=(
    "apps/"
    "prompts/"
    "scripts/"
    "agents/base/"
    "howto.md"
    "howto.html"
    "README_INSTALL.md"
    "README_INSTALL.html"
    "tommi_frontend.png"
    "web/"
    ".github/"
    ".dockerignore"
)

# Add selected agents
for agent in "${AGENTS_TO_INCLUDE[@]}"; do
    FILES_TO_INCLUDE+=("$agent")
done

# Verify that files exist
echo -e "${YELLOW}Verifying files...${NC}"
MISSING_FILES=()
for file in "${FILES_TO_INCLUDE[@]}"; do
    if [ ! -e "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}Error: The following files do not exist:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
fi
echo -e "${GREEN}  ✓ All files found${NC}"

# -----------------------------------------------------------------------------
# Create tar.gz for Linux/Mac
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Creating ${TAR_FILE}...${NC}"

# Use syntax compatible with BSD tar (macOS) and GNU tar (Linux)
if tar -czvf "${DIST_DIR}/${TAR_FILE}" \
    --exclude '.venv' \
    --exclude '.env' \
    --exclude '__pycache__' \
    --exclude '.claude' \
    --exclude '.DS_Store' \
    --exclude 'venv' \
    --exclude '*.pyc' \
    --exclude 'logs' \
    --exclude 'chroma_db' \
    --exclude 'audit_log.jsonl' \
    --exclude 'authorships_cache.json' \
    "${FILES_TO_INCLUDE[@]}"; then
    echo -e "${GREEN}  ✓ ${TAR_FILE} created${NC}"
else
    echo -e "${RED}  ✗ Error creating ${TAR_FILE}${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Create zip for Windows
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Creating ${ZIP_FILE}...${NC}"

# Remove previous zip if exists
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
    -x "*/logs/*" \
    -x "*/chroma_db/*" \
    -x "*/audit_log.jsonl" \
    -x "*/authorships_cache.json"; then
    echo -e "${GREEN}  ✓ ${ZIP_FILE} created${NC}"
else
    echo -e "${RED}  ✗ Error creating ${ZIP_FILE}${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Final summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}=============================================="
echo "           Distribution completed            "
echo "==============================================${NC}"
echo ""
echo "Files created in ${DIST_DIR}/:"
echo ""
ls -lh "${DIST_DIR}/${TAR_FILE}" "${DIST_DIR}/${ZIP_FILE}" 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo ""

# .env.template cleanup is done automatically via trap EXIT
