#!/usr/bin/env python3
"""
Copy agents between TOMMI 3 and TOMMI Lite platforms.

Handles the structural differences automatically:
  - Import paths in agent.py (../../web vs ../..)
  - Environment files (.env vs env.txt)
  - config.json fields (pinned only exists in tommilite)
  - Text references (TOMMI Lite <-> TOMMI)

Usage:
  python copy_agent.py --from-lite prompt_assistant
  python copy_agent.py --from-tommi3 math_topology
  python copy_agent.py --list-lite
  python copy_agent.py --list-tommi3
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# Platform roots (sibling dirs of this script's grandparent)
SCRIPT_DIR = Path(__file__).resolve().parent
TOMMI3_ROOT = SCRIPT_DIR.parent
TOMMILITE_ROOT = TOMMI3_ROOT.parent / "tommilite"

TOMMI3_AGENTS = TOMMI3_ROOT / "agents"
TOMMILITE_AGENTS = TOMMILITE_ROOT / "agents"

SKIP_DIRS = {"__pycache__", ".DS_Store", "base"}


# ---------------------------------------------------------------------------
# Agent listing
# ---------------------------------------------------------------------------

def list_agents(agents_dir: Path) -> list[dict]:
    """Return a list of {id, name, type, description} for agents in a dir."""
    agents = []
    if not agents_dir.exists():
        return agents
    for d in sorted(agents_dir.iterdir()):
        if not d.is_dir() or d.name in SKIP_DIRS or d.name.startswith("."):
            continue
        config_path = d / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                agents.append({
                    "id": cfg.get("agent_id", d.name),
                    "name": cfg.get("agent_name", d.name),
                    "type": cfg.get("type", "oneshot"),
                    "description": cfg.get("description", ""),
                })
            except (json.JSONDecodeError, IOError):
                agents.append({"id": d.name, "name": d.name, "type": "?", "description": ""})
        elif (d / "app.py").exists():
            agents.append({"id": d.name, "name": d.name, "type": "?", "description": ""})
    return agents


def print_agents(agents: list[dict], platform: str):
    if not agents:
        print(f"No agents found in {platform}.")
        return
    print(f"\n  Agents in {platform}:\n")
    for i, a in enumerate(agents, 1):
        print(f"  {i:2d}. {a['name']} ({a['id']})  [{a['type']}]")
        if a["description"]:
            print(f"      {a['description']}")
    print()


# ---------------------------------------------------------------------------
# Transformation helpers
# ---------------------------------------------------------------------------

def transform_agent_py_to_tommi3(content: str) -> str:
    """Adapt agent.py imports from tommilite to tommi3 layout."""
    # ../../llm_client -> ../../web/llm_client
    content = re.sub(
        r'sys\.path\.insert\(\s*0\s*,\s*os\.path\.join\(\s*os\.path\.dirname\(__file__\)\s*,\s*'
        r'"\.\."s*,\s*"\.\."\s*\)\s*\)',
        'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))',
        content,
    )
    # Also catch the two-level variant with different quoting
    content = re.sub(
        r"""sys\.path\.insert\(\s*0\s*,\s*os\.path\.join\(\s*os\.path\.dirname\(__file__\)\s*,\s*['"]\.\.['"],\s*['"]\.\.['"]"""
        r"""\s*\)\s*\)""",
        'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))',
        content,
    )
    # Replace TOMMI Lite references
    content = content.replace("TOMMI Lite", "TOMMI")
    content = content.replace("tommi lite", "tommi")
    content = content.replace("TommiLite", "Tommi")
    return content


def transform_agent_py_to_lite(content: str) -> str:
    """Adapt agent.py imports from tommi3 to tommilite layout."""
    # ../../web/llm_client -> ../../llm_client
    content = re.sub(
        r"""sys\.path\.insert\(\s*0\s*,\s*os\.path\.join\(\s*os\.path\.dirname\(__file__\)\s*,\s*['"]\.\.['"],\s*['"]\.\.['"],\s*['"]web['"]\s*\)\s*\)""",
        'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))',
        content,
    )
    return content


def transform_config_to_tommi3(cfg: dict) -> dict:
    """Remove tommilite-only fields from config.json."""
    cfg = dict(cfg)
    cfg.pop("pinned", None)
    return cfg


def transform_config_to_lite(cfg: dict) -> dict:
    """No fields to add — tommilite accepts everything tommi3 has."""
    return dict(cfg)


def transform_prompts_to_tommi3(prompts: dict) -> dict:
    """Replace TOMMI Lite references in prompt text."""
    out = {}
    for k, v in prompts.items():
        if isinstance(v, str):
            v = v.replace("TOMMI Lite", "TOMMI")
        out[k] = v
    return out


def transform_prompts_to_lite(prompts: dict) -> dict:
    """Replace bare TOMMI references with TOMMI Lite in prompt text."""
    out = {}
    for k, v in prompts.items():
        if isinstance(v, str):
            # Only replace standalone "TOMMI" (not already "TOMMI Lite" or "TOMMI 3")
            v = re.sub(r'\bTOMMI\b(?!\s*(Lite|3))', 'TOMMI Lite', v)
        out[k] = v
    return out


def convert_env_file(src_dir: Path, dst_dir: Path, to_platform: str):
    """Copy and rename environment config between platforms.

    tommilite uses env.txt, tommi3 uses .env.
    """
    if to_platform == "tommi3":
        src = src_dir / "env.txt"
        dst = dst_dir / ".env"
    else:
        src = src_dir / ".env"
        dst = dst_dir / "env.txt"

    if src.exists():
        shutil.copy2(src, dst)
        print(f"    Converted {src.name} -> {dst.name}")


# ---------------------------------------------------------------------------
# Copy logic
# ---------------------------------------------------------------------------

def copy_agent(agent_id: str, src_agents: Path, dst_agents: Path, to_platform: str):
    """Copy an agent directory with all necessary transformations."""
    src_dir = src_agents / agent_id
    if not src_dir.exists():
        print(f"Error: agent '{agent_id}' not found in {src_agents}")
        sys.exit(1)

    dst_dir = dst_agents / agent_id
    if dst_dir.exists():
        answer = input(f"  Agent '{agent_id}' already exists in destination. Overwrite? [y/N] ")
        if answer.lower() not in ("y", "yes"):
            print("  Aborted.")
            return
        shutil.rmtree(dst_dir)

    print(f"\n  Copying '{agent_id}' -> {to_platform}...\n")

    # Copy the full directory tree first (data/, docs/, etc.)
    shutil.copytree(src_dir, dst_dir, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))

    # --- Transform agent.py ---
    agent_py = dst_dir / "agent.py"
    if agent_py.exists():
        content = agent_py.read_text(encoding="utf-8")
        if to_platform == "tommi3":
            content = transform_agent_py_to_tommi3(content)
        else:
            content = transform_agent_py_to_lite(content)
        agent_py.write_text(content, encoding="utf-8")
        print("    Transformed agent.py imports")

    # --- Transform config.json ---
    config_path = dst_dir / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if to_platform == "tommi3":
            cfg = transform_config_to_tommi3(cfg)
        else:
            cfg = transform_config_to_lite(cfg)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print("    Transformed config.json")

    # --- Transform prompts.json ---
    prompts_path = dst_dir / "prompts.json"
    if prompts_path.exists():
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
        if to_platform == "tommi3":
            prompts = transform_prompts_to_tommi3(prompts)
        else:
            prompts = transform_prompts_to_lite(prompts)
        with open(prompts_path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2, ensure_ascii=False)
        print("    Transformed prompts.json")

    # --- Convert env file ---
    # Remove the source-platform env file from the copy, then convert
    if to_platform == "tommi3":
        old_env = dst_dir / "env.txt"
        if old_env.exists():
            old_env.unlink()
    else:
        old_env = dst_dir / ".env"
        if old_env.exists():
            old_env.unlink()
    convert_env_file(src_dir, dst_dir, to_platform)

    print(f"\n  Done! Agent '{agent_id}' copied to {dst_dir}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Copy agents between TOMMI 3 and TOMMI Lite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python copy_agent.py --from-lite prompt_assistant   Copy from Lite to TOMMI 3
  python copy_agent.py --from-tommi3 math_topology    Copy from TOMMI 3 to Lite
  python copy_agent.py --list-lite                    List agents in Lite
  python copy_agent.py --list-tommi3                  List agents in TOMMI 3
""",
    )
    parser.add_argument("--from-lite", metavar="AGENT_ID",
                        help="Copy an agent from TOMMI Lite to TOMMI 3")
    parser.add_argument("--from-tommi3", metavar="AGENT_ID",
                        help="Copy an agent from TOMMI 3 to TOMMI Lite")
    parser.add_argument("--list-lite", action="store_true",
                        help="List agents in TOMMI Lite")
    parser.add_argument("--list-tommi3", action="store_true",
                        help="List agents in TOMMI 3")
    parser.add_argument("--lite-path", type=Path, default=TOMMILITE_ROOT,
                        help=f"Path to TOMMI Lite root (default: {TOMMILITE_ROOT})")
    parser.add_argument("--tommi3-path", type=Path, default=TOMMI3_ROOT,
                        help=f"Path to TOMMI 3 root (default: {TOMMI3_ROOT})")

    args = parser.parse_args()

    lite_agents = args.lite_path / "agents"
    t3_agents = args.tommi3_path / "agents"

    if not any([args.from_lite, args.from_tommi3, args.list_lite, args.list_tommi3]):
        parser.print_help()
        return

    if args.list_lite:
        if not lite_agents.exists():
            print(f"Error: TOMMI Lite agents dir not found at {lite_agents}")
            sys.exit(1)
        print_agents(list_agents(lite_agents), "TOMMI Lite")

    if args.list_tommi3:
        if not t3_agents.exists():
            print(f"Error: TOMMI 3 agents dir not found at {t3_agents}")
            sys.exit(1)
        print_agents(list_agents(t3_agents), "TOMMI 3")

    if args.from_lite:
        if not lite_agents.exists():
            print(f"Error: TOMMI Lite agents dir not found at {lite_agents}")
            sys.exit(1)
        copy_agent(args.from_lite, lite_agents, t3_agents, "tommi3")

    if args.from_tommi3:
        if not t3_agents.exists():
            print(f"Error: TOMMI 3 agents dir not found at {t3_agents}")
            sys.exit(1)
        copy_agent(args.from_tommi3, t3_agents, lite_agents, "tommilite")


if __name__ == "__main__":
    main()
