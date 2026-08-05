"""
Generador de ejercicios de errores fonológicos.

Genera ejercicios parametrizados por tipo de error y dificultad,
listos para presentar al alumno. Las palabras se seleccionan del
banco_palabras.py según sus propiedades (sílabas, codas, ataques
complejos, divergencias AFI).
"""

import random
from .generador import generar_errores, ERRORES_SISTEMICOS, ERRORES_SILABA, ERRORES_PALABRA
from .analizador import analizar
from .silaba import reconstruir_transcripcion, parsear_silabas
from .banco_palabras import BANCO_PALABRAS, seleccionar_palabras


# ── Legacy BANCO_PALABRAS_DICT (kept for backwards compatibility) ─────
# The old dict-based format is no longer used for word selection.
# Word selection now uses banco_palabras.seleccionar_palabras().

_LEGACY_BANCO = {
    # Bisílabas simples (cubren los 18 fonemas consonánticos + 5 vocales)
    2: [
        ("casa", "ˈka.sa"),
        ("mesa", "ˈme.sa"),
        ("niña", "ˈni.ɲa"),
        ("boca", "ˈbo.ka"),
        ("dedo", "ˈde.do"),
        ("gato", "ˈga.to"),
        ("luna", "ˈlu.na"),
        ("pato", "ˈpa.to"),
        ("taza", "ˈta.θa"),
        ("vaso", "ˈba.so"),
        ("nube", "ˈnu.be"),
        ("peso", "ˈpe.so"),
        ("foca", "ˈfo.ka"),
        ("mano", "ˈma.no"),
        ("cama", "ˈka.ma"),
        ("chilla", "ˈtʃi.ʝa"),     # tʃ, ʝ
        ("cayo", "ˈka.ʝo"),         # ʝ
        ("mocho", "ˈmo.tʃo"),       # tʃ
        ("jefe", "ˈxe.fe"),          # x
        ("rojo", "ˈro.xo"),          # r, x
        ("carro", "ˈka.ro"),         # r
        ("para", "ˈpa.ɾa"),          # ɾ
        ("cero", "ˈθe.ɾo"),          # ɾ
        ("llave", "ˈʝa.be"),         # ʝ
        ("pollo", "ˈpo.ʝo"),         # ʝ
    ],
    # Trisílabas (cubren los 18 fonemas consonánticos)
    3: [
        ("zapato", "θa.'pa.to"),
        ("maleta", "ma.'le.ta"),
        ("camisa", "ka.'mi.sa"),
        ("pelota", "pe.'lo.ta"),
        ("banana", "ba.'na.na"),
        ("cabeza", "ka.'be.θa"),
        ("madera", "ma.'de.ɾa"),
        ("cocina", "ko.'θi.na"),
        ("salida", "sa.'li.da"),
        ("moneda", "mo.'ne.da"),
        ("cerebro", "θe.'ɾe.bɾo"),
        ("croqueta", "kɾo.'ke.ta"),
        ("machete", "ma.'tʃe.te"),   # tʃ
        ("cuchillo", "ku.'tʃi.ʝo"),  # tʃ, ʝ
        ("gallina", "ga.'ʝi.na"),    # g, ʝ
        ("tobillo", "to.'bi.ʝo"),    # ʝ
        ("guitarra", "gi.'ta.ra"),   # g, r
        ("cigarra", "θi.'ga.ra"),    # r
        ("pizarra", "pi.'θa.ra"),    # r
        ("jirafa", "xi.'ɾa.fa"),     # x, f
        ("tijera", "ti.'xe.ɾa"),     # x
        ("mochila", "mo.'tʃi.la"),   # tʃ
        ("montaña", "mon.'ta.ɲa"),   # ɲ
        ("cigüeña", "θi.'gue.ɲa"),  # ɲ
    ],
    # Tetrasílabas
    4: [
        ("mariposa", "ma.ɾi.'po.sa"),
        ("magdalena", "mag.da.'le.na"),
        ("chocolate", "tʃo.ko.'la.te"),
        ("bicicleta", "bi.θi.'kle.ta"),
        ("elefante", "e.le.'fan.te"),
        ("zapatilla", "θa.pa.'ti.ʝa"),
        ("caramelo", "ka.ɾa.'me.lo"),
        ("cocodrilo", "ko.ko.'dɾi.lo"),
        ("bestiario", "bes.'tia.ɾio"),
        ("estudiante", "es.tu.'dian.te"),
    ],
    # 5+ sílabas
    5: [
        ("superficial", "su.peɾ.fi.'θial"),
        ("murciélago", "muɾ.'θie.la.go"),
        ("celebración", "θe.le.bɾa.'θion"),
        ("puertecilla", "pueɾ.te.'θi.ʝa"),
        ("refrigerador", "re.fɾi.xe.ɾa.'doɾ"),
        ("extraordinario", "eks.tɾa.oɾ.di.'na.ɾio"),
        ("multiplicación", "mul.ti.pli.ka.'θion"),
        ("responsabilidad", "res.pon.sa.bi.li.'dad"),
    ],
    # Con ataques complejos
    'complejas': [
        ("tren", "ˈtɾen"),
        ("plan", "ˈplan"),
        ("blusa", "ˈblu.sa"),
        ("grupo", "ˈgɾu.po"),
        ("crema", "ˈkɾe.ma"),
        ("plato", "ˈpla.to"),
        ("fresa", "ˈfɾe.sa"),
        ("primo", "ˈpɾi.mo"),
        ("brazo", "ˈbɾa.θo"),
        ("tropa", "ˈtɾo.pa"),
        ("cerebro", "θe.'ɾe.bɾo"),
        ("croqueta", "kɾo.'ke.ta"),
        ("celebración", "θe.le.bɾa.'θion"),
        ("refrigerador", "re.fɾi.xe.ɾa.'doɾ"),
        ("multiplicación", "mul.ti.pli.ka.'θion"),
    ],
    # Con diptongos
    'diptongos': [
        ("tiene", "ˈtie.ne"),
        ("bueno", "ˈbue.no"),
        ("fuego", "ˈfue.go"),
        ("siete", "ˈsie.te"),
        ("nuevo", "ˈnue.bo"),
        ("cielo", "ˈθie.lo"),
        ("puerta", "ˈpueɾ.ta"),
        ("piedra", "ˈpie.dɾa"),
        ("murciélago", "muɾ.'θie.la.go"),
        ("bestiario", "bes.'tia.ɾio"),
        ("estudiante", "es.tu.'dian.te"),
        ("puertecilla", "pueɾ.te.'θi.ʝa"),
        ("superficial", "su.peɾ.fi.'θial"),
        ("celebración", "θe.le.bɾa.'θion"),
    ],
    # Con codas
    'codas': [
        ("pan", "ˈpan"),
        ("sol", "ˈsol"),
        ("mar", "ˈmaɾ"),
        ("luz", "ˈluθ"),
        ("arbol", "ˈaɾ.bol"),
        ("cartel", "kaɾ.'tel"),
        ("cantar", "kan.'taɾ"),
        ("comprar", "kom.'pɾaɾ"),
        ("estudiante", "es.tu.'dian.te"),
        ("bestiario", "bes.'tia.ɾio"),
        ("murciélago", "muɾ.'θie.la.go"),
        ("superficial", "su.peɾ.fi.'θial"),
        ("celebración", "θe.le.bɾa.'θion"),
        ("puertecilla", "pueɾ.te.'θi.ʝa"),
        ("responsabilidad", "res.pon.sa.bi.li.'dad"),
    ],
}


# ── Niveles de dificultad ──────────────────────────────────────────────

NIVELES = {
    'basico': {
        'descripcion': 'Un solo tipo de error, palabras cortas',
        'num_errores': 1,
        'num_silabas_min': 2,
        'num_silabas_max': 2,
        'mezclar_tipos': False,
    },
    'intermedio': {
        'descripcion': 'Uno o dos errores, palabras con codas, ataques complejos y diptongos',
        'num_errores': 2,
        'num_silabas_min': 2,
        'num_silabas_max': 4,
        'mezclar_tipos': False,
    },
    'avanzado': {
        'descripcion': 'Varios errores de diferentes tipos, palabras largas y complejas',
        'num_errores': 3,
        'num_silabas_min': 3,
        'num_silabas_max': 99,
        'mezclar_tipos': True,
    },
}


def generar_ejercicio(tipo: str = None, nivel: str = 'basico',
                      num_items: int = 5, seed: int = None) -> dict:
    """
    Genera un ejercicio de identificación de errores fonológicos.

    Las palabras se seleccionan del banco según el tipo de error y el nivel:
    - Errores sistémicos: se priorizan palabras con grafías AFI divergentes
    - Errores de sílaba: se priorizan palabras con codas y ataques complejos
    - Errores de palabra: se priorizan palabras con 3+ sílabas

    Args:
        tipo: Tipo de error ('sistemico', 'silaba', 'palabra', o nombre específico).
              Si None y nivel avanzado, mezcla tipos.
        nivel: 'basico', 'intermedio', 'avanzado'
        num_items: Número de palabras en el ejercicio
        seed: Semilla para reproducibilidad

    Returns:
        dict con:
          - instrucciones: texto para el alumno
          - items: lista de dicts con objetivo, producido, solucion
          - nivel: nivel del ejercicio
          - tipo_error: tipo de error solicitado
    """
    rng = random.Random(seed)
    config = NIVELES.get(nivel, NIVELES['basico'])

    # Seleccionar palabras según tipo de error y nivel
    palabras_disponibles = seleccionar_palabras(
        num_silabas_min=config['num_silabas_min'],
        num_silabas_max=config['num_silabas_max'],
        solo_estructurales=(tipo in ('silaba', 'palabra')),
        solo_sistemicas=(tipo == 'sistemico'),
        requiere_codas=(tipo == 'silaba' and nivel != 'basico'),
        requiere_ataques_complejos=(tipo == 'silaba' and nivel == 'avanzado'),
    )

    # Fallback: use all words in range if selection is too narrow
    if len(palabras_disponibles) < num_items:
        palabras_disponibles = seleccionar_palabras(
            num_silabas_min=config['num_silabas_min'],
            num_silabas_max=config['num_silabas_max'],
        )

    if not palabras_disponibles:
        palabras_disponibles = BANCO_PALABRAS  # ultimate fallback

    if num_items > len(palabras_disponibles):
        seleccionadas = palabras_disponibles
    else:
        seleccionadas = rng.sample(palabras_disponibles, num_items)

    # Determinar tipos de error
    if tipo:
        tipos = [tipo]
    elif config['mezclar_tipos']:
        tipos = ['sistemico', 'silaba', 'palabra']
    else:
        tipos = ['sistemico']  # por defecto

    # Generar items
    items = []
    for palabra in seleccionadas:
        ortografia = palabra['ortografia']
        transcripcion = palabra['transcripcion']

        producido, errores = generar_errores(
            transcripcion,
            tipos=tipos,
            num_errores=config['num_errores'],
            seed=rng.randint(0, 100000)
        )

        items.append({
            'ortografia': ortografia,
            'objetivo': transcripcion,
            'producido': producido,
            'errores': errores,
            'num_errores': len(errores),
        })

    # Instrucciones
    tipo_desc = tipo or ('varios tipos' if config['mezclar_tipos'] else 'sistémico')
    instrucciones = _generar_instrucciones(tipo_desc, nivel, config)

    return {
        'instrucciones': instrucciones,
        'items': items,
        'nivel': nivel,
        'tipo_error': tipo_desc,
        'num_items': len(items),
    }


def corregir_ejercicio(ejercicio: dict, respuestas: list[dict]) -> dict:
    """
    Corrige las respuestas de un alumno a un ejercicio.

    Args:
        ejercicio: El ejercicio generado por generar_ejercicio()
        respuestas: Lista de dicts con las respuestas del alumno.
                    Cada dict: {'item': int, 'errores_identificados': list[str]}

    Returns:
        dict con:
          - puntuacion: porcentaje de aciertos
          - items_corregidos: lista con corrección detallada de cada item
          - retroalimentacion: texto de retroalimentación
    """
    items_corregidos = []
    total_errores = 0
    errores_identificados_correctamente = 0
    errores_inventados = 0
    errores_no_identificados = 0

    for i, item in enumerate(ejercicio['items']):
        resp = next((r for r in respuestas if r.get('item') == i), None)

        errores_reales = {e['tipo'] for e in item['errores']}
        total_errores += len(errores_reales)

        if resp:
            errores_alumno = set(resp.get('errores_identificados', []))
            aciertos = errores_reales & errores_alumno
            inventados = errores_alumno - errores_reales
            no_encontrados = errores_reales - errores_alumno

            errores_identificados_correctamente += len(aciertos)
            errores_inventados += len(inventados)
            errores_no_identificados += len(no_encontrados)

            items_corregidos.append({
                'item': i,
                'ortografia': item['ortografia'],
                'objetivo': item['objetivo'],
                'producido': item['producido'],
                'errores_reales': [e['descripcion'] for e in item['errores']],
                'aciertos': list(aciertos),
                'no_identificados': list(no_encontrados),
                'inventados': list(inventados),
                'correcto': len(no_encontrados) == 0 and len(inventados) == 0,
            })
        else:
            errores_no_identificados += len(errores_reales)
            items_corregidos.append({
                'item': i,
                'ortografia': item['ortografia'],
                'sin_respuesta': True,
                'errores_reales': [e['descripcion'] for e in item['errores']],
            })

    puntuacion = round(errores_identificados_correctamente / total_errores * 100, 1) if total_errores > 0 else 0

    return {
        'puntuacion': puntuacion,
        'total_errores': total_errores,
        'identificados': errores_identificados_correctamente,
        'no_identificados': errores_no_identificados,
        'inventados': errores_inventados,
        'items_corregidos': items_corregidos,
        'retroalimentacion': _generar_retroalimentacion(puntuacion, items_corregidos),
    }


def _generar_instrucciones(tipo: str, nivel: str, config: dict) -> str:
    """Genera el texto de instrucciones para el alumno."""
    intro = "A continuación se presentan varias palabras. Para cada una se indica:\n"
    intro += "- **Objetivo**: lo que el paciente debería haber dicho\n"
    intro += "- **Producido**: lo que el paciente realmente ha dicho\n\n"

    if tipo == 'sistemico':
        intro += "**Tu tarea**: Identifica los **errores sistémicos** (errores que afectan a un fonema individual: "
        intro += "sonorización, ensordecimiento, lenición, fortición, adelantamiento, posteriorización, "
        intro += "nasalización o desnasalización).\n"
    elif tipo == 'silaba':
        intro += "**Tu tarea**: Identifica los **errores de sílaba** (omisión de ataque, simplificación de ataque, "
        intro += "simplificación de núcleo u omisión de coda).\n"
    elif tipo == 'palabra':
        intro += "**Tu tarea**: Identifica los **errores de palabra** (asimilación regresiva o progresiva, "
        intro += "metátesis, omisión de sílaba átona o tónica).\n"
    else:
        intro += "**Tu tarea**: Identifica **todos los tipos de errores** (sistémicos, de sílaba y de palabra).\n"

    intro += f"\n**Nivel**: {nivel} — {config['descripcion']}\n"
    intro += f"**Número de errores por palabra**: {config['num_errores']}\n"

    return intro


def _generar_retroalimentacion(puntuacion: float, items: list[dict]) -> str:
    """Genera texto de retroalimentación pedagógica."""
    lineas = []

    if puntuacion >= 90:
        lineas.append("**Excelente trabajo.** Has identificado casi todos los errores correctamente.")
    elif puntuacion >= 70:
        lineas.append("**Buen trabajo.** Has identificado la mayoría de los errores, aunque hay algunos que se te han escapado.")
    elif puntuacion >= 50:
        lineas.append("**Resultado aceptable.** Necesitas repasar algunos tipos de errores.")
    else:
        lineas.append("**Necesitas más práctica.** Te recomiendo repasar los tipos de errores en el Tema 2.")

    # Errores más frecuentes no identificados
    tipos_fallidos = []
    for item in items:
        for t in item.get('no_identificados', []):
            tipos_fallidos.append(t)

    if tipos_fallidos:
        from collections import Counter
        conteo = Counter(tipos_fallidos)
        mas_comun = conteo.most_common(3)
        lineas.append("\n**Errores que más te cuestan:**")
        for tipo, n in mas_comun:
            lineas.append(f"- {tipo}: no identificado {n} vez/veces")

    return '\n'.join(lineas)
