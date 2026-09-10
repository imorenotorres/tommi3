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

import hashlib
import hmac
import json
import os
import random
import secrets
import sys
import time
import urllib.parse
from base64 import b64encode
from pathlib import Path

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["lti_fonesp"])

# -- Paths ------------------------------------------------------------------

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"
_TUTOR_BASE = Path(__file__).resolve().parent.parent.parent.parent / "agents" / "tutor_fonetica_base"
_EULALIA_DATA = Path(__file__).resolve().parent.parent.parent.parent / "agents" / "eulalia" / "data"

# -- LTI config -------------------------------------------------------------

LTI_KEY = os.environ.get("FONESP_LTI_KEY", "fonesp_uma")
LTI_SECRET = os.environ.get("FONESP_LTI_SECRET", "change_this_secret_in_env")

# -- Sessions ----------------------------------------------------------------

_sessions: dict = {}
SESSION_TTL = 3600 * 8


def _validate_oauth_signature(method: str, url: str, params: dict, consumer_secret: str) -> bool:
    provided_sig = params.get("oauth_signature", "")
    sig_params = {k: v for k, v in params.items() if k != "oauth_signature"}
    sorted_params = sorted(sig_params.items())
    param_string = "&".join(
        f"{urllib.parse.quote(str(k), safe='')}" + "=" + f"{urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted_params
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_string, safe=""),
    ])
    signing_key = urllib.parse.quote(consumer_secret, safe="") + "&"
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    computed_sig = b64encode(hashed.digest()).decode()
    return hmac.compare_digest(computed_sig, provided_sig)


def _check_timestamp_nonce(timestamp: str, nonce: str) -> bool:
    try:
        return abs(time.time() - int(timestamp)) < 600
    except (ValueError, TypeError):
        return False


def _create_session(data: dict) -> str:
    token = secrets.token_hex(32)
    data["expires"] = time.time() + SESSION_TTL
    _sessions[token] = data
    now = time.time()
    for k in [k for k, v in _sessions.items() if v["expires"] < now]:
        del _sessions[k]
    return token


def _get_session(token: str) -> dict | None:
    s = _sessions.get(token)
    return s if s and s["expires"] > time.time() else None


def _require_session(request: Request) -> dict:
    token = request.query_params.get("token", "") or request.cookies.get("fonesp_session", "")
    session = _get_session(token)
    if not session:
        raise HTTPException(401, "Sesion no valida. Accede desde Moodle.")
    return session


def _is_instructor(session: dict) -> bool:
    return "instructor" in session.get("role", "").lower()


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
async def lti_get():
    return RedirectResponse("/lti/fonesp/info", status_code=303)


@router.post("/lti/fonesp")
async def lti_launch(request: Request):
    form = await request.form()
    params = dict(form)

    if params.get("oauth_consumer_key", "") != LTI_KEY:
        return HTMLResponse("<h2>Error: Consumer key no reconocido</h2>", status_code=403)

    launch_url = str(request.url).split("?")[0]
    if request.headers.get("x-forwarded-proto"):
        launch_url = (
            request.headers["x-forwarded-proto"] + "://"
            + request.headers.get("x-forwarded-host", request.url.hostname)
            + request.url.path
        )

    if not _validate_oauth_signature("POST", launch_url, params, LTI_SECRET):
        return HTMLResponse(
            "<h2>Error: Firma OAuth no valida</h2>"
            "<p>Verifica que la clave y el secreto coinciden en Moodle y en el servidor.</p>",
            status_code=403,
        )
    if not _check_timestamp_nonce(params.get("oauth_timestamp", ""), params.get("oauth_nonce", "")):
        return HTMLResponse("<h2>Error: Solicitud expirada</h2>", status_code=403)

    roles = params.get("roles", "")
    session_data = {
        "user_id": params.get("user_id", ""),
        "name": params.get("lis_person_name_full", ""),
        "email": params.get("lis_person_contact_email_primary", ""),
        "role": roles,
        "course_id": params.get("context_id", "default"),
        "course_name": params.get("context_title", ""),
    }
    token = _create_session(session_data)
    return RedirectResponse(f"/lti/fonesp/practicar?token={token}", status_code=303)


# ═══════════════════════════════════════════════════════════════════════
# Test access (no Moodle needed)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/test")
async def lti_test(role: str = "learner"):
    token = _create_session({
        "user_id": "test_user",
        "name": "Usuario de prueba",
        "email": "test@test.com",
        "role": "Instructor" if role == "instructor" else "Learner",
        "course_id": "test",
        "course_name": "Curso de prueba",
    })
    return RedirectResponse(f"/lti/fonesp/practicar?token={token}", status_code=303)


# ═══════════════════════════════════════════════════════════════════════
# Info page (public)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/info")
async def lti_info():
    path = _STATIC_DIR / "info.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════
# HTML pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/practicar")
async def page_practicar(request: Request):
    _require_session(request)
    return HTMLResponse((_STATIC_DIR / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/fonesp/api/session")
async def api_session(request: Request):
    session = _require_session(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_name": session["course_name"],
        "is_instructor": _is_instructor(session),
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
    _require_session(request)
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
    _require_session(request)
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
    _require_session(request)
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
