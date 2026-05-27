"""MetadataRAGMixin - Mixin for RAG+Metadata agents (robotics_ai, health_tech, responsible_ai).

Provides ALL methods specific to metadata-enriched RAG agents that are NOT
in BaseRAGAgent or SimpleRAGMixin, including:
- Metadata loading and extraction
- Paper/researcher context builders
- Paper search and map data methods
- Map HTML builders (Leaflet)
- Query classification helpers
- chat() and chat_stream() with complex routing
- reindex() with metadata cache clearing
"""

import asyncio
import os
import sys
import json
import re
import glob
import logging
import urllib.request
import urllib.error
import urllib.parse

logger = logging.getLogger(__name__)

from .claims import ClaimExtractor, GroundingAnalyzer


# ---------------------------------------------------------------------------
# Web search helper (Google Custom Search API)
# ---------------------------------------------------------------------------

def _web_search(query: str, api_key: str, cx: str, num_results: int = 5) -> str:
    """Search the web via Google Custom Search API and return concatenated snippets.

    Parameters
    ----------
    query : str
        Search query string.
    api_key : str
        Google API key.
    cx : str
        Google Custom Search Engine ID.
    num_results : int
        Number of results to request (max 10).

    Returns
    -------
    str
        Concatenated snippets from search results, each prefixed with
        source URL and title. Empty string on error or no results.
    """
    if not api_key or not cx:
        return ""

    params = urllib.parse.urlencode({
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(num_results, 10),
    })
    url = f"https://www.googleapis.com/customsearch/v1?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TOMMI-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        print(f"[web_search] Error: {e}")
        return ""

    items = data.get("items", [])
    if not items:
        return ""

    parts = []
    for item in items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        parts.append(f"[Web source: {link} | {title}]\n{snippet}")

    return "\n\n---\n\n".join(parts)
from .badges import ReliabilityBadge, AuditLogger, StudyLogger


class MetadataRAGMixin:
    """Mixin providing chat()/chat_stream() and metadata features for RAG+Metadata agents.

    Must be combined with BaseRAGAgent (which provides _agent_dir, _config,
    _build_system_prompt, _load_rag_config, _extract_pdf_text, _init_chromadb,
    _get_indexed_sources, _get_docs_files, etc.).
    """

    # ------------------------------------------------------------------
    # Keyword patterns for matching UNINOVIS universities in affiliation strings.
    # IMPORTANT: Use specific institution names, NOT just city names, to avoid
    # false matches (e.g. "Universitaetsklinikum Wuerzburg" is NOT THWS).
    # ------------------------------------------------------------------
    UNINOVIS_AFFILIATION_KEYWORDS = {
        "USPN":  ["sorbonne paris nord", "paris 13", "universite sorbonne paris nord"],
        "UDCLV": ["vanvitelli", "university of campania"],
        "UMA":   ["universidad de malaga", "malaga university", "malaga"],
        "KK":    ["kauno kolegija", "kaunas kolegija"],
        "UT":    ["universiteti i tiranes", "universiteti i tiranes",
                  "=university of tirana"],
        "THWS":  ["technical university of applied sciences wurzburg",
                  "hochschule fur angewandte wissenschaften wurzburg",
                  "thws", "fhws"],
        "TAMK":  ["tampere university of applied sciences", "tampereen ammattikorkeakoulu"],
        "THUAS": ["hague university of applied sciences", "haagse hogeschool"],
    }

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

    # ------------------------------------------------------------------
    # _post_init hook (overrides BaseRAGAgent)
    # ------------------------------------------------------------------

    def _post_init(self):
        """Load metadata caches and structured data, then init ChromaDB."""
        # Document metadata cache
        self._documents_metadata = {}

        # Load metadata configuration
        self._load_metadata_config()

        # Cache papers data from papers.json (used by multiple methods)
        self._all_uni_papers = {}
        papers_json_path = os.path.join(self._agent_dir, "data", "papers.json")
        if os.path.exists(papers_json_path):
            try:
                with open(papers_json_path, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                for acronym, uni_data in pdata.get("universities", {}).items():
                    self._all_uni_papers[acronym] = uni_data.get("papers", [])
                total_p = sum(len(v) for v in self._all_uni_papers.values())
                print(f"Papers cache loaded: {total_p} papers across {len(self._all_uni_papers)} universities")
            except Exception as e:
                print(f"Warning: Could not load papers.json: {e}")

        # Cache projects data from project_docs/ markdown files
        self._all_uni_projects = {}
        self._load_project_docs()

        # Load researchers index
        self._researchers_by_uni = {}
        researchers_path = os.path.join(self._agent_dir, "data", "researchers.json")
        if os.path.exists(researchers_path):
            try:
                with open(researchers_path, "r", encoding="utf-8") as f:
                    self._researchers_by_uni = json.load(f)
                total_r = sum(len(v) for v in self._researchers_by_uni.values())
                print(f"Researchers index loaded: {total_r} researchers across {len(self._researchers_by_uni)} universities")
            except Exception as e:
                print(f"Warning: Could not load researchers.json: {e}")

        # Build topical scope set for two-axis banner system
        self._topical_scope = self._build_topical_scope()

    # ------------------------------------------------------------------
    # Topical scope (two-axis banner system)
    # ------------------------------------------------------------------

    def _build_topical_scope(self) -> set:
        """Build a set of lowercase terms that define the agent's topical scope.

        Sources:
        1. Glossary concept names + aliases + abbreviations
        2. Related concepts from glossary entries
        3. Bold/technical terms from glossary definition bodies
        4. Concept/topic names from papers.json
        5. Researcher topics from researchers.json
        6. Extra scope terms from config.json
        """
        scope = set()

        # 1, 2 & 3: Glossary concepts, related concepts, and body terms
        glossary = self._load_glossary()
        for concept_name, entry in glossary.items():
            scope.add(concept_name.lower())
            # Abbreviations in parentheses
            abbrev_match = re.search(r'\(([A-Z]{2,})\)', concept_name)
            if abbrev_match:
                scope.add(abbrev_match.group(1).lower())
            # Name without parenthetical
            clean = re.sub(r'\s*\([^)]*\)\s*', '', concept_name).strip()
            if clean:
                scope.add(clean.lower())
            # Related concepts
            for related in entry.get("related_concepts", []):
                scope.add(related.lower().strip())
            # Bold terms from definition body (technical phrases)
            definition = entry.get("definition", "")
            for bold_match in re.findall(r'\*\*(.+?)\*\*', definition):
                term = bold_match.strip().strip(':.,').lower()
                if (term and len(term) > 3
                        and not term.startswith("related")
                        and not term.startswith("reference")):
                    scope.add(term)

        # 4: Concepts from papers
        for papers in self._all_uni_papers.values():
            for paper in papers:
                for concept in paper.get("concepts", []):
                    name = concept.get("name", "").lower().strip()
                    if name and len(name) > 2:
                        scope.add(name)

        # 5: Researcher topics
        for researchers in self._researchers_by_uni.values():
            for researcher in researchers:
                for topic in researcher.get("topics", []):
                    t = topic.lower().strip()
                    if t and len(t) > 2:
                        scope.add(t)

        # 6: Extra scope terms from config
        for term in self._config.get("extra_scope_terms", []):
            t = term.lower().strip()
            if t:
                scope.add(t)

        if scope:
            print(f"Topical scope built: {len(scope)} terms")
        return scope

    def _is_in_topical_scope(self, user_message: str) -> bool:
        """Check if the user's question falls within the agent's topical scope.

        Returns True if the message mentions any term from the scope set
        (glossary concepts, paper topics, researcher topics).
        Returns False for non-research task requests (write, translate, book,
        etc.) even if they contain scope terms.
        """
        if not self._topical_scope:
            return False
        msg_lower = user_message.lower()

        # Non-research task requests are out of scope regardless of terms present
        task_patterns = [
            r'^write\b.*\b(?:essay|report|letter|poem|story|code)\b',
            r'^translate\b',
            r'\btranslate\s+(?:this|the|my|following)\b',
            r'\bbook\s+(?:me|a|my)\b',
            r'\border\s+(?:me|a|my)\b',
            r'\bwho\s+won\b',
            r'\bwhat\s+is\s+the\s+(?:weather|temperature|time|capital|population)\b',
            r'\bwrite\s+(?:me\s+)?(?:an?\s+)?essay\b',
        ]
        if any(re.search(p, msg_lower) for p in task_patterns):
            return False

        # Meta-questions about the agent itself are always in scope
        meta_patterns = [
            "what can you do", "how does this work", "how do you work",
            "what kind of questions", "what do the", "what are the banners",
            "what is uninovis", "which universities",
        ]
        if any(p in msg_lower for p in meta_patterns):
            return True

        for term in self._topical_scope:
            if term in msg_lower:
                return True
        return False

    def _log_undefined_topic(self, user_message: str):
        """Log queries that are in-scope but have no glossary or database match.

        Writes to data/undefined_topics.jsonl so developers can review
        which Responsible AI concepts users are asking about.
        """
        import datetime
        log_path = os.path.join(self._agent_dir, "data", "undefined_topics.jsonl")
        try:
            entry = {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "query": user_message.strip(),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Non-critical — do not break the query flow

    # ------------------------------------------------------------------
    # Project document parsing
    # ------------------------------------------------------------------

    def _load_project_docs(self):
        """Parse project markdown files from data/project_docs/ into structured data.

        Each .md file has a consistent structure with grant ID, funder, programme,
        period, status, total cost, summary, keywords, participants, and UNINOVIS partners.
        Projects are grouped by UNINOVIS partner university acronym.
        """
        project_docs_dir = os.path.join(self._agent_dir, "data", "project_docs")
        if not os.path.isdir(project_docs_dir):
            return

        projects_by_uni = {}
        for md_path in sorted(glob.glob(os.path.join(project_docs_dir, "*.md"))):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()

                project = self._parse_project_md(content, os.path.basename(md_path))
                if not project:
                    continue

                for acronym in project.get("uninovis_partners", []):
                    projects_by_uni.setdefault(acronym, []).append(project)
            except Exception as e:
                print(f"Warning: Could not parse project file {md_path}: {e}")

        self._all_uni_projects = projects_by_uni
        total = sum(len(v) for v in projects_by_uni.values())
        if total:
            print(f"Projects cache loaded: {total} projects across {len(projects_by_uni)} universities")

    @staticmethod
    def _parse_project_md(content: str, filename: str) -> dict:
        """Parse a single project markdown file into a structured dict."""
        project = {"filename": filename}

        # Title: first markdown heading
        title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        if title_match:
            project["title"] = title_match.group(1).strip()
        else:
            project["title"] = filename.replace(".md", "")

        # Structured fields
        field_patterns = {
            "grant_id": r'\*\*Grant ID:\*\*\s*(.+)',
            "funder": r'\*\*Funder:\*\*\s*(.+)',
            "programme": r'\*\*Programme:\*\*\s*(.+)',
            "period": r'\*\*Period:\*\*\s*(.+)',
            "status": r'\*\*Status:\*\*\s*(.+)',
            "total_cost": r'\*\*Total cost:\*\*\s*(.+)',
        }
        for field, pattern in field_patterns.items():
            match = re.search(pattern, content)
            project[field] = match.group(1).strip() if match else ""

        # Extract start/end years from period (e.g. "2021-03-01 — 2023-02-28")
        period = project.get("period", "")
        year_matches = re.findall(r'(\d{4})', period)
        project["start_year"] = int(year_matches[0]) if len(year_matches) >= 1 else None
        project["end_year"] = int(year_matches[-1]) if len(year_matches) >= 2 else project.get("start_year")

        # Summary: text between ## Summary and the next ## or **Keywords
        summary_match = re.search(r'## Summary\s*\n(.*?)(?=\n##|\n\*\*Keywords)', content, re.DOTALL)
        project["summary"] = summary_match.group(1).strip() if summary_match else ""

        # Keywords
        kw_match = re.search(r'\*\*Keywords:\*\*\s*(.+)', content)
        if kw_match:
            project["keywords"] = [k.strip() for k in kw_match.group(1).split(",")]
        else:
            project["keywords"] = []

        # Participants
        participants = []
        in_participants = False
        for line in content.split("\n"):
            if line.strip() == "## Participants":
                in_participants = True
                continue
            if in_participants:
                if line.startswith("**UNINOVIS"):
                    break
                if line.strip().startswith("- "):
                    participants.append(line.strip()[2:].strip())
        project["participants"] = participants

        # Website URL
        website_match = re.search(r'\*\*Website:\*\*\s*(\S+)', content)
        project["website"] = website_match.group(1).strip() if website_match else ""

        # UNINOVIS researchers (added by enrich_projects.py)
        researchers_section = re.search(r'## UNINOVIS Researchers\s*\n(.*?)(?=\n## |\n\*\*UNINOVIS partners|\Z)', content, re.DOTALL)
        uninovis_researchers = []
        if researchers_section:
            for line in researchers_section.group(1).strip().split("\n"):
                # Format: **UMA:** Name1, Name2, Name3
                m = re.match(r'\*\*(\w+):\*\*\s*(.+)', line)
                if m:
                    acronym = m.group(1)
                    names = [n.strip() for n in m.group(2).split(",")]
                    for name in names:
                        if name:
                            uninovis_researchers.append({"name": name, "university": acronym})
        project["uninovis_researchers"] = uninovis_researchers

        # UNINOVIS partners
        partners_match = re.search(r'\*\*UNINOVIS partners:\*\*\s*(.+)', content)
        if partners_match:
            project["uninovis_partners"] = [p.strip() for p in partners_match.group(1).split(",")]
        else:
            project["uninovis_partners"] = []

        return project

    # ------------------------------------------------------------------
    # Metadata / Document methods
    # ------------------------------------------------------------------

    def _load_metadata_config(self):
        """Load metadata configuration and external metadata from data/metadata.json.

        The metadata.json file can contain:
        - "fields": list of metadata field names to track
        - "documents": dict mapping filenames to their metadata values,
          e.g. {"file.pdf": {"author": "Dr. Smith", "university": "UMA"}}

        External metadata supplements auto-extracted metadata (PDF metadata).
        If a field is provided in both, the external value takes precedence.
        """
        config_path = os.path.join(self._agent_dir, "data", "metadata.json")
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

    def _extract_metadata(self, filepath: str) -> dict:
        """Extract metadata from a file and combine with external metadata.

        Sources (in order of priority, lowest to highest):
        1. Basic file information (name, size, type)
        2. Embedded PDF metadata (title, author, date)
        3. External metadata from data/metadata.json (highest priority)
        """
        from pypdf import PdfReader

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

    def _refresh_metadata_cache(self):
        """Refresh the metadata cache from all document directories."""
        self._documents_metadata = {}
        for docs_path in self._get_all_docs_dirs():
            if not os.path.exists(docs_path):
                continue
            for filename in os.listdir(docs_path):
                filepath = os.path.join(docs_path, filename)
                if os.path.isfile(filepath) and filename.endswith(('.txt', '.md', '.pdf')):
                    self._documents_metadata[filename] = self._extract_metadata(filepath)

    def _index_documents(self, only_files: set = None):
        """Index documents from data/docs/ and any extra_docs_dirs with enriched metadata."""
        documents = []
        metadatas = []
        ids = []

        # Collect files from all document directories
        all_files = []  # list of (filename, filepath)
        for docs_path in self._get_all_docs_dirs():
            if not os.path.exists(docs_path):
                os.makedirs(docs_path, exist_ok=True)
                continue
            for f in os.listdir(docs_path):
                fp = os.path.join(docs_path, f)
                if os.path.isfile(fp) and (only_files is None or f in only_files):
                    all_files.append((f, fp))

        if not all_files:
            return

        total_files = len(all_files)

        for i, (filename, filepath) in enumerate(all_files):

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

    def _sync_documents(self):
        """Synchronize documents: index new, remove orphans.
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
        """Retrieve relevant context for the query, with optional metadata filter.

        Args:
            query: The search query
            n_results: Number of chunks to retrieve
            metadata_filter: Optional ChromaDB where filter for metadata
                            e.g. {"author": "John"} or {"file_type": "pdf"}

        Returns:
            context_str with retrieved document chunks and metadata.
        """
        if n_results is None:
            n_results = self.retrieve_chunks
        if self.collection is None or self.collection.count() == 0:
            return ""

        query_params = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas"],
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

    # ------------------------------------------------------------------
    # Paper / researcher context builders
    # ------------------------------------------------------------------

    def _build_metadata_context(self) -> str:
        """Build a metadata summary string to include in the system prompt."""
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
                lines.append(f"- [{unis}] \"{p['title']}\"{year_str} -- Authors: {authors}")
            lines.append("")
            lines.append("IMPORTANT: When the user asks about collaborations filtered by year, trust the collaboration data above -- filter it by the year shown in parentheses. Do NOT second-guess whether a paper is a real collaboration; if it appears in this list, it IS a confirmed collaboration.")
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
        lines.append("IMPORTANT: This is supplementary data for reference. Do NOT present this list as a separate section in your answer. When the user asks about relevant topics, integrate this information naturally with the content retrieved from the documents. Do not duplicate information -- if the retrieved documents already discuss topics, prefer that content over this list.")
        return "\n".join(lines)

    def _load_glossary(self) -> dict:
        """Load and parse the responsible AI glossary into a dict keyed by concept name.

        Returns a dict like:
            {"Explainable Artificial Intelligence (XAI)": {"definition": "...", "related_concepts": [...], "references": "..."}, ...}

        The glossary is cached after first load.
        """
        if hasattr(self, '_glossary_cache'):
            return self._glossary_cache

        glossary_path = os.path.join(self._agent_dir, "data", "docs", "responsible_ai_glossary.md")
        if not os.path.exists(glossary_path):
            glossary_path = os.path.join(self._agent_dir, "data", "docs", "Glossary_Responsible_AI.md")
        if not os.path.exists(glossary_path):
            self._glossary_cache = {}
            return self._glossary_cache

        with open(glossary_path, "r", encoding="utf-8") as f:
            content = f.read()

        glossary = {}
        # Split by ## headings
        sections = re.split(r'^## ', content, flags=re.MULTILINE)
        for section in sections[1:]:  # skip preamble before first ##
            lines = section.strip().split('\n')
            concept_name = lines[0].strip()
            body = '\n'.join(lines[1:]).strip()

            # Extract related_concepts if present
            related = []
            related_match = re.search(r'\*\*Related concepts:\*\*\s*(.+?)(?:\n\n|\n\*\*|\Z)', body, re.DOTALL)
            if related_match:
                related_text = related_match.group(1).strip()
                related = [r.strip().strip('.,') for r in re.split(r'[,;]', related_text) if r.strip()]

            glossary[concept_name] = {
                "definition": body,
                "related_concepts": related,
            }

        self._glossary_cache = glossary
        return self._glossary_cache

    def _build_glossary_context(self, user_message: str) -> str:
        """Build glossary context for conceptual questions.

        Extracts concept names mentioned in the user message and returns
        their glossary definitions plus related concepts.
        """
        glossary = self._load_glossary()
        if not glossary:
            return ""

        msg_lower = user_message.lower()
        matched = []

        # Build lookup: lowercase aliases -> concept key
        aliases = {}
        for concept_name in glossary:
            aliases[concept_name.lower()] = concept_name
            # Also match abbreviations in parentheses, e.g. "XAI" from "Explainable Artificial Intelligence (XAI)"
            abbrev_match = re.search(r'\(([A-Z]{2,})\)', concept_name)
            if abbrev_match:
                aliases[abbrev_match.group(1).lower()] = concept_name
            # Also match the name without parenthetical
            clean = re.sub(r'\s*\([^)]*\)\s*', '', concept_name).strip()
            if clean:
                aliases[clean.lower()] = concept_name
            # Also match shortened forms: "Explainable Artificial Intelligence" -> "explainable ai"
            short = re.sub(r'\bartificial intelligence\b', 'ai', clean.lower())
            if short != clean.lower():
                aliases[short] = concept_name

        # Find concepts mentioned in the question
        for alias, concept_name in aliases.items():
            if alias in msg_lower and concept_name not in matched:
                matched.append(concept_name)

        # Also include related concepts of matched entries
        related_to_add = []
        for concept_name in matched:
            entry = glossary[concept_name]
            for related in entry.get("related_concepts", []):
                # Find the glossary entry for this related concept
                for alias, full_name in aliases.items():
                    if related.lower() == alias or related.lower() in alias:
                        if full_name not in matched and full_name not in related_to_add:
                            related_to_add.append(full_name)
                        break

        all_concepts = matched + related_to_add

        if not all_concepts:
            return ""

        lines = ["GLOSSARY CONTEXT — Definitions from the Responsible AI Glossary:"]
        lines.append("Use this information to answer the user's conceptual question. "
                      "Do NOT search for papers unless the user explicitly asks for papers. "
                      "IMPORTANT: When listing references, you MUST include the full URLs exactly as they appear in the glossary entries below. "
                      "Do NOT omit or shorten the URLs.")
        for concept_name in all_concepts:
            entry = glossary[concept_name]
            lines.append(f"\n### {concept_name}")
            lines.append(entry["definition"])
        return "\n".join(lines)

    def _build_topic_context(self, user_message: str) -> str:
        """Extract topic from user message and return structured paper data
        from search_papers_by_topic so that text responses and figures use the same source.
        Returns context even when 0 results are found (confirmed absence is authoritative)."""

        topic = self._extract_topic(user_message)
        if not topic:
            return ""

        results = self.search_papers_by_topic(topic)

        # If the user asked about a specific university, filter results to only that university
        uni_filter = self._detect_university_filter(user_message)
        if uni_filter:
            if "university_acronym" in uni_filter:
                val = uni_filter["university_acronym"]
                if isinstance(val, str):
                    allowed = {val}
                elif isinstance(val, dict) and "$in" in val:
                    allowed = set(val["$in"])
                else:
                    allowed = None
                if allowed:
                    results = {k: v for k, v in results.items() if k in allowed}

        total = sum(uni["count"] for uni in results.values())
        if total == 0:
            return f'TOPIC SEARCH RESULTS for "{topic}": 0 papers found. This topic has not been studied by UNINOVIS universities.'

        # Build set of confirmed UNINOVIS researchers per university
        uninovis_researchers = {}
        for acronym, researchers in self._researchers_by_uni.items():
            uninovis_researchers[acronym] = {r["name"] for r in researchers}

        lines = [f"TOPIC SEARCH RESULTS for \"{topic}\" ({total} papers total):"]
        lines.append(f"ANSWER MUST STATE EXACTLY {total} PAPERS. This is the verified count from the database. Do NOT invent a different number.")
        lines.append("CRITICAL: Use ONLY these topic-specific numbers and papers when answering. Do NOT use the overall PUBLICATION COUNTS PER UNIVERSITY -- those are totals across all topics.")
        lines.append("Only researchers confirmed as UNINOVIS members are listed. Other co-authors are from external institutions.")
        for acronym, uni in sorted(results.items(), key=lambda x: x[1]["count"], reverse=True):
            if uni["count"] == 0:
                continue
            # Filter authors to only confirmed UNINOVIS members who are
            # genuinely relevant to this topic:
            #   - appear on ≥2 matching papers, OR
            #   - appear on a paper with a strong topic match (topic in
            #     title or concepts, not just incidental abstract mention)
            uni_members = uninovis_researchers.get(acronym, set())
            author_paper_count = {}   # author → number of matching papers
            author_strong_match = {}  # author → has at least one strong match
            paper_details = []
            for p in uni["papers"]:
                is_strong = p.get("strong_topic_match", True)
                for a in p["authors"]:
                    if a in uni_members:
                        author_paper_count[a] = author_paper_count.get(a, 0) + 1
                        if is_strong:
                            author_strong_match[a] = True
                authors_str = ", ".join(p["authors"])
                year_str = f" ({p['year']})" if p.get("year") else ""
                pdf = self._pdf_link(p.get("id", ""), p.get("doi", ""))
                paper_details.append(f"  - \"{p['title']}\"{year_str} by {authors_str}{pdf}")
            # Keep only researchers with ≥2 papers OR at least one strong match
            paper_authors = {
                a for a in author_paper_count
                if author_paper_count[a] >= 2 or author_strong_match.get(a, False)
            }
            lines.append(f"\n{acronym} ({uni['name']}): {uni['count']} papers, {len(paper_authors)} UNINOVIS researchers")
            if paper_authors:
                lines.append(f"  UNINOVIS researchers: {', '.join(sorted(paper_authors))}")
            lines.extend(paper_details)

        return "\n".join(lines)

    def _build_topic_factual_section(self, user_message: str, show_banners: bool = True) -> str:
        """Build a user-facing factual section for topic queries.

        Returns markdown text generated PROGRAMMATICALLY from structured data
        (no LLM involved).  Every claim is directly traceable to papers.json.
        Returns "" if no topic is detected or no results found.
        """
        topic = self._extract_topic(user_message)
        if not topic:
            return ""

        results = self.search_papers_by_topic(topic)

        # Apply university filter if present
        uni_filter = self._detect_university_filter(user_message)
        if uni_filter:
            val = uni_filter.get("university_acronym")
            if isinstance(val, str):
                allowed = {val}
            elif isinstance(val, dict) and "$in" in val:
                allowed = set(val["$in"])
            else:
                allowed = None
            if allowed:
                results = {k: v for k, v in results.items() if k in allowed}

        total = sum(uni["count"] for uni in results.values())
        if total == 0:
            return f"No papers found on **{topic}** in the UNINOVIS database."

        # Build confirmed UNINOVIS researchers per university
        uninovis_researchers = {}
        for acronym, researchers in self._researchers_by_uni.items():
            uninovis_researchers[acronym] = {r["name"] for r in researchers}

        lines = []
        if show_banners:
            lines.append(self._banner_verified(f"{total} papers from the UNINOVIS database (no AI involved)."))
        lines.extend([
            f'### Papers on "{topic}" ({total} papers)',
            '',
        ])

        paper_num = 0
        for acronym, uni in sorted(results.items(), key=lambda x: x[1]["count"], reverse=True):
            if uni["count"] == 0:
                continue

            uni_members = uninovis_researchers.get(acronym, set())
            author_paper_count = {}
            author_strong_match = {}

            # Collect papers and researchers
            paper_lines = []
            for p in uni["papers"]:
                paper_num += 1
                is_strong = p.get("strong_topic_match", True)
                for a in p["authors"]:
                    if a in uni_members:
                        author_paper_count[a] = author_paper_count.get(a, 0) + 1
                        if is_strong:
                            author_strong_match[a] = True

                authors_str = ", ".join(p["authors"][:4])
                if len(p["authors"]) > 4:
                    authors_str += " et al."
                year_str = f" ({p['year']})" if p.get("year") else ""
                pdf = self._pdf_link(p.get("id", ""), p.get("doi", ""))
                paper_lines.append(f"- \"{p['title']}\"{year_str} — {authors_str}{pdf}")

            paper_authors = {
                a for a in author_paper_count
                if author_paper_count[a] >= 2 or author_strong_match.get(a, False)
            }

            # University header with researcher count
            researcher_note = f", {len(paper_authors)} UNINOVIS researchers" if paper_authors else ""
            lines.append(f"**{acronym}** ({uni['name']}): {uni['count']} papers{researcher_note}")
            if paper_authors:
                lines.append(f"*Researchers: {', '.join(sorted(paper_authors))}*")
            lines.append("")
            lines.extend(paper_lines)
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Section banners (4-level transparency system)
    # ------------------------------------------------------------------
    # 🟢 Verified data   — from structured database, no AI involved
    # 🟡 AI Commentary   — LLM summarizes/formats verified data
    # 🔴 AI Speculation  — LLM reasons beyond the data (gap analysis,
    #                       researcher connections) — verify before use
    # ⚪ Creative response — off-topic, no data relationship

    # Common style for all banners (consistent padding, radius, font)
    _BANNER_STYLE = 'padding:8px 12px;margin-bottom:10px;border-radius:4px;font-size:0.9em;'

    @classmethod
    def _banner_verified(cls, detail: str = "") -> str:
        """🟢 Green banner for programmatic data from structured metadata."""
        text = "This section is generated directly from the UNINOVIS database (no AI involved)."
        if detail:
            text = detail
        return (
            f'<div style="background-color:#d4edda;border-left:4px solid #28a745;{cls._BANNER_STYLE}">'
            f'\U0001F7E2 <strong>Verified data</strong> — {text}'
            '</div>\n\n'
        )

    @classmethod
    def _banner_database(cls, detail: str = "") -> str:
        """🟡 Yellow banner for LLM responses based on document database content."""
        text = "The response below is generated by the AI model based on research documents from the UNINOVIS database."
        if detail:
            text = detail
        note = (' <em style="font-weight:normal;font-size:0.9em;">'
                'Note: paper counts in AI-generated summaries are approximate groupings '
                'and may differ from exact database queries on the same topic.</em>')
        return (
            f'<div style="background-color:#fff3cd;border-left:4px solid #ffc107;{cls._BANNER_STYLE}">'
            f'\U0001F7E1 <strong>AI interpretation of database content</strong> — {text}{note}'
            '</div>\n\n'
        )

    @classmethod
    def _banner_commentary(cls, detail: str = "") -> str:
        """🟡 Yellow banner for low-risk LLM output (topic summary, formatting)."""
        text = "The commentary below is generated by the AI model based on the verified data above."
        if detail:
            text = detail
        return (
            '\n\n---\n\n'
            f'<div style="background-color:#fff3cd;border-left:4px solid #ffc107;{cls._BANNER_STYLE}">'
            f'\U0001F7E1 <strong>AI Commentary</strong> — {text}'
            '</div>\n\n'
        )

    @classmethod
    def _banner_speculation(cls, detail: str = "") -> str:
        """🔴 Red banner — AI output without direct database verification."""
        text = "The content below involves AI interpretation that should be verified before use."
        if detail:
            text = detail
        return (
            '\n\n---\n\n'
            f'<div style="background-color:#f8d7da;border-left:4px solid #dc3545;{cls._BANNER_STYLE}">'
            f'\U0001F534 <strong>Unverified</strong> — {text}'
            '</div>\n\n'
        )

    @classmethod
    def _banner_undefined(cls) -> str:
        """🟡 Yellow banner for on-topic queries not yet covered in the database."""
        return (
            f'<div style="background-color:#fff3cd;border-left:4px solid #ffc107;{cls._BANNER_STYLE}">'
            '\U0001F7E1 <strong>On-topic, undefined</strong> — '
            'This topic is related to Responsible AI but is not yet defined in the glossary '
            'or covered by specific papers in the database. The answer below is based on '
            'general AI knowledge. Consider adding a glossary entry or related research.'
            '</div>\n\n'
        )

    @classmethod
    def _banner_creative(cls) -> str:
        """🔴 Red banner for off-topic responses — no database verification possible."""
        return (
            f'<div style="background-color:#f8d7da;border-left:4px solid #dc3545;{cls._BANNER_STYLE}">'
            '\U0001F534 <strong>Unverified</strong> — '
            'This is outside the scope of the UNINOVIS research database.'
            '</div>\n\n'
        )

    @staticmethod
    def _glossary_answer_diverged(llm_response: str, glossary_ctx: str) -> bool:
        """Check if the LLM response substantially diverges from the glossary content.

        Returns True if the LLM introduced significant content not present in the
        glossary, suggesting the answer goes beyond curated definitions.
        """
        # Extract glossary definition text (strip the GLOSSARY CONTEXT header)
        glossary_words = set(re.findall(r'[a-z]{3,}', glossary_ctx.lower()))
        response_words = set(re.findall(r'[a-z]{3,}', llm_response.lower()))

        if not response_words:
            return False

        # Words in the response that are NOT in the glossary
        novel_words = response_words - glossary_words
        # Common filler/connecting words that don't indicate divergence
        fillers = {
            'the', 'and', 'that', 'this', 'with', 'for', 'are', 'from', 'has',
            'have', 'been', 'which', 'their', 'also', 'can', 'not', 'but',
            'may', 'more', 'such', 'into', 'these', 'than', 'other', 'its',
            'all', 'some', 'about', 'would', 'will', 'could', 'should',
            'being', 'each', 'how', 'our', 'many', 'most', 'often',
            'generally', 'understood', 'described', 'commonly', 'according',
            'various', 'across', 'while', 'both', 'between', 'those',
        }
        novel_words -= fillers
        # High proportion of novel substantive words suggests divergence
        substantive_response = response_words - fillers
        if not substantive_response:
            return False
        novelty_ratio = len(novel_words) / len(substantive_response)
        return novelty_ratio > 0.5

    @staticmethod
    def _analysis_prompt(topic: str, hedged: bool = False) -> str:
        """Return the constrained prompt for LLM analysis of topic data."""
        base = (
            f"The factual data above has already been shown to the user. "
            f"DO NOT repeat any paper titles, authors, IDs, or counts — the user can already see them. "
            f"DO NOT list or enumerate papers. DO NOT start with a heading or horizontal rule. "
            f"Instead, provide a brief analytical commentary (3-5 sentences) about the research on \"{topic}\" "
            f"based ONLY on the data in the context. You may comment on: "
            f"which universities are most active, what subtopics emerge, whether there are collaboration patterns, "
            f"or suggest related topics the user might explore."
        )
        if hedged:
            base += (
                f"\n\nIMPORTANT STYLE (MANDATORY): This commentary is YOUR interpretation, not verified fact. "
                f"The user can already see the raw data — your job is to offer perspective, not authority. "
                f"You MUST:\n"
                f"- Use cautious, hedging language throughout (e.g., 'the data suggests', "
                f"'this may indicate', 'it appears that', 'based on the available records').\n"
                f"- NEVER use definitive or authoritative phrasing such as 'this shows', 'this confirms', "
                f"'it is clear', 'the most active', 'the leading'. Instead say 'appear to be among the most active', "
                f"'seem to contribute frequently'.\n"
                f"- For EVERY pattern you mention, offer at least one alternative explanation "
                f"(e.g., 'though this could reflect indexing differences rather than actual research volume').\n"
                f"- Acknowledge that the database is partial and may not represent the full picture.\n"
                f"- Frame suggestions as gentle possibilities, not directives."
            )
        return base

    @staticmethod
    def _is_project_query(user_message: str) -> bool:
        """Detect if the user is asking about research projects (not papers)."""
        msg_lower = user_message.lower()
        project_phrases = [
            "project", "projects", "grant", "grants", "funding",
            "funded", "funder", "consortium", "consortia",
        ]
        return any(phrase in msg_lower for phrase in project_phrases)

    def _find_project_by_name(self, user_message: str) -> list:
        """Find projects whose acronym or title appears in the user message.
        Returns list of (project_dict, university_acronym) tuples."""
        msg_lower = user_message.lower()
        matches = []
        seen_grants = set()
        for acronym, projects in self._all_uni_projects.items():
            for proj in projects:
                grant_id = proj.get("grant_id", "")
                if grant_id in seen_grants:
                    continue
                # Match project title keywords (the part before the colon, i.e. the acronym)
                title = proj.get("title", "")
                # Extract acronym from title like "InnoGuard: Hybrid and Generative..."
                proj_acronym = title.split(":")[0].strip() if ":" in title else ""
                if proj_acronym and len(proj_acronym) >= 3 and proj_acronym.lower() in msg_lower:
                    matches.append((proj, acronym))
                    seen_grants.add(grant_id)
                elif grant_id and grant_id in user_message:
                    matches.append((proj, acronym))
                    seen_grants.add(grant_id)
        return matches

    def _build_project_context(self, user_message: str) -> str:
        """Extract topic from user message and return structured project data.
        Only triggered when the query is about projects (not papers)."""
        if not self._all_uni_projects:
            return ""
        if not self._is_project_query(user_message):
            return ""

        # First try to find a specific project by name/acronym
        named_matches = self._find_project_by_name(user_message)
        if named_matches:
            lines = [f"PROJECT SEARCH RESULTS ({len(named_matches)} project(s) matching query):"]
            lines.append("This data is authoritative -- use it as-is. These are PROJECTS (funded research), NOT papers/publications.")
            for proj, uni_acronym in named_matches:
                lines.append(self._format_project_detail(self._format_project(proj), uni_acronym))
            return "\n".join(lines)

        topic = self._extract_topic(user_message)

        if topic:
            results = self.search_projects_by_topic(topic)
        else:
            results = self.get_all_projects_by_university()

        total = sum(uni["count"] for uni in results.values())
        label = f' on "{topic}"' if topic else ""

        if total == 0:
            return f'PROJECT SEARCH RESULTS{label}: 0 projects found.'

        lines = [f"PROJECT SEARCH RESULTS{label} ({total} projects total):"]
        lines.append("This data is authoritative -- use it as-is. These are PROJECTS (funded research), NOT papers/publications.")
        for acronym, uni in sorted(results.items(), key=lambda x: x[1]["count"], reverse=True):
            if uni["count"] == 0:
                continue
            lines.append(f"\n{acronym} ({uni['name']}): {uni['count']} projects")
            for p in uni["projects"]:
                lines.append(self._format_project_detail(p, acronym))

        return "\n".join(lines)

    @staticmethod
    def _format_project_detail(p: dict, uni_acronym: str) -> str:
        """Format a single project dict into a detailed text line for LLM context."""
        detail = f"  - \"{p['title']}\" (Grant: {p['grant_id']}, University: {uni_acronym})"
        if p.get("funder"):
            detail += f" — Funder: {p['funder']}"
        if p.get("period"):
            detail += f" — {p['period']}"
        if p.get("status"):
            detail += f" ({p['status']})"
        if p.get("total_cost"):
            detail += f" — Budget: {p['total_cost']}"
        if p.get("website"):
            detail += f"\n    Website: {p['website']}"
        researchers = p.get("uninovis_researchers", [])
        if researchers:
            names = ", ".join(r["name"] for r in researchers)
            detail += f"\n    UNINOVIS researchers: {names}"
        if p.get("participants"):
            detail += f"\n    Participants: {', '.join(p['participants'])}"
        return detail

    def _build_university_papers_context(self, user_message: str) -> str:
        """When a university is mentioned but no research topic is detected,
        return the authoritative paper list from *_papers.json instead of RAG.

        Triggers whenever a university is detected and no topic is extracted,
        regardless of specific keywords -- structured data is always more
        authoritative than RAG for university-specific queries.
        """
        # Detect university
        uni_filter = self._detect_university_filter(user_message)
        if not uni_filter:
            return ""

        # Extract the set of target acronyms
        val = uni_filter.get("university_acronym")
        if isinstance(val, str):
            target_acronyms = {val}
        elif isinstance(val, dict) and "$in" in val:
            target_acronyms = set(val["$in"])
        else:
            return ""

        # Check that no specific topic was extracted (those go through _build_topic_context)
        topic = self._extract_topic(user_message)
        if topic:
            return ""

        # Use get_all_papers_by_university for authoritative data
        all_results = self.get_all_papers_by_university()
        results = {k: v for k, v in all_results.items() if k in target_acronyms}

        total = sum(uni["count"] for uni in results.values())
        if total == 0:
            return ""

        # Build set of confirmed UNINOVIS researchers per university
        uninovis_researchers = {}
        for acronym, researchers in self._researchers_by_uni.items():
            uninovis_researchers[acronym] = {r["name"] for r in researchers}

        lines = [f"UNIVERSITY PAPERS ({total} papers total):"]
        lines.append("This data is authoritative -- use it as-is. Do NOT add papers from other sources.")
        for acronym, uni in sorted(results.items(), key=lambda x: x[1]["count"], reverse=True):
            if uni["count"] == 0:
                continue
            uni_members = uninovis_researchers.get(acronym, set())
            paper_authors = set()
            paper_details = []
            for p in uni["papers"]:
                for a in p["authors"]:
                    if a in uni_members:
                        paper_authors.add(a)
                authors_str = ", ".join(p["authors"])
                year_str = f" ({p['year']})" if p.get("year") else ""
                cited = f" -- Cited: {p['cited_by_count']}" if p.get("cited_by_count") else ""
                pdf = self._pdf_link(p.get("id", ""), p.get("doi", ""))
                paper_details.append(f"  - \"{p['title']}\"{year_str} by {authors_str}{cited}{pdf}")
            lines.append(f"\n{acronym} ({uni['name']}): {uni['count']} papers, {len(paper_authors)} UNINOVIS researchers")
            if paper_authors:
                lines.append(f"  UNINOVIS researchers: {', '.join(sorted(paper_authors))}")
            lines.extend(paper_details)

        return "\n".join(lines)

    def _is_shared_topics_query(self, user_message: str) -> bool:
        """Detect if the user is asking about shared/common topics between universities."""
        uni_filter = self._detect_university_filter(user_message)
        if not uni_filter:
            return False
        val = uni_filter.get("university_acronym")
        # Need 2+ universities
        if not (isinstance(val, dict) and "$in" in val and len(val["$in"]) >= 2):
            return False
        msg_lower = user_message.lower()
        # Comparison intent keywords
        comparison_words = [
            "shared", "common", "in common", "both", "compare", "comparison",
            "overlap", "overlapping", "similar", "similarities", "mutual",
            "together", "intersection",
        ]
        # Topic/interest keywords
        topic_words = [
            "topic", "interest", "area", "field", "theme", "subject",
            "research line", "research area",
        ]
        has_comparison = any(w in msg_lower for w in comparison_words)
        has_topic = any(w in msg_lower for w in topic_words)
        return has_comparison or has_topic

    def _build_shared_topics_context(self, user_message: str) -> str:
        """Build programmatic context for shared research topics between universities.

        Groups papers by shared OpenAlex concept tags across the requested
        universities, with full paper details and links.
        """
        uni_filter = self._detect_university_filter(user_message)
        if not uni_filter:
            return ""
        val = uni_filter.get("university_acronym")
        if isinstance(val, dict) and "$in" in val:
            target_acronyms = set(val["$in"])
        else:
            return ""

        if len(target_acronyms) < 2:
            return ""

        min_concept_score = 0.3

        # Collect concepts per university with their papers
        # concept_name → {acronym → [paper_dicts]}
        concept_unis = {}
        for acronym in target_acronyms:
            papers = self._all_uni_papers.get(acronym, [])
            for p in papers:
                for c in p.get("concepts", []):
                    if c.get("score", 0) < min_concept_score:
                        continue
                    cname = c["name"]
                    if cname not in concept_unis:
                        concept_unis[cname] = {}
                    if acronym not in concept_unis[cname]:
                        concept_unis[cname][acronym] = []
                    concept_unis[cname][acronym].append(p)

        # Filter to concepts present in ALL target universities
        shared_concepts = {}
        for cname, unis_papers in concept_unis.items():
            if target_acronyms.issubset(unis_papers.keys()):
                total = sum(len(ps) for ps in unis_papers.values())
                shared_concepts[cname] = (unis_papers, total)

        if not shared_concepts:
            acronyms_str = " and ".join(sorted(target_acronyms))
            return f"No shared research topics found between {acronyms_str} in the UNINOVIS database."

        # Sort by total papers descending, take top 15 concepts
        sorted_concepts = sorted(shared_concepts.items(), key=lambda x: x[1][1], reverse=True)[:15]

        # Filter out overly generic concepts (Computer science, Business, etc.)
        generic_concepts = {
            "computer science", "mathematics", "business", "engineering",
            "political science", "sociology", "psychology", "philosophy",
            "economics", "medicine", "biology",
        }
        sorted_concepts = [
            (cname, data) for cname, data in sorted_concepts
            if cname.lower() not in generic_concepts
        ]

        acronyms_str = " and ".join(sorted(target_acronyms))
        lines = [f'SHARED RESEARCH TOPICS between {acronyms_str} ({len(sorted_concepts)} topics):']
        lines.append("This data is authoritative — generated from OpenAlex concept tags in the database.")
        lines.append("Present the topics with their papers grouped by university. Include all paper links provided below.")
        lines.append("")

        seen_paper_ids = set()
        for cname, (unis_papers, total) in sorted_concepts:
            lines.append(f"### {cname} ({total} papers total)")
            for acronym in sorted(target_acronyms):
                papers = unis_papers.get(acronym, [])
                if not papers:
                    continue
                uni_name = self.UNIVERSITY_COORDS.get(acronym, {}).get("name", acronym)
                lines.append(f"**{acronym}** ({uni_name}): {len(papers)} papers")
                for p in papers:
                    pid = p.get("id", "")
                    if pid in seen_paper_ids:
                        continue
                    seen_paper_ids.add(pid)
                    authors = [a.get("name", "") for a in p.get("authors", [])]
                    authors_str = ", ".join(authors[:4])
                    if len(authors) > 4:
                        authors_str += " et al."
                    year_str = f" ({p.get('publication_year', '')})" if p.get("publication_year") else ""
                    pdf = self._pdf_link(pid, p.get("doi", ""))
                    lines.append(f"  - \"{p.get('title', '')}\"{year_str} — {authors_str}{pdf}")
            lines.append("")

        return "\n".join(lines)

    def _build_shared_topics_factual_section(self, user_message: str, show_banners: bool = True) -> str:
        """Build a user-facing factual section for shared topic queries.

        Returns markdown text generated PROGRAMMATICALLY from structured data.
        """
        uni_filter = self._detect_university_filter(user_message)
        if not uni_filter:
            return ""
        val = uni_filter.get("university_acronym")
        if isinstance(val, dict) and "$in" in val:
            target_acronyms = set(val["$in"])
        else:
            return ""

        if len(target_acronyms) < 2:
            return ""

        min_concept_score = 0.3

        # Collect concepts per university with their papers
        concept_unis = {}
        for acronym in target_acronyms:
            papers = self._all_uni_papers.get(acronym, [])
            for p in papers:
                for c in p.get("concepts", []):
                    if c.get("score", 0) < min_concept_score:
                        continue
                    cname = c["name"]
                    if cname not in concept_unis:
                        concept_unis[cname] = {}
                    if acronym not in concept_unis[cname]:
                        concept_unis[cname][acronym] = []
                    concept_unis[cname][acronym].append(p)

        # Filter to concepts present in ALL target universities
        shared_concepts = {}
        for cname, unis_papers in concept_unis.items():
            if target_acronyms.issubset(unis_papers.keys()):
                total = sum(len(ps) for ps in unis_papers.values())
                shared_concepts[cname] = (unis_papers, total)

        acronyms_str = " and ".join(sorted(target_acronyms))

        if not shared_concepts:
            return f"No shared research topics found between {acronyms_str} in the UNINOVIS database."

        # Sort by total papers descending
        sorted_concepts = sorted(shared_concepts.items(), key=lambda x: x[1][1], reverse=True)

        # Filter out overly generic concepts
        generic_concepts = {
            "computer science", "mathematics", "business", "engineering",
            "political science", "sociology", "psychology", "philosophy",
            "economics", "medicine", "biology",
        }
        sorted_concepts = [
            (cname, data) for cname, data in sorted_concepts
            if cname.lower() not in generic_concepts
        ][:15]

        total_papers = len({
            p.get("id", id(p))
            for _, (unis_papers, _) in sorted_concepts
            for ps in unis_papers.values()
            for p in ps
        })

        lines = []
        if show_banners:
            lines.append(self._banner_verified(
                f"Shared research topics between {acronyms_str} from the UNINOVIS database (no AI involved)."
            ))
        lines.append(f'### Shared Research Topics between {acronyms_str} ({len(sorted_concepts)} topics, {total_papers} unique papers)')
        lines.append('')

        seen_paper_ids = set()
        for cname, (unis_papers, total) in sorted_concepts:
            lines.append(f"**{cname}** ({total} papers)")
            for acronym in sorted(target_acronyms):
                papers = unis_papers.get(acronym, [])
                if not papers:
                    continue
                uni_name = self.UNIVERSITY_COORDS.get(acronym, {}).get("name", acronym)
                lines.append(f"- *{acronym}* ({len(papers)}):")
                for p in papers:
                    pid = p.get("id", "")
                    title = p.get("title", "")
                    # Deduplicate papers appearing under multiple concepts
                    display_key = pid or title
                    if display_key in seen_paper_ids:
                        continue
                    seen_paper_ids.add(display_key)
                    authors = [a.get("name", "") for a in p.get("authors", [])]
                    authors_str = ", ".join(authors[:4])
                    if len(authors) > 4:
                        authors_str += " et al."
                    year_str = f" ({p.get('publication_year', '')})" if p.get("publication_year") else ""
                    pdf = self._pdf_link(pid, p.get("doi", ""))
                    lines.append(f"  - \"{title}\"{year_str} — {authors_str}{pdf}")
            lines.append("")

        return "\n".join(lines)

    def _build_affiliation_context(self, user_message: str) -> str:
        """Detect queries asking for researchers affiliated to a specific institution.
        Returns a clean list of researcher names and their affiliations."""
        if not self._researchers_by_uni:
            return ""

        msg_lower = user_message.lower()

        # Trigger on affiliation-related queries OR "researchers from/at <university>"
        affiliation_keywords = ["affiliated", "affiliation", "work at", "works at",
                                "working at", "belong to", "belongs to", "member of",
                                "members of", "employed by", "employed at"]
        researcher_keywords = ["researcher", "researchers", "author", "authors",
                               "scientist", "scientists", "professor", "professors",
                               "academic", "academics"]
        has_affiliation_kw = any(kw in msg_lower for kw in affiliation_keywords)
        has_researcher_kw = any(kw in msg_lower for kw in researcher_keywords)

        # Detect which institution the user is asking about
        target_institution = None
        target_acronym = None
        universities = self._config.get("universities", {})
        for acronym, info in universities.items():
            full_name = info.get("name", "").lower()
            if full_name and full_name in msg_lower:
                target_institution = full_name
                target_acronym = acronym
                break
            if re.search(r'\b' + re.escape(acronym) + r'\b', msg_lower, re.IGNORECASE):
                target_institution = info.get("name", acronym).lower()
                target_acronym = acronym
                break

        # Trigger if: (affiliation keywords) OR (researcher keywords + university detected)
        if not has_affiliation_kw and not (has_researcher_kw and target_acronym):
            return ""

        if not target_acronym:
            return ""

        # Collect researchers whose affiliations include the target institution
        matching_confirmed = []
        matching_unconfirmed = []
        for acronym, researchers in self._researchers_by_uni.items():
            for r in researchers:
                for aff in r.get("affiliations", []):
                    if target_institution in aff.lower():
                        entry = {
                            "name": r["name"],
                            "affiliations": r.get("affiliations", []),
                            "paper_count": r["paper_count"],
                            "uni_acronym": acronym,
                            "status": r.get("affiliation_status", "confirmed"),
                        }
                        if entry["status"] == "confirmed":
                            matching_confirmed.append(entry)
                        else:
                            matching_unconfirmed.append(entry)
                        break

        if not matching_confirmed and not matching_unconfirmed:
            return ""

        uni_info = universities.get(target_acronym, {})
        institution_name = uni_info.get("name", target_acronym)
        total = len(matching_confirmed) + len(matching_unconfirmed)

        lines = [f"RESEARCHERS AFFILIATED TO {institution_name.upper()} ({total} researchers):"]
        lines.append("Present as a simple list. Do NOT group by university or list individual papers unless the user specifically asks.")
        lines.append("Researchers marked [unconfirmed] have only 1 paper and multiple affiliations -- their affiliation needs verification.")

        if matching_confirmed:
            lines.append(f"\nConfirmed ({len(matching_confirmed)}):")
            for m in sorted(matching_confirmed, key=lambda x: x["name"]):
                affs_str = ", ".join(m["affiliations"][:5])
                lines.append(f"  - {m['name']} ({m['paper_count']} paper(s)) -- Affiliations: {affs_str}")

        if matching_unconfirmed:
            lines.append(f"\nUnconfirmed -- affiliation needs verification ({len(matching_unconfirmed)}):")
            for m in sorted(matching_unconfirmed, key=lambda x: x["name"]):
                affs_str = ", ".join(m["affiliations"][:5])
                lines.append(f"  - [unconfirmed] {m['name']} ({m['paper_count']} paper(s)) -- Affiliations: {affs_str}")

        return "\n".join(lines)

    def _build_researcher_context(self, user_message: str) -> str:
        """Search researchers.json for names mentioned in the query.
        Returns structured data about matching UNINOVIS researchers."""
        if not self._researchers_by_uni:
            return ""

        msg_lower = user_message.lower()
        matches = []

        for acronym, researchers in self._researchers_by_uni.items():
            for r in researchers:
                name = r["name"]
                # Match full name or surname (last word of name)
                name_parts = name.split()
                surname = name_parts[-1] if name_parts else ""
                if (name.lower() in msg_lower or
                        (len(surname) > 3 and surname.lower() in msg_lower)):
                    uni_info = self._config.get("universities", {}).get(acronym, {})
                    matches.append({
                        "name": name,
                        "acronym": acronym,
                        "university": uni_info.get("name", acronym),
                        "paper_count": r["paper_count"],
                        "papers": r["papers"],
                        "topics": r["topics"],
                        "affiliations": r.get("affiliations", []),
                        "affiliation_status": r.get("affiliation_status", "confirmed"),
                    })

        if not matches:
            return ""

        # Build project lookup: search project_docs for researcher names
        project_docs_dir = os.path.join(self._agent_dir, "data", "project_docs")
        researcher_projects = {}  # name_lower -> list of project info dicts
        if os.path.exists(project_docs_dir):
            for fname in os.listdir(project_docs_dir):
                if not fname.endswith('.md'):
                    continue
                fpath = os.path.join(project_docs_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    content_lower = content.lower()
                    # Extract project title and grant ID
                    title_match = re.search(r'^# (.+)', content)
                    grant_match = re.search(r'\*\*Grant ID:\*\*\s*(\S+)', content)
                    proj_title = title_match.group(1).strip() if title_match else fname
                    grant_id = grant_match.group(1) if grant_match else ""
                    # Check if any matched researcher appears in the project
                    for m in matches:
                        name_lower = m["name"].lower()
                        # Match full name or surname in project participants
                        surname = m["name"].split()[-1].lower() if m["name"].split() else ""
                        if name_lower in content_lower or (len(surname) > 3 and surname in content_lower):
                            if name_lower not in researcher_projects:
                                researcher_projects[name_lower] = []
                            researcher_projects[name_lower].append({
                                "title": proj_title,
                                "grant_id": grant_id,
                            })
                except Exception:
                    pass

        # Build paper-author lookup for attribution verification
        paper_authors = {}  # paper_id -> set of lowercased author names
        for uni_papers in self._all_uni_papers.values():
            for paper in uni_papers:
                pid = paper.get("id", "")
                if pid:
                    authors = set()
                    for a in paper.get("authors", []):
                        aname = a.get("name", "") if isinstance(a, dict) else str(a)
                        if aname:
                            authors.add(aname.lower())
                    paper_authors[pid] = authors

        lines = [f"RESEARCHER LOOKUP RESULTS ({len(matches)} match(es)):"]
        lines.append("This data is authoritative. Use ONLY this information when answering about these researchers. Do NOT invent or reassign papers or projects.")
        for m in matches:
            status_tag = " [unconfirmed affiliation]" if m.get("affiliation_status") == "unconfirmed" else ""
            lines.append(f"\n{m['name']} -- {m['acronym']} ({m['university']}){status_tag}")

            # Verify paper attributions against actual author lists
            verified_papers = []
            unverified_papers = []
            researcher_name_lower = m["name"].lower()
            researcher_surname = m["name"].split()[-1].lower() if m["name"].split() else ""
            for p in m["papers"]:
                pid = p.get("id", "")
                authors_set = paper_authors.get(pid, set())
                # Check each author individually — no cross-author substring matching
                is_author = False
                for author in authors_set:
                    # Full name match (e.g. "ignacio moreno-torres" in "ignacio moreno-torres")
                    if researcher_name_lower in author or author in researcher_name_lower:
                        is_author = True
                        break
                    # Surname match (e.g. "moreno-torres" in "i. moreno-torres")
                    if researcher_surname and researcher_surname in author:
                        is_author = True
                        break
                if is_author or not authors_set:
                    verified_papers.append(p)
                else:
                    unverified_papers.append(p)

            if verified_papers:
                lines.append(f"  Papers ({len(verified_papers)} verified):")
                for p in verified_papers:
                    year_str = f" ({p['year']})" if p.get("year") else ""
                    pdf = self._pdf_link(p.get("id", ""), p.get("doi", ""))
                    lines.append(f"    - \"{p['title']}\"{year_str}{pdf}")
            if unverified_papers:
                lines.append(f"  ⚠️ Papers with UNVERIFIED attribution ({len(unverified_papers)}) — researcher name not found in author list:")
                for p in unverified_papers:
                    year_str = f" ({p['year']})" if p.get("year") else ""
                    pdf = self._pdf_link(p.get("id", ""), p.get("doi", ""))
                    lines.append(f"    - ⚠️ \"{p['title']}\"{year_str}{pdf} [ATTRIBUTION NOT VERIFIED]")

            # Add projects
            name_lower = m["name"].lower()
            projs = researcher_projects.get(name_lower, [])
            if projs:
                lines.append(f"  Research projects ({len(projs)}):")
                for proj in projs:
                    grant_str = f" (Grant: {proj['grant_id']})" if proj["grant_id"] else ""
                    lines.append(f"    - \"{proj['title']}\"{grant_str}")
            if m["affiliations"]:
                lines.append(f"  Affiliations: {', '.join(m['affiliations'][:5])}")
            if m["topics"]:
                lines.append(f"  Topics: {', '.join(m['topics'][:10])}")

        return "\n".join(lines)

    def _extract_topic(self, user_message: str) -> str:
        """Extract a research topic from the user's message, if any."""
        msg_lower = user_message.lower()

        # Phrases after which a topic typically appears
        topic_phrases = [
            "papers on", "papers about", "publications on", "publications about",
            "researchers on", "researchers in", "research on", "research about",
            "projects on", "projects about", "projects related to",
            "grants on", "grants about", "funding on", "funding for",
            "working on", "works on", "work on", "interested in", "interest in", "interest on",
            "figure of", "figure about", "figure with",
            "list of papers", "list of researchers", "list of publications",
            "list of projects", "list of grants",
            "studies on", "studies about", "studies per",
            "related with", "related to", "topics on", "topics about",
            "number of", "focused on",
        ]

        # Try to extract topic from after a matching phrase
        topic = None
        for t in sorted(topic_phrases, key=len, reverse=True):
            idx = msg_lower.find(t)
            if idx >= 0:
                topic = user_message[idx + len(t):].strip().strip('"\'.,!?')
                break

        # Fallback: if no phrase matched, treat the entire message as a potential
        # bare topic phrase (e.g. "Aging and wellbeing technologies").
        # Only accept short noun-phrase-like messages (no question words, no verbs).
        if not topic or len(topic) < 2:
            bare = user_message.strip().strip('"\'.,!?')
            bare_lower = bare.lower()
            word_count = len(bare.split())
            has_question_word = re.match(
                r'^(what|who|how|why|when|where|which|can|do|does|is|are|list|show|tell|describe)\b',
                bare_lower,
            )
            if 2 <= word_count <= 6 and not has_question_word:
                topic = bare
            else:
                return ""

        # Remove trailing university references (acronyms and full names) and filler words
        universities = self._config.get("universities", {})
        for acronym, info in universities.items():
            topic = re.sub(r'\b' + re.escape(acronym) + r'\b.*$', '', topic, flags=re.IGNORECASE).strip()
            full_name = info.get("name", "")
            if full_name:
                topic = re.sub(re.escape(full_name) + r'.*$', '', topic, flags=re.IGNORECASE).strip()
        # Remove trailing filler like "per partner", "per university", "from", "at", "in", "by"
        topic = re.sub(r'\s+per\s+\w+$', '', topic, flags=re.IGNORECASE).strip()
        topic = re.sub(r'\s+(?:from|at|in|by|for|of)$', '', topic, flags=re.IGNORECASE).strip()
        topic = topic.strip('"\'.,!?')

        if not topic or len(topic) < 2:
            return ""

        # Filter out non-topic extractions (figure/map structural words)
        # Strip year references, filler words, and structural phrases before checking
        topic_for_check = re.sub(r'\b(in\s+)?(the\s+)?year\s+\d{4}\b', '', topic, flags=re.IGNORECASE).strip()
        topic_for_check = re.sub(r'\b\d{4}\b', '', topic_for_check).strip().strip('.,!?')
        # Remove common structural/filler phrases
        structural_words = [
            r'\b(all|the|some|any|every)\b',
            r'\b(among|between|across|within|per)\b',
            r'\b(partners?|universities?|institutions?)\b',
            r'\b(publications?|papers?|articles?|studies|collaborations?|projects?|grants?|research)\b',
        ]
        check = topic_for_check.lower()
        for pattern in structural_words:
            check = re.sub(pattern, '', check, flags=re.IGNORECASE)
        check = re.sub(r'\s+', ' ', check).strip().strip('.,!?')
        if not check:
            return ""

        return topic

    def _pdf_link(self, paper_id: str, doi: str = "") -> str:
        """Return the paper ID and a PDF link (if the PDF exists locally).

        Always includes the paper ID so the LLM can cite it.
        When the PDF exists locally, adds a clickable PDF link.
        When it does not, shows 'PDF not in database' and a DOI link if available.
        """
        if not paper_id:
            return ""
        filename = f"{paper_id}.pdf"
        docs_path = os.path.join(self._agent_dir, "data", "docs", filename)
        if os.path.exists(docs_path):
            agent_id = self._config.get("agent_id", "responsible_ai")
            return f" (ID: {paper_id}) [PDF](/api/agents/{agent_id}/pdf/{filename})"
        # PDF not available — show informative text + DOI link if available
        suffix = f" (ID: {paper_id}) — PDF not in database."
        if doi:
            suffix += f' <a href="{doi}" target="_blank">Link to Internet paper</a>'
        return suffix

    def _build_paper_id_index(self) -> dict:
        """Build a paper_id → doi lookup from cached papers data.

        Returns dict like {"W4400460850": "https://doi.org/...", ...}.
        Cached after first call.
        """
        if hasattr(self, '_paper_id_doi_index'):
            return self._paper_id_doi_index
        index = {}
        for papers in self._all_uni_papers.values():
            for p in papers:
                pid = p.get("id", "")
                doi = p.get("doi", "")
                if pid:
                    index[pid] = doi
        self._paper_id_doi_index = index
        return index

    def _inject_paper_links(self, text: str) -> str:
        """Post-process LLM output to inject DOI/PDF links for paper IDs that lack them.

        Scans for paper IDs (W followed by digits) and checks if they already
        have an adjacent link. If not, appends the appropriate link.
        """
        index = self._build_paper_id_index()
        if not index:
            return text

        def _replace_bare_id(m):
            """Replace a bare paper ID mention with one that includes a link."""
            full_match = m.group(0)
            paper_id = m.group(1)
            if paper_id not in index:
                return full_match
            # Check if there's already a link nearby (within the same line)
            # by looking at what follows the match
            after = text[m.end():m.end() + 200]
            # If there's already a PDF link, DOI link, or "Link to Internet paper" nearby, skip
            if re.match(r'[^<\n]{0,50}(?:<a\s|href=|\[PDF\]|\[Link)', after):
                return full_match
            # Generate the link — extract just the link portion (skip the "(ID: ...)" part
            # since the ID is already present in the text)
            link = self._pdf_link(paper_id, index[paper_id])
            # _pdf_link returns " (ID: W...) [PDF](...)" or " (ID: W...) — PDF not in database. <a...>"
            # Strip the "(ID: ...)" prefix since the ID already appears in the text
            link_only = re.sub(r'^\s*\(ID:\s*\w+\)\s*', '', link).strip()
            if link_only:
                return full_match + " " + link_only
            return full_match

        # Match paper IDs in patterns like "(ID: W1234)" or bare "W1234"
        # Capture optional surrounding (ID: ...) wrapper to replace the whole thing
        # but NOT inside existing href/src attributes or markdown links
        result = re.sub(
            r'(?<!\/)(?<!=")(?<!\.pdf)(?:\(ID:\s*)?\b(W\d{5,})\b(?:\s*\))?(?!\.pdf)(?![^<]*<\/a>)',
            _replace_bare_id,
            text,
        )
        return result

    # ------------------------------------------------------------------
    # Paper search / map data methods
    # ------------------------------------------------------------------

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

    def search_papers_by_topic(self, topic: str, min_score: float = 0.3) -> dict:
        """Search all university paper JSON files for papers matching a topic.

        Matching strategy (in order of priority):
        0. If the topic matches the agent's research_topic (the umbrella topic
           covering all papers in the database), return ALL papers without filtering.
        1. Concept tag match: the full topic phrase appears in a concept name
           or the concept name appears in the topic (score >= min_score).
        2. Title/abstract match: the full topic phrase appears in the title or abstract.
        3. Keyword fallback: if the above yield zero results, splits the topic into
           keywords and checks if ALL keywords appear in concepts, title, or abstract.

        Returns a dict: {acronym: {"name": ..., "country": ..., "lat": ..., "lon": ..., "count": N, "papers": [...]}}
        """
        topic_lower = topic.lower()

        # If the topic matches the agent's umbrella research_topic, return all papers
        # (all papers in the database are already on this topic by construction)
        research_topic_raw = self._config.get("research_topic", "")
        if research_topic_raw:
            # Extract the core topic (before any parenthetical subtopic examples)
            rt_full = research_topic_raw.lower()
            rt_core = re.split(r'\(', rt_full)[0].strip().rstrip(',').strip()
            # Build set of umbrella phrases from the CORE topic only
            # e.g. "ai & responsibility" → "responsible ai", "ai responsibility", etc.
            umbrella_phrases = {rt_core}
            # Extract significant words from core (not "ai", "and", "&")
            core_words = [w for w in re.split(r'\W+', rt_core) if w and len(w) > 3]
            # Generate adjective/noun variants for each significant word
            for w in core_words:
                variants = {w}
                if w.endswith("bility"):
                    variants.add(w[:-6] + "ble")         # responsibility → responsible
                elif w.endswith("ity"):
                    variants.add(w[:-3] + "e")           # e.g. creativity → creative
                elif w.endswith("ble"):
                    variants.add(w[:-3] + "bility")      # responsible → responsibility
                elif w.endswith("ness"):
                    variants.add(w[:-4])                  # fairness → fair
                elif w.endswith("tion"):
                    variants.add(w[:-4] + "te")           # automation → automate
                for v in list(variants):
                    umbrella_phrases.add(f"ai {v}")
                    umbrella_phrases.add(f"{v} ai")
                    umbrella_phrases.add(f"ai & {v}")
                    umbrella_phrases.add(f"ai and {v}")

            is_umbrella = topic_lower in umbrella_phrases or any(
                topic_lower == p or topic_lower in p or p in topic_lower
                for p in umbrella_phrases if len(p) > 5
            )
            if is_umbrella:
                # Return all papers — no filtering needed
                output = {}
                for acronym, papers in self._all_uni_papers.items():
                    formatted_papers = []
                    for paper in papers:
                        formatted_papers.append({
                            "id": paper.get("id", ""),
                            "title": paper.get("title", ""),
                            "authors": [a.get("name", "") for a in paper.get("authors", [])],
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

        stop_words = {"the", "a", "an", "in", "on", "of", "and", "or", "for", "to", "is", "are", "was", "were", "by", "with", "from", "at", "as"}
        # Keep domain-critical short terms like "ai", "xai", "ml" that would
        # otherwise be dropped by the len>2 filter
        keep_words = {"ai", "xai", "ml", "nlp", "cv", "rl", "llm"}
        topic_words = [w for w in re.split(r'\W+', topic_lower) if w and w not in stop_words and (len(w) > 2 or w in keep_words)]

        # Use cached papers data
        all_uni_papers = self._all_uni_papers

        # Combine strict and keyword matching (deduplicated by paper id)
        # Tag each paper with match strength for downstream researcher filtering
        results = {}
        for acronym, papers in all_uni_papers.items():
            seen_ids = set()
            matching = []  # list of (paper, is_strong_match)
            # Strict matches first (higher priority) — strong match
            for p in papers:
                if self._match_paper_strict(p, topic_lower, min_score):
                    pid = p.get("id", id(p))
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        matching.append((p, True))
            # Then keyword matches — check title/concepts for strong vs weak
            if topic_words:
                for p in papers:
                    pid = p.get("id", id(p))
                    if pid not in seen_ids and self._match_paper_keywords(p, topic_lower, min_score, topic_words):
                        seen_ids.add(pid)
                        # Strong if topic words appear in title or concepts
                        title = p.get("title", "").lower()
                        concept_text = " ".join(
                            c.get("name", "").lower()
                            for c in p.get("concepts", [])
                            if c.get("score", 0) >= min_score
                        )
                        strong = self._all_keywords_in_text(topic_words, title) or \
                                 self._all_keywords_in_text(topic_words, concept_text) or \
                                 self._all_keywords_in_text(topic_words, concept_text + " " + title)
                        matching.append((p, strong))
            results[acronym] = matching

        # Build output
        output = {}
        for acronym, matching_papers in results.items():
            formatted_papers = []
            for paper, strong in matching_papers:
                formatted_papers.append({
                    "id": paper.get("id", ""),
                    "title": paper.get("title", ""),
                    "authors": [a.get("name", "") for a in paper.get("authors", [])],
                    "year": paper.get("publication_year"),
                    "doi": paper.get("doi", ""),
                    "cited_by_count": paper.get("cited_by_count", 0),
                    "strong_topic_match": strong,
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
    def _match_paper_strict(paper, topic_lower, min_score=0.3):
        """Match by full phrase in concepts, title, or abstract.

        For concept matching, require that the concept covers at least half
        of the topic words (not just a single word) to avoid overly broad
        matches like "robotics" matching all papers when the topic is
        "Lego robotics".
        """
        topic_words = set(topic_lower.split())
        for concept in paper.get("concepts", []):
            concept_name = concept.get("name", "").lower()
            if concept.get("score", 0) < min_score:
                continue
            # Full topic appears inside concept name
            if topic_lower in concept_name:
                return True
            # Concept name appears inside topic — but only if the concept
            # covers a significant portion of the topic (>= 50% of words)
            if concept_name in topic_lower:
                concept_words = set(concept_name.split())
                if len(concept_words) > len(topic_words) / 2:
                    return True
        title = paper.get("title", "").lower()
        abstract = (paper.get("abstract") or "").lower()
        text = title + " " + abstract
        if topic_lower in text:
            return True
        return False

    # Abbreviation expansions for keyword matching.
    # When a keyword is an abbreviation, also accept its full form.
    _KEYWORD_EXPANSIONS = {
        "ai": "artificial intelligence",
        "xai": "explainable artificial intelligence",
        "ml": "machine learning",
        "nlp": "natural language processing",
        "cv": "computer vision",
        "rl": "reinforcement learning",
        "llm": "large language model",
    }

    @staticmethod
    def _keyword_in_text(word, text):
        """Check if a keyword appears in text, also trying abbreviation expansions."""
        if word in text:
            return True
        expansion = MetadataRAGMixin._KEYWORD_EXPANSIONS.get(word)
        if expansion and expansion in text:
            return True
        return False

    @staticmethod
    def _all_keywords_in_text(topic_words, text):
        """Check if ALL keywords appear in text (with abbreviation expansion)."""
        return all(MetadataRAGMixin._keyword_in_text(w, text) for w in topic_words)

    @staticmethod
    def _match_paper_keywords(paper, topic_lower, min_score=0.3, topic_words=None):
        """Fallback: match if ALL keywords appear somewhere in the paper.

        Priority: concepts first, then title only.  Abstract is only used
        when at least one keyword already appears in concepts or title,
        to avoid matching papers that mention a keyword incidentally
        (e.g. "ethics committee approval" matching an "AI ethics" query).
        """
        if topic_words is None:
            stop_words = {"the", "a", "an", "in", "on", "of", "and", "or", "for", "to", "is", "are", "was", "were", "by", "with", "from", "at", "as"}
            keep_words = {"ai", "xai", "ml", "nlp", "cv", "rl", "llm"}
            topic_words = [w for w in re.split(r'\W+', topic_lower) if w and w not in stop_words and (len(w) > 2 or w in keep_words)]
        if not topic_words:
            return False

        _kw = MetadataRAGMixin._all_keywords_in_text

        # 1. All keywords in a single concept → strong match
        for concept in paper.get("concepts", []):
            concept_name = concept.get("name", "").lower()
            if concept.get("score", 0) < min_score:
                continue
            if _kw(topic_words, concept_name):
                return True

        # 2. All keywords in the title → strong match
        title = paper.get("title", "").lower()
        if _kw(topic_words, title):
            return True

        # 3. Keywords split across concepts + title → acceptable match
        concept_text = " ".join(
            c.get("name", "").lower()
            for c in paper.get("concepts", [])
            if c.get("score", 0) >= min_score
        )
        combined = concept_text + " " + title
        if _kw(topic_words, combined):
            return True

        # 4. Keywords in title/concepts + abstract (weaker match — paper is
        #    included but flagged as not a strong topic match for researcher
        #    filtering).  Only for topics with 3+ keywords, and only when
        #    at least half the keywords already appear in title/concepts.
        #    Disabled for short topics (≤2 keywords) because common words
        #    like "AI" trivially anchor, causing false positives from
        #    incidental abstract mentions (e.g. "ethics committee approval"
        #    matching an "AI ethics" query).
        if len(topic_words) >= 3:
            anchor_text = title + " " + concept_text
            anchor_hits = sum(1 for w in topic_words if MetadataRAGMixin._keyword_in_text(w, anchor_text))
            if anchor_hits >= len(topic_words) / 2 and anchor_hits < len(topic_words):
                abstract = (paper.get("abstract") or "").lower()
                if _kw(topic_words, anchor_text + " " + abstract):
                    return True

        return False

    # ------------------------------------------------------------------
    # Project search / map data methods
    # ------------------------------------------------------------------

    @staticmethod
    def _project_active_in_year(proj: dict, year: int) -> bool:
        """Check if a project was active during a given year."""
        start = proj.get("start_year")
        end = proj.get("end_year")
        if start is None:
            return False
        if end is None:
            end = start
        return start <= year <= end

    @staticmethod
    def _format_project(proj: dict) -> dict:
        """Format a project dict for API output."""
        return {
            "title": proj.get("title", ""),
            "grant_id": proj.get("grant_id", ""),
            "funder": proj.get("funder", ""),
            "programme": proj.get("programme", ""),
            "period": proj.get("period", ""),
            "status": proj.get("status", ""),
            "total_cost": proj.get("total_cost", ""),
            "keywords": proj.get("keywords", []),
            "participants": proj.get("participants", []),
            "website": proj.get("website", ""),
            "uninovis_researchers": proj.get("uninovis_researchers", []),
        }

    def _empty_project_results(self) -> dict:
        """Return an empty results dict with all universities initialized."""
        results = {}
        for acronym in self._config.get("universities", {}).keys():
            coords = self.UNIVERSITY_COORDS.get(acronym, {})
            results[acronym] = {
                "name": coords.get("name", acronym),
                "country": coords.get("country", ""),
                "lat": coords.get("lat", 0),
                "lon": coords.get("lon", 0),
                "count": 0,
                "projects": [],
            }
        return results

    def get_all_projects_by_university(self, year: int = None) -> dict:
        """Return all projects grouped by university, optionally filtered by year.

        Args:
            year: If provided, only include projects active during this year.

        Returns a dict: {acronym: {"name": ..., "country": ..., "lat": ..., "lon": ..., "count": N, "projects": [...]}}
        """
        results = self._empty_project_results()

        for acronym, projects_list in self._all_uni_projects.items():
            if acronym not in results:
                coords = self.UNIVERSITY_COORDS.get(acronym, {})
                results[acronym] = {
                    "name": coords.get("name", acronym),
                    "country": coords.get("country", ""),
                    "lat": coords.get("lat", 0),
                    "lon": coords.get("lon", 0),
                    "count": 0,
                    "projects": [],
                }
            formatted = []
            for proj in projects_list:
                if year is not None and not self._project_active_in_year(proj, year):
                    continue
                formatted.append(self._format_project(proj))
            results[acronym]["projects"] = formatted
            results[acronym]["count"] = len(formatted)

        return results

    def search_projects_by_topic(self, topic: str, year: int = None) -> dict:
        """Search all projects for those matching a topic, optionally filtered by year.

        Matching: checks if the topic (or all topic keywords) appear in
        the project title, summary, keywords, or programme.

        Args:
            topic: Search topic.
            year: If provided, only include projects active during this year.

        Returns a dict: {acronym: {"name": ..., "country": ..., "lat": ..., "lon": ..., "count": N, "projects": [...]}}
        """
        topic_lower = topic.lower()
        stop_words = {"the", "a", "an", "in", "on", "of", "and", "or", "for", "to", "is", "are", "was", "were", "by", "with", "from", "at", "as"}
        topic_words = [w for w in re.split(r'\W+', topic_lower) if w and w not in stop_words and len(w) > 2]

        results = self._empty_project_results()

        for acronym, projects_list in self._all_uni_projects.items():
            if acronym not in results:
                coords = self.UNIVERSITY_COORDS.get(acronym, {})
                results[acronym] = {
                    "name": coords.get("name", acronym),
                    "country": coords.get("country", ""),
                    "lat": coords.get("lat", 0),
                    "lon": coords.get("lon", 0),
                    "count": 0,
                    "projects": [],
                }
            matching = []
            for proj in projects_list:
                if year is not None and not self._project_active_in_year(proj, year):
                    continue
                searchable = " ".join([
                    proj.get("title", ""),
                    proj.get("summary", ""),
                    " ".join(proj.get("keywords", [])),
                    proj.get("programme", ""),
                ]).lower()

                # Full phrase match first
                if topic_lower in searchable:
                    matching.append(proj)
                    continue
                # Keyword fallback: all topic keywords must appear
                if topic_words and all(w in searchable for w in topic_words):
                    matching.append(proj)

            formatted = [self._format_project(p) for p in matching]
            results[acronym]["projects"] = formatted
            results[acronym]["count"] = len(formatted)

        return results

    @staticmethod
    def build_project_map_html(results_json: str, topic_escaped: str) -> str:
        """Build the HTML for the interactive project map (similar to topic map but for projects)."""
        return ("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNINOVIS Projects Map: __TOPIC__</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f8fafc; color: #1e293b; }
        .header { background: #1e293b; padding: 16px 24px; border-bottom: 3px solid #059669; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 1.3em; color: #ffffff; font-weight: 600; }
        .header h1 span { color: #6ee7b7; }
        .header p { font-size: 0.9em; color: #94a3b8; margin-top: 2px; }
        .header-left { flex: 1; }
        .header-badge { background: #059669; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 0.8em; font-weight: 600; letter-spacing: 0.5px; }
        #map { height: calc(100vh - 72px); width: 100%; }
        .uni-popup { min-width: 300px; }
        .uni-popup h3 { color: #1e293b; margin-bottom: 4px; font-size: 1.1em; font-weight: 600; }
        .uni-popup .country { color: #64748b; font-size: 0.85em; margin-bottom: 10px; }
        .uni-popup .count { font-size: 1.3em; font-weight: 700; color: #059669; margin-bottom: 10px; padding: 6px 0; border-bottom: 2px solid #e2e8f0; }
        .uni-popup .projects-list { max-height: 280px; overflow-y: auto; font-size: 0.82em; }
        .uni-popup .project-item { padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
        .uni-popup .project-item:last-child { border-bottom: none; }
        .uni-popup .project-title { font-weight: 500; color: #1e293b; }
        .uni-popup .project-meta { color: #64748b; font-size: 0.9em; margin-top: 2px; }
        .uni-popup a { color: #059669; text-decoration: none; }
        .uni-popup a:hover { text-decoration: underline; }
        .legend { background: #ffffff; padding: 14px 18px; border-radius: 10px; color: #1e293b; font-size: 0.85em; line-height: 1.7; box-shadow: 0 2px 8px rgba(0,0,0,0.12); border: 1px solid #e2e8f0; }
        .legend h4 { margin-bottom: 6px; color: #1e293b; font-weight: 600; font-size: 0.95em; }
        .legend .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
        .legend .dot-has { background: #059669; }
        .legend .dot-none { background: #cbd5e1; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>UNINOVIS Projects Map: <span>"__TOPIC__"</span></h1>
            <p id="summary"></p>
        </div>
        <div class="header-badge">UNINOVIS</div>
    </div>
    <div id="map"></div>
    <script>
        const data = __DATA__;
        const topic = "__TOPIC__";

        // Summary
        let totalProjects = 0;
        let uniWithProjects = 0;
        Object.values(data).forEach(u => {
            totalProjects += u.count;
            if (u.count > 0) uniWithProjects++;
        });
        document.getElementById('summary').textContent =
            totalProjects + ' project(s) found across ' + uniWithProjects + ' of ' + Object.keys(data).length + ' UNINOVIS universities';

        // Map focused tightly on UNINOVIS universities
        const uniBounds = L.latLngBounds(
            L.latLng(35, -6),
            L.latLng(63, 26)
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
            const color = uni.count > 0 ? '#059669' : '#cbd5e1';
            const borderColor = uni.count > 0 ? '#047857' : '#94a3b8';
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
            let projectsHtml = '';
            if (uni.projects && uni.projects.length > 0) {
                projectsHtml = '<div class="projects-list">';
                uni.projects.forEach(p => {
                    const keywords = p.keywords ? p.keywords.join(', ') : '';
                    projectsHtml += '<div class="project-item">'
                        + '<div class="project-title">' + (p.title || 'Untitled') + '</div>'
                        + '<div class="project-meta">'
                        + (p.grant_id ? 'Grant: ' + p.grant_id : '')
                        + (p.funder ? ' &mdash; ' + p.funder : '')
                        + (p.period ? ' &mdash; ' + p.period : '')
                        + (p.status ? ' (' + p.status + ')' : '')
                        + '</div>'
                        + (p.total_cost ? '<div class="project-meta">Budget: ' + p.total_cost + '</div>' : '')
                        + (keywords ? '<div class="project-meta">Keywords: ' + keywords + '</div>' : '')
                        + '</div>';
                });
                projectsHtml += '</div>';
            } else {
                projectsHtml = '<p style="color:#94a3b8;font-style:italic;">No projects found for this topic.</p>';
            }

            marker.bindPopup(
                '<div class="uni-popup">'
                + '<h3>' + acronym + ' &mdash; ' + uni.name + '</h3>'
                + '<div class="country">' + uni.country + '</div>'
                + '<div class="count">' + uni.count + ' project(s) on "' + topic + '"</div>'
                + projectsHtml
                + '</div>',
                { maxWidth: 400 }
            );
        });

        // Legend
        const legend = L.control({position: 'bottomright'});
        legend.onAdd = function() {
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<h4>UNINOVIS Projects Map</h4>'
                + '<div><span class="dot dot-has"></span> Has projects (size = count)</div>'
                + '<div><span class="dot dot-none"></span> No projects found</div>';
            return div;
        };
        legend.addTo(map);
    </script>
</body>
</html>"""
            .replace("__DATA__", results_json)
            .replace("__TOPIC__", topic_escaped)
        )

    def get_top_topics(self, min_score: float = 0.3, top_n: int = 30) -> list:
        """Aggregate concepts/topics across all university papers.

        Returns a list of (topic_name, count, universities) sorted by frequency.
        Only considers concepts with score >= min_score.
        Filters out overly generic academic disciplines.
        """
        from collections import Counter, defaultdict
        topic_counts = Counter()
        topic_universities = defaultdict(set)

        for acronym, papers in self._all_uni_papers.items():
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

    def get_all_papers_by_university(self, year: int = None) -> dict:
        """Return all papers grouped by university, optionally filtered by year.

        Args:
            year: If provided, only include papers from this publication year.

        Returns a dict: {acronym: {"name": ..., "country": ..., "lat": ..., "lon": ..., "count": N, "papers": [...]}}
        """
        data_dir = os.path.join(self._agent_dir, "data")
        results = {}

        # Use cached papers data, fall back to per-university *_papers.json
        if self._all_uni_papers:
            for acronym, papers_list in self._all_uni_papers.items():
                all_papers = []
                for paper in papers_list:
                    if year is not None and paper.get("publication_year") != year:
                        continue
                    all_papers.append({
                        "id": paper.get("id", ""),
                        "title": paper.get("title", ""),
                        "authors": [a.get("name", "") for a in paper.get("authors", [])],
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
        else:
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
                        "authors": [a.get("name", "") for a in paper.get("authors", [])],
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
        # Load all papers grouped by university from cache
        all_papers = {}  # (title, acronym) -> paper dict
        for acronym, papers_list in self._all_uni_papers.items():
            for paper in papers_list:
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
                paper_unis[title].update(self.match_uninovis(aff))

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

    def match_uninovis(self, affiliation: str) -> set:
        """Match an affiliation string against UNINOVIS university keywords.

        Returns a set of matched university acronyms.
        """
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

    def get_metadata_summary(self) -> list:
        """Returns metadata summary for all indexed documents."""
        return list(self._documents_metadata.values())

    # ------------------------------------------------------------------
    # Map HTML builders (static methods)
    # ------------------------------------------------------------------

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
            L.latLng(35, -6),    // Southwest: just below Malaga
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

    # ------------------------------------------------------------------
    # Query classification (static)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_conceptual_question(user_message: str) -> bool:
        """Detect questions about concept definitions or relationships between concepts.

        Examples that match:
        - "is explainable AI related with ethics"
        - "what is fairness in AI?"
        - "define transparency"
        - "difference between interpretability and explainability"
        - "how does XAI relate to accountability?"
        - "what does bias mean in AI?"

        These questions should be answered using the glossary, not by
        searching for papers.
        """
        msg_lower = user_message.lower().strip().rstrip("?!.")

        # Exclude project queries — "What is the TAILOR project about?" is not conceptual
        if any(kw in msg_lower for kw in ("project", "grant", "funding", "funded", "consortium")):
            return False

        # Exclude researcher queries — "What are the research interests of X?" is not conceptual
        if any(kw in msg_lower for kw in ("research interest", "published", "work on", "works on",
                                           "papers by", "researcher")):
            return False

        conceptual_patterns = [
            # "is X related to/with Y"
            r'\bis\b.+\brelated\s+(?:to|with)\b',
            # "what is X" / "what are X"
            r'^what\s+(?:is|are)\b',
            # "define X" / "definition of X"
            r'\bdefin(?:e|ition\s+of)\b',
            # "difference between X and Y"
            r'\bdifference\s+between\b',
            # "how does X relate to Y" / "how is X related to Y"
            r'\bhow\s+(?:does|do|is|are)\b.+\brelate[ds]?\s+(?:to|with)\b',
            # "what does X mean"
            r'\bwhat\s+does\b.+\bmean\b',
            # "explain the concept of X"
            r'\bexplain\s+(?:the\s+)?concept\b',
            # "what is the relationship between X and Y"
            r'\brelationship\s+between\b',
            # "are X and Y related"
            r'\bare\b.+\band\b.+\brelated\b',
            # "does X have to do with Y"
            r'\bdoes\b.+\bhave\s+to\s+do\s+with\b',
            # "is X part of Y" / "is X a subset of Y"
            r'\bis\b.+\b(?:part|subset|component|aspect|pillar|dimension)\s+of\b',
            # "what is the connection between"
            r'\bconnection\s+between\b',
        ]
        return any(re.search(p, msg_lower) for p in conceptual_patterns)

    @staticmethod
    def _is_figure_request(user_message: str) -> bool:
        """Detect if the user is asking for a figure or map.
        These requests don't need RAG context -- the system prompt has all
        the instructions the LLM needs to generate the correct map link,
        and the map endpoints themselves use structured data."""
        msg_lower = user_message.lower()
        return any(kw in msg_lower for kw in ("figure", "map"))

    @staticmethod
    def _is_non_research_task(user_message: str) -> bool:
        """Detect non-research task requests (write essays, translate, book flights, etc.).

        These should always get a red banner regardless of whether the query
        contains in-scope terms, because the user's intent is not research.
        """
        msg_lower = user_message.lower().strip()
        task_patterns = [
            r'^write\s+(?:me\s+)?(?:an?\s+)?(?:essay|report|letter|poem|story|code)',
            r'^translate\b',
            r'\btranslate\s+(?:this|the|my|following)\b',
            r'\bbook\s+(?:me|a|my)\s+(?:a\s+)?(?:flight|hotel|ticket|room)',
            r'\border\s+(?:me|a|my)\b',
            r'\bwho\s+won\s+(?:the|last)\b',
            r'\bwhat\s+is\s+the\s+(?:weather|temperature|time|capital|population)\b',
            r'\bwhat\s+(?:is|was)\s+the\s+score\b',
            r'\brecipe\s+for\b',
            r'\bhow\s+(?:do|can)\s+(?:i|you)\s+(?:cook|make|bake|prepare)\b',
        ]
        return any(re.search(p, msg_lower) for p in task_patterns)

    @staticmethod
    def _is_gap_analysis_query(user_message: str) -> bool:
        """Detect queries asking about topics NOT studied, research gaps, or missing areas.
        These require LLM reasoning beyond database content."""
        msg_lower = user_message.lower()
        gap_phrases = [
            "not been studied", "not studied", "have not been",
            "has not been", "missing", "gaps", "unstudied",
            "not covered", "not researched", "not explored",
            "not addressed", "not investigated",
        ]
        return any(phrase in msg_lower for phrase in gap_phrases)

    @staticmethod
    @staticmethod
    def _is_off_topic_response(text: str) -> bool:
        """Detect if the LLM response is an off-topic refusal."""
        text_lower = text.lower()
        off_topic_phrases = [
            "outside my scope", "outside the scope",
            "outside my area", "outside my domain",
            "outside my expertise", "not within my scope",
            "beyond my scope", "beyond the scope",
            "not related to", "is not part of my",
        ]
        return any(phrase in text_lower for phrase in off_topic_phrases)

    @classmethod
    def _split_off_topic_banners(cls, text: str) -> str:
        """Split an off-topic response into verified refusal + unverified suggestions.

        The refusal part (correctly identifying the question as off-topic) gets a
        green Verified banner. The suggestions part (AI-generated topic ideas) gets
        a red Unverified banner since they may not correspond to actual database content.
        """
        import re
        # Find where suggestions begin — match both newline-separated and mid-sentence
        split_patterns = [
            r'(?:However|That said|Instead),?\s+I can suggest',
            r'(?:However|That said|Instead),?\s+(?:here are|you might|let me)',
            r'\n\s*(?:However|That said|Instead|But),?\s',
            r'\n\s*(?:I can suggest|Here are some|You might|Let me suggest)',
            r'(?:I can suggest|Here are some|You might find)',
            r'(?:such as:|for example:)',
            r'\n\s*(?:related topics|suggest.*topics|topics.*interest)',
        ]
        split_pos = None
        for pattern in split_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                if split_pos is None or m.start() < split_pos:
                    split_pos = m.start()

        if split_pos and split_pos > 10:
            refusal = text[:split_pos].strip()
            suggestions = text[split_pos:].strip()
            return (
                cls._banner_verified("This question is outside the scope of this agent.")
                + refusal + "\n\n"
                + cls._banner_speculation("The topic suggestions below are generated by the AI model and may not correspond to actual content in the database.")
                + suggestions
            )
        else:
            # Can't split — use verified banner for the whole refusal
            return cls._banner_verified("This question is outside the scope of this agent.") + text

    def _query_mentions_researcher(self, user_message: str) -> bool:
        """Check if the user's query mentions a known researcher name."""
        if not self._researchers_by_uni:
            return False
        msg_lower = user_message.lower()
        for researchers in self._researchers_by_uni.values():
            for r in researchers:
                name = r["name"]
                name_parts = name.split()
                surname = name_parts[-1] if name_parts else ""
                if (name.lower() in msg_lower or
                        (len(surname) > 3 and surname.lower() in msg_lower)):
                    return True
        return False

    @staticmethod
    def _is_not_found_response(text: str) -> bool:
        """Detect if the LLM response is just a 'not found' refusal (no substantive content)."""
        text_lower = text.lower()
        not_found_phrases = [
            "could not find", "couldn't find", "not found", "no papers",
            "no relevant", "no results", "no study", "no research",
            "no matching", "does not include", "do not include",
            "not available", "no information", "no data",
        ]
        return any(phrase in text_lower for phrase in not_found_phrases)

    @classmethod
    def _inject_unsolicited_gap_banner(cls, text: str, is_gap_analysis: bool) -> str:
        """Inject a red 'Unverified' banner before unsolicited gap analysis sections.

        When the user did NOT ask about gaps (is_gap_analysis=False) but the LLM
        volunteers a section about topics not studied / research gaps, inject a
        red banner before that section to warn the user.

        Returns the text unchanged if no unsolicited gap section is found.
        """
        if is_gap_analysis:
            return text  # user asked for gaps — the whole response is already bannered

        # Patterns that indicate the start of a gap analysis section
        gap_section_patterns = [
            r'\n#+\s*(?:Topics?\s+Not\s+(?:Studied|Covered|Explored|Addressed|Researched))',
            r'\n#+\s*(?:Research\s+Gaps?|Gaps?\s+in\s+Research|Missing\s+(?:Topics?|Areas?))',
            r'\n#+\s*(?:Areas?\s+Not\s+(?:Covered|Explored|Addressed|Studied))',
            r'\n\*\*(?:Topics?\s+Not\s+(?:Studied|Covered|Explored|Addressed))',
            r'\n\*\*(?:Research\s+Gaps?|Missing\s+(?:Topics?|Areas?))',
            # Bold or heading with "not" + studied/covered/explored
            r'\n(?:#{1,4}\s+|\*\*)[^\n]*\bnot\b[^\n]*\b(?:studied|covered|explored|addressed|researched)\b',
        ]

        earliest_pos = None
        for pattern in gap_section_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m and (earliest_pos is None or m.start() < earliest_pos):
                earliest_pos = m.start()

        if earliest_pos is None or earliest_pos < 20:
            return text

        before = text[:earliest_pos].rstrip()
        gap_section = text[earliest_pos:]

        banner = (
            '\n\n'
            + cls._banner_speculation(
                "The section below identifies potential research gaps by reasoning "
                "about what is absent from the database. Topics may exist under "
                "different names or may not have been indexed. "
                "Verify before using this to inform research decisions."
            )
        )

        return before + banner + gap_section

    @staticmethod
    def _cites_database_sources(text: str) -> bool:
        """Detect if the LLM response cites actual sources from the database
        (papers, PDFs, titles, authors), indicating RAG content was used."""
        indicators = [
            r'\U0001F4C4', r'PDF', r'Title:', r'Author:', r'DOI',
            r'\bpaper\b.*\bfound\b', r'\bstudy\b.*\bfound\b',
            r'I found \d+', r'\d+ paper', r'\d+ study',
        ]
        return any(re.search(p, text) for p in indicators)

    @staticmethod
    def _is_followup_query(user_message: str) -> bool:
        """Detect short follow-up queries that refer to previous conversation context
        (e.g. 'expand on 1', 'tell me more about 3', 'more details', 'yes', 'go on')."""
        msg = user_message.strip().lower()
        if MetadataRAGMixin._is_web_expand_request(msg):
            return False  # web expand requests are not follow-ups
        if len(msg) < 60:
            followup_patterns = [
                r'^(expand|elaborate|more|details|explain|continue|go on|yes|no|ok)',
                r'^\d+$',  # just a number
                r'^(tell me )?more (about|on|details)',
                r'^what about',
                r'^(and|but) ',
                r'^can you (expand|elaborate|explain)',
            ]
            return any(re.match(p, msg) for p in followup_patterns)
        return False

    @staticmethod
    def _is_web_expand_request(user_message: str) -> bool:
        """Detect when the user accepts the web search expansion offer."""
        msg = user_message.strip().lower()
        if len(msg) > 80:
            return False
        expand_patterns = [
            r'^(yes,?\s*)?(expand|search)\s*(the\s+)?web',
            r'^(yes,?\s*)?web\s*search',
            r'^(yes,?\s*)?(expand|broaden|widen)\s*(the\s+)?search',
            r'^(yes,?\s*)?search\s*(the\s+)?(internet|web|online)',
            r'^yes,?\s*please\s*(expand|search|look)',
            r'^(yes|si|sí|ok|okay|sure|please|go ahead)',
        ]
        return any(re.match(p, msg) for p in expand_patterns)

    def _should_offer_web_search(self, breakdown: dict, topic_ctx: str, context: str) -> bool:
        """Decide whether to offer web search expansion based on result quality.

        Offers web search when:
        - Topic search found 0 papers, OR
        - RAG retrieved very little context, OR
        - Confidence is below 50% (mostly LLM-generated claims)
        AND web search is configured (API key present).
        """
        web_cfg = self._config.get("web_search", {})
        if not web_cfg.get("google_api_key") or not web_cfg.get("google_cx"):
            return False

        # Already used web search in this response
        if breakdown.get("web_pct", 0) > 0:
            return False

        # Topic search found 0 papers
        if topic_ctx and "0 papers found" in topic_ctx:
            return True

        # Very little RAG context
        if not context or len(context) < 100:
            if not topic_ctx:
                return True

        # Low confidence — mostly LLM claims
        if breakdown.get("confidence", 100) < 50:
            return True

        return False

    def _get_last_query(self) -> str:
        """Get the last query from history for web search expansion."""
        if self._query_history:
            return self._query_history[-1].get("question", "")
        return ""

    @staticmethod
    def _strip_map_links(text: str) -> str:
        """Remove markdown map links from text when the LLM adds them despite instructions."""
        return re.sub(
            r'\[([^\]]*)\]\([^)]*(?:topic-map|publications-map|collaboration-map|projects-map|project-topic-map)[^)]*\)\s*',
            '', text
        ).rstrip()

    def _verify_paper_references(self, text: str, context: str, transparency: str = None) -> tuple:
        """Verify paper references in the response against the papers cache.

        Skipped entirely in black_box transparency mode.

        Two verification passes:
        1. **Title verification** — every quoted title (in bold or quotes) is
           checked against the full title list. Unrecognised titles are flagged.
        2. **ID verification** — every paper ID is cross-checked against the
           surrounding text to detect ID-title mismatches.
        """
        # No verification in black_box mode
        if (transparency or self._transparency) == "black_box":
            return text, 0

        # Build lookups
        paper_by_id = {}       # pid → paper info
        known_titles = set()   # lowercased titles for fast lookup
        title_to_info = {}     # lowercased title → paper info (first match)

        for uni_acro, uni_papers in self._all_uni_papers.items():
            for paper in uni_papers:
                pid = paper.get("id", "")
                title = paper.get("title", "")
                author_names = [a.get("name", "") for a in paper.get("authors", [])]
                has_pdf = bool(paper.get("pdf_url") or paper.get("local_pdf_path"))
                info = {
                    "id": pid,
                    "title": title,
                    "authors": author_names,
                    "university": uni_acro,
                    "year": paper.get("publication_year", ""),
                    "has_pdf": has_pdf,
                }
                if pid:
                    paper_by_id[pid] = info
                if title:
                    t_lower = title.lower()
                    known_titles.add(t_lower)
                    if t_lower not in title_to_info:
                        title_to_info[t_lower] = info

        # Also register indexed documents (PDFs on disk) that aren't in
        # papers.json — ChromaDB indexes them and the LLM may cite them.
        docs_path = os.path.join(self._agent_dir, "data", "docs")
        if os.path.exists(docs_path):
            for fname in os.listdir(docs_path):
                if not fname.endswith('.pdf'):
                    continue
                pid = fname.replace('.pdf', '')
                if pid in paper_by_id:
                    # Already known from papers.json — just ensure has_pdf is set
                    paper_by_id[pid]["has_pdf"] = True
                    continue
                # Orphan PDF: on disk but not in papers.json.
                # Use ChromaDB metadata if available.
                doc_meta = self._documents_metadata.get(fname, {})
                title = doc_meta.get("title", "")
                info = {
                    "id": pid,
                    "title": title,
                    "authors": [a.strip() for a in doc_meta.get("author", "").split(",") if a.strip()],
                    "university": doc_meta.get("university_acronym", ""),
                    "year": doc_meta.get("date", "")[:4] if doc_meta.get("date") else "",
                    "has_pdf": True,
                }
                paper_by_id[pid] = info
                if title:
                    t_lower = title.lower()
                    known_titles.add(t_lower)
                    if t_lower not in title_to_info:
                        title_to_info[t_lower] = info

        # Also register project titles from project_docs/ directory
        project_docs_dir = os.path.join(self._agent_dir, "data", "project_docs")
        if os.path.exists(project_docs_dir):
            for fname in os.listdir(project_docs_dir):
                if not fname.endswith('.md'):
                    continue
                fpath = os.path.join(project_docs_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                    # Title format: "# ShortName: Full Project Title"
                    if first_line.startswith('# '):
                        project_title = first_line[2:].strip()
                        known_titles.add(project_title.lower())
                        # Also add the part after the colon (the descriptive title)
                        if ':' in project_title:
                            desc_title = project_title.split(':', 1)[1].strip()
                            if len(desc_title) > 10:
                                known_titles.add(desc_title.lower())
                except Exception:
                    pass

        # --- Pass 1: Title verification ---
        # Extract paper titles from the response.  Paper titles appear in
        # specific patterns: quoted text in list items, typically followed
        # by "Authors:", "Year:", "PDF", or similar metadata lines.
        # We use a context-aware regex to avoid matching descriptive phrases.
        #
        # Pattern: a quoted string (≥20 chars) that appears after a list
        # marker (number, bullet, or newline) and is followed within 200
        # chars by author/year keywords.
        paper_title_pattern = re.compile(
            r'(?:^|\n)\s*(?:\d+\.?\s*|[-*•]\s*)?'   # optional list marker
            r'[*"]*"([^"]{20,})"[*"]*'               # quoted title (≥20 chars)
            r'(?=.{0,200}(?:Author|Year|PDF|University|\d{4}))',  # followed by metadata
            re.IGNORECASE | re.DOTALL
        )
        cited_titles = list(dict.fromkeys(paper_title_pattern.findall(text)))

        unrecognised_titles = []
        for title in cited_titles:
            t_lower = title.lower().strip().rstrip('.')
            # Skip very short or obviously non-title strings
            if len(t_lower.split()) < 3:
                continue
            # Skip example queries / suggested questions (not paper titles).
            # These typically start with interrogative/imperative words.
            if re.match(
                r'^(what|who|how|why|when|where|which|can|do|does|is|are|'
                r'show|list|tell|describe|explain|find|give|compare)',
                t_lower,
            ):
                continue
            # Check exact match
            if t_lower in known_titles:
                continue
            # Check 4-word sliding window match against all known titles
            found = False
            t_words = t_lower.split()
            if len(t_words) >= 4:
                for known_t in known_titles:
                    for i in range(len(t_words) - 3):
                        fragment = " ".join(t_words[i:i + 4])
                        if fragment in known_t:
                            found = True
                            break
                    if found:
                        break
            if not found:
                unrecognised_titles.append(title)

        # Annotate unrecognised titles inline
        for title in unrecognised_titles:
            marker = ' **⚠️ [not found in database]**'
            for pattern in [f'"{title}"', f'**"{title}"**', f'**{title}**']:
                if pattern in text:
                    text = text.replace(pattern, pattern + marker, 1)
                    break

        # --- Pass 1b: Remove fake PDF IDs for papers that have no PDF ---
        # For recognised titles whose real paper has no PDF, check if the
        # LLM fabricated a PDF reference nearby and remove it.
        fake_pdf_ids = set()
        for title in cited_titles:
            t_lower = title.lower().strip().rstrip('.')
            real_info = title_to_info.get(t_lower)
            if not real_info:
                # Try 4-word match
                for known_t, info in title_to_info.items():
                    t_words = t_lower.split()
                    if len(t_words) >= 4:
                        for i in range(len(t_words) - 3):
                            if " ".join(t_words[i:i + 4]) in known_t:
                                real_info = info
                                break
                    if real_info:
                        break
            if not real_info or real_info.get("has_pdf"):
                continue
            # This paper has no PDF — check for a fabricated PDF ID nearby
            title_pos = text.lower().find(t_lower)
            if title_pos == -1:
                continue
            # Search for a paper ID in the 300 chars after the title
            after_title = text[title_pos:title_pos + 300]
            fake_match = re.search(r'(?:PDF|pdf)[:\s]*(W\d{7,})', after_title)
            if fake_match:
                fake_id = fake_match.group(1)
                # Replace the "PDF: W..." line with a note
                text = text.replace(
                    fake_match.group(0),
                    'PDF: not available for this paper',
                    1
                )
                fake_pdf_ids.add(fake_id)

        # --- Pass 2: ID verification ---
        seen_ids = set(fake_pdf_ids)  # skip IDs already handled in Pass 1b
        cited_ids = []
        for pid in re.findall(r'\b(W\d{7,})\b', text):
            if pid not in seen_ids:
                seen_ids.add(pid)
                cited_ids.append(pid)

        unknown_ids = []
        mismatched_ids = []

        for pid in cited_ids:
            if pid not in paper_by_id:
                unknown_ids.append(pid)
                continue

            real = paper_by_id[pid]
            real_title_lower = real["title"].lower()

            # Check surrounding text (500 chars before AND after ID)
            pid_pos = text.find(pid)
            if pid_pos == -1:
                continue
            before = text[max(0, pid_pos - 500):pid_pos].lower()
            after = text[pid_pos + len(pid):pid_pos + len(pid) + 500].lower()
            nearby = before + " " + after

            # Title match: 3-word window
            title_matched = False
            title_words = real_title_lower.split()
            if len(title_words) >= 3:
                for i in range(len(title_words) - 2):
                    if " ".join(title_words[i:i + 3]) in nearby:
                        title_matched = True
                        break
            elif real_title_lower and real_title_lower in nearby:
                title_matched = True

            # Author match: at least one surname
            author_matched = False
            for name in real["authors"]:
                parts = name.split()
                if parts:
                    surname = parts[-1].lower()
                    if len(surname) > 2 and surname in nearby:
                        author_matched = True
                        break

            if not title_matched and not author_matched:
                mismatched_ids.append((pid, real))

        # Remove markdown/HTML links containing paper IDs before annotating,
        # so that inline replacement doesn't break link syntax.
        for pid, _real in mismatched_ids + [(p, None) for p in unknown_ids]:
            # Strip markdown links like [PDF](/api/.../W1234.pdf) or [text](url/W1234...)
            text = re.sub(
                r'\[([^\]]*)\]\([^)]*' + re.escape(pid) + r'[^)]*\)',
                pid, text
            )

        # Helper: find the best matching paper for nearby text, scored by
        # number of 3-word title fragments + author surname matches.
        def _best_match(nearby: str, exclude_pid: str = None):
            best_id = None
            best_score = 0
            for cand_id, cand_info in paper_by_id.items():
                if cand_id == exclude_pid:
                    continue
                score = 0
                cand_title_lower = cand_info["title"].lower()
                title_words = cand_title_lower.split()
                if len(title_words) >= 3:
                    for i in range(len(title_words) - 2):
                        if " ".join(title_words[i:i + 3]) in nearby:
                            score += 2  # each 3-word fragment match
                elif cand_title_lower and cand_title_lower in nearby:
                    score += 2
                for name in cand_info["authors"]:
                    parts = name.split()
                    if parts:
                        surname = parts[-1].lower()
                        if len(surname) > 2 and surname in nearby:
                            score += 1  # each author surname match
                if score > best_score:
                    best_score = score
                    best_id = cand_id
            return best_id if best_score > 0 else None

        # Auto-correct mismatched IDs by finding the best paper from nearby text
        still_mismatched = []
        for pid, real in mismatched_ids:
            pid_pos = text.find(pid)
            if pid_pos == -1:
                still_mismatched.append((pid, real))
                continue
            before = text[max(0, pid_pos - 500):pid_pos].lower()
            after = text[pid_pos + len(pid):pid_pos + len(pid) + 500].lower()
            nearby = before + " " + after

            corrected_id = _best_match(nearby, exclude_pid=pid)

            if corrected_id:
                text = text.replace(pid, corrected_id)
            else:
                still_mismatched.append((pid, real))

        for pid, real in still_mismatched:
            annotation = (
                f'{pid}\n'
                f'  **⚠️ Warning:** the PDF link is not correct '
                f'(it is most possibly a hallucination from the LLM)'
            )
            text = text.replace(pid, annotation, 1)

        # Try to auto-correct unknown IDs by matching nearby title/author text
        still_unknown = []
        for pid in unknown_ids:
            pid_pos = text.find(pid)
            if pid_pos == -1:
                still_unknown.append(pid)
                continue
            before = text[max(0, pid_pos - 500):pid_pos].lower()
            after = text[pid_pos + len(pid):pid_pos + len(pid) + 500].lower()
            nearby = before + " " + after

            corrected = _best_match(nearby)

            if corrected:
                text = text.replace(pid, corrected)
            else:
                still_unknown.append(pid)

        for pid in still_unknown:
            text = text.replace(pid, f'{pid} **(not in database)**', 1)

        # Summary note
        note_lines = []
        if fake_pdf_ids:
            note_lines.append(
                f"**{len(fake_pdf_ids)} fake PDF link(s) removed** — "
                f"the paper(s) have no PDF available in the database."
            )
        if unrecognised_titles:
            note_lines.append(
                f"**{len(unrecognised_titles)} paper title(s) not found in the "
                f"database — may be hallucinated:**"
            )
            for t in unrecognised_titles:
                note_lines.append(f'- "{t}"')
        if still_mismatched:
            note_lines.append(
                f"**{len(still_mismatched)} PDF link(s) may be incorrect** "
                f"(possible LLM hallucination)."
            )
        if still_unknown:
            note_lines.append(
                f"**{len(still_unknown)} paper ID(s) not found in the database:** "
                + ", ".join(f"`{pid}`" for pid in still_unknown)
            )
        if note_lines:
            text += "\n\n---\n⚠️ **Verification note:**\n" + "\n".join(note_lines)

        total_hallucinations = len(unrecognised_titles) + len(still_mismatched) + len(still_unknown) + len(fake_pdf_ids)
        return text, total_hallucinations

    # ------------------------------------------------------------------
    # Chat methods (override SimpleRAGMixin or BaseRAGAgent)
    # ------------------------------------------------------------------

    def chat(self, user_message: str, history: list = None, username: str = None, **kwargs) -> str:
        """Send a message with RAG+Metadata context and return the response."""
        # Use per-request overrides or fall back to instance defaults
        transparency = kwargs.get('transparency_override') or self._transparency
        model = kwargs.get('model_override') or self.model
        prompt_level = kwargs.get('prompt_level_override') or self._prompt_level

        # Ensure ChromaDB is initialized (lazy)
        if not self._chromadb_initialized:
            self._init_chromadb()

        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"

        university_acronyms = list(self._config.get("universities", {}).keys())

        # --- Web search expansion: user accepted the offer ---
        is_web_expand = self._is_web_expand_request(user_message) and history
        web_ctx = ""
        if is_web_expand:
            original_query = self._get_last_query()
            if original_query:
                web_cfg = self._config.get("web_search", {})
                web_ctx = _web_search(
                    original_query,
                    api_key=web_cfg.get("google_api_key", ""),
                    cx=web_cfg.get("google_cx", ""),
                    num_results=web_cfg.get("num_results", 5),
                )

        # Conceptual questions (definitions, concept relationships) use glossary, not paper search
        is_conceptual = (not is_web_expand) and self._is_conceptual_question(user_message)
        glossary_ctx = self._build_glossary_context(user_message) if is_conceptual else ""

        # Check for project-specific queries first (before paper queries)
        project_ctx = "" if (is_web_expand or is_conceptual) else self._build_project_context(user_message)
        # Check for affiliation-based researcher queries
        affiliation_ctx = "" if (project_ctx or is_web_expand or is_conceptual) else self._build_affiliation_context(user_message)
        # Shared topics between 2+ universities (must check before uni_papers_ctx)
        shared_topics_ctx = ""
        if not (affiliation_ctx or project_ctx or is_web_expand or is_conceptual):
            if self._is_shared_topics_query(user_message):
                shared_topics_ctx = self._build_shared_topics_context(user_message)
        # University paper listing (no topic) -- uses authoritative *_papers.json
        uni_papers_ctx = "" if (shared_topics_ctx or affiliation_ctx or project_ctx or is_web_expand or is_conceptual) else self._build_university_papers_context(user_message)
        # Add topic-specific structured data (same source as figures)
        topic_ctx = "" if (shared_topics_ctx or affiliation_ctx or uni_papers_ctx or project_ctx or is_web_expand or is_conceptual) else self._build_topic_context(user_message)
        # Look up specific researchers mentioned in the query
        researcher_ctx = "" if (shared_topics_ctx or affiliation_ctx or uni_papers_ctx or project_ctx or is_web_expand or is_conceptual) else self._build_researcher_context(user_message)

        # Figure/map requests: the LLM generates the map link from system prompt
        # instructions alone -- no data context needed, maps use structured data
        is_figure_request = False if is_web_expand else self._is_figure_request(user_message)

        # Follow-up queries rely on conversation history, not RAG
        is_followup = (not is_web_expand) and self._is_followup_query(user_message) and history

        # Gap analysis queries use metadata + LLM reasoning, not RAG
        is_gap_analysis = False if is_web_expand else self._is_gap_analysis_query(user_message)

        # When structured context is available, use it instead of RAG
        if is_web_expand:
            # For web expansion, also retrieve local RAG context to combine
            original_query = self._get_last_query() or user_message
            uni_filter = self._detect_university_filter(original_query)
            context = self._retrieve_context(original_query, metadata_filter=uni_filter)
            source_type = "Web+RAG"
        elif is_conceptual:
            context = ""
            source_type = "Glossary"
        elif is_followup:
            context = ""
            source_type = "RAG"
        elif is_gap_analysis or shared_topics_ctx or affiliation_ctx or uni_papers_ctx or topic_ctx or researcher_ctx or project_ctx or is_figure_request:
            context = ""
            source_type = "Metadata"
        else:
            uni_filter = self._detect_university_filter(user_message)
            context = self._retrieve_context(user_message, metadata_filter=uni_filter)
            source_type = "RAG"

        system_with_context = self._build_system_prompt()
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system_with_context += f"\n\n{metadata_ctx}"
        if glossary_ctx:
            system_with_context += f"\n\n{glossary_ctx}"
        if project_ctx:
            system_with_context += f"\n\n{project_ctx}"
        if affiliation_ctx:
            system_with_context += f"\n\n{affiliation_ctx}"
        if shared_topics_ctx:
            system_with_context += f"\n\n{shared_topics_ctx}"
        if uni_papers_ctx:
            system_with_context += f"\n\n{uni_papers_ctx}"
        if topic_ctx:
            system_with_context += f"\n\n{topic_ctx}"
        if researcher_ctx:
            system_with_context += f"\n\n{researcher_ctx}"
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"
        if web_ctx:
            system_with_context += (
                f"\n\nAdditional context from web search (external sources — clearly indicate "
                f"when information comes from web sources vs. the UNINOVIS database):\n{web_ctx}"
            )

        has_structured_data = bool(
            shared_topics_ctx or affiliation_ctx or uni_papers_ctx or researcher_ctx or project_ctx or glossary_ctx
        )

        # Reliability text style: inject hedging instructions based on context quality
        if self._should_use_text_style():
            # Gap analysis and conceptual questions are speculative — always use cautious style
            if is_gap_analysis:
                quality = "gap_analysis"
            elif is_conceptual:
                quality = "conceptual"
            else:
                combined_for_estimate = " ".join(filter(None, [
                    project_ctx, affiliation_ctx, shared_topics_ctx, uni_papers_ctx,
                    topic_ctx, researcher_ctx, glossary_ctx,
                ]))
                quality = self._estimate_context_quality(context, metadata_ctx=combined_for_estimate)
            system_with_context += self._get_style_instruction(quality)

        # For web expand, rephrase the user message to re-ask the original query
        effective_message = user_message
        if is_web_expand and self._get_last_query():
            effective_message = (
                f"The user asked to expand the search to the web for their previous question. "
                f"Please answer this question using both the local database and the web search results: "
                f"{self._get_last_query()}"
            )

        use_procedural = getattr(self, '_skip_claim_classification', False)
        show_banners = use_procedural and transparency == "scaffolded" and self._should_show_visual_badge()
        detect_hallucinations = not use_procedural or transparency == "scaffolded"

        # --- Approach D: Programmatic facts + LLM commentary (AI3 only) ---
        factual_section = ""
        if use_procedural and not is_figure_request and not is_gap_analysis and not is_web_expand:
            if shared_topics_ctx:
                factual_section = self._build_shared_topics_factual_section(user_message, show_banners=show_banners)
            elif topic_ctx:
                factual_section = self._build_topic_factual_section(user_message, show_banners=show_banners)

        if factual_section:
            topic = self._extract_topic(user_message) or "shared research topics"
            analysis_prompt = self._analysis_prompt(topic, hedged=self._should_use_text_style())
            messages = [{"role": "system", "content": system_with_context}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": analysis_prompt})

            response = self.client.chat.complete(
                model=model,
                messages=messages,
                max_tokens=1024,
            )
            separator = self._banner_commentary() if show_banners else "\n\n---\n\n"
            commentary = self._sanitize_authority(response.choices[0].message.content)
            llm_content = factual_section + separator + commentary
            hallucination_count = 0
        else:
            # Determine banner based on query type (AI3 only)
            pre_banner = ""
            if show_banners:
                if is_figure_request:
                    pre_banner = self._banner_verified(
                        "This figure is generated directly from the UNINOVIS database (no AI involved)."
                    )
                elif is_followup:
                    pre_banner = self._banner_database(
                        "This follow-up response is generated by the AI model based on your previous query and database content."
                    )
                elif is_gap_analysis:
                    pre_banner = self._banner_speculation(
                        "The content below identifies potential research gaps by reasoning "
                        "about what is absent from the database. Topics may exist under "
                        "different names or may not have been indexed. "
                        "Verify before using this to inform research decisions."
                    )
                elif is_conceptual:
                    # LLM interprets glossary/general knowledge → yellow
                    if glossary_ctx:
                        pre_banner = self._banner_database(
                            "This response is generated by the AI model based on the "
                            "glossary definitions in the UNINOVIS database."
                        )
                    else:
                        pre_banner = self._banner_database(
                            "This response is generated by the AI model based on "
                            "general knowledge. The topic is within scope but not yet "
                            "covered by a specific glossary entry."
                        )
                elif project_ctx:
                    # LLM interprets project data → yellow
                    if self._query_mentions_researcher(user_message):
                        pre_banner = self._banner_database(
                            "Papers and projects come from the database, but links to "
                            "specific researchers may contain errors due to name disambiguation. "
                            "Verify authorship and participation before use."
                        )
                    else:
                        pre_banner = self._banner_database(
                            "The response below is generated by the AI model based on "
                            "research project data from the UNINOVIS database."
                        )
                elif researcher_ctx:
                    if "ATTRIBUTION NOT VERIFIED" in researcher_ctx:
                        pre_banner = self._banner_database(
                            "Some papers attributed to this researcher could not be "
                            "verified against the database author lists. "
                            "Items marked with \u26A0\uFE0F should be checked."
                        )
                    else:
                        pre_banner = self._banner_database(
                            "Papers and projects come from the database, but links to "
                            "specific researchers may contain errors due to name disambiguation. "
                            "Verify authorship and participation before use."
                        )
                elif has_structured_data:
                    pre_banner = self._banner_verified()
                elif not context and not web_ctx:
                    # No data at all: distinguish in-scope from out-of-scope
                    if self._is_in_topical_scope(user_message):
                        pre_banner = self._banner_undefined()
                        self._log_undefined_topic(user_message)
                    else:
                        pre_banner = self._banner_creative()
                elif context:
                    pre_banner = self._banner_database()

                # Override: non-research task requests always get a red banner
                if pre_banner and self._is_non_research_task(user_message):
                    pre_banner = self._banner_creative()

            messages = [{"role": "system", "content": system_with_context}]

            if history:
                messages.extend(history)

            messages.append({"role": "user", "content": effective_message})

            # Cap tokens for conceptual queries to enforce brevity
            tokens_limit = 1024 if is_conceptual else 16384

            response = self.client.chat.complete(
                model=model,
                messages=messages,
                max_tokens=tokens_limit,
            )

            llm_content = response.choices[0].message.content
            llm_content = self._sanitize_authority(llm_content)
            if not is_figure_request:
                llm_content = self._strip_map_links(llm_content)

            # Verify paper references against the database
            combined_ctx = " ".join(filter(None, [
                project_ctx, affiliation_ctx, shared_topics_ctx, uni_papers_ctx, topic_ctx, researcher_ctx,
                metadata_ctx, context, web_ctx
            ]))
            if detect_hallucinations:
                llm_content, hallucination_count = self._verify_paper_references(llm_content, combined_ctx, transparency)
            else:
                hallucination_count = 0

            # Post-process: inject DOI/PDF links for paper IDs missing links
            llm_content = self._inject_paper_links(llm_content)

            # For conceptual+glossary answers, check if the LLM substantially
            # deviated from the glossary content.  If so, downgrade the banner
            # from verified to database (AI interpretation).
            if is_conceptual and glossary_ctx and pre_banner and "Verified" in pre_banner:
                if self._glossary_answer_diverged(llm_content, glossary_ctx):
                    pre_banner = self._banner_database(
                        "This response is based on the Responsible AI Glossary, "
                        "but includes additional AI interpretation beyond the curated definitions."
                    )

            # Prepend banner (AI3 only)
            # If the LLM refused as off-topic, split into verified refusal + unverified suggestions
            if show_banners and self._is_off_topic_response(llm_content):
                llm_content = self._split_off_topic_banners(llm_content)
            elif pre_banner:
                llm_content = pre_banner + llm_content

            # Inject red banner before unsolicited gap analysis sections (AI3 only)
            if show_banners:
                llm_content = self._inject_unsolicited_gap_banner(llm_content, is_gap_analysis)

        # Compute grounding badge with source breakdown
        structured_ctx = " ".join(filter(None, [
            project_ctx, affiliation_ctx, shared_topics_ctx, uni_papers_ctx, topic_ctx, researcher_ctx, metadata_ctx, glossary_ctx
        ]))

        highlight_cfg = self._config.get("inline_claim_highlights")

        skip_claims = getattr(self, '_skip_claim_classification', False)

        if skip_claims:
            # AI3 procedural badge: agent tuning only, banners handle reliability
            reliability_label = "none"
            badge = ReliabilityBadge.procedural_badge(
                transparency=transparency,
                prompt_level=prompt_level,
                model_name=self.model_display_name,
                is_local_llm=self._is_local_llm,
            )
            breakdown = {}
        elif is_figure_request:
            # AI2 figure requests: 100% metadata, no claims
            reliability_label = "High"
            figure_breakdown = {"metadata_pct": 100, "database_pct": 0, "web_pct": 0, "llm_pct": 0,
                                "total_claims": 0, "confidence": 100,
                                "metadata_claims": [], "database_claims": [], "web_claims": [], "llm_claims": []}
            badge = ReliabilityBadge.source_badge(
                "Metadata", figure_breakdown,
                transparency=transparency,
                highlight_config=highlight_cfg,
                prompt_level=prompt_level,
                model_name=self.model_display_name,
                is_local_llm=self._is_local_llm,
            )
            breakdown = figure_breakdown
        else:
            # AI2 standard: full claim classification
            badge, breakdown, reliability_label = ReliabilityBadge.compute_badge_and_breakdown(
                llm_content, context,
                metadata_ctx=structured_ctx,
                web_ctx=web_ctx,
                transparency=transparency,
                green_max=self._reliability_green_max_llm,
                red_min=self._reliability_red_min_llm,
                highlight_config=highlight_cfg,
                university_acronyms=university_acronyms,
                is_gap_analysis=is_gap_analysis,
                is_not_found=self._is_not_found_response(llm_content),
                prompt_level=prompt_level,
                model_name=self.model_display_name,
                is_local_llm=self._is_local_llm,
                hallucination_count=hallucination_count,
            )

        # Humility post-processing: soften ungrounded claims
        llm_content = self._humility.rewrite(llm_content, breakdown)

        # Only prepend visual badge if configured
        if self._should_show_visual_badge() and badge:
            response_content = badge + llm_content
        else:
            response_content = llm_content

        # Offer web search expansion if results were insufficient
        if (not is_web_expand and not is_figure_request and not is_followup
                and self._should_offer_web_search(breakdown, topic_ctx, context)):
            response_content += (
                "\n\n---\n\n"
                "\U0001F310 *I found limited information in the UNINOVIS database on this topic. "
                "Would you like me to expand this search to the web? "
                "Reply **\"expand search\"** to search external sources.*"
            )

        # Audit log
        if is_web_expand:
            query_type = "web_expand"
        elif is_followup:
            query_type = "followup"
        elif is_figure_request:
            query_type = "figure"
        elif is_gap_analysis:
            query_type = "gap_analysis"
        elif is_conceptual:
            query_type = "conceptual"
        else:
            query_type = "normal"

        ctx_sources = []
        if glossary_ctx:    ctx_sources.append("glossary")
        if affiliation_ctx: ctx_sources.append("affiliation")
        if shared_topics_ctx: ctx_sources.append("shared_topics")
        if uni_papers_ctx:  ctx_sources.append("university_papers")
        if topic_ctx:       ctx_sources.append("topic")
        if researcher_ctx:  ctx_sources.append("researcher")
        if metadata_ctx:    ctx_sources.append("metadata")
        if context:         ctx_sources.append("rag")
        if web_ctx:         ctx_sources.append("web")

        AuditLogger.log(
            audit_path=self._audit_path,
            enabled=self._audit_enabled,
            agent_id=self._config.get("agent_id", "unknown"),
            query=user_message,
            query_type=query_type,
            breakdown=breakdown,
            reliability_label=reliability_label or "none",
            transparency=transparency,
            prompt_level=prompt_level,
            source_type=source_type or "none",
            context_sources=ctx_sources,
            username=username,
        )

        self._query_history.append({
            'question': self._get_last_query() if is_web_expand else user_message,
            'response_length': len(response_content)
        })

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, username: str = None, study_info: dict = None, **kwargs):
        """Send a message with RAG+Metadata context and stream the response."""
        # Use per-request overrides or fall back to instance defaults
        transparency = kwargs.get('transparency_override') or self._transparency
        model = kwargs.get('model_override') or self.model
        prompt_level = kwargs.get('prompt_level_override') or self._prompt_level

        # Ensure ChromaDB is initialized (lazy)
        if not self._chromadb_initialized:
            init_msg = getattr(self, '_init_status_message', "Creating ChromaDB for the agent...")
            yield ("status", init_msg)
            self._init_chromadb()

        yield ("status", "Thinking...")

        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"
            return

        university_acronyms = list(self._config.get("universities", {}).keys())

        # --- Web search expansion: user accepted the offer ---
        is_web_expand = self._is_web_expand_request(user_message) and history
        web_ctx = ""
        if is_web_expand:
            yield ("status", "Searching the web...")
            original_query = self._get_last_query()
            if original_query:
                web_cfg = self._config.get("web_search", {})
                web_ctx = _web_search(
                    original_query,
                    api_key=web_cfg.get("google_api_key", ""),
                    cx=web_cfg.get("google_cx", ""),
                    num_results=web_cfg.get("num_results", 5),
                )

        # Conceptual questions (definitions, concept relationships) use glossary, not paper search
        is_conceptual = (not is_web_expand) and self._is_conceptual_question(user_message)
        glossary_ctx = self._build_glossary_context(user_message) if is_conceptual else ""

        # Check for project-specific queries first (before paper queries)
        project_ctx = "" if (is_web_expand or is_conceptual) else self._build_project_context(user_message)
        # Check for affiliation-based researcher queries
        affiliation_ctx = "" if (project_ctx or is_web_expand or is_conceptual) else self._build_affiliation_context(user_message)
        # Shared topics between 2+ universities (must check before uni_papers_ctx)
        shared_topics_ctx = ""
        if not (affiliation_ctx or project_ctx or is_web_expand or is_conceptual):
            if self._is_shared_topics_query(user_message):
                shared_topics_ctx = self._build_shared_topics_context(user_message)
        # University paper listing (no topic) -- uses authoritative *_papers.json
        uni_papers_ctx = "" if (shared_topics_ctx or affiliation_ctx or project_ctx or is_web_expand or is_conceptual) else self._build_university_papers_context(user_message)
        # Add topic-specific structured data (same source as figures)
        topic_ctx = "" if (shared_topics_ctx or affiliation_ctx or uni_papers_ctx or project_ctx or is_web_expand or is_conceptual) else self._build_topic_context(user_message)
        # Look up specific researchers mentioned in the query
        researcher_ctx = "" if (shared_topics_ctx or affiliation_ctx or uni_papers_ctx or project_ctx or is_web_expand or is_conceptual) else self._build_researcher_context(user_message)

        # Figure/map requests: the LLM generates the map link from system prompt
        # instructions alone -- no data context needed, maps use structured data
        is_figure_request = False if is_web_expand else self._is_figure_request(user_message)

        # Follow-up queries rely on conversation history, not RAG
        is_followup = (not is_web_expand) and self._is_followup_query(user_message) and history

        # Gap analysis queries use metadata + LLM reasoning, not RAG
        is_gap_analysis = False if is_web_expand else self._is_gap_analysis_query(user_message)

        # When structured context is available, use it instead of RAG
        if is_web_expand:
            original_query = self._get_last_query() or user_message
            uni_filter = self._detect_university_filter(original_query)
            context = self._retrieve_context(original_query, metadata_filter=uni_filter)
            source_type = "Web+RAG"
        elif is_conceptual:
            context = ""
            source_type = "Glossary"
        elif is_followup:
            context = ""
            source_type = "RAG"
        elif is_gap_analysis or shared_topics_ctx or affiliation_ctx or uni_papers_ctx or topic_ctx or researcher_ctx or project_ctx or is_figure_request:
            context = ""
            source_type = "Metadata"
        else:
            uni_filter = self._detect_university_filter(user_message)
            context = self._retrieve_context(user_message, metadata_filter=uni_filter)
            source_type = "RAG"

        system_with_context = self._build_system_prompt()
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system_with_context += f"\n\n{metadata_ctx}"
        if glossary_ctx:
            system_with_context += f"\n\n{glossary_ctx}"
        if project_ctx:
            system_with_context += f"\n\n{project_ctx}"
        if affiliation_ctx:
            system_with_context += f"\n\n{affiliation_ctx}"
        if shared_topics_ctx:
            system_with_context += f"\n\n{shared_topics_ctx}"
        if uni_papers_ctx:
            system_with_context += f"\n\n{uni_papers_ctx}"
        if topic_ctx:
            system_with_context += f"\n\n{topic_ctx}"
        if researcher_ctx:
            system_with_context += f"\n\n{researcher_ctx}"
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"
        if web_ctx:
            system_with_context += (
                f"\n\nAdditional context from web search (external sources — clearly indicate "
                f"when information comes from web sources vs. the UNINOVIS database):\n{web_ctx}"
            )

        has_structured_data = bool(
            shared_topics_ctx or affiliation_ctx or uni_papers_ctx or researcher_ctx or project_ctx or glossary_ctx
        )

        # Reliability text style: inject hedging instructions based on context quality
        if self._should_use_text_style():
            # Gap analysis and conceptual questions are speculative — always use cautious style
            if is_gap_analysis:
                quality = "gap_analysis"
            elif is_conceptual:
                quality = "conceptual"
            else:
                combined_for_estimate = " ".join(filter(None, [
                    project_ctx, affiliation_ctx, shared_topics_ctx, uni_papers_ctx,
                    topic_ctx, researcher_ctx, glossary_ctx,
                ]))
                quality = self._estimate_context_quality(context, metadata_ctx=combined_for_estimate)
            system_with_context += self._get_style_instruction(quality)

        # For web expand, rephrase the user message to re-ask the original query
        effective_message = user_message
        if is_web_expand and self._get_last_query():
            effective_message = (
                f"The user asked to expand the search to the web for their previous question. "
                f"Please answer this question using both the local database and the web search results: "
                f"{self._get_last_query()}"
            )

        use_procedural = getattr(self, '_skip_claim_classification', False)
        show_banners = use_procedural and transparency == "scaffolded" and self._should_show_visual_badge()
        detect_hallucinations = not use_procedural or transparency == "scaffolded"

        # --- Approach D: Programmatic facts + LLM commentary (AI3 only) ---
        factual_section = ""
        if use_procedural and not is_figure_request and not is_gap_analysis and not is_web_expand:
            if shared_topics_ctx:
                factual_section = self._build_shared_topics_factual_section(user_message, show_banners=show_banners)
            elif topic_ctx:
                factual_section = self._build_topic_factual_section(user_message, show_banners=show_banners)

        if factual_section:
            # Stream the factual section first (no LLM involved)
            separator = self._banner_commentary() if show_banners else "\n\n---\n\n"
            full_response = factual_section
            yield factual_section

            # Stream the separator/banner
            full_response += separator
            yield separator

            # Ask the LLM for a brief analysis only — constrained prompt
            topic = self._extract_topic(user_message) or "shared research topics"
            analysis_prompt = self._analysis_prompt(topic, hedged=self._should_use_text_style())
            messages = [{"role": "system", "content": system_with_context}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": analysis_prompt})

            for _attempt in range(3):
                try:
                    async for chunk in await self.client.chat.stream_async(
                        model=model,
                        messages=messages,
                        max_tokens=1024,
                    ):
                        if chunk.data.choices[0].delta.content:
                            full_response += chunk.data.choices[0].delta.content
                            yield chunk.data.choices[0].delta.content
                    break  # success
                except Exception as e:
                    logger.warning("Mistral streaming attempt %d failed: %s", _attempt + 1, e)
                    if _attempt < 2:
                        await asyncio.sleep(1 * (_attempt + 1))
                    else:
                        raise

            # Post-process: sanitize authoritative phrases in commentary
            sanitized = self._sanitize_authority(full_response)
            if sanitized != full_response:
                full_response = sanitized
                yield ("replace", factual_section + separator + sanitized)

            hallucination_count = 0  # Factual section is verified by construction
        else:
            # Determine banner based on query type (AI3 procedural only)
            pre_banner = ""
            if show_banners:
                if is_figure_request:
                    pre_banner = self._banner_verified(
                        "This figure is generated directly from the UNINOVIS database (no AI involved)."
                    )
                elif is_followup:
                    pre_banner = self._banner_database(
                        "This follow-up response is generated by the AI model based on your previous query and database content."
                    )
                elif is_gap_analysis:
                    pre_banner = self._banner_speculation(
                        "The content below identifies potential research gaps by reasoning "
                        "about what is absent from the database. Topics may exist under "
                        "different names or may not have been indexed. "
                        "Verify before using this to inform research decisions."
                    )
                elif is_conceptual:
                    # LLM interprets glossary/general knowledge → yellow
                    if glossary_ctx:
                        pre_banner = self._banner_database(
                            "This response is generated by the AI model based on the "
                            "glossary definitions in the UNINOVIS database."
                        )
                    else:
                        pre_banner = self._banner_database(
                            "This response is generated by the AI model based on "
                            "general knowledge. The topic is within scope but not yet "
                            "covered by a specific glossary entry."
                        )
                elif project_ctx:
                    # LLM interprets project data → yellow
                    if self._query_mentions_researcher(user_message):
                        pre_banner = self._banner_database(
                            "Papers and projects come from the database, but links to "
                            "specific researchers may contain errors due to name disambiguation. "
                            "Verify authorship and participation before use."
                        )
                    else:
                        pre_banner = self._banner_database(
                            "The response below is generated by the AI model based on "
                            "research project data from the UNINOVIS database."
                        )
                elif researcher_ctx:
                    if "ATTRIBUTION NOT VERIFIED" in researcher_ctx:
                        pre_banner = self._banner_database(
                            "Some papers attributed to this researcher could not be "
                            "verified against the database author lists. "
                            "Items marked with \u26A0\uFE0F should be checked."
                        )
                    else:
                        pre_banner = self._banner_database(
                            "Papers and projects come from the database, but links to "
                            "specific researchers may contain errors due to name disambiguation. "
                            "Verify authorship and participation before use."
                        )
                elif has_structured_data:
                    pre_banner = self._banner_verified()
                elif not context and not web_ctx:
                    # No data at all: distinguish in-scope from out-of-scope
                    if self._is_in_topical_scope(user_message):
                        pre_banner = self._banner_undefined()
                        self._log_undefined_topic(user_message)
                    else:
                        pre_banner = self._banner_creative()
                elif context:
                    pre_banner = self._banner_database()

                # Override: non-research task requests always get a red banner
                if pre_banner and self._is_non_research_task(user_message):
                    pre_banner = self._banner_creative()

            messages = [{"role": "system", "content": system_with_context}]

            if history:
                messages.extend(history)

            messages.append({"role": "user", "content": effective_message})

            # Stream the banner first (AI3 only)
            # Use "procedural_banner" event type so it's displayed but NOT saved to session history
            full_response = ""
            if pre_banner:
                yield ("procedural_banner", pre_banner)

            # Cap tokens for conceptual queries to enforce brevity
            stream_tokens_limit = 1024 if is_conceptual else 16384

            # Stream LLM response
            for _attempt in range(3):
                try:
                    async for chunk in await self.client.chat.stream_async(
                        model=model,
                        messages=messages,
                        max_tokens=stream_tokens_limit,
                    ):
                        if chunk.data.choices[0].delta.content:
                            full_response += chunk.data.choices[0].delta.content
                            yield chunk.data.choices[0].delta.content
                    break  # success
                except Exception as e:
                    logger.warning("Mistral streaming attempt %d failed: %s", _attempt + 1, e)
                    if _attempt < 2:
                        await asyncio.sleep(1 * (_attempt + 1))
                    else:
                        raise

            # Post-process: sanitize authoritative phrases
            sanitized = self._sanitize_authority(full_response)
            if sanitized != full_response:
                full_response = sanitized
                yield ("replace", sanitized)

            # Strip map links if LLM added them despite not being a figure request
            if not is_figure_request:
                cleaned = self._strip_map_links(full_response)
                if cleaned != full_response:
                    full_response = cleaned
                    yield ("replace", cleaned)

            # If the LLM refused as off-topic, split into verified refusal + unverified suggestions
            if show_banners and self._is_off_topic_response(full_response):
                corrected = self._split_off_topic_banners(full_response)
                full_response = corrected
                yield ("replace", corrected)

            # Inject red banner before unsolicited gap analysis sections (AI3 only)
            if show_banners:
                gap_corrected = self._inject_unsolicited_gap_banner(full_response, is_gap_analysis)
                if gap_corrected != full_response:
                    full_response = gap_corrected
                    yield ("replace", gap_corrected)

            # Verify paper references against the database
            combined_ctx = " ".join(filter(None, [
                project_ctx, affiliation_ctx, shared_topics_ctx, uni_papers_ctx, topic_ctx, researcher_ctx,
                metadata_ctx, context, web_ctx
            ]))
            if detect_hallucinations:
                verified, hallucination_count = self._verify_paper_references(full_response, combined_ctx, transparency)
                if verified != full_response:
                    full_response = verified
                    yield ("replace", verified)
            else:
                hallucination_count = 0

            # Post-process: inject DOI/PDF links for paper IDs missing links
            enriched = self._inject_paper_links(full_response)
            if enriched != full_response:
                full_response = enriched
                yield ("replace", enriched)

            # For conceptual+glossary answers, downgrade banner if LLM diverged
            if is_conceptual and glossary_ctx and show_banners and pre_banner and "Verified" in pre_banner:
                if self._glossary_answer_diverged(full_response, glossary_ctx):
                    downgraded = self._banner_database(
                        "This response is based on the Responsible AI Glossary, "
                        "but includes additional AI interpretation beyond the curated definitions."
                    )
                    yield ("replace", downgraded + full_response)

        # Deferred grounding badge with source breakdown
        structured_ctx = " ".join(filter(None, [
            project_ctx, affiliation_ctx, shared_topics_ctx, uni_papers_ctx, topic_ctx, researcher_ctx, metadata_ctx, glossary_ctx
        ]))

        highlight_cfg = self._config.get("inline_claim_highlights")

        skip_claims = getattr(self, '_skip_claim_classification', False)

        if skip_claims:
            # AI3 procedural badge: agent tuning only, banners handle reliability
            reliability_label = "none"
            if self._should_show_visual_badge():
                yield ("badge", ReliabilityBadge.procedural_badge(
                    transparency=transparency,
                    prompt_level=prompt_level,
                    model_name=self.model_display_name,
                    is_local_llm=self._is_local_llm,
                ))
            breakdown = {}
        elif is_figure_request:
            # AI2 figure requests: 100% metadata, no claims
            reliability_label = "High"
            figure_breakdown = {"metadata_pct": 100, "database_pct": 0, "web_pct": 0, "llm_pct": 0,
                                "total_claims": 0, "confidence": 100,
                                "metadata_claims": [], "database_claims": [], "web_claims": [], "llm_claims": []}
            if self._should_show_visual_badge():
                yield ("badge", ReliabilityBadge.source_badge(
                    "Metadata", figure_breakdown,
                    transparency=transparency,
                    highlight_config=highlight_cfg,
                    prompt_level=prompt_level,
                    model_name=self.model_display_name,
                    is_local_llm=self._is_local_llm,
                ))
            breakdown = figure_breakdown
        else:
            # AI2 standard: full claim classification
            badge, breakdown, reliability_label = ReliabilityBadge.compute_badge_and_breakdown(
                full_response, context,
                metadata_ctx=structured_ctx,
                web_ctx=web_ctx,
                transparency=transparency,
                green_max=self._reliability_green_max_llm,
                red_min=self._reliability_red_min_llm,
                highlight_config=highlight_cfg,
                university_acronyms=university_acronyms,
                is_gap_analysis=is_gap_analysis,
                is_not_found=self._is_not_found_response(full_response),
                prompt_level=prompt_level,
                model_name=self.model_display_name,
                is_local_llm=self._is_local_llm,
                hallucination_count=hallucination_count,
            )
            if self._should_show_visual_badge() and badge:
                yield ("badge", badge)

        # Humility post-processing: soften ungrounded claims
        humbled = self._humility.rewrite(full_response, breakdown)
        if humbled != full_response:
            full_response = humbled
            yield ("replace", humbled)

        # Offer web search expansion if results were insufficient
        if (not is_web_expand and not is_figure_request and not is_followup
                and self._should_offer_web_search(breakdown, topic_ctx, context)):
            offer_text = (
                "\n\n---\n\n"
                "\U0001F310 *I found limited information in the UNINOVIS database on this topic. "
                "Would you like me to expand this search to the web? "
                "Reply **\"expand search\"** to search external sources.*"
            )
            full_response += offer_text
            yield offer_text

        # Send claim highlights (development only)
        if transparency == "crystal_box":
            highlight_cfg_obj = self._config.get("inline_claim_highlights", {})
            if (highlight_cfg_obj.get("enabled", False)
                    and breakdown.get("total_claims", 0) > 0):
                yield ("claim_highlights", json.dumps({
                    "metadata": breakdown.get("metadata_claims", []),
                    "database": breakdown.get("database_claims", []),
                    "web": breakdown.get("web_claims", []),
                    "llm": breakdown.get("llm_claims", []),
                    "metadata_style": highlight_cfg_obj.get("metadata_style", ""),
                    "database_style": highlight_cfg_obj.get("database_style", ""),
                    "web_style": highlight_cfg_obj.get("web_style", "background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;"),
                    "llm_style": highlight_cfg_obj.get("llm_style", ""),
                    "gap_analysis": is_gap_analysis,
                }))

        # Determine query type and context sources for audit
        if is_web_expand:
            query_type = "web_expand"
        elif is_followup:
            query_type = "followup"
        elif is_figure_request:
            query_type = "figure"
        elif is_gap_analysis:
            query_type = "gap_analysis"
        elif is_conceptual:
            query_type = "conceptual"
        else:
            query_type = "normal"

        ctx_sources = []
        if glossary_ctx:    ctx_sources.append("glossary")
        if affiliation_ctx: ctx_sources.append("affiliation")
        if shared_topics_ctx: ctx_sources.append("shared_topics")
        if uni_papers_ctx:  ctx_sources.append("university_papers")
        if topic_ctx:       ctx_sources.append("topic")
        if researcher_ctx:  ctx_sources.append("researcher")
        if metadata_ctx:    ctx_sources.append("metadata")
        if context:         ctx_sources.append("rag")
        if web_ctx:         ctx_sources.append("web")

        # Write audit log
        AuditLogger.log(
            audit_path=self._audit_path,
            enabled=self._audit_enabled,
            agent_id=self._config.get("agent_id", "unknown"),
            query=user_message,
            query_type=query_type,
            breakdown=breakdown,
            reliability_label=reliability_label or "none",
            transparency=transparency,
            prompt_level=prompt_level,
            source_type=source_type or "none",
            context_sources=ctx_sources,
            username=username,
        )

        # Write study log (separate de-identified log for research)
        if study_info:
            study_log_path = os.path.join(self._agent_dir, "data", "study_log.jsonl")
            StudyLogger.log(
                study_log_path=study_log_path,
                study_id=study_info.get("study_id", ""),
                email_domain=study_info.get("email_domain", ""),
                study_condition=study_info.get("study_condition", ""),
                query_number=study_info.get("query_number", 0),
                query_text=user_message,
                transparency_level=transparency,
                confidence=breakdown.get("confidence") if breakdown else None,
                reliability_label=reliability_label,
                breakdown=breakdown,
                hallucination_count=hallucination_count,
            )

        self._query_history.append({
            'question': self._get_last_query() if is_web_expand else user_message,
            'response_length': len(full_response)
        })

    # ------------------------------------------------------------------
    # reindex() override
    # ------------------------------------------------------------------

    def reindex(self):
        """Reindex all documents with metadata."""
        # Ensure ChromaDB is initialized
        if not self._chromadb_initialized:
            self._init_chromadb()

        self.chroma_client.delete_collection("documents")
        self.collection = self.chroma_client.create_collection(
            name="documents",
            embedding_function=self.embedding_fn
        )
        self._documents_metadata = {}
        self._index_documents()
        return self.collection.count()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {
                'question': entry['question'],
                'num_results': 1
            }
            for entry in self._query_history
        ]
