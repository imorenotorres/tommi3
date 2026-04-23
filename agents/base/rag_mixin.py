from .claims import GroundingAnalyzer
from .badges import ReliabilityBadge, AuditLogger


class SimpleRAGMixin:
    """Mixin providing chat() and chat_stream() for simple RAG agents."""

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        """Send a message with RAG context and return the response."""
        # Use per-request overrides or fall back to instance defaults
        transparency = kwargs.get('transparency_override') or self._transparency
        model = kwargs.get('model_override') or self.model
        prompt_level = kwargs.get('prompt_level_override') or self._prompt_level

        # Ensure ChromaDB is initialized (lazy)
        if not self._chromadb_initialized:
            self._init_chromadb()

        if self._chromadb_error:
            err = self._chromadb_error
            return f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"

        context = self._retrieve_context(user_message)

        system_with_context = self._build_system_prompt()
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(
            model=model,
            messages=messages
        )

        llm_content = response.choices[0].message.content

        # Post-process: convert PDF filename mentions into clickable links
        if hasattr(self, '_linkify_pdf_sources'):
            llm_content = self._linkify_pdf_sources(llm_content)

        # Compute reliability badge
        badge, breakdown, reliability_label = ReliabilityBadge.compute_badge_and_breakdown(
            llm_content, context,
            transparency=transparency,
            green_max=self._reliability_green_max_llm,
            red_min=self._reliability_red_min_llm,
            highlight_config=self._config.get("inline_claim_highlights"),
            is_not_found=self._is_not_found_response(llm_content),
            prompt_level=prompt_level,
            model_name=self.model_display_name,
            is_local_llm=self._is_local_llm,
        )
        response_content = badge + llm_content

        # Audit log
        is_followup = self._is_followup_query(user_message) and history
        AuditLogger.log(
            audit_path=self._audit_path,
            enabled=self._audit_enabled,
            agent_id=self._config.get("agent_id", "unknown"),
            query=user_message,
            query_type="followup" if is_followup else "normal",
            breakdown=breakdown,
            reliability_label=reliability_label,
            transparency=transparency,
            prompt_level=prompt_level,
            model_name=self.model_display_name,
            is_local_llm=self._is_local_llm,
        )

        self._query_history.append({
            'question': user_message,
            'response_length': len(response_content)
        })

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        """Send a message with RAG context and stream the response."""
        # Use per-request overrides or fall back to instance defaults
        transparency = kwargs.get('transparency_override') or self._transparency
        model = kwargs.get('model_override') or self.model
        prompt_level = kwargs.get('prompt_level_override') or self._prompt_level

        # Ensure ChromaDB is initialized (lazy)
        if not self._chromadb_initialized:
            yield ("status", "Creating ChromaDB for the agent...")
            self._init_chromadb()

        yield ("status", "Thinking...")

        if self._chromadb_error:
            err = self._chromadb_error
            yield f"**Error {err['error_code']}:** {err['error']}\n\n{err.get('instructions', '')}"
            return

        context = self._retrieve_context(user_message)

        system_with_context = self._build_system_prompt()
        if context:
            system_with_context += f"\n\nRelevant context from the knowledge base:\n{context}"

        messages = [{"role": "system", "content": system_with_context}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Stream response
        full_response = ""
        async for chunk in await self.client.chat.stream_async(
            model=model,
            messages=messages
        ):
            if chunk.data.choices[0].delta.content:
                full_response += chunk.data.choices[0].delta.content
                yield chunk.data.choices[0].delta.content

        # Post-process: convert PDF filename mentions into clickable links
        if hasattr(self, '_linkify_pdf_sources'):
            linkified = self._linkify_pdf_sources(full_response)
            if linkified != full_response:
                full_response = linkified
                yield ("replace", full_response)

        # Deferred reliability badge + inline highlights
        badge, breakdown, reliability_label = ReliabilityBadge.compute_badge_and_breakdown(
            full_response, context,
            transparency=transparency,
            green_max=self._reliability_green_max_llm,
            red_min=self._reliability_red_min_llm,
            highlight_config=self._config.get("inline_claim_highlights"),
            is_not_found=self._is_not_found_response(full_response),
            prompt_level=prompt_level,
            model_name=self.model_display_name,
            is_local_llm=self._is_local_llm,
        )
        if badge:
            yield ("badge", badge)

        # Send claim highlights (development only)
        if transparency == "crystal_box":
            import json
            highlight_cfg = self._config.get("inline_claim_highlights", {})
            if highlight_cfg.get("enabled", False) and breakdown.get("total_claims", 0) > 0:
                yield ("claim_highlights", json.dumps({
                    "grounded": breakdown.get("grounded_claims", []),
                    "ungrounded": breakdown.get("ungrounded_claims", []),
                    "grounded_style": highlight_cfg.get("grounded_style", ""),
                    "ungrounded_style": highlight_cfg.get("ungrounded_style", ""),
                }))

        # Audit log
        is_followup = self._is_followup_query(user_message) and history
        AuditLogger.log(
            audit_path=self._audit_path,
            enabled=self._audit_enabled,
            agent_id=self._config.get("agent_id", "unknown"),
            query=user_message,
            query_type="followup" if is_followup else "normal",
            breakdown=breakdown,
            reliability_label=reliability_label,
            transparency=transparency,
            prompt_level=prompt_level,
            model_name=self.model_display_name,
            is_local_llm=self._is_local_llm,
        )

        self._query_history.append({
            'question': user_message,
            'response_length': len(full_response)
        })
