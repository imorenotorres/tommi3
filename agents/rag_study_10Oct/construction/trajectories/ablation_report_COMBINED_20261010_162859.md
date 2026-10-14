# Ablation Study Report — 10Oct
Generated: 2026-10-10 16:28  |  LLM: mistral-small-latest

## 1. Study Design

### Research Questions
- **RQ1a** — Tier vulnerability: does query phrasing complexity (T2 unusual, T3 adversarial) hurt classification?
- **RQ1b** — L2 vulnerability: do Spanish L1 typos and grammar errors hurt classification?
- **RQ2** — Training remedy: does exposing the construction process to variant queries improve L2 robustness?

### Conditions
| Condition | Variants | Dev set | Agents |
|-----------|----------|---------|--------|
| **std-only** | llm_A_std / B_std / C_std | 50 standard queries | 3 independent runs |
| **full** | llm_A / B / C | 150 queries (50 std + 50 typo + 50 grammar) | 3 independent runs |

### Evaluation Sets
| Set | n | Description |
|-----|---|-------------|
| Tier 1 | 116 | Standard typical phrasings — **baseline** |
| Tier 2 | 68 | Unusual phrasings (informal, verbose, telegraphic, indirect) |
| Tier 3 | 54 | Adversarial (ambiguous, compound, edge cases, near-misses) |
| Standard total | 238 | T1 + T2 + T3 combined |
| Typo L1-ES | 77 | Tier 1 queries with Spanish L1 orthographic errors |
| Grammar L1-ES | 77 | Tier 1 queries with Spanish L1 grammatical interference |

Typo and Grammar sets are paired variants of Tier 1 queries.
No consistency test in this phase.

## 2. Construction Summary

| Agent | Condition | Dev set best acc | Notes |
|-------|-----------|-----------------|-------|
| llm_A_std | std-only | — | (50 standard queries) |
| llm_B_std | std-only | — | (50 standard queries) |
| llm_C_std | std-only | — | (50 standard queries) |
| llm_A | full | 92.0% | (150 queries, all variants) |
| llm_B | full | 92.0% | (150 queries, all variants) |
| llm_C | full | 94.7% | (150 queries, all variants) |

std-only agents converged in 1–2 iterations (98–100% dev accuracy on 50 standard queries).  
Full agents plateaued at 91–95% on 150 mixed queries (harder optimisation target).

## 3. Evaluation Results

### 3.1 Overall Accuracy by Set

| Set | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C | **std avg** | **full avg** |
|-----|---------|---------|---------|---------|---------|---------|----------|----------|
| Tier 1 — standard typical   (116) | 96/116 (82.8%) | 96/116 (82.8%) | 92/116 (79.3%) | 98/116 (84.5%) | 97/116 (83.6%) | 95/116 (81.9%) | **81.6%** | **83.3%** |
| Tier 2 — unusual phrasing    (68) | 54/68 (79.4%) | 53/68 (77.9%) | 53/68 (77.9%) | 54/68 (79.4%) | 54/68 (79.4%) | 52/68 (76.5%) | **78.4%** | **78.4%** |
| Tier 3 — adversarial          (54) | 45/54 (83.3%) | 45/54 (83.3%) | 40/54 (74.1%) | 44/54 (81.5%) | 46/54 (85.2%) | 47/54 (87.0%) | **80.2%** | **84.6%** |
| Standard total              (238) | 195/238 (81.9%) | 194/238 (81.5%) | 185/238 (77.7%) | 196/238 (82.4%) | 197/238 (82.8%) | 194/238 (81.5%) | **80.4%** | **82.2%** |
| Typo L1-ES                   (77) | 57/77 (74.0%) | 59/77 (76.6%) | 56/77 (72.7%) | 53/77 (68.8%) | 60/77 (77.9%) | 54/77 (70.1%) | **74.5%** | **72.3%** |
| Grammar L1-ES                (77) | 61/77 (79.2%) | 66/77 (85.7%) | 60/77 (77.9%) | 62/77 (80.5%) | 67/77 (87.0%) | 62/77 (80.5%) | **81.0%** | **82.7%** |

### 3.2 RQ1a — Tier Vulnerability

Tier 1 is the baseline. Deltas show accuracy change relative to Tier 1.

| Condition | Tier 1 | Tier 2 | Δ T2 | Tier 3 | Δ T3 |
|-----------|--------|--------|------|--------|------|
| std-only (avg) | 81.6% | 78.4% | -3.2% | 80.2% | -1.4% |
| full (avg) | 83.3% | 78.4% | -4.9% | 84.6% | +1.2% |

### 3.3 RQ1b — L2 Noise Vulnerability

Tier 1 is the baseline. Deltas show accuracy change relative to Tier 1.

| Condition | Tier 1 | Typo | Δ Typo | Grammar | Δ Grammar |
|-----------|--------|------|--------|---------|-----------|
| std-only (avg) | 81.6% | 74.5% | -7.2% | 81.0% | -0.7% |
| full (avg) | 83.3% | 72.3% | -11.0% | 82.7% | -0.6% |

### 3.4 RQ2 — Effect of Variant Training

| Set | std-only avg | full avg | Δ (full − std) | Interpretation |
|-----|-------------|----------|----------------|----------------|
| Typo L1-ES | 74.5% | 72.3% | -2.2% | ✗ No benefit |
| Grammar L1-ES | 81.0% | 82.7% | +1.7% | ✓ Moderate benefit |

### 3.5 Per-category Breakdown

#### Tier 1 (baseline)

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C | std avg | full avg |
|----------|---------|---------|---------|---------|---------|---------|---------|---------|
| meta | 7/7 (100%) | 7/7 (100%) | 6/7 (86%) | 7/7 (100%) | 7/7 (100%) | 7/7 (100%) | 95% | 100% |
| organization | 2/2 (100%) | 2/2 (100%) | 2/2 (100%) | 2/2 (100%) | 2/2 (100%) | 2/2 (100%) | 100% | 100% |
| out_of_scope | 16/24 (67%) | 16/24 (67%) | 15/24 (62%) | 17/24 (71%) | 17/24 (71%) | 17/24 (71%) | 65% | 71% |
| general | 4/6 (67%) | 5/6 (83%) | 3/6 (50%) | 2/6 (33%) | 3/6 (50%) | 3/6 (50%) | 67% | 44% |
| papers | 11/16 (69%) | 11/16 (69%) | 12/16 (75%) | 14/16 (88%) | 12/16 (75%) | 13/16 (81%) | 71% | 81% |
| researcher | 12/13 (92%) | 12/13 (92%) | 12/13 (92%) | 12/13 (92%) | 12/13 (92%) | 12/13 (92%) | 92% | 92% |
| project | 11/11 (100%) | 10/11 (91%) | 11/11 (100%) | 11/11 (100%) | 11/11 (100%) | 11/11 (100%) | 97% | 100% |
| topic | 24/26 (92%) | 24/26 (92%) | 23/26 (88%) | 24/26 (92%) | 25/26 (96%) | 21/26 (81%) | 91% | 90% |
| glossary | 9/11 (82%) | 9/11 (82%) | 8/11 (73%) | 9/11 (82%) | 8/11 (73%) | 9/11 (82%) | 79% | 79% |

#### Typo L1-ES

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C | std avg | full avg |
|----------|---------|---------|---------|---------|---------|---------|---------|---------|
| meta | 5/6 (83%) | 5/6 (83%) | 4/6 (67%) | 5/6 (83%) | 5/6 (83%) | 5/6 (83%) | 78% | 83% |
| organization | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 5/5 (100%) | 4/5 (80%) | 80% | 87% |
| out_of_scope | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 88% | 88% |
| general | 3/8 (38%) | 4/8 (50%) | 4/8 (50%) | 2/8 (25%) | 3/8 (38%) | 2/8 (25%) | 46% | 29% |
| papers | 6/10 (60%) | 6/10 (60%) | 5/10 (50%) | 7/10 (70%) | 6/10 (60%) | 5/10 (50%) | 57% | 60% |
| researcher | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 7/10 (70%) | 10/10 (100%) | 9/10 (90%) | 97% | 87% |
| project | 7/10 (70%) | 8/10 (80%) | 9/10 (90%) | 8/10 (80%) | 6/10 (60%) | 8/10 (80%) | 80% | 73% |
| topic | 5/10 (50%) | 5/10 (50%) | 4/10 (40%) | 4/10 (40%) | 8/10 (80%) | 4/10 (40%) | 47% | 53% |
| glossary | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 10/10 (100%) | 10/10 (100%) | 100% | 97% |

#### Grammar L1-ES

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C | std avg | full avg |
|----------|---------|---------|---------|---------|---------|---------|---------|---------|
| meta | 6/6 (100%) | 6/6 (100%) | 6/6 (100%) | 5/6 (83%) | 6/6 (100%) | 6/6 (100%) | 100% | 94% |
| organization | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 80% | 100% |
| out_of_scope | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 8/8 (100%) | 8/8 (100%) | 88% | 96% |
| general | 2/8 (25%) | 7/8 (88%) | 2/8 (25%) | 1/8 (12%) | 2/8 (25%) | 3/8 (38%) | 46% | 25% |
| papers | 6/10 (60%) | 5/10 (50%) | 5/10 (50%) | 8/10 (80%) | 9/10 (90%) | 6/10 (60%) | 53% | 77% |
| researcher | 9/10 (90%) | 9/10 (90%) | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 9/10 (90%) | 93% | 93% |
| project | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 9/10 (90%) | 10/10 (100%) | 8/10 (80%) | 97% | 90% |
| topic | 7/10 (70%) | 8/10 (80%) | 7/10 (70%) | 7/10 (70%) | 8/10 (80%) | 7/10 (70%) | 73% | 73% |
| glossary | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 100% | 100% |

## 4. Discussion

### RQ1a — Tier complexity
The effect of phrasing complexity (T2/T3) on classification accuracy is **small and inconsistent**.
Tier 2 (unusual phrasings) causes a modest −3.2% drop for std-only agents.
Tier 3 (adversarial) shows no consistent drop — in some agents accuracy even improves,
possibly because adversarial queries are more explicit about category intent.

### RQ1b — L2 noise vulnerability
**Typo errors** cause a consistent and meaningful accuracy drop (−7.2% for std-only, −11.1% for full).
**Grammar errors** show a surprisingly small effect (−0.6% for std-only), though with high variance.
The most vulnerable categories are `general` and `topic`.
Robust categories: `researcher`, `project`, `glossary`, `out_of_scope`.

### RQ2 — Training remedy
Training on typo/grammar variant queries during construction **does not improve** L2 robustness.
For typo, the full condition is marginally worse (−2.1%); for grammar, marginally better (+1.7%).
Neither difference is meaningful given the high inter-agent variance.
This suggests that LLM-based prompt optimisation via a meta-LLM is not an effective mechanism
for inducing noise robustness — the meta-LLM does not incorporate variant-specific rules
that transfer to unseen noisy queries.

### Variance and reliability
High inter-agent variance (e.g., typo: 68.8%–77.9% within the full condition) indicates
that results depend strongly on the specific prompt evolution path rather than the training condition.
Consistency testing would be needed to confirm agent reliability before drawing strong conclusions.

## 5. Next Steps

- Consistency test (K=5) on final prompts to assess stability
- Review specific failures in `general` and `topic` under noise
- Consider explicit noise-handling rules in CLASSIFY_PROMPT
- Consider whether the ablation result (no benefit from variant training) is worth reporting as a null finding