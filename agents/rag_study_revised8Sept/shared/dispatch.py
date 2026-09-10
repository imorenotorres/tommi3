"""
Shared dispatch logic for Rule-based and LLM-based agents.

Both agents use identical response paths — the only difference is
how the classification dict is produced. This module is the controlled
variable: given the same classification, both agents produce identical output.

Classification dict format:
  {"category": str, "topic": str, "researcher": str, "university": str, "project": str}
"""

import os
import re
import json

# ── All categories ─────────────────────────────────────────────────────────

ALL_CATEGORIES = [
    "researcher", "topic_search", "papers", "project",
    "glossary", "figure", "meta", "non_research", "off_topic",
    "followup", "gap", "general",
]


# ── Decision trace ─────────────────────────────────────────────────────────

def build_trace(classification: dict, action: str, production: str,
                reasoning_label: str = "Classification") -> str:
    """Build a collapsible decision trace (Perception → Reasoning → Action → Production)."""
    cat = classification.get("category", "general")
    topic = classification.get("topic", "")
    researcher = classification.get("researcher", "")
    university = classification.get("university", "")
    project = classification.get("project", "")

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
            detail = f' — <span style="color:#64748b;">{", ".join(entities)}</span>' if entities else ""
            lines.append(f'<div style="color:#16a34a;font-weight:600;">✓ {c}{detail}</div>')
        else:
            lines.append(f'<div style="color:#94a3b8;">✗ {c}</div>')
    lines.append('</div>')

    lines.append(f'<div style="margin-bottom:6px;"><span style="color:#16a34a;font-weight:600;">Action:</span> {action}</div>')
    lines.append(f'<div><span style="color:#9333ea;font-weight:600;">Production:</span> {production}</div>')

    lines.append('</div></details>')
    return '\n'.join(lines)


# ── Programmatic responses ─────────────────────────────────────────────────

def build_meta_response(config: dict) -> str:
    """Build a programmatic meta-question response from config."""
    research_topic = config.get("research_topic", "Responsible AI")
    alliance = config.get("alliance", {}).get("name", "UNINOVIS")
    unis = config.get("universities", {})
    uni_list = ", ".join(f"**{acr}** ({info.get('name', acr)})" for acr, info in unis.items())
    return (
        f"I am a research assistant for the **{alliance}** Excellence Hub on **{research_topic}**.\n\n"
        f"I can help you with:\n"
        f"- Search **research papers** by topic, university, or researcher\n"
        f"- Look up **researchers** and their publications\n"
        f"- Explore **funded research projects**\n"
        f"- Answer **conceptual questions** about Responsible AI (from the glossary)\n"
        f"- Show **interactive maps and figures** of research output\n"
        f"- Analyse **research gaps** in the database\n\n"
        f"Partner universities: {uni_list}"
    )


def build_non_research_response(config: dict) -> str:
    """Build a programmatic refusal for non-research tasks."""
    research_topic = config.get("research_topic", "Responsible AI")
    return (
        f"I am a research assistant specialised in **{research_topic}**. "
        f"I can help you search papers, researchers, and projects within this domain, "
        f"but I cannot perform this type of task."
    )


def build_off_topic_response(config: dict) -> str:
    """Build a programmatic refusal for off-topic queries."""
    research_topic = config.get("research_topic", "Responsible AI")
    scope_terms = config.get("extra_scope_terms", [])[:6]
    response = f"This question is outside my scope. I specialise in **{research_topic}**."
    if scope_terms:
        response += f"\n\nTopics I can help with include: {', '.join(scope_terms)}."
    return response


# ── Main dispatch ──────────────────────────────────────────────────────────

def dispatch(agent, classification: dict, user_message: str,
             reasoning_label: str = "Classification"):
    """
    Dispatch to the appropriate response path based on classification.

    Returns (response_text, trace_html) for programmatic paths,
    or (None, trace_html) when the query should fall through to the LLM.
    """
    cat = classification.get("category", "general")
    classification["_query"] = user_message

    if cat == "meta":
        trace = build_trace(classification, "Built from config.json",
                           "Programmatic response (no LLM)", reasoning_label)
        return build_meta_response(agent._config), trace

    if cat == "non_research":
        trace = build_trace(classification, "Fixed refusal message",
                           "Programmatic refusal (no LLM)", reasoning_label)
        return build_non_research_response(agent._config), trace

    if cat == "off_topic":
        trace = build_trace(classification, "Scope refusal from config.json",
                           "Programmatic refusal (no LLM)", reasoning_label)
        return build_off_topic_response(agent._config), trace

    if cat == "figure":
        agent_id = agent._config.get("agent_id", "")
        trace = build_trace(classification, "Map link from query extraction",
                           "Interactive map (no LLM)", reasoning_label)
        if hasattr(agent, '_generate_map_link_programmatic'):
            return agent._generate_map_link_programmatic(user_message, agent_id), trace
        return "Figure generation is not available in this variant.", trace

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

    # --- LLM paths ---
    trace = build_trace(classification, "LLM generates response with RAG context",
                       "LLM response + post-processing", reasoning_label)
    return None, trace


def build_llm_context(agent, classification: dict, user_message: str) -> str:
    """Build system prompt + context for LLM fallback paths."""
    cat = classification.get("category", "general")

    # Use synonym-expanded query for context retrieval if available
    if hasattr(agent, '_normalise_query'):
        user_msg = agent._normalise_query(user_message)
    else:
        user_msg = user_message

    context = agent._retrieve_context(user_message)

    extra_ctx = ""
    if cat == "topic_search":
        if hasattr(agent, '_build_topic_context'):
            topic_ctx = agent._build_topic_context(user_msg)
            if topic_ctx:
                extra_ctx = topic_ctx
    elif cat == "papers":
        if hasattr(agent, '_build_university_papers_context'):
            uni_ctx = agent._build_university_papers_context(user_msg)
            if uni_ctx:
                extra_ctx = uni_ctx
    elif cat == "gap":
        if hasattr(agent, '_build_metadata_context'):
            metadata_ctx = agent._build_metadata_context()
            if metadata_ctx:
                extra_ctx = metadata_ctx

    system = agent._build_system_prompt()
    if context:
        system += f"\n\n--- Retrieved Context ---\n{context}"
    if extra_ctx:
        system += f"\n\n--- Structured Data ---\n{extra_ctx}"

    return system
