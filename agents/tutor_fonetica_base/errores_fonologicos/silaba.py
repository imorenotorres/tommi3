"""
Parser de sílabas del español.

Descompone una transcripción fonológica en sílabas y cada sílaba en
sus componentes: ataque, núcleo y coda.
"""

from .inventario import es_vocal, es_semivocal, es_consonante

# Grupos consonánticos válidos en ataque del español
ATAQUES_COMPLEJOS = {
    'pl', 'bl', 'fl', 'kl', 'gl',
    'pɾ', 'bɾ', 'fɾ', 'kɾ', 'gɾ', 'tɾ', 'dɾ',
}


class Silaba:
    """Representa una sílaba con sus componentes."""

    def __init__(self, ataque: list[str], nucleo: list[str], coda: list[str],
                 tonica: bool = False):
        self.ataque = ataque      # consonantes antes del núcleo
        self.nucleo = nucleo      # vocal(es) del núcleo (incluye semivocales de diptongos)
        self.coda = coda          # consonantes después del núcleo
        self.tonica = tonica

    @property
    def fonemas(self) -> list[str]:
        return self.ataque + self.nucleo + self.coda

    @property
    def tiene_ataque(self) -> bool:
        return len(self.ataque) > 0

    @property
    def tiene_coda(self) -> bool:
        return len(self.coda) > 0

    @property
    def ataque_complejo(self) -> bool:
        return len(self.ataque) >= 2

    @property
    def tiene_diptongo(self) -> bool:
        return len(self.nucleo) >= 2

    def __repr__(self):
        partes = []
        if self.ataque:
            partes.append(''.join(self.ataque))
        partes.append(''.join(self.nucleo))
        if self.coda:
            partes.append(''.join(self.coda))
        marca = "'" if self.tonica else ""
        return f"{marca}{''.join(partes)}"

    def __str__(self):
        return repr(self)


class Palabra:
    """Representa una palabra como secuencia de sílabas."""

    def __init__(self, silabas: list[Silaba]):
        self.silabas = silabas

    @property
    def fonemas(self) -> list[str]:
        resultado = []
        for s in self.silabas:
            resultado.extend(s.fonemas)
        return resultado

    @property
    def num_silabas(self) -> int:
        return len(self.silabas)

    @property
    def silaba_tonica(self) -> int:
        """Índice de la sílaba tónica (0-based). -1 si no hay."""
        for i, s in enumerate(self.silabas):
            if s.tonica:
                return i
        return -1

    @property
    def silabas_atonas(self) -> list[int]:
        """Índices de las sílabas átonas."""
        return [i for i, s in enumerate(self.silabas) if not s.tonica]

    def __repr__(self):
        return '.'.join(str(s) for s in self.silabas)

    def __str__(self):
        return repr(self)


def _es_nucleo(fonema: str) -> bool:
    """Un fonema puede ser núcleo si es vocal o semivocal."""
    return es_vocal(fonema) or es_semivocal(fonema)


def parsear_silabas(transcripcion: str) -> Palabra:
    """
    Parsea una transcripción fonológica en sílabas.

    Formato de entrada: sílabas separadas por '.', tónica marcada con "ˈ" antes.
    Ejemplo: "ˈka.sa"  →  [Silaba(k,a,tonica), Silaba(s,a)]
             "ma.ɾi.ˈpo.sa" → 4 sílabas, tónica en 'po'

    También acepta notación con barra: /'ka.sa/
    """
    # Limpiar barras
    transcripcion = transcripcion.strip().strip('/')

    silabas = []
    partes = transcripcion.split('.')

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        tonica = False
        if parte.startswith("'") or parte.startswith("ˈ"):
            tonica = True
            parte = parte[1:]

        # Tokenizar fonemas (manejar dígrafos como 'tʃ')
        fonemas = _tokenizar(parte)

        # Separar en ataque, núcleo, coda
        ataque = []
        nucleo = []
        coda = []

        i = 0
        # Ataque: consonantes iniciales
        while i < len(fonemas) and not _es_nucleo(fonemas[i]):
            ataque.append(fonemas[i])
            i += 1

        # Núcleo: vocales y semivocales contiguas
        while i < len(fonemas) and _es_nucleo(fonemas[i]):
            nucleo.append(fonemas[i])
            i += 1

        # Coda: consonantes restantes
        while i < len(fonemas):
            coda.append(fonemas[i])
            i += 1

        if nucleo:  # Solo crear sílaba si tiene núcleo
            silabas.append(Silaba(ataque, nucleo, coda, tonica))

    return Palabra(silabas)


def _tokenizar(texto: str) -> list[str]:
    """Tokeniza una cadena de fonemas, reconociendo dígrafos como 'tʃ'."""
    digrafos = {'tʃ'}
    fonemas = []
    i = 0
    while i < len(texto):
        # Intentar dígrafo
        if i + 1 < len(texto) and texto[i:i+2] in digrafos:
            fonemas.append(texto[i:i+2])
            i += 2
        else:
            fonemas.append(texto[i])
            i += 1
    return fonemas


def reconstruir_transcripcion(palabra: Palabra) -> str:
    """Reconstruye la transcripción fonológica a partir de una Palabra."""
    partes = []
    for s in palabra.silabas:
        marca = "'" if s.tonica else ""
        partes.append(f"{marca}{''.join(s.fonemas)}")
    return '.'.join(partes)
