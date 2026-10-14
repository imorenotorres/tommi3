#!/usr/bin/env python3
"""
Automated Agent Construction + Evaluation — 9-class taxonomy (10Oct)
Works with Python 3.13 using only stdlib (no mistralai package needed).

Conditions:
  std-only : llm_A_std / llm_B_std / llm_C_std — built with 50 standard queries
  full     : llm_A     / llm_B     / llm_C     — built with all 150 queries

Usage:
    python3.13 automate.py                     # run everything
    python3.13 automate.py --phase construct   # only construction
    python3.13 automate.py --phase evaluate    # only evaluation
    python3.13 automate.py --variant llm_A_std # single variant
"""

import os, sys, re, json, time, argparse, urllib.request
from collections import Counter

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
STUDY_DIR   = os.path.dirname(SCRIPT_DIR)
AGENTS_DIR  = os.path.join(STUDY_DIR, "agents")
BENCH_DIR   = os.path.join(STUDY_DIR, "benchmark")
TRAJ_DIR    = os.path.join(SCRIPT_DIR, "trajectories")
MATERIALS_DIR = os.path.join(
    os.path.expanduser("~"),
    "Library/CloudStorage/OneDrive-UniversidaddeMálaga/DatosTrabajo/Invest/"
    "LineasTrabajo/AIAgents/AIAgents_Reliability_Samuel/Paper/Version3/Materials"
)

# ── Mistral credentials ───────────────────────────────────────────────────────
API_KEY = "5csuTcL2eHvm98DvHzrjALMMgqJTiat3"
MODEL   = "mistral-small-latest"

# ── construction settings ─────────────────────────────────────────────────────
MAX_ITERATIONS    = 8
TARGET_ACCURACY   = 0.96   # stop when >= this
PATIENCE          = 3      # stop if no improvement for this many iterations
DEGRADATION_LIMIT = 0.06   # stop if drops > 6% below best

CATEGORIES = ["meta", "organization", "out_of_scope", "general",
               "papers", "researcher", "project", "topic", "glossary"]

STD_ONLY_VARIANTS = ["llm_A_std", "llm_B_std", "llm_C_std"]
FULL_VARIANTS     = ["llm_A",     "llm_B",     "llm_C"]


# ── Mistral HTTP helper ───────────────────────────────────────────────────────
def mistral_call(messages, max_tokens=250, temperature=0.0):
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [API ERROR] {e}")
        time.sleep(3)
        return None


# ── CLASSIFY_PROMPT I/O ───────────────────────────────────────────────────────
PROMPT_RE = re.compile(
    r'(CLASSIFY_PROMPT\s*=\s*""")(.*?)(""")',
    re.DOTALL
)

def read_prompt(agent_py_path):
    with open(agent_py_path, encoding="utf-8") as f:
        src = f.read()
    m = PROMPT_RE.search(src)
    if not m:
        raise ValueError(f"CLASSIFY_PROMPT not found in {agent_py_path}")
    return m.group(2)

def write_prompt(agent_py_path, new_prompt):
    with open(agent_py_path, encoding="utf-8") as f:
        src = f.read()
    new_src = PROMPT_RE.sub(r'\g<1>' + new_prompt + r'\g<3>', src)
    with open(agent_py_path, "w", encoding="utf-8") as f:
        f.write(new_src)


# ── Classify a single query ───────────────────────────────────────────────────
def classify(prompt_template, query):
    prompt = prompt_template.replace("{query}", query)
    text = mistral_call([{"role": "user", "content": prompt}], max_tokens=200)
    if text is None:
        return {"category": "out_of_scope"}
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        text = m.group(1).strip() if m else text
    jm = re.search(r"\{[^{}]*\}", text)
    try:
        return json.loads(jm.group() if jm else text)
    except Exception:
        return {"category": "out_of_scope"}


# ── Load dev set ──────────────────────────────────────────────────────────────
def load_dev_set(mode="standard"):
    path = os.path.join(BENCH_DIR, "development_set_9class.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    queries = [q for q in data["queries"] if not q.get("_layer2_only")]
    if mode == "standard":
        queries = [q for q in queries if q.get("variant_type", "standard") == "standard"]
    return queries


# ── Accuracy test ─────────────────────────────────────────────────────────────
def accuracy_test(prompt, dev_set, verbose=False):
    correct, failures = 0, []
    by_cat = Counter(q["expected"] for q in dev_set)
    ok_cat = Counter()
    for entry in dev_set:
        res = classify(prompt, entry["query"])
        cat = res.get("category", "out_of_scope")
        if cat == entry["expected"]:
            correct += 1
            ok_cat[cat] += 1
            if verbose:
                print(f"  [OK] {cat:18s}  {entry['query'][:60]}")
        else:
            failures.append({
                "query": entry["query"],
                "expected": entry["expected"],
                "got": cat,
                "variant_type": entry.get("variant_type", "standard"),
            })
            print(f"  [!!] {entry['query'][:60]}")
            print(f"       Expected: {entry['expected']}, Got: {cat}")
    total = len(dev_set)
    return {
        "total": total,
        "correct": correct,
        "rate": round(correct / total, 4) if total else 0,
        "failures": failures,
        "by_category": dict(by_cat),
        "correct_by_category": dict(ok_cat),
    }


# ── Meta-LLM: generate improved prompt (conservative — add rules only) ────────
META_PROMPT = """You are an expert NLP engineer refining a query classifier prompt.

CURRENT PROMPT:
---
{current_prompt}
---

MISCLASSIFICATIONS (expected → got, query):
{failures}

TASK: Make the MINIMUM necessary changes to fix these misclassifications.
- Do NOT rewrite the whole prompt.
- Only ADD short disambiguation rules or clarifying notes to the existing text.
- You may add a "DISAMBIGUATION NOTES:" section at the end (before USER QUERY).
- Keep all existing category definitions unchanged.
- Keep the JSON output format line and the {{query}} placeholder unchanged.
- If an existing disambiguation note already covers the error, just leave it.
- Return ONLY the complete updated prompt text (no ```fences, no commentary).
"""

def improve_prompt(current_prompt, failures):
    fail_str = "\n".join(
        f"  - {f['expected']:18s} → {f['got']:18s}: \"{f['query']}\""
        for f in failures[:20]
    )
    msg = META_PROMPT.format(current_prompt=current_prompt, failures=fail_str)
    new_prompt = mistral_call(
        [{"role": "user", "content": msg}],
        max_tokens=1800,
        temperature=0.1,
    )
    return new_prompt.strip() if new_prompt else current_prompt


# ── Save trajectory ───────────────────────────────────────────────────────────
def save_trajectory(variant, iteration, accuracy, prompt, mode):
    traj_v = os.path.join(TRAJ_DIR, variant)
    os.makedirs(traj_v, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(traj_v, f"iter_{iteration:02d}_{ts}.json")
    data = {
        "timestamp": ts,
        "variant": variant,
        "iteration": iteration,
        "variants_mode": mode,
        "accuracy": {k: v for k, v in accuracy.items() if k != "failures"},
        "failures": accuracy["failures"],
        "prompt": prompt,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


# ── Construct one variant ─────────────────────────────────────────────────────
def construct_variant(variant, dev_mode="standard"):
    """
    dev_mode: 'standard' for std-only (50 q), 'all' for full (150 q).
    Always restores the best-seen prompt to agent.py at the end.
    Stops early if accuracy hasn't improved for PATIENCE iterations or
    if it drops more than DEGRADATION_LIMIT below the best.
    """
    print(f"\n{'='*70}")
    print(f"  CONSTRUCTION: {variant}  (mode={dev_mode})")
    print(f"{'='*70}")
    agent_py = os.path.join(AGENTS_DIR, variant, "agent.py")
    dev_set  = load_dev_set(dev_mode)
    print(f"  Dev set: {len(dev_set)} queries\n")

    best_rate   = 0.0
    best_prompt = read_prompt(agent_py)   # start with seed as fallback
    no_improve  = 0
    history     = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Iteration {iteration} ---")
        prompt = read_prompt(agent_py)
        acc = accuracy_test(prompt, dev_set)
        rate = acc["rate"]
        print(f"\n  Accuracy: {acc['correct']}/{acc['total']} ({rate:.1%})")

        # Per-category
        for cat in sorted(CATEGORIES):
            t = acc["by_category"].get(cat, 0)
            c = acc["correct_by_category"].get(cat, 0)
            print(f"    {cat:18s}: {c:2d}/{t:2d} ({c/t:.0%})" if t else f"    {cat:18s}: -")

        tpath = save_trajectory(variant, iteration, acc, prompt, dev_mode)
        print(f"  Trajectory: {tpath}")

        history.append({"iteration": iteration, "rate": rate, "failures": len(acc["failures"])})

        # Track best
        if rate > best_rate:
            best_rate   = rate
            best_prompt = prompt
            no_improve  = 0
        else:
            no_improve += 1

        # Convergence
        if rate >= TARGET_ACCURACY:
            print(f"\n  Converged ({rate:.1%} >= {TARGET_ACCURACY:.0%})")
            break

        # No failures
        if not acc["failures"]:
            print("  No failures — converged.")
            break

        # Early stop: patience exhausted
        if no_improve >= PATIENCE:
            print(f"  No improvement for {PATIENCE} iterations — stopping early.")
            break

        # Early stop: severe degradation
        if rate < best_rate - DEGRADATION_LIMIT:
            print(f"  Accuracy dropped {best_rate - rate:.1%} below best — stopping early.")
            break

        print(f"\n  Generating improved prompt ({len(acc['failures'])} failures)...")
        new_prompt = improve_prompt(prompt, acc["failures"])
        if new_prompt == prompt:
            print("  Meta-LLM returned same prompt — stopping.")
            break
        write_prompt(agent_py, new_prompt)
        print("  Prompt updated.")

    # Restore best prompt to agent.py
    current_in_file = read_prompt(agent_py)
    if current_in_file != best_prompt:
        write_prompt(agent_py, best_prompt)
        print(f"\n  Restored best prompt ({best_rate:.1%}) to agent.py")
    else:
        print(f"\n  Best prompt already in agent.py ({best_rate:.1%})")

    print(f"  Construction done. Best accuracy: {best_rate:.1%}")
    return {"variant": variant, "best_rate": best_rate, "history": history}


# ── Evaluate on a list of queries ─────────────────────────────────────────────
def evaluate_queries(prompt, queries, label=""):
    correct, failures = 0, []
    by_cat = Counter(q["expected"] for q in queries)
    ok_cat = Counter()
    for entry in queries:
        res = classify(prompt, entry["query"])
        cat = res.get("category", "out_of_scope")
        if cat == entry["expected"]:
            correct += 1
            ok_cat[cat] += 1
        else:
            failures.append({
                "query": entry["query"],
                "expected": entry["expected"],
                "got": cat,
            })
    total = len(queries)
    return {
        "label": label,
        "total": total,
        "correct": correct,
        "rate": round(correct / total, 4) if total else 0,
        "by_category": dict(by_cat),
        "correct_by_category": dict(ok_cat),
        "failures": failures,
    }


def evaluate_variant(variant):
    """Evaluate one variant on all sets: Tier1/2/3 standard + typo + grammar."""
    agent_py = os.path.join(AGENTS_DIR, variant, "agent.py")
    prompt   = read_prompt(agent_py)

    # Load standard set (already has follow-ups removed)
    with open(os.path.join(BENCH_DIR, "evaluation_set_9class.json"), encoding="utf-8") as f:
        std_data = json.load(f)["queries"]
    std_qs = [q for q in std_data if q.get("variant_type", "standard") == "standard"]

    tier1 = [q for q in std_qs if q.get("tier") == 1]
    tier2 = [q for q in std_qs if q.get("tier") == 2]
    tier3 = [q for q in std_qs if q.get("tier") == 3]

    # Load typo and grammar sets
    with open(os.path.join(BENCH_DIR, "evaluation_set_typo.json"), encoding="utf-8") as f:
        typo_qs = json.load(f)["queries"]
    with open(os.path.join(BENCH_DIR, "evaluation_set_grammar.json"), encoding="utf-8") as f:
        gram_qs = json.load(f)["queries"]

    results = {}
    sets = [
        ("tier1",   tier1),
        ("tier2",   tier2),
        ("tier3",   tier3),
        ("typo",    typo_qs),
        ("grammar", gram_qs),
    ]
    for label, qs in sets:
        print(f"    {label:12s} ({len(qs):3d} q)...", end=" ", flush=True)
        r = evaluate_queries(prompt, qs, label=label)
        results[label] = r
        print(f"{r['correct']}/{r['total']} ({r['rate']:.1%})")

    # Compute standard (all tiers) from individual results without extra API calls
    total_std = sum(results[t]["total"]   for t in ["tier1", "tier2", "tier3"])
    correct_std = sum(results[t]["correct"] for t in ["tier1", "tier2", "tier3"])
    by_cat_std = Counter()
    ok_cat_std = Counter()
    for t in ["tier1", "tier2", "tier3"]:
        by_cat_std.update(results[t]["by_category"])
        ok_cat_std.update(results[t]["correct_by_category"])
    results["standard"] = {
        "label": "standard",
        "total": total_std,
        "correct": correct_std,
        "rate": round(correct_std / total_std, 4) if total_std else 0,
        "by_category": dict(by_cat_std),
        "correct_by_category": dict(ok_cat_std),
        "failures": [],  # combined failures not stored to save memory
    }
    print(f"    {'standard':12s} ({total_std:3d} q)  {correct_std}/{total_std} ({correct_std/total_std:.1%})  [derived from tiers]")

    return results


# ── Full pipeline ─────────────────────────────────────────────────────────────
def run_all(phase="both", target_variant=None):
    results = {}
    os.makedirs(TRAJ_DIR, exist_ok=True)

    all_variants = STD_ONLY_VARIANTS + FULL_VARIANTS
    if target_variant:
        all_variants = [target_variant]

    def dev_mode_for(v):
        return "all" if v in FULL_VARIANTS else "standard"

    # ── Phase 1: Construct ────────────────────────────────────────────────────
    if phase in ("both", "construct"):
        print("\n" + "="*70)
        print("  PHASE 1: CONSTRUCTION")
        print("="*70)
        construction_summary = {}
        for v in all_variants:
            res = construct_variant(v, dev_mode_for(v))
            construction_summary[v] = res
        results["construction"] = construction_summary

    # ── Phase 2: Evaluate ─────────────────────────────────────────────────────
    if phase in ("both", "evaluate"):
        print("\n" + "="*70)
        print("  PHASE 2: EVALUATION")
        print("  Sets: Tier1 / Tier2 / Tier3 / standard(all) / typo / grammar")
        print("="*70)

        eval_results = {}
        for v in all_variants:
            print(f"\n  --- {v} ---")
            eval_results[v] = evaluate_variant(v)
        results["evaluation"] = eval_results

    # ── Report ────────────────────────────────────────────────────────────────
    if "evaluation" in results:
        report = generate_report(results)
        ts = time.strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(TRAJ_DIR, f"ablation_report_{ts}.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n  Report saved: {report_path}")

        if os.path.isdir(MATERIALS_DIR):
            mat_path = os.path.join(MATERIALS_DIR, f"ablation_report_10Oct_{ts}.md")
            with open(mat_path, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"  Report also saved: {mat_path}")

        json_path = os.path.join(TRAJ_DIR, f"ablation_results_{ts}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"  Results JSON: {json_path}")

        print("\n" + "="*70)
        print("  SUMMARY")
        print("="*70)
        print(report)

    return results


# ── Report generator ──────────────────────────────────────────────────────────
def generate_report(results):
    lines = []
    lines.append("# 10Oct Ablation Study — Full Report")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    lines.append("## Study Design")
    lines.append("- **std-only condition**: llm_A_std / B_std / C_std — built with 50 standard dev queries")
    lines.append("- **full condition**: llm_A / B / C — built with all 150 dev queries (standard + typo + grammar)")
    lines.append("- **Evaluation sets**: Standard Tier1 (116) / Tier2 (68) / Tier3 (54) / Typo L1-ES (77) / Grammar L1-ES (77)")
    lines.append("- **RQ1a**: T1→T2→T3 — vulnerability to phrasing complexity (any user)")
    lines.append("- **RQ1b**: T1→Typo / T1→Grammar — vulnerability to L2 Spanish noise")
    lines.append("- **RQ2**: std-only vs full agents on Typo/Grammar — can variant training help?")
    lines.append("- **No consistency test** (API call limit)")
    lines.append("- **LLM**: mistral-small-latest\n")

    if "construction" in results:
        lines.append("## Construction Summary")
        lines.append("| Variant | Condition | Best Dev Acc | Iterations |")
        lines.append("|---------|-----------|-------------|------------|")
        for v, cs in results["construction"].items():
            cond = "std-only" if "_std" in v else "full"
            iters = len(cs.get("history", []))
            lines.append(f"| {v} | {cond} | {cs['best_rate']:.1%} | {iters} |")
        lines.append("")

    if "evaluation" in results:
        eval_res = results["evaluation"]
        all_sets = ["tier1", "tier2", "tier3", "standard", "typo", "grammar"]
        variants_present = [v for v in STD_ONLY_VARIANTS + FULL_VARIANTS if v in eval_res]

        # ── Overall accuracy table ─────────────────────────────────────────
        lines.append("## Evaluation: Overall Accuracy by Set")
        header = "| Set (n) | " + " | ".join(variants_present) + " |"
        sep    = "|---------|" + "---------|" * len(variants_present)
        lines.append(header)
        lines.append(sep)
        set_labels = {
            "tier1":    "Tier 1 — standard   (116)",
            "tier2":    "Tier 2 — unusual    (68)",
            "tier3":    "Tier 3 — adversarial (54)",
            "standard": "Standard total      (238)",
            "typo":     "Typo L1-ES          (77)",
            "grammar":  "Grammar L1-ES       (77)",
        }
        for s in all_sets:
            label = set_labels.get(s, s)
            row = f"| {label} |"
            for v in variants_present:
                r = eval_res[v].get(s)
                if r:
                    row += f" {r['correct']}/{r['total']} ({r['rate']:.1%}) |"
                else:
                    row += " - |"
            lines.append(row)
        lines.append("")

        # ── RQ1: Vulnerability — Tier degradation ─────────────────────────
        lines.append("## RQ1a: Vulnerability to Tier Complexity (std-only agents avg)")
        lines.append("Comparison: Tier 1 (baseline) → Tier 2 → Tier 3 → Typo → Grammar\n")
        std_vs = [v for v in STD_ONLY_VARIANTS if v in eval_res]
        full_vs = [v for v in FULL_VARIANTS if v in eval_res]
        for group_label, group_vs in [("std-only", std_vs), ("full", full_vs)]:
            if not group_vs:
                continue
            lines.append(f"**{group_label} agents** (avg of {len(group_vs)}):")
            t1_avg = sum(eval_res[v]["tier1"]["rate"] for v in group_vs) / len(group_vs)
            for s in ["tier2", "tier3", "typo", "grammar"]:
                rates = [eval_res[v][s]["rate"] for v in group_vs if s in eval_res[v]]
                if not rates:
                    continue
                avg = sum(rates) / len(rates)
                delta = avg - t1_avg
                lines.append(f"- Tier 1 → {s:8s}: {t1_avg:.1%} → {avg:.1%}  (Δ = {delta:+.1%})")
            lines.append("")

        # ── RQ2: Can training on variants overcome L2 vulnerability? ───────
        lines.append("## RQ2: Effect of Variant Training on L2 Sets")
        lines.append("Comparison: std-only vs full agents on Typo and Grammar sets\n")
        lines.append("| Set | std-only avg | full avg | Δ (full − std) |")
        lines.append("|-----|-------------|----------|----------------|")
        for s in ["typo", "grammar"]:
            std_rates  = [eval_res[v][s]["rate"] for v in std_vs  if s in eval_res[v]]
            full_rates = [eval_res[v][s]["rate"] for v in full_vs if s in eval_res[v]]
            if std_rates and full_rates:
                avg_std  = sum(std_rates)  / len(std_rates)
                avg_full = sum(full_rates) / len(full_rates)
                delta    = avg_full - avg_std
                lines.append(f"| {s:7s} | {avg_std:.1%} | {avg_full:.1%} | {delta:+.1%} |")
        lines.append("")

        # ── Per-category breakdown for key sets ───────────────────────────
        for s in ["tier1", "typo", "grammar"]:
            lines.append(f"## Per-category accuracy — {s}")
            header = "| Category | " + " | ".join(variants_present) + " |"
            sep    = "|----------|" + "----------|" * len(variants_present)
            lines.append(header)
            lines.append(sep)
            for cat in CATEGORIES:
                row = f"| {cat} |"
                for v in variants_present:
                    r = eval_res[v].get(s, {})
                    t = r.get("by_category", {}).get(cat, 0)
                    c = r.get("correct_by_category", {}).get(cat, 0)
                    cell = f" {c}/{t} ({c/t:.0%}) |" if t else " - |"
                    row += cell
                lines.append(row)
            lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automate construction + evaluation (10Oct ablation)")
    parser.add_argument("--phase", choices=["construct", "evaluate", "both"], default="both")
    parser.add_argument("--variant", help="Run single variant only")
    args = parser.parse_args()
    run_all(phase=args.phase, target_variant=args.variant)
