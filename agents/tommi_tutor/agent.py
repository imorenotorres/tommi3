"""
Tommi virtual tutor - Agente RAG con Mistral API + ChromaDB
Versión RAG que usa búsqueda semántica en lugar de cargar todo en contexto
"""

import os
import sys
import json
import re

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient
from error_codes import format_error, DATA_CHROMADB_PYTHON_INCOMPATIBLE, DATA_CHROMADB_ERROR

from pypdf import PdfReader


class ChromaDBError(Exception):
    """Error específico de ChromaDB con código de error."""
    def __init__(self, error_dict):
        self.error_dict = error_dict
        super().__init__(error_dict.get("error", "ChromaDB error"))


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = os.getenv("OLLAMA_MODEL", "mistral-small-latest") if os.getenv("LLM_PROVIDER", "mistral") == "ollama" else "mistral-small-latest"
        self.system_prompt = """You are Tommi virtual tutor, a helpful assistant specialized in teaching about AI Agents development using the TOMMI framework.

Your capabilities include:
- Helping users understand how to create and deploy AI agents with TOMMI
- Explaining the different agent types (oneshot, RAG, ConsultaBD_SQL)
- Providing guidance on configuration, troubleshooting, and best practices
- Answering questions about LLM setup (Mistral Cloud, Ollama)

CRITICAL RULES:
1. Answer questions based ONLY on the context provided from the knowledge base below.
2. If you cannot find relevant information in the context, say: "I don't have information about that in my knowledge base."
3. NEVER use your general knowledge. Only use the text provided in the context.
4. All information comes from a database maintained by IT-UMA (Universidad de Málaga IT department).
5. When discussing LLMs, only talk about European LLMs."""

        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"

        # Query history for the sidebar
        self._query_history = []

        # ChromaDB se inicializa bajo demanda (lazy initialization)
        self.chroma_client = None
        self.collection = None
        self.embedding_fn = None
        self._chromadb_error = None
        self._chromadb_initialized = False

    def _init_chromadb(self):
        """Inicializa ChromaDB de forma diferida (lazy initialization)."""
        if self._chromadb_initialized:
            return

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
            print(f"Warning: ChromaDB initialization failed: {error_msg}")
            self.chroma_client = None
            self.collection = None

        self._chromadb_initialized = True

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
            filename = os.path.basename(filepath)
            print(f"Error 303: Error extrayendo texto de {filename}: {e}")
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
            print(f"Documents in sync ({len(indexed)} indexed)")
            return

        # Eliminar documentos huérfanos de ChromaDB
        if removed_docs:
            print(f"Removing {len(removed_docs)} deleted documents from index...")
            for source in removed_docs:
                # Obtener IDs de chunks de este documento
                results = self.collection.get(where={"source": source})
                if results["ids"]:
                    self.collection.delete(ids=results["ids"])
            print(f"Removed: {', '.join(removed_docs)}")

        # Indexar documentos nuevos
        if new_docs:
            print(f"Indexing {len(new_docs)} new documents...")
            self._index_documents(only_files=new_docs)
            print(f"Added: {', '.join(new_docs)}")

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
                # Dividir en chunks de ~2000 caracteres con overlap de 400
                # (context-preserving approach for better retrieval)
                chunk_size = 2000
                overlap = 400
                chunks = []
                start = 0
                while start < len(content):
                    end = start + chunk_size
                    chunk = content[start:end]
                    chunks.append(chunk)
                    start = end - overlap

                for k, chunk in enumerate(chunks):
                    documents.append(chunk)
                    metadatas.append({"source": filename, "chunk": k})
                    ids.append(f"{filename}_{k}")

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"Indexed {len(documents)} chunks from {len(set(m['source'] for m in metadatas))} documents")

    def _retrieve_context(self, query: str, n_results: int = 5) -> str:
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
            context_parts.append(f"[Source: {meta['source']}]\n{doc}")

        return "\n\n---\n\n".join(context_parts)

    def _verify_grounding(self, response: str, user_question: str, context: str) -> dict:
        """
        Verifica si la respuesta está basada SOLO en el contexto recuperado.

        Args:
            response: Respuesta generada por el agente
            user_question: Pregunta original del usuario
            context: Contexto recuperado de ChromaDB

        Returns:
            dict con {"grounded": bool, "reason": str}
        """
        if not context:
            return {"grounded": True, "reason": "No context to verify against"}

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided context.

RETRIEVED CONTEXT:
{context}

USER QUESTION: {user_question}

AGENT RESPONSE: {response}

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
{{"grounded": true, "reason": "brief explanation"}}
or
{{"grounded": false, "reason": "specific claim that was not in the context"}}"""

        result = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": verify_prompt}]
        )

        try:
            content = result.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\n?", "", content)
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return {"grounded": True, "reason": "Verification parsing failed"}

    def _get_fallback_response(self, user_question: str) -> str:
        """Generates a response when verification fails."""
        return (
            "I'm sorry, I cannot find specific information about that in my knowledge base. "
            "I can only provide information that is explicitly documented in my sources. "
            "Could you ask something different or rephrase your question?"
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

        # Inicializar ChromaDB si no está inicializado
        if not self._chromadb_initialized:
            self._init_chromadb()

        # Verificar si ChromaDB está disponible
        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"

        # Recuperar contexto relevante
        context = self._retrieve_context(user_message)

        # Construir prompt con contexto
        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        response_content = response.choices[0].message.content

        if should_verify and context:
            verification = self._verify_grounding(response_content, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                response_content = self._get_fallback_response(user_message)

        # Track query in history
        self._query_history.append({
            'question': user_message,
            'response_length': len(response_content)
        })

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

        # Inicializar ChromaDB si no está inicializado
        if not self._chromadb_initialized:
            yield ("status", "Creating ChromaDB for the agent...")
            self._init_chromadb()

        # Mostrar "Thinking..." una vez la BD está lista
        yield ("status", "Thinking...")

        # Verificar si ChromaDB está disponible
        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"
            return

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

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
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                full_response = self._get_fallback_response(user_message)

            # Track query in history
            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })
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
            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {
                'question': entry['question'],
                'num_results': 1  # For RAG agents, each query = 1 result
            }
            for entry in self._query_history
        ]

    def reindex(self):
        """Reindexa todos los documentos (útil después de añadir nuevos)."""
        # Inicializar ChromaDB si no está inicializado
        if not self._chromadb_initialized:
            self._init_chromadb()

        if self._chromadb_error:
            return 0

        # Borrar colección existente
        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._index_documents()
        return self.collection.count()
