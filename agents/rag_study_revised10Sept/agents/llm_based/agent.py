"""
RAG Study (8-class) — LLM-based Classification (Iteration 0)

LLM classification using a separate LLM call, followed by shared
programmatic response paths (identical to auto_rule_based variant).

8-class taxonomy (Layer 1):
  papers, researcher, project, topic, glossary, organization, meta, out_of_scope

Construction protocol:
  1. Start with minimal prompt based only on the taxonomy descriptions
  2. Run constructor against development_set_8class.json
  3. Analyse misclassifications
  4. Refine prompt to fix errors
  5. Repeat until convergence

Iteration 0: Minimal classification prompt derived solely from the
8-class category definitions. No development set queries have been seen yet.
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

REASONING_LABEL = "LLM classification (8-class, iteration 4)"

# Classification prompt — iteration 1: refined with disambiguation rules
# derived from error analysis on the development set.
CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Given the user's query, classify it into exactly ONE of these categories.

CATEGORIES (8-class taxonomy, use the FIRST matching category):
1. out_of_scope: Task requests (write, translate, book, cook, send), off-topic questions about non-AI domains (quantum computing, photosynthesis, coffee, poetry, history, geography), opinion questions ("Is AI dangerous?", "Should students...?", "Is it ethical...?"), greetings ("Hello"), trivia ("Who won the World Cup?"), and general knowledge questions NOT specific to Responsible AI ("What is a language model?"). Also: queries about papers/researchers in domains OUTSIDE AI (e.g. "papers about coffee making", "researchers working on German poetry").
2. papers: Queries whose primary object is a set of publications AT A SPECIFIC UNIVERSITY or requests for data VISUALISATION about publications. Use when: (a) a university is mentioned + papers/publications requested, (b) a figure/chart/graph/map about publications/research output is requested (even if "per partner" is mentioned — "partner" here means university partner, not the organization itself). Examples: "List all papers from THUAS researchers", "Show a figure with publications per partner", "Show a map with research projects per partner", "Any papers about irresponsible AI".
3. researcher: Queries about a specific PERSON's publications or interests, or asking to list researchers at a university. Must mention a person's name OR focus on researchers (not their papers). "List all papers from THUAS researchers" = papers (focus is papers). "List THUAS researchers" = researcher (focus is people).
4. project: Queries mentioning named research PROJECTS or asking to list projects.
5. topic: Queries surveying a research area, asking about publications on a topic WITHOUT specifying a university, or asking about research gaps/underexplored areas. "What are the research gaps in UNINOVIS?" = topic (asking about gaps, not about the organization). "Is AI changing education?" = topic.
6. glossary: Definitional queries about a specific Responsible AI term (explainable AI, fairness, EU AI Act, trustworthy AI, interpretability, AI governance, AI bias). NOT general computing terms.
7. organization: Factual queries about UNINOVIS as an alliance or its member institutions (which universities, how many partners, countries). NOT research content questions that merely mention UNINOVIS.
8. meta: Queries about the agent itself, its capabilities, or how it works.

IMPORTANT DISTINCTIONS:
- "per partner" in a visualisation request = papers (data about university partners), NOT organization
- "research gaps in UNINOVIS" = topic (about research content), NOT organization
- Papers/researchers on non-AI topics (coffee, poetry, history) = out_of_scope
- "What is a language model?" = out_of_scope (general knowledge, not RA-specific)
- Opinion/ethical questions = out_of_scope (even if about AI)
- "Visualise publications on X" = papers (primary object is the publications, visualised), NOT topic
- "List research projects on X" = project (asking about projects), NOT topic
- papers vs topic: When a query asks about papers/publications on a specific research TOPIC (ethics, privacy, education, fairness, bias, etc.) WITHOUT mentioning a university, it's always topic — even if it says "papers" or "publications". Examples: "Papers on AI ethics" = topic, "List papers about AI and privacy" = topic, "Any publications on AI and privacy" = topic, "Research on AI in education" = topic. Use papers ONLY when: (a) a specific university is mentioned, (b) it's a broad request without a topic filter ("Any papers about irresponsible AI" — irresponsible AI is not a well-defined topic), or (c) it's a visualisation/figure request about publication data.

UNIVERSITIES: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

Respond with ONLY a JSON object:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "...", "output_format": "..."}
Fill only relevant fields. Use "" for fields that don't apply.
Set output_format to "figure" if the query asks for a visualisation/chart/map, otherwise "text".

USER QUERY: {query}"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """LLM classification (8-class) -> shared dispatch."""
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
