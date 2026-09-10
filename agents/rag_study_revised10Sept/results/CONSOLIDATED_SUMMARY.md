# Consolidated Results Summary — 8-Class Taxonomy Experiment

**Date:** 2026-09-10
**Location:** `agents/rag_study_revised10Sept/`

---

## 1. Experimental Setup

### 1.1 Taxonomy

The 12-class flat taxonomy from the previous version was replaced with a **3-layer, 8-class taxonomy**:

**Layer 1 — Content intent (8 classes):**

| Class | Description |
|---|---|
| papers | Queries whose primary object is a set of publications |
| researcher | Queries about specific researchers |
| project | Queries about named research projects |
| topic | Queries that survey a research subject area (incl. gaps) |
| glossary | Definitional queries about a single concept or term |
| organization | Factual queries about UNINOVIS or member institutions |
| meta | Queries about the agent itself, its data sources or capabilities |
| out_of_scope | Anything not answerable by this agent |

**Layer 2 — Turn type:** initial / follow_up
**Layer 3 — Output format:** text / figure / table

**Migration from 12-class:**
- non_research + off_topic → out_of_scope
- topic_search + gap → topic (gap queries retain facet='gap')
- figure → reclassified by content intent + output_format='figure'
- followup → excluded from content accuracy (Layer 2 only)
- general → case-by-case: glossary / topic / out_of_scope
- meta → split: agent-related stays meta, UNINOVIS/institution → organization

### 1.2 Query Sets

| Set | Content queries | Follow-up (L2) | Total | Tiers |
|---|---|---|---|---|
| Development | 78 | 3 | 81 | 1 only |
| Evaluation | 233 | 18 | 251 | T1: 113, T2: 65, T3: 55 |

**Development set distribution:**

| Class | N |
|---|---|
| out_of_scope | 23 |
| topic | 13 |
| papers | 10 |
| glossary | 9 |
| researcher | 8 |
| project | 7 |
| meta | 5 |
| organization | 3 |

**Evaluation set distribution:**

| Class | N | T1 | T2 | T3 |
|---|---|---|---|---|
| out_of_scope | 58 | 27 | 20 | 11 |
| topic | 54 | 26 | 14 | 14 |
| papers | 29 | 16 | 7 | 6 |
| glossary | 24 | 11 | 7 | 6 |
| researcher | 23 | 13 | 5 | 5 |
| project | 21 | 11 | 5 | 5 |
| meta | 18 | 7 | 5 | 6 |
| organization | 6 | 2 | 2 | 2 |

**Tier definitions:**
- Tier 1: Standard phrasings — typical user queries
- Tier 2: Unusual phrasings — informal, verbose, telegraphic, indirect
- Tier 3: Adversarial — ambiguous, compound, edge cases, near-misses

### 1.3 Agent Variants

| Agent | Classification | Description |
|---|---|---|
| **Baseline** | None | Vanilla RAG: BM25 retrieval + LLM, no classification |
| **Production** | Rule-based (hand-crafted) | MetadataRAGMixin's 13-step chain developed over months, remapped to 8-class |
| **Auto rule-based** | Rule-based (constructed) | Regex/keyword patterns built from scratch using the constructor |
| **LLM-based** | LLM prompt (constructed) | Classification prompt built from scratch using the constructor |

**Controlled variable:** All classified agents share the same dispatch module (`shared/dispatch.py`) and the same programmatic response paths. Given the same classification, all agents produce identical output. The only difference is **how** the classification is produced.

**Information parity:** Both constructed agents (auto rule-based and LLM-based) received the same information during construction: the 8-class taxonomy definition, the development set queries, and the error analysis from each iteration. The difference is only in **how** they encode that information (regex patterns vs. natural language prompt).

---

## 2. Construction Protocol

Both agents were built from scratch using an iterative protocol:
1. Start with minimal rules/prompt based only on the 8-class taxonomy descriptions
2. Run constructor against `development_set_8class.json` (78 content queries)
3. Analyse misclassifications (error patterns: expected → got)
4. Add/refine rules or prompt text to fix errors
5. Repeat until convergence

### 2.1 Auto Rule-Based Construction Trajectory

| Iteration | Accuracy | Errors | Key changes |
|---|---|---|---|
| 0 | 88.5% (69/78) | 9 | Initial skeleton from taxonomy definitions only |
| 1 | 96.2% (75/78) | 3 | +figure detection before project/researcher; +typo-tolerant scope check; +partial-word glossary matching; +topic "at" preposition; +paper-query guard on researcher |
| 2 | 97.4% (76/78) | 2 | +person name check always runs; +"written by" exemption for university queries |
| 3 | **100.0% (78/78)** | **0** | +university code + papers guard on researcher DB lookup |

**Error pattern evolution:**
- Iter 0: papers→researcher (5x), out_of_scope→topic (1x), papers→project (1x), glossary→out_of_scope (1x), topic→out_of_scope (1x)
- Iter 1: out_of_scope→topic (1x), researcher→out_of_scope (1x), papers→researcher (1x)
- Iter 2: papers→researcher (2x)
- Iter 3: converged

### 2.2 LLM-Based Construction Trajectory

| Iteration | Accuracy | Consistency (K=5) | Errors | Key changes |
|---|---|---|---|---|
| 0 | 84.6% (66/78) | 96.2% | 12 | Initial prompt from taxonomy definitions only |
| 1 | 96.2% (75/78) | 94.9% | 3 | +disambiguation rules for out_of_scope (opinions, non-AI domains); +figure/partner→papers; +researcher vs papers distinction |
| 2 | 94.9% (74/78) | 100.0% | 4 | Overcorrection: papers/topic boundary shifted too far |
| 3 | 97.4% (76/78) | 98.7% | 2 | +refined topic/papers boundary (topic = research area without university) |
| 4 | **98.7% (77/78)** | **98.7%** | **1** | +further refinement; remaining: 1 borderline query ("Any papers about irresponsible AI") |

**Error pattern evolution:**
- Iter 0: out_of_scope→{topic,researcher} (4x), papers→{organization,topic,researcher} (6x), topic→organization (1x), out_of_scope→glossary (1x)
- Iter 1: papers→topic (2x), project→topic (1x)
- Iter 2: topic→papers (4x) — overcorrection
- Iter 3: topic→papers (2x)
- Iter 4: papers→topic (1x) — borderline, inconsistent across runs

---

## 3. Evaluation Results

### 3.1 Baseline (Vanilla RAG)

| Metric | Value |
|---|---|
| Response consistency (C_out, K=3) | **3.3%** (1/30) |
| Refusal accuracy | **0.0%** (0/10) |
| False refusals | 4/20 |
| Avg response length | 147 words |
| Avg response time | 2002 ms |

The baseline never refuses off-topic queries — it hallucinates answers for every input. Response text varies across runs (only 3.3% identical). This establishes the lower bound and demonstrates that classification is essential for reliability.

### 3.2 Full Reliability Benchmark (233 evaluation queries)

#### Overall Accuracy

| Agent | Overall | Tier 1 | Tier 2 | Tier 3 | Degradation T1→T3 |
|---|---|---|---|---|---|
| Auto rule-based | 51.1% | 54.0% | 55.4% | 40.0% | 14.0% |
| Production | 48.9% | 54.0% | 43.1% | 45.5% | 8.5% |
| LLM-based | **82.4%** | **88.5%** | **75.4%** | **78.2%** | 10.3% |

#### Per-Category Accuracy

| Category | N | Auto rule-based | Production | LLM-based |
|---|---|---|---|---|
| glossary | 24 | 17% | 33% | **92%** |
| meta | 18 | 0% | 0% | **67%** |
| organization | 6 | **83%** | 0% | **83%** |
| out_of_scope | 58 | **91%** | 48% | 81% |
| papers | 29 | 45% | 52% | **76%** |
| project | 21 | **95%** | 90% | 90% |
| researcher | 23 | 61% | 48% | **96%** |
| topic | 54 | 19% | **61%** | 80% |

#### Per-Category Per-Tier Accuracy (LLM-based)

| Category | T1 (N) | T2 (N) | T3 (N) |
|---|---|---|---|
| glossary | 91% (11) | 100% (7) | 83% (6) |
| meta | 100% (7) | 40% (5) | 50% (6) |
| organization | 100% (2) | 100% (2) | 50% (2) |
| out_of_scope | 85% (27) | 80% (20) | 73% (11) |
| papers | 81% (16) | 57% (7) | 83% (6) |
| project | 91% (11) | 80% (5) | 100% (5) |
| researcher | 92% (13) | 100% (5) | 100% (5) |
| topic | 88% (26) | 64% (14) | 79% (14) |

#### Rabanser Reliability Dimensions

| Dimension | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| **R_Con (Consistency)** | **0.952** | 0.809 | 0.911 |
| **R_Rob (Robustness)** | 0.685 | 0.702 | **0.860** |
| **R_Pred (Predictability)** | 0.671 | 0.534 | **0.754** |
| **R_Saf (Safety)** | **0.914** | 0.483 | 0.879 |

**Component breakdown:**

| Metric | Auto rule-based | Production | LLM-based |
|---|---|---|---|
| C_traj (classification consistency) | **100.0%** | **100.0%** | 93.6% |
| C_out (response consistency) | **96.7%** | 46.7% | 93.3% |
| C_res (latency CV) | 0.112 | **0.040** | 0.137 |
| Avg latency (ms) | **3** | 4 | 485 |
| Programmatic path fraction | 86.7% | 48.9% | 64.8% |
| Programmatic path accuracy | 47.5% | 57.9% | **86.1%** |
| LLM path accuracy | 74.2% | 40.3% | **78.0%** |
| Refusal accuracy (out_of_scope) | **91.4%** | 48.3% | 87.9% |

#### Safety Failures (out_of_scope misclassified)

| Agent | Failures | Examples |
|---|---|---|
| Auto rule-based | 5/58 | "Generate a bibliography in APA format" → researcher; "Draft a research proposal on explainable AI" → topic |
| Production | 30/58 | Widespread: "Write a paragraph about ML" → topic; "Create a table comparing AI frameworks" → topic |
| LLM-based | 7/58 | "I'm new here" → meta; "Calculate average papers per university" → papers; "write something about XAI for homework" → glossary |

### 3.3 N-Run Variance Analysis (LLM-based, N=3)

| Metric | Mean | Std | Min | Max |
|---|---|---|---|---|
| **Accuracy** | **85.4%** | 0.4% | 85.0% | 85.8% |
| C_traj | 94.3% | 0.9% | 93.6% | 95.3% |
| Tier 1 | 89.7% | 1.0% | 88.5% | 90.3% |
| Tier 2 | 81.5% | 3.1% | 78.5% | 84.6% |
| Tier 3 | 81.2% | 1.1% | 80.0% | 81.8% |
| Degradation T1→T3 | 8.5% | 1.8% | 6.7% | 10.3% |
| Refusal rate | 84.5% | 3.0% | 82.8% | 87.9% |
| **R_Con** | **0.981** | 0.003 | 0.979 | 0.984 |
| **R_Rob** | **0.885** | 0.010 | 0.876 | 0.896 |
| **R_Pred** | **0.758** | 0.002 | 0.757 | 0.760 |
| **R_Saf** | **0.845** | 0.030 | 0.828 | 0.879 |

**Individual runs:**
- Run 1: acc=85.4%, C_traj=94.0%, T1=90.3%, T2=81.5%, T3=80.0%, R_Saf=0.828 (676s)
- Run 2: acc=85.8%, C_traj=93.6%, T1=88.5%, T2=84.6%, T3=81.8%, R_Saf=0.879 (615s)
- Run 3: acc=85.0%, C_traj=95.3%, T1=90.3%, T2=78.5%, T3=81.8%, R_Saf=0.828 (575s)

---

## 4. Key Findings

### 4.1 Generalization Gap (Dev → Eval)

| Agent | Dev set accuracy | Eval set accuracy | Drop |
|---|---|---|---|
| Auto rule-based | 100.0% | 51.1% | **-48.9 pp** |
| LLM-based | 98.7% | 85.4% (mean) | **-13.3 pp** |

Rule-based classification exhibits severe overfitting: 100% on the development set collapses to 51% on unseen phrasings. The LLM-based classifier generalizes substantially better, retaining 85% accuracy — a **3.6x smaller generalization gap**.

### 4.2 Consistency vs. Accuracy Trade-off

Rule-based agents achieve **perfect classification consistency** (C_traj = 100%) but at low accuracy. The LLM-based agent sacrifices some consistency (C_traj = 94.3% ± 0.9%) but gains dramatically in accuracy. This reveals a fundamental trade-off: deterministic rules are perfectly reproducible but brittle; LLM classification is slightly variable but far more robust.

### 4.3 Between-Run Stability

Despite non-determinism, the LLM-based classifier shows remarkably low between-run variance:
- Accuracy std = 0.4% (range: 85.0%–85.8%)
- Rabanser scores std < 0.03 for all dimensions

This confirms that the LLM's non-determinism does **not** translate to practically significant reliability concerns.

### 4.4 Tier Degradation

| Agent | T1 → T3 degradation |
|---|---|
| Auto rule-based | 54.0% → 40.0% = **-14.0 pp** |
| Production | 54.0% → 45.5% = **-8.5 pp** |
| LLM-based | 89.7% → 81.2% = **-8.5 pp** |

The LLM degrades gracefully from standard to adversarial phrasings. Rule-based agents, already at low accuracy, degrade further. The auto rule-based agent shows the worst degradation (-14 pp), consistent with pattern-matching being vulnerable to unusual phrasings.

### 4.5 Safety (Refusal Accuracy)

| Agent | Refusal rate | Mechanism |
|---|---|---|
| Baseline | 0.0% | No classification — never refuses |
| Auto rule-based | **91.4%** (53/58) | Unknown queries default to out_of_scope |
| Production | 48.3% (28/58) | Complex remap logic leaks many queries |
| LLM-based | 84.5% ± 3.0% | Semantic understanding of scope |

The auto rule-based agent's conservative fallback (out_of_scope for anything unrecognized) provides the best refusal accuracy. However, this comes at the cost of also misclassifying many valid queries as out_of_scope (meta 0%, topic 19%). The LLM achieves strong refusal accuracy (84.5%) while maintaining high accuracy on valid queries.

### 4.6 The Baseline Gap

The vanilla RAG baseline (no classification) demonstrates why classification matters:
- **0% refusal accuracy**: never refuses off-topic or task requests
- **3.3% response consistency**: generates different text each time
- **4 false refusals**: occasionally refuses valid queries

Classification, regardless of method, transforms an unreliable system into one with measurable, improvable reliability properties.

### 4.7 Production vs. Constructed Agents

The hand-crafted production agent (developed over months of reactive fixes) performs comparably to the auto rule-based agent constructed in 3 iterations (~48.9% vs 51.1%). Neither generalizes well. This suggests that the fundamental limitation is in the rule-based approach itself, not in the amount of engineering effort.

---

## 5. Summary Table for Paper

| | Baseline | Production (rule) | Auto rule-based | LLM-based |
|---|---|---|---|---|
| **Classification** | None | Hand-crafted | Constructed (3 iter) | Constructed (4 iter) |
| **Dev accuracy** | — | — | 100.0% | 98.7% |
| **Eval accuracy** | — | 48.9% | 51.1% | **85.4% ± 0.4%** |
| **C_traj** | — | 100.0% | 100.0% | 94.3% ± 0.9% |
| **C_out** | 3.3% | 46.7% | 96.7% | 93.3% |
| **R_Con** | — | 0.809 | 0.952 | **0.981 ± 0.003** |
| **R_Rob** | — | 0.702 | 0.685 | **0.885 ± 0.010** |
| **R_Pred** | — | 0.534 | 0.671 | **0.758 ± 0.002** |
| **R_Saf** | 0.0% | 0.483 | **0.914** | 0.845 ± 0.030 |
| **Latency (ms)** | 2002 | 4 | 3 | 485 |

---

## 6. Files and Reproducibility

### Result files
- `results/full_reliability_20260910_000155.json` — Auto rule-based + Production
- `results/full_reliability_20260910_001441.json` — LLM-based (single run)
- `results/baseline_20260910_001802.json` — Vanilla RAG baseline
- `results/nrun_llm_20260910_085639.json` — LLM N=3 variance analysis

### Construction trajectories
- `construction/auto_rule_based_trajectory/` — 4 iteration files
- `construction/llm_based_trajectory/` — 5 iteration files

### Agent code (final state)
- `agents/baseline/agent.py` — Vanilla RAG (no classification)
- `agents/production/agent.py` — Hand-crafted rules, remapped to 8-class
- `agents/auto_rule_based/agent.py` — Constructed rules (iteration 3)
- `agents/llm_based/agent.py` — Constructed LLM prompt (iteration 4)

### Shared infrastructure
- `shared/dispatch.py` — Controlled dispatch (same for all classified agents)
- `benchmark/development_set_8class.json` — 78 content + 3 follow-up queries
- `benchmark/evaluation_set_8class.json` — 233 content + 18 follow-up queries
- `benchmark/full_reliability_benchmark.py` — Rabanser 4-dimension benchmark
- `benchmark/nrun_llm_benchmark.py` — N-run variance analysis
- `benchmark/baseline_benchmark.py` — Baseline response-level metrics
- `construction/constructor.py` — Iterative construction protocol

### Known issues
- `nrun_llm_benchmark.py` hangs when loading all 3 agents in the same process (chromadb SQLite lock conflict via shared data symlinks). Workaround: run LLM agent in isolation.
- Production agent's C_out is low (46.7%) because the MetadataRAGMixin's internal methods (e.g. `_build_glossary_context`) are not perfectly deterministic across calls.
