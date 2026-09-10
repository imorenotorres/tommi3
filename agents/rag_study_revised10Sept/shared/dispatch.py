"""
Shared dispatch logic for Rule-based and LLM-based agents.
8-class layered taxonomy (revised 10 Sept 2026).

Both agents use identical response paths — the only difference is
how the classification dict is produced. This module is the controlled
variable: given the same classification, both agents produce identical output.

Classification dict format:
  {"category": str, "topic": str, "researcher": str, "university": str,
   "project": str, "output_format": str}

Layer 1 — Content intent (8 classes):
  papers, researcher, project, topic, glossary, organization, meta, out_of_scope

Layer 2 — Turn type: initial, follow_up
Layer 3 — Output format: text, figure, table
"""

import os
import re
import json

# ── All Layer 1 categories ────────────────────────────────────────────────

ALL_CATEGORIES = [
    "papers", "researcher", "project", "topic",
    "glossary", "organization", "meta", "out_of_scope",
]


# ── Decision trace ────────────────────────────────────────────────────────

def build_trace(classification: dict, action: str, production: str,
                reasoning_label: str = "Classification") -> str:
    """Build a collapsible decision trace (Perception -> Reasoning -> Action -> Production)."""
    cat = classification.get("category", "out_of_scope")
    topic = classification.get("topic", "")
    researcher = classification.get("researcher", "")
    university = classification.get("university", "")
    project = classification.get("project", "")
    output_format = classification.get("output_format", "text")

    lines = []
    lines.append('<details class="decision-trace" style="margin-top:8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;font-size:12px;">')
    lines.append('<summary style="padding:6px 10px;cursor:pointer;font-weight:600;color:#64748b;">Decision Trace</summary>')
    lines.append('<div style="padding:8px 10px;">')

    query_preview = classification.get("_query", "")[:120]
    lines.append(f'<div style="margin-bottom:6px;"><span style="color:#0284c7;font-weight:600;">Perception:</span> {query_preview}</div>')

    lines.append(f'<div style="margin-bottom:6px;"><span style="color:#d97706;font-weight:600;">Reasoning ({reasoning_label}):</span></div>')
    lines.append('<div style="margin-left:12px;">')
    for c in ALL_CATEGORIES:
        if c == cat:
            entities = []
            if topic: entities.append(f'topic="{topic}"')
            if researcher: entities.append(f'researcher="{researcher}"')
            if university: entities.append(f'university={university}')
            if project: entities.append(f'project="{project}"')
            if output_format != "text": entities.append(f'format={output_format}')
            detail = f' — <span style="color:#64748b;">{", ".join(entities)}</span>' if entities else ""
            lines.append(f'<div style="color:#16a34a;font-weight:600;">✓ {c}{detail}</div>')
        else:
            lines.append(f'<div style="color:#94a3b8;">✗ {c}</div>')
    lines.append('</div>')

    lines.append(f'<div style="margin-bottom:6px;"><span style="color:#16a34a;font-weight:600;">Action:</span> {action}</div>')
    lines.append(f'<div><span style="color:#9333ea;font-weight:600;">Production:</span> {production}</div>')

    lines.append('</div></details>')
    return '\n'.join(lines)


# ── Programmatic responses ────────────────────────────────────────────────

def build_meta_response(config: dict) -> str:
    """Build a programmatic meta-question response from config."""
    research_topic = config.get("research_topic", "Responsible AI")
    alliance = config.get("alliance", {}).get("name", "UNINOVIS")
    return (
        f"I am a research assistant for the **{alliance}** Excellence Hub on **{research_topic}**.\n\n"
        f"I can help you with:\n"
        f"- Search **research papers** by topic, university, or researcher\n"
        f"- Look up **researchers** and their publications\n"
        f"- Explore **funded research projects**\n"
        f"- Answer **conceptual questions** about Responsible AI (from the glossary)\n"
        f"- Show **interactive maps and figures** of research output\n"
        f"- Analyse **research gaps** in the database\n\n"
        f"Ask me anything about Responsible AI research in {alliance}!"
    )


def build_organization_response(config: dict) -> str:
    """Build a programmatic response about the alliance/organization."""
    alliance = config.get("alliance", {})
    name = alliance.get("name", "UNINOVIS")
    description = alliance.get("description", "")
    unis = config.get("universities", {})
    uni_list = "\n".join(f"- **{acr}** — {info.get('name', acr)} ({info.get('country', '')})"
                         for acr, info in unis.items())
    return (
        f"**{name}**\n\n"
        f"{description}\n\n"
        f"Partner universities ({len(unis)}):\n{uni_list}"
    )


def build_out_of_scope_response(config: dict) -> str:
    """Build a programmatic refusal for out-of-scope queries."""
    research_topic = config.get("research_topic", "Responsible AI")
    return (
        f"I am a research assistant specialised in **{research_topic}**. "
        f"I can help you search papers, researchers, and projects within this domain, "
        f"but this query is outside my scope."
    )


# ── Main dispatch ─────────────────────────────────────────────────────────

def dispatch(agent, classification: dict, user_message: str,
             reasoning_label: str = "Classification"):
    """
    Dispatch to the appropriate response path based on classification.

    Returns (response_text, trace_html) for programmatic paths,
    or (None, trace_html) when the query should fall through to the LLM.
    """
    cat = classification.get("category", "out_of_scope")
    classification["_query"] = user_message

    if cat == "meta":
        trace = build_trace(classification, "Built from config.json",
                           "Programmatic response (no LLM)", reasoning_label)
        return build_meta_response(agent._config), trace

    if cat == "organization":
        trace = build_trace(classification, "Built from config.json universities",
                           "Programmatic response (no LLM)", reasoning_label)
        return build_organization_response(agent._config), trace

    if cat == "out_of_scope":
        trace = build_trace(classification, "Fixed refusal message",
                           "Programmatic refusal (no LLM)", reasoning_label)
        return build_out_of_scope_response(agent._config), trace

    if cat == "project":
        ctx = agent._build_project_context(user_message)
        if ctx:
            trace = build_trace(classification, "Formatted from project_docs/",
                               "Programmatic response (no LLM)", reasoning_label)
            return agent._format_project_response(ctx), trace

    if cat == "researcher":
        ctx = agent._build_researcher_context(user_message)
        if ctx:
            trace = build_trace(classification, "Formatted from researchers.json",
                               "Programmatic response (no LLM)", reasoning_label)
            return agent._format_researcher_response(ctx), trace

    if cat == "glossary":
        glossary_ctx = agent._build_glossary_context(user_message)
        if glossary_ctx:
            trace = build_trace(classification, "Formatted from Glossary.md",
                               "Programmatic glossary response (no LLM)", reasoning_label)
            return agent._format_glossary_response(user_message, glossary_ctx), trace

    # Check if this is a figure request (Layer 3)
    output_format = classification.get("output_format", "text")
    if output_format == "figure":
        agent_id = agent._config.get("agent_id", "")
        trace = build_trace(classification, "Map link from query extraction",
                           "Interactive map (no LLM)", reasoning_label)
        if hasattr(agent, '_generate_map_link_programmatic'):
            return agent._generate_map_link_programmatic(user_message, agent_id), trace
        return "Figure generation is not available in this variant.", trace

    # --- LLM paths (papers, topic, and fallback) ---
    trace = build_trace(classification, "LLM generates response with RAG context",
                       "LLM response + post-processing", reasoning_label)
    return None, trace


def build_llm_context(agent, classification: dict, user_message: str) -> str:
    """Build system prompt + context for LLM fallback paths."""
    cat = classification.get("category", "out_of_scope")

    # Use synonym-expanded query for context retrieval if available
    if hasattr(agent, '_normalise_query'):
        user_msg = agent._normalise_query(user_message)
    else:
        user_msg = user_message

    context = agent._retrieve_context(user_message)

    extra_ctx = ""
    if cat == "topic":
        # Covers both topic_search and gap queries
        if hasattr(agent, '_build_topic_context'):
            topic_ctx = agent._build_topic_context(user_msg)
            if topic_ctx:
                extra_ctx = topic_ctx
        # Also check for gap-specific metadata
        if hasattr(agent, '_build_metadata_context'):
            metadata_ctx = agent._build_metadata_context()
            if metadata_ctx:
                extra_ctx = (extra_ctx + "\n\n" + metadata_ctx) if extra_ctx else metadata_ctx
    elif cat == "papers":
        if hasattr(agent, '_build_university_papers_context'):
            uni_ctx = agent._build_university_papers_context(user_msg)
            if uni_ctx:
                extra_ctx = uni_ctx

    system = agent._build_system_prompt()
    if context:
        system += f"\n\n--- Retrieved Context ---\n{context}"
    if extra_ctx:
        system += f"\n\n--- Structured Data ---\n{extra_ctx}"

    return system
