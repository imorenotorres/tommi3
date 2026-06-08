"""
RAG Study — Baseline: Vanilla RAG

Simplest architecture: BM25 retrieval + LLM. No classification,
no structured data, no programmatic paths. Every query follows the
same pipeline: retrieve chunks → send to LLM → return response.

This establishes what vanilla RAG can do with documents alone.
"""

import os
import sys

# Add paths for base classes and web modules
_STUDY_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))

from base import BaseRAGAgent
from base.vectorless_mixin import VectorlessMixin

# Load the system prompt from prompt.md
_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt.md")
with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    # Skip the markdown heading line
    _lines = _f.readlines()
    _SYSTEM_PROMPT = "".join(line for line in _lines if not line.startswith("# ")).strip()


class Agent(VectorlessMixin, BaseRAGAgent):
    """Vanilla RAG — BM25 retrieval + LLM, nothing else."""
    _AGENT_FILE = __file__

    @property
    def _agent_dir(self):
        """Override agent dir to point to shared data."""
        return os.path.dirname(os.path.abspath(__file__))

    def _build_system_prompt(self) -> str:
        """Use the fixed baseline prompt instead of the config-driven one."""
        return _SYSTEM_PROMPT

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Retrieve BM25 context
        context = self._retrieve_context(user_message)

        # Build prompt
        system = self._build_system_prompt()
        if context:
            system = system.replace("{context}", context)
        else:
            system = system.replace("{context}", "(No relevant documents found.)")

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Single LLM call
        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        return response.choices[0].message.content

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        yield ("status", "Searching...")

        # Retrieve BM25 context
        context = self._retrieve_context(user_message)

        # Build prompt
        system = self._build_system_prompt()
        if context:
            system = system.replace("{context}", context)
        else:
            system = system.replace("{context}", "(No relevant documents found.)")

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Stream LLM response
        async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content
