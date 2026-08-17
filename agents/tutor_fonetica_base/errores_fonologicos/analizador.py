"""
Analizador de errores fonológicos.

Compara una transcripción objetivo con una transcripción producida
y genera un informe estructurado de errores en tres niveles:

  1. PALABRA: alineación sílaba a sílaba → omisión de sílabas,
     asimilación, metátesis
  2. SÍLABA: para cada par de sílabas alineadas → omisión/simplificación
     de ataque, simplificación de núcleo, omisión de coda
  3. FONEMA (sistémico): para cada fonema que difiere y no está ya
     explicado por un error de sílaba → sonorización, ensordecimiento,
     adelantamiento, posteriorización, nasalización, desnasalización
"""

from .inventario import es_consonante, es_vocal, clasificar_error_sistemico
from .silaba import parsear_silabas, Palabra, Silaba


def _extraer_palabras(transcripcion: str) -> list[str]:
    """Extrae palabras individuales de una transcripción fonológica.
    Limpia barras / /, espacios y separa por espacios entre sílabas no separadas por punto.
    Ejemplo: '/ me ˈka.go en ˈdios /' → ['me', 'ˈka.go', 'en', 'ˈdios']
    """
    import re
    t = transcripcion.strip().strip('/')
    # Split by spaces, filter empty
    tokens = [w.strip() for w in t.split() if w.strip()]
    # Filter out stray markers
    palabras = [w for w in tokens if any(c.isalpha() or c in 'ˈˌ.θʝʧɲɾʎ' for c in w)]
    return palabras


def analizar(objetivo: str, producido: str) -> dict:
    """
    Analiza los errores entre una transcripción objetivo y una producida.
    Soporta oraciones completas: divide por palabras y analiza cada par.

    Args:
        objetivo: Transcripción fonológica correcta (ej: "/ me ˈka.go en ˈdios /")
        producido: Transcripción fonológica real (ej: "/ me ˈka.o en ˈios /")

    Returns:
        dict con errores_palabra, errores_silaba, errores_sistemicos,
        medidas_cuantitativas y resumen.
    """
    # Split into words and analyze word by word
    palabras_obj = _extraer_palabras(objetivo)
    palabras_prod = _extraer_palabras(producido)

    # Align words using simple positional alignment
    # (handles omission of whole words)
    pares_palabras = _alinear_palabras(palabras_obj, palabras_prod)

    informe_global = {
        'objetivo': objetivo,
        'producido': producido,
        'medidas_cuantitativas': {},
        'errores_palabra': [],
        'errores_silaba': [],
        'errores_sistemicos': [],
    }

    total_fonemas_obj = 0
    total_fonemas_prod = 0
    total_correctos = 0
    palabras_correctas = 0
    total_palabras = 0

    for w_obj, w_prod in pares_palabras:
        if w_obj is None:
            continue  # inserted word in production, skip
        total_palabras += 1

        if w_prod is None:
            # Whole word omitted
            p_obj = parsear_silabas(w_obj)
            informe_global['errores_palabra'].append({
                'tipo': 'omision_palabra',
                'descripcion': f'Omisión de palabra: /{w_obj}/',
            })
            total_fonemas_obj += len(p_obj.fonemas)
            continue

        # Analyze this word pair
        resultado = _analizar_palabra(w_obj, w_prod)

        # Aggregate results
        mc = resultado['medidas_cuantitativas']
        total_fonemas_obj += mc['total_fonemas_objetivo']
        total_fonemas_prod += mc['total_fonemas_producidos']
        total_correctos += mc['fonemas_correctos']

        if mc['fonemas_correctos'] == mc['total_fonemas_objetivo']:
            palabras_correctas += 1

        # Add word context to errors
        for e in resultado['errores_palabra']:
            e['palabra'] = w_obj
            informe_global['errores_palabra'].append(e)
        for e in resultado['errores_silaba']:
            e['palabra'] = w_obj
            informe_global['errores_silaba'].append(e)
        for e in resultado['errores_sistemicos']:
            e['palabra'] = w_obj
            informe_global['errores_sistemicos'].append(e)

    # Global quantitative measures
    informe_global['medidas_cuantitativas'] = {
        'total_fonemas_objetivo': total_fonemas_obj,
        'total_fonemas_producidos': total_fonemas_prod,
        'fonemas_correctos': total_correctos,
        'PFC': round(total_correctos / total_fonemas_obj * 100, 1) if total_fonemas_obj > 0 else 0,
        'PPC': round(palabras_correctas / total_palabras * 100, 1) if total_palabras > 0 else 0,
        'palabras_correctas': palabras_correctas,
        'total_palabras': total_palabras,
    }

    informe_global['resumen'] = _generar_resumen(informe_global)
    return informe_global


def _alinear_palabras(obj: list[str], prod: list[str]) -> list[tuple]:
    """Align words between objective and production using Needleman-Wunsch."""
    n, m = len(obj), len(prod)
    if n == m:
        return list(zip(obj, prod))

    GAP = -2
    def score(w1, w2):
        # Simple: first phoneme match = good
        if w1 and w2 and w1[0] == w2[0]:
            return 2
        return -1

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = GAP * i
    for j in range(m + 1): dp[0][j] = GAP * j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = max(
                dp[i-1][j-1] + score(obj[i-1], prod[j-1]),
                dp[i-1][j] + GAP,
                dp[i][j-1] + GAP,
            )

    alineacion = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + score(obj[i-1], prod[j-1]):
            alineacion.append((obj[i-1], prod[j-1]))
            i -= 1; j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + GAP:
            alineacion.append((obj[i-1], None))
            i -= 1
        else:
            alineacion.append((None, prod[j-1]))
            j -= 1
    alineacion.reverse()
    return alineacion


def _analizar_palabra(objetivo: str, producido: str) -> dict:
    """Analyze errors for a single word pair."""
    p_obj = parsear_silabas(objetivo)
    p_prod = parsear_silabas(producido)

    informe = {
        'medidas_cuantitativas': {},
        'errores_palabra': [],
        'errores_silaba': [],
        'errores_sistemicos': [],
    }

    alineacion_silabas = _alinear_silabas(p_obj, p_prod)
    fonemas_explicados = set()  # (indice_silaba_obj, indice_fonema) ya explicados

    # Omisión de sílabas
    for i, (s_obj, s_prod) in enumerate(alineacion_silabas):
        if s_obj is not None and s_prod is None:
            tipo = 'omision_silaba_tonica' if s_obj.tonica else 'omision_silaba_atona'
            desc_tipo = 'tónica' if s_obj.tonica else 'átona'
            informe['errores_palabra'].append({
                'tipo': tipo,
                'silaba': i + 1,
                'descripcion': f'Omisión de sílaba {desc_tipo} (sílaba {i+1}: /{"".join(s_obj.fonemas)}/)',
            })
            # All phonemes in this syllable are explained
            for fi in range(len(s_obj.fonemas)):
                fonemas_explicados.add((i, fi))

    # Metátesis: comprobar si consonantes se han intercambiado entre sílabas
    _detectar_metatesis(alineacion_silabas, informe, fonemas_explicados)

    # Asimilación: comprobar si un fonema se ha asimilado al de la sílaba vecina
    _detectar_asimilaciones_silabicas(alineacion_silabas, informe, fonemas_explicados)

    # ══════════════════════════════════════════════════════════════════
    # PASO 2: Dentro de cada par de sílabas → errores de SÍLABA
    # ══════════════════════════════════════════════════════════════════

    for i, (s_obj, s_prod) in enumerate(alineacion_silabas):
        if s_obj is None or s_prod is None:
            continue  # sílaba omitida/insertada, ya reportada

        # Omisión de ataque
        if s_obj.tiene_ataque and not s_prod.tiene_ataque:
            informe['errores_silaba'].append({
                'tipo': 'omision_ataque', 'silaba': i + 1,
                'descripcion': f'Omisión de ataque en sílaba {i+1}: /{"".join(s_obj.ataque)}/ omitido',
            })
            for fi in range(len(s_obj.ataque)):
                fonemas_explicados.add((i, fi))

        # Simplificación de ataque (complejo → simple)
        elif s_obj.ataque_complejo and not s_prod.ataque_complejo and s_prod.tiene_ataque:
            informe['errores_silaba'].append({
                'tipo': 'simplificacion_ataque', 'silaba': i + 1,
                'descripcion': (f'Simplificación de ataque en sílaba {i+1}: '
                                f'/{"".join(s_obj.ataque)}/ > /{"".join(s_prod.ataque)}/'),
            })
            # The omitted consonant is explained
            for fi in range(len(s_obj.ataque)):
                if fi >= len(s_prod.ataque) or (fi < len(s_prod.ataque) and
                        fi < len(s_obj.ataque) and s_obj.ataque[fi] != s_prod.ataque[fi]):
                    fonemas_explicados.add((i, fi))

        # Simplificación de núcleo (diptongo → monoptongo)
        if s_obj.tiene_diptongo and not s_prod.tiene_diptongo:
            offset = len(s_obj.ataque)
            informe['errores_silaba'].append({
                'tipo': 'simplificacion_nucleo', 'silaba': i + 1,
                'descripcion': (f'Simplificación de núcleo en sílaba {i+1}: '
                                f'/{"".join(s_obj.nucleo)}/ > /{"".join(s_prod.nucleo)}/'),
            })
            for fi in range(len(s_obj.nucleo)):
                fonemas_explicados.add((i, offset + fi))

        # Omisión de coda
        if s_obj.tiene_coda and not s_prod.tiene_coda:
            offset = len(s_obj.ataque) + len(s_obj.nucleo)
            informe['errores_silaba'].append({
                'tipo': 'omision_coda', 'silaba': i + 1,
                'descripcion': f'Omisión de coda en sílaba {i+1}: /{"".join(s_obj.coda)}/ omitida',
            })
            for fi in range(len(s_obj.coda)):
                fonemas_explicados.add((i, offset + fi))

    # ══════════════════════════════════════════════════════════════════
    # PASO 3: Dentro de cada fonema → errores SISTÉMICOS
    # Solo para fonemas no explicados por errores de sílaba/palabra
    # ══════════════════════════════════════════════════════════════════

    for i, (s_obj, s_prod) in enumerate(alineacion_silabas):
        if s_obj is None or s_prod is None:
            continue

        # Alinear fonemas dentro de la sílaba
        pares = _alinear_fonemas_silaba(s_obj, s_prod)

        fi_obj = 0
        for f_obj, f_prod in pares:
            if f_obj and f_prod and f_obj != f_prod:
                if (i, fi_obj) not in fonemas_explicados:
                    try:
                        errores = clasificar_error_sistemico(f_obj, f_prod)
                        for err in errores:
                            err['silaba'] = i + 1
                            informe['errores_sistemicos'].append(err)
                    except KeyError:
                        pass
            if f_obj:
                fi_obj += 1

    # ══════════════════════════════════════════════════════════════════
    # Medidas cuantitativas
    # ══════════════════════════════════════════════════════════════════

    fonemas_obj = p_obj.fonemas
    fonemas_prod = p_prod.fonemas
    alineacion_flat = _alinear_fonemas(fonemas_obj, fonemas_prod)
    correctos = sum(1 for o, p in alineacion_flat if o == p)
    total = len(fonemas_obj)

    informe['medidas_cuantitativas'] = {
        'total_fonemas_objetivo': total,
        'total_fonemas_producidos': len(fonemas_prod),
        'fonemas_correctos': correctos,
        'PFC': round(correctos / total * 100, 1) if total > 0 else 0,
        'num_silabas_objetivo': p_obj.num_silabas,
        'num_silabas_producidas': p_prod.num_silabas,
    }

    return informe


# ═══════════════════════════════════════════════════════════════════════
# ALINEACIÓN DE SÍLABAS
# ═══════════════════════════════════════════════════════════════════════

def _alinear_silabas(p_obj: Palabra, p_prod: Palabra) -> list[tuple]:
    """
    Alinea las sílabas de objetivo y producido.

    Devuelve lista de pares (silaba_obj, silaba_prod).
    None indica sílaba omitida (en prod) o insertada (en obj).

    Usa Needleman-Wunsch con scoring basado en similitud de fonemas.
    """
    n = p_obj.num_silabas
    m = p_prod.num_silabas

    if n == 0:
        return [(None, s) for s in p_prod.silabas]
    if m == 0:
        return [(s, None) for s in p_obj.silabas]

    # Si tienen el mismo número de sílabas, alinear directamente
    if n == m:
        return list(zip(p_obj.silabas, p_prod.silabas))

    # Dynamic programming alignment
    GAP = -2

    def score(s1: Silaba, s2: Silaba) -> int:
        """Score similarity between two syllables."""
        f1 = s1.fonemas
        f2 = s2.fonemas
        # Count matching phonemes
        matches = sum(1 for a, b in zip(f1, f2) if a == b)
        total = max(len(f1), len(f2))
        if total == 0:
            return 0
        # +2 for mostly similar, -1 for very different
        ratio = matches / total
        return 2 if ratio >= 0.5 else -1

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = GAP * i
    for j in range(m + 1):
        dp[0][j] = GAP * j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = dp[i-1][j-1] + score(p_obj.silabas[i-1], p_prod.silabas[j-1])
            delete = dp[i-1][j] + GAP
            insert = dp[i][j-1] + GAP
            dp[i][j] = max(match, delete, insert)

    # Traceback
    alineacion = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + score(p_obj.silabas[i-1], p_prod.silabas[j-1]):
            alineacion.append((p_obj.silabas[i-1], p_prod.silabas[j-1]))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + GAP:
            alineacion.append((p_obj.silabas[i-1], None))
            i -= 1
        else:
            alineacion.append((None, p_prod.silabas[j-1]))
            j -= 1

    alineacion.reverse()
    return alineacion


# ═══════════════════════════════════════════════════════════════════════
# ALINEACIÓN DE FONEMAS (dentro de una sílaba)
# ═══════════════════════════════════════════════════════════════════════

def _alinear_fonemas_silaba(s_obj: Silaba, s_prod: Silaba) -> list[tuple]:
    """
    Alinea fonemas dentro de un par de sílabas.
    Alinea por posición estructural: ataque con ataque, núcleo con núcleo,
    coda con coda.
    """
    pares = []

    # Ataque
    for k in range(max(len(s_obj.ataque), len(s_prod.ataque))):
        fo = s_obj.ataque[k] if k < len(s_obj.ataque) else None
        fp = s_prod.ataque[k] if k < len(s_prod.ataque) else None
        pares.append((fo, fp))

    # Núcleo
    for k in range(max(len(s_obj.nucleo), len(s_prod.nucleo))):
        fo = s_obj.nucleo[k] if k < len(s_obj.nucleo) else None
        fp = s_prod.nucleo[k] if k < len(s_prod.nucleo) else None
        pares.append((fo, fp))

    # Coda
    for k in range(max(len(s_obj.coda), len(s_prod.coda))):
        fo = s_obj.coda[k] if k < len(s_obj.coda) else None
        fp = s_prod.coda[k] if k < len(s_prod.coda) else None
        pares.append((fo, fp))

    return pares


def _alinear_fonemas(obj: list[str], prod: list[str]) -> list[tuple]:
    """
    Alineación global de dos secuencias de fonemas (Needleman-Wunsch).
    Se usa solo para calcular PFC. No se usa para detectar errores.
    """
    n, m = len(obj), len(prod)
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = -i
    for j in range(m + 1):
        dp[0][j] = -j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = dp[i-1][j-1] + (1 if obj[i-1] == prod[j-1] else -1)
            delete = dp[i-1][j] - 1
            insert = dp[i][j-1] - 1
            dp[i][j] = max(match, delete, insert)

    alineacion = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + (1 if obj[i-1] == prod[j-1] else -1):
            alineacion.append((obj[i-1], prod[j-1]))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] - 1:
            alineacion.append((obj[i-1], None))
            i -= 1
        else:
            alineacion.append((None, prod[j-1]))
            j -= 1

    alineacion.reverse()
    return alineacion


# ═══════════════════════════════════════════════════════════════════════
# DETECCIÓN DE ERRORES DE PALABRA
# ═══════════════════════════════════════════════════════════════════════

def _detectar_metatesis(alineacion: list[tuple], informe: dict, fonemas_explicados: set):
    """
    Detecta metátesis: dos fonemas intercambian sus posiciones entre sílabas.
    Ej: /me.sa/ → /se.ma/ — /m/ y /s/ intercambian posiciones.
    Solo se reporta si las dos sílabas tienen el mismo número de fonemas
    y exactamente dos posiciones están intercambiadas.
    """
    for i in range(len(alineacion) - 1):
        s_obj1, s_prod1 = alineacion[i]
        s_obj2, s_prod2 = alineacion[i + 1]
        if s_obj1 is None or s_prod1 is None or s_obj2 is None or s_prod2 is None:
            continue

        fonemas_obj = s_obj1.fonemas + s_obj2.fonemas
        fonemas_prod = s_prod1.fonemas + s_prod2.fonemas

        if len(fonemas_obj) != len(fonemas_prod):
            continue

        diffs = [(j, fonemas_obj[j], fonemas_prod[j])
                 for j in range(len(fonemas_obj)) if fonemas_obj[j] != fonemas_prod[j]]
        if len(diffs) == 2:
            j1, o1, p1 = diffs[0]
            j2, o2, p2 = diffs[1]
            if o1 == p2 and o2 == p1:
                informe['errores_palabra'].append({
                    'tipo': 'metatesis',
                    'descripcion': f'Metátesis: /{o1}/ ↔ /{o2}/ (sílabas {i+1}-{i+2})',
                })
                n1 = len(s_obj1.fonemas)
                if j1 < n1:
                    fonemas_explicados.add((i, j1))
                else:
                    fonemas_explicados.add((i + 1, j1 - n1))
                if j2 < n1:
                    fonemas_explicados.add((i, j2))
                else:
                    fonemas_explicados.add((i + 1, j2 - n1))


def _detectar_asimilaciones_silabicas(alineacion: list[tuple], informe: dict, fonemas_explicados: set):
    """
    Detecta asimilación entre sílabas adyacentes.
    """
    for i in range(len(alineacion) - 1):
        s_obj1, s_prod1 = alineacion[i]
        s_obj2, s_prod2 = alineacion[i + 1]
        if s_obj1 is None or s_prod1 is None or s_obj2 is None or s_prod2 is None:
            continue

        if not s_obj1.fonemas or not s_obj2.fonemas:
            continue
        if not s_prod1.fonemas or not s_prod2.fonemas:
            continue

        ultimo_obj = s_obj1.fonemas[-1]
        ultimo_prod = s_prod1.fonemas[-1]
        primero_obj = s_obj2.fonemas[0]
        primero_prod = s_prod2.fonemas[0]

        # Regresiva: último fonema de sílaba 1 cambia hacia el primero de sílaba 2
        if ultimo_obj != ultimo_prod and ultimo_prod == primero_obj:
            informe['errores_palabra'].append({
                'tipo': 'asimilacion_regresiva',
                'descripcion': (f'Asimilación regresiva: /{ultimo_obj}/ > /{ultimo_prod}/ '
                                f'(por efecto de /{primero_obj}/ siguiente, sílabas {i+1}-{i+2})'),
            })
            fonemas_explicados.add((i, len(s_obj1.fonemas) - 1))

        # Progresiva: primer fonema de sílaba 2 cambia hacia el último de sílaba 1
        if primero_obj != primero_prod and primero_prod == ultimo_obj:
            informe['errores_palabra'].append({
                'tipo': 'asimilacion_progresiva',
                'descripcion': (f'Asimilación progresiva: /{primero_obj}/ > /{primero_prod}/ '
                                f'(por efecto de /{ultimo_obj}/ anterior, sílabas {i+1}-{i+2})'),
            })
            fonemas_explicados.add((i + 1, 0))


# ═══════════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════════

def _generar_resumen(informe: dict) -> str:
    """Genera un resumen legible del informe de errores."""
    lineas = []
    lineas.append("## Informe de errores fonológicos\n")

    mc = informe['medidas_cuantitativas']
    lineas.append(f"### Medidas cuantitativas")
    lineas.append(f"- Objetivo: /{informe['objetivo']}/")
    lineas.append(f"- Producido: /{informe['producido']}/")
    lineas.append(f"- PFC (Porcentaje de Fonemas Correctos): {mc['PFC']}%")
    lineas.append(f"- Fonemas correctos: {mc['fonemas_correctos']}/{mc['total_fonemas_objetivo']}")
    if 'num_silabas_objetivo' in mc:
        lineas.append(f"- Sílabas: {mc.get('num_silabas_producidas', '?')}/{mc['num_silabas_objetivo']}")
    if 'total_palabras' in mc:
        lineas.append(f"- Palabras correctas: {mc['palabras_correctas']}/{mc['total_palabras']} (PPC: {mc['PPC']}%)")
    lineas.append("")

    lineas.append("### Paso 1 — Errores de palabra")
    if informe['errores_palabra']:
        for e in informe['errores_palabra']:
            lineas.append(f"- {e['descripcion']}")
    else:
        lineas.append("- No se detectaron errores de palabra.")
    lineas.append("")

    lineas.append("### Paso 2 — Errores de sílaba")
    if informe['errores_silaba']:
        for e in informe['errores_silaba']:
            lineas.append(f"- {e['descripcion']}")
    else:
        lineas.append("- No se detectaron errores de sílaba.")
    lineas.append("")

    lineas.append("### Paso 3 — Errores sistémicos (fonema)")
    if informe['errores_sistemicos']:
        for e in informe['errores_sistemicos']:
            lineas.append(f"- {e['descripcion']}")
    else:
        lineas.append("- No se detectaron errores sistémicos.")
    lineas.append("")

    return '\n'.join(lineas)
