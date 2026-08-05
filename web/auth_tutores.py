"""
Autenticación para Tutores Virtuales.

Sistema de registro independiente de TOMMI3, con dos roles:
  - docente: puede modificar configuración del tutor
  - estudiante: puede hacer ejercicios y consultas

Los usuarios se almacenan en data/tutores_users.json.
"""

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "tutores_users.json"

ROLES_TUTORES = {"docente", "estudiante"}

# Active sessions: {token: {"username": str, "role": str, "created": float}}
_sessions: dict = {}

# Invitation tokens: {token: {"username": str, "created": float}}
# Valid for 7 days
_INVITE_EXPIRY = 7 * 86400
_invites: dict = {}


# ---------------------------------------------------------------------------
# Password hashing (same as main auth, but self-contained)
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return h.hex(), salt


def _verify_password(password: str, hash_hex: str, salt: str) -> bool:
    h, _ = _hash_password(password, salt)
    return secrets.compare_digest(h, hash_hex)


# ---------------------------------------------------------------------------
# User storage
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def list_users() -> list[dict]:
    """List all tutores users (without sensitive data)."""
    users = _load_users()
    return [
        {"username": u, "role": d.get("role", "estudiante"),
         "nombre": d.get("nombre", ""), "activo": d.get("activo", False)}
        for u, d in users.items()
    ]


def create_user(username: str, password: str = None, role: str = "estudiante",
                nombre: str = "", activo: bool = False) -> bool:
    """Create a new tutores user. Returns True if created.
    If password is None, account is pending activation (needs invite link).
    If activo=True, account is immediately usable (for docente self-setup)."""
    if role not in ROLES_TUTORES:
        raise ValueError(f"Rol inválido: {role}. Debe ser 'docente' o 'estudiante'.")
    users = _load_users()
    if username in users:
        return False
    user_data = {
        "role": role,
        "nombre": nombre,
        "activo": activo,
    }
    if password:
        hash_hex, salt = _hash_password(password)
        user_data["password_hash"] = hash_hex
        user_data["salt"] = salt
    users[username] = user_data
    _save_users(users)
    return True


def delete_user(username: str) -> bool:
    """Delete a tutores user."""
    users = _load_users()
    if username not in users:
        return False
    del users[username]
    _save_users(users)
    return True


def update_user(username: str, role: str = None, nombre: str = None, password: str = None) -> bool:
    """Update user fields. Returns True if user exists."""
    users = _load_users()
    if username not in users:
        return False
    if role is not None:
        if role not in ROLES_TUTORES:
            raise ValueError(f"Rol inválido: {role}")
        users[username]["role"] = role
    if nombre is not None:
        users[username]["nombre"] = nombre
    if password is not None:
        hash_hex, salt = _hash_password(password)
        users[username]["password_hash"] = hash_hex
        users[username]["salt"] = salt
    _save_users(users)
    return True


def bulk_create(entries: list[dict]) -> dict:
    """
    Create multiple users at once.

    Each entry: {"username": str, "password": str, "role": str, "nombre": str}

    Returns {"created": int, "skipped": int, "errors": list}
    """
    created = 0
    skipped = 0
    errors = []
    for e in entries:
        username = e.get("username", "").strip()
        password = e.get("password", "").strip()
        role = e.get("role", "estudiante").strip()
        nombre = e.get("nombre", "").strip()
        if not username or not password:
            errors.append(f"Falta usuario o contraseña: {e}")
            continue
        try:
            if create_user(username, password, role, nombre):
                created += 1
            else:
                skipped += 1
        except ValueError as ex:
            errors.append(str(ex))
    return {"created": created, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def create_invite(username: str) -> Optional[str]:
    """Generate an invitation token for a user.
    Returns the token, or None if user doesn't exist.
    Replaces any previous invite for the same user."""
    users = _load_users()
    if username not in users:
        return None
    # Remove existing invites for this user
    to_remove = [t for t, inv in _invites.items() if inv["username"] == username]
    for t in to_remove:
        del _invites[t]
    # Create new token
    token = secrets.token_urlsafe(32)
    _invites[token] = {
        "username": username,
        "created": time.time(),
    }
    return token


def validate_invite(token: str) -> Optional[str]:
    """Validate an invite token. Returns the username if valid, None otherwise."""
    invite = _invites.get(token)
    if not invite:
        return None
    if time.time() - invite["created"] > _INVITE_EXPIRY:
        del _invites[token]
        return None
    return invite["username"]


def activate_with_invite(token: str, new_password: str) -> Optional[str]:
    """Set password and activate account using an invite token.
    Returns the username if successful, None otherwise."""
    invite = _invites.get(token)
    if not invite:
        return None
    if time.time() - invite["created"] > _INVITE_EXPIRY:
        del _invites[token]
        return None
    username = invite["username"]
    users = _load_users()
    if username not in users:
        del _invites[token]
        return None
    # Set password and activate
    hash_hex, salt = _hash_password(new_password)
    users[username]["password_hash"] = hash_hex
    users[username]["salt"] = salt
    users[username]["activo"] = True
    _save_users(users)
    # Consume token
    del _invites[token]
    return username


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """Change password. Clears provisional flag. Returns True if successful."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return False
    if not _verify_password(old_password, user["password_hash"], user["salt"]):
        return False
    hash_hex, salt = _hash_password(new_password)
    user["password_hash"] = hash_hex
    user["salt"] = salt
    user["provisional"] = False
    _save_users(users)
    return True


def authenticate(username: str, password: str) -> Optional[dict]:
    """Authenticate a tutores user. Returns session dict or None.
    Returns None if account is not activated (no password set)."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if not user.get("activo", False):
        return None  # Account pending activation
    if "password_hash" not in user:
        return None  # No password set
    if not _verify_password(password, user["password_hash"], user["salt"]):
        return None

    token = secrets.token_hex(32)
    role = user.get("role", "estudiante")
    _sessions[token] = {
        "username": username,
        "role": role,
        "nombre": user.get("nombre", ""),
        "created": time.time(),
    }
    return {
        "token": token,
        "username": username,
        "role": role,
        "nombre": user.get("nombre", ""),
    }


SESSION_INACTIVITY_TIMEOUT = 1800  # 30 minutes
SESSION_MAX_LIFETIME = 86400       # 24 hours absolute max


def get_session(token: str) -> Optional[dict]:
    """Get session info. Returns None if invalid, expired (24h), or inactive (30min)."""
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    now = time.time()
    # Expire after 24 hours absolute
    if now - session["created"] > SESSION_MAX_LIFETIME:
        del _sessions[token]
        return None
    # Expire after 30 minutes of inactivity
    last_activity = session.get("last_activity", session["created"])
    if now - last_activity > SESSION_INACTIVITY_TIMEOUT:
        del _sessions[token]
        return None
    # Update last activity
    session["last_activity"] = now
    return session


def logout(token: str) -> None:
    _sessions.pop(token, None)


def is_docente(session: dict) -> bool:
    """Check if session has docente role."""
    return session.get("role") == "docente"
