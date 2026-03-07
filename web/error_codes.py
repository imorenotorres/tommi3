"""
TOMMI Error Codes - Códigos de error centralizados

Estructura de códigos:
- 1xx: Errores de conexión LLM
- 2xx: Errores de agentes
- 3xx: Errores de datos
- 4xx: Errores de herramientas (toolcall)
- 5xx: Errores de servidor/streaming
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TommiError:
    """Representa un error de TOMMI con código, mensaje e instrucciones."""
    code: int
    error_type: str
    message: str
    instructions: Optional[str] = None


# =============================================================================
# 1xx - Errores de conexión LLM
# =============================================================================

LLM_OLLAMA_NOT_RUNNING = TommiError(
    code=101,
    error_type="ollama_not_running",
    message="Ollama is not running",
    instructions="1. Install Ollama from https://ollama.com\n2. Run: ollama serve"
)

LLM_MODEL_NOT_FOUND = TommiError(
    code=102,
    error_type="model_not_found",
    message="Model '{model}' is not downloaded in Ollama",
    instructions="Run in terminal: ollama pull {model}"
)

LLM_OLLAMA_ERROR = TommiError(
    code=103,
    error_type="ollama_error",
    message="Ollama returned an error"
)

LLM_OLLAMA_TIMEOUT = TommiError(
    code=104,
    error_type="ollama_timeout",
    message="Ollama is not responding (timeout)",
    instructions="Check that Ollama is running: ollama serve"
)

LLM_NO_API_KEY = TommiError(
    code=105,
    error_type="no_api_key",
    message="MISTRAL_API_KEY is not configured",
    instructions="Add MISTRAL_API_KEY=your_key to the agent's .env file"
)

LLM_INVALID_API_KEY = TommiError(
    code=106,
    error_type="invalid_api_key",
    message="Mistral API key is invalid",
    instructions="Get a valid API key at https://console.mistral.ai"
)

LLM_MISTRAL_ERROR = TommiError(
    code=107,
    error_type="mistral_error",
    message="Mistral API error: {status_code}"
)

LLM_CONNECTION_ERROR = TommiError(
    code=108,
    error_type="connection_error",
    message="Could not connect to Mistral: {details}",
    instructions="Check your internet connection"
)

LLM_UNKNOWN_ERROR = TommiError(
    code=109,
    error_type="unknown_llm_error",
    message="Unknown LLM error: {details}"
)

LLM_VLLM_NOT_RUNNING = TommiError(
    code=110,
    error_type="vllm_not_running",
    message="vLLM server is not running",
    instructions="1. Start vLLM with: python -m vllm.entrypoints.openai.api_server --model <model_name>\n2. Verify VLLM_BASE_URL in .env"
)

LLM_VLLM_ERROR = TommiError(
    code=111,
    error_type="vllm_error",
    message="vLLM server error: {status_code}"
)

LLM_VLLM_MODEL_NOT_FOUND = TommiError(
    code=112,
    error_type="vllm_model_not_found",
    message="Model '{model}' is not loaded in vLLM",
    instructions="Restart vLLM with the correct model: python -m vllm.entrypoints.openai.api_server --model {model}"
)


# =============================================================================
# 2xx - Errores de agentes
# =============================================================================

AGENT_NOT_FOUND = TommiError(
    code=201,
    error_type="agent_not_found",
    message="Agent '{agent_id}' not found",
    instructions="Check that the agent exists in the agents/ directory"
)

AGENT_FILE_NOT_FOUND = TommiError(
    code=202,
    error_type="agent_file_not_found",
    message="Agent file not found: {path}",
    instructions="Ensure the agent directory contains agent.py and app.py"
)

AGENT_CONFIG_INVALID = TommiError(
    code=203,
    error_type="agent_config_invalid",
    message="Invalid agent configuration: {details}",
    instructions="Check AGENT_CONFIG in the agent's app.py file"
)

AGENT_NOT_INITIALIZED = TommiError(
    code=204,
    error_type="agent_not_initialized",
    message="Agent '{agent_id}' is not initialized",
    instructions="Restart the server or check agent initialization logs"
)

AGENT_LOAD_ERROR = TommiError(
    code=205,
    error_type="agent_load_error",
    message="Failed to load agent '{agent_id}': {details}",
    instructions="Check the agent's code for syntax errors"
)


# =============================================================================
# 3xx - Errores de datos
# =============================================================================

DATA_FILE_NOT_FOUND = TommiError(
    code=301,
    error_type="data_file_not_found",
    message="Data file not found: {path}",
    instructions="Create the data/data.md file with your knowledge base"
)

DATA_DOCS_EMPTY = TommiError(
    code=302,
    error_type="docs_empty",
    message="No documents found in data/docs/",
    instructions="Add .txt, .md, or .pdf files to data/docs/"
)

DATA_PDF_EXTRACTION_ERROR = TommiError(
    code=303,
    error_type="pdf_extraction_error",
    message="Error extracting text from PDF: {filename}",
    instructions="Verify the PDF opens correctly; reinstall pypdf with: pip install pypdf"
)

DATA_CHROMADB_ERROR = TommiError(
    code=304,
    error_type="chromadb_error",
    message="ChromaDB indexing error: {details}",
    instructions="Delete data/chroma_db/ folder and call /reindex endpoint"
)

DATA_CHROMADB_PYTHON_INCOMPATIBLE = TommiError(
    code=307,
    error_type="chromadb_python_incompatible",
    message="ChromaDB is not compatible with Python 3.14",
    instructions="RAG agents require Python 3.13 or earlier. Install Python 3.13 and create a new venv."
)

DATA_DATABASE_NOT_FOUND = TommiError(
    code=305,
    error_type="database_not_found",
    message="Database not found: {path}",
    instructions="Create or copy your SQLite database to data/database.db"
)

DATA_CONTEXT_TOO_LARGE = TommiError(
    code=306,
    error_type="context_too_large",
    message="Data file too large ({size}KB). Maximum recommended: 100KB",
    instructions="Reduce data/data.md size or switch to RAG agent type"
)


# =============================================================================
# 4xx - Errores de herramientas (toolcall)
# =============================================================================

TOOL_NOT_FOUND = TommiError(
    code=401,
    error_type="tool_not_found",
    message="Tool not found: {tool_name}",
    instructions="Verify the tool name matches AVAILABLE_TOOLS in agent.py"
)

TOOL_SQL_ERROR = TommiError(
    code=402,
    error_type="sql_error",
    message="SQL error: {details}",
    instructions="Review the query; add schema info to data/data.md or system prompt"
)

TOOL_MATH_ERROR = TommiError(
    code=403,
    error_type="math_error",
    message="Invalid mathematical expression: {expression}",
    instructions="Use valid Python math syntax (e.g., 2+2, 10*5, 100/4)"
)

TOOL_EXECUTION_ERROR = TommiError(
    code=404,
    error_type="tool_execution_error",
    message="Error executing tool '{tool_name}': {details}",
    instructions="Check the tool function code for bugs"
)

TOOL_MAX_ITERATIONS = TommiError(
    code=405,
    error_type="max_iterations",
    message="Maximum iterations reached ({max_iter})",
    instructions="Review system prompt to give clearer instructions"
)

TOOL_TABLE_NOT_FOUND = TommiError(
    code=406,
    error_type="table_not_found",
    message="Table not found: {table_name}",
    instructions="Use listar_tablas tool to check available tables"
)


# =============================================================================
# 5xx - Errores de servidor/streaming
# =============================================================================

SERVER_STREAMING_ERROR = TommiError(
    code=501,
    error_type="streaming_error",
    message="Error during response streaming: {details}"
)

SERVER_SESSION_NOT_FOUND = TommiError(
    code=502,
    error_type="session_not_found",
    message="Session not found: {session_id}",
    instructions="Start a new conversation"
)

SERVER_INTERNAL_ERROR = TommiError(
    code=503,
    error_type="internal_error",
    message="Internal server error: {details}",
    instructions="Check server logs for details"
)


# =============================================================================
# Helper functions
# =============================================================================

def format_error(error: TommiError, **kwargs) -> dict:
    """
    Formatea un TommiError en un diccionario para respuesta JSON.

    Args:
        error: El TommiError a formatear
        **kwargs: Valores para reemplazar en el mensaje (e.g., model='mistral')

    Returns:
        dict con error_code, error_type, error, e instructions
    """
    message = error.message.format(**kwargs) if kwargs else error.message
    instructions = error.instructions.format(**kwargs) if error.instructions and kwargs else error.instructions

    result = {
        "error_code": error.code,
        "error_type": error.error_type,
        "error": message,
    }

    if instructions:
        result["instructions"] = instructions

    return result


def get_error_by_code(code: int) -> Optional[TommiError]:
    """Obtiene un TommiError por su código."""
    all_errors = [
        # 1xx
        LLM_OLLAMA_NOT_RUNNING, LLM_MODEL_NOT_FOUND, LLM_OLLAMA_ERROR,
        LLM_OLLAMA_TIMEOUT, LLM_NO_API_KEY, LLM_INVALID_API_KEY,
        LLM_MISTRAL_ERROR, LLM_CONNECTION_ERROR, LLM_UNKNOWN_ERROR,
        LLM_VLLM_NOT_RUNNING, LLM_VLLM_ERROR, LLM_VLLM_MODEL_NOT_FOUND,
        # 2xx
        AGENT_NOT_FOUND, AGENT_FILE_NOT_FOUND, AGENT_CONFIG_INVALID,
        AGENT_NOT_INITIALIZED, AGENT_LOAD_ERROR,
        # 3xx
        DATA_FILE_NOT_FOUND, DATA_DOCS_EMPTY, DATA_PDF_EXTRACTION_ERROR,
        DATA_CHROMADB_ERROR, DATA_DATABASE_NOT_FOUND, DATA_CONTEXT_TOO_LARGE,
        DATA_CHROMADB_PYTHON_INCOMPATIBLE,
        # 4xx
        TOOL_NOT_FOUND, TOOL_SQL_ERROR, TOOL_MATH_ERROR,
        TOOL_EXECUTION_ERROR, TOOL_MAX_ITERATIONS, TOOL_TABLE_NOT_FOUND,
        # 5xx
        SERVER_STREAMING_ERROR, SERVER_SESSION_NOT_FOUND, SERVER_INTERNAL_ERROR,
    ]

    for error in all_errors:
        if error.code == code:
            return error
    return None
