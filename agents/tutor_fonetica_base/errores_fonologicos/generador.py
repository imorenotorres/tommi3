"""
Generador de errores fonológicos.

Aplica errores controlados sobre una transcripción fonológica correcta.
Cada función devuelve la transcripción modificada y la lista de errores aplicados.
"""

import random
from copy import deepcopy
from .inventario import (
    FONEMAS, CONSONANTES, VOCALES, ESCALA_MODO, ESCALA_LUGAR,
    es_consonante, es_vocal, rasgos, fonemas_similares, fonemas_por_rasgo,
    clasificar_error_sistemico
)
from .silaba import Palabra, Silaba, parsear_silabas, reconstruir_transcripcion


# ═══════════════════════════════════════════════════════════════════════
# ERRORES SISTÉMICOS (afectan a un fonema individual)
# ═══════════════════════════════════════════════════════════════════════

def error_sonorizacion(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Sonoriza una consonante sorda aleatoria."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    pares = {'p': 'b', 't': 'd', 'k': 'g'}  # solo oclusivas sordas → sonoras
    candidatos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if f in pares:
                candidatos.append((si, fi, f, pares[f]))
    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'sonorizacion', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Sonorización: /{orig}/ > /{nuevo}/'}


def error_ensordecimiento(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Ensordece una consonante sonora aleatoria."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    pares = {'b': 'p', 'd': 't', 'g': 'k'}
    candidatos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if f in pares:
                candidatos.append((si, fi, f, pares[f]))
    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'ensordecimiento', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Ensordecimiento: /{orig}/ > /{nuevo}/'}


def error_adelantamiento(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Adelanta el lugar de articulación de una consonante."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    candidatos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if not es_consonante(f):
                continue
            r = rasgos(f)
            idx = ESCALA_LUGAR.index(r['lugar']) if r['lugar'] in ESCALA_LUGAR else -1
            if idx > 0:  # puede adelantarse
                lugar_nuevo = ESCALA_LUGAR[idx - 1]
                nuevos = [fn for fn, rr in CONSONANTES.items()
                          if rr['lugar'] == lugar_nuevo and rr['modo'] == r['modo']
                          and rr['sonoridad'] == r['sonoridad'] and fn != f]
                if nuevos:
                    candidatos.append((si, fi, f, rng.choice(nuevos)))
    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'adelantamiento', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Adelantamiento: /{orig}/ > /{nuevo}/'}


def error_posteriorizacion(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Posterioriza el lugar de articulación de una consonante."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    candidatos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if not es_consonante(f):
                continue
            r = rasgos(f)
            idx = ESCALA_LUGAR.index(r['lugar']) if r['lugar'] in ESCALA_LUGAR else -1
            if 0 <= idx < len(ESCALA_LUGAR) - 1:
                lugar_nuevo = ESCALA_LUGAR[idx + 1]
                nuevos = [fn for fn, rr in CONSONANTES.items()
                          if rr['lugar'] == lugar_nuevo and rr['modo'] == r['modo']
                          and rr['sonoridad'] == r['sonoridad'] and fn != f]
                if nuevos:
                    candidatos.append((si, fi, f, rng.choice(nuevos)))
    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'posteriorizacion', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Posteriorización: /{orig}/ > /{nuevo}/'}


def error_nasalizacion(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Nasaliza una consonante oral (b>m, d>n, g>ŋ)."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    pares = {'b': 'm', 'd': 'n', 'g': 'ɲ'}
    candidatos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if f in pares:
                candidatos.append((si, fi, f, pares[f]))
    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'nasalizacion', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Nasalización: /{orig}/ > /{nuevo}/'}


def error_desnasalizacion(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Desnasaliza una consonante nasal (m>b, n>d)."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    pares = {'m': 'b', 'n': 'd', 'ɲ': 'g'}
    candidatos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if f in pares:
                candidatos.append((si, fi, f, pares[f]))
    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'desnasalizacion', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Desnasalización: /{orig}/ > /{nuevo}/'}


# ═══════════════════════════════════════════════════════════════════════
# ERRORES ESTRUCTURALES — SÍLABA
# ═══════════════════════════════════════════════════════════════════════

def error_omision_ataque(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Omite el ataque de una sílaba aleatoria."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    candidatos = [i for i, s in enumerate(p.silabas) if s.tiene_ataque]
    if not candidatos:
        return p, None
    si = rng.choice(candidatos)
    ataque_orig = ''.join(p.silabas[si].ataque)
    p.silabas[si].ataque = []
    return p, {'tipo': 'omision_ataque', 'silaba': si,
               'descripcion': f'Omisión de ataque: /{ataque_orig}/ omitido en sílaba {si+1}'}


def error_simplificacion_ataque(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Simplifica un ataque complejo (ej: /tɾ/ > /t/)."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    candidatos = [i for i, s in enumerate(p.silabas) if s.ataque_complejo]
    if not candidatos:
        return p, None
    si = rng.choice(candidatos)
    ataque_orig = ''.join(p.silabas[si].ataque)
    # Mantener solo la primera consonante
    p.silabas[si].ataque = [p.silabas[si].ataque[0]]
    return p, {'tipo': 'simplificacion_ataque', 'silaba': si,
               'descripcion': f'Simplificación de ataque: /{ataque_orig}/ > /{p.silabas[si].ataque[0]}/'}


def error_simplificacion_nucleo(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Simplifica un diptongo (ej: /ie/ > /e/)."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    candidatos = [i for i, s in enumerate(p.silabas) if s.tiene_diptongo]
    if not candidatos:
        return p, None
    si = rng.choice(candidatos)
    nucleo_orig = ''.join(p.silabas[si].nucleo)
    # Mantener solo la vocal principal (la más abierta)
    vocales = [f for f in p.silabas[si].nucleo if es_vocal(f)]
    if vocales:
        p.silabas[si].nucleo = [vocales[-1]]  # última vocal suele ser la principal
    else:
        p.silabas[si].nucleo = [p.silabas[si].nucleo[-1]]
    return p, {'tipo': 'simplificacion_nucleo', 'silaba': si,
               'descripcion': f'Simplificación de núcleo: /{nucleo_orig}/ > /{"".join(p.silabas[si].nucleo)}/'}


def error_omision_coda(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Omite la coda de una sílaba aleatoria."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    candidatos = [i for i, s in enumerate(p.silabas) if s.tiene_coda]
    if not candidatos:
        return p, None
    si = rng.choice(candidatos)
    coda_orig = ''.join(p.silabas[si].coda)
    p.silabas[si].coda = []
    return p, {'tipo': 'omision_coda', 'silaba': si,
               'descripcion': f'Omisión de coda: /{coda_orig}/ omitida en sílaba {si+1}'}


# ═══════════════════════════════════════════════════════════════════════
# ERRORES ESTRUCTURALES — PALABRA
# ═══════════════════════════════════════════════════════════════════════

def error_asimilacion_regresiva(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Asimilación regresiva: un sonido cambia por efecto de otro posterior."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    fonemas_planos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            fonemas_planos.append((si, fi, f))

    candidatos = []
    for i in range(len(fonemas_planos) - 1):
        si1, fi1, f1 = fonemas_planos[i]
        si2, fi2, f2 = fonemas_planos[i + 1]
        if es_consonante(f1) and es_consonante(f2) and f1 != f2:
            candidatos.append((si1, fi1, f1, f2))

    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'asimilacion_regresiva', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Asimilación regresiva: /{orig}/ > /{nuevo}/'}


def error_asimilacion_progresiva(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Asimilación progresiva: un sonido cambia por efecto de otro anterior."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    fonemas_planos = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            fonemas_planos.append((si, fi, f))

    candidatos = []
    for i in range(1, len(fonemas_planos)):
        si_prev, fi_prev, f_prev = fonemas_planos[i - 1]
        si_curr, fi_curr, f_curr = fonemas_planos[i]
        if es_consonante(f_prev) and es_consonante(f_curr) and f_prev != f_curr:
            candidatos.append((si_curr, fi_curr, f_curr, f_prev))

    if not candidatos:
        return p, None
    si, fi, orig, nuevo = rng.choice(candidatos)
    _reemplazar_fonema(p.silabas[si], fi, nuevo)
    return p, {'tipo': 'asimilacion_progresiva', 'original': orig, 'producido': nuevo,
               'silaba': si, 'descripcion': f'Asimilación progresiva: /{orig}/ > /{nuevo}/'}


def error_metátesis(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Intercambia dos consonantes de la palabra."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    consonantes = []
    for si, sil in enumerate(p.silabas):
        for fi, f in enumerate(sil.fonemas):
            if es_consonante(f):
                consonantes.append((si, fi, f))

    if len(consonantes) < 2:
        return p, None
    idx1, idx2 = rng.sample(range(len(consonantes)), 2)
    si1, fi1, f1 = consonantes[idx1]
    si2, fi2, f2 = consonantes[idx2]
    _reemplazar_fonema(p.silabas[si1], fi1, f2)
    _reemplazar_fonema(p.silabas[si2], fi2, f1)
    return p, {'tipo': 'metatesis', 'descripcion': f'Metátesis: /{f1}/ ↔ /{f2}/'}


def error_omision_silaba_atona(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Omite una sílaba átona."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    atonas = p.silabas_atonas
    if not atonas or len(p.silabas) <= 1:
        return p, None
    si = rng.choice(atonas)
    silaba_omitida = str(p.silabas[si])
    p.silabas.pop(si)
    return p, {'tipo': 'omision_silaba_atona', 'silaba': si,
               'descripcion': f'Omisión de sílaba átona: /{silaba_omitida}/ (sílaba {si+1})'}


def error_omision_silaba_tonica(palabra: Palabra, rng: random.Random = None) -> tuple[Palabra, dict]:
    """Omite la sílaba tónica."""
    rng = rng or random.Random()
    p = deepcopy(palabra)
    tonica = p.silaba_tonica
    if tonica < 0 or len(p.silabas) <= 1:
        return p, None
    silaba_omitida = str(p.silabas[tonica])
    p.silabas.pop(tonica)
    return p, {'tipo': 'omision_silaba_tonica', 'silaba': tonica,
               'descripcion': f'Omisión de sílaba tónica: /{silaba_omitida}/'}


# ═══════════════════════════════════════════════════════════════════════
# CATÁLOGO DE ERRORES
# ═══════════════════════════════════════════════════════════════════════

ERRORES_SISTEMICOS = {
    'sonorizacion': error_sonorizacion,
    'ensordecimiento': error_ensordecimiento,
    'adelantamiento': error_adelantamiento,
    'posteriorizacion': error_posteriorizacion,
    'nasalizacion': error_nasalizacion,
    'desnasalizacion': error_desnasalizacion,
}

ERRORES_SILABA = {
    'omision_ataque': error_omision_ataque,
    'simplificacion_ataque': error_simplificacion_ataque,
    'simplificacion_nucleo': error_simplificacion_nucleo,
    'omision_coda': error_omision_coda,
}

ERRORES_PALABRA = {
    'asimilacion_regresiva': error_asimilacion_regresiva,
    'asimilacion_progresiva': error_asimilacion_progresiva,
    'metatesis': error_metátesis,
    'omision_silaba_atona': error_omision_silaba_atona,
    'omision_silaba_tonica': error_omision_silaba_tonica,
}

TODOS_LOS_ERRORES = {**ERRORES_SISTEMICOS, **ERRORES_SILABA, **ERRORES_PALABRA}


def generar_errores(transcripcion: str, tipos: list[str] = None,
                    num_errores: int = 1, seed: int = None) -> tuple[str, list[dict]]:
    """
    Aplica errores aleatorios a una transcripción fonológica.

    Args:
        transcripcion: Transcripción fonológica (ej: "ˈka.sa")
        tipos: Lista de tipos de error a aplicar. Si None, usa todos.
               Puede ser nombres específicos o categorías: 'sistemico', 'silaba', 'palabra'
        num_errores: Número de errores a aplicar
        seed: Semilla para reproducibilidad

    Returns:
        (transcripcion_con_errores, lista_de_errores_aplicados)
    """
    rng = random.Random(seed)
    palabra = parsear_silabas(transcripcion)

    # Resolver tipos
    funciones = []
    if tipos is None:
        funciones = list(TODOS_LOS_ERRORES.values())
    else:
        for t in tipos:
            if t == 'sistemico':
                funciones.extend(ERRORES_SISTEMICOS.values())
            elif t == 'silaba':
                funciones.extend(ERRORES_SILABA.values())
            elif t == 'palabra':
                funciones.extend(ERRORES_PALABRA.values())
            elif t in TODOS_LOS_ERRORES:
                funciones.append(TODOS_LOS_ERRORES[t])

    if not funciones:
        return reconstruir_transcripcion(palabra), []

    errores_aplicados = []
    intentos = 0
    max_intentos = num_errores * 5

    while len(errores_aplicados) < num_errores and intentos < max_intentos:
        func = rng.choice(funciones)
        palabra, error = func(palabra, rng)
        if error is not None:
            errores_aplicados.append(error)
        intentos += 1

    return reconstruir_transcripcion(palabra), errores_aplicados


# ═══════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════

def _reemplazar_fonema(silaba: Silaba, indice_global: int, nuevo: str):
    """Reemplaza un fonema en una sílaba dado su índice global (ataque+nucleo+coda)."""
    n_ataque = len(silaba.ataque)
    n_nucleo = len(silaba.nucleo)

    if indice_global < n_ataque:
        silaba.ataque[indice_global] = nuevo
    elif indice_global < n_ataque + n_nucleo:
        silaba.nucleo[indice_global - n_ataque] = nuevo
    else:
        silaba.coda[indice_global - n_ataque - n_nucleo] = nuevo
