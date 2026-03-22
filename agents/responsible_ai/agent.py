"""
Responsible AI - Agente RAG+Metadata con ChromaDB
Soporta Mistral Cloud y Ollama via LLM_PROVIDER
Incluye extracción y filtrado por metadatos de documentos.

NOTA: ChromaDB no es compatible con Python 3.14+. Requiere Python 3.11-3.13.
"""

import os
import sys
import json
import re
import glob
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
    def __init__(self, progress_callback=None):
        self._progress_callback = progress_callback
        self.client = LLMClient()
        self.model = self._get_model()
        self._config = self._load_config()
        self.system_prompt = self._build_system_prompt()
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Query history for the sidebar
        self._query_history = []
        # Document metadata cache
        self._documents_metadata = {}

        # RAG Chunking Configuration
        self._load_rag_config()

        # Load metadata configuration
        self._load_metadata_config()

        # Load researchers index
        self._researchers_by_uni = {}
        researchers_path = os.path.join(os.path.dirname(__file__), "data", "researchers.json")
        if os.path.exists(researchers_path):
            try:
                with open(researchers_path, "r", encoding="utf-8") as f:
                    self._researchers_by_uni = json.load(f)
                total_r = sum(len(v) for v in self._researchers_by_uni.values())
                print(f"Researchers index loaded: {total_r} researchers across {len(self._researchers_by_uni)} universities")
            except Exception as e:
                print(f"Warning: Could not load researchers.json: {e}")

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
        """Build the system prompt from config.json values."""
        cfg = self._config
        agent_name = cfg.get("agent_name", "Research Assistant")
        research_topic = cfg.get("research_topic", "research papers")
        alliance = cfg.get("alliance", {})
        alliance_name = alliance.get("name", "")
        alliance_desc = alliance.get("description", "")
        universities = cfg.get("universities", {})
        agent_id = cfg.get("agent_id", "agent")

        # Build university list
        uni_lines = []
        for acronym, info in universities.items():
            uni_lines.append(f"- {acronym}: {info['name']} ({info['country']})")
        uni_list = "\n".join(uni_lines)

        # Build acronym examples for disambiguation
        acronym_list = ", ".join(universities.keys())

        return f"""You are {agent_name}, a research assistant specialized in {research_topic} papers from the {alliance_name} European university alliance.

{alliance_name.upper()} ALLIANCE CONTEXT:
{alliance_desc} It consists of {len(universities)} universities from {len(universities)} countries:
{uni_list}

Your document database contains research papers on {research_topic} topics from {alliance_name} partner universities. Each paper has metadata including the university it belongs to.

IMPORTANT: When users refer to university acronyms ({acronym_list}), use the mapping above.

CRITICAL — UNINOVIS PARTNER RECOGNITION:
The {len(universities)} universities listed above are the ONLY {alliance_name} partners. Many papers have co-authors from external institutions (e.g., other universities, hospitals, research centres). These external institutions are NOT {alliance_name} partners. When listing papers or universities in your answers:
- ONLY refer to the {len(universities)} universities above as "{alliance_name} universities" or "{alliance_name} partners".
- NEVER present any other institution as a {alliance_name} partner, even if it appears in a paper's affiliations or author list.
- Each paper in the database is assigned to one {alliance_name} university. Use that assignment, not the full affiliations list, to determine which {alliance_name} partner a paper belongs to.
- When the user asks about collaborations between {alliance_name} partners, use ONLY the CROSS-UNIVERSITY COLLABORATIONS data provided below. Do NOT infer cross-university collaborations from affiliations of non-{alliance_name} institutions.

IMPORTANT RULES:
1. Answer questions based ONLY on the context retrieved from your document database
2. If the retrieved context doesn't contain relevant information, clearly state that
3. Never make up or infer information not present in the provided context
4. When citing sources, include the document title, authors, and university
5. Use the same language as the user's question
6. When the user asks about metadata (e.g., "documents by author X", "papers from a university"), use the metadata information provided
7. When the user asks about content, use the document text provided

RESPONSE FORMAT:
- Provide clear, well-structured answers based on the retrieved documents
- Reference the source document, authors, and university when relevant
- If filtering by metadata, mention which filters were applied
- If no relevant information is found, explain this clearly
- When listing researchers or papers, provide the COMPLETE list. Only if the list exceeds 50 researchers, cap at 50 and state the total count. Do NOT add notes about "representative sample" or suggest narrowing the query unless you actually had to cap the list.
  - For each university, use a compact format: "**ACRONYM** (N papers): Author1, Author2, Author3, ..."

INTERACTIVE MAP FEATURE — STRICT RULES:
Before including ANY map link in your response, perform this check:
- Does the user's question contain the word "figure" or "map"? If YES → you may include a map link. If NO → you MUST NOT include any map link.
The words "list", "show", "tell", "describe", "what", "which" do NOT count — only "figure" or "map".
Examples of questions that do NOT get a map link:
- "List the topics most studied" → NO map (no "figure"/"map" word)
- "Show the researchers working on ethics" → NO map
- "What are the most studied topics?" → NO map
Examples of questions that DO get a map link:
- "Show a figure of publications" → YES (contains "figure")
- "Show a map of collaborations" → YES (contains "map")
NEVER include more than ONE map link per response.

DECISION RULE for choosing figure type (only when a map link IS allowed):
1. Does the user's question mention ANY subject, topic, or keyword (e.g. "ethics", "AI", "fairness", "XAI", "studies on X", "X papers")? → Use TOPIC figure.
2. Does the user ask for ALL publications, total papers, or overall numbers with NO subject/topic at all? → Use PUBLICATIONS figure.
3. Does the user ask about collaborations between universities? → Use COLLABORATION figure.
If in doubt between TOPIC and PUBLICATIONS, ALWAYS choose TOPIC.

Examples:
- "figure of AI and Ethics studies per partner" → TOPIC (topic="AI Ethics")
- "figure of papers on fairness" → TOPIC (topic="fairness")
- "figure of all publications" → PUBLICATIONS
- "figure of papers published in 2025" → PUBLICATIONS with ?year=2025
- "figure of collaborations on XAI" → COLLABORATION with ?topic=XAI

Figure link formats:

- TOPIC figure:
   [View interactive map for "TOPIC"](/api/agents/{agent_id}/topic-map?topic=TOPIC)
   Replace TOPIC with the topic extracted from the user's question (URL-encoded, e.g. topic=AI%20Ethics).

- PUBLICATIONS figure:
   [View publications map](/api/agents/{agent_id}/publications-map)
   With optional year filter: ?year=YEAR (e.g. ?year=2025)

- COLLABORATION figure:
   [View collaboration map](/api/agents/{agent_id}/collaboration-map)
   With optional filters: ?topic=TOPIC and/or ?year=YEAR
"""

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

    def _load_metadata_config(self):
        """Load metadata configuration and external metadata from data/metadata.json.

        The metadata.json file can contain:
        - "fields": list of metadata field names to track
        - "documents": dict mapping filenames to their metadata values,
          e.g. {"file.pdf": {"author": "Dr. Smith", "university": "UMA"}}

        External metadata supplements auto-extracted metadata (PDF metadata).
        If a field is provided in both, the external value takes precedence.
        """
        config_path = os.path.join(os.path.dirname(__file__), "data", "metadata.json")
        self.metadata_fields = ["title", "author", "date", "file_type", "file_size", "page_count"]
        self._external_metadata = {}
        self._university_paper_counts = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if "fields" in config:
                    self.metadata_fields = config["fields"]
                if "documents" in config and isinstance(config["documents"], dict):
                    self._external_metadata = config["documents"]
                # Derive per-document metadata from universities structure
                if "universities" in config and isinstance(config["universities"], dict):
                    for acronym, uni_data in config["universities"].items():
                        uni_name = uni_data.get("name", acronym)
                        paper_count = uni_data.get("papers_count", 0)
                        self._university_paper_counts[acronym] = {
                            "name": uni_name,
                            "count": paper_count,
                        }
                        for paper in uni_data.get("papers", []):
                            paper_id = paper.get("id", "")
                            if paper_id:
                                filename = f"{paper_id}.pdf"
                                authors = ", ".join(a.get("name", "") for a in paper.get("authors", []))
                                self._external_metadata[filename] = {
                                    "university": uni_name,
                                    "university_acronym": acronym,
                                    "title": paper.get("title", ""),
                                    "author": authors,
                                    "date": paper.get("publication_date", ""),
                                }
                if self._external_metadata:
                    print(f"External metadata loaded for {len(self._external_metadata)} document(s)")
                print(f"Metadata config loaded: fields={self.metadata_fields}")
            except Exception as e:
                print(f"Warning: Could not load metadata config: {e}")

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

        metadata = {
            "title": os.path.splitext(filename)[0],
            "author": "",
            "date": "",
            "file_type": file_type,
            "file_size": file_size,
            "page_count": 0,
            "source": filename,
        }

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
                print(f"Warning: Could not extract PDF metadata from {filename}: {e}")

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
        """Sincroniza documentos: indexa nuevos y elimina huérfanos.
        Also reindexes if external metadata has changed (e.g. university info)."""
        indexed = self._get_indexed_sources()
        on_disk = self._get_docs_files()

        new_docs = on_disk - indexed
        removed_docs = indexed - on_disk

        # Check if existing chunks are missing university metadata that we now have
        needs_reindex = False
        if not new_docs and not removed_docs and self._external_metadata and self.collection and self.collection.count() > 0:
            sample = self.collection.peek(limit=1)
            if sample and sample.get("metadatas"):
                meta = sample["metadatas"][0]
                source = meta.get("source", "")
                if source in self._external_metadata and not meta.get("university"):
                    needs_reindex = True
                    print("Detected missing university metadata in index, triggering reindex...")

        if not new_docs and not removed_docs and not needs_reindex:
            print(f"Documents in sync ({len(indexed)} indexed)")
            # Load metadata for existing documents
            self._refresh_metadata_cache()
            return

        if needs_reindex:
            print("Reindexing all documents to update metadata...")
            self.chroma_client.delete_collection("documents")
            self.collection = self.chroma_client.create_collection(
                name="documents",
                embedding_function=self.embedding_fn
            )
            self._documents_metadata = {}
            self._index_documents()
            self._refresh_metadata_cache()
            return

        if removed_docs:
            print(f"Removing {len(removed_docs)} deleted documents from index...")
            for source in removed_docs:
                results = self.collection.get(where={"source": source})
                if results["ids"]:
                    self.collection.delete(ids=results["ids"])
                if source in self._documents_metadata:
                    del self._documents_metadata[source]
            print(f"Removed: {', '.join(removed_docs)}")

        if new_docs:
            print(f"Indexing {len(new_docs)} new documents...")
            self._index_documents(only_files=new_docs)
            print(f"Added: {', '.join(new_docs)}")

        self._refresh_metadata_cache()

    def _refresh_metadata_cache(self):
        """Refresh the metadata cache from indexed documents."""
        docs_path = os.path.join(os.path.dirname(__file__), "data", "docs")
        if not os.path.exists(docs_path):
            return

        self._documents_metadata = {}
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

        # Build file list first to know total count for progress reporting
        all_files = [
            f for f in os.listdir(docs_path)
            if os.path.isfile(os.path.join(docs_path, f))
            and (only_files is None or f in only_files)
        ]
        total_files = len(all_files)

        for i, filename in enumerate(all_files):
            filepath = os.path.join(docs_path, filename)

            if self._progress_callback:
                self._progress_callback(i + 1, total_files, filename)

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
                            for sep in ['\n\n', '. ', '\n']:
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
                        chunk_metadata = {
                            "source": filename,
                            "chunk": k,
                            "title": file_metadata.get("title", ""),
                            "author": file_metadata.get("author", ""),
                            "date": file_metadata.get("date", ""),
                            "file_type": file_metadata.get("file_type", ""),
                            "page_count": file_metadata.get("page_count", 0),
                            "university": file_metadata.get("university", ""),
                            "university_acronym": file_metadata.get("university_acronym", ""),
                        }
                        metadatas.append(chunk_metadata)
                        ids.append(f"{filename}_{k}")

        if documents:
            # Add in batches to avoid ChromaDB max batch size limit
            batch_size = 5000
            for i in range(0, len(documents), batch_size):
                self.collection.add(
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    ids=ids[i:i+batch_size],
                )
            print(f"Indexed {len(documents)} chunks from {len(set(m['source'] for m in metadatas))} documents (with metadata)")

    def _detect_university_filter(self, query: str) -> dict:
        """Detect university acronyms in the query and return a ChromaDB where filter.

        If exactly one university is mentioned, returns {"university_acronym": "ACRONYM"}.
        If multiple are mentioned, returns a $in filter.
        Returns empty dict if no university is detected.
        """
        query_upper = query.upper()
        universities = self._config.get("universities", {})
        matched = set()

        for acronym in universities:
            # Match the acronym as a whole word
            if re.search(r'\b' + re.escape(acronym) + r'\b', query_upper):
                matched.add(acronym)

        # Also check full university names
        query_lower = query.lower()
        for acronym, info in universities.items():
            name = info.get("name", "").lower()
            if name and name in query_lower:
                matched.add(acronym)

        if len(matched) == 1:
            return {"university_acronym": matched.pop()}
        elif len(matched) > 1:
            return {"university_acronym": {"$in": list(matched)}}
        return {}

    def _retrieve_context(self, query: str, n_results: int = None, metadata_filter: dict = None) -> str:
        """Recupera contexto relevante para la query, con filtro de metadatos opcional.

        Args:
            query: The search query
            n_results: Number of chunks to retrieve
            metadata_filter: Optional ChromaDB where filter for metadata
                            e.g. {"author": "John"} or {"file_type": "pdf"}
        """
        if n_results is None:
            n_results = self.retrieve_chunks
        if self.collection is None or self.collection.count() == 0:
            return ""

        query_params = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if metadata_filter:
            query_params["where"] = metadata_filter

        results = self.collection.query(**query_params)

        if not results['documents'][0]:
            return ""

        context_parts = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            meta_info = f"[Source: {meta['source']}"
            if meta.get('title'):
                meta_info += f" | Title: {meta['title']}"
            if meta.get('author'):
                meta_info += f" | Author: {meta['author']}"
            if meta.get('date'):
                meta_info += f" | Date: {meta['date']}"
            if meta.get('university'):
                meta_info += f" | University: {meta['university']}"
            if meta.get('university_acronym'):
                meta_info += f" ({meta['university_acronym']})"
            meta_info += "]"
            context_parts.append(f"{meta_info}\n{doc}")

        return "\n\n---\n\n".join(context_parts)

    @property
    def UNIVERSITY_COORDS(self):
        """University coordinates for map visualization, loaded from config.json."""
        universities = self._config.get("universities", {})
        coords = {}
        for acronym, info in universities.items():
            coords[acronym] = {
                "lat": info.get("lat", 0),
                "lon": info.get("lon", 0),
                "name": info.get("name", acronym),
                "country": info.get("country", ""),
            }
        return coords

    def get_all_papers_by_university(self, year: int = None) -> dict:
        """Return all papers grouped by university, optionally filtered by year.

        Args:
            year: If provided, only include papers from this publication year.

        Returns a dict: {acronym: {"name": ..., "country": ..., "lat": ..., "lon": ..., "count": N, "papers": [...]}}
        """
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        results = {}

        for json_path in glob.glob(os.path.join(data_dir, "*_papers.json")):
            acronym = os.path.basename(json_path).replace("_papers.json", "").upper()
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    papers = json.load(f)
            except Exception:
                continue

            all_papers = []
            for paper in papers:
                if year is not None and paper.get("publication_year") != year:
                    continue
                all_papers.append({
                    "id": paper.get("id", ""),
                    "title": paper.get("title", ""),
                    "authors": [a.get("name", "") for a in paper.get("authors", [])[:3]],
                    "year": paper.get("publication_year"),
                    "doi": paper.get("doi", ""),
                    "cited_by_count": paper.get("cited_by_count", 0),
                })

            coords = self.UNIVERSITY_COORDS.get(acronym, {})
            results[acronym] = {
                "name": coords.get("name", acronym),
                "country": coords.get("country", ""),
                "lat": coords.get("lat", 0),
                "lon": coords.get("lon", 0),
                "count": len(all_papers),
                "papers": all_papers,
            }

        return results

    # Keyword patterns for matching UNINOVIS universities in affiliation strings.
    # IMPORTANT: Use specific institution names, NOT just city names, to avoid
    # false matches (e.g. "Universitätsklinikum Würzburg" is NOT THWS).
    UNINOVIS_AFFILIATION_KEYWORDS = {
        "USPN":  ["sorbonne paris nord", "paris 13", "université paris nord"],
        "UDCLV": ["vanvitelli", "university of campania"],
        "UMA":   ["málaga", "malaga"],
        "KK":    ["kauno kolegija", "kaunas kolegija"],
        "UT":    ["universiteti i tiranës", "universiteti i tiranes",
                  "=university of tirana"],
        "THWS":  ["technical university of applied sciences würzburg",
                  "technical university of applied sciences wurzburg",
                  "hochschule für angewandte wissenschaften würzburg",
                  "thws", "fhws"],
        "TAMK":  ["tampere university of applied sciences", "tampereen ammattikorkeakoulu"],
        "THUAS": ["hague university of applied sciences", "haagse hogeschool"],
    }

    def get_cross_university_papers(self, topic: str = None, year: int = None) -> list:
        """Find papers that connect two or more UNINOVIS universities.

        Args:
            topic: Optional topic to filter by. When provided, only papers
                   matching the topic (via search_papers_by_topic) are considered.
            year: Optional publication year to filter by.

        Detection method: checks if a paper's affiliations list contains
        names matching 2+ UNINOVIS universities.

        Returns a list of dicts with paper info and matched universities.
        """
        data_dir = os.path.join(os.path.dirname(__file__), "data")

        def match_uninovis(affiliation: str) -> set:
            aff_lower = affiliation.lower()
            matched = set()
            for acronym, keywords in self.UNINOVIS_AFFILIATION_KEYWORDS.items():
                for kw in keywords:
                    if kw.startswith("="):
                        # Exact match: affiliation must equal the keyword
                        if aff_lower == kw[1:]:
                            matched.add(acronym)
                            break
                    else:
                        # Substring match (default)
                        if kw in aff_lower:
                            matched.add(acronym)
                            break
            return matched

        # Load all papers grouped by university file
        all_papers = {}  # (title, acronym) -> paper dict

        for json_path in glob.glob(os.path.join(data_dir, "*_papers.json")):
            acronym = os.path.basename(json_path).replace("_papers.json", "").upper()
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    papers = json.load(f)
            except Exception:
                continue
            for paper in papers:
                title = paper.get("title", "")
                all_papers[(title, acronym)] = paper

        # Filter by topic if provided
        if topic:
            topic_results = self.search_papers_by_topic(topic)
            topic_titles = set()
            for uni_data in topic_results.values():
                for p in uni_data.get("papers", []):
                    topic_titles.add(p.get("title", ""))
            all_papers = {k: v for k, v in all_papers.items() if v.get("title", "") in topic_titles}

        # Filter by year if provided
        if year:
            all_papers = {k: v for k, v in all_papers.items() if v.get("publication_year") == year}

        # Track which UNINOVIS universities each paper title connects to
        from collections import defaultdict
        paper_unis = defaultdict(set)  # title -> set of UNINOVIS acronyms

        # Affiliation-based matching
        for (title, acronym), paper in all_papers.items():
            paper_unis[title].add(acronym)
            for aff in paper.get("affiliations", []):
                paper_unis[title].update(match_uninovis(aff))

        # Collect papers connected to 2+ UNINOVIS universities
        seen_titles = set()
        cross_papers = []

        for (title, acronym), paper in all_papers.items():
            if title in seen_titles:
                continue
            unis = paper_unis.get(title, set())
            if len(unis) >= 2:
                seen_titles.add(title)
                authors = [a.get("name", "") for a in paper.get("authors", [])]
                cross_papers.append({
                    "title": title,
                    "authors": authors,
                    "universities": sorted(unis),
                    "year": paper.get("publication_year"),
                    "doi": paper.get("doi", ""),
                    "cited_by_count": paper.get("cited_by_count", 0),
                })

        return cross_papers

    def get_collaboration_map_data(self, topic: str = None, year: int = None) -> dict:
        """Return collaboration data structured for the map visualization.

        Args:
            topic: Optional topic to filter collaborations by.
            year: Optional publication year to filter by.

        Returns a dict with:
        - "universities": {acronym: {name, country, lat, lon, collab_count}}
        - "connections": [{from, to, count, papers: [{title, authors, year, doi}]}]
        """
        from collections import defaultdict
        from itertools import combinations

        cross_papers = self.get_cross_university_papers(topic=topic, year=year)
        coords = self.UNIVERSITY_COORDS

        # Count collaborations per university pair
        pair_papers = defaultdict(list)
        for paper in cross_papers:
            unis = paper["universities"]
            for a, b in combinations(unis, 2):
                pair_key = tuple(sorted([a, b]))
                pair_papers[pair_key].append({
                    "title": paper["title"],
                    "authors": paper["authors"][:3],
                    "year": paper.get("year"),
                    "doi": paper.get("doi", ""),
                })

        # Build university nodes (only those involved in collaborations)
        uni_collab_count = defaultdict(int)
        for (a, b), papers in pair_papers.items():
            uni_collab_count[a] += len(papers)
            uni_collab_count[b] += len(papers)

        universities = {}
        for acronym, info in coords.items():
            universities[acronym] = {
                "name": info.get("name", acronym),
                "country": info.get("country", ""),
                "lat": info.get("lat", 0),
                "lon": info.get("lon", 0),
                "collab_count": uni_collab_count.get(acronym, 0),
            }

        # Build connections list
        connections = []
        for (a, b), papers in sorted(pair_papers.items()):
            connections.append({
                "from": a,
                "to": b,
                "count": len(papers),
                "papers": papers,
            })

        return {
            "universities": universities,
            "connections": connections,
            "total_collaborations": len(cross_papers),
        }

    @staticmethod
    def build_collaboration_map_html(data_json: str) -> str:
        """Build HTML for the interactive collaboration map with connection lines."""
        return ("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNINOVIS Collaboration Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f8fafc; color: #1e293b; }
        .header { background: #1e293b; padding: 16px 24px; border-bottom: 3px solid #7c3aed; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 1.3em; color: #ffffff; font-weight: 600; }
        .header h1 span { color: #a78bfa; }
        .header p { font-size: 0.9em; color: #94a3b8; margin-top: 2px; }
        .header-left { flex: 1; }
        .header-badge { background: #7c3aed; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 0.8em; font-weight: 600; letter-spacing: 0.5px; }
        #map { height: calc(100vh - 72px); width: 100%; }
        .collab-popup { min-width: 280px; }
        .collab-popup h3 { color: #1e293b; margin-bottom: 8px; font-size: 1.05em; font-weight: 600; }
        .collab-popup .count { font-size: 1.2em; font-weight: 700; color: #7c3aed; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; }
        .collab-popup .papers-list { max-height: 220px; overflow-y: auto; font-size: 0.82em; }
        .collab-popup .paper-item { padding: 5px 0; border-bottom: 1px solid #f1f5f9; }
        .collab-popup .paper-item:last-child { border-bottom: none; }
        .collab-popup .paper-title { font-weight: 500; color: #1e293b; }
        .collab-popup .paper-meta { color: #64748b; font-size: 0.9em; margin-top: 2px; }
        .collab-popup a { color: #7c3aed; text-decoration: none; }
        .collab-popup a:hover { text-decoration: underline; }
        .uni-popup { min-width: 220px; }
        .uni-popup h3 { color: #1e293b; margin-bottom: 4px; font-size: 1.05em; }
        .uni-popup .country { color: #64748b; font-size: 0.85em; margin-bottom: 6px; }
        .uni-popup .count { font-weight: 600; color: #7c3aed; }
        .legend { background: #ffffff; padding: 14px 18px; border-radius: 10px; color: #1e293b; font-size: 0.85em; line-height: 1.8; box-shadow: 0 2px 8px rgba(0,0,0,0.12); border: 1px solid #e2e8f0; }
        .legend h4 { margin-bottom: 6px; color: #1e293b; font-weight: 600; font-size: 0.95em; }
        .legend .line-sample { display: inline-block; width: 30px; height: 3px; background: #7c3aed; vertical-align: middle; margin-right: 6px; border-radius: 2px; }
        .legend .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
        .legend .dot-active { background: #7c3aed; }
        .legend .dot-inactive { background: #cbd5e1; }
        .line-label { background: #7c3aed; color: #fff; font-weight: 700; font-size: 13px; border-radius: 12px; padding: 2px 8px; text-align: center; border: 2px solid #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.25); }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>UNINOVIS <span>Collaboration Map</span></h1>
            <p id="summary"></p>
        </div>
        <div class="header-badge">UNINOVIS</div>
    </div>
    <div id="map"></div>
    <script>
        const data = __DATA__;
        const unis = data.universities;
        const connections = data.connections;

        // Summary
        const totalCollabs = data.total_collaborations;
        const pairsWithCollabs = connections.filter(c => c.count > 0).length;
        document.getElementById('summary').textContent =
            totalCollabs + ' collaboration paper(s) across ' + pairsWithCollabs + ' university pair(s)';

        // Map focused on UNINOVIS universities
        const map = L.map('map', {
            maxBounds: L.latLngBounds(L.latLng(35, -6), L.latLng(63, 26)).pad(0.15),
            maxBoundsViscosity: 1.0,
            minZoom: 4,
            maxZoom: 18
        }).fitBounds(L.latLngBounds(L.latLng(35, -6), L.latLng(63, 26)), { padding: [30, 30] });

        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap &copy; CARTO',
            maxZoom: 18
        }).addTo(map);

        // Draw connection lines
        const maxCount = Math.max(...connections.map(c => c.count), 1);

        // Pairs that need a curved line to avoid overlapping nearby connections.
        // Positive offset = curve south/down, negative = curve north/up.
        const curvedPairs = { 'UMA-UT': -3 };

        function buildCurvedPath(ptA, ptB, offsetDeg) {
            const steps = 20;
            const pts = [];
            for (let i = 0; i <= steps; i++) {
                const t = i / steps;
                const lat = ptA.lat + (ptB.lat - ptA.lat) * t;
                const lon = ptA.lon + (ptB.lon - ptA.lon) * t;
                // Parabolic offset, max at midpoint (t=0.5)
                const bend = offsetDeg * 4 * t * (1 - t);
                pts.push([lat + bend, lon]);
            }
            return pts;
        }

        connections.forEach(conn => {
            const fromUni = unis[conn.from];
            const toUni = unis[conn.to];
            if (!fromUni || !toUni || !fromUni.lat || !toUni.lat) return;

            // Check if this pair needs a curved line
            const pairKey = [conn.from, conn.to].sort().join('-');
            const curveOffset = curvedPairs[pairKey] || 0;
            const latlngs = curveOffset
                ? buildCurvedPath(fromUni, toUni, curveOffset)
                : [[fromUni.lat, fromUni.lon], [toUni.lat, toUni.lon]];

            // Line thickness proportional to collaboration count
            const weight = Math.max(1.5, Math.min(5, 1.5 + (conn.count / maxCount) * 3.5));

            const line = L.polyline(latlngs, {
                color: '#7c3aed',
                weight: weight,
                opacity: 0.7,
                dashArray: null
            }).addTo(map);

            // Number label at midpoint
            const midIdx = Math.floor((latlngs.length - 1) / 2);
            const midLat = (latlngs[midIdx][0] + latlngs[midIdx + 1 < latlngs.length ? midIdx + 1 : midIdx][0]) / 2;
            const midLon = (latlngs[midIdx][1] + latlngs[midIdx + 1 < latlngs.length ? midIdx + 1 : midIdx][1]) / 2;
            // Offset midpoint slightly to avoid overlap with line
            const offsetLat = midLat + (fromUni.lon - toUni.lon) * 0.02;
            const offsetLon = midLon - (fromUni.lat - toUni.lat) * 0.02;

            const labelIcon = L.divIcon({
                className: '',
                html: '<div class="line-label">' + conn.count + '</div>',
                iconSize: [32, 24],
                iconAnchor: [16, 12]
            });
            L.marker([offsetLat, offsetLon], { icon: labelIcon, interactive: true }).addTo(map)
                .bindPopup(buildConnectionPopup(conn, fromUni, toUni));

            // Also bind popup to the line itself
            line.bindPopup(buildConnectionPopup(conn, fromUni, toUni));
        });

        function buildConnectionPopup(conn, fromUni, toUni) {
            let papersHtml = '<div class="papers-list">';
            conn.papers.forEach(p => {
                const authors = p.authors ? p.authors.join(', ') : '';
                const doiLink = p.doi ? ' &mdash; <a href="' + p.doi + '" target="_blank">DOI</a>' : '';
                papersHtml += '<div class="paper-item">'
                    + '<div class="paper-title">' + (p.title || 'Untitled') + '</div>'
                    + '<div class="paper-meta">' + authors + (p.year ? ' (' + p.year + ')' : '') + doiLink + '</div>'
                    + '</div>';
            });
            papersHtml += '</div>';

            return '<div class="collab-popup">'
                + '<h3>' + conn.from + ' &harr; ' + conn.to + '</h3>'
                + '<div class="count">' + conn.count + ' shared paper(s)</div>'
                + papersHtml
                + '</div>';
        }

        // University markers
        Object.entries(unis).forEach(([acronym, uni]) => {
            if (!uni.lat || !uni.lon) return;

            const hasCollabs = uni.collab_count > 0;
            const radius = hasCollabs ? 16 : 10;
            const color = hasCollabs ? '#7c3aed' : '#cbd5e1';
            const borderColor = hasCollabs ? '#5b21b6' : '#94a3b8';

            const marker = L.circleMarker([uni.lat, uni.lon], {
                radius: radius,
                fillColor: color,
                color: borderColor,
                weight: 2,
                opacity: 1,
                fillOpacity: 0.85
            }).addTo(map);

            // Acronym label
            const icon = L.divIcon({
                className: '',
                html: '<div style="color:#fff;font-weight:bold;font-size:11px;text-align:center;line-height:' + (radius*2) + 'px;text-shadow:0 1px 2px rgba(0,0,0,0.4);">' + acronym + '</div>',
                iconSize: [radius*2, radius*2],
                iconAnchor: [radius, radius]
            });
            L.marker([uni.lat, uni.lon], { icon: icon, interactive: false }).addTo(map);

            marker.bindPopup(
                '<div class="uni-popup">'
                + '<h3>' + acronym + ' &mdash; ' + uni.name + '</h3>'
                + '<div class="country">' + uni.country + '</div>'
                + '<div class="count">' + uni.collab_count + ' collaboration paper(s)</div>'
                + '</div>'
            );
        });

        // Legend
        const legend = L.control({ position: 'bottomright' });
        legend.onAdd = function() {
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<h4>Collaboration Map</h4>'
                + '<div><span class="line-sample"></span> Collaboration link (thicker = more papers)</div>'
                + '<div><span class="dot dot-active"></span> University with collaborations</div>'
                + '<div><span class="dot dot-inactive"></span> No cross-partner collaborations</div>';
            return div;
        };
        legend.addTo(map);
    </script>
</body>
</html>""".replace("__DATA__", data_json))

    # Generic academic disciplines and noisy OpenAlex artifacts to filter out
    GENERIC_CONCEPTS = {
        "computer science", "artificial intelligence", "psychology", "business",
        "medicine", "sociology", "political science", "engineering", "marketing",
        "mathematics", "philosophy", "economics", "biology", "chemistry",
        "physics", "law", "education", "history", "geography", "linguistics",
        "management", "finance", "statistics", "art",
        # Noisy OpenAlex disambiguation artifacts
        "context (archaeology)", "key (lock)", "set (abstract data type)",
        "identification (biology)", "process (computing)", "generative grammar",
        "pattern recognition (psychology)", "generalizability theory",
        "management science", "epistemology",
    }

    def get_top_topics(self, min_score: float = 0.3, top_n: int = 30) -> list:
        """Aggregate concepts/topics across all university papers.

        Returns a list of (topic_name, count, universities) sorted by frequency.
        Only considers concepts with score >= min_score.
        Filters out overly generic academic disciplines.
        """
        from collections import Counter, defaultdict
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        topic_counts = Counter()
        topic_universities = defaultdict(set)

        for json_path in glob.glob(os.path.join(data_dir, "*_papers.json")):
            acronym = os.path.basename(json_path).replace("_papers.json", "").upper()
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    papers = json.load(f)
            except Exception:
                continue

            for paper in papers:
                for concept in paper.get("concepts", []):
                    if concept.get("score", 0) >= min_score:
                        name = concept["name"]
                        if name.lower() not in self.GENERIC_CONCEPTS:
                            topic_counts[name] += 1
                            topic_universities[name].add(acronym)

        results = []
        for name, count in topic_counts.most_common(top_n):
            results.append({
                "topic": name,
                "paper_count": count,
                "universities": sorted(topic_universities[name]),
            })
        return results

    def _build_topics_summary(self) -> str:
        """Build a summary of top research topics from the paper database."""
        topics = self.get_top_topics(top_n=25)
        if not topics:
            return ""

        lines = ["RESEARCH SUBTOPICS FOUND ACROSS PAPERS (from OpenAlex concept tags, filtered to specific subtopics only):"]
        for t in topics:
            unis = ", ".join(t["universities"])
            lines.append(f"- {t['topic']}: {t['paper_count']} papers (universities: {unis})")
        lines.append("")
        lines.append("IMPORTANT: This is supplementary data for reference. Do NOT present this list as a separate section in your answer. When the user asks about relevant topics, integrate this information naturally with the content retrieved from the documents. Do not duplicate information — if the retrieved documents already discuss topics, prefer that content over this list.")
        return "\n".join(lines)

    def search_papers_by_topic(self, topic: str, min_score: float = 0.3) -> dict:
        """Search all university paper JSON files for papers matching a topic.

        Matching strategy (in order of priority):
        1. Concept tag match: the full topic phrase appears in a concept name
           or the concept name appears in the topic (score >= min_score).
        2. Title/abstract match: the full topic phrase appears in the title or abstract.
        3. Keyword fallback: if the above yield zero results, splits the topic into
           keywords and checks if ALL keywords appear in concepts, title, or abstract.

        Returns a dict: {acronym: {"name": ..., "country": ..., "lat": ..., "lon": ..., "count": N, "papers": [...]}}
        """
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        topic_lower = topic.lower()
        stop_words = {"the", "a", "an", "in", "on", "of", "and", "or", "for", "to", "is", "are", "was", "were", "by", "with", "from", "at", "as"}
        topic_words = [w for w in re.split(r'\W+', topic_lower) if w and w not in stop_words and len(w) > 2]

        def _match_paper_strict(paper):
            """Match by full phrase in concepts, title, or abstract."""
            for concept in paper.get("concepts", []):
                concept_name = concept.get("name", "").lower()
                if concept.get("score", 0) < min_score:
                    continue
                if topic_lower in concept_name or concept_name in topic_lower:
                    return True
            title = paper.get("title", "").lower()
            abstract = (paper.get("abstract") or "").lower()
            text = title + " " + abstract
            if topic_lower in text:
                return True
            return False

        def _match_paper_keywords(paper):
            """Fallback: match if ALL keywords appear somewhere in the paper."""
            for concept in paper.get("concepts", []):
                concept_name = concept.get("name", "").lower()
                if concept.get("score", 0) < min_score:
                    continue
                if all(w in concept_name for w in topic_words):
                    return True
            title = paper.get("title", "").lower()
            abstract = (paper.get("abstract") or "").lower()
            text = title + " " + abstract
            if all(w in text for w in topic_words):
                return True
            return False

        # Load all papers
        all_uni_papers = {}
        for json_path in glob.glob(os.path.join(data_dir, "*_papers.json")):
            acronym = os.path.basename(json_path).replace("_papers.json", "").upper()
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    all_uni_papers[acronym] = json.load(f)
            except Exception:
                continue

        # Combine strict and keyword matching (deduplicated by paper id)
        results = {}
        for acronym, papers in all_uni_papers.items():
            seen_ids = set()
            matching = []
            # Strict matches first (higher priority)
            for p in papers:
                if _match_paper_strict(p):
                    pid = p.get("id", id(p))
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        matching.append(p)
            # Then keyword matches
            if topic_words:
                for p in papers:
                    pid = p.get("id", id(p))
                    if pid not in seen_ids and _match_paper_keywords(p):
                        seen_ids.add(pid)
                        matching.append(p)
            results[acronym] = matching

        # Build output
        output = {}
        for acronym, matching_papers in results.items():
            formatted_papers = []
            for paper in matching_papers:
                formatted_papers.append({
                    "id": paper.get("id", ""),
                    "title": paper.get("title", ""),
                    "authors": [a.get("name", "") for a in paper.get("authors", [])[:3]],
                    "year": paper.get("publication_year"),
                    "doi": paper.get("doi", ""),
                    "cited_by_count": paper.get("cited_by_count", 0),
                })

            coords = self.UNIVERSITY_COORDS.get(acronym, {})
            output[acronym] = {
                "name": coords.get("name", acronym),
                "country": coords.get("country", ""),
                "lat": coords.get("lat", 0),
                "lon": coords.get("lon", 0),
                "count": len(formatted_papers),
                "papers": formatted_papers,
            }

        return output

    @staticmethod
    def build_topic_map_html(results_json: str, topic_escaped: str) -> str:
        """Build the HTML for the interactive topic map (light theme, Europe-focused)."""
        # Use replace instead of f-string to avoid brace escaping issues with JS/CSS
        return ("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNINOVIS Topic Map: __TOPIC__</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f8fafc; color: #1e293b; }
        .header { background: #1e293b; padding: 16px 24px; border-bottom: 3px solid #2563eb; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 1.3em; color: #ffffff; font-weight: 600; }
        .header h1 span { color: #60a5fa; }
        .header p { font-size: 0.9em; color: #94a3b8; margin-top: 2px; }
        .header-left { flex: 1; }
        .header-badge { background: #2563eb; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 0.8em; font-weight: 600; letter-spacing: 0.5px; }
        #map { height: calc(100vh - 72px); width: 100%; }
        .uni-popup { min-width: 300px; }
        .uni-popup h3 { color: #1e293b; margin-bottom: 4px; font-size: 1.1em; font-weight: 600; }
        .uni-popup .country { color: #64748b; font-size: 0.85em; margin-bottom: 10px; }
        .uni-popup .count { font-size: 1.3em; font-weight: 700; color: #2563eb; margin-bottom: 10px; padding: 6px 0; border-bottom: 2px solid #e2e8f0; }
        .uni-popup .papers-list { max-height: 220px; overflow-y: auto; font-size: 0.82em; }
        .uni-popup .paper-item { padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
        .uni-popup .paper-item:last-child { border-bottom: none; }
        .uni-popup .paper-title { font-weight: 500; color: #1e293b; }
        .uni-popup .paper-meta { color: #64748b; font-size: 0.9em; margin-top: 2px; }
        .uni-popup a { color: #2563eb; text-decoration: none; }
        .uni-popup a:hover { text-decoration: underline; }
        .legend { background: #ffffff; padding: 14px 18px; border-radius: 10px; color: #1e293b; font-size: 0.85em; line-height: 1.7; box-shadow: 0 2px 8px rgba(0,0,0,0.12); border: 1px solid #e2e8f0; }
        .legend h4 { margin-bottom: 6px; color: #1e293b; font-weight: 600; font-size: 0.95em; }
        .legend .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
        .legend .dot-has { background: #2563eb; }
        .legend .dot-none { background: #cbd5e1; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>UNINOVIS Research Map: <span>"__TOPIC__"</span></h1>
            <p id="summary"></p>
        </div>
        <div class="header-badge">UNINOVIS</div>
    </div>
    <div id="map"></div>
    <script>
        const data = __DATA__;
        const topic = "__TOPIC__";

        // Summary
        let totalPapers = 0;
        let uniWithPapers = 0;
        Object.values(data).forEach(u => {
            totalPapers += u.count;
            if (u.count > 0) uniWithPapers++;
        });
        document.getElementById('summary').textContent =
            totalPapers + ' paper(s) found across ' + uniWithPapers + ' of ' + Object.keys(data).length + ' UNINOVIS universities';

        // Map focused tightly on UNINOVIS universities
        const uniBounds = L.latLngBounds(
            L.latLng(35, -6),    // Southwest: just below Málaga
            L.latLng(63, 26)     // Northeast: just above Tampere
        );
        const map = L.map('map', {
            maxBounds: uniBounds.pad(0.15),
            maxBoundsViscosity: 1.0,
            minZoom: 4,
            maxZoom: 18
        }).fitBounds(uniBounds, { padding: [30, 30] });

        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
            maxZoom: 18
        }).addTo(map);

        // Markers
        const maxCount = Math.max(...Object.values(data).map(u => u.count), 1);

        Object.entries(data).forEach(([acronym, uni]) => {
            if (!uni.lat || !uni.lon) return;

            const radius = uni.count > 0 ? Math.max(18, Math.min(42, 18 + (uni.count / maxCount) * 24)) : 12;
            const color = uni.count > 0 ? '#2563eb' : '#cbd5e1';
            const borderColor = uni.count > 0 ? '#1e40af' : '#94a3b8';
            const fillOpacity = uni.count > 0 ? 0.8 : 0.5;

            const marker = L.circleMarker([uni.lat, uni.lon], {
                radius: radius,
                fillColor: color,
                color: borderColor,
                weight: 2,
                opacity: 1,
                fillOpacity: fillOpacity
            }).addTo(map);

            // Number label
            const icon = L.divIcon({
                className: 'count-label',
                html: '<div style="color:#fff;font-weight:bold;font-size:' + (radius > 22 ? '14' : '12') + 'px;text-align:center;line-height:' + (radius*2) + 'px;text-shadow:0 1px 2px rgba(0,0,0,0.3);">' + uni.count + '</div>',
                iconSize: [radius*2, radius*2],
                iconAnchor: [radius, radius]
            });
            L.marker([uni.lat, uni.lon], {icon: icon, interactive: false}).addTo(map);

            // Popup
            let papersHtml = '';
            if (uni.papers && uni.papers.length > 0) {
                papersHtml = '<div class="papers-list">';
                uni.papers.forEach(p => {
                    const authors = p.authors ? p.authors.join(', ') : '';
                    const doiLink = p.doi ? '<a href="' + p.doi + '" target="_blank">DOI</a>' : '';
                    papersHtml += '<div class="paper-item">'
                        + '<div class="paper-title">' + (p.title || 'Untitled') + '</div>'
                        + '<div class="paper-meta">' + authors + (p.year ? ' (' + p.year + ')' : '')
                        + (p.cited_by_count ? ' &mdash; Cited: ' + p.cited_by_count : '')
                        + (doiLink ? ' &mdash; ' + doiLink : '')
                        + '</div></div>';
                });
                papersHtml += '</div>';
            } else {
                papersHtml = '<p style="color:#94a3b8;font-style:italic;">No papers found for this topic.</p>';
            }

            marker.bindPopup(
                '<div class="uni-popup">'
                + '<h3>' + acronym + ' &mdash; ' + uni.name + '</h3>'
                + '<div class="country">' + uni.country + '</div>'
                + '<div class="count">' + uni.count + ' paper(s) on "' + topic + '"</div>'
                + papersHtml
                + '</div>',
                { maxWidth: 380 }
            );
        });

        // Legend
        const legend = L.control({position: 'bottomright'});
        legend.onAdd = function() {
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<h4>UNINOVIS Topic Map</h4>'
                + '<div><span class="dot dot-has"></span> Has papers (size = count)</div>'
                + '<div><span class="dot dot-none"></span> No papers found</div>';
            return div;
        };
        legend.addTo(map);
    </script>
</body>
</html>"""
            .replace("__DATA__", results_json)
            .replace("__TOPIC__", topic_escaped)
        )

    def get_metadata_summary(self) -> list:
        """Returns metadata summary for all indexed documents."""
        return list(self._documents_metadata.values())

    def _build_metadata_context(self) -> str:
        """Builds a metadata summary string to include in the system prompt."""
        lines = []

        # Include university-level paper counts summary
        if self._university_paper_counts:
            lines.append("PUBLICATION COUNTS PER UNIVERSITY (from OpenAlex database):")
            total = 0
            for acronym, info in self._university_paper_counts.items():
                count = info["count"]
                total += count
                lines.append(f"- {acronym} ({info['name']}): {count} papers")
            lines.append(f"- TOTAL: {total} papers across all UNINOVIS universities")
            lines.append("")

        # Include top research topics aggregated from paper concepts
        topics_summary = self._build_topics_summary()
        if topics_summary:
            lines.append(topics_summary)
            lines.append("")

        # Include cross-university collaboration papers
        cross_papers = self.get_cross_university_papers()
        if cross_papers:
            lines.append("CROSS-UNIVERSITY COLLABORATIONS (papers with authors from 2+ UNINOVIS universities):")
            lines.append("A paper is a collaboration if its author affiliations include 2 or more UNINOVIS universities.")
            for p in cross_papers:
                unis = " + ".join(p["universities"])
                authors = ", ".join(p["authors"][:5])
                if len(p["authors"]) > 5:
                    authors += f" et al. ({len(p['authors'])} authors)"
                year_str = f" ({p['year']})" if p.get("year") else ""
                lines.append(f"- [{unis}] \"{p['title']}\"{year_str} — Authors: {authors}")
            lines.append("")
            lines.append("IMPORTANT: When the user asks about collaborations filtered by year, trust the collaboration data above — filter it by the year shown in parentheses. Do NOT second-guess whether a paper is a real collaboration; if it appears in this list, it IS a confirmed collaboration.")
            lines.append("")

        if not self._documents_metadata:
            return "\n".join(lines) if lines else ""

        lines.append("Available documents and their metadata:")
        for filename, meta in self._documents_metadata.items():
            parts = [f"- {filename}"]
            if meta.get("title") and meta["title"] != os.path.splitext(filename)[0]:
                parts.append(f"Title: {meta['title']}")
            if meta.get("author"):
                parts.append(f"Author: {meta['author']}")
            if meta.get("date"):
                parts.append(f"Date: {meta['date']}")
            if meta.get("university"):
                uni_str = meta['university']
                if meta.get("university_acronym"):
                    uni_str += f" ({meta['university_acronym']})"
                parts.append(f"University: {uni_str}")
            if meta.get("page_count"):
                parts.append(f"Pages: {meta['page_count']}")
            if meta.get("file_type"):
                parts.append(f"Type: {meta['file_type']}")
            lines.append(" | ".join(parts))

        return "\n".join(lines)

    def _verify_grounding(self, response: str, user_question: str, context: str) -> dict:
        """Verifica si la respuesta está basada SOLO en el contexto recuperado."""
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

    def _build_topic_context(self, user_message: str) -> str:
        """Detect topic keywords in the user message and return structured paper data
        from search_papers_by_topic so that text responses and figures use the same source."""
        msg_lower = user_message.lower()

        # Only trigger for queries that seem to ask about papers/researchers on a topic
        topic_triggers = ["papers on", "papers about", "publications on", "publications about",
                          "researchers on", "researchers in", "research on", "research about",
                          "working on", "interested in", "figure of", "figure about",
                          "list of papers", "list of researchers", "list of publications"]
        triggered = any(t in msg_lower for t in topic_triggers)
        if not triggered:
            return ""

        # Extract the topic: take text after the trigger phrase
        topic = None
        for t in sorted(topic_triggers, key=len, reverse=True):
            idx = msg_lower.find(t)
            if idx >= 0:
                topic = user_message[idx + len(t):].strip().strip('"\'.,!?')
                break
        if not topic or len(topic) < 2:
            return ""

        # Remove trailing university references from topic
        universities = self._config.get("universities", {})
        for acronym in universities:
            topic = re.sub(r'\b' + re.escape(acronym) + r'\b.*$', '', topic, flags=re.IGNORECASE).strip()
        if not topic or len(topic) < 2:
            return ""

        results = self.search_papers_by_topic(topic)
        total = sum(uni["count"] for uni in results.values())
        if total == 0:
            return ""

        # Build set of confirmed UNINOVIS researchers per university
        uninovis_researchers = {}
        for acronym, researchers in self._researchers_by_uni.items():
            uninovis_researchers[acronym] = {r["name"] for r in researchers}

        lines = [f"TOPIC SEARCH RESULTS for \"{topic}\" ({total} papers total):"]
        lines.append("Use these exact numbers and researcher-university assignments when answering. These are authoritative — do NOT reassign researchers to different universities.")
        lines.append("Only researchers confirmed as UNINOVIS members are listed. Other co-authors are from external institutions.")
        for acronym, uni in sorted(results.items(), key=lambda x: x[1]["count"], reverse=True):
            if uni["count"] == 0:
                continue
            # Filter authors to only confirmed UNINOVIS members
            uni_members = uninovis_researchers.get(acronym, set())
            paper_authors = set()
            paper_details = []
            for p in uni["papers"]:
                for a in p["authors"]:
                    if a in uni_members:
                        paper_authors.add(a)
                authors_str = ", ".join(p["authors"][:3])
                if len(p["authors"]) > 3:
                    authors_str += " et al."
                year_str = f" ({p['year']})" if p.get("year") else ""
                paper_details.append(f"  - \"{p['title']}\"{year_str} by {authors_str}")
            lines.append(f"\n{acronym} ({uni['name']}): {uni['count']} papers, {len(paper_authors)} UNINOVIS researchers")
            if paper_authors:
                lines.append(f"  UNINOVIS researchers: {', '.join(sorted(paper_authors))}")
            lines.extend(paper_details)

        return "\n".join(lines)

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
            return f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"

        # Add topic-specific structured data (same source as figures)
        topic_ctx = self._build_topic_context(user_message)

        # When topic context is available, use it as the sole data source
        # to ensure consistency with figures. Otherwise, use RAG.
        if topic_ctx:
            context = ""
        else:
            uni_filter = self._detect_university_filter(user_message)
            context = self._retrieve_context(user_message, metadata_filter=uni_filter)

        system_with_context = self.system_prompt
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system_with_context += f"\n\n{metadata_ctx}"
        if topic_ctx:
            system_with_context += f"\n\n{topic_ctx}"
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages,
            max_tokens=8192,
        )

        response_content = response.choices[0].message.content

        if should_verify and context:
            verification = self._verify_grounding(response_content, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                response_content = self._get_fallback_response(user_message)

        self._query_history.append({
            'question': user_message,
            'response_length': len(response_content)
        })

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, verify: bool = None):
        """Envía un mensaje con contexto RAG+Metadata y obtiene respuesta en streaming."""
        should_verify = verify if verify is not None else self.verify_grounding

        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"
            return

        # Add topic-specific structured data (same source as figures)
        topic_ctx = self._build_topic_context(user_message)

        # When topic context is available, use it as the sole data source
        # to ensure consistency with figures. Otherwise, use RAG.
        if topic_ctx:
            context = ""
        else:
            uni_filter = self._detect_university_filter(user_message)
            context = self._retrieve_context(user_message, metadata_filter=uni_filter)

        system_with_context = self.system_prompt
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system_with_context += f"\n\n{metadata_ctx}"
        if topic_ctx:
            system_with_context += f"\n\n{topic_ctx}"
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        if should_verify and context:
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages,
                max_tokens=8192,
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content

            verification = self._verify_grounding(full_response, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                full_response = self._get_fallback_response(user_message)

            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })
            yield full_response
        else:
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages,
                max_tokens=8192,
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content
                    yield chunk.data.choices[0].delta.content

            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {
                'question': entry['question'],
                'num_results': 1
            }
            for entry in self._query_history
        ]

    def reindex(self):
        """Reindexa todos los documentos con metadatos."""
        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._documents_metadata = {}
        self._index_documents()
        return self.collection.count()
