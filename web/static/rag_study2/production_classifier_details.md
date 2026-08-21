# Production Rule-Based Classifier — Technical Details

## Source Code
- Agent: `agents/rag_study2/agents/production/agent.py`
- Classification logic: `agents/base/rag_metadata_mixin.py` (methods `_normalise_query`, `_is_meta_question`, `_is_non_research_task`, etc.)

## Overview

The production classifier was developed through iterative real-world use. Patterns were added reactively: each time a user query failed, a specific fix was added. This represents what production engineering naturally produces — a classifier shaped by the reactive feedback loop of fixing individual failures as they occur.

The classifier delegates to methods in `MetadataRAGMixin`, the base class for all UNINOVIS research explorer agents.

---

## Synonym Expansion (~60 mappings)

Applied before pattern matching via `_normalise_query()`. Sorted by length descending (longest match first).

### Figure/Map synonyms
| Synonym | Canonical |
|---------|-----------|
| visualise, visualize, graph, chart, diagram, plot | figure |
| display a | show a |

### Paper/Publication synonyms
| Synonym | Canonical |
|---------|-----------|
| publications → papers | publication → paper |
| articles → papers | article → paper |
| studies → papers | study on → paper on |
| works on → papers on | |

### Researcher synonyms
| Synonym | Canonical |
|---------|-----------|
| professor, prof., dr. | (removed — stripped from query) |
| scholar(s), academic(s), scientist(s), author(s) | researcher(s) |

### Action synonyms
| Synonym | Canonical |
|---------|-----------|
| enumerate, give me, provide | list |
| tell me about, describe, define | what is |
| explain to me | explain |
| bibliography of | papers by |
| bibliography from | papers from |

### Meta-question synonyms
| Synonym | Canonical |
|---------|-----------|
| tell me about your capabilities | what can you do |
| what functionality do you offer | what can you do |
| your abilities | what can you do |
| what are you able to | what can you do |
| how can you assist | how can you help |
| how do you operate | how does this work |
| what agent is this | who are you |

### Non-research synonyms
| Synonym | Canonical |
|---------|-----------|
| draft a paper, draft an essay | write an essay |
| compose | write |
| i need this translated | translate this |

### Gap analysis synonyms
| Synonym | Canonical |
|---------|-----------|
| research gaps, knowledge gaps | gaps |
| underexplored, under-explored | least studied |
| unexplored, overlooked | not studied |
| little coverage | gaps |

### Other synonyms
| Synonym | Canonical |
|---------|-----------|
| harmful | dangerous |
| differ | difference |
| i want to understand | what is |
| nation(s) | country/countries |

---

## Classification Chain (12 steps, priority-ordered)

### 1. Meta questions (`_is_meta_question`)
**Mechanism**: Exact substring matching against a list of 16 phrases.

Phrases: `what can you do`, `how does this work`, `how do you work`, `what kind of questions`, `what do the`, `what are the banners`, `what is uninovis`, `which universities`, `who are you`, `what are you`, `how can you help`, `what do you know`, `what is your`, `tell me about yourself`, `i'd like to know what you can do`, `partner universities`

### 2. Non-research tasks (`_is_non_research_task`)
**Mechanism**: Regex pattern matching against 13 patterns.

Patterns include:
- `^write (me )?(an? )?(essay|report|letter|poem|story|code|summary)`
- `translate (this|the|my|following)`
- `book (me|a|my) (a )?(flight|hotel|ticket|room)`
- `who won (the|last)`
- `what is the (weather|temperature|time|capital|population)`
- `recipe`
- `how (do|can) (i|you) (cook|make|bake|prepare)`

### 3. Figure/map requests (`_is_figure_request`)
**Mechanism**: Simple keyword check after synonym expansion.

Checks if `figure` or `map` appears in the lowercased message. Synonym expansion has already mapped `visualise`, `graph`, `chart`, `diagram`, `plot` → `figure`.

### 4. Follow-up queries (`_is_followup_query`)
**Mechanism**: Short-message regex patterns.

Only triggers on messages < 60 characters. Patterns: `expand`, `elaborate`, `more`, `details`, `explain`, `continue`, `go on`, `yes`, `no`, `ok`.

### 5. Project queries (`_build_project_context`)
**Mechanism**: Searches project markdown files for matching content.

Matches project names and keywords against the `data/project_docs/` collection.

### 6. Researcher queries (`_query_mentions_researcher`)
**Mechanism**: Name matching against the researcher database with accent stripping.

- Full name match (with and without accents)
- Surname match (if surname > 3 chars)
- First+last name combination match
- First name only (if ≥ 5 chars)
- Also detects `papers by [Name]` pattern via regex

### 7. Conceptual/glossary queries (`_is_conceptual_question`)
**Mechanism**: 15 regex patterns for conceptual question structures.

Patterns include:
- `^what (is|are)` — "What is X?"
- `defin(e|ition of)` — "Define X"
- `difference between` — "Difference between X and Y"
- `how does X relate to Y`
- `is AI (dangerous|safe|trustworthy|reliable|ethical|biased)`
- `can AI (be trusted|be dangerous|make decisions|think|feel)`

If conceptual, checks glossary for matching entry. If found → `glossary`; if not → `general`.

### 8. Gap analysis (`_is_gap_analysis_query`)
**Mechanism**: Substring matching against 16 gap-related phrases.

Phrases: `not been studied`, `not studied`, `have not been`, `missing`, `gaps`, `unstudied`, `not covered`, `not researched`, `not explored`, `not addressed`, `not investigated`, `least studied`, `underrepresented`, `least explored`, `least researched`, `least covered`

### 9. University paper listing (`_build_university_papers_context`)
**Mechanism**: Detects university names/acronyms and retrieves paper data.

### 10. Topic search (`_build_topic_context`)
**Mechanism**: Retrieves relevant document chunks based on query content.

### 11. Off-topic check (`_is_in_topical_scope`)
**Mechanism**: Checks if any word in the query matches the topical scope set (~711 terms built from glossary, paper concepts, researcher topics, and config).

If no term matches → `off_topic`.

### 12. General (fallback)
If nothing else matched but the query is in scope → `general`.

---

## Key Differences from Auto-Constructed Rule-Based

| Aspect | Production | Auto-constructed |
|--------|-----------|-----------------|
| **Pattern design** | Query-specific (one fix per failure) | Word-class (cover categories of queries) |
| **Synonym mappings** | ~60 (accumulated over time) | ~35 (designed systematically) |
| **Intent templates** | None — uses exact phrase lists and specific regex | Yes — `task_verb + any_object → non_research` |
| **Entity-type detection** | Database lookup only | Database lookup + capitalised name patterns |
| **Broad category signals** | Limited — relies on exact patterns | Extensive — keyword signals for each category |
| **Construction process** | Reactive (fix one failure → add one pattern) | Batch (see multiple failures → design class-level patterns) |
| **Dev set accuracy** | Not measured during development | 100% (69/69) |
| **Eval set accuracy** | 44.0% | 75.5% |

## Why Production Generalises Worst

The production classifier's low accuracy on unseen queries (44.0%) despite having more synonym mappings (~60 vs ~35) illustrates a key finding: **the number of patterns matters less than their generality**.

Production patterns are query-specific — each was added to fix a single observed failure. For example, after a user asked "What functionality do you offer?" and it was misclassified, the synonym `"what functionality do you offer" → "what can you do"` was added. This fixes that exact phrasing but does not cover "What services do you provide?" or "What features are available?".

The auto-constructed classifier, built through batch feedback (seeing multiple failures at once), generates broader patterns. Instead of mapping individual phrases, it maps word classes: any combination of `(capabilities|functionality|features|purpose|your help)` → `what can you do`.

This difference mirrors the overfitting problem in machine learning: memorising training examples (production) vs. learning generalisable features (auto-constructed).
