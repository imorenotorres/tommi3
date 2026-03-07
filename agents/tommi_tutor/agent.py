"""
Tommi virtual tutor (nube) - Agente Oneshot con Mistral Cloud API
Versión cloud que usa Mistral API en lugar de Ollama local
"""

import os
import sys
import json
import re

# Añadir web/ al path para importar llm_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = os.getenv("OLLAMA_MODEL", "mistral-large-latest") if os.getenv("LLM_PROVIDER", "mistral") == "ollama" else "mistral-large-latest"
        self.data = self._load_data()  # Guardar datos para verificación
        self.system_prompt = self._build_system_prompt()
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Query history for the sidebar
        self._query_history = []

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
        base_prompt = """You are Tommi virtual tutor, a helpful assistant. Answer questions based EXCLUSIVELY on the provided data.

IMPORTANT RULES:
1. All information you provide comes from a database maintained by IT-UMA (Universidad de Málaga IT department). Always mention this when relevant.
2. If you are asked about topics not covered in your data, politely decline to answer.
3. If you ever need to provide information from sources OTHER than the provided database, you MUST format that text in blue color using HTML: <span style="color: blue;">your text here</span>
4. When discussing LLMs, only talk about European LLMs.
5. Be clear about what comes from the IT-UMA database vs. any supplementary information."""

        if self.data:
            return f"{base_prompt}\n\nAvailable data (from IT-UMA database):\n{self.data}"
        return base_prompt

    def _verify_grounding(self, response: str, user_question: str) -> dict:
        """
        Verifica si la respuesta está basada SOLO en los datos disponibles.

        Args:
            response: Respuesta generada por el agente
            user_question: Pregunta original del usuario

        Returns:
            dict con {"grounded": bool, "reason": str}
        """
        if not self.data:
            return {"grounded": True, "reason": "No data to verify against"}

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided data.

AVAILABLE DATA:
{self.data}

USER QUESTION: {user_question}

AGENT RESPONSE: {response}

STRICT VERIFICATION RULES:
1. The response is "grounded" ONLY if ALL factual claims are EXPLICITLY written in the AVAILABLE DATA
2. It is NOT grounded if the response:
   - Infers or deduces information not explicitly stated in the data
   - Adds details, relationships, or facts not present in the data
   - Makes assumptions or generalizations beyond the data
   - Uses information that might be true but is not in the provided data
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly states it cannot find information, it IS grounded
5. BE VERY STRICT: if a claim cannot be found in the data, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{"grounded": true, "reason": "brief explanation"}}
or
{{"grounded": false, "reason": "specific claim that was not in the data"}}"""

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
        """Genera una respuesta cuando la verificación falla."""
        return (
            "I'm sorry, I cannot find specific information about that in my knowledge base. "
            "I can only provide information that is explicitly documented in my sources. "
            "Could you ask something different or rephrase your question?"
        )

    def chat(self, user_message: str, history: list = None, verify: bool = None) -> str:
        """
        Envía un mensaje y obtiene respuesta.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos [{"role": "user/assistant", "content": "..."}]
            verify: Si True, verifica que la respuesta esté basada en los datos.
                    Si None, usa el valor de VERIFY_GROUNDING del .env

        Returns:
            Respuesta del agente
        """
        # Usar configuración del .env si no se especifica
        should_verify = verify if verify is not None else self.verify_grounding

        messages = [{"role": "system", "content": self.system_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages
        )

        response_content = response.choices[0].message.content

        # Verificar grounding si está habilitado
        if should_verify and self.data:
            verification = self._verify_grounding(response_content, user_message)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                response_content = self._get_fallback_response(user_message)

        # Track query in history
        self._query_history.append({
            'question': user_message,
            'response_length': len(response_content)
        })

        return response_content

    async def chat_stream(self, user_message: str, history: list = None, verify: bool = None):
        """
        Envía un mensaje y obtiene respuesta en streaming.

        Args:
            user_message: Mensaje del usuario
            history: Lista de mensajes previos
            verify: Si True, verifica la respuesta al final del streaming.
                    Si None, usa el valor de VERIFY_GROUNDING del .env

        Yields:
            Chunks de texto de la respuesta
        """
        # Usar configuración del .env si no se especifica
        should_verify = verify if verify is not None else self.verify_grounding

        messages = [{"role": "system", "content": self.system_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        if should_verify and self.data:
            # Acumular respuesta completa para verificar
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content

            # Verificar después de obtener la respuesta completa
            verification = self._verify_grounding(full_response, user_message)
            if not verification.get("grounded", True):
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                full_response = self._get_fallback_response(user_message)

            # Track query in history
            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })
            yield full_response
        else:
            # Sin verificación: streaming normal
            full_response = ""
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    full_response += chunk.data.choices[0].delta.content
                    yield chunk.data.choices[0].delta.content

            # Track query in history
            self._query_history.append({
                'question': user_message,
                'response_length': len(full_response)
            })

    def get_history(self, session_id: str = None) -> list:
        """Returns query history for the sidebar."""
        return [
            {
                'question': entry['question'],
                'num_results': 1  # For oneshot agents, each query = 1 result
            }
            for entry in self._query_history
        ]
