#!/usr/bin/env python3
"""
RAG Architecture Study — Benchmark Runner

Runs all 30 core queries + 15 paraphrases through all 5 variants (V0–V4),
collecting responses, timing, and classification data.

Phase 1: Single run (automated metrics)
Phase 2: Consistency test (K=3 runs on core queries)

Output: results/benchmark_YYYYMMDD_HHMMSS.json
"""

import os
import sys
import json
import time
import importlib
import importlib.util
from datetime import datetime
from pathlib import Path

# Load env vars from web/.env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "web", ".env"))

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))

# ── Benchmark queries ──────────────────────────────────────────────────────

CORE_QUERIES = [
    # Meta-questions (3)
    ("meta", "What can you do?"),
    ("meta", "What is UNINOVIS?"),
    ("meta", "Which universities are in UNINOVIS?"),
    # Non-research tasks (3)
    ("non_research", "Write me an essay about AI"),
    ("non_research", "Can you book me a flight?"),
    ("non_research", 'Translate this text to French: "Responsible AI is important"'),
    # Conceptual / Glossary (5)
    ("glossary", "What is explainable AI?"),
    ("glossary", "What is fairness in AI?"),
    ("glossary", "What is the EU AI Act?"),
    ("glossary", "What is the difference between interpretability and explainability?"),
    ("glossary", "Is AI dangerous?"),
    # Researcher lookup (3)
    ("researcher", "Papers by Rubén González Vallejo"),
    ("researcher", "What has Fabrizio Esposito published?"),
    ("researcher", "What are the research interests of Frank-Michael Schleif?"),
    # Project queries (3)
    ("project", "What is the TAILOR project about?"),
    ("project", "Describe the IntelliMan project"),
    ("project", "List research projects on trustworthy AI"),
    # Topic search (4)
    ("topic_search", "Papers on AI ethics"),
    ("topic_search", "Papers about AI and privacy"),
    ("topic_search", "Research on AI in education within UNINOVIS"),
    ("topic_search", "List all papers from UDCLV on AI in healthcare"),
    # Gap analysis (3)
    ("gap", "What responsible AI topics have not been studied in UNINOVIS?"),
    ("gap", "Are there gaps in UNINOVIS research on AI regulation?"),
    ("gap", "Which responsible AI subtopics are least studied?"),
    # Off-topic (3)
    ("off_topic", "What is quantum computing?"),
    ("off_topic", "What is the weather today?"),
    ("off_topic", "Who won the last World Cup?"),
    # Boundary / ambiguous (3)
    ("boundary", "Things to do"),
    ("boundary", "Can AI be trusted?"),
    ("boundary", "What is a language model?"),
]

PARAPHRASE_QUERIES = [
    ("meta", "Tell me about your capabilities", "What can you do?"),
    ("glossary", "Define XAI", "What is explainable AI?"),
    ("researcher", "Publications by Rubén González", "Papers by Rubén González Vallejo"),
    ("project", "Describe the TAILOR project", "What is the TAILOR project about?"),
    ("topic_search", "Articles about AI ethics", "Papers on AI ethics"),
    ("non_research", "Help me draft a paper on AI", "Write me an essay about AI"),
    ("glossary", "Describe the EU AI Act", "What is the EU AI Act?"),
    ("researcher", "List Fabrizio Esposito's publications", "What has Fabrizio Esposito published?"),
    ("gap", "What are the research gaps in UNINOVIS?", "What responsible AI topics have not been studied in UNINOVIS?"),
    ("glossary", "Define fairness in artificial intelligence", "What is fairness in AI?"),
    ("off_topic", "Explain quantum computing", "What is quantum computing?"),
    ("topic_search", "Research on privacy in AI", "Papers about AI and privacy"),
    ("glossary", "Can AI be harmful?", "Is AI dangerous?"),
    ("off_topic", "Tell me the World Cup winner", "Who won the last World Cup?"),
    ("project", "Show me projects about trustworthy AI", "List research projects on trustworthy AI"),
]

# ── Variant definitions ────────────────────────────────────────────────────

VARIANTS = [
    {
        "id": "V0",
        "name": "Oneshot",
        "folder": "oneshot",
        "agent_id": "rag_study_oneshot",
    },
    {
        "id": "V1",
        "name": "Vanilla RAG",
        "folder": "vanilla_rag",
        "agent_id": "rag_study_vanilla",
    },
    {
        "id": "V2",
        "name": "LLM Reasoning",
        "folder": "llm_reasoning",
        "agent_id": "rag_study_llm_reasoning",
    },
    {
        "id": "V3",
        "name": "Procedural",
        "folder": "procedural",
        "agent_id": "rag_study_procedural",
    },
    {
        "id": "V4",
        "name": "LLM-Guided",
        "folder": "llm_guided",
        "agent_id": "rag_study_llm_guided",
    },
]


def load_agent(variant: dict):
    """Dynamically load and instantiate an agent from its folder."""
    folder = variant["folder"]
    agent_dir = os.path.join(os.path.dirname(__file__), folder)
    # Import the agent module
    spec = importlib.util.spec_from_file_location(
        f"agent_{folder}", os.path.join(agent_dir, "agent.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    agent = mod.Agent()
    return agent


def run_query(agent, query: str, variant_id: str) -> dict:
    """Run a single query and collect response + timing."""
    start = time.time()
    try:
        response = agent.chat(query)
        elapsed_ms = int((time.time() - start) * 1000)
        # Strip HTML decision traces for word count
        import re
        clean = re.sub(r'<details.*?</details>', '', response or '', flags=re.DOTALL)
        clean = re.sub(r'<[^>]+>', '', clean)
        word_count = len(clean.split())
        return {
            "response": response,
            "time_ms": elapsed_ms,
            "word_count": word_count,
            "error": None,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "response": None,
            "time_ms": elapsed_ms,
            "word_count": 0,
            "error": str(e),
        }


def run_phase1(agents: dict) -> dict:
    """Phase 1: Run all queries once through all variants."""
    results = {}
    total = len(CORE_QUERIES) + len(PARAPHRASE_QUERIES)

    for v_info in VARIANTS:
        vid = v_info["id"]
        agent = agents[vid]
        results[vid] = {"core": [], "paraphrases": []}

        print(f"\n{'='*60}")
        print(f"  {vid}: {v_info['name']}")
        print(f"{'='*60}")

        # Core queries
        for i, (expected_type, query) in enumerate(CORE_QUERIES):
            print(f"  [{i+1}/{len(CORE_QUERIES)}] {query[:60]}...", end=" ", flush=True)
            result = run_query(agent, query, vid)
            result["query"] = query
            result["expected_type"] = expected_type
            result["query_index"] = i
            results[vid]["core"].append(result)
            status = f"{result['time_ms']}ms, {result['word_count']}w"
            if result["error"]:
                status = f"ERROR: {result['error'][:40]}"
            print(status)

        # Paraphrase queries
        for i, (expected_type, query, original) in enumerate(PARAPHRASE_QUERIES):
            print(f"  [P{i+1}/{len(PARAPHRASE_QUERIES)}] {query[:60]}...", end=" ", flush=True)
            result = run_query(agent, query, vid)
            result["query"] = query
            result["original_query"] = original
            result["expected_type"] = expected_type
            result["query_index"] = i
            results[vid]["paraphrases"].append(result)
            status = f"{result['time_ms']}ms, {result['word_count']}w"
            if result["error"]:
                status = f"ERROR: {result['error'][:40]}"
            print(status)

    return results


def run_phase2(agents: dict, k: int = 3) -> dict:
    """Phase 2: Consistency test — run core queries K times."""
    results = {}

    for v_info in VARIANTS:
        vid = v_info["id"]
        agent = agents[vid]
        results[vid] = {}

        print(f"\n{'='*60}")
        print(f"  {vid}: {v_info['name']} — Consistency (K={k})")
        print(f"{'='*60}")

        for i, (expected_type, query) in enumerate(CORE_QUERIES):
            results[vid][i] = []
            print(f"  [{i+1}/{len(CORE_QUERIES)}] {query[:50]}...", end=" ", flush=True)
            for run in range(k):
                result = run_query(agent, query, vid)
                result["run"] = run
                results[vid][i].append(result)
            times = [r["time_ms"] for r in results[vid][i]]
            print(f"runs: {times}")

    return results


def compute_phase1_metrics(results: dict) -> dict:
    """Compute automated metrics from Phase 1 results."""
    metrics = {}

    for vid in results:
        core = results[vid]["core"]
        para = results[vid]["paraphrases"]

        # Response length stats
        word_counts = [r["word_count"] for r in core if r["response"]]
        avg_words = sum(word_counts) / len(word_counts) if word_counts else 0

        # Response time stats
        times = [r["time_ms"] for r in core if r["response"]]
        avg_time = sum(times) / len(times) if times else 0

        # Error rate
        errors = sum(1 for r in core if r["error"])

        # Per query type
        type_stats = {}
        for r in core:
            t = r["expected_type"]
            if t not in type_stats:
                type_stats[t] = {"count": 0, "total_words": 0, "total_time": 0, "errors": 0}
            type_stats[t]["count"] += 1
            type_stats[t]["total_words"] += r["word_count"]
            type_stats[t]["total_time"] += r["time_ms"]
            if r["error"]:
                type_stats[t]["errors"] += 1

        for t in type_stats:
            s = type_stats[t]
            s["avg_words"] = round(s["total_words"] / s["count"], 1)
            s["avg_time_ms"] = round(s["total_time"] / s["count"])

        metrics[vid] = {
            "total_queries": len(core),
            "avg_word_count": round(avg_words, 1),
            "avg_time_ms": round(avg_time),
            "errors": errors,
            "paraphrase_count": len(para),
            "paraphrase_errors": sum(1 for r in para if r["error"]),
            "by_type": type_stats,
        }

    return metrics


def compute_phase2_metrics(results: dict) -> dict:
    """Compute consistency metrics from Phase 2."""
    metrics = {}

    for vid in results:
        consistent = 0
        total = 0
        for qi in results[vid]:
            runs = results[vid][qi]
            responses = [r["response"] for r in runs if r["response"]]
            if len(responses) >= 2:
                total += 1
                # Check if all responses are identical (exact match)
                if all(r == responses[0] for r in responses):
                    consistent += 1

        metrics[vid] = {
            "total_queries": total,
            "exact_match": consistent,
            "consistency_rate": round(consistent / total, 3) if total else 0,
        }

    return metrics


def print_summary(p1_metrics: dict = None, p2_metrics: dict = None):
    """Print summary tables."""
    if p1_metrics:
        print("\n" + "=" * 80)
        print("  PHASE 1 SUMMARY — Automated Metrics")
        print("=" * 80)

        # Header
        header = f"{'Metric':<25}"
        for v in VARIANTS:
            header += f"{'  ' + v['id']:>10}"
        print(header)
        print("-" * 75)

        # Avg word count
        row = f"{'Avg word count':<25}"
        for v in VARIANTS:
            val = p1_metrics[v["id"]]["avg_word_count"]
            row += f"{val:>10.1f}"
        print(row)

        # Avg time
        row = f"{'Avg time (ms)':<25}"
        for v in VARIANTS:
            val = p1_metrics[v["id"]]["avg_time_ms"]
            row += f"{val:>10}"
        print(row)

        # Errors
        row = f"{'Errors':<25}"
        for v in VARIANTS:
            val = p1_metrics[v["id"]]["errors"]
            row += f"{val:>10}"
        print(row)

        # Per-type breakdown
        all_types = ["meta", "non_research", "glossary", "researcher", "project",
                     "topic_search", "gap", "off_topic", "boundary"]

        print(f"\n{'--- By Query Type (avg words) ---':^75}")
        header = f"{'Type':<25}"
        for v in VARIANTS:
            header += f"{'  ' + v['id']:>10}"
        print(header)
        print("-" * 75)

        for t in all_types:
            row = f"{t:<25}"
            for v in VARIANTS:
                stats = p1_metrics[v["id"]]["by_type"].get(t, {})
                val = stats.get("avg_words", 0)
                row += f"{val:>10.1f}"
            print(row)

        print(f"\n{'--- By Query Type (avg ms) ---':^75}")
        header = f"{'Type':<25}"
        for v in VARIANTS:
            header += f"{'  ' + v['id']:>10}"
        print(header)
        print("-" * 75)

        for t in all_types:
            row = f"{t:<25}"
            for v in VARIANTS:
                stats = p1_metrics[v["id"]]["by_type"].get(t, {})
                val = stats.get("avg_time_ms", 0)
                row += f"{val:>10}"
            print(row)

    if p2_metrics:
        print("\n" + "=" * 80)
        print("  PHASE 2 SUMMARY — Consistency (K=3)")
        print("=" * 80)
        header = f"{'Metric':<25}"
        for v in VARIANTS:
            header += f"{'  ' + v['id']:>10}"
        print(header)
        print("-" * 75)

        row = f"{'Exact match / 30':<25}"
        for v in VARIANTS:
            val = p2_metrics[v["id"]]["exact_match"]
            row += f"{val:>10}"
        print(row)

        row = f"{'Consistency rate':<25}"
        for v in VARIANTS:
            val = p2_metrics[v["id"]]["consistency_rate"]
            row += f"{val:>10.3f}"
        print(row)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG Study Benchmark Runner")
    parser.add_argument("--phase", type=int, choices=[1, 2], default=1,
                        help="Phase to run: 1=single run, 2=consistency (K=3)")
    parser.add_argument("--variants", type=str, default=None,
                        help="Comma-separated variant IDs to run (e.g. V0,V3,V4). Default: all")
    parser.add_argument("--k", type=int, default=3,
                        help="Number of runs for consistency test (Phase 2)")
    args = parser.parse_args()

    # Filter variants
    global VARIANTS
    active_variants = VARIANTS
    if args.variants:
        requested = [v.strip().upper() for v in args.variants.split(",")]
        active_variants = [v for v in VARIANTS if v["id"] in requested]
        VARIANTS = active_variants

    if not active_variants:
        print("No valid variants specified.")
        return

    print(f"\nRAG Architecture Study — Benchmark Runner")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Phase: {args.phase}")
    print(f"Variants: {', '.join(v['id'] + ' (' + v['name'] + ')' for v in active_variants)}")

    # Load agents
    print("\nLoading agents...")
    agents = {}
    for v in active_variants:
        print(f"  Loading {v['id']}: {v['name']}...", end=" ", flush=True)
        try:
            agent = load_agent(v)
            agents[v["id"]] = agent
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            return

    # Run benchmark
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    if args.phase == 1:
        p1_results = run_phase1(agents)
        p1_metrics = compute_phase1_metrics(p1_results)
        print_summary(p1_metrics)

        # Save results
        output = {
            "timestamp": timestamp,
            "phase": 1,
            "variants": [v["id"] for v in active_variants],
            "results": p1_results,
            "metrics": p1_metrics,
        }
        out_path = os.path.join(results_dir, f"benchmark_phase1_{timestamp}.json")
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {out_path}")

    elif args.phase == 2:
        p2_results = run_phase2(agents, k=args.k)
        p2_metrics = compute_phase2_metrics(p2_results)
        print_summary(p2_metrics=p2_metrics)

        output = {
            "timestamp": timestamp,
            "phase": 2,
            "k": args.k,
            "variants": [v["id"] for v in active_variants],
            "results": p2_results,
            "metrics": p2_metrics,
        }
        out_path = os.path.join(results_dir, f"benchmark_phase2_{timestamp}.json")
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
