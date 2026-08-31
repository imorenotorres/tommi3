"""
LTI 1.1 Tool Provider — Práctica de redacción

Provides an LTI-compatible tool that can be embedded in Moodle (or any LMS)
for concept definition practice with AI feedback.

LTI 1.1 uses OAuth 1.0a for authentication:
- Moodle signs the launch request with a shared secret
- This provider validates the signature
- User info (role, name, course) comes in the launch parameters

Configuration:
    In web/.env:
        LTI_CONSUMER_KEY=redaccion_uma
        LTI_CONSUMER_SECRET=<shared_secret>

Admin setup in Moodle:
    Tool URL: https://gloria.uma.es/lti/redaccion
    Consumer key: redaccion_uma
    Shared secret: <same_secret>
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from base64 import b64encode
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter(tags=["lti_redaccion"])

# ── Config ──
_APP_DIR = Path(__file__).parent
_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

LTI_KEY = os.environ.get("LTI_CONSUMER_KEY", "redaccion_uma")
LTI_SECRET = os.environ.get("LTI_CONSUMER_SECRET", "change_this_secret_in_env")

# In-memory session store (simple; for production use signed cookies or Redis)
_sessions = {}  # token → {user_id, name, email, role, course_id, course_name, expires}
SESSION_TTL = 3600 * 8  # 8 hours


# ══════════════════════════════════════════════════════════════════════
# OAuth 1.0a signature validation (no external dependencies)
# ══════════════════════════════════════════════════════════════════════

def _validate_oauth_signature(method: str, url: str, params: dict, consumer_secret: str) -> bool:
    """Validate an OAuth 1.0a HMAC-SHA1 signature."""
    # Extract the signature from params
    provided_sig = params.get("oauth_signature", "")

    # Build the signature base string
    # 1. Collect all params except oauth_signature
    sig_params = {k: v for k, v in params.items() if k != "oauth_signature"}

    # 2. Sort and encode
    sorted_params = sorted(sig_params.items())
    param_string = "&".join(
        f"{urllib.parse.quote(str(k), safe='')}" + "=" + f"{urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted_params
    )

    # 3. Build base string: METHOD&url&params
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_string, safe=""),
    ])

    # 4. Signing key: consumer_secret& (no token secret in LTI 1.1)
    signing_key = urllib.parse.quote(consumer_secret, safe="") + "&"

    # 5. HMAC-SHA1
    hashed = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1
    )
    computed_sig = b64encode(hashed.digest()).decode("utf-8")

    return hmac.compare_digest(computed_sig, provided_sig)


def _check_timestamp_nonce(timestamp: str, nonce: str) -> bool:
    """Basic replay protection: reject requests older than 10 minutes."""
    try:
        ts = int(timestamp)
        return abs(time.time() - ts) < 600
    except (ValueError, TypeError):
        return False


# ══════════════════════════════════════════════════════════════════════
# Session management
# ══════════════════════════════════════════════════════════════════════

def _create_session(user_data: dict) -> str:
    """Create a session and return the token."""
    token = secrets.token_hex(32)
    user_data["expires"] = time.time() + SESSION_TTL
    _sessions[token] = user_data
    # Cleanup expired sessions
    now = time.time()
    expired = [k for k, v in _sessions.items() if v["expires"] < now]
    for k in expired:
        del _sessions[k]
    return token


def _get_session(token: str) -> dict | None:
    """Get session data, or None if expired/invalid."""
    session = _sessions.get(token)
    if session and session["expires"] > time.time():
        return session
    return None


def _require_session(request: Request) -> dict:
    """Extract and validate session from request."""
    token = request.query_params.get("token", "") or request.cookies.get("lti_session", "")
    session = _get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Sesión no válida. Accede desde Moodle.")
    return session


def _is_instructor(session: dict) -> bool:
    return "instructor" in session.get("role", "").lower()


# ══════════════════════════════════════════════════════════════════════
# Course data management
# ══════════════════════════════════════════════════════════════════════

def _course_dir(course_id: str) -> Path:
    """Get/create data directory for a course."""
    safe_id = "".join(c for c in course_id if c.isalnum() or c in "-_")
    d = _DATA_DIR / safe_id
    d.mkdir(exist_ok=True)
    return d


def _load_course_data(course_id: str) -> dict:
    """Load concepts and config for a course."""
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


# ══════════════════════════════════════════════════════════════════════
# Info page (public, no auth)
# ══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion/info")
async def lti_info():
    """Public information page about the tool."""
    path = _APP_DIR / "static" / "info.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════
# Test access (no LTI — for development/demo)
# ══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion/test")
async def lti_test_launch(role: str = "instructor"):
    """Direct access for testing without Moodle. Use ?role=learner for student view."""
    session_data = {
        "user_id": "test_user",
        "name": "Usuario de prueba",
        "email": "test@test.com",
        "role": "Instructor" if role == "instructor" else "Learner",
        "course_id": "test",
        "course_name": "Curso de prueba (datos de Eulalia)",
        "resource_link_id": "test",
    }
    token = _create_session(session_data)
    if "instructor" in role.lower():
        return RedirectResponse(f"/lti/redaccion/docente?token={token}", status_code=303)
    return RedirectResponse(f"/lti/redaccion/practicar?token={token}", status_code=303)


# ══════════════════════════════════════════════════════════════════════
# LTI Launch endpoint
# ══════════════════════════════════════════════════════════════════════

@router.post("/lti/redaccion")
async def lti_launch(request: Request):
    """LTI 1.1 launch endpoint. Moodle POSTs here with OAuth-signed params."""
    form = await request.form()
    params = dict(form)

    # Validate OAuth signature
    consumer_key = params.get("oauth_consumer_key", "")
    if consumer_key != LTI_KEY:
        return HTMLResponse("<h2>Error: Consumer key no reconocido</h2>", status_code=403)

    # Build the launch URL (what Moodle signed against)
    launch_url = str(request.url).split("?")[0]
    # Use X-Forwarded headers if behind proxy
    if request.headers.get("x-forwarded-proto"):
        launch_url = request.headers["x-forwarded-proto"] + "://" + request.headers.get("x-forwarded-host", request.url.hostname) + request.url.path

    if not _validate_oauth_signature("POST", launch_url, params, LTI_SECRET):
        return HTMLResponse("<h2>Error: Firma OAuth no válida</h2><p>Verifica que la clave y el secreto coinciden en Moodle y en el servidor.</p>", status_code=403)

    if not _check_timestamp_nonce(params.get("oauth_timestamp", ""), params.get("oauth_nonce", "")):
        return HTMLResponse("<h2>Error: Solicitud expirada</h2><p>Inténtalo de nuevo.</p>", status_code=403)

    # Extract user info
    roles = params.get("roles", "")
    session_data = {
        "user_id": params.get("user_id", ""),
        "name": params.get("lis_person_name_full", ""),
        "email": params.get("lis_person_contact_email_primary", ""),
        "role": roles,
        "course_id": params.get("context_id", "default"),
        "course_name": params.get("context_title", ""),
        "resource_link_id": params.get("resource_link_id", ""),
    }

    token = _create_session(session_data)

    # Redirect to appropriate view
    if "instructor" in roles.lower():
        return RedirectResponse(f"/lti/redaccion/docente?token={token}", status_code=303)
    else:
        return RedirectResponse(f"/lti/redaccion/practicar?token={token}", status_code=303)


# ══════════════════════════════════════════════════════════════════════
# API endpoints (course-specific)
# ══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion/api/conceptos")
async def lti_get_conceptos(request: Request):
    session = _require_session(request)
    data = _load_course_data(session["course_id"])
    return {"config": data.get("config", {}), "conceptos": data.get("conceptos", [])}


@router.put("/lti/redaccion/api/conceptos")
async def lti_put_conceptos(request: Request):
    session = _require_session(request)
    if not _is_instructor(session):
        raise HTTPException(status_code=403, detail="Solo docentes")
    body = await request.json()
    _save_course_data(session["course_id"], {
        "config": body.get("config", {}),
        "conceptos": body.get("conceptos", [])
    })
    return {"ok": True}


@router.post("/lti/redaccion/api/evaluar")
async def lti_evaluar(request: Request):
    """Evaluate a student definition — same logic as Eulalia's endpoint."""
    session = _require_session(request)
    from llm_client import LLMClient

    body = await request.json()
    concepto = body.get("concepto", "")
    definicion = body.get("definicion", "")
    rubrica = body.get("rubrica", [])
    referencia = body.get("referencia", "")

    if not concepto or not definicion or not rubrica:
        return JSONResponse({"error": "Faltan campos"}, status_code=400)

    # Load config
    course_data = _load_course_data(session["course_id"])
    cfg = course_data.get("config", {})

    orto_tol = cfg.get("ortografia_tolerancia",
        "Errores menores aislados (1-2) se toleran. Marca false solo si hay errores frecuentes o graves.")
    estilo_crit = cfg.get("estilo_criterio",
        "Frases claras y bien construidas, con un registro apropiado para un contexto académico.")

    rubrica_ext = list(rubrica) + [
        {"descripcion": f"ORTOGRAFÍA: El texto no contiene faltas de ortografía significativas. {orto_tol}"},
        {"descripcion": f"ESTILO: El texto está bien redactado: {estilo_crit}"},
    ]
    criterios_text = "\n".join(f"- Criterio {i+1}: {c['descripcion']}" for i, c in enumerate(rubrica_ext))

    prompt = f"""Eres un tutor que evalúa definiciones. Dirígete al estudiante de tú, con un tono cercano y constructivo.

DEFINICIÓN DE REFERENCIA:
{referencia}

DEFINICIÓN DEL ESTUDIANTE:
{definicion}

RÚBRICA — Evalúa cada criterio como true (cumplido) o false (no cumplido):
{criterios_text}

INSTRUCCIONES:
- Tu ÚNICA fuente de conocimiento es la DEFINICIÓN DE REFERENCIA. NO uses tu conocimiento general.
- Sé justo y generoso con sinónimos y reformulaciones.
- Solo marca false si el concepto falta o es incorrecto SEGÚN LA REFERENCIA.
- Asegúrate de que cumplido (true/false) es coherente con tu comentario.
- En el comentario_general, NO añadas información que no esté en la referencia.
- Responde ÚNICAMENTE con JSON:
{{
  "criterios": [{{"cumplido": true/false, "comentario": "breve explicación"}}, ...],
  "comentario_general": "retroalimentación en 1-2 frases"
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

        # Log (anonymous)
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
        return JSONResponse({"error": "La IA no devolvió JSON válido"}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/lti/redaccion/api/log")
async def lti_get_log(request: Request):
    session = _require_session(request)
    if not _is_instructor(session):
        raise HTTPException(status_code=403, detail="Solo docentes")
    return {"entries": _load_course_log(session["course_id"])}


# ══════════════════════════════════════════════════════════════════════
# HTML pages (served inline for simplicity)
# ══════════════════════════════════════════════════════════════════════

@router.get("/lti/redaccion/api/session")
async def lti_session_info(request: Request):
    """Return session info for the frontend."""
    session = _require_session(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_name": session["course_name"],
        "is_instructor": _is_instructor(session),
    }


@router.get("/lti/redaccion/practicar")
async def lti_practicar(request: Request):
    """Student practice view."""
    session = _require_session(request)
    path = _APP_DIR / "static" / "practicar.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/lti/redaccion/docente")
async def lti_docente(request: Request):
    """Instructor dashboard — links to editor and review."""
    session = _require_session(request)
    if not _is_instructor(session):
        return RedirectResponse(f"/lti/redaccion/practicar?token={request.query_params.get('token', '')}")
    path = _APP_DIR / "static" / "docente.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/lti/redaccion/editor")
async def lti_editor(request: Request):
    """Concept editor view."""
    session = _require_session(request)
    if not _is_instructor(session):
        raise HTTPException(status_code=403)
    path = _APP_DIR / "static" / "editor.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/lti/redaccion/revisiones")
async def lti_revisiones(request: Request):
    """Review log view."""
    session = _require_session(request)
    if not _is_instructor(session):
        raise HTTPException(status_code=403)
    path = _APP_DIR / "static" / "revisiones.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))
