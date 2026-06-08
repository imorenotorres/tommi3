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
- meta: Questions about the agent itself ("What can you do?", "How does this work?", "What is UNINOVIS?", "Who are you?")
- non_research: Requests to PERFORM a task — write essays, translate, book flights, get recipes, report weather, sports results. Use this for ANY action request, even if the topic seems off-topic. Examples: "Can you book me a flight?", "What is the weather today?", "Write me an essay", "Who won the World Cup?", "Give me a recipe"
- figure: Requests containing "figure", "map", "chart", "graph", or "visualise" for data visualisation
- project: Questions mentioning specific research PROJECTS or grants, OR asking to LIST research projects. Examples: "What is the TAILOR project?", "List research projects on trustworthy AI", "Show me projects about X"
- researcher: Questions about a specific PERSON's publications or research interests. Must mention a person's name. Examples: "Papers by [name]", "What has [name] published?", "Publications by [name]". If a query mentions a person's name, it is ALWAYS researcher, even if it also mentions a university or topic.
- glossary: Conceptual "What is X?" questions ONLY about terms that are clearly Responsible AI concepts (explainable AI, fairness, EU AI Act, trustworthy AI, AI bias, AI governance, etc.). Do NOT use this for general/ambiguous questions like "Is AI dangerous?" or topics outside Responsible AI like "quantum computing".
- gap: Questions about topics NOT studied, research gaps, missing areas, underexplored subtopics
- topic_search: Requests for PAPERS or PUBLICATIONS on a specific research topic (NOT projects)
- university_papers: Requests for papers or researchers from a specific university (must mention a university name or acronym)
- off_topic: Questions that are clearly outside Responsible AI AND are not task requests. Examples: "What is quantum computing?", "Hello", "Explain photosynthesis", "Things to do". NOT for task requests (those are non_research). Also use for vague, meaningless, or greeting-like inputs.
- followup: Short follow-ups referring to previous context ("tell me more", "expand on that")
- general: Broad or ambiguous Responsible AI questions that don't match a specific category above. Examples: "Is AI dangerous?", "Can AI be trusted?", "What is a language model?". Use this for any question that relates to AI/technology but doesn't fit a more specific category. "What is a language model?" is general (AI-related), NOT off_topic.

IMPORTANT DISTINCTIONS:
- non_research vs off_topic: If the user asks to DO something (write, translate, book, cook), it's non_research. If they ask a KNOWLEDGE question outside scope or send a vague/meaningless input ("Things to do", "Hello"), it's off_topic.
- glossary vs general: Only use glossary for well-defined Responsible AI terms. For broad questions ("Is AI dangerous?") or terms not in the RA glossary ("quantum computing", "language model"), use general or off_topic.
- general vs off_topic: If the question is about AI or technology (even broadly), it's general. If it has nothing to do with AI, it's off_topic.
- project vs topic_search: If the query mentions "project(s)", use project. If it asks for "papers" or "publications", use topic_search.
- topic_search vs university_papers: If a query mentions a TOPIC (e.g. "AI in education", "AI ethics"), use topic_search — even if it also mentions a university or "UNINOVIS". Use university_papers ONLY when asking for ALL papers/researchers from a university without specifying a topic (e.g. "List all papers from UDCLV", "Who are the researchers at THUAS?").

UNIVERSITIES (use these acronyms): UMA, THUAS, USPN, UDCLV, THWS, TAMK, KK, UT

Respond with ONLY a JSON object, no explanation:
{"category": "...", "topic": "...", "researcher": "...", "university": "...", "project": "..."}

- Fill only the relevant fields. Use empty string "" for fields that don't apply.
- For "topic": extract the research topic if mentioned (e.g. "AI ethics", "explainable AI")
- For "researcher": extract the person's name if mentioned
- For "university": extract the university acronym if mentioned
- For "project": extract the project name if mentioned

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
