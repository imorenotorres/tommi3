#!/bin/bash
# Sonic Pi Bridge — double-click to start (Mac)
cd "$(dirname "$0")"

echo ""
echo "  ==============================="
echo "   Sonic Pi Bridge"
echo "  ==============================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "  ERROR: Python 3 not found. Install it from python.org"
    echo ""; read -p "  Press Enter to exit..."
    exit 1
fi

# Create venv if needed
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment (first time only)..."
    python3 -m venv .venv
fi

# Install python-sonic if needed
.venv/bin/python3 -c "import psonic" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  Installing python-sonic..."
    .venv/bin/pip install python-sonic --quiet
fi

echo "  Starting bridge..."
echo ""
.venv/bin/python3 sonic_bridge.py
