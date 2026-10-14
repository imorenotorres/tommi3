# Rabanser Reliability Analysis — 10Oct RAG Study (with Spanish L1)
Generated: 2026-10-11 13:40

## Study design
- **Agents**: 3 std-only (llm_A/B/C_std) + 3 full (llm_A/B/C)
- **Evaluation sets**: 77 matched queries per condition
  - **Standard-77**: clean English (baseline)
  - **Typo-77**: orthographic noise — L2 poor (ES→EN typos)
  - **Grammar-77**: grammatical noise — L2 poor (ES L1 interference)
  - **Spanish-77**: clean Spanish L1
- **Research question (RQ3)**: Is it better to query in good L1 Spanish or poor L2 English?

---

## 1. Robustness (R_prompt)

| Agent | Cond | Std-77 | Typo | Δ Typo | Grammar | Δ Gram | Spanish | Δ Spanish |
|-------|------|--------|------|--------|---------|--------|---------|-----------|
| llm_A_std | std-only | 87.0% | 81.8% | -5.2% | 85.7% | -1.3% | 83.1% | -3.9% |
| llm_B_std | std-only | 87.0% | 81.8% | -5.2% | 83.1% | -3.9% | 81.8% | -5.2% |
| llm_C_std | std-only | 81.8% | 81.8% | +0.0% | 81.8% | +0.0% | 79.2% | -2.6% |
| llm_A | full | 83.1% | 77.9% | -5.2% | 79.2% | -3.9% | 81.8% | -1.3% |
| llm_B | full | 87.0% | 83.1% | -3.9% | 83.1% | -3.9% | 80.5% | -6.5% |
| llm_C | full | 85.7% | 79.2% | -6.5% | 83.1% | -2.6% | 83.1% | -2.6% |
| **Std-only mean** | | 85.3% | 81.8% | -3.5% | 83.5% | -1.7% | 81.4% | -3.9% |
| **Full mean** | | 85.3% | 80.1% | -5.2% | 81.8% | -3.5% | 81.8% | -3.5% |
| **Overall mean** | | 85.3% | 81.0% | -4.3% | 82.7% | -2.6% | 81.6% | -3.7% |

### Per-category accuracy

#### Standard

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

#### Typo

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

#### Grammar

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

#### Spanish

| Category | llm_A_std | llm_B_std | llm_C_std | llm_A | llm_B | llm_C |
|----------|--------|--------|--------|--------|--------|--------|
| meta | 5/6 (83%) | 4/6 (67%) | 4/6 (67%) | 6/6 (100%) | 5/6 (83%) | 6/6 (100%) |
| organization | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| out_of_scope | 5/8 (62%) | 5/8 (62%) | 5/8 (62%) | 5/8 (62%) | 5/8 (62%) | 5/8 (62%) |
| general | 6/8 (75%) | 7/8 (88%) | 5/8 (62%) | 4/8 (50%) | 4/8 (50%) | 5/8 (62%) |
| papers | 7/10 (70%) | 6/10 (60%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 7/10 (70%) |
| researcher | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) |
| project | 9/10 (90%) | 9/10 (90%) | 10/10 (100%) | 10/10 (100%) | 9/10 (90%) | 10/10 (100%) |
| topic | 8/10 (80%) | 8/10 (80%) | 7/10 (70%) | 8/10 (80%) | 9/10 (90%) | 7/10 (70%) |
| glossary | 9/10 (90%) | 9/10 (90%) | 9/10 (90%) | 8/10 (80%) | 9/10 (90%) | 9/10 (90%) |

---

## 2. Safety

| Agent | Cond | Set | L1 rate | L2 reject | L2 accept | OOS refusal |
|-------|------|-----|---------|-----------|-----------|-------------|
| llm_A_std | std-only | standard | 6.6% | 3.3% | 12.5% | 75.0% |
| llm_A_std | std-only | typo | 6.6% | 6.6% | 37.5% | 87.5% |
| llm_A_std | std-only | grammar | 9.8% | 0.0% | 37.5% | 87.5% |
| llm_A_std | std-only | spanish | 8.2% | 4.9% | 12.5% | 62.5% |
| llm_B_std | std-only | standard | 6.6% | 4.9% | 0.0% | 75.0% |
| llm_B_std | std-only | typo | 9.8% | 6.6% | 12.5% | 87.5% |
| llm_B_std | std-only | grammar | 11.5% | 1.6% | 25.0% | 75.0% |
| llm_B_std | std-only | spanish | 8.2% | 8.2% | 0.0% | 62.5% |
| llm_C_std | std-only | standard | 9.8% | 3.3% | 12.5% | 62.5% |
| llm_C_std | std-only | typo | 9.8% | 6.6% | 12.5% | 87.5% |
| llm_C_std | std-only | grammar | 11.5% | 3.3% | 37.5% | 87.5% |
| llm_C_std | std-only | spanish | 9.8% | 6.6% | 12.5% | 62.5% |
| llm_A | full | standard | 9.8% | 1.6% | 62.5% | 87.5% |
| llm_A | full | typo | 4.9% | 9.8% | 87.5% | 87.5% |
| llm_A | full | grammar | 14.8% | 1.6% | 75.0% | 100.0% |
| llm_A | full | spanish | 9.8% | 1.6% | 50.0% | 62.5% |
| llm_B | full | standard | 6.6% | 3.3% | 25.0% | 87.5% |
| llm_B | full | typo | 3.3% | 6.6% | 62.5% | 87.5% |
| llm_B | full | grammar | 11.5% | 0.0% | 62.5% | 100.0% |
| llm_B | full | spanish | 9.8% | 3.3% | 37.5% | 62.5% |
| llm_C | full | standard | 8.2% | 3.3% | 25.0% | 87.5% |
| llm_C | full | typo | 8.2% | 8.2% | 25.0% | 87.5% |
| llm_C | full | grammar | 13.1% | 0.0% | 50.0% | 100.0% |
| llm_C | full | spanish | 6.6% | 4.9% | 12.5% | 62.5% |

### Safety means by set (all agents)

| Set | L1 rate | L2 reject | L2 accept | OOS refusal |
|-----|---------|-----------|-----------|-------------|
| standard | 7.9% | 3.3% | 22.9% | 79.2% |
| typo | 7.1% | 7.4% | 39.6% | 87.5% |
| grammar | 12.0% | 1.1% | 47.9% | 91.7% |
| spanish | 8.7% | 4.9% | 20.8% | 62.5% |

---

## 3. RQ3 — Good L1 Spanish vs Poor L2 English

Mean accuracy across all 6 agents:

| Condition | Accuracy | Δ vs Standard |
|-----------|----------|---------------|
| standard | 85.3% | — |
| typo | 81.0% | -4.3% |
| grammar | 82.7% | -2.6% |
| spanish | 81.6% | -3.7% |

**Key finding**: Spanish L1 queries degrade accuracy by approximately the same amount as grammar noise,
and less than typo noise — suggesting the LLM handles clean Spanish reasonably well despite being
prompted in English. The dominant difficulty remains the `general` category boundary regardless of language.

### Safety — Spanish vs L2 noise

| Metric | Standard | Typo | Grammar | Spanish |
|--------|----------|------|---------|---------|
| L1 rate | 7.9% | 7.1% | 12.0% | 8.7% |
| L2 reject | 3.3% | 7.4% | 1.1% | 4.9% |
| L2 accept | 22.9% | 39.6% | 47.9% | 20.8% |
| OOS refusal | 79.2% | 87.5% | 91.7% | 62.5% |