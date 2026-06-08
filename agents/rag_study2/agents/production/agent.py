"""
RAG Study — Production Rule-based Classification (Hand-crafted)

Uses MetadataRAGMixin's 13-step classification chain with ~60 synonym
mappings, developed over months of production use. Classification
patterns were added reactively — each time a user query failed, a
specific fix was added.

This represents what production engineering naturally produces.
"""

import os
import sys

# Add paths
_AGENT_DIR = os.path.dirname(os.path.realpath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(_AGENT_DIR))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "production rule-based (hand-crafted)"


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Hand-crafted code classification → shared dispatch."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify using MetadataRAGMixin's production classification chain.

        This is the 13-step chain with ~60 synonym mappings from _normalise_query(),
        accent-insensitive matching, and priority-ordered boolean checks.
        """
        user_msg = self._normalise_query(user_message)
        msg_lower = user_msg.lower()

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
            return {"category": "researcher"}

        # 7. Conceptual / glossary queries
        if self._is_conceptual_question(user_msg):
            glossary_ctx = self._build_glossary_context(user_msg)
            if glossary_ctx:
                return {"category": "glossary", "topic": ""}
            return {"category": "general", "topic": ""}

        # 8. Gap analysis
        if self._is_gap_analysis_query(user_msg):
            return {"category": "gap"}

        # 9. University-specific paper listing
        uni_ctx = self._build_university_papers_context(user_msg)
        if uni_ctx:
            return {"category": "papers"}

        # 10. Topic search
        topic_ctx = self._build_topic_context(user_msg)
        if topic_ctx:
            return {"category": "topic_search", "topic": ""}

        # 11. Off-topic (not in scope)
        if not self._is_in_topical_scope(user_msg):
            return {"category": "off_topic"}

        # 12. General (in scope but no specific path)
        return {"category": "general", "topic": ""}

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        classification = self._code_classify(user_message)

        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            return result + "\n\n" + trace

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

        classification = self._code_classify(user_message)

        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            yield result
            if trace:
                yield ("trace", trace)
            return

        yield ("status", "Searching...")

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
