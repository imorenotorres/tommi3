#!/usr/bin/env python3
"""
Robustness benchmark — accuracy per error condition + degradation vs. standard ENG.

Conditions evaluated (169 queries each):
  standard_ENG                    ← baseline
  error_query_typo_15/25/35
  error_query_phon_15/25/35
  error_query_morph_15/25/35
  standard_ESP                    ← reference (non-English baseline)

For each agent × condition:
  - Overall accuracy
  - Per-category accuracy
  - Degradation = acc(standard_ENG) − acc(condition)

Agents: llm_A_std, llm_B_std, llm_C_std  (October 10, standard-only)

Usage:
    python3 robustness_benchmark.py
    python3 robustness_benchmark.py --agents llm_B_std
    python3 robustness_benchmark.py --no-esp
"""

import os, sys, json, re, time, csv, argparse
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

try:
    from mistralai.client import Mistral
except ImportError:
    from mistralai import Mistral

STUDY_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISTRAL_KEY   = os.environ["MISTRAL_API_KEY"]
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

TSV_PATH = (
    "/Users/ignaciomoreno-torres/Library/CloudStorage/"
    "OneDrive-UniversidaddeMálaga/DatosTrabajo/Invest/LineasTrabajo/"
    "AIAgents/AIAgents_Reliability_Samuel/Paper/Version3/Materials/"
    "errorsSP_T1T2T3.tsv"
)

AGENT_IDS = ["llm_A_std", "llm_B_std", "llm_C_std"]
LABELS    = {"llm_A_std": "LLM A std", "llm_B_std": "LLM B std", "llm_C_std": "LLM C std"}

# Ordered conditions: baseline first, then error tiers, then Spanish
CONDITIONS_ENG = [
    ("standard_ENG",   "standard_query_ENG"),
    ("typo_15",        "error_query_typo_15"),
    ("typo_25",        "error_query_typo_25"),
    ("typo_35",        "error_query_typo_35"),
    ("phon_15",        "error_query_phon_15"),
    ("phon_25",        "error_query_phon_25"),
    ("phon_35",        "error_query_phon_35"),
    ("morph_15",       "error_query_morph_15"),
    ("morph_25",       "error_query_morph_25"),
    ("morph_35",       "error_query_morph_35"),
]
CONDITIONS_ESP = [
    ("standard_ESP",   "standard_query_ESP"),
]

CATEGORIES = [
    "meta", "organization", "out_of_scope", "general",
    "papers", "researcher", "project", "topic", "glossary",
]

ERROR_TYPES = {
    "typo":  ["typo_15",  "typo_25",  "typo_35"],
    "phon":  ["phon_15",  "phon_25",  "phon_35"],
    "morph": ["morph_15", "morph_25", "morph_35"],
}


# ── Helpers ───────────────────────────────────────────────────────────────

def load_classify_prompt(variant: str) -> str:
    agent_py = os.path.join(STUDY_DIR, "agents", variant, "agent.py")
    with open(agent_py, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'CLASSIFY_PROMPT\s*=\s*"""(.*?)"""', src, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r"CLASSIFY_PROMPT\s*=\s*'''(.*?)'''", src, re.DOTALL)
    if m:
        return m.group(1)
    raise ValueError(f"CLASSIFY_PROMPT not found in {agent_py}")


_client = None
def get_client():
    global _client
    if _client is None:
        _client = Mistral(api_key=MISTRAL_KEY)
    return _client


def llm_classify(prompt_template: str, query: str) -> dict:
    prompt = prompt_template.replace("{query}", query)
    try:
        resp = get_client().chat.complete(
            model=MISTRAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        if "```" in text:
            m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            text = m.group(1).strip() if m else text
        m = re.search(r'\{[^{}]*\}', text)
        if m:
            return json.loads(m.group())
        return json.loads(text)
    except Exception as e:
        print(f"  [warn] {e}")
        return {"category": "out_of_scope"}


def load_queries():
    rows = []
    with open(TSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append({k: v.strip() for k, v in row.items()})
    return rows


# ── Evaluation ────────────────────────────────────────────────────────────

def evaluate_condition(prompt_template, queries, col, label=""):
    """Evaluate one condition. Returns (overall_acc, per_cat_dict, detail_list)."""
    total = correct = 0
    per_cat = defaultdict(lambda: {"total": 0, "correct": 0})
    detail  = []
    n = len(queries)

    for i, row in enumerate(queries):
        query    = row[col]
        expected = row["category"]
        result   = llm_classify(prompt_template, query)
        got      = result.get("category", "out_of_scope")
        ok       = got == expected

        total += 1
        if ok: correct += 1
        per_cat[expected]["total"] += 1
        if ok: per_cat[expected]["correct"] += 1
        detail.append({"n": i+1, "category": expected, "query": query,
                        "predicted": got, "correct": ok})

        if (i+1) % 20 == 0 or (i+1) == n:
            print(f"      {i+1}/{n}  acc: {correct/(i+1):.1%}", flush=True)

    acc = round(correct / total, 4) if total else 0
    per_cat_out = {
        cat: {"total": v["total"], "correct": v["correct"],
              "acc": round(v["correct"]/v["total"], 4) if v["total"] else 0}
        for cat, v in per_cat.items()
    }
    return acc, per_cat_out, detail


# ── Reporting ─────────────────────────────────────────────────────────────

def fmt_deg(d):
    """Format degradation: negative = drop, positive = gain."""
    if d is None: return "  —   "
    sign = "-" if d > 0 else ("+" if d < 0 else " ")
    return f"{sign}{abs(d):.1%}"


def print_summary(results, agent_ids, conditions):
    """Print a compact table: rows = conditions, cols = agents."""
    W = 16
    print(f"\n{'='*80}")
    print(f"  ROBUSTNESS BENCHMARK — Accuracy & Degradation vs. standard_ENG")
    print(f"{'='*80}")

    # Header
    hdr = f"  {'Condition':<18}"
    for vid in agent_ids:
        hdr += f"  {LABELS[vid]+' acc':>{W}}  {'Δ':>6}"
    print(hdr)
    print(f"  {'-'*(18 + (W+10)*len(agent_ids))}")

    for cname, _ in conditions:
        row = f"  {cname:<18}"
        for vid in agent_ids:
            acc = results[vid][cname]["overall_acc"]
            std = results[vid]["standard_ENG"]["overall_acc"]
            deg = round(std - acc, 4) if cname != "standard_ENG" else None
            row += f"  {acc:>{W}.1%}  {fmt_deg(deg):>6}"
        print(row)

    print()


def build_markdown(results, agent_ids, conditions, elapsed, n):
    cols_acc = [f"{LABELS[v]} acc" for v in agent_ids]
    cols_deg = [f"{LABELS[v]} Δ"   for v in agent_ids]
    # interleave: A_acc, A_Δ, B_acc, B_Δ, C_acc, C_Δ
    header_cols = []
    for v in agent_ids:
        header_cols += [f"{LABELS[v]} acc", f"Δ"]

    lines = [
        "# Robustness Benchmark — Accuracy & Degradation vs. standard ENG",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Model:** {MISTRAL_MODEL}  ",
        f"**Queries per condition:** {n}  ",
        f"**Elapsed:** {elapsed:.0f}s",
        "",
        "Δ = standard_ENG accuracy − condition accuracy (positive = drop).",
        "",
        "| Condition | " + " | ".join(header_cols) + " |",
        "|" + "---|" * (1 + len(header_cols)),
    ]

    for cname, _ in conditions:
        cells = []
        for vid in agent_ids:
            acc = results[vid][cname]["overall_acc"]
            std = results[vid]["standard_ENG"]["overall_acc"]
            deg = round(std - acc, 4) if cname != "standard_ENG" else None
            cells.append(f"{acc:.1%}")
            cells.append("—" if deg is None else f"{deg:+.1%}")
        lines.append(f"| **{cname}** | " + " | ".join(cells) + " |")

    # Per-error-type summary
    lines += ["", "## Degradation by error type (average across tiers)", ""]
    type_cols = ["| Error type |"] + [f" {LABELS[v]} avg Δ |" for v in agent_ids]
    lines.append("".join(type_cols))
    lines.append("|" + "---|" * (1 + len(agent_ids)))

    for etype, cnames in ERROR_TYPES.items():
        cells = []
        for vid in agent_ids:
            std = results[vid]["standard_ENG"]["overall_acc"]
            degs = [round(std - results[vid][c]["overall_acc"], 4) for c in cnames]
            avg  = round(sum(degs)/len(degs), 4)
            cells.append(f"{avg:+.1%}")
        lines.append(f"| {etype} | " + " | ".join(cells) + " |")

    # Per-category breakdown for each condition
    lines += ["", "## Per-category accuracy by condition", ""]
    for cname, _ in conditions:
        lines.append(f"### {cname}")
        cat_cols = ["| Category |"] + [f" {LABELS[v]} |" for v in agent_ids]
        lines.append("".join(cat_cols))
        lines.append("|" + "---|" * (1 + len(agent_ids)))
        for cat in CATEGORIES:
            cells = []
            for vid in agent_ids:
                pc = results[vid][cname]["per_cat"].get(cat)
                cells.append(f"{pc['acc']:.1%}" if pc else "—")
            lines.append(f"| {cat} | " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────

def run_benchmark(agent_ids, include_esp=True):
    queries = load_queries()
    n = len(queries)
    print(f"Loaded {n} queries | Model: {MISTRAL_MODEL}")

    conditions = CONDITIONS_ENG + (CONDITIONS_ESP if include_esp else [])

    # Load prompts
    prompts = {}
    for vid in agent_ids:
        print(f"Loading prompt for {LABELS.get(vid, vid)}...", end=" ", flush=True)
        prompts[vid] = load_classify_prompt(vid)
        print("OK")

    results = {vid: {} for vid in agent_ids}
    t_start = time.time()

    for vid in agent_ids:
        label = LABELS.get(vid, vid)
        print(f"\n{'='*60}\n  {label}\n{'='*60}")

        for cname, col in conditions:
            print(f"  [{cname}]  column: {col}")
            acc, per_cat, detail = evaluate_condition(prompts[vid], queries, col)
            results[vid][cname] = {
                "overall_acc": acc,
                "per_cat":     per_cat,
                "detail":      detail,
            }
            std = results[vid].get("standard_ENG", {}).get("overall_acc")
            if std is not None and cname != "standard_ENG":
                deg = round(std - acc, 4)
                print(f"  → acc: {acc:.1%}  |  Δ vs standard_ENG: {deg:+.1%}")
            else:
                print(f"  → acc: {acc:.1%}")

    elapsed = time.time() - t_start

    # Print summary table
    print_summary(results, agent_ids, conditions)

    # Degradation by error type
    print("  Average degradation by error type:")
    for etype, cnames in ERROR_TYPES.items():
        row = f"    {etype:<8}"
        for vid in agent_ids:
            std  = results[vid]["standard_ENG"]["overall_acc"]
            degs = [round(std - results[vid][c]["overall_acc"], 4) for c in cnames]
            avg  = round(sum(degs)/len(degs), 4)
            row += f"  {LABELS[vid]}: {avg:+.1%}"
        print(row)

    # Save
    results_dir = (
        "/Users/ignaciomoreno-torres/Library/CloudStorage/"
        "OneDrive-UniversidaddeMálaga/DatosTrabajo/Invest/LineasTrabajo/"
        "AIAgents/AIAgents_Reliability_Samuel/Paper/Version3/Resultados"
    )
    os.makedirs(results_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    out_json = {
        "timestamp":   time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s":   round(elapsed, 1),
        "model":       MISTRAL_MODEL,
        "n_queries":   n,
        "agents":      agent_ids,
        "conditions":  [c for c, _ in conditions],
        "results": {
            vid: {
                cname: {
                    "overall_acc": results[vid][cname]["overall_acc"],
                    "degradation_vs_std_ENG": (
                        round(results[vid]["standard_ENG"]["overall_acc"]
                              - results[vid][cname]["overall_acc"], 4)
                        if cname != "standard_ENG" else 0.0
                    ),
                    "per_cat": results[vid][cname]["per_cat"],
                }
                for cname, _ in conditions
            }
            for vid in agent_ids
        },
        "detail": {
            vid: {cname: results[vid][cname]["detail"] for cname, _ in conditions}
            for vid in agent_ids
        },
    }
    json_path = os.path.join(results_dir, f"robustness_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2, ensure_ascii=False)
    print(f"\nJSON     → {json_path}")

    md = build_markdown(results, agent_ids, conditions, elapsed, n)
    md_path = os.path.join(results_dir, f"robustness_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Markdown → {md_path}")
    print(f"Elapsed  → {elapsed:.0f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robustness benchmark — degradation vs. standard ENG")
    parser.add_argument("--agents",  type=str, default=",".join(AGENT_IDS))
    parser.add_argument("--no-esp",  action="store_true", help="Skip standard_ESP condition")
    args = parser.parse_args()

    agent_ids = [a.strip() for a in args.agents.split(",")]
    run_benchmark(agent_ids, include_esp=not args.no_esp)
