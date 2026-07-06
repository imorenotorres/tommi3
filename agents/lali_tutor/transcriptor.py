"""
Transcriptor fonológico del español peninsular distinguidor.

Dada una frase en ortografía española, produce la transcripción fonológica
con separación silábica (puntos) y marca de acento (apóstrofo antes de la
sílaba tónica).

Ejemplo:
    transcribir("El niño come pan") → / el 'ni.ɲo 'ko.me 'pan /

LIMITACIONES (requieren tratamiento manual):
    1. HIATOS vs DIPTONGOS: La decisión de si dos vocales forman diptongo
       o hiato no siempre es predecible desde la ortografía.
       Ej: "piano" → ¿/pia.no/ o /pi.a.no/? (depende del hablante/dialecto)
       REGLA ACTUAL: vocal cerrada (/i/,/u/) + vocal abierta (/a/,/e/,/o/)
       = diptongo; dos abiertas = hiato. La tilde rompe el diptongo (día = /di.a/).

    2. ACENTO en palabras desconocidas: El script aplica las reglas generales
       del español (aguda si termina en consonante salvo n/s, llana si termina
       en vocal/n/s). Las tildes se respetan. Pero no tiene diccionario de
       excepciones.

    3. PRÉSTAMOS y EXTRANJERISMOS: Palabras como "software", "marketing",
       "jazz" no siguen las reglas del español y se transcriben mal.

    4. LETRAS MUDAS: La "h" se elimina correctamente, pero "güe/güi" con
       diéresis podría fallar en casos raros.

    5. NOMBRES PROPIOS: No se distinguen de palabras comunes.

    6. PALABRAS FUNCIONALES ÁTONAS: Artículos, preposiciones y pronombres
       átonos (el, de, me, te, se, la, lo...) no llevan acento. El script
       tiene una lista básica pero puede ser incompleta.
"""

import json
import os
import re
import unicodedata

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE TRANSCRIPCIÓN
# ═══════════════════════════════════════════════════════════════════════

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'transcripcion_config.json')

def _cargar_config() -> dict:
    """Carga la configuración de transcripción desde transcripcion_config.json."""
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return {
            'sibilantes': raw.get('sibilantes', {}).get('valor', 'distinguidor'),
            'nasalizacion_vocalica': raw.get('nasalizacion_vocalica', {}).get('valor', False),
            's_coda': raw.get('s_coda', {}).get('valor', 'sibilante'),
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {'sibilantes': 'distinguidor', 'nasalizacion_vocalica': False, 's_coda': 'sibilante'}

# Se carga una vez al importar; recargar con recargar_config()
_config = _cargar_config()

def recargar_config():
    """Recarga la configuración desde disco."""
    global _config
    _config = _cargar_config()

def get_config() -> dict:
    """Devuelve la configuración actual (copia)."""
    return _config.copy()


# ═══════════════════════════════════════════════════════════════════════
# PASO 1: Conversión grafema → fonema
# ═══════════════════════════════════════════════════════════════════════

# Mapa de grafemas a fonemas
# NOTA: Algunos grafemas dependen del contexto (c, g, r, x, etc.)

def _sibilante_sorda() -> str:
    """Devuelve el fonema sibilante según la configuración de sibilantes.
    - distinguidor: 'θ' (para c+e/i y z)
    - seseo: 's' (todo se realiza como /s/)
    - ceceo: 'θ' (todo se realiza como /θ/)
    En seseo, c+e/i y z se transcriben como /s/.
    En distinguidor y ceceo, se transcriben como /θ/.
    """
    if _config['sibilantes'] == 'seseo':
        return 's'
    return 'θ'  # distinguidor y ceceo usan /θ/


def grafema_a_fonema(palabra: str) -> tuple:
    """Convierte una palabra ortográfica a secuencia de fonemas.

    Returns:
        (fonemas_str, pos_tilde, hiato_positions)
        - fonemas_str: string de fonemas
        - pos_tilde: posición del fonema con tilde (-1 si no hay)
        - hiato_positions: set de posiciones de vocales cerradas con tilde
          (fuerzan hiato con la vocal adyacente)

    TRATAMIENTO MANUAL NECESARIO:
    - "x" entre vocales: /ks/ o /s/ según el registro
    - Préstamos extranjeros no cubiertos
    """
    # Normalizar: minúsculas, eliminar h muda
    p = palabra.lower()

    # Eliminar tildes pero recordar la posición de la vocal acentuada
    # y si la tilde está en una vocal cerrada (fuerza hiato)
    pos_tilde = -1
    tilde_en_cerrada = set()  # posiciones en p_limpia de vocales cerradas con tilde
    p_limpia = ""
    for i, c in enumerate(p):
        sin_tilde = unicodedata.normalize('NFD', c)
        if len(sin_tilde) > 1 and sin_tilde[1] == '\u0301':  # combining acute
            pos_tilde = len(p_limpia)
            vocal_base = sin_tilde[0]
            if vocal_base in ('i', 'u'):
                tilde_en_cerrada.add(len(p_limpia))
            p_limpia += vocal_base
        elif c == 'ü':
            p_limpia += 'ü'
        else:
            p_limpia += c

    p = p_limpia

    # hie- inicial → /ʝe/ (hierba → ʝerba, hielo → ʝelo, hiena → ʝena)
    # Se reemplaza "hie" por "ʝe" antes de eliminar la h muda
    p = re.sub(r'^hie', 'ʝe', p)
    # hie- tras prefijo (des-hierbar, etc.) — menos frecuente, se ignora por ahora

    # Eliminar h muda (pero no en "ch")
    p = re.sub(r'(?<!c)h', '', p)

    fonemas = []
    hiato_fonema_positions = set()  # fonema positions that force hiato
    i = 0
    while i < len(p):
        c = p[i]
        next_c = p[i + 1] if i + 1 < len(p) else ''

        # Dígrafos primero
        if c == 'c' and next_c == 'h':
            fonemas.append('ʧ')
            i += 2
        elif c == 'l' and next_c == 'l':
            fonemas.append('ʝ')  # yeísmo generalizado en peninsular moderno
            i += 2
        elif c == 'r' and next_c == 'r':
            fonemas.append('r')  # vibrante múltiple
            i += 2
        elif c == 'g' and next_c == 'u':
            # gu + e/i = /g/ (la u es muda)
            next2 = p[i + 2] if i + 2 < len(p) else ''
            if next2 in ('e', 'i'):
                fonemas.append('g')
                i += 3
                fonemas.append(_vocal_a_fonema(next2))
            elif next_c == 'ü':
                # güe, güi = /gu/ + vocal
                fonemas.append('g')
                fonemas.append('u')
                i += 2
            else:
                fonemas.append('g')
                fonemas.append('u')
                i += 2
        elif c == 'q' and next_c == 'u':
            fonemas.append('k')
            i += 2
            # la vocal siguiente va aparte
        # Consonantes simples con contexto
        elif c == 'c':
            if next_c in ('e', 'i'):
                fonemas.append(_sibilante_sorda())  # ce, ci
            else:
                fonemas.append('k')
            i += 1
        elif c == 'g':
            if next_c in ('e', 'i'):
                fonemas.append('x')  # ge, gi = /x/
            else:
                fonemas.append('g')
            i += 1
        elif c == 'r':
            # r a inicio de palabra o tras n, l, s = vibrante múltiple
            if i == 0:
                fonemas.append('r')
            elif i > 0 and p[i - 1] in ('n', 'l', 's'):
                fonemas.append('r')
            else:
                fonemas.append('ɾ')
            i += 1
        elif c == 'x':
            # "x" + vocal = /ks/ (saxofón, examen)
            # "x" + consonante o final = /s/ (sexto, exterior → /sesto/, /esterioɾ/)
            # TRATAMIENTO MANUAL: posición inicial (xilófono) = /s/
            if next_c in ('a', 'e', 'i', 'o', 'u', 'ü', ''):
                fonemas.append('k')
                fonemas.append('s')
                # Ajustar pos_tilde porque "x" genera 2 fonemas
                if pos_tilde > i:
                    pos_tilde += 1
            else:
                fonemas.append('s')
            i += 1
        elif c == 'z':
            fonemas.append(_sibilante_sorda())  # z
            i += 1
        elif c == 'ñ':
            fonemas.append('ɲ')
            i += 1
        elif c == 'j':
            fonemas.append('x')
            i += 1
        elif c == 'y':
            if i == len(p) - 1:
                # "y" final = vocal /i/ (como en "hoy", "rey")
                fonemas.append('i')
            else:
                fonemas.append('ʝ')
            i += 1
        elif c == 'v':
            fonemas.append('b')  # v = b en español
            i += 1
        elif c == 'w':
            # TRATAMIENTO MANUAL: préstamos
            fonemas.append('u')
            i += 1
        elif c in ('a', 'e', 'i', 'o', 'u', 'ü'):
            if i in tilde_en_cerrada:
                hiato_fonema_positions.add(len(fonemas))
            fonemas.append(_vocal_a_fonema(c))
            i += 1
        elif c in ('b', 'd', 'f', 'k', 'l', 'm', 'n', 'p', 's', 't'):
            fonemas.append(c)
            i += 1
        elif c in ('ʝ', 'ɲ', 'θ', 'ɾ', 'ʧ'):
            # Fonemas IPA ya insertados por reglas previas (ej: hie- → ʝe)
            fonemas.append(c)
            i += 1
        elif c == ' ' or c in '.,;:!?¿¡-':
            i += 1
            continue
        else:
            # Carácter desconocido: saltar
            # TRATAMIENTO MANUAL: caracteres no reconocidos
            i += 1
            continue

    return ''.join(fonemas), pos_tilde, hiato_fonema_positions


def _vocal_a_fonema(v: str) -> str:
    return {'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u', 'ü': 'u'}[v]


# ═══════════════════════════════════════════════════════════════════════
# PASO 2: Silabificación
# ═══════════════════════════════════════════════════════════════════════

VOCALES = set('aeiou')
VOCALES_ABIERTAS = set('aeo')
VOCALES_CERRADAS = set('iu')

# Grupos consonánticos inseparables (ataque complejo)
ATAQUES_COMPLEJOS = {
    'bl', 'bɾ', 'kl', 'kɾ', 'dl', 'dɾ',  # dl/dr son raros pero posibles
    'fl', 'fɾ', 'gl', 'gɾ', 'pl', 'pɾ',
    'tɾ',  # 'tl' NO es ataque válido en español peninsular (sí en mexicano)
}


def silabificar(fonemas: str, hiato_positions: set = None) -> list[str]:
    """Divide una secuencia de fonemas en sílabas.

    Aplica las reglas de silabificación del español:
    1. Una consonante entre vocales va con la segunda vocal (a.ba)
    2. Dos consonantes entre vocales: primera con la anterior, segunda con
       la siguiente (an.te), SALVO que formen ataque complejo (a.bɾa)
    3. Tres consonantes: las dos últimas con la siguiente si forman ataque
       complejo (ins.tɾu), si no, solo la última (cons.ta)

    TRATAMIENTO MANUAL NECESARIO:
    - Hiatos vs diptongos (ver nota al inicio del módulo)
    """
    if not fonemas:
        return []

    # Clasificar cada fonema como V (vocal) o C (consonante)
    tipos = ['V' if f in VOCALES else 'C' for f in fonemas]

    # Resolver diptongos/hiatos
    # Regla: cerrada + abierta o abierta + cerrada = diptongo (misma sílaba)
    # Dos abiertas = hiato (sílabas distintas)
    # Dos cerradas = diptongo
    # TRATAMIENTO MANUAL: esta heurística no cubre todos los casos

    silabas = []
    silaba_actual = ""

    i = 0
    while i < len(fonemas):
        f = fonemas[i]
        t = tipos[i]

        if t == 'V':
            silaba_actual += f
            # Mirar si la siguiente vocal forma diptongo
            if i + 1 < len(fonemas) and tipos[i + 1] == 'V':
                v1 = f
                v2 = fonemas[i + 1]
                # Tilde en vocal cerrada fuerza hiato
                _hiato = hiato_positions or set()
                if i in _hiato or (i + 1) in _hiato:
                    # Cerrar sílaba actual y empezar nueva con la siguiente vocal
                    silabas.append(silaba_actual)
                    silaba_actual = ""
                    i += 1
                    continue
                if _es_diptongo(v1, v2):
                    silaba_actual += v2
                    i += 2
                    # Posible triptongo
                    if i < len(fonemas) and tipos[i] == 'V' and fonemas[i] in VOCALES_CERRADAS:
                        silaba_actual += fonemas[i]
                        i += 1
                    continue
                else:
                    # Hiato: dos vocales que no forman diptongo → separar sílabas
                    silabas.append(silaba_actual)
                    silaba_actual = ""
                    i += 1
                    continue
            i += 1
        elif t == 'C':
            # Consonante: decidir si va con la sílaba actual o la siguiente
            # Contar consonantes consecutivas
            cons = ""
            j = i
            while j < len(fonemas) and tipos[j] == 'C':
                cons += fonemas[j]
                j += 1

            if j >= len(fonemas):
                # Consonantes al final de la palabra: van con la sílaba actual
                silaba_actual += cons
                i = j
            elif not silaba_actual:
                # Al inicio de palabra: todas las consonantes van con la primera vocal
                silaba_actual += cons
                i = j
            else:
                # Consonantes entre vocales: aplicar reglas
                n = len(cons)
                if n == 1:
                    # Una consonante: va con la vocal siguiente
                    silabas.append(silaba_actual)
                    silaba_actual = cons
                    i = j
                elif n == 2:
                    if cons in ATAQUES_COMPLEJOS:
                        # Ataque complejo: ambas con la siguiente
                        silabas.append(silaba_actual)
                        silaba_actual = cons
                    else:
                        # Primera con la anterior, segunda con la siguiente
                        silaba_actual += cons[0]
                        silabas.append(silaba_actual)
                        silaba_actual = cons[1]
                    i = j
                elif n == 3:
                    if cons[1:] in ATAQUES_COMPLEJOS:
                        silaba_actual += cons[0]
                        silabas.append(silaba_actual)
                        silaba_actual = cons[1:]
                    else:
                        silaba_actual += cons[:2]
                        silabas.append(silaba_actual)
                        silaba_actual = cons[2]
                    i = j
                else:  # 4+ consonantes (raro)
                    if cons[-2:] in ATAQUES_COMPLEJOS:
                        silaba_actual += cons[:-2]
                        silabas.append(silaba_actual)
                        silaba_actual = cons[-2:]
                    else:
                        silaba_actual += cons[:-1]
                        silabas.append(silaba_actual)
                        silaba_actual = cons[-1]
                    i = j

    if silaba_actual:
        silabas.append(silaba_actual)

    return silabas


def _es_diptongo(v1: str, v2: str) -> bool:
    """Determina si dos vocales forman diptongo.

    TRATAMIENTO MANUAL: Esta regla es una aproximación.
    No cubre todos los hiatos (ej: "caer" = /ka.eɾ/, no */kaeɾ/).
    """
    if v1 in VOCALES_CERRADAS and v2 in VOCALES_ABIERTAS:
        return True  # ia, ie, io, ua, ue, uo
    if v1 in VOCALES_ABIERTAS and v2 in VOCALES_CERRADAS:
        return True  # ai, ei, oi, au, eu, ou
    if v1 in VOCALES_CERRADAS and v2 in VOCALES_CERRADAS and v1 != v2:
        return True  # iu, ui
    return False  # dos abiertas = hiato


# ═══════════════════════════════════════════════════════════════════════
# PASO 3: Acentuación
# ═══════════════════════════════════════════════════════════════════════

# Palabras funcionales átonas (no llevan acento prosódico)
# TRATAMIENTO MANUAL: esta lista puede ser incompleta
ATONAS = {
    'el', 'la', 'lo', 'los', 'las', 'un', 
    'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin',
    'me', 'te', 'se', 'le', 'les', 'nos', 'os',
    'mi', 'tu', 'su', 'que', 'y', 'e', 'o', 'u', 'ni',
}


def acentuar(silabas: list[str], palabra_original: str, pos_tilde: int) -> int:
    """Determina qué sílaba lleva el acento y retorna su índice.

    Retorna -1 si la palabra es átona.
    """
    if palabra_original.lower().strip() in ATONAS:
        return -1

    if not silabas:
        return -1

    # Si hay tilde explícita, la sílaba que la contiene es la tónica
    if pos_tilde >= 0:
        # Encontrar en qué sílaba cae la posición de la tilde
        pos = 0
        fonemas_concat = ''.join(silabas)
        for idx, sil in enumerate(silabas):
            for f in sil:
                if pos == pos_tilde and f in VOCALES:
                    return idx
                pos += 1
        # Fallback: buscar la vocal tildada
        return len(silabas) - 2 if len(silabas) > 1 else 0

    # Reglas generales del español:
    ultima = silabas[-1]
    ultimo_fonema = ultima[-1] if ultima else ''

    if ultimo_fonema in VOCALES or ultimo_fonema in ('n', 's'):
        # Llana (penúltima sílaba)
        return max(0, len(silabas) - 2)
    else:
        # Aguda (última sílaba)
        return len(silabas) - 1


# ═══════════════════════════════════════════════════════════════════════
# PASO 4: Validación
# ═══════════════════════════════════════════════════════════════════════

# Grafemas no españoles (indican préstamo/extranjerismo)
_GRAFEMAS_EXTRANJEROS = re.compile(r'[wW]|zz|kk|sh|sch|ph|th(?!u)')

# Ataques válidos en español (consonante o grupo consonántico inicial de sílaba)
_ATAQUES_VALIDOS = (
    # Consonante simple
    {'b', 'd', 'f', 'g', 'k', 'l', 'm', 'n', 'ɲ', 'p', 'r', 'ɾ', 's', 't',
     'θ', 'x', 'ʧ', 'ʝ'}
    # Grupos consonánticos
    | ATAQUES_COMPLEJOS
)

# Codas válidas en español (máximo 2 consonantes)
_CODAS_SIMPLES = {'b', 'd', 'f', 'g', 'k', 'l', 'm', 'n', 'ɲ', 'p', 'ɾ', 'r', 's', 't', 'θ', 'x'}
_CODAS_DOBLES = {'ns', 'ks', 'bs', 'ds', 'ls', 'ɾs', 'ɾn', 'st'}


def validar_palabra(palabra: str) -> str | None:
    """Valida que la palabra sea transcribible en español.

    Retorna None si la palabra es válida, o un mensaje de error si no lo es.
    """
    p = palabra.lower().strip()

    # Grafemas extranjeros
    if _GRAFEMAS_EXTRANJEROS.search(p):
        return f"'{palabra}' contiene grafemas no españoles y no puede transcribirse con las reglas del español peninsular."

    return None


def validar_silabas(silabas: list[str], palabra: str) -> str | None:
    """Valida que las sílabas generadas sean compatibles con la fonología del español.

    Retorna None si son válidas, o un mensaje de error si no.
    """
    for sil in silabas:
        # Separar ataque, núcleo y coda
        fonemas = list(sil)

        # Sílaba demasiado larga (más de 5 fonemas es sospechoso)
        if len(fonemas) > 5:
            return f"'{palabra}' produce la sílaba /{sil}/ con {len(fonemas)} fonemas, lo cual es inusual en español."

        # Extraer consonantes iniciales (ataque)
        ataque = ""
        i = 0
        while i < len(fonemas) and fonemas[i] not in VOCALES:
            ataque += fonemas[i]
            i += 1

        # Validar ataque
        if len(ataque) > 2:
            return f"'{palabra}' produce un ataque silábico /{ataque}/ con más de 2 consonantes, lo cual no es válido en español."
        if len(ataque) == 2 and ataque not in ATAQUES_COMPLEJOS:
            return f"'{palabra}' produce el ataque silábico /{ataque}/ que no es un grupo consonántico válido en español."

        # Extraer núcleo (vocales)
        nucleo = ""
        while i < len(fonemas) and fonemas[i] in VOCALES:
            nucleo += fonemas[i]
            i += 1

        # Validar núcleo vocálico
        if len(nucleo) > 3:
            return f"'{palabra}' produce la sílaba /{sil}/ con {len(nucleo)} vocales consecutivas, lo cual no es válido en español (máximo 3: triptongo)."
        if len(nucleo) == 3:
            # Triptongo: cerrada + abierta + cerrada
            if nucleo[0] not in VOCALES_CERRADAS or nucleo[1] not in VOCALES_ABIERTAS or nucleo[2] not in VOCALES_CERRADAS:
                return f"'{palabra}' produce la sílaba /{sil}/ con el grupo vocálico /{nucleo}/ que no es un triptongo válido en español (debe ser cerrada + abierta + cerrada)."
        if len(nucleo) == 2:
            # Diptongo: cerrada+abierta, abierta+cerrada, o cerrada+cerrada
            if nucleo[0] in VOCALES_ABIERTAS and nucleo[1] in VOCALES_ABIERTAS:
                return f"'{palabra}' produce la sílaba /{sil}/ con dos vocales abiertas /{nucleo}/ en la misma sílaba, lo cual no es válido en español (deberían formar hiato)."

        # Extraer coda (consonantes finales)
        coda = ""
        while i < len(fonemas) and fonemas[i] not in VOCALES:
            coda += fonemas[i]
            i += 1

        # Validar coda
        if len(coda) > 2:
            return f"'{palabra}' produce una coda silábica /{coda}/ con más de 2 consonantes, lo cual no es válido en español."
        if len(coda) == 1 and coda not in _CODAS_SIMPLES:
            return f"'{palabra}' produce la coda /{coda}/ que no es habitual en español."
        if len(coda) == 2 and coda not in _CODAS_DOBLES:
            return f"'{palabra}' produce la coda /{coda}/ que no es un grupo consonántico habitual en coda en español."

    return None


# ═══════════════════════════════════════════════════════════════════════
# PASO 5: Formateo final
# ═══════════════════════════════════════════════════════════════════════

def transcribir_palabra(palabra: str) -> str | tuple:
    """Transcribe una palabra ortográfica a notación fonológica.

    Returns:
        str con la transcripción si es válida, o
        tuple (None, error_msg) si la palabra no es transcribible.
    """
    if not palabra.strip():
        return ""

    # Validar grafemas
    error = validar_palabra(palabra)
    if error:
        return (None, error)

    fonemas_str, pos_tilde, hiato_positions = grafema_a_fonema(palabra)
    if not fonemas_str:
        return ""

    silabas = silabificar(fonemas_str, hiato_positions)
    if not silabas:
        return fonemas_str

    # Validar sílabas
    error = validar_silabas(silabas, palabra)
    if error:
        return (None, error)

    acento_idx = acentuar(silabas, palabra, pos_tilde)

    # Formatear con puntos y acento
    resultado = []
    for idx, sil in enumerate(silabas):
        if idx == acento_idx:
            resultado.append("'" + sil)
        else:
            resultado.append(sil)

    return '.'.join(resultado)


def transcribir(frase: str) -> str | tuple:
    """Transcribe una frase completa a notación fonológica.

    Retorna la transcripción entre barras: / ... /
    O una tupla (None, error_msg) si alguna palabra no es transcribible.

    Ejemplo:
        transcribir("El niño come pan") → / el 'ni.ɲo 'ko.me 'pan /
    """
    # Limpiar la frase
    frase = frase.strip()
    if not frase:
        return ""

    # Separar en palabras (eliminar puntuación)
    palabras = re.findall(r"[a-záéíóúüñ]+", frase.lower())

    errores = []
    transcripciones = []
    for p in palabras:
        t = transcribir_palabra(p)
        if isinstance(t, tuple):
            # Error de validación
            errores.append(t[1])
        elif t:
            transcripciones.append(t)

    if errores:
        return (None, "\n".join(errores))

    if not transcripciones:
        return ""

    return "/ " + " ".join(transcripciones) + " /"


# ═══════════════════════════════════════════════════════════════════════
# TRANSCRIPCIÓN FONÉTICA (fonológica → fonética)
# ═══════════════════════════════════════════════════════════════════════
#
# Dada una transcripción fonológica ya silabificada, aplica las reglas
# alofónicas del español peninsular para producir la transcripción fonética.
#
# Se implementa por fases:
#   Fase 1: Vocales (reglas de semiconsonante/semivocal)
#   Fase 2: Consonantes (TODO: oclusivas, fricativas, nasales, etc.)
# ═══════════════════════════════════════════════════════════════════════


_DIGRAFOS_FONETICOS = {'tʃ', 'β̞', 'ð̞', 'ɣ̞', 'n̪', 'n̟', 'nʲ', 'l̪', 'l̟', 'i̯', 'u̯'}

def _tokenizar_fonemas(texto: str) -> list[str]:
    """Tokeniza una cadena de fonemas, reconociendo dígrafos como 'tʃ', 'β̞', etc."""
    fonemas = []
    i = 0
    while i < len(texto):
        # Try 2-char and 3-char digraphs
        matched = False
        for length in (3, 2):
            if i + length <= len(texto) and texto[i:i+length] in _DIGRAFOS_FONETICOS:
                fonemas.append(texto[i:i+length])
                i += length
                matched = True
                break
        if not matched:
            fonemas.append(texto[i])
            i += 1
    return fonemas


def _analizar_silaba(sil: str) -> dict:
    """Analiza una sílaba y devuelve sus componentes.

    Returns dict con:
        'ataque': consonantes iniciales (str)
        'nucleo': vocales del núcleo (str) — puede ser 1, 2 o 3 vocales
        'coda': consonantes finales (str)
        'fonemas': lista de fonemas individuales
        'posiciones': lista de dicts con 'fonema', 'tipo' ('C'/'V'), 'rol'
            rol puede ser: 'ataque', 'nucleo', 'prenuclear', 'postnuclear', 'coda'
    """
    fonemas = _tokenizar_fonemas(sil)
    posiciones = []
    i = 0

    # Ataque: consonantes iniciales
    while i < len(fonemas) and fonemas[i] not in VOCALES:
        posiciones.append({'fonema': fonemas[i], 'tipo': 'C', 'rol': 'ataque'})
        i += 1

    # Núcleo vocálico: determinar roles
    vocales_inicio = i
    nucleo_vocales = []
    while i < len(fonemas) and fonemas[i] in VOCALES:
        nucleo_vocales.append(fonemas[i])
        i += 1

    # Asignar roles a las vocales
    if len(nucleo_vocales) == 1:
        # Vocal sola: siempre núcleo
        posiciones.append({'fonema': nucleo_vocales[0], 'tipo': 'V', 'rol': 'nucleo'})
    elif len(nucleo_vocales) == 2:
        v1, v2 = nucleo_vocales
        if v1 in VOCALES_CERRADAS and v2 in VOCALES_ABIERTAS:
            # Diptongo creciente: cerrada es prenuclear, abierta es núcleo
            posiciones.append({'fonema': v1, 'tipo': 'V', 'rol': 'prenuclear'})
            posiciones.append({'fonema': v2, 'tipo': 'V', 'rol': 'nucleo'})
        elif v1 in VOCALES_ABIERTAS and v2 in VOCALES_CERRADAS:
            # Diptongo decreciente: abierta es núcleo, cerrada es postnuclear
            posiciones.append({'fonema': v1, 'tipo': 'V', 'rol': 'nucleo'})
            posiciones.append({'fonema': v2, 'tipo': 'V', 'rol': 'postnuclear'})
        elif v1 in VOCALES_CERRADAS and v2 in VOCALES_CERRADAS:
            # Dos cerradas: primera prenuclear, segunda núcleo
            posiciones.append({'fonema': v1, 'tipo': 'V', 'rol': 'prenuclear'})
            posiciones.append({'fonema': v2, 'tipo': 'V', 'rol': 'nucleo'})
        else:
            # Dos abiertas (no debería ocurrir en diptongo, pero por seguridad)
            posiciones.append({'fonema': v1, 'tipo': 'V', 'rol': 'nucleo'})
            posiciones.append({'fonema': v2, 'tipo': 'V', 'rol': 'nucleo'})
    elif len(nucleo_vocales) == 3:
        # Triptongo: cerrada + abierta + cerrada
        posiciones.append({'fonema': nucleo_vocales[0], 'tipo': 'V', 'rol': 'prenuclear'})
        posiciones.append({'fonema': nucleo_vocales[1], 'tipo': 'V', 'rol': 'nucleo'})
        posiciones.append({'fonema': nucleo_vocales[2], 'tipo': 'V', 'rol': 'postnuclear'})

    # Coda: consonantes finales
    while i < len(fonemas) and fonemas[i] not in VOCALES:
        posiciones.append({'fonema': fonemas[i], 'tipo': 'C', 'rol': 'coda'})
        i += 1

    return {
        'fonemas': fonemas,
        'posiciones': posiciones,
    }


def _vocal_a_alofono(fonema: str, rol: str, contexto: dict = None) -> str:
    """Convierte un fonema vocálico a su alófono según la posición en la sílaba.

    Reglas:
        /a/ → [a] siempre
        /e/ → [e] siempre
        /o/ → [o] siempre
        /i/ → [i] núcleo, [j] prenuclear, [i̯] postnuclear
        /u/ → [u] núcleo, [w] prenuclear, [u̯] postnuclear

    Si nasalizacion_vocalica está activada:
        Vocal ante nasal en coda o entre nasales → se nasaliza (ej: [ã])

    Si s_coda == 'alargamiento':
        Vocal seguida de /s/ en coda → se alarga (ej: [aː])
    """
    NASALES = {'m', 'n', 'ɲ'}
    DIACRITICO_NASAL = '\u0303'   # combining tilde: ã, ẽ, ĩ, õ, ũ
    DIACRITICO_LARGO = 'ː'

    # Base allophone
    if fonema == 'i':
        if rol == 'prenuclear':
            base = 'j'
        elif rol == 'postnuclear':
            base = 'i̯'
        else:
            base = 'i'
    elif fonema == 'u':
        if rol == 'prenuclear':
            base = 'w'
        elif rol == 'postnuclear':
            base = 'u̯'
        else:
            base = 'u'
    else:
        base = fonema

    if contexto is None:
        return base

    next_f = contexto.get('next')
    next_rol = contexto.get('next_rol')

    # Nasalización vocálica: vocal ante nasal en coda, o entre nasales
    if _config['nasalizacion_vocalica'] and rol == 'nucleo':
        prev_f = contexto.get('prev')
        if next_f in NASALES and next_rol == 'coda':
            base = base + DIACRITICO_NASAL
        elif prev_f in NASALES and next_f in NASALES:
            base = base + DIACRITICO_NASAL

    # Alargamiento vocálico: vocal seguida de /s/ en coda que se omite
    if _config['s_coda'] == 'alargamiento' and rol == 'nucleo':
        if next_f == 's' and next_rol == 'coda':
            base = base + DIACRITICO_LARGO

    return base


def _consonante_a_alofono(fonema: str, rol: str, contexto: dict) -> str:
    """Convierte un fonema consonántico a su alófono según contexto.

    contexto debe incluir:
        'prev': fonema anterior (None si inicio de enunciado)
        'next': fonema siguiente (None si final)
        'prev_rol': rol del fonema anterior
        'is_word_start': True si es el primer fonema de la palabra
        'is_utterance_start': True si es inicio de enunciado (tras pausa)
    """
    prev = contexto.get('prev')
    next_f = contexto.get('next')
    is_start = contexto.get('is_utterance_start', False)

    # Nasales: /m/, /n/, /ɲ/
    BILABIALES = {'p', 'b', 'm'}
    LABIODENTALES = {'f'}
    INTERDENTALES = {'θ'}
    DENTALES = {'t', 'd'}
    PALATALES = {'ʧ', 'ʝ', 'ɲ'}
    VELARES = {'k', 'g', 'x'}
    NASALES = {'m', 'n', 'ɲ'}
    LATERALES = {'l'}

    # ── Oclusivas ──

    if fonema == 'p':
        if rol == 'coda':
            return 'β̞'   # implosiva → aproximante
        return 'p'

    if fonema == 'b':
        if is_start or prev in NASALES:
            return 'b'   # tras pausa o nasal → oclusivo
        return 'β̞'       # resto → aproximante

    if fonema == 't':
        if rol == 'coda':
            return 'ð̞'   # implosiva → aproximante
        return 't'

    if fonema == 'd':
        if is_start or prev in NASALES or prev in LATERALES:
            return 'd'   # tras pausa, nasal o lateral → oclusivo
        return 'ð̞'       # resto → aproximante

    if fonema == 'k':
        if rol == 'coda':
            return 'ɣ̞'   # implosiva → aproximante
        return 'k'

    if fonema == 'g':
        if is_start or prev in NASALES:
            return 'g'   # tras pausa o nasal → oclusivo
        return 'ɣ̞'       # resto → aproximante

    # ── Africada ──

    if fonema == 'ʧ':
        return 'ʧ'       # siempre

    # ── Fricativas ──

    if fonema == 'f':
        return 'f'       # siempre

    if fonema == 'θ':
        # Seseo: /θ/ → [s] (no debería llegar aquí si seseo, pero por seguridad)
        if _config['sibilantes'] == 'seseo':
            return 's'
        return 'θ'

    if fonema == 's':
        # Ceceo: /s/ → [θ] en todas las posiciones
        if _config['sibilantes'] == 'ceceo':
            alofono_s = 'θ'
        else:
            alofono_s = 's'
        # Tratamiento de /s/ en coda
        if rol == 'coda':
            modo_coda = _config['s_coda']
            if modo_coda == 'aspiracion':
                return 'h'
            elif modo_coda == 'omision':
                return ''    # se elimina
            elif modo_coda == 'alargamiento':
                return ''    # se elimina (el alargamiento se aplica a la vocal)
            # 'sibilante': se mantiene
        return alofono_s

    if fonema == 'ʝ':
        if prev in NASALES:
            return 'ʤ'   # tras nasal → africado
        return 'ʝ'        # resto → fricativo

    if fonema == 'x':
        return 'x'       # siempre

    # ── Nasales ──

    if fonema == 'm':
        return 'm'       # siempre

    if fonema == 'ɲ':
        return 'ɲ'       # siempre

    if fonema == 'n':
        if next_f in BILABIALES:
            return 'm'   # ante bilabial
        if next_f in LABIODENTALES:
            return 'ɱ'   # ante labiodental
        if next_f in INTERDENTALES:
            return 'n̟'   # ante interdental
        if next_f in DENTALES:
            return 'n̪'   # ante dental
        if next_f in PALATALES:
            return 'nʲ'  # ante palatal
        if next_f in VELARES:
            return 'ŋ'   # ante velar
        return 'n'        # resto

    # ── Laterales ──

    if fonema == 'l':
        if next_f in INTERDENTALES:
            return 'l̟'   # ante interdental
        if next_f in DENTALES:
            return 'l̪'   # ante dental
        return 'l'        # resto

    # ── Vibrantes ──

    if fonema == 'ɾ':
        if rol == 'coda':
            return 'ɹ'   # final de sílaba → aproximante
        return 'ɾ'        # ante vocal → vibrante simple

    if fonema == 'r':
        return 'r'        # siempre vibrante múltiple

    # Fonema no reconocido: devolver sin cambios
    return fonema


def transcripcion_fonetica_palabra(palabra: str, is_utterance_start: bool = True,
                                   prev_word_last_fonema: str = None,
                                   next_word_first_fonema: str = None) -> str | tuple:
    """Genera la transcripción fonética de una palabra.

    Args:
        palabra: palabra ortográfica
        is_utterance_start: True si la palabra está al inicio del enunciado
            (tras pausa). Afecta a /b,d,g/ que son oclusivos tras pausa.
        prev_word_last_fonema: último fonema de la palabra anterior (para
            contexto inter-palabra). Afecta a /b,d,g,ʝ/ al inicio de palabra.
        next_word_first_fonema: primer fonema de la palabra siguiente (para
            contexto inter-palabra). Afecta a /n,l/ al final de palabra.

    Returns str con transcripción fonética o tuple (None, error).
    """
    if not palabra.strip():
        return ""

    # Primero obtener la transcripción fonológica (silabificada)
    resultado = transcribir_palabra(palabra)
    if isinstance(resultado, tuple):
        return resultado  # error
    if not resultado:
        return ""

    # Separar las sílabas y analizar cada una
    silabas_raw = resultado.split('.')
    acentos = []
    analisis_todas = []
    for sil in silabas_raw:
        sil_limpia = sil.lstrip("'")
        acentos.append("'" if sil.startswith("'") else "")
        analisis_todas.append(_analizar_silaba(sil_limpia))

    # Construir secuencia plana de (fonema, rol, tipo, idx_silaba)
    secuencia = []
    for idx_sil, analisis in enumerate(analisis_todas):
        for pos in analisis['posiciones']:
            secuencia.append({
                'fonema': pos['fonema'],
                'rol': pos['rol'],
                'tipo': pos['tipo'],
                'silaba_idx': idx_sil,
            })

    # Convertir cada fonema con contexto completo
    alofonos = []
    for i, item in enumerate(secuencia):
        prev_fonema = secuencia[i - 1]['fonema'] if i > 0 else prev_word_last_fonema
        next_fonema = secuencia[i + 1]['fonema'] if i + 1 < len(secuencia) else next_word_first_fonema
        is_first = (i == 0)

        next_rol = secuencia[i + 1]['rol'] if i + 1 < len(secuencia) else None
        if item['tipo'] == 'V':
            contexto_v = {
                'prev': prev_fonema,
                'next': next_fonema,
                'next_rol': next_rol,
            }
            alofono = _vocal_a_alofono(item['fonema'], item['rol'], contexto_v)
        else:
            contexto = {
                'prev': prev_fonema,
                'next': next_fonema,
                'is_utterance_start': is_utterance_start and is_first,
            }
            alofono = _consonante_a_alofono(item['fonema'], item['rol'], contexto)

        alofonos.append({
            'alofono': alofono,
            'silaba_idx': item['silaba_idx'],
        })

    # Reagrupar por sílaba y formatear
    silabas_foneticas = []
    for idx_sil in range(len(silabas_raw)):
        sil_alofonos = ''.join(
            a['alofono'] for a in alofonos if a['silaba_idx'] == idx_sil
        )
        silabas_foneticas.append(acentos[idx_sil] + sil_alofonos)

    return '.'.join(silabas_foneticas)


def transcripcion_fonetica_desde_fonologica(transcripcion_fonologica: str,
                                             is_utterance_start: bool = True,
                                             prev_word_last_fonema: str = None,
                                             next_word_first_fonema: str = None) -> str:
    """Genera la transcripción fonética a partir de una transcripción fonológica.

    A diferencia de transcripcion_fonetica_palabra(), esta función NO parte
    de la ortografía sino de una transcripción fonológica ya hecha
    (ej: "'u.pa", "da.'ɾiθ"). Esto es necesario cuando se trabaja con
    habla atípica: la fonética debe derivarse de lo que el hablante
    realmente produjo, no de lo que debería haber dicho.

    Args:
        transcripcion_fonologica: transcripción fonológica con sílabas
            separadas por '.' y acento marcado con "'" (ej: "'ka.sa")
        is_utterance_start: True si es inicio de enunciado
        prev_word_last_fonema: último fonema de la palabra anterior
        next_word_first_fonema: primer fonema de la palabra siguiente

    Returns:
        str con la transcripción fonética (sin corchetes)
    """
    if not transcripcion_fonologica or not transcripcion_fonologica.strip():
        return ""

    resultado = transcripcion_fonologica.strip().strip('/')

    # Separar las sílabas y analizar cada una
    silabas_raw = resultado.split('.')
    acentos = []
    analisis_todas = []
    for sil in silabas_raw:
        sil_limpia = sil.lstrip("'").lstrip("ˈ")
        acentos.append("'" if (sil.startswith("'") or sil.startswith("ˈ")) else "")
        analisis_todas.append(_analizar_silaba(sil_limpia))

    # Construir secuencia plana de (fonema, rol, tipo, idx_silaba)
    secuencia = []
    for idx_sil, analisis in enumerate(analisis_todas):
        for pos in analisis['posiciones']:
            secuencia.append({
                'fonema': pos['fonema'],
                'rol': pos['rol'],
                'tipo': pos['tipo'],
                'silaba_idx': idx_sil,
            })

    # Convertir cada fonema con contexto completo
    alofonos = []
    for i, item in enumerate(secuencia):
        prev_fonema = secuencia[i - 1]['fonema'] if i > 0 else prev_word_last_fonema
        next_fonema = secuencia[i + 1]['fonema'] if i + 1 < len(secuencia) else next_word_first_fonema
        is_first = (i == 0)

        next_rol = secuencia[i + 1]['rol'] if i + 1 < len(secuencia) else None
        if item['tipo'] == 'V':
            contexto_v = {
                'prev': prev_fonema,
                'next': next_fonema,
                'next_rol': next_rol,
            }
            alofono = _vocal_a_alofono(item['fonema'], item['rol'], contexto_v)
        else:
            contexto = {
                'prev': prev_fonema,
                'next': next_fonema,
                'is_utterance_start': is_utterance_start and is_first,
            }
            alofono = _consonante_a_alofono(item['fonema'], item['rol'], contexto)

        alofonos.append({
            'alofono': alofono,
            'silaba_idx': item['silaba_idx'],
        })

    # Reagrupar por sílaba y formatear
    silabas_foneticas = []
    for idx_sil in range(len(silabas_raw)):
        sil_alofonos = ''.join(
            a['alofono'] for a in alofonos if a['silaba_idx'] == idx_sil
        )
        silabas_foneticas.append(acentos[idx_sil] + sil_alofonos)

    return '.'.join(silabas_foneticas)


def transcripcion_fonetica(frase: str) -> str | tuple:
    """Genera la transcripción fonética de una frase.

    Returns la transcripción entre corchetes: [ ... ]
    O tuple (None, error) si alguna palabra no es transcribible.

    Nota: la primera palabra se trata como inicio de enunciado (tras pausa).
    Las siguientes palabras no: /b,d,g/ al inicio de palabra intermedia
    dependen del fonema final de la palabra anterior.
    """
    frase = frase.strip()
    if not frase:
        return ""

    palabras = re.findall(r"[a-záéíóúüñ]+", frase.lower())

    # Pre-calcular fonemas de cada palabra para contexto inter-palabra
    fonemas_por_palabra = []
    for p in palabras:
        resultado = grafema_a_fonema(p)
        fonemas_por_palabra.append(resultado[0] if resultado[0] else "")

    errores = []
    transcripciones = []
    prev_last_fonema = None
    for idx, p in enumerate(palabras):
        is_start = (idx == 0)
        # Primer fonema de la siguiente palabra
        next_first = fonemas_por_palabra[idx + 1][0] if idx + 1 < len(palabras) and fonemas_por_palabra[idx + 1] else None
        t = transcripcion_fonetica_palabra(
            p, is_utterance_start=is_start,
            prev_word_last_fonema=prev_last_fonema,
            next_word_first_fonema=next_first
        )
        if isinstance(t, tuple):
            errores.append(t[1])
        elif t:
            transcripciones.append(t)
        # Último fonema para la siguiente palabra
        if fonemas_por_palabra[idx]:
            prev_last_fonema = fonemas_por_palabra[idx][-1]

    if errores:
        return (None, "\n".join(errores))

    if not transcripciones:
        return ""

    return "[ " + " ".join(transcripciones) + " ]"


# ═══════════════════════════════════════════════════════════════════════
# Tests básicos
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        texto = " ".join(sys.argv[1:])
        resultado = transcribir(texto)
        if isinstance(resultado, tuple):
            print(f"Error: {resultado[1]}")
        else:
            print(resultado)
        sys.exit(0)

    tests = [
        ("mesa", "/ 'me.sa /"),
        ("pan", "/ 'pan /"),
        ("encender", "/ en.θen.'deɾ /"),
        ("comprar", "/ kom.'pɾaɾ /"),
        ("meseta", "/ me.'se.ta /"),
        ("niño", "/ 'ni.ɲo /"),
        ("averiguar", "/ a.be.ɾi.'guaɾ /"),
        ("estudiar", "/ es.tu.'diaɾ /"),
        ("chilla", "/ 'ʧi.ʝa /"),
        ("caña", "/ 'ka.ɲa /"),
        ("cielo", "/ 'θie.lo /"),
        ("zapato", "/ θa.'pa.to /"),
        ("El niño come pan", "/ el 'ni.ɲo 'ko.me 'pan /"),
        ("sueña", "/ 'sue.ɲa /"),
        ("kosilatroque", "/ ko.si.la.'tɾo.ke /"),
        ("menciabiso","/ men.θia.'bi.so /"),
        ("diario","/ 'dia.ɾio /"),
        ("lío","/ 'li.o /"),
        ("lio","/ 'lio /"),
        ("dío","/ 'di.o /"),
        ("dio","/ 'dio /"),
        ("rey","/ 'rei /"),
        ("reino","/ 'rei.no /"),
        ("saxofón","/ sak.so.'fon /"),
        ("sexto","/ 'ses.to /"),
        ("averigüe","/ a.be.'ɾi.gue /"),
        ("averigüéis","/ a.be.ɾi.'gueis /"),
    ]

    print("=== Tests de transcripción fonológica ===\n")
    ok = 0
    fallos = []
    for entrada, esperado in tests:
        resultado = transcribir(entrada)
        if resultado == esperado:
            ok += 1
            print(f"  ✓ '{entrada}'")
        else:
            fallos.append((entrada, esperado, resultado))

    print(f"\nResultado: {ok}/{len(tests)} correctos")

    if fallos:
        print(f"\n=== {len(fallos)} FALLOS ===\n")
        for entrada, esperado, resultado in fallos:
            print(f"  ✗ '{entrada}'")
            print(f"    Esperado:  {esperado}")
            print(f"    Obtenido:  {resultado}")
            print()
