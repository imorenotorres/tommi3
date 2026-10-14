# Reliability Study — Comprehensive Final Report (10Oct)
Generated: 2026-10-11 13:52  |  Model: mistral-small-latest

---

## 1. Study Overview

### Research Questions
| RQ | Question |
|-----|---------|
| **RQ1a** | Does phrasing complexity (T2 unusual, T3 adversarial) hurt classification accuracy? |
| **RQ1b** | Do Spanish L1 orthographic (Typo) and grammatical (Grammar) errors hurt classification? |
| **RQ2** | Does training on variant queries during AACP construction improve L2 robustness? |
| **RQ3a** | Which prompt strategies can recover robustness lost to typos? |
| **RQ3b** | Is it better to query in clean Spanish L1 or poor English L2? |

### Agents and Conditions
| Agent | Condition | Dev set | Best dev acc | AACP iterations |
|-------|-----------|---------|-------------|----------------|
| llm_A_std | std-only | 50 std | 98% | 2 (converged) |
| llm_B_std | std-only | 50 std | 100% | 2 (converged) |
| llm_C_std | std-only | 50 std | 98% | 2 (converged) |
| llm_A | full | 150 mixed | 92.0% | 4 (patience) |
| llm_B | full | 150 mixed | 92.0% | 3 (degradation stop) |
| llm_C | full | 150 mixed | 94.7% | 5 (patience) |

### Evaluation Sets
| Set | n | Description |
|-----|---|-------------|
| **Tier 1 (T1)** | 116 | Standard typical phrasings — main benchmark |
| **Tier 2 (T2)** | 68 | Unusual phrasings (informal, verbose, telegraphic) |
| **Tier 3 (T3)** | 54 | Adversarial (ambiguous, compound, near-misses) |
| **Standard-77** | 77 | Matched subset of standard queries (paired with noise sets) |
| **Typo-77** | 77 | Orthographic noise — Spanish L1 spelling errors (corrected) |
| **Grammar-77** | 77 | Grammatical noise — Spanish L1 interference patterns |
| **Spanish-77** | 77 | Clean Spanish L1 queries (manually translated and corrected) |
| **Typo+V1** | 77 | Typo-77 + explicit noise instruction in prompt |
| **Typo+V2** | 77 | Typo-77 + LLM spell-correction preprocessing (2 calls/query) |
| **Typo+V3** | 77 | Typo-77 + 10 few-shot typo examples in prompt |

---

## 2. RQ1a — Phrasing Complexity (T2/T3)

*(From ablation study — full standard evaluation sets)*

| Condition | T1 (116) | T2 (68) | Δ T2 | T3 (54) | Δ T3 |
|-----------|----------|---------|------|---------|------|
| std-only mean | 81.6% | 78.4% | -3.2% | 80.2% | -1.4% |
| full mean | 83.3% | 78.4% | -4.9% | 84.6% | +1.3% |

**Finding**: Phrasing complexity has a small, inconsistent effect. T3 (adversarial) shows no
clear drop — possibly because adversarial queries are still explicit about their intent.

---

## 3. RQ1b — Vulnerability to L2 Noise

### 3.1 Ablation results (T1 baseline vs original typo/grammar sets, 77 queries)

| Condition | T1 baseline | Typo Δ | Grammar Δ |
|-----------|------------|--------|-----------|
| std-only mean | 81.6% | -7.2% | -0.7% |
| full mean | 83.3% | -11.0% | -0.6% |

### 3.2 Rabanser matched-pairs analysis (Standard-77 baseline)

| Agent | Cond | Std-77 | Typo | Δ Typo | Grammar | Δ Gram |
|-------|------|--------|------|--------|---------|--------|
| llm_A_std | std-only | 87.0% | 81.8% | -5.2% | 85.7% | -1.3% |
| llm_B_std | std-only | 87.0% | 81.8% | -5.2% | 83.1% | -3.9% |
| llm_C_std | std-only | 81.8% | 81.8% | +0.0% | 81.8% | +0.0% |
| llm_A | full | 83.1% | 77.9% | -5.2% | 79.2% | -3.9% |
| llm_B | full | 87.0% | 83.1% | -3.9% | 83.1% | -3.9% |
| llm_C | full | 85.7% | 79.2% | -6.5% | 83.1% | -2.6% |
| **Std-only mean** | | 85.3% | 81.8% | -3.5% | 83.5% | -1.7% |
| **Full mean** | | 85.3% | 80.1% | -5.2% | 81.8% | -3.5% |

**Finding**: Typo errors cause consistent -5 to -6% degradation. Grammar errors are milder (-1 to -4%).
The `general` category is the most vulnerable in both cases (38–62% under typo noise).

---

## 4. RQ2 — Effect of Variant Training

| Set | std-only avg | full avg | Δ (full − std) | Finding |
|-----|-------------|----------|----------------|---------|
| Typo-77 | 81.8% | 80.1% | -1.7% | No benefit |
| Grammar-77 | 83.5% | 81.8% | -1.7% | No benefit |

**Finding**: Training on variant queries (AACP with full dev set) does not improve L2 robustness.
The meta-LLM learns category disambiguation rules, not noise-handling strategies.

---

## 5. RQ3a — Typo Robustness Strategies

### 5.1 All 6 agents on Typo-77 (corrected set)

| Agent | Cond | Typo baseline | V1 Explicit | Δ V1 | V2 Preprocess | Δ V2 | V3 Few-shot | Δ V3 |
|-------|------|--------------|-------------|------|--------------|------|-------------|------|
| llm_A_std | std-only | 81.8% | 83.1% | +1.3% | 88.3% | +6.5% | 87.0% | +5.2% |
| llm_B_std | std-only | 81.8% | 85.7% | +3.9% | 88.3% | +6.5% | 88.3% | +6.5% |
| llm_C_std | std-only | 81.8% | 87.0% | +5.2% | 87.0% | +5.2% | 88.3% | +6.5% |
| llm_A | full | 77.9% | 84.4% | +6.5% | 83.1% | +5.2% | 81.8% | +3.9% |
| llm_B | full | 83.1% | 87.0% | +3.9% | 84.4% | +1.3% | 84.4% | +1.3% |
| llm_C | full | 79.2% | 87.0% | +7.8% | 81.8% | +2.6% | 83.1% | +3.9% |
| **Std-only mean** | | 81.8% | 85.3% | +3.5% | 87.9% | +6.1% | 87.9% | +6.1% |
| **Full mean** | | 80.1% | 86.1% | +6.1% | 83.1% | +3.0% | 83.1% | +3.0% |
| **Overall mean** | | 81.0% | 85.7% | +4.8% | 85.5% | +4.5% | 85.5% | +4.5% |

### 5.2 Strategy comparison (original typo set, llm_A_std only — from prior study)

| Approach | Accuracy | Δ baseline |
|----------|----------|------------|
| Baseline (llm_A_std) | 74.0% | — |
| V1 — Explicit instruction | 83.1% | +9.1% |
| V2 — Preprocessing | 79.2% | +5.2% |
| V3 — Few-shot | 83.1% | +9.1% |

### 5.3 Analysis

Across all 6 agents on the corrected Typo-77 set:

| Approach | Mean gain vs typo baseline | Cost |
|----------|--------------------------|------|
| V1 Explicit | +4.8% | 1 call/query |
| V2 Preprocess | +4.5% | 2 calls/query |
| V3 Few-shot | +4.5% | 1 call/query |

**Key finding**: V2 (preprocessing) is the **best strategy** on the corrected set, matched by V3.
V1 (explicit instruction) also improves but slightly less. All strategies recover 6–8 percentage points.
This differs from the prior study on the original set (where V1=V3>V2), suggesting the corrected
typo set is harder and preprocessing adds more value on well-formed noise.

---

## 6. RQ3b — Clean Spanish L1 vs Poor English L2

| Condition | Mean accuracy (all 6 agents) | Δ vs Standard-77 |
|-----------|----------------------------|------------------|
| Standard-77 (clean EN) | 85.3% | +0.0% |
| Typo-77 (poor L2 ortho) | 81.0% | -4.3% |
| Grammar-77 (poor L2 gram) | 82.7% | -2.6% |
| Spanish-77 (clean L1) | 81.6% | -3.7% |

| Agent | Cond | Std-77 | Typo Δ | Grammar Δ | Spanish Δ |
|-------|------|--------|--------|-----------|-----------|
| llm_A_std | std-only | 87.0% | -5.2% | -1.3% | -3.9% |
| llm_B_std | std-only | 87.0% | -5.2% | -3.9% | -5.2% |
| llm_C_std | std-only | 81.8% | +0.0% | +0.0% | -2.6% |
| llm_A | full | 83.1% | -5.2% | -3.9% | -1.3% |
| llm_B | full | 87.0% | -3.9% | -3.9% | -6.5% |
| llm_C | full | 85.7% | -6.5% | -2.6% | -2.6% |

**Finding**: Clean Spanish L1 (-3.7% mean) degrades accuracy more than grammar noise (-2.6%)
but less than typo noise (-4.3%). The LLM handles Spanish reasonably despite English-only prompts.
The std-only agents show smaller degradation on Spanish than full agents.

---

## 7. Safety Analysis (Rabanser framework)

- **L1**: in-scope query → wrong in-scope class (correct domain, wrong category)
- **L2 reject**: in-scope query → `general`/`out_of_scope` (false domain rejection)
- **L2 accept**: `general` query → in-scope class (false domain acceptance)
- **OOS refusal**: `out_of_scope` queries correctly classified

### 7.1 Mean safety rates by set (all 6 agents)

| Set | L1 rate | L2 reject | L2 accept | OOS refusal |
|-----|---------|-----------|-----------|-------------|
| standard | 7.9% | 3.3% | 22.9% | 79.2% |
| typo | 7.1% | 7.4% | 39.6% | 87.5% |
| typo_v1 | 7.9% | 3.8% | 16.7% | 81.2% |
| typo_v2 | 6.8% | 4.6% | 29.2% | 87.5% |
| typo_v3 | 6.8% | 5.7% | 16.7% | 87.5% |
| grammar | 12.0% | 1.1% | 47.9% | 91.7% |
| spanish | 8.7% | 4.9% | 20.8% | 62.5% |

### 7.2 Key safety observations

- **L2 false acceptance** (general→in-scope) is the dominant failure: full agents show 25–62%
  at standard, rising to 50–87% under typo/grammar noise
- **Std-only agents are safer**: L2 accept at 0–12% standard vs 25–62% for full agents
- **Typo strategies reduce L2 accept**: V1/V2/V3 lower false acceptance by recovering `general` queries
- **Spanish L1 is safer than L2 noise**: L2 accept reverts toward standard levels
- **OOS refusal** is paradoxically higher under noise (87–100% grammar) — broken syntax
  triggers conservative refusal, a double-edged effect

---

## 8. Summary and Conclusions

| RQ | Finding | Strength |
|----|---------|---------|
| **RQ1a** | Phrasing complexity (T2/T3): small inconsistent effect (-1 to -5%) | Weak |
| **RQ1b** | Typo: consistent -5 to -7% drop; Grammar: mild -1 to -4% | Strong for typo |
| **RQ2** | Variant training (full AACP) does not improve L2 robustness | Clear null result |
| **RQ3a** | V1/V2/V3 recover +6 to +8pp on typo set; V2/V3 best overall | Strong, practical |
| **RQ3b** | Clean Spanish L1 (-3.7%) worse than grammar (-2.6%), better than typo (-4.3%) | Moderate |

### Key takeaways

1. **LLMs are moderately vulnerable to orthographic noise** (Spanish L1 typos), less so to
   grammatical interference from the same L1. Clean Spanish L1 falls between the two.

2. **AACP cannot overcome noise vulnerability** — even when noise variants are included in
   the dev set. The meta-LLM learns category disambiguation, not noise robustness.

3. **Std-only agents have better safety profiles**: lower L2 false acceptance despite
   comparable or slightly lower robustness accuracy.

4. **Simple prompt strategies work**: V2 (spell-correction preprocessing) and V3 (few-shot)
   recover 6–8pp on typo queries. V1 (explicit instruction) is nearly as effective at no extra cost.

5. **Persistent challenge**: the `general` category (non-RAI research with noise) remains the
   hardest to classify reliably across all conditions and strategies.

6. **Spanish L1 is not a simple substitute for English**: accuracy drops ~3.7% even with clean
   queries, but safety profiles are better than under L2 noise conditions.

---
*Report generated: 2026-10-11 13:52  |  Agents: rag_study_10Oct  |  Model: mistral-small-latest*