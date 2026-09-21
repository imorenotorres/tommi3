"""
RAG Study (9-class) — Auto Rule-based Classification (Iteration 2)

9-class taxonomy (Layer 1):
  papers, researcher, project, topic, glossary, organization, meta,
  general, out_of_scope

  general    — Research/academic/STEM questions NOT about Responsible AI
  out_of_scope — Non-research queries: task requests, greetings, trivia,
                 opinions, personal advice

Construction protocol:
  1. Start with minimal rules based only on the taxonomy descriptions
  2. Run constructor against development_set_9class.json
  3. Analyse misclassifications
  4. Add/refine rules to fix errors
  5. Repeat until convergence

Iteration 0 → Accuracy: 76.8% (53/69)

Iteration 1 fixes (→ Iteration 2):
  - Fix _GENERAL_DOMAINS trailing \\b preventing plural/suffix matches
    (compiler optimisation, database systems, operating systems)
  - Move project check BEFORE general domain check
    (prevents "projects on robot manipulation" → general)
  - Move "what is [non-RA term]?" from general → out_of_scope section
    (quantum computing is trivia, not a research query)
  - Add meta pattern: "scope of your knowledge"
  - Researcher: add "publications by", "what has X published", "working on"
    heuristics for names not matched by DB lookup
  - Researcher: move researchers? keyword check before _is_paper_query guard
  - Glossary: add "what does / what do" triggers
  - Glossary: add "different from" trigger for RA terms
  - Glossary: guard against gap-analysis queries ("underexplored in X")
  - Topic: add "studies" to research-term list
  - Topic: add "what has/have been done on" pattern
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

REASONING_LABEL = "auto rule-based (9-class, iteration 2)"


def _strip_accents(text: str) -> str:
    """Remove accents for matching."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# RA-domain keywords: if any of these appear, the query is NOT general
_RA_TERMS = re.compile(
    r'\b(?:responsible ai|explainable ai|xai|ai ethics|ai fairness|'
    r'trustworthy ai|ai governance|ai accountability|ai transparency|'
    r'ai bias|ai risk|ai audit|ai regulation|ai safety|ai alignment|'
    r'ai literacy|ai surveillance|ai decision|ai and privacy|'
    r'algorithmic|deepfake|data governance|data privacy|'
    r'fairness|bias|explainability|interpretability|accountability|'
    r'transparency|uninovis)\b'
)

# Non-RA research domains that signal `general`.
# No trailing \b on the outer group — individual alternatives already end at
# natural word boundaries or use s? to allow plurals.
_GENERAL_DOMAINS = re.compile(
    r'\b(?:'
    r'deep learning architectures?|computer vision|'
    r'image recognition|object detection|'
    r'neural machine translation|natural language (?:processing|understanding)|nlp|'
    r'bioinformatics|robotics?|robot manipulation|autonomous vehicles?|'
    r'quantum (?:computing|algorithms?|error correction)|'
    r'blockchain|cryptocurrency|'
    r'iot|internet of things|smart homes?|'
    r'5g|6g|cloud computing|'
    r'compiler optimi\w+|'
    r'database systems?|operating systems?|'
    r'graph neural networks?|neural architecture search|'
    r'medical image analysis|'
    r'vaccines?|photosynthesis|relativity|'
    r'machine learning(?! fairness| bias| ethics| accountability| governance)'
    r')'
)


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Rule-based 9-class classification -> shared dispatch."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        """Classify using deterministic rules. 9-class taxonomy.

        Priority order (first match wins):
          1. meta        — questions about the agent itself
          2. organization — questions about UNINOVIS / member institutions
          3. out_of_scope — non-research: tasks, greetings, opinions, trivia
          4. project     — named projects or "project(s)" keyword
                           (BEFORE general to prevent domain-overlap hijacking)
          5. general     — research/STEM questions outside the RA domain
          6. papers (figure) — visualisation requests about publications
          7. researcher  — person names, "researchers at [university]"
          8. glossary    — definitional questions about RA terms
          9. papers      — university-specific publication queries
         10. topic       — RA topic searches + gap analysis
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
        # "scope of your knowledge / data" — agent capability question
        if re.search(r'\b(?:scope of your|your (?:scope|knowledge|data|coverage))\b', msg_lower):
            return {"category": "meta"}

        # 2. ORGANIZATION — UNINOVIS, member institutions
        if re.search(r'\buninovis\b', msg_lower):
            if re.search(r'\b(?:universit|partner|countr|member|how many|which|about|info)\b', msg_lower):
                return {"category": "organization"}
            if re.search(r'^what is uninovis', msg_lower):
                return {"category": "organization"}

        # 3. OUT_OF_SCOPE — non-research: task requests, opinions, greetings, trivia
        # Task verbs
        task_verbs = r'\b(?:write|compose|draft|book|translate|send|schedule|cook|proofread)\b'
        if re.search(task_verbs, msg_lower):
            if not re.search(r'\bpapers?\b|\bresearch\b|\bproject\b', msg_lower):
                return {"category": "out_of_scope"}
        # "help me [do something]"
        if re.search(r'\bhelp me\b', msg_lower):
            return {"category": "out_of_scope"}
        # Explicit non-research keywords
        if re.search(r'\b(?:recipe|flight|hotel|ticket|weather|capital of|things to do)\b', msg_lower):
            return {"category": "out_of_scope"}
        # "who won" trivia
        if re.search(r'\bwho won\b', msg_lower):
            return {"category": "out_of_scope"}
        # Greetings
        if re.search(r'^(?:hello|hi|hey|good morning|good afternoon|test|asdf)[\.\?!]?\s*$', msg_lower):
            return {"category": "out_of_scope"}
        # Opinion questions
        if re.search(r'^(?:is ai|can ai be|should)\b', msg_lower):
            if not re.search(r'\b(?:papers?|research|project|published)\b', msg_lower):
                return {"category": "out_of_scope"}
        if re.search(r'\bis it ethical\b', msg_lower):
            return {"category": "out_of_scope"}
        # "What is X?" for clearly non-research non-RA topics → trivia/out_of_scope
        # (research queries on these domains use "papers on / research on" phrasing → general)
        if re.search(r'\bwhat is (?:a |the |an )?(?:quantum|blockchain|iot|5g|6g|cloud computing|photosynthesis|the capital)\b', msg_lower):
            if not _RA_TERMS.search(msg_lower):
                return {"category": "out_of_scope"}

        # 4. PROJECT — BEFORE general to avoid domain-overlap (e.g. "projects on robot manipulation")
        project_names = ['tailor', 'intelliman', 'duca', 'aias', 'daibetes',
                         'innoguard', 'crystal', 'movecare', 'empathic', 'menhir']
        if re.search(r'\bprojects?\b', msg_lower):
            if not re.search(r'\bpapers?\b', msg_lower) and not re.search(
                    r'\b(?:figure|chart|graph|map|visuali[sz]e|plot|display)\b', msg_lower):
                return {"category": "project"}
        if any(re.search(r'\b' + re.escape(name) + r'\b', msg_lower) for name in project_names):
            return {"category": "project"}

        # 5. GENERAL — research/STEM questions outside the RA domain
        if _GENERAL_DOMAINS.search(msg_lower) and not _RA_TERMS.search(msg_lower):
            return {"category": "general"}
        # Research queries on coffee/poetry/history → general (not RA)
        if re.search(r'\b(?:coffee|poetry|history)\b', msg_lower):
            if re.search(r'\b(?:papers?|research|find|publications?)\b', msg_lower):
                return {"category": "general"}
            if not _RA_TERMS.search(msg_lower):
                return {"category": "out_of_scope"}

        # 6. PAPERS (figure) — visualisation requests about publication data
        if re.search(r'\b(?:figure|chart|graph|visuali[sz]e|plot|display)\b', msg_lower):
            if re.search(r'\b(?:papers?|publications?|research|per partner|per year|by year|by university)\b', msg_lower):
                return {"category": "papers", "output_format": "figure"}
        if re.search(r'\bmap\b', msg_lower):
            if re.search(r'\b(?:papers?|publications?|research|projects?|per partner|number of)\b', msg_lower):
                return {"category": "papers", "output_format": "figure"}

        # 7. RESEARCHER — person names or researcher-focused queries
        _has_uni_code = bool(re.search(r'\b(?:UMA|THUAS|USPN|UDCLV|THWS|TAMK|KK|UT)\b', msg))
        _mentions_papers = bool(re.search(r'\b(?:papers?|publications?)\b', msg_lower))

        # "researchers" keyword — check BEFORE the paper-query guard
        # Only skip if the query is clearly paper-focused ("papers/publications from/at uni")
        if re.search(r'\bresearchers?\b', msg_lower):
            _paper_from_uni = bool(re.search(
                r'\b(?:papers?|publications?)\b.*\b(?:from|at|by)\b', msg_lower))
            if not _paper_from_uni:
                return {"category": "researcher"}

        if not (_has_uni_code and _mentions_papers):
            if self._query_mentions_researcher(msg):
                return {"category": "researcher"}
            if self._query_mentions_researcher(_strip_accents(msg)):
                return {"category": "researcher"}

        # Heuristic fallbacks for researcher names not in DB
        # "What has [Name] published?" — "has" + proper noun + "published"
        if re.search(r'\bwhat has\b', msg_lower) and re.search(r'\bpublished\b', msg_lower):
            return {"category": "researcher"}
        # "publications by [Name]" or "papers by [Name]"
        if re.search(r'\bpublications?\s+by\b', msg_lower):
            return {"category": "researcher"}
        if re.search(r'\bpapers by\b', msg_lower) and re.search(r'by\s+[A-ZÁÉÍÓÚÑ]', msg):
            return {"category": "researcher"}
        # "What is [Name] working on?" — proper noun + "working on"
        if re.search(r'\bworking on\b', msg_lower):
            if re.search(r'(?<![.]\s)\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]', msg):
                return {"category": "researcher"}
        if re.search(r'\bbibliography\b', msg_lower):
            return {"category": "researcher"}
        if re.search(r'\b(?:published|written) by\b', msg_lower):
            if not re.search(r'\b(?:THUAS|UMA|USPN|UDCLV|THWS|TAMK)\b', msg):
                return {"category": "researcher"}

        # 8. GLOSSARY — definitional questions about RA terms
        _gap_query = bool(re.search(r'\b(?:gaps?|underexplored|least studied|not (?:been )?studied)\b', msg_lower))
        glossary_terms = (r'\b(?:explainable ai|xai|fairness|eu ai act|trustworthy ai|'
                          r'interpretability|explainability|ai governance|ai bias|'
                          r'accountability|transparency)\b')
        if not _gap_query:
            if re.search(r'\b(?:what is|what are|define|describe|what does|what do)\b', msg_lower):
                if re.search(glossary_terms, msg_lower):
                    return {"category": "glossary"}
        if re.search(r'\bdifference between\b.*(?:interpret|explain)', msg_lower):
            return {"category": "glossary"}
        if re.search(r'\bdiffer\b', msg_lower) and re.search(r'(?:interpret|explain)', msg_lower):
            return {"category": "glossary"}
        # "How is X different from Y?" with RA terms
        if re.search(r'\bdifferent from\b', msg_lower) and re.search(glossary_terms, msg_lower):
            return {"category": "glossary"}
        # "What does the EU AI Act say/mean?"
        if re.search(r'\b(?:eu ai act|ai governance|ai bias|trustworthy ai)\b', msg_lower):
            if re.search(r'\b(?:what does|what do|mean|say|stand for|refer to)\b', msg_lower):
                return {"category": "glossary"}

        # 9. PAPERS — university-specific publication queries
        uni_codes = ['UMA', 'THUAS', 'USPN', 'UDCLV', 'THWS', 'TAMK', 'KK', 'UT']
        if any(re.search(r'\b' + re.escape(u) + r'\b', msg) for u in uni_codes):
            if re.search(r'\b(?:papers?|publications?|written|published)\b', msg_lower):
                return {"category": "papers"}
        if re.search(r'\b(?:from|at)\b.*\b(?:papers?|publications?)\b', msg_lower):
            return {"category": "papers"}
        if re.search(r'\b(?:papers?|publications?)\b.*\b(?:from|at)\b', msg_lower):
            return {"category": "papers"}
        if re.search(r'\bany papers?\b', msg_lower):
            return {"category": "papers"}

        # 10. TOPIC — RA topic searches + gap analysis
        if re.search(r'\b(?:gaps?|not (?:been )?studied|underexplored|least studied)\b', msg_lower):
            return {"category": "topic"}
        # "what has/have been done on X"
        if re.search(r'\bwhat (?:has|have) been done\b', msg_lower):
            return {"category": "topic"}
        if re.search(r'\b(?:papers?|publications?|research|articles?|studies)\b.*\b(?:on|about|regarding)\b', msg_lower):
            return {"category": "topic"}
        if re.search(r'\b(?:on|about)\b.*\b(?:papers?|publications?|research|articles?|studies)\b', msg_lower):
            return {"category": "topic"}
        if re.search(r'\bresearch\b.*\b(?:on|in|about|within|at)\b', msg_lower):
            return {"category": "topic"}
        if re.search(r'\bresearch\b', msg_lower) and re.search(
                r'\b(?:ai|responsible|ethic|trustworth|explainabl|education|privacy)\b', msg_lower):
            return {"category": "topic"}
        if re.search(r'\bhow is\b.*\bchanging\b', msg_lower):
            return {"category": "topic"}

        # Fallback
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
