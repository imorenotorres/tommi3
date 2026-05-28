#!/usr/bin/env python3
"""
Script para crear agentes independientes con FastAPI + LLM.
Soporta Mistral Cloud y Ollama como proveedores de LLM.
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
        agent_type: Tipo de agente (oneshot, rag, text2sql)

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
        "rag_vectorless": ["prompt_RAG.txt"],
        "rag": ["prompt_RAG.txt"],
        "rag_metadata": ["prompt_RAG_Metadata.txt"],
        "text2sql": ["prompt_Text2SQL.txt"]
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

REQUIREMENTS_RAG_METADATA = """fastapi>=0.115.0
uvicorn>=0.32.0
mistralai>=1.0.0
ollama>=0.3.0
openai>=1.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
pypdf>=4.0.0
cryptography>=3.1
"""

REQUIREMENTS_TEXT2SQL = """fastapi>=0.115.0
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
import json
import re

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.system_prompt = self._build_system_prompt()
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Query history for the sidebar
        self._query_history = []

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
            return f"{{base_prompt}}\\n\\nDatos disponibles:\\n{{data}}"
        return base_prompt

    def _verify_grounding(self, response: str, user_question: str) -> dict:
        """
        Verifica si la respuesta está basada SOLO en los datos proporcionados.

        Args:
            response: Respuesta generada por el agente
            user_question: Pregunta original del usuario

        Returns:
            dict con {{"grounded": bool, "reason": str}}
        """
        data = self._load_data()

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided data.

AVAILABLE DATA:
{{data}}

USER QUESTION: {{user_question}}

AGENT RESPONSE: {{response}}

STRICT VERIFICATION RULES:
1. The response is "grounded" ONLY if ALL factual claims are EXPLICITLY written in the AVAILABLE DATA
2. It is NOT grounded if the response:
   - Infers or deduces information not explicitly stated
   - Adds relationships between entities that are not explicitly documented
   - Makes assumptions about events, contacts, or collaborations not explicitly mentioned
   - Uses names/data from the source but creates new claims about them
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly declines to answer, it IS grounded
5. BE VERY STRICT: if a claim cannot be found VERBATIM or nearly verbatim in the data, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{{{"grounded": true, "reason": "brief explanation"}}}}
or
{{{{"grounded": false, "reason": "specific claim that was not explicitly in the data"}}}}"""

        result = self.client.chat.complete(
            model=self.model,
            messages=[{{"role": "user", "content": verify_prompt}}]
        )

        try:
            content = result.choices[0].message.content.strip()
            # Limpiar posibles bloques de código markdown
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\\n?", "", content)
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            # Si falla el parsing, asumir que está grounded para no bloquear
            return {{"grounded": True, "reason": "Verification parsing failed"}}

    def _get_fallback_response(self, user_question: str) -> str:
        """Genera una respuesta cuando la verificación falla."""
        return (
            "I apologize, but I cannot find specific information about that in my database. "
            "I can only provide information that is explicitly documented. "
            "Could you please ask something else?"
        )

    def chat(self, user_message: str, history: list = None, verify: bool = None) -> str:
        """
        Envía un mensaje y obtiene respuesta.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos [{{"role": "user/assistant", "content": "..."}}]
            verify: Si True, verifica que la respuesta esté basada en los datos.
                    Si None, usa el valor de VERIFY_GROUNDING del .env

        Returns:
            Respuesta del agente (verificada si verify=True)
        """
        # Usar configuración del .env si no se especifica
        should_verify = verify if verify is not None else self.verify_grounding

        messages = [{{"role": "system", "content": self.system_prompt}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        response_content = response.choices[0].message.content

        if should_verify:
            verification = self._verify_grounding(response_content, user_message)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {{verification.get('reason', 'Unknown')}}")
                response_content = self._get_fallback_response(user_message)

        # Track query in history
        self._query_history.append({{
            'question': user_message,
            'response_length': len(response_content)
        }})

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, verify: bool = None):
        """
        Envía un mensaje y obtiene respuesta en streaming.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos
            verify: Si True, verifica la respuesta al final del streaming.
                    Si None, usa el valor de VERIFY_GROUNDING del .env

        Yields:
            Chunks de texto de la respuesta
        """
        # Usar configuración del .env si no se especifica
        should_verify = verify if verify is not None else self.verify_grounding

        messages = [{{"role": "system", "content": self.system_prompt}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        if should_verify:
            # Acumular respuesta completa para verificar
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content

            # Verificar después de obtener la respuesta completa
            verification = self._verify_grounding(full_response, user_message)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {{verification.get('reason', 'Unknown')}}")
                full_response = self._get_fallback_response(user_message)

            # Track query in history
            self._query_history.append({{
                'question': user_message,
                'response_length': len(full_response)
            }})
            yield full_response
        else:
            # Sin verificación: streaming normal
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content
                    yield chunk.data.choices[0].delta.content

            # Track query in history
            self._query_history.append({{
                'question': user_message,
                'response_length': len(full_response)
            }})

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {{
                'question': entry['question'],
                'num_results': 1  # For oneshot agents, each query = 1 result
            }}
            for entry in self._query_history
        ]
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
import json
import re
import warnings
import logging

# Suppress pypdf warnings about malformed PDFs
logging.getLogger("pypdf").setLevel(logging.ERROR)
# Suppress sentence-transformers position_ids warning
warnings.filterwarnings("ignore", message=".*position_ids.*")

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
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Query history for the sidebar
        self._query_history = []

        # RAG Chunking Configuration
        self._load_rag_config()

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

            # Indexar documentos nuevos automáticamente
            self._sync_documents()

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

    def _load_rag_config(self):
        """Load RAG chunking configuration from environment variables."""
        approach = os.getenv("RAG_APPROACH", "context_preserving").lower()

        if approach == "basic":
            self.chunk_size = 500
            self.chunk_overlap = 100
            self.retrieve_chunks = 3
            self.chunking_strategy = "fixed"
        elif approach == "context_preserving":
            self.chunk_size = 2000
            self.chunk_overlap = 400
            self.retrieve_chunks = 8
            self.chunking_strategy = "smart"
        else:  # custom
            self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "2000"))
            self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "400"))
            self.retrieve_chunks = int(os.getenv("RAG_RETRIEVE_CHUNKS", "8"))
            self.chunking_strategy = os.getenv("RAG_CHUNKING_STRATEGY", "smart").lower()

        print(f"RAG config: {{approach}} (chunks={{self.chunk_size}}, overlap={{self.chunk_overlap}}, retrieve={{self.retrieve_chunks}}, strategy={{self.chunking_strategy}})")

    def _extract_pdf_text(self, filepath: str) -> str:
        """Extrae texto de un archivo PDF."""
        try:
            reader = PdfReader(filepath)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\\n".join(text_parts)
        except Exception as e:
            print(f"Error extracting text from {{filepath}}: {{e}}")
            return ""

    def _get_indexed_sources(self) -> set:
        """Obtiene el conjunto de fuentes ya indexadas en ChromaDB."""
        if self.collection is None or self.collection.count() == 0:
            return set()

        # Obtener todos los metadatos para extraer fuentes únicas
        all_data = self.collection.get(include=["metadatas"])
        sources = set()
        for meta in all_data.get("metadatas", []):
            if meta and "source" in meta:
                sources.add(meta["source"])
        return sources

    def _get_docs_files(self) -> set:
        """Obtiene el conjunto de archivos en data/docs/."""
        docs_path = os.path.join(os.path.dirname(__file__), "data", "docs")
        if not os.path.exists(docs_path):
            return set()

        files = set()
        for filename in os.listdir(docs_path):
            filepath = os.path.join(docs_path, filename)
            if os.path.isfile(filepath) and filename.endswith(('.txt', '.md', '.pdf')):
                files.add(filename)
        return files

    def _sync_documents(self):
        """Sincroniza documentos: indexa nuevos y elimina huérfanos."""
        indexed = self._get_indexed_sources()
        on_disk = self._get_docs_files()

        # Documentos nuevos (en disco pero no indexados)
        new_docs = on_disk - indexed
        # Documentos eliminados (indexados pero ya no en disco)
        removed_docs = indexed - on_disk

        if not new_docs and not removed_docs:
            print(f"Documents in sync ({{len(indexed)}} indexed)")
            return

        # Eliminar documentos huérfanos de ChromaDB
        if removed_docs:
            print(f"Removing {{len(removed_docs)}} deleted documents from index...")
            for source in removed_docs:
                # Obtener IDs de chunks de este documento
                results = self.collection.get(where={{"source": source}})
                if results["ids"]:
                    self.collection.delete(ids=results["ids"])
            print(f"Removed: {{', '.join(removed_docs)}}")

        # Indexar documentos nuevos
        if new_docs:
            print(f"Indexing {{len(new_docs)}} new documents...")
            self._index_documents(only_files=new_docs)
            print(f"Added: {{', '.join(new_docs)}}")

    def _index_documents(self, only_files: set = None):
        """Indexa los documentos del directorio data/docs/

        Args:
            only_files: Si se especifica, solo indexa estos archivos.
                       Si es None, indexa todos los archivos.
        """
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
            # Si only_files está especificado, solo procesar esos archivos
            if only_files is not None and filename not in only_files:
                continue

            content = None
            if filename.endswith(('.txt', '.md')):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif filename.endswith('.pdf'):
                content = self._extract_pdf_text(filepath)

            if content:
                # Chunking based on configured strategy
                chunks = []
                if self.chunking_strategy == "smart":
                    # Smart chunking: try to cut at natural boundaries
                    start = 0
                    while start < len(content):
                        end = start + self.chunk_size
                        chunk = content[start:end]
                        # Try to cut at paragraph/sentence boundary
                        if end < len(content):
                            for sep in ['\\n\\n', '. ', '\\n']:
                                last_sep = chunk.rfind(sep)
                                if last_sep > self.chunk_size * 0.6:
                                    chunk = chunk[:last_sep + len(sep)]
                                    end = start + len(chunk)
                                    break
                        chunks.append(chunk.strip())
                        start = end - self.chunk_overlap
                else:
                    # Fixed chunking: cut at exact positions
                    step = self.chunk_size - self.chunk_overlap
                    chunks = [content[j:j+self.chunk_size] for j in range(0, len(content), step)]

                for k, chunk in enumerate(chunks):
                    if chunk:  # Only add non-empty chunks
                        documents.append(chunk)
                        metadatas.append({{"source": filename, "chunk": k}})
                        ids.append(f"{{filename}}_{{k}}")

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"Indexed {{len(documents)}} chunks from {{len(set(m['source'] for m in metadatas))}} documents")

    def _retrieve_context(self, query: str, n_results: int = None) -> str:
        """Recupera contexto relevante para la query.

        Args:
            query: The search query
            n_results: Number of chunks to retrieve (uses self.retrieve_chunks if None)
        """
        if n_results is None:
            n_results = self.retrieve_chunks
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
            context_parts.append(f"[Fuente: {{meta['source']}}]\\n{{doc}}")

        return "\\n\\n---\\n\\n".join(context_parts)

    def _verify_grounding(self, response: str, user_question: str, context: str) -> dict:
        """
        Verifica si la respuesta está basada SOLO en el contexto recuperado.

        Args:
            response: Respuesta generada por el agente
            user_question: Pregunta original del usuario
            context: Contexto recuperado de ChromaDB

        Returns:
            dict con {{"grounded": bool, "reason": str}}
        """
        if not context:
            # Sin contexto, no podemos verificar
            return {{"grounded": True, "reason": "No context to verify against"}}

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided context.

RETRIEVED CONTEXT:
{{context}}

USER QUESTION: {{user_question}}

AGENT RESPONSE: {{response}}

STRICT VERIFICATION RULES:
1. The response is "grounded" ONLY if ALL factual claims are EXPLICITLY written in the CONTEXT
2. It is NOT grounded if the response:
   - Infers or deduces information not explicitly stated in the context
   - Adds details, relationships, or facts not present in the context
   - Makes assumptions or generalizations beyond the context
   - Uses information that might be true but is not in the provided context
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly states it cannot find information, it IS grounded
5. BE VERY STRICT: if a claim cannot be found in the context, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{{{"grounded": true, "reason": "brief explanation"}}}}
or
{{{{"grounded": false, "reason": "specific claim that was not in the context"}}}}"""

        result = self.client.chat.complete(
            model=self.model,
            messages=[{{"role": "user", "content": verify_prompt}}]
        )

        try:
            content = result.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\\n?", "", content)
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return {{"grounded": True, "reason": "Verification parsing failed"}}

    def _get_fallback_response(self, user_question: str) -> str:
        """Genera una respuesta cuando la verificación falla."""
        return (
            "I apologize, but I cannot find specific information about that in my knowledge base. "
            "I can only provide information that is explicitly documented in my sources. "
            "Could you please ask something else or rephrase your question?"
        )

    def chat(self, user_message: str, history: list = None, verify: bool = None) -> str:
        """
        Envía un mensaje con contexto RAG y obtiene respuesta.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos
            verify: Si True, verifica que la respuesta esté basada en el contexto.
                    Si None, usa el valor de VERIFY_GROUNDING del .env
        """
        # Usar configuración del .env si no se especifica
        should_verify = verify if verify is not None else self.verify_grounding

        # Verificar si ChromaDB está disponible
        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {{err['error_code']}}:** {{err['error']}}\\n\\n{{err.get('instructions', '')}}"

        # Recuperar contexto relevante
        context = self._retrieve_context(user_message)

        # Construir prompt con contexto
        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\\n\\nContexto relevante de la base de conocimiento:\\n{{context}}"

        messages = [{{"role": "system", "content": system_with_context}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        response_content = response.choices[0].message.content

        if should_verify and context:
            verification = self._verify_grounding(response_content, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {{verification.get('reason', 'Unknown')}}")
                response_content = self._get_fallback_response(user_message)

        # Track query in history
        self._query_history.append({{
            'question': user_message,
            'response_length': len(response_content)
        }})

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, verify: bool = None):
        """
        Envía un mensaje con contexto RAG y obtiene respuesta en streaming.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos
            verify: Si True, verifica la respuesta al final del streaming.
                    Si None, usa el valor de VERIFY_GROUNDING del .env
        """
        # Usar configuración del .env si no se especifica
        should_verify = verify if verify is not None else self.verify_grounding

        # Verificar si ChromaDB está disponible
        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {{err['error_code']}}:** {{err['error']}}\\n\\n{{err.get('instructions', '')}}"
            return

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\\n\\nContexto relevante de la base de conocimiento:\\n{{context}}"

        messages = [{{"role": "system", "content": system_with_context}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        if should_verify and context:
            # Acumular respuesta completa para verificar
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content

            # Verificar después de obtener la respuesta completa
            verification = self._verify_grounding(full_response, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {{verification.get('reason', 'Unknown')}}")
                full_response = self._get_fallback_response(user_message)

            # Track query in history
            self._query_history.append({{
                'question': user_message,
                'response_length': len(full_response)
            }})
            yield full_response
        else:
            # Sin verificación: streaming normal
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content
                    yield chunk.data.choices[0].delta.content

            # Track query in history
            self._query_history.append({{
                'question': user_message,
                'response_length': len(full_response)
            }})

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {{
                'question': entry['question'],
                'num_results': 1  # For RAG agents, each query = 1 result
            }}
            for entry in self._query_history
        ]

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
# PLANTILLA AGENTE RAG_METADATA (RAG con metadatos enriquecidos)
# ============================================================================

AGENT_RAG_METADATA_TEMPLATE = '''"""
{agent_name} - Agente RAG+Metadata con ChromaDB
Soporta Mistral Cloud y Ollama via LLM_PROVIDER
Incluye extracción y filtrado por metadatos de documentos.

NOTA: ChromaDB no es compatible con Python 3.14+. Requiere Python 3.11-3.13.
"""

import os
import sys
import json
import re
import warnings
import logging

# Suppress pypdf warnings about malformed PDFs
logging.getLogger("pypdf").setLevel(logging.ERROR)
# Suppress sentence-transformers position_ids warning
warnings.filterwarnings("ignore", message=".*position_ids.*")

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
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Query history for the sidebar
        self._query_history = []
        # Document metadata cache
        self._documents_metadata = {{}}

        # RAG Chunking Configuration
        self._load_rag_config()

        # Load metadata configuration
        self._load_metadata_config()

        # Inicializar ChromaDB con manejo de errores
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            db_path = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
            self.chroma_client = chromadb.PersistentClient(path=db_path)

            # Función de embeddings (usa sentence-transformers por defecto)
            print("Preparing RAG+Metadata database...")
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )

            # Obtener o crear colección
            self.collection = self.chroma_client.get_or_create_collection(
                name="documents",
                embedding_function=self.embedding_fn
            )

            # Indexar documentos nuevos automáticamente
            self._sync_documents()

            print("RAG+Metadata database ready.")
            self._chromadb_error = None

        except Exception as e:
            error_msg = str(e)
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

    def _load_rag_config(self):
        """Load RAG chunking configuration from environment variables."""
        approach = os.getenv("RAG_APPROACH", "context_preserving").lower()

        if approach == "basic":
            self.chunk_size = 500
            self.chunk_overlap = 100
            self.retrieve_chunks = 3
            self.chunking_strategy = "fixed"
        elif approach == "context_preserving":
            self.chunk_size = 2000
            self.chunk_overlap = 400
            self.retrieve_chunks = 8
            self.chunking_strategy = "smart"
        else:  # custom
            self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "2000"))
            self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "400"))
            self.retrieve_chunks = int(os.getenv("RAG_RETRIEVE_CHUNKS", "8"))
            self.chunking_strategy = os.getenv("RAG_CHUNKING_STRATEGY", "smart").lower()

        print(f"RAG config: {{approach}} (chunks={{self.chunk_size}}, overlap={{self.chunk_overlap}}, retrieve={{self.retrieve_chunks}}, strategy={{self.chunking_strategy}})")

    def _load_metadata_config(self):
        """Load metadata configuration and external metadata from data/metadata.json.

        The metadata.json file can contain:
        - "fields": list of metadata field names to track
        - "documents": dict mapping filenames to their metadata values,
          e.g. {{"file.pdf": {{"author": "Dr. Smith", "department": "CS"}}}}

        External metadata supplements auto-extracted metadata (PDF metadata).
        If a field is provided in both, the external value takes precedence.
        """
        config_path = os.path.join(os.path.dirname(__file__), "data", "metadata.json")
        self.metadata_fields = ["title", "author", "date", "file_type", "file_size", "page_count"]
        self._external_metadata = {{}}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if "fields" in config:
                    self.metadata_fields = config["fields"]
                if "documents" in config and isinstance(config["documents"], dict):
                    self._external_metadata = config["documents"]
                    print(f"External metadata loaded for {{len(self._external_metadata)}} document(s)")
                print(f"Metadata config loaded: fields={{self.metadata_fields}}")
            except Exception as e:
                print(f"Warning: Could not load metadata config: {{e}}")

    def _extract_pdf_text(self, filepath: str) -> str:
        """Extrae texto de un archivo PDF."""
        try:
            reader = PdfReader(filepath)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\\n".join(text_parts)
        except Exception as e:
            print(f"Error extracting text from {{filepath}}: {{e}}")
            return ""

    def _extract_metadata(self, filepath: str) -> dict:
        """Extrae metadatos de un archivo y los combina con metadatos externos.

        Fuentes de metadatos (en orden de prioridad, de menor a mayor):
        1. Información básica del archivo (nombre, tamaño, tipo)
        2. Metadatos embebidos en el PDF (título, autor, fecha)
        3. Metadatos externos de data/metadata.json (mayor prioridad)
        """
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        file_type = os.path.splitext(filename)[1].lower().lstrip(".")

        metadata = {{
            "title": os.path.splitext(filename)[0],
            "author": "",
            "date": "",
            "file_type": file_type,
            "file_size": file_size,
            "page_count": 0,
            "source": filename,
        }}

        # 2. Extract embedded PDF metadata
        if filename.endswith(".pdf"):
            try:
                reader = PdfReader(filepath)
                info = reader.metadata
                if info:
                    if info.title:
                        metadata["title"] = info.title
                    if info.author:
                        metadata["author"] = info.author
                    if info.creation_date:
                        metadata["date"] = str(info.creation_date)
                metadata["page_count"] = len(reader.pages)
            except Exception as e:
                print(f"Warning: Could not extract PDF metadata from {{filename}}: {{e}}")

        # 3. Override/supplement with external metadata (highest priority)
        if hasattr(self, '_external_metadata') and filename in self._external_metadata:
            external = self._external_metadata[filename]
            for key, value in external.items():
                if value:  # Only override with non-empty values
                    metadata[key] = value

        return metadata

    def _get_indexed_sources(self) -> set:
        """Obtiene el conjunto de fuentes ya indexadas en ChromaDB."""
        if self.collection is None or self.collection.count() == 0:
            return set()

        all_data = self.collection.get(include=["metadatas"])
        sources = set()
        for meta in all_data.get("metadatas", []):
            if meta and "source" in meta:
                sources.add(meta["source"])
        return sources

    def _get_docs_files(self) -> set:
        """Obtiene el conjunto de archivos en data/docs/."""
        docs_path = os.path.join(os.path.dirname(__file__), "data", "docs")
        if not os.path.exists(docs_path):
            return set()

        files = set()
        for filename in os.listdir(docs_path):
            filepath = os.path.join(docs_path, filename)
            if os.path.isfile(filepath) and filename.endswith(('.txt', '.md', '.pdf')):
                files.add(filename)
        return files

    def _sync_documents(self):
        """Sincroniza documentos: indexa nuevos y elimina huérfanos."""
        indexed = self._get_indexed_sources()
        on_disk = self._get_docs_files()

        new_docs = on_disk - indexed
        removed_docs = indexed - on_disk

        if not new_docs and not removed_docs:
            print(f"Documents in sync ({{len(indexed)}} indexed)")
            # Load metadata for existing documents
            self._refresh_metadata_cache()
            return

        if removed_docs:
            print(f"Removing {{len(removed_docs)}} deleted documents from index...")
            for source in removed_docs:
                results = self.collection.get(where={{"source": source}})
                if results["ids"]:
                    self.collection.delete(ids=results["ids"])
                if source in self._documents_metadata:
                    del self._documents_metadata[source]
            print(f"Removed: {{', '.join(removed_docs)}}")

        if new_docs:
            print(f"Indexing {{len(new_docs)}} new documents...")
            self._index_documents(only_files=new_docs)
            print(f"Added: {{', '.join(new_docs)}}")

        self._refresh_metadata_cache()

    def _refresh_metadata_cache(self):
        """Refresh the metadata cache from indexed documents."""
        docs_path = os.path.join(os.path.dirname(__file__), "data", "docs")
        if not os.path.exists(docs_path):
            return

        self._documents_metadata = {{}}
        for filename in os.listdir(docs_path):
            filepath = os.path.join(docs_path, filename)
            if os.path.isfile(filepath) and filename.endswith(('.txt', '.md', '.pdf')):
                self._documents_metadata[filename] = self._extract_metadata(filepath)

    def _index_documents(self, only_files: set = None):
        """Indexa los documentos del directorio data/docs/ con metadatos enriquecidos."""
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
            if only_files is not None and filename not in only_files:
                continue

            # Extract metadata
            file_metadata = self._extract_metadata(filepath)
            self._documents_metadata[filename] = file_metadata

            # Extract content
            content = None
            if filename.endswith(('.txt', '.md')):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif filename.endswith('.pdf'):
                content = self._extract_pdf_text(filepath)

            if content:
                # Chunking based on configured strategy
                chunks = []
                if self.chunking_strategy == "smart":
                    start = 0
                    while start < len(content):
                        end = start + self.chunk_size
                        chunk = content[start:end]
                        if end < len(content):
                            for sep in ['\\n\\n', '. ', '\\n']:
                                last_sep = chunk.rfind(sep)
                                if last_sep > self.chunk_size * 0.6:
                                    chunk = chunk[:last_sep + len(sep)]
                                    end = start + len(chunk)
                                    break
                        chunks.append(chunk.strip())
                        start = end - self.chunk_overlap
                else:
                    step = self.chunk_size - self.chunk_overlap
                    chunks = [content[j:j+self.chunk_size] for j in range(0, len(content), step)]

                for k, chunk in enumerate(chunks):
                    if chunk:
                        documents.append(chunk)
                        # Store enriched metadata with each chunk
                        chunk_metadata = {{
                            "source": filename,
                            "chunk": k,
                            "title": file_metadata.get("title", ""),
                            "author": file_metadata.get("author", ""),
                            "date": file_metadata.get("date", ""),
                            "file_type": file_metadata.get("file_type", ""),
                            "page_count": file_metadata.get("page_count", 0),
                        }}
                        metadatas.append(chunk_metadata)
                        ids.append(f"{{filename}}_{{k}}")

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"Indexed {{len(documents)}} chunks from {{len(set(m['source'] for m in metadatas))}} documents (with metadata)")

    def _retrieve_context(self, query: str, n_results: int = None, metadata_filter: dict = None) -> str:
        """Recupera contexto relevante para la query, con filtro de metadatos opcional.

        Args:
            query: The search query
            n_results: Number of chunks to retrieve
            metadata_filter: Optional ChromaDB where filter for metadata
                            e.g. {{"author": "John"}} or {{"file_type": "pdf"}}
        """
        if n_results is None:
            n_results = self.retrieve_chunks
        if self.collection is None or self.collection.count() == 0:
            return ""

        query_params = {{
            "query_texts": [query],
            "n_results": n_results,
        }}
        if metadata_filter:
            query_params["where"] = metadata_filter

        results = self.collection.query(**query_params)

        if not results['documents'][0]:
            return ""

        context_parts = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            meta_info = f"[Source: {{meta['source']}}"
            if meta.get('title'):
                meta_info += f" | Title: {{meta['title']}}"
            if meta.get('author'):
                meta_info += f" | Author: {{meta['author']}}"
            if meta.get('date'):
                meta_info += f" | Date: {{meta['date']}}"
            meta_info += "]"
            context_parts.append(f"{{meta_info}}\\n{{doc}}")

        return "\\n\\n---\\n\\n".join(context_parts)

    def get_metadata_summary(self) -> list:
        """Returns metadata summary for all indexed documents."""
        return list(self._documents_metadata.values())

    def _build_metadata_context(self) -> str:
        """Builds a metadata summary string to include in the system prompt."""
        if not self._documents_metadata:
            return ""

        lines = ["Available documents and their metadata:"]
        for filename, meta in self._documents_metadata.items():
            parts = [f"- {{filename}}"]
            if meta.get("title") and meta["title"] != os.path.splitext(filename)[0]:
                parts.append(f"Title: {{meta['title']}}")
            if meta.get("author"):
                parts.append(f"Author: {{meta['author']}}")
            if meta.get("date"):
                parts.append(f"Date: {{meta['date']}}")
            if meta.get("page_count"):
                parts.append(f"Pages: {{meta['page_count']}}")
            if meta.get("file_type"):
                parts.append(f"Type: {{meta['file_type']}}")
            lines.append(" | ".join(parts))

        return "\\n".join(lines)

    def _verify_grounding(self, response: str, user_question: str, context: str) -> dict:
        """Verifica si la respuesta está basada SOLO en el contexto recuperado."""
        if not context:
            return {{"grounded": True, "reason": "No context to verify against"}}

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided context.

RETRIEVED CONTEXT:
{{context}}

USER QUESTION: {{user_question}}

AGENT RESPONSE: {{response}}

STRICT VERIFICATION RULES:
1. The response is "grounded" ONLY if ALL factual claims are EXPLICITLY written in the CONTEXT
2. It is NOT grounded if the response:
   - Infers or deduces information not explicitly stated in the context
   - Adds details, relationships, or facts not present in the context
   - Makes assumptions or generalizations beyond the context
   - Uses information that might be true but is not in the provided context
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly states it cannot find information, it IS grounded
5. BE VERY STRICT: if a claim cannot be found in the context, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{{{"grounded": true, "reason": "brief explanation"}}}}
or
{{{{"grounded": false, "reason": "specific claim that was not in the context"}}}}"""

        result = self.client.chat.complete(
            model=self.model,
            messages=[{{"role": "user", "content": verify_prompt}}]
        )

        try:
            content = result.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\\n?", "", content)
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return {{"grounded": True, "reason": "Verification parsing failed"}}

    def _get_fallback_response(self, user_question: str) -> str:
        """Genera una respuesta cuando la verificación falla."""
        return (
            "I apologize, but I cannot find specific information about that in my knowledge base. "
            "I can only provide information that is explicitly documented in my sources. "
            "Could you please ask something else or rephrase your question?"
        )

    def chat(self, user_message: str, history: list = None, verify: bool = None) -> str:
        """Envía un mensaje con contexto RAG+Metadata y obtiene respuesta."""
        should_verify = verify if verify is not None else self.verify_grounding

        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {{err['error_code']}}:** {{err['error']}}\\n\\n{{err.get('instructions', '')}}"

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system_with_context += f"\\n\\n{{metadata_ctx}}"
        if context:
            system_with_context += f"\\n\\nRelevant context from the knowledge base:\\n{{context}}"

        messages = [{{"role": "system", "content": system_with_context}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        response_content = response.choices[0].message.content

        if should_verify and context:
            verification = self._verify_grounding(response_content, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {{verification.get('reason', 'Unknown')}}")
                response_content = self._get_fallback_response(user_message)

        self._query_history.append({{
            'question': user_message,
            'response_length': len(response_content)
        }})

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, verify: bool = None):
        """Envía un mensaje con contexto RAG+Metadata y obtiene respuesta en streaming."""
        should_verify = verify if verify is not None else self.verify_grounding

        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {{err['error_code']}}:** {{err['error']}}\\n\\n{{err.get('instructions', '')}}"
            return

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system_with_context += f"\\n\\n{{metadata_ctx}}"
        if context:
            system_with_context += f"\\n\\nRelevant context from the knowledge base:\\n{{context}}"

        messages = [{{"role": "system", "content": system_with_context}}]

        if history:
            messages.extend(history)

        messages.append({{"role": "user", "content": user_message}})

        if should_verify and context:
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content

            verification = self._verify_grounding(full_response, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {{verification.get('reason', 'Unknown')}}")
                full_response = self._get_fallback_response(user_message)

            self._query_history.append({{
                'question': user_message,
                'response_length': len(full_response)
            }})
            yield full_response
        else:
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content
                    yield chunk.data.choices[0].delta.content

            self._query_history.append({{
                'question': user_message,
                'response_length': len(full_response)
            }})

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {{
                'question': entry['question'],
                'num_results': 1
            }}
            for entry in self._query_history
        ]

    def reindex(self):
        """Reindexa todos los documentos con metadatos."""
        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._documents_metadata = {{}}
        self._index_documents()
        return self.collection.count()
'''

# ============================================================================
# PLANTILLA AGENTE TEXT2SQL (Text-to-SQL simplificado)
# ============================================================================

AGENT_TEXT2SQL_TEMPLATE = '''"""
{agent_name} - Agente Text2SQL
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

**Problem:** {{error_msg}}

Try rephrasing your question or verify that the data exists in the database."""

    def _format_empty(self, sql_query: str) -> str:
        """Formatea un mensaje cuando no hay resultados (sin LLM)."""
        return f"""**No results**

The query executed successfully but found no data:
```sql
{{sql_query}}
```

Try different search criteria."""

    def _format_success(self, results: list, sql_query: str) -> str:
        """Formatea los resultados exitosos (sin LLM) - solo resumen."""
        num_rows = len(results)
        num_cols = len(results[0]) if results else 0

        summary = f"**Query executed:** `{{sql_query}}`\\n\\n"
        summary += f"**Results:** {{num_rows}} row(s), {{num_cols}} column(s)"

        if num_rows > 100:
            summary += " (showing first 100)"

        return summary

    def _format_as_html_table(self, results: list) -> str:
        """Formatea los resultados JSON como una tabla HTML."""
        if not results:
            return "<p><em>No results</em></p>"

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
<div class="sql-stats">Results: <strong>{{row_count}}</strong> rows</div>
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
        matches = [line for line in content.split('\\n') if query.lower() in line.lower()]
        if matches:
            return "\\n".join(matches[:5])
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
            return "The query returned no results."

        # Formatear resultados como tabla
        columns = rows[0].keys()
        result_lines = [" | ".join(columns)]
        result_lines.append("-" * len(result_lines[0]))

        for row in rows[:50]:  # Limitar a 50 filas
            result_lines.append(" | ".join(str(row[col]) for col in columns))

        if len(rows) > 50:
            result_lines.append(f"... ({{len(rows) - 50}} filas más)")

        return "\\n".join(result_lines)

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

        return "Tablas disponibles:\\n" + "\\n".join(f"  - {{t[0]}}" for t in tables)

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

The query returned no results.

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
            return "<p><em>No results</em></p>"

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

            yield ("status", "Generating results table...")

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

The query returned no results.

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
            return "<p><em>No results</em></p>"

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

        yield ("status", "Generating results table...")
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
            return "<p><em>No results</em></p>"

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
    verify: Optional[bool] = None  # None = usar VERIFY_GROUNDING del .env


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
            async for chunk in agent.chat_stream(request.message, request.history, verify=request.verify):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history, verify=request.verify)
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
    verify: Optional[bool] = None  # None = usar VERIFY_GROUNDING del .env


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
            async for chunk in agent.chat_stream(request.message, request.history, verify=request.verify):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history, verify=request.verify)
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

APP_PY_RAG_METADATA_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (RAG+Metadata)
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
    "type": "rag_metadata",
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
    verify: Optional[bool] = None


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
    """Endpoint principal de chat con RAG+Metadata."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history, verify=request.verify):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history, verify=request.verify)
    return ChatResponse(response=response)


@app.post("/reindex")
async def reindex():
    """Reindexa los documentos en data/docs/ con metadatos"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    count = agent.reindex()
    return {{"status": "ok", "indexed_chunks": count}}


@app.get("/metadata")
async def metadata():
    """Devuelve los metadatos de todos los documentos indexados."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {{"documents": agent.get_metadata_summary()}}


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
# APP TEXT2SQL
# ============================================================================

APP_TEXT2SQL_TEMPLATE = '''"""
{agent_name} - Servidor FastAPI (Text2SQL)
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

README_RAG_METADATA_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente RAG+Metadata (Retrieval-Augmented Generation with Metadata)

> ⚠️ **IMPORTANTE**: Los agentes RAG+Metadata requieren Python 3.11, 3.12 o 3.13.
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

2. Añade tus documentos en `data/docs/` (formatos soportados: .txt, .md, .pdf)

3. (Opcional) Configura campos de metadatos personalizados en `data/metadata.json`

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
- `GET /metadata` - Metadatos de todos los documentos indexados
- `POST /chat` - Enviar mensaje (busca contexto relevante con metadatos)
- `POST /reindex` - Reindexa los documentos con metadatos

### Ejemplo de uso con curl

```bash
# Chat normal
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "¿Qué información tienes sobre X?"}}'

# Ver metadatos de documentos
curl http://localhost:8000/metadata

# Reindexar documentos
curl -X POST http://localhost:8000/reindex
```

## Metadatos

Los metadatos se extraen automáticamente de los documentos:

| Campo | PDF | TXT/MD |
|-------|-----|--------|
| title | Del PDF o nombre de archivo | Nombre de archivo |
| author | Del PDF | - |
| date | Del PDF | - |
| page_count | Sí | - |
| file_size | Sí | Sí |
| file_type | Sí | Sí |

### Configuración personalizada de metadatos

Puedes personalizar los campos de metadatos creando `data/metadata.json`:

```json
{{
    "fields": ["title", "author", "date", "file_type", "file_size", "page_count", "department", "category"]
}}
```

## Estructura

```
{agent_id}/
├── .env                    # API key (no subir a git)
├── requirements.txt        # Dependencias
├── agent.py               # Lógica del agente con RAG+Metadata
├── app.py                 # Servidor FastAPI
├── config.json            # Configuración del agente
├── prompts.json           # Plantillas de prompts del sistema
├── run.sh                 # Script de ejecución
└── data/
    ├── docs/              # Documentos a indexar (.txt, .md, .pdf)
    ├── metadata.json      # Metadatos de documentos
    ├── researchers.json   # Perfiles de investigadores
    ├── institution_ids.json # IDs de universidades (OpenAlex)
    └── chroma_db/         # Base de datos vectorial (se genera automáticamente)
```

## Cómo funciona

1. Al iniciar, el agente indexa todos los documentos en `data/docs/` extrayendo contenido y metadatos
2. Los metadatos (autor, título, fecha, etc.) se almacenan junto a cada chunk en ChromaDB
3. Cuando recibes una pregunta, busca los fragmentos más relevantes
4. El LLM recibe tanto el contenido relevante como los metadatos para generar respuestas informadas
5. Las preguntas sobre metadatos (e.g., "¿qué documentos hay de tal autor?") se responden usando la información de metadatos
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
# README TEXT2SQL
# ============================================================================

# ============================================================================
# PLANTILLA BENCHMARK TEXT2SQL
# ============================================================================

BENCHMARK_TEXT2SQL_TEMPLATE = '''#!/usr/bin/env python3
"""
Benchmark de {agent_name} - Script para pruebas de rendimiento

Ejecuta un paquete de preguntas predefinidas y genera un log con:
- Tiempos de cada fase (text_to_sql, execute, format)
- SQL generado para cada pregunta
- Resultados y errores

Uso:
    python benchmark.py              # Ejecutar todas las preguntas
    python benchmark.py -n 5         # Ejecutar solo 5 preguntas
    python benchmark.py --quick      # Ejecutar preguntas rápidas
    python benchmark.py --help       # Mostrar ayuda
"""

import os
import sys
import json
import argparse
import statistics
from datetime import datetime

# Cargar variables de entorno desde .env ANTES de importar el agente
def load_env_file(env_path: str) -> None:
    """Carga variables de entorno desde un archivo .env."""
    if not os.path.exists(env_path):
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                os.environ[key] = value

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_env_file(env_path)

sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent

# ============================================================================
# PAQUETE DE PREGUNTAS DE PRUEBA
# Personaliza estas preguntas según tu base de datos
# ============================================================================

PREGUNTAS_BENCHMARK = [
    # --- Warm-up (se repite la primera pregunta) ---
    "¿Cuántos registros hay en total?",
    "¿Cuántos registros hay en total?",

    # --- Consultas básicas ---
    "Muéstrame todos los registros",
    "¿Cuáles son las tablas disponibles?",

    # --- Añade aquí tus preguntas de prueba ---
    # "¿Qué registros hay de tipo X?",
    # "¿Cuántos elementos hay en la categoría Y?",
    # "Muéstrame los últimos 10 registros",
]

PREGUNTAS_QUICK = [
    "¿Cuántos registros hay?",
    "Muéstrame los primeros 5 registros",
]

# ============================================================================
# RESPUESTAS SQL DE REFERENCIA (opcional)
# Añade el SQL esperado para comparar con el generado
# ============================================================================

RESPUESTAS_REFERENCIA = {{
    # "¿Cuántos registros hay en total?": "SELECT COUNT(*) FROM tabla",
    # "Muéstrame todos los registros": "SELECT * FROM tabla",
}}


def run_benchmark(questions: list, output_prefix: str = "benchmark") -> dict:
    """
    Ejecuta el benchmark con las preguntas proporcionadas.

    Args:
        questions: Lista de preguntas a ejecutar
        output_prefix: Prefijo para el archivo de salida

    Returns:
        dict con resultados del benchmark
    """
    print("=" * 70)
    print("BENCHMARK {agent_name} - Prueba de Rendimiento")
    print("=" * 70)
    print(f"Preguntas a ejecutar: {{len(questions)}}")
    print(f"Inicio: {{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}")
    print("=" * 70)
    print()

    # Inicializar agente
    print("Inicializando agente...")
    agent = Agent()
    print(f"Modelo SQL: {{agent.sql_model}}")
    print(f"Base de datos: {{agent.db_path}}")
    print()

    # Resultados del benchmark
    results = {{
        "metadata": {{
            "timestamp": datetime.now().isoformat(),
            "num_questions": len(questions),
            "sql_model": agent.sql_model,
            "db_path": agent.db_path,
        }},
        "questions": [],
        "summary": {{
            "total_time": 0,
            "avg_time": 0,
            "successful": 0,
            "failed": 0,
            "sql_errors": 0,
        }}
    }}

    times_total = []

    # Ejecutar cada pregunta
    for i, question in enumerate(questions, 1):
        is_warmup = (i == 1)
        warmup_tag = " [WARM-UP]" if is_warmup else ""
        print(f"[{{i}}/{{len(questions)}}]{{warmup_tag}} {{question[:60]}}...")

        # Mostrar SQL de referencia si existe
        sql_ref = RESPUESTAS_REFERENCIA.get(question, None)
        if sql_ref:
            print(f"    Ref: {{sql_ref}}")

        try:
            # Usar chat_with_metrics si está disponible
            if hasattr(agent, 'chat_with_metrics'):
                metrics = agent.chat_with_metrics(question)
                success = metrics.get("success", False)
                sql_query = metrics.get("sql_query", "")
                total_time = metrics.get("total_time", 0)
                num_results = metrics.get("num_results", 0)
                error = metrics.get("error", "")
                timings = metrics.get("timings", {{}})
            else:
                # Fallback: usar chat normal con timing manual
                import time
                start = time.time()
                response = agent.chat(question)
                total_time = time.time() - start
                success = True
                sql_query = ""
                num_results = 0
                error = ""
                timings = {{}}

            question_result = {{
                "id": i,
                "question": question,
                "is_warmup": is_warmup,
                "sql_query": sql_query,
                "sql_referencia": sql_ref,
                "success": success,
                "num_results": num_results,
                "timings": timings,
                "total_time": total_time,
                "error": error
            }}
            results["questions"].append(question_result)

            if not is_warmup:
                times_total.append(total_time)

            status = "OK" if success else "ERROR"
            print(f"    -> {{status}} | {{total_time:.2f}}s | Resultados: {{num_results}}")

            if success:
                results["summary"]["successful"] += 1
            else:
                results["summary"]["failed"] += 1
                if error:
                    print(f"    !! Error: {{error[:80]}}")

        except Exception as e:
            print(f"    !! Excepción: {{str(e)}}")
            results["questions"].append({{
                "id": i,
                "question": question,
                "sql_query": None,
                "success": False,
                "error": str(e),
                "total_time": 0
            }})
            results["summary"]["failed"] += 1

        print()

    # Calcular resumen
    if times_total:
        results["summary"]["total_time"] = sum(times_total)
        results["summary"]["avg_time"] = statistics.mean(times_total)

    # Mostrar resumen
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Preguntas ejecutadas: {{len(questions)}}")
    print(f"Exitosas: {{results['summary']['successful']}}")
    print(f"Fallidas: {{results['summary']['failed']}}")
    print(f"Tiempo total: {{results['summary']['total_time']:.2f}}s")
    print(f"Tiempo promedio: {{results['summary']['avg_time']:.2f}}s")
    print("=" * 70)

    # Guardar resultados
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/{{output_prefix}}_{{timestamp}}.json"

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\\nResultados guardados en: {{log_file}}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark de {agent_name}")
    parser.add_argument("-n", "--num", type=int, help="Número de preguntas a ejecutar")
    parser.add_argument("--quick", action="store_true", help="Ejecutar solo preguntas rápidas")
    parser.add_argument("-o", "--output", default="benchmark", help="Prefijo del archivo de salida")

    args = parser.parse_args()

    if args.quick:
        questions = PREGUNTAS_QUICK
    elif args.num:
        questions = PREGUNTAS_BENCHMARK[:args.num]
    else:
        questions = PREGUNTAS_BENCHMARK

    run_benchmark(questions, args.output)


if __name__ == "__main__":
    main()
'''

README_TEXT2SQL_TEMPLATE = '''# {agent_name}

{description}

**Tipo**: Agente Text2SQL (Consultas en lenguaje natural a SQL)

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
├── agent.py           # Lógica Text2SQL
├── app.py             # Servidor FastAPI
├── run.sh             # Script de ejecución
├── benchmark.py       # Script de pruebas de rendimiento
├── logs/              # Resultados de benchmarks
└── data/
    └── database.db    # Base de datos SQLite (debes crearla)
```

## Benchmark (Pruebas de rendimiento)

El agente incluye un script de benchmark para probar el rendimiento:

```bash
# Ejecutar todas las preguntas de prueba
python benchmark.py

# Ejecutar solo N preguntas
python benchmark.py -n 5

# Ejecutar preguntas rápidas
python benchmark.py --quick

# Ver ayuda
python benchmark.py --help
```

### Personalizar preguntas

Edita `benchmark.py` y modifica:
- `PREGUNTAS_BENCHMARK`: Lista de preguntas de prueba
- `RESPUESTAS_REFERENCIA`: SQL esperado para cada pregunta (opcional)

Los resultados se guardan en `logs/benchmark_YYYYMMDD_HHMMSS.json`.

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
    """Request input with default value."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def input_multiline(prompt: str) -> str:
    """Request multiline input (ends with empty line)."""
    print(f"{prompt} (empty line to finish):")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def create_agent_structure(config: dict) -> str:
    """
    Creates an agent structure programmatically.

    Args:
        config: Dictionary with agent configuration:
            - agent_type: 'oneshot', 'rag', 'rag_vectorless', 'rag_metadata', or 'text2sql'
            - agent_id: Lowercase identifier
            - output_dir: Directory to create agent in
            - agent_name: Display name
            - description: Short description
            - welcome: Welcome message
            - examples: List of example questions
            - system_prompt: System prompt text
            - llm_provider: 'default', 'mistral', or 'ollama'
            - model: Model name
            - api_key: API key (for mistral)
            - ollama_url: Ollama URL (for ollama)
            - ollama_model: Ollama model (for ollama)
            - verify_grounding: Boolean for grounding verification
            - rag_approach: 'basic', 'context_preserving', or 'custom' (for RAG agents)

    Returns:
        Path to created agent directory
    """
    agent_type = config['agent_type']
    agent_id = config['agent_id']
    output_dir = config['output_dir']
    agent_name = config['agent_name']
    description = config.get('description', f"{agent_name} Assistant")
    welcome = config.get('welcome', f"Hello! I'm {agent_name}. How can I help you?")
    examples = config.get('examples', [])
    system_prompt = config['system_prompt']
    # Replace {agent_name} placeholder in system prompt
    system_prompt = system_prompt.replace('{agent_name}', agent_name)
    llm_provider = config.get('llm_provider', 'default')
    model = config.get('model', 'mistral-large-latest')
    api_key = config.get('api_key', '')
    ollama_url = config.get('ollama_url', 'http://localhost:11434')
    ollama_model = config.get('ollama_model', '')
    verify_grounding = config.get('verify_grounding', False)
    rag_approach = config.get('rag_approach', 'context_preserving')

    # Create directories
    os.makedirs(get_agents_dir(), exist_ok=True)
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # For RAG types, create documents directory
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        docs_dir = os.path.join(data_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

    # requirements.txt by type
    requirements_map = {
        "oneshot": REQUIREMENTS_ONESHOT,
        "rag": REQUIREMENTS_RAG,
        "rag_vectorless": REQUIREMENTS_RAG,
        "rag_metadata": REQUIREMENTS_RAG_METADATA,
        "text2sql": REQUIREMENTS_TEXT2SQL
    }
    with open(os.path.join(output_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(requirements_map.get(agent_type, REQUIREMENTS_RAG))

    # .env by provider
    with open(os.path.join(output_dir, ".env"), "w", encoding="utf-8") as f:
        if llm_provider == "default":
            f.write(ENV_TEMPLATE_DEFAULT)
        elif llm_provider == "mistral":
            f.write(ENV_TEMPLATE_MISTRAL.format(api_key=api_key or "YOUR_API_KEY_HERE", model=model))
        elif llm_provider == "ollama":
            f.write(ENV_TEMPLATE_OLLAMA.format(ollama_url=ollama_url, ollama_model=ollama_model))

        # Add verification configuration for oneshot and rag (not rag_metadata/rag_vectorless — uses procedural banners)
        if agent_type in ["oneshot", "rag"]:
            f.write("\n# ============================================\n")
            f.write("# Grounding Verification (Anti-hallucination)\n")
            f.write("# ============================================\n")
            if agent_type == "oneshot":
                f.write("# Verifies that responses are based ONLY on data.md\n")
            else:
                f.write("# Verifies that responses are based ONLY on retrieved context\n")
            f.write("# NOTE: Doubles LLM calls (higher latency and cost)\n")
            f.write(f"VERIFY_GROUNDING={'true' if verify_grounding else 'false'}\n")

        # Add RAG chunking configuration for rag agents
        if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
            f.write("\n# ============================================\n")
            f.write("# RAG Chunking Configuration\n")
            f.write("# ============================================\n")
            f.write("# RAG_APPROACH: basic | context_preserving | custom\n")
            f.write("#   - basic: Fast indexing (500 chars, 100 overlap, 3 results)\n")
            f.write("#   - context_preserving: Better retrieval (2000 chars, 400 overlap, 8 results, smart boundaries)\n")
            f.write("#   - custom: Use the custom values below\n")
            f.write(f"RAG_APPROACH={rag_approach}\n")
            f.write("\n# Custom RAG parameters (only used when RAG_APPROACH=custom)\n")
            f.write("# RAG_CHUNK_SIZE=2000\n")
            f.write("# RAG_CHUNK_OVERLAP=400\n")
            f.write("# RAG_RETRIEVE_CHUNKS=8\n")
            f.write("# RAG_CHUNKING_STRATEGY=smart\n")

    # .gitignore
    gitignore_content = GITIGNORE
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        gitignore_content += "data/chroma_db/\n"
    with open(os.path.join(output_dir, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(gitignore_content)

    # agent.py by type
    if agent_type == "rag_vectorless":
        # RAG Vectorless agents use SimpleVectorlessMixin with procedural banners
        agent_py_content = '"""\n{name} — Simple vectorless RAG agent with procedural banners.\nAll behavior from config.json + base classes.\n"""\n\nimport os\nimport sys\n\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))\nfrom base import BaseRAGAgent, SimpleRAGMixin\nfrom base.simple_vectorless_mixin import SimpleVectorlessMixin\n\n\nclass Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):\n    _AGENT_FILE = __file__\n'.format(name=agent_name)
        with open(os.path.join(output_dir, "agent.py"), "w", encoding="utf-8") as f:
            f.write(agent_py_content)

        # Generate config.json for RAG Vectorless agents
        reliability_green = config.get('reliability_green_max_llm', 20)
        reliability_red = config.get('reliability_red_min_llm', 50)
        agent_config = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "type": "rag_vectorless",
            "description": description,
            "welcome_message": welcome,
            "show_history": True,
            "example_queries": examples,
            "prompt_level": "stringent",
            "transparency_level": "scaffolded",
            "transparency_type": "procedural",
            "audit_log_enabled": True,
            "reliability_green_max_llm": reliability_green,
            "reliability_red_min_llm": reliability_red,
            "inline_claim_highlights": {
                "enabled": True,
                "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
                "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
                "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
                "web_style": "background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;",
                "show_legend": True,
            },
            "humility_prompt": "on",
            "humility_postprocessing": "moderate",
        }
        with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(agent_config, f, indent=2, ensure_ascii=False)

        # Generate prompts.json for RAG Vectorless agents
        prompts_scaffold = {
            "identity": "You are {agent_name}, a helpful {description}.",
            "rules": "IMPORTANT RULES:\n1. Answer questions based ONLY on the context provided from the knowledge base below.\n2. If you cannot find relevant information in the context, say: \"I don't have information about that in my knowledge base.\"\n3. NEVER use your general knowledge. Only use the text provided in the context.",
            "strict": ""
        }
        with open(os.path.join(output_dir, "prompts.json"), "w", encoding="utf-8") as f:
            json.dump(prompts_scaffold, f, indent=2, ensure_ascii=False)

        # Copy build_chunk_db.py from tommi_tutor as reference
        build_script_src = os.path.join(os.path.dirname(__file__), "..", "agents", "tommi_tutor", "build_chunk_db.py")
        if os.path.exists(build_script_src):
            import shutil as _shutil2
            _shutil2.copy2(build_script_src, os.path.join(output_dir, "build_chunk_db.py"))

    elif agent_type == "rag_metadata":
        # RAG+Metadata agents use a reference agent.py (config-driven, no template needed)
        import shutil
        reference_agent = os.path.join(os.path.dirname(__file__), "..", "agents", "responsible_ai", "agent.py")
        if os.path.exists(reference_agent):
            shutil.copy2(reference_agent, os.path.join(output_dir, "agent.py"))
        else:
            # Fallback to template if reference agent not found
            agent_content = AGENT_RAG_METADATA_TEMPLATE.format(
                agent_id=agent_id, agent_name=agent_name, model=model,
                system_prompt=system_prompt.replace('"', '\\"').replace("'", "\\'")
            )
            with open(os.path.join(output_dir, "agent.py"), "w", encoding="utf-8") as f:
                f.write(agent_content)

        # Generate config.json for RAG+Metadata agents
        reliability_green = config.get('reliability_green_max_llm', 20)
        reliability_red = config.get('reliability_red_min_llm', 50)
        agent_config = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "description": description,
            "welcome_message": welcome,
            "research_topic": config.get('research_topic', description),
            "show_history": False,
            "example_queries": examples,
            "alliance": {
                "name": config.get('alliance_name', 'UNINOVIS'),
                "description": config.get('alliance_description', 'European university alliance.')
            },
            "universities": config.get('universities', {}),
            "gap_analysis_examples": config.get('gap_analysis_examples', ''),
            "prompt_level": config.get('prompt_level', 'stringent'),
            "transparency_level": config.get('transparency_level', 'crystal_box'),
            "audit_log_enabled": config.get('audit_log_enabled', True),
            "reliability_green_max_llm": reliability_green,
            "reliability_red_min_llm": reliability_red,
            "inline_claim_highlights": config.get('inline_claim_highlights', {
                "enabled": True,
                "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
                "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
                "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
                "web_style": "background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;",
                "show_legend": True,
                "_style_comment": "Green = metadata, Yellow = database (RAG), Blue = web search, Red = LLM interpretation"
            })
        }
        with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(agent_config, f, indent=2, ensure_ascii=False)

        # Generate prompts.json for RAG+Metadata agents
        prompts_src = os.path.join(os.path.dirname(__file__), "..", "agents", "responsible_ai", "prompts.json")
        if os.path.exists(prompts_src):
            import shutil as _shutil
            _shutil.copy2(prompts_src, os.path.join(output_dir, "prompts.json"))
        else:
            # Minimal prompts.json scaffold
            prompts_scaffold = {
                "identity": "You are {agent_name}, a research assistant specialized in {research_topic} papers from the {alliance_name} European university alliance.\n\n{alliance_name_upper} ALLIANCE CONTEXT:\n{alliance_desc} It consists of {num_universities} universities from {num_universities} countries:\n{uni_list}\n\nYour document database contains research papers on {research_topic} topics from {alliance_name} partner universities. Each paper has metadata including the university it belongs to.\n\nIMPORTANT: When users refer to university acronyms ({acronym_list}), use the mapping above.",
                "rules": "IMPORTANT RULES:\n1. Answer questions based ONLY on the context retrieved from your document database\n2. If the retrieved context doesn't contain relevant information, clearly state that\n3. NEVER invent, fabricate, or hallucinate paper titles, author names, or paper IDs.",
                "strict": ""
            }
            with open(os.path.join(output_dir, "prompts.json"), "w", encoding="utf-8") as f:
                json.dump(prompts_scaffold, f, indent=2, ensure_ascii=False)
    else:
        agent_templates = {
            "oneshot": AGENT_PY_TEMPLATE,
            "rag": AGENT_RAG_TEMPLATE,
            "text2sql": AGENT_TEXT2SQL_TEMPLATE
        }
        agent_content = agent_templates[agent_type].format(
            agent_id=agent_id,
            agent_name=agent_name,
            model=model,
            system_prompt=system_prompt.replace('"', '\\"').replace("'", "\\'")
        )
        with open(os.path.join(output_dir, "agent.py"), "w", encoding="utf-8") as f:
            f.write(agent_content)

        # Generate config.json for non-rag_metadata agents (oneshot, rag, text2sql)
        basic_config = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "type": agent_type,
            "description": description,
            "welcome_message": welcome,
            "example_queries": examples,
            "transparency_level": config.get('transparency_level', 'crystal_box'),
            "prompt_level": config.get('prompt_level', 'stringent'),
        }
        if agent_type == "rag":
            basic_config["audit_log_enabled"] = True
            basic_config["reliability_green_max_llm"] = config.get('reliability_green_max_llm', 20)
            basic_config["reliability_red_min_llm"] = config.get('reliability_red_min_llm', 50)
            basic_config["inline_claim_highlights"] = {
                "enabled": True,
                "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
                "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
                "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
                "web_style": "background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;",
                "show_legend": True,
                "_style_comment": "Green = metadata, Yellow = database (RAG), Blue = web search, Red = LLM interpretation"
            }
        with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(basic_config, f, indent=2, ensure_ascii=False)

    # app.py by type
    app_templates = {
        "oneshot": APP_PY_TEMPLATE,
        "rag": APP_PY_RAG_TEMPLATE,
        "rag_metadata": APP_PY_RAG_METADATA_TEMPLATE,
        "text2sql": APP_TEXT2SQL_TEMPLATE
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

    # Data files by type
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        example_doc = f"# Example document for {agent_name}\n\nAdd your content here.\n\nThis file will be automatically indexed when the agent starts.\n"
        with open(os.path.join(docs_dir, "example.md"), "w", encoding="utf-8") as f:
            f.write(example_doc)
        # Create sample data files for rag_metadata agents
        if agent_type == "rag_metadata":
            sample_metadata = json.dumps({
                "fields": ["title", "author", "date", "file_type", "file_size", "page_count"],
                "documents": {
                    "example.md": {
                        "title": "Example Document",
                        "author": "Your Name",
                        "date": "2024-01-01"
                    }
                }
            }, indent=2, ensure_ascii=False)
            with open(os.path.join(data_dir, "metadata.json"), "w", encoding="utf-8") as f:
                f.write(sample_metadata)
            # Empty researchers.json (populated by openalex_collector or researchers_tsv.py)
            with open(os.path.join(data_dir, "researchers.json"), "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)
            # Empty institution_ids.json (populated by openalex_collector)
            with open(os.path.join(data_dir, "institution_ids.json"), "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)
    elif agent_type == "text2sql":
        db_readme = f"""# Database for {agent_name}

Create your SQLite database here named `database.db`.

## Creation example

```bash
sqlite3 database.db << 'EOF'
CREATE TABLE example (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    value REAL
);

INSERT INTO example VALUES (1, 'Item 1', 100.0);
INSERT INTO example VALUES (2, 'Item 2', 200.0);
EOF
```

Once the DB is created, the agent will be able to answer questions in natural language.
"""
        with open(os.path.join(data_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(db_readme)
    else:
        data_content = DATA_MD_TEMPLATE.format(agent_name=agent_name)
        with open(os.path.join(data_dir, "data.md"), "w", encoding="utf-8") as f:
            f.write(data_content)

    # run.sh
    run_sh_template = RUN_SH_RAG_TEMPLATE if agent_type in ["rag", "rag_vectorless", "rag_metadata"] else RUN_SH_TEMPLATE
    with open(os.path.join(output_dir, "run.sh"), "w", encoding="utf-8") as f:
        f.write(run_sh_template)
    os.chmod(os.path.join(output_dir, "run.sh"), 0o755)

    # README.md
    readme_templates = {
        "oneshot": README_TEMPLATE,
        "rag": README_RAG_TEMPLATE,
        "rag_metadata": README_RAG_METADATA_TEMPLATE,
        "text2sql": README_TEXT2SQL_TEMPLATE
    }
    readme_content = readme_templates[agent_type].format(
        agent_name=agent_name,
        agent_id=agent_id,
        agent_type=agent_type,
        model=model,
        description=description
    )
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)

    return output_dir


def main():
    print("=" * 60)
    print("  Create Agent (FastAPI + Mistral/Ollama)")
    print("=" * 60)
    print()

    # 1. Agent type
    print("Available agent types:")
    print("  1. oneshot        - Simple agent with prompt and static data")
    print("  2. rag            - Agent with semantic search in documents (ChromaDB)")
    print("  3. text2sql - Agent that converts natural language to SQL (Text2SQL)")
    print("  4. rag_metadata   - Agent with semantic search + document metadata (ChromaDB)")
    print()

    agent_type = ""
    while agent_type not in ["1", "2", "3", "4", "oneshot", "rag", "text2sql", "rag_metadata"]:
        agent_type = input("Agent type [1/2/3/4]: ").strip().lower()

    # Normalize type
    type_map = {"1": "oneshot", "2": "rag", "3": "text2sql", "4": "rag_metadata"}
    agent_type = type_map.get(agent_type, agent_type)
    print(f"  → Selected type: {agent_type}")

    # Warning for RAG if Python 3.14+
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        import platform
        py_version = tuple(map(int, platform.python_version().split('.')[:2]))
        if py_version >= (3, 14):
            print()
            print("  ⚠️  WARNING: You are using Python 3.14+")
            print("     ChromaDB is NOT compatible with this version.")
            print("     The agent will show Error 307 when trying to use it.")
            print("     Solution: Install Python 3.12 or 3.13:")
            print("       brew install python@3.12")
            print("     The run.sh script will automatically look for a compatible version.")
            print()
            confirm_rag = input("  Continue anyway? (y/n): ").strip().lower()
            if confirm_rag != "y":
                print("Cancelled.")
                sys.exit(0)

    print()

    # 2. Agent name (ID)
    agent_id = ""
    while not agent_id:
        agent_id = input("Agent name (no spaces or uppercase): ").strip().lower()
        if " " in agent_id or not agent_id.replace("_", "").replace("-", "").isalnum():
            print("  Error: use only lowercase letters, numbers, hyphens or underscores")
            agent_id = ""

    # 3. Output directory (inside tommi2/agents/)
    agents_base = get_agents_dir()
    default_output = os.path.join(agents_base, agent_id)
    output_dir = input_with_default("Output directory", default_output)

    # 4. Public agent name
    agent_name = input_with_default("Public agent name", agent_id.replace("_", " ").title())

    # 5. Description
    description = input_with_default("Short agent description", f"{agent_name} Assistant")

    # 6. Welcome message
    welcome = input_with_default(
        "Welcome message",
        f"Hello! I'm {agent_name}. How can I help you?"
    )

    # 7. Example questions
    print("\nExample questions (one per line, empty line to finish):")
    examples = []
    while True:
        ex = input(f"  Question {len(examples) + 1}: ").strip()
        if not ex:
            break
        examples.append(ex)
    if not examples:
        if agent_type == "rag":
            examples = ["What information do you have?", "Search for X"]
        elif agent_type == "rag_metadata":
            examples = ["What documents are available?", "Show me documents by author X", "Search for X"]
        elif agent_type == "text2sql":
            examples = ["How many records are there?", "Show me the last 10 records"]
        else:
            examples = ["What can you do?", "Give me information"]

    # 8. System prompt - select from available templates
    print("\nSystem prompt:")

    # List available templates
    templates = list_prompt_templates(agent_type)

    if templates:
        print("  Available templates:")
        for i, (name, _) in enumerate(templates, 1):
            print(f"    {i}. {name}")
        print()

        template_choice = ""
        valid_choices = [str(i) for i in range(1, len(templates) + 1)]
        while template_choice not in valid_choices:
            template_choice = input(f"  Select template [1-{len(templates)}]: ").strip()

        template_idx = int(template_choice) - 1
        template_name, template_path = templates[template_idx]
        system_prompt = load_prompt_template(template_path, agent_name)
        print(f"  → Template loaded: {template_name}")
    else:
        # No templates found, use default prompt
        print("  (No templates found in prompts/)")
        system_prompt = ""

    # Default prompt if no templates
    if not system_prompt:
        if agent_type == "rag":
            system_prompt = f"You are {agent_name}, a helpful assistant. Answer questions based on the context provided from the knowledge base. If you don't find relevant information, say so clearly."
        elif agent_type == "rag_metadata":
            system_prompt = f"You are {agent_name}, a helpful assistant. Answer questions based on the context provided from the knowledge base. You have access to document metadata (author, title, date, etc.) and can answer questions about document properties. If you don't find relevant information, say so clearly."
        elif agent_type == "text2sql":
            system_prompt = f"You are {agent_name}, an assistant specialized in database queries. You help users get information from the database by answering their questions in natural language."
        else:
            system_prompt = f"You are {agent_name}, a helpful assistant. Answer questions based on the provided data."

    # 9. LLM Provider
    print("\nLLM Configuration:")
    print("  1. default  - Use web/.env configuration (recommended)")
    print("  2. mistral  - Configure Mistral Cloud specific for this agent")
    print("  3. ollama   - Configure Ollama specific for this agent")
    print()

    llm_provider = ""
    while llm_provider not in ["1", "2", "3", "default", "mistral", "ollama"]:
        llm_provider = input("LLM Configuration [1/2/3]: ").strip().lower()

    provider_map = {"1": "default", "2": "mistral", "3": "ollama"}
    llm_provider = provider_map.get(llm_provider, llm_provider)
    print(f"  → Selected configuration: {llm_provider}")

    # 10. Configuration by provider
    api_key = ""
    ollama_url = ""
    ollama_model = ""
    model = "mistral-large-latest"  # Default

    if llm_provider == "mistral":
        print("\nMistral models: mistral-large-latest, mistral-medium-latest, mistral-small-latest")
        model = input_with_default("Model", "mistral-large-latest")
        api_key = input("Mistral API Key (or leave empty to add later): ").strip()
        if not api_key:
            api_key = "YOUR_API_KEY_HERE"
    elif llm_provider == "ollama":
        ollama_url = input_with_default("Ollama URL", "http://localhost:11434")
        print("\nCommon Ollama models: mistral-large:latest, mistral, llama3, codellama, phi3")
        ollama_model = input_with_default("Ollama Model", "mistral-large:latest")
        model = ollama_model
    # else: default - no additional configuration needed

    # 11. Grounding verification (for oneshot and rag)
    verify_grounding = False
    if agent_type in ["oneshot", "rag", "rag_metadata"]:
        print("\nGrounding verification (anti-hallucination):")
        if agent_type == "oneshot":
            print("  This option verifies that agent responses are based")
            print("  ONLY on data from data.md, avoiding hallucinations.")
        else:  # rag
            print("  This option verifies that agent responses are based")
            print("  ONLY on the context retrieved from documents, avoiding hallucinations.")
        print("  NOTE: Doubles LLM calls (higher latency and cost).")
        print()
        verify_choice = input("  Enable grounding verification? (y/n) [n]: ").strip().lower()
        verify_grounding = verify_choice == "y"
        print(f"  → Verification: {'Enabled' if verify_grounding else 'Disabled'}")

    # 12. RAG Chunking Approach (for rag agents only)
    rag_approach = "context_preserving"  # Default
    rag_chunk_size = 2000
    rag_chunk_overlap = 400
    rag_retrieve_chunks = 8
    rag_chunking_strategy = "smart"

    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        print("\nRAG Chunking Approach:")
        print("  1. basic             - Fast indexing, lower accuracy")
        print("                         (500 chars, 100 overlap, 3 results)")
        print("  2. context_preserving - Better retrieval, recommended for dense documents")
        print("                         (2000 chars, 400 overlap, 8 results, smart boundaries)")
        print("  3. custom            - Define your own parameters")
        print()

        rag_choice = ""
        while rag_choice not in ["1", "2", "3", "basic", "context_preserving", "custom"]:
            rag_choice = input("  RAG approach [1/2/3]: ").strip().lower()

        rag_map = {"1": "basic", "2": "context_preserving", "3": "custom"}
        rag_approach = rag_map.get(rag_choice, rag_choice)

        if rag_approach == "basic":
            rag_chunk_size = 500
            rag_chunk_overlap = 100
            rag_retrieve_chunks = 3
            rag_chunking_strategy = "fixed"
        elif rag_approach == "context_preserving":
            rag_chunk_size = 2000
            rag_chunk_overlap = 400
            rag_retrieve_chunks = 8
            rag_chunking_strategy = "smart"
        elif rag_approach == "custom":
            print("\n  Custom RAG parameters:")
            rag_chunk_size = int(input_with_default("    Chunk size (chars)", "2000"))
            rag_chunk_overlap = int(input_with_default("    Chunk overlap (chars)", "400"))
            rag_retrieve_chunks = int(input_with_default("    Chunks to retrieve", "8"))
            print("    Chunking strategy:")
            print("      - fixed: Cut at exact character positions")
            print("      - smart: Try to cut at paragraph/sentence boundaries")
            rag_chunking_strategy = input_with_default("    Strategy", "smart")
            if rag_chunking_strategy not in ["fixed", "smart"]:
                rag_chunking_strategy = "smart"

        print(f"  → RAG approach: {rag_approach}")
        if rag_approach == "custom":
            print(f"     Chunk size: {rag_chunk_size}, Overlap: {rag_chunk_overlap}")
            print(f"     Retrieve: {rag_retrieve_chunks} chunks, Strategy: {rag_chunking_strategy}")

    # Confirm
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"  Type:         {agent_type}")
    print(f"  ID:           {agent_id}")
    print(f"  Directory:    {output_dir}/")
    print(f"  Name:         {agent_name}")
    if llm_provider == "default":
        print(f"  LLM:          Uses web/.env configuration")
    else:
        print(f"  Provider:     {llm_provider}")
        print(f"  Model:        {model}")
        if llm_provider == "ollama":
            print(f"  Ollama URL:   {ollama_url}")
    print(f"  Examples:     {len(examples)} question(s)")
    if agent_type in ["oneshot", "rag", "rag_metadata"]:
        print(f"  Verification: {'Yes (grounding check)' if verify_grounding else 'No'}")
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        print(f"  RAG approach: {rag_approach}")
    print("=" * 60)

    confirm = input("\nCreate agent? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        sys.exit(0)

    # Create structure
    print("\nCreating structure...")

    # Ensure tommi2 agents folder exists
    os.makedirs(get_agents_dir(), exist_ok=True)

    # Main directory and data
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # For RAG/RAG+Metadata, create documents directory
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        docs_dir = os.path.join(data_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

    # requirements.txt by type
    requirements_map = {
        "oneshot": REQUIREMENTS_ONESHOT,
        "rag": REQUIREMENTS_RAG,
        "rag_metadata": REQUIREMENTS_RAG_METADATA,
        "text2sql": REQUIREMENTS_TEXT2SQL
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

        # Add verification configuration for oneshot and rag
        if agent_type in ["oneshot", "rag", "rag_metadata"]:
            f.write("\n# ============================================\n")
            f.write("# Grounding Verification (Anti-hallucination)\n")
            f.write("# ============================================\n")
            if agent_type == "oneshot":
                f.write("# Verifies that responses are based ONLY on data.md\n")
            else:  # rag or rag_metadata
                f.write("# Verifies that responses are based ONLY on retrieved context\n")
            f.write("# NOTE: Doubles LLM calls (higher latency and cost)\n")
            f.write(f"VERIFY_GROUNDING={'true' if verify_grounding else 'false'}\n")

        # Add RAG chunking configuration for rag agents
        if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
            f.write("\n# ============================================\n")
            f.write("# RAG Chunking Configuration\n")
            f.write("# ============================================\n")
            f.write("# RAG_APPROACH: basic | context_preserving | custom\n")
            f.write("#   - basic: Fast indexing (500 chars, 100 overlap, 3 results)\n")
            f.write("#   - context_preserving: Better retrieval (2000 chars, 400 overlap, 8 results, smart boundaries)\n")
            f.write("#   - custom: Use the custom values below\n")
            f.write(f"RAG_APPROACH={rag_approach}\n")
            f.write("\n# Custom RAG parameters (only used when RAG_APPROACH=custom)\n")
            if rag_approach == "custom":
                f.write(f"RAG_CHUNK_SIZE={rag_chunk_size}\n")
                f.write(f"RAG_CHUNK_OVERLAP={rag_chunk_overlap}\n")
                f.write(f"RAG_RETRIEVE_CHUNKS={rag_retrieve_chunks}\n")
                f.write(f"RAG_CHUNKING_STRATEGY={rag_chunking_strategy}\n")
            else:
                f.write("# RAG_CHUNK_SIZE=2000\n")
                f.write("# RAG_CHUNK_OVERLAP=400\n")
                f.write("# RAG_RETRIEVE_CHUNKS=8\n")
                f.write("# RAG_CHUNKING_STRATEGY=smart\n")
    print(f"  ✓ {output_dir}/.env")

    # .gitignore
    gitignore_content = GITIGNORE
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        gitignore_content += "data/chroma_db/\n"
    with open(os.path.join(output_dir, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(gitignore_content)
    print(f"  ✓ {output_dir}/.gitignore")

    # agent.py según tipo
    if agent_type == "rag_metadata":
        # RAG+Metadata agents use a reference agent.py (config-driven, no template needed)
        import shutil as _shutil2
        reference_agent = os.path.join(os.path.dirname(__file__), "..", "agents", "responsible_ai", "agent.py")
        if os.path.exists(reference_agent):
            _shutil2.copy2(reference_agent, os.path.join(output_dir, "agent.py"))
        else:
            agent_content = AGENT_RAG_METADATA_TEMPLATE.format(
                agent_id=agent_id, agent_name=agent_name, model=model,
                system_prompt=system_prompt.replace('"', '\\"').replace("'", "\\'")
            )
            with open(os.path.join(output_dir, "agent.py"), "w", encoding="utf-8") as f:
                f.write(agent_content)

        # Generate config.json for RAG+Metadata agents
        agent_config = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "description": description,
            "welcome_message": welcome,
            "research_topic": description,
            "show_history": False,
            "example_queries": examples,
            "alliance": {
                "name": "UNINOVIS",
                "description": "UNINOVIS is a European university alliance focused on enhancing education, research, and innovation in applied data science."
            },
            "universities": {},
            "gap_analysis_examples": "",
            "prompt_level": "stringent",
            "transparency_level": "crystal_box",
            "audit_log_enabled": True,
            "reliability_green_max_llm": 20,
            "reliability_red_min_llm": 50,
            "inline_claim_highlights": {
                "enabled": True,
                "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
                "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
                "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
                "web_style": "background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;",
                "show_legend": True,
                "_style_comment": "Green = metadata, Yellow = database (RAG), Blue = web search, Red = LLM interpretation"
            }
        }
        with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(agent_config, f, indent=2, ensure_ascii=False)
        print(f"  ✓ {output_dir}/config.json")

        # Generate prompts.json for RAG+Metadata agents
        prompts_src = os.path.join(os.path.dirname(__file__), "..", "agents", "responsible_ai", "prompts.json")
        if os.path.exists(prompts_src):
            _shutil2.copy2(prompts_src, os.path.join(output_dir, "prompts.json"))
        else:
            prompts_scaffold = {
                "identity": "You are {agent_name}, a research assistant specialized in {research_topic} papers from the {alliance_name} European university alliance.\n\n{alliance_name_upper} ALLIANCE CONTEXT:\n{alliance_desc} It consists of {num_universities} universities from {num_universities} countries:\n{uni_list}\n\nYour document database contains research papers on {research_topic} topics from {alliance_name} partner universities. Each paper has metadata including the university it belongs to.\n\nIMPORTANT: When users refer to university acronyms ({acronym_list}), use the mapping above.",
                "rules": "IMPORTANT RULES:\n1. Answer questions based ONLY on the context retrieved from your document database\n2. If the retrieved context doesn't contain relevant information, clearly state that\n3. NEVER invent, fabricate, or hallucinate paper titles, author names, or paper IDs.",
                "strict": ""
            }
            with open(os.path.join(output_dir, "prompts.json"), "w", encoding="utf-8") as f:
                json.dump(prompts_scaffold, f, indent=2, ensure_ascii=False)
        print(f"  ✓ {output_dir}/prompts.json")
    else:
        agent_templates = {
            "oneshot": AGENT_PY_TEMPLATE,
            "rag": AGENT_RAG_TEMPLATE,
            "text2sql": AGENT_TEXT2SQL_TEMPLATE
        }
        agent_content = agent_templates[agent_type].format(
            agent_id=agent_id,
            agent_name=agent_name,
            model=model,
            system_prompt=system_prompt.replace('"', '\\"').replace("'", "\\'")
        )
        with open(os.path.join(output_dir, "agent.py"), "w", encoding="utf-8") as f:
            f.write(agent_content)

        # Generate config.json for non-rag_metadata agents (oneshot, rag, text2sql)
        basic_config = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "type": agent_type,
            "description": description,
            "welcome_message": welcome,
            "example_queries": examples,
            "transparency_level": "crystal_box",
            "prompt_level": "stringent",
        }
        if agent_type == "rag":
            basic_config["audit_log_enabled"] = True
            basic_config["reliability_green_max_llm"] = 20
            basic_config["reliability_red_min_llm"] = 50
            basic_config["inline_claim_highlights"] = {
                "enabled": True,
                "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
                "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
                "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
                "web_style": "background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;",
                "show_legend": True,
                "_style_comment": "Green = metadata, Yellow = database (RAG), Blue = web search, Red = LLM interpretation"
            }
        with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(basic_config, f, indent=2, ensure_ascii=False)
        print(f"  ✓ {output_dir}/config.json")
    print(f"  ✓ {output_dir}/agent.py")

    # app.py según tipo
    app_templates = {
        "oneshot": APP_PY_TEMPLATE,
        "rag": APP_PY_RAG_TEMPLATE,
        "rag_metadata": APP_PY_RAG_METADATA_TEMPLATE,
        "text2sql": APP_TEXT2SQL_TEMPLATE
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

    # data/data.md (for oneshot) or example in docs/ (for rag/rag_metadata) or README for text2sql
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        example_doc = f"# Example document for {agent_name}\n\nAdd your content here.\n\nThis file will be automatically indexed when the agent starts.\n"
        with open(os.path.join(docs_dir, "example.md"), "w", encoding="utf-8") as f:
            f.write(example_doc)
        print(f"  ✓ {docs_dir}/example.md")
        # Create sample metadata.json for rag_metadata agents
        if agent_type == "rag_metadata":
            sample_metadata = json.dumps({
                "fields": ["title", "author", "date", "file_type", "file_size", "page_count"],
                "documents": {
                    "example.md": {
                        "title": "Example Document",
                        "author": "Your Name",
                        "date": "2024-01-01"
                    }
                }
            }, indent=2, ensure_ascii=False)
            with open(os.path.join(data_dir, "metadata.json"), "w", encoding="utf-8") as f:
                f.write(sample_metadata)
            print(f"  ✓ {data_dir}/metadata.json")
            # Empty researchers.json (populated by openalex_collector or researchers_tsv.py)
            with open(os.path.join(data_dir, "researchers.json"), "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)
            print(f"  ✓ {data_dir}/researchers.json")
            # Empty institution_ids.json (populated by openalex_collector)
            with open(os.path.join(data_dir, "institution_ids.json"), "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)
            print(f"  ✓ {data_dir}/institution_ids.json")
    elif agent_type == "text2sql":
        # For text2sql, create a README explaining how to create the DB
        db_readme = f"""# Database for {agent_name}

Create your SQLite database here named `database.db`.

## Creation example

```bash
sqlite3 database.db << 'EOF'
CREATE TABLE example (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    value REAL
);

INSERT INTO example VALUES (1, 'Item 1', 100.0);
INSERT INTO example VALUES (2, 'Item 2', 200.0);
EOF
```

## Import from CSV

```bash
sqlite3 database.db << 'EOF'
.mode csv
.import your_file.csv table_name
EOF
```

Once the DB is created, the agent will be able to answer questions in natural language.
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
    run_sh_template = RUN_SH_RAG_TEMPLATE if agent_type in ["rag", "rag_vectorless", "rag_metadata"] else RUN_SH_TEMPLATE
    with open(os.path.join(output_dir, "run.sh"), "w", encoding="utf-8") as f:
        f.write(run_sh_template)
    os.chmod(os.path.join(output_dir, "run.sh"), 0o755)
    print(f"  ✓ {output_dir}/run.sh")

    # README.md según tipo
    readme_templates = {
        "oneshot": README_TEMPLATE,
        "rag": README_RAG_TEMPLATE,
        "rag_metadata": README_RAG_METADATA_TEMPLATE,
        "text2sql": README_TEXT2SQL_TEMPLATE
    }
    readme_content = readme_templates[agent_type].format(
        agent_id=agent_id,
        agent_name=agent_name,
        description=description
    )
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"  ✓ {output_dir}/README.md")

    # benchmark.py para text2sql
    if agent_type == "text2sql":
        benchmark_content = BENCHMARK_TEXT2SQL_TEMPLATE.format(
            agent_id=agent_id,
            agent_name=agent_name
        )
        with open(os.path.join(output_dir, "benchmark.py"), "w", encoding="utf-8") as f:
            f.write(benchmark_content)
        os.chmod(os.path.join(output_dir, "benchmark.py"), 0o755)
        print(f"  ✓ {output_dir}/benchmark.py")

        # Crear directorio logs para benchmark
        logs_dir = os.path.join(output_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        print(f"  ✓ {output_dir}/logs/")

    print("\n" + "=" * 60)
    print(f"{agent_type.upper()} agent created!")
    print("=" * 60)

    # Show structure by type
    print(f"\nGenerated structure:")
    print(f"  {output_dir}/")
    print(f"  ├── .env              # API key")
    print(f"  ├── requirements.txt  # Dependencies")
    print(f"  ├── agent.py          # Agent logic")
    print(f"  ├── app.py            # FastAPI server")
    print(f"  ├── run.sh            # Run script")
    print(f"  ├── README.md         # Documentation")
    if agent_type == "text2sql":
        print(f"  ├── benchmark.py      # Performance test script")
        print(f"  ├── logs/             # Benchmark results")
    if agent_type == "rag_metadata":
        print(f"  ├── config.json       # Agent configuration")
        print(f"  ├── prompts.json      # System prompt templates")
    print(f"  └── data/")
    if agent_type == "rag_metadata":
        print(f"      ├── docs/              # Documents to index")
        print(f"      ├── metadata.json      # Document metadata")
        print(f"      ├── researchers.json   # Researcher profiles")
        print(f"      └── institution_ids.json # University IDs")
    elif agent_type == "rag":
        print(f"      └── docs/         # Documents to index")
    elif agent_type == "text2sql":
        print(f"      └── database.db   # SQLite database (you must create it)")
    else:
        print(f"      └── data.md       # Agent data")

    print()
    print("Next steps:")
    step = 1
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        print(f"  {step}. Add documents (.txt, .md) in {data_dir}/docs/")
    elif agent_type == "text2sql":
        print(f"  {step}. Create your SQLite database at {data_dir}/database.db")
    else:
        print(f"  {step}. Edit {data_dir}/data.md with your data")
    step += 1

    if llm_provider == "default":
        print(f"  {step}. Make sure web/.env has the correct LLM configuration")
        step += 1
    elif api_key == "YOUR_API_KEY_HERE":
        print(f"  {step}. Add your API key in {output_dir}/.env")
        step += 1

    print(f"  {step}. Run:")
    print(f"     - (Linux/Mac) cd web && ./run_html_server.sh")
    print(f"     - (Windows) cd web && run_html_server.bat")
    step += 1
    print(f"  {step}. Open: http://localhost:8000")
    step += 1
    print(f"  {step}. Or use the CLI directly: cd web && python cli.py {agent_id}")

    print()
    print("Available endpoints:")
    print("  GET  /         - Agent info")
    print("  GET  /examples - Example questions")
    print("  POST /chat     - Send message")
    if agent_type in ["rag", "rag_vectorless", "rag_metadata"]:
        print("  POST /reindex  - Reindex documents")
        if agent_type == "rag_metadata":
            print("  GET  /metadata - View document metadata")
        print()
        print("⚠️  NOTE: RAG agents require Python 3.11-3.13")
        print("   ChromaDB is not compatible with Python 3.14+")
        print("   The run.sh script will automatically detect the correct version")
    elif agent_type == "text2sql":
        print("  GET  /schema   - View database schema")
        print()
        print("📝 NOTE: You must create the SQLite database at data/database.db")
        print("   Example: sqlite3 data/database.db < your_schema.sql")
    print()


if __name__ == "__main__":
    main()
