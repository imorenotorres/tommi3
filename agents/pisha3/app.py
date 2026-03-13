"""
Pisha2 - Servidor FastAPI (Text-to-SQL)
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
    "id": "pisha3",
    "name": "Agoria DB assistant+",
    "type": "text2sql",
    "description": "Database assistant for university agreements",
    "welcome_message": "Hi! I'm the Agoria DB assistant. How can I help you?",
    "example_queries": ["What agreements are there with The Hague University of Applied Sciences?",
                        "Which Dutch universities have agreements?",
                        "Are there any agreements with 'English B1' as language requirement?",
                        "Do we have agreements with the Netherlands?"
                        ]
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
    stream: Optional[bool] = False


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


@app.get("/schema")
async def schema():
    """Devuelve el esquema de la base de datos."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {"schema": agent.get_schema()}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.
    Convierte la pregunta a SQL, ejecuta y formatea resultados.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                if event_type == "content":
                    yield content

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
