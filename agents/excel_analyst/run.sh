#!/bin/bash
# Start Liana's Assistant (ExcelAnalyst agent)
cd "$(dirname "$0")"

# Create venv if needed
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

PORT=${PORT:-8000}
echo "Starting Liana's Assistant on port $PORT..."
python app.py
