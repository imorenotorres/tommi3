"""
Proyecto LTI — AI-assisted research/writing projects with RAG.

Instructors upload reference documents (PDFs/text) and configure project
phases.  Students chat with an LLM grounded in those documents, and
explicitly accept/reject/adapt each AI suggestion with a justification.
All interactions are stored and visible to the instructor.

Configuration (web/.env):
    PROYECTO_LTI_KEY=proyecto_uma
    PROYECTO_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/proyecto
"""

import json
import math
import os
import re
import shutil
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_proyecto"])

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"
_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

LTI_KEY = os.environ.get("PROYECTO_LTI_KEY", "proyecto_uma")
LTI_SECRET = os.environ.get("PROYECTO_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()

DEFAULT_PHASES = [
    {"id": "introduccion", "name": "Introduction"},
    {"id": "metodologia", "name": "Methodology"},
    {"id": "resultados", "name": "Results"},
    {"id": "discusion", "name": "Discussion"},
]

DEFAULT_SYSTEM_PROMPT = (
    "You are an academic tutor helping a student with their research project. "
    "The student is working on phase: {phase_name}.\n\n"
    "Your role is to GUIDE the student:\n"
    "- If the student explains their goal, suggest how to approach this phase.\n"
    "- If they show their work, point out inconsistencies and suggest concrete improvements.\n"
    "- Ask questions to make them reflect: 'Have you considered...?', 'What if...?'\n\n"
    "WRITING STRATEGY:\n"
    "When the student asks for help WRITING a section, WRITE THE TEXT DIRECTLY as a paragraph "
    "for the final paper. Do NOT give steps or guidelines — write the text.\n"
    "Mark anything the student must verify in [brackets].\n"
    "After the text, add: 'Read this draft and tell me what you want to change.'\n"
    "Allow a maximum of 2 refinements. After the second, say: "
    "'This is the final draft. Work on it in your text editor.'\n\n"
    "KNOWLEDGE LIMITS:\n"
    "- Base your answers FIRST on the retrieved context from the course materials (below).\n"
    "- If you need information NOT in the materials, you may use general knowledge but WARN: "
    "'This information does not come from the course materials. Verify with other sources.'\n"
    "- NEVER invent bibliographic references.\n"
    "- Be concise (max 200 words)."
)


# ═══════════════════════════════════════════════════════════════════════
# Per-course data
# ═══════════════════════════════════════════════════════════════════════

def _course_dir(course_id: str) -> Path:
    safe = "".join(c for c in course_id if c.isalnum() or c in "-_") or "default"
    d = _DATA_DIR / safe
    d.mkdir(exist_ok=True)
    return d


def _docs_dir(course_id: str) -> Path:
    d = _course_dir(course_id) / "docs"
    d.mkdir(exist_ok=True)
    return d


def _projects_dir(course_id: str) -> Path:
    d = _course_dir(course_id) / "projects"
    d.mkdir(exist_ok=True)
    return d


def _load_course_config(course_id: str) -> dict:
    path = _course_dir(course_id) / "config.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "phases": DEFAULT_PHASES,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "max_group_size": 3,
    }


def _save_course_config(course_id: str, config: dict):
    path = _course_dir(course_id) / "config.json"
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# BM25 RAG (self-contained, no agent dependency)
# ═══════════════════════════════════════════════════════════════════════

_WORD_RE = re.compile(r"[a-z][a-z0-9]{2,}", re.IGNORECASE)
_STOP = frozenset(
    "a an the and or but in on of to for is are was were be been being "
    "have has had do does did will would shall should may might can could "
    "this that these those it its we you he she they them their our "
    "with from by at as not no nor so if than too very also about above "
    "after before between into through during over under up down out off "
    "then once here there when where which who whom what how all each "
    "both few more most other some such only own same just because "
    "while however although though even still already yet since until "
    "el la los las un una de del en que es son fue era ser estar "
    "por para con como si no su sus al lo este esta estos estas "
    "pero mas muy ya todo este esto esta eso esa aquel aquella "
    "hay tiene puede sobre entre hasta desde donde cuando".split()
)


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOP and len(w) > 2]


def _smart_chunk(text: str, size: int = 600, overlap: int = 100) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        if end < len(text):
            for sep in ["\n\n", ". ", "\n"]:
                last = chunk.rfind(sep)
                if last > size * 0.6:
                    chunk = chunk[:last + len(sep)]
                    end = start + len(chunk)
                    break
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def _extract_text(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            return "\n".join(p.extract_text() or "" for p in PdfReader(filepath).pages)
        except Exception:
            return ""
    elif ext in (".md", ".txt"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
    return ""


def _build_chunk_db(course_id: str) -> dict:
    """Build BM25 chunk database from all documents in the course docs dir."""
    docs = _docs_dir(course_id)
    all_chunks = []
    for fn in sorted(os.listdir(docs)):
        text = _extract_text(str(docs / fn))
        if not text.strip():
            continue
        for chunk_text in _smart_chunk(text):
            keywords = _tokenize(chunk_text)
            all_chunks.append({"text": chunk_text, "keywords": keywords, "source": fn})

    # Compute IDF
    n = len(all_chunks) or 1
    df = Counter()
    for c in all_chunks:
        df.update(set(c["keywords"]))
    idf = {term: math.log((n - freq + 0.5) / (freq + 0.5) + 1) for term, freq in df.items()}

    db = {"chunks": all_chunks, "idf": idf}
    db_path = _course_dir(course_id) / "chunk_db.json"
    db_path.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    return db


def _load_chunk_db(course_id: str) -> dict:
    db_path = _course_dir(course_id) / "chunk_db.json"
    if db_path.exists():
        return json.loads(db_path.read_text(encoding="utf-8"))
    return _build_chunk_db(course_id)


def _retrieve_context(course_id: str, query: str, top_k: int = 5) -> str:
    db = _load_chunk_db(course_id)
    chunks = db.get("chunks", [])
    idf = db.get("idf", {})
    if not chunks:
        return ""
    avg_kw = sum(len(c["keywords"]) for c in chunks) / len(chunks) if chunks else 15

    query_tokens = _tokenize(query)
    scored = []
    for i, c in enumerate(chunks):
        kw = c["keywords"]
        score = 0.0
        kw_set = set(kw)
        doc_len = len(kw)
        for qt in query_tokens:
            if qt not in kw_set:
                continue
            tf = kw.count(qt)
            idf_val = idf.get(qt, 0.0)
            score += idf_val * (tf * 2.5) / (tf + 1.5 * (1 - 0.75 + 0.75 * doc_len / avg_kw))
        if score > 0:
            scored.append((score, i))

    scored.sort(reverse=True)
    results = [chunks[i]["text"] for _, i in scored[:top_k]]
    return "\n\n---\n\n".join(results)


# ═══════════════════════════════════════════════════════════════════════
# Project data
# ═══════════════════════════════════════════════════════════════════════

def _load_project(course_id: str, project_id: str) -> dict | None:
    path = _projects_dir(course_id) / f"{project_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_project(course_id: str, project: dict):
    project["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    path = _projects_dir(course_id) / f"{project['id']}.json"
    path.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/proyecto")
async def proyecto_get():
    return RedirectResponse("/lti/proyecto/info", status_code=303)


@router.post("/lti/proyecto")
async def proyecto_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/proyecto/docente",
        redirect_learner="/lti/proyecto/estudiante",
    )


@router.get("/lti/proyecto/test")
async def proyecto_test(role: str = "learner"):
    """Test with a pre-configured demo: Phonological Errors in VPD."""
    token = sessions.create({
        "user_id": "test_user",
        "name": "Test User",
        "email": "test@test.com",
        "role": "Instructor" if role == "instructor" else "Learner",
        "course_id": "test",
        "course_name": "Demo: Phonological Errors in Velopharyngeal Dysfunction",
        "resource_link_id": "test",
    })
    dest = "/lti/proyecto/docente" if role == "instructor" else "/lti/proyecto/estudiante"
    return RedirectResponse(f"{dest}?token={token}", status_code=303)


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/proyecto/info")
async def proyecto_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/proyecto/estudiante")
async def proyecto_estudiante(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "estudiante.html").read_text(encoding="utf-8"))


@router.get("/lti/proyecto/docente")
async def proyecto_docente(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        return RedirectResponse(f"/lti/proyecto/estudiante?token={request.query_params.get('token', '')}")
    return HTMLResponse((_STATIC_DIR / "docente.html").read_text(encoding="utf-8"))


@router.get("/lti/proyecto/api/session")
async def proyecto_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "email": session["email"],
        "role": session["role"],
        "course_id": session["course_id"],
        "course_name": session["course_name"],
        "is_instructor": is_instructor(session),
    }


# ═══════════════════════════════════════════════════════════════════════
# Course config (instructor only)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/proyecto/api/config")
async def proyecto_get_config(request: Request):
    session = sessions.require(request)
    config = _load_course_config(session["course_id"])
    # List uploaded documents
    docs = sorted(os.listdir(_docs_dir(session["course_id"])))
    return {**config, "documents": docs}


@router.put("/lti/proyecto/api/config")
async def proyecto_put_config(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes")
    body = await request.json()
    config = _load_course_config(session["course_id"])
    if "phases" in body:
        config["phases"] = body["phases"]
    if "system_prompt" in body:
        config["system_prompt"] = body["system_prompt"]
    if "max_group_size" in body:
        config["max_group_size"] = body["max_group_size"]
    _save_course_config(session["course_id"], config)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Document upload (instructor only)
# ═══════════════════════════════════════════════════════════════════════

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

# MIME signatures for allowed file types
_MIME_SIGNATURES = {
    b"%PDF": ".pdf",
    b"# ": ".md",     # Markdown typically starts with heading
}


@router.post("/lti/proyecto/api/docs")
async def proyecto_upload_doc(request: Request, file: UploadFile = File(...)):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".md", ".txt"):
        raise HTTPException(400, "Solo PDF, Markdown o texto plano")
    content = await file.read()
    # Size limit
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"File too large (max {MAX_UPLOAD_SIZE // (1024*1024)} MB)")
    # MIME validation for PDFs
    if ext == ".pdf" and not content[:5].startswith(b"%PDF"):
        raise HTTPException(400, "File does not appear to be a valid PDF")
    safe_name = re.sub(r'[^\w\-. ]', '_', file.filename or "doc")
    dest = _docs_dir(session["course_id"]) / safe_name
    dest.write_bytes(content)
    _build_chunk_db(session["course_id"])
    return {"ok": True, "filename": safe_name}


@router.delete("/lti/proyecto/api/docs/{filename}")
async def proyecto_delete_doc(filename: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo docentes")
    # Same cleanup as the upload endpoint above — filename ends up in a
    # path and must never be treated as anything but inert text.
    safe_name = re.sub(r'[^\w\-. ]', '_', filename or "")
    path = _docs_dir(session["course_id"]) / safe_name
    if not path.exists():
        raise HTTPException(404, "Documento no encontrado")
    path.unlink()
    _build_chunk_db(session["course_id"])
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Projects CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/proyecto/api/projects")
async def proyecto_list(request: Request):
    session = sessions.require(request)
    course_id = session["course_id"]
    email = session["email"].lower()
    is_prof = is_instructor(session)

    projects = []
    pdir = _projects_dir(course_id)
    for f in pdir.glob("*.json"):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            if is_prof or email in [m.lower() for m in p.get("grupo", [])]:
                summary = {k: v for k, v in p.items() if k != "chat"}
                summary["n_chat"] = len(p.get("chat", []))
                projects.append(summary)
        except Exception:
            pass
    projects.sort(key=lambda x: x.get("updated", ""), reverse=True)
    return {"projects": projects}


@router.post("/lti/proyecto/api/projects")
async def proyecto_create(request: Request):
    session = sessions.require(request)
    course_id = session["course_id"]
    email = session["email"].lower()
    is_prof = is_instructor(session)

    # Students: 1 project max
    if not is_prof:
        for f in _projects_dir(course_id).glob("*.json"):
            try:
                p = json.loads(f.read_text(encoding="utf-8"))
                if email in [m.lower() for m in p.get("grupo", [])]:
                    raise HTTPException(409, "You already have a project in this course.")
            except HTTPException:
                raise
            except Exception:
                pass

    body = await request.json()
    titulo = body.get("titulo", "").strip()
    if not titulo:
        raise HTTPException(400, "Title is required")

    config = _load_course_config(course_id)
    phases = config.get("phases", DEFAULT_PHASES)

    project_id = uuid.uuid4().hex[:8]
    project = {
        "id": project_id,
        "titulo": titulo,
        "grupo": [email],
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fases": {ph["id"]: {"texto": "", "ultima_edicion": ""} for ph in phases},
        "chat": [],
    }
    _save_project(course_id, project)
    return {"ok": True, "id": project_id}


@router.get("/lti/proyecto/api/projects/{project_id}")
async def proyecto_get(project_id: str, request: Request):
    session = sessions.require(request)
    project = _load_project(session["course_id"], project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    email = session["email"].lower()
    is_prof = is_instructor(session)
    if not is_prof and email not in [m.lower() for m in project.get("grupo", [])]:
        raise HTTPException(403, "No access to this project")
    return project


@router.delete("/lti/proyecto/api/projects/{project_id}")
async def proyecto_delete(project_id: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Instructors only")
    course_id = session["course_id"]
    project = _load_project(course_id, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    deleted_dir = _course_dir(course_id) / "deleted"
    deleted_dir.mkdir(exist_ok=True)
    src = _projects_dir(course_id) / f"{project_id}.json"
    shutil.move(str(src), str(deleted_dir / f"{project_id}.json"))
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Group management
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/proyecto/api/projects/{project_id}/invite")
async def proyecto_invite(project_id: str, request: Request):
    session = sessions.require(request)
    course_id = session["course_id"]
    project = _load_project(course_id, project_id)
    if not project:
        raise HTTPException(404)
    email = session["email"].lower()
    if email not in [m.lower() for m in project.get("grupo", [])]:
        raise HTTPException(403)
    body = await request.json()
    new_email = body.get("email", "").strip().lower()
    if not new_email or "@" not in new_email:
        raise HTTPException(400, "Invalid email")
    if new_email in [m.lower() for m in project["grupo"]]:
        raise HTTPException(409, "Already a member")
    config = _load_course_config(course_id)
    max_size = config.get("max_group_size", 3)
    if len(project["grupo"]) >= max_size:
        raise HTTPException(400, f"Group already has {max_size} members (maximum)")
    project["grupo"].append(new_email)
    _save_project(course_id, project)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Chat (RAG + LLM)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/proyecto/api/projects/{project_id}/chat")
async def proyecto_chat(project_id: str, request: Request):
    session = sessions.require(request)
    course_id = session["course_id"]
    email = session["email"].lower()

    project = _load_project(course_id, project_id)
    if not project:
        raise HTTPException(404)
    if email not in [m.lower() for m in project.get("grupo", [])]:
        raise HTTPException(403)

    body = await request.json()
    mensaje = body.get("mensaje", "").strip()
    fase = body.get("fase", "")
    contexto_fase = body.get("contexto_fase", "")
    if not mensaje:
        raise HTTPException(400, "Empty message")

    # Load course config
    config = _load_course_config(course_id)
    phases = config.get("phases", DEFAULT_PHASES)
    phase_name = next((ph["name"] for ph in phases if ph["id"] == fase), fase)

    # RAG: retrieve context from course documents
    rag_context = _retrieve_context(course_id, mensaje)

    # Build system prompt
    sys_prompt = config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    sys_prompt = sys_prompt.replace("{phase_name}", phase_name)

    if rag_context:
        sys_prompt += f"\n\nRetrieved context from course materials:\n{rag_context}"
    if contexto_fase:
        sys_prompt += f"\n\nCurrent content of phase '{phase_name}' written by the group:\n{contexto_fase}"

    # Recent chat history (with decision annotations)
    recent = [m for m in project.get("chat", []) if m.get("fase") == fase][-6:]
    messages = [{"role": "system", "content": sys_prompt}]
    for m in recent:
        messages.append({"role": "user", "content": m.get("prompt", "")})
        if m.get("respuesta"):
            resp = m["respuesta"]
            decision = m.get("decision")
            if decision and decision.get("accion"):
                labels = {"aplicado": "ACCEPTED", "no_aplicado": "REJECTED", "parcialmente": "PARTIALLY ACCEPTED"}
                label = labels.get(decision["accion"], "")
                justif = decision.get("justificacion", "")
                resp += f"\n[The student {label} this response"
                if justif:
                    resp += f": {justif}"
                resp += "]"
            messages.append({"role": "assistant", "content": resp})
    messages.append({"role": "user", "content": mensaje})

    # Call LLM
    try:
        from llm_client import LLMClient
        client = LLMClient()
        response = client.chat.complete(messages=messages, max_tokens=1024)
        respuesta = response.choices[0].message.content
    except Exception as e:
        respuesta = f"Error querying AI: {str(e)}"

    # Save chat entry
    chat_entry = {
        "autor": email,
        "prompt": mensaje,
        "respuesta": respuesta,
        "fase": fase,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "decision": None,
    }
    project["chat"].append(chat_entry)
    _save_project(course_id, project)

    return {"respuesta": respuesta, "chat_index": len(project["chat"]) - 1}


# ═══════════════════════════════════════════════════════════════════════
# Decision tracking
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/proyecto/api/projects/{project_id}/decision")
async def proyecto_decision(project_id: str, request: Request):
    session = sessions.require(request)
    course_id = session["course_id"]
    email = session["email"].lower()

    project = _load_project(course_id, project_id)
    if not project:
        raise HTTPException(404)
    if email not in [m.lower() for m in project.get("grupo", [])]:
        raise HTTPException(403)

    body = await request.json()
    chat_index = body.get("chat_index")
    accion = body.get("accion", "")
    justificacion = body.get("justificacion", "")

    if chat_index is None or chat_index < 0 or chat_index >= len(project.get("chat", [])):
        raise HTTPException(400, "Invalid chat index")
    if accion not in ("aplicado", "no_aplicado", "parcialmente"):
        raise HTTPException(400, "Action must be: aplicado, no_aplicado, parcialmente")

    project["chat"][chat_index]["decision"] = {
        "accion": accion,
        "justificacion": justificacion,
        "autor": email,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _save_project(course_id, project)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Instructor: scoring
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/proyecto/api/projects/{project_id}/score")
async def proyecto_score(project_id: str, request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403)
    project = _load_project(session["course_id"], project_id)
    if not project:
        raise HTTPException(404)
    body = await request.json()
    idx = body.get("chat_index")
    score = body.get("score")
    if idx is None or idx < 0 or idx >= len(project.get("chat", [])):
        raise HTTPException(400, "Invalid index")
    if score is None or score < 0 or score > 4:
        raise HTTPException(400, "Score must be 0-4")
    project["chat"][idx]["teacher_score"] = score
    _save_project(session["course_id"], project)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/proyecto/api/projects/{project_id}/export")
async def proyecto_export(project_id: str, request: Request):
    session = sessions.require(request)
    course_id = session["course_id"]
    project = _load_project(course_id, project_id)
    if not project:
        raise HTTPException(404)
    email = session["email"].lower()
    is_prof = is_instructor(session)
    if not is_prof and email not in [m.lower() for m in project.get("grupo", [])]:
        raise HTTPException(403)

    # TSV export of all interactions
    lines = ["Phase\tDate\tAuthor\tPrompt\tResponse\tDecision\tJustification\tScore"]
    for m in project.get("chat", []):
        dec = m.get("decision") or {}
        lines.append("\t".join([
            m.get("fase", ""),
            m.get("fecha", ""),
            m.get("autor", ""),
            m.get("prompt", "").replace("\t", " ").replace("\n", " "),
            m.get("respuesta", "").replace("\t", " ").replace("\n", " ")[:500],
            dec.get("accion", ""),
            dec.get("justificacion", "").replace("\t", " ").replace("\n", " "),
            str(m.get("teacher_score", "")),
        ]))

    tsv = "\ufeff" + "\n".join(lines)  # BOM for Excel
    from fastapi.responses import Response
    return Response(
        content=tsv,
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="project_{project_id}.tsv"'},
    )
