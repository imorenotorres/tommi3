#!/usr/bin/env python3
"""
CLI interactivo para agentes TOMMI
Permite interactuar con agentes directamente desde el terminal sin servidor web.
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import asyncio
import sys
from pathlib import Path

from agent_runner import AgentRunner


def print_agents(agents):
    """Muestra la lista de agentes disponibles"""
    print("\nAgentes disponibles:")
    print("-" * 50)
    for agent in agents:
        print(f"  {agent.id:<20} - {agent.name}")
    print("-" * 50)


def print_welcome(agent):
    """Muestra el mensaje de bienvenida del agente"""
    print(f"\n{'='*60}")
    print(f"  {agent.name}")
    print(f"{'='*60}")
    if agent.description:
        print(f"\n{agent.description}")
    if agent.welcome_message:
        print(f"\n{agent.welcome_message}")
    if agent.example_queries:
        print("\nEjemplos de preguntas:")
        for q in agent.example_queries[:3]:
            print(f"  - {q}")
    print(f"\n(Escribe 'salir' o 'exit' para terminar)")
    print("-" * 60)


async def interactive_loop(runner: AgentRunner, agent_id: str):
    """Loop principal de interacción"""
    agent = runner.get_agent(agent_id)
    if not agent:
        print(f"Error: Agente '{agent_id}' no encontrado")
        return

    print_welcome(agent)

    session_id = None

    while True:
        try:
            print()
            user_input = input("Tú: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ('salir', 'exit', 'quit', 'q'):
                print("\n¡Hasta luego!")
                break

            print("\nAgente: ", end="", flush=True)

            result = await runner.run_query(agent_id, user_input, session_id)
            session_id = result.session_id

            print(result.response)

        except KeyboardInterrupt:
            print("\n\n¡Hasta luego!")
            break
        except EOFError:
            print("\n\n¡Hasta luego!")
            break
        except Exception as e:
            print(f"\nError: {e}")


def main():
    # Configurar path base (carpeta agents/ en el directorio padre de web/)
    base_path = Path(__file__).parent.parent / "agents"

    runner = AgentRunner(str(base_path))
    agents = runner.discover_agents()

    if not agents:
        print("No se encontraron agentes disponibles.")
        sys.exit(1)

    # Si se pasa un agente como argumento
    if len(sys.argv) > 1:
        agent_id = sys.argv[1]

        if agent_id in ('-l', '--list'):
            print_agents(agents)
            sys.exit(0)

        if agent_id in ('-h', '--help'):
            print(f"Uso: python {sys.argv[0]} [agent_id]")
            print(f"     python {sys.argv[0]} -l          (listar agentes)")
            print(f"\nEjemplo: python {sys.argv[0]} conf26_local")
            sys.exit(0)

        asyncio.run(interactive_loop(runner, agent_id))
    else:
        # Mostrar lista y pedir selección
        print_agents(agents)
        print("\nIntroduce el ID del agente (o 'salir' para terminar):")

        try:
            agent_id = input("> ").strip()
            if agent_id.lower() in ('salir', 'exit', 'quit', 'q'):
                sys.exit(0)
            asyncio.run(interactive_loop(runner, agent_id))
        except (KeyboardInterrupt, EOFError):
            print("\n¡Hasta luego!")
            sys.exit(0)


if __name__ == "__main__":
    main()
