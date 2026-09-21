"""
RAG Study (9-class) — LLM-based Classifier
MINIMAL SEED — 19BSept Construction Run C

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

REASONING_LABEL = "LLM classification (9-class, 19BSept, run-C iter-3)"

CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI (RA) research assistant.
Classify the query into ONE of 9 categories. Learn from these examples:

--- meta ---
"What can you do?" → meta
"What data do you have access to?" → meta
"What topics can you help me with?" → meta
"What is your scope?" → meta
"Do you have access to UNINOVIS publications?" → meta  [asking about YOUR data access, not about UNINOVIS]
"Have you access to UNINOVIS publications?" → meta  [same: what data do YOU have]

--- organization ---
"What is UNINOVIS?" → organization
"Which universities are in UNINOVIS?" → organization
"What is UMA's role in the alliance?" → organization
"How many members does UNINOVIS have?" → organization

--- out_of_scope ---
"Hello!" → out_of_scope
"Help me write a report on responsible AI" → out_of_scope  [task request]
"Write a summary of AI ethics" → out_of_scope  [task request]
"What is the capital of France?" → out_of_scope
"What is your opinion about AI regulation?" → out_of_scope  [asking for opinion]
"What your opinion about the AI regulation?" → out_of_scope  [broken grammar, still opinion request]

--- general ---
"What is machine learning?" → general  [ML is NOT an RA term]
"What is NLP?" → general  [NLP is NOT an RA term]
"Research on compiler optimisation" → general  [compiler optimisation is NOT RA]
"Research on neural machine translation" → general  [NMT is NOT RA]
"Are there any studies on NLP for code generation?" → general  [NLP + code generation = non-RA]
"What is the latest in quantum computing research?" → general  [quantum computing is NOT RA]
"I need publications on neural machine translation" → general  [NMT = non-RA, no university specified]
"Papers on deep learning for image recognition" → general  [no university, non-RA topic]
"Robotics research" → general
RULE: If the domain is machine learning, deep learning, NLP, computer vision, quantum computing, robotics, bioinformatics, compiler optimisation, blockchain, IoT — and NO RA term is present → general

--- papers ---
"How many papers has UMA published?" → papers
"Publications from THUAS" → papers
"Papers from Lithuanian researchers" → papers  [national origin → university output]
"How many peipers has KK published?" → papers  [peipers=papers, KK is a university code]
"List all papers of THUAS researchers" → papers  [THUAS is a university code → papers, not researcher]
"Show publications of TAMK about AI ethics" → papers  [TAMK is a university code → papers]
"Show me a chart of publications by university" → papers, output_format=figure
RULE: If a university code (UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT) is present → papers takes priority. "papers of [UNI_CODE] researchers" → papers (the university code means it's a university output query).

--- researcher ---
"Who works on explainability at UMA?" → researcher
"Researchers working on explainable AI in UNINOVIS" → researcher  [researchers = person query]
"List researchers at THUAS" → researcher  [listing people at a university]
"What has Maria Garcia published?" → researcher
"Find publications by Giulio Iannello" → researcher  [named person → researcher, not papers]
"Find publications of Giulio Iannello" → researcher  [named person → researcher]
"Find publicacions by Gulio Ianello" → researcher  [typos don't change: named person]
"Who in UNINOVIS works on both AI fairness and interpretability?" → researcher
RULE: "publications by/of [Person Name]" → researcher (not papers). BUT "publications of [UNI_CODE]" → papers. Distinguish: person name (mixed case, not a university code) → researcher; university code → papers.

--- project ---
"What projects are funded by Horizon 2020?" → project
"Are there any projects on elderly care and AI?" → project  [projects keyword → project, not topic]
"List research projects at UNINOVIS" → project
"Tell me about the TAILOR project" → project
"Describe the DUCA project" → project
"What proyects are fanded by Horizon 2020?" → project  [proyects=projects]

--- topic ---
"Research on AI fairness" → topic
"What has been done on explainability?" → topic
"Articles about AI governance" → topic
"Gap analysis in trustworthy AI research" → topic
"Research on machine learning fairness" → topic  [fairness is RA; no university; no "projects"]
"Reserch on machine lerning fearness" → topic  [reserch=research, lerning=learning, fearness=fairness]
"Are there papers on regulatory compliance for AI?" → topic  [regulatory compliance for AI = RA topic, no university]
"There are papers about regulatory compliance for AI?" → topic  [inverted grammar, still topic]
"Articles about the societal impact of AI" → topic  [societal impact = RA topic]
"Artikels abaut the societal impact of IA" → topic  [artikels=articles, IA=AI]
RULE: If RA term present (fairness, explainability, AI governance, regulatory compliance, societal impact of AI, AI bias, AI safety, accountability, transparency) AND no university specified AND no "projects" keyword → topic

--- glossary ---
"What is explainability?" → glossary
"Define AI fairness" → glossary
"How is trustworthy AI different from responsible AI?" → glossary  [definitional comparison]
"What does XAI mean?" → glossary
RULE: Only RA-specific concepts go to glossary. Machine learning, NLP, quantum computing, etc. → general.

University codes: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT
Typo tolerance: "peipers"=papers, "proyects"=projects, "fearness"=fairness, "reserch"=research, "reserchers"=researchers, "regulatori"=regulatory, "artikels"=articles, "IA"=AI.

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
            print(f"[LLM_C] Classification error: {e}")
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
