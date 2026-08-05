"""
Inventario de alófonos del español peninsular (distinguidor).

Proporciona:
  - Catálogo completo de alófonos con descripción articulatoria
  - Reconocimiento: descripción articulatoria → símbolo IPA
  - Descripción: símbolo IPA → descripción articulatoria completa
  - Contexto de aparición de cada alófono
  - Ejercicios de identificación de alófonos

Uso:
    from alofonos import describir_alofono, reconocer_alofono, inventario_completo

    describir_alofono('β̞')
    # → {'simbolo': 'β̞', 'tipo': 'aproximante', 'lugar': 'bilabial',
    #    'sonoridad': 'sonora', 'fonema': '/b/', ...}

    reconocer_alofono('oclusiva bilabial sonora')
    # → [{'simbolo': '[b]', 'fonema': '/b/', ...}]
"""

# ═══════════════════════════════════════════════════════════════════════
# INVENTARIO DE ALÓFONOS
# ═══════════════════════════════════════════════════════════════════════

# Cada entrada: símbolo IPA, tipo (modo articulatorio), lugar, sonoridad,
# fonema del que es alófono, contexto de aparición, ejemplo.

INVENTARIO = [
    # ── Vocales ──────────────────────────────────────────────────────
    {
        "simbolo": "a", "tipo": "vocal", "subtipo": "abierta",
        "lugar": "central", "sonoridad": "sonora",
        "fonema": "/a/", "contexto": "Siempre",
        "ejemplo": ("casa", "[ˈka.sa]"),
        "descripcion_corta": "vocal abierta central",
    },
    {
        "simbolo": "e", "tipo": "vocal", "subtipo": "media",
        "lugar": "anterior", "sonoridad": "sonora",
        "fonema": "/e/", "contexto": "Siempre",
        "ejemplo": ("mesa", "[ˈme.sa]"),
        "descripcion_corta": "vocal media anterior",
    },
    {
        "simbolo": "i", "tipo": "vocal", "subtipo": "cerrada",
        "lugar": "anterior", "sonoridad": "sonora",
        "fonema": "/i/", "contexto": "En posición de núcleo silábico",
        "ejemplo": ("misa", "[ˈmi.sa]"),
        "descripcion_corta": "vocal cerrada anterior",
    },
    {
        "simbolo": "o", "tipo": "vocal", "subtipo": "media",
        "lugar": "posterior", "sonoridad": "sonora",
        "fonema": "/o/", "contexto": "Siempre",
        "ejemplo": ("cosa", "[ˈko.sa]"),
        "descripcion_corta": "vocal media posterior",
    },
    {
        "simbolo": "u", "tipo": "vocal", "subtipo": "cerrada",
        "lugar": "posterior", "sonoridad": "sonora",
        "fonema": "/u/", "contexto": "En posición de núcleo silábico",
        "ejemplo": ("muro", "[ˈmu.ɾo]"),
        "descripcion_corta": "vocal cerrada posterior",
    },
    # ── Semivocales y semiconsonantes ────────────────────────────────
    {
        "simbolo": "j", "tipo": "semiconsonante", "subtipo": "cerrada",
        "lugar": "anterior (palatal)", "sonoridad": "sonora",
        "fonema": "/i/", "contexto": "En posición prenuclear (antes del núcleo silábico), en diptongos crecientes",
        "ejemplo": ("pie", "[pje]"),
        "descripcion_corta": "semiconsonante palatal",
    },
    {
        "simbolo": "i̯", "tipo": "semivocal", "subtipo": "cerrada",
        "lugar": "anterior (palatal)", "sonoridad": "sonora",
        "fonema": "/i/", "contexto": "En posición postnuclear (después del núcleo silábico), en diptongos decrecientes",
        "ejemplo": ("aire", "[ˈai̯.ɾe]"),
        "descripcion_corta": "semivocal palatal",
    },
    {
        "simbolo": "w", "tipo": "semiconsonante", "subtipo": "cerrada",
        "lugar": "posterior (velar)", "sonoridad": "sonora",
        "fonema": "/u/", "contexto": "En posición prenuclear (antes del núcleo silábico), en diptongos crecientes",
        "ejemplo": ("fuego", "[ˈfwe.ɣ̞o]"),
        "descripcion_corta": "semiconsonante velar",
    },
    {
        "simbolo": "u̯", "tipo": "semivocal", "subtipo": "cerrada",
        "lugar": "posterior (velar)", "sonoridad": "sonora",
        "fonema": "/u/", "contexto": "En posición postnuclear (después del núcleo silábico), en diptongos decrecientes",
        "ejemplo": ("pausa", "[ˈpau̯.sa]"),
        "descripcion_corta": "semivocal velar",
    },
    # ── Oclusivas ────────────────────────────────────────────────────
    {
        "simbolo": "p", "tipo": "oclusiva",
        "lugar": "bilabial", "sonoridad": "sorda",
        "fonema": "/p/", "contexto": "En posición de ataque silábico",
        "ejemplo": ("pata", "[ˈpa.ta]"),
        "descripcion_corta": "oclusiva bilabial sorda",
    },
    {
        "simbolo": "b", "tipo": "oclusiva",
        "lugar": "bilabial", "sonoridad": "sonora",
        "fonema": "/b/", "contexto": "Tras pausa (inicio de enunciado) o tras consonante nasal",
        "ejemplo": ("vamos", "[ˈba.mos]"),
        "descripcion_corta": "oclusiva bilabial sonora",
    },
    {
        "simbolo": "t", "tipo": "oclusiva",
        "lugar": "dental", "sonoridad": "sorda",
        "fonema": "/t/", "contexto": "En posición de ataque silábico",
        "ejemplo": ("tapa", "[ˈta.pa]"),
        "descripcion_corta": "oclusiva dental sorda",
    },
    {
        "simbolo": "d", "tipo": "oclusiva",
        "lugar": "dental", "sonoridad": "sonora",
        "fonema": "/d/", "contexto": "Tras pausa, tras consonante nasal o tras consonante lateral",
        "ejemplo": ("donde", "[ˈdon̪.de]"),
        "descripcion_corta": "oclusiva dental sonora",
    },
    {
        "simbolo": "k", "tipo": "oclusiva",
        "lugar": "velar", "sonoridad": "sorda",
        "fonema": "/k/", "contexto": "En posición de ataque silábico",
        "ejemplo": ("casa", "[ˈka.sa]"),
        "descripcion_corta": "oclusiva velar sorda",
    },
    {
        "simbolo": "g", "tipo": "oclusiva",
        "lugar": "velar", "sonoridad": "sonora",
        "fonema": "/g/", "contexto": "Tras pausa (inicio de enunciado) o tras consonante nasal",
        "ejemplo": ("gato", "[ˈga.to]"),
        "descripcion_corta": "oclusiva velar sonora",
    },
    # ── Aproximantes ─────────────────────────────────────────────────
    {
        "simbolo": "β̞", "tipo": "aproximante",
        "lugar": "bilabial", "sonoridad": "sonora",
        "fonema": "/b/", "contexto": "En cualquier posición excepto tras pausa o nasal (distribución complementaria con [b])",
        "ejemplo": ("saber", "[sa.ˈβ̞eɾ]"),
        "descripcion_corta": "aproximante bilabial sonora",
    },
    {
        "simbolo": "ð̞", "tipo": "aproximante",
        "lugar": "interdental", "sonoridad": "sonora",
        "fonema": "/d/", "contexto": "En cualquier posición excepto tras pausa, nasal o lateral (distribución complementaria con [d])",
        "ejemplo": ("nada", "[ˈna.ð̞a]"),
        "descripcion_corta": "aproximante interdental sonora",
    },
    {
        "simbolo": "ɣ̞", "tipo": "aproximante",
        "lugar": "velar", "sonoridad": "sonora",
        "fonema": "/g/", "contexto": "En cualquier posición excepto tras pausa o nasal (distribución complementaria con [g])",
        "ejemplo": ("lago", "[ˈla.ɣ̞o]"),
        "descripcion_corta": "aproximante velar sonora",
    },
    {
        "simbolo": "ɹ", "tipo": "aproximante",
        "lugar": "alveolar", "sonoridad": "sonora",
        "fonema": "/ɾ/", "contexto": "En posición de coda silábica (implosiva)",
        "ejemplo": ("carta", "[ˈkaɹ.ta]"),
        "descripcion_corta": "aproximante alveolar sonora",
    },
    # ── Fricativas ───────────────────────────────────────────────────
    {
        "simbolo": "f", "tipo": "fricativa",
        "lugar": "labiodental", "sonoridad": "sorda",
        "fonema": "/f/", "contexto": "Siempre",
        "ejemplo": ("foca", "[ˈfo.ka]"),
        "descripcion_corta": "fricativa labiodental sorda",
    },
    {
        "simbolo": "θ", "tipo": "fricativa",
        "lugar": "interdental", "sonoridad": "sorda",
        "fonema": "/θ/", "contexto": "Siempre (en dialecto distinguidor)",
        "ejemplo": ("cena", "[ˈθe.na]"),
        "descripcion_corta": "fricativa interdental sorda",
    },
    {
        "simbolo": "s", "tipo": "fricativa",
        "lugar": "alveolar", "sonoridad": "sorda",
        "fonema": "/s/", "contexto": "Siempre (en dialecto distinguidor)",
        "ejemplo": ("sala", "[ˈsa.la]"),
        "descripcion_corta": "fricativa alveolar sorda",
    },
    {
        "simbolo": "ʝ", "tipo": "fricativa",
        "lugar": "palatal", "sonoridad": "sonora",
        "fonema": "/ʝ/", "contexto": "En cualquier posición excepto tras nasal",
        "ejemplo": ("mayo", "[ˈma.ʝo]"),
        "descripcion_corta": "fricativa palatal sonora",
    },
    {
        "simbolo": "x", "tipo": "fricativa",
        "lugar": "velar", "sonoridad": "sorda",
        "fonema": "/x/", "contexto": "Siempre",
        "ejemplo": ("jota", "[ˈxo.ta]"),
        "descripcion_corta": "fricativa velar sorda",
    },
    # ── Africadas ────────────────────────────────────────────────────
    {
        "simbolo": "ʧ", "tipo": "africada",
        "lugar": "palatal", "sonoridad": "sorda",
        "fonema": "/ʧ/", "contexto": "Siempre",
        "ejemplo": ("chico", "[ˈʧi.ko]"),
        "descripcion_corta": "africada palatal sorda",
    },
    {
        "simbolo": "ʤ", "tipo": "africada",
        "lugar": "palatal", "sonoridad": "sonora",
        "fonema": "/ʝ/", "contexto": "Tras consonante nasal",
        "ejemplo": ("cónyuge", "[ˈkoɲ.ʤu.xe]"),
        "descripcion_corta": "africada palatal sonora",
    },
    # ── Nasales ──────────────────────────────────────────────────────
    {
        "simbolo": "m", "tipo": "nasal",
        "lugar": "bilabial", "sonoridad": "sonora",
        "fonema": "/m/", "contexto": "Siempre como fonema /m/. También alófono de /n/ ante consonante bilabial",
        "ejemplo": ("mano", "[ˈma.no]"),
        "descripcion_corta": "nasal bilabial sonora",
        "tambien_alofono_de": "/n/",
        "contexto_como_alofono": "Ante consonante bilabial (/p/, /b/)",
        "ejemplo_como_alofono": ("un beso", "[um.ˈβ̞e.so]"),
    },
    {
        "simbolo": "ɱ", "tipo": "nasal",
        "lugar": "labiodental", "sonoridad": "sonora",
        "fonema": "/n/", "contexto": "Ante consonante labiodental (/f/)",
        "ejemplo": ("enfermo", "[eɱ.ˈfeɹ.mo]"),
        "descripcion_corta": "nasal labiodental sonora",
    },
    {
        "simbolo": "n̟", "tipo": "nasal",
        "lugar": "interdental", "sonoridad": "sonora",
        "fonema": "/n/", "contexto": "Ante consonante interdental (/θ/)",
        "ejemplo": ("once", "[ˈon̟.θe]"),
        "descripcion_corta": "nasal interdental sonora",
    },
    {
        "simbolo": "n̪", "tipo": "nasal",
        "lugar": "dental", "sonoridad": "sonora",
        "fonema": "/n/", "contexto": "Ante consonante dental (/t/, /d/)",
        "ejemplo": ("antes", "[ˈan̪.tes]"),
        "descripcion_corta": "nasal dental sonora",
    },
    {
        "simbolo": "n", "tipo": "nasal",
        "lugar": "alveolar", "sonoridad": "sonora",
        "fonema": "/n/", "contexto": "En posición de ataque silábico, o en coda ante alveolar o ante pausa",
        "ejemplo": ("nada", "[ˈna.ð̞a]"),
        "descripcion_corta": "nasal alveolar sonora",
    },
    {
        "simbolo": "nʲ", "tipo": "nasal",
        "lugar": "palatalizada", "sonoridad": "sonora",
        "fonema": "/n/", "contexto": "Ante consonante palatal (/ʧ/, /ʝ/, /ɲ/)",
        "ejemplo": ("ancho", "[ˈanʲ.ʧo]"),
        "descripcion_corta": "nasal palatalizada sonora",
    },
    {
        "simbolo": "ŋ", "tipo": "nasal",
        "lugar": "velar", "sonoridad": "sonora",
        "fonema": "/n/", "contexto": "Ante consonante velar (/k/, /g/, /x/)",
        "ejemplo": ("tengo", "[ˈteŋ.go]"),
        "descripcion_corta": "nasal velar sonora",
    },
    {
        "simbolo": "ɲ", "tipo": "nasal",
        "lugar": "palatal", "sonoridad": "sonora",
        "fonema": "/ɲ/", "contexto": "Siempre",
        "ejemplo": ("año", "[ˈa.ɲo]"),
        "descripcion_corta": "nasal palatal sonora",
    },
    # ── Laterales ────────────────────────────────────────────────────
    {
        "simbolo": "l", "tipo": "lateral",
        "lugar": "alveolar", "sonoridad": "sonora",
        "fonema": "/l/", "contexto": "En posición de ataque, o en coda ante consonante alveolar o ante pausa",
        "ejemplo": ("luna", "[ˈlu.na]"),
        "descripcion_corta": "lateral alveolar sonora",
    },
    {
        "simbolo": "l̟", "tipo": "lateral",
        "lugar": "interdental", "sonoridad": "sonora",
        "fonema": "/l/", "contexto": "Ante consonante interdental (/θ/)",
        "ejemplo": ("calzar", "[kal̟.ˈθaɹ]"),
        "descripcion_corta": "lateral interdental sonora",
    },
    {
        "simbolo": "l̪", "tipo": "lateral",
        "lugar": "dental", "sonoridad": "sonora",
        "fonema": "/l/", "contexto": "Ante consonante dental (/t/, /d/)",
        "ejemplo": ("alto", "[ˈal̪.to]"),
        "descripcion_corta": "lateral dental sonora",
    },
    # ── Vibrantes ────────────────────────────────────────────────────
    {
        "simbolo": "ɾ", "tipo": "vibrante simple",
        "lugar": "alveolar", "sonoridad": "sonora",
        "fonema": "/ɾ/", "contexto": "En posición de ataque silábico (prenuclear)",
        "ejemplo": ("pero", "[ˈpe.ɾo]"),
        "descripcion_corta": "vibrante simple alveolar sonora",
    },
    {
        "simbolo": "r", "tipo": "vibrante múltiple",
        "lugar": "alveolar", "sonoridad": "sonora",
        "fonema": "/r/", "contexto": "Siempre",
        "ejemplo": ("perro", "[ˈpe.ro]"),
        "descripcion_corta": "vibrante múltiple alveolar sonora",
    },
    # ── Aproximantes de oclusivas sordas en coda ─────────────────────
    {
        "simbolo": "β̞", "tipo": "aproximante",
        "lugar": "bilabial", "sonoridad": "sonora",
        "fonema": "/p/", "contexto": "En posición de coda silábica (alófono de /p/ en posición implosiva)",
        "ejemplo": ("apto", "[ˈaβ̞.to]"),
        "descripcion_corta": "aproximante bilabial sonora",
        "nota": "Alófono de /p/ en coda — mismo sonido que el alófono de /b/",
    },
    {
        "simbolo": "ð̞", "tipo": "aproximante",
        "lugar": "interdental", "sonoridad": "sonora",
        "fonema": "/t/", "contexto": "En posición de coda silábica (alófono de /t/ en posición implosiva)",
        "ejemplo": ("atlas", "[ˈað̞.las]"),
        "descripcion_corta": "aproximante interdental sonora",
        "nota": "Alófono de /t/ en coda — mismo sonido que el alófono de /d/",
    },
    {
        "simbolo": "ɣ̞", "tipo": "aproximante",
        "lugar": "velar", "sonoridad": "sonora",
        "fonema": "/k/", "contexto": "En posición de coda silábica (alófono de /k/ en posición implosiva)",
        "ejemplo": ("acto", "[ˈaɣ̞.to]"),
        "descripcion_corta": "aproximante velar sonora",
        "nota": "Alófono de /k/ en coda — mismo sonido que el alófono de /g/",
    },
]


# ═══════════════════════════════════════════════════════════════════════
# ÍNDICES PARA BÚSQUEDA RÁPIDA
# ═══════════════════════════════════════════════════════════════════════

# Índice por símbolo (primer match — los duplicados como β̞ se buscan por fonema)
_POR_SIMBOLO: dict[str, list[dict]] = {}
for _a in INVENTARIO:
    _POR_SIMBOLO.setdefault(_a["simbolo"], []).append(_a)

# Índice por fonema
_POR_FONEMA: dict[str, list[dict]] = {}
for _a in INVENTARIO:
    _POR_FONEMA.setdefault(_a["fonema"], []).append(_a)

# Sinónimos para normalización de búsqueda
_SINONIMOS_TIPO = {
    "oclusiva": "oclusiva", "oclusivo": "oclusiva",
    "plosiva": "oclusiva", "plosivo": "oclusiva",
    "fricativa": "fricativa", "fricativo": "fricativa",
    "africada": "africada", "africado": "africada",
    "aproximante": "aproximante",
    "lateral": "lateral",
    "vibrante": "vibrante simple",
    "vibrante simple": "vibrante simple", "tap": "vibrante simple", "flap": "vibrante simple",
    "vibrante múltiple": "vibrante múltiple", "trill": "vibrante múltiple", "vibrante multiple": "vibrante múltiple",
    "nasal": "nasal",
    "semiconsonante": "semiconsonante",
    "semivocal": "semivocal",
    "vocal": "vocal",
}

_SINONIMOS_LUGAR = {
    "bilabial": "bilabial",
    "labiodental": "labiodental",
    "interdental": "interdental",
    "dental": "dental",
    "alveolar": "alveolar",
    "palatal": "palatal", "alveopalatal": "palatal",
    "palatalizada": "palatalizada", "palatalizado": "palatalizada",
    "velar": "velar",
    "central": "central",
    "anterior": "anterior", "palatal": "palatal",
    "posterior": "posterior",
}

_SINONIMOS_SONORIDAD = {
    "sorda": "sorda", "sordo": "sorda", "áfona": "sorda",
    "sonora": "sonora", "sonoro": "sonora",
}


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES PÚBLICAS
# ═══════════════════════════════════════════════════════════════════════

def describir_alofono(simbolo: str) -> list[dict]:
    """Dado un símbolo IPA, devuelve la(s) descripción(es) articulatoria(s).

    Args:
        simbolo: Símbolo IPA (ej: 'β̞', 'b', 'ŋ'). Acepta con o sin corchetes.

    Returns:
        Lista de dicts con toda la información del alófono.
        Lista vacía si no se encuentra.
    """
    simbolo = simbolo.strip().strip("[]")
    return _POR_SIMBOLO.get(simbolo, [])


def describir_fonema(fonema: str) -> list[dict]:
    """Dado un fonema, devuelve todos sus alófonos con sus contextos.

    Args:
        fonema: Fonema IPA (ej: '/b/', 'b'). Acepta con o sin barras.

    Returns:
        Lista de dicts (un alófono por entrada).
    """
    fonema = fonema.strip()
    if not fonema.startswith("/"):
        fonema = f"/{fonema}/"
    return _POR_FONEMA.get(fonema, [])


def reconocer_alofono(descripcion: str) -> list[dict]:
    """Dado una descripción articulatoria, encuentra el/los alófono(s) correspondientes.

    Acepta descripciones parciales o completas, en cualquier orden:
        - "oclusiva bilabial sonora" → [b]
        - "nasal velar" → [ŋ]
        - "aproximante bilabial" → [β̞]
        - "bilabial sonora" → [b], [β̞], [m]

    Args:
        descripcion: Texto con rasgos articulatorios (tipo, lugar, sonoridad).

    Returns:
        Lista de alófonos que coinciden con TODOS los rasgos especificados.
    """
    palabras = descripcion.lower().strip().split()

    # Extraer rasgos de la descripción
    tipo_buscado = None
    lugar_buscado = None
    sonoridad_buscada = None

    for palabra in palabras:
        if palabra in _SINONIMOS_TIPO and tipo_buscado is None:
            tipo_buscado = _SINONIMOS_TIPO[palabra]
        elif palabra in _SINONIMOS_LUGAR and lugar_buscado is None:
            lugar_buscado = _SINONIMOS_LUGAR[palabra]
        elif palabra in _SINONIMOS_SONORIDAD and sonoridad_buscada is None:
            sonoridad_buscada = _SINONIMOS_SONORIDAD[palabra]

    # Buscar también combinaciones de dos palabras ("vibrante simple", "vibrante múltiple")
    texto = " ".join(palabras)
    for clave, valor in _SINONIMOS_TIPO.items():
        if " " in clave and clave in texto:
            tipo_buscado = valor

    if tipo_buscado is None and lugar_buscado is None and sonoridad_buscada is None:
        return []

    resultados = []
    for a in INVENTARIO:
        coincide = True
        if tipo_buscado is not None:
            tipo_a = a["tipo"].lower()
            # Para vibrantes, comparar incluyendo subtipo
            if "vibrante" in tipo_buscado:
                if tipo_a != tipo_buscado:
                    coincide = False
            elif tipo_a != tipo_buscado:
                coincide = False
        if lugar_buscado is not None and coincide:
            lugar_a = a["lugar"].lower()
            if lugar_buscado not in lugar_a:
                coincide = False
        if sonoridad_buscada is not None and coincide:
            if a["sonoridad"] != sonoridad_buscada:
                coincide = False
        if coincide:
            resultados.append(a)

    return resultados


def inventario_completo(solo_tipo: str = None) -> list[dict]:
    """Devuelve el inventario completo, opcionalmente filtrado por tipo.

    Args:
        solo_tipo: Filtrar por tipo (ej: 'oclusiva', 'fricativa', 'nasal', 'vocal').

    Returns:
        Lista de alófonos.
    """
    if solo_tipo is None:
        return list(INVENTARIO)
    tipo = _SINONIMOS_TIPO.get(solo_tipo.lower(), solo_tipo.lower())
    return [a for a in INVENTARIO if a["tipo"].lower() == tipo]


def formatear_descripcion(alofono: dict, *, incluir_contexto: bool = True) -> str:
    """Formatea la descripción de un alófono para presentación en chat.

    Returns:
        String en markdown con la descripción completa.
    """
    lineas = []
    simbolo = alofono["simbolo"]
    desc = alofono["descripcion_corta"]
    fonema = alofono["fonema"]

    lineas.append(f"**[{simbolo}]** — {desc}")
    lineas.append(f"- Fonema: {fonema}")
    lineas.append(f"- Modo: {alofono['tipo']}")
    lineas.append(f"- Lugar: {alofono['lugar']}")
    lineas.append(f"- Sonoridad: {alofono['sonoridad']}")

    if incluir_contexto:
        lineas.append(f"- Contexto: {alofono['contexto']}")

    pal, trans = alofono["ejemplo"]
    lineas.append(f"- Ejemplo: *{pal}* → {trans}")

    if "nota" in alofono:
        lineas.append(f"- Nota: {alofono['nota']}")

    if "tambien_alofono_de" in alofono:
        lineas.append(f"- También alófono de: {alofono['tambien_alofono_de']} ({alofono['contexto_como_alofono']})")
        pal2, trans2 = alofono["ejemplo_como_alofono"]
        lineas.append(f"  Ejemplo: *{pal2}* → {trans2}")

    return "\n".join(lineas)


def formatear_inventario_fonema(fonema: str) -> str | None:
    """Formatea todos los alófonos de un fonema para presentación en chat.

    Returns:
        String en markdown, o None si el fonema no existe.
    """
    alofonos = describir_fonema(fonema)
    if not alofonos:
        return None

    fonema_fmt = alofonos[0]["fonema"]
    lineas = [f"## Alófonos de {fonema_fmt}\n"]

    for a in alofonos:
        lineas.append(formatear_descripcion(a))
        lineas.append("")

    return "\n".join(lineas)


def formatear_reconocimiento(descripcion: str) -> str:
    """Busca alófonos por descripción articulatoria y formatea el resultado.

    Returns:
        String en markdown con los resultados.
    """
    resultados = reconocer_alofono(descripcion)

    if not resultados:
        return (f"No se ha encontrado ningún alófono que coincida con "
                f"la descripción «{descripcion}».\n\n"
                f"Prueba con rasgos como: oclusiva, fricativa, nasal, lateral, "
                f"vibrante, aproximante, bilabial, dental, alveolar, palatal, "
                f"velar, sorda, sonora.")

    if len(resultados) == 1:
        return formatear_descripcion(resultados[0])

    lineas = [f"Se han encontrado **{len(resultados)} alófonos** que coinciden "
              f"con «{descripcion}»:\n"]
    for a in resultados:
        lineas.append(formatear_descripcion(a, incluir_contexto=False))
        lineas.append("")

    return "\n".join(lineas)
