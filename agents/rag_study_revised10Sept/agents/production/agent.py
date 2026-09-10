"""
RAG Study (8-class) — Production Rule-based Classification (Hand-crafted)

Uses MetadataRAGMixin's classification chain, developed over months of
production use. Classification patterns were added reactively — each time
a user query failed, a specific fix was added.

Output is remapped to the 8-class layered taxonomy:
  Layer 1: papers, researcher, project, topic, glossary, organization, meta, out_of_scope
  Layer 2: initial / follow_up
  Layer 3: text / figure / table

Remapping from internal 12-class to 8-class:
  non_research + off_topic -> out_of_scope
  topic_search + gap       -> topic
  meta (UNINOVIS queries)  -> organization
  figure                   -> papers + output_format: figure
  general (opinions/tasks) -> out_of_scope
  general (in-scope)       -> topic
  followup                 -> _follow_up (layer 2)
"""

import os
import sys
import re

# Add paths
_AGENT_DIR = os.path.dirname(os.path.realpath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(_AGENT_DIR))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "production rule-based (hand-crafted, 8-class remapped)"


def _remap_to_8class(classification: dict, user_message: str) -> dict:
    """Remap internal 12-class output to 8-class taxonomy."""
    cat = classification.get("category", "general")
    msg_lower = user_message.lower()
    result = dict(classification)

    if cat == "non_research":
        result["category"] = "out_of_scope"

    elif cat == "off_topic":
        result["category"] = "out_of_scope"

    elif cat == "topic_search":
        result["category"] = "topic"

    elif cat == "gap":
        result["category"] = "topic"
        result["facet"] = "gap"

    elif cat == "figure":
        result["category"] = "papers"
        result["output_format"] = "figure"

    elif cat == "followup":
        result["category"] = "_follow_up"

    elif cat == "meta":
        # Split: agent-related stays meta, UNINOVIS/institution -> organization
        if re.search(r'\buninovis\b', msg_lower) and re.search(
                r'\b(?:universit|partner|countr|member|how many|which)\b', msg_lower):
            result["category"] = "organization"
        elif re.search(r'\b(?:what is uninovis|about uninovis)\b', msg_lower):
            result["category"] = "organization"
        # else stays "meta"

    elif cat == "general":
        # Opinion/task questions -> out_of_scope
        if re.search(r'\b(?:should|is it ethical|can ai be|is ai)\b', msg_lower):
            result["category"] = "out_of_scope"
        elif re.search(r'\bwhat is a\b', msg_lower) and not re.search(
                r'\b(?:responsible|explainable|trustworthy|fairness|governance|eu ai act)\b', msg_lower):
            result["category"] = "out_of_scope"
        else:
            result["category"] = "topic"

    return result


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Hand-crafted code classification -> 8-class remap -> shared dispatch."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify using MetadataRAGMixin's production chain, then remap to 8-class."""
        user_msg = self._normalise_query(user_message)
        msg_lower = user_msg.lower()

        # Use the inherited production classification chain
        if self._is_meta_question(msg_lower):
            internal = {"category": "meta"}
        elif self._is_non_research_task(user_msg):
            internal = {"category": "non_research"}
        elif self._is_figure_request(user_msg):
            internal = {"category": "figure"}
        elif self._is_followup_query(user_msg):
            internal = {"category": "followup"}
        else:
            project_ctx = self._build_project_context(user_msg)
            if project_ctx:
                internal = {"category": "project"}
            elif self._query_mentions_researcher(user_msg):
                internal = {"category": "researcher"}
            elif self._is_conceptual_question(user_msg):
                glossary_ctx = self._build_glossary_context(user_msg)
                if glossary_ctx:
                    internal = {"category": "glossary", "topic": ""}
                else:
                    internal = {"category": "general", "topic": ""}
            elif self._is_gap_analysis_query(user_msg):
                internal = {"category": "gap"}
            else:
                uni_ctx = self._build_university_papers_context(user_msg)
                if uni_ctx:
                    internal = {"category": "papers"}
                else:
                    topic_ctx = self._build_topic_context(user_msg)
                    if topic_ctx:
                        internal = {"category": "topic_search", "topic": ""}
                    elif not self._is_in_topical_scope(user_msg):
                        internal = {"category": "off_topic"}
                    else:
                        internal = {"category": "general", "topic": ""}

        # Remap to 8-class
        return _remap_to_8class(internal, user_message)

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
