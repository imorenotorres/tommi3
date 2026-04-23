"""Reliability badge rendering and audit logging shared by all TOMMI agents.

Classes
-------
- ReliabilityBadge: static methods for rendering HTML reliability badges
- AuditLogger: static method for writing JSONL audit log entries (EU AI Act)
"""

import hashlib
import json
import os

from .claims import GroundingAnalyzer


class ReliabilityBadge:
    """Unified reliability badge renderer for all TOMMI agent variants."""

    PROMPT_LEVEL_LABELS = {
        "stringent": "\U0001F6E1\uFE0F Stringent",
        "tolerant":  "\u2696\uFE0F Tolerant",
        "lax":       "\u26A0\uFE0F Lax",
    }

    TRANSPARENCY_LABELS = {
        "crystal_box": "Crystal box",
        "grey_box": "Grey box",
        "black_box": "Black box",
    }

    @staticmethod
    def source_badge(
        source_type: str,
        breakdown: dict = None,
        transparency: str = "crystal_box",
        highlight_config: dict = None,
        gap_analysis: bool = False,
        prompt_level: str = None,
        model_name: str = None,
        is_local_llm: bool = False,
        hallucination_count: int = 0,
    ) -> str:
        """Return an HTML badge indicating the reliability of the response.

        Parameters
        ----------
        source_type : str or None
            "Metadata", "Grounded", "Partial", or "Ungrounded".
        breakdown : dict, optional
            Claim breakdown dict from GroundingAnalyzer.grounding_breakdown()
            or the simpler 2-way dict with grounded_claims/ungrounded_claims.
        transparency : str
            "crystal_box" (full detail), "grey_box" (minimal), or "black_box" (no badge).
        highlight_config : dict, optional
            The ``inline_claim_highlights`` config section.  When ``None``,
            the legend is omitted.
        gap_analysis : bool
            When True, the legend uses "found in data" / "not in data" wording.

        Returns
        -------
        str
            HTML string (or "" when suppressed).
        """
        if source_type is None:
            return ""
        if transparency == "black_box":
            return ""

        is_dev = transparency == "crystal_box"
        three_way = breakdown is not None and "metadata_pct" in breakdown
        total_claims = breakdown.get("total_claims", 0) if breakdown else 0
        confidence = breakdown.get("confidence", 100) if breakdown else 100
        hallucinations = hallucination_count or 0

        # Apply hallucination penalty to confidence (20% per hallucination).
        # This ensures that any hallucination caps reliability at Good at best.
        if hallucinations > 0 and confidence > 0:
            penalty = hallucinations * 20
            confidence = max(0, confidence - penalty)

        # ====== Build compact format ======
        s = 'font-size:0.8em;'  # base style for all lines
        b = 'font-weight:bold;'  # bold for labels
        conf_color = _conf_color(confidence)

        # --- Line 1: Agent tuning ---
        tuning_parts = []
        if model_name:
            llm_location = 'On-premise' if is_local_llm else 'Cloud'
            llm_icon = '/static/icon_llm_local.svg' if is_local_llm else '/static/icon_llm_cloud.svg'
            tuning_parts.append(
                f'<img src="{llm_icon}" style="width:14px;height:14px;vertical-align:middle;"> '
                f'{model_name} ({llm_location})'
            )
        tr_label = ReliabilityBadge.TRANSPARENCY_LABELS.get(transparency, transparency)
        tr_icon = {
            'crystal_box': '/static/icon_crystal_box.svg',
            'grey_box': '/static/icon_grey_box.svg',
            'black_box': '/static/icon_black_box.svg',
        }.get(transparency, '')
        if tr_icon:
            tuning_parts.append(
                f'<img src="{tr_icon}" style="width:14px;height:14px;vertical-align:middle;"> '
                f'{tr_label}'
            )
        else:
            tuning_parts.append(tr_label)
        if prompt_level:
            pl_label = ReliabilityBadge.PROMPT_LEVEL_LABELS.get(
                prompt_level, prompt_level.capitalize()
            )
            tuning_parts.append(pl_label)
        tuning_line = (
            f'<span style="{s}"><span style="{b}">Agent tuning:</span> '
            f'{" / ".join(tuning_parts)}</span>'
        )

        # --- Line 2: Sources (Crystal box and Grey box) ---
        source_line = ""
        if transparency != "black_box" and breakdown and total_claims > 0:
            use_absolute = total_claims < 3
            src_parts = []

            if three_way:
                metadata_n = len(breakdown.get("metadata_claims", []))
                database_n = len(breakdown.get("database_claims", []))
                web_n = len(breakdown.get("web_claims", []))
                ungrounded_n = len(breakdown.get("llm_claims", []))
                if breakdown.get("metadata_pct", 0) > 0 or (use_absolute and metadata_n > 0):
                    val = f'{metadata_n}/{total_claims}' if use_absolute else f'{breakdown["metadata_pct"]}%'
                    src_parts.append(f'\U0001F7E2 Metadata: {val}')
                if breakdown.get("database_pct", 0) > 0 or (use_absolute and database_n > 0):
                    val = f'{database_n}/{total_claims}' if use_absolute else f'{breakdown["database_pct"]}%'
                    src_parts.append(f'\U0001F7E1 Documents: {val}')
                if breakdown.get("web_pct", 0) > 0 or (use_absolute and web_n > 0):
                    val = f'{web_n}/{total_claims}' if use_absolute else f'{breakdown["web_pct"]}%'
                    src_parts.append(f'\U0001F535 Web: {val}')
                if breakdown.get("llm_pct", 0) > 0 or (use_absolute and ungrounded_n > 0):
                    val = f'{ungrounded_n}/{total_claims}' if use_absolute else f'{breakdown["llm_pct"]}%'
                    src_parts.append(f'\U0001F534 LLM: {val}')
            else:
                grounded_n = len(breakdown.get("grounded_claims", []))
                ungrounded_n = len(breakdown.get("ungrounded_claims", []))
                if grounded_n > 0:
                    val = f'{grounded_n}/{total_claims}' if use_absolute else f'{breakdown.get("database_pct", 0)}%'
                    src_parts.append(f'\U0001F7E2 Documents: {val}')
                if ungrounded_n > 0:
                    val = f'{ungrounded_n}/{total_claims}' if use_absolute else f'{breakdown.get("llm_pct", 0)}%'
                    src_parts.append(f'\U0001F534 LLM: {val}')

            # Verification info (inline after sources)
            grounded = total_claims - len(breakdown.get("llm_claims", breakdown.get("ungrounded_claims", [])))
            ver_str = f'(Verified claims: {grounded}/{total_claims})'
            if hallucinations > 0:
                ver_str = f'(\u26A0\uFE0F Hallucinations: {hallucinations} | Verified claims: {grounded}/{total_claims})'

            source_line = (
                f'<span style="{s}"><span style="{b}">Sources:</span> '
                f'{" / ".join(src_parts)} {ver_str}</span>'
            )
        elif transparency != "black_box" and breakdown:
            # No claims — show coverage warning
            coverage_pct = breakdown.get("coverage_pct", 100)
            if coverage_pct == 0:
                source_line = (
                    f'<span style="{s}"><span style="{b}">Sources:</span> '
                    f'\u26A0\uFE0F No verifiable claims found</span>'
                )
            elif coverage_pct < 15:
                source_line = (
                    f'<span style="{s}"><span style="{b}">Sources:</span> '
                    f'\u26A0\uFE0F Low verifiability ({coverage_pct}% checked)</span>'
                )

        # --- Line 3: Reliability score (based on penalized confidence) ---
        high_thr = 100 - 20  # 80% — matches compute_badge_and_breakdown thresholds
        good_thr = 100 - 50  # 50%
        if confidence > high_thr:
            rel_dot = '\U0001F7E2'
            rel_label = 'High'
            rel_bg = '#d4edda'
            rel_fg = '#155724'
        elif confidence >= good_thr:
            rel_dot = '\U0001F7E1'
            rel_label = 'Good'
            rel_bg = '#fff3cd'
            rel_fg = '#856404'
        else:
            rel_dot = '\U0001F534'
            rel_label = 'Poor'
            rel_bg = '#f8d7da'
            rel_fg = '#721c24'

        conf_str = f' ({confidence}%)' if transparency != "black_box" and total_claims > 0 else ''

        # Formula breakdown (Crystal box only, when there are claims)
        formula_str = ''
        if is_dev and total_claims > 0:
            raw = breakdown.get("confidence", 100) if breakdown else 100
            if hallucinations > 0:
                formula_str = (
                    f' = ({raw}% − {hallucinations}×20%)'
                )
            else:
                formula_str = f' = (100% − {breakdown.get("llm_pct", 0)}% LLM)'

        reliability_line = (
            f'<span style="{s}"><span style="{b}">Reliability score:</span> '
            f'<span style="background-color:{rel_bg};color:{rel_fg};'
            f'padding:1px 6px;border-radius:3px;font-weight:bold;">'
            f'{rel_dot} {rel_label}{conf_str}</span>'
            f'<span style="font-size:0.75em;color:#666;">{formula_str}</span></span>'
        )

        # ====== Assemble ======
        lines = [tuning_line]
        if source_line:
            lines.append(source_line)
        lines.append(reliability_line)
        body = '<br>'.join(lines)

        # Grey box: tuning + reliability only (no sources breakdown)
        if not is_dev:
            body = '<br>'.join([tuning_line, reliability_line])

        return f'<div class="claim-badge-area" style="margin-bottom:10px;">{body}</div>\n\n'

    @staticmethod
    def compute_badge_and_breakdown(
        llm_content: str,
        context: str,
        metadata_ctx: str = "",
        web_ctx: str = "",
        transparency: str = "crystal_box",
        green_max: int = 20,
        red_min: int = 50,
        highlight_config: dict = None,
        university_acronyms: list = None,
        is_gap_analysis: bool = False,
        is_not_found: bool = False,
        prompt_level: str = None,
        model_name: str = None,
        is_local_llm: bool = False,
        hallucination_count: int = 0,
    ) -> tuple:
        """Compute reliability badge and per-claim breakdown for a response.

        Parameters
        ----------
        llm_content : str
            The LLM-generated response text.
        context : str
            RAG context (document database retrieval).
        metadata_ctx : str
            Structured metadata context.  When non-empty, the 3-way
            ``GroundingAnalyzer.grounding_breakdown`` is used; otherwise
            the simpler 2-way variant is used.
        web_ctx : str
            Text from web search results.
        transparency : str
            Passed through to ``source_badge``.
        green_max : int
            Maximum LLM % to qualify as "High" reliability.
        red_min : int
            Minimum LLM % to qualify as "Poor" reliability.
        highlight_config : dict, optional
            Passed through to ``source_badge``.
        university_acronyms : list, optional
            Forwarded to ``GroundingAnalyzer.grounding_breakdown``.
        is_gap_analysis : bool
            Passed through to ``source_badge``.
        is_not_found : bool
            When True and llm_pct == 100, the response is treated as a
            legitimate "not found" refusal and labelled "High".

        Returns
        -------
        tuple
            (badge_html, breakdown_dict, reliability_label)
        """
        breakdown = GroundingAnalyzer.grounding_breakdown(
            llm_content,
            metadata_ctx=metadata_ctx,
            rag_ctx=context,
            web_ctx=web_ctx,
            university_acronyms=university_acronyms,
        )

        # Compute penalized confidence (hallucinations reduce it by 10% each)
        raw_confidence = breakdown.get("confidence", 100)
        if hallucination_count > 0:
            penalty = hallucination_count * 10
            penalized = max(0, raw_confidence - penalty)
        else:
            penalized = raw_confidence

        # Determine reliability label from penalized confidence
        # (not from raw llm_pct — hallucinations must affect the label)
        high_threshold = 100 - green_max   # default: 80%
        good_threshold = 100 - red_min     # default: 50%

        # Special case: agent correctly says "not found" — treat as reliable refusal
        if is_not_found and breakdown.get("llm_pct", 0) == 100:
            label = "High"
            source = "Metadata" if "metadata_pct" in breakdown else "Grounded"
        elif penalized > high_threshold:
            label = "High"
            source = "Metadata" if "metadata_pct" in breakdown else "Grounded"
        elif penalized >= good_threshold:
            label = "Good"
            source = "Grounded" if "metadata_pct" in breakdown else "Partial"
        else:
            label = "Poor"
            source = "Ungrounded"

        badge = ReliabilityBadge.source_badge(
            source,
            breakdown,
            transparency=transparency,
            highlight_config=highlight_config,
            gap_analysis=is_gap_analysis,
            prompt_level=prompt_level,
            model_name=model_name,
            is_local_llm=is_local_llm,
            hallucination_count=hallucination_count,
        )

        return badge, breakdown, label


class AuditLogger:
    """JSONL audit logger for EU AI Act compliance."""

    # Stable salt for pseudonymizing usernames within the same deployment.
    # Changing this value will break continuity of user_id across log entries.
    _PSEUDO_SALT = "tommi-uninovis-2026"

    @staticmethod
    def pseudonymize(username: str) -> str:
        """Return a pseudonymized user ID (SHA-256 prefix) for audit logs."""
        raw = f"{AuditLogger._PSEUDO_SALT}:{username}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def log(
        audit_path: str,
        enabled: bool,
        agent_id: str,
        query: str,
        query_type: str,
        breakdown: dict,
        reliability_label: str,
        transparency: str,
        prompt_level: str,
        source_type: str = None,
        context_sources: list = None,
        model_name: str = None,
        is_local_llm: bool = False,
        username: str = None,
    ) -> None:
        """Append a decision event to the JSONL audit log.

        Parameters
        ----------
        audit_path : str
            Filesystem path to the ``.jsonl`` audit file.
        enabled : bool
            When False, the method returns immediately (audit disabled).
        agent_id : str
            Identifier of the agent that produced the response.
        query : str
            The user query.
        query_type : str
            "normal", "followup", "figure", "gap_analysis", etc.
        breakdown : dict
            Claim breakdown dict (2-way or 3-way).
        reliability_label : str
            "High", "Good", or "Poor".
        transparency : str
            Current transparency level.
        prompt_level : str
            Current prompt level ("tolerant" or "stringent").
        source_type : str, optional
            When provided, included in the log entry.
        context_sources : list, optional
            When provided, included in the log entry.
        username : str, optional
            When provided, pseudonymized and included as ``user_id``.
        """
        if not enabled:
            return

        from datetime import datetime, timezone

        # Build breakdown sub-dict — include metadata_pct when present (3-way)
        breakdown_entry = {
            "database_pct": breakdown.get("database_pct", 0),
            "llm_pct": breakdown.get("llm_pct", 0),
        }
        if "metadata_pct" in breakdown:
            breakdown_entry["metadata_pct"] = breakdown.get("metadata_pct", 0)
        if breakdown.get("web_pct", 0) > 0:
            breakdown_entry["web_pct"] = breakdown.get("web_pct", 0)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": AuditLogger.pseudonymize(username) if username else None,
            "agent_id": agent_id,
            "query": query,
            "query_type": query_type,
            "reliability_label": reliability_label,
            "confidence": breakdown.get("confidence", None),
            "coverage_pct": breakdown.get("coverage_pct", None),
            "total_claims": breakdown.get("total_claims", 0),
            "breakdown": breakdown_entry,
            "transparency_level": transparency,
            "prompt_level": prompt_level,
            "model": model_name,
            "is_local_llm": is_local_llm,
        }

        if source_type is not None:
            entry["source_type"] = source_type
        if context_sources is not None:
            entry["context_sources"] = context_sources

        try:
            with open(audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[audit_log] Write error: {e}")


class StudyLogger:
    """Separate JSONL logger for research study data.

    Writes de-identified records keyed by study_id (not username).
    Only contains: study_id, email_domain (country TLD), condition,
    query metrics, and inline questionnaire responses.
    """

    @staticmethod
    def log(
        study_log_path: str,
        study_id: str,
        email_domain: str,
        study_condition: str,
        query_number: int,
        query_text: str,
        transparency_level: str,
        confidence: int = None,
        reliability_label: str = None,
        breakdown: dict = None,
        hallucination_count: int = 0,
        questionnaire: dict = None,
    ) -> None:
        """Append a study event to the dedicated study JSONL log."""
        from datetime import datetime, timezone

        breakdown_entry = {}
        if breakdown:
            breakdown_entry = {
                "metadata_pct": breakdown.get("metadata_pct", 0),
                "database_pct": breakdown.get("database_pct", 0),
                "llm_pct": breakdown.get("llm_pct", 0),
                "web_pct": breakdown.get("web_pct", 0),
            }

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "study_id": study_id,
            "email_domain": email_domain,
            "study_condition": study_condition,
            "query_number": query_number,
            "query_text": query_text,
            "transparency_level": transparency_level,
            "confidence": confidence,
            "reliability_label": reliability_label,
            "breakdown": breakdown_entry,
            "hallucination_count": hallucination_count,
            "questionnaire": questionnaire,
        }

        try:
            with open(study_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[study_log] Write error: {e}")

    @staticmethod
    def update_questionnaire(
        study_log_path: str,
        study_id: str,
        query_number: int,
        questionnaire: dict,
    ) -> bool:
        """Update the questionnaire field of the last matching entry."""
        import os
        if not os.path.exists(study_log_path):
            return False

        lines = []
        updated = False
        with open(study_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the last matching entry (reverse search)
        for i in range(len(lines) - 1, -1, -1):
            try:
                entry = json.loads(lines[i])
                if entry.get("study_id") == study_id and entry.get("query_number") == query_number:
                    entry["questionnaire"] = questionnaire
                    lines[i] = json.dumps(entry, ensure_ascii=False) + "\n"
                    updated = True
                    break
            except json.JSONDecodeError:
                continue

        if updated:
            with open(study_log_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        return updated


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _conf_color(confidence: int) -> str:
    """Return the CSS colour for a given confidence percentage."""
    if confidence >= 80:
        return "#155724"
    elif confidence >= 50:
        return "#856404"
    else:
        return "#721c24"
