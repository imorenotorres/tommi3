"""
Bloom's Taxonomy Trainer — LTI 1.1 Tool

Three exercise types built around Bloom's revised taxonomy (Anderson &
Krathwohl, 2001). All grading is deterministic — no LLM required.

Exercise types:
  1. classify    — given a learning objective, identify its Bloom's level
  2. verb_match  — given a verb, identify its level and match an objective
  3. design      — given a target level, pick the matching objective; then
                   identify the objective at the adjacent level

Configuration (web/.env):
    BLOOM_LTI_KEY=bloom_uma
    BLOOM_LTI_SECRET=<shared_secret>

Moodle setup:
    Tool URL: https://gloria.uma.es/lti/bloom
"""

import os
import random
from pathlib import Path

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from UltiR.lti_common import (
    LTISessionStore, is_instructor, lti_launch, lti_test_launch,
)

router = APIRouter(tags=["lti_bloom"])

_APP_DIR   = Path(__file__).parent
_STATIC_DIR = _APP_DIR / "static"

LTI_KEY    = os.environ.get("BLOOM_LTI_KEY",    "bloom_uma")
LTI_SECRET = os.environ.get("BLOOM_LTI_SECRET", "change_this_secret_in_env")

sessions = LTISessionStore()


# ═══════════════════════════════════════════════════════════════════════
# Taxonomy data
# ═══════════════════════════════════════════════════════════════════════

LEVELS = {
    1: {"name": "Remember",   "color": "#64748b"},
    2: {"name": "Understand", "color": "#3b82f6"},
    3: {"name": "Apply",      "color": "#10b981"},
    4: {"name": "Analyze",    "color": "#f59e0b"},
    5: {"name": "Evaluate",   "color": "#f97316"},
    6: {"name": "Create",     "color": "#8b5cf6"},
}

VERBS = {
    1: ["define", "list", "recall", "identify", "name", "state", "recognize",
        "label", "enumerate", "memorize", "reproduce", "match"],
    2: ["explain", "summarize", "classify", "describe", "interpret", "compare",
        "outline", "discuss", "paraphrase", "illustrate", "predict", "translate"],
    3: ["apply", "demonstrate", "implement", "use", "solve", "calculate",
        "operate", "practice", "show", "carry out", "execute", "produce"],
    4: ["analyze", "differentiate", "examine", "distinguish", "deconstruct",
        "break down", "organize", "test", "inspect", "relate", "attribute"],
    5: ["evaluate", "judge", "justify", "critique", "assess", "recommend",
        "defend", "argue", "select", "prioritize", "appraise", "weigh"],
    6: ["design", "create", "develop", "formulate", "plan", "produce",
        "compose", "construct", "generate", "invent", "devise", "draft"],
}

# Each entry: (verb, rest_of_objective)
OBJECTIVES = {
    1: [
        ("define",      "the concept of formative assessment"),
        ("list",        "the main characteristics of constructivist learning"),
        ("identify",    "the six levels of Bloom's revised taxonomy"),
        ("recall",      "the four stages of Piaget's cognitive development theory"),
        ("name",        "three inclusive education strategies based on UDL principles"),
        ("label",       "the key components of a structured lesson plan"),
        ("state",       "the differences between qualitative and quantitative research"),
        ("recognize",   "examples of summative and formative assessment in a given list"),
        ("enumerate",   "the competences included in the national curriculum framework"),
        ("reproduce",   "the main theories of motivation applied to educational settings"),
    ],
    2: [
        ("explain",     "the role of the zone of proximal development in guided learning"),
        ("summarize",   "the main principles of cooperative learning"),
        ("describe",    "how socioeconomic context can influence student motivation"),
        ("compare",     "direct instruction with inquiry-based learning approaches"),
        ("interpret",   "the results of a diagnostic assessment"),
        ("classify",    "assessment methods according to their primary purpose"),
        ("illustrate",  "the concept of scaffolding using a classroom example"),
        ("outline",     "the main phases of the backward design process"),
        ("discuss",     "the implications of neuroscience research for classroom practice"),
        ("predict",     "the likely impact of a given intervention on student engagement"),
    ],
    3: [
        ("apply",       "Bloom's taxonomy to write measurable objectives for a lesson on fractions"),
        ("demonstrate", "a classroom management strategy during a micro-teaching session"),
        ("use",         "cooperative learning techniques to plan a structured group activity"),
        ("implement",   "UDL principles to adapt an existing lesson plan for a diverse class"),
        ("solve",       "a classroom conflict using restorative dialogue techniques"),
        ("calculate",   "reliability indices from a set of teacher-made test items"),
        ("practice",    "a structured observation protocol during a school placement visit"),
        ("carry out",   "a needs analysis for a specific educational context"),
        ("show",        "how to align assessment tasks with learning objectives in a course"),
        ("execute",     "a differentiated instruction plan for a mixed-ability group"),
    ],
    4: [
        ("analyze",     "the factors contributing to school failure in a given case study"),
        ("differentiate","between behaviourist and constructivist feedback approaches"),
        ("examine",     "how assessment design influences students' learning strategies"),
        ("deconstruct", "a lesson plan to identify its underlying pedagogical assumptions"),
        ("distinguish", "between formative feedback and evaluative feedback in practice"),
        ("break down",  "a complex competence into observable and measurable indicators"),
        ("inspect",     "a set of student work samples to identify patterns of misconception"),
        ("relate",      "theoretical models of motivation to observed classroom behaviours"),
        ("attribute",   "differences in student outcomes to specific instructional variables"),
        ("test",        "the validity of assessment instruments used in a given programme"),
    ],
    5: [
        ("evaluate",    "the effectiveness of an educational intervention using pre- and post-test data"),
        ("judge",       "the appropriateness of an assessment method for a specific learning objective"),
        ("justify",     "the pedagogical choices made in a lesson plan"),
        ("critique",    "a published research study in terms of its methodology and conclusions"),
        ("recommend",   "evidence-based strategies to improve engagement in a low-motivation class"),
        ("assess",      "the quality of learning objectives against alignment and measurability criteria"),
        ("argue",       "for or against the use of standardized testing in primary education"),
        ("prioritize",  "interventions for a student with learning difficulties based on assessment data"),
        ("defend",      "the use of portfolio assessment in a competence-based curriculum"),
        ("weigh",       "the ethical implications of using AI tools in student assessment"),
    ],
    6: [
        ("design",      "an inclusive unit of work applying UDL principles for a diverse classroom"),
        ("create",      "an assessment rubric aligned with the learning objectives of a given course"),
        ("develop",     "a professional development plan for a newly qualified teacher"),
        ("formulate",   "a research question and propose an appropriate methodology to address it"),
        ("produce",     "a portfolio of differentiated teaching resources for a specific subject"),
        ("plan",        "a parent engagement strategy for a school with low family involvement"),
        ("compose",     "a reflective report on the effectiveness of your teaching practice placement"),
        ("generate",    "a set of project-based learning activities for a cross-curricular unit"),
        ("invent",      "a classroom routine that supports metacognitive skill development"),
        ("draft",       "a complete programme evaluation report based on collected evidence"),
    ],
}


def _opts_html(options):
    """Format a list of (verb, rest) tuples as A/B/C/D HTML options."""
    letters = "ABCD"
    return "<br>".join(
        f"<strong>{letters[i]})</strong> The student will be able to "
        f"<strong>{o[0]}</strong> {o[1]}."
        for i, o in enumerate(options)
    )


def _four_opts(correct_level, seed_state=None):
    """Return (options, correct_position_1indexed) with 1 correct + 3 distractors."""
    correct = random.choice(OBJECTIVES[correct_level])
    wrong_levels = random.sample([l for l in range(1, 7) if l != correct_level], 3)
    wrong = [random.choice(OBJECTIVES[l]) for l in wrong_levels]
    opts = [correct] + wrong
    random.shuffle(opts)
    pos = opts.index(correct) + 1
    return opts, pos


# ═══════════════════════════════════════════════════════════════════════
# Exercise generators
# ═══════════════════════════════════════════════════════════════════════

def _generate_classify():
    """Given an objective, identify the Bloom's level; then match a verb."""
    level = random.randint(1, 6)
    verb, rest = random.choice(OBJECTIVES[level])

    # Step 2: find a verb at the same level + 3 distractors
    correct_verb = random.choice(VERBS[level])
    wrong_verbs = [random.choice(VERBS[l]) for l in random.sample([l for l in range(1, 7) if l != level], 3)]
    verb_opts = [correct_verb] + wrong_verbs
    random.shuffle(verb_opts)
    verb_pos = verb_opts.index(correct_verb) + 1
    verb_opts_text = " / ".join(f"<strong>{'ABCD'[i]})</strong> {v}" for i, v in enumerate(verb_opts))

    steps = [
        {
            "id": "level",
            "prompt": (
                f"Classify this learning objective into Bloom's revised taxonomy:"
                f"<br><br>"
                f"<em>\"The student will be able to <strong>{verb}</strong> {rest}.\"</em>"
                f"<br><br>What is the Bloom's level?"
            ),
            "answer": level,
            "unit": "",
            "hint": f'Focus on the verb <strong>"{verb}"</strong>. What cognitive operation does it require?',
            "formula": f'Level {level}: <strong>{LEVELS[level]["name"]}</strong> — "{verb}" signals {LEVELS[level]["name"].lower()}.',
            "input_type": "level",
        },
        {
            "id": "verb",
            "prompt": (
                f"Which of these verbs belongs to the <strong>same Bloom's level</strong> as \"{verb}\"?"
                f"<br><br>{verb_opts_text}"
            ),
            "answer": verb_pos,
            "unit": "",
            "hint": f'Level {level} ({LEVELS[level]["name"]}) uses verbs such as: {", ".join(VERBS[level][:6])}.',
            "formula": f'"{correct_verb}" → Level {level}: {LEVELS[level]["name"]}.',
            "input_type": "choice",
        },
    ]

    return {
        "type": "classify",
        "title": "Classify the Objective",
        "description": "Read the objective, identify the Bloom's level, then confirm with a matching verb.",
        "steps": steps,
    }


def _generate_verb_match():
    """Given a verb, identify its level; then pick an objective that uses it."""
    level = random.randint(1, 6)
    verb = random.choice(VERBS[level])

    # Step 2: pick an objective at this level vs distractors
    opts, pos = _four_opts(level)
    opts_html = _opts_html(opts)

    steps = [
        {
            "id": "level",
            "prompt": (
                f"Which Bloom's level does the verb <strong>\"{verb}\"</strong> belong to?"
            ),
            "answer": level,
            "unit": "",
            "hint": f'Think about what cognitive operation "{verb}" requires. Is it recall, understanding, application, analysis, evaluation, or creation?',
            "formula": f'"{verb}" → Level {level}: {LEVELS[level]["name"]}.',
            "input_type": "level",
        },
        {
            "id": "objective",
            "prompt": (
                f"Which of these objectives is at <strong>Level {level} ({LEVELS[level]['name']})</strong>?"
                f"<br><br>{opts_html}"
            ),
            "answer": pos,
            "unit": "",
            "hint": f'Look for the objective whose verb signals {LEVELS[level]["name"].lower()}. Key verbs: {", ".join(VERBS[level][:5])}.',
            "formula": f'Level {level} ({LEVELS[level]["name"]}): "{opts[pos-1][0]}" is a {LEVELS[level]["name"].lower()} verb.',
            "input_type": "choice",
        },
    ]

    return {
        "type": "verb_match",
        "title": "Classify the Verb",
        "description": "Identify the Bloom's level of the verb, then pick an objective that reflects it.",
        "steps": steps,
    }


def _generate_design():
    """Pick the objective matching a target level; then identify the adjacent level."""
    level = random.randint(1, 6)

    # Step 1: pick the level-X objective from 4 options
    opts1, pos1 = _four_opts(level)
    opts1_html = _opts_html(opts1)

    # Step 2: adjacent level
    next_level = level + 1 if level < 6 else level - 1
    direction  = "higher" if level < 6 else "lower"
    opts2, pos2 = _four_opts(next_level)
    opts2_html = _opts_html(opts2)

    steps = [
        {
            "id": "pick",
            "prompt": (
                f"Select the objective that is at "
                f"<strong>Level {level}: {LEVELS[level]['name']}</strong> of Bloom's Taxonomy:"
                f"<br><br>{opts1_html}"
            ),
            "answer": pos1,
            "unit": "",
            "hint": f'Level {level} ({LEVELS[level]["name"]}) verbs: {", ".join(VERBS[level][:6])}.',
            "formula": (
                f'Level {level} ({LEVELS[level]["name"]}): '
                f'"{opts1[pos1-1][0]}" is a {LEVELS[level]["name"].lower()} verb.'
            ),
            "input_type": "choice",
        },
        {
            "id": "adjacent",
            "prompt": (
                f"Good. Now identify an objective one level {direction} — "
                f"<strong>Level {next_level}: {LEVELS[next_level]['name']}</strong>:"
                f"<br><br>{opts2_html}"
            ),
            "answer": pos2,
            "unit": "",
            "hint": f'Level {next_level} ({LEVELS[next_level]["name"]}) verbs: {", ".join(VERBS[next_level][:6])}.',
            "formula": (
                f'Level {next_level} ({LEVELS[next_level]["name"]}): '
                f'"{opts2[pos2-1][0]}" is a {LEVELS[next_level]["name"].lower()} verb.'
            ),
            "input_type": "choice",
        },
    ]

    return {
        "type": "design",
        "title": "Identify the Level — and Escalate",
        "description": (
            f"Step 1: find the Level {level} ({LEVELS[level]['name']}) objective. "
            f"Step 2: find the {direction} adjacent level."
        ),
        "steps": steps,
    }


GENERATORS = {
    "classify":   _generate_classify,
    "verb_match": _generate_verb_match,
    "design":     _generate_design,
}


# ═══════════════════════════════════════════════════════════════════════
# LTI Launch
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/bloom")
async def bloom_get():
    return RedirectResponse("/lti/bloom/info", status_code=303)


@router.post("/lti/bloom")
async def bloom_launch(request: Request):
    return await lti_launch(
        request, LTI_KEY, LTI_SECRET, sessions,
        redirect_instructor="/lti/bloom/practicar",
        redirect_learner="/lti/bloom/practicar",
    )


@router.get("/lti/bloom/test")
async def bloom_test(role: str = "learner"):
    return await lti_test_launch(
        sessions,
        redirect_instructor="/lti/bloom/practicar",
        redirect_learner="/lti/bloom/practicar",
        role=role,
    )


# ═══════════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════════

@router.get("/lti/bloom/info")
async def bloom_info():
    return HTMLResponse((_STATIC_DIR / "info.html").read_text(encoding="utf-8"))


@router.get("/lti/bloom/practicar")
async def bloom_practicar(request: Request):
    sessions.require(request)
    return HTMLResponse((_STATIC_DIR / "practicar.html").read_text(encoding="utf-8"))


@router.get("/lti/bloom/api/session")
async def bloom_session(request: Request):
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

@router.get("/lti/bloom/api/exercise")
async def bloom_exercise(
    request: Request,
    type: str = Query("classify", regex="^(classify|verb_match|design)$"),
    seed: int = Query(None),
):
    sessions.require(request)
    if seed is not None:
        random.seed(seed)
    problem = GENERATORS.get(type, _generate_classify)()
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


@router.post("/lti/bloom/api/check")
async def bloom_check(request: Request):
    """Check a student answer; regenerates problem server-side using seed."""
    sessions.require(request)
    body = await request.json()

    problem_type   = body.get("type", "classify")
    seed           = body.get("seed")
    step_id        = body.get("step_id", "")
    student_answer = body.get("answer")

    if student_answer is None:
        raise HTTPException(400, "Missing answer")

    if seed is not None:
        random.seed(seed)
    problem = GENERATORS.get(problem_type, _generate_classify)()

    step = next((s for s in problem["steps"] if s["id"] == step_id), None)
    if not step:
        raise HTTPException(400, f"Unknown step: {step_id}")

    # All bloom answers are exact integers (level 1-6 or choice 1-4)
    is_correct = abs(float(student_answer) - step["answer"]) < 0.4

    return {
        "correct":  is_correct,
        "expected": step["answer"],
        "formula":  step["formula"],
        "unit":     step["unit"],
    }
