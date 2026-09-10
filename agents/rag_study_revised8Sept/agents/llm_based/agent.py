"""
RAG Study — LLM-based Classification (Non-Deterministic)

LLM classification using a separate LLM call, followed by shared
programmatic response paths (identical to Rule-based variant).

Architecture:
  1. Perception: receive query
  2. Reasoning: LLM classifies → returns query_type + extracted entities
  3. Action: shared dispatch → programmatic response or LLM fallback
  4. Production: same paths as Rule-based variant
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

REASONING_LABEL = "LLM classification"

# Initial classification prompt — built from expert_input.md Phase A
CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Given the user's query, classify it into exactly ONE of these categories and extract relevant entities.

CATEGORIES (in priority order — use the FIRST matching category):
1. researcher: Questions about a specific PERSON's publications or research interests. Must mention a person's name OR ask about "researchers" at a university. Examples: "Papers by [name]", "What has [name] published?", "List all THUAS researchers", "Any TAMK researcher in the database?"
2. project: Questions mentioning research PROJECTS or grants, OR asking to list projects. Examples: "What is the TAILOR project?", "List research projects on trustworthy AI", "Any research projects in KK?"
3. papers: Requests for papers from a specific UNIVERSITY. Use when the query mentions a university and asks about papers/publications/output WITHOUT specifying a particular research topic. Examples: "List all papers from UDCLV", "Papers from the Italian partner", "List papers from UDCLV on AI in healthcare" (university + topic = papers, NOT topic_search)
4. glossary: Conceptual "What is X?" or "Define X" questions about Responsible AI terms (explainable AI, fairness, EU AI Act, trustworthy AI, AI bias, AI governance, interpretability). Also "How do X and Y differ?" about RA concepts.
5. figure: Requests for data visualisation — "figure", "map", "chart", "graph", "visualise"
6. meta: Questions about the agent itself ("What can you do?", "How does this work?", "What is UNINOVIS?"). Greetings like "Hello", "Hi", "Good morning" are NOT meta — they are non_research.
7. non_research: Requests to PERFORM a task (write, translate, book, cook) OR simple factual questions unrelated to AI research. Examples: "Write me an essay", "Who won the World Cup?", "What is the capital of France?", "Things to do", "What is the weather today?". Greetings ("Hello", "Hi", "Good morning") and meaningless inputs ("test", "asdf") are off_topic, NOT non_research.
8. off_topic: Questions that are about a domain OUTSIDE Responsible AI and are NOT task requests. Examples: "What is quantum computing?", "Explain photosynthesis". Also: queries asking about papers/researchers on topics completely outside the database scope (e.g. "List papers about coffee making", "Find researchers working on German poetry").
9. followup: Short follow-ups referring to previous context ("tell me more", "expand on that", "can you give more details?")
10. gap: Questions about topics NOT studied, research gaps, missing areas, underexplored subtopics
11. general: Broad or ambiguous AI questions that don't match a more specific category. Examples: "Is AI dangerous?", "Can AI be trusted?", "What is a language model?", "Should students use LLMs for homework?"
12. topic_search: Requests for papers on a TOPIC without mentioning a specific university. Use ONLY when the query asks about publications on a research topic and does NOT mention a university. Examples: "Papers on AI ethics", "Research on AI in education", "Research on AI in education within UNINOVIS" (mentioning UNINOVIS is OK — it means within the database, not a specific university)

IMPORTANT DISTINCTIONS:
- non_research vs off_topic: Task requests ("write", "translate", "book") AND simple real-world factual questions ("capital of France", "weather", "Things to do") are non_research. Knowledge questions outside AI scope are off_topic.
- papers vs topic_search: If the query mentions a UNIVERSITY, use papers (even if it also mentions a topic). Use topic_search ONLY when no university is mentioned.
- off_topic for out-of-scope research: If someone asks for papers/researchers on a topic that has nothing to do with AI/Responsible AI (coffee, poetry, history), use off_topic — not topic_search. But "AI in education", "AI in healthcare" etc. ARE in scope — use topic_search.
- papers vs researcher: "Which papers were written by researchers at THUAS?" asks about PAPERS (not about the researchers themselves) — use papers. Use researcher only when the focus is on the person, not their output.
- researcher: Use when asking about researchers at a university (e.g. "List THUAS researchers") — not papers.
- project: Use when the word "project(s)" appears OR a known project name is mentioned, even if a university is also mentioned.
- glossary vs general: Glossary for well-defined Responsible AI terms (explainability, fairness, EU AI Act, trustworthy AI, AI governance). General terms like "language model", "deep learning", "neural network" are general, NOT glossary — they are not specific to Responsible AI.
- papers vs topic_search: "Any papers about X" where X is a broad concept → papers. Use topic_search only for focused research topic queries without a university.

UNIVERSITIES: UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

Respond with ONLY a JSON object:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "..."}
Fill only relevant fields. Use "" for fields that don't apply.

USER QUERY: {query}"""


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """LLM classification → shared dispatch."""
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
            return {"category": "general"}

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: LLM classification (non-deterministic)
        classification = self._llm_classify(user_message)

        # Step 2: Shared dispatch (identical to Rule-based)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            return result + "\n\n" + trace

        # Step 3: LLM fallback (identical to Rule-based)
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
