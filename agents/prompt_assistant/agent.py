"""PROMPT Assistant — specialised agent for designing and improving AI prompts.

Can list other agents, load their prompts for review, and apply modifications.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
from llm_client import LLMClient

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..")
_VISIBILITY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "web", "data", "agent_visibility.json")


def _load_json(filename):
    path = os.path.join(AGENT_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_visibility():
    """Load the agent visibility configuration."""
    if not os.path.exists(_VISIBILITY_FILE):
        return {}
    with open(_VISIBILITY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _can_user_see_agent(agent_id, username, role):
    """Check if a user can see an agent based on visibility level and allowed_users."""
    if role == "superuser":
        return True
    vis = _load_visibility()
    entry = vis.get(agent_id, {})
    if not isinstance(entry, dict):
        entry = {"level": "restricted", "allowed_users": []}
    allowed = entry.get("allowed_users", [])
    if allowed:
        return username.lower() in [u.lower() for u in allowed]
    level = entry.get("level", "restricted")
    if level == "hidden":
        return False
    if level == "open":
        return True
    return role in ("tester", "superuser")


def _list_agents(username=None, role=None):
    """List available agents (excluding self), filtered by user access."""
    agents = []
    for name in sorted(os.listdir(AGENTS_DIR)):
        agent_path = os.path.join(AGENTS_DIR, name)
        config_path = os.path.join(agent_path, "config.json")
        if os.path.isdir(agent_path) and os.path.exists(config_path):
            if name == "prompt_assistant":
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                agent_id = cfg.get("agent_id", name)
                # Filter by visibility if user info is available
                if username and role and not _can_user_see_agent(agent_id, username, role):
                    continue
                agents.append({
                    "id": agent_id,
                    "dir": name,
                    "name": cfg.get("agent_name", name),
                    "description": cfg.get("description", ""),
                })
            except (json.JSONDecodeError, IOError):
                pass
    return agents


def _load_agent_prompts(agent_dir):
    """Load prompts.json for a given agent directory."""
    path = os.path.join(AGENTS_DIR, agent_dir, "prompts.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_agent_prompts(agent_dir, prompts):
    """Save prompts.json for a given agent directory."""
    path = os.path.join(AGENTS_DIR, agent_dir, "prompts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)


def _build_system_prompt(config, prompts):
    level = config.get("prompt_level", "stringent")
    tvars = {
        "agent_name": config.get("agent_name", "PROMPT Assistant"),
        "description": config.get("description", "prompt specialist"),
    }

    def render(section):
        text = prompts.get(section, "")
        if not text:
            return ""
        try:
            return text.format(**tvars)
        except KeyError:
            return text

    parts = [render("identity")]
    if level in ("tolerant", "stringent"):
        rules = render("rules")
        if rules:
            parts.append(rules)
    if level == "stringent":
        strict = render("strict")
        if strict:
            parts.append(strict)
    return "\n\n".join(parts)


class Agent:
    def __init__(self, system_prompt=None, **kwargs):
        self.client = LLMClient()
        self.model = os.getenv("MISTRAL_MODEL", os.getenv("OLLAMA_MODEL", os.getenv("VLLM_MODEL", "mistral-small-latest")))
        self._config = _load_json("config.json")
        self._prompts = _load_json("prompts.json")
        self.system_prompt = system_prompt or _build_system_prompt(self._config, self._prompts)
        self._sessions = {}

    def _get_prompt(self, prompt_level_override=None):
        if prompt_level_override and self._prompts:
            cfg = dict(self._config)
            cfg["prompt_level"] = prompt_level_override
            return _build_system_prompt(cfg, self._prompts)
        return self.system_prompt

    def _get_session(self, session_id):
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "selected_agent": None,
                "selected_dir": None,
                "loaded_prompts": None,
                "pending_prompts": None,
            }
        return self._sessions[session_id]

    def _handle_command(self, message, session, username=None, role=None):
        """Handle special commands. Returns (handled, response) tuple."""
        msg = message.strip().lower()

        # List agents command — match exact commands or any message mentioning agents + list/show
        _is_list_cmd = msg in ("list agents", "/list", "show agents", "list") or \
            ("agent" in msg and any(w in msg for w in ("list", "show", "which", "available")))
        if _is_list_cmd:
            agents = _list_agents(username, role)
            if not agents:
                return True, "No agents found (other than me)."
            lines = ["Here are the available agents:\n"]
            for i, a in enumerate(agents, 1):
                lines.append(f"**{i}. {a['name']}** (`{a['id']}`)")
                if a['description']:
                    lines.append(f"   {a['description']}")
            lines.append("\nTell me which agent's prompt you'd like to review (by name or number).")
            return True, "\n".join(lines)

        # Select agent by number or name
        agents = _list_agents(username, role)
        selected = None

        # Check if it's a number
        try:
            idx = int(msg) - 1
            if 0 <= idx < len(agents):
                selected = agents[idx]
        except ValueError:
            pass

        # Check if it matches an agent name/id
        if not selected:
            for a in agents:
                if msg == a['id'].lower() or msg == a['name'].lower():
                    selected = a
                    break

        if selected and not session["selected_agent"]:
            session["selected_agent"] = selected["id"]
            session["selected_dir"] = selected["dir"]
            prompts = _load_agent_prompts(selected["dir"])
            if not prompts:
                session["selected_agent"] = None
                session["selected_dir"] = None
                return True, f"Could not load prompts for **{selected['name']}**. Make sure it has a `prompts.json` file."
            session["loaded_prompts"] = prompts
            lines = [f"Loaded prompts for **{selected['name']}** (`{selected['id']}`):\n"]
            lines.append("---")
            lines.append(f"**Identity:**\n{prompts.get('identity', '(empty)')}\n")
            lines.append(f"**Rules:**\n{prompts.get('rules', '(empty)')}\n")
            lines.append(f"**Strict:**\n{prompts.get('strict', '(empty)')}")
            lines.append("---\n")
            lines.append("What would you like me to improve? I can:")
            lines.append("- Review the full prompt and suggest improvements")
            lines.append("- Rewrite a specific section (identity, rules, or strict)")
            lines.append("- Make it more focused, stricter, or friendlier")
            return True, "\n".join(lines)

        # Apply pending changes (with optional edited JSON from the editor)
        if message.strip().startswith("apply_json:") and session.get("selected_agent"):
            raw = message.strip()[len("apply_json:"):]
            try:
                edited = json.loads(raw)
                if "identity" in edited or "rules" in edited or "strict" in edited:
                    session["pending_prompts"] = edited
                else:
                    return True, "The JSON doesn't look like a valid prompts.json (needs 'identity', 'rules', or 'strict' keys)."
            except json.JSONDecodeError:
                return True, "Could not parse the edited JSON. Please fix any syntax errors and try again."
            agent_dir = session["selected_dir"]
            _save_agent_prompts(agent_dir, session["pending_prompts"])
            session["pending_prompts"] = None
            session["loaded_prompts"] = _load_agent_prompts(agent_dir)
            return True, f"Done! The prompts for **{session['selected_agent']}** have been updated. Restart the server or start a new chat with that agent to see the changes."

        if msg in ("yes", "apply", "ok", "confirm", "accept", "do it") and session.get("pending_prompts"):
            agent_dir = session["selected_dir"]
            _save_agent_prompts(agent_dir, session["pending_prompts"])
            session["pending_prompts"] = None
            session["loaded_prompts"] = _load_agent_prompts(agent_dir)
            return True, f"Done! The prompts for **{session['selected_agent']}** have been updated. Restart the server or start a new chat with that agent to see the changes."

        # Reject pending changes
        if msg in ("no", "cancel", "reject", "undo") and session.get("pending_prompts"):
            session["pending_prompts"] = None
            return True, "OK, changes discarded. Tell me what you'd like to adjust instead."

        return False, None

    def chat(self, message, history, **kwargs):
        session_id = kwargs.get("session_id", "default")
        username = kwargs.get("username")
        role = kwargs.get("role")
        session = self._get_session(session_id)

        handled, response = self._handle_command(message, session, username, role)
        if handled:
            return response

        prompt = self._get_prompt(kwargs.get("prompt_level_override"))

        # Add context about selected agent
        context = prompt
        if session.get("selected_agent") and session.get("loaded_prompts"):
            context += f"\n\n--- CONTEXT ---\nYou are currently reviewing the prompts for agent '{session['selected_agent']}'.\nCurrent prompts:\n{json.dumps(session['loaded_prompts'], indent=2)}\n\nWhen you suggest a rewrite, include the FULL updated prompts.json as a JSON code block (```json ... ```) so I can offer to apply it automatically."

        messages = [{"role": "system", "content": context}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        response = self.client.complete(model=self.model, messages=messages)
        result = response.choices[0].message.content

        # Try to detect a proposed JSON in the response
        if session.get("selected_agent"):
            proposed = self._extract_json_proposal(result)
            if proposed:
                session["pending_prompts"] = proposed
                result += self._render_editor(session["selected_agent"], proposed)

        return result

    async def chat_stream(self, message, history, **kwargs):
        session_id = kwargs.get("session_id", "default")
        username = kwargs.get("username")
        role = kwargs.get("role")
        session = self._get_session(session_id)

        handled, response = self._handle_command(message, session, username, role)
        if handled:
            yield ("content", response)
            return

        prompt = self._get_prompt(kwargs.get("prompt_level_override"))

        # Add context about selected agent
        context = prompt
        if session.get("selected_agent") and session.get("loaded_prompts"):
            context += f"\n\n--- CONTEXT ---\nYou are currently reviewing the prompts for agent '{session['selected_agent']}'.\nCurrent prompts:\n{json.dumps(session['loaded_prompts'], indent=2)}\n\nWhen you suggest a rewrite, include the FULL updated prompts.json as a JSON code block (```json ... ```) so I can offer to apply it automatically."

        messages = [{"role": "system", "content": context}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        full_response = ""
        stream = await self.client.stream_async(model=self.model, messages=messages)
        async for chunk in stream:
            content = chunk.data.choices[0].delta.content
            if content:
                full_response += content
                yield ("content", content)

        # Check for proposed JSON after streaming completes
        if session.get("selected_agent"):
            proposed = self._extract_json_proposal(full_response)
            if proposed:
                session["pending_prompts"] = proposed
                yield ("editor", self._render_editor(session["selected_agent"], proposed))

    def _render_editor(self, agent_id, proposed):
        """Render an HTML editor widget for the proposed prompts."""
        import base64
        json_str = json.dumps(proposed, indent=2, ensure_ascii=False)
        b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
        editor_id = f"editor-{id(proposed)}"
        return (
            f'\n\n<div class="prompt-editor" data-json="{b64}">'
            f'<label>Proposed prompts.json for <strong>{agent_id}</strong> — edit below before applying:</label>'
            f'<textarea id="{editor_id}"></textarea>'
            f'<div class="editor-buttons">'
            f'<button class="btn-apply" onclick="applyPromptEdit(\'{agent_id}\', \'{editor_id}\')">Apply Changes</button>'
            f'<button class="btn-discard" onclick="discardPromptEdit(this)">Discard</button>'
            f'</div></div>'
        )

    def _extract_json_proposal(self, text):
        """Try to extract a prompts.json proposal from the response."""
        import re
        # Look for JSON code blocks
        matches = re.findall(r'```json\s*\n([\s\S]*?)\n```', text)
        for match in matches:
            try:
                data = json.loads(match)
                # Validate it looks like a prompts.json
                if "identity" in data or "rules" in data or "strict" in data:
                    return data
            except json.JSONDecodeError:
                continue
        return None
