"""
Global request-size limit for the TOMMI server.

Every HTTP request body (form posts, JSON, file uploads — including the LTI
tools mounted on the same app) is capped at MAX_REQUEST_BYTES. Larger requests
are refused with 413 before the body is read into memory: up front when the
client announces a Content-Length, and while streaming otherwise.

The per-feature limits in the code (audio uploads, bulk user files, agent
documents, LTI proyecto documents, imports) all use this same value, so it is
changed in one place.
"""

import json

from fastapi import HTTPException  # FastAPI re-raises its own HTTPException from body parsing

MAX_REQUEST_MB = 2
MAX_REQUEST_BYTES = MAX_REQUEST_MB * 1024 * 1024

TOO_LARGE_DETAIL = (
    f"La petición es demasiado grande (máximo {MAX_REQUEST_MB} MB). "
    f"Request too large (max {MAX_REQUEST_MB} MB)."
)


class _BodyTooLarge(HTTPException):
    """Raised while a body streams past the limit. It is an HTTPException so
    FastAPI passes it through as a 413 instead of wrapping body-read errors
    in a generic 400; if it escapes the app instead, the middleware below
    answers 413 itself."""

    def __init__(self):
        super().__init__(status_code=413, detail=TOO_LARGE_DETAIL)


class BodySizeLimitMiddleware:
    """Pure ASGI middleware (not BaseHTTPMiddleware) so it can stop a request
    while the body is still streaming in."""

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send, status=400, detail="Invalid Content-Length header")
                return

        received = 0
        response_started = False
        exceeded = False

        async def limited_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal response_started
            if exceeded:
                # The app may turn the interrupted read into its own error
                # (e.g. FastAPI's "error parsing the body" 400). Answer with
                # the 413 instead and drop the app's response.
                if message["type"] == "http.response.start" and not response_started:
                    response_started = True
                    await self._reject(send)
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(send)

    async def _reject(self, send, status: int = 413, detail: str = TOO_LARGE_DETAIL):
        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        })
        await send({"type": "http.response.body", "body": body})
