"""
Algoria Map - Interactive map explorer for UMA mobility agreements.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import os
import json as _json
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from agent import Agent

_config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_config_path, "r", encoding="utf-8") as _f:
    AGENT_CONFIG = _json.load(_f)
AGENT_CONFIG.setdefault("id", AGENT_CONFIG.get("agent_id", "algoria_map"))

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = Agent()
    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

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


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    return AGENT_CONFIG


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/examples")
async def examples():
    return {"examples": AGENT_CONFIG.get("example_queries", [])}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
