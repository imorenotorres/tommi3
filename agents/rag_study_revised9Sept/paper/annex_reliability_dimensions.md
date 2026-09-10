## Annex: Reliability Dimensions — Detailed Definitions

The study adopts the four-dimensional reliability framework from Rabanser et al. (2025), adapted to the specific context of query classification in RAG agents. Each dimension captures a different aspect of "can we trust this system?".

### 1. Consistency (R_Con)

**Question**: *Does the classifier produce the same classification for the same input across multiple runs?*

A consistent classifier is one where repeating the same query yields the same classification. Inconsistency erodes user trust — if the same query is routed to different response paths each time, users cannot rely on the system.

| Measure | Definition | How measured |
|---|---|---|
| **R_Con** | Fraction of queries receiving the same classification across K runs | Run each query K=5 times through the classifier. Rule-based = 100% by construction (deterministic). LLM-based ≤ 100% (stochastic). |

$$R_{Con} = \frac{1}{N} \sum_{i=1}^{N} \mathbb{1}\left[\forall k \in \{1,...,K\}: c_k(q_i) = c_1(q_i)\right]$$

where $c_k(q_i)$ is the classification assigned to query $q_i$ on run $k$, and $K = 5$.

### 2. Robustness (R_Rob)

**Question**: *Does the classifier handle perturbations — rephrased queries, unusual phrasings, adversarial inputs — correctly?*

A robust classifier handles natural language variation gracefully. Users don't phrase queries identically; the system should understand "Show me AI ethics papers", "List publications about ethical AI", and "What has been published on responsible artificial intelligence?" as equivalent.

| Measure | Definition | How measured |
|---|---|---|
| **R_Rob** | Classification accuracy across diverse phrasings | 216 evaluation queries across 3 difficulty tiers: Tier 1 (standard phrasings, n=120), Tier 2 (unusual phrasings, n=61), Tier 3 (adversarial/boundary cases, n=35). |

$$R_{Rob} = \frac{1}{N} \sum_{i=1}^{N} \mathbb{1}\left[c(q_i) = y_i\right]$$

where $c(q_i)$ is the predicted classification and $y_i$ is the ground truth label.

The **degradation metric** quantifies robustness loss across tiers:

$$\Delta_{T1 \rightarrow T3} = Acc_{T1} - Acc_{T3}$$

where lower values indicate more robust classification.

**Key finding**: The LLM-based classifier degrades only 3.3 points (T1: 91.3% to T3: 88.0%), while the auto rule-based degrades 42.4 points (T1: 96.7% to T3: 54.3%). Rules excel on anticipated phrasings but collapse on unexpected ones.

### 3. Predictability (R_Pred)

**Question**: *Can we predict when the system will produce a correct vs. incorrect response?*

A predictable system is one where we know in advance whether to trust its output. In RAG agents with programmatic paths, the response type (programmatic vs. LLM-generated) serves as a built-in confidence signal — programmatic responses are deterministic and verifiable, while LLM responses may contain hallucinations.

| Measure | Definition | How measured |
|---|---|---|
| **Programmatic path fraction** | Fraction of queries routed to programmatic (deterministic) paths | ~54–61% across all variants |
| **Classification accuracy (programmatic categories)** | When a query should go to a programmatic path, how often is the classification correct? | Accuracy on queries whose ground truth maps to programmatic paths |
| **Classification accuracy (LLM categories)** | When a query should go to the LLM, how often is the classification correct? | Accuracy on queries whose ground truth maps to LLM paths |

**Key finding**: The LLM-based classifier achieves uniformly high accuracy on both programmatic (~88%) and LLM (~87%) categories, making behaviour predictable regardless of path type.

### 4. Safety (R_Saf)

**Question**: *When the classifier encounters queries the agent should not answer, does it classify them correctly for refusal?*

A safe system refuses out-of-scope queries rather than generating plausible-sounding but fabricated answers. In a domain-specific research assistant, answering "Write me a recipe" or "What's the weather?" with AI-generated content is a safety failure.

| Measure | Definition | How measured |
|---|---|---|
| **R_Saf** (refusal accuracy) | Fraction of off-topic and non-research queries correctly classified for refusal | Accuracy on queries labelled `off_topic` or `non_research` in the evaluation set |

**Key finding**: The production rule-based agent refuses only 50% of out-of-scope queries despite months of development. The LLM-based classifier achieves 93.6% ± 1.0% refusal accuracy. In domains classified as high-risk under the EU AI Act (e.g., education), high refusal accuracy is not optional.

### Summary Table

| Dimension | Question | What is measured | Formula |
|---|---|---|---|
| **R_Con** (Consistency) | Same input, same classification? | Classification consistency across K=5 runs | Fraction of queries with identical classification |
| **R_Rob** (Robustness) | Handles rephrasing? | Classification accuracy across 3 difficulty tiers | Overall accuracy + degradation metric |
| **R_Pred** (Predictability) | Know when to trust it? | Accuracy by response path type (programmatic vs LLM) | Path-specific classification accuracy |
| **R_Saf** (Safety) | Refuses when it should? | Refusal accuracy on out-of-scope queries | Accuracy on off_topic + non_research categories |
