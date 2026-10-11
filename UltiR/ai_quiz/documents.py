"""Course documents: checking an upload, storing it, reading it, listing and deleting.

Layout inside a course folder:

    documents.json                 index, oldest first
    docs/<doc_id>/source.<ext>     the upload, stored under our id, never under its own name
    docs/<doc_id>/pages.json       [{"page": 3, "text": "..."}]   page is null for .md/.txt
    docs/<doc_id>/chunks.json      [{"chunk_id", "page", "text"}]

The file name the user gave is kept only as a cleaned display label.

A document has a status. Text reading happens inside the upload request, so
such a document is "ready" at once. Full reading takes minutes: the upload is
answered with "processing", a background job does the reading, and the
document ends as "ready" or as "failed" with a reason. A failed reading keeps
its line in the index and none of its files.
"""

import hashlib
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from UltiR.ai_quiz import ingestion, jobs, limits, storage

log = logging.getLogger("ultir.ai_quiz")


class UploadRejected(Exception):
    def __init__(self, status: int, code: str, **extra):
        super().__init__(code)
        self.status = status
        self.code = code
        self.extra = extra


def _index_path(course_id: str) -> Path:
    return storage.course_dir(course_id) / "documents.json"


def _doc_dir(course_id: str, doc_id: str) -> Path:
    return storage.course_dir(course_id) / "docs" / doc_id


def _extension(filename: str) -> str:
    match = re.search(r"\.[A-Za-z0-9]{1,5}$", filename or "")
    return match.group(0).lower() if match else ""


def _label(filename: str) -> str:
    """A display label from an untrusted file name: last path part, safe characters, bounded length."""
    name = re.split(r"[\\/]", filename or "")[-1]
    name = re.sub(r"[^\w\-. ]", "_", name)
    name = re.sub(r"\.{2,}", ".", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > limits.MAX_LABEL_CHARS:
        extension = _extension(name)
        name = name[: limits.MAX_LABEL_CHARS - len(extension)] + extension
    return name or "document"


def _check(filename: str, data: bytes, mode: str) -> str:
    """Refuse anything that is not a document we can read. Returns the extension."""
    extension = _extension(filename)
    if extension not in limits.ALLOWED_EXTENSIONS:
        raise UploadRejected(415, "unsupported_type")
    if mode not in ("text", "full"):
        raise UploadRejected(400, "bad_mode")
    if not data:
        raise UploadRejected(400, "empty_file")
    if len(data) > limits.MAX_UPLOAD_BYTES:
        raise UploadRejected(413, "file_too_large")
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise UploadRejected(400, "not_a_pdf")
    else:
        if b"\x00" in data:
            raise UploadRejected(400, "not_text")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise UploadRejected(400, "not_text") from None
    if mode == "full":
        try:
            ingestion.get_reader("full")
        except ingestion.ReaderUnavailable:
            raise UploadRejected(409, "full_reading_unavailable") from None
        if extension != ".pdf":
            raise UploadRejected(400, "full_reading_pdf_only")
    return extension


def _index(course_id: str) -> list[dict]:
    """The index of the course, oldest first.

    A document that is marked as being read while this process runs no job
    for it was cut short, by a restart for instance. It is marked as failed
    here, so that it never shows as "processing" for ever. This relies on the
    server being one process: a second process would not know the first one's jobs.
    """
    with storage.locked(course_id):
        index = storage.read_json(_index_path(course_id), default=[])
        lost = [d for d in index if d["status"] == "processing" and not jobs.is_running(jobs.key_of(d["doc_id"]))]
        for document in lost:
            document.update(status="failed", error="reading_interrupted")
            shutil.rmtree(_doc_dir(course_id, document["doc_id"]), ignore_errors=True)
        if lost:
            storage.write_json(_index_path(course_id), index)
        return index


def list_documents(course_id: str) -> list[dict]:
    """Newest first."""
    return list(reversed(_index(course_id)))


def get_document(course_id: str, doc_id: str) -> dict | None:
    if not storage.is_id(doc_id, "d"):
        return None
    return next((d for d in _index(course_id) if d["doc_id"] == doc_id), None)


def load_chunks(course_id: str, doc_id: str) -> list[dict]:
    document = get_document(course_id, doc_id)
    if document is None or document["status"] != "ready":
        return []
    return storage.read_json(_doc_dir(course_id, doc_id) / "chunks.json", default=[])


def _store_reading(folder: Path, parsed: ingestion.ParsedDocument) -> dict:
    """Write what a reader produced into the document's folder. Returns the index fields it settles."""
    chunks = ingestion.chunk_pages(parsed.pages)
    storage.write_json(folder / "pages.json", [{"page": p.number, "text": p.text} for p in parsed.pages])
    storage.write_json(folder / "chunks.json", chunks)
    records = []
    for figure in parsed.figures:
        # The file is named by us, from our id and the type we found in the image's first bytes.
        name = figure.figure_id + _FIGURE_EXTENSIONS[figure.media_type]
        (folder / "figures").mkdir(exist_ok=True)
        (folder / "figures" / name).write_bytes(figure.image)
        records.append({"figure_id": figure.figure_id, "page": figure.page, "caption": figure.caption, "file": name,
                        "media_type": figure.media_type, "bytes": len(figure.image),
                        "width": figure.width, "height": figure.height})
    if records:
        storage.write_json(folder / "figures.json", records)
    return {"engine": parsed.engine, "status": "ready", "n_pages": len(parsed.pages), "n_chunks": len(chunks),
            "n_figures": len(records), "warnings": parsed.warnings}


# ── Figures ───────────────────────────────────────────────────────────────────
# Figures exist only inside the folder of their document, which is inside the folder of its
# course. Nothing here builds a path from what a request says: an id is compared with the ids
# in figures.json, and the file name comes from that record.

_FIGURE_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg"}
_FIGURE_ID = re.compile(r"f\d{4}")


def _figure_records(course_id: str, doc_id: str) -> list[dict] | None:
    document = get_document(course_id, doc_id)
    if document is None or document["status"] != "ready":
        return None
    return storage.read_json(_doc_dir(course_id, doc_id) / "figures.json", default=[])


def list_figures(course_id: str, doc_id: str) -> list[dict] | None:
    """What the figures of a document are, without where they are kept. None: no such document that is ready."""
    records = _figure_records(course_id, doc_id)
    if records is None:
        return None
    return [{key: record.get(key) for key in ("figure_id", "page", "caption", "width", "height")} for record in records]


def get_figure(course_id: str, doc_id: str, figure_id) -> dict | None:
    """The stored record of one figure of this course, or None."""
    if not isinstance(figure_id, str) or not _FIGURE_ID.fullmatch(figure_id):
        return None
    return next((r for r in _figure_records(course_id, doc_id) or [] if r.get("figure_id") == figure_id), None)


def figure_file(course_id: str, doc_id: str, figure_id) -> tuple[Path, str] | None:
    """Where the image of a figure is, and its type. None if there is no such figure in this course."""
    record = get_figure(course_id, doc_id, figure_id)
    if record is None:
        return None
    extension = _FIGURE_EXTENSIONS.get(record.get("media_type"))
    # The record was written by us. It is checked all the same: if it has been damaged or
    # tampered with, the name it gives is not used.
    if extension is None or record.get("file") != figure_id + extension:
        return None
    path = _doc_dir(course_id, doc_id) / "figures" / record["file"]
    return (path, record["media_type"]) if path.is_file() else None


def add_document(course_id: str, filename: str, data: bytes, mode: str = "text") -> dict:
    """Check and store one upload, and read it: at once in text mode, as a background job in full mode.

    Raises UploadRejected; a refusal leaves nothing on disk.
    """
    extension = _check(filename, data, mode)
    digest = hashlib.sha256(data).hexdigest()

    with storage.locked(course_id):
        index = _index(course_id)
        same = next((d for d in index if d["sha256"] == digest and d["status"] != "failed"), None)
        if same:
            raise UploadRejected(409, "duplicate_document", doc_id=same["doc_id"])
        if len(index) >= limits.MAX_DOCUMENTS_PER_COURSE:
            raise UploadRejected(409, "too_many_documents")
        if mode == "full" and any(d["status"] == "processing" for d in index):
            raise UploadRejected(409, "reading_in_progress")

        doc_id = storage.new_id("d")
        folder = _doc_dir(course_id, doc_id)
        folder.mkdir(parents=True)
        document = {
            "doc_id": doc_id,
            "label": _label(filename),
            "size": len(data),
            "sha256": digest,
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": mode,
            "error": None,
        }
        try:
            source = folder / f"source{extension}"
            source.write_bytes(data)
            # Text reading comes first in both modes. It is quick, and it refuses a damaged
            # file or a scan before a slow job is started for it.
            parsed = ingestion.get_reader("text").read(source)
            if mode == "text":
                document.update(_store_reading(folder, parsed))
            elif len(parsed.pages) > limits.MAX_FULL_READING_PAGES:
                raise UploadRejected(422, "too_many_pages_for_full_reading")
            else:
                document.update(engine=ingestion.get_reader("full").name, status="processing",
                                n_pages=len(parsed.pages), n_chunks=0, warnings=[])
        except ingestion.Unreadable as error:
            shutil.rmtree(folder, ignore_errors=True)
            _prune(course_id)
            raise UploadRejected(422, error.code) from None
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            _prune(course_id)
            raise

        # An earlier failed reading of the same file makes way for this upload.
        index = [d for d in index if not (d["sha256"] == digest and d["status"] == "failed")]
        storage.write_json(_index_path(course_id), index + [document])
        if document["status"] == "processing":
            jobs.start(jobs.key_of(doc_id),
                       lambda stop: _read_in_full(course_id, doc_id, source, stop),
                       limits.FULL_READING_SECONDS,
                       lambda: _fail(course_id, doc_id, "reading_timeout"))
        return document


# ── The full-reading job ──────────────────────────────────────────────────────

def _read_in_full(course_id: str, doc_id: str, source: Path, stop) -> None:
    """The work of one job. Every way out ends in _finish or _fail, or in nothing when it was stopped."""
    try:
        parsed = ingestion.get_reader("full").read(source, stop=stop)
        _finish(course_id, doc_id, parsed)
    except ingestion.ReadingStopped:
        pass                                    # whoever stopped it has already settled the document
    except ingestion.Unreadable as error:
        _fail(course_id, doc_id, error.code)
    except ingestion.ReaderUnavailable as error:
        log.error("AI Quiz: full reading is not available: %s", error.reason)
        _fail(course_id, doc_id, "full_reading_unavailable")
    except Exception as error:   # noqa: BLE001 - whatever the engine throws; details go to the log only
        log.error("AI Quiz: full reading of %s failed (%s)", doc_id, type(error).__name__)
        _fail(course_id, doc_id, "reading_failed")


def _finish(course_id: str, doc_id: str, parsed: ingestion.ParsedDocument) -> None:
    """Store the result, unless the document was settled in the meantime (time limit, deletion, restart)."""
    with storage.locked(course_id):
        index = storage.read_json(_index_path(course_id), default=[])
        document = next((d for d in index if d["doc_id"] == doc_id), None)
        if document is None or document["status"] != "processing":
            return
        document.update(_store_reading(_doc_dir(course_id, doc_id), parsed))
        storage.write_json(_index_path(course_id), index)


def _fail(course_id: str, doc_id: str, code: str) -> None:
    """Mark a reading as failed and remove its files. Does nothing to a document that is already settled."""
    with storage.locked(course_id):
        index = storage.read_json(_index_path(course_id), default=[])
        document = next((d for d in index if d["doc_id"] == doc_id), None)
        if document is None or document["status"] != "processing":
            return
        document.update(status="failed", error=code)
        shutil.rmtree(_doc_dir(course_id, doc_id), ignore_errors=True)
        storage.write_json(_index_path(course_id), index)


def delete_document(course_id: str, doc_id: str) -> bool:
    with storage.locked(course_id):
        if get_document(course_id, doc_id) is None:
            return False
        jobs.cancel(jobs.key_of(doc_id))        # a reading still under way finds its document gone
        index = storage.read_json(_index_path(course_id), default=[])
        storage.write_json(_index_path(course_id), [d for d in index if d["doc_id"] != doc_id])
        shutil.rmtree(_doc_dir(course_id, doc_id), ignore_errors=True)
        return True


def _prune(course_id: str) -> None:
    """Remove the docs folder again if a refused upload was the only thing that created it."""
    docs = storage.course_dir(course_id) / "docs"
    try:
        docs.rmdir()
    except OSError:
        pass
