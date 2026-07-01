"""VectorlessMixin - Replaces ChromaDB with keyword-based BM25 retrieval
from a pre-built chunk database (chunk_db.json).

Use this as the FIRST parent in the MRO so it intercepts _init_chromadb and
_retrieve_context before BaseRAGAgent:

    class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
        _AGENT_FILE = __file__

The chunk database is built by running build_chunk_db.py in the agent directory.
If no chunk_db.json exists, retrieval returns empty context (pure metadata mode).
"""

import json
import math
import os
import re
import sys


# Simple tokenizer matching the one used in build_chunk_db.py
_WORD_RE = re.compile(r"[a-z][a-z0-9]{2,}", re.IGNORECASE)

STOP_WORDS = frozenset(
    "a an the and or but in on of to for is are was were be been being "
    "have has had do does did will would shall should may might can could "
    "this that these those it its i we you he she they them their our "
    "with from by at as not no nor so if than too very also about above "
    "after before between into through during over under up down out off "
    "then once here there when where which who whom what how all each "
    "both few more most other some such only own same just because "
    "while however although though even still already yet since until "
    "much many well back new also make like use used using".split()
)


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, excluding stop words."""
    words = _WORD_RE.findall(text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def _bm25_score(query_tokens: list[str], chunk_keywords: list[str],
                idf: dict, k1: float = 1.5, b: float = 0.75,
                avg_kw_len: float = 15.0) -> float:
    """Compute BM25 score for a chunk given query tokens."""
    kw_set = set(chunk_keywords)
    doc_len = len(chunk_keywords)
    score = 0.0
    for qt in query_tokens:
        if qt not in kw_set:
            continue
        tf = chunk_keywords.count(qt)
        idf_val = idf.get(qt, 0.0)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / avg_kw_len)
        score += idf_val * numerator / denominator
    return score


class VectorlessMixin:
    """Mixin that replaces ChromaDB with BM25 keyword retrieval from chunk_db.json.

    All metadata-based functionality (topic search, researcher lookup, project
    search, figures, maps, gap analysis) continues to work unchanged.  For
    free-text queries that fall through to RAG, this mixin searches a pre-built
    keyword-indexed chunk database using BM25 scoring instead of vector
    similarity.
    """

    _chunk_db = None       # Loaded once, shared across queries
    _chunk_db_idf = None
    _chunk_db_avg_kw = 15.0
    _skip_claim_classification = True   # Banners handle transparency, no need for claim analysis
    _show_procedural_banners = True   # Show procedural banners (green/yellow/red)
    _init_status_message = "Preparing knowledge base — indexing documents..."

    def _init_chromadb(self):
        """Skip ChromaDB — load or rebuild the keyword chunk database."""
        self._chromadb_initialized = True
        self._chromadb_error = None
        self.chroma_client = None
        self.collection = None

        if not hasattr(self, '_instance_chunk_db') or self._instance_chunk_db is None:
            db_path = os.path.join(self._agent_dir, "data", "chunk_db.json")

            # Auto-rebuild if chunk_db.json is missing or stale
            if self._chunk_db_needs_rebuild(db_path):
                self._report_progress("Rebuilding search index from documents...")
                self._rebuild_chunk_db(db_path)

            # Load chunk_db.json
            if os.path.exists(db_path):
                self._report_progress("Loading search index...")
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._instance_chunk_db = data.get("chunks", [])
                    self._instance_chunk_db_idf = data.get("idf", {})
                    total_kw = sum(len(c.get("keywords", [])) for c in self._instance_chunk_db)
                    if self._instance_chunk_db:
                        self._instance_chunk_db_avg_kw = total_kw / len(self._instance_chunk_db)
                    else:
                        self._instance_chunk_db_avg_kw = 15.0
                    print(f"Vectorless chunk DB loaded: {len(self._instance_chunk_db)} chunks, "
                          f"{len(self._instance_chunk_db_idf)} IDF terms ({os.path.basename(self._agent_dir)})")
                except Exception as e:
                    print(f"Warning: could not load chunk_db.json: {e}")
                    self._instance_chunk_db = []
                    self._instance_chunk_db_idf = {}
                    self._instance_chunk_db_avg_kw = 15.0
            else:
                print("No chunk_db.json and no documents to build from — pure metadata mode")
                self._instance_chunk_db = []
                self._instance_chunk_db_idf = {}
                self._instance_chunk_db_avg_kw = 15.0

    def _report_progress(self, message: str):
        """Report progress via callback if available, otherwise print."""
        cb = getattr(self, '_progress_callback', None)
        if cb:
            cb(message)
        print(message)

    def _chunk_db_needs_rebuild(self, db_path: str) -> bool:
        """Check if chunk_db.json is missing or older than any document."""
        if not os.path.exists(db_path):
            # Only rebuild if there are actual documents
            docs_dir = os.path.join(self._agent_dir, "data", "docs")
            return os.path.exists(docs_dir) and any(
                f.endswith(('.pdf', '.md', '.txt')) for f in os.listdir(docs_dir)
            )

        db_mtime = os.path.getmtime(db_path)

        # Check all document directories
        doc_dirs = [os.path.join(self._agent_dir, "data", "docs")]
        for extra in self._config.get("extra_docs_dirs", []):
            doc_dirs.append(os.path.join(self._agent_dir, "data", extra))

        for docs_dir in doc_dirs:
            if not os.path.exists(docs_dir):
                continue
            for filename in os.listdir(docs_dir):
                if not filename.endswith(('.pdf', '.md', '.txt')):
                    continue
                filepath = os.path.join(docs_dir, filename)
                if os.path.isfile(filepath) and os.path.getmtime(filepath) > db_mtime:
                    print(f"chunk_db.json is stale ({filename} is newer) — rebuilding...")
                    return True

        return False

    def _rebuild_chunk_db(self, db_path: str):
        """Rebuild chunk_db.json by invoking build_chunk_db."""
        # Import the builder from the agent directory
        builder_path = os.path.join(self._agent_dir, "build_chunk_db.py")
        if not os.path.exists(builder_path):
            print("No build_chunk_db.py found — cannot auto-rebuild chunk database")
            return

        print("Auto-rebuilding chunk database...")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, builder_path, "--agent-dir", self._agent_dir, "--output", db_path],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                print("Chunk database rebuilt successfully")
            else:
                print(f"Warning: chunk DB rebuild failed: {result.stderr[-200:]}")
        except Exception as e:
            print(f"Warning: could not rebuild chunk database: {e}")

    def _retrieve_context(self, query: str, n_results: int = None, **kwargs) -> str:
        """Retrieve relevant chunks using BM25 keyword matching."""
        chunks = getattr(self, '_instance_chunk_db', None) or []
        idf = getattr(self, '_instance_chunk_db_idf', None) or {}
        if not chunks or not idf:
            return ""

        if n_results is None:
            n_results = getattr(self, "retrieve_chunks", 5)

        query_tokens = _tokenize(query)
        if not query_tokens:
            return ""

        # Score all chunks
        scored = []
        for chunk in chunks:
            score = _bm25_score(
                query_tokens, chunk.get("keywords", []),
                idf, avg_kw_len=getattr(self, '_instance_chunk_db_avg_kw', 15.0),
            )
            if score > 0:
                scored.append((score, chunk))

        if not scored:
            return ""

        # Sort by score descending, take top N
        scored.sort(key=lambda x: -x[0])
        top = scored[:n_results]

        # Format like BaseRAGAgent._retrieve_context
        context_parts = []
        has_glossary = False
        for score, chunk in top:
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            # Tag glossary chunks so the LLM knows they are NOT UNINOVIS papers
            is_glossary = not source.startswith("W") and source.endswith(".md")
            if is_glossary:
                has_glossary = True
                context_parts.append(
                    f"[Fuente: {source} — GLOSSARY: definitions and concepts, "
                    f"NOT UNINOVIS papers]\n{text}"
                )
            else:
                context_parts.append(f"[Fuente: {source}]\n{text}")

        result = "\n\n---\n\n".join(context_parts)

        if has_glossary:
            result += (
                "\n\n⚠️ IMPORTANT: Glossary chunks above contain definitions and "
                "concept explanations from the curated glossary. Any paper titles, "
                "authors, or references mentioned in glossary text are from EXTERNAL "
                "literature and are NOT papers in the UNINOVIS database. Do NOT cite "
                "them as UNINOVIS papers. Only cite papers that appear in the "
                "TOPIC SEARCH RESULTS or structured metadata sections."
            )

        return result

    def reindex(self):
        """Clear cached chunk DB so it reloads on next query."""
        self._instance_chunk_db = None
        self._instance_chunk_db_idf = None
        self._instance_chunk_db_avg_kw = 15.0
        if hasattr(self, '_metadata_cache'):
            self._metadata_cache = None
        return 0
