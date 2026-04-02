"""Claim extraction and grounding analysis shared by all TOMMI agents.

This module provides two classes:
- ClaimExtractor: extracts verifiable factual claims from LLM responses
- GroundingAnalyzer: classifies extracted claims against metadata and RAG contexts
"""

import re


class ClaimExtractor:
    """Extract factual claims (titles, names, years, bold text, key phrases) from a response."""

    # Bold fragments that are headings/labels, not factual claims
    NON_BOLD = {
        "Note", "Summary", "Key findings", "Important",
        "References", "UNINOVIS", "Example", "For example",
        "Tip", "Warning",
    }

    # Lower-cased prefixes that indicate imperative/conditional bold text
    INSTRUCTION_STARTS = (
        "if ", "modify ", "update ", "use ", "open ", "script ",
        "combine ", "create ", "add ", "check ", "run ", "set ",
        "install ", "configure ", "start ", "stop ", "try ",
        "would you", "for example", "for instance", "the developer",
    )

    # Multi-word matches that look like names but are not
    NON_NAMES = {
        "No papers", "No research", "No study", "High reliability",
        "Good reliability", "Poor reliability", "View publications",
        "View interactive", "Partially reliable", "Source Database",
        "Source Metadata", "No verifiable",
    }

    # Common English words whose capitalisation at sentence start does not
    # make them proper nouns
    NON_NAME_STARTS = {
        "if", "in", "on", "at", "to", "by", "or", "an", "as", "so",
        "it", "is", "be", "do", "we", "no", "my", "up", "but", "not",
        "the", "this", "that", "for", "with", "from", "have", "has",
        "are", "was", "were", "will", "can", "may", "all", "any",
        "each", "both", "some", "when", "how", "what", "which",
        "where", "here", "there", "would", "could", "should",
        "please", "however", "also", "more", "most",
    }

    # ALL-CAPS tokens that are English filler, not technical acronyms
    NON_TECH = {
        "IMPORTANT", "RULES", "NOTE", "RESPONSE", "FORMAT",
        "CRITICAL", "NEVER", "ONLY", "NOT", "MUST", "SHALL",
        "AND", "THE", "FOR", "BUT", "ALL", "ANY", "YOU",
        "EACH", "ALSO", "DOES", "WITH", "FROM", "HAVE",
    }

    @staticmethod
    def extract_claims(response: str, university_acronyms: list = None) -> list:
        """Extract verifiable factual claims from *response*.

        Parameters
        ----------
        response : str
            The LLM-generated text to analyse.
        university_acronyms : list, optional
            E.g. ``["THUAS", "UMA", "TAMK"]``.  When provided, mentions of
            these acronyms are extracted as claims (step 5) and excluded from
            the generic technical-acronym step so they are not double-counted.
        """
        claims = []

        # 1. Quoted strings (paper titles, topic names)
        quoted = re.findall(r'"([^"]{10,})"', response)
        claims.extend(quoted)

        # 2. Bold text — only factual claims, not headings/instructions
        bold = re.findall(r'\*\*([^*]{5,})\*\*', response)
        for b in bold:
            if b in ClaimExtractor.NON_BOLD:
                continue
            b_lower = b.lower().strip()
            if b_lower.startswith(ClaimExtractor.INSTRUCTION_STARTS):
                continue
            if b_lower.endswith("?"):
                continue
            if len(b.split()) > 8:
                continue
            claims.append(b)

        # 3. Author / proper-noun patterns: "Name Surname"
        #    Supports accented characters (e, u, n, etc.), hyphens, and
        #    lowercase particles (de, van, von, del, la, di, el, al, ben)
        author_matches = re.findall(
            r'(?<!\w)([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ \t\u2010-](?:(?:de|van|von|del|la|di|el|al|ben) )?(?:[A-ZÀ-ÖØ-Þ]\.[ \t])?[A-ZÀ-ÖØ-Þa-zà-öø-ÿ][a-zà-öø-ÿ]+)+)(?!\w)',
            response,
        )
        for a in author_matches:
            if a in ClaimExtractor.NON_NAMES:
                continue
            first_word = a.split()[0].lower()
            if first_word in ClaimExtractor.NON_NAME_STARTS:
                continue
            claims.append(a)

        # 4. Years (e.g. 2023, 2024)
        years = re.findall(r'\b(20\d{2})\b', response)
        claims.extend(years)

        # 5. University acronyms (only when the caller supplies a list)
        uni_refs = []
        if university_acronyms:
            pattern = r'\b(' + '|'.join(re.escape(a) for a in university_acronyms) + r')\b'
            uni_refs = re.findall(pattern, response)
            claims.extend(uni_refs)

        # 6. Paper IDs (e.g. W4405602662)
        paper_ids = re.findall(r'\b(W\d{7,})\b', response)
        claims.extend(paper_ids)

        # 7. Technical terms: ALL_CAPS acronyms (>= 3 chars), compound
        #    terms with + (e.g. RAG+Metadata), and mixed alphanumeric
        #    identifiers (e.g. Text2SQL)
        acronyms = re.findall(
            r'(?<![A-Za-z])([A-Z]{3,}(?:\+[A-Za-z]+)?)(?![A-Za-z+])',
            response,
        )
        existing_unis = set(uni_refs)
        claims.extend(
            t for t in acronyms
            if t not in ClaimExtractor.NON_TECH and t not in existing_unis
        )
        # Mixed alphanumeric identifiers (e.g. Text2SQL, Gpt4)
        claims.extend(re.findall(r'\b([A-Z][a-z]+\d+[A-Za-z]*)\b', response))

        # Deduplicate while preserving order
        seen = set()
        unique_claims = []
        for c in claims:
            if c not in seen:
                seen.add(c)
                unique_claims.append(c)
        return unique_claims


class GroundingAnalyzer:
    """Three-way claim classification: metadata / database (RAG) / LLM."""

    @staticmethod
    def grounding_breakdown(
        response: str,
        metadata_ctx: str = "",
        rag_ctx: str = "",
        university_acronyms: list = None,
    ) -> dict:
        """Classify every claim extracted from *response*.

        Parameters
        ----------
        response : str
            The LLM-generated text.
        metadata_ctx : str
            Text built from document metadata (keyword context).
        rag_ctx : str
            Text retrieved from the vector / document database.
        university_acronyms : list, optional
            Forwarded to ``ClaimExtractor.extract_claims``.

        Returns
        -------
        dict
            metadata_pct, database_pct, llm_pct, total_claims, confidence,
            metadata_claims, database_claims, llm_claims,
            grounded_claims (= metadata + database),
            ungrounded_claims (= llm).
        """
        claims = ClaimExtractor.extract_claims(response, university_acronyms)

        if not claims:
            return {
                "metadata_pct": 100,
                "database_pct": 0,
                "llm_pct": 0,
                "total_claims": 0,
                "confidence": 100,
                "metadata_claims": [],
                "database_claims": [],
                "llm_claims": [],
                "grounded_claims": [],
                "ungrounded_claims": [],
            }

        metadata_lower = (metadata_ctx or "").lower()
        rag_lower = (rag_ctx or "").lower()

        metadata_count = 0
        database_count = 0
        llm_count = 0
        metadata_claims = []
        database_claims = []
        llm_claims = []

        for claim in claims:
            claim_lower = claim.lower()

            # Exact substring match against metadata context
            if metadata_lower and claim_lower in metadata_lower:
                metadata_count += 1
                metadata_claims.append(claim)
                continue

            # Exact substring match against RAG context
            if rag_lower and claim_lower in rag_lower:
                database_count += 1
                database_claims.append(claim)
                continue

            # Fuzzy match: for multi-word claims (e.g. author names), try
            # matching significant words (length > 3) against contexts.
            # Require a strict majority (> 50 %) of significant words.
            words = claim_lower.split()
            fuzzy_matched = False

            if len(words) >= 2:
                significant = [w.rstrip('.') for w in words if len(w.rstrip('.')) > 3]

                if significant and metadata_lower:
                    matched = sum(1 for w in significant if w in metadata_lower)
                    if matched > len(significant) / 2:
                        metadata_count += 1
                        metadata_claims.append(claim)
                        fuzzy_matched = True

                if not fuzzy_matched and significant and rag_lower:
                    matched = sum(1 for w in significant if w in rag_lower)
                    if matched > len(significant) / 2:
                        database_count += 1
                        database_claims.append(claim)
                        fuzzy_matched = True

            if not fuzzy_matched:
                llm_count += 1
                llm_claims.append(claim)

        total = len(claims)
        grounded_total = metadata_count + database_count
        confidence = round(grounded_total / total * 100) if total > 0 else 100

        return {
            "metadata_pct": round(metadata_count / total * 100),
            "database_pct": round(database_count / total * 100),
            "llm_pct": round(llm_count / total * 100),
            "total_claims": total,
            "confidence": confidence,
            "metadata_claims": metadata_claims,
            "database_claims": database_claims,
            "llm_claims": llm_claims,
            "grounded_claims": metadata_claims + database_claims,
            "ungrounded_claims": llm_claims,
        }
