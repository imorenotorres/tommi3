"""
RAG Study (9-class) — LLM-based Classifier
MINIMAL SEED — 10Oct Construction Run A-std (standard-only condition)

Classification prompt derived solely from the 9-class taxonomy definitions.
No development set examples have been seen. This identical seed is the
starting point for LLM construction runs A-std, B-std, C-std; each run
will independently refine the prompt using ONLY standard (non-variant)
development queries (ablation condition).

Construction protocol (--variants standard):
  1. Start with this minimal prompt (taxonomy definitions only)
  2. Run constructor --variant llm_A_std --variants standard
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

REASONING_LABEL = "LLM classification (9-class, 10Oct, run-A-std seed)"

CLASSIFY_PROMPT = """---
You are a query classifier for a Responsible AI research assistant.
Classify the user query into exactly ONE of these 9 categories:

1. meta — queries about what this agent can do, what data it has access to, or how it works
2. organization — factual queries about UNINOVIS (the European university alliance) or its member institutions
3. out_of_scope — non-research requests: task requests (write, translate, cook, book, schedule, proofread), greetings, trivia, opinions, personal advice
4. general — research or academic questions NOT about Responsible AI (e.g. deep learning, NLP, robotics, quantum computing, bioinformatics, compiler optimisation)
5. papers — queries about publications AT A SPECIFIC UNIVERSITY, or requests for a visualisation/chart/graph of publication data
6. researcher — queries about a specific person's research or publications, or asking to list/find researchers at a university
7. project — queries about named research projects or asking to list/find projects (e.g., Horizon 2020, EU-funded initiatives)
8. topic — queries surveying a Responsible AI research area (AI ethics, fairness, explainability, accountability, transparency, AI governance, AI bias, AI safety, trustworthy AI, regulatory compliance, societal impact), including research gap analysis
9. glossary — definitional queries: "what is X?", "define X", "what does X mean?", "how is X different from Y?" where X is a Responsible AI term

University codes: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

DISAMBIGUATION NOTES:
- For definitional queries about Responsible AI terms, use "glossary" (e.g., "What is machine learning?" → glossary).
- Queries about researchers working on Responsible AI topics (e.g., "Researchers working on explainable AI in UNINOVIS") belong in "researcher".
- Queries about named or funded projects (e.g., "What projects are funded by Horizon 2020?") belong in "project".
- Queries about projects related to Responsible AI topics (e.g., "Are there any projects on elderly care and AI?") belong in "project".

Respond with ONLY a JSON object:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "...", "output_format": "..."}
Fill only relevant fields. Use "" for fields that don't apply.
Set output_format to "figure" if the query asks for a visualisation/chart/map, otherwise "text".

USER QUERY: {query}
---"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Minimal LLM-based seed for 9-class taxonomy (std-only condition)."""
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
            print(f"[LLM_A_std] Classification error: {e}")
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
