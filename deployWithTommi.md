# Deploying with TOMMI -- Developer Guide

**Target audience:** Software developers and IT staff deploying TOMMI agents.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Project Structure](#4-project-structure)
5. [Creating a New Agent](#5-creating-a-new-agent)
   - [5.1 Using the Web Interface](#51-using-the-web-interface)
   - [5.2 Manual Creation](#52-manual-creation)
   - [5.3 Agent Types -- What to Inherit](#53-agent-types----what-to-inherit)
6. [Configuration Reference](#6-configuration-reference)
   - [6.1 config.json](#61-configjson)
   - [6.2 prompts.json](#62-promptsjson)
   - [6.3 .env Configuration](#63-env-configuration)
7. [Adding Data](#7-adding-data)
   - [7.1 RAG Agents](#71-rag-agents)
   - [7.2 Metadata+RAG Agents](#72-metadatarag-agents)
   - [7.3 Text2SQL Agents](#73-text2sql-agents)
8. [Transparency and Reliability Configuration](#8-transparency-and-reliability-configuration)
9. [LLM Configuration](#9-llm-configuration)
   - [9.1 Mistral Cloud](#91-mistral-cloud)
   - [9.2 Ollama (Local)](#92-ollama-local)
   - [9.3 Per-Agent LLM Override](#93-per-agent-llm-override)
10. [Running the Service](#10-running-the-service)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

TOMMI is an open-source framework for building transparent AI agents. It is designed so that both developers and end-users can understand how responses are generated, what data sources they draw from, and how reliable the output is.

TOMMI supports four agent types:

| Type | Description |
|------|-------------|
| **Oneshot** | Loads all data into LLM context. Best for small knowledge bases (<100 KB). |
| **RAG** | Retrieval-Augmented Generation. Indexes documents into ChromaDB and retrieves relevant chunks per query. |
| **Metadata+RAG** | RAG plus structured paper metadata, publication analytics, topic aggregation, and interactive map visualizations. Designed for multi-institution research analysis. |
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
│   │   └── badges.py          # ReliabilityBadge, AuditLogger
│   └── {agent_name}/          # Each agent: thin wrapper + config + prompts + data
│       ├── agent.py           # 5-15 lines: inherits from base classes
│       ├── app.py             # FastAPI wrapper with AGENT_CONFIG
│       ├── config.json        # Agent settings
│       ├── prompts.json       # System prompt sections
│       └── data/              # Documents, metadata, or database
├── web/                       # Central web hub (FastAPI server, frontend)
│   ├── app.py
│   ├── agent_runner.py
│   ├── .env                   # Default LLM configuration
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

3. Configure `web/.env` with your LLM provider and API key (see [Section 6.3](#63-env-configuration)).

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
| `base_RAGagent.py` | `BaseRAGAgent` | Core config loading, ChromaDB init, prompt assembly, document indexing, context retrieval |
| `rag_mixin.py` | `SimpleRAGMixin` | `chat()` and `chat_stream()` for plain RAG agents (with claim extraction and badges) |
| `rag_metadata_mixin.py` | `MetadataRAGMixin` | `chat()` and `chat_stream()` plus metadata search, maps, researchers, topic aggregation |
| `claims.py` | `ClaimExtractor`, `GroundingAnalyzer` | Claim extraction from LLM responses and grounding analysis against data sources |
| `badges.py` | `ReliabilityBadge`, `AuditLogger` | Traffic-light reliability badges and EU AI Act audit logging |

---

## 5. Creating a New Agent

### 5.1 Using the Web Interface

1. Start the web server: `./web/run_html_server.sh` (or `web\run_html_server.bat` on Windows).
2. Go to `http://localhost:8000` and click **"Create Agent"** in the sidebar.
3. Fill in agent type, ID, name, description, welcome message, example queries, system prompt, LLM provider, and model.
4. Click **"Create Agent"**. The new agent is immediately available.

### 5.2 Manual Creation

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
  "transparency_level": "development",
  "audit_log_enabled": true,
  "reliability_green_max_llm": 20,
  "reliability_red_min_llm": 50,
  "show_history": false,
  "show_description": true
}
```

For Metadata+RAG agents, also include `alliance` and `universities` (see [Section 6.1](#61-configjson)).

**Step 3 -- Create `prompts.json`:**

```json
{
  "identity": "You are {agent_name}, a research assistant specialized in {research_topic}...",
  "rules": "IMPORTANT RULES:\n1. Answer based ONLY on retrieved context\n2. If no relevant info, clearly state that\n3. Never make up information...",
  "strict": "CRITICAL CONSTRAINTS:\n..."
}
```

See [Section 6.2](#62-promptsjson) for the full template placeholder reference.

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

For simpler agent types (Oneshot, RAG, Text2SQL), `AGENT_CONFIG` is defined inline in `app.py` instead of reading from `config.json`:

```python
AGENT_CONFIG = {
    "id": "my_agent",
    "name": "My Agent",
    "type": "rag",  # or "oneshot", "text2sql"
    "description": "Helps with specific tasks",
    "welcome_message": "Hello! How can I help you?",
    "example_queries": [
        "What can you do?",
        "Tell me about X"
    ]
}
```

**Step 6 -- Add documents to `data/docs/`:**

Place your PDF, TXT, or MD files in the `data/docs/` directory. They are automatically indexed when the agent first loads (see [Section 7](#7-adding-data)).

### 5.3 Agent Types -- What to Inherit

The inheritance pattern determines the agent's capabilities. All agents inherit from `BaseRAGAgent` (which handles config, ChromaDB, prompt assembly) plus a mixin for the chat interface:

| Agent Type | Class Declaration |
|------------|-------------------|
| **Simple RAG** | `class Agent(SimpleRAGMixin, BaseRAGAgent): _AGENT_FILE = __file__` |
| **Metadata+RAG** | `class Agent(MetadataRAGMixin, BaseRAGAgent): _AGENT_FILE = __file__` |
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

## 6. Configuration Reference

### 6.1 config.json

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
| `transparency_level` | string | No | `"development"` (full detail), `"production"` (minimal), or `"opaque"` (no transparency shown). Default: `"development"`. |
| `audit_log_enabled` | boolean | No | Enable/disable the JSONL audit log in `data/audit_log.jsonl`. Default: `false`. |
| `reliability_green_max_llm` | integer | No | Maximum LLM % for green badge (High reliability). Default: `20`. |
| `reliability_red_min_llm` | integer | No | Minimum LLM % for red badge (Poor reliability). Default: `50`. |
| `inline_claim_highlights` | object | No | Claim highlighting config (see [Section 8](#8-transparency-and-reliability-configuration)). |
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
  "transparency_level": "development",
  "audit_log_enabled": true,
  "reliability_green_max_llm": 20,
  "reliability_red_min_llm": 50,
  "inline_claim_highlights": {
    "enabled": true,
    "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
    "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
    "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
    "show_legend": true
  }
}
```

### 6.2 prompts.json

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

### 6.3 .env Configuration

The file `web/.env` sets default configuration for **all** agents. Individual agents can override these defaults by creating their own `.env` file (see [Section 9.3](#93-per-agent-llm-override)).

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

## 7. Adding Data

### 7.1 RAG Agents

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

### 7.2 Metadata+RAG Agents

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

### 7.3 Text2SQL Agents

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

## 8. Transparency and Reliability Configuration

TOMMI implements a Graduated Transparency framework aligned with the EU AI Act (Articles 12-14), the NIST AI Risk Management Framework, and the OECD AI Principles.

### Transparency Levels

Set via `transparency_level` in `config.json`:

| Level | Badge & breakdown | Confidence | Inline highlights | Audit log |
|-------|-------------------|------------|-------------------|-----------|
| `development` | Full source % breakdown | With claim count | Colour-coded per claim | Active |
| `production` | Label only (High/Good/Poor) | Percentage only | Hidden | Active |
| `opaque` | Hidden | Hidden | Hidden | Active |

Transparency can be switched live by clicking the badge in the web UI (cycles through development -> production -> opaque). The change takes effect immediately but resets to the `config.json` default on server restart.

### Reliability Badges

The reliability badge uses a traffic-light colour scheme based on how much of the response is LLM-generated:

| Colour | Label | Condition |
|--------|-------|-----------|
| Green | **Reliability: High** | LLM % <= `reliability_green_max_llm` (default: 20%) |
| Yellow | **Reliability: Good** | LLM % between green and red thresholds |
| Red | **Reliability: Poor** | LLM % >= `reliability_red_min_llm` (default: 50%) |

### Inline Claim Highlights

When `transparency_level` is `development` and `inline_claim_highlights.enabled` is `true`, individual claims in the response are colour-coded by source:

**RAG+Metadata agents (3-tier):**

| Colour | Source | Config key |
|--------|--------|------------|
| Green | Metadata (structured data) | `metadata_style` |
| Yellow | Database (RAG chunks) | `database_style` |
| Red (italic) | LLM (ungrounded) | `llm_style` |

**RAG agents (2-tier):**

| Colour | Source | Config key |
|--------|--------|------------|
| Green | Grounded (RAG chunks) | `grounded_style` |
| Red (italic) | LLM (ungrounded) | `ungrounded_style` |

**Configuration example:**

```json
{
  "inline_claim_highlights": {
    "enabled": true,
    "metadata_style": "background-color:#d4edda;padding:1px 3px;border-radius:3px;border-bottom:2px solid #28a745;",
    "database_style": "background-color:#fff3cd;padding:1px 3px;border-radius:3px;border-bottom:2px solid #ffc107;",
    "llm_style": "background-color:#f8d7da;padding:1px 3px;border-radius:3px;border-bottom:2px solid #dc3545;font-style:italic;",
    "show_legend": true
  }
}
```

### Audit Logging

When `audit_log_enabled` is `true`, every query generates a JSON line in `data/audit_log.jsonl`:

```json
{
  "timestamp": "2026-04-01T10:30:45.123456+00:00",
  "agent_id": "responsible_ai",
  "query": "List researchers that have interest in AI and Ethics",
  "query_type": "normal",
  "source_type": "Metadata",
  "reliability_label": "High",
  "confidence": 100,
  "total_claims": 59,
  "breakdown": {
    "metadata_pct": 100,
    "database_pct": 0,
    "llm_pct": 0
  },
  "context_sources": ["researcher", "metadata"],
  "transparency_level": "development"
}
```

The JSONL format is append-only and processable with standard tools (`jq`, `grep`, pandas). For production, use standard log rotation (e.g., `logrotate`).

---

## 9. LLM Configuration

### 9.1 Mistral Cloud

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

### 9.2 Ollama (Local)

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

### 9.3 Per-Agent LLM Override

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

## 10. Running the Service

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
./web/liberar-puerto.sh 8000
```

---

## 11. Troubleshooting

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
| 504 | Port in use | Run `./web/liberar-puerto.sh 8000` |

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
