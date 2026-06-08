"""
RAG Study — Variant 0: Oneshot (Baseline without retrieval)

No retrieval, no metadata, no classification. Pure LLM with system prompt.
Establishes what the LLM knows on its own about Responsible AI.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent


class Agent(BaseRAGAgent):
    """Oneshot agent — no retrieval, no mixins. LLM only."""
    _AGENT_FILE = __file__

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model
        system = self._build_system_prompt()
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        return response.choices[0].message.content

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model
        system = self._build_system_prompt()
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content
