"""
Tommi virtual tutor (nube) - Agente Oneshot con Mistral Cloud API
Versión cloud que usa Mistral API en lugar de Ollama local
"""

import os
import sys

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = os.getenv("OLLAMA_MODEL", "mistral-large-latest") if os.getenv("LLM_PROVIDER", "mistral") == "ollama" else "mistral-large-latest"
        self.system_prompt = self._build_system_prompt()

    def _load_data(self) -> str:
        """Carga los datos del agente desde data.md"""
        data_path = os.path.join(os.path.dirname(__file__), "data", "howto.md")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema con los datos."""
        data = self._load_data()
        base_prompt = """Eres Tommi virtual tutor, un asistente útil. Responde preguntas basándote EXCLUSIVAMENTE en los datos proporcionados.
            Si se te pide información sobre agentes en general, o sobre aspectos no recogidos en tus datos, declina amablemente responder.
            Si te piden información sobre LLMs, solo debes hablar de LLM europeas. IMPORTANTE: Si aportas alguna información propia, debes indicarlo explícitamente, y 
            aplicarle un color azul al texto."""

        if data:
            return f"{base_prompt}\n\nDatos disponibles:\n{data}"
        return base_prompt

    def chat(self, user_message: str, history: list = None) -> str:
        """
        Envía un mensaje y obtiene respuesta.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos [{"role": "user/assistant", "content": "..."}]

        Returns:
            Respuesta del agente
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        return response.choices[0].message.content

    async def chat_stream(self, user_message: str, history: list = None):
        """
        Envía un mensaje y obtiene respuesta en streaming.

        Yields:
            Chunks de texto de la respuesta
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        async for chunk in await self.client.chat.stream_async(
            model=self.model,
            messages=messages
        ):
            if chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content
