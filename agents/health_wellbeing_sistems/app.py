"""
Health and Wellbeing Systems (Vectorless) - Servidor FastAPI (Metadata-only)
"""

import os
import re
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
    "name": _config.get("agent_name", "RAG+Metadata Agent (Vectorless)"),
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


# Allowed external domains: UNINOVIS alliance, partner universities, and academic publishers
_ALLOWED_DOMAINS = [
    # UNINOVIS and partners
    "uninovis.eu",
    "univ-paris13.fr", "sorbonne-paris-nord.fr",  # USPN
    "unicampania.it",  # UDCLV
    "uma.es",  # UMA
    "kfraunokolegija.lt", "go.kauko.lt",  # KK
    "unitir.edu.al",  # UT
    "thws.de",  # THWS
    "tuni.fi", "tamk.fi",  # TAMK
    "thuas.com", "dehaagsehogeschool.nl",  # THUAS
    # Academic publishers and indices
    "doi.org", "arxiv.org", "springer.com", "nature.com",
    "ieee.org", "acm.org", "sciencedirect.com", "wiley.com",
    "mdpi.com", "frontiersin.org", "plos.org", "elsevier.com",
    "researchgate.net", "scholar.google.com", "scopus.com",
    "openalex.org", "semanticscholar.org", "pubmed.ncbi.nlm.nih.gov",
    "taylorandfrancis.com", "tandfonline.com", "iospress.com",
    "cambridge.org", "oxford.org", "oxfordjournals.org",
    "sagepub.com", "degruyter.com", "jstor.org",
]


def _is_allowed_url(url: str) -> bool:
    """Check if a URL belongs to an allowed domain."""
    for domain in _ALLOWED_DOMAINS:
        if domain in url:
            return True
    return False


# Known system prompt fragments that should never appear in responses
_PROMPT_LEAK_PATTERNS = [
    r"NEVER invent, fabricate, or hallucinate.*?paper IDs",
    r"CRITICAL.*?UNINOVIS PARTNER RECOGNITION",
    r"GAP ANALYSIS.*?TOPICS NOT STUDIED",
    r"DECISION RULE for choosing figure type",
    r"INTERACTIVE MAP FEATURE.*?STRICT RULES",
    r"ABSOLUTE SECURITY RULES",
    r"RESPONSE FORMAT:",
    r"IMPORTANT RULES:\s*\n",
    r"Figure link formats:",
    r"TOPIC figure \(papers\):",
    r"PUBLICATIONS figure \(papers\):",
    r"COLLABORATION figure:",
    r"PROJECTS figure \(all projects\):",
    r"PROJECT-TOPIC figure",
    r"View interactive map for",
    r"View projects map for",
    r"prompt_level",
    r"transparency_level",
    r"NEVER invent, fabricate, or hallucinate",  # Exact rule text from completion attack
]


def filter_prompt_leaks(response: str) -> str:
    """Detect and redact system prompt fragments from the response."""
    for pattern in _PROMPT_LEAK_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE | re.DOTALL):
            # Replace the response with a safe refusal
            return (
                "I cannot share my system instructions. "
                "I am a research assistant for UNINOVIS AI & Responsibility "
                "(explainable AI, AI ethics, trustworthy AI, AI fairness, etc.). "
                "I can help you search papers, researchers, and projects."
            )
    return response


def sanitize_response(response: str, agent_id: str) -> str:
    """Remove external URLs and prompt leaks from responses."""
    def _replace_link(m):
        url = m.group(2)
        # Allow internal API links
        if url.startswith(f"/api/agents/{agent_id}/") or url.startswith("/api/agents/"):
            return m.group(0)
        # Allow whitelisted domains
        if _is_allowed_url(url):
            return m.group(0)
        return m.group(1)  # Keep link text, remove URL

    # Replace markdown links [text](url) with disallowed external URLs
    response = re.sub(r'\[([^\]]*)\]\((https?://[^\)]+)\)', _replace_link, response)
    # Remove any remaining bare external URLs that aren't allowed
    def _replace_bare(m):
        url = m.group(0)
        if _is_allowed_url(url):
            return url
        return '[external link removed]'
    response = re.sub(r'(?<!\()(https?://[^\s\)<>]+)', _replace_bare, response)
    return response


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint principal de chat con Metadata."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    if request.stream:
        async def generate():
            async for chunk in agent.chat_stream(request.message, request.history, verify=request.verify):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history, verify=request.verify)
    response = filter_prompt_leaks(response)
    response = sanitize_response(response, AGENT_CONFIG["id"])
    return ChatResponse(response=response)


@app.post("/reindex")
async def reindex():
    """No-op for vectorless agent."""
    return {"status": "ok", "indexed_chunks": 0, "note": "Vectorless agent — no documents to reindex"}


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


@app.get("/projects-search")
async def projects_search(year: int = Query(None, description="Optional year to filter projects")):
    """Return all projects grouped by university as JSON data."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")
    results = agent.get_all_projects_by_university(year=year)
    return {"topic": "All Projects", "universities": results}


@app.get("/projects-map", response_class=HTMLResponse)
async def projects_map(year: int = Query(None, description="Optional year to filter projects")):
    """Returns an interactive Leaflet map showing total projects per university."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    results = agent.get_all_projects_by_university(year=year)
    results_json = json.dumps(results)
    title = f"Projects ({year})" if year else "All Projects"
    html = Agent.build_project_map_html(results_json, title)
    return HTMLResponse(content=html)


@app.get("/project-topic-map", response_class=HTMLResponse)
async def project_topic_map(topic: str = Query(..., description="Topic to search for"),
                            year: int = Query(None, description="Optional year to filter projects")):
    """Returns an interactive Leaflet map showing which universities have projects on a topic."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agente no inicializado")

    results = agent.search_projects_by_topic(topic, year=year)
    results_json = json.dumps(results)
    topic_escaped = topic.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    title = f"{topic_escaped} ({year})" if year else topic_escaped
    html = Agent.build_project_map_html(results_json, title)
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
