"""Topics for practice: the parts of a course document a student can choose to practise.

A topic is found in the document itself, never written by a model, and nothing here knows a
subject. In this order:

- numbered section headings ("3 Keypoint localisation", "2. Elementos del contrato"): a line that
  starts with a whole number one higher than the previous heading's, has mostly letters in its
  title and does not end like a sentence. A subsection ("3.1 ...") is no such line and stays
  inside its section;
- Markdown headings ("# ..." or "## ..."), for .md and .txt files;
- when neither gives at least two topics: ranges of PAGES_PER_TOPIC pages, or, in a file
  without pages, runs of CHUNKS_PER_TOPIC chunks.

A topic is the list of chunks it covers. A chunk in which a heading starts belongs to the topic
before it too, unless the heading opens the chunk: so no passage of a section is left out of it.
The id of a topic is worked out from its document and what was found, so it stays the same when
it is found again, and so does what the instructor set for it (practice_settings).
"""

import hashlib
import re

from UltiR.ai_quiz import documents, storage

PAGES_PER_TOPIC = 3
CHUNKS_PER_TOPIC = 4
MAX_HEADING_CHARS = 80
MIN_TOPICS = 2

_NUMBERED = re.compile(r"(\d{1,2})\.?\s+(\S.*)")
_MARKDOWN = re.compile(r"(#{1,2})\s+(\S.*?)\s*#*")


def _letters(text: str) -> str:
    return "".join(char.lower() for char in text if char.isalnum())


def _title_like(title: str) -> bool:
    """Whether the rest of a numbered line reads as the title of a section and not as a formula,
    a row of a table or an item of a numbered list."""
    if not 3 <= len(title) <= MAX_HEADING_CHARS or not title[0].isalpha():
        return False
    if title[-1] in ".,;:=+-−(" or "=" in title:
        return False
    visible = [char for char in title if not char.isspace()]
    return sum(char.isalpha() for char in visible) >= 0.8 * len(visible)


def numbered_headings(pages: list[dict]) -> list[dict]:
    """The top-level numbered headings of a document, in order: [{"number", "title", "page"}]."""
    found, expected = [], 1
    for page in pages:
        for line in (page.get("text") or "").split("\n"):
            line = line.strip()
            match = _NUMBERED.fullmatch(line)
            if not match or int(match.group(1)) != expected or not _title_like(match.group(2)):
                continue
            found.append({"number": expected, "title": match.group(2), "page": page.get("page")})
            expected += 1
    return found


def markdown_headings(pages: list[dict]) -> list[dict]:
    """The Markdown headings of the shallowest level that occurs more than once."""
    lines = [(line.strip(), page.get("page")) for page in pages for line in (page.get("text") or "").split("\n")]
    matches = [(m, page) for line, page in lines if (m := _MARKDOWN.fullmatch(line))]
    for level in ("#", "##"):
        chosen = [{"number": None, "title": m.group(2), "page": page} for m, page in matches if m.group(1) == level]
        if len(chosen) >= MIN_TOPICS:
            return chosen
    return []


def _id(doc_id: str, kind: str, key: str) -> str:
    digest = hashlib.sha256(f"{doc_id}\x00{kind}\x00{key}".encode("utf-8")).hexdigest()[:16]
    return f"t_{digest}"


def _by_headings(document: dict, headings: list[dict], chunks: list[dict]) -> list[dict]:
    """Topics that start where their heading is found in the chunks. A heading that is not found is no topic."""
    flat = [_letters(chunk["text"]) for chunk in chunks]
    starts, at = [], 0
    for heading in headings:
        needle = _letters(f"{heading['number'] or ''} {heading['title']}")
        place = next(((i, flat[i].find(needle)) for i in range(at, len(chunks)) if needle in flat[i]), None)
        if place is None:
            continue
        starts.append((heading, place[0], place[1] == 0))
        at = place[0]
    topics = []
    for number, (heading, first, opens) in enumerate(starts):
        nxt = starts[number + 1] if number + 1 < len(starts) else None
        last = len(chunks) - 1 if nxt is None else (nxt[1] if not nxt[2] else nxt[1] - 1)
        covered = chunks[first: max(first, last) + 1]
        key = f"{heading['number'] or ''} {heading['title']}"
        topics.append(_topic(document, _id(document["doc_id"], "heading", key), heading["title"], "heading", covered))
    return topics


def _by_pages(document: dict, chunks: list[dict]) -> list[dict]:
    paged = [chunk for chunk in chunks if chunk.get("page")]
    if paged:
        groups: dict[int, list[dict]] = {}
        for chunk in paged:
            groups.setdefault((chunk["page"] - 1) // PAGES_PER_TOPIC, []).append(chunk)
        return [_topic(document, _id(document["doc_id"], "pages", str(group)), None, "pages", members)
                for group, members in sorted(groups.items())]
    return [_topic(document, _id(document["doc_id"], "chunks", str(start)), None, "chunks",
                   chunks[start: start + CHUNKS_PER_TOPIC]) for start in range(0, len(chunks), CHUNKS_PER_TOPIC)]


def _topic(document: dict, topic_id: str, title, kind: str, chunks: list[dict]) -> dict:
    pages = sorted({chunk["page"] for chunk in chunks if chunk.get("page")})
    return {"topic_id": topic_id, "doc_id": document["doc_id"], "doc_label": document["label"], "title": title,
            "kind": kind, "pages": [pages[0], pages[-1]] if pages else None,
            "chunk_ids": [chunk["chunk_id"] for chunk in chunks]}


def document_topics(course_id: str, document: dict) -> list[dict]:
    """The topics of one document of the course that is ready, in reading order."""
    chunks = documents.load_chunks(course_id, document["doc_id"])
    if not chunks:
        return []
    pages = storage.read_json(storage.course_dir(course_id) / "docs" / document["doc_id"] / "pages.json", default=[])
    for headings in (numbered_headings(pages), markdown_headings(pages)):
        if len(headings) >= MIN_TOPICS:
            topics = _by_headings(document, headings, chunks)
            if len(topics) >= MIN_TOPICS:
                return topics
    return _by_pages(document, chunks)


def course_topics(course_id: str) -> list[dict]:
    """The topics of every ready document of the course, oldest document first."""
    ready = [d for d in reversed(documents.list_documents(course_id)) if d["status"] == "ready"]
    return [topic for document in ready for topic in document_topics(course_id, document)]


def topic_chunks(course_id: str, topic: dict) -> list[dict]:
    """The chunk records of a topic, with the document's id, label and reading mode, as generation takes them."""
    document = documents.get_document(course_id, topic["doc_id"])
    if document is None:
        return []
    wanted = set(topic["chunk_ids"])
    return [{"doc_id": document["doc_id"], "doc_label": document["label"], "mode": document["mode"], **chunk}
            for chunk in documents.load_chunks(course_id, topic["doc_id"]) if chunk["chunk_id"] in wanted]
