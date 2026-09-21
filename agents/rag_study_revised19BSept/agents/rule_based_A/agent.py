"""
RAG Study (9-class) — Auto Rule-based Classifier
CONSTRUCTION RUN A — 19BSept Iteration 3

Fixes from iteration 2 (91.3% → target >96%):
  researcher:   fixed regex bug: \breser\w*ers?\b did NOT match 'researchers'
                (resea- != reser-); now uses \b(?:researchers?|reser\w{2,4}ers?)\b
                fixed 'show publications of [UNI]' → wrongly matched researcher rule;
                require [A-Z][a-z] (mixed-case name) not all-caps uni code
                fixed 'researchers working on RA in UNINOVIS' → add RA guard removal
                fixed 'who are main researchers at UMA' → uni code check for researcher
  meta:         added 'with what topics' (l2_grammar inverted); 'acces' (typo of access)
  general:      fixed fuzzy 'learning' pattern (l[ae]rn didn't match 'learning');
                added 'learning machine' (inverted word order)
  papers:       added 'peipers' to fuzzy publication keywords
  topic:        added 'articles? + ai' → topic; 'impact of ai' pattern

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

REASONING_LABEL = "rule-based (9-class, 19BSept, run-A iter-4)"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# RA-domain terms (also catches common l2_typo variants)
_RA_TERMS = re.compile(
    r'\b(?:responsible ai|responsable ai|explainable ai|explanable ai|xai|'
    r'ai ethics|ai fairness|ai fearness|'
    r'trustworthy ai|ai governance|ai gobernance|ai accountability|ai acountability|'
    r'ai transparency|ai bias|ai risk|ai regulation|ai safety|ai alignment|'
    r'algorithmic|data governance|data privacy|'
    r'regulatory compliance|regulatori compliance|'
    r'societal impact|high.stakes?|haig.stak\w*|'
    r'fairness|fearness|bias|explainability|explainabilty|'
    r'interpretability|interpretabilty|accountability|acountability|'
    r'transparency|uninovis)\b'
    r'|\bIA\b'  # Spanish acronym inversion (AI→IA)
)

# Non-RA research domains
_GENERAL_DOMAINS = re.compile(
    r'\b(?:deep learning|machine learning|computer vision|'
    r'image recognition|object detection|'
    r'neural machine translation|natural language processing|nlp|'
    r'bioinformatics|robotics|robot manipulation|autonomous vehicles|'
    r'quantum computing|quantum algorithms|'
    r'blockchain|cryptocurrency|'
    r'internet of things|iot|smart home|'
    r'cloud computing|'
    r'database systems|operating systems|'
    r'graph neural networks|neural architecture search|'
    r'medical image analysis)\b'
)

# Fuzzy general domain terms for l2_typo misspellings
_GENERAL_DOMAINS_FUZZY = re.compile(
    r'\b(?:machin\w*\s+learn\w+|'          # machin learning, machin lerning
    r'deep\s+l[ae]rn\w+|'                  # deep lerning
    r'kuan\w+\s+comput\w+|'                # kuantun computing
    r'neural\s+machin\w*\s+translac?\w+|'  # neural machin translacion
    r'imag\s+recognit\w+|'                 # imag recognition
    r'learning\s+machine)\b'               # inverted word order
)

# RA glossary terms (includes fuzzy l2_typo variants)
_RA_GLOSSARY_TERMS = re.compile(
    r'\b(?:explainab\w+\s+(?:ai|ia)|explanab\w+|xai|'
    r'f[ae]irness|fearness?|fearnes\b|'
    r'eu ai act|trustworthy ai|'
    r'interpret\w{6,}|'
    r'ai\s+gov\w+|gobernance|'
    r'ai\s+bias|'
    r'accountab\w+|'
    r'transparen\w+|'
    r'responsible ai|responsable ai)\b'
)

# University codes
_UNI_CODES = ['UMA', 'THUAS', 'USPN', 'UDCLV', 'THWS', 'TAMK', 'KK', 'UT']

# UNINOVIS member country adjectives
_UNI_COUNTRIES = re.compile(
    r'\b(?:french|italian|spanish|german|finnish|dutch|lithuanian|albanian|'
    r'france|italy|spain|germany|finland|netherlands|lithuania|albania)\b'
)

# Known project names
_PROJECT_NAMES = [
    'tailor', 'intelliman', 'duca', 'aias', 'daibetes',
    'innoguard', 'crystal', 'movecare', 'empathic', 'menhir',
]

# Researcher keyword: both correct and typo forms
# 'researchers?' = correct; 'reser\w{2,4}ers?' = typo (reserchers, reserchers, etc.)
_RESEARCHER_KW = re.compile(r'\b(?:researchers?|reser\w{2,4}ers?)\b')


def _has_uni_code(msg: str) -> bool:
    return any(re.search(r'\b' + re.escape(u) + r'\b', msg) for u in _UNI_CODES)


def _has_publication_keyword(msg_lower: str) -> bool:
    """Match 'papers', 'publications', and fuzzy typo variants (peipers, publicasions...)."""
    return bool(re.search(
        r'\b(?:papers?|peipers?|publicat\w+|publicas\w+|publicc\w+)\b', msg_lower))


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Rule-based classifier for 9-class taxonomy — Run A, Iteration 3."""
    _AGENT_FILE = __file__

    def _code_classify(self, user_message: str) -> dict:
        msg = user_message.strip()
        msg_lower = msg.lower()

        # 1. META — agent identity, capabilities, data access
        if re.search(r'\b(?:who are you|what can you do|what do you do|how does this work)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\b(?:your capabilities|your functionality|what functionality|you offer)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\b(?:scope of your|scop of your|'
                     r'do you have acces\w*|have you access|'
                     r'what (?:topics?|areas?) (?:can|do) you|'
                     r'topics? (?:can|do) you (?:help|cover)|you cover)\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\bcapabilit\w+\b', msg_lower):
            return {"category": "meta"}
        # Inverted: "with what topics you can help me", "topics you can help"
        if re.search(r'\btopics?\b.{0,30}\bcan\b', msg_lower):
            return {"category": "meta"}
        if re.search(r'\btopics?\b.{0,20}\byou\b.{0,20}\bhelp\b', msg_lower):
            return {"category": "meta"}
        # Typo/inversion of "who are you"
        if re.search(r'\b(?:who are y\w{1,3}|you are who)\b', msg_lower):
            return {"category": "meta"}

        # 2. ORGANIZATION — UNINOVIS alliance or member institutions
        _has_ra = bool(_RA_TERMS.search(msg_lower))
        _has_res_kw = bool(_RESEARCHER_KW.search(msg_lower))
        if not (_has_res_kw and _has_ra):
            if re.search(r'\buninovis\b', msg_lower):
                if re.search(r'\b(?:what is|what\'s|whats?|universit|partner|countr|member|'
                             r'how many|which|about|role|alliance)\b', msg_lower):
                    return {"category": "organization"}
            if re.search(r'\bunino[a-z]{2,6}\b', msg_lower) and not re.search(r'\buninovis\b', msg_lower):
                return {"category": "organization"}
            if _has_uni_code(msg):
                if re.search(r'\b(?:role?|alian\w+|member of)\b', msg_lower):
                    return {"category": "organization"}

        # 3. OUT_OF_SCOPE
        task_verbs = r'\b(?:write|compose|draft|book|translate|send|schedule|cook|proofread)\b'
        if re.search(task_verbs, msg_lower):
            if not re.search(r'\b(?:papers?|research|project)\b', msg_lower):
                return {"category": "out_of_scope"}
        if re.search(r'\bhelp me\b', msg_lower):
            if not re.search(r'\b(?:topics?|areas?|cover|capabilit)\b', msg_lower):
                return {"category": "out_of_scope"}
        if re.search(r'\b(?:recipe|flight|hotel|ticket|weather|capital of)\b', msg_lower):
            return {"category": "out_of_scope"}
        if re.search(r'\bwho won\b', msg_lower):
            return {"category": "out_of_scope"}
        if re.search(r'^(?:hello|hi|hey|good morning|good afternoon)[\.\?!]?\s*$', msg_lower):
            return {"category": "out_of_scope"}
        if re.search(r'\b(?:your opinion|is it ethical|should ai)\b', msg_lower):
            return {"category": "out_of_scope"}

        # 4. GENERAL
        if re.search(r'\bcompiler optim\w+\b', msg_lower) and not _RA_TERMS.search(msg_lower):
            return {"category": "general"}
        if (_GENERAL_DOMAINS.search(msg_lower) or _GENERAL_DOMAINS_FUZZY.search(msg_lower)) \
                and not _RA_TERMS.search(msg_lower):
            return {"category": "general"}

        # 5. PAPERS (figure)
        if re.search(r'\b(?:chart|graph|figure|visuali[sz]e|plot|map)\b', msg_lower):
            if _has_publication_keyword(msg_lower):
                return {"category": "papers", "output_format": "figure"}

        # 6. RESEARCHER
        if _RESEARCHER_KW.search(msg_lower):
            # Guard: "papers from X researchers" — papers-keyword precedes researcher-keyword
            papers_before = re.search(
                r'\b(?:papers?|peipers?|publicat\w+|publicas\w+)\b.{0,50}\b(?:researchers?|reser\w+ers?)\b',
                msg_lower)
            if not papers_before:
                return {"category": "researcher"}
        # "what has [Name] published/publised"
        if re.search(r'\bwhat has .{2,35} publi\w+\b', msg_lower):
            return {"category": "researcher"}
        # "what is [Name] publications?"
        if re.search(r'\bwhat is .{2,25} publicat\w+\b', msg_lower):
            return {"category": "researcher"}
        # "find/show/get publications by/of [Proper Name]" — require mixed-case name (not uni code)
        if re.search(r'\b(?:find|show|get)\b', msg_lower):
            if re.search(r'\bpublicac?\w*\s+(?:by|of)\s+[A-Z][a-z]', msg):
                return {"category": "researcher"}
        # "who in [ORG] works on / is working on"
        if re.search(r'\bwho in\b', msg_lower):
            if re.search(r'\b(?:works?\s+on|working|research\w*)\b', msg_lower):
                return {"category": "researcher"}
        # "who are the main researchers at [UNI]"
        if re.search(r'\bwho (?:are|is) the\b', msg_lower):
            if _has_uni_code(msg) or re.search(r'\buninovis\b', msg_lower):
                return {"category": "researcher"}
        # DB lookup
        if self._query_mentions_researcher(msg):
            return {"category": "researcher"}
        if self._query_mentions_researcher(_strip_accents(msg)):
            return {"category": "researcher"}

        # 7. GLOSSARY
        _gloss_trigger = re.search(
            r'\b(?:what is|what are|what does|what do|define|describe|mean|means?|'
            r'difference between|different from|diferent from|differ\w+ (?:from|between))\b',
            msg_lower)
        if _gloss_trigger and _RA_GLOSSARY_TERMS.search(msg_lower):
            return {"category": "glossary"}
        if re.search(r'\bmeans?\b', msg_lower) and _RA_GLOSSARY_TERMS.search(msg_lower):
            return {"category": "glossary"}

        # 8. PAPERS — university-specific publications
        if _has_uni_code(msg):
            if _has_publication_keyword(msg_lower):
                return {"category": "papers"}
        if _UNI_COUNTRIES.search(msg_lower):
            if _has_publication_keyword(msg_lower):
                return {"category": "papers"}
        if re.search(r'\b(?:papers?|peipers?|publicat\w+|publicas\w+)\b.{0,30}\b(?:from|at|by|of)\b',
                     msg_lower):
            return {"category": "papers"}
        if re.search(r'\b(?:from|at)\b.{0,30}\b(?:papers?|peipers?|publicat\w+|publicas\w+)\b',
                     msg_lower):
            return {"category": "papers"}

        # 9. PROJECT
        if re.search(r'\bpro(?:jects?|yects?)\b', msg_lower):
            return {"category": "project"}
        if any(re.search(r'\b' + re.escape(n) + r'\b', msg_lower) for n in _PROJECT_NAMES):
            return {"category": "project"}

        # 10. TOPIC
        if re.search(r'\bwhat has been (?:done|made|written)\b', msg_lower):
            if _RA_TERMS.search(msg_lower):
                return {"category": "topic"}
        if re.search(r'\b(?:are there|there are|is there)\b', msg_lower):
            if re.search(r'\b(?:papers?|peipers?|publicat\w+|reserch\w*|research|articles?)\b', msg_lower):
                return {"category": "topic"}
        # "articles? about/on AI [topic]" — "AI" alone sufficient as RA signal in article context
        if re.search(r'\barti(?:c|k)\w*\b', msg_lower):
            if re.search(r'\bai\b', msg_lower) or _RA_TERMS.search(msg_lower):
                return {"category": "topic"}
        # Fuzzy "research" variants
        if re.search(r'\breserch\w*\b', msg_lower) and _RA_TERMS.search(msg_lower):
            return {"category": "topic"}
        if re.search(r'\b(?:papers?|peipers?|publicat\w+|research|articles?|studies)\b', msg_lower):
            if _RA_TERMS.search(msg_lower):
                return {"category": "topic"}
        if re.search(r'\b(?:gaps?|underexplored|least studied)\b', msg_lower):
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
