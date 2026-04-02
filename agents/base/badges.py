"""Reliability badge rendering and audit logging shared by all TOMMI agents.

Classes
-------
- ReliabilityBadge: static methods for rendering HTML reliability badges
- AuditLogger: static method for writing JSONL audit log entries (EU AI Act)
"""

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

    @staticmethod
    def source_badge(
        source_type: str,
        breakdown: dict = None,
        transparency: str = "crystal_box",
        highlight_config: dict = None,
        gap_analysis: bool = False,
        prompt_level: str = None,
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
        confidence = breakdown.get("confidence", 100) if breakdown else 100

        # Detect 3-way vs 2-way mode from breakdown keys
        three_way = breakdown is not None and "metadata_pct" in breakdown

        if breakdown and breakdown.get("total_claims", 0) > 0:
            total_claims = breakdown["total_claims"]
            use_absolute = total_claims < 3  # Too few claims for meaningful %

            if three_way:
                # --- 3-way mode: Metadata / Database / LLM ---
                metadata_n = len(breakdown.get("metadata_claims", []))
                database_n = len(breakdown.get("database_claims", []))
                ungrounded_n = len(breakdown.get("llm_claims", []))

                # percentage string (development only)
                if is_dev:
                    parts = []
                    if breakdown["metadata_pct"] > 0 or (use_absolute and metadata_n > 0):
                        if use_absolute:
                            parts.append(f"Metadata: {metadata_n}/{total_claims}")
                        else:
                            parts.append(f"Metadata: {breakdown['metadata_pct']}%")
                    if breakdown["database_pct"] > 0 or (use_absolute and database_n > 0):
                        if use_absolute:
                            parts.append(f"Database: {database_n}/{total_claims}")
                        else:
                            parts.append(f"Database: {breakdown['database_pct']}%")
                    if breakdown["llm_pct"] > 0 or (use_absolute and ungrounded_n > 0):
                        if use_absolute:
                            parts.append(f"LLM: {ungrounded_n}/{total_claims}")
                        else:
                            parts.append(f"LLM: {breakdown['llm_pct']}%")
                    pct_str = f" ({' | '.join(parts)})"
                else:
                    pct_str = ""

                # confidence indicator
                conf_color = _conf_color(confidence)

                if is_dev:
                    conf_str = (
                        f'<br><span style="font-weight:normal;font-size:0.85em;">'
                        f'\U0001F4CA Confidence: <strong style="color:{conf_color};">{confidence}%</strong>'
                        f' ({total_claims} claims verified)</span>'
                    )
                else:
                    conf_str = (
                        f'<br><span style="font-weight:normal;font-size:0.85em;">'
                        f'\U0001F4CA Confidence: <strong style="color:{conf_color};">{confidence}%</strong></span>'
                    )

                # source explanation (development only)
                source_html = ""
                if is_dev:
                    llm_pct = breakdown.get("llm_pct", 0)
                    source_lines = []
                    if breakdown.get("metadata_pct", 0) > 0 or (use_absolute and metadata_n > 0):
                        if use_absolute:
                            source_lines.append(
                                f'\U0001F7E2 Sources: {metadata_n} of {total_claims} from structured metadata'
                            )
                        else:
                            source_lines.append(
                                f'\U0001F7E2 Sources: {breakdown["metadata_pct"]}% from structured metadata'
                            )
                    if breakdown.get("database_pct", 0) > 0 or (use_absolute and database_n > 0):
                        if use_absolute:
                            source_lines.append(
                                f'\U0001F7E1 Database: {database_n} of {total_claims} from document database (RAG)'
                            )
                        else:
                            source_lines.append(
                                f'\U0001F7E1 Database: {breakdown["database_pct"]}% from document database (RAG)'
                            )
                    if llm_pct > 0 or (use_absolute and ungrounded_n > 0):
                        if use_absolute:
                            source_lines.append(
                                f'\U0001F534 LLM Refinement: {ungrounded_n} of {total_claims} combined/summarized for readability'
                            )
                        else:
                            source_lines.append(
                                f'\U0001F534 LLM Refinement: {llm_pct}% combined/summarized for readability'
                            )
                    source_html = '<br>'.join(
                        f'<span style="font-weight:normal;font-size:0.8em;">{line}</span>'
                        for line in source_lines
                    )
                    if source_html:
                        source_html = '<br>' + source_html

                note = conf_str + source_html

            else:
                # --- 2-way mode: Database / LLM ---
                grounded_n = len(breakdown.get("grounded_claims", []))
                ungrounded_n = len(breakdown.get("ungrounded_claims", []))

                # percentage string (development only)
                if is_dev:
                    parts = []
                    if use_absolute:
                        if grounded_n > 0:
                            parts.append(f"Database: {grounded_n}/{total_claims}")
                        if ungrounded_n > 0:
                            parts.append(f"LLM: {ungrounded_n}/{total_claims}")
                    else:
                        if breakdown.get("database_pct", 0) > 0:
                            parts.append(f"Database: {breakdown['database_pct']}%")
                        if breakdown.get("llm_pct", 0) > 0:
                            parts.append(f"LLM: {breakdown['llm_pct']}%")
                    pct_str = f" ({' | '.join(parts)})"
                else:
                    pct_str = ""

                # confidence indicator
                conf_color = _conf_color(confidence)

                if is_dev:
                    conf_str = (
                        f'<br><span style="font-weight:normal;font-size:0.85em;">'
                        f'\U0001F4CA Confidence: <strong style="color:{conf_color};">{confidence}%</strong>'
                        f' ({total_claims} claims verified)</span>'
                    )
                    # source lines
                    llm_pct = breakdown.get("llm_pct", 0)
                    source_lines = []
                    if grounded_n > 0:
                        if use_absolute:
                            source_lines.append(
                                f'\U0001F7E2 Sources: {grounded_n} of {total_claims} from document database (RAG)'
                            )
                        else:
                            source_lines.append(
                                f'\U0001F7E2 Sources: {breakdown["database_pct"]}% from document database (RAG)'
                            )
                    if ungrounded_n > 0:
                        if use_absolute:
                            source_lines.append(
                                f'\U0001F534 LLM Refinement: {ungrounded_n} of {total_claims} combined/summarized for readability'
                            )
                        else:
                            source_lines.append(
                                f'\U0001F534 LLM Refinement: {llm_pct}% combined/summarized for readability'
                            )
                    source_html = '<br>'.join(
                        f'<span style="font-weight:normal;font-size:0.8em;">{line}</span>'
                        for line in source_lines
                    )
                    note = conf_str + ('<br>' + source_html if source_html else '')
                else:
                    note = (
                        f'<br><span style="font-weight:normal;font-size:0.85em;">'
                        f'\U0001F4CA Confidence: <strong style="color:{conf_color};">{confidence}%</strong></span>'
                    )
        else:
            # No claims in breakdown (or no breakdown at all)
            if source_type == "Metadata":
                pct_str = " (Metadata: 100%)" if is_dev else ""
                if is_dev:
                    note = (
                        '<br><span style="font-weight:normal;font-size:0.85em;">'
                        '\U0001F4CA Confidence: <strong style="color:#155724;">100%</strong></span>'
                        '<br><span style="font-weight:normal;font-size:0.8em;">'
                        '\U0001F7E2 Sources: 100% from structured metadata</span>'
                    )
                else:
                    note = (
                        '<br><span style="font-weight:normal;font-size:0.85em;">'
                        '\U0001F4CA Confidence: <strong style="color:#155724;">100%</strong></span>'
                    )
            else:
                pct_str = ""
                note = ""

        # Legend for inline highlights (development only)
        legend = ""
        if is_dev:
            highlight_cfg = highlight_config or {}
            if highlight_cfg.get("enabled", False) and highlight_cfg.get("show_legend", True):
                if three_way:
                    meta_style = highlight_cfg.get("metadata_style", "")
                    db_style = highlight_cfg.get("database_style", "")
                    llm_style = highlight_cfg.get("llm_style", "")
                    if gap_analysis:
                        legend = (
                            '<div style="margin-top:6px;font-size:0.8em;color:#555;">'
                            f'<span style="{meta_style}">found in data</span> = term exists in database (may already be studied) &nbsp; '
                            f'<span style="{llm_style}">not in data</span> = not found in database (likely a true gap)'
                            '</div>'
                        )
                    else:
                        legend = (
                            '<div style="margin-top:6px;font-size:0.8em;color:#555;">'
                            f'<span style="{meta_style}">metadata</span> = structured data &nbsp; '
                            f'<span style="{db_style}">database</span> = RAG documents &nbsp; '
                            f'<span style="{llm_style}">llm</span> = LLM interpretation'
                            '</div>'
                        )
                else:
                    grounded_style = highlight_cfg.get("grounded_style", "")
                    ungrounded_style = highlight_cfg.get("ungrounded_style", "")
                    legend = (
                        '<div style="margin-top:6px;font-size:0.8em;color:#555;">'
                        f'<span style="{grounded_style}">grounded</span> = from document database &nbsp; '
                        f'<span style="{ungrounded_style}">ungrounded</span> = LLM interpretation'
                        '</div>'
                    )

        # Prompt level indicator (development only)
        prompt_html = ""
        if is_dev and prompt_level:
            pl_label = ReliabilityBadge.PROMPT_LEVEL_LABELS.get(
                prompt_level, prompt_level.capitalize()
            )
            prompt_html = (
                f'<br><span style="font-weight:normal;font-size:0.8em;">'
                f'Prompt: {pl_label}</span>'
            )

        # Map source_type to reliability label and colour scheme
        if source_type in ("Metadata", "Grounded"):
            return (
                f'<div class="claim-badge-area" style="margin-bottom:10px;">'
                f'<span style="background-color:#d4edda;color:#155724;'
                f'padding:2px 8px;border-radius:4px;font-size:0.85em;'
                f'font-weight:bold;">Reliability: High{pct_str}</span>'
                f'{note}{prompt_html}{legend}</div>\n\n'
            )
        elif source_type == "Partial":
            return (
                f'<div class="claim-badge-area" style="margin-bottom:10px;">'
                f'<span style="background-color:#fff3cd;color:#856404;'
                f'padding:2px 8px;border-radius:4px;font-size:0.85em;'
                f'font-weight:bold;">Reliability: Good{pct_str}</span>'
                f'{note}{prompt_html}{legend}</div>\n\n'
            )
        else:  # Ungrounded
            return (
                f'<div class="claim-badge-area" style="margin-bottom:10px;">'
                f'<span style="background-color:#f8d7da;color:#721c24;'
                f'padding:2px 8px;border-radius:4px;font-size:0.85em;'
                f'font-weight:bold;">Reliability: Poor{pct_str}</span>'
                f'{note}{prompt_html}{legend}</div>\n\n'
            )

    @staticmethod
    def compute_badge_and_breakdown(
        llm_content: str,
        context: str,
        metadata_ctx: str = "",
        transparency: str = "crystal_box",
        green_max: int = 20,
        red_min: int = 50,
        highlight_config: dict = None,
        university_acronyms: list = None,
        is_gap_analysis: bool = False,
        is_not_found: bool = False,
        prompt_level: str = None,
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
            university_acronyms=university_acronyms,
        )
        llm_pct = breakdown["llm_pct"]

        if llm_pct == 100 and is_not_found:
            label = "High"
            source = "Metadata" if "metadata_pct" in breakdown else "Grounded"
        elif llm_pct <= green_max:
            label = "High"
            source = "Metadata" if "metadata_pct" in breakdown else "Grounded"
        elif llm_pct < red_min:
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
        )

        return badge, breakdown, label


class AuditLogger:
    """JSONL audit logger for EU AI Act compliance."""

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

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "query": query,
            "query_type": query_type,
            "reliability_label": reliability_label,
            "confidence": breakdown.get("confidence", None),
            "total_claims": breakdown.get("total_claims", 0),
            "breakdown": breakdown_entry,
            "transparency_level": transparency,
            "prompt_level": prompt_level,
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
