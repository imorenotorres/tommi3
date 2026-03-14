"""
LLM Client - Unified client for Mistral Cloud, Ollama, and vLLM (on premise)

Configuration via environment variables:
    LLM_PROVIDER: "mistral" (default), "ollama", or "vllm"

    For Mistral:
        MISTRAL_API_KEY: Mistral API key

    For Ollama:
        OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
        OLLAMA_MODEL: Model to use (default: mistral)

    For vLLM:
        VLLM_BASE_URL: vLLM server URL (default: http://localhost:8000/v1)
        VLLM_MODEL: Model to use (required)
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, AsyncIterator


@dataclass
class Message:
    """Chat message."""
    role: str
    content: str


@dataclass
class Choice:
    """Response option."""
    message: Message

    @property
    def delta(self):
        """For streaming compatibility."""
        return self.message


@dataclass
class TokenUsage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """Normalized chat response."""
    choices: List[Choice]
    usage: Optional[TokenUsage] = None


@dataclass
class StreamChunk:
    """Normalized streaming chunk."""
    data: 'StreamChunk'
    choices: List[Choice]

    def __post_init__(self):
        self.data = self


class LLMClient:
    """
    Unified LLM client.
    Supports Mistral Cloud and Ollama with the same interface.
    """

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        self._client = None
        self._default_model = None

        if self.provider == "mistral":
            self._init_mistral()
        elif self.provider == "ollama":
            self._init_ollama()
        elif self.provider == "vllm":
            self._init_vllm()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Use 'mistral', 'ollama', or 'vllm'")

    def _init_mistral(self):
        """Initialize Mistral client."""
        from mistralai import Mistral

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not configured")

        self._client = Mistral(api_key=api_key)
        self._default_model = "mistral-small-latest"

    def _init_ollama(self):
        """Initialize Ollama client."""
        import ollama

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._client = ollama.Client(host=base_url)
        self._default_model = os.getenv("OLLAMA_MODEL", "mistral")

    def _init_vllm(self):
        """Initialize vLLM client (OpenAI API compatible)."""
        from openai import OpenAI

        base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        # vLLM doesn't require a real API key, but OpenAI SDK requires one
        api_key = os.getenv("VLLM_API_KEY", "dummy")
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._default_model = os.getenv("VLLM_MODEL")
        if not self._default_model:
            raise ValueError("VLLM_MODEL is required when using vLLM")

    @property
    def chat(self):
        """Returns self to maintain compatibility with client.chat.complete()"""
        return self

    def complete(self, model: str = None, messages: List[Dict[str, str]] = None,
                 tools: List[Dict] = None, tool_choice: str = None,
                 max_tokens: int = None) -> ChatResponse:
        """
        Synchronous chat call.

        Args:
            model: Model to use (uses default if not specified)
            messages: List of messages [{"role": "...", "content": "..."}]
            tools: List of tools (Mistral only for now)
            tool_choice: Tool selection mode
            max_tokens: Maximum tokens in response (default: 4096)

        Returns:
            ChatResponse with normalized response
        """
        model = model or self._default_model
        max_tokens = max_tokens or 4096  # Default to 4096 for longer responses

        if self.provider == "mistral":
            return self._complete_mistral(model, messages, tools, tool_choice, max_tokens)
        elif self.provider == "ollama":
            return self._complete_ollama(model, messages, tools, max_tokens)
        else:  # vllm
            return self._complete_vllm(model, messages, tools, tool_choice, max_tokens)

    def _complete_mistral(self, model: str, messages: List[Dict],
                          tools: List[Dict] = None, tool_choice: str = None,
                          max_tokens: int = 4096) -> ChatResponse:
        """Call to Mistral Cloud."""
        kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        response = self._client.chat.complete(**kwargs)
        # Mistral response includes usage info - attach it to our response
        if hasattr(response, 'usage') and response.usage:
            response.usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        return response

    def _complete_ollama(self, model: str, messages: List[Dict],
                         tools: List[Dict] = None, max_tokens: int = 4096) -> ChatResponse:
        """Call to Ollama."""
        kwargs = {"model": model, "messages": messages}
        kwargs["options"] = {"num_predict": max_tokens}
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat(**kwargs)

        # Normalize Ollama response to Mistral format
        message = Message(
            role=response["message"]["role"],
            content=response["message"].get("content", "")
        )

        choice = Choice(message=message)

        # Handle tool_calls if they exist
        if tools and "tool_calls" in response["message"]:
            # Crear objeto compatible con Mistral para tool_calls
            choice.message.tool_calls = self._normalize_ollama_tool_calls(
                response["message"]["tool_calls"]
            )

        # Extract token usage from Ollama response
        usage = None
        if "prompt_eval_count" in response or "eval_count" in response:
            usage = TokenUsage(
                prompt_tokens=response.get("prompt_eval_count", 0),
                completion_tokens=response.get("eval_count", 0),
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
            )

        return ChatResponse(choices=[choice], usage=usage)

    def _normalize_ollama_tool_calls(self, tool_calls: List[Dict]) -> List:
        """Normalize Ollama tool_calls to Mistral format."""
        import json
        from dataclasses import dataclass

        @dataclass
        class ToolFunction:
            name: str
            arguments: str

        @dataclass
        class ToolCall:
            id: str
            function: ToolFunction

        normalized = []
        for i, tc in enumerate(tool_calls):
            func = tc.get("function", {})
            normalized.append(ToolCall(
                id=f"call_{i}",
                function=ToolFunction(
                    name=func.get("name", ""),
                    arguments=json.dumps(func.get("arguments", {}))
                )
            ))
        return normalized

    def _complete_vllm(self, model: str, messages: List[Dict],
                       tools: List[Dict] = None, tool_choice: str = None,
                       max_tokens: int = 4096) -> ChatResponse:
        """Call to vLLM (OpenAI API compatible)."""
        kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        response = self._client.chat.completions.create(**kwargs)

        # Normalize OpenAI/vLLM response to internal format
        msg = response.choices[0].message
        message = Message(
            role=msg.role,
            content=msg.content or ""
        )

        choice = Choice(message=message)

        # Handle tool_calls if they exist
        if tools and msg.tool_calls:
            choice.message.tool_calls = self._normalize_vllm_tool_calls(msg.tool_calls)

        # Extract token usage from OpenAI/vLLM response
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )

        return ChatResponse(choices=[choice], usage=usage)

    def _normalize_vllm_tool_calls(self, tool_calls) -> List:
        """Normalize vLLM/OpenAI tool_calls to internal format."""
        from dataclasses import dataclass

        @dataclass
        class ToolFunction:
            name: str
            arguments: str

        @dataclass
        class ToolCall:
            id: str
            function: ToolFunction

        normalized = []
        for tc in tool_calls:
            normalized.append(ToolCall(
                id=tc.id,
                function=ToolFunction(
                    name=tc.function.name,
                    arguments=tc.function.arguments
                )
            ))
        return normalized

    async def stream_async(self, model: str = None,
                           messages: List[Dict[str, str]] = None,
                           max_tokens: int = None):
        """
        Asynchronous response streaming.
        Returns an async iterator compatible with Mistral format.

        Args:
            model: Model to use
            messages: List of messages
            max_tokens: Maximum tokens in response (default: 4096)

        Returns:
            Async iterator of StreamChunk
        """
        model = model or self._default_model
        max_tokens = max_tokens or 4096

        if self.provider == "mistral":
            return await self._client.chat.stream_async(model=model, messages=messages, max_tokens=max_tokens)
        elif self.provider == "ollama":
            return self._create_ollama_stream(model, messages, max_tokens)
        else:  # vllm
            return self._create_vllm_stream(model, messages, max_tokens)

    def _create_ollama_stream(self, model: str, messages: List[Dict], max_tokens: int = 4096):
        """Creates an async iterator for Ollama."""
        return OllamaStreamIterator(self._client, model, messages, max_tokens)

    def _create_vllm_stream(self, model: str, messages: List[Dict], max_tokens: int = 4096):
        """Creates an async iterator for vLLM."""
        return VLLMStreamIterator(self._client, model, messages, max_tokens)


class OllamaStreamIterator:
    """Async iterator for Ollama streaming."""

    def __init__(self, client, model: str, messages: List[Dict], max_tokens: int = 4096):
        self._client = client
        self._model = model
        self._messages = messages
        self._max_tokens = max_tokens
        self._stream = None
        self._iterator = None
        self._exhausted = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        import asyncio

        if self._exhausted:
            raise StopAsyncIteration

        if self._stream is None:
            loop = asyncio.get_event_loop()
            self._stream = await loop.run_in_executor(
                None,
                lambda: self._client.chat(
                    model=self._model,
                    messages=self._messages,
                    stream=True,
                    options={"num_predict": self._max_tokens}
                )
            )
            self._iterator = iter(self._stream)

        def get_next():
            try:
                return next(self._iterator)
            except StopIteration:
                return None

        loop = asyncio.get_event_loop()
        chunk = await loop.run_in_executor(None, get_next)

        if chunk is None:
            self._exhausted = True
            raise StopAsyncIteration

        content = chunk.get("message", {}).get("content", "")
        message = Message(role="assistant", content=content)
        choice = Choice(message=message)
        return StreamChunk(data=None, choices=[choice])


class VLLMStreamIterator:
    """Async iterator for vLLM streaming."""

    def __init__(self, client, model: str, messages: List[Dict], max_tokens: int = 4096):
        self._client = client
        self._model = model
        self._messages = messages
        self._max_tokens = max_tokens
        self._stream = None
        self._iterator = None
        self._exhausted = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        import asyncio

        if self._exhausted:
            raise StopAsyncIteration

        if self._stream is None:
            loop = asyncio.get_event_loop()
            self._stream = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self._model,
                    messages=self._messages,
                    stream=True,
                    max_tokens=self._max_tokens
                )
            )
            self._iterator = iter(self._stream)

        def get_next():
            try:
                return next(self._iterator)
            except StopIteration:
                return None

        loop = asyncio.get_event_loop()
        chunk = await loop.run_in_executor(None, get_next)

        if chunk is None:
            self._exhausted = True
            raise StopAsyncIteration

        content = chunk.choices[0].delta.content or ""
        message = Message(role="assistant", content=content)
        choice = Choice(message=message)
        return StreamChunk(data=None, choices=[choice])
