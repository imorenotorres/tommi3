"""
Decision Logic Benchmark — Tests the Reasoning stage classification
for the Responsible AI3 agent.

Runs each query through the classification chain and verifies
it is routed to the expected category. No LLM is called.

Usage:
    python3 decision_logic_test.py
    python3 decision_logic_test.py --verbose
"""

import os
import sys
import re
import json
import argparse

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(AGENT_DIR, ".."))
sys.path.insert(0, os.path.join(AGENT_DIR, "..", "..", "web"))
sys.path.insert(0, AGENT_DIR)
os.chdir(AGENT_DIR)
os.environ.setdefault("MISTRAL_API_KEY", "dummy")  # Not needed, LLM not called

# ---------------------------------------------------------------------------
# Test cases: (query, expected_classification)
#
# Expected classifications:
#   "meta"              - Meta-question (about the agent itself)
#   "non_research"      - Non-research task (essay, recipe, translation)
#   "disambiguation"    - Disambiguation follow-up (number reply)
#   "figure"            - Figure/map request
#   "web_expand"        - Web expansion
#   "followup"          - Follow-up query
#   "gap"               - Gap analysis
#   "off_topic"         - Off-topic (outside scope)
#   "conceptual_gloss"  - Conceptual with glossary match
#   "conceptual_no"     - Conceptual without glossary match
#   "project"           - Project query
#   "affiliation"       - Affiliation/researcher listing
#   "shared_topics"     - Shared topics between universities
#   "uni_papers"        - University paper listing
#   "topic_search"      - Topic search
#   "researcher"        - Researcher lookup
#   "rag"               - Fallback RAG retrieval
# ---------------------------------------------------------------------------

TEST_CASES = [
    # === Meta-questions (no LLM needed) ===
    ("What can you do?", "meta"),
    ("How does this work?", "meta"),
    ("What kind of questions can I ask you?", "meta"),
    ("What is UNINOVIS?", "meta"),
    ("Which universities are in UNINOVIS?", "meta"),
    ("Who are you?", "meta"),

    # === Non-research tasks (no LLM needed) ===
    ("Write me a summary of responsible AI for my essay", "non_research"),
    ("Write an essay for me about AI", "non_research"),
    ("What is the weather today?", "non_research"),
    ("Can you book me a flight?", "non_research"),
    ("Translate this text to French: 'Responsible AI is important'", "non_research"),
    ("Can you give me the recipe of Responsible AI Coffee?", "non_research"),
    ("Who won the last World Cup?", "non_research"),

    # === Figure/map requests (no LLM for data, only for link) ===
    ("Show a figure with all the publications per partner", "figure"),
    ("Show a figure of studies on the topic AI and Ethics", "figure"),
    ("Show a map with the number of research projects per partner", "figure"),
    ("Show a figure of the collaborations among the partners", "figure"),
    ("Show a figure of the collaborations in the year 2025", "figure"),
    ("Show a map of publications on trustworthy AI", "figure"),
    ("Show a figure of papers by year", "figure"),

    # === Gap analysis (LLM reasons about absence) ===
    ("What responsible AI topics have not been studied in UNINOVIS?", "gap"),
    ("Are there gaps in UNINOVIS research on AI regulation?", "gap"),
    ("Which responsible AI subtopics are least studied?", "gap"),
    ("What topics are underrepresented in the database?", "gap"),

    # === Conceptual questions (glossary) ===
    ("What is explainable AI?", "conceptual_gloss"),
    ("What is fairness in AI?", "conceptual_gloss"),
    ("What is the EU AI Act?", "conceptual_gloss"),
    ("What is AI red-teaming?", "conceptual_gloss"),
    ("What is trustworthy AI?", "conceptual_gloss"),
    ("What is the difference between interpretability and explainability?", "conceptual_gloss"),
    ("What is AI alignment?", "conceptual_gloss"),

    # === Conceptual questions (not in glossary) ===
    ("Explain predictive policing and its relation to responsible AI", "conceptual_gloss"),

    # === Project queries ===
    ("What is the TAILOR project about?", "project"),
    ("Describe the IntelliMan project", "project"),
    ("What does the DUCA project propose about data governance?", "project"),
    ("List research projects on trustworthy AI", "project"),

    # === Affiliation/researcher listing ===
    ("List all researchers from THUAS", "uni_papers"),  # uni_papers fires first (detects university)
    ("List researchers from the University of Tirana", "uni_papers"),  # same — affiliation needs keyword "researcher" + university

    # === Topic search ===
    ("List all papers from UDCLV on AI in healthcare", "uni_papers"),  # university detected first, topic filter applied within
    ("Papers about AI and privacy", "topic_search"),
    ("Research on AI in education within UNINOVIS", "topic_search"),
    ("Papers on AI ethics", "topic_search"),

    # === Researcher lookup ===
    ("Papers by Rubén González Vallejo", "researcher"),
    ("What has Fabrizio Esposito published?", "researcher"),
    ("What are the research interests of Frank-Michael Schleif?", "researcher"),
    ("Papers by Rubén González", "researcher"),

    # === Off-topic (in-scope words but genuinely off-topic) ===
    # Note: these are tricky — they may contain scope terms but the intent is off-topic.
    # Most off-topic queries without scope terms are caught by non_research first.

    # === Queries that should NOT be misclassified ===
    ("Is AI dangerous?", "conceptual_no"),
    ("Can AI be trusted?", "conceptual_no"),
    ("Can AI make decisions on its own?", "conceptual_no"),
    ("What is a language model?", "conceptual_no"),
    ("What are deepfakes?", "conceptual_no"),
    ("What is bias in AI? Can you give me an example?", "conceptual_gloss"),
    ("What does transparency mean in the context of AI?", "conceptual_gloss"),
    ("What is sustainable AI?", "conceptual_gloss"),
    ("What is AI governance?", "conceptual_gloss"),
    ("What is human-centred AI?", "conceptual_gloss"),
]


def classify_query(agent, query, history=None):
    """Run the classification chain on a query and return the classification.

    This simulates the Reasoning stage without calling the LLM.
    Returns a string matching the expected classification codes above.
    """
    msg = query
    msg_lower = msg.lower()

    # 1. Meta-question
    if agent._is_meta_question(msg_lower):
        return "meta"

    # 2. Non-research task
    if agent._is_non_research_task(msg):
        return "non_research"

    # 3. Disambiguation follow-up
    if hasattr(agent, '_disambiguation_candidates') and agent._disambiguation_candidates:
        if re.match(r'^\d+\.?$', msg.strip()):
            return "disambiguation"

    # 4. Figure/map request
    if agent._is_figure_request(msg):
        return "figure"

    # 5. Follow-up (needs history)
    if history and agent._is_followup_query(msg):
        return "followup"

    # 6. Gap analysis
    if agent._is_gap_analysis_query(msg):
        return "gap"

    # 7. Conceptual (checked BEFORE off-topic — a conceptual question is never off-topic)
    is_conceptual = agent._is_conceptual_question(msg)
    if is_conceptual:
        glossary_ctx = agent._build_glossary_context(msg)
        if glossary_ctx:
            return "conceptual_gloss"
        else:
            return "conceptual_no"

    # 8-14. Content query chain (checked BEFORE off-topic — these queries use agent features)
    # Check if researcher query (this blocks topic search)
    if agent._query_mentions_researcher(msg):
        researcher_ctx = agent._build_researcher_context(msg)
        if researcher_ctx:
            return "researcher"

    project_ctx = agent._build_project_context(msg)
    if project_ctx:
        return "project"

    # Affiliation checked before uni_papers — "list researchers from X" is an affiliation query
    affiliation_ctx = agent._build_affiliation_context(msg)
    if affiliation_ctx:
        return "affiliation"

    if agent._is_shared_topics_query(msg):
        shared_ctx = agent._build_shared_topics_context(msg)
        if shared_ctx:
            return "shared_topics"

    # Topic search before uni_papers — "papers from UDCLV on AI in healthcare" has a topic
    topic_ctx = agent._build_topic_context(msg)
    if topic_ctx:
        return "topic_search"

    uni_papers_ctx = agent._build_university_papers_context(msg)
    if uni_papers_ctx:
        return "uni_papers"

    # 15. Off-topic (only if nothing else matched)
    if not agent._is_in_topical_scope(msg):
        return "off_topic"

    # 16. Fallback
    return "rag"


def run_benchmark(verbose=False):
    """Run all test cases and report results."""
    from agent import Agent
    agent = Agent()

    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*70}")
    print(f"Decision Logic Benchmark — {len(TEST_CASES)} test cases")
    print(f"{'='*70}\n")

    for i, (query, expected) in enumerate(TEST_CASES, 1):
        try:
            actual = classify_query(agent, query)
            ok = (actual == expected)
            if ok:
                passed += 1
                if verbose:
                    print(f"  ✓ {i:3d}. [{actual:18s}] {query[:60]}")
            else:
                failed += 1
                errors.append((i, query, expected, actual))
                print(f"  ✗ {i:3d}. [{actual:18s}] {query[:60]}")
                print(f"         Expected: {expected}, Got: {actual}")
        except Exception as e:
            failed += 1
            errors.append((i, query, expected, f"ERROR: {e}"))
            print(f"  ✗ {i:3d}. [ERROR] {query[:60]}")
            print(f"         {e}")

    print(f"\n{'='*70}")
    print(f"Results: {passed}/{len(TEST_CASES)} passed, {failed} failed")
    print(f"{'='*70}")

    if errors:
        print(f"\nFailed cases:")
        for i, query, expected, actual in errors:
            print(f"  {i:3d}. Query: {query}")
            print(f"       Expected: {expected}")
            print(f"       Actual:   {actual}")
            print()

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decision Logic Benchmark")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show passing tests too")
    args = parser.parse_args()

    success = run_benchmark(verbose=args.verbose)
    sys.exit(0 if success else 1)
