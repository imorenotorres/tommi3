#!/usr/bin/env python3
"""
Automated Agent Construction Protocol — 9-class taxonomy (19BSept)

Extended dev set: 150 queries (50 standard / 50 L2-typo / 50 L2-grammar).

Key addition vs 19Sept:
  --variants {standard,all}   Which variant types to include during construction.
                               'standard' replicates 19Sept behaviour.
                               'all' exposes the builder to L2 orthographic and
                               grammatical errors, testing whether this yields
                               more robust rules.
  --run N                     Run label (1, 2, 3 …) for independent construction
                               runs under construction/<variant>_trajectory/run_N/.

Usage:
    python3 constructor.py                              # standard queries, single run
    python3 constructor.py --variant auto_rule_based
    python3 constructor.py --variants all --run 2
    python3 constructor.py --verbose
"""

import os
import sys
import json
import time
import argparse
import importlib
import importlib.util
from collections import Counter

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))


def load_agent(variant):
    agent_dir = os.path.join(STUDY_DIR, "agents", variant)
    spec = importlib.util.spec_from_file_location(
        f"agent_{variant}", os.path.join(agent_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_dev_set(variants_mode="standard"):
    """
    Load dev set queries.

    variants_mode:
      'standard' — only standard queries (replicates 19Sept construction)
      'all'      — standard + l2_typo + l2_grammar queries
    """
    path = os.path.join(STUDY_DIR, "benchmark", "development_set_9class.json")
    with open(path) as f:
        data = json.load(f)

    queries = [q for q in data["queries"] if not q.get("_layer2_only", False)]

    if variants_mode == "standard":
        queries = [q for q in queries if q.get("variant", "standard") == "standard"]
    # 'all' keeps everything

    return queries


def classify_query(agent, variant, query):
    if "rule_based" in variant:
        return agent._code_classify(query)
    elif "llm" in variant:
        return agent._llm_classify(query)
    else:
        raise ValueError(f"Unknown variant: {variant}")


def run_accuracy_test(agent, variant, dev_set, verbose=False):
    total = 0
    correct = 0
    failures = []
    by_category = Counter()
    correct_by_category = Counter()

    for entry in dev_set:
        query = entry["query"]
        expected = entry["expected"]
        result = classify_query(agent, variant, query)
        cat = result.get("category", "out_of_scope")
        total += 1
        by_category[expected] += 1

        if cat == expected:
            correct += 1
            correct_by_category[expected] += 1
            if verbose:
                print(f"  [OK] {cat:18s}  {query[:60]}")
        else:
            failures.append({
                "query": query,
                "expected": expected,
                "got": cat,
                "variant_type": entry.get("variant", "standard"),
                "base_id": entry.get("base_id", ""),
                "full_result": result,
            })
            print(f"  [!!] {query[:60]}")
            print(f"       Expected: {expected}, Got: {cat}  [{entry.get('variant','standard')}]")

    rate = correct / total if total else 0
    return {
        "total": total,
        "correct": correct,
        "rate": round(rate, 4),
        "failures": failures,
        "by_category": dict(by_category),
        "correct_by_category": dict(correct_by_category),
    }


def run_consistency_test(agent, variant, dev_set, k=5, verbose=False):
    total = 0
    consistent = 0
    inconsistent = []

    for entry in dev_set:
        query = entry["query"]
        categories = []
        for _ in range(k):
            result = classify_query(agent, variant, query)
            categories.append(result.get("category", "out_of_scope"))

        total += 1
        if len(set(categories)) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {categories[0]:18s}  {query[:55]} (x{k})")
        else:
            inconsistent.append({
                "query": query,
                "expected": entry["expected"],
                "variant_type": entry.get("variant", "standard"),
                "categories": categories,
            })
            print(f"  [!!] {query[:55]:55s} -> {set(categories)}")

    rate = consistent / total if total else 0
    return {
        "total": total,
        "consistent": consistent,
        "rate": round(rate, 4),
        "inconsistent": inconsistent,
    }


def run_iteration(variant, variants_mode="standard", run_label=1, verbose=False, k_consistency=5):
    print(f"\n{'='*70}")
    print(f"  Construction Iteration — {variant} (9-class, 19BSept)")
    print(f"  Variants mode: {variants_mode}  |  Run: {run_label}")
    print(f"{'='*70}")

    print(f"\nLoading {variant}...", end=" ", flush=True)
    agent = load_agent(variant)
    print("OK")

    dev_set = load_dev_set(variants_mode)
    print(f"Development set: {len(dev_set)} queries "
          f"(mode={variants_mode}, Layer 2 follow-ups excluded)\n")

    cats = Counter(q["expected"] for q in dev_set)
    var_counts = Counter(q.get("variant", "standard") for q in dev_set)
    print(f"Category distribution:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:18s}: {n:3d}")
    print(f"\nVariant distribution: {dict(var_counts)}\n")

    print(f"--- Accuracy Test ---")
    accuracy = run_accuracy_test(agent, variant, dev_set, verbose)
    print(f"\nAccuracy: {accuracy['correct']}/{accuracy['total']} ({accuracy['rate']:.1%})")

    # Per-category accuracy
    print(f"\nPer-category accuracy:")
    for cat in sorted(cats.keys()):
        total = accuracy["by_category"].get(cat, 0)
        correct = accuracy["correct_by_category"].get(cat, 0)
        rate = correct / total if total else 0
        print(f"  {cat:18s}: {correct:2d}/{total:2d} ({rate:.0%})")

    # Per-variant accuracy (only when mode == 'all')
    if variants_mode == "all":
        print(f"\nPer-variant accuracy:")
        for vt in ["standard", "l2_typo", "l2_grammar"]:
            vqs = [q for q in dev_set if q.get("variant", "standard") == vt]
            v_fail = [f for f in accuracy["failures"] if f.get("variant_type") == vt]
            v_correct = len(vqs) - len(v_fail)
            v_rate = v_correct / len(vqs) if vqs else 0
            print(f"  {vt:12s}: {v_correct:2d}/{len(vqs):2d} ({v_rate:.0%})")

    # Consistency (LLM only)
    consistency = None
    if "llm" in variant:
        print(f"\n--- Consistency Test (K={k_consistency}) ---")
        consistency = run_consistency_test(agent, variant, dev_set, k=k_consistency, verbose=verbose)
        print(f"\nConsistency: {consistency['consistent']}/{consistency['total']} ({consistency['rate']:.1%})")

    # Summary
    print(f"\n{'='*70}")
    print(f"  Summary — {variant} | run={run_label} | variants={variants_mode}")
    print(f"{'='*70}")
    print(f"  Accuracy:    {accuracy['rate']:.1%} ({accuracy['correct']}/{accuracy['total']})")
    if consistency:
        print(f"  Consistency: {consistency['rate']:.1%} ({consistency['consistent']}/{consistency['total']})")
    if accuracy['failures']:
        print(f"  Failures:    {len(accuracy['failures'])}")

        error_types = Counter()
        for f in accuracy['failures']:
            error_types[(f['expected'], f['got'])] += 1

        print(f"\n  Error patterns (expected -> got):")
        for (exp, got), n in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"    {exp:18s} -> {got:18s}  ({n}x)")

        print(f"\n  Misclassifications (for next iteration):")
        for f in accuracy['failures']:
            vt = f.get('variant_type', 'standard')
            print(f"    [{vt:10s}] {f['expected']:18s} -> {f['got']:18s}  \"{f['query']}\"")

    # Save trajectory
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    traj_dir = os.path.join(
        STUDY_DIR, "construction",
        f"{variant}_trajectory", f"run_{run_label}"
    )
    os.makedirs(traj_dir, exist_ok=True)
    traj_path = os.path.join(traj_dir, f"iteration_{timestamp}.json")

    traj_data = {
        "timestamp": timestamp,
        "variant": variant,
        "taxonomy": "9-class",
        "study": "19BSept",
        "variants_mode": variants_mode,
        "run_label": run_label,
        "dev_set_size": len(dev_set),
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
    parser = argparse.ArgumentParser(description="Construction Protocol — 9-class taxonomy (19BSept)")
    parser.add_argument("--variant",
                        choices=["rule_based_A", "rule_based_B", "rule_based_C",
                                 "llm_A", "llm_B", "llm_C"],
                        help="Run single agent variant (default: all six)")
    parser.add_argument("--variants", choices=["standard", "all"], default="standard",
                        help="Which query variants to include during construction "
                             "(standard=replicates 19Sept; all=includes L2 typo+grammar)")
    parser.add_argument("--run", type=int, default=1,
                        help="Run label for independent construction runs (default: 1)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--k", type=int, default=5, help="K for consistency test")
    args = parser.parse_args()

    variants = [args.variant] if args.variant else [
        "rule_based_A", "rule_based_B", "rule_based_C",
        "llm_A", "llm_B", "llm_C",
    ]

    for v in variants:
        run_iteration(
            v,
            variants_mode=args.variants,
            run_label=args.run,
            verbose=args.verbose,
            k_consistency=args.k,
        )


if __name__ == "__main__":
    main()
