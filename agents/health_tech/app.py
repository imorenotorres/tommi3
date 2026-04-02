"""
Health and social technology - Servidor FastAPI (RAG+Metadata)
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
    verify: Optional[bool] = None


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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint principal de chat con RAG+Metadata."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history, verify=request.verify):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history, verify=request.verify)
    return ChatResponse(response=response)


@app.post("/reindex")
async def reindex():
    """Reindexa los documentos en data/docs/ con metadatos"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    count = agent.reindex()
    return {"status": "ok", "indexed_chunks": count}


@app.get("/metadata")
async def metadata():
    """Devuelve los metadatos de todos los documentos indexados."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return {"documents": agent.get_metadata_summary()}


@app.get("/examples")
async def examples():
    """Devuelve preguntas de ejemplo."""
    return {"examples": AGENT_CONFIG["example_queries"]}


def build_topic_map_html(results_json: str, topic_escaped: str) -> str:
    """Delegate to Agent's static method."""
    return Agent.build_topic_map_html(results_json, topic_escaped)


@app.get("/topic-search")
async def topic_search(topic: str = Query(..., description="Topic to search for")):
    """Search papers by topic across all UNINOVIS universities. Returns JSON data."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    results = agent.search_papers_by_topic(topic)
    return {"topic": topic, "universities": results}


@app.get("/publications-search")
async def publications_search():
    """Return all papers grouped by university as JSON data."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    results = agent.get_all_papers_by_university()
    return {"topic": "All Publications", "universities": results}


@app.get("/publications-map", response_class=HTMLResponse)
async def publications_map():
    """Returns an interactive Leaflet map showing total publications per university."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    results = agent.get_all_papers_by_university()
    results_json = json.dumps(results)

    html = build_topic_map_html(results_json, "All Publications")
    return HTMLResponse(content=html)


@app.get("/topic-map", response_class=HTMLResponse)
async def topic_map(topic: str = Query(..., description="Topic to search for")):
    """Returns an interactive Leaflet map showing which universities have explored a topic."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    results = agent.search_papers_by_topic(topic)
    results_json = json.dumps(results)
    topic_escaped = topic.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

    html = build_topic_map_html(results_json, topic_escaped)
    return HTMLResponse(content=html)


@app.get("/collaboration-search")
async def collaboration_search(topic: str = Query(None, description="Optional topic to filter collaborations"),
                               year: int = Query(None, description="Optional publication year to filter collaborations")):
    """Return collaboration data as JSON (universities + connections)."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    return agent.get_collaboration_map_data(topic=topic, year=year)


@app.get("/collaboration-map", response_class=HTMLResponse)
async def collaboration_map(topic: str = Query(None, description="Optional topic to filter collaborations"),
                            year: int = Query(None, description="Optional publication year to filter collaborations")):
    """Returns an interactive map showing collaboration lines between UNINOVIS universities."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    data = agent.get_collaboration_map_data(topic=topic, year=year)
    data_json = json.dumps(data)
    html = Agent.build_collaboration_map_html(data_json)
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
