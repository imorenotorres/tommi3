"""Humility post-processing for TOMMI agents.

Rewrites sentences that contain ungrounded (LLM-only) claims by adding
hedging language so the agent does not present uncertain information as fact.

Levels
------
- "off"      : no changes
- "moderate" : soften sentences containing ungrounded claims
- "strict"   : soften all partially-grounded and ungrounded claims,
               plus append a disclaimer footer

Usage
-----
    from agents.base.humility import HumilityRewriter

    rewriter = HumilityRewriter(level="moderate")
    new_text = rewriter.rewrite(response_text, breakdown)
"""

import re
import random


class HumilityRewriter:
    """Rule-based post-processor that adds hedging to ungrounded claims."""

    LEVELS = {"off", "moderate", "strict"}

    # Hedging prefixes — rotated to avoid repetitive phrasing
    _HEDGES_MODERATE = [
        "Based on available information, ",
        "According to available data, ",
        "From what I could find, ",
    ]

    _HEDGES_STRICT = [
        "This may not be fully verified, but ",
        "I could not fully verify this, however ",
        "Please note this could not be confirmed: ",
    ]

    # Phrases that indicate the sentence already has hedging
    _ALREADY_HEDGED = [
        "based on", "according to", "it appears", "it seems",
        "may ", "might ", "could ", "possibly", "potentially",
        "from what", "as far as", "likely", "reportedly",
        "i could not", "not fully verified", "please note",
        "available information", "available data",
    ]

    # Patterns that should never be hedged (headers, disclaimers, questions)
    _SKIP_PATTERNS = [
        re.compile(r'^\s*#{1,6}\s'),          # markdown headers
        re.compile(r'^\s*[-*]\s'),             # list items (handled per-item)
        re.compile(r'^\s*\d+\.\s'),            # numbered list items
        re.compile(r'\?\s*$'),                 # questions
        re.compile(r'^\s*>'),                  # blockquotes
        re.compile(r'^\s*\|'),                 # table rows
        re.compile(r'^\s*```'),                # code blocks
        re.compile(r'^\s*---'),                # horizontal rules
    ]

    def __init__(self, level: str = "off"):
        if level not in self.LEVELS:
            level = "off"
        self.level = level
        self._hedge_idx = 0

    def _next_hedge(self, strict: bool = False) -> str:
        pool = self._HEDGES_STRICT if strict else self._HEDGES_MODERATE
        hedge = pool[self._hedge_idx % len(pool)]
        self._hedge_idx += 1
        return hedge

    def _is_already_hedged(self, sentence: str) -> bool:
        s_lower = sentence.lower()
        return any(h in s_lower for h in self._ALREADY_HEDGED)

    def _should_skip(self, line: str) -> bool:
        return any(p.search(line) for p in self._SKIP_PATTERNS)

    def _sentence_contains_claim(self, sentence: str, claims: list) -> bool:
        s_lower = sentence.lower()
        for claim in claims:
            if claim.lower() in s_lower:
                return True
        return False

    def _hedge_sentence(self, sentence: str, strict: bool = False) -> str:
        """Add a hedging prefix to a sentence."""
        if self._is_already_hedged(sentence):
            return sentence

        hedge = self._next_hedge(strict)

        # Preserve leading markdown bold/italic markers
        match = re.match(r'^(\s*(?:\*{1,3}|_{1,3})?\s*)', sentence)
        prefix = match.group(0) if match else ""
        body = sentence[len(prefix):]

        if not body:
            return sentence

        # Lowercase the first character of the original sentence after hedge
        if body[0].isupper():
            body = body[0].lower() + body[1:]

        return prefix + hedge + body

    def rewrite(self, text: str, breakdown: dict) -> str:
        """Apply humility rewriting to *text* using claim data from *breakdown*.

        Parameters
        ----------
        text : str
            The LLM-generated response (markdown).
        breakdown : dict
            Output of ``GroundingAnalyzer.grounding_breakdown()`` or
            ``ReliabilityBadge.compute_badge_and_breakdown()``.

        Returns
        -------
        str
            The (possibly modified) response text.
        """
        if self.level == "off":
            return text
        if not breakdown or breakdown.get("total_claims", 0) == 0:
            return text

        llm_claims = breakdown.get("llm_claims", breakdown.get("ungrounded_claims", []))
        web_claims = breakdown.get("web_claims", [])

        # In strict mode, also hedge web-sourced claims (less trusted)
        claims_to_hedge = list(llm_claims)
        if self.level == "strict":
            claims_to_hedge.extend(web_claims)

        if not claims_to_hedge:
            return text

        # Reset hedge index for consistent output
        self._hedge_idx = random.randint(0, 2)

        lines = text.split('\n')
        in_code_block = False
        result = []

        for line in lines:
            # Track code blocks (don't modify inside them)
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                continue

            if in_code_block:
                result.append(line)
                continue

            # Skip structural lines
            if self._should_skip(line):
                # For list items, check if the content after the bullet needs hedging
                list_match = re.match(r'^(\s*(?:[-*]|\d+\.)\s+)', line)
                if list_match and self._sentence_contains_claim(line, claims_to_hedge):
                    prefix = list_match.group(1)
                    body = line[len(prefix):]
                    if not self._is_already_hedged(body):
                        use_strict = self.level == "strict" and not self._sentence_contains_claim(line, llm_claims)
                        hedged_body = self._hedge_sentence(body, strict=use_strict)
                        result.append(prefix + hedged_body[len(prefix):] if hedged_body.startswith(prefix) else prefix + hedged_body.lstrip())
                        continue
                result.append(line)
                continue

            # Empty lines pass through
            if not line.strip():
                result.append(line)
                continue

            # Check if this line contains any claims that need hedging
            if self._sentence_contains_claim(line, claims_to_hedge):
                use_strict = self.level == "strict" and not self._sentence_contains_claim(line, llm_claims)
                result.append(self._hedge_sentence(line, strict=use_strict))
            else:
                result.append(line)

        modified = '\n'.join(result)

        # In strict mode, append a disclaimer footer
        if self.level == "strict" and llm_claims:
            disclaimer = (
                "\n\n---\n\n"
                "*Note: Some statements in this response could not be fully verified "
                "against the available data sources. Please verify critical information "
                "independently before relying on it.*"
            )
            modified += disclaimer

        return modified
