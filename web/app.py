"""
Tommi Web Interface - FastAPI server para interactuar con agentes Tommi
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Depends, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel

# Cargar .env de web/ con override para asegurar que se usa la configuración correcta
_web_env = Path(__file__).parent / ".env"
load_dotenv(_web_env, override=True)

from agent_runner import AgentRunner
from auth import (
    authenticate, approve_access_request, change_password, create_access_request,
    create_user, create_user_pending, create_invite_token, delete_user,
    ensure_superuser, get_session, has_role, list_access_requests, list_users,
    logout, reject_access_request, send_invite_email, set_password_from_invite,
    update_user_role, user_exists, validate_invite_token, validate_password,
    validate_uninovis_email, ROLES, TOOL_ACCESS, UNINOVIS_DOMAINS,
    can_access_tool, can_edit, user_roles, max_role_level,
)
from error_codes import (
    format_error,
    LLM_OLLAMA_NOT_RUNNING, LLM_MODEL_NOT_FOUND, LLM_OLLAMA_ERROR,
    LLM_OLLAMA_TIMEOUT, LLM_NO_API_KEY, LLM_INVALID_API_KEY,
    LLM_MISTRAL_ERROR, LLM_CONNECTION_ERROR, LLM_UNKNOWN_ERROR,
    LLM_VLLM_NOT_RUNNING, LLM_VLLM_ERROR, LLM_VLLM_MODEL_NOT_FOUND,
    AGENT_NOT_FOUND, SERVER_STREAMING_ERROR
)

# Configuración de logging (activable/desactivable via ENABLE_LOGGING)
ENABLE_LOGGING = os.getenv("ENABLE_LOGGING", "true").lower() in ("true", "1", "yes")

# All logs (conversations + feedback) stored in /logs, one file per agent
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Per-agent conversation loggers (one .log file per agent, created on demand)
_agent_loggers: dict = {}


def _get_agent_logger(agent_id: str) -> logging.Logger:
    """Return (or create) a per-agent conversation logger."""
    if agent_id not in _agent_loggers:
        logger = logging.getLogger(f"conversations.{agent_id}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.FileHandler(
            LOGS_DIR / f"{agent_id}_conversations.log", encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        _agent_loggers[agent_id] = logger
    return _agent_loggers[agent_id]


def log_conversation(
    client_ip: str,
    agent_id: str,
    agent_name: str,
    question: str,
    response: str,
    session_id: str = "",
    transparency_level: str = None,
    username: str = None,
):
    """Registra una conversación en el log (si está habilitado).
    Writes a per-agent .log file and a per-agent .jsonl file."""
    if not ENABLE_LOGGING:
        return

    # Pseudonymize username for privacy (same method as AuditLogger)
    anon_user_id = None
    email_domain = None
    if username:
        import hashlib
        raw = f"tommi-uninovis-2026:{username}"
        anon_user_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        # Extract country TLD (e.g. "user@uma.es" -> "es")
        if "@" in username:
            email_domain = username.rsplit("@", 1)[1].rsplit(".", 1)[-1].lower()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "client_ip": client_ip,
        "session_id": session_id,
        "user_id": anon_user_id,
        "email_domain": email_domain,
        "transparency_level": transparency_level,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "question": question,
        "response": response[:500] + "..." if len(response) > 500 else response
    }

    # Per-agent .log (human-readable, pretty-printed)
    try:
        _get_agent_logger(agent_id).info(
            json.dumps(entry, ensure_ascii=False, indent=2) + "\n"
        )
    except Exception:
        pass
    # Per-agent .jsonl (machine-readable, one line per entry)
    try:
        agent_log = LOGS_DIR / f"{agent_id}_conversations.jsonl"
        with open(agent_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

# Configuración
SCRIPT_DIR = Path(__file__).parent
AGENTS_PATH = SCRIPT_DIR.parent / "agents"  # tommi/agents/

# Inicializar runner
runner = AgentRunner(agents_base_path=str(AGENTS_PATH))

# FastAPI app
app = FastAPI(
    title="Tommi Web Interface",
    description="Interfaz web para agentes Tommi",
    version="1.0.0"
)

# Ensure a superuser exists on startup
_su = ensure_superuser()
logger = logging.getLogger("tommi")
logger.info(f"Superuser ready: {_su}")

# Auth middleware — protects /api/* routes (except /api/auth/login)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    # Routes that don't require authentication
    PUBLIC_PATHS = {"/api/auth/login", "/api/auth/invite/validate", "/api/auth/invite/set-password", "/api/auth/request-access", "/api/auth/forgot-password"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Only protect /api/ routes (not static files, HTML pages, etc.)
        # PDF endpoints are public (academic documents, not personal data)
        # Study app routes are public (participants don't need TOMMI accounts)
        is_study = path.startswith("/study/api/") or path.startswith("/rag-study/api/") or path.startswith("/sql-study/api/")
        if path.startswith("/api/") and path not in self.PUBLIC_PATHS and "/pdf/" not in path and "/quickguide" not in path and "/agreements-search" not in path and "/agreements-config" not in path and "/public-tools" not in path and not is_study:
            token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not token:
                token = request.query_params.get("token", "")
            if not token or not get_session(token):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        return await call_next(request)


app.add_middleware(AuthMiddleware)

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory=SCRIPT_DIR / "static"), name="static")
app.mount("/img", StaticFiles(directory=SCRIPT_DIR / "img"), name="img")

# Mount UNIGRACON app (grade converter)
from apps.unigracon.unigracon import router as unigracon_router
app.include_router(unigracon_router)
app.mount("/unigracon/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "unigracon" / "static"), name="unigracon_static")

# Mount Mobility Planner app
from apps.mobility_planner.mobility_planner import router as mobility_router
app.include_router(mobility_router)
app.mount("/mobility_planner/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "mobility_planner" / "static"), name="mobility_static")

# Mount Directory app
from apps.directory.directory import router as directory_router
app.include_router(directory_router)
app.mount("/directory/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "directory" / "static"), name="directory_static")

# Mount UNINOVIS Admin hub
from apps.uninovis.uninovis import router as uninovis_router
app.include_router(uninovis_router)
app.mount("/uninovis/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "uninovis" / "static"), name="uninovis_static")

# Mount Researcher Connect app
from apps.researcher_connect.researcher_connect import router as researcher_connect_router
app.include_router(researcher_connect_router)
app.mount("/researcher_connect/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "researcher_connect" / "static"), name="researcher_connect_static")

# Mount Transparency Study apps
from apps.rag_study.study import router as rag_study_router
app.include_router(rag_study_router)
app.mount("/rag-study/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "rag_study" / "static"), name="rag_study_static")

# Mount Event Calendar app
from apps.event_calendar.event_calendar import router as event_calendar_router
app.include_router(event_calendar_router)
app.mount("/event-calendar/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "event_calendar" / "static"), name="event_calendar_static")

# Mount Matomo Analytics app
from apps.matomo_analytics.matomo_analytics import router as matomo_analytics_router
app.include_router(matomo_analytics_router)
app.mount("/matomo-analytics/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "matomo_analytics" / "static"), name="matomo_analytics_static")

# Mount Survey DATA FOR L.I.F.E. app
from apps.survey_datalife.survey_datalife import router as survey_datalife_router
app.include_router(survey_datalife_router)
app.mount("/survey-datalife/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "survey_datalife" / "static"), name="survey_datalife_static")

# Mount Research Proposals app
from apps.research_proposals.research_proposals import router as research_proposals_router
app.include_router(research_proposals_router)
app.mount("/research_proposals/static", StaticFiles(directory=SCRIPT_DIR / "apps" / "research_proposals" / "static"), name="research_proposals_static")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_token(request: Request) -> str | None:
    """Extract bearer token from Authorization header or query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.query_params.get("token")


def require_auth(request: Request) -> dict:
    """Dependency: require a valid session. Returns session dict."""
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def require_role(minimum_role: str):
    """Dependency factory: require at least the given role level."""
    from auth import max_role_level as _max_level
    def _check(session: dict = Depends(require_auth)):
        if _max_level(session) < ROLES.get(minimum_role, 99):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return session
    return _check


# ---------------------------------------------------------------------------
# Auth API routes
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str
    roles: list[str] = []


class UpdateRoleRequest(BaseModel):
    role: str
    roles: list[str] = []


@app.post("/api/auth/login")
async def api_login(req: LoginRequest):
    result = authenticate(req.username, req.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return result


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    token = _get_token(request)
    if token:
        logout(token)
    return {"ok": True}


@app.get("/api/auth/me")
async def api_me(session: dict = Depends(require_auth)):
    from auth import _load_users, is_study_mode
    users = _load_users()
    user = users.get(session["username"], {})
    result = {
        "username": session["username"],
        "role": session["role"],
        "roles": session.get("roles", [session["role"]]),
        "provisional_password": user.get("provisional_password", False),
    }
    if is_study_mode():
        result["study_mode"] = True
        result["study_condition"] = user.get("study_condition")
    return result


@app.post("/api/auth/change-password")
async def api_change_password(req: ChangePasswordRequest, session: dict = Depends(require_auth)):
    pwd_error = validate_password(req.new_password)
    if pwd_error:
        raise HTTPException(status_code=400, detail=pwd_error)
    ok = change_password(session["username"], req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    return {"ok": True}


@app.get("/api/auth/users")
async def api_list_users(session: dict = Depends(require_role("superuser"))):
    return list_users()


@app.post("/api/auth/users")
async def api_create_user(req: CreateUserRequest, session: dict = Depends(require_role("superuser"))):
    all_roles = req.roles if req.roles else [req.role]
    for r in all_roles:
        if r not in ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role '{r}'. Must be one of: {list(ROLES.keys())}")
    pwd_error = validate_password(req.password)
    if pwd_error:
        raise HTTPException(status_code=400, detail=pwd_error)
    ok = create_user(req.username, req.password, all_roles[0], provisional=True, roles=all_roles)
    if not ok:
        raise HTTPException(status_code=409, detail="Username already exists")
    return {"ok": True, "username": req.username, "roles": all_roles}


@app.post("/api/auth/users/bulk")
async def api_bulk_create_users(
    file: UploadFile,
    session: dict = Depends(require_role("superuser")),
):
    """
    Bulk-create users from a TSV or Excel (.xlsx) file.
    Expected columns: username, password, role
    Header row is optional (auto-detected).
    All users are created with provisional_password=True.
    """
    filename = (file.filename or "").lower()
    content = await file.read()

    rows: list[list[str]] = []

    if filename.endswith((".xlsx", ".xls")):
        import io
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() if c is not None else "" for c in row]
                if any(cells):
                    rows.append(cells)
            wb.close()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading Excel file: {e}")
    elif filename.endswith((".tsv", ".txt", ".csv")):
        import csv, io
        text = content.decode("utf-8-sig")
        # Auto-detect delimiter
        dialect = csv.Sniffer().sniff(text[:2048], delimiters="\t,;")
        reader = csv.reader(io.StringIO(text), dialect)
        for row in reader:
            cells = [c.strip() for c in row]
            if any(cells):
                rows.append(cells)
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Use .xlsx, .tsv, .csv, or .txt",
        )

    if not rows:
        raise HTTPException(status_code=400, detail="File is empty")

    # Auto-detect header: if first row looks like a header, skip it
    first = [c.lower() for c in rows[0]]
    if "username" in first or "user" in first or "nombre" in first:
        rows = rows[1:]

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found after header")

    valid_roles = set(ROLES.keys())
    created = []
    skipped = []
    errors = []

    for i, row in enumerate(rows, start=1):
        if len(row) < 2:
            errors.append(f"Row {i}: not enough columns (need at least username and password)")
            continue

        username = row[0].strip()
        password = row[1].strip()
        role = row[2].strip().lower() if len(row) > 2 and row[2].strip() else "user"

        if not username:
            errors.append(f"Row {i}: empty username")
            continue
        pwd_err = validate_password(password)
        if pwd_err:
            errors.append(f"Row {i} ({username}): {pwd_err}")
            continue
        if role not in valid_roles:
            errors.append(f"Row {i} ({username}): invalid role '{role}' (must be {', '.join(valid_roles)})")
            continue

        ok = create_user(username, password, role, provisional=True)
        if ok:
            created.append({"username": username, "role": role})
        else:
            skipped.append(f"{username} (already exists)")

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "total_created": len(created),
        "total_skipped": len(skipped),
        "total_errors": len(errors),
    }


@app.delete("/api/auth/users/{username}")
async def api_delete_user(username: str, session: dict = Depends(require_role("superuser"))):
    if username == session["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    ok = delete_user(username)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@app.put("/api/auth/users/{username}/role")
async def api_update_role(username: str, req: UpdateRoleRequest, session: dict = Depends(require_role("superuser"))):
    all_roles = req.roles if req.roles else [req.role]
    for r in all_roles:
        if r not in ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role '{r}'. Must be one of: {list(ROLES.keys())}")
    if username == session["username"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    ok = update_user_role(username, all_roles[0], all_roles)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Invitation / email routes
# ---------------------------------------------------------------------------

# SMTP config — re-read from .env on each call so changes don't require restart
def _check_directory_email(email: str) -> str:
    """Check if an email exists in the directory. Returns the person's name if found, empty string if not."""
    try:
        import json
        directory_path = SCRIPT_DIR / "apps" / "directory" / "data.json"
        if not directory_path.exists():
            return ""
        with open(directory_path, encoding="utf-8") as f:
            data = json.load(f)
        email_lower = email.lower()
        for user in data.get("users", []):
            if user.get("email", "").lower() == email_lower:
                return f"{user.get('first_name', '')} {user.get('family_name', '')}".strip()
    except Exception:
        pass
    return ""


def _get_smtp_config() -> dict:
    """Read SMTP settings from .env file each time (not cached)."""
    from dotenv import dotenv_values
    env = dotenv_values(_web_env)
    host = env.get("SMTP_HOST", "")
    user = env.get("SMTP_USER", "")
    password = env.get("SMTP_PASSWORD", "")
    return {
        "host": host,
        "port": int(env.get("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "from_addr": env.get("SMTP_FROM", "") or user,
        "use_tls": env.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        "configured": bool(host and user and password),
    }


class InviteUserRequest(BaseModel):
    username: str  # email address
    role: str


class SetPasswordRequest(BaseModel):
    token: str
    password: str


@app.get("/api/auth/smtp-status")
async def api_smtp_status(session: dict = Depends(require_role("superuser"))):
    """Check if SMTP is configured."""
    smtp = _get_smtp_config()
    return {"configured": smtp["configured"]}


@app.post("/api/auth/invite")
async def api_invite_user(req: InviteUserRequest, request: Request, session: dict = Depends(require_role("superuser"))):
    """Create a user and send an invitation email to set their password."""
    if req.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(ROLES.keys())}")
    smtp = _get_smtp_config()
    if not smtp["configured"]:
        raise HTTPException(status_code=503, detail="SMTP is not configured. Add SMTP_HOST, SMTP_USER, and SMTP_PASSWORD to web/.env")

    # Create user without password (pending invite)
    from auth import user_exists
    if user_exists(req.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    create_user_pending(req.username, req.role)

    # Generate invitation token
    invite_token = create_invite_token(req.username)
    if not invite_token:
        raise HTTPException(status_code=500, detail="Failed to create invitation token")

    # Build invitation URL
    base_url = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
    invite_url = f"{base_url}/set-password?token={invite_token}"

    # Send email
    ok = send_invite_email(
        username=req.username,
        invite_url=invite_url,
        smtp_host=smtp["host"],
        smtp_port=smtp["port"],
        smtp_user=smtp["user"],
        smtp_password=smtp["password"],
        smtp_from=smtp["from_addr"],
        smtp_use_tls=smtp["use_tls"],
    )

    if not ok:
        return {"ok": True, "email_sent": False, "warning": "User created but email could not be sent. Check SMTP configuration."}

    return {"ok": True, "email_sent": True, "username": req.username}


@app.post("/api/auth/invite/resend/{username}")
async def api_resend_invite(username: str, request: Request, session: dict = Depends(require_role("superuser"))):
    """Resend invitation email to an existing user."""
    smtp = _get_smtp_config()
    if not smtp["configured"]:
        raise HTTPException(status_code=503, detail="SMTP is not configured")

    from auth import user_exists
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")

    invite_token = create_invite_token(username)
    if not invite_token:
        raise HTTPException(status_code=500, detail="Failed to create invitation token")

    base_url = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
    invite_url = f"{base_url}/set-password?token={invite_token}"

    ok = send_invite_email(
        username=username,
        invite_url=invite_url,
        smtp_host=smtp["host"],
        smtp_port=smtp["port"],
        smtp_user=smtp["user"],
        smtp_password=smtp["password"],
        smtp_from=smtp["from_addr"],
        smtp_use_tls=smtp["use_tls"],
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SMTP configuration.")
    return {"ok": True, "email_sent": True}


@app.get("/api/auth/invite/validate")
async def api_validate_invite(token: str = Query(...)):
    """Validate an invitation token (public endpoint)."""
    username = validate_invite_token(token)
    if not username:
        return {"valid": False}
    return {"valid": True, "username": username}


@app.post("/api/auth/invite/set-password")
async def api_set_password_from_invite(req: SetPasswordRequest):
    """Set password using an invitation token (public endpoint)."""
    pwd_error = validate_password(req.password)
    if pwd_error:
        raise HTTPException(status_code=400, detail=pwd_error)
    username = set_password_from_invite(req.token, req.password)
    if not username:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation link")
    return {"ok": True, "username": username}


@app.get("/set-password")
async def set_password_page():
    """Serve the set-password page."""
    return FileResponse(SCRIPT_DIR / "static" / "set_password.html")


# ---------------------------------------------------------------------------
# Access request routes (self-registration)
# ---------------------------------------------------------------------------

class AccessRequestBody(BaseModel):
    email: str
    full_name: str
    institution: str
    department: str = ""
    profile_url: str = ""
    reason: str = ""


@app.post("/api/auth/request-access")
async def api_request_access(req: AccessRequestBody, request: Request):
    """Public endpoint: submit an access request (must be UNINOVIS email).
    If the email is found in the directory, an invitation is sent automatically."""
    email = req.email.strip().lower()
    # Validate email domain
    domain_err = validate_uninovis_email(email)
    if domain_err:
        raise HTTPException(status_code=400, detail=domain_err)
    if not req.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required")

    # Check if user already exists
    if user_exists(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Use 'Forgot password' if you need to reset it.")

    # Check if the email is in the directory
    directory_match = _check_directory_email(email)

    if directory_match:
        # Auto-create user and send invitation
        try:
            create_user(email, role="student", provisional=True)
            invite_token = create_invite_token(email)
            if invite_token:
                smtp = _get_smtp_config()
                if smtp["configured"]:
                    base_url = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
                    invite_url = f"{base_url}/set-password?token={invite_token}"
                    try:
                        send_invite_email(
                            username=email,
                            invite_url=invite_url,
                            smtp_host=smtp["host"],
                            smtp_port=smtp["port"],
                            smtp_user=smtp["user"],
                            smtp_password=smtp["password"],
                            from_addr=smtp["from_addr"],
                        )
                    except Exception:
                        pass
            return {"ok": True, "message": f"Your email was found in the UNINOVIS directory ({directory_match}). An invitation has been sent to {email}."}
        except Exception:
            pass  # Fall through to manual request

    # Not in directory — create a pending access request
    reason = req.reason.strip() if req.reason.strip() else "Sign up request"
    ok = create_access_request(
        email, req.full_name.strip(), req.institution.strip(),
        department=getattr(req, 'department', ''),
        profile_url=getattr(req, 'profile_url', ''),
        reason=reason,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="A request with this email already exists")
    return {"ok": True, "message": "Access request submitted. A UNINOVIS administrator will review your request and you will receive an email when approved."}


@app.post("/api/auth/forgot-password")
async def api_forgot_password(request: Request, body: dict = None):
    """Public endpoint: request a password reset link.
    Checks if the email/username exists and sends an invite token that
    allows setting a new password via the existing set-password flow."""
    if body is None:
        body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email or username is required")

    # Check if user exists
    if not user_exists(email):
        # Don't reveal whether the user exists — always show success
        return {"ok": True, "message": "If this email is registered, a password reset link has been sent."}

    # Generate an invite token (reuses the existing invite mechanism)
    invite_token = create_invite_token(email)
    if not invite_token:
        return {"ok": True, "message": "If this email is registered, a password reset link has been sent."}

    # Try to send the reset email
    smtp = _get_smtp_config()
    if smtp["configured"]:
        base_url = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
        reset_url = f"{base_url}/set-password?token={invite_token}"
        try:
            send_invite_email(
                username=email,
                invite_url=reset_url,
                smtp_host=smtp["host"],
                smtp_port=smtp["port"],
                smtp_user=smtp["user"],
                smtp_password=smtp["password"],
                from_addr=smtp["from_addr"],
                subject="UNINOVIS — Password Reset",
            )
        except Exception:
            pass  # Don't reveal email sending failures

    return {"ok": True, "message": "If this email is registered, a password reset link has been sent."}


@app.get("/api/auth/access-requests")
async def api_list_requests(
    status: Optional[str] = Query(None),
    session: dict = Depends(require_role("superuser")),
):
    """List access requests (superuser only)."""
    return list_access_requests(status)


@app.post("/api/auth/access-requests/{email}/approve")
async def api_approve_request(
    email: str,
    request: Request,
    role: str = Query("user"),
    session: dict = Depends(require_role("superuser")),
):
    """Approve an access request and optionally send invitation email."""
    if role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(ROLES.keys())}")
    ok = approve_access_request(email, role)
    if not ok:
        raise HTTPException(status_code=404, detail="Pending request not found")

    # Try to send invitation email
    email_sent = False
    smtp = _get_smtp_config()
    if smtp["configured"]:
        invite_token = create_invite_token(email)
        if invite_token:
            base_url = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
            invite_url = f"{base_url}/set-password?token={invite_token}"
            email_sent = send_invite_email(
                username=email,
                invite_url=invite_url,
                smtp_host=smtp["host"],
                smtp_port=smtp["port"],
                smtp_user=smtp["user"],
                smtp_password=smtp["password"],
                smtp_from=smtp["from_addr"],
                smtp_use_tls=smtp["use_tls"],
            )

    return {"ok": True, "email_sent": email_sent}


@app.post("/api/auth/access-requests/{email}/reject")
async def api_reject_request(email: str, session: dict = Depends(require_role("superuser"))):
    """Reject an access request."""
    ok = reject_access_request(email)
    if not ok:
        raise HTTPException(status_code=404, detail="Pending request not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Study mode endpoints (superuser only)
# ---------------------------------------------------------------------------

@app.get("/api/study/status")
async def study_status(session: dict = Depends(require_role("superuser"))):
    """Get study mode status and condition assignments."""
    from auth import is_study_mode, _load_users, STUDY_CONDITIONS
    users = _load_users()
    counts = {c: 0 for c in STUDY_CONDITIONS}
    assignments = []
    for uname, udata in users.items():
        cond = udata.get("study_condition")
        if cond:
            counts[cond] = counts.get(cond, 0) + 1
            assignments.append({"username": uname, "condition": cond})
    return {
        "enabled": is_study_mode(),
        "conditions": STUDY_CONDITIONS,
        "counts": counts,
        "total_assigned": sum(counts.values()),
        "assignments": assignments,
    }


@app.post("/api/study/enable")
async def study_enable(session: dict = Depends(require_role("superuser"))):
    """Enable study mode (random transparency assignment)."""
    from auth import STUDY_CONFIG_FILE
    config = {"enabled": True, "study_id": "UMA-IA-TOMMI-STUDY-001",
              "conditions": ["black_box", "grey_box", "crystal_box"],
              "description": "Effect of AI Transparency Levels on User Trust"}
    with open(STUDY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return {"ok": True, "study_mode": True}


@app.post("/api/study/disable")
async def study_disable(session: dict = Depends(require_role("superuser"))):
    """Disable study mode (users choose transparency freely)."""
    from auth import STUDY_CONFIG_FILE
    config = {"enabled": False}
    with open(STUDY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return {"ok": True, "study_mode": False}


@app.post("/api/study/reset")
async def study_reset(session: dict = Depends(require_role("superuser"))):
    """Clear all study condition assignments (for a new study run)."""
    from auth import _load_users, _save_users
    users = _load_users()
    cleared = 0
    for udata in users.values():
        for key in ["study_condition", "study_participant", "study_id",
                     "email_domain", "study_completed"]:
            if key in udata:
                del udata[key]
        cleared += 1
    _save_users(users)
    return {"ok": True, "cleared": cleared}


@app.post("/api/study/enroll/{username}")
async def study_enroll(username: str, session: dict = Depends(require_role("superuser"))):
    """Enroll a specific user as a study participant."""
    from auth import enroll_study_participant
    result = enroll_study_participant(username)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, **result}


@app.post("/api/study/enroll-bulk")
async def study_enroll_bulk(usernames: list[str], session: dict = Depends(require_role("superuser"))):
    """Enroll multiple users as study participants."""
    from auth import enroll_study_participant
    results = []
    for u in usernames:
        r = enroll_study_participant(u)
        results.append({"username": u, **(r or {"error": "not found"})})
    return {"ok": True, "enrolled": results}


@app.get("/api/study/queries")
async def study_queries(session: dict = Depends(require_auth)):
    """Return the predefined study queries."""
    queries_file = SCRIPT_DIR / "data" / "study_queries.json"
    if not queries_file.exists():
        raise HTTPException(status_code=404, detail="Study queries not configured")
    with open(queries_file, "r", encoding="utf-8") as f:
        return json.load(f)


class StudyQuestionnaireRequest(BaseModel):
    agent_id: str
    query_number: int
    stias_1: int
    stias_2: int
    stias_3: int
    understanding: int
    reliance: int


@app.post("/api/study/questionnaire")
async def study_questionnaire(req: StudyQuestionnaireRequest, session: dict = Depends(require_auth)):
    """Save per-query questionnaire answers to the study log."""
    from auth import get_study_info
    info = get_study_info(session["username"])
    if not info:
        raise HTTPException(status_code=403, detail="Not a study participant")

    # Find the agent's study_log.jsonl
    agent_instance = runner.get_agent_instance(req.agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not found")

    import os
    from sys import path as sys_path
    agent_dir = getattr(agent_instance, '_agent_dir', None)
    if not agent_dir:
        raise HTTPException(status_code=500, detail="Agent directory not found")

    study_log_path = os.path.join(agent_dir, "data", "study_log.jsonl")

    # Import StudyLogger from the agent's base
    sys_path_entry = os.path.join(os.path.dirname(agent_dir), "base")
    if sys_path_entry not in sys_path:
        sys_path.insert(0, sys_path_entry)
    from badges import StudyLogger

    questionnaire = {
        "stias_1": req.stias_1,
        "stias_2": req.stias_2,
        "stias_3": req.stias_3,
        "understanding": req.understanding,
        "reliance": req.reliance,
    }

    updated = StudyLogger.update_questionnaire(
        study_log_path=study_log_path,
        study_id=info["study_id"],
        query_number=req.query_number,
        questionnaire=questionnaire,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Study log entry not found for this query")
    return {"ok": True}


@app.post("/api/study/comparison")
async def study_comparison(request: Request, session: dict = Depends(require_auth)):
    """Save within-subjects comparison study results to a JSONL log."""
    import os
    data = await request.json()
    log_path = SCRIPT_DIR / "data" / "study_comparison_log.jsonl"
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "username": session["username"],
        **data,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.post("/api/study/complete")
async def study_complete(session: dict = Depends(require_auth)):
    """Mark the current user's study as completed."""
    from auth import mark_study_completed, get_study_info
    info = get_study_info(session["username"])
    if not info:
        raise HTTPException(status_code=403, detail="Not a study participant")
    mark_study_completed(session["username"])
    return {"ok": True, "study_id": info["study_id"]}


@app.get("/study")
async def study_page():
    """Serve the study interface page."""
    return FileResponse(SCRIPT_DIR / "static" / "study.html")


class ChatRequest(BaseModel):
    """Request para enviar un mensaje a un agente"""
    agent_id: str
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Respuesta de un agente"""
    response: str
    session_id: str


class AgentResponse(BaseModel):
    """Información de un agente"""
    id: str
    name: str
    agent_type: str
    description: str
    welcome_message: str
    example_queries: list[str]
    rag_approach: str = "context_preserving"
    show_history: bool = True
    show_description: bool = False
    transparency_level: str = "black_box"
    transparency_type: str = ""
    prompt_level: str = "stringent"
    decision_trace: str = "black_box"


@app.get("/")
async def root():
    """Serve the UNINOVIS intranet as the landing page"""
    return FileResponse(SCRIPT_DIR / "static" / "intranet.html")


@app.get("/intranet")
async def intranet_page():
    """Alias for the intranet landing page"""
    return FileResponse(SCRIPT_DIR / "static" / "intranet.html")


@app.get("/rag-study")
async def rag_study_page():
    """RAG Architecture Study entry point"""
    return FileResponse(SCRIPT_DIR / "static" / "rag_study.html")


@app.get("/agents")
async def agents_page():
    """Serve the TOMMI AI Agents interface"""
    return FileResponse(SCRIPT_DIR / "static" / "index.html")


@app.get("/agents/{agent_id}")
async def agents_page_with_agent(agent_id: str):
    """Serve the TOMMI AI Agents interface with a specific agent pre-selected"""
    return FileResponse(SCRIPT_DIR / "static" / "index.html")


@app.get("/login")
async def login_page():
    """Sirve la página de login"""
    return FileResponse(SCRIPT_DIR / "static" / "login.html")


@app.get("/testing")
async def testing():
    """Sirve la interfaz de tester-developer"""
    return FileResponse(SCRIPT_DIR / "static" / "testing.html")


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    return FileResponse(SCRIPT_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/config")
async def get_config():
    """Devuelve la configuración pública del servidor"""
    return {"logging_enabled": ENABLE_LOGGING}


async def get_ollama_model_info(base_url: str, model_name: str) -> dict:
    """Consulta la API de Ollama para obtener información detallada del modelo."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{base_url}/api/show", json={"name": model_name})
            if response.status_code == 200:
                data = response.json()
                # Extraer información relevante
                details = data.get("details", {})
                model_info = {
                    "family": details.get("family", ""),
                    "parameter_size": details.get("parameter_size", ""),
                    "quantization_level": details.get("quantization_level", ""),
                }
                # Construir nombre descriptivo
                parts = [model_name]
                if model_info["parameter_size"]:
                    parts.append(model_info["parameter_size"])
                if model_info["quantization_level"]:
                    parts.append(model_info["quantization_level"])
                return {
                    "full_name": " ".join(parts) if len(parts) > 1 else model_name,
                    "details": model_info
                }
    except Exception:
        pass
    return {"full_name": model_name, "details": {}}


async def check_ollama_health(base_url: str, model: str) -> dict:
    """Check if Ollama is running and if the model is available."""
    import httpx

    result = {
        "ollama_running": False,
        "model_available": False,
        "error": None,
        "error_code": None,
        "error_type": None,
        "instructions": None
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Check if Ollama is running
            try:
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    result["ollama_running"] = True
                    models_data = response.json()
                    available_models = [m.get("name", "").split(":")[0] for m in models_data.get("models", [])]

                    # 2. Check if model is available
                    model_base = model.split(":")[0]
                    if model_base in available_models or model in [m.get("name", "") for m in models_data.get("models", [])]:
                        result["model_available"] = True
                    else:
                        err = format_error(LLM_MODEL_NOT_FOUND, model=model)
                        result.update(err)
                        result["available_models"] = available_models[:5]
                else:
                    result.update(format_error(LLM_OLLAMA_ERROR))
            except httpx.ConnectError:
                result.update(format_error(LLM_OLLAMA_NOT_RUNNING))
            except httpx.TimeoutException:
                result.update(format_error(LLM_OLLAMA_TIMEOUT))

    except Exception as e:
        result.update(format_error(LLM_UNKNOWN_ERROR, details=str(e)))

    return result


async def check_mistral_health(api_key: str) -> dict:
    """Check if the Mistral API key is valid."""
    import httpx

    result = {
        "api_key_configured": False,
        "api_key_valid": False,
        "error": None,
        "error_code": None,
        "error_type": None,
        "instructions": None
    }

    if not api_key:
        result.update(format_error(LLM_NO_API_KEY))
        return result

    result["api_key_configured"] = True

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code == 200:
                result["api_key_valid"] = True
            elif response.status_code == 401:
                result.update(format_error(LLM_INVALID_API_KEY))
            else:
                result.update(format_error(LLM_MISTRAL_ERROR, status_code=response.status_code))
    except Exception as e:
        result.update(format_error(LLM_CONNECTION_ERROR, details=str(e)))

    return result


async def check_vllm_health(base_url: str, model: str) -> dict:
    """Check if vLLM is running and if the model is available."""
    import httpx

    result = {
        "vllm_running": False,
        "model_available": False,
        "error": None,
        "error_code": None,
        "error_type": None,
        "instructions": None
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Check if vLLM is running (endpoint /v1/models)
            try:
                response = await client.get(f"{base_url}/models")
                if response.status_code == 200:
                    result["vllm_running"] = True
                    models_data = response.json()
                    available_models = [m.get("id", "") for m in models_data.get("data", [])]

                    # 2. Check if model is available
                    if model in available_models:
                        result["model_available"] = True
                    else:
                        err = format_error(LLM_VLLM_MODEL_NOT_FOUND, model=model)
                        result.update(err)
                        result["available_models"] = available_models[:5]
                else:
                    result.update(format_error(LLM_VLLM_ERROR, status_code=response.status_code))
            except httpx.ConnectError:
                result.update(format_error(LLM_VLLM_NOT_RUNNING))
            except httpx.TimeoutException:
                result.update(format_error(LLM_VLLM_NOT_RUNNING))

    except Exception as e:
        result.update(format_error(LLM_UNKNOWN_ERROR, details=str(e)))

    return result


# ---------------------------------------------------------------------------
# LLM provider helpers & agent visibility
# ---------------------------------------------------------------------------

LOCAL_PROVIDERS = {"ollama", "vllm"}

# Agent visibility: {agent_id: {level: "hidden"|"restricted"|"open", allowed_users: [...]}}
# Stored in data/agent_visibility.json
# Levels: hidden = superuser only, restricted (default) = testers+, open = any user
_VISIBILITY_FILE = Path(__file__).parent / "data" / "agent_visibility.json"

VISIBILITY_LEVELS = {"hidden", "restricted", "open"}


def _load_visibility() -> dict:
    if not _VISIBILITY_FILE.exists():
        return {}
    with open(_VISIBILITY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Migrate old boolean format to new format
    migrated = False
    for k, v in list(data.items()):
        if isinstance(v, bool):
            data[k] = {"level": "restricted" if v else "hidden", "allowed_users": []}
            migrated = True
        elif isinstance(v, str):
            data[k] = {"level": v if v in VISIBILITY_LEVELS else "restricted", "allowed_users": []}
            migrated = True
    if migrated:
        _save_visibility(data)
    return data


def _save_visibility(data: dict) -> None:
    with open(_VISIBILITY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_agent_visibility(agent_id: str) -> dict:
    """Get visibility config for an agent. Default is restricted."""
    vis = _load_visibility()
    entry = vis.get(agent_id, {})
    if isinstance(entry, dict):
        return {"level": entry.get("level", "restricted"), "allowed_users": entry.get("allowed_users", [])}
    return {"level": "restricted", "allowed_users": []}


def _can_user_see_agent(agent_id: str, username: str, role: str) -> bool:
    """Check if a user can see an agent based on visibility level and allowed_users."""
    if role == "superuser":
        return True
    cfg = _get_agent_visibility(agent_id)
    # If allowed_users is set, only those users can see it (overrides level)
    if cfg["allowed_users"]:
        return username.lower() in [u.lower() for u in cfg["allowed_users"]]
    level = cfg["level"]
    if level == "hidden":
        return False
    if level == "open":
        return True
    # restricted: testers and above
    return role in ("tester", "superuser")


def _get_agent_provider(agent_id: str) -> str:
    """Determine the LLM provider for a given agent. Returns provider name (lowercase)."""
    from dotenv import dotenv_values

    # Check agent-specific .env
    agent_info = runner.get_agent(agent_id)
    if agent_info:
        agent_env_path = Path(agent_info.path) / ".env"
        if agent_env_path.exists():
            agent_env = dotenv_values(agent_env_path)
            if agent_env.get("LLM_PROVIDER"):
                return agent_env["LLM_PROVIDER"].lower()

    # Fallback to global web/.env
    web_env = dotenv_values(Path(__file__).parent / ".env")
    return web_env.get("LLM_PROVIDER", "mistral").lower()


def _is_local_provider(agent_id: str) -> bool:
    """Check if an agent uses a local (on-premise) LLM provider."""
    return _get_agent_provider(agent_id) in LOCAL_PROVIDERS


@app.get("/api/llm-status")
async def get_llm_status(agent_id: Optional[str] = Query(None, description="ID del agente (opcional)")):
    """Devuelve información sobre el proveedor de LLM del agente especificado o el global"""
    from dotenv import dotenv_values

    # Determinar configuración a usar
    provider = None
    model = None
    base_url = None
    api_key = None

    # Si se especifica un agente, verificar si tiene su propia config LLM
    # Solo usa la config del agente si define LLM_PROVIDER explícitamente
    if agent_id:
        agent_info = runner.get_agent(agent_id)
        if agent_info:
            agent_env_path = Path(agent_info.path) / ".env"
            if agent_env_path.exists():
                agent_env = dotenv_values(agent_env_path)

                # Solo usar config del agente si define LLM_PROVIDER
                if agent_env.get("LLM_PROVIDER"):
                    provider = agent_env.get("LLM_PROVIDER").lower()

                    if provider == "ollama":
                        model = agent_env.get("OLLAMA_MODEL", "mistral")
                        base_url = agent_env.get("OLLAMA_BASE_URL", "http://localhost:11434")
                    elif provider == "vllm":
                        model = agent_env.get("VLLM_MODEL")
                        base_url = agent_env.get("VLLM_BASE_URL", "http://localhost:8000/v1")
                    else:
                        model = agent_env.get("MISTRAL_MODEL", "mistral-small-latest")
                        api_key = agent_env.get("MISTRAL_API_KEY")

    # Configuración global (leer directamente de web/.env, no de os.environ
    # porque agent_runner puede haberlo sobrescrito al cargar otro agente)
    if not provider:
        web_env = dotenv_values(Path(__file__).parent / ".env")
        provider = web_env.get("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            model = web_env.get("OLLAMA_MODEL", "mistral")
            base_url = web_env.get("OLLAMA_BASE_URL", "http://localhost:11434")
        elif provider == "vllm":
            model = web_env.get("VLLM_MODEL")
            base_url = web_env.get("VLLM_BASE_URL", "http://localhost:8000/v1")
        else:
            model = web_env.get("MISTRAL_MODEL", "mistral-small-latest")
            api_key = web_env.get("MISTRAL_API_KEY")

    # Build main LLM response
    response = {}

    if provider == "ollama":
        health = await check_ollama_health(base_url, model)

        if health["error"]:
            response = {
                "provider": "ollama",
                "is_local": True,
                "model": model,
                "base_url": base_url,
                "status": "error",
                "error_code": health["error_code"],
                "error_type": health["error_type"],
                "error": health["error"],
                "instructions": health["instructions"],
                "available_models": health.get("available_models", [])
            }
        else:
            model_info = await get_ollama_model_info(base_url, model)
            # Fetch all available Ollama models for cycling
            ollama_models = []
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as hclient:
                    resp = await hclient.get(f"{base_url}/api/tags")
                    if resp.status_code == 200:
                        for m in resp.json().get("models", []):
                            name = m.get("name", "")
                            size_bytes = m.get("size", 0)
                            size_gb = round(size_bytes / (1024**3), 1)
                            ollama_models.append({"name": name, "size_gb": size_gb})
            except Exception:
                pass
            # Filter out models larger than the cycling threshold (default 20 GB).
            # This prevents users from cycling to very large models that would
            # cause memory pressure and slow model-swapping on shared instances.
            max_cycling_gb = float(os.getenv("OLLAMA_MAX_CYCLING_GB", "20"))
            cycling_models = [m for m in ollama_models if m["size_gb"] <= max_cycling_gb]
            # Build sizes dict with both full name and base name (without tag)
            model_sizes = {}
            for m in ollama_models:
                model_sizes[m["name"]] = m["size_gb"]
                base_name = m["name"].split(":")[0]
                if base_name not in model_sizes:
                    model_sizes[base_name] = m["size_gb"]
            response = {
                "provider": "ollama",
                "is_local": True,
                "model": model,
                "display_name": f"Ollama: {model_info['full_name']}",
                "base_url": base_url,
                "model_details": model_info["details"],
                "status": "ok",
                "available_models": [m["name"] for m in cycling_models],
                "model_sizes": model_sizes,
            }
    elif provider == "vllm":
        health = await check_vllm_health(base_url, model)

        if health["error"]:
            response = {
                "provider": "vllm",
                "is_local": True,
                "model": model,
                "base_url": base_url,
                "status": "error",
                "error_code": health["error_code"],
                "error_type": health["error_type"],
                "error": health["error"],
                "instructions": health["instructions"],
                "available_models": health.get("available_models", [])
            }
        else:
            response = {
                "provider": "vllm",
                "is_local": True,
                "model": model,
                "display_name": f"vLLM: {model}",
                "base_url": base_url,
                "status": "ok"
            }
    else:
        health = await check_mistral_health(api_key)

        if health["error"]:
            response = {
                "provider": "mistral",
                "is_local": False,
                "model": model,
                "status": "error",
                "error_code": health["error_code"],
                "error_type": health["error_type"],
                "error": health["error"],
                "instructions": health["instructions"]
            }
        else:
            response = {
                "provider": "mistral",
                "is_local": False,
                "model": model,
                "display_name": f"Mistral: {model}",
                "base_url": None,
                "status": "ok"
            }

    # Add available models list (for model switching UI)
    # Only apply AVAILABLE_MODELS from .env for cloud providers;
    # local (Ollama/vLLM) already have their own list from the API.
    if not response.get("is_local"):
        from dotenv import dotenv_values as _dv
        _web_env = _dv(Path(__file__).parent / ".env")
        available_raw = _web_env.get("AVAILABLE_MODELS", "")
        if available_raw:
            response["available_models"] = [m.strip() for m in available_raw.split(",") if m.strip()]

    return response


@app.get("/api/llm-models")
async def get_llm_models(provider: str = Query(...), session: dict = Depends(require_role("tester"))):
    """Return available models for a given LLM provider."""
    from dotenv import dotenv_values
    web_env = dotenv_values(Path(__file__).parent / ".env")
    provider = provider.lower()

    if provider == "ollama":
        base_url = web_env.get("OLLAMA_BASE_URL", "http://localhost:11434")
        models = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as hclient:
                resp = await hclient.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    for m in resp.json().get("models", []):
                        name = m.get("name", "")
                        size_gb = round(m.get("size", 0) / (1024**3), 1)
                        models.append({"name": name, "size_gb": size_gb})
        except Exception:
            pass
        max_gb = float(os.getenv("OLLAMA_MAX_CYCLING_GB", "20"))
        return {"provider": "ollama", "models": [m["name"] for m in models if m["size_gb"] <= max_gb]}
    elif provider == "mistral":
        available_raw = web_env.get("AVAILABLE_MODELS", "")
        models = [m.strip() for m in available_raw.split(",") if m.strip()] if available_raw else ["mistral-small-latest", "mistral-large-latest"]
        return {"provider": "mistral", "models": models}
    elif provider == "openai":
        return {"provider": "openai", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]}
    elif provider == "anthropic":
        return {"provider": "anthropic", "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"]}
    else:
        return {"provider": provider, "models": []}


@app.put("/api/agents/{agent_id}/llm-provider")
async def set_agent_llm_provider(agent_id: str, request: Request, session: dict = Depends(require_role("superuser"))):
    """Update the LLM provider and model for an agent by writing its .env file."""
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    body = await request.json()
    provider = body.get("provider", "").lower()
    model = body.get("model", "")

    if not provider or not model:
        raise HTTPException(status_code=400, detail="provider and model are required")

    agent_env_path = Path(agent.path) / ".env"

    # Read existing .env lines, preserving non-LLM entries
    existing_lines = []
    llm_keys = {"LLM_PROVIDER", "OLLAMA_MODEL", "OLLAMA_BASE_URL", "MISTRAL_MODEL",
                "MISTRAL_API_KEY", "VLLM_MODEL", "VLLM_BASE_URL", "OPENAI_MODEL",
                "OPENAI_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_API_KEY"}
    if agent_env_path.exists():
        with open(agent_env_path, "r", encoding="utf-8") as f:
            for line in f:
                key = line.split("=", 1)[0].strip()
                if key not in llm_keys:
                    existing_lines.append(line)

    # Build new LLM lines
    from dotenv import dotenv_values
    web_env = dotenv_values(Path(__file__).parent / ".env")
    new_lines = [f"LLM_PROVIDER={provider}\n"]

    if provider == "ollama":
        base_url = web_env.get("OLLAMA_BASE_URL", "http://localhost:11434")
        new_lines.append(f"OLLAMA_MODEL={model}\n")
        new_lines.append(f"OLLAMA_BASE_URL={base_url}\n")
    elif provider == "mistral":
        api_key = web_env.get("MISTRAL_API_KEY", "")
        new_lines.append(f"MISTRAL_MODEL={model}\n")
        if api_key:
            new_lines.append(f"MISTRAL_API_KEY={api_key}\n")
    elif provider == "openai":
        api_key = web_env.get("OPENAI_API_KEY", "")
        new_lines.append(f"OPENAI_MODEL={model}\n")
        if api_key:
            new_lines.append(f"OPENAI_API_KEY={api_key}\n")
    elif provider == "anthropic":
        api_key = web_env.get("ANTHROPIC_API_KEY", "")
        new_lines.append(f"ANTHROPIC_MODEL={model}\n")
        if api_key:
            new_lines.append(f"ANTHROPIC_API_KEY={api_key}\n")

    with open(agent_env_path, "w", encoding="utf-8") as f:
        f.writelines(existing_lines)
        f.writelines(new_lines)

    return {"ok": True, "provider": provider, "model": model}


@app.get("/api/history")
async def get_history(
    agent_id: str = Query(..., description="ID del agente"),
    session_id: Optional[str] = Query(None, description="ID de sesión")
):
    """Obtiene el historial de consultas de un agente para una sesión"""
    history = runner.get_agent_history(agent_id, session_id)
    return {"history": history}


@app.get("/api/agents", response_model=list[AgentResponse])
async def list_agents(request: Request, mode: Optional[str] = Query(None)):
    """Lista todos los agentes disponibles (filtered by visibility, mode, and role)"""
    agents = runner.discover_agents()

    # Determine user role and username from session
    token = _get_token(request)
    session = get_session(token) if token else None
    user_role = session["role"] if session else "user"
    username = session["username"] if session else ""

    # Filter agents based on visibility level and allowed_users
    agents = [a for a in agents if _can_user_see_agent(a.id, username, user_role)]

    return [
        AgentResponse(
            id=a.id,
            name=a.name,
            agent_type=a.agent_type,
            description=a.description,
            welcome_message=a.welcome_message,
            example_queries=a.example_queries,
            rag_approach=a.rag_approach,
            show_history=a.show_history,
            show_description=a.show_description,
            transparency_level=a.transparency_level,
            transparency_type=a.transparency_type,
            prompt_level=a.prompt_level,
            decision_trace=a.decision_trace
        )
        for a in agents
    ]


@app.get("/api/agents/visibility")
async def get_agents_visibility(session: dict = Depends(require_role("superuser"))):
    """Get visibility config of all agents (superuser only)."""
    all_agents = runner.discover_agents()
    vis = _load_visibility()
    return [
        {
            "id": a.id,
            "name": a.name,
            "level": vis.get(a.id, {}).get("level", "restricted") if isinstance(vis.get(a.id), dict) else "restricted",
            "allowed_users": vis.get(a.id, {}).get("allowed_users", []) if isinstance(vis.get(a.id), dict) else [],
            "provider": _get_agent_provider(a.id),
            "is_local": _is_local_provider(a.id),
        }
        for a in all_agents
    ]


class AgentVisibilityBody(BaseModel):
    level: str = "restricted"
    allowed_users: list[str] = []


@app.put("/api/agents/{agent_id}/visibility")
async def set_agent_visibility(
    agent_id: str,
    body: AgentVisibilityBody,
    session: dict = Depends(require_role("superuser")),
):
    """Set visibility level and allowed users for an agent (superuser only)."""
    if body.level not in VISIBILITY_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid level. Must be one of: {', '.join(VISIBILITY_LEVELS)}")
    agent = runner.get_agent(agent_id)
    if not agent:
        all_agents = runner.discover_agents()
        if not any(a.id == agent_id for a in all_agents):
            raise HTTPException(status_code=404, detail="Agent not found")
    vis = _load_visibility()
    vis[agent_id] = {"level": body.level, "allowed_users": body.allowed_users}
    _save_visibility(vis)
    return {"ok": True, "agent_id": agent_id, "level": body.level, "allowed_users": body.allowed_users}


# ---------------------------------------------------------------------------
# Tool access management (superuser only)
# ---------------------------------------------------------------------------

@app.get("/api/tool-access")
async def get_tool_access(session: dict = Depends(require_role("superuser"))):
    """Get current tool access configuration."""
    return {"tool_access": TOOL_ACCESS}


@app.put("/api/tool-access")
async def set_tool_access(request: Request, session: dict = Depends(require_role("superuser"))):
    """Update tool access configuration (superuser only)."""
    from auth import save_tool_access
    body = await request.json()
    new_access = body.get("tool_access")
    if not isinstance(new_access, dict):
        raise HTTPException(status_code=400, detail="tool_access must be a dict")
    # Validate: values must be lists of known role strings
    valid_roles = {"public", "student", "admin_staff", "teaching_staff", "tester", "superuser"}
    for tool_id, roles in new_access.items():
        if not isinstance(roles, list):
            raise HTTPException(status_code=400, detail=f"Roles for {tool_id} must be a list")
        for r in roles:
            if r not in valid_roles:
                raise HTTPException(status_code=400, detail=f"Unknown role: {r}")
    # Update in-memory and persist
    TOOL_ACCESS.clear()
    TOOL_ACCESS.update(new_access)
    save_tool_access(new_access)
    return {"ok": True}


@app.get("/api/public-tools")
async def get_public_tools():
    """Return tools marked as public (no auth required)."""
    public = [tool_id for tool_id, roles in TOOL_ACCESS.items()
              if "public" in roles]
    return {"public_tools": public}


# ---------------------------------------------------------------------------
# Agent config editing (tester+ only)
# ---------------------------------------------------------------------------

@app.get("/api/agents/{agent_id}/config")
async def get_agent_config(agent_id: str, session: dict = Depends(require_role("tester"))):
    """Get config.json and prompts.json for an agent (tester+).

    Includes the caller's role so the frontend can render a role-appropriate
    editor (testers see basic settings + prompts + scope terms, superusers
    see everything).
    """
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_path = Path(agent.path)
    config, prompts = {}, {}
    config_path = agent_path / "config.json"
    prompts_path = agent_path / "prompts.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    if prompts_path.exists():
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)

    # Include current LLM provider info
    from dotenv import dotenv_values
    agent_env_path = agent_path / ".env"
    llm_provider = None
    llm_model = None
    if agent_env_path.exists():
        agent_env = dotenv_values(agent_env_path)
        llm_provider = agent_env.get("LLM_PROVIDER")
        if llm_provider:
            llm_provider = llm_provider.lower()
            if llm_provider == "ollama":
                llm_model = agent_env.get("OLLAMA_MODEL")
            elif llm_provider == "mistral":
                llm_model = agent_env.get("MISTRAL_MODEL")
            elif llm_provider == "openai":
                llm_model = agent_env.get("OPENAI_MODEL")
            elif llm_provider == "anthropic":
                llm_model = agent_env.get("ANTHROPIC_MODEL")
    if not llm_provider:
        web_env = dotenv_values(Path(__file__).parent / ".env")
        llm_provider = web_env.get("LLM_PROVIDER", "mistral").lower()
        if llm_provider == "ollama":
            llm_model = web_env.get("OLLAMA_MODEL")
        elif llm_provider == "mistral":
            llm_model = web_env.get("MISTRAL_MODEL")
        elif llm_provider == "openai":
            llm_model = web_env.get("OPENAI_MODEL")
        elif llm_provider == "anthropic":
            llm_model = web_env.get("ANTHROPIC_MODEL")

    return {"config": config, "prompts": prompts, "role": session.get("role", "tester"),
            "llm_provider": llm_provider, "llm_model": llm_model}


@app.put("/api/agents/{agent_id}/config")
async def set_agent_config(agent_id: str, request: Request, session: dict = Depends(require_role("tester"))):
    """Update config.json and/or prompts.json for an agent (tester+).

    Role-based write protection:
    - tester: can update basic settings, prompts, scope terms, examples
    - superuser: can update everything (including agent_id, universities, etc.)
    """
    from auth import max_role_level as _max_level
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    body = await request.json()
    agent_path = Path(agent.path)
    role_level = _max_level(session)

    if "config" in body and isinstance(body["config"], dict):
        config_path = agent_path / "config.json"
        current = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                current = json.load(f)

        new_config = body["config"]

        if role_level >= 4:  # superuser — full access
            merged = new_config
        else:  # tester — only immediate-effect settings (no restart needed)
            TESTER_FIELDS = {"prompt_level", "transparency_level", "reliability_cues", "humility_prompt", "humility_postprocessing", "decision_trace"}
            merged = {**current}
            for key in TESTER_FIELDS:
                if key in new_config:
                    merged[key] = new_config[key]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.write("\n")

    if "prompts" in body and isinstance(body["prompts"], dict) and role_level >= 4:
        with open(agent_path / "prompts.json", "w", encoding="utf-8") as f:
            json.dump(body["prompts"], f, indent=2, ensure_ascii=False)
            f.write("\n")

    return {"ok": True, "agent_id": agent_id}


# ---------------------------------------------------------------------------
# Data export & review endpoints (for tester verification)
# ---------------------------------------------------------------------------

@app.get("/api/agents/{agent_id}/export/researchers")
async def export_researchers(
    agent_id: str,
    university: Optional[str] = Query(None),
    session: dict = Depends(require_role("tester")),
):
    """Export researchers as Excel with a Review column for tester annotations."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")

    researchers_path = Path(agent_info.path) / "data" / "researchers.json"
    if not researchers_path.exists():
        raise HTTPException(status_code=404, detail="No researchers data found for this agent")

    with open(researchers_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    wb = Workbook()
    ws = wb.active
    ws.title = "Researchers"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    review_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Headers
    headers = ["University", "Researcher", "Paper count", "Topics", "Papers", "Review: Correct? (Yes/No)", "Review: Comments"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    # Data
    row = 2
    unis = [university.upper()] if university else sorted(data.keys())
    for uni in unis:
        if uni not in data:
            continue
        for researcher in data[uni]:
            papers_str = "; ".join([f"{p.get('title', '')} ({p.get('year', '')})" for p in researcher.get("papers", [])])
            topics_str = ", ".join(researcher.get("topics", []))

            ws.cell(row=row, column=1, value=uni).border = thin_border
            ws.cell(row=row, column=2, value=researcher.get("name", "")).border = thin_border
            ws.cell(row=row, column=3, value=researcher.get("paper_count", 0)).border = thin_border
            ws.cell(row=row, column=4, value=topics_str).border = thin_border
            ws.cell(row=row, column=4).alignment = Alignment(wrap_text=True)
            ws.cell(row=row, column=5, value=papers_str).border = thin_border
            ws.cell(row=row, column=5).alignment = Alignment(wrap_text=True)
            # Review columns (yellow background)
            for col in [6, 7]:
                cell = ws.cell(row=row, column=col, value="")
                cell.fill = review_fill
                cell.border = thin_border
            row += 1

    # Column widths
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 35
    ws.column_dimensions["E"].width = 50
    ws.column_dimensions["F"].width = 20
    ws.column_dimensions["G"].width = 35

    # Instructions sheet
    ws_inst = wb.create_sheet("Instructions")
    instructions = [
        "RESEARCHER DATA REVIEW",
        "",
        "Please review the researcher data for your university:",
        "",
        "1. Check each researcher in the list.",
        "2. In the 'Review: Correct?' column, write 'Yes' if the data is correct, or 'No' if there is an error.",
        "3. In the 'Review: Comments' column, describe any issues found:",
        "   - Researcher should not be listed (not affiliated with this university)",
        "   - Wrong topics assigned",
        "   - Missing papers",
        "   - Wrong paper attribution",
        "",
        "4. If researchers are MISSING from the list, add them at the bottom with:",
        "   - University code, Name, and in Comments write 'MISSING - should be included'",
        "",
        "5. Save the file and send it back to the TOMMI team.",
        "",
        f"Data source: OpenAlex (https://openalex.org/)",
        f"Agent: {agent_id}",
        f"Export date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    for i, line in enumerate(instructions, 1):
        cell = ws_inst.cell(row=i, column=1, value=line)
        if i == 1:
            cell.font = Font(bold=True, size=14)
    ws_inst.column_dimensions["A"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    uni_suffix = f"_{university.upper()}" if university else ""
    filename = f"{agent_id}_researchers{uni_suffix}_review.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/agents/{agent_id}/export/papers")
async def export_papers(
    agent_id: str,
    university: Optional[str] = Query(None),
    session: dict = Depends(require_role("tester")),
):
    """Export publications as Excel with a Review column for tester annotations."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")

    papers_path = Path(agent_info.path) / "data" / "papers.json"
    if not papers_path.exists():
        raise HTTPException(status_code=404, detail="No papers data found for this agent")

    with open(papers_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    universities = data.get("universities", data)

    wb = Workbook()
    ws = wb.active
    ws.title = "Publications"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    review_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    headers = ["University", "ID", "Title", "Authors", "Year", "DOI", "Type", "Cited by", "Review: Correct? (Yes/No)", "Review: Comments"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    row = 2
    unis = [university.upper()] if university else sorted(universities.keys())
    for uni in unis:
        uni_data = universities.get(uni, {})
        papers = uni_data.get("papers", []) if isinstance(uni_data, dict) else uni_data
        for paper in papers:
            authors_str = ", ".join([a.get("name", "") for a in paper.get("authors", [])])
            doi = paper.get("doi", "") or ""

            ws.cell(row=row, column=1, value=uni).border = thin_border
            ws.cell(row=row, column=2, value=paper.get("id", "")).border = thin_border
            ws.cell(row=row, column=3, value=paper.get("title", "")).border = thin_border
            ws.cell(row=row, column=3).alignment = Alignment(wrap_text=True)
            ws.cell(row=row, column=4, value=authors_str).border = thin_border
            ws.cell(row=row, column=4).alignment = Alignment(wrap_text=True)
            ws.cell(row=row, column=5, value=paper.get("publication_year", "")).border = thin_border
            ws.cell(row=row, column=6, value=doi).border = thin_border
            ws.cell(row=row, column=7, value=paper.get("type", "")).border = thin_border
            ws.cell(row=row, column=8, value=paper.get("cited_by_count", 0)).border = thin_border
            for col in [9, 10]:
                cell = ws.cell(row=row, column=col, value="")
                cell.fill = review_fill
                cell.border = thin_border
            row += 1

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 50
    ws.column_dimensions["D"].width = 35
    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 35
    ws.column_dimensions["G"].width = 12
    ws.column_dimensions["H"].width = 10
    ws.column_dimensions["I"].width = 20
    ws.column_dimensions["J"].width = 35

    # Instructions sheet
    ws_inst = wb.create_sheet("Instructions")
    instructions = [
        "PUBLICATION DATA REVIEW",
        "",
        "Please review the publications for your university:",
        "",
        "1. Check each publication in the list.",
        "2. In the 'Review: Correct?' column, write 'Yes' if correct, or 'No' if there is an error.",
        "3. In the 'Review: Comments' column, describe any issues:",
        "   - Paper should not be attributed to this university",
        "   - Wrong authors listed",
        "   - Wrong year or title",
        "   - Paper is a duplicate",
        "",
        "4. If publications are MISSING from the list, add them at the bottom with:",
        "   - University code, Title, Authors, Year, and in Comments write 'MISSING'",
        "",
        "5. Save the file and send it back to the TOMMI team.",
        "",
        f"Data source: OpenAlex (https://openalex.org/)",
        f"Agent: {agent_id}",
        f"Export date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    for i, line in enumerate(instructions, 1):
        cell = ws_inst.cell(row=i, column=1, value=line)
        if i == 1:
            cell.font = Font(bold=True, size=14)
    ws_inst.column_dimensions["A"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    uni_suffix = f"_{university.upper()}" if university else ""
    filename = f"{agent_id}_papers{uni_suffix}_review.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/agents/{agent_id}/export/projects")
async def export_projects(
    agent_id: str,
    university: Optional[str] = Query(None),
    session: dict = Depends(require_role("tester")),
):
    """Export projects as Excel with a Review column for tester annotations."""
    import io, re
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")

    project_dir = Path(agent_info.path) / "data" / "project_docs"
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="No project data found for this agent")

    # Parse project markdown files
    projects = []
    for md_file in sorted(project_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        title_match = re.search(r"^# (.+)", content, re.MULTILINE)
        grant_match = re.search(r"\*\*Grant ID:\*\*\s*(\S+)", content)
        programme_match = re.search(r"\*\*Programme:\*\*\s*(.+)", content)
        period_match = re.search(r"\*\*Period:\*\*\s*(.+)", content)
        status_match = re.search(r"\*\*Status:\*\*\s*(\S+)", content)
        keywords_match = re.search(r"\*\*Keywords:\*\*\s*(.+)", content)

        # Extract participants
        participants = []
        in_participants = False
        for line in content.split("\n"):
            if line.strip().startswith("## Participants"):
                in_participants = True
                continue
            if in_participants:
                if line.strip().startswith("## ") or line.strip().startswith("# "):
                    break
                if line.strip().startswith("- "):
                    participants.append(line.strip()[2:])

        project = {
            "file": md_file.name,
            "title": title_match.group(1).split(":")[1].strip() if title_match and ":" in title_match.group(1) else (title_match.group(1) if title_match else md_file.stem),
            "grant_id": grant_match.group(1) if grant_match else "",
            "programme": programme_match.group(1).strip() if programme_match else "",
            "period": period_match.group(1).strip() if period_match else "",
            "status": status_match.group(1).strip() if status_match else "",
            "keywords": keywords_match.group(1).strip() if keywords_match else "",
            "participants": participants,
        }

        # Filter by university if specified
        if university:
            # Check config for university full names
            config_path = Path(agent_info.path) / "config.json"
            uni_names = {}
            if config_path.exists():
                with open(config_path) as f:
                    cfg = json.load(f)
                uni_names = {k: v.get("name", "") for k, v in cfg.get("universities", {}).items()}
            uni_full = uni_names.get(university.upper(), university)
            if not any(uni_full.lower() in p.lower() or university.upper() in p.upper() for p in participants):
                continue

        projects.append(project)

    wb = Workbook()
    ws = wb.active
    ws.title = "Projects"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    review_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    headers = ["Grant ID", "Title", "Programme", "Period", "Status", "Keywords", "Participants", "Review: Correct? (Yes/No)", "Review: Comments"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for r, proj in enumerate(projects, 2):
        ws.cell(row=r, column=1, value=proj["grant_id"]).border = thin_border
        ws.cell(row=r, column=2, value=proj["title"]).border = thin_border
        ws.cell(row=r, column=2).alignment = Alignment(wrap_text=True)
        ws.cell(row=r, column=3, value=proj["programme"]).border = thin_border
        ws.cell(row=r, column=3).alignment = Alignment(wrap_text=True)
        ws.cell(row=r, column=4, value=proj["period"]).border = thin_border
        ws.cell(row=r, column=5, value=proj["status"]).border = thin_border
        ws.cell(row=r, column=6, value=proj["keywords"]).border = thin_border
        ws.cell(row=r, column=6).alignment = Alignment(wrap_text=True)
        ws.cell(row=r, column=7, value="\n".join(proj["participants"])).border = thin_border
        ws.cell(row=r, column=7).alignment = Alignment(wrap_text=True)
        for col in [8, 9]:
            cell = ws.cell(row=r, column=col, value="")
            cell.fill = review_fill
            cell.border = thin_border

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 30
    ws.column_dimensions["G"].width = 40
    ws.column_dimensions["H"].width = 20
    ws.column_dimensions["I"].width = 35

    ws_inst = wb.create_sheet("Instructions")
    instructions = [
        "PROJECT DATA REVIEW",
        "",
        "Please review the project data:",
        "",
        "1. Check each project in the list.",
        "2. In the 'Review: Correct?' column, write 'Yes' if correct, or 'No' if there is an error.",
        "3. In the 'Review: Comments' column, describe any issues:",
        "   - Your university is not actually a participant",
        "   - Wrong project details (title, period, programme)",
        "   - Missing participants",
        "",
        "4. If projects are MISSING from the list, add them at the bottom with:",
        "   - Grant ID, Title, and in Comments write 'MISSING'",
        "",
        "5. Save the file and send it back to the TOMMI team.",
        "",
        f"Data source: CORDIS (https://cordis.europa.eu/)",
        f"Agent: {agent_id}",
        f"Export date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    for i, line in enumerate(instructions, 1):
        cell = ws_inst.cell(row=i, column=1, value=line)
        if i == 1:
            cell.font = Font(bold=True, size=14)
    ws_inst.column_dimensions["A"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    uni_suffix = f"_{university.upper()}" if university else ""
    filename = f"{agent_id}_projects{uni_suffix}_review.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/agents/{agent_id}/reset-logs")
async def reset_agent_logs(agent_id: str, session: dict = Depends(require_role("superuser"))):
    """
    Archive and reset all logs for an agent (superuser only).
    Feedback logs and audit logs are renamed with a timestamp suffix.
    """
    from datetime import datetime as dt
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    archived = []

    # Feedback logs in web/logs/
    for suffix in ["_feedback_tester.jsonl", "_feedback_user.jsonl", "_conversations.jsonl", "_conversations.log"]:
        log_path = LOGS_DIR / f"{agent_id}{suffix}"
        if log_path.exists() and log_path.stat().st_size > 0:
            ext = suffix.rsplit('.', 1)[-1]
            archive_name = f"{agent_id}{suffix.rsplit('.', 1)[0]}_{timestamp}.{ext}"
            archive_path = LOGS_DIR / archive_name
            log_path.rename(archive_path)
            archived.append(archive_name)

    # Reset cached logger so a new file handler is created for the fresh log
    if agent_id in _agent_loggers:
        logger = _agent_loggers.pop(agent_id)
        for h in logger.handlers[:]:
            h.close()
            logger.removeHandler(h)

    # Audit log in agents/{agent_id}/data/
    agent_info = runner.get_agent(agent_id)
    if agent_info:
        audit_path = Path(agent_info.path) / "data" / "audit_log.jsonl"
        if audit_path.exists() and audit_path.stat().st_size > 0:
            archive_name = f"audit_log_{timestamp}.jsonl"
            archive_path = audit_path.parent / archive_name
            audit_path.rename(archive_path)
            archived.append(f"agents/{agent_id}/data/{archive_name}")

    if not archived:
        return {"ok": True, "message": "No logs to reset", "archived": []}

    return {"ok": True, "message": f"Archived {len(archived)} log file(s)", "archived": archived}


# ---------------------------------------------------------------------------
# Log Analytics API (superuser only)
# ---------------------------------------------------------------------------

@app.get("/api/logs/summary")
async def logs_summary(
    period: str = "day",
    start: str | None = None,
    end: str | None = None,
    session: dict = Depends(require_role("superuser")),
):
    """
    Return aggregated request/visitor stats across all agents.
    period: 'hour', 'day', 'week' (ignored when start/end are given).
    start/end: ISO date(time) strings for a custom interval.
    """
    from datetime import datetime as dt, timedelta

    now = dt.now()
    if start and end:
        try:
            t_start = dt.fromisoformat(start)
            t_end = dt.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601.")
    else:
        if period == "hour":
            t_start = now - timedelta(hours=1)
        elif period == "3days":
            t_start = now - timedelta(days=3)
        elif period == "week":
            t_start = now - timedelta(weeks=1)
        else:
            t_start = now - timedelta(days=1)
        t_end = now

    # Scan all JSONL conversation logs
    totals = {"requests": 0, "sessions": set(), "users": set()}
    per_agent: dict[str, dict] = {}

    for log_file in sorted(LOGS_DIR.glob("*_conversations.jsonl")):
        agent_id = log_file.name.rsplit("_conversations.jsonl", 1)[0]
        agent_stats = {"requests": 0, "sessions": set(), "users": set()}

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    try:
                        ts = dt.fromisoformat(entry["timestamp"])
                    except (KeyError, ValueError):
                        continue
                    if ts < t_start or ts > t_end:
                        continue

                    agent_stats["requests"] += 1
                    if entry.get("session_id"):
                        agent_stats["sessions"].add(entry["session_id"])
                    if entry.get("user_id"):
                        agent_stats["users"].add(entry["user_id"])
        except Exception:
            continue

        if agent_stats["requests"] > 0:
            per_agent[agent_id] = {
                "requests": agent_stats["requests"],
                "sessions": len(agent_stats["sessions"]),
                "unique_users": len(agent_stats["users"]),
            }
            totals["requests"] += agent_stats["requests"]
            totals["sessions"] |= agent_stats["sessions"]
            totals["users"] |= agent_stats["users"]

    return {
        "period": period if not (start and end) else "custom",
        "start": t_start.isoformat(),
        "end": t_end.isoformat(),
        "totals": {
            "requests": totals["requests"],
            "sessions": len(totals["sessions"]),
            "unique_users": len(totals["users"]),
        },
        "per_agent": per_agent,
    }


@app.get("/api/logs/files")
async def list_log_files(session: dict = Depends(require_role("superuser"))):
    """List all log files with size and modification time."""
    files = []
    for f in sorted(LOGS_DIR.iterdir()):
        if f.is_file() and f.name != ".DS_Store":
            stat = f.stat()
            files.append({
                "name": f.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return files


@app.get("/api/logs/content")
async def get_log_content(filename: str, session: dict = Depends(require_role("superuser"))):
    """Return parsed content of a log file (superuser only)."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    target = LOGS_DIR / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    entries = []
    try:
        with open(target, "r", encoding="utf-8") as f:
            if filename.endswith(".jsonl"):
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        entries.append({"_raw": line})
            elif filename.endswith(".log"):
                # .log files contain pretty-printed JSON blocks separated by blank lines
                buf = []
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        buf.append(stripped)
                    else:
                        if buf:
                            try:
                                entries.append(json.loads(" ".join(buf)))
                            except json.JSONDecodeError:
                                entries.append({"_raw": "\n".join(buf)})
                            buf = []
                if buf:
                    try:
                        entries.append(json.loads(" ".join(buf)))
                    except json.JSONDecodeError:
                        entries.append({"_raw": "\n".join(buf)})
            else:
                text = f.read()
                return {"filename": filename, "format": "text", "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")

    return {"filename": filename, "format": "entries", "count": len(entries), "entries": entries}


@app.delete("/api/logs/{filename}")
async def delete_log_file(filename: str, session: dict = Depends(require_role("superuser"))):
    """Delete a specific log file (superuser only)."""
    # Sanitize: prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    target = LOGS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # If it's an active conversation log, also clear the cached logger
    for agent_id in list(_agent_loggers.keys()):
        if filename == f"{agent_id}_conversations.log":
            logger = _agent_loggers.pop(agent_id)
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)
            break

    target.unlink()
    return {"ok": True, "message": f"Deleted {filename}"}


@app.post("/api/agents/{agent_id}/init")
async def init_agent(agent_id: str):
    """
    Initialize an agent, forcing ChromaDB indexing for RAG agents.
    Call this when selecting a RAG agent to ensure the database is ready.
    """
    result = runner.init_agent(agent_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result


@app.get("/api/agents/{agent_id}/init-stream")
async def init_agent_stream(agent_id: str):
    """
    Initialize a RAG agent with SSE progress reporting.
    Streams progress events during document indexing.
    """
    import asyncio
    import threading

    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        err = format_error(AGENT_NOT_FOUND, agent_id=agent_id)
        raise HTTPException(status_code=404, detail=f"Error {err['error_code']}: {err['error']}")

    async def event_generator():
        loop = asyncio.get_event_loop()
        aq = asyncio.Queue()

        def progress_callback(current, total, filename):
            loop.call_soon_threadsafe(aq.put_nowait, {
                "event": "progress",
                "current": current,
                "total": total,
                "filename": filename,
            })

        def run_init():
            try:
                result = runner.init_agent_with_callback(agent_id, progress_callback)
                loop.call_soon_threadsafe(aq.put_nowait, {"event": "done", "result": result})
            except Exception as e:
                loop.call_soon_threadsafe(aq.put_nowait, {
                    "event": "done",
                    "result": {"success": False, "error": str(e)},
                })

        thread = threading.Thread(target=run_init, daemon=True)
        thread.start()

        while True:
            event = await aq.get()
            if event["event"] == "progress":
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"
            elif event["event"] == "done":
                yield f"event: done\ndata: {json.dumps(event['result'])}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/agents/{agent_id}/reindex")
async def reindex_agent(agent_id: str):
    """
    Force reindex of a RAG agent's documents.
    Use this after adding, removing, or modifying documents in data/docs/.
    """
    result = runner.reindex_agent(agent_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result


@app.get("/api/agents/{agent_id}/token-usage")
async def get_token_usage(agent_id: str):
    """
    Get token usage statistics for an agent.
    Returns prompt tokens, completion tokens, and total tokens for the session.
    """
    result = runner.get_agent_token_usage(agent_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not loaded or doesn't support token tracking")
    return result


@app.post("/api/agents/{agent_id}/reset-token-usage")
async def reset_token_usage(agent_id: str):
    """
    Reset token usage counters for an agent.
    """
    result = runner.reset_agent_token_usage(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not loaded or doesn't support token tracking")
    return {"success": True, "message": "Token usage counters reset"}


def _disable_web_search_for_user(agent_id: str, session: dict | None) -> tuple:
    """
    If the user has role 'user', temporarily disable web search on the agent
    to prevent data from leaving UMA infrastructure.
    Returns (agent_instance, original_web_search_config) for later restoration.
    """
    if not session or session["role"] != "user":
        return None, None
    agent_instance = runner._load_agent_module(agent_id)
    if not agent_instance:
        return None, None
    config = getattr(agent_instance, '_config', None)
    if not config or "web_search" not in config:
        return None, None
    original = config["web_search"].copy()
    config["web_search"]["google_api_key"] = ""
    config["web_search"]["google_cx"] = ""
    return agent_instance, original


def _restore_web_search(agent_instance, original_config):
    """Restore web search config after request."""
    if agent_instance and original_config:
        agent_instance._config["web_search"] = original_config


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    """Envía un mensaje a un agente y obtiene respuesta completa"""
    # Block users from accessing cloud-provider agents
    token = _get_token(http_request)
    session = get_session(token) if token else None
    if session and session["role"] == "user" and not _is_local_provider(request.agent_id):
        raise HTTPException(status_code=403, detail="Access restricted: this agent uses a cloud LLM provider")
    # Disable web search for end users (data sovereignty)
    agent_inst, orig_ws = _disable_web_search_for_user(request.agent_id, session)
    try:
        result = await runner.run_query(
            agent_id=request.agent_id,
            message=request.message,
            session_id=request.session_id  # None en primera llamada
        )
        return ChatResponse(response=result.response, session_id=result.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _restore_web_search(agent_inst, orig_ws)


@app.get("/api/chat/stream")
async def chat_stream(
    request: Request,
    agent_id: str = Query(..., description="ID del agente"),
    message: str = Query(..., description="Mensaje a enviar"),
    session_id: Optional[str] = Query(None, description="ID de sesión (opcional, se crea automáticamente)"),
    model: Optional[str] = Query(None, description="LLM model override (client preference)"),
    transparency: Optional[str] = Query(None, description="Transparency level override (client preference)"),
    prompt_level: Optional[str] = Query(None, description="Prompt level override (client preference)"),
    study_query_number: Optional[int] = Query(None, description="Study query number (1-8) for study participants"),
):
    """Envía un mensaje y hace streaming de la respuesta via SSE"""
    # Block users from accessing cloud-provider agents
    token = _get_token(request)
    session = get_session(token) if token else None
    if session and session["role"] == "user" and not _is_local_provider(agent_id):
        raise HTTPException(status_code=403, detail="Access restricted: this agent uses a cloud LLM provider")
    # Disable web search for end users (data sovereignty)
    agent_inst, orig_ws = _disable_web_search_for_user(agent_id, session)

    agent = runner.get_agent(agent_id)
    if not agent:
        err = format_error(AGENT_NOT_FOUND, agent_id=agent_id)
        raise HTTPException(status_code=404, detail=f"Error {err['error_code']}: {err['error']}")

    client_ip = request.client.host if request.client else "unknown"

    async def event_generator():
        new_session_id = None
        full_response = ""

        try:
            # Build study_info if this is a study participant query
            _study_info = None
            if session and study_query_number:
                from auth import get_study_info as _get_si
                _si = _get_si(session["username"])
                if _si:
                    _study_info = {**_si, "query_number": study_query_number}

            async for event_type, content, returned_session_id in runner.run_query_stream(
                agent_id=agent_id,
                message=message,
                session_id=session_id,  # None en primera llamada
                model_override=model,
                transparency_override=transparency,
                prompt_level_override=prompt_level,
                username=session["username"] if session else None,
                role=session["role"] if session else None,
                study_info=_study_info,
            ):
                # Enviar session_id cuando lo recibimos (primera iteración)
                if returned_session_id and not new_session_id:
                    new_session_id = returned_session_id
                    yield f"event: session\ndata: {new_session_id}\n\n"

                if event_type == "status":
                    # Enviar evento de estado
                    yield f"event: status\ndata: {content}\n\n"
                elif event_type == "badge":
                    # Enviar badge de fiabilidad como evento separado (no se acumula en el texto)
                    escaped = content.replace("\n", "\\n")
                    yield f"event: badge\ndata: {escaped}\n\n"
                elif event_type == "trace":
                    # Decision trace — raw HTML, bypasses markdown
                    escaped = content.replace("\n", "\\n")
                    yield f"event: trace\ndata: {escaped}\n\n"
                elif event_type == "editor":
                    # Raw HTML editor widget — sent as-is, bypasses markdown
                    escaped = content.replace("\n", "\\n")
                    yield f"event: editor\ndata: {escaped}\n\n"
                elif event_type == "procedural_banner":
                    # Procedural banner — separate event, persists through replace events
                    escaped = content.replace("\n", "\\n")
                    yield f"event: procedural_banner\ndata: {escaped}\n\n"
                elif event_type == "replace":
                    # Replace full response (e.g. after stripping map links)
                    full_response = content
                    escaped = content.replace("\n", "\\n")
                    yield f"event: replace\ndata: {escaped}\n\n"
                else:
                    # Enviar contenido
                    full_response += content
                    escaped = content.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"

            # Registrar la conversación en el log
            log_conversation(
                client_ip=client_ip,
                agent_id=agent_id,
                agent_name=agent.name,
                question=message,
                response=full_response,
                session_id=new_session_id or session_id or "",
                transparency_level=transparency,
                username=session["username"] if session else None,
            )

            yield "event: done\ndata: complete\n\n"
        except Exception as e:
            err = format_error(SERVER_STREAMING_ERROR, details=str(e))
            import json
            yield f"event: error\ndata: {json.dumps(err)}\n\n"
        finally:
            _restore_web_search(agent_inst, orig_ws)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Topic Map Endpoint (for agents with search_papers_by_topic)
# ============================================================================

@app.get("/api/agents/{agent_id}/publications-search")
async def agent_publications_search(agent_id: str, year: Optional[int] = Query(None)):
    """Return all papers grouped by university as JSON data."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_all_papers_by_university"):
        raise HTTPException(status_code=400, detail="Agent does not support publications search")
    results = agent_instance.get_all_papers_by_university(year=year)
    title = f"Publications ({year})" if year else "All Publications"
    return {"topic": title, "universities": results}


@app.get("/api/agents/{agent_id}/publications-map")
async def agent_publications_map(agent_id: str, year: Optional[int] = Query(None)):
    """Returns an interactive Leaflet map showing publications per university, optionally filtered by year."""
    from fastapi.responses import HTMLResponse
    import json as json_module

    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_all_papers_by_university"):
        raise HTTPException(status_code=400, detail="Agent does not support publications search")

    results = agent_instance.get_all_papers_by_university(year=year)
    results_json = json_module.dumps(results)
    title = f"Publications ({year})" if year else "All Publications"

    if hasattr(agent_instance, "build_topic_map_html"):
        html = agent_instance.build_topic_map_html(results_json, title)
        return HTMLResponse(content=html)

    return HTMLResponse(content=f"<html><body><h1>All Publications</h1><pre>{results_json}</pre></body></html>")


@app.get("/api/agents/{agent_id}/collaboration-search")
async def agent_collaboration_search(agent_id: str, topic: str = Query(None),
                                     year: int = Query(None)):
    """Return collaboration data (universities + connections) as JSON."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_collaboration_map_data"):
        raise HTTPException(status_code=400, detail="Agent does not support collaboration search")
    return agent_instance.get_collaboration_map_data(topic=topic, year=year)


@app.get("/api/agents/{agent_id}/topic-search")
async def agent_topic_search(agent_id: str, topic: str = Query(...)):
    """Search papers by topic across universities. Returns JSON data."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "search_papers_by_topic"):
        raise HTTPException(status_code=400, detail="Agent does not support topic search")
    results = agent_instance.search_papers_by_topic(topic)
    return {"topic": topic, "universities": results}


@app.get("/api/agents/{agent_id}/topic-map")
async def agent_topic_map(agent_id: str, topic: str = Query(...)):
    """Returns an interactive Leaflet map for a topic across UNINOVIS universities."""
    from fastapi.responses import HTMLResponse
    import json as json_module

    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "search_papers_by_topic"):
        raise HTTPException(status_code=400, detail="Agent does not support topic search")

    results = agent_instance.search_papers_by_topic(topic)
    results_json = json_module.dumps(results)
    topic_escaped = topic.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

    # Use the agent's build_topic_map_html if available
    if hasattr(agent_instance, "build_topic_map_html"):
        html = agent_instance.build_topic_map_html(results_json, topic_escaped)
        return HTMLResponse(content=html)

    # Fallback: simple response
    return HTMLResponse(content=f"<html><body><h1>Topic map for {topic_escaped}</h1><pre>{results_json}</pre></body></html>")


@app.get("/api/agents/{agent_id}/projects-search")
async def agent_projects_search(agent_id: str, year: Optional[int] = Query(None)):
    """Return all projects grouped by university as JSON data, optionally filtered by year."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_all_projects_by_university"):
        raise HTTPException(status_code=400, detail="Agent does not support projects search")
    results = agent_instance.get_all_projects_by_university(year=year)
    return {"topic": "All Projects", "universities": results}


@app.get("/api/agents/{agent_id}/project-topic-search")
async def agent_project_topic_search(agent_id: str, topic: str = Query(...),
                                     year: Optional[int] = Query(None)):
    """Search projects by topic across universities, optionally filtered by year. Returns JSON data."""
    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "search_projects_by_topic"):
        raise HTTPException(status_code=400, detail="Agent does not support project topic search")
    results = agent_instance.search_projects_by_topic(topic, year=year)
    return {"topic": topic, "universities": results}


@app.get("/api/agents/{agent_id}/projects-map")
async def agent_projects_map(agent_id: str, year: Optional[int] = Query(None)):
    """Returns an interactive Leaflet map showing projects per university, optionally filtered by year."""
    from fastapi.responses import HTMLResponse
    import json as json_module

    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "get_all_projects_by_university"):
        raise HTTPException(status_code=400, detail="Agent does not support projects search")

    results = agent_instance.get_all_projects_by_university(year=year)
    results_json = json_module.dumps(results)
    title = f"Projects ({year})" if year else "All Projects"

    if hasattr(agent_instance, "build_project_map_html"):
        html = agent_instance.build_project_map_html(results_json, title)
        return HTMLResponse(content=html)

    return HTMLResponse(content=f"<html><body><h1>{title}</h1><pre>{results_json}</pre></body></html>")


@app.get("/api/agents/{agent_id}/project-topic-map")
async def agent_project_topic_map(agent_id: str, topic: str = Query(...),
                                  year: Optional[int] = Query(None)):
    """Returns an interactive Leaflet map for projects on a topic, optionally filtered by year."""
    from fastapi.responses import HTMLResponse
    import json as json_module

    agent_instance = runner.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not loaded")
    if not hasattr(agent_instance, "search_projects_by_topic"):
        raise HTTPException(status_code=400, detail="Agent does not support project topic search")

    results = agent_instance.search_projects_by_topic(topic, year=year)
    results_json = json_module.dumps(results)
    topic_escaped = topic.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    title = f"{topic_escaped} ({year})" if year else topic_escaped

    if hasattr(agent_instance, "build_project_map_html"):
        html = agent_instance.build_project_map_html(results_json, title)
        return HTMLResponse(content=html)

    return HTMLResponse(content=f"<html><body><h1>Projects on {title}</h1><pre>{results_json}</pre></body></html>")


# ============================================================================
# Algoria Map — Agreements map endpoint
# ============================================================================

@app.get("/api/agents/{agent_id}/agreements-config")
async def agent_agreements_config(agent_id: str):
    """Returns public config (language, translations) for the agreements map page."""
    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")
    config_path = Path(agent_info.path) / "config.json"
    if not config_path.exists():
        return {}
    import json as json_module
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json_module.load(f)
    # Only expose language and translations (no sensitive data)
    return {"language": cfg.get("language", "en"), "translations": cfg.get("translations", {})}


@app.get("/api/agents/{agent_id}/agreements-search")
async def agent_agreements_search(
    agent_id: str,
    continent: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    faculty: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    language_level: Optional[str] = Query(None),
    mobility_program: Optional[str] = Query(None),
    degree_level: Optional[str] = Query(None),
    university: Optional[str] = Query(None),
    uninovis: Optional[bool] = Query(None),
):
    """Returns JSON data for the agreements map (markers, center, zoom)."""
    agent_instance = runner.get_agent_instance(agent_id) or runner._load_agent_module(agent_id)
    if not agent_instance:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not hasattr(agent_instance, "get_map_data"):
        raise HTTPException(status_code=400, detail="Agent does not support agreements search")

    filters = {}
    if continent: filters["continent"] = continent
    if country: filters["country"] = country
    if faculty: filters["faculty"] = faculty
    if language: filters["language"] = language
    if language_level: filters["language_level"] = language_level
    if mobility_program: filters["mobility_program"] = mobility_program
    if degree_level: filters["degree_level"] = degree_level
    if university: filters["university"] = university
    if uninovis: filters["uninovis"] = True

    return agent_instance.get_map_data(filters)


# ============================================================================
# PDF Document Endpoint
# ============================================================================

@app.get("/api/agents/{agent_id}/pdf-list")
async def agent_pdf_list(agent_id: str):
    """List available PDFs for an agent."""
    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")
    docs_dir = Path(agent_info.path) / "data" / "docs"
    if not docs_dir.exists():
        return {"pdfs": []}
    pdfs = [f.stem for f in docs_dir.glob("*.pdf")]
    return {"pdfs": pdfs}


@app.get("/api/agents/{agent_id}/pdf/{filename}")
async def agent_pdf(agent_id: str, filename: str):
    """Serve a PDF from an agent's data/docs/ directory."""
    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Security: only allow .pdf files, no path traversal
    if not filename.endswith(".pdf") or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    pdf_path = Path(agent_info.path) / "data" / "docs" / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


# ============================================================================
# Agent Quick Guide Endpoint
# ============================================================================

@app.head("/api/agents/{agent_id}/quickguide")
@app.get("/api/agents/{agent_id}/quickguide")
async def agent_quickguide(agent_id: str):
    """Serve the quick guide HTML for an agent (if available)."""
    agent_info = runner.get_agent(agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Look for agent-specific quickguide, then fall back to the legacy name
    agent_dir = Path(agent_info.path)
    guide_path = None
    for candidate in sorted(agent_dir.glob("*quickguide*.html")):
        guide_path = candidate
        break
    if not guide_path or not guide_path.exists():
        raise HTTPException(status_code=404, detail="Quick guide not found")

    return FileResponse(guide_path, media_type="text/html")


# ============================================================================
# Agent Creation Endpoints
# ============================================================================

@app.get("/create-agent")
async def create_agent_page():
    """Serve the create agent page"""
    return FileResponse(SCRIPT_DIR / "static" / "create_agent.html")


@app.get("/api/prompt-templates")
async def get_prompt_templates(agent_type: str = Query(...)):
    """List available prompt templates for an agent type"""
    # Import from crear_agente
    apps_dir = SCRIPT_DIR.parent / "apps"
    sys.path.insert(0, str(apps_dir))

    try:
        from crear_agente import list_prompt_templates
        templates = list_prompt_templates(agent_type)
        return [{"name": name, "path": path} for name, path in templates]
    except Exception as e:
        return []


@app.get("/api/prompt-template")
async def get_prompt_template(path: str = Query(...)):
    """Get content of a prompt template"""
    try:
        # Security: ensure path is within prompts directory
        prompts_dir = SCRIPT_DIR.parent / "prompts"
        template_path = Path(path).resolve()

        if not str(template_path).startswith(str(prompts_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import Form, UploadFile, File
from typing import List, Optional

@app.post("/api/create-agent")
async def create_agent(
    agent_type: str = Form(...),
    agent_id: str = Form(...),
    agent_name: str = Form(...),
    description: str = Form(""),
    welcome_message: str = Form(""),
    examples: str = Form("[]"),  # JSON array
    system_prompt: str = Form(...),
    llm_provider: str = Form("default"),
    mistral_model: str = Form("mistral-large-latest"),
    mistral_api_key: str = Form(""),
    ollama_url: str = Form("http://localhost:11434"),
    ollama_model: str = Form(""),
    context_preserving: bool = Form(True),  # RAG chunking approach
    reliability_green_max_llm: int = Form(20),
    reliability_red_min_llm: int = Form(50),
    database_schema: str = Form(""),
    data_file: Optional[UploadFile] = File(None),
    schema_file: Optional[UploadFile] = File(None),
    rag_documents: List[UploadFile] = File(None),
    rag_vectorless_documents: List[UploadFile] = File(None),
    rag_metadata_documents: List[UploadFile] = File(None),
    metadata_file: Optional[UploadFile] = File(None),
    database_file: Optional[UploadFile] = File(None),
):
    """Create a new agent"""
    import json as json_module
    import shutil

    try:
        # Parse examples
        example_list = json_module.loads(examples) if examples else []

        # Validate agent_id
        if not agent_id or " " in agent_id or not agent_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(status_code=400, detail="Invalid agent ID. Use only lowercase letters, numbers, hyphens or underscores.")

        # Check if agent already exists
        output_dir = AGENTS_PATH / agent_id
        if output_dir.exists():
            raise HTTPException(status_code=400, detail=f"Agent '{agent_id}' already exists")

        # Import crear_agente functions
        apps_dir = SCRIPT_DIR.parent / "apps"
        sys.path.insert(0, str(apps_dir))
        from crear_agente import (
            create_agent_structure,
            get_agents_dir
        )

        # Prepare configuration
        config = {
            "agent_type": agent_type,
            "agent_id": agent_id,
            "output_dir": str(output_dir),
            "agent_name": agent_name,
            "description": description or f"{agent_name} Assistant",
            "welcome": welcome_message or f"Hello! I'm {agent_name}. How can I help you?",
            "examples": example_list,
            "system_prompt": system_prompt,
            "llm_provider": llm_provider,
            "model": mistral_model if llm_provider == "mistral" else ollama_model,
            "api_key": mistral_api_key if llm_provider == "mistral" else "",
            "ollama_url": ollama_url if llm_provider == "ollama" else "",
            "ollama_model": ollama_model if llm_provider == "ollama" else "",
            "rag_approach": "context_preserving" if context_preserving else "basic",
            "reliability_green_max_llm": reliability_green_max_llm,
            "reliability_red_min_llm": reliability_red_min_llm,
        }

        # Create agent structure
        create_agent_structure(config)

        # Create data directory
        data_dir = output_dir / "data"
        data_dir.mkdir(exist_ok=True)

        # Handle data based on agent type
        if agent_type == "oneshot" and data_file and data_file.filename:
            # Save uploaded data.md file
            content = await data_file.read()
            with open(data_dir / "data.md", "wb") as f:
                f.write(content)

        elif agent_type == "rag" and rag_documents:
            # Create docs subfolder for RAG
            docs_dir = data_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            # Save uploaded documents (from folder selection)
            for doc in rag_documents:
                if doc.filename:
                    # Handle folder structure - get just the filename
                    filename = Path(doc.filename).name
                    # Skip hidden files and non-document files
                    if filename.startswith('.'):
                        continue
                    ext = Path(filename).suffix.lower()
                    if ext in ['.pdf', '.txt', '.md', '.docx', '.doc']:
                        doc_path = docs_dir / filename
                        content = await doc.read()
                        with open(doc_path, "wb") as f:
                            f.write(content)

        elif agent_type == "rag_vectorless" and rag_vectorless_documents:
            # Create docs subfolder for RAG Vectorless
            docs_dir = data_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            for doc in rag_vectorless_documents:
                if doc.filename:
                    filename = Path(doc.filename).name
                    if filename.startswith('.'):
                        continue
                    ext = Path(filename).suffix.lower()
                    if ext in ['.pdf', '.txt', '.md', '.docx', '.doc']:
                        doc_path = docs_dir / filename
                        content = await doc.read()
                        with open(doc_path, "wb") as f:
                            f.write(content)

        elif agent_type == "rag_metadata":
            # Create docs subfolder for RAG+Metadata
            docs_dir = data_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            # Save uploaded documents (from folder selection)
            if rag_metadata_documents:
                for doc in rag_metadata_documents:
                    if doc.filename:
                        filename = Path(doc.filename).name
                        if filename.startswith('.'):
                            continue
                        ext = Path(filename).suffix.lower()
                        if ext in ['.pdf', '.txt', '.md', '.docx', '.doc']:
                            doc_path = docs_dir / filename
                            content = await doc.read()
                            with open(doc_path, "wb") as f:
                                f.write(content)
            # Save metadata file if provided
            if metadata_file and metadata_file.filename:
                content = await metadata_file.read()
                with open(data_dir / "metadata.json", "wb") as f:
                    f.write(content)

        elif agent_type == "consultabd_sql":
            # Handle database schema - from file or textarea
            if schema_file and schema_file.filename:
                content = await schema_file.read()
                with open(data_dir / "database_schema.md", "wb") as f:
                    f.write(content)
            elif database_schema:
                with open(data_dir / "database_schema.md", "w", encoding="utf-8") as f:
                    f.write(database_schema)

            # Save database file
            if database_file and database_file.filename:
                db_path = data_dir / "database.db"
                content = await database_file.read()
                with open(db_path, "wb") as f:
                    f.write(content)

        # Reload agents
        runner.discover_agents()

        return {
            "success": True,
            "agent_id": agent_id,
            "path": str(output_dir),
            "message": f"Agent '{agent_name}' created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── User feedback on agent responses ──────────────────────────────

class FeedbackRequest(BaseModel):
    agent_id: str
    session_id: str = ""
    message_index: int = 0
    mode: str = "user"               # "user" or "tester"
    rating: str                      # "up" or "down"
    error_code: Optional[str] = None # "1.1", "1.2.1", "2.1", "3.1", etc. (tester mode)
    severity: Optional[str] = None   # "minor", "major", "critical" (tester mode)
    notes: Optional[str] = None      # comments (both modes)
    user_question: str = ""
    full_response: str = ""


@app.post("/api/feedback")
async def submit_feedback(fb: FeedbackRequest):
    """Log user feedback on an agent response.
    User and tester feedback are stored in separate per-agent files."""
    is_positive = fb.rating == "up"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "feedback_type": "positive" if is_positive else "negative",
        "agent_id": fb.agent_id,
        "session_id": fb.session_id,
        "message_index": fb.message_index,
        "rating": fb.rating,
        "user_question": fb.user_question,
        "full_response": fb.full_response,
    }
    if not is_positive:
        if fb.mode == "tester":
            # Tester: structured error report with full response
            entry["error_code"] = fb.error_code
            entry["severity"] = fb.severity
        entry["notes"] = (fb.notes or "")[:1000]

    if fb.mode == "tester":
        log_file = LOGS_DIR / f"{fb.agent_id}_feedback_tester.jsonl"
    else:
        log_file = LOGS_DIR / f"{fb.agent_id}_feedback_user.jsonl"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    import sys
    import socket

    print(f"Agents path: {AGENTS_PATH}")

    # Descubrir agentes al inicio
    agents = runner.discover_agents()
    print(f"Found {len(agents)} agents:")
    for agent in agents:
        print(f"  - {agent.name} ({agent.id})")

    # Verificar si el puerto está disponible antes de iniciar uvicorn
    host, port = "0.0.0.0", 8000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            msg = (
                f"\n*** ERROR: Port {port} is already in use. ***\n"
                f"Another server (or a previous instance of TOMMI) is using this port.\n\n"
                f"To fix this, either:\n"
                f"  1. Stop the other server, or\n"
                f"  2. Run: ./liberar-puerto.sh {port}\n"
            )
            print(msg)
            print(msg, file=sys.stderr)
            sys.exit(1)
        else:
            raise

    uvicorn.run(app, host=host, port=port)
