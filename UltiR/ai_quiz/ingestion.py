"""Ingestion: turn a stored course document into pages and chunks.

This seam knows nothing about quizzes, the LLM or HTTP. A reader produces a
ParsedDocument; `chunk_pages` cuts it into chunks that keep the page they came
from; `select_chunks` picks the chunks for one request.

Page numbers are written here, by the reader, and nowhere else. The model is
never asked for one.

Readers: "text" (pypdf for PDFs, plain decoding for .md/.txt) is the default
and the only one so far. "full" (formulas, figures) arrives with the Docling
reader; the interface below already has its place.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from UltiR.ai_quiz import limits

CHUNK_CHARS = 1200
_MIN_CHUNK_CHARS = 200


@dataclass(frozen=True)
class Page:
    number: int | None      # 1-based; None for files that have no pages (.md, .txt)
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[Page]
    mode: str               # "text" | "full"
    engine: str             # "pypdf" | "plain"
    warnings: list[dict] = field(default_factory=list)


class Unreadable(Exception):
    """The file was accepted but nothing usable could be read from it."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code    # "corrupt" | "no_text" | "too_long"


class ReaderUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ReadingStopped(Exception):
    """The reader gave up because it was told to stop. There is no result."""


class Reader(Protocol):
    name: str
    mode: str

    def read(self, path: Path, stop=None) -> ParsedDocument:
        """`stop` is a threading.Event or None. A reader that can take long looks at it
        and raises ReadingStopped once it is set."""
        ...


# ── Text cleaning ─────────────────────────────────────────────────────────────

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LINE_END_HYPHEN = re.compile(r"(?<=[^\W\d_])-\n(?=[^\W\d_])")


def _clean(text: str) -> str:
    """Repair what extraction breaks, and nothing else.

    No Unicode normalisation: NFKC would turn ² into 2 and ½ into 1/2-like
    digits, which changes what the document says.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for ligature, letters in _LIGATURES.items():
        text = text.replace(ligature, letters)
    text = _CONTROL.sub("", text)
    # "rank-\ning" -> "ranking" only when the next line goes on in lower case
    text = _LINE_END_HYPHEN.sub(lambda m: "" if text[m.end()].islower() else "-\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _strip_running_lines(texts: list[str]) -> list[str]:
    """Drop a header line repeated across pages and bare page numbers at the bottom.

    Only for documents of three or more pages; with fewer there is no telling
    a running header from content.
    """
    if len(texts) < 3:
        return texts
    firsts = Counter(t.split("\n", 1)[0] for t in texts if t)
    header, count = firsts.most_common(1)[0] if firsts else ("", 0)
    result = []
    for t in texts:
        lines = t.split("\n")
        if header and count > len(texts) / 2 and lines and lines[0] == header:
            lines = lines[1:]
        if lines and re.fullmatch(r"\d{1,4}", lines[-1]):
            lines = lines[:-1]
        result.append("\n".join(lines).strip())
    return result


def _letters(text: str) -> int:
    return sum(1 for c in text if c.isalnum())


# ── Readers ───────────────────────────────────────────────────────────────────

class TextReader:
    """Text-only reading. PDFs must be born-digital: a scan has no text layer."""

    name = "text"
    mode = "text"

    def read(self, path: Path, stop=None) -> ParsedDocument:
        if path.suffix.lower() == ".pdf":
            return self._read_pdf(path)
        return self._read_plain(path)

    def _read_pdf(self, path: Path) -> ParsedDocument:
        from pypdf import PdfReader

        try:
            reader = PdfReader(str(path))
            if len(reader.pages) > limits.MAX_PAGES:
                raise Unreadable("too_long")
            texts = [_clean(page.extract_text() or "") for page in reader.pages]
        except Unreadable:
            raise
        except Exception:
            # pypdf raises many different errors for damaged files
            raise Unreadable("corrupt") from None
        texts = _strip_running_lines(texts)
        return self._finish(texts, numbered=True, engine="pypdf")

    def _read_plain(self, path: Path) -> ParsedDocument:
        try:
            text = _clean(path.read_bytes().decode("utf-8-sig"))
        except UnicodeDecodeError:
            raise Unreadable("corrupt") from None
        return self._finish([text], numbered=False, engine="plain")

    def _finish(self, texts: list[str], numbered: bool, engine: str) -> ParsedDocument:
        if sum(len(t) for t in texts) > limits.MAX_TEXT_CHARS:
            raise Unreadable("too_long")
        # A page of real text has hundreds of letters; a scan has none.
        if not texts or _letters("".join(texts)) < max(20, 10 * len(texts)):
            raise Unreadable("no_text")
        pages = [Page(number=i if numbered else None, text=t) for i, t in enumerate(texts, start=1)]
        warnings = []
        empty = [p.number for p in pages if numbered and not p.text]
        if empty:
            warnings.append({"code": "pages_without_text", "pages": empty})
        return ParsedDocument(pages=pages, mode="text", engine=engine, warnings=warnings)


def full_reading_available() -> bool:
    return False


def get_reader(mode: str) -> Reader:
    if mode == "text":
        return TextReader()
    if mode == "full":
        raise ReaderUnavailable("no full-reading engine is installed")
    raise ValueError(f"unknown reading mode: {mode!r}")


# ── Chunks ────────────────────────────────────────────────────────────────────

def _flow(text: str) -> str:
    """One line per paragraph: line breaks inside a paragraph become spaces."""
    paragraphs = re.split(r"\n\s*\n", text)
    return "\n\n".join(" ".join(p.split()) for p in paragraphs if p.strip())


def _split(text: str) -> list[str]:
    """Cut text into pieces of at most CHUNK_CHARS, at a paragraph or sentence end when there is one."""
    pieces, rest = [], text.strip()
    while len(rest) > CHUNK_CHARS:
        window = rest[:CHUNK_CHARS]
        cut = max(window.rfind("\n\n"), -1)
        if cut < CHUNK_CHARS * 0.4:
            ends = [m.end() for m in re.finditer(r"[.!?…](?=\s)", window)]
            cut = ends[-1] if ends and ends[-1] >= CHUNK_CHARS * 0.4 else -1
        if cut < 0:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = CHUNK_CHARS
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        # a short tail joins the piece before it when the two still fit
        if pieces and len(rest) < _MIN_CHUNK_CHARS and len(pieces[-1]) + 1 + len(rest) <= CHUNK_CHARS:
            pieces[-1] = f"{pieces[-1]} {rest}"
        else:
            pieces.append(rest)
    return [p for p in pieces if p]


def chunk_pages(pages: list[Page]) -> list[dict]:
    """Chunks in reading order. A chunk never crosses a page, so its page number is exact."""
    chunks = []
    for page in pages:
        for piece in _split(_flow(page.text)):
            chunks.append({"chunk_id": f"c_{len(chunks) + 1:04d}", "page": page.number, "text": piece})
    return chunks


# ── Choosing chunks ───────────────────────────────────────────────────────────

_WORD = re.compile(r"[^\W_]{3,}")   # letters and digits in any script, three or more
_STOP = frozenset(
    "the and for are was were been being have has had does did will would shall should may might can could "
    "this that these those its with from not nor than too very also about above after before between into "
    "through during over under then once here there when where which who whom what how all each both few more "
    "most other some such only own same just because while however although though even still already yet "
    "since until "
    "los las una uno unos unas del que son fue era ser estar por para con como sus este esta estos estas pero "
    "mas muy todo esto eso esa aquel aquella hay tiene puede sobre entre hasta desde donde cuando".split()
)


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def _spread(chunks: list[dict], limit: int) -> list[dict]:
    if limit >= len(chunks):
        return list(chunks)
    if limit == 1:
        return [chunks[0]]
    step = (len(chunks) - 1) / (limit - 1)
    return [chunks[round(i * step)] for i in range(limit)]


def select_chunks(chunks: list[dict], topic: str, limit: int) -> list[dict]:
    """Up to `limit` chunks, in reading order.

    With a topic: the chunks that match it best (BM25). Without one, or when
    nothing matches: an even spread over the whole document.
    """
    if limit <= 0 or not chunks:
        return []
    query = _tokens(topic or "")
    if not query:
        return _spread(chunks, limit)

    docs = [_tokens(c["text"]) for c in chunks]
    n = len(docs)
    average = sum(len(d) for d in docs) / n or 1.0
    frequency = Counter(term for d in docs for term in set(d))
    scored = []
    for index, words in enumerate(docs):
        counts = Counter(words)
        score = 0.0
        for term in query:
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log((n - frequency[term] + 0.5) / (frequency[term] + 0.5) + 1)
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * len(words) / average))
        if score > 0:
            scored.append((score, index))
    if not scored:
        return _spread(chunks, limit)
    best = sorted(index for _, index in sorted(scored, key=lambda s: (-s[0], s[1]))[:limit])
    return [chunks[i] for i in best]
