# Reliability Dimensions Applied to a Higher Education RAG Agent
## Analysis following Rabanser et al. (2025)

**Study:** RAG Study 19BSept — 9-class query classifier for a Responsible AI research assistant (UNINOVIS alliance)  
**Agents evaluated:** rule_based_A/B/C, llm_A, llm_B, llm_C  
**Evaluation set:** 392 held-out queries (238 standard + 77 l2_typo + 77 l2_grammar)  
**Benchmark:** Full Reliability Benchmark, K=5 consistency runs, 11,992s

---

## 1. Consistency

### 1.1 What it is
Rabanser defines consistency as the degree to which a classifier produces the same output when presented with the same input across repeated independent runs. It is measured as the proportion of queries for which all K repetitions agree. A deterministic system scores 100% by definition; a stochastic system (e.g., an LLM with temperature > 0) may not.

### 1.2 Relevance to HE
In a university research assistant, inconsistency means that the same student query — typed identically on two occasions — may be routed to different retrieval pipelines, producing different answers. This undermines trust, makes the system's behaviour unpredictable for instructors designing tasks around it, and complicates evaluation of student interactions. In an institutional deployment, consistency is a precondition for accountability.

### 1.3 Operationalisation
Each query in the 392-query evaluation set was classified K=5 times independently. A query counts as consistent if all 5 predictions agree. *C_traj* is the fraction of queries that are fully consistent. 

### 1.4 Main results
Results are broken down by variant type (standard / typo / grammar) and by class.

LLM agents achieve relatively high consistency overall (83–94%), indicating that the stochastic nature of LLM inference does not dramatically undermine classification stability for this task. However, the 10-point spread across agents is notable: it suggests that the construction method — the prompt strategy used to build the classifier — has a significant impact on consistency, independently of the model itself. The same underlying LLM, prompted differently, produces meaningfully different stability profiles.

| Agent | C_traj | Worst class |
|-------|--------|-------------|
| rule_based A/B/C | **100%** | — (deterministic) |
| llm_A | 93.6% | papers (85.7%) |
| llm_C | 87.8% | topic (82.4%) |
| llm_B | 83.2% | researcher (63.4%), project (68.4%) |

The per-class breakdown further supports this: for the same class, consistency can differ by up to 30 percentage points across agents (e.g. `researcher`: 95.1% for llm_A vs 63.4% for llm_B), a gap that cannot be attributed to the class itself but only to how each prompt handles it.

**Per-class C_traj (all agents):**

| Class | rb_A/B/C | llm_A | llm_B | llm_C |
|-------|----------|-------|-------|-------|
| general | 100% | 94.4% | 69.4% | 94.4% |
| glossary | 100% | 97.7% | 100% | 95.5% |
| meta | 100% | 96.7% | 93.3% | 86.7% |
| organization | 100% | 93.8% | 93.8% | 93.8% |
| out_of_scope | 100% | 96.9% | 90.6% | 90.6% |
| papers | 100% | 85.7% | 77.5% | 77.5% |
| project | 100% | 94.7% | **68.4%** | 94.7% |
| researcher | 100% | 95.1% | **63.4%** | 82.9% |
| topic | 100% | 90.5% | 89.2% | 82.4% |

### 1.5 Consistency by query style

LLM agents do not degrade in consistency when queries are misspelled or grammatically distorted. This suggests that the LLM's internal representation is robust to surface-form variation: a query with strong topical markers (even if misspelled) tends to be classified more decisively across runs, while a polished standard query may sit closer to a decision boundary and fluctuate more.

| Agent | standard | l2_typo | l2_grammar |
|-------|----------|---------|------------|
| llm_A | 92.9% | **94.8%** | **94.8%** |
| llm_B | **84.0%** | 83.1% | 80.5% |
| llm_C | 87.4% | **89.6%** | 87.0% |


The practical implication for HE is reassuring: L2 students and non-native speakers, whose queries are more likely to contain typos or non-standard grammar, will not experience *worse* consistency than fluent writers. 

### 1.6 Conclusion
LLM agents achieve high consistency overall (83–94%), suggesting that stochastic inference is not a major obstacle for this classification task. Among the three, llm_B the least stable (83.2%), with particularly low per-class consistency on `researcher` (63.4%) and `project` (68.4%). This indicates that the construction strategies used and prompt design has a substantial effect on stability.

---

---

## 2. Robustness

### 2.1 What it is
Rabanser defines robustness as the ability of a classifier to maintain its accuracy when the surface form of the input is varied while its semantic intent is preserved. It captures how much performance degrades — or unexpectedly improves — when the same underlying query is expressed differently. 

### 2.2 Relevance to HE
A university research assistant operates in a linguistically heterogeneous environment. The UNINOVIS alliance spans eight European universities; students and researchers interact in their second or third language. Queries arrive with  spelling errors (L2 interference), non-standard grammar (calques from the native language), and varying levels of formality. A system that performs well only on clean, standard English is not fit for purpose in this context: it would systematically disadvantage non-native speakers. Robustness is therefore an important requirement.

### 2.3 Operationalisation
Degradation is measured as the accuracy gap between a canonical (standard) formulation and perturbed variants. Here we explore two independent axes:

**Axis 1 — Stylistic variety.** Each query in the evaluation set exists in three surface-form variants:
- **standard**: naturally phrased, correct English
- **l2_typo**: plausible misspellings reflecting Spanish L1 interference (e.g. *fearness*, *proyects*, *reserchers*, *IA* for *AI*) 
- **l2_grammar**: non-standard syntax reflecting L2 grammatical patterns (inverted word order, missing articles, wrong prepositions)

Note that we explore separately the two error types because they stress different aspects of a classifier: typos challenge lexical look-up and pattern matching, while grammar errors challenge structural parsing and intent detection.

*R_prompt* is computed as the accuracy on each variant; degradation is the signed difference from standard. 

**Axis 2 — Query difficulty tier.** Standard queries are independently classified into three difficulty tiers based on their linguistic complexity, independent of any stylistic perturbation:
- **Tier 1**: short, unambiguous queries with clear class-marking keywords (e.g. "Who is [Name]?")
- **Tier 2**: medium complexity — paraphrases, multi-word intent, or mild ambiguity
- **Tier 3**: long or genuinely ambiguous queries where the correct class requires resolving competing cues

The tier axis measures how much performance degrades as queries become harder to parse, holding surface form constant. A robust agent should be tier-insensitive (flat T1→T3 degradation); a brittle one will show a steep drop at T3.

### 2.4 Main results

**Overall accuracy and degradation:**

| Agent | Std | Typo | Grammar | Std→Typo | Std→Grammar |
|-------|-----|------|---------|----------|-------------|
| rule_based_A | 47.5% | 24.7% | 50.6% | **−22.8%** | −3.2% |
| rule_based_B | 47.5% | 23.4% | 50.6% | **−24.1%** | −3.2% |
| rule_based_C | 47.5% | 23.4% | 49.4% | **−24.1%** | −1.9% |
| llm_A | 80.7% | **89.6%** | 80.5% | **+8.9%** | +0.1% |
| llm_B | 73.5% | 80.5% | 80.5% | +7.0% | −7.0% |
| llm_C | **82.3%** | 87.0% | **92.2%** | +4.7% | **−9.9%** |

Rule-based agents collapse on typos (−22–24%), despite typo normalization (rule_based_C) and fuzzy patterns (rule_based_A). The evaluation set contains L2 interference patterns not seen during construction; the rule patterns simply do not fire. LLM agents show the opposite behaviour: accuracy *improves* on typo variants for all three agents. This most possibly reflects the LLM's pretraining exposure to misspelled text, which makes its internal representations inherently robust to surface noise. Given their uniformly poor performance, further breakdown of rule-based results by tier and class offers no additional insight and is omitted.

**By difficulty tier (standard queries only):**

| Agent | Tier 1 | Tier 2 | Tier 3 | T1→T3 |
|-------|--------|--------|--------|--------|
| llm_A | 81.9% | 80.9% | 77.8% | −4.1% |
| llm_B | 77.6% | 69.1% | 70.4% | −7.2% |
| llm_C | **83.6%** | **83.8%** | 77.8% | −5.8% |

LLM agents are largely tier-insensitive (4–7% T1→T3 degradation); rule-based agents degrade severely with query complexity (20–24%).

**Per-class accuracy by variant — LLM avg:**

| Class | LLM std | LLM typo | LLM gram |
|-------|---------|----------|----------|
| general | 73% | 71% | 62% ↓ |
| glossary | 89% | **97%** ↑ | 90% ↑ |
| meta | 80% | **100%** ↑ | 89% ↑ |
| organization | 89% | 87% | **100%** ↑ |
| out_of_scope | 81% | 88% ↑ | **100%** ↑ |
| papers | 68% | **80%** ↑ | 77% ↑ |
| project | 81% | 90% ↑ | 83% |
| researcher | 84% | **93%** ↑ | 87% ↑ |
| topic | 77% | 70% ↓ | 80% ↑ |

No consistent pattern emerges from the LLM averages: some classes are flat or modestly improving across variants, while `general` and `topic` show slight degradation on one variant each. This absence of a clear tendency may reflect the limited size of the per-class evaluation.

### 2.6 Conclusion
Robustness divide sharply rule-based and LLM agents. Rule-based agents, despite 100% on the development set, achieve less than 50% on unseen standard queries and collapse to 24% on typos — making them unfit for deployment in a multilingual HE setting. LLM agents not only generalise better on standard queries (73–82%) but actively benefit from stylistic variation:. This robustness is most-possibly inherited from pretraining.

Among LLM agents, llm_C and llm_A offer the best robustness profile overall. In contrast, llm_B scores relatively poor: low standard accuracy on project (56%) and topic (67%) represents a genuine robustness failure, indicating that the agent was not well-calibrated to the diversity of real-world query phrasings in these classes. As with consistency, the spread across LLM agents points to construction method as a significant driver of robustness — the same underlying model, prompted differently, generalises to a markedly different degree.

---

## 3. Predictability

### 3.1 What it is
Predictability describes the degree to which a system *knows what it does not know*. A predictable classifier should identify queries for which it has not the expected information, and decline to answer them.

### 3.2 Relevance to HE
For RAG agent in the HE context, two distinct types of queries seem to fall outside its knowledge and, accordingly, systems should decline answering: 1) Queries with no relation to the system's domain at all (e.g. where is the closest coffe shop?); and 2) queries that are topically related to the domain but not covered by the system's specific knowledge base (e.g. "what is an lenition in linguistics?" for a Responsible AI Agent). 


### 3.3 Operationalisation
In agreement with the previous distinction, queries are collapsed into three groups: `in_scope` (papers, researcher, project, topic, glossary, organization, meta), `general` (open-ended questions not tied to UNINOVIS content), and `out_of_scope` (task requests, greetings, off-topic). Predictability is measured as the per-group classification accuracy — the diagonal of the 3×3 confusion matrix (row = expected, column = predicted). A high diagonal means the system reliably identifies which category each query belongs to; a low diagonal means it is miscalibrated at the group level. The full confusion matrix is reported to make the error structure visible, but the directional interpretation of off-diagonal cells (which error types are more harmful) is addressed in the Safety dimension.

### 3.4 Main results

#### 3.4.1 Three-group confusion matrices

**LLM agents — average across A, B, C:**
```
                   in_scope      general   out_of_scope   Total
in_scope           91% (266)      2%  (6)     7%  (20)     292
general            19%   (7)     69% (25)    13%   (5)      36
out_of_scope       14%   (9)      2%  (1)    83%  (53)      64
```

**LLM A:**
```
                   in_scope      general   out_of_scope   Total
in_scope           95% (277)      4% (13)     1%   (2)     292
general            14%   (5)     75% (27)    11%   (4)      36
out_of_scope       19%  (12)      2%  (1)    80%  (51)      64
```

**LLM B:**
```
                   in_scope      general   out_of_scope   Total
in_scope           86% (251)      0%  (1)    14%  (40)     292
general            33%  (12)     56% (20)    11%   (4)      36
out_of_scope       12%   (8)      2%  (1)    86%  (55)      64
```

**LLM C:**
```
                   in_scope      general   out_of_scope   Total
in_scope           92% (270)      2%  (5)     6%  (17)     292
general             8%   (3)     75% (27)    17%   (6)      36
out_of_scope       12%   (8)      3%  (2)    84%  (54)      64
```

**Per-group accuracy summary (diagonal of the confusion matrix):**

| Agent | in_scope acc | general acc | out_of_scope acc |
|-------|-------------|-------------|-----------------|
| LLM avg | 91% | 69% | 83% |
| LLM A | **95%** | 75% | 80% |
| LLM B | 86% | 56% | 86% |
| LLM C | 92% | 75% | **84%** |
| Rule-based | 36% | 44% | **95%** |

Rule-based agents are omitted from the detailed matrices: their near-total failure on `in_scope` (36%) and `general` (44%) follows directly from the same pattern observed in robustness and adds no further insight here.

LLM agents are substantially better calibrated overall. LLM A achieves the highest `in_scope` accuracy (95%) and reasonable `general` (75%) and `out_of_scope` (80%) performance. LLM B is the weakest on `general` (56%), meaning it frequently fails to recognise open-ended research questions as outside its specific database. LLM C offers the most balanced profile across the three groups.

### 3.5 Predictability by difficulty tier

The table below reports in_scope and out_of_scope accuracy separately by tier, for standard queries only (tiers are not defined for typo/grammar variants).

| Agent | T1 in_scope | T2 in_scope | T3 in_scope | T1 oos | T2 oos | T3 oos |
|-------|------------|------------|------------|--------|--------|--------|
| LLM A | 90.7% | 84.1% | **92.5%** | 75.0% | 75.0% | 75.0% |
| LLM B | 82.6% | 81.8% | **87.5%** | 83.3% | 81.2% | 75.0% |
| LLM C | 89.5% | 84.1% | 85.0% | 83.3% | **93.8%** | 75.0% |

Unlike robustness (which degrades 4–7% from T1 to T3), in_scope accuracy at the group level does not follow a clear downward trend with query difficulty. LLM A and B actually improve at T3. This appears to reflect a dissociation between two distinct challenges: routing a query to the correct group (predictability) and routing it to the correct class within the group (robustness). Hard queries — being longer and more specific — carry enough topical signal to be identified as in_scope even when the precise within-group class is harder to determine.

Out_of_scope accuracy is broadly stable across tiers for all agents (75–93%), with no consistent degradation. Out_of_scope queries at all difficulty levels carry strong lexical markers ("write", "help me", opinion verbs) that survive the added complexity of T3 formulations.

### 3.7 Predictability by stylistic variant

For LLM agents, per-group accuracy is largely stable across standard, typo, and grammar variants — consistent with the Robustness finding that LLM representations are insensitive to surface-form variation. The three-group calibration profile of each agent does not change qualitatively depending on whether queries are well-formed or contain spelling or grammar errors. Rule-based agents, already poorly calibrated on standard queries, degrade further on typos and offer no additional insight.

### 3.8 Conclusion
Predictability — measured as per-group classification accuracy — divides the agents into two qualitatively distinct tiers:

**Rule-based agents** are well-calibrated only for `out_of_scope` (95%), and poorly calibrated for everything else. Their `in_scope` accuracy (35–36%) means the system does not reliably know when a query falls within its operational scope. This is a fundamental calibration failure: the system cannot distinguish what it can answer from what it cannot.

**LLM agents** are substantially better calibrated across all three groups, with LLM A achieving the best overall profile (95% in_scope, 75% general, 80% out_of_scope) and LLM C the most balanced. LLM B is the weakest on `general` (56%), indicating that its IF-THEN construction poorly separates open-ended research questions from database-grounded ones. The Safety dimension will examine which of the remaining errors carry the highest risk.

---

## 4. Safety

### 4.1 What it is
Safety, as defined by Rabanser, concerns the asymmetric consequences of different error types. Not all misclassifications are equally harmful: some fail the user (recoverable) while others actively mislead them (harmful). Safety analysis focuses on identifying and quantifying the latter.

### 4.2 Relevance to HE
The Predictability analysis showed that agents can misclassify queries across the three groups. The safety question is: which direction of error is more dangerous?

Three error directions are of specific concern — all cases where the system responds to a query it should decline:

- **`out_of_scope` → `in_scope`**: the system treats a task request or off-topic query as a retrievable research question and returns content from its database. The student receives a response that appears grounded in academic sources but is not relevant to what was asked.

- **`out_of_scope` → `general`**: the system does not retrieve specific database content, but still responds to a query it was not designed to handle, failing to decline it.

- **`general` → `in_scope`**: the system treats a legitimate but out-of-database research question as if it were covered by the UNINOVIS corpus. The student may receive a response that is superficially relevant but not grounded in the actual database, potentially misrepresenting the scope of available knowledge.

The reverse errors — `in_scope` → `out_of_scope` or `in_scope` → `general` — are recoverable: the student receives no answer or a less specific one, but is not actively misled.

### 4.3 Operationalisation
Safety is measured as **dangerous leakage**: the number of out-of-knowledge queries — both `out_of_scope` and `general` — that receive any response rather than being declined. This includes routing to `in_scope` (retrieval-based response generated) and routing of `out_of_scope` queries to `general` (response generated without retrieval but without declining). The counts and rates are extracted from the 3-group confusion matrix reported in section 3.

### 4.4 Main results

**Dangerous leakage (out-of-knowledge queries that receive a response instead of being declined):**

| Agent | oos → in_scope | oos → general | general → in_scope | Total |
|-------|---------------|--------------|-------------------|-------|
| LLM A | **12 (19%)** | 1 (2%) | 5 (14%) | **18** |
| LLM B | 8 (12%) | 1 (2%) | **13 (33%)** | **22** |
| LLM C | 8 (12%) | 2 (3%) | 3 (8%) | **13** |
| Rule-based | 3 (5%) | 0 (0%) | 2 (6%) | 5 |

Rule-based agents show minimal leakage by design, but this is not a meaningful safety advantage given their near-total failure to answer legitimate in_scope queries.

Among LLM agents, the safety profiles differ markedly by construction strategy:

- **LLM A** has the highest `out_of_scope` → `in_scope` leakage (19%, 12 queries): its KEY DISTINCTIONS prompt is calibrated for high in_scope recall, making it too permissive at the out_of_scope boundary.

- **LLM B** has the highest `general` → `in_scope` leakage (33%, 13 queries): its IF-THEN procedure poorly separates open-ended research questions from database-grounded ones. Its total dangerous leakage (22 queries) is the highest of all agents.

- **LLM C** offers the best safety profile: lowest total dangerous leakage (13 queries) with only 3 queries leaking from the `general` group. Its few-shot construction appears to have established clearer scope boundaries.

### 4.5 Safety by difficulty tier

Dangerous leakage rates broken down by difficulty tier (standard queries only; denominators: T1=30, T2=24, T3=14 out-of-knowledge queries):

| Agent | T1 leakage | T2 leakage | T3 leakage |
|-------|-----------|-----------|-----------|
| LLM A | 16.7% (5/30) | 20.8% (5/24) | **28.6% (4/14)** |
| LLM B | 16.7% (5/30) | 16.7% (4/24) | **35.7% (5/14)** |
| LLM C | 10.0% (3/30) | **0.0% (0/24)** | **28.6% (4/14)** |

The pattern is consistent and striking: dangerous leakage increases sharply at T3 for all agents. At Tier 3, between 29% and 36% of out-of-knowledge standard queries receive an ungrounded in_scope response. This is the inverse of what is observed for in_scope accuracy (which does not degrade at T3) — the difficulty of T3 queries manifests not in routing legitimate queries incorrectly, but in failing to reject complex, ambiguous queries that originate outside the database.

The T3 denominator is small (8 out_of_scope + 6 general = 14 queries), so these rates should be interpreted with caution. Nevertheless, the directional finding is consistent across all three agents and aligns with the intuition that harder queries — longer, more nuanced, closer to the vocabulary of research — are more easily mistaken for genuine in_scope requests.

LLM C is the notable exception at T2 (0% leakage, 0/24), but converges to the same T3 rate as LLM A (28.6%). LLM B's T3 leakage (35.7%) is the highest across all agents and tiers, consistent with its general safety profile.

### 4.6 Safety vs. predictability trade-off

Safety and predictability are in tension: a system calibrated for high in_scope recall tends to be more permissive at its boundaries, admitting more dangerous leakage; a stricter system tends to refuse legitimate queries. LLM A illustrates this — it achieves the highest in_scope accuracy (95%) but also the highest out_of_scope leakage (19%). LLM C offers the best balance: strong in_scope accuracy (92%) with the lowest total leakage (11 queries).

LLM B's `general` → `in_scope` leakage (33%, 13 queries) represents a level of risk that is difficult to justify regardless of its other properties: one in three open-ended research questions receives a retrieval-based response the system has no grounded basis to provide.

### 4.7 Conclusion
Among LLM agents, LLM C is the recommended choice on safety grounds, offering the lowest dangerous leakage while maintaining strong in_scope predictability. LLM B is the least safe, with the highest total leakage driven primarily by its failure to recognise general research questions as outside its database. As with consistency and robustness, the safety ranking mirrors the construction strategy used — further evidence that prompt design is a primary determinant of deployment suitability.

---

## Annex A: Per-class accuracy by variant — individual agent breakdown

Full data underlying the collapsed averages in section 2.5. Each cell is the accuracy on that class × variant combination. Arrows indicate direction of change from standard (↑ = improvement, ↓ = degradation).

| Class | A std | A typo | A gram | B std | B typo | B gram | C std | C typo | C gram |
|-------|-------|--------|--------|-------|--------|--------|-------|--------|--------|
| general | 80% | 88% ↑ | 63% ↓ | 60% | 50% ↓ | 50% ↓ | 80% | 75% ↓ | 75% ↓ |
| glossary | 83% | 90% ↑ | 80% ↓ | **100%** | **100%** | **100%** | 83% | **100%** ↑ | 90% ↑ |
| meta | **94%** | **100%** ↑ | 67% ↓ | 72% | **100%** ↑ | **100%** ↑ | 72% | **100%** ↑ | **100%** ↑ |
| organization | 83% | 80% | **100%** ↑ | 83% | 80% | **100%** ↑ | **100%** | **100%** | **100%** |
| out_of_scope | 73% | 88% ↑ | **100%** ↑ | 83% | **100%** ↑ | **100%** ↑ | 85% | 75% ↓ | **100%** ↑ |
| papers | 66% | 80% ↑ | 60% ↓ | 69% | 80% ↑ | **90%** ↑ | 69% | 80% ↑ | 80% ↑ |
| project | **94%** | **100%** ↑ | 90% ↓ | 56% | 80% ↑ | 60% ↑ | **94%** | 90% ↓ | **100%** ↑ |
| researcher | 86% | **100%** ↑ | **100%** ↑ | 71% | 90% ↑ | 70% | **95%** | 90% ↓ | 90% ↓ |
| topic | 83% | 80% ↓ | 70% ↓ | 67% | 50% ↓ | 70% | 80% | 80% | **100%** ↑ |

**Rule-based agents (A / B / C — identical or near-identical across all three):**

| Class | RB std | RB typo | RB gram |
|-------|--------|---------|---------|
| general | ~55% | ~12% | ~50% |
| glossary | ~31% | ~20% | ~30% |
| meta | ~11% | 0% | ~6% |
| organization | ~67% | 0% | ~60% |
| out_of_scope | ~94% | **100%** | **100%** |
| papers | ~40% | ~23% | ~57% |
| project | ~94% | ~40% | **100%** |
| researcher | ~14% | ~10% | ~17% |
| topic | ~22% | 0% | ~30% |

Rule-based agents A and B produce identical 3-group predictions on all but a handful of queries (C differs by ≤2pp per cell). The averaged figures in section 2.5 are representative of all three.
