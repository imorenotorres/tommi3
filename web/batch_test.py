#!/usr/bin/env python3
"""
Script para lanzar múltiples preguntas a un agente Tommi.

Uso:
    python batch_test.py <agent_id> <evals/preguntas.txt> [--output archivo.json]

Ejemplo:
    python batch_test.py conf26 evals/preguntas_ejemplo.txt
    # Genera: evals/preguntas_ejemplo_respuestas.json

    python batch_test.py conf26 evals/preguntas.txt --output custom.json
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Añadir el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from agent_runner import AgentRunner

# Configuración
SCRIPT_DIR = Path(__file__).parent
AGENTS_PATH = SCRIPT_DIR.parent
TOKKI_EXECUTABLE = SCRIPT_DIR.parent.parent / "tokki_docs_y_ejemplos" / "tokki"


async def run_batch_test(agent_id: str, questions: list[str], use_session: bool = False):
    """Ejecuta una lista de preguntas contra un agente"""
    runner = AgentRunner(
        agents_base_path=str(AGENTS_PATH),
        tokki_executable=str(TOKKI_EXECUTABLE)
    )

    agent = runner.get_agent(agent_id)
    if not agent:
        # Intentar descubrir agentes
        runner.discover_agents()
        agent = runner.get_agent(agent_id)
        if not agent:
            print(f"Error: Agente '{agent_id}' no encontrado")
            print("Agentes disponibles:")
            for a in runner.discover_agents():
                print(f"  - {a.id}: {a.name}")
            return None

    print(f"Agente: {agent.name} ({agent.id})")
    print(f"Preguntas a procesar: {len(questions)}")
    print("-" * 50)

    results = []
    session_id = None

    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question[:60]}...")

        try:
            result = await runner.run_query(
                agent_id=agent_id,
                message=question,
                session_id=session_id if use_session else None
            )

            # Guardar session_id para mantener contexto si se desea
            if use_session and result.session_id:
                session_id = result.session_id

            results.append({
                "question": question,
                "response": result.response,
                "session_id": result.session_id,
                "success": True
            })
            print(f"    ✓ Respuesta recibida ({len(result.response)} chars)")

        except Exception as e:
            results.append({
                "question": question,
                "response": None,
                "error": str(e),
                "success": False
            })
            print(f"    ✗ Error: {e}")

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(questions),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "use_session": use_session,
        "results": results
    }


def load_questions(file_path: str) -> list[str]:
    """Carga preguntas desde un archivo de texto (una por línea)"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    return questions


def main():
    parser = argparse.ArgumentParser(
        description="Lanza múltiples preguntas a un agente Tokki"
    )
    parser.add_argument("agent_id", nargs="?", help="ID del agente (ej: conf26, algoria)")
    parser.add_argument("questions_file", nargs="?", help="Archivo con preguntas (una por línea)")
    parser.add_argument("--output", "-o", help="Archivo de salida JSON (por defecto: <input>_respuestas.json)")
    parser.add_argument("--session", "-s", action="store_true",
                        help="Mantener sesión entre preguntas (contexto)")
    parser.add_argument("--list-agents", "-l", action="store_true",
                        help="Listar agentes disponibles y salir")
    parser.add_argument("--no-save", action="store_true",
                        help="No guardar resultados, solo mostrar en consola")

    args = parser.parse_args()

    # Listar agentes
    if args.list_agents:
        runner = AgentRunner(str(AGENTS_PATH), str(TOKKI_EXECUTABLE))
        print("Agentes disponibles:")
        for agent in runner.discover_agents():
            print(f"  - {agent.id}: {agent.name}")
        return

    # Verificar argumentos requeridos
    if not args.agent_id or not args.questions_file:
        parser.print_help()
        return

    # Cargar preguntas
    try:
        questions = load_questions(args.questions_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    if not questions:
        print("Error: No se encontraron preguntas en el archivo")
        return

    # Ejecutar test
    results = asyncio.run(run_batch_test(args.agent_id, questions, args.session))

    if results:
        print("-" * 50)
        print(f"Completado: {results['successful']}/{results['total_questions']} exitosas")

        # Determinar archivo de salida
        if args.no_save:
            # Solo mostrar en consola
            print("\nRespuestas:")
            for r in results["results"]:
                print(f"\nQ: {r['question']}")
                if r["success"]:
                    response = r["response"][:200] + "..." if len(r["response"]) > 200 else r["response"]
                    print(f"A: {response}")
                else:
                    print(f"Error: {r['error']}")
        else:
            # Guardar resultados
            if args.output:
                output_path = Path(args.output)
            else:
                # Generar nombre: <input>_respuestas.json
                input_path = Path(args.questions_file)
                output_path = input_path.parent / f"{input_path.stem}_respuestas.json"

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"Resultados guardados en: {output_path}")


if __name__ == "__main__":
    main()
