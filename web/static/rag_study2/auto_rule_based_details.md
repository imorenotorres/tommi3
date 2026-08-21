# Auto-Constructed Rule-Based Classifier — Technical Details

## Source Code
`agents/rag_study2/agents/auto_rule_based/agent.py`

## Generalisation Mechanisms (4 strategies)

The auto-constructed rule-based classifier uses four generalisation mechanisms that distinguish it from the production hand-crafted classifier:

### 1. Synonym Expansion (~35 mappings)
Applied to the query BEFORE pattern matching, so patterns only need to match canonical forms.

**Synonym families:**

| Family | Mappings |
|--------|----------|
| Action verbs | compose, draft, prepare, create, generate, produce → **write** |
| Summarise | summarise → **summarize** |
| Review | proofread → **review** |
| Organise | schedule, arrange → **organize** |
| Compute | calculate → **compute** |
| Papers | publications, articles, studies, literature, output, work → **papers** |
| Visualisation | visualize, visualise, plot, graph, chart, diagram, timeline, bar chart → **show figure** |
| Bibliography | bibliography, academic output → **papers by** |
| Define/Explain | define, explain, meaning of, meant by, refer to, concept of → **what is** |
| Meta | capabilities, functionality, features, purpose, your help → **what can you do** |
| Gaps | blind spots, underrepresented, opportunities, missing, not explored, not addressed, new research directions → **gaps / not studied** |
| Followup | go deeper, elaborate, continue, show me more, yes elaborate → **tell me more** |

Total: ~35 unique synonym mappings, sorted by length (longest match first to avoid partial replacements).

### 2. Intent Templates (structural patterns)
Broad patterns that match **word classes** rather than specific phrases:

- **Non-research**: `task_verbs + any object` → `non_research`
  - Task verbs: `write|summarize|review|send|organize|compute|book|translat*`
  - With exclusions for figure requests and paper searches
- **Meta**: `(you|your|this tool|this system) + (what can you do|help|cover|access|offer|purpose)` → `meta`
- **Project**: `(project|EU-funded|Horizon|funded|grant)` → `project`
- **Topic search**: `papers + (on|about|regarding|related|dealing)` → `topic_search`
- **Glossary**: `(what is|difference between|tell me about) + RA concept` → `glossary`
- **Gap**: `(not studied|not explored|least studied|underexplored|zero papers)` → `gap`

### 3. Entity-Type Detection
For researcher queries, uses **person name detection** as a class rather than matching specific names:

- Checks against the metadata database via `_query_mentions_researcher()`
- Also checks accent-stripped versions
- Detects capitalised name patterns: `[A-Z][a-z]+ [A-Z][a-z]+`
- Structural patterns: `papers by`, `published by`, `authored by`, `from Professor/Dr.`

### 4. Broad Category Signals
Keywords that indicate a category regardless of sentence structure:

- **Non-research**: `recipe|flight|hotel|ticket|weather|PowerPoint|presentation|email|meeting`
- **Non-research**: `who won` pattern
- **Project**: Specific project names: `tailor, intelliman, duca, aias, daibetes, innoguard, crystal, movecare, empathic, menhir`
- **University**: Acronyms `UMA|THUAS|USPN|UDCLV|THWS|TAMK` + full names `málaga|hague|sorbonne|campania|würzburg|tampere|kauno|tirana`
- **General (AI)**: `ai + (danger|harmful|trust|safe|bias|rights|replace|regulat|future|challeng|teach|ethic|model)`

---

## Classification Chain (13 categories, priority-ordered)

1. **meta** — Agent identity, capabilities, UNINOVIS membership
2. **non_research** — Task requests (action verb + object, explicit task keywords)
3. **figure** — Visualisation requests (after synonym expansion)
4. **followup** — Short context-dependent replies
5. **project** — Project names or "project(s)" keyword
6. **papers** — University-specific paper requests (no topic specified)
7. **researcher** — Person name detected (entity-type detection)
8. **glossary** — Conceptual questions about RA terms (with glossary lookup)
9. **gap** — Research gaps, missing topics
10. **topic_search** — Papers/publications on a topic
11. **general (AI)** — Broad AI/technology questions (before off_topic)
12. **off_topic** — Outside topical scope
13. **general** — Fallback

---

## Construction Trajectory

Built by automated constructor (Claude Sonnet 4) in 3 iterations:

| Iteration | Accuracy (dev set, n=69) | Fixes applied |
|-----------|--------------------------|---------------|
| 0 (initial) | 79.7% (55/69) | Initial patterns from expert examples |
| 1 | 91.3% (63/69) | +meta patterns; fix `\bprojects?\b`; university acronym case fix; expanded scope terms |
| 2 | 97.1% (67/69) | Reordered university before researcher; word-boundary fix for project names; broad AI patterns |
| 3 | 100.0% (69/69) | Stemming fix ("trusted"); topic_search pattern expansion ("at/in/within") |

---

## Comparison: Production vs. Auto-Constructed Rule-Based

| Feature | Production (hand-crafted) | Auto-constructed |
|---------|--------------------------|------------------|
| Synonym mappings | ~60 | ~35 |
| Classification steps | 13-step priority chain | 13-step priority chain |
| Pattern style | Query-specific (fix individual failures) | Word-class (cover classes of queries) |
| Construction | Months, reactive (one failure at a time) | Hours, batch feedback (multiple failures at once) |
| Dev set accuracy | 100% | 100% |
| Eval set accuracy | 44.0% | 75.5% |
| Degradation T1→T3 | 5.8 pts (low because uniformly poor) | 42.4 pts (high T1, collapses T2-T3) |

---

## LLM-Based Classifier (for comparison)

Source: `agents/rag_study2/agents/llm_based/agent.py`

Uses a single LLM call (Mistral Small) with a classification prompt defining the same 12 categories. The prompt includes:
- Category definitions with examples
- Priority ordering rules
- Important distinctions (non_research vs off_topic, glossary vs general, etc.)
- University acronyms list

Construction trajectory: 3 iterations, starting at 95.7% → 100% on dev set.

---

## Benchmark Sets

- **Development set**: `benchmark/development_set.json` — 69 queries, all categories
- **Evaluation set**: `benchmark/evaluation_set_extended.json` — 216 queries, 3 tiers:
  - Tier 1 (standard): 120 queries
  - Tier 2 (unusual): 61 queries
  - Tier 3 (adversarial): 35 queries
  - 12 categories: meta(18), non_research(20), off_topic(24), figure(14), project(16), researcher(18), glossary(19), topic_search(20), papers(16), gap(17), general(22), followup(12)
