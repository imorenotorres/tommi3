"""Full reading with Docling: display formulas as LaTeX, figures, tables, exact page numbers.

Docling is not a dependency of the platform. It lives in a Python environment
of its own, and this reader starts it as a separate process for one document
at a time (docling_worker.py, run by the interpreter named in
AI_QUIZ_DOCLING_PYTHON). That keeps its three gigabytes of memory out of the
web server, lets a reading that hangs be stopped, and lets the process be
started without network access: the worker runs in a network namespace of its
own (`unshare -rn`) and gets none of the server's environment. Models must
already be in a folder on the server; nothing is fetched.

If any of this is missing, full reading is reported as unavailable and
text-only reading goes on working.

The worker only reports what Docling found. What becomes of it is decided in
`build_document`, which is plain Python and is tested against a recorded
result. What it does, and why (from the reader test of 2026-10-10):

- a paragraph that runs over a page break is split by Docling's own character
  ranges, so every sentence keeps its page;
- a formula is kept as LaTeX between $$ and $$ only if it passes a sanity
  check; otherwise the text layer's version of it is used, as text reading
  would give it (a block of pseudocode and formulas next to a second column
  came out broken);
- a picture smaller than 100 pixels is not a figure (the page-header logo);
- a figure's caption must carry its "Figure N" label; otherwise the caption is
  looked up among the captions on the page (a figure got one of its inner
  labels as caption);
- figures get our own ids and are checked to be PNG or JPEG by their first bytes.

Inline formulas are not recovered: Docling reads them from the text layer,
exactly as text reading does.
"""

import functools
import json
import logging
import os
import re
import shutil
import signal
import struct
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from UltiR.ai_quiz import config, ingestion, limits

log = logging.getLogger("ultir.ai_quiz")

WORKER = Path(__file__).with_name("docling_worker.py")
RESULT_VERSION = 1
MAX_RESULT_BYTES = 20 * 1024 * 1024

FIGURE_MARK = ingestion.FIGURE_MARK
_CAPTION = re.compile(r"(?:Figure|Fig\.|Figura)\s*\d+", re.IGNORECASE)
_EQUATION_NUMBER = re.compile(r"\((\d{1,3}[a-z]?)\)\s*$")
_PRIVATE_USE = re.compile(r"[\ue000-\uf8ff]")
_WORKER_IMAGE = re.compile(r"p\d{4}\.png")
_LONG_TEXT_IN_FORMULA = re.compile(r"\\text\s*\{[^{}]{40,}\}")


# ── Is full reading available on this server? ─────────────────────────────────

@functools.lru_cache(maxsize=None)
def _can_block_network() -> bool:
    """Whether a process can be started without network access. Asked once per server process."""
    tool = shutil.which("unshare")
    if not tool:
        return False
    try:
        return subprocess.run([tool, "-rn", "true"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@functools.lru_cache(maxsize=8)
def _has_docling(python: str) -> bool:
    """Whether that interpreter can see a docling package. Looks it up, does not import it."""
    probe = "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('docling') else 1)"
    try:
        return subprocess.run([python, "-I", "-c", probe], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def unavailable_reason() -> str | None:
    """None when full reading can run; otherwise why not, for the log."""
    python = config.docling_python()
    if not python:
        return "AI_QUIZ_DOCLING_PYTHON is not set"
    if not (os.path.isabs(python) and os.path.isfile(python) and os.access(python, os.X_OK)):
        return "AI_QUIZ_DOCLING_PYTHON does not name a Python interpreter"
    if not os.path.isdir(config.docling_models()):
        return "the folder of Docling models does not exist"
    if not _can_block_network():
        return "a process cannot be started without network access here (unshare -rn)"
    if not _has_docling(python):
        return "the interpreter in AI_QUIZ_DOCLING_PYTHON has no docling package"
    return None


# ── Running the worker ────────────────────────────────────────────────────────

def _collect(out_dir: Path) -> tuple[dict, dict[str, bytes]]:
    """Read what the worker left in its folder: the result, and the images the result names.

    The worker's output is checked like any other untrusted input. An image is
    read only if its name has exactly the shape the worker uses, so a name in
    the result can never point outside the folder.
    """
    result = out_dir / "result.json"
    if not result.is_file() or result.stat().st_size > MAX_RESULT_BYTES:
        raise RuntimeError("the worker left no usable result")
    raw = json.loads(result.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise RuntimeError("the worker's result has the wrong shape")
    images = {}
    for item in raw["items"]:
        name = item.get("file") if isinstance(item, dict) else None
        if not isinstance(name, str) or not _WORKER_IMAGE.fullmatch(name):
            continue
        path = out_dir / name
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= limits.MAX_FIGURE_BYTES:
            images[name] = path.read_bytes()
    return raw, images


def run_worker(pdf: Path, stop=None) -> tuple[dict, dict[str, bytes]]:
    """Run Docling on `pdf` in a process of its own, without network. Returns its result and images."""
    reason = unavailable_reason()
    if reason:
        raise ingestion.ReaderUnavailable(reason)
    out_dir = Path(tempfile.mkdtemp(prefix="reading-", dir=pdf.parent))
    try:
        command = [shutil.which("unshare"), "-rn", config.docling_python(), "-I", str(WORKER),
                   str(pdf), str(out_dir), config.docling_models(), config.docling_device(),
                   str(min(8, os.cpu_count() or 1))]
        # A fresh environment: none of the server's settings, and so none of its secrets, reach the worker.
        environment = {"PATH": "/usr/bin:/bin", "HOME": os.path.expanduser("~"), "HF_HUB_OFFLINE": "1"}
        with open(out_dir / "worker.log", "wb") as errors:
            process = subprocess.Popen(command, env=environment, cwd=out_dir, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
            try:
                while True:
                    try:
                        code = process.wait(timeout=0.2)
                        break
                    except subprocess.TimeoutExpired:
                        if stop is not None and stop.is_set():
                            raise ingestion.ReadingStopped() from None
            finally:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
        if code != 0:
            raise RuntimeError(f"the Docling worker ended with code {code}")
        return _collect(out_dir)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ── Turning the worker's result into a document ───────────────────────────────

def image_type(data: bytes) -> str | None:
    """PNG or JPEG, decided from the first bytes. Anything else, SVG included, is not an image for us."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG's header."""
    if len(data) < 24:
        return 0, 0
    return struct.unpack(">II", data[16:24])


def formula_is_sound(latex: str) -> bool:
    """A cheap check that a recognised formula is worth showing. Rendering is the browser's job."""
    if not latex.strip() or len(latex) > limits.MAX_FORMULA_CHARS or "$" in latex:
        return False
    depth = 0
    for char in re.sub(r"\\[{}]", "", latex):          # \{ and \} are literal braces, not grouping
        depth += (char == "{") - (char == "}")
        if depth < 0:
            return False
    if depth != 0:
        return False
    begins, ends = len(re.findall(r"\\begin\s*\{", latex)), len(re.findall(r"\\end\s*\{", latex))
    if begins != ends or ("&" in latex.replace("\\&", "") and not begins):
        return False
    # \left and \right come in pairs (\leftarrow and the like are other commands)
    if len(re.findall(r"\\left(?![A-Za-z])", latex)) != len(re.findall(r"\\right(?![A-Za-z])", latex)):
        return False
    return not _LONG_TEXT_IN_FORMULA.search(latex)       # a sentence inside \text{}: prose read as a formula


def _prose(text) -> str:
    """Text from the worker as a paragraph of ours: repaired like any extracted text, and never a formula."""
    text = ingestion.clean(_PRIVATE_USE.sub("", text if isinstance(text, str) else ""))
    return " ".join(text.replace("$$", "$ $").split())


def _pages_of(item: dict, n_pages: int) -> list[dict]:
    found = []
    for entry in item.get("prov") or []:
        page = entry.get("page") if isinstance(entry, dict) else None
        if isinstance(page, int) and not isinstance(page, bool) and 1 <= page <= n_pages:
            found.append(entry)
    return found


def _caption(text: str) -> str:
    text = _prose(text)
    if len(text) > limits.MAX_CAPTION_CHARS:
        text = text[: limits.MAX_CAPTION_CHARS].rsplit(" ", 1)[0] + "…"
    return text


def build_document(raw: dict, images: dict[str, bytes]) -> ingestion.ParsedDocument:
    """Pages, figures and warnings from one worker result. Raises Unreadable when nothing usable is in it."""
    if raw.get("version") != RESULT_VERSION:
        raise RuntimeError("the worker's result is of a version this reader does not know")
    n_pages = raw.get("n_pages")
    if not isinstance(n_pages, int) or isinstance(n_pages, bool) or n_pages < 1:
        raise ingestion.Unreadable("no_text")
    if n_pages > limits.MAX_FULL_READING_PAGES:
        raise ingestion.Unreadable("too_long")

    items = [(item, _pages_of(item, n_pages)) for item in raw["items"] if isinstance(item, dict)]
    items = [(item, prov) for item, prov in items if prov]            # an item without a page has no place

    # Which pictures are figures, and which caption belongs to each.
    labelled = [(index, _caption(item.get("text")), prov[0]["page"])
                for index, (item, prov) in enumerate(items) if item.get("kind") == "text"]
    labelled = [entry for entry in labelled if _CAPTION.match(entry[1])]
    figures, figure_at, taken, dropped = [], {}, set(), 0
    for index, (item, prov) in enumerate(items):
        if item.get("kind") != "picture":
            continue
        data = images.get(item.get("file") if isinstance(item.get("file"), str) else "")
        if not data:
            continue                                                  # Docling found a picture and made no image of it
        media_type = image_type(data)
        if media_type is None or len(data) > limits.MAX_FIGURE_BYTES:
            dropped += 1
            continue
        # The size is read from the image itself where that is simple; what the worker says is only a fallback.
        width, height = _png_size(data) if media_type == "image/png" else (item.get("width"), item.get("height"))
        if not (isinstance(width, int) and isinstance(height, int)) or min(width, height) < limits.MIN_FIGURE_PIXELS:
            continue                                                  # a logo or an ornament, not a figure
        if len(figures) >= limits.MAX_FIGURES_PER_DOCUMENT:
            dropped += 1
            continue
        page = prov[0]["page"]
        caption = _caption(item.get("caption"))
        if not _CAPTION.match(caption) or caption in taken:
            near = [(abs(at - index), text) for at, text, on_page in labelled if on_page == page and text not in taken]
            caption = min(near)[1] if near else ""
        if caption:
            taken.add(caption)
        figure = ingestion.Figure(figure_id=f"f{len(figures) + 1:04d}", page=page, caption=caption,
                                  image=data, media_type=media_type, width=width, height=height)
        figures.append(figure)
        figure_at[index] = figure

    parts: dict[int, list[str]] = defaultdict(list)
    as_text, collapsed = set(), set()
    for index, (item, prov) in enumerate(items):
        page, kind = prov[0]["page"], item.get("kind")
        if kind == "picture":
            figure = figure_at.get(index)
            if figure:
                parts[page].append(f"[FIGURE {figure.figure_id}] {figure.caption}".strip())
        elif kind == "table":
            rows = [[_prose(cell) for cell in row] for row in item.get("rows") or [] if isinstance(row, list)]
            rows = [" | ".join(cell for cell in row if cell) for row in rows]
            if len(rows) < 3:
                collapsed.add(page)                                   # a header and one row: the grid was not recognised
            parts[page].extend(row for row in rows if row)
        elif kind == "formula":
            latex = item.get("text") if isinstance(item.get("text"), str) else ""
            original = _prose(item.get("orig"))
            if formula_is_sound(latex):
                number = _EQUATION_NUMBER.search(original)
                parts[page].append(f"$${' '.join(latex.split())}$$" + (f" ({number.group(1)})" if number else ""))
            elif original:
                as_text.add(page)
                parts[page].append(original)
        elif kind == "text":
            text = item.get("text") if isinstance(item.get("text"), str) else ""
            if _prose(text) in taken or _caption(text) in taken:
                continue                                              # already written beside its figure
            spans = [entry.get("charspan") for entry in prov]
            if len(prov) > 1 and all(isinstance(s, list) and len(s) == 2 for s in spans):
                # one paragraph over a page break: each page gets its own part
                for entry, (start, end) in zip(prov, spans):
                    piece = _prose(text[start:end])
                    if piece:
                        parts[entry["page"]].append(piece)
            elif _prose(text):
                parts[page].append(_prose(text))

    pages = [ingestion.Page(number=n, text="\n\n".join(parts.get(n, []))) for n in range(1, n_pages + 1)]
    if sum(len(p.text) for p in pages) > limits.MAX_TEXT_CHARS:
        raise ingestion.Unreadable("too_long")
    if sum(1 for p in pages for c in p.text if c.isalnum()) < max(20, 10 * n_pages):
        raise ingestion.Unreadable("no_text")

    warnings = []
    empty = [p.number for p in pages if not p.text]
    if empty:
        warnings.append({"code": "pages_without_text", "pages": empty})
    if as_text:
        warnings.append({"code": "formulas_as_text", "pages": sorted(as_text)})
    if collapsed:
        warnings.append({"code": "table_collapsed", "pages": sorted(collapsed)})
    if dropped:
        warnings.append({"code": "figures_dropped", "count": dropped})
    return ingestion.ParsedDocument(pages=pages, mode="full", engine="docling", warnings=warnings, figures=figures)


class DoclingReader:
    name = "docling"
    mode = "full"

    def read(self, path: Path, stop=None) -> ingestion.ParsedDocument:
        raw, images = run_worker(path, stop)
        return build_document(raw, images)
