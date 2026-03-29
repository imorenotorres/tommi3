"""
Proyectos Euopeos - Agente RAG con ChromaDB
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
        self._config = self._load_config()
        self.system_prompt = self._build_system_prompt()
        # Reliability badge thresholds from config
        self._reliability_green_max_llm = self._config.get("reliability_green_max_llm", 20)
        self._reliability_red_min_llm = self._config.get("reliability_red_min_llm", 50)
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
            print(f"Warning: ChromaDB initialization failed: {error_msg}")
            self.chroma_client = None
            self.collection = None

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "")
        return os.getenv("MISTRAL_MODEL", "")

    def _load_config(self) -> dict:
        """Load agent configuration from config.json."""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                print(f"Agent config loaded: {config.get('agent_name', 'Unknown')}")
                return config
            except Exception as e:
                print(f"Warning: Could not load config.json: {e}")
        return {}

    def _build_system_prompt(self) -> str:
        """Build system prompt from config.json values."""
        agent_name = self._config.get("agent_name", "Proyectos Europeos")
        description = self._config.get("description", "assistant with access to a document knowledge base")

        return f"""You are {agent_name}, a helpful {description}.

IMPORTANT RULES:
1. Answer questions based ONLY on the context retrieved from your document database
2. If the retrieved context doesn't contain relevant information, clearly state that
3. Never make up or infer information not present in the provided context
4. Cite the source document when possible
5. Use the same language as the user's question

RESPONSE FORMAT:
- Provide clear, well-structured answers based on the retrieved documents
- Reference the source when the information comes from a specific document
- If no relevant information is found, explain this clearly"""

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

        print(f"RAG config: {approach} (chunks={self.chunk_size}, overlap={self.chunk_overlap}, retrieve={self.retrieve_chunks}, strategy={self.chunking_strategy})")

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
            print(f"Error extracting text from {filepath}: {e}")
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
                            for sep in ['\n\n', '. ', '\n']:
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
                        metadatas.append({"source": filename, "chunk": k})
                        ids.append(f"{filename}_{k}")

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"Indexed {len(documents)} chunks from {len(set(m['source'] for m in metadatas))} documents")

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
            context_parts.append(f"[Fuente: {meta['source']}]\n{doc}")

        return "\n\n---\n\n".join(context_parts)

    # ------------------------------------------------------------------
    # Reliability badge system
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_claims(response: str) -> list:
        """Extract factual claims (titles, names, years, bold text) from a response."""
        claims = []
        quoted = re.findall(r'"([^"]{10,})"', response)
        claims.extend(quoted)
        bold = re.findall(r'\*\*([^*]{5,})\*\*', response)
        non_bold = {"Note", "Summary", "Key findings", "Important", "References", "UNINOVIS"}
        claims.extend([b for b in bold if b not in non_bold])
        author_matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', response)
        non_names = {"No papers", "No research", "No study", "High reliability",
                     "Good reliability", "Poor reliability", "View publications",
                     "View interactive", "Partially reliable", "Source Database",
                     "Source Metadata", "No verifiable"}
        claims.extend([a for a in author_matches if a not in non_names])
        years = re.findall(r'\b(20\d{2})\b', response)
        claims.extend(years)
        paper_ids = re.findall(r'\b(W\d{7,})\b', response)
        claims.extend(paper_ids)
        return claims

    @classmethod
    def _grounding_breakdown(cls, response: str, rag_ctx: str) -> dict:
        """Check claims against RAG context. For plain RAG agents (no metadata)."""
        claims = cls._extract_claims(response)
        if not claims:
            return {"database_pct": 100, "llm_pct": 0, "total_claims": 0}

        rag_lower = (rag_ctx or "").lower()
        database_count = 0
        llm_count = 0

        for claim in claims:
            claim_lower = claim.lower()
            if rag_lower and claim_lower in rag_lower:
                database_count += 1
            else:
                words = claim_lower.split()
                fuzzy_matched = False
                if len(words) >= 2:
                    surname = words[-1]
                    if len(surname) > 3 and rag_lower and surname in rag_lower:
                        database_count += 1
                        fuzzy_matched = True
                if not fuzzy_matched:
                    llm_count += 1

        total = len(claims)
        return {
            "database_pct": round(database_count / total * 100),
            "llm_pct": round(llm_count / total * 100),
            "total_claims": total,
        }

    @staticmethod
    def _source_badge(source_type: str, breakdown: dict = None) -> str:
        """Return an HTML badge indicating the reliability of the response."""
        if source_type is None:
            return ""

        if breakdown and breakdown.get("total_claims", 0) > 0:
            parts = []
            if breakdown.get("database_pct", 0) > 0:
                parts.append(f"Database: {breakdown['database_pct']}%")
            if breakdown.get("llm_pct", 0) > 0:
                parts.append(f"LLM: {breakdown['llm_pct']}%")
            pct_str = f" ({' | '.join(parts)})"
            llm_pct = breakdown.get("llm_pct", 0)
            if 0 < llm_pct < 100:
                note = '<br><span style="font-weight:normal;font-size:0.8em;font-style:italic;">Factual claims are grounded in the document database (RAG). Suggestions and interpretations may come from the LLM.</span>'
            else:
                note = ""
        else:
            pct_str = ""
            note = ""

        if source_type == "Grounded":
            return (
                f'<div style="margin-bottom:10px;">'
                f'<span style="background-color:#d4edda;color:#155724;'
                f'padding:2px 8px;border-radius:4px;font-size:0.85em;'
                f'font-weight:bold;">Reliability: High{pct_str}</span>'
                f'{note}</div>\n\n'
            )
        elif source_type == "Partial":
            return (
                f'<div style="margin-bottom:10px;">'
                f'<span style="background-color:#fff3cd;color:#856404;'
                f'padding:2px 8px;border-radius:4px;font-size:0.85em;'
                f'font-weight:bold;">Reliability: Good{pct_str}</span>'
                f'{note}</div>\n\n'
            )
        else:  # Ungrounded
            return (
                f'<div style="margin-bottom:10px;">'
                f'<span style="background-color:#f8d7da;color:#721c24;'
                f'padding:2px 8px;border-radius:4px;font-size:0.85em;'
                f'font-weight:bold;">Reliability: Poor{pct_str}</span>'
                f'{note}</div>\n\n'
            )

    @staticmethod
    def _is_followup_query(user_message: str) -> bool:
        """Detect short follow-up queries."""
        msg = user_message.strip().lower()
        if len(msg) < 60:
            patterns = [
                r'^(expand|elaborate|more|details|explain|continue|go on|yes|no|ok)',
                r'^\d+$',
                r'^(tell me )?more (about|on|details)',
                r'^what about',
                r'^(and|but) ',
                r'^can you (expand|elaborate|explain)',
            ]
            return any(re.match(p, msg) for p in patterns)
        return False

    @staticmethod
    def _is_not_found_response(text: str) -> bool:
        """Detect if the LLM response is a 'not found' refusal."""
        text_lower = text.lower()
        phrases = [
            "could not find", "couldn't find", "not found", "no papers",
            "no relevant", "no results", "no study", "no research",
            "no matching", "does not include", "do not include",
            "not available", "no information", "no data",
        ]
        return any(phrase in text_lower for phrase in phrases)

    def _compute_badge(self, llm_content: str, context: str) -> str:
        """Compute reliability badge for a response."""
        breakdown = self._grounding_breakdown(llm_content, context)
        llm_pct = breakdown["llm_pct"]

        if llm_pct == 100 and self._is_not_found_response(llm_content):
            return self._source_badge("Grounded", breakdown)
        elif llm_pct <= self._reliability_green_max_llm:
            return self._source_badge("Grounded", breakdown)
        elif llm_pct < self._reliability_red_min_llm:
            return self._source_badge("Partial", breakdown)
        else:
            return self._source_badge("Ungrounded", breakdown)

    def chat(self, user_message: str, history: list = None) -> str:
        """Envía un mensaje con contexto RAG y obtiene respuesta."""
        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"

        # Follow-ups use conversation history, no badge
        is_followup = self._is_followup_query(user_message) and history

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\n\nContexto relevante de la base de conocimiento:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        llm_content = response.choices[0].message.content

        # Compute reliability badge
        if is_followup:
            badge = ""
        else:
            badge = self._compute_badge(llm_content, context)

        response_content = badge + llm_content

        self._query_history.append({
            'question': user_message,
            'response_length': len(response_content)
        })

        return response_content

    async def chat_stream(self, user_message: str, history: list = None):
        """Envía un mensaje con contexto RAG y obtiene respuesta en streaming."""
        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"
            return

        is_followup = self._is_followup_query(user_message) and history

        context = self._retrieve_context(user_message)

        system_with_context = self.system_prompt
        if context:
            system_with_context += f"\n\nContexto relevante de la base de conocimiento:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Stream response
        full_response = ""
        async for chunk in await self.client.chat.stream_async(
            model=self.model,
            messages=messages
        ):
            if chunk.data.choices[0].delta.content:
                full_response += chunk.data.choices[0].delta.content
                yield chunk.data.choices[0].delta.content

        # Deferred reliability badge (after full response is collected)
        if not is_followup:
            badge = self._compute_badge(full_response, context)
            if badge:
                yield ("badge", badge)

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
        # Borrar colección existente
        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._index_documents()
        return self.collection.count()
