"""
Statistics Explorer — LTI 1.1 Tool

Interactive statistics exercises: descriptive statistics, confidence
intervals, and one-sample z-test. All computations are deterministic
(no LLM). Includes an interactive normal distribution explorer.

Exercise types:
  1. descriptive  — mean, median, population variance, std dev
  2. ic           — confidence interval for μ (σ known)
  3. z_test       — one-sample z-test, two-tailed (σ known)

Configuration (web/.env):
    STATS_LTI_KEY=stats_uma
    STATS_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/stats
"""

import math
import os
import random
from pathlib import Path

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_stats"])

_APP_DIR = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"

LTI_KEY = os.environ.get("STATS_LTI_KEY", "stats_uma")
LTI_SECRET = os.environ.get("STATS_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()


# ═══════════════════════════════════════════════════════════════════════
# Math helpers
# ═══════════════════════════════════════════════════════════════════════

def _r(x, decimals=4):
    return round(float(x), decimals)

def _norm_cdf(x):
    """Standard normal CDF  Φ(x)."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

_Z_STAR = {90: 1.645, 95: 1.960, 99: 2.576}
_Z_BETA = {0.80: 0.842, 0.85: 1.036, 0.90: 1.282, 0.95: 1.645}


# ═══════════════════════════════════════════════════════════════════════
# Exercise generators
# ═══════════════════════════════════════════════════════════════════════

def _generate_descriptive():
    n = random.randint(6, 10)
    raw = [random.randint(10, 99) for _ in range(n)]
    data = sorted(raw)

    mean = sum(data) / n
    mid = n // 2
    median = (data[mid - 1] + data[mid]) / 2 if n % 2 == 0 else float(data[mid])
    variance = sum((x - mean) ** 2 for x in data) / n
    std = math.sqrt(variance)

    steps = [
        {
            "id": "mean",
            "prompt": "Calculate the mean (x̄)",
            "answer": _r(mean),
            "unit": "",
            "hint": f"x̄ = (Σxᵢ) / n  — add all values and divide by {n}",
            "formula": f"({' + '.join(str(x) for x in data)}) / {n} = {_r(mean)}",
        },
        {
            "id": "median",
            "prompt": "Calculate the median",
            "answer": _r(median),
            "unit": "",
            "hint": "Sort the data, take the middle value (or average of the two middle values)",
            "formula": f"Sorted: {data}  →  Median = {_r(median)}",
        },
        {
            "id": "variance",
            "prompt": "Calculate the population variance (σ²)",
            "answer": _r(variance),
            "unit": "",
            "hint": "σ² = Σ(xᵢ − x̄)² / n",
            "formula": f"Σ(xᵢ − {_r(mean)})² / {n} = {_r(variance)}",
        },
        {
            "id": "std",
            "prompt": "Calculate the population standard deviation (σ)",
            "answer": _r(std),
            "unit": "",
            "hint": "σ = √σ²",
            "formula": f"√{_r(variance)} = {_r(std)}",
        },
    ]

    return {
        "type": "descriptive",
        "title": "Descriptive Statistics",
        "description": f"Dataset (n = {n}):  {raw}",
        "steps": steps,
    }


def _generate_ic():
    sigma = random.choice([5, 8, 10, 12, 15, 20])
    n = random.choice([25, 36, 49, 64, 100])
    conf = random.choice([90, 95, 99])
    z_star = _Z_STAR[conf]
    mu_approx = random.randint(50, 200)
    x_bar = round(mu_approx + random.uniform(-sigma / 4, sigma / 4), 1)

    se = sigma / math.sqrt(n)
    me = z_star * se
    lower = x_bar - me
    upper = x_bar + me

    steps = [
        {
            "id": "z_star",
            "prompt": f"Find the critical value z* for a {conf}% confidence interval",
            "answer": _r(z_star),
            "unit": "",
            "hint": f"For {conf}% CI: z* = {z_star}  (α/2 = {round((1 - conf / 100) / 2, 3)})",
            "formula": f"z* = {z_star}",
        },
        {
            "id": "se",
            "prompt": f"Calculate the standard error  SE = σ / √n  (σ = {sigma}, n = {n})",
            "answer": _r(se),
            "unit": "",
            "hint": "SE = σ / √n",
            "formula": f"{sigma} / √{n} = {sigma} / {_r(math.sqrt(n))} = {_r(se)}",
        },
        {
            "id": "me",
            "prompt": "Calculate the margin of error  ME = z* × SE",
            "answer": _r(me),
            "unit": "",
            "hint": "ME = z* × SE",
            "formula": f"{z_star} × {_r(se)} = {_r(me)}",
        },
        {
            "id": "lower",
            "prompt": f"Calculate the lower bound  (x̄ = {x_bar})",
            "answer": _r(lower),
            "unit": "",
            "hint": "Lower = x̄ − ME",
            "formula": f"{x_bar} − {_r(me)} = {_r(lower)}",
        },
        {
            "id": "upper",
            "prompt": "Calculate the upper bound",
            "answer": _r(upper),
            "unit": "",
            "hint": "Upper = x̄ + ME",
            "formula": f"{x_bar} + {_r(me)} = {_r(upper)}",
        },
    ]

    return {
        "type": "ic",
        "title": f"{conf}% Confidence Interval for μ",
        "description": (
            f"A sample of n = {n} observations has x̄ = {x_bar}. "
            f"The population standard deviation is σ = {sigma}. "
            f"Construct a {conf}% confidence interval for μ."
        ),
        "steps": steps,
    }


def _generate_z_test():
    mu_0 = random.choice([50, 100, 120, 150, 200, 500])
    sigma = random.choice([10, 15, 20, 25])
    n = random.choice([25, 36, 49, 64, 100])
    alpha = random.choice([0.05, 0.01])
    z_crit = _Z_STAR[95] if alpha == 0.05 else _Z_STAR[99]

    reject = random.choice([True, False])
    if reject:
        z_signed = random.choice([-1, 1]) * round(random.uniform(z_crit + 0.3, z_crit + 2.0), 2)
    else:
        z_signed = round(random.uniform(-(z_crit - 0.5), z_crit - 0.5), 2)

    se = sigma / math.sqrt(n)
    x_bar = round(mu_0 + z_signed * se, 2)
    z_actual = (x_bar - mu_0) / se
    reject_actual = abs(z_actual) > z_crit

    steps = [
        {
            "id": "se",
            "prompt": f"Calculate the standard error  SE = σ / √n  (σ = {sigma}, n = {n})",
            "answer": _r(se),
            "unit": "",
            "hint": "SE = σ / √n",
            "formula": f"{sigma} / √{n} = {_r(se)}",
        },
        {
            "id": "z_stat",
            "prompt": f"Calculate the test statistic  z = (x̄ − μ₀) / SE  (x̄ = {x_bar}, μ₀ = {mu_0})",
            "answer": _r(z_actual),
            "unit": "",
            "hint": "z = (x̄ − μ₀) / SE",
            "formula": f"({x_bar} − {mu_0}) / {_r(se)} = {_r(z_actual)}",
        },
        {
            "id": "z_crit",
            "prompt": f"Find the critical value z* for a two-tailed test at α = {alpha}",
            "answer": _r(z_crit),
            "unit": "",
            "hint": f"Two-tailed at α = {alpha}: z* = z_{{α/2}} = {z_crit}",
            "formula": f"z* = {z_crit}",
        },
        {
            "id": "reject",
            "prompt": "Should we reject H₀? (1 = Yes / 0 = No)",
            "answer": 1 if reject_actual else 0,
            "unit": "",
            "hint": f"Reject H₀ if |z| > z*  →  |{_r(z_actual)}| {'>' if reject_actual else '≤'} {z_crit}",
            "formula": f"|z| = {_r(abs(z_actual))} {'>' if reject_actual else '≤'} {z_crit}  →  {'Reject H₀' if reject_actual else 'Fail to reject H₀'}",
            "input_type": "binary",
        },
    ]

    return {
        "type": "z_test",
        "title": "One-Sample Z-Test (two-tailed)",
        "description": (
            f"Test H₀: μ = {mu_0}  vs  H₁: μ ≠ {mu_0}  at α = {alpha}. "
            f"A sample of n = {n} has x̄ = {x_bar} and σ = {sigma} (known)."
        ),
        "steps": steps,
    }


def _generate_power():
    """Calculate statistical power given n, δ, σ, α."""
    mu_0 = random.choice([100, 120, 150, 200])
    sigma = random.choice([10, 15, 20])
    delta = random.choice([3, 4, 5, 6, 8, 10])
    mu_1 = mu_0 + delta
    n = random.choice([25, 36, 49, 64, 100])
    alpha = random.choice([0.05, 0.01])
    z_crit = _Z_STAR[95] if alpha == 0.05 else _Z_STAR[99]

    se = sigma / math.sqrt(n)
    lam = delta / se          # non-centrality parameter λ
    power = 1 - _norm_cdf(z_crit - lam)
    beta = 1 - power

    steps = [
        {
            "id": "se",
            "prompt": f"Calculate the standard error  SE = σ / √n  (σ = {sigma}, n = {n})",
            "answer": _r(se),
            "unit": "",
            "hint": "SE = σ / √n  — the standard deviation of the sampling distribution of x̄",
            "formula": f"{sigma} / √{n} = {_r(se)}",
        },
        {
            "id": "z_crit",
            "prompt": f"Find the critical value z* for α = {alpha} (two-tailed)",
            "answer": _r(z_crit),
            "unit": "",
            "hint": f"Two-tailed at α = {alpha}: z* = {z_crit}",
            "formula": f"z* = {z_crit}",
        },
        {
            "id": "lambda",
            "prompt": f"Calculate the non-centrality parameter  λ = (μ₁ − μ₀) / SE  (μ₁ = {mu_1}, μ₀ = {mu_0})",
            "answer": _r(lam),
            "unit": "",
            "hint": "λ = δ / SE  where δ = μ₁ − μ₀  — how many SEs apart are the two means?",
            "formula": f"{delta} / {_r(se)} = {_r(lam)}",
        },
        {
            "id": "power",
            "prompt": "Calculate power = 1 − Φ(z* − λ)  [Φ = standard normal CDF]",
            "answer": _r(power),
            "unit": "",
            "hint": "Power = 1 − Φ(z* − λ).  If z* − λ is negative, power > 0.5",
            "formula": f"1 − Φ({_r(z_crit)} − {_r(lam)}) = 1 − Φ({_r(z_crit - lam)}) = {_r(power)}",
        },
    ]

    return {
        "type": "power",
        "title": "Statistical Power",
        "description": (
            f"Test H₀: μ = {mu_0}  vs  H₁: μ = {mu_1}  at α = {alpha}. "
            f"n = {n},  σ = {sigma} (known).  Calculate the power of the test."
        ),
        "steps": steps,
    }


def _generate_sample_size():
    """Calculate required n for a desired power level."""
    sigma = random.choice([10, 15, 20])
    delta = random.choice([4, 5, 6, 8, 10])
    desired_power = random.choice([0.80, 0.90])
    alpha = random.choice([0.05, 0.01])
    z_crit = _Z_STAR[95] if alpha == 0.05 else _Z_STAR[99]
    z_beta = _Z_BETA[desired_power]

    n_exact = ((z_crit + z_beta) * sigma / delta) ** 2
    n_required = math.ceil(n_exact)

    steps = [
        {
            "id": "z_crit",
            "prompt": f"Find z_α/2 for α = {alpha} (two-tailed)",
            "answer": _r(z_crit),
            "unit": "",
            "hint": f"For α = {alpha}: z_α/2 = {z_crit}",
            "formula": f"z_α/2 = {z_crit}",
        },
        {
            "id": "z_beta",
            "prompt": f"Find z_β for desired power = {int(desired_power * 100)}%",
            "answer": _r(z_beta),
            "unit": "",
            "hint": f"Power = {int(desired_power * 100)}%  →  β = {round(1 - desired_power, 2)}  →  z_β = {z_beta}",
            "formula": f"z_β = {z_beta}",
        },
        {
            "id": "n_exact",
            "prompt": f"Calculate  n = ((z_α/2 + z_β) × σ / δ)²  (σ = {sigma}, δ = {delta})",
            "answer": _r(n_exact),
            "unit": "",
            "hint": "n = ((z_α/2 + z_β) × σ / δ)²  — the sample size formula for a z-test",
            "formula": f"(({z_crit} + {z_beta}) × {sigma} / {delta})² = {_r(n_exact)}",
        },
        {
            "id": "n_required",
            "prompt": "Round up to the nearest integer (always ceiling — rounding down gives insufficient power)",
            "answer": n_required,
            "unit": "",
            "hint": "Use ⌈n_exact⌉ — always round UP, never down",
            "formula": f"⌈{_r(n_exact)}⌉ = {n_required}",
        },
    ]

    return {
        "type": "sample_size",
        "title": f"Required Sample Size (Power = {int(desired_power * 100)}%)",
        "description": (
            f"You want {int(desired_power * 100)}% power to detect δ = {delta} "
            f"at α = {alpha}, with σ = {sigma}. "
            f"What is the minimum sample size?"
        ),
        "steps": steps,
    }


GENERATORS = {
    "descriptive": _generate_descriptive,
    "ic": _generate_ic,
    "z_test": _generate_z_test,
    "power": _generate_power,
    "sample_size": _generate_sample_size,
}


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/stats")
async def stats_get():
    return RedirectResponse("/lti/stats/info", status_code=303)


@router.post("/lti/stats")
async def stats_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/stats/practicar",
        redirect_learner="/lti/stats/practicar",
    )


@router.get("/lti/stats/test")
async def stats_test(role: str = "learner"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/stats/practicar",
        redirect_learner="/lti/stats/practicar",
        role=role,
    )


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/stats/info")
async def stats_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/stats/practicar")
async def stats_practicar(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/stats/api/session")
async def stats_session(request: Request):
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

@router.get("/lti/stats/api/exercise")
async def stats_exercise(
    request: Request,
    type: str = Query("descriptive", regex="^(descriptive|ic|z_test|power|sample_size)$"),
    seed: int = Query(None),
):
    sessions.require(request)
    if seed is not None:
        random.seed(seed)
    problem = GENERATORS.get(type, _generate_descriptive)()
    # Strip answers before sending to client
    client_steps = [
        {k: v for k, v in s.items() if k not in ("answer", "formula")}
        for s in problem["steps"]
    ]
    return {
        "type": problem["type"],
        "title": problem["title"],
        "description": problem["description"],
        "steps": client_steps,
        "n_steps": len(client_steps),
    }


@router.post("/lti/stats/api/check")
async def stats_check(request: Request):
    """Check one step; regenerates the problem server-side using the seed."""
    sessions.require(request)
    body = await request.json()

    problem_type = body.get("type", "descriptive")
    seed = body.get("seed")
    step_id = body.get("step_id", "")
    student_answer = body.get("answer")

    if student_answer is None:
        raise HTTPException(400, "Missing answer")

    if seed is not None:
        random.seed(seed)
    problem = GENERATORS.get(problem_type, _generate_descriptive)()

    step = next((s for s in problem["steps"] if s["id"] == step_id), None)
    if not step:
        raise HTTPException(400, f"Unknown step: {step_id}")

    correct = step["answer"]
    if step_id == "reject":
        is_correct = abs(float(student_answer) - correct) < 0.5
    else:
        tolerance = max(abs(correct) * 0.02, 0.005)
        is_correct = abs(float(student_answer) - correct) <= tolerance

    return {
        "correct": is_correct,
        "expected": correct,
        "formula": step["formula"],
        "unit": step["unit"],
    }
