"""
RAG Study (9-class) — Auto Rule-based Classifier
CONSTRUCTION RUN B — 19BSept Iteration 1

Different construction path from Run A:
  - researcher step moved BEFORE organization (handles UNINOVIS+researcher queries naturally)
  - glossary moved BEFORE papers
  - no helper functions — inline logic throughout
  - stem-based fuzzy matching instead of alternation groups
  - papers/researcher: whitelist of explicit researcher patterns rather than word-order guard
  - meta: broad 'topic/area + you' detection; capability stems
  - RA terms: added 'impact of ai', 'societal', standalone 'ai' in article context

Starting from the minimal seed (55.3%) targeting convergence through a different path.

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

Priority order (first match wins):
  1. meta
  2. researcher   ← moved up (before organization)
  3. organization
  4. out_of_scope
  5. general
  6. papers (figure)
  7. glossary     ← moved up (before papers)
  8. papers
  9. project
  10. topic
  (fallback: out_of_scope)
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

REASONING_LABEL = "rule-based (9-class, 19BSept, run-B iter-3)"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# RA-domain terms — broad, includes l2_typo variants
_RA_TERMS = re.compile(
    r'\b(?:responsible ai|responsable ai|'
    r'explainable ai|explanable ai|xai|'
    r'ai ethics|ai fairness|ai fearness|'
    r'trustworthy ai|ai governance|ai gobernance|'
    r'ai accountability|ai acountability|'
    r'ai transparency|ai bias|ai risk|ai regulation|'
    r'ai safety|ai alignment|algorithmic|'
    r'data governance|data privacy|'
    r'regulatory compliance|regulatori compliance|'
    r'societal impact|societal|high.stakes?|haig.stak\w*|'
    r'fairness|fearness|bias|'
    r'explainability|explainabilty|'
    r'interpretability|interpretabilty|'
    r'accountability|acountability|'
    r'transparency|uninovis)\b',
    re.IGNORECASE
)

# Non-RA research domains (exact spelling)
_GENERAL_DOMAINS = re.compile(
    r'\b(?:deep learning|machine learning|computer vision|'
    r'image recognition|object detection|'
    r'neural machine translation|natural language processing|nlp|'
    r'bioinformatics|robotics|robot manipulation|autonomous vehicles|'
    r'quantum computing|quantum algorithms|'
    r'blockchain|cryptocurrency|'
    r'internet of things|iot|smart home|'
    r'cloud computing|compiler optimis\w+|'
    r'database systems|operating systems|'
    r'graph neural networks|neural architecture search|'
    r'medical image analysis)\b',
    re.IGNORECASE
)

# RA glossary terms — broad match with typo tolerance
_RA_GLOSSARY_TERMS = re.compile(
    r'\b(?:xai|eu ai act|trustworthy ai|responsible ai|responsable ai|'
    r'explainab\w+(?:\s+(?:ai|ia))?|explanab\w+|'
    r'f[ae]irness\w*|fearness\w*|fearnes\b|'   # fearnes = typo of fearness/fairness
    r'ai\s+gov\w+|gobernance|'
    r'interpret\w{5,}|'
    r'accountab\w+|transparen\w+|ai\s+bias)\b',
    re.IGNORECASE
)

# University codes
_UNI_CODES = ['UMA', 'THUAS', 'USPN', 'UDCLV', 'THWS', 'TAMK', 'KK', 'UT']

# Member country adjectives
_UNI_COUNTRIES = re.compile(
    r'\b(?:french|italian|spanish|german|finnish|dutch|lithuanian|albanian)\b',
    re.IGNORECASE
)

# Known project names
_PROJECT_NAMES = [
    'tailor', 'intelliman', 'duca', 'aias', 'daibetes',
    'innoguard', 'crystal', 'movecare', 'empathic', 'menhir',
]

# Stem patterns for "publication" variants (typos included)
_PUB_STEMS = re.compile(
    r'\b(?:papers?|peipers?|publications?|publicat\w+|publicas\w+|publicac\w+|publicc\w+)\b',
    re.IGNORECASE
)

# Explicit researcher-focused patterns (whitelist — these are unambiguously about a person/list)
_RESEARCHER_PATTERNS = re.compile(
    r'\b(?:'
    r'researchers?\s+(?:at|in|from|of|working|are\s+working)|'  # "researchers at UMA" / "researchers are working"
    r'reser\w{2,5}ers?\s+(?:at|in|from|working)|'  # typo: "reserchers at"
    r'(?:list|find|show|who\s+are|who\s+is)\s+(?:the\s+)?(?:main\s+)?\w*\s*researchers?|'  # "list THWS researchers"
    r'researchers?\s+(?:are\s+)?working|'
    r'who\s+(?:are|is)\s+(?:the\s+)?(?:main\s+)?researchers?|'
    r'who\s+in\s+\w+\s+(?:works?|is\s+working)|'
    r'what\s+(?:has|is)\s+\w+\s+\w+\s+publi\w+|'  # "what has/is X Y published/publications"
    r'publi\w+\s+(?:by|of)\s+[A-Z]\w+'             # "publications by Giulio..." — \w+ to avoid \b after [a-z]
    r')',
    re.IGNORECASE
)


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Rule-based classifier for 9-class taxonomy — Run B, Iteration 1."""
    _AGENT_FILE = __file__

    def _has_uni_code(self, msg: str) -> bool:
        return any(re.search(r'\b' + re.escape(u) + r'\b', msg) for u in _UNI_CODES)

    def _code_classify(self, user_message: str) -> dict:
        msg = user_message.strip()
        msg_lower = msg.lower()

        # ── 1. META ─────────────────────────────────────────────────────────
        # Core identity phrases
        if re.search(r'\b(?:who are you|what can you do|what do you do|how does this work)\b',
                     msg_lower):
            return {"category": "meta"}
        # Capability stems: "capabilit*", "functionality", "you offer"
        if re.search(r'\bcapabilit\w*\b|\bfunctionalit\w+\b|\byou offer\b', msg_lower):
            return {"category": "meta"}
        # Scope / topics you handle / data access
        if re.search(r'\bscop\w*\s+of\s+your\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\b(?:do\s+you|have\s+you)\s+(?:have\s+)?acces\w*\b', msg_lower):
            return {"category": "meta"}
        # "what topics can you" / "topics you can help" / "with what topics you"
        if re.search(r'\btopics?\b.{0,40}\b(?:can\s+you|you\s+can|do\s+you\s+cover|you\s+help)\b',
                     msg_lower):
            return {"category": "meta"}
        if re.search(r'\bwhat\s+(?:topics?|areas?)\b.{0,30}\b(?:can|do)\s+you\b', msg_lower):
            return {"category": "meta"}
        # Typo/inversion of "who are you"
        if re.search(r'\byou\s+are\s+who\b|\bwho\s+are\s+y\w{1,3}\b', msg_lower):
            return {"category": "meta"}

        # ── 2. RESEARCHER ────────────────────────────────────────────────────
        # Moved before organization to handle "researchers in UNINOVIS" naturally
        #
        # First: explicit researcher-pattern whitelist
        if _RESEARCHER_PATTERNS.search(msg):
            # Guard: "publications of [UNI_CODE]" is papers, not researcher
            _uni_code_pat = r'\bpubli\w+\s+(?:of|by)\s+(?:UMA|THUAS|USPN|UDCLV|THWS|TAMK|KK|UT)\b'
            if not re.search(_uni_code_pat, msg, re.IGNORECASE):
                return {"category": "researcher"}
        # "researchers?" keyword — but NOT when it's a modifier in "papers from X researchers"
        if re.search(r'\b(?:researchers?|reser\w{2,5}ers?)\b', msg_lower):
            # If "papers/publications" precedes "researcher" keyword → skip (it's a papers query)
            if not re.search(
                    r'\b(?:papers?|peipers?|publicat\w+|publicac\w+)\b'
                    r'.{0,50}\b(?:researchers?|reser\w{2,5}ers?)\b',
                    msg_lower):
                return {"category": "researcher"}
        # DB lookup
        if self._query_mentions_researcher(msg):
            return {"category": "researcher"}
        if self._query_mentions_researcher(_strip_accents(msg)):
            return {"category": "researcher"}

        # ── 3. ORGANIZATION ──────────────────────────────────────────────────
        if re.search(r'\buninovis\b', msg_lower):
            if re.search(r'\b(?:what\s+is|what\'?s|whats?|universit|partner|countr|member|'
                         r'how\s+many|which|about|role|alliance)\b', msg_lower):
                return {"category": "organization"}
        # UNINOVIS typo
        if re.search(r'\bunino[a-z]{2,6}\b', msg_lower) and \
                not re.search(r'\buninovis\b', msg_lower):
            return {"category": "organization"}
        # Member institution + role/alliance context
        if self._has_uni_code(msg):
            if re.search(r'\b(?:role?|alian\w+|member\s+of)\b', msg_lower):
                return {"category": "organization"}

        # ── 4. OUT_OF_SCOPE ──────────────────────────────────────────────────
        if re.search(r'\b(?:write|compose|draft|book|translate|send|schedule|cook|proofread)\b',
                     msg_lower):
            if not re.search(r'\b(?:papers?|research|project)\b', msg_lower):
                return {"category": "out_of_scope"}
        if re.search(r'\bhelp\s+me\b', msg_lower):
            if not re.search(r'\b(?:topics?|areas?|cover|capabilit)\b', msg_lower):
                return {"category": "out_of_scope"}
        if re.search(r'\b(?:recipe|flight|hotel|ticket|weather|capital\s+of)\b', msg_lower):
            return {"category": "out_of_scope"}
        if re.search(r'\bwho\s+won\b', msg_lower):
            return {"category": "out_of_scope"}
        if re.search(r'^(?:hello|hi|hey|good\s+morning|good\s+afternoon)[\.\?!]?\s*$', msg_lower):
            return {"category": "out_of_scope"}
        if re.search(r'\b(?:your\s+opinion|is\s+it\s+ethical|should\s+ai)\b', msg_lower):
            return {"category": "out_of_scope"}

        # ── 5. GENERAL ───────────────────────────────────────────────────────
        _is_general_domain = (
            _GENERAL_DOMAINS.search(msg_lower) or
            # Fuzzy stems for l2_typo: machin(e) learn(ing), deep learn(ing), etc.
            re.search(r'\bmachin\w*\s+learn\w+\b', msg_lower) or
            re.search(r'\bdeep\s+l[ae]rn\w+\b', msg_lower) or
            re.search(r'\bkuan\w+\s+comput\w+\b', msg_lower) or
            re.search(r'\bneural\s+machin\w*\s+translac?\w+\b', msg_lower) or
            re.search(r'\bimag\s+recognit\w+\b', msg_lower) or
            re.search(r'\blearning\s+machine\b', msg_lower) or  # inverted
            re.search(r'\bcompiler\s+optim\w+\b', msg_lower)
        )
        if _is_general_domain and not _RA_TERMS.search(msg_lower):
            return {"category": "general"}

        # ── 6. PAPERS (figure) ───────────────────────────────────────────────
        if re.search(r'\b(?:chart|graph|figure|visuali[sz]e|plot|map)\b', msg_lower):
            if _PUB_STEMS.search(msg_lower):
                return {"category": "papers", "output_format": "figure"}

        # ── 7. GLOSSARY (moved before papers) ────────────────────────────────
        _gloss_trigger = re.search(
            r'\b(?:what\s+is|what\s+are|what\s+does|what\s+do|define|'
            r'describe|mean\w*|difference\s+between|different\s+from|'
            r'diferent\s+from|how\s+is.{0,30}different)\b',
            msg_lower)
        if _gloss_trigger and _RA_GLOSSARY_TERMS.search(msg_lower):
            return {"category": "glossary"}
        # "what AI governance means?" (verb at end — l2_grammar)
        if _RA_GLOSSARY_TERMS.search(msg_lower) and \
                re.search(r'\bmeans?\b|\bdefine\w*\b', msg_lower):
            return {"category": "glossary"}

        # ── 8. PAPERS ────────────────────────────────────────────────────────
        if self._has_uni_code(msg) and _PUB_STEMS.search(msg_lower):
            return {"category": "papers"}
        # Country adjective + publications → papers
        if _UNI_COUNTRIES.search(msg_lower) and _PUB_STEMS.search(msg_lower):
            return {"category": "papers"}
        # Structural patterns: "papers from/at/by/of X" or "from/at X papers"
        if re.search(r'\b(?:papers?|peipers?|publicat\w+|publicas\w+)\b.{0,30}'
                     r'\b(?:from|at|by|of)\b', msg_lower):
            return {"category": "papers"}
        if re.search(r'\b(?:from|at)\b.{0,30}'
                     r'\b(?:papers?|peipers?|publicat\w+|publicas\w+)\b', msg_lower):
            return {"category": "papers"}

        # ── 9. PROJECT ───────────────────────────────────────────────────────
        if re.search(r'\bpro(?:jects?|yects?)\b', msg_lower):
            return {"category": "project"}
        if any(re.search(r'\b' + re.escape(n) + r'\b', msg_lower) for n in _PROJECT_NAMES):
            return {"category": "project"}

        # ── 10. TOPIC ────────────────────────────────────────────────────────
        # "what has been done/made on [RA topic]"
        if re.search(r'\bwhat\s+has\s+been\s+(?:done|made|written)\b', msg_lower):
            if _RA_TERMS.search(msg_lower):
                return {"category": "topic"}
        # "are there / there are + research/papers/articles"
        if re.search(r'\b(?:are\s+there|there\s+are|is\s+there)\b', msg_lower):
            if re.search(r'\b(?:papers?|reserch\w*|research|articles?|publicat\w+)\b', msg_lower):
                return {"category": "topic"}
        # "articles/artikels about AI/RA topic"
        if re.search(r'\barti(?:c|k)\w*\b', msg_lower):
            if re.search(r'\bai\b', msg_lower) or _RA_TERMS.search(msg_lower):
                return {"category": "topic"}
        # Fuzzy "research" + RA term
        if re.search(r'\breserch\w*\b', msg_lower) and _RA_TERMS.search(msg_lower):
            return {"category": "topic"}
        # Standard: research/papers + RA term
        if re.search(r'\b(?:papers?|peipers?|publicat\w+|research|articles?|studies)\b',
                     msg_lower):
            if _RA_TERMS.search(msg_lower):
                return {"category": "topic"}
        if re.search(r'\b(?:gaps?|underexplored|least\s+studied)\b', msg_lower):
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
