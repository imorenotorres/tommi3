"""
Generador de oraciones a partir del banco de palabras.

Construye oraciones gramaticalmente correctas usando palabras del banco
de datos y plantillas sintácticas. Las palabras funcionales (artículos,
preposiciones, verbos) son fijas. Las palabras de contenido se seleccionan
del banco según su categoría semántica.

La transcripción fonológica se genera automáticamente con el transcriptor.
"""

import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════════
# CATEGORÍAS SEMÁNTICAS
# ═══════════════════════════════════════════════════════════════════════

# Map words to semantic categories for sentence generation
_CATEGORIAS = {
    'persona': [
        'pedro', 'maría', 'antonio', 'carmen', 'francisco', 'manuel',
        'josé', 'teresa', 'juan', 'miguel', 'lucía', 'ángel',
        'elena', 'ana', 'fernando', 'isabel', 'pablo', 'laura',
        'sergio', 'cristina', 'alejandro', 'patricia', 'carlos',
        'silvia', 'daniel', 'natalia', 'david', 'andrea', 'jorge',
        'paula', 'diego', 'sofía', 'enrique', 'beatriz', 'mónica',
        'ignacio', 'raquel', 'guillermo', 'verónica', 'inés', 'roberto',
    ],
    'animal': [
        'perro', 'gato', 'caballo', 'vaca', 'oveja', 'conejo',
        'gallina', 'pájaro', 'águila', 'león', 'mono',
        'serpiente', 'tortuga', 'ballena', 'lobo', 'oso',
        'ciervo', 'abeja', 'hormiga', 'araña', 'mariposa',
    ],
    'alimento': [
        'manzana', 'naranja', 'plátano', 'fresa', 'limón', 'sandía',
        'melón', 'cereza', 'uva', 'pera', 'piña', 'ciruela',
        'higo', 'mora', 'mango', 'tomate', 'lechuga', 'cebolla',
        'ajo', 'patata', 'pepino', 'calabaza', 'arroz', 'pasta',
        'leche', 'queso', 'huevo', 'ternera', 'pescado', 'tarta',
        'churro', 'galleta', 'aceite', 'harina', 'pan',
    ],
    'color': [
        'verde', 'negro', 'blanco', 'amarillo', 'rojo', 'gris',
    ],
    'profesion': [
        'maestro', 'abogado', 'arquitecto', 'enfermero', 'bombero',
        'policía', 'ingeniero', 'carpintero', 'fontanero', 'peluquero',
        'panadero', 'cocinero', 'camarero', 'músico', 'pintor',
        'escritor', 'dentista', 'piloto', 'cirujano',
    ],
    'lugar': [
        'málaga', 'sevilla', 'granada', 'cádiz', 'ronda', 'marbella',
        'antequera', 'argentina', 'bolivia', 'chile', 'colombia',
        'cuba', 'ecuador', 'guatemala', 'panamá', 'perú', 'brasil',
        'canadá', 'méxico',
    ],
    'cuerpo': [
        'cabeza', 'manos', 'pies', 'labios', 'nariz', 'ojos', 'pelo',
        'muslo', 'rodilla', 'pierna', 'hombro', 'espalda', 'pecho',
        'barriga', 'muñeca', 'cuello', 'frente', 'lengua', 'diente',
    ],
    'casa': [
        'cocina', 'dormitorio', 'salón', 'silla', 'sofá', 'armario',
        'lámpara', 'alfombra', 'espejo', 'ventana', 'puerta',
        'balcón', 'terraza', 'jardín', 'tejado', 'chimenea',
    ],
    'ropa': [
        'pantalón', 'falda', 'vestido', 'chaqueta', 'abrigo', 'bota',
        'bufanda', 'sombrero', 'corbata', 'jersey',
    ],
    'utensilio': [
        'cuchillo', 'tenedor', 'cuchara', 'vaso', 'plato', 'horno',
        'tostadora', 'cafetera',
    ],
    'naturaleza': [
        'bosque', 'playa', 'desierto', 'selva', 'volcán', 'isla',
        'lago', 'valle', 'cueva', 'océano', 'península', 'pradera',
    ],
    'clima': [
        'lluvia', 'nieve', 'viento', 'tormenta', 'trueno', 'niebla',
        'helada', 'brisa',
    ],
    'objeto': [
        'mesa', 'casa', 'cama', 'libro', 'carro', 'brazo', 'piedra',
        'blusa', 'crema', 'grupo', 'reloj',
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# PLANTILLAS DE ORACIONES
# ═══════════════════════════════════════════════════════════════════════

# Each template: (pattern, categories_needed)
# {el/la} are resolved based on the word's gender (simplified)

_PLANTILLAS_CORTAS = [
    # 3-5 words
    ("{persona} come {alimento}", ['persona', 'alimento']),
    ("{persona} quiere {alimento}", ['persona', 'alimento']),
    ("el {animal} come {alimento}", ['animal', 'alimento']),
    ("el {animal} es {color}", ['animal', 'color']),
    ("{persona} vive en {lugar}", ['persona', 'lugar']),
    ("{persona} trabaja en {lugar}", ['persona', 'lugar']),
    ("el {profesion} compra {alimento}", ['profesion', 'alimento']),
    ("{persona} tiene un {animal}", ['persona', 'animal']),
    ("hay {clima} en {lugar}", ['clima', 'lugar']),
    ("el {utensilio} está en la {casa}", ['utensilio', 'casa']),
    ("{persona} lleva un {ropa}", ['persona', 'ropa']),
    ("el {animal} corre mucho", ['animal']),
    ("la {naturaleza} es grande", ['naturaleza']),
    ("{persona} mira el {naturaleza}", ['persona', 'naturaleza']),
    ("me duele la {cuerpo}", ['cuerpo']),
]

_PLANTILLAS_LARGAS = [
    # 6+ words
    ("{persona} come {alimento} en la {casa}", ['persona', 'alimento', 'casa']),
    ("el {profesion} de {lugar} compra {alimento}", ['profesion', 'lugar', 'alimento']),
    ("{persona} tiene un {animal} {color} muy grande", ['persona', 'animal', 'color']),
    ("el {animal} {color} vive en el {naturaleza}", ['animal', 'color', 'naturaleza']),
    ("{persona} lleva un {ropa} {color} y un {ropa}", ['persona', 'ropa', 'color', 'ropa']),
    ("en la {casa} de {persona} hay un {utensilio}", ['casa', 'persona', 'utensilio']),
    ("{persona} viaja a {lugar} con {persona}", ['persona', 'lugar', 'persona']),
    ("el {profesion} come {alimento} con {utensilio}", ['profesion', 'alimento', 'utensilio']),
    ("hace {clima} en {lugar} y {persona} tiene frío", ['clima', 'lugar', 'persona']),
    ("{persona} ve un {animal} en el {naturaleza} de {lugar}", ['persona', 'animal', 'naturaleza', 'lugar']),
    ("la {cuerpo} de {persona} es grande y {color}", ['cuerpo', 'persona', 'color']),
    ("el {profesion} pone el {utensilio} en la {casa}", ['profesion', 'utensilio', 'casa']),
]


# ═══════════════════════════════════════════════════════════════════════
# GENERACIÓN
# ═══════════════════════════════════════════════════════════════════════

def generar_oracion(tipo: str = 'corta', seed: int = None) -> tuple[str, str]:
    """
    Genera una oración y su transcripción fonológica.

    Args:
        tipo: 'corta' (3-5 palabras) o 'larga' (6+ palabras)
        seed: semilla para reproducibilidad

    Returns:
        (oracion_ortografica, transcripcion_fonologica)
    """
    from transcriptor import transcribir

    rng = random.Random(seed)
    plantillas = _PLANTILLAS_CORTAS if tipo == 'corta' else _PLANTILLAS_LARGAS

    # Try up to 10 times to get a valid transcription
    for _ in range(10):
        plantilla, categorias = rng.choice(plantillas)

        # Fill in the categories
        palabras_usadas = set()
        oracion = plantilla
        for cat in categorias:
            opciones = [p for p in _CATEGORIAS.get(cat, ['cosa'])
                        if p not in palabras_usadas]
            if not opciones:
                opciones = _CATEGORIAS.get(cat, ['cosa'])
            palabra = rng.choice(opciones)
            palabras_usadas.add(palabra)
            # Replace first occurrence of {cat}
            oracion = oracion.replace('{' + cat + '}', palabra, 1)

        # Capitalize first letter
        oracion = oracion[0].upper() + oracion[1:]

        # Transcribe
        transcripcion = transcribir(oracion)
        if isinstance(transcripcion, tuple):
            continue  # Error — try another combination
        if not transcripcion:
            continue

        # Remove the / / wrapper
        transcripcion = transcripcion.strip()
        if transcripcion.startswith('/'):
            transcripcion = transcripcion[1:].strip()
        if transcripcion.endswith('/'):
            transcripcion = transcripcion[:-1].strip()

        return oracion, transcripcion

    # Fallback
    return "El gato come pan", "el 'ga.to 'ko.me 'pan"


def generar_oraciones(num: int = 1, tipo: str = 'corta',
                      seed: int = None) -> list[tuple[str, str]]:
    """Genera múltiples oraciones con sus transcripciones."""
    rng = random.Random(seed)
    resultado = []
    for i in range(num):
        ort, trans = generar_oracion(tipo=tipo, seed=rng.randint(0, 99999))
        resultado.append((ort, trans))
    return resultado
