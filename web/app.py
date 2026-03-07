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
    verify_grounding: bool = False


@app.get("/")
async def root():
    """Sirve la página principal"""
    return FileResponse(SCRIPT_DIR / "static" / "index.html")


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
            response = {
                "provider": "ollama",
                "is_local": True,
                "model": model,
                "display_name": f"Ollama: {model_info['full_name']}",
                "base_url": base_url,
                "model_details": model_info["details"],
                "status": "ok"
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
            verify_grounding=a.verify_grounding
        )
        for a in agents
    ]


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
    session_id: Optional[str] = Query(None, description="ID de sesión (opcional, se crea automáticamente)")
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
                session_id=session_id  # None en primera llamada
            ):
                # Enviar session_id cuando lo recibimos (primera iteración)
                if returned_session_id and not new_session_id:
                    new_session_id = returned_session_id
                    yield f"event: session\ndata: {new_session_id}\n\n"

                if event_type == "status":
                    # Enviar evento de estado
                    yield f"event: status\ndata: {content}\n\n"
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
