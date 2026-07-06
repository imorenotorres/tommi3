"""
Catálogo de explicaciones revisadas para cada tipo de error fonológico.

Cada entrada contiene:
  - nombre: nombre del error en español
  - explicacion: explicación breve del error
  - ejemplo: ejemplo concreto
  - consejo: qué repasar
  - referencia: tema de los apuntes

Este catálogo se usa para generar retroalimentación verificada (verde)
en lugar de depender de la LLM (rojo).
"""

CATALOGO = {

    # ═══════════════════════════════════════════════════════════════════
    # ERRORES SISTÉMICOS (afectan a un fonema individual)
    # ═══════════════════════════════════════════════════════════════════

    'sonorizacion': {
        'nombre': 'Sonorización',
        'explicacion': (
            'La sonorización consiste en producir un fonema sonoro en lugar '
            'del sordo correspondiente. Las cuerdas vocales vibran cuando '
            'no deberían hacerlo.'
        ),
        'ejemplo': '/p/ → /b/, /t/ → /d/, /k/ → /g/ (ej: "casa" → "gasa")',
        'consejo': (
            'Repasa los pares de fonemas oclusivos sordos y sonoros: /p/-/b/, /t/-/d/, '
            '/t/-/d/, /k/-/g/.'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de sonoridad',
    },

    'ensordecimiento': {
        'nombre': 'Ensordecimiento',
        'explicacion': (
            'El ensordecimiento consiste en producir un fonema sordo en lugar '
            'del sonoro correspondiente. Las cuerdas vocales no vibran cuando '
            'deberían hacerlo.'
        ),
        'ejemplo': '/b/ → /p/, /d/ → /t/, /g/ → /k/ (ej: "boca" → "poca")',
        'consejo': (
            'Repasa los pares de oclusivas sordas y sonoras. '
            'El ensordecimiento es el proceso inverso a la sonorización.'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de sonoridad',
    },

    'adelantamiento': {
        'nombre': 'Adelantamiento',
        'explicacion': (
            'El adelantamiento consiste en producir un fonema con un punto de '
            'articulación más anterior al correcto (más cerca de los labios de lo esperado.'
        ),
        'ejemplo': '/k/ → /t/ (velar → dental), /s/ → /f/ (alveolar → labiodental)',
        'consejo': (
            'Repasa la escala de lugares de articulación: bilabial, labiodental, '
            'interdental, dental, alveolar, palatal, velar. El adelantamiento '
            'desplaza hacia la izquierda de esta escala.'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de lugar',
    },

    'posteriorizacion': {
        'nombre': 'Posteriorización',
        'explicacion': (
            'La posteriorización consiste en producir un fonema con un punto de '
            'articulación más posterior al correcto '
            '(más atrás en la boca de lo esperado).'
        ),
        'ejemplo': '/t/ → /k/ (dental → velar), /θ/ → /s/ (interdental → alveolar)',
        'consejo': (
            'Repasa la escala de lugares de articulación: bilabial, labiodental, '
            'interdental, dental, alveolar, palatal, velar. La posteriorización '
            'desplaza hacia la derecha (hacia el velo del paladar).'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de lugar',
    },

    'nasalizacion': {
        'nombre': 'Nasalización',
        'explicacion': (
            'La nasalización consiste en producir un fonema nasal en lugar de '
            'uno oral. El aire sale por nariz y boca cuando debería salir solo por la boca.'
        ),
        'ejemplo': '/b/ → /m/, /d/ → /n/ (ej: "boca" → "moca")',
        'consejo': (
            'Repasa la diferencia entre fonemas orales y nasales. '
            'Los nasales del español son /m/, /n/ y /ɲ/.'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de nasalidad',
    },

    'desnasalizacion': {
        'nombre': 'Desnasalización',
        'explicacion': (
            'La desnasalización consiste en producir un fonema oral en lugar de '
            'uno nasal. El aire sale por la boca cuando debería salir por nariz y boca.'
        ),
        'ejemplo': '/m/ → /b/, /n/ → /d/ (ej: "mano" → "bano")',
        'consejo': (
            'Repasa los fonemas nasales /m/, /n/, /ɲ/ y sus correspondientes '
            'orales /b/, /d/, /g/. Comparten el mismo lugar de articulación.'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de nasalidad',
    },

    # Errores de modo (detectados por el analizador)

    'lenicion': {
        'nombre': 'Lenición (suavización)',
        'explicacion': (
            'La lenición consiste en producir un fonema con un modo de '
            'articulación más abierto o suave que el esperado.'
        ),
        'ejemplo': '/t/ → /s/ (oclusivo → fricativo)',
        'consejo': (
            'Repasa los modos de articulación. Ordenados de mayor a menor '
            'constricción, son estos:'
            ' oclusivos y africados > fricativos > nasales y líquidas'
            ' > vocales cerradas (/i, u/) > vocales medias (/e, o/) '
            ' > vocal abierta (/a/)'

        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de modo',
    },

    'forticion': {
        'nombre': 'Fortición (refuerzo)',
        'explicacion': (
            'La fortición consiste en producir un fonema con un modo de '
            'articulación más cerrado o fuerte que el esperado.'
        ),
        'ejemplo': '/s/ → /t/ (fricativo → oclusivo)',
            'Repasa los modos de articulación. Ordenados de mayor a menor '
            'constricción, son estos:'
            ' oclusivos y africados > fricativos > nasales y líquidas'
            ' > vocales cerradas (/i, u/) > vocales medias (/e, o/) '
            ' > vocal abierta (/a/)'

        'referencia': 'Tema 2: Errores sistémicos — rasgo de modo',
    },

    'cambio_modo': {
        'nombre': 'Cambio de modo',
        'explicacion': (
            'Cambio en el modo de articulación sin dirección clara de '
            'lenición o fortición (mismos niveles de apertura).'
        ),
        'ejemplo': '/l/ → /ɾ/ (lateral → vibrante simple)',
        'consejo': (
            'Repasa los distintos modos de articulación y las diferencias '
            'entre laterales, vibrantes, nasales, etc.'
        ),
        'referencia': 'Tema 2: Errores sistémicos — rasgo de modo',
    },

    # ═══════════════════════════════════════════════════════════════════
    # ERRORES DE SÍLABA (afectan a la estructura silábica)
    # ═══════════════════════════════════════════════════════════════════

    'omision_ataque': {
        'nombre': 'Omisión de ataque',
        'explicacion': (
            'El ataque (consonante o grupo consonántico al inicio de la sílaba) '
            'se omite por completo. La sílaba queda sin consonante inicial.'
        ),
        'ejemplo': '"/\'pla.to/" → "/\'a.to/" (se omite /pl/)',
        'consejo': (
            'Repasa la estructura de la sílaba (ataque + núcleo + coda). '
            'La omisión del ataque elimina todas las consonantes previas al núcleo.'
        ),
        'referencia': 'Tema 2: Errores de estructura silábica — Omisión de ataque',
    },

    'simplificacion_ataque': {
        'nombre': 'Simplificación de ataque',
        'explicacion': (
            'Un ataque complejo (dos consonantes, como /pl/, /bɾ/, /kl/) se '
            'reduce a una sola consonante. Es uno de los errores más frecuentes '
            'en el habla infantil.'
        ),
        'ejemplo': '"/\'pla.to/" → "/\'pa.to/" (se omite la líquida /l/)',
        'consejo': (
            'Repasa los grupos consonánticos válidos en ataque del español: '
            'oclusiva/fricativa + líquida (/l/ o /ɾ/). En la simplificación, '
            'generalmente se conserva la primera consonante y se omite la líquida.'
        ),
        'referencia': 'Tema 2: Errores de estructura silábica — Simplificación de ataque complejo',
    },

    'simplificacion_nucleo': {
        'nombre': 'Simplificación de núcleo (reducción de diptongo)',
        'explicacion': (
            'Un diptongo (dos vocales en la misma sílaba) se reduce a una sola '
            'vocal. Se pierde la semiconsonante o la semivocal. También puede '
            'ocurrir si un triptongo (3 vocales) se reduce a dos o a una sola vocal.'
        ),
        'ejemplo': '/\'tie.ne/ → /\'te.ne\' (el diptongo /ie/ se reduce a /e/)',
        'consejo': (
            'Repasa la diferencia entre diptongos e hiatos. Los diptongos' 
            'son secuencias de dos vocales que están dentro de la misma sílaba. '
            'Está formados por una vocal cerrada (/i/, /u/) y una abierta (/a/, /e/, /o/),'
            'o bien por dos vocales cerradas (/iu/, /ui/m siendo la primera una'
            'semiconsonante, la más cerrada. La simplificación elimina la vocal cerrada.'
        ),
        'referencia': 'Tema 2: Errores de estructura silábica — Simplificación del núcleo',
    },

    'omision_coda': {
        'nombre': 'Omisión de coda',
        'explicacion': (
            'La coda (consonante al final de la sílaba) se omite. La sílaba '
            'queda abierta (terminada en vocal) cuando debería ser cerrada.'
        ),
        'ejemplo': '/kan.\'tar/ → /ka.\'tar/ (se omite la coda /n/)',
        'consejo': (
            'Repasa la estructura silábica. Las codas válidas en español son '
            'limitadas: /n/, /s/, /l/, /ɾ/, /d/, /θ/ y algunos grupos. '
            'La omisión de coda es muy frecuente en el habla infantil.'
        ),
        'referencia': 'Tema 2: Errores de estructura silábica — Omisión de coda',
    },

    # ═══════════════════════════════════════════════════════════════════
    # ERRORES DE PALABRA (afectan a la estructura de la palabra)
    # ═══════════════════════════════════════════════════════════════════

    'asimilacion_regresiva': {
        'nombre': 'Asimilación regresiva',
        'explicacion': (
            'Un fonema cambia por influencia del fonema que le sigue. '
            'El sonido siguiente "atrae" al anterior hacia sus propios rasgos.'
        ),
        'ejemplo': '/a.po.\'lo.nio/ → /a.po.\'no.nio (/l/ se nasaliza por efecto de /n/)',
        'consejo': (
            'Repasa los procesos de asimilación. En la asimilación regresiva, '
            'el fonema afectado está ANTES del que causa el cambio. '
            'Se llama "regresiva" porque la influencia va de derecha a izquierda.'
        ),
        'referencia': 'Tema 2: Errores de palabra — asimilación',
    },

    'asimilacion_progresiva': {
        'nombre': 'Asimilación progresiva',
        'explicacion': (
            'Un fonema cambia por influencia del fonema que le precede. '
            'El sonido anterior "arrastra" al siguiente hacia sus propios rasgos.'
        ),
        'ejemplo': '/ma.no/ → /ma.mo/ (/n/ se labializa por efecto de /m/)',
        'consejo': (
            'Repasa los procesos de asimilación. En la asimilación progresiva, '
            'el fonema afectado está DESPUÉS del que causa el cambio. '
            'Se llama "progresiva" porque la influencia va de izquierda a derecha.'
        ),
        'referencia': 'Tema 2: Errores de palabra — asimilación',
    },

    'metatesis': {
        'nombre': 'Metátesis',
        'explicacion': (
            'Dos fonemas intercambian sus posiciones dentro de la palabra. '
            'Los sonidos son correctos, pero están en el lugar equivocado.'
        ),
        'ejemplo': '/\'me.sa/ → /\'se.ma/ (/m/ y /s/ intercambian posiciones)',
        'consejo': (
            'La metátesis no implica un error en la producción del fonema, '
            'sino en la secuenciación.'
        ),
        'referencia': 'Tema 2: Errores de palabra — metátesis',
    },

    'omision_silaba_atona': {
        'nombre': 'Omisión de sílaba átona',
        'explicacion': (
            'Se omite una sílaba átona (no acentuada) de la palabra. '
            'Es uno de los errores más frecuentes en el habla infantil, '
            'especialmente en palabras largas.'
        ),
        'ejemplo': '/ma.ri.\'po.sa/ → /ma.\'po.sa/ (se omite la sílaba átona /ɾi/)',
        'consejo': (
            'Repasa la estructura prosódica de la palabra. Las sílabas átonas '
            'son más vulnerables a la omisión, especialmente las pretónicas.'
        ),
        'referencia': 'Tema 2: Errores de palabra — omisión de sílabas',
    },

    'omision_silaba_tonica': {
        'nombre': 'Omisión de sílaba tónica',
        'explicacion': (
            'Se omite la sílaba tónica (acentuada) de la palabra. '
            'Es un error menos frecuente que la omisión de sílabas átonas '
            'y puede indicar dificultades más graves.'
        ),
        'ejemplo': '/θa.\'pa.to" → /\'θa.to/ (se omite la sílaba tónica /pa/)',
        'consejo': (
            'La omisión de la sílaba tónica es infrecuente porque la sílaba '
            'acentuada es la más prominente. Si aparece, puede indicar '
            'dificultades de planificación motora o de percepción.'
        ),
        'referencia': 'Tema 2: Errores de palabra — omisión de sílabas',
    },
}


def explicacion_para_error(tipo: str) -> dict | None:
    """Devuelve la explicación del catálogo para un tipo de error."""
    return CATALOGO.get(tipo)


def generar_retroalimentacion(errores_detectados: list[dict]) -> str:
    """
    Genera retroalimentación verificada a partir de los errores detectados.

    Args:
        errores_detectados: lista de dicts con 'tipo' y 'descripcion'
            (de errores_palabra + errores_silaba + errores_sistemicos)

    Returns:
        Texto en markdown con explicaciones y consejos.
    """
    if not errores_detectados:
        return "No se han detectado errores en este ejercicio."

    # Group errors by type (avoid repeating the same explanation)
    tipos_vistos = {}
    for e in errores_detectados:
        tipo = e.get('tipo', '')
        if tipo and tipo not in tipos_vistos:
            tipos_vistos[tipo] = e.get('descripcion', '')

    lineas = []

    for tipo, descripcion in tipos_vistos.items():
        info = CATALOGO.get(tipo)
        if info:
            lineas.append(f"**{info['nombre']}** — {descripcion}")
            lineas.append(f"- {info['explicacion']}")
            lineas.append(f"- *Ejemplo*: {info['ejemplo']}")
            lineas.append(f"- *Consejo*: {info['consejo']}")
            lineas.append(f"- *Referencia*: {info['referencia']}")
            lineas.append("")
        else:
            lineas.append(f"**{tipo}** — {descripcion}")
            lineas.append("")

    return '\n'.join(lineas)


def generar_retroalimentacion_transcripcion(items_corregidos: list[dict],
                                             ejercicio: dict) -> str:
    """
    Genera retroalimentación para ejercicios de transcripción.
    Analiza los errores comunes y da consejos específicos.

    Args:
        items_corregidos: items con resultado de corrección
        ejercicio: el ejercicio original

    Returns:
        Texto en markdown.
    """
    nivel = ejercicio.get('nivel', 1)
    tipo = ejercicio.get('tipo', 'fonologica')
    errores_comunes = []

    # Analyze what went wrong
    for item in items_corregidos:
        if item.get('correcto', True):
            continue
        # Could analyze specific phoneme errors here
        errores_comunes.append(item.get('ortografia', ''))

    if not errores_comunes:
        return "Todas las transcripciones son correctas en este ejercicio."

    from .ejercicios_transcripcion import _NIVEL_NOMBRES, _NIVEL_PISTAS

    lineas = []
    pista = _NIVEL_PISTAS.get(nivel)
    nombre = _NIVEL_NOMBRES.get(nivel, '')

    lineas.append(f"Ítems con errores: {len(errores_comunes)}")
    lineas.append("")

    if pista:
        lineas.append(f"**Recordatorio para el nivel {nivel} ({nombre})**:")
        lineas.append(f"- {pista}")
        lineas.append("")

    lineas.append("Revisa la transcripción comparando tu respuesta con la solución. "
                  "Los errores aparecen marcados en rojo.")

    return '\n'.join(lineas)
