"""
Liana's Assistant — ExcelAnalyst agent.
Reads CSV/Excel files and answers data analysis questions using LLM-generated pandas code.
"""

import os
import sys
import io
import re
import json
import base64
import logging
import traceback

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "web"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps"))

from llm_client import LLMClient
from data_verifier import DataVerifier, DataReliabilityBadge

# Load config
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_config_path, "r", encoding="utf-8") as _f:
    _agent_config = json.load(_f)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("excel_analyst")


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.model = self._get_model()
        self._config = _agent_config
        self._transparency = self._config.get("transparency_level", "crystal_box")
        self._prompt_level = self._config.get("prompt_level", "stringent")
        self._max_rows = self._config.get("max_rows_display", 50)
        self._sessions = {}  # session_id -> session state
        # Auto-load first data file found in data/ directory
        self._auto_load_data()

    def _get_model(self) -> str:
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
        if provider == "ollama":
            return os.getenv("OLLAMA_MODEL", "mistral")
        elif provider == "vllm":
            return os.getenv("VLLM_MODEL", "mistral-large-latest")
        else:
            return os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    def _auto_load_data(self):
        """Auto-load the first CSV/Excel file found in data/ directory."""
        # Try multiple paths to find the data directory
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
            os.path.join(os.path.dirname(_config_path), "data"),
        ]
        data_dir = None
        for d in candidates:
            if os.path.isdir(d):
                data_dir = d
                break
        if not data_dir:
            logger.warning(f"Data directory not found. Tried: {candidates}")
            return
        for f in sorted(os.listdir(data_dir)):
            if f.endswith(('.csv', '.xlsx', '.xls')):
                filepath = os.path.join(data_dir, f)
                logger.info(f"Auto-loading data file: {f}")
                try:
                    self.load_file(filepath, session_id="default")
                except Exception as e:
                    logger.error(f"Failed to auto-load {f}: {e}")
                return
        logger.info(f"No CSV/Excel files found in {data_dir}")

    def _get_session(self, session_id: str) -> dict:
        if session_id not in self._sessions:
            # For new sessions, inherit data from default session if available
            default = self._sessions.get("default", {})
            self._sessions[session_id] = {
                "df": default.get("df"),
                "filename": default.get("filename"),
                "schema_info": default.get("schema_info"),
                "history": [],
            }
        return self._sessions[session_id]

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def load_file(self, file_path: str, session_id: str = "default") -> str:
        """Load a CSV or Excel file into the session."""
        import pandas as pd

        state = self._get_session(session_id)
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext == ".csv":
                df = pd.read_csv(file_path)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
            else:
                return f"Unsupported file format: {ext}. Please use .csv, .xlsx, or .xls"

            state["df"] = df
            state["filename"] = filename
            state["schema_info"] = self._build_schema_info(df)
            state["history"] = []

            logger.info(f"Loaded {filename}: {df.shape[0]} rows, {df.shape[1]} columns")
            return self._format_load_summary(df, filename)

        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return f"Error loading file: {e}"

    def load_file_bytes(self, file_bytes: bytes, filename: str, session_id: str = "default") -> str:
        """Load file from bytes (for web upload)."""
        import pandas as pd

        state = self._get_session(session_id)
        ext = os.path.splitext(filename)[1].lower()

        try:
            buf = io.BytesIO(file_bytes)
            if ext == ".csv":
                df = pd.read_csv(buf)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(buf)
            else:
                return f"Unsupported file format: {ext}. Please use .csv, .xlsx, or .xls"

            state["df"] = df
            state["filename"] = filename
            state["schema_info"] = self._build_schema_info(df)
            state["history"] = []

            logger.info(f"Loaded {filename}: {df.shape[0]} rows, {df.shape[1]} columns")
            return self._format_load_summary(df, filename)

        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return f"Error loading file: {e}"

    def _build_schema_info(self, df) -> str:
        """Build a concise schema description for the LLM prompt."""
        lines = [f"DATA SCHEMA ({df.shape[0]} rows, {df.shape[1]} columns):"]
        lines.append("")
        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = df[col].count()
            null_pct = round((1 - non_null / len(df)) * 100, 1) if len(df) > 0 else 0

            if dtype in ("object", "string", "str", "category") or "str" in dtype:
                unique = df[col].nunique()
                if unique <= 15:
                    # Show ALL values for low-cardinality columns (exact match is critical)
                    all_vals = df[col].dropna().unique().tolist()
                    vals_str = ", ".join(f'"{s}"' for s in all_vals)
                    lines.append(f"- {col} (text, {unique} unique values, {null_pct}% null): ALL VALUES: {vals_str}")
                else:
                    sample = df[col].dropna().unique()[:5].tolist()
                    sample_str = ", ".join(f'"{s}"' for s in sample)
                    lines.append(f"- {col} (text, {unique} unique values, {null_pct}% null): e.g. {sample_str}")
            elif "int" in dtype or "float" in dtype:
                lines.append(f"- {col} ({dtype}, {null_pct}% null): min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.2f}")
            elif "datetime" in dtype:
                lines.append(f"- {col} (datetime, {null_pct}% null): from {df[col].min()} to {df[col].max()}")
            else:
                lines.append(f"- {col} ({dtype}, {null_pct}% null)")

        return "\n".join(lines)

    def _format_load_summary(self, df, filename: str) -> str:
        """Format a summary of the loaded file."""
        lines = [f"**File loaded: {filename}**\n"]
        lines.append(f"- **Rows:** {df.shape[0]}")
        lines.append(f"- **Columns:** {df.shape[1]}")
        lines.append(f"\n**Column overview:**\n")

        for col in df.columns:
            dtype = str(df[col].dtype)
            if dtype in ("object", "string", "str", "category") or "str" in dtype:
                unique = df[col].nunique()
                lines.append(f"- `{col}` — text ({unique} unique values)")
            elif "int" in dtype or "float" in dtype:
                lines.append(f"- `{col}` — numeric (min: {df[col].min()}, max: {df[col].max()})")
            elif "datetime" in dtype:
                lines.append(f"- `{col}` — date")
            else:
                lines.append(f"- `{col}` — {dtype}")

        lines.append(f"\nYou can now ask me questions about this data. For example:")
        lines.append(f'- "Show descriptive statistics"')
        lines.append(f'- "Split by {df.columns[0]} and show the distribution of {df.columns[-1]}"')
        lines.append(f'- "Make a chart of {df.columns[0]} vs {df.columns[-1] if len(df.columns) > 1 else df.columns[0]}"')
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Code generation
    # ------------------------------------------------------------------

    def _generate_code(self, question: str, schema_info: str, history: list) -> str:
        """Use LLM to generate pandas code for the user's question."""
        system_prompt = f"""You are Liana's Assistant, a data analysis expert. You write Python pandas code to answer questions about a DataFrame called `df`.

RULES:
1. The DataFrame is already loaded as `df`. Do NOT load any files.
2. `pd` (pandas), `np` (numpy), and `plt` (matplotlib.pyplot) are ALREADY imported. Do NOT write import statements — just use pd, np, plt, and df directly.
3. For charts: use plt.figure(), then plot, then plt.tight_layout(). The chart will be captured automatically.
4. For tables/text results: assign the result to a variable called `result`. Print it with print(result).
5. For charts with ratios/proportions: use normalize=True in value_counts() or compute proportions manually.
6. Always use column names AND values EXACTLY as they appear in the schema (case-sensitive). For example, use "Universidad de Málaga (España)" not "UMA", and "Estudiante de Grado" not "Estudiante de grado". When the schema shows ALL VALUES, use those exact strings.
7. Return ONLY the Python code inside a ```python code block. No explanations outside the code block.
8. If the question asks for a figure, ALWAYS create one using matplotlib.
9. For grouped bar charts or stacked charts, handle the data properly — use unstack(), pivot_table(), or crosstab().
10. Add a title and axis labels to every chart.

{schema_info}
"""
        messages = [{"role": "system", "content": system_prompt}]

        # Add recent history for context
        for h in history[-4:]:
            messages.append({"role": "user", "content": h["question"]})
            messages.append({"role": "assistant", "content": f"```python\n{h['code']}\n```"})

        messages.append({"role": "user", "content": question})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages,
            max_tokens=2048,
        )

        content = response.choices[0].message.content
        return self._extract_code(content)

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Try ```python block first
        match = re.search(r'```python\s*\n(.*?)```', response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try generic ``` block
        match = re.search(r'```\s*\n(.*?)```', response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If no code block, try to extract lines that look like code
        lines = []
        for line in response.split('\n'):
            stripped = line.strip()
            if stripped and (stripped.startswith('df') or stripped.startswith('plt.')
                           or stripped.startswith('result') or stripped.startswith('print')
                           or stripped.startswith('import') or '=' in stripped):
                lines.append(line)

        return '\n'.join(lines) if lines else response

    # ------------------------------------------------------------------
    # Safe execution
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_imports(code: str) -> str:
        """Remove import lines from generated code (pd/np/plt are pre-loaded)."""
        lines = []
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                # Keep only safe imports that are already in the namespace
                continue
            lines.append(line)
        return '\n'.join(lines)

    def _execute_code(self, code: str, df) -> dict:
        """Execute pandas code in a restricted environment.

        Returns dict with: success, output (text), chart_base64, error.
        """
        import pandas as pd
        import numpy as np

        # Strip import statements — pd, np, plt are pre-loaded
        code = self._strip_imports(code)

        result = {"success": False, "output": "", "chart_base64": None, "error": None}

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            # Close any existing figures
            plt.close('all')

            # Safe execution namespace
            exec_globals = {
                "df": df.copy(),
                "pd": pd,
                "np": np,
                "plt": plt,
                "io": io,
                "base64": base64,
                "__builtins__": {
                    "print": print,
                    "len": len,
                    "range": range,
                    "enumerate": enumerate,
                    "zip": zip,
                    "sorted": sorted,
                    "reversed": reversed,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "abs": abs,
                    "round": round,
                    "int": int,
                    "float": float,
                    "str": str,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "type": type,
                    "isinstance": isinstance,
                    "True": True,
                    "False": False,
                    "None": None,
                    "ValueError": ValueError,
                    "TypeError": TypeError,
                    "KeyError": KeyError,
                    "IndexError": IndexError,
                },
            }

            exec(code, exec_globals)

            # Capture text output
            result["output"] = captured.getvalue()

            # Check if a result variable was set
            if "result" in exec_globals and exec_globals["result"] is not None:
                res = exec_globals["result"]
                if isinstance(res, pd.DataFrame):
                    if len(res) > self._max_rows:
                        result["output"] += f"\n(Showing first {self._max_rows} of {len(res)} rows)\n"
                        result["output"] += res.head(self._max_rows).to_string()
                    else:
                        result["output"] += res.to_string()
                elif isinstance(res, pd.Series):
                    result["output"] += res.to_string()
                else:
                    result["output"] += str(res)

            # Capture chart if one was created
            if plt.get_fignums():
                buf = io.BytesIO()
                plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
                buf.seek(0)
                result["chart_base64"] = base64.b64encode(buf.read()).decode('utf-8')
                plt.close('all')

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Execution error: {e}\n{traceback.format_exc()}")

        finally:
            sys.stdout = old_stdout

        return result

    # ------------------------------------------------------------------
    # Main chat
    # ------------------------------------------------------------------

    def chat(self, user_message: str, history: list = None, session_id: str = None,
             transparency_override: str = None, model_override: str = None,
             prompt_level_override: str = None, **kwargs) -> str:
        """Process a data analysis question."""
        # Use per-request overrides or fall back to instance defaults
        transparency = transparency_override or self._transparency
        model = model_override or self.model
        prompt_level = prompt_level_override or self._prompt_level

        if session_id is None:
            session_id = "default"

        state = self._get_session(session_id)

        # Check if data is loaded
        if state["df"] is None:
            return ("No data loaded yet. Please upload a CSV or Excel file first.\n\n"
                    "You can upload a file using the upload button, or place a file in "
                    "the `data/` folder and I'll load it automatically.")

        df = state["df"]
        schema_info = state["schema_info"]

        logger.info(f"Question: {user_message}")

        # Generate code
        code = self._generate_code(user_message, schema_info, state["history"])
        logger.info(f"Generated code:\n{code}")

        # Verify code
        verifier = DataVerifier(
            columns=list(df.columns),
            dtypes={c: str(df[c].dtype) for c in df.columns},
            row_count=len(df),
        )
        pre_check = verifier.verify(code)

        # Prompt level enforcement
        if prompt_level == "stringent" and not pre_check["is_safe"]:
            badge = DataReliabilityBadge.source_badge(
                pre_check, transparency=transparency,
                prompt_level=prompt_level,
                model_name=model,
                is_local_llm=os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm"),
            )
            issues_text = "\n".join(f"- {i}" for i in pre_check["issues"])
            return (
                f"{badge}**Generated code:**\n```python\n{code}\n```\n\n"
                f"**Code verification failed (stringent mode):**\n{issues_text}\n\n"
                f"The code was **not executed** because it contains unsafe patterns."
            )

        if prompt_level == "stringent" and pre_check["unknown_columns"]:
            badge = DataReliabilityBadge.source_badge(
                pre_check, transparency=transparency,
                prompt_level=prompt_level,
                model_name=model,
                is_local_llm=os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm"),
            )
            issues_text = "\n".join(f"- {i}" for i in pre_check["issues"])
            return (
                f"{badge}**Generated code:**\n```python\n{code}\n```\n\n"
                f"**Code verification failed (stringent mode):**\n{issues_text}\n\n"
                f"The code references unknown columns. Available columns: {', '.join(df.columns)}"
            )

        # Execute code
        exec_result = self._execute_code(code, df)

        # Post-execution verification
        verification = verifier.verify_with_execution(
            code, exec_result["success"], exec_result.get("error")
        )

        is_local = os.getenv("LLM_PROVIDER", "mistral").lower() in ("ollama", "vllm")
        badge = DataReliabilityBadge.source_badge(
            verification, transparency=transparency,
            prompt_level=prompt_level,
            model_name=model,
            is_local_llm=is_local,
        )

        # Save to history
        state["history"].append({
            "question": user_message,
            "code": code,
            "success": exec_result["success"],
        })

        # Format response
        parts = [badge]

        if transparency == "crystal_box":
            parts.append(f"**Generated code:**\n```python\n{code}\n```\n\n")

        if exec_result["success"]:
            if exec_result["output"].strip():
                parts.append(f"**Results:**\n\n```\n{exec_result['output'].strip()}\n```\n")
            if exec_result["chart_base64"]:
                parts.append(f'\n\n<img src="data:image/png;base64,{exec_result["chart_base64"]}" style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin:8px 0;">\n')
            if not exec_result["output"].strip() and not exec_result["chart_base64"]:
                parts.append("The code executed successfully but produced no output.\n")
        else:
            parts.append(f"**Error:** {exec_result['error']}\n")

        if prompt_level == "tolerant" and pre_check["issues"]:
            issues_text = ", ".join(pre_check["issues"])
            parts.append(f"\n*Warning: {issues_text}*\n")

        return "\n".join(parts)

    async def chat_stream(self, user_message: str, history: list = None, session_id: str = None,
                          transparency_override: str = None, model_override: str = None,
                          prompt_level_override: str = None, **kwargs):
        """Streaming version — yields (event_type, content) tuples."""
        if session_id is None:
            session_id = "default"

        state = self._get_session(session_id)

        if state["df"] is None:
            yield ("content", "No data loaded yet. Please upload a CSV or Excel file first.")
            return

        yield ("status", "Generating analysis code...")
        # The actual analysis is fast enough to not need true streaming
        result = self.chat(user_message, history, session_id,
                           transparency_override=transparency_override,
                           model_override=model_override,
                           prompt_level_override=prompt_level_override)

        # Split badge from content
        if '<div class="claim-badge-area"' in result:
            badge_end = result.index('</div>') + len('</div>\n\n')
            badge = result[:badge_end]
            content = result[badge_end:]
            yield ("badge", badge)
            yield ("content", content)
        else:
            yield ("content", result)

    def get_schema(self, session_id: str = "default") -> str:
        """Return the current DataFrame schema."""
        state = self._get_session(session_id)
        if state["schema_info"]:
            return state["schema_info"]
        return "No data loaded."

    @property
    def name(self) -> str:
        return self._config.get("agent_name", "Liana's Assistant")
