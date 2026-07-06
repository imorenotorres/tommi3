"""
Gestión del progreso del alumno en ejercicios de transcripción fonológica.

Almacena el historial de ejercicios por alumno en archivos JSON individuales.
Permite sugerir el nivel adecuado y hacer seguimiento.
"""

import json
import os
from datetime import datetime
from pathlib import Path

_PROGRESS_DIR = Path(__file__).parent / "progress"
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

    from errores_fonologicos.ejercicios_transcripcion import _NIVEL_NOMBRES
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
