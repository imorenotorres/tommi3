#!/usr/bin/env python3
"""
Reliability Benchmark — Final evaluation on unseen queries.

Runs Rule-based and LLM-based classifiers on the evaluation set
(never seen during construction) and measures:
  1. Classification accuracy
  2. Classification consistency (K runs)
  3. Paraphrase robustness (by query type)
  4. Classification agreement (Rule-based vs LLM-based)

Based on Rabanser et al. (2025) reliability framework.

Usage:
    python3 reliability_benchmark.py
    python3 reliability_benchmark.py --verbose
    python3 reliability_benchmark.py --json
    python3 reliability_benchmark.py --eval-set evaluation_set_extended.json
    python3 reliability_benchmark.py --agents rule_based,llm_based,phase2
"""

import os
import sys
import json
import time
import argparse
import importlib
import importlib.util

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))


AGENT_PATHS = {
    "rule_based": os.path.join(STUDY_DIR, "agents", "rule_based"),
    "llm_based": os.path.join(STUDY_DIR, "agents", "llm_based"),
    "phase2": os.path.join(STUDY_DIR, "rag_rulebased_study", "phase2_generalised"),
}

def load_agent(variant):
    agent_dir = AGENT_PATHS.get(variant, os.path.join(STUDY_DIR, "agents", variant))
    spec = importlib.util.spec_from_file_location(
        f"agent_{variant}", os.path.join(agent_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_eval_set(filename="evaluation_set.json"):
    path = os.path.join(STUDY_DIR, "benchmark", filename)
    with open(path) as f:
        data = json.load(f)
    return data["queries"]


def classify(agent, variant, query):
    if variant == "llm_based":
        return agent._llm_classify(query)
    else:
        return agent._code_classify(query)


def test_accuracy(agent, variant, eval_set, verbose=False):
    """Classification accuracy on evaluation set."""
    total = correct = 0
    failures = []
    by_category = {}

    for entry in eval_set:
        query, expected = entry["query"], entry["expected"]
        result = classify(agent, variant, query)
        cat = result.get("category", "general")
        total += 1

        if expected not in by_category:
            by_category[expected] = {"total": 0, "correct": 0}
        by_category[expected]["total"] += 1

        if cat == expected:
            correct += 1
            by_category[expected]["correct"] += 1
            if verbose:
                print(f"  [OK] {cat:18s}  {query[:60]}")
        else:
            failures.append({"query": query, "expected": expected, "got": cat,
                             "type": entry.get("type", "")})
            print(f"  [!!] {query[:60]}")
            print(f"       Expected: {expected}, Got: {cat}")

    # Per-category rates
    for cat in by_category:
        s = by_category[cat]
        s["rate"] = round(s["correct"] / s["total"], 3) if s["total"] else 0

    rate = correct / total if total else 0
    return {
        "total": total, "correct": correct, "rate": round(rate, 4),
        "failures": failures, "by_category": by_category,
    }


def test_consistency(agent, variant, eval_set, k=5, verbose=False):
    """Classification consistency — K runs per query."""
    total = consistent = 0
    issues = []

    for entry in eval_set:
        query = entry["query"]
        cats = []
        for _ in range(k):
            result = classify(agent, variant, query)
            cats.append(result.get("category", "general"))
        total += 1
        if len(set(cats)) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {cats[0]:18s}  {query[:55]} (x{k})")
        else:
            issues.append({"query": query, "expected": entry["expected"],
                           "categories": cats})
            print(f"  [!!] {query[:55]:55s} → {set(cats)}")

    rate = consistent / total if total else 0
    return {"total": total, "consistent": consistent, "rate": round(rate, 4),
            "issues": issues}


def test_agreement(rb_agent, llm_agent, eval_set, verbose=False):
    """Classification agreement between Rule-based and LLM-based."""
    total = agree = 0
    v3_correct = v4_correct = both_wrong = 0
    disagreements = []

    for entry in eval_set:
        query, expected = entry["query"], entry["expected"]
        rb_result = classify(rb_agent, "rule_based", query)
        llm_result = classify(llm_agent, "llm_based", query)
        rb_cat = rb_result.get("category", "general")
        llm_cat = llm_result.get("category", "general")
        total += 1

        if rb_cat == llm_cat:
            agree += 1
            if verbose:
                print(f"  [==] {rb_cat:18s}  {query[:55]}")
        else:
            rb_ok = (rb_cat == expected)
            llm_ok = (llm_cat == expected)
            if rb_ok and not llm_ok:
                v3_correct += 1
            elif llm_ok and not rb_ok:
                v4_correct += 1
            else:
                both_wrong += 1
            disagreements.append({
                "query": query, "expected": expected,
                "rule_based": rb_cat, "llm_based": llm_cat,
                "rb_correct": rb_ok, "llm_correct": llm_ok,
            })
            marker = "RB✓" if rb_ok else ("LLM✓" if llm_ok else "both✗")
            print(f"  [!=] {query[:45]:45s}  RB={rb_cat:15s} LLM={llm_cat:15s} [{marker}]")

    rate = agree / total if total else 0
    return {
        "total": total, "agree": agree, "rate": round(rate, 4),
        "rb_correct_when_disagree": v3_correct,
        "llm_correct_when_disagree": v4_correct,
        "both_wrong_when_disagree": both_wrong,
        "disagreements": disagreements,
    }


def run_all(verbose=False, output_json=False, k=5, eval_filename="evaluation_set.json",
            agent_ids=None):
    t_start = time.time()
    eval_set = load_eval_set(eval_filename)
    print(f"Evaluation set: {len(eval_set)} queries ({eval_filename})\n")

    if agent_ids is None:
        agent_ids = ["rule_based", "llm_based"]

    # Load agents
    agents = {}
    labels = {"rule_based": "Rule-based (narrow)", "llm_based": "LLM-based",
              "phase2": "Rule-based (generalised)"}
    for vid in agent_ids:
        label = labels.get(vid, vid)
        print(f"Loading {label}...", end=" ", flush=True)
        agents[vid] = load_agent(vid)
        print("OK")

    results = {}

    # --- Accuracy ---
    for variant in agent_ids:
        agent = agents[variant]
        label = labels.get(variant, variant)
        print(f"\n{'='*70}")
        print(f"  ACCURACY — {label}")
        print(f"{'='*70}")
        results[f"{variant}_accuracy"] = test_accuracy(agent, variant, eval_set, verbose)
        r = results[f"{variant}_accuracy"]
        print(f"\n  Accuracy: {r['correct']}/{r['total']} ({r['rate']:.1%})")

    # --- Consistency ---
    for variant in agent_ids:
        agent = agents[variant]
        label = labels.get(variant, variant)
        print(f"\n{'='*70}")
        print(f"  CONSISTENCY (K={k}) — {label}")
        print(f"{'='*70}")
        results[f"{variant}_consistency"] = test_consistency(agent, variant, eval_set, k=k, verbose=verbose)
        r = results[f"{variant}_consistency"]
        print(f"\n  Consistency: {r['consistent']}/{r['total']} ({r['rate']:.1%})")

    # --- Agreement (only if both rule_based and llm_based are present) ---
    if "rule_based" in agents and "llm_based" in agents:
        print(f"\n{'='*70}")
        print(f"  CLASSIFICATION AGREEMENT (Rule-based vs LLM-based)")
        print(f"{'='*70}")
        results["agreement"] = test_agreement(agents["rule_based"], agents["llm_based"], eval_set, verbose)
        ag = results["agreement"]
        print(f"\n  Agreement: {ag['agree']}/{ag['total']} ({ag['rate']:.1%})")
        print(f"  When disagree — RB correct: {ag['rb_correct_when_disagree']}, "
              f"LLM correct: {ag['llm_correct_when_disagree']}, "
              f"both wrong: {ag['both_wrong_when_disagree']}")

    elapsed = time.time() - t_start

    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"  RELIABILITY BENCHMARK — Summary (Rabanser et al. 2025)")
    print(f"{'='*70}")
    print(f"  Evaluation set: {len(eval_set)} queries ({eval_filename})")
    print(f"")

    # Header
    header = f"  {'Metric':<35}"
    for vid in agent_ids:
        header += f" {labels.get(vid, vid):>20}"
    print(header)
    print(f"  {'-'*(35 + 21 * len(agent_ids))}")

    # Accuracy row
    row = f"  {'Accuracy':<35}"
    for vid in agent_ids:
        row += f" {results[f'{vid}_accuracy']['rate']:>19.1%}"
    print(row)

    # Consistency row
    row = f"  {'Consistency (C_traj, K=' + str(k) + ')':<35}"
    for vid in agent_ids:
        row += f" {results[f'{vid}_consistency']['rate']:>19.1%}"
    print(row)

    print()

    # Per-category accuracy
    all_cats = set()
    for vid in agent_ids:
        all_cats.update(results[f"{vid}_accuracy"]["by_category"].keys())
    all_cats = sorted(all_cats)

    header = f"  {'Category':<20}"
    for vid in agent_ids:
        header += f" {labels.get(vid, vid)[:12]:>12}"
    header += f" {'n':>5}"
    print(header)
    print(f"  {'-'*(20 + 13 * len(agent_ids) + 6)}")

    for cat in all_cats:
        row = f"  {cat:<20}"
        n = 0
        for vid in agent_ids:
            s = results[f"{vid}_accuracy"]["by_category"].get(cat, {"correct": 0, "total": 0, "rate": 0})
            row += f" {s['rate']:>11.0%}"
            n = max(n, s['total'])
        row += f" {n:>5}"
        print(row)

    print(f"\n  Time elapsed: {elapsed:.1f}s")
    print(f"{'='*70}")

    if output_json:
        out = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "eval_set_size": len(eval_set),
            "k_consistency": k,
            "rule_based": {
                "accuracy": {k: v for k, v in rb_acc.items() if k != "failures"},
                "accuracy_failures": rb_acc["failures"],
                "consistency": {k: v for k, v in rb_con.items() if k != "issues"},
                "consistency_issues": rb_con["issues"],
            },
            "llm_based": {
                "accuracy": {k: v for k, v in llm_acc.items() if k != "failures"},
                "accuracy_failures": llm_acc["failures"],
                "consistency": {k: v for k, v in llm_con.items() if k != "issues"},
                "consistency_issues": llm_con["issues"],
            },
            "agreement": {k: v for k, v in ag.items() if k != "disagreements"},
            "agreement_disagreements": ag["disagreements"],
        }
        results_dir = os.path.join(STUDY_DIR, "results")
        os.makedirs(results_dir, exist_ok=True)
        out_path = os.path.join(results_dir, f"reliability_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reliability Benchmark (Rabanser et al. 2025)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true", help="Save results as JSON")
    parser.add_argument("--k", type=int, default=5, help="K for consistency test")
    parser.add_argument("--eval-set", type=str, default="evaluation_set.json",
                        help="Evaluation set filename")
    parser.add_argument("--agents", type=str, default=None,
                        help="Comma-separated agent IDs (e.g. rule_based,llm_based,phase2)")
    args = parser.parse_args()

    agent_ids = None
    if args.agents:
        agent_ids = [a.strip() for a in args.agents.split(",")]

    run_all(verbose=args.verbose, output_json=args.json, k=args.k,
            eval_filename=args.eval_set, agent_ids=agent_ids)
