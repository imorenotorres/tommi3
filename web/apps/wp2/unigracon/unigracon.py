"""
UNIGRACON — UNINOVIS Grade Converter

Converts grades between UNINOVIS partner universities using either:
  - Arithmetic formulas (Excel-style, using X as the input grade)
  - Conversion tables (range-to-value mapping)

Designed to be mounted on the TOMMI FastAPI server.
"""

import ast
import json
import math
import operator
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


# Safe math evaluator — replaces eval() for formula computation
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


_MAX_EXPONENT = 10
_MAX_POW_BASE = 1000
_MAX_FORMULA_LENGTH = 500


def _safe_eval(expr: str):
    """Evaluate a math expression safely using AST parsing (no exec/eval)."""
    if len(expr) > _MAX_FORMULA_LENGTH:
        raise ValueError(f"Formula is too long (max {_MAX_FORMULA_LENGTH} characters)")
    try:
        tree = ast.parse(expr.strip(), mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Invalid expression: {e}")
    return _eval_node(tree.body)


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow):
            # Grade formulas never need large powers; unbounded ones (e.g.
            # 9**9**9) would tie up the server computing a huge integer.
            if abs(right) > _MAX_EXPONENT or abs(left) > _MAX_POW_BASE:
                raise ValueError(f"Powers are limited to a base of at most {_MAX_POW_BASE} and an exponent of at most {_MAX_EXPONENT}")
            return float(left) ** right
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    elif isinstance(node, ast.Compare):
        left = _eval_node(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _SAFE_OPS.get(type(op_node))
            if not op:
                raise ValueError(f"Unsupported comparison: {type(op_node).__name__}")
            right = _eval_node(comparator)
            if not op(left, right):
                return False
            left = right
        return True
    else:
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

# Tool Visibility is enforced on the server for every /api/ route (see auth.tool_access_guard).
from auth import tool_access_guard as _tool_access_guard

router = APIRouter(prefix="/unigracon", tags=["unigracon"], dependencies=[Depends(_tool_access_guard("unigracon", ()))])


# ── Auth helpers for edit protection ─────────────────────────────────
# UNIGRACON is curated only by content managers, so it uses the narrower
# content-manager-only editor check rather than the general EDITOR_ROLES
# shared by most other apps.

from auth import require_login as _require_auth, require_content_manager_editor as _require_editor, can_edit_as_content_manager as _can_edit_check, user_roles as _user_roles

# The UNINOVIS staff directory is the single source of truth for which
# university each person belongs to — every user has a directory entry, so
# rather than guess from the email domain we look up their entry there.
from apps.wp1.directory.directory import load_data as _load_directory_data


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


def _require_own_university(acro: str, session: dict):
    """Content managers may only edit their own home university's data;
    superuser is exempt from this restriction."""
    if "superuser" in _user_roles(session):
        return
    home = _home_university(session["username"])
    if not home or acro.upper() != home:
        raise HTTPException(status_code=403, detail="You can only edit your own university's data")


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
        result = float(_safe_eval(expr))
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

    cond_result = _safe_eval(cond_expr)

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


# ── Grading system helpers ────────────────────────────────────────────

def _get_system(uni_info: dict, system_id: str) -> dict:
    """Get a grading system by id from a university's grading_systems list."""
    for gs in uni_info.get("grading_systems", []):
        if gs["id"] == system_id:
            return gs
    # Fallback: use top-level fields (backward compat)
    if system_id == "general":
        return {
            "id": "general",
            "name": uni_info.get("grading_system", "General"),
            "description": "",
            "min_grade": uni_info["min_grade"],
            "max_grade": uni_info["max_grade"],
            "pass_grade": uni_info["pass_grade"],
            "inverted": uni_info.get("inverted", False),
            "grade_labels": uni_info.get("grade_labels", []),
        }
    return None


def _parse_key(compound: str):
    """Parse 'UNI:system' into (uni, system). Default system is 'general'."""
    if ':' in compound:
        uni, sys = compound.split(':', 1)
        return uni, sys
    return compound, 'general'


# ── Conversion logic ──────────────────────────────────────────────────

def convert_grade(source: str, target: str, grade: float, data: dict,
                  source_system: str = "general", target_system: str = "general") -> dict:
    """Convert a grade from source university/system to target university/system."""
    unis = data["universities"]
    conversions = data["conversions"]

    if source not in unis:
        raise ValueError(f"Unknown university: {source}")
    if target not in unis:
        raise ValueError(f"Unknown university: {target}")

    src_info = unis[source]
    tgt_info = unis[target]

    src_sys = _get_system(src_info, source_system)
    tgt_sys = _get_system(tgt_info, target_system)

    if not src_sys:
        raise ValueError(f"Unknown grading system '{source_system}' for {source}")
    if not tgt_sys:
        raise ValueError(f"Unknown grading system '{target_system}' for {target}")

    # Validate input grade
    if grade < src_sys["min_grade"] or grade > src_sys["max_grade"]:
        raise ValueError(
            f"Grade {grade} is out of range for {source}:{source_system} "
            f"({src_sys['min_grade']}-{src_sys['max_grade']})"
        )

    key = f"{source}:{source_system}->{target}:{target_system}"
    if key not in conversions:
        raise ValueError(f"No conversion defined from {source}:{source_system} to {target}:{target_system}")

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
    result = max(tgt_sys["min_grade"], min(tgt_sys["max_grade"], result))
    result = round(result, 2)

    # Find label for source grade
    src_label = ""
    for lbl in src_sys.get("grade_labels", []):
        if lbl["min"] <= grade <= lbl["max"]:
            src_label = lbl["label"]
            break

    # Find label for target grade
    tgt_label = ""
    for lbl in tgt_sys.get("grade_labels", []):
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
        "source_system": src_sys["name"],
        "source_system_id": source_system,
        "source_grade": grade,
        "source_label": src_label,
        "target_university": target,
        "target_name": tgt_info["name"],
        "target_system": tgt_sys["name"],
        "target_system_id": target_system,
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
    source_system: str = "general"
    target_system: str = "general"


# ── Routes ────────────────────────────────────────────────────────────

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers={"Cache-Control": "no-store"})


@router.get("/api/universities")
def universities(session: dict = Depends(_require_auth)):
    data = load_data()
    return data["universities"]


@router.get("/api/conversions")
def conversions_list(session: dict = Depends(_require_auth)):
    """List all available conversion pairs."""
    data = load_data()
    pairs = []
    for key, conv in data["conversions"].items():
        src_full, tgt_full = key.split("->")
        src_uni, src_sys = _parse_key(src_full)
        tgt_uni, tgt_sys = _parse_key(tgt_full)
        entry = {
            "source": src_uni,
            "source_system": src_sys,
            "target": tgt_uni,
            "target_system": tgt_sys,
            "method": conv["method"],
            "notes": conv.get("notes", ""),
            "confirmed": conv.get("confirmed", False),
        }
        if conv["method"] == "formula":
            entry["formula"] = conv["formula"]
        elif conv["method"] == "table":
            entry["table"] = conv["table"]
        pairs.append(entry)
    return {"conversions": pairs}


@router.post("/api/convert")
def convert(body: ConvertRequest, session: dict = Depends(_require_auth)):
    data = load_data()
    try:
        result = convert_grade(body.source, body.target, body.grade, data,
                               body.source_system, body.target_system)
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
    confirmed: bool = False


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
    can_edit = _can_edit_check(session)
    is_superuser = "superuser" in _user_roles(session)
    return {
        "username": session["username"],
        "role": session["role"],
        "can_edit": can_edit,
        "is_superuser": is_superuser,
        # Content managers may only edit their own home university's data;
        # superuser is exempt and may pick any university in the editor.
        "home_university": None if is_superuser else _home_university(session["username"]),
    }


# ── Batch conversion update (per target university) ─────────────────

@router.get("/api/conversions-to/{target}")
def get_conversions_to(target: str, session: dict = Depends(_require_auth)):
    data = load_data()
    if target not in data["universities"]:
        raise HTTPException(404, f"University {target} not found")
    result = {}
    for key, conv in data["conversions"].items():
        src_full, tgt_full = key.split("->")
        tgt_uni, tgt_sys = _parse_key(tgt_full)
        if tgt_uni == target:
            result[src_full] = conv
    return {"target": target, "conversions": result}


@router.put("/api/conversions-to/{target}")
def update_conversions_to(
    target: str,
    body: BatchConversionsBody,
    session: dict = Depends(_require_editor),
    target_system: str = "general",
):
    data = load_data()
    tgt_uni, _ = _parse_key(target)
    if tgt_uni not in data["universities"]:
        raise HTTPException(404, f"University {tgt_uni} not found")
    _require_own_university(tgt_uni, session)

    errors = []
    for source_key, conv in body.conversions.items():
        src_uni, src_sys = _parse_key(source_key)
        if src_uni not in data["universities"]:
            errors.append(f"Unknown university: {src_uni}")
            continue
        if src_uni == tgt_uni and src_sys == target_system:
            continue

        key = f"{source_key}->{tgt_uni}:{target_system}"

        # Empty conversion — remove if it exists
        if conv.method == "formula" and not conv.formula.strip():
            data["conversions"].pop(key, None)
            continue
        if conv.method == "table" and not conv.table:
            data["conversions"].pop(key, None)
            continue

        if conv.method == "formula":
            src_sys = _get_system(data["universities"][src_uni], src_sys)
            if src_sys:
                mid = (src_sys["min_grade"] + src_sys["max_grade"]) / 2
            else:
                mid = 5
            try:
                _eval_formula(conv.formula, mid)
            except Exception as e:
                errors.append(f"{source_key}: Invalid formula — {e}")
                continue
            data["conversions"][key] = {
                "method": "formula",
                "formula": conv.formula,
                "notes": conv.notes,
                "confirmed": conv.confirmed,
            }
        elif conv.method == "table":
            data["conversions"][key] = {
                "method": "table",
                "table": [row.model_dump() for row in conv.table],
                "notes": conv.notes,
                "confirmed": conv.confirmed,
            }
        else:
            errors.append(f"{source_key}: Invalid method — {conv.method}")

    if errors:
        raise HTTPException(400, detail={"errors": errors})

    save_data(data)
    return {"ok": True}


# ── Grading systems management ───────────────────────────────────────

class GradingSystemBody(BaseModel):
    id: str
    name: str
    description: str = ""
    min_grade: float
    max_grade: float
    pass_grade: float
    inverted: bool = False
    grade_labels: list[dict] = []


@router.post("/api/universities/{acro}/grading-systems")
def add_grading_system(acro: str, body: GradingSystemBody, session: dict = Depends(_require_editor)):
    data = load_data()
    if acro not in data["universities"]:
        raise HTTPException(404, f"University {acro} not found")
    _require_own_university(acro, session)
    uni = data["universities"][acro]
    systems = uni.setdefault("grading_systems", [])
    if any(gs["id"] == body.id for gs in systems):
        raise HTTPException(400, f"Grading system '{body.id}' already exists for {acro}")
    systems.append(body.model_dump())
    save_data(data)
    return {"ok": True}


@router.put("/api/universities/{acro}/grading-systems/{sys_id}")
def update_grading_system(acro: str, sys_id: str, body: GradingSystemBody, session: dict = Depends(_require_editor)):
    data = load_data()
    if acro not in data["universities"]:
        raise HTTPException(404, f"University {acro} not found")
    _require_own_university(acro, session)
    systems = data["universities"][acro].get("grading_systems", [])
    for i, gs in enumerate(systems):
        if gs["id"] == sys_id:
            systems[i] = body.model_dump()
            save_data(data)
            return {"ok": True}
    raise HTTPException(404, f"Grading system '{sys_id}' not found")


@router.delete("/api/universities/{acro}/grading-systems/{sys_id}")
def delete_grading_system(acro: str, sys_id: str, session: dict = Depends(_require_editor)):
    data = load_data()
    if acro not in data["universities"]:
        raise HTTPException(404, f"University {acro} not found")
    _require_own_university(acro, session)
    if sys_id == "general":
        raise HTTPException(400, "Cannot delete the general grading system")
    systems = data["universities"][acro].get("grading_systems", [])
    data["universities"][acro]["grading_systems"] = [gs for gs in systems if gs["id"] != sys_id]
    # Remove conversions using this system
    prefix_src = f"{acro}:{sys_id}->"
    prefix_tgt = f"->{acro}:{sys_id}"
    keys_to_remove = [k for k in data["conversions"] if prefix_src in k or k.endswith(f"->{acro}:{sys_id}")]
    for k in keys_to_remove:
        del data["conversions"][k]
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
