"""
RAG Study (9-class) — LLM-based Classifier
MINIMAL SEED — 19BSept Construction Run B

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

REASONING_LABEL = "LLM classification (9-class, 19BSept, run-B iter-6)"

CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI (RA) research assistant.

Follow this decision procedure in order — use the FIRST rule that applies:

STEP 1 — Is this about the agent itself?
  → IF the query asks what you can do, what data you have access to, your scope, your capabilities → meta
  → "Do you have access to UNINOVIS publications?" = meta (asking about YOUR data access, not about UNINOVIS)
  → "Do you have acces to UNINOVIS publicacions?" = meta (typos don't change: this is about your data)
  → "What topics can you help me with?" = meta

STEP 2 — Is this a task request or completely off-topic?
  → Task verbs that ask you to PRODUCE content: write, draft, compose, translate, cook, book, schedule, proofread → out_of_scope
  → "Help me write a report on responsible AI" = out_of_scope
  → Opinions: "What is your opinion on X?", "What your opinion about X?" = out_of_scope (asking for your opinion)
  → "What is your opinion on AI regulation?" = out_of_scope (opinion request, NOT a glossary query)
  → "What is your opinion on AI regulacion?" = out_of_scope (regulacion=regulation, still an opinion)
  → Greetings: "Hello", "Hi" = out_of_scope
  → Trivia: capital of country, sports results = out_of_scope
  → CRITICAL — do NOT catch these as task requests; they go to STEP 4 or STEP 5:
    · "Tell me about the IntelliMan project" → goes to STEP 5 (project)
    · "Describe the DUCA project" → goes to STEP 5 (project)
    · "Describe me the DUCA project" → goes to STEP 5 (project)
    · "Find publications by Giulio Iannello" → goes to STEP 4 (researcher)
    · "What has Antonio Moreno published?" → goes to STEP 4 (researcher)
    · "List researchers at UMA" → goes to STEP 4 (researcher)

STEP 3 — Is this about UNINOVIS or a member university as an institution?
  → IF asking about the alliance, its members, countries, structure, or a university's role → organization
  University codes: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT
  → "What is UNINOVIS?" = organization (UNINOVIS is an institution, not an RA concept)

STEP 4 — Is the main subject a PERSON or a list of researchers?
  → IF asking about a specific researcher's work/publications, or listing researchers → researcher
  → "What has [Person Name] published?" = researcher — asking about a person's output
  → "What has Antonio Moreno published?" = researcher
  → "What has Antonio Moreno publised?" = researcher (publised=published)
  → "What is Antonio Moreno publications?" = researcher (broken grammar, still about a person)
  → "Find publications by Giulio Iannello" = researcher (named person, not a university)
  → "Find publications of Giulio Iannello" = researcher
  → "Find publicacions by Gulio Ianello" = researcher (typos don't change: named person)
  → "Who in UNINOVIS works on both AI fairness and interpretability?" = researcher
  → This applies even when RA topics are mentioned: the subject is people, not the RA area

STEP 5 — Is this asking about PROJECTS?
  → IF the query uses "project(s)" or "proyect(s)" (typo), OR mentions a named project → project
  → Named projects: TAILOR, IntelliMan, DUCA, MenHir, AIAS, DAIBETES, InnoGuard, Crystal, MoveCare, EMPATHIC
  → "Are there any projects on elderly care and AI?" = project
  → "Tell me about the IntelliMan project" = project (NOT out_of_scope — "tell me about" is an info request)
  → "Tell me abaut de IntelliMan proyect" = project
  → "Describe the DUCA project" = project (NOT out_of_scope — "describe" here is an info request)
  → "Describe me the DUCA project" = project (broken grammar doesn't change intent)
  → "What is the MenHir project about?" = project
  → "What projects are funded by Horizon 2020?" = project

STEP 6 — Is this a DEFINITION query about an RA term?
  → IF asking "what is X?", "define X", "how is X different from Y?" where X is an RA concept → glossary
  → RA concepts: fairness, explainability, XAI, AI governance, trustworthy AI, AI bias, accountability, transparency, EU AI Act
  → NOT glossary: "What is machine learning?" = general (ML is not an RA concept)
  → NOT glossary: "What is learning machine?" = general (inverted word order, still ML)
  → NOT glossary: "What has been done on explainability in X?" = topic (research survey, not definition)
  → NOT glossary: "What are research gaps in X?" = topic (gap analysis → STEP 9)

STEP 7 — Is this a NON-RA research domain?
  → IF about deep learning, NLP, computer vision, robotics, quantum computing, bioinformatics, compiler optimisation, etc. AND no RA term present → general

STEP 8 — Is this about publications AT A SPECIFIC UNIVERSITY?
  → IF asking for papers/publications from a specific university (UMA, THUAS, etc.) → papers
  → OR if requesting a chart/graph/visualisation of publication data → papers (output_format: figure)
  → "Papers from Lithuanian researchers" = papers
  → "Show me the publication timeline for UMA as a chart" = papers, output_format=figure

STEP 9 — Is this a survey of an RA research area?
  → IF asking about research/papers on an RA topic WITHOUT a specific university → topic
  → "What are research gaps in AI ethics?" = topic (gap analysis = topic, not glossary)
  → "What has been done on explainability in high-stakes AI decisions?" = topic (research survey)
  → "Research on machine learning fairness" = topic (fairness is RA)
  → RA topics: fairness, explainability, AI governance, regulatory compliance, societal impact of AI, AI bias, AI safety, trustworthy AI, accountability, transparency, AI ethics

STEP 10 — Fallback → out_of_scope

Typo tolerance: "peipers"=papers, "fearness"=fairness, "reserch"=research, "reserchers"=researchers, "proyects"=projects, "regulatori"=regulatory, "publised"=published, "acces"=access, "regulacion"=regulation.

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
            print(f"[LLM_B] Classification error: {e}")
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
