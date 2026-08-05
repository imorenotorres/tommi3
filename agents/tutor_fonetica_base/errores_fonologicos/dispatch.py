"""
Dispatch de errores fonológicos para el agente LALI.

Detecta peticiones del usuario relacionadas con errores fonológicos
y genera respuestas programáticas o contexto para el LLM.
"""

import re
import json
from .generador import generar_errores, TODOS_LOS_ERRORES
from .analizador import analizar
from .ejercicios import generar_ejercicio, corregir_ejercicio
from .ejercicios_transcripcion import (
    generar_ejercicio_transcripcion, corregir_ejercicio_transcripcion,
    clasificar_nivel_transcripcion, resumen_niveles
)
from .silaba import parsear_silabas, reconstruir_transcripcion
from .inventario import clasificar_error_sistemico


# ═══════════════════════════════════════════════════════════════════════
# DETECCIÓN DE INTENCIÓN
# ═══════════════════════════════════════════════════════════════════════

def detectar_peticion_errores(msg: str) -> dict | None:
    """
    Detecta si el usuario pide algo relacionado con errores fonológicos.

    Returns:
        dict con 'accion' y parámetros, o None si no es una petición de errores.
    """
    msg_lower = msg.lower().strip()

    # ── Pedir ejercicio de TRANSCRIPCIÓN ─────────────────────────────
    transcripcion_ej_patterns = [
        r'ejercicio\s+(?:de\s+)?transcripci[oó]n',
        r'(?:dame|genera|hazme|quiero)\s+(?:un\s+)?ejercicio\s+(?:de\s+)?transcripci[oó]n',
        r'(?:practicar|práctica|entrenar)\s+(?:con\s+)?transcripci[oó]n(?:es)?',
        r'(?:quiero|necesito)\s+practicar\s+transcripci[oó]n',
    ]
    for pattern in transcripcion_ej_patterns:
        if re.search(pattern, msg_lower):
            nivel = _extraer_nivel_transcripcion(msg_lower)
            tipo = _extraer_tipo_transcripcion(msg_lower)
            habla = _extraer_habla_transcripcion(msg_lower)
            num_items = _extraer_num_items(msg_lower)
            return {'accion': 'ejercicio_transcripcion', 'nivel': nivel,
                    'tipo': tipo, 'habla': habla, 'num_items': num_items}

    # ── Pedir ejercicio de ERRORES ────────────────────────────────────
    ejercicio_patterns = [
        r'(?:dame|genera|hazme|quiero|pon(?:me)?)\s+(?:un\s+)?ejercicio',
        r'(?:practicar|práctica|entrenar)\s+(?:con\s+)?(?:errores|ejercicio)',
        r'ejercicio\s+(?:de\s+)?(?:errores?\s+)?(?:fonológico|sistémico|de\s+sílaba|de\s+palabra)',
        r'(?:quiero|necesito)\s+practicar\s+(?:errores|fonolog)',
    ]
    for pattern in ejercicio_patterns:
        if re.search(pattern, msg_lower):
            tipo = _extraer_tipo_error(msg_lower)
            nivel = _extraer_nivel(msg_lower)
            return {'accion': 'ejercicio', 'tipo': tipo, 'nivel': nivel}

    # ── Analizar un caso ───────────────────────────────────────────────
    analisis_patterns = [
        r'(?:analiza|analizar|compara|comparar)\s+.*(?:objetivo|produce|producido|debería)',
        r'(?:objetivo|target)\s*[:=]\s*[/\[]?([^\n]+)',
        r'(?:informe|report)\s+(?:de\s+)?(?:errores?\s+)?(?:fonológico|del\s+caso)',
    ]
    for pattern in analisis_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            objetivo, producido = _extraer_par_transcripciones(msg)
            if objetivo and producido:
                return {'accion': 'analizar', 'objetivo': objetivo, 'producido': producido}

    # ── Pedir explicación de tipo de error ─────────────────────────────
    tipo_patterns = [
        r'(?:qué\s+es|explica|explícame|describe)\s+(?:la\s+|el\s+|un\s+|una\s+)?'
        r'(sonorizaci[oó]n|ensordecimiento|leni[ct]i[oó]n|fortici[oó]n|'
        r'adelantamiento|posteriorizaci[oó]n|nasalizaci[oó]n|desnasalizaci[oó]n|'
        r'asimilaci[oó]n|met[aá]tesis|omisi[oó]n\s+de\s+(?:ataque|coda|s[ií]laba)|'
        r'simplificaci[oó]n\s+de\s+(?:ataque|n[uú]cleo)|'
        r'error(?:es)?\s+sist[eé]mico|error(?:es)?\s+de\s+s[ií]laba|error(?:es)?\s+de\s+palabra|'
        r'error(?:es)?\s+r[ií]tmico|pausa(?:s)?\s+indebida|titubeo|autocorrecci[oó]n|muletilla)',
    ]
    for pattern in tipo_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            return {'accion': 'explicar_tipo', 'tipo': match.group(1)}

    # ── Clasificar un error concreto ───────────────────────────────────
    clasificar_patterns = [
        r'(?:clasifica|clasifícame|qué\s+tipo\s+de\s+error)\s+.*?/([a-zθɲʝɾβðɣʃtʃ]+)/\s*(?:>|→|a)\s*/([a-zθɲʝɾβðɣʃtʃ]+)/',
        r'/([a-zθɲʝɾβðɣʃtʃ]+)/\s*(?:>|→)\s*/([a-zθɲʝɾβðɣʃtʃ]+)/\s*(?:qué|que)\s+(?:tipo|error)',
    ]
    for pattern in clasificar_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            return {'accion': 'clasificar', 'objetivo': match.group(1), 'producido': match.group(2)}

    return None


# ═══════════════════════════════════════════════════════════════════════
# DISPATCH — genera respuestas programáticas
# ═══════════════════════════════════════════════════════════════════════

def dispatch_errores(peticion: dict, session_state: dict = None) -> str | None:
    """
    Procesa una petición de errores fonológicos y devuelve una respuesta.

    Args:
        peticion: dict de detectar_peticion_errores()
        session_state: estado de sesión (para recordar ejercicios en curso)

    Returns:
        Respuesta en markdown, o None si no puede procesarse.
    """
    accion = peticion.get('accion')

    if accion == 'ejercicio_transcripcion':
        return _dispatch_ejercicio_transcripcion(peticion, session_state)
    elif accion == 'ejercicio':
        return _dispatch_ejercicio(peticion, session_state)
    elif accion == 'analizar':
        return _dispatch_analizar(peticion)
    elif accion == 'clasificar':
        return _dispatch_clasificar(peticion)
    elif accion == 'explicar_tipo':
        return None  # dejar que el LLM explique usando el documento como contexto

    return None


def _dispatch_ejercicio(peticion: dict, session_state: dict = None) -> str:
    """Genera un ejercicio y lo formatea para el chat."""
    tipo = peticion.get('tipo')
    nivel = peticion.get('nivel', 'basico')

    import random
    seed = random.randint(0, 99999)
    ejercicio = generar_ejercicio(tipo=tipo, nivel=nivel, num_items=5, seed=seed)

    # Guardar en sesión para posterior corrección
    if session_state is not None:
        session_state['ejercicio_actual'] = ejercicio
        session_state['ejercicio_seed'] = seed

    # Formatear para el chat
    lineas = []
    lineas.append(ejercicio['instrucciones'])
    lineas.append("\n---\n")

    for i, item in enumerate(ejercicio['items'], 1):
        lineas.append(f"**{i}. {item['ortografia']}**")
        lineas.append(f"- Objetivo: /{item['objetivo']}/")
        lineas.append(f"- Producido: /{item['producido']}/")
        lineas.append(f"- Número de errores: {item['num_errores']}")
        lineas.append("")

    lineas.append("---\n")
    lineas.append("**Responde copiando esta plantilla y completándola:**\n")
    lineas.append("```")
    for i, item in enumerate(ejercicio['items'], 1):
        lineas.append(f"{i}. ")
    lineas.append("```")
    lineas.append("\n*Ejemplo: 1. sonorización, 2. omisión de coda*")
    lineas.append("")

    return '\n'.join(lineas)


def _dispatch_ejercicio_transcripcion(peticion: dict, session_state: dict = None) -> str:
    """Genera un ejercicio de transcripción fonológica/fonética."""
    nivel = peticion.get('nivel', 1)
    tipo = peticion.get('tipo', 'fonologica')
    habla = peticion.get('habla', 'tipica')
    num_items = peticion.get('num_items', 6)

    import random
    seed = random.randint(0, 99999)
    ejercicio = generar_ejercicio_transcripcion(
        nivel=nivel, num_items=num_items, seed=seed, tipo=tipo, habla=habla)

    # Guardar en sesión para posterior corrección
    if session_state is not None:
        session_state['ejercicio_actual'] = ejercicio
        session_state['ejercicio_tipo'] = 'transcripcion'
        session_state['ejercicio_seed'] = seed

    # Formatear para el chat
    lineas = []
    lineas.append(ejercicio['instrucciones'])
    lineas.append("\n---\n")

    # Items
    for i, item in enumerate(ejercicio['items'], 1):
        if habla == 'errores' and 'producido' in item:
            ort_error = item.get('ortografia_error', item['ortografia'])
            errores_desc = ', '.join(e['descripcion'] for e in item.get('errores', []))
            lineas.append(f"**{i}.** Objetivo: **{item['ortografia']}** → "
                          f"Producido: "
                          f"<span style=\"color:#dc2626;font-weight:600;\">\"{ort_error}\"</span>")
            if errores_desc:
                lineas.append(f"   <span style=\"font-size:12px;color:#64748b;\">({errores_desc})</span>")
        else:
            lineas.append(f"**{i}. {item['ortografia']}**")
        lineas.append("")

    lineas.append("---\n")

    # Template
    lineas.append("**Responde copiando esta plantilla y completándola:**\n")
    lineas.append("```")
    for i, item in enumerate(ejercicio['items'], 1):
        if tipo == 'fonetica':
            lineas.append(f"{i}. /    / [    ]")
        else:
            lineas.append(f"{i}. /    /")
    lineas.append("```")

    lineas.append("")

    return '\n'.join(lineas)


def _dispatch_analizar(peticion: dict) -> str:
    """Analiza un par objetivo/producido y devuelve el informe."""
    objetivo = peticion['objetivo']
    producido = peticion['producido']

    try:
        informe = analizar(objetivo, producido)
        return informe['resumen']
    except Exception as e:
        return f"Error al analizar: {e}. Asegúrate de usar transcripción fonológica válida."


def _dispatch_clasificar(peticion: dict) -> str:
    """Clasifica un error fonema → fonema."""
    objetivo = peticion['objetivo']
    producido = peticion['producido']

    try:
        errores = clasificar_error_sistemico(objetivo, producido)
        if not errores:
            return f"/{objetivo}/ → /{producido}/: No se detecta un error sistémico (los fonemas son idénticos o no están en el inventario)."

        lineas = [f"**Análisis del error /{objetivo}/ → /{producido}/:**\n"]
        for e in errores:
            lineas.append(f"- **{e['rasgo'].capitalize()}**: {e['descripcion']}")
        return '\n'.join(lineas)
    except KeyError as e:
        return f"Fonema no reconocido: {e}. Usa notación IPA (p, t, k, b, d, g, θ, s, f, x, m, n, ɲ, ʝ, l, ɾ, r, tʃ)."


def dispatch_correccion(ejercicio: dict, respuestas_texto: str,
                        ejercicio_tipo: str = 'errores',
                        session_state: dict = None) -> tuple[str, list[str]]:
    """
    Corrige las respuestas del alumno a un ejercicio.

    Returns:
        tuple (texto_correccion, lista_palabras_incorrectas)
    """
    # Delegate to transcription correction if needed
    if ejercicio_tipo == 'transcripcion':
        return corregir_ejercicio_transcripcion(ejercicio, respuestas_texto)

    respuestas_alumno = _parsear_respuestas_alumno(respuestas_texto, len(ejercicio['items']))

    lineas = []
    lineas.append("## Corrección del ejercicio\n")

    total_errores = 0
    aciertos_total = 0
    fallos_total = 0
    inventados_total = 0

    for i, item in enumerate(ejercicio['items']):
        num = i + 1
        lineas.append(f"**{num}. {item['ortografia']}**")
        lineas.append(f"- Objetivo: /{item['objetivo']}/")
        lineas.append(f"- Producido: /{item['producido']}/")

        errores_reales = {e['tipo'] for e in item['errores']}
        total_errores += len(errores_reales)

        # Get student answers for this item
        errores_alumno = respuestas_alumno.get(i, set())

        if not errores_reales:
            lineas.append(f"  - (sin errores aplicados)")
            if errores_alumno:
                inventados_total += len(errores_alumno)
                for ea in errores_alumno:
                    lineas.append(f"  - ❌ Has dicho **{_nombre_legible(ea)}** — pero no hay errores en esta palabra")
            lineas.append("")
            continue

        aciertos = errores_reales & errores_alumno
        no_encontrados = errores_reales - errores_alumno
        inventados = errores_alumno - errores_reales

        aciertos_total += len(aciertos)
        fallos_total += len(no_encontrados)
        inventados_total += len(inventados)

        # Show correct answers with student's result
        for e in item['errores']:
            if e['tipo'] in aciertos:
                lineas.append(f"  - ✅ {e['descripcion']} — **correcto**")
            else:
                lineas.append(f"  - ❌ {e['descripcion']} — **no identificado**")

        for ea in inventados:
            lineas.append(f"  - ❌ Has dicho **{_nombre_legible(ea)}** — no es el error correcto")

        if not errores_alumno:
            lineas.append(f"  - ⚠️ No has respondido a esta palabra")

        lineas.append("")

    # Summary — objective data only, no value judgments
    lineas.append("---\n")
    lineas.append("### Resultado\n")
    if total_errores > 0:
        puntuacion = round(aciertos_total / total_errores * 100, 1)
        lineas.append(f"- Errores identificados correctamente: {aciertos_total}/{total_errores} ({puntuacion}%)")
    else:
        puntuacion = 100
        lineas.append(f"- No había errores que identificar.")

    if fallos_total > 0:
        lineas.append(f"- Errores no identificados: {fallos_total}")
    if inventados_total > 0:
        lineas.append(f"- Respuestas incorrectas: {inventados_total}")

    lineas.append("")

    # Track exercise history in session
    lineas.append(_registrar_y_mostrar_progreso(puntuacion, session_state))

    return '\n'.join(lineas), []  # error exercises don't track incorrect words yet


# ═══════════════════════════════════════════════════════════════════════
# UTILIDADES INTERNAS
# ═══════════════════════════════════════════════════════════════════════

def es_respuesta_ejercicio(msg: str, session_state: dict) -> bool:
    """
    Cuando hay un ejercicio activo, SIEMPRE devuelve True.
    El alumno debe abandonar explícitamente el ejercicio para volver al chat.
    """
    if not session_state or not session_state.get('ejercicio_actual'):
        return False
    return True


def es_abandono_ejercicio(msg: str) -> bool:
    """Detecta si el alumno quiere abandonar el ejercicio en curso."""
    msg_lower = msg.lower().strip()
    return any(t in msg_lower for t in [
        'dejar ejercicio', 'abandonar ejercicio', 'salir del ejercicio',
        'no quiero seguir', 'cambiar de tema', 'otra cosa',
        'dejar el ejercicio', 'abandonar el ejercicio', 'salir ejercicio',
        'sí, dejar', 'si, dejar', 'sí dejar', 'si dejar',
    ])


# Map from user-friendly names (with accents, variations) to internal tipo keys
_NOMBRES_ERRORES_MAP = {
    'sonorizacion': 'sonorizacion',
    'sonorización': 'sonorizacion',
    'ensordecimiento': 'ensordecimiento',
    'adelantamiento': 'adelantamiento',
    'posteriorización': 'posteriorizacion',
    'posteriorizacion': 'posteriorizacion',
    'posterioracion': 'posteriorizacion',
    'nasalización': 'nasalizacion',
    'nasalizacion': 'nasalizacion',
    'desnasalización': 'desnasalizacion',
    'desnasalizacion': 'desnasalizacion',
    'omisión de ataque': 'omision_ataque',
    'omision de ataque': 'omision_ataque',
    'simplificación de ataque': 'simplificacion_ataque',
    'simplificacion de ataque': 'simplificacion_ataque',
    'simplificación de núcleo': 'simplificacion_nucleo',
    'simplificacion de nucleo': 'simplificacion_nucleo',
    'simplificación del núcleo': 'simplificacion_nucleo',
    'omisión de coda': 'omision_coda',
    'omision de coda': 'omision_coda',
    'asimilación regresiva': 'asimilacion_regresiva',
    'asimilacion regresiva': 'asimilacion_regresiva',
    'asimilación progresiva': 'asimilacion_progresiva',
    'asimilacion progresiva': 'asimilacion_progresiva',
    'metátesis': 'metatesis',
    'metatesis': 'metatesis',
    'omisión de sílaba átona': 'omision_silaba_atona',
    'omision de silaba atona': 'omision_silaba_atona',
    'omisión de sílaba tónica': 'omision_silaba_tonica',
    'omision de silaba tonica': 'omision_silaba_tonica',
    'lenición': 'sonorizacion',
    'lenicion': 'sonorizacion',
    'fortición': 'ensordecimiento',
    'forticion': 'ensordecimiento',
}

_NOMBRES_ERRORES = set(_NOMBRES_ERRORES_MAP.keys())

# Reverse map: internal tipo -> user-friendly name
_NOMBRES_LEGIBLES = {
    'sonorizacion': 'Sonorización',
    'ensordecimiento': 'Ensordecimiento',
    'adelantamiento': 'Adelantamiento',
    'posteriorizacion': 'Posteriorización',
    'nasalizacion': 'Nasalización',
    'desnasalizacion': 'Desnasalización',
    'omision_ataque': 'Omisión de ataque',
    'simplificacion_ataque': 'Simplificación de ataque',
    'simplificacion_nucleo': 'Simplificación de núcleo',
    'omision_coda': 'Omisión de coda',
    'asimilacion_regresiva': 'Asimilación regresiva',
    'asimilacion_progresiva': 'Asimilación progresiva',
    'metatesis': 'Metátesis',
    'omision_silaba_atona': 'Omisión de sílaba átona',
    'omision_silaba_tonica': 'Omisión de sílaba tónica',
}


def _nombre_legible(tipo: str) -> str:
    """Converts internal error type to user-friendly name."""
    return _NOMBRES_LEGIBLES.get(tipo, tipo)


def _parsear_respuestas_alumno(texto: str, num_items: int) -> dict[int, set[str]]:
    """
    Parse free-text student answers into structured format.

    Supports patterns like:
      "1. sonorización, 2. omisión de coda"
      "1: sonorización\n2: ensordecimiento"
      "1) sonorización 2) omisión de ataque"

    Returns:
        dict mapping item index (0-based) to set of error type keys
    """
    respuestas = {}
    texto_lower = texto.lower().strip()

    # Split by item number patterns
    # Match "1. ...", "1: ...", "1) ...", "1- ..."
    partes = re.split(r'(?:^|\n|,\s*|;\s*)(\d+)\s*[.:\-)\]]\s*', texto_lower)

    # partes alternates: [pre, num, text, num, text, ...]
    for i in range(1, len(partes) - 1, 2):
        try:
            item_num = int(partes[i])
            item_texto = partes[i + 1].strip()
        except (ValueError, IndexError):
            continue

        if 1 <= item_num <= num_items:
            errores = set()
            # Try to match error names (longest first to avoid partial matches)
            for nombre in sorted(_NOMBRES_ERRORES, key=len, reverse=True):
                if nombre in item_texto:
                    errores.add(_NOMBRES_ERRORES_MAP[nombre])
                    # Remove matched name to avoid double-matching
                    item_texto = item_texto.replace(nombre, '', 1)
            respuestas[item_num - 1] = errores  # 0-based index

    return respuestas


def _extraer_tipo_transcripcion(msg: str) -> str:
    """Extrae si el ejercicio es 'fonologica' o 'fonetica' (fonológica + fonética)."""
    if any(t in msg for t in ['fonética', 'fonetica', 'fonológica y fonética',
                               'fonologica y fonetica']):
        return 'fonetica'
    return 'fonologica'


def _extraer_habla_transcripcion(msg: str) -> str:
    """Extrae si el ejercicio es 'tipica' o 'errores'."""
    if any(t in msg for t in ['error', 'errores', 'habla con error',
                               'habla atípica', 'habla atipica']):
        return 'errores'
    return 'tipica'


def _extraer_num_items(msg: str) -> int:
    """Extrae el número de palabras/ítems solicitado. Por defecto 6."""
    match = re.search(r'(?:con\s+)?(\d+)\s+(?:palabras?|ítems?|items?|elementos?)', msg)
    if match:
        n = int(match.group(1))
        if 1 <= n <= 20:
            return n
    return 6


def _extraer_nivel_transcripcion(msg: str) -> int:
    """Extrae el nivel de transcripción solicitado (1-6)."""
    # Check for explicit level number
    match = re.search(r'nivel\s*(\d)', msg)
    if match:
        n = int(match.group(1))
        if 1 <= n <= 8:
            return n

    if any(t in msg for t in ['transparente', 'sin divergen', 'fácil', 'facil', 'básico', 'basico']):
        return 1
    if any(t in msg for t in ['divergencia', 'simple']):
        return 2
    if any(t in msg for t in ['dígrafo', 'digrafo']):
        return 3
    if any(t in msg for t in ['contextual']):
        return 4
    if any(t in msg for t in ['diptongo', 'h muda', 'hiato']):
        return 5
    if any(t in msg for t in ['complej', 'difícil', 'dificil', 'avanzado']):
        return 6
    return 1  # default: start from the easiest


EJERCICIOS_PARA_DOMINIO = 5  # número de ejercicios con ≥80% para considerar dominio

def _registrar_y_mostrar_progreso(puntuacion: float, session_state: dict = None) -> str:
    """
    Registra el resultado del ejercicio en el historial de la sesión
    y muestra el progreso objetivo del alumno.
    """
    if session_state is None:
        session_state = {}

    # Inicializar historial si no existe
    if 'historial_ejercicios' not in session_state:
        session_state['historial_ejercicios'] = []

    session_state['historial_ejercicios'].append(puntuacion)
    historial = session_state['historial_ejercicios']

    # Contar ejercicios con ≥80% de aciertos
    buenos = sum(1 for p in historial if p >= 80)
    total = len(historial)

    lineas = []
    lineas.append(f"### Progreso en esta sesión\n")
    lineas.append(f"- Ejercicios realizados: {total}")
    lineas.append(f"- Ejercicios con ≥80% de aciertos: {buenos}/{EJERCICIOS_PARA_DOMINIO}")

    # Mostrar historial como barra visual
    barra = " ".join(f"{'🟢' if p >= 80 else '🟡' if p >= 50 else '🔴'}" for p in historial)
    lineas.append(f"- Historial: {barra}")
    lineas.append("")

    if buenos >= EJERCICIOS_PARA_DOMINIO:
        lineas.append(f"Has completado {EJERCICIOS_PARA_DOMINIO} ejercicios con buen resultado. "
                      f"Puedes pasar a practicar con un tipo de error diferente o un nivel más alto.")
    else:
        faltan = EJERCICIOS_PARA_DOMINIO - buenos
        lineas.append(f"Necesitas {faltan} ejercicio(s) más con ≥80% de aciertos para completar esta práctica. "
                      f"Pide otro ejercicio del mismo tipo para seguir practicando.")

    return '\n'.join(lineas)


def _extraer_tipo_error(msg: str) -> str | None:
    """Extrae el tipo de error solicitado del mensaje."""
    if any(t in msg for t in ['sistémico', 'sistemico', 'fonema', 'sonorización', 'ensordecimiento']):
        return 'sistemico'
    if any(t in msg for t in ['sílaba', 'silaba', 'ataque', 'coda', 'núcleo', 'nucleo']):
        return 'silaba'
    if any(t in msg for t in ['palabra', 'asimilación', 'asimilacion', 'metátesis', 'metatesis']):
        return 'palabra'
    if any(t in msg for t in ['combinado', 'mixto', 'todo', 'todos']):
        return None  # todos
    return None  # por defecto: sistémico en nivel básico, todos en avanzado


def _extraer_nivel(msg: str) -> str:
    """Extrae el nivel de dificultad del mensaje."""
    if any(t in msg for t in ['fácil', 'facil', 'básico', 'basico', 'sencillo']):
        return 'basico'
    if any(t in msg for t in ['intermedio', 'medio', 'normal']):
        return 'intermedio'
    if any(t in msg for t in ['difícil', 'dificil', 'avanzado', 'complejo']):
        return 'avanzado'
    return 'basico'


def _extraer_par_transcripciones(msg: str) -> tuple[str | None, str | None]:
    """Extrae un par objetivo/producido del mensaje."""
    # Buscar patrones como "objetivo: /X/ producido: /Y/"
    obj_match = re.search(r'(?:objetivo|target|correcto)\s*[:=]\s*/?([^/\n]+)/?', msg, re.IGNORECASE)
    prod_match = re.search(r'(?:producido|producción|produce|real)\s*[:=]\s*/?([^/\n]+)/?', msg, re.IGNORECASE)

    if obj_match and prod_match:
        return obj_match.group(1).strip(), prod_match.group(1).strip()

    # Buscar patrón /X/ > /Y/ o /X/ → /Y/
    par_match = re.search(r'/?([^/]+)/?\s*(?:>|→|->)\s*/?([^/\n]+)/?', msg)
    if par_match:
        return par_match.group(1).strip(), par_match.group(2).strip()

    return None, None
