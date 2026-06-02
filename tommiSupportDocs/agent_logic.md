# Quick Introduction to AI Agents and Agent Workflows

An **AI Agent** is a flexible, autonomous software system that facilitates the interaction between users and computer systems. Unlike traditional applications with rigid interfaces, AI Agents may accept different input types, including natural language, interpret the user's intent, execute the appropriate actions, and deliver results — adapting their behaviour to each situation.

This document first presents a general model for AI Agents. It then shows how each stage of the model is implemented as code components in the **TOMMI Agentic Platform**. Finally, it describes the different types of agents available in the platform.

---

## Part 1 — A General Model for AI Agents

### How do AI Agents work?

According to the classic AI agent framework (Russell & Norvig, 1995), every agent follows three basic stages: Perception → Reasoning → Action. Here, we add a fourth stage — **Production** — to distinguish executing the task (e.g., querying a database, calling a language model) from producing the output (e.g., rendering a map, formatting a table, adding reliability indicators). Thus, according to this proposal, the stages of every AI agent are the following:

```
1. Perception  →  2. Reasoning  →  3. Action  →  4. Production
```

**Note:** This four-stage model is a conceptual abstraction for understanding agent behaviour. In practice, the boundaries between stages may overlap — for example, context retrieval serves both Reasoning (deciding what is relevant) and Action (querying a data store). Simpler agents may have minimal Reasoning, while complex agents may interleave multiple stages. The model is most useful as a framework for *explaining* what an agent does, not as a rigid architectural blueprint.

### Intuitive Examples of Each Stage

| Stage | What happens | Everyday analogy |
|-------|-------------|------------------|
| **1. Perception** | The agent accepts the user's input: a typed question, a button click, a form selection, or a voice command. | A librarian hears your question at the desk. |
| **2. Reasoning** | The agent analyses the input to understand what the user wants and decides which action to take. This may be trivial (pass to the LLM) or complex (classify the query type, select data sources, detect intent). | The librarian decides whether to look in the catalogue, the encyclopaedia, the archives, or simply answer from memory. |
| **3. Action** | The agent executes one or more actions: query a database, search documents, call a language model, generate a chart, compute a result, or decline a request. | The librarian walks to the shelf, finds the book, and reads the relevant passage. |
| **4. Production** | The agent produces the output for the user: text, a table, a map, a chart, or a polite explanation of why it cannot help. A reliability indicator may be added. The output format depends on the interface and the type of result. | The librarian returns to the desk and gives you the answer, noting whether it came from a trusted reference or a less reliable source. |

Not every agent uses artificial intelligence in every stage. Some agents use AI only for Reasoning (understanding the question), others use it only for Action (generating text), and some use no AI at all — relying on rules and structured data throughout.

---

## Part 2 — Technical Implementation in TOMMI

Each stage of the general model maps to specific technical components in the TOMMI platform. This section describes how the four stages are implemented in code.

### From General Model to Code

| Stage | Role | Technical implementation | Key files |
|-------|------|------------------------|-----------|
| **Perception** | Accept and parse user input | The web server receives the HTTP request (text query, session ID, model preference) and routes it to the appropriate agent module. | `web/app.py`, `web/static/app.js` |
| **Reasoning** | Analyse, classify, decide | The agent classifies the query and builds context from the appropriate data source. Ranges from no reasoning (Oneshot) to a 12-step classification chain (Metadata+RAG). This is the agent's **decision logic** — entirely rule-based and deterministic. | `agents/base/rag_metadata_mixin.py`, `agents/base/vectorless_mixin.py`, `config.json` |
| **Action** | Execute the task | Depending on the Reasoning outcome: query SQLite, search papers.json, call the LLM with system prompt + context, generate a map link, or refuse. The LLM call uses the **system prompt** (`prompts.json`) and the **context** built during Reasoning. | `web/llm_client.py`, `prompts.json`, `agents/base/base_RAGagent.py` |
| **Production** | Produce and deliver output | Post-process the LLM response (authority sanitisation, paper verification, humility hedging), assign reliability cues, format for the interface (markdown text, HTML table, Leaflet map, interactive figure), and stream to the user via SSE. | `agents/base/humility.py`, `agents/base/badges.py`, `web/static/app.js` |

### Key Technical Concepts

| Concept | Stage | What it is |
|---------|-------|-----------|
| **System prompt** | Action | Instructions given to the LLM that define the agent's identity, rules, and constraints. Stored in `prompts.json` as three sections: *identity*, *rules*, and *strict*. Only used when the Action stage involves an LLM call. |
| **Context** | Reasoning → Action | Data retrieved from the knowledge base (documents, metadata, glossary) during Reasoning and injected into the LLM prompt during Action. The LLM can only "see" what the context provides — it does not access the database directly. |
| **Classification chain** | Reasoning | A priority-ordered list of checks that the agent runs to determine the query type. Each check tests for a specific pattern (meta-question, topic search, researcher lookup, etc.). The first match wins. Implemented in `rag_metadata_mixin.py`. |
| **Reliability cue** | Production | A coloured banner (🟢 green, 🟡 yellow, 🔴 red, or none) added to the response to indicate the source and trustworthiness of the content. Determined by the query type identified during Reasoning. |
| **Post-processing** | Production | A pipeline of transformations applied to the LLM output before delivery: authority sanitisation, paper verification, humility hedging, and alliance name correction. |
| **Prompt level** | Reasoning + Action | Controls how many prompt sections are active: *stringent* (identity + rules + strict), *tolerant* (identity + rules), or *lax* (identity only). |

### How Reasoning Varies Across Agent Types

The Reasoning stage is where the most significant architectural differences between agent types emerge.

| Agent type | Reasoning implementation | Complexity |
|-----------|------------------------|------------|
| **Oneshot** | **None.** The query is passed directly to the LLM with the system prompt. No classification, no retrieval, no decision-making. | ⬜ |
| **RAG** | **Mechanical retrieval.** The query is converted to a vector embedding and used to find similar document chunks in ChromaDB. | ⬜⬜ |
| **RAG Vectorless** | **Keyword retrieval.** Same as RAG but uses BM25 keyword matching instead of vector similarity. | ⬜⬜ |
| **Text2SQL** | **Intent detection.** The agent checks whether the user is navigating existing results or asking a new question. Navigation is handled without the LLM. | ⬜⬜⬜ |
| **Metadata+RAG (EH)** | **Multi-step classification.** A priority chain of 12 checks determines the query type. Each type is routed to a different data source and action. | ⬜⬜⬜⬜⬜ |

### Comparison Across TOMMI Agent Types

| Stage | Oneshot | RAG | RAG Vectorless | Text2SQL | Metadata+RAG (EH) |
|-------|---------|-----|----------------|----------|-------------------|
| **Perception** | Text | Text | Text | Text | Text |
| **Reasoning** | None | Vector embed | BM25 tokenise | Intent detection (7 types) | Classification chain (12 steps) |
| **Action** | LLM only | ChromaDB → LLM | BM25 → LLM | LLM → SQL → DB | DB / glossary / LLM / maps (varies) |
| **Production** | Text | Text + cues | Text + cues | Text + table + cues | Text + lists + maps + cues |
| **Uses LLM?** | Always | Always | Always | For new queries only | For some query types only |
| **Reliability cues** | Hidden | High / Good / Poor | Yellow / None | Yellow + Green | Green / Yellow / Red / None |

---

## Oneshot Agents (Prompt Assistant)

Oneshot agents process each query independently with no conversation memory, no document retrieval, and no structured data. They rely entirely on the system prompt and the LLM.

### 1. Perception
The agent receives the user's text query via the chat interface. Each query is independent — there is no conversation memory.

### 2. Reasoning
None. The query is passed directly to the LLM without any classification, retrieval, or decision-making. Every query follows exactly the same path.

### 3. Action
The LLM generates a response using only the system prompt (identity + rules) and the user's query. No documents, no database, no external data.

### 4. Production
The LLM's text response is delivered directly to the user. No post-processing, no reliability cues (typically hidden for Oneshot agents).

---

## RAG Agents (Vector-based retrieval)

RAG agents use ChromaDB vector embeddings to find semantically similar document chunks. Unlike BM25 (keyword matching), vector retrieval can find relevant content even when the exact words differ — e.g., "adversarial testing" matches "red-teaming".

### 1. Perception
The agent receives the user's text query via the chat interface.

### 2. Reasoning
The query is converted into a vector embedding and used to search ChromaDB for semantically similar document chunks. This is mechanical — no classification of query type, no decision-making. The retrieval is automatic.

### 3. Action
The retrieved document chunks are injected as context into the system prompt. The LLM generates an answer constrained to this context.

### 4. Production
The LLM response is post-processed (humility hedging, authority sanitisation) and delivered with reliability cues (High / Good / Poor) based on claim-level grounding analysis.

### RAG vs RAG Vectorless

| Feature | RAG (Vector) | RAG Vectorless (BM25) |
|---------|-------------|----------------------|
| Retrieval method | Vector similarity (ChromaDB) | BM25 keyword matching |
| Semantic matching | Yes — "adversarial testing" finds "red-teaming" | No — exact words only |
| Setup | Requires ChromaDB + embedding model | No dependencies — pure Python |
| Index storage | `data/chroma_db/` | `data/chunk_db.json` |
| Best for | Large corpora, semantic queries | Small corpora, keyword-rich queries |

---

## RAG Vectorless Agents (Tommi Tutor, Proyectos Europeos)

RAG Vectorless agents use BM25 keyword retrieval (no vector embeddings) and procedural banner logic. They skip the 12-step classification chain used by Metadata+RAG agents.

### 1. Perception
The agent receives the user's text query via the chat interface.

### 2. Reasoning
The query is tokenised (split into words, stop words removed) and scored against all document chunks using BM25 keyword matching. The top N chunks with the highest scores are selected as context. This is mechanical — no classification of query type.

### 3. Action
The retrieved chunks are injected as context into the system prompt. The LLM generates an answer constrained to this context.

### 4. Production
The first 300 characters of the response are checked for off-topic refusal phrases. If detected, no banner is shown (honest refusal). Otherwise, a yellow "AI Commentary" banner is added.

---

## Text2SQL Agents (Pisha, Algoria)

Text2SQL agents convert natural language to SQL queries. Before calling the LLM, they first check if the user is navigating existing results.

### 1. Perception
The agent receives the user's text query. It also maintains session state (previous SQL, previous results) for navigation and refinement.

### 2. Reasoning — Intent Detection

Before converting a query to SQL, the agent checks whether the user is navigating or refining previous results:

| Intent | Example | Action | Needs LLM? |
|--------|---------|--------|------------|
| **Show more** | "Show me more", "next results" | Display next page | No |
| **Detail request** | "Show details of #3", "expand #5" | Show full details | No |
| **Sort** | "Sort by country A-Z" | Re-sort current results | No |
| **Show field** | "Show language requirements" | Add column | No |
| **Back** | "Go back", "previous search" | Restore previous results | No |
| **Refinement** | "Only those in Italy" | Add WHERE clause | Partial |
| **New query** | "Show agreements with The Hague" | Full Text-to-SQL | Yes |

### 3. Action
For new queries: the LLM translates the natural language question into SQL. The SQL is verified (table/column existence, semantic match) and executed against the SQLite database. For navigation intents: handled directly from session state without the LLM.

### 4. Production
Results are formatted as HTML tables with expandable details. Transparency cues indicate the AI translation risk (yellow) and verified data from the database (green). In Crystal box mode, the SQL query and a plain-language explanation are shown.

### Transparency Levels

| Level | Shows |
|-------|-------|
| Crystal box | SQL query + plain-language explanation + verification badges |
| Black box | Results only |

---

## Metadata+RAG Agents — Excellence Hubs (EH)

The most complex TOMMI agent type, used for the UNINOVIS Excellence Hubs. Combines structured metadata (papers, researchers, projects, glossary) with document retrieval, interactive maps, and a multi-step decision logic.

### 1. Perception
The agent receives the user's text query via the chat interface. It also receives session context (conversation history, session ID, model preference, transparency level).

### 2. Reasoning
This is where the agent's intelligence resides. A priority chain of 12 classification checks determines the query type. The first match wins. Based on the classification, the agent selects the appropriate data source and builds context.

#### Query Classification (priority order)

| Priority | Category | Example query | Reliability cue |
|----------|----------|---------------|-----------------|
| 1 | Meta-question | "What can you do?" | None |
| 2 | Non-research task | "Write an essay" | None |
| 3 | Off-topic | "What's the weather?" | None |
| 4 | Disambiguation follow-up | "1" (after researcher list) | None |
| 5 | Figure/map request | "Show a figure of papers on AI ethics" | 🟢 Green |
| 6 | Gap analysis | "Which topics are least studied?" | 🔴 Red |
| 7 | Conceptual (glossary) | "What is explainable AI?" | 🟡 Yellow |
| 8 | Conceptual (not in glossary) | "What is predictive policing?" | 🟡 Yellow |
| 9 | Follow-up | "Expand on point 1" | 🟡 Yellow |
| 10 | Content query | "Papers on AI ethics from UMA" | Varies |

#### Content Query Context Chain

When the classification reaches step 10 (Content query), the agent runs a second priority chain to decide which data source to use:

| Priority | Type | Example | Source | Cue |
|----------|------|---------|--------|-----|
| 1 | Project query | "What is the TAILOR project?" | project_docs/ | 🟡 |
| 2 | Affiliation listing | "List researchers from THUAS" | researchers.json | 🟡 |
| 3 | Shared topics | "Topics shared by UMA and USPN" | papers.json cross-ref | 🟢 |
| 4 | University papers | "List papers from UMA" | *_papers.json | 🟢 |
| 5 | Topic search | "Papers on AI ethics" | search_papers_by_topic() | 🟢+🟡 |
| 6 | Researcher lookup | "Papers by Rubén González" | researchers.json | None |
| 7 | Fallback: RAG | (any query not caught above) | BM25 / ChromaDB | 🟡 |

#### Researcher Name Matching

| Match level | Condition | Example | Result |
|-------------|-----------|---------|--------|
| Exact match | Full name found | "Rubén González Vallejo" | Show papers directly |
| Surname | Last name (≥4 chars) | "Schleif" | Partial match |
| First + surname | Combined (≥9 chars) | "Rubén González" | Partial match |
| First name only | First name (≥5 chars) | "Rubén" | Partial match |

Partial match results: **1 match** → show papers. **Multiple matches** → disambiguation list. **No match** → fall through to RAG.

### 3. Action
Depends on the query type identified during Reasoning. May include: querying papers.json or researchers.json directly (no LLM), calling the LLM with system prompt + context, generating a map link, building a programmatic factual section, or refusing an off-topic request.

#### Figure/Map Type Selection

| Decision | Map type | Example query |
|----------|----------|---------------|
| About projects + specific topic | PROJECT-TOPIC map | "Figure of projects on trustworthy AI" |
| About projects + no topic | PROJECTS map | "Map of funded projects" |
| About collaborations | COLLABORATION map | "Figure of collaborations on XAI" |
| About papers + specific topic | TOPIC map | "Figure of papers on AI ethics" |
| About papers + no topic | PUBLICATIONS map | "Figure of all publications" |

### 4. Production

The output depends on the query type: it may be formatted text, an interactive map, a structured list, or a refusal. When the output involves LLM-generated text, it passes through a post-processing pipeline:

#### Post-Processing Pipeline

| # | Step | What it does | When active |
|---|------|-------------|-------------|
| 1 | Authority sanitisation | Replaces overconfident phrases (e.g., "has not been studied" → "does not appear in the indexed database") | Always |
| 2 | Alliance name correction | Fixes common LLM misspellings (e.g., "UNINOVOS" → "UNINOVIS") | Always |
| 3 | Paper verification | Checks quoted paper titles against papers.json. Flags unrecognised titles with ⚠️ | Not for meta-questions or off-topic |
| 4 | Unsolicited gap detection | Detects when the LLM volunteers gap analysis the user didn't ask for. Injects a 🔴 red banner. | When user didn't ask about gaps |
| 5 | Off-topic detection | Checks first 300 characters for refusal phrases. Removes banner if detected. | Always (except conceptual) |
| 6 | Humility rewriting | Adds hedging prefixes to ungrounded claims. Moderate: LLM-only claims. Strict: + web claims + disclaimer. | If humility_postprocessing ≠ "off" |

#### Reliability Cue Assignment

| Response type | Cue | Rationale |
|--------------|-----|-----------|
| Programmatic data (structured DB) | 🟢 Green | Data comes directly from the database, no AI involved |
| AI interprets database content | 🟡 Yellow | LLM summarises or formats real data |
| AI uses general knowledge (in-scope) | 🟡 Yellow | Topic is within scope but not in the database |
| AI reasons about absence (gaps) | 🔴 Red | Speculative — verify independently |
| Honest refusal (off-topic, meta, non-research) | None | Refusal is not unreliable content |
| Researcher disambiguation | None | Clarification question, not content |
| Researcher lookup (definitive match) | None | Data from structured database |
| "How many" queries | 🟡 Yellow + note | Counts may be approximate |
