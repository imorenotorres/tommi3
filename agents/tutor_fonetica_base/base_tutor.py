"""
BaseTutorFonetica — Clase base para tutores virtuales de Fonética.

Proporciona toda la maquinaria común:
  - Detección y ejecución de transcripciones fonológicas
  - Detección y dispatch de ejercicios (transcripción y errores)
  - Gestión de sesión (ejercicio en curso, respuestas)
  - Registro de progreso del alumno
  - Corrección de ejercicios
  - RAG Q&A como fallback

Las subclases (agentes concretos) solo necesitan:
  - _AGENT_FILE = __file__
  - config.json y prompts.json propios
  - data/docs/ con sus materiales
  - Opcionalmente sobrescribir métodos para personalizar
"""

import os
import re
import sys

# Asegurar que el directorio base está en el path para importar transcriptor, etc.
_BASE_DIR = os.path.dirname(__file__)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from base import BaseRAGAgent, SimpleRAGMixin, SimpleVectorlessMixin
import base.simple_vectorless_mixin as _svm

# ── Banners de fiabilidad en español ──
_BANNER_STYLE = "padding:8px 12px;border-radius:6px;font-size:13px;margin-bottom:8px;"

def _banner_verified_es(detail=""):
    text = detail or "Contenido generado directamente desde la base de conocimiento (sin IA)."
    return (
        f'<div style="background-color:#d4edda;border-left:4px solid #28a745;{_BANNER_STYLE}">'
        f'\U0001F7E2 <strong>Datos verificados</strong> \u2014 {text}'
        '</div>\n\n'
    )

def _banner_database_es(detail=""):
    text = detail or "La respuesta ha sido generada por el modelo de IA a partir de los materiales de la asignatura."
    return (
        f'<div style="background-color:#fff3cd;border-left:4px solid #ffc107;{_BANNER_STYLE}">'
        f'\U0001F7E1 <strong>Comentario IA</strong> \u2014 {text}'
        '</div>\n\n'
    )

def _banner_unverified_es(detail=""):
    text = detail or "Esta consulta está fuera del alcance de los materiales de la asignatura."
    return (
        f'<div style="background-color:#f8d7da;border-left:4px solid #dc3545;{_BANNER_STYLE}">'
        f'\U0001F534 <strong>No verificado</strong> \u2014 {text}'
        '</div>\n\n'
    )

# Reemplazar los banners del módulo base con las versiones en español
_svm._banner_verified = _banner_verified_es
_svm._banner_database = _banner_database_es
_svm._banner_unverified = _banner_unverified_es

from tutor_fonetica_base.transcriptor import transcribir, transcribir_palabra
from tutor_fonetica_base.errores_fonologicos.dispatch import (
    detectar_peticion_errores, dispatch_errores, dispatch_correccion,
    es_respuesta_ejercicio, es_abandono_ejercicio
)
from tutor_fonetica_base.progreso_alumno import (
    registrar_resultado, nivel_recomendado, mensaje_bienvenida_ejercicios,
    set_progress_dir
)
from tutor_fonetica_base.autoevaluacion import (
    set_autoeval_dir,
    registrar_practico, registrar_teorico,
    progreso_tema as autoeval_progreso_tema,
    formatear_progreso as autoeval_formatear_progreso,
    generar_prompt_evaluacion_teorica,
)
from tutor_fonetica_base.alofonos import (
    describir_alofono, describir_fonema, reconocer_alofono,
    formatear_descripcion, formatear_inventario_fonema, formatear_reconocimiento,
)


# ═══════════════════════════════════════════════════════════════════════
# DETECCIÓN DE PETICIONES SOBRE ALÓFONOS
# ═══════════════════════════════════════════════════════════════════════

def _es_peticion_alofono(msg: str) -> dict | None:
    """Detecta si el usuario pregunta sobre alófonos.

    Tipos de petición:
      - describir: "¿qué es [β̞]?", "describe el alófono [ŋ]"
      - reconocer: "oclusiva bilabial sonora", "¿qué alófono es una nasal velar?"
      - listar_fonema: "alófonos de /b/", "¿cuáles son los alófonos de /n/?"

    Returns:
        dict con 'tipo' y parámetros, o None.
    """
    msg_lower = msg.lower().strip()

    # Si el mensaje es sobre ejercicios o transcripción, no interceptar
    if any(kw in msg_lower for kw in ['ejercicio', 'practicar', 'transcribe', 'transcripción fonológica']):
        return None

    # ── Describir un alófono por símbolo: [β̞], [ŋ], etc. ──
    match = re.search(
        r'(?:qué\s+es|describe|descríbeme|explica|dime\s+qué\s+es)\s+'
        r'(?:el\s+)?(?:alófono\s+|sonido\s+)?\[([^\]]+)\]',
        msg_lower
    )
    if match:
        return {"tipo": "describir", "simbolo": match.group(1).strip()}

    # También: "el alófono [x]", "[x] qué es"
    match = re.search(r'\[([^\]]+)\]', msg)
    if match:
        simbolo = match.group(1).strip()
        if any(kw in msg_lower for kw in ['qué es', 'que es', 'describe', 'explica', 'dime']):
            return {"tipo": "describir", "simbolo": simbolo}

    # ── Listar alófonos de un fonema: "alófonos de /b/" ──
    match = re.search(
        r'(?:alófonos?|variantes?|realizaciones?)\s+(?:de(?:l)?\s+)?(?:fonema\s+)?/([^/]+)/',
        msg_lower
    )
    if match:
        return {"tipo": "listar_fonema", "fonema": match.group(1).strip()}

    # También: "¿cuáles son los alófonos de /n/?"
    match = re.search(
        r'(?:cuáles|cuales)\s+son\s+(?:los\s+)?(?:alófonos?|variantes?)\s+(?:de(?:l)?\s+)?(?:fonema\s+)?/([^/]+)/',
        msg_lower
    )
    if match:
        return {"tipo": "listar_fonema", "fonema": match.group(1).strip()}

    # ── Reconocer por descripción articulatoria ──
    # "¿qué alófono es una oclusiva bilabial sonora?"
    match = re.search(
        r'(?:qué|que|cuál|cual)\s+(?:alófono|alofono|sonido)\s+'
        r'(?:es\s+)?(?:una?\s+)?(.+?)(?:\?|$)',
        msg_lower
    )
    if match:
        desc = match.group(1).strip().rstrip('?')
        if len(desc.split()) >= 2:
            return {"tipo": "reconocer", "descripcion": desc}

    # "identifica: oclusiva bilabial sonora"
    match = re.search(
        r'(?:identifica|reconoce|clasifica)\s*:?\s*(.+)',
        msg_lower
    )
    if match:
        desc = match.group(1).strip().rstrip('?')
        if len(desc.split()) >= 2:
            return {"tipo": "reconocer", "descripcion": desc}

    return None


def _dispatch_alofono(peticion: dict) -> str:
    """Procesa una petición sobre alófonos y devuelve respuesta en markdown."""
    tipo = peticion["tipo"]

    if tipo == "describir":
        simbolo = peticion["simbolo"]
        resultados = describir_alofono(simbolo)
        if not resultados:
            return (f"No se ha encontrado el alófono [{simbolo}] en el inventario.\n\n"
                    f"Comprueba que usas la notación IPA correcta.")
        lineas = []
        for a in resultados:
            lineas.append(formatear_descripcion(a))
            lineas.append("")
        return "\n".join(lineas)

    elif tipo == "listar_fonema":
        fonema = peticion["fonema"]
        resultado = formatear_inventario_fonema(fonema)
        if resultado is None:
            return f"No se ha encontrado el fonema /{fonema}/ en el inventario."
        return resultado

    elif tipo == "reconocer":
        return formatear_reconocimiento(peticion["descripcion"])

    return ""


# ═══════════════════════════════════════════════════════════════════════
# DETECCIÓN DE TRANSCRIPCIONES
# ═══════════════════════════════════════════════════════════════════════

_PALABRAS_INAPROPIADAS = {
    # Insultos y palabras malsonantes
    'gilipollas', 'gilipollez', 'capullo', 'imbécil', 'imbecil', 'idiota',
    'subnormal', 'retrasado', 'retrasada', 'mongolo', 'mongola',
    'cabrón', 'cabron', 'cabrona', 'hijo de puta', 'hijoputa', 'hijaputa',
    'puta', 'puto', 'zorra', 'zorro', 'pendejo', 'pendeja',
    'maricón', 'maricon', 'marica', 'bollera',
    'mierda', 'mierdas', 'cagada', 'cagar', 'cagarse',
    'coño', 'cono', 'coñazo', 'joder', 'jódete', 'jodete',
    'hostia', 'hostias', 'ostia', 'ostias',
    'follar', 'follada', 'follón',
    'culo', 'culos', 'culada',
    'polla', 'pollas', 'pollón',
    'cojones', 'cojón', 'cojonudo',
    'tetas', 'tetón', 'tetona',
    'mamada', 'mamón', 'mamon', 'mamona',
    'chingar', 'chingada', 'verga',
    # Escatológicas
    'caca', 'culo', 'pedo', 'pis', 'meada', 'mear',
}


def _contiene_palabra_inapropiada(texto: str) -> bool:
    """Comprueba si el texto contiene palabras obscenas, insultos o escatológicas."""
    palabras = set(re.findall(r'[a-záéíóúüñ]+', texto.lower()))
    # Comprobar palabras individuales
    if palabras & _PALABRAS_INAPROPIADAS:
        return True
    # Comprobar expresiones multipalabra
    texto_lower = texto.lower()
    if 'hijo de puta' in texto_lower:
        return True
    return False


def _es_peticion_transcripcion(msg: str) -> str | None:
    """Detect if the user is asking for a transcription (phonological or phonetic).
    Returns the text to transcribe, or None."""
    msg_lower = msg.lower().strip()

    if any(kw in msg_lower for kw in ['ejercicio', 'practicar', 'práctica', 'entrenar']):
        return None

    # Preguntas sobre la transcripción como concepto (no peticiones de transcribir)
    if re.match(r'^¿?\s*(?:quién|quien|cuándo|cuando|dónde|donde|por\s+qué|porque|'
                r'qué\s+es|que\s+es|cómo\s+(?:se\s+)?(?:llama|creó|inventó|desarrolló|surgió))',
                msg_lower):
        return None

    patterns = [
        # Peticiones explícitas de transcripción fonológica
        r'transcri(?:be|pción)\s+fonológica(?:mente)?\s+(?:de\s+)?(?:la\s+(?:palabra|frase|oración|pseudopalabra)\s+)?["\']?(.+?)["\']?\s*$',
        r'transcri(?:be|pción)\s+fonológica(?:mente)?\s*:\s*["\']?(.+?)["\']?\s*$',
        r'(?:haz|hazme|dame)\s+(?:la\s+)?transcripción\s+(?:fonológica\s+)?(?:de\s+)?["\']?(.+?)["\']?\s*$',
        r'transcri(?:be|bir)\s+fonológicamente\s+["\']?(.+?)["\']?\s*$',
        r'transcripción\s+fonológica\s+(?:de\s+)?["\']?(.+?)["\']?\s*$',
        # Peticiones explícitas de transcripción fonética
        r'transcri(?:be|pción)\s+fonética(?:mente)?\s+(?:de\s+)?(?:la\s+(?:palabra|frase|oración|pseudopalabra)\s+)?["\']?(.+?)["\']?\s*$',
        r'transcri(?:be|bir)\s+fonéticamente\s+(?:(?:la\s+)?(?:palabra|pseudopalabra)\s+)?["\']?(.+?)["\']?\s*$',
        # Peticiones genéricas de transcripción (sin especificar tipo)
        r'transcri(?:be|pción)\s+(?:de\s+)?(?:la\s+(?:palabra|frase|oración|pseudopalabra)\s+)?["\']?(.+?)["\']?\s*$',
        r'transcri(?:be|bir)\s+(?:(?:la\s+)?(?:palabra|pseudopalabra)\s+)?["\']?(.+?)["\']?\s*$',
        # "cómo se transcribe X", "cuál es la transcripción de X"
        r'¿?cómo\s+se\s+transcribe\s+(?:fonológicamente\s+)?["\']?(.+?)["\']?\s*\??$',
        r'¿?(?:cuál|cual)\s+es\s+la\s+transcripción\s+(?:fonológica\s+)?(?:de\s+)?(?:la\s+(?:palabra|frase|pseudopalabra)\s+)?["\']?(.+?)["\']?\s*\??$',
        # "fonemas de X", "qué fonemas tiene X"
        r'(?:los\s+)?fonemas\s+de\s+["\']?(.+?)["\']?\s*\??$',
        r'¿?(?:qué|cuáles?\s+son\s+los)\s+fonemas\s+(?:de\s+|que\s+tiene\s+|tiene\s+)["\']?(.+?)["\']?\s*\??$',
        # "cómo se pronuncia X" (fonológicamente)
        r'¿?cómo\s+se\s+(?:pronuncia|dice)\s+(?:fonológicamente\s+)?["\']?(.+?)["\']?\s*\??$',
    ]

    for pattern in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            texto = match.group(1).strip().strip('"\'').strip('?')
            # Filtrar si el texto extraído es demasiado largo o parece una pregunta
            if not texto or len(texto) >= 200 or texto.startswith('¿'):
                continue
            # Filtrar si solo capturó un término técnico (no es texto para transcribir)
            _technical = {'fonética', 'fonetica', 'fonológica', 'fonologica',
                          'fonéticamente', 'foneticamente', 'fonológicamente', 'fonologicamente'}
            if texto.lower() in _technical:
                continue
            # Bloquear palabras obscenas, insultos y escatológicas
            if _contiene_palabra_inapropiada(texto):
                return "__BLOCKED__"
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

    respuesta += '<p style="font-size:11px;color:#94a3b8;margin-top:8px;">Transcripción generada mediante un algoritmo programado en Python (no por IA).</p>'

    return respuesta, False


def _corregir_transcripciones_en_texto(texto: str) -> str:
    """Postprocesa la respuesta del LLM para reemplazar transcripciones fonológicas
    por las generadas programáticamente. Busca patrones como:
      "palabra" → /transcripción/
      «palabra» → /transcripción/
      palabra → /transcripción/
    y reemplaza la transcripción del LLM por la programática."""

    # 1. Buscar "palabra" → /.../ y reemplazar con transcripción programática
    def reemplazar_con_programatica(m):
        palabra = m.group(1).strip()
        transcripcion_llm = m.group(2)
        resultado = transcribir(palabra)
        if isinstance(resultado, str):
            return m.group(0).replace('/' + transcripcion_llm + '/', resultado)
        return m.group(0)

    # Patrón: "palabra" → /transcripción/ (con comillas, «», o sin)
    texto = re.sub(
        r'[""«]([a-záéíóúüñ]+(?:\s+[a-záéíóúüñ]+)*)[""»]'
        r'\s*→\s*/([^/]+)/',
        reemplazar_con_programatica,
        texto
    )
    # Sin comillas: palabra → /transcripción/
    texto = re.sub(
        r'(?<!\w)([a-záéíóúüñ]+(?:\s+[a-záéíóúüñ]+)*)\s*→\s*/([^/]+)/',
        reemplazar_con_programatica,
        texto
    )

    # 2. Buscar /palabra_española/ (sin IPA) y transcribir
    def reemplazar_palabra_plana(m):
        palabra = m.group(1).strip()
        resultado = transcribir(palabra)
        if isinstance(resultado, str):
            return resultado
        return m.group(0)

    texto = re.sub(
        r'/([a-záéíóúüñ]{2,}(?:\s+[a-záéíóúüñ]+)*)/',
        reemplazar_palabra_plana,
        texto
    )

    # 3. Reemplazar ʎ por ʝ (yeísmo)
    texto = texto.replace('ʎ', 'ʝ')

    return texto


def _es_pregunta_sobre_tema(msg: str) -> int | None:
    """Detecta si el usuario pregunta qué se estudia en un tema concreto.
    Returns el número de tema (1-6) o None."""
    msg_lower = msg.lower().strip()
    patterns = [
        r'(?:qué|que)\s+(?:se\s+)?(?:estudia|ve|trata|aprende|cubre|incluye|hay)\s+(?:en\s+)?(?:el\s+)?tema\s+(\d)',
        r'(?:de\s+qué|de\s+que)\s+(?:va|trata)\s+(?:el\s+)?tema\s+(\d)',
        r'(?:contenido|resumen|índice)\s+(?:del?\s+)?tema\s+(\d)',
        r'tema\s+(\d)\s+(?:de\s+qué|que\s+(?:se\s+)?estudia|contenido|resumen)',
        r'(?:háblame|cuéntame|explica)\s+(?:del?\s+|sobre\s+(?:el\s+)?)?tema\s+(\d)',
    ]
    for p in patterns:
        m = re.search(p, msg_lower)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 6:
                return n
    return None


def _respuesta_sobre_tema(tema_id: int, agent_dir: str) -> str | None:
    """Genera una respuesta programática sobre qué se estudia en un tema."""
    import json as _json
    temas_path = os.path.join(agent_dir, 'temas.json')
    if not os.path.exists(temas_path):
        return None
    with open(temas_path, 'r', encoding='utf-8') as f:
        data = _json.load(f)
    temas = data.get('temas', [])
    tema = next((t for t in temas if t['id'] == tema_id), None)
    if not tema:
        return None

    lineas = [f"## Tema {tema['id']} — {tema['titulo']}\n"]
    lineas.append(tema['resumen'])
    lineas.append("")

    # Índice de contenidos
    if tema.get('contenidos'):
        lineas.append("### Contenidos\n")
        for bloque in tema['contenidos']:
            lineas.append(f"- **{bloque['bloque']}**")
            for sub in bloque.get('subbloques', []):
                lineas.append(f"  - {sub['nombre']}")
        lineas.append("")

    # Ejercicios disponibles
    if tema.get('ejercicios'):
        lineas.append(f"### Ejercicios prácticos: {len(tema['ejercicios'])} disponible(s)\n")

    return "\n".join(lineas)


def _es_pregunta_general(msg: str) -> bool:
    """Detecta si el mensaje es una pregunta general (no una respuesta de ejercicio).
    Permite que el alumno haga preguntas mientras tiene un ejercicio activo."""
    msg_lower = msg.lower().strip()
    # Preguntas explícitas
    if msg_lower.startswith('¿') or msg_lower.endswith('?'):
        return True
    # Palabras interrogativas al inicio
    if re.match(r'^(qué|que|cómo|como|cuál|cual|cuáles|cuales|cuándo|cuando|'
                r'por qué|porque|dónde|donde|quién|quien|explica|describe|'
                r'descríbeme|dime|háblame)\b', msg_lower):
        return True
    return False


def _es_peticion_correccion(msg: str) -> bool:
    """Detecta si el alumno pide corregir o ver la solución."""
    msg_lower = msg.lower().strip()
    return any(t in msg_lower for t in [
        'corregir', 'corrígeme', 'corrige', 'solución', 'solucion',
        'respuesta correcta', 'ver solución', 'ver solucion', 'muestra la solución',
    ])


# ═══════════════════════════════════════════════════════════════════════
# CLASE BASE
# ═══════════════════════════════════════════════════════════════════════

class BaseTutorFonetica(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    """Clase base para agentes tutores de Fonética.

    Subclases deben definir:
        _AGENT_FILE = __file__  (en el módulo del agente concreto)
    """

    def __init__(self):
        super().__init__()
        self._session_state = {}
        # Configurar directorios en el agente concreto
        agent_dir = os.path.dirname(os.path.abspath(self._AGENT_FILE))
        set_progress_dir(os.path.join(agent_dir, "progress"))
        set_autoeval_dir(os.path.join(agent_dir, "autoevaluacion"))

    # -- Helpers --

    def _get_username(self, kwargs) -> str | None:
        return kwargs.get('username') or self._session_state.get('username')

    def _registrar_correccion(self, correccion_texto: str, username: str):
        """Registra el resultado de una corrección de transcripción en el progreso."""
        if not username:
            return
        ejercicio = self._session_state.get('ejercicio_actual')
        if not ejercicio or self._session_state.get('ejercicio_tipo') != 'transcripcion':
            return
        match = re.search(r'(\d+(?:\.\d+)?)%\s*\((\d+)/(\d+)\)', correccion_texto)
        if match:
            puntuacion = float(match.group(1))
            num_items = int(match.group(3))
            nivel = ejercicio.get('nivel', 1)
            modo = ejercicio.get('modo', 'fonologica_tipica')
            registrar_resultado(username, nivel, puntuacion, num_items, modo=modo)

    # -- Puntos de extensión para subclases --

    def _get_transcription_system_prompt(self) -> str:
        """Prompt del sistema para la explicación pedagógica tras transcripción.
        Las subclases pueden sobreescribirlo para personalizar."""
        return (
            "Eres un tutor de fonología del español. "
            "El sistema ha generado automáticamente la transcripción fonológica que aparece abajo. "
            "Tu tarea es añadir una breve explicación pedagógica (3-5 líneas máximo). "
            "NO modifiques la transcripción — es correcta. "
            "NO empieces con 'Explicación' ni 'Explicación pedagógica' — ve directo al contenido. "
            "Responde en español. Sé breve y claro."
        )

    # -- Chat síncrono --

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        username = self._get_username(kwargs)
        if username:
            self._session_state['username'] = username

        # 1. Check transcription request
        texto = _es_peticion_transcripcion(user_message)
        if texto == "__BLOCKED__":
            return "Lo siento, no puedo transcribir ese tipo de contenido. Estoy aquí para ayudarte con la asignatura. ¿Quieres practicar con otra palabra?"
        if texto:
            respuesta, es_error = _generar_respuesta_transcripcion(texto)
            if es_error:
                return respuesta

            model = kwargs.get('model_override') or self.model
            messages = [
                {"role": "system", "content": self._get_transcription_system_prompt()},
                {"role": "user", "content": f"Palabra/frase: \"{texto}\"\n\nTranscripción generada:\n{respuesta}"}
            ]
            llm_response = self.client.chat.complete(model=model, messages=messages)
            explicacion = llm_response.choices[0].message.content
            return (respuesta
                    + '\n\n<details style="margin-top:8px;"><summary style="cursor:pointer;color:#4250b3;font-weight:600;font-size:13px;">Explicación</summary>'
                    + '<div style="margin-top:8px;font-size:13px;line-height:1.6;">\n\n'
                    + explicacion
                    + '\n\n</div></details>')

        # 2. Active exercise
        if self._session_state.get('ejercicio_actual'):
            if es_abandono_ejercicio(user_message):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
                return "De acuerdo, dejamos el ejercicio. ¿En qué puedo ayudarte?"

            peticion_nueva = detectar_peticion_errores(user_message)
            if peticion_nueva and peticion_nueva.get('accion') in ('ejercicio', 'ejercicio_transcripcion'):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
            elif _es_pregunta_general(user_message):
                # Es una pregunta, no una respuesta de ejercicio → dejar pasar
                # al flujo normal (pasos 3-5) sin tocar el ejercicio activo
                pass
            else:
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

                self._session_state['respuestas_alumno'] = user_message
                return 'Respuestas recibidas.\n\n<div class="ejercicio-btns-placeholder"></div>'

        # 3. Check question about a tema
        tema_pregunta = _es_pregunta_sobre_tema(user_message)
        if tema_pregunta:
            agent_dir = os.path.dirname(os.path.abspath(self._AGENT_FILE))
            resp = _respuesta_sobre_tema(tema_pregunta, agent_dir)
            if resp:
                return resp

        # 4. Check allophone query
        peticion_alofono = _es_peticion_alofono(user_message)
        if peticion_alofono:
            return _dispatch_alofono(peticion_alofono)

        # 5. Check phonological error request
        peticion = detectar_peticion_errores(user_message)
        if peticion:
            if peticion.get('accion') == 'ejercicio_transcripcion' and username:
                msg = mensaje_bienvenida_ejercicios(username)
                if msg:
                    if peticion.get('nivel', 1) == 1:
                        recomendado = nivel_recomendado(username)
                        peticion['nivel'] = recomendado
            respuesta = dispatch_errores(peticion, self._session_state)
            if respuesta:
                if peticion.get('accion') == 'ejercicio_transcripcion' and username:
                    msg = mensaje_bienvenida_ejercicios(username)
                    if msg:
                        respuesta = f"📊 *{msg}*\n\n---\n\n" + respuesta
                return respuesta

        # 5. Normal RAG (postprocesar transcripciones del LLM)
        respuesta = super().chat(user_message, history, **kwargs)
        return _corregir_transcripciones_en_texto(respuesta)

    # -- Chat streaming --

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        username = self._get_username(kwargs)
        if username:
            self._session_state['username'] = username

        # 1. Transcription request
        texto = _es_peticion_transcripcion(user_message)
        if texto == "__BLOCKED__":
            yield "Lo siento, no puedo transcribir ese tipo de contenido. Estoy aquí para ayudarte con la asignatura. ¿Quieres practicar con otra palabra?"
            return
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

            yield ("procedural_banner", _banner_verified_es(
                "Transcripción generada automáticamente (verificada, sin IA)."))
            yield respuesta

            yield '\n\n<details style="margin-top:8px;"><summary style="cursor:pointer;color:#4250b3;font-weight:600;font-size:13px;">Explicación</summary><div style="margin-top:8px;font-size:13px;line-height:1.6;">\n\n'

            model = kwargs.get('model_override') or self.model
            messages = [
                {"role": "system", "content": self._get_transcription_system_prompt()},
                {"role": "user", "content": f"Palabra/frase: \"{texto}\"\n\nTranscripción generada:\n{respuesta}"}
            ]

            async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
                if chunk.data.choices and chunk.data.choices[0].delta.content:
                    yield chunk.data.choices[0].delta.content

            yield '\n\n</div></details>'
            return

        # 2. Active exercise
        if self._session_state.get('ejercicio_actual'):
            if es_abandono_ejercicio(user_message):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
                yield "De acuerdo, dejamos el ejercicio. ¿En qué puedo ayudarte?"
                return

            peticion_nueva = detectar_peticion_errores(user_message)
            if peticion_nueva and peticion_nueva.get('accion') in ('ejercicio', 'ejercicio_transcripcion'):
                self._session_state.pop('ejercicio_actual', None)
                self._session_state.pop('ejercicio_tipo', None)
            elif _es_pregunta_general(user_message):
                pass  # Es una pregunta → dejar pasar al flujo normal
            else:
                if _es_peticion_correccion(user_message):
                    respuestas = self._session_state.get('respuestas_alumno', '')
                    if not respuestas:
                        yield "No he recibido tus respuestas todavía. Escríbelas primero y luego pulsa **Corregir**."
                        return
                else:
                    self._session_state['respuestas_alumno'] = user_message
                    yield 'Respuestas recibidas.\n\n<div class="ejercicio-btns-placeholder"></div>'
                    return

                if not self._chromadb_initialized:
                    yield ("status", "Preparando...")
                    self._init_chromadb()

                yield ("procedural_banner", _banner_verified_es(
                    "Corrección generada automáticamente (verificada, sin IA)."))

                correccion, incorrectas = dispatch_correccion(
                    self._session_state['ejercicio_actual'],
                    respuestas,
                    ejercicio_tipo=self._session_state.get('ejercicio_tipo', 'errores'),
                    session_state=self._session_state,
                )
                self._registrar_correccion(correccion, username)
                yield correccion

                ejercicio_tipo_ej = self._session_state.get('ejercicio_tipo', 'errores')
                if ejercicio_tipo_ej != 'transcripcion':
                    ejercicio = self._session_state.get('ejercicio_actual', {})
                    from tutor_fonetica_base.errores_fonologicos.catalogo_errores import generar_retroalimentacion
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

        # 3. Question about a tema
        tema_pregunta = _es_pregunta_sobre_tema(user_message)
        if tema_pregunta:
            agent_dir = os.path.dirname(os.path.abspath(self._AGENT_FILE))
            resp = _respuesta_sobre_tema(tema_pregunta, agent_dir)
            if resp:
                yield ("procedural_banner", _banner_verified_es(
                    "Información del programa de la asignatura (verificada, sin IA)."))
                yield resp
                return

        # 4. Allophone query
        peticion_alofono = _es_peticion_alofono(user_message)
        if peticion_alofono:
            yield ("procedural_banner", _banner_verified_es(
                "Información generada desde el inventario de alófonos (verificada, sin IA)."))
            yield _dispatch_alofono(peticion_alofono)
            return

        # 5. Phonological error request
        peticion = detectar_peticion_errores(user_message)
        if peticion:
            if not self._chromadb_initialized:
                yield ("status", "Preparando...")
                self._init_chromadb()

            if peticion.get('accion') == 'ejercicio_transcripcion' and username:
                if peticion.get('nivel', 1) == 1:
                    recomendado = nivel_recomendado(username)
                    peticion['nivel'] = recomendado

            respuesta = dispatch_errores(peticion, self._session_state)
            if respuesta:
                if peticion['accion'] == 'ejercicio_transcripcion':
                    yield ("procedural_banner", _banner_verified_es(
                        "Ejercicio generado automáticamente."))
                    if username:
                        msg = mensaje_bienvenida_ejercicios(username)
                        if msg:
                            yield f"*{msg}*\n\n---\n\n"
                elif peticion['accion'] == 'ejercicio':
                    yield ("procedural_banner", _banner_verified_es(
                        "Ejercicio generado automáticamente."))
                elif peticion['accion'] in ('analizar', 'clasificar'):
                    yield ("procedural_banner", _banner_verified_es(
                        "Análisis generado automáticamente (verificado, sin IA)."))
                yield respuesta
                return

        # 5. Normal RAG streaming (corregir transcripciones del LLM en cada chunk)
        yield ("procedural_banner", _banner_database_es(
            "La respuesta ha sido generada por el modelo de IA a partir de los materiales de la asignatura. Podría contener errores."))
        async for item in super().chat_stream(user_message, history, **kwargs):
            if isinstance(item, str):
                yield item.replace('ʎ', 'ʝ')
            elif isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], str):
                yield (item[0], item[1].replace('ʎ', 'ʝ'))
            else:
                yield item
