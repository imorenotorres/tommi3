"""
Prueba - Agente Text-to-SQL
Convierte preguntas en lenguaje natural a consultas SQL usando Mistral Large.
Soporta Mistral Cloud, Ollama y vLLM via LLM_PROVIDER.
"""

import os
import sys
import sqlite3
import logging
import subprocess

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))

# Ruta al script consultar_sql.py
APPS_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
CONSULTAR_SQL_PATH = os.path.join(APPS_DIR, "consultar_sql.py")
from llm_client import LLMClient

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("prueba")


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = """You are Prueba, a database assistant specialized in converting natural language questions to SQL queries.

IMPORTANT RULES:
1. You help users query a SQLite database by understanding their questions in natural language
2. When the user asks about data, you will receive the database schema and query results
3. Explain the results clearly and concisely in the user\'s language
4. If you cannot answer a question with the available data, explain why
5. Never make up data - only use the actual query results provided

RESPONSE FORMAT:
- Provide only data, do not be conversational
- When presenting data, use tables or lists for clarity
- If the query returned no results, explain what that means
- Suggest related questions the user might want to ask"""
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")

        # Cliente local (Ollama) para formatear resultados
        # Usa LOCAL_LLM_* vars, con fallback a OLLAMA_* vars
        self.local_client = self._init_local_client()
        self.local_model = os.getenv("LOCAL_LLM_MODEL", os.getenv("OLLAMA_MODEL", "mistral"))

    def _init_local_client(self):
        """Inicializa un cliente Ollama local para formatear resultados."""
        try:
            import ollama
            # Prioriza LOCAL_LLM_BASE_URL, luego OLLAMA_BASE_URL
            base_url = os.getenv("LOCAL_LLM_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
            logger.info(f"🏠 Conectando a LLM local en {base_url}...")
            return ollama.Client(host=base_url)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo inicializar cliente local Ollama: {e}")
            return None

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "")
        elif provider == "vllm":
            return os.getenv("VLLM_MODEL", "")
        return ""

    def _get_db_schema(self) -> str:
        """Obtiene el esquema completo de la base de datos."""
        if not os.path.exists(self.db_path):
            return "ERROR: Base de datos no encontrada en data/database.db"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Obtener todas las tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = cursor.fetchall()

            if not tables:
                conn.close()
                return "La base de datos está vacía (no hay tablas)."

            schema_parts = ["ESQUEMA DE LA BASE DE DATOS:"]
            schema_parts.append("=" * 40)

            for (table_name,) in tables:
                schema_parts.append(f"
Tabla: {table_name}")
                schema_parts.append("-" * 20)

                # Obtener estructura de la tabla
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()

                for col in columns:
                    col_id, name, col_type, not_null, default, pk = col
                    constraints = []
                    if pk:
                        constraints.append("PRIMARY KEY")
                    if not_null:
                        constraints.append("NOT NULL")
                    constraint_str = f" ({', '.join(constraints)})" if constraints else ""
                    schema_parts.append(f"  - {name}: {col_type}{constraint_str}")

                # Obtener número de filas
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                row_count = cursor.fetchone()[0]
                schema_parts.append(f"  [{row_count} filas]")

            conn.close()
            return "
".join(schema_parts)

        except sqlite3.Error as e:
            return f"Error leyendo esquema: {str(e)}"

    def _text_to_sql(self, user_question: str, schema: str) -> str:
        """Usa el LLM para convertir una pregunta en lenguaje natural a SQL."""
        logger.info(f"🔄 Convirtiendo pregunta a SQL: {user_question[:50]}...")

        conversion_prompt = f"""Eres un experto en SQL. Tu tarea es convertir la siguiente pregunta en lenguaje natural a una consulta SQL válida para SQLite.

{schema}

REGLAS IMPORTANTES:
1. Genera SOLO la consulta SQL, sin explicaciones
2. Solo genera consultas SELECT (lectura)
3. La consulta debe ser válida para SQLite
4. Si la pregunta no puede responderse con los datos disponibles, responde: ERROR: [explicación]
5. Usa nombres de columnas y tablas EXACTAMENTE como aparecen en el esquema

PREGUNTA DEL USUARIO:
{user_question}

CONSULTA SQL:"""

        messages = [{"role": "user", "content": conversion_prompt}]

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        sql = response.choices[0].message.content.strip()

        # Limpiar la respuesta (quitar bloques de código markdown si los hay)
        if sql.startswith("```"):
            lines = sql.split("
")
            sql = "
".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        sql = sql.strip()
        logger.info(f"📝 SQL generado: {sql}")
        return sql

    def _execute_sql(self, query: str) -> tuple:
        """
        Ejecuta una consulta SQL y devuelve (éxito, resultado).
        resultado es una lista de diccionarios si éxito, o mensaje de error si falla.
        """
        logger.info(f"⚡ Ejecutando SQL...")

        # Validación de seguridad básica
        query_upper = query.strip().upper()

        # Verificar si es un error del LLM
        if query_upper.startswith("ERROR:"):
            return (False, query)

        # Solo permitir SELECT
        if not query_upper.startswith("SELECT"):
            return (False, "Solo se permiten consultas SELECT.")

        # Palabras prohibidas
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC", "--"]
        for word in forbidden:
            if word in query_upper:
                return (False, f"Operación '{word}' no permitida por seguridad.")

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return (True, [])

            # Convertir a lista de diccionarios
            columns = rows[0].keys()
            results = [dict(row) for row in rows]

            logger.info(f"✅ Consulta exitosa: {len(results)} filas")
            return (True, results)

        except sqlite3.Error as e:
            logger.error(f"❌ Error SQL: {str(e)}")
            return (False, f"Error SQL: {str(e)}")

    def _format_results(self, user_question: str, sql_query: str, results: list, success: bool) -> str:
        """Usa el LLM LOCAL (Ollama) para formatear los resultados de manera amigable."""
        logger.info("📊 Formateando resultados con LLM local...")

        if not success:
            # results contiene el mensaje de error
            format_prompt = f"""El usuario preguntó: "{user_question}"

Se intentó ejecutar esta consulta SQL: {sql_query}

Pero ocurrió un error: {results}

Por favor, explica al usuario qué salió mal de manera amigable y sugiere cómo podría reformular su pregunta."""

        elif not results:
            format_prompt = f"""El usuario preguntó: "{user_question}"

Se ejecutó esta consulta SQL: {sql_query}

The query returned no results.

Por favor, informa al usuario de manera amigable que no se encontraron datos que coincidan con su búsqueda."""

        else:
            # Limitar resultados para no exceder contexto
            display_results = results[:100]
            truncated = len(results) > 100

            format_prompt = f"""El usuario preguntó: "{user_question}"

Se ejecutó esta consulta SQL: {sql_query}

Resultados ({len(results)} filas{"(mostrando primeras 100)" if truncated else ""}):
{display_results}

Por favor, presenta estos resultados al usuario de manera clara y amigable:
- Usa formato de tabla markdown si es apropiado
- Resume los puntos clave
- Responde directamente a la pregunta del usuario
- Si hay muchos datos, destaca los más relevantes"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": format_prompt}
        ]

        # Usar cliente local (Ollama) para formatear
        if self.local_client:
            try:
                logger.info(f"🏠 Usando Ollama local ({self.local_model}) para formatear...")
                response = self.local_client.chat(
                    model=self.local_model,
                    messages=messages
                )
                return response["message"]["content"]
            except Exception as e:
                logger.warning(f"⚠️ Error con LLM local, usando cliente principal: {e}")

        # Fallback al cliente principal si el local no está disponible
        logger.info("🌐 Usando cliente principal para formatear...")
        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content

    def _format_as_html_table(self, results: list) -> str:
        """Formatea los resultados JSON como una tabla HTML interactiva."""
        if not results:
            return "<p><em>No results</em></p>"

        import json as json_module
        columns = list(results[0].keys())

        html = """<div class="sql-results" style="margin: 15px 0;">
<style>
.sql-table { border-collapse: collapse; width: 100%; font-size: 14px; }
.sql-table th { background: #2c3e50; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }
.sql-table td { padding: 8px 12px; border-bottom: 1px solid #eee; }
.sql-table tr:hover { background: #f5f5f5; }
.sql-table tr:nth-child(even) { background: #fafafa; }
.sql-table .number { text-align: right; font-family: monospace; }
.sql-table .null { color: #999; font-style: italic; }
.sql-stats { margin-bottom: 10px; color: #666; font-size: 13px; }
</style>
<div class="sql-stats">Resultados: <strong>{row_count}</strong> filas</div>
<div style="overflow-x: auto;">
<table class="sql-table">
<thead><tr>{headers}</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
</div>"""

        headers = "".join(f"<th>{col}</th>" for col in columns)

        rows_html = []
        for row in results[:100]:  # Limitar a 100 filas
            cells = []
            for col in columns:
                val = row.get(col)
                if val is None:
                    cells.append('<td class="null">NULL</td>')
                elif isinstance(val, (int, float)):
                    cells.append(f'<td class="number">{val}</td>')
                else:
                    escaped = str(val).replace("<", "&lt;").replace(">", "&gt;")
                    cells.append(f"<td>{escaped}</td>")
            rows_html.append(f"<tr>{''.join(cells)}</tr>")

        return html.format(
            row_count=len(results),
            headers=headers,
            rows="
".join(rows_html)
        )

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Procesa una pregunta del usuario:
        1. Obtiene el esquema de la BD
        2. Convierte la pregunta a SQL
        3. Ejecuta el SQL usando consultar_sql.py
        4. Muestra los resultados en tabla HTML inline
        5. Formatea y devuelve los resultados
        """
        logger.info(f"📩 Usuario: {user_message}")

        # Verificar que existe la BD
        if not os.path.exists(self.db_path):
            return "⚠️ **Base de datos no encontrada**

Por favor, crea una base de datos SQLite en `data/database.db`.

Ejemplo:
```bash
sqlite3 data/database.db < tu_schema.sql
```"

        # Paso 1: Obtener esquema
        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            return f"⚠️ {schema}"

        # Paso 2: Convertir texto a SQL
        sql_query = self._text_to_sql(user_message, schema)

        # Validar que no sea un error del LLM
        if sql_query.strip().upper().startswith("ERROR:"):
            return f"⚠️ {sql_query}"

        # Paso 3: Ejecutar SQL usando consultar_sql.py
        try:
            logger.info(f"⚡ Ejecutando consultar_sql.py...")

            # Llamar a consultar_sql.py con --json
            consultar_result = subprocess.run(
                [sys.executable, CONSULTAR_SQL_PATH, self.db_path, sql_query, "--json"],
                capture_output=True,
                text=True
            )

            if consultar_result.returncode != 0:
                error_msg = consultar_result.stderr or "Error desconocido"
                logger.error(f"❌ Error en consultar_sql.py: {error_msg}")
                return f"⚠️ Error ejecutando consulta: {error_msg}"

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            # Parsear JSON y generar tabla HTML
            import json as json_module
            results = json_module.loads(json_output)
            html_table = self._format_as_html_table(results)

            logger.info(f"📊 Tabla HTML generada con {len(results)} filas")

        except Exception as e:
            logger.error(f"❌ Error ejecutando consultar_sql.py: {str(e)}")
            # Fallback: ejecutar SQL internamente
            success, results = self._execute_sql(sql_query)
            if success:
                html_table = self._format_as_html_table(results)
            else:
                return f"⚠️ Error: {str(e)}"

        # Paso 4: Formatear explicación con LLM
        success, results = self._execute_sql(sql_query)
        formatted = self._format_results(user_message, sql_query, results, success)

        # Paso 5: Combinar explicación + tabla HTML
        return f"{formatted}

{html_table}"

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Versión streaming - emite eventos de estado y contenido.
        """
        logger.info(f"📩 [STREAM] Usuario: {user_message}")

        # Verificar BD
        if not os.path.exists(self.db_path):
            yield ("content", "⚠️ **Base de datos no encontrada**

Crea una base de datos SQLite en `data/database.db`.")
            return

        # Emitir estados
        yield ("status", "Analizando esquema de la base de datos...")
        schema = self._get_db_schema()

        yield ("status", "Convirtiendo pregunta a SQL...")
        sql_query = self._text_to_sql(user_message, schema)

        # Validar que no sea un error del LLM
        if sql_query.strip().upper().startswith("ERROR:"):
            yield ("content", f"⚠️ {sql_query}")
            return

        yield ("status", "Ejecutando consulta con consultar_sql.py...")

        # Ejecutar SQL usando consultar_sql.py
        html_table = ""
        try:
            # Llamar a consultar_sql.py con --json
            consultar_result = subprocess.run(
                [sys.executable, CONSULTAR_SQL_PATH, self.db_path, sql_query, "--json"],
                capture_output=True,
                text=True
            )

            if consultar_result.returncode != 0:
                error_msg = consultar_result.stderr or "Error desconocido"
                logger.error(f"❌ Error en consultar_sql.py: {error_msg}")
                yield ("content", f"⚠️ Error ejecutando consulta: {error_msg}")
                return

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            yield ("status", "Generating results table...")

            # Parsear JSON y generar tabla HTML
            import json as json_module
            results = json_module.loads(json_output)
            html_table = self._format_as_html_table(results)

            logger.info(f"📊 Tabla HTML generada con {len(results)} filas")

        except Exception as e:
            logger.error(f"❌ Error ejecutando consultar_sql.py: {str(e)}")
            # Fallback: ejecutar SQL internamente
            success, results = self._execute_sql(sql_query)
            if success:
                html_table = self._format_as_html_table(results)
            else:
                yield ("content", f"⚠️ Error: {str(e)}")
                return

        yield ("status", "Formateando explicación...")
        success, results = self._execute_sql(sql_query)
        formatted = self._format_results(user_message, sql_query, results, success)

        # Combinar explicación + tabla HTML
        yield ("content", f"{formatted}

{html_table}")

    def get_schema(self) -> str:
        """Devuelve el esquema de la BD (útil para debugging/API)."""
        return self._get_db_schema()
