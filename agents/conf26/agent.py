"""
Novis B - Agente Oneshot con Mistral API
Soporta Mistral Cloud y Ollama (on premise) via LLM_PROVIDER
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

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
        self.model = os.getenv("OLLAMA_MODEL", "mistral-small-latest") if os.getenv("LLM_PROVIDER", "mistral") == "ollama" else "mistral-small-latest"
        self.system_prompt = self._build_system_prompt()
        # Configuración de verificación desde .env (VERIFY_GROUNDING=true/false)
        self.verify_grounding = os.getenv("VERIFY_GROUNDING", "false").lower() == "true"

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
        base_prompt = (
            f"You are NOVIS 1, a helpful multilingual assistant for Uninovis Conference 2026 and DiPYUA Workshop (but not about the General Assembly). "
            f"Both events are organized by UNINOVIS, "
            f"Alliance of European Universities. The data related to the Conference, Workshop and UNINOVIS Alliance is here: {data}. "
            f"Use this data to answer questions in a very concise manner and using markdown formatting. "
            f"If the user clicks on a link, open the page in a new window. "
            f"Decline politely and do not: "
            f"1) answer questions outside the scope of Uninovis Conference or DiPYUA Workshop, "
            f"2) provide numerical data (you may add that as an LLN you are good with letters rather than numbers); "
            f"3) draft a letter or document. "
            f"4) describe your linguistic skills "
            f"5) provide indications to or from any place not explicitely mentioned in data.md, such as beaches, pharmacies, restaurants, hospitals, cafes or any shop "
            f"6) provide health related information "
            f"7) provide information of any kind that is not explicitely mentioned in the database "
            f"If asked to provide numerical data, advise that you have a linguistic mind and are not good with maths. However you can provide the requested information. "
            f"Your motto is: Proudly UNINOVIS, proudly EUROPEAN. "
            f"Developed by UNINOVIS and Powered by Tokkibunny x Mistral. For technical information please ask to contact: tokkibunnyapp@gmail.com"
        )

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
   - Infers or deduces information not explicitly stated (e.g., assuming people collaborated just because they work on similar topics)
   - Adds relationships between entities that are not explicitly documented
   - Makes assumptions about events, contacts, or collaborations not explicitly mentioned
   - Uses names/data from the source but creates new claims about them
3. General courtesies, greetings, or formatting are allowed
4. If the response correctly declines to answer, it IS grounded
5. BE VERY STRICT: if a claim cannot be found VERBATIM or nearly verbatim in the data, it is NOT grounded

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{"grounded": true, "reason": "brief explanation"}}
or
{{"grounded": false, "reason": "specific claim that was not explicitly in the data"}}
"""

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
            "I can only provide information about UNINOVIS Conference 2026 and DiPYUA Workshop "
            "that is explicitly documented. Could you please ask something else about these events?"
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
                # Log para debugging (opcional)
                print(f"[GROUNDING FAILED] Reason: {verification.get('reason', 'Unknown')}")
                return self._get_fallback_response(user_message)

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
            Si verify=True y falla, yield del mensaje de fallback en lugar del contenido
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
                yield self._get_fallback_response(user_message)
            else:
                yield full_response
        else:
            # Sin verificación: streaming normal
            async for chunk in await self.client.chat.stream_async(
                model=self.model,
                messages=messages
            ):
                if chunk.data.choices[0].delta.content:
                    yield chunk.data.choices[0].delta.content


def main():
    """Interfaz de línea de comandos para el agente."""
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 50)
    print("NOVIS 1 - Asistente de UNINOVIS Conference 2026")
    print("=" * 50)
    print("Escribe tu mensaje o 'salir' para terminar.\n")

    try:
        agent = Agent()
    except ValueError as e:
        print(f"Error: {e}")
        return

    history = []

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nHasta luego!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["salir", "exit", "quit", "q"]:
            print("\nHasta luego!")
            break

        try:
            response = agent.chat(user_input, history)
            print(f"\nNovis: {response}\n")

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
