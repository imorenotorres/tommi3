"""
Tommi Access Control - User authentication and role-based authorization.

Roles:
  - superuser: Full access (user management, testing, consultation)
  - tester: Testing access (agent testing + consultation)
  - user: Consultation access only

Users are stored in data/users.json with PBKDF2-hashed passwords.
"""

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Optional

# User data file
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"

# Role hierarchy
ROLES = {
    "superuser": 3,
    "tester": 2,
    "user": 1,
}

# Active sessions: {token: {"username": str, "role": str, "created": float}}
_sessions: dict[str, dict] = {}

# Invitation tokens: {token: {"username": str, "created": float}}
# Tokens expire after 72 hours
_INVITE_EXPIRY = 72 * 3600
INVITES_FILE = DATA_DIR / "invites.json"

# Access requests file
REQUESTS_FILE = DATA_DIR / "access_requests.json"

# Valid UNINOVIS partner email domains
UNINOVIS_DOMAINS = {
    "uma.es",           # Universidad de Malaga (Spain)
    "thws.de",          # TH Wurzburg-Schweinfurt (Germany)
    "thuas.nl",         # The Hague University of Applied Sciences (Netherlands)
    "univ-paris13.fr",  # Universite Sorbonne Paris Nord (France)
    "sorbonne-paris-nord.fr",
    "unicampania.it",   # University of Campania "Luigi Vanvitelli" (Italy)
    "go.kauko.lt",      # Kauno Kolegija (Lithuania)
    "kauko.lt",
    "unitir.edu.al",    # University of Tirana (Albania)
    "tuni.fi",          # Tampere University of Applied Sciences (Finland)
    "tamk.fi",
}


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

import re

def validate_password(password: str) -> str | None:
    """
    Validate password complexity. Returns None if valid, or an error message.
    Requirements: 8+ chars, uppercase, lowercase, digit, special character.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one digit"
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Password must contain at least one special character (!@#$%...)"
    return None


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return h.hex(), salt


def _verify_password(password: str, hash_hex: str, salt: str) -> bool:
    """Verify a password against its stored hash."""
    h, _ = _hash_password(password, salt)
    return secrets.compare_digest(h, hash_hex)


# ---------------------------------------------------------------------------
# User storage
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    """Load users from JSON file."""
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict) -> None:
    """Save users to JSON file."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def user_exists(username: str) -> bool:
    """Check if a user exists."""
    users = _load_users()
    return username in users


def create_user(username: str, password: str, role: str, provisional: bool = True) -> bool:
    """
    Create a new user.
    Returns True if created, False if username already exists.
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {list(ROLES.keys())}")

    users = _load_users()
    if username in users:
        return False

    hash_hex, salt = _hash_password(password)
    users[username] = {
        "password_hash": hash_hex,
        "salt": salt,
        "role": role,
        "provisional_password": provisional,
    }
    _save_users(users)
    return True


def delete_user(username: str) -> bool:
    """Delete a user. Returns True if deleted, False if not found."""
    users = _load_users()
    if username not in users:
        return False
    del users[username]
    _save_users(users)
    # Also remove any active sessions for this user
    tokens_to_remove = [t for t, s in _sessions.items() if s["username"] == username]
    for t in tokens_to_remove:
        del _sessions[t]
    return True


def list_users() -> list[dict]:
    """List all users (without password hashes)."""
    users = _load_users()
    return [
        {
            "username": uname,
            "role": data["role"],
            "provisional_password": data.get("provisional_password", False),
            "pending_invite": data.get("pending_invite", False),
        }
        for uname, data in users.items()
    ]


def update_user_role(username: str, new_role: str) -> bool:
    """Update a user's role. Returns True if updated."""
    if new_role not in ROLES:
        raise ValueError(f"Invalid role: {new_role}")
    users = _load_users()
    if username not in users:
        return False
    users[username]["role"] = new_role
    _save_users(users)
    return True


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user. Returns session info dict or None.
    Session info: {"token", "username", "role", "provisional_password"}
    """
    users = _load_users()
    user = users.get(username)
    if not user:
        return None

    if not _verify_password(password, user["password_hash"], user["salt"]):
        return None

    token = secrets.token_hex(32)
    _sessions[token] = {
        "username": username,
        "role": user["role"],
        "created": time.time(),
    }

    return {
        "token": token,
        "username": username,
        "role": user["role"],
        "provisional_password": user.get("provisional_password", False),
    }


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """Change a user's password. Clears provisional flag. Returns True if successful."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return False

    if not _verify_password(old_password, user["password_hash"], user["salt"]):
        return False

    hash_hex, salt = _hash_password(new_password)
    user["password_hash"] = hash_hex
    user["salt"] = salt
    user["provisional_password"] = False
    _save_users(users)
    return True


def get_session(token: str) -> Optional[dict]:
    """Get session info for a token. Returns None if invalid."""
    session = _sessions.get(token)
    if not session:
        return None
    # Check if user still exists with same role
    users = _load_users()
    user = users.get(session["username"])
    if not user:
        del _sessions[token]
        return None
    # Update role if changed
    session["role"] = user["role"]
    return session


def logout(token: str) -> None:
    """Invalidate a session token."""
    _sessions.pop(token, None)


def has_role(token: str, minimum_role: str) -> bool:
    """Check if the session has at least the given role level."""
    session = get_session(token)
    if not session:
        return False
    return ROLES.get(session["role"], 0) >= ROLES.get(minimum_role, 99)


# ---------------------------------------------------------------------------
# Invitation tokens
# ---------------------------------------------------------------------------

def _load_invites() -> dict:
    if not INVITES_FILE.exists():
        return {}
    with open(INVITES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_invites(invites: dict) -> None:
    with open(INVITES_FILE, "w", encoding="utf-8") as f:
        json.dump(invites, f, indent=2, ensure_ascii=False)


def create_user_pending(username: str, role: str) -> bool:
    """
    Create a user without a password (pending invitation).
    The user cannot log in until they set a password via invitation token.
    Returns True if created, False if already exists.
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}")
    users = _load_users()
    if username in users:
        return False
    users[username] = {
        "password_hash": "",
        "salt": "",
        "role": role,
        "provisional_password": True,
        "pending_invite": True,
    }
    _save_users(users)
    return True


def create_invite_token(username: str) -> Optional[str]:
    """
    Generate an invitation token for a user.
    The user must already exist. Returns the token or None if user not found.
    Replaces any previous token for the same user.
    """
    users = _load_users()
    if username not in users:
        return None

    invites = _load_invites()
    # Remove any existing token for this user
    invites = {t: v for t, v in invites.items() if v["username"] != username}
    # Create new token
    token = secrets.token_urlsafe(32)
    invites[token] = {
        "username": username,
        "created": time.time(),
    }
    _save_invites(invites)
    return token


def validate_invite_token(token: str) -> Optional[str]:
    """
    Validate an invitation token. Returns the username if valid, None otherwise.
    """
    invites = _load_invites()
    invite = invites.get(token)
    if not invite:
        return None
    # Check expiry
    if time.time() - invite["created"] > _INVITE_EXPIRY:
        del invites[token]
        _save_invites(invites)
        return None
    return invite["username"]


def set_password_from_invite(token: str, new_password: str) -> Optional[str]:
    """
    Set password for a user using an invitation token.
    Consumes the token. Returns the username if successful, None otherwise.
    """
    invites = _load_invites()
    invite = invites.get(token)
    if not invite:
        return None
    if time.time() - invite["created"] > _INVITE_EXPIRY:
        del invites[token]
        _save_invites(invites)
        return None

    username = invite["username"]
    users = _load_users()
    user = users.get(username)
    if not user:
        return None

    hash_hex, salt = _hash_password(new_password)
    user["password_hash"] = hash_hex
    user["salt"] = salt
    user["provisional_password"] = False
    user.pop("pending_invite", None)
    _save_users(users)

    # Consume the token
    del invites[token]
    _save_invites(invites)

    return username


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_invite_email(
    username: str,
    invite_url: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from: str,
    smtp_use_tls: bool = True,
) -> bool:
    """
    Send an invitation email to the user (username is their email).
    Returns True if sent successfully.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Tommi Agents - Set up your account"
    msg["From"] = smtp_from
    msg["To"] = username

    text_body = f"""Hello,

You have been invited to use Tommi Agents.

Please set your password by visiting the following link:

{invite_url}

This link will expire in 72 hours.

If you did not expect this email, you can safely ignore it.

— Tommi Agents
"""

    html_body = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; max-width: 500px; margin: 0 auto; padding: 2rem;">
  <h2 style="color: #2563eb;">Tommi Agents</h2>
  <p>Hello,</p>
  <p>You have been invited to use <b>Tommi Agents</b>.</p>
  <p>Please set your password by clicking the button below:</p>
  <p style="text-align: center; margin: 2rem 0;">
    <a href="{invite_url}" style="background-color: #2563eb; color: #ffffff; padding: 0.75rem 1.5rem; border-radius: 6px; text-decoration: none; font-weight: 500;">Set my password</a>
  </p>
  <p style="font-size: 0.85rem; color: #64748b;">This link will expire in 72 hours.</p>
  <p style="font-size: 0.85rem; color: #64748b;">If you did not expect this email, you can safely ignore it.</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0;">
  <p style="font-size: 0.8rem; color: #94a3b8;">Tommi Agents — Universidad de Málaga</p>
</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if smtp_use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, [username], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        import logging
        logging.getLogger("tommi").error(f"Failed to send invite email to {username}: {e}")
        return False


# ---------------------------------------------------------------------------
# Access requests (self-registration)
# ---------------------------------------------------------------------------

def _load_requests() -> list:
    if not REQUESTS_FILE.exists():
        return []
    with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_requests(requests: list) -> None:
    with open(REQUESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2, ensure_ascii=False)


def validate_uninovis_email(email: str) -> str | None:
    """
    Validate that an email belongs to a UNINOVIS partner institution.
    Returns None if valid, or an error message.
    """
    if not email or "@" not in email:
        return "A valid email address is required"
    domain = email.rsplit("@", 1)[1].lower()
    if domain not in UNINOVIS_DOMAINS:
        return f"Email domain '@{domain}' is not a recognised UNINOVIS partner institution"
    return None


def create_access_request(
    email: str, full_name: str, institution: str,
    department: str = "", profile_url: str = "", reason: str = "",
) -> bool:
    """
    Create an access request. Returns True if created, False if a request
    or user with this email already exists.
    """
    email = email.strip().lower()
    # Check if user already exists
    if user_exists(email):
        return False
    # Check if request already exists
    requests = _load_requests()
    if any(r["email"] == email and r["status"] == "pending" for r in requests):
        return False
    requests.append({
        "email": email,
        "full_name": full_name,
        "institution": institution,
        "department": department,
        "profile_url": profile_url,
        "reason": reason,
        "status": "pending",
        "created": time.time(),
    })
    _save_requests(requests)
    return True


def list_access_requests(status: str | None = None) -> list[dict]:
    """List access requests, optionally filtered by status."""
    requests = _load_requests()
    if status:
        requests = [r for r in requests if r["status"] == status]
    return requests


def approve_access_request(email: str, role: str = "user") -> bool:
    """
    Approve a pending access request. Creates the user as pending invite
    so an invitation email can be sent separately.
    Returns True if approved, False if not found.
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}")
    requests = _load_requests()
    found = False
    for r in requests:
        if r["email"] == email and r["status"] == "pending":
            r["status"] = "approved"
            r["approved_at"] = time.time()
            r["approved_role"] = role
            found = True
            break
    if not found:
        return False
    _save_requests(requests)
    # Create the user as pending invite
    create_user_pending(email, role)
    return True


def reject_access_request(email: str) -> bool:
    """Reject a pending access request. Returns True if rejected."""
    requests = _load_requests()
    found = False
    for r in requests:
        if r["email"] == email and r["status"] == "pending":
            r["status"] = "rejected"
            r["rejected_at"] = time.time()
            found = True
            break
    if not found:
        return False
    _save_requests(requests)
    return True


# ---------------------------------------------------------------------------
# Setup helper
# ---------------------------------------------------------------------------

def ensure_superuser(username: str = "admin", password: str = "admin") -> str:
    """
    Create the default superuser if no superuser exists.
    Returns the username of the superuser (existing or newly created).
    """
    users = _load_users()
    # Check if any superuser exists
    for uname, data in users.items():
        if data["role"] == "superuser":
            return uname

    # No superuser found — create one
    create_user(username, password, "superuser", provisional=True)
    return username
