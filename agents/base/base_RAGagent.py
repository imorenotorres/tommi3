"""
BaseRAGAgent - Base class shared by ALL RAG-based TOMMI agents.

Provides: config loading, system prompt assembly, ChromaDB lazy init,
document indexing/sync, context retrieval, reliability badge system,
audit logging, and reindex support.

Subclasses must NOT override __init__; use _post_init() for extra setup.
chat() and chat_stream() are provided by mixins (not included here).
"""

import os
import sys
import json
import re
import warnings
import logging

logging.getLogger("pypdf").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*position_ids.*")

# Add web/ to path for llm_client and error_codes
# Support both normal layout and Docker layout
_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base_dir, "..", "..", "web"))
sys.path.insert(0, os.path.join(_base_dir, "web"))
from llm_client import LLMClient
from error_codes import format_error, DATA_CHROMADB_PYTHON_INCOMPATIBLE, DATA_CHROMADB_ERROR

from pypdf import PdfReader


class BaseRAGAgent:
    """Base class for all TOMMI RAG agents."""

    def __init__(self, progress_callback=None):
        self._progress_callback = progress_callback
        # Resolve agent directory FIRST — needed by _load_config and everything else
        self.__agent_dir = self._resolve_agent_dir()
        self.client = LLMClient()
        self.model = self._get_model()
        self._is_local_llm = os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm")
        self.model_display_name = self._resolve_model_display_name()
        self._config = self._load_config()
        self._prompt_level = self._config.get("prompt_level", "stringent")
        self.system_prompt = self._build_system_prompt()
        # Reliability badge thresholds from config
        self._reliability_green_max_llm = self._config.get("reliability_green_max_llm", 20)
        self._reliability_red_min_llm = self._config.get("reliability_red_min_llm", 50)
        # Reliability cues & content transparency (two independent dimensions)
        #   reliability_cues: "shown" (banners visible) or "hidden" — all agents
        #   transparency_level: "crystal_box" (SQL/sources visible) or "black_box" — Text2SQL only
        self._audit_enabled = self._config.get("audit_log_enabled", False)
        self._audit_path = os.path.join(self._agent_dir, "data", "audit_log.jsonl")

        # Reliability cues (procedural banners: green/yellow/red)
        cues = self._config.get("reliability_cues", "shown")
        self._show_procedural_banners = (cues == "shown")
        # For internal compatibility: set _transparency to map cues to the old values
        self._transparency = "shown" if cues == "shown" else "hidden"

        # Content transparency (SQL queries, source disclosure) — Text2SQL agents
        self._transparency_level = self._config.get("transparency_level", "black_box")
        self._show_content_transparency = (self._transparency_level == "crystal_box")

        # Claim-level analysis is not used by any current agent type
        self._skip_claim_classification = True

        # Humility (system prompt): pre-generation hedging instructions
        self._humility_prompt = self._config.get("humility_prompt", "off")

        # Humility (post-processing): "off", "moderate", "strict"
        from .humility import HumilityRewriter
        self._humility = HumilityRewriter(self._config.get("humility_postprocessing", "off"))

        # Query history for the sidebar
        self._query_history = []

        # RAG Chunking Configuration
        self._load_rag_config()

        # ChromaDB lazy initialization
        self.chroma_client = None
        self.collection = None
        self.embedding_fn = None
        self._chromadb_error = None
        self._chromadb_initialized = False

        # Hook for subclasses / mixins
        self._post_init()

    # ------------------------------------------------------------------
    # _agent_dir: resolves to the concrete subclass directory
    # ------------------------------------------------------------------

    def _resolve_agent_dir(self):
        """Find the directory of the concrete agent subclass.

        Uses the _AGENT_FILE class attribute set by each thin wrapper,
        or falls back to inspecting the class source file.
        """
        # Preferred: explicit _AGENT_FILE set by subclass
        agent_file = getattr(self.__class__, '_AGENT_FILE', None)
        if agent_file:
            return os.path.dirname(os.path.abspath(agent_file))

        # Fallback: walk MRO for a module outside base/
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for cls in type(self).__mro__:
            mod = sys.modules.get(cls.__module__)
            if mod and hasattr(mod, '__file__') and mod.__file__:
                d = os.path.dirname(os.path.abspath(mod.__file__))
                if d != base_dir:
                    return d
        return base_dir

    @property
    def _agent_dir(self):
        """Return the directory of the concrete agent subclass."""
        return self.__agent_dir

    # ------------------------------------------------------------------
    # Model / config loading
    # ------------------------------------------------------------------

    def _get_model(self) -> str:
        """Obtiene el modelo segun el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "")
        return os.getenv("MISTRAL_MODEL", "")

    def _resolve_model_display_name(self) -> str:
        """Build a descriptive model name (e.g., 'mistral 7B Q4_0').

        For Ollama models, queries the local API for parameter size
        and quantization level.  For cloud models, returns the model id.
        """
        if not self._is_local_llm or not self.model:
            return self.model
        try:
            import httpx
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            verify = not base_url.startswith("https")
            resp = httpx.post(f"{base_url}/api/show", json={"name": self.model}, timeout=5.0, verify=verify)
            if resp.status_code == 200:
                details = resp.json().get("details", {})
                parts = [self.model]
                if details.get("parameter_size"):
                    parts.append(details["parameter_size"])
                if details.get("quantization_level"):
                    parts.append(details["quantization_level"])
                return " ".join(parts)
        except Exception:
            pass
        return self.model

    def _load_config(self) -> dict:
        """Load agent configuration from config.json."""
        config_path = os.path.join(self._agent_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                print(f"Agent config loaded: {config.get('agent_name', 'Unknown')}")
                return config
            except Exception as e:
                print(f"Warning: Could not load config.json: {e}")
        return {}

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

    # ------------------------------------------------------------------
    # System prompt assembly
    # ------------------------------------------------------------------

    def _load_prompts(self) -> dict:
        """Load prompt sections from prompts.json in the agent directory."""
        prompts_path = os.path.join(self._agent_dir, "prompts.json")
        if os.path.exists(prompts_path):
            try:
                with open(prompts_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load prompts.json: {e}")
        return {}

    def _prompt_template_vars(self) -> dict:
        """Build the template variables for prompt rendering from config."""
        cfg = self._config
        universities = cfg.get("universities", {})
        alliance = cfg.get("alliance", {})
        alliance_name = alliance.get("name", "")

        uni_lines = []
        for acronym, info in universities.items():
            uni_lines.append(f"- {acronym}: {info['name']} ({info['country']})")

        return {
            "agent_name": cfg.get("agent_name", "TOMMI Agent"),
            "description": cfg.get("description", "assistant with access to a document knowledge base"),
            "research_topic": cfg.get("research_topic", "research papers"),
            "alliance_name": alliance_name,
            "alliance_name_upper": alliance_name.upper(),
            "alliance_desc": alliance.get("description", ""),
            "num_universities": str(len(universities)),
            "uni_list": "\n".join(uni_lines),
            "acronym_list": ", ".join(universities.keys()),
            "agent_id": cfg.get("agent_id", "agent"),
            "gap_examples": cfg.get("gap_analysis_examples", "emerging subtopics not yet covered in the database"),
        }

    def _render_prompt_section(self, section_key: str) -> str:
        """Load a prompt section from prompts.json and render placeholders."""
        prompts = self._load_prompts()
        template = prompts.get(section_key, "")
        if not template:
            return ""
        try:
            return template.format(**self._prompt_template_vars())
        except KeyError as e:
            print(f"Warning: Missing prompt placeholder {e} in section '{section_key}'")
            return template

    def _prompt_section_identity(self) -> str:
        """Section 1: Identity and style — loaded from prompts.json."""
        return self._render_prompt_section("identity")

    def _prompt_section_rules(self) -> str:
        """Section 2: Standard rules — loaded from prompts.json."""
        return self._render_prompt_section("rules")

    def _prompt_section_strict(self) -> str:
        """Section 3: Strict restrictions — loaded from prompts.json."""
        return self._render_prompt_section("strict")

    def _build_system_prompt(self) -> str:
        """Build system prompt respecting prompt_level."""
        level = getattr(self, '_prompt_level', 'stringent')
        parts = [self._prompt_section_identity()]
        if level in ('tolerant', 'stringent'):
            rules = self._prompt_section_rules()
            if rules:
                parts.append(rules)
        if level == 'stringent':
            strict = self._prompt_section_strict()
            if strict:
                parts.append(strict)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Reliability cues & humility: visual badges and prompt-level hedging
    # ------------------------------------------------------------------

    def _should_show_visual_badge(self) -> bool:
        """Whether to render the visual reliability badge (tied to reliability_cues)."""
        return self._show_procedural_banners

    def _should_use_text_style(self) -> bool:
        """Whether to inject hedging instructions based on context quality (humility_prompt)."""
        return self._humility_prompt == "on"

    def _estimate_context_quality(self, context: str, metadata_ctx: str = "") -> str:
        """Estimate context quality BEFORE LLM generation.

        Returns "high", "moderate", or "low" based on the amount and
        presence of retrieved context.
        """
        has_context = bool(context and context.strip())
        has_metadata = bool(metadata_ctx and metadata_ctx.strip())

        if has_metadata and has_context:
            return "high"
        if has_metadata or has_context:
            # Rough heuristic: short context is weaker
            text = context or metadata_ctx
            if len(text) > 500:
                return "high"
            return "moderate"
        return "low"

    def _get_style_instruction(self, quality: str) -> str:
        """Return a style instruction to append to the system prompt
        based on the pre-generation context quality estimate."""
        if quality == "conceptual":
            return (
                "\n\nSTYLE INSTRUCTION (MANDATORY): You are answering a conceptual question. "
                "Your response is based primarily on your general knowledge, NOT on verified data "
                "from the knowledge base. You MUST follow these rules strictly:\n"
                "- FORMAT (MANDATORY — VIOLATIONS WILL BE FLAGGED): "
                "Write EXACTLY 2-3 short paragraphs of flowing prose. "
                "NEVER use numbered lists, bullet points, headings (###), tables, or structured sections. "
                "NEVER enumerate challenges, principles, or frameworks as a list. "
                "Instead, weave 3-4 key points into natural prose paragraphs. "
                "If you produce more than 4 paragraphs or any numbered/bulleted list, the response WILL be rejected.\n"
                "- NEVER present definitions or explanations as established facts. "
                "Use framing such as 'Responsible AI is generally understood as', "
                "'this concept is often described as', 'according to common frameworks'.\n"
                "- NEVER use authoritative language such as 'X is a core requirement', "
                "'X is essential', 'X is a foundational principle', 'X are explicit requirements'. "
                "Instead use 'X is often considered', 'X is commonly cited as', "
                "'many authors describe X as'.\n"
                "- BANNED PHRASES: 'is a core requirement', 'is essential', 'is a foundational principle', "
                "'are explicit requirements', 'is necessary for', 'is critical for', "
                "'widely discussed', 'widely recognized'. "
                "These imply authority beyond what your knowledge supports.\n"
                "- Acknowledge that definitions and frameworks vary across authors, institutions, "
                "and contexts.\n"
                "- GROUND YOUR RESPONSE in the database: after the conceptual overview, briefly note "
                "which related topics DO appear in the indexed database and which do not. "
                "This helps the user connect the concept to available UNINOVIS research.\n"
                "- If the glossary provides a definition, you may reference it, but note that "
                "the broader explanation is your own interpretation.\n"
                "- End with a note that this explanation reflects general AI knowledge and "
                "the user should consult authoritative sources for formal definitions."
            )
        elif quality == "gap_analysis":
            return (
                "\n\nSTYLE INSTRUCTION (MANDATORY — VIOLATIONS WILL BE FLAGGED): "
                "You are identifying potential research gaps — reasoning about what is ABSENT "
                "from the database. This is inherently speculative. "
                "You MUST follow these rules strictly:\n"
                "- The words 'studied' and 'study' are BANNED in this response. "
                "NEVER write 'has not been studied', 'have not been studied', 'not yet studied', "
                "'understudied', or ANY phrase containing the word 'studied'. "
                "Instead use: 'does not appear in the indexed database', 'was not found among the indexed records', "
                "'no matching entries were identified', or 'not represented in the current index'.\n"
                "- BANNED WORDS AND PHRASES (do NOT use any of these): "
                "'well-known', 'well known', 'widely recognized', 'widely known', "
                "'it is established', 'clearly', 'certainly', 'obviously', 'undoubtedly', "
                "'important', 'fundamental', 'key', 'essential', 'critical', 'major'. "
                "These words imply authority you do not have. You only know what is or is not "
                "in the database — you cannot judge what is important or well-known.\n"
                "- ALWAYS caveat that the database may be incomplete, topics may exist under different names, "
                "or relevant work may not have been indexed.\n"
                "- Use hedging language throughout: 'it appears that', 'based on the available records', "
                "'this could suggest', 'it is possible that', 'some authors have discussed'.\n"
                "- When listing potential gaps, frame them as possibilities, not facts: "
                "'topics such as X, which are sometimes discussed in the literature, do not appear "
                "in the current index' rather than 'X has not been studied'.\n"
                "- End with a reminder that these gaps reflect the database contents, not necessarily "
                "the actual research activity of the alliance."
            )
        elif quality == "high":
            if self._show_procedural_banners or self._show_content_transparency:
                return (
                    "\n\nSTYLE INSTRUCTION (MANDATORY): The user can see the raw data directly. "
                    "Your role is to offer a possible interpretation, NOT to state conclusions as fact. "
                    "You MUST follow these rules:\n"
                    "- Frame your commentary as ONE possible reading of the data: "
                    "'the data suggests', 'this may indicate', 'one possible interpretation is'.\n"
                    "- NEVER use authoritative language such as 'this shows', 'this confirms', "
                    "'it is clear that', 'the evidence demonstrates'. The user can judge for themselves.\n"
                    "- Acknowledge alternative explanations for any pattern you identify "
                    "(e.g., 'though this could also reflect differences in indexing rather than actual research volume').\n"
                    "- When commenting on distributions or patterns, note that the database may not "
                    "capture all relevant work and that apparent gaps may be artifacts.\n"
                    "- Position yourself as a helper offering perspective, not as an authority delivering findings."
                )
            return (
                "\n\nSTYLE INSTRUCTION: You have strong evidence from the knowledge base. "
                "Present the information clearly, but use measured language. "
                "Prefer 'the data suggests' and 'based on the available records' over "
                "definitive claims. Cite source documents when possible."
            )
        elif quality == "moderate":
            return (
                "\n\nSTYLE INSTRUCTION: The available evidence is limited. "
                "Use cautious language (e.g., 'based on the available data', "
                "'the documents suggest'). Note which parts of your answer "
                "you are less certain about."
            )
        else:
            return (
                "\n\nSTYLE INSTRUCTION: You have no relevant data from the knowledge base "
                "for this query. State clearly that your answer is based on general "
                "knowledge and may not be accurate. Recommend the user verify "
                "the information from an authoritative source."
            )

    # ------------------------------------------------------------------
    # Post-processing: sanitize authoritative language in LLM output
    # ------------------------------------------------------------------

    _AUTHORITY_REPLACEMENTS = [
        # "has/have not been studied" in any context
        ("has not been studied", "does not appear in the indexed database"),
        ("have not been studied", "do not appear in the indexed database"),
        ("has not yet been studied", "does not yet appear in the indexed database"),
        ("not yet been studied", "not yet represented in the indexed database"),
        ("understudied", "underrepresented in the indexed database"),
        # Common authoritative phrases
        ("well-known", "commonly discussed"),
        ("well known", "commonly discussed"),
        ("it is clear that", "the data suggests that"),
        ("it is clear", "it appears"),
        ("clearly ", "notably "),
        ("widely recognized", "commonly discussed"),
        ("widely known", "commonly discussed"),
    ]

    def _sanitize_authority(self, text: str) -> str:
        """Post-process LLM output to replace authoritative phrases with
        humble alternatives.  Applied unconditionally as a safety net — these
        phrases are banned in prompts across all transparency conditions."""
        for old, new in self._AUTHORITY_REPLACEMENTS:
            # Case-insensitive replacement preserving first-char case
            pattern = re.compile(re.escape(old), re.IGNORECASE)
            def _repl(m, new=new):
                if m.group(0)[0].isupper():
                    return new[0].upper() + new[1:]
                return new
            text = pattern.sub(_repl, text)
        # Fix common LLM misspelling of alliance name
        text = text.replace("UNINOVOS", "UNINOVIS").replace("Uninovos", "Uninovis")
        return text

    # ------------------------------------------------------------------
    # Post-init hook
    # ------------------------------------------------------------------

    def _post_init(self):
        """Hook called at the end of __init__. Override in mixins/subclasses."""
        pass

    # ------------------------------------------------------------------
    # ChromaDB lazy initialization
    # ------------------------------------------------------------------

    def _init_chromadb(self):
        """Inicializa ChromaDB de forma diferida (lazy initialization)."""
        if self._chromadb_initialized:
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            db_path = os.path.join(self._agent_dir, "data", "chroma_db")
            self.chroma_client = chromadb.PersistentClient(path=db_path)

            # Funcion de embeddings (usa sentence-transformers por defecto)
            # La primera vez descarga el modelo (~90MB), puede tardar
            print("Preparing RAG database...")
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )

            # Obtener o crear coleccion
            self.collection = self.chroma_client.get_or_create_collection(
                name="documents",
                embedding_function=self.embedding_fn
            )

            # Indexar documentos nuevos automaticamente
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

    # ------------------------------------------------------------------
    # Document extraction and indexing
    # ------------------------------------------------------------------

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

        # Obtener todos los metadatos para extraer fuentes unicas
        all_data = self.collection.get(include=["metadatas"])
        sources = set()
        for meta in all_data.get("metadatas", []):
            if meta and "source" in meta:
                sources.add(meta["source"])
        return sources

    def _get_all_docs_dirs(self) -> list:
        """Return list of document directories to index.
        Always includes data/docs/, plus any extra_docs_dirs from config."""
        dirs = [os.path.join(self._agent_dir, "data", "docs")]
        for extra in self._config.get("extra_docs_dirs", []):
            dirs.append(os.path.join(self._agent_dir, "data", extra))
        return dirs

    def _get_docs_files(self) -> set:
        """Obtiene el conjunto de archivos en all document directories."""
        files = set()
        for docs_path in self._get_all_docs_dirs():
            if not os.path.exists(docs_path):
                continue
            for filename in os.listdir(docs_path):
                filepath = os.path.join(docs_path, filename)
                if os.path.isfile(filepath) and filename.endswith(('.txt', '.md', '.pdf')):
                    files.add(filename)
        return files

    def _sync_documents(self):
        """Sincroniza documentos: indexa nuevos y elimina huerfanos."""
        indexed = self._get_indexed_sources()
        on_disk = self._get_docs_files()

        # Documentos nuevos (en disco pero no indexados)
        new_docs = on_disk - indexed
        # Documentos eliminados (indexados pero ya no en disco)
        removed_docs = indexed - on_disk

        if not new_docs and not removed_docs:
            print(f"Documents in sync ({len(indexed)} indexed)")
            self._newly_indexed_chunks = 0
            return

        # Eliminar documentos huerfanos de ChromaDB
        if removed_docs:
            print(f"Removing {len(removed_docs)} deleted documents from index...")
            for source in removed_docs:
                # Obtener IDs de chunks de este documento
                results = self.collection.get(where={"source": source})
                if results["ids"]:
                    self.collection.delete(ids=results["ids"])
            print(f"Removed: {', '.join(removed_docs)}")

        # Indexar documentos nuevos
        chunks_before = self.collection.count()
        if new_docs:
            print(f"Indexing {len(new_docs)} new documents...")
            self._index_documents(only_files=new_docs)
            print(f"Added: {', '.join(new_docs)}")
        self._newly_indexed_chunks = self.collection.count() - chunks_before

    def _index_documents(self, only_files: set = None):
        """Indexa los documentos del directorio data/docs/

        Args:
            only_files: Si se especifica, solo indexa estos archivos.
                       Si es None, indexa todos los archivos.
        """
        docs_path = os.path.join(self._agent_dir, "data", "docs")
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
            # Si only_files esta especificado, solo procesar esos archivos
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

    # ------------------------------------------------------------------
    # Context retrieval
    # ------------------------------------------------------------------

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

    def _linkify_pdf_sources(self, text: str) -> str:
        """Post-process LLM response to convert PDF filename mentions into
        clickable download links.

        Detects patterns like 'source: filename.pdf' or 'filename.pdf, pp. X'
        and converts the filename into a Markdown link to the PDF endpoint.
        Only links filenames that actually exist in data/docs/.
        """
        agent_id = self._config.get("agent_id", "")
        if not agent_id:
            return text

        docs_path = os.path.join(self._agent_dir, "data", "docs")
        if not os.path.exists(docs_path):
            return text

        # Build set of actual PDF filenames
        pdf_files = {f for f in os.listdir(docs_path) if f.endswith('.pdf')}
        if not pdf_files:
            return text

        # Replace each mention of a known PDF filename with a clickable link
        # Skip if already inside a markdown link
        for filename in pdf_files:
            if filename not in text:
                continue
            # Skip if this filename is already part of a markdown link
            if f"/pdf/{filename})" in text or f"[{filename}](" in text:
                continue
            link = f"[{filename}](/api/agents/{agent_id}/pdf/{filename})"
            text = text.replace(filename, link)

        return text

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    # NOTE: badge rendering and audit logging live in base/badges.py.
    # Mixins call ReliabilityBadge / AuditLogger directly.
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

    # ------------------------------------------------------------------
    # History & reindex
    # ------------------------------------------------------------------

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
        """Reindexa todos los documentos (util despues de anadir nuevos)."""
        # Inicializar ChromaDB si no esta inicializado
        if not self._chromadb_initialized:
            self._init_chromadb()

        if self._chromadb_error:
            return 0

        # Borrar coleccion existente
        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._index_documents()
        return self.collection.count()
