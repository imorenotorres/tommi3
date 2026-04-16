"""
Liana's Assistant — ExcelAnalyst FastAPI server
"""

# Activate venv automatically if not active
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import os
import json
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent import Agent

# Load config
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_config_path, "r", encoding="utf-8") as _f:
    AGENT_CONFIG = json.load(_f)
AGENT_CONFIG.setdefault("id", AGENT_CONFIG.get("agent_id", "excel_analyst"))

agent: Agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = Agent()
    # Auto-load any file in data/ directory
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    for f in os.listdir(data_dir):
        if f.endswith(('.csv', '.xlsx', '.xls')):
            agent.load_file(os.path.join(data_dir, f))
            break
    yield


app = FastAPI(
    title=AGENT_CONFIG.get("agent_name", "Liana's Assistant"),
    description=AGENT_CONFIG.get("description", ""),
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
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    return AGENT_CONFIG


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    """Upload a CSV or Excel file for analysis."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only .csv, .xlsx, .xls files are supported")

    content = await file.read()
    sid = session_id or "default"
    result = agent.load_file_bytes(content, file.filename, sid)
    return {"message": result, "filename": file.filename}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if request.stream:
        async def generate():
            async for event_type, content in agent.chat_stream(request.message, request.history):
                if event_type == "content":
                    yield content
        return StreamingResponse(generate(), media_type="text/plain")

    response = agent.chat(request.message, request.history)
    return ChatResponse(response=response)


@app.get("/schema")
async def schema(session_id: Optional[str] = None):
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {"schema": agent.get_schema(session_id or "default")}


@app.get("/examples")
async def examples():
    return {"examples": AGENT_CONFIG.get("example_queries", [])}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
