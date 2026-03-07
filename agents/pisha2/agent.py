"""
Pisha2 - Agente Text-to-SQL
Convierte preguntas en lenguaje natural a consultas SQL usando qwen2.5-coder via Ollama.
Usa Chain-of-Thought (CoT) para mejorar el razonamiento en consultas complejas.
"""

import os
import sys
import sqlite3
import logging
import subprocess
import time

# Añadir web/ y apps/ al path para importar módulos compartidos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps"))

# Ruta al script consultar_sql.py
APPS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "apps")
CONSULTAR_SQL_PATH = os.path.join(APPS_DIR, "consultar_sql.py")
from llm_client import LLMClient
from normalize import normalize_text_for_search

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("pisha2")


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")
        self.schema_path = os.path.join(os.path.dirname(__file__), "data", "database_schema.md")
        self._cached_schema = None  # Cache del esquema
        self.system_prompt = """You are Pisha2, a database assistant specialized in converting natural language questions to SQL queries.

IMPORTANT RULES:
1. You help users query a SQLite database by understanding their questions in natural language
2. When the user asks about data, you will receive the database schema and query results
3. Explain the results clearly and concisely in the user\'s language
4. If you cannot answer a question with the available data, explain why
5. Never make up data - only use the actual query results provided

RESPONSE FORMAT:
- Provide only data, do not be conversational
- When presenting data, use tables or lists for clarity
- If the query returned no results, explain what that means
- Suggest related questions the user might want to ask"""

        # Cliente local (Ollama)
        self.local_client = self._init_local_client()
        # Modelo para generar SQL (usa el modelo del provider configurado)
        self.sql_model = self._get_model()

        # Configuración
        self.default_page_size = 20  # Resultados por página
        self.max_history = 10  # Máximo de consultas en historial

        # Estado por sesión (cada session_id tiene su propio contexto)
        self._sessions = {}

    def _get_session_state(self, session_id: str) -> dict:
        """Obtiene o crea el estado para una sesión."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                'last_sql_query': None,
                'last_results': [],
                'last_results_grouped': False,
                'last_display_offset': 0,
                'query_history': [],
                'last_user_question': None,
            }
        return self._sessions[session_id]

    @property
    def last_sql_query(self) -> str | None:
        """Expone last_sql_query de la sesión por defecto para uso externo (benchmarks)."""
        state = self._get_session_state("default")
        return state.get('last_sql_query')

    @property
    def last_results(self) -> list:
        """Expone last_results de la sesión por defecto para uso externo (benchmarks)."""
        state = self._get_session_state("default")
        return state.get('last_results', [])

    def _is_show_more_query(self, question: str) -> bool:
        """Detecta si el usuario quiere ver más resultados."""
        question_lower = question.lower().strip()
        show_more_patterns = [
            "muéstrame más", "muestrame mas", "muestrame más", "muéstrame mas",
            "ver más", "ver mas", "mostrar más", "mostrar mas",
            "siguientes", "los siguientes", "más resultados", "mas resultados",
            "continuar", "continúa", "continua",
            "muéstrame todos", "muestrame todos", "ver todos", "mostrar todos",
            "todos los resultados", "lista completa",
        ]
        for pattern in show_more_patterns:
            if pattern in question_lower:
                return True
        return False

    def _is_back_request(self, question: str) -> bool:
        """Detecta si el usuario quiere volver a una búsqueda anterior."""
        question_lower = question.lower().strip()
        back_patterns = [
            "volver atrás", "volver atras", "vuelve atrás", "vuelve atras",
            "búsqueda anterior", "busqueda anterior", "consulta anterior",
            "deshacer", "undo", "atrás", "atras",
            "volver a la anterior", "restaurar", "recuperar anterior",
            "quita el filtro", "quitar filtro", "sin filtro",
            "volver al principio", "empezar de nuevo",
        ]
        for pattern in back_patterns:
            if pattern in question_lower:
                return True
        return False

    def _is_history_request(self, question: str) -> bool:
        """Detecta si el usuario quiere ver el historial de consultas."""
        question_lower = question.lower().strip()
        history_patterns = [
            "historial", "ver historial", "mostrar historial",
            "mis consultas", "ver consultas", "consultas anteriores",
            "mis preguntas", "ver preguntas", "preguntas anteriores",
            "qué he preguntado", "que he preguntado",
            "ver sql", "mostrar sql", "mis sql",
        ]
        for pattern in history_patterns:
            if pattern in question_lower:
                return True
        return False

    def _is_show_field_request(self, question: str) -> tuple:
        """
        Detecta si el usuario quiere ver un campo adicional.
        Retorna (True, nombre_campo) si detecta, (False, None) si no.
        """
        import re
        question_lower = question.lower().strip()

        # Mapeo de términos del usuario a nombres de campos
        field_mapping = {
            'centro': 'uma_faculties',
            'centros': 'uma_faculties',
            'facultad': 'uma_faculties',
            'facultades': 'uma_faculties',
            'titulacion': 'uma_degrees',
            'titulaciones': 'uma_degrees',
            'carrera': 'uma_degrees',
            'carreras': 'uma_degrees',
            'grado': 'uma_degrees',
            'grados': 'uma_degrees',
            'programa': 'mobility_program',
            'programas': 'mobility_program',
            'tipo de programa': 'mobility_program',
            'idioma': 'language_requirements',
            'idiomas': 'language_requirements',
            'requisito': 'language_requirements',
            'requisitos': 'language_requirements',
            'plaza': 'student_vacancies',
            'plazas': 'student_vacancies',
            'vacantes': 'student_vacancies',
            'duracion': 'student_vacancies',
            'duración': 'student_vacancies',
            'fecha': 'start_date',
            'fechas': 'start_date',
            'vigencia': 'start_date',
            'pais': 'destination_country',
            'país': 'destination_country',
            'universidad': 'host_institution',
            'universidades': 'host_institution',
            'institucion': 'host_institution',
            'institución': 'host_institution',
            'facultad destino': 'destination_faculty',
            'nivel': 'available_levels',
            'niveles': 'available_levels',
        }

        # Patrones para detectar peticiones de mostrar campo adicional
        show_patterns = [
            r'muestra(?:me)?\s+también\s+(?:el|la|los|las)?\s*(.+)',
            r'añade\s+también\s+(?:el|la|los|las)?\s*(.+)',
            r'incluye\s+también\s+(?:el|la|los|las)?\s*(.+)',
            r'muestra(?:me)?\s+(?:el|la|los|las)?\s*(.+)',
            r'añade\s+(?:el|la|los|las)?\s*(.+)',
            r'incluye\s+(?:el|la|los|las)?\s*(.+)',
            r'pon(?:me)?\s+(?:el|la|los|las)?\s*(.+)',
            r'quiero\s+ver\s+(?:el|la|los|las)?\s*(.+)',
            r'ver\s+(?:el|la|los|las)?\s*(.+)',
        ]

        for pattern in show_patterns:
            match = re.search(pattern, question_lower)
            if match:
                requested_field = match.group(1).strip()
                # Buscar en el mapeo
                for term, field_name in field_mapping.items():
                    if term in requested_field:
                        return (True, field_name)

        return (False, None)

    def _is_sort_request(self, question: str) -> tuple:
        """
        Detecta si el usuario quiere ordenar los resultados.
        Retorna (True, criterio, direccion) si detecta, (False, None, None) si no.
        """
        import re
        question_lower = question.lower().strip()

        # Mapeo de términos a campos de ordenación
        sort_mapping = {
            'pais': 'destination_country',
            'país': 'destination_country',
            'universidad': 'host_institution',
            'nombre': 'host_institution',
            'institucion': 'host_institution',
            'institución': 'host_institution',
            'programa': 'mobility_program',
            'idioma': 'language_requirements',
            'facultad': 'uma_faculties',
            'centro': 'uma_faculties',
            'alfabeticamente': 'host_institution',
            'alfabéticamente': 'host_institution',
        }

        # Patrones para detectar peticiones de ordenación
        sort_patterns = [
            r'ordena(?:r|los|las|me)?\s+(?:por|según)?\s*(.+)',
            r'ordéna(?:me|los|las)?\s+(?:por|según)?\s*(.+)',
            r'clasifica(?:r|los|las)?\s+(?:por|según)?\s*(.+)',
            r'organiza(?:r|los|las)?\s+(?:por|según)?\s*(.+)',
            r'(?:de\s+)?(?:la\s+)?(?:a\s+a\s+la\s+)?z(?:\s+|$)',
            r'(?:de\s+)?(?:la\s+)?z\s+a\s+(?:la\s+)?a(?:\s+|$)',
        ]

        # Detectar dirección
        ascending = True
        if 'descend' in question_lower or 'z a a' in question_lower or 'mayor a menor' in question_lower:
            ascending = False

        for pattern in sort_patterns:
            match = re.search(pattern, question_lower)
            if match:
                if match.groups():
                    requested_sort = match.group(1).strip()
                    # Buscar en el mapeo
                    for term, field_name in sort_mapping.items():
                        if term in requested_sort:
                            return (True, field_name, ascending)
                    # Si pide alfabéticamente sin especificar
                    if 'alfab' in requested_sort:
                        return (True, 'host_institution', ascending)
                else:
                    # Patrón de A-Z o Z-A
                    return (True, 'host_institution', ascending)

        # Detectar patrones más simples
        if 'ordena' in question_lower or 'ordéna' in question_lower:
            for term, field_name in sort_mapping.items():
                if term in question_lower:
                    return (True, field_name, ascending)

        return (False, None, None)

    def _show_history(self, session_id: str) -> str:
        """Muestra el historial de consultas recientes con su SQL."""
        state = self._get_session_state(session_id)

        if not state['query_history'] and not state['last_sql_query']:
            return "📋 No hay historial de consultas todavía."

        response_parts = ["📋 **Historial de consultas**\n"]

        # Mostrar consultas del historial (de más antigua a más reciente)
        all_queries = []

        for entry in state['query_history']:
            all_queries.append({
                'question': entry.get('question', ''),
                'sql': entry.get('sql', ''),
                'num_results': len(entry.get('results', []))
            })

        # Añadir la consulta actual si existe
        if state['last_sql_query']:
            all_queries.append({
                'question': state['last_user_question'] or '(consulta actual)',
                'sql': state['last_sql_query'],
                'num_results': len(state['last_results'])
            })

        if not all_queries:
            return "📋 No hay historial de consultas todavía."

        for i, entry in enumerate(all_queries, 1):
            response_parts.append(f"### {i}. {entry['question']}")
            response_parts.append(f"```sql\n{entry['sql']}\n```")
            response_parts.append(f"*Resultados: {entry['num_results']}*\n")

        response_parts.append("---")
        response_parts.append("💡 *Puedes decir \"volver atrás\" para restaurar una consulta anterior.*")

        return "\n".join(response_parts)

    def _handle_back_request(self, session_id: str) -> str:
        """Restaura la búsqueda anterior del historial o re-muestra los resultados actuales."""
        state = self._get_session_state(session_id)

        # Si hay historial, restaurar el estado anterior
        if state['query_history']:
            previous_state = state['query_history'].pop()
            state['last_sql_query'] = previous_state['sql']
            state['last_results'] = previous_state['results']
            state['last_user_question'] = previous_state.get('question', '')
            state['last_results_grouped'] = previous_state.get('grouped', False)
            state['last_display_offset'] = min(self.default_page_size, len(state['last_results']))

            num_results = len(state['last_results'])
            history_remaining = len(state['query_history'])

            response_parts = [f"⏪ **Volviendo a la búsqueda anterior**\n"]

            # Mostrar la pregunta original si existe
            if state['last_user_question']:
                response_parts.append(f"📝 *\"{state['last_user_question']}\"*\n")

            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

            if history_remaining > 0:
                response_parts.append(f"*({history_remaining} búsqueda(s) más en el historial)*\n")

            # Mostrar resumen de resultados
            if num_results > 20:
                response_parts.append(f"📊 **{num_results} resultados**\n")
                response_parts.append('💡 *Di "Muéstrame los resultados" para ver la lista*')
            else:
                response_parts.append(self._format_results_basic(state['last_results']))

            return "\n".join(response_parts)

        # Si no hay historial pero hay resultados actuales, re-mostrarlos
        if state['last_results']:
            state['last_display_offset'] = min(self.default_page_size, len(state['last_results']))
            num_results = len(state['last_results'])

            response_parts = [f"📋 **Volviendo a los resultados actuales**\n"]

            # Mostrar la pregunta original si existe
            if state['last_user_question']:
                response_parts.append(f"📝 *\"{state['last_user_question']}\"*\n")

            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

            if num_results > 20:
                response_parts.append(f"📊 **{num_results} resultados**\n")
                response_parts.append('💡 *Di "Muéstrame los resultados" para ver la lista*')
            else:
                response_parts.append(self._format_results_basic(state['last_results']))

            return "\n".join(response_parts)

        return "⚠️ No hay búsquedas anteriores en el historial."

    def _save_to_history(self, session_id: str, user_question: str = None):
        """Guarda el estado actual en el historial antes de refinar."""
        state = self._get_session_state(session_id)

        if state['last_sql_query'] and state['last_results']:
            # Evitar duplicados consecutivos
            if state['query_history'] and state['query_history'][-1]['sql'] == state['last_sql_query']:
                return

            state['query_history'].append({
                'sql': state['last_sql_query'],
                'results': state['last_results'].copy(),
                'question': state['last_user_question'] or user_question,
                'grouped': state['last_results_grouped']
            })

            # Limitar tamaño del historial
            if len(state['query_history']) > self.max_history:
                state['query_history'].pop(0)

    def _handle_show_field(self, session_id: str, field_name: str) -> str:
        """Muestra los resultados actuales añadiendo un campo adicional a la información básica."""
        state = self._get_session_state(session_id)

        if not state['last_results']:
            return "⚠️ No hay resultados previos. Primero realiza una búsqueda."

        results = state['last_results']
        num_results = len(results)

        # Mapeo de nombres de campo a etiquetas legibles
        field_labels = {
            'uma_faculties': '🏫 Centro UMA',
            'uma_degrees': '📚 Titulaciones',
            'mobility_program': '📋 Programa',
            'language_requirements': '🗣️ Idioma',
            'student_vacancies': '🎓 Plazas',
            'start_date': '📅 Fecha inicio',
            'end_date': '📅 Fecha fin',
            'destination_country': '🌍 País',
            'host_institution': '🏛️ Universidad',
            'destination_faculty': '🎯 Facultad destino',
            'available_levels': '📈 Niveles',
        }

        # Campos que ya se muestran por defecto
        default_fields = {'host_institution', 'destination_country', 'mobility_program',
                         'student_vacancies', 'language_requirements'}

        label = field_labels.get(field_name, field_name)

        # Si el campo ya se muestra por defecto, indicarlo
        if field_name in default_fields:
            response_parts = [f"✅ **{num_results} resultado(s)** (el campo {label} ya se muestra)\n"]
        else:
            response_parts = [f"✅ **{num_results} resultado(s)** - Añadiendo: {label}\n"]

        # Mostrar máximo 20 resultados con información completa + campo adicional
        max_display = min(20, num_results)
        for i, r in enumerate(results[:max_display], 1):
            institution = r.get('host_institution', 'N/A')
            country = r.get('destination_country', 'N/A')
            program = r.get('mobility_program', 'N/A')

            response_parts.append(f"**{i}. 🏛️ {institution}**")
            response_parts.append(f"- **País:** {country}")
            response_parts.append(f"- **Programa:** {program}")

            # Plazas (resumido)
            vacancies = r.get('student_vacancies', 'N/A')
            if vacancies and vacancies != 'N/A':
                # Extraer solo el número de plazas si es posible
                import re
                match = re.search(r'Plazas:\s*(\d+)', str(vacancies))
                if match:
                    response_parts.append(f"- **Plazas:** {match.group(1)}")
                else:
                    response_parts.append(f"- **Plazas:** {str(vacancies)[:50]}...")

            # Idioma (resumido)
            lang = r.get('language_requirements', 'N/A')
            if lang and lang != 'N/A':
                lang_short = self._extract_language_level(lang) if hasattr(self, '_extract_language_level') else lang
                if len(str(lang_short)) > 50:
                    lang_short = str(lang_short)[:50] + "..."
                response_parts.append(f"- **Idioma:** {lang_short}")

            # Campo adicional solicitado (si no es uno de los que ya mostramos)
            if field_name not in default_fields:
                field_value = r.get(field_name, 'N/A')
                if field_value and field_value != 'N/A':
                    # Truncar valores muy largos
                    if len(str(field_value)) > 100:
                        field_value = str(field_value)[:100] + "..."
                    response_parts.append(f"- **{label}:** {field_value}")

            response_parts.append("")

        if num_results > max_display:
            remaining = num_results - max_display
            response_parts.append(f"*... y {remaining} convenio(s) más*")

        response_parts.append("---")
        response_parts.append('💡 *"Muestra también las titulaciones" | "Ordena por país"*')

        return "\n".join(response_parts)

    def _handle_sort_results(self, session_id: str, sort_field: str, ascending: bool = True) -> str:
        """Ordena los resultados actuales por un campo específico."""
        state = self._get_session_state(session_id)

        if not state['last_results']:
            return "⚠️ No hay resultados previos. Primero realiza una búsqueda."

        results = state['last_results'].copy()
        num_results = len(results)

        # Ordenar
        try:
            results.sort(key=lambda x: str(x.get(sort_field, '')).lower(), reverse=not ascending)
            state['last_results'] = results
        except Exception as e:
            return f"⚠️ No se pudo ordenar por ese campo: {e}"

        # Mapeo de nombres de campo a etiquetas legibles
        field_labels = {
            'destination_country': 'país',
            'host_institution': 'universidad',
            'mobility_program': 'programa',
            'language_requirements': 'idioma',
            'uma_faculties': 'facultad UMA',
        }

        sort_label = field_labels.get(sort_field, sort_field)
        direction = "A→Z" if ascending else "Z→A"

        response_parts = [f"📊 **{num_results} resultado(s)** - Ordenados por {sort_label} ({direction})\n"]

        # Mostrar máximo 20 resultados
        max_display = min(20, num_results)
        for i, r in enumerate(results[:max_display], 1):
            institution = r.get('host_institution', 'N/A')
            country = r.get('destination_country', 'N/A')
            program = r.get('mobility_program', 'N/A')

            response_parts.append(f"**{i}.** 🏛️ {institution}")
            response_parts.append(f"   🌍 {country} | 📋 {program}")
            response_parts.append("")

        if num_results > max_display:
            remaining = num_results - max_display
            response_parts.append(f"*... y {remaining} convenio(s) más*")
            response_parts.append(f'💡 *"Muéstrame los siguientes 20" | "Muestra también el centro" | "Ordena por país"*')
        else:
            response_parts.append("---")
            response_parts.append('💡 *"Muestra también el centro" | "Ordena por país"*')

        return "\n".join(response_parts)

    def _is_detail_request(self, question: str) -> tuple:
        """
        Detecta si el usuario pide detalles de un acuerdo específico.
        Retorna (True, número) si detecta, (False, None) si no.
        """
        import re
        question_lower = question.lower().strip()

        # Patrones: "amplía el 3", "detalles del 2", "más info del 1", "el número 5"
        # IMPORTANTE: Excluir ordinales como "1er", "2do", "3ro" para no confundir "del 2do cuatrimestre"
        detail_patterns = [
            r"ampl[ií]a.*?(\d+)",
            r"detalle[s]?.*?(\d+)",
            r"m[aá]s info.*?(\d+)",
            r"info(?:rmaci[oó]n)?.*?(\d+)",
            r"(?:el|del|número|numero)\s*(\d+)(?!(?:er|do|ro|to|º))",  # Excluir ordinales
            r"acuerdo\s*(?:número|numero)?\s*(\d+)",
            r"convenio\s*(?:número|numero)?\s*(\d+)",
            r"^(\d+)$",  # Solo el número
        ]

        for pattern in detail_patterns:
            match = re.search(pattern, question_lower)
            if match:
                num = int(match.group(1))
                return (True, num)

        return (False, None)

    def _show_agreement_details(self, session_id: str, index: int) -> str:
        """Muestra información detallada de un acuerdo específico."""
        state = self._get_session_state(session_id)

        if not state['last_results']:
            return "⚠️ No hay resultados previos. Haz primero una consulta."

        # Si los resultados estaban agrupados, no se puede ampliar por número
        if state['last_results_grouped']:
            return ("⚠️ Los resultados están agrupados y no se pueden ampliar por número.\n\n"
                    "💡 Para ver detalles, refina la búsqueda indicando el grupo que te interesa.\n"
                    "Por ejemplo: *\"muéstrame los de Alemania\"* o *\"los de la Universidad de Berlín\"*")

        if index < 1 or index > len(state['last_results']):
            return f"⚠️ Número inválido. Elige un número entre 1 y {len(state['last_results'])}."

        r = state['last_results'][index - 1]

        # Detectar si es una consulta de campos específicos (no tiene host_institution)
        if 'host_institution' not in r:
            # Mostrar solo los campos disponibles
            response_parts = [f"📋 **Detalle #{index}**\n"]
            field_labels = {
                'uma_faculties': '🏫 Facultad UMA',
                'destination_country': '🌍 País',
                'host_institution': '🏛️ Universidad',
                'mobility_program': '📄 Programa',
                'destination_faculty': '🎯 Facultad de destino',
                'uma_degrees': '📚 Titulaciones',
                'language_requirements': '🗣️ Idioma',
            }
            for field, value in r.items():
                if value:
                    label = field_labels.get(field, field.replace('_', ' ').title())
                    response_parts.append(f"**{label}:** {value}")
            response_parts.append("")
            response_parts.append("ℹ️ *Para ver convenios completos, haz una búsqueda más específica.*")
            return "\n".join(response_parts)

        response_parts = [f"📋 **Detalles del acuerdo #{index}**\n"]

        # Información principal
        response_parts.append(f"### 🏛️ {r.get('host_institution', 'N/A')}")
        response_parts.append(f"**País:** {r.get('destination_country', 'N/A')}")
        response_parts.append(f"**Programa:** {r.get('mobility_program', 'N/A')}")
        response_parts.append("")

        # Vigencia
        start = r.get('start_date', '')
        end = r.get('end_date', '')
        if start or end:
            response_parts.append(f"**📅 Vigencia:** {start} → {end}")

        # Plazas
        vacancies = r.get('student_vacancies', '')
        if vacancies:
            response_parts.append(f"**🎓 Plazas:** {vacancies}")

        # Requisitos de idioma
        lang = r.get('language_requirements', '')
        if lang:
            response_parts.append(f"**🗣️ Idioma:** {lang}")

        # Facultades UMA
        uma_fac = r.get('uma_faculties', '')
        if uma_fac:
            response_parts.append(f"**🏫 Facultades UMA:** {uma_fac}")

        # Titulaciones UMA
        uma_deg = r.get('uma_degrees', '')
        if uma_deg:
            response_parts.append(f"**📚 Titulaciones:** {uma_deg}")

        # Facultad destino
        dest_fac = r.get('destination_faculty', '')
        if dest_fac and dest_fac != 'General/No especificada':
            response_parts.append(f"**🎯 Facultad destino:** {dest_fac}")

        # Códigos ISCED
        isced = r.get('isced_codes', '')
        if isced:
            response_parts.append(f"**📊 Áreas (ISCED):** {isced}")

        # Niveles disponibles
        levels = r.get('available_levels', '')
        if levels:
            response_parts.append(f"**📈 Niveles:** {levels}")

        # Tutores
        tutors = r.get('tutors', '')
        if tutors:
            # Simplificar lista de tutores (puede ser muy larga)
            tutor_list = tutors.split('|')
            unique_tutors = list(set(t.strip() for t in tutor_list if t.strip()))[:3]
            response_parts.append(f"**👤 Coordinador(es):** {', '.join(unique_tutors)}")

        # Requisitos académicos
        acad_req = r.get('academic_requirements_text', '')
        if acad_req:
            response_parts.append(f"\n**📝 Requisitos académicos:**")
            response_parts.append(f"_{acad_req[:500]}{'...' if len(acad_req) > 500 else ''}_")

        # Comentarios públicos
        comments = r.get('public_comments', '')
        if comments:
            response_parts.append(f"\n**💬 Notas:**")
            response_parts.append(f"_{comments[:500]}{'...' if len(comments) > 500 else ''}_")

        return "\n".join(response_parts)

    def _handle_show_more(self, session_id: str, question: str) -> str:
        """Muestra más resultados de la última consulta."""
        state = self._get_session_state(session_id)

        if not state['last_results']:
            return "⚠️ No hay resultados previos. Haz primero una consulta."

        question_lower = question.lower()
        total = len(state['last_results'])

        # Detectar si quiere ver todos
        if "todos" in question_lower or "completa" in question_lower:
            # Mostrar TODOS los resultados desde el principio
            state['last_display_offset'] = total
            return self._format_results_basic(state['last_results'], max_display=total)

        # Detectar número específico (ej: "siguientes 30")
        import re
        num_match = re.search(r'(\d+)', question)
        page_size = int(num_match.group(1)) if num_match else self.default_page_size

        # Calcular siguiente página
        start = state['last_display_offset']
        end = min(start + page_size, total)

        if start >= total:
            return f"✅ Ya se han mostrado todos los {total} resultados."

        # Obtener siguiente página
        next_page = state['last_results'][start:end]
        state['last_display_offset'] = end

        remaining = total - end
        response_parts = [f"📄 **Mostrando resultados {start + 1} a {end} de {total}**\n"]

        for i, r in enumerate(next_page, start + 1):
            response_parts.append(f"### {i}. {r.get('host_institution', 'N/A')}")
            response_parts.append(f"- **País:** {r.get('destination_country', 'N/A')}")
            response_parts.append(f"- **Programa:** {r.get('mobility_program', 'N/A')}")
            response_parts.append(f"- **Plazas:** {r.get('student_vacancies', 'N/A')}")
            response_parts.append(f"- **Idioma:** {r.get('language_requirements', 'N/A')}")
            response_parts.append("")

        if remaining > 0:
            response_parts.append(f"*... quedan {remaining} convenio(s) más*")
            response_parts.append(f'💡 *"Muéstrame más" | "Muestra también el centro" | "Ordena por país"*')

        return "\n".join(response_parts)

    def _is_refinement_query(self, session_id: str, question: str) -> bool:
        """
        Detecta si la pregunta es un refinamiento de la consulta anterior.
        Ejemplo: "los de INGLÉS B2", "muéstrame solo los de Francia", "de esos, los del primer cuatrimestre"
        """
        state = self._get_session_state(session_id)
        if not state['last_sql_query']:
            return False

        question_lower = question.lower().strip()

        # Patrones que indican refinamiento (con y sin acentos)
        refinement_patterns = [
            # Referencias a resultados previos
            "de esos", "de estos", "de ellos", "de esas",
            "los de ", "las de ", "solo los", "solo las", "solo ",
            # Con acentos
            "muéstrame los", "muéstrame las", "muéstrame solo", "muéstrame ",
            "cuáles de ", "cuántos de ",
            # Sin acentos (variantes comunes)
            "muestrame los", "muestrame las", "muestrame solo", "muestrame ",
            "cuales de ", "cuantos de ",
            # Imperativo directo (muestra, dame, enseña)
            "muestra el", "muestra los", "muestra las", "muestra la",
            "dame el", "dame los", "dame las", "dame la",
            "enseña el", "enseña los", "enseña las", "enseña la",
            "enséñame el", "enséñame los", "enséñame las", "enséñame la",
            "ensename el", "ensename los", "ensename las", "ensename la",
            # Confirmación + refinamiento
            "sí,", "si,", "sí ", "si ",
            # Filtros
            "filtra por", "filtrar por", "filtra los", "filtrar los",
            "de los anteriores", "de las anteriores",
            "los que ", "las que ", "aquellos que", "aquellas que",
            # Añadir/cambiar condición
            "pero solo", "pero que", "y que además", "y que ademas", "que también", "que tambien",
            "con requisito", "sin requisito",
            # Cuatrimestres y plazas
            "primer cuatrimestre", "segundo cuatrimestre", "1er cuatrimestre", "2do cuatrimestre",
            "anual", "anuales",
        ]

        for pattern in refinement_patterns:
            if pattern in question_lower:
                return True

        return False

    def _preprocess_level_substitution(self, question: str, previous_sql: str) -> str:
        """
        Pre-procesa el SQL anterior para sustituir niveles de idioma si el usuario
        está pidiendo un nivel diferente al existente.

        Esto es necesario porque las LLMs no siguen bien las instrucciones de sustituir
        niveles (B1→B2) y tienden a mantener el nivel anterior.

        Args:
            question: La pregunta del usuario
            previous_sql: El SQL de la consulta anterior

        Returns:
            El SQL modificado con el nivel sustituido, o el original si no aplica
        """
        import re

        if not previous_sql:
            return previous_sql

        question_upper = question.upper()
        sql_upper = previous_sql.upper()

        # Niveles de idioma ordenados (más comunes primero)
        niveles = ["B1", "B2", "A1", "A2", "C1", "C2"]

        # 1. Detectar si el usuario está pidiendo un nivel específico
        nivel_pedido = None
        for nivel in niveles:
            # Buscar patrones como "nivel B2", "B2", "los de B2", "inglés B2"
            if re.search(rf'\b{nivel}\b', question_upper):
                nivel_pedido = nivel
                break

        if not nivel_pedido:
            return previous_sql

        # 2. Detectar si el SQL anterior tiene un nivel diferente
        nivel_anterior = None
        for nivel in niveles:
            if f"'%{nivel}%'" in sql_upper or f'"%{nivel}%"' in sql_upper:
                nivel_anterior = nivel
                break

        if not nivel_anterior or nivel_anterior == nivel_pedido:
            return previous_sql

        # 3. Sustituir el nivel en el SQL
        # Patrones a buscar y reemplazar (case insensitive)
        patrones_nivel = [
            (rf"'%{nivel_anterior}%'", f"'%{nivel_pedido}%'"),
            (rf'"%{nivel_anterior}%"', f'"%{nivel_pedido}%"'),
        ]

        sql_modificado = previous_sql
        for patron, reemplazo in patrones_nivel:
            sql_modificado = re.sub(patron, reemplazo, sql_modificado, flags=re.IGNORECASE)

        if sql_modificado != previous_sql:
            logger.info(f"🔄 Pre-procesamiento: Nivel {nivel_anterior}→{nivel_pedido} en SQL")
            logger.debug(f"   SQL original: {previous_sql}")
            logger.debug(f"   SQL modificado: {sql_modificado}")

        return sql_modificado

    def _init_local_client(self):
        """Inicializa un cliente Ollama local para formatear resultados."""
        try:
            import ollama
            # Prioriza LOCAL_LLM_BASE_URL, luego OLLAMA_BASE_URL
            base_url = os.getenv("LOCAL_LLM_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
            logger.info(f"🏠 Conectando a LLM local en {base_url}...")
            return ollama.Client(host=base_url)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo inicializar cliente local Ollama: {e}")
            return None

    def _get_model(self) -> str:
        """Obtiene el modelo según el proveedor configurado."""
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
        elif provider == "vllm":
            return os.getenv("VLLM_MODEL", "mistral-large-latest")
        elif provider == "mistral":
            return os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        return "qwen2.5-coder:14b"

    def _get_db_schema(self) -> str:
        """
        Obtiene el esquema de la base de datos en formato COMPACTO para el LLM.
        Genera un esquema simplificado desde la BD directamente para evitar confundir al modelo.
        """
        # Usar cache si está disponible
        if self._cached_schema:
            return self._cached_schema

        if not os.path.exists(self.db_path):
            return "ERROR: Base de datos no encontrada en data/database.db"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = cursor.fetchall()

            if not tables:
                conn.close()
                return "La base de datos está vacía (no hay tablas)."

            schema_parts = ["ESQUEMA DE LA BASE DE DATOS:"]
            schema_parts.append("Base de datos de acuerdos de movilidad para estudiantes de la Universidad de Málaga.")
            schema_parts.append("")

            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = [col[1] for col in cursor.fetchall()]
                schema_parts.append(f"Tabla: {table_name}")
                schema_parts.append(f"Columnas: {', '.join(columns)}")
                schema_parts.append("")

                # Añadir descripciones clave para columnas importantes
                if table_name == "destinations":
                    schema_parts.append("Columnas importantes:")
                    schema_parts.append("- host_institution: nombre de la universidad de destino")
                    schema_parts.append("- destination_country: país del destino")
                    schema_parts.append("- mobility_program: programa completo (ej: 'ERASMUS+ KA131', 'ERASMUS+ KA171', 'MOVILIDAD INTERNACIONAL UMA')")
                    schema_parts.append("- uma_faculties: facultades UMA que pueden aplicar")
                    schema_parts.append("- uma_degrees: titulaciones UMA permitidas")
                    schema_parts.append("- language_requirements: requisitos de idioma")
                    schema_parts.append("- student_vacancies: plazas disponibles")

            conn.close()
            self._cached_schema = "\n".join(schema_parts)
            logger.info("📄 Esquema compacto generado desde la BD (cacheado)")
            return self._cached_schema

        except sqlite3.Error as e:
            return f"Error leyendo esquema: {str(e)}"

    def _text_to_sql(self, user_question: str, schema: str, previous_sql: str = None) -> str:
        """Usa Ollama con qwen2.5-coder para convertir preguntas a SQL."""
        # Normalizar países y otros términos antes de procesar
        normalized_question = normalize_text_for_search(user_question)
        if normalized_question != user_question:
            logger.info(f"🌍 Pregunta normalizada: '{user_question}' → '{normalized_question}'")

        # Detectar si es un refinamiento
        is_refinement = previous_sql is not None
        if is_refinement:
            logger.info(f"🔍 Detectado refinamiento. SQL anterior: {previous_sql[:80]}...")
            # Pre-procesar sustitución de niveles (B1→B2, etc.) antes de enviar a la LLM
            previous_sql = self._preprocess_level_substitution(user_question, previous_sql)

        logger.info(f"🔄 Convirtiendo pregunta a SQL con {self.sql_model}: {normalized_question[:50]}...")

        # Prompt simplificado - pide solo el SQL en bloque markdown
        conversion_prompt = f"""Eres un experto en SQL. Convierte la siguiente pregunta a una consulta SQL para SQLite.

BASE DE DATOS (convenios de movilidad universitaria):
- Tabla: destinations
- Columnas:
  * host_institution: nombre de la UNIVERSIDAD DE DESTINO (ej: "The Hague University", "Sorbonne")
  * destination_country: PAÍS de destino (ej: "Francia", "Alemania")
  * mobility_program: nombre COMPLETO del programa (ej: "ERASMUS+ KA131", "ERASMUS+ KA171", "MOVILIDAD INTERNACIONAL UMA", "ISEP")
  * uma_faculties: facultades de la UMA que participan
  * uma_degrees: titulaciones de la UMA permitidas
  * language_requirements: requisitos de idioma
  * student_vacancies: plazas disponibles

REGLAS:
- Usa LIKE '%texto%' para búsquedas de texto (no =)
- Solo genera SELECT (nunca INSERT, UPDATE, DELETE)
- COUNT(*) solo para contar CONVENIOS/ACUERDOS ("cuántos convenios", "número de acuerdos")
- PLAZAS y CUATRIMESTRES: student_vacancies es TEXTO con formato "[Grado] Plazas: 4, Periodos permitidos: 1er CUATRIMESTRE"
  * Para filtrar por cuatrimestre: WHERE student_vacancies LIKE '%1er CUATRIMESTRE%' o '%2do CUATRIMESTRE%' o '%ANUAL%'
  * NO uses SUM() con student_vacancies (es texto). Usa COUNT(*) para contar destinos o SELECT student_vacancies para ver detalles
- REQUISITOS DE IDIOMA: language_requirements tiene formato "IDIOMA (Nivel: X) -> Detalles"
  * Ejemplo de valor: "INGLÉS (Nivel: B2) -> Certificado Obligatorio..."
  * Sin requisito de idioma: WHERE language_requirements = 'No requiere acreditación de idioma'
  * IMPORTANTE: Para buscar "Inglés B1" usa DOS condiciones separadas:
    WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%'
  * NUNCA uses '%INGLÉS B1%' porque el formato real es 'INGLÉS (Nivel: B1)'
- Si pregunta "qué...", "cuáles...", "muéstrame...", "hay...", "universidades...", "facultades..." → usa SELECT * (NO COUNT, NO columnas específicas)
- SIEMPRE usa SELECT * excepto para:
  * COUNT(*) para contar convenios/acuerdos
  * SELECT DISTINCT columna SOLO cuando pide LISTAR valores únicos de UNA columna (ej: "¿Qué países hay?", "¿Qué programas existen?")
  * SELECT columna_específica SOLO para preguntas MUY concretas como "qué idioma necesito para X"
- IMPORTANTE: "¿Qué facultades tienen convenios con X?" → SELECT * (NO SELECT DISTINCT, necesitamos TODOS los datos incluyendo plazas e idiomas)
- Busca universidades en host_institution, NO en uma_faculties
- IMPORTANTE: Busca PAÍSES en destination_country (ej: Alemania, Francia, Italia, España)
- Los nombres de países NUNCA van en host_institution (que solo tiene nombres de universidades)
- REGIONES GEOGRÁFICAS: Para "Europa", "Asia", "África", "América Latina", "Oceanía" usa destination_country LIKE '%NombreRegion%' (el sistema lo expandirá a los países de esa región)
- REDES DE UNIVERSIDADES: Para "UNINOVIS" usa host_institution LIKE '%UNINOVIS%' (el sistema lo expandirá a las universidades de la red)
- INTERPRETACIÓN SEMÁNTICA IMPORTANTE:
  * "¿Qué nivel de INGLÉS necesito para X?" → FILTRAR por language_requirements LIKE '%INGLÉS%' (devolver solo los que piden inglés)
  * "¿Hay destinos con SOLO B1?" o "requiera solo B1" → EXCLUIR niveles superiores: AND language_requirements NOT LIKE '%B2%'
  * "plazas disponibles" o "destinos con plazas" → EXCLUIR plazas vacías: WHERE student_vacancies NOT LIKE '%Plazas: 0%'
  * "¿Con qué PAÍSES tiene convenios X?" → usar SELECT DISTINCT destination_country para evitar duplicados

EJEMPLOS:
- "¿Qué acuerdos hay con The Hague University of Applied Sciences?" → SELECT * FROM destinations WHERE host_institution LIKE '%The Hague%'
- "¿Cuántos acuerdos hay con Alemania?" → SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Alemania%'
- "¿Hay convenios con Italia?" → SELECT * FROM destinations WHERE destination_country LIKE '%Italia%'
- "¿Qué nivel de inglés necesito para ir a Alemania?" → SELECT language_requirements FROM destinations WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%'
- "¿Qué universidades hay en Francia?" → SELECT * FROM destinations WHERE destination_country LIKE '%Francia%'
- "¿Qué destinos hay con ERASMUS+ KA131?" → SELECT * FROM destinations WHERE mobility_program LIKE '%ERASMUS+ KA131%'
- "¿Qué programas de movilidad hay?" → SELECT DISTINCT mobility_program FROM destinations
- "¿Cuántas plazas hay para el primer cuatrimestre?" → SELECT COUNT(*) FROM destinations WHERE student_vacancies LIKE '%1er CUATRIMESTRE%'
- "¿Qué destinos hay para el segundo cuatrimestre?" → SELECT * FROM destinations WHERE student_vacancies LIKE '%2do CUATRIMESTRE%'
- "¿Qué plazas hay en Italia?" → SELECT * FROM destinations WHERE destination_country LIKE '%Italia%'
- "¿Qué destinos no requieren idioma?" → SELECT * FROM destinations WHERE language_requirements = 'No requiere acreditación de idioma'
- "¿Qué destinos requieren inglés B2?" → SELECT * FROM destinations WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B2%'
- "¿Hay convenios con requisito de Inglés B1?" → SELECT * FROM destinations WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%'
- "¿Cuántos destinos hay en América Latina?" → SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%América Latina%'
- "¿Qué universidades hay en Europa?" → SELECT * FROM destinations WHERE destination_country LIKE '%Europa%'
- "¿Cuántos convenios hay en Asia?" → SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Asia%'
- "¿Hay destinos donde se requiera SOLO B1 de inglés?" → SELECT * FROM destinations WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%' AND language_requirements NOT LIKE '%B2%'
- "¿Qué destinos tienen plazas disponibles?" → SELECT * FROM destinations WHERE student_vacancies NOT LIKE '%Plazas: 0%'
- "¿Con qué países tiene convenios la Facultad de Medicina?" → SELECT DISTINCT destination_country FROM destinations WHERE uma_faculties LIKE '%Medicina%'
- "¿Qué facultades tienen convenios con universidades de Africa?" → SELECT * FROM destinations WHERE destination_country LIKE '%Africa%'
- "¿Qué facultades tienen acuerdos con Alemania?" → SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%'

PREGUNTA: {normalized_question}

Responde SOLO con la consulta SQL dentro de un bloque ```sql
"""

        # Si es un refinamiento, añadir contexto de la consulta anterior
        if is_refinement:
            refinement_context = f"""

⚠️ CONTEXTO DE REFINAMIENTO - MUY IMPORTANTE:
El usuario está REFINANDO una consulta anterior. DEBES CONSERVAR TODAS las condiciones existentes y añadir las nuevas.

CONSULTA ANTERIOR (COPIA TODAS LAS CONDICIONES):
```sql
{previous_sql}
```

🚨 REGLA CRÍTICA - NUNCA PIERDAS CONDICIONES:
- COPIA PRIMERO todas las condiciones de la consulta anterior
- LUEGO añade o modifica según lo que pide el usuario
- Si la consulta anterior tiene "destination_country LIKE '%Alemania%'", tu nueva consulta DEBE TENERLO también (a menos que el usuario pida otro país)

REGLAS OBLIGATORIAS:
1. COPIA TODAS las condiciones de la consulta anterior EXCEPTO la que se modifica explícitamente
2. SUSTITUYE solo el valor específico que el usuario quiere cambiar
3. CONSERVA SIEMPRE: destination_country, host_institution, uma_faculties, y otras condiciones no mencionadas

CUÁNDO AÑADIR (conservar TODO lo anterior + nuevo filtro):
- "los que requieran inglés" → AÑADIR language_requirements, CONSERVAR destination_country
- "solo nivel B1" → AÑADIR B1, CONSERVAR destination_country e INGLÉS
- "del primer cuatrimestre" → AÑADIR student_vacancies, CONSERVAR TODO lo anterior

CUÁNDO SUSTITUIR (mantener el resto):
- País/Región: "los de Asia" → sustituir destination_country, CONSERVAR language_requirements
- Nivel: "los de B2" → sustituir el nivel (B1→B2), CONSERVAR destination_country e INGLÉS
- Universidad: "los de Sorbonne" → sustituir host_institution, CONSERVAR todo lo demás

IMPORTANTE - PAÍSES Y REGIONES:
- REGIONES PRINCIPALES: Europa, Asia, América Latina, Latinoamérica, África, Oceanía
- SUBREGIONES: países escandinavos, países nórdicos, Europa del Este, países de habla alemana, países de habla inglesa, países mediterráneos, Benelux
- Si el usuario pide una REGIÓN o PAÍS diferente al actual → SUSTITUYE destination_country
- Ejemplo: SQL anterior con "Alemania", usuario dice "los de Asia" → destination_country LIKE '%Asia%'
- Ejemplo: SQL anterior con "Italia", usuario dice "los de Francia" → destination_country LIKE '%Francia%'
- Para regiones usa LIKE y el sistema las expandirá: destination_country LIKE '%países escandinavos%'

IMPORTANTE PARA IDIOMAS Y NIVELES:
- NIVELES: A1, A2, B1, B2, C1, C2
- Si ya hay un NIVEL (B1) y el usuario pide OTRO NIVEL (B2) → SUSTITUIR el nivel
- Si ya hay "LIKE '%INGLÉS%'" y el usuario pide "nivel B1" (sin nivel previo) → AÑADIR B1
- Si ya hay "LIKE '%B1%'" y el usuario pide "nivel B2" → SUSTITUIR B1 por B2
- Ejemplo: B1 existente + usuario pide B2 → quitar '%B1%' y poner '%B2%'

EJEMPLOS CORRECTOS:

🔴 CASO CRÍTICO - AÑADIR IDIOMA CONSERVANDO PAÍS:
- Anterior: "WHERE destination_country LIKE '%Alemania%'"
  Usuario: "los que requieran inglés" → AÑADIR idioma, CONSERVAR país:
  WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%'
  ❌ INCORRECTO: WHERE language_requirements LIKE '%INGLÉS%' (perdió Alemania!)

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%'"
  Usuario: "solo nivel B1" → AÑADIR B1, CONSERVAR Alemania e INGLÉS:
  WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%'
  ❌ INCORRECTO: WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%' (perdió Alemania!)

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%'"
  Usuario: "los de Asia" → SUSTITUIR país por región:
  WHERE destination_country LIKE '%Asia%' AND language_requirements LIKE '%INGLÉS%'

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%'"
  Usuario: "solo los de nivel B1" → AÑADIR B1 (no había nivel):
  WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%'

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%'"
  Usuario: "los de nivel B2" → SUSTITUIR solo B1→B2, CONSERVAR Alemania e INGLÉS:
  WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B2%'

- Anterior: "WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B1%' AND destination_country LIKE '%Alemania%'"
  Usuario: "muestra los de inglés B2" → SUSTITUIR solo B1→B2, CONSERVAR Alemania:
  WHERE language_requirements LIKE '%INGLÉS%' AND language_requirements LIKE '%B2%' AND destination_country LIKE '%Alemania%'

- Anterior: "WHERE language_requirements LIKE '%INGLÉS%' AND destination_country LIKE '%Alemania%'"
  Usuario: "los de TECHNISCHE UNIVERSITÄT" → AÑADIR universidad:
  WHERE language_requirements LIKE '%INGLÉS%' AND destination_country LIKE '%Alemania%' AND host_institution LIKE '%TECHNISCHE UNIVERSITÄT%'

- Anterior: "WHERE destination_country LIKE '%Italia%'"
  Usuario: "mejor los de Turquía" → SUSTITUIR país:
  WHERE destination_country LIKE '%Turquía%'

- Anterior: "WHERE language_requirements LIKE '%B1%'"
  Usuario: "los de Alemania" → AÑADIR país (no había filtro de país):
  WHERE language_requirements LIKE '%B1%' AND destination_country LIKE '%Alemania%'

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%'"
  Usuario: "solo primer cuatrimestre" → AÑADIR cuatrimestre:
  WHERE destination_country LIKE '%Alemania%' AND language_requirements LIKE '%INGLÉS%' AND student_vacancies LIKE '%1er CUATRIMESTRE%'

🔴 MÁS EJEMPLOS DE AÑADIR (NUNCA PERDER CONDICIONES):
- Anterior: "WHERE destination_country LIKE '%Italia%'"
  Usuario: "que requieran francés" → AÑADIR idioma:
  WHERE destination_country LIKE '%Italia%' AND language_requirements LIKE '%FRANCÉS%'

- Anterior: "WHERE uma_faculties LIKE '%Medicina%'"
  Usuario: "en Europa" → AÑADIR región:
  WHERE uma_faculties LIKE '%Medicina%' AND destination_country LIKE '%Europa%'

- Anterior: "WHERE uma_faculties LIKE '%Medicina%'"
  Usuario: "muestra el de Estados Unidos" o "los de Estados Unidos" → AÑADIR país:
  WHERE uma_faculties LIKE '%Medicina%' AND destination_country LIKE '%Estados Unidos%'
  ❌ INCORRECTO: WHERE destination_country LIKE '%Estados Unidos%' (perdió Medicina!)

- Anterior: "WHERE destination_country LIKE '%Francia%'"
  Usuario: "de la Facultad de Derecho" → AÑADIR facultad:
  WHERE destination_country LIKE '%Francia%' AND uma_faculties LIKE '%Derecho%'

"""
            conversion_prompt = conversion_prompt.replace("PREGUNTA:", refinement_context + "PREGUNTA:")

        messages = [{"role": "user", "content": conversion_prompt}]

        # Determinar qué cliente usar según LLM_PROVIDER
        provider = os.getenv("LLM_PROVIDER", "ollama").lower()

        if provider == "mistral":
            # Usar Mistral Cloud API
            try:
                mistral_model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
                logger.info(f"☁️ Usando Mistral Cloud ({mistral_model})...")
                response = self.client.chat.complete(
                    model=mistral_model,
                    messages=messages
                )
                full_response = response.choices[0].message.content.strip()
                logger.debug(f"📝 Respuesta CoT completa:\n{full_response}")
            except Exception as e:
                logger.error(f"❌ Error con Mistral Cloud: {e}")
                raise RuntimeError(f"Error generando SQL con Mistral Cloud: {e}")
        elif self.local_client:
            # Usar cliente local (Ollama)
            try:
                logger.info(f"🏠 Usando Ollama ({self.sql_model})...")
                response = self.local_client.chat(
                    model=self.sql_model,
                    messages=messages
                )
                full_response = response["message"]["content"].strip()
                logger.debug(f"📝 Respuesta CoT completa:\n{full_response}")
            except Exception as e:
                logger.error(f"❌ Error con Ollama: {e}")
                raise RuntimeError(f"Error generando SQL con Ollama: {e}")
        else:
            raise RuntimeError("Cliente LLM no disponible. Configura Ollama o Mistral Cloud.")

        # Extraer SQL de la respuesta CoT
        sql = self._extract_sql_from_cot(full_response)

        # Limpiar comentarios SQL que el LLM pueda haber generado
        sql = self._clean_sql_comments(sql)

        # Limpiar basura común del LLM
        sql = self._clean_sql_garbage(sql)

        # Convertir = a LIKE para búsquedas de texto más flexibles
        sql = self._fix_sql_equality_to_like(sql)

        # Expandir regiones geográficas (Europa, Asia, América Latina)
        sql = self._expand_regions_in_sql(sql)

        # Añadir campos de contexto si el SELECT tiene pocos campos
        sql = self._add_context_fields_to_sql(sql)

        logger.info(f"📝 SQL generado: {sql}")
        return sql

    def _extract_sql_from_cot(self, response: str) -> str:
        """Extrae la consulta SQL de una respuesta Chain-of-Thought."""
        import re

        # Buscar SQL en bloque de código markdown
        code_block = re.search(r'```(?:sql)?\s*(SELECT.*?)```', response, re.DOTALL | re.IGNORECASE)
        if code_block:
            return code_block.group(1).strip()

        # Buscar línea que empiece con SELECT
        select_match = re.search(r'(SELECT\s+.+?)(?:\n\n|\Z)', response, re.DOTALL | re.IGNORECASE)
        if select_match:
            sql = select_match.group(1).strip()
            # Tomar solo hasta el primer ; si hay múltiples sentencias
            if ';' in sql:
                sql = sql.split(';')[0].strip()
            return sql

        # Buscar después de "SQL:" o "Consulta:"
        labeled_match = re.search(r'(?:SQL|Consulta|Query):\s*(SELECT.+?)(?:\n\n|\Z)', response, re.DOTALL | re.IGNORECASE)
        if labeled_match:
            return labeled_match.group(1).strip()

        # Fallback: buscar cualquier SELECT
        any_select = re.search(r'(SELECT\s+[^;]+)', response, re.IGNORECASE)
        if any_select:
            return any_select.group(1).strip()

        logger.warning("⚠️ No se pudo extraer SQL del razonamiento")
        return "ERROR: No se pudo generar SQL válido"

    def _clean_sql_comments(self, query: str) -> str:
        """
        Elimina comentarios SQL de la consulta para evitar falsos positivos de seguridad.
        Elimina comentarios de línea (--) y comentarios de bloque (/* */).
        """
        import re
        # Eliminar comentarios de bloque /* ... */
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        # Eliminar comentarios de línea -- ...
        query = re.sub(r'--.*?(?:\n|$)', ' ', query)
        # Limpiar espacios múltiples
        query = re.sub(r'\s+', ' ', query).strip()
        return query

    def _clean_sql_garbage(self, query: str) -> str:
        """
        Limpia basura común que generan los LLMs en las consultas SQL.
        """
        import re

        # Tomar solo la primera sentencia SQL (hasta el primer ;)
        if ';' in query:
            query = query.split(';')[0].strip()

        # Eliminar patrones de basura comunes
        # AND/OR sin columna antes
        query = re.sub(r'\s+AND\s+LIKE\s+', ' AND host_institution LIKE ', query)
        query = re.sub(r'\s+AND\s+NOT\s+LIKE\s+[\'"].*?[\'"]', '', query)

        # Eliminar texto después de patrones rotos
        query = re.sub(r"['\"]\s*%texto%\s*['\"].*$", "'%'", query)
        query = re.sub(r"\s*;\s*['\"].*$", "", query)

        # Limpiar espacios múltiples
        query = re.sub(r'\s+', ' ', query).strip()

        return query

    def _fix_sql_equality_to_like(self, query: str) -> str:
        """
        Convierte condiciones de igualdad exacta a LIKE para búsquedas de texto más flexibles.
        Ejemplo: host_institution = 'The Hague' -> host_institution LIKE '%The Hague%'
        """
        import re
        # Columnas de texto donde preferimos LIKE sobre =
        text_columns = ['host_institution', 'destination_country', 'mobility_program',
                        'uma_faculties', 'uma_degrees', 'destination_faculty']

        for col in text_columns:
            # Patrón: columna = 'valor' o columna = "valor"
            pattern = rf"({col})\s*=\s*['\"]([^'\"]+)['\"]"
            replacement = rf"\1 LIKE '%\2%'"
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

        return query

    def _expand_regions_in_sql(self, query: str) -> str:
        """
        Expande regiones geográficas en el SQL.
        Convierte: destination_country LIKE '%Europa%'
        A: destination_country IN ('Alemania', 'Francia', ...)
        """
        import re

        # Definir regiones y sus países (incluir variantes con/sin tilde)
        ASIA_COUNTRIES = ['Armenia', 'Corea del Sur', 'Filipinas', 'India', 'Indonesia', 'Japón', 'Kazajistán', 'Malasia', 'Nepal', 'Tailandia', 'Taiwán']
        LATAM_COUNTRIES = ['Argentina', 'Bolivia', 'Brasil', 'Chile', 'Colombia', 'Costa Rica', 'Ecuador', 'Honduras', 'México', 'Panamá', 'Paraguay', 'Perú', 'Puerto Rico', 'República Dominicana', 'Uruguay', 'Venezuela']
        EUROPE_COUNTRIES = ['Albania', 'Alemania', 'Austria', 'Bélgica', 'Bulgaria', 'República Checa', 'Croacia', 'Dinamarca', 'Eslovaquia', 'Eslovenia', 'España', 'Estonia', 'Finlandia', 'Francia', 'Georgia', 'Grecia', 'Hungría', 'Irlanda', 'Islandia', 'Italia', 'Letonia', 'Lituania', 'Malta', 'Moldavia', 'Noruega', 'Países Bajos', 'Polonia', 'Portugal', 'Reino Unido', 'República de Chipre', 'República de Macedonia', 'Rumanía', 'Serbia', 'Suecia', 'Suiza', 'Turquía', 'Ucrania']

        # Subregiones de Europa
        NORDIC_COUNTRIES = ['Dinamarca', 'Finlandia', 'Islandia', 'Noruega', 'Suecia']
        EASTERN_EUROPE = ['Bulgaria', 'Croacia', 'Eslovaquia', 'Eslovenia', 'Estonia', 'Hungría', 'Letonia', 'Lituania', 'Polonia', 'República Checa', 'Rumanía', 'Serbia', 'Ucrania']
        GERMAN_SPEAKING = ['Alemania', 'Austria', 'Suiza']
        ENGLISH_SPEAKING = ['Irlanda', 'Reino Unido', 'Estados Unidos', 'Canadá', 'Australia']
        MEDITERRANEAN = ['España', 'Francia', 'Italia', 'Grecia', 'Croacia', 'Eslovenia', 'Malta', 'República de Chipre', 'Turquía', 'Marruecos', 'Túnez', 'Argelia', 'Egipto']
        BENELUX = ['Bélgica', 'Países Bajos', 'Luxemburgo']
        AFRICA_COUNTRIES = ['Argelia', 'Egipto', 'Marruecos', 'Sudáfrica', 'Túnez', 'Senegal', 'Ghana', 'Kenia', 'Nigeria', 'Etiopía', 'Tanzania', 'Uganda', 'Mozambique', 'Cabo Verde']

        REGIONS = {
            'Europa': EUROPE_COUNTRIES,
            'Asia': ASIA_COUNTRIES,
            'Ásia': ASIA_COUNTRIES,  # Variante con tilde (Qwen a veces la usa)
            'América Latina': LATAM_COUNTRIES,
            'Latinoamérica': LATAM_COUNTRIES,
            'America Latina': LATAM_COUNTRIES,  # Sin tilde
            'Oceanía': ['Australia', 'Nueva Zelanda'],
            'Oceania': ['Australia', 'Nueva Zelanda'],  # Sin tilde
            'África': AFRICA_COUNTRIES,
            'Africa': AFRICA_COUNTRIES,  # Sin tilde
            # Subregiones
            'países escandinavos': NORDIC_COUNTRIES,
            'Países escandinavos': NORDIC_COUNTRIES,
            'países nórdicos': NORDIC_COUNTRIES,
            'Países nórdicos': NORDIC_COUNTRIES,
            'paises nordicos': NORDIC_COUNTRIES,  # Sin tildes
            'Europa del Este': EASTERN_EUROPE,
            'europa del este': EASTERN_EUROPE,
            'países de habla alemana': GERMAN_SPEAKING,
            'Países de habla alemana': GERMAN_SPEAKING,
            'países germanófonos': GERMAN_SPEAKING,
            'países de habla inglesa': ENGLISH_SPEAKING,
            'Países de habla inglesa': ENGLISH_SPEAKING,
            'países anglófonos': ENGLISH_SPEAKING,
            'países mediterráneos': MEDITERRANEAN,
            'Países mediterráneos': MEDITERRANEAN,
            'paises mediterraneos': MEDITERRANEAN,  # Sin tildes
            'Benelux': BENELUX,
            'benelux': BENELUX,
        }

        # Redes de universidades - cada entrada tiene patrones de búsqueda (nombre inglés, acrónimo, etc.)
        # Usar patrones específicos para evitar falsos positivos
        UNIVERSITY_NETWORKS = {
            'UNINOVIS': [
                ['Sorbonne Paris Nord', 'USPN'],                    # France
                ['Campania', 'Vanvitelli'],                         # Italy
                ['Kauno Kolegija'],                                 # Lithuania
                ['University of Tirana', 'UNIVERSITY OF TIRANA'],   # Albania (específico)
                ['Würzburg-Schweinfurt', 'THWS'],                   # Germany
                ['Tampere University of Applied', 'TAMK'],          # Finland (TAMK usa igualdad exacta)
                ['Hague University', 'THUAS'],                      # Netherlands
            ],
        }

        # Expandir redes de universidades usando OR con múltiples LIKE
        for network, universities in UNIVERSITY_NETWORKS.items():
            pattern = rf"host_institution\s+LIKE\s+['\"]%{network}%['\"]"
            if re.search(pattern, query, flags=re.IGNORECASE):
                # Construir condiciones OR para cada universidad
                conditions = []
                for uni_patterns in universities:
                    # Cada universidad puede tener múltiples patrones (nombre, acrónimo)
                    uni_conditions = []
                    for p in uni_patterns:
                        # Patrones cortos (<=4 chars) usan igualdad exacta para evitar falsos positivos
                        if len(p) <= 4:
                            uni_conditions.append(f"host_institution = '{p}'")
                        else:
                            uni_conditions.append(f"host_institution LIKE '%{p}%'")
                    conditions.append(f"({' OR '.join(uni_conditions)})")
                replacement = f"({' OR '.join(conditions)})"
                query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

        for region, countries in REGIONS.items():
            # Patrón: destination_country LIKE '%Region%'
            pattern = rf"destination_country\s+LIKE\s+['\"]%{region}%['\"]"
            countries_str = ", ".join(f"'{c}'" for c in countries)
            replacement = f"destination_country IN ({countries_str})"
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

        return query

    def _add_context_fields_to_sql(self, query: str) -> str:
        """
        Añade campos de contexto cuando el SELECT tiene pocos campos.
        Esto mejora la visualización de resultados.

        Ejemplo:
          SELECT host_institution FROM destinations WHERE...
        Se convierte en:
          SELECT host_institution, destination_country, mobility_program FROM destinations WHERE...
        """
        import re

        # No modificar si es COUNT, SELECT *, o DISTINCT con múltiples campos
        query_upper = query.upper().strip()
        if 'COUNT(' in query_upper or 'SELECT *' in query_upper:
            return query

        # Extraer la parte SELECT ... FROM
        match = re.match(r'(SELECT\s+)(DISTINCT\s+)?(.+?)(\s+FROM\s+)', query, re.IGNORECASE | re.DOTALL)
        if not match:
            return query

        select_keyword = match.group(1)
        distinct = match.group(2) or ''
        fields_part = match.group(3).strip()
        from_part = match.group(4)

        # Contar campos actuales (separados por coma)
        current_fields = [f.strip() for f in fields_part.split(',')]

        # Si ya tiene 3 o más campos, no modificar
        if len(current_fields) >= 3:
            return query

        # Campos de contexto a añadir según lo que ya está presente
        context_fields = {
            'host_institution': ['destination_country', 'mobility_program'],
            'destination_country': ['host_institution', 'mobility_program'],
            'mobility_program': ['host_institution', 'destination_country'],
            'language_requirements': ['host_institution', 'destination_country'],
            'student_vacancies': ['host_institution', 'destination_country'],
            'uma_faculties': ['destination_country', 'host_institution'],
            'uma_degrees': ['destination_country', 'host_institution'],
        }

        # Determinar qué campos añadir
        fields_to_add = []
        current_fields_lower = [f.lower() for f in current_fields]

        for field in current_fields:
            field_lower = field.lower()
            if field_lower in context_fields:
                for ctx_field in context_fields[field_lower]:
                    if ctx_field.lower() not in current_fields_lower and ctx_field not in fields_to_add:
                        fields_to_add.append(ctx_field)
                        if len(current_fields) + len(fields_to_add) >= 4:
                            break
            if len(current_fields) + len(fields_to_add) >= 4:
                break

        if not fields_to_add:
            return query

        # Reconstruir la consulta con los campos adicionales
        new_fields = current_fields + fields_to_add
        new_fields_str = ', '.join(new_fields)

        rest_of_query = query[match.end():]
        new_query = f"{select_keyword}{distinct}{new_fields_str}{from_part}{rest_of_query}"

        logger.debug(f"Campos de contexto añadidos: {fields_to_add}")
        return new_query

    def _execute_sql(self, query: str) -> tuple:
        """
        Ejecuta una consulta SQL y devuelve (éxito, resultado).
        resultado es una lista de diccionarios si éxito, o mensaje de error si falla.
        """
        logger.info(f"⚡ Ejecutando SQL...")

        # Limpiar comentarios SQL antes de validar (el LLM puede generarlos)
        query = self._clean_sql_comments(query)

        # Validación de seguridad básica
        query_upper = query.strip().upper()

        # Verificar si es un error del LLM
        if query_upper.startswith("ERROR:"):
            return (False, query)

        # Solo permitir SELECT
        if not query_upper.startswith("SELECT"):
            return (False, "Solo se permiten consultas SELECT.")

        # Palabras prohibidas
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC", "--"]
        for word in forbidden:
            if word in query_upper:
                return (False, f"Operación '{word}' no permitida por seguridad.")

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return (True, [])

            # Convertir a lista de diccionarios
            columns = rows[0].keys()
            results = [dict(row) for row in rows]

            logger.info(f"✅ Consulta exitosa: {len(results)} filas")
            return (True, results)

        except sqlite3.Error as e:
            logger.error(f"❌ Error SQL: {str(e)}")
            return (False, f"Error SQL: {str(e)}")

    def _is_why_question(self, question: str) -> bool:
        """Detecta si es una pregunta de tipo 'por qué'."""
        # Eliminar signos de interrogación y espacios
        question_clean = question.lower().strip().lstrip("¿").strip()
        why_patterns = [
            "por qué", "por que", "porque",
            "cuál es la razón", "cual es la razon",
            "a qué se debe", "a que se debe",
            "cómo es que", "como es que",
            "qué hace que", "que hace que",
        ]
        for pattern in why_patterns:
            if question_clean.startswith(pattern) or f" {pattern} " in question_clean:
                return True
        return False

    def _extract_search_context(self, sql_query: str) -> dict:
        """Extrae el contexto de búsqueda desde la consulta SQL."""
        import re
        context = {
            "pais": None,
            "idioma": None,
            "nivel": None,
            "facultad": None,
            "programa": None,
            "universidad": None,
            "plazas_disponibles": False,
        }

        sql_upper = sql_query.upper()

        # Extraer país
        match = re.search(r"DESTINATION_COUNTRY\s+LIKE\s+'%([^%]+)%'", sql_upper)
        if match:
            context["pais"] = match.group(1).title()

        # Extraer idioma (mantener en mayúsculas para coincidir con BD)
        idiomas = ["INGLÉS", "ALEMÁN", "FRANCÉS", "ITALIANO", "RUSO", "PORTUGUÉS", "CHINO", "JAPONÉS", "COREANO", "JAPONES"]
        for idioma in idiomas:
            if idioma in sql_upper:
                context["idioma"] = idioma  # Mantener mayúsculas
                break

        # Extraer nivel
        niveles = ["A1", "A2", "B1", "B2", "C1", "C2"]
        for nivel in niveles:
            if nivel in sql_upper:
                context["nivel"] = nivel
                break

        # Extraer facultad
        match = re.search(r"UMA_FACULTIES\s+LIKE\s+'%([^%]+)%'", sql_upper)
        if match:
            context["facultad"] = match.group(1).title()

        # Extraer programa
        match = re.search(r"MOBILITY_PROGRAM\s+LIKE\s+'%([^%]+)%'", sql_upper)
        if match:
            context["programa"] = match.group(1)

        # Extraer universidad
        match = re.search(r"HOST_INSTITUTION\s+LIKE\s+'%([^%]+)%'", sql_upper)
        if match:
            context["universidad"] = match.group(1).title()

        # Detectar filtro de plazas disponibles
        if "STUDENT_VACANCIES NOT LIKE '%PLAZAS: 0%'" in sql_upper or "PLAZAS: 0" in sql_upper:
            context["plazas_disponibles"] = True

        return context

    def _analyze_search_criteria(self, context: dict) -> list:
        """
        Analiza cada criterio de búsqueda individualmente y en combinación.
        Si hay filtro de plazas, muestra también cuántos tienen plazas disponibles.
        Retorna lista de tuplas: (descripción, count, count_con_plazas, tipo)
        """
        import sqlite3

        filtrar_plazas = context.get("plazas_disponibles", False)
        condicion_plazas = "student_vacancies NOT LIKE '%Plazas: 0%'"

        # Construir condiciones SQL individuales (sin incluir plazas como criterio separado)
        criterios = []
        if context["pais"]:
            criterios.append((
                f"País: {context['pais']}",
                f"destination_country LIKE '%{context['pais']}%'"
            ))
        if context["idioma"]:
            if context["nivel"]:
                criterios.append((
                    f"Idioma: {context['idioma']} {context['nivel']}",
                    f"language_requirements LIKE '%{context['idioma']}%' AND language_requirements LIKE '%{context['nivel']}%'"
                ))
            else:
                criterios.append((
                    f"Idioma: {context['idioma']}",
                    f"language_requirements LIKE '%{context['idioma']}%'"
                ))
        if context["facultad"]:
            criterios.append((
                f"Facultad: {context['facultad']}",
                f"uma_faculties LIKE '%{context['facultad']}%'"
            ))
        if context["programa"]:
            criterios.append((
                f"Programa: {context['programa']}",
                f"mobility_program LIKE '%{context['programa']}%'"
            ))
        if context["universidad"]:
            criterios.append((
                f"Universidad: {context['universidad']}",
                f"host_institution LIKE '%{context['universidad']}%'"
            ))

        if len(criterios) < 2:
            return []  # No tiene sentido analizar si hay solo 1 criterio

        resultados = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Contar para cada criterio individual (en toda la BD)
            for desc, condicion in criterios:
                # Total de convenios con este criterio
                query = f"SELECT COUNT(*) FROM destinations WHERE {condicion}"
                cursor.execute(query)
                count = cursor.fetchone()[0]

                # Convenios con plazas disponibles (si aplica el filtro)
                count_plazas = None
                if filtrar_plazas:
                    query_plazas = f"SELECT COUNT(*) FROM destinations WHERE {condicion} AND {condicion_plazas}"
                    cursor.execute(query_plazas)
                    count_plazas = cursor.fetchone()[0]

                resultados.append((desc, count, count_plazas, "individual", condicion))

            # Contar combinaciones de pares y la combinación total
            if len(criterios) >= 2:
                from itertools import combinations

                # Combinaciones de 2 criterios
                for (i, (desc1, cond1)), (j, (desc2, cond2)) in combinations(enumerate(criterios), 2):
                    where_clause = f"{cond1} AND {cond2}"
                    query = f"SELECT COUNT(*) FROM destinations WHERE {where_clause}"
                    cursor.execute(query)
                    count = cursor.fetchone()[0]

                    count_plazas = None
                    if filtrar_plazas:
                        query_plazas = f"SELECT COUNT(*) FROM destinations WHERE {where_clause} AND {condicion_plazas}"
                        cursor.execute(query_plazas)
                        count_plazas = cursor.fetchone()[0]

                    # Descripción: valores reales de ambos criterios
                    val1 = desc1.split(": ", 1)[1] if ": " in desc1 else desc1
                    val2 = desc2.split(": ", 1)[1] if ": " in desc2 else desc2
                    combo_desc = f"{val1} + {val2}"
                    resultados.append((combo_desc, count, count_plazas, "combinacion_2", None))

                # Combinación de todos los criterios (si hay 3 o más)
                if len(criterios) >= 3:
                    where_clause = ' AND '.join([cond for _, cond in criterios])
                    query = f"SELECT COUNT(*) FROM destinations WHERE {where_clause}"
                    cursor.execute(query)
                    count = cursor.fetchone()[0]

                    count_plazas = None
                    if filtrar_plazas:
                        query_plazas = f"SELECT COUNT(*) FROM destinations WHERE {where_clause} AND {condicion_plazas}"
                        cursor.execute(query_plazas)
                        count_plazas = cursor.fetchone()[0]

                    # Descripción: valores reales de todos los criterios
                    valores = [c[0].split(": ", 1)[1] if ": " in c[0] else c[0] for c in criterios]
                    combo_desc = " + ".join(valores)
                    resultados.append((combo_desc, count, count_plazas, "combinacion_total", None))

            conn.close()
        except Exception as e:
            logger.error(f"Error analizando criterios: {e}")
            return []

        return resultados

    def _generate_empty_result_message(self, user_question: str, sql_query: str) -> str:
        """Genera un mensaje explicativo cuando no hay resultados."""
        context = self._extract_search_context(sql_query)
        filtrar_plazas = context.get("plazas_disponibles", False)

        # Construir lista de condiciones aplicadas (para descripción)
        condiciones = []
        if context["pais"]:
            condiciones.append(("País", context["pais"]))
        if context["idioma"]:
            if context["nivel"]:
                condiciones.append(("Requisito de idioma", f"{context['idioma']} nivel {context['nivel']}"))
            else:
                condiciones.append(("Requisito de idioma", context["idioma"]))
        if context["facultad"]:
            condiciones.append(("Facultad", context["facultad"]))
        if context["programa"]:
            condiciones.append(("Programa", context["programa"]))
        if context["universidad"]:
            condiciones.append(("Universidad", context["universidad"]))

        # Construir descripción breve
        if not condiciones:
            search_desc = "los criterios especificados"
        else:
            search_desc = ", ".join([c[1] for c in condiciones])
            if filtrar_plazas:
                search_desc += " (con plazas disponibles)"

        # Mensaje base
        msg = f"🔍 **No se encontraron convenios** con {search_desc}.\n\n"

        # Análisis detallado si hay más de 1 condición
        if len(condiciones) > 1:
            analisis = self._analyze_search_criteria(context)
            if analisis:
                msg += "📊 **Análisis de criterios:**\n\n"

                # Cabecera de tabla (con o sin columna de plazas)
                if filtrar_plazas:
                    msg += "| Criterio | Convenios | Con plazas |\n"
                    msg += "|----------|----------:|----------:|\n"
                else:
                    msg += "| Criterio | Convenios |\n"
                    msg += "|----------|----------:|\n"

                # Mostrar criterios individuales
                # Formato: (desc, count, count_plazas, tipo, condicion)
                for item in analisis:
                    desc, count, count_plazas, tipo = item[0], item[1], item[2], item[3]
                    if tipo == "individual":
                        emoji = "✅" if count > 0 else "❌"
                        if filtrar_plazas:
                            emoji_plazas = "✅" if count_plazas and count_plazas > 0 else "❌"
                            plazas_str = str(count_plazas) if count_plazas is not None else "—"
                            msg += f"| {emoji} {desc} | {count} | {plazas_str} |\n"
                        else:
                            msg += f"| {emoji} {desc} | {count} |\n"

                # Separador y combinaciones de pares
                combinaciones_2 = [item for item in analisis if item[3] == "combinacion_2"]
                combinacion_total = [item for item in analisis if item[3] == "combinacion_total"]

                if combinaciones_2:
                    if filtrar_plazas:
                        msg += "|----------|----------:|----------:|\n"
                    else:
                        msg += "|----------|----------:|\n"

                    for item in combinaciones_2:
                        desc, count, count_plazas, tipo = item[0], item[1], item[2], item[3]
                        emoji = "✅" if count > 0 else "❌"
                        if filtrar_plazas:
                            plazas_str = str(count_plazas) if count_plazas is not None else "—"
                            msg += f"| {emoji} {desc} | {count} | {plazas_str} |\n"
                        else:
                            msg += f"| {emoji} {desc} | {count} |\n"

                # Separador y combinación total (si hay 3+ criterios)
                if combinacion_total:
                    if filtrar_plazas:
                        msg += "|----------|----------:|----------:|\n"
                    else:
                        msg += "|----------|----------:|\n"

                    for item in combinacion_total:
                        desc, count, count_plazas, tipo = item[0], item[1], item[2], item[3]
                        emoji = "✅" if count > 0 else "❌"
                        if filtrar_plazas:
                            plazas_str = str(count_plazas) if count_plazas is not None else "—"
                            msg += f"| {emoji} **{desc}** | {count} | {plazas_str} |\n"
                        else:
                            msg += f"| {emoji} **{desc}** | {count} |\n"

                msg += "\n"

                # Identificar la causa del problema
                criterios_sin_resultados = [item[0] for item in analisis if item[3] == "individual" and item[1] == 0]
                criterios_con_resultados = [(item[0], item[1]) for item in analisis if item[3] == "individual" and item[1] > 0]

                # Combinaciones de pares y total
                combos_2 = [(item[0], item[1], item[2]) for item in analisis if item[3] == "combinacion_2"]
                combo_total = [(item[0], item[1], item[2]) for item in analisis if item[3] == "combinacion_total"]

                if criterios_sin_resultados:
                    # Algún criterio individual no existe en la BD
                    msg += f"⚠️ **Criterio sin coincidencias en la BD:** {', '.join(criterios_sin_resultados)}\n"
                    msg += "No existen convenios con este requisito en toda la base de datos.\n\n"
                elif len(criterios_con_resultados) > 1:
                    # Todos los criterios individuales existen
                    # Analizar qué combinaciones de pares fallan
                    combos_ok = [(d, c) for d, c, _ in combos_2 if c > 0]
                    combos_fail = [(d, c) for d, c, _ in combos_2 if c == 0]

                    if combos_fail and combos_ok:
                        # Algunas combinaciones de pares funcionan, otras no
                        msg += f"⚠️ **Combinaciones que fallan:**\n"
                        for desc, _ in combos_fail:
                            msg += f"  • {desc}: no hay convenios con ambos criterios\n"
                        msg += "\n"
                    elif combos_fail and not combos_ok:
                        # Todas las combinaciones de pares fallan
                        msg += f"⚠️ **Ninguna combinación de criterios tiene resultados**\n"
                        msg += f"Existen convenios con cada criterio por separado:\n"
                        for nombre, cantidad in criterios_con_resultados:
                            msg += f"  • {nombre}: {cantidad} convenios\n"
                        msg += f"Pero no hay ningún convenio que cumpla dos criterios a la vez.\n\n"
                    elif combos_ok and combo_total and combo_total[0][1] == 0:
                        # Algunas combinaciones de pares funcionan, pero la combinación total falla
                        msg += f"⚠️ **No hay convenios que cumplan los 3 criterios a la vez**\n"
                        msg += f"Combinaciones parciales que sí existen:\n"
                        for desc, count in combos_ok:
                            msg += f"  • {desc}: {count} convenios\n"
                        msg += "\n"

        # Sugerencias basadas en el contexto
        msg += "💡 **Sugerencias:**\n"
        suggestions = []

        if context["idioma"] and context["nivel"]:
            suggestions.append(f"- Buscar convenios con {context['idioma']} sin filtrar por nivel")
            suggestions.append(f"- Probar con otro nivel (B1, B2, C1...)")
        if context["pais"]:
            suggestions.append(f"- Buscar otros países con requisitos similares")
        if context["idioma"]:
            suggestions.append(f"- Buscar destinos sin requisito de idioma")
        if context["facultad"]:
            suggestions.append(f"- Buscar convenios de otras facultades en el mismo país")

        if not suggestions:
            suggestions = [
                "- Ampliar los criterios de búsqueda",
                "- Probar con otros países o programas",
                "- Consultar destinos sin requisito de idioma"
            ]

        msg += "\n".join(suggestions[:3])

        return msg

    def _format_results(self, user_question: str, sql_query: str, results: list, success: bool, session_state: dict = None) -> str:
        """
        Formatea los resultados de la consulta SQL usando Python (rápido).
        """
        if not success:
            return f"❌ **Error en la consulta**\n\n{results}\n\nIntenta reformular tu pregunta."

        if not results:
            return self._generate_empty_result_message(user_question, sql_query)

        logger.info("📊 Formateando resultados con Python...")
        return self._format_results_basic(results, session_state=session_state)

    def _format_results_basic(self, results: list, max_display: int = 20, session_state: dict = None) -> str:
        """Formateo básico sin LLM (fallback)."""
        num_results = len(results)

        # Detectar si es una consulta de campos específicos (no tiene host_institution)
        if results and 'host_institution' not in results[0]:
            if session_state is not None:
                session_state['last_results_grouped'] = False
            return self._format_results_simple_fields(results)

        # Si hay más de 50 resultados, agrupar para mejor visualización
        if num_results > 50:
            if session_state is not None:
                session_state['last_results_grouped'] = True  # Marcar que están agrupados
            return self._format_results_grouped(results)

        # Si hay pocos resultados (1-5), mostrar información detallada
        if session_state is not None:
            session_state['last_results_grouped'] = False  # No están agrupados
        if num_results <= 5:
            return self._format_results_detailed(results)

        response_parts = [f"✅ **Encontré {num_results} convenio(s)**\n"]

        # Mostrar hasta max_display resultados con formato compacto
        display_count = min(num_results, max_display)
        for i, r in enumerate(results[:display_count], 1):
            response_parts.append(f"### {i}. {r.get('host_institution', 'N/A')}")
            response_parts.append(f"- **País:** {r.get('destination_country', 'N/A')}")
            response_parts.append(f"- **Programa:** {r.get('mobility_program', 'N/A')}")
            response_parts.append(f"- **Plazas:** {r.get('student_vacancies', 'N/A')}")
            response_parts.append(f"- **Idioma:** {r.get('language_requirements', 'N/A')}")
            response_parts.append("")

        if num_results > max_display:
            remaining = num_results - max_display
            response_parts.append(f"*... y {remaining} convenio(s) más*")
            response_parts.append(f'💡 *Para ver más, di: "Muéstrame los siguientes 20" o "Muéstrame todos"*')
            response_parts.append('💡 *También: "Muestra también el centro", "Ordena por país"*')
        else:
            # Con resultados moderados, mostrar ayuda para ampliar
            response_parts.append("---")
            response_parts.append('💡 *"Amplía el 1" | "Muestra también el centro" | "Ordena por país"*')

        return "\n".join(response_parts)

    def _format_results_detailed(self, results: list) -> str:
        """
        Formato detallado para pocos resultados (1-5).
        Muestra información extendida de cada convenio.
        """
        num_results = len(results)
        response_parts = [f"✅ **Encontré {num_results} convenio(s)**\n"]

        for i, r in enumerate(results, 1):
            response_parts.append(f"### {i}. 🏛️ {r.get('host_institution', 'N/A')}")
            response_parts.append(f"**País:** {r.get('destination_country', 'N/A')} | **Programa:** {r.get('mobility_program', 'N/A')}")
            response_parts.append("")

            # Vigencia
            start = r.get('start_date', '')
            end = r.get('end_date', '')
            if start or end:
                response_parts.append(f"📅 **Vigencia:** {start} → {end}")

            # Plazas
            vacancies = r.get('student_vacancies', '')
            if vacancies:
                response_parts.append(f"🎓 **Plazas:** {vacancies}")

            # Requisitos de idioma
            lang = r.get('language_requirements', '')
            if lang:
                # Simplificar si es muy largo
                if len(lang) > 100:
                    lang_short = self._extract_language_level(lang)
                    response_parts.append(f"🗣️ **Idioma:** {lang_short}")
                else:
                    response_parts.append(f"🗣️ **Idioma:** {lang}")

            # Facultades UMA
            uma_fac = r.get('uma_faculties', '')
            if uma_fac:
                # Acortar si hay muchas facultades
                if len(uma_fac) > 150:
                    uma_fac = uma_fac[:150] + "..."
                response_parts.append(f"🏫 **Facultades UMA:** {uma_fac}")

            # Titulaciones UMA
            uma_deg = r.get('uma_degrees', '')
            if uma_deg:
                if len(uma_deg) > 150:
                    uma_deg = uma_deg[:150] + "..."
                response_parts.append(f"📚 **Titulaciones:** {uma_deg}")

            # Facultad destino (si está especificada y no es genérica)
            dest_fac = r.get('destination_faculty', '')
            if dest_fac and dest_fac not in ['General/No especificada', 'N/A', '']:
                response_parts.append(f"🎯 **Facultad destino:** {dest_fac}")

            # Niveles disponibles
            levels = r.get('available_levels', '')
            if levels:
                response_parts.append(f"📈 **Niveles:** {levels}")

            response_parts.append("")  # Línea en blanco entre convenios

        # Ayuda para ver más detalles
        if num_results > 1:
            response_parts.append("---")
            response_parts.append('💡 *"Amplía el 1" | "Muestra también el centro" | "Ordena por país"*')

        return "\n".join(response_parts)

    def _format_results_grouped(self, results: list) -> str:
        """
        Agrupa resultados numerosos (>50) para mejor visualización.
        Detecta qué campos están disponibles y agrupa inteligentemente.
        """
        num_results = len(results)

        # Detectar qué campos están disponibles en los resultados
        available_fields = set(results[0].keys()) if results else set()

        # Si solo hay un campo, agrupar por valores únicos de ese campo
        if len(available_fields) == 1:
            field_name = list(available_fields)[0]
            return self._format_grouped_by_field(results, field_name, num_results)

        # Si no hay destination_country, buscar otro campo para agrupar
        if 'destination_country' not in available_fields:
            # Prioridad de campos para agrupar
            grouping_priority = ['host_institution', 'mobility_program', 'language_requirements', 'uma_faculties']
            for field in grouping_priority:
                if field in available_fields:
                    return self._format_grouped_by_field(results, field, num_results)
            # Si no hay ninguno, mostrar lista simple
            return self._format_results_simple_list(results, num_results)

        # Obtener países únicos
        countries = {}
        for r in results:
            country = r.get('destination_country', 'Sin país')
            if country not in countries:
                countries[country] = []
            countries[country].append(r)

        num_countries = len(countries)

        # Determinar tipo de agrupación
        if num_countries > 1:
            # Agrupar por país
            return self._format_grouped_by_country(results, countries, num_results)
        else:
            # Un solo país: verificar si hay host_institution
            if 'host_institution' in available_fields:
                return self._format_grouped_by_university(results, num_results)
            else:
                # Buscar otro campo para agrupar
                for field in ['mobility_program', 'language_requirements']:
                    if field in available_fields:
                        return self._format_grouped_by_field(results, field, num_results)
                return self._format_results_simple_list(results, num_results)

    def _format_grouped_by_country(self, results: list, countries: dict, num_results: int) -> str:
        """Formatea resultados agrupados por país."""
        response_parts = []
        response_parts.append(f"📊 **Se encontraron {num_results} resultados agrupados por país**\n")

        # Ordenar países por número de convenios (descendente)
        sorted_countries = sorted(countries.items(), key=lambda x: len(x[1]), reverse=True)

        for country, country_results in sorted_countries:
            num_convenios = len(country_results)
            # Obtener universidades únicas en este país
            universities = set(r.get('host_institution', 'N/A') for r in country_results)
            num_universities = len(universities)

            response_parts.append(f"### 🌍 {country}")
            response_parts.append(f"- **Convenios:** {num_convenios}")
            response_parts.append(f"- **Universidades:** {num_universities}")
            response_parts.append("")

        # Añadir sugerencia para afinar búsqueda
        response_parts.append("---")
        response_parts.append("💡 **¿Deseas afinar la búsqueda?**")
        top_country = sorted_countries[0][0]
        response_parts.append(f'Puedes decir: *"Sí, muéstrame los de {top_country}"*')
        response_parts.append('O añade más filtros: *"Los que además requieran inglés B2"*, *"Solo los del primer cuatrimestre"*')

        return "\n".join(response_parts)

    def _format_grouped_by_university(self, results: list, num_results: int) -> str:
        """Formatea resultados agrupados por universidad (cuando hay un solo país)."""
        response_parts = []

        # Obtener el país (es único)
        country = results[0].get('destination_country', 'Sin país') if results else 'Sin país'

        # Agrupar por universidad
        universities = {}
        for r in results:
            uni = r.get('host_institution', 'Sin universidad')
            if uni not in universities:
                universities[uni] = []
            universities[uni].append(r)

        num_universities = len(universities)

        response_parts.append(f"📊 **Se encontraron {num_results} resultados en {country}, agrupados por universidad**\n")

        # Ordenar universidades por número de convenios (descendente)
        sorted_unis = sorted(universities.items(), key=lambda x: len(x[1]), reverse=True)

        for uni, uni_results in sorted_unis:
            num_convenios = len(uni_results)
            # Obtener programas únicos
            programs = set(r.get('mobility_program', 'N/A') for r in uni_results)

            response_parts.append(f"### 🏛️ {uni}")
            response_parts.append(f"- **Convenios:** {num_convenios}")
            response_parts.append(f"- **Programas:** {', '.join(programs)}")
            response_parts.append("")

        # Añadir sugerencia para afinar búsqueda
        response_parts.append("---")
        response_parts.append("💡 **¿Deseas afinar la búsqueda?**")
        top_uni = sorted_unis[0][0]
        # Acortar el nombre si es muy largo
        short_uni = top_uni[:40] + "..." if len(top_uni) > 40 else top_uni
        response_parts.append(f'Puedes decir: *"Sí, muéstrame los de {short_uni}"*')
        response_parts.append('O añade más filtros: *"Los que además requieran inglés B2"*, *"Solo los del primer cuatrimestre"*')

        return "\n".join(response_parts)

    def _extract_language_level(self, value: str) -> str:
        """
        Extrae idioma y nivel de un campo language_requirements.
        Ejemplo: "ALEMÁN (Nivel: B1) -> Certificado..." → "ALEMÁN B1"
        """
        import re
        if not value or value == 'Sin especificar':
            return value

        # Buscar todos los patrones IDIOMA (Nivel: X)
        pattern = r'([A-ZÁÉÍÓÚÑ]+)\s*\(Nivel:\s*([A-Z0-9]+)\)'
        matches = re.findall(pattern, value, re.IGNORECASE)

        if matches:
            # Combinar todos los idiomas encontrados: "ALEMÁN B1, INGLÉS B2"
            return ", ".join(f"{idioma.upper()} {nivel.upper()}" for idioma, nivel in matches)

        # Si no hay patrón de nivel, buscar "No requiere acreditación"
        if 'no requiere' in value.lower():
            return "Sin requisito de idioma"

        # Fallback: devolver valor truncado
        return value[:40] + "..." if len(value) > 40 else value

    def _format_grouped_by_field(self, results: list, field_name: str, num_results: int) -> str:
        """Agrupa resultados por un campo específico."""
        response_parts = []

        # Nombres legibles para los campos
        field_labels = {
            'language_requirements': 'nivel de idioma',
            'mobility_program': 'programa',
            'host_institution': 'universidad',
            'destination_country': 'país',
            'uma_faculties': 'facultad UMA',
        }
        label = field_labels.get(field_name, field_name)

        # Agrupar por valores únicos del campo
        groups = {}
        for r in results:
            raw_value = r.get(field_name, 'Sin especificar')

            # Para language_requirements, extraer solo idioma y nivel
            if field_name == 'language_requirements':
                value = self._extract_language_level(raw_value)
            else:
                value = raw_value

            if value not in groups:
                groups[value] = 0
            groups[value] += 1

        # Ordenar alfabéticamente por el campo de agrupación
        sorted_groups = sorted(groups.items(), key=lambda x: x[0])

        response_parts.append(f"📊 **Se encontraron {num_results} resultados agrupados por {label}**\n")

        for value, count in sorted_groups[:15]:  # Limitar a 15 grupos
            # Truncar valores muy largos
            display_value = value[:80] + "..." if len(str(value)) > 80 else value
            response_parts.append(f"- **{display_value}**: {count} convenio(s)")

        if len(sorted_groups) > 15:
            response_parts.append(f"\n*... y {len(sorted_groups) - 15} grupos más*")

        # Añadir sugerencia de refinamiento con ejemplos personalizados
        response_parts.append("")
        response_parts.append("---")
        response_parts.append("💡 **¿Deseas afinar la búsqueda?**")

        # Generar ejemplos basados en los grupos mostrados
        example_value = sorted_groups[0][0] if sorted_groups else "valor"

        # Personalizar el ejemplo según el campo
        if field_name == 'language_requirements':
            response_parts.append(f'Puedes decir: *"Sí, muéstrame los de {example_value}"*')
        elif field_name == 'destination_country':
            response_parts.append(f'Puedes decir: *"Sí, muéstrame los de {example_value}"*')
        elif field_name == 'mobility_program':
            response_parts.append(f'Puedes decir: *"Sí, solo los de {example_value}"*')
        elif field_name == 'host_institution':
            response_parts.append(f'Puedes decir: *"Sí, muéstrame los de {example_value}"*')
        else:
            response_parts.append(f'Puedes decir: *"Sí, muéstrame los de {example_value}"*')

        response_parts.append('O añade más filtros: *"Los que además requieran inglés B2"*, *"Solo los del primer cuatrimestre"*')

        return "\n".join(response_parts)

    def _format_results_simple_fields(self, results: list) -> str:
        """
        Formato para consultas que devuelven campos específicos (no convenios completos).
        Ej: SELECT DISTINCT uma_faculties, SELECT DISTINCT destination_country, etc.
        """
        num_results = len(results)
        if not results:
            return "🔍 **No se encontraron resultados**"

        # Obtener los nombres de los campos
        fields = list(results[0].keys())

        # Mapeo de campos a nombres legibles
        field_labels = {
            'uma_faculties': 'Facultades UMA',
            'destination_country': 'País',
            'host_institution': 'Universidad',
            'mobility_program': 'Programa',
            'destination_faculty': 'Facultad de destino',
            'uma_degrees': 'Titulaciones UMA',
            'language_requirements': 'Idioma',
        }

        # Si es un solo campo, mostrar como lista simple
        if len(fields) == 1:
            field = fields[0]
            label = field_labels.get(field, field.replace('_', ' ').title())
            response_parts = [f"✅ **Encontré {num_results} {label.lower()}:**\n"]

            for i, r in enumerate(results, 1):
                value = r.get(field, 'N/A')
                if value:
                    response_parts.append(f"{i}. {value}")

            return "\n".join(response_parts)

        # Si hay múltiples campos, mostrar en formato tabla
        response_parts = [f"✅ **Encontré {num_results} resultado(s)**\n"]

        for i, r in enumerate(results[:20], 1):
            parts = []
            for field in fields:
                value = r.get(field)
                if value:
                    label = field_labels.get(field, field.replace('_', ' ').title())
                    parts.append(f"**{label}:** {value}")
            if parts:
                response_parts.append(f"{i}. " + " | ".join(parts))

        if num_results > 20:
            response_parts.append(f"\n*... y {num_results - 20} más*")

        return "\n".join(response_parts)

    def _format_results_simple_list(self, results: list, num_results: int) -> str:
        """Formato simple cuando no hay campo claro para agrupar."""
        response_parts = [f"✅ **Encontré {num_results} resultado(s)**\n"]

        # Mostrar los primeros resultados con todos sus campos
        for i, r in enumerate(results[:10], 1):
            response_parts.append(f"### {i}.")
            for key, value in r.items():
                if value:
                    display_value = str(value)[:100] + "..." if len(str(value)) > 100 else value
                    response_parts.append(f"- **{key}:** {display_value}")
            response_parts.append("")

        if num_results > 10:
            response_parts.append(f"*... y {num_results - 10} más*")

        return "\n".join(response_parts)

    def _format_as_html_table(self, results: list) -> str:
        """Formatea los resultados JSON como una tabla HTML interactiva."""
        if not results:
            return "<p><em>Sin resultados</em></p>"

        import json as json_module
        columns = list(results[0].keys())

        html = """<div class="sql-results" style="margin: 15px 0;">
<style>
.sql-table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
.sql-table th {{ background: #2c3e50; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }}
.sql-table td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
.sql-table tr:hover {{ background: #f5f5f5; }}
.sql-table tr:nth-child(even) {{ background: #fafafa; }}
.sql-table .number {{ text-align: right; font-family: monospace; }}
.sql-table .null {{ color: #999; font-style: italic; }}
.sql-stats {{ margin-bottom: 10px; color: #666; font-size: 13px; }}
</style>
<div class="sql-stats">Resultados: <strong>{row_count}</strong> filas</div>
<div style="overflow-x: auto;">
<table class="sql-table">
<thead><tr>{headers}</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
</div>"""

        headers = "".join(f"<th>{col}</th>" for col in columns)

        rows_html = []
        for row in results[:100]:  # Limitar a 100 filas
            cells = []
            for col in columns:
                val = row.get(col)
                if val is None:
                    cells.append('<td class="null">NULL</td>')
                elif isinstance(val, (int, float)):
                    cells.append(f'<td class="number">{val}</td>')
                else:
                    escaped = str(val).replace("<", "&lt;").replace(">", "&gt;")
                    cells.append(f"<td>{escaped}</td>")
            rows_html.append(f"<tr>{''.join(cells)}</tr>")

        return html.format(
            row_count=len(results),
            headers=headers,
            rows="\n".join(rows_html)
        )

    def _log_timing_summary(self, timings: dict):
        """Muestra un resumen de tiempos del workflow en el log."""
        logger.info("=" * 60)
        logger.info("⏱️  RESUMEN DE TIEMPOS DEL WORKFLOW")
        logger.info("=" * 60)

        total = 0
        for fase, tiempo in timings.items():
            total += tiempo
            logger.info(f"  {fase}: {tiempo:.3f}s")

        logger.info("-" * 60)
        logger.info(f"  TIEMPO TOTAL: {total:.3f}s")
        logger.info("=" * 60)

    def chat(self, user_message: str, history: list = None, session_id: str = None) -> str:
        """
        Procesa una pregunta del usuario:
        1. Obtiene el esquema de la BD
        2. Convierte la pregunta a SQL
        3. Ejecuta el SQL usando consultar_sql.py
        4. Muestra los resultados en tabla HTML inline
        5. Formatea y devuelve los resultados
        """
        # Usar session_id por defecto si no se proporciona
        if session_id is None:
            session_id = "default"

        state = self._get_session_state(session_id)

        # Iniciar medición de tiempos
        timings = {}
        t_start = time.perf_counter()

        logger.info(f"📩 Usuario: {user_message} (session: {session_id})")

        # Verificar si el usuario quiere ver más resultados
        if self._is_show_more_query(user_message):
            logger.info("📄 Mostrando más resultados...")
            return self._handle_show_more(session_id, user_message)

        # Verificar si el usuario pide detalles de un acuerdo específico
        is_detail, detail_num = self._is_detail_request(user_message)
        if is_detail:
            logger.info(f"📋 Mostrando detalles del acuerdo #{detail_num}...")
            return self._show_agreement_details(session_id, detail_num)

        # Verificar si el usuario quiere volver a una búsqueda anterior
        if self._is_back_request(user_message):
            logger.info("⏪ Volviendo a búsqueda anterior...")
            return self._handle_back_request(session_id)

        # Verificar si el usuario quiere ver el historial de consultas
        if self._is_history_request(user_message):
            logger.info("📋 Mostrando historial de consultas...")
            return self._show_history(session_id)

        # Verificar si el usuario quiere ver un campo adicional
        is_show_field, field_name = self._is_show_field_request(user_message)
        if is_show_field:
            logger.info(f"📋 Mostrando campo adicional: {field_name}...")
            return self._handle_show_field(session_id, field_name)

        # Verificar si el usuario quiere ordenar los resultados
        is_sort, sort_field, ascending = self._is_sort_request(user_message)
        if is_sort:
            direction = "ascendente" if ascending else "descendente"
            logger.info(f"📊 Ordenando resultados por {sort_field} ({direction})...")
            return self._handle_sort_results(session_id, sort_field, ascending)

        # Verificar que existe la BD
        if not os.path.exists(self.db_path):
            return """⚠️ **Base de datos no encontrada**

Por favor, crea una base de datos SQLite en `data/database.db`.

Ejemplo:
```bash
sqlite3 data/database.db < tu_schema.sql
```"""

        # ⏱️ Fase 1: Recepción de pregunta y obtención de esquema
        t_fase1_start = time.perf_counter()
        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            return f"⚠️ {schema}"
        t_fase1_end = time.perf_counter()
        timings["1. Recepción pregunta + esquema BD"] = t_fase1_end - t_fase1_start

        # ⏱️ Fase 2: Convertir texto a SQL (LLM)
        t_fase2_start = time.perf_counter()

        # Guardar consulta anterior en historial antes de ejecutar nueva
        self._save_to_history(session_id)

        # Detectar si es un refinamiento de la consulta anterior
        previous_sql = None
        if self._is_refinement_query(session_id, user_message):
            previous_sql = state['last_sql_query']
            logger.info(f"🔄 Refinando consulta anterior")

        sql_query = self._text_to_sql(user_message, schema, previous_sql)
        t_fase2_end = time.perf_counter()
        timings["2. LLM genera SQL"] = t_fase2_end - t_fase2_start

        # Validar que no sea un error del LLM
        if sql_query.strip().upper().startswith("ERROR:"):
            self._log_timing_summary(timings)
            return f"⚠️ {sql_query}"

        # Guardar la consulta y pregunta para posibles refinamientos futuros
        state['last_sql_query'] = sql_query
        state['last_user_question'] = user_message

        # Mostrar la SQL generada
        sql_display = f"```sql\n{sql_query}\n```\n\n"

        # ⏱️ Fase 3: Ejecutar SQL usando consultar_sql.py
        t_fase3_start = time.perf_counter()
        try:
            logger.info(f"⚡ Ejecutando consultar_sql.py...")

            # Llamar a consultar_sql.py con --json
            consultar_result = subprocess.run(
                [sys.executable, CONSULTAR_SQL_PATH, self.db_path, sql_query, "--json"],
                capture_output=True,
                text=True
            )

            if consultar_result.returncode != 0:
                error_msg = consultar_result.stderr or "Error desconocido"
                logger.error(f"❌ Error en consultar_sql.py: {error_msg}")
                t_fase3_end = time.perf_counter()
                timings["3. Ejecución SQLite"] = t_fase3_end - t_fase3_start
                self._log_timing_summary(timings)
                return f"⚠️ Error ejecutando consulta: {error_msg}"

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            # Parsear JSON
            import json as json_module
            results = json_module.loads(json_output)
            logger.info(f"📊 Resultados: {len(results)} filas")

        except Exception as e:
            logger.error(f"❌ Error ejecutando consultar_sql.py: {str(e)}")
            # Fallback: ejecutar SQL internamente
            success, results = self._execute_sql(sql_query)
            if not success:
                t_fase3_end = time.perf_counter()
                timings["3. Ejecución SQLite"] = t_fase3_end - t_fase3_start
                self._log_timing_summary(timings)
                return f"⚠️ Error: {str(e)}"

        t_fase3_end = time.perf_counter()
        timings["3. Ejecución SQLite"] = t_fase3_end - t_fase3_start

        # ⏱️ Fase 4: Formatear explicación con LLM
        t_fase4_start = time.perf_counter()
        success, results = self._execute_sql(sql_query)

        # Guardar resultados para paginación
        if success and results:
            state['last_results'] = results
            state['last_display_offset'] = min(self.default_page_size, len(results))

        formatted = self._format_results(user_message, sql_query, results, success, state)
        t_fase4_end = time.perf_counter()
        timings["4. Python formatea respuesta"] = t_fase4_end - t_fase4_start

        # Mostrar resumen de tiempos
        self._log_timing_summary(timings)

        # Paso 5: Combinar SQL + explicación (sin tabla HTML redundante)
        return f"**Consulta SQL generada:**\n{sql_display}{formatted}"

    async def chat_stream(self, user_message: str, history: list = None, session_id: str = None):
        """
        Versión streaming - emite eventos de estado y contenido.
        """
        # Usar session_id por defecto si no se proporciona
        if session_id is None:
            session_id = "default"

        state = self._get_session_state(session_id)

        # Iniciar medición de tiempos
        timings = {}

        logger.info(f"📩 [STREAM] Usuario: {user_message} (session: {session_id})")

        # Verificar si el usuario quiere ver más resultados
        if self._is_show_more_query(user_message):
            logger.info("📄 [STREAM] Mostrando más resultados...")
            yield ("content", self._handle_show_more(session_id, user_message))
            return

        # Verificar si el usuario pide detalles de un acuerdo específico
        is_detail, detail_num = self._is_detail_request(user_message)
        if is_detail:
            logger.info(f"📋 [STREAM] Mostrando detalles del acuerdo #{detail_num}...")
            yield ("content", self._show_agreement_details(session_id, detail_num))
            return

        # Verificar si el usuario quiere volver a una búsqueda anterior
        if self._is_back_request(user_message):
            logger.info("⏪ [STREAM] Volviendo a búsqueda anterior...")
            yield ("content", self._handle_back_request(session_id))
            return

        # Verificar si el usuario quiere ver el historial de consultas
        if self._is_history_request(user_message):
            logger.info("📋 [STREAM] Mostrando historial de consultas...")
            yield ("content", self._show_history(session_id))
            return

        # Verificar si el usuario quiere ver un campo adicional
        is_show_field, field_name = self._is_show_field_request(user_message)
        if is_show_field:
            logger.info(f"📋 [STREAM] Mostrando campo adicional: {field_name}...")
            yield ("content", self._handle_show_field(session_id, field_name))
            return

        # Verificar si el usuario quiere ordenar los resultados
        is_sort, sort_field, ascending = self._is_sort_request(user_message)
        if is_sort:
            direction = "ascendente" if ascending else "descendente"
            logger.info(f"📊 [STREAM] Ordenando resultados por {sort_field} ({direction})...")
            yield ("content", self._handle_sort_results(session_id, sort_field, ascending))
            return

        # Verificar BD
        if not os.path.exists(self.db_path):
            yield ("content", "⚠️ **Base de datos no encontrada**\n\nCrea una base de datos SQLite en `data/database.db`.")
            return

        # ⏱️ Fase 1: Recepción de pregunta y obtención de esquema
        t_fase1_start = time.perf_counter()
        yield ("status", "Analizando esquema de la base de datos...")
        schema = self._get_db_schema()
        t_fase1_end = time.perf_counter()
        timings["1. Recepción pregunta + esquema BD"] = t_fase1_end - t_fase1_start

        # ⏱️ Fase 2: Convertir texto a SQL (LLM)
        t_fase2_start = time.perf_counter()

        # Guardar consulta anterior en historial antes de ejecutar nueva
        self._save_to_history(session_id)

        # Detectar si es un refinamiento de la consulta anterior
        previous_sql = None
        if self._is_refinement_query(session_id, user_message):
            previous_sql = state['last_sql_query']
            yield ("status", "Refinando consulta anterior...")
        else:
            yield ("status", "Convirtiendo pregunta a SQL...")

        sql_query = self._text_to_sql(user_message, schema, previous_sql)
        t_fase2_end = time.perf_counter()
        timings["2. LLM genera SQL"] = t_fase2_end - t_fase2_start

        # Validar que no sea un error del LLM
        if sql_query.strip().upper().startswith("ERROR:"):
            self._log_timing_summary(timings)
            yield ("content", f"⚠️ {sql_query}")
            return

        # Guardar la consulta y pregunta para posibles refinamientos futuros
        state['last_sql_query'] = sql_query
        state['last_user_question'] = user_message

        # Mostrar la SQL generada inmediatamente
        yield ("content", f"**Consulta SQL generada:**\n```sql\n{sql_query}\n```\n\n")

        # ⏱️ Fase 3: Ejecutar SQL
        t_fase3_start = time.perf_counter()
        yield ("status", "Ejecutando consulta...")

        # Ejecutar SQL usando consultar_sql.py
        html_table = ""
        try:
            # Llamar a consultar_sql.py con --json
            consultar_result = subprocess.run(
                [sys.executable, CONSULTAR_SQL_PATH, self.db_path, sql_query, "--json"],
                capture_output=True,
                text=True
            )

            if consultar_result.returncode != 0:
                error_msg = consultar_result.stderr or "Error desconocido"
                logger.error(f"❌ Error en consultar_sql.py: {error_msg}")
                t_fase3_end = time.perf_counter()
                timings["3. Ejecución SQLite"] = t_fase3_end - t_fase3_start
                self._log_timing_summary(timings)
                yield ("content", f"⚠️ Error ejecutando consulta: {error_msg}")
                return

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            yield ("status", "Procesando resultados...")

            # Parsear JSON
            import json as json_module
            results = json_module.loads(json_output)
            logger.info(f"📊 Resultados: {len(results)} filas")

        except Exception as e:
            logger.error(f"❌ Error ejecutando consultar_sql.py: {str(e)}")
            # Fallback: ejecutar SQL internamente
            success, results = self._execute_sql(sql_query)
            if not success:
                t_fase3_end = time.perf_counter()
                timings["3. Ejecución SQLite"] = t_fase3_end - t_fase3_start
                self._log_timing_summary(timings)
                yield ("content", f"⚠️ Error: {str(e)}")
                return

        t_fase3_end = time.perf_counter()
        timings["3. Ejecución SQLite"] = t_fase3_end - t_fase3_start

        # ⏱️ Fase 4: Formatear explicación con LLM
        t_fase4_start = time.perf_counter()
        yield ("status", "Formateando explicación...")
        success, results = self._execute_sql(sql_query)

        # Guardar resultados para paginación y detalles
        if success and results:
            state['last_results'] = results
            state['last_display_offset'] = min(self.default_page_size, len(results))

        formatted = self._format_results(user_message, sql_query, results, success, state)
        t_fase4_end = time.perf_counter()
        timings["4. Python formatea respuesta"] = t_fase4_end - t_fase4_start

        # Mostrar resumen de tiempos
        self._log_timing_summary(timings)

        # Enviar solo la explicación formateada (sin tabla HTML redundante)
        yield ("content", formatted)

    def get_schema(self) -> str:
        """Devuelve el esquema de la BD (útil para debugging/API)."""
        return self._get_db_schema()

    def get_history(self, session_id: str = None) -> list:
        """Devuelve el historial de consultas para la API."""
        if session_id is None:
            session_id = "default"

        state = self._get_session_state(session_id)
        all_queries = []

        for entry in state['query_history']:
            all_queries.append({
                'question': entry.get('question', ''),
                'sql': entry.get('sql', ''),
                'num_results': len(entry.get('results', []))
            })

        # Añadir la consulta actual si existe
        if state['last_sql_query']:
            all_queries.append({
                'question': state['last_user_question'] or '(consulta actual)',
                'sql': state['last_sql_query'],
                'num_results': len(state['last_results']) if state['last_results'] else 0
            })

        return all_queries

    def chat_with_metrics(self, user_message: str, history: list = None) -> dict:
        """
        Procesa una pregunta y devuelve métricas detalladas para benchmarking.

        Returns:
            dict con keys:
                - question: pregunta original
                - sql_query: SQL generado
                - success: si la consulta fue exitosa
                - num_results: número de resultados
                - timings: dict con tiempos de cada fase
                - total_time: tiempo total
                - response: respuesta formateada
                - error: mensaje de error (si hubo)
        """
        metrics = {
            "question": user_message,
            "sql_query": None,
            "success": False,
            "num_results": 0,
            "timings": {},
            "total_time": 0,
            "response": None,
            "error": None
        }

        t_total_start = time.perf_counter()

        # Verificar que existe la BD
        if not os.path.exists(self.db_path):
            metrics["error"] = "Base de datos no encontrada"
            return metrics

        # Fase 1: Obtener esquema
        t_fase1_start = time.perf_counter()
        schema = self._get_db_schema()
        if schema.startswith("ERROR:"):
            metrics["error"] = schema
            return metrics
        t_fase1_end = time.perf_counter()
        metrics["timings"]["1_schema"] = round(t_fase1_end - t_fase1_start, 4)

        # Fase 2: Convertir texto a SQL (LLM)
        t_fase2_start = time.perf_counter()
        try:
            sql_query = self._text_to_sql(user_message, schema)
            metrics["sql_query"] = sql_query
        except Exception as e:
            metrics["error"] = f"Error generando SQL: {str(e)}"
            t_fase2_end = time.perf_counter()
            metrics["timings"]["2_text_to_sql"] = round(t_fase2_end - t_fase2_start, 4)
            metrics["total_time"] = round(time.perf_counter() - t_total_start, 4)
            return metrics
        t_fase2_end = time.perf_counter()
        metrics["timings"]["2_text_to_sql"] = round(t_fase2_end - t_fase2_start, 4)

        # Validar SQL
        if sql_query.strip().upper().startswith("ERROR:"):
            metrics["error"] = sql_query
            metrics["total_time"] = round(time.perf_counter() - t_total_start, 4)
            return metrics

        # Fase 3: Ejecutar SQL
        t_fase3_start = time.perf_counter()
        success, results = self._execute_sql(sql_query)
        t_fase3_end = time.perf_counter()
        metrics["timings"]["3_execute_sql"] = round(t_fase3_end - t_fase3_start, 4)

        metrics["success"] = success
        if success:
            metrics["num_results"] = len(results) if isinstance(results, list) else 0
        else:
            metrics["error"] = results

        # Fase 4: Formatear respuesta
        t_fase4_start = time.perf_counter()
        formatted = self._format_results(user_message, sql_query, results, success)
        t_fase4_end = time.perf_counter()
        metrics["timings"]["4_format_response"] = round(t_fase4_end - t_fase4_start, 4)

        metrics["response"] = formatted
        metrics["total_time"] = round(time.perf_counter() - t_total_start, 4)

        return metrics
