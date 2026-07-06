"""
Ejercicios de transcripción fonológica y fonética.

Cuatro modos de ejercicio:
  - Fonológica solo + Habla típica
  - Fonológica solo + Habla con errores
  - Fonológica + Fonética + Habla típica
  - Fonológica + Fonética + Habla con errores

Niveles 1-6 de dificultad ortográfica.
"""

import re
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .banco_palabras import BANCO_PALABRAS
from .generador import generar_errores
from .silaba import reconstruir_transcripcion, parsear_silabas
from .generador_oraciones import generar_oraciones


# ═══════════════════════════════════════════════════════════════════════
# CLASIFICACIÓN POR NIVEL
# ═══════════════════════════════════════════════════════════════════════

def clasificar_nivel_transcripcion(ortografia: str) -> int:
    """Clasifica una palabra en niveles 1-6 de dificultad de transcripción."""
    ort = ortografia.lower()

    # Level 6: x (any position — /ks/ or /s/), ps- initial, cc→/kθ/
    if ort.startswith('ps'):
        return 6
    if 'x' in ort:
        return 6
    if 'cc' in ort:
        return 6

    # Detect features
    has_h_muda = bool(re.search(r'(?<!c)h', ort))
    has_hie_hue = bool(re.match(r'hie|hue', ort))
    has_diphthong = bool(re.search(r'[iu][aeoáéó]|[aeoáéó][iu]|[iu][éá]|[éáó][iu]', ort))
    has_hiatus_tilde = bool(re.search(r'[íú][aeou]|[aeou][íú]', ort))

    has_ll = 'll' in ort
    has_ch = 'ch' in ort
    has_rr = 'rr' in ort
    has_qu = 'qu' in ort
    has_gu_ei = bool(re.search(r'gu[eéií]', ort))
    has_digrafo = has_ll or has_ch or has_rr or has_qu or has_gu_ei

    has_c_ei = bool(re.search(r'c[eéiíü]', ort)) and not has_ch
    has_g_ei = bool(re.search(r'(?<!u)g[eéií]', ort))
    has_contextual = has_c_ei or has_g_ei

    has_v = 'v' in ort
    has_z = 'z' in ort
    has_j = 'j' in ort
    has_ñ = 'ñ' in ort
    has_simple_div = has_v or has_z or has_j or has_ñ
    num_simple = sum([has_v, has_z, has_j, has_ñ])

    # 4+ distinct feature types → 6
    total_features = num_simple + has_digrafo + has_contextual + has_h_muda + has_diphthong
    if total_features >= 4:
        return 6

    # 5+ sílabas with multiple divergences → 6
    num_silabas = len(re.findall(r'[aeiouáéíóúü]+', ort))
    if num_silabas >= 5 and total_features >= 2:
        return 6

    # Level 5: h muda, hie-/hue-, hiatus with tilde, diphthong + divergence
    if has_hie_hue or has_hiatus_tilde:
        return 5
    if has_h_muda:
        return 5
    if has_diphthong and (has_contextual or has_digrafo or has_simple_div):
        return 5
    if has_diphthong:
        return 5

    # Level 4: contextual (c+e/i, g+e/i) — combined with others → 5
    if has_contextual:
        if has_digrafo or has_simple_div:
            return 5
        return 4

    # Level 3: digraphs
    if has_digrafo:
        if has_simple_div:
            return 4
        return 3

    # Level 2: simple divergences (v, z, j, ñ)
    if has_simple_div:
        return 2

    # Level 1: transparent
    return 1


# ═══════════════════════════════════════════════════════════════════════
# SELECCIÓN DE PALABRAS POR NIVEL
# ═══════════════════════════════════════════════════════════════════════

# Pre-classify all words in the bank
_PALABRAS_POR_NIVEL = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}

for p in BANCO_PALABRAS:
    nivel = clasificar_nivel_transcripcion(p['ortografia'])
    p_with_nivel = {**p, 'nivel_transcripcion': nivel}
    _PALABRAS_POR_NIVEL[nivel].append(p_with_nivel)


def palabras_por_nivel(nivel: int) -> list[dict]:
    """Devuelve las palabras clasificadas en un nivel dado."""
    return _PALABRAS_POR_NIVEL.get(nivel, [])


def resumen_niveles() -> str:
    """Resumen de cuántas palabras hay por nivel."""
    lineas = ["Palabras por nivel de transcripción:"]
    for n in range(1, 7):
        lineas.append(f"  Nivel {n}: {len(_PALABRAS_POR_NIVEL[n])} palabras")
    lineas.append(f"  Nivel 7: {len(_ORACIONES_CORTAS)} oraciones cortas")
    lineas.append(f"  Nivel 8: {len(_ORACIONES_LARGAS)} oraciones largas")
    return '\n'.join(lineas)


# ═══════════════════════════════════════════════════════════════════════
# GENERACIÓN DE EJERCICIOS
# ═══════════════════════════════════════════════════════════════════════

_NIVEL_NOMBRES = {
    1: "Transparente",
    2: "Divergencias simples",
    3: "Dígrafos",
    4: "Contextuales",
    5: "H muda y diptongos",
    6: "Combinaciones complejas",
    7: "Oraciones cortas",
    8: "Oraciones largas",
}

_NIVEL_DESCRIPCIONES = {
    1: "Cada letra corresponde directamente a un fonema. No hay grafías divergentes.",
    2: "Contienen una grafía que no se transcribe como se escribe: v→/b/, z→/θ/, j→/x/, ñ→/ɲ/.",
    3: "Contienen dígrafos: ll→/ʝ/, ch→/tʃ/, rr→/r/, qu→/k/, gu+e,i→/g/.",
    4: "La misma letra se transcribe de forma diferente según el contexto: c→/θ/ o /k/, g→/x/ o /g/.",
    5: "Incluyen h muda, hie-→/ʝe/, diptongos (ia, ie, ue...) o hiatos con tilde (í, ú).",
    6: "Combinaciones complejas: x→/ks/ o /s/, ps-→/s/, cc→/kθ/, múltiples divergencias.",
    7: "Oraciones cortas (3-5 palabras). Transcribe la oración completa.",
    8: "Oraciones largas (6+ palabras). Transcribe la oración completa.",
}

_NIVEL_PISTAS = {
    1: None,
    2: "Recuerda: v=/b/, z=/θ/, j=/x/, ñ=/ɲ/",
    3: "Recuerda: ll=/ʝ/, ch=/tʃ/, rr=/r/, qu=/k/, gu+e,i: la u no suena",
    4: "Recuerda: c+e,i=/θ/ pero c+a,o,u=/k/; g+e,i=/x/ pero g+a,o,u=/g/",
    5: "Recuerda: la h no se pronuncia; hie-=/ʝe/; diptongos van en la misma sílaba",
    6: "x entre vocales=/ks/; x+consonante=/s/; ps-: la p no suena; cc=/kθ/",
    7: "Transcribe cada palabra de la oración con separación silábica y acento.",
    8: "Transcribe cada palabra de la oración con separación silábica y acento.",
}

# Número de errores por nivel (para habla con errores)
_ERRORES_POR_NIVEL = {
    1: 1, 2: 1, 3: 1, 4: 1,
    5: 2, 6: 2,
    7: 3, 8: 3,
}

# ── Banco de oraciones para niveles 7 y 8 ─────────────────────────────

_ORACIONES_CORTAS = [
    ("El gato come pan", "el 'ga.to 'ko.me 'pan"),
    ("La niña tiene sed", "la 'ni.ɲa 'tie.ne 'sed"),
    ("Mi casa es grande", "mi 'ka.sa es 'gɾan.de"),
    ("Voy a la playa", "'boi a la 'pla.ʝa"),
    ("Quiero un vaso de agua", "'kie.ɾo un 'ba.so de 'a.gua"),
    ("El perro corre mucho", "el 'pe.ro 'ko.re 'mu.tʃo"),
    ("Dame la llave roja", "'da.me la 'ʝa.be 'ro.xa"),
    ("Llueve en la calle", "'ʝue.be en la 'ka.ʝe"),
    ("Juan come arroz", "'xuan 'ko.me a.'roθ"),
    ("Pon el libro aquí", "'pon el 'li.bɾo a.'ki"),
    ("Hace mucho calor", "'a.θe 'mu.tʃo ka.'loɾ"),
    ("Cierra la ventana", "'θie.ra la ben.'ta.na"),
]

_ORACIONES_LARGAS = [
    ("El niño pequeño juega en el jardín de su casa", "el 'ni.ɲo pe.'ke.ɲo 'xue.ga en el xaɾ.'din de su 'ka.sa"),
    ("La profesora explica la lección a los estudiantes", "la pɾo.fe.'so.ɾa eks.'pli.ka la lek.'θion a los es.tu.'dian.tes"),
    ("Mi hermana compró un vestido rojo muy bonito", "mi eɾ.'ma.na kom.'pɾo un bes.'ti.do 'ro.xo mui bo.'ni.to"),
    ("Los pájaros cantan en las ramas del árbol grande", "los 'pa.xa.ɾos 'kan.tan en las 'ra.mas del 'aɾ.bol 'gɾan.de"),
    ("El médico recetó unas pastillas para el dolor de cabeza", "el 'me.di.ko re.θe.'to 'u.nas pas.'ti.ʝas 'pa.ɾa el do.'loɾ de ka.'be.θa"),
    ("La chica rubia llevaba una chaqueta verde y zapatos negros", "la 'tʃi.ka 'ru.bia ʝe.'ba.ba 'u.na tʃa.'ke.ta 'beɾ.de i θa.'pa.tos 'ne.gɾos"),
]


def generar_ejercicio_transcripcion(nivel: int = 1, num_items: int = 5,
                                     tipo: str = 'fonologica',
                                     habla: str = 'tipica',
                                     seed: int = None) -> dict:
    """
    Genera un ejercicio de transcripción.

    Args:
        nivel: 1-6 (dificultad ortográfica)
        num_items: número de palabras
        tipo: 'fonologica' o 'fonetica' (fonológica + fonética)
        habla: 'tipica' o 'errores' (habla con errores fonológicos)
        seed: semilla para reproducibilidad

    Returns:
        dict con instrucciones, items, nivel, tipo, habla, etc.
    """
    rng = random.Random(seed)

    # Levels 7-8 use sentences instead of individual words
    if nivel == 7:
        disponibles = [{'ortografia': o, 'transcripcion': t, 'num_silabas': t.count('.') + 1}
                       for o, t in _ORACIONES_CORTAS]
    elif nivel == 8:
        disponibles = [{'ortografia': o, 'transcripcion': t, 'num_silabas': t.count('.') + 1}
                       for o, t in _ORACIONES_LARGAS]
    elif nivel == 0:
        disponibles = list(BANCO_PALABRAS)
    else:
        disponibles = _PALABRAS_POR_NIVEL.get(nivel, [])

    if not disponibles:
        disponibles = list(BANCO_PALABRAS)

    if num_items > len(disponibles):
        seleccionadas = disponibles[:]
        rng.shuffle(seleccionadas)
    else:
        seleccionadas = rng.sample(disponibles, num_items)

    # Number of errors scales with level
    num_errores = _ERRORES_POR_NIVEL.get(nivel, 1)

    items = []
    for p in seleccionadas:
        item = {
            'ortografia': p['ortografia'],
            'transcripcion': p['transcripcion'],
            'num_silabas': p.get('num_silabas', 1),
        }

        # Generate phonetic transcription if needed
        if tipo == 'fonetica':
            if nivel in (7, 8):
                # For sentences, use the phonological transcription with inter-word context
                item['fonetica'] = _fonologica_a_fonetica_con_contexto(p['transcripcion'])
            else:
                from transcriptor import transcripcion_fonetica_palabra
                fonetica = transcripcion_fonetica_palabra(p['ortografia'])
                if isinstance(fonetica, tuple):
                    fonetica = p['transcripcion']
                item['fonetica'] = fonetica

        # Generate error version if needed
        if habla == 'errores':
            if nivel in (7, 8):
                # For sentences: apply errors only to content words (≥2 syllables)
                palabras_trans = p['transcripcion'].split(' ')
                producidas = []
                errores_todos = []
                errores_aplicados = 0
                for pt in palabras_trans:
                    # Skip short words (function words: el, la, de, en, a, etc.)
                    if pt.count('.') == 0 and len(pt.replace("'", "")) <= 3:
                        producidas.append(pt)
                        continue
                    if errores_aplicados >= num_errores:
                        producidas.append(pt)
                        continue
                    prod, errs = generar_errores(
                        pt, tipos=['sistemico'],
                        num_errores=1,
                        seed=rng.randint(0, 100000)
                    )
                    producidas.append(prod)
                    errores_todos.extend(errs)
                    if errs:
                        errores_aplicados += len(errs)
                producido = ' '.join(producidas)
            else:
                producido, errores_todos = generar_errores(
                    p['transcripcion'],
                    tipos=['sistemico'],
                    num_errores=num_errores,
                    seed=rng.randint(0, 100000)
                )
            # Only include if at least one error was actually applied
            if errores_todos and producido != p['transcripcion']:
                item['producido'] = producido
                item['errores'] = errores_todos
                item['ortografia_error'] = fonemas_a_ortografia(producido)
            else:
                # No error applied — retry with different seed
                for _ in range(5):
                    producido, errores_todos = generar_errores(
                        p['transcripcion'], tipos=['sistemico'],
                        num_errores=num_errores, seed=rng.randint(0, 100000))
                    if errores_todos and producido != p['transcripcion']:
                        break
                item['producido'] = producido if errores_todos else p['transcripcion']
                item['errores'] = errores_todos
                item['ortografia_error'] = fonemas_a_ortografia(item['producido'])
            # Derive phonetic from the produced phonological form
            if tipo == 'fonetica':
                item['fonetica'] = _fonologica_a_fonetica_con_contexto(producido)

        items.append(item)

    instrucciones = _generar_instrucciones(nivel, tipo, habla)
    pista = _NIVEL_PISTAS.get(nivel)

    # Mode key for progress tracking
    modo = f"{tipo}_{habla}"

    return {
        'instrucciones': instrucciones,
        'items': items,
        'nivel': nivel,
        'nivel_nombre': _NIVEL_NOMBRES.get(nivel, "Mixto"),
        'tipo': tipo,
        'habla': habla,
        'modo': modo,
        'pista': pista,
        'num_items': len(items),
    }


def corregir_ejercicio_transcripcion(ejercicio: dict, respuestas_texto: str) -> tuple[str, list[str]]:
    """
    Corrige un ejercicio de transcripción (todos los modos).

    Returns:
        tuple (texto_correccion, lista_items_incorrectos)
    """
    tipo = ejercicio.get('tipo', 'fonologica')
    habla = ejercicio.get('habla', 'tipica')
    respuestas = _parsear_respuestas_transcripcion(respuestas_texto, len(ejercicio['items']))

    lineas = []
    lineas.append("## Corrección\n")

    correctas_fonol = 0
    correctas_fonet = 0
    total_fonol = 0
    total_fonet = 0
    items_incorrectos = []

    for i, item in enumerate(ejercicio['items']):
        num = i + 1
        resp_alumno = respuestas.get(i, '')

        # Header: show orthographic form
        if habla == 'errores' and 'ortografia_error' in item:
            ort_error = item['ortografia_error']
            lineas.append(f"**{num}. {item['ortografia']}** → producido: "
                          f"<span style=\"color:#dc2626;font-weight:600;\">\"{ort_error}\"</span>")
            solucion_fonol = item.get('producido', item['transcripcion'])
        else:
            lineas.append(f"**{num}. {item['ortografia']}**")
            solucion_fonol = item['transcripcion']

        resp_fonol, resp_fonet = _separar_fonologica_fonetica(resp_alumno)

        # Check phonological
        total_fonol += 1
        if not resp_fonol:
            lineas.append(f"- ⚠️ Sin respuesta")
            items_incorrectos.append(f"Ítem {num}: sin respuesta")
        elif _transcripciones_equivalentes(resp_fonol, solucion_fonol):
            lineas.append(f"- ✅ Fonológica: /{resp_fonol}/ — **correcto**")
            correctas_fonol += 1
        else:
            diff_html = _marcar_diferencias(resp_fonol, solucion_fonol)
            lineas.append(f"- ❌ Tu respuesta: /{diff_html}/")
            lineas.append(f"- Correcto: /{solucion_fonol}/")
            items_incorrectos.append(f"Ítem {num} ({item['ortografia']}): fonológica incorrecta")

        # Check phonetic if required
        if tipo == 'fonetica':
            solucion_fonet = item.get('fonetica', '')
            if solucion_fonet:
                total_fonet += 1
                if not resp_fonet:
                    lineas.append(f"- ⚠️ Sin respuesta fonética")
                    if f"Ítem {num}" not in ' '.join(items_incorrectos):
                        items_incorrectos.append(f"Ítem {num} ({item['ortografia']}): sin fonética")
                elif _transcripciones_equivalentes(resp_fonet, solucion_fonet):
                    lineas.append(f"- ✅ Fonética: [{resp_fonet}] — **correcto**")
                    correctas_fonet += 1
                else:
                    diff_html = _marcar_diferencias(resp_fonet, solucion_fonet)
                    lineas.append(f"- ❌ Tu fonética: [{diff_html}]")
                    lineas.append(f"- Correcto: [{solucion_fonet}]")
                    if f"Ítem {num}" not in ' '.join(items_incorrectos):
                        items_incorrectos.append(f"Ítem {num} ({item['ortografia']}): fonética incorrecta")

        lineas.append("")

    # Summary
    lineas.append("---\n")

    # Unified error report with tables — for both typical and error speech
    if habla == 'errores':
        lineas.append("### Informe de errores identificados\n")
    else:
        lineas.append("### Informe de errores\n")

    errores_fonol_lista = []
    errores_fonet_lista = []

    for i, item in enumerate(ejercicio['items']):
        resp_alumno = respuestas.get(i, '')
        resp_fonol, resp_fonet = _separar_fonologica_fonetica(resp_alumno)

        if habla == 'errores' and 'producido' in item:
            solucion_fonol = item['producido']
        else:
            solucion_fonol = item['transcripcion']

        fonol_norm = _normalizar_transcripcion(solucion_fonol)
        fonol_palabras = fonol_norm.split(' ') if ' ' in fonol_norm else None

        if resp_fonol and not _transcripciones_equivalentes(resp_fonol, solucion_fonol):
            diffs = _extraer_pares_error(
                _normalizar_transcripcion(resp_fonol), fonol_norm, fonol_palabras)
            errores_fonol_lista.extend(diffs)

        if tipo == 'fonetica':
            solucion_fonet = item.get('fonetica', '')
            if solucion_fonet:
                fonet_norm = _normalizar_transcripcion(solucion_fonet)
                fonet_palabras = fonet_norm.split(' ') if ' ' in fonet_norm else None
                if resp_fonet and not _transcripciones_equivalentes(resp_fonet, solucion_fonet):
                    diffs = _extraer_pares_error(
                        _normalizar_transcripcion(resp_fonet), fonet_norm, fonet_palabras)
                    errores_fonet_lista.extend(diffs)

    if not errores_fonol_lista and not errores_fonet_lista and not items_incorrectos:
        lineas.append("Sin errores.")
    else:
        if errores_fonol_lista:
            lineas.append("**Errores en transcripción fonológica:**\n")
            lineas.append(_tabla_errores_agrupados(errores_fonol_lista, '/'))
        if errores_fonet_lista:
            lineas.append("**Errores en transcripción fonética:**\n")
            lineas.append(_tabla_errores_agrupados(errores_fonet_lista, '['))

    nombres_incorrectos = []
    for item_desc in items_incorrectos:
        if '(' in item_desc:
            nombre = item_desc.split('(')[1].split(')')[0]
            nombres_incorrectos.append(nombre)
    return '\n'.join(lineas), nombres_incorrectos


# ═══════════════════════════════════════════════════════════════════════
# UTILIDADES INTERNAS
# ═══════════════════════════════════════════════════════════════════════

def _generar_instrucciones(nivel: int, tipo: str = 'fonologica',
                           habla: str = 'tipica') -> str:
    """Genera instrucciones para el ejercicio según modo."""
    nombre = _NIVEL_NOMBRES.get(nivel, "Mixto")
    desc = _NIVEL_DESCRIPCIONES.get(nivel, "")

    # Title
    if tipo == 'fonetica':
        titulo_tipo = "fonológica y fonética"
    else:
        titulo_tipo = "fonológica"

    if habla == 'errores':
        titulo_habla = " (habla con errores)"
    else:
        titulo_habla = ""

    intro = f"## Ejercicio de transcripción {titulo_tipo}{titulo_habla} — Nivel {nivel}: {nombre}\n\n"

    # Task description (no level description — the student doesn't need it)
    if habla == 'tipica' and tipo == 'fonologica':
        intro += "**Tu tarea**: Escribe la transcripción fonológica de cada palabra.\n"
        intro += "Usa barras / /, puntos para separar sílabas y apóstrofo para el acento.\n"
        intro += "Ejemplo: \"mesa\" → /'me.sa/\n"
    elif habla == 'tipica' and tipo == 'fonetica':
        intro += "**Tu tarea**: Escribe la transcripción fonológica y la fonética de cada palabra.\n"
        intro += "Fonológica entre barras / /, fonética entre corchetes [ ].\n"
        intro += "Ejemplo: \"mesa\" → /'me.sa/ ['me.sa]\n"
    elif habla == 'errores' and tipo == 'fonologica':
        intro += "**Tu tarea**: Para cada palabra se muestra lo que dice el paciente. "
        intro += "Escribe la transcripción fonológica de lo **producido**.\n"
        intro += "Ejemplo: si el paciente dice \"tasa\" por \"casa\" → /'ta.sa/\n"
    elif habla == 'errores' and tipo == 'fonetica':
        intro += "**Tu tarea**: Para cada palabra se muestra lo que dice el paciente. "
        intro += "Escribe la transcripción fonológica y fonética de lo **producido**.\n"
        intro += "Fonológica entre barras / /, fonética entre corchetes [ ].\n"

    pista = _NIVEL_PISTAS.get(nivel)
    if pista:
        intro += f"\n**Pista**: {pista}\n"

    return intro


def _fonologica_a_fonetica_con_contexto(transcripcion_frase: str) -> str:
    """
    Convierte una transcripción fonológica de frase a fonética,
    procesando palabra por palabra con contexto inter-palabra.
    """
    from transcriptor import transcripcion_fonetica_desde_fonologica
    from .silaba import parsear_silabas

    palabras = transcripcion_frase.strip().split(' ')
    if not palabras:
        return ''

    # Pre-extract first/last phonemes for inter-word context
    fonemas_palabras = []
    for p in palabras:
        parsed = parsear_silabas(p)
        fons = parsed.fonemas
        fonemas_palabras.append(fons)

    resultados = []
    for idx, p in enumerate(palabras):
        is_start = (idx == 0)
        prev_last = fonemas_palabras[idx - 1][-1] if idx > 0 and fonemas_palabras[idx - 1] else None
        next_first = fonemas_palabras[idx + 1][0] if idx + 1 < len(palabras) and fonemas_palabras[idx + 1] else None

        fonetica = transcripcion_fonetica_desde_fonologica(
            p,
            is_utterance_start=is_start,
            prev_word_last_fonema=prev_last,
            next_word_first_fonema=next_first
        )
        resultados.append(fonetica)

    return ' '.join(resultados)


def fonemas_a_ortografia(transcripcion: str) -> str:
    """
    Convierte una transcripción fonológica a pseudo-ortografía española.
    Usa la grafía más intuitiva para cada fonema.
    Soporta transcripciones de frases (palabras separadas por espacios).

    Ej: /'ka.θa/ → "caza", /'ta.θa/ → "taza", /tom.'paɾ/ → "tompar"
    """
    # Handle multi-word transcriptions
    palabras = transcripcion.strip().split(' ')
    if len(palabras) > 1:
        return ' '.join(fonemas_a_ortografia(p) for p in palabras)

    palabra = parsear_silabas(transcripcion)
    resultado = []

    for sil in palabra.silabas:
        for i, f in enumerate(sil.fonemas):
            # Get the next phoneme for context
            next_f = sil.fonemas[i + 1] if i + 1 < len(sil.fonemas) else None

            if f == 'k':
                if next_f in ('e', 'i'):
                    resultado.append('qu')
                else:
                    resultado.append('c')
            elif f == 'θ':
                if next_f in ('e', 'i'):
                    resultado.append('c')
                else:
                    resultado.append('z')
            elif f == 'b':
                resultado.append('b')
            elif f == 'g':
                if next_f in ('e', 'i'):
                    resultado.append('gu')
                else:
                    resultado.append('g')
            elif f == 'x':
                resultado.append('j')
            elif f == 'ʝ':
                resultado.append('y')
            elif f == 'tʃ':
                resultado.append('ch')
            elif f == 'ɲ':
                resultado.append('ñ')
            elif f == 'r':
                # Vibrante múltiple: "rr" entre vocales, "r" al inicio
                if resultado and resultado[-1][-1] in 'aeiou':
                    resultado.append('rr')
                else:
                    resultado.append('r')
            elif f == 'ɾ':
                resultado.append('r')
            elif f in ('a', 'e', 'i', 'o', 'u'):
                resultado.append(f)
            elif f in ('p', 't', 'd', 'f', 's', 'l', 'm', 'n'):
                resultado.append(f)
            else:
                resultado.append(f)  # fallback

    return ''.join(resultado)


def _separar_fonologica_fonetica(texto: str) -> tuple[str, str]:
    """
    Separa una respuesta que puede contener transcripción fonológica y fonética.
    Busca /.../ para fonológica y [...] para fonética.
    Si no hay marcadores, asume que todo es fonológico.
    """
    fonol = ''
    fonet = ''

    # Extract /.../ (phonological)
    m_fonol = re.search(r'/([^/]+)/', texto)
    if m_fonol:
        fonol = m_fonol.group(1).strip()

    # Extract [...] (phonetic)
    m_fonet = re.search(r'\[([^\]]+)\]', texto)
    if m_fonet:
        fonet = m_fonet.group(1).strip()

    # If no markers found, treat the whole thing as phonological
    if not fonol and not fonet:
        fonol = _normalizar_transcripcion(texto)

    return fonol, fonet


def _normalizar_transcripcion(t: str) -> str:
    """Normaliza una transcripción para comparación."""
    t = t.strip()
    # Remove surrounding slashes/brackets
    t = t.strip('/').strip('[').strip(']').strip()
    # Normalize apostrophe/accent variants
    t = t.replace('ˈ', "'").replace('\u02c8', "'")
    # Normalize comma→dot (common typo)
    t = t.replace(',', '.')
    # Collapse multiple spaces
    import re as _re
    t = _re.sub(r'\s+', ' ', t).strip()
    return t


def _transcripciones_equivalentes(alumno: str, correcta: str) -> bool:
    """Compara dos transcripciones, tolerando variaciones menores."""
    a = _normalizar_transcripcion(alumno)
    c = _normalizar_transcripcion(correcta)
    return a == c


def _clasificar_errores_transcripcion(alumno: str, correcta: str) -> tuple[int, int, int, int]:
    """
    Clasifica las diferencias entre dos transcripciones por tipo de error.
    Usa tokenización IPA para manejar dígrafos como tʃ, β̞, etc.

    Returns:
        (errores_acento, errores_silaba, errores_fonema, errores_palabra)
    """
    errores_acento = 0
    errores_silaba = 0
    errores_fonema = 0
    errores_palabra = 0

    palabras_a = alumno.split(' ')
    palabras_c = correcta.split(' ')

    if len(palabras_a) != len(palabras_c):
        errores_palabra += abs(len(palabras_a) - len(palabras_c))

    for wi in range(min(len(palabras_a), len(palabras_c))):
        pa = palabras_a[wi]
        pc = palabras_c[wi]

        if pa == pc:
            continue

        # Check accent only
        pa_sin = pa.replace("'", "")
        pc_sin = pc.replace("'", "")
        if pa_sin == pc_sin:
            errores_acento += 1
            continue

        # Split into syllables
        sils_a = pa.split('.')
        sils_c = pc.split('.')

        if len(sils_a) != len(sils_c):
            errores_silaba += 1
            continue

        # Compare syllable by syllable using IPA tokenization
        for si in range(len(sils_a)):
            sa = sils_a[si]
            sc = sils_c[si]
            if sa == sc:
                continue

            sa_sin = sa.replace("'", "")
            sc_sin = sc.replace("'", "")
            if sa_sin == sc_sin:
                errores_acento += 1
                continue

            # Tokenize into IPA units (handles tʃ, β̞, etc.)
            toks_a = _tokenizar_afi(sa_sin)
            toks_c = _tokenizar_afi(sc_sin)

            if len(toks_a) != len(toks_c):
                # Different number of phonemes → syllable structure error
                errores_silaba += 1
            else:
                # Same number of phonemes → count systemic errors
                for ti in range(len(toks_a)):
                    if toks_a[ti] != toks_c[ti]:
                        errores_fonema += 1

    return errores_acento, errores_silaba, errores_fonema, errores_palabra


_RASGO_NOMBRES = {
    'sonoridad': 'Sonoridad',
    'lugar': 'Lugar',
    'modo': 'Modo',
    'nasalidad': 'Nasalidad',
}


def _tabla_errores_agrupados(errores: list, delim: str) -> str:
    """
    Agrupa errores idénticos, cuenta ocurrencias, muestra rasgo y contexto.

    Args:
        errores: lista de (esperado, escrito, contexto, rasgo)
        delim: '/' para fonológica, '[' para fonética
    """
    cierre = '/' if delim == '/' else ']'
    from collections import OrderedDict
    agrupados = OrderedDict()
    for item in errores:
        esperado, escrito = item[0], item[1]
        contexto = item[2] if len(item) > 2 else ''
        rasgo = item[3] if len(item) > 3 else '—'
        key = (esperado, escrito)
        if key not in agrupados:
            agrupados[key] = {'contextos': [], 'rasgo': rasgo}
        if contexto not in agrupados[key]['contextos']:
            agrupados[key]['contextos'].append(contexto)

    lineas = []
    lineas.append("| Correcto | Tu respuesta | Rasgo | Veces | Contexto |")
    lineas.append("|:---:|:---:|:---:|:---:|---|")
    rojo = lambda t: f'<span style="color:#dc2626;font-weight:700">{t}</span>'

    for (esperado, escrito), info in agrupados.items():
        n = sum(1 for e in errores if e[0] == esperado and e[1] == escrito)
        rasgo = _RASGO_NOMBRES.get(info['rasgo'], info['rasgo'])
        contextos_marcados = []
        for ctx in info['contextos']:
            if esperado in ctx:
                ctx_marcado = ctx.replace(esperado, rojo(esperado), 1)
            else:
                ctx_marcado = ctx
            contextos_marcados.append(f"{delim}{ctx_marcado}{cierre}")
        ctx_str = ', '.join(contextos_marcados)
        lineas.append(f"| {delim}{esperado}{cierre} | {delim}{escrito}{cierre} | {rasgo} | {n} | {ctx_str} |")
    lineas.append("")
    return '\n'.join(lineas)


def _tokenizar_afi(texto: str) -> list[str]:
    """Tokeniza texto IPA agrupando diacríticos con su base."""
    import unicodedata
    tokens = []
    current = ''
    for ch in texto:
        cat = unicodedata.category(ch)
        if cat.startswith('M'):
            # Combining mark: attach to previous character
            current += ch
        else:
            if current:
                tokens.append(current)
            current = ch
    if current:
        tokens.append(current)

    # Merge known digraphs (tʃ, etc.)
    merged = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i] + tokens[i+1] in ('tʃ', 'nʲ'):
            merged.append(tokens[i] + tokens[i+1])
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    return merged


def _clasificar_rasgo_error(esperado: str, escrito: str) -> str:
    """Clasifica un par de fonemas/alófonos por el rasgo afectado."""
    from .inventario import clasificar_error_sistemico

    # Try direct classification from the inventory
    try:
        errores = clasificar_error_sistemico(esperado, escrito)
        if errores:
            rasgos = [e['rasgo'] for e in errores]
            for r in ('sonoridad', 'lugar', 'modo', 'nasalidad'):
                if r in rasgos:
                    return r
            return rasgos[0]
    except KeyError:
        pass

    # Map allophones to their base phoneme for classification
    _alofono_a_fonema = {
        'β̞': 'b', 'ð̞': 'd', 'ɣ̞': 'g',  # aproximantes
        'ɹ': 'ɾ',  # vibrante aproximante
        'ɱ': 'm', 'ŋ': 'n', 'n̪': 'n', 'n̟': 'n', 'nʲ': 'n',  # nasales
        'l̪': 'l', 'l̟': 'l',  # laterales
        'ʤ': 'ʝ',  # africada sonora
        'j': 'i', 'w': 'u', 'i̯': 'i', 'u̯': 'u',  # semivocales
    }

    base_e = _alofono_a_fonema.get(esperado, esperado)
    base_s = _alofono_a_fonema.get(escrito, escrito)

    if base_e != esperado or base_s != escrito:
        try:
            errores = clasificar_error_sistemico(base_e, base_s)
            if errores:
                rasgos = [e['rasgo'] for e in errores]
                for r in ('sonoridad', 'lugar', 'modo', 'nasalidad'):
                    if r in rasgos:
                        return r
                return rasgos[0]
        except KeyError:
            pass

    # If one is an allophone and the other its base → modo
    if base_e == base_s:
        return 'modo'

    return '—'


def _extraer_pares_error(alumno: str, correcta: str,
                         palabras_contexto: list[str] = None) -> list[tuple[str, str, str, str]]:
    """
    Extrae cuádruplos (esperado, escrito, contexto, rasgo) de errores.

    Args:
        alumno: transcripción del alumno (normalizada)
        correcta: transcripción correcta (normalizada)
        palabras_contexto: lista de palabras (fonológicas o ortográficas) para contexto.
    """
    pares = []
    palabras_a = alumno.split(' ')
    palabras_c = correcta.split(' ')

    for wi in range(min(len(palabras_a), len(palabras_c))):
        pa = palabras_a[wi]
        pc = palabras_c[wi]
        if pa == pc:
            continue

        ctx = palabras_contexto[wi] if palabras_contexto and wi < len(palabras_contexto) else pc

        sils_a = pa.replace("'", "").split('.')
        sils_c = pc.replace("'", "").split('.')

        for si in range(min(len(sils_a), len(sils_c))):
            sa = sils_a[si]
            sc = sils_c[si]
            if sa == sc:
                continue
            toks_a = _tokenizar_afi(sa)
            toks_c = _tokenizar_afi(sc)
            for ti in range(min(len(toks_a), len(toks_c))):
                if toks_a[ti] != toks_c[ti]:
                    rasgo = _clasificar_rasgo_error(toks_c[ti], toks_a[ti])
                    pares.append((toks_c[ti], toks_a[ti], ctx, rasgo))
            if len(toks_a) > len(toks_c):
                for ti in range(len(toks_c), len(toks_a)):
                    pares.append(('—', toks_a[ti], ctx, '—'))
            elif len(toks_c) > len(toks_a):
                for ti in range(len(toks_a), len(toks_c)):
                    pares.append((toks_c[ti], '—', ctx, '—'))

    return pares


_ERR_STYLE = 'color:#dc2626;font-weight:700'


def _rojo(texto: str) -> str:
    """Envuelve texto en span rojo."""
    return f'<span style="{_ERR_STYLE}">{texto}</span>'


def _marcar_diferencias(alumno: str, correcta: str) -> str:
    """
    Compara la respuesta del alumno con la correcta de forma jerárquica:
    1. Palabras (separadas por espacios) — si una palabra entera difiere, se marca entera
    2. Sílabas (separadas por puntos) — si una sílaba difiere, se marca entera
    3. Fonemas — si solo difiere un fonema dentro de una sílaba, se marca solo ese

    Devuelve la respuesta del alumno con las partes incorrectas en rojo.
    """
    a = _normalizar_transcripcion(alumno)
    c = _normalizar_transcripcion(correcta)

    # Split into words
    palabras_a = a.split(' ')
    palabras_c = c.split(' ')

    resultado_palabras = []

    # Align words (handle different number of words)
    max_words = max(len(palabras_a), len(palabras_c))
    for wi in range(min(len(palabras_a), max_words)):
        pa = palabras_a[wi] if wi < len(palabras_a) else ''

        if wi >= len(palabras_c):
            # Extra word in student's answer
            resultado_palabras.append(_rojo(pa))
            continue

        pc = palabras_c[wi]

        if pa == pc:
            # Word is correct
            resultado_palabras.append(pa)
            continue

        # Word differs — compare syllables
        sils_a = pa.split('.')
        sils_c = pc.split('.')

        if len(sils_a) != len(sils_c):
            # Different number of syllables — mark whole word
            resultado_palabras.append(_rojo(pa))
            continue

        # Same number of syllables — compare each
        resultado_sils = []
        for si in range(len(sils_a)):
            sa = sils_a[si]
            sc = sils_c[si]

            if sa == sc:
                resultado_sils.append(sa)
            elif len(sa) == len(sc):
                # Same length — compare phoneme by phoneme
                chars = []
                for ci in range(len(sa)):
                    if sa[ci] == sc[ci]:
                        chars.append(sa[ci])
                    else:
                        chars.append(_rojo(sa[ci]))
                resultado_sils.append(''.join(chars))
            else:
                # Different length — mark whole syllable
                resultado_sils.append(_rojo(sa))

        resultado_palabras.append('.'.join(resultado_sils))

    return ' '.join(resultado_palabras)


def _parsear_respuestas_transcripcion(texto: str, num_items: int) -> dict[int, str]:
    """
    Parsea respuestas de transcripción del alumno.

    Soporta formatos variados:
      "1. /'me.sa/ 2. /'pa.to/"
      "1: /me.sa/\\n2: /pa.to/"
      "1. /me.sa/ ['me.sa]\\n2. /pa.to/ ['pa.to]"
      "1. 'me.sa, 2. 'pa.to"
    """
    respuestas = {}
    texto = texto.strip()

    # Find all (number, content) pairs
    # Content extends until the next "N." / "N:" / "N)" pattern or end of string
    pattern = r'(\d+)\s*[.:)\-]\s*((?:(?!\d+\s*[.:)\-]).)*)'
    matches = re.findall(pattern, texto, re.DOTALL)

    for num_str, content in matches:
        try:
            num = int(num_str)
        except ValueError:
            continue
        if 1 <= num <= num_items:
            cleaned = content.strip().rstrip(',').rstrip(';').strip()
            respuestas[num - 1] = cleaned

    return respuestas
