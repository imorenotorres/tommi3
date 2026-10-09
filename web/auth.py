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
import random
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request

# User data file
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"

# Role hierarchy — numeric level for privilege checks
ROLES = {
    "superuser": 4,
    "content_manager": 3.5,  # below superuser, above every other role
    "tester": 3,
    "uninovis_staff": 2.5,  # admin_staff/teaching_staff who are also on the UNINOVIS project
    "wp_leader": 2.2,  # leads a UNINOVIS work package; scoped unit-management rights in directory
    "admin_staff": 2,
    "teaching_staff": 2,
    "student": 1,
    "user": 1,  # legacy alias for student
}

# Tool access — which roles can access each tool (defaults)
# content_manager sits just below superuser, so it is included on every tool
# except the reserved System Administration / analytics tools below.
_DEFAULT_TOOL_ACCESS = {
    # Learning & Mobility
    "course_catalogue":   ["student", "admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "module_overview":    ["student", "admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "module_recognition": ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "micro_credentials":  ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "learning_support":   ["student", "admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "gloria_learner_support": ["student", "admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "unigracon":          ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "mobility_planner":   ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    # Research & Innovation
    "internships":        ["student", "admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "researcher_connect": ["teaching_staff", "tester", "content_manager", "superuser"],
    "research_proposals": ["teaching_staff", "tester", "content_manager", "superuser"],
    "research_portfolio": ["teaching_staff", "tester", "content_manager", "superuser"],
    "research_explorers": ["student", "teaching_staff", "tester", "content_manager", "superuser"],
    "european_projects":  ["student", "admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "uninovis_uma_dashboard": ["uninovis_staff", "content_manager", "superuser"],
    # Events & Communication
    "event_catalogue":    ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    # Administration
    "directory":          ["admin_staff", "uninovis_staff", "teaching_staff", "wp_leader", "tester", "content_manager", "superuser"],
    "event_tracker":      ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "dp_status":          ["admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"],
    "holiday_tracker":    ["uninovis_staff", "content_manager", "superuser"],
    # Analytics & System Administration — reserved for superuser
    "log_analytics":      ["superuser"],
    "matomo_analytics":   ["superuser"],
    "user_management":    ["superuser"],
    "agent_management":   ["superuser"],
    "tool_visibility":    ["superuser"],
    "feedback":           ["superuser"],
}

TOOL_ACCESS_FILE = DATA_DIR / "tool_access.json"


def _load_tool_access() -> dict:
    """Load tool access from JSON file, falling back to defaults."""
    if TOOL_ACCESS_FILE.exists():
        try:
            with open(TOOL_ACCESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULT_TOOL_ACCESS)


def save_tool_access(access: dict):
    """Save tool access overrides to JSON file."""
    with open(TOOL_ACCESS_FILE, "w", encoding="utf-8") as f:
        json.dump(access, f, indent=2, ensure_ascii=False)
        f.write("\n")


TOOL_ACCESS = _load_tool_access()

# Roles that grant editing rights in apps (equivalent to old "tester" check)
EDITOR_ROLES = {"admin_staff", "uninovis_staff", "teaching_staff", "tester", "content_manager", "superuser"}

# Narrower editing rights for tools curated only by content managers (UNIGRACON,
# Mobility Planner) — unlike EDITOR_ROLES above, teaching_staff/tester/admin_staff/
# uninovis_staff no longer get an edit toggle on these two tools.
CONTENT_MANAGER_EDITOR_ROLES = {"content_manager", "superuser"}


def user_roles(user_or_session: dict) -> list:
    """Return the list of roles for a user/session. Supports both 'role' (str) and 'roles' (list)."""
    roles = user_or_session.get("roles")
    if roles and isinstance(roles, list):
        return roles
    role = user_or_session.get("role", "")
    return [role] if role else []


def can_access_tool(user_or_session: dict, tool_id: str) -> bool:
    """Check if a user can access a given tool based on their roles.

    Secure by default: a tool with no TOOL_ACCESS entry yet (e.g. a newly
    added app nobody has configured in the Tool Visibility panel) is
    accessible only to superuser, not to everyone, until an admin opens it up.
    """
    if tool_id not in TOOL_ACCESS:
        return "superuser" in set(user_roles(user_or_session))
    allowed = set(TOOL_ACCESS[tool_id])
    return bool(allowed & set(user_roles(user_or_session)))


def can_edit(user_or_session: dict) -> bool:
    """Check if a user has editing rights (admin_staff, teaching_staff, tester, superuser)."""
    return bool(EDITOR_ROLES & set(user_roles(user_or_session)))


def can_edit_as_content_manager(user_or_session: dict) -> bool:
    """Check if a user has editing rights restricted to content_manager/superuser
    (used by tools curated only by content managers, e.g. UNIGRACON and Mobility
    Planner)."""
    return bool(CONTENT_MANAGER_EDITOR_ROLES & set(user_roles(user_or_session)))


def max_role_level(user_or_session: dict) -> int:
    """Return the highest privilege level among the user's roles."""
    return max((ROLES.get(r, 0) for r in user_roles(user_or_session)), default=0)

# ---------------------------------------------------------------------------
# Study mode — random transparency assignment for experiments
# ---------------------------------------------------------------------------
# When enabled, users are randomly assigned a transparency condition at first
# login. The condition is stored in users.json as "study_condition" and cannot
# be changed by the user during the session.

STUDY_CONFIG_FILE = DATA_DIR / "study_config.json"
STUDY_CONDITIONS = ["black_box", "grey_box", "crystal_box"]


def _load_study_config() -> dict:
    """Load study mode configuration."""
    if not STUDY_CONFIG_FILE.exists():
        return {"enabled": False}
    with open(STUDY_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def is_study_mode() -> bool:
    """Return True if study mode is currently enabled."""
    return _load_study_config().get("enabled", False)


def assign_study_condition(username: str) -> Optional[str]:
    """Assign a random transparency condition to a user for the study.

    Uses stratified assignment: picks the condition with the fewest
    current participants to maintain balanced groups.

    Returns the assigned condition, or None if study mode is disabled
    or the user already has a condition.
    """
    if not is_study_mode():
        return None

    users = _load_users()
    user = users.get(username)
    if not user:
        return None

    # Already assigned
    if user.get("study_condition"):
        return user["study_condition"]

    # Count current assignments for balanced allocation
    counts = {c: 0 for c in STUDY_CONDITIONS}
    for u in users.values():
        cond = u.get("study_condition")
        if cond in counts:
            counts[cond] += 1

    # Pick the least-assigned condition (random tiebreak)
    min_count = min(counts.values())
    candidates = [c for c, n in counts.items() if n == min_count]
    condition = random.choice(candidates)

    user["study_condition"] = condition
    _save_users(users)
    return condition


def get_study_condition(username: str) -> Optional[str]:
    """Return the user's assigned study condition, or None."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    return user.get("study_condition")


def _extract_email_domain(username: str) -> str:
    """Extract country TLD from email/username (e.g. 'user@uma.es' -> 'es')."""
    if "@" in username:
        domain = username.rsplit("@", 1)[1]
        return domain.rsplit(".", 1)[-1].lower()
    return "unknown"


def enroll_study_participant(username: str) -> Optional[dict]:
    """Enroll a user as a study participant.

    Assigns a study_id (S001, S002...), a random transparency condition,
    and extracts the email country domain.  Returns the study info dict
    or None if the user doesn't exist.
    """
    users = _load_users()
    user = users.get(username)
    if not user:
        return None

    # Already enrolled — return existing info
    if user.get("study_participant"):
        return {
            "study_id": user["study_id"],
            "study_condition": user["study_condition"],
            "email_domain": user["email_domain"],
        }

    # Generate next study_id
    existing_ids = [
        u.get("study_id", "")
        for u in users.values()
        if u.get("study_participant")
    ]
    next_num = len(existing_ids) + 1
    study_id = f"S{next_num:03d}"

    # Ensure uniqueness
    while study_id in existing_ids:
        next_num += 1
        study_id = f"S{next_num:03d}"

    # Assign condition (balanced)
    counts = {c: 0 for c in STUDY_CONDITIONS}
    for u in users.values():
        cond = u.get("study_condition")
        if u.get("study_participant") and cond in counts:
            counts[cond] += 1
    min_count = min(counts.values())
    candidates = [c for c, n in counts.items() if n == min_count]
    condition = random.choice(candidates)

    email_domain = _extract_email_domain(username)

    user["study_participant"] = True
    user["study_id"] = study_id
    user["study_condition"] = condition
    user["email_domain"] = email_domain
    user["study_completed"] = False
    _save_users(users)

    return {
        "study_id": study_id,
        "study_condition": condition,
        "email_domain": email_domain,
    }


def get_study_info(username: str) -> Optional[dict]:
    """Return full study info for a participant, or None."""
    users = _load_users()
    user = users.get(username)
    if not user or not user.get("study_participant"):
        return None
    return {
        "study_id": user.get("study_id"),
        "study_condition": user.get("study_condition"),
        "email_domain": user.get("email_domain"),
        "study_completed": user.get("study_completed", False),
    }


def mark_study_completed(username: str) -> bool:
    """Mark a study participant as having completed all queries."""
    users = _load_users()
    user = users.get(username)
    if not user or not user.get("study_participant"):
        return False
    user["study_completed"] = True
    _save_users(users)
    return True


# Active sessions: {token: {"username", "role", "roles", "created", "last_seen"}}
_sessions: dict[str, dict] = {}

# A session ends after SESSION_IDLE_HOURS without any request, and in any case
# SESSION_MAX_DAYS after login (both overridable in .env).
import os as _os
SESSION_IDLE_SECONDS = float(_os.getenv("SESSION_IDLE_HOURS", "8")) * 3600
SESSION_MAX_AGE_SECONDS = float(_os.getenv("SESSION_MAX_DAYS", "7")) * 86400


def _purge_expired_sessions() -> None:
    now = time.time()
    expired = [
        t for t, s in _sessions.items()
        if now - s.get("created", now) > SESSION_MAX_AGE_SECONDS
        or now - s.get("last_seen", s.get("created", now)) > SESSION_IDLE_SECONDS
    ]
    for t in expired:
        _sessions.pop(t, None)


def revoke_user_sessions(username: str, keep_token: Optional[str] = None) -> int:
    """End every active session of `username` (except `keep_token`). Used when
    the password changes, so a stolen token stops working. Returns the count."""
    tokens = [t for t, s in _sessions.items() if s["username"] == username and t != keep_token]
    for t in tokens:
        _sessions.pop(t, None)
    return len(tokens)

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
    "hhs.nl",           # Haagse Hogeschool (THUAS alternative domain)
    "univ-paris13.fr",  # Universite Sorbonne Paris Nord (France)
    "univ-paris.fr",
    "sorbonne-paris-nord.fr",
    "unicampania.it",   # University of Campania "Luigi Vanvitelli" (Italy)
    "go.kauko.lt",      # Kauno Kolegija (Lithuania)
    "kauko.lt",
    "kaunokolegija.lt",
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

_PBKDF2_ITERATIONS = 310_000  # NIST SP 800-132 (2023) recommendation


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return h.hex(), salt


def _verify_password(password: str, hash_hex: str, salt: str) -> bool:
    """Verify a password against its stored hash.
    Supports both old (100k) and new (310k) iteration counts."""
    h, _ = _hash_password(password, salt)
    if secrets.compare_digest(h, hash_hex):
        return True
    # Fallback: try old iteration count for hashes created before the upgrade
    h_old = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(h_old.hex(), hash_hex)


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


def _find_username(users: dict, username: str) -> Optional[str]:
    """Return the stored key matching `username` case-insensitively (emails
    may be stored in any case), preferring an exact match. None if not found."""
    if username in users:
        return username
    wanted = (username or "").strip().lower()
    for key in users:
        if key.lower() == wanted:
            return key
    return None


def user_exists(username: str) -> bool:
    """Check if a user exists (case-insensitive)."""
    users = _load_users()
    return _find_username(users, username) is not None


def create_user(username: str, password: str, role: str, provisional: bool = True, roles: list = None, name: str = "") -> bool:
    """
    Create a new user. Supports dual roles via the `roles` parameter.
    Returns True if created, False if username already exists.
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {list(ROLES.keys())}")
    if roles:
        for r in roles:
            if r not in ROLES:
                raise ValueError(f"Invalid role: {r}. Must be one of {list(ROLES.keys())}")

    users = _load_users()
    if username in users:
        return False

    hash_hex, salt = _hash_password(password)
    user_data = {
        "password_hash": hash_hex,
        "salt": salt,
        "role": role,
        "roles": roles or [role],
        "provisional_password": provisional,
        "name": name.strip(),
    }
    users[username] = user_data
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
            "roles": data.get("roles", [data["role"]]),
            "provisional_password": data.get("provisional_password", False),
            "pending_invite": data.get("pending_invite", False),
            "name": data.get("name", ""),
        }
        for uname, data in users.items()
    ]


def mark_onboarding_seen(username: str) -> bool:
    """Mark that a user has completed the intranet onboarding tour. Returns True if updated."""
    users = _load_users()
    if username not in users:
        return False
    users[username]["seen_onboarding_tour"] = True
    _save_users(users)
    return True


def update_user_role(username: str, new_role: str, roles: list = None) -> bool:
    """Update a user's role(s). Returns True if updated."""
    all_roles = roles or [new_role]
    for r in all_roles:
        if r not in ROLES:
            raise ValueError(f"Invalid role: {r}")
    users = _load_users()
    if username not in users:
        return False
    users[username]["role"] = all_roles[0]
    users[username]["roles"] = all_roles
    _save_users(users)
    return True


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

# ── Login lockout ──────────────────────────────────────────────────
# After LOGIN_MAX_FAILURES failed logins for the same username within
# LOGIN_FAILURE_WINDOW seconds, that username is locked for LOGIN_LOCKOUT
# seconds. Keyed on the typed username (lowercased) whether or not the account
# exists, so the lock itself doesn't reveal which accounts are real.
LOGIN_MAX_FAILURES = 5
LOGIN_FAILURE_WINDOW = 15 * 60
LOGIN_LOCKOUT = 15 * 60
_failed_logins: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}


def login_locked_for(username: str) -> int:
    """Seconds left on this username's lockout (0 if not locked)."""
    key = username.strip().lower()
    remaining = _locked_until.get(key, 0) - time.time()
    if remaining <= 0:
        _locked_until.pop(key, None)
        return 0
    return int(remaining) + 1


def record_failed_login(username: str) -> None:
    key = username.strip().lower()
    now = time.time()
    recent = [t for t in _failed_logins.get(key, []) if now - t < LOGIN_FAILURE_WINDOW]
    recent.append(now)
    if len(recent) >= LOGIN_MAX_FAILURES:
        _locked_until[key] = now + LOGIN_LOCKOUT
        recent = []
    _failed_logins[key] = recent
    # Keep the maps from growing without bound under a spray of usernames.
    if len(_failed_logins) > 10_000:
        for k in [k for k, v in _failed_logins.items() if not v or now - v[-1] > LOGIN_FAILURE_WINDOW]:
            _failed_logins.pop(k, None)
    if len(_locked_until) > 10_000:
        for k in [k for k, v in _locked_until.items() if v < now]:
            _locked_until.pop(k, None)


def clear_failed_logins(username: str) -> None:
    key = username.strip().lower()
    _failed_logins.pop(key, None)
    _locked_until.pop(key, None)


# Hash checked when the username doesn't exist, so an unknown username takes as
# long to reject as a wrong password (no timing difference to enumerate users).
_DUMMY_SALT = secrets.token_hex(16)
_DUMMY_HASH = ""


def _dummy_verify(password: str) -> None:
    global _DUMMY_HASH
    if not _DUMMY_HASH:
        _DUMMY_HASH, _ = _hash_password(secrets.token_hex(16), _DUMMY_SALT)
    _verify_password(password, _DUMMY_HASH, _DUMMY_SALT)


def authenticate(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user. Returns session info dict or None.
    Session info: {"token", "username", "role", "provisional_password"}
    The email is matched case-insensitively; the session carries the
    username exactly as stored so per-app ownership checks keep matching.
    """
    users = _load_users()
    username = _find_username(users, username)
    if not username:
        _dummy_verify(password)
        return None
    user = users[username]

    if not _verify_password(password, user["password_hash"], user["salt"]):
        return None

    roles = user.get("roles") or [user.get("role", "user")]
    primary_role = roles[0] if roles else "user"

    _purge_expired_sessions()
    token = secrets.token_hex(32)
    _sessions[token] = {
        "username": username,
        "role": primary_role,
        "roles": roles,
        "created": time.time(),
        "last_seen": time.time(),
    }

    # Study info
    study_info = get_study_info(username)

    result = {
        "token": token,
        "username": username,
        "role": primary_role,
        "roles": roles,
        "provisional_password": user.get("provisional_password", False),
    }
    if study_info:
        result["study_participant"] = True
        result["study_id"] = study_info["study_id"]
        result["study_condition"] = study_info["study_condition"]
    elif is_study_mode():
        result["study_mode"] = True
        cond = assign_study_condition(username)
        result["study_condition"] = cond or user.get("study_condition")

    return result


def change_password(username: str, old_password: str, new_password: str, keep_token: Optional[str] = None) -> bool:
    """Change a user's password. Clears provisional flag and ends the user's
    other sessions (all but `keep_token`). Returns True if successful."""
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
    revoke_user_sessions(username, keep_token=keep_token)
    return True


def get_session(token: str) -> Optional[dict]:
    """Get session info for a token. Returns None if invalid or expired."""
    session = _sessions.get(token)
    if not session:
        return None
    now = time.time()
    last_seen = session.get("last_seen", session.get("created", now))
    if now - session.get("created", now) > SESSION_MAX_AGE_SECONDS or now - last_seen > SESSION_IDLE_SECONDS:
        _sessions.pop(token, None)
        return None
    # Check if user still exists with same role
    users = _load_users()
    user = users.get(session["username"])
    if not user:
        _sessions.pop(token, None)
        return None
    session["last_seen"] = now
    # Roles are re-read on every lookup so a role change or demotion applies
    # immediately — user_roles() reads "roles" first, so both must be fresh.
    session["roles"] = user.get("roles") or [user["role"]]
    session["role"] = session["roles"][0]
    # Kept fresh on every lookup (not just at login) so a password change
    # mid-session takes effect immediately, without requiring a re-login.
    session["provisional_password"] = user.get("provisional_password", False)
    return session


def logout(token: str) -> None:
    """Invalidate a session token."""
    _sessions.pop(token, None)


def has_role(token: str, minimum_role: str) -> bool:
    """Check if the session has at least the given role level."""
    session = get_session(token)
    if not session:
        return False
    return max_role_level(session) >= ROLES.get(minimum_role, 99)


# ---------------------------------------------------------------------------
# Shared FastAPI dependencies — every app under web/apps/ was independently
# redefining these same three functions; they now import them from here
# instead so login/guest-fallback and editor-gating behavior can't drift
# between apps.
# ---------------------------------------------------------------------------

def get_token(request: Request) -> Optional[str]:
    """Extract the bearer token from the Authorization header, falling back
    to a ?token= query param."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.query_params.get("token")


def require_session(request: Request) -> dict:
    """FastAPI dependency: resolve the caller's session, falling back to a
    read-only 'guest' session when there's no valid token."""
    token = get_token(request)
    if not token:
        return {"username": "guest", "role": "public", "roles": ["public"]}
    session = get_session(token)
    if not session:
        return {"username": "guest", "role": "public", "roles": ["public"]}
    return session


def require_login(request: Request) -> dict:
    """FastAPI dependency: require a REAL authenticated session — unlike
    require_session, there is no guest fallback; a missing or invalid token
    raises 401. For apps that must not be usable at all without logging in."""
    token = get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def tool_access_guard(tool_id: str, exempt_suffixes: tuple = ()):
    """Router-level dependency that applies the Tool Visibility settings
    (TOOL_ACCESS) on the server, not only by hiding the intranet card.
    Checks every */api/* route of the router except paths ending in one of
    `exempt_suffixes`; the HTML page itself stays loadable so it can explain
    the missing access."""
    def guard(request: Request, session: dict = Depends(require_session)) -> None:
        path = request.url.path
        if "/api/" not in path or path.endswith(exempt_suffixes):
            return
        if session.get("role") == "public":
            raise HTTPException(status_code=401, detail="Authentication required")
        if not can_access_tool(session, tool_id):
            raise HTTPException(status_code=403, detail="You do not have access to this tool")
    return guard


def require_editor(session: dict = Depends(require_session)) -> dict:
    """FastAPI dependency: require EDITOR_ROLES membership on top of a
    resolved session."""
    if not can_edit(session):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


def require_content_manager_editor(session: dict = Depends(require_session)) -> dict:
    """FastAPI dependency: require CONTENT_MANAGER_EDITOR_ROLES membership on
    top of a resolved session (content_manager/superuser only)."""
    if not can_edit_as_content_manager(session):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


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
    username = _find_username(users, username)
    if not username:
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
    revoke_user_sessions(username)

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
    recipient_name: str | None = None,
    is_reset: bool = False,
) -> bool:
    """
    Send an invitation (or, with is_reset=True, a password-reset) email to
    the user (username is their email). Returns True if sent successfully.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
    intro = "A password reset was requested for your UNINOVIS Intranet account." if is_reset else "You have been invited to use the UNINOVIS Intranet."
    action_label = "Reset my password" if is_reset else "Set my password"
    ignore_note = "If you did not request this, you can safely ignore this email — your password will not change." if is_reset else "If you did not expect this email, you can safely ignore it."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "UNINOVIS Intranet - Reset your password" if is_reset else "UNINOVIS Intranet - Set up your account"
    msg["From"] = smtp_from
    msg["To"] = username

    text_body = f"""{greeting}

{intro}

Please {'reset' if is_reset else 'set'} your password by visiting the following link:

{invite_url}

This link will expire in 72 hours.

{ignore_note}

— UNINOVIS Intranet
"""

    html_body = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; max-width: 500px; margin: 0 auto; padding: 2rem;">
  <h2 style="color: #2563eb;">UNINOVIS Intranet</h2>
  <p>{greeting}</p>
  <p>{intro}</p>
  <p>Please {'reset' if is_reset else 'set'} your password by clicking the button below:</p>
  <p style="text-align: center; margin: 2rem 0;">
    <a href="{invite_url}" style="background-color: #2563eb; color: #ffffff; padding: 0.75rem 1.5rem; border-radius: 6px; text-decoration: none; font-weight: 500;">{action_label}</a>
  </p>
  <p style="font-size: 0.85rem; color: #64748b;">This link will expire in 72 hours.</p>
  <p style="font-size: 0.85rem; color: #64748b;">{ignore_note}</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0;">
  <p style="font-size: 0.8rem; color: #94a3b8;">UNINOVIS Intranet — Universidad de Málaga</p>
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


def delete_access_request(email: str) -> bool:
    """Permanently remove an access request, regardless of its status.
    Used once a reviewer has finished handling it (the intranet's "Solved"
    button) — there is no undo. Returns True if a matching request was
    found and removed."""
    requests = _load_requests()
    remaining = [r for r in requests if r["email"] != email]
    if len(remaining) == len(requests):
        return False
    _save_requests(remaining)
    return True


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
