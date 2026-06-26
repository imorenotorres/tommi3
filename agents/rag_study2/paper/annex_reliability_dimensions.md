## Annex: Reliability Dimensions — Detailed Definitions

The study adopts the four-dimensional reliability framework from Rabanser et al. (2025), adapted to the specific context of query classification in RAG agents. Each dimension captures a different aspect of "can we trust this system?".

### 1. Consistency (R_Con)

**Question**: *Does the agent produce the same result for the same input across multiple runs?*

A consistent system is one where repeating the same query yields the same answer. Inconsistency erodes user trust — if asking "List papers on AI ethics" gives different results each time, users cannot rely on the system.

Decomposed into three sub-measures:

| Sub-measure | Definition | How measured in this study |
|---|---|---|
| **C_traj** (trajectory consistency) | Does the classifier assign the same category to the same query across runs? | Run each query K=5 times through the classifier. Fraction of queries receiving the same classification in all runs. Rule-based = 100% by construction (deterministic). LLM-based <= 100% (stochastic). |
| **C_out** (outcome consistency) | Does the full agent produce the same response for the same query across runs? | Run each query K=3 times through the full agent. Fraction producing identical responses (exact string match). Programmatic paths = 100% (deterministic code). LLM paths ~ 0% (inherently variable). |
| **C_res** (resource consistency) | Does the system use similar resources (time, API calls) across runs? | Coefficient of variation of response latency across runs. Rule-based ~ 2-4ms (pattern matching). LLM-based ~ 556ms with higher variance (network/API fluctuations). |

**Aggregate**: R_Con = (C_traj + C_out) / 2

**Key insight from the study**: Perfect classification consistency (C_traj = 100%) does not guarantee high response consistency (C_out). If the classifier is deterministic but inaccurate, queries are *consistently routed to the wrong path*, producing inconsistent LLM-generated responses. This is the "consistency paradox" — determinism without accuracy yields consistently wrong routing.

### 2. Robustness (R_Rob)

**Question**: *Does the agent handle perturbations — rephrased queries, unusual phrasings, adversarial inputs — correctly?*

A robust system handles natural language variation gracefully. Users don't phrase queries identically; the system should understand "Show me AI ethics papers", "List publications about ethical AI", and "What has been published on responsible artificial intelligence?" as equivalent.

| Sub-measure | Definition | How measured in this study |
|---|---|---|
| **R_prompt** (prompt robustness) | Does the classifier produce the correct result when the query is rephrased? | 216 evaluation queries across 3 difficulty tiers: Tier 1 (standard phrasings), Tier 2 (unusual phrasings), Tier 3 (adversarial/boundary cases). Fraction correctly classified at each tier. |

The Rabanser et al. framework also defines R_fault (resilience to system faults such as API timeouts or missing data) and R_env (stability across different deployment environments). These were not measured in this study because all agents share the same infrastructure and the focus is on classification behaviour, not operational resilience.

**Aggregate**: R_Rob = R_prompt

**Key insight**: Robustness is measured by accuracy *degradation* across tiers. The LLM-based classifier degrades only 3.3 points (T1: 91.3% to T3: 88.0%), while generalised rules degrade 42.4 points (T1: 96.7% to T3: 54.3%). Rules excel on anticipated phrasings but collapse on unexpected ones.

### 3. Predictability (R_Pred)

**Question**: *Can we predict when the system will produce a correct vs. incorrect response?*

A predictable system is one where we know in advance whether to trust its output. In RAG agents with programmatic paths, the response type (programmatic vs. LLM-generated) serves as a built-in confidence signal — programmatic responses are deterministic and verifiable, while LLM responses may contain hallucinations.

| Sub-measure | Definition | How measured in this study |
|---|---|---|
| **Programmatic path fraction** | What fraction of queries are routed to programmatic (deterministic) paths? | Fraction of evaluation queries classified into categories with programmatic response paths (~54-61% across all variants). |
| **Programmatic path accuracy** | When a query is routed to a programmatic path, how often is the classification correct? | Accuracy of classification for queries routed to programmatic paths only. |
| **LLM path accuracy** | When a query falls through to the LLM, how often is the classification correct? | Accuracy of classification for queries routed to LLM fallback paths only. |

The Rabanser et al. framework defines predictability through calibration (P_cal: do the system's confidence scores match actual accuracy?) and discrimination (P_AUROC: can the system distinguish correct from incorrect outputs?). In this study, the classification mechanism itself serves as the predictability signal: programmatic paths are inherently more predictable than LLM paths, so the fraction of queries correctly routed to programmatic paths becomes the primary predictability measure.

**Aggregate**: R_Pred measures whether the system's internal signals (which path was chosen) correlate with actual correctness.

**Key insight**: If programmatic path accuracy is much higher than LLM path accuracy, the system is predictable — users can trust green-bannered (programmatic) responses more than yellow/red-bannered (LLM) ones. The LLM-based classifier achieves uniformly high accuracy on both paths (~88-89%), making behaviour predictable regardless of path.

### 4. Safety (R_Saf)

**Question**: *When the agent encounters queries it should not answer, does it refuse correctly?*

A safe system refuses out-of-scope queries rather than generating plausible-sounding but fabricated answers. In a domain-specific research assistant, answering "Write me a recipe" or "What's the weather?" with AI-generated content is a safety failure — it wastes user time and erodes trust in legitimate responses.

| Sub-measure | Definition | How measured in this study |
|---|---|---|
| **Refusal accuracy** | Fraction of off-topic and non-research queries correctly refused. | Accuracy on queries labelled `off_topic` or `non_research` in the evaluation set. Correct = classified into a refusal category and responded with a programmatic refusal message. |

The Rabanser et al. framework defines safety through compliance (S_comp: does the system follow safety policies?) and harm severity (S_harm: when it fails, how bad are the consequences?). In this study, refusal accuracy operationalises S_comp directly. S_harm is implicit: a failed refusal in a research assistant means the LLM generates content on a topic outside the knowledge base, risking hallucinated facts presented as authoritative — a moderate-severity failure in educational contexts classified as high-risk under the EU AI Act (European Parliament & Council, 2024).

**Aggregate**: R_Saf = refusal accuracy

**Key insight**: The hand-crafted rule-based agent refuses only 50% of out-of-scope queries despite months of development — the other 50% fall through to the LLM, which generates hallucinated content on topics outside the knowledge base. The LLM-based classifier achieves 93.6% refusal accuracy. In domains classified as high-risk under the EU AI Act (e.g., education), high refusal accuracy is not optional.

### Summary Table

| Dimension | Question | Sub-measures used | Aggregate formula |
|---|---|---|---|
| **Consistency** (R_Con) | Same input, same output? | C_traj (classification), C_out (response), C_res (latency) | (C_traj + C_out) / 2 |
| **Robustness** (R_Rob) | Handles rephrasing? | R_prompt (accuracy across difficulty tiers) | R_prompt |
| **Predictability** (R_Pred) | Know when to trust it? | Path fraction, path accuracy | Programmatic/LLM path accuracy |
| **Safety** (R_Saf) | Refuses when it should? | Refusal accuracy | Refusal accuracy on off-topic + non-research |
