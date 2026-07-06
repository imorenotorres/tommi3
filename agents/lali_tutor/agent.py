"""
Tutor LALI — Tutor virtual de Lingüística Aplicada a la Logopedia.
RAG agent with programmatic transcription and phonological error support.

Capabilities:
1. Phonological transcription (transcriptor.py)
2. Phonological error exercises and analysis (errores_fonologicos/)
3. General RAG Q&A from course materials
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, SimpleRAGMixin, SimpleVectorlessMixin
from transcriptor import transcribir, transcribir_palabra
from errores_fonologicos.dispatch import (
    detectar_peticion_errores, dispatch_errores, dispatch_correccion,
    es_respuesta_ejercicio, es_abandono_ejercicio
)
from progreso_alumno import (
    registrar_resultado, nivel_recomendado, mensaje_bienvenida_ejercicios
)


# ═══════════════════════════════════════════════════════════════════════
# DETECCIÓN DE TRANSCRIPCIONES
# ═══════════════════════════════════════════════════════════════════════

def _es_peticion_transcripcion(msg: str) -> str | None:
    """Detect if the user is asking for a phonological transcription.
    Returns the text to transcribe, or None."""
    msg_lower = msg.lower().strip()

    # If the message is about exercises, don't treat it as a transcription request
    if any(kw in msg_lower for kw in ['ejercicio', 'practicar', 'práctica', 'entrenar']):
        return None

    patterns = [
        r'transcri(?:be|pción)\s+fonológica(?:mente)?\s+(?:de\s+)?(?:la\s+palabra\s+)?["\']?(.+?)["\']?\s*$',
        r'transcri(?:be|pción)\s+fonológica(?:mente)?\s*:\s*["\']?(.+?)["\']?\s*$',
        r'(?:haz|hazme|dame)\s+(?:la\s+)?transcripción\s+fonológica\s+(?:de\s+)?["\']?(.+?)["\']?\s*$',
        r'transcri(?:be|bir)\s+fonológicamente\s+["\']?(.+?)["\']?\s*$',
        r'transcripción\s+fonológica\s+(?:de\s+)?["\']?(.+?)["\']?\s*$',
        r'¿?cómo\s+se\s+transcribe\s+(?:fonológicamente\s+)?["\']?(.+?)["\']?\s*\??$',
    ]

    for pattern in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            texto = match.group(1).strip().strip('"\'')
            if texto:
                return texto
    return None


def _generar_respuesta_transcripcion(texto: str) -> tuple:
    """Generate a programmatic transcription response."""
    transcripcion = transcribir(texto)

    if isinstance(transcripcion, tuple):
        error_msg = transcripcion[1]
        respuesta = (
            f"**No es posible transcribir automáticamente:**\n\n"
            f"{error_msg}\n\n"
            f"Esta palabra parece ser un préstamo o extranjerismo, o contiene "
            f"combinaciones no habituales en español. Consulta con tu profesor/a "
            f"para la transcripción correcta."
        )
        return respuesta, True

    palabras = re.findall(r"[a-záéíóúüñ]+", texto.lower())
    detalle = []
    for p in palabras:
        t = transcribir_palabra(p)
        if isinstance(t, tuple):
            detalle.append(f"- **{p}** → ⚠️ {t[1]}")
        elif t:
            detalle.append(f"- **{p}** → / {t} /")

    respuesta = f"**Transcripción fonológica** (español peninsular distinguidor):\n\n"
    respuesta += f"> {transcripcion}\n\n"

    if len(palabras) > 1:
        respuesta += "**Detalle por palabra:**\n\n"
        respuesta += "\n".join(detalle) + "\n\n"

    respuesta += "*Nota: Esta transcripción ha sido generada mediante un algoritmo programado en Python (no por IA).*"

    return respuesta, False


# ═══════════════════════════════════════════════════════════════════════
# DETECCIÓN DE CORRECCIÓN DE EJERCICIO
# ═══════════════════════════════════════════════════════════════════════

def _es_peticion_correccion(msg: str) -> bool:
    """Detecta si el alumno pide corregir o ver la solución."""
    msg_lower = msg.lower().strip()
    return any(t in msg_lower for t in [
        'corregir', 'corrígeme', 'corrige', 'solución', 'solucion',
        'respuesta correcta', 'ver solución', 'ver solucion', 'muestra la solución',
    ])


# ═══════════════════════════════════════════════════════════════════════
# AGENTE
# ═══════════════════════════════════════════════════════════════════════

class Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__

    def __init__(self):
        super().__init__()
        self._session_state = {}  # estado por sesión (ejercicio en curso, etc.)

    def _get_username(self, kwargs) -> str | None:
        """Extrae el username de los kwargs."""
        return kwargs.get('username') or self._session_state.get('username')

    def _registrar_correccion(self, correccion_texto: str, username: str):
        """Registra el resultado de una corrección de transcripción en el progreso."""
        if not username:
            return
        ejercicio = self._session_state.get('ejercicio_actual')
        if not ejercicio or self._session_state.get('ejercicio_tipo') != 'transcripcion':
            return
        # Extract score from correction text
        import re
        match = re.search(r'(\d+(?:\.\d+)?)%\s*\((\d+)/(\d+)\)', correccion_texto)
        if match:
            puntuacion = float(match.group(1))
            num_items = int(match.group(3))
            nivel = ejercicio.get('nivel', 1)
            modo = ejercicio.get('modo', 'fonologica_tipica')
            registrar_resultado(username, nivel, puntuacion, num_items, modo=modo)

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        username = self._get_username(kwargs)
        if username:
            self._session_state['username'] = username

        # 1. Check transcription request
        texto = _es_peticion_transcripcion(user_message)
        if texto:
            respuesta, es_error = _generar_respuesta_transcripcion(texto)
            if es_error:
                return respuesta

            model = kwargs.get('model_override') or self.model
            messages = [
                {"role": "system", "content": (
                    "Eres un tutor de fonología del español. "
                    "El sistema ha generado automáticamente la transcripción fonológica que aparece abajo. "
                    "Tu tarea es añadir una breve explicación pedagógica. "
                    "NO modifiques la transcripción — es correcta. "
                    "Responde en español. Sé breve y claro."
                )},
                {"role": "user", "content": f"Palabra/frase: \"{texto}\"\n\nTranscripción generada:\n{respuesta}"}
            ]
            llm_response = self.client.chat.complete(model=model, messages=messages)
            explicacion = llm_response.choices[0].message.content
            return respuesta + "\n---\n\n**Explicación:**\n\n" + explicacion

        # 2. Active exercise: everything goes through exercise handler
        if self._session_state.get('ejercicio_actual'):
            # Check if student wants to abandon
            if es_abandono_ejercicio(user_message):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
                return "De acuerdo, dejamos el ejercicio. ¿En qué puedo ayudarte?"

            # Check if student is requesting a NEW exercise (replaces current one)
            peticion_nueva = detectar_peticion_errores(user_message)
            if peticion_nueva and peticion_nueva.get('accion') in ('ejercicio', 'ejercicio_transcripcion'):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
                # Fall through to step 3 to generate the new exercise
            else:
                # If "corregir"/"solución": correct using saved answers
                if _es_peticion_correccion(user_message):
                    respuestas = self._session_state.get('respuestas_alumno', '')
                    if not respuestas:
                        return "No he recibido tus respuestas todavía. Escríbelas primero y luego pulsa **Corregir**."
                    correccion, incorrectas = dispatch_correccion(
                        self._session_state['ejercicio_actual'],
                        respuestas,
                        ejercicio_tipo=self._session_state.get('ejercicio_tipo', 'errores'),
                        session_state=self._session_state,
                    )
                    self._registrar_correccion(correccion, username)
                    return correccion

                # Anything else = student's answers → save them
                self._session_state['respuestas_alumno'] = user_message
                return 'Respuestas recibidas.\n\n<div class="ejercicio-btns-placeholder"></div>'

        # 3. Check phonological error request
        peticion = detectar_peticion_errores(user_message)
        if peticion:
            # For transcription exercises, add progress context
            if peticion.get('accion') == 'ejercicio_transcripcion' and username:
                msg = mensaje_bienvenida_ejercicios(username)
                if msg:
                    # Inject suggested level if none specified
                    if peticion.get('nivel', 1) == 1:
                        recomendado = nivel_recomendado(username)
                        peticion['nivel'] = recomendado
            respuesta = dispatch_errores(peticion, self._session_state)
            if respuesta:
                # Prepend progress message if available
                if peticion.get('accion') == 'ejercicio_transcripcion' and username:
                    msg = mensaje_bienvenida_ejercicios(username)
                    if msg:
                        respuesta = f"📊 *{msg}*\n\n---\n\n" + respuesta
                return respuesta
            # If dispatch returns None (e.g. 'explicar_tipo'), fall through to RAG

        # 4. Normal RAG
        return super().chat(user_message, history, **kwargs)

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        username = self._get_username(kwargs)
        if username:
            self._session_state['username'] = username

        # 1. Check transcription request
        texto = _es_peticion_transcripcion(user_message)
        if texto:
            if not self._chromadb_initialized:
                init_msg = getattr(self, '_init_status_message', "Preparando...")
                yield ("status", init_msg)
                self._init_chromadb()

            yield ("status", "Transcribiendo...")

            respuesta, es_error = _generar_respuesta_transcripcion(texto)

            if es_error:
                yield ("procedural_banner", '<div style="padding:8px 12px;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;font-size:13px;color:#991b1b;margin-bottom:8px;">⚠️ Palabra no transcribible con las reglas del español.</div>')
                yield respuesta
                return

            from base.simple_vectorless_mixin import _banner_verified
            yield ("procedural_banner", _banner_verified(
                "Transcripción generada automáticamente (verificada, sin IA)."))
            yield respuesta

            yield "\n---\n\n**Explicación:**\n\n"

            model = kwargs.get('model_override') or self.model
            messages = [
                {"role": "system", "content": (
                    "Eres un tutor de fonología del español. "
                    "El sistema ha generado automáticamente la transcripción fonológica que aparece abajo. "
                    "Tu tarea es añadir una breve explicación pedagógica. "
                    "NO modifiques la transcripción — es correcta. "
                    "Responde en español. Sé breve y claro."
                )},
                {"role": "user", "content": f"Palabra/frase: \"{texto}\"\n\nTranscripción generada:\n{respuesta}"}
            ]

            async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
                if chunk.data.choices and chunk.data.choices[0].delta.content:
                    yield chunk.data.choices[0].delta.content
            return

        # 2. Active exercise: everything goes through exercise handler
        if self._session_state.get('ejercicio_actual'):
            # Check if student wants to abandon
            if es_abandono_ejercicio(user_message):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
                yield "De acuerdo, dejamos el ejercicio. ¿En qué puedo ayudarte?"
                return

            # Check if student is requesting a NEW exercise (replaces current one)
            peticion_nueva = detectar_peticion_errores(user_message)
            if peticion_nueva and peticion_nueva.get('accion') in ('ejercicio', 'ejercicio_transcripcion'):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
                # Fall through to step 3 to generate the new exercise
            else:
                # If "corregir"/"solución": correct using saved answers
                if _es_peticion_correccion(user_message):
                    respuestas = self._session_state.get('respuestas_alumno', '')
                    if not respuestas:
                        yield "No he recibido tus respuestas todavía. Escríbelas primero y luego pulsa **Corregir**."
                        return
                else:
                    # Student is sending answers → save them and confirm
                    self._session_state['respuestas_alumno'] = user_message
                    yield 'Respuestas recibidas.\n\n<div class="ejercicio-btns-placeholder"></div>'
                    return

                if not self._chromadb_initialized:
                    yield ("status", "Preparando...")
                    self._init_chromadb()

                from base.simple_vectorless_mixin import _banner_verified
                yield ("procedural_banner", _banner_verified(
                    "Corrección generada automáticamente (verificada, sin IA)."))

                correccion, incorrectas = dispatch_correccion(
                    self._session_state['ejercicio_actual'],
                    respuestas,
                    ejercicio_tipo=self._session_state.get('ejercicio_tipo', 'errores'),
                    session_state=self._session_state,
                )
                self._registrar_correccion(correccion, username)
                yield correccion

                # Pedagogical feedback for error exercises (not transcription)
                ejercicio_tipo_ej = self._session_state.get('ejercicio_tipo', 'errores')
                if ejercicio_tipo_ej != 'transcripcion':
                    ejercicio = self._session_state.get('ejercicio_actual', {})
                    from errores_fonologicos.catalogo_errores import generar_retroalimentacion
                    todos_errores = []
                    if 'items' in ejercicio:
                        for item in ejercicio['items']:
                            for e in item.get('errores', []):
                                todos_errores.append(e)
                    feedback = generar_retroalimentacion(todos_errores)
                    if feedback:
                        yield "\n---\n\n**Comentario del tutor:**\n\n"
                        yield feedback
                return

        # 3. Check phonological error request
        peticion = detectar_peticion_errores(user_message)
        if peticion:
            if not self._chromadb_initialized:
                yield ("status", "Preparando...")
                self._init_chromadb()

            # For transcription exercises, adjust level based on progress
            if peticion.get('accion') == 'ejercicio_transcripcion' and username:
                if peticion.get('nivel', 1) == 1:
                    recomendado = nivel_recomendado(username)
                    peticion['nivel'] = recomendado

            respuesta = dispatch_errores(peticion, self._session_state)
            if respuesta:
                if peticion['accion'] == 'ejercicio_transcripcion':
                    from base.simple_vectorless_mixin import _banner_verified
                    yield ("procedural_banner", _banner_verified(
                        "Ejercicio generado automáticamente."))
                    # Prepend progress info
                    if username:
                        msg = mensaje_bienvenida_ejercicios(username)
                        if msg:
                            yield f"*{msg}*\n\n---\n\n"
                elif peticion['accion'] == 'ejercicio':
                    from base.simple_vectorless_mixin import _banner_verified
                    yield ("procedural_banner", _banner_verified(
                        "Ejercicio generado automáticamente."))
                elif peticion['accion'] in ('analizar', 'clasificar'):
                    from base.simple_vectorless_mixin import _banner_verified
                    yield ("procedural_banner", _banner_verified(
                        "Análisis generado automáticamente (verificado, sin IA)."))
                yield respuesta
                return

        # 4. Normal RAG streaming
        async for item in super().chat_stream(user_message, history, **kwargs):
            yield item
