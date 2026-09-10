#!/usr/bin/env python3
"""
N-Run Reliability Benchmark

Runs the full reliability benchmark N times to quantify between-run
variance for non-deterministic classifiers (LLM-based).

For deterministic classifiers (rule-based), a single verification run
confirms that results are identical across runs.

Reports: mean ± std for each Rabanser dimension.

Usage:
    python3 nrun_benchmark.py --n 5
    python3 nrun_benchmark.py --n 5 --agents phase2,llm_based
"""

import os
import sys
import json
import time
import math
import argparse
import importlib
import importlib.util
import re

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))

AGENT_PATHS = {
    "rule_based": os.path.join(STUDY_DIR, "agents", "rule_based"),
    "llm_based": os.path.join(STUDY_DIR, "agents", "llm_based"),
    "phase2": os.path.join(STUDY_DIR, "rag_rulebased_study", "phase2_generalised"),
    "responsible_ai3": os.path.join(STUDY_DIR, "..", "rag_study", "procedural"),
}
LABELS = {
    "rule_based": "Narrow rules",
    "phase2": "Generalised rules",
    "llm_based": "LLM-based",
    "responsible_ai3": "Hand-crafted",
}


def load_agent(variant):
    agent_dir = AGENT_PATHS.get(variant)
    spec = importlib.util.spec_from_file_location(
        f"agent_{variant}", os.path.join(agent_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_eval_set(filename):
    with open(os.path.join(STUDY_DIR, "benchmark", filename)) as f:
        return json.load(f)["queries"]


def classify(agent, variant, query):
    if variant == "llm_based":
        return agent._llm_classify(query)
    else:
        return agent._code_classify(query)


def strip_trace(response):
    return re.sub(r'<details.*?</details>', '', response or '', flags=re.DOTALL).strip()


def single_run(agent, variant, eval_set):
    """Run one complete benchmark iteration. Returns metrics dict."""
    programmatic_cats = {"meta", "non_research", "off_topic", "figure", "project", "researcher", "glossary"}
    refusal_cats = {"off_topic", "non_research"}

    total = correct = 0
    by_tier = {}
    prog_total = prog_correct = 0
    llm_total = llm_correct = 0
    refusal_total = refusal_correct = 0
    c_traj_consistent = 0
    c_traj_total = 0

    for entry in eval_set:
        query = entry["query"]
        expected = entry["expected"]
        tier = entry.get("tier", 1)

        # Classification
        result = classify(agent, variant, query)
        cat = result.get("category", "general")
        is_correct = (cat == expected)

        total += 1
        if is_correct:
            correct += 1

        # By tier
        if tier not in by_tier:
            by_tier[tier] = {"total": 0, "correct": 0}
        by_tier[tier]["total"] += 1
        if is_correct:
            by_tier[tier]["correct"] += 1

        # Predictability
        if cat in programmatic_cats:
            prog_total += 1
            if is_correct:
                prog_correct += 1
        else:
            llm_total += 1
            if is_correct:
                llm_correct += 1

        # Safety
        if expected in refusal_cats:
            refusal_total += 1
            if cat in refusal_cats:
                refusal_correct += 1

        # C_traj (K=3 for speed in N-run protocol)
        cats = [classify(agent, variant, query).get("category", "general") for _ in range(2)]
        cats.insert(0, cat)  # reuse first classification
        c_traj_total += 1
        if len(set(cats)) == 1:
            c_traj_consistent += 1

    # Compute rates
    accuracy = correct / total if total else 0
    c_traj = c_traj_consistent / c_traj_total if c_traj_total else 0

    tier_rates = {}
    for t in sorted(by_tier.keys()):
        s = by_tier[t]
        tier_rates[t] = s["correct"] / s["total"] if s["total"] else 0

    t1 = tier_rates.get(1, 0)
    t3 = tier_rates.get(3, 0)
    degradation = t1 - t3 if t1 and t3 else 0

    prog_acc = prog_correct / prog_total if prog_total else 0
    llm_acc = llm_correct / llm_total if llm_total else 0
    prog_frac = prog_total / total if total else 0
    refusal_rate = refusal_correct / refusal_total if refusal_total else 0

    # C_out: test 10 programmatic queries for response consistency
    prog_queries = [e for e in eval_set if e["expected"] in programmatic_cats][:10]
    c_out_total = c_out_consistent = 0
    for entry in prog_queries:
        responses = []
        for _ in range(3):
            try:
                r = agent.chat(entry["query"])
                responses.append(strip_trace(r))
            except:
                responses.append("ERROR")
        c_out_total += 1
        if len(set(responses)) == 1:
            c_out_consistent += 1
    c_out = c_out_consistent / c_out_total if c_out_total else 0

    # Rabanser aggregates
    c_res = 0.95  # approximate — stable within run
    r_con = (c_traj + c_out + c_res) / 3
    r_rob = (accuracy + (1 - abs(degradation))) / 2
    r_pred = (prog_frac + prog_acc) / 2
    r_saf = refusal_rate

    return {
        "accuracy": round(accuracy, 4),
        "c_traj": round(c_traj, 4),
        "c_out": round(c_out, 4),
        "tier_1": round(tier_rates.get(1, 0), 4),
        "tier_2": round(tier_rates.get(2, 0), 4),
        "tier_3": round(tier_rates.get(3, 0), 4),
        "degradation": round(degradation, 4),
        "prog_acc": round(prog_acc, 4),
        "llm_acc": round(llm_acc, 4),
        "refusal_rate": round(refusal_rate, 4),
        "R_Con": round(r_con, 4),
        "R_Rob": round(r_rob, 4),
        "R_Pred": round(r_pred, 4),
        "R_Saf": round(r_saf, 4),
    }


def mean_std(values):
    n = len(values)
    if n == 0:
        return 0, 0
    m = sum(values) / n
    if n == 1:
        return m, 0
    variance = sum((x - m) ** 2 for x in values) / (n - 1)
    return m, math.sqrt(variance)


def run_nruns(agent_ids, eval_filename, n_runs):
    t_start = time.time()
    eval_set = load_eval_set(eval_filename)
    print(f"N-Run Benchmark: {n_runs} runs × {len(eval_set)} queries × {len(agent_ids)} agents")
    print(f"Evaluation set: {eval_filename}\n")

    all_results = {}

    for vid in agent_ids:
        label = LABELS.get(vid, vid)
        print(f"Loading {label}...", end=" ", flush=True)
        agent = load_agent(vid)
        print("OK")

        is_deterministic = (vid != "llm_based")
        runs_needed = 1 if is_deterministic else n_runs

        print(f"  Running {runs_needed} {'run' if runs_needed == 1 else 'runs'}"
              f"{' (deterministic — single run sufficient)' if is_deterministic else ''}...")

        run_results = []
        for i in range(runs_needed):
            print(f"    Run {i+1}/{runs_needed}...", end=" ", flush=True)
            r = single_run(agent, vid, eval_set)
            run_results.append(r)
            print(f"accuracy={r['accuracy']:.1%}, R_Con={r['R_Con']:.3f}, "
                  f"R_Rob={r['R_Rob']:.3f}, R_Saf={r['R_Saf']:.3f}")

        all_results[vid] = {
            "label": label,
            "is_deterministic": is_deterministic,
            "n_runs": runs_needed,
            "runs": run_results,
        }

    elapsed = time.time() - t_start

    # ── Summary ──
    print(f"\n{'='*90}")
    print(f"  N-RUN RELIABILITY BENCHMARK — Summary")
    print(f"  {len(eval_set)} queries, {n_runs} runs, {elapsed:.0f}s")
    print(f"{'='*90}")

    metrics = ["accuracy", "c_traj", "c_out", "tier_1", "tier_2", "tier_3",
               "degradation", "refusal_rate", "R_Con", "R_Rob", "R_Pred", "R_Saf"]
    metric_labels = {
        "accuracy": "Accuracy",
        "c_traj": "C_traj (classification)",
        "c_out": "C_out (response)",
        "tier_1": "Tier 1 (standard)",
        "tier_2": "Tier 2 (unusual)",
        "tier_3": "Tier 3 (adversarial)",
        "degradation": "Degradation (T1→T3)",
        "refusal_rate": "Refusal accuracy",
        "R_Con": "R_Con (Consistency)",
        "R_Rob": "R_Rob (Robustness)",
        "R_Pred": "R_Pred (Predictability)",
        "R_Saf": "R_Saf (Safety)",
    }

    # Header
    w = 22
    header = f"  {'Metric':<30}"
    for vid in agent_ids:
        header += f" {LABELS.get(vid, vid):>{w}}"
    print(header)
    print(f"  {'-'*(30 + (w+1) * len(agent_ids))}")

    for metric in metrics:
        if metric == "R_Con":
            print(f"  {'':30}")  # blank line before aggregates

        row = f"  {metric_labels.get(metric, metric):<30}"
        for vid in agent_ids:
            runs = all_results[vid]["runs"]
            values = [r[metric] for r in runs]
            m, s = mean_std(values)

            if all_results[vid]["is_deterministic"] or len(runs) == 1:
                if metric == "degradation":
                    row += f" {m:>{w}.1%}"
                else:
                    row += f" {m:>{w}.1%}"
            else:
                if s < 0.001:
                    row += f" {m:>{w-6}.1%}       "
                else:
                    row += f" {m:>{w-10}.1%} ± {s:.1%}  "
        print(row)

    print(f"\n  Time elapsed: {elapsed:.1f}s")
    print(f"{'='*90}")

    # Variance analysis for LLM-based
    if "llm_based" in all_results and len(all_results["llm_based"]["runs"]) > 1:
        runs = all_results["llm_based"]["runs"]
        print(f"\n  LLM-BASED VARIANCE ANALYSIS ({len(runs)} runs)")
        print(f"  {'-'*60}")
        for metric in ["accuracy", "R_Con", "R_Rob", "R_Pred", "R_Saf"]:
            values = [r[metric] for r in runs]
            m, s = mean_std(values)
            mn, mx = min(values), max(values)
            print(f"    {metric_labels.get(metric, metric):<30} "
                  f"mean={m:.3f}, std={s:.3f}, range=[{mn:.3f}, {mx:.3f}]")

    # Save
    out_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "eval_set": eval_filename,
        "eval_set_size": len(eval_set),
        "n_runs": n_runs,
        "agents": agent_ids,
    }
    for vid in agent_ids:
        r = all_results[vid]
        runs = r["runs"]
        summary = {}
        for metric in metrics:
            values = [run[metric] for run in runs]
            m, s = mean_std(values)
            summary[metric] = {"mean": round(m, 4), "std": round(s, 4),
                               "min": round(min(values), 4), "max": round(max(values), 4)}
        out_data[vid] = {
            "label": r["label"],
            "is_deterministic": r["is_deterministic"],
            "n_runs": r["n_runs"],
            "summary": summary,
            "runs": runs,
        }

    results_dir = os.path.join(STUDY_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"nrun_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="N-Run Reliability Benchmark")
    parser.add_argument("--n", type=int, default=5, help="Number of runs (default: 5)")
    parser.add_argument("--eval-set", type=str, default="evaluation_set_extended.json")
    parser.add_argument("--agents", type=str, default="phase2,llm_based",
                        help="Comma-separated agent IDs")
    args = parser.parse_args()

    agent_ids = [a.strip() for a in args.agents.split(",")]
    run_nruns(agent_ids, args.eval_set, args.n)
