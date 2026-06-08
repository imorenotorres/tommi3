"""Minimal app.py for agent runner discovery."""
import json, os
_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_dir, "config.json")) as f:
    _cfg = json.load(f)
AGENT_CONFIG = {"id": _cfg["agent_id"], "name": _cfg["agent_name"], "description": _cfg.get("description", "")}
def create_agent(progress_callback=None):
    from agent import Agent
    return Agent(progress_callback=progress_callback)
