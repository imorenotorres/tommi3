#!/usr/bin/env python3
"""
RAG Architecture Study — Reliability Benchmark

Based on Rabanser et al. (2025), "Towards a Science of AI Agent Reliability"

Tests two reliability dimensions across V3 (code classification) and V4 (LLM classification):
  1. CONSISTENCY: Same query → same classification → same response (K runs)
  2. ROBUSTNESS: Paraphrased queries → same classification → same response

Both variants share identical dispatch paths — the ONLY difference is
classification mechanism (deterministic code vs non-deterministic LLM).

Usage:
    python3 reliability_benchmark.py
    python3 reliability_benchmark.py --verbose
    python3 reliability_benchmark.py --json
    python3 reliability_benchmark.py --variants V3     # single variant
"""

import os
import sys
import json
import time
import argparse

# Load env vars
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "web", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))

import importlib
import importlib.util

# ── Classification categories (shared by V3 and V4) ───────────────────────
# These map to the shared_dispatch.py categories.
# V3's code chain has finer distinctions (conceptual_gloss vs conceptual_no,
# uni_papers vs topic_search) — we map both to the shared taxonomy.

# Mapping from V3 fine-grained → shared categories
V3_TO_SHARED = {
    "meta": "meta",
    "non_research": "non_research",
    "figure": "figure",
    "followup": "followup",
    "project": "project",
    "researcher": "researcher",
    "glossary": "glossary",
    "conceptual_gloss": "glossary",  # V3 distinguishes, shared doesn't
    "conceptual_no": "general",     # conceptual without glossary → general
    "gap": "gap",
    "topic_search": "topic_search",
    "university_papers": "university_papers",
    "uni_papers": "university_papers",
    "off_topic": "off_topic",
    "general": "general",
    "rag": "general",              # V3 fallback → general
    "affiliation": "university_papers",
    "shared_topics": "topic_search",
}


# ── Test queries with expected classifications ─────────────────────────────
# Expected classification uses the SHARED taxonomy (not V3-specific)

CLASSIFICATION_TESTS = [
    # Meta-questions
    ("What can you do?", "meta"),
    ("What is UNINOVIS?", "meta"),
    ("Which universities are in UNINOVIS?", "meta"),
    ("How does this work?", "meta"),
    ("Who are you?", "meta"),

    # Non-research tasks
    ("Write me an essay about AI", "non_research"),
    ("Can you book me a flight?", "non_research"),
    ("Translate this text to French: 'Responsible AI is important'", "non_research"),
    ("What is the weather today?", "non_research"),
    ("Who won the last World Cup?", "non_research"),
    ("Can you give me the recipe of Responsible AI Coffee?", "non_research"),

    # Figure/map requests
    ("Show a figure with all the publications per partner", "figure"),
    ("Show a map with the number of research projects per partner", "figure"),
    ("Show a figure of papers by year", "figure"),

    # Glossary / conceptual (with glossary match)
    ("What is explainable AI?", "glossary"),
    ("What is fairness in AI?", "glossary"),
    ("What is the EU AI Act?", "glossary"),
    ("What is the difference between interpretability and explainability?", "glossary"),
    ("What is trustworthy AI?", "glossary"),

    # Researcher lookup
    ("Papers by Rubén González Vallejo", "researcher"),
    ("What has Fabrizio Esposito published?", "researcher"),
    ("What are the research interests of Frank-Michael Schleif?", "researcher"),

    # Project queries
    ("What is the TAILOR project about?", "project"),
    ("Describe the IntelliMan project", "project"),
    ("List research projects on trustworthy AI", "project"),

    # Topic search
    ("Papers on AI ethics", "topic_search"),
    ("Papers about AI and privacy", "topic_search"),
    ("Research on AI in education within UNINOVIS", "topic_search"),

    # Gap analysis
    ("What responsible AI topics have not been studied in UNINOVIS?", "gap"),
    ("Are there gaps in UNINOVIS research on AI regulation?", "gap"),
    ("Which responsible AI subtopics are least studied?", "gap"),

    # Off-topic
    ("What is quantum computing?", "off_topic"),
    ("Hello", "off_topic"),

    # Boundary / ambiguous
    ("Is AI dangerous?", "general"),
    ("Can AI be trusted?", "general"),
    ("What is a language model?", "general"),
]

# ── Paraphrase robustness tests ───────────────────────────────────────────
# (paraphrase, expected_classification)

PARAPHRASE_TESTS = [
    # Meta
    ("Tell me about your capabilities", "meta"),
    ("What functionality do you offer?", "meta"),
    ("I'd like to know what you can do", "meta"),
    ("Tell me the UNINOVIS partner universities", "meta"),

    # Non-research
    ("Compose an essay on artificial intelligence", "non_research"),
    ("Draft an essay about AI for me", "non_research"),
    ("Book a flight for me please", "non_research"),
    ("I need this translated into French", "non_research"),
    ("Tell me the World Cup winner", "non_research"),
    ("Help me write a report on responsible AI", "non_research"),

    # Figure/map
    ("Display a chart of publications by year", "figure"),
    ("Visualise publications on trustworthy AI", "figure"),
    ("Graph the collaborations among partners", "figure"),

    # Glossary
    ("Define explainable AI", "glossary"),
    ("Explain what XAI means", "glossary"),
    ("Describe the EU AI Act", "glossary"),
    ("Define fairness in artificial intelligence", "glossary"),
    ("How do interpretability and explainability differ?", "glossary"),

    # Researcher
    ("Publications by Rubén González Vallejo", "researcher"),
    ("List Fabrizio Esposito's publications", "researcher"),
    ("Give me the bibliography of Fabrizio Esposito", "researcher"),
    ("What topics does Frank-Michael Schleif work on?", "researcher"),

    # Project
    ("Describe the TAILOR project", "project"),
    ("What does the IntelliMan project do?", "project"),
    ("Show me projects related to trustworthy AI", "project"),

    # Topic search
    ("Articles about AI ethics", "topic_search"),
    ("Publications on AI and privacy", "topic_search"),
    ("AI in education research at UNINOVIS", "topic_search"),

    # Gap
    ("Which responsible AI topics are unexplored?", "gap"),
    ("What are the research gaps in UNINOVIS?", "gap"),
    ("What subtopics are underexplored?", "gap"),

    # Off-topic
    ("Explain quantum computing", "off_topic"),
    ("Things to do", "off_topic"),

    # Boundary
    ("Can AI be harmful?", "general"),
]

# ── Programmatic response consistency test set ─────────────────────────────
# Queries that should produce identical responses across K runs
# (programmatic paths — no LLM in response generation)

PROGRAMMATIC_QUERIES = [
    ("What can you do?", "meta"),
    ("What is UNINOVIS?", "meta"),
    ("Write me an essay about AI", "non_research"),
    ("Can you book me a flight?", "non_research"),
    ("What is explainable AI?", "glossary"),
    ("What is fairness in AI?", "glossary"),
    ("What is the EU AI Act?", "glossary"),
    ("Papers by Rubén González Vallejo", "researcher"),
    ("What has Fabrizio Esposito published?", "researcher"),
    ("What is the TAILOR project about?", "project"),
    ("Describe the IntelliMan project", "project"),
    ("What is the weather today?", "non_research"),
]


# ── Agent loading ──────────────────────────────────────────────────────────

def load_agent(folder):
    """Load an agent from a study variant folder."""
    agent_dir = os.path.join(os.path.dirname(__file__), folder)
    spec = importlib.util.spec_from_file_location(
        f"agent_{folder}", os.path.join(agent_dir, "agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Agent()


def classify_v3(agent, query):
    """Run V3's deterministic code classification."""
    return agent._code_classify(query)


def classify_v4(agent, query):
    """Run V4's LLM classification."""
    return agent._llm_classify(query)


# ── Test 1: Classification Accuracy ────────────────────────────────────────

def test_classification_accuracy(agent, classify_fn, variant_name, verbose=False):
    """Test classification accuracy against expected categories."""
    print(f"\n{'='*70}")
    print(f"TEST 1: Classification Accuracy — {variant_name}")
    print(f"{'='*70}")

    total = 0
    correct = 0
    failures = []

    for query, expected in CLASSIFICATION_TESTS:
        result = classify_fn(agent, query)
        cat = result.get("category", "general")
        # V3 may return fine-grained categories — map to shared
        cat_mapped = V3_TO_SHARED.get(cat, cat)
        total += 1

        if cat_mapped == expected:
            correct += 1
            if verbose:
                print(f"  [OK] {query[:55]:55s} → {cat}")
        else:
            failures.append((query, expected, cat, cat_mapped))
            print(f"  [!!] {query[:55]:55s}")
            print(f"       Expected: {expected}, Got: {cat} (→ {cat_mapped})")

    rate = correct / total if total else 0
    print(f"\nAccuracy: {correct}/{total} ({rate:.1%})")

    return {"total": total, "correct": correct, "rate": round(rate, 4),
            "failures": [(q, e, g, m) for q, e, g, m in failures]}


# ── Test 2: Classification Consistency (K runs) ───────────────────────────

def test_classification_consistency(agent, classify_fn, variant_name, k=5, verbose=False):
    """Run each query K times — same classification every time?"""
    print(f"\n{'='*70}")
    print(f"TEST 2: Classification Consistency (K={k}) — {variant_name}")
    print(f"{'='*70}")

    total = 0
    consistent = 0
    inconsistent = []

    for query, expected in CLASSIFICATION_TESTS:
        categories = []
        for _ in range(k):
            result = classify_fn(agent, query)
            cat = result.get("category", "general")
            categories.append(cat)

        total += 1
        unique = set(categories)
        if len(unique) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {query[:55]:55s} → {categories[0]} (x{k})")
        else:
            inconsistent.append((query, expected, categories))
            print(f"  [!!] {query[:55]:55s} → {unique}")

    rate = consistent / total if total else 0
    print(f"\nConsistency: {consistent}/{total} ({rate:.1%})")

    return {"total": total, "consistent": consistent, "rate": round(rate, 4),
            "inconsistent": [(q, e, c) for q, e, c in inconsistent]}


# ── Test 3: Paraphrase Robustness ─────────────────────────────────────────

def test_paraphrase_robustness(agent, classify_fn, variant_name, verbose=False):
    """Do paraphrased queries get the correct classification?"""
    print(f"\n{'='*70}")
    print(f"TEST 3: Paraphrase Robustness ({len(PARAPHRASE_TESTS)} paraphrases) — {variant_name}")
    print(f"{'='*70}")

    total = 0
    correct = 0
    failures = []

    for query, expected in PARAPHRASE_TESTS:
        result = classify_fn(agent, query)
        cat = result.get("category", "general")
        cat_mapped = V3_TO_SHARED.get(cat, cat)
        total += 1

        if cat_mapped == expected:
            correct += 1
            if verbose:
                print(f"  [OK] {query[:55]:55s} → {cat}")
        else:
            failures.append((query, expected, cat, cat_mapped))
            print(f"  [!!] {query[:55]:55s}")
            print(f"       Expected: {expected}, Got: {cat} (→ {cat_mapped})")

    rate = correct / total if total else 0
    print(f"\nRobustness: {correct}/{total} ({rate:.1%})")

    return {"total": total, "correct": correct, "rate": round(rate, 4),
            "failures": [(q, e, g, m) for q, e, g, m in failures]}


# ── Test 4: Response Consistency (programmatic paths) ─────────────────────

def test_response_consistency(agent, variant_name, k=3, verbose=False):
    """For programmatic paths, verify identical response across K runs."""
    print(f"\n{'='*70}")
    print(f"TEST 4: Response Consistency (K={k}, {len(PROGRAMMATIC_QUERIES)} queries) — {variant_name}")
    print(f"{'='*70}")

    total = 0
    consistent = 0
    inconsistent = []

    for query, expected_type in PROGRAMMATIC_QUERIES:
        responses = []
        for _ in range(k):
            try:
                r = agent.chat(query)
                # Strip decision trace for comparison
                import re
                clean = re.sub(r'<details.*?</details>', '', r, flags=re.DOTALL).strip()
                responses.append(clean)
            except Exception as e:
                responses.append(f"ERROR: {e}")

        total += 1
        if len(set(responses)) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {query[:55]:55s} → identical (x{k})")
        else:
            inconsistent.append((query, expected_type, responses))
            print(f"  [!!] {query[:55]:55s} → {len(set(responses))} unique responses")
            if verbose:
                for i, r in enumerate(responses):
                    print(f"       run{i}: {r[:80]}...")

    rate = consistent / total if total else 0
    print(f"\nResponse consistency: {consistent}/{total} ({rate:.1%})")

    return {"total": total, "consistent": consistent, "rate": round(rate, 4),
            "inconsistent": [(q, t) for q, t, _ in inconsistent]}


# ── Test 5: Classification Agreement (V3 vs V4) ──────────────────────────

def test_classification_agreement(v3_agent, v4_agent, verbose=False):
    """Compare V3 and V4 classifications on the same queries."""
    print(f"\n{'='*70}")
    print(f"TEST 5: Classification Agreement (V3 code vs V4 LLM)")
    print(f"{'='*70}")

    all_queries = [(q, e) for q, e in CLASSIFICATION_TESTS] + [(q, e) for q, e in PARAPHRASE_TESTS]
    total = 0
    agree = 0
    disagree_v3_correct = 0
    disagree_v4_correct = 0
    disagree_both_wrong = 0
    disagreements = []

    for query, expected in all_queries:
        v3_result = classify_v3(v3_agent, query)
        v4_result = classify_v4(v4_agent, query)
        v3_cat = V3_TO_SHARED.get(v3_result.get("category", "general"), v3_result.get("category", "general"))
        v4_cat = v4_result.get("category", "general")

        total += 1
        if v3_cat == v4_cat:
            agree += 1
            if verbose:
                print(f"  [==] {query[:50]:50s} → {v3_cat}")
        else:
            v3_ok = (v3_cat == expected)
            v4_ok = (v4_cat == expected)
            if v3_ok and not v4_ok:
                disagree_v3_correct += 1
            elif v4_ok and not v3_ok:
                disagree_v4_correct += 1
            else:
                disagree_both_wrong += 1
            disagreements.append((query, expected, v3_cat, v4_cat, v3_ok, v4_ok))
            print(f"  [!=] {query[:50]:50s}")
            print(f"       V3={v3_cat}{'✓' if v3_ok else '✗'}, V4={v4_cat}{'✓' if v4_ok else '✗'}, expected={expected}")

    rate = agree / total if total else 0
    print(f"\nAgreement: {agree}/{total} ({rate:.1%})")
    print(f"  V3 correct when disagree: {disagree_v3_correct}")
    print(f"  V4 correct when disagree: {disagree_v4_correct}")
    print(f"  Both wrong when disagree: {disagree_both_wrong}")

    return {
        "total": total, "agree": agree, "rate": round(rate, 4),
        "disagree_v3_correct": disagree_v3_correct,
        "disagree_v4_correct": disagree_v4_correct,
        "disagree_both_wrong": disagree_both_wrong,
        "disagreements": [(q, e, v3, v4) for q, e, v3, v4, _, _ in disagreements],
    }


# ── Main ──────────────────────────────────────────────────────────────────

def run_all(variants=None, verbose=False, output_json=False, k_consistency=5, k_response=3):
    if variants is None:
        variants = ["V3", "V4"]

    t_start = time.time()
    results = {}

    # Load agents
    agents = {}
    if "V3" in variants:
        print("Loading V3 (Procedural)...", end=" ", flush=True)
        agents["V3"] = load_agent("procedural")
        print("OK")
    if "V4" in variants:
        print("Loading V4 (LLM-Guided)...", end=" ", flush=True)
        agents["V4"] = load_agent("llm_guided")
        print("OK")

    # Run tests per variant
    for vid in variants:
        agent = agents[vid]
        classify_fn = classify_v3 if vid == "V3" else classify_v4
        vname = f"{vid} ({'code' if vid == 'V3' else 'LLM'})"

        results[vid] = {}
        results[vid]["accuracy"] = test_classification_accuracy(
            agent, classify_fn, vname, verbose)
        results[vid]["consistency"] = test_classification_consistency(
            agent, classify_fn, vname, k=k_consistency, verbose=verbose)
        results[vid]["robustness"] = test_paraphrase_robustness(
            agent, classify_fn, vname, verbose)
        results[vid]["response_consistency"] = test_response_consistency(
            agent, vname, k=k_response, verbose=verbose)

    # Cross-variant agreement test
    agreement = None
    if "V3" in agents and "V4" in agents:
        agreement = test_classification_agreement(
            agents["V3"], agents["V4"], verbose)
        results["agreement"] = agreement

    elapsed = time.time() - t_start

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"RELIABILITY BENCHMARK — Summary (Rabanser et al. 2025)")
    print(f"{'='*70}")

    for vid in variants:
        r = results[vid]
        print(f"\n  {vid} ({'Code classification' if vid == 'V3' else 'LLM classification'}):")
        print(f"    Classification accuracy:     {r['accuracy']['rate']:.1%} "
              f"({r['accuracy']['correct']}/{r['accuracy']['total']})")
        print(f"    Classification consistency:  {r['consistency']['rate']:.1%} "
              f"({r['consistency']['consistent']}/{r['consistency']['total']})")
        print(f"    Paraphrase robustness:       {r['robustness']['rate']:.1%} "
              f"({r['robustness']['correct']}/{r['robustness']['total']})")
        print(f"    Response consistency:         {r['response_consistency']['rate']:.1%} "
              f"({r['response_consistency']['consistent']}/{r['response_consistency']['total']})")

        # Rabanser aggregate scores
        c_traj = r['consistency']['rate']       # Trajectory consistency
        c_out = r['response_consistency']['rate']  # Outcome consistency
        r_prompt = r['robustness']['rate']      # Prompt robustness

        r_con = (c_traj + c_out) / 2
        r_rob = r_prompt

        print(f"    ── Rabanser Dimensions ──")
        print(f"    R_Con (Consistency):  {r_con:.3f}  (C_traj={c_traj:.3f}, C_out={c_out:.3f})")
        print(f"    R_Rob (Robustness):   {r_rob:.3f}")

        results[vid]["rabanser"] = {
            "R_Con": round(r_con, 4),
            "C_traj": round(c_traj, 4),
            "C_out": round(c_out, 4),
            "R_Rob": round(r_rob, 4),
        }

    if agreement:
        print(f"\n  V3 vs V4 Classification Agreement:")
        print(f"    Agreement rate: {agreement['rate']:.1%} ({agreement['agree']}/{agreement['total']})")
        print(f"    When disagree — V3 correct: {agreement['disagree_v3_correct']}, "
              f"V4 correct: {agreement['disagree_v4_correct']}, "
              f"both wrong: {agreement['disagree_both_wrong']}")

    print(f"\n  Time elapsed: {elapsed:.1f}s")
    print(f"{'='*70}")

    if output_json:
        # Clean results for JSON (remove non-serializable items)
        out = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "variants": variants,
        }
        for vid in variants:
            r = results[vid]
            out[vid] = {
                "accuracy": {k: v for k, v in r["accuracy"].items() if k != "failures"},
                "accuracy_failures": r["accuracy"]["failures"],
                "consistency": {k: v for k, v in r["consistency"].items() if k != "inconsistent"},
                "consistency_issues": r["consistency"].get("inconsistent", []),
                "robustness": {k: v for k, v in r["robustness"].items() if k != "failures"},
                "robustness_failures": r["robustness"]["failures"],
                "response_consistency": {k: v for k, v in r["response_consistency"].items() if k != "inconsistent"},
                "response_issues": r["response_consistency"].get("inconsistent", []),
                "rabanser": r["rabanser"],
            }
        if agreement:
            out["agreement"] = {k: v for k, v in agreement.items() if k != "disagreements"}
            out["agreement_disagreements"] = agreement["disagreements"]

        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)
        out_path = os.path.join(results_dir,
                                f"reliability_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {out_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RAG Study — Reliability Benchmark (Rabanser et al. 2025)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true", help="Save results as JSON")
    parser.add_argument("--variants", type=str, default=None,
                        help="Comma-separated: V3,V4 (default: both)")
    parser.add_argument("--k-consistency", type=int, default=5,
                        help="K runs for consistency test (default: 5)")
    parser.add_argument("--k-response", type=int, default=3,
                        help="K runs for response consistency (default: 3)")
    args = parser.parse_args()

    variants = None
    if args.variants:
        variants = [v.strip().upper() for v in args.variants.split(",")]

    run_all(variants=variants, verbose=args.verbose, output_json=args.json,
            k_consistency=args.k_consistency, k_response=args.k_response)
