#!/usr/bin/env python3
"""
Automated Agent Construction Protocol — Phase B

Runs both classifiers against the development set, reports accuracy,
and identifies misclassifications for the next iteration.

Usage:
    python3 constructor.py                    # Run both
    python3 constructor.py --variant rule_based
    python3 constructor.py --variant llm_based
    python3 constructor.py --verbose
"""

import os
import sys
import json
import time
import argparse
import importlib
import importlib.util

# Load env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))


def load_agent(variant):
    """Load an agent from agents/<variant>/agent.py."""
    agent_dir = os.path.join(STUDY_DIR, "agents", variant)
    spec = importlib.util.spec_from_file_location(
        f"agent_{variant}", os.path.join(agent_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_dev_set():
    """Load the development query set."""
    path = os.path.join(STUDY_DIR, "benchmark", "development_set.json")
    with open(path) as f:
        data = json.load(f)
    return data["queries"]


def classify_query(agent, variant, query):
    """Run classification for a single query."""
    if variant == "rule_based":
        return agent._code_classify(query)
    elif variant == "llm_based":
        return agent._llm_classify(query)
    else:
        raise ValueError(f"Unknown variant: {variant}")


def run_accuracy_test(agent, variant, dev_set, verbose=False):
    """Run all dev queries and compute accuracy."""
    total = 0
    correct = 0
    failures = []

    for entry in dev_set:
        query = entry["query"]
        expected = entry["expected"]
        result = classify_query(agent, variant, query)
        cat = result.get("category", "general")
        total += 1

        if cat == expected:
            correct += 1
            if verbose:
                print(f"  [OK] {cat:18s}  {query[:60]}")
        else:
            failures.append({
                "query": query,
                "expected": expected,
                "got": cat,
                "full_result": result,
            })
            print(f"  [!!] {query[:60]}")
            print(f"       Expected: {expected}, Got: {cat}")

    rate = correct / total if total else 0
    return {
        "total": total,
        "correct": correct,
        "rate": round(rate, 4),
        "failures": failures,
    }


def run_consistency_test(agent, variant, dev_set, k=5, verbose=False):
    """Run each query K times, check classification consistency."""
    total = 0
    consistent = 0
    inconsistent = []

    for entry in dev_set:
        query = entry["query"]
        categories = []
        for _ in range(k):
            result = classify_query(agent, variant, query)
            categories.append(result.get("category", "general"))

        total += 1
        if len(set(categories)) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {categories[0]:18s}  {query[:55]} (x{k})")
        else:
            inconsistent.append({
                "query": query,
                "expected": entry["expected"],
                "categories": categories,
            })
            print(f"  [!!] {query[:55]:55s} → {set(categories)}")

    rate = consistent / total if total else 0
    return {
        "total": total,
        "consistent": consistent,
        "rate": round(rate, 4),
        "inconsistent": inconsistent,
    }


def run_iteration(variant, verbose=False, k_consistency=5):
    """Run one iteration of the construction loop for a variant."""
    print(f"\n{'='*70}")
    print(f"  Construction Iteration — {variant}")
    print(f"{'='*70}")

    # Load
    print(f"\nLoading {variant}...", end=" ", flush=True)
    agent = load_agent(variant)
    print("OK")

    dev_set = load_dev_set()
    print(f"Development set: {len(dev_set)} queries\n")

    # Accuracy
    print(f"--- Accuracy Test ---")
    accuracy = run_accuracy_test(agent, variant, dev_set, verbose)
    print(f"\nAccuracy: {accuracy['correct']}/{accuracy['total']} ({accuracy['rate']:.1%})")

    # Consistency (only for LLM-based, rule-based is deterministic by definition)
    consistency = None
    if variant == "llm_based":
        print(f"\n--- Consistency Test (K={k_consistency}) ---")
        consistency = run_consistency_test(agent, variant, dev_set, k=k_consistency, verbose=verbose)
        print(f"\nConsistency: {consistency['consistent']}/{consistency['total']} ({consistency['rate']:.1%})")

    # Summary
    print(f"\n{'='*70}")
    print(f"  Summary — {variant}")
    print(f"{'='*70}")
    print(f"  Accuracy:    {accuracy['rate']:.1%} ({accuracy['correct']}/{accuracy['total']})")
    if consistency:
        print(f"  Consistency: {consistency['rate']:.1%} ({consistency['consistent']}/{consistency['total']})")
    if accuracy['failures']:
        print(f"  Failures:    {len(accuracy['failures'])}")
        print(f"\n  Misclassifications (for next iteration):")
        for f in accuracy['failures']:
            print(f"    {f['expected']:18s} → {f['got']:18s}  \"{f['query']}\"")

    # Save trajectory
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    traj_dir = os.path.join(STUDY_DIR, "construction", f"{variant}_trajectory")
    os.makedirs(traj_dir, exist_ok=True)
    traj_path = os.path.join(traj_dir, f"iteration_{timestamp}.json")

    traj_data = {
        "timestamp": timestamp,
        "variant": variant,
        "accuracy": {k: v for k, v in accuracy.items() if k != "failures"},
        "failures": accuracy["failures"],
    }
    if consistency:
        traj_data["consistency"] = {k: v for k, v in consistency.items() if k != "inconsistent"}
        traj_data["consistency_issues"] = consistency.get("inconsistent", [])

    with open(traj_path, "w") as f:
        json.dump(traj_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Trajectory saved: {traj_path}")

    return accuracy, consistency


def main():
    parser = argparse.ArgumentParser(description="Construction Protocol — Phase B")
    parser.add_argument("--variant", choices=["rule_based", "llm_based"],
                        help="Run single variant (default: both)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--k", type=int, default=5, help="K for consistency test")
    args = parser.parse_args()

    variants = [args.variant] if args.variant else ["rule_based", "llm_based"]

    for v in variants:
        run_iteration(v, verbose=args.verbose, k_consistency=args.k)


if __name__ == "__main__":
    main()
