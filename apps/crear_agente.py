#!/usr/bin/env python3
"""
Script interactivo para crear agentes independientes con FastAPI + LLM.
Soporta Mistral Cloud y Ollama como proveedores de LLM.
No requiere tokki - es 100% standalone.
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from venv_helper import ensure_venv
ensure_venv()

import os
import sys
import json
import glob


def get_prompts_dir() -> str:
    """Obtiene la ruta de la carpeta de prompts."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(script_dir), "prompts")


def list_prompt_templates(agent_type: str) -> list:
    """
    Lista las plantillas de prompt disponibles para un tipo de agente.
    Busca archivos .txt en la carpeta prompts/ que coincidan con el tipo.

    Args:
        agent_type: Tipo de agente (oneshot, rag, consultabd_sql)

    Returns:
        Lista de tuplas (nombre_mostrar, ruta_archivo)
    """
    prompts_dir = get_prompts_dir()
    templates = []

    if not os.path.exists(prompts_dir):
        return templates

    # Mapeo de tipos a patrones de archivo (case-insensitive matching)
    type_patterns = {
        "oneshot": ["prompt_Oneshot.txt"],
        "rag": ["prompt_RAG.txt"],
        "consultabd_sql": ["prompt_Text2SQL.txt"]
    }

    # Primero añadir las plantillas específicas del tipo
    for pattern in type_patterns.get(agent_type, []):
        filepath = os.path.join(prompts_dir, pattern)
        if os.path.exists(filepath):
            name = os.path.splitext(os.path.basename(filepath))[0]
            templates.append((name, filepath))

    # Luego añadir otras plantillas .txt que no sean del tipo específico
    for filepath in glob.glob(os.path.join(prompts_dir, "*.txt")):
        name = os.path.splitext(os.path.basename(filepath))[0]
        # Evitar duplicados
        if not any(t[1] == filepath for t in templates):
            templates.append((name, filepath))

    return templates


def load_prompt_template(filepath: str, agent_name: str) -> str:
    """
    Carga una plantilla de prompt y reemplaza las variables.

    Args:
        filepath: Ruta al archivo de plantilla
        agent_name: Nombre del agente para sustituir {agent_name}

    Returns:
        Contenido del prompt con variables sustituidas
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Reemplazar variables
        content = content.replace("{agent_name}", agent_name)
        return content.strip()
    except Exception as e:
        print(f"  Error cargando plantilla: {e}")
        return ""

# ============================================================================
# PLANTILLAS
# ============================================================================

REQUIREMENTS_ONESHOT = """fastapi>=0.115.0
uvicorn>=0.32.0
mistralai>=1.0.0
ollama>=0.3.0
openai>=1.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
"""

REQUIREMENTS_RAG = """fastapi>=0.115.0
uvicorn>=0.32.0
mistralai>=1.0.0
ollama>=0.3.0
openai>=1.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
pypdf>=4.0.0
"""

REQUIREMENTS_CONSULTABD_SQL = """fastapi>=0.115.0
uvicorn>=0.32.0
mistralai>=1.0.0
ollama>=0.3.0
python-dotenv>=1.0.0
httpx>=0.27.0
"""

ENV_TEMPLATE_DEFAULT = """# ============================================
# Agent-specific LLM Configuration (OPTIONAL)
# ============================================
# This agent uses the DEFAULT configuration from web/.env
#
# To override, uncomment and configure ONE of these options:

# --- Local LLM (Ollama) ---
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=mistral

# --- Cloud LLM (Mistral) ---
# LLM_PROVIDER=mistral
# MISTRAL_API_KEY=your_key_here
# MISTRAL_MODEL=mistral-large-latest
"""

ENV_TEMPLATE_MISTRAL = """# ============================================
# Agent-specific LLM Configuration
# ============================================
# This agent OVERRIDES the default from web/.env

LLM_PROVIDER=mistral
MISTRAL_API_KEY={api_key}
MISTRAL_MODEL={model}
"""

ENV_TEMPLATE_OLLAMA = """# ============================================
# Agent-specific LLM Configuration
# ============================================
# This agent OVERRIDES the default from web/.env

LLM_PROVIDER=ollama
OLLAMA_BASE_URL={ollama_url}
OLLAMA_MODEL={ollama_model}
"""

ENV_TEMPLATE_TEXT2SQL = """# ============================================
# Text2SQL Agent - Dual LLM Configuration
# ============================================
# Este agente usa DOS LLMs:
#   1. LLM Principal (cloud) - para convertir texto a SQL
#   2. LLM Local (Ollama) - para formatear resultados

# ----- LLM PRINCIPAL (texto a SQL) -----
LLM_PROVIDER={provider}
{provider_config}

# ----- LLM LOCAL (formatear resultados) -----
# Siempre usa Ollama local para formatear
LOCAL_LLM_BASE_URL={local_url}
LOCAL_LLM_MODEL={local_model}
"""

GITIGNORE = """.env
.venv/
__pycache__/
*.pyc
.DS_Store
"""

AGENT_PY_TEMPLATE = '''"""
{agent_name} - Agente Oneshot
Soporta Mistral Cloud y Ollama via LLM_PROVIDER
"""

import os
import sys

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = self._build_system_prompt()

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "{model}")
        return os.getenv("MISTRAL_MODEL", "{model}")

    def _load_data(self) -> str:
        """Carga los datos del agente desde data.md"""
        data_path = os.path.join(os.path.dirname(__file__), "data", "data.md")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema con los datos."""
        data = self._load_data()
        base_prompt = """{system_prompt}"""

        if data:
            return f"{{base_prompt}}\n\nDatos disponibles:\n{{data}}"
        return base_prompt

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Envía un mensaje y obtiene respuesta.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos [{{"role": "user/assistant", "content": "..."}}]

        Returns:
            Respuesta del agente
        """
        messages = [{{"role": "system", "content": self.system_prompt}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        return response.choices[0].message.content

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Envía un mensaje y obtiene respuesta en streaming.

        Yields:
            Chunks de texto de la respuesta
        """
        messages = [{{"role": "system", "content": self.system_prompt}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        async for chunk in await self.client.chat.stream_async(
            model=self.model,
            messages=messages
        ):
            if chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content
'''

# ============================================================================
# PLANTILLA AGENTE RAG
# ============================================================================

AGENT_RAG_TEMPLATE = '''"""
{agent_name} - Agente RAG con ChromaDB
Soporta Mistral Cloud y Ollama via LLM_PROVIDER

NOTA: ChromaDB no es compatible con Python 3.14+. Requiere Python 3.11-3.13.
"""

import os
import sys

# Añadir web/ al path para importar llm_client y error_codes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient
from error_codes import format_error, DATA_CHROMADB_PYTHON_INCOMPATIBLE, DATA_CHROMADB_ERROR

from pypdf import PdfReader


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = """{system_prompt}"""

        # Inicializar ChromaDB con manejo de errores
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            db_path = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
            self.chroma_client = chromadb.PersistentClient(path=db_path)

            # Función de embeddings (usa sentence-transformers por defecto)
            # La primera vez descarga el modelo (~90MB), puede tardar
            print("Preparing RAG database...")
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )

            # Obtener o crear colección
            self.collection = self.chroma_client.get_or_create_collection(
                name="documents",
                embedding_function=self.embedding_fn
            )

            # Indexar documentos si la colección está vacía
            if self.collection.count() == 0:
                print("Indexing documents for the first time...")
                self._index_documents()

            print("RAG database ready.")
            self._chromadb_error = None

        except Exception as e:
            error_msg = str(e)
            # Detectar error de incompatibilidad Python 3.14
            if "unable to infer type" in error_msg or "chroma_server" in error_msg:
                self._chromadb_error = format_error(DATA_CHROMADB_PYTHON_INCOMPATIBLE)
            else:
                self._chromadb_error = format_error(DATA_CHROMADB_ERROR, details=error_msg)
            print(f"Warning: ChromaDB initialization failed: {{error_msg}}")
            self.chroma_client = None
            self.collection = None

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "{model}")
        return os.getenv("MISTRAL_MODEL", "{model}")

    def _extract_pdf_text(self, filepath: str) -> str:
        """Extrae texto de un archivo PDF."""
        try:
            reader = PdfReader(filepath)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts)
        except Exception as e:
            print(f"Error extracting text from {{filepath}}: {{e}}")
            return ""

    def _index_documents(self):
        """Indexa los documentos del directorio data/docs/"""
        docs_path = os.path.join(os.path.dirname(__file__), "data", "docs")
        if not os.path.exists(docs_path):
            os.makedirs(docs_path)
            return

        documents = []
        metadatas = []
        ids = []

        for i, filename in enumerate(os.listdir(docs_path)):
            filepath = os.path.join(docs_path, filename)
            if not os.path.isfile(filepath):
                continue

            content = None
            if filename.endswith(('.txt', '.md')):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif filename.endswith('.pdf'):
                content = self._extract_pdf_text(filepath)

            if content:
                # Dividir en chunks de ~500 caracteres
                chunks = [content[j:j+500] for j in range(0, len(content), 400)]
                for k, chunk in enumerate(chunks):
                    documents.append(chunk)
                    metadatas.append({{"source": filename, "chunk": k}})
                    ids.append(f"{{filename}}_{{k}}")

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"Indexed {{len(documents)}} chunks from {{len(set(m['source'] for m in metadatas))}} documents")

    def _retrieve_context(self, query: str, n_results: int = 3) -> str:
        """Recupera contexto relevante para la query."""
        if self.collection is None or self.collection.count() == 0:
            return ""

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        if not results['documents'][0]:
            return ""

        context_parts = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            context_parts.append(f"[Fuente: {{meta['source']}}]\n{{doc}}")

        return "\n\n---\n\n".join(context_parts)

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Envía un mensaje con contexto RAG y obtiene respuesta.
        """
        # Verificar si ChromaDB está disponible
        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {{err['error_code']}}:** {{err['error']}}\n\n{{err.get('instructions', '')}}"

        # Recuperar contexto relevante
        context = self._retrieve_context(user_message)

        # Construir prompt con contexto
        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\n\nContexto relevante de la base de conocimiento:\n{{context}}"

        messages = [{{"role": "system", "content": system_with_context}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        return response.choices[0].message.content

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Envía un mensaje con contexto RAG y obtiene respuesta en streaming.
        """
        # Verificar si ChromaDB está disponible
        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {{err['error_code']}}:** {{err['error']}}\n\n{{err.get('instructions', '')}}"
            return

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\n\nContexto relevante de la base de conocimiento:\n{{context}}"

        messages = [{{"role": "system", "content": system_with_context}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        async for chunk in await self.client.chat.stream_async(
            model=self.model,
            messages=messages
        ):
            if chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content

    def reindex(self):
        """Reindexa todos los documentos (útil después de añadir nuevos)."""
        # Borrar colección existente
        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._index_documents()
        return self.collection.count()
'''

# ============================================================================
# PLANTILLA AGENTE CONSULTABD_SQL (Text-to-SQL simplificado)
# ============================================================================

AGENT_CONSULTABD_SQL_TEMPLATE = '''"""
{agent_name} - Agente ConsultaBD_SQL
Convierte preguntas en lenguaje natural a consultas SQL.
Soporta Mistral Cloud y Ollama via LLM_PROVIDER.
"""

import os
import sys
import sqlite3
import logging

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("{agent_id}")


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = """{system_prompt}"""
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "{model}")
        return os.getenv("MISTRAL_MODEL", "{model}")

    def _get_db_schema(self) -> str:
        """Obtiene el esquema completo de la base de datos."""
        if not os.path.exists(self.db_path):
            return "ERROR: Base de datos no encontrada en data/database.db"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = cursor.fetchall()

            if not tables:
                conn.close()
                return "La base de datos está vacía (no hay tablas)."

            schema_parts = ["ESQUEMA DE LA BASE DE DATOS:"]
            schema_parts.append("=" * 40)

            for (table_name,) in tables:
                schema_parts.append(f"\\nTabla: {{table_name}}")
                schema_parts.append("-" * 20)

                cursor.execute(f"PRAGMA table_info({{table_name}});")
                columns = cursor.fetchall()

                for col in columns:
                    col_id, name, col_type, not_null, default, pk = col
                    constraints = []
                    if pk:
                        constraints.append("PRIMARY KEY")
                    if not_null:
                        constraints.append("NOT NULL")
                    constraint_str = f" ({{', '.join(constraints)}})" if constraints else ""
                    schema_parts.append(f"  - {{name}}: {{col_type}}{{constraint_str}}")

                cursor.execute(f"SELECT COUNT(*) FROM {{table_name}};")
                row_count = cursor.fetchone()[0]
                schema_parts.append(f"  [{{row_count}} filas]")

            conn.close()
            return "\\n".join(schema_parts)

        except sqlite3.Error as e:
            return f"Error leyendo esquema: {{str(e)}}"

    def _text_to_sql(self, user_question: str, schema: str) -> str:
        """Usa el LLM para convertir una pregunta en lenguaje natural a SQL."""
        logger.info(f"🔄 Convirtiendo pregunta a SQL: {{user_question[:50]}}...")

        conversion_prompt = f"""Eres un experto en SQL. Tu tarea es convertir la siguiente pregunta en lenguaje natural a una consulta SQL válida para SQLite.

{{schema}}

REGLAS IMPORTANTES:
1. Genera SOLO la consulta SQL, sin explicaciones
2. Solo genera consultas SELECT (lectura)
3. La consulta debe ser válida para SQLite
4. Si la pregunta no puede responderse con los datos disponibles, responde: ERROR: [explicación]
5. Usa nombres de columnas y tablas EXACTAMENTE como aparecen en el esquema

PREGUNTA DEL USUARIO:
{{user_question}}

CONSULTA SQL:"""

        messages = [{{"role": "user", "content": conversion_prompt}}]

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        sql = response.choices[0].message.content.strip()

        if sql.startswith("```"):
            lines = sql.split("\\n")
            sql = "\\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        sql = sql.strip()
        logger.info(f"📝 SQL generado: {{sql}}")
        return sql

    def _execute_sql(self, query: str) -> tuple:
        """Ejecuta una consulta SQL y devuelve (éxito, resultado)."""
        logger.info(f"⚡ Ejecutando SQL...")

        query_upper = query.strip().upper()

        if query_upper.startswith("ERROR:"):
            return (False, query)

        if not query_upper.startswith("SELECT"):
            return (False, "Solo se permiten consultas SELECT.")

        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC", "--"]
        for word in forbidden:
            if word in query_upper:
                return (False, f"Operación '{{word}}' no permitida por seguridad.")

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return (True, [])

            results = [dict(row) for row in rows]
            logger.info(f"✅ Consulta exitosa: {{len(results)}} filas")
            return (True, results)

        except sqlite3.Error as e:
            logger.error(f"❌ Error SQL: {{str(e)}}")
            return (False, f"Error SQL: {{str(e)}}")

    def _format_error(self, sql_query: str, error_msg: str) -> str:
        """Formatea un mensaje de error de forma amigable (sin LLM)."""
        return f"""**Error en la consulta**

Se intentó ejecutar:
```sql
{{sql_query}}
```

**Problema:** {{error_msg}}

Intenta reformular tu pregunta o verifica que los datos existan en la base de datos."""

    def _format_empty(self, sql_query: str) -> str:
        """Formatea un mensaje cuando no hay resultados (sin LLM)."""
        return f"""**Sin resultados**

La consulta se ejecutó correctamente pero no encontró datos:
```sql
{{sql_query}}
```

Prueba con otros criterios de búsqueda."""

    def _format_success(self, results: list, sql_query: str) -> str:
        """Formatea los resultados exitosos (sin LLM) - solo resumen."""
        num_rows = len(results)
        num_cols = len(results[0]) if results else 0

        summary = f"**Consulta ejecutada:** `{{sql_query}}`\\n\\n"
        summary += f"**Resultados:** {{num_rows}} fila(s), {{num_cols}} columna(s)"

        if num_rows > 100:
            summary += " (mostrando primeras 100)"

        return summary

    def _format_as_html_table(self, results: list) -> str:
        """Formatea los resultados JSON como una tabla HTML."""
        if not results:
            return "<p><em>Sin resultados</em></p>"

        columns = list(results[0].keys())

        html = """<div class="sql-results" style="margin: 15px 0;">
<style>
.sql-table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
.sql-table th {{ background: #2c3e50; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }}
.sql-table td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
.sql-table tr:hover {{ background: #f5f5f5; }}
.sql-table tr:nth-child(even) {{ background: #fafafa; }}
.sql-table .number {{ text-align: right; font-family: monospace; }}
.sql-table .null {{ color: #999; font-style: italic; }}
.sql-stats {{ margin-bottom: 10px; color: #666; font-size: 13px; }}
</style>
<div class="sql-stats">Resultados: <strong>{{row_count}}</strong> filas</div>
<div style="overflow-x: auto;">
<table class="sql-table">
<thead><tr>{{headers}}</tr></thead>
<tbody>{{rows}}</tbody>
</table>
</div>
</div>"""

        headers = "".join(f"<th>{{col}}</th>" for col in columns)

        rows_html = []
        for row in results[:100]:
            cells = []
            for col in columns:
                val = row.get(col)
                if val is None:
                    cells.append('<td class="null">NULL</td>')
                elif isinstance(val, (int, float)):
                    cells.append(f'<td class="number">{{val}}</td>')
                else:
                    escaped = str(val).replace("<", "&lt;").replace(">", "&gt;")
                    cells.append(f"<td>{{escaped}}</td>")
            rows_html.append(f"<tr>{{''.join(cells)}}</tr>")

        return html.format(
            row_count=len(results),
            headers=headers,
            rows="\\n".join(rows_html)
        )

    def chat(self, user_message: str, history: list = None) -> str:
        """Procesa una pregunta del usuario y devuelve la respuesta."""
        logger.info(f"📩 Usuario: {{user_message}}")

        if not os.path.exists(self.db_path):
            return "⚠️ **Base de datos no encontrada**\\n\\nPor favor, crea una base de datos SQLite en `data/database.db`."

        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            return f"⚠️ {{schema}}"

        # UNA sola llamada al LLM: texto -> SQL
        sql_query = self._text_to_sql(user_message, schema)

        if sql_query.strip().upper().startswith("ERROR:"):
            return f"⚠️ {{sql_query}}"

        success, results = self._execute_sql(sql_query)

        # Formateo con Python (sin LLM adicional)
        if not success:
            return self._format_error(sql_query, results)
        elif not results:
            return self._format_empty(sql_query)
        else:
            summary = self._format_success(results, sql_query)
            html_table = self._format_as_html_table(results)
            return f"{{summary}}\\n\\n{{html_table}}"

    async def chat_stream(self, user_message: str, history: list = None):
        """Versión streaming del chat."""
        yield ("status", "Analizando pregunta...")

        if not os.path.exists(self.db_path):
            yield ("content", "⚠️ **Base de datos no encontrada**\\n\\nPor favor, crea una base de datos SQLite en `data/database.db`.")
            return

        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            yield ("content", f"⚠️ {{schema}}")
            return

        yield ("status", "Generando consulta SQL...")
        sql_query = self._text_to_sql(user_message, schema)

        if sql_query.strip().upper().startswith("ERROR:"):
            yield ("content", f"⚠️ {{sql_query}}")
            return

        yield ("status", "Ejecutando consulta...")
        success, results = self._execute_sql(sql_query)

        # Formateo con Python (sin LLM adicional)
        if not success:
            yield ("content", self._format_error(sql_query, results))
        elif not results:
            yield ("content", self._format_empty(sql_query))
        else:
            summary = self._format_success(results, sql_query)
            html_table = self._format_as_html_table(results)
            yield ("content", f"{{summary}}\\n\\n{{html_table}}")

    def get_schema(self) -> str:
        """Devuelve el esquema de la BD."""
        return self._get_db_schema()
'''

# ============================================================================
# PLANTILLA AGENTE TOOLCALL (obsoleta, mantenida por compatibilidad)
# ============================================================================

AGENT_TOOLCALL_TEMPLATE = '''"""
{agent_name} - Agente con Function Calling (Toolcall)
Soporta Mistral Cloud, Ollama y vLLM via LLM_PROVIDER
"""

import os
import sys
import json
import logging

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("{agent_id}")


# ============================================================================
# DEFINICIÓN DE HERRAMIENTAS
# ============================================================================

def obtener_hora_actual() -> str:
    """Obtiene la hora actual."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S del %d/%m/%Y")


def calcular(expresion: str) -> str:
    """Calcula una expresión matemática simple."""
    try:
        # Solo permitir operaciones matemáticas básicas
        allowed = set('0123456789+-*/.() ')
        if not all(c in allowed for c in expresion):
            return "Error: expresión no válida"
        result = eval(expresion)
        return str(result)
    except Exception as e:
        return f"Error: {{str(e)}}"


def buscar_en_datos(query: str) -> str:
    """Busca información en los datos del agente."""
    data_path = os.path.join(os.path.dirname(__file__), "data", "data.md")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Búsqueda simple por líneas que contienen la query
        matches = [line for line in content.split('\n') if query.lower() in line.lower()]
        if matches:
            return "\n".join(matches[:5])
        return "No se encontró información relevante."
    except FileNotFoundError:
        return "Archivo de datos no encontrado."


def consultar_sql(query: str) -> str:
    """
    Ejecuta una consulta SQL SELECT en la base de datos.
    Solo permite consultas de lectura (SELECT).
    """
    import sqlite3

    # Validar que sea solo SELECT (seguridad básica)
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        return "Error: Solo se permiten consultas SELECT por seguridad."

    # Palabras prohibidas para evitar inyección
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC", "--", ";"]
    for word in forbidden:
        if word in query_upper:
            return f"Error: Operación '{{word}}' no permitida."

    db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")

    if not os.path.exists(db_path):
        return "Error: Base de datos no encontrada. Crea data/database.db primero."

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "La consulta no devolvió resultados."

        # Formatear resultados como tabla
        columns = rows[0].keys()
        result_lines = [" | ".join(columns)]
        result_lines.append("-" * len(result_lines[0]))

        for row in rows[:50]:  # Limitar a 50 filas
            result_lines.append(" | ".join(str(row[col]) for col in columns))

        if len(rows) > 50:
            result_lines.append(f"... ({{len(rows) - 50}} filas más)")

        return "\n".join(result_lines)

    except sqlite3.Error as e:
        return f"Error SQL: {{str(e)}}"
    except Exception as e:
        return f"Error: {{str(e)}}"


def listar_tablas() -> str:
    """Lista todas las tablas disponibles en la base de datos."""
    import sqlite3

    db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")

    if not os.path.exists(db_path):
        return "Error: Base de datos no encontrada. Crea data/database.db primero."

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        conn.close()

        if not tables:
            return "No hay tablas en la base de datos."

        return "Tablas disponibles:\n" + "\n".join(f"  - {{t[0]}}" for t in tables)

    except sqlite3.Error as e:
        return f"Error SQL: {{str(e)}}"


def describir_tabla(tabla: str) -> str:
    """Muestra la estructura (columnas) de una tabla."""
    import sqlite3

    # Validar nombre de tabla (solo alfanuméricos y guión bajo)
    if not tabla.replace("_", "").isalnum():
        return "Error: Nombre de tabla no válido."

    db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")

    if not os.path.exists(db_path):
        return "Error: Base de datos no encontrada."

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({{tabla}});")
        columns = cursor.fetchall()
        conn.close()

        if not columns:
            return f"La tabla '{{tabla}}' no existe o no tiene columnas."

        result = f"Estructura de '{{tabla}}':\n"
        for col in columns:
            pk = " (PK)" if col[5] else ""
            nullable = "" if col[3] else " NOT NULL"
            result += f"  - {{col[1]}}: {{col[2]}}{{nullable}}{{pk}}\n"

        return result.strip()

    except sqlite3.Error as e:
        return f"Error SQL: {{str(e)}}"


# Mapeo de nombres de función a funciones
AVAILABLE_TOOLS = {{
    "obtener_hora_actual": obtener_hora_actual,
    "calcular": calcular,
    "buscar_en_datos": buscar_en_datos,
    "consultar_sql": consultar_sql,
    "listar_tablas": listar_tablas,
    "describir_tabla": describir_tabla,
}}

# Especificación de herramientas para Mistral
TOOLS_SPEC = [
    {{
        "type": "function",
        "function": {{
            "name": "obtener_hora_actual",
            "description": "Obtiene la fecha y hora actual",
            "parameters": {{
                "type": "object",
                "properties": {{}},
                "required": []
            }}
        }}
    }},
    {{
        "type": "function",
        "function": {{
            "name": "calcular",
            "description": "Calcula una expresión matemática. Ejemplo: calcular('2 + 2')",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "expresion": {{
                        "type": "string",
                        "description": "La expresión matemática a calcular"
                    }}
                }},
                "required": ["expresion"]
            }}
        }}
    }},
    {{
        "type": "function",
        "function": {{
            "name": "buscar_en_datos",
            "description": "Busca información en la base de conocimiento del agente",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "query": {{
                        "type": "string",
                        "description": "Término o frase a buscar"
                    }}
                }},
                "required": ["query"]
            }}
        }}
    }},
    {{
        "type": "function",
        "function": {{
            "name": "consultar_sql",
            "description": "Ejecuta una consulta SQL SELECT en la base de datos SQLite. Solo lectura, no permite INSERT/UPDATE/DELETE. Usa listar_tablas() primero para ver las tablas disponibles.",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "query": {{
                        "type": "string",
                        "description": "Consulta SQL SELECT a ejecutar. Ejemplo: SELECT * FROM usuarios WHERE edad > 18"
                    }}
                }},
                "required": ["query"]
            }}
        }}
    }},
    {{
        "type": "function",
        "function": {{
            "name": "listar_tablas",
            "description": "Lista todas las tablas disponibles en la base de datos SQLite",
            "parameters": {{
                "type": "object",
                "properties": {{}},
                "required": []
            }}
        }}
    }},
    {{
        "type": "function",
        "function": {{
            "name": "describir_tabla",
            "description": "Muestra la estructura de una tabla (columnas, tipos, claves primarias)",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "tabla": {{
                        "type": "string",
                        "description": "Nombre de la tabla a describir"
                    }}
                }},
                "required": ["tabla"]
            }}
        }}
    }}
]


class Agent:
    def __init__(self, system_prompt: str = None):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = system_prompt or """{system_prompt}"""
        self.tools = TOOLS_SPEC

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "{model}")
        elif provider == "vllm":
            return os.getenv("VLLM_MODEL", "{model}")
        return "{model}"

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Ejecuta una herramienta y devuelve el resultado."""
        logger.info(f"🔧 Ejecutando herramienta: {{tool_name}}")
        logger.debug(f"   Argumentos: {{arguments}}")

        if tool_name not in AVAILABLE_TOOLS:
            logger.error(f"   Herramienta no encontrada: {{tool_name}}")
            return f"Error: herramienta '{{tool_name}}' no encontrada"

        try:
            func = AVAILABLE_TOOLS[tool_name]
            if arguments:
                result = func(**arguments)
            else:
                result = func()
            logger.info(f"   Resultado: {{str(result)[:200]}}...")
            return str(result)
        except Exception as e:
            logger.error(f"   Error: {{str(e)}}")
            return f"Error ejecutando {{tool_name}}: {{str(e)}}"

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Envía un mensaje y obtiene respuesta, ejecutando herramientas si es necesario.
        Soporta múltiples ciclos de herramientas (el modelo puede llamar varias herramientas secuencialmente).
        """
        logger.info(f"📩 Usuario: {{user_message}}")

        messages = [{{"role": "system", "content": self.system_prompt}}]

        if history:
            messages.extend(history)
            logger.debug(f"   Historial: {{len(history)}} mensajes")

        messages.append({{"role": "user", "content": user_message}})

        max_iterations = 10  # Límite de seguridad para evitar bucles infinitos

        for iteration in range(max_iterations):
            logger.debug(f"🤖 Llamando a Mistral ({{self.model}}) - iteración {{iteration + 1}}...")
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message
            logger.debug(f"   Respuesta recibida. tool_calls: {{assistant_message.tool_calls is not None}}")

            # Si no hay tool_calls, devolver respuesta directa
            if not assistant_message.tool_calls:
                final_content = assistant_message.content or ""
                if iteration == 0:
                    logger.warning("⚠️  NO HAY TOOL_CALLS - El modelo respondió sin usar herramientas")
                logger.info(f"📤 Respuesta final (iteración {{iteration + 1}}): {{final_content[:200]}}...")
                return final_content

            logger.info(f"🔨 Tool calls detectados: {{len(assistant_message.tool_calls)}}")

            # Ejecutar herramientas
            messages.append(assistant_message)

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {{}}

                result = self._execute_tool(tool_name, arguments)

                messages.append({{
                    "role": "tool",
                    "name": tool_name,
                    "content": result,
                    "tool_call_id": tool_call.id
                }})

            # Continuar el bucle para procesar más tool_calls si es necesario

        # Si llegamos aquí, se alcanzó el límite de iteraciones
        logger.error("❌ Se alcanzó el límite de iteraciones de herramientas")
        return "Error: Se alcanzó el límite de iteraciones de herramientas."

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Versión streaming con eventos de estado.
        Emite tuplas (tipo, contenido): ("status", mensaje) o ("content", texto)
        """
        logger.info(f"📩 [STREAM] Usuario: {{user_message}}")

        messages = [{{"role": "system", "content": self.system_prompt}}]
        if history:
            messages.extend(history)
        messages.append({{"role": "user", "content": user_message}})

        # Mensajes de estado por herramienta
        status_messages = {{
            "consultar_sql": "Consultando base de datos...",
            "buscar_en_datos": "Buscando información...",
            "calcular": "Calculando...",
            "obtener_hora_actual": "Obteniendo hora...",
            "listar_tablas": "Listando tablas...",
            "describir_tabla": "Describiendo tabla..."
        }}

        max_iterations = 10
        for iteration in range(max_iterations):
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            if not assistant_message.tool_calls:
                yield ("content", assistant_message.content or "")
                return

            # Emitir status para cada herramienta
            messages.append(assistant_message)
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                status = status_messages.get(tool_name, "Procesando...")
                yield ("status", status)

                arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {{}}
                result = self._execute_tool(tool_name, arguments)

                messages.append({{
                    "role": "tool",
                    "name": tool_name,
                    "content": result,
                    "tool_call_id": tool_call.id
                }})

        yield ("content", "Error: Se alcanzó el límite de iteraciones.")
'''

# ============================================================================
# PLANTILLA AGENTE TEXT2SQL
# ============================================================================

AGENT_TEXT2SQL_TEMPLATE = '''"""
{agent_name} - Agente Text-to-SQL
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
logger = logging.getLogger("{agent_id}")


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = """{system_prompt}"""
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
            logger.info(f"🏠 Conectando a LLM local en {{base_url}}...")
            return ollama.Client(host=base_url)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo inicializar cliente local Ollama: {{e}}")
            return None

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "{model}")
        elif provider == "vllm":
            return os.getenv("VLLM_MODEL", "{model}")
        return "{model}"

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
                schema_parts.append(f"\nTabla: {{table_name}}")
                schema_parts.append("-" * 20)

                # Obtener estructura de la tabla
                cursor.execute(f"PRAGMA table_info({{table_name}});")
                columns = cursor.fetchall()

                for col in columns:
                    col_id, name, col_type, not_null, default, pk = col
                    constraints = []
                    if pk:
                        constraints.append("PRIMARY KEY")
                    if not_null:
                        constraints.append("NOT NULL")
                    constraint_str = f" ({{', '.join(constraints)}})" if constraints else ""
                    schema_parts.append(f"  - {{name}}: {{col_type}}{{constraint_str}}")

                # Obtener número de filas
                cursor.execute(f"SELECT COUNT(*) FROM {{table_name}};")
                row_count = cursor.fetchone()[0]
                schema_parts.append(f"  [{{row_count}} filas]")

            conn.close()
            return "\n".join(schema_parts)

        except sqlite3.Error as e:
            return f"Error leyendo esquema: {{str(e)}}"

    def _text_to_sql(self, user_question: str, schema: str) -> str:
        """Usa el LLM para convertir una pregunta en lenguaje natural a SQL."""
        logger.info(f"🔄 Convirtiendo pregunta a SQL: {{user_question[:50]}}...")

        conversion_prompt = f"""Eres un experto en SQL. Tu tarea es convertir la siguiente pregunta en lenguaje natural a una consulta SQL válida para SQLite.

{{schema}}

REGLAS IMPORTANTES:
1. Genera SOLO la consulta SQL, sin explicaciones
2. Solo genera consultas SELECT (lectura)
3. La consulta debe ser válida para SQLite
4. Si la pregunta no puede responderse con los datos disponibles, responde: ERROR: [explicación]
5. Usa nombres de columnas y tablas EXACTAMENTE como aparecen en el esquema

PREGUNTA DEL USUARIO:
{{user_question}}

CONSULTA SQL:"""

        messages = [{{"role": "user", "content": conversion_prompt}}]

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        sql = response.choices[0].message.content.strip()

        # Limpiar la respuesta (quitar bloques de código markdown si los hay)
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        sql = sql.strip()
        logger.info(f"📝 SQL generado: {{sql}}")
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
                return (False, f"Operación '{{word}}' no permitida por seguridad.")

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

            logger.info(f"✅ Consulta exitosa: {{len(results)}} filas")
            return (True, results)

        except sqlite3.Error as e:
            logger.error(f"❌ Error SQL: {{str(e)}}")
            return (False, f"Error SQL: {{str(e)}}")

    def _format_results(self, user_question: str, sql_query: str, results: list, success: bool) -> str:
        """Usa el LLM LOCAL (Ollama) para formatear los resultados de manera amigable."""
        logger.info("📊 Formateando resultados con LLM local...")

        if not success:
            # results contiene el mensaje de error
            format_prompt = f"""El usuario preguntó: "{{user_question}}"

Se intentó ejecutar esta consulta SQL: {{sql_query}}

Pero ocurrió un error: {{results}}

Por favor, explica al usuario qué salió mal de manera amigable y sugiere cómo podría reformular su pregunta."""

        elif not results:
            format_prompt = f"""El usuario preguntó: "{{user_question}}"

Se ejecutó esta consulta SQL: {{sql_query}}

La consulta no devolvió ningún resultado.

Por favor, informa al usuario de manera amigable que no se encontraron datos que coincidan con su búsqueda."""

        else:
            # Limitar resultados para no exceder contexto
            display_results = results[:100]
            truncated = len(results) > 100

            format_prompt = f"""El usuario preguntó: "{{user_question}}"

Se ejecutó esta consulta SQL: {{sql_query}}

Resultados ({{len(results)}} filas{{"(mostrando primeras 100)" if truncated else ""}}):
{{display_results}}

Por favor, presenta estos resultados al usuario de manera clara y amigable:
- Usa formato de tabla markdown si es apropiado
- Resume los puntos clave
- Responde directamente a la pregunta del usuario
- Si hay muchos datos, destaca los más relevantes"""

        messages = [
            {{"role": "system", "content": self.system_prompt}},
            {{"role": "user", "content": format_prompt}}
        ]

        # Usar cliente local (Ollama) para formatear
        if self.local_client:
            try:
                logger.info(f"🏠 Usando Ollama local ({{self.local_model}}) para formatear...")
                response = self.local_client.chat(
                    model=self.local_model,
                    messages=messages
                )
                return response["message"]["content"]
            except Exception as e:
                logger.warning(f"⚠️ Error con LLM local, usando cliente principal: {{e}}")

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
            return "<p><em>Sin resultados</em></p>"

        import json as json_module
        columns = list(results[0].keys())

        html = """<div class="sql-results" style="margin: 15px 0;">
<style>
.sql-table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
.sql-table th {{ background: #2c3e50; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }}
.sql-table td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
.sql-table tr:hover {{ background: #f5f5f5; }}
.sql-table tr:nth-child(even) {{ background: #fafafa; }}
.sql-table .number {{ text-align: right; font-family: monospace; }}
.sql-table .null {{ color: #999; font-style: italic; }}
.sql-stats {{ margin-bottom: 10px; color: #666; font-size: 13px; }}
</style>
<div class="sql-stats">Resultados: <strong>{{row_count}}</strong> filas</div>
<div style="overflow-x: auto;">
<table class="sql-table">
<thead><tr>{{headers}}</tr></thead>
<tbody>{{rows}}</tbody>
</table>
</div>
</div>"""

        headers = "".join(f"<th>{{col}}</th>" for col in columns)

        rows_html = []
        for row in results[:100]:  # Limitar a 100 filas
            cells = []
            for col in columns:
                val = row.get(col)
                if val is None:
                    cells.append('<td class="null">NULL</td>')
                elif isinstance(val, (int, float)):
                    cells.append(f'<td class="number">{{val}}</td>')
                else:
                    escaped = str(val).replace("<", "&lt;").replace(">", "&gt;")
                    cells.append(f"<td>{{escaped}}</td>")
            rows_html.append(f"<tr>{{''.join(cells)}}</tr>")

        return html.format(
            row_count=len(results),
            headers=headers,
            rows="\n".join(rows_html)
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
        logger.info(f"📩 Usuario: {{user_message}}")

        # Verificar que existe la BD
        if not os.path.exists(self.db_path):
            return "⚠️ **Base de datos no encontrada**\n\nPor favor, crea una base de datos SQLite en `data/database.db`.\n\nEjemplo:\n```bash\nsqlite3 data/database.db < tu_schema.sql\n```"

        # Paso 1: Obtener esquema
        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            return f"⚠️ {{schema}}"

        # Paso 2: Convertir texto a SQL
        sql_query = self._text_to_sql(user_message, schema)

        # Validar que no sea un error del LLM
        if sql_query.strip().upper().startswith("ERROR:"):
            return f"⚠️ {{sql_query}}"

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
                logger.error(f"❌ Error en consultar_sql.py: {{error_msg}}")
                return f"⚠️ Error ejecutando consulta: {{error_msg}}"

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            # Parsear JSON y generar tabla HTML
            import json as json_module
            results = json_module.loads(json_output)
            html_table = self._format_as_html_table(results)

            logger.info(f"📊 Tabla HTML generada con {{len(results)}} filas")

        except Exception as e:
            logger.error(f"❌ Error ejecutando consultar_sql.py: {{str(e)}}")
            # Fallback: ejecutar SQL internamente
            success, results = self._execute_sql(sql_query)
            if success:
                html_table = self._format_as_html_table(results)
            else:
                return f"⚠️ Error: {{str(e)}}"

        # Paso 4: Formatear explicación con LLM
        success, results = self._execute_sql(sql_query)
        formatted = self._format_results(user_message, sql_query, results, success)

        # Paso 5: Combinar explicación + tabla HTML
        return f"{{formatted}}\n\n{{html_table}}"

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Versión streaming - emite eventos de estado y contenido.
        """
        logger.info(f"📩 [STREAM] Usuario: {{user_message}}")

        # Verificar BD
        if not os.path.exists(self.db_path):
            yield ("content", "⚠️ **Base de datos no encontrada**\n\nCrea una base de datos SQLite en `data/database.db`.")
            return

        # Emitir estados
        yield ("status", "Analizando esquema de la base de datos...")
        schema = self._get_db_schema()

        yield ("status", "Convirtiendo pregunta a SQL...")
        sql_query = self._text_to_sql(user_message, schema)

        # Validar que no sea un error del LLM
        if sql_query.strip().upper().startswith("ERROR:"):
            yield ("content", f"⚠️ {{sql_query}}")
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
                logger.error(f"❌ Error en consultar_sql.py: {{error_msg}}")
                yield ("content", f"⚠️ Error ejecutando consulta: {{error_msg}}")
                return

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            yield ("status", "Generando tabla de resultados...")

            # Parsear JSON y generar tabla HTML
            import json as json_module
            results = json_module.loads(json_output)
            html_table = self._format_as_html_table(results)

            logger.info(f"📊 Tabla HTML generada con {{len(results)}} filas")

        except Exception as e:
            logger.error(f"❌ Error ejecutando consultar_sql.py: {{str(e)}}")
            # Fallback: ejecutar SQL internamente
            success, results = self._execute_sql(sql_query)
            if success:
                html_table = self._format_as_html_table(results)
            else:
                yield ("content", f"⚠️ Error: {{str(e)}}")
                return

        yield ("status", "Formateando explicación...")
        success, results = self._execute_sql(sql_query)
        formatted = self._format_results(user_message, sql_query, results, success)

        # Combinar explicación + tabla HTML
        yield ("content", f"{{formatted}}\n\n{{html_table}}")

    def get_schema(self) -> str:
        """Devuelve el esquema de la BD (útil para debugging/API)."""
        return self._get_db_schema()
'''

# ============================================================================
# TEXT2SQL CON REINTENTOS (text2sql_retry)
# ============================================================================

AGENT_TEXT2SQL_RETRY_TEMPLATE = '''"""
{agent_name} - Agente Text-to-SQL con Reintentos
Convierte preguntas en lenguaje natural a consultas SQL usando Mistral Large.
Incluye autocorrección: si una consulta falla, reintenta hasta 3 veces.
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
logger = logging.getLogger("{agent_id}")

# Número máximo de reintentos para generar SQL
MAX_SQL_RETRIES = 3


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = """{system_prompt}"""
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
            logger.info(f"🏠 Conectando a LLM local en {{base_url}}...")
            return ollama.Client(host=base_url)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo inicializar cliente local Ollama: {{e}}")
            return None

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "{model}")
        elif provider == "vllm":
            return os.getenv("VLLM_MODEL", "{model}")
        return "{model}"

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
                schema_parts.append(f"\nTabla: {{table_name}}")
                schema_parts.append("-" * 20)

                # Obtener estructura de la tabla
                cursor.execute(f"PRAGMA table_info({{table_name}});")
                columns = cursor.fetchall()

                for col in columns:
                    col_id, name, col_type, not_null, default, pk = col
                    constraints = []
                    if pk:
                        constraints.append("PRIMARY KEY")
                    if not_null:
                        constraints.append("NOT NULL")
                    constraint_str = f" ({{', '.join(constraints)}})" if constraints else ""
                    schema_parts.append(f"  - {{name}}: {{col_type}}{{constraint_str}}")

                # Obtener número de filas
                cursor.execute(f"SELECT COUNT(*) FROM {{table_name}};")
                row_count = cursor.fetchone()[0]
                schema_parts.append(f"  [{{row_count}} filas]")

            conn.close()
            return "\n".join(schema_parts)

        except sqlite3.Error as e:
            return f"Error leyendo esquema: {{str(e)}}"

    def _text_to_sql(self, user_question: str, schema: str, last_error: str = None) -> str:
        """
        Usa el LLM para convertir una pregunta en lenguaje natural a SQL.
        Si hay un error previo, lo incluye en el prompt para autocorrección.
        """
        logger.info(f"🔄 Convirtiendo pregunta a SQL: {{user_question[:50]}}...")

        # Construir prompt base
        conversion_prompt = f"""Eres un experto en SQL. Tu tarea es convertir la siguiente pregunta en lenguaje natural a una consulta SQL válida para SQLite.

{{schema}}

REGLAS IMPORTANTES:
1. Genera SOLO la consulta SQL, sin explicaciones
2. Solo genera consultas SELECT (lectura)
3. La consulta debe ser válida para SQLite
4. Si la pregunta no puede responderse con los datos disponibles, responde: ERROR: [explicación]
5. Usa nombres de columnas y tablas EXACTAMENTE como aparecen en el esquema"""

        # Si hay error previo, añadirlo al prompt
        if last_error:
            conversion_prompt += f"""

⚠️ INTENTO ANTERIOR FALLÓ con este error:
{{last_error}}

IMPORTANTE: Corrige la consulta SQL considerando este error. Revisa los nombres de columnas y tablas en el esquema."""

        conversion_prompt += f"""

PREGUNTA DEL USUARIO:
{{user_question}}

CONSULTA SQL:"""

        messages = [{{"role": "user", "content": conversion_prompt}}]

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        sql = response.choices[0].message.content.strip()

        # Limpiar la respuesta (quitar bloques de código markdown si los hay)
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        sql = sql.strip()
        logger.info(f"📝 SQL generado: {{sql}}")
        return sql

    def _text_to_sql_with_retry(self, user_question: str, schema: str) -> tuple:
        """
        Genera SQL con reintentos automáticos si falla.

        Returns:
            tuple: (sql_query, success, results_or_error, attempts)
        """
        last_error = None

        for attempt in range(1, MAX_SQL_RETRIES + 1):
            logger.info(f"🔄 Intento {{attempt}}/{{MAX_SQL_RETRIES}}")

            # Generar SQL (con error previo si existe)
            sql_query = self._text_to_sql(user_question, schema, last_error)

            # Verificar si el LLM devolvió error
            if sql_query.strip().upper().startswith("ERROR:"):
                return (sql_query, False, sql_query, attempt)

            # Intentar ejecutar
            success, result = self._execute_sql(sql_query)

            if success:
                logger.info(f"✅ SQL exitoso en intento {{attempt}}")
                return (sql_query, True, result, attempt)

            # Guardar error para el siguiente intento
            last_error = result
            logger.warning(f"⚠️ Intento {{attempt}} falló: {{result}}")

        # Todos los intentos fallaron
        logger.error(f"❌ Todos los intentos fallaron. Último error: {{last_error}}")
        return (sql_query, False, f"Error tras {{MAX_SQL_RETRIES}} intentos: {{last_error}}", MAX_SQL_RETRIES)

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
                return (False, f"Operación '{{word}}' no permitida por seguridad.")

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

            logger.info(f"✅ Consulta exitosa: {{len(results)}} filas")
            return (True, results)

        except sqlite3.Error as e:
            logger.error(f"❌ Error SQL: {{str(e)}}")
            return (False, f"Error SQL: {{str(e)}}")

    def _format_results(self, user_question: str, sql_query: str, results: list, success: bool, attempts: int = 1) -> str:
        """Usa el LLM LOCAL (Ollama) para formatear los resultados de manera amigable."""
        logger.info("📊 Formateando resultados con LLM local...")

        retry_note = f"\n\n(Consulta exitosa tras {{attempts}} intento(s))" if attempts > 1 else ""

        if not success:
            # results contiene el mensaje de error
            format_prompt = f"""El usuario preguntó: "{{user_question}}"

Se intentó ejecutar esta consulta SQL: {{sql_query}}

Pero ocurrió un error: {{results}}

Por favor, explica al usuario qué salió mal de manera amigable y sugiere cómo podría reformular su pregunta."""

        elif not results:
            format_prompt = f"""El usuario preguntó: "{{user_question}}"

Se ejecutó esta consulta SQL: {{sql_query}}{{retry_note}}

La consulta no devolvió ningún resultado.

Por favor, informa al usuario de manera amigable que no se encontraron datos que coincidan con su búsqueda."""

        else:
            # Limitar resultados para no exceder contexto
            display_results = results[:100]
            truncated = len(results) > 100

            format_prompt = f"""El usuario preguntó: "{{user_question}}"

Se ejecutó esta consulta SQL: {{sql_query}}{{retry_note}}

Resultados ({{len(results)}} filas{{"(mostrando primeras 100)" if truncated else ""}}):
{{display_results}}

Por favor, presenta estos resultados al usuario de manera clara y amigable:
- Usa formato de tabla markdown si es apropiado
- Resume los puntos clave
- Responde directamente a la pregunta del usuario
- Si hay muchos datos, destaca los más relevantes"""

        messages = [
            {{"role": "system", "content": self.system_prompt}},
            {{"role": "user", "content": format_prompt}}
        ]

        # Usar cliente local (Ollama) para formatear
        if self.local_client:
            try:
                logger.info(f"🏠 Usando Ollama local ({{self.local_model}}) para formatear...")
                response = self.local_client.chat(
                    model=self.local_model,
                    messages=messages
                )
                return response["message"]["content"]
            except Exception as e:
                logger.warning(f"⚠️ Error con LLM local, usando cliente principal: {{e}}")

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
            return "<p><em>Sin resultados</em></p>"

        import json as json_module
        columns = list(results[0].keys())

        html = """<div class="sql-results" style="margin: 15px 0;">
<style>
.sql-table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
.sql-table th {{ background: #2c3e50; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }}
.sql-table td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
.sql-table tr:hover {{ background: #f5f5f5; }}
.sql-table tr:nth-child(even) {{ background: #fafafa; }}
.sql-table .number {{ text-align: right; font-family: monospace; }}
.sql-table .null {{ color: #999; font-style: italic; }}
.sql-stats {{ margin-bottom: 10px; color: #666; font-size: 13px; }}
</style>
<div class="sql-stats">Resultados: <strong>{{row_count}}</strong> filas</div>
<div style="overflow-x: auto;">
<table class="sql-table">
<thead><tr>{{headers}}</tr></thead>
<tbody>{{rows}}</tbody>
</table>
</div>
</div>"""

        headers = "".join(f"<th>{{col}}</th>" for col in columns)

        rows_html = []
        for row in results[:100]:  # Limitar a 100 filas
            cells = []
            for col in columns:
                val = row.get(col)
                if val is None:
                    cells.append('<td class="null">NULL</td>')
                elif isinstance(val, (int, float)):
                    cells.append(f'<td class="number">{{val}}</td>')
                else:
                    escaped = str(val).replace("<", "&lt;").replace(">", "&gt;")
                    cells.append(f"<td>{{escaped}}</td>")
            rows_html.append(f"<tr>{{''.join(cells)}}</tr>")

        return html.format(
            row_count=len(results),
            headers=headers,
            rows="\n".join(rows_html)
        )

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Procesa una pregunta del usuario con reintentos automáticos:
        1. Obtiene el esquema de la BD
        2. Convierte la pregunta a SQL (con reintentos si falla)
        3. Muestra los resultados en tabla HTML inline
        4. Formatea y devuelve los resultados
        """
        logger.info(f"📩 Usuario: {{user_message}}")

        # Verificar que existe la BD
        if not os.path.exists(self.db_path):
            return "⚠️ **Base de datos no encontrada**\n\nPor favor, crea una base de datos SQLite en `data/database.db`.\n\nEjemplo:\n```bash\nsqlite3 data/database.db < tu_schema.sql\n```"

        # Paso 1: Obtener esquema
        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            return f"⚠️ {{schema}}"

        # Paso 2: Convertir texto a SQL CON REINTENTOS
        sql_query, success, results, attempts = self._text_to_sql_with_retry(user_message, schema)

        # Si falló tras todos los intentos
        if not success:
            formatted = self._format_results(user_message, sql_query, results, success, attempts)
            return formatted

        # Paso 3: Generar tabla HTML
        html_table = self._format_as_html_table(results)
        logger.info(f"📊 Tabla HTML generada con {{len(results)}} filas")

        # Paso 4: Formatear explicación con LLM
        formatted = self._format_results(user_message, sql_query, results, success, attempts)

        # Paso 5: Combinar explicación + tabla HTML
        return f"{{formatted}}\n\n{{html_table}}"

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Versión streaming con reintentos - emite eventos de estado y contenido.
        """
        logger.info(f"📩 [STREAM] Usuario: {{user_message}}")

        # Verificar BD
        if not os.path.exists(self.db_path):
            yield ("content", "⚠️ **Base de datos no encontrada**\n\nCrea una base de datos SQLite en `data/database.db`.")
            return

        # Emitir estados
        yield ("status", "Analizando esquema de la base de datos...")
        schema = self._get_db_schema()

        yield ("status", "Convirtiendo pregunta a SQL (con reintentos)...")
        sql_query, success, results, attempts = self._text_to_sql_with_retry(user_message, schema)

        if attempts > 1:
            yield ("status", f"SQL corregido tras {{attempts}} intentos...")

        # Si falló tras todos los intentos
        if not success:
            formatted = self._format_results(user_message, sql_query, results, success, attempts)
            yield ("content", formatted)
            return

        yield ("status", "Generando tabla de resultados...")
        html_table = self._format_as_html_table(results)
        logger.info(f"📊 Tabla HTML generada con {{len(results)}} filas")

        yield ("status", "Formateando explicación...")
        formatted = self._format_results(user_message, sql_query, results, success, attempts)

        # Combinar explicación + tabla HTML
        yield ("content", f"{{formatted}}\n\n{{html_table}}")

    def get_schema(self) -> str:
        """Devuelve el esquema de la BD (útil para debugging/API)."""
        return self._get_db_schema()
'''

AGENT_TEXT2SQL_PURO_TEMPLATE = '''"""
Text2SQL Puro - Agente ultra-rapido para consultas en lenguaje natural a SQL.
Soporta Mistral Cloud (Codestral) y Ollama local (deepseek-coder, etc).
Optimizado para velocidad maxima.
"""

import os
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("text2sql_puro")


class Agent:
    def __init__(self):
        # Detectar proveedor LLM
        self.provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        self.client = None
        self.model = None

        if self.provider == "ollama":
            self._init_ollama()
        else:
            self._init_mistral()

    def _init_mistral(self):
        """Inicializa cliente Mistral Cloud (Codestral)."""
        from mistralai import Mistral
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY no configurada")
        self.client = Mistral(api_key=api_key)
        self.model = os.getenv("CODESTRAL_MODEL", "codestral-latest")
        self._setup_paths()

    def _init_ollama(self):
        """Inicializa cliente Ollama local."""
        import ollama
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = ollama.Client(host=base_url)
        self.model = os.getenv("OLLAMA_MODEL", "deepseek-coder")

        # Paths (se mueven al __init__ principal)
        self._setup_paths()

    def _setup_paths(self):
        """Configura paths y carga esquema."""
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")
        self.schema_path = os.path.join(os.path.dirname(__file__), "data", "database_schema.md")
        self._cached_schema = None
        self._load_schema()
        logger.info(f"Agente inicializado: provider={{self.provider}}, model={{self.model}}")

    def _load_schema(self):
        """Carga y cachea el esquema de la BD al iniciar."""
        if os.path.exists(self.schema_path):
            try:
                with open(self.schema_path, "r", encoding="utf-8") as f:
                    self._cached_schema = f.read()
                logger.info("Esquema cargado desde database_schema.md")
                return
            except Exception as e:
                logger.warning(f"Error leyendo esquema: {{e}}")

        # Fallback: generar esquema desde BD
        if os.path.exists(self.db_path):
            self._cached_schema = self._generate_schema_from_db()
        else:
            self._cached_schema = ""

    def _generate_schema_from_db(self) -> str:
        """Genera esquema basico desde la BD."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            schema_parts = []
            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({{table_name}});")
                cols = [f"{{c[1]}} {{c[2]}}" for c in cursor.fetchall()]
                schema_parts.append(f"CREATE TABLE {{table_name}} ({{', '.join(cols)}});")

            conn.close()
            return "\n".join(schema_parts)
        except Exception as e:
            logger.error(f"Error generando esquema: {{e}}")
            return ""

    def _text_to_sql(self, question: str) -> str:
        """Convierte pregunta en lenguaje natural a SQL."""
        # Prompt minimalista para maxima velocidad
        prompt = f"""Schema:
{{self._cached_schema}}

Question: {{question}}

Write ONLY the SQL query (SQLite). No explanations."""

        if self.provider == "ollama":
            response = self.client.chat(
                model=self.model,
                messages=[{{"role": "user", "content": prompt}}],
                options={{"temperature": 0, "num_predict": 500}}
            )
            sql = response["message"]["content"].strip()
        else:
            # Mistral
            response = self.client.chat.complete(
                model=self.model,
                messages=[{{"role": "user", "content": prompt}}],
                max_tokens=500,
                temperature=0
            )
            sql = response.choices[0].message.content.strip()

        # Limpiar markdown si existe
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(l for l in lines[1:] if not l.startswith("```"))

        return sql.strip()

    def _execute_sql(self, query: str) -> tuple:
        """Ejecuta SQL y devuelve (exito, resultado/error)."""
        query_upper = query.upper()

        # Solo SELECT permitido
        if not query_upper.strip().startswith("SELECT"):
            return (False, "Solo consultas SELECT permitidas")

        # Palabras prohibidas
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "--"]
        for word in forbidden:
            if word in query_upper:
                return (False, f"Operacion {{word}} no permitida")

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return (True, [])

            return (True, [dict(row) for row in rows])

        except sqlite3.Error as e:
            return (False, str(e))

    def _format_as_html_table(self, results: list) -> str:
        """Formatea resultados como tabla HTML."""
        if not results:
            return "<p><em>Sin resultados</em></p>"

        columns = list(results[0].keys())

        html = """<div class="sql-results">
<style>
.sql-table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
.sql-table th {{ background: #2c3e50; color: white; padding: 8px; text-align: left; }}
.sql-table td {{ padding: 6px 8px; border-bottom: 1px solid #eee; }}
.sql-table tr:hover {{ background: #f5f5f5; }}
</style>
<div style="overflow-x: auto;">
<table class="sql-table">
<thead><tr>"""

        for col in columns:
            html += f"<th>{{col}}</th>"
        html += "</tr></thead><tbody>"

        for row in results[:100]:
            html += "<tr>"
            for col in columns:
                val = row.get(col, "")
                if val is None:
                    html += '<td style="color:#999">NULL</td>'
                else:
                    escaped = str(val).replace("<", "&lt;").replace(">", "&gt;")
                    html += f"<td>{{escaped}}</td>"
            html += "</tr>"

        html += "</tbody></table></div>"

        if len(results) > 100:
            html += f"<p><em>Mostrando 100 de {{len(results)}} filas</em></p>"

        html += "</div>"
        return html

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Procesa consulta: texto -> SQL -> ejecucion -> resultado.
        Optimizado para velocidad maxima (sin LLM para formatear).
        """
        if not os.path.exists(self.db_path):
            return "Error: Base de datos no encontrada en data/database.db"

        if not self._cached_schema:
            return "Error: Esquema de BD no disponible"

        # Convertir a SQL
        try:
            sql_query = self._text_to_sql(user_message)
            logger.info(f"SQL: {{sql_query}}")
        except Exception as e:
            return f"Error generando SQL: {{str(e)}}"

        # Ejecutar
        success, results = self._execute_sql(sql_query)

        if not success:
            return f"**Error SQL:** {{results}}\n\n**Consulta:** `{{sql_query}}`"

        # Formatear respuesta (sin LLM adicional)
        html_table = self._format_as_html_table(results)

        return f"""**Consulta SQL:**
```sql
{{sql_query}}
```

**Resultados:** {{len(results)}} filas

{{html_table}}"""

    async def chat_stream(self, user_message: str, history: list = None):
        """Version streaming - emite estados y resultado final."""
        yield ("status", "Generando SQL...")

        if not os.path.exists(self.db_path):
            yield ("content", "Error: Base de datos no encontrada")
            return

        try:
            sql_query = self._text_to_sql(user_message)
        except Exception as e:
            yield ("content", f"Error: {{str(e)}}")
            return

        yield ("status", "Ejecutando consulta...")
        success, results = self._execute_sql(sql_query)

        if not success:
            yield ("content", f"Error SQL: {{results}}")
            return

        html_table = self._format_as_html_table(results)
        yield ("content", f"```sql\n{{sql_query}}\n```\n\n{{html_table}}")

    def get_schema(self) -> str:
        """Devuelve el esquema cacheado."""
        return self._cached_schema or "Esquema no disponible"

    def query(self, natural_query: str) -> dict:
        """
        API directa: devuelve SQL y resultados como dict.
        Ideal para integraciones que necesitan solo los datos.
        """
        if not self._cached_schema:
            return {{"error": "Esquema no disponible", "sql": None, "results": None}}

        try:
            sql = self._text_to_sql(natural_query)
        except Exception as e:
            return {{"error": str(e), "sql": None, "results": None}}

        success, results = self._execute_sql(sql)

        if not success:
            return {{"error": results, "sql": sql, "results": None}}

        return {{"error": None, "sql": sql, "results": results, "count": len(results)}}
'''

APP_PY_TEXT2SQL_RETRY_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (Text-to-SQL con Reintentos)
"""

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "text2sql_retry",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok"}}


@app.get("/schema")
async def schema():
    """Devuelve el esquema de la base de datos."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {{"schema": agent.get_schema()}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.
    Convierte la pregunta a SQL con reintentos automáticos, ejecuta y formatea resultados.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                if event_type == "content":
                    yield content

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

APP_TEXT2SQL_PURO_TEMPLATE = '''"""
Text2SQL Codestral - Servidor FastAPI optimizado para velocidad.
"""

import os
from contextlib import asynccontextmanager
from typing import Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "text2sql_puro",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    sql: Optional[str]
    results: Optional[List[dict]]
    count: Optional[int]
    error: Optional[str]


@app.get("/")
async def root():
    """Informacion del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok", "model": agent.model if agent else "not_loaded"}}


@app.get("/schema")
async def schema():
    """Devuelve el esquema de la BD."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {{"schema": agent.get_schema()}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint de chat: pregunta natural -> SQL -> resultados formateados.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                if event_type == "content":
                    yield content

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Endpoint directo: devuelve SQL y datos JSON (sin formateo).
    Ideal para integraciones programaticas.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    result = agent.query(request.query)
    return QueryResponse(**result)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

README_TEXT2SQL_RETRY_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente Text-to-SQL con Reintentos (Autocorrección)

## Cómo funciona

Este agente convierte preguntas en lenguaje natural a consultas SQL con **autocorrección automática**:

1. **Análisis**: El LLM analiza tu pregunta y el esquema de la base de datos
2. **Generación SQL**: Convierte la pregunta a una consulta SQL válida
3. **Ejecución**: Ejecuta la consulta en la base de datos SQLite local
4. **Reintento** (si falla): Si hay error, el LLM recibe el error y genera una nueva consulta (hasta 3 intentos)
5. **Formateo**: El LLM presenta los resultados de forma clara y amigable

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Configura tu LLM en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. **IMPORTANTE**: Crea tu base de datos SQLite en `data/database.db`:
```bash
sqlite3 data/database.db < tu_esquema.sql
```

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

## Ejemplos de uso

Una vez configurada la base de datos, puedes hacer preguntas como:

- "¿Cuántos clientes hay en total?"
- "Muéstrame los clientes de Madrid"
- "¿Cuál es el producto más vendido?"

Si el SQL generado tiene un error (ej: nombre de columna incorrecto), el agente automáticamente lo corregirá.

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /schema` - Ver esquema de la base de datos
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar pregunta en lenguaje natural

## Estructura

```
{agent_id}/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica Text-to-SQL con reintentos
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── database.db    # Base de datos SQLite (debes crearla)
```

## Seguridad

El agente solo permite consultas SELECT por seguridad:
- No se pueden ejecutar INSERT, UPDATE, DELETE
- No se permite DROP, CREATE, ALTER
- Los comentarios SQL (--) están bloqueados
'''

README_TEXT2SQL_PURO_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente Text-to-SQL Codestral (Ultra-rapido)

## Caracteristicas

- **Velocidad maxima**: Usa Codestral, el modelo de codigo mas rapido de Mistral
- **Sin formateo LLM**: Los resultados se formatean localmente, sin llamadas extra
- **API simple**: Endpoints `/chat` (formateado) y `/query` (JSON directo)
- **Cache de esquema**: El esquema se carga una sola vez al iniciar

## Instalacion

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuracion

1. Configura tu API key de Mistral en `.env`:
```
MISTRAL_API_KEY=tu_api_key
CODESTRAL_MODEL=codestral-latest
```

2. **IMPORTANTE**: Crea tu base de datos SQLite en `data/database.db`

3. (Opcional) Crea `data/database_schema.md` con descripciones semanticas

## Ejecucion

```bash
./run.sh
# o
python app.py
```

El servidor estara disponible en http://localhost:8000

## Endpoints

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/` | GET | Info del agente |
| `/health` | GET | Health check |
| `/schema` | GET | Esquema de la BD |
| `/chat` | POST | Consulta natural -> respuesta formateada |
| `/query` | POST | Consulta natural -> SQL + JSON (mas rapido) |

### Ejemplo /query (mas rapido)

```bash
curl -X POST http://localhost:8000/query \\
  -H "Content-Type: application/json" \\
  -d \'{{"query": "Cuantos usuarios hay?"}}\'
```

Respuesta:
```json
{{
  "sql": "SELECT COUNT(*) as total FROM users",
  "results": [{{"total": 150}}],
  "count": 1,
  "error": null
}}
```

## Optimizaciones para velocidad

1. **Codestral**: Modelo especializado en codigo, 2-3x mas rapido
2. **Prompt minimalista**: Sin instrucciones largas
3. **Sin LLM de formateo**: Tablas generadas localmente
4. **Cache de esquema**: Cargado una vez al iniciar
5. **temperature=0**: Respuestas deterministas

## Estructura

```
{agent_id}/
├── .env                # API key
├── requirements.txt    # Dependencias minimas
├── agent.py           # Logica Text-to-SQL con Codestral
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecucion
└── data/
    ├── database.db    # Base de datos SQLite
    └── database_schema.md  # Esquema (opcional)
```

## Seguridad

Solo consultas SELECT permitidas por seguridad.
'''

APP_PY_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (Oneshot)
"""

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "oneshot",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok"}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

APP_PY_RAG_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (RAG)
"""

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "rag",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok"}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat con RAG.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.post("/reindex")
async def reindex():
    """Reindexa los documentos en data/docs/"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    count = agent.reindex()
    return {{"status": "ok", "indexed_chunks": count}}


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

APP_PY_TOOLCALL_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (Toolcall)
"""

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "toolcall",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


def load_workspace_content() -> str:
    """Carga el contenido del workspace desde data/data.md."""
    data_path = os.path.join(os.path.dirname(__file__), "data", "data.md")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def build_system_prompt() -> str:
    """Construye el system prompt completo con los datos del workspace."""
    workspace_content = load_workspace_content()

    base_prompt = """{system_prompt}"""

    if workspace_content:
        return f"{{base_prompt}}\n\nDatos disponibles:\n{{workspace_content}}"
    return base_prompt


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    system_prompt = build_system_prompt()
    agent = Agent(system_prompt=system_prompt)
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok"}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.

    Body:
        message: Mensaje del usuario
        history: Historial de conversación (opcional)
        stream: Si es True, devuelve streaming (opcional)
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                # event_type puede ser "status" o "content"
                # Solo emitimos el contenido al frontend
                if event_type == "content":
                    yield content

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

APP_PY_TEXT2SQL_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (Text-to-SQL)
"""

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "text2sql",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok"}}


@app.get("/schema")
async def schema():
    """Devuelve el esquema de la base de datos."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {{"schema": agent.get_schema()}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.
    Convierte la pregunta a SQL, ejecuta y formatea resultados.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                if event_type == "content":
                    yield content

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

# ============================================================================
# APP CONSULTABD_SQL
# ============================================================================

APP_CONSULTABD_SQL_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (ConsultaBD_SQL)
"""

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {{
    "id": "{agent_id}",
    "name": "{agent_name}",
    "type": "consultabd_sql",
    "description": "{description}",
    "welcome_message": "{welcome_message}",
    "example_queries": {example_queries}
}}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "ok"}}


@app.get("/schema")
async def schema():
    """Devuelve el esquema de la base de datos."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {{"schema": agent.get_schema()}}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.
    Convierte la pregunta a SQL, ejecuta y formatea resultados.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                if event_type == "content":
                    yield content

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {{"examples": AGENT_CONFIG["example_queries"]}}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
'''

DATA_MD_TEMPLATE = '''# Datos para {agent_name}

Añade aquí la información que el agente usará para responder preguntas.

## Sección 1

Contenido...

## Sección 2

Contenido...
'''

RUN_SH_TEMPLATE = '''#!/bin/bash
cd "$(dirname "$0")"

# Puerto configurable (por defecto 8000)
PORT=${{PORT:-8000}}

# Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi

# Activar entorno
source .venv/bin/activate

# Instalar dependencias
pip install -q -r requirements.txt

# Ejecutar servidor
echo "Iniciando servidor en http://localhost:$PORT"
PORT=$PORT python app.py
'''

# Template especial para RAG que requiere Python 3.12 (ChromaDB incompatible con 3.14+)
RUN_SH_RAG_TEMPLATE = '''#!/bin/bash
cd "$(dirname "$0")"

# Puerto configurable (por defecto 8000)
PORT=${{PORT:-8000}}

# RAG agents requieren Python <= 3.13 (ChromaDB incompatible con 3.14+)
# Buscar Python compatible
PYTHON_CMD=""
for cmd in python3.12 python3.13 python3.11; do
    if command -v $cmd &> /dev/null; then
        PYTHON_CMD=$cmd
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Se requiere Python 3.11, 3.12 o 3.13 para agentes RAG"
    echo "       ChromaDB no es compatible con Python 3.14+"
    echo "       Instala Python 3.12: brew install python@3.12"
    exit 1
fi

echo "Usando $PYTHON_CMD"

# Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual con $PYTHON_CMD..."
    $PYTHON_CMD -m venv .venv
fi

# Activar entorno
source .venv/bin/activate

# Instalar dependencias
pip install -q -r requirements.txt

# Ejecutar servidor
echo "Iniciando servidor en http://localhost:$PORT"
PORT=$PORT python app.py
'''

README_TEMPLATE = '''# {agent_name}

{description}

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Copia tu API key de Mistral en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. Edita `data/data.md` con la información de tu agente.

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

Para usar un puerto diferente: `PORT=8001 ./run.sh`

## Interacción por terminal

También puedes interactuar directamente desde el terminal sin servidor web:

```bash
cd web
source .venv/bin/activate
python cli.py {agent_id}
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar mensaje

### Ejemplo de uso con curl

```bash
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Hola, ¿qué puedes hacer?"}}'
```

## Estructura

```
{agent_id}/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── data.md        # Datos del agente
```
'''

README_RAG_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente RAG (Retrieval-Augmented Generation)

> ⚠️ **IMPORTANTE**: Los agentes RAG requieren Python 3.11, 3.12 o 3.13.
> ChromaDB **no es compatible con Python 3.14+**. Si ves el error 307, usa una versión anterior de Python.

## Instalación

```bash
# Crear entorno virtual (requiere Python 3.11-3.13)
python3.12 -m venv .venv  # o python3.13, python3.11
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Copia tu API key de Mistral en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. Añade tus documentos en `data/docs/` (formatos soportados: .txt, .md)

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

Para usar un puerto diferente: `PORT=8001 ./run.sh`

## Interacción por terminal

También puedes interactuar directamente desde el terminal sin servidor web:

```bash
cd web
source .venv/bin/activate
python cli.py {agent_id}
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar mensaje (busca contexto relevante automáticamente)
- `POST /reindex` - Reindexa los documentos (usar después de añadir nuevos)

### Ejemplo de uso con curl

```bash
# Chat normal
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "¿Qué información tienes sobre X?"}}'

# Reindexar documentos
curl -X POST http://localhost:8000/reindex
```

## Estructura

```
{agent_id}/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente con RAG
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    ├── docs/          # Documentos a indexar (.txt, .md)
    └── chroma_db/     # Base de datos vectorial (se genera automáticamente)
```

## Cómo funciona

1. Al iniciar, el agente indexa todos los documentos en `data/docs/`
2. Cuando recibes una pregunta, busca los fragmentos más relevantes
3. Incluye ese contexto en el prompt para generar una respuesta informada
'''

README_TOOLCALL_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente con Function Calling (Toolcall)

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Copia tu API key de Mistral en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. Personaliza las herramientas en `agent.py` (ver sección "Añadir herramientas")

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

Para usar un puerto diferente: `PORT=8001 ./run.sh`

## Interacción por terminal

También puedes interactuar directamente desde el terminal sin servidor web:

```bash
cd web
source .venv/bin/activate
python cli.py {agent_id}
```

## Herramientas incluidas

- `obtener_hora_actual` - Devuelve la fecha y hora actual
- `calcular` - Calcula expresiones matemáticas
- `buscar_en_datos` - Busca información en data/data.md
- `consultar_sql` - Ejecuta consultas SELECT en la base de datos SQLite
- `listar_tablas` - Lista las tablas disponibles en la base de datos
- `describir_tabla` - Muestra la estructura de una tabla

## Configurar base de datos SQL

Para usar las herramientas SQL, crea una base de datos SQLite en `data/database.db`:

```bash
# Crear base de datos de ejemplo
sqlite3 data/database.db << 'EOF'
CREATE TABLE productos (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    precio REAL,
    stock INTEGER
);

INSERT INTO productos VALUES (1, 'Laptop', 999.99, 10);
INSERT INTO productos VALUES (2, 'Mouse', 29.99, 50);
INSERT INTO productos VALUES (3, 'Teclado', 79.99, 30);
EOF
```

El agente podrá consultar la base de datos con preguntas como:
- "¿Qué tablas hay en la base de datos?"
- "¿Cuál es la estructura de la tabla productos?"
- "Muéstrame los productos con precio mayor a 50"

## Añadir herramientas

Para añadir una nueva herramienta, edita `agent.py`:

1. Define la función:
```python
def mi_herramienta(parametro: str) -> str:
    \"\"\"Descripción de lo que hace.\"\"\"
    # Tu código aquí
    return resultado
```

2. Añádela al mapeo:
```python
AVAILABLE_TOOLS = {{
    ...
    "mi_herramienta": mi_herramienta,
}}
```

3. Añade la especificación:
```python
TOOLS_SPEC.append({{
    "type": "function",
    "function": {{
        "name": "mi_herramienta",
        "description": "Descripción para el modelo",
        "parameters": {{
            "type": "object",
            "properties": {{
                "parametro": {{
                    "type": "string",
                    "description": "Descripción del parámetro"
                }}
            }},
            "required": ["parametro"]
        }}
    }}
}})
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar mensaje (ejecuta herramientas automáticamente)

### Ejemplo de uso con curl

```bash
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "¿Qué hora es?"}}'

curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Calcula 25 * 4 + 100"}}'
```

## Estructura

```
{agent_id}/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica del agente + definición de herramientas
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── data.md        # Datos para la herramienta buscar_en_datos
```
'''

README_TEXT2SQL_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente Text-to-SQL (Consultas en lenguaje natural)

## Cómo funciona

Este agente convierte preguntas en lenguaje natural a consultas SQL:

1. **Análisis**: El LLM analiza tu pregunta y el esquema de la base de datos
2. **Generación SQL**: Convierte la pregunta a una consulta SQL válida
3. **Ejecución**: Ejecuta la consulta en la base de datos SQLite local
4. **Formateo**: El LLM presenta los resultados de forma clara y amigable

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Configura tu LLM en `.env`:
```
MISTRAL_API_KEY=tu_api_key
```

2. **IMPORTANTE**: Crea tu base de datos SQLite en `data/database.db`:
```bash
# Ejemplo: crear base de datos desde un archivo SQL
sqlite3 data/database.db < tu_esquema.sql

# O crear tablas manualmente
sqlite3 data/database.db << 'EOF'
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    email TEXT,
    ciudad TEXT
);

INSERT INTO clientes VALUES (1, 'Ana García', 'ana@email.com', 'Madrid');
INSERT INTO clientes VALUES (2, 'Carlos López', 'carlos@email.com', 'Barcelona');
EOF
```

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

## Ejemplos de uso

Una vez configurada la base de datos, puedes hacer preguntas como:

- "¿Cuántos clientes hay en total?"
- "Muéstrame los clientes de Madrid"
- "¿Cuál es el producto más vendido?"
- "Dame las ventas del último mes ordenadas por fecha"

### Con curl

```bash
# Pregunta simple
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "¿Cuántos registros hay en la tabla clientes?"}}'

# Ver el esquema de la BD
curl http://localhost:8000/schema
```

## Interacción por terminal

```bash
cd web
source .venv/bin/activate
python cli.py {agent_id}
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /schema` - Ver esquema de la base de datos
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar pregunta en lenguaje natural

## Estructura

```
{agent_id}/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica Text-to-SQL
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── database.db    # Base de datos SQLite (debes crearla)
```

## Seguridad

El agente solo permite consultas SELECT por seguridad:
- No se pueden ejecutar INSERT, UPDATE, DELETE
- No se permite DROP, CREATE, ALTER
- Los comentarios SQL (--) están bloqueados

## Consejos

- **Esquema claro**: Usa nombres de tablas y columnas descriptivos
- **Datos de ejemplo**: Añade algunos registros para probar
- **Preguntas específicas**: Cuanto más específica la pregunta, mejor el SQL generado
'''

# ============================================================================
# README CONSULTABD_SQL
# ============================================================================

README_CONSULTABD_SQL_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente ConsultaBD_SQL (Consultas en lenguaje natural a SQL)

## Cómo funciona

Este agente convierte preguntas en lenguaje natural a consultas SQL:

1. **Análisis**: El LLM analiza tu pregunta y el esquema de la base de datos
2. **Generación SQL**: Convierte la pregunta a una consulta SQL válida
3. **Ejecución**: Ejecuta la consulta en la base de datos SQLite local
4. **Formateo**: El LLM presenta los resultados de forma clara y amigable

## Instalación

```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Configura tu LLM en `.env` (Mistral Cloud u Ollama)

2. **IMPORTANTE**: Crea tu base de datos SQLite en `data/database.db`:
```bash
# Ejemplo: crear base de datos desde un archivo SQL
sqlite3 data/database.db < tu_esquema.sql

# O crear tablas manualmente
sqlite3 data/database.db << 'EOF'
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    email TEXT,
    ciudad TEXT
);

INSERT INTO clientes VALUES (1, 'Ana García', 'ana@email.com', 'Madrid');
INSERT INTO clientes VALUES (2, 'Carlos López', 'carlos@email.com', 'Barcelona');
EOF
```

## Ejecución

```bash
# Opción 1: Script automático
./run.sh

# Opción 2: Manual
source .venv/bin/activate
python app.py
```

El servidor estará disponible en http://localhost:8000

## Ejemplos de uso

Una vez configurada la base de datos, puedes hacer preguntas como:

- "¿Cuántos clientes hay en total?"
- "Muéstrame los clientes de Madrid"
- "¿Cuál es el producto más vendido?"
- "Dame las ventas del último mes ordenadas por fecha"

### Con curl

```bash
# Pregunta simple
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "¿Cuántos registros hay en la tabla clientes?"}}'

# Ver el esquema de la BD
curl http://localhost:8000/schema
```

## Interacción por terminal

```bash
cd web
source .venv/bin/activate
python cli.py {agent_id}
```

## API Endpoints

- `GET /` - Información del agente
- `GET /health` - Health check
- `GET /schema` - Ver esquema de la base de datos
- `GET /examples` - Preguntas de ejemplo
- `POST /chat` - Enviar pregunta en lenguaje natural

## Estructura

```
{agent_id}/
├── .env                # API key (no subir a git)
├── requirements.txt    # Dependencias
├── agent.py           # Lógica ConsultaBD_SQL
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
└── data/
    └── database.db    # Base de datos SQLite (debes crearla)
```

## Seguridad

El agente solo permite consultas SELECT por seguridad:
- No se pueden ejecutar INSERT, UPDATE, DELETE
- No se permite DROP, CREATE, ALTER
- Los comentarios SQL (--) están bloqueados

## Consejos

- **Esquema claro**: Usa nombres de tablas y columnas descriptivos
- **Datos de ejemplo**: Añade algunos registros para probar
- **Preguntas específicas**: Cuanto más específica la pregunta, mejor el SQL generado
'''


def get_agents_dir() -> str:
    """Obtiene la ruta de la carpeta agents en tommi2."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(script_dir), "agents")


def input_with_default(prompt: str, default: str = "") -> str:
    """Solicita input con valor por defecto."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def input_multiline(prompt: str) -> str:
    """Solicita input multilínea (termina con línea vacía)."""
    print(f"{prompt} (línea vacía para terminar):")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("  Crear Agente (FastAPI + Mistral/Ollama)")
    print("=" * 60)
    print()

    # 1. Tipo de agente
    print("Tipos de agente disponibles:")
    print("  1. oneshot        - Agente simple con prompt y datos estáticos")
    print("  2. rag            - Agente con búsqueda semántica en documentos (ChromaDB)")
    print("  3. consultabd_sql - Agente que convierte lenguaje natural a SQL (Text2SQL)")
    print()

    agent_type = ""
    while agent_type not in ["1", "2", "3", "oneshot", "rag", "consultabd_sql"]:
        agent_type = input("Tipo de agente [1/2/3]: ").strip().lower()

    # Normalizar tipo
    type_map = {"1": "oneshot", "2": "rag", "3": "consultabd_sql"}
    agent_type = type_map.get(agent_type, agent_type)
    print(f"  → Tipo seleccionado: {agent_type}")

    # Advertencia para RAG si Python 3.14+
    if agent_type == "rag":
        import platform
        py_version = tuple(map(int, platform.python_version().split('.')[:2]))
        if py_version >= (3, 14):
            print()
            print("  ⚠️  ADVERTENCIA: Estás usando Python 3.14+")
            print("     ChromaDB NO es compatible con esta versión.")
            print("     El agente mostrará Error 307 al intentar usarse.")
            print("     Solución: Instala Python 3.12 o 3.13:")
            print("       brew install python@3.12")
            print("     El script run.sh buscará automáticamente una versión compatible.")
            print()
            confirm_rag = input("  ¿Continuar de todos modos? (s/n): ").strip().lower()
            if confirm_rag != "s":
                print("Cancelado.")
                sys.exit(0)

    print()

    # 2. Nombre del agente (ID)
    agent_id = ""
    while not agent_id:
        agent_id = input("Nombre del agente (sin espacios ni mayúsculas): ").strip().lower()
        if " " in agent_id or not agent_id.replace("_", "").replace("-", "").isalnum():
            print("  Error: usa solo letras minúsculas, números, guiones o guiones bajos")
            agent_id = ""

    # 3. Directorio de salida (dentro de tommi2/agents/)
    agents_base = get_agents_dir()
    default_output = os.path.join(agents_base, agent_id)
    output_dir = input_with_default("Directorio de salida", default_output)

    # 4. Nombre público del agente
    agent_name = input_with_default("Nombre público del agente", agent_id.replace("_", " ").title())

    # 5. Descripción
    description = input_with_default("Descripción corta del agente", f"Asistente {agent_name}")

    # 6. Mensaje de bienvenida
    welcome = input_with_default(
        "Mensaje de bienvenida",
        f"¡Hola! Soy {agent_name}. ¿En qué puedo ayudarte?"
    )

    # 7. Preguntas de ejemplo
    print("\nPreguntas de ejemplo (una por línea, línea vacía para terminar):")
    examples = []
    while True:
        ex = input(f"  Pregunta {len(examples) + 1}: ").strip()
        if not ex:
            break
        examples.append(ex)
    if not examples:
        if agent_type == "rag":
            examples = ["¿Qué información tienes?", "Busca sobre X"]
        elif agent_type == "consultabd_sql":
            examples = ["¿Cuántos registros hay?", "Muéstrame los últimos 10 registros"]
        else:
            examples = ["¿Qué puedes hacer?", "Dame información"]

    # 8. System prompt - seleccionar de plantillas disponibles
    print("\nSystem prompt:")

    # List available templates
    templates = list_prompt_templates(agent_type)

    if templates:
        print("  Plantillas disponibles:")
        for i, (name, _) in enumerate(templates, 1):
            print(f"    {i}. {name}")
        print()

        template_choice = ""
        valid_choices = [str(i) for i in range(1, len(templates) + 1)]
        while template_choice not in valid_choices:
            template_choice = input(f"  Selecciona plantilla [1-{len(templates)}]: ").strip()

        template_idx = int(template_choice) - 1
        template_name, template_path = templates[template_idx]
        system_prompt = load_prompt_template(template_path, agent_name)
        print(f"  → Plantilla cargada: {template_name}")
    else:
        # No templates found, use default prompt
        print("  (No se encontraron plantillas en prompts/)")
        system_prompt = ""

    # Prompt por defecto si no hay plantillas
    if not system_prompt:
        if agent_type == "rag":
            system_prompt = f"Eres {agent_name}, un asistente útil. Responde preguntas basándote en el contexto proporcionado de la base de conocimiento. Si no encuentras información relevante, dilo claramente."
        elif agent_type == "consultabd_sql":
            system_prompt = f"Eres {agent_name}, un asistente especializado en consultas de bases de datos. Ayudas a los usuarios a obtener información de la base de datos respondiendo sus preguntas en lenguaje natural."
        else:
            system_prompt = f"Eres {agent_name}, un asistente útil. Responde preguntas basándote en los datos proporcionados."

    # 9. Proveedor LLM
    print("\nConfiguración LLM:")
    print("  1. default  - Usar configuración de web/.env (recomendado)")
    print("  2. mistral  - Configurar Mistral Cloud específico para este agente")
    print("  3. ollama   - Configurar Ollama específico para este agente")
    print()

    llm_provider = ""
    while llm_provider not in ["1", "2", "3", "default", "mistral", "ollama"]:
        llm_provider = input("Configuración LLM [1/2/3]: ").strip().lower()

    provider_map = {"1": "default", "2": "mistral", "3": "ollama"}
    llm_provider = provider_map.get(llm_provider, llm_provider)
    print(f"  → Configuración seleccionada: {llm_provider}")

    # 10. Configuración según proveedor
    api_key = ""
    ollama_url = ""
    ollama_model = ""
    model = "mistral-large-latest"  # Default

    if llm_provider == "mistral":
        print("\nModelos Mistral: mistral-large-latest, mistral-medium-latest, mistral-small-latest")
        model = input_with_default("Modelo", "mistral-large-latest")
        api_key = input("API Key de Mistral (o déjalo vacío para añadirla después): ").strip()
        if not api_key:
            api_key = "TU_API_KEY_AQUI"
    elif llm_provider == "ollama":
        ollama_url = input_with_default("URL de Ollama", "http://localhost:11434")
        print("\nModelos Ollama comunes: mistral-large:latest, mistral, llama3, codellama, phi3")
        ollama_model = input_with_default("Modelo Ollama", "mistral-large:latest")
        model = ollama_model
    # else: default - no necesita configuración adicional

    # Confirmar
    print("\n" + "=" * 60)
    print("Resumen:")
    print("=" * 60)
    print(f"  Tipo:         {agent_type}")
    print(f"  ID:           {agent_id}")
    print(f"  Directorio:   {output_dir}/")
    print(f"  Nombre:       {agent_name}")
    if llm_provider == "default":
        print(f"  LLM:          Usa configuración de web/.env")
    else:
        print(f"  Proveedor:    {llm_provider}")
        print(f"  Modelo:       {model}")
        if llm_provider == "ollama":
            print(f"  URL Ollama:   {ollama_url}")
    print(f"  Ejemplos:     {len(examples)} pregunta(s)")
    print("=" * 60)

    confirm = input("\n¿Crear agente? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        sys.exit(0)

    # Crear estructura
    print("\nCreando estructura...")

    # Asegurar que existe la carpeta agents de tommi2
    os.makedirs(get_agents_dir(), exist_ok=True)

    # Directorio principal y data
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Para RAG, crear directorio de documentos
    if agent_type == "rag":
        docs_dir = os.path.join(data_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

    # requirements.txt según tipo
    requirements_map = {
        "oneshot": REQUIREMENTS_ONESHOT,
        "rag": REQUIREMENTS_RAG,
        "consultabd_sql": REQUIREMENTS_CONSULTABD_SQL
    }
    with open(os.path.join(output_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(requirements_map[agent_type])
    print(f"  ✓ {output_dir}/requirements.txt")

    # .env según proveedor
    with open(os.path.join(output_dir, ".env"), "w", encoding="utf-8") as f:
        if llm_provider == "default":
            f.write(ENV_TEMPLATE_DEFAULT)
        elif llm_provider == "mistral":
            f.write(ENV_TEMPLATE_MISTRAL.format(api_key=api_key, model=model))
        elif llm_provider == "ollama":
            f.write(ENV_TEMPLATE_OLLAMA.format(ollama_url=ollama_url, ollama_model=ollama_model))
    print(f"  ✓ {output_dir}/.env")

    # .gitignore
    gitignore_content = GITIGNORE
    if agent_type == "rag":
        gitignore_content += "data/chroma_db/\n"
    with open(os.path.join(output_dir, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(gitignore_content)
    print(f"  ✓ {output_dir}/.gitignore")

    # agent.py según tipo
    agent_templates = {
        "oneshot": AGENT_PY_TEMPLATE,
        "rag": AGENT_RAG_TEMPLATE,
        "consultabd_sql": AGENT_CONSULTABD_SQL_TEMPLATE
    }
    agent_content = agent_templates[agent_type].format(
        agent_id=agent_id,
        agent_name=agent_name,
        model=model,
        system_prompt=system_prompt.replace('"', '\\"').replace("'", "\\'")
    )
    with open(os.path.join(output_dir, "agent.py"), "w", encoding="utf-8") as f:
        f.write(agent_content)
    print(f"  ✓ {output_dir}/agent.py")

    # app.py según tipo
    app_templates = {
        "oneshot": APP_PY_TEMPLATE,
        "rag": APP_PY_RAG_TEMPLATE,
        "consultabd_sql": APP_CONSULTABD_SQL_TEMPLATE
    }
    app_content = app_templates[agent_type].format(
        agent_id=agent_id,
        agent_name=agent_name,
        description=description,
        welcome_message=welcome,
        example_queries=json.dumps(examples, ensure_ascii=False),
        system_prompt=system_prompt.replace('"', '\\"').replace("'", "\\'")
    )
    with open(os.path.join(output_dir, "app.py"), "w", encoding="utf-8") as f:
        f.write(app_content)
    print(f"  ✓ {output_dir}/app.py")

    # data/data.md (para oneshot) o ejemplo en docs/ (para rag) o README para consultabd_sql
    if agent_type == "rag":
        example_doc = f"# Ejemplo de documento para {agent_name}\n\nAñade aquí tu contenido.\n\nEste archivo será indexado automáticamente al iniciar el agente.\n"
        with open(os.path.join(docs_dir, "ejemplo.md"), "w", encoding="utf-8") as f:
            f.write(example_doc)
        print(f"  ✓ {docs_dir}/ejemplo.md")
    elif agent_type == "consultabd_sql":
        # Para consultabd_sql, crear un README explicando cómo crear la BD
        db_readme = f"""# Base de datos para {agent_name}

Crea aquí tu base de datos SQLite llamada `database.db`.

## Ejemplo de creación

```bash
sqlite3 database.db << 'EOF'
CREATE TABLE ejemplo (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    valor REAL
);

INSERT INTO ejemplo VALUES (1, 'Item 1', 100.0);
INSERT INTO ejemplo VALUES (2, 'Item 2', 200.0);
EOF
```

## Importar desde CSV

```bash
sqlite3 database.db << 'EOF'
.mode csv
.import tu_archivo.csv nombre_tabla
EOF
```

Una vez creada la BD, el agente podrá responder preguntas en lenguaje natural.
"""
        with open(os.path.join(data_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(db_readme)
        print(f"  ✓ {data_dir}/README.md")
    else:
        data_content = DATA_MD_TEMPLATE.format(agent_name=agent_name)
        with open(os.path.join(data_dir, "data.md"), "w", encoding="utf-8") as f:
            f.write(data_content)
        print(f"  ✓ {data_dir}/data.md")

    # run.sh (usa template especial para RAG por compatibilidad con Python)
    run_sh_template = RUN_SH_RAG_TEMPLATE if agent_type == "rag" else RUN_SH_TEMPLATE
    with open(os.path.join(output_dir, "run.sh"), "w", encoding="utf-8") as f:
        f.write(run_sh_template)
    os.chmod(os.path.join(output_dir, "run.sh"), 0o755)
    print(f"  ✓ {output_dir}/run.sh")

    # README.md según tipo
    readme_templates = {
        "oneshot": README_TEMPLATE,
        "rag": README_RAG_TEMPLATE,
        "consultabd_sql": README_CONSULTABD_SQL_TEMPLATE
    }
    readme_content = readme_templates[agent_type].format(
        agent_id=agent_id,
        agent_name=agent_name,
        description=description
    )
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"  ✓ {output_dir}/README.md")

    print("\n" + "=" * 60)
    print(f"¡Agente {agent_type.upper()} creado!")
    print("=" * 60)

    # Mostrar estructura según tipo
    print(f"\nEstructura generada:")
    print(f"  {output_dir}/")
    print(f"  ├── .env              # API key")
    print(f"  ├── requirements.txt  # Dependencias")
    print(f"  ├── agent.py          # Lógica del agente")
    print(f"  ├── app.py            # Servidor FastAPI")
    print(f"  ├── run.sh            # Script de ejecución")
    print(f"  ├── README.md         # Documentación")
    print(f"  └── data/")
    if agent_type == "rag":
        print(f"      └── docs/         # Documentos a indexar")
    elif agent_type == "consultabd_sql":
        print(f"      └── database.db   # Base de datos SQLite (debes crearla)")
    else:
        print(f"      └── data.md       # Datos del agente")

    print()
    print("Próximos pasos:")
    step = 1
    if agent_type == "rag":
        print(f"  {step}. Añade documentos (.txt, .md) en {data_dir}/docs/")
    elif agent_type == "consultabd_sql":
        print(f"  {step}. Crea tu base de datos SQLite en {data_dir}/database.db")
    else:
        print(f"  {step}. Edita {data_dir}/data.md con tus datos")
    step += 1

    if llm_provider == "default":
        print(f"  {step}. Asegúrate de que web/.env tiene la configuración LLM correcta")
        step += 1
    elif api_key == "TU_API_KEY_AQUI":
        print(f"  {step}. Añade tu API key en {output_dir}/.env")
        step += 1

    print(f"  {step}. Ejecuta:")
    print(f"     - (Linux/Mac) cd web && ./run_html_server.sh")
    print(f"     - (Windows) cd web && run_html_server.bat")
    step += 1
    print(f"  {step}. Abre: http://localhost:8000")
    step += 1
    print(f"  {step}. O usa el CLI directo: cd web && python cli.py {agent_id}")

    print()
    print("Endpoints disponibles:")
    print("  GET  /         - Info del agente")
    print("  GET  /examples - Preguntas de ejemplo")
    print("  POST /chat     - Enviar mensaje")
    if agent_type == "rag":
        print("  POST /reindex  - Reindexar documentos")
        print()
        print("⚠️  NOTA: Los agentes RAG requieren Python 3.11-3.13")
        print("   ChromaDB no es compatible con Python 3.14+")
        print("   El script run.sh detectará automáticamente la versión correcta")
    elif agent_type == "consultabd_sql":
        print("  GET  /schema   - Ver esquema de la base de datos")
        print()
        print("📝 NOTA: Debes crear la base de datos SQLite en data/database.db")
        print("   Ejemplo: sqlite3 data/database.db < tu_esquema.sql")
    print()


if __name__ == "__main__":
    main()
