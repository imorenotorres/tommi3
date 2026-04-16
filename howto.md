---
pagetitle: "A practical guide to TOMMI: building and deploying AI agents"
header-includes: |
  <style>
    .preface {
      background-color: #e8f4f8;
      border-left: 4px solid #2196F3;
      padding: 1em 1.5em;
      margin: 1.5em 0;
      border-radius: 4px;
    }
    .caution {
      background-color: #fff3cd;
      border-left: 4px solid #ffc107;
      padding: 1em 1.5em;
      margin: 1.5em 0;
      border-radius: 4px;
    }
  </style>
---

# A practical guide to TOMMI:<br>building and deploying AI agents

**By: UNINOVIS-UMA IT TEAM**

## Preface

AI agents are becoming increasingly available across industries, education, and public services. Their ability to retrieve information, answer questions, and automate tasks makes them attractive tools for a wide range of applications. However, the deployment and use of AI agents requires a good understanding of their risks and limitations.

Most AI agent applications fail in two important aspects:

- **Technical transparency:** Different models have different capabilities, biases, knowledge cutoffs, and cost profiles — yet this information is rarely disclosed.
- **Content transparency:** When an agent provides an answer, users generally cannot tell whether the response comes from a curated database, a retrieved document, or the LLM's own training data — which may include hallucinated or outdated content.

This lack of transparency makes it difficult for users to assess the reliability of the information they receive, and for developers to understand and communicate the limitations of the systems they build.

The main motivation in developing TOMMI was to create an AI agent framework that, by being transparent, would help:

1. **Developers** understand the key characteristics of AI agents and be able to responsibly develop new ones — knowing exactly which data sources are used, how retrieval works, and where the LLM contributes.
2. **End-users** evaluate the potential interest and/or risks of using AI agents as information sources — through visible reliability indicators that show the origin of each response.

TOMMI addresses these goals through features such as open-source architecture, configurable LLM selection (with visible model badges), structured data pipelines, a **reliability badge system** that transparently breaks down each response into the percentage sourced from human-checked content and LLMs whose reliability cannot be checked (see [Section 3.7](#reliability-badges)), and a **Graduated Transparency framework** with claim-level provenance tracking, contextual explainability, and EU AI Act-compliant audit logging (see [Section 3.8](#graduated-transparency-with-claim-level-provenance)).

---

## Index

- [Preface](#preface)
1. [Introduction to Agents](#introduction-to-agents)
   - [1.1 Oneshot Agents](#oneshot-agents)
   - [1.2 RAG Agents](#rag-agents-retrieval-augmented-generation)
   - [1.3 Text2SQL Agents](#text2sql-agents)
   - [1.4 RAG+Metadata Agents](#ragmetadata-agents)
   - [1.5 Agent Types Comparison](#agent-types-comparison)
2. [Setting Up the TOMMI Agents Service](#setting-up-the-tommi-agents-service)
   - [2.1 Prerequisites](#prerequisites)
   - [2.2 Installation](#installation)
   - [2.3 Project Structure](#project-structure)
   - [2.4 Configuring LLMs](#configuring-llms)
3. [Creating Agents](#creating-agents)
   - [3.1 Using the Web Interface](#using-the-web-interface)
   - [3.2 Using the Interactive CLI](#using-the-interactive-cli)
   - [3.3 Prompt Templates](#prompt-templates)
   - [3.4 Generated Files](#generated-files)
   - [3.5 Agent Configuration](#agent-configuration)
   - [3.6 Adding Data to Your Agent](#adding-data-to-your-agent)
     - [3.6.1 Oneshot Agents: Single Data File](#oneshot-agents-single-data-file)
     - [3.6.2 RAG Agents: Document Collection](#rag-agents-document-collection)
       - [RAG Chunking Approaches](#rag-chunking-approaches)
       - [3.6.3 RAG+Metadata Agents: Documents with Metadata](#ragmetadata-agents-documents-with-metadata)
     - [3.6.4 Text2SQL Agents: Database Only](#text2sql-agents-database-only)
   - [3.7 Reliability Badges](#reliability-badges)
     - [3.7.1 Why Reliability Matters](#why-reliability-matters)
     - [3.7.2 How Reliability Is Measured (Back-office)](#how-reliability-is-measured-back-office)
     - [3.7.3 How Reliability Is Displayed (Front-office)](#how-reliability-is-displayed-front-office)
     - [3.7.4 Configuring Reliability Thresholds](#configuring-reliability-thresholds)
     - [3.7.5 Similarity Tuning with `similarity_test.py`](#similarity-tuning-with-similarity_testpy)
   - [3.8 Graduated Transparency with Claim-level Provenance](#graduated-transparency-with-claim-level-provenance)
     - [3.8.1 Transparency Levels](#transparency-levels)
     - [3.8.2 Claim-level Provenance (Inline Highlights)](#claim-level-provenance-inline-highlights)
     - [3.8.3 Contextual Explainability (Gap Analysis)](#contextual-explainability-gap-analysis)
     - [3.8.4 EU AI Act Audit Trail](#eu-ai-act-audit-trail)
     - [3.8.5 Configuration Reference](#transparency-configuration-reference)
4. [Interacting with Agents](#interacting-with-agents)
   - [4.1 Web Interface](#web-interface)
     - [4.1.1 Starting the Web Hub](#starting-the-web-hub)
     - [4.1.2 Using the Interface](#using-the-interface)
     - [4.1.3 Interactive Commands for Text-to-SQL Agents](#interactive-commands-for-text-to-sql-agents)
   - [4.2 Terminal](#terminal)
5. [Developer Functionalities](#developer-functionalities)
   - [5.1 Testing Your Agent](#testing-your-agent)
   - [5.2 Using local LLMs](#using-local-llms)
   - [5.3 Local vs Cloud: quality differences](#local-vs-cloud-quality-differences)
   - [5.4 Conversation Logging](#conversation-logging)
6. [Quick Reference](#quick-reference)
   - [6.1 End-User Commands](#end-user-commands)
   - [6.2 Developer API](#developer-api)
   - [6.3 Setup Commands](#setup-commands)
7. [Troubleshooting: Error Codes Reference](#troubleshooting-error-codes-reference)
   - [7.1 LLM Connection Errors (1xx)](#llm-connection-errors-1xx)
   - [7.2 Agent Errors (2xx)](#agent-errors-2xx)
   - [7.3 Data Errors (3xx)](#data-errors-3xx)
   - [7.4 Server Errors (5xx)](#server-errors-5xx)
8. [Annex A: Terminal Command Reference](#annex-a-terminal-command-reference)
   - [A.1 Environment Setup](#a1-environment-setup)
   - [A.2 Agent Management](#a2-agent-management)
   - [A.3 Web Server](#a3-web-server)
   - [A.4 RAG Agent Operations](#a4-rag-agent-operations)
   - [A.5 RAG+Metadata Agent Operations](#a5-ragmetadata-agent-operations)
   - [A.6 Text2SQL Agent Operations](#a6-text2sql-agent-operations)
   - [A.7 Ollama Commands (Local LLM)](#a7-ollama-commands-local-llm)
   - [A.8 API Testing with curl](#a8-api-testing-with-curl)
   - [A.9 Logs and Debugging](#a9-logs-and-debugging)
   - [A.10 Distribution](#a10-distribution)
   - [A.11 Useful Environment Variables](#a11-useful-environment-variables)
9. [Annex B: CLI Quick Reference](#annex-b-cli-quick-reference)
   - [B.1 Interactive CLI](#b1-interactive-cli)
   - [B.2 Batch Testing](#b2-batch-testing)
   - [B.3 HTTP API with curl](#b3-http-api-with-curl)

---

## 1. Introduction to Agents

An **agent** is an AI-powered system that can understand natural language queries and respond intelligently. AI agents should not be confused with traditional AI assistants such as ChatGPT or Claude. The latter are powerful but generic: they rely solely on their training data, have no access to your private information, and cannot perform actions beyond generating text. An agent, by contrast, is **specialized** and **connected**. It can access specific knowledge bases (your documents, your database), retrieve relevant information on demand, and even execute actions through tools (run calculations, query APIs, send emails). While a traditional AI might say "I don't have access to that information," an agent built with TOMMI can actually look it up and give you a precise answer.

In educational and institutional settings, agents offer significant advantages. They can provide **24/7 availability** to answer frequently asked questions about admissions, course schedules, or administrative procedures—reducing the workload on staff while improving response times for students. Agents can also serve as **personalized learning assistants**, helping students navigate complex documentation, summarize research papers, or explain institutional policies in plain language. For administrative staff, agents can automate repetitive inquiries and provide consistent, accurate information across departments. At the same time, improper use of agents may have severe consequences for educational institutions (e.g. sensitive data breach, open access to hackers, or even economic costs due to excess of use).

In order for educational institutions to benefit from this novel technology while at the same time minimizing risks, it is crucial that several actions are adopted. These include:

- A clear regulation on the use of agents
- A safe agentic infrastructure
- Training IT and other staff in creating agents
- Training end users on how to interact with AI Agents.

With TOMMI we bring a tool that may help universities to address the last two aspects. Regarding staff, TOMMI allows rapidly hands-on experience with AI Agents, which may accelerate the training process. Regarding end-users, its friendly but transparent interface may encourage use of AI Agents, thus fostering **digital literacy** and critical thinking about how these technologies work.

TOMMI supports four agent types, each suited for different use cases:

### 1.1 Oneshot Agents

The simplest type. Loads all data into memory and includes it directly in the LLM context.

**How it works:**
1. Loads data from `data/data.md` at startup
2. Includes the full data in every system prompt
3. LLM generates response using the embedded context

**Architecture:**
```
┌──────────────┐
│   Question   │────┐
└──────────────┘    │
                    ▼
              ┌──────────┐    ┌──────────────┐
              │    LLM   │───▶│   Response   │
              └──────────┘    └──────────────┘
                    ▲
┌──────────────┐    │
│   data.md    │────┘
│   (static)   │
└──────────────┘
```

**Best for:**
- Small to moderate knowledge bases (< 100KB)
- FAQ systems
- Static information assistants

**Optional feature:** [Grounding verification](#grounding-verification-anti-hallucination) can be enabled to prevent hallucinations by verifying responses against the source data.

**Example:** Conference information assistant that answers questions about schedules, speakers, and venues.

### 1.2 RAG Agents (Retrieval-Augmented Generation)

Uses semantic search to find relevant information before generating responses.

**How it works:**
1. Indexes documents from `data/docs/` into ChromaDB vector database
2. When a query arrives, searches for the most relevant chunks
3. Includes only relevant context in the LLM prompt
4. Generates response based on retrieved information

**Architecture:**
```
┌──────────────┐
│   Question   │──────────────────────┐
└──────┬───────┘                      │
       │                              ▼
       │                        ┌──────────┐    ┌──────────────┐
       │                        │   LLM    │───▶│   Response   │
       │                        └──────────┘    └──────────────┘
       │                              ▲
       │    ┌──────────────┐          │
       └───▶│    Search    │──────────┘
            └──────┬───────┘    (relevant chunks)
                   │
            ┌──────▼───────┐
            │   ChromaDB   │◀── docs/ (PDF, TXT)
            │   (vectors)  │
            └──────────────┘
```

**Best for:**
- Large document collections
- Academic papers or manuals
- Frequently updated content (supports re-indexing)

**Optional feature:** [Grounding verification](#grounding-verification-anti-hallucination) can be enabled to ensure responses are based only on retrieved documents.

**Example:** Academic proceedings Q&A system that searches through hundreds of papers.

### 1.3 Text2SQL Agents

Converts natural language questions directly to SQL queries against a database.

**How it works:**
1. User asks a question in natural language
2. Agent uses the configured LLM (Mistral or Ollama) to convert the question to SQL
3. **SQL Verification** (pre-execution): validates the generated SQL against the database schema and checks semantic alignment with the user's question
4. Executes the SQL query against a SQLite database (only SELECT queries allowed)
5. **Reliability badge** (post-execution): assesses confidence based on schema verification, semantic alignment, and execution results
6. Formats results using Python (fast, no additional LLM call)
7. Displays results in an interactive HTML table

**Architecture:**
```
┌──────────────┐
│   Question   │──────────────────────┐
└──────────────┘                      │
                                      ▼
┌──────────────┐                ┌──────────┐    ┌──────────────┐
│    Schema    │───────────────▶│   LLM    │───▶│ Execute SQL  │
│   (tables)   │                │(text2sql)│    │   (SQLite)   │
└──────────────┘                └──────────┘    └──────┬───────┘
                                                       │
                                                       ▼
                                                ┌──────────────┐
                                                │    Python    │
                                                │  (format)    │
                                                └──────┬───────┘
                                                       │
                                                       ▼
                                                ┌──────────────┐
                                                │   Response   │
                                                │ + HTML table │
                                                └──────────────┘
```

**Best for:**
- Database exploration without SQL knowledge
- Data analysis and reporting
- Quick data lookups
- Educational environments where users need to query data

**Key features:**
- **Single LLM call:** Uses one LLM for SQL generation; formatting is done with Python for speed
- **Security:** Only SELECT queries are allowed; INSERT, UPDATE, DELETE, and other modifying operations are blocked
- **Schema awareness:** Automatically reads and understands the database structure
- **SQL verification:** Every generated query is verified against the database schema before execution — unknown tables, columns, and dangerous keywords are detected and blocked
- **Semantic alignment check:** Detects when the LLM generates SQL that doesn't match the user's question (e.g. user asks about "Libya" but SQL searches for "English B1"). Supports cross-language equivalences (english↔inglés, finland↔finlandia, etc.)
- **Reliability badges:** Post-execution confidence assessment displayed as a badge (similar to RAG agent grounding badges)
- **Interactive results:** Displays query results in formatted HTML tables

**Example:** A university department needs to query a database of courses and professors. Users can ask "How many courses are in the Law department?" and get instant results without knowing SQL.

### 1.4 RAG+Metadata Agents

An enhanced version of RAG agents designed for **multi-institution research paper analysis**. Beyond basic RAG, these agents provide publication analytics per university, topic aggregation from paper metadata, and interactive map visualizations.

**How it works:**
1. Indexes PDF documents from `data/docs/` into ChromaDB vector database
2. Loads structured paper metadata from `*_papers.json` files (per university)
3. Automatically extracts and aggregates research topics from paper concepts
4. Provides publication counts per university and top research topics to the LLM
5. Generates interactive maps showing paper distribution across universities
6. All configuration is driven by `config.json` — no code changes needed for new topics

**Architecture:**
```
┌──────────────┐
│   Question   │──────────────────────┐
└──────┬───────┘                      │
       │                              ▼
       │                        ┌──────────┐    ┌──────────────┐
       │                        │   LLM    │───▶│   Response   │
       │                        └──────────┘    └──────────────┘
       │                              ▲
       │    ┌──────────────┐          │
       └───▶│    Search    │──────────┘
            └──────┬───────┘  (chunks + metadata + topics + counts)
                   │
            ┌──────▼───────┐    ┌────────────────────┐
            │   ChromaDB   │    │  *_papers.json      │
            │  (vectors +  │    │  (per-university    │
            │   metadata)  │    │   paper metadata,   │
            └──────────────┘    │   concepts, authors)│
                   ▲            └────────────────────┘
                   │                     ▲
            docs/ (PDFs)          metadata.json
```

**Best for:**
- Analyzing research output across multiple institutions
- Comparing publication counts and research topics per university
- Interactive visualizations on maps
- Filtering and searching papers by university, author, topic, or content

**Key features:**
- **Fully configurable via `config.json`**: agent name, research topic, universities, coordinates — no code changes needed
- Publication counts per university included in LLM context
- Top research topics aggregated from paper concepts (OpenAlex)
- Interactive Leaflet maps embedded inline in chat responses
- Side panels with paper lists and "open in new window" option
- Automatic metadata extraction from PDFs (title, author, date, page count)
- External metadata from `metadata.json` (maps papers to universities)
- All RAG features (smart chunking, grounding verification)

**Optional feature:** [Grounding verification](#grounding-verification-anti-hallucination) can be enabled, same as RAG agents.

**Example:** The *Responsible AI* agent analyzes AI & Responsibility papers across 8 UNINOVIS universities. Users can ask "How many publications does each university have?", "Which are the most important topics?", or "Which universities have publications about Ethics & AI?" — and get tables, aggregated topic data, and interactive maps.

### 1.5 Agent Types Comparison

#### Feature Comparison Table

| Feature | Oneshot | RAG | RAG+Metadata | Text2SQL |
|---------|:-------:|:---:|:------------:|:--------------:|
| **Complexity** | Low | Medium | Medium | Medium |
| **LLM Calls per Query** | 1 (or 2)* | 1 (or 2)* | 1 (or 2)* | 1 |
| **Vector Database** | - | ✓ | ✓ | - |
| **SQL Database** | - | - | - | ✓ |
| **Document Search** | - | ✓ | ✓ | - |
| **Metadata Filtering** | - | - | ✓ | - |
| **Dynamic Knowledge** | - | ✓ | ✓ | ✓ |
| **Grounding Verification** | ✓ | ✓ | ✓ | ✓ (SQL schema + semantic) |
| **Python Version** | Any | 3.11-3.13 | 3.11-3.13 | Any |

\* With grounding verification enabled, requires 2 LLM calls per query.

#### Use Case Recommendations

| Scenario | Recommended Type | Why |
|----------|------------------|-----|
| Simple FAQ with static information | **Oneshot** | Minimal complexity, fastest response |
| Q&A over many documents/PDFs | **RAG** | Semantic search scales to thousands of documents |
| Document collection with metadata filtering | **RAG+Metadata** | Metadata extraction + semantic search |
| Database queries by non-technical users | **Text2SQL** | Natural language to SQL conversion |
| Need lowest latency | **Oneshot** | Single LLM call, no external lookups |
| Need to scale to thousands of documents | **RAG** | Vector database handles large collections |
| Privacy-sensitive data queries | **Text2SQL** | Data stays local, only questions sent to LLM |

#### Cost Comparison

| Type | LLM Calls | Total Cost Profile |
|------|-----------|-------------------|
| **Oneshot** | 1 (2 with verification) | Low (Medium with verification) |
| **RAG** | 1 (2 with verification) | Low (Medium with verification) |
| **RAG+Metadata** | 1 (2 with verification) | Low (Medium with verification) |
| **Text2SQL** | 1 (+ local verification) | Low |

#### Architecture Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                          AGENT TYPES                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ONESHOT         RAG       RAG+METADATA   Text_2_SQL        │
│  ───────         ───       ────────────   ──────────────        │
│                                                                  │
│  Question      Question     Question        Question             │
│     +             +            +               +                 │
│   Data         Search       Search          Schema               │
│     │          Results    Results +           │                  │
│     │             │       Metadata            │                  │
│     │             │            │              │                  │
│     ▼             ▼            ▼              ▼                  │
│   [LLM]        [LLM]        [LLM]          [LLM]                │
│     │             │            │              │                  │
│     │             │            │              ▼                  │
│     │             │            │         [SQL DB]                │
│     │             │            │              │                  │
│     │             │            │              ▼                  │
│     │             │            │          [Python]               │
│     │             │            │          (format)               │
│     │             │            │              │                  │
│     ▼             ▼            ▼              ▼                  │
│  Response     Response     Response       Response               │
│                                           + HTML table           │
└──────────────────────────────────────────────────────────────────┘
```

#### Quick Selection Guide

**Choose based on your primary need:**

1. **"I have a small knowledge base (<100KB)"** → **Oneshot**
2. **"I have many documents to search"** → **RAG**
3. **"I want users to query a database naturally"** → **Text2SQL**
4. **"I have documents and need to filter by author/date/type"** → **RAG+Metadata**

[↑ Back to index](#index){.back-to-top}

---

## 2. Setting Up the TOMMI Agents Service

### 2.1 Prerequisites

- Python 3.10+ (for Oneshot and Text2SQL agents)
- Python 3.11-3.13 (for RAG and RAG+Metadata agents - ChromaDB is **not compatible** with Python 3.14+)
- Mistral API key

> **Note:** If you plan to use RAG or RAG+Metadata agents and have Python 3.14+, install Python 3.12:
> ```bash
> brew install python@3.12  # macOS
> ```

### 2.2 Installation

Run the setup script to configure the environment:

- **Windows:** `apps\setup.bat`
- **Linux/macOS:** `./apps/setup.sh`

The script will automatically create a virtual environment, install dependencies, and configure your API key.

### 2.3 Project Structure

```
tommi/
├── apps/                    # Scripts and utilities
│   ├── setup.sh             # Setup script (Linux/macOS)
│   ├── setup.bat            # Setup script (Windows)
│   ├── crear_agente.py      # Agent creator with built-in templates
│   ├── crear_dist.sh        # Distribution script (Linux/macOS)
│   └── crear_dist.bat       # Distribution script (Windows)
├── web/                     # Central web service hub
│   ├── app.py               # FastAPI server
│   ├── agent_runner.py      # Agent discovery engine
│   └── static/              # Frontend files
└── agents/                  # All agents are stored here
    ├── your_agent/          # Your custom agents
    ├── conf26_cloud/        # Example: conference assistant (cloud)
    ├── conf26_local/        # Example: conference assistant (local)
    └── ...
```

### 2.4 Configuring LLMs

TOMMI supports two LLM providers:
- **Mistral Cloud** (default) - LLMs on the cloud, requires API key
- **Ollama** (optional) - Local LLMs, easy setup, good for development and privacy

For starters, Mistral Cloud is recommended as it requires no local setup.

#### Available Mistral Models

| Model | Use Case |
|-------|----------|
| `mistral-large-latest` | Best quality, complex reasoning (default) |
| `mistral-medium-latest` | Balanced performance |
| `mistral-small-latest` | Fast responses, simple tasks |

#### Default configuration (web/.env)

The file `web/.env` sets the **default configuration for ALL agents**:

```bash
# ============================================
# DEFAULT LLM Provider Configuration
# ============================================
# This is the DEFAULT configuration for all agents.
# Individual agents can override by adding LLM_PROVIDER to their own .env

# --- Cloud LLM (Mistral) - DEFAULT ---
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_api_key_here
MISTRAL_MODEL=mistral-large-latest

# --- To use Local LLM (Ollama) as default, comment above and uncomment below ---
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=mistral
```

> **Note:** Replace `your_api_key_here` with an API key that you should obtain from Mistral at [https://mistral.ai/](https://mistral.ai/).

[↑ Back to index](#index){.back-to-top}

---

## 3. Creating Agents

### 3.1 Using the Web Interface

The easiest way to create a new agent is through the web interface. First, start the web server if it's not already running:

- **Linux/macOS:** `web/run_html_server.sh`
- **Windows:** `web\run_html_server.bat`

Then access `http://localhost:8000` and click on the **"Create Agent"** button in the sidebar.

The web interface provides a visual form where you can configure:

1. **Agent type** - Select from oneshot, RAG, RAG+Metadata, or text2sql
2. **Agent ID** - Unique identifier (lowercase, alphanumeric)
3. **Display name** - Human-readable name
4. **Description** - What the agent does
5. **Welcome message** - Greeting shown to users
6. **Example queries** - Sample questions users can ask
7. **System prompt** - Instructions for the LLM behavior (with templates available)
8. **Grounding verification** - (oneshot/RAG only) Enable anti-hallucination verification
9. **LLM Provider** - Mistral Cloud or Ollama
10. **Model** - Which model to use

After filling out the form, click **"Create Agent"** and your new agent will be immediately available in the agent selector.

### 3.2 Using the Interactive CLI

Alternatively, you can create agents from the command line:

```bash
python apps/crear_agente.py
```

The script will prompt you for the same options as the web interface:

1. **Agent type** (1=oneshot, 2=rag, 3=text2sql, 4=rag_metadata)
2. **Agent ID** - Unique identifier (lowercase, alphanumeric)
3. **Output directory** - Where to create the agent
4. **Display name** - Human-readable name
5. **Description** - What the agent does
6. **Welcome message** - Greeting shown to users
7. **Example queries** - Sample questions users can ask
8. **System prompt** - Instructions for the LLM behavior
9. **Grounding verification** - (oneshot/RAG only) Enable anti-hallucination verification
10. **LLM Provider** - Mistral Cloud or Ollama
11. **Model** - Which model to use

### 3.3 Prompt Templates

When creating a new agent, you can choose from pre-defined prompt templates instead of writing a system prompt from scratch. Templates are built into the `crear_agente.py` script and provide a solid starting point for each agent type.

**Available templates:**

| Template | Description |
|----------|-------------|
| Oneshot | Instructions for data-based assistants |
| RAG | Instructions for document retrieval assistants |
| RAG+Metadata | Instructions for metadata-aware document retrieval assistants |
| Text2SQL | Instructions for database query assistants |

**How it works:**

During agent creation (`python apps/crear_agente.py`), the script will prompt you to enter a system prompt or use a default template based on the agent type you selected.

**Template variables:**

Templates support the `{agent_name}` variable, which is automatically replaced with your agent's name.

**Customizing after creation:**

Once an agent is created, its prompt is stored in `agent.py` and can be edited independently.

### 3.4 Generated Files

The creator generates a complete agent structure:

```
your_agent/
├── agent.py           # Core agent logic
├── app.py             # FastAPI wrapper with AGENT_CONFIG
├── config.json        # (rag_metadata) Agent configuration (name, topic, universities)
├── requirements.txt   # Python dependencies
├── .env               # API credentials
├── .gitignore         # Security (ignores .env)
├── run.sh             # Startup script
├── README.md          # Documentation
└── data/
    ├── data.md        # (oneshot) Knowledge base (to be replaced by your own data)
    ├── docs/          # (rag, rag_metadata) Document folder for indexing
    ├── metadata.json  # (rag_metadata) Paper-to-university mapping
    ├── *_papers.json  # (rag_metadata) Per-university paper metadata from OpenAlex
    ├── institution_ids.json  # (rag_metadata) University identifiers
    └── database.db    # (text2sql) SQLite database (to be replaced by your own database)
```

### 3.5 Agent Configuration

For **oneshot**, **RAG**, and **text2sql** agents, configuration is defined in `app.py`:

```python
AGENT_CONFIG = {
    "id": "my_agent",
    "name": "My Agent",
    "type": "oneshot",  # or "rag", "rag_metadata", or "text2sql"
    "description": "Helps with specific tasks",
    "welcome_message": "Hello! How can I help you?",
    "example_queries": [
        "What can you do?",
        "Tell me about X"
    ]
}
```

You can edit `app.py` at any time to add or remove example queries, change the welcome message, update the description, or modify any other metadata field.

For **RAG+Metadata** agents, all configuration is centralized in `config.json` (both `app.py` and `agent.py` read from it automatically):

```json
{
  "agent_id": "my_research_agent",
  "agent_name": "My Research Agent",
  "description": "Research assistant for Topic X papers",
  "welcome_message": "Hello! I'm a research assistant for Topic X. How can I help?",
  "research_topic": "Topic X (subtopic A, subtopic B, etc.)",
  "example_queries": [
    "Which are the most important topics",
    "Show a table with the number of publications per university",
    "Which universities have publications about subtopic A?"
  ],
  "alliance": {
    "name": "MY_ALLIANCE",
    "description": "Description of the university alliance or research network."
  },
  "universities": {
    "UNI1": {"name": "University One", "country": "Country", "lat": 40.0, "lon": 2.0},
    "UNI2": {"name": "University Two", "country": "Country", "lat": 48.0, "lon": 10.0}
  }
}
```

The `config.json` fields control:

| Field | What it controls |
|-------|-----------------|
| `agent_id` | Agent identifier (used in URLs and API routes) |
| `agent_name` | Display name in the UI and system prompt |
| `description` | Short description of the agent's purpose |
| `research_topic` | Describes the research area for the LLM's system prompt |
| `welcome_message` | Greeting shown when the agent is selected |
| `show_history` | Whether to display query history in the sidebar |
| `example_queries` | Suggested questions shown to users in the UI |
| `alliance` | Name and description of the institutional network |
| `universities` | List of institutions with name, country, and coordinates for map visualization |
| `rag_domain_keywords` | Domain-specific keywords used by `similarity_test.py` for calibration |
| `rag_keyword_boost` | Similarity boost per keyword, used by `similarity_test.py` |
| `reliability_green_max_llm` | Maximum LLM % for green badge (High reliability) |
| `reliability_red_min_llm` | Minimum LLM % for red badge (Poor reliability) |

### 3.6 Adding Data to Your Agent

**Why data matters:** LLMs have a knowledge cutoff date and no access to your private information. Without data, an agent is just a generic chatbot. With your data, it becomes a specialized assistant that can answer questions about your specific domain.


#### 3.6.1 Oneshot Agents: Single Data File

Oneshot agents load all their knowledge from a single Markdown file.

**Data location:** `data/data.md`

**How to add data:**
1. Edit `data/data.md` with all the information your agent needs
2. Use Markdown formatting for structure (headers, lists, tables)
3. Keep the file under ~100KB for optimal performance

**Example `data/data.md`:**
```markdown
# Conference information

## Sessions
- **Session A**: Description of session A, time, room
- **Session B**: Description of session B, time, room


## FAQ
### Where is the conference?
...
```

**Note:** The entire file is included in every LLM prompt, so keep it concise and well-organized.

---

#### 3.6.2 RAG Agents: Document Collection

RAG agents index multiple documents and retrieve relevant chunks at query time.

> **Important:** RAG agents require **Python 3.11-3.13**. ChromaDB is not compatible with Python 3.14+. If you see Error 307, install Python 3.12 and recreate the virtual environment.

**Data location:** `data/docs/`

**Supported formats:** `.txt`, `.md`, `.pdf`

**How to add data:**
1. Place your documents in `data/docs/`
2. Use descriptive filenames (e.g., `user-manual.md`, `api-reference.txt`)
3. **New documents are automatically detected and indexed** when the agent starts
4. Documents removed from `data/docs/` are automatically removed from the index

**Example structure:**
```
data/
└── docs/
    ├── chapter1-introduction.md
    ├── chapter2-installation.md
    ├── chapter3-configuration.md
    ├── faq.md
    ├── user-manual.pdf
    └── troubleshooting.txt
```

**Automatic synchronization:**

When the agent starts, it automatically compares files in `data/docs/` with the indexed documents:
- **New files** are indexed without re-indexing existing documents
- **Deleted files** are removed from the index
- **No changes** = fast startup (no re-indexing needed)

Example output when starting an agent with new documents:
```
Preparing RAG database...
Indexing 2 new documents...
Indexed 150 chunks from 2 documents
Added: new_manual.pdf, updated_faq.md
RAG database ready.
```

**Manual re-indexing:**

If you need to force a complete re-index (e.g., after modifying an existing document), use the `/reindex` endpoint:
```bash
curl -X POST http://localhost:8000/api/agents/<agent_id>/reindex
```

**How it works internally:**
- PDF text is extracted using `pypdf`
- Documents are split into chunks (size depends on RAG approach)
- Each chunk is embedded using `sentence-transformers` (all-MiniLM-L6-v2)
- Embeddings are stored in ChromaDB at `data/chroma_db/`
- On query, relevant chunks are retrieved and included in the prompt

**Tip:** Structure your documents with clear headers and sections for better retrieval accuracy.

#### RAG Chunking Approaches

When creating a RAG agent, you can choose from three chunking approaches that affect how documents are split and retrieved:

| Approach | Chunk Size | Overlap | Retrieved | Strategy | Best For |
|----------|-----------|---------|-----------|----------|----------|
| **Basic** | 500 chars | 100 chars | 3 chunks | Fixed cut | Small documents, quick indexing |
| **Context-preserving** | 2000 chars | 400 chars | 8 chunks | Smart boundaries | Dense documents (PDFs, manuals, regulations) |
| **Custom** | Configurable | Configurable | Configurable | Configurable | Fine-tuning for specific use cases |

**Basic approach:**
- Fast indexing with smaller chunks
- Lower accuracy for complex queries
- Suitable for FAQs, short documents

**Context-preserving approach (recommended):**
- Larger chunks preserve more context
- Smart boundary detection (cuts at paragraphs/sentences)
- Better for dense documents like academic papers, regulations, manuals
- More context retrieved per query

**Custom approach:**
- Full control over all parameters
- Configure via environment variables:
  - `RAG_CHUNK_SIZE`: Characters per chunk (default: 2000)
  - `RAG_CHUNK_OVERLAP`: Overlap between chunks (default: 400)
  - `RAG_RETRIEVE_CHUNKS`: Chunks to retrieve per query (default: 8)
  - `RAG_CHUNKING_STRATEGY`: `fixed` or `smart` (default: smart)

**Configuration in `.env`:**
```bash
# RAG Chunking Configuration
RAG_APPROACH=context_preserving  # basic | context_preserving | custom

# Custom parameters (only used when RAG_APPROACH=custom)
RAG_CHUNK_SIZE=2000
RAG_CHUNK_OVERLAP=400
RAG_RETRIEVE_CHUNKS=8
RAG_CHUNKING_STRATEGY=smart  # fixed | smart
```

**When to change the approach:**
- Switch to **basic** if you have very small documents or need faster indexing
- Use **context_preserving** (default) for most document types
- Use **custom** when you need to fine-tune retrieval for specific document structures

**Important:** After changing RAG configuration, delete the ChromaDB folder and restart the agent to reindex with new settings:
```bash
rm -rf agents/<agent_id>/data/chroma_db/
```

---

#### 3.6.3 RAG+Metadata Agents: Multi-Institution Research Analysis

RAG+Metadata agents are designed for analyzing research papers across multiple institutions. They combine full-text search with structured paper metadata, publication analytics, topic aggregation, and interactive map visualizations.

**Creating a new RAG+Metadata agent for a different research topic:**

To create a new agent, copy an existing one (e.g., `responsible_ai`) and replace:

1. **`config.json`** — Change `agent_id`, `agent_name`, `research_topic`, `description`, `welcome_message`, `example_queries`, and `universities` (with coordinates for the map)
2. **`data/docs/`** — Replace with your PDF documents
3. **`data/*_papers.json`** — One file per university (e.g., `UMA_papers.json`), containing paper metadata with `concepts`, `authors`, `title`, `abstract`, etc.
4. **`data/metadata.json`** — Update the `universities` structure mapping papers to institutions
5. **`data/institution_ids.json`** — Update university identifiers if needed

No Python code changes are required.

**Data files explained:**

| File | Purpose |
|------|---------|
| `config.json` | Agent configuration: name, topic, universities with coordinates |
| `data/docs/*.pdf` | Full-text PDF documents indexed into ChromaDB |
| `data/UNI_papers.json` | Per-university paper metadata (concepts, authors, citations) |
| `data/metadata.json` | Maps paper IDs to universities; provides paper counts |
| `data/institution_ids.json` | University identifiers (e.g., OpenAlex IDs, ROR) |

**Example `UMA_papers.json` structure:**
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
    "affiliations": ["Universidad de Málaga"]
  }
]
```

**Example `metadata.json` structure:**
```json
{
  "collection_date": "2026-03-18T09:25:06",
  "universities": {
    "UMA": {
      "name": "Universidad de Málaga",
      "papers_count": 50,
      "papers": [{"id": "W4409459278", "title": "...", "authors": [...], ...}]
    }
  },
  "total_papers": 183
}
```

**What the LLM receives as context:**

The agent automatically builds and includes in every LLM call:
- **Publication counts per university** (e.g., "UMA: 50 papers, USPN: 27 papers")
- **Top 30 research topics** aggregated from paper concepts, with frequency and which universities cover each topic
- **Per-document metadata** (title, author, date, university) for indexed PDFs
- **Retrieved text chunks** from semantic search (standard RAG)

**Interactive map feature:**

When users ask about topics per university or publication counts, the agent includes an interactive Leaflet map embedded directly in the chat response. The map shows:
- Circles sized by the number of papers at each university
- A side panel (left for western universities, right for eastern) with the paper list when clicking a circle
- An "Open in new window" button for detailed viewing

**API endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /metadata` | Returns metadata for all indexed documents |
| `POST /reindex` | Reindexes all documents with metadata |
| `GET /topic-search?topic=X` | Search papers by topic across universities (JSON) |
| `GET /topic-map?topic=X` | Interactive map for a specific topic (HTML) |
| `GET /publications-search` | All papers grouped by university (JSON) |
| `GET /publications-map` | Interactive map with total publications (HTML) |

**How queries work:**

- **Content questions** (e.g., "What does paper X say about fairness?"): uses semantic search on indexed PDFs, enriched with university metadata
- **Metadata questions** (e.g., "How many papers does UMA have?"): uses the publication counts and paper metadata provided in the LLM context
- **Topic questions** (e.g., "Which are the most important topics?"): uses the aggregated topic data from paper concepts
- **Map questions** (e.g., "Which universities study Ethics & AI?"): returns an inline interactive map

---

#### 3.6.4 Text2SQL Agents: Database Only

Text2SQL agents convert natural language questions to SQL queries, executing them against a SQLite database.

**Data location:** `data/database.db`

**How to add data:**

1. Create a SQLite database file at `data/database.db`
2. You can create it using SQL scripts or by importing existing data

**Example using SQL script:**
```bash
cd your_agent/data
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

CREATE TABLE professors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    email TEXT
);

INSERT INTO courses VALUES (1, 'Introduction to Law', 'Law', 1, 6);
INSERT INTO courses VALUES (2, 'Constitutional Law', 'Law', 2, 6);
INSERT INTO courses VALUES (3, 'Programming I', 'Computer Science', 1, 6);
```

**How it works:**

Text2SQL agents use a single LLM call for SQL generation, followed by multi-layer verification and Python for fast result formatting:

1. The LLM converts the natural language question to SQL
2. **Schema verification:** Table and column names are validated against the actual database schema
3. **Semantic alignment check:** Key terms from the user's question are compared against the SQL's WHERE clauses to detect mismatches (supports cross-language equivalences like english↔inglés)
4. If verification passes, the SQL is executed against the SQLite database
5. **Post-execution check:** Result ratio is assessed (queries returning >70% of all rows are flagged as too broad)
6. Results are formatted as an HTML table using Python (no additional LLM call)
7. A reliability badge is generated showing confidence level and any issues

**Configuration in `.env`:**
```bash
# Using Mistral Cloud
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=mistral-large-latest

# Or using Ollama (local)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=mistral
```

**Security and verification features:**

- Only SELECT queries are allowed
- INSERT, UPDATE, DELETE, DROP, and other modifying operations are blocked
- SQL injection attempts are rejected
- Schema verification blocks queries referencing non-existent tables or columns
- Semantic alignment blocks SQL that doesn't match the user's intent (e.g. asking about "Libya" but SQL searches for "English B1")
- Cross-language equivalence support prevents false positives (english↔inglés, erasmus↔KA131, etc.)
- `prompt_level: "stringent"` blocks mismatched queries; `"tolerant"` logs warnings but executes

**API endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /schema` | Returns the database schema |
| `POST /chat` | Process a natural language question |

**Tip:** The agent automatically reads the database schema at startup. Well-designed table and column names (e.g., `student_name` instead of `sn`) help the LLM generate more accurate SQL queries.

### 3.7 Reliability Badges

RAG+Metadata agents include a **reliability badge** system that informs end users about how much of the response is grounded in the database versus generated by the LLM. This is essential for responsible AI: users should know whether they can trust a response as factual or whether it contains unverified content.

#### 3.7.1 Why Reliability Matters

When an AI agent answers a question, its response can draw from three distinct sources:

1. **Metadata (keyword search):** Structured data from `papers.json` — paper titles, authors, years, university assignments, topic counts, and researcher indexes. This data is authoritative and factual.
2. **Database (RAG):** Text chunks retrieved from ChromaDB via semantic similarity search. The retrieved content is real, but the LLM interprets and synthesizes it, which can introduce errors.
3. **LLM (ungrounded):** Content generated by the language model from its own training data, not backed by any source in the agent's database. This may include suggestions, interpretations, or hallucinations.

Without reliability indicators, users have no way to distinguish a fact retrieved from the database from a plausible-sounding hallucination. The reliability badge system makes this distinction transparent.

**Why is an LLM needed when the data comes from the database?**

A common question is: if the agent can find the answer in structured metadata (papers.json, researchers.json), why involve an LLM at all? The agent could format the data directly — faster, cheaper, and with zero hallucination risk. However, the LLM adds value in three ways:

1. **Natural language formatting.** The LLM turns raw structured data into readable, well-organized prose and adapts its response to the user's language (English, Spanish, etc.).
2. **Interpretation.** Questions like *"Which university publishes the most?"* or *"Compare the research focus of THUAS and UMA"* require comparing, ranking, or summarizing data — tasks that go beyond simple formatting.
3. **Flexibility.** Users phrase questions in many different ways. The LLM handles this variety naturally, whereas template-based formatters would require explicit rules for each phrasing.

Removing the LLM from metadata responses is technically feasible by building template-based formatters for each query type (paper lists, researcher lists, topic summaries, etc.), but it adds rigidity and maintenance cost. The current approach keeps the LLM in the loop for all responses, and the **reliability badge** transparently shows how much of the response comes from the database versus the LLM — so users always know what to trust.

#### 3.7.2 How Reliability Is Measured (Back-office)

The reliability system operates in two stages:

**Stage 1 — Source Classification.** When a user query arrives, the agent determines which data source to use:

- **Metadata path:** The query triggers keyword-based search (`search_papers_by_topic`), researcher lookup, affiliation search, or university paper listing. The response is constrained to structured data.
- **RAG path:** When no structured context matches, the query is embedded and compared against ChromaDB chunks via cosine similarity. The top-N most similar chunks are retrieved and passed to the LLM as context.

**Stage 2 — Lightweight Grounding Check.** After the LLM generates its response, the agent extracts **verifiable claims** from the response text:

- Quoted strings (paper titles)
- Bold markdown text (key terms, titles)
- Author names (capitalized multi-word patterns)
- Years (e.g., 2024)
- University acronyms (THUAS, UMA, etc.)
- Paper IDs (e.g., W4405602662)

Each claim is checked against two context pools:

- **Metadata context:** Structured data from keyword search, topic summaries, researcher indexes, and paper lists.
- **RAG context:** Text chunks retrieved from ChromaDB.

Claims found in either pool are **grounded**. Claims not found in any pool are attributed to the **LLM**. The result is a percentage breakdown:

```
Example: Metadata: 75% | Database: 10% | LLM: 15%
```

This means 75% of the verifiable claims in the response come from structured metadata, 10% from RAG-retrieved text chunks, and 15% were generated by the LLM without database backing.

**Special cases:**

| Scenario | Badge behaviour |
|----------|----------------|
| **Figure/map requests** | Always green (Metadata: 100%) — figures are rendered from structured data |
| **"Not found" responses** | Green — the database confirmed the absence of results |
| **Follow-up queries** ("expand on 1", "more details") | No badge — relies on conversation history |
| **Gap analysis** ("topics not studied") | Always red (LLM: 100%) — the LLM identifies gaps from its own knowledge |

#### 3.7.3 How Reliability Is Displayed (Front-office)

The badge appears at the top of each response in the web interface, using a traffic-light colour scheme:

| Colour | Label | Meaning | Condition |
|--------|-------|---------|-----------|
| 🟢 Green | **Reliability: High** | Response is grounded in the database | LLM ≤ `reliability_green_max_llm` (default: 20%) |
| 🟡 Yellow | **Reliability: Good** | Response is mostly grounded with some LLM content | LLM between green and red thresholds |
| 🔴 Red | **Reliability: Poor** | Response is mostly or entirely LLM-generated | LLM ≥ `reliability_red_min_llm` (default: 50%) |

Each badge includes the source breakdown in parentheses. When there is a mix of sources, an explanatory note appears:

```
Reliability: High (Metadata: 85% | LLM: 15%)
Factual claims are grounded in structured metadata (keyword search).
Suggestions and interpretations may come from the LLM.
```

```
Reliability: Good (Metadata: 40% | Database: 25% | LLM: 35%)
Factual claims are grounded in structured metadata (keyword search)
and document database (RAG). Suggestions and interpretations may
come from the LLM.
```

```
Reliability: Poor (LLM: 100%)
```

#### 3.7.4 Configuring Reliability Thresholds

All reliability parameters are set in the agent's `config.json`:

```json
{
  "reliability_green_max_llm": 20,
  "reliability_red_min_llm": 50
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `reliability_green_max_llm` | 20 | Maximum LLM percentage for the green badge (High reliability). |
| `reliability_red_min_llm` | 50 | Minimum LLM percentage for the red badge (Poor reliability). Values between `green_max` and `red_min` produce a yellow badge (Good reliability). |

**Tuning guidance:**

- **Stricter reliability:** Lower `reliability_green_max_llm` (e.g., 10) and/or lower `reliability_red_min_llm` (e.g., 40). More responses will show yellow or red.
- **More permissive:** Raise `reliability_green_max_llm` (e.g., 30) and/or raise `reliability_red_min_llm` (e.g., 60). More responses will show green.

#### 3.7.5 Similarity Tuning with `similarity_test.py`

The agent directory includes a utility script `similarity_test.py` for testing and calibrating the similarity threshold and keyword boost. It processes a list of queries and reports their similarity scores, allowing you to find the optimal threshold.

**Usage:**

```bash
python similarity_test.py queries.txt              # Print to stdout
python similarity_test.py queries.txt -o results.tsv  # Save to file
python similarity_test.py queries.txt -t 0.75       # Custom threshold
python similarity_test.py queries.txt -n 4          # Use 4 chunks (default: 3)
```

**Input file format** (`queries.txt`): one query per line. Blank lines and lines starting with `#` are skipped.

```
# Off-topic queries (should score Poor)
What is the recipe for chocolate cake?
How tall is the Eiffel Tower?

# On-topic queries (should score Good)
What ethical guidelines exist for AI development?
Tell me about bias detection in machine learning
```

**Output:** TSV with columns `similarity`, `status`, `query`.

**Calibration workflow:**

1. Create a `queries.txt` with ~20 off-topic queries, ~20 general tech queries, and ~20 on-topic queries.
2. Run `similarity_test.py` and examine the scores.
3. Find the threshold that best separates off-topic from on-topic. Look for a natural gap in scores.
4. Add domain keywords to `rag_domain_keywords` for on-topic queries that score just below the threshold.
5. Adjust `rag_keyword_boost` to control how much each keyword increases the score.
6. Re-run to verify. Aim for a clean separation: all off-topic below threshold, all on-topic above.

[↑ Back to index](#index){.back-to-top}

### 3.8 Graduated Transparency with Claim-level Provenance

All RAG and RAG+Metadata agents implement a **Graduated Transparency** framework that goes beyond the reliability badge. This approach aligns with the EU AI Act (Articles 13–14), the NIST AI Risk Management Framework, and the OECD AI Principles by providing layered disclosure adapted to the audience.

The framework is available in two variants depending on the agent type:

| Feature | RAG agents | RAG+Metadata agents |
|---------|-----------|-------------------|
| Source breakdown | Database % / LLM % | Metadata % / Database % / LLM % |
| Inline highlight colours | 2 (green = grounded, red = LLM) | 3 (green = metadata, yellow = RAG, red = LLM) |
| Contextual explainability (gap analysis) | — | ✅ |
| Confidence score | ✅ | ✅ |
| Transparency levels | ✅ (Debug / Basic / Opaque) | ✅ (Debug / Basic / Opaque) |
| Audit log | ✅ | ✅ |

The framework combines five standard techniques:

| Technique | Standard reference | TOMMI implementation |
|-----------|-------------------|---------------------|
| **Trust Indicators** | ISO/IEC 42001 | Reliability badge (High / Good / Poor) |
| **Provenance Tracking** | W3C PROV, EU AI Act Art. 13 | Source breakdown (Metadata % / Database % / LLM %) |
| **Claim-level Attribution** | ACM FAccT | Inline highlights with per-claim source colour |
| **Calibrated Confidence** | NIST AI RMF | Confidence score based on verified claims |
| **Decision Logging** | EU AI Act Art. 12, ISO 42001 | Audit trail in `data/audit_log.jsonl` |

#### 3.8.1 Transparency Levels

The `transparency_level` parameter in `config.json` controls how much detail is shown to the user. Three levels are available:

- **`development`** — full detail for developers and testers. All transparency features are active: reliability badge with source breakdown, confidence scores, source lines, colour legend, and inline claim highlights.
- **`production`** — minimal for end users. Shows the reliability label (High / Good / Poor) and confidence percentage only. No inline highlights, no source breakdown, no legend.
- **`opaque`** — no transparency shown to users. The response appears without any badge, confidence indicator, or highlights. This mode is useful for A/B testing or research: comparing user trust and behaviour with and without transparency tools. **The audit log remains active**, so all decision data is still recorded for compliance and analysis.

| | `development` (high) | `production` (basic) | `opaque` |
|---|---|---|---|
| Reliability badge | ✅ with source % breakdown | ✅ label only (High / Good / Poor) | ❌ |
| Confidence score | ✅ with claim count | ✅ percentage only | ❌ |
| Source lines (🟢 🟡 🔴) | ✅ | ❌ | ❌ |
| Colour legend | ✅ | ❌ | ❌ |
| Inline claim highlights | ✅ | ❌ | ❌ |
| Audit log | ✅ | ✅ | ✅ |

The active transparency level is shown in the web interface above the example queries as a colour-coded badge:

- **🔍 Transparency: Debug** — green badge
- **🔍 Transparency: Basic** — yellow badge
- **🔍 Transparency: Opaque** — red badge

There are two ways to switch transparency levels:

**1. Live switching (no restart).** Click the transparency badge in the web interface to cycle through levels: Debug → Basic → Opaque → Debug. The change takes effect immediately for the next query but resets to the `config.json` default when the server restarts.

**2. Persistent default.** Change the `transparency_level` value in the agent's `config.json` and restart the server:

```json
{
  "transparency_level": "development"
}
```

**Use case — researching the impact of transparency.** By deploying two instances of the same agent — one with `"development"` and one with `"opaque"` — researchers can compare user behaviour, trust calibration, and decision quality. Both instances log identical audit data, enabling controlled comparison. The live switching feature also allows quick toggling during demos or user studies.

#### 3.8.2 Claim-level Provenance (Inline Highlights)

When `transparency_level` is set to `"development"`, the agent highlights individual claims in the response text using colour-coded backgrounds. Each highlighted claim indicates its provenance. The number of colours depends on the agent type:

**RAG+Metadata agents** (3-tier):

| Colour | Source | Meaning |
|--------|--------|---------|
| No colour | — | Text was not identified as a verifiable claim (e.g., connective phrases, formatting, or names that did not match the extraction patterns) |
| 🟢 Green background | **Metadata** | Claim found in structured data (papers.json, researchers.json) |
| 🟡 Yellow background | **Database (RAG)** | Claim found in document chunks retrieved from ChromaDB |
| 🔴 Red background (italic) | **LLM** | Claim not found in any data source — presumably generated by the language model |

**RAG agents** (2-tier):

| Colour | Source | Meaning |
|--------|--------|---------|
| No colour | — | Text was not identified as a verifiable claim |
| 🟢 Green background | **Grounded** | Claim found in document chunks retrieved from ChromaDB |
| 🔴 Red background (italic) | **LLM** | Claim not found in any data source — presumably generated by the language model |

Hovering over a highlighted claim shows a tooltip explaining its source. Text without any colour was simply not recognized as a verifiable claim by the extraction patterns — it does not imply that the text is correct or incorrect.

**How claims are extracted.** The agent identifies verifiable claims using pattern matching:

- Quoted strings (≥10 characters) — typically paper titles
- Bold markdown text (≥5 characters) — key terms, titles
- Author names — capitalized multi-word patterns, including accented characters (é, ñ, ü), hyphens (García-López), middle initials (F., J.), and lowercase particles (de, van, von)
- Years — four-digit patterns (e.g., 2024)
- University acronyms (RAG+Metadata only) — THUAS, UMA, TAMK, etc.
- Paper IDs (RAG+Metadata only) — patterns like W4405602662

**How claims are matched.** Each extracted claim is checked (case-insensitive) against the available context pools:

- **RAG+Metadata agents:** (1) Metadata context — structured data from keyword search, topic summaries, researcher indexes. (2) RAG context — text chunks retrieved from ChromaDB.
- **RAG agents:** (1) RAG context — text chunks retrieved from ChromaDB.

For multi-word claims (author names), a fuzzy fallback checks all significant words (longer than 3 characters) — not just the surname — against each context pool. If any word matches, the entire claim is classified under that source. Claims not found in any pool are attributed to the LLM.

A colour legend appears below the reliability badge explaining the highlight colours.

#### 3.8.3 Contextual Explainability (Gap Analysis)

For gap analysis queries (e.g., *"List topics related to responsible AI that have not been studied"*), the meaning of claim highlights is reversed:

| Colour | Gap analysis meaning |
|--------|---------------------|
| 🟢 Green | Term **found** in the database — it may already be studied (suspicious as a "gap") |
| 🔴 Red | Term **not found** in any data source — likely a true gap |

The legend updates automatically to reflect this reversed interpretation, and tooltips explain the meaning on hover. This is an application of **contextual explainability**: the same data is presented differently depending on the query intent.

#### 3.8.4 EU AI Act Audit Trail

When `audit_log_enabled` is `true` in `config.json`, every query generates a decision event in `data/audit_log.jsonl`. This lightweight, append-only log is designed for EU AI Act compliance (Article 12: Record-keeping) and can be used for post-hoc audits.

Each log entry is a single JSON line. The structure varies slightly between agent types:

**RAG+Metadata agent example:**

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

**RAG agent example:**

```json
{
  "timestamp": "2026-04-01T11:15:22.789012+00:00",
  "agent_id": "tommi_tutor_nube",
  "query": "How do I create a RAG agent?",
  "query_type": "normal",
  "reliability_label": "High",
  "confidence": 85,
  "total_claims": 7,
  "breakdown": {
    "database_pct": 85,
    "llm_pct": 15
  },
  "transparency_level": "development"
}
```

**Fields:**

| Field | Description | Agent types |
|-------|-------------|-------------|
| `timestamp` | UTC ISO 8601 timestamp | All |
| `agent_id` | Agent identifier from `config.json` | All |
| `query` | The user's original question | All |
| `query_type` | `normal`, `figure`, `gap_analysis`, or `followup` | All |
| `source_type` | `Metadata`, `RAG`, or `none` (follow-ups) | RAG+Metadata only |
| `reliability_label` | `High`, `Good`, `Poor`, or `none` | All |
| `confidence` | Percentage of claims verified against data sources | All |
| `total_claims` | Number of verifiable claims extracted from the response | All |
| `breakdown` | Per-source percentage. RAG+Metadata: metadata/database/LLM. RAG: database/LLM | All |
| `context_sources` | Which context builders were used (affiliation, topic, researcher, rag, etc.) | RAG+Metadata only |
| `transparency_level` | Active transparency level at the time of the query | All |

The JSONL format is chosen for its simplicity: each line is independent, the file is append-only, and it can be processed with standard tools (`jq`, `grep`, pandas).

**Log rotation.** The log file grows indefinitely. For production deployments, use standard log rotation tools (e.g., `logrotate` on Linux) or periodically archive and clear the file.

#### 3.8.5 Configuration Reference

All transparency parameters are set in the agent's `config.json`. The highlight style keys differ between agent types:

**RAG+Metadata agents** (3-tier highlights):

```json
{
  "transparency_level": "development",
  "audit_log_enabled": true,
  "inline_claim_highlights": {
    "enabled": true,
    "metadata_style": "background-color:#d4edda;padding:1px 3px;...",
    "database_style": "background-color:#fff3cd;padding:1px 3px;...",
    "llm_style": "background-color:#f8d7da;padding:1px 3px;...",
    "show_legend": true
  }
}
```

**RAG agents** (2-tier highlights):

```json
{
  "transparency_level": "development",
  "audit_log_enabled": true,
  "inline_claim_highlights": {
    "enabled": true,
    "grounded_style": "background-color:#d4edda;padding:1px 3px;...",
    "ungrounded_style": "background-color:#f8d7da;padding:1px 3px;...",
    "show_legend": true
  }
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `transparency_level` | `"development"` | `"development"` (full detail), `"production"` (minimal), or `"opaque"` (no transparency shown, audit log still active). Can also be changed live by clicking the badge in the web interface. |
| `audit_log_enabled` | `false` | Enable/disable the JSONL audit log in `data/audit_log.jsonl`. |
| `inline_claim_highlights.enabled` | `false` | Enable/disable inline claim highlighting (only active in development). |
| `inline_claim_highlights.metadata_style` | green | CSS style for metadata-grounded claims (RAG+Metadata agents). |
| `inline_claim_highlights.database_style` | yellow | CSS style for RAG-grounded claims (RAG+Metadata agents). |
| `inline_claim_highlights.llm_style` | red | CSS style for LLM-generated claims (RAG+Metadata agents). |
| `inline_claim_highlights.grounded_style` | green | CSS style for grounded claims (RAG agents). |
| `inline_claim_highlights.ungrounded_style` | red | CSS style for LLM-generated claims (RAG agents). |
| `inline_claim_highlights.show_legend` | `true` | Show/hide the colour legend below the badge. |

[↑ Back to index](#index){.back-to-top}

---

## 4. Interacting with Agents

TOMMI offers two ways to interact with your agents:

- **Web Interface:** A visual interface accessible from any browser, ideal for end users.
- **Terminal:** Direct interaction via command line, useful for testing and automation.

### 4.1 Web Interface

#### 4.1.1 Starting the Web Hub

The web hub provides a unified interface to all your agents.

**Starting the server:**

- **Linux/macOS:** `web/run_html_server.sh`
- **Windows:** `web\run_html_server.bat`

Access the web interface at `http://localhost:8000`

#### 4.1.2 Using the Interface

Once the server is running, open your browser and go to the address shown in the terminal.

![TOMMI Web Interface](tommi_frontend.png)

1. **Select an agent:** Use the dropdown menu on the left side to choose the agent you want to talk to.
2. **Read the description:** Below the selector, you'll see a brief description of what the selected agent can help you with.
3. **Try example questions:** Click on any of the example questions shown on the left panel to quickly start a conversation.
4. **Type your question:** Write your question in the text box at the bottom and press Enter or click Send.
5. **Read the response:** The agent's response will appear in the chat area. You can continue the conversation by asking follow-up questions.

**Tip:** The agent remembers your conversation, so you can ask follow-up questions without repeating context.

#### 4.1.3 Interactive Commands for Text-to-SQL Agents

Text-to-SQL agents (Text2SQL) offer several interactive commands to explore and manipulate results after your initial query:

**Viewing more results:**

| Command | Description |
|---------|-------------|
| "Show me more" | Show next batch of results |
| "Show me the next 20" | Show next 20 results |
| "Show me all" | Show all results |

**Viewing details:**

| Command | Description |
|---------|-------------|
| "Expand #1" | Show full details of result #1 |
| "Details of #3" | Show full details of result #3 |

**Showing additional fields:**

These commands add the requested field to the basic information (university, country, program, positions, language):

| Command | Description |
|---------|-------------|
| "Also show the center" | Add the faculty/center field |
| "Also show the degrees" | Add degree programs |
| "Also show the validity" | Add validity dates |
| "Also show the destination faculty" | Add destination faculty |

**Sorting results:**

| Command | Description |
|---------|-------------|
| "Sort by country" | Sort results by country (A→Z) |
| "Sort by university" | Sort results by institution name |
| "Sort alphabetically" | Sort results alphabetically |
| "Sort from Z to A" | Sort in descending order |

**Refining your query:**

| Command | Description |
|---------|-------------|
| "Only France" | Filter previous results to France only |
| "Only those requiring English" | Add language filter to previous query |
| "From the first semester" | Filter by semester |

**Navigation:**

| Command | Description |
|---------|-------------|
| "Go back" | Return to previous query results |
| "History" | Show query history |

**Example interaction:**
```
User: What universities are in Germany?
Agent: ✅ Found 45 agreements... [shows first 20 with basic info]

User: Sort by university
Agent: 📊 45 result(s) - Sorted by university (A→Z)

User: Also show the center
Agent: ✅ 45 result(s) - Adding: 🏫 UMA Faculty
       [shows results with basic info + center field]

User: Only those requiring English B2
Agent: ✅ Found 12 agreements with English B2 requirement...
```

### 4.2 Terminal

You can interact with agents directly from the terminal without starting a web server. This is useful for testing, automation, or quick queries.

**Interactive CLI:**

```bash
cd web
source .venv/bin/activate
python cli.py
```

This will show available agents and let you select one. You can also specify the agent directly:

```bash
python cli.py my_agent
```

Once inside, type your questions and receive responses directly. Type `exit` or `salir` to quit.

**List available agents:**

```bash
python cli.py -l
```

[↑ Back to index](#index){.back-to-top}

---

## 5. Developer Functionalities

### 5.1 Testing Your Agent

TOMMI includes a batch testing tool that allows you to evaluate your agent by running multiple questions and collecting the responses. This is useful for:

- Validating that your agent answers correctly
- Comparing responses before and after changes
- Building a test suite for your agent

**Usage:**

```bash
cd web
python batch_test.py <agent_id> <questions_file> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--output, -o` | Custom output file (default: `<input>_respuestas.json`) |
| `--session, -s` | Maintain session context between questions |
| `--list-agents, -l` | List available agents and exit |
| `--no-save` | Display results in console without saving |

**Example:**

1. Create a file `evals/my_questions.txt` with one question per line:

```
# Lines starting with # are ignored
What is TOMMI?
How do I create an agent?
What types of agents are available?
```

2. Run the test:

```bash
python batch_test.py my_agent evals/my_questions.txt
```

3. Results are saved to `evals/my_questions_respuestas.json` with all questions, responses, and metadata.


### 5.2. Using local LLMs

By default, TOMMI uses **Mistral Cloud**. For local inference, TOMMI supports two options:
- **Ollama** - Easy to use, good for development and testing
- **vLLM** - High-performance inference, better for production workloads

#### Using Ollama

To use **local LLMs with Ollama**, you have two options:

#### Option A: Change the default for ALL agents

Edit `web/.env` to use Ollama as the default:

```bash
# --- Local LLM (Ollama) ---
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Comment out the Mistral configuration
# LLM_PROVIDER=mistral
# MISTRAL_API_KEY=your_api_key_here
```

#### Option B: Use local LLM for SPECIFIC agents only

Keep Mistral as the default in `web/.env`, and configure individual agents to use Ollama by adding `LLM_PROVIDER` to their `.env` file:

```bash
# agents/my_local_agent/.env
# This agent OVERRIDES the default to use Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

**Important:** An agent's `.env` only overrides the default if it contains `LLM_PROVIDER`. If `LLM_PROVIDER` is not defined (or is commented out), the agent uses the default from `web/.env`.

#### Hybrid deployments

TOMMI supports **hybrid deployments** where each agent can use a different LLM provider:

| Agent | Configuration | Provider Used |
|-------|---------------|---------------|
| `conf26_nube` | No `LLM_PROVIDER` in .env | Default (Mistral Cloud) |
| `conf26_local` | `LLM_PROVIDER=ollama` | Ollama (local) |
| `pisha` | `LLM_PROVIDER=mistral` + larger model | Mistral Cloud (mistral-large) |
| `adles` | No `LLM_PROVIDER` in .env | Default (Mistral Cloud) |

This is useful for:
- Running sensitive data agents locally while using cloud for others
- Using higher-quality cloud models for complex agents
- Balancing costs between local and cloud resources

After changing any `.env` configuration, restart the web server for changes to take effect.

#### Visual indicator

The web interface displays a color-coded badge in the sidebar showing the current LLM provider and model size:

| Color | Badge | Background Color | Meaning |
|-------|-------|------------------|---------|
| 🟢 **Green** | 🏠 Local | `#22c55e` | Using a local LLM (Ollama, vLLM) - data stays on your machine |
| 🟡 **Yellow/Orange** | ☁️ Cloud (small) | `#f59e0b` | Using a small cloud model (e.g., mistral-small, gpt-3.5) - lower cost |
| 🔴 **Red** | ☁️ Cloud (large) | `#ef4444` | Using a large cloud model (e.g., mistral-large, gpt-4) - higher cost/quality |

**Color coding rationale:**
- **Green (Local):** Data privacy + Sustainability - your data never leaves your machine, and local models have lower environmental impact
- **Yellow (Cloud Small):** Moderate cost - smaller models are cheaper and more energy-efficient, but less capable
- **Red (Cloud Large):** Higher cost + Lower sustainability - large models provide best quality but cost more per query and have higher energy consumption

**Sustainability note:** Large cloud LLMs require significant computational resources and energy. Using local models or smaller cloud models is more ecologically sustainable. Consider using the smallest model that meets your quality requirements.

**How model size is detected:**

The system automatically classifies cloud models as "small" or "large" based on their name. The classification is implemented in `web/static/app.js` (function `getCloudModelSize`).

A model is classified as **small** if its name contains any of these patterns:
- `small`, `mini`, `tiny`, `lite`, `nano`, `micro`
- `3.5` (e.g., gpt-3.5)
- `7b`, `8b` (7 or 8 billion parameters)
- `haiku` (Claude Haiku)

All other models are classified as **large**, including those containing: `large`, `medium`, `pro`, `opus`, `sonnet`, `gpt-4`, etc.

**Badge CSS classes:**

The badge styling is defined in `web/static/style.css`. The relevant CSS classes are:
- `.llm-badge.local` - Green background for local LLMs
- `.llm-badge.cloud-small` - Yellow/orange background for small cloud models
- `.llm-badge.cloud-large` - Red background for large cloud models

Hover over the badge to see additional details (model name, server URL).

#### Ollama setup

To use Ollama locally:

1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull mistral`
3. Ensure Ollama is running: `ollama serve`
4. Configure `web/.env` with the Ollama settings (see above)

### 5.3. Local vs Cloud: quality differences

You may notice that **cloud models produce better results** than local models. This is expected due to fundamental differences in how these models operate:

| Aspect | Cloud (Mistral) | Local (Ollama) |
|--------|-----------------|----------------|
| **Model size** | Full model, uncompressed | Quantized (compressed) for local hardware |
| **Precision** | 16-bit floating point | 4-bit or 8-bit quantization |
| **Parameters** | All parameters active | Reduced precision sacrifices some quality |
| **Updates** | Frequently updated by Mistral | Manual updates required |
| **Reasoning** | Better coherence and accuracy | May struggle with complex tasks |

**The trade-off:**
- **Local** = Privacy + No API costs + Low latency
- **Cloud** = Better quality + More capabilities + Usage costs

#### Improving local model quality

If you want better results from Ollama while staying local, try:

```bash
# Other high-quality models
ollama pull mixtral:8x7b
```

Then update the agent's `.env`:

```bash
OLLAMA_MODEL=mixtral:8x7b
```

**Table**: European LLM models

| Model                 | Number of parameters | Minimum RAM (FP16) | Minimum RAM (4-bit) | GPU? | Notes                                                                 |
|-----------------------|---------------------|-------------------|--------------------|-------------------|-----------------------------------------------------------------------|
| Mistral-7B            | 7B                  | ~14 GB            | ~4-6 GB            | Recommended   | Works on M1 Max with 4-bit quantization.                          |
| Mistral-7B-Instruct   | 7B                  | ~14 GB            | ~4-6 GB            | No            | Instruction-tuned version.                                  |
| Mixtral-8x7B          | 47B (MoE)           | ~30-40 GB         | ~10-12 GB          | Yes           | Sparse model (Mixture of Experts), more efficient than a dense 47B model.|
| Mistral-large         | ~120B (estimado)    | ~240 GB           | ~30-40 GB          | Yes           | Requires high-performance hardware.                                |


**Notes:**
- **FP16**: Standard precision (16-bit), requires plenty of RAM.
- **4-bit**: Aggressive quantization, reduces RAM usage but may slightly affect quality.
- **Recommended GPU**: For models >13B, a GPU (such as NVIDIA A100 or RTX 4090) accelerates inference.
- **Apple M1 Max (32 GB)**: Only viable for models ≤7B with 4-bit quantization.
- **Mistral-large**: Not feasible on an M1 Max; requires at least 64 GB of RAM and a powerful GPU.
- **[OpenEuroLLM](https://openeurollm.eu/)**, which is supported by the European Commission, is expected to launch further LLMs during 2026.


#### Memory Requirements for Mistral Large

- **FP16 (unquantized)**: Approximately **250 GB of RAM** (the model at full precision is extremely demanding and not feasible on consumer hardware) [hardware-corner.net](https://www.hardware-corner.net/llm-database/Mistral/).
- **4-bit (Q4_K_M)**: Between **30-40 GB of RAM** (depending on context size and specific implementation). This quantization reduces memory usage by about 75% compared to FP16, but it is still very demanding for most consumer devices [hardware-corner.net](https://www.hardware-corner.net/llm-database/Mistral/), [apidog.com](https://apidog.com/blog/small-local-llm/).
- **5-bit (Q5_K_M)**: Slightly less than 4-bit, but still over **25-35 GB of RAM**.
- **8-bit (Q8_0)**: Around **50-70 GB of RAM**, as it uses more bits per weight than more aggressively quantized versions [apidog.com](https://apidog.com/blog/small-local-llm/).


Technically, **Ollama does support running non-quantized (FP16/FP32) versions of models**, but for **Mistral-large (123B parameters)**, there are major practical limitations:

- **Memory Requirements**: The non-quantized (FP16) version of Mistral-large requires **around 250 GB of RAM** to load the model weights alone. This is far beyond the capacity of most consumer hardware, including high-end workstations [[hardware-corner.net](https://www.hardware-corner.net/llm-database/Mistral/)].
- **Ollama's Default Behavior**: Ollama typically uses quantized versions (e.g., `Q4_K_M`) by default for large models to make them feasible on consumer hardware. Non-quantized versions are rarely provided for models of this size due to their impractical memory demands [[apxml.com](https://apxml.com/tools/vram-calculator)].
- **Hardware Feasibility**: Even if you could obtain an FP16 version, running it would require a system with **250+ GB of RAM and a powerful GPU** (e.g., multiple A100/H100 GPUs), which is not typical for personal or even most professional setups.


### 5.4 Conversation Logging

> **Note:** Conversation logging should only be used during testing phases. Disable it in production environments to protect user privacy.

TOMMI can log all conversations to a file for auditing or analysis purposes. Logs are stored in `web/logs/conversations.log` and include:

- Timestamp
- Client IP address
- Session ID
- Agent ID and name
- Question asked
- Response (truncated to 500 characters)

**Enabling/Disabling logging:**

During installation, the setup script asks whether to enable logging (default: disabled). You can change this setting later by editing the `web/.env` file:

```
ENABLE_LOGGING=true   # to enable
ENABLE_LOGGING=false  # to disable
```

Valid values: `true`, `1`, `yes` (enabled) or `false`, `0`, `no` (disabled).

[↑ Back to index](#index){.back-to-top}

---

## 6. Quick Reference

### 6.1 End-User Commands

| Task | Command |
|------|---------|
| Create new agent (web) | Start web hub, then click "Create Agent" button |
| Create new agent (CLI) | `python apps/crear_agente.py` |
| Start web hub | `web/run_html_server.sh` (Linux/macOS) or `web\run_html_server.bat` (Windows) |
| Interactive CLI | `cd web && source .venv/bin/activate && python cli.py` |
| CLI with specific agent | `python cli.py my_agent` |
| List agents (CLI) | `python cli.py -l` |

### 6.2 Developer API

| Task | Endpoint |
|------|----------|
| List agents | `GET /api/agents` |
| Chat | `POST /api/chat` |
| Stream chat | `GET /api/chat/stream` |
| Initialize agent | `POST /api/agents/<agent_id>/init` |
| Reindex RAG agent | `POST /api/agents/<agent_id>/reindex` |
| Get DB schema (Text2SQL) | `GET /schema` |

### 6.3 Setup Commands

| Task | Windows | Linux/macOS |
|------|---------|-------------|
| Initial setup | `apps\setup.bat` | `./apps/setup.sh` |

[↑ Back to index](#index){.back-to-top}

---

## 7. Troubleshooting: Error Codes Reference

TOMMI uses structured error codes to help you quickly identify and resolve issues. When an error occurs, you'll see a code like **Error 101** or **Error 305**. Use this reference to understand and fix the problem.

### Error Code Structure

| Range | Category | Description |
|-------|----------|-------------|
| **1xx** | LLM Connection | Problems connecting to Ollama or Mistral |
| **2xx** | Agent | Issues with agent configuration or loading |
| **3xx** | Data | Problems with data files, PDFs, or databases |
| **5xx** | Server | Server-side or streaming errors |

---

### 7.1 LLM Connection Errors (1xx)

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| **101** | Ollama is not running | Ollama service is not started | 1. Install Ollama from https://ollama.com<br>2. Run: `ollama serve` |
| **102** | Model not found in Ollama | The specified model hasn't been downloaded | Run: `ollama pull <model_name>` |
| **103** | Ollama returned an error | Ollama is running but returned an HTTP error | Check Ollama logs; restart Ollama service |
| **104** | Ollama timeout | Ollama didn't respond within 5 seconds | Check that Ollama is running: `ollama serve` |
| **105** | MISTRAL_API_KEY not configured | Missing API key for Mistral Cloud | Add `MISTRAL_API_KEY=your_key` to `.env` file |
| **106** | Invalid Mistral API key | The API key is incorrect or expired | Get a new key at https://console.mistral.ai |
| **107** | Mistral API error | Mistral returned an HTTP error | Check Mistral status at https://status.mistral.ai |
| **108** | Cannot connect to Mistral | Network issues or Mistral unavailable | Check your internet connection |
| **109** | Unknown LLM error | Unexpected error during LLM health check | Check server logs for details |

---

### 7.2 Agent Errors (2xx)

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| **201** | Agent not found | Agent ID doesn't exist | Verify the agent folder exists in `agents/` directory |
| **202** | Agent file not found | Missing `agent.py` in agent folder | Ensure the agent directory contains both `agent.py` and `app.py` |
| **203** | Invalid agent configuration | `AGENT_CONFIG` in `app.py` is malformed | Check syntax of `AGENT_CONFIG` dictionary in `app.py` |
| **204** | Agent not initialized | Agent failed to initialize | Restart the server; check agent initialization logs |
| **205** | Failed to load agent | Syntax error or import error in agent code | Check the agent's Python code for errors |

---

### 7.3 Data Errors (3xx)

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| **301** | Data file not found | Missing `data/data.md` | Create `data/data.md` with your knowledge base content |
| **302** | No documents in docs folder | Empty `data/docs/` for RAG agent | Add `.txt`, `.md`, or `.pdf` files to `data/docs/` |
| **303** | PDF extraction error | Corrupted PDF or pypdf issue | Verify PDF opens correctly; run `pip install pypdf` |
| **304** | ChromaDB error | Database corruption or permission issue | Delete `data/chroma_db/` and call `/reindex` endpoint |
| **305** | Database not found | Missing SQLite database | Create or copy your database to `data/database.db` |
| **306** | Context too large | `data/data.md` exceeds 100KB | Reduce file size or switch to RAG agent type |
| **307** | ChromaDB Python incompatible | ChromaDB not compatible with Python 3.14+ | Install Python 3.12 or 3.13 and recreate `.venv` |

---

### 7.4 Server Errors (5xx)

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| **501** | Streaming error | Error during response streaming | Check server logs for details |
| **502** | Session not found | Invalid or expired session ID | Start a new conversation |
| **503** | Internal server error | Unexpected server-side error | Check server logs; restart if needed |
| **504** | Port in use | Another process is using the server port | Run `./liberar-puerto.sh 8000` to free the port |

---

### General Debugging Tips

1. **Port already in use (Error 504):** If you see `ERROR 504. Port in use`, it means another process is using port 8000 (often a previous server instance that wasn't closed properly). To fix it:
   ```bash
   cd web
   ./liberar-puerto.sh 8000
   ```
   Then start the server again. You can use this script with any port number.

2. **Check the error code:** Look for "Error XXX" in the message and find it in the tables above.

2. **Check logs:** Review the terminal output where the server is running:
   ```bash
   # Logs show detailed error information
   cd web && uvicorn app:app --reload
   ```

3. **Verify environment:** Ensure the virtual environment is activated:
   ```bash
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

4. **Test components individually:**
   - Test Ollama: `ollama list` and `ollama run mistral "Hello"`
   - Test Mistral API: Verify your key at https://console.mistral.ai
   - Test agent: Use CLI mode `python cli.py <agent_id>` before web interface

5. **Restart services:** After changing `.env` files, restart the web server for changes to take effect.

6. **Check file permissions:** Ensure the user running TOMMI has read/write access to agent directories and data files.

[↑ Back to index](#index){.back-to-top}

---

## Annex A: Terminal Command Reference

Quick reference of useful terminal commands for working with TOMMI agents.

### A.1 Environment Setup

```bash
# Activate virtual environment
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate             # Windows

# Deactivate virtual environment
deactivate

# Check Python version
python --version

# Install dependencies
pip install -r requirements.txt
```

### A.2 Agent Management

```bash
# Create a new agent
python apps/crear_agente.py

# List available agents
python web/cli.py -l

# Test a specific agent interactively
cd web && python cli.py <agent_id>

# Run batch tests
python web/batch_test.py <agent_id> <questions_file>

# Run batch tests with session context
python web/batch_test.py <agent_id> <questions_file> -s
```

### A.3 Web Server

```bash
# Start the web hub (recommended)
./web/run_html_server.sh           # Linux/macOS
web\run_html_server.bat            # Windows

# Start server manually (with auto-reload)
cd web && uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Free a port in use
./web/liberar-puerto.sh 8000

# Check which process is using a port
lsof -i :8000                      # Linux/macOS
netstat -ano | findstr :8000       # Windows
```

### A.4 RAG Agent Operations

```bash
# Reindex documents (via API)
curl -X POST http://localhost:8000/api/agents/<agent_id>/reindex

# Delete ChromaDB to force full reindex
rm -rf agents/<agent_id>/data/chroma_db/
```

### A.5 RAG+Metadata Agent Operations

```bash
# Reindex documents with metadata (via API)
curl -X POST http://localhost:8000/api/agents/<agent_id>/reindex

# Get metadata for all indexed documents
curl http://localhost:8000/api/agents/<agent_id>/metadata

# Search papers by topic across universities
curl "http://localhost:8000/api/agents/<agent_id>/topic-search?topic=ethics"

# Get all papers grouped by university
curl http://localhost:8000/api/agents/<agent_id>/publications-search

# Delete ChromaDB to force full reindex with metadata
rm -rf agents/<agent_id>/data/chroma_db/
```

**Creating a new agent for a different research topic:**
```bash
# 1. Copy an existing agent
cp -r agents/responsible_ai agents/my_new_topic

# 2. Edit config.json (agent name, topic, universities, etc.)
nano agents/my_new_topic/config.json

# 3. Replace data files
rm agents/my_new_topic/data/docs/*.pdf
rm agents/my_new_topic/data/*_papers.json
# ... add your own PDFs, papers.json files, and metadata.json

# 4. Delete old ChromaDB index
rm -rf agents/my_new_topic/data/chroma_db/

# 5. Restart the server — the new agent will be auto-detected
```

### A.6 Text2SQL Agent Operations

```bash
# View database schema (via API)
curl http://localhost:8000/schema

# Create a new SQLite database
sqlite3 agents/<agent_id>/data/database.db < schema.sql

# Open database interactively
sqlite3 agents/<agent_id>/data/database.db

# Common SQLite commands
.tables                            # List all tables
.schema <table_name>               # Show table structure
.quit                              # Exit SQLite
```

### A.7 Ollama Commands (Local LLM)

```bash
# Start Ollama server
ollama serve

# List available models
ollama list

# Download a model
ollama pull mistral
ollama pull mixtral:8x7b

# Test a model
ollama run mistral "Hello, world"

# Delete a model
ollama rm <model_name>

# Check Ollama status
curl http://localhost:11434/api/tags
```

### A.8 API Testing with curl

```bash
# List all agents
curl http://localhost:8000/api/agents

# Send a chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "<agent_id>", "message": "Hello"}'

# Send message with grounding verification
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "<agent_id>", "message": "Your question", "verify": true}'

# Check agent health
curl http://localhost:8000/api/agents/<agent_id>/health
```

### A.9 Logs and Debugging

```bash
# View conversation logs (if enabled)
tail -f web/logs/conversations.log

# View last 50 lines of logs
tail -50 web/logs/conversations.log

# Search logs for specific agent
grep "<agent_id>" web/logs/conversations.log

# Clear logs
> web/logs/conversations.log
```

### A.10 Distribution

```bash
# Create distribution package
./apps/crear_dist.sh               # Linux/macOS
apps\crear_dist.bat                # Windows
```

### A.11 Useful Environment Variables

```bash
# Check current LLM configuration
cat web/.env | grep LLM
cat agents/<agent_id>/.env | grep LLM

# Edit environment variables
nano web/.env                      # Linux/macOS
notepad web\.env                   # Windows
```

[↑ Back to index](#index){.back-to-top}

---

## Annex B: CLI Quick Reference

Quick reference for interacting with TOMMI agents from the command line.

### B.1 Interactive CLI

The interactive CLI (`web/cli.py`) allows direct conversation with agents without starting a web server.

```bash
# List available agents
python web/cli.py -l
python web/cli.py --list

# Start interactive session with a specific agent
python web/cli.py conf26
python web/cli.py pisha2

# Without arguments - interactive agent selection menu
python web/cli.py

# Show help
python web/cli.py -h
python web/cli.py --help
```

**Exiting the session:** Type `exit`, `quit`, `q`, or `salir` to end the conversation.

### B.2 Batch Testing

The batch testing tool (`web/batch_test.py`) runs multiple questions against an agent from a file.

```bash
# Run questions from a file
python web/batch_test.py conf26 questions.txt

# Maintain session context between questions
python web/batch_test.py conf26 questions.txt --session

# Save results to a specific file
python web/batch_test.py conf26 questions.txt -o results.json

# Display results in console only (no file output)
python web/batch_test.py conf26 questions.txt --no-save

# List available agents
python web/batch_test.py --list-agents
```

**Question file format:** One question per line. Lines starting with `#` are treated as comments and ignored.

### B.3 HTTP API with curl

When the web server is running, you can interact with agents via HTTP.

```bash
# Send a question (agent-specific endpoint)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Your question here"}'

# Send a question to a specific agent (central API)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "conf26", "message": "Your question"}'

# List all available agents
curl http://localhost:8000/api/agents

# Check agent health
curl http://localhost:8000/api/agents/<agent_id>/health
```

[↑ Back to index](#index){.back-to-top}
