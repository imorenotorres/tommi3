#!/usr/bin/env python3
"""
Muestra datos JSON en una página web interactiva.

Uso:
    python ver_json.py <archivo.json>
    python ver_json.py -                     # Lee de stdin
    cat datos.json | python ver_json.py -
    python consultar_sql.py db.db "SELECT *" --json | python ver_json.py -

Opciones:
    -p, --port PORT    Puerto del servidor (default: 8080)
    --no-open          No abrir navegador automáticamente
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from venv_helper import ensure_venv
ensure_venv()
import json
import argparse
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs
import threading

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visor de Datos</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            color: #333;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #2c3e50; }
        .stats {
            background: #fff;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stats span { margin-right: 20px; color: #666; }
        .stats strong { color: #2c3e50; }
        .search-box {
            width: 100%;
            padding: 12px 16px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            margin-bottom: 20px;
            outline: none;
            transition: border-color 0.2s;
        }
        .search-box:focus { border-color: #3498db; }
        .table-container {
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        table { width: 100%; border-collapse: collapse; }
        th {
            background: #2c3e50;
            color: #fff;
            padding: 14px 12px;
            text-align: left;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            position: relative;
        }
        th:hover { background: #34495e; }
        th .sort-icon { margin-left: 8px; opacity: 0.5; }
        th.sorted .sort-icon { opacity: 1; }
        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        td:hover { white-space: normal; word-break: break-all; }
        tr:hover { background: #f8f9fa; }
        tr:nth-child(even) { background: #fafafa; }
        tr:nth-child(even):hover { background: #f0f0f0; }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        .number { text-align: right; font-family: monospace; }
        .null { color: #999; font-style: italic; }
        .export-btn {
            background: #3498db;
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
        }
        .export-btn:hover { background: #2980b9; }
        .toolbar { display: flex; align-items: center; margin-bottom: 20px; }
        .toolbar .search-box { flex: 1; margin-bottom: 0; margin-right: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Visor de Datos</h1>
        <div class="stats">
            <span>Total: <strong id="total">0</strong> filas</span>
            <span>Mostrando: <strong id="showing">0</strong></span>
            <span>Columnas: <strong id="columns">0</strong></span>
        </div>
        <div class="toolbar">
            <input type="text" class="search-box" id="search" placeholder="Buscar en todos los campos...">
            <button class="export-btn" onclick="exportCSV()">Exportar CSV</button>
            <button class="export-btn" onclick="exportJSON()">Exportar JSON</button>
        </div>
        <div class="table-container">
            <table id="dataTable">
                <thead><tr id="headerRow"></tr></thead>
                <tbody id="dataBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        const DATA = __DATA_PLACEHOLDER__;
        let sortColumn = null;
        let sortAsc = true;
        let filteredData = [...DATA];

        function init() {
            if (!DATA.length) {
                document.getElementById('dataBody').innerHTML = '<tr><td class="no-data" colspan="100">Sin datos</td></tr>';
                return;
            }

            const columns = Object.keys(DATA[0]);
            document.getElementById('columns').textContent = columns.length;
            document.getElementById('total').textContent = DATA.length;

            // Header
            const headerRow = document.getElementById('headerRow');
            headerRow.innerHTML = columns.map(col =>
                `<th onclick="sortBy('${col}')">${col}<span class="sort-icon">⇅</span></th>`
            ).join('');

            renderData(DATA);

            // Search
            document.getElementById('search').addEventListener('input', (e) => {
                const term = e.target.value.toLowerCase();
                filteredData = DATA.filter(row =>
                    Object.values(row).some(v =>
                        String(v).toLowerCase().includes(term)
                    )
                );
                renderData(filteredData);
            });
        }

        function renderData(data) {
            document.getElementById('showing').textContent = data.length;
            const columns = DATA.length ? Object.keys(DATA[0]) : [];
            const tbody = document.getElementById('dataBody');

            if (!data.length) {
                tbody.innerHTML = '<tr><td class="no-data" colspan="100">Sin resultados</td></tr>';
                return;
            }

            tbody.innerHTML = data.map(row =>
                '<tr>' + columns.map(col => {
                    const val = row[col];
                    if (val === null) return '<td class="null">NULL</td>';
                    if (typeof val === 'number') return `<td class="number">${val}</td>`;
                    return `<td title="${String(val).replace(/"/g, '&quot;')}">${val}</td>`;
                }).join('') + '</tr>'
            ).join('');
        }

        function sortBy(column) {
            if (sortColumn === column) {
                sortAsc = !sortAsc;
            } else {
                sortColumn = column;
                sortAsc = true;
            }

            filteredData.sort((a, b) => {
                let va = a[column], vb = b[column];
                if (va === null) return 1;
                if (vb === null) return -1;
                if (typeof va === 'number' && typeof vb === 'number') {
                    return sortAsc ? va - vb : vb - va;
                }
                return sortAsc
                    ? String(va).localeCompare(String(vb))
                    : String(vb).localeCompare(String(va));
            });

            // Update header
            document.querySelectorAll('th').forEach(th => th.classList.remove('sorted'));
            event.target.closest('th').classList.add('sorted');

            renderData(filteredData);
        }

        function exportCSV() {
            if (!filteredData.length) return;
            const columns = Object.keys(DATA[0]);
            const csv = [
                columns.join(','),
                ...filteredData.map(row =>
                    columns.map(c => {
                        const v = row[c];
                        if (v === null) return '';
                        if (typeof v === 'string' && (v.includes(',') || v.includes('"'))) {
                            return '"' + v.replace(/"/g, '""') + '"';
                        }
                        return v;
                    }).join(',')
                )
            ].join('\\n');
            download('datos.csv', csv, 'text/csv');
        }

        function exportJSON() {
            download('datos.json', JSON.stringify(filteredData, null, 2), 'application/json');
        }

        function download(filename, content, type) {
            const blob = new Blob([content], { type });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }

        init();
    </script>
</body>
</html>
'''


class DataHandler(SimpleHTTPRequestHandler):
    """Handler que sirve la página con los datos."""

    html_content = ""

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(self.html_content.encode('utf-8'))

    def log_message(self, format, *args):
        pass  # Silenciar logs


def main():
    parser = argparse.ArgumentParser(
        description="Muestra datos JSON en una página web interactiva",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s datos.json
  %(prog)s -                                    # Lee de stdin
  python consultar_sql.py db.db "SELECT *" --json | %(prog)s -
        """
    )

    parser.add_argument("input", help="Archivo JSON o '-' para stdin")
    parser.add_argument("-p", "--port", type=int, default=8080, help="Puerto (default: 8080)")
    parser.add_argument("--no-open", action="store_true", help="No abrir navegador")

    args = parser.parse_args()

    # Leer datos
    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)

    # Asegurar que es una lista
    if isinstance(data, dict):
        data = [data]

    # Generar HTML
    html = HTML_TEMPLATE.replace('__DATA_PLACEHOLDER__', json.dumps(data, ensure_ascii=False))
    DataHandler.html_content = html

    # Iniciar servidor
    server = HTTPServer(('localhost', args.port), DataHandler)
    url = f"http://localhost:{args.port}"

    print(f"Servidor iniciado en {url}")
    print(f"Mostrando {len(data)} registros")
    print("Presiona Ctrl+C para salir")

    # Abrir navegador
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")


if __name__ == "__main__":
    main()
