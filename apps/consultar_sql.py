#!/usr/bin/env python3
"""
Consulta una base de datos SQLite y devuelve los resultados.

Uso:
    python consultar_sql.py <database.db> <query>
    python consultar_sql.py <database.db> -f <archivo.sql>

Ejemplos:
    python consultar_sql.py datos.db "SELECT * FROM usuarios"
    python consultar_sql.py datos.db "SELECT nombre, edad FROM usuarios WHERE edad > 18"
    python consultar_sql.py datos.db -f consulta.sql

Opciones de formato:
    --json     Salida en formato JSON
    --csv      Salida en formato CSV
    --table    Salida en formato tabla (por defecto)
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from venv_helper import ensure_venv
ensure_venv()
import sqlite3
import json
import argparse
import re


def clean_sql_query(query: str) -> str:
    """
    Limpia una consulta SQL:
    1. Elimina comentarios de bloque /* ... */
    2. Elimina comentarios de línea -- ...
    3. Toma solo la primera sentencia SQL (antes del primer ;)
    4. Limpia espacios múltiples
    """
    # Eliminar comentarios de bloque /* ... */
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    # Eliminar comentarios de línea -- ...
    query = re.sub(r'--.*?(?:\n|$)', ' ', query)
    # Limpiar espacios múltiples y saltos de línea
    query = re.sub(r'\s+', ' ', query).strip()
    # Tomar solo la primera sentencia (antes del primer ;)
    if ';' in query:
        query = query.split(';')[0].strip()
    return query


def execute_query(db_path: str, query: str) -> tuple:
    """
    Ejecuta una consulta SQL y devuelve (columnas, filas).
    """
    # Limpiar la consulta (comentarios, múltiples sentencias)
    query = clean_sql_query(query)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query)

    rows = cursor.fetchall()
    columns = rows[0].keys() if rows else []

    # Convertir a lista de diccionarios
    results = [dict(row) for row in rows]

    conn.close()
    return columns, results


def format_table(columns: list, rows: list) -> str:
    """Formatea resultados como tabla."""
    if not rows:
        return "(sin resultados)"

    # Calcular anchos de columna
    widths = {col: len(str(col)) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ''))))

    # Construir tabla
    lines = []

    # Encabezado
    header = " | ".join(str(col).ljust(widths[col]) for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    # Filas
    for row in rows:
        line = " | ".join(str(row.get(col, '')).ljust(widths[col]) for col in columns)
        lines.append(line)

    lines.append(f"\n({len(rows)} filas)")
    return "\n".join(lines)


def format_csv(columns: list, rows: list) -> str:
    """Formatea resultados como CSV."""
    if not rows:
        return ""

    lines = [",".join(str(col) for col in columns)]
    for row in rows:
        lines.append(",".join(str(row.get(col, '')) for col in columns))

    return "\n".join(lines)


def format_json(columns: list, rows: list) -> str:
    """Formatea resultados como JSON."""
    return json.dumps(rows, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Consulta una base de datos SQLite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s datos.db "SELECT * FROM usuarios"
  %(prog)s datos.db "SELECT * FROM productos WHERE precio > 100" --json
  %(prog)s datos.db -f consulta.sql --csv
        """
    )

    parser.add_argument("database", help="Ruta a la base de datos SQLite")
    parser.add_argument("query", nargs="?", help="Consulta SQL a ejecutar")
    parser.add_argument("-f", "--file", help="Archivo con la consulta SQL")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--csv", action="store_true", help="Salida en formato CSV")
    parser.add_argument("--table", action="store_true", help="Salida en formato tabla (default)")

    args = parser.parse_args()

    # Obtener la consulta
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            query = f.read().strip()
    elif args.query:
        query = args.query
    else:
        parser.error("Debes proporcionar una consulta SQL o un archivo con -f")

    try:
        columns, rows = execute_query(args.database, query)

        # Formatear salida
        if args.json:
            print(format_json(columns, rows))
        elif args.csv:
            print(format_csv(columns, rows))
        else:
            print(format_table(columns, rows))

    except sqlite3.Error as e:
        print(f"Error SQL: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: No se encuentra la base de datos '{args.database}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
