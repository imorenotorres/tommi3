"""
LLM Client - Cliente unificado para Mistral Cloud, Ollama y vLLM (on premise)

Configuración via variables de entorno:
    LLM_PROVIDER: "mistral" (default), "ollama" o "vllm"

    Para Mistral:
        MISTRAL_API_KEY: API key de Mistral

    Para Ollama:
        OLLAMA_BASE_URL: URL del servidor Ollama (default: http://localhost:11434)
        OLLAMA_MODEL: Modelo a usar (default: mistral)

    Para vLLM:
        VLLM_BASE_URL: URL del servidor vLLM (default: http://localhost:8000/v1)
        VLLM_MODEL: Modelo a usar (requerido)
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, AsyncIterator


@dataclass
class Message:
    """Mensaje de chat."""
    role: str
    content: str


@dataclass
class Choice:
    """Opción de respuesta."""
    message: Message

    @property
    def delta(self):
        """Para compatibilidad con streaming."""
        return self.message


@dataclass
class ChatResponse:
    """Respuesta de chat normalizada."""
    choices: List[Choice]


@dataclass
class StreamChunk:
    """Chunk de streaming normalizado."""
    data: 'StreamChunk'
    choices: List[Choice]

    def __post_init__(self):
        self.data = self


class LLMClient:
    """
    Cliente unificado para LLMs.
    Soporta Mistral Cloud y Ollama con la misma interfaz.
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
            raise ValueError(f"Proveedor LLM no soportado: {self.provider}. Usa 'mistral', 'ollama' o 'vllm'")

    def _init_mistral(self):
        """Inicializa cliente de Mistral."""
        from mistralai import Mistral

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY no configurada")

        self._client = Mistral(api_key=api_key)
        self._default_model = "mistral-small-latest"

    def _init_ollama(self):
        """Inicializa cliente de Ollama."""
        import ollama

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._client = ollama.Client(host=base_url)
        self._default_model = os.getenv("OLLAMA_MODEL", "mistral")

    def _init_vllm(self):
        """Inicializa cliente de vLLM (compatible con OpenAI API)."""
        from openai import OpenAI

        base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        # vLLM no requiere API key real, pero OpenAI SDK lo exige
        api_key = os.getenv("VLLM_API_KEY", "dummy")
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._default_model = os.getenv("VLLM_MODEL")
        if not self._default_model:
            raise ValueError("VLLM_MODEL es requerido cuando usas vLLM")

    @property
    def chat(self):
        """Devuelve self para mantener compatibilidad con client.chat.complete()"""
        return self

    def complete(self, model: str = None, messages: List[Dict[str, str]] = None,
                 tools: List[Dict] = None, tool_choice: str = None) -> ChatResponse:
        """
        Llamada de chat síncrona.

        Args:
            model: Modelo a usar (usa default si no se especifica)
            messages: Lista de mensajes [{"role": "...", "content": "..."}]
            tools: Lista de herramientas (solo Mistral por ahora)
            tool_choice: Modo de selección de herramientas

        Returns:
            ChatResponse con la respuesta normalizada
        """
        model = model or self._default_model

        if self.provider == "mistral":
            return self._complete_mistral(model, messages, tools, tool_choice)
        elif self.provider == "ollama":
            return self._complete_ollama(model, messages, tools)
        else:  # vllm
            return self._complete_vllm(model, messages, tools, tool_choice)

    def _complete_mistral(self, model: str, messages: List[Dict],
                          tools: List[Dict] = None, tool_choice: str = None) -> ChatResponse:
        """Llamada a Mistral Cloud."""
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        response = self._client.chat.complete(**kwargs)
        return response  # Mistral ya devuelve formato compatible

    def _complete_ollama(self, model: str, messages: List[Dict],
                         tools: List[Dict] = None) -> ChatResponse:
        """Llamada a Ollama."""
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat(**kwargs)

        # Normalizar respuesta de Ollama al formato de Mistral
        message = Message(
            role=response["message"]["role"],
            content=response["message"].get("content", "")
        )

        choice = Choice(message=message)

        # Manejar tool_calls si existen
        if tools and "tool_calls" in response["message"]:
            # Crear objeto compatible con Mistral para tool_calls
            choice.message.tool_calls = self._normalize_ollama_tool_calls(
                response["message"]["tool_calls"]
            )

        return ChatResponse(choices=[choice])

    def _normalize_ollama_tool_calls(self, tool_calls: List[Dict]) -> List:
        """Normaliza tool_calls de Ollama al formato de Mistral."""
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
                       tools: List[Dict] = None, tool_choice: str = None) -> ChatResponse:
        """Llamada a vLLM (API compatible con OpenAI)."""
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        response = self._client.chat.completions.create(**kwargs)

        # Normalizar respuesta de OpenAI/vLLM al formato interno
        msg = response.choices[0].message
        message = Message(
            role=msg.role,
            content=msg.content or ""
        )

        choice = Choice(message=message)

        # Manejar tool_calls si existen
        if tools and msg.tool_calls:
            choice.message.tool_calls = self._normalize_vllm_tool_calls(msg.tool_calls)

        return ChatResponse(choices=[choice])

    def _normalize_vllm_tool_calls(self, tool_calls) -> List:
        """Normaliza tool_calls de vLLM/OpenAI al formato interno."""
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
                           messages: List[Dict[str, str]] = None):
        """
        Streaming asíncrono de respuestas.
        Devuelve un async iterator compatible con el formato de Mistral.

        Args:
            model: Modelo a usar
            messages: Lista de mensajes

        Returns:
            Async iterator de StreamChunk
        """
        model = model or self._default_model

        if self.provider == "mistral":
            return await self._client.chat.stream_async(model=model, messages=messages)
        elif self.provider == "ollama":
            return self._create_ollama_stream(model, messages)
        else:  # vllm
            return self._create_vllm_stream(model, messages)

    def _create_ollama_stream(self, model: str, messages: List[Dict]):
        """Crea un async iterator para Ollama."""
        return OllamaStreamIterator(self._client, model, messages)

    def _create_vllm_stream(self, model: str, messages: List[Dict]):
        """Crea un async iterator para vLLM."""
        return VLLMStreamIterator(self._client, model, messages)


class OllamaStreamIterator:
    """Async iterator para streaming de Ollama."""

    def __init__(self, client, model: str, messages: List[Dict]):
        self._client = client
        self._model = model
        self._messages = messages
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
                    stream=True
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
    """Async iterator para streaming de vLLM."""

    def __init__(self, client, model: str, messages: List[Dict]):
        self._client = client
        self._model = model
        self._messages = messages
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
                    stream=True
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
