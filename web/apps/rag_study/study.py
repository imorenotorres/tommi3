"""
AI Transparency Comparative Study — Procedural vs. Content Transparency.

2x2 mixed design:
  - Within-subjects: Transparency type (content vs. procedural)
  - Between-subjects: Agent domain (RAG vs. Text2SQL)
  - Counterbalanced presentation order

Designed to be mounted on the TOMMI FastAPI server.
"""

import json
import os
import secrets
import sqlite3
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import asyncio

APP_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(APP_DIR, "static")
RESPONSES_DIR = os.path.join(APP_DIR, "responses")
DB_PATH = os.path.join(APP_DIR, "study_data.db")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

router = APIRouter(prefix="/rag-study", tags=["rag-study"])

# ============================================================
# CONFIGURATION — loaded from config.json
# ============================================================
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()


# ============================================================
# DATABASE
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure table exists (handles DB deletion while running)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            domain TEXT NOT NULL,
            presentation_order TEXT NOT NULL,
            experience INTEGER,
            trust_pre INTEGER,
            technical INTEGER,
            time_agent1_sec INTEGER,
            time_agent2_sec INTEGER,
            trust_content INTEGER,
            trust_procedural INTEGER,
            useful_content INTEGER,
            useful_procedural INTEGER,
            ease_content INTEGER,
            ease_procedural INTEGER,
            effort_content INTEGER,
            effort_procedural INTEGER,
            preference TEXT,
            comment TEXT,
            total_time_sec INTEGER,
            completed INTEGER DEFAULT 0
        )
    """)
    return conn


def generate_participant_id():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(8))


# ============================================================
# ASSIGNMENT LOGIC
# ============================================================
# 2 groups per question (counterbalanced order)
# With N questions: 2*N groups, cycling through questions and orders

def build_groups():
    """Build group list from config questions."""
    questions = CONFIG.get("questions", [])
    groups = []
    for q in questions:
        groups.append({"question_id": q["id"], "order": "informator_first"})
        groups.append({"question_id": q["id"], "order": "cooperator_first"})
    return groups

GROUPS = build_groups()


def get_question_config(question_id):
    """Find question config by id."""
    for q in CONFIG.get("questions", []):
        if q["id"] == question_id:
            return q
    return None


def get_agent_config(question_id, order):
    """Return blackbox_url, agent1, agent2, question text based on assignment."""
    q = get_question_config(question_id)
    if not q:
        raise ValueError(f"Question '{question_id}' not found in config")

    informator_agent = {
        "url": q["informator"],
        "label": CONFIG["INFORMATOR_LABEL"],
        "desc": CONFIG["INFORMATOR_DESC"],
        "type": "informator",
    }
    cooperator_agent = {
        "url": q["cooperator"],
        "label": CONFIG["COOPERATOR_LABEL"],
        "desc": CONFIG["COOPERATOR_DESC"],
        "type": "cooperator",
    }

    if order == "informator_first":
        return q["blackbox"], informator_agent, cooperator_agent, q["text"]
    else:
        cooperator_agent["label"] = CONFIG["INFORMATOR_LABEL"]
        informator_agent["label"] = CONFIG["COOPERATOR_LABEL"]
        return q["blackbox"], cooperator_agent, informator_agent, q["text"]


# ============================================================
# REQUEST MODELS
# ============================================================
class StartBody(BaseModel):
    email: str

class SurveyBody(BaseModel):
    participant_id: str
    experience: int
    trust_pre: int
    technical: int

class TimeBody(BaseModel):
    participant_id: str
    agent_num: int
    time_sec: int

class RatingBody(BaseModel):
    participant_id: str
    agent_num: int
    trust: int
    useful: int
    effort: int

class ComparisonBody(BaseModel):
    participant_id: str
    preference: str
    comment: str = ""
    total_time_sec: int = 0


# ============================================================
# STUDY SESSION — creates a limited TOMMI session for the participant
# ============================================================
# Study participants stored in auth._sessions need a matching user in
# auth._load_users(). We create a temporary "study_participant" user once,
# then issue sessions against it. This user has role "user" (minimal access).
_STUDY_USERNAME = "__study_participant__"

def _ensure_study_user():
    """Create a shared study user in the TOMMI user store if it doesn't exist."""
    from auth import _load_users, _save_users, _hash_password
    users = _load_users()
    if _STUDY_USERNAME not in users or users[_STUDY_USERNAME].get("role") != "tester":
        pwd = secrets.token_hex(32)
        salt = secrets.token_hex(16)
        import hashlib
        h = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 100_000).hex()
        users[_STUDY_USERNAME] = {
            "password_hash": h,
            "salt": salt,
            "role": "tester",
        }
        _save_users(users)

def create_study_session() -> str:
    """Create a TOMMI session for a study participant. Returns the token."""
    _ensure_study_user()
    from auth import _sessions
    token = secrets.token_hex(32)
    _sessions[token] = {
        "username": _STUDY_USERNAME,
        "role": "tester",   # tester role needed to access cloud-provider agents
        "created": time.time(),
    }
    return token


# ============================================================
# HELPER
# ============================================================
def _get_participant(conn, pid):
    row = conn.execute(
        "SELECT * FROM participants WHERE participant_id = ?", (pid,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Participant not found")
    return row


# ============================================================
# ROUTES
# ============================================================
@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.post("/api/start")
def start_study(body: StartBody):
    """Register participant and assign condition."""
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    conn = get_db()
    existing = conn.execute(
        "SELECT participant_id, completed, domain, presentation_order FROM participants WHERE email = ?",
        (email,),
    ).fetchone()

    if existing and existing["completed"]:
        conn.close()
        raise HTTPException(status_code=400, detail="This email has already completed the study. Thank you!")

    if existing:
        pid = existing["participant_id"]
        question_id = existing["domain"]  # domain column stores question_id
        order = existing["presentation_order"]
    else:
        pid = generate_participant_id()
        count = conn.execute("SELECT COUNT(*) as c FROM participants").fetchone()["c"]
        num_groups = len(GROUPS) if GROUPS else 2
        group = GROUPS[count % num_groups]
        question_id = group["question_id"]
        order = group["order"]

        conn.execute(
            """INSERT INTO participants
               (participant_id, email, created_at, domain, presentation_order)
               VALUES (?, ?, ?, ?, ?)""",
            (pid, email, datetime.utcnow().isoformat(), question_id, order),
        )
        conn.commit()

    conn.close()

    blackbox_url, agent1, agent2, question_text = get_agent_config(question_id, order)

    return {
        "participant_id": pid,
        "question_id": question_id,
        "order": order,
        "agent1": agent1,
        "agent2": agent2,
        "question": question_text,
        "blackbox_url": blackbox_url,
    }


@router.post("/api/save_survey")
def save_survey(body: SurveyBody):
    conn = get_db()
    _get_participant(conn, body.participant_id)
    conn.execute(
        """UPDATE participants
           SET experience = ?, trust_pre = ?, technical = ?
           WHERE participant_id = ?""",
        (body.experience, body.trust_pre, body.technical, body.participant_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/api/save_time")
def save_time(body: TimeBody):
    conn = get_db()
    row = _get_participant(conn, body.participant_id)
    col = "time_agent1_sec" if body.agent_num == 1 else "time_agent2_sec"
    conn.execute(
        f"UPDATE participants SET {col} = ? WHERE participant_id = ?",
        (body.time_sec, body.participant_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/api/save_agent_rating")
def save_agent_rating(body: RatingBody):
    conn = get_db()
    row = _get_participant(conn, body.participant_id)
    order = row["presentation_order"]

    if order == "informator_first":
        is_content = (body.agent_num == 1)
    else:
        is_content = (body.agent_num == 2)

    if is_content:
        conn.execute(
            """UPDATE participants
               SET trust_content = ?, useful_content = ?, effort_content = ?
               WHERE participant_id = ?""",
            (body.trust, body.useful, body.effort, body.participant_id),
        )
    else:
        conn.execute(
            """UPDATE participants
               SET trust_procedural = ?, useful_procedural = ?, effort_procedural = ?
               WHERE participant_id = ?""",
            (body.trust, body.useful, body.effort, body.participant_id),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/api/save_comparison")
def save_comparison(body: ComparisonBody):
    conn = get_db()
    _get_participant(conn, body.participant_id)
    conn.execute(
        """UPDATE participants
           SET preference = ?, comment = ?,
               completed = 1, completed_at = ?,
               total_time_sec = ?
           WHERE participant_id = ?""",
        (body.preference, body.comment, datetime.utcnow().isoformat(),
         body.total_time_sec, body.participant_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/export")
def export_csv():
    """Download all completed results as CSV."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM participants WHERE completed = 1 ORDER BY created_at"
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No completed results yet.")

    headers = [
        "participant_id", "email", "created_at", "completed_at",
        "domain", "presentation_order",
        "experience", "trust_pre", "technical",
        "time_agent1_sec", "time_agent2_sec",
        "trust_content", "trust_procedural",
        "useful_content", "useful_procedural",
        "ease_content", "ease_procedural",
        "effort_content", "effort_procedural",
        "preference", "comment", "total_time_sec",
    ]

    def generate():
        yield ",".join(headers) + "\n"
        for row in rows:
            values = []
            for h in headers:
                val = row[h] if row[h] is not None else ""
                val_str = str(val)
                if "," in val_str or '"' in val_str or "\n" in val_str:
                    val_str = '"' + val_str.replace('"', '""') + '"'
                values.append(val_str)
            yield ",".join(values) + "\n"

    return Response(
        content="".join(generate()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=transparency_study_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@router.get("/api/stats")
def stats():
    """Stats for the researcher."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM participants").fetchone()["c"]
    completed = conn.execute("SELECT COUNT(*) as c FROM participants WHERE completed = 1").fetchone()["c"]

    # Per-order counts
    order_counts = {}
    for row in conn.execute("SELECT presentation_order, COUNT(*) as c FROM participants WHERE completed = 1 GROUP BY presentation_order").fetchall():
        order_counts[row["presentation_order"]] = row["c"]

    # Averages
    avgs = conn.execute("""
        SELECT
            AVG(useful_content) as avg_useful_inf,
            AVG(useful_procedural) as avg_useful_coop,
            AVG(effort_content) as avg_effort_inf,
            AVG(effort_procedural) as avg_effort_coop,
            AVG(trust_content) as avg_trust_inf,
            AVG(trust_procedural) as avg_trust_coop
        FROM participants WHERE completed = 1
    """).fetchone()

    def r(v): return round(v, 2) if v else None

    # Preference counts
    pref_counts = {}
    for row in conn.execute("SELECT preference, COUNT(*) as c FROM participants WHERE completed = 1 GROUP BY preference").fetchall():
        pref_counts[row["preference"]] = row["c"]

    # Per-question counts
    question_counts = {}
    for row in conn.execute("SELECT domain, COUNT(*) as c FROM participants WHERE completed = 1 GROUP BY domain").fetchall():
        question_counts[row["domain"]] = row["c"]

    # Individual responses for detail view
    rows = conn.execute("""
        SELECT participant_id, presentation_order, domain,
               useful_content, useful_procedural,
               effort_content, effort_procedural,
               trust_content, trust_procedural,
               preference, comment
        FROM participants WHERE completed = 1 ORDER BY created_at
    """).fetchall()

    responses = []
    for row in rows:
        responses.append({
            "id": row["participant_id"],
            "order": row["presentation_order"],
            "question": row["domain"],
            "useful_inf": row["useful_content"],
            "useful_coop": row["useful_procedural"],
            "effort_inf": row["effort_content"],
            "effort_coop": row["effort_procedural"],
            "trust_inf": row["trust_content"],
            "trust_coop": row["trust_procedural"],
            "preference": row["preference"],
            "comment": row["comment"],
        })

    result = {
        "total_registered": total,
        "completed": completed,
        "order_counts": order_counts,
        "question_counts": question_counts,
        "averages": {
            "useful_informator": r(avgs["avg_useful_inf"]),
            "useful_cooperator": r(avgs["avg_useful_coop"]),
            "effort_informator": r(avgs["avg_effort_inf"]),
            "effort_cooperator": r(avgs["avg_effort_coop"]),
            "trust_informator": r(avgs["avg_trust_inf"]),
            "trust_cooperator": r(avgs["avg_trust_coop"]),
        },
        "preference_counts": pref_counts,
        "responses": responses,
    }
    conn.close()
    return result


@router.get("/results")
def results_page():
    """Serve the results dashboard."""
    return FileResponse(os.path.join(STATIC_DIR, "results.html"))


@router.post("/api/reload_config")
def reload_config():
    """Reload config.json without restarting the server."""
    global CONFIG, GROUPS
    CONFIG = load_config()
    GROUPS = build_groups()
    return {"ok": True, "config": CONFIG}


# ============================================================
# CAPTURE — record a live agent response for later replay
# ============================================================
@router.get("/api/capture")
async def capture_response(agent_id: str, message: str):
    """Call a live agent and save the SSE event stream to responses/<agent_id>.json.

    Requires the TOMMI server to be running and the agent to be available.
    Usage: GET /study/api/capture?agent_id=pisha4&message=List+agreements+with+Netherlands
    """
    try:
        from app import runner
    except Exception as e:
        raise HTTPException(500, f"Cannot access agent runner: {e}")

    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    # Load the agent module (creates instance if not cached)
    try:
        runner._load_agent_module(agent_id)
    except Exception as e:
        raise HTTPException(500, f"Cannot load agent '{agent_id}': {e}")

    events = []
    t_start = time.time()

    try:
        async for event_type, content, session_id in runner.run_query_stream(
            agent_id=agent_id,
            message=message,
            session_id=None,
        ):
            elapsed_ms = int((time.time() - t_start) * 1000)
            if event_type == "status":
                events.append({"event": "status", "data": content, "delay_ms": elapsed_ms})
            elif event_type == "badge":
                escaped = content.replace("\n", "\\n")
                events.append({"event": "badge", "data": escaped, "delay_ms": elapsed_ms})
            elif event_type == "procedural_banner":
                escaped = content.replace("\n", "\\n")
                events.append({"event": "data", "data": escaped, "delay_ms": elapsed_ms})
            elif event_type == "replace":
                escaped = content.replace("\n", "\\n")
                events.append({"event": "replace", "data": escaped, "delay_ms": elapsed_ms})
            else:
                escaped = content.replace("\n", "\\n")
                events.append({"event": "data", "data": escaped, "delay_ms": elapsed_ms})
    except Exception as e:
        raise HTTPException(500, f"Error streaming from agent: {e}")

    # Save to file
    out_path = os.path.join(RESPONSES_DIR, f"{agent_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"agent_id": agent_id, "message": message, "events": events}, f, indent=2, ensure_ascii=False)

    return {
        "ok": True,
        "agent_id": agent_id,
        "message": message,
        "events_count": len(events),
        "file": out_path,
    }


@router.get("/api/list_responses")
def list_responses():
    """List all stored agent responses."""
    files = []
    for f in os.listdir(RESPONSES_DIR):
        if f.endswith(".json"):
            path = os.path.join(RESPONSES_DIR, f)
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            files.append({
                "file": f,
                "agent_id": data.get("agent_id"),
                "message": data.get("message"),
                "events_count": len(data.get("events", [])),
            })
    return files


# ============================================================
# REPLAY — stream a stored response as SSE
# ============================================================
from starlette.responses import StreamingResponse

@router.get("/api/replay")
async def replay_response(agent_id: str):
    """Replay a stored agent response as SSE stream with simulated delays."""
    path = os.path.join(RESPONSES_DIR, f"{agent_id}.json")
    if not os.path.exists(path):
        raise HTTPException(404, f"No stored response for '{agent_id}'. Run /study/api/capture first.")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])

    async def event_generator():
        prev_delay = 0
        for evt in events:
            # Simulate timing gaps (capped at 500ms to keep it snappy)
            delay = evt.get("delay_ms", 0) - prev_delay
            if delay > 0:
                await asyncio.sleep(min(delay, 500) / 1000)
            prev_delay = evt.get("delay_ms", 0)

            event_type = evt.get("event", "data")
            payload = evt.get("data", "")

            if event_type == "data":
                yield f"data: {payload}\n\n"
            else:
                yield f"event: {event_type}\ndata: {payload}\n\n"

        yield "event: done\ndata: complete\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
