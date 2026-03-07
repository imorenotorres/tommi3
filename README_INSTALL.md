This document explains step-by-step how to install Tommi. If you have already downloaded and unzipped the Tommi installation file, jump to step 2. Requirements.

## 1. Download Tommi

Get the latest version of Tommi and uncompress it to where you want to work in your Hard Disk. You may want to rename the long name of the main folder with just Tommi.

## 2. Requirements

1. Python 3.10 or higher
2. One of the following LLM providers:
   - **Mistral API key** (cloud, recommended for starters)
   - **Ollama** (local, easy setup)
   - **vLLM** (local, high-performance)

## 3. Installation

1. Open a terminal in the TOMMI folder
2. Run the setup script:
   - **Windows:** `apps\setup.bat` (double-click or run from cmd)
   - **Linux/macOS:** `./apps/setup.sh`
3. The script will automatically:
   - Create the virtual environment `.venv` in the `web/` folder
   - Install all dependencies
   - Configure conversation logging (optional, useful for testing)
   - Configure the Mistral API key for each agent

## 4. Start the server

### Linux/macOS

- **Local access (localhost):**
  ```bash
  cd web && source .venv/bin/activate && uvicorn app:app --reload
  ```

- **Network access:**
  ```bash
  cd web && source .venv/bin/activate && uvicorn app:app --reload --host 0.0.0.0
  ```

### Windows

- **Local access (localhost):**
  ```cmd
  cd web && .venv\Scripts\activate && uvicorn app:app --reload
  ```

- **Network access:**
  ```cmd
  cd web && .venv\Scripts\activate && uvicorn app:app --reload --host 0.0.0.0
  ```

### Notes

- **Open in browser:** http://localhost:8000
- **Network access:** If the server has IP `150.150.150.150`, users will access `http://150.150.150.150:8000`
- **Stop:** `Ctrl+C` in the terminal

With the server running, we recommend you to open the Tommi Virtual Tutor, which provides plenty of information about Tommi.

## 5. Troubleshooting

### "No such file or directory: python3"
Install Python 3.10 or higher.

### "Permission denied: ./apps/setup.sh"
Run: `chmod +x apps/setup.sh`

### The page doesn't load
1. Verify the server is running
2. Check for errors in the terminal

## 6. Prompt Templates

The `prompts/` folder contains base prompt templates for each agent type:
- `prompt_Oneshot.txt` - Template for oneshot agents
- `prompt_RAG.txt` - Template for RAG agents
- `prompt_ToolCall.txt` - Template for toolcall agents

When creating a new agent with `python apps/crear_agente.py`, you can select a template instead of writing a prompt from scratch.

## 7. LLM Providers

TOMMI supports three LLM providers:

| Provider | Type | Best For |
|----------|------|----------|
| **Mistral Cloud** | Cloud | Getting started, no local setup required |
| **Ollama** | Local | Development, easy local inference |
| **vLLM** | Local | Production, high-performance workloads |

See `HOWTO.md` section 5.2 for detailed configuration of local LLMs.

## 8. More information

To learn how to create agents and use the web interface:

- See `HOWTO.md` or `HOWTO.html`
- Once you have your web interface in place, you can start using "Tommi virtual tutor"
