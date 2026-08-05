"""
Inventario fonológico del español.

Cada fonema se describe con 4 rasgos:
  - sonoridad: 'sordo' | 'sonoro'
  - modo: 'oclusivo' | 'africado' | 'fricativo' | 'nasal' | 'lateral' | 'vibrante_simple' | 'vibrante_multiple' | 'aproximante' | 'vocal_cerrada' | 'vocal_media' | 'vocal_abierta'
  - lugar: 'bilabial' | 'labiodental' | 'interdental' | 'dental' | 'alveolar' | 'palatal' | 'velar'
  - nasalidad: 'nasal' | 'oral'

Para vocales, 'lugar' indica la posición anterior/central/posterior.
"""

# Escala de modo (de mayor cierre a mayor apertura)
# Los modos con el mismo nivel de apertura comparten el mismo índice.
# Nasal, lateral, vibrante simple y vibrante múltiple están al mismo nivel.
ESCALA_MODO_NIVELES = {
    'oclusivo': 0,
    'africado': 0,
    'fricativo': 1,
    'nasal': 2,
    'lateral': 2,
    'vibrante_simple': 2,
    'vibrante_multiple': 2,
    'vocal_cerrada': 3,
    'vocal_media': 4,
    'vocal_abierta': 5,
}

# Lista ordenada (para compatibilidad)
ESCALA_MODO = [
    'oclusivo', 'africado', 'fricativo', 'nasal', 'lateral',
    'vibrante_simple', 'vibrante_multiple',
    'vocal_cerrada', 'vocal_media', 'vocal_abierta'
]

# Escala de lugar (de más anterior a más posterior)
ESCALA_LUGAR = [
    'bilabial', 'labiodental', 'interdental', 'dental', 'alveolar',
    'palatal', 'velar'
]

# Escala de lugar vocálico
ESCALA_LUGAR_VOCAL = ['anterior', 'central', 'posterior']


# ── Inventario de consonantes ──────────────────────────────────────────

# Inventario fonológico: solo fonemas, no alófonos.
# 18 fonemas consonánticos + 5 vocales = 23 fonemas del español peninsular.

CONSONANTES = {
    # Oclusivas sordas
    'p': {'sonoridad': 'sordo', 'modo': 'oclusivo', 'lugar': 'bilabial', 'nasalidad': 'oral'},
    't': {'sonoridad': 'sordo', 'modo': 'oclusivo', 'lugar': 'dental', 'nasalidad': 'oral'},
    'k': {'sonoridad': 'sordo', 'modo': 'oclusivo', 'lugar': 'velar', 'nasalidad': 'oral'},

    # Oclusivas sonoras
    'b': {'sonoridad': 'sonoro', 'modo': 'oclusivo', 'lugar': 'bilabial', 'nasalidad': 'oral'},
    'd': {'sonoridad': 'sonoro', 'modo': 'oclusivo', 'lugar': 'dental', 'nasalidad': 'oral'},
    'g': {'sonoridad': 'sonoro', 'modo': 'oclusivo', 'lugar': 'velar', 'nasalidad': 'oral'},

    # Africada
    'tʃ': {'sonoridad': 'sordo', 'modo': 'africado', 'lugar': 'palatal', 'nasalidad': 'oral'},

    # Fricativas
    'f': {'sonoridad': 'sordo', 'modo': 'fricativo', 'lugar': 'labiodental', 'nasalidad': 'oral'},
    'θ': {'sonoridad': 'sordo', 'modo': 'fricativo', 'lugar': 'interdental', 'nasalidad': 'oral'},
    's': {'sonoridad': 'sordo', 'modo': 'fricativo', 'lugar': 'alveolar', 'nasalidad': 'oral'},
    'x': {'sonoridad': 'sordo', 'modo': 'fricativo', 'lugar': 'velar', 'nasalidad': 'oral'},
    'ʝ': {'sonoridad': 'sonoro', 'modo': 'fricativo', 'lugar': 'palatal', 'nasalidad': 'oral'},

    # Nasales
    'm': {'sonoridad': 'sonoro', 'modo': 'nasal', 'lugar': 'bilabial', 'nasalidad': 'nasal'},
    'n': {'sonoridad': 'sonoro', 'modo': 'nasal', 'lugar': 'alveolar', 'nasalidad': 'nasal'},
    'ɲ': {'sonoridad': 'sonoro', 'modo': 'nasal', 'lugar': 'palatal', 'nasalidad': 'nasal'},

    # Lateral
    'l': {'sonoridad': 'sonoro', 'modo': 'lateral', 'lugar': 'alveolar', 'nasalidad': 'oral'},

    # Vibrantes
    'ɾ': {'sonoridad': 'sonoro', 'modo': 'vibrante_simple', 'lugar': 'alveolar', 'nasalidad': 'oral'},
    'r': {'sonoridad': 'sonoro', 'modo': 'vibrante_multiple', 'lugar': 'alveolar', 'nasalidad': 'oral'},
}

# ── Inventario de vocales ──────────────────────────────────────────────

VOCALES = {
    'i': {'sonoridad': 'sonoro', 'modo': 'vocal_cerrada', 'lugar': 'anterior', 'nasalidad': 'oral'},
    'u': {'sonoridad': 'sonoro', 'modo': 'vocal_cerrada', 'lugar': 'posterior', 'nasalidad': 'oral'},
    'e': {'sonoridad': 'sonoro', 'modo': 'vocal_media', 'lugar': 'anterior', 'nasalidad': 'oral'},
    'o': {'sonoridad': 'sonoro', 'modo': 'vocal_media', 'lugar': 'posterior', 'nasalidad': 'oral'},
    'a': {'sonoridad': 'sonoro', 'modo': 'vocal_abierta', 'lugar': 'central', 'nasalidad': 'oral'},
}

# Inventario completo (23 fonemas)
FONEMAS = {**CONSONANTES, **VOCALES}


# ── Funciones de consulta ──────────────────────────────────────────────

def es_consonante(fonema: str) -> bool:
    return fonema in CONSONANTES

def es_vocal(fonema: str) -> bool:
    return fonema in VOCALES

def es_semivocal(fonema: str) -> bool:
    """En el inventario fonológico, las semivocales /j, w/ son alófonos de /i, u/.
    En las transcripciones fonológicas se representan como vocales."""
    return False

def rasgos(fonema: str) -> dict:
    """Devuelve los rasgos de un fonema. Lanza KeyError si no existe."""
    if fonema in FONEMAS:
        return FONEMAS[fonema].copy()
    raise KeyError(f"Fonema desconocido: '{fonema}'")

def comparar_rasgos(fonema1: str, fonema2: str) -> list[str]:
    """Devuelve la lista de rasgos que difieren entre dos fonemas."""
    r1 = rasgos(fonema1)
    r2 = rasgos(fonema2)
    return [rasgo for rasgo in r1 if r1[rasgo] != r2[rasgo]]

def clasificar_error_sistemico(objetivo: str, producido: str) -> list[dict]:
    """
    Dado un fonema objetivo y uno producido, clasifica el error sistémico.
    Devuelve una lista de errores (puede haber más de un rasgo afectado).

    Cada error es un dict: {'rasgo': str, 'tipo': str, 'descripcion': str}
    """
    if objetivo == producido:
        return []

    r_obj = rasgos(objetivo)
    r_prod = rasgos(producido)
    errores = []

    # Sonoridad
    if r_obj['sonoridad'] != r_prod['sonoridad']:
        if r_prod['sonoridad'] == 'sonoro':
            errores.append({'rasgo': 'sonoridad', 'tipo': 'sonorizacion',
                           'descripcion': f'Sonorización: /{objetivo}/ > /{producido}/'})
        else:
            errores.append({'rasgo': 'sonoridad', 'tipo': 'ensordecimiento',
                           'descripcion': f'Ensordecimiento: /{objetivo}/ > /{producido}/'})

    # Modo de articulación
    if r_obj['modo'] != r_prod['modo']:
        nivel_obj = ESCALA_MODO_NIVELES.get(r_obj['modo'], -1)
        nivel_prod = ESCALA_MODO_NIVELES.get(r_prod['modo'], -1)
        if nivel_obj >= 0 and nivel_prod >= 0:
            if nivel_obj == nivel_prod:
                # Mismo nivel de apertura (ej: vibrante simple ↔ lateral) → error de modo sin dirección
                errores.append({'rasgo': 'modo', 'tipo': 'cambio_modo',
                               'descripcion': f'Cambio de modo: /{objetivo}/ ({r_obj["modo"]}) > /{producido}/ ({r_prod["modo"]})'})
            elif nivel_prod > nivel_obj:
                errores.append({'rasgo': 'modo', 'tipo': 'lenicion',
                               'descripcion': f'Lenición (suavización): /{objetivo}/ > /{producido}/'})
            else:
                errores.append({'rasgo': 'modo', 'tipo': 'forticion',
                               'descripcion': f'Fortición (refuerzo): /{objetivo}/ > /{producido}/'})

    # Lugar de articulación
    if r_obj['lugar'] != r_prod['lugar']:
        escala = ESCALA_LUGAR if es_consonante(objetivo) else ESCALA_LUGAR_VOCAL
        idx_obj = escala.index(r_obj['lugar']) if r_obj['lugar'] in escala else -1
        idx_prod = escala.index(r_prod['lugar']) if r_prod['lugar'] in escala else -1
        if idx_obj >= 0 and idx_prod >= 0:
            if idx_prod < idx_obj:
                errores.append({'rasgo': 'lugar', 'tipo': 'adelantamiento',
                               'descripcion': f'Adelantamiento: /{objetivo}/ > /{producido}/'})
            else:
                errores.append({'rasgo': 'lugar', 'tipo': 'posteriorizacion',
                               'descripcion': f'Posteriorización: /{objetivo}/ > /{producido}/'})

    # Nasalidad
    if r_obj['nasalidad'] != r_prod['nasalidad']:
        if r_prod['nasalidad'] == 'nasal':
            errores.append({'rasgo': 'nasalidad', 'tipo': 'nasalizacion',
                           'descripcion': f'Nasalización: /{objetivo}/ > /{producido}/'})
        else:
            errores.append({'rasgo': 'nasalidad', 'tipo': 'desnasalizacion',
                           'descripcion': f'Desnasalización: /{objetivo}/ > /{producido}/'})

    return errores


def fonemas_por_rasgo(rasgo: str, valor: str) -> list[str]:
    """Devuelve todos los fonemas que tienen un determinado valor en un rasgo."""
    return [f for f, r in FONEMAS.items() if r.get(rasgo) == valor]


def fonemas_similares(fonema: str, max_diferencias: int = 1) -> list[str]:
    """Devuelve fonemas que difieren en como máximo N rasgos."""
    resultado = []
    for f in FONEMAS:
        if f == fonema:
            continue
        diffs = comparar_rasgos(fonema, f)
        if len(diffs) <= max_diferencias:
            resultado.append(f)
    return resultado
