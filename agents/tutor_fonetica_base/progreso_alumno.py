"""
Gestión del progreso del alumno en ejercicios de transcripción fonológica.

Almacena el historial de ejercicios por alumno en archivos JSON individuales.
Permite sugerir el nivel adecuado y hacer seguimiento.
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Directorio de progreso por defecto (se puede cambiar con set_progress_dir).
# Cada agente concreto debe llamar a set_progress_dir() con su propio directorio.
_PROGRESS_DIR = Path(__file__).parent / "progress"
_PROGRESS_DIR.mkdir(exist_ok=True)


def set_progress_dir(path: Path | str):
    """Configura el directorio donde se almacenan los archivos de progreso.
    Cada agente concreto debe llamar a esta función con su directorio de datos."""
    global _PROGRESS_DIR
    _PROGRESS_DIR = Path(path)
    _PROGRESS_DIR.mkdir(exist_ok=True)

# Umbral para considerar un nivel "superado"
UMBRAL_SUPERADO = 80  # ≥80% (como máximo 1 error en 6 items)
NUM_EJERCICIOS_SUPERADO = 4  # al menos 4 ejercicios buenos para superar


def _ruta_alumno(username: str) -> Path:
    """Devuelve la ruta del archivo de progreso de un alumno."""
    # Sanitize username for filesystem
    safe = username.replace('/', '_').replace('\\', '_').replace('..', '_')
    return _PROGRESS_DIR / f"{safe}.json"


def cargar_progreso(username: str) -> dict:
    """Carga el progreso de un alumno. Devuelve dict vacío si no existe."""
    ruta = _ruta_alumno(username)
    if not ruta.exists():
        return {}
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def guardar_progreso(username: str, progreso: dict):
    """Guarda el progreso de un alumno."""
    ruta = _ruta_alumno(username)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(progreso, f, ensure_ascii=False, indent=2)
        f.write('\n')


def registrar_resultado(username: str, nivel: int, puntuacion: float, num_items: int,
                        modo: str = 'fonologica_tipica'):
    """
    Registra el resultado de un ejercicio completado.

    Args:
        username: identificador del alumno
        nivel: nivel del ejercicio (1-6)
        puntuacion: porcentaje de aciertos (0-100)
        num_items: número de items en el ejercicio
        modo: 'fonologica_tipica', 'fonologica_errores',
              'fonetica_tipica', 'fonetica_errores'
    """
    progreso = cargar_progreso(username)

    # Initialize structure if needed
    if modo not in progreso:
        progreso[modo] = {}

    # Backwards compatibility: old 'transcripcion' key = 'fonologica_tipica'
    if modo == 'fonologica_tipica' and 'transcripcion' in progreso and modo not in progreso:
        progreso[modo] = progreso['transcripcion']

    nivel_key = str(nivel)
    if nivel_key not in progreso[modo]:
        progreso[modo][nivel_key] = {
            'intentos': [],
            'superado': False,
            'mejor_puntuacion': 0,
        }

    nivel_data = progreso[modo][nivel_key]
    nivel_data['intentos'].append({
        'fecha': datetime.now().isoformat(),
        'puntuacion': puntuacion,
        'num_items': num_items,
    })

    # Keep only last 20 attempts per level
    if len(nivel_data['intentos']) > 20:
        nivel_data['intentos'] = nivel_data['intentos'][-20:]

    # Update best score
    if puntuacion > nivel_data['mejor_puntuacion']:
        nivel_data['mejor_puntuacion'] = puntuacion

    # Check if level is "superado" (≥80% in at least NUM_EJERCICIOS_SUPERADO exercises)
    buenos = [i for i in nivel_data['intentos'] if i['puntuacion'] >= UMBRAL_SUPERADO]
    nivel_data['superado'] = len(buenos) >= NUM_EJERCICIOS_SUPERADO

    guardar_progreso(username, progreso)


def nivel_recomendado(username: str, modo: str = 'fonologica_tipica') -> int:
    """
    Devuelve el nivel recomendado para el alumno en un modo dado.
    Es el nivel más bajo no superado (o 6 si todos están superados).
    """
    progreso = cargar_progreso(username)
    modo_data = progreso.get(modo, progreso.get('transcripcion', {}))

    for nivel in range(1, 7):
        nivel_data = modo_data.get(str(nivel), {})
        if not nivel_data.get('superado', False):
            return nivel

    return 6


def resumen_progreso(username: str, modo: str = 'fonologica_tipica') -> dict | None:
    """
    Genera info sobre el estado del alumno en un modo dado.

    Returns:
        dict con niveles_superados, nivel_actual, etc., o None si no hay datos.
    """
    progreso = cargar_progreso(username)
    modo_data = progreso.get(modo, progreso.get('transcripcion', {}))

    if not modo_data:
        return None

    niveles_superados = []
    nivel_actual = None
    ultimo_intento = None

    for nivel in range(1, 7):
        nivel_data = modo_data.get(str(nivel), {})
        if nivel_data.get('superado', False):
            niveles_superados.append(nivel)
        elif nivel_data.get('intentos'):
            nivel_actual = nivel
            ultimo_intento = nivel_data['intentos'][-1]
            break
        else:
            nivel_actual = nivel
            break

    if not nivel_actual and not niveles_superados:
        return None

    return {
        'niveles_superados': niveles_superados,
        'nivel_actual': nivel_actual,
        'ultimo_intento': ultimo_intento,
        'nivel_recomendado': nivel_recomendado(username, modo),
    }


_MODO_NOMBRES = {
    'fonologica_tipica': 'transcripción fonológica',
    'fonologica_errores': 'transcripción fonológica (habla con errores)',
    'fonetica_tipica': 'transcripción fonológica y fonética',
    'fonetica_errores': 'transcripción fonológica y fonética (habla con errores)',
}


def mensaje_bienvenida_ejercicios(username: str, modo: str = 'fonologica_tipica') -> str | None:
    """
    Genera un mensaje de bienvenida contextualizado al progreso del alumno.
    Devuelve None si no hay historial (primer uso).
    """
    info = resumen_progreso(username, modo)
    if info is None:
        return None

    niveles_sup = info['niveles_superados']
    nivel_act = info['nivel_actual']
    ultimo = info['ultimo_intento']
    recomendado = info['nivel_recomendado']

    from tutor_fonetica_base.errores_fonologicos.ejercicios_transcripcion import _NIVEL_NOMBRES
    modo_nombre = _MODO_NOMBRES.get(modo, 'transcripción')

    if not niveles_sup and not ultimo:
        return None

    if niveles_sup and nivel_act:
        max_superado = max(niveles_sup)
        nombre_siguiente = _NIVEL_NOMBRES.get(recomendado, '')
        if ultimo:
            ultima_punt = ultimo['puntuacion']
            if ultima_punt >= UMBRAL_SUPERADO:
                return (f"En {modo_nombre}, has superado hasta el nivel {max_superado}. "
                        f"¿Quieres pasar al nivel {recomendado} ({nombre_siguiente})?")
            else:
                return (f"En {modo_nombre}, has superado hasta el nivel {max_superado}. "
                        f"En tu último intento en el nivel {nivel_act} sacaste un {ultima_punt:.0f}%. "
                        f"¿Quieres seguir practicando el nivel {nivel_act}?")
        return (f"En {modo_nombre}, has superado hasta el nivel {max_superado}. "
                f"¿Continuamos con el nivel {recomendado} ({nombre_siguiente})?")

    if niveles_sup and not nivel_act:
        return (f"Has superado todos los niveles de {modo_nombre}. "
                "¿Quieres repasar algún nivel en concreto?")

    if not niveles_sup and ultimo:
        ultima_punt = ultimo['puntuacion']
        return (f"En {modo_nombre}, aún no has superado el nivel {nivel_act}. "
                f"Tu última puntuación fue {ultima_punt:.0f}%. "
                f"¿Quieres seguir practicando?")

    return None


# ═══════════════════════════════════════════════════════════════════════
# PROGRESO POR TEMA
# ═══════════════════════════════════════════════════════════════════════

# Criterios para considerar un tema "superado"
_CRITERIOS_TEMA = {
    1: {
        'descripcion': 'Consultar al menos 4 conceptos clave',
        'min_conceptos': 4,
    },
    2: {
        'descripcion': 'Superar nivel 3 de transcripción + 2 ejercicios de errores con ≥80%',
        'min_nivel_transcripcion': 3,
        'min_ejercicios_errores': 2,
        'umbral': UMBRAL_SUPERADO,
    },
    3: {
        'descripcion': 'Superar nivel 3 de transcripción fonética + consultar 3 conceptos sobre alófonos',
        'min_nivel_transcripcion_fonetica': 3,
        'min_conceptos': 3,
    },
    4: {
        'descripcion': 'Analizar al menos 1 audio + consultar 3 conceptos acústicos',
        'min_audios': 1,
        'min_conceptos': 3,
    },
    5: {
        'descripcion': 'Consultar al menos 4 conceptos clave de percepción',
        'min_conceptos': 4,
    },
    6: {
        'descripcion': 'Consultar al menos 3 conceptos del proyecto',
        'min_conceptos': 3,
    },
}


def registrar_actividad_tema(username: str, tema_id: int, tipo: str,
                              detalle: str = ''):
    """Registra una actividad del alumno en un tema.

    Args:
        username: identificador del alumno
        tema_id: número de tema (1-5)
        tipo: tipo de actividad:
            - 'concepto': consultó un concepto clave
            - 'ejercicio': completó un ejercicio (detalle = puntuación)
            - 'audio': analizó un audio
            - 'autoevaluacion': revisó la autoevaluación
        detalle: información adicional (ej: nombre del concepto, puntuación)
    """
    progreso = cargar_progreso(username)

    if 'temas' not in progreso:
        progreso['temas'] = {}

    tema_key = str(tema_id)
    if tema_key not in progreso['temas']:
        progreso['temas'][tema_key] = {
            'conceptos': [],
            'ejercicios': [],
            'audios': 0,
            'autoevaluacion': False,
            'primera_visita': datetime.now().isoformat(),
        }

    tema = progreso['temas'][tema_key]

    if tipo == 'concepto':
        if detalle and detalle not in tema['conceptos']:
            tema['conceptos'].append(detalle)
    elif tipo == 'ejercicio':
        tema['ejercicios'].append({
            'fecha': datetime.now().isoformat(),
            'detalle': detalle,
        })
    elif tipo == 'audio':
        tema['audios'] = tema.get('audios', 0) + 1
    elif tipo == 'autoevaluacion':
        tema['autoevaluacion'] = True

    tema['ultima_actividad'] = datetime.now().isoformat()
    guardar_progreso(username, progreso)


def progreso_tema(username: str, tema_id: int) -> dict:
    """Devuelve el estado de progreso de un alumno en un tema.

    Returns:
        dict con superado, porcentaje, conceptos_consultados,
        ejercicios_completados, criterio, recomendacion.
    """
    progreso = cargar_progreso(username)
    tema_key = str(tema_id)
    tema_data = progreso.get('temas', {}).get(tema_key, {})
    criterio = _CRITERIOS_TEMA.get(tema_id, {})

    n_conceptos = len(tema_data.get('conceptos', []))
    n_ejercicios = len(tema_data.get('ejercicios', []))
    n_audios = tema_data.get('audios', 0)

    superado = False
    items_totales = 0
    items_cumplidos = 0

    if tema_id in (1, 5, 6):
        min_c = criterio.get('min_conceptos', 4)
        items_totales = min_c
        items_cumplidos = min(n_conceptos, min_c)
        superado = n_conceptos >= min_c

    elif tema_id == 2:
        modo_data = progreso.get('fonologica_tipica', {})
        niveles_sup = sum(1 for n in range(1, 4)
                         if modo_data.get(str(n), {}).get('superado', False))
        min_nivel = criterio.get('min_nivel_transcripcion', 3)
        min_ej = criterio.get('min_ejercicios_errores', 2)
        ej_errores_buenos = sum(1 for e in tema_data.get('ejercicios', [])
                                if 'error' in e.get('detalle', '').lower())
        items_totales = min_nivel + min_ej
        items_cumplidos = min(niveles_sup, min_nivel) + min(ej_errores_buenos, min_ej)
        superado = niveles_sup >= min_nivel and ej_errores_buenos >= min_ej

    elif tema_id == 3:
        modo_data = progreso.get('fonetica_tipica', {})
        niveles_sup = sum(1 for n in range(1, 4)
                         if modo_data.get(str(n), {}).get('superado', False))
        min_nivel = criterio.get('min_nivel_transcripcion_fonetica', 3)
        min_c = criterio.get('min_conceptos', 3)
        items_totales = min_nivel + min_c
        items_cumplidos = min(niveles_sup, min_nivel) + min(n_conceptos, min_c)
        superado = niveles_sup >= min_nivel and n_conceptos >= min_c

    elif tema_id == 4:
        min_a = criterio.get('min_audios', 1)
        min_c = criterio.get('min_conceptos', 3)
        items_totales = min_a + min_c
        items_cumplidos = min(n_audios, min_a) + min(n_conceptos, min_c)
        superado = n_audios >= min_a and n_conceptos >= min_c

    porcentaje = round(items_cumplidos / items_totales * 100) if items_totales > 0 else 0
    porcentaje = min(porcentaje, 100)

    recomendacion = None
    if superado:
        if tema_id < 5:
            recomendacion = f'Has superado el Tema {tema_id}. Puedes avanzar al Tema {tema_id + 1}.'
        else:
            recomendacion = 'Has completado todos los temas.'
    elif porcentaje > 0:
        recomendacion = f'Tema {tema_id} en progreso ({porcentaje}%). ' + criterio.get('descripcion', '')

    return {
        'superado': superado,
        'porcentaje': porcentaje,
        'conceptos_consultados': n_conceptos,
        'ejercicios_completados': n_ejercicios,
        'audios_analizados': n_audios,
        'criterio': criterio.get('descripcion', ''),
        'recomendacion': recomendacion,
    }


def progreso_todos_temas(username: str, num_temas: int = 6) -> list[dict]:
    """Devuelve el progreso de todos los temas."""
    return [
        {'tema_id': i, **progreso_tema(username, i)}
        for i in range(1, num_temas + 1)
    ]


def tema_recomendado(username: str, num_temas: int = 6) -> int:
    """Devuelve el primer tema no superado."""
    for i in range(1, num_temas + 1):
        if not progreso_tema(username, i)['superado']:
            return i
    return num_temas
