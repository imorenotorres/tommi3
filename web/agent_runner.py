"""
Agent Runner - Ejecuta agentes Tommi directamente
"""

import importlib.util
import json
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
    rag_approach: str = "context_preserving"  # basic, context_preserving, custom
    show_history: bool = True
    show_description: bool = False
    transparency_level: str = "black_box"
    prompt_level: str = "stringent"


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

                # Check settings in agent's .env
                rag_approach = "context_preserving"
                env_file = agent_dir / ".env"
                if env_file.exists():
                    try:
                        env_content = env_file.read_text(encoding="utf-8")
                        for line in env_content.split('\n'):
                            line = line.strip()
                            if line.startswith('RAG_APPROACH'):
                                rag_approach = line.split('=', 1)[1].strip().lower()
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
                    rag_approach=rag_approach,
                    show_history=config.get("show_history", True),
                    show_description=config.get("show_description", False),
                    transparency_level=config.get("transparency_level", "black_box"),
                    prompt_level=config.get("prompt_level", "stringent"),
                )

                if agent.public:
                    agents.append(agent)
                    self._agents_cache[agent.id] = agent

            except Exception as e:
                print(f"Error loading agent from {agent_dir}: {e}")
                continue

        return agents

    def _extract_agent_config(self, app_py: Path) -> Optional[dict]:
        """Extrae la configuración del agente.

        Primero intenta leer config.json junto a app.py.  Si no existe,
        parsea AGENT_CONFIG como diccionario literal del propio app.py.
        """
        # 1. Try config.json first (preferred single source of truth)
        config_json = app_py.parent / "config.json"
        if config_json.exists():
            try:
                with open(config_json, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                # Normalise key names so the rest of the code works
                config = {
                    "id": cfg.get("agent_id", app_py.parent.name),
                    "name": cfg.get("agent_name", app_py.parent.name),
                    "description": cfg.get("description", ""),
                    "welcome_message": cfg.get("welcome_message", ""),
                    "example_queries": cfg.get("example_queries", []),
                    "show_history": cfg.get("show_history", True),
                    "show_description": cfg.get("show_description", False),
                    "public": cfg.get("public", True),
                    "transparency_level": cfg.get("transparency_level", "black_box"),
                    "prompt_level": cfg.get("prompt_level", "stringent"),
                }
                # Use type from config.json if present, otherwise try app.py
                config["type"] = cfg.get("type") or self._extract_agent_type(app_py) or "oneshot"
                return config
            except Exception as e:
                print(f"Warning: Could not load {config_json}: {e}")

        # 2. Fallback: parse AGENT_CONFIG literal from app.py
        try:
            content = app_py.read_text(encoding="utf-8")

            import ast
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "AGENT_CONFIG":
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

    @staticmethod
    def _extract_agent_type(app_py: Path) -> Optional[str]:
        """Extract the 'type' value from AGENT_CONFIG in app.py."""
        try:
            import ast
            tree = ast.parse(app_py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "AGENT_CONFIG":
                            if isinstance(node.value, ast.Dict):
                                for key, value in zip(node.value.keys, node.value.values):
                                    if isinstance(key, ast.Constant) and key.value == "type" and isinstance(value, ast.Constant):
                                        return value.value
        except Exception:
            pass
        return None

    def _load_agent_module(self, agent_id: str, progress_callback=None) -> object:
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

            # Crear instancia con system_prompt y progress_callback si están disponibles
            import inspect
            sig = inspect.signature(module.Agent.__init__)
            kwargs = {}
            if system_prompt:
                kwargs['system_prompt'] = system_prompt
            if progress_callback and 'progress_callback' in sig.parameters:
                kwargs['progress_callback'] = progress_callback
            agent_instance = module.Agent(**kwargs)

            self._agent_instances[agent_id] = agent_instance
            return agent_instance
        finally:
            sys.path.remove(str(agent_path))

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Obtiene información de un agente por su ID"""
        if not self._agents_cache:
            self.discover_agents()
        return self._agents_cache.get(agent_id)

    def get_agent_instance(self, agent_id: str) -> Optional[object]:
        """Returns the loaded agent instance, or None if not loaded."""
        return self._agent_instances.get(agent_id)

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
        session_id: Optional[str] = None,
        model_override: Optional[str] = None,
        transparency_override: Optional[str] = None,
        prompt_level_override: Optional[str] = None,
        username: Optional[str] = None,
        study_info: Optional[dict] = None
    ) -> AsyncGenerator[tuple[str, str, Optional[str]], None]:
        """
        Ejecuta una query y hace streaming de la respuesta.
        Yields tuplas de (tipo, contenido, session_id).
        tipo: "status" o "content"
        model_override/transparency_override/prompt_level_override: per-request client preferences
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
            # Pass optional kwargs if the agent supports them
            kwargs = {}
            if 'session_id' in agent_instance.chat_stream.__code__.co_varnames:
                kwargs['session_id'] = session_id
            if username and 'username' in agent_instance.chat_stream.__code__.co_varnames:
                kwargs['username'] = username
            if study_info and 'study_info' in agent_instance.chat_stream.__code__.co_varnames:
                kwargs['study_info'] = study_info
            # Pass overrides as parameters instead of mutating the shared instance
            if transparency_override:
                kwargs['transparency_override'] = transparency_override
            if model_override:
                kwargs['model_override'] = model_override
            if prompt_level_override:
                kwargs['prompt_level_override'] = prompt_level_override
            stream = agent_instance.chat_stream(message, history, **kwargs)

            async for item in stream:
                # El agente puede emitir tuplas (tipo, contenido) o solo strings
                if isinstance(item, tuple):
                    event_type, content = item
                else:
                    event_type, content = "content", item

                # Only accumulate content chunks in the full response (not badges/status)
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
        For RAG agents, this triggers ChromaDB initialization and sync.
        Returns status dict with 'success' and optional 'indexed_chunks'.
        """
        # Remove from cache to force reload
        if agent_id in self._agent_instances:
            del self._agent_instances[agent_id]

        try:
            agent_instance = self._load_agent_module(agent_id)
            result = {"success": True, "agent_id": agent_id}

            # Force ChromaDB initialization if lazy (collection is None).
            if hasattr(agent_instance, '_init_chromadb') and (
                not hasattr(agent_instance, 'collection') or agent_instance.collection is None
            ):
                agent_instance._init_chromadb()

            if hasattr(agent_instance, 'collection') and agent_instance.collection is not None:
                result["indexed_chunks"] = agent_instance.collection.count()
                result["newly_indexed_chunks"] = getattr(agent_instance, '_newly_indexed_chunks', 0)

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def init_agent_with_callback(self, agent_id: str, progress_callback=None) -> dict:
        """Like init_agent but accepts a progress_callback for reporting indexing progress."""
        if agent_id in self._agent_instances:
            del self._agent_instances[agent_id]

        try:
            agent_instance = self._load_agent_module(agent_id, progress_callback=progress_callback)
            result = {"success": True, "agent_id": agent_id}

            # Force ChromaDB initialization if lazy (collection is None).
            # _init_chromadb calls _sync_documents which detects and indexes
            # new files (with progress_callback) and removes deleted ones.
            if hasattr(agent_instance, '_init_chromadb') and (
                not hasattr(agent_instance, 'collection') or agent_instance.collection is None
            ):
                agent_instance._init_chromadb()

            if hasattr(agent_instance, 'collection') and agent_instance.collection is not None:
                result["indexed_chunks"] = agent_instance.collection.count()
                result["newly_indexed_chunks"] = getattr(agent_instance, '_newly_indexed_chunks', 0)

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reindex_agent(self, agent_id: str) -> dict:
        """
        Force reindex of a RAG agent's documents.
        Returns status dict with 'success' and 'indexed_chunks'.
        """
        # Load agent if not already loaded
        if agent_id not in self._agent_instances:
            try:
                self._load_agent_module(agent_id)
            except Exception as e:
                return {"success": False, "error": f"Failed to load agent: {str(e)}"}

        agent_instance = self._agent_instances.get(agent_id)
        if not agent_instance:
            return {"success": False, "error": "Agent not found"}

        # Check if agent supports reindexing
        if not hasattr(agent_instance, 'reindex'):
            return {"success": False, "error": "Agent does not support reindexing (not a RAG agent)"}

        try:
            count = agent_instance.reindex()
            return {"success": True, "agent_id": agent_id, "indexed_chunks": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_agent_token_usage(self, agent_id: str) -> Optional[dict]:
        """
        Get token usage statistics for an agent.
        Returns None if agent is not loaded or doesn't support token tracking.
        """
        agent_instance = self._agent_instances.get(agent_id)
        if not agent_instance:
            return None

        if hasattr(agent_instance, 'get_token_usage'):
            return agent_instance.get_token_usage()
        return None

    def reset_agent_token_usage(self, agent_id: str) -> bool:
        """
        Reset token usage counters for an agent.
        Returns True if successful, False if agent not found or doesn't support it.
        """
        agent_instance = self._agent_instances.get(agent_id)
        if not agent_instance:
            return False

        if hasattr(agent_instance, 'reset_token_usage'):
            agent_instance.reset_token_usage()
            return True
        return False
