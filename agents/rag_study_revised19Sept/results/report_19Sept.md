# RAG Study — Full Reliability Report
**9-class taxonomy · Revised 19 September 2026**

---

## 1. Study Overview

This study extends the 8-class reliability benchmark (10 Sept 2026) by introducing a finer-grained taxonomy and wider evaluation coverage. The main changes are:

- **9-class taxonomy**: `out_of_scope` from the 8-class study is split into `general` (research/STEM questions outside the Responsible AI domain) and `out_of_scope` (non-research queries: tasks, greetings, trivia, opinions).
- **Variant queries**: typo and grammar error variants are added to each standard query, nearly doubling the evaluation set and enabling robustness measurement across surface-level distortions.
- **Extended metrics**: consistency stratified by variant type and class; robustness (R_prompt) per variant type; 3-group predictability confusion matrix (in_scope / general / out_of_scope); two-level safety assessment.

Three agents are evaluated:

| Agent | Classification mechanism | Taxonomy |
|---|---|---|
| **Auto rule-based** | Deterministic regex/keyword rules, built iteratively on dev set | 9-class (native) |
| **Production** | Hand-crafted MetadataRAGMixin chain (months of production use), remapped | 12-class → 9-class |
| **LLM-based** | Separate LLM classification call | 9-class (native) |

---

## 2. Datasets

### 2.1 Development set (construction)
- **69 queries** (follow-ups excluded), 9 classes
- Distribution: out_of_scope 10, topic 10, general 8, papers 8, researcher 8, glossary 8, project 7, meta 6, organization 4

### 2.2 Evaluation set (benchmark)
- **392 queries** (18 follow-ups excluded from 410 total)
- Standard: 238 · Typo: 77 · Grammar: 77
- Standard tiers: T1 (typical) · T2 (informal/indirect) · T3 (adversarial/ambiguous)

### 2.3 Taxonomy: 9 classes
| Class | Group | Definition |
|---|---|---|
| papers | in_scope | Publications at a specific university or visualisation of publication data |
| researcher | in_scope | Queries about specific persons or lists of researchers |
| project | in_scope | Named research projects or project listings |
| topic | in_scope | RA topic surveys and gap analysis |
| glossary | in_scope | Definitions of RA terms |
| organization | in_scope | Factual queries about UNINOVIS or member institutions |
| meta | in_scope | Queries about the agent itself |
| **general** | general | Research/STEM questions **outside** the RA domain |
| **out_of_scope** | out_of_scope | Non-research queries: tasks, greetings, trivia, opinions |

---

## 3. Agent Construction (Auto Rule-based)

### Iteration 1 (baseline, Iteration 0)
**76.8% accuracy (53/69)** — 16 failures

| Error pattern | Count | Root cause |
|---|---|---|
| researcher → out_of_scope | 3 | Names not in DB; no fallback patterns |
| glossary → out_of_scope | 3 | "what does" / "different from" not matched |
| general → topic | 2 | Regex trailing `\b` breaks on plurals/suffixes |
| topic → out_of_scope | 2 | "studies" / "what has been done" not caught |
| meta → out_of_scope | 1 | "scope of your knowledge" not matched |
| general → out_of_scope | 1 | "operating systems" not matched due to `\b` bug |
| out_of_scope → general | 1 | "what is quantum?" in general section, not OOS |
| researcher → papers | 1 | `_is_paper_query` guard too broad |
| project → general | 1 | Project check ran after general domain check |
| topic → glossary | 1 | "what is underexplored" caught by glossary rule |

### Fixes applied (→ Iteration 2)
1. **`_GENERAL_DOMAINS` regex**: Removed trailing `\b` from outer group; added `s?` for plurals; changed `compiler optimis` → `compiler optimi\w+`
2. **Priority reordering**: Project check moved to step 4 (before general domain detection at step 5)
3. **`"what is [non-RA term]?"` → out_of_scope** in section 3 (was in section 4 as general)
4. **Meta**: Added "scope of your knowledge / data" pattern
5. **Researcher heuristics**: Added `publications? by`, `what has X published`, `working on` + proper noun
6. **Researcher guard**: `researchers?` keyword check moved before `_is_paper_query` guard; narrowed guard condition
7. **Glossary**: Added `what does / what do` triggers; `different from` + RA terms; gap-query guard (`_gap_query`)
8. **Topic**: Added "studies" to research-term list; added `what has/have been done` pattern

### Iteration 2 result
**100.0% accuracy (69/69)** — all 9 classes perfect

---

## 4. Full Reliability Benchmark Results

**Evaluation set**: 392 queries · **K** (C_traj) = 3 · **Runtime**: 1365s

### 4.1 Consistency (C_traj)

| | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| **Overall** | **100.0%** | **100.0%** | 92.9% |
| Standard | 100.0% | 100.0% | 93.7% |
| Typo | 100.0% | 100.0% | 89.6% |
| Grammar | 100.0% | 100.0% | 93.5% |

**Per-class consistency (LLM-based only — deterministic agents always 100%):**

| Class | C_traj |
|---|---|
| project | 76.3% ← lowest |
| meta | 86.7% |
| topic | 91.9% |
| out_of_scope | 93.8% |
| papers | 93.9% |
| general | 97.2% |
| glossary | 97.7% |
| organization | 100.0% |
| researcher | 100.0% |

LLM-based consistency drops more with typos (89.6%) than with grammar errors (93.5%), and is worst for the `project` class (76.3%).

### 4.2 Robustness (R_prompt by variant type)

| | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| **Accuracy — standard** | 48.7% | 18.5% | **82.3%** |
| **Accuracy — typo** | 13.0% | 11.7% | **77.9%** |
| **Accuracy — grammar** | 57.1% | 16.9% | **87.0%** |
| Degradation std → typo | **35.8%** | 6.8% | 4.4% |
| Degradation std → grammar | −8.4% | 1.6% | −4.7% |

**By tier (standard queries only):**

| | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| Tier 1 | 52.6% | 21.6% | 83.6% |
| Tier 2 | 52.9% | 13.2% | 79.4% |
| Tier 3 | 35.2% | 18.5% | 83.3% |
| T1→T3 degradation | **17.4%** | 3.0% | 0.3% |

**Notable observations:**
- Auto rule-based is highly sensitive to typos (−35.8 pp): regex patterns cannot match misspelled words.
- Grammar variants *improve* auto rule-based accuracy (+8.4 pp): reordered sentence structure sometimes creates regex-matchable patterns.
- LLM-based is remarkably robust: only −4.4 pp for typos, essentially no degradation across tiers (0.3 pp T1→T3).
- Production is uniformly low across all variant types (~11–19%), reflecting the `off_topic→general` remapping mismatch.

### 4.3 Predictability — 3-group confusion matrix

**Row = expected group · Column = predicted group · Values = recall (%)**

#### Auto rule-based

| | → in_scope | → general | → out_of_scope |
|---|---|---|---|
| in_scope | **33%** (96) | 1% (3) | **66%** (193) |
| general | 6% (2) | **64%** (23) | 31% (11) |
| out_of_scope | 6% (4) | 0% (0) | **94%** (60) |

#### Production

| | → in_scope | → general | → out_of_scope |
|---|---|---|---|
| in_scope | **57%** (165) | **40%** (117) | 3% (10) |
| general | **67%** (24) | 28% (10) | 6% (2) |
| out_of_scope | **52%** (33) | **47%** (30) | 2% (1) |

#### LLM-based

| | → in_scope | → general | → out_of_scope |
|---|---|---|---|
| in_scope | **95%** (278) | 1% (4) | 3% (10) |
| general | 14% (5) | **50%** (18) | **36%** (13) |
| out_of_scope | 12% (8) | 0% (0) | **88%** (56) |

**Programmatic path metrics:**

| | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| Programmatic fraction | 88.3% | 41.1% | 65.3% |
| Programmatic accuracy | 38.7% | 6.8% | **84.8%** |
| LLM path accuracy | 78.3% | 23.8% | 75.7% |

### 4.4 Safety

| | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| **Level 1**: in_scope accuracy | 29.8% | 18.8% | **84.9%** |
| **Level 1**: within-in_scope errors (N) | 202 | 120 | 42 |
| **Level 2**: in_scope → general (N) | 3 | **117** | 2 |
| **Level 2**: general → in_scope (N) | 2 | **24** | 5 |
| **OOS refusal rate** | **93.8%** | 1.6% | 87.5% |

---

## 5. Analysis by Agent

### 5.1 Auto rule-based
**Strengths**: Perfect consistency (deterministic); OOS refusal rate 93.8%; very few Level 2 safety errors (5 total).

**Weaknesses**: Large dev→eval accuracy gap (100% → 48.7% standard). The root cause is that 66% of in_scope queries fall through to the `out_of_scope` fallback — the rules cover the dev set's specific phrasings but do not generalize to the eval set's varied language. Very high typo sensitivity (−35.8 pp). This demonstrates the classic **overfitting problem in iterative rule construction**: rules converge to the specific patterns seen during development, not to the underlying intent.

**Level 2 safety errors (5)**: Two `general→in_scope` boundary crossings involve queries that genuinely straddle the RA/non-RA boundary ("federated learning for speech", "NLP and ethics", "researchers who publish on both AI and Medicine"). Three `in_scope→general` errors involve topic queries that mention ML/NLP keywords triggering the general domain detector.

### 5.2 Production
**Strengths**: Deterministic, fast, 100% consistent.

**Weaknesses**: Catastrophic accuracy (18.5% standard) due to the `off_topic→general` remapping. The production chain was designed for the original 12-class taxonomy where `off_topic` covered queries outside the RA domain (which correctly get refused). In the 9-class remapping, `off_topic→general` was intended to capture research-but-not-RA queries, but the production chain's `_is_in_topical_scope()` check is too aggressive — it fires on many legitimate in_scope queries (meta, papers, researcher, project, glossary), routing them to `general` instead of their correct class. This generates **141 Level 2 errors** and makes OOS refusal nearly impossible (1.6%).

**Implication**: A classifier designed for taxonomy A cannot be reliably remapped to taxonomy B without redesigning the internal decision chain. The production agent's failure here is a controlled demonstration of this principle.

### 5.3 LLM-based
**Strengths**: Highest accuracy (82.3% standard), best safety profile (Level 1: 84.9% in_scope accuracy, Level 2: only 7 errors), best typo robustness (−4.4 pp), near-zero tier degradation (0.3 pp T1→T3).

**Weaknesses**: Inconsistency in `project` class (76.3% C_traj), partial inconsistency in `meta` (86.7%). The `general` class has only 50% accuracy — the LLM tends to classify non-RA research questions as `out_of_scope` (36%) rather than `general`. This is a prompt-calibration issue: the LLM's prior knowledge leads it to refuse or reroute questions about topics clearly outside its RA domain, rather than acknowledging them as research questions.

**Consistency issues concentrate on**:
- Ambiguous project queries ("any funded projects related to elderly care?")
- Near-scope meta queries with visual/figure requests
- Adversarial topic queries ("where should we look next?", "white spaces in the research map?")

---

## 6. Cross-cutting Findings

### 6.1 The `general` class is hard for all agents
The `general` class — research/STEM questions outside the RA domain — is the most difficult to classify correctly across all variants:
- Auto rule-based: 64% (standard), drops with grammar/typo variants
- LLM-based: 50% (standard, all variants combined), LLM prefers `out_of_scope`
- Production: 28% (standard), mostly routed to `topic` or `in_scope`

The ambiguity is inherent: `general` queries look syntactically similar to `topic` queries (both use research vocabulary) but differ only in domain (RA vs. non-RA). Reliable `general` detection requires semantic domain knowledge.

### 6.2 Typo robustness reveals architectural differences
| | Typo degradation |
|---|---|
| Auto rule-based | −35.8 pp |
| Production | −6.8 pp |
| LLM-based | −4.4 pp |

Rule-based classifiers rely on surface-level pattern matching and degrade sharply with character-level noise. LLM-based classifiers handle typos naturally because they operate on semantic representations. This gap is a key argument for LLM-based or hybrid classification in production systems where user input quality is variable.

### 6.3 Grammar errors can help rule-based classifiers
Auto rule-based **improves** with grammar errors (+8.4 pp vs. standard). Grammatically distorted queries sometimes reorder words in ways that happen to match regex triggers more cleanly (e.g., SOV order brings topic words to sentence start). This is an artefact of regex pattern structure, not a general benefit.

### 6.4 Tier degradation vs. variant degradation
For LLM-based, tier degradation (T1→T3: 0.3 pp) is negligible while variant degradation exists but is small (−4.4 pp for typos). This suggests the LLM classifies by intent rather than surface form, making it robust to phrasing complexity.

For auto rule-based, tier degradation (17.4 pp) is meaningful: adversarial tier-3 queries use indirect language that triggers fewer rules.

### 6.5 Safety profile summary
| Safety dimension | Best agent | Key number |
|---|---|---|
| OOS refusal accuracy | Auto rule-based | 93.8% |
| Level 1 in_scope accuracy | LLM-based | 84.9% |
| Level 2 boundary errors (fewest) | Auto rule-based | 5 |
| Level 2 boundary errors (most) | Production | 141 |

Production's 141 Level 2 errors (predominantly in_scope→general) represent the highest safety risk: in_scope queries are incorrectly refused as outside-domain. Auto rule-based's Level 1 problem (202 within-in_scope errors) is less severe — the agent still refuses the query, but with the wrong rationale (OOS fallback instead of correct in_scope class).

---

## 7. Construction Trajectory

| Iteration | Accuracy (dev set) | Failures |
|---|---|---|
| 0 (initial) | 76.8% (53/69) | 16 |
| 1 (all fixes) | **100.0% (69/69)** | 0 |

Trajectory files: `construction/auto_rule_based_trajectory/`

---

## 8. Summary of Main Findings

1. **LLM-based classification is the most reliable overall** (82.3% eval accuracy, 7 Level 2 errors, 4.4% typo degradation) for the 9-class taxonomy. The prompt-based approach generalizes well beyond the development set.

2. **Rule-based classifiers show a systematic dev→eval gap** (100% dev → 48.7% eval): iterative construction on a finite dev set produces rules overfit to specific phrasings. The fallback to `out_of_scope` hides this — 66% of in_scope queries fall through.

3. **Remapping an existing classifier to a new taxonomy is unreliable** (Production: 18.5% accuracy). The internal decision chain must be redesigned, not just post-hoc remapped.

4. **The `general` class is the boundary most prone to confusion**, for all agents. Its discriminating feature (RA domain vs. non-RA domain) is semantic, not syntactic, making it hard for regex and partially hard for the LLM.

5. **Typos expose rule-based architecture weaknesses** (−35.8 pp for auto rule-based vs. −4.4 pp for LLM-based). In real deployment, where user typing quality is variable, this gap is practically significant.

6. **Consistency and safety trade off differently across agents**: deterministic agents are perfectly consistent but have poor safety (Level 1); LLM-based is imperfectly consistent but much safer at the boundary that matters most (Level 2).

---

*Results file*: `results/full_reliability_20260919_180646.json`
*Construction trajectories*: `construction/auto_rule_based_trajectory/`
*Benchmark script*: `benchmark/full_reliability_benchmark.py`
