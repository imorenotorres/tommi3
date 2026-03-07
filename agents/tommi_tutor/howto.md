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

::: {.preface}
TOMMI is an easy to use educational tool that serves to create and test AI agents. With TOMMI:

- IT staff will have rapid hands-on experience with different types of agents;
- academic and admin staff, ideally supported by IT experts, will be able to create agents for their professional context;
- end-users (students, researchers, admin staff) will be able to experience with this technology and explore its potential benefits, thus fostering digital literacy.

TOMMI is built entirely on **open source** tools—Python, FastAPI, ChromaDB, and more—ensuring transparency and flexibility.
:::

::: {.caution}
**Caution:** The use of TOMMI agents for other goals apart from training requires close supervision. IT experts should pay special attention to two main risks. First, no sensitive data should be added unless an IT expert confirms that the agent deployment is safe (e.g., only specific persons have access to the server). Second, adding new tools to TOMMI is feasible, but it may result in dangerous situations (e.g., a tool deleting your hard disk); modifications made on the agents' templates are made at your own risk.
:::

---

## Index

1. [Introduction to Agents](#introduction-to-agents)
   - [1.1 Oneshot Agents](#oneshot-agents)
   - [1.2 RAG Agents](#rag-agents-retrieval-augmented-generation)
   - [1.3 Toolcall Agents](#toolcall-agents)
2. [Setting Up the TOMMI Agents Service](#setting-up-the-tommi-agents-service)
   - [2.1 Prerequisites](#prerequisites)
   - [2.2 Installation](#installation)
   - [2.3 Project Structure](#project-structure)
   - [2.4 Configuring LLMs on cloud](#configuring-llms-on-cloud)
3. [Creating Agents](#creating-agents)
   - [3.1 Using the Interactive Creator](#using-the-interactive-creator)
   - [3.2 Prompt Templates](#prompt-templates)
   - [3.3 Generated Files](#generated-files)
   - [3.4 Agent Configuration](#agent-configuration)
   - [3.5 Adding Data to Your Agent](#adding-data-to-your-agent)
     - [3.5.1 Oneshot Agents: Single Data File](#oneshot-agents-single-data-file)
     - [3.5.2 RAG Agents: Document Collection](#rag-agents-document-collection)
     - [3.5.3 Toolcall Agents: Data + Tools](#toolcall-agents-data--tools)
4. [Interacting with Agents](#interacting-with-agents)
   - [4.1 Web Interface](#web-interface)
     - [4.1.1 Starting the Web Hub](#starting-the-web-hub)
     - [4.1.2 Using the Interface](#using-the-interface)
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
   - [7.4 Tool Errors (4xx)](#tool-errors-4xx)
   - [7.5 Server Errors (5xx)](#server-errors-5xx)

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

TOMMI supports three agent types, each suited for different use cases:

### 1.1 Oneshot Agents

The simplest type. Loads all data into memory and includes it directly in the LLM context.

**How it works:**
1. Loads data from `data/data.md` at startup
2. Includes the full data in every system prompt
3. LLM generates response using the embedded context

**Best for:**
- Small to moderate knowledge bases (< 100KB)
- FAQ systems
- Static information assistants

**Example:** Conference information assistant that answers questions about schedules, speakers, and venues.

### 1.2 RAG Agents (Retrieval-Augmented Generation)

Uses semantic search to find relevant information before generating responses.

**How it works:**
1. Indexes documents from `data/docs/` into ChromaDB vector database
2. When a query arrives, searches for the most relevant chunks
3. Includes only relevant context in the LLM prompt
4. Generates response based on retrieved information

**Best for:**
- Large document collections
- Academic papers or manuals
- Frequently updated content (supports re-indexing)

**Example:** Academic proceedings Q&A system that searches through hundreds of papers.

### 1.3 Toolcall Agents

Can execute functions and tools to complete complex tasks.

**How it works:**
1. Defines available tools (Python functions) with descriptions
2. LLM decides which tools to call based on the query
3. Agent executes tools and feeds results back to LLM
4. Loop continues until LLM provides a final response (max 10 iterations)

**Best for:**
- Database queries
- Calculations and data analysis
- External API integrations
- Multi-step reasoning tasks

**Example:** University mobility data assistant that can query SQLite databases, perform calculations, and search documents.

[↑ Back to index](#index){.back-to-top}

---

## 2. Setting Up the TOMMI Agents Service

### 2.1 Prerequisites

- Python 3.10+ (for Oneshot and Toolcall agents)
- Python 3.11-3.13 (for RAG agents - ChromaDB is **not compatible** with Python 3.14+)
- Mistral API key

> **Note:** If you plan to use RAG agents and have Python 3.14+, install Python 3.12:
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
│   ├── crear_agente.py      # Agent creation script
│   ├── crear_dist.sh        # Distribution script (Linux/macOS)
│   └── crear_dist.bat       # Distribution script (Windows)
├── prompts/                 # Prompt templates for agent creation
│   ├── prompt_Oneshot.txt   # Base prompt for oneshot agents
│   ├── prompt_RAG.txt       # Base prompt for RAG agents
│   └── prompt_ToolCall.txt  # Base prompt for toolcall agents
├── web/                     # Central web service hub
│   ├── app.py               # FastAPI server
│   ├── agent_runner.py      # Agent discovery engine
│   └── static/              # Frontend files
└── agents/                  # All agents are stored here
    ├── your_agent/          # Your custom agents
    ├── conf26_nube/         # Example: conference assistant (cloud)
    ├── conf26_local/        # Example: conference assistant (local)
    └── ...
```

### 2.4 Configuring LLMs

TOMMI supports two LLM providers:
- **Mistral Cloud** (default) - LLMs on the cloud, requires API key
- **Ollama** (optional) - LLMs on premise, requires local installation

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

### 3.1 Using the Interactive Creator

The easiest way to create a new agent:

```bash
python apps/crear_agente.py
```

The script will prompt you for:

1. **Agent type** (1=oneshot, 2=rag, 3=toolcall)
2. **Agent ID** - Unique identifier (lowercase, alphanumeric)
3. **Output directory** - Where to create the agent
4. **Display name** - Human-readable name
5. **Description** - What the agent does
6. **Welcome message** - Greeting shown to users
7. **Example queries** - Sample questions users can ask
8. **System prompt** - Instructions for the LLM behavior
9. **Model** - Which Mistral model to use
10. **API key** - Your Mistral API key (optional, can add later)

### 3.2 Prompt Templates

When creating a new agent, you can choose from pre-defined prompt templates instead of writing a system prompt from scratch. Templates are stored in the `prompts/` folder and provide a solid starting point for each agent type.

**Available templates:**

| Template | Description |
|----------|-------------|
| `prompt_Oneshot.txt` | Instructions for data-based assistants |
| `prompt_RAG.txt` | Instructions for document retrieval assistants |
| `prompt_ToolCall.txt` | Instructions for tool-using assistants |

**How it works:**

During agent creation (`python apps/crear_agente.py`), you'll see:

```
System prompt:
  Available templates:
    1. prompt_ToolCall
    2. prompt_Oneshot
    3. prompt_RAG
    4. Write custom prompt

  Select template [1-4]:
```

**Template variables:**

Templates support the `{agent_name}` variable, which is automatically replaced with your agent's name. For example:

```
Eres {agent_name}, un asistente con acceso a herramientas.
```

Becomes:

```
Eres Mi Asistente, un asistente con acceso a herramientas.
```

**Customizing templates:**

1. **Edit existing templates:** Modify files in `prompts/` to change the default behavior for all new agents of that type.
2. **Add new templates:** Create new `.txt` files in `prompts/`. They will automatically appear in the selection menu.
3. **Edit after selection:** When creating an agent, you can edit the loaded template before it's saved.

**Tip:** Templates are only used during agent creation. Once an agent is created, its prompt is stored in `agent.py` and can be edited independently.

### 3.3 Generated Files

The creator generates a complete agent structure:

```
your_agent/
├── agent.py           # Core agent logic
├── app.py             # FastAPI wrapper with AGENT_CONFIG
├── requirements.txt   # Python dependencies
├── .env               # API credentials
├── .gitignore         # Security (ignores .env)
├── run.sh             # Startup script
├── README.md          # Documentation
└── data/
    ├── data.md        # (oneshot/toolcall) Knowledge base
    └── docs/          # (rag) Document folder for indexing
```

### 3.4 Agent Configuration

Each agent defines its metadata in `app.py`:

```python
AGENT_CONFIG = {
    "id": "my_agent",
    "name": "My Agent",
    "type": "oneshot",  # or "rag" or "toolcall"
    "description": "Helps with specific tasks",
    "welcome_message": "Hello! How can I help you?",
    "example_queries": [
        "What can you do?",
        "Tell me about X"
    ]
}
```

You can edit `app.py` at any time to add or remove example queries, change the welcome message, update the description, or modify any other metadata field.

### 3.5 Adding Data to Your Agent

**Why data matters:** LLMs have a knowledge cutoff date and no access to your private information. Without data, an agent is just a generic chatbot. With your data, it becomes a specialized assistant that can answer questions about your specific domain.

Each agent type uses a different approach:

- **Oneshot:** Injects all data directly into every prompt
- **RAG:** Retrieves only relevant chunks from large document collections
- **Toolcall:** Queries live data sources (databases, APIs) at runtime

#### 3.5.1 Oneshot Agents: Single Data File

Oneshot agents load all their knowledge from a single Markdown file.

**Data location:** `data/data.md`

**How to add data:**
1. Edit `data/data.md` with all the information your agent needs
2. Use Markdown formatting for structure (headers, lists, tables)
3. Keep the file under ~100KB for optimal performance

**Example `data/data.md`:**
```markdown
# Company Information

## Products
- **Product A**: Description of product A, pricing $99
- **Product B**: Description of product B, pricing $149

## Contact
- Email: support@company.com
- Phone: +1-800-123-4567

## FAQ
### How do I reset my password?
Go to Settings > Security > Reset Password...
```

**Note:** The entire file is included in every LLM prompt, so keep it concise and well-organized.

---

#### 3.5.2 RAG Agents: Document Collection

RAG agents index multiple documents and retrieve relevant chunks at query time.

> **Important:** RAG agents require **Python 3.11-3.13**. ChromaDB is not compatible with Python 3.14+. If you see Error 307, install Python 3.12 and recreate the virtual environment.

**Data location:** `data/docs/`

**Supported formats:** `.txt`, `.md`, `.pdf`

**How to add data:**
1. Place your documents in `data/docs/`
2. Use descriptive filenames (e.g., `user-manual.md`, `api-reference.txt`)
3. Documents are automatically chunked and indexed at startup
4. After adding new documents, call the `/reindex` endpoint

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

**Re-indexing after changes:**
```bash
curl -X POST http://localhost:8000/reindex
```

**How it works internally:**
- PDF text is extracted using `pypdf`
- Documents are split into chunks (~500 tokens each)
- Each chunk is embedded using `sentence-transformers` (all-MiniLM-L6-v2)
- Embeddings are stored in ChromaDB at `data/chroma_db/`
- On query, the 3 most relevant chunks are retrieved and included in the prompt

**Tip:** Structure your documents with clear headers and sections for better retrieval accuracy.

---

#### 3.5.3 Toolcall Agents: Data + Tools

Toolcall agents can access data through both static files and dynamic tools.

**Data locations:**
- `data/data.md` - Static knowledge base (searchable via `buscar_en_datos` tool)
- `data/database.db` - SQLite database (queryable via SQL tools)

**How to add static data:**

Same as oneshot agents, edit `data/data.md`:
```markdown
# Project Guidelines

## Coding Standards
- Use 4 spaces for indentation
- Maximum line length: 120 characters
...
```

**How to add database data:**

1. Create or copy an SQLite database to `data/database.db`
2. The agent can query it using the built-in `consultar_sql` tool

**Tip:** It helps to include a database schema in `data/data.md` or in the system prompt, describing the main tables, their relationships, and any views. This allows the agent to write more accurate SQL queries.

**Built-in tools for data access:**

| Tool | Description |
|------|-------------|
| `buscar_en_datos` | Search text in `data/data.md` |
| `consultar_sql` | Execute SQL queries on the database |
| `listar_tablas` | List all tables in the database |
| `describir_tabla` | Get schema of a specific table |
| `calcular` | Evaluate mathematical expressions |

**Adding custom tools:**

Edit `agent.py` to add new tools:

```python
# 1. Define the function
def my_custom_tool(param1: str, param2: int) -> str:
    """Your tool logic here"""
    return f"Result for {param1} with {param2}"

# 2. Add to AVAILABLE_TOOLS dictionary
AVAILABLE_TOOLS = {
    "my_custom_tool": my_custom_tool,
    # ... existing tools
}

# 3. Add tool specification for the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "my_custom_tool",
            "description": "Describe what this tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Description of param1"
                    },
                    "param2": {
                        "type": "integer",
                        "description": "Description of param2"
                    }
                },
                "required": ["param1", "param2"]
            }
        }
    },
    # ... existing tools
]
```

[↑ Back to index](#index){.back-to-top}

---

## 4. Interacting with Agents

TOMMI offers two ways to interact with your agents:

- **Web Interface:** A visual interface accessible from any browser, ideal for end users.
- **Terminal:** Direct interaction via command line, useful for testing and automation.

### 4.1 Web Interface

#### 4.1.1 Starting the Web Hub

The web hub provides a unified interface to all your agents.

**Local access (localhost only):**

```bash
cd web && source .venv/bin/activate && uvicorn app:app --reload
```

**Network access (other devices can connect):**

```bash
cd web && source .venv/bin/activate && uvicorn app:app --reload --host 0.0.0.0
```

Access the web interface at:
- **Local:** `http://localhost:8000`
- **Network:** `http://<server-ip>:8000` (e.g., if server IP is `150.150.150.150`, users access `http://150.150.150.150:8000`)

**Custom port:** Use the `--port` option:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

#### 4.1.2 Using the Interface

Once the server is running, open your browser and go to the address shown in the terminal.

![TOMMI Web Interface](tommi_frontend.png)

1. **Select an agent:** Use the dropdown menu on the left side to choose the agent you want to talk to.
2. **Read the description:** Below the selector, you'll see a brief description of what the selected agent can help you with.
3. **Try example questions:** Click on any of the example questions shown on the left panel to quickly start a conversation.
4. **Type your question:** Write your question in the text box at the bottom and press Enter or click Send.
5. **Read the response:** The agent's response will appear in the chat area. You can continue the conversation by asking follow-up questions.

**Tip:** The agent remembers your conversation, so you can ask follow-up questions without repeating context.

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

By default, TOMMI uses **Mistral Cloud**. To use **local LLMs with Ollama**, you have two options:

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

The web interface displays a badge in the sidebar showing the current LLM provider:

| Badge | Meaning |
|-------|---------|
| 🏠 **Local (model)** | Using Ollama with the specified model |
| ☁️ **Cloud (Mistral)** | Using Mistral cloud API |

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
| Create new agent | `python apps/crear_agente.py` |
| Start web hub (local) | `cd web && source .venv/bin/activate && uvicorn app:app --reload` |
| Start web hub (network) | `cd web && source .venv/bin/activate && uvicorn app:app --reload --host 0.0.0.0` |
| Interactive CLI | `cd web && source .venv/bin/activate && python cli.py` |
| CLI with specific agent | `python cli.py my_agent` |
| List agents (CLI) | `python cli.py -l` |

### 6.2 Developer API

| Task | Endpoint |
|------|----------|
| List agents | `GET /api/agents` |
| Chat | `POST /api/chat` |
| Stream chat | `GET /api/chat/stream` |
| Reindex RAG | `POST /reindex` |

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
| **4xx** | Tools | Errors in toolcall agent operations |
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
| **307** | ChromaDB Python incompatible | ChromaDB not compatible with Python 3.14+ | Install Python 3.12 or 3.13 and recreate venv |

---

### 7.4 Tool Errors (4xx)

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| **401** | Tool not found | Tool name doesn't match `AVAILABLE_TOOLS` | Verify tool name in `agent.py` matches exactly |
| **402** | SQL error | Invalid SQL syntax or operation | Review the query; add schema info to system prompt |
| **403** | Invalid math expression | Expression contains invalid characters | Use valid Python math: `+`, `-`, `*`, `/`, `()` |
| **404** | Tool execution error | Exception in tool function | Check tool function code for bugs |
| **405** | Maximum iterations reached | Agent stuck in tool-calling loop | Review system prompt; give clearer instructions |
| **406** | Table not found | SQL query references non-existent table | Use `listar_tablas` to check available tables |

---

### 7.5 Server Errors (5xx)

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| **501** | Streaming error | Error during response streaming | Check server logs for details |
| **502** | Session not found | Invalid or expired session ID | Start a new conversation |
| **503** | Internal server error | Unexpected server-side error | Check server logs; restart if needed |

---

### General Debugging Tips

1. **Check the error code:** Look for "Error XXX" in the message and find it in the tables above.

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
   - Test Mistral API: Verify your key at the Mistral console
   - Test agent: Use CLI mode `python cli.py <agent_id>` before web interface

5. **Restart services:** After changing `.env` files, restart the web server for changes to take effect.

6. **Check file permissions:** Ensure the user running TOMMI has read/write access to agent directories and data files.

[↑ Back to index](#index){.back-to-top}
