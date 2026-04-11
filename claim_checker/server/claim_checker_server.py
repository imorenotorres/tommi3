"""TOMMI Claim Checker — FastAPI backend for hallucination detection.

Imports ClaimExtractor and GroundingAnalyzer from agents/base/claims.py
to extract and classify factual claims against reference text.

Usage:
    cd claim_checker/server
    python claim_checker_server.py
"""

import os
import sys

# Add agents/base to path so we can import claims module directly
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AGENTS_BASE = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "agents", "base"))
if AGENTS_BASE not in sys.path:
    sys.path.insert(0, AGENTS_BASE)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from claims import ClaimExtractor, GroundingAnalyzer

app = FastAPI(title="TOMMI Claim Checker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="Text to analyze (e.g. LLM response)")
    reference_text: str = Field("", description="Reference/source text to ground against")
    strategy: str = Field("reference", description="Grounding strategy: reference, web_search, llm")


class ClaimDetail(BaseModel):
    text: str
    category: str  # "grounded" or "ungrounded"
    source: str    # "metadata", "database", or "llm"


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if req.strategy != "reference":
        return {"error": f"Strategy '{req.strategy}' not yet implemented. Use 'reference'."}

    breakdown = GroundingAnalyzer.grounding_breakdown(
        response=req.text,
        metadata_ctx="",
        rag_ctx=req.reference_text,
    )

    total = breakdown["total_claims"]
    confidence = breakdown["confidence"]

    # Determine badge
    if confidence > 80:
        badge_label, badge_color = "High", "#d4edda"
    elif confidence >= 50:
        badge_label, badge_color = "Good", "#fff3cd"
    else:
        badge_label, badge_color = "Poor", "#f8d7da"

    # Build claim details list
    claims_detail = []
    for c in breakdown["database_claims"]:
        claims_detail.append({"text": c, "category": "grounded", "source": "database"})
    for c in breakdown["metadata_claims"]:
        claims_detail.append({"text": c, "category": "grounded", "source": "metadata"})
    for c in breakdown["llm_claims"]:
        claims_detail.append({"text": c, "category": "ungrounded", "source": "llm"})

    return {
        "claims": {
            "total": total,
            "grounded": breakdown["grounded_claims"],
            "ungrounded": breakdown["ungrounded_claims"],
            "detail": claims_detail,
        },
        "badge": {
            "label": badge_label,
            "color": badge_color,
            "confidence": confidence,
        },
        "highlights": {
            "grounded": breakdown["grounded_claims"],
            "ungrounded": breakdown["ungrounded_claims"],
            "grounded_style": "background-color: rgba(40, 167, 69, 0.2); border-bottom: 2px solid #28a745; padding: 1px 2px; border-radius: 2px;",
            "ungrounded_style": "background-color: rgba(220, 53, 69, 0.2); border-bottom: 2px solid #dc3545; padding: 1px 2px; border-radius: 2px;",
        },
        "breakdown": {
            "database_pct": breakdown["database_pct"],
            "metadata_pct": breakdown["metadata_pct"],
            "llm_pct": breakdown["llm_pct"],
            "coverage_pct": breakdown["coverage_pct"],
        },
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8100))
    print(f"TOMMI Claim Checker server starting on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
