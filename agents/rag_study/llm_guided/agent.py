"""
RAG Study — Variant 5: LLM-Guided Paths

The LLM classifies the query type, then code executes the appropriate
response path — same paths as the Procedural variant (Variant 4), but
the routing decision is made by the LLM instead of pattern matching.

This tests whether LLM classification can match or surpass human-designed
pattern matching, while keeping the same data access and formatting.

Architecture:
  1. Perception: receive query
  2. Reasoning: LLM classifies → returns query_type + extracted entities
  3. Action: code dispatches to the appropriate data function
  4. Production: same formatting and cues as Procedural
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin


# Classification prompt sent to the LLM
CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Given the user's query, classify it into exactly ONE of these categories and extract relevant entities.

CATEGORIES:
- meta: Questions about the agent itself ("What can you do?", "How does this work?", "What is UNINOVIS?")
- non_research: Requests for essays, translations, recipes, flights, weather, sports results
- figure: Requests containing "figure" or "map" for data visualisation
- project: Questions about specific research projects or grants (e.g. "What is the TAILOR project?")
- researcher: Questions about a specific person's publications or research interests
- glossary: Conceptual "What is X?" questions about Responsible AI terms (explainable AI, fairness, EU AI Act, etc.)
- gap: Questions about topics NOT studied, research gaps, missing areas
- topic_search: Requests for papers on a specific research topic
- university_papers: Requests for all papers or researchers from a specific university
- off_topic: Questions clearly outside Responsible AI (cooking, sports, general knowledge)
- followup: Short follow-ups referring to previous context ("tell me more", "expand on that")
- general: Any other Responsible AI question that doesn't fit the above

UNIVERSITIES (use these acronyms): UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

Respond with ONLY a JSON object, no explanation:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "..."}

- Fill only the relevant fields. Use empty string "" for fields that don't apply.
- For "topic": extract the research topic if mentioned (e.g. "AI ethics", "explainable AI")
- For "researcher": extract the person's name if mentioned
- For "university": extract the university acronym if mentioned
- For "project": extract the project name if mentioned

USER QUERY: {query}"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """LLM classifies the query, then code executes the response path."""
    _AGENT_FILE = __file__

    def _llm_classify(self, query: str) -> dict:
        """Ask the LLM to classify the query. Returns parsed JSON."""
        prompt = CLASSIFY_PROMPT.replace("{query}", query)
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
            )
            text = response.choices[0].message.content.strip()
            # Extract JSON from response (handle markdown code blocks)
            if "```" in text:
                text = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
                text = text.group(1).strip() if text else "{}"
            return json.loads(text)
        except Exception as e:
            print(f"[LLM_GUIDED] Classification error: {e}")
            return {"category": "general"}

    def _dispatch(self, classification: dict, user_message: str, history: list = None, **kwargs):
        """Dispatch to the appropriate response path based on LLM classification."""
        cat = classification.get("category", "general")
        topic = classification.get("topic", "")
        researcher = classification.get("researcher", "")
        university = classification.get("university", "")
        project_name = classification.get("project", "")

        # --- Programmatic paths (no LLM needed for response) ---

        if cat == "meta":
            return self._build_meta_response()

        if cat == "non_research":
            research_topic = self._config.get("research_topic", "Responsible AI")
            return (
                f"I am a research assistant specialised in **{research_topic}**. "
                f"I can help you search papers, researchers, and projects within this domain, "
                f"but I cannot perform this type of task."
            )

        if cat == "off_topic":
            research_topic = self._config.get("research_topic", "Responsible AI")
            scope_terms = self._config.get("extra_scope_terms", [])[:6]
            response = f"This question is outside my scope. I specialise in **{research_topic}**."
            if scope_terms:
                response += f"\n\nTopics I can help with include: {', '.join(scope_terms)}."
            return response

        if cat == "figure":
            agent_id = self._config.get("agent_id", "")
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
                return self._format_glossary_response(glossary_ctx)

        # --- LLM paths (need LLM for response generation) ---
        # Fall through to standard RAG for: topic_search, university_papers,
        # gap, followup, general, and any failed programmatic lookups
        return None  # signals caller to use LLM

    def _build_meta_response(self) -> str:
        """Build a programmatic meta-question response."""
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

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: LLM classifies the query
        classification = self._llm_classify(user_message)
        print(f"[LLM_GUIDED] Classification: {classification}")

        # Step 2: Try programmatic dispatch
        result = self._dispatch(classification, user_message, history, **kwargs)
        if result is not None:
            return result

        # Step 3: Fall through to LLM with RAG context
        user_msg = self._normalise_query(user_message)
        context = self._retrieve_context(user_message)

        # Build context with metadata if available
        cat = classification.get("category", "general")
        extra_ctx = ""
        if cat == "topic_search":
            topic_ctx = self._build_topic_context(user_msg)
            if topic_ctx:
                extra_ctx = topic_ctx
        elif cat == "university_papers":
            uni_ctx = self._build_university_papers_context(user_msg)
            if uni_ctx:
                extra_ctx = uni_ctx
        elif cat == "gap":
            metadata_ctx = self._build_metadata_context()
            if metadata_ctx:
                extra_ctx = metadata_ctx

        system = self._build_system_prompt()
        if context:
            system += f"\n\n--- Retrieved Context ---\n{context}"
        if extra_ctx:
            system += f"\n\n--- Structured Data ---\n{extra_ctx}"

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        return response.choices[0].message.content

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        yield ("status", "Classifying query...")

        # Step 1: LLM classifies
        classification = self._llm_classify(user_message)
        print(f"[LLM_GUIDED] Classification: {classification}")

        # Step 2: Try programmatic dispatch
        result = self._dispatch(classification, user_message, history, **kwargs)
        if result is not None:
            yield result
            return

        yield ("status", "Searching...")

        # Step 3: LLM with RAG context
        user_msg = self._normalise_query(user_message)
        context = self._retrieve_context(user_message)

        cat = classification.get("category", "general")
        extra_ctx = ""
        if cat == "topic_search":
            topic_ctx = self._build_topic_context(user_msg)
            if topic_ctx:
                extra_ctx = topic_ctx
        elif cat == "university_papers":
            uni_ctx = self._build_university_papers_context(user_msg)
            if uni_ctx:
                extra_ctx = uni_ctx
        elif cat == "gap":
            metadata_ctx = self._build_metadata_context()
            if metadata_ctx:
                extra_ctx = metadata_ctx

        system = self._build_system_prompt()
        if context:
            system += f"\n\n--- Retrieved Context ---\n{context}"
        if extra_ctx:
            system += f"\n\n--- Structured Data ---\n{extra_ctx}"

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048, stream=True)
        for chunk in response:
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content
