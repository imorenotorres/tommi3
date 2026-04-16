"""Data Analysis Verifier — Code validation and reliability assessment.

Verifies that LLM-generated pandas code is safe to execute and references
valid DataFrame columns. Produces reliability badges analogous to SQLVerifier.
"""

import re


# Allowed modules/functions for safe execution
ALLOWED_IMPORTS = {"pandas", "numpy", "matplotlib", "matplotlib.pyplot", "io", "base64"}

# Blocked patterns that should never appear in generated code
BLOCKED_PATTERNS = [
    r'\bimport\s+os\b',
    r'\bimport\s+sys\b',
    r'\bimport\s+subprocess\b',
    r'\bimport\s+shutil\b',
    r'\bimport\s+socket\b',
    r'\bimport\s+requests\b',
    r'\bimport\s+urllib\b',
    r'\b__import__\b',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\bcompile\s*\(',
    r'\bopen\s*\(',
    r'\bos\.\w+',
    r'\bsys\.\w+',
    r'\bsubprocess\.',
    r'\bglobals\s*\(',
    r'\blocals\s*\(',
    r'\bgetattr\s*\(',
    r'\bsetattr\s*\(',
    r'\bdelattr\s*\(',
    r'\b__builtins__\b',
    r'\bbreakpoint\s*\(',
]


class DataVerifier:
    """Verify generated pandas code against a DataFrame schema."""

    def __init__(self, columns: list, dtypes: dict, row_count: int):
        """
        Parameters
        ----------
        columns : list
            List of column names in the DataFrame.
        dtypes : dict
            Mapping of column name to dtype string (e.g. {"score": "float64"}).
        row_count : int
            Number of rows in the DataFrame.
        """
        self._columns = set(c.lower() for c in columns)
        self._columns_original = {c.lower(): c for c in columns}
        self._dtypes = {k.lower(): str(v) for k, v in dtypes.items()}
        self._row_count = row_count

    def verify(self, code: str) -> dict:
        """Verify generated code before execution.

        Returns
        -------
        dict
            verified_columns, unknown_columns, issues, confidence,
            is_safe, has_chart.
        """
        issues = []

        # 1. Safety check — blocked patterns
        is_safe = True
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, code):
                match = re.search(pattern, code).group(0)
                issues.append(f"Blocked pattern: {match}")
                is_safe = False

        # 2. Extract column references from code
        # Match df['col'], df["col"], df.col patterns
        col_refs = set()
        for m in re.finditer(r'''df\[['"](\w+)['"]\]''', code):
            col_refs.add(m.group(1))
        for m in re.finditer(r'''df\.(\w+)''', code):
            attr = m.group(1)
            # Exclude pandas methods
            pandas_methods = {
                "groupby", "mean", "median", "std", "sum", "count", "min", "max",
                "describe", "head", "tail", "info", "value_counts", "sort_values",
                "sort_index", "reset_index", "set_index", "drop", "dropna", "fillna",
                "merge", "join", "concat", "pivot", "pivot_table", "melt", "stack",
                "unstack", "apply", "map", "applymap", "agg", "aggregate",
                "plot", "hist", "boxplot", "corr", "cov", "nunique", "unique",
                "isin", "between", "clip", "replace", "rename", "astype",
                "to_csv", "to_excel", "to_json", "to_dict", "to_numpy",
                "iloc", "loc", "at", "iat", "columns", "index", "dtypes",
                "shape", "values", "T", "transpose", "copy", "sample",
                "nlargest", "nsmallest", "idxmax", "idxmin", "cumsum",
                "cumprod", "diff", "pct_change", "rolling", "expanding",
                "str", "dt", "cat", "abs", "round", "select_dtypes",
                "query", "eval", "pipe", "assign", "where", "mask",
                "duplicated", "drop_duplicates", "iterrows", "itertuples",
            }
            if attr.lower() not in pandas_methods:
                col_refs.add(attr)

        # Also match string references in groupby, etc.
        for m in re.finditer(r'''['"](\w+)['"]''', code):
            candidate = m.group(1)
            if candidate.lower() in self._columns:
                col_refs.add(candidate)

        # 3. Validate columns
        verified_columns = []
        unknown_columns = []
        for col in col_refs:
            if col.lower() in self._columns:
                verified_columns.append(self._columns_original.get(col.lower(), col))
            else:
                unknown_columns.append(col)
                issues.append(f"Unknown column: {col}")

        # 4. Check for type mismatches
        numeric_ops = ["mean", "median", "std", "sum", "corr", "cov"]
        for col in verified_columns:
            dtype = self._dtypes.get(col.lower(), "")
            if any(op in code for op in numeric_ops):
                if "object" in dtype or "str" in dtype:
                    # Only warn if this specific column is used in a numeric operation
                    col_pattern = re.escape(col)
                    if re.search(rf'''['"]{col_pattern}['"].*?\.(?:mean|median|std|sum)''', code):
                        issues.append(f"Numeric operation on text column: {col} ({dtype})")

        # 5. Detect chart generation
        has_chart = bool(re.search(r'\bplot\b|\bhist\b|\bboxplot\b|\bscatter\b|\bbar\b|\bpie\b|\bfigure\b|\bplt\.', code))

        # 6. Calculate confidence
        total_cols = len(verified_columns) + len(unknown_columns)
        if total_cols == 0:
            confidence = 70 if is_safe else 0
        else:
            confidence = round(len(verified_columns) / total_cols * 100)

        if not is_safe:
            confidence = 0

        return {
            "verified_columns": verified_columns,
            "unknown_columns": unknown_columns,
            "issues": issues,
            "confidence": confidence,
            "is_safe": is_safe,
            "has_chart": has_chart,
            "executed_ok": None,
        }

    def verify_with_execution(self, code: str, success: bool, error_msg: str = None) -> dict:
        """Verify code and include execution results."""
        result = self.verify(code)
        result["executed_ok"] = success
        if not success:
            result["confidence"] = max(0, result["confidence"] - 30)
            if error_msg:
                result["issues"].append(f"Execution error: {error_msg[:100]}")
        return result


class DataReliabilityBadge:
    """Render HTML reliability badges for data analysis responses."""

    @staticmethod
    def source_badge(
        verification: dict,
        transparency: str = "crystal_box",
        prompt_level: str = None,
        model_name: str = None,
        is_local_llm: bool = False,
    ) -> str:
        if transparency == "black_box":
            return ""

        is_dev = transparency == "crystal_box"
        confidence = verification.get("confidence", 0)
        issues = verification.get("issues", [])
        verified_cols = verification.get("verified_columns", [])
        unknown_cols = verification.get("unknown_columns", [])
        executed_ok = verification.get("executed_ok")
        has_chart = verification.get("has_chart", False)

        s = 'font-size:0.8em;'
        b = 'font-weight:bold;'

        # Line 1: Agent tuning
        tuning_parts = []
        if model_name:
            llm_location = 'On-premise' if is_local_llm else 'Cloud'
            llm_icon = '/static/icon_llm_local.svg' if is_local_llm else '/static/icon_llm_cloud.svg'
            tuning_parts.append(
                f'<img src="{llm_icon}" style="width:14px;height:14px;vertical-align:middle;"> '
                f'{model_name} ({llm_location})'
            )
        if prompt_level:
            pl_labels = {
                "stringent": "\U0001F6E1\uFE0F Stringent",
                "tolerant": "\u2696\uFE0F Tolerant",
                "lax": "\u26A0\uFE0F Lax",
            }
            tuning_parts.append(pl_labels.get(prompt_level, prompt_level.capitalize()))
        tuning_line = ""
        if tuning_parts:
            tuning_line = (
                f'<span style="{s}"><span style="{b}">Agent tuning:</span> '
                f'{" / ".join(tuning_parts)}</span>'
            )

        # Line 2: Data verification
        total_cols = len(verified_cols) + len(unknown_cols)
        src_parts = []
        if total_cols > 0:
            col_icon = '\U0001F534' if unknown_cols else '\U0001F7E2'
            src_parts.append(f'{col_icon} Columns: {len(verified_cols)}/{total_cols} verified')

        if executed_ok is not None:
            if executed_ok:
                src_parts.append('\U0001F7E2 Code executed OK')
            else:
                src_parts.append('\U0001F534 Execution failed')

        if has_chart:
            src_parts.append('\U0001F4CA Chart generated')

        source_line = ""
        if src_parts:
            source_line = (
                f'<span style="{s}"><span style="{b}">Analysis verification:</span> '
                f'{" / ".join(src_parts)}</span>'
            )

        # Issues
        issues_line = ""
        if is_dev and issues:
            issues_html = "; ".join(issues[:3])
            if len(issues) > 3:
                issues_html += f" (+{len(issues) - 3} more)"
            issues_line = f'<span style="{s}color:#856404;">\u26A0\uFE0F {issues_html}</span>'

        # Line 3: Reliability
        if confidence > 80:
            rel_dot, rel_label = '\U0001F7E2', 'High'
            rel_bg, rel_fg = '#d4edda', '#155724'
        elif confidence >= 50:
            rel_dot, rel_label = '\U0001F7E1', 'Good'
            rel_bg, rel_fg = '#fff3cd', '#856404'
        else:
            rel_dot, rel_label = '\U0001F534', 'Poor'
            rel_bg, rel_fg = '#f8d7da', '#721c24'

        conf_str = f' ({confidence}%)' if is_dev else ''
        reliability_line = (
            f'<span style="{s}"><span style="{b}">Reliability score:</span> '
            f'<span style="background-color:{rel_bg};color:{rel_fg};'
            f'padding:1px 6px;border-radius:3px;font-weight:bold;">'
            f'{rel_dot} {rel_label}{conf_str}</span></span>'
        )

        lines = []
        if tuning_line:
            lines.append(tuning_line)
        if source_line:
            lines.append(source_line)
        if issues_line:
            lines.append(issues_line)
        lines.append(reliability_line)

        if not is_dev:
            lines = [l for l in lines if "Reliability" in l or "Agent tuning" in l]

        body = '<br>'.join(lines)
        return f'<div class="claim-badge-area" style="margin-bottom:10px;">{body}</div>\n\n'
