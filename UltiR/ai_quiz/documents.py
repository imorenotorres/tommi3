"""Course documents: checking an upload, storing it, reading it, listing and deleting.

Layout inside a course folder:

    documents.json                 index, oldest first
    docs/<doc_id>/source.<ext>     the upload, stored under our id, never under its own name
    docs/<doc_id>/pages.json       [{"page": 3, "text": "..."}]   page is null for .md/.txt
    docs/<doc_id>/chunks.json      [{"chunk_id", "page", "text"}]

The file name the user gave is kept only as a cleaned display label.
"""

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from UltiR.ai_quiz import ingestion, limits, storage


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
    return extension


def list_documents(course_id: str) -> list[dict]:
    """Newest first."""
    return list(reversed(storage.read_json(_index_path(course_id), default=[])))


def get_document(course_id: str, doc_id: str) -> dict | None:
    if not storage.is_id(doc_id, "d"):
        return None
    return next((d for d in storage.read_json(_index_path(course_id), default=[]) if d["doc_id"] == doc_id), None)


def load_chunks(course_id: str, doc_id: str) -> list[dict]:
    if get_document(course_id, doc_id) is None:
        return []
    return storage.read_json(_doc_dir(course_id, doc_id) / "chunks.json", default=[])


def add_document(course_id: str, filename: str, data: bytes, mode: str = "text") -> dict:
    """Check, store and read one upload. Raises UploadRejected; a refusal leaves nothing on disk."""
    extension = _check(filename, data, mode)
    digest = hashlib.sha256(data).hexdigest()

    with storage.locked(course_id):
        index = storage.read_json(_index_path(course_id), default=[])
        same = next((d for d in index if d["sha256"] == digest), None)
        if same:
            raise UploadRejected(409, "duplicate_document", doc_id=same["doc_id"])
        if len(index) >= limits.MAX_DOCUMENTS_PER_COURSE:
            raise UploadRejected(409, "too_many_documents")

        doc_id = storage.new_id("d")
        folder = _doc_dir(course_id, doc_id)
        folder.mkdir(parents=True)
        try:
            source = folder / f"source{extension}"
            source.write_bytes(data)
            parsed = ingestion.get_reader(mode).read(source)
            chunks = ingestion.chunk_pages(parsed.pages)
            storage.write_json(folder / "pages.json", [{"page": p.number, "text": p.text} for p in parsed.pages])
            storage.write_json(folder / "chunks.json", chunks)
        except ingestion.Unreadable as error:
            shutil.rmtree(folder, ignore_errors=True)
            _prune(course_id)
            raise UploadRejected(422, error.code) from None
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            _prune(course_id)
            raise

        document = {
            "doc_id": doc_id,
            "label": _label(filename),
            "size": len(data),
            "sha256": digest,
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": parsed.mode,
            "engine": parsed.engine,
            "status": "ready",
            "n_pages": len(parsed.pages),
            "n_chunks": len(chunks),
            "warnings": parsed.warnings,
        }
        storage.write_json(_index_path(course_id), index + [document])
        return document


def delete_document(course_id: str, doc_id: str) -> bool:
    with storage.locked(course_id):
        if get_document(course_id, doc_id) is None:
            return False
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
