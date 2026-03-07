"""
Novis B - Servidor FastAPI
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import os
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Configuración del agente
AGENT_CONFIG = {
    "id": "conf26_nube",
    "type": "oneshot",
    "name": "Novis en la nube",
    "description": "Asistente de la conferencia de UNINOVIS (cloud)",
    "welcome_message": "¡Hola! Soy Novis en la nube. ¿En qué puedo ayudarte?",
    "example_queries": ["¿Qué sesiones hay el día 26?", "¿Quién interviene en la sesión 6b?"]
}

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el agente al arrancar."""
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS para permitir llamadas desde frontend
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
    stream: Optional[bool] = True


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    """Información del agente."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.

    Body:
        message: Mensaje del usuario
        history: Historial de conversación (opcional)
        stream: Si es True, devuelve streaming (opcional)
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {"examples": AGENT_CONFIG["example_queries"]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
