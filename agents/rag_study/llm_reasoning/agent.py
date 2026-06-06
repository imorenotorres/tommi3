"""
RAG Study — Variant 2: LLM Reasoning

BM25 retrieval + metadata + LLM-based classification (via prompt) + post-processing.
Classification and response are FUSED in a single LLM call — the prompt instructs
the LLM to identify the query type and respond accordingly.

Unlike Variant 3 (Procedural), there is no code classification chain and no
programmatic response paths. The LLM manages everything.

Unlike Variant 1 (Baseline), this variant has:
- Metadata injected into context (papers count, researchers, glossary, projects)
- Post-processing pipeline (paper verification, authority sanitisation, etc.)
- Complex prompt with query type instructions
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Loads metadata but skips the classification chain — LLM does everything."""
    _AGENT_FILE = __file__

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()
        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"

        # Retrieve BM25 context
        context = self._retrieve_context(user_message)

        # Build system prompt with metadata context
        system = self._build_system_prompt()
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system += f"\n\n{metadata_ctx}"

        # Inject glossary if available
        glossary_ctx = self._build_glossary_context(user_message)
        if glossary_ctx:
            system += f"\n\nGLOSSARY CONTEXT:\n{glossary_ctx}"

        # Inject researcher data if query mentions a name
        if self._query_mentions_researcher(user_message):
            researcher_ctx = self._build_researcher_context(user_message)
            if researcher_ctx:
                system += f"\n\nRESEARCHER DATA:\n{researcher_ctx}"

        # Inject project data if query mentions projects
        project_ctx = self._build_project_context(user_message)
        if project_ctx:
            system += f"\n\nPROJECT DATA:\n{project_ctx}"

        if context:
            system += f"\n\n--- Retrieved Document Context ---\n{context}"

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Single fused LLM call — classification + response together
        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        result = response.choices[0].message.content

        # Post-processing pipeline (same as Procedural)
        result = self._sanitize_authority(result)
        if hasattr(self, '_verify_papers'):
            result = self._verify_papers(result)
        if hasattr(self, '_inject_unsolicited_gap_banner'):
            is_gap = self._is_gap_analysis_query(user_message) if hasattr(self, '_is_gap_analysis_query') else False
            result = self._inject_unsolicited_gap_banner(result, is_gap)

        return result

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            init_msg = getattr(self, '_init_status_message', "Initializing...")
            yield ("status", init_msg)
            self._init_chromadb()

        yield ("status", "Thinking...")

        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"
            return

        # Retrieve BM25 context
        context = self._retrieve_context(user_message)

        # Build system prompt with metadata
        system = self._build_system_prompt()
        metadata_ctx = self._build_metadata_context()
        if metadata_ctx:
            system += f"\n\n{metadata_ctx}"

        glossary_ctx = self._build_glossary_context(user_message)
        if glossary_ctx:
            system += f"\n\nGLOSSARY CONTEXT:\n{glossary_ctx}"

        if self._query_mentions_researcher(user_message):
            researcher_ctx = self._build_researcher_context(user_message)
            if researcher_ctx:
                system += f"\n\nRESEARCHER DATA:\n{researcher_ctx}"

        project_ctx = self._build_project_context(user_message)
        if project_ctx:
            system += f"\n\nPROJECT DATA:\n{project_ctx}"

        if context:
            system += f"\n\n--- Retrieved Document Context ---\n{context}"

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Fused LLM call — stream response
        full_response = ""
        async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                text = chunk.data.choices[0].delta.content
                full_response += text
                yield text

        # Post-processing on full response (streamed via replace event)
        processed = self._sanitize_authority(full_response)
        if hasattr(self, '_inject_unsolicited_gap_banner'):
            is_gap = self._is_gap_analysis_query(user_message) if hasattr(self, '_is_gap_analysis_query') else False
            processed = self._inject_unsolicited_gap_banner(processed, is_gap)

        if processed != full_response:
            yield ("replace", processed)
