"""
LTI 1.1 Tool Provider — Practica de redaccion

Concept definition practice with AI feedback.  Instructors create concepts
and rubrics per course; students write definitions and get evaluated.

Configuration (web/.env):
    LTI_CONSUMER_KEY=redaccion_uma
    LTI_CONSUMER_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/redaccion
    Consumer key / Shared secret: same as above
"""

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_redaccion"])

# -- Config ------------------------------------------------------------------

_APP_DIR = Path(__file__).parent
_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

LTI_KEY = os.environ.get("LTI_CONSUMER_KEY", "redaccion_uma")
LTI_SECRET = os.environ.get("LTI_CONSUMER_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()


# -- Course data management --------------------------------------------------

def _course_dir(course_id: str) -> Path:
    safe_id = "".join(c for c in course_id if c.isalnum() or c in "-_")
    d = _DATA_DIR / safe_id
    d.mkdir(exist_ok=True)
    return d


def _load_course_data(course_id: str) -> dict:
    path = _course_dir(course_id) / "conceptos.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"config": {}, "conceptos": data}
        return data
    return {"config": {
        "ortografia_tolerancia": "Errores menores aislados (1-2) se toleran. Marca false solo si hay errores frecuentes o graves.",
        "estilo_criterio": "Frases claras y bien construidas, sin ambigüedades, con un registro apropiado para un contexto académico.",
        "peso_contenido": 80,
        "peso_ortografia": 10,
        "peso_estilo": 10,
    }, "conceptos": []}


def _save_course_data(course_id: str, data: dict):
    path = _course_dir(course_id) / "conceptos.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_course_log(course_id: str) -> list:
    path = _course_dir(course_id) / "redaccion_log.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _append_course_log(course_id: str, entry: dict):
    path = _course_dir(course_id) / "redaccion_log.json"
    logs = _load_course_log(course_id)
    logs.append(entry)
    path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/redaccion")
async def redaccion_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/redaccion/docente",
        redirect_learner="/lti/redaccion/practicar",
    )


@router.get("/lti/redaccion/test")
async def redaccion_test(role: str = "instructor"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/redaccion/docente",
        redirect_learner="/lti/redaccion/practicar",
        role=role,
    )


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion/info")
async def redaccion_info():
    return HTMLResponse((_APP_DIR / "static" / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion/api/session")
async def redaccion_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_name": session["course_name"],
        "is_instructor": is_instructor(session),
    }


@router.get("/lti/redaccion/practicar")
async def redaccion_practicar(request: Request):
    sessions.require(request)
    return HTMLResponse((_APP_DIR / "static" / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion/docente")
async def redaccion_docente(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        return RedirectResponse(f"/lti/redaccion/practicar?token={request.query_params.get('token', '')}")
    return HTMLResponse((_APP_DIR / "static" / "docente.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion/editor")
async def redaccion_editor(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403)
    return HTMLResponse((_APP_DIR / "static" / "editor.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion/revisiones")
async def redaccion_revisiones(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403)
    return HTMLResponse((_APP_DIR / "static" / "revisiones.html").read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════
# API endpoints (course-specific)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion/api/conceptos")
async def redaccion_get_conceptos(request: Request):
    session = sessions.require(request)
    data = _load_course_data(session["course_id"])
    return {"config": data.get("config", {}), "conceptos": data.get("conceptos", [])}


@router.put("/lti/redaccion/api/conceptos")
async def redaccion_put_conceptos(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403, detail="Solo docentes")
    body = await request.json()
    _save_course_data(session["course_id"], {
        "config": body.get("config", {}),
        "conceptos": body.get("conceptos", [])
    })
    return {"ok": True}


@router.post("/lti/redaccion/api/evaluar")
async def redaccion_evaluar(request: Request):
    session = sessions.require(request)
    from llm_client import LLMClient

    body = await request.json()
    concepto = body.get("concepto", "")
    definicion = body.get("definicion", "")
    rubrica = body.get("rubrica", [])
    referencia = body.get("referencia", "")

    if not concepto or not definicion or not rubrica:
        return JSONResponse({"error": "Faltan campos"}, status_code=400)

    course_data = _load_course_data(session["course_id"])
    cfg = course_data.get("config", {})

    orto_tol = cfg.get("ortografia_tolerancia",
        "Errores menores aislados (1-2) se toleran. Marca false solo si hay errores frecuentes o graves.")
    estilo_crit = cfg.get("estilo_criterio",
        "Frases claras y bien construidas, con un registro apropiado para un contexto académico.")

    rubrica_ext = list(rubrica) + [
        {"descripcion": f"ORTOGRAFIA: El texto no contiene faltas de ortografia significativas. {orto_tol}"},
        {"descripcion": f"ESTILO: El texto esta bien redactado: {estilo_crit}"},
    ]
    criterios_text = "\n".join(f"- Criterio {i+1}: {c['descripcion']}" for i, c in enumerate(rubrica_ext))

    prompt = f"""Eres un tutor que evalua definiciones. Dirigete al estudiante de tu, con un tono cercano y constructivo.

DEFINICION DE REFERENCIA:
{referencia}

DEFINICION DEL ESTUDIANTE:
{definicion}

RUBRICA — Evalua cada criterio como true (cumplido) o false (no cumplido):
{criterios_text}

INSTRUCCIONES:
- Tu UNICA fuente de conocimiento es la DEFINICION DE REFERENCIA. NO uses tu conocimiento general.
- Se justo y generoso con sinonimos y reformulaciones.
- Solo marca false si el concepto falta o es incorrecto SEGUN LA REFERENCIA.
- Asegurate de que cumplido (true/false) es coherente con tu comentario.
- En el comentario_general, NO anadas informacion que no este en la referencia.
- Responde UNICAMENTE con JSON:
{{
  "criterios": [{{"cumplido": true/false, "comentario": "breve explicacion"}}, ...],
  "comentario_general": "retroalimentacion en 1-2 frases"
}}"""

    try:
        client = LLMClient()
        response = client.chat.complete(messages=[{"role": "user", "content": prompt}], max_tokens=1024)
        llm_text = response.choices[0].message.content.strip()
        import re
        if "```" in llm_text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", llm_text, re.DOTALL)
            if match:
                llm_text = match.group(1)
        result = json.loads(llm_text)

        _append_course_log(session["course_id"], {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "concepto": concepto,
            "definicion": definicion,
            "criterios": result.get("criterios", []),
            "comentario_general": result.get("comentario_general", ""),
            "aprobados": sum(1 for c in result.get("criterios", []) if c.get("cumplido")),
            "total_criterios": len(result.get("criterios", [])),
        })

        return result
    except json.JSONDecodeError:
        return JSONResponse({"error": "La IA no devolvio JSON valido"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/lti/redaccion/api/log")
async def redaccion_get_log(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403, detail="Solo docentes")
    return {"entries": _load_course_log(session["course_id"])}
