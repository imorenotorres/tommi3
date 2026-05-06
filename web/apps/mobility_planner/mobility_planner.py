"""
Mobility Planner — computes how far in advance a UNINOVIS mobility
activity call must be opened, accounting for each university's
administrative periods and holiday calendars.

Designed to be mounted on the TOMMI FastAPI server.
"""

import json
import os
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/mobility_planner", tags=["mobility_planner"])


# ── Auth helpers for edit protection ─────────────────────────────────

from auth import get_session, ROLES


def _get_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.query_params.get("token")


def _require_auth(request: Request) -> dict:
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def _require_editor(session: dict = Depends(_require_auth)) -> dict:
    if ROLES.get(session["role"], 0) < ROLES.get("tester", 99):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return session


# ── Data I/O ─────────────────────────────────────────────────────────

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def is_in_holiday(d: date, holidays: list) -> str | None:
    """Return the holiday label if *d* falls inside a holiday range, else None."""
    for h in holidays:
        if parse_date(h["start"]) <= d <= parse_date(h["end"]):
            return h["label"]
    return None


def subtract_working_days(start_date: date, num_days: int, holidays: list):
    """Go backwards *num_days* calendar days from *start_date*.

    If any of those calendar days overlap with a holiday period,
    the overlapping days are added on top (i.e. the period is extended
    so that the effective non-holiday duration equals *num_days*).

    Returns (result_date, holiday_days_added, holidays_hit).
    """
    current = start_date
    remaining = num_days
    holiday_days = 0
    holidays_hit = set()

    while remaining > 0:
        current -= timedelta(days=1)
        h_label = is_in_holiday(current, holidays)
        if h_label:
            holiday_days += 1
            holidays_hit.add(h_label)
        else:
            remaining -= 1

    return current, holiday_days, sorted(holidays_hit)


def compute_deadline(activity_date: date, sending_uni: str, receiving_uni: str, data: dict):
    """Compute the call opening date for one sending university.

    Timeline (working backwards from activity_date):
      activity_date
        <- receiving_period (skip receiving-uni holidays)  = docs_arrival_date
        <- sending_period   (skip sending-uni holidays)    = call_open_date
    """
    unis = data["universities"]
    recv = unis[receiving_uni]
    send = unis[sending_uni]

    # Step 1: subtract receiving period (holidays of receiving uni)
    docs_date, recv_hol_days, recv_hols = subtract_working_days(
        activity_date, recv["receiving_period_days"], recv["holidays"]
    )

    # Step 2: subtract sending period (holidays of sending uni)
    call_date, send_hol_days, send_hols = subtract_working_days(
        docs_date, send["sending_period_days"], send["holidays"]
    )

    total_days = (activity_date - call_date).days

    return {
        "sending_university": sending_uni,
        "sending_name": send["name"],
        "sending_confirmed": send.get("confirmed", False),
        "receiving_university": receiving_uni,
        "receiving_name": recv["name"],
        "receiving_confirmed": recv.get("confirmed", False),
        "activity_date": activity_date.isoformat(),
        "call_open_date": call_date.isoformat(),
        "docs_arrival_date": docs_date.isoformat(),
        "total_calendar_days": total_days,
        "sending_period_days": send["sending_period_days"],
        "sending_holiday_days_added": send_hol_days,
        "sending_holidays_hit": send_hols,
        "receiving_period_days": recv["receiving_period_days"],
        "receiving_holiday_days_added": recv_hol_days,
        "receiving_holidays_hit": recv_hols,
    }


# ── Models ─────────────────────────────────────────────────────────────

class ComputeRequest(BaseModel):
    receiving_university: str
    sending_universities: List[str]
    activity_date: str


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/universities")
def universities():
    data = load_data()
    return {
        acro: {
            "name": info["name"],
            "country": info["country"],
            "sending_period_days": info["sending_period_days"],
            "receiving_period_days": info["receiving_period_days"],
            "confirmed": info.get("confirmed", False),
        }
        for acro, info in data["universities"].items()
    }


@router.post("/api/compute")
def compute(body: ComputeRequest):
    data = load_data()
    unis = data["universities"]

    if body.receiving_university not in unis:
        raise HTTPException(400, f"Unknown receiving university: {body.receiving_university}")
    for s in body.sending_universities:
        if s not in unis:
            raise HTTPException(400, f"Unknown sending university: {s}")

    activity_date = parse_date(body.activity_date)
    results = [
        compute_deadline(activity_date, s, body.receiving_university, data)
        for s in body.sending_universities
    ]
    results.sort(key=lambda r: r["call_open_date"])

    return {"results": results}


# ── Auth check ───────────────────────────────────────────────────────

@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    can_edit = ROLES.get(session["role"], 0) >= ROLES.get("tester", 99)
    return {"username": session["username"], "role": session["role"], "can_edit": can_edit}


# ── Full data endpoint (includes holidays, for editor) ───────────────

@router.get("/api/universities-full")
def universities_full(session: dict = Depends(_require_editor)):
    data = load_data()
    return data["universities"]


# ── Save university data ─────────────────────────────────────────────

class HolidayEntry(BaseModel):
    start: str
    end: str
    label: str


class UniversityUpdate(BaseModel):
    name: str
    country: str
    sending_period_days: int
    receiving_period_days: int
    holidays: list[HolidayEntry] = []
    confirmed: bool = False


class BatchUniversitiesBody(BaseModel):
    universities: dict[str, UniversityUpdate]


@router.put("/api/universities")
def update_universities(
    body: BatchUniversitiesBody,
    session: dict = Depends(_require_editor),
):
    data = load_data()
    errors = []

    for acro, uni in body.universities.items():
        if acro not in data["universities"]:
            errors.append(f"Unknown university: {acro}")
            continue
        if uni.sending_period_days < 0 or uni.receiving_period_days < 0:
            errors.append(f"{acro}: period days cannot be negative")
            continue
        # Validate holiday dates
        for h in uni.holidays:
            try:
                s = date.fromisoformat(h.start)
                e = date.fromisoformat(h.end)
                if s > e:
                    errors.append(f"{acro}: holiday '{h.label}' start is after end")
            except ValueError as ex:
                errors.append(f"{acro}: invalid date in holiday '{h.label}' — {ex}")

    if errors:
        raise HTTPException(400, detail={"errors": errors})

    for acro, uni in body.universities.items():
        entry = data["universities"][acro]
        entry["name"] = uni.name
        entry["country"] = uni.country
        entry["sending_period_days"] = uni.sending_period_days
        entry["receiving_period_days"] = uni.receiving_period_days
        entry["holidays"] = [h.model_dump() for h in uni.holidays]
        entry["confirmed"] = uni.confirmed

    save_data(data)
    return {"ok": True}
