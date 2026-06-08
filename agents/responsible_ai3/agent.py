"""
EH: Responsible AI — LLM-Classified RAG Agent

Uses LLM-based query classification (non-deterministic) to route queries
to programmatic response paths or LLM fallback with targeted context.

Based on findings from the RAG Architecture Reliability Study:
LLM classification achieves higher robustness (R_Rob = 0.922) and safety
(R_Saf = 0.936) than rule-based classification, with minimal consistency
cost (C_traj = 97.4%).
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin

# ── Classification prompt ──────────────────────────────────────────────────

CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Given the user's query, classify it into exactly ONE of these categories and extract relevant entities.

CATEGORIES (in priority order — use the FIRST matching category):
- researcher: Questions about a specific PERSON's publications or research interests. Must mention a person's name. If a query mentions a person's name, it is ALWAYS researcher.
- topic_search: Requests for PAPERS or PUBLICATIONS on a specific research topic (NOT projects)
- papers: Requests for papers or researchers from a specific university (must mention a university name or acronym). Use ONLY when no specific topic is mentioned.
- project: Questions mentioning specific research PROJECTS or grants, OR asking to LIST research projects.
- glossary: Conceptual "What is X?" questions ONLY about well-defined Responsible AI terms (explainable AI, fairness, EU AI Act, trustworthy AI, AI bias, AI governance, etc.). Do NOT use for general/ambiguous questions.
- figure: Requests containing "figure", "map", "chart", "graph", or "visualise" for data visualisation
- meta: Questions about the agent itself ("What can you do?", "How does this work?", "What is UNINOVIS?", "Who are you?")
- non_research: Requests to PERFORM a task — write essays, translate, book flights, get recipes, report weather, sports results. Use this for ANY action request, even if the topic seems off-topic.
- off_topic: Questions clearly outside Responsible AI AND not task requests. Also for vague, meaningless, or greeting-like inputs.
- followup: Short follow-ups referring to previous context ("tell me more", "expand on that")
- gap: Questions about topics NOT studied, research gaps, missing areas, underexplored subtopics
- general: Broad or ambiguous AI/technology questions that don't match a specific category above.

IMPORTANT DISTINCTIONS:
- non_research vs off_topic: DO something = non_research. KNOW something outside scope = off_topic.
- glossary vs general: Glossary only for well-defined RA terms. Broad AI questions = general.
- project vs topic_search: "project(s)" keyword = project. "papers/publications" = topic_search.
- topic_search vs papers: If a TOPIC is mentioned, use topic_search even if a university is also mentioned.

UNIVERSITIES: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

Respond with ONLY a JSON object:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "..."}
Fill only relevant fields. Use "" for fields that don't apply.

USER QUERY: {query}"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """LLM-classified RAG agent with programmatic response paths."""
    _AGENT_FILE = __file__

    def _llm_classify(self, query: str) -> dict:
        """Classify the query using a separate LLM call."""
        prompt = CLASSIFY_PROMPT.replace("{query}", query)
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = response.choices[0].message.content.strip()
            if "```" in text:
                match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
                text = match.group(1).strip() if match else text
            json_match = re.search(r'\{[^{}]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(text)
        except Exception as e:
            print(f"[LLM_CLASSIFY] Error: {e}")
            return {"category": "general"}

    # ── Programmatic responses ─────────────────────────────────────────────

    def _build_meta_response(self) -> str:
        research_topic = self._config.get("research_topic", "Responsible AI")
        alliance = self._config.get("alliance", {}).get("name", "UNINOVIS")
        unis = self._config.get("universities", {})
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

    def _build_non_research_response(self) -> str:
        research_topic = self._config.get("research_topic", "Responsible AI")
        return (
            f"I am a research assistant specialised in **{research_topic}**. "
            f"I can help you search papers, researchers, and projects within this domain, "
            f"but I cannot perform this type of task."
        )

    def _build_off_topic_response(self) -> str:
        research_topic = self._config.get("research_topic", "Responsible AI")
        scope_terms = self._config.get("extra_scope_terms", [])[:6]
        response = f"This question is outside my scope. I specialise in **{research_topic}**."
        if scope_terms:
            response += f"\n\nTopics I can help with include: {', '.join(scope_terms)}."
        return response

    # ── Dispatch ───────────────────────────────────────────────────────────

    def _dispatch(self, classification: dict, user_message: str):
        """Route to programmatic path or return None for LLM fallback."""
        cat = classification.get("category", "general")

        if cat == "meta":
            return self._build_meta_response()

        if cat == "non_research":
            return self._build_non_research_response()

        if cat == "off_topic":
            return self._build_off_topic_response()

        if cat == "figure":
            agent_id = self._config.get("agent_id", "")
            if hasattr(self, '_generate_map_link_programmatic'):
                return self._generate_map_link_programmatic(user_message, agent_id)

        if cat == "project":
            ctx = self._build_project_context(user_message)
            if ctx:
                return self._format_project_response(ctx)

        if cat == "researcher":
            ctx = self._build_researcher_context(user_message)
            if ctx:
                return self._format_researcher_response(ctx)

        if cat == "glossary":
            glossary_ctx = self._build_glossary_context(user_message)
            if glossary_ctx:
                return self._format_glossary_response(user_message, glossary_ctx)

        if cat == "topic_search":
            if hasattr(self, '_build_topic_factual_section'):
                result = self._build_topic_factual_section(user_message)
                if result:
                    return result

        return None  # LLM fallback

    def _build_llm_context(self, classification: dict, user_message: str) -> str:
        """Build system prompt + context for LLM fallback."""
        cat = classification.get("category", "general")

        if hasattr(self, '_normalise_query'):
            user_msg = self._normalise_query(user_message)
        else:
            user_msg = user_message

        context = self._retrieve_context(user_message)

        extra_ctx = ""
        if cat == "papers":
            if hasattr(self, '_build_university_papers_context'):
                uni_ctx = self._build_university_papers_context(user_msg)
                if uni_ctx:
                    extra_ctx = uni_ctx
        elif cat == "gap":
            if hasattr(self, '_build_metadata_context'):
                metadata_ctx = self._build_metadata_context()
                if metadata_ctx:
                    extra_ctx = metadata_ctx

        system = self._build_system_prompt()
        if context:
            system += f"\n\n--- Retrieved Context ---\n{context}"
        if extra_ctx:
            system += f"\n\n--- Structured Data ---\n{extra_ctx}"

        return system

    # ── Chat (synchronous) ─────────────────────────────────────────────────

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: LLM classification
        classification = self._llm_classify(user_message)

        # Step 2: Try programmatic dispatch
        result = self._dispatch(classification, user_message)
        if result is not None:
            # Post-processing (humility, sanitisation)
            result = self._sanitize_authority(result)
            return result

        # Step 3: LLM fallback with targeted context
        system = self._build_llm_context(classification, user_message)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        llm_content = response.choices[0].message.content

        # Post-processing
        llm_content = self._sanitize_authority(llm_content)
        if hasattr(self, '_verify_paper_references'):
            llm_content, _ = self._verify_paper_references(llm_content, system, "hidden")
        if hasattr(self, '_inject_paper_links'):
            llm_content = self._inject_paper_links(llm_content)

        return llm_content

    # ── Chat stream (async) ────────────────────────────────────────────────

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            init_msg = getattr(self, '_init_status_message', "Initializing...")
            yield ("status", init_msg)
            self._init_chromadb()

        yield ("status", "Classifying query...")

        # Step 1: LLM classification
        classification = self._llm_classify(user_message)
        cat = classification.get("category", "general")

        # Step 2: Try programmatic dispatch
        result = self._dispatch(classification, user_message)
        if result is not None:
            result = self._sanitize_authority(result)
            yield result

            # Decision trace (if crystal_box)
            if self._config.get("decision_trace") == "crystal_box":
                trace = self._build_decision_trace(classification, programmatic=True)
                yield ("trace", trace)
            return

        yield ("status", "Searching...")

        # Step 3: LLM fallback with targeted context
        system = self._build_llm_context(classification, user_message)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        full_response = ""
        async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                text = chunk.data.choices[0].delta.content
                full_response += text
                yield text

        # Post-processing
        processed = self._sanitize_authority(full_response)
        if hasattr(self, '_verify_paper_references'):
            processed, _ = self._verify_paper_references(processed, system, "hidden")
        if hasattr(self, '_inject_paper_links'):
            processed = self._inject_paper_links(processed)
        if processed != full_response:
            yield ("replace", processed)

        # Decision trace (if crystal_box)
        if self._config.get("decision_trace") == "crystal_box":
            trace = self._build_decision_trace(classification, programmatic=False)
            yield ("trace", trace)

        # Audit log
        if self._audit_enabled:
            from base.badges import AuditLogger
            AuditLogger.log(
                audit_path=self._audit_path,
                enabled=True,
                agent_id=self._config.get("agent_id", "unknown"),
                query=user_message,
                query_type=cat,
                breakdown={"source": "llm_classification", "category": cat},
                reliability_label=cat,
                transparency=self._transparency,
                prompt_level=self._prompt_level,
                model_name=self.model_display_name,
                is_local_llm=self._is_local_llm,
            )

    # ── Decision trace ─────────────────────────────────────────────────────

    def _build_decision_trace(self, classification: dict, programmatic: bool) -> str:
        cat = classification.get("category", "general")
        all_categories = [
            "researcher", "topic_search", "papers", "project",
            "glossary", "figure", "meta", "non_research", "off_topic",
            "followup", "gap", "general",
        ]

        lines = []
        lines.append('<details class="decision-trace" style="margin-top:8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;font-size:12px;">')
        lines.append('<summary style="padding:6px 10px;cursor:pointer;font-weight:600;color:#64748b;">Decision Trace</summary>')
        lines.append('<div style="padding:8px 10px;">')

        lines.append(f'<div style="margin-bottom:6px;"><span style="color:#d97706;font-weight:600;">Reasoning (LLM classification):</span></div>')
        lines.append('<div style="margin-left:12px;">')
        for c in all_categories:
            if c == cat:
                entities = []
                for key in ["topic", "researcher", "university", "project"]:
                    val = classification.get(key, "")
                    if val:
                        entities.append(f'{key}="{val}"')
                detail = f' — <span style="color:#64748b;">{", ".join(entities)}</span>' if entities else ""
                lines.append(f'<div style="color:#16a34a;font-weight:600;">✓ {c}{detail}</div>')
            else:
                lines.append(f'<div style="color:#94a3b8;">✗ {c}</div>')
        lines.append('</div>')

        action = "Programmatic response (no LLM)" if programmatic else "LLM generates response with context"
        lines.append(f'<div style="margin-top:6px;"><span style="color:#16a34a;font-weight:600;">Action:</span> {action}</div>')

        lines.append('</div></details>')
        return '\n'.join(lines)
