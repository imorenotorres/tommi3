"""Course-scoped storage for the AI Quiz tool.

Everything a course owns lives in one folder under the data root. The folder
name is derived from the course id of the LTI session and from nothing else,
so one course cannot reach another course's files.

Writes are atomic (temp file, then rename). Read-modify-write sequences must
run inside `locked(course_id)`. The lock is per process: this assumes the
server runs as a single process, which is how the platform is started today.
"""

import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

_APP_DIR = Path(__file__).parent
_ID_RE = re.compile(r"[a-z]_[0-9a-f]{16}")

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def data_root() -> Path:
    """Where course folders live. AI_QUIZ_DATA_DIR overrides the default (used by the tests)."""
    root = Path(os.environ.get("AI_QUIZ_DATA_DIR") or _APP_DIR / "data")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _folder_name(course_id: str) -> str:
    """A safe, distinct folder name for any course id.

    The readable part keeps only ASCII letters, digits, "-" and "_". The hash
    of the full id is always appended, so two ids that look alike after
    cleaning (or differ only in case or beyond the kept length) still get
    different folders.
    """
    readable = "".join(c for c in course_id if c.isascii() and (c.isalnum() or c in "-_"))[:40]
    digest = hashlib.sha256(course_id.encode("utf-8", "replace")).hexdigest()[:16]
    return f"{readable or 'course'}-{digest}"


def course_dir(course_id: str) -> Path:
    folder = data_root() / _folder_name(str(course_id))
    folder.mkdir(exist_ok=True)
    return folder


@contextmanager
def locked(course_id: str):
    """Hold the course's lock. Re-entrant, so helpers can nest."""
    name = _folder_name(str(course_id))
    with _locks_guard:
        lock = _locks.setdefault(name, threading.RLock())
    with lock:
        yield


def new_id(kind: str) -> str:
    """A server-generated id such as d_3f9a1c2e5b7d9e01. `kind` is one lowercase letter."""
    return f"{kind}_{secrets.token_hex(8)}"


def is_id(value, kind: str) -> bool:
    """True only for an id of this kind in the exact shape new_id() produces.

    Ids arrive in URLs and become part of file names, so anything else is
    refused before it gets near a path.
    """
    return isinstance(value, str) and value[:1] == kind and _ID_RE.fullmatch(value) is not None


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data) -> None:
    """Replace `path` with `data` in one step; on any error the old file stays as it was."""
    path = Path(path)
    text = json.dumps(data, indent=2, ensure_ascii=False)   # fails here, before the disk is touched
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
