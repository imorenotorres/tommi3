#!/usr/bin/env python3
"""
Remap old 12-class flat taxonomy to new 8-class layered taxonomy.

Old classes (12): meta, non_research, off_topic, figure, followup, gap,
                  general, glossary, topic_search, papers, project, researcher

New Layer 1 — Content intent (8):
  papers, researcher, project, topic, glossary, organization, meta, out_of_scope

New Layer 2 — Turn type: initial, follow_up
New Layer 3 — Output format: text, figure, table

Migration rules:
  non_research + off_topic  → out_of_scope
  topic_search + gap        → topic
  meta (agent)              → meta
  meta (UNINOVIS/alliance)  → organization
  figure                    → content-based + output_format: figure
  followup                  → content unknown + turn_type: follow_up
  general                   → case-by-case (glossary / topic / out_of_scope)
  glossary/papers/project/researcher → unchanged
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Per-query overrides for ambiguous cases ──────────────────────────────────

# Keyed by query text (exact match). Value = new content intent.
# Only needed where automatic rules don't apply.

META_TO_ORGANIZATION = {
    # These ask about UNINOVIS/institutions, not the agent
    "How many universities participate in UNINOVIS?",
    "Which countries are represented in UNINOVIS?",
    "UNINOVIS info",
    "tell me everything about uninovis and the universities involved",
    "UNINOVIS — how many partners and from where?",
}

# Figure queries → content intent (output_format will be "figure")
FIGURE_CONTENT_MAP = {
    "Show me a visualisation of publications per year": "papers",
    "I want to see a graph showing collaboration patterns": "papers",
    "Can you plot the distribution of papers across universities?": "papers",
    "Generate a bar chart of research output by partner": "papers",
    "Map the research projects geographically": "project",
    "Display a timeline of publications": "papers",
    "Show me how many papers each university has published": "papers",
    "Visualise the network of co-authored papers": "papers",
    "publications by year as a line chart": "papers",
    "could I see some kind of visual breakdown?": "meta",  # asking about capabilities
    "give me a pie chart of papers per country": "papers",
    "can you show the data graphically?": "meta",  # asking about capabilities
    "I'd love to see a heatmap of collaborations between universities": "papers",
    "Is there a way to visualise which topics each university works on?": "topic",
    "Make a kind of diagram showing research areas?": "topic",
    "Give me something visual about the partnerships": "organization",
    "Plot whatever data you have — surprise me": "meta",  # asking about capabilities
    "I want to see numbers, not text — show me a dashboard": "meta",  # asking about capabilities
}

# General queries → case-by-case
GENERAL_REMAP = {
    "Create a table comparing AI frameworks": "out_of_scope",  # task request
    "What's the difference between AI safety and AI alignment?": "glossary",
    "Do you think AI will replace human workers?": "out_of_scope",  # opinion
    "How does responsible AI relate to sustainability?": "topic",
    "What are the main challenges in AI ethics today?": "topic",
    "Is regulation enough to make AI safe?": "out_of_scope",  # opinion
    "What role does education play in responsible AI?": "topic",
    "Can we ever fully trust AI systems?": "out_of_scope",  # opinion
    "What is the future of AI governance?": "topic",
    "How should AI be taught in universities?": "out_of_scope",  # opinion
    "Are current AI models biased?": "topic",
    "What makes an AI system trustworthy?": "glossary",
    "Should AI have rights?": "out_of_scope",  # opinion
    "How do we measure fairness in AI?": "topic",
    "why is AI ethics important?": "topic",
    "is there any consensus on what trustworthy AI means?": "glossary",
    "what's the deal with AI and jobs?": "out_of_scope",  # not about research
    "do LLMs have biases?": "topic",
    "how worried should we be about AI?": "out_of_scope",  # opinion
    "can AI systems be held legally responsible for their decisions?": "topic",
    "Is it possible to build an AI system that is both fair and accurate?": "topic",
    "What would a responsible AI curriculum look like at the university level?": "out_of_scope",  # task
    "How do different cultures approach the question of AI ethics?": "topic",
    "Is there a trade-off between explainability and performance in ML models?": "topic",
}


def remap_query(entry: dict) -> dict:
    """Remap a single query entry to the new taxonomy."""
    old_cat = entry["expected"]
    query = entry["query"]
    new = dict(entry)  # copy

    # Layer 2 — Turn type
    turn_type = "initial"
    output_format = "text"

    # ── Automatic mappings ──

    if old_cat == "non_research":
        new["expected"] = "out_of_scope"

    elif old_cat == "off_topic":
        new["expected"] = "out_of_scope"

    elif old_cat == "topic_search":
        new["expected"] = "topic"

    elif old_cat == "gap":
        new["expected"] = "topic"
        new["facet"] = "gap"

    elif old_cat == "followup":
        turn_type = "follow_up"
        new["expected"] = "_follow_up"  # Can't determine content without context
        new["_layer2_only"] = True

    elif old_cat == "figure":
        output_format = "figure"
        if query in FIGURE_CONTENT_MAP:
            new["expected"] = FIGURE_CONTENT_MAP[query]
        else:
            new["expected"] = "papers"  # default for figure queries

    elif old_cat == "meta":
        if query in META_TO_ORGANIZATION:
            new["expected"] = "organization"
        else:
            new["expected"] = "meta"

    elif old_cat == "general":
        if query in GENERAL_REMAP:
            new["expected"] = GENERAL_REMAP[query]
        else:
            new["expected"] = "topic"  # default for unmatched general

    elif old_cat in ("glossary", "papers", "project", "researcher"):
        pass  # unchanged

    else:
        print(f"WARNING: unknown old category '{old_cat}' for: {query}")

    # Add layer metadata
    new["turn_type"] = turn_type
    new["output_format"] = output_format
    new["_old_category"] = old_cat

    return new


def remap_file(input_path: str, output_path: str):
    with open(input_path) as f:
        data = json.load(f)

    queries = data["queries"]
    remapped = [remap_query(q) for q in queries]

    # Count changes
    changes = []
    for old, new in zip(queries, remapped):
        if old["expected"] != new["expected"]:
            changes.append({
                "query": old["query"],
                "old": old["expected"],
                "new": new["expected"],
            })

    # Separate follow-up queries
    content_queries = [q for q in remapped if not q.get("_layer2_only")]
    followup_queries = [q for q in remapped if q.get("_layer2_only")]

    # Stats
    from collections import Counter
    old_cats = Counter(q["expected"] for q in queries)
    new_cats = Counter(q["expected"] for q in content_queries)

    print(f"\nRemapped {len(queries)} queries → {len(content_queries)} content + {len(followup_queries)} follow-up")
    print(f"\nOld distribution:")
    for cat, n in sorted(old_cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")
    print(f"\nNew content distribution:")
    for cat, n in sorted(new_cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")
    print(f"\n{len(changes)} queries changed category")

    # Build output
    new_data = {
        "_description": (
            f"Revised evaluation set with 8-class content taxonomy. "
            f"{len(content_queries)} content queries + {len(followup_queries)} follow-up queries (Layer 2 only). "
            f"Remapped from 12-class flat taxonomy on 2026-09-10."
        ),
        "_taxonomy": {
            "layer1_content": {
                "papers": "Queries whose primary object is a set of publications",
                "researcher": "Queries about specific researchers",
                "project": "Queries about named research projects",
                "topic": "Queries that survey a research subject area (incl. gaps)",
                "glossary": "Definitional queries about a single concept or term",
                "organization": "Factual queries about UNINOVIS or member institutions",
                "meta": "Queries about the agent itself, its data sources or capabilities",
                "out_of_scope": "Anything not answerable by this agent",
            },
            "layer2_turn_type": {
                "initial": "Self-contained first query",
                "follow_up": "References or revises a previous answer",
            },
            "layer3_output_format": {
                "text": "Default prose answer",
                "figure": "Chart, graph, map, or other visualisation",
                "table": "Tabular comparison or listing",
            },
        },
        "_tiers": {
            "tier1": "Standard phrasings - typical user queries",
            "tier2": "Unusual phrasings - informal, verbose, telegraphic, indirect",
            "tier3": "Adversarial - ambiguous, compound, edge cases, near-misses",
        },
        "_migration_notes": [
            "non_research + off_topic → out_of_scope",
            "topic_search + gap → topic (gap queries retain facet='gap')",
            "figure → reclassified by content intent + output_format='figure'",
            "followup → excluded from content accuracy (Layer 2 only)",
            "general → case-by-case: glossary (definitional) / topic (survey) / out_of_scope (opinion/task)",
            "meta → split: agent-related stays meta, UNINOVIS/institution → organization",
        ],
        "_changes": changes,
        "queries": remapped,
    }

    with open(output_path, "w") as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    # Remap evaluation set
    remap_file(
        os.path.join(SCRIPT_DIR, "evaluation_set_extended_revised.json"),
        os.path.join(SCRIPT_DIR, "evaluation_set_8class.json"),
    )
