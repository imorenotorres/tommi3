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

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/mobility-planner", tags=["mobility_planner"])


# ── Auth helpers for edit protection ─────────────────────────────────
# Mobility Planner is curated only by content managers, so it uses the
# narrower content-manager-only editor check rather than the general
# EDITOR_ROLES shared by most other apps.

from auth import require_login as _require_auth, require_content_manager_editor as _require_editor, can_edit_as_content_manager as _can_edit_check, user_roles as _user_roles

# The UNINOVIS staff directory is the single source of truth for which
# universities exist and each person's own university — adding/removing a
# university there automatically adds/removes it here, and a content manager
# may only edit the one their own directory entry belongs to.
from apps.wp1.directory.directory import load_data as _load_directory_data, UNIVERSITIES as _DIRECTORY_UNIVERSITIES


def _home_university(username: str) -> str:
    """Return the UNINOVIS partner university acronym of the directory entry
    matching this login email, or "" if there is no such entry or it has no
    university recorded."""
    if not username:
        return ""
    username_lower = username.lower()
    directory_data = _load_directory_data()
    person = next(
        (p for p in directory_data.get("people", []) if p.get("email", "").lower() == username_lower),
        None,
    )
    return (person or {}).get("university") or ""


_DEFAULT_UNIVERSITY_ENTRY = {"sending_period_days": 0, "receiving_period_days": 0, "holidays": [], "confirmed": False}


def _active_universities(data: dict) -> dict:
    """Universities scoped to whatever the directory currently recognizes.

    A university removed from the directory disappears here even if stale
    scheduling data for it remains on disk; one added to the directory
    appears immediately with blank defaults ready to be filled in. Identity
    (name/country) always comes from the directory, not from our own data —
    this file only owns each university's sending/receiving periods and
    holiday calendar.
    """
    stored = data["universities"]
    result = {}
    for code, info in _DIRECTORY_UNIVERSITIES.items():
        entry = dict(_DEFAULT_UNIVERSITY_ENTRY, **stored.get(code, {}))
        entry["name"] = info["name"]
        entry["country"] = info["country"]
        result[code] = entry
    return result


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
    return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers={"Cache-Control": "no-store"})


@router.get("/api/universities")
def universities(session: dict = Depends(_require_auth)):
    data = load_data()
    return {
        acro: {
            "name": info["name"],
            "country": info["country"],
            "sending_period_days": info["sending_period_days"],
            "receiving_period_days": info["receiving_period_days"],
            "confirmed": info.get("confirmed", False),
        }
        for acro, info in _active_universities(data).items()
    }


@router.post("/api/compute")
def compute(body: ComputeRequest, session: dict = Depends(_require_auth)):
    data = load_data()
    data = {**data, "universities": _active_universities(data)}
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
    can_edit = _can_edit_check(session)
    is_superuser = "superuser" in _user_roles(session)
    return {
        "username": session["username"],
        "role": session["role"],
        "can_edit": can_edit,
        "is_superuser": is_superuser,
        # Content managers may only edit their own home university's data;
        # superuser is exempt and may edit any university.
        "home_university": None if is_superuser else _home_university(session["username"]),
    }


# ── Full data endpoint (includes holidays, for editor) ───────────────

@router.get("/api/universities-full")
def universities_full(session: dict = Depends(_require_editor)):
    data = load_data()
    active = _active_universities(data)
    if "superuser" in _user_roles(session):
        return active
    # Content managers only ever see (and can therefore only edit) their own
    # home university's data — not the other partner universities'.
    home = _home_university(session["username"])
    return {home: active[home]} if home and home in active else {}


# ── Save university data ─────────────────────────────────────────────

class HolidayEntry(BaseModel):
    start: str
    end: str
    label: str


class UniversityUpdate(BaseModel):
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
    active_codes = set(_DIRECTORY_UNIVERSITIES.keys())
    is_superuser = "superuser" in _user_roles(session)
    home = None if is_superuser else _home_university(session["username"])

    if not is_superuser:
        for acro in body.universities:
            if acro != home:
                raise HTTPException(status_code=403, detail="You can only edit your own university's data")

    errors = []
    for acro, uni in body.universities.items():
        if acro not in active_codes:
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
        entry = data["universities"].setdefault(acro, {})
        entry["sending_period_days"] = uni.sending_period_days
        entry["receiving_period_days"] = uni.receiving_period_days
        entry["holidays"] = [h.model_dump() for h in uni.holidays]
        entry["confirmed"] = uni.confirmed

    save_data(data)
    return {"ok": True}
