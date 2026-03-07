"""
Tommi Debate Web Interface - FastAPI server para debates entre agentes
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import json
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

# Asegurar que el directorio padre este en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_runner import AgentRunner

# Importar el orquestador de debate
from debate_v2 import DebateOrchestratorV2, DebateConfig

# Cargar variables de entorno
load_dotenv()

# Configuracion
SCRIPT_DIR = Path(__file__).parent
AGENTS_PATH = SCRIPT_DIR.parent / "agents"  # tommi/agents/

# Inicializar runner
runner = AgentRunner(agents_base_path=str(AGENTS_PATH))

# FastAPI app
app = FastAPI(
    title="Tommi Debate Interface",
    description="Interfaz web para debates entre agentes TOMMI",
    version="2.0.0"
)


# Middleware anti-cache para desarrollo
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static") or request.url.path in ["/", "/chat"]:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheMiddleware)

# Servir archivos estaticos
app.mount("/static", StaticFiles(directory=SCRIPT_DIR / "static"), name="static")


class AgentResponse(BaseModel):
    """Informacion de un agente"""
    id: str
    name: str
    description: str
    welcome_message: str
    example_queries: list[str]


@app.get("/")
async def root():
    """Sirve la pagina de debate"""
    return FileResponse(SCRIPT_DIR / "static" / "index_debate.html")


@app.get("/chat")
async def chat_page():
    """Sirve la pagina de chat original"""
    return FileResponse(SCRIPT_DIR / "static" / "index.html")


@app.get("/api/agents", response_model=list[AgentResponse])
async def list_agents():
    """Lista todos los agentes disponibles"""
    agents = runner.discover_agents()
    return [
        AgentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            welcome_message=a.welcome_message,
            example_queries=a.example_queries
        )
        for a in agents
    ]


@app.get("/api/debate/stream")
async def debate_stream(
    agent_a_id: str = Query(..., description="ID del primer agente"),
    agent_b_id: str = Query(..., description="ID del segundo agente"),
    moderator_id: str = Query(..., description="ID del moderador"),
    topic: str = Query(..., description="Tema del debate"),
    rounds: int = Query(3, description="Numero de rondas"),
    role_a: str = Query("a favor", description="Rol del primer agente"),
    role_b: str = Query("en contra", description="Rol del segundo agente")
):
    """
    Ejecuta un debate con streaming via SSE.
    Retorna eventos JSON con el progreso del debate.
    """
    # Verificar que los agentes existen
    agent_a = runner.get_agent(agent_a_id)
    agent_b = runner.get_agent(agent_b_id)
    moderator = runner.get_agent(moderator_id)

    if not agent_a:
        raise HTTPException(status_code=404, detail=f"Agente no encontrado: {agent_a_id}")
    if not agent_b:
        raise HTTPException(status_code=404, detail=f"Agente no encontrado: {agent_b_id}")
    if not moderator:
        raise HTTPException(status_code=404, detail=f"Moderador no encontrado: {moderator_id}")

    config = DebateConfig(
        topic=topic,
        rounds=rounds,
        agent_a_role=role_a,
        agent_b_role=role_b
    )

    orchestrator = DebateOrchestratorV2(runner)

    async def event_generator():
        try:
            async for event in orchestrator.run_debate_stream(
                agent_a_id=agent_a_id,
                agent_b_id=agent_b_id,
                moderator_id=moderator_id,
                config=config
            ):
                # Convertir evento a JSON
                event_json = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_json}\n\n"

            yield "event: done\ndata: complete\n\n"

        except Exception as e:
            error_json = json.dumps({"type": "error", "message": str(e)})
            yield f"event: error\ndata: {error_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/config")
async def get_config():
    """Devuelve la configuracion publica del servidor"""
    return {"logging_enabled": False, "mode": "debate"}


# Incluir tambien el endpoint de chat para compatibilidad
@app.get("/api/chat/stream")
async def chat_stream(
    agent_id: str = Query(..., description="ID del agente"),
    message: str = Query(..., description="Mensaje a enviar"),
    session_id: Optional[str] = Query(None, description="ID de sesion")
):
    """Envía un mensaje y hace streaming de la respuesta via SSE"""
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    async def event_generator():
        new_session_id = None
        full_response = ""

        try:
            async for event_type, content, returned_session_id in runner.run_query_stream(
                agent_id=agent_id,
                message=message,
                session_id=session_id
            ):
                if returned_session_id and not new_session_id:
                    new_session_id = returned_session_id
                    yield f"event: session\ndata: {new_session_id}\n\n"

                if event_type == "status":
                    yield f"event: status\ndata: {content}\n\n"
                else:
                    full_response += content
                    escaped = content.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"

            yield "event: done\ndata: complete\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

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

    print(f"Agents path: {AGENTS_PATH}")

    # Descubrir agentes al inicio
    agents = runner.discover_agents()
    print(f"Found {len(agents)} agents:")
    for agent in agents:
        print(f"  - {agent.name} ({agent.id})")

    print("\nStarting Debate Server...")
    print("  - Debate interface: http://localhost:8001/")
    print("  - Chat interface: http://localhost:8001/chat")

    uvicorn.run(app, host="0.0.0.0", port=8001)
