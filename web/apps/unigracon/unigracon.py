"""
UNIGRACON — UNINOVIS Grade Converter

Converts grades between UNINOVIS partner universities using either:
  - Arithmetic formulas (Excel-style, using X as the input grade)
  - Conversion tables (range-to-value mapping)

Designed to be mounted on the TOMMI FastAPI server.
"""

import json
import math
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

router = APIRouter(prefix="/unigracon", tags=["unigracon"])


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

def load_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Excel-style formula evaluator ─────────────────────────────────────

def _eval_formula(formula: str, x: float) -> float:
    """Evaluate an Excel-style formula with X as the variable.

    Supported: arithmetic (+, -, *, /), IF(cond, true_val, false_val),
    parentheses, comparisons (<, >, <=, >=).
    """
    expr = formula.strip()

    # Recursively resolve IF() from the inside out (handles nesting)
    def resolve_ifs(s: str) -> str:
        while True:
            # Find innermost IF( — one whose parenthesised body has no IF(
            m = re.search(r'IF\(', s, re.IGNORECASE)
            if not m:
                break
            # Walk forward to find the matching closing paren
            start = m.start()
            open_pos = m.end()  # position right after "IF("
            depth = 1
            i = open_pos
            while i < len(s) and depth > 0:
                if s[i] == '(':
                    depth += 1
                elif s[i] == ')':
                    depth -= 1
                i += 1
            if depth != 0:
                raise ValueError(f"Unbalanced parentheses in IF: {s}")
            inner = s[open_pos:i - 1]  # content between IF( and )
            # If inner contains another IF, recurse on it first
            if re.search(r'IF\(', inner, re.IGNORECASE):
                inner = resolve_ifs(inner)
            # Evaluate this IF
            result_str = _eval_if_args(inner, x)
            s = s[:start] + result_str + s[i:]
        return s

    expr = resolve_ifs(expr)

    # Replace X with the value
    expr = re.sub(r'\bX\b', str(x), expr, flags=re.IGNORECASE)

    # Validate: only allow safe characters
    if not re.match(r'^[\d\s+\-*/().eE<>=!]+$', expr):
        raise ValueError(f"Unsafe formula expression: {expr}")

    try:
        result = float(eval(expr))  # safe: input is validated above
    except Exception as e:
        raise ValueError(f"Formula evaluation error: {e}")

    return result


def _eval_if_args(args_str: str, x: float) -> str:
    """Evaluate IF(condition, true_val, false_val) and return the result as string."""
    # Split on commas, respecting that values may have nested parens (already resolved)
    parts = _split_if_args(args_str)
    if len(parts) != 3:
        raise ValueError(f"IF() expects 3 arguments, got {len(parts)}: {args_str}")

    cond_str, true_str, false_str = [p.strip() for p in parts]

    # Evaluate condition with X substituted
    cond_expr = re.sub(r'\bX\b', str(x), cond_str, flags=re.IGNORECASE)
    if not re.match(r'^[\d\s+\-*/().eE<>=!]+$', cond_expr):
        raise ValueError(f"Unsafe condition: {cond_expr}")

    cond_result = eval(cond_expr)

    return true_str if cond_result else false_str


def _split_if_args(s: str) -> list:
    """Split IF arguments by commas, respecting parentheses depth."""
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return parts


# ── Table lookup ──────────────────────────────────────────────────────

def _table_lookup(table: list, x: float) -> float | None:
    """Find the matching row in a conversion table and return the 'to' value."""
    for row in table:
        if row["from_min"] <= x <= row["from_max"]:
            return row["to"]
    return None


# ── Conversion logic ──────────────────────────────────────────────────

def convert_grade(source: str, target: str, grade: float, data: dict) -> dict:
    """Convert a grade from source university to target university."""
    unis = data["universities"]
    conversions = data["conversions"]

    if source not in unis:
        raise ValueError(f"Unknown university: {source}")
    if target not in unis:
        raise ValueError(f"Unknown university: {target}")
    if source == target:
        raise ValueError("Source and target must be different universities")

    src_info = unis[source]
    tgt_info = unis[target]

    # Validate input grade
    if grade < src_info["min_grade"] or grade > src_info["max_grade"]:
        raise ValueError(
            f"Grade {grade} is out of range for {source} "
            f"({src_info['min_grade']}-{src_info['max_grade']})"
        )

    key = f"{source}->{target}"
    if key not in conversions:
        raise ValueError(f"No conversion defined from {source} to {target}")

    conv = conversions[key]
    method = conv["method"]

    if method == "formula":
        result = _eval_formula(conv["formula"], grade)
    elif method == "table":
        result = _table_lookup(conv["table"], grade)
        if result is None:
            raise ValueError(f"Grade {grade} not covered by conversion table for {key}")
    else:
        raise ValueError(f"Unknown conversion method: {method}")

    # Clamp to target range
    result = max(tgt_info["min_grade"], min(tgt_info["max_grade"], result))
    result = round(result, 2)

    # Find label for source grade
    src_label = ""
    for lbl in src_info.get("grade_labels", []):
        if lbl["min"] <= grade <= lbl["max"]:
            src_label = lbl["label"]
            break

    # Find label for target grade
    tgt_label = ""
    for lbl in tgt_info.get("grade_labels", []):
        if lbl["min"] <= result <= lbl["max"]:
            tgt_label = lbl["label"]
            break

    # Display value (special case: Italian 31 = "30 e lode")
    display_result = result
    if target == "UDCLV" and result >= 30.5:
        display_result = "30 e lode"

    return {
        "source_university": source,
        "source_name": src_info["name"],
        "source_system": src_info["grading_system"],
        "source_grade": grade,
        "source_label": src_label,
        "target_university": target,
        "target_name": tgt_info["name"],
        "target_system": tgt_info["grading_system"],
        "target_grade": result,
        "target_grade_display": str(display_result),
        "target_label": tgt_label,
        "method": method,
        "formula": conv.get("formula", ""),
        "notes": conv.get("notes", ""),
    }


# ── API Models ────────────────────────────────────────────────────────

class ConvertRequest(BaseModel):
    source: str
    target: str
    grade: float


# ── Routes ────────────────────────────────────────────────────────────

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/universities")
def universities():
    data = load_data()
    return data["universities"]


@router.get("/api/conversions")
def conversions_list():
    """List all available conversion pairs."""
    data = load_data()
    pairs = []
    for key, conv in data["conversions"].items():
        src, tgt = key.split("->")
        entry = {
            "source": src,
            "target": tgt,
            "method": conv["method"],
            "notes": conv.get("notes", ""),
        }
        if conv["method"] == "formula":
            entry["formula"] = conv["formula"]
        elif conv["method"] == "table":
            entry["table"] = conv["table"]
        pairs.append(entry)
    return {"conversions": pairs}


@router.post("/api/convert")
def convert(body: ConvertRequest):
    data = load_data()
    try:
        result = convert_grade(body.source, body.target, body.grade, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


# ── Models for data editing ──────────────────────────────────────────

class TableRow(BaseModel):
    from_min: float
    from_max: float
    to: float


class SingleConversion(BaseModel):
    method: str
    formula: str = ""
    table: list[TableRow] = []
    notes: str = ""


class BatchConversionsBody(BaseModel):
    conversions: dict[str, SingleConversion]


class TestRequest(BaseModel):
    method: str
    formula: str = ""
    table: list[dict] = []
    grade: float


# ── Auth check ───────────────────────────────────────────────────────

@router.get("/api/auth-check")
def auth_check(session: dict = Depends(_require_auth)):
    can_edit = ROLES.get(session["role"], 0) >= ROLES.get("tester", 99)
    return {"username": session["username"], "role": session["role"], "can_edit": can_edit}


# ── Batch conversion update (per target university) ─────────────────

@router.get("/api/conversions-to/{target}")
def get_conversions_to(target: str):
    data = load_data()
    if target not in data["universities"]:
        raise HTTPException(404, f"University {target} not found")
    result = {}
    for key, conv in data["conversions"].items():
        src, tgt = key.split("->")
        if tgt == target:
            result[src] = conv
    return {"target": target, "conversions": result}


@router.put("/api/conversions-to/{target}")
def update_conversions_to(
    target: str,
    body: BatchConversionsBody,
    session: dict = Depends(_require_editor),
):
    data = load_data()
    if target not in data["universities"]:
        raise HTTPException(404, f"University {target} not found")

    errors = []
    for source, conv in body.conversions.items():
        if source not in data["universities"]:
            errors.append(f"Unknown university: {source}")
            continue
        if source == target:
            continue

        key = f"{source}->{target}"

        # Empty conversion — remove if it exists
        if conv.method == "formula" and not conv.formula.strip():
            data["conversions"].pop(key, None)
            continue
        if conv.method == "table" and not conv.table:
            data["conversions"].pop(key, None)
            continue

        if conv.method == "formula":
            src_info = data["universities"][source]
            mid = (src_info["min_grade"] + src_info["max_grade"]) / 2
            try:
                _eval_formula(conv.formula, mid)
            except Exception as e:
                errors.append(f"{source}: Invalid formula — {e}")
                continue
            data["conversions"][key] = {
                "method": "formula",
                "formula": conv.formula,
                "notes": conv.notes,
            }
        elif conv.method == "table":
            data["conversions"][key] = {
                "method": "table",
                "table": [row.model_dump() for row in conv.table],
                "notes": conv.notes,
            }
        else:
            errors.append(f"{source}: Invalid method — {conv.method}")

    if errors:
        raise HTTPException(400, detail={"errors": errors})

    save_data(data)
    return {"ok": True}


# ── Test a formula / table without saving ────────────────────────────

@router.post("/api/test-formula")
def test_formula(body: TestRequest, session: dict = Depends(_require_editor)):
    try:
        if body.method == "formula":
            if not body.formula.strip():
                return {"error": "Formula is empty"}
            result = _eval_formula(body.formula, body.grade)
        elif body.method == "table":
            if not body.table:
                return {"error": "Table is empty"}
            result = _table_lookup(body.table, body.grade)
            if result is None:
                return {"error": f"Grade {body.grade} not covered by table"}
        else:
            return {"error": f"Unknown method: {body.method}"}
        return {"result": round(result, 2)}
    except Exception as e:
        return {"error": str(e)}
