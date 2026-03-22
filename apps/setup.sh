#!/bin/bash

# =============================================================================
# TOMMI - Setup Script
# =============================================================================
# This script configures the environment after extracting the installation file
# Compatible with Linux (Debian/Ubuntu, RHEL/CentOS, Arch) and macOS
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# =============================================================================
# Auto-fix for files that passed through Windows
# =============================================================================
fix_line_endings_and_permissions() {
    local fixed_crlf=false
    local fixed_perms=false

    # Find all .sh scripts in the project
    while IFS= read -r -d '' script; do
        # Ignore .venv and __pycache__
        if [[ "$script" == *"/.venv/"* ]] || [[ "$script" == *"__pycache__"* ]]; then
            continue
        fi

        # Check and fix CRLF line endings
        if file "$script" 2>/dev/null | grep -q "CRLF"; then
            # Use perl which works the same on macOS and Linux
            if command -v perl &> /dev/null; then
                perl -pi -e 's/\r$//' "$script" 2>/dev/null
                fixed_crlf=true
            fi
        fi

        # Restore execution permissions if missing
        if [ ! -x "$script" ]; then
            chmod +x "$script" 2>/dev/null || true
            fixed_perms=true
        fi
    done < <(find . -name "*.sh" -type f -print0 2>/dev/null)

    # Show message only if corrections were made
    if [ "$fixed_crlf" = true ] || [ "$fixed_perms" = true ]; then
        echo -e "${YELLOW}Auto-fix applied:${NC}"
        [ "$fixed_crlf" = true ] && echo -e "  → CRLF line endings fixed"
        [ "$fixed_perms" = true ] && echo -e "  → Execution permissions restored"
        echo ""
    fi
}

# Run auto-fix silently
fix_line_endings_and_permissions

echo -e "${BLUE}"
echo "=============================================="
echo "         TOMMI - Initial Setup               "
echo "=============================================="
echo -e "${NC}"

# Detect operating system
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
echo -e "  Detected system: ${GREEN}$OS_TYPE${NC}"

# -----------------------------------------------------------------------------
# 0. Verify system dependencies
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[0/7] Verifying system dependencies...${NC}"

# Verify that Python3 exists
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  ✗ Python3 is not installed${NC}"
    case $OS_TYPE in
        debian)
            echo -e "${YELLOW}    Install with: sudo apt update && sudo apt install python3 python3-pip python3-venv${NC}"
            ;;
        redhat)
            echo -e "${YELLOW}    Install with: sudo dnf install python3 python3-pip${NC}"
            ;;
        arch)
            echo -e "${YELLOW}    Install with: sudo pacman -S python python-pip${NC}"
            ;;
        macos)
            echo -e "${YELLOW}    Install with: brew install python3${NC}"
            ;;
    esac
    exit 1
fi

# Verify that venv module is available
if ! python3 -c "import venv" 2>/dev/null; then
    echo -e "${RED}  ✗ The 'venv' module is not installed${NC}"
    case $OS_TYPE in
        debian)
            echo -e "${YELLOW}    Install with: sudo apt install python3-venv${NC}"
            ;;
        redhat)
            echo -e "${YELLOW}    Install with: sudo dnf install python3-libs${NC}"
            ;;
        arch)
            echo -e "${YELLOW}    The venv module should be included in python${NC}"
            ;;
        macos)
            echo -e "${YELLOW}    The venv module should be included in python3${NC}"
            ;;
    esac
    exit 1
fi

echo -e "${GREEN}  ✓ System dependencies verified${NC}"

# -----------------------------------------------------------------------------
# 1. Detect compatible Python version
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/7] Detecting compatible Python version...${NC}"

# Detect if there are RAG agents (require Python 3.11-3.13)
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

# Find compatible Python
PYTHON_CMD=""
if [ "$HAS_RAG_AGENTS" = true ]; then
    echo -e "  → RAG/RAG+Metadata agents detected (require Python 3.11-3.13)"
    # RAG agents: find Python 3.11-3.13 (ChromaDB not compatible with 3.14+)
    for cmd in python3.12 python3.13 python3.11; do
        if command -v $cmd &> /dev/null; then
            PYTHON_CMD=$cmd
            break
        fi
    done
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}  ⚠️  WARNING: Python 3.11-3.13 not found${NC}"
        echo -e "${RED}     RAG agents will not work with Python 3.14+${NC}"
        case $OS_TYPE in
            debian)
                echo -e "${YELLOW}     Install Python 3.12: sudo apt install python3.12 python3.12-venv${NC}"
                ;;
            redhat)
                echo -e "${YELLOW}     Install Python 3.12: sudo dnf install python3.12${NC}"
                ;;
            macos)
                echo -e "${YELLOW}     Install Python 3.12: brew install python@3.12${NC}"
                ;;
            *)
                echo -e "${YELLOW}     Install Python 3.12 from your package manager${NC}"
                ;;
        esac
        echo ""
        read -p "  Continue with python3 anyway? [y/N]: " CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            exit 1
        fi
        PYTHON_CMD="python3"
    fi
else
    PYTHON_CMD="python3"
fi

echo -e "${GREEN}  → Using: $PYTHON_CMD ($(${PYTHON_CMD} --version 2>&1))${NC}"

# -----------------------------------------------------------------------------
# 2. Create virtual environment
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/7] Creating virtual environment .venv...${NC}"

if [ -d ".venv" ]; then
    echo -e "${GREEN}  → Virtual environment already exists in .venv/${NC}"
else
    echo "  → Creating virtual environment with $PYTHON_CMD..."
    if ! $PYTHON_CMD -m venv .venv; then
        echo -e "${RED}  ✗ Error creating virtual environment${NC}"
        # Determine the correct venv package based on Python version
        PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        case $OS_TYPE in
            debian)
                echo -e "${YELLOW}    Try: sudo apt install python${PYTHON_VERSION}-venv${NC}"
                ;;
            *)
                echo -e "${YELLOW}    Verify that the venv module is installed for Python ${PYTHON_VERSION}${NC}"
                ;;
        esac
        exit 1
    fi
    echo -e "${GREEN}  → Virtual environment created in .venv/${NC}"
fi

# -----------------------------------------------------------------------------
# 3. Activate virtual environment
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/7] Activating virtual environment...${NC}"

if [ ! -f ".venv/bin/activate" ]; then
    echo -e "${RED}  ✗ .venv/bin/activate not found${NC}"
    echo -e "${YELLOW}    Delete .venv/ and run the script again${NC}"
    exit 1
fi

source .venv/bin/activate
echo -e "${GREEN}  → Environment activated: $(which python)${NC}"

# -----------------------------------------------------------------------------
# 4. Install dependencies
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/7] Installing dependencies...${NC}"

# Update pip (use python from venv, not system python3)
echo "  → Updating pip..."
python -m pip install --upgrade pip -q 2>/dev/null || {
    echo -e "${YELLOW}  → Installing pip in the virtual environment...${NC}"
    python -m ensurepip --upgrade 2>/dev/null || true
    python -m pip install --upgrade pip -q
}

# Install web requirements
if [ -f "web/requirements.txt" ]; then
    echo "  → Installing web requirements..."
    if ! python -m pip install -r web/requirements.txt -q; then
        echo -e "${RED}  ✗ Error installing dependencies${NC}"
        echo -e "${YELLOW}    Some dependencies may require compilation.${NC}"
        PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        case $OS_TYPE in
            debian)
                echo -e "${YELLOW}    Try: sudo apt install build-essential python${PYTHON_VERSION}-dev${NC}"
                ;;
            redhat)
                echo -e "${YELLOW}    Try: sudo dnf install gcc python${PYTHON_VERSION}-devel${NC}"
                ;;
        esac
        exit 1
    fi
    echo -e "${GREEN}  → Web requirements installed${NC}"
else
    echo -e "${YELLOW}  → web/requirements.txt not found${NC}"
fi

# -----------------------------------------------------------------------------
# 5. Configure conversation logging
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/7] Configuring conversation logging...${NC}"
echo ""
echo -e "  ${BLUE}Do you want to enable conversation logging?${NC}"
echo -e "  (Useful for testing. Logs are saved to web/logs/conversations.log)"
echo ""
read -p "  Enable logging [y/N]: " ENABLE_LOG

# Save logging preference to write at the end
if [[ "$ENABLE_LOG" =~ ^[Yy]$ ]]; then
    LOGGING_VALUE="true"
    echo -e "${GREEN}  → Logging enabled${NC}"
else
    LOGGING_VALUE="false"
    echo -e "${GREEN}  → Logging disabled${NC}"
fi

# -----------------------------------------------------------------------------
# 6. Configure Mistral API key (saved only in web/.env)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[6/7] Configuring Mistral API key...${NC}"
echo ""

# Detect agent folders to show information
AGENT_DIRS=()
if [ -d "agents" ]; then
    for dir in agents/*/; do
        dir_name="${dir%/}"
        # Verify it has agent.py (is a valid agent)
        if [ -f "$dir_name/agent.py" ]; then
            AGENT_DIRS+=("$dir_name")
        fi
    done
fi

API_KEY=""
if [ ${#AGENT_DIRS[@]} -eq 0 ]; then
    echo -e "${YELLOW}  → No agent folders found${NC}"
else
    echo "  Agents detected: ${#AGENT_DIRS[@]}"
    echo ""

    # Ask for API key
    echo -e "${BLUE}  Enter your Mistral API key:${NC}"
    echo -e "  (You can get it at https://console.mistral.ai/api-keys)"
    echo ""
    read -p "  MISTRAL_API_KEY: " API_KEY

    if [ -z "$API_KEY" ]; then
        echo -e "${YELLOW}  → No API key provided. You can configure it manually in web/.env${NC}"
    else
        echo -e "${GREEN}  → API key configured (will be saved to web/.env)${NC}"
    fi
fi

# NOTE: All agents use the default configuration from web/.env.
# Agents can override this configuration in their own .env if needed.

# -----------------------------------------------------------------------------
# 7. Create web/.env configuration file
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[7/7] Creating web/.env configuration file...${NC}"

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

echo -e "${GREEN}  → web/.env file created${NC}"

# -----------------------------------------------------------------------------
# Final summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}=============================================="
echo "            Setup completed                   "
echo "==============================================${NC}"
echo ""
echo "To start the web server:"
echo -e "  ${GREEN}cd ..${NC}"
echo -e "  ${GREEN}cd web${NC}"
echo -e "  ${GREEN}./run_html_server.sh${NC}"
echo ""
