"""
RAG Study — Variant 4: LLM-Guided (LLM Classification)

Non-deterministic LLM classification followed by shared programmatic
response paths (identical to V3).

Architecture:
  1. Perception: receive query
  2. Reasoning: LLM classifies → returns query_type + extracted entities
  3. Action: shared dispatch → programmatic response or LLM fallback
  4. Production: same paths as V3

The only difference with V3 is step 2: LLM classification vs code patterns.
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from shared_dispatch import dispatch, build_llm_context

REASONING_LABEL = "LLM classification"

# Classification prompt sent to the LLM
CLASSIFY_PROMPT = """You are a query classifier for a Responsible AI research assistant.
Given the user's query, classify it into exactly ONE of these categories and extract relevant entities.

CATEGORIES (in priority order — use the FIRST matching category):
- meta: Questions about the agent itself ("What can you do?", "How does this work?", "What is UNINOVIS?", "Who are you?")
- non_research: Requests to PERFORM a task — write essays, translate, book flights, get recipes, report weather, sports results. Use this for ANY action request, even if the topic seems off-topic. Examples: "Can you book me a flight?", "What is the weather today?", "Write me an essay", "Who won the World Cup?", "Give me a recipe"
- figure: Requests containing "figure", "map", "chart", "graph", or "visualise" for data visualisation
- project: Questions mentioning specific research PROJECTS or grants, OR asking to LIST research projects. Examples: "What is the TAILOR project?", "List research projects on trustworthy AI", "Show me projects about X"
- researcher: Questions about a specific PERSON's publications or research interests. Must mention a person's name.
- glossary: Conceptual "What is X?" questions ONLY about terms that are clearly Responsible AI concepts (explainable AI, fairness, EU AI Act, trustworthy AI, AI bias, AI governance, etc.). Do NOT use this for general/ambiguous questions like "Is AI dangerous?" or topics outside Responsible AI like "quantum computing".
- gap: Questions about topics NOT studied, research gaps, missing areas, underexplored subtopics
- topic_search: Requests for PAPERS or PUBLICATIONS on a specific research topic (NOT projects)
- university_papers: Requests for papers or researchers from a specific university (must mention a university name or acronym)
- off_topic: Questions that are clearly outside Responsible AI AND are not task requests. Examples: "What is quantum computing?", "Hello", "Explain photosynthesis". NOT for task requests (those are non_research).
- followup: Short follow-ups referring to previous context ("tell me more", "expand on that")
- general: Broad or ambiguous Responsible AI questions that don't match a specific category above. Examples: "Is AI dangerous?", "Can AI be trusted?", "What is a language model?"

IMPORTANT DISTINCTIONS:
- non_research vs off_topic: If the user asks to DO something (write, translate, book, cook), it's non_research. If they ask a KNOWLEDGE question outside scope, it's off_topic.
- glossary vs general: Only use glossary for well-defined Responsible AI terms. For broad questions ("Is AI dangerous?") or terms not in the RA glossary ("quantum computing"), use general or off_topic.
- project vs topic_search: If the query mentions "project(s)", use project. If it asks for "papers" or "publications", use topic_search.

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
    """LLM classification → shared dispatch with V3."""
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
            print(f"[LLM_GUIDED] Raw LLM response: {text[:300]}")
            # Extract JSON from response (handle markdown code blocks)
            if "```" in text:
                match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
                text = match.group(1).strip() if match else text
            # Try to find JSON object in the response
            json_match = re.search(r'\{[^{}]*\}', text)
            if json_match:
                result = json.loads(json_match.group())
                print(f"[LLM_GUIDED] Parsed classification: {result}")
                return result
            # Last resort: try parsing the whole text
            result = json.loads(text)
            print(f"[LLM_GUIDED] Parsed classification: {result}")
            return result
        except Exception as e:
            print(f"[LLM_GUIDED] Classification error: {e}")
            print(f"[LLM_GUIDED] Raw text was: {text[:300] if 'text' in dir() else 'N/A'}")
            return {"category": "general"}

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: LLM classification (non-deterministic)
        classification = self._llm_classify(user_message)
        print(f"[LLM_GUIDED] Classification: {classification}")

        # Step 2: Shared dispatch (identical to V3)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            return result + "\n\n" + trace

        # Step 3: LLM fallback (identical to V3)
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

        # Step 1: LLM classification (non-deterministic)
        classification = self._llm_classify(user_message)
        print(f"[LLM_GUIDED] Classification: {classification}")

        # Step 2: Shared dispatch (identical to V3)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            yield result
            if trace:
                yield ("trace", trace)
            return

        yield ("status", "Searching...")

        # Step 3: LLM fallback (identical to V3)
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
