"""
Quirón — Research assistant for a Master's thesis on Psychoanalysis and Neuroscience.

Vectorless RAG agent with programmatic interception of identity and source queries.
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, SimpleRAGMixin, SimpleVectorlessMixin


def _evaluar_fidelidad(client, model, contexto, pregunta, respuesta):
    """Evalúa con un LLM-juez cuánto se basa la respuesta en el contexto."""
    prompt_juez = (
        "Eres un evaluador de calidad de respuestas en un sistema RAG académico. "
        "Se te proporcionan: el CONTEXTO recuperado de los artículos, la PREGUNTA del usuario, "
        "y la RESPUESTA generada por la IA.\n\n"
        "Evalúa del 1 al 5 cuánto se basa la RESPUESTA en el CONTEXTO:\n"
        "- 5: Toda la información está en el contexto\n"
        "- 4: La mayor parte está en el contexto, con alguna inferencia razonable\n"
        "- 3: Mezcla información del contexto con extrapolaciones significativas\n"
        "- 2: La mayor parte es extrapolación, aunque usa terminología correcta\n"
        "- 1: La respuesta no tiene relación con el contexto\n\n"
        "CASO ESPECIAL: Si la respuesta rechaza correctamente una pregunta fuera de tema, puntúa con 5.\n\n"
        "Responde SOLO con este formato exacto:\n"
        "PUNTUACION: N\n"
        "JUSTIFICACION: una frase breve"
    )
    messages = [
        {"role": "system", "content": prompt_juez},
        {"role": "user", "content": (
            f"CONTEXTO:\n{contexto[:2000]}\n\n"
            f"PREGUNTA: {pregunta}\n\n"
            f"RESPUESTA:\n{respuesta[:1500]}"
        )}
    ]
    try:
        result = client.chat.complete(model=model, messages=messages)
        text = result.choices[0].message.content.strip()
        puntuacion = 3
        justificacion = ""
        for line in text.split('\n'):
            if line.startswith('PUNTUACION:'):
                try:
                    puntuacion = int(line.split(':')[1].strip()[0])
                except (ValueError, IndexError):
                    pass
            elif line.startswith('JUSTIFICACION:'):
                justificacion = line.split(':', 1)[1].strip()
        return {'puntuacion': puntuacion, 'justificacion': justificacion}
    except Exception:
        return {'puntuacion': 3, 'justificacion': 'No se pudo evaluar'}


def _load_known_sources():
    """Load known author names and title keywords from the PDF filenames."""
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(agent_dir, "data", "docs")
    sources = set()
    if os.path.exists(docs_dir):
        for f in os.listdir(docs_dir):
            if not f.lower().endswith('.pdf'):
                continue
            name = f.replace('.pdf', '').replace('.PDF', '').replace('_', ' ')
            # Extract likely author surnames (capitalized words)
            for word in re.findall(r'[A-Z][a-záéíóúñ]{2,}', name):
                sources.add(word.lower())
            # Also add multi-word title fragments
            for fragment in re.findall(r'[A-Za-záéíóúñ]{4,}', name):
                sources.add(fragment.lower())
    return sources

_KNOWN_SOURCES = None

def _get_known_sources():
    global _KNOWN_SOURCES
    if _KNOWN_SOURCES is None:
        _KNOWN_SOURCES = _load_known_sources()
    return _KNOWN_SOURCES


def _extract_citations(text):
    """Extract cited names/titles from a paragraph."""
    citations = []
    # (Author, Year) or (Author et al., Year)
    for m in re.finditer(r'\(([A-Z][a-záéíóúñA-Z\s\.\-&,]+?)(?:,\s*\d{4})?\)', text):
        citations.append(m.group(1).strip())
    # "Title" or «Title» — only if it looks like an article title (contains capital words)
    for m in re.finditer(r'[""«]([A-Z][^""»]{10,})[""»]', text):
        title = m.group(1).strip()
        # Skip short quoted expressions that aren't titles
        cap_words = len(re.findall(r'[A-Z][a-z]{2,}', title))
        if cap_words >= 2:  # At least 2 capitalized words = likely a title
            citations.append(title)
    # según/como señala Author
    for m in re.finditer(r'(?:según|como señala|de acuerdo con)\s+([A-Z][a-záéíóúñ]+(?:\s+(?:y|and|&)\s+[A-Z][a-záéíóúñ]+)?)', text):
        citations.append(m.group(1).strip())
    # Filename-style references: (whatisneuropsychoanalysispankseppSolms2012) or similar
    for m in re.finditer(r'\(([a-zA-Z_\-\s]{10,})\)', text):
        citations.append(m.group(1).strip())
    # Title-style references in parentheses: (An Attachment Model of Depression)
    for m in re.finditer(r'\(([A-Z][a-z]+ [A-Z][^)]{10,})\)', text):
        if m.group(1) not in citations:
            citations.append(m.group(1).strip())
    # Standalone title references after a dash or colon
    for m in re.finditer(r'(?:—|:)\s*([A-Z][^.]{15,}(?:TFM|Psycho|Neuro|Emotion|Attachment|Memory|Depression|Ethics|Empathy)[^.]*)', text):
        if m.group(1).strip() not in citations:
            citations.append(m.group(1).strip())
    return citations


def _verify_citation(citation, known_sources):
    """Check if a citation matches a known source. Returns True if verified."""
    citation_lower = citation.lower()
    # Check if any significant word from the citation matches known sources
    words = re.findall(r'[a-záéíóúñ]{3,}', citation_lower)
    matches = sum(1 for w in words if w in known_sources)
    # At least one significant word should match
    return matches >= 1


def _annotate_citations(response):
    """Annotate logical blocks with citation indicators.

    Groups lines into blocks (separated by headers or numbered items).
    Each block gets ONE indicator based on whether it contains verified citations.

    - 🟢 Block contains at least one verified citation
    - 🔴 Block contains citations that don't match any known source
    - ⚠️ Block has no citations at all
    """
    known = _get_known_sources()

    _CITATION_PATTERNS = [
        # Author references
        r'\([A-Z][a-záéíóúñ]+\s*,\s*\d{4}',      # (Author, 2024)
        r'\([A-Z][a-záéíóúñ]+ et al',              # (Author et al
        r'\([A-Z][a-záéíóúñ]+ &',                  # (Author &
        r'\([A-Z][a-záéíóúñ]+,\s*[A-Z]',           # (Author, Title...
        r'según [A-Z][a-záéíóúñ]',                  # según Author
        r'como señala [A-Z]',                        # como señala Author
        r'de acuerdo con [A-Z]',                     # de acuerdo con Author
        # Filename-style references in parentheses
        r'\([a-zA-Z_\-]{15,}\)',                    # (whatisneuropsychoanalysis...)
        # Title references in parentheses (must contain multiple capitalized words)
        r'\([A-Z][a-z]+ [A-Z][a-z]+ [A-Z]',        # (An Attachment Model...
        # ALL-CAPS title references
        r'[A-Z]{3,}\s+[A-Z]{3,}\s+[A-Z]{3,}',     # EMOTION REGULATION RELATIONSHIP
    ]

    def _is_block_start(line):
        """Detect if a line starts a new logical block."""
        s = line.strip()
        if not s:
            return False
        # Numbered items: "1.", "2.", etc.
        if re.match(r'^\d+\.?\s', s):
            return True
        # Headers
        if s.startswith('#'):
            return True
        # Bold headers: "**Title**" or "- **Title**"
        if re.match(r'^-?\s*\*\*', s):
            return True
        # Emoji headers
        if re.match(r'^[🟢🔴🟡📌🔬🧠]\s', s):
            return True
        # Lettered items: "A.", "B.", etc.
        if re.match(r'^[A-Z]\.?\s', s):
            return True
        # Indented list items with bold (sub-sections)
        if re.match(r'^\s{2,}-?\s*\*\*', s):
            return True
        return False

    def _is_skippable(line):
        """Lines that should not be annotated."""
        s = line.strip()
        return (not s or
                s.startswith('#') or
                s.startswith('---') or
                s.startswith('|') or
                len(s) < 40 or
                s.startswith('Fuentes citadas') or
                s.startswith('📌') or
                (s.startswith('*') and s.endswith('*') and len(s) < 100))

    # Split response into blocks
    lines = response.split('\n')
    blocks = []  # list of (start_idx, end_idx)
    current_start = None

    for i, line in enumerate(lines):
        if _is_block_start(line):
            if current_start is not None:
                blocks.append((current_start, i))
            current_start = i
        elif not line.strip() and current_start is not None:
            # Empty line might end a block, but only if next line starts a new one
            pass

    if current_start is not None:
        blocks.append((current_start, len(lines)))

    # If no blocks detected, treat entire response as one block
    if not blocks:
        blocks = [(0, len(lines))]

    # Two-pass annotation:
    # Pass 1: Mark individual lines that have citations (verify each)
    # Pass 2: For blocks without any citation, mark the block once

    annotated = list(lines)

    # Skip patterns for conversational/meta content
    _SKIP_CONTENT = [
        'soy quirón', 'asistente de investigación', 'moreno-torres',
        'sant pau', 'centauro', 'sanador herido', 'mi nombre viene',
        'mi base de conocimiento', '40 artículos', 'puedo ayudar',
        'si quieres profundizar', 'puedo ayudarte a explorar',
        'si necesitas', 'dime y te ayudo', 'no dudes en preguntar',
        '¿te gustaría', 'puedo buscar', 'quieres que', 'en qué más',
        'algo más', 'espero que', 'ánimo con', 'para tu tfm',
        'en tu trabajo', 'para la discusión', 'fuentes clave',
        'fuentes citadas', '¿cómo integrar',
    ]

    # Pass 1: Check every line for citations
    lines_with_citations = set()  # indices of lines that have citations
    block_has_citation = {}  # block_index -> bool

    for i, line in enumerate(lines):
        stripped = line.strip()
        if _is_skippable(stripped):
            continue
        if any(p in stripped.lower() for p in _SKIP_CONTENT):
            continue

        has_citation = any(re.search(p, stripped) for p in _CITATION_PATTERNS)
        if has_citation:
            lines_with_citations.add(i)
            citations = _extract_citations(stripped)
            if citations:
                verified = [c for c in citations if _verify_citation(c, known)]
                unverified = [c for c in citations if not _verify_citation(c, known)]

                if verified and not unverified:
                    annotated[i] += ' <span style="color:#16a34a;font-size:11px;" title="Cita verificada: coincide con artículos del TFM">🟢</span>'
                elif unverified and not verified:
                    annotated[i] += ' <span style="color:#dc2626;font-size:11px;" title="Cita no encontrada en los artículos del TFM. Posible alucinación: ' + ', '.join(unverified[:2]) + '">🔴 cita no verificada</span>'
                elif verified and unverified:
                    annotated[i] += ' <span style="color:#f59e0b;font-size:11px;" title="Algunas citas no verificadas: ' + ', '.join(unverified[:2]) + '">🟡</span>'

    # Pass 2: For blocks without any cited line, mark the block
    for start, end in blocks:
        block_text = '\n'.join(lines[start:end])
        block_lower = block_text.lower()

        # Skip meta/conversational blocks
        if any(p in block_lower for p in _SKIP_CONTENT):
            continue

        # Skip short blocks
        substantial = ''.join(l.strip() for l in lines[start:end] if not _is_skippable(l))
        if len(substantial) < 80:
            continue

        # Check if any line in the block already has a citation
        block_has_any_citation = any(i in lines_with_citations for i in range(start, end))
        if block_has_any_citation:
            continue  # Already annotated per-line

        # No citations in block — mark at the end
        last_substantial = end - 1
        while last_substantial > start and _is_skippable(lines[last_substantial]):
            last_substantial -= 1
        if last_substantial >= start:
            annotated[last_substantial] += ' <span style="color:#94a3b8;font-size:11px;" title="Este bloque no cita fuentes específicas">⚠️ sin cita</span>'

    return '\n'.join(annotated)


_IDENTITY_RESPONSE = """¡Hola Blanca! Soy **Quirón**, tu asistente de investigación personal para ayudarte a completar tu Trabajo Fin de Máster. Puedes llamarme Quirón. Espero que nos llevemos bien 😊

Mi nombre viene de **Quirón**, el centauro sabio de la mitología griega, conocido como el *sanador herido*: transformó su propio sufrimiento en conocimiento y compasión para curar y enseñar a otros. Carl Gustav Jung recuperó este arquetipo para la psicoterapia moderna — algo muy relevante para tu TFM.

Tengo acceso a unos **40 artículos científicos** sobre neuropsicoanálisis, regulación emocional, apego, empatía en psicoterapia y los debates sobre la validez de este enfoque. Puedo ayudarte a:

- **Explorar los textos**: buscar qué dicen los artículos sobre un tema concreto
- **Comparar autores**: contrastar las posturas de diferentes investigadores
- **Preparar la discusión**: encontrar argumentos a favor y en contra para tu TFM
- **Listar las fuentes**: pregúntame "¿Cuáles son tus fuentes?" para ver todos los artículos

**Sobre la fiabilidad**: mis respuestas se basan en estos artículos, y siempre indico las fuentes. Pero debo ser honesto: utilizo una IA (un modelo de lenguaje) para procesar los textos, y a veces puede cometer errores o ir más allá de lo que dicen los artículos. Por eso verás indicadores de fiabilidad en cada respuesta:

- 🟢 **Verde**: información verificada programáticamente (como esta presentación o la lista de fuentes)
- 🟡 **Amarillo**: respuesta generada por la IA a partir de los artículos — probablemente correcta, pero contrasta con las fuentes originales
- 🔴 **Rojo**: el sistema ha detectado que la respuesta podría ir más allá de los artículos — no la uses sin verificarla

Si algo no te cuadra, consulta siempre el artículo original."""


def _is_identity_query(msg):
    msg_lower = msg.lower().strip().rstrip('?').strip()
    patterns = [
        r'quién eres', r'quien eres', r'qué eres', r'que eres',
        r'para qué.*creado', r'para que.*creado', r'para qué sirves', r'para que sirves',
        r'cuál es tu propósito', r'cual es tu proposito',
        r'preséntate', r'presentate', r'háblame de ti', r'hablame de ti',
        r'qué puedes hacer', r'que puedes hacer',
    ]
    return any(re.search(p, msg_lower) for p in patterns)


def _is_sources_query(msg):
    msg_lower = msg.lower().strip().rstrip('?').strip()
    patterns = [
        r'cuáles son tus fuentes', r'cuales son tus fuentes',
        r'qué fuentes', r'que fuentes', r'tus fuentes',
        r'qué artículos', r'que artículos', r'qué documentos', r'que documentos',
        r'lista.*fuentes', r'lista.*artículos', r'muestra.*fuentes',
        r'de dónde sacas', r'de donde sacas',
    ]
    return any(re.search(p, msg_lower) for p in patterns)


def _build_sources_response():
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    meta_path = os.path.join(agent_dir, "data", "papers_metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            papers = json.load(f)
    else:
        docs_dir = os.path.join(agent_dir, "data", "docs")
        papers = [{"title": f.replace(".pdf", "").replace("_", " ")}
                  for f in sorted(os.listdir(docs_dir)) if f.lower().endswith(".pdf")]

    response = f"**Mis fuentes** ({len(papers)} artículos):\n\n"
    for i, p in enumerate(papers, 1):
        title = p.get("title", "Sin título")
        authors = p.get("authors", "")
        year = p.get("year", "")
        extra = ""
        if authors:
            extra += f" — {authors}"
        if year:
            extra += f" ({year})"
        response += f"{i}. {title}{extra}\n"

    response += "\n*Estos son los artículos que Blanca ha seleccionado para su TFM. Mis respuestas se basan exclusivamente en ellos.*"
    return response


class Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        if _is_identity_query(user_message):
            return _IDENTITY_RESPONSE
        if _is_sources_query(user_message):
            return _build_sources_response()
        return super().chat(user_message, history, **kwargs)

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        if _is_identity_query(user_message):
            yield ("procedural_banner",
                   '<div style="background-color:#d4edda;border-left:4px solid #28a745;'
                   'padding:8px 12px;border-radius:6px;font-size:13px;margin-bottom:8px;">'
                   '\U0001F7E2 <strong>Información verificada</strong></div>\n\n')
            yield _IDENTITY_RESPONSE
            return
        if _is_sources_query(user_message):
            yield ("procedural_banner",
                   '<div style="background-color:#d4edda;border-left:4px solid #28a745;'
                   'padding:8px 12px;border-radius:6px;font-size:13px;margin-bottom:8px;">'
                   '\U0001F7E2 <strong>Información verificada</strong> — Lista de artículos del TFM</div>\n\n')
            yield _build_sources_response()
            return
        # Stream the RAG response and collect it for citation checking
        full_response = ""
        async for item in super().chat_stream(user_message, history, **kwargs):
            if isinstance(item, str):
                full_response += item
            yield item

        # Post-process: check citations per paragraph and replace response with annotated version
        if full_response and len(full_response) > 100:
            annotated = _annotate_citations(full_response)
            if annotated != full_response:
                yield ("replace", annotated)
