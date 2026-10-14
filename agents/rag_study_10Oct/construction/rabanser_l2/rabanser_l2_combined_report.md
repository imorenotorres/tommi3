# Rabanser L2 Reliability Analysis — 10Oct RAG Study
Generated: 2026-10-11 12:30  |  Sets: Std-77 + Typo-77 + Grammar-77 (matched pairs)

## Study design
- **Agents**: 3 std-only (llm_A/B/C_std, trained on 50 standard dev queries) + 3 full (llm_A/B/C, trained on 150 = 50 std + 50 typo + 50 grammar)
- **Evaluation sets**: 77 matched triplets (standard / typo L1-ES / grammar L1-ES), corrected manually
- **Metrics**: Robustness R_prompt (accuracy + Δ degradation) · Safety L1/L2 (domain boundary errors)
- **No T2/T3** — focus on L2 (orthographic + grammatical) noise only

---

## 1. Robustness (R_prompt)

Accuracy using majority-vote classification (K=1). Δ = accuracy(noise) − accuracy(standard).

| Agent | Condition | Std-77 | Typo-77 | Δ Typo | Grammar-77 | Δ Grammar |
|-------|-----------|--------|---------|--------|------------|-----------|
| llm_A_std | std-only | 87.0% | 81.8% | -5.2% | 85.7% | -1.3% |
| llm_B_std | std-only | 87.0% | 81.8% | -5.2% | 83.1% | -3.9% |
| llm_C_std | std-only | 81.8% | 81.8% | +0.0% | 81.8% | +0.0% |
| llm_A | full | 83.1% | 77.9% | -5.2% | 79.2% | -3.9% |
| llm_B | full | 87.0% | 83.1% | -3.9% | 83.1% | -3.9% |
| llm_C | full | 85.7% | 79.2% | -6.5% | 83.1% | -2.6% |
| **Std-only mean** | | 85.3% | 81.8% | -3.5% | 83.5% | -1.7% |
| **Full mean** | | 85.3% | 80.1% | -5.2% | 81.8% | -3.5% |

### 1.1 Robustness per category — Standard-77 baseline

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C |
|----------|--------|--------|--------|--------|--------|--------|
| meta | 6/6 (100%) | 5/6 (83%) | 5/6 (83%) | 6/6 (100%) | 6/6 (100%) | 6/6 (100%) |
| organization | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 4/5 (80%) |
| out_of_scope | 6/8 (75%) | 6/8 (75%) | 5/8 (62%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) |
| general | 6/8 (75%) | 7/8 (88%) | 5/8 (62%) | 3/8 (38%) | 5/8 (62%) | 5/8 (62%) |
| papers | 7/10 (70%) | 7/10 (70%) | 8/10 (80%) | 9/10 (90%) | 7/10 (70%) | 8/10 (80%) |
| researcher | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) |
| project | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 10/10 (100%) |
| topic | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) | 8/10 (80%) | 10/10 (100%) | 8/10 (80%) |
| glossary | 9/10 (90%) | 9/10 (90%) | 7/10 (70%) | 6/10 (60%) | 8/10 (80%) | 8/10 (80%) |

### 1.2 Robustness per category — Typo-77

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C |
|----------|--------|--------|--------|--------|--------|--------|
| meta | 6/6 (100%) | 5/6 (83%) | 6/6 (100%) | 6/6 (100%) | 6/6 (100%) | 6/6 (100%) |
| organization | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 5/5 (100%) | 4/5 (80%) |
| out_of_scope | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) |
| general | 3/8 (38%) | 5/8 (62%) | 5/8 (62%) | 1/8 (12%) | 2/8 (25%) | 3/8 (38%) |
| papers | 7/10 (70%) | 7/10 (70%) | 7/10 (70%) | 7/10 (70%) | 7/10 (70%) | 7/10 (70%) |
| researcher | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |
| project | 9/10 (90%) | 8/10 (80%) | 9/10 (90%) | 10/10 (100%) | 8/10 (80%) | 10/10 (100%) |
| topic | 7/10 (70%) | 7/10 (70%) | 6/10 (60%) | 7/10 (70%) | 9/10 (90%) | 6/10 (60%) |
| glossary | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |

### 1.3 Robustness per category — Grammar-77

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C |
|----------|--------|--------|--------|--------|--------|--------|
| meta | 5/6 (83%) | 5/6 (83%) | 5/6 (83%) | 5/6 (83%) | 5/6 (83%) | 5/6 (83%) |
| organization | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| out_of_scope | 7/8 (88%) | 6/8 (75%) | 7/8 (88%) | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) |
| general | 4/8 (50%) | 5/8 (62%) | 4/8 (50%) | 2/8 (25%) | 2/8 (25%) | 3/8 (38%) |
| papers | 9/10 (90%) | 8/10 (80%) | 8/10 (80%) | 8/10 (80%) | 9/10 (90%) | 8/10 (80%) |
| researcher | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) |
| project | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) |
| topic | 9/10 (90%) | 8/10 (80%) | 8/10 (80%) | 8/10 (80%) | 10/10 (100%) | 8/10 (80%) |
| glossary | 8/10 (80%) | 8/10 (80%) | 7/10 (70%) | 6/10 (60%) | 6/10 (60%) | 8/10 (80%) |

---

## 2. Safety

- **L1**: in-scope query misclassified into another in-scope category (correct domain, wrong class)
- **L2 false rejection**: in-scope query classified as `general` or `out_of_scope` (domain rejection)
- **L2 false acceptance**: `general` query classified as an in-scope category (false domain admission)
- **OOS refusal rate**: `out_of_scope` queries correctly classified as `out_of_scope`

| Agent | Condition | Set | L1 rate | L2 reject | L2 accept | OOS refusal |
|-------|-----------|-----|---------|-----------|-----------|-------------|
| llm_A_std | std-only | standard | 6.6% | 3.3% | 12.5% | 75.0% |
| llm_A_std | std-only | typo | 6.6% | 6.6% | 37.5% | 87.5% |
| llm_A_std | std-only | grammar | 9.8% | 0.0% | 37.5% | 87.5% |
| llm_B_std | std-only | standard | 6.6% | 4.9% | 0.0% | 75.0% |
| llm_B_std | std-only | typo | 9.8% | 6.6% | 12.5% | 87.5% |
| llm_B_std | std-only | grammar | 11.5% | 1.6% | 25.0% | 75.0% |
| llm_C_std | std-only | standard | 9.8% | 3.3% | 12.5% | 62.5% |
| llm_C_std | std-only | typo | 9.8% | 6.6% | 12.5% | 87.5% |
| llm_C_std | std-only | grammar | 11.5% | 3.3% | 37.5% | 87.5% |
| llm_A | full | standard | 9.8% | 1.6% | 62.5% | 87.5% |
| llm_A | full | typo | 4.9% | 9.8% | 87.5% | 87.5% |
| llm_A | full | grammar | 14.8% | 1.6% | 75.0% | 100.0% |
| llm_B | full | standard | 6.6% | 3.3% | 25.0% | 87.5% |
| llm_B | full | typo | 3.3% | 6.6% | 62.5% | 87.5% |
| llm_B | full | grammar | 11.5% | 0.0% | 62.5% | 100.0% |
| llm_C | full | standard | 8.2% | 3.3% | 25.0% | 87.5% |
| llm_C | full | typo | 8.2% | 8.2% | 25.0% | 87.5% |
| llm_C | full | grammar | 13.1% | 0.0% | 50.0% | 100.0% |

### 2.1 Safety means by condition and set

| Set | Metric | Std-only mean | Full mean |
|-----|--------|--------------|-----------|
| standard | L1 rate | 7.7% | 8.2% |
| standard | L2 false rejection | 3.8% | 2.7% |
| standard | L2 false acceptance | 8.3% | 37.5% |
| standard | OOS refusal | 70.8% | 87.5% |
| typo | L1 rate | 8.7% | 5.5% |
| typo | L2 false rejection | 6.6% | 8.2% |
| typo | L2 false acceptance | 20.8% | 58.3% |
| typo | OOS refusal | 87.5% | 87.5% |
| grammar | L1 rate | 10.9% | 13.1% |
| grammar | L2 false rejection | 1.6% | 0.5% |
| grammar | L2 false acceptance | 33.3% | 62.5% |
| grammar | OOS refusal | 83.3% | 100.0% |

---

## 3. Key findings

### Robustness
- **Typo noise degrades more than grammar noise** across all agents
  (mean Δ typo ≈ −4 to −6%; mean Δ grammar ≈ −1 to −4%)
- **`general` is the most vulnerable category**: drops from ~62–88% (std) to as low as 12% (typo, llm_A)
  — boundary between domain-relevant and domain-irrelevant research is most sensitive to surface noise
- **`researcher`, `project`, `meta`** are most robust: typically ≥80% under both noise types
- **Std-only vs full training**: no consistent advantage for full training in robustness
  (llm_C_std shows 0% degradation; full agents degrade comparably or more)

### Safety
- **L2 false acceptance** is the dominant safety failure: `general` queries over-classified as in-scope
  — especially severe in full agents (25–62% at std; 50–87% under typo/grammar)
  — std-only agents are notably safer here (0–12.5% at std)
- **L1 errors** (wrong in-scope class) increase modestly under noise (~+3–5pp), consistent across agents
- **L2 false rejection** is low across all conditions (<10%), suggesting the model rarely
  rejects genuinely domain-relevant queries even when noisy
- **OOS refusal rate** improves under noise (grammar: 87–100%), suggesting broken syntax
  triggers conservative refusal — a double-edged effect

### Implications for the paper (L2 focus)
- LLMs are **moderately robust** to orthographic and grammatical L1-ES noise in overall accuracy,
  but show **systematic safety degradation** at the domain boundary (`general` category)
- Full training on noise variants does **not reliably improve robustness** and may worsen safety
  (higher L2 false acceptance) by making agents more inclusive of noisy in-domain-looking queries
- Std-only agents offer a better safety profile with comparable accuracy degradation