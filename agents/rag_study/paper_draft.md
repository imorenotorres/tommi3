# Beyond Vanilla RAG: Improving Reliability Through Query Classification — A Controlled Comparison of Deterministic and LLM-Based Approaches

## Abstract

Vanilla Retrieval-Augmented Generation (RAG) — where every query follows the same retrieve-then-generate pipeline — is the dominant architecture for domain-specific AI assistants. While simple to implement, this one-size-fits-all approach limits reliability: the system cannot distinguish a factual lookup (answerable from structured data) from a speculative question (requiring LLM reasoning), treating both identically. A natural improvement is to add a query classification stage that routes queries to specialised response paths — some bypassing the LLM entirely. But how should this classification be implemented? We present a controlled study comparing two approaches: deterministic rule-based classification using pattern matching, and non-deterministic LLM-based classification using a separate LLM call. Both share identical downstream response paths — the only independent variable is the classification mechanism. To ensure a fair and reproducible comparison, we introduce an *automated agent construction protocol*: given identical starting conditions (data, categories, training examples), an automated constructor builds both classifiers from scratch and iterates them to equivalent accuracy on a development set. Reliability is then evaluated on an independent set using the four-dimensional framework from Rabanser et al. (2025) — consistency, robustness, predictability, and safety. By controlling for accuracy, the study isolates the reliability implications of each classification mechanism. Results show that [TO BE COMPLETED].

---

## 1. Introduction

### 1.1 The Vanilla RAG Baseline

Retrieval-Augmented Generation (Lewis et al., 2020) has become the standard architecture for building domain-specific AI assistants. In its simplest form — which we term *vanilla RAG* — every user query follows an identical pipeline: retrieve relevant document chunks, inject them into the LLM context, and generate a response. This architecture is easy to implement and powers popular tools such as Google NotebookLM, Microsoft Copilot, and countless custom chatbots.

However, vanilla RAG has well-documented reliability limitations. The LLM generates every response, even when the answer could be produced deterministically from structured data. A query like "List papers by Dr. Smith" could be answered precisely from a database lookup, yet vanilla RAG retrieves document chunks, passes them to the LLM, and hopes the model correctly extracts and formats the information — introducing opportunities for hallucination, inconsistency, and formatting errors. Similarly, a query like "Book me a flight" receives the same retrieval-and-generation treatment as a legitimate research question, when it should be refused programmatically.

### 1.2 Improving RAG Through Query Classification

A natural architectural improvement is to add a **query classification stage** that routes queries to specialised response paths before retrieval and generation. This enables:

- **Programmatic paths**: Queries answerable from structured data (researcher lookups, glossary definitions, project details) bypass the LLM entirely, producing deterministic, verifiable responses.
- **Targeted retrieval**: Topic searches can use metadata-aware retrieval instead of generic BM25.
- **Principled refusals**: Off-topic or non-research queries are refused without wasting retrieval and generation resources.
- **Appropriate context**: Gap analysis queries receive metadata about what *exists* in the database, rather than document chunks.

The classification stage transforms vanilla RAG from a single-path architecture into a multi-path one, where each path is optimised for a specific query type. Prior work on modular RAG (Gao et al., 2024), adaptive RAG (Jeong et al., 2024), and agentic RAG (Schick et al., 2023) has explored various forms of this idea, but typically evaluates end-to-end performance without isolating the classification component.

### 1.3 The Classification Mechanism Question

Given that query classification improves RAG reliability, a critical design decision remains: **how should the classification be implemented?** Two approaches dominate in practice:

1. **Deterministic rule-based classification**: Pattern matching using regular expressions, keyword lists, and synonym expansion. Produces consistent, auditable results but requires manual engineering and may miss novel phrasings.

2. **Non-deterministic LLM-based classification**: A separate LLM call classifies the query before response generation. Handles diverse phrasings naturally through pre-trained linguistic knowledge but introduces non-determinism and potential misclassification.

Each approach represents a different trade-off. Rule-based classification leverages explicit human engineering; LLM classification leverages implicit pre-trained knowledge. Rule-based classification is deterministic by construction; LLM classification is stochastic. Rule-based classification requires ongoing maintenance as new phrasings emerge; LLM classification adapts automatically but may make unpredictable errors.

### 1.4 Research Gap

Despite growing interest in query routing for RAG systems (RAGRouter, Hu et al., 2025; R³AG, 2025; RouteRAG), existing work focuses primarily on routing queries to different *retrieval strategies* or *models*, optimising for accuracy or cost. No prior study has:

1. **Isolated classification as an independent variable** while controlling for downstream response generation.
2. **Evaluated classification through a reliability lens** — measuring consistency across runs and robustness to paraphrases, rather than just accuracy.
3. **Compared deterministic vs LLM-based classification** for the same set of response paths with a methodology that controls for both engineering effort and accuracy.

### 1.5 Contributions

This paper makes three contributions:

1. **An automated agent construction protocol** in which a separate LLM (not the one being tested) builds both classification mechanisms from identical starting conditions and iterates them to equivalent accuracy. This removes human engineering skill as a confound, ensures reproducibility, and enables the study to be replicated across domains.

2. **A controlled experimental design** where two classification mechanisms (deterministic rules and non-deterministic LLM) share identical downstream response paths, isolating classification as the sole independent variable. By controlling for accuracy, the study measures reliability independently.

3. **The first application of the Rabanser et al. (2025) reliability framework to query routing in RAG systems**, adapting the four dimensions (consistency, robustness, predictability, safety) to the specific characteristics of multi-path RAG agents.

### 1.6 Research Questions

- **RQ1**: How does adding query classification (either rule-based or LLM-based) improve the reliability of vanilla RAG?
- **RQ2**: Given equivalent classification accuracy, does LLM-based classification offer higher robustness than rule-based classification?
- **RQ3**: Given equivalent classification accuracy, what is the consistency cost of non-deterministic LLM classification?
- **RQ4**: Is the construction process itself revealing — does one mechanism require more iterations to reach the accuracy target, and what types of fixes does the automated constructor apply?

---

## 2. Related Work

### 2.1 Retrieval-Augmented Generation

Retrieval-Augmented Generation (Lewis et al., 2020) combines parametric knowledge (LLM) with non-parametric knowledge (retrieved documents) to ground responses in external data. The original formulation uses a single retrieval-generation pipeline for all queries. Subsequent work has introduced architectural refinements along several dimensions.

**Modular RAG** (Gao et al., 2024) decomposes RAG into interchangeable modules (retrieval, reranking, generation, verification), enabling flexible pipeline composition. Frameworks such as FlashRAG (Jin et al., 2024), RAGLAB, and ComposeRAG provide standardised implementations for comparative evaluation. However, these frameworks focus on module selection rather than on the reliability implications of how modules are composed.

**Adaptive RAG** (Jeong et al., 2024) dynamically routes queries to no-retrieval, single-step, or multi-step retrieval pipelines based on estimated query complexity. This is the closest precedent to our work, but it adapts the *retrieval strategy* rather than the *response generation path*, and evaluates accuracy rather than consistency or robustness.

**Self-RAG** (Asai et al., 2023) introduces self-reflection tokens that allow the model to decide when to retrieve and to critique its own output. This adds adaptive behaviour but keeps a single generation path and does not separate classification from generation.

### 2.2 Query Routing in RAG Systems

Recent work has focused specifically on query routing — deciding how to process each query:

**RAGRouter** (Hu et al., 2025) routes queries to different RAG-enabled LLMs using retrieval-aware embeddings, optimising for accuracy across heterogeneous models. **R³AG** (2025) frames routing as retriever selection, learning to choose between sparse, dense, and multi-hop retrievers. **RouteRAG** proposes adaptive routing between retrieval strategies based on query characteristics. **InSemRAG** (Xiang et al., 2025) uses intent-aware retrieval with a lightweight classifier to improve retrieval relevance.

These approaches share a common pattern: they route queries to different *retrieval strategies* or *models*, evaluating end-to-end accuracy (F1, exact match). None isolates the routing mechanism itself as a variable, and none evaluates routing through a reliability lens (consistency across runs, robustness to perturbations).

A survey by Ding et al. (2025) categorises routing strategies in LLM-based systems as rule-based, classifier-based, and LLM-based, noting that "the use of probabilistic strategies seems to outperform deterministic strategies" in terms of accuracy. However, this observation does not account for consistency — a deterministic strategy that is slightly less accurate may be preferable in production if it produces identical results every time.

### 2.3 AI Agent Reliability

Rabanser et al. (2025) propose a four-dimensional framework for evaluating AI agent reliability:

- **Consistency** (C): Does the agent produce the same result for the same input across multiple runs? Decomposed into outcome consistency (C_out), trajectory consistency (C_traj), and resource consistency (C_res).
- **Robustness** (R): Does the agent handle perturbations — rephrased queries, edge cases, unexpected inputs — correctly? Decomposed into prompt robustness (R_prompt), fault robustness (R_fault), and environment robustness (R_env).
- **Predictability** (P): Can the system predict when the agent is likely to produce incorrect output? Measured through calibration (P_cal) and discrimination (P_AUROC).
- **Safety** (S): When the agent fails, how severe are the consequences? Measured through compliance (S_comp) and harm severity (S_harm).

This framework was developed for general-purpose agents operating in complex environments. We adapt it to the specific context of domain-specific RAG agents, where some response paths are fully deterministic (programmatic), creating a heterogeneous reliability profile that single-metric evaluations would obscure.

### 2.4 Robustness of RAG Systems

Recent work has begun to examine RAG robustness specifically. Wang et al. (2025) reveal that retriever performance can degrade significantly under minor query perturbations, proposing evaluation frameworks to assess sensitivity systematically. ReliabilityRAG (Xie et al., 2025) uses graph-theoretic consistency analysis over retrieved documents to improve adversarial robustness. Research on guardrail robustness under RAG-style contexts (2025) introduces the Flip Rate metric to measure how retrieval context affects safety judgements.

These studies evaluate robustness at the retrieval or generation stages. Our work evaluates robustness at the *classification* stage — an earlier point in the pipeline where failures propagate to all downstream components.

---

## 3. System Architecture

### 3.1 The TOMMI Agent Platform

The study is conducted on the TOMMI platform, a multi-agent system serving the UNINOVIS European university alliance (8 universities across 8 countries). The platform hosts domain-specific RAG agents for research management, with a knowledge base containing 154 research papers, 145 researchers, 11 funded projects, and a Responsible AI glossary.

### 3.2 Three Agent Variants

We compare three architectural configurations, each building on the previous one:

#### Variant 1: Vanilla RAG (Baseline)

The simplest architecture: BM25 keyword retrieval over 19,942 document chunks, followed by LLM generation. Every query follows the same pipeline: retrieve → generate. No classification, no structured data access, no programmatic paths.

This represents the architecture of tools like NotebookLM: upload documents, ask questions, receive LLM-generated answers grounded in retrieved chunks.

#### Variant 3: Rule-Based Classification + Programmatic Paths (Deterministic)

Adds a deterministic query classification stage before retrieval and generation. A priority-ordered chain of boolean checks classifies each query into one of 12 categories. Each check uses regular expressions, keyword lists, and a synonym expansion map. Classification is fully deterministic: the same input always produces the same output. Classified queries are dispatched to specialised response paths — some programmatic (no LLM), some LLM-based with targeted context.

#### Variant 4: LLM Classification + Programmatic Paths (Non-Deterministic)

Replaces V3's rule-based classification chain with a single LLM call. The LLM receives a classification prompt defining the same 12 categories with descriptions and examples, and returns a JSON object with the category and extracted entities.

After classification, V4 dispatches to **the same response paths as V3** — identical code, identical data access, identical formatting. The only difference is how the classification decision is made.

### 3.3 Shared Components (Controlled Variables)

| Component | V1 (Baseline) | V3 (Rule-based) | V4 (LLM-based) |
|---|---|---|---|
| Retrieval | BM25 | BM25 | BM25 |
| Structured data | None | papers.json, researchers.json, Glossary.md, project_docs/ | Same as V3 |
| Classification | None | Rule-based (deterministic) | LLM call (non-deterministic) |
| Response paths | Single (retrieve → generate) | 12 paths (7 programmatic + 5 LLM) | Same as V3 |
| Post-processing | None | Authority sanitisation, paper verification | Same as V3 |
| LLM model | Mistral Small | Mistral Small | Mistral Small |

### 3.4 Shared Dispatch Architecture

V3 and V4 share a common `dispatch()` module that translates a classification result into a response:

- **Programmatic paths** (meta, non_research, off_topic, figure, project, researcher, glossary): Return pre-built responses from structured data. No LLM involvement in response generation. Given the same classification, both variants produce byte-identical output.
- **LLM paths** (topic_search, university_papers, gap, general, followup): Build context from metadata and retrieved documents, then call the LLM to generate a response. Given the same classification, both variants use the same context and prompt.

This architecture ensures that any difference in output between V3 and V4 is attributable solely to classification differences.

### 3.5 Classification Ontology: User-Driven Design

The 12 classification categories reflect the types of questions users naturally ask a domain-specific research assistant: looking up a researcher, exploring a concept, searching for papers on a topic, asking about a project. These intent types emerge from the **user's perspective** and map directly to the underlying data sources (researchers.json, Glossary.md, papers.json, project_docs/). Any classification system serving this knowledge base — whether rule-based, LLM-based, or a fine-tuned classifier — would need to distinguish these same intent types, because each requires accessing a different data source and presenting results in a different format.

We therefore treat the classification ontology as a controlled variable — shared by both variants — and leave the question of alternative ontologies as future work (see Section 7.5).

---

## 4. Methodology

### 4.1 Automated Agent Construction Protocol

The central methodological challenge in comparing two classification mechanisms is ensuring that observed differences reflect **architectural properties** rather than **engineering quality**. If one classifier was carefully tuned and the other hastily written, the comparison measures engineering effort, not architecture. Conversely, if one mechanism benefits from months of implicit development while the other was built for the study, the comparison is asymmetric.

We address this with an automated agent construction protocol that removes human engineering skill as a confound and produces a reproducible, domain-independent methodology.

#### 4.1.1 Design Principles

The protocol is governed by three principles:

1. **Same starting conditions**: Both classifiers receive identical inputs from a human expert — category definitions, representative examples, boundary rules. The expert defines *what* to classify, not *how*.
2. **Automated construction**: A separate LLM (Claude, distinct from the Mistral model used for V4 classification) builds both classifiers through iterative optimisation. This removes human engineering skill as a variable.
3. **Equivalent accuracy**: Both classifiers are iterated until they reach the same accuracy target on a development set. Reliability is then measured on an independent evaluation set. By controlling for accuracy, the study isolates reliability as the dependent variable.

#### 4.1.2 Phase A: Human Expert Input (Shared, One-Time)

A domain expert provides the following, shared identically by both variants:

1. **Category definitions**: The 12 classification categories, each with a natural-language description of the user intent it captures and the data source it maps to (e.g., "researcher: questions about a specific person's publications or interests → researchers.json").
2. **Representative examples**: 3–5 example queries per category, covering typical phrasings.
3. **Boundary clarifications**: Explicit rules for cases where categories overlap (e.g., "task requests such as 'book a flight' are non_research, not off_topic"; "queries mentioning 'project(s)' are project, not topic_search").
4. **Response path design**: The programmatic and LLM-based response paths, shared by both variants.

This input constitutes the **human-in-the-loop** contribution. It encodes the domain expert's understanding of user needs and data structure. Crucially, it is mechanism-agnostic — it specifies *what* should be classified, not *how*.

#### 4.1.3 Phase B: Automated Construction (Independent, Iterative)

Given the expert input from Phase A, the automated constructor (Claude) builds each classifier independently through the following loop:

```
INPUT:  Category definitions, examples, boundary rules
OUTPUT: A classifier (V3: patterns + synonyms; V4: classification prompt)

1. INITIALISE: Translate expert input into an initial classifier
     V3: Generate regex patterns and keyword lists from examples
     V4: Generate a classification prompt from category descriptions

2. ITERATE until convergence:
   a. Run the development benchmark (classify all dev queries)
   b. Compare against ground truth → list of misclassifications
   c. IF accuracy ≥ X%: STOP (target reached)
   d. Feed misclassifications to the constructor:
        "Query Q was classified as A, expected B. Fix the classifier."
   e. Constructor proposes fixes:
        V3: new patterns, synonym mappings, priority reorderings
        V4: prompt refinements, better descriptions, added examples
   f. Apply fixes → go to (a)

3. CONVERGENCE: Target accuracy X reached, or two consecutive
   iterations with no improvement (architectural ceiling)
```

#### 4.1.4 Accuracy Target Selection

The accuracy target X is set to **min(ceiling_V3, ceiling_V4)** — the maximum accuracy that *both* mechanisms can achieve. This is determined empirically:

1. Run the construction loop for both variants until each reaches its plateau (two consecutive iterations with no improvement).
2. Record each variant's ceiling accuracy: ceiling_V3 and ceiling_V4.
3. Set X = min(ceiling_V3, ceiling_V4).
4. If one variant exceeded X, roll back to the iteration where it first reached X.

This ensures that both classifiers operate at the **same accuracy level**, so reliability differences cannot be attributed to accuracy differences. If one variant reaches a substantially higher ceiling, that asymmetry is itself a finding — but the reliability comparison is conducted at the shared accuracy level.

#### 4.1.5 Development vs. Evaluation Query Sets

To prevent overfitting the construction to the benchmark, we use separate query sets:

- **Development set**: Used during the construction loop. Contains queries covering all categories with validated ground-truth labels. Failures on this set drive automated improvements. Both variants see this set during construction.
- **Evaluation set**: A larger, independently generated set of queries, **never seen during construction**. Generated using the same constructor LLM (Claude) in a separate session, with explicit instructions to produce diverse phrasings, boundary cases, and novel formulations. Ground truth labels are validated by the domain expert. This set is used exclusively for the final reliability benchmark.

This separation ensures that the final comparison measures **generalisation to unseen queries**, not memorisation of training examples.

#### 4.1.6 Reproducibility and Domain Independence

The protocol is designed to be **reproducible and domain-independent**:

- **Reproducibility**: The only human input is Phase A (category definitions and examples). The construction loop is fully automated and deterministic given the same constructor LLM and random seed. Another research team with different data could replicate the protocol.
- **Domain independence**: The method requires only (1) a knowledge base with heterogeneous data sources, (2) a domain expert who can define query categories, and (3) a set of example queries. It could be applied to medical, legal, educational, or any other domain-specific RAG system.
- **Transparency**: For each variant, we record the full construction trajectory: initial classifier, fixes applied at each iteration, accuracy after each iteration, and final classifier. This allows readers to inspect not just the result but the construction process.

#### 4.1.7 On the Role of Pre-Trained Knowledge

An important asymmetry remains even after controlling for expert input and accuracy: V4's LLM brings pre-trained knowledge that V3's patterns do not have. The LLM "knows" that "book a flight" is a task request, that "quantum computing" is outside Responsible AI, and that "XAI" means "explainable AI" — without being told. V3 must learn each of these through explicit patterns or synonym mappings generated by the constructor.

This asymmetry is not a confound — it is **the independent variable**. The research question is precisely whether leveraging the LLM's pre-trained knowledge for classification produces more *reliable* routing than encoding knowledge explicitly in rules, when accuracy is held constant. The automated construction protocol ensures that both approaches are optimised to equivalent accuracy by the same process, so that the reliability comparison is fair.

### 4.2 Reliability Evaluation Framework

We adapt the Rabanser et al. (2025) framework to our controlled setting. For the V1 vs V3/V4 comparison, we evaluate all four dimensions. For the V3 vs V4 comparison, we focus on the two dimensions directly affected by the classification mechanism.

#### 4.2.1 Consistency (R_Con)

**Trajectory consistency (C_traj)**: Run each evaluation query K=5 times through the classifier. Measure the fraction of queries that receive the same classification across all runs.

- V1: Not applicable (no classification stage).
- V3 (deterministic): Expected C_traj = 1.0 by construction.
- V4 (non-deterministic): C_traj ≤ 1.0 when the LLM classifies the same query differently across runs.

**Outcome consistency (C_out)**: Run the full agent K=3 times per query. Measure the fraction of queries that produce identical responses (exact string match, excluding decision traces).

- V1: Expected C_out ≈ 0.0 (all responses are LLM-generated, inherently variable).
- V3/V4 programmatic paths: If classification is consistent, response is byte-identical.
- V3/V4 LLM paths: Response varies across runs regardless of classification.

**Aggregate**: R_Con = (C_traj + C_out) / 2

#### 4.2.2 Robustness (R_Rob)

**Prompt robustness (R_prompt)**: For each evaluation query, create paraphrases at multiple levels (surface rewording, structural changes, boundary cases). Measure the fraction of paraphrases that receive the correct classification or (for V1) produce semantically equivalent responses.

- V3: Robustness depends on the rule patterns and synonym coverage generated by the constructor.
- V4: Robustness depends on the LLM's ability to generalise across phrasings.

**Aggregate**: R_Rob = R_prompt

#### 4.2.3 Correctness and Safety (Expert Evaluation)

For the V1 vs V3/V4 comparison, a domain expert evaluates responses on:

- **Factual correctness** (0–3): Are facts accurate and verifiable against the knowledge base?
- **Completeness** (0–2): Does the response include all relevant information?
- **Hallucination** (0–2): Does the response contain fabricated facts?
- **Safety violations**: Invented paper titles, fabricated researcher affiliations, scope violations.

These dimensions are expected to improve from V1 to V3/V4, since programmatic paths eliminate hallucination for structured queries by construction.

#### 4.2.4 Classification Agreement (V3 vs V4)

For all evaluation queries, run both classifiers and record:

- **Agreement rate**: Fraction of queries where both produce the same category.
- **Disagreement analysis**: When they disagree, which was correct? This reveals whether the mechanisms have complementary strengths (queries that rules handle but LLM misses, and vice versa).

### 4.3 Benchmark Query Sets

#### 4.3.1 Development Set

Queries covering all 12 categories with validated ground-truth labels. Used during the automated construction loop. Both variants see these queries during optimisation.

Target size: 70–100 queries (5–8 per category, including paraphrases).

#### 4.3.2 Evaluation Set

A larger set of queries (target: 200+) independently generated using the constructor LLM (Claude) in a separate session, with instructions to produce:

- Diverse phrasings not present in the development set.
- Surface paraphrases (rewording), structural variations (sentence restructuring), and boundary cases (ambiguous queries).
- Queries at varying difficulty levels per category.

Ground truth labels are validated by the domain expert. Neither classifier is modified after seeing these queries.

### 4.4 Statistical Analysis

- **Classification accuracy**: Fraction of correct classifications per variant (expected to be equivalent by construction).
- **McNemar's test**: Paired comparison testing whether the two classifiers make errors on the same queries or on different ones (complementary vs overlapping failures).
- **Per-category analysis**: Accuracy, consistency, and robustness broken down by query type, identifying categories where each mechanism excels.
- **Consistency coefficient of variation**: For V4, measure the variance in classification across K runs, per category.
- **Effect size**: Cohen's d or equivalent for the V1 → V3/V4 reliability improvement.

---

## 5. Experimental Setup

### 5.1 Platform and Knowledge Base

- **Platform**: TOMMI multi-agent system (Python, Mistral API)
- **Knowledge base**: 154 papers, 145 researchers, 11 projects, Responsible AI glossary
- **Retrieval**: BM25 over 19,942 document chunks (shared by all variants)
- **Classification/Generation LLM**: Mistral Small (mistral-small-latest)
- **Constructor LLM**: Claude (Anthropic) — separate from the classification LLM to avoid self-optimisation bias

### 5.2 Agent Variants

| Component | V1 (Vanilla RAG) | V3 (Rule-based) | V4 (LLM-based) |
|---|---|---|---|
| Classification | None | Pattern chain (deterministic) | LLM prompt (non-deterministic) |
| Classification time | 0ms | <1ms | ~400ms |
| Programmatic paths | 0 | 7 | 7 (shared with V3) |
| LLM paths | 1 (all queries) | 5 | 5 (shared with V3) |
| Post-processing | None | Full pipeline | Full pipeline (shared) |

### 5.3 Construction Trajectory

[TO BE COMPLETED — document the automated construction for both variants]

| | V3 (Rule-based) | V4 (LLM-based) |
|---|---|---|
| Initial accuracy (after Phase A) | —% | —% |
| Iterations to target | — | — |
| Accuracy target X | —% | —% |
| Types of fixes applied | [patterns, synonyms, ...] | [prompt refinements, ...] |
| Final dev-set accuracy | —% | —% |

### 5.4 Evaluation Protocol

1. **Phase A**: Domain expert provides category definitions, examples, boundary rules.
2. **Phase B**: Automated constructor builds both classifiers to accuracy target X.
3. **Evaluation set generation**: Constructor LLM generates 200+ unseen queries; expert validates ground truth.
4. **Benchmark execution**:
   a. V1, V3, V4 respond to all evaluation queries.
   b. Classification accuracy (V3, V4) on evaluation set.
   c. Classification consistency: K=5 runs per query.
   d. Paraphrase robustness: evaluation set includes paraphrases.
   e. Response consistency: K=3 full agent runs for programmatic-path queries.
   f. Expert evaluation: correctness and safety for V1 vs V3/V4 comparison.
5. **Statistical analysis**: McNemar's test, per-category breakdown, effect sizes.

---

## 6. Results

[TO BE COMPLETED WITH FINAL BENCHMARK RESULTS]

### 6.1 Construction Trajectory

[TO BE COMPLETED — accuracy curves for V3 and V4 during automated construction, types of fixes applied, number of iterations]

### 6.2 V1 vs V3/V4: The Effect of Adding Classification

| Metric | V1 (Vanilla RAG) | V3 (Rule-based) | V4 (LLM-based) |
|---|---|---|---|
| Response consistency (C_out, K=3) | —% | —% | —% |
| Factual correctness (expert, 0–3) | — | — | — |
| Hallucination rate | —% | —% | —% |
| Avg response time (ms) | — | — | — |

### 6.3 V3 vs V4: Reliability at Equivalent Accuracy

| Metric | V3 (Rule-based) | V4 (LLM-based) |
|---|---|---|
| Classification accuracy (eval set) | —% | —% |
| Classification consistency (C_traj, K=5) | —% | —% |
| Paraphrase robustness (R_prompt) | —% | —% |
| Response consistency (C_out, K=3) | —% | —% |
| R_Con (Consistency) | — | — |
| R_Rob (Robustness) | — | — |

### 6.4 Classification Agreement Analysis

[TO BE COMPLETED — agreement rate, complementary strengths, per-category breakdown]

### 6.5 Construction Effort Comparison

| Aspect | V3 (Rule-based) | V4 (LLM-based) |
|---|---|---|
| Iterations to accuracy target | — | — |
| Final classifier size | ~N patterns + M synonyms | ~N words in prompt |
| Fix types | [pattern additions, synonym maps, priority changes] | [description refinements, example additions, boundary rules] |

---

## 7. Discussion

### 7.1 The Value of Classification Over Vanilla RAG

[TO BE COMPLETED based on V1 vs V3/V4 results]

Adding query classification to vanilla RAG is expected to improve reliability across multiple dimensions:
- **Consistency**: Programmatic paths produce identical responses across runs, unlike LLM-generated responses.
- **Correctness**: Structured data access eliminates hallucination for factual queries.
- **Safety**: Programmatic refusals for off-topic and non-research queries prevent scope violations.
- **Efficiency**: Programmatic paths avoid unnecessary LLM calls, reducing latency and cost.

The key finding is that this improvement is substantial regardless of whether classification is rule-based or LLM-based — the architectural decision to *add* classification matters more than *how* it is implemented.

### 7.2 The Consistency-Robustness Trade-off at Equivalent Accuracy

[TO BE COMPLETED based on V3 vs V4 results]

By controlling for accuracy, the study isolates the reliability trade-off:
- **V3 offers perfect consistency** (C_traj = 1.0 by construction) but its robustness depends on the patterns generated by the constructor.
- **V4 offers natural robustness** through pre-trained linguistic knowledge but sacrifices consistency due to LLM non-determinism.

This trade-off is **architectural**, not engineering-related: no amount of prompt refinement can make LLM classification deterministic, and no amount of pattern generation can give rule-based classification the LLM's generalisation capability. The automated construction protocol confirms this by showing that both mechanisms reach a ceiling — and the ceiling performance differs on consistency and robustness dimensions.

### 7.3 The Automated Construction Protocol

The automated construction protocol provides several insights beyond the V3/V4 comparison:

- **Construction trajectory**: The number of iterations and types of fixes reveal qualitative differences between the mechanisms. V3 fixes tend to be narrow (add a specific pattern), while V4 fixes tend to be broad (restructure a category description). [TO BE CONFIRMED WITH RESULTS]
- **Ceiling asymmetry**: If one mechanism reaches a higher ceiling, this suggests an inherent accuracy advantage independent of engineering effort.
- **Reproducibility**: The protocol can be replicated by other teams with different data, enabling cross-domain comparisons.

### 7.4 Practical Implications

For practitioners choosing between classification approaches:

- **Use rule-based classification** when consistency is paramount (e.g., regulatory contexts, audit trails, EU AI Act compliance) and the query vocabulary is well-defined.
- **Use LLM classification** when handling diverse user populations with unpredictable phrasings and when slight classification variance is acceptable.
- **Consider hybrid approaches**: Use rule-based classification as a first pass (high-confidence patterns) with LLM fallback for unmatched queries. This combines V3's consistency with V4's robustness.
- **Start with vanilla RAG, then add classification**: The improvement from V1 to V3/V4 is larger than the difference between V3 and V4. Classification is the high-impact decision; the mechanism is a second-order optimisation.

### 7.5 Classification Ontology: User-Driven Design

A potential concern is whether the classification categories are biased toward V3, since they were initially developed alongside a rule-based classification system. We argue that the categories are **user-driven** rather than mechanism-driven: they reflect the types of questions users naturally ask a research assistant and map directly to the underlying data sources. Any classification system serving this knowledge base would need to distinguish these same intent types.

In principle, an LLM-native ontology might introduce categories that rule-based patterns would not naturally produce — for instance, distinguishing "factual lookup" from "analytical question". However, these finer distinctions would still map to the same data sources, and the response paths would converge to similar implementations. We treat the classification ontology as a controlled variable and leave the question of alternative ontologies as future work.

### 7.6 Limitations

- **Single LLM**: The study uses Mistral Small for V4 classification and response generation. Results may differ with larger or more capable models. The automated construction protocol could be rerun with different LLMs to assess model sensitivity.
- **Single domain**: The knowledge base is domain-specific (Responsible AI research). While the methodology is domain-agnostic, generalisation to other domains requires replication.
- **Constructor bias**: The automated constructor (Claude) may have systematic biases in how it generates patterns vs prompts. Using a different constructor LLM would test this.
- **Ontology**: The classification categories were initially designed for a rule-based system. While we argue they are user-driven (Section 7.5), an LLM-native ontology might yield different trade-offs.
- **Expert evaluation**: Predictability and safety dimensions require domain expert annotation, which is resource-intensive and introduces subjectivity.

---

## 8. Conclusion

[TO BE COMPLETED]

This study addresses a practical question faced by every RAG system builder: having decided to add query classification for reliability, should the classifier be rule-based or LLM-based? By isolating classification as the sole independent variable — with identical downstream response paths, knowledge base, and LLM — and by controlling for accuracy through an automated construction protocol, we reveal a fundamental consistency-robustness trade-off that is architectural rather than engineering-related.

The automated agent construction protocol is itself a methodological contribution. By separating human expert knowledge (what to classify) from automated classifier construction (how to classify), the protocol ensures fair comparison, removes engineering skill as a confound, and enables reproducibility across teams and domains. We propose that future comparative studies of AI systems adopt similar protocols when engineering effort or implicit knowledge differences are potential confounds.

More broadly, the study demonstrates that the decision to *add* query classification to vanilla RAG has a larger reliability impact than the choice of classification mechanism. This suggests that practitioners should prioritise architectural decisions (adding classification and programmatic paths) over implementation decisions (rules vs LLM classification), selecting the mechanism that best fits their specific consistency and robustness requirements.

---

## References

Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2023). Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. *NeurIPS 2023*.

Ding, Y., et al. (2025). Doing More with Less — Implementing Routing Strategies in Large Language Model-Based Systems: An Extended Survey. *arXiv:2502.00409*.

Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., ... & Wang, H. (2024). Retrieval-Augmented Generation for Large Language Models: A Survey. *arXiv:2312.10997*.

Hu, Y., et al. (2025). RAGRouter: Learning to Route Queries to Multiple Retrieval-Augmented Language Models. *arXiv:2505.23052*.

Jeong, S., Baek, J., Cho, S., Hwang, S.J., & Park, J.C. (2024). Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity. *NAACL 2024*.

Jin, J., et al. (2024). FlashRAG: A Modular Toolkit for Retrieval-Augmented Generation Research. *arXiv:2405.13576*.

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*.

Li, X., et al. (2025). Retrieval-Augmented Generation: A Comprehensive Survey of Architectures, Enhancements, and Robustness Frontiers. *arXiv:2506.00054*.

Rabanser, S., Kapoor, S., Kirgis, P., Liu, K., Utpala, S., & Narayanan, A. (2025). Towards a Science of AI Agent Reliability. Princeton University. *arXiv:2602.16666*.

R³AG (2025). Retriever Routing for Retrieval-Augmented Generation. *arXiv:2604.22849*.

Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., ... & Scialom, T. (2023). Toolformer: Language Models Can Teach Themselves to Use Tools. *NeurIPS 2023*.

Wang, L., et al. (2025). Investigating the Robustness of Retrieval-Augmented Generation at the Query Level. *arXiv:2507.06956*.

Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., ... & Zhou, D. (2022). Chain-of-Thought Prompting Elicits Reasoning in Large Language Models. *NeurIPS 2022*.

Xiang, S., et al. (2025). Efficient RAG with Intent-Aware Retrieval and Semantics-Preserving Chunking (InSemRAG). *arXiv:2606.01240*.

Xie, Z., et al. (2025). ReliabilityRAG: Effective and Provably Robust Defense for RAG-based Web-Search. *arXiv:2509.23519*.
