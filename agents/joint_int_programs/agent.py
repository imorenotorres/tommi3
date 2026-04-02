"""
Joint International Programs — Simple RAG agent with LLM-based grounding verification.
Unique features: verify_grounding, token tracking.
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent

from pypdf import PdfReader


class Agent(BaseRAGAgent):
    """Joint Programs agent with optional LLM-based grounding verification."""
    _AGENT_FILE = __file__

    def __init__(self):
        super().__init__()
        # Grounding verification from .env
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Token usage tracking
        self._token_usage = {
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'queries': []
        }

    # ------------------------------------------------------------------
    # Token tracking (unique to this agent)
    # ------------------------------------------------------------------

    def _track_token_usage(self, response, question: str):
        """Track token usage from an LLM response."""
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
            completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
            total = getattr(usage, 'total_tokens', 0) or (prompt_tokens + completion_tokens)

            self._token_usage['total_prompt_tokens'] += prompt_tokens
            self._token_usage['total_completion_tokens'] += completion_tokens
            self._token_usage['total_tokens'] += total

            self._token_usage['queries'].append({
                'question': question[:50] + '...' if len(question) > 50 else question,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total
            })

    def get_token_usage(self) -> dict:
        """Returns token usage statistics for the current session."""
        return {
            'session_totals': {
                'prompt_tokens': self._token_usage['total_prompt_tokens'],
                'completion_tokens': self._token_usage['total_completion_tokens'],
                'total_tokens': self._token_usage['total_tokens']
            },
            'query_count': len(self._token_usage['queries']),
            'recent_queries': self._token_usage['queries'][-10:]
        }

    def reset_token_usage(self):
        """Resets token usage counters."""
        self._token_usage = {
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'queries': []
        }

    # ------------------------------------------------------------------
    # LLM-based grounding verification (unique to this agent)
    # ------------------------------------------------------------------

    def _verify_grounding(self, response: str, user_question: str, context: str) -> dict:
        """Verify if the response is based ONLY on the retrieved context."""
        if not context:
            return {"grounded": True, "reason": "No context to verify against"}

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided context.

RETRIEVED CONTEXT:
{context}

USER QUESTION: {user_question}

AGENT RESPONSE: {response}

STRICT VERIFICATION RULES:
1. The response is "grounded" ONLY if ALL factual claims are EXPLICITLY written in the CONTEXT
2. It is NOT grounded if the response:
   - Infers or deduces information not explicitly stated in the context
   - Adds details, relationships, or facts not present in the context
   - Makes assumptions or generalizations beyond the context
   - Uses information that might be true but is not in the provided context
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly states it cannot find information, it IS grounded
5. BE VERY STRICT: if a claim cannot be found in the context, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{"grounded": true, "reason": "brief explanation"}}
or
{{"grounded": false, "reason": "specific claim that was not in the context"}}"""

        result = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": verify_prompt}]
        )

        try:
            content = result.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\n?", "", content)
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            return {"grounded": True, "reason": "Verification parsing failed"}

    def _get_fallback_response(self, user_question: str) -> str:
        """Generate a response when grounding verification fails."""
        return (
            "I apologize, but I cannot find specific information about that in my knowledge base. "
            "I can only provide information that is explicitly documented in my sources. "
            "Could you please ask something else or rephrase your question?"
        )

    # ------------------------------------------------------------------
    # Chat (with optional grounding verification + token tracking)
    # ------------------------------------------------------------------

    def chat(self, user_message: str, history: list = None, verify: bool = None) -> str:
        should_verify = verify if verify is not None else self.verify_grounding

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
            model=self.model,
            messages=messages
        )

        self._track_token_usage(response, user_message)
        response_content = response.choices[0].message.content

        if should_verify and context:
            verification = self._verify_grounding(response_content, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                response_content = self._get_fallback_response(user_message)

        self._query_history.append({
            'question': user_message,
            'response_length': len(response_content)
        })

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, verify: bool = None):
        should_verify = verify if verify is not None else self.verify_grounding

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

        if should_verify and context:
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content

            verification = self._verify_grounding(full_response, user_message, context)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                full_response = self._get_fallback_response(user_message)

            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })
            yield full_response
        else:
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content
                    yield chunk.data.choices[0].delta.content

            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })
