"""
AI Transparency Comparative Study - Flask Backend
University of Malaga

Usage:
    pip install flask
    python app.py

Configuration:
    Edit CONFIG below to set agent URLs and study questions.
"""

import os
import csv
import json
import sqlite3
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ============================================================
# CONFIGURATION - Edit these for your study
# ============================================================
CONFIG = {
    # TOMMI Agent URLs on gloria.uma.es
    "AI2_URL": "https://gloria.uma.es/agent/ai2-content-transparency",
    "AI3_URL": "https://gloria.uma.es/agent/ai3-procedural-transparency",

    # Neutral labels shown during interaction (to avoid bias)
    "AI2_LABEL": "Agent A",
    "AI3_LABEL": "Agent B",

    # Descriptions shown to participants (neutral)
    "AI2_DESC": "This agent provides transparency information about its sources using quantitative indicators and citation details.",
    "AI3_DESC": "This agent provides transparency information using colour-coded indicators for different sections of its response.",

    # Two predefined questions (same for all participants, both agents)
    "QUESTIONS": [
        "What are the main research topics on Responsible AI at UNINOVIS universities?",
        "Which researchers at the University of Malaga work on AI ethics?",
    ],
}

DB_PATH = os.path.join(os.path.dirname(__file__), "study_data.db")


# ============================================================
# DATABASE
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
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
            preference TEXT,
            comment TEXT,
            completed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


init_db()


def generate_participant_id():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(8))


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    session.clear()
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start_study():
    """Register participant and assign random order."""
    data = request.get_json()
    email = data.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    conn = get_db()
    existing = conn.execute(
        "SELECT participant_id, completed FROM participants WHERE email = ?",
        (email,),
    ).fetchone()

    if existing and existing["completed"]:
        conn.close()
        return jsonify({"error": "This email has already completed the study. Thank you!"}), 400

    if existing:
        pid = existing["participant_id"]
        row = conn.execute(
            "SELECT * FROM participants WHERE participant_id = ?", (pid,)
        ).fetchone()
        order = row["presentation_order"]
    else:
        pid = generate_participant_id()
        count = conn.execute("SELECT COUNT(*) as c FROM participants").fetchone()["c"]
        order = "AI2_first" if count % 2 == 0 else "AI3_first"

        conn.execute(
            """INSERT INTO participants
               (participant_id, email, created_at, presentation_order)
               VALUES (?, ?, ?, ?)""",
            (pid, email, datetime.utcnow().isoformat(), order),
        )
        conn.commit()

    conn.close()

    session["participant_id"] = pid
    session["order"] = order

    if order == "AI2_first":
        first_url = CONFIG["AI2_URL"]
        first_label = CONFIG["AI2_LABEL"]
        first_desc = CONFIG["AI2_DESC"]
        second_url = CONFIG["AI3_URL"]
        second_label = CONFIG["AI3_LABEL"]
        second_desc = CONFIG["AI3_DESC"]
    else:
        first_url = CONFIG["AI3_URL"]
        first_label = CONFIG["AI3_LABEL"]
        first_desc = CONFIG["AI3_DESC"]
        second_url = CONFIG["AI2_URL"]
        second_label = CONFIG["AI2_LABEL"]
        second_desc = CONFIG["AI2_DESC"]

    return jsonify({
        "participant_id": pid,
        "order": order,
        "agent1": {"url": first_url, "label": first_label, "desc": first_desc},
        "agent2": {"url": second_url, "label": second_label, "desc": second_desc},
        "questions": CONFIG["QUESTIONS"],
    })


@app.route("/api/save_survey", methods=["POST"])
def save_survey():
    """Save background survey answers."""
    pid = session.get("participant_id")
    if not pid:
        return jsonify({"error": "Session expired. Please reload."}), 401

    data = request.get_json()
    conn = get_db()
    conn.execute(
        """UPDATE participants
           SET experience = ?, trust_pre = ?, technical = ?
           WHERE participant_id = ?""",
        (data.get("experience"), data.get("trust_pre"), data.get("technical"), pid),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/save_time", methods=["POST"])
def save_time():
    """Save time spent on an agent interaction."""
    pid = session.get("participant_id")
    if not pid:
        return jsonify({"error": "Session expired."}), 401

    data = request.get_json()
    agent_num = data.get("agent_num")  # 1 or 2
    time_sec = data.get("time_sec", 0)

    conn = get_db()
    col = "time_agent1_sec" if agent_num == 1 else "time_agent2_sec"
    conn.execute(
        f"UPDATE participants SET {col} = ? WHERE participant_id = ?",
        (time_sec, pid),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/save_agent_rating", methods=["POST"])
def save_agent_rating():
    """Save per-agent rating (trust, usefulness, ease) mapped to content/procedural."""
    pid = session.get("participant_id")
    if not pid:
        return jsonify({"error": "Session expired."}), 401

    data = request.get_json()
    agent_num = data.get("agent_num")  # 1 or 2
    trust = data.get("trust")
    useful = data.get("useful")
    ease = data.get("ease")
    order = session.get("order")

    # Map agent_num to content/procedural based on presentation order
    if order == "AI2_first":
        is_content = (agent_num == 1)
    else:
        is_content = (agent_num == 2)

    conn = get_db()
    if is_content:
        conn.execute(
            """UPDATE participants
               SET trust_content = ?, useful_content = ?, ease_content = ?
               WHERE participant_id = ?""",
            (trust, useful, ease, pid),
        )
    else:
        conn.execute(
            """UPDATE participants
               SET trust_procedural = ?, useful_procedural = ?, ease_procedural = ?
               WHERE participant_id = ?""",
            (trust, useful, ease, pid),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/save_comparison", methods=["POST"])
def save_comparison():
    """Save final forced preference and optional comment, mark as completed."""
    pid = session.get("participant_id")
    if not pid:
        return jsonify({"error": "Session expired."}), 401

    data = request.get_json()
    conn = get_db()
    conn.execute(
        """UPDATE participants
           SET preference = ?, comment = ?,
               completed = 1, completed_at = ?
           WHERE participant_id = ?""",
        (
            data.get("preference"),
            data.get("comment", ""),
            datetime.utcnow().isoformat(),
            pid,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/export")
def export_csv():
    """Download all completed results as CSV (researcher access)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM participants WHERE completed = 1 ORDER BY created_at"
    ).fetchall()
    conn.close()

    if not rows:
        return "No completed results yet.", 404

    headers = [
        "participant_id", "email", "created_at", "completed_at",
        "presentation_order", "experience", "trust_pre", "technical",
        "time_agent1_sec", "time_agent2_sec",
        "trust_content", "trust_procedural",
        "useful_content", "useful_procedural",
        "ease_content", "ease_procedural",
        "preference", "comment",
    ]

    def generate():
        yield ",".join(headers) + "\n"
        for row in rows:
            values = []
            for h in headers:
                val = row[h] if row[h] is not None else ""
                # Escape commas and quotes in text fields
                val_str = str(val)
                if "," in val_str or '"' in val_str or "\n" in val_str:
                    val_str = '"' + val_str.replace('"', '""') + '"'
                values.append(val_str)
            yield ",".join(values) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=transparency_study_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@app.route("/api/stats")
def stats():
    """Quick stats for the researcher."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM participants").fetchone()["c"]
    completed = conn.execute("SELECT COUNT(*) as c FROM participants WHERE completed = 1").fetchone()["c"]
    ai2_first = conn.execute("SELECT COUNT(*) as c FROM participants WHERE presentation_order = 'AI2_first' AND completed = 1").fetchone()["c"]
    ai3_first = completed - ai2_first

    # Averages for completed participants
    avgs = conn.execute("""
        SELECT
            AVG(trust_content) as avg_trust_content,
            AVG(trust_procedural) as avg_trust_proc,
            AVG(useful_content) as avg_useful_content,
            AVG(useful_procedural) as avg_useful_proc,
            AVG(ease_content) as avg_ease_content,
            AVG(ease_procedural) as avg_ease_proc
        FROM participants WHERE completed = 1
    """).fetchone()

    pref_counts = {}
    for row in conn.execute("SELECT preference, COUNT(*) as c FROM participants WHERE completed = 1 GROUP BY preference").fetchall():
        pref_counts[row["preference"]] = row["c"]

    conn.close()
    return jsonify({
        "total_registered": total,
        "completed": completed,
        "ai2_first": ai2_first,
        "ai3_first": ai3_first,
        "averages": {
            "trust_content": round(avgs["avg_trust_content"], 2) if avgs["avg_trust_content"] else None,
            "trust_procedural": round(avgs["avg_trust_proc"], 2) if avgs["avg_trust_proc"] else None,
            "useful_content": round(avgs["avg_useful_content"], 2) if avgs["avg_useful_content"] else None,
            "useful_procedural": round(avgs["avg_useful_proc"], 2) if avgs["avg_useful_proc"] else None,
            "ease_content": round(avgs["avg_ease_content"], 2) if avgs["avg_ease_content"] else None,
            "ease_procedural": round(avgs["avg_ease_proc"], 2) if avgs["avg_ease_proc"] else None,
        },
        "preference_counts": pref_counts,
    })


if __name__ == "__main__":
    print(f"\n  Study running at http://localhost:5000")
    print(f"  Export CSV:       http://localhost:5000/api/export")
    print(f"  Quick stats:      http://localhost:5000/api/stats\n")
    app.run(debug=True, port=5000)
