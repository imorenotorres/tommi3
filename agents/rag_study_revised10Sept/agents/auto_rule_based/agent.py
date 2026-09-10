"""
RAG Study (8-class) — Auto Rule-based Classification (Iteration 0)

Deterministic classification using regex/keyword patterns, built from
scratch using only the 8-class taxonomy definition and the development
set. This is the initial skeleton — the constructor will iteratively
refine the rules.

8-class taxonomy (Layer 1):
  papers, researcher, project, topic, glossary, organization, meta, out_of_scope

Construction protocol:
  1. Start with minimal rules based only on the taxonomy descriptions
  2. Run constructor against development_set_8class.json
  3. Analyse misclassifications
  4. Add/refine rules to fix errors
  5. Repeat until convergence

Iteration 0: Minimal rules derived solely from the 8-class category
definitions. No development set queries have been seen yet.
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

REASONING_LABEL = "auto rule-based (8-class, iteration 3)"


def _strip_accents(text: str) -> str:
    """Remove accents for matching."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Rule-based 8-class classification -> shared dispatch."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify using deterministic rules. 8-class taxonomy.

        Priority order (first match wins):
          1. meta — questions about the agent itself
          2. organization — questions about UNINOVIS / member institutions
          3. out_of_scope — tasks, off-topic, opinions, greetings
          4. project — named projects or "project(s)" keyword
          5. researcher — person names, "researchers at [university]"
          6. glossary — "what is [RA term]?" definitional questions
          7. papers — university-specific paper queries + figure requests
          8. topic — topic searches + gap analysis
          (fallback: out_of_scope)
        """
        msg = user_message.strip()
        msg_lower = msg.lower()

        # 1. META — questions about the agent's identity/capabilities
        if re.search(r'\b(?:what can you do|who are you|how does this work|what do you do)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\b(?:your capabilities|your functionality|what functionality|you offer)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\bhow (?:does|do) (?:this|you|it) work\b', msg_lower):
            return {"category": "meta"}

        # 2. ORGANIZATION — UNINOVIS, member institutions
        if re.search(r'\buninovis\b', msg_lower):
            if re.search(r'\b(?:universit|partner|countr|member|how many|which|about|info)\b', msg_lower):
                return {"category": "organization"}
            if re.search(r'^what is uninovis', msg_lower):
                return {"category": "organization"}

        # 3. OUT_OF_SCOPE — task requests, off-topic, opinions, greetings
        # Task verbs
        task_verbs = r'\b(?:write|compose|draft|book|translate|send|schedule|cook|proofread)\b'
        if re.search(task_verbs, msg_lower):
            if not re.search(r'\bpapers?\b|\bresearch\b|\bproject\b', msg_lower):
                return {"category": "out_of_scope"}
        # "help me [do something]"
        if re.search(r'\bhelp me\b', msg_lower):
            return {"category": "out_of_scope"}
        # Explicit off-topic keywords
        if re.search(r'\b(?:recipe|flight|hotel|ticket|weather|capital of|things to do)\b', msg_lower):
            return {"category": "out_of_scope"}
        # "who won" pattern
        if re.search(r'\bwho won\b', msg_lower):
            return {"category": "out_of_scope"}
        # Greetings and meaningless input
        if re.search(r'^(?:hello|hi|hey|good morning|good afternoon|test|asdf)[\.\?!]?\s*$', msg_lower):
            return {"category": "out_of_scope"}
        # Opinion questions about AI (not research-related)
        if re.search(r'^(?:is ai|can ai be|should)\b', msg_lower):
            if not re.search(r'\b(?:papers?|research|project|published)\b', msg_lower):
                return {"category": "out_of_scope"}
        # "what is X" where X is NOT an RA term
        if re.search(r'\bwhat is (?:a |the )?(?:quantum|photosynthesis|language model|capital)\b', msg_lower):
            return {"category": "out_of_scope"}
        # Out-of-scope research domains (incl. common misspellings)
        if re.search(r'\b(?:coff?ee?\b|coffe\b|poetry|history|photosynthesis|quantum)\b', msg_lower):
            if re.search(r'\b(?:papers?|research|find)\b', msg_lower):
                return {"category": "out_of_scope"}
            if not re.search(r'\b(?:ai|responsible|ethic|trustworth|explainabl)\b', msg_lower):
                return {"category": "out_of_scope"}
        # "is it ethical" questions (opinion)
        if re.search(r'\bis it ethical\b', msg_lower):
            return {"category": "out_of_scope"}

        # 4. PAPERS (figure) — visualisation requests (before project/researcher)
        # "show a figure/chart/map/graph" with data terms
        if re.search(r'\b(?:figure|chart|graph|visuali[sz]e|plot|display)\b', msg_lower):
            if re.search(r'\b(?:papers?|publications?|research|per partner|per year|by year|by university)\b', msg_lower):
                return {"category": "papers", "output_format": "figure"}
        # "show a map" with publications/projects context -> papers (figure)
        if re.search(r'\bmap\b', msg_lower):
            if re.search(r'\b(?:papers?|publications?|research|projects?|per partner|number of)\b', msg_lower):
                return {"category": "papers", "output_format": "figure"}

        # 5. PROJECT — project names or "project(s)" keyword
        project_names = ['tailor', 'intelliman', 'duca', 'aias', 'daibetes',
                         'innoguard', 'crystal', 'movecare', 'empathic', 'menhir']
        if re.search(r'\bprojects?\b', msg_lower):
            # Not if query is about papers or already caught as figure
            if not re.search(r'\bpapers?\b', msg_lower) and not re.search(r'\b(?:figure|chart|graph|map|visuali[sz]e|plot|display)\b', msg_lower):
                return {"category": "project"}
        if any(re.search(r'\b' + re.escape(name) + r'\b', msg_lower) for name in project_names):
            return {"category": "project"}

        # 6. RESEARCHER — person names, "researchers at [university]"
        # Check for specific person names — but NOT when query has a university code + papers
        _has_uni_code = bool(re.search(r'\b(?:UMA|THUAS|USPN|UDCLV|THWS|TAMK|KK|UT)\b', msg))
        _mentions_papers = bool(re.search(r'\b(?:papers?|publications?)\b', msg_lower))
        if not (_has_uni_code and _mentions_papers):
            if self._query_mentions_researcher(msg):
                return {"category": "researcher"}
            if self._query_mentions_researcher(_strip_accents(msg)):
                return {"category": "researcher"}
        # "researchers" keyword — but NOT when query is about papers from a university's researchers
        _is_paper_query = bool(re.search(r'\b(?:list|show|which|any)\b.*\b(?:papers?|publications?)\b', msg_lower))
        if not _is_paper_query:
            if re.search(r'\bresearchers?\b', msg_lower):
                return {"category": "researcher"}
        # "bibliography of [Name]" — always researcher
        if re.search(r'\bbibliography\b', msg_lower):
            return {"category": "researcher"}
        # "published by" / "written by" — researcher only when NOT about papers at a university
        if re.search(r'\b(?:published|written) by\b', msg_lower):
            if not re.search(r'\b(?:THUAS|UMA|USPN|UDCLV|THWS|TAMK)\b', msg):
                return {"category": "researcher"}
        # "papers by [Name]" only when followed by a capitalised name
        if re.search(r'\bpapers by\b', msg_lower):
            if re.search(r'by\s+[A-ZÁÉÍÓÚÑ]', msg):
                return {"category": "researcher"}

        # 6. GLOSSARY — "what is [RA term]?" definitional questions
        glossary_terms = r'\b(?:explainable ai|xai|fairness|eu ai act|trustworthy ai|interpretability|explainability|ai governance|ai bias|accountability|transparency)\b'
        if re.search(r'\b(?:what is|define|describe)\b', msg_lower):
            if re.search(glossary_terms, msg_lower):
                return {"category": "glossary"}
        if re.search(r'\bdifference between\b.*(?:interpret|explain)', msg_lower):
            return {"category": "glossary"}
        if re.search(r'\bdiffer\b', msg_lower) and re.search(r'(?:interpret|explain)', msg_lower):
            return {"category": "glossary"}

        # 7. PAPERS — university-specific paper queries
        # (Figure/visualisation requests already handled in step 4 above)
        # University-specific paper queries
        uni_codes = ['UMA', 'THUAS', 'USPN', 'UDCLV', 'THWS', 'TAMK', 'KK', 'UT']
        if any(re.search(r'\b' + re.escape(u) + r'\b', msg) for u in uni_codes):
            if re.search(r'\b(?:papers?|publications?|written|published)\b', msg_lower):
                return {"category": "papers"}
        # "papers from [university name]"
        if re.search(r'\b(?:from|at)\b.*\b(?:papers?|publications?)\b', msg_lower):
            return {"category": "papers"}
        if re.search(r'\b(?:papers?|publications?)\b.*\b(?:from|at)\b', msg_lower):
            return {"category": "papers"}
        # "any papers about X" (broad, not topic-specific)
        if re.search(r'\bany papers?\b', msg_lower):
            return {"category": "papers"}

        # 8. TOPIC — topic searches + gap analysis
        # Gap analysis
        if re.search(r'\b(?:gaps?|not (?:been )?studied|underexplored|least studied)\b', msg_lower):
            return {"category": "topic"}
        # Topic searches
        if re.search(r'\b(?:papers?|publications?|research|articles?)\b.*\b(?:on|about|regarding)\b', msg_lower):
            return {"category": "topic"}
        if re.search(r'\b(?:on|about)\b.*\b(?:papers?|publications?|research|articles?)\b', msg_lower):
            return {"category": "topic"}
        # "research on/in/at [topic]"
        if re.search(r'\bresearch\b.*\b(?:on|in|about|within|at)\b', msg_lower):
            return {"category": "topic"}
        # "[topic] research at [place]"
        if re.search(r'\bresearch\b', msg_lower) and re.search(r'\b(?:ai|responsible|ethic|trustworth|explainabl|education|privacy)\b', msg_lower):
            return {"category": "topic"}
        # "How is X changing Y" (survey questions)
        if re.search(r'\bhow is\b.*\bchanging\b', msg_lower):
            return {"category": "topic"}

        # Fallback: out_of_scope
        return {"category": "out_of_scope"}

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
