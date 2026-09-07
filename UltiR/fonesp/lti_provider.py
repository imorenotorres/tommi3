"""
FonESP — LTI 1.1 Tool Provider for phonological & phonetic transcription.

Reuses the transcription engine from tutor_fonetica_base and the exercise
banks from agents/eulalia/data/.  No LLM needed — all transcriptions are
programmatic.

Configuration (web/.env):
    FONESP_LTI_KEY=fonesp_uma
    FONESP_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/fonesp
    Consumer key / Shared secret: same as above
"""

import json
import os
import random
import sys
from pathlib import Path

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_fonesp"])

# -- Paths ------------------------------------------------------------------

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TUTOR_BASE = _PROJECT_ROOT / "agents" / "tutor_fonetica_base"
_EULALIA_DATA = _PROJECT_ROOT / "agents" / "eulalia" / "data"

# -- LTI config -------------------------------------------------------------

LTI_KEY = os.environ.get("FONESP_LTI_KEY", "fonesp_uma")
LTI_SECRET = os.environ.get("FONESP_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()

# -- Transcription helpers ---------------------------------------------------

def _ensure_transcriptor():
    if str(_TUTOR_BASE) not in sys.path:
        sys.path.insert(0, str(_TUTOR_BASE))


def _load_exercise_bank(filename: str) -> dict:
    path = _EULALIA_DATA / filename
    if not path.exists():
        raise HTTPException(500, f"Banco de ejercicios no encontrado: {filename}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp")
async def fonesp_get():
    return RedirectResponse("/lti/fonesp/info", status_code=303)


@router.post("/lti/fonesp")
async def fonesp_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/fonesp/practicar",
        redirect_learner="/lti/fonesp/practicar",
    )


@router.get("/lti/fonesp/test")
async def fonesp_test(role: str = "learner"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/fonesp/practicar",
        redirect_learner="/lti/fonesp/practicar",
        role=role,
    )


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/info")
async def fonesp_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/fonesp/practicar")
async def fonesp_practicar(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/fonesp/api/session")
async def fonesp_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_name": session["course_name"],
        "is_instructor": is_instructor(session),
    }


# ═══════════════════════════════════════════════════════════════════════
# Exercise API — phonological transcription (levels 1-5)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/api/ejercicio-transcripcion")
async def api_ejercicio_fonologica(
    request: Request,
    nivel: int = Query(1, ge=1, le=5),
    items: int = Query(5, ge=1, le=15),
    exclude: str = Query(""),
):
    sessions.require(request)
    _ensure_transcriptor()
    from transcriptor import transcribir_palabra, transcripcion_fonetica_palabra

    banco = _load_exercise_bank("ejercicios_transcripcion.json")
    nivel_key = f"nivel{nivel}"
    if nivel_key not in banco:
        raise HTTPException(400, f"Nivel {nivel} no existe")

    nivel_data = banco[nivel_key]

    if nivel == 5:
        frases = nivel_data["frases"]
        excl_set = set(e.strip() for e in exclude.split(",") if e.strip()) if exclude else set()
        disponibles = [f for f in frases if f["frase"] not in excl_set] or frases
        seleccion = random.sample(disponibles, min(items, len(disponibles)))
        ejercicios = [{"palabra": f["frase"], "solucion": f["solucion"]} for f in seleccion]
    else:
        palabras = nivel_data["palabras"]
        excl_set = set(e.strip() for e in exclude.split(",") if e.strip()) if exclude else set()
        disponibles = [p for p in palabras if p not in excl_set]
        if len(disponibles) < items:
            disponibles = palabras
        seleccion = random.sample(disponibles, min(items, len(disponibles)))

        ejercicios = []
        for palabra in seleccion:
            t = transcribir_palabra(palabra)
            if isinstance(t, tuple):
                continue
            ej = {"palabra": palabra, "solucion": t}
            try:
                tf = transcripcion_fonetica_palabra(palabra)
                if tf and not isinstance(tf, tuple):
                    ej["fonetica"] = tf
            except Exception:
                pass
            ejercicios.append(ej)

    return {
        "nivel": nivel,
        "nombre": nivel_data["nombre"],
        "descripcion": nivel_data["descripcion"],
        "ejercicios": ejercicios,
    }


# ═══════════════════════════════════════════════════════════════════════
# Exercise API — phonetic transcription (levels 1-7)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/api/ejercicio-transcripcion-fonetica")
async def api_ejercicio_fonetica(
    request: Request,
    nivel: int = Query(1, ge=1, le=7),
    items: int = Query(5, ge=1, le=15),
    exclude: str = Query(""),
):
    sessions.require(request)
    _ensure_transcriptor()
    from transcriptor import transcripcion_fonetica_palabra, transcribir_palabra

    banco = _load_exercise_bank("ejercicios_transcripcion_fonetica.json")
    nivel_key = f"nivel{nivel}"
    if nivel_key not in banco:
        raise HTTPException(400, f"Nivel {nivel} no existe")

    nivel_data = banco[nivel_key]
    palabras = nivel_data["palabras"]

    excl_set = set(e.strip() for e in exclude.split(",") if e.strip()) if exclude else set()
    disponibles = [p for p in palabras if p not in excl_set]
    if len(disponibles) < items:
        disponibles = palabras
    seleccion = random.sample(disponibles, min(items, len(disponibles)))

    ejercicios = []
    for texto in seleccion:
        palabras_txt = texto.split()
        partes_fon = []
        partes_fonet = []
        error = False
        for i, p in enumerate(palabras_txt):
            is_start = (i == 0)
            prev_last = None
            next_first = None
            if i > 0:
                prev_t = transcribir_palabra(palabras_txt[i - 1])
                if isinstance(prev_t, str) and prev_t:
                    prev_last = prev_t.replace("\u02c8", "").replace(".", "")[-1]
            if i + 1 < len(palabras_txt):
                next_t = transcribir_palabra(palabras_txt[i + 1])
                if isinstance(next_t, str) and next_t:
                    next_first = next_t.replace("\u02c8", "").replace(".", "")[0]

            tf = transcripcion_fonetica_palabra(
                p, is_utterance_start=is_start,
                prev_word_last_fonema=prev_last,
                next_word_first_fonema=next_first,
            )
            tl = transcribir_palabra(p)
            if isinstance(tf, tuple) or isinstance(tl, tuple):
                error = True
                break
            partes_fon.append(tl)
            partes_fonet.append(tf)

        if not error:
            ejercicios.append({
                "palabra": texto,
                "fonologica": "/ " + ".".join(partes_fon) + " /",
                "solucion": "[" + ".".join(partes_fonet) + "]",
            })

    return {
        "nivel": nivel,
        "nombre": nivel_data["nombre"],
        "descripcion": nivel_data["descripcion"],
        "pista": nivel_data.get("pista", ""),
        "ejercicios": ejercicios,
    }


# ═══════════════════════════════════════════════════════════════════════
# Free transcription API
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/api/transcribir")
async def api_transcribir(
    request: Request,
    texto: str = Query(..., max_length=200),
):
    sessions.require(request)
    _ensure_transcriptor()
    from transcriptor import transcribir, transcribir_palabra, transcripcion_fonetica
    from base_tutor import _contiene_palabra_inapropiada

    texto = texto.strip()
    if not texto:
        raise HTTPException(400, "Texto vacio")

    if _contiene_palabra_inapropiada(texto):
        return {"ok": False, "error": "Contenido no permitido."}

    resultado = transcribir(texto)
    if isinstance(resultado, tuple):
        return {"ok": False, "error": resultado[1]}

    result_fone = transcripcion_fonetica(texto)
    if isinstance(result_fone, tuple):
        result_fone = result_fone[0] if result_fone[0] else None

    import re
    palabras = re.findall(r"[a-záéíóúüñ]+", texto.lower())
    detalle = []
    for p in palabras:
        t = transcribir_palabra(p)
        if isinstance(t, tuple):
            detalle.append({"palabra": p, "error": t[1]})
        elif t:
            detalle.append({"palabra": p, "transcripcion": t})

    return {"ok": True, "texto": texto, "transcripcion": resultado, "fonetica": result_fone, "detalle": detalle}
