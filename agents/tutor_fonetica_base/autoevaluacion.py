"""
Sistema de autoevaluación para tutores de Fonética.

Gestiona dos tipos de ejercicios de autoevaluación:
  - Prácticos: evaluación programática (transcripción, identificación de alófonos, etc.)
  - Teóricos: evaluación con LLM (contenido + aspectos formales)

Todos los resultados se almacenan persistentemente por alumno.
El progreso incluye métricas cuantitativas (ejercicios, errores por semana)
y cualitativas (áreas con más fallos, recomendaciones).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════
# ALMACENAMIENTO
# ═══════════════════════════════════════════════════════════════════════

_AUTOEVAL_DIR = None


def set_autoeval_dir(path):
    """Configura el directorio de almacenamiento de autoevaluaciones."""
    global _AUTOEVAL_DIR
    _AUTOEVAL_DIR = Path(path)
    _AUTOEVAL_DIR.mkdir(parents=True, exist_ok=True)


def _ruta_alumno(username: str) -> Path:
    safe = username.replace('/', '_').replace('\\', '_').replace('..', '_')
    return _AUTOEVAL_DIR / f"{safe}_autoeval.json"


def _cargar(username: str) -> dict:
    ruta = _ruta_alumno(username)
    if not ruta.exists():
        return {"temas": {}}
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"temas": {}}


def _guardar(username: str, data: dict):
    ruta = _ruta_alumno(username)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


# ═══════════════════════════════════════════════════════════════════════
# REGISTRO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════

def registrar_practico(username: str, tema_id: int, *,
                       pregunta: str, respuesta: str,
                       correcto: bool, puntuacion: float = None,
                       errores: list = None, categoria: str = '',
                       recomendaciones: list = None):
    """Registra el resultado de un ejercicio práctico (evaluación programática).

    Args:
        username: alumno
        tema_id: número de tema
        pregunta: enunciado del ejercicio
        respuesta: respuesta del alumno
        correcto: si la respuesta es correcta
        puntuacion: porcentaje (0-100), opcional
        errores: lista de tipos de error (ej: ['acento', 'fonema'])
        categoria: categoría del ejercicio (ej: 'transcripcion', 'alofonos')
        recomendaciones: lista de recomendaciones
    """
    data = _cargar(username)
    tema_key = str(tema_id)
    if tema_key not in data["temas"]:
        data["temas"][tema_key] = {"evaluaciones": []}

    now = datetime.now()
    data["temas"][tema_key]["evaluaciones"].append({
        "fecha": now.isoformat(),
        "semana": now.isocalendar()[1],
        "anio": now.year,
        "tipo": "practico",
        "metodo": "programatico",
        "categoria": categoria,
        "pregunta": pregunta,
        "respuesta_alumno": respuesta,
        "correcto": correcto,
        "puntuacion": puntuacion,
        "errores": errores or [],
        "recomendaciones": recomendaciones or [],
    })
    _guardar(username, data)


def registrar_teorico(username: str, tema_id: int, *,
                      pregunta: str, respuesta: str,
                      evaluacion_contenido: dict = None,
                      evaluacion_formal: dict = None,
                      puntuacion: float = None,
                      recomendaciones: list = None,
                      consultado_docente: bool = False):
    """Registra el resultado de un ejercicio teórico (evaluación LLM).

    Args:
        evaluacion_contenido: dict con:
            - correspondencia: float (0-100) grado de coincidencia con lo esperado
            - elementos_presentes: list de conceptos mencionados correctamente
            - elementos_faltantes: list de conceptos no mencionados
            - errores_conceptuales: list de errores en el contenido
        evaluacion_formal: dict con:
            - ortografia: int (0-100)
            - gramatica: int (0-100)
            - redaccion: int (0-100)
            - observaciones: list de observaciones formales
    """
    data = _cargar(username)
    tema_key = str(tema_id)
    if tema_key not in data["temas"]:
        data["temas"][tema_key] = {"evaluaciones": []}

    now = datetime.now()
    data["temas"][tema_key]["evaluaciones"].append({
        "fecha": now.isoformat(),
        "semana": now.isocalendar()[1],
        "anio": now.year,
        "tipo": "teorico",
        "metodo": "llm",
        "pregunta": pregunta,
        "respuesta_alumno": respuesta,
        "puntuacion": puntuacion,
        "evaluacion_contenido": evaluacion_contenido or {},
        "evaluacion_formal": evaluacion_formal or {},
        "recomendaciones": recomendaciones or [],
        "consultado_docente": consultado_docente,
    })
    _guardar(username, data)


# ═══════════════════════════════════════════════════════════════════════
# PROGRESO CUANTITATIVO Y CUALITATIVO
# ═══════════════════════════════════════════════════════════════════════

def progreso_tema(username: str, tema_id: int) -> dict:
    """Devuelve el progreso detallado de un alumno en un tema.

    Returns:
        dict con:
            - total_ejercicios: int
            - practicos: {total, correctos, incorrectos, puntuacion_media}
            - teoricos: {total, puntuacion_media_contenido, puntuacion_media_formal}
            - por_semana: [{semana, anio, total, correctos, incorrectos}]
            - errores_frecuentes: [{tipo, frecuencia}] (top 5)
            - recomendaciones: [str]
            - categorias: {categoria: {total, correctos}} (desglose por tipo de ejercicio)
    """
    data = _cargar(username)
    evals = data.get("temas", {}).get(str(tema_id), {}).get("evaluaciones", [])

    if not evals:
        return {
            "total_ejercicios": 0,
            "practicos": {"total": 0, "correctos": 0, "incorrectos": 0, "puntuacion_media": None},
            "teoricos": {"total": 0, "puntuacion_media_contenido": None, "puntuacion_media_formal": None},
            "por_semana": [],
            "errores_frecuentes": [],
            "recomendaciones": [],
            "categorias": {},
        }

    # Prácticos
    practicos = [e for e in evals if e["tipo"] == "practico"]
    p_correctos = sum(1 for e in practicos if e.get("correcto"))
    p_puntuaciones = [e["puntuacion"] for e in practicos if e.get("puntuacion") is not None]

    # Teóricos
    teoricos = [e for e in evals if e["tipo"] == "teorico"]
    t_contenido = [e["evaluacion_contenido"].get("correspondencia")
                   for e in teoricos
                   if e.get("evaluacion_contenido", {}).get("correspondencia") is not None]
    t_formal_scores = []
    for e in teoricos:
        ef = e.get("evaluacion_formal", {})
        scores = [ef.get(k) for k in ("ortografia", "gramatica", "redaccion") if ef.get(k) is not None]
        if scores:
            t_formal_scores.append(sum(scores) / len(scores))

    # Por semana
    semanas = {}
    for e in evals:
        key = (e.get("anio", 0), e.get("semana", 0))
        if key not in semanas:
            semanas[key] = {"semana": key[1], "anio": key[0], "total": 0, "correctos": 0, "incorrectos": 0}
        semanas[key]["total"] += 1
        if e.get("correcto") is True:
            semanas[key]["correctos"] += 1
        elif e.get("correcto") is False:
            semanas[key]["incorrectos"] += 1
    por_semana = sorted(semanas.values(), key=lambda s: (s["anio"], s["semana"]))

    # Errores frecuentes
    error_count = {}
    for e in evals:
        for err in e.get("errores", []):
            error_count[err] = error_count.get(err, 0) + 1
    errores_frecuentes = sorted(error_count.items(), key=lambda x: -x[1])[:5]

    # Recomendaciones (últimas únicas)
    recomendaciones_set = []
    seen = set()
    for e in reversed(evals):
        for r in e.get("recomendaciones", []):
            if r not in seen:
                recomendaciones_set.append(r)
                seen.add(r)
            if len(recomendaciones_set) >= 5:
                break

    # Por categoría
    categorias = {}
    for e in practicos:
        cat = e.get("categoria", "general")
        if cat not in categorias:
            categorias[cat] = {"total": 0, "correctos": 0}
        categorias[cat]["total"] += 1
        if e.get("correcto"):
            categorias[cat]["correctos"] += 1

    return {
        "total_ejercicios": len(evals),
        "practicos": {
            "total": len(practicos),
            "correctos": p_correctos,
            "incorrectos": len(practicos) - p_correctos,
            "puntuacion_media": round(sum(p_puntuaciones) / len(p_puntuaciones), 1) if p_puntuaciones else None,
        },
        "teoricos": {
            "total": len(teoricos),
            "puntuacion_media_contenido": round(sum(t_contenido) / len(t_contenido), 1) if t_contenido else None,
            "puntuacion_media_formal": round(sum(t_formal_scores) / len(t_formal_scores), 1) if t_formal_scores else None,
        },
        "por_semana": por_semana,
        "errores_frecuentes": [{"tipo": t, "frecuencia": f} for t, f in errores_frecuentes],
        "recomendaciones": recomendaciones_set,
        "categorias": categorias,
    }


def progreso_global(username: str, num_temas: int = 6) -> dict:
    """Devuelve un resumen del progreso en todos los temas.

    Returns:
        dict con temas: [{tema_id, total, correctos, puntuacion_media}]
        y estadisticas_globales.
    """
    temas = []
    total_global = 0
    correctos_global = 0

    for i in range(1, num_temas + 1):
        p = progreso_tema(username, i)
        total = p["total_ejercicios"]
        correctos = p["practicos"]["correctos"]
        total_global += total
        correctos_global += correctos
        temas.append({
            "tema_id": i,
            "total_ejercicios": total,
            "correctos": correctos,
            "puntuacion_media": p["practicos"]["puntuacion_media"],
            "errores_frecuentes": p["errores_frecuentes"][:3],
        })

    return {
        "temas": temas,
        "total_global": total_global,
        "correctos_global": correctos_global,
        "porcentaje_global": round(correctos_global / total_global * 100, 1) if total_global > 0 else None,
    }


# ═══════════════════════════════════════════════════════════════════════
# FORMATEO PARA CHAT
# ═══════════════════════════════════════════════════════════════════════

def formatear_progreso(username: str, tema_id: int) -> str:
    """Formatea el progreso de un tema en markdown para el chat."""
    p = progreso_tema(username, tema_id)

    if p["total_ejercicios"] == 0:
        return "No hay autoevaluaciones registradas en este tema todavía."

    lineas = [f"## Progreso en el Tema {tema_id}\n"]

    # Cuantitativo
    lineas.append(f"**Total de ejercicios:** {p['total_ejercicios']}")

    if p["practicos"]["total"] > 0:
        pr = p["practicos"]
        lineas.append(f"\n### Ejercicios prácticos")
        lineas.append(f"- Realizados: {pr['total']}")
        lineas.append(f"- Correctos: {pr['correctos']} ({round(pr['correctos']/pr['total']*100)}%)")
        lineas.append(f"- Incorrectos: {pr['incorrectos']}")
        if pr["puntuacion_media"] is not None:
            lineas.append(f"- Puntuación media: {pr['puntuacion_media']}%")

    if p["teoricos"]["total"] > 0:
        te = p["teoricos"]
        lineas.append(f"\n### Ejercicios teóricos")
        lineas.append(f"- Realizados: {te['total']}")
        if te["puntuacion_media_contenido"] is not None:
            lineas.append(f"- Contenido (media): {te['puntuacion_media_contenido']}%")
        if te["puntuacion_media_formal"] is not None:
            lineas.append(f"- Aspectos formales (media): {te['puntuacion_media_formal']}%")

    # Evolución por semana
    if p["por_semana"]:
        lineas.append(f"\n### Evolución semanal")
        for s in p["por_semana"][-4:]:  # últimas 4 semanas
            barra = '🟢' * s["correctos"] + '🔴' * s["incorrectos"]
            lineas.append(f"- Semana {s['semana']}: {barra} ({s['total']} ejercicios)")

    # Errores frecuentes
    if p["errores_frecuentes"]:
        lineas.append(f"\n### Áreas con más fallos")
        for e in p["errores_frecuentes"]:
            lineas.append(f"- **{e['tipo']}**: {e['frecuencia']} error(es)")

    # Por categoría
    if p["categorias"]:
        lineas.append(f"\n### Desglose por tipo de ejercicio")
        for cat, datos in p["categorias"].items():
            pct = round(datos["correctos"] / datos["total"] * 100) if datos["total"] > 0 else 0
            lineas.append(f"- {cat}: {datos['correctos']}/{datos['total']} ({pct}%)")

    # Recomendaciones
    if p["recomendaciones"]:
        lineas.append(f"\n### Recomendaciones")
        for r in p["recomendaciones"]:
            lineas.append(f"- {r}")

    return "\n".join(lineas)


# ═══════════════════════════════════════════════════════════════════════
# EVALUACIÓN TEÓRICA (prompt para LLM)
# ═══════════════════════════════════════════════════════════════════════

def generar_prompt_evaluacion_teorica(pregunta: str, respuesta_alumno: str,
                                      respuesta_esperada: str = '') -> str:
    """Genera el prompt del sistema para que el LLM evalúe una respuesta teórica.

    El LLM debe devolver un JSON con la evaluación de contenido y formal.
    """
    return f"""Eres un evaluador de respuestas de estudiantes de fonología del español.
Evalúa la siguiente respuesta del alumno con criterios estrictos pero justos.

PREGUNTA: {pregunta}

RESPUESTA DEL ALUMNO:
{respuesta_alumno}

{('RESPUESTA ESPERADA (referencia):' + chr(10) + respuesta_esperada + chr(10)) if respuesta_esperada else ''}

Debes evaluar DOS aspectos y responder SOLO con JSON válido (sin comentarios):

{{
  "contenido": {{
    "correspondencia": <0-100>,
    "elementos_presentes": ["concepto1", "concepto2"],
    "elementos_faltantes": ["concepto3"],
    "errores_conceptuales": ["error1"],
    "comentario": "Breve comentario sobre el contenido"
  }},
  "formal": {{
    "ortografia": <0-100>,
    "gramatica": <0-100>,
    "redaccion": <0-100>,
    "observaciones": ["observación1"]
  }},
  "puntuacion_global": <0-100>,
  "recomendaciones": ["recomendación1"],
  "consultar_docente": <true si la respuesta es ambigua y necesita revisión humana>
}}

Criterios:
- CONTENIDO: ¿menciona los conceptos clave? ¿hay errores conceptuales? ¿corresponde a lo esperado?
- ORTOGRAFÍA: tildes, uso correcto de mayúsculas, errores tipográficos
- GRAMÁTICA: concordancia, uso de preposiciones, construcción de frases
- REDACCIÓN: claridad, coherencia, organización de ideas
- Si la respuesta es discutible o necesita interpretación humana, pon consultar_docente: true"""
