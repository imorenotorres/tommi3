"""SQL Verifier — Schema validation and reliability assessment for Text-to-SQL agents.

Parses generated SQL and verifies every table name, column name, and join
against the actual database schema. Produces a reliability breakdown
analogous to the claim grounding system used in RAG agents.

Classes
-------
- SQLVerifier: Extracts and validates SQL identifiers against the DB schema
- SQLReliabilityBadge: Renders HTML reliability badges for Text-to-SQL responses
"""

import re
import sqlite3


class SQLVerifier:
    """Verify generated SQL against a SQLite database schema."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._schema = {}  # {table_name: set(column_names)}
        self._load_schema()

    def _load_schema(self):
        """Load all table and column names from the database."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = {col[1].lower() for col in cursor.fetchall()}
                self._schema[table.lower()] = columns
            conn.close()
        except sqlite3.Error:
            pass

    def get_tables(self) -> set:
        return set(self._schema.keys())

    def get_columns(self, table: str) -> set:
        return self._schema.get(table.lower(), set())

    def verify(self, sql: str) -> dict:
        """Verify a SQL query against the database schema.

        Returns
        -------
        dict
            verified_tables, unknown_tables, verified_columns,
            unknown_columns, issues (list of warning strings),
            confidence (0-100), is_select, executed_ok (None until checked).
        """
        sql_clean = self._strip_comments(sql)
        sql_upper = sql_clean.strip().upper()

        is_select = sql_upper.startswith("SELECT")

        # Extract identifiers from SQL
        tables_used = self._extract_tables(sql_clean)
        columns_used = self._extract_columns(sql_clean)

        # Build alias → table mapping (e.g. "s" → "subjects")
        alias_map = {}
        for m in re.finditer(r'\bFROM\s+(\w+)\s+(?:AS\s+)?(\w+)', sql_clean, re.IGNORECASE):
            table_name, alias = m.group(1).lower(), m.group(2).lower()
            if alias not in ("where", "on", "join", "inner", "left", "right",
                             "outer", "cross", "natural", "order", "group",
                             "having", "limit"):
                alias_map[alias] = table_name
        for m in re.finditer(r'\bJOIN\s+(\w+)\s+(?:AS\s+)?(\w+)', sql_clean, re.IGNORECASE):
            table_name, alias = m.group(1).lower(), m.group(2).lower()
            if alias not in ("on", "where", "using"):
                alias_map[alias] = table_name

        # Validate tables
        verified_tables = []
        unknown_tables = []
        for t in tables_used:
            if t.lower() in self._schema:
                verified_tables.append(t)
            else:
                unknown_tables.append(t)

        # Validate columns against known tables
        all_known_columns = set()
        for t in verified_tables:
            all_known_columns.update(self._schema.get(t.lower(), set()))

        verified_columns = []
        unknown_columns = []
        for c in columns_used:
            # Handle table.column or alias.column references
            if "." in c:
                parts = c.split(".", 1)
                table_part = parts[0].lower()
                col_part = parts[1].lower()
                # Resolve alias to actual table name
                resolved_table = alias_map.get(table_part, table_part)
                table_cols = self._schema.get(resolved_table, set())
                if col_part in table_cols or col_part == "*":
                    verified_columns.append(c)
                else:
                    unknown_columns.append(c)
            elif c.lower() in all_known_columns or c == "*":
                verified_columns.append(c)
            else:
                unknown_columns.append(c)

        # Build issues list
        issues = []
        if not is_select:
            issues.append("Query is not a SELECT statement")
        for t in unknown_tables:
            issues.append(f"Unknown table: {t}")
        for c in unknown_columns:
            issues.append(f"Unknown column: {c}")

        # Check for dangerous patterns
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
        for word in dangerous:
            if word in sql_upper:
                issues.append(f"Dangerous keyword detected: {word}")

        # --- Semantic plausibility checks ---
        semantic_penalty = 0

        # 1. SELECT * is overly broad — the LLM should select specific columns
        if re.search(r'\bSELECT\s+\*\s', sql_upper):
            issues.append("SELECT * returns all columns (overly broad)")
            semantic_penalty += 10

        # 2. OR explosion: many OR conditions with LIKE suggest the LLM is guessing
        or_like_count = len(re.findall(r'\bOR\b.*?\bLIKE\b', sql_upper))
        if or_like_count >= 4:
            issues.append(f"Query has {or_like_count} OR+LIKE conditions (may be too broad)")
            semantic_penalty += min(30, or_like_count * 5)

        # 3. Wildcard LIKE on many columns — searching '%term%' across
        #    unrelated columns (e.g. host_institution, mobility_program)
        like_columns = re.findall(r'(\w+)\s+LIKE\s+', sql_clean, re.IGNORECASE)
        unique_like_cols = set(c.lower() for c in like_columns)
        if len(unique_like_cols) >= 4:
            issues.append(f"LIKE search across {len(unique_like_cols)} different columns (shotgun query)")
            semantic_penalty += 15

        # Calculate confidence
        total_identifiers = len(verified_tables) + len(verified_columns) + len(unknown_tables) + len(unknown_columns)
        verified_count = len(verified_tables) + len(verified_columns)

        if total_identifiers == 0:
            confidence = 0 if not is_select else 50
        else:
            confidence = round(verified_count / total_identifiers * 100)

        if not is_select:
            confidence = 0
        if issues and any("Dangerous" in i for i in issues):
            confidence = 0

        # 4. Country name in wrong column: searching a country name in
        #    host_institution or other non-country columns
        country_like_values = re.findall(
            r"(\w+)\s+LIKE\s+['\"]%([^%'\"]+)%['\"]", sql_clean, re.IGNORECASE
        )
        _COMMON_COUNTRIES = {
            "países bajos", "netherlands", "holanda", "france", "francia",
            "germany", "alemania", "italy", "italia", "spain", "españa",
            "finland", "finlandia", "lithuania", "lituania", "albania",
            "portugal", "greece", "grecia", "sweden", "suecia",
            "norway", "noruega", "denmark", "dinamarca", "belgium", "bélgica",
            "austria", "switzerland", "suiza", "poland", "polonia",
            "czech republic", "república checa", "croatia", "croacia",
            "ireland", "irlanda", "romania", "rumanía", "hungary", "hungría",
            "united kingdom", "reino unido", "japan", "japón",
            "china", "brazil", "brasil", "mexico", "méxico",
            "turkey", "turquía", "morocco", "marruecos",
        }
        # Build set of country values already searched in destination_country
        _countries_in_correct_col = {
            v.lower() for c, v in country_like_values if c.lower() == "destination_country"
        }
        for col, value in country_like_values:
            if value.lower() in _COMMON_COUNTRIES and col.lower() != "destination_country":
                # Only penalize if the same value is NOT also searched in destination_country
                if value.lower() in _countries_in_correct_col:
                    issues.append(
                        f"Country name '{value}' also searched in '{col}' (redundant but acceptable)"
                    )
                else:
                    issues.append(
                        f"Country name '{value}' searched in '{col}' instead of 'destination_country'"
                    )
                    semantic_penalty += 20

        # Apply semantic penalty
        confidence = max(0, confidence - semantic_penalty)

        return {
            "verified_tables": verified_tables,
            "unknown_tables": unknown_tables,
            "verified_columns": verified_columns,
            "unknown_columns": unknown_columns,
            "issues": issues,
            "confidence": confidence,
            "is_select": is_select,
            "executed_ok": None,
            "result_count": None,
        }

    def _get_total_rows(self, table: str) -> int:
        """Get total row count for a table (cached)."""
        if not hasattr(self, '_row_counts'):
            self._row_counts = {}
        if table.lower() not in self._row_counts:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                self._row_counts[table.lower()] = cursor.fetchone()[0]
                conn.close()
            except sqlite3.Error:
                self._row_counts[table.lower()] = 0
        return self._row_counts.get(table.lower(), 0)

    # ------------------------------------------------------------------
    # Semantic alignment: does the SQL match the user's question?
    # ------------------------------------------------------------------

    # Words to ignore when extracting key terms from the user question
    _QUESTION_STOP_WORDS = {
        # English
        "show", "list", "find", "get", "give", "tell", "what", "which",
        "where", "how", "many", "much", "are", "there", "is", "the",
        "all", "any", "with", "from", "for", "and", "that", "have",
        "has", "been", "can", "does", "about", "this", "those", "these",
        "their", "they", "them", "some", "more", "most", "between",
        "than", "also", "other", "only", "each", "every", "both",
        "such", "into", "over", "after", "before", "during", "without",
        "not", "but", "yes", "no", "do", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "our",
        "your", "its", "his", "her", "who", "whom", "whose", "when",
        "why", "me", "my", "you", "we", "us", "it", "to", "of", "in",
        "on", "at", "by", "up", "an", "or", "if", "so", "be", "as",
        "a", "i",
        # Spanish
        "muestra", "mostrar", "buscar", "busca", "listar", "lista",
        "dame", "dime", "cuáles", "cuales", "cuántos", "cuantos",
        "qué", "que", "cómo", "como", "dónde", "donde", "quién",
        "quien", "hay", "tiene", "tienen", "son", "está", "están",
        "los", "las", "les", "del", "por", "para", "con", "sin",
        "sobre", "entre", "desde", "hasta", "más", "menos", "todo",
        "todos", "todas", "toda", "cada", "otro", "otra", "otros",
        "otras", "ese", "esa", "esos", "esas", "este", "esta",
        "estos", "estas", "aquel", "aquella", "uno", "una", "unos",
        "unas", "ser", "haber", "tener", "hacer", "poder", "poner",
        "ver", "dar", "saber", "querer", "llegar", "pasar",
        "el", "la", "lo", "en", "de", "un", "no", "se", "si",
        "ya", "muy", "al", "le", "su", "me", "te", "nos", "mi",
        "tu", "yo", "él", "ella", "ellos", "ellas",
        # Common query words
        "agreements", "agreement", "acuerdos", "acuerdo",
        "universities", "university", "universidad", "universidades",
        "destinations", "destination", "destino", "destinos",
        "students", "student", "estudiante", "estudiantes",
        "subjects", "subject", "asignatura", "asignaturas",
        "degree", "degrees", "titulación", "titulaciones", "grado",
    }

    # Cross-language equivalences: term in question → might appear as this in SQL
    _EQUIVALENCES = {
        # Languages
        "english": {"inglés", "ingles", "english"},
        "inglés": {"english", "inglés", "ingles"},
        "french": {"francés", "frances", "french", "français"},
        "francés": {"french", "francés", "frances", "français"},
        "german": {"alemán", "aleman", "german", "deutsch"},
        "alemán": {"german", "alemán", "aleman", "deutsch"},
        "italian": {"italiano", "italian", "italiana"},
        "italiano": {"italian", "italiano", "italiana"},
        "portuguese": {"portugués", "portugues", "portuguese"},
        "portugués": {"portuguese", "portugués", "portugues"},
        "korean": {"coreano", "korean"},
        "coreano": {"korean", "coreano"},
        "greek": {"griego", "griega", "griegos", "griegas", "greek", "grecia", "greece"},
        "griego": {"greek", "griego", "griega", "griegos", "griegas", "grecia", "greece"},
        "griega": {"greek", "griego", "griega", "griegas", "grecia", "greece"},
        "griegas": {"greek", "griego", "griega", "griegas", "grecia", "greece"},
        "grecia": {"greek", "griego", "griega", "griegas", "grecia", "greece"},
        "greece": {"greek", "griego", "griega", "griegas", "grecia", "greece"},
        "japanese": {"japones", "japonés", "japanese"},
        "japones": {"japanese", "japones", "japonés"},
        "polish": {"polaco", "polish"},
        "polaco": {"polish", "polaco"},
        "spanish": {"español", "spanish", "castellano"},
        "español": {"spanish", "español", "castellano"},
        "none": {"ninguno", "none", "00 ninguno"},
        "ninguno": {"none", "ninguno", "00 ninguno"},
        # Mobility programmes
        "erasmus": {"erasmus", "ka131", "ka171", "erasmus+", "erasmus bip"},
        # Countries
        "finland": {"finlandia", "finland", "finnish", "finlandés", "finlandesa", "finlandeses", "finlandesas"},
        "finlandia": {"finland", "finlandia", "finlandés", "finlandesa", "finlandeses", "finlandesas"},
        "finlandesas": {"finland", "finlandia", "finlandés", "finlandesa", "finlandeses", "finlandesas"},
        "finlandeses": {"finland", "finlandia", "finlandés", "finlandesa", "finlandeses", "finlandesas"},
        "germany": {"alemania", "germany", "alemán", "alemana", "alemanes", "alemanas"},
        "alemania": {"germany", "alemania", "alemán", "alemana", "alemanes", "alemanas"},
        "alemanas": {"germany", "alemania", "alemán", "alemana", "alemanes", "alemanas"},
        "alemanes": {"germany", "alemania", "alemán", "alemana", "alemanes", "alemanas"},
        "france": {"francia", "france", "francés", "francesa", "franceses", "francesas"},
        "francia": {"france", "francia", "francés", "francesa", "franceses", "francesas"},
        "francesas": {"france", "francia", "francés", "francesa", "franceses", "francesas"},
        "franceses": {"france", "francia", "francés", "francesa", "franceses", "francesas"},
        "italy": {"italia", "italy", "italiano", "italiana", "italianos", "italianas"},
        "italia": {"italy", "italia", "italiano", "italiana", "italianos", "italianas"},
        "italianas": {"italy", "italia", "italiano", "italiana", "italianos", "italianas"},
        "italianos": {"italy", "italia", "italiano", "italiana", "italianos", "italianas"},
        "spain": {"españa", "spain", "español", "española", "españoles", "españolas"},
        "españa": {"spain", "españa", "español", "española", "españoles", "españolas"},
        "dutch": {"países bajos", "holanda", "netherlands", "dutch", "holandés", "holandesa", "holandeses", "holandesas"},
        "netherlands": {"países bajos", "holanda", "netherlands", "dutch", "holandés", "holandesa", "holandeses", "holandesas"},
        "holanda": {"netherlands", "países bajos", "holanda", "dutch", "holandés", "holandesa", "holandeses", "holandesas"},
        "holandesas": {"netherlands", "países bajos", "holanda", "dutch", "holandesas", "holandeses"},
        "holandeses": {"netherlands", "países bajos", "holanda", "dutch", "holandesas", "holandeses"},
        "países": {"países bajos", "netherlands", "holanda", "dutch"},
        "lithuania": {"lituania", "lithuania", "lituano", "lituana", "lituanos", "lituanas"},
        "lituania": {"lithuania", "lituania", "lituano", "lituana", "lituanos", "lituanas"},
        "lituanas": {"lithuania", "lituania", "lituano", "lituana", "lituanos", "lituanas"},
        "turkey": {"turquía", "turquia", "turkey", "turco", "turca", "turcos", "turcas"},
        "turquía": {"turkey", "turquía", "turquia", "turco", "turca", "turcos", "turcas"},
        "turcas": {"turkey", "turquía", "turquia", "turco", "turca", "turcos", "turcas"},
        "albania": {"albania"},
        "libya": {"libia", "libya"},
        "libia": {"libya", "libia"},
        "morocco": {"marruecos", "morocco", "marroquí", "marroquíes", "marroquies"},
        "marruecos": {"morocco", "marruecos", "marroquí", "marroquíes", "marroquies"},
        "marroquíes": {"morocco", "marruecos", "marroquí", "marroquíes", "marroquies"},
        "argentina": {"argentina", "argentino", "argentina", "argentinos", "argentinas"},
        "armenia": {"armenia"},
        "australia": {"australia"},
        "austria": {"austria"},
        "bolivia": {"bolivia"},
        "brazil": {"brasil", "brazil"},
        "brasil": {"brazil", "brasil"},
        "canada": {"canadá", "canada"},
        "canadá": {"canada", "canadá"},
        "chile": {"chile"},
        "colombia": {"colombia"},
        "korea": {"corea del sur", "corea", "korea", "south korea"},
        "corea": {"korea", "corea del sur", "south korea"},
        "costa": {"costa rica"},
        "usa": {"estados unidos", "usa", "united states"},
        "united": {"estados unidos", "usa", "united states"},
        "estados": {"estados unidos", "usa", "united states"},
        "philippines": {"filipinas", "philippines"},
        "filipinas": {"philippines", "filipinas"},
        "georgia": {"georgia"},
        "india": {"india"},
        "japan": {"japón", "japan"},
        "japón": {"japan", "japón"},
        "mexico": {"méxico", "mexico"},
        "méxico": {"mexico", "méxico"},
        # Academic disciplines
        "architecture": {"arquitectura", "architecture"},
        "arquitectura": {"architecture", "arquitectura"},
        "law": {"derecho", "law"},
        "derecho": {"law", "derecho"},
        "arts": {"bellas artes", "arts", "fine arts"},
        "engineering": {"ingeniería", "ingenieria", "engineering"},
        "ingeniería": {"engineering", "ingeniería", "ingenieria"},
        "computer": {"informática", "informatica", "computer science", "computer"},
        "informática": {"computer science", "informática", "informatica", "computer"},
        "telecommunications": {"telecomunicación", "telecomunicacion", "telecommunications", "telecom"},
        "telecomunicación": {"telecommunications", "telecomunicación", "telecomunicacion"},
        "economics": {"económicas", "economicas", "economics", "business"},
        "económicas": {"economics", "económicas", "economicas", "business"},
        "business": {"empresariales", "business", "economics"},
        "empresariales": {"business", "empresariales"},
        "science": {"ciencias", "science"},
        "ciencias": {"science", "ciencias"},
        "education": {"educación", "educacion", "education", "didáctica"},
        "educación": {"education", "educación", "educacion"},
        "medicine": {"medicina", "medicine"},
        "medicina": {"medicine", "medicina"},
        "nursing": {"enfermería", "enfermeria", "nursing"},
        "enfermería": {"nursing", "enfermería", "enfermeria"},
        "psychology": {"psicología", "psicologia", "psychology"},
        "psicología": {"psychology", "psicología", "psicologia"},
        "chemistry": {"química", "quimica", "chemistry"},
        "química": {"chemistry", "química", "quimica"},
        "biology": {"biología", "biologia", "biology"},
        "biología": {"biology", "biología", "biologia"},
        "mathematics": {"matemáticas", "matematicas", "mathematics", "maths"},
        "matemáticas": {"mathematics", "matemáticas", "matematicas"},
        "philosophy": {"filosofía", "filosofia", "philosophy"},
        "filosofía": {"philosophy", "filosofía", "filosofia"},
        "history": {"historia", "history"},
        "historia": {"history", "historia"},
        "tourism": {"turismo", "tourism"},
        "turismo": {"tourism", "turismo"},
        "communication": {"comunicación", "comunicacion", "communication"},
        "comunicación": {"communication", "comunicación", "comunicacion"},
        "industrial": {"industrial"},
        "mechanical": {"mecánica", "mecanica", "mechanical"},
        "mecánica": {"mechanical", "mecánica", "mecanica"},
        "electrical": {"eléctrica", "electrica", "electrical"},
        "eléctrica": {"electrical", "eléctrica", "electrica"},
        "electronic": {"electrónica", "electronica", "electronic"},
        "electrónica": {"electronic", "electrónica", "electronica"},
        "energy": {"energía", "energia", "energy"},
        "energía": {"energy", "energía", "energia"},
        "biotechnology": {"biotecnología", "biotecnologia", "biotechnology"},
        "biotecnología": {"biotechnology", "biotecnología", "biotecnologia"},
        "archaeology": {"arqueología", "arqueologia", "archaeology"},
        "arqueología": {"archaeology", "arqueología", "arqueologia"},
        # Common query terms
        "agreements": {"acuerdos", "convenios", "agreements", "destinations"},
        "students": {"estudiantes", "students", "alumnos"},
        "degree": {"titulación", "titulacion", "grado", "degree"},
        "faculty": {"facultad", "faculty", "escuela", "school"},
        "any": {"cualquier", "any", "todos"},
        "cualquier": {"any", "cualquier"},
    }

    # Words that express query intent but won't appear in SQL literally
    _INTENT_WORDS = {
        "requiring", "required", "need", "needs", "needed",
        "level", "minimum", "maximum", "above", "below",
        "available", "active", "current", "valid", "open",
        "undergraduate", "master", "phd", "doctoral",
        "grado", "máster", "doctorado",
        "requiere", "requieren", "necesita", "necesitan",
        "disponible", "disponibles", "activo", "activos",
        "vigente", "vigentes", "abierto", "abiertos",
        "nivel", "mínimo", "máximo",
        # Agreement-related words (not semantic content)
        "convenio", "convenios", "acuerdo", "acuerdos",
        "agreement", "agreements", "mobility", "movilidad",
        "universidades", "universidad", "universities", "university",
    }

    def verify_semantic(self, user_question: str, sql: str) -> dict:
        """Check if the SQL query is semantically aligned with the user question.

        Extracts key terms from the question and checks whether any appear
        in the SQL's string literals or column/table references.
        Cross-language equivalences (e.g. english↔inglés) are handled.

        Returns
        -------
        dict
            aligned: bool, question_terms: list, sql_values: list,
            missing_terms: list, issues: list, penalty: int
        """
        # 1. Extract key terms from the user question
        q_lower = user_question.lower()
        raw_words = re.split(r'[\s,;:!?¿¡()\[\]{}\"\']+', q_lower)
        question_terms = [
            w for w in raw_words
            if len(w) >= 3
            and w not in self._QUESTION_STOP_WORDS
            and w not in self._INTENT_WORDS
        ]

        if not question_terms:
            return {"aligned": True, "question_terms": [], "sql_values": [],
                    "missing_terms": [], "issues": [], "penalty": 0}

        # 2. Extract string literals from the SQL (LIKE '%X%', = 'X', IN ('X','Y'))
        sql_literals = re.findall(r"['\"]%?([^'\"]+?)%?['\"]", sql)
        sql_values_lower = " ".join(v.lower() for v in sql_literals)
        sql_full_lower = sql.lower()

        # 3. Check which question terms appear in SQL (with equivalences)
        found = []
        missing = []
        for term in question_terms:
            # Direct match in SQL values or full SQL text
            if term in sql_values_lower or term in sql_full_lower:
                found.append(term)
                continue
            # Check cross-language equivalences
            equivalents = self._EQUIVALENCES.get(term, set())
            if any(eq in sql_values_lower or eq in sql_full_lower for eq in equivalents):
                found.append(term)
                continue
            missing.append(term)

        # 4. Determine alignment
        # Only flag as mismatch if NO question terms match at all
        issues = []
        penalty = 0

        if len(question_terms) > 0 and len(found) == 0:
            issues.append(
                f"Semantic mismatch: question mentions '{', '.join(question_terms)}' "
                f"but SQL filters on '{', '.join(sql_literals[:3])}'"
            )
            penalty = 40

        return {
            "aligned": penalty == 0,
            "question_terms": question_terms,
            "sql_values": sql_literals,
            "missing_terms": missing,
            "issues": issues,
            "penalty": penalty,
        }

    def _suggest_similar_values(self, sql: str) -> list:
        """When a LIKE query returns 0 results, check if similar values exist.

        Extracts the column and search term from LIKE clauses, then queries
        the database for actual values that are similar (using substring or
        character overlap).  Returns a list of suggestion strings.
        """
        suggestions = []
        like_clauses = re.findall(
            r"(\w+)\s+LIKE\s+['\"]%([^%'\"]+)%['\"]", sql, re.IGNORECASE
        )
        if not like_clauses:
            return suggestions

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            for col, search_term in like_clauses:
                # Find the table containing this column
                table = None
                for t, cols in self._schema.items():
                    if col.lower() in cols:
                        table = t
                        break
                if not table:
                    continue

                # Get distinct values for this column
                try:
                    cursor.execute(
                        f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL"
                    )
                    db_values = [row[0] for row in cursor.fetchall() if row[0]]
                except sqlite3.Error:
                    continue

                # Find similar values: require that the search term and
                # the candidate share a long common substring, or that
                # every word of the search term has a close match in the value.
                search_lower = search_term.lower()
                search_words = search_lower.split()
                candidates = []
                for val in db_values:
                    val_lower = val.lower()
                    # Strategy 1: long prefix match (e.g. "Kolegia" vs "Kolegija")
                    # Find longest common prefix between search and value words
                    val_words = val_lower.split()
                    word_matches = 0
                    for sw in search_words:
                        for vw in val_words:
                            # Words share a prefix of >= 70% of the shorter word
                            min_len = min(len(sw), len(vw))
                            if min_len < 3:
                                continue
                            prefix_len = 0
                            for a, b in zip(sw, vw):
                                if a == b:
                                    prefix_len += 1
                                else:
                                    break
                            if prefix_len >= min_len * 0.7:
                                word_matches += 1
                                break
                    # Require ALL search words to have a close match
                    if len(search_words) >= 1 and word_matches == len(search_words):
                        candidates.append(val)

                if candidates:
                    # Show up to 3 suggestions
                    shown = candidates[:3]
                    suggestions.append(
                        f"Did you mean: {', '.join(shown)}? "
                        f"(searched '{search_term}' in {col})"
                    )
            conn.close()
        except sqlite3.Error:
            pass

        return suggestions

    def autocorrect_sql(self, sql: str) -> tuple:
        """Try to fix a LIKE query that returned 0 results by replacing
        misspelled search terms with the best matching value from the database.

        Returns
        -------
        tuple
            (corrected_sql: str or None, corrections: list of str)
            corrected_sql is None if no corrections were possible.
        """
        like_clauses = re.findall(
            r"(\w+)\s+LIKE\s+(['\"])(%[^%'\"]+%)\2", sql, re.IGNORECASE
        )
        if not like_clauses:
            return None, []

        corrected_sql = sql
        corrections = []

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            for col, _quote, like_pattern in like_clauses:
                # Extract the search term from %term%
                search_term = like_pattern.strip('%')
                search_words = search_term.lower().split()

                # Find the table
                table = None
                for t, cols in self._schema.items():
                    if col.lower() in cols:
                        table = t
                        break
                if not table:
                    continue

                # Check if the original query would return results
                try:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE ?",
                        [f"%{search_term}%"]
                    )
                    if cursor.fetchone()[0] > 0:
                        continue  # Original term works, no correction needed
                except sqlite3.Error:
                    continue

                # Get distinct values and find the best match
                try:
                    cursor.execute(
                        f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL"
                    )
                    db_values = [row[0] for row in cursor.fetchall() if row[0]]
                except sqlite3.Error:
                    continue

                best_match = None
                best_score = 0
                for val in db_values:
                    val_words = val.lower().split()
                    word_matches = 0
                    for sw in search_words:
                        for vw in val_words:
                            min_len = min(len(sw), len(vw))
                            if min_len < 3:
                                continue
                            prefix_len = 0
                            for a, b in zip(sw, vw):
                                if a == b:
                                    prefix_len += 1
                                else:
                                    break
                            if prefix_len >= min_len * 0.7:
                                word_matches += 1
                                break
                    if word_matches == len(search_words) and word_matches > best_score:
                        best_score = word_matches
                        best_match = val

                if best_match:
                    # Replace the LIKE value in the SQL
                    old_like = f"%{search_term}%"
                    new_like = f"%{best_match}%"
                    corrected_sql = corrected_sql.replace(old_like, new_like)
                    corrections.append(
                        f"Auto-corrected '{search_term}' → '{best_match}'"
                    )

            conn.close()
        except sqlite3.Error:
            return None, []

        if corrections:
            return corrected_sql, corrections
        return None, []

    def verify_with_execution(self, sql: str, success: bool, result_count: int) -> dict:
        """Verify SQL and include execution results."""
        result = self.verify(sql)
        result["executed_ok"] = success
        result["result_count"] = result_count
        result["suggestions"] = []

        # Adjust confidence based on execution
        if not success:
            result["confidence"] = max(0, result["confidence"] - 30)
            result["issues"].append("SQL execution failed")
        elif result_count == 0:
            result["issues"].append("Query returned no results")
            # Try to find similar values that might match
            suggestions = self._suggest_similar_values(sql)
            if suggestions:
                result["suggestions"] = suggestions
                for s in suggestions:
                    result["issues"].append(s)

        # 4. Result ratio check: if query returns >70% of all rows, it's too broad
        if success and result_count > 0 and result["verified_tables"]:
            table = result["verified_tables"][0]
            total = self._get_total_rows(table)
            if total > 0:
                ratio = result_count / total
                if ratio > 0.7:
                    result["issues"].append(
                        f"Query returns {result_count}/{total} rows ({round(ratio*100)}% of table — likely too broad)"
                    )
                    result["confidence"] = max(0, result["confidence"] - 25)
            # Don't penalize confidence for empty results — it may be correct

        return result

    # ------------------------------------------------------------------
    # SQL parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_comments(sql: str) -> str:
        """Remove SQL comments."""
        sql = re.sub(r'--[^\n]*', '', sql)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        return sql

    @staticmethod
    def _extract_tables(sql: str) -> list:
        """Extract table names from FROM and JOIN clauses."""
        tables = []
        seen = set()

        # FROM clause: FROM table_name [alias]
        for m in re.finditer(r'\bFROM\s+(\w+)', sql, re.IGNORECASE):
            t = m.group(1)
            if t.lower() not in seen and t.upper() not in ("SELECT", "WHERE", "AND", "OR"):
                tables.append(t)
                seen.add(t.lower())

        # JOIN clause: JOIN table_name [alias]
        for m in re.finditer(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE):
            t = m.group(1)
            if t.lower() not in seen:
                tables.append(t)
                seen.add(t.lower())

        return tables

    @staticmethod
    def _extract_aliases(sql: str) -> set:
        """Extract table aliases from FROM and JOIN clauses (e.g. 'subjects s' → 's')."""
        aliases = set()
        # FROM table alias (no AS keyword)
        for m in re.finditer(r'\bFROM\s+(\w+)\s+(\w+)', sql, re.IGNORECASE):
            candidate = m.group(2).lower()
            if candidate not in ("where", "on", "join", "inner", "left", "right",
                                 "outer", "cross", "natural", "order", "group",
                                 "having", "limit", "as"):
                aliases.add(candidate)
        # FROM table AS alias
        for m in re.finditer(r'\bFROM\s+\w+\s+AS\s+(\w+)', sql, re.IGNORECASE):
            aliases.add(m.group(1).lower())
        # JOIN table alias
        for m in re.finditer(r'\bJOIN\s+(\w+)\s+(\w+)', sql, re.IGNORECASE):
            candidate = m.group(2).lower()
            if candidate not in ("on", "where", "using", "as"):
                aliases.add(candidate)
        # JOIN table AS alias
        for m in re.finditer(r'\bJOIN\s+\w+\s+AS\s+(\w+)', sql, re.IGNORECASE):
            aliases.add(m.group(1).lower())
        return aliases

    @staticmethod
    def _extract_columns(sql: str) -> list:
        """Extract column names from SELECT, WHERE, ORDER BY, GROUP BY, etc."""
        # First, remove string literals so their contents are not parsed as columns
        # e.g. LIKE '%Países Bajos%' → LIKE ''
        sql_no_strings = re.sub(r"'[^']*'", "''", sql)
        sql_no_strings = re.sub(r'"[^"]*"', '""', sql_no_strings)

        # Extract table aliases to exclude them from column detection
        aliases = SQLVerifier._extract_aliases(sql)

        columns = []
        seen = set()

        # SQL keywords to exclude
        keywords = {
            "select", "from", "where", "and", "or", "not", "in", "is",
            "null", "like", "between", "exists", "as", "on", "join",
            "inner", "left", "right", "outer", "cross", "natural",
            "order", "by", "group", "having", "limit", "offset",
            "asc", "desc", "distinct", "count", "sum", "avg", "min",
            "max", "case", "when", "then", "else", "end", "cast",
            "coalesce", "ifnull", "nullif", "upper", "lower", "trim",
            "length", "substr", "replace", "instr", "typeof", "abs",
            "round", "total", "union", "all", "except", "intersect",
            "values", "into", "set", "true", "false", "with",
            "recursive", "over", "partition", "row_number", "rank",
            "dense_rank", "glob", "regexp", "escape",
        }

        # Match identifiers (word or table.word) from the string-stripped SQL
        # SELECT columns
        select_match = re.search(r'\bSELECT\s+(.*?)\bFROM\b', sql_no_strings, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_part = select_match.group(1)
            for m in re.finditer(r'(\w+(?:\.\w+)?)', select_part):
                ident = m.group(1)
                if ident.lower() not in keywords and not ident.isdigit() and ident.lower() not in aliases:
                    if ident.lower() not in seen:
                        columns.append(ident)
                        seen.add(ident.lower())

        # WHERE, ORDER BY, GROUP BY columns
        for clause in re.finditer(r'\b(?:WHERE|ORDER\s+BY|GROUP\s+BY|HAVING|ON)\b\s+(.*?)(?=\b(?:ORDER|GROUP|HAVING|LIMIT|$))', sql_no_strings, re.IGNORECASE | re.DOTALL):
            clause_text = clause.group(1)
            for m in re.finditer(r'(\w+(?:\.\w+)?)', clause_text):
                ident = m.group(1)
                if ident.lower() not in keywords and not ident.isdigit() and ident.lower() not in aliases:
                    if ident.lower() not in seen:
                        columns.append(ident)
                        seen.add(ident.lower())

        return columns

    @staticmethod
    def sql_to_text(sql: str) -> str:
        """Convert a SQL query into a human-readable natural language description.

        Designed for the simple, single-table queries generated by Pisha4.
        Returns a plain-language string that non-technical users can understand.
        """
        if not sql or not sql.strip():
            return ""

        sql_clean = sql.strip().rstrip(";")

        # Friendly names for tables
        table_names = {
            "destinations": "mobility agreements",
            "students": "students",
            "subjects": "subjects",
            "degree": "degrees",
        }

        # Friendly names for columns
        col_names = {
            "host_institution": "university",
            "destination_country": "country",
            "mobility_program": "mobility programme",
            "uma_faculties": "UMA faculties",
            "uma_degrees": "UMA degrees",
            "lang_1_name": "first required language",
            "lang_1_level": "first language level",
            "lang_2_name": "second required language",
            "lang_2_level": "second language level",
            "allows_undergraduate": "allows undergraduates",
            "allows_master": "allows master students",
            "allows_phd": "allows PhD students",
            "min_gpa_requirement": "minimum GPA",
            "student_vacancies": "available places",
            "name": "name",
            "email": "email",
            "degree_id": "degree",
            "id": "ID",
        }

        def _friendly_col(col):
            """Return friendly column name, stripping table alias prefixes."""
            col = col.strip()
            if "." in col:
                col = col.split(".")[-1]
            return col_names.get(col.lower(), col.replace("_", " "))

        def _friendly_table(t):
            return table_names.get(t.strip().lower(), t.strip())

        parts = []

        try:
            upper = sql_clean.upper()

            # --- What is being selected ---
            select_m = re.match(
                r'SELECT\s+(.*?)\s+FROM\s+(\w+)',
                sql_clean, re.IGNORECASE | re.DOTALL)
            if not select_m:
                return ""

            select_clause = select_m.group(1).strip()
            main_table = select_m.group(2).strip()
            friendly_table = _friendly_table(main_table)

            # COUNT
            count_m = re.match(r'COUNT\s*\(\s*\*\s*\)', select_clause, re.IGNORECASE)
            if count_m:
                parts.append(f"Count the number of {friendly_table}")
            # DISTINCT
            elif re.match(r'DISTINCT\s+', select_clause, re.IGNORECASE):
                dist_cols = re.sub(r'^DISTINCT\s+', '', select_clause, flags=re.IGNORECASE)
                cols = [_friendly_col(c) for c in dist_cols.split(",")]
                parts.append(f"List the distinct values of {', '.join(cols)} from {friendly_table}")
            # SELECT *
            elif select_clause.strip() == "*":
                parts.append(f"Retrieve all {friendly_table}")
            # Specific columns
            else:
                cols = [_friendly_col(c) for c in select_clause.split(",")]
                parts.append(f"Show {', '.join(cols)} from {friendly_table}")

            # --- JOIN ---
            join_m = re.search(
                r'JOIN\s+(\w+)\s+\w*\s*ON\s+', sql_clean, re.IGNORECASE)
            if join_m:
                join_table = _friendly_table(join_m.group(1))
                parts.append(f"linked to {join_table}")

            # --- WHERE conditions ---
            where_m = re.search(
                r'WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT\s+|$)',
                sql_clean, re.IGNORECASE | re.DOTALL)
            if where_m:
                where_clause = where_m.group(1).strip()

                def _parse_single_condition(cond):
                    """Parse a single atomic condition into friendly text."""
                    cond = cond.strip().strip("()")
                    # LIKE '%value%'
                    like_m = re.match(
                        r"(\w+(?:\.\w+)?)\s+LIKE\s+'%(.+?)%'",
                        cond, re.IGNORECASE)
                    if like_m:
                        return f"{_friendly_col(like_m.group(1))} contains \"{like_m.group(2)}\""
                    # = 'value'
                    eq_m = re.match(
                        r"(\w+(?:\.\w+)?)\s*=\s*'(.+?)'",
                        cond, re.IGNORECASE)
                    if eq_m:
                        return f"{_friendly_col(eq_m.group(1))} is \"{eq_m.group(2)}\""
                    # IS NULL / IS NOT NULL
                    null_m = re.match(
                        r"(\w+(?:\.\w+)?)\s+IS\s+(NOT\s+)?NULL",
                        cond, re.IGNORECASE)
                    if null_m:
                        col = _friendly_col(null_m.group(1))
                        if null_m.group(2):
                            return f"{col} is specified"
                        else:
                            return f"{col} is not specified"
                    # Numeric comparisons: >=, <=, >, <
                    num_m = re.match(
                        r"(\w+(?:\.\w+)?)\s*(>=|<=|>|<)\s*(\d+(?:\.\d+)?)",
                        cond, re.IGNORECASE)
                    if num_m:
                        col = _friendly_col(num_m.group(1))
                        op = {">=": "is at least", "<=": "is at most", ">": "is more than", "<": "is less than"}
                        return f"{col} {op.get(num_m.group(2), num_m.group(2))} {num_m.group(3)}"
                    # Fallback: include as-is but clean up
                    return cond

                def _parse_and_group(group_str):
                    """Parse a group of AND-connected conditions."""
                    conditions = re.split(r'\s+AND\s+', group_str, flags=re.IGNORECASE)
                    return [_parse_single_condition(c) for c in conditions]

                # Check if there's an OR at the top level (possibly with parenthesized groups)
                # Split by OR that's outside parentheses
                or_groups = re.split(r'\)\s+OR\s+\(', where_clause, flags=re.IGNORECASE)
                if len(or_groups) > 1:
                    # Clean leading ( from first group and trailing ) from last
                    or_groups[0] = or_groups[0].lstrip("( ")
                    or_groups[-1] = or_groups[-1].rstrip(") ")
                    group_texts = []
                    for g in or_groups:
                        filters = _parse_and_group(g)
                        group_texts.append(" and ".join(filters))
                    parts.append(f"where ({') or ('.join(group_texts)})")
                else:
                    # Also check for bare OR without parentheses
                    or_parts = re.split(r'\s+OR\s+', where_clause, flags=re.IGNORECASE)
                    if len(or_parts) > 1:
                        group_texts = []
                        for g in or_parts:
                            filters = _parse_and_group(g.strip("() "))
                            group_texts.append(" and ".join(filters))
                        parts.append(f"where ({') or ('.join(group_texts)})")
                    else:
                        # Simple AND-only case
                        filters = _parse_and_group(where_clause)
                        if filters:
                            parts.append(f"where {' and '.join(filters)}")

            # --- GROUP BY ---
            group_m = re.search(
                r'GROUP\s+BY\s+(.*?)(?:\s+ORDER\s+BY|\s+HAVING|\s+LIMIT|$)',
                sql_clean, re.IGNORECASE | re.DOTALL)
            if group_m:
                cols = [_friendly_col(c) for c in group_m.group(1).split(",")]
                parts.append(f"grouped by {', '.join(cols)}")

            # --- ORDER BY ---
            order_m = re.search(
                r'ORDER\s+BY\s+(.*?)(?:\s+LIMIT|$)',
                sql_clean, re.IGNORECASE | re.DOTALL)
            if order_m:
                order_clause = order_m.group(1).strip()
                if "DESC" in order_clause.upper():
                    col = re.sub(r'\s+(ASC|DESC).*', '', order_clause, flags=re.IGNORECASE)
                    parts.append(f"sorted by {_friendly_col(col)} (highest first)")
                else:
                    col = re.sub(r'\s+(ASC|DESC).*', '', order_clause, flags=re.IGNORECASE)
                    parts.append(f"sorted by {_friendly_col(col)}")

            # --- LIMIT ---
            limit_m = re.search(r'LIMIT\s+(\d+)', sql_clean, re.IGNORECASE)
            if limit_m:
                parts.append(f"showing up to {limit_m.group(1)} results")

        except Exception:
            return ""

        if not parts:
            return ""

        text = " ".join(parts)
        # Capitalize first letter
        return text[0].upper() + text[1:]


class SQLReliabilityBadge:
    """Render HTML reliability badges for Text-to-SQL responses."""

    @staticmethod
    def source_badge(
        verification: dict,
        transparency: str = "crystal_box",
        prompt_level: str = None,
        model_name: str = None,
        is_local_llm: bool = False,
    ) -> str:
        # Procedural banners now handle transparency inline — no header badge needed
        return ""

    @staticmethod
    def _source_badge_legacy(
        verification: dict,
        transparency: str = "crystal_box",
        prompt_level: str = None,
        model_name: str = None,
        is_local_llm: bool = False,
    ) -> str:
        """Return an HTML badge for a verified SQL query.

        Parameters
        ----------
        verification : dict
            Result from SQLVerifier.verify() or verify_with_execution().
        transparency : str
            "crystal_box", "grey_box", or "black_box".
        """
        if transparency == "black_box":
            return ""

        is_dev = transparency == "crystal_box"
        confidence = verification.get("confidence", 0)
        issues = verification.get("issues", [])
        verified_tables = verification.get("verified_tables", [])
        unknown_tables = verification.get("unknown_tables", [])
        verified_cols = verification.get("verified_columns", [])
        unknown_cols = verification.get("unknown_columns", [])
        executed_ok = verification.get("executed_ok")
        result_count = verification.get("result_count")

        s = 'font-size:0.8em;'
        b = 'font-weight:bold;'

        # --- Line 1: Agent tuning ---
        tuning_parts = []
        if model_name:
            llm_location = 'On-premise' if is_local_llm else 'Cloud'
            llm_icon = '/static/icon_llm_local.svg' if is_local_llm else '/static/icon_llm_cloud.svg'
            tuning_parts.append(
                f'<img src="{llm_icon}" style="width:14px;height:14px;vertical-align:middle;"> '
                f'{model_name} ({llm_location})'
            )
        tuning_line = ""
        if tuning_parts:
            tuning_line = (
                f'<span style="{s}"><span style="{b}">Agent tuning:</span> '
                f'{" / ".join(tuning_parts)}</span>'
            )

        # --- Line 1b: Prompt ---
        # SQL generation by the LLM needs supervision (prompt-level dependent),
        # but data rendering from executed queries is always reliable.
        supervision_line = ""
        if prompt_level:
            sv_labels = {
                "stringent": ("\U0001F7E2", "Stringent", "#155724", "#d4edda"),
                "tolerant":  ("\U0001F7E1", "Tolerant",  "#856404", "#fff3cd"),
                "lax":       ("\U0001F534", "Lax",       "#721c24", "#f8d7da"),
            }
            if executed_ok:
                # SQL executed successfully — data comes from the DB, not the LLM
                sql_dot, sql_lbl, sql_fg, sql_bg = sv_labels.get(
                    prompt_level, ("\U0001F7E1", "Mid", "#856404", "#fff3cd"))
                supervision_line = (
                    f'<span style="{s}"><span style="{b}">Prompt:</span> '
                    f'SQL generation: '
                    f'<span style="background-color:{sql_bg};color:{sql_fg};'
                    f'padding:1px 6px;border-radius:3px;font-weight:bold;">'
                    f'{sql_dot} {sql_lbl}</span>'
                    f' / Data rendering: '
                    f'<span style="background-color:#d4edda;color:#155724;'
                    f'padding:1px 6px;border-radius:3px;font-weight:bold;">'
                    f'\U0001F7E2 None (from database)</span></span>'
                )
            else:
                # SQL did not execute or failed — only LLM supervision applies
                dot, lbl, fg, bg = sv_labels.get(
                    prompt_level, ("\U0001F7E1", "Mid", "#856404", "#fff3cd"))
                supervision_line = (
                    f'<span style="{s}"><span style="{b}">Prompt:</span> '
                    f'<span style="background-color:{bg};color:{fg};'
                    f'padding:1px 6px;border-radius:3px;font-weight:bold;">'
                    f'{dot} {lbl}</span></span>'
                )

        # --- Line 2: Schema verification ---
        total_tables = len(verified_tables) + len(unknown_tables)
        total_cols = len(verified_cols) + len(unknown_cols)

        src_parts = []
        if total_tables > 0:
            if unknown_tables:
                src_parts.append(f'\U0001F534 Tables: {len(verified_tables)}/{total_tables} verified')
            else:
                src_parts.append(f'\U0001F7E2 Tables: {len(verified_tables)}/{total_tables} verified')

        if total_cols > 0:
            if unknown_cols:
                src_parts.append(f'\U0001F534 Columns: {len(verified_cols)}/{total_cols} verified')
            else:
                src_parts.append(f'\U0001F7E2 Columns: {len(verified_cols)}/{total_cols} verified')

        if executed_ok is not None:
            if executed_ok:
                exec_str = f'\U0001F7E2 Executed OK'
                if result_count is not None:
                    exec_str += f' ({result_count} results)'
            else:
                exec_str = '\U0001F534 Execution failed'
            src_parts.append(exec_str)

        source_line = ""
        if src_parts:
            source_line = (
                f'<span style="{s}"><span style="{b}">SQL verification:</span> '
                f'{" / ".join(src_parts)}</span>'
            )

        # Issues detail (crystal box only)
        issues_line = ""
        if is_dev and issues:
            issues_html = "; ".join(issues[:3])
            if len(issues) > 3:
                issues_html += f" (+{len(issues) - 3} more)"
            issues_line = f'<span style="{s}color:#856404;">\u26A0\uFE0F {issues_html}</span>'

        # --- Line 3: Reliability score ---
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

        # Assemble
        lines = []
        if tuning_line:
            lines.append(tuning_line)
        if supervision_line:
            lines.append(supervision_line)
        if source_line:
            lines.append(source_line)
        if issues_line:
            lines.append(issues_line)
        lines.append(reliability_line)

        if not is_dev:
            lines = [l for l in lines if "Reliability" in l or "Agent tuning" in l or "Supervision" in l]

        body = '<br>'.join(lines)
        return f'<div class="claim-badge-area" style="margin-bottom:10px;">{body}</div>\n\n'
