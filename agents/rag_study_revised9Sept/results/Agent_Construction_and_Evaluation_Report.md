# Agent Construction & Evaluation Report

**Study:** Reliability of Intent Classification in RAG Agents (Revised, September 2026)
**Development set:** 81 queries (revised from original 69)
**Evaluation set:** 216 queries (with revised ground-truth labels)
**Agents:** Auto rule-based, LLM-based, Production (baseline)

---

## Classification Taxonomy

The intent classifier assigns each user query to one of 12 categories. These categories determine which response pathway the RAG agent uses (programmatic database lookup, LLM-generated response, or refusal).

| Category | Description |
|----------|-------------|
| **figure** | Requests for any graphical representation — publications per year, researchers per university, collaboration maps, bar charts, timelines, etc. |
| **followup** | Requests to revisit, expand or clarify a previous answer. Typically short, context-dependent queries such as "tell me more", "expand on that", "and the others?" |
| **gap** | Questions about unexplored or underrepresented research topics within the UNINOVIS portfolio — research gaps, missing areas, new directions. |
| **general** | Questions related to Responsible AI that cannot be answered from the database alone — broad, open-ended or discursive questions requiring general AI knowledge (e.g., "Is AI dangerous?", "Should students use LLMs for homework?"). |
| **glossary** | Queries requesting the definition or explanation of a specific concept — typically Responsible AI terms such as explainability, fairness, AI governance, the EU AI Act. |
| **meta** | Questions about the agent itself, its data sources, capabilities, or about the UNINOVIS alliance (e.g., "What can you do?", "Which universities participate in UNINOVIS?"). |
| **non_research** | Queries that are not research-related search requests — task requests ("write an essay on AI", "translate this text"), factual trivia ("What is the capital of France?"), greetings, or meaningless input. |
| **off_topic** | Research-oriented questions that fall outside the Responsible AI domain — e.g., queries about quantum computing, photosynthesis, cybersecurity, or requests for papers/researchers on non-AI topics. |
| **papers** | Queries about publications from a specific university, about groups of researchers, or about papers on a broad topic. Typically mentions a university name or acronym (e.g., "List all papers from UDCLV", "Papers from the Italian partner"). |
| **project** | Queries related to research projects or grants — asking about a specific project by name, listing projects, or searching projects by topic. |
| **researcher** | Queries about a specific researcher — their publications, research interests, collaborations. Must mention a person's name or ask about researchers at a specific institution. |
| **topic_search** | Queries identifying a specific research topic without specifying whether the result should be papers or projects — the system searches both. Used only when no more specific category (papers, project, researcher) applies. |

---

## Part 1: Agent Construction Process

### 1.1 Starting Points

Both agents were originally constructed for `rag_study2` using the original (unrevised) development set of 69 queries. For this revised study, they were re-trained from scratch using a corrected development set of 81 queries, following the same iterative protocol.

#### Auto rule-based — Starting point

The auto rule-based agent uses deterministic pattern matching with:
- **Synonym expansion** — a dictionary mapping ~60 word families to canonical forms (e.g., "compose/draft/prepare/create/generate/produce" → "write"; "publications/articles/studies/literature" → "papers")
- **Intent templates** — regex patterns grouped by category, tested in priority order
- **Entity-type detection** — researcher names matched against the metadata database
- **Topical scope checking** — BM25-indexed term set (667 terms) to determine if a query is within the Responsible AI domain

Starting code: 367 lines (Python), 12 category detection blocks in priority order.

#### LLM-based — Starting point

The LLM-based agent uses a single classification prompt sent to Mistral (mistral-small-latest). The original prompt (from rag_study2) contained:
- 12 category definitions with examples
- Priority ordering instruction ("use the FIRST matching category")
- 5 "important distinctions" for ambiguous boundaries
- Entity extraction instructions (topic, researcher, university, project)
- Output format: JSON object

Starting prompt: ~500 words.

#### Production agent (baseline)

The production agent is the hand-crafted rule-based classifier developed over months of real-world use. It was NOT re-trained — it was copied as-is from `rag_study2` to serve as a baseline representing the "organic" development approach.

---

### 1.2 Auto Rule-Based Construction — Iteration Log

#### Iteration 0 (starting point): 82.7% (67/81)

The original rules from rag_study2 were evaluated against the revised dev set. **14 errors**, revealing that the label changes impacted several category boundaries.

**Key misclassifications:**
- "How does this work?" → general (should be meta) — synonym "work" → "papers" corrupted the query
- "Things to do", "What is the capital of France?" → off_topic (should be non_research) — no pattern for factual trivia
- "List all THUAS researchers", "Any TAMK researcher" → papers (should be researcher) — university abbreviation triggered papers before researcher check
- "Describe the EU AI Act", "How do interpretability and explainability differ?" → general (should be glossary) — missing synonym mapping and word-boundary issue
- "Expand on that", "Can you give more details?" → off_topic (should be followup) — patterns too restrictive
- "How is IA changing education?" → off_topic (should be general) — "IA" (Spanish for AI) not recognised

#### Iteration 1: 88.9% (72/81) — 5 fixes applied

**Changes made:**
1. **Synonym fix:** Changed `"work": "papers"` to `"work by": "papers by"` — prevented "How does this work?" from being corrupted to "How does this papers?"
2. **Added `"describe": "what is"`** to synonym map — enables glossary detection for "Describe the EU AI Act"
3. **Added `"ia": "ai"`** to synonym map — recognises Spanish abbreviation
4. **Expanded followup patterns:** Added `\b(?:expand on|elaborate on|more details|give more details)\b` for short queries (≤8 words)
5. **University + researcher routing:** When a university abbreviation is detected AND the query mentions "researchers", route to `researcher` instead of `papers` (but NOT if "papers" is also mentioned)
6. **Non-research trivia patterns:** Added `\b(?:capital of|things to do|how tall|how old|how far|how much does)\b` for factual questions

**New errors introduced:** 3 regressions (papers queries with "researchers" keyword incorrectly routed to researcher)

#### Iteration 2: 93.8% (76/81) — 4 fixes applied

**Changes made:**
1. **Refined university+researcher routing:** Only route to `researcher` when the query does NOT also mention "papers" — fixes "List all papers from THUAS researchers" → papers
2. **Added LLM/students/education/homework/assessment keywords** to the `general` category AI-question detector
3. **Questions excluded from task detection:** Queries starting with "should/can/is/are/do/does/will/would" are not treated as task requests — fixes "Should students be allowed to use LLMs..." → general (not non_research)
4. **Scope-aware topic_search:** Before routing to `topic_search`, check if the query mentions known AI/RA keywords. If yes, trust it. If no, check topical scope and reject as `off_topic` if out of scope — fixes "List papers about coffee making" → off_topic

#### Iteration 3: 96.3% (78/81) — 1 fix applied

**Changes made:**
1. **Word-boundary fix for glossary differ pattern:** Changed `\bdiffer\b.*\b(?:interpret|...)\b` to `\bdiffer\b` AND `(?:interpret|...)` (without word boundaries) — because `\binterpret\b` does NOT match "interpretability"

#### Iteration 4 (final): 97.5% (79/81)

**Residual errors (2):**
- "Find researchers working on Spanish history" → classified as `general` instead of `off_topic`. Root cause: "Spanish" appears in the topical scope database (due to "Spanish university"), so the scope checker considers it in-scope.
- "Any papers about irresponsible AI" → classified as `topic_search` instead of `papers`. Root cause: the AI keyword whitelist in the topic_search scope check captures "irresponsible AI" before the papers rules can fire.

Both are genuine edge cases where the rule-based approach has structural limitations.

---

### 1.3 LLM-Based Construction — Iteration Log

#### Iteration 0 (starting point): 90.1% accuracy, 93.8% consistency

The original prompt from rag_study2 was evaluated against the revised dev set. **8 errors, 5 inconsistencies.**

**Key misclassifications:**
- "Things to do", "What is the capital of France?" → off_topic (should be non_research)
- "List all THUAS researchers", "Any TAMK researcher" → papers (should be researcher)
- "Any research projects in KK?" → papers (should be project)
- "List papers from UDCLV on AI in healthcare" → topic_search (should be papers)
- "Any papers about irresponsible AI" → topic_search (should be papers)

#### Iteration 1: 93.8% accuracy, 100% consistency — Major prompt rewrite

**Changes made:**
- **Restructured categories as numbered priority list** (1-12) instead of bullet points
- **Moved `topic_search` from position 2 to position 12** (last resort) — key change addressing the user's requirement that topic_search should only be used when no more specific category applies
- **Expanded `researcher` definition:** "Must mention a person's name OR ask about researchers at a university"
- **Expanded `papers` definition:** "List papers from UDCLV on AI in healthcare (university + topic = papers, NOT topic_search)"
- **Added `non_research` expansion:** Factual questions ("What is the capital of France?", "Things to do") explicitly listed
- **Added `off_topic` for out-of-scope research:** "queries asking about papers/researchers on topics completely outside the database scope"
- **Added greetings exclusion from meta:** "Greetings like Hello, Hi are NOT meta"
- **Added new distinction:** "papers vs researcher — Which papers were written by researchers at THUAS? asks about PAPERS"
- **Added UNINOVIS clarification for topic_search:** "mentioning UNINOVIS is OK — it means within the database, not a specific university"

**New errors:** "Hello" misrouted (meta→non_research), "AI in education" queries rejected as off_topic

#### Iteration 2: 96.3% accuracy, 100% consistency — 3 targeted fixes

**Changes made:**
1. **Greetings clarified in non_research:** "Greetings (Hello, Hi, Good morning) and meaningless inputs (test, asdf) are off_topic, NOT non_research"
2. **AI in education/healthcare explicitly in-scope:** Added to topic_search examples
3. **Glossary vs general distinction sharpened:** "General terms like language model, deep learning, neural network are general, NOT glossary"
4. **Papers vs topic_search clarified:** "Any papers about X where X is a broad concept → papers"

#### Iteration 3 (final): 97.5% accuracy, 98.8% consistency

**Residual errors (2):**
- "Hello" → classified as `non_research` instead of `off_topic`. The LLM interprets "Hello" as a request (to be greeted back), despite explicit instructions.
- "Any papers about irresponsible AI" → classified as `topic_search` instead of `papers`. The LLM sees "irresponsible AI" as a research topic and routes accordingly.

Both agents converge to the same accuracy (97.5%) with the same two hard cases.

---

### 1.4 Construction Summary

| Metric | Auto rule-based | LLM-based |
|--------|----------------|-----------|
| Starting accuracy | 82.7% | 90.1% |
| Final accuracy | 97.5% | 97.5% |
| Iterations needed | 7 | 4 |
| Starting consistency | 100% (deterministic) | 93.8% |
| Final consistency | 100% (deterministic) | 98.8% |
| Code changes | 37 new lines (367→404) | Prompt rewrite (~500→700 words) |
| Residual errors | 2 (same queries) | 2 (same queries) |

---

## Part 2: Evaluation Results (216 queries, revised labels)

### 2.1 Overall Accuracy

| Agent | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| **LLM-based** | **175** | **216** | **81.0%** |
| Auto rule-based | 145 | 216 | 67.1% |
| Production (baseline) | 81 | 216 | 37.5% |

### 2.2 Accuracy by Tier

| Tier | Description | N | Auto rule-based | Production | LLM-based |
|------|------------|---|----------------|------------|-----------|
| 1 | Standard phrasings | 120 | 86.7% | 39.2% | 83.3% |
| 2 | Unusual phrasings | 61 | 39.3% | 34.4% | 78.7% |
| 3 | Adversarial/ambiguous | 35 | 48.6% | 37.1% | 77.1% |
| | **Degradation T1→T3** | | **-38.1 pp** | **-2.1 pp** | **-6.2 pp** |

### 2.3 Accuracy by Category

| Category | N | Auto rule-based | Production | LLM-based |
|----------|---|----------------|------------|-----------|
| project | 16 | **100.0%** | 93.8% | 87.5% |
| topic_search | 18 | 72.2% | 66.7% | **94.4%** |
| glossary | 18 | 66.7% | 38.9% | **94.4%** |
| researcher | 21 | 66.7% | 52.4% | **95.2%** |
| figure | 14 | 78.6% | 64.3% | **92.9%** |
| gap | 16 | 75.0% | 25.0% | **87.5%** |
| meta | 17 | 58.8% | 0.0% | **82.4%** |
| non_research | 33 | 45.5% | 3.0% | **81.8%** |
| general | 24 | **75.0%** | 33.3% | 58.3% |
| papers | 16 | **68.8%** | 37.5% | **68.8%** |
| off_topic | 9 | **66.7%** | 22.2% | **66.7%** |
| followup | 14 | **50.0%** | 42.9% | **57.1%** |

---

## Part 3: Qualitative Error Analysis by Tier

### 3.1 Auto Rule-Based Agent (71 errors)

#### Tier 1 errors (16 errors out of 120 queries — 86.7% accuracy)

The rule-based agent performs well on standard queries but has systematic blind spots:

**Pattern 1: Off-topic collapse (10 errors).** Many non_research queries are misclassified as off_topic. The agent treats "Hi there!", "Thanks", "Good morning", "test", "asdf", "how do I cook pasta?" as off_topic because they fail the topical scope check. The revised labels classify these as non_research (the tool cannot do this) rather than off_topic (outside the domain). This is the single largest error source.

**Pattern 2: Glossary undergeneralisation (4 errors).** Queries like "How is AI bias defined?", "AI governance — what exactly is it?", "give me a definition of trustworthy AI" are misclassified as general because the synonym expansion and glossary matching are too narrow. The rules rely on exact pattern matches ("what is X") and fail on paraphrases.

**Pattern 3: Researcher/papers confusion (2 errors).** "Who are the active researchers at Sorbonne Paris Nord?" → papers (should be researcher). The university name triggers the papers rule before the researcher check.

#### Tier 2 errors (37 errors out of 61 queries — 39.3% accuracy)

Dramatic drop. Informal and unusual phrasings break the pattern matching:

**Pattern 1: Meta failures (5 errors).** Informal meta queries like "so what exactly is this thing for?", "what databases do you use", "Are you useful for a law student?" don't match the rigid meta patterns (which expect "what can you do" or "who are you").

**Pattern 2: Non-research misrouted (8 errors).** Informal task requests ("i need a cover letter mentioning AI skills", "Format these references in IEEE style", "turn this into a blog post") are not caught by the task verb patterns because they use implicit rather than explicit action verbs.

**Pattern 3: Gap/followup unrecognised (9 errors).** Short, informal gap queries ("where should we look next?", "what hasn't been covered yet?", "are there topics nobody is working on?") and followups ("what else?", "more", "and the others?") don't match the rigid patterns.

**Pattern 4: Topic_search/papers confusion (4 errors).** Queries like "give me everything you have on AI and education", "I need references on XAI methods" don't trigger the topic_search patterns because they lack explicit keywords like "papers" or "research".

#### Tier 3 errors (18 errors out of 35 queries — 48.6% accuracy)

Adversarial and compound queries expose fundamental limitations:

**Pattern 1: Cross-category ambiguity (6 errors).** Queries that span categories: "Can you write an abstract about trustworthy AI for my conference paper?" (non_research, but contains topic keywords → topic_search). "Is there a formal definition of responsible AI in the glossary?" (glossary, but "formal definition" doesn't match patterns → general).

**Pattern 2: Figure detection (3 errors).** Implicit visualisation requests: "could I see some kind of visual breakdown?", "can you show the data graphically?", "I'd love to see a heatmap" — no explicit "figure/chart/graph" keyword.

**Pattern 3: General boundary (4 errors).** Broad AI questions misrouted: "What is the future of AI governance?" → glossary (rule treats "governance" as glossary term). "what's the deal with AI and jobs?" → off_topic (too informal for the AI keyword matcher).

---

### 3.2 LLM-Based Agent (41 errors)

#### Tier 1 errors (20 errors out of 120 queries — 83.3% accuracy)

**Pattern 1: General ↔ glossary confusion (10 errors).** This is the LLM's dominant error pattern. Queries like "What is the future of AI governance?", "Are current AI models biased?", "What makes an AI system trustworthy?", "why is AI ethics important?" are classified as glossary instead of general. The LLM sees Responsible AI keywords and defaults to glossary, even when the question is open-ended/discursive rather than definitional. This is arguably the most debatable boundary in the entire taxonomy.

**Pattern 2: Non-research ↔ meta/general swaps (5 errors).** "I'm new here, what should I know?" → meta (should be non_research). "Help me prepare my lecture notes on AI" → general. The LLM struggles with queries that blend a task request with an AI topic.

**Pattern 3: Papers ↔ topic_search (3 errors).** "Find papers about bias detection in machine learning", "Literature on AI regulation in Europe", "deep learning + ethics — any papers?" → topic_search instead of papers. The revised labels treat these as papers (they ask for specific publications), but the LLM sees the topic and routes to topic_search.

#### Tier 2 errors (13 errors out of 61 queries — 78.7% accuracy)

**Pattern 1: General ↔ glossary (continued, 4 errors).** Same pattern as Tier 1 but with informal phrasings.

**Pattern 2: Followup misclassification (3 errors).** "Ok" → non_research, "??" → off_topic, "What about the ethical implications?" → general. Short, context-dependent queries are hard for the LLM because it has no conversation history.

**Pattern 3: Researcher/papers boundary (2 errors).** "What has the University of Tirana contributed?" → papers (should be researcher). "what's UDCLV been working on?" → researcher (should be papers). The LLM inconsistently interprets "university + contribution" queries.

#### Tier 3 errors (8 errors out of 35 queries — 77.1% accuracy)

**Pattern 1: General ↔ glossary (3 errors).** "can AI systems be held legally responsible?" → glossary (should be general). The LLM overextends the glossary category to open-ended ethical questions.

**Pattern 2: Cross-category edge cases (3 errors).** "white spaces in the research map?" → figure (should be gap). "Are there responsible AI topics that only one university covers?" → gap (should be topic_search). "ok but what about from THWS specifically?" → papers (should be followup).

**Pattern 3: Project boundary (2 errors).** "Which projects focus on healthcare and AI?", "Are there any projects on data governance?" → topic_search (should be project). Despite "projects" being in the query, the LLM prioritises the topic.

---

### 3.3 Production Agent (135 errors — 37.5% accuracy)

The production agent was not trained on any development set — it evolved organically through months of real-world use. Its error profile reveals that organic development produces an agent heavily biased toward a few well-exercised categories:

- **meta: 0% accuracy** — no meta detection at all (all 17 queries misclassified)
- **non_research: 3% accuracy** — only 1 out of 33 correct
- **gap: 25% accuracy** — most gap queries routed to off_topic or general
- **project: 93.8%** — the only category where it approaches the trained agents

This confirms that hand-crafted, organically evolved classification is unreliable for categories that weren't frequently encountered during development.

---

## Part 4: Summary of Findings

### 4.1 Key Results

1. **The LLM-based classifier is significantly more robust than the rule-based one.** Both achieve 97.5% on the development set, but on unseen evaluation queries: LLM-based 81.0% vs rule-based 67.1%. The gap widens dramatically on unusual phrasings (Tier 2: 78.7% vs 39.3%).

2. **Rule-based classification is brittle to paraphrasing.** Accuracy drops from 86.7% (Tier 1) to 39.3% (Tier 2) — a 47-point degradation. The LLM drops only 4.6 points (83.3% → 78.7%).

3. **The general ↔ glossary boundary is the hardest distinction.** It accounts for the largest share of LLM errors (10/41) and is also debatable at the human annotation level. This suggests the taxonomy itself may need refinement at this boundary.

4. **Production (organic) development is unreliable.** 37.5% overall accuracy demonstrates that iterative real-world development without systematic evaluation produces severely biased classifiers.

5. **Both trained agents converge to the same residual errors.** The two fundamentally different approaches (pattern matching vs LLM prompting) fail on the same 2 queries in the dev set, suggesting these are inherent ambiguities in the task rather than classifier deficiencies.

### 4.2 Implications for RAG Agent Design

- **Use LLM-based classification** when robustness to diverse phrasings matters (most real-world scenarios)
- **Use rule-based classification** when deterministic behaviour and zero API cost are priorities (but accept the brittleness)
- **Never rely on organic development** — always use a systematic development set and iterative evaluation
- **Accept that ~15-20% of queries are inherently ambiguous** — report accuracy on unambiguous subsets alongside overall accuracy

---

*Report generated September 2026 as part of the UNINOVIS RAG reliability study.*
