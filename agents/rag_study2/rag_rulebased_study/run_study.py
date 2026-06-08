#!/usr/bin/env python3
"""
Rule-Based Generalisation Study

Tests whether rule-based classification improves with:
  Phase 1: More training queries (larger dev set, narrow patterns)
  Phase 2: Generalisation mechanisms (synonym expansion, stemming, etc.)

Evaluates all phases on the same 120-query evaluation set.

Usage:
    python3 run_study.py --phase phase1_more_queries
    python3 run_study.py --phase phase2_generalised
    python3 run_study.py --all
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
RBSTUDY_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))


def load_agent(phase_dir):
    spec = importlib.util.spec_from_file_location(
        f"agent_{os.path.basename(phase_dir)}",
        os.path.join(phase_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_queries(path):
    with open(path) as f:
        return json.load(f)["queries"]


def run_accuracy(agent, queries, label, verbose=False):
    total = correct = 0
    failures = []
    by_cat = {}

    for entry in queries:
        query, expected = entry["query"], entry["expected"]
        result = agent._code_classify(query)
        cat = result.get("category", "general")
        total += 1
        if expected not in by_cat:
            by_cat[expected] = {"total": 0, "correct": 0}
        by_cat[expected]["total"] += 1

        if cat == expected:
            correct += 1
            by_cat[expected]["correct"] += 1
            if verbose:
                print(f"  [OK] {cat:18s}  {query[:60]}")
        else:
            failures.append({"query": query, "expected": expected, "got": cat})
            print(f"  [!!] {query[:60]}")
            print(f"       Expected: {expected}, Got: {cat}")

    for c in by_cat:
        s = by_cat[c]
        s["rate"] = round(s["correct"] / s["total"], 3) if s["total"] else 0

    rate = correct / total if total else 0
    print(f"\n  {label}: {correct}/{total} ({rate:.1%})")
    return {"total": total, "correct": correct, "rate": round(rate, 4),
            "failures": failures, "by_category": by_cat}


def run_phase(phase_name, verbose=False):
    phase_dir = os.path.join(RBSTUDY_DIR, phase_name)
    print(f"\n{'='*70}")
    print(f"  {phase_name}")
    print(f"{'='*70}")

    print(f"\nLoading agent...", end=" ", flush=True)
    agent = load_agent(phase_dir)
    print("OK")

    # Dev set accuracy
    dev_path = os.path.join(RBSTUDY_DIR, "development_set_large.json")
    dev_queries = load_queries(dev_path)
    print(f"\n--- Development Set ({len(dev_queries)} queries) ---")
    dev_result = run_accuracy(agent, dev_queries, "Dev accuracy", verbose)

    # Eval set accuracy
    eval_path = os.path.join(STUDY_DIR, "benchmark", "evaluation_set.json")
    eval_queries = load_queries(eval_path)
    print(f"\n--- Evaluation Set ({len(eval_queries)} unseen queries) ---")
    eval_result = run_accuracy(agent, eval_queries, "Eval accuracy", verbose)

    # Generalisation gap
    gap = round(dev_result["rate"] - eval_result["rate"], 4)

    print(f"\n--- Summary ---")
    print(f"  Dev accuracy:    {dev_result['rate']:.1%}")
    print(f"  Eval accuracy:   {eval_result['rate']:.1%}")
    print(f"  Generalisation gap: {gap:.1%}")

    # Per-category eval
    print(f"\n  {'Category':<20} {'Eval acc':>10} {'n':>5}")
    print(f"  {'-'*35}")
    for cat in sorted(eval_result["by_category"].keys()):
        s = eval_result["by_category"][cat]
        print(f"  {cat:<20} {s['rate']:>9.0%} {s['total']:>5}")

    # Save
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": phase_name,
        "dev": {"total": dev_result["total"], "correct": dev_result["correct"],
                "rate": dev_result["rate"], "failures_count": len(dev_result["failures"])},
        "eval": {"total": eval_result["total"], "correct": eval_result["correct"],
                 "rate": eval_result["rate"], "by_category": eval_result["by_category"]},
        "eval_failures": eval_result["failures"],
        "generalisation_gap": gap,
    }
    out_path = os.path.join(RBSTUDY_DIR, "results",
                            f"{phase_name}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=str, help="Phase to run")
    parser.add_argument("--all", action="store_true", help="Run all phases")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    phases = []
    if args.all:
        for d in sorted(os.listdir(RBSTUDY_DIR)):
            if os.path.isdir(os.path.join(RBSTUDY_DIR, d)) and d.startswith("phase"):
                phases.append(d)
    elif args.phase:
        phases = [args.phase]
    else:
        phases = ["phase1_more_queries"]

    all_results = {}
    for phase in phases:
        all_results[phase] = run_phase(phase, args.verbose)

    if len(all_results) > 1:
        print(f"\n{'='*70}")
        print(f"  COMPARISON")
        print(f"{'='*70}")
        print(f"  {'Phase':<30} {'Dev':>8} {'Eval':>8} {'Gap':>8}")
        print(f"  {'-'*54}")
        for phase, r in all_results.items():
            print(f"  {phase:<30} {r['dev']['rate']:>7.1%} {r['eval']['rate']:>7.1%} {r['generalisation_gap']:>7.1%}")


if __name__ == "__main__":
    main()
