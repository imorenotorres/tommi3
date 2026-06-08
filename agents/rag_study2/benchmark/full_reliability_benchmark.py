#!/usr/bin/env python3
"""
Full Reliability Benchmark — Rabanser et al. (2025)

Measures all four reliability dimensions (automated metrics):

  CONSISTENCY
    C_traj: Classification consistency (K runs, same query → same category?)
    C_out:  Response consistency (K runs, full agent → same response text?)
    C_res:  Resource consistency (latency variance across K runs)

  ROBUSTNESS
    R_prompt: Accuracy degradation across difficulty tiers (1→2→3)
    R_per_cat: Per-category robustness (which categories degrade most?)

  PREDICTABILITY (automated proxy)
    P_programmatic: Fraction of queries routed to programmatic paths
    P_agreement: Classification agreement between agents (proxy for confidence)

  SAFETY (automated proxy)
    S_refusal: Does the agent correctly refuse off-topic/non-research queries?
    S_scope: Does the agent stay within scope?

Usage:
    python3 full_reliability_benchmark.py
    python3 full_reliability_benchmark.py --eval-set evaluation_set_extended.json
    python3 full_reliability_benchmark.py --agents rule_based,phase2,llm_based
"""

import os
import sys
import json
import time
import re
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
    "embedding_based": os.path.join(STUDY_DIR, "agents", "embedding_based"),
    "phase2": os.path.join(STUDY_DIR, "rag_rulebased_study", "phase2_generalised"),
    "responsible_ai3": os.path.join(STUDY_DIR, "..", "rag_study", "procedural"),
}
LABELS = {
    "rule_based": "Narrow rules",
    "phase2": "Generalised rules",
    "llm_based": "LLM-based",
    "embedding_based": "Embedding-based",
    "responsible_ai3": "Hand-crafted (months)",
}


def load_agent(variant):
    agent_dir = AGENT_PATHS.get(variant, os.path.join(STUDY_DIR, "agents", variant))
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
    elif variant == "embedding_based":
        return agent._embedding_classify(query)
    else:
        return agent._code_classify(query)


def strip_trace(response):
    """Remove decision trace HTML from response for comparison."""
    return re.sub(r'<details.*?</details>', '', response or '', flags=re.DOTALL).strip()


# ═══════════════════════════════════════════════════════════════════════════
# CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════

def measure_c_traj(agent, variant, eval_set, k=5):
    """C_traj: Classification trajectory consistency."""
    total = consistent = 0
    issues = []
    for entry in eval_set:
        cats = [classify(agent, variant, entry["query"]).get("category", "general")
                for _ in range(k)]
        total += 1
        if len(set(cats)) == 1:
            consistent += 1
        else:
            issues.append({"query": entry["query"], "expected": entry["expected"],
                           "categories": cats})
    return {
        "total": total, "consistent": consistent,
        "rate": round(consistent / total, 4) if total else 0,
        "issues": issues,
    }


def measure_c_out(agent, variant, eval_set, k=3):
    """C_out: Response outcome consistency (full agent, programmatic paths only)."""
    # Only test queries that should hit programmatic paths
    programmatic_cats = {"meta", "non_research", "off_topic", "glossary", "researcher", "project", "figure"}
    prog_queries = [e for e in eval_set if e["expected"] in programmatic_cats]

    total = consistent = 0
    issues = []
    for entry in prog_queries[:30]:  # Limit to 30 to keep runtime reasonable
        responses = []
        for _ in range(k):
            try:
                r = agent.chat(entry["query"])
                responses.append(strip_trace(r))
            except Exception as e:
                responses.append(f"ERROR: {e}")

        total += 1
        if len(set(responses)) == 1:
            consistent += 1
        else:
            issues.append({
                "query": entry["query"],
                "expected": entry["expected"],
                "n_unique": len(set(responses)),
            })

    return {
        "total": total, "consistent": consistent,
        "rate": round(consistent / total, 4) if total else 0,
        "issues": issues,
    }


def measure_c_res(agent, variant, eval_set, k=3):
    """C_res: Resource consistency (latency variance)."""
    sample = eval_set[:20]  # Sample for efficiency
    all_times = []
    per_query_cv = []

    for entry in sample:
        times = []
        for _ in range(k):
            start = time.time()
            classify(agent, variant, entry["query"])
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            all_times.append(elapsed)

        mean = sum(times) / len(times) if times else 0
        if mean > 0:
            std = (sum((t - mean) ** 2 for t in times) / len(times)) ** 0.5
            cv = std / mean
        else:
            cv = 0
        per_query_cv.append(cv)

    avg_latency = sum(all_times) / len(all_times) if all_times else 0
    avg_cv = sum(per_query_cv) / len(per_query_cv) if per_query_cv else 0

    return {
        "avg_latency_ms": round(avg_latency, 1),
        "avg_cv": round(avg_cv, 4),
        "consistency": round(1 - avg_cv, 4),  # Higher = more consistent
    }


# ═══════════════════════════════════════════════════════════════════════════
# ROBUSTNESS
# ═══════════════════════════════════════════════════════════════════════════

def measure_robustness(agent, variant, eval_set):
    """R_prompt: Accuracy by difficulty tier — measures degradation."""
    by_tier = {}
    by_category = {}
    total_correct = 0
    total = 0

    for entry in eval_set:
        tier = entry.get("tier", 1)
        cat_expected = entry["expected"]
        result = classify(agent, variant, entry["query"])
        cat_got = result.get("category", "general")
        correct = (cat_got == cat_expected)

        total += 1
        if correct:
            total_correct += 1

        if tier not in by_tier:
            by_tier[tier] = {"total": 0, "correct": 0}
        by_tier[tier]["total"] += 1
        if correct:
            by_tier[tier]["correct"] += 1

        if cat_expected not in by_category:
            by_category[cat_expected] = {"total": 0, "correct": 0,
                                         "by_tier": {1: {"t": 0, "c": 0},
                                                     2: {"t": 0, "c": 0},
                                                     3: {"t": 0, "c": 0}}}
        by_category[cat_expected]["total"] += 1
        if correct:
            by_category[cat_expected]["correct"] += 1
        if tier in by_category[cat_expected]["by_tier"]:
            by_category[cat_expected]["by_tier"][tier]["t"] += 1
            if correct:
                by_category[cat_expected]["by_tier"][tier]["c"] += 1

    # Compute rates
    for tier in by_tier:
        s = by_tier[tier]
        s["rate"] = round(s["correct"] / s["total"], 4) if s["total"] else 0

    for cat in by_category:
        s = by_category[cat]
        s["rate"] = round(s["correct"] / s["total"], 4) if s["total"] else 0
        for tier in s["by_tier"]:
            t = s["by_tier"][tier]
            t["rate"] = round(t["c"] / t["t"], 4) if t["t"] else 0

    # Degradation: tier1 accuracy - tier3 accuracy
    t1 = by_tier.get(1, {}).get("rate", 0)
    t2 = by_tier.get(2, {}).get("rate", 0)
    t3 = by_tier.get(3, {}).get("rate", 0)
    degradation = round(t1 - t3, 4) if t1 and t3 else 0

    return {
        "overall_accuracy": round(total_correct / total, 4) if total else 0,
        "by_tier": by_tier,
        "degradation_t1_t3": degradation,
        "by_category": by_category,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PREDICTABILITY (automated proxy)
# ═══════════════════════════════════════════════════════════════════════════

def measure_predictability(agent, variant, eval_set):
    """Proxy for predictability: programmatic path fraction + accuracy by path type."""
    programmatic_cats = {"meta", "non_research", "off_topic", "figure", "project", "researcher", "glossary"}
    llm_cats = {"topic_search", "papers", "gap", "general", "followup"}

    prog_total = prog_correct = 0
    llm_total = llm_correct = 0

    for entry in eval_set:
        result = classify(agent, variant, entry["query"])
        cat = result.get("category", "general")
        correct = (cat == entry["expected"])

        if cat in programmatic_cats:
            prog_total += 1
            if correct:
                prog_correct += 1
        else:
            llm_total += 1
            if correct:
                llm_correct += 1

    return {
        "programmatic_fraction": round(prog_total / (prog_total + llm_total), 4) if (prog_total + llm_total) else 0,
        "programmatic_accuracy": round(prog_correct / prog_total, 4) if prog_total else 0,
        "llm_path_accuracy": round(llm_correct / llm_total, 4) if llm_total else 0,
        "programmatic_n": prog_total,
        "llm_path_n": llm_total,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY (automated proxy)
# ═══════════════════════════════════════════════════════════════════════════

def measure_safety(agent, variant, eval_set):
    """Automated safety proxy: refusal accuracy for off-topic and non-research."""
    refusal_cats = {"off_topic", "non_research"}
    scope_queries = [e for e in eval_set if e["expected"] in refusal_cats]

    correctly_refused = 0
    total = len(scope_queries)
    failures = []

    for entry in scope_queries:
        result = classify(agent, variant, entry["query"])
        cat = result.get("category", "general")
        if cat in refusal_cats:
            correctly_refused += 1
        else:
            failures.append({
                "query": entry["query"], "expected": entry["expected"],
                "got": cat,
            })

    return {
        "total_refusal_queries": total,
        "correctly_refused": correctly_refused,
        "refusal_rate": round(correctly_refused / total, 4) if total else 0,
        "failures": failures,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run_benchmark(agent_ids, eval_filename, k_traj=5, k_out=3, k_res=3, verbose=False):
    t_start = time.time()
    eval_set = load_eval_set(eval_filename)
    print(f"Evaluation set: {len(eval_set)} queries ({eval_filename})")
    tiers = set(e.get("tier", 1) for e in eval_set)
    print(f"Tiers: {sorted(tiers)}, queries per tier: {', '.join(str(sum(1 for e in eval_set if e.get('tier',1)==t)) for t in sorted(tiers))}")

    agents = {}
    for vid in agent_ids:
        label = LABELS.get(vid, vid)
        print(f"\nLoading {label}...", end=" ", flush=True)
        agents[vid] = load_agent(vid)
        print("OK")

    results = {}

    for vid in agent_ids:
        agent = agents[vid]
        label = LABELS.get(vid, vid)
        results[vid] = {}

        print(f"\n{'='*70}")
        print(f"  {label}")
        print(f"{'='*70}")

        # Robustness (accuracy + per-tier)
        print(f"\n  Measuring robustness (accuracy by tier)...")
        results[vid]["robustness"] = measure_robustness(agent, vid, eval_set)

        # Consistency — C_traj
        print(f"  Measuring C_traj (K={k_traj})...")
        results[vid]["c_traj"] = measure_c_traj(agent, vid, eval_set, k=k_traj)

        # Consistency — C_out (response consistency)
        print(f"  Measuring C_out (K={k_out}, programmatic paths)...")
        results[vid]["c_out"] = measure_c_out(agent, vid, eval_set, k=k_out)

        # Consistency — C_res (latency)
        print(f"  Measuring C_res (K={k_res}, latency variance)...")
        results[vid]["c_res"] = measure_c_res(agent, vid, eval_set, k=k_res)

        # Predictability
        print(f"  Measuring predictability proxy...")
        results[vid]["predictability"] = measure_predictability(agent, vid, eval_set)

        # Safety
        print(f"  Measuring safety proxy...")
        results[vid]["safety"] = measure_safety(agent, vid, eval_set)

    elapsed = time.time() - t_start

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════

    print(f"\n{'='*80}")
    print(f"  FULL RELIABILITY BENCHMARK — Rabanser et al. (2025)")
    print(f"  {len(eval_set)} queries, {len(agent_ids)} agents, {elapsed:.0f}s")
    print(f"{'='*80}")

    # Header
    w = 18
    header = f"  {'Metric':<40}"
    for vid in agent_ids:
        header += f" {LABELS.get(vid, vid):>{w}}"
    print(header)
    print(f"  {'-'*(40 + (w+1) * len(agent_ids))}")

    # CONSISTENCY
    print(f"  {'CONSISTENCY':}")
    row = f"    {'C_traj (classification, K=' + str(k_traj) + ')':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['c_traj']['rate']:>{w}.1%}"
    print(row)

    row = f"    {'C_out (response, K=' + str(k_out) + ')':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['c_out']['rate']:>{w}.1%}"
    print(row)

    row = f"    {'C_res (latency CV)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['c_res']['avg_cv']:>{w}.3f}"
    print(row)

    row = f"    {'Avg latency (ms)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['c_res']['avg_latency_ms']:>{w}.0f}"
    print(row)

    # ROBUSTNESS
    print(f"  {'ROBUSTNESS':}")
    row = f"    {'Overall accuracy':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['robustness']['overall_accuracy']:>{w}.1%}"
    print(row)

    for tier in sorted(tiers):
        row = f"    {'Tier ' + str(tier) + ' accuracy':<38}"
        for vid in agent_ids:
            t = results[vid]["robustness"]["by_tier"].get(tier, {})
            rate = t.get("rate", 0)
            n = t.get("total", 0)
            row += f" {rate:>{w-4}.1%} ({n:>2})"
        print(row)

    row = f"    {'Degradation (T1→T3)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['robustness']['degradation_t1_t3']:>{w}.1%}"
    print(row)

    # PREDICTABILITY
    print(f"  {'PREDICTABILITY':}")
    row = f"    {'Programmatic path fraction':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['predictability']['programmatic_fraction']:>{w}.1%}"
    print(row)

    row = f"    {'Programmatic path accuracy':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['predictability']['programmatic_accuracy']:>{w}.1%}"
    print(row)

    row = f"    {'LLM path accuracy':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['predictability']['llm_path_accuracy']:>{w}.1%}"
    print(row)

    # SAFETY
    print(f"  {'SAFETY':}")
    row = f"    {'Refusal accuracy (off-topic + non-res)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['safety']['refusal_rate']:>{w}.1%}"
    print(row)

    # RABANSER AGGREGATES
    print(f"\n  {'RABANSER AGGREGATE SCORES':}")
    print(f"  {'-'*(40 + (w+1) * len(agent_ids))}")

    for vid in agent_ids:
        r = results[vid]
        c_traj = r["c_traj"]["rate"]
        c_out = r["c_out"]["rate"]
        c_res = r["c_res"]["consistency"]
        r_con = round((c_traj + c_out + c_res) / 3, 4)

        r_overall = r["robustness"]["overall_accuracy"]
        r_degrade = 1 - abs(r["robustness"]["degradation_t1_t3"])
        r_rob = round((r_overall + r_degrade) / 2, 4)

        p_prog_frac = r["predictability"]["programmatic_fraction"]
        p_prog_acc = r["predictability"]["programmatic_accuracy"]
        r_pred = round((p_prog_frac + p_prog_acc) / 2, 4)

        r_saf = r["safety"]["refusal_rate"]

        results[vid]["rabanser"] = {
            "R_Con": r_con, "R_Rob": r_rob, "R_Pred": r_pred, "R_Saf": r_saf,
            "components": {
                "C_traj": c_traj, "C_out": c_out, "C_res": c_res,
                "accuracy": r_overall, "degradation": r["robustness"]["degradation_t1_t3"],
            },
        }

    row = f"    {'R_Con (Consistency)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['rabanser']['R_Con']:>{w}.3f}"
    print(row)

    row = f"    {'R_Rob (Robustness)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['rabanser']['R_Rob']:>{w}.3f}"
    print(row)

    row = f"    {'R_Pred (Predictability)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['rabanser']['R_Pred']:>{w}.3f}"
    print(row)

    row = f"    {'R_Saf (Safety)':<38}"
    for vid in agent_ids:
        row += f" {results[vid]['rabanser']['R_Saf']:>{w}.3f}"
    print(row)

    print(f"\n  Time elapsed: {elapsed:.1f}s")
    print(f"{'='*80}")

    # Per-category breakdown
    print(f"\n  PER-CATEGORY ACCURACY (by tier)")
    all_cats = sorted(set(e["expected"] for e in eval_set))
    for cat in all_cats:
        print(f"\n  {cat}:")
        header_row = f"    {'Tier':<8}"
        for vid in agent_ids:
            header_row += f" {LABELS.get(vid, vid)[:14]:>14}"
        print(header_row)
        for tier in sorted(tiers):
            row = f"    {tier:<8}"
            for vid in agent_ids:
                bt = results[vid]["robustness"]["by_category"].get(cat, {}).get("by_tier", {}).get(tier, {})
                rate = bt.get("rate", 0)
                n = bt.get("t", 0)
                if n > 0:
                    row += f" {rate:>10.0%} ({n:>2})"
                else:
                    row += f" {'—':>14}"
            print(row)

    # Save results
    out_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "eval_set": eval_filename,
        "eval_set_size": len(eval_set),
        "k_traj": k_traj, "k_out": k_out, "k_res": k_res,
        "agents": agent_ids,
    }
    for vid in agent_ids:
        r = results[vid]
        out_data[vid] = {
            "c_traj": {k: v for k, v in r["c_traj"].items() if k != "issues"},
            "c_traj_issues": r["c_traj"]["issues"],
            "c_out": {k: v for k, v in r["c_out"].items() if k != "issues"},
            "c_out_issues": r["c_out"]["issues"],
            "c_res": r["c_res"],
            "robustness": {k: v for k, v in r["robustness"].items() if k != "by_category"},
            "robustness_by_category": {cat: {k: v for k, v in s.items()}
                                       for cat, s in r["robustness"]["by_category"].items()},
            "predictability": r["predictability"],
            "safety": {k: v for k, v in r["safety"].items() if k != "failures"},
            "safety_failures": r["safety"]["failures"],
            "rabanser": r["rabanser"],
        }

    results_dir = os.path.join(STUDY_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"full_reliability_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Reliability Benchmark (Rabanser et al. 2025)")
    parser.add_argument("--eval-set", type=str, default="evaluation_set_extended.json")
    parser.add_argument("--agents", type=str, default="rule_based,phase2,llm_based")
    parser.add_argument("--k-traj", type=int, default=5, help="K for C_traj")
    parser.add_argument("--k-out", type=int, default=3, help="K for C_out")
    parser.add_argument("--k-res", type=int, default=3, help="K for C_res")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    agent_ids = [a.strip() for a in args.agents.split(",")]
    run_benchmark(agent_ids, args.eval_set,
                  k_traj=args.k_traj, k_out=args.k_out, k_res=args.k_res,
                  verbose=args.verbose)
