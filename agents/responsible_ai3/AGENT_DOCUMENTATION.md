# Responsible AI3 Agent -- Documentation

**Agent ID:** `responsible_ai3`
**Agent Name:** EH: Responsible AI (V02)
**Type:** `rag_metadata_vectorless` -- metadata-driven RAG agent without vector database dependencies

This document covers three audiences: developers/superusers, content managers/testers, and end users (teachers/students).

---

## 1. Developer / Superuser Guide

### 1.1 Architecture Overview

The agent is defined in a single class declaration with a carefully ordered MRO (Method Resolution Order):

```python
class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
```

**Class hierarchy (MRO order matters):**

| Order | Class | File | Role |
|-------|-------|------|------|
| 1 | `VectorlessMixin` | `base/vectorless_mixin.py` | Replaces ChromaDB with BM25 keyword retrieval from `chunk_db.json` |
| 2 | `MetadataRAGMixin` | `base/rag_metadata_mixin.py` | Papers, researchers, projects, glossary, banners, topic detection, figures/maps, audit logging |
| 3 | `BaseRAGAgent` | `base/base_RAGagent.py` | LLM client init, config loading, system prompt building, reliability display, humility rewriter |

The MRO order ensures that `VectorlessMixin._init_chromadb()` and `VectorlessMixin._retrieve_context()` intercept calls before `BaseRAGAgent` attempts ChromaDB operations. `MetadataRAGMixin._post_init()` is called from `BaseRAGAgent.__init__()` and loads all structured data (papers, researchers, projects, glossary, topical scope).

### 1.2 Data Files

All data lives under `/agents/responsible_ai3/data/`.

| File / Directory | Format | Description |
|---|---|---|
| `papers.json` | JSON | Papers grouped by university. Each paper has: `id`, `doi`, `title`, `abstract`, `publication_date`, `publication_year`, `type`, `cited_by_count`, `authors` (name + orcid), `affiliations`, `concepts` (name + score). Top-level key is `universities` with university acronyms as sub-keys. |
| `researchers.json` | JSON | Researchers grouped by university acronym. Each researcher has: `name`, `paper_count`, `topics` (list of strings), `papers` (id + title + year), `affiliations`, `affiliation_status`. |
| `chunk_db.json` | JSON (auto-built) | Keyword-indexed chunk database for BM25 retrieval. Contains `version`, `chunk_size`, `overlap`, `total_chunks`, `total_sources`, `idf` (term -> IDF score), and `chunks` (each with `id`, `source`, `paper_id`, `paper_title`, `chunk_index`, `text`, `keywords`). Auto-rebuilt when stale or missing. |
| `docs/` | PDF, MD, TXT | Source documents. Includes the glossary (`Glossary_Responsible_AI.md`) and paper PDFs. |
| `project_docs/` | MD | Funded research project descriptions (EU/national grants). Parsed into structured project data at init. |
| `audit_log.jsonl` | JSONL | Audit log for EU AI Act compliance. Each line records: timestamp, query, source type, breakdown, confidence, query type, context sources. |
| `undefined_topics.jsonl` | JSONL | Logs queries that are on-topic (within Responsible AI scope) but have no glossary or database match. Each entry has `timestamp` and `query`. |

### 1.3 Query Pipeline

The `chat()` method in `MetadataRAGMixin` processes each query through these stages:

1. **Query classification** -- Determines query type via pattern matching:
   - Conceptual question (glossary lookup)
   - Figure/map request (keyword "figure" or "map")
   - Gap analysis (research gaps)
   - Project query
   - Researcher query
   - Follow-up (references previous conversation)
   - University paper listing
   - Shared topics between universities
   - Web expansion (user accepted "expand search" offer)
   - Normal RAG query (fallback)

2. **Context building** -- Based on classification, the system assembles context from the appropriate sources: glossary text, structured paper/researcher/project data, BM25-retrieved document chunks, or web search results. Only one primary context path is active per query.

3. **System prompt assembly** -- The base system prompt (identity + rules + strict, controlled by `prompt_level`) is augmented with metadata context (paper counts, top topics, cross-university collaborations) and the query-specific context.

4. **Factual section generation** (for topic queries) -- Programmatic, no-LLM factual data is generated directly from `papers.json`. This is shown with a green banner. The LLM then generates a commentary section shown with a yellow banner.

5. **LLM call** -- The assembled messages are sent to the configured LLM model.

6. **Post-processing**:
   - `_sanitize_authority()` -- removes authoritative phrasing
   - `_strip_map_links()` -- removes unsolicited map links
   - `_verify_paper_references()` -- checks cited paper IDs against the database, annotates hallucinated references
   - `_inject_paper_links()` -- adds DOI/PDF links for paper IDs
   - `_glossary_answer_diverged()` -- if a glossary-based answer diverges, downgrades banner from green to yellow
   - Humility rewriter -- adds hedging language based on configured level
   - Banner prepending -- adds the appropriate colored banner
   - Audit logging -- writes to `audit_log.jsonl`

### 1.4 Two-Axis Banner System

The banner system classifies responses along two axes: **data source** (where did the information come from?) and **topical scope** (is the query within the agent's domain?).

**Topical scope set** is built from 6 sources at init (`_build_topical_scope()`):

| # | Source | Example |
|---|--------|---------|
| 1 | Glossary concept names + abbreviations | "responsible ai", "xai" |
| 2 | Related concepts from glossary entries | "trustworthy ai", "ai governance" |
| 3 | Bold terms from glossary definition bodies | "algorithmic audits", "privacy" |
| 4 | Concept names from `papers.json` | "software deployment", "european union" |
| 5 | Researcher topics from `researchers.json` | "data science", "computer science" |
| 6 | `extra_scope_terms` from `config.json` | "green ai", "federated learning", "ai red-teaming" |

`_is_in_topical_scope(user_message)` checks if any term from this set appears in the user's message (case-insensitive substring match).

**Banner hierarchy:**

| Banner | Color | Condition | Meaning |
|--------|-------|-----------|---------|
| Verified data | Green | Programmatic output from structured data (figures, topic factual sections, glossary answers) | No AI involved; directly traceable to database |
| AI interpretation of database content | Yellow | LLM response grounded in database/document content | AI summarized or formatted real data |
| AI Commentary | Yellow | LLM commentary appended after a green factual section | Low-risk AI interpretation of verified data |
| On-topic, undefined | Yellow | Query is in topical scope but no glossary/database match found | Topic is Responsible AI-related but not yet in the database |
| Unverified (speculation) | Red | Gap analysis or AI reasoning beyond data | Verify before use |
| Unverified (creative/off-topic) | Red | Query is outside topical scope entirely | Outside the UNINOVIS research database |

### 1.5 Glossary Answer Divergence Check

When the query is conceptual and a glossary entry is found, the initial banner is green (Verified). After the LLM responds, `_glossary_answer_diverged()` compares the words in the LLM response against the words in the glossary context. If the ratio of novel substantive words exceeds a threshold, the banner is downgraded from green to yellow ("AI interpretation beyond curated definitions").

### 1.6 Vectorless BM25 Retrieval

**Building the chunk database** (`build_chunk_db.py`):

1. Reads all PDF, MD, and TXT files from `data/docs/` and any `extra_docs_dirs` (e.g., `project_docs/`)
2. Extracts text (PyPDF for PDFs, plain read for MD/TXT)
3. Splits into overlapping chunks (default: 600 chars, 100 overlap) at natural boundaries (paragraph, sentence, line)
4. Tags each chunk with keywords: paper concepts from `papers.json` (matched by paper ID in filename, score >= 0.3) + TF-style top terms extracted from the chunk text
5. Computes IDF scores across all chunks
6. Saves to `data/chunk_db.json`

**Auto-rebuild**: `VectorlessMixin._init_chromadb()` checks if `chunk_db.json` is missing or older than any source document. If stale, it runs `build_chunk_db.py` as a subprocess.

**Query-time retrieval** (`VectorlessMixin._retrieve_context()`):
1. Tokenizes the query (lowercase, stop-word removal, min 3 chars)
2. Scores all chunks using BM25 (k1=1.5, b=0.75)
3. Returns the top N chunks (default 5) formatted as `[Fuente: filename]\ntext`

### 1.7 Transparency Types

Configured via `transparency_type` in `config.json`:

| Type | Config Value | Behavior |
|------|-------------|----------|
| Procedural | `"procedural"` | Uses inline banners (green/yellow/red) to indicate data source. No per-claim classification. Sets `_skip_claim_classification = True`. |
| Content | `"content"` | Full claim-level grounding analysis. Each claim is classified as metadata/database/web/LLM-sourced with percentage breakdown. |

The current agent uses **procedural** transparency.

### 1.8 Reliability Display Modes

Configured via `reliability_display` in `config.json`:

| Mode | Value | Effect |
|------|-------|--------|
| Visual | `"visual"` | Color badges only (sidebar reliability indicator) |
| Text style | `"text_style"` | Hedging language injected into LLM instructions based on context quality |
| Both | `"both"` | Badges + hedging language (current default) |
| None | `"none"` | Disabled |

### 1.9 Humility Rewriter

Post-processing step in `base/humility.py` (`HumilityRewriter`). Applied after the LLM response, before final output.

| Level | Behavior |
|-------|----------|
| `off` | No changes |
| `moderate` | Adds hedging prefixes ("Based on available information, ...") to sentences containing ungrounded (LLM-only) claims |
| `strict` | Hedges all partially-grounded and ungrounded claims + appends a disclaimer footer |

The rewriter skips markdown headers, code blocks, table rows, blockquotes, and sentences that already contain hedging language. Hedging prefixes rotate to avoid repetitive phrasing.

### 1.10 Audit Logging

When `audit_log_enabled` is `true`, every query is logged to `data/audit_log.jsonl` with:
- Timestamp
- Agent ID
- Query text and query type (normal, conceptual, figure, gap_analysis, followup, web_expand)
- Source type (Metadata, RAG, Glossary, Web+RAG)
- Reliability label
- Transparency level and prompt level
- Context sources used (glossary, affiliation, topic, researcher, rag, web, etc.)
- Breakdown (claim percentages)
- Username (if available)

### 1.11 The undefined_topics.jsonl Log

When a query is within topical scope (`_is_in_topical_scope()` returns `True`) but no structured data, glossary entry, or RAG context is found, the query is logged to `data/undefined_topics.jsonl`. Each entry contains a UTC timestamp and the raw query text. This log helps content managers identify which Responsible AI concepts users are asking about but are not yet covered in the database or glossary.

### 1.12 API Endpoints

Defined in `app.py` (FastAPI):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Agent info (id, name, type, description, welcome message, example queries) |
| `/health` | GET | Health check |
| `/chat` | POST | Main chat endpoint. Body: `{message, history?, stream?, verify?}` |
| `/reindex` | POST | No-op for vectorless agent (returns status ok, 0 chunks) |
| `/metadata` | GET | Returns metadata summary of all indexed documents |
| `/examples` | GET | Returns example queries |
| `/topic-search` | GET | Search papers by topic. Param: `?topic=...` |
| `/publications-search` | GET | All papers grouped by university |
| `/collaboration-search` | GET | Collaboration data. Params: `?topic=...&year=...` (optional) |
| `/projects-search` | GET | All projects grouped by university. Param: `?year=...` (optional) |
| `/topic-map` | GET | Interactive Leaflet map for a topic. Param: `?topic=...` |
| `/publications-map` | GET | Interactive Leaflet map of all publications |
| `/collaboration-map` | GET | Interactive collaboration map. Params: `?topic=...&year=...` (optional) |
| `/projects-map` | GET | Interactive projects map. Param: `?year=...` (optional) |
| `/project-topic-map` | GET | Projects map filtered by topic. Params: `?topic=...&year=...` |

### 1.13 How to Add New Data

**Adding papers:**
1. Add paper entries to `data/papers.json` under the appropriate university key. Required fields: `id`, `title`, `authors` (array of `{name, orcid}`), `publication_year`. Optional: `doi`, `abstract`, `type`, `cited_by_count`, `affiliations`, `concepts` (array of `{name, score}`).
2. Optionally place the paper PDF in `data/docs/` with the paper ID as filename (e.g., `W4400460850.pdf`).
3. Rebuild chunk DB (see below).

**Adding researchers:**
1. Add entries to `data/researchers.json` under the university acronym key. Required fields: `name`, `paper_count`, `topics` (array), `papers` (array of `{id, title, year}`). Optional: `affiliations`, `affiliation_status`.

**Adding glossary entries:**
1. Edit `data/docs/Glossary_Responsible_AI.md`. Add a new entry using the format described in Section 2.7 below.
2. Rebuild chunk DB to index the new text.

**Adding project documents:**
1. Place markdown files in `data/project_docs/`. The agent parses these at startup.

**Rebuilding the chunk database:**
Run manually: `python build_chunk_db.py` from the agent directory. Or simply delete `data/chunk_db.json` -- it will be auto-rebuilt on next agent startup if source documents exist. Options: `--chunk-size 800`, `--overlap 100`, `--output path`.

---

## 2. Content Manager / Tester Guide

### 2.1 Config Editor UI

The config editor is accessible via the **gear icon** in the agent's web interface. It requires a role of **tester or higher** (tester, admin_staff, teaching_staff, or superuser -- level 2+). The role hierarchy is:

| Role | Level | Config Editor Access |
|------|-------|---------------------|
| superuser | 4 | Full access -- all fields including agent identity, universities, thresholds |
| tester | 3 | Behavior settings, prompts, scope terms, examples, description |
| admin_staff | 2 | No config editor access |
| teaching_staff | 2 | No config editor access |
| student / user | 1 | No config editor access |

The config editor uses **role-based field visibility**:

- **Tester view**: Shows behavior settings (prompt level, transparency, humility, reliability display, LLM model, show history, audit log), description, welcome message, example queries, extra scope terms, and prompts.
- **Superuser view**: Shows everything the tester sees, plus agent name, agent ID, and full unrestricted write access to all config fields.

On the backend, write protection enforces these boundaries. When a tester saves, only the allowed fields are merged into the existing config -- structural fields like `universities`, `alliance`, `inline_claim_highlights`, `reliability_green_max_llm`, etc. are preserved unchanged.

### 2.2 Editable Config Fields

| Field | Values | Effect | Editable by |
|-------|--------|--------|-------------|
| `prompt_level` | `stringent` / `tolerant` / `lax` | Controls how many prompt sections are included in the system prompt. **Stringent**: identity + rules + strict (all guardrails). **Tolerant**: identity + rules (no strict section). **Lax**: identity only (minimal constraints). | tester+ | immediate |
| `transparency_level` | `scaffolded` / `unscaffolded` | **Scaffolded**: shows colored banners (green/yellow/red) on each response section indicating data source reliability. **Unscaffolded**: no banners, plain responses. Used for research comparison studies. | tester+ | immediate |
| LLM model | (depends on provider) | Affects response quality, speed, and cost. Client-side selection sent with each request. | tester+ | immediate |
| `humility_level` | `off` / `moderate` / `strict` | **Off**: no post-processing. **Moderate**: adds hedging prefixes to sentences with ungrounded claims. **Strict**: hedges all uncertain claims + appends a disclaimer footer. | superuser only | restart |
| `reliability_display` | `visual` / `text_style` / `both` / `none` | **Visual**: color badges in the sidebar. **Text style**: hedging language injected into LLM instructions. **Both**: badges + hedging. **None**: disabled. | superuser only | restart |
| `extra_scope_terms` | list of strings | Domain terms that are in-scope but not yet in the glossary or papers. Used by the two-axis banner system. | superuser only | restart |
| `example_queries` | list of strings | Shown in the UI as suggested questions for the user. | superuser only | restart |
| `description` | text | Agent description shown in the UI. | superuser only | restart |
| `welcome_message` | text | Greeting shown when the agent is selected. | superuser only | restart |
| `agent_name` | text | Display name of the agent. | superuser only |
| `agent_id` | text | Internal identifier. Changing this requires corresponding filesystem changes. | superuser only |
| `universities` | object | University definitions with coordinates. | superuser only |
| `reliability_green_max_llm` | number | LLM % threshold for green badge. | superuser only |
| `reliability_red_min_llm` | number | LLM % threshold for red badge. | superuser only |

### 2.3 Prompts Editing

The file `prompts.json` contains three editable sections:

| Section | Key | Description |
|---------|-----|-------------|
| Identity | `identity` | Defines who the agent is, the UNINOVIS alliance context, university list, and general behavior. Uses template variables like `{agent_name}`, `{research_topic}`, `{alliance_name}`, `{uni_list}`, etc. |
| Rules | `rules` | Response format rules: citation requirements, hallucination prevention, language matching, metadata usage, list formatting, paper ID inclusion, link preservation. Included at `tolerant` and `stringent` levels. |
| Strict | `strict` | Critical guardrails: UNINOVIS partner recognition (only 8 listed universities are partners), gap analysis logic, interactive map rules (only when user says "figure" or "map"), figure type decision tree. Included only at `stringent` level. |

### 2.4 extra_scope_terms

The `extra_scope_terms` array in `config.json` contains additional terms within the Responsible AI domain that may not appear in the glossary or paper topics. These are used by the two-axis banner system to distinguish on-topic queries from off-topic ones.

**When to add new terms:** When users ask about a Responsible AI concept and it gets a red "off-topic" banner instead of a yellow "on-topic, undefined" banner.

**Format:** Lowercase strings. Multi-word terms work (substring matching). Examples: `"green ai"`, `"federated learning"`, `"ai red-teaming"`.

The current list includes 67 terms covering areas like AI regulation, AI alignment, deepfakes, AI surveillance, AI standards (ISO 42001, NIST AI RMF, OECD AI principles), AI and disability, AI colonialism, AGI safety, and more.

### 2.5 How to Add a Glossary Entry

Edit the file `data/docs/Glossary_Responsible_AI.md`. Each entry follows this format:

```markdown
## Concept Name

Definition paragraph(s). Use **bold** for key technical terms within the definition.
Multiple paragraphs are allowed.

**Related concepts:** Concept A; Concept B; Concept C

**References:**
- Author, A. (Year). Title. Journal. DOI.
- Author, B. (Year). Title. Conference.
```

Key points:
- The `##` heading becomes the concept name (used for glossary lookups and topical scope)
- Bold terms in the definition body are extracted into the topical scope set
- Related concepts are extracted and added to the topical scope set
- References provide academic grounding for the definition

After adding an entry, rebuild the chunk DB to make the text searchable via BM25.

### 2.6 How to Add Papers and Researchers

**Papers** (`data/papers.json`):

```json
{
  "id": "W1234567890",
  "doi": "https://doi.org/10.xxxx/...",
  "title": "Paper Title",
  "abstract": "Abstract text...",
  "publication_date": "2025-01-15",
  "publication_year": 2025,
  "type": "article",
  "cited_by_count": 10,
  "authors": [
    {"name": "Author Name", "orcid": "https://orcid.org/0000-..."}
  ],
  "affiliations": ["University Name"],
  "concepts": [
    {"name": "Concept Name", "score": 0.85}
  ]
}
```

Add to the `papers` array under the correct university acronym (KK, THUAS, UMA, etc.).

**Researchers** (`data/researchers.json`):

```json
{
  "name": "Researcher Name",
  "paper_count": 3,
  "topics": ["Topic A", "Topic B"],
  "papers": [
    {"id": "W1234567890", "title": "Paper Title", "year": 2025}
  ],
  "affiliations": [],
  "affiliation_status": "confirmed"
}
```

Add to the array under the correct university acronym.

### 2.7 Triggering a Chunk DB Rebuild

Three options:
1. **Automatic**: Delete `data/chunk_db.json`. It will be rebuilt on next agent startup.
2. **Manual**: Run `python build_chunk_db.py` from the agent directory.
3. **API**: Call `POST /reindex` (note: for the vectorless agent, this clears the cache so the DB reloads on next query; it does not actively rebuild).

### 2.8 Example Queries

Example queries appear in the UI as clickable suggestions. They are defined in `config.json` under `example_queries`. Current examples include:
- "**Show a figure** with all the publications per partner"
- "**Show a figure** of studies on the **topic** AI and Ethics"
- "**List researchers** that have interest in AI and Ethics"
- "**List the Responsible AI subtopics** MOST studied in UNINOVIS"
- "**List any topics** related with responsible AI that have not been studied"
- "**Show a figure** of the **collaborations** among the partners"
- "**Show a figure** of the collaborations in the **year** 2025"
- "List **research projects** on trustworthy AI"
- "**Show a map** with the number of **research projects** per partner"
- "Tell me **an AI responsible hot chocolate recipe**" (tests off-topic handling)
- "What is responsible AI?" (tests conceptual/glossary path)

### 2.9 The undefined_topics.jsonl File

Located at `data/undefined_topics.jsonl`. Each line is a JSON object with `timestamp` and `query`.

**What it tells you:** Users are asking about a Responsible AI topic that the agent recognizes as in-scope (via the topical scope set) but cannot answer from the glossary or database.

**How to act on it:** Review the logged queries periodically. For frequently asked topics:
1. Add a glossary entry in `Glossary_Responsible_AI.md`
2. Or add relevant papers to `papers.json`
3. Or add the topic to `extra_scope_terms` if it should be recognized but not yet defined

### 2.10 Testing Tips: Verifying Banner Correctness

| Query Type | Expected Banner |
|------------|----------------|
| "What is responsible AI?" | Green (glossary answer) or Yellow (if LLM diverges from glossary) |
| "List researchers from THUAS" | Green (structured data) |
| "Show a figure of AI Ethics studies" | Green (figure from database) |
| "List topics not studied in UNINOVIS" | Red (gap analysis / speculation) |
| "Tell me a cake recipe" | Red (off-topic / creative) |
| "What is AI red-teaming?" (if not in glossary but in extra_scope_terms) | Yellow (on-topic, undefined) |
| "Papers on explainable AI" | Green factual section + Yellow AI commentary |
| Follow-up question referencing previous answer | Yellow (database-based follow-up) |

To test with banners visible, ensure `transparency_level` is set to `scaffolded`.

---

## 3. End User Guide (Teachers / Students)

### 3.1 What the Agent Does

This agent is a research assistant specialized in **UNINOVIS Responsible AI research**. It can answer questions about:
- Research papers published by the 8 UNINOVIS partner universities (USPN, UDCLV, UMA, KK, UT, THWS, TAMK, THUAS)
- Funded research projects (EU and national grants) involving UNINOVIS partners
- Responsible AI concepts and definitions
- Researchers and their areas of expertise
- Collaboration patterns between universities
- Research gaps and trends

The UNINOVIS alliance is a European university alliance focused on enhancing education, research, and innovation in applied data science.

### 3.2 Understanding the Banners

When transparency is enabled, each response section includes a colored banner indicating how reliable the information is:

| Banner | Color | Meaning |
|--------|-------|---------|
| **Verified data** | Green | The information comes directly from the UNINOVIS database with no AI involvement. Paper lists, researcher data, figures, and glossary definitions appear with this banner. You can trust this data. |
| **AI interpretation of database content** | Yellow | The AI model generated this response based on real data from the UNINOVIS database. The information is grounded but may contain approximate groupings or interpretive summaries. |
| **AI Commentary** | Yellow | The AI provides additional analysis or context on top of verified data shown above. Useful but should be read as interpretation, not fact. |
| **On-topic, undefined** | Yellow | Your question is about a Responsible AI topic, but it is not yet covered in the database or glossary. The answer draws on the AI's general knowledge. Consider it informational, not authoritative. |
| **Unverified** | Red | The content involves AI reasoning beyond the database (e.g., research gap analysis) or is outside the scope of UNINOVIS research. Verify before relying on this information. |

### 3.3 Configuration Options

Depending on your role and the deployment setup, you may be able to adjust:

| Option | What It Does |
|--------|-------------|
| **LLM model** | Changes the AI model used for responses. Different models vary in quality, speed, and style. |
| **Prompt level** | **Stringent** -- the agent follows strict rules, stays focused, and includes all guardrails. **Tolerant** -- slightly more flexible responses. **Lax** -- minimal constraints, most conversational. |
| **Transparency level** | **Scaffolded** -- shows reliability banners (green/yellow/red) on each response. **Unscaffolded** -- no banners, clean responses. |
| **Humility level** | Controls how cautiously the agent phrases uncertain information. **Off** -- normal phrasing. **Moderate** -- adds qualifiers like "Based on available information..." **Strict** -- strong hedging + disclaimer. |

### 3.4 Types of Questions You Can Ask

| Category | Example Queries |
|----------|----------------|
| **Topic search** | "Papers on explainable AI", "Studies on AI fairness in healthcare" |
| **Researcher lookup** | "List researchers from THUAS", "Who works on AI ethics?" |
| **Paper listings** | "Show all publications per partner", "Papers from UMA in 2024" |
| **Conceptual definitions** | "What is responsible AI?", "Define algorithmic fairness", "Is XAI related to transparency?" |
| **Research gap analysis** | "What topics have not been studied?", "List any missing research areas" |
| **Project search** | "List research projects on trustworthy AI", "Projects funded in 2023" |
| **Collaboration maps** | "Show a figure of collaborations among the partners", "Collaborations in 2025" |
| **Interactive figures** | "Show a figure of studies on AI and Ethics" (must include the word "figure" or "map") |

**Tip:** To get an interactive map or figure, include the word "figure" or "map" in your question. Without these words, the agent provides text-based answers only.

### 3.5 What the Reliability Badge Means

In the sidebar, you may see a reliability badge showing the agent's current tuning parameters. This is a **procedural badge** -- it describes how the agent is configured (transparency level, prompt strictness, model), not the reliability of any specific answer. For per-response reliability, refer to the colored banners within the response text.
