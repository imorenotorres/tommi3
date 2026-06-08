"""
Rule-Based Generalisation Study — Phase 2: Generalised Rules

Same deterministic classification as Phase 1, but with generalisation
mechanisms that prevent overfitting:
  1. Synonym expansion: word families mapped to canonical forms
  2. Intent templates: structural patterns instead of exact phrases
  3. Entity-type detection: person names as a class
  4. Broad category signals: keywords that indicate a category
"""

import os
import sys
import re
import unicodedata

# Add paths
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "generalised rule-based patterns"

# ── Synonym expansion ──────────────────────────────────────────────────────
# Maps families of related words to canonical forms.
# Applied to the query BEFORE pattern matching, so patterns only need
# to match the canonical form.

SYNONYM_MAP = {
    # Action verbs → canonical
    "compose": "write", "draft": "write", "prepare": "write", "create": "write",
    "generate": "write", "produce": "write",
    "summarise": "summarize", "summarize": "summarize",
    "proofread": "review", "review": "review",
    "schedule": "organize", "organize": "organize", "arrange": "organize",
    "calculate": "compute", "compute": "compute",
    # Paper/publication synonyms
    "publications": "papers", "articles": "papers", "studies": "papers",
    "literature": "papers", "output": "papers", "work": "papers",
    # Visualisation synonyms
    "visualize": "show figure", "visualise": "show figure",
    "plot": "show figure", "graph": "show figure", "chart": "show figure",
    "diagram": "show figure", "timeline": "show figure",
    "bar chart": "show figure", "display": "show",
    # Research synonyms
    "bibliography": "papers by", "academic output": "papers by",
    # Define/explain synonyms
    "define": "what is", "explain": "what is",
    "meaning of": "what is", "meant by": "what is",
    "refer to": "what is", "concept of": "what is",
    # Meta synonyms
    "capabilities": "what can you do", "functionality": "what can you do",
    "features": "what can you do", "purpose": "what can you do",
    "your help": "what can you do",
    # Gap synonyms
    "blind spots": "gaps", "underrepresented": "gaps",
    "opportunities": "gaps", "missing": "gaps",
    "not explored": "not studied", "not addressed": "not studied",
    "new research directions": "gaps",
    # Followup synonyms
    "go deeper": "tell me more", "go deeper into that": "tell me more",
    "elaborate": "tell me more", "yes, elaborate": "tell me more",
    "continue": "tell me more", "show me more": "tell me more",
    # Visualisation synonyms (more)
    "visualisation": "figure", "visualization": "figure",
    "bar chart": "figure",
    # Generate → create, but only when NOT followed by chart/figure terms
    # (handled in pattern logic, not here)
    # Followup (more)
    "yes, elaborate please": "tell me more",
    "yes elaborate": "tell me more",
    # Not addressed → gap
    "not being addressed": "not studied", "challenges are not": "gaps not",
}

# Sort by length descending (longest match first) to avoid partial replacements
_SORTED_SYNONYMS = sorted(SYNONYM_MAP.items(), key=lambda x: -len(x[0]))


def _normalise_query(query: str) -> str:
    """Apply synonym expansion to the query."""
    result = query.lower()
    for old, new in _SORTED_SYNONYMS:
        # Use word boundaries to avoid replacing inside words
        result = re.sub(r'\b' + re.escape(old) + r'\b', new, result)
    return result


def _strip_accents(text: str) -> str:
    """Remove accents for matching (preserves original for display)."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Generalised rule-based classification → shared dispatch."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify with generalisation mechanisms.

        Key differences from narrow rules:
        1. Synonym expansion applied before pattern matching
        2. Intent templates instead of exact phrases
        3. Entity-type detection for researcher names
        4. Broad category signals (keywords that indicate a category)
        """
        msg_original = user_message.strip()
        msg = _normalise_query(msg_original)
        msg_lower = msg.lower()

        # 1. META — questions about the agent, its capabilities, or UNINOVIS itself
        if re.search(r'\bwhat can you do\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\b(?:who|what)\s+(?:are|is)\s+(?:you|this|uninovis)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\buninovis\b.*\b(?:universit|partner|countr|member)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\b(?:universit|partner|countr|member)\b.*\buninovis\b', msg_lower):
            return {"category": "meta"}
        # Intent template: questions about the agent's identity/purpose/capabilities
        if re.search(r'\b(?:you|your|this tool|this system|this assistant)\b', msg_lower):
            if re.search(r'\b(?:what can you do|help|cover|access|offer|purpose|about you)\b', msg_lower):
                return {"category": "meta"}
            if re.search(r'\bai assistant\b', msg_lower):
                return {"category": "meta"}
        if re.search(r'\bhow (?:does|do) (?:this|you) work\b', msg_lower):
            return {"category": "meta"}
        # "new here" intent
        if re.search(r'\bnew here\b|\bget started\b|\boverview\b', msg_lower):
            return {"category": "meta"}
        # "how many universities", "which countries" + UNINOVIS (but NOT project queries)
        if re.search(r'\buninovis\b', msg_lower) and re.search(r'\b(?:how many|which|countries|participate|members)\b', msg_lower):
            if not re.search(r'\bprojects?\b|\bfunded\b|\bgrant\b', msg_lower):
                return {"category": "meta"}

        # 2. NON-RESEARCH — task requests (action verb + task object)
        # Intent template: [action verb] + [object] where action is a task
        task_verbs = r'(?:write|summarize|review|send|organize|compute|book|translat\w*)'
        # "make" only as task verb when followed by task objects, not "what makes"
        if re.search(r'\bmake\s+(?:me|a|the)\b', msg_lower):
            if not re.search(r'\b(?:figure|chart|graph)\b', msg_lower):
                return {"category": "non_research"}
        if re.search(task_verbs, msg_lower):
            # Exclude when it's about papers/research (topic_search)
            if not re.search(r'\bpapers?\b.*\bon\b|\bon\b.*\bpapers?\b', msg_lower):
                # Exclude broad AI questions (these are "general", not tasks)
                if not re.search(r'\b(?:is|are|does|can|will|should)\b.*\bai\b', msg_lower):
                    # Exclude figure requests ("generate a bar chart")
                    if not re.search(r'\b(?:figure|chart|graph|bar chart|pie chart|histogram)\b', msg_lower):
                        return {"category": "non_research"}
        # Explicit task keywords
        if re.search(r'\b(?:recipe|flight|hotel|ticket|weather|PowerPoint|presentation|email|meeting)\b', msg_lower):
            return {"category": "non_research"}
        # "who won" pattern
        if re.search(r'\bwho won\b', msg_lower):
            return {"category": "non_research"}
        # Help me [do something]
        if re.search(r'\bhelp me\b', msg_lower):
            return {"category": "non_research"}

        # 3. FIGURE/MAP — visualisation requests
        # Synonym expansion already mapped visualise/plot/graph/chart/timeline → "show figure"
        if re.search(r'\bfigure\b|\bmap\b', msg_lower):
            return {"category": "figure"}
        # "show me how many papers" → figure (data display intent)
        # But NOT "show me all research FROM [university]" → that's university_papers
        if re.search(r'\bshow\s+(?:me\s+)?(?:how many|the number)\b.*\b(?:papers?|publications?|research)\b', msg_lower):
            return {"category": "figure"}

        # 4. FOLLOWUP — short, context-dependent
        # Synonym expansion mapped elaborate/continue/show me more → "tell me more"
        if re.search(r'^(?:tell me more|yes,?\s+tell me more|and (?:from|about|what about))[\.\?!]?\s*$', msg_lower):
            return {"category": "followup"}
        if re.search(r'^(?:can you (?:give|provide) more|more details|go on)[\.\?!]?\s*$', msg_lower):
            return {"category": "followup"}
        # Very short queries that reference prior context
        if len(msg_original.split()) <= 5 and re.search(r'\b(?:and from|what about|also)\b', msg_lower):
            return {"category": "followup"}

        # 5. PROJECT — project names or "project(s)" keyword
        project_names = ['tailor', 'intelliman', 'duca', 'aias', 'daibetes',
                         'innoguard', 'crystal', 'movecare', 'empathic', 'menhir']
        if re.search(r'\bprojects?\b', msg_lower):
            if not re.search(r'\bpapers?\b', msg_lower):
                return {"category": "project"}
        if any(re.search(r'\b' + re.escape(name) + r'\b', msg_lower) for name in project_names):
            return {"category": "project"}
        # "EU-funded", "Horizon" → project context
        if re.search(r'\b(?:eu.funded|horizon|funded|grant)\b', msg_lower):
            return {"category": "project"}

        # 6. UNIVERSITY — mentions a university (before researcher to avoid substring matches)
        if re.search(r'\b(?:UMA|THUAS|USPN|UDCLV|THWS|TAMK)\b', msg_original):
            return {"category": "university_papers"}
        if re.search(r'\bKK\b', msg_original) and re.search(r'\b(?:kauno|lithuania|universit|papers?|researcher)\b', msg_lower):
            return {"category": "university_papers"}
        if re.search(r'\bUT\b', msg_original) and re.search(r'\b(?:tirana|albania|universit|papers?|researcher)\b', msg_lower):
            return {"category": "university_papers"}
        uni_names = [r'm[aá]laga', r'hague', r'sorbonne', r'campania', r'vanvitelli',
                     r'w[uü]rzburg', r'tampere', r'kauno', r'tirana']
        if any(re.search(r'\b' + p + r'\b', msg_lower) for p in uni_names):
            # Only university_papers if the query is about research/papers/researchers
            if re.search(r'\b(?:papers?|research|publications?|researchers?|output|from|university|all)\b', msg_lower):
                return {"category": "university_papers"}
        # "Italian/Spanish/German/etc. partner" → university
        if re.search(r'\b(?:italian|spanish|german|french|finnish|dutch|lithuanian|albanian)\s+(?:partner|university)\b', msg_lower):
            return {"category": "university_papers"}

        # 7. RESEARCHER — entity-type detection (person name)
        # Use the MetadataRAGMixin's researcher detection (matches against DB)
        # Try both original and accent-stripped versions
        if self._query_mentions_researcher(msg_original):
            return {"category": "researcher"}
        if self._query_mentions_researcher(_strip_accents(msg_original)):
            return {"category": "researcher"}
        # Intent template: "papers by [name]" / "[name]'s papers" patterns
        # After synonym expansion, "publications by" → "papers by"
        if re.search(r'\bpapers by\b', msg_lower):
            return {"category": "researcher"}
        # "published by [name]", "authored by [name]", "from Professor [name]"
        if re.search(r'\b(?:published|authored|written) by\b', msg_lower):
            return {"category": "researcher"}
        if re.search(r'\b(?:from|by)\s+(?:professor|prof\.?|dr\.?)\b', msg_lower):
            return {"category": "researcher"}
        # "published anything on [topic]" with a person's name earlier
        if re.search(r'\bpublished\b.*\bon\b', msg_lower):
            # Check for capitalised name
            if re.search(r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+', msg_original):
                return {"category": "researcher"}
        # "topics does [Name] research" — but NOT "topics that UNINOVIS has not explored"
        if re.search(r'\btopics?\s+does\b', msg_lower):
            if re.search(r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+', msg_original):
                return {"category": "researcher"}
        # "research of/by/interests of [Name]" with a capitalised word after
        if re.search(r'\b(?:research|topics|work)\s+(?:of|by|interests of)\b', msg_lower):
            # Check if followed by a capitalised name in the original
            name_match = re.search(r'(?:of|by)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)', msg_original)
            if name_match:
                return {"category": "researcher"}
        # "looking for work by [Name]"
        if re.search(r'\blooking for\b.*\bby\b', msg_lower):
            return {"category": "researcher"}

        # 8. GLOSSARY — conceptual questions about RA terms
        # After synonym expansion: "define X" → "what is X", "explain X" → "what is X",
        # "meaning of X" → "what is X", "meant by X" → "what is X"
        glossary_check = False
        if re.search(r'\bwhat is\b', msg_lower):
            glossary_check = True
        # "difference between X and Y" about RA concepts
        if re.search(r'\bdifference between\b.*\b(?:ai|interpret|explain|fair|bias|trust)\b', msg_lower):
            glossary_check = True
        # "tell me about [RA concept]"
        if re.search(r'\btell me about\b.*\b(?:ai|responsible|explainable|trustworthy|fairness|governance|bias|accountability|transparency|human.centr)\b', msg_lower):
            glossary_check = True
        # "how is X defined", "What does X mean?"
        if re.search(r'\bhow is\b.*\bdefined\b', msg_lower):
            glossary_check = True
        if re.search(r'\bwhat does\b.*\bmean\b', msg_lower):
            glossary_check = True

        if glossary_check and hasattr(self, '_build_glossary_context'):
            # Try multiple forms: original, normalised, and with "AI" prefix/suffix variations
            for q in [msg_original, msg, user_message]:
                glossary_ctx = self._build_glossary_context(q)
                if glossary_ctx:
                    return {"category": "glossary", "topic": ""}
            # If no glossary match but it's a "what is" question about RA, still glossary-like
            if re.search(r'\bwhat is\b.*\b(?:accountability|governance|transparency|bias|sustainable|red.?teaming|responsible)\b', msg_lower):
                return {"category": "glossary", "topic": ""}

        # 9. GAP — research gaps, missing topics
        # After synonym expansion: "blind spots" → "gaps", "missing" → "gaps", etc.
        if re.search(r'\bgaps?\b', msg_lower):
            return {"category": "gap"}
        if re.search(r'\bnot (?:been )?studied\b|\bnot (?:been )?explored\b', msg_lower):
            return {"category": "gap"}
        if re.search(r'\bleast studied\b|\bunderexplored\b|\bunexplored\b', msg_lower):
            return {"category": "gap"}
        if re.search(r'\bzero papers\b', msg_lower):
            return {"category": "gap"}
        # "focus on next", "new research" → gap-like intent
        if re.search(r'\bfocus on next\b|\bnew research\b', msg_lower):
            return {"category": "gap"}

        # 10. TOPIC SEARCH — papers/publications on a topic
        # After synonym expansion: "publications/articles/studies/literature" → "papers"
        if re.search(r'\bpapers?\b.*\b(?:on|about|regarding|related|dealing)\b', msg_lower):
            return {"category": "topic_search", "topic": ""}
        if re.search(r'\b(?:on|about)\b.*\bpapers?\b', msg_lower):
            return {"category": "topic_search", "topic": ""}
        if re.search(r'\bresearch\b.*\b(?:on|about|in|at|within|exists)\b', msg_lower):
            return {"category": "topic_search", "topic": ""}
        # "what has been published on X"
        if re.search(r'\bpublished on\b|\bexists on\b', msg_lower):
            return {"category": "topic_search", "topic": ""}

        # 11. Broad AI questions → general (before off_topic check)
        if re.search(r'\bai\b', msg_lower):
            if re.search(r'\b(?:danger|harmful|trust\w*|safe\w*|bias\w*|rights|replace|regulat\w*|future|challeng\w*|teach|taught|measure|ethic\w*|model)\b', msg_lower):
                return {"category": "general", "topic": ""}
        # Broad technology/research questions that are in scope
        if re.search(r'\b(?:responsible|explainable|trustworthy|fairness)\b', msg_lower):
            return {"category": "general", "topic": ""}

        # 12. OFF-TOPIC
        if hasattr(self, '_is_in_topical_scope') and not self._is_in_topical_scope(msg_original):
            return {"category": "off_topic"}

        # 13. GENERAL — fallback
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
