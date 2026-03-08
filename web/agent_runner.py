"""
Agent Runner - Ejecuta agentes Tommi directamente
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

from error_codes import (
    format_error,
    AGENT_NOT_FOUND, AGENT_FILE_NOT_FOUND, AGENT_LOAD_ERROR,
    SERVER_STREAMING_ERROR
)


@dataclass
class AgentInfo:
    """Información de un agente Tommi"""
    id: str
    name: str
    agent_type: str
    description: str
    welcome_message: str
    example_queries: list[str]
    path: str
    public: bool = True
    verify_grounding: bool = False


@dataclass
class QueryResult:
    """Resultado de una query"""
    response: str
    session_id: str


class AgentRunner:
    """Ejecuta agentes Tommi y gestiona sus respuestas"""

    def __init__(self, agents_base_path: str):
        self.agents_base_path = Path(agents_base_path)
        self._agents_cache: dict[str, AgentInfo] = {}
        self._agent_instances: dict[str, object] = {}
        self._sessions: dict[str, list] = {}  # session_id -> history

    def discover_agents(self) -> list[AgentInfo]:
        """Descubre todos los agentes disponibles leyendo AGENT_CONFIG de app.py"""
        agents = []

        for agent_dir in self.agents_base_path.iterdir():
            if not agent_dir.is_dir():
                continue

            # Ignorar carpetas especiales
            if agent_dir.name.startswith('.') or agent_dir.name in ['web', '__pycache__']:
                continue

            app_py = agent_dir / "app.py"
            if not app_py.exists():
                continue

            try:
                # Leer AGENT_CONFIG del archivo app.py
                config = self._extract_agent_config(app_py)
                if not config:
                    continue

                # Check if verification is enabled in agent's .env
                verify_grounding = False
                env_file = agent_dir / ".env"
                if env_file.exists():
                    try:
                        env_content = env_file.read_text(encoding="utf-8")
                        for line in env_content.split('\n'):
                            if line.strip().startswith('VERIFY_GROUNDING'):
                                value = line.split('=', 1)[1].strip().lower()
                                verify_grounding = value == 'true'
                                break
                    except Exception:
                        pass

                agent = AgentInfo(
                    id=config.get("id", agent_dir.name),
                    name=config.get("name", agent_dir.name),
                    agent_type=config.get("type", "oneshot"),
                    description=config.get("description", ""),
                    welcome_message=config.get("welcome_message", ""),
                    example_queries=config.get("example_queries", []),
                    path=str(agent_dir),
                    public=config.get("public", True),
                    verify_grounding=verify_grounding,
                )

                if agent.public:
                    agents.append(agent)
                    self._agents_cache[agent.id] = agent

            except Exception as e:
                print(f"Error loading agent from {agent_dir}: {e}")
                continue

        return agents

    def _extract_agent_config(self, app_py: Path) -> Optional[dict]:
        """Extrae AGENT_CONFIG del archivo app.py"""
        try:
            content = app_py.read_text(encoding="utf-8")

            # Buscar AGENT_CONFIG en el código
            import ast
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "AGENT_CONFIG":
                            # Evaluar el diccionario de forma segura
                            if isinstance(node.value, ast.Dict):
                                config = {}
                                for key, value in zip(node.value.keys, node.value.values):
                                    if isinstance(key, ast.Constant):
                                        key_str = key.value
                                        if isinstance(value, ast.Constant):
                                            config[key_str] = value.value
                                        elif isinstance(value, ast.List):
                                            config[key_str] = [
                                                elt.value for elt in value.elts
                                                if isinstance(elt, ast.Constant)
                                            ]
                                return config
            return None
        except Exception as e:
            print(f"Error parsing {app_py}: {e}")
            return None

    def _load_agent_module(self, agent_id: str) -> object:
        """Carga dinámicamente el módulo agent.py y retorna una instancia de Agent"""
        if agent_id in self._agent_instances:
            return self._agent_instances[agent_id]

        agent_info = self.get_agent(agent_id)
        if not agent_info:
            err = format_error(AGENT_NOT_FOUND, agent_id=agent_id)
            raise ValueError(f"Error {err['error_code']}: {err['error']}")

        agent_path = Path(agent_info.path)
        agent_py = agent_path / "agent.py"

        if not agent_py.exists():
            err = format_error(AGENT_FILE_NOT_FOUND, path=str(agent_py))
            raise ValueError(f"Error {err['error_code']}: {err['error']}")

        # SIEMPRE restaurar primero los valores por defecto de web/.env
        # Esto asegura que cada agente empiece con la configuración base
        from dotenv import load_dotenv, dotenv_values
        web_env = Path(__file__).parent / ".env"
        load_dotenv(web_env, override=True)

        # Luego, si el agente tiene su propio LLM_PROVIDER, sobrescribir
        env_file = agent_path / ".env"
        if env_file.exists():
            agent_env = dotenv_values(env_file)
            if agent_env.get("LLM_PROVIDER"):
                load_dotenv(env_file, override=True)

        # Importar dinámicamente el módulo
        spec = importlib.util.spec_from_file_location("agent", agent_py)
        module = importlib.util.module_from_spec(spec)

        # Añadir el directorio del agente al path temporalmente
        sys.path.insert(0, str(agent_path))

        try:
            spec.loader.exec_module(module)

            # Intentar cargar build_system_prompt de app.py si existe
            system_prompt = None
            app_py = agent_path / "app.py"
            if app_py.exists():
                try:
                    app_spec = importlib.util.spec_from_file_location("app", app_py)
                    app_module = importlib.util.module_from_spec(app_spec)
                    app_spec.loader.exec_module(app_module)
                    if hasattr(app_module, 'build_system_prompt'):
                        system_prompt = app_module.build_system_prompt()
                except Exception as e:
                    print(f"Warning: Could not load build_system_prompt from {app_py}: {e}")

            # Crear instancia con system_prompt si está disponible
            if system_prompt:
                agent_instance = module.Agent(system_prompt=system_prompt)
            else:
                agent_instance = module.Agent()

            self._agent_instances[agent_id] = agent_instance
            return agent_instance
        finally:
            sys.path.remove(str(agent_path))

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Obtiene información de un agente por su ID"""
        if not self._agents_cache:
            self.discover_agents()
        return self._agents_cache.get(agent_id)

    def _get_session_history(self, session_id: str) -> list:
        """Obtiene el historial de una sesión"""
        return self._sessions.get(session_id, [])

    def _save_to_session(self, session_id: str, user_msg: str, assistant_msg: str):
        """Guarda mensajes en la sesión"""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append({"role": "user", "content": user_msg})
        self._sessions[session_id].append({"role": "assistant", "content": assistant_msg})

    async def run_query(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None
    ) -> QueryResult:
        """Ejecuta una query contra un agente y devuelve la respuesta"""
        agent_instance = self._load_agent_module(agent_id)

        # Generar session_id si no existe
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())

        # Obtener historial
        history = self._get_session_history(session_id)

        # Ejecutar query (pasar session_id si el agente lo soporta)
        if 'session_id' in agent_instance.chat.__code__.co_varnames:
            response = agent_instance.chat(message, history, session_id=session_id)
        else:
            response = agent_instance.chat(message, history)

        # Guardar en sesión
        self._save_to_session(session_id, message, response)

        return QueryResult(response=response, session_id=session_id)

    async def run_query_stream(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[tuple[str, str, Optional[str]], None]:
        """
        Ejecuta una query y hace streaming de la respuesta.
        Yields tuplas de (tipo, contenido, session_id).
        tipo: "status" o "content"
        """
        agent_instance = self._load_agent_module(agent_id)

        # Generar session_id si no existe
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())

        # Obtener historial
        history = self._get_session_history(session_id)

        full_response = ""
        first_chunk = True

        try:
            # Pasar session_id si el agente lo soporta
            if 'session_id' in agent_instance.chat_stream.__code__.co_varnames:
                stream = agent_instance.chat_stream(message, history, session_id=session_id)
            else:
                stream = agent_instance.chat_stream(message, history)

            async for item in stream:
                # El agente puede emitir tuplas (tipo, contenido) o solo strings
                if isinstance(item, tuple):
                    event_type, content = item
                else:
                    event_type, content = "content", item

                if event_type == "content":
                    full_response += content

                if first_chunk:
                    yield (event_type, content, session_id)
                    first_chunk = False
                else:
                    yield (event_type, content, None)
        except Exception as e:
            err = format_error(SERVER_STREAMING_ERROR, details=str(e))
            yield ("content", f"[Error {err['error_code']}: {err['error']}]", session_id if first_chunk else None)
            return

        # Guardar en sesión
        self._save_to_session(session_id, message, full_response)

    def get_agent_history(self, agent_id: str, session_id: str = None) -> list:
        """Obtiene el historial de consultas de un agente (si tiene el método get_history)."""
        if agent_id not in self._agent_instances:
            return []

        agent_instance = self._agent_instances[agent_id]
        if hasattr(agent_instance, 'get_history'):
            # Pasar session_id si el agente lo soporta
            if 'session_id' in agent_instance.get_history.__code__.co_varnames:
                return agent_instance.get_history(session_id=session_id)
            return agent_instance.get_history()
        return []

    def init_agent(self, agent_id: str) -> dict:
        """
        Initializes an agent, forcing reload if needed.
        For RAG agents, this triggers ChromaDB indexing.
        Returns status dict with 'success' and optional 'indexed_chunks'.
        """
        # Remove from cache to force reload
        if agent_id in self._agent_instances:
            del self._agent_instances[agent_id]

        try:
            agent_instance = self._load_agent_module(agent_id)
            result = {"success": True, "agent_id": agent_id}

            # If it's a RAG agent, check if reindex is needed
            if hasattr(agent_instance, 'collection') and agent_instance.collection is not None:
                if agent_instance.collection.count() == 0:
                    # Force reindex
                    if hasattr(agent_instance, 'reindex'):
                        count = agent_instance.reindex()
                        result["indexed_chunks"] = count
                    elif hasattr(agent_instance, '_index_documents'):
                        agent_instance._index_documents()
                        result["indexed_chunks"] = agent_instance.collection.count()
                else:
                    result["indexed_chunks"] = agent_instance.collection.count()

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
