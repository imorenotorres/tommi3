"""
Research Proposals — Platform for posting and discovering research collaboration opportunities.

Researchers can post proposals with funding call info, collaboration types, and partner needs.
Others can browse and express interest in collaborating.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/research_proposals", tags=["research_proposals"])


# -- Auth helpers --------------------------------------------------------------

from auth import get_session, ROLES


def _get_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.query_params.get("token")


def _require_auth(request: Request) -> dict:
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def _require_editor(request: Request) -> dict:
    session = _require_auth(request)
    if ROLES.get(session["role"], 0) < ROLES.get("tester", 99):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


# -- Data I/O ------------------------------------------------------------------

def load_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -- Models --------------------------------------------------------------------

class ProposalBody(BaseModel):
    title: str
    topic: str
    abstract: str = ""
    research_areas: list[str] = []
    keywords: list[str] = []
    # Proposer info (filled by the user posting the proposal)
    proposer_name: str = ""
    proposer_email: str = ""
    proposer_university: str = ""
    proposer_department: str = ""
    proposer_position: str = ""
    proposer_orcid: str = ""
    # Funding
    funding_call: str = ""
    funding_agency: str = ""
    funding_status: str = "planning"  # planning | submitted | funded | ongoing
    application_deadline: str = ""
    interest_deadline: str = ""
    # Collaboration
    collaboration_types: list[str] = []
    partner_profile: str = ""
    roles_available: list[str] = []
    partners_needed: int = 0
    geographic_scope: str = ""
    # Budget & positions
    budget_range: str = ""
    phd_positions: bool = False
    phd_positions_count: int = 0
    internship_positions: bool = False
    internship_positions_count: int = 0
    postdoc_positions: bool = False
    # Project info
    expected_duration: str = ""
    project_type: str = ""
    expected_outputs: str = ""
    # Status
    status: str = "open"  # open | closed | submitted | funded


# -- Routes --------------------------------------------------------------------

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    can_edit = ROLES.get(session["role"], 0) >= ROLES.get("tester", 99)
    return {"username": session["username"], "role": session["role"], "can_edit": can_edit}


@router.get("/api/data")
def get_all_data():
    return load_data()


# -- Proposal CRUD -------------------------------------------------------------

@router.post("/api/proposals")
def create_proposal(body: ProposalBody, session: dict = Depends(_require_auth)):
    data = load_data()
    now = datetime.utcnow().isoformat()
    proposal = {
        "id": str(uuid.uuid4())[:8],
        "title": body.title,
        "topic": body.topic,
        "abstract": body.abstract,
        "research_areas": body.research_areas,
        "keywords": body.keywords,
        "proposer_name": body.proposer_name,
        "proposer_email": body.proposer_email,
        "proposer_university": body.proposer_university,
        "proposer_department": body.proposer_department,
        "proposer_position": body.proposer_position,
        "proposer_orcid": body.proposer_orcid,
        "funding_call": body.funding_call,
        "funding_agency": body.funding_agency,
        "funding_status": body.funding_status,
        "application_deadline": body.application_deadline,
        "interest_deadline": body.interest_deadline,
        "collaboration_types": body.collaboration_types,
        "partner_profile": body.partner_profile,
        "roles_available": body.roles_available,
        "partners_needed": body.partners_needed,
        "geographic_scope": body.geographic_scope,
        "budget_range": body.budget_range,
        "phd_positions": body.phd_positions,
        "phd_positions_count": body.phd_positions_count,
        "internship_positions": body.internship_positions,
        "internship_positions_count": body.internship_positions_count,
        "postdoc_positions": body.postdoc_positions,
        "expected_duration": body.expected_duration,
        "project_type": body.project_type,
        "expected_outputs": body.expected_outputs,
        "status": body.status,
        "linked_username": session["username"].lower(),
        "created_at": now,
        "updated_at": now,
    }
    data["proposals"].append(proposal)
    save_data(data)
    return proposal


@router.put("/api/proposals/{proposal_id}")
def update_proposal(proposal_id: str, body: ProposalBody, session: dict = Depends(_require_auth)):
    is_editor = ROLES.get(session["role"], 0) >= ROLES.get("tester", 99)
    data = load_data()
    for p in data["proposals"]:
        if p["id"] == proposal_id:
            username = session["username"].lower()
            is_owner = p.get("linked_username", "").lower() == username
            if not is_editor and not is_owner:
                raise HTTPException(403, "You can only edit your own proposals")
            now = datetime.utcnow().isoformat()
            p.update({
                "title": body.title,
                "topic": body.topic,
                "abstract": body.abstract,
                "research_areas": body.research_areas,
                "keywords": body.keywords,
                "proposer_name": body.proposer_name,
                "proposer_email": body.proposer_email,
                "proposer_university": body.proposer_university,
                "proposer_department": body.proposer_department,
                "proposer_position": body.proposer_position,
                "proposer_orcid": body.proposer_orcid,
                "funding_call": body.funding_call,
                "funding_agency": body.funding_agency,
                "funding_status": body.funding_status,
                "application_deadline": body.application_deadline,
                "interest_deadline": body.interest_deadline,
                "collaboration_types": body.collaboration_types,
                "partner_profile": body.partner_profile,
                "roles_available": body.roles_available,
                "partners_needed": body.partners_needed,
                "geographic_scope": body.geographic_scope,
                "budget_range": body.budget_range,
                "phd_positions": body.phd_positions,
                "phd_positions_count": body.phd_positions_count,
                "internship_positions": body.internship_positions,
                "internship_positions_count": body.internship_positions_count,
                "postdoc_positions": body.postdoc_positions,
                "expected_duration": body.expected_duration,
                "project_type": body.project_type,
                "expected_outputs": body.expected_outputs,
                "status": body.status,
                "updated_at": now,
            })
            save_data(data)
            return p
    raise HTTPException(404, "Proposal not found")


@router.delete("/api/proposals/{proposal_id}")
def delete_proposal(proposal_id: str, session: dict = Depends(_require_auth)):
    is_editor = ROLES.get(session["role"], 0) >= ROLES.get("tester", 99)
    data = load_data()
    username = session["username"].lower()
    proposal = next((p for p in data["proposals"] if p["id"] == proposal_id), None)
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    is_owner = proposal.get("linked_username", "").lower() == username
    if not is_editor and not is_owner:
        raise HTTPException(403, "You can only delete your own proposals")
    data["proposals"] = [p for p in data["proposals"] if p["id"] != proposal_id]
    save_data(data)
    return {"ok": True}


# -- Research areas management -------------------------------------------------

class AreasBody(BaseModel):
    research_areas: list[str]


@router.put("/api/research-areas")
def update_research_areas(body: AreasBody, session: dict = Depends(_require_editor)):
    data = load_data()
    data["research_areas"] = body.research_areas
    save_data(data)
    return {"ok": True}
