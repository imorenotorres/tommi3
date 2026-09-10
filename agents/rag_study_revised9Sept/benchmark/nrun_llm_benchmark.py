#!/usr/bin/env python3
"""
N-run benchmark for the LLM-based classifier.

Runs the full robustness/predictability/safety/consistency measurements
N times (default 5) and computes mean ± std for each metric.
Rule-based agents are deterministic — run once only.

Usage:
    python3 nrun_llm_benchmark.py
    python3 nrun_llm_benchmark.py --n 5 --eval-set evaluation_set_extended_revised.json
"""

import os
import sys
import json
import time
import math
import argparse

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))

from full_reliability_benchmark import (
    load_agent, load_eval_set, classify,
    measure_c_traj, measure_robustness, measure_predictability, measure_safety,
)


def mean_std(values):
    n = len(values)
    if n == 0:
        return 0, 0
    m = sum(values) / n
    if n == 1:
        return m, 0
    s = math.sqrt(sum((x - m) ** 2 for x in values) / (n - 1))
    return m, s


def run_nruns(eval_filename, n_runs=5, k_traj=5):
    eval_set = load_eval_set(eval_filename)
    N = len(eval_set)
    print(f"Evaluation set: {N} queries ({eval_filename})")
    print(f"N={n_runs} runs, K_traj={k_traj}")

    # ── Rule-based agents (deterministic — 1 run each) ──
    rule_agents = ["auto_rule_based", "production"]
    rule_results = {}

    for vid in rule_agents:
        print(f"\nLoading {vid}...", end=" ", flush=True)
        agent = load_agent(vid)
        print("OK")

        rob = measure_robustness(agent, vid, eval_set)
        pred = measure_predictability(agent, vid, eval_set)
        saf = measure_safety(agent, vid, eval_set)

        # R_Con = 1.0 by construction
        r_con = 1.0
        r_rob = round((rob["overall_accuracy"] + (1 - abs(rob["degradation_t1_t3"]))) / 2, 4)
        r_pred = round((pred["programmatic_fraction"] + pred["programmatic_accuracy"]) / 2, 4)
        r_saf = saf["refusal_rate"]

        rule_results[vid] = {
            "robustness": rob,
            "predictability": pred,
            "safety": saf,
            "rabanser": {"R_Con": r_con, "R_Rob": r_rob, "R_Pred": r_pred, "R_Saf": r_saf},
        }
        print(f"  {vid}: acc={rob['overall_accuracy']:.1%}, R_Rob={r_rob:.3f}, R_Pred={r_pred:.3f}, R_Saf={r_saf:.3f}")

    # ── LLM-based agent (N runs) ──
    print(f"\nLoading llm_based...", end=" ", flush=True)
    agent_llm = load_agent("llm_based")
    print("OK")

    all_runs = []
    for run_i in range(n_runs):
        t0 = time.time()
        print(f"\n{'='*60}")
        print(f"  LLM-based — Run {run_i + 1}/{n_runs}")
        print(f"{'='*60}")

        # C_traj
        print(f"  C_traj (K={k_traj})...")
        c_traj = measure_c_traj(agent_llm, "llm_based", eval_set, k=k_traj)

        # Robustness
        print(f"  Robustness...")
        rob = measure_robustness(agent_llm, "llm_based", eval_set)

        # Predictability
        print(f"  Predictability...")
        pred = measure_predictability(agent_llm, "llm_based", eval_set)

        # Safety
        print(f"  Safety...")
        saf = measure_safety(agent_llm, "llm_based", eval_set)

        # Rabanser aggregates
        r_con = round((c_traj["rate"] + 1.0 + 1.0) / 3, 4)  # C_out and C_res not re-measured each run
        r_rob = round((rob["overall_accuracy"] + (1 - abs(rob["degradation_t1_t3"]))) / 2, 4)
        r_pred = round((pred["programmatic_fraction"] + pred["programmatic_accuracy"]) / 2, 4)
        r_saf = saf["refusal_rate"]

        elapsed = time.time() - t0

        run_data = {
            "run": run_i + 1,
            "elapsed_s": round(elapsed, 1),
            "c_traj": c_traj["rate"],
            "accuracy": rob["overall_accuracy"],
            "tier1": rob["by_tier"].get(1, {}).get("rate", 0),
            "tier2": rob["by_tier"].get(2, {}).get("rate", 0),
            "tier3": rob["by_tier"].get(3, {}).get("rate", 0),
            "degradation": rob["degradation_t1_t3"],
            "prog_fraction": pred["programmatic_fraction"],
            "prog_accuracy": pred["programmatic_accuracy"],
            "llm_path_accuracy": pred["llm_path_accuracy"],
            "refusal_rate": saf["refusal_rate"],
            "R_Con": r_con,
            "R_Rob": r_rob,
            "R_Pred": r_pred,
            "R_Saf": r_saf,
            "robustness_by_category": rob.get("by_category", {}),
        }
        all_runs.append(run_data)

        print(f"  Run {run_i+1}: acc={rob['overall_accuracy']:.1%}, "
              f"T1={run_data['tier1']:.1%}, T2={run_data['tier2']:.1%}, T3={run_data['tier3']:.1%}, "
              f"C_traj={c_traj['rate']:.1%}, refusal={saf['refusal_rate']:.1%} ({elapsed:.0f}s)")

    # ── Compute statistics ──
    print(f"\n{'='*80}")
    print(f"  N-RUN SUMMARY (LLM-based, N={n_runs})")
    print(f"{'='*80}")

    metrics = [
        ("C_traj (classification consistency)", "c_traj"),
        ("Overall accuracy", "accuracy"),
        ("Tier 1 accuracy", "tier1"),
        ("Tier 2 accuracy", "tier2"),
        ("Tier 3 accuracy", "tier3"),
        ("Degradation (T1→T3)", "degradation"),
        ("Programmatic path fraction", "prog_fraction"),
        ("Programmatic path accuracy", "prog_accuracy"),
        ("LLM path accuracy", "llm_path_accuracy"),
        ("Refusal rate (safety)", "refusal_rate"),
        ("R_Con (Consistency)", "R_Con"),
        ("R_Rob (Robustness)", "R_Rob"),
        ("R_Pred (Predictability)", "R_Pred"),
        ("R_Saf (Safety)", "R_Saf"),
    ]

    print(f"\n  {'Metric':<40}  {'Mean':>8}  {'Std':>8}  {'Min':>8}  {'Max':>8}")
    print(f"  {'-'*78}")

    stats = {}
    for label, key in metrics:
        values = [r[key] for r in all_runs]
        m, s = mean_std(values)
        mn, mx = min(values), max(values)
        stats[key] = {"mean": m, "std": s, "min": mn, "max": mx, "values": values}
        print(f"  {label:<40}  {m:>8.4f}  {s:>8.4f}  {mn:>8.4f}  {mx:>8.4f}")

    # ── Per-category per-tier across runs ──
    print(f"\n  PER-CATEGORY ACCURACY (LLM-based, mean ± std over {n_runs} runs)")
    all_cats = sorted(set(e["expected"] for e in eval_set))
    cat_stats = {}
    for cat in all_cats:
        cat_stats[cat] = {}
        for tier in [1, 2, 3]:
            values = []
            for r in all_runs:
                bt = r["robustness_by_category"].get(cat, {}).get("by_tier", {}).get(tier, {})
                rate = bt.get("rate", None)
                if rate is not None and bt.get("t", 0) > 0:
                    values.append(rate)
            if values:
                m, s = mean_std(values)
                n_queries = all_runs[0]["robustness_by_category"].get(cat, {}).get("by_tier", {}).get(tier, {}).get("t", 0)
                cat_stats[cat][tier] = {"mean": m, "std": s, "n": n_queries}

    print(f"\n  {'Category':<15}  {'T1 (mean±std)':>18}  {'T2 (mean±std)':>18}  {'T3 (mean±std)':>18}")
    print(f"  {'-'*73}")
    for cat in all_cats:
        row = f"  {cat:<15}"
        for tier in [1, 2, 3]:
            cs = cat_stats[cat].get(tier)
            if cs and cs["n"] > 0:
                row += f"  {cs['mean']:>6.0%}±{cs['std']:>4.0%} ({cs['n']:>2})"
            else:
                row += f"  {'—':>18}"
        print(row)

    # ── Comparison table (all agents) ──
    print(f"\n{'='*80}")
    print(f"  FULL COMPARISON TABLE")
    print(f"{'='*80}")

    print(f"\n  {'Metric':<40}  {'Production':>12}  {'Auto R-B':>12}  {'LLM (N={n_runs})':>18}")
    print(f"  {'-'*86}")

    def fmt_rule(vid, key):
        r = rule_results[vid]
        if key == "accuracy": return f"{r['robustness']['overall_accuracy']:.1%}"
        if key == "tier1": return f"{r['robustness']['by_tier'].get(1,{}).get('rate',0):.1%}"
        if key == "tier2": return f"{r['robustness']['by_tier'].get(2,{}).get('rate',0):.1%}"
        if key == "tier3": return f"{r['robustness']['by_tier'].get(3,{}).get('rate',0):.1%}"
        if key == "degradation": return f"{r['robustness']['degradation_t1_t3']:.1%}"
        if key == "c_traj": return "100.0%"
        if key == "refusal_rate": return f"{r['safety']['refusal_rate']:.1%}"
        if key == "prog_fraction": return f"{r['predictability']['programmatic_fraction']:.1%}"
        if key == "prog_accuracy": return f"{r['predictability']['programmatic_accuracy']:.1%}"
        if key == "llm_path_accuracy": return f"{r['predictability']['llm_path_accuracy']:.1%}"
        if key.startswith("R_"): return f"{r['rabanser'][key]:.3f}"
        return "?"

    def fmt_llm(key):
        s = stats[key]
        return f"{s['mean']:.3f} ± {s['std']:.3f}"

    for label, key in metrics:
        prod = fmt_rule("production", key)
        arb = fmt_rule("auto_rule_based", key)
        llm = fmt_llm(key)
        print(f"  {label:<40}  {prod:>12}  {arb:>12}  {llm:>18}")

    # ── Save results ──
    out_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "eval_set": eval_filename,
        "eval_set_size": N,
        "n_runs": n_runs,
        "k_traj": k_traj,
        "rule_based_results": {
            vid: {
                "accuracy": rule_results[vid]["robustness"]["overall_accuracy"],
                "by_tier": rule_results[vid]["robustness"]["by_tier"],
                "degradation": rule_results[vid]["robustness"]["degradation_t1_t3"],
                "predictability": rule_results[vid]["predictability"],
                "safety": {k: v for k, v in rule_results[vid]["safety"].items() if k != "failures"},
                "rabanser": rule_results[vid]["rabanser"],
                "robustness_by_category": rule_results[vid]["robustness"].get("by_category", {}),
            }
            for vid in rule_agents
        },
        "llm_runs": all_runs,
        "llm_stats": {key: {"mean": s["mean"], "std": s["std"], "min": s["min"], "max": s["max"]}
                      for key, s in stats.items()},
        "llm_cat_stats": cat_stats,
    }

    results_dir = os.path.join(STUDY_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(results_dir, f"nrun_llm_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="N-run LLM benchmark")
    parser.add_argument("--eval-set", type=str, default="evaluation_set_extended_revised.json")
    parser.add_argument("--n", type=int, default=5, help="Number of LLM runs")
    parser.add_argument("--k-traj", type=int, default=5, help="K for C_traj consistency")
    args = parser.parse_args()

    run_nruns(args.eval_set, n_runs=args.n, k_traj=args.k_traj)
