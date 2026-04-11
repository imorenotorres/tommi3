#!/usr/bin/env python3
"""
UNINOVIS RAG Agent - FastAPI Server
API for querying UNINOVIS alliance research on AI & Responsibility.
"""

import os
from contextlib import asynccontextmanager
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from rag_agent import UNINOVISRagAgent

# Configuration
AGENT_CONFIG = {
    "id": "uninovis-rag",
    "name": "UNINOVIS AI & Responsibility Research Agent",
    "type": "rag",
    "description": "Research assistant for AI & Responsibility papers from UNINOVIS alliance universities",
    "welcome_message": "Hello! I can help you explore AI & Responsibility research from UNINOVIS alliance universities (UMA, USPN, UDCLV, KK, UT, THWS, TAMK, THUAS). Ask me about research topics, collaboration opportunities, or specific university contributions.",
    "example_queries": [
        "What research on explainable AI exists in the alliance?",
        "Which universities work on AI ethics?",
        "What are the main AI research topics at Universidad de Málaga?",
        "Find potential collaborations on responsible AI governance",
        "What papers discuss AI bias and fairness?",
        "Summary of AI research from THWS"
    ],
    "universities": [
        {"acronym": "USPN", "name": "University of Sorbonne Paris Nord", "country": "France"},
        {"acronym": "UDCLV", "name": "University of Campania Luigi Vanvitelli", "country": "Italy"},
        {"acronym": "UMA", "name": "University of Malaga", "country": "Spain"},
        {"acronym": "KK", "name": "Kauno Kolegija", "country": "Lithuania"},
        {"acronym": "UT", "name": "University of Tirana", "country": "Albania"},
        {"acronym": "THWS", "name": "TH Würzburg-Schweinfurt", "country": "Germany"},
        {"acronym": "TAMK", "name": "Tampere University of Applied Sciences", "country": "Finland"},
        {"acronym": "THUAS", "name": "The Hague University of Applied Sciences", "country": "Netherlands"}
    ]
}

# Global agent instance
agent: UNINOVISRagAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the RAG agent on startup."""
    global agent

    print("Initializing UNINOVIS RAG Agent...")

    # Get configuration from environment
    llm_provider = os.getenv("LLM_PROVIDER", "ollama")
    llm_model = os.getenv("LLM_MODEL", "mistral")
    data_dir = os.getenv("DATA_DIR", "data")

    agent = UNINOVISRagAgent(
        data_dir=data_dir,
        llm_provider=llm_provider,
        llm_model=llm_model
    )

    try:
        agent.initialize_embeddings()
        agent.initialize_llm()
        agent.build_vectorstore()
        print("Agent initialized successfully!")
    except Exception as e:
        print(f"Warning: Agent initialization incomplete: {e}")
        print("Some features may not be available.")

    yield


app = FastAPI(
    title=AGENT_CONFIG["name"],
    description=AGENT_CONFIG["description"],
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    history: Optional[List] = None
    num_sources: Optional[int] = 5


class Source(BaseModel):
    title: str
    doi: Optional[str] = None
    year: Optional[str] = None
    affiliations: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[Source]


class UniversitySummary(BaseModel):
    university: str
    total_papers: int
    top_topics: List[tuple]
    total_citations: int
    open_access_papers: int


class CollaborationOpportunity(BaseModel):
    university: str
    papers: List[dict]
    count: int


# Endpoints
@app.get("/")
async def root():
    """Agent information."""
    return AGENT_CONFIG


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "agent_ready": agent is not None and agent.vectorstore is not None,
        "papers_loaded": len(agent.papers_metadata) if agent else 0
    }


@app.get("/universities")
async def get_universities():
    """Get list of UNINOVIS universities."""
    return {"universities": AGENT_CONFIG["universities"]}


@app.get("/examples")
async def get_examples():
    """Get example queries."""
    return {"examples": AGENT_CONFIG["example_queries"]}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Query the RAG system about UNINOVIS research.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not agent.vectorstore:
        raise HTTPException(status_code=503, detail="Vectorstore not ready")

    try:
        result = agent.query(request.message, k=request.num_sources or 5)

        sources = [
            Source(
                title=s.get("title", "Unknown"),
                doi=s.get("doi"),
                year=str(s.get("year", "")) if s.get("year") else None,
                affiliations=s.get("affiliations")
            )
            for s in result.get("sources", [])
        ]

        return ChatResponse(
            response=result["answer"],
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summary/{university_acronym}")
async def get_university_summary(university_acronym: str):
    """Get research summary for a specific university."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = agent.get_university_summary(university_acronym)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@app.get("/collaborations")
async def find_collaborations(topic: str):
    """Find collaboration opportunities for a given topic."""
    if not agent or not agent.vectorstore:
        raise HTTPException(status_code=503, detail="Agent not ready")

    try:
        opportunities = agent.find_collaboration_opportunities(topic)
        return {"topic": topic, "opportunities": opportunities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get statistics about the research collection."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Calculate stats
    total_papers = len(agent.papers_metadata)
    total_citations = sum(p.get("cited_by_count", 0) for p in agent.papers_metadata)
    open_access = sum(1 for p in agent.papers_metadata if p.get("is_open_access"))

    # Papers by year
    from collections import Counter
    years = Counter(p.get("publication_year") for p in agent.papers_metadata if p.get("publication_year"))

    # Top topics
    all_concepts = []
    for p in agent.papers_metadata:
        all_concepts.extend([c["name"] for c in p.get("concepts", [])[:3] if c.get("name")])
    top_topics = Counter(all_concepts).most_common(20)

    return {
        "total_papers": total_papers,
        "total_citations": total_citations,
        "open_access_papers": open_access,
        "papers_by_year": dict(sorted(years.items())),
        "top_topics": top_topics,
        "vectorstore_ready": agent.vectorstore is not None
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
