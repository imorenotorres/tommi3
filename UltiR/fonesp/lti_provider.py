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
import re
import sys
from datetime import datetime
from pathlib import Path

_PALABRAS_INAPROPIADAS = {
    'gilipollas', 'gilipollez', 'capullo', 'imbécil', 'imbecil', 'idiota',
    'subnormal', 'retrasado', 'retrasada', 'mongolo', 'mongola',
    'cabrón', 'cabron', 'cabrona', 'hijo de puta', 'hijoputa', 'hijaputa',
    'puta', 'puto', 'zorra', 'zorro', 'pendejo', 'pendeja',
    'maricón', 'maricon', 'marica', 'bollera',
    'mierda', 'mierdas', 'cagada', 'cagar', 'cagarse',
    'coño', 'cono', 'coñazo', 'joder', 'jódete', 'jodete',
    'hostia', 'hostias', 'ostia', 'ostias',
    'follar', 'follada', 'follón',
    'culo', 'culos', 'culada',
    'polla', 'pollas', 'pollón',
    'cojones', 'cojón', 'cojonudo',
    'tetas', 'tetón', 'tetona',
    'mamada', 'mamón', 'mamon', 'mamona',
    'chingar', 'chingada', 'verga',
    'caca', 'pedo', 'pis', 'meada', 'mear',
}


def _contiene_palabra_inapropiada(texto: str) -> bool:
    palabras = set(re.findall(r'[a-záéíóúüñ]+', texto.lower()))
    if palabras & _PALABRAS_INAPROPIADAS:
        return True
    if 'hijo de puta' in texto.lower():
        return True
    return False

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
_LOGS_DIR = _PROJECT_ROOT / "web" / "logs"
_LOGS_DIR.mkdir(exist_ok=True)
_PROGRESO_PATH = _LOGS_DIR / "fonesp_progreso.json"

# -- LTI config -------------------------------------------------------------

LTI_KEY = os.environ.get("FONESP_LTI_KEY", "fonesp_uma")
LTI_SECRET = os.environ.get("FONESP_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()


# -- Stats helpers ------------------------------------------------------------

def _log_fonesp_event(session: dict, event_type: str, data: dict):
    """Append a structured event to fonesp_stats.jsonl."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "user_id": session.get("user_id", ""),
        "name": session.get("name", ""),
        "course_id": session.get("course_id", ""),
        "course_name": session.get("course_name", ""),
    }
    entry.update(data)
    try:
        stats_log = _LOGS_DIR / "fonesp_stats.jsonl"
        with open(stats_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load_progreso() -> dict:
    try:
        if _PROGRESO_PATH.exists():
            return json.loads(_PROGRESO_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_progreso(data: dict):
    _PROGRESO_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    session = sessions.require(request)
    _log_fonesp_event(session, "visit", {"page": "practicar"})
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
    session = sessions.require(request)
    _log_fonesp_event(session, "exercise_start", {"exercise": "transcripcion", "nivel": nivel, "items": items})
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
    session = sessions.require(request)
    _log_fonesp_event(session, "exercise_start", {"exercise": "transcripcion_fonetica", "nivel": nivel, "items": items})
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


# ═══════════════════════════════════════════════════════════════════════
# Progress tracking
# ═══════════════════════════════════════════════════════════════════════

@router.post("/lti/fonesp/api/progreso")
async def api_save_progreso(request: Request):
    """Record exercise completion with score (called by frontend after each exercise)."""
    session = sessions.require(request)
    body = await request.json()
    ejercicio = body.get("ejercicio", "")
    score = body.get("score", 0)
    max_score = body.get("max_score", 0)

    if not ejercicio:
        raise HTTPException(400, "Falta el ID del ejercicio")

    pct = round(score / max_score * 100) if max_score > 0 else 0
    user_id = session.get("user_id") or session.get("name", "anónimo")

    all_progress = _load_progreso()
    user_data = all_progress.setdefault(user_id, {"name": session.get("name", ""), "exercises": {}})
    prev = user_data["exercises"].get(ejercicio, {})
    if not prev or pct > prev.get("score", 0):
        user_data["exercises"][ejercicio] = {
            "score": pct,
            "completed": pct >= 75,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        _save_progreso(all_progress)

    _log_fonesp_event(session, "exercise_complete", {
        "exercise": ejercicio,
        "score": pct,
        "completed": pct >= 75,
    })
    return {"ok": True, "score": pct}


# ═══════════════════════════════════════════════════════════════════════
# Stats endpoint (instructor only)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/fonesp/api/stats")
async def api_stats(request: Request):
    """Usage statistics for FonESP (instructor only)."""
    session = sessions.require(request)
    if not is_instructor(session):
        raise HTTPException(403, "Solo los instructores pueden ver las estadísticas")

    stats_log = _LOGS_DIR / "fonesp_stats.jsonl"
    events = []
    if stats_log.exists():
        for line in stats_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass

    visits = [e for e in events if e.get("event") == "visit"]
    starts = [e for e in events if e.get("event") == "exercise_start"]
    completes = [e for e in events if e.get("event") == "exercise_complete"]

    exercise_counts: dict = {}
    for e in starts:
        ex = e.get("exercise", "unknown")
        exercise_counts[ex] = exercise_counts.get(ex, 0) + 1

    # Unique students seen
    students_seen = {e.get("user_id") for e in events if e.get("user_id")}

    progreso = _load_progreso()
    student_summary = {
        uid: {
            "name": data.get("name", ""),
            "total": len(data.get("exercises", {})),
            "completed": sum(1 for v in data.get("exercises", {}).values() if v.get("completed")),
        }
        for uid, data in progreso.items()
    }

    return {
        "visits": {"total": len(visits)},
        "exercises": {
            "starts_total": len(starts),
            "completions_total": len(completes),
            "by_exercise": exercise_counts,
        },
        "students": {
            "unique_seen": len(students_seen),
            "progress": student_summary,
        },
    }
