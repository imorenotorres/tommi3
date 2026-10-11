"""The upload size limit is enforced while the body is read, whatever length the request declares (rule A7).

The first tests call the router at the ASGI level with a hand-fed body, so they
can count how much of it the tool actually asked for. A body that passes the
limit must be cut off there, not read to the end and refused afterwards.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI

from UltiR.ai_quiz import limits, storage

from .conftest import BASE

DOCS = f"{BASE}/api/documents"
BOUNDARY = "testboundary7d9f2a"
CHUNK = 16 * 1024


def multipart(name: str, data: bytes) -> bytes:
    return (f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{BOUNDARY}--\r\n".encode()


def pieces(body: bytes, size: int = CHUNK) -> list[bytes]:
    return [body[i:i + size] for i in range(0, len(body), size)]


def feed(token: str, chunks: list[bytes], declared_length: int | None) -> tuple[int, int]:
    """POST the chunks to the upload route. Returns (status code, number of chunks the tool asked for)."""
    from UltiR.ai_quiz.lti_provider import router

    app = FastAPI()
    app.include_router(router)
    headers = [(b"content-type", f"multipart/form-data; boundary={BOUNDARY}".encode())]
    if declared_length is not None:
        headers.append((b"content-length", str(declared_length).encode()))
    else:
        headers.append((b"transfer-encoding", b"chunked"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": DOCS, "raw_path": DOCS.encode(), "query_string": f"token={token}".encode(), "root_path": "",
        "headers": headers, "client": ("127.0.0.1", 50000), "server": ("testserver", 80),
    }
    asked = 0
    sent = []

    async def receive():
        nonlocal asked
        if asked < len(chunks):
            asked += 1
            return {"type": "http.request", "body": chunks[asked - 1], "more_body": asked < len(chunks)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    # In a thread of its own: the browser tests keep an event loop running in the main thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(app(scope, receive, send))).result()
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    return status, asked


def stored_files():
    return sorted(p for p in storage.data_root().rglob("*") if p.is_file())


@pytest.fixture
def instructor(launch):
    return launch.token(role="Instructor", course="course-A")


@pytest.fixture
def small_limit(monkeypatch):
    """A 1000-byte file limit, so a body of 100 chunks of 16 kB is far over it."""
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 1000)
    return 1000


OVERSIZED = pieces(multipart("big.txt", b"x" * (100 * CHUNK)))
# With the limit at 1000 bytes plus the room allowed for the form around the file,
# the tool may read a handful of 16 kB chunks before it knows. Not a hundred.
FEW = 8


def test_a_body_without_a_declared_length_is_cut_off_once_it_passes_the_limit(instructor, small_limit):
    status, asked = feed(instructor, OVERSIZED, declared_length=None)

    assert status == 413
    assert asked <= FEW, f"read {asked} of {len(OVERSIZED)} chunks before refusing"
    assert stored_files() == []


def test_a_body_longer_than_its_declared_length_is_cut_off_once_it_passes_the_limit(instructor, small_limit):
    status, asked = feed(instructor, OVERSIZED, declared_length=500)       # claims 500 bytes, sends 1.6 MB

    assert status == 413
    assert asked <= FEW, f"read {asked} of {len(OVERSIZED)} chunks before refusing"
    assert stored_files() == []


def test_a_declared_length_over_the_limit_is_refused_before_anything_is_read(instructor, small_limit):
    status, asked = feed(instructor, OVERSIZED, declared_length=sum(len(c) for c in OVERSIZED))

    assert (status, asked) == (413, 0)
    assert stored_files() == []


@pytest.mark.parametrize("declared", [None, 0, 5, "exact"])
def test_a_file_within_the_limit_is_accepted_whatever_length_is_declared(instructor, declared):
    body = multipart("notes.txt", b"Feature matching links the same physical point across two images. " * 4)
    chunks = pieces(body, 64)

    status, asked = feed(instructor, chunks, declared_length=len(body) if declared == "exact" else declared)

    assert status == 201
    assert asked == len(chunks)
    assert len([p for p in stored_files() if p.name.startswith("source")]) == 1


def test_a_file_just_over_the_limit_is_refused_and_one_just_under_is_accepted(instructor, monkeypatch):
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 2000)
    text = b"Twenty letters here. "

    over, _ = feed(instructor, pieces(multipart("over.txt", text * 96)), declared_length=None)       # 2016 bytes
    under, _ = feed(instructor, pieces(multipart("under.txt", text * 95)), declared_length=None)     # 1995 bytes

    assert (over, under) == (413, 201)


def test_an_oversized_body_from_a_learner_is_refused_for_the_role_before_any_of_it_is_read(launch, small_limit):
    status, asked = feed(launch.token(role="Learner", course="course-A"), OVERSIZED, declared_length=None)

    assert (status, asked) == (403, 0)


def test_an_oversized_body_without_a_session_is_refused_before_any_of_it_is_read(small_limit):
    status, asked = feed("", OVERSIZED, declared_length=None)

    assert (status, asked) == (401, 0)


# ── The same through the ordinary test client ───────────────────────────────

def test_a_chunked_upload_within_the_limit_works_through_the_http_client(client, instructor):
    body = multipart("notes.txt", b"Feature matching links the same physical point across two images. " * 4)

    response = client.post(DOCS, params={"token": instructor}, content=iter(pieces(body, 50)),
                           headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"})

    assert "content-length" not in response.request.headers
    assert response.status_code == 201


def test_a_chunked_upload_over_the_limit_is_refused_through_the_http_client(client, instructor, small_limit):
    response = client.post(DOCS, params={"token": instructor}, content=iter(OVERSIZED),
                           headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"})

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"
    assert stored_files() == []
