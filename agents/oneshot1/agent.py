"""
Oneshot1 - Agente Oneshot
Soporta Mistral Cloud y Ollama via LLM_PROVIDER
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
        self.model = self._get_model()
        self.system_prompt = self._build_system_prompt()
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"
        # Query history for the sidebar
        self._query_history = []

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "mistral-small-latest")
        return os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    def _load_data(self) -> str:
        """Carga los datos del agente desde data.md"""
        data_path = os.path.join(os.path.dirname(__file__), "data", "data.md")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema con los datos."""
        data = self._load_data()
        base_prompt = """You are Oneshot1, a helpful assistant with access to a knowledge base.

IMPORTANT RULES:
1. Answer questions based ONLY on the information provided in your knowledge base
2. If the information is not in your knowledge base, clearly state that you don\'t have that information
3. Be concise and direct in your responses
4. Use the same language as the user\'s question

RESPONSE FORMAT:
- Provide clear, well-structured answers
- Use lists or bullet points when appropriate
- If you cannot answer, explain why and suggest alternatives"""

        if data:
            return f"{base_prompt}\n\nDatos disponibles:\n{data}"
        return base_prompt

    def _verify_grounding(self, response: str, user_question: str) -> dict:
        """
        Verifica si la respuesta está basada SOLO en los datos proporcionados.

        Args:
            response: Respuesta generada por el agente
            user_question: Pregunta original del usuario

        Returns:
            dict con {"grounded": bool, "reason": str}
        """
        data = self._load_data()

        verify_prompt = f"""You are a strict verification assistant. Your job is to verify if a response contains ONLY information that is EXPLICITLY stated in the provided data.

AVAILABLE DATA:
{data}

USER QUESTION: {user_question}

AGENT RESPONSE: {response}

STRICT VERIFICATION RULES:
1. The response is "grounded" ONLY if ALL factual claims are EXPLICITLY written in the AVAILABLE DATA
2. It is NOT grounded if the response:
   - Infers or deduces information not explicitly stated
   - Adds relationships between entities that are not explicitly documented
   - Makes assumptions about events, contacts, or collaborations not explicitly mentioned
   - Uses names/data from the source but creates new claims about them
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly declines to answer, it IS grounded
5. BE VERY STRICT: if a claim cannot be found VERBATIM or nearly verbatim in the data, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{"grounded": true, "reason": "brief explanation"}}
or
{{"grounded": false, "reason": "specific claim that was not explicitly in the data"}}"""

        result = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": verify_prompt}]
        )

        try:
            content = result.choices[0].message.content.strip()
            # Limpiar posibles bloques de código markdown
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\n?", "", content)
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            # Si falla el parsing, asumir que está grounded para no bloquear
            return {"grounded": True, "reason": "Verification parsing failed"}

    def _get_fallback_response(self, user_question: str) -> str:
        """Genera una respuesta cuando la verificación falla."""
        return (
            "I apologize, but I cannot find specific information about that in my database. "
            "I can only provide information that is explicitly documented. "
            "Could you please ask something else?"
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
            Respuesta del agente (verificada si verify=True)
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

        if should_verify:
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

        if should_verify:
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
