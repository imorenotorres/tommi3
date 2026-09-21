"""
RAG Study (9-class) — Auto Rule-based Classifier
CONSTRUCTION RUN C — 19BSept Iteration 1

Different construction path from Runs A and B:
  - Same priority order as seed (meta→org→OOS→general→papers-fig→researcher→glossary→papers→project→topic)
  - Typo normalization preprocessing: standardise common Spanish-phonetic misspellings
    before classification, rather than adding fuzzy patterns at every check point
  - Inline RA-term expansion without rewriting compiled patterns
  - Papers/researcher: researcher check uses a direct 'person-query' pattern list;
    papers check uses a 'university-output' pattern list — no shared guards

Starting from the minimal seed (55.3%).

9-class taxonomy:
  papers       — publications at a specific university, or visualisation
  researcher   — specific persons or lists of researchers
  project      — named research projects or project listings
  topic        — surveys of a Responsible AI area, incl. gap analysis
  glossary     — definitions of RA concepts or terms
  organization — factual queries about UNINOVIS or member institutions
  meta         — queries about the agent's capabilities or data
  general      — research/academic questions NOT about Responsible AI
  out_of_scope — non-research: tasks, greetings, trivia, opinions
"""

import os
import sys
import re
import unicodedata

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "rule-based (9-class, 19BSept, run-C iter-3)"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# ── Typo normalization map ────────────────────────────────────────────────
# Maps Spanish-phonetic l2_typo forms → canonical English spellings.
# Applied as a preprocessing step before classification.
_TYPO_MAP = [
    # General domain terms
    (r'\bmachin\b',          'machine'),
    (r'\bl[ae]rning\b',      'learning'),
    (r'\blerning\b',         'learning'),
    (r'\bkuantun\b',         'quantum'),
    (r'\btranslacion\b',     'translation'),
    (r'\bimag\b(?=\s+recog)', 'image'),
    # Publication variants
    (r'\bpublicasion\w*\b',  'publications'),
    (r'\bpublicacion\w*\b',  'publications'),
    (r'\bpublicac\w+\b',     'publications'),
    (r'\bpubliccc?\w+\b',    'publications'),
    (r'\bpeipers?\b',        'papers'),
    # RA concept misspellings
    (r'\bfearness\b',        'fairness'),
    (r'\bfearnes\b',         'fairness'),
    (r'\bexplainab\w+\b',    'explainability'),
    (r'\bexplanab\w+\b',     'explainability'),
    (r'\binterpretabilty\b', 'interpretability'),
    (r'\binterpretabiliti\b','interpretability'),
    (r'\bgobernance\b',      'governance'),
    (r'\bresponsable\b',     'responsible'),
    (r'\bregulatori\b',      'regulatory'),
    (r'\bacountability\b',   'accountability'),
    (r'\bexplainabilty\b',   'explainability'),
    (r'\bhaig.stak\w+\b',    'high-stakes'),
    # Organization
    (r'\baliance\b',         'alliance'),
    # Meta
    (r'\bcapabilitis\b',     'capabilities'),
    (r'\bnowledge\b',        'knowledge'),
    (r'\bacces\b',           'access'),
    (r'\bscop\b',            'scope'),
    (r'\byu\b',              'you'),
    # Glossary typos
    (r'\bdiferent\b',        'different'),
    # Researcher
    (r'\breserchers?\b',     'researchers'),
    (r'\bpublised\b',        'published'),
    # Topic / articles
    (r'\bartikels?\b',       'articles'),
    (r'\bartikles?\b',       'articles'),
    (r'\breserch\b',         'research'),
    # Project
    (r'\bproyects?\b',       'projects'),
    # IA → AI (Spanish acronym inversion)
    (r'\bIA\b',              'AI'),
]


def _normalize(text: str) -> str:
    """Apply typo normalization map to produce a canonical form for classification."""
    result = text
    for pattern, replacement in _TYPO_MAP:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


# ── Core compiled patterns (on normalized text) ───────────────────────────

_RA_TERMS = re.compile(
    r'\b(?:responsible ai|explainable ai|xai|ai ethics|ai fairness|'
    r'trustworthy ai|ai governance|ai accountability|ai transparency|'
    r'ai bias|ai risk|ai regulation|ai safety|ai alignment|'
    r'algorithmic|data governance|data privacy|regulatory compliance|'
    r'societal impact|high.stakes|'
    r'fairness|bias|explainability|interpretability|accountability|'
    r'transparency|uninovis)\b',
    re.IGNORECASE
)

_GENERAL_DOMAINS = re.compile(
    r'\b(?:deep learning|machine learning|computer vision|'
    r'image recognition|object detection|'
    r'neural machine translation|natural language processing|nlp|'
    r'bioinformatics|robotics|robot manipulation|autonomous vehicles|'
    r'quantum computing|quantum algorithms|'
    r'blockchain|cryptocurrency|'
    r'internet of things|iot|smart home|'
    r'cloud computing|compiler optim\w+|'
    r'database systems|operating systems|'
    r'graph neural networks|neural architecture search|'
    r'medical image analysis|learning machine)\b',  # inverted word order
    re.IGNORECASE
)

_RA_GLOSSARY_TERMS = re.compile(
    r'\b(?:explainability|xai|fairness|eu ai act|trustworthy ai|'
    r'interpretability|ai governance|ai bias|'
    r'accountability|transparency|responsible ai)\b',
    re.IGNORECASE
)

_UNI_CODES = ['UMA', 'THUAS', 'USPN', 'UDCLV', 'THWS', 'TAMK', 'KK', 'UT']

_UNI_COUNTRIES = re.compile(
    r'\b(?:french|italian|spanish|german|finnish|dutch|lithuanian|albanian)\b',
    re.IGNORECASE
)

_PROJECT_NAMES = [
    'tailor', 'intelliman', 'duca', 'aias', 'daibetes',
    'innoguard', 'crystal', 'movecare', 'empathic', 'menhir',
]


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Rule-based classifier for 9-class taxonomy — Run C, Iteration 1."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        msg = user_message.strip()
        # Normalize typos first — classification runs on normalized text
        norm = _normalize(msg)
        n = norm.lower()          # normalized lowercase (for most checks)
        msg_orig = msg            # original case (for uni-code and proper-name checks)

        def _has_uni(text=msg_orig):
            return any(re.search(r'\b' + re.escape(u) + r'\b', text) for u in _UNI_CODES)

        # 1. META
        if re.search(r'\b(?:who are you|what can you do|what do you do|how does this work)\b', n):
            return {"category": "meta"}
        if re.search(r'\b(?:your capabilities|your functionality|what functionality|you offer)\b', n):
            return {"category": "meta"}
        if re.search(r'\b(?:scope of your knowledge|do you have access|have you access)\b', n):
            return {"category": "meta"}
        if re.search(r'\bcapabilit\w+\b', n):
            return {"category": "meta"}
        # "what topics can you" / "with what topics you can help me"
        if re.search(r'\btopics?\b.{0,40}\bcan\b|\bwhat\s+(?:topics?|areas?)\b.{0,30}\byou\b', n):
            return {"category": "meta"}
        if re.search(r'\byou are who\b|\bwho are you\b', n):
            return {"category": "meta"}

        # 2. ORGANIZATION
        # Guard: researcher queries mentioning UNINOVIS should not be caught here
        _researcher_query = bool(re.search(r'\bresearchers?\b', n) and _RA_TERMS.search(n))
        if not _researcher_query:
            if re.search(r'\buninovis\b', n):
                if re.search(r'\b(?:what is|universit|partner|countr|member|how many|which|about|'
                             r'role|alliance|whats?)\b', n):
                    return {"category": "organization"}
        # Typo of UNINOVIS (normalization doesn't cover it — catch here)
        if not _researcher_query:
            if re.search(r'\bunino[a-z]{2,6}\b', n) and not re.search(r'\buninovis\b', n):
                return {"category": "organization"}
            if _has_uni():
                if re.search(r'\b(?:role|alliance|member of)\b', n):
                    return {"category": "organization"}

        # 3. OUT_OF_SCOPE
        if re.search(r'\b(?:write|compose|draft|book|translate|send|schedule|cook|proofread)\b', n):
            if not re.search(r'\b(?:papers?|research|projects?)\b', n):
                return {"category": "out_of_scope"}
        if re.search(r'\bhelp me\b', n):
            if not re.search(r'\b(?:topics?|areas?|cover|capabilit)\b', n):
                return {"category": "out_of_scope"}
        if re.search(r'\b(?:recipe|flight|hotel|ticket|weather|capital of)\b', n):
            return {"category": "out_of_scope"}
        if re.search(r'\bwho won\b', n):
            return {"category": "out_of_scope"}
        if re.search(r'^(?:hello|hi|hey|good morning|good afternoon)[\.\?!]?\s*$', n):
            return {"category": "out_of_scope"}
        if re.search(r'\b(?:your opinion|is it ethical|should ai)\b', n):
            return {"category": "out_of_scope"}

        # 4. GENERAL (normalized text catches machin→machine, lerning→learning, etc.)
        if _GENERAL_DOMAINS.search(n) and not _RA_TERMS.search(n):
            return {"category": "general"}

        # 5. PAPERS (figure)
        if re.search(r'\b(?:chart|graph|figure|visuali[sz]e|plot|map)\b', n):
            if re.search(r'\b(?:papers?|publications?|research output)\b', n):
                return {"category": "papers", "output_format": "figure"}

        # 6. RESEARCHER
        # Direct person-query patterns (on normalized text)
        if re.search(r'\bresearchers?\s+(?:at|in|from|of|working|are\b)', n):
            return {"category": "researcher"}
        if re.search(r'\b(?:list|find|show|who are|who is)\s+(?:the\s+)?(?:\w+\s+)?researchers?\b', n):
            return {"category": "researcher"}
        if re.search(r'\bresearchers?\s+(?:are\s+)?working\b', n):
            return {"category": "researcher"}
        if re.search(r'\bwho\s+in\s+\w+\s+(?:works?|is\s+working)\b', n):
            return {"category": "researcher"}
        if re.search(r'\bwhat\s+has\s+\w+\s+\w+\s+published\b', n):
            return {"category": "researcher"}
        # "what is/are [ProperName] [ProperName] publications?" — require capitalised names
        # Use n (lowercase) for trigger, norm (original case) for name check
        if re.search(r'\bwhat\s+(?:is|are)\b', n):
            if re.search(r'\b[A-Z]\w+\s+[A-Z]\w+\s+publications?\b', norm):
                return {"category": "researcher"}
        # "publications by/of [Proper Name]" — require mixed case (not uni code)
        if re.search(r'\bpublications?\s+(?:by|of)\s+[A-Z][a-z]', norm):
            return {"category": "researcher"}
        if self._query_mentions_researcher(norm):
            return {"category": "researcher"}
        if self._query_mentions_researcher(_strip_accents(norm)):
            return {"category": "researcher"}

        # 7. GLOSSARY
        if re.search(r'\b(?:what is|what are|what does|what do|define|describe|'
                     r'mean\w*|difference between|different from)\b', n):
            if _RA_GLOSSARY_TERMS.search(n):
                return {"category": "glossary"}

        # 8. PAPERS — university-specific
        if _has_uni():
            if re.search(r'\b(?:papers?|publications?|published|written)\b', n):
                return {"category": "papers"}
        if _UNI_COUNTRIES.search(n):
            if re.search(r'\b(?:papers?|publications?)\b', n):
                return {"category": "papers"}
        if re.search(r'\b(?:papers?|publications?)\b.*\b(?:from|at|by|of)\b', n):
            return {"category": "papers"}
        if re.search(r'\b(?:from|at)\b.*\b(?:papers?|publications?)\b', n):
            return {"category": "papers"}

        # 9. PROJECT
        if re.search(r'\bprojects?\b', n):
            return {"category": "project"}
        if any(re.search(r'\b' + re.escape(p) + r'\b', n) for p in _PROJECT_NAMES):
            return {"category": "project"}

        # 10. TOPIC
        if re.search(r'\bwhat has been (?:done|made|written)\b', n):
            if _RA_TERMS.search(n):
                return {"category": "topic"}
        if re.search(r'\b(?:are there|there are|is there)\b', n):
            if re.search(r'\b(?:papers?|publications?|research|articles?)\b', n):
                return {"category": "topic"}
        if re.search(r'\barticles?\b', n):
            if re.search(r'\bai\b', n) or _RA_TERMS.search(n):
                return {"category": "topic"}
        if re.search(r'\b(?:papers?|publications?|research|articles?|studies)\b', n):
            if _RA_TERMS.search(n):
                return {"category": "topic"}
        if re.search(r'\b(?:gaps?|underexplored|least studied)\b', n):
            return {"category": "topic"}

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
