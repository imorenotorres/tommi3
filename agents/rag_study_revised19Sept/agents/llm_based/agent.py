"""
RAG Study (9-class) — LLM-based Classification (Iteration 0)

LLM classification using a separate LLM call, followed by shared
programmatic response paths (identical to auto_rule_based variant).

9-class taxonomy (Layer 1):
  papers, researcher, project, topic, glossary, organization, meta,
  general, out_of_scope

  general    — Research/academic/STEM questions NOT about Responsible AI
  out_of_scope — Non-research queries: task requests, greetings, trivia,
                 opinions, personal advice

Construction protocol:
  1. Start with minimal prompt based only on the taxonomy descriptions
  2. Run constructor against development_set_9class.json
  3. Analyse misclassifications
  4. Refine prompt to fix errors
  5. Repeat until convergence

Iteration 0: Minimal classification prompt derived solely from the
9-class category definitions. No development set queries have been seen yet.
"""

import os
import sys
import json
import re

# Add paths
_AGENT_DIR = os.path.dirname(os.path.realpath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(_AGENT_DIR))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "LLM classification (9-class, iteration 0)"

CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Given the user's query, classify it into exactly ONE of these 9 categories.

CATEGORIES (use the FIRST matching category):
1. out_of_scope: Non-research queries only — task requests (write, translate, book, schedule, cook, proofread), greetings ("Hello"), trivia ("Who won the World Cup?"), opinions ("Is AI dangerous?"), personal advice, and other non-research questions (weather, geography, recipes). NOT for research questions about topics outside AI.
2. general: Valid research or academic/technical questions that are NOT about Responsible AI. Examples: deep learning architectures, computer vision, robotics, NLP methods, bioinformatics, quantum computing/algorithms, blockchain, IoT, autonomous vehicles, medical image analysis, neural architecture search, graph neural networks. Also: "Papers about deep learning", "Find research on computer vision". NOT: queries about fairness, explainability, AI ethics, AI governance — those are topic.
3. meta: Queries about the agent itself, its capabilities, data sources, or how it works.
4. organization: Factual queries about UNINOVIS as an alliance or its member institutions (which universities, how many partners, which countries). NOT research content questions.
5. papers: Queries whose primary object is a set of publications AT A SPECIFIC UNIVERSITY, or requests for data VISUALISATION about publications (figure/chart/graph/map). Use when: (a) a university code is mentioned + papers/publications requested, (b) a figure/chart/graph/map about publications/research output is requested. University codes: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT.
6. researcher: Queries about a specific PERSON's publications or interests, or asking to list/find researchers at a university.
7. project: Queries mentioning named research projects or asking to list/find projects.
8. topic: Queries surveying a Responsible AI research area — asking about papers/publications on an RA topic WITHOUT specifying a university, or asking about research gaps. RA topics include: AI ethics, fairness, explainability, interpretability, accountability, transparency, AI governance, AI bias, AI safety, AI regulation, trustworthy AI, responsible AI, data privacy, algorithmic decision-making, deepfakes, AI surveillance.
9. glossary: Definitional queries about a specific Responsible AI term (explainable AI/XAI, fairness, EU AI Act, trustworthy AI, interpretability, AI governance, AI bias, accountability, transparency). NOT definitions of general computing terms.

KEY DISTINCTIONS:
- general vs out_of_scope: "Papers on deep learning" = general (research question, outside RA). "Write me an essay" = out_of_scope (task request, not research).
- general vs topic: "Research on machine learning fairness" = topic (RA domain). "Research on computer vision" = general (not RA domain).
- papers vs topic: When asking about papers on an RA topic WITHOUT a university → topic. When a specific university is mentioned → papers.
- "per partner" in a visualisation = papers (university partner data), NOT organization.
- "research gaps in UNINOVIS" = topic (about research content), NOT organization.

UNIVERSITIES: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

Respond with ONLY a JSON object:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "...", "output_format": "..."}
Fill only relevant fields. Use "" for fields that don't apply.
Set output_format to "figure" if the query asks for a visualisation/chart/map, otherwise "text".

USER QUERY: {query}"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """LLM classification (9-class) -> shared dispatch."""
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
            # Extract JSON from response (handle markdown code blocks)
            if "```" in text:
                match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
                text = match.group(1).strip() if match else text
            json_match = re.search(r'\{[^{}]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(text)
        except Exception as e:
            print(f"[LLM_BASED] Classification error: {e}")
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
