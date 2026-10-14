#!/usr/bin/env python3
"""
Accuracy benchmark for standard English and standard Spanish queries.

Agents: llm_A_std, llm_B_std, llm_C_std  (October 10 standard-only agents)
Data:   errorsSP_T1T2T3.tsv  (169 queries, columns standard_query_ENG / standard_query_ESP)

Calls Mistral directly (bypasses pypdf / base class) by extracting each
agent's CLASSIFY_PROMPT from its agent.py source file.

Outputs:
  - Console report (overall + per-category accuracy)
  - results/accuracy_std_<timestamp>.json
  - results/accuracy_std_<timestamp>.md

Usage:
    python3 accuracy_std_benchmark.py
    python3 accuracy_std_benchmark.py --agents llm_A_std,llm_B_std
    python3 accuracy_std_benchmark.py --no-spanish
"""

import os
import sys
import json
import re
import time
import csv
import argparse

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

try:
    from mistralai.client import Mistral
except ImportError:
    from mistralai import Mistral

STUDY_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

CATEGORIES = [
    "meta", "organization", "out_of_scope", "general",
    "papers", "researcher", "project", "topic", "glossary",
]


# ── Extract CLASSIFY_PROMPT from agent.py source ──────────────────────────

def load_classify_prompt(variant: str) -> str:
    """Extract CLASSIFY_PROMPT string from agent.py without importing it."""
    agent_py = os.path.join(STUDY_DIR, "agents", variant, "agent.py")
    with open(agent_py, encoding="utf-8") as f:
        src = f.read()
    # CLASSIFY_PROMPT = """..."""  (triple-quoted)
    m = re.search(r'CLASSIFY_PROMPT\s*=\s*"""(.*?)"""', src, re.DOTALL)
    if m:
        return m.group(1)
    # fallback: single-quoted
    m = re.search(r"CLASSIFY_PROMPT\s*=\s*'''(.*?)'''", src, re.DOTALL)
    if m:
        return m.group(1)
    raise ValueError(f"CLASSIFY_PROMPT not found in {agent_py}")


# ── Mistral call ───────────────────────────────────────────────────────────

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
            match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            text = match.group(1).strip() if match else text
        json_match = re.search(r'\{[^{}]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(text)
    except Exception as e:
        print(f"  [warn] classify error: {e}")
        return {"category": "out_of_scope"}


# ── Data ──────────────────────────────────────────────────────────────────

def load_queries():
    rows = []
    with open(TSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append({
                "category":  row["category"].strip(),
                "eng_query": row["standard_query_ENG"].strip(),
                "esp_query": row["standard_query_ESP"].strip(),
            })
    return rows


# ── Evaluate ──────────────────────────────────────────────────────────────

def evaluate(prompt_template, queries, query_key, label=""):
    from collections import defaultdict
    total = correct = 0
    per_cat = defaultdict(lambda: {"total": 0, "correct": 0})
    detail = []

    n = len(queries)
    for i, row in enumerate(queries):
        query    = row[query_key]
        expected = row["category"]

        result  = llm_classify(prompt_template, query)
        got     = result.get("category", "out_of_scope")
        ok      = got == expected

        total += 1
        if ok:
            correct += 1
        per_cat[expected]["total"]   += 1
        if ok:
            per_cat[expected]["correct"] += 1

        detail.append({
            "n": i + 1, "category": expected,
            "query": query, "predicted": got, "correct": ok,
        })

        if (i + 1) % 20 == 0 or (i + 1) == n:
            print(f"    {i+1}/{n}  acc so far: {correct/(i+1):.1%}", flush=True)

    acc = round(correct / total, 4) if total else 0
    per_cat_out = {
        cat: {
            "total":   v["total"],
            "correct": v["correct"],
            "acc":     round(v["correct"] / v["total"], 4) if v["total"] else 0,
        }
        for cat, v in per_cat.items()
    }
    return acc, per_cat_out, detail


# ── Reporting ─────────────────────────────────────────────────────────────

def print_table(results, agent_ids, sets):
    W = 13
    header = f"  {'Category':<22}"
    for vid in agent_ids:
        for s in sets:
            col = f"{LABELS[vid]}/{s}"
            header += f"  {col:>{W}}"
    print(header)
    print(f"  {'-'*(22 + (W+2)*len(agent_ids)*len(sets))}")

    row = f"  {'OVERALL':<22}"
    for vid in agent_ids:
        for s in sets:
            acc = results[vid][s]["overall_acc"]
            row += f"  {acc:>{W}.1%}"
    print(row)
    print()

    for cat in CATEGORIES:
        row = f"  {cat:<22}"
        for vid in agent_ids:
            for s in sets:
                pc = results[vid][s]["per_cat"].get(cat)
                row += f"  {pc['acc']:>{W}.1%}" if pc else f"  {'—':>{W}}"
        print(row)


def build_markdown(results, agent_ids, sets, elapsed, n_queries):
    cols = [f"{LABELS[v]}/{s}" for v in agent_ids for s in sets]
    lines = [
        "# Accuracy Benchmark — Standard Queries",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Model:** {MISTRAL_MODEL}  ",
        f"**Agents:** {', '.join(LABELS[v] for v in agent_ids)}  ",
        f"**Queries per set:** {n_queries}  ",
        f"**Elapsed:** {elapsed:.0f}s",
        "",
        "| Category | " + " | ".join(cols) + " |",
        "|" + "---|" * (1 + len(cols)),
    ]

    row_vals = [f"{results[v][s]['overall_acc']:.1%}" for v in agent_ids for s in sets]
    lines.append("| **OVERALL** | " + " | ".join(row_vals) + " |")

    for cat in CATEGORIES:
        row_vals = []
        for vid in agent_ids:
            for s in sets:
                pc = results[vid][s]["per_cat"].get(cat)
                row_vals.append(f"{pc['acc']:.1%}" if pc else "—")
        lines.append(f"| {cat} | " + " | ".join(row_vals) + " |")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────

def run_benchmark(agent_ids, run_english=True, run_spanish=True):
    queries = load_queries()
    n = len(queries)
    print(f"Loaded {n} queries from errorsSP_T1T2T3.tsv")
    print(f"Model: {MISTRAL_MODEL}")

    sets = []
    if run_english: sets.append("ENG")
    if run_spanish: sets.append("ESP")

    # Load prompts
    prompts = {}
    for vid in agent_ids:
        print(f"Loading prompt for {LABELS.get(vid, vid)}...", end=" ", flush=True)
        prompts[vid] = load_classify_prompt(vid)
        print("OK")

    results = {}
    t_start = time.time()

    for vid in agent_ids:
        label = LABELS.get(vid, vid)
        print(f"\n{'='*60}\n  {label}\n{'='*60}")
        results[vid] = {}

        if run_english:
            print(f"  English ({n} queries)...")
            acc, per_cat, detail = evaluate(prompts[vid], queries, "eng_query", label)
            results[vid]["ENG"] = {"overall_acc": acc, "per_cat": per_cat, "detail": detail}
            print(f"  → English accuracy: {acc:.1%}")

        if run_spanish:
            print(f"  Spanish ({n} queries)...")
            acc, per_cat, detail = evaluate(prompts[vid], queries, "esp_query", label)
            results[vid]["ESP"] = {"overall_acc": acc, "per_cat": per_cat, "detail": detail}
            print(f"  → Spanish accuracy: {acc:.1%}")

    elapsed = time.time() - t_start

    print(f"\n{'='*80}")
    print(f"  ACCURACY BENCHMARK — Standard Queries")
    print(f"  {n} queries | {len(agent_ids)} agents | {elapsed:.0f}s")
    print(f"{'='*80}")
    print_table(results, agent_ids, sets)

    # Save
    results_dir = (
        "/Users/ignaciomoreno-torres/Library/CloudStorage/"
        "OneDrive-UniversidaddeMálaga/DatosTrabajo/Invest/LineasTrabajo/"
        "AIAgents/AIAgents_Reliability_Samuel/Paper/Version3/Resultados"
    )
    os.makedirs(results_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    out_json = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(elapsed, 1),
        "model":     MISTRAL_MODEL,
        "n_queries": n,
        "agents":    agent_ids,
        "sets":      sets,
        "results": {
            vid: {s: {"overall_acc": results[vid][s]["overall_acc"],
                      "per_cat":     results[vid][s]["per_cat"]}
                  for s in sets}
            for vid in agent_ids
        },
        "detail": {
            vid: {s: results[vid][s]["detail"] for s in sets}
            for vid in agent_ids
        },
    }
    json_path = os.path.join(results_dir, f"accuracy_std_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2, ensure_ascii=False)
    print(f"\nJSON     → {json_path}")

    md = build_markdown(results, agent_ids, sets, elapsed, n)
    md_path = os.path.join(results_dir, f"accuracy_std_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Markdown → {md_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Accuracy benchmark for standard queries")
    parser.add_argument("--agents",     type=str, default=",".join(AGENT_IDS))
    parser.add_argument("--no-english", action="store_true")
    parser.add_argument("--no-spanish", action="store_true")
    args = parser.parse_args()

    agent_ids = [a.strip() for a in args.agents.split(",")]
    run_benchmark(
        agent_ids,
        run_english=not args.no_english,
        run_spanish=not args.no_spanish,
    )
