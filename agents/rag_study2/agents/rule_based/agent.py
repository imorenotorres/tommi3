"""
RAG Study — Rule-based Classification (Deterministic)

Deterministic classification using pattern matching, followed by
shared programmatic response paths.

Architecture:
  1. Perception: receive query
  2. Reasoning: code classifies via pattern matching (deterministic)
  3. Action: shared dispatch → programmatic response or LLM fallback
  4. Production: same paths as LLM-based variant
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

REASONING_LABEL = "rule-based patterns"


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Rule-based classification → shared dispatch."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify query using deterministic pattern matching.

        Initial classifier built from expert_input.md Phase A.
        Patterns are priority-ordered: first match wins.
        """
        msg = user_message.strip()
        msg_lower = msg.lower()

        # 1. META — questions about the agent or UNINOVIS
        meta_patterns = [
            r'\bwhat can you do\b', r'\bwho are you\b', r'\bhow does this work\b',
            r'\bwhat.*(?:your|you).*(?:capabilit|functionalit|feature|do)\b',
            r'\bwhat is uninovis\b', r'\bwhat.*uninovis\b.*(?:about|is)\b',
            r'\bwhich.*universit\w*\b.*\buninovis\b', r'\buninovis.*universit\b',
            r'\buninovis.*partner\b', r'\bpartner.*universit\b',
            r'\btell me (?:about\s+)?(?:your|the\s+uninovis)\b',
            r'\b(?:your|you)\b.*\bfunctionalit\b',
            r'\bfunctionalit\w*\b.*\b(?:you|your|offer)\b',
        ]
        if any(re.search(p, msg_lower) for p in meta_patterns):
            return {"category": "meta"}

        # 2. NON-RESEARCH — task requests
        non_research_patterns = [
            r'\b(?:write|compose|draft)\s+(?:me\s+)?(?:an?\s+)?(?:essay|report|summary|paper)\b',
            r'\b(?:book|reserve)\s+(?:me\s+)?(?:a\s+)?(?:flight|hotel|ticket)\b',
            r'\btranslat\w*\b',
            r'\bwhat is the weather\b', r'\bweather today\b',
            r'\bwho won\b.*(?:world cup|championship|election)\b',
            r'\bworld cup winner\b',
            r'\brecipe\b',
            r'\b(?:cook|bake|prepare)\b.*\b(?:food|cake|coffee|meal)\b',
            r'\bhelp me (?:write|draft)\b',
        ]
        if any(re.search(p, msg_lower) for p in non_research_patterns):
            return {"category": "non_research"}

        # 3. FIGURE/MAP — visualisation requests
        figure_patterns = [
            r'\b(?:show|display|create|generate)\s+(?:a\s+)?(?:figure|map|chart|graph|diagram)\b',
            r'\bvisuali[sz]e\b', r'\bplot\b.*(?:paper|publication|collaboration)\b',
        ]
        if any(re.search(p, msg_lower) for p in figure_patterns):
            return {"category": "figure"}

        # 4. FOLLOWUP — short context-dependent utterances
        followup_patterns = [
            r'^(?:tell me more|expand on that|more details|go on|continue)[\.\?!]?$',
            r'^(?:can you (?:give|provide) more (?:details|information))[\.\?!]?$',
            r'^(?:and (?:from|about|what about))[\.\?!]?',
        ]
        if any(re.search(p, msg_lower) for p in followup_patterns):
            return {"category": "followup"}

        # 5. PROJECT — questions about specific projects or listing projects
        project_names = ['tailor', 'intelliman', 'duca', 'aias', 'daibetes',
                         'innoguard', 'crystal', 'movecare', 'empathic', 'menhir']
        if re.search(r'\bprojects?\b', msg_lower):
            # "projects" keyword present — but check if it's asking for papers, not projects
            if not re.search(r'\b(?:papers?|publications?|articles?)\b', msg_lower):
                return {"category": "project"}
        if any(re.search(r'\b' + name + r'\b', msg_lower) for name in project_names):
            return {"category": "project"}

        # 6. UNIVERSITY PAPERS — mentions a specific university
        # (checked before researcher to avoid false positives from name substrings)
        # Case-sensitive check for acronyms (avoid false positives on "ut", "kk")
        if re.search(r'\b(?:UMA|THUAS|USPN|UDCLV|THWS|TAMK)\b', msg):
            return {"category": "university_papers"}
        # KK and UT need more context to avoid false positives
        if re.search(r'\bKK\b', msg) and re.search(r'\b(?:kauno|lithuania|universit|papers?|researchers?)\b', msg_lower):
            return {"category": "university_papers"}
        if re.search(r'\bUT\b', msg) and re.search(r'\b(?:tirana|albania|universit|papers?|researchers?)\b', msg_lower):
            return {"category": "university_papers"}
        # Full university names (case-insensitive)
        uni_name_patterns = [
            r'\bm[aá]laga\b', r'\bhague\b', r'\bsorbonne\b', r'\bcampania\b',
            r'\bw[uü]rzburg\b', r'\btampere\b', r'\bkauno\b', r'\btirana\b',
            r'\bvanvitelli\b',
        ]
        if any(re.search(p, msg_lower) for p in uni_name_patterns):
            return {"category": "university_papers"}

        # 7. RESEARCHER — mentions a person's name
        if self._query_mentions_researcher(msg):
            return {"category": "researcher"}

        # 8. GLOSSARY — conceptual "What is X?" about RA terms
        glossary_patterns = [
            r'\bwhat is (?:the )?(?:explainable ai|xai|fairness in ai|eu ai act|'
            r'trustworthy ai|ai governance|ai bias|ai accountability|'
            r'ai transparency|responsible ai|ai red.?teaming|ai alignment|'
            r'sustainable ai|human.?centr\w+ ai)\b',
            r'\bdefine\s+(?:explainable ai|xai|fairness|eu ai act|trustworthy ai)\b',
            r'\bwhat is the difference between (?:interpretability|explainability)\b',
            r'\bhow do (?:interpretability|explainability)\b.*\bdiffer\b',
            r'\bdescribe the eu ai act\b',
        ]
        if any(re.search(p, msg_lower) for p in glossary_patterns):
            # Verify glossary entry exists
            if hasattr(self, '_build_glossary_context'):
                glossary_ctx = self._build_glossary_context(msg)
                if glossary_ctx:
                    return {"category": "glossary", "topic": ""}
            return {"category": "general", "topic": ""}

        # 9. GAP — research gaps, missing topics
        gap_patterns = [
            r'\b(?:gap|gaps)\b.*\bresearch\b', r'\bresearch\b.*\b(?:gap|gaps)\b',
            r'\bnot been studied\b', r'\bhave not been\b.*\bstudied\b',
            r'\bunexplored\b', r'\bunderexplored\b', r'\bleast studied\b',
            r'\bmissing\b.*\btopic\b', r'\btopic\b.*\bmissing\b',
            r'\bnot.*(?:covered|addressed|researched)\b',
        ]
        if any(re.search(p, msg_lower) for p in gap_patterns):
            return {"category": "gap"}

        # 10. TOPIC SEARCH — papers/publications on a topic
        topic_patterns = [
            r'\b(?:papers?|publications?|articles?)\b.*\b(?:on|about|regarding)\b',
            r'\b(?:on|about)\b.*\b(?:papers?|publications?|articles?)\b',
            r'\bresearch\b.*\b(?:on|about|at|in|within)\b',
        ]
        if any(re.search(p, msg_lower) for p in topic_patterns):
            topic = self._extract_topic_from_query(msg_lower)
            return {"category": "topic_search", "topic": topic}

        # 11. Broad AI questions — in scope but no specific category
        broad_ai_patterns = [
            r'\b(?:is|can|are|does|will)\b.*\bai\b.*\b(?:danger|harmful|trust|safe|risky|threat)\b',
            r'\bai\b.*\b(?:danger|harmful|trust\w*|safe\w*|risky|threat)\b',
            r'\bwhat is (?:a\s+)?(?:language model|neural network|deep learning|machine learning)\b',
        ]
        if any(re.search(p, msg_lower) for p in broad_ai_patterns):
            return {"category": "general", "topic": ""}

        # 12. OFF-TOPIC — not in Responsible AI scope
        if hasattr(self, '_is_in_topical_scope') and not self._is_in_topical_scope(msg):
            return {"category": "off_topic"}

        # 12. GENERAL — fallback for in-scope queries
        return {"category": "general", "topic": ""}

    def _extract_topic_from_query(self, msg_lower: str) -> str:
        """Extract the topic from a topic search query."""
        # Try to find "on/about X" pattern
        match = re.search(r'\b(?:on|about|regarding)\s+(.+?)(?:\s+(?:within|in|from|at)\b|$)', msg_lower)
        if match:
            return match.group(1).strip().rstrip('?.')
        return ""

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: Code classification (deterministic)
        classification = self._code_classify(user_message)

        # Step 2: Shared dispatch (identical to LLM-based)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            return result + "\n\n" + trace

        # Step 3: LLM fallback (identical to LLM-based)
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
