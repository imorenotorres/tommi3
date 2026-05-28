# Deploying with TOMMI -- Developer Guide

> **Who is this document for?**
>
> This guide is **exclusively for IT professionals** — system administrators, DevOps engineers, and software developers responsible for installing, configuring, and maintaining TOMMI in production environments. It requires solid expertise in Python, server administration, environment configuration, Docker/process management, and familiarity with LLM APIs (Mistral, Ollama) and vector databases (ChromaDB).
>
> If you are an end user, see *Using TOMMI Agents*. If you are a tester, see *Testing TOMMI Agents*.

**Target audience:** Software developers and IT staff deploying TOMMI agents.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Project Structure](#project-structure)
5. [Agent Development Lifecycle](#agent-development-lifecycle)
   - [5.1 Phase 1: Planning and Data Preparation](#phase-1-planning-and-data-preparation)
   - [5.2 Phase 2: Agent Creation](#phase-2-agent-creation)
   - [5.3 Phase 3: Testing, Benchmarking, and Red-Teaming](#phase-3-testing-benchmarking-and-red-teaming)
6. [Creating a New Agent](#creating-a-new-agent)
   - [6.1 Using the Web Interface](#using-the-web-interface)
   - [6.2 Manual Creation](#manual-creation)
   - [6.3 Agent Types -- What to Inherit](#agent-types-what-to-inherit)
7. [Configuration Reference](#configuration-reference)
   - [7.1 config.json](#config.json)
   - [7.2 prompts.json](#prompts.json)
   - [7.3 .env Configuration](#env-configuration)
8. [Adding Data](#adding-data)
   - [8.1 RAG Agents](#rag-agents)
   - [8.2 Metadata+RAG Agents](#metadatarag-agents)
   - [8.3 Text2SQL Agents](#text2sql-agents)
9. [Transparency and Reliability Configuration](#transparency-and-reliability-configuration)
10. [LLM Configuration](#llm-configuration)
    - [10.1 Mistral Cloud](#mistral-cloud)
    - [10.2 Ollama (Local)](#ollama-local)
    - [10.3 Per-Agent LLM Override](#per-agent-llm-override)
11. [Running the Service](#running-the-service)
12. [Access Control and Roles](#access-control-and-roles)
13. [Troubleshooting](#troubleshooting)

---

## 1. Overview

TOMMI is an open-source framework for building transparent AI agents. It is designed so that both developers and end-users can understand how responses are generated, what data sources they draw from, and how reliable the output is.

TOMMI supports four agent types:

| Type | Description |
|------|-------------|
| **Oneshot** | Loads all data into LLM context. Best for small knowledge bases (<100 KB). |
| **RAG** | Retrieval-Augmented Generation. Indexes documents into ChromaDB and retrieves relevant chunks per query. |
| **Metadata+RAG (Vector)** | RAG plus structured paper metadata, uses vector embeddings (ChromaDB). |
| **Metadata+RAG (Vectorless)** | Same as above but uses BM25 keyword retrieval instead of vector embeddings. No ChromaDB dependency., publication analytics, topic aggregation, and interactive map visualizations. Designed for multi-institution research analysis. |
| **Text2SQL** | Converts natural language to SQL queries against a SQLite database. |

**Architecture at a glance:**

```
tommi/
├── agents/
│   ├── base/                  # Shared code: base classes, mixins, claims, badges
│   │   ├── __init__.py
│   │   ├── base_RAGagent.py   # BaseRAGAgent: config, ChromaDB, prompt assembly, indexing
│   │   ├── rag_mixin.py       # SimpleRAGMixin: chat/chat_stream for plain RAG
│   │   ├── rag_metadata_mixin.py  # MetadataRAGMixin: chat/stream + metadata, maps, researchers
│   │   ├── claims.py          # ClaimExtractor, GroundingAnalyzer
│   │   ├── badges.py          # ReliabilityBadge, AuditLogger, StudyLogger
│   │   └── humility.py        # HumilityRewriter: post-processing to soften ungrounded claims
│   └── {agent_name}/          # Each agent: thin wrapper + config + prompts + data
│       ├── agent.py           # 5-15 lines: inherits from base classes
│       ├── app.py             # FastAPI wrapper with AGENT_CONFIG
│       ├── config.json        # Agent settings
│       ├── prompts.json       # System prompt sections
│       └── data/              # Documents, metadata, or database
├── web/                       # Central web hub (FastAPI server, frontend)
│   ├── app.py                 # FastAPI server with all API endpoints
│   ├── auth.py                # Authentication, roles, access control, study mode
│   ├── agent_runner.py
│   ├── .env                   # Default LLM configuration
│   ├── data/
│   │   └── tool_access.json   # Role-based tool access configuration
│   └── static/
└── apps/                      # Setup scripts, agent creator, distribution tools
    ├── setup.sh / setup.bat
    └── crear_agente.py
```

The key architectural principle is that `agents/base/` contains all shared logic, while each individual agent directory is a thin configuration layer: an `agent.py` that is typically 5-15 lines of code, a `config.json` for settings, a `prompts.json` for system prompt sections, and a `data/` directory for the agent's knowledge base.

---

## 2. Prerequisites

- **Python 3.11-3.13** (required for RAG and Metadata+RAG agents; ChromaDB is **not compatible** with Python 3.14+)
- **Python 3.10+** is sufficient for Oneshot and Text2SQL agents only
- **Mistral API key** (for cloud LLM) -- obtain one from [https://mistral.ai/](https://mistral.ai/)
- **Ollama** (optional, for local LLM) -- install from [https://ollama.com](https://ollama.com)

If you have Python 3.14+ and need RAG agents:

```bash
brew install python@3.12   # macOS
```

---

## 3. Installation

1. Clone the repository.
2. Run the setup script:

```bash
# Linux/macOS
./apps/setup.sh

# Windows
apps\setup.bat
```

The script creates a virtual environment, installs dependencies, and prompts for your API key.

3. Configure `web/.env` with your LLM provider and API key (see [Section 7.3](#env-configuration)).

---

## 4. Project Structure

Each agent follows a standard directory layout:

```
agents/{your_agent}/
├── agent.py           # Core agent class (thin wrapper inheriting from base)
├── app.py             # FastAPI wrapper with AGENT_CONFIG dict
├── config.json        # Agent configuration (name, topic, universities, thresholds)
├── prompts.json       # System prompt in 3 sections (identity, rules, strict)
├── .env               # (optional) Per-agent LLM overrides
├── .gitignore
└── data/
    ├── docs/          # (RAG, Metadata+RAG) PDF/TXT/MD documents
    ├── *_papers.json  # (Metadata+RAG) Per-university paper metadata
    ├── metadata.json  # (Metadata+RAG) Paper-to-university mapping
    ├── chroma_db/     # (RAG, Metadata+RAG) Auto-generated ChromaDB index
    ├── data.md        # (Oneshot) Single knowledge base file
    └── database.db    # (Text2SQL) SQLite database
```

The `agents/base/` directory provides the building blocks:

| Module | Exports | Purpose |
|--------|---------|---------|
| `base_RAGagent.py` | `BaseRAGAgent` | Core config loading, ChromaDB init, prompt assembly, document indexing, context retrieval, authority sanitization, context quality estimation |
| `rag_mixin.py` | `SimpleRAGMixin` | `chat()` and `chat_stream()` for plain RAG agents (with claim extraction, badges, and humility rewriting) |
| `rag_metadata_mixin.py` | `MetadataRAGMixin` | `chat()` and `chat_stream()` plus metadata search, maps, researchers, topic aggregation, web search, study logging |
| `claims.py` | `ClaimExtractor`, `GroundingAnalyzer` | Claim extraction from LLM responses and grounding analysis against data sources |
| `vectorless_mixin.py` | `VectorlessMixin` | BM25 keyword retrieval replacement for ChromaDB. Enables Metadata+RAG without vector dependencies |
| `badges.py` | `ReliabilityBadge`, `AuditLogger`, `StudyLogger` | Reliability badges, procedural badges, EU AI Act audit logging, and study experiment logging |
| `humility.py` | `HumilityRewriter` | Post-processing module that softens ungrounded claims by adding hedging language. Configurable levels: `off`, `moderate`, `strict` |

---

## 5. Agent Development Lifecycle

Developing a TOMMI agent is a structured process with three distinct phases. Following this lifecycle ensures that the agent is well-designed, properly configured, and robust against misuse before deployment.

| Phase 1 | | Phase 2 | | Phase 3 |
|:-------:|:---:|:-------:|:---:|:-------:|
| **PLANNING & DATA PREPARATION** | ► | **AGENT CREATION** | ► | **TESTING & SAFETY** |
| Analyse use case, choose agent type, collect and pre-process data, define scope | | Create agent in TOMMI (web UI or manual), configure prompts and settings | | Benchmark accuracy, red-team for security, iterate until robust |

### 5.1 Phase 1: Planning and Data Preparation

Before creating the agent in TOMMI, several decisions and preparations are required.

#### 5.1.1 Choose the Agent Type

Select the agent type based on your data and use case:

| Use Case | Recommended Type | When to Choose |
|----------|-----------------|----------------|
| Small knowledge base (<100 KB), simple Q&A | **Oneshot** | FAQ-style agents, policy documents, single manuals |
| Large document collections, full-text search | **RAG** | Regulation repositories, technical documentation, general knowledge bases |
| Multi-institution research with structured metadata (vector embeddings) | **Metadata+RAG (Vector)** | Research paper analysis with semantic search, requires ChromaDB |
| Multi-institution research with structured metadata (no vector DB) | **Metadata+RAG (Vectorless)** | Same as above but uses BM25 keyword retrieval. No ChromaDB dependency. Simpler deployment. |
| Structured database queries | **Text2SQL** | Course catalogs, student records, inventory systems |

**Key considerations:**
- How large is the data? (Oneshot has a ~100 KB limit; RAG and Metadata+RAG scale to thousands of documents)
- Is the data structured (tables, JSON) or unstructured (PDFs, text)?
- Do users need analytics (counts, maps, comparisons) or just information retrieval?
- Do you need real-time updates or is the data static?

#### 5.1.2 Ensure Data Availability

Verify that you have access to the data the agent will use:

- **For RAG agents:** Collect all documents (PDF, TXT, MD). Ensure they are machine-readable (not scanned images without OCR).
- **For Metadata+RAG agents:** You need both documents AND structured metadata (paper lists, researcher profiles, project databases). Sources like OpenAlex, Scopus, or institutional repositories can provide this.
- **For Text2SQL agents:** You need a well-structured database with clear table/column names.

#### 5.1.3 Pre-process Data

Data quality directly impacts agent performance. Follow these guidelines:

**For RAG documents (PDF/TXT/MD):**

| Guideline | Why |
|-----------|-----|
| If possible, remove headers/footers/page numbers from PDFs | They fragment text during chunking |
| Prefer text-based PDFs over scanned images | OCR introduces errors |
| Split very large documents (>50 pages) into logical sections | Improves retrieval precision |
| Use descriptive filenames (e.g., `AI_Ethics_Guidelines_2024.pdf`) | Helps with source attribution |
| Remove duplicate documents | Duplicates dilute retrieval quality |

**For Metadata+RAG structured data (`*_papers.json`):**

The optimal format for paper metadata is one JSON file per university, with this structure:

```json
[
  {
    "id": "W4409459278",
    "title": "Full Paper Title",
    "authors": [
      {"name": "Author Name", "orcid": "0000-0001-..."}
    ],
    "publication_date": "2025-04-15",
    "publication_year": 2025,
    "cited_by_count": 12,
    "abstract": "Full abstract text...",
    "concepts": [
      {"name": "AI Ethics", "score": 0.85},
      {"name": "Fairness", "score": 0.72}
    ],
    "doi": "https://doi.org/10.1007/...",
    "affiliations": ["University Name"],
    "pdf_url": "https://...",
    "local_pdf_path": "docs/W4409459278.pdf"
  }
]
```

**Key rules:**
- Each paper must have a unique `id` field
- The `concepts` array is used for topic search and analytics — ensure it is populated
- The `authors` array links papers to researchers — use consistent name formatting
- If PDFs are available locally, place them in `data/docs/` and reference via `local_pdf_path`

**For Text2SQL databases:**
- Use descriptive column names (`student_name` not `sn`, `enrollment_date` not `ed`)
- Add comments to the schema explaining relationships
- Include representative sample data so the LLM can understand the data model
- Normalize the schema (avoid storing multiple values in a single column)

#### 5.1.4 Define Scope and Prompt Strategy

Before creating the agent, document:

1. **Domain scope:** What topics should the agent answer? What is explicitly out of scope?
2. **Target users:** Researchers? Students? General public? (This affects language and detail level)
3. **Security requirements:** Will the agent be public-facing? Does it handle sensitive data?
4. **Transparency level:** How much should users see about the agent's reasoning? (See Section 9)

### 5.2 Phase 2: Agent Creation

Once planning is complete, create the agent using TOMMI. This can be done via:

- **Web interface** (no coding required) — see [Section 6.1](#using-the-web-interface)
- **Manual file creation** — see [Section 6.2](#manual-creation)
- **Copying an existing agent** and modifying its configuration

The creation process involves:

1. Setting up the agent directory structure (`agents/{agent_id}/`)
2. Configuring `config.json` (agent metadata, universities, scope terms, transparency settings)
3. Writing `prompts.json` (system prompt: identity, rules, strict rules)
4. Adding data files (documents, metadata, database)
5. Configuring the LLM provider (`.env` or per-agent override)
6. Starting the server and verifying the agent loads correctly

**Iterative prompt refinement:** After initial creation, test the agent manually with representative queries. Adjust the system prompt (`prompts.json`) based on observed behavior — particularly the `rules` section which controls scope enforcement, refusal behavior, and hallucination prevention.

### 5.3 Phase 3: Testing, Benchmarking, and Red-Teaming

After the agent is functional, it must be validated for accuracy, reliability, and security before deployment. TOMMI provides two automated tools for this.

#### 5.3.1 Benchmarking (Functional Testing)

The benchmark script (`Benchmark/benchmark.py`) tests the agent's core capabilities:

- **Accuracy:** Does the agent answer correctly when data exists in the database?
- **Scope enforcement:** Does it refuse off-topic queries?
- **Hallucination resistance:** Does it avoid inventing information?
- **Transparency:** Are reliability badges and banners correctly applied?

**Running the benchmark:**

```bash
cd agents/{agent_id}/Benchmark
source venv/bin/activate  # If using a virtual environment
python3 benchmark.py --server http://localhost:8000 --token YOUR_TOKEN
```

Optional flags:
- `--models mistral-small-latest,mistral-large-latest` — test multiple models
- `--output results.xlsx` — specify output filename

**Output:** An Excel report with per-query results, accuracy metrics, and model comparison.

**Writing benchmark queries:** Adapt the `BENCHMARK_QUERIES` list in `benchmark.py` to your agent's domain. Include queries for:
- On-topic questions with known answers (verify accuracy)
- Off-topic questions (verify refusal)
- Edge cases (ambiguous queries, missing data)
- Metadata queries (researcher lookup, paper counts)

#### 5.3.2 Red-Teaming (Security Testing)

The red-team script (`Benchmark/redteam.py`) tests the agent's resistance to adversarial attacks:

| Attack Category | What It Tests |
|----------------|---------------|
| **Prompt Injection** | Can the user override system instructions, hijack the role, or bypass restrictions? |
| **Data Exfiltration** | Can the user extract the system prompt via direct requests, authority claims, completion attacks, or encoding tricks? |
| **Scope Bypass** | Can the user trick the agent into answering off-topic via emotional manipulation, tangential justification, or topic wrapping? |
| **Hallucination Induction** | Can the user make the agent fabricate papers, researchers, or data that don't exist? |
| **Harmful Content** | Can the user extract dangerous tutorials or code for scraping personal data? |
| **Map/Link Injection** | Can the user inject malicious URLs into the agent's responses? |
| **Multi-Turn Escalation** | Can the user gradually shift the agent off-topic across multiple messages? |
| **Encoding & Obfuscation** | Can the user bypass restrictions using language switching, character spacing, or reversed text? |
| **Reliability Manipulation** | Can the user force false reliability indicators? |

**Running the red-team assessment:**

```bash
cd agents/{agent_id}/Benchmark
source venv/bin/activate
python3 redteam.py --server http://localhost:8000 --token YOUR_TOKEN
```

Optional flags:
- `--agent your_agent_id` — specify agent (default: derived from directory)
- `--models mistral-small-latest` — specify model to test
- `--output report.xlsx` — specify output filename

**Output:** An Excel report with:
- **Summary:** Overall robustness score, vulnerability counts by severity
- **By Category:** Success rate per attack category
- **Detailed Results:** Per-query results with response excerpts
- **Recommendations:** Automated suggestions for fixing vulnerabilities

#### 5.3.3 Iterative Hardening

Red-teaming is not a one-time activity. The recommended workflow is:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Run redteam │ ──► │ Analyse      │ ──► │ Fix prompts  │ ──┐
│  script      │     │ report       │     │ or add       │   │
│              │     │              │     │ server-side  │   │
│              │     │              │     │ filters      │   │
└──────────────┘     └──────────────┘     └──────────────┘   │
       ▲                                                      │
       └──────────────────────────────────────────────────────┘
                        Repeat until satisfied
```

**Common fixes by vulnerability type:**

| Vulnerability | Fix Layer | Typical Solution |
|---------------|-----------|-----------------|
| Prompt injection | `prompts.json` | Add explicit role-locking rules ("NEVER change your role...") |
| Data exfiltration | `prompts.json` + server | Add anti-exfiltration rules + output filter for prompt fragments |
| Scope bypass | `prompts.json` | Add per-turn scope enforcement, refuse stories/essays/creative content |
| Hallucination | `prompts.json` + base class | Strengthen "NEVER invent" rules; use `_verify_paper_references()` |
| Link injection | Server (`app.py`) | URL sanitization with domain whitelist |
| Multi-turn escalation | `prompts.json` | "Every message must be evaluated independently for scope" |

**Target robustness scores:**

| Score | Assessment | Action |
|-------|-----------|--------|
| < 60% | Poor | Critical fixes needed before deployment |
| 60–80% | Moderate | Address high/critical vulnerabilities |
| 80–90% | Good | Ready for internal deployment; continue hardening |
| > 90% | Strong | Ready for public-facing deployment |

#### 5.3.4 Pre-Deployment Checklist

Before making the agent available to end users:

- [ ] Benchmark score meets accuracy requirements for the use case
- [ ] Red-team robustness score ≥ 80% (no critical/high vulnerabilities)
- [ ] System prompt does not leak when directly or indirectly requested
- [ ] Agent refuses all off-topic queries, including emotionally framed ones
- [ ] Agent does not hallucinate papers, researchers, or data
- [ ] External URLs cannot be injected into responses
- [ ] Audit logging is enabled (`audit_log_enabled: true`)
- [ ] Appropriate transparency level is configured for the target audience
- [ ] Agent access is restricted to authorized user roles

---

## 6. Creating a New Agent

### Technical Expertise Required to Create AI Agents

**It depends on what you want to build.** TOMMI provides several agent templates (Oneshot, RAG, RAG+Metadata, Text2SQL) that cover the most common use cases. The level of expertise required varies significantly:

1. **Using built-in templates (low expertise):** If your needs match one of the standard TOMMI templates, creating an agent requires no programming skills. You can use the web interface or the CLI tool (`crear_agente.py`) to fill in a form — agent name, description, documents, LLM settings — and the system generates all necessary files automatically. This is accessible to researchers, project managers, and academic staff with a basic understanding of AI concepts (what an LLM is, what prompts do).

2. **Customizing templates (moderate expertise):** If the template does not fully match your requirements, you may need to modify configuration files (`config.json`, `prompts.json`, `.env`) or adjust the system prompt. This requires a good understanding of how the agent works (retrieval, grounding, transparency levels, prompt levels) but not necessarily deep programming expertise.

3. **Building specialized agents (higher expertise):** This is particularly the case for **RAG+Metadata agents**, which have been customized for a specific context in UNINOVIS: the Excellence Hubs. These agents include features like university-level metadata, researcher profiles, cross-university collaboration detection, and publication maps. Replicating or adapting these features for a different institutional context requires understanding the data pipeline and the Python codebase.

4. **Adapting TOMMI with AI coding tools:** An important point is that TOMMI can be extended and customized using advanced AI coding assistants such as **Devstral**. This means that **a good understanding of the AI agents' architecture and behavior — rather than deep coding expertise — is the key requirement** for making significant modifications. A user who understands what the agent should do can use AI coding tools to implement the necessary changes, even without being a professional developer.

In summary: creating a standard agent from a template requires no coding skills; customizing behavior requires understanding the framework; and building entirely new agent types benefits from AI coding tools that lower the traditional programming barrier.

### 6.1 Using the Web Interface

1. Start the web server: `./web/run_html_server.sh` (or `web\run_html_server.bat` on Windows).
2. Go to `http://localhost:8000` and click **"Create Agent"** in the sidebar.
3. Fill in agent type, ID, name, description, welcome message, example queries, system prompt, LLM provider, and model.
4. Click **"Create Agent"**. The new agent is immediately available.

### 6.2 Manual Creation

Step-by-step instructions for creating an agent by hand:

**Step 1 -- Create the directory:**

```bash
mkdir -p agents/{your_agent}/data/docs
```

**Step 2 -- Create `config.json`:**

```json
{
  "agent_id": "your_agent",
  "agent_name": "Your Agent Name",
  "description": "Brief description of what this agent does",
  "welcome_message": "Hello! How can I help you?",
  "example_queries": [
    "What can you do?",
    "Tell me about X"
  ],
  "research_topic": "Your research area (subtopic A, subtopic B, etc.)",
  "prompt_level": "stringent",
  "reliability_cues": "shown",
  "transparency_level": "black_box",
  "audit_log_enabled": true,
  "show_history": false,
  "show_description": true
}
```

For Metadata+RAG agents, also include `alliance` and `universities` (see [Section 7.1](#config.json)).

**Step 3 -- Create `prompts.json`:**

```json
{
  "identity": "You are {agent_name}, a research assistant specialized in {research_topic}...",
  "rules": "IMPORTANT RULES:\n1. Answer based ONLY on retrieved context\n2. If no relevant info, clearly state that\n3. Never make up information...",
  "strict": "CRITICAL CONSTRAINTS:\n..."
}
```

See [Section 7.2](#prompts.json) for the full template placeholder reference.

**Step 4 -- Create `agent.py`:**

For a simple RAG agent (the most common case), the file is just:

```python
"""
Your Agent -- Simple RAG agent.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, SimpleRAGMixin


class Agent(SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
```

For a Metadata+RAG agent:

```python
"""
Your Agent -- RAG+Metadata agent.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, MetadataRAGMixin


class Agent(MetadataRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
```

**Step 5 -- Create `app.py`:**

For RAG+Metadata agents, `app.py` reads configuration from `config.json`:

```python
"""
Your Agent -- FastAPI server (RAG+Metadata)
"""

import os
import json
import urllib.parse
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Load configuration from config.json
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
_config = {}
if os.path.exists(_config_path):
    with open(_config_path, "r", encoding="utf-8") as _f:
        _config = json.load(_f)

AGENT_CONFIG = {
    "id": _config.get("agent_id", os.path.basename(os.path.dirname(__file__))),
    "name": _config.get("agent_name", "RAG+Metadata Agent"),
    "type": "rag_metadata",
    "description": _config.get("description", ""),
    "welcome_message": _config.get("welcome_message", ""),
    "show_history": _config.get("show_history", True),
    "example_queries": _config.get("example_queries", []),
}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    verify: Optional[bool] = None


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    return AGENT_CONFIG


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history, verify=request.verify):
                yield chunk
        return StreamingResponse(generate(), media_type="text/plain")
    response = agent.chat(request.message, request.history, verify=request.verify)
    return ChatResponse(response=response)


@app.post("/reindex")
async def reindex():
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    count = agent.reindex()
    return {"status": "ok", "indexed_chunks": count}


@app.get("/metadata")
async def metadata():
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {"documents": agent.get_metadata_summary()}
```

All agent types (Oneshot, RAG, Text2SQL, RAG+Metadata) now use a `config.json` file for configuration. The agent creation tools (`crear_agente.py` and the web UI) automatically generate this file. For simpler agents (Oneshot, Text2SQL), the `config.json` contains basic settings:

```json
{
  "agent_id": "my_agent",
  "agent_name": "My Agent",
  "type": "rag",
  "description": "Helps with specific tasks",
  "welcome_message": "Hello! How can I help you?",
  "example_queries": ["What can you do?", "Tell me about X"],
  "reliability_cues": "shown",
  "transparency_level": "black_box",
  "prompt_level": "stringent"
}
```

For RAG and RAG+Metadata agents, `config.json` additionally includes `audit_log_enabled` and reliability cues settings. See [Section 7.1](#config.json) for the full reference.

**Step 6 -- Add documents to `data/docs/`:**

Place your PDF, TXT, or MD files in the `data/docs/` directory. They are automatically indexed when the agent first loads (see [Section 8](#adding-data)).

### 6.3 Agent Types -- What to Inherit

The inheritance pattern determines the agent's capabilities. All agents inherit from `BaseRAGAgent` (which handles config, ChromaDB, prompt assembly) plus a mixin for the chat interface:

| Agent Type | Class Declaration |
|------------|-------------------|
| **Simple RAG** | `class Agent(SimpleRAGMixin, BaseRAGAgent): _AGENT_FILE = __file__` |
| **Metadata+RAG (Vector)** | `class Agent(MetadataRAGMixin, BaseRAGAgent): _AGENT_FILE = __file__` |
| **Metadata+RAG (Vectorless)** | `class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent): _AGENT_FILE = __file__` |
| **Custom behavior** | Inherit from `BaseRAGAgent` directly and override `chat()` and `chat_stream()` |

**Custom behavior example:** The `joint_int_programs` agent inherits directly from `BaseRAGAgent` (without a mixin) and implements its own `chat()` and `chat_stream()` methods to add LLM-based grounding verification and token usage tracking:

```python
class Agent(BaseRAGAgent):
    _AGENT_FILE = __file__

    def __init__(self):
        super().__init__()
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        self._token_usage = { ... }

    def chat(self, user_message, history=None, verify=None):
        # Custom logic: retrieve context, call LLM, verify grounding, track tokens
        ...

    async def chat_stream(self, user_message, history=None, verify=None):
        # Custom streaming with grounding verification
        ...
```

This pattern allows any agent to add custom behavior while reusing all the config loading, ChromaDB management, and prompt assembly from `BaseRAGAgent`.

---

## 7. Configuration Reference

### 7.1 config.json

The `config.json` file drives all agent behavior. Below is a complete reference of all supported keys:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `agent_id` | string | Yes | Unique identifier (lowercase, alphanumeric, underscores). Used in URLs and API routes. |
| `agent_name` | string | Yes | Display name in the UI and system prompt. |
| `description` | string | Yes | Short description of the agent's purpose. |
| `welcome_message` | string | Yes | Greeting shown when the agent is selected. |
| `example_queries` | array | Yes | Suggested questions shown in the UI sidebar. |
| `research_topic` | string | Metadata+RAG | Research area description for the LLM system prompt. |
| `alliance` | object | Metadata+RAG | `{ "name": "...", "description": "..." }` -- the institutional network. |
| `universities` | object | Metadata+RAG | Map of acronym to `{ "name", "country", "lat", "lon" }`. Coordinates are used for map visualizations. |
| `gap_analysis_examples` | string | Metadata+RAG | Comma-separated example subtopics for gap analysis prompts. |
| `prompt_level` | string | No | `"stringent"` (all 3 prompt sections), `"tolerant"` (identity + rules), or `"lax"` (identity only). Default: `"stringent"`. |
| `reliability_cues` | string | No | `"shown"` (coloured banners visible) or `"hidden"` (no banners). Controls procedural reliability banners (green/yellow/red). Applies to all agents. Default: `"shown"`. |
| `transparency_level` | string | No | `"crystal_box"` (SQL queries and sources visible) or `"black_box"` (hidden). Only applicable to Text2SQL agents. Default: `"black_box"`. |
| `reliability_display` | string | No | `"visual"` (badge only), `"text_style"` (inline hedging), `"both"`, or `"none"`. Default: `"visual"`. |
| `audit_log_enabled` | boolean | No | Enable/disable the JSONL audit log in `data/audit_log.jsonl`. Default: `false`. |
| `web_search` | object | No | Web search expansion config. When configured, the agent offers to search the web when local results are insufficient. See below. |
| `show_history` | boolean | No | Display query history in the sidebar. Default: `true`. |
| `show_description` | boolean | No | Show the agent description in the UI. Default: `true`. |
| `rag_domain_keywords` | array | No | Domain-specific keywords for `similarity_test.py` calibration. |
| `rag_keyword_boost` | number | No | Similarity boost per keyword match. |

**Full example (Metadata+RAG agent):**

```json
{
  "agent_id": "robotics_ai",
  "agent_name": "EH: AI & Robotics",
  "description": "Research assistant for THWS AI & Robotics Excellence Hub",
  "welcome_message": "Hello! I am a research assistant specialized in UNINOVIS AI & Robotics research.",
  "research_topic": "AI & Robotics (intelligent automation, human-robot interaction, Industry 4.0, etc.)",
  "show_history": false,
  "example_queries": [
    "**Show a figure** with all the publications per partner",
    "**List researchers** that have interest in autonomous systems",
    "**List the AI & Robotics subtopics** MOST studied in UNINOVIS"
  ],
  "alliance": {
    "name": "UNINOVIS",
    "description": "UNINOVIS is a European university alliance focused on enhancing education, research, and innovation in applied data science."
  },
  "universities": {
    "UMA": {"name": "Universidad de Malaga", "country": "Spain", "lat": 36.7213, "lon": -4.4214},
    "THWS": {"name": "Technical University of Applied Sciences", "country": "Germany", "lat": 49.7913, "lon": 9.9534}
  },
  "gap_analysis_examples": "autonomous navigation, swarm robotics, soft robotics, human-robot collaboration",
  "prompt_level": "stringent",
  "reliability_cues": "shown",
  "transparency_level": "black_box",
  "audit_log_enabled": true
}
```

### 7.2 prompts.json

The system prompt is split into three sections in `prompts.json`. Which sections are included depends on `prompt_level` in `config.json`:

| `prompt_level` | Sections used |
|----------------|---------------|
| `stringent` | identity + rules + strict |
| `tolerant` | identity + rules |
| `lax` | identity only |

**Template placeholders:** The following placeholders are automatically replaced at runtime with values from `config.json`:

| Placeholder | Replaced with |
|-------------|---------------|
| `{agent_name}` | `config.agent_name` |
| `{description}` | `config.description` |
| `{research_topic}` | `config.research_topic` |
| `{alliance_name}` | `config.alliance.name` |
| `{alliance_name_upper}` | `config.alliance.name` (uppercased) |
| `{alliance_desc}` | `config.alliance.description` |
| `{num_universities}` | Number of entries in `config.universities` |
| `{uni_list}` | Formatted list of universities with names and countries |
| `{acronym_list}` | Comma-separated university acronyms |
| `{agent_id}` | `config.agent_id` |
| `{gap_examples}` | `config.gap_analysis_examples` |

**Example `prompts.json`:**

```json
{
  "identity": "You are {agent_name}, a research assistant specialized in {research_topic} papers from the {alliance_name} European university alliance.\n\n{alliance_name_upper} ALLIANCE CONTEXT:\n{alliance_desc} It consists of {num_universities} universities:\n{uni_list}\n\nIMPORTANT: When users refer to university acronyms ({acronym_list}), use the mapping above.",

  "rules": "IMPORTANT RULES:\n1. Answer questions based ONLY on the context retrieved from your document database\n2. If the retrieved context doesn't contain relevant information, clearly state that\n3. Never make up or infer information not present in the provided context\n4. When citing sources, include the document title, authors, and university\n5. Use the same language as the user's question",

  "strict": "CRITICAL CONSTRAINTS:\n..."
}
```

### 7.3 .env Configuration

The file `web/.env` sets default configuration for **all** agents. Individual agents can override these defaults by creating their own `.env` file (see [Section 10.3](#per-agent-llm-override)).

**Primary variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM backend to use | `mistral` or `ollama` |
| `MISTRAL_API_KEY` | API key for Mistral Cloud | `your_api_key_here` |
| `MISTRAL_MODEL` | Mistral model name | `mistral-large-latest` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `mistral` |
| `AVAILABLE_MODELS` | Comma-separated list of cloud models for cycling | `mistral-large-latest,mistral-small-latest` |
| `RAG_APPROACH` | Chunking strategy | `basic`, `context_preserving`, or `custom` |
| `ENABLE_LOGGING` | Enable conversation logging (testing only) | `true` or `false` |

**RAG chunking variables (only when `RAG_APPROACH=custom`):**

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_CHUNK_SIZE` | 2000 | Characters per chunk |
| `RAG_CHUNK_OVERLAP` | 400 | Overlap between chunks |
| `RAG_RETRIEVE_CHUNKS` | 8 | Number of chunks to retrieve per query |
| `RAG_CHUNKING_STRATEGY` | `smart` | `fixed` or `smart` (smart cuts at paragraph/sentence boundaries) |

**Default `web/.env` template:**

```bash
# ============================================
# DEFAULT LLM Provider Configuration
# ============================================

# --- Cloud LLM (Mistral) - DEFAULT ---
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_api_key_here
MISTRAL_MODEL=mistral-large-latest

# --- To use Local LLM (Ollama) as default, comment above and uncomment below ---
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=mistral

# --- RAG Chunking ---
RAG_APPROACH=context_preserving

# --- Logging (testing only) ---
ENABLE_LOGGING=false
```

---

## 8. Adding Data

### 8.1 RAG Agents

Place PDF, TXT, or MD files in `data/docs/`. Documents are automatically indexed on first load and auto-synced on subsequent loads:

- **New files** are indexed without re-indexing existing ones.
- **Deleted files** are removed from the index.
- **No changes** = fast startup.

Supported formats: `.txt`, `.md`, `.pdf`

**Chunking strategies:**

| Approach | Chunk Size | Overlap | Retrieved | Strategy | Best For |
|----------|-----------|---------|-----------|----------|----------|
| `basic` | 500 chars | 100 chars | 3 chunks | Fixed cut | Small documents, quick indexing |
| `context_preserving` | 2000 chars | 400 chars | 8 chunks | Smart boundaries | Dense documents (PDFs, manuals, regulations) |
| `custom` | Configurable | Configurable | Configurable | Configurable | Fine-tuning for specific use cases |

**Force a complete re-index:**

```bash
# Via API
curl -X POST http://localhost:8000/api/agents/<agent_id>/reindex

# Or delete ChromaDB and restart
rm -rf agents/<agent_id>/data/chroma_db/
```

**After changing RAG configuration** (chunk size, approach, etc.), you must delete the ChromaDB folder and restart to re-index with the new settings.

### 8.2 Metadata+RAG Agents

Metadata+RAG agents use everything from RAG agents (documents in `data/docs/`) plus structured metadata files:

| File | Purpose |
|------|---------|
| `data/docs/*.pdf` | Full-text PDF documents indexed into ChromaDB |
| `data/{UNI}_papers.json` | Per-university paper metadata (one file per university acronym) |
| `data/metadata.json` | Maps paper IDs to universities; provides paper counts |
| `data/institution_ids.json` | University identifiers (e.g., OpenAlex IDs, ROR) |

**Example `UMA_papers.json`:**

```json
[
  {
    "id": "W4409459278",
    "title": "Implementing ethical principles in AI",
    "authors": [{"name": "John Smith", "orcid": null}],
    "publication_date": "2025-04-15",
    "publication_year": 2025,
    "cited_by_count": 3,
    "abstract": "In recent years...",
    "concepts": [
      {"name": "Engineering ethics", "score": 0.44},
      {"name": "Artificial intelligence", "score": 0.38}
    ],
    "doi": "https://doi.org/10.1007/...",
    "affiliations": ["Universidad de Malaga"]
  }
]
```

**Example `metadata.json`:**

```json
{
  "collection_date": "2026-03-18T09:25:06",
  "universities": {
    "UMA": {
      "name": "Universidad de Malaga",
      "papers_count": 50,
      "papers": [{"id": "W4409459278", "title": "...", "authors": []}]
    }
  },
  "total_papers": 183
}
```

**Creating a new Metadata+RAG agent for a different topic:**

```bash
# 1. Copy an existing agent
cp -r agents/responsible_ai agents/my_new_topic

# 2. Edit config.json (agent_id, agent_name, research_topic, universities, etc.)
nano agents/my_new_topic/config.json

# 3. Replace data files
rm agents/my_new_topic/data/docs/*.pdf
rm agents/my_new_topic/data/*_papers.json
# Add your own PDFs, papers.json files, and metadata.json

# 4. Delete old ChromaDB index
rm -rf agents/my_new_topic/data/chroma_db/

# 5. Restart the server -- the new agent is auto-detected
```

No Python code changes are required.

### 8.3 Text2SQL Agents

Text2SQL agents require a SQLite database at `data/database.db`.

**Create from a SQL script:**

```bash
cd agents/your_agent/data
sqlite3 database.db < schema.sql
```

**Example `schema.sql`:**

```sql
CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    year INTEGER,
    credits INTEGER
);

INSERT INTO courses VALUES (1, 'Introduction to Law', 'Law', 1, 6);
INSERT INTO courses VALUES (2, 'Constitutional Law', 'Law', 2, 6);
```

The agent automatically reads the database schema at startup. Well-designed table and column names (e.g., `student_name` instead of `sn`) help the LLM generate more accurate SQL queries.

**Security:** Only SELECT queries are allowed. INSERT, UPDATE, DELETE, DROP, and other modifying operations are blocked.

---

## 9. Transparency and Reliability Configuration

TOMMI implements a Graduated Transparency framework aligned with the EU AI Act (Articles 12-14), the NIST AI Risk Management Framework, and the OECD AI Principles.

### Reliability Cues (Coloured Banners)

TOMMI uses **reliability cues** — coloured banners prepended to each response that indicate the data source and reliability of the information:

| Banner | Colour | Meaning |
|--------|--------|---------|
| 🟢 **Verified data** | Green | Response generated directly from structured database data (no AI interpretation involved) |
| 🟡 **AI interpretation** | Yellow | Response generated by the AI model based on database documents (may contain approximate groupings) |
| 🟡 **On-topic, undefined** | Yellow | Topic is within the agent's domain but not yet covered by specific papers in the database |
| 🔴 **Unverified** | Red | Question is outside the scope of the research database |

**Configuration:** Set `reliability_cues: "shown"` in `config.json`. Set to `"hidden"` to disable banners.

Reliability cues can be toggled live by clicking the badge icon in the web UI. The change takes effect immediately but resets to the `config.json` default on server restart.

### Content Transparency (Text2SQL Only)

For Text2SQL agents, an additional `transparency_level` parameter controls whether the SQL query and its natural-language translation are shown to the user:

- `"crystal_box"` — SQL queries and source details are visible
- `"black_box"` — no process disclosure

**Configuration:** Set `transparency_level: "crystal_box"` in `config.json`. This parameter only applies to Text2SQL agents.

### Authority Sanitization

`BaseRAGAgent` automatically replaces authoritative phrases in LLM responses to avoid overstating certainty:

| Original phrase | Replaced with |
|----------------|---------------|
| "has not been studied" | "does not appear in the indexed database" |
| "well-known" | "commonly discussed" |
| "it is clear that" | "the data suggests that" |
| "clearly" | "notably" |
| "widely recognized" | "commonly discussed" |

This happens automatically for all agents.

### Audit Logging

When `audit_log_enabled` is `true`, every query generates a JSON line in `data/audit_log.jsonl`:

```json
{
  "timestamp": "2026-04-01T10:30:45.123456+00:00",
  "agent_id": "responsible_ai",
  "query": "List researchers that have interest in AI and Ethics",
  "query_type": "normal",
  "source_type": "Metadata",
  "context_sources": ["researcher", "metadata"],
  "reliability_cues": "shown"
}
```

The JSONL format is append-only and processable with standard tools (`jq`, `grep`, pandas). For production, use standard log rotation (e.g., `logrotate`).

---

## 10. LLM Configuration

### 10.1 Mistral Cloud

Set in `web/.env`:

```bash
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_api_key_here
MISTRAL_MODEL=mistral-large-latest
```

Available models:

| Model | Use Case |
|-------|----------|
| `mistral-large-latest` | Best quality, complex reasoning (default) |
| `mistral-medium-latest` | Balanced performance |
| `mistral-small-latest` | Fast responses, simple tasks |

### 10.2 Ollama (Local)

1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull a model: `ollama pull mistral`
3. Ensure Ollama is running: `ollama serve`
4. Configure `web/.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

For better local quality, try larger models:

```bash
ollama pull mixtral:8x7b
# Then set OLLAMA_MODEL=mixtral:8x7b in .env
```

### 10.3 Per-Agent LLM Override

Keep Mistral as the default in `web/.env`, and override for specific agents by creating `agents/{your_agent}/.env`:

```bash
# This agent uses Ollama instead of the default Mistral
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

An agent's `.env` only overrides the default if it contains `LLM_PROVIDER`. If `LLM_PROVIDER` is absent or commented out, the agent falls back to `web/.env`.

**Hybrid deployment example:**

| Agent | Has `LLM_PROVIDER` in .env? | Provider Used |
|-------|------------------------------|---------------|
| `conf26_cloud` | No | Default (Mistral Cloud) |
| `conf26_local` | `LLM_PROVIDER=ollama` | Ollama (local) |
| `pisha` | `LLM_PROVIDER=mistral` + large model | Mistral Cloud (mistral-large) |

After changing any `.env` configuration, restart the web server.

---

## 11. Running the Service

Start the web hub:

```bash
# Linux/macOS
./web/run_html_server.sh

# Windows
web\run_html_server.bat

# Or manually with auto-reload (development)
cd web && uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Default address: `http://localhost:8000`

**API endpoints (all agents):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents` | GET | List all available agents |
| `/api/chat` | POST | Send a chat message |
| `/api/chat/stream` | GET | Stream a chat response |
| `/api/agents/<id>/init` | POST | Initialize an agent |
| `/api/agents/<id>/reindex` | POST | Re-index RAG documents |
| `/api/agents/<id>/config` | GET | Get agent config (includes `llm_provider` and `llm_model`) |

**Additional endpoints (Metadata+RAG only):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/<id>/metadata` | GET | Document metadata |
| `/api/agents/<id>/topic-search?topic=X` | GET | Search papers by topic (JSON) |
| `/api/agents/<id>/topic-map?topic=X` | GET | Interactive topic map (HTML) |
| `/api/agents/<id>/publications-search` | GET | All papers by university (JSON) |
| `/api/agents/<id>/publications-map` | GET | Publications map (HTML) |
| `/api/agents/<id>/collaboration-search` | GET | Collaboration data (JSON) |
| `/api/agents/<id>/collaboration-map` | GET | Collaboration map (HTML) |

**LLM management endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/llm-models` | GET | Get available models for a provider (Ollama or Mistral) |
| `/api/agents/<id>/llm-provider` | PUT | Update LLM provider and model for a specific agent |

**Agent visibility and configuration (superuser/tester):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/visibility` | GET | Get visibility config for all agents |
| `/api/agents/<id>/visibility` | PUT | Set visibility level (`hidden`, `restricted`, `open`) and allowed users |

**Tool access control (superuser only):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tool-access` | GET | Get current tool access configuration |
| `/api/tool-access` | PUT | Update role-based tool access |

**Log analytics:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/logs/summary` | GET | Aggregated request/visitor stats (period: `hour`, `day`, `3days`, `week`; custom `start`/`end`) |
| `/api/logs/files` | GET | List all log files with metadata |
| `/api/logs/content` | GET | Return parsed log file content |
| `/api/logs/<filename>` | DELETE | Delete a log file |

**Study mode (experimental design):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/study/status` | GET | Get study mode status and condition assignments |
| `/api/study/enable` | POST | Enable study mode (randomized assignment) |
| `/api/study/disable` | POST | Disable study mode |
| `/api/study/reset` | POST | Clear all study assignments |
| `/api/study/enroll/<username>` | POST | Manually enroll a user as study participant |
| `/api/study/enroll-bulk` | POST | Bulk enroll multiple users |
| `/api/study/queries` | GET | Return predefined study queries |
| `/api/study/questionnaire` | POST | Save per-query questionnaire responses |
| `/api/study/comparison` | POST | Save within-subjects comparison results |
| `/api/study/complete` | POST | Mark user's study as completed |
| `/study` | GET | Study interface page |

**Testing with curl:**

```bash
# List agents
curl http://localhost:8000/api/agents

# Chat with an agent
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "your_agent", "message": "Hello"}'

# Reindex
curl -X POST http://localhost:8000/api/agents/your_agent/reindex
```

**Freeing a port in use:**

```bash
# Find and kill the process using the port
lsof -i :8000                # Linux/macOS — find the PID
kill <PID>                   # Then kill it

netstat -ano | findstr :8000  # Windows — find the PID
taskkill /PID <PID> /F       # Then kill it
```

---

## 12. Access Control and Roles

TOMMI implements a role-based access control system. Each user is assigned one or more roles that determine what tools, agents, and features they can access.

### Roles

| Role | Level | Description |
|------|-------|-------------|
| `superuser` | 4 | Full system access: user management, agent configuration, tool visibility, study mode, log analytics |
| `tester` | 2 | Agent testing: can access all agents (including cloud LLM), structured error reporting, settings panel |
| `admin_staff` | 2 | Administrative staff: access to directory, event calendar, mobility planner, intranet services |
| `teaching_staff` | 2 | Teaching staff: access to research tools, researcher connect, TOMMI agents |
| `student` / `user` | 1 | Basic access: only agents with local LLM (Ollama), student-specific tools |

### Tool Access Configuration

Tool access is configured in `web/data/tool_access.json`. This file maps tool IDs to the roles that can access them. Example:

```json
{
  "directory": ["admin_staff", "teaching_staff", "tester", "superuser"],
  "tommi_agents": ["teaching_staff", "tester", "superuser"],
  "student_admin": ["student", "tester", "superuser"],
  "virtual_campus": ["student", "teaching_staff", "superuser"]
}
```

Tool access can also be managed at runtime through the web interface settings panel (superuser only) or via the `/api/tool-access` API endpoint.

### Agent Visibility

Agents can be configured with three visibility levels:

| Level | Description |
|-------|-------------|
| `open` | Visible to all users with access to TOMMI agents |
| `restricted` | Visible only to users in the allowed list |
| `hidden` | Not visible in the agent selector |

Agent visibility is managed via the settings panel or the `/api/agents/<id>/visibility` API endpoint.

### Self-Registration and Access Requests

Users from UNINOVIS partner institutions can request access via a self-registration form on the login page. The system validates that the email belongs to a recognized UNINOVIS partner domain. Access requests are stored in `web/data/access_requests.json` and must be approved by a superuser.

---

## 13. Troubleshooting

TOMMI uses structured error codes. When an error occurs, look for "Error XXX" in the output and consult the tables below.

### Error Code Structure

| Range | Category |
|-------|----------|
| 1xx | LLM connection |
| 2xx | Agent configuration/loading |
| 3xx | Data/ChromaDB |
| 5xx | Server |

### LLM Connection Errors (1xx)

| Code | Error | Solution |
|------|-------|----------|
| 101 | Ollama is not running | Install Ollama; run `ollama serve` |
| 102 | Model not found in Ollama | Run `ollama pull <model_name>` |
| 103 | Ollama returned an error | Check Ollama logs; restart service |
| 104 | Ollama timeout | Verify Ollama is running: `ollama serve` |
| 105 | MISTRAL_API_KEY not configured | Add `MISTRAL_API_KEY=your_key` to `.env` |
| 106 | Invalid Mistral API key | Get a new key at https://console.mistral.ai |
| 107 | Mistral API error | Check https://status.mistral.ai |
| 108 | Cannot connect to Mistral | Check internet connection |
| 109 | Unknown LLM error | Check server logs |

### Agent Errors (2xx)

| Code | Error | Solution |
|------|-------|----------|
| 201 | Agent not found | Verify the agent folder exists in `agents/` |
| 202 | Agent file not found | Ensure directory contains `agent.py` and `app.py` |
| 203 | Invalid agent configuration | Check `AGENT_CONFIG` syntax in `app.py` |
| 204 | Agent not initialized | Restart server; check initialization logs |
| 205 | Failed to load agent | Check agent Python code for syntax/import errors |

### Data Errors (3xx)

| Code | Error | Solution |
|------|-------|----------|
| 301 | Data file not found | Create `data/data.md` with knowledge base content |
| 302 | No documents in docs folder | Add `.txt`, `.md`, or `.pdf` files to `data/docs/` |
| 303 | PDF extraction error | Verify PDF opens correctly; run `pip install pypdf` |
| 304 | ChromaDB error | Delete `data/chroma_db/` and call `/reindex` |
| 305 | Database not found | Create or copy database to `data/database.db` |
| 306 | Context too large | Reduce `data/data.md` size or switch to RAG |
| 307 | ChromaDB Python incompatible | Install Python 3.12 or 3.13 and recreate `.venv` |

### Server Errors (5xx)

| Code | Error | Solution |
|------|-------|----------|
| 501 | Streaming error | Check server logs |
| 502 | Session not found | Start a new conversation |
| 503 | Internal server error | Check server logs; restart |
| 504 | Port in use | Find and kill the process: `lsof -i :8000` then `kill <PID>` |

### General Debugging

```bash
# Check Python version (must be 3.11-3.13 for RAG)
python --version

# Verify virtual environment is active
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows

# Test Ollama
ollama list
ollama run mistral "Hello"

# Test agent via CLI before web interface
cd web && python cli.py <agent_id>

# Check which process uses a port
lsof -i :8000                # Linux/macOS
netstat -ano | findstr :8000  # Windows

# View server logs with auto-reload
cd web && uvicorn app:app --reload
```
