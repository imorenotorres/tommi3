"""
RAG Study — Variant 3: Procedural (Code Classification)

Deterministic code classification (pattern matching + synonym expansion)
followed by shared programmatic response paths.

Architecture:
  1. Perception: receive query
  2. Reasoning: code classifies via pattern matching (deterministic)
  3. Action: shared dispatch → programmatic response or LLM fallback
  4. Production: same paths as V4

The only difference with V4 is step 2: code patterns vs LLM classification.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from shared_dispatch import dispatch, build_llm_context

REASONING_LABEL = "code patterns"


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Code classification → shared dispatch with V4."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify query using the deterministic code classification chain.

        Maps MetadataRAGMixin's boolean checks to the shared category format.
        Uses synonym-expanded query for classification, original for entity extraction.
        """
        user_msg = self._normalise_query(user_message)
        msg_lower = user_msg.lower()

        # Priority-ordered classification (mirrors the 13-step chain)

        # 1. Meta questions
        if self._is_meta_question(msg_lower):
            return {"category": "meta"}

        # 2. Non-research tasks
        if self._is_non_research_task(user_msg):
            return {"category": "non_research"}

        # 3. Figure/map requests
        if self._is_figure_request(user_msg):
            return {"category": "figure"}

        # 4. Follow-up queries
        if self._is_followup_query(user_msg):
            return {"category": "followup"}

        # 5. Project queries
        project_ctx = self._build_project_context(user_msg)
        if project_ctx:
            return {"category": "project"}

        # 6. Researcher queries
        if self._query_mentions_researcher(user_msg):
            return {"category": "researcher", "researcher": self._extract_researcher_name(user_msg)}

        # 7. Conceptual / glossary queries
        if self._is_conceptual_question(user_msg):
            glossary_ctx = self._build_glossary_context(user_msg)
            if glossary_ctx:
                return {"category": "glossary", "topic": self._extract_topic(user_msg) or ""}
            # Conceptual but no glossary match — general LLM
            return {"category": "general", "topic": self._extract_topic(user_msg) or ""}

        # 8. Gap analysis
        if self._is_gap_analysis_query(user_msg):
            return {"category": "gap"}

        # 9. University-specific paper listing
        uni_ctx = self._build_university_papers_context(user_msg)
        if uni_ctx:
            return {"category": "university_papers"}

        # 10. Topic search
        topic_ctx = self._build_topic_context(user_msg)
        if topic_ctx:
            return {"category": "topic_search", "topic": self._extract_topic(user_msg) or ""}

        # 11. Off-topic (not in scope)
        if not self._is_in_topical_scope(user_msg):
            return {"category": "off_topic"}

        # 12. General (in scope but no specific path)
        return {"category": "general", "topic": self._extract_topic(user_msg) or ""}

    def _extract_researcher_name(self, user_message: str) -> str:
        """Extract researcher name from query (best effort)."""
        # Use the researcher context builder which already does name matching
        ctx = self._build_researcher_context(user_message)
        if ctx:
            # Try to extract name from context header
            import re
            match = re.search(r'Researcher:\s*(.+?)(?:\n|$)', ctx)
            if match:
                return match.group(1).strip()
        return ""

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: Code classification (deterministic)
        classification = self._code_classify(user_message)
        print(f"[PROCEDURAL] Classification: {classification}")

        # Step 2: Shared dispatch (identical to V4)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            return result + "\n\n" + trace

        # Step 3: LLM fallback (identical to V4)
        system = build_llm_context(self, classification, user_message)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        return response.choices[0].message.content + "\n\n" + trace

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        yield ("status", "Classifying query...")

        # Step 1: Code classification (deterministic)
        classification = self._code_classify(user_message)
        print(f"[PROCEDURAL] Classification: {classification}")

        # Step 2: Shared dispatch (identical to V4)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            yield result
            if trace:
                yield ("trace", trace)
            return

        yield ("status", "Searching...")

        # Step 3: LLM fallback (identical to V4)
        system = build_llm_context(self, classification, user_message)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content

        if trace:
            yield ("trace", trace)
