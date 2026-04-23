"""
Pisha4 - Agente Text-to-SQL with SQL verification and reliability badges.
Convierte preguntas en lenguaje natural a consultas SQL usando qwen2.5-coder via Ollama.
Usa Chain-of-Thought (CoT) para mejorar el razonamiento en consultas complejas.
Adds schema verification and reliability assessment (badges) to every response.
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
from sql_verifier import SQLVerifier, SQLReliabilityBadge

# Load config.json
import json as _json
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(_config_path, "r", encoding="utf-8") as _f:
        _agent_config = _json.load(_f)
except FileNotFoundError:
    _agent_config = {}

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("pisha4")

# UNINOVIS Alliance members (excluding UMA which is the home university)
UNINOVIS_MEMBERS = [
    "Sorbonne Paris Nord",      # USPN - France
    "Campania",                 # UDCLV - Italy (Luigi Vanvitelli)
    "Kauno Kolegija",           # KK - Lithuania
    "Tirana",                   # UT - Albania
    "Würzburg-Schweinfurt",     # THWS - Germany
    "Tampere",                  # TAMK - Finland
    "The Hague",                # THUAS - Netherlands
]


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")
        self.schema_path = os.path.join(os.path.dirname(__file__), "data", "database_schema.md")
        self._cached_schema = None  # Cache del esquema
        # SQL verification and reliability
        self._config = _agent_config
        self._transparency = self._config.get("transparency_level", "crystal_box")
        self._prompt_level = self._config.get("prompt_level", "stringent")
        self._sql_verifier = SQLVerifier(self.db_path)
        # Audit log
        self._audit_path = os.path.join(os.path.dirname(__file__), "data", "audit_log.jsonl")
        self._audit_enabled = self._config.get("audit_log_enabled", False)
        self.system_prompt = """You are Pisha4, a database assistant specialized in converting natural language questions to SQL queries.

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
                'operations_history': [],  # Track modifications on results
                'last_user_question': None,
                'shown_fields': set(),  # Track extra fields that have been shown
            }
        return self._sessions[session_id]

    def _add_operation_to_history(self, session_id: str, operation_type: str, description: str):
        """Adds an operation (modification) to the history."""
        state = self._get_session_state(session_id)
        state['operations_history'].append({
            'type': operation_type,
            'description': description,
            'sql': state['last_sql_query'],
            'query_index': len(state['query_history'])  # Links to the parent query
        })
        # Limit operations history size
        if len(state['operations_history']) > 50:
            state['operations_history'].pop(0)

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
            # Spanish
            "muéstrame más", "muestrame mas", "muestrame más", "muéstrame mas",
            "ver más", "ver mas", "mostrar más", "mostrar mas",
            "siguientes", "los siguientes", "más resultados", "mas resultados",
            "continuar", "continúa", "continua",
            "muéstrame todos", "muestrame todos", "ver todos", "mostrar todos",
            "todos los resultados", "lista completa",
            # English
            "show me more", "show more", "see more", "more results",
            "next", "the next", "following", "continue",
            "show me all", "show all", "see all", "all results",
            "complete list", "full list",
        ]
        for pattern in show_more_patterns:
            if pattern in question_lower:
                return True
        return False

    def _is_back_request(self, question: str) -> bool:
        """Detecta si el usuario quiere volver a una búsqueda anterior."""
        question_lower = question.lower().strip()
        back_patterns = [
            # Spanish
            "volver atrás", "volver atras", "vuelve atrás", "vuelve atras",
            "búsqueda anterior", "busqueda anterior", "consulta anterior",
            "deshacer", "atrás", "atras",
            "volver a la anterior", "restaurar", "recuperar anterior",
            "quita el filtro", "quitar filtro", "sin filtro",
            "volver al principio", "empezar de nuevo",
            # English
            "go back", "back", "undo", "previous search", "previous query",
            "restore", "recover previous", "remove filter", "without filter",
            "start over", "start again",
        ]
        for pattern in back_patterns:
            if pattern in question_lower:
                return True
        return False

    def _is_history_request(self, question: str) -> bool:
        """Detecta si el usuario quiere ver el historial de consultas."""
        question_lower = question.lower().strip()
        history_patterns = [
            # Spanish
            "historial", "ver historial", "mostrar historial",
            "mis consultas", "ver consultas", "consultas anteriores",
            "mis preguntas", "ver preguntas", "preguntas anteriores",
            "qué he preguntado", "que he preguntado",
            "ver sql", "mostrar sql", "mis sql",
            # English
            "history", "show history", "view history",
            "my queries", "view queries", "previous queries",
            "my questions", "view questions", "previous questions",
            "what have i asked", "what did i ask",
            "show sql", "view sql", "my sql",
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
            # Spanish
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
            'idioma': 'lang_1_name',
            'idiomas': 'lang_1_name',
            'requisito': 'lang_1_name',
            'requisitos': 'lang_1_name',
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
            # English
            'faculty': 'uma_faculties',
            'faculties': 'uma_faculties',
            'school': 'uma_faculties',
            'schools': 'uma_faculties',
            'degree': 'uma_degrees',
            'degrees': 'uma_degrees',
            'major': 'uma_degrees',
            'majors': 'uma_degrees',
            'program': 'mobility_program',
            'programs': 'mobility_program',
            'program type': 'mobility_program',
            'language': 'lang_1_name',
            'languages': 'lang_1_name',
            'requirement': 'lang_1_name',
            'requirements': 'lang_1_name',
            'vacancy': 'student_vacancies',
            'vacancies': 'student_vacancies',
            'spots': 'student_vacancies',
            'slots': 'student_vacancies',
            'duration': 'student_vacancies',
            'date': 'start_date',
            'dates': 'start_date',
            'validity': 'start_date',
            'country': 'destination_country',
            'countries': 'destination_country',
            'university': 'host_institution',
            'universities': 'host_institution',
            'institution': 'host_institution',
            'institutions': 'host_institution',
            'destination faculty': 'destination_faculty',
            'host faculty': 'destination_faculty',
            'level': 'available_levels',
            'levels': 'available_levels',
        }

        # Patrones para detectar peticiones de mostrar campo adicional
        show_patterns = [
            # Spanish (with accent handling: é->e, á->a, etc.)
            r'mu[eé]stra(?:me)?\s+tambi[eé]n\s+(?:el|la|los|las)?\s*(.+)',
            r'a[nñ]ade\s+tambi[eé]n\s+(?:el|la|los|las)?\s*(.+)',
            r'incluye\s+tambi[eé]n\s+(?:el|la|los|las)?\s*(.+)',
            r'mu[eé]stra(?:me)?\s+(?:el|la|los|las)?\s*(.+)',
            r'a[nñ]ade\s+(?:el|la|los|las)?\s*(.+)',
            r'incluye\s+(?:el|la|los|las)?\s*(.+)',
            r'pon(?:me)?\s+(?:el|la|los|las)?\s*(.+)',
            r'quiero\s+ver\s+(?:el|la|los|las)?\s*(.+)',
            r'ver\s+(?:el|la|los|las)?\s*(.+)',
            # English
            r'also\s+show\s+(?:me\s+)?(?:the\s+)?(.+)',
            r'show\s+(?:me\s+)?also\s+(?:the\s+)?(.+)',
            r'add\s+(?:the\s+)?(.+)',
            r'include\s+(?:the\s+)?(.+)',
            r'show\s+(?:me\s+)?(?:the\s+)?(.+)',
            r'i\s+want\s+to\s+see\s+(?:the\s+)?(.+)',
            r'see\s+(?:the\s+)?(.+)',
        ]

        # Words that indicate filtering (refinement), NOT showing a field
        filter_indicators = [
            'solo', 'only', 'solamente', 'únicamente', 'unicamente',
            'de derecho', 'de medicina', 'de ingeniería', 'de ingenieria',
            'de ciencias', 'de económicas', 'de economicas', 'de turismo',
            'de comercio', 'de educación', 'de educacion', 'de psicología',
            'of law', 'of medicine', 'of engineering', 'of science',
            'of business', 'of education', 'of psychology',
            # Language levels - "nivel B2" is a language filter, not academic level
            'nivel a1', 'nivel a2', 'nivel b1', 'nivel b2', 'nivel c1', 'nivel c2',
            'level a1', 'level a2', 'level b1', 'level b2', 'level c1', 'level c2',
            'de nivel a1', 'de nivel a2', 'de nivel b1', 'de nivel b2', 'de nivel c1', 'de nivel c2',
        ]

        # If the question contains filter indicators, it's likely a refinement, not show field
        for indicator in filter_indicators:
            if indicator in question_lower:
                return (False, None)

        for pattern in show_patterns:
            match = re.search(pattern, question_lower)
            if match:
                requested_field = match.group(1).strip()
                # Only match if the captured part is SHORT (just the field name)
                # Long phrases like "los acuerdos con la facultad de derecho" are refinements
                if len(requested_field) > 30:
                    return (False, None)
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
            # Spanish
            'pais': 'destination_country',
            'país': 'destination_country',
            'universidad': 'host_institution',
            'nombre': 'host_institution',
            'institucion': 'host_institution',
            'institución': 'host_institution',
            'programa': 'mobility_program',
            'idioma': 'lang_1_name',
            'facultad': 'uma_faculties',
            'centro': 'uma_faculties',
            'alfabeticamente': 'host_institution',
            'alfabéticamente': 'host_institution',
            # English
            'country': 'destination_country',
            'university': 'host_institution',
            'name': 'host_institution',
            'institution': 'host_institution',
            'program': 'mobility_program',
            'language': 'lang_1_name',
            'faculty': 'uma_faculties',
            'school': 'uma_faculties',
            'alphabetically': 'host_institution',
            'alphabetical': 'host_institution',
        }

        # Patrones para detectar peticiones de ordenación
        sort_patterns = [
            # Spanish
            r'ordena(?:r|los|las|me)?\s+(?:por|según)?\s*(.+)',
            r'ordéna(?:me|los|las)?\s+(?:por|según)?\s*(.+)',
            r'clasifica(?:r|los|las)?\s+(?:por|según)?\s*(.+)',
            r'organiza(?:r|los|las)?\s+(?:por|según)?\s*(.+)',
            r'(?:de\s+)?(?:la\s+)?(?:a\s+a\s+la\s+)?z(?:\s+|$)',
            r'(?:de\s+)?(?:la\s+)?z\s+a\s+(?:la\s+)?a(?:\s+|$)',
            # English
            r'sort\s+(?:by|them\s+by)?\s*(.+)',
            r'order\s+(?:by|them\s+by)?\s*(.+)',
            r'arrange\s+(?:by|them\s+by)?\s*(.+)',
            r'organize\s+(?:by|them\s+by)?\s*(.+)',
            r'(?:from\s+)?a\s+to\s+z(?:\s+|$)',
            r'(?:from\s+)?z\s+to\s+a(?:\s+|$)',
        ]

        # Detectar dirección
        ascending = True
        if 'descend' in question_lower or 'z a a' in question_lower or 'mayor a menor' in question_lower or 'z to a' in question_lower:
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

        if not state['query_history'] and not state['last_sql_query'] and not state.get('operations_history'):
            return "📋 No query history yet."

        response_parts = ["### 📋 Query history\n"]

        # Build a combined timeline of queries and operations
        timeline = []

        # Add queries from history
        for i, entry in enumerate(state['query_history']):
            timeline.append({
                'type': 'query',
                'question': entry.get('question', ''),
                'sql': entry.get('sql', ''),
                'num_results': len(entry.get('results', [])),
                'query_index': i
            })

        # Add current query if exists
        current_query_index = len(state['query_history'])
        if state['last_sql_query']:
            timeline.append({
                'type': 'query',
                'question': state['last_user_question'] or '(current query)',
                'sql': state['last_sql_query'],
                'num_results': len(state['last_results']),
                'query_index': current_query_index
            })

        # Group operations by their parent query
        operations_by_query = {}
        for op in state.get('operations_history', []):
            q_idx = op.get('query_index', current_query_index)
            if q_idx not in operations_by_query:
                operations_by_query[q_idx] = []
            operations_by_query[q_idx].append(op)

        if not timeline and not operations_by_query:
            return "📋 No query history yet."

        # Display timeline with operations nested under their queries
        query_num = 0
        for entry in timeline:
            query_num += 1
            q_idx = entry['query_index']

            # Display query: number + bold question
            response_parts.append(f"#### {query_num}. {entry['question']}")
            response_parts.append(f"```sql\n{entry['sql']}\n```")
            response_parts.append(f"Results: {entry['num_results']}")

            # Display operations for this query (indented list)
            if q_idx in operations_by_query:
                for op in operations_by_query[q_idx]:
                    response_parts.append(f"- ↳ _{op['description']}_")

            response_parts.append("")

        response_parts.append("---")
        response_parts.append("💡 Say \"go back\" to restore a previous query.")

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

            response_parts = [f"⏪ **Going back to previous search**\n"]

            # Mostrar la pregunta original si existe
            if state['last_user_question']:
                response_parts.append(f"📝 *\"{state['last_user_question']}\"*\n")

            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

            if history_remaining > 0:
                response_parts.append(f"*({history_remaining} more search(es) in history)*\n")

            # Mostrar resumen de resultados
            if num_results > 20:
                response_parts.append(f"📊 **{num_results} results**\n")
                response_parts.append(f'💡 {self._make_clickable("Show me the results")}')
            else:
                response_parts.append(self._format_results_basic(state['last_results']))

            return "\n".join(response_parts)

        # Si no hay historial pero hay resultados actuales, re-mostrarlos
        if state['last_results']:
            state['last_display_offset'] = min(self.default_page_size, len(state['last_results']))
            num_results = len(state['last_results'])

            response_parts = [f"📋 **Returning to current results**\n"]

            # Mostrar la pregunta original si existe
            if state['last_user_question']:
                response_parts.append(f"📝 *\"{state['last_user_question']}\"*\n")

            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

            if num_results > 20:
                response_parts.append(f"📊 **{num_results} results**\n")
                response_parts.append(f'💡 {self._make_clickable("Show me the results")}')
            else:
                response_parts.append(self._format_results_basic(state['last_results']))

            return "\n".join(response_parts)

        return "⚠️ No previous searches in history."

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
            return "⚠️ No previous results. Please perform a search first."

        results = state['last_results']
        num_results = len(results)

        # Mapeo de nombres de campo a etiquetas legibles
        field_labels = {
            'uma_faculties': '🏫 UMA Faculty',
            'uma_degrees': '📚 Degrees',
            'mobility_program': '📋 Program',
            'lang_1_name': '🗣️ Language 1',
            'lang_1_level': '📊 Level 1',
            'lang_2_name': '🗣️ Language 2',
            'lang_2_level': '📊 Level 2',
            'student_vacancies': '🎓 Vacancies',
            'start_date': '📅 Start date',
            'end_date': '📅 End date',
            'destination_country': '🌍 Country',
            'host_institution': '🏛️ University',
            'destination_faculty': '🎯 Destination faculty',
            'available_levels': '📈 Levels',
        }

        # Campos que ya se muestran por defecto
        default_fields = {'host_institution', 'destination_country', 'mobility_program',
                         'student_vacancies', 'lang_1_name', 'lang_1_level'}

        label = field_labels.get(field_name, field_name)

        # Add operation to history and track shown fields
        if field_name not in default_fields:
            self._add_operation_to_history(session_id, 'show_field', f"Added field: {label}")
            state['shown_fields'].add(field_name)

        # Si el campo ya se muestra por defecto, indicarlo
        if field_name in default_fields:
            response_parts = [f"✅ **{num_results} result(s)** (field {label} already shown)\n"]
        else:
            response_parts = [f"✅ **{num_results} result(s)** - Adding: {label}\n"]

        # Mostrar la SQL de la consulta original
        if state['last_sql_query']:
            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

        # Mostrar máximo 20 resultados con información completa + campo adicional
        max_display = min(20, num_results)
        for i, r in enumerate(results[:max_display], 1):
            institution = r.get('host_institution', 'N/A')
            country = r.get('destination_country', 'N/A')
            program = r.get('mobility_program', 'N/A')

            response_parts.append(f"**{i}. 🏛️ {institution}**")
            response_parts.append(f"- **Country:** {country}")
            response_parts.append(f"- **Program:** {program}")

            # Plazas (resumido)
            vacancies = r.get('student_vacancies', 'N/A')
            if vacancies and vacancies != 'N/A':
                # Extraer solo el número de plazas si es posible
                import re
                match = re.search(r'Plazas:\s*(\d+)', str(vacancies))
                if match:
                    response_parts.append(f"- **Vacancies:** {match.group(1)}")
                else:
                    response_parts.append(f"- **Vacancies:** {str(vacancies)[:50]}...")

            # Idioma (resumido)
            lang = self._format_language_from_fields(r)
            if lang and lang != 'No requiere acreditación de idioma':
                if len(str(lang)) > 50:
                    lang = str(lang)[:50] + "..."
                response_parts.append(f"- **Language:** {lang}")

            # Campo adicional solicitado (si no es uno de los que ya mostramos)
            if field_name not in default_fields:
                # Manejar campos especiales que requieren formateo
                if field_name == 'available_levels':
                    field_value = self._format_available_levels(r)
                else:
                    field_value = r.get(field_name, 'N/A')
                if field_value and field_value != 'N/A' and field_value != 'No especificado':
                    # Truncar valores muy largos
                    if len(str(field_value)) > 100:
                        field_value = str(field_value)[:100] + "..."
                    response_parts.append(f"- **{label}:** {field_value}")

            response_parts.append("")

        if num_results > max_display:
            remaining = num_results - max_display
            response_parts.append(f"*... and {remaining} more agreement(s)*")

        response_parts.append("---")
        displayed_results = results[:max_display]
        # Check if faculty fields have been shown
        faculty_fields = {'uma_faculties', 'uma_degrees', 'destination_faculty'}
        faculty_shown = bool(state['shown_fields'] & faculty_fields)
        response_parts.append(self._generate_contextual_suggestions(displayed_results, has_more=(num_results > max_display), show_expand=True, faculty_shown=faculty_shown))

        return "\n".join(response_parts)

    def _handle_sort_results(self, session_id: str, sort_field: str, ascending: bool = True) -> str:
        """Ordena los resultados actuales por un campo específico."""
        state = self._get_session_state(session_id)

        if not state['last_results']:
            return "⚠️ No previous results. Please perform a search first."

        results = state['last_results'].copy()
        num_results = len(results)

        # Ordenar (in Python, SQL unchanged)
        try:
            results.sort(key=lambda x: str(x.get(sort_field, '')).lower(), reverse=not ascending)
            state['last_results'] = results
        except Exception as e:
            return f"⚠️ Could not sort by that field: {e}"

        # Mapeo de nombres de campo a etiquetas legibles
        field_labels = {
            'destination_country': 'country',
            'host_institution': 'university',
            'mobility_program': 'program',
            'lang_1_name': 'language',
            'uma_faculties': 'UMA faculty',
        }

        sort_label = field_labels.get(sort_field, sort_field)
        direction = "A→Z" if ascending else "Z→A"

        # Add operation to history
        self._add_operation_to_history(session_id, 'sort', f"Sorted by {sort_label} ({direction})")

        response_parts = [f"📊 **{num_results} result(s)** - Sorted by {sort_label} ({direction})\n"]

        # Mostrar la SQL original (sorting done in Python)
        if state['last_sql_query']:
            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

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
            response_parts.append(f"*... and {remaining} more agreement(s)*")
            response_parts.append(f'💡 {self._make_clickable("Show me the next 20")} | {self._make_clickable("Show me all")}')
        response_parts.append("---")
        displayed_results = results[:max_display]
        # Check if faculty fields have been shown
        faculty_fields = {'uma_faculties', 'uma_degrees', 'destination_faculty'}
        faculty_shown = bool(state.get('shown_fields', set()) & faculty_fields)
        response_parts.append(self._generate_contextual_suggestions(displayed_results, has_more=(num_results > max_display), show_expand=True, faculty_shown=faculty_shown))

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
            r"expand.*?(\d+)",
            r"detalle[s]?.*?(\d+)",
            r"m[aá]s info.*?(\d+)",
            r"info(?:rmaci[oó]n)?.*?(\d+)",
            r"(?:el|del|número|numero)\s*(\d+)(?!(?:er|do|ro|to|º))",  # Excluir ordinales
            r"acuerdo\s*(?:número|numero)?\s*(\d+)",
            r"convenio\s*(?:número|numero)?\s*(\d+)",
            r"#(\d+)",  # Solo el número y #
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
            return "⚠️ No previous results. Please perform a query first."

        # Si los resultados estaban agrupados, no se puede ampliar por número
        if state['last_results_grouped']:
            return ("⚠️ Results are grouped and cannot be expanded by number.\n\n"
                    "💡 To see details, refine your search by specifying the group you're interested in.\n"
                    "For example: *\"show me those from Germany\"* or *\"those from Berlin University\"*")

        if index < 1 or index > len(state['last_results']):
            return f"⚠️ Invalid number. Choose a number between 1 and {len(state['last_results'])}."

        r = state['last_results'][index - 1]

        # Add operation to history
        institution = r.get('host_institution', f'Item #{index}')
        self._add_operation_to_history(session_id, 'expand', f"Expanded details: {institution}")

        # Detectar si es una consulta de campos específicos (no tiene host_institution)
        if 'host_institution' not in r:
            # Mostrar solo los campos disponibles
            response_parts = [f"📋 **Detail #{index}**\n"]
            # Mostrar la SQL de la consulta original
            if state['last_sql_query']:
                response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")
            field_labels = {
                'uma_faculties': '🏫 UMA Faculty',
                'destination_country': '🌍 Country',
                'host_institution': '🏛️ University',
                'mobility_program': '📄 Program',
                'destination_faculty': '🎯 Destination Faculty',
                'uma_degrees': '📚 Degrees',
                'lang_1_name': '🗣️ Language 1',
                'lang_1_level': '📊 Level 1',
                'lang_2_name': '🗣️ Language 2',
                'lang_2_level': '📊 Level 2',
            }
            for field, value in r.items():
                if value:
                    label = field_labels.get(field, field.replace('_', ' ').title())
                    response_parts.append(f"**{label}:** {value}")
            response_parts.append("")
            response_parts.append("ℹ️ *To see complete agreements, perform a more specific search.*")
            return "\n".join(response_parts)

        response_parts = [f"📋 **Detalles del acuerdo #{index}**\n"]
        # Mostrar la SQL de la consulta original
        if state['last_sql_query']:
            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

        # Información principal
        response_parts.append(f"### 🏛️ {r.get('host_institution', 'N/A')}")
        response_parts.append(f"**Country:** {r.get('destination_country', 'N/A')}")
        response_parts.append(f"**Program:** {r.get('mobility_program', 'N/A')}")
        response_parts.append("")

        # Vigencia
        start = r.get('start_date', '')
        end = r.get('end_date', '')
        if start or end:
            response_parts.append(f"**📅 Vigencia:** {start} → {end}")

        # Plazas
        vacancies = r.get('student_vacancies', '')
        if vacancies:
            response_parts.append(f"**🎓 Vacancies:** {vacancies}")

        # Requisitos de idioma
        lang = self._format_language_from_fields(r)
        if lang and lang != 'No requiere acreditación de idioma':
            response_parts.append(f"**🗣️ Language:** {lang}")

        # Facultades UMA
        uma_fac = r.get('uma_faculties', '')
        if uma_fac:
            response_parts.append(f"**🏫 UMA Faculties:** {uma_fac}")

        # Titulaciones UMA
        uma_deg = r.get('uma_degrees', '')
        if uma_deg:
            response_parts.append(f"**📚 Degrees:** {uma_deg}")

        # Facultad destino
        dest_fac = r.get('destination_faculty', '')
        if dest_fac and dest_fac != 'General/No especificada':
            response_parts.append(f"**🎯 Destination faculty:** {dest_fac}")

        # Códigos ISCED
        isced = r.get('isced_codes', '')
        if isced:
            response_parts.append(f"**📊 Areas (ISCED):** {isced}")

        # Niveles disponibles
        levels = self._format_available_levels(r)
        if levels and levels != 'No especificado':
            response_parts.append(f"**📈 Levels:** {levels}")

        # Tutores
        tutors = r.get('tutors', '')
        if tutors:
            # Simplificar lista de tutores (puede ser muy larga)
            tutor_list = tutors.split('|')
            unique_tutors = list(set(t.strip() for t in tutor_list if t.strip()))[:3]
            response_parts.append(f"**👤 Coordinator(s):** {', '.join(unique_tutors)}")

        # Requisitos académicos
        acad_req = r.get('academic_requirements_text', '')
        if acad_req:
            response_parts.append(f"\n**📝 Academic requirements:**")
            response_parts.append(f"_{acad_req[:500]}{'...' if len(acad_req) > 500 else ''}_")

        # Comentarios públicos
        comments = r.get('public_comments', '')
        if comments:
            response_parts.append(f"\n**💬 Notes:**")
            response_parts.append(f"_{comments[:500]}{'...' if len(comments) > 500 else ''}_")

        return "\n".join(response_parts)

    def _handle_show_more(self, session_id: str, question: str) -> str:
        """Muestra más resultados de la última consulta."""
        state = self._get_session_state(session_id)

        if not state['last_results']:
            return "⚠️ No previous results. Please perform a query first."

        question_lower = question.lower()
        total = len(state['last_results'])

        # Detectar si quiere ver todos
        if "todos" in question_lower or "completa" in question_lower or "all" in question_lower:
            # Mostrar TODOS los resultados desde el principio
            state['last_display_offset'] = total
            # Add operation to history
            self._add_operation_to_history(session_id, 'show_more', f"Showed all {total} results")
            sql_display = ""
            if state['last_sql_query']:
                sql_display = f"```sql\n{state['last_sql_query']}\n```\n\n"
            return sql_display + self._format_results_basic(state['last_results'], max_display=total)

        # Detectar número específico (ej: "siguientes 30")
        import re
        num_match = re.search(r'(\d+)', question)
        page_size = int(num_match.group(1)) if num_match else self.default_page_size

        # Calcular siguiente página
        start = state['last_display_offset']
        end = min(start + page_size, total)

        if start >= total:
            return f"✅ All {total} results have been shown."

        # Obtener siguiente página
        next_page = state['last_results'][start:end]
        state['last_display_offset'] = end

        # Add operation to history
        self._add_operation_to_history(session_id, 'show_more', f"Showed results {start + 1} to {end} of {total}")

        remaining = total - end
        response_parts = [f"📄 **Mostrando resultados {start + 1} a {end} de {total}**\n"]

        # Mostrar la SQL de la consulta original
        if state['last_sql_query']:
            response_parts.append(f"```sql\n{state['last_sql_query']}\n```\n")

        for i, r in enumerate(next_page, start + 1):
            response_parts.append(f"### {i}. {r.get('host_institution', 'N/A')}")
            response_parts.append(f"- **Country:** {r.get('destination_country', 'N/A')}")
            response_parts.append(f"- **Program:** {r.get('mobility_program', 'N/A')}")
            response_parts.append(f"- **Vacancies:** {r.get('student_vacancies', 'N/A')}")
            response_parts.append(f"- **Language:** {self._format_language_from_fields(r)}")
            response_parts.append("")

        if remaining > 0:
            response_parts.append(f"*... {remaining} more agreement(s) remaining*")
        response_parts.append("---")
        # Check if faculty fields have been shown
        faculty_fields = {'uma_faculties', 'uma_degrees', 'destination_faculty'}
        faculty_shown = bool(state.get('shown_fields', set()) & faculty_fields)
        response_parts.append(self._generate_contextual_suggestions(next_page, has_more=(remaining > 0), show_expand=True, faculty_shown=faculty_shown))

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
            # Spanish - Referencias a resultados previos
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
            # English - References to previous results
            "of those", "from those", "of these", "from these", "of them", "from them",
            "the ones from", "only the", "only those", "just the", "just those",
            "only agreements", "only with", "show only",
            # Imperative (show me, give me)
            "show me the", "show me only", "show me just",
            "give me the", "give me only", "give me just",
            # Confirmation + refinement
            "yes,", "yes ", "yeah,", "yeah ",
            # Filters
            "filter by", "filter the", "filter those",
            "from the previous", "of the previous",
            "those that", "the ones that", "which have", "which require",
            # Add/change condition
            "but only", "but that", "and also", "that also",
            "with requirement", "without requirement",
            # Semesters and vacancies
            "first semester", "second semester", "1st semester", "2nd semester",
            "full year", "annual",
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
            # Buscar patrones como '%B1%' o = 'B1' (con o sin LIKE)
            if (f"'%{nivel}%'" in sql_upper or
                f'"%{nivel}%"' in sql_upper or
                f"= '{nivel}'" in sql_upper or
                f"='{nivel}'" in sql_upper):
                nivel_anterior = nivel
                break

        if not nivel_anterior or nivel_anterior == nivel_pedido:
            return previous_sql

        # 3. Sustituir el nivel en el SQL
        # Patrones a buscar y reemplazar (case insensitive)
        patrones_nivel = [
            (rf"'%{nivel_anterior}%'", f"'%{nivel_pedido}%'"),
            (rf'"%{nivel_anterior}%"', f'"%{nivel_pedido}%"'),
            (rf"= '{nivel_anterior}'", f"= '{nivel_pedido}'"),
            (rf"='{nivel_anterior}'", f"='{nivel_pedido}'"),
        ]

        sql_modificado = previous_sql
        for patron, reemplazo in patrones_nivel:
            sql_modificado = re.sub(patron, reemplazo, sql_modificado, flags=re.IGNORECASE)

        if sql_modificado != previous_sql:
            logger.info(f"🔄 Pre-procesamiento: Nivel {nivel_anterior}→{nivel_pedido} en SQL")
            logger.debug(f"   SQL original: {previous_sql}")
            logger.debug(f"   SQL modificado: {sql_modificado}")

        return sql_modificado

    def _fix_sql_operator_precedence(self, sql: str) -> str:
        """
        Fix SQL operator precedence when AND and OR are mixed without proper
        parentheses. This prevents bugs like:
            WHERE (A AND B) OR (C AND D) AND E
        Which should be:
            WHERE ((A AND B) OR (C AND D)) AND E

        Strategy: split WHERE at top-level OR to find OR-connected segments,
        then wrap the entire OR group in parentheses if there are also
        top-level AND conditions outside the OR group.
        """
        import re

        where_match = re.search(r'\bWHERE\s+(.*?)(?:\s+ORDER\s+|\s+GROUP\s+|\s+LIMIT\s+|\s*$)', sql, re.IGNORECASE | re.DOTALL)
        if not where_match:
            return sql

        where_clause = where_match.group(1).strip()

        # Find positions of top-level AND and OR operators
        depth = 0
        top_and_positions = []
        top_or_positions = []
        for i, ch in enumerate(where_clause):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif depth == 0:
                rest = where_clause[i:].upper()
                if rest.startswith('AND '):
                    top_and_positions.append(i)
                elif rest.startswith('OR '):
                    top_or_positions.append(i)

        if not top_and_positions or not top_or_positions:
            return sql  # No mixed operators — no fix needed

        # Find the span of the OR group: from the start of the first
        # OR-connected segment to the end of the last one.
        # The OR group starts at the beginning of the clause (or after the
        # last AND before the first OR) and ends at the last OR segment
        # (or before the first AND after the last OR).
        first_or = min(top_or_positions)
        last_or = max(top_or_positions)

        # Find the start of the OR group: look for the last top-level AND
        # before the first OR
        or_group_start = 0
        for pos in sorted(top_and_positions):
            if pos < first_or:
                or_group_start = pos + 4  # skip "AND "
                while or_group_start < len(where_clause) and where_clause[or_group_start] == ' ':
                    or_group_start += 1
            else:
                break

        # Find the end of the OR group: look for the first top-level AND
        # after the last OR
        or_group_end = len(where_clause)
        for pos in sorted(top_and_positions):
            if pos > last_or:
                # Back up to before the AND keyword (strip trailing space)
                or_group_end = pos
                while or_group_end > 0 and where_clause[or_group_end - 1] == ' ':
                    or_group_end -= 1
                break

        or_group = where_clause[or_group_start:or_group_end].strip()

        # Only wrap if the OR group doesn't already start+end with parens
        # covering the entire group
        if or_group.startswith('(') and or_group.endswith(')'):
            # Check if the outer parens cover the whole group
            d = 0
            covers_all = True
            for k, c in enumerate(or_group):
                if c == '(':
                    d += 1
                elif c == ')':
                    d -= 1
                if d == 0 and k < len(or_group) - 1:
                    covers_all = False
                    break
            if covers_all:
                return sql  # Already properly wrapped

        # Rebuild the WHERE clause with the OR group wrapped
        before = where_clause[:or_group_start].strip()
        after = where_clause[or_group_end:].strip()

        parts = []
        if before:
            # Remove trailing AND
            if before.upper().endswith(' AND'):
                before = before[:-4].strip()
            elif before.upper().endswith('AND'):
                before = before[:-3].strip()
            if before:
                parts.append(before)
        parts.append(f'({or_group})')
        if after:
            # Remove leading AND
            if after.upper().startswith('AND '):
                after = after[4:].strip()
            if after:
                parts.append(after)

        new_where = ' AND '.join(parts)

        if new_where != where_clause:
            sql = sql[:where_match.start(1)] + new_where + sql[where_match.end(1):]
            logger.info(f"🔧 Fixed operator precedence: wrapped OR group in parentheses")

        return sql

    def _postprocess_level_substitution(self, question: str, generated_sql: str, previous_sql: str) -> str:
        """
        Post-procesa el SQL generado para forzar la sustitución de niveles de idioma.

        Las LLMs tienden a ignorar las instrucciones de sustituir niveles (B1→B2) y
        mantienen el nivel anterior. Esta función fuerza la sustitución DESPUÉS de
        que la LLM genere el SQL.

        Args:
            question: La pregunta del usuario
            generated_sql: El SQL generado por la LLM
            previous_sql: El SQL de la consulta anterior

        Returns:
            El SQL con el nivel corregido si aplica
        """
        import re

        if not previous_sql or not generated_sql:
            return generated_sql

        question_upper = question.upper()

        # Niveles de idioma
        niveles = ["B1", "B2", "A1", "A2", "C1", "C2"]

        # 1. Detectar si el usuario está pidiendo un nivel específico
        nivel_pedido = None
        for nivel in niveles:
            if re.search(rf'\b{nivel}\b', question_upper):
                nivel_pedido = nivel
                break

        if not nivel_pedido:
            return generated_sql

        # 2. Detectar si el SQL anterior tenía un nivel diferente
        sql_anterior_upper = previous_sql.upper()
        nivel_anterior = None
        for nivel in niveles:
            if f"= '{nivel}'" in sql_anterior_upper or f"='{nivel}'" in sql_anterior_upper:
                nivel_anterior = nivel
                break

        if not nivel_anterior or nivel_anterior == nivel_pedido:
            return generated_sql

        # 3. Verificar si el SQL generado todavía contiene el nivel anterior
        generated_upper = generated_sql.upper()
        sql_corregido = generated_sql
        cambios = False

        if f"= '{nivel_anterior}'" in generated_upper or f"='{nivel_anterior}'" in generated_upper:
            # Forzar la sustitución del nivel
            patrones = [
                (rf"= '{nivel_anterior}'", f"= '{nivel_pedido}'"),
                (rf"='{nivel_anterior}'", f"='{nivel_pedido}'"),
            ]

            for patron, reemplazo in patrones:
                sql_corregido = re.sub(patron, reemplazo, sql_corregido, flags=re.IGNORECASE)

            if sql_corregido != generated_sql:
                cambios = True

        # 4. Eliminar cláusulas NOT IN que excluyan el nivel pedido
        # Buscar "AND NOT (" y eliminar hasta el paréntesis de cierre balanceado
        match_and_not = re.search(r'\s*AND\s+NOT\s*\(', sql_corregido, flags=re.IGNORECASE)
        if match_and_not:
            start_idx = match_and_not.start()
            paren_start = match_and_not.end() - 1  # Posición del '('
            # Contar paréntesis para encontrar el cierre balanceado
            count = 1
            end_idx = paren_start + 1
            while end_idx < len(sql_corregido) and count > 0:
                if sql_corregido[end_idx] == '(':
                    count += 1
                elif sql_corregido[end_idx] == ')':
                    count -= 1
                end_idx += 1
            if count == 0:
                clausula_not = sql_corregido[start_idx:end_idx]
                # Solo eliminar si contiene el nivel pedido
                if nivel_pedido in clausula_not.upper():
                    sql_nuevo = sql_corregido[:start_idx] + sql_corregido[end_idx:]
                    if sql_nuevo != sql_corregido:
                        sql_corregido = sql_nuevo
                        cambios = True
                        logger.info(f"🔄 Post-procesamiento: Eliminada cláusula NOT IN que excluía {nivel_pedido}")

        if cambios:
            logger.info(f"🔄 Post-procesamiento: Forzado nivel {nivel_anterior}→{nivel_pedido} en SQL generado")
            return sql_corregido

        return generated_sql

    def _postprocess_country_substitution(self, question: str, generated_sql: str, previous_sql: str) -> str:
        """
        Post-procesa el SQL generado para forzar la sustitución de país/región.

        Cuando el usuario pide "los de Asia" después de buscar en "Alemania", la LLM
        tiende a AÑADIR Asia en vez de SUSTITUIR Alemania. Esta función detecta y
        corrige estos casos.

        Args:
            question: La pregunta del usuario
            generated_sql: El SQL generado por la LLM
            previous_sql: El SQL de la consulta anterior

        Returns:
            El SQL con el país/región corregido si aplica
        """
        import re

        if not previous_sql or not generated_sql:
            return generated_sql

        question_lower = question.lower()

        # Regiones que indican sustitución
        regiones = ['asia', 'europa', 'américa latina', 'america latina', 'latinoamérica',
                    'latinoamerica', 'áfrica', 'africa', 'oceanía', 'oceania',
                    'países nórdicos', 'paises nordicos', 'europa del este']

        # Detectar si el usuario pide una REGIÓN o un PAÍS diferente
        # Patrones que indican sustitución (no ampliación)
        patrones_sustitucion = [
            r'(?:los|las|muéstrame|muestrame|ver|dame)\s+(?:los\s+)?(?:de\s+)?(\w+)',
            r'(?:cambiar?|cambia)\s+a\s+(\w+)',
            r'(?:mejor|prefiero)\s+(?:los\s+de\s+)?(\w+)',
            r'^(?:los\s+de\s+)?(\w+)$',  # Solo el nombre de una región/país
        ]

        region_pedida = None
        for patron in patrones_sustitucion:
            match = re.search(patron, question_lower)
            if match:
                candidato = match.group(1).lower()
                # Verificar si es una región conocida
                for region in regiones:
                    if candidato in region or region.startswith(candidato):
                        region_pedida = candidato
                        break
                if region_pedida:
                    break

        if not region_pedida:
            return generated_sql

        # Detectar si el SQL anterior tenía un país específico
        # Buscar patrones como: destination_country LIKE '%Alemania%'
        pais_anterior_match = re.search(
            r"destination_country\s+LIKE\s+'%([^%]+)%'",
            previous_sql,
            re.IGNORECASE
        )

        if not pais_anterior_match:
            return generated_sql

        pais_anterior = pais_anterior_match.group(1)

        # Verificar si el SQL generado todavía contiene el país anterior
        if pais_anterior.lower() in generated_sql.lower():
            # El SQL tiene AMBOS: el país anterior y la nueva región
            # Necesitamos eliminar la referencia al país anterior

            # Patrones para eliminar el país anterior
            patrones_eliminar = [
                # destination_country LIKE '%Alemania%' AND
                rf"destination_country\s+LIKE\s+'%{re.escape(pais_anterior)}%'\s+AND\s+",
                # AND destination_country LIKE '%Alemania%'
                rf"\s+AND\s+destination_country\s+LIKE\s+'%{re.escape(pais_anterior)}%'",
            ]

            sql_corregido = generated_sql
            for patron in patrones_eliminar:
                sql_corregido = re.sub(patron, " ", sql_corregido, flags=re.IGNORECASE)

            # Limpiar espacios múltiples y WHERE AND
            sql_corregido = re.sub(r'\s+', ' ', sql_corregido)
            sql_corregido = re.sub(r'WHERE\s+AND', 'WHERE', sql_corregido, flags=re.IGNORECASE)
            sql_corregido = sql_corregido.strip()

            if sql_corregido != generated_sql:
                logger.info(f"🔄 Post-procesamiento: Eliminado país anterior '{pais_anterior}' (sustitución por región)")
                return sql_corregido

        return generated_sql

    def _postprocess_preserve_conditions(self, question: str, generated_sql: str, previous_sql: str) -> str:
        """
        Post-procesa el SQL generado para preservar condiciones del SQL anterior
        que no deberían haberse perdido.

        Cuando el usuario añade un filtro (ej: "solo los de Derecho"), la LLM
        a veces genera un SQL que pierde condiciones anteriores (ej: pierde Alemania).
        Esta función detecta y corrige esos casos.

        Args:
            question: La pregunta del usuario
            generated_sql: El SQL generado por la LLM
            previous_sql: El SQL de la consulta anterior

        Returns:
            El SQL con las condiciones preservadas si aplica
        """
        import re

        if not previous_sql or not generated_sql:
            return generated_sql

        question_lower = question.lower()

        # Patrones que indican AÑADIR filtro (no sustituir)
        # Estos patrones sugieren que el usuario quiere filtrar más, no cambiar
        patrones_anadir = [
            r'^solo\s+los',  # "solo los de Derecho"
            r'^solo\s+las',
            r'^los\s+de\s+(?:la\s+)?(?:facultad|medicina|derecho|ciencias|ingeniería)',
            r'^las\s+de\s+(?:la\s+)?(?:facultad|medicina|derecho|ciencias|ingeniería)',
            r'^de\s+(?:la\s+)?(?:facultad|medicina|derecho|ciencias)',
            r'^(?:y\s+)?que\s+(?:tengan|requieran|pidan)',
            r'^(?:y\s+)?los\s+del\s+primer',
            r'^(?:y\s+)?los\s+del\s+segundo',
            r'^(?:y\s+)?del\s+primer\s+cuatrimestre',
            r'^(?:y\s+)?del\s+segundo\s+cuatrimestre',
            r'^(?:y\s+)?solo\s+(?:los\s+)?del',
            r'^(?:y\s+)?que\s+no\s+requieran',
            r'^filtra',
        ]

        es_filtro_anadir = False
        for patron in patrones_anadir:
            if re.search(patron, question_lower):
                es_filtro_anadir = True
                break

        if not es_filtro_anadir:
            return generated_sql

        # Extraer condiciones clave del SQL anterior
        condiciones_a_preservar = []

        # 1. Condición de país (destination_country)
        pais_match = re.search(
            r"(destination_country\s+(?:LIKE\s+'%[^%]+%'|IN\s*\([^)]+\)))",
            previous_sql,
            re.IGNORECASE
        )
        if pais_match:
            condicion_pais = pais_match.group(1)
            # Verificar si el SQL generado tiene esta condición
            if 'destination_country' not in generated_sql.upper():
                condiciones_a_preservar.append(condicion_pais)
                logger.info(f"🔄 Preservando condición de país: {condicion_pais[:50]}...")

        # 2. Condición de facultad (uma_faculties)
        facultad_match = re.search(
            r"(uma_faculties\s+LIKE\s+'%[^%]+%')",
            previous_sql,
            re.IGNORECASE
        )
        if facultad_match:
            condicion_facultad = facultad_match.group(1)
            # Verificar si el SQL generado tiene esta condición
            if 'uma_faculties' not in generated_sql.upper():
                condiciones_a_preservar.append(condicion_facultad)
                logger.info(f"🔄 Preservando condición de facultad: {condicion_facultad[:50]}...")

        # 3. Condición de idioma (lang_1_name o lang_2_name)
        idioma_match = re.search(
            r"(\(?\s*(?:lang_1_name|lang_2_name)\s+LIKE\s+'%[^%]+%'(?:\s+(?:AND|OR)\s+(?:lang_1_name|lang_2_name)\s+LIKE\s+'%[^%]+%')?\s*\)?)",
            previous_sql,
            re.IGNORECASE
        )
        if idioma_match:
            condicion_idioma = idioma_match.group(1)
            # Verificar si el SQL generado tiene condición de idioma
            if 'lang_1_name' not in generated_sql.upper() and 'lang_2_name' not in generated_sql.upper():
                condiciones_a_preservar.append(condicion_idioma)
                logger.info(f"🔄 Preservando condición de idioma: {condicion_idioma[:50]}...")

        # Si no hay condiciones a preservar, devolver el SQL original
        if not condiciones_a_preservar:
            return generated_sql

        # Añadir las condiciones al SQL generado
        # Buscar el WHERE en el SQL generado
        where_match = re.search(r'\bWHERE\b(.+?)(?:ORDER BY|GROUP BY|LIMIT|$)', generated_sql, re.IGNORECASE | re.DOTALL)

        if where_match:
            # Ya tiene WHERE, añadir con AND
            where_clause = where_match.group(1).strip()
            nuevas_condiciones = " AND ".join(condiciones_a_preservar)

            # Insertar las condiciones preservadas al principio del WHERE
            nuevo_where = f"WHERE {nuevas_condiciones} AND {where_clause}"
            sql_corregido = re.sub(
                r'\bWHERE\b.+?(?=ORDER BY|GROUP BY|LIMIT|$)',
                nuevo_where + " ",
                generated_sql,
                flags=re.IGNORECASE | re.DOTALL
            )
        else:
            # No tiene WHERE (raro, pero posible)
            nuevas_condiciones = " AND ".join(condiciones_a_preservar)
            # Insertar WHERE antes de ORDER BY, GROUP BY, LIMIT o al final
            if re.search(r'\b(ORDER BY|GROUP BY|LIMIT)\b', generated_sql, re.IGNORECASE):
                sql_corregido = re.sub(
                    r'\b(ORDER BY|GROUP BY|LIMIT)\b',
                    f"WHERE {nuevas_condiciones} \\1",
                    generated_sql,
                    count=1,
                    flags=re.IGNORECASE
                )
            else:
                sql_corregido = generated_sql.rstrip() + f" WHERE {nuevas_condiciones}"

        # Limpiar espacios múltiples
        sql_corregido = re.sub(r'\s+', ' ', sql_corregido).strip()

        if sql_corregido != generated_sql:
            logger.info(f"🔧 Condiciones preservadas añadidas al SQL")

        return sql_corregido

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
            return "ERROR: Database not found at data/database.db"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = cursor.fetchall()

            if not tables:
                conn.close()
                return "The database is empty (no tables found)."

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
                    schema_parts.append("- lang_1_name, lang_1_level: primer idioma y nivel requerido")
                    schema_parts.append("- lang_2_name, lang_2_level: segundo idioma y nivel (si aplica)")
                    schema_parts.append("- allows_undergraduate, allows_master, allows_phd: niveles académicos permitidos")
                    schema_parts.append("- min_gpa_requirement: nota media mínima requerida")
                    schema_parts.append("- student_vacancies: plazas disponibles")

            conn.close()
            self._cached_schema = "\n".join(schema_parts)
            logger.info("📄 Esquema compacto generado desde la BD (cacheado)")
            return self._cached_schema

        except sqlite3.Error as e:
            return f"Error leyendo esquema: {str(e)}"

    @staticmethod
    def _ensure_default_order(sql: str) -> str:
        """Append ORDER BY host_institution when a SELECT on 'destinations'
        has no ORDER BY clause.  This ensures results are grouped by
        university by default."""
        import re as _re
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return sql
        if "ORDER BY" in sql_upper:
            return sql  # already has an ORDER BY
        if "DESTINATIONS" not in sql_upper:
            return sql  # not querying destinations table
        # Append ORDER BY before any trailing semicolon
        sql_stripped = sql.rstrip().rstrip(";")
        return sql_stripped + " ORDER BY host_institution"

    def _text_to_sql(self, user_question: str, schema: str, previous_sql: str = None) -> str:
        """Usa Ollama con qwen2.5-coder para convertir preguntas a SQL."""
        # Normalizar países y otros términos antes de procesar
        normalized_question = normalize_text_for_search(user_question)
        if normalized_question != user_question:
            logger.info(f"🌍 Pregunta normalizada: '{user_question}' → '{normalized_question}'")

        # Detectar si es un refinamiento
        is_refinement = previous_sql is not None
        original_previous_sql = previous_sql  # Guardar el SQL original ANTES de preprocesamiento
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
  * lang_1_name: nombre del primer idioma requerido en MAYÚSCULAS (ej: "INGLÉS", "FRANCÉS", "ALEMÁN"). NULL si no requiere idioma
  * lang_1_level: nivel del primer idioma (ej: "B1", "B2", "C1")
  * lang_2_name: nombre del segundo idioma si lo hay. NULL si no hay segundo idioma
  * lang_2_level: nivel del segundo idioma
  * allows_undergraduate: "Sí" o "No" - si permite estudiantes de Grado
  * allows_master: "Sí" o "No" - si permite estudiantes de Máster
  * allows_phd: "Sí" o "No" - si permite estudiantes de Doctorado
  * min_gpa_requirement: nota media mínima requerida (REAL). NULL si no hay requisito
  * student_vacancies: plazas disponibles

REGLAS:
- Usa LIKE '%texto%' para búsquedas de texto (no =)
- Solo genera SELECT (nunca INSERT, UPDATE, DELETE)
- COUNT(*) solo para contar CONVENIOS/ACUERDOS ("cuántos convenios", "número de acuerdos")
- PLAZAS y CUATRIMESTRES: student_vacancies es TEXTO con formato "[Grado] Plazas: 4, Periodos permitidos: 1er CUATRIMESTRE"
  * Para filtrar por cuatrimestre: WHERE student_vacancies LIKE '%1er CUATRIMESTRE%' o '%2do CUATRIMESTRE%' o '%ANUAL%'
  * NO uses SUM() con student_vacancies (es texto). Usa COUNT(*) para contar destinos o SELECT student_vacancies para ver detalles
- REQUISITOS DE IDIOMA: Usa los campos lang_1_name, lang_1_level, lang_2_name, lang_2_level
  * Sin requisito de idioma: WHERE lang_1_name IS NULL
  * Buscar idioma específico: WHERE lang_1_name LIKE '%INGLÉS%' OR lang_2_name LIKE '%INGLÉS%'
  * Buscar idioma Y nivel: WHERE (lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B2')
  * SOLO nivel B1 (sin niveles superiores): WHERE ((lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B1')) AND NOT ((lang_1_level IN ('B2','C1','C2')) OR (lang_2_level IN ('B2','C1','C2')))
- NIVELES ACADÉMICOS:
  * Solo Grado: WHERE allows_undergraduate = 'Sí'
  * Solo Máster: WHERE allows_master = 'Sí'
  * Solo Doctorado: WHERE allows_phd = 'Sí'
- NOTA MEDIA MÍNIMA:
  * Con requisito de nota: WHERE min_gpa_requirement IS NOT NULL
  * Nota específica: WHERE min_gpa_requirement >= 7.0
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
- REDES DE UNIVERSIDADES: Para "UNINOVIS" usa host_institution LIKE '%UNINOVIS%' (el sistema lo expandirá a las universidades de la red: USPN, UDCLV, KK, UT, THWS, TAMK, THUAS)
- INTERPRETACIÓN SEMÁNTICA IMPORTANTE:
  * "¿Qué nivel de INGLÉS necesito para X?" → FILTRAR por lang_1_name o lang_2_name LIKE '%INGLÉS%' (devolver solo los que piden inglés)
  * "plazas disponibles" o "destinos con plazas" → EXCLUIR plazas vacías: WHERE student_vacancies NOT LIKE '%Plazas: 0%'
  * "¿Con qué PAÍSES tiene convenios X?" → usar SELECT DISTINCT destination_country para evitar duplicados

EJEMPLOS:
- "¿Qué acuerdos hay con The Hague University of Applied Sciences?" → SELECT * FROM destinations WHERE host_institution LIKE '%The Hague%'
- "¿Cuántos acuerdos hay con Alemania?" → SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Alemania%'
- "¿Hay convenios con Italia?" → SELECT * FROM destinations WHERE destination_country LIKE '%Italia%'
- "¿Qué nivel de inglés necesito para ir a Alemania?" → SELECT lang_1_name, lang_1_level, lang_2_name, lang_2_level FROM destinations WHERE destination_country LIKE '%Alemania%' AND (lang_1_name LIKE '%INGLÉS%' OR lang_2_name LIKE '%INGLÉS%')
- "¿Qué universidades hay en Francia?" → SELECT * FROM destinations WHERE destination_country LIKE '%Francia%'
- "¿Qué destinos hay con ERASMUS+ KA131?" → SELECT * FROM destinations WHERE mobility_program LIKE '%ERASMUS+ KA131%'
- "¿Qué programas de movilidad hay?" → SELECT DISTINCT mobility_program FROM destinations
- "¿Cuántas plazas hay para el primer cuatrimestre?" → SELECT COUNT(*) FROM destinations WHERE student_vacancies LIKE '%1er CUATRIMESTRE%'
- "¿Qué destinos hay para el segundo cuatrimestre?" → SELECT * FROM destinations WHERE student_vacancies LIKE '%2do CUATRIMESTRE%'
- "¿Qué plazas hay en Italia?" → SELECT * FROM destinations WHERE destination_country LIKE '%Italia%'
- "¿Qué destinos no requieren idioma?" → SELECT * FROM destinations WHERE lang_1_name IS NULL
- "¿Qué destinos requieren inglés B2?" → SELECT * FROM destinations WHERE (lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B2') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B2')
- "¿Hay convenios con requisito de Inglés B1?" → SELECT * FROM destinations WHERE (lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B1')
- "¿Cuántos destinos hay en América Latina?" → SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%América Latina%'
- "¿Qué universidades hay en Europa?" → SELECT * FROM destinations WHERE destination_country LIKE '%Europa%'
- "¿Cuántos convenios hay en Asia?" → SELECT COUNT(*) FROM destinations WHERE destination_country LIKE '%Asia%'
- "¿Qué destinos tienen plazas disponibles?" → SELECT * FROM destinations WHERE student_vacancies NOT LIKE '%Plazas: 0%'
- "¿Con qué países tiene convenios la Facultad de Medicina?" → SELECT DISTINCT destination_country FROM destinations WHERE uma_faculties LIKE '%Medicina%'
- "¿Qué facultades tienen convenios con universidades de Africa?" → SELECT * FROM destinations WHERE destination_country LIKE '%Africa%'
- "¿Qué facultades tienen acuerdos con Alemania?" → SELECT * FROM destinations WHERE destination_country LIKE '%Alemania%'
- "¿Hay convenios con universidades UNINOVIS?" → SELECT * FROM destinations WHERE host_institution LIKE '%UNINOVIS%'
- "What agreements do we have with UNINOVIS members?" → SELECT * FROM destinations WHERE host_institution LIKE '%UNINOVIS%'
- "¿Hay destinos para estudiantes de Máster?" → SELECT * FROM destinations WHERE allows_master = 'Sí'
- "¿Qué destinos exigen nota media mínima?" → SELECT * FROM destinations WHERE min_gpa_requirement IS NOT NULL

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
- "los que requieran inglés" → AÑADIR filtro de idioma (lang_1_name/lang_2_name), CONSERVAR destination_country
- "solo nivel B1" → AÑADIR nivel (lang_1_level/lang_2_level = 'B1'), CONSERVAR destination_country e idioma
- "del primer cuatrimestre" → AÑADIR student_vacancies, CONSERVAR TODO lo anterior

CUÁNDO SUSTITUIR (mantener el resto):
- País/Región: "los de Asia" → sustituir destination_country, CONSERVAR filtros de idioma
- Nivel: "los de B2" → sustituir el nivel (lang_X_level = 'B1' → lang_X_level = 'B2'), CONSERVAR destination_country e idioma
- Universidad: "los de Sorbonne" → sustituir host_institution, CONSERVAR todo lo demás

IMPORTANTE - PAÍSES Y REGIONES:
- REGIONES PRINCIPALES: Europa, Asia, América Latina, Latinoamérica, África, Oceanía
- SUBREGIONES: países escandinavos, países nórdicos, Europa del Este, países de habla alemana, países de habla inglesa, países mediterráneos, Benelux
- Si el usuario pide una REGIÓN o PAÍS diferente al actual → SUSTITUYE destination_country
- Ejemplo: SQL anterior con "Alemania", usuario dice "los de Asia" → destination_country LIKE '%Asia%'
- Ejemplo: SQL anterior con "Italia", usuario dice "los de Francia" → destination_country LIKE '%Francia%'
- Para regiones usa LIKE y el sistema las expandirá: destination_country LIKE '%países escandinavos%'

IMPORTANTE PARA IDIOMAS Y NIVELES:
- Campos de idioma: lang_1_name, lang_1_level, lang_2_name, lang_2_level
- NIVELES: A1, A2, B1, B2, C1, C2
- Si ya hay un NIVEL (B1) y el usuario pide OTRO NIVEL (B2) → SUSTITUIR el nivel
- Si ya hay filtro de idioma y el usuario pide "nivel B1" (sin nivel previo) → AÑADIR lang_X_level = 'B1'
- Si ya hay lang_X_level = 'B1' y el usuario pide "nivel B2" → SUSTITUIR B1 por B2

EJEMPLOS CORRECTOS:

🔴 CASO CRÍTICO - AÑADIR IDIOMA CONSERVANDO PAÍS:
- Anterior: "WHERE destination_country LIKE '%Alemania%'"
  Usuario: "los que requieran inglés" → AÑADIR idioma, CONSERVAR país:
  WHERE destination_country LIKE '%Alemania%' AND (lang_1_name LIKE '%INGLÉS%' OR lang_2_name LIKE '%INGLÉS%')
  ❌ INCORRECTO: WHERE lang_1_name LIKE '%INGLÉS%' (perdió Alemania!)

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND (lang_1_name LIKE '%INGLÉS%' OR lang_2_name LIKE '%INGLÉS%')"
  Usuario: "solo nivel B1" → AÑADIR B1, CONSERVAR Alemania e INGLÉS:
  WHERE destination_country LIKE '%Alemania%' AND ((lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B1'))
  ❌ INCORRECTO: WHERE lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1' (perdió Alemania!)

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND lang_1_name LIKE '%INGLÉS%'"
  Usuario: "los de Asia" → SUSTITUIR país por región:
  WHERE destination_country LIKE '%Asia%' AND lang_1_name LIKE '%INGLÉS%'

- Anterior: "WHERE destination_country LIKE '%Italia%'"
  Usuario: "mejor los de Turquía" → SUSTITUIR país:
  WHERE destination_country LIKE '%Turquía%'

- Anterior: "WHERE lang_1_level = 'B1'"
  Usuario: "los de Alemania" → AÑADIR país (no había filtro de país):
  WHERE lang_1_level = 'B1' AND destination_country LIKE '%Alemania%'

- Anterior: "WHERE destination_country LIKE '%Alemania%' AND lang_1_name LIKE '%INGLÉS%'"
  Usuario: "solo primer cuatrimestre" → AÑADIR cuatrimestre:
  WHERE destination_country LIKE '%Alemania%' AND lang_1_name LIKE '%INGLÉS%' AND student_vacancies LIKE '%1er CUATRIMESTRE%'

🔴 CASO CRÍTICO - AÑADIR PAÍS A CONDICIONES DE IDIOMA CON OR:
- Anterior: "WHERE (lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B1')"
  Usuario: "los de Chile" → AÑADIR país, CONSERVAR condiciones de idioma:
  WHERE destination_country LIKE '%Chile%' AND ((lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B1'))
  ❌ INCORRECTO: WHERE (lang_1_name LIKE '%INGLÉS%' AND lang_1_level = 'B1') OR (lang_2_name LIKE '%INGLÉS%' AND lang_2_level = 'B1') AND destination_country LIKE '%Chile%'
  ⚠️ SIN PARÉNTESIS el AND solo aplica al segundo OR, devolviendo resultados incorrectos

⚠️ REGLA DE PRECEDENCIA DE OPERADORES:
- AND tiene mayor precedencia que OR en SQL
- Cuando mezcles AND con OR, SIEMPRE usa paréntesis para claridad
- Envuelve los grupos OR en paréntesis antes de combinarlos con AND
- Ejemplo: WHERE country = 'Chile' AND (lang_1 = 'EN' OR lang_2 = 'EN')
- NUNCA: WHERE country = 'Chile' AND lang_1 = 'EN' OR lang_2 = 'EN' (ambiguo!)

🔴 MÁS EJEMPLOS DE AÑADIR (NUNCA PERDER CONDICIONES):
- Anterior: "WHERE destination_country LIKE '%Italia%'"
  Usuario: "que requieran francés" → AÑADIR idioma:
  WHERE destination_country LIKE '%Italia%' AND (lang_1_name LIKE '%Francés%' OR lang_2_name LIKE '%Francés%')

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

        # Corregir precedencia de operadores AND/OR
        sql = self._fix_sql_operator_precedence(sql)

        # Post-procesar sustituciones si es un refinamiento
        if is_refinement and original_previous_sql:
            # Forzar sustitución de nivel (B1→B2) si la LLM no lo hizo
            # Usamos original_previous_sql (antes de preprocesamiento) para detectar el nivel anterior
            sql = self._postprocess_level_substitution(normalized_question, sql, original_previous_sql)
            # Forzar sustitución de país/región si la LLM añadió en vez de sustituir
            sql = self._postprocess_country_substitution(normalized_question, sql, previous_sql)
            # Preservar condiciones del SQL anterior que se perdieron incorrectamente
            sql = self._postprocess_preserve_conditions(user_question, sql, previous_sql)

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
        return "ERROR: Could not generate valid SQL"

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
            'nórdicos': NORDIC_COUNTRIES,  # Sin "países"
            'Nórdicos': NORDIC_COUNTRIES,  # Sin "países", capitalizado
            'nordicos': NORDIC_COUNTRIES,  # Sin "países" ni tildes
            'escandinavos': NORDIC_COUNTRIES,  # Sin "países"
            'Escandinavos': NORDIC_COUNTRIES,  # Sin "países", capitalizado
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
        # Acronyms <=4 chars use exact match to avoid false positives
        UNIVERSITY_NETWORKS = {
            'UNINOVIS': [
                ['Sorbonne Paris Nord', 'USPN'],                    # France - University of Sorbonne Paris Nord
                ['Campania', 'Vanvitelli', 'UDCLV'],                # Italy - University of Campania "Luigi Vanvitelli"
                ['Kauno Kolegija', 'KK'],                           # Lithuania - Kauno Kolegija Higher Education Institution
                ['University of Tirana', 'UNIVERSITY OF TIRANA', 'UT'],  # Albania - University of Tirana
                ['Würzburg-Schweinfurt', 'THWS'],                   # Germany - Technical University of Applied Sciences
                ['Tampere University of Applied', 'TAMK'],          # Finland - Tampere University of Applied Sciences
                ['Hague University', 'THUAS'],                      # Netherlands - The Hague University of Applied Sciences
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
            'lang_1_name': ['host_institution', 'destination_country'],
            'lang_1_level': ['host_institution', 'destination_country'],
            'lang_2_name': ['host_institution', 'destination_country'],
            'lang_2_level': ['host_institution', 'destination_country'],
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
                    f"((lang_1_name LIKE '%{context['idioma']}%' AND lang_1_level = '{context['nivel']}') OR (lang_2_name LIKE '%{context['idioma']}%' AND lang_2_level = '{context['nivel']}'))"
                ))
            else:
                criterios.append((
                    f"Idioma: {context['idioma']}",
                    f"(lang_1_name LIKE '%{context['idioma']}%' OR lang_2_name LIKE '%{context['idioma']}%')"
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
        msg = f"🔍 **No agreements found** with {search_desc}.\n\n"

        # Análisis detallado si hay más de 1 condición
        if len(condiciones) > 1:
            analisis = self._analyze_search_criteria(context)
            if analisis:
                msg += "📊 **Criteria analysis:**\n\n"

                # Cabecera de tabla (con o sin columna de plazas)
                if filtrar_plazas:
                    msg += "| Criterion | Agreements | With vacancies |\n"
                    msg += "|-----------|----------:|---------------:|\n"
                else:
                    msg += "| Criterion | Agreements |\n"
                    msg += "|-----------|----------:|\n"

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
                    msg += f"⚠️ **Criterion with no matches in DB:** {', '.join(criterios_sin_resultados)}\n"
                    msg += "There are no agreements with this requirement in the entire database.\n\n"
                elif len(criterios_con_resultados) > 1:
                    # Todos los criterios individuales existen
                    # Analizar qué combinaciones de pares fallan
                    combos_ok = [(d, c) for d, c, _ in combos_2 if c > 0]
                    combos_fail = [(d, c) for d, c, _ in combos_2 if c == 0]

                    if combos_fail and combos_ok:
                        # Algunas combinaciones de pares funcionan, otras no
                        msg += f"⚠️ **Failing combinations:**\n"
                        for desc, _ in combos_fail:
                            msg += f"  • {desc}: no agreements with both criteria\n"
                        msg += "\n"
                    elif combos_fail and not combos_ok:
                        # Todas las combinaciones de pares fallan
                        msg += f"⚠️ **No combination of criteria has results**\n"
                        msg += f"There are agreements with each criterion separately:\n"
                        for nombre, cantidad in criterios_con_resultados:
                            msg += f"  • {nombre}: {cantidad} agreements\n"
                        msg += f"But there are no agreements that meet two criteria at once.\n\n"
                    elif combos_ok and combo_total and combo_total[0][1] == 0:
                        # Algunas combinaciones de pares funcionan, pero la combinación total falla
                        msg += f"⚠️ **No agreements meet all 3 criteria at once**\n"
                        msg += f"Partial combinations that do exist:\n"
                        for desc, count in combos_ok:
                            msg += f"  • {desc}: {count} agreements\n"
                        msg += "\n"

        # Sugerencias basadas en el contexto
        msg += "💡 **Suggestions:**\n"
        suggestions = []

        if context["idioma"] and context["nivel"]:
            suggestions.append(f"- Search for agreements with {context['idioma']} without filtering by level")
            suggestions.append(f"- Try another level (B1, B2, C1...)")
        if context["pais"]:
            suggestions.append(f"- Search for other countries with similar requirements")
        if context["idioma"]:
            suggestions.append(f"- Search for destinations without language requirement")
        if context["facultad"]:
            suggestions.append(f"- Search for agreements from other faculties in the same country")

        if not suggestions:
            suggestions = [
                "- Broaden the search criteria",
                "- Try other countries or programs",
                "- Look for destinations without language requirement"
            ]

        msg += "\n".join(suggestions[:3])

        return msg

    def _format_results(self, user_question: str, sql_query: str, results: list, success: bool, session_state: dict = None) -> str:
        """
        Formatea los resultados de la consulta SQL usando Python (rápido).
        """
        if not success:
            return f"❌ **Query error**\n\n{results}\n\nTry rephrasing your question."

        if not results:
            return self._generate_empty_result_message(user_question, sql_query)

        logger.info("📊 Formateando resultados con Python...")
        return self._format_results_basic(results, session_state=session_state)

    def _make_clickable(self, text: str) -> str:
        """Wraps text in a clickable span for the frontend."""
        return f'<span class="clickable-suggestion">{text}</span>'

    def _generate_contextual_suggestions(self, results: list, has_more: bool = False, show_expand: bool = True, faculty_shown: bool = False) -> str:
        """
        Generates contextual help suggestions based on the results.

        Args:
            results: List of result dictionaries
            has_more: Whether there are more results to show
            show_expand: Whether to show the "Expand #N" suggestion
            faculty_shown: Whether faculty information is already displayed

        Returns:
            Formatted suggestion string
        """
        suggestions = []

        # Check if results have multiple countries
        if results:
            countries = set(r.get('destination_country', '') for r in results if r.get('destination_country'))
            has_multiple_countries = len(countries) > 1

            # Check if results have multiple universities
            universities = set(r.get('host_institution', '') for r in results if r.get('host_institution'))
            has_multiple_universities = len(universities) > 1
        else:
            has_multiple_countries = False
            has_multiple_universities = False

        # Add "Show more" if there are more results
        if has_more:
            suggestions.append(self._make_clickable('Show me more'))

        # Add "Expand #N" if showing numbered results
        if show_expand and len(results) > 0:
            # Use a number from the middle of the displayed results for variety
            example_num = min(3, len(results))
            suggestions.append(self._make_clickable(f'Expand #{example_num}'))

        # Add "Also show faculty" only if faculty is not already shown
        if not faculty_shown:
            suggestions.append(self._make_clickable('Also show faculty'))

        # Add sorting suggestion only if it makes sense
        if has_multiple_countries:
            suggestions.append(self._make_clickable('Sort by country'))
        elif has_multiple_universities:
            suggestions.append(self._make_clickable('Sort by university'))

        # Build the suggestion line
        if suggestions:
            return '💡 ' + ' | '.join(suggestions)
        return ''

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

        response_parts = [f"✅ **Found {num_results} agreement(s)**\n"]

        # Mostrar hasta max_display resultados con formato compacto
        display_count = min(num_results, max_display)
        for i, r in enumerate(results[:display_count], 1):
            response_parts.append(f"### {i}. {r.get('host_institution', 'N/A')}")
            response_parts.append(f"- **Country:** {r.get('destination_country', 'N/A')}")
            response_parts.append(f"- **Program:** {r.get('mobility_program', 'N/A')}")
            response_parts.append(f"- **Vacancies:** {r.get('student_vacancies', 'N/A')}")
            response_parts.append(f"- **Language:** {self._format_language_from_fields(r)}")
            response_parts.append("")

        if num_results > max_display:
            remaining = num_results - max_display
            response_parts.append(f"*... and {remaining} more agreement(s)*")
            response_parts.append(f'💡 {self._make_clickable("Show me the next 20")} | {self._make_clickable("Show me all")}')
            # Add contextual suggestions for the displayed results
            displayed_results = results[:max_display]
            # Check if faculty fields have been shown
            faculty_fields = {'uma_faculties', 'uma_degrees', 'destination_faculty'}
            faculty_shown = bool(session_state.get('shown_fields', set()) & faculty_fields) if session_state else False
            response_parts.append(self._generate_contextual_suggestions(displayed_results, has_more=False, show_expand=True, faculty_shown=faculty_shown))
        else:
            # Con resultados moderados, mostrar ayuda para ampliar
            response_parts.append("---")
            # Check if faculty fields have been shown
            faculty_fields = {'uma_faculties', 'uma_degrees', 'destination_faculty'}
            faculty_shown = bool(session_state.get('shown_fields', set()) & faculty_fields) if session_state else False
            response_parts.append(self._generate_contextual_suggestions(results, has_more=False, show_expand=True, faculty_shown=faculty_shown))

        return "\n".join(response_parts)

    def _format_results_detailed(self, results: list) -> str:
        """
        Formato detallado para pocos resultados (1-5).
        Muestra información extendida de cada convenio.
        """
        num_results = len(results)
        response_parts = [f"✅ **Found {num_results} agreement(s)**\n"]

        for i, r in enumerate(results, 1):
            response_parts.append(f"### {i}. 🏛️ {r.get('host_institution', 'N/A')}")
            response_parts.append(f"**Country:** {r.get('destination_country', 'N/A')} | **Program:** {r.get('mobility_program', 'N/A')}")
            response_parts.append("")

            # Vigencia
            start = r.get('start_date', '')
            end = r.get('end_date', '')
            if start or end:
                response_parts.append(f"📅 **Validity:** {start} → {end}")

            # Plazas
            vacancies = r.get('student_vacancies', '')
            if vacancies:
                response_parts.append(f"🎓 **Vacancies:** {vacancies}")

            # Requisitos de idioma
            lang = self._format_language_from_fields(r)
            if lang and lang != 'No requiere acreditación de idioma':
                response_parts.append(f"🗣️ **Language:** {lang}")

            # Facultades UMA
            uma_fac = r.get('uma_faculties', '')
            if uma_fac:
                # Acortar si hay muchas facultades
                if len(uma_fac) > 150:
                    uma_fac = uma_fac[:150] + "..."
                response_parts.append(f"🏫 **UMA Faculties:** {uma_fac}")

            # Titulaciones UMA
            uma_deg = r.get('uma_degrees', '')
            if uma_deg:
                if len(uma_deg) > 150:
                    uma_deg = uma_deg[:150] + "..."
                response_parts.append(f"📚 **Degrees:** {uma_deg}")

            # Facultad destino (si está especificada y no es genérica)
            dest_fac = r.get('destination_faculty', '')
            if dest_fac and dest_fac not in ['General/No especificada', 'N/A', '']:
                response_parts.append(f"🎯 **Destination faculty:** {dest_fac}")

            # Niveles disponibles
            levels = self._format_available_levels(r)
            if levels and levels != 'No especificado':
                response_parts.append(f"📈 **Levels:** {levels}")

            response_parts.append("")  # Línea en blanco entre convenios

        # Ayuda para ver más detalles (faculty already shown in detailed view)
        if num_results > 1:
            response_parts.append("---")
            response_parts.append(self._generate_contextual_suggestions(results, has_more=False, show_expand=True, faculty_shown=True))

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
            grouping_priority = ['host_institution', 'mobility_program', 'lang_1_name', 'uma_faculties']
            for field in grouping_priority:
                if field in available_fields:
                    return self._format_grouped_by_field(results, field, num_results)
            # Si no hay ninguno, mostrar lista simple
            return self._format_results_simple_list(results, num_results)

        # Obtener países únicos
        countries = {}
        for r in results:
            country = r.get('destination_country', 'Unknown country')
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
                for field in ['mobility_program', 'lang_1_name']:
                    if field in available_fields:
                        return self._format_grouped_by_field(results, field, num_results)
                return self._format_results_simple_list(results, num_results)

    def _format_grouped_by_country(self, results: list, countries: dict, num_results: int) -> str:
        """Formatea resultados agrupados por país."""
        response_parts = []
        response_parts.append(f"📊 **Found {num_results} results grouped by country**\n")

        # Ordenar países por número de convenios (descendente)
        sorted_countries = sorted(countries.items(), key=lambda x: len(x[1]), reverse=True)

        for country, country_results in sorted_countries:
            num_convenios = len(country_results)
            # Obtener universidades únicas en este país
            universities = set(r.get('host_institution', 'N/A') for r in country_results)
            num_universities = len(universities)

            response_parts.append(f"### 🌍 {country}")
            response_parts.append(f"- **Agreements:** {num_convenios}")
            response_parts.append(f"- **Universities:** {num_universities}")
            response_parts.append("")

        # Añadir sugerencia para afinar búsqueda
        response_parts.append("---")
        response_parts.append("💡 **Would you like to refine the search?**")
        top_country = sorted_countries[0][0]
        response_parts.append(f'You can say: *"Yes, show me those from {top_country}"*')
        response_parts.append('Or add more filters: *"Those that also require English B2"*, *"Only first semester"*')

        return "\n".join(response_parts)

    def _format_grouped_by_university(self, results: list, num_results: int) -> str:
        """Formatea resultados agrupados por universidad (cuando hay un solo país)."""
        response_parts = []

        # Obtener el país (es único)
        country = results[0].get('destination_country', 'Unknown country') if results else 'Unknown country'

        # Agrupar por universidad
        universities = {}
        for r in results:
            uni = r.get('host_institution', 'Unknown university')
            if uni not in universities:
                universities[uni] = []
            universities[uni].append(r)

        num_universities = len(universities)

        response_parts.append(f"📊 **Found {num_results} results in {country}, grouped by university**\n")

        # Ordenar universidades por número de convenios (descendente)
        sorted_unis = sorted(universities.items(), key=lambda x: len(x[1]), reverse=True)

        for uni, uni_results in sorted_unis:
            num_convenios = len(uni_results)
            # Obtener programas únicos
            programs = set(r.get('mobility_program', 'N/A') for r in uni_results)

            response_parts.append(f"### 🏛️ {uni}")
            response_parts.append(f"- **Agreements:** {num_convenios}")
            response_parts.append(f"- **Programs:** {', '.join(programs)}")
            response_parts.append("")

        # Añadir sugerencia para afinar búsqueda
        response_parts.append("---")
        response_parts.append("💡 **Want to refine your search?**")
        top_uni = sorted_unis[0][0]
        # Acortar el nombre si es muy largo
        short_uni = top_uni[:40] + "..." if len(top_uni) > 40 else top_uni
        response_parts.append(f'You can say: *"Yes, show me those from {short_uni}"*')
        response_parts.append('Or add more filters: *"Those that also require English B2"*, *"Only first semester"*')

        return "\n".join(response_parts)

    def _format_language_from_fields(self, row: dict) -> str:
        """
        Construye un string legible de requisitos de idioma a partir de los campos lang_1_* y lang_2_*.
        Ejemplo: "INGLÉS B2, ALEMÁN B1" o "No requiere acreditación de idioma"
        """
        parts = []

        # Primer idioma
        lang1_name = row.get('lang_1_name', '')
        lang1_level = row.get('lang_1_level', '')
        if lang1_name and lang1_name.strip():
            lang_str = lang1_name.upper()
            if lang1_level and lang1_level.strip():
                lang_str += f" {lang1_level.upper()}"
            parts.append(lang_str)

        # Segundo idioma
        lang2_name = row.get('lang_2_name', '')
        lang2_level = row.get('lang_2_level', '')
        if lang2_name and lang2_name.strip():
            lang_str = lang2_name.upper()
            if lang2_level and lang2_level.strip():
                lang_str += f" {lang2_level.upper()}"
            parts.append(lang_str)

        if parts:
            return ", ".join(parts)
        return "No requiere acreditación de idioma"

    def _format_available_levels(self, row: dict) -> str:
        """
        Construye un string de niveles disponibles a partir de allows_undergraduate, allows_master, allows_phd.
        Ejemplo: "Grado, Máster" o "Grado, Máster, Doctorado"
        """
        levels = []
        if row.get('allows_undergraduate', '').lower() in ['sí', 'si', 'yes', '1', 'true']:
            levels.append("Grado")
        if row.get('allows_master', '').lower() in ['sí', 'si', 'yes', '1', 'true']:
            levels.append("Máster")
        if row.get('allows_phd', '').lower() in ['sí', 'si', 'yes', '1', 'true']:
            levels.append("Doctorado")
        return ", ".join(levels) if levels else "No especificado"

    def _format_language_info(self, row: dict) -> str:
        """
        Formatea la información de idiomas desde los campos lang_1_* y lang_2_*.
        Ejemplo: lang_1_name="Inglés", lang_1_level="B2" → "Inglés B2"
        """
        parts = []

        lang_1_name = row.get('lang_1_name', '')
        lang_1_level = row.get('lang_1_level', '')
        if lang_1_name:
            if lang_1_level:
                parts.append(f"{lang_1_name} {lang_1_level}")
            else:
                parts.append(lang_1_name)

        lang_2_name = row.get('lang_2_name', '')
        lang_2_level = row.get('lang_2_level', '')
        if lang_2_name:
            if lang_2_level:
                parts.append(f"{lang_2_name} {lang_2_level}")
            else:
                parts.append(lang_2_name)

        if not parts:
            return "No language requirement"

        return ", ".join(parts)

    def _format_grouped_by_field(self, results: list, field_name: str, num_results: int) -> str:
        """Agrupa resultados por un campo específico."""
        response_parts = []

        # Nombres legibles para los campos
        field_labels = {
            'lang_1_name': 'language',
            'mobility_program': 'program',
            'host_institution': 'university',
            'destination_country': 'country',
            'uma_faculties': 'UMA faculty',
        }
        label = field_labels.get(field_name, field_name)

        # Agrupar por valores únicos del campo
        groups = {}
        for r in results:
            # Para campos de idioma, usar el formateador especial
            if field_name == 'lang_1_name':
                value = self._format_language_from_fields(r)
            else:
                value = r.get(field_name, 'Not specified') or 'Not specified'

            if value not in groups:
                groups[value] = 0
            groups[value] += 1

        # Ordenar alfabéticamente por el campo de agrupación
        sorted_groups = sorted(groups.items(), key=lambda x: str(x[0]))

        response_parts.append(f"📊 **Found {num_results} results grouped by {label}**\n")

        for value, count in sorted_groups[:15]:  # Limitar a 15 grupos
            # Truncar valores muy largos
            display_value = str(value)[:80] + "..." if len(str(value)) > 80 else value
            response_parts.append(f"- **{display_value}**: {count} agreement(s)")

        if len(sorted_groups) > 15:
            response_parts.append(f"\n*... and {len(sorted_groups) - 15} more groups*")

        # Añadir sugerencia de refinamiento con ejemplos personalizados
        response_parts.append("")
        response_parts.append("---")
        response_parts.append("💡 **Would you like to refine the search?**")

        # Generar ejemplos basados en los grupos mostrados
        example_value = sorted_groups[0][0] if sorted_groups else "value"

        # Personalizar el ejemplo según el campo
        if field_name == 'lang_1_name':
            response_parts.append(f'You can say: *"Yes, show me those with {example_value}"*')
        elif field_name == 'destination_country':
            response_parts.append(f'You can say: *"Yes, show me those from {example_value}"*')
        elif field_name == 'mobility_program':
            response_parts.append(f'You can say: *"Yes, only those from {example_value}"*')
        elif field_name == 'host_institution':
            response_parts.append(f'You can say: *"Yes, show me those from {example_value}"*')
        else:
            response_parts.append(f'You can say: *"Yes, show me those from {example_value}"*')

        response_parts.append('Or add more filters: *"Those that also require English B2"*, *"Only first semester"*')

        return "\n".join(response_parts)

    def _format_results_simple_fields(self, results: list) -> str:
        """
        Formato para consultas que devuelven campos específicos (no convenios completos).
        Ej: SELECT DISTINCT uma_faculties, SELECT DISTINCT destination_country, etc.
        """
        num_results = len(results)
        if not results:
            return "🔍 **No results found**"

        # Obtener los nombres de los campos
        fields = list(results[0].keys())

        # Mapeo de campos a nombres legibles
        field_labels = {
            'uma_faculties': 'UMA Faculties',
            'destination_country': 'Country',
            'host_institution': 'University',
            'mobility_program': 'Program',
            'destination_faculty': 'Destination Faculty',
            'uma_degrees': 'UMA Degrees',
            'lang_1_name': 'Language 1',
            'lang_1_level': 'Level 1',
            'lang_2_name': 'Language 2',
            'lang_2_level': 'Level 2',
        }

        # Si es un solo campo, mostrar como lista simple
        if len(fields) == 1:
            field = fields[0]
            label = field_labels.get(field, field.replace('_', ' ').title())
            response_parts = [f"✅ **Found {num_results} {label.lower()}:**\n"]

            for i, r in enumerate(results, 1):
                value = r.get(field, 'N/A')
                if value:
                    response_parts.append(f"{i}. {value}")

            return "\n".join(response_parts)

        # Si hay múltiples campos, mostrar en formato tabla
        response_parts = [f"✅ **Found {num_results} result(s)**\n"]

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
            response_parts.append(f"\n*... and {num_results - 20} more*")

        return "\n".join(response_parts)

    def _format_results_simple_list(self, results: list, num_results: int) -> str:
        """Formato simple cuando no hay campo claro para agrupar."""
        response_parts = [f"✅ **Found {num_results} result(s)**\n"]

        # Mostrar los primeros resultados con todos sus campos
        for i, r in enumerate(results[:10], 1):
            response_parts.append(f"### {i}.")
            for key, value in r.items():
                if value:
                    display_value = str(value)[:100] + "..." if len(str(value)) > 100 else value
                    response_parts.append(f"- **{key}:** {display_value}")
            response_parts.append("")

        if num_results > 10:
            response_parts.append(f"*... and {num_results - 10} more*")

        return "\n".join(response_parts)

    def _format_as_html_table(self, results: list) -> str:
        """Formatea los resultados JSON como una tabla HTML interactiva."""
        if not results:
            return "<p><em>No results</em></p>"

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
<div class="sql-stats">Results: <strong>{row_count}</strong> rows</div>
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
            return """⚠️ **Database not found**

Please create a SQLite database at `data/database.db`.

Example:
```bash
sqlite3 data/database.db < your_schema.sql
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
        state['shown_fields'] = set()  # Reset shown fields for new query

        # Inject default ORDER BY host_institution when missing
        sql_query = self._ensure_default_order(sql_query)
        state['last_sql_query'] = sql_query

        # Mostrar la SQL generada (solo crystal_box y grey_box)
        show_sql = self._transparency in ("crystal_box", "grey_box")
        sql_display = f"```sql\n{sql_query}\n```\n\n" if show_sql else ""

        # ⏱️ Fase 2b: Pre-execution verification (prompt level enforcement)
        if self._prompt_level in ("stringent", "tolerant"):
            pre_check = self._sql_verifier.verify(sql_query)

            # Semantic alignment check: does the SQL match the user's question?
            semantic = self._sql_verifier.verify_semantic(user_message, sql_query)
            if semantic["issues"]:
                pre_check["issues"].extend(semantic["issues"])
                pre_check["confidence"] = max(0, pre_check["confidence"] - semantic["penalty"])
                logger.warning(f"⚠️ Semantic check: {semantic['issues']}")

            if self._prompt_level == "stringent":
                # STRINGENT: reject on hard errors (unknown tables/columns, unsafe code, semantic mismatch)
                hard_errors = [i for i in pre_check["issues"]
                               if i.startswith("Unknown table:") or i.startswith("Unknown column:")
                               or i.startswith("Dangerous keyword")
                               or i.startswith("Semantic mismatch:")]
                if hard_errors:
                    issues_text = "\n".join(f"- {i}" for i in hard_errors)
                    badge = SQLReliabilityBadge.source_badge(
                        pre_check, transparency=self._transparency,
                        prompt_level=self._prompt_level,
                        model_name=self.model or "unknown",
                        is_local_llm=os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm"),
                    )
                    self._write_audit_log(user_message, sql_query, pre_check, 0)
                    self._log_timing_summary(timings)
                    sql_section = f"**Generated SQL query:**\n{sql_display}" if show_sql else ""
                    return (
                        f"{badge}{sql_section}"
                        f"**SQL verification failed (stringent mode):**\n{issues_text}\n\n"
                        f"The query was **not executed** because it does not match your question. "
                        f"Please try rephrasing your question."
                    )

            if self._prompt_level == "tolerant" and pre_check["issues"]:
                # TOLERANT: warn but continue execution
                logger.warning(f"⚠️ [tolerant] SQL issues detected but proceeding: {pre_check['issues']}")

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
                return f"⚠️ Error executing query: {error_msg}"

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

        # Auto-correct: if 0 results, try fixing misspelled LIKE terms
        autocorrect_note = ""
        if success and (not results or len(results) == 0):
            corrected_sql, corrections = self._sql_verifier.autocorrect_sql(sql_query)
            if corrected_sql and corrected_sql != sql_query:
                logger.info(f"🔄 Auto-correcting SQL: {corrections}")
                success2, results2 = self._execute_sql(corrected_sql)
                if success2 and results2:
                    # Use corrected results
                    success, results = success2, results2
                    sql_query = corrected_sql
                    state['last_sql_query'] = corrected_sql
                    autocorrect_note = "\n\n".join(f"🔄 {c}" for c in corrections) + "\n\n"
                    if show_sql:
                        sql_display = f"```sql\n{sql_query}\n```\n\n"

        # Guardar resultados para paginación
        if success and results:
            state['last_results'] = results
            state['last_display_offset'] = min(self.default_page_size, len(results))

        formatted = self._format_results(user_message, sql_query, results, success, state)
        t_fase4_end = time.perf_counter()
        timings["4. Python formatea respuesta"] = t_fase4_end - t_fase4_start

        # ⏱️ Fase 5: SQL verification and reliability badge
        result_count = len(results) if isinstance(results, list) else 0
        verification = self._sql_verifier.verify_with_execution(sql_query, success, result_count)

        # Post-execution semantic check (also applies to tolerant mode)
        semantic_post = self._sql_verifier.verify_semantic(user_message, sql_query)
        if semantic_post["issues"]:
            verification["issues"].extend(semantic_post["issues"])
            verification["confidence"] = max(0, verification["confidence"] - semantic_post["penalty"])

        logger.info(f"🔍 SQL verification: confidence={verification['confidence']}%, "
                     f"tables={len(verification['verified_tables'])}/{len(verification['verified_tables'])+len(verification['unknown_tables'])}, "
                     f"columns={len(verification['verified_columns'])}/{len(verification['verified_columns'])+len(verification['unknown_columns'])}")
        if verification['issues']:
            logger.info(f"⚠️ Issues: {verification['issues']}")

        # Determine model display name
        model_display = self.model or "unknown"
        is_local = os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm")

        badge = SQLReliabilityBadge.source_badge(
            verification,
            transparency=self._transparency,
            prompt_level=self._prompt_level,
            model_name=model_display,
            is_local_llm=is_local,
        )

        # Audit log
        self._write_audit_log(user_message, sql_query, verification, result_count)

        # Mostrar resumen de tiempos
        self._log_timing_summary(timings)

        # Paso 5: Combinar badge + SQL + explicación + suggestions
        sql_section = f"**Generated SQL query:**\n{sql_display}" if show_sql else ""
        suggestion_section = ""
        if verification.get("suggestions"):
            suggestion_section = "\n\n" + "\n".join(
                f"💡 {s}" for s in verification["suggestions"]
            ) + "\n"
        return f"{badge}{autocorrect_note}{sql_section}{formatted}{suggestion_section}"

    async def chat_stream(self, user_message: str, history: list = None, session_id: str = None,
                          transparency_override: str = None, model_override: str = None,
                          prompt_level_override: str = None, **kwargs):
        """
        Versión streaming - emite eventos de estado y contenido.
        """
        # Use per-request overrides or fall back to instance defaults
        transparency = transparency_override or self._transparency
        model = model_override or self.model
        prompt_level = prompt_level_override or self._prompt_level

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
            yield ("content", "⚠️ **Database not found**\n\nCreate a SQLite database at `data/database.db`.")
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
        state['shown_fields'] = set()  # Reset shown fields for new query

        # Inject default ORDER BY host_institution when missing
        sql_query = self._ensure_default_order(sql_query)
        state['last_sql_query'] = sql_query

        # Mostrar la SQL generada inmediatamente (solo crystal_box y grey_box)
        show_sql = transparency in ("crystal_box", "grey_box")
        if show_sql:
            yield ("content", f"**Generated SQL query:**\n```sql\n{sql_query}\n```\n\n")

        # ⏱️ Fase 2b: Pre-execution verification (prompt level enforcement)
        if prompt_level in ("stringent", "tolerant"):
            pre_check = self._sql_verifier.verify(sql_query)

            # Semantic alignment check
            semantic = self._sql_verifier.verify_semantic(user_message, sql_query)
            if semantic["issues"]:
                pre_check["issues"].extend(semantic["issues"])
                pre_check["confidence"] = max(0, pre_check["confidence"] - semantic["penalty"])
                logger.warning(f"⚠️ Semantic check: {semantic['issues']}")

            if prompt_level == "stringent":
                hard_errors = [i for i in pre_check["issues"]
                               if i.startswith("Unknown table:") or i.startswith("Unknown column:")
                               or i.startswith("Dangerous keyword")
                               or i.startswith("Semantic mismatch:")]
                if hard_errors:
                    issues_text = "\n".join(f"- {i}" for i in hard_errors)
                    badge = SQLReliabilityBadge.source_badge(
                        pre_check, transparency=transparency,
                        prompt_level=prompt_level,
                        model_name=model or "unknown",
                        is_local_llm=os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm"),
                    )
                    if badge:
                        yield ("badge", badge)
                    self._write_audit_log(user_message, sql_query, pre_check, 0,
                                          transparency=transparency, prompt_level=prompt_level, model_name=model)
                    self._log_timing_summary(timings)
                    yield ("content",
                        f"**SQL verification failed (stringent mode):**\n{issues_text}\n\n"
                        f"The query was **not executed** because it does not match your question. "
                        f"Please try rephrasing your question."
                    )
                    return

            if prompt_level == "tolerant" and pre_check["issues"]:
                issues_text = ", ".join(pre_check["issues"])
                yield ("content", f"⚠️ *Warning (tolerant mode): {issues_text}*\n\n")

        # ⏱️ Fase 3: Ejecutar SQL
        t_fase3_start = time.perf_counter()
        yield ("status", "Executing query...")

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
                yield ("content", f"⚠️ Error executing query: {error_msg}")
                return

            json_output = consultar_result.stdout
            logger.info(f"✅ Consulta ejecutada correctamente")

            yield ("status", "Processing results...")

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

        # Auto-correct: if 0 results, try fixing misspelled LIKE terms
        if success and (not results or len(results) == 0):
            corrected_sql, corrections = self._sql_verifier.autocorrect_sql(sql_query)
            if corrected_sql and corrected_sql != sql_query:
                logger.info(f"🔄 Auto-correcting SQL: {corrections}")
                success2, results2 = self._execute_sql(corrected_sql)
                if success2 and results2:
                    success, results = success2, results2
                    sql_query = corrected_sql
                    state['last_sql_query'] = corrected_sql
                    correction_text = "\n\n".join(f"🔄 {c}" for c in corrections)
                    yield ("content", f"{correction_text}\n\n")
                    if show_sql:
                        yield ("content", f"**Corrected SQL query:**\n```sql\n{sql_query}\n```\n\n")

        # Guardar resultados para paginación y detalles
        if success and results:
            state['last_results'] = results
            state['last_display_offset'] = min(self.default_page_size, len(results))

        formatted = self._format_results(user_message, sql_query, results, success, state)
        t_fase4_end = time.perf_counter()
        timings["4. Python formatea respuesta"] = t_fase4_end - t_fase4_start

        # ⏱️ Fase 5: SQL verification and reliability badge
        result_count = len(results) if isinstance(results, list) else 0
        verification = self._sql_verifier.verify_with_execution(sql_query, success, result_count)

        model_display = model or "unknown"
        is_local = os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm")

        badge = SQLReliabilityBadge.source_badge(
            verification,
            transparency=transparency,
            prompt_level=prompt_level,
            model_name=model_display,
            is_local_llm=is_local,
        )
        if badge:
            yield ("badge", badge)

        # Audit log
        self._write_audit_log(user_message, sql_query, verification, result_count,
                              transparency=transparency, prompt_level=prompt_level, model_name=model)

        # Mostrar resumen de tiempos
        self._log_timing_summary(timings)

        # Enviar solo la explicación formateada (sin tabla HTML redundante)
        yield ("content", formatted)

        # Show suggestions if any (e.g. "Did you mean: KAUNO KOLEGIJA?")
        if verification.get("suggestions"):
            suggestion_text = "\n".join(f"💡 {s}" for s in verification["suggestions"])
            yield ("content", f"\n\n{suggestion_text}\n")

    def _write_audit_log(self, query: str, sql: str, verification: dict, result_count: int,
                         transparency: str = None, prompt_level: str = None, model_name: str = None):
        """Write an audit log entry for EU AI Act compliance."""
        if not self._audit_enabled:
            return
        try:
            from datetime import datetime, timezone
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_id": self._config.get("agent_id", "pisha4"),
                "query": query,
                "query_type": "text2sql",
                "sql": sql,
                "confidence": verification.get("confidence", 0),
                "issues": verification.get("issues", []),
                "verified_tables": verification.get("verified_tables", []),
                "unknown_columns": verification.get("unknown_columns", []),
                "executed_ok": verification.get("executed_ok"),
                "result_count": result_count,
                "transparency_level": transparency or self._transparency,
                "prompt_level": prompt_level or self._prompt_level,
                "model": model_name or self.model,
            }
            import json as json_mod
            with open(self._audit_path, "a", encoding="utf-8") as f:
                f.write(json_mod.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[audit_log] Write error: {e}")

    def get_schema(self) -> str:
        """Devuelve el esquema de la BD (útil para debugging/API)."""
        return self._get_db_schema()

    def get_history(self, session_id: str = None) -> list:
        """Devuelve el historial de consultas para la API, incluyendo operaciones."""
        if session_id is None:
            session_id = "default"

        state = self._get_session_state(session_id)

        # Group operations by query_index
        operations_by_query = {}
        for op in state.get('operations_history', []):
            q_idx = op.get('query_index', 0)
            if q_idx not in operations_by_query:
                operations_by_query[q_idx] = []
            operations_by_query[q_idx].append(op['description'])

        all_queries = []

        for i, entry in enumerate(state['query_history']):
            all_queries.append({
                'question': entry.get('question', ''),
                'sql': entry.get('sql', ''),
                'num_results': len(entry.get('results', [])),
                'operations': operations_by_query.get(i, [])
            })

        # Añadir la consulta actual si existe
        current_idx = len(state['query_history'])
        if state['last_sql_query']:
            all_queries.append({
                'question': state['last_user_question'] or '(consulta actual)',
                'sql': state['last_sql_query'],
                'num_results': len(state['last_results']) if state['last_results'] else 0,
                'operations': operations_by_query.get(current_idx, [])
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
            metrics["error"] = "Database not found"
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
