#!/usr/bin/env python3
"""
Benchmarking Loop - Ejecuta benchmarks con diferentes LLMs y compara resultados

Este script permite ejecutar el benchmark de Pisha2 en bucle, configurando
diferentes LLMs en cada iteración, y luego comparar los resultados.

Uso:
    python benchmarking_loop.py -q                 # Ejecuta todas las preguntas con LLMs por defecto
    python benchmarking_loop.py -q 10              # Ejecuta 10 preguntas con LLMs por defecto
    python benchmarking_loop.py -s                 # Ejecuta todos los escenarios
    python benchmarking_loop.py -s 5               # Ejecuta 5 escenarios
    python benchmarking_loop.py -i                 # Ejecuta solo preguntas de idiomas
    python benchmarking_loop.py --all              # Ejecuta todo (preguntas + escenarios)
    python benchmarking_loop.py -q --llms mistral-large,qwen2.5-coder-14b  # Solo LLMs específicas
    python benchmarking_loop.py --list             # Lista LLMs disponibles

    # Solo comparación (sin ejecutar benchmarks):
    python benchmarking_loop.py --compare-only                    # Usa los últimos resultados de cada LLM
    python benchmarking_loop.py --compare-only --files f1.json,f2.json  # Archivos específicos
    python benchmarking_loop.py --list-results                    # Lista archivos de resultados disponibles

Configuración de LLMs:
    Edita el diccionario LLM_CONFIGS para añadir o modificar configuraciones.
"""

# Activar venv automáticamente si no está activo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps"))
from venv_helper import ensure_venv
ensure_venv()

import os
import json
import argparse
import subprocess
from datetime import datetime

# Directorio del script
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"
LOGS_DIR = SCRIPT_DIR / "logs"

# ============================================================================
# CONFIGURACIONES DE LLM DISPONIBLES
# ============================================================================
# Cada entrada define cómo configurar el .env para esa LLM
# Añade o modifica según tus necesidades

LLM_CONFIGS = {
    # --- Mistral Cloud ---
    "mistral-large": {
        "name": "Mistral Large (Cloud)",
        "provider": "mistral",
        "env_vars": {
            "LLM_PROVIDER": "mistral",
            "MISTRAL_API_KEY": "5csuTcL2eHvm98DvHzrjALMMgqJTiat3",
            "MISTRAL_MODEL": "mistral-large-latest",
        }
    },
    "mistral-small": {
        "name": "Mistral Small (Cloud)",
        "provider": "mistral",
        "env_vars": {
            "LLM_PROVIDER": "mistral",
            "MISTRAL_API_KEY": "5csuTcL2eHvm98DvHzrjALMMgqJTiat3",
            "MISTRAL_MODEL": "mistral-small-latest",
        }
    },
    "codestral": {
        "name": "Codestral (Cloud)",
        "provider": "mistral",
        "env_vars": {
            "LLM_PROVIDER": "mistral",
            "MISTRAL_API_KEY": "5csuTcL2eHvm98DvHzrjALMMgqJTiat3",
            "MISTRAL_MODEL": "codestral-latest",
        }
    },

    # --- Ollama Local ---
    "qwen2.5-coder-14b": {
        "name": "Qwen 2.5 Coder 14B (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen2.5-coder:14b",
        }
    },

    "qwen3:4b": {
        "name": "Qwen 3 4B (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:4b",
        }
    },


    "qwen2.5-coder-7b": {
        "name": "Qwen 2.5 Coder 7B (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen2.5-coder:7b",
        }
    },
    "codestral-local": {
        "name": "Codestral (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "codestral:latest",
        }
    },

    "mistral_7b": {
        "name": "mistral_7b (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "mistral:7b",
        }
    },

    "ministral-3_8b": {
        "name": "ministral-3_8b (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "ministral-3:8b",
        }
    },


    "deepseek-coder:latest": {
        "name": "DeepSeek Coder (Ollama)",
        "provider": "ollama",
        "env_vars": {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "deepseek-coder:6.7b",
        }
    },
}

# LLMs por defecto a ejecutar (puedes modificar esta lista)
# IMPORTANTE: Los nombres deben coincidir con las claves de LLM_CONFIGS
DEFAULT_LLMS = ["mistral_7b", "ministral-3_8b", "mistral-large", "mistral-small","codestral","qwen2.5-coder-14b", "qwen2.5-coder-7b", "codestral-local","qwen3:4b"]
DEFAULT_LLMS = ["mistral_7b", "ministral-3_8b", "mistral-small"]

def write_env_file(config: dict) -> None:
    """Escribe el archivo .env con la configuración especificada."""
    env_content = """

# ================================================================
# LLM Configuration (Auto-generated by benchmarking_loop.py)     #
# ================================================================
"""
    for key, value in config["env_vars"].items():
        env_content += f"{key}={value}\n"

    with open(ENV_FILE, "w") as f:
        f.write(env_content)

    print(f"  [ENV] Configurado: {config['name']}")


def backup_env_file() -> str | None:
    """Guarda una copia del .env actual. Devuelve el contenido o None."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            return f.read()
    return None


def restore_env_file(content: str | None) -> None:
    """Restaura el contenido del .env."""
    if content is not None:
        with open(ENV_FILE, "w") as f:
            f.write(content)
        print("  [ENV] Configuración original restaurada")


def check_ollama_available(base_url: str = "http://localhost:11434") -> bool:
    """Verifica si Ollama está disponible."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def check_model_available(model: str, base_url: str = "http://localhost:11434") -> bool:
    """Verifica si un modelo específico está disponible en Ollama."""
    try:
        import urllib.request
        import json as json_module
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json_module.loads(response.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            # Verificar coincidencia exacta o parcial
            return any(model in m or m.startswith(model.split(":")[0]) for m in models)
    except Exception:
        return False


def run_benchmark(llm_key: str, config: dict, num_questions: int = None, num_scenarios: int = None, run_idiomas: bool = False) -> dict | None:
    """
    Ejecuta el benchmark para una LLM específica.

    Args:
        llm_key: Clave identificadora de la LLM
        config: Configuración de la LLM
        num_questions: Número de preguntas a ejecutar (None = no ejecutar, -1 = todas)
        num_scenarios: Número de escenarios a ejecutar (None = no ejecutar, -1 = todos)
        run_idiomas: Si True, ejecuta solo preguntas de idiomas

    Returns:
        dict con resultados del benchmark o None si falla
    """
    print(f"\n{'='*70}")
    print(f"BENCHMARK: {config['name']}")
    print(f"{'='*70}")

    # Verificar disponibilidad para Ollama
    if config["provider"] == "ollama":
        base_url = config["env_vars"].get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = config["env_vars"].get("OLLAMA_MODEL", "")

        if not check_ollama_available(base_url):
            print(f"  [SKIP] Ollama no disponible en {base_url}")
            return None

        if not check_model_available(model, base_url):
            print(f"  [SKIP] Modelo '{model}' no disponible en Ollama")
            return None

    # Configurar .env
    write_env_file(config)

    # Construir comando
    benchmark_script = SCRIPT_DIR / "benchmark.py"
    cmd = [sys.executable, str(benchmark_script)]

    # Determinar el prefijo de salida
    output_prefix = f"loop_{llm_key}"
    cmd.extend(["-o", output_prefix])

    # Añadir opciones según lo solicitado
    if run_idiomas:
        cmd.append("-i")  # Solo preguntas de idiomas

    if num_questions is not None:
        if num_questions > 0:
            cmd.extend(["-q", str(num_questions)])
        else:
            cmd.append("-q")  # Todas las preguntas

    if num_scenarios is not None:
        if num_scenarios > 0:
            cmd.extend(["-s", str(num_scenarios)])
        else:
            cmd.append("-s")  # Todos los escenarios

    print(f"  [RUN] Ejecutando: {' '.join(cmd)}")
    print()

    try:
        # Ejecutar benchmark como subproceso
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            capture_output=False,  # Mostrar output en tiempo real
            text=True
        )

        if result.returncode != 0:
            print(f"  [ERROR] El benchmark terminó con código {result.returncode}")
            return None

        # Buscar el archivo de resultados más reciente
        result_files = sorted(LOGS_DIR.glob(f"{output_prefix}_*.json"), reverse=True)
        if result_files:
            with open(result_files[0], "r") as f:
                results = json.load(f)
            results["llm_key"] = llm_key
            results["llm_name"] = config["name"]
            results["result_file"] = str(result_files[0])
            return results
        else:
            print(f"  [ERROR] No se encontró archivo de resultados")
            return None

    except Exception as e:
        print(f"  [ERROR] Excepción: {str(e)}")
        return None


def compare_results(all_results: list[dict], scenarios: bool = False) -> dict:
    """
    Compara los resultados de todos los benchmarks.

    Args:
        all_results: Lista de resultados de cada LLM
        scenarios: Si True, compara escenarios en lugar de preguntas

    Returns:
        dict con comparación
    """
    comparison = {
        "timestamp": datetime.now().isoformat(),
        "num_llms": len(all_results),
        "mode": "scenarios" if scenarios else "questions",
        "llms": [],
        "ranking": {
            "by_speed": [],
            "by_success_rate": [],
            "by_sql_errors": [],
        }
    }

    for result in all_results:
        summary = result.get("summary", {})

        if scenarios:
            # Métricas para escenarios
            llm_summary = {
                "key": result.get("llm_key"),
                "name": result.get("llm_name"),
                "total_scenarios": summary.get("total_scenarios", 0),
                "passed_scenarios": summary.get("passed_scenarios", 0),
                "failed_scenarios": summary.get("failed_scenarios", 0),
                "total_steps": summary.get("total_steps", 0),
                "passed_steps": summary.get("passed_steps", 0),
                "failed_steps": summary.get("failed_steps", 0),
                "success_rate": 0,
                "step_success_rate": 0,
                "scenario_errors": [],  # Detalles de errores por escenario
            }
            if llm_summary["total_scenarios"] > 0:
                llm_summary["success_rate"] = round(
                    llm_summary["passed_scenarios"] / llm_summary["total_scenarios"] * 100, 1
                )
            if llm_summary["total_steps"] > 0:
                llm_summary["step_success_rate"] = round(
                    llm_summary["passed_steps"] / llm_summary["total_steps"] * 100, 1
                )

            # Extraer errores de escenarios fallidos
            scenarios_data = result.get("scenarios", [])
            for scenario in scenarios_data:
                if not scenario.get("passed"):
                    scenario_error = {
                        "nombre": scenario.get("nombre", ""),
                        "descripcion": scenario.get("descripcion", ""),
                        "pasos_fallidos": []
                    }
                    for paso in scenario.get("pasos", []):
                        if not paso.get("passed") or paso.get("errors"):
                            paso_error = {
                                "pregunta": paso.get("pregunta", ""),
                                "tipo": paso.get("tipo", ""),
                                "sql": paso.get("sql", ""),
                                "num_results": paso.get("num_results", 0),
                                "errors": paso.get("errors", [])
                            }
                            scenario_error["pasos_fallidos"].append(paso_error)
                    llm_summary["scenario_errors"].append(scenario_error)
        else:
            # Métricas para preguntas directas
            metadata = result.get("metadata", {})
            warmup_data = summary.get("warmup", {})
            num_warmup = metadata.get("num_warmup", 1)

            llm_summary = {
                "key": result.get("llm_key"),
                "name": result.get("llm_name"),
                "total_questions": summary.get("successful", 0) + summary.get("failed", 0),
                "num_warmup": num_warmup,
                "successful": summary.get("successful", 0),
                "failed": summary.get("failed", 0),
                "sql_errors_count": summary.get("sql_errors_count", 0),
                "sql_errors_total": summary.get("sql_errors_total", 0),
                "total_time": summary.get("total_time", 0),
                "avg_time": summary.get("avg_time", 0),
                "avg_time_text_to_sql": summary.get("avg_time_text_to_sql", 0),
                "p90_time": summary.get("p90_time", 0),
                "success_rate": 0,
                "sql_errors_details": [],  # Detalles de errores SQL (si hay hasta 5)
                # Métricas de warm-up
                "warmup": {
                    "total_time": warmup_data.get("total_time", 0),
                    "time_text_to_sql": warmup_data.get("time_text_to_sql", 0),
                    "time_execute": warmup_data.get("time_execute", 0),
                },
            }
            if llm_summary["total_questions"] > 0:
                llm_summary["success_rate"] = round(
                    llm_summary["successful"] / llm_summary["total_questions"] * 100, 1
                )

            # Extraer los detalles de TODOS los fallos (no solo errores SQL explícitos)
            questions = result.get("questions", [])
            for q in questions:
                # Incluir cualquier pregunta que falló o tuvo error SQL (excepto warm-up)
                if not q.get("is_warmup") and (q.get("has_sql_error") or not q.get("success")):
                    error_detail = {
                        "question": q.get("question", ""),
                        "sql_query": q.get("sql_query"),
                        "sql_referencia": q.get("sql_referencia"),  # SQL esperado
                        "error": q.get("error", ""),
                        "success": q.get("success", False),
                        "has_sql_error": q.get("has_sql_error", False),
                        "num_results": q.get("num_results", 0),
                    }
                    llm_summary["sql_errors_details"].append(error_detail)

        comparison["llms"].append(llm_summary)

    # Generar rankings
    if not scenarios:
        # Ranking por velocidad (menor avg_time es mejor)
        comparison["ranking"]["by_speed"] = sorted(
            [llm["key"] for llm in comparison["llms"]],
            key=lambda k: next((l["avg_time"] for l in comparison["llms"] if l["key"] == k), 999)
        )

        # Ranking por errores SQL (menor sql_errors_count es mejor)
        comparison["ranking"]["by_sql_errors"] = sorted(
            [llm["key"] for llm in comparison["llms"]],
            key=lambda k: next((l.get("sql_errors_count", 0) for l in comparison["llms"] if l["key"] == k), 999)
        )

    # Ranking por tasa de éxito (mayor success_rate es mejor)
    comparison["ranking"]["by_success_rate"] = sorted(
        [llm["key"] for llm in comparison["llms"]],
        key=lambda k: next((l["success_rate"] for l in comparison["llms"] if l["key"] == k), 0),
        reverse=True
    )

    return comparison


def print_comparison_report(comparison: dict) -> None:
    """Imprime un informe comparativo en consola."""
    print("\n" + "=" * 80)
    print("INFORME COMPARATIVO DE BENCHMARKS")
    print("=" * 80)
    print(f"Fecha: {comparison['timestamp']}")
    print(f"LLMs evaluadas: {comparison['num_llms']}")
    print(f"Modo: {comparison['mode']}")
    print()

    if comparison["mode"] == "scenarios":
        # Tabla para escenarios
        print(f"{'LLM':<35} {'Escenarios':<15} {'Pasos':<15} {'%Escenarios':<12} {'%Pasos':<10}")
        print("-" * 90)
        for llm in comparison["llms"]:
            scenarios_str = f"{llm['passed_scenarios']}/{llm['total_scenarios']}"
            steps_str = f"{llm['passed_steps']}/{llm['total_steps']}"
            print(f"{llm['name']:<35} {scenarios_str:<15} {steps_str:<15} {llm['success_rate']:>8.1f}%    {llm.get('step_success_rate', 0):>6.1f}%")

        # Comparativa entre LLMs
        print()
        print("COMPARATIVA DE RENDIMIENTO")
        print("-" * 60)

        # Encontrar el mejor y peor en cada métrica
        if comparison["llms"]:
            best_scenarios = max(comparison["llms"], key=lambda x: x["success_rate"])
            worst_scenarios = min(comparison["llms"], key=lambda x: x["success_rate"])
            best_steps = max(comparison["llms"], key=lambda x: x.get("step_success_rate", 0))
            worst_steps = min(comparison["llms"], key=lambda x: x.get("step_success_rate", 0))

            print(f"  Mejor tasa escenarios: {best_scenarios['name']} ({best_scenarios['success_rate']:.1f}%)")
            print(f"  Peor tasa escenarios:  {worst_scenarios['name']} ({worst_scenarios['success_rate']:.1f}%)")
            print(f"  Mejor tasa pasos:      {best_steps['name']} ({best_steps.get('step_success_rate', 0):.1f}%)")
            print(f"  Peor tasa pasos:       {worst_steps['name']} ({worst_steps.get('step_success_rate', 0):.1f}%)")

            # Diferencia entre mejor y peor
            diff_scenarios = best_scenarios["success_rate"] - worst_scenarios["success_rate"]
            diff_steps = best_steps.get("step_success_rate", 0) - worst_steps.get("step_success_rate", 0)
            print()
            print(f"  Diferencia escenarios: {diff_scenarios:.1f} puntos porcentuales")
            print(f"  Diferencia pasos:      {diff_steps:.1f} puntos porcentuales")
    else:
        # Tabla para preguntas (excluyendo warm-up)
        # Mostrar info de warm-up
        num_warmup = comparison["llms"][0].get("num_warmup", 1) if comparison["llms"] else 1
        print(f"Nota: {num_warmup} consulta(s) de warm-up por LLM (excluidas de promedios)")
        print()

        print(f"{'LLM':<35} {'Éxito':<10} {'Err.SQL':<8} {'T.Promedio':<12} {'T.SQL':<12} {'P90':<10} {'Tasa':<8}")
        print("-" * 95)
        for llm in comparison["llms"]:
            success_str = f"{llm['successful']}/{llm['total_questions']}"
            sql_err_str = f"{llm.get('sql_errors_count', 0)}"
            print(f"{llm['name']:<35} {success_str:<10} {sql_err_str:<8} {llm['avg_time']:>8.2f}s "
                  f"{llm['avg_time_text_to_sql']:>8.2f}s {llm['p90_time']:>8.2f}s {llm['success_rate']:>6.1f}%")

        # Mostrar tiempos de warm-up
        print()
        print("TIEMPOS DE WARM-UP (primera consulta)")
        print("-" * 60)
        print(f"{'LLM':<35} {'Total':<12} {'Text-to-SQL':<12}")
        print("-" * 60)
        for llm in comparison["llms"]:
            warmup = llm.get("warmup", {})
            print(f"{llm['name']:<35} {warmup.get('total_time', 0):>8.2f}s {warmup.get('time_text_to_sql', 0):>8.2f}s")

    print()
    print("RANKINGS")
    print("-" * 40)

    if comparison["mode"] != "scenarios":
        print("Por velocidad (más rápido primero):")
        for i, key in enumerate(comparison["ranking"]["by_speed"], 1):
            llm = next((l for l in comparison["llms"] if l["key"] == key), None)
            if llm:
                print(f"  {i}. {llm['name']} ({llm['avg_time']:.2f}s)")

        print()

        print("Por errores SQL (menos errores primero):")
        for i, key in enumerate(comparison["ranking"]["by_sql_errors"], 1):
            llm = next((l for l in comparison["llms"] if l["key"] == key), None)
            if llm:
                print(f"  {i}. {llm['name']} ({llm.get('sql_errors_count', 0)} errores)")

        print()

    print("Por tasa de éxito (mejor primero):")
    for i, key in enumerate(comparison["ranking"]["by_success_rate"], 1):
        llm = next((l for l in comparison["llms"] if l["key"] == key), None)
        if llm:
            print(f"  {i}. {llm['name']} ({llm['success_rate']:.1f}%)")

    # Mostrar errores específicos de escenarios
    if comparison["mode"] == "scenarios":
        llms_with_errors = [llm for llm in comparison["llms"] if llm.get("scenario_errors")]
        if llms_with_errors:
            print()
            print("=" * 80)
            print("DETALLE DE ERRORES POR LLM (ESCENARIOS)")
            print("=" * 80)
            for llm in llms_with_errors:
                total_errors = len(llm["scenario_errors"])
                print(f"\n{'─'*80}")
                print(f"📛 {llm['name']} ({total_errors} escenarios fallidos)")
                print(f"{'─'*80}")
                for scenario_err in llm["scenario_errors"]:
                    print(f"\n  📋 Escenario: {scenario_err['nombre']}")
                    print(f"     Descripción: {scenario_err['descripcion']}")
                    for paso in scenario_err.get("pasos_fallidos", []):
                        print(f"\n     ❌ Paso fallido ({paso['tipo']}):")
                        print(f"        Pregunta: {paso['pregunta']}")
                        if paso.get("sql"):
                            print(f"        SQL generado: {paso['sql']}")
                        print(f"        Resultados: {paso.get('num_results', 0)}")
                        if paso.get("errors"):
                            print(f"        Errores:")
                            for err in paso["errors"]:
                                print(f"          • {err}")

    # Mostrar detalles de todos los errores y fallos
    if comparison["mode"] != "scenarios":
        llms_with_errors = [llm for llm in comparison["llms"] if llm.get("sql_errors_details")]
        if llms_with_errors:
            print()
            print("DETALLE DE ERRORES PRECISOS POR LLM")
            print("=" * 80)
            for llm in llms_with_errors:
                total_errors = len(llm["sql_errors_details"])
                print(f"\n{'─'*80}")
                print(f"📛 {llm['name']} ({total_errors} fallos)")
                print(f"{'─'*80}")
                for i, err in enumerate(llm["sql_errors_details"], 1):
                    # Determinar tipo de error
                    if err.get("has_sql_error"):
                        error_type = "❌ ERROR SQL"
                    elif not err.get("success"):
                        error_type = "⚠️ FALLO"
                    else:
                        error_type = "?"

                    print(f"\n  [{i}] {error_type}")
                    print(f"      Pregunta: {err['question']}")

                    # Mostrar SQL generado (completo)
                    if err.get("sql_query"):
                        print(f"      SQL generado:")
                        print(f"        {err['sql_query']}")

                    # Mostrar SQL de referencia si existe (completo, para comparar)
                    if err.get("sql_referencia"):
                        print(f"      SQL referencia:")
                        print(f"        {err['sql_referencia']}")

                    # Mostrar mensaje de error si existe (completo)
                    if err.get("error"):
                        print(f"      Mensaje error:")
                        print(f"        {err['error']}")

                    # Mostrar número de resultados
                    print(f"      Resultados: {err.get('num_results', 0)}")

    print("=" * 80)


def save_comparison_report(comparison: dict, all_results: list[dict]) -> str:
    """Guarda el informe comparativo en archivos JSON y texto."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Crear directorio de logs si no existe
    LOGS_DIR.mkdir(exist_ok=True)

    # Guardar JSON
    json_file = LOGS_DIR / f"comparison_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "comparison": comparison,
            "results": all_results
        }, f, ensure_ascii=False, indent=2)

    # Guardar informe de texto
    txt_file = LOGS_DIR / f"comparison_{timestamp}.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("INFORME COMPARATIVO DE BENCHMARKS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Fecha: {comparison['timestamp']}\n")
        f.write(f"LLMs evaluadas: {comparison['num_llms']}\n")
        f.write(f"Modo: {comparison['mode']}\n\n")

        if comparison["mode"] == "scenarios":
            f.write(f"{'LLM':<35} {'Escenarios':<15} {'Pasos':<15} {'%Escenarios':<12} {'%Pasos':<10}\n")
            f.write("-" * 90 + "\n")
            for llm in comparison["llms"]:
                scenarios_str = f"{llm['passed_scenarios']}/{llm['total_scenarios']}"
                steps_str = f"{llm['passed_steps']}/{llm['total_steps']}"
                f.write(f"{llm['name']:<35} {scenarios_str:<15} {steps_str:<15} {llm['success_rate']:>8.1f}%    {llm.get('step_success_rate', 0):>6.1f}%\n")

            # Comparativa entre LLMs
            f.write("\nCOMPARATIVA DE RENDIMIENTO\n")
            f.write("-" * 60 + "\n")
            if comparison["llms"]:
                best_scenarios = max(comparison["llms"], key=lambda x: x["success_rate"])
                worst_scenarios = min(comparison["llms"], key=lambda x: x["success_rate"])
                best_steps = max(comparison["llms"], key=lambda x: x.get("step_success_rate", 0))
                worst_steps = min(comparison["llms"], key=lambda x: x.get("step_success_rate", 0))

                f.write(f"  Mejor tasa escenarios: {best_scenarios['name']} ({best_scenarios['success_rate']:.1f}%)\n")
                f.write(f"  Peor tasa escenarios:  {worst_scenarios['name']} ({worst_scenarios['success_rate']:.1f}%)\n")
                f.write(f"  Mejor tasa pasos:      {best_steps['name']} ({best_steps.get('step_success_rate', 0):.1f}%)\n")
                f.write(f"  Peor tasa pasos:       {worst_steps['name']} ({worst_steps.get('step_success_rate', 0):.1f}%)\n")

                diff_scenarios = best_scenarios["success_rate"] - worst_scenarios["success_rate"]
                diff_steps = best_steps.get("step_success_rate", 0) - worst_steps.get("step_success_rate", 0)
                f.write(f"\n  Diferencia escenarios: {diff_scenarios:.1f} puntos porcentuales\n")
                f.write(f"  Diferencia pasos:      {diff_steps:.1f} puntos porcentuales\n")
        else:
            # Mostrar info de warm-up
            num_warmup = comparison["llms"][0].get("num_warmup", 1) if comparison["llms"] else 1
            f.write(f"Nota: {num_warmup} consulta(s) de warm-up por LLM (excluidas de promedios)\n\n")

            f.write(f"{'LLM':<35} {'Éxito':<10} {'Err.SQL':<8} {'T.Promedio':<12} {'T.SQL':<12} {'P90':<10} {'Tasa':<8}\n")
            f.write("-" * 95 + "\n")
            for llm in comparison["llms"]:
                success_str = f"{llm['successful']}/{llm['total_questions']}"
                sql_err_str = f"{llm.get('sql_errors_count', 0)}"
                f.write(f"{llm['name']:<35} {success_str:<10} {sql_err_str:<8} {llm['avg_time']:>8.2f}s "
                        f"{llm['avg_time_text_to_sql']:>8.2f}s {llm['p90_time']:>8.2f}s {llm['success_rate']:>6.1f}%\n")

            # Tiempos de warm-up
            f.write("\nTIEMPOS DE WARM-UP (primera consulta)\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'LLM':<35} {'Total':<12} {'Text-to-SQL':<12}\n")
            f.write("-" * 60 + "\n")
            for llm in comparison["llms"]:
                warmup = llm.get("warmup", {})
                f.write(f"{llm['name']:<35} {warmup.get('total_time', 0):>8.2f}s {warmup.get('time_text_to_sql', 0):>8.2f}s\n")

        f.write("\nRANKINGS\n")
        f.write("-" * 40 + "\n")

        if comparison["mode"] != "scenarios":
            f.write("Por velocidad (más rápido primero):\n")
            for i, key in enumerate(comparison["ranking"]["by_speed"], 1):
                llm = next((l for l in comparison["llms"] if l["key"] == key), None)
                if llm:
                    f.write(f"  {i}. {llm['name']} ({llm['avg_time']:.2f}s)\n")
            f.write("\n")

            f.write("Por errores SQL (menos errores primero):\n")
            for i, key in enumerate(comparison["ranking"]["by_sql_errors"], 1):
                llm = next((l for l in comparison["llms"] if l["key"] == key), None)
                if llm:
                    f.write(f"  {i}. {llm['name']} ({llm.get('sql_errors_count', 0)} errores)\n")
            f.write("\n")

        f.write("Por tasa de éxito (mejor primero):\n")
        for i, key in enumerate(comparison["ranking"]["by_success_rate"], 1):
            llm = next((l for l in comparison["llms"] if l["key"] == key), None)
            if llm:
                f.write(f"  {i}. {llm['name']} ({llm['success_rate']:.1f}%)\n")

        # Guardar errores específicos de escenarios
        if comparison["mode"] == "scenarios":
            llms_with_errors = [llm for llm in comparison["llms"] if llm.get("scenario_errors")]
            if llms_with_errors:
                f.write("\n")
                f.write("=" * 80 + "\n")
                f.write("DETALLE DE ERRORES POR LLM (ESCENARIOS)\n")
                f.write("=" * 80 + "\n")
                for llm in llms_with_errors:
                    total_errors = len(llm["scenario_errors"])
                    f.write(f"\n{'-'*80}\n")
                    f.write(f"{llm['name']} ({total_errors} escenarios fallidos)\n")
                    f.write(f"{'-'*80}\n")
                    for scenario_err in llm["scenario_errors"]:
                        f.write(f"\n  Escenario: {scenario_err['nombre']}\n")
                        f.write(f"  Descripción: {scenario_err['descripcion']}\n")
                        for paso in scenario_err.get("pasos_fallidos", []):
                            f.write(f"\n    Paso fallido ({paso['tipo']}):\n")
                            f.write(f"      Pregunta: {paso['pregunta']}\n")
                            if paso.get("sql"):
                                f.write(f"      SQL generado: {paso['sql']}\n")
                            f.write(f"      Resultados: {paso.get('num_results', 0)}\n")
                            if paso.get("errors"):
                                f.write(f"      Errores:\n")
                                for err in paso["errors"]:
                                    f.write(f"        - {err}\n")

        # Guardar detalles de todos los errores y fallos
        if comparison["mode"] != "scenarios":
            llms_with_errors = [llm for llm in comparison["llms"] if llm.get("sql_errors_details")]
            if llms_with_errors:
                f.write("\n")
                f.write("=" * 80 + "\n")
                f.write("DETALLE DE ERRORES PRECISOS POR LLM\n")
                f.write("=" * 80 + "\n")
                for llm in llms_with_errors:
                    total_errors = len(llm["sql_errors_details"])
                    f.write(f"\n{'-'*80}\n")
                    f.write(f"{llm['name']} ({total_errors} fallos)\n")
                    f.write(f"{'-'*80}\n")
                    for i, err in enumerate(llm["sql_errors_details"], 1):
                        # Determinar tipo de error
                        if err.get("has_sql_error"):
                            error_type = "ERROR SQL"
                        elif not err.get("success"):
                            error_type = "FALLO"
                        else:
                            error_type = "?"

                        f.write(f"\n  [{i}] {error_type}\n")
                        f.write(f"      Pregunta: {err['question']}\n")

                        # Mostrar SQL generado
                        if err.get("sql_query"):
                            f.write(f"      SQL generado:   {err['sql_query']}\n")

                        # Mostrar SQL de referencia si existe (para comparar)
                        if err.get("sql_referencia"):
                            f.write(f"      SQL referencia: {err['sql_referencia']}\n")

                        # Mostrar mensaje de error si existe
                        if err.get("error"):
                            f.write(f"      Mensaje error:  {err['error']}\n")

                        # Mostrar número de resultados
                        f.write(f"      Resultados: {err.get('num_results', 0)}\n")

    print(f"\nInforme guardado en:")
    print(f"  JSON: {json_file}")
    print(f"  Texto: {txt_file}")

    return str(json_file)


def load_existing_results(file_paths: list[str] = None, pattern: str = None) -> list[dict]:
    """
    Carga resultados de benchmarks existentes desde archivos JSON.

    Args:
        file_paths: Lista de rutas a archivos JSON específicos
        pattern: Patrón glob para buscar archivos (ej: "loop_*.json")

    Returns:
        Lista de resultados cargados
    """
    results = []

    if file_paths:
        # Cargar archivos específicos
        for path in file_paths:
            file_path = Path(path)
            if not file_path.exists():
                # Intentar buscar en LOGS_DIR
                file_path = LOGS_DIR / path
            if not file_path.exists():
                print(f"  [WARN] Archivo no encontrado: {path}")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extraer llm_key del nombre del archivo (loop_<llm_key>_timestamp.json)
                filename = file_path.stem
                parts = filename.split("_")
                if len(parts) >= 2 and parts[0] == "loop":
                    # Reconstruir llm_key (puede contener _)
                    llm_key = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]
                else:
                    llm_key = filename

                # Añadir metadatos si no existen
                if "llm_key" not in data:
                    data["llm_key"] = llm_key
                if "llm_name" not in data:
                    # Intentar obtener nombre de la configuración
                    config = LLM_CONFIGS.get(llm_key, {})
                    data["llm_name"] = config.get("name", llm_key)
                data["result_file"] = str(file_path)

                results.append(data)
                print(f"  [OK] Cargado: {file_path.name} ({data.get('llm_name', llm_key)})")

            except Exception as e:
                print(f"  [ERROR] Error cargando {path}: {str(e)}")

    elif pattern:
        # Buscar archivos por patrón
        matching_files = sorted(LOGS_DIR.glob(pattern), reverse=True)
        if not matching_files:
            print(f"  [WARN] No se encontraron archivos con patrón: {pattern}")
            return []

        # Agrupar por LLM y tomar el más reciente de cada uno
        llm_files = {}
        for file_path in matching_files:
            filename = file_path.stem
            parts = filename.split("_")
            if len(parts) >= 2 and parts[0] == "loop":
                llm_key = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]
                if llm_key not in llm_files:
                    llm_files[llm_key] = file_path

        # Cargar los archivos encontrados
        return load_existing_results(file_paths=[str(f) for f in llm_files.values()])

    return results


def list_available_results() -> None:
    """Lista los archivos de resultados disponibles en logs/."""
    print("\nArchivos de resultados disponibles:")
    print("-" * 80)

    # Buscar archivos loop_*.json
    loop_files = sorted(LOGS_DIR.glob("loop_*.json"), reverse=True)

    if not loop_files:
        print("  No se encontraron archivos de resultados.")
        return

    # Agrupar por LLM
    llm_files = {}
    for file_path in loop_files:
        filename = file_path.stem
        parts = filename.split("_")
        if len(parts) >= 2:
            llm_key = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]
            if llm_key not in llm_files:
                llm_files[llm_key] = []
            llm_files[llm_key].append(file_path)

    for llm_key, files in sorted(llm_files.items()):
        config = LLM_CONFIGS.get(llm_key, {})
        llm_name = config.get("name", llm_key)
        print(f"\n  {llm_name}:")
        for f in files[:3]:  # Mostrar máximo 3 por LLM
            print(f"    - {f.name}")
        if len(files) > 3:
            print(f"    ... y {len(files) - 3} más")

    print()
    print("Uso:")
    print("  python benchmarking_loop.py --compare-only")
    print("  python benchmarking_loop.py --compare-only --files archivo1.json,archivo2.json")


def list_available_llms():
    """Lista todas las LLMs configuradas."""
    print("\nLLMs disponibles:")
    print("-" * 60)
    for key, config in LLM_CONFIGS.items():
        provider = config["provider"]
        model = config["env_vars"].get("MISTRAL_MODEL") or config["env_vars"].get("OLLAMA_MODEL")
        default = " (default)" if key in DEFAULT_LLMS else ""
        print(f"  {key:<25} {config['name']:<30}{default}")
    print()
    print(f"LLMs por defecto: {', '.join(DEFAULT_LLMS)}")
    print("\nUso: python benchmarking_loop.py --llms mistral-large,qwen2.5-coder-14b")


def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta benchmarks de Pisha2 con diferentes LLMs y compara resultados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python benchmarking_loop.py -q              # Todas las preguntas con LLMs por defecto
  python benchmarking_loop.py -q 10           # Solo 10 preguntas
  python benchmarking_loop.py -s              # Todos los escenarios
  python benchmarking_loop.py -s 5            # Solo 5 escenarios
  python benchmarking_loop.py --all           # Todo (preguntas + escenarios)
  python benchmarking_loop.py -q -s           # Todas las preguntas y escenarios
  python benchmarking_loop.py -i              # Solo preguntas de idiomas
  python benchmarking_loop.py -q --llms mistral-large,qwen2.5-coder-14b
"""
    )
    parser.add_argument(
        "-q", "--questions",
        type=int,
        nargs="?",
        const=-1,
        default=None,
        metavar="N",
        help="Ejecutar preguntas (sin N = todas, con N = solo N preguntas)"
    )
    parser.add_argument(
        "-s", "--scenarios",
        type=int,
        nargs="?",
        const=-1,
        default=None,
        metavar="N",
        help="Ejecutar escenarios (sin N = todos, con N = solo N escenarios)"
    )
    parser.add_argument(
        "-i", "--idiomas",
        action="store_true",
        help="Ejecutar solo preguntas relacionadas con idiomas"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ejecutar todo: todas las preguntas + todos los escenarios"
    )
    parser.add_argument(
        "--llms", "-l",
        type=str,
        default=None,
        help="Lista de LLMs separadas por coma (ej: mistral-large,qwen2.5-coder-14b)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista todas las LLMs disponibles"
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="No restaurar el .env original al finalizar"
    )
    parser.add_argument(
        "--compare-only", "-c",
        action="store_true",
        help="Solo generar comparación usando resultados existentes (no ejecuta benchmarks)"
    )
    parser.add_argument(
        "--files", "-f",
        type=str,
        default=None,
        help="Archivos JSON específicos para comparar (separados por coma). Usa con --compare-only"
    )
    parser.add_argument(
        "--list-results",
        action="store_true",
        help="Lista los archivos de resultados disponibles en logs/"
    )

    args = parser.parse_args()

    # Listar LLMs disponibles
    if args.list:
        list_available_llms()
        return

    # Listar archivos de resultados disponibles
    if args.list_results:
        list_available_results()
        return

    # Modo solo comparación
    if args.compare_only:
        print("=" * 80)
        print("BENCHMARKING LOOP - Solo Comparación")
        print("=" * 80)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if args.files:
            # Cargar archivos específicos
            file_list = [f.strip() for f in args.files.split(",")]
            print(f"Cargando archivos especificados: {len(file_list)}")
            all_results = load_existing_results(file_paths=file_list)
        else:
            # Cargar los últimos resultados de cada LLM
            print("Buscando últimos resultados de cada LLM...")
            all_results = load_existing_results(pattern="loop_*.json")

        if len(all_results) >= 1:
            # Detectar si son escenarios o preguntas
            is_scenarios = any("scenarios" in r.get("metadata", {}) for r in all_results)
            comparison = compare_results(all_results, scenarios=is_scenarios)
            print_comparison_report(comparison)
            save_comparison_report(comparison, all_results)
        else:
            print("\nNo se encontraron resultados para comparar.")
            print("Usa --list-results para ver archivos disponibles.")
        return

    # Si no se especifica ninguna opción de ejecución, mostrar ayuda
    if args.questions is None and args.scenarios is None and not args.all and not args.idiomas:
        parser.print_help()
        return

    # Determinar qué ejecutar
    num_questions = None
    num_scenarios = None
    run_idiomas = args.idiomas

    if args.all:
        num_questions = -1  # Todas
        num_scenarios = -1  # Todos
    else:
        if args.questions is not None:
            num_questions = args.questions
        if args.scenarios is not None:
            num_scenarios = args.scenarios

    # Determinar qué LLMs ejecutar
    if args.llms:
        llm_keys = [k.strip() for k in args.llms.split(",")]
        # Validar que existan
        for key in llm_keys:
            if key not in LLM_CONFIGS:
                print(f"Error: LLM '{key}' no encontrada. Usa --list para ver disponibles.")
                return
    else:
        llm_keys = DEFAULT_LLMS

    # Descripción del modo
    mode_parts = []
    if run_idiomas:
        mode_parts.append("Preguntas de idiomas")
    if num_questions is not None:
        if num_questions > 0:
            mode_parts.append(f"{num_questions} preguntas")
        else:
            mode_parts.append("Todas las preguntas")
    if num_scenarios is not None:
        if num_scenarios > 0:
            mode_parts.append(f"{num_scenarios} escenarios")
        else:
            mode_parts.append("Todos los escenarios")
    mode_str = " + ".join(mode_parts)

    print("=" * 80)
    print("BENCHMARKING LOOP - Comparación de LLMs")
    print("=" * 80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"LLMs a evaluar: {', '.join(llm_keys)}")
    print(f"Modo: {mode_str}")
    print("=" * 80)

    # Backup del .env original
    original_env = backup_env_file()

    all_results = []
    try:
        for llm_key in llm_keys:
            config = LLM_CONFIGS[llm_key]
            result = run_benchmark(
                llm_key=llm_key,
                config=config,
                num_questions=num_questions,
                num_scenarios=num_scenarios,
                run_idiomas=run_idiomas
            )

            if result:
                all_results.append(result)
            else:
                print(f"  [WARN] Sin resultados para {llm_key}")

    finally:
        # Restaurar .env original
        if not args.no_restore:
            restore_env_file(original_env)

    # Generar comparación si hay resultados
    if len(all_results) >= 1:
        is_scenarios = num_scenarios is not None and num_questions is None
        comparison = compare_results(all_results, scenarios=is_scenarios)
        print_comparison_report(comparison)
        save_comparison_report(comparison, all_results)
    else:
        print("\nNo hay suficientes resultados para comparar.")


if __name__ == "__main__":
    main()
