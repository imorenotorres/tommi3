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
        "first", "second", "third", "then", "after", "before",
        "next", "finally", "here", "another", "many", "several",
        "still", "just", "only", "even", "since", "because",
        "while", "although", "therefore", "thus", "hence",
        # Institutional words (university names are not author claims)
        "universidad", "université", "university", "universität",
        "technical", "institute", "institution", "college",
        "school", "faculty", "department", "centre", "center",
    }

    # Common English words used to detect non-proper-noun multi-word matches.
    # If ALL words in an author-like match are in this set, the match is
    # rejected (no word looks like an actual proper noun).
    _COMMON_WORDS = {
        "about", "above", "add", "after", "again", "air", "all", "also",
        "and", "any", "are", "ask", "away", "back", "base", "been", "best",
        "big", "book", "both", "but", "call", "came", "can", "case", "cold",
        "come", "cook", "cool", "cost", "cut", "dark", "data", "day", "did",
        "does", "done", "down", "dry", "each", "end", "even", "ever", "face",
        "fact", "far", "fast", "few", "find", "fine", "food", "form", "free",
        "from", "full", "gave", "give", "goal", "good", "got", "half",
        "hard", "have", "heat", "help", "here", "high", "hold", "home",
        "hot", "hour", "how", "idea", "into", "just", "keep", "key", "kind",
        "know", "last", "late", "left", "less", "life", "like", "line",
        "list", "long", "look", "loss", "lost", "low", "made", "main",
        "make", "many", "mean", "mind", "miss", "mix", "more", "most",
        "move", "much", "must", "name", "near", "need", "new", "next",
        "nice", "note", "now", "off", "once", "only", "open", "other",
        "out", "over", "own", "part", "past", "pick", "plan", "play",
        "plus", "point", "poor", "prep", "put", "rate", "read", "real",
        "rest", "rich", "risk", "role", "room", "rule", "run", "safe",
        "said", "same", "save", "self", "send", "serve", "set", "show",
        "side", "sign", "size", "slow", "small", "some", "sort", "step",
        "stop", "such", "sure", "take", "talk", "tell", "term", "test",
        "text", "than", "that", "the", "them", "then", "they", "thin",
        "this", "thus", "time", "tip", "told", "too", "took", "tool",
        "top", "total", "true", "try", "turn", "type", "unit", "upon",
        "use", "used", "very", "view", "wait", "walk", "want", "warm",
        "was", "way", "well", "went", "were", "what", "when", "wide",
        "will", "with", "word", "work", "year", "yet", "your",
        # Additional adjectives/nouns that appear capitalized in lists
        "black", "blue", "bread", "brown", "clean", "clear", "close",
        "cream", "daily", "deep", "early", "easy", "empty", "equal",
        "exact", "extra", "fair", "false", "final", "fixed", "flat",
        "fresh", "front", "fruit", "grand", "great", "green", "gross",
        "happy", "heavy", "human", "ideal", "inner", "joint", "juice",
        "known", "large", "legal", "light", "local", "lower", "major",
        "minor", "mixed", "moral", "novel", "older", "outer", "plain",
        "prime", "prior", "quick", "rapid", "rough", "round", "royal",
        "rural", "sauce", "scene", "sharp", "short", "simple", "smooth",
        "soft", "solid", "soup", "special", "standard", "steep", "strong",
        "sugar", "super", "sweet", "thick", "tough", "upper", "urban",
        "usual", "valid", "vital", "water", "white", "whole", "wild",
        "young",
        # Common gerunds / participles that appear capitalized in lists
        "mining", "production", "higher", "building", "growing",
        "learning", "training", "testing", "working", "making",
        "leading", "reading", "looking", "setting", "getting",
        "version", "organic", "economy", "principles",
        "generated", "practice", "step", "process",
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
            # Strip trailing punctuation (colons, periods, commas)
            b = b.rstrip(':.,;')
            # If bold text is a comma-separated list, split into individual claims
            # e.g., "transparency, fairness, and sustainability" → 3 claims
            if ',' in b:
                parts = re.split(r',\s*(?:and\s+)?', b)
                parts = [p.strip().rstrip('.') for p in parts if p.strip()]
                # Also handle trailing "and X" without comma
                if parts and ' and ' in parts[-1]:
                    last = parts.pop()
                    parts.extend(p.strip() for p in last.split(' and ') if p.strip())
                for part in parts:
                    if len(part) >= 3 and part not in ClaimExtractor.NON_BOLD:
                        claims.append(part)
                continue
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

        # 3. Author / proper-noun patterns: "Name Surname" (2-4 words)
        #    Each word must start with a capital letter (or be a lowercase
        #    particle like de, van, von, del, la, di, el, al, ben).
        #    Limited to {1,3} additional words to avoid matching long phrases.
        author_matches = re.findall(
            r'(?<!\w)([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ \t\u2010-](?:(?:de|van|von|del|la|di|el|al|ben) )?(?:[A-ZÀ-ÖØ-Þ]\.[ \t])?[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3})(?!\w)',
            response,
        )
        # Institutional words: if ANY word is an institutional term, the match
        # is a university/organization name, not an author name.
        _INSTITUTIONAL = {
            "university", "universidad", "université", "universität",
            "institute", "institution", "college", "school", "faculty",
            "department", "centre", "center", "sciences", "applied",
            "technical", "technology", "polytechnic", "academy",
            "education", "higher", "kolegija", "hochschule",
        }
        for a in author_matches:
            if a in ClaimExtractor.NON_NAMES:
                continue
            words_lower = [w.lower().rstrip('.') for w in a.split()]
            # Skip if the first word is a common sentence starter
            if words_lower[0] in ClaimExtractor.NON_NAME_STARTS:
                continue
            # Skip if any word is an institutional term (university names)
            if any(w in _INSTITUTIONAL for w in words_lower):
                continue
            # Skip if ALL words are common English words (no proper noun detected).
            if all(w in ClaimExtractor._COMMON_WORDS for w in words_lower):
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

        # Deduplicate while preserving order; skip trivially short claims
        seen = set()
        unique_claims = []
        for c in claims:
            if len(c) < 2:
                continue
            if c not in seen:
                seen.add(c)
                unique_claims.append(c)

        return unique_claims

    # -----------------------------------------------------------------
    # Context-driven claim identification (bidirectional)
    # -----------------------------------------------------------------

    # Common short words and stop-phrases to skip when extracting context terms
    _STOP_WORDS = {
        # Determiners, pronouns, prepositions, conjunctions
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "up", "as", "is", "it", "its",
        "be", "are", "was", "were", "has", "had", "do", "does", "did",
        "not", "no", "so", "if", "we", "he", "she", "they", "you", "i",
        "my", "our", "your", "this", "that", "these", "those", "which",
        "who", "what", "how", "when", "where", "each", "all", "any",
        "both", "more", "most", "some", "can", "may", "will", "would",
        "could", "should", "also", "than", "then", "very", "about",
        "into", "over", "such", "only", "other", "new", "one", "two",
        # Common verbs and adverbs
        "used", "based", "using", "between", "through", "after", "before",
        "however", "therefore", "among", "within", "without", "been",
        "make", "made", "help", "helps", "show", "shows", "find", "found",
        "give", "given", "take", "taken", "come", "work", "works",
        "include", "includes", "including", "provide", "provides",
        "need", "needs", "want", "know", "known", "think", "like",
        "explore", "review", "specific", "specifically",
        # Generic academic/document words (too common to be meaningful claims)
        "data", "results", "study", "paper", "papers", "research", "analysis",
        "topic", "topics", "approach", "method", "methods", "system",
        "systems", "model", "models", "process", "processing",
        "case", "cases", "type", "types", "form", "level", "levels",
        "area", "areas", "field", "part", "role", "view", "point",
        "way", "ways", "time", "year", "years", "number",
        "information", "example", "examples", "different", "important",
        "available", "possible", "current", "related", "general",
        "particular", "various", "several", "many", "much", "well",
        "even", "still", "just", "often", "usually", "there", "here",
        # Additional common words that appear in context but are too generic
        "look", "looking", "found", "find", "apply", "applied", "alter",
        "condition", "conditions", "effect", "effects", "change", "changes",
        "best", "better", "good", "high", "low", "large", "small", "long",
        "short", "dark", "light", "early", "late", "first", "last",
        "common", "certain", "enough", "likely", "similar", "further",
        "present", "recent", "simple", "complete", "direct", "single",
        "previous", "following", "according", "across", "along", "around",
        "above", "below", "during", "toward", "towards", "against",
        "consider", "considered", "suggest", "suggested", "proposed",
        "describe", "described", "identify", "identified", "develop",
        "developed", "improve", "improved", "focus", "focused",
        "address", "addressed", "require", "required", "achieve",
        "perform", "performed", "demonstrate", "discussed",
        "compared", "evaluated", "observed", "obtained", "conducted",
        "associated", "relevant", "significant", "potential", "existing",
        "traditional", "conventional", "overall", "additional",
        "effective", "efficient", "appropriate", "suitable",
        "eco", "brand", "range", "class", "group", "source", "order",
        "place", "state", "value", "world", "power", "space", "sense",
        "issue", "issues", "aspect", "aspects", "factor", "factors",
        "feature", "features", "context", "design", "response", "support",
        "impact", "access", "target", "input", "output", "stage",
        "side", "face", "hand", "body", "head", "mind", "able",
        "mining", "production", "higher", "building", "growing",
        "learning", "training", "testing", "working", "making",
        "leading", "reading", "looking", "setting", "getting",
        "running", "coming", "going", "having", "being", "doing",
        "saying", "telling", "asking", "given", "taken", "shown",
        "known", "called", "named", "based", "needed", "expected",
        "proposed", "applied", "related", "involved", "concerned",
        "limited", "required", "suggested", "reported", "observed",
        "obtained", "published", "presented", "discussed", "compared",
        "version", "organic", "economy", "principles",
        "generated", "practice", "practices", "standard", "standards",
        "concept", "concepts", "strategy", "solution", "solutions",
        "framework", "challenge", "challenges", "benefit", "benefits",
        "quality", "measure", "measures", "step", "steps",
        "evidence", "theory", "structure", "resource", "resources",
        "service", "services", "sector", "market", "policy", "policies",
        "performance", "criteria", "purpose", "progress", "list",
        "university", "universities", "partner", "partners",
        "document", "documents", "database", "collection",
        "question", "questions", "answer", "answers",
        "summary", "overview", "introduction", "conclusion",
        "figure", "table", "section", "page", "pages",
        "total", "count", "number", "amount",
        # Countries and regions (too generic to be meaningful claims)
        "france", "italy", "spain", "germany", "finland", "netherlands",
        "lithuania", "albania", "greece", "portugal", "belgium", "austria",
        "sweden", "denmark", "norway", "poland", "ireland", "switzerland",
        "europe", "european", "country", "countries", "nation", "national",
        "improvement", "monitoring", "explain", "reasoning",
        "implementation", "evaluation", "assessment", "regulation",
        "recommendation", "integration", "adoption", "deployment",
        "definition", "classification", "detection", "prediction",
        "generation", "optimization", "automation", "verification",
        # Additional generic words and phrases to omit as claims
        "agency", "comprehensive", "ensuring", "account",
        "contexts", "exaggerated", "must", "solely", "enhance",
        "future", "offers", "offer", "developing", "creating",
        "science", "approaches", "already", "shaping",
    }

    @staticmethod
    def extract_context_terms(
        context: str,
        min_term_length: int = 4,
        max_ngram: int = 3,
    ) -> set:
        """Extract significant terms and short phrases from context text.

        Returns a set of lowercased terms (1–3 word n-grams) that appear
        in the context and are likely to be domain-specific vocabulary.
        These can then be searched for in the LLM response to identify
        grounded content that regex-based extraction would miss.

        Parameters
        ----------
        context : str
            Metadata or RAG context text.
        min_term_length : int
            Minimum character length for single-word terms.
        max_ngram : int
            Maximum n-gram size (default 3 = up to 3-word phrases).
        """
        if not context:
            return set()

        # Extract ALL_CAPS acronyms (2+ chars) from original text before lowercasing.
        # These are almost always meaningful (AI, ML, NLP, XAI, IoT) and should
        # bypass the min_term_length filter.
        acronyms_original = set(re.findall(r'\b([A-Z]{2,})\b', context))
        acronym_lower = {a.lower() for a in acronyms_original
                         if a not in ClaimExtractor.NON_TECH}

        # Extract phrases connected by & / + (e.g., "AI & Responsibility",
        # "AI & Robotics", "Health & Social").  These are common domain names
        # that the normal tokenizer would split apart.
        connector_phrases = re.findall(
            r'([A-Za-zÀ-ÖØ-öø-ÿ]{2,}(?:\s*[&/+]\s*[A-Za-zÀ-ÖØ-öø-ÿ]{2,})+)',
            context
        )

        # Tokenise: split on non-alphanumeric (keep hyphens inside words)
        tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9](?:[A-Za-zÀ-ÖØ-öø-ÿ0-9\-]*[A-Za-zÀ-ÖØ-öø-ÿ0-9])?", context.lower())

        # Filter stop words and short tokens
        filtered = [t for t in tokens if t not in ClaimExtractor._STOP_WORDS and len(t) >= min_term_length]

        terms = set()

        # Single words: significant tokens + short acronyms
        terms.update(filtered)
        terms.update(acronym_lower)

        # Add connector phrases as-is (lowercased, preserving & / +)
        for phrase in connector_phrases:
            lp = phrase.lower().strip()
            if len(lp) >= min_term_length:
                terms.add(lp)

        # Bigrams and trigrams from the original token stream
        for n in range(2, max_ngram + 1):
            for i in range(len(tokens) - n + 1):
                ngram_tokens = tokens[i:i + n]
                # Require at least one significant (non-stop) word in the n-gram
                significant_in_ngram = [t for t in ngram_tokens
                                        if t not in ClaimExtractor._STOP_WORDS
                                        and len(t) >= min_term_length]
                if not significant_in_ngram:
                    continue
                phrase = " ".join(ngram_tokens)
                if len(phrase) >= min_term_length + 2:  # meaningful length
                    terms.add(phrase)

        return terms

    @staticmethod
    def find_context_terms_in_response(
        response: str,
        context_terms: set,
        existing_claims: list,
    ) -> list:
        """Find context-derived terms that appear in the response but were
        not already identified by regex-based claim extraction.

        Returns a list of new claim strings (lowercased terms found in the
        response text).  Only terms of 2+ words or single words of 5+ chars
        are included, to avoid noise from very common short words.

        Parameters
        ----------
        response : str
            The LLM-generated response.
        context_terms : set
            Terms from ``extract_context_terms()``.
        existing_claims : list
            Claims already identified by ``extract_claims()``.
        """
        if not context_terms:
            return []

        response_lower = response.lower()
        existing_lower = {c.lower() for c in existing_claims}
        new_claims = []

        # Sort by length descending so longer phrases are matched first
        sorted_terms = sorted(context_terms, key=len, reverse=True)
        matched_spans = []  # track matched positions to avoid sub-matches

        for term in sorted_terms:
            if term in existing_lower:
                continue
            # Only include multi-word terms, single words >= 6 chars,
            # or short terms that appear as ALL_CAPS in the response (acronyms like AI, ML, XAI)
            word_count = len(term.split())
            if word_count == 1 and len(term) < 6:
                # Check if it appears as an ALL_CAPS acronym in the original response
                if not re.search(r'\b' + re.escape(term.upper()) + r'\b', response):
                    continue

            # Use word-boundary matching to avoid partial-word matches
            # (e.g., "review" should not match inside "reviewing").
            # For terms containing connectors (& / +), use plain substring
            # search since \b doesn't work across these characters.
            has_connector = any(c in term for c in '&/+')
            if has_connector:
                idx = response_lower.find(term)
                if idx == -1:
                    continue
                end = idx + len(term)
            else:
                pattern = r'\b' + re.escape(term) + r'\b'
                m = re.search(pattern, response_lower)
                if not m:
                    continue
                idx = m.start()
                end = m.end()

            # Check this isn't inside an already-matched longer phrase
            overlaps = any(s <= idx < e or s < end <= e for s, e in matched_spans)
            if overlaps:
                continue

            matched_spans.append((idx, end))
            # Store with original casing from the response
            original = response[idx:end]
            if original.lower() not in existing_lower:
                new_claims.append(original)
                existing_lower.add(original.lower())

        return new_claims


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
        # --- Phase A: regex-based claim extraction (response-driven) ---
        claims = ClaimExtractor.extract_claims(response, university_acronyms)

        # --- Phase B: context-driven claim identification (bidirectional) ---
        # Extract key terms from context and find them in the response.
        # These are automatically grounded (they come FROM the context).
        metadata_terms = ClaimExtractor.extract_context_terms(metadata_ctx)
        rag_terms = ClaimExtractor.extract_context_terms(rag_ctx)

        # Find context terms in response that regex missed
        ctx_meta_claims = ClaimExtractor.find_context_terms_in_response(
            response, metadata_terms, claims
        )
        ctx_rag_claims = ClaimExtractor.find_context_terms_in_response(
            response, rag_terms - metadata_terms,  # exclude already-found metadata terms
            claims + ctx_meta_claims
        )

        if not claims and not ctx_meta_claims and not ctx_rag_claims:
            return {
                "metadata_pct": 0,
                "database_pct": 0,
                "llm_pct": 0,
                "total_claims": 0,
                "confidence": 0,
                "coverage_pct": 0,
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

        # --- Phase B results: add context-derived claims (already grounded) ---
        for c in ctx_meta_claims:
            metadata_count += 1
            metadata_claims.append(c)
        for c in ctx_rag_claims:
            database_count += 1
            database_claims.append(c)

        # Remove sub-claims that are part of a connector phrase (with &/+).
        # E.g., if "AI & Responsibility" is a claim, remove standalone "AI"
        # and "Responsibility" to prevent overlapping highlights.
        all_claim_lists = [metadata_claims, database_claims, llm_claims]
        all_texts = metadata_claims + database_claims + llm_claims
        connector_claims = {c.lower() for c in all_texts if '&' in c or '+' in c}
        if connector_claims:
            for claim_list in all_claim_lists:
                to_remove = []
                for c in claim_list:
                    if '&' in c or '+' in c:
                        continue
                    c_lower = c.lower()
                    if any(c_lower in cc for cc in connector_claims if len(cc) > len(c_lower)):
                        to_remove.append(c)
                for c in to_remove:
                    claim_list.remove(c)
            # Recount
            metadata_count = len(metadata_claims)
            database_count = len(database_claims)
            llm_count = len(llm_claims)

        total = metadata_count + database_count + llm_count
        grounded_total = metadata_count + database_count
        confidence = round(grounded_total / total * 100) if total > 0 else 100

        # Coverage: what fraction of the response text is covered by claims?
        # Strip markdown formatting for a cleaner word count.
        response_clean = re.sub(r'[*#\[\]()_`>|]', ' ', response)
        response_words = len(response_clean.split())
        all_claims = (metadata_claims + database_claims + llm_claims
                      + ctx_meta_claims + ctx_rag_claims)
        claim_words = sum(len(c.split()) for c in all_claims)
        coverage_pct = min(100, round(claim_words / response_words * 100)) if response_words > 0 else 0

        return {
            "metadata_pct": round(metadata_count / total * 100) if total else 0,
            "database_pct": round(database_count / total * 100) if total else 0,
            "llm_pct": round(llm_count / total * 100) if total else 0,
            "total_claims": total,
            "confidence": confidence,
            "coverage_pct": coverage_pct,
            "metadata_claims": metadata_claims,
            "database_claims": database_claims,
            "llm_claims": llm_claims,
            "grounded_claims": metadata_claims + database_claims,
            "ungrounded_claims": llm_claims,
        }
