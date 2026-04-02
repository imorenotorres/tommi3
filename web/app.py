"""
Tommi Web Interface - FastAPI server para interactuar con agentes Tommi
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# Cargar .env de web/ con override para asegurar que se usa la configuración correcta
_web_env = Path(__file__).parent / ".env"
load_dotenv(_web_env, override=True)

from agent_runner import AgentRunner
from error_codes import (
    format_error,
    LLM_OLLAMA_NOT_RUNNING, LLM_MODEL_NOT_FOUND, LLM_OLLAMA_ERROR,
    LLM_OLLAMA_TIMEOUT, LLM_NO_API_KEY, LLM_INVALID_API_KEY,
    LLM_MISTRAL_ERROR, LLM_CONNECTION_ERROR, LLM_UNKNOWN_ERROR,
    LLM_VLLM_NOT_RUNNING, LLM_VLLM_ERROR, LLM_VLLM_MODEL_NOT_FOUND,
    AGENT_NOT_FOUND, SERVER_STREAMING_ERROR
)

# Configuración de logging (activable/desactivable via ENABLE_LOGGING)
ENABLE_LOGGING = os.getenv("ENABLE_LOGGING", "false").lower() in ("true", "1", "yes")

# Configurar logging de conversaciones solo si está habilitado
LOGS_DIR = Path(__file__).parent / "logs"
if ENABLE_LOGGING:
    LOGS_DIR.mkdir(exist_ok=True)
    conversation_logger = logging.getLogger("conversations")
    conversation_logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOGS_DIR / "conversations.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    conversation_logger.addHandler(handler)
else:
    conversation_logger = None


def log_conversation(
    client_ip: str,
    agent_id: str,
    agent_name: str,
    question: str,
    response: str,
    session_id: str = ""
):
    """Registra una conversación en el log (si está habilitado)"""
    if not ENABLE_LOGGING or conversation_logger is None:
        return
    entry = {
        "timestamp": datetime.now().isoformat(),
        "client_ip": client_ip,
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "question": question,
        "response": response[:500] + "..." if len(response) > 500 else response
    }
    conversation_logger.info(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")

# Configuración
SCRIPT_DIR = Path(__file__).parent
AGENTS_PATH = SCRIPT_DIR.parent / "agents"  # tommi/agents/

# Inicializar runner
runner = AgentRunner(agents_base_path=str(AGENTS_PATH))

# FastAPI app
app = FastAPI(
    title="Tommi Web Interface",
    description="Interfaz web para agentes Tommi",
    version="1.0.0"
)

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory=SCRIPT_DIR / "static"), name="static")
app.mount("/img", StaticFiles(directory=SCRIPT_DIR / "img"), name="img")


class ChatRequest(BaseModel):
    """Request para enviar un mensaje a un agente"""
    agent_id: str
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Respuesta de un agente"""
    response: str
    session_id: str


class AgentResponse(BaseModel):
    """Información de un agente"""
    id: str
    name: str
    agent_type: str
    description: str
    welcome_message: str
    example_queries: list[str]
    rag_approach: str = "context_preserving"
    show_history: bool = True
    show_description: bool = False
    transparency_level: str = "black_box"
    prompt_level: str = "stringent"


@app.get("/")
async def root():
    """Sirve la página principal"""
    return FileResponse(SCRIPT_DIR / "static" / "index.html")


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    return FileResponse(SCRIPT_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/config")
async def get_config():
    """Devuelve la configuración pública del servidor"""
    return {"logging_enabled": ENABLE_LOGGING}


async def get_ollama_model_info(base_url: str, model_name: str) -> dict:
    """Consulta la API de Ollama para obtener información detallada del modelo."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{base_url}/api/show", json={"name": model_name})
            if response.status_code == 200:
                data = response.json()
                # Extraer información relevante
                details = data.get("details", {})
                model_info = {
                    "family": details.get("family", ""),
                    "parameter_size": details.get("parameter_size", ""),
                    "quantization_level": details.get("quantization_level", ""),
                }
                # Construir nombre descriptivo
                parts = [model_name]
                if model_info["parameter_size"]:
                    parts.append(model_info["parameter_size"])
                if model_info["quantization_level"]:
                    parts.append(model_info["quantization_level"])
                return {
                    "full_name": " ".join(parts) if len(parts) > 1 else model_name,
                    "details": model_info
                }
    except Exception:
        pass
    return {"full_name": model_name, "details": {}}


async def check_ollama_health(base_url: str, model: str) -> dict:
    """Check if Ollama is running and if the model is available."""
    import httpx

    result = {
        "ollama_running": False,
        "model_available": False,
        "error": None,
        "error_code": None,
        "error_type": None,
        "instructions": None
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Check if Ollama is running
            try:
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    result["ollama_running"] = True
                    models_data = response.json()
                    available_models = [m.get("name", "").split(":")[0] for m in models_data.get("models", [])]

                    # 2. Check if model is available
                    model_base = model.split(":")[0]
                    if model_base in available_models or model in [m.get("name", "") for m in models_data.get("models", [])]:
                        result["model_available"] = True
                    else:
                        err = format_error(LLM_MODEL_NOT_FOUND, model=model)
                        result.update(err)
                        result["available_models"] = available_models[:5]
                else:
                    result.update(format_error(LLM_OLLAMA_ERROR))
            except httpx.ConnectError:
                result.update(format_error(LLM_OLLAMA_NOT_RUNNING))
            except httpx.TimeoutException:
                result.update(format_error(LLM_OLLAMA_TIMEOUT))

    except Exception as e:
        result.update(format_error(LLM_UNKNOWN_ERROR, details=str(e)))

    return result


async def check_mistral_health(api_key: str) -> dict:
    """Check if the Mistral API key is valid."""
    import httpx

    result = {
        "api_key_configured": False,
        "api_key_valid": False,
        "error": None,
        "error_code": None,
        "error_type": None,
        "instructions": None
    }

    if not api_key:
        result.update(format_error(LLM_NO_API_KEY))
        return result

    result["api_key_configured"] = True

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code == 200:
                result["api_key_valid"] = True
            elif response.status_code == 401:
                result.update(format_error(LLM_INVALID_API_KEY))
            else:
                result.update(format_error(LLM_MISTRAL_ERROR, status_code=response.status_code))
    except Exception as e:
        result.update(format_error(LLM_CONNECTION_ERROR, details=str(e)))

    return result


async def check_vllm_health(base_url: str, model: str) -> dict:
    """Check if vLLM is running and if the model is available."""
    import httpx

    result = {
        "vllm_running": False,
        "model_available": False,
        "error": None,
        "error_code": None,
        "error_type": None,
        "instructions": None
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Check if vLLM is running (endpoint /v1/models)
            try:
                response = await client.get(f"{base_url}/models")
                if response.status_code == 200:
                    result["vllm_running"] = True
                    models_data = response.json()
                    available_models = [m.get("id", "") for m in models_data.get("data", [])]

                    # 2. Check if model is available
                    if model in available_models:
                        result["model_available"] = True
                    else:
                        err = format_error(LLM_VLLM_MODEL_NOT_FOUND, model=model)
                        result.update(err)
                        result["available_models"] = available_models[:5]
                else:
                    result.update(format_error(LLM_VLLM_ERROR, status_code=response.status_code))
            except httpx.ConnectError:
                result.update(format_error(LLM_VLLM_NOT_RUNNING))
            except httpx.TimeoutException:
                result.update(format_error(LLM_VLLM_NOT_RUNNING))

    except Exception as e:
        result.update(format_error(LLM_UNKNOWN_ERROR, details=str(e)))

    return result


@app.get("/api/llm-status")
async def get_llm_status(agent_id: Optional[str] = Query(None, description="ID del agente (opcional)")):
    """Devuelve información sobre el proveedor de LLM del agente especificado o el global"""
    from dotenv import dotenv_values

    # Determinar configuración a usar
    provider = None
    model = None
    base_url = None
    api_key = None

    # Si se especifica un agente, verificar si tiene su propia config LLM
    # Solo usa la config del agente si define LLM_PROVIDER explícitamente
    if agent_id:
        agent_info = runner.get_agent(agent_id)
        if agent_info:
            agent_env_path = Path(agent_info.path) / ".env"
            if agent_env_path.exists():
                agent_env = dotenv_values(agent_env_path)

                # Solo usar config del agente si define LLM_PROVIDER
                if agent_env.get("LLM_PROVIDER"):
                    provider = agent_env.get("LLM_PROVIDER").lower()

                    if provider == "ollama":
                        model = agent_env.get("OLLAMA_MODEL", "mistral")
                        base_url = agent_env.get("OLLAMA_BASE_URL", "http://localhost:11434")
                    elif provider == "vllm":
                        model = agent_env.get("VLLM_MODEL")
                        base_url = agent_env.get("VLLM_BASE_URL", "http://localhost:8000/v1")
                    else:
                        model = agent_env.get("MISTRAL_MODEL", "mistral-small-latest")
                        api_key = agent_env.get("MISTRAL_API_KEY")

    # Configuración global (leer directamente de web/.env, no de os.environ
    # porque agent_runner puede haberlo sobrescrito al cargar otro agente)
    if not provider:
        web_env = dotenv_values(Path(__file__).parent / ".env")
        provider = web_env.get("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            model = web_env.get("OLLAMA_MODEL", "mistral")
            base_url = web_env.get("OLLAMA_BASE_URL", "http://localhost:11434")
        elif provider == "vllm":
            model = web_env.get("VLLM_MODEL")
            base_url = web_env.get("VLLM_BASE_URL", "http://localhost:8000/v1")
        else:
            model = web_env.get("MISTRAL_MODEL", "mistral-small-latest")
            api_key = web_env.get("MISTRAL_API_KEY")

    # Build main LLM response
    response = {}

    if provider == "ollama":
        health = await check_ollama_health(base_url, model)

        if health["error"]:
            response = {
                "provider": "ollama",
                "is_local": True,
                "model": model,
                "base_url": base_url,
                "status": "error",
                "error_code": health["error_code"],
                "error_type": health["error_type"],
                "error": health["error"],
                "instructions": health["instructions"],
                "available_models": health.get("available_models", [])
            }
        else:
            model_info = await get_ollama_model_info(base_url, model)
            # Fetch all available Ollama models for cycling
            ollama_models = []
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as hclient:
                    resp = await hclient.get(f"{base_url}/api/tags")
                    if resp.status_code == 200:
                        for m in resp.json().get("models", []):
                            name = m.get("name", "")
                            size_bytes = m.get("size", 0)
                            size_gb = round(size_bytes / (1024**3), 1)
                            ollama_models.append({"name": name, "size_gb": size_gb})
            except Exception:
                pass
            # Build sizes dict with both full name and base name (without tag)
            model_sizes = {}
            for m in ollama_models:
                model_sizes[m["name"]] = m["size_gb"]
                base_name = m["name"].split(":")[0]
                if base_name not in model_sizes:
                    model_sizes[base_name] = m["size_gb"]
            response = {
                "provider": "ollama",
                "is_local": True,
                "model": model,
                "display_name": f"Ollama: {model_info['full_name']}",
                "base_url": base_url,
                "model_details": model_info["details"],
                "status": "ok",
                "available_models": [m["name"] for m in ollama_models],
                "model_sizes": model_sizes,
            }
    elif provider == "vllm":
        health = await check_vllm_health(base_url, model)

        if health["error"]:
            response = {
                "provider": "vllm",
                "is_local": True,
                "model": model,
                "base_url": base_url,
                "status": "error",
                "error_code": health["error_code"],
                "error_type": health["error_type"],
                "error": health["error"],
                "instructions": health["instructions"],
                "available_models": health.get("available_models", [])
            }
        else:
            response = {
                "provider": "vllm",
                "is_local": True,
                "model": model,
                "display_name": f"vLLM: {model}",
                "base_url": base_url,
                "status": "ok"
            }
    else:
        health = await check_mistral_health(api_key)

        if health["error"]:
            response = {
                "provider": "mistral",
                "is_local": False,
                "model": model,
                "status": "error",
                "error_code": health["error_code"],
                "error_type": health["error_type"],
                "error": health["error"],
                "instructions": health["instructions"]
            }
        else:
            response = {
                "provider": "mistral",
                "is_local": False,
                "model": model,
                "display_name": f"Mistral: {model}",
                "base_url": None,
                "status": "ok"
            }

    # Add available models list (for model switching UI)
    from dotenv import dotenv_values as _dv
    _web_env = _dv(Path(__file__).parent / ".env")
    available_raw = _web_env.get("AVAILABLE_MODELS", "")
    if available_raw:
        response["available_models"] = [m.strip() for m in available_raw.split(",") if m.strip()]

    return response


@app.get("/api/history")
async def get_history(
    agent_id: str = Query(..., description="ID del agente"),
    session_id: Optional[str] = Query(None, description="ID de sesión")
):
    """Obtiene el historial de consultas de un agente para una sesión"""
    history = runner.get_agent_history(agent_id, session_id)
    return {"history": history}


@app.get("/api/agents", response_model=list[AgentResponse])
async def list_agents():
    """Lista todos los agentes disponibles"""
    agents = runner.discover_agents()
    return [
        AgentResponse(
            id=a.id,
            name=a.name,
            agent_type=a.agent_type,
            description=a.description,
            welcome_message=a.welcome_message,
            example_queries=a.example_queries,
            rag_approach=a.rag_approach,
            show_history=a.show_history,
            show_description=a.show_description,
            transparency_level=a.transparency_level,
            prompt_level=a.prompt_level
        )
        for a in agents
    ]


@app.post("/api/agents/{agent_id}/init")
async def init_agent(agent_id: str):
    """
    Initialize an agent, forcing ChromaDB indexing for RAG agents.
    Call this when selecting a RAG agent to ensure the database is ready.
    """
    result = runner.init_agent(agent_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result


@app.get("/api/agents/{agent_id}/init-stream")
async def init_agent_stream(agent_id: str):
    """
    Initialize a RAG agent with SSE progress reporting.
    Streams progress events during document indexing.
    """
    import asyncio
    import threading

    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        err = format_error(AGENT_NOT_FOUND, agent_id=agent_id)
        raise HTTPException(status_code=404, detail=f"Error {err['error_code']}: {err['error']}")

    async def event_generator():
        loop = asyncio.get_event_loop()
        aq = asyncio.Queue()

        def progress_callback(current, total, filename):
            loop.call_soon_threadsafe(aq.put_nowait, {
                "event": "progress",
                "current": current,
                "total": total,
                "filename": filename,
            })

        def run_init():
            try:
                result = runner.init_agent_with_callback(agent_id, progress_callback)
                loop.call_soon_threadsafe(aq.put_nowait, {"event": "done", "result": result})
            except Exception as e:
                loop.call_soon_threadsafe(aq.put_nowait, {
                    "event": "done",
                    "result": {"success": False, "error": str(e)},
                })

        thread = threading.Thread(target=run_init, daemon=True)
        thread.start()

        while True:
            event = await aq.get()
            if event["event"] == "progress":
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"
            elif event["event"] == "done":
                yield f"event: done\ndata: {json.dumps(event['result'])}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/agents/{agent_id}/reindex")
async def reindex_agent(agent_id: str):
    """
    Force reindex of a RAG agent's documents.
    Use this after adding, removing, or modifying documents in data/docs/.
    """
    result = runner.reindex_agent(agent_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result


@app.get("/api/agents/{agent_id}/token-usage")
async def get_token_usage(agent_id: str):
    """
    Get token usage statistics for an agent.
    Returns prompt tokens, completion tokens, and total tokens for the session.
    """
    result = runner.get_agent_token_usage(agent_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not loaded or doesn't support token tracking")
    return result


@app.post("/api/agents/{agent_id}/reset-token-usage")
async def reset_token_usage(agent_id: str):
    """
    Reset token usage counters for an agent.
    """
    result = runner.reset_agent_token_usage(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not loaded or doesn't support token tracking")
    return {"success": True, "message": "Token usage counters reset"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Envía un mensaje a un agente y obtiene respuesta completa"""
    try:
        result = await runner.run_query(
            agent_id=request.agent_id,
            message=request.message,
            session_id=request.session_id  # None en primera llamada
        )
        return ChatResponse(response=result.response, session_id=result.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/stream")
async def chat_stream(
    request: Request,
    agent_id: str = Query(..., description="ID del agente"),
    message: str = Query(..., description="Mensaje a enviar"),
    session_id: Optional[str] = Query(None, description="ID de sesión (opcional, se crea automáticamente)"),
    model: Optional[str] = Query(None, description="LLM model override (client preference)"),
    transparency: Optional[str] = Query(None, description="Transparency level override (client preference)"),
    prompt_level: Optional[str] = Query(None, description="Prompt level override (client preference)")
):
    """Envía un mensaje y hace streaming de la respuesta via SSE"""
    agent = runner.get_agent(agent_id)
    if not agent:
        err = format_error(AGENT_NOT_FOUND, agent_id=agent_id)
        raise HTTPException(status_code=404, detail=f"Error {err['error_code']}: {err['error']}")

    client_ip = request.client.host if request.client else "unknown"

    async def event_generator():
        new_session_id = None
        full_response = ""

        try:
            async for event_type, content, returned_session_id in runner.run_query_stream(
                agent_id=agent_id,
                message=message,
                session_id=session_id,  # None en primera llamada
                model_override=model,
                transparency_override=transparency,
                prompt_level_override=prompt_level
            ):
                # Enviar session_id cuando lo recibimos (primera iteración)
                if returned_session_id and not new_session_id:
                    new_session_id = returned_session_id
                    yield f"event: session\ndata: {new_session_id}\n\n"

                if event_type == "status":
                    # Enviar evento de estado
                    yield f"event: status\ndata: {content}\n\n"
                elif event_type == "badge":
                    # Enviar badge de fiabilidad como evento separado (no se acumula en el texto)
                    escaped = content.replace("\n", "\\n")
                    yield f"event: badge\ndata: {escaped}\n\n"
                elif event_type == "claim_highlights":
                    # Send claim classification data for client-side highlighting
                    yield f"event: claim_highlights\ndata: {content}\n\n"
                elif event_type == "replace":
                    # Replace full response (e.g. after stripping map links)
                    full_response = content
                    escaped = content.replace("\n", "\\n")
                    yield f"event: replace\ndata: {escaped}\n\n"
                else:
                    # Enviar contenido
                    full_response += content
                    escaped = content.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"

            # Registrar la conversación en el log
            log_conversation(
                client_ip=client_ip,
                agent_id=agent_id,
                agent_name=agent.name,
                question=message,
                response=full_response,
                session_id=new_session_id or session_id or ""
            )

            yield "event: done\ndata: complete\n\n"
        except Exception as e:
            err = format_error(SERVER_STREAMING_ERROR, details=str(e))
            import json
            yield f"event: error\ndata: {json.dumps(err)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Topic Map Endpoint (for agents with search_papers_by_topic)
# ============================================================================

@app.get("/api/agents/{agent_id}/publications-search")
async def agent_publications_search(agent_id: str, year: Optional[int] = Query(None)):
    """Return all papers grouped by university as JSON data."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_all_papers_by_university"):
        raise HTTPException(status_code=400, detail="Agent does not support publications search")
    results = agent_instance.get_all_papers_by_university(year=year)
    title = f"Publications ({year})" if year else "All Publications"
    return {"topic": title, "universities": results}


@app.get("/api/agents/{agent_id}/publications-map")
async def agent_publications_map(agent_id: str, year: Optional[int] = Query(None)):
    """Returns an interactive Leaflet map showing publications per university, optionally filtered by year."""
    from fastapi.responses import HTMLResponse
    import json as json_module

    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_all_papers_by_university"):
        raise HTTPException(status_code=400, detail="Agent does not support publications search")

    results = agent_instance.get_all_papers_by_university(year=year)
    results_json = json_module.dumps(results)
    title = f"Publications ({year})" if year else "All Publications"

    if hasattr(agent_instance, "build_topic_map_html"):
        html = agent_instance.build_topic_map_html(results_json, title)
        return HTMLResponse(content=html)

    return HTMLResponse(content=f"<html><body><h1>All Publications</h1><pre>{results_json}</pre></body></html>")


@app.get("/api/agents/{agent_id}/collaboration-search")
async def agent_collaboration_search(agent_id: str, topic: str = Query(None),
                                     year: int = Query(None)):
    """Return collaboration data (universities + connections) as JSON."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_collaboration_map_data"):
        raise HTTPException(status_code=400, detail="Agent does not support collaboration search")
    return agent_instance.get_collaboration_map_data(topic=topic, year=year)


@app.get("/api/agents/{agent_id}/topic-search")
async def agent_topic_search(agent_id: str, topic: str = Query(...)):
    """Search papers by topic across universities. Returns JSON data."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "search_papers_by_topic"):
        raise HTTPException(status_code=400, detail="Agent does not support topic search")
    results = agent_instance.search_papers_by_topic(topic)
    return {"topic": topic, "universities": results}


@app.get("/api/agents/{agent_id}/topic-map")
async def agent_topic_map(agent_id: str, topic: str = Query(...)):
    """Returns an interactive Leaflet map for a topic across UNINOVIS universities."""
    from fastapi.responses import HTMLResponse
    import json as json_module

    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "search_papers_by_topic"):
        raise HTTPException(status_code=400, detail="Agent does not support topic search")

    results = agent_instance.search_papers_by_topic(topic)
    results_json = json_module.dumps(results)
    topic_escaped = topic.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

    # Use the agent's build_topic_map_html if available
    if hasattr(agent_instance, "build_topic_map_html"):
        html = agent_instance.build_topic_map_html(results_json, topic_escaped)
        return HTMLResponse(content=html)

    # Fallback: simple response
    return HTMLResponse(content=f"<html><body><h1>Topic map for {topic_escaped}</h1><pre>{results_json}</pre></body></html>")


# ============================================================================
# PDF Document Endpoint
# ============================================================================

@app.get("/api/agents/{agent_id}/pdf-list")
async def agent_pdf_list(agent_id: str):
    """List available PDFs for an agent."""
    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")
    docs_dir = Path(agent_info.path) / "data" / "docs"
    if not docs_dir.exists():
        return {"pdfs": []}
    pdfs = [f.stem for f in docs_dir.glob("*.pdf")]
    return {"pdfs": pdfs}


@app.get("/api/agents/{agent_id}/pdf/{filename}")
async def agent_pdf(agent_id: str, filename: str):
    """Serve a PDF from an agent's data/docs/ directory."""
    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Security: only allow .pdf files, no path traversal
    if not filename.endswith(".pdf") or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    pdf_path = Path(agent_info.path) / "data" / "docs" / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


# ============================================================================
# Agent Creation Endpoints
# ============================================================================

@app.get("/create-agent")
async def create_agent_page():
    """Serve the create agent page"""
    return FileResponse(SCRIPT_DIR / "static" / "create_agent.html")


@app.get("/api/prompt-templates")
async def get_prompt_templates(agent_type: str = Query(...)):
    """List available prompt templates for an agent type"""
    # Import from crear_agente
    apps_dir = SCRIPT_DIR.parent / "apps"
    sys.path.insert(0, str(apps_dir))

    try:
        from crear_agente import list_prompt_templates
        templates = list_prompt_templates(agent_type)
        return [{"name": name, "path": path} for name, path in templates]
    except Exception as e:
        return []


@app.get("/api/prompt-template")
async def get_prompt_template(path: str = Query(...)):
    """Get content of a prompt template"""
    try:
        # Security: ensure path is within prompts directory
        prompts_dir = SCRIPT_DIR.parent / "prompts"
        template_path = Path(path).resolve()

        if not str(template_path).startswith(str(prompts_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import Form, UploadFile, File
from typing import List, Optional

@app.post("/api/create-agent")
async def create_agent(
    agent_type: str = Form(...),
    agent_id: str = Form(...),
    agent_name: str = Form(...),
    description: str = Form(""),
    welcome_message: str = Form(""),
    examples: str = Form("[]"),  # JSON array
    system_prompt: str = Form(...),
    llm_provider: str = Form("default"),
    mistral_model: str = Form("mistral-large-latest"),
    mistral_api_key: str = Form(""),
    ollama_url: str = Form("http://localhost:11434"),
    ollama_model: str = Form(""),
    context_preserving: bool = Form(True),  # RAG chunking approach
    reliability_green_max_llm: int = Form(20),
    reliability_red_min_llm: int = Form(50),
    database_schema: str = Form(""),
    data_file: Optional[UploadFile] = File(None),
    schema_file: Optional[UploadFile] = File(None),
    rag_documents: List[UploadFile] = File(None),
    rag_metadata_documents: List[UploadFile] = File(None),
    metadata_file: Optional[UploadFile] = File(None),
    database_file: Optional[UploadFile] = File(None),
):
    """Create a new agent"""
    import json as json_module
    import shutil

    try:
        # Parse examples
        example_list = json_module.loads(examples) if examples else []

        # Validate agent_id
        if not agent_id or " " in agent_id or not agent_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(status_code=400, detail="Invalid agent ID. Use only lowercase letters, numbers, hyphens or underscores.")

        # Check if agent already exists
        output_dir = AGENTS_PATH / agent_id
        if output_dir.exists():
            raise HTTPException(status_code=400, detail=f"Agent '{agent_id}' already exists")

        # Import crear_agente functions
        apps_dir = SCRIPT_DIR.parent / "apps"
        sys.path.insert(0, str(apps_dir))
        from crear_agente import (
            create_agent_structure,
            get_agents_dir
        )

        # Prepare configuration
        config = {
            "agent_type": agent_type,
            "agent_id": agent_id,
            "output_dir": str(output_dir),
            "agent_name": agent_name,
            "description": description or f"{agent_name} Assistant",
            "welcome": welcome_message or f"Hello! I'm {agent_name}. How can I help you?",
            "examples": example_list,
            "system_prompt": system_prompt,
            "llm_provider": llm_provider,
            "model": mistral_model if llm_provider == "mistral" else ollama_model,
            "api_key": mistral_api_key if llm_provider == "mistral" else "",
            "ollama_url": ollama_url if llm_provider == "ollama" else "",
            "ollama_model": ollama_model if llm_provider == "ollama" else "",
            "rag_approach": "context_preserving" if context_preserving else "basic",
            "reliability_green_max_llm": reliability_green_max_llm,
            "reliability_red_min_llm": reliability_red_min_llm,
        }

        # Create agent structure
        create_agent_structure(config)

        # Create data directory
        data_dir = output_dir / "data"
        data_dir.mkdir(exist_ok=True)

        # Handle data based on agent type
        if agent_type == "oneshot" and data_file and data_file.filename:
            # Save uploaded data.md file
            content = await data_file.read()
            with open(data_dir / "data.md", "wb") as f:
                f.write(content)

        elif agent_type == "rag" and rag_documents:
            # Create docs subfolder for RAG
            docs_dir = data_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            # Save uploaded documents (from folder selection)
            for doc in rag_documents:
                if doc.filename:
                    # Handle folder structure - get just the filename
                    filename = Path(doc.filename).name
                    # Skip hidden files and non-document files
                    if filename.startswith('.'):
                        continue
                    ext = Path(filename).suffix.lower()
                    if ext in ['.pdf', '.txt', '.md', '.docx', '.doc']:
                        doc_path = docs_dir / filename
                        content = await doc.read()
                        with open(doc_path, "wb") as f:
                            f.write(content)

        elif agent_type == "rag_metadata":
            # Create docs subfolder for RAG+Metadata
            docs_dir = data_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            # Save uploaded documents (from folder selection)
            if rag_metadata_documents:
                for doc in rag_metadata_documents:
                    if doc.filename:
                        filename = Path(doc.filename).name
                        if filename.startswith('.'):
                            continue
                        ext = Path(filename).suffix.lower()
                        if ext in ['.pdf', '.txt', '.md', '.docx', '.doc']:
                            doc_path = docs_dir / filename
                            content = await doc.read()
                            with open(doc_path, "wb") as f:
                                f.write(content)
            # Save metadata file if provided
            if metadata_file and metadata_file.filename:
                content = await metadata_file.read()
                with open(data_dir / "metadata.json", "wb") as f:
                    f.write(content)

        elif agent_type == "consultabd_sql":
            # Handle database schema - from file or textarea
            if schema_file and schema_file.filename:
                content = await schema_file.read()
                with open(data_dir / "database_schema.md", "wb") as f:
                    f.write(content)
            elif database_schema:
                with open(data_dir / "database_schema.md", "w", encoding="utf-8") as f:
                    f.write(database_schema)

            # Save database file
            if database_file and database_file.filename:
                db_path = data_dir / "database.db"
                content = await database_file.read()
                with open(db_path, "wb") as f:
                    f.write(content)

        # Reload agents
        runner.discover_agents()

        return {
            "success": True,
            "agent_id": agent_id,
            "path": str(output_dir),
            "message": f"Agent '{agent_name}' created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import sys
    import socket

    print(f"Agents path: {AGENTS_PATH}")

    # Descubrir agentes al inicio
    agents = runner.discover_agents()
    print(f"Found {len(agents)} agents:")
    for agent in agents:
        print(f"  - {agent.name} ({agent.id})")

    # Verificar si el puerto está disponible antes de iniciar uvicorn
    host, port = "0.0.0.0", 8000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"\nERROR:    [Error 504] error while attempting to bind on address ('{host}', {port}): address already in use", file=sys.stderr)
            print(f"\nYou can fix this by running: ./liberar-puerto.sh {port}", file=sys.stderr)
            print("\nSee howto.html (section 7.5. Server errors) for more information.", file=sys.stderr)
            sys.exit(1)
        else:
            raise

    uvicorn.run(app, host=host, port=port)
