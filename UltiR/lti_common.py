"""
Shared LTI 1.1 infrastructure for all UNINOVIS LTI tools.

Provides OAuth 1.0a signature validation, session management, and the
standard LTI launch flow.  Each tool only needs to supply its own
consumer key/secret and route prefix.
"""

import hashlib
import hmac
import secrets
import time
import urllib.parse
from base64 import b64encode

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse


# ── OAuth 1.0a signature validation ──────────────────────────────────

def validate_oauth_signature(method: str, url: str, params: dict, consumer_secret: str) -> bool:
    """Validate an OAuth 1.0a HMAC-SHA1 signature (LTI 1.1)."""
    provided_sig = params.get("oauth_signature", "")
    sig_params = {k: v for k, v in params.items() if k != "oauth_signature"}
    sorted_params = sorted(sig_params.items())
    param_string = "&".join(
        f"{urllib.parse.quote(str(k), safe='')}" + "=" + f"{urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted_params
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_string, safe=""),
    ])
    signing_key = urllib.parse.quote(consumer_secret, safe="") + "&"
    hashed = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    computed_sig = b64encode(hashed.digest()).decode()
    return hmac.compare_digest(computed_sig, provided_sig)


def check_timestamp_nonce(timestamp: str, nonce: str) -> bool:
    """Basic replay protection: reject requests older than 10 minutes."""
    try:
        return abs(time.time() - int(timestamp)) < 600
    except (ValueError, TypeError):
        return False


# ── Session management ───────────────────────────────────────────────

SESSION_TTL = 3600 * 8  # 8 hours


class LTISessionStore:
    """Simple in-memory session store for an LTI tool."""

    def __init__(self):
        self._sessions: dict = {}

    def create(self, data: dict) -> str:
        token = secrets.token_hex(32)
        data["expires"] = time.time() + SESSION_TTL
        self._sessions[token] = data
        # Cleanup expired
        now = time.time()
        for k in [k for k, v in self._sessions.items() if v["expires"] < now]:
            del self._sessions[k]
        return token

    def get(self, token: str) -> dict | None:
        s = self._sessions.get(token)
        return s if s and s["expires"] > time.time() else None

    def require(self, request: Request) -> dict:
        token = request.query_params.get("token", "") or request.cookies.get("lti_session", "")
        session = self.get(token)
        if not session:
            raise HTTPException(401, "Sesion no valida. Accede desde Moodle.")
        return session


def is_instructor(session: dict) -> bool:
    """Check if the LTI session has an instructor role."""
    return "instructor" in session.get("role", "").lower()


# ── Standard LTI 1.1 launch ─────────────────────────────────────────

async def lti_launch(
    request: Request,
    consumer_key: str,
    consumer_secret: str,
    sessions: LTISessionStore,
    redirect_instructor: str,
    redirect_learner: str,
) -> HTMLResponse | RedirectResponse:
    """Handle an LTI 1.1 POST launch.  Returns a redirect to the
    appropriate view based on the user's role."""

    form = await request.form()
    params = dict(form)

    if params.get("oauth_consumer_key", "") != consumer_key:
        return HTMLResponse("<h2>Error: Consumer key no reconocido</h2>", status_code=403)

    # Build the launch URL (what Moodle signed against)
    launch_url = str(request.url).split("?")[0]
    if request.headers.get("x-forwarded-proto"):
        launch_url = (
            request.headers["x-forwarded-proto"] + "://"
            + request.headers.get("x-forwarded-host", request.url.hostname)
            + request.url.path
        )

    if not validate_oauth_signature("POST", launch_url, params, consumer_secret):
        return HTMLResponse(
            "<h2>Error: Firma OAuth no valida</h2>"
            "<p>Verifica que la clave y el secreto coinciden en Moodle y en el servidor.</p>",
            status_code=403,
        )
    if not check_timestamp_nonce(params.get("oauth_timestamp", ""), params.get("oauth_nonce", "")):
        return HTMLResponse("<h2>Error: Solicitud expirada</h2>", status_code=403)

    roles = params.get("roles", "")
    session_data = {
        "user_id": params.get("user_id", ""),
        "name": params.get("lis_person_name_full", ""),
        "email": params.get("lis_person_contact_email_primary", ""),
        "role": roles,
        "course_id": params.get("context_id", "default"),
        "course_name": params.get("context_title", ""),
        "resource_link_id": params.get("resource_link_id", ""),
    }
    token = sessions.create(session_data)

    if "instructor" in roles.lower():
        return RedirectResponse(f"{redirect_instructor}?token={token}", status_code=303)
    return RedirectResponse(f"{redirect_learner}?token={token}", status_code=303)


async def lti_test_launch(
    sessions: LTISessionStore,
    redirect_instructor: str,
    redirect_learner: str,
    role: str = "learner",
) -> RedirectResponse:
    """Create a test session without Moodle."""
    token = sessions.create({
        "user_id": "test_user",
        "name": "Usuario de prueba",
        "email": "test@test.com",
        "role": "Instructor" if role == "instructor" else "Learner",
        "course_id": "test",
        "course_name": "Curso de prueba",
        "resource_link_id": "test",
    })
    if "instructor" in role.lower():
        return RedirectResponse(f"{redirect_instructor}?token={token}", status_code=303)
    return RedirectResponse(f"{redirect_learner}?token={token}", status_code=303)
