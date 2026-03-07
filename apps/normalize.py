"""
Módulo de normalización compartido para agentes tommi2b.
Proporciona funciones para normalizar países, idiomas y otros términos.
"""

import re

# Mapeo de sinónimos de idiomas al nombre oficial en la BD (MAYÚSCULAS)
LANGUAGE_SYNONYMS = {
    # Inglés
    "inglés": "INGLÉS",
    "ingles": "INGLÉS",
    "english": "INGLÉS",
    "anglais": "INGLÉS",
    "inglesa": "INGLÉS",

    # Español
    "español": "ESPAÑOL",
    "espanol": "ESPAÑOL",
    "spanish": "ESPAÑOL",
    "castellano": "ESPAÑOL",

    # Francés
    "francés": "FRANCÉS",
    "frances": "FRANCÉS",
    "french": "FRANCÉS",
    "français": "FRANCÉS",

    # Alemán
    "alemán": "ALEMÁN",
    "aleman": "ALEMÁN",
    "german": "ALEMÁN",
    "deutsch": "ALEMÁN",

    # Italiano
    "italiano": "ITALIANO",
    "italian": "ITALIANO",

    # Portugués
    "portugués": "PORTUGUÉS",
    "portugues": "PORTUGUÉS",
    "portuguese": "PORTUGUÉS",

    # Holandés / Neerlandés
    "holandés": "NEERLANDÉS",
    "holandes": "NEERLANDÉS",
    "neerlandés": "NEERLANDÉS",
    "neerlandes": "NEERLANDÉS",
    "dutch": "NEERLANDÉS",

    # Chino
    "chino": "CHINO",
    "chinese": "CHINO",
    "mandarín": "CHINO",
    "mandarin": "CHINO",

    # Japonés
    "japonés": "JAPONÉS",
    "japones": "JAPONÉS",
    "japanese": "JAPONÉS",

    # Coreano
    "coreano": "COREANO",
    "korean": "COREANO",

    # Ruso
    "ruso": "RUSO",
    "russian": "RUSO",

    # Árabe
    "árabe": "ÁRABE",
    "arabe": "ÁRABE",
    "arabic": "ÁRABE",

    # Polaco
    "polaco": "POLACO",
    "polish": "POLACO",

    # Sueco
    "sueco": "SUECO",
    "swedish": "SUECO",

    # Danés
    "danés": "DANÉS",
    "danes": "DANÉS",
    "danish": "DANÉS",

    # Noruego
    "noruego": "NORUEGO",
    "norwegian": "NORUEGO",

    # Finlandés / Finés
    "finlandés": "FINÉS",
    "finlandes": "FINÉS",
    "finés": "FINÉS",
    "fines": "FINÉS",
    "finnish": "FINÉS",

    # Griego
    "griego": "GRIEGO",
    "greek": "GRIEGO",

    # Turco
    "turco": "TURCO",
    "turkish": "TURCO",

    # Checo
    "checo": "CHECO",
    "czech": "CHECO",

    # Húngaro
    "húngaro": "HÚNGARO",
    "hungaro": "HÚNGARO",
    "hungarian": "HÚNGARO",

    # Rumano
    "rumano": "RUMANO",
    "romanian": "RUMANO",
}

# Mapeo de sinónimos de países al nombre oficial en la BD
COUNTRY_SYNONYMS = {
    # Países Bajos / Holanda
    "holanda": "Países Bajos",
    "holandés": "de Países Bajos",
    "holandes": "de Países Bajos",
    "holandesa": "de Países Bajos",
    "holandeses": "de Países Bajos",
    "holandesas": "de Países Bajos",
    "neerlandés": "de Países Bajos",
    "neerlandes": "de Países Bajos",
    "neerlandesa": "de Países Bajos",
    "neerlandeses": "de Países Bajos",
    "neerlandesas": "de Países Bajos",
    "netherlands": "Países Bajos",
    "holland": "Países Bajos",
    "dutch": "de Países Bajos",
    "the netherlands": "Países Bajos",
    "países bajos": "Países Bajos",
    "paises bajos": "Países Bajos",

    # Reino Unido (no usar inglés/inglesa porque conflicto con idioma)
    "uk": "Reino Unido",
    "united kingdom": "Reino Unido",
    "gran bretaña": "Reino Unido",
    "gran bretana": "Reino Unido",
    "england": "Reino Unido",
    "inglaterra": "Reino Unido",
    "britain": "Reino Unido",
    "reino unido": "Reino Unido",
    "británico": "del Reino Unido",
    "britanico": "del Reino Unido",
    "británica": "del Reino Unido",
    "britanica": "del Reino Unido",
    "británicos": "del Reino Unido",
    "britanicos": "del Reino Unido",
    "británicas": "del Reino Unido",
    "britanicas": "del Reino Unido",

    # Estados Unidos
    "usa": "Estados Unidos",
    "eeuu": "Estados Unidos",
    "united states": "Estados Unidos",
    "us": "Estados Unidos",
    "america": "Estados Unidos",
    "estados unidos": "Estados Unidos",

    # Alemania (no incluir "alemán" porque conflicto con idioma)
    "germany": "Alemania",
    "deutschland": "Alemania",
    "alemania": "Alemania",
    "alemana": "de Alemania",
    "alemanes": "de Alemania",
    "alemanas": "de Alemania",
    "germano": "de Alemania",
    "germana": "de Alemania",
    "germanos": "de Alemania",
    "germanas": "de Alemania",

    # Francia (no incluir "francés" porque conflicto con idioma)
    "france": "Francia",
    "francia": "Francia",
    "francesa": "de Francia",
    "franceses": "de Francia",
    "francesas": "de Francia",
    "galo": "de Francia",
    "gala": "de Francia",
    "galos": "de Francia",
    "galas": "de Francia",

    # Italia (no incluir "italiano" porque conflicto con idioma)
    "italy": "Italia",
    "italia": "Italia",
    "italiana": "de Italia",
    "italianos": "de Italia",
    "italianas": "de Italia",

    # España (no incluir "español" porque conflicto con idioma)
    "spain": "España",
    "espana": "España",
    "españa": "España",
    "española": "de España",
    "espanola": "de España",
    "españoles": "de España",
    "espanoles": "de España",
    "españolas": "de España",
    "espanolas": "de España",

    # Portugal (no incluir "portugués" porque conflicto con idioma)
    "portugal": "Portugal",
    "portuguesa": "de Portugal",
    "portugueses": "de Portugal",
    "portuguesas": "de Portugal",
    "luso": "de Portugal",
    "lusa": "de Portugal",
    "lusos": "de Portugal",
    "lusas": "de Portugal",

    # Bélgica
    "belgium": "Bélgica",
    "belgica": "Bélgica",
    "bélgica": "Bélgica",

    # Suiza
    "switzerland": "Suiza",
    "suiza": "Suiza",

    # Austria
    "austria": "Austria",

    # Polonia
    "poland": "Polonia",
    "polska": "Polonia",
    "polonia": "Polonia",

    # República Checa
    "czech republic": "República Checa",
    "czechia": "República Checa",
    "chequia": "República Checa",
    "republica checa": "República Checa",

    # Grecia
    "greece": "Grecia",
    "grecia": "Grecia",

    # Irlanda
    "ireland": "Irlanda",
    "irlanda": "Irlanda",

    # Dinamarca
    "denmark": "Dinamarca",
    "dinamarca": "Dinamarca",

    # Suecia
    "sweden": "Suecia",
    "suecia": "Suecia",

    # Noruega
    "norway": "Noruega",
    "noruega": "Noruega",

    # Finlandia
    "finland": "Finlandia",
    "finlandia": "Finlandia",

    # Japón
    "japan": "Japón",
    "japon": "Japón",
    "nippon": "Japón",

    # China
    "china": "China",

    # Corea del Sur
    "south korea": "Corea del Sur",
    "korea": "Corea del Sur",
    "corea": "Corea del Sur",
    "corea del sur": "Corea del Sur",

    # Brasil
    "brazil": "Brasil",
    "brasil": "Brasil",

    # México
    "mexico": "México",
    "méxico": "México",

    # Argentina
    "argentina": "Argentina",

    # Chile
    "chile": "Chile",

    # Colombia
    "colombia": "Colombia",

    # Perú
    "peru": "Perú",
    "perú": "Perú",

    # Canadá
    "canada": "Canadá",
    "canadá": "Canadá",

    # Australia
    "australia": "Australia",

    # Nueva Zelanda
    "new zealand": "Nueva Zelanda",
    "nueva zelanda": "Nueva Zelanda",

    # Rumanía
    "romania": "Rumanía",
    "rumania": "Rumanía",
    "rumanía": "Rumanía",

    # Hungría
    "hungary": "Hungría",
    "hungria": "Hungría",
    "hungría": "Hungría",

    # Turquía
    "turkey": "Turquía",
    "turquia": "Turquía",
    "turquía": "Turquía",
}


def normalize_country(text: str) -> str:
    """
    Normaliza el nombre de un país a su forma oficial en la BD.

    Args:
        text: Nombre del país (puede ser sinónimo o variante)

    Returns:
        Nombre oficial del país si se encuentra, o el texto original

    Ejemplo:
        >>> normalize_country("Holanda")
        'Países Bajos'
        >>> normalize_country("UK")
        'Reino Unido'
    """
    if not text:
        return text

    key = text.lower().strip()
    return COUNTRY_SYNONYMS.get(key, text)


def normalize_language(text: str) -> str:
    """
    Normaliza el nombre de un idioma a su forma oficial en la BD (MAYÚSCULAS).

    Args:
        text: Nombre del idioma (puede ser sinónimo o variante)

    Returns:
        Nombre oficial del idioma si se encuentra, o el texto original

    Ejemplo:
        >>> normalize_language("inglés")
        'INGLÉS'
        >>> normalize_language("english")
        'INGLÉS'
    """
    if not text:
        return text

    key = text.lower().strip()
    return LANGUAGE_SYNONYMS.get(key, text)


def normalize_text_for_search(text: str) -> str:
    """
    Normaliza un texto para búsqueda, normalizando idiomas y países.
    Procesa PRIMERO idiomas y LUEGO países para evitar conflictos
    (ej: "francés" como idioma vs "francesas" como adjetivo de país).

    Args:
        text: Texto a normalizar

    Returns:
        Texto con idiomas y países normalizados
    """
    if not text:
        return text

    result = text

    # PRIMERO: Buscar y reemplazar sinónimos de idiomas (ordenados por longitud descendente)
    # Así "nivel de francés" → "FRANCÉS" antes de procesar países
    sorted_languages = sorted(LANGUAGE_SYNONYMS.keys(), key=len, reverse=True)
    for synonym in sorted_languages:
        pattern = re.compile(r'\b' + re.escape(synonym) + r'\b', re.IGNORECASE)
        if pattern.search(result):
            result = pattern.sub(LANGUAGE_SYNONYMS[synonym], result)

    # DESPUÉS: Buscar y reemplazar sinónimos de países (ordenados por longitud descendente)
    # Así "universidades francesas" → "de Francia" (porque "francesas" no es idioma)
    sorted_countries = sorted(COUNTRY_SYNONYMS.keys(), key=len, reverse=True)
    for synonym in sorted_countries:
        pattern = re.compile(r'\b' + re.escape(synonym) + r'\b', re.IGNORECASE)
        if pattern.search(result):
            result = pattern.sub(COUNTRY_SYNONYMS[synonym], result)

    return result


def get_all_country_names() -> list:
    """
    Devuelve lista de todos los nombres de países conocidos (sinónimos + oficiales).
    Útil para validación o autocompletado.
    """
    all_names = set(COUNTRY_SYNONYMS.keys())
    all_names.update(COUNTRY_SYNONYMS.values())
    return sorted(all_names)


if __name__ == "__main__":
    # Tests de países
    print("=== Tests de normalización de PAÍSES ===")
    country_tests = [
        ("Holanda", "Países Bajos"),
        ("UK", "Reino Unido"),
        ("USA", "Estados Unidos"),
        ("alemania", "Alemania"),
        ("France", "Francia"),
        ("UnKnown Country", "UnKnown Country"),
    ]

    for input_val, expected in country_tests:
        result = normalize_country(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} normalize_country('{input_val}') = '{result}'")

    # Tests de idiomas
    print("\n=== Tests de normalización de IDIOMAS ===")
    language_tests = [
        ("inglés", "INGLÉS"),
        ("ingles", "INGLÉS"),
        ("english", "INGLÉS"),
        ("francés", "FRANCÉS"),
        ("german", "ALEMÁN"),
        ("UnKnown Language", "UnKnown Language"),
    ]

    for input_val, expected in language_tests:
        result = normalize_language(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} normalize_language('{input_val}') = '{result}'")

    # Test completo
    print("\n=== Test normalize_text_for_search ===")
    tests = [
        ("Qué convenios hay con Holanda", "Qué convenios hay con Países Bajos"),
        ("convenios sin requisito de inglés", "convenios sin requisito de INGLÉS"),
        ("Holanda sin inglés", "Países Bajos sin INGLÉS"),
    ]

    for input_text, expected in tests:
        result = normalize_text_for_search(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{input_text}' → '{result}'")
