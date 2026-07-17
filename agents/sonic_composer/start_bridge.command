#!/bin/bash
# Sonic Pi Bridge — double-click to start (Mac)
cd "$(dirname "$0")"

echo ""
echo "  Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "  ERROR: Python 3 not found. Install it from python.org"
    echo ""; read -p "  Press Enter to exit..."
    exit 1
fi

echo "  Checking python-sonic..."
python3 -c "import psonic" 2>/dev/null || python3 -m pip install python-sonic --quiet

echo "  Starting bridge..."
echo ""
python3 sonic_bridge.py
