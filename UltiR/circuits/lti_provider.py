"""
Circuit Analysis Trainer — LTI 1.1 Tool

Step-by-step DC circuit analysis exercises. Students solve for total
resistance, current, voltage drops and power — one step at a time,
with immediate feedback. All computations are deterministic (no LLM).

Problem types:
  1. Series resistors
  2. Parallel resistors
  3. Series-parallel combination
  4. Voltage divider
  5. Current divider

Configuration (web/.env):
    CIRCUITS_LTI_KEY=circuits_uma
    CIRCUITS_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/circuits
"""

import json
import os
import random
from pathlib import Path

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_circuits"])

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"

LTI_KEY = os.environ.get("CIRCUITS_LTI_KEY", "circuits_uma")
LTI_SECRET = os.environ.get("CIRCUITS_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()


# ═══════════════════════════════════════════════════════════════════════
# Problem generation
# ═══════════════════════════════════════════════════════════════════════

def _rand_r():
    """Random resistor value: nice values from E12 series."""
    e12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82,
           100, 120, 150, 180, 220, 270, 330, 390, 470, 560, 680, 820,
           1000, 1200, 1500, 1800, 2200, 2700, 3300, 4700]
    return random.choice(e12)


def _rand_v():
    """Random voltage: common supply values."""
    return random.choice([3, 5, 6, 9, 10, 12, 15, 18, 24])


def _fmt(val):
    """Format a number nicely for display."""
    if val >= 1000:
        return f"{val/1000:.2f}".rstrip('0').rstrip('.') + " k"
    if val < 0.01:
        return f"{val*1000:.2f}".rstrip('0').rstrip('.') + " m"
    if val == int(val):
        return str(int(val))
    return f"{val:.4f}".rstrip('0').rstrip('.')


def _generate_series(n_resistors=None):
    n = n_resistors or random.choice([2, 3, 4])
    resistors = [_rand_r() for _ in range(n)]
    v = _rand_v()
    r_total = sum(resistors)
    i_total = v / r_total
    v_drops = [i_total * r for r in resistors]
    p_total = v * i_total

    steps = [
        {
            "id": "r_total",
            "prompt": f"Calculate the total resistance (R_total) of {n} resistors in series: " +
                      ", ".join(f"R{i+1} = {_fmt(r)} Ω" for i, r in enumerate(resistors)),
            "answer": round(r_total, 4),
            "unit": "Ω",
            "hint": "In series: R_total = R1 + R2 + ... + Rn",
            "formula": " + ".join(f"{_fmt(r)}" for r in resistors) + f" = {_fmt(r_total)} Ω",
        },
        {
            "id": "i_total",
            "prompt": f"Calculate the total current (I) with V = {v} V and R_total = {_fmt(r_total)} Ω",
            "answer": round(i_total, 6),
            "unit": "A",
            "hint": "Ohm's law: I = V / R_total",
            "formula": f"{v} / {_fmt(r_total)} = {_fmt(i_total)} A",
        },
    ]
    for i, (r, vd) in enumerate(zip(resistors, v_drops)):
        steps.append({
            "id": f"v_r{i+1}",
            "prompt": f"Calculate the voltage drop across R{i+1} = {_fmt(r)} Ω",
            "answer": round(vd, 6),
            "unit": "V",
            "hint": f"V_R{i+1} = I × R{i+1}",
            "formula": f"{_fmt(i_total)} × {_fmt(r)} = {_fmt(vd)} V",
        })
    steps.append({
        "id": "p_total",
        "prompt": "Calculate the total power dissipated by the circuit",
        "answer": round(p_total, 6),
        "unit": "W",
        "hint": "P = V × I",
        "formula": f"{v} × {_fmt(i_total)} = {_fmt(p_total)} W",
    })

    return {
        "type": "series",
        "title": f"Series Circuit — {n} resistors",
        "description": f"A {v} V source is connected to {n} resistors in series.",
        "components": {"V": v, "resistors": resistors},
        "steps": steps,
    }


def _generate_parallel(n_resistors=None):
    n = n_resistors or random.choice([2, 3])
    resistors = [_rand_r() for _ in range(n)]
    v = _rand_v()
    r_total = 1 / sum(1/r for r in resistors)
    i_total = v / r_total
    i_branches = [v / r for r in resistors]
    p_total = v * i_total

    steps = [
        {
            "id": "r_total",
            "prompt": f"Calculate the total resistance of {n} resistors in parallel: " +
                      ", ".join(f"R{i+1} = {_fmt(r)} Ω" for i, r in enumerate(resistors)),
            "answer": round(r_total, 4),
            "unit": "Ω",
            "hint": "In parallel: 1/R_total = 1/R1 + 1/R2 + ... + 1/Rn",
            "formula": "1 / (" + " + ".join(f"1/{_fmt(r)}" for r in resistors) + f") = {_fmt(r_total)} Ω",
        },
        {
            "id": "i_total",
            "prompt": f"Calculate the total current (I_total) with V = {v} V",
            "answer": round(i_total, 6),
            "unit": "A",
            "hint": "I_total = V / R_total",
            "formula": f"{v} / {_fmt(r_total)} = {_fmt(i_total)} A",
        },
    ]
    for i, (r, ib) in enumerate(zip(resistors, i_branches)):
        steps.append({
            "id": f"i_r{i+1}",
            "prompt": f"Calculate the current through R{i+1} = {_fmt(r)} Ω",
            "answer": round(ib, 6),
            "unit": "A",
            "hint": f"I_R{i+1} = V / R{i+1}",
            "formula": f"{v} / {_fmt(r)} = {_fmt(ib)} A",
        })
    steps.append({
        "id": "p_total",
        "prompt": "Calculate the total power dissipated",
        "answer": round(p_total, 6),
        "unit": "W",
        "hint": "P = V × I_total",
        "formula": f"{v} × {_fmt(i_total)} = {_fmt(p_total)} W",
    })

    return {
        "type": "parallel",
        "title": f"Parallel Circuit — {n} resistors",
        "description": f"A {v} V source is connected to {n} resistors in parallel.",
        "components": {"V": v, "resistors": resistors},
        "steps": steps,
    }


def _generate_series_parallel():
    # Series branch: R1 in series with (R2 || R3)
    r1 = _rand_r()
    r2 = _rand_r()
    r3 = _rand_r()
    v = _rand_v()

    r_parallel = 1 / (1/r2 + 1/r3)
    r_total = r1 + r_parallel
    i_total = v / r_total
    v_r1 = i_total * r1
    v_parallel = i_total * r_parallel
    i_r2 = v_parallel / r2
    i_r3 = v_parallel / r3

    steps = [
        {
            "id": "r_parallel",
            "prompt": f"First, calculate the equivalent resistance of R2 = {_fmt(r2)} Ω and R3 = {_fmt(r3)} Ω in parallel",
            "answer": round(r_parallel, 4),
            "unit": "Ω",
            "hint": "R_parallel = 1 / (1/R2 + 1/R3)  or  R2×R3 / (R2+R3)",
            "formula": f"1 / (1/{_fmt(r2)} + 1/{_fmt(r3)}) = {_fmt(r_parallel)} Ω",
        },
        {
            "id": "r_total",
            "prompt": f"Now calculate R_total: R1 = {_fmt(r1)} Ω in series with the parallel combination",
            "answer": round(r_total, 4),
            "unit": "Ω",
            "hint": "R_total = R1 + R_parallel",
            "formula": f"{_fmt(r1)} + {_fmt(r_parallel)} = {_fmt(r_total)} Ω",
        },
        {
            "id": "i_total",
            "prompt": f"Calculate the total current with V = {v} V",
            "answer": round(i_total, 6),
            "unit": "A",
            "hint": "I = V / R_total",
            "formula": f"{v} / {_fmt(r_total)} = {_fmt(i_total)} A",
        },
        {
            "id": "v_r1",
            "prompt": f"Calculate the voltage drop across R1 = {_fmt(r1)} Ω",
            "answer": round(v_r1, 6),
            "unit": "V",
            "hint": "V_R1 = I × R1",
            "formula": f"{_fmt(i_total)} × {_fmt(r1)} = {_fmt(v_r1)} V",
        },
        {
            "id": "v_parallel",
            "prompt": "Calculate the voltage across the parallel combination (R2 || R3)",
            "answer": round(v_parallel, 6),
            "unit": "V",
            "hint": "V_parallel = I × R_parallel  or  V - V_R1",
            "formula": f"{_fmt(i_total)} × {_fmt(r_parallel)} = {_fmt(v_parallel)} V",
        },
        {
            "id": "i_r2",
            "prompt": f"Calculate the current through R2 = {_fmt(r2)} Ω",
            "answer": round(i_r2, 6),
            "unit": "A",
            "hint": "I_R2 = V_parallel / R2",
            "formula": f"{_fmt(v_parallel)} / {_fmt(r2)} = {_fmt(i_r2)} A",
        },
        {
            "id": "i_r3",
            "prompt": f"Calculate the current through R3 = {_fmt(r3)} Ω",
            "answer": round(i_r3, 6),
            "unit": "A",
            "hint": "I_R3 = V_parallel / R3",
            "formula": f"{_fmt(v_parallel)} / {_fmt(r3)} = {_fmt(i_r3)} A",
        },
    ]

    return {
        "type": "series_parallel",
        "title": "Series-Parallel Circuit",
        "description": f"A {v} V source is connected to R1 = {_fmt(r1)} Ω in series with a parallel combination of R2 = {_fmt(r2)} Ω and R3 = {_fmt(r3)} Ω.",
        "components": {"V": v, "R1": r1, "R2": r2, "R3": r3},
        "steps": steps,
    }


GENERATORS = {
    "series": _generate_series,
    "parallel": _generate_parallel,
    "series_parallel": _generate_series_parallel,
}


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/circuits")
async def circuits_get():
    return RedirectResponse("/lti/circuits/info", status_code=303)


@router.post("/lti/circuits")
async def circuits_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/circuits/practicar",
        redirect_learner="/lti/circuits/practicar",
    )


@router.get("/lti/circuits/test")
async def circuits_test(role: str = "learner"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/circuits/practicar",
        redirect_learner="/lti/circuits/practicar",
        role=role,
    )


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/circuits/info")
async def circuits_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/circuits/practicar")
async def circuits_practicar(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/circuits/api/session")
async def circuits_session(request: Request):
    session = sessions.require(request)
    return {
        "name": session["name"],
        "role": session["role"],
        "course_name": session["course_name"],
        "is_instructor": is_instructor(session),
    }


# ═══════════════════════════════════════════════════════════════════════
# Exercise API
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/circuits/api/exercise")
async def circuits_exercise(
    request: Request,
    type: str = Query("series", regex="^(series|parallel|series_parallel)$"),
    seed: int = Query(None),
):
    sessions.require(request)
    if seed is not None:
        random.seed(seed)
    gen = GENERATORS.get(type, _generate_series)
    problem = gen()
    # Don't send answers to the client
    client_steps = []
    for s in problem["steps"]:
        client_steps.append({
            "id": s["id"],
            "prompt": s["prompt"],
            "unit": s["unit"],
            "hint": s["hint"],
        })
    return {
        "type": problem["type"],
        "title": problem["title"],
        "description": problem["description"],
        "components": problem["components"],
        "steps": client_steps,
        "n_steps": len(client_steps),
    }


@router.post("/lti/circuits/api/check")
async def circuits_check(request: Request):
    """Check a student's answer for one step. Regenerates the problem server-side."""
    sessions.require(request)
    body = await request.json()

    problem_type = body.get("type", "series")
    seed = body.get("seed")
    step_id = body.get("step_id", "")
    student_answer = body.get("answer")

    if student_answer is None:
        raise HTTPException(400, "Missing answer")

    # Regenerate same problem
    if seed is not None:
        random.seed(seed)
    gen = GENERATORS.get(problem_type, _generate_series)
    problem = gen()

    # Find the step
    step = next((s for s in problem["steps"] if s["id"] == step_id), None)
    if not step:
        raise HTTPException(400, f"Unknown step: {step_id}")

    correct = step["answer"]
    # Tolerance: 2% or 0.001 (whichever is larger)
    tolerance = max(abs(correct) * 0.02, 0.001)
    is_correct = abs(float(student_answer) - correct) <= tolerance

    return {
        "correct": is_correct,
        "expected": correct,
        "formula": step["formula"],
        "unit": step["unit"],
    }
