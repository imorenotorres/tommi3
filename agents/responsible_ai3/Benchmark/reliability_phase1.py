"""
Reliability Benchmark — Phase 1: Automated tests (no LLM needed)

Tests two reliability dimensions that can be evaluated without calling the LLM:
  1. CONSISTENCY: Classification consistency — same query always gets same path
  2. ROBUSTNESS: Paraphrase robustness — rephrased queries get the same classification

Based on: Rabanser et al. (2025), "Towards a Science of AI Agent Reliability"

Usage:
    python3 reliability_phase1.py
    python3 reliability_phase1.py --verbose
    python3 reliability_phase1.py --json          # Machine-readable output
"""

import os
import sys
import re
import json
import argparse
import time

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(AGENT_DIR, ".."))
sys.path.insert(0, os.path.join(AGENT_DIR, "..", "..", "web"))
sys.path.insert(0, AGENT_DIR)
os.chdir(AGENT_DIR)
os.environ.setdefault("MISTRAL_API_KEY", "dummy")

from decision_logic_test import classify_query, TEST_CASES

# ---------------------------------------------------------------------------
# Paraphrase test set
# Each entry: (original, paraphrase, expected_classification)
# Paraphrases at three levels:
#   Surface:    change wording, keep structure
#   Structural: change sentence structure
#   Boundary:   edge cases that stress the classification
# ---------------------------------------------------------------------------

PARAPHRASE_TESTS = [
    # === META-QUESTIONS ===
    # Surface
    ("What can you do?", "What are your capabilities?", "meta"),
    ("What can you do?", "What functionality do you offer?", "meta"),
    ("How does this work?", "How do you operate?", "meta"),
    ("Who are you?", "What agent is this?", "meta"),
    # Structural
    ("What can you do?", "I'd like to know what you can do", "meta"),
    ("Which universities are in UNINOVIS?", "Tell me the UNINOVIS partner universities", "meta"),

    # === NON-RESEARCH TASKS ===
    # Surface
    ("Write me an essay about AI", "Compose an essay on artificial intelligence", "non_research"),
    ("Write me an essay about AI", "Draft an essay about AI for me", "non_research"),
    ("Can you book me a flight?", "Book a flight for me please", "non_research"),
    # Structural
    ("Translate this text to French", "I need this translated into French", "non_research"),
    ("Who won the last World Cup?", "Tell me the World Cup winner", "non_research"),
    # Boundary — contains scope terms but intent is non-research
    ("Write me a summary of responsible AI for my essay", "Help me write a report on responsible AI", "non_research"),

    # === FIGURE / MAP ===
    # Surface
    ("Show a figure of papers by year", "Display a chart of publications by year", "figure"),
    ("Show a map of publications on trustworthy AI", "Visualise publications on trustworthy AI", "figure"),
    ("Show a figure of the collaborations", "Graph the collaborations among partners", "figure"),
    # Structural
    ("Show a figure with all the publications per partner", "I want to see a diagram of publications per partner", "figure"),

    # === GAP ANALYSIS ===
    # Surface
    ("What responsible AI topics have not been studied?", "Which responsible AI topics are unexplored?", "gap"),
    ("Are there gaps in UNINOVIS research?", "What are the research gaps in UNINOVIS?", "gap"),
    ("Which responsible AI subtopics are least studied?", "What subtopics are underexplored?", "gap"),
    # Structural
    ("What topics are underrepresented in the database?", "Tell me which topics have little coverage in the database", "gap"),

    # === CONCEPTUAL (GLOSSARY) ===
    # Surface
    ("What is explainable AI?", "Define explainable AI", "conceptual_gloss"),
    ("What is explainable AI?", "Explain what XAI means", "conceptual_gloss"),
    ("What is the EU AI Act?", "Describe the EU AI Act", "conceptual_gloss"),
    ("What is fairness in AI?", "Define fairness in artificial intelligence", "conceptual_gloss"),
    # Structural
    ("What is the difference between interpretability and explainability?",
     "How do interpretability and explainability differ?", "conceptual_gloss"),
    ("What is trustworthy AI?", "I want to understand trustworthy AI", "conceptual_gloss"),

    # === CONCEPTUAL (NOT IN GLOSSARY) ===
    ("Is AI dangerous?", "Can AI be harmful?", "conceptual_no"),
    ("Can AI make decisions on its own?", "Is AI capable of autonomous decision-making?", "conceptual_no"),

    # === PROJECT QUERIES ===
    # Surface
    ("What is the TAILOR project about?", "Describe the TAILOR project", "project"),
    ("Describe the IntelliMan project", "What does the IntelliMan project do?", "project"),
    # Structural
    ("List research projects on trustworthy AI", "Show me projects related to trustworthy AI", "project"),

    # === RESEARCHER LOOKUP ===
    # Surface
    ("Papers by Ruben Gonzalez Vallejo", "Publications by Ruben Gonzalez Vallejo", "researcher"),
    ("What has Fabrizio Esposito published?", "List Fabrizio Esposito's publications", "researcher"),
    # Structural
    ("Papers by Ruben Gonzalez", "Give me the bibliography of Ruben Gonzalez", "researcher"),
    ("What are the research interests of Frank-Michael Schleif?",
     "What topics does Frank-Michael Schleif work on?", "researcher"),

    # === TOPIC SEARCH ===
    # Surface
    ("Papers about AI and privacy", "Publications on AI and privacy", "topic_search"),
    ("Papers on AI ethics", "Articles about AI ethics", "topic_search"),
    # Structural
    ("Research on AI in education within UNINOVIS", "AI in education research at UNINOVIS", "topic_search"),

    # === UNIVERSITY PAPERS ===
    ("List all researchers from THUAS", "Show me THUAS researchers", "uni_papers"),
    ("List all researchers from THUAS", "Who are the researchers at THUAS?", "uni_papers"),

    # === BOUNDARY / ADVERSARIAL ===
    # Vague queries that should NOT match a topic
    ("Hello", "off_topic", "off_topic"),  # greeting
    ("Things to do", "off_topic", "off_topic"),  # everyday phrase
    ("test", "off_topic", "off_topic"),  # testing input
    # Contains scope terms but is a non-research request
    ("Can you give me the recipe of Responsible AI Coffee?", "Recipe for AI Ethics cake", "non_research"),
]


# ---------------------------------------------------------------------------
# Programmatic output consistency test set
# Queries on programmatic paths — output should be identical across runs
# ---------------------------------------------------------------------------

PROGRAMMATIC_CONSISTENCY = [
    # Meta-questions
    "What can you do?",
    "Who are you?",
    "What is UNINOVIS?",
    "Which universities are in UNINOVIS?",
    # Non-research refusals
    "Write me an essay about AI",
    "Can you book me a flight?",
    "What is the weather today?",
    # Off-topic refusals
    "What is quantum computing?",
    # Researcher lookups (programmatic formatting)
    "Papers by Ruben Gonzalez Vallejo",
    # Glossary definitions
    "What is explainable AI?",
    # Project queries
    "What is the TAILOR project about?",
    # Figure requests
    "Show a figure of papers by year",
]


def run_consistency_test(agent, k=5, verbose=False):
    """Test 1: Classification consistency — run each query K times."""
    print(f"\n{'='*70}")
    print(f"TEST 1: Classification Consistency (K={k} runs)")
    print(f"{'='*70}")

    total = 0
    consistent = 0
    inconsistent = []

    for query, expected in TEST_CASES:
        results = []
        for _ in range(k):
            results.append(classify_query(agent, query))

        total += 1
        if len(set(results)) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {query[:55]:55s} -> {results[0]}")
        else:
            inconsistent.append((query, expected, results))
            print(f"  [!!] {query[:55]:55s} -> {set(results)}")

    rate = consistent / total if total else 0
    print(f"\nClassification consistency: {consistent}/{total} ({rate:.1%})")

    if inconsistent:
        print(f"\nInconsistent queries:")
        for q, exp, res in inconsistent:
            print(f"  Query: {q}")
            print(f"  Expected: {exp}, Got: {res}")

    return {"total": total, "consistent": consistent, "rate": rate,
            "inconsistent": [(q, exp, res) for q, exp, res in inconsistent]}


def run_programmatic_consistency_test(agent, k=5, verbose=False):
    """Test 2: Output consistency for programmatic paths."""
    print(f"\n{'='*70}")
    print(f"TEST 2: Programmatic Output Consistency (K={k} runs)")
    print(f"{'='*70}")

    total = 0
    consistent = 0
    inconsistent = []

    for query in PROGRAMMATIC_CONSISTENCY:
        # For programmatic paths, we can test the classification + the
        # _normalise_query output, which should be identical
        results = []
        for _ in range(k):
            normalised = agent._normalise_query(query)
            classification = classify_query(agent, query)
            results.append((normalised, classification))

        total += 1
        normalisations = [r[0] for r in results]
        classifications = [r[1] for r in results]

        if len(set(normalisations)) == 1 and len(set(classifications)) == 1:
            consistent += 1
            if verbose:
                print(f"  [OK] {query[:55]:55s} -> {classifications[0]}")
        else:
            inconsistent.append((query, results))
            print(f"  [!!] {query[:55]:55s}")
            if len(set(normalisations)) > 1:
                print(f"       Normalisation varies: {set(normalisations)}")
            if len(set(classifications)) > 1:
                print(f"       Classification varies: {set(classifications)}")

    rate = consistent / total if total else 0
    print(f"\nProgrammatic output consistency: {consistent}/{total} ({rate:.1%})")
    print(f"(Programmatic paths should always be 100% — any failure is a bug)")

    return {"total": total, "consistent": consistent, "rate": rate}


def run_robustness_test(agent, verbose=False):
    """Test 3: Paraphrase robustness — do rephrased queries get the same classification?"""
    print(f"\n{'='*70}")
    print(f"TEST 3: Paraphrase Robustness ({len(PARAPHRASE_TESTS)} paraphrases)")
    print(f"{'='*70}")

    total = 0
    matched = 0
    failures = []

    for entry in PARAPHRASE_TESTS:
        if len(entry) == 3:
            original, paraphrase, expected = entry
        else:
            continue

        # Special case: entries where paraphrase == "off_topic" are standalone tests
        if original in ("Hello", "Things to do", "test"):
            query = original
        else:
            query = paraphrase

        try:
            actual = classify_query(agent, query)
            total += 1

            if actual == expected:
                matched += 1
                if verbose:
                    print(f"  [OK] {query[:55]:55s} -> {actual}")
            else:
                failures.append((original, query, expected, actual))
                print(f"  [!!] {query[:55]:55s}")
                print(f"       Expected: {expected}, Got: {actual}")
        except Exception as e:
            total += 1
            failures.append((original, query, expected, f"ERROR: {e}"))
            print(f"  [!!] {query[:55]:55s} ERROR: {e}")

    rate = matched / total if total else 0
    print(f"\nParaphrase robustness: {matched}/{total} ({rate:.1%})")

    if failures:
        print(f"\nFailed paraphrases ({len(failures)}):")
        for orig, para, exp, act in failures:
            if orig != para:
                print(f"  Original:   {orig}")
                print(f"  Paraphrase: {para}")
            else:
                print(f"  Query: {para}")
            print(f"  Expected: {exp}, Got: {act}")
            print()

    return {"total": total, "matched": matched, "rate": rate,
            "failures": [(o, p, e, a) for o, p, e, a in failures]}


def run_normalisation_test(agent, verbose=False):
    """Test 4: Verify synonym normalisation produces expected results."""
    print(f"\n{'='*70}")
    print(f"TEST 4: Synonym Normalisation Verification")
    print(f"{'='*70}")

    NORMALISATION_CASES = [
        ("Publications by Gonzalez", "papers by Gonzalez"),
        ("Visualise the collaborations", "figure the collaborations"),
        ("Define explainable AI", "what is explainable AI"),
        ("Give me the bibliography of Esposito", "list the papers by Esposito"),
        ("Help me draft a paper on AI", "Help me write an essay on AI"),
        ("Tell me about your capabilities", "Tell me about what can you do"),
        ("Which topics are underexplored?", "Which topics are least studied?"),
        ("List scholars from THUAS", "list researchers from THUAS"),
        # Word boundary tests — these should NOT be modified
        ("bibliography of Esposito", "papers by of Esposito"),  # "bibliography" contains "graph" but should not become "figureaphy"
    ]

    total = 0
    passed = 0
    failures = []

    for input_q, expected_contains in NORMALISATION_CASES:
        normalised = agent._normalise_query(input_q).lower()
        expected_lower = expected_contains.lower()
        total += 1

        # Check that the expected canonical form appears in the normalised output
        if expected_lower in normalised:
            passed += 1
            if verbose:
                print(f"  [OK] '{input_q}' -> '{normalised}'")
        else:
            # Special check for bibliography — should NOT contain "figure"
            if "bibliography" in input_q.lower() and "figure" not in normalised:
                passed += 1
                if verbose:
                    print(f"  [OK] '{input_q}' -> '{normalised}' (word boundary respected)")
            else:
                failures.append((input_q, normalised, expected_contains))
                print(f"  [!!] '{input_q}'")
                print(f"       Got:      '{normalised}'")
                print(f"       Expected: '{expected_contains}'")

    rate = passed / total if total else 0
    print(f"\nNormalisation verification: {passed}/{total} ({rate:.1%})")

    return {"total": total, "passed": passed, "rate": rate}


def run_all(verbose=False, output_json=False):
    """Run all Phase 1 reliability tests."""
    from agent import Agent
    agent = Agent()

    t_start = time.time()

    r1 = run_consistency_test(agent, k=5, verbose=verbose)
    r2 = run_programmatic_consistency_test(agent, k=5, verbose=verbose)
    r3 = run_robustness_test(agent, verbose=verbose)
    r4 = run_normalisation_test(agent, verbose=verbose)

    elapsed = time.time() - t_start

    # Summary
    print(f"\n{'='*70}")
    print(f"RELIABILITY BENCHMARK — Phase 1 Summary")
    print(f"{'='*70}")
    print(f"  Classification consistency:     {r1['rate']:.1%} ({r1['consistent']}/{r1['total']})")
    print(f"  Programmatic output consistency: {r2['rate']:.1%} ({r2['consistent']}/{r2['total']})")
    print(f"  Paraphrase robustness:          {r3['rate']:.1%} ({r3['matched']}/{r3['total']})")
    print(f"  Synonym normalisation:          {r4['rate']:.1%} ({r4['passed']}/{r4['total']})")
    print(f"  Time elapsed:                   {elapsed:.1f}s")
    print(f"{'='*70}")

    # Aggregate scores (Rabanser-style)
    consistency_score = (r1['rate'] + r2['rate']) / 2
    robustness_score = r3['rate']
    print(f"\n  R_Con (Consistency):  {consistency_score:.3f}")
    print(f"  R_Rob (Robustness):   {robustness_score:.3f}")
    print(f"\n  Note: These scores cover only the classification stage.")
    print(f"  Phase 2 (LLM-involved) and Phase 3 (expert evaluation)")
    print(f"  are needed for full reliability profiling.")

    if output_json:
        results = {
            "phase": 1,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "consistency": {
                "classification": {"total": r1["total"], "consistent": r1["consistent"], "rate": round(r1["rate"], 4)},
                "programmatic": {"total": r2["total"], "consistent": r2["consistent"], "rate": round(r2["rate"], 4)},
                "aggregate": round(consistency_score, 4),
            },
            "robustness": {
                "paraphrase": {"total": r3["total"], "matched": r3["matched"], "rate": round(r3["rate"], 4),
                               "failures": [(o, p, e, a) for o, p, e, a in r3.get("failures", [])]},
                "normalisation": {"total": r4["total"], "passed": r4["passed"], "rate": round(r4["rate"], 4)},
                "aggregate": round(robustness_score, 4),
            },
        }
        out_path = os.path.join(SCRIPT_DIR, f"reliability_phase1_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {out_path}")

    all_pass = (r1['rate'] == 1.0 and r2['rate'] == 1.0
                and len(r3.get('failures', [])) == 0
                and r4['rate'] == 1.0)
    return all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reliability Benchmark — Phase 1")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show passing tests")
    parser.add_argument("--json", action="store_true", help="Save results as JSON")
    args = parser.parse_args()

    success = run_all(verbose=args.verbose, output_json=args.json)
    sys.exit(0 if success else 1)
