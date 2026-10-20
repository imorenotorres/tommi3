"""
LTI 1.1 Tool Provider — Practica de redaccion (evaluacion con Jev)

Variante experimental de redaccion que usa Jev (TypeSafe AI) en lugar de
un LLM de proposito general para evaluar los criterios de la rubrica.

Cada criterio se evalua como una pregunta Noul independiente sobre el estado
{referencia, definicion}, obteniendo una probabilidad 0-1 en paralelo.
Para comentario_general (texto libre) sigue usando el LLM si esta disponible.

Configuracion (web/.env):
    LTI_CONSUMER_KEY_JEV=redaccion_jev_uma
    LTI_CONSUMER_SECRET_JEV=<shared_secret>
    JEV_API_KEY=<typesafe_ai_api_key>
    JEV_COMENTARIO_LLM=true   # false para desactivar comentario_general

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/redaccion_jev
    Consumer key / Shared secret: same as above
"""

import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_redaccion_jev"])

# -- Config ------------------------------------------------------------------

_APP_DIR = Path(__file__).parent
_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

LTI_KEY = os.environ.get("LTI_CONSUMER_KEY_JEV", "redaccion_jev_uma")
LTI_SECRET = os.environ.get("LTI_CONSUMER_SECRET_JEV", "change_this_secret_in_env")
JEV_API_KEY = os.environ.get("JEV_API_KEY", "")
JEV_MODEL = os.environ.get("JEV_MODEL", "jev-latest")
JEV_COMENTARIO_LLM = os.environ.get("JEV_COMENTARIO_LLM", "true").lower() == "true"
JEV_UMBRAL = float(os.environ.get("JEV_UMBRAL", "0.5"))  # noul >= umbral -> cumplido

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


# -- Jev evaluation ----------------------------------------------------------

async def _evaluar_con_jev(referencia: str, definicion: str, rubrica_ext: list) -> dict:
    """
    Evalua cada criterio de rubrica_ext usando Jev (Noul questions).
    Devuelve dict con 'criterios' y 'jev_raw' (respuesta completa de la API).
    """
    if not JEV_API_KEY:
        raise ValueError("JEV_API_KEY no configurado")

    state = {
        "referencia": referencia,
        "definicion": definicion,
    }

    questions = {}
    for i, c in enumerate(rubrica_ext):
        questions[f"c{i}"] = {
            "type": "noul",
            "instructions": (
                f"La definicion del estudiante cumple el siguiente criterio: "
                f"{c['descripcion']}"
            ),
        }

    payload = {
        "state": state,
        "model": JEV_MODEL,
        "questions": questions,
    }

    def _call():
        resp = httpx.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={
                "Authorization": f"Bearer {JEV_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    jev_resp = await run_in_threadpool(_call)
    answers = jev_resp.get("answers", {})

    criterios = []
    for i, c in enumerate(rubrica_ext):
        key = f"c{i}"
        noul_val = answers.get(key, {}).get("noul", 0.0)
        cumplido = noul_val >= JEV_UMBRAL
        # Comentario basado en confianza, sin LLM
        if cumplido:
            comentario = f"Confianza: {noul_val:.0%}"
        else:
            comentario = f"No detectado. Confianza de ausencia: {1 - noul_val:.0%}"
        criterios.append({
            "cumplido": cumplido,
            "comentario": comentario,
            "noul": round(noul_val, 3),
        })

    return {
        "criterios": criterios,
        "jev_raw": jev_resp,
        "usage": jev_resp.get("usage", {}),
    }


async def _comentario_general_llm(referencia: str, definicion: str, criterios: list) -> str:
    """Genera comentario_general con el LLM si JEV_COMENTARIO_LLM=true."""
    from llm_client import LLMClient
    import re

    aprobados = sum(1 for c in criterios if c.get("cumplido"))
    total = len(criterios)
    resumen = "\n".join(
        f"- Criterio {i+1}: {'cumplido' if c['cumplido'] else 'no cumplido'} (confianza {c['noul']:.0%})"
        for i, c in enumerate(criterios)
    )

    prompt = f"""Eres un tutor que da retroalimentacion breve y constructiva.
Dirigete al estudiante de tu.

DEFINICION DE REFERENCIA:
{referencia}

DEFINICION DEL ESTUDIANTE:
{definicion}

EVALUACION AUTOMATICA (Jev):
{resumen}
{aprobados}/{total} criterios cumplidos.

Escribe UNA o DOS frases de retroalimentacion general. No repitas los criterios.
No anadas informacion que no este en la referencia. Solo el texto, sin formato."""

    client = LLMClient()
    response = await run_in_threadpool(
        client.chat.complete,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/redaccion_jev")
async def redaccion_jev_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/redaccion_jev/docente",
        redirect_learner="/lti/redaccion_jev/practicar",
    )


@router.get("/lti/redaccion_jev/test")
async def redaccion_jev_test(role: str = "instructor"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/redaccion_jev/docente",
        redirect_learner="/lti/redaccion_jev/practicar",
        role=role,
    )


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion_jev/info")
async def redaccion_jev_info():
    return HTMLResponse((_APP_DIR / "static" / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion_jev/api/session")
async def redaccion_jev_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_name": session["course_name"],
        "is_instructor": is_instructor(session),
    }


@router.get("/lti/redaccion_jev/practicar")
async def redaccion_jev_practicar(request: Request):
    sessions.require(request)
    return HTMLResponse((_APP_DIR / "static" / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion_jev/docente")
async def redaccion_jev_docente(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        return RedirectResponse(f"/lti/redaccion_jev/practicar?token={request.query_params.get('token', '')}")
    return HTMLResponse((_APP_DIR / "static" / "docente.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion_jev/editor")
async def redaccion_jev_editor(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403)
    return HTMLResponse((_APP_DIR / "static" / "editor.html").read_text(encoding="utf-8"))


@router.get("/lti/redaccion_jev/revisiones")
async def redaccion_jev_revisiones(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403)
    return HTMLResponse((_APP_DIR / "static" / "revisiones.html").read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════
# API endpoints (course-specific)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion_jev/api/conceptos")
async def redaccion_jev_get_conceptos(request: Request):
    session = sessions.require(request)
    data = _load_course_data(session["course_id"])
    return {"config": data.get("config", {}), "conceptos": data.get("conceptos", [])}


@router.put("/lti/redaccion_jev/api/conceptos")
async def redaccion_jev_put_conceptos(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403, detail="Solo docentes")
    body = await request.json()
    _save_course_data(session["course_id"], {
        "config": body.get("config", {}),
        "conceptos": body.get("conceptos", [])
    })
    return {"ok": True}


@router.get("/lti/redaccion_jev/api/jev-status")
async def redaccion_jev_status():
    """Informa si la clave Jev esta configurada."""
    return {
        "jev_configured": bool(JEV_API_KEY),
        "jev_model": JEV_MODEL,
        "jev_umbral": JEV_UMBRAL,
        "comentario_llm": JEV_COMENTARIO_LLM,
    }


@router.post("/lti/redaccion_jev/api/evaluar")
async def redaccion_jev_evaluar(request: Request):
    session = sessions.require(request)

    body = await request.json()
    concepto = body.get("concepto", "")
    definicion = body.get("definicion", "")
    rubrica = body.get("rubrica", [])
    referencia = body.get("referencia", "")

    if not concepto or not definicion or not rubrica:
        return JSONResponse({"error": "Faltan campos"}, status_code=400)

    if not JEV_API_KEY:
        return JSONResponse({"error": "JEV_API_KEY no configurado en el servidor"}, status_code=503)

    course_data = _load_course_data(session["course_id"])
    cfg = course_data.get("config", {})

    orto_tol = cfg.get("ortografia_tolerancia",
        "Errores menores aislados (1-2) se toleran. Marca false solo si hay errores frecuentes o graves.")
    estilo_crit = cfg.get("estilo_criterio",
        "Frases claras y bien construidas, con un registro apropiado para un contexto academico.")

    rubrica_ext = list(rubrica) + [
        {"descripcion": f"ORTOGRAFIA: El texto no contiene faltas de ortografia significativas. {orto_tol}"},
        {"descripcion": f"ESTILO: El texto esta bien redactado: {estilo_crit}"},
    ]

    try:
        jev_result = await _evaluar_con_jev(referencia, definicion, rubrica_ext)
        criterios = jev_result["criterios"]

        comentario_general = ""
        if JEV_COMENTARIO_LLM:
            try:
                comentario_general = await _comentario_general_llm(referencia, definicion, criterios)
            except Exception:
                comentario_general = ""

        _append_course_log(session["course_id"], {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "concepto": concepto,
            "definicion": definicion,
            "criterios": criterios,
            "comentario_general": comentario_general,
            "aprobados": sum(1 for c in criterios if c.get("cumplido")),
            "total_criterios": len(criterios),
            "motor": "jev",
            "jev_model": jev_result.get("jev_raw", {}).get("model", JEV_MODEL),
            "jev_usage": jev_result.get("usage", {}),
        })

        return {
            "criterios": criterios,
            "comentario_general": comentario_general,
            "motor": "jev",
        }

    except httpx.HTTPStatusError as e:
        return JSONResponse({"error": f"Error de Jev API: {e.response.status_code}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/lti/redaccion_jev/api/log")
async def redaccion_jev_get_log(request: Request):
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(status_code=403, detail="Solo docentes")
    return {"entries": _load_course_log(session["course_id"])}
