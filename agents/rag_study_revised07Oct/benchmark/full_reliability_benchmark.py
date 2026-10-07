#!/usr/bin/env python3
"""
Full Reliability Benchmark — Rabanser et al. (2025) — 9-class taxonomy

Measures reliability dimensions with extended metrics for the 9-class taxonomy:

  CONSISTENCY
    C_traj: Classification consistency (K runs, same query → same category?)
      · by variant_type (standard / typo / grammar)
      · by class (which classes have more inconsistency?)

  ROBUSTNESS
    R_prompt: Accuracy degradation across variant types (standard → typo / grammar)
      · per variant_type
      · per variant_type × class

  PREDICTABILITY
    3-group confusion matrix: in_scope / general / out_of_scope
    (in_scope = papers + researcher + project + topic + glossary + organization + meta)

  SAFETY
    Level 1 (low risk):  errors within the in_scope group
    Level 2 (high risk): boundary errors between in_scope and general (both directions)

Usage:
    python3 full_reliability_benchmark.py
    python3 full_reliability_benchmark.py --agents rule_based_A,llm_A
    python3 full_reliability_benchmark.py --k-traj 3 --verbose
"""

import os
import sys
import json
import time
import re
import argparse
import importlib
import importlib.util
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))

AGENT_PATHS = {
    "rule_based_A": os.path.join(STUDY_DIR, "agents", "rule_based_A"),
    "rule_based_B": os.path.join(STUDY_DIR, "agents", "rule_based_B"),
    "rule_based_C": os.path.join(STUDY_DIR, "agents", "rule_based_C"),
    "llm_A":        os.path.join(STUDY_DIR, "agents", "llm_A"),
    "llm_B":        os.path.join(STUDY_DIR, "agents", "llm_B"),
    "llm_C":        os.path.join(STUDY_DIR, "agents", "llm_C"),
    "baseline":     os.path.join(STUDY_DIR, "agents", "baseline"),
}
LABELS = {
    "rule_based_A": "Rule-based A",
    "rule_based_B": "Rule-based B",
    "rule_based_C": "Rule-based C",
    "llm_A":        "LLM A",
    "llm_B":        "LLM B",
    "llm_C":        "LLM C",
    "baseline":     "Baseline",
}

# ── 3-group mapping ───────────────────────────────────────────────────────
IN_SCOPE = {"papers", "researcher", "project", "topic", "glossary", "organization", "meta"}
GENERAL  = {"general"}
OOS      = {"out_of_scope"}

def to_group(cat: str) -> str:
    if cat in IN_SCOPE:  return "in_scope"
    if cat in GENERAL:   return "general"
    return "out_of_scope"


# ── Loaders ───────────────────────────────────────────────────────────────

def load_agent(variant):
    agent_dir = AGENT_PATHS.get(variant, os.path.join(STUDY_DIR, "agents", variant))
    spec = importlib.util.spec_from_file_location(
        f"agent_{variant}", os.path.join(agent_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_eval_set(filename):
    with open(os.path.join(STUDY_DIR, "benchmark", filename)) as f:
        queries = json.load(f)["queries"]
    return [q for q in queries if not q.get("_layer2_only")]


def classify(agent, variant, query):
    if "llm" in variant:
        return agent._llm_classify(query)
    else:
        return agent._code_classify(query)


def strip_trace(response):
    return re.sub(r'<details.*?</details>', '', response or '', flags=re.DOTALL).strip()


# ═══════════════════════════════════════════════════════════════════════════
# CONSISTENCY  (C_traj, stratified by variant_type and class)
# ═══════════════════════════════════════════════════════════════════════════

def measure_consistency(agent, variant, eval_set, k=5):
    """
    C_traj overall + by variant_type + by class.

    For each query, run classification K times and check if the result is
    always the same. Reports rates for:
      - All queries combined
      - Per variant_type (standard / typo / grammar)
      - Per expected class
    """
    # Buckets: overall, by variant_type, by class
    buckets = {
        "overall":      defaultdict(int),
        "by_variant":   defaultdict(lambda: defaultdict(int)),
        "by_class":     defaultdict(lambda: defaultdict(int)),
    }
    issues = []

    for entry in eval_set:
        query = entry["query"]
        vtype = entry.get("variant_type", "standard")
        expected = entry["expected"]

        cats = [classify(agent, variant, query).get("category", "out_of_scope")
                for _ in range(k)]

        is_consistent = len(set(cats)) == 1

        buckets["overall"]["total"] += 1
        if is_consistent:
            buckets["overall"]["consistent"] += 1

        buckets["by_variant"][vtype]["total"] += 1
        if is_consistent:
            buckets["by_variant"][vtype]["consistent"] += 1

        buckets["by_class"][expected]["total"] += 1
        if is_consistent:
            buckets["by_class"][expected]["consistent"] += 1

        if not is_consistent:
            issues.append({
                "query": query, "expected": expected,
                "variant_type": vtype, "categories": cats,
            })

    def rate(d):
        t = d.get("total", 0)
        return round(d.get("consistent", 0) / t, 4) if t else 0

    overall = dict(buckets["overall"])
    overall["rate"] = rate(overall)

    by_variant = {
        vt: {"total": d["total"], "consistent": d["consistent"], "rate": rate(d)}
        for vt, d in buckets["by_variant"].items()
    }

    by_class = {
        cls: {"total": d["total"], "consistent": d["consistent"], "rate": rate(d)}
        for cls, d in buckets["by_class"].items()
    }

    return {
        "k": k,
        "overall": overall,
        "by_variant_type": by_variant,
        "by_class": by_class,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ROBUSTNESS  (R_prompt per variant_type, and per variant_type × class)
# ═══════════════════════════════════════════════════════════════════════════

def measure_robustness(agent, variant, eval_set):
    """
    R_prompt: accuracy by variant_type (standard / typo / grammar).

    Also reports accuracy by tier (standard queries only) and
    accuracy by variant_type × class.
    """
    by_variant  = defaultdict(lambda: {"total": 0, "correct": 0})
    by_tier     = defaultdict(lambda: {"total": 0, "correct": 0})
    by_vc       = defaultdict(lambda: defaultdict(lambda: {"total": 0, "correct": 0}))

    for entry in eval_set:
        query    = entry["query"]
        expected = entry["expected"]
        vtype    = entry.get("variant_type", "standard")
        tier     = entry.get("tier")

        result  = classify(agent, variant, query)
        cat_got = result.get("category", "out_of_scope")
        correct = (cat_got == expected)

        by_variant[vtype]["total"]   += 1
        if correct: by_variant[vtype]["correct"] += 1

        by_vc[vtype][expected]["total"]   += 1
        if correct: by_vc[vtype][expected]["correct"] += 1

        if tier is not None:
            by_tier[tier]["total"]   += 1
            if correct: by_tier[tier]["correct"] += 1

    def rate(d):
        t = d.get("total", 0)
        return round(d.get("correct", 0) / t, 4) if t else 0

    def to_dict(d):
        return {k: {"total": v["total"], "correct": v["correct"], "rate": rate(v)}
                for k, v in d.items()}

    # Degradation: standard accuracy vs typo / grammar
    std_rate   = rate(by_variant.get("standard", {}))
    typo_rate  = rate(by_variant.get("typo", {}))
    gram_rate  = rate(by_variant.get("grammar", {}))

    # Tier degradation (standard queries only)
    tier_rates = {t: rate(by_tier[t]) for t in sorted(by_tier)}
    t1 = tier_rates.get(1, 0)
    t3 = tier_rates.get(3, 0)
    tier_degradation = round(t1 - t3, 4) if t1 and t3 else 0

    # Per variant × class
    by_vc_out = {
        vt: to_dict(cls_dict)
        for vt, cls_dict in by_vc.items()
    }

    return {
        "by_variant_type": to_dict(by_variant),
        "degradation_std_to_typo":    round(std_rate - typo_rate, 4),
        "degradation_std_to_grammar": round(std_rate - gram_rate, 4),
        "by_tier_standard_only":      to_dict(by_tier),
        "degradation_tier1_to_tier3": tier_degradation,
        "by_variant_type_x_class":    by_vc_out,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PREDICTABILITY  (3-group confusion matrix)
# ═══════════════════════════════════════════════════════════════════════════

def measure_predictability(agent, variant, eval_set):
    """
    3-group confusion matrix: in_scope / general / out_of_scope.

    Also reports the programmatic path fraction (classes that go to
    deterministic paths vs LLM) as an additional predictability proxy.
    """
    groups = ["in_scope", "general", "out_of_scope"]
    # confusion[expected_group][predicted_group] = count
    confusion = {g: {g2: 0 for g2 in groups} for g in groups}
    group_totals = defaultdict(int)

    programmatic_cats = {"meta", "organization", "general", "out_of_scope",
                         "project", "researcher", "glossary"}
    prog_total = prog_correct = 0
    llm_total  = llm_correct  = 0

    for entry in eval_set:
        result  = classify(agent, variant, entry["query"])
        cat_got = result.get("category", "out_of_scope")
        expected = entry["expected"]

        exp_group = to_group(expected)
        got_group = to_group(cat_got)
        confusion[exp_group][got_group] += 1
        group_totals[exp_group] += 1

        correct = (cat_got == expected)
        if cat_got in programmatic_cats:
            prog_total += 1
            if correct: prog_correct += 1
        else:
            llm_total  += 1
            if correct: llm_correct  += 1

    # Normalise rows (recall per group)
    confusion_pct = {}
    for exp_g in groups:
        total = group_totals[exp_g]
        confusion_pct[exp_g] = {
            got_g: round(confusion[exp_g][got_g] / total, 4) if total else 0
            for got_g in groups
        }

    return {
        "confusion_counts":  confusion,
        "confusion_recall":  confusion_pct,
        "group_totals":      dict(group_totals),
        "programmatic_fraction": round(prog_total / (prog_total + llm_total), 4)
                                  if (prog_total + llm_total) else 0,
        "programmatic_accuracy": round(prog_correct / prog_total, 4) if prog_total else 0,
        "llm_path_accuracy":     round(llm_correct  / llm_total,  4) if llm_total  else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY  (Level 1: within in_scope; Level 2: in_scope ↔ general)
# ═══════════════════════════════════════════════════════════════════════════

def measure_safety(agent, variant, eval_set):
    """
    Safety proxy — two levels:

    Level 1 (low risk):  error WITHIN the in_scope group
        Expected = in_scope, Got = different in_scope class
        (User asked about RA research, got the wrong in_scope type)

    Level 2 (high risk): error crossing the in_scope / general boundary
        A: Expected = in_scope, Got = general  (false out-of-domain rejection)
        B: Expected = general,  Got = in_scope (false in-domain acceptance)
    """
    l1_total = l1_correct = 0
    l1_errors = []

    l2_total = 0
    l2_in_to_gen = 0    # in_scope → general
    l2_gen_to_in = 0    # general → in_scope
    l2_errors = []

    # Also track OOS accuracy (refusals)
    oos_total = oos_correct = 0
    oos_errors = []

    for entry in eval_set:
        result   = classify(agent, variant, entry["query"])
        cat_got  = result.get("category", "out_of_scope")
        expected = entry["expected"]

        exp_g = to_group(expected)
        got_g = to_group(cat_got)

        # ── Safety Level 1 ───────────────────────────────────────────────
        if exp_g == "in_scope":
            l1_total += 1
            if cat_got == expected:
                l1_correct += 1
            elif got_g == "in_scope":
                # Wrong in_scope class — Level 1 error
                l1_errors.append({
                    "query": entry["query"], "expected": expected, "got": cat_got,
                    "variant_type": entry.get("variant_type", "standard"),
                })
            # (errors to general or oos counted at Level 2)

        # ── Safety Level 2 ───────────────────────────────────────────────
        if exp_g == "in_scope" and got_g == "general":
            l2_total += 1
            l2_in_to_gen += 1
            l2_errors.append({
                "direction": "in_scope→general",
                "query": entry["query"], "expected": expected, "got": cat_got,
                "variant_type": entry.get("variant_type", "standard"),
            })
        elif exp_g == "general" and got_g == "in_scope":
            l2_total += 1
            l2_gen_to_in += 1
            l2_errors.append({
                "direction": "general→in_scope",
                "query": entry["query"], "expected": expected, "got": cat_got,
                "variant_type": entry.get("variant_type", "standard"),
            })

        # ── OOS refusal tracking ─────────────────────────────────────────
        if expected == "out_of_scope":
            oos_total += 1
            if cat_got == "out_of_scope":
                oos_correct += 1
            else:
                oos_errors.append({
                    "query": entry["query"], "got": cat_got,
                    "variant_type": entry.get("variant_type", "standard"),
                })

    l1_error_count = l1_total - l1_correct - l2_in_to_gen  # within-in_scope only
    return {
        "level1": {
            "description": "Errors within in_scope group (wrong in_scope class)",
            "in_scope_total":   l1_total,
            "correct":          l1_correct,
            "within_in_scope_errors": l1_error_count,
            "rate_correct":     round(l1_correct / l1_total, 4) if l1_total else 0,
            "errors":           l1_errors,
        },
        "level2": {
            "description": "Boundary errors between in_scope and general",
            "total_errors":     l2_total,
            "in_scope_to_general": l2_in_to_gen,
            "general_to_in_scope": l2_gen_to_in,
            "errors":           l2_errors,
        },
        "oos_refusal": {
            "total":    oos_total,
            "correct":  oos_correct,
            "rate":     round(oos_correct / oos_total, 4) if oos_total else 0,
            "errors":   oos_errors,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run_benchmark(agent_ids, eval_filename, k_traj=5, verbose=False):
    t_start   = time.time()
    eval_set  = load_eval_set(eval_filename)

    # Partition
    std_queries  = [e for e in eval_set if e.get("variant_type", "standard") == "standard"]
    typo_queries = [e for e in eval_set if e.get("variant_type") == "typo"]
    gram_queries = [e for e in eval_set if e.get("variant_type") == "grammar"]

    print(f"Evaluation set: {len(eval_set)} queries ({eval_filename})")
    print(f"  standard: {len(std_queries)}, typo: {len(typo_queries)}, grammar: {len(gram_queries)}")
    tiers = sorted(set(e.get("tier") for e in std_queries if e.get("tier") is not None))
    print(f"  Standard tiers: {tiers}")

    agents = {}
    for vid in agent_ids:
        print(f"\nLoading {LABELS.get(vid, vid)}...", end=" ", flush=True)
        agents[vid] = load_agent(vid)
        print("OK")

    results = {}

    for vid in agent_ids:
        agent = agents[vid]
        label = LABELS.get(vid, vid)
        print(f"\n{'='*70}\n  {label}\n{'='*70}")

        print(f"  Measuring consistency (K={k_traj})...")
        consistency = measure_consistency(agent, vid, eval_set, k=k_traj)

        print(f"  Measuring robustness (R_prompt by variant type)...")
        robustness = measure_robustness(agent, vid, eval_set)

        print(f"  Measuring predictability (3-group confusion matrix)...")
        predictability = measure_predictability(agent, vid, eval_set)

        print(f"  Measuring safety (Level 1 + Level 2)...")
        safety = measure_safety(agent, vid, eval_set)

        results[vid] = {
            "consistency":    consistency,
            "robustness":     robustness,
            "predictability": predictability,
            "safety":         safety,
        }

    elapsed = time.time() - t_start

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY REPORT
    # ═══════════════════════════════════════════════════════════════════════

    W = 18
    def header_row(label):
        h = f"  {label:<40}"
        for vid in agent_ids:
            h += f" {LABELS.get(vid, vid):>{W}}"
        return h

    def data_row(label, getter, fmt=".1%"):
        row = f"    {label:<38}"
        for vid in agent_ids:
            try:
                val = getter(results[vid])
                row += f" {val:>{W}{fmt}}"
            except Exception:
                row += f" {'—':>{W}}"
        return row

    sep = f"  {'-'*(40 + (W+1)*len(agent_ids))}"

    print(f"\n{'='*80}")
    print(f"  FULL RELIABILITY BENCHMARK — Rabanser et al. (2025) — 9-class")
    print(f"  {len(eval_set)} queries | {len(agent_ids)} agents | {elapsed:.0f}s")
    print(f"{'='*80}")
    print(header_row("Metric"))
    print(sep)

    # ── CONSISTENCY ───────────────────────────────────────────────────────
    print("  CONSISTENCY")
    print(data_row(f"C_traj overall (K={k_traj})",
                   lambda r: r["consistency"]["overall"]["rate"]))

    for vt in ["standard", "typo", "grammar"]:
        print(data_row(f"  C_traj {vt}",
                       lambda r, v=vt: r["consistency"]["by_variant_type"].get(v, {}).get("rate", 0)))

    # Worst-class consistency
    print(f"\n    Per-class C_traj:")
    all_classes = sorted(set(e["expected"] for e in eval_set))
    for cls in all_classes:
        print(data_row(f"  {cls}",
                       lambda r, c=cls: r["consistency"]["by_class"].get(c, {}).get("rate", 0)))

    # ── ROBUSTNESS ────────────────────────────────────────────────────────
    print(f"\n  ROBUSTNESS (R_prompt)")
    for vt in ["standard", "typo", "grammar"]:
        print(data_row(f"  Accuracy {vt}",
                       lambda r, v=vt: r["robustness"]["by_variant_type"].get(v, {}).get("rate", 0)))

    print(data_row("  Degradation std → typo",
                   lambda r: r["robustness"]["degradation_std_to_typo"]))
    print(data_row("  Degradation std → grammar",
                   lambda r: r["robustness"]["degradation_std_to_grammar"]))

    if tiers:
        print(f"\n    By tier (standard queries only):")
        for t in tiers:
            print(data_row(f"  Tier {t}",
                           lambda r, tier=t: r["robustness"]["by_tier_standard_only"].get(tier, {}).get("rate", 0)))
        print(data_row("  Degradation T1→T3",
                       lambda r: r["robustness"]["degradation_tier1_to_tier3"]))

    # ── PREDICTABILITY ────────────────────────────────────────────────────
    print(f"\n  PREDICTABILITY (3-group confusion matrix — row = expected, col = predicted)")
    groups = ["in_scope", "general", "out_of_scope"]
    for vid in agent_ids:
        print(f"\n    {LABELS.get(vid, vid)}:")
        col_w = 14
        hdr = f"    {'':20s}"
        for g in groups:
            hdr += f" {g:>{col_w}}"
        print(hdr)
        cm = results[vid]["predictability"]["confusion_recall"]
        cm_c = results[vid]["predictability"]["confusion_counts"]
        for exp_g in groups:
            row = f"    {exp_g:<20s}"
            for got_g in groups:
                pct = cm[exp_g][got_g]
                cnt = cm_c[exp_g][got_g]
                cell = f"{pct:.0%}({cnt})"
                row += f" {cell:>{col_w}}"
            print(row)

    print()
    print(data_row("  Programmatic fraction",
                   lambda r: r["predictability"]["programmatic_fraction"]))
    print(data_row("  Programmatic accuracy",
                   lambda r: r["predictability"]["programmatic_accuracy"]))
    print(data_row("  LLM path accuracy",
                   lambda r: r["predictability"]["llm_path_accuracy"]))

    # ── SAFETY ────────────────────────────────────────────────────────────
    print(f"\n  SAFETY")
    print(data_row("  Level 1: in_scope accuracy",
                   lambda r: r["safety"]["level1"]["rate_correct"]))
    print(data_row("  Level 1: within-in_scope errors (N)",
                   lambda r: r["safety"]["level1"]["within_in_scope_errors"],
                   fmt="d"))
    print(data_row("  Level 2: in_scope → general (N)",
                   lambda r: r["safety"]["level2"]["in_scope_to_general"],
                   fmt="d"))
    print(data_row("  Level 2: general → in_scope (N)",
                   lambda r: r["safety"]["level2"]["general_to_in_scope"],
                   fmt="d"))
    print(data_row("  OOS refusal rate",
                   lambda r: r["safety"]["oos_refusal"]["rate"]))

    # ── CONSISTENCY ISSUES ────────────────────────────────────────────────
    if verbose:
        for vid in agent_ids:
            issues = results[vid]["consistency"]["issues"]
            if issues:
                print(f"\n  Consistency issues — {LABELS.get(vid, vid)} ({len(issues)}):")
                for iss in issues:
                    print(f"    [{iss['variant_type']}] {iss['query'][:60]}")
                    print(f"      expected={iss['expected']}, got={set(iss['categories'])}")

        for vid in agent_ids:
            l2 = results[vid]["safety"]["level2"]["errors"]
            if l2:
                print(f"\n  Safety Level 2 errors — {LABELS.get(vid, vid)} ({len(l2)}):")
                for e in l2:
                    print(f"    [{e['direction']}][{e['variant_type']}] {e['query'][:60]}")
                    print(f"      expected={e['expected']}, got={e['got']}")

    print(f"\n  Time elapsed: {elapsed:.1f}s")
    print(f"{'='*80}")

    # ── SAVE ──────────────────────────────────────────────────────────────
    out_data = {
        "timestamp":     time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s":     round(elapsed, 1),
        "eval_set":      eval_filename,
        "eval_set_size": len(eval_set),
        "k_traj":        k_traj,
        "agents":        agent_ids,
    }
    for vid in agent_ids:
        r = results[vid]
        out_data[vid] = {
            "consistency": {
                "overall":          r["consistency"]["overall"],
                "by_variant_type":  r["consistency"]["by_variant_type"],
                "by_class":         r["consistency"]["by_class"],
                "issues":           r["consistency"]["issues"],
            },
            "robustness":     r["robustness"],
            "predictability": r["predictability"],
            "safety":         r["safety"],
        }

    results_dir = os.path.join(STUDY_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"full_reliability_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full Reliability Benchmark — 9-class taxonomy (Rabanser et al. 2025)")
    parser.add_argument("--eval-set", type=str, default="evaluation_set_typo.json")
    parser.add_argument("--agents",   type=str, default="llm_A,llm_B,llm_C")
    parser.add_argument("--k-traj",   type=int, default=5, help="K for C_traj consistency")
    parser.add_argument("--verbose",  "-v", action="store_true")
    args = parser.parse_args()

    agent_ids = [a.strip() for a in args.agents.split(",")]
    run_benchmark(agent_ids, args.eval_set, k_traj=args.k_traj, verbose=args.verbose)
