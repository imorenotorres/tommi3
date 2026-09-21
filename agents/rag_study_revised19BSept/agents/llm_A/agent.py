"""
RAG Study (9-class) — LLM-based Classifier
MINIMAL SEED — 19BSept Construction Run A

Classification prompt derived solely from the 9-class taxonomy definitions.
No development set examples have been seen. This identical seed is the
starting point for LLM construction runs A, B, C; each run will independently
refine the prompt through different paths.

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

Construction protocol:
  1. Start with this minimal prompt (taxonomy definitions only)
  2. Run constructor against development_set_9class.json
  3. Analyse misclassifications
  4. Refine CLASSIFY_PROMPT to fix errors
  5. Repeat until convergence
"""

import os
import sys
import json
import re

_AGENT_DIR = os.path.dirname(os.path.realpath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(_AGENT_DIR))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "LLM classification (9-class, 19BSept, run-A iter-4)"

CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Classify the user query into exactly ONE of these 9 categories:

1. meta — queries about what this agent can do, what data it has access to, or how it works
2. organization — factual queries about UNINOVIS (the European university alliance) or its member institutions
3. out_of_scope — non-research requests: task requests (write, translate, cook, book, schedule, proofread, "help me write/draft"), greetings, trivia, opinions, personal advice
4. general — research or academic questions NOT about Responsible AI (e.g. deep learning, NLP, robotics, quantum computing, bioinformatics, compiler optimisation)
5. papers — queries about publications AT A SPECIFIC UNIVERSITY, or requests for a visualisation/chart/graph of publication data
6. researcher — queries about a specific person's research or publications, or asking to list/find researchers at a university
7. project — queries about named research projects or asking to list/find projects (keyword: "projects")
8. topic — queries surveying a Responsible AI research area (AI ethics, fairness, explainability, accountability, transparency, AI governance, AI bias, AI safety, trustworthy AI, regulatory compliance, societal impact), including research gap analysis
9. glossary — definitional queries: "what is X?", "define X", "what does X mean?", "how is X different from Y?" where X is a Responsible AI term

University codes: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

KEY DISTINCTIONS — read these carefully before classifying:

ORGANIZATION: "What is UNINOVIS?" or "What is UMA?" with a proper institution name → organization (not glossary). "What is X?" is glossary ONLY when X is an RA concept, not when X is a proper name or institution.
  ✓ "What is UNINOVIS?" → organization
  ✗ NOT glossary (UNINOVIS is an institution, not an RA concept)

META (data access about the agent): If the query asks whether YOU have access to something, or what data YOU hold — it's meta, even if UNINOVIS is mentioned.
  ✓ "Do you have access to UNINOVIS publications?" → meta
  ✓ "Do you have acces to UNINOVIS publicacions?" → meta  (typos: acces=access, publicacions=publications)
  ✓ "Have you access to UNINOVIS publications?" → meta
  ✗ NOT organization — the query is about your capabilities, not about UNINOVIS as an institution

RESEARCHER PRIORITY: If the query mentions "researchers", "who works on", "who in X works on" → researcher EVEN IF RA topics are also mentioned. The subject is people.
  ✓ "Researchers working on explainable AI in UNINOVIS" → researcher
  ✓ "Who in UNINOVIS works on both AI fairness and interpretability?" → researcher

GLOSSARY vs TOPIC: Glossary = definitional. Topic = survey of research.
  ✓ "How is trustworthy AI different from responsible AI?" → glossary
  ✓ "Research on trustworthy AI" → topic

GENERAL vs GLOSSARY: ML, deep learning, NLP, computer vision, robotics = NON-RA → general.
  ✓ "What is machine learning?" → general (ML is not an RA concept)
  ✓ "What is explainability?" → glossary (RA concept)

GENERAL vs TOPIC — RA TERM WINS: If a query mentions both a non-RA domain (e.g. machine learning) AND an RA term (fairness, regulatory compliance, societal impact, AI bias, etc.), the RA term determines the category → topic.
  ✓ "Research on machine learning fairness" → topic (fairness is RA)
  ✓ "Are there papers on regulatory compliance for AI?" → topic (regulatory compliance for AI is RA)
  ✓ "Societal impact of AI" → topic (societal impact is an RA topic)
  Note: "IA" = "AI" (Spanish acronym inversion); treat identically.

PROJECT PRIORITY: If the query contains "project(s)" or "proyect(s)" (typo) → project, NOT topic.
  ✓ "Are there any projects on elderly care and AI?" → project
  ✓ "What proyects are fanded by Horizon 2020?" → project

OUT_OF_SCOPE TASK REQUESTS: Any query asking you to write/draft/help write = out_of_scope.
  ✓ "Help me write a report on responsible AI" → out_of_scope

PAPERS: Requires a specific university OR visualisation. No university = general.
  ✓ "Papers from Lithuanian researchers" → papers
  ✓ "How many peipers has KK published?" → papers (peipers=papers)
  ✗ "Papers on deep learning" (no university) → general

TYPO TOLERANCE: "peipers"=papers, "proyects"=projects, "fearness"=fairness, "reserch"=research, "reserchers"=researchers, "regulatori"=regulatory, "artikels"=articles, "IA"=AI, "acces"=access, "publicacions"=publications.

Respond with ONLY a JSON object:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "...", "output_format": "..."}
Fill only relevant fields. Use "" for fields that don't apply.
Set output_format to "figure" if the query asks for a visualisation/chart/map, otherwise "text".

USER QUERY: {query}"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Minimal LLM-based seed for 9-class taxonomy."""
    _AGENT_FILE = __file__

    def _llm_classify(self, query: str) -> dict:
        """Ask the LLM to classify the query. Returns parsed JSON."""
        prompt = CLASSIFY_PROMPT.replace("{query}", query)
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = response.choices[0].message.content.strip()
            if "```" in text:
                match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
                text = match.group(1).strip() if match else text
            json_match = re.search(r'\{[^{}]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(text)
        except Exception as e:
            print(f"[LLM_A] Classification error: {e}")
            return {"category": "out_of_scope"}

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model
        if not self._chromadb_initialized:
            self._init_chromadb()
        classification = self._llm_classify(user_message)
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
        classification = self._llm_classify(user_message)
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
