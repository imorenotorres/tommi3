#!/bin/bash
# OpenAlex Collector Runner
# Ejecuta el script de recolección de papers desde cualquier ubicación
#
# Uso:
#   ./openalex_collector.sh collect  -t TOPICS [-o DIR] [-m N] [-u UNI] [--continue]  # Paso 1: genera CSV para revisión
#   ./openalex_collector.sh download [-o DIR] [--csv P]                     # Paso 2: descarga papers del CSV revisado
#   ./openalex_collector.sh discover [-o DIR]                               # Solo descubre IDs de instituciones
#
# Ejemplo:
#   ./openalex_collector.sh collect -t topics_THUAS_ResponsibleAI.txt -m 0   # sin límite de papers por partner

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ] && [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  collect    Step 1: query OpenAlex and generate a CSV for manual review (requires -t TOPICS)"
    echo "  download   Step 2: download PDFs for papers marked 'keep=yes' in the reviewed CSV"
    echo "  discover   Only discover and cache OpenAlex institution IDs"
    echo ""
    echo "Run '$0 <command> --help' for more options."
    exit 1
fi

"$PROJECT_ROOT/.venv/bin/python" "$SCRIPT_DIR/openalex_collector.py" "$@"
