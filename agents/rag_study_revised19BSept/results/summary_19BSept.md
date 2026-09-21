# RAG Study 19BSept — Construction & Benchmark Summary

**Date:** 2026-09-20  
**Taxonomy:** 9-class (papers, researcher, project, topic, glossary, organization, meta, general, out_of_scope)  
**Dev set:** 150 queries (50 standard + 50 l2_typo + 50 l2_grammar)  
**Eval set:** 392 queries (238 standard + 77 l2_typo + 77 l2_grammar), held out throughout construction

---

## 1. Construction Protocol

All 6 agents started from an identical minimal seed (~55% on the dev set with `--variants all`). Each run independently refined the classifier through different strategies.

### Rule-based agents

| Agent | Strategy | Iterations to 100% |
|-------|----------|-------------------|
| rule_based_A | Compiled fuzzy patterns; word-order guard for papers vs researcher; `_has_publication_keyword()` helper with typo variants | 4 |
| rule_based_B | Researcher check before organization; `_RESEARCHER_PATTERNS` whitelist; guard on `publi\w+ (of\|by) UNI_CODE` | 3 |
| rule_based_C | Typo normalization preprocessing (`_normalize()` maps l2_typo → canonical) before classification | 3 |

All three converged to **100% accuracy and 100% consistency** on the 150-query dev set.

### LLM agents

| Agent | Prompt strategy | Iterations | Dev accuracy |
|-------|----------------|-----------|-------------|
| llm_A | KEY DISTINCTIONS prose — bolded rules with ✓/✗ inline examples | 4 | 99.3% |
| llm_B | IF-THEN ordered decision procedure (10 steps); project/researcher before task filter | 6 | 98.7% |
| llm_C | Labeled few-shot examples per category with inline RULE summaries | 3 | 100% |

Convergence threshold: ≥97.5% accuracy on dev set.

**Common LLM construction failure modes discovered:**
- `researcher → topic`: LLM sees RA terms (fairness, explainability) and misses the "researchers" subject
- `general → glossary`: "What is machine learning?" treated as definitional
- `project → topic/out_of_scope`: "Tell me about [project]" / "Are there projects on X?" misrouted
- `glossary → topic`: "How is trustworthy AI different from responsible AI?" misread as survey
- `meta → organization`: "Do you have access to UNINOVIS publications?" → organization instead of meta
- `out_of_scope → glossary`: "What is your opinion on AI regulation?" → glossary

---

## 2. Benchmark Results

**Full reliability benchmark** — Rabanser et al. (2025) framework  
392 held-out queries | K=5 consistency runs | 11,992s (~3.3 hours)

### 2.1 Robustness (R_prompt)

| Agent | Acc. standard | Acc. typo | Acc. grammar | Degradation std→typo | Degradation std→grammar |
|-------|--------------|-----------|-------------|----------------------|------------------------|
| rule_based_A | 47.5% | 24.7% | 50.6% | **−22.8%** | −3.2% |
| rule_based_B | 47.5% | 23.4% | 50.6% | **−24.1%** | −3.2% |
| rule_based_C | 47.5% | 23.4% | 49.4% | **−24.1%** | −1.9% |
| llm_A | 80.7% | **89.6%** | 80.5% | **+8.9%** | +0.1% |
| llm_B | 73.5% | 80.5% | 80.5% | +7.0% | −7.0% |
| **llm_C** | **82.3%** | 87.0% | **92.2%** | +4.7% | −9.9% |

**By difficulty tier (standard queries only):**

| Agent | Tier 1 | Tier 2 | Tier 3 | Degradation T1→T3 |
|-------|--------|--------|--------|-------------------|
| rule_based_A | 53.4% | 48.5% | 33.3% | 20.1% |
| rule_based_B | 55.2% | 47.1% | 31.5% | 23.7% |
| rule_based_C | 53.4% | 48.5% | 33.3% | 20.1% |
| llm_A | 81.9% | 80.9% | 77.8% | 4.1% |
| llm_B | 77.6% | 69.1% | 70.4% | 7.2% |
| llm_C | 83.6% | **83.8%** | 77.8% | 5.8% |

### 2.2 Consistency (C_traj, K=5)

| Agent | Overall | standard | typo | grammar | papers | researcher | project |
|-------|---------|----------|------|---------|--------|------------|---------|
| rule_based_A/B/C | **100%** | 100% | 100% | 100% | 100% | 100% | 100% |
| llm_A | 93.6% | 92.9% | 94.8% | 94.8% | 85.7% | 95.1% | 94.7% |
| llm_C | 87.8% | 87.4% | 89.6% | 87.0% | 77.5% | 82.9% | 94.7% |
| llm_B | 83.2% | 84.0% | 83.1% | 80.5% | 77.5% | **63.4%** | **68.4%** |

### 2.3 Predictability (3-group confusion matrix)

Row = expected group, column = predicted group. Percentages are row-normalised; raw counts in parentheses.

**LLM A**
```
                   in_scope      general   out_of_scope   Total
in_scope          95% (277)      4%  (13)     1%   (2)     292
general           14%   (5)     75%  (27)    11%   (4)      36
out_of_scope      19%  (12)      2%   (1)    80%  (51)      64
```

**LLM B**
```
                   in_scope      general   out_of_scope   Total
in_scope          86% (251)      0%   (1)    14%  (40)     292
general           33%  (12)     56%  (20)    11%   (4)      36
out_of_scope      12%   (8)      2%   (1)    86%  (55)      64
```

**LLM C**
```
                   in_scope      general   out_of_scope   Total
in_scope          92% (270)      2%   (5)     6%  (17)     292
general            8%   (3)     75%  (27)    17%   (6)      36
out_of_scope      12%   (8)      3%   (2)    84%  (54)      64
```

**LLM A + B + C combined** (pooled, N = 1176 = 392 × 3 agents)
```
                   in_scope      general   out_of_scope   Total
in_scope          91% (798)      2%  (19)     7%  (59)     876
general           19%  (20)     69%  (74)    13%  (14)     108
out_of_scope      15%  (28)      2%   (4)    83% (160)     192
```

The combined matrix shows that across all three LLM construction strategies, 91% of in-scope queries are correctly routed, 69% of general queries are identified, and 83% of out-of-scope queries are refused. LLM B's two pathologies — high in_scope→out_of_scope leakage (14%) and high general→in_scope leakage (33%) — are visible individually but are diluted in the aggregate.

### 2.3b In-scope confusion matrix (7 × 7, all variants pooled)

Row = expected class; column = predicted class. Diagonal = correct. `→general` = leaked to general group (not shown as a class here). Dots indicate zero. Percentages are row-normalised.

**LLM A**
```
            papers  researc  project    topic  glossary   organ    meta  →general  Total
papers        67%(33)  10%(5)   2%(1)   4%(2)      ·       6%(3)    ·      6%(3)    49
researcher     5%(2)   93%(38)    ·       ·         ·       2%(1)    ·      0%       41
project          ·       ·    95%(36)     ·         ·         ·    3%(1)    0%       38
topic          1%(1)     ·    1%(1)    81%(60)      ·         ·    3%(2)   14%(10)   74
glossary         ·       ·       ·    16%(7)    84%(37)       ·      ·      0%       44
organization     ·       ·    6%(1)      ·         ·      88%(14)  6%(1)    0%       16
meta             ·       ·       ·       ·       3%(1)       ·    90%(27)   0%       30
```

**LLM B**
```
            papers  researc  project    topic  glossary   organ    meta  →general  Total
papers        76%(37)  2%(1)    ·       8%(4)      ·       2%(1)    ·      0%       49
researcher     7%(3)   76%(31)   ·        ·         ·       2%(1)    ·      0%       41
project          ·       ·    63%(24)  5%(2)        ·       8%(3)    ·      0%       38
topic            ·       ·       ·    65%(48)   26%(19)   4%(3)     ·      1%(1)    74
glossary         ·       ·       ·       ·      100%(44)     ·       ·      0%       44
organization     ·       ·       ·       ·         ·      88%(14)   ·      0%       16
meta             ·       ·       ·       ·         ·         ·    83%(25)   0%       30
```

**LLM C**
```
            papers  researc  project    topic  glossary   organ    meta  →general  Total
papers        73%(36)  6%(3)   2%(1)   8%(4)      ·         ·    4%(2)    0%       49
researcher     2%(1)   93%(38)   ·        ·         ·         ·     ·      0%       41
project          ·       ·    95%(36)  3%(1)        ·       3%(1)   ·      0%       38
topic          1%(1)     ·       ·    82%(61)       ·       1%(1)  5%(4)   7%(5)    74
glossary         ·       ·       ·    11%(5)    89%(39)      ·    5%(2)    0%       44
organization     ·       ·    6%(1)      ·         ·      100%(16) 6%(1)   0%       16
meta             ·       ·       ·       ·       3%(1)       ·    83%(25)  0%       30
```

**Key patterns across agents:**

| Class | LLM A | LLM B | LLM C | Main confusion |
|-------|-------|-------|-------|---------------|
| papers | 67% | 76% | 73% | → researcher, topic, organization |
| researcher | 93% | 76% | 93% | → papers |
| project | 95% | **63%** | 95% | → topic, organization (llm_B only) |
| topic | 81% | **65%** | 82% | → glossary (llm_B: 26%), → general |
| glossary | 84% | **100%** | 89% | → topic |
| organization | 88% | 88% | **100%** | — |
| meta | 90% | 83% | 83% | — |

`papers` is the hardest in-scope class for all agents — it overlaps semantically with researcher (person-at-university queries), topic (RA papers without explicit university), and organization (university-name queries). LLM B shows two distinct pathologies: `project` (63%) and `topic` (65%), with 26% of topic queries leaking to `glossary`.

### 2.4 Safety

| Agent | L1: in_scope acc | L2: in→general (high-risk) | L2: general→in (high-risk) | OOS refusal |
|-------|-----------------|--------------------------|--------------------------|-------------|
| rule_based_A/B/C | ~32% | 4 | 1–2 | **95.3%** |
| llm_A | **84.9%** | 13 | 5 | 79.7% |
| llm_B | 75.7% | 1 | **13** | 82.8% |
| llm_C | 82.5% | 5 | 3 | **85.9%** |

---

## 3. Key Findings

### Finding 1: Rule-based agents catastrophically overfit
Despite 100% accuracy on the 150-query dev set, all three rule-based agents achieve only **47.5% on standard eval queries** — worse than random for a 9-class problem. The root cause: 63% of genuinely in-scope queries are routed to `out_of_scope`. The hand-crafted regex patterns learned during construction do not generalise beyond the specific phrasings in the dev set.

Additionally, rule-based agents degrade dramatically on l2_typo variants (−22–24%), despite typo normalization (run_C) or fuzzy patterns (run_A). The evaluation set contains typo patterns not seen during construction.

### Finding 2: LLM agents generalise substantially better
LLM agents achieve 73–82% on standard eval queries and do **not** degrade on typos — they actually improve (LLM A: +8.9% on typos vs standard). This is consistent with the LLM's pretraining exposure to misspelled text, making it inherently robust to surface-form variation.

### Finding 3: Construction strategy affects generalisation
Among LLM agents, the strategy influenced benchmark performance:
- **llm_C (few-shot examples)**: Best standard accuracy (82.3%), best grammar accuracy (92.2%), strong safety profile
- **llm_A (KEY DISTINCTIONS prose)**: Best in-scope recall (95%), best consistency (93.6%), but more in→general leakage (13 cases)
- **llm_B (IF-THEN procedure)**: Lowest consistency (83.2%), serious researcher/project per-class instability; general→in-scope leakage (13 cases)

### Finding 4: The construction process is itself a source of variance
LLM B required 6 iterations to converge vs 3 for llm_C, and its construction path was unstable — restructuring the IF-THEN steps caused regressions (iter-4: 88.7%, iter-5: 86.0%) before recovering. The prompt format matters beyond the content.

### Finding 5: Consistency and accuracy trade-off
Rule-based agents are perfectly consistent (deterministic) but inaccurate on unseen queries. LLM agents are accurate but probabilistic — the same query may be classified differently across runs (C_traj 83–94%). LLM B's low consistency on researcher (63%) and project (68%) classes is a deployment risk.

---

## 4. Recommendations

1. **Deploy LLM-based classifiers** for this task. Rule-based construction achieves strong dev-set numbers but fails on generalisation.
2. **LLM A or LLM C** are the preferred agents: LLM A for best in-scope recall, LLM C for best typo/grammar robustness and cleaner safety profile.
3. **Avoid LLM B** for production: low consistency on researcher and project classes (63–68%) creates unpredictable user experience.
4. **For future studies**: the dev set (150 queries) is too small and too stylistically uniform to prevent rule-based overfitting. A larger, more diverse dev set or explicit anti-overfitting regularisation is needed.
5. **OOS refusal**: rule-based agents (95.3%) outperform LLM agents (80–86%) at refusing truly out-of-scope queries. A hybrid — LLM classification with a rule-based OOS pre-filter — may offer the best of both.
