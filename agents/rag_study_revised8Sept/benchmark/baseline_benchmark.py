#!/usr/bin/env python3
"""
Baseline (Vanilla RAG) Reliability Benchmark

Measures response-level metrics for the baseline agent that has no
classification stage. Compares against classified agents on:
  - Response consistency (C_out, K runs)
  - Refusal behaviour (does it refuse off-topic/non-research queries?)
  - Response length and latency

Usage:
    python3 baseline_benchmark.py
"""

import os
import sys
import json
import time
import re
import importlib
import importlib.util

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", ".env"))

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(STUDY_DIR, "..", "..", "web"))


def load_agent(path):
    spec = importlib.util.spec_from_file_location("agent", os.path.join(path, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def load_eval_set(filename):
    with open(os.path.join(STUDY_DIR, "benchmark", filename)) as f:
        return json.load(f)["queries"]


def strip_trace(text):
    return re.sub(r'<details.*?</details>', '', text or '', flags=re.DOTALL).strip()


def is_refusal(response):
    """Check if the response is a refusal."""
    refusal_phrases = [
        "outside my scope", "outside the scope", "cannot perform",
        "cannot help with", "not within my scope", "cannot assist",
        "i specialise in", "i specialize in", "i am a research assistant",
        "cannot do that", "not something i can",
    ]
    head = response[:500].lower()
    return any(p in head for p in refusal_phrases)


def run_baseline_benchmark(eval_filename="evaluation_set_extended.json", k=3):
    t_start = time.time()
    eval_set = load_eval_set(eval_filename)

    # Select a representative subset for full response testing (expensive)
    # Pick queries from key categories
    refusal_cats = {"off_topic", "non_research"}
    programmatic_cats = {"meta", "glossary", "researcher", "project"}

    refusal_queries = [e for e in eval_set if e["expected"] in refusal_cats][:10]
    programmatic_queries = [e for e in eval_set if e["expected"] in programmatic_cats][:10]
    llm_queries = [e for e in eval_set if e["expected"] not in refusal_cats and e["expected"] not in programmatic_cats][:10]

    test_queries = refusal_queries + programmatic_queries + llm_queries
    print(f"Baseline Benchmark: {len(test_queries)} queries × K={k} runs")
    print(f"  Refusal queries: {len(refusal_queries)}")
    print(f"  Programmatic-category queries: {len(programmatic_queries)}")
    print(f"  LLM-category queries: {len(llm_queries)}")

    print("\nLoading Baseline...", end=" ", flush=True)
    baseline = load_agent(os.path.join(STUDY_DIR, "agents", "baseline"))
    print("OK")

    # Run K times
    results = []
    for entry in test_queries:
        query = entry["query"]
        expected = entry["expected"]
        print(f"  {query[:55]}...", end=" ", flush=True)

        responses = []
        times = []
        for _ in range(k):
            start = time.time()
            try:
                r = baseline.chat(query)
                elapsed = (time.time() - start) * 1000
                responses.append(strip_trace(r))
                times.append(elapsed)
            except Exception as e:
                responses.append(f"ERROR: {e}")
                times.append(0)

        # Metrics
        unique = len(set(responses))
        consistent = (unique == 1)
        avg_len = sum(len(r.split()) for r in responses) / len(responses)
        avg_time = sum(times) / len(times)
        refused = any(is_refusal(r) for r in responses)

        results.append({
            "query": query,
            "expected": expected,
            "consistent": consistent,
            "n_unique": unique,
            "avg_words": round(avg_len),
            "avg_time_ms": round(avg_time),
            "refused": refused,
            "should_refuse": expected in refusal_cats,
        })
        print(f"{'✓' if consistent else '✗'} {unique} unique, {avg_len:.0f}w, {avg_time:.0f}ms"
              f"{' [refused]' if refused else ''}")

    elapsed = time.time() - t_start

    # Summary
    total = len(results)
    n_consistent = sum(1 for r in results if r["consistent"])
    c_out = n_consistent / total if total else 0

    # Refusal analysis
    should_refuse = [r for r in results if r["should_refuse"]]
    correctly_refused = sum(1 for r in should_refuse if r["refused"])
    refusal_rate = correctly_refused / len(should_refuse) if should_refuse else 0

    should_not_refuse = [r for r in results if not r["should_refuse"]]
    false_refusals = sum(1 for r in should_not_refuse if r["refused"])

    avg_words = sum(r["avg_words"] for r in results) / total if total else 0
    avg_time = sum(r["avg_time_ms"] for r in results) / total if total else 0

    print(f"\n{'='*60}")
    print(f"  BASELINE RELIABILITY SUMMARY")
    print(f"{'='*60}")
    print(f"  Response consistency (C_out, K={k}):  {c_out:.1%} ({n_consistent}/{total})")
    print(f"  Refusal accuracy:                     {refusal_rate:.1%} ({correctly_refused}/{len(should_refuse)})")
    print(f"  False refusals:                        {false_refusals}/{len(should_not_refuse)}")
    print(f"  Avg response length:                   {avg_words:.0f} words")
    print(f"  Avg response time:                     {avg_time:.0f} ms")
    print(f"  Time elapsed:                          {elapsed:.0f}s")
    print(f"{'='*60}")

    # Save
    out_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "k": k,
        "total_queries": total,
        "c_out": round(c_out, 4),
        "refusal_accuracy": round(refusal_rate, 4),
        "false_refusals": false_refusals,
        "avg_words": round(avg_words),
        "avg_time_ms": round(avg_time),
        "results": results,
    }
    results_dir = os.path.join(STUDY_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"baseline_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    run_baseline_benchmark()
