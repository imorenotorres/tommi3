# Reliability of Query Classification in RAG Agents: A Controlled Comparison of Rule-Based and LLM-Based Approaches

## Abstract

Domain-specific AI assistants built on Retrieval-Augmented Generation (RAG) are increasingly deployed in contexts that demand high reliability such as education,or healthcare information. A key architectural improvement is adding intent classification to route queries to specialized response paths. There are different intent classification mechanisms (deterministic rule-based, LLM based, etc.) Theoretically, rule based classification should offer higher consistency and safety, while LLM-based classification should offer higher robustness. However, no prior study has compared the reliability of different query classification approaches in RAG systems. We present a controlled study that isolates classification as the sole independent variable and evaluate reliability using the four-dimensional framework of Rabanser et al. (2025): consistency, robustness, predictability, and safety. Three intent classification approaches are compared: 1) a human developed rule-based classifier developed over months of reactive engineering (HRBC), 2) a rule-based classifier developed automatically; and 3) an LLM classifier developed automatically (ALLMC).

Results on 216 unseen queries across three difficulty tiers challenge the theoretical expectations: while rule-based classification achieves perfect classification consistency, accuracy varies dramatically depending on the construction process --- a production rule-based classifier developed over months of reactive engineering (44.0%) scores far below an auto-constructed variant using broad word-class patterns (75.5%). Both fall short of LLM-based classification (87.8% ± 0.4%). LLM-based classification achieves higher scores on all four reliability dimensions simultaneously. We conclude that response consistency is a function of classification accuracy rather than determinism, and that LLM-based classification --- with its superior accuracy and robustness on unseen queries --- is the more reliable choice overall.

## 1. Introduction

### 1.1 Reliability in Domain-Specific AI Assistants

Retrieval-Augmented Generation (Lewis et al., 2020) has become the standard architecture for domain-specific AI assistants. RAG agents are deployed in educational platforms, research management systems, healthcare information tools, and legal analysis --- domains where users rely on the agent's responses for consequential decisions. Education is of particular concern: the EU AI Act (Regulation (EU) 2024/1689) explicitly classifies AI systems used in education as **high-risk** (Annex III, Section 3), noting that such systems "may determine the educational and professional course of a person's life" and, when improperly designed, "can be particularly intrusive and may violate the right to education and training" (European Parliament & Council, 2024). Thus, in this context, reliability is not a desirable feature but a prerequisite.

Despite their growing deployment, the reliability of RAG agents has received surprisingly little systematic attention. Existing evaluations focus primarily on accuracy metrics --- correctness, hallucination rate, F1 scores --- measured in single-run settings. These metrics capture whether the agent *can* produce a correct response, but not whether it *reliably* does so: the same query asked twice may produce different responses, a rephrased question may be misrouted, and the system may confidently generate responses on topics it should refuse.

Rabanser et al. (2025) have recently propose a four-dimensional framework for AI agent reliability --- consistency, robustness, predictability, and safety --- which was applied it to general-purpose agents. No prior work has adapted this framework to evaluate the specific reliability challenges of domain-specific RAG agents, where some response paths are deterministic (programmatic data lookups) while others depend on LLM generation.

### 1.2 The Role of Query Classification

In vanilla RAG --- where every query follows the same retrieve-then-generate pipeline --- the system cannot distinguish a factual lookup (answerable from structured data) from a speculative question (requiring LLM reasoning), treating both identically. This limits reliability in several ways: the LLM may hallucinate facts that exist in structured data, it may attempt to answer questions outside its scope, and it produces different responses each time.

A natural improvement is to add a **query classification stage** that routes queries to specialized response paths:

- **Programmatic paths**: Queries answerable from structured data (researcher lookups, glossary definitions, project details) bypass the LLM entirely, producing deterministic, verifiable responses with zero hallucination risk.
- **Principled refusals**: Off-topic or non-research queries are refused programmatically, preventing scope violations.
- **Targeted context**: Different query types receive context from the appropriate data source, improving correctness.

This architecture transforms the reliability profile of the agent: programmatic paths are perfectly reliable by construction, while LLM paths retain their inherent variability. The overall reliability depends critically on how well the classification stage routes queries to the correct path. Figure 1 illustrates the architectural difference between vanilla RAG and the classified approach.

  -----------------------------------------------------------------------
   ![](media/image1.png){width="6.1375in" height="1.7506944444444446in"}

  -----------------------------------------------------------------------

  : Figure 1: Architectural configurations compared in this study. The transition from (a) to (b)/(c) adds response paths. The transition from (b) to (c) swaps the classification mechanism --- everything downstream remains identical. Two rule-based variants are tested under (b): a production variant developed over months through reactive feedback, and an auto-constructed variant built in hours through batch feedback. Both are deterministic; they differ in pattern breadth. (Section 3.5)

### 1.3 The Classification Mechanism Question

Given that query classification improves reliability, a critical design decision remains: **how should the classification be implemented?** Two approaches dominate, each with theoretical reliability implications:

**Deterministic rule-based classification** uses pattern matching, keyword lists, and synonym expansion. Theoretically, it should offer:

\- **Higher consistency**: the same query always produces the same classification (deterministic by construction).

\- **Higher safety**: decision logic is auditable, and refusal patterns can be verified exhaustively.

\- **Lower robustness**: patterns only cover anticipated phrasings; novel formulations may be misrouted.

**Non-deterministic LLM-based classification** uses a separate LLM call to classify the query. Theoretically, it should offer:

\- **Higher robustness**: pre-trained linguistic knowledge handles diverse phrasings, paraphrases, and indirect formulations naturally.

\- **Lower consistency**: the same query may be classified differently across runs due to LLM stochasticity.

\- **Less auditable safety**: classification decisions are opaque and cannot be exhaustively verified.

This theoretical framing suggests a **consistency-robustness trade-off** in which practitioners must choose between deterministic safety and flexible coverage. Our study tests whether this trade-off holds in practice.

### 1.4 Research Gap

Despite growing interest in query routing for RAG systems (RAGRouter, Hu et al., 2025; R³AG, Zhao et al., 2026; RouteRAG, Guo et al., 2025), existing work has not examined the reliability implications of the routing mechanism itself. Specifically:

1.  **No prior study has evaluated the reliability of RAG agents** using a multi-dimensional framework. Existing evaluations measure accuracy in single-run settings, overlooking consistency across runs, robustness to paraphrases, and safety of refusal behaviour.

2.  **No prior study has isolated classification as an independent variable** while controlling for downstream response generation. Existing comparisons confound classification differences with response generation differences.

3.  **No prior study has compared deterministic vs LLM-based classification** through a reliability lens, testing whether the theoretical consistency-robustness trade-off holds empirically.

### 1.5 Contributions

This paper makes three contributions:

1.  **The first reliability evaluation of query classification in RAG agents**, using the four-dimensional framework of Rabanser et al. (2025) --- consistency, robustness, predictability, and safety --- adapted to the specific characteristics of domain-specific RAG systems with mixed programmatic and LLM-generated response paths.

2.  **A controlled experimental design** where two classification mechanisms (deterministic rules and non-deterministic LLM) share identical downstream response paths, isolating classification as the sole independent variable. An *automated agent construction protocol* removes human engineering skill as a confound and enables reproducibility.

3.  **An empirical challenge to the theoretical expectations**: we show that deterministic classification does not guarantee higher consistency or safety at the system level, because classification accuracy --- not determinism --- is the primary driver of response reliability.

### 1.6 Research Questions

- **RQ1**: Does adding query classification to vanilla RAG improve reliability across all four Rabanser dimensions?
- **RQ2**: Does LLM-based classification offer higher robustness than rule-based classification, as theoretically expected?
- **RQ3**: Does rule-based classification offer higher consistency and safety than LLM-based classification, as theoretically expected?
- **RQ4**: Is there a fundamental consistency-robustness trade-off, or does one approach dominate across all reliability dimensions?

## 2. Related Work

### 2.1 Retrieval-Augmented Generation

Retrieval-Augmented Generation (Lewis et al., 2020) combines parametric knowledge (LLM) with non-parametric knowledge (retrieved documents) to ground responses in external data. The architecture has been widely adopted for domain-specific applications, yet evaluation of RAG systems has focused almost exclusively on single-run accuracy metrics --- correctness, hallucination rate, and F1 scores (Gao et al., 2024). Multi-run reliability (does the system produce the same answer twice?) and robustness (does it handle rephrased queries?) have not been systematically studied.

### Modular RAG (Gao et al., 2024) decomposes RAG into interchangeable modules, and frameworks such as FlashRAG (Jin et al., 2024) provide standardized implementations for comparative evaluation. Adaptive RAG (Jeong et al., 2024) dynamically routes queries to different retrieval pipelines, and Self-RAG (Asai et al., 2023) adds self-reflection tokens for retrieval decisions. However, these approaches evaluate module performance, not reliability, and none separates classification from generation --- making it impossible to attribute reliability differences to the routing mechanism.

### 2.2 Query Routing in RAG Systems

Recent work on query routing focuses on *where* to route, not on the *reliability* of routing: **RAGRouter** (Hu et al., 2025) routes queries to different RAG-enabled LLMs using retrieval-aware embeddings. **R³AG** (Zhao et al., 2026) frames routing as retriever selection. **RouteRAG** (Guo et al., 2025) proposes adaptive routing between retrieval strategies. **InSemRAG** (Xiang et al., 2025) uses intent-aware retrieval with a lightweight classifier.

These approaches evaluate routing through accuracy metrics (F1, exact match). None measures whether the router produces the same decision across multiple runs (consistency), whether it handles paraphrased queries correctly (robustness), or whether it appropriately refuses out-of-scope queries (safety).

A survey by Ding et al. (2025) categorizes routing strategies as rule-based, classifier-based, and LLM-based, noting that "probabilistic strategies seem to outperform deterministic strategies" in terms of accuracy. However, this finding does not account for consistency or safety --- dimensions that may be critical for high-stakes deployments.

### 2.3 AI Agent Reliability

Rabanser et al. (2025) propose a four-dimensional framework for evaluating AI agent reliability:

- **Consistency** (C): Does the agent produce the same result for the same input across multiple runs? In our version we measure trajectory consistency (C_traj: same classification across runs) and outcome consistency (C_out: same response across runs).
- **Robustness** (R): Does the agent handle perturbations \-\-- rephrased queries, edge cases, unexpected inputs \-\-- correctly? In our version we measure prompt robustness (R_prompt): accuracy across paraphrases at multiple difficulty tiers.
- **Predictability** (P): Can the system predict when the agent is likely to produce correct or incorrect output? In our version we measure whether the classification path (programmatic vs LLM) correlates with actual correctness.
- **Safety** (S): Does the agent refuse queries it should not answer? In our version we measure refusal accuracy (S_comp): the fraction of out-of-scope queries correctly refused.

This framework was developed for general-purpose agents in complex environments. **No prior work has applied it to RAG agents**, despite the growing deployment of RAG systems in domains where reliability is critical. We adapt the framework to the specific characteristics of domain-specific RAG agents with mixed programmatic and LLM-generated response paths.

### 2.4 Robustness of RAG Systems

Recent work has begun to examine RAG robustness at specific pipeline stages. Wang et al. (2025) reveal that retriever performance degrades under minor query perturbations. ReliabilityRAG (Xie et al., 2025) uses graph-theoretic consistency analysis over retrieved documents. Research on guardrail robustness under RAG-style contexts (Yi et al., 2025) introduces the Flip Rate metric for safety judgements.

These studies evaluate robustness at the retrieval or generation stages. Our work evaluates robustness at the *classification* stage --- an earlier point in the pipeline where failures propagate to all downstream components. A misclassified query not only receives the wrong response but may bypass safety guardrails entirely.

## 3. System Architecture

### 3.1 The TOMMI Agent Platform

The study is conducted on the TOMMI platform, a multi-agent system serving the UNINOVIS European university alliance (8 universities across 8 countries). The platform hosts domain-specific RAG agents for research management. The present study used one of the agents, which has a knowledge base related with Responsible AI research. The knowledge base contains 154 research papers, a list of 145 UNINOVIS researchers, 11 funded projects, and a Responsible AI glossary.

### 3.2 Agent Variants

We compare four agent configurations. The **Baseline** establishes what vanilla RAG can do alone. The three classified variants share identical response paths --- the only difference is the classification mechanism:

#### Baseline (Vanilla RAG)

The simplest architecture: BM25 keyword retrieval over 19,942 document chunks, followed by LLM generation. Every query follows the same pipeline: retrieve → generate. No classification, no structured data access, no programmatic paths.

This is the simplest architecture: BM25 keyword retrieval over 19,942 document chunks, followed by LLM generation. Every query follows the same pipeline: retrieve → generate. No classification, no structured data access, no programmatic paths.

#### Production Rule-based (Hand-crafted)

A rule-based classifier developed over several months of real-world production use. It uses \~60 manually designed synonym mappings, accent-insensitive matching, and a 13-step priority-ordered classification chain. Patterns were added reactively as individual failures occurred in production use (see Section 7 for discussion of how this feedback loop affects generalisation).

#### Auto-constructed Rule-based

A rule-based classifier built from scratch by an automated constructor (Claude), given the same expert input as all variants. The constructor generates synonym families (\~35 mappings), broad classification patterns that match word classes rather than specific phrases (e.g., any task verb + any object → non_research), and entity-type detection. This represents what systematic construction produces --- patterns designed to cover classes of queries rather than individual instances.

#### Auto-constructed LLM-based

A single LLM call classifies the query. The LLM receives a classification prompt defining the same 12 categories with descriptions, examples, and boundary rules, and returns a JSON object with the category and extracted entities. Classification is non-deterministic: the same query may occasionally be classified differently across runs.

After classification, all three classified variants dispatch to the same response paths --- identical code, identical data access, identical formatting. The only difference is how the classification decision is made.

### 3.3 Shared Components (Controlled Variables)

  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Component**        **Baseline**    **Production rule-based**                                   **Rule-based (auto)**                                       **LLM-based (auto)**
  -------------------- --------------- ----------------------------------------------------------- ----------------------------------------------------------- -----------------------------------------------------------
  Retrieval            BM25            BM25                                                        BM25                                                        BM25

  Structured data      None            papers.json, researchers.json, Glossary.md, project_docs/   papers.json, researchers.json, Glossary.md, project_docs/   papers.json, researchers.json, Glossary.md, project_docs/

  Classification       None            Hand-crafted patterns (deterministic)                       Auto-built patterns (deterministic)                         LLM call (non-deterministic)

  Response paths       Single          12 paths (7 programmatic + 5 LLM)                           Same                                                        Same

  Post-processing      None            Authority sanitisation, paper verification                  Same                                                        Same

  LLM model            Mistral Small   Mistral Small                                               Mistral Small                                               Mistral Small

  Development effort   Minutes         Months                                                      Hours (automated)                                           Hours (automated)
  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

### 3.4 Shared Dispatch Architecture

All three classified variants share a common `dispatch()` module that translates a classification result into a response:

- **Programmatic paths** (meta, non_research, off_topic, figure, project, researcher, glossary): Return pre-built responses from structured data. No LLM involvement in response generation. Given the same classification, all variants produce byte-identical output.
- **LLM paths** (topic_search, university_papers, gap, general, followup): Build context from metadata and retrieved documents, then call the LLM to generate a response. Given the same classification, all variants use the same context and prompt.

This architecture ensures that any difference in output between variants is attributable solely to classification differences.

## 4. Methodology

### 4.1 Automated Agent Construction Protocol

The central methodological challenge in comparing two classification mechanisms is ensuring that observed differences reflect **architectural properties** rather than **engineering quality**. If one classifier was carefully tuned and the other hastily written, the comparison measures engineering effort, not architecture. Conversely, if one mechanism benefits from months of implicit development while the other was built for the study, the comparison is asymmetric.

We address this with an automated agent construction protocol that removes human engineering skill as a confound and produces a reproducible, domain-independent methodology.

#### 4.1.1 Design Principles

The protocol is governed by three principles:

1.  **Same starting conditions**: Both classifiers receive identical inputs from a human expert --- category definitions, representative examples, boundary rules. The expert defines *what* to classify, not *how*.
2.  **Automated construction**: A separate LLM (Claude, distinct from the Mistral model used for LLM-based classification) builds both classifiers through iterative optimization. This removes human engineering skill as a variable.
3.  **Equivalent accuracy**: Both classifiers are iterated until they reach the same accuracy target on a development set. Reliability is then measured on an independent evaluation set. By controlling for accuracy, the study isolates reliability as the dependent variable.

#### 4.1.2 Phase A: Human Expert Input (Shared, One-Time)

A domain expert provides the following, shared identically by both variants:

1.  **Category definitions**: The 12 classification categories, each with a natural-language description of the user intent it captures and the data source it maps to (e.g., "researcher: questions about a specific person's publications or interests).
2.  **Representative examples**: 3--5 example queries per category, covering typical phrasings.
3.  **Boundary clarifications**: Explicit rules for cases where categories overlap (e.g., "task requests such as 'book a flight' are non_research, not off_topic"; "queries mentioning 'project(s)' are project, not topic_search").
4.  **Response path design**: The programmatic and LLM-based response paths, shared by both variants.

This input constitutes the **human-in-the-loop** contribution. It encodes the domain expert's understanding of user needs and data structure. Crucially, it is mechanism-agnostic --- it specifies *what* should be classified, not *how*.

#### 4.1.3 Phase B: Automated Construction (Independent, Iterative)

Given the expert input from Phase A, the automated constructor (Claude) builds each classifier independently through the following loop:

    INPUT:  Category definitions, examples, boundary rules, Development set
    OUTPUT: A classifier (Rule-based: patterns + synonyms; LLM-based: classification prompt)

    1. INITIALISE: Translate expert input into an initial classifier
         Rule-based: Generate regex patterns and keyword lists from examples
         LLM-based: Generate a classification prompt from category descriptions

    2. ITERATE until convergence:
       a. Run the development benchmark (classify all training queries)
       b. Compare against ground truth → list of misclassifications
       c. IF accuracy ≥ X%: STOP (target reached)
       d. Feed misclassifications to the constructor:
            "Query Q was classified as A, expected B. Fix the classifier."
       e. Constructor proposes fixes:
            Rule-based: new patterns, synonym mappings, priority re-orderings
            LLM-based: prompt refinements, better descriptions, added examples
       f. Apply fixes → go to (a)

    3. CONVERGENCE: Target accuracy X reached, or two consecutive
       iterations with no improvement (architectural ceiling)

#### 4.1.4 Accuracy Target Selection

The accuracy target X is set to **min(ceiling_rule, ceiling_llm)** --- the maximum accuracy that *both* mechanisms can achieve. This is determined empirically:

1.  Run the construction loop for both variants until each reaches its plateau (two consecutive iterations with no improvement).
2.  Record each variant's ceiling accuracy: ceiling_rule and ceiling_llm.
3.  Set X = min(ceiling_rule, ceiling_llm).
4.  If one variant exceeded X, roll back to the iteration where it first reached X.

This ensures that both classifiers operate at the **same accuracy level**, so reliability differences cannot be attributed to accuracy differences. If one variant reaches a substantially higher ceiling, that asymmetry is itself a finding --- but the reliability comparison is conducted at the shared accuracy level.

#### 4.1.5 Development vs. Evaluation Query Sets

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

An important asymmetry remains even after controlling for expert input and accuracy: the LLM-based variant's LLM brings pre-trained knowledge that the Rule-based variant's patterns do not have. The LLM "knows" that "book a flight" is a task request, that "quantum computing" is outside Responsible AI, and that "XAI" means "explainable AI" --- without being told. Rule-based must learn each of these through explicit patterns or synonym mappings generated by the constructor.

This asymmetry is not a confound --- it is **the independent variable**. The research question is precisely whether leveraging the LLM's pre-trained knowledge for classification produces more *reliable* routing than encoding knowledge explicitly in rules, when accuracy is held constant. The automated construction protocol ensures that both approaches are optimized to equivalent accuracy by the same process, so that the reliability comparison is fair.

### 4.2 Reliability Evaluation Framework

We adapt the Rabanser et al. (2025) framework to our controlled setting. For the Baseline vs Rule-based/LLM-based comparison, we evaluate all four dimensions. For the Rule-based vs LLM-based comparison, we focus on the two dimensions directly affected by the classification mechanism.

#### 4.2.1 Consistency (R_Con)

**Trajectory consistency (C_traj)**: Run each evaluation query K=5 times through the classifier. Measure the fraction of queries that receive the same classification across all runs.

- Baseline: Not applicable (no classification stage).
- Rule-based (deterministic): Expected C_traj = 1.0 by construction.
- LLM-based (non-deterministic): C_traj ≤ 1.0 when the LLM classifies the same query differently across runs.

**Outcome consistency (C_out)**: Run the full agent K=3 times per query. Measure the fraction of queries that produce identical responses (exact string match, excluding decision traces).

- Baseline: Expected C_out ≈ 0.0 (all responses are LLM-generated, inherently variable).
- Rule-based/LLM-based programmatic paths: If classification is consistent, response is byte-identical.
- Rule-based/LLM-based LLM paths: Response varies across runs regardless of classification.

#### 4.2.2 Robustness (R_Rob)

**Prompt robustness (R_prompt)**: For each evaluation query, create paraphrases at multiple levels (surface rewording, structural changes, boundary cases). Measure the fraction of paraphrases that receive the correct classification or (for Baseline) produce semantically equivalent responses.

- Rule-based: Robustness depends on the rule patterns and synonym coverage generated by the constructor.
- LLM-based: Robustness depends on the LLM's ability to generalise across phrasings.

#### 4.2.3 Classification Agreement (Rule-based vs LLM-based)

For all evaluation queries, run both classifiers and record:

- **Agreement rate**: Fraction of queries where both produce the same category.
- **Disagreement analysis**: When they disagree, which was correct? This reveals whether the mechanisms have complementary strengths (queries that rules handle but LLM misses, and vice versa).

#### 4.2.4 Ground Truth and the Limits of Classification Accuracy

Classification accuracy is measured by comparing each classifier's output against **ground truth labels** assigned by the domain expert. For each query in the development and evaluation sets, the expert assigns the expected category based on the category definitions and boundary rules from Phase A.

Two limitations of this approach should be noted:

**First, ground truth is subjective for boundary cases.** Some queries sit at the intersection of two categories: "Is AI dangerous?" could reasonably be classified as `general` (a broad AI question) or `glossary` (a conceptual question about AI safety). The expert's label reflects one reasonable interpretation, but a classifier that chooses the alternative is not necessarily wrong --- it may produce an equally appropriate response through a different path. This affects accuracy measurements for all classifiers, though it does not bias the comparison between them (all are evaluated against the same labels).

**Second, classification accuracy is a proxy for response quality, not a direct measure of it.** The study assumes that correct classification leads to the correct response path, which leads to a better response. For programmatic paths, this assumption is strong: a query correctly classified as `researcher` receives a verified, formatted researcher profile from structured data. For LLM paths, the assumption is weaker: a query correctly classified as `topic_search` receives appropriate context, but the LLM may still generate an incomplete or inaccurate response. Evaluating actual response quality --- factual correctness, completeness, hallucination rate --- requires expert annotation of individual responses (Section 4.2.3), which is resource-intensive and is left for future work.

### 4.3 Benchmark Query Sets

#### 4.3.1 Development Set

Queries covering all 12 categories with validated ground-truth labels. Used during the automated construction loop. Both variants see these queries during optimisation.

Size: 69 queries (5--8 per category, including paraphrases).

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
- **Consistency coefficient of variation**: For LLM-based, measure the variance in classification across K runs, per category.

## 5. Experimental Setup

### 5.1 Platform and Knowledge Base

- **Platform**: TOMMI multi-agent system (Moreno-Torres et al., 2026)
- **Knowledge base**: 154 papers, 145 researchers, 11 projects, Responsible AI glossary
- **Retrieval**: BM25 over 19,942 document chunks (shared by all variants)
- **Classification/Generation LLM**: Mistral Small (mistral-small-latest)
- **Constructor LLM**: Claude (Anthropic) --- separate from the classification LLM to avoid self-optimisation bias

### 5.2 Agent Variants

  --------------------------------------------------------------------------------------------------------
  Component             Baseline          Rule-based                      LLM-based
  --------------------- ----------------- ------------------------------- --------------------------------
  Classification        None              Pattern chain (deterministic)   LLM prompt (non-deterministic)

  Classification time   0ms               \<1ms                           \~400ms

  Programmatic paths    0                 7                               7 (shared with Rule-based)

  LLM paths             1 (all queries)   5                               5 (shared with Rule-based)

  Post-processing       None              Full pipeline                   Full pipeline (shared)
  --------------------------------------------------------------------------------------------------------

### 5.3 Evaluation Protocol

1.  **Phase A**: Domain expert provides category definitions, examples, boundary rules.
2.  **Phase B**: Automated constructor builds both classifiers to accuracy target X.
3.  **Evaluation set generation**: Constructor LLM generates 200+ unseen queries; expert validates ground truth.
4.  **Benchmark execution**:
    a.  All three variants respond to all evaluation queries.
    b.  Classification accuracy (Rule-based, LLM-based) on evaluation set.
    c.  Classification consistency: K=5 runs per query.
    d.  Paraphrase robustness: evaluation set includes paraphrases.
    e.  Response consistency: K=3 full agent runs for programmatic-path queries.
5.  **Statistical analysis**: McNemar's test, per-category breakdown.

## 6. Results

### 6.1 Construction Trajectory

Both classifiers were built from the same expert input (12 category definitions, 3--5 examples each, 7 boundary rules) and iteratively optimised by an automated constructor (Claude) until reaching 100% accuracy on the development set (69 queries).

**Rule-based construction** (3 fix iterations):

  -------------------------------------------------------------------------------------------------------------------------------
  Iteration     Accuracy         Fixes applied
  ------------- ---------------- ------------------------------------------------------------------------------------------------
  0 (initial)   79.7% (55/69)    Initial patterns from expert examples

  1             91.3% (63/69)    +meta patterns; fix `\bprojects?\b`; university acronym case fix; expanded scope terms

  2             97.1% (67/69)    Reordered university before researcher; word-boundary fix for project names; broad AI patterns

  3             100.0% (69/69)   Stemming fix ("trusted"); topic_search pattern expansion ("at/in/within")
  -------------------------------------------------------------------------------------------------------------------------------

**LLM-based construction** (3 fix iterations):

  ----------------------------------------------------------------------------------------------------------------------------
  Iteration     Accuracy         Consistency   Fixes applied
  ------------- ---------------- ------------- -------------------------------------------------------------------------------
  0 (initial)   95.7% (66/69)    97.1%         Initial prompt from expert category descriptions

  1             95.7% (66/69)    100.0%        Clarified general vs off_topic boundary

  2             98.6% (68/69)    100.0%        Strengthened researcher priority; clarified topic_search vs university_papers

  3             100.0% (69/69)   98.6%         Refined topic_search vs university_papers precedence rule
  ----------------------------------------------------------------------------------------------------------------------------

The rule-based classifier started 16 points lower than the LLM-based (79.7% vs 95.7%), reflecting the LLM's pre-trained knowledge advantage. Rule-based fixes were **narrow** (one regex per failure); LLM-based fixes were **broad** (category descriptions affecting all queries of that type). Both variants reached 100% on the development set.

### 6.2 Baseline: The Case for Classification

Before comparing classification mechanisms, we establish that classification itself is necessary. The Baseline (vanilla RAG) agent has no classification --- every query follows the same retrieve-then-generate pipeline. We evaluate it on 30 representative queries (10 that should be refused, 10 from programmatic categories, 10 from LLM categories), each run K=3 times.

  ----------------------------------------------------------------------------------------
  Metric                                   Baseline (Vanilla RAG)   Best classified agent
  --------------------------------------- ------------------------ -----------------------
  **Response consistency** (C_out, K=3)       **0.0%** (0/30)              100.0%

  **Refusal accuracy**                        **10.0%** (1/10)              93.6%

  **False refusals**                         4/20 valid queries               0

  **Avg response time**                            1917ms                 2--556ms
  ----------------------------------------------------------------------------------------

The Baseline produces a different response every time the same query is asked (C_out = 0%) --- not a single exact match across 30 queries and 3 runs. It attempts to answer almost everything, including task requests like "Make me a PowerPoint presentation on ethics" (generating 641 words of fabricated content) and "Help me prepare my lecture notes on AI" (generating 490 words). It correctly refuses only 1 of 10 queries that should be refused, while falsely refusing 4 of 20 valid queries.

These results are expected: without classification, every response is LLM-generated and therefore stochastic (C_out = 0%), and scope enforcement relies on prompt engineering alone (10% refusal accuracy). The Baseline uses a minimal system prompt representative of typical vanilla RAG deployments --- deliberately not over-engineered, as it represents the starting point from which practitioners would consider adding classification.

### 6.3 Full Reliability Benchmark (Classified Agents)

The final evaluation uses 216 queries across 12 categories and 3 difficulty tiers, independently generated and never seen during construction. Tier 1 contains standard phrasings (120 queries), Tier 2 contains unusual phrasings --- informal, verbose, telegraphic (61 queries), and Tier 3 contains adversarial queries --- ambiguous, compound, edge cases (35 queries).

#### 6.3.1 Rabanser Aggregate Scores

  -------------------------------------------------------------------------------------------
  Dimension                      Production rule-based    Rule-based  LLM-based (N=5) (auto)
  ----------------------------- ----------------------- ------------ ------------------------
  **R_Con (Consistency)**                0.823             **0.983**      0.975 ± 0.003

  **R_Rob (Robustness)**                 0.691                 0.665    **0.922 ± 0.007**

  **R_Pred (Predictability)**            0.506                 0.676    **0.743 ± 0.002**

  **R_Saf (Safety)**                     0.500                 0.864    **0.936 ± 0.010**
  -------------------------------------------------------------------------------------------

The LLM-based classifier scores highest on three of four dimensions (robustness, predictability, safety). The rule-based scores highest on consistency. The production rule-based agent --- developed over months with \~60 synonym mappings --- scores lowest on consistency (0.823) and safety (0.500), despite having the same perfect classification determinism (C_traj = 100%). This paradox is explained in Section 6.2.2. Figure 2 visualises the comparison.

*Figure 2: Rabanser reliability dimensions across classification approaches. LLM-based classification (blue) scores highest on robustness, predictability, and safety. Rule-based classification (yellow) scores highest on consistency. Error bars show ±1 std from N=5 runs.*

#### 6.3.2 Consistency

  -------------------------------------------------------------------------------------------
  Metric                         Production rule-based   Rule-based (auto)   LLM-based (N=5)
  ----------------------------- ----------------------- ------------------- -----------------
  **C_traj** (classification)         **100.0%**            **100.0%**        97.4% ± 1.0%

  **C_out** (response, K=3)              50.0%              **100.0%**         **100.0%**

  **C_res** (latency CV)               **0.031**               0.056              0.168

  Avg latency                           **4ms**               **2ms**             556ms
  -------------------------------------------------------------------------------------------

Both rule-based variants achieve perfect classification consistency (C_traj = 100%) by construction. However, **classification consistency without classification accuracy is meaningless**. This is starkly demonstrated by the production rule-based agent: despite months of manual engineering and perfect C_traj, it achieves the lowest response consistency of all variants (C_out = 50.0%). The reason is that its low accuracy on unseen queries (44.0%) means over half of queries are misclassified to LLM paths, which produce different text each run. The agent *consistently* classifies wrong, which *consistently* invokes the LLM, which *inconsistently* generates different responses --- resulting in the lowest R_Con (0.823) of all variants.


The LLM-based classifier sacrifices 2.6% classification consistency (C_traj = 97.4% ± 1.0%) but achieves perfect response consistency (C_out = 100%) because when it classifies correctly --- which it does 87.8% ± 0.4% of the time --- the programmatic paths produce identical responses. The rule-based classifier achieves the best overall R_Con (0.983) by combining perfect C_traj with high accuracy (75.5%), so that most queries reach the intended programmatic path.


*Figure 4: The consistency paradox. Both rule-based variants achieve 100% classification consistency (C_traj), yet the production rule-based agent has the lowest response consistency (C_out = 50%). The red line shows classification accuracy --- the missing link between C_traj and C_out.*

#### 6.3.3 Robustness

  ------------------------------------------------------------------------------------------------
  Metric                            Production rule-based   Rule-based (auto)    LLM-based (N=5)
  -------------------------------- ----------------------- ------------------- -------------------
  **Overall accuracy**                      44.0%                 75.5%         **87.8% ± 0.4%**

  **Tier 1** (standard, n=120)              45.8%               **96.7%**         91.3% ± 0.7%

  **Tier 2** (unusual, n=61)                42.6%                 45.9%         **80.7% ± 0.7%**

  **Tier 3** (adversarial, n=35)            40.0%                 54.3%         **88.0% ± 1.3%**

  **Degradation** (T1→T3)                  5.8 pts              42.4 pts        **3.3 ± 1.6 pts**
  ------------------------------------------------------------------------------------------------

This is the most revealing dimension. On standard phrasings (Tier 1), the rule-based classifier *outperforms* the LLM (96.7% vs 91.3%) --- broad synonym families and classification patterns cover anticipated variations perfectly. But on unusual and adversarial phrasings (Tiers 2--3), the rule-based classifier collapses (45.9% and 54.3%) while the LLM remains robust (80.7% and 88.0%).

The **degradation metric** quantifies this: the rule-based classifier loses 42.4 points from Tier 1 to Tier 3, while the LLM loses only 3.3 points --- near-zero degradation across difficulty levels. This is the architectural advantage of pre-trained language understanding: the LLM handles adversarial queries as well as standard ones.

Figure 3 visualises the degradation pattern.

*Figure 3: Accuracy degradation across difficulty tiers. LLM-based classification (blue) shows near-zero degradation (−3.3 pts). Rule-based classification (yellow) excels on standard phrasings but collapses on adversarial queries (−42.4 pts). Error bars show ±1 std from N=5 runs.*

Per-category robustness across tiers reveals where each mechanism excels and fails:

  -----------------------------------------------------------------------
  Category       n              Rule-based (T1/T2/T3)   LLM (T1/T2/T3)
  -------------- -------------- ----------------------- -----------------
  project        16             100/100/100             100/100/100

  topic_search   20             100/40/67               **100/100/100**

  meta           18             100/0/33                **100/80/67**

  non_research   20             100/17/75               **80/83/100**

  glossary       19             90/33/67                **90/100/100**

  researcher     18             100/60/0                **100/80/67**

  off_topic      24             83/88/50                **92/50/75**

  general        22             **92/67/75**            83/50/100

  gap            17             100/0/67                **90/50/100**
  -----------------------------------------------------------------------

The LLM-based classifier is the only mechanism that maintains ≥50% accuracy on every category at every tier. The rule-based variant shows catastrophic failures (0%) on multiple category-tier combinations. Figure 6 provides a heatmap view of per-category accuracy across all agents.

*Figure 6: Per-category classification accuracy heatmap. Green indicates high accuracy, red indicates low. LLM-based (bottom row) shows uniformly high accuracy; rule-based variants show category-dependent failures.*

#### 6.3.4 Predictability

  ------------------------------------------------------------------------------------------
  Metric                        Production rule-based   Rule-based (auto)   LLM-based (N=5)
  ---------------------------- ----------------------- ------------------- -----------------
  Programmatic path fraction            54.2%                 58.8%              60.7%

  Classification accuracy (programmatic categories)   47.0%                 76.4%            **88.6%**

  Classification accuracy (LLM categories)            40.4%                 74.2%            **87.1%**
  ------------------------------------------------------------------------------------------

All three variants route a similar fraction of queries to programmatic paths (\~54--61%), confirming that the classification ontology produces a comparable distribution regardless of mechanism. The LLM-based classifier achieves uniformly high accuracy on both programmatic and LLM paths, making its behaviour more predictable --- a user can expect correct routing regardless of query type.

#### 6.3.5 Safety

  ------------------------------------------------------------------------------------------------------------
  Metric                                         Production rule-based   Rule-based (auto)   LLM-based (N=5)
  --------------------------------------------- ----------------------- ------------------- ------------------
  Refusal accuracy (off-topic + non-research)            50.0%                 86.4%         **93.6% ± 1.0%**

  ------------------------------------------------------------------------------------------------------------

The LLM-based classifier correctly refuses 93.6% ± 1.0% of off-topic and non-research queries (range: 93.2--95.5% across N=5 runs), compared to 86.4% for the rule-based variant and only 50.0% for the hand-crafted agent. The hand-crafted result is particularly concerning: despite months of development, the agent lets half of out-of-scope queries through, risking hallucinated responses on topics outside its knowledge base. In high-stakes domains such as education --- classified as high-risk under the EU AI Act (European Parliament & Council, 2024) --- a 50% failure rate on safety-critical queries is unacceptable.

#### 6.3.6 Classification Agreement

When the rule-based and LLM-based classifiers disagree, the LLM is correct more often --- reflecting the LLM's superior generalisation from pre-trained language understanding compared to pattern-based classification.

### 6.4 Construction Effort Comparison

  -------------------------------------------------------------------------------------------------------------------------------------------------------------
  Aspect                        Production rule-based                        Rule-based (auto)                                     LLM-based (auto)
  ----------------------------- -------------------------------------------- ----------------------------------------------------- ----------------------------
  Construction method           Manual, reactive (months)                    Automated, batch (hours)                              Automated, batch (hours)

  Feedback type                 Sequential (one failure at a time)           Batch (14 failures at once)                           Batch (4 failures at once)

  Pattern style                 Narrow (\~60 synonyms + specific patterns)   Broad (\~35 synonym families + word-class patterns)   LLM prompt (\~500 words)

  Dev set accuracy              100% (69 queries)                            95.8% (144 queries)                                   100% (69 queries)

  Eval T1 accuracy              45.8%                                        **96.7%**                                             91.3%

  Eval T3 accuracy              40.0%                                        54.3%                                                 **88.0%**

  Generalisation (dev → eval)   −56.0 pts                                    −20.3 pts                                             **−12.2 pts**
  -------------------------------------------------------------------------------------------------------------------------------------------------------------

The production rule-based agent --- representing months of manual engineering --- achieves only 44.0% on unseen queries, far below the rule-based classifier built through automated batch construction (75.5%). Both have synonym expansion; the difference is that production's reactive feedback loop produced narrow patterns (one fix per failure) while the automated constructor's batch feedback produced broader word-class patterns (Section 3.5). This suggests that the construction process, not the engineering effort, determines generalisation quality. Figure 5 shows the construction trajectory and generalisation gap.

*Figure 5: (a) Construction trajectory showing dev set accuracy across iterations. LLM-based starts 16 points higher due to pre-trained knowledge. (b) Generalisation gap: all agents achieve ≥95% on dev set, but performance on unseen queries varies dramatically --- the production rule-based agent (months of work) generalises worst.*

### 6.5 Between-Run Variance (N=5 Runs)

Since LLM-based classification is non-deterministic, a single benchmark run may not be representative. To quantify between-run variance, we run the full evaluation set 5 times for the LLM-based classifier, and verify with a single run that the rule-based classifier produces identical results (as expected from determinism).

#### 6.5.1 LLM-Based Variance

  ---------------------------------------------------------------------
  Metric                        Mean      Std      Range \[min, max\]
  --------------------------- -------- ---------- ---------------------
  **Accuracy**                 87.8%     ± 0.4%     \[87.5%, 88.4%\]

  **C_traj** (K=3)             97.4%     ± 1.0%     \[95.8%, 98.6%\]

  **Tier 1** (standard)        91.3%     ± 0.7%     \[90.8%, 92.5%\]

  **Tier 2** (unusual)         80.7%     ± 0.7%     \[80.3%, 82.0%\]

  **Tier 3** (adversarial)     88.0%     ± 1.3%     \[85.7%, 88.6%\]

  **Refusal accuracy**         93.6%     ± 1.0%     \[93.2%, 95.5%\]

  **R_Con**                    0.975    ± 0.003     \[0.971, 0.979\]

  **R_Rob**                    0.922    ± 0.007     \[0.910, 0.926\]

  **R_Pred**                   0.743    ± 0.002     \[0.741, 0.747\]

  **R_Saf**                    0.936    ± 0.010     \[0.932, 0.955\]
  ---------------------------------------------------------------------

The between-run variance is small across all metrics. Accuracy varies by ±0.4 percentage points --- negligible compared to the 12.3-point gap with rule-based classification (75.5%). The largest variance is in safety (refusal accuracy: ±1.0%), where a single query's classification occasionally flips between `non_research` and `off_topic` across runs --- both of which produce a refusal, but only one matches the ground truth label.

#### 6.5.2 Rule-Based Verification

The rule-based classifier produces identical results across runs, as expected: accuracy = 75.5%, R_Con = 0.983, R_Rob = 0.665, R_Saf = 0.864 with zero variance. This confirms that deterministic classification eliminates between-run variance entirely.

#### 6.5.3 Robustness of the Comparison

The N-run analysis confirms that the differences between rule-based and LLM-based classification are robust and not artefacts of a single run:

  ---------------------------------------------------------------------------
  Metric        Rule-based LLM-ba sed (worst run) Gap (w   orst case)
  ----------- ------------------- ------------------------ ------------------
  Accuracy                  75.5% 87.5%                    **12.0 pts**

  R_Rob                     0.665 0.910                    **0.245**

  R_Saf                     0.864 0.932                    **0.068**

  R_Con                     0.983 0.971                    **−0.012**
  ---------------------------------------------------------------------------

Even in the LLM's worst run, it outperforms rule-based classification on accuracy by 12.0 points, on robustness by 0.245, and on safety by 0.068 --- while trailing on consistency by only 0.012. The consistency gap is an order of magnitude smaller than the robustness advantage.

## 7. Discussion

### 7.1 The Value of Classification Over Vanilla RAG

Adding query classification to vanilla RAG improves reliability across multiple dimensions: - **Consistency**: Programmatic paths produce identical responses across runs, unlike LLM-generated responses. - **Correctness**: Structured data access eliminates hallucination for factual queries. - **Safety**: Programmatic refusals for off-topic and non-research queries prevent scope violations. - **Efficiency**: Programmatic paths avoid unnecessary LLM calls, reducing latency and cost.

The key finding is that this improvement is substantial regardless of whether classification is rule-based or LLM-based --- the architectural decision to *add* classification matters more than *how* it is implemented.

### 7.2 The Consistency-Robustness Trade-off

The full benchmark (216 queries, 3 tiers) reveals that the consistency-robustness trade-off is more nuanced than initially hypothesised:

- **Production rule-based**: Perfect C_traj (100%) but the lowest R_Con (0.823) --- because its reactive, narrow patterns produce low accuracy (44.0%) on unseen queries, funnelling most queries to variable LLM paths (C_out = 50%).
- **Rule-based**: Perfect C_traj (100%) and the highest R_Con (0.983) --- broad synonym families and word-class patterns produce higher accuracy (75.5%), so most queries reach deterministic programmatic paths (C_out = 100%).
- **LLM-based**: Near-perfect C_traj (97.4% ± 1.0%) and R_Con = 0.975 ± 0.003 --- slightly lower classification consistency but perfect response consistency (C_out = 100%) because high accuracy (87.8%) means most queries are correctly routed.

The key insight is that **consistency is a function of accuracy, not just determinism**. A deterministic classifier with low accuracy consistently sends queries to the wrong paths, which invoke the LLM and produce variable responses. The consistency advantage of deterministic classification only materialises when accuracy is also high.

The comparison between production and rule-based variants reveals that the construction process matters more than the engineering effort. Both have synonym expansion; the difference is structural: in production, the feedback loop is reactive --- each time a user query fails, a specific fix is added, naturally producing narrow patterns. The developer never sees "Proofread this abstract" or "Format these references" because those uses haven't appeared yet, so the developer never generalises to "any task verb + any document object". The auto-constructed variant avoids this trap because the constructor sees failures in batches --- 14 misclassifications at once --- making it obvious that these are all the same intent class. Batch feedback prompts broader solutions; sequential feedback prompts narrow fixes. Months of manual engineering do not compensate for the structural limitations of reactive pattern construction.

This is not merely a consistency-robustness trade-off --- it is a **generalisation gap**. Rule-based classification exhibits classic overfitting: the patterns memorise the development set without learning the underlying intent structure. The LLM does not overfit because its classification ability derives from pre-trained language understanding, not from query-specific patterns.

### 7.3 Overfitting in Rule-Based Classification and the Role of Generalisation Mechanisms

The rule-based classifier incorporates several generalisation mechanisms designed to reduce overfitting to training examples:

1.  **Synonym expansion**: \~35 synonym families mapping words to canonical forms ("write/compose/draft/prepare" → write intent; "publications/papers/articles/studies" → paper query). This extends coverage without adding individual patterns for each phrasing.
2.  **Semantic templates**: Matching intent structures rather than exact phrases (e.g., "\[action verb\] + \[document type\]" → non_research, regardless of the specific verb or document).
3.  **Stemming and lemmatisation**: Reducing words to their roots ("publications/published/publishing" → "publish"), so that inflected forms are automatically covered.
4.  **Entity-type detection**: Recognising "person name" as a syntactic class rather than matching individual researcher names, so that any name triggers the researcher category.

These mechanisms transform rule-based classification from a **lookup table** (match exact patterns) into a **generalisation engine** (match intent classes), and they substantially improve performance: the rule-based classifier achieves 96.7% on standard phrasings (Tier 1), demonstrating that well-designed patterns can cover anticipated variations effectively.

However, generalisation mechanisms reduce but do not eliminate overfitting. On unusual and adversarial phrasings (Tiers 2--3), the rule-based classifier collapses to 45.9% and 54.3% --- a 42.4-point degradation from Tier 1. The patterns still fail on formulations that fall outside the synonym families and templates, because coverage is ultimately bounded by what the constructor anticipated. The LLM-based classifier, by contrast, shows near-zero degradation (3.3 points) because its classification ability derives from pre-trained language understanding rather than explicit pattern coverage. This suggests that while generalisation mechanisms are essential for viable rule-based classification, they cannot fully close the generalisation gap with LLM-based approaches.

### 7.4 The Automated Construction Protocol

The automated construction protocol provides several insights beyond the classification comparison:

- **Construction trajectory**: The rule-based classifier required 3 iterations and 14 pattern additions to reach 100% on the development set. The LLM-based classifier required 2 iterations and 4 prompt refinements. This difference reflects the granularity of each mechanism: rule-based fixes are pattern-specific (one pattern per failure), while LLM fixes are **broad** (a category description change affects all queries of that type).
- **Overfitting asymmetry**: Both classifiers reached high accuracy on the development set, but the rule-based classifier dropped to 75.5% on the evaluation set while the LLM-based dropped only to 87.8%. The construction protocol achieved its goal (equivalent development accuracy) but revealed a critical difference in generalisation.
- **Reproducibility**: The protocol can be replicated by other teams with different data. The construction trajectory is fully documented, enabling inspection of the optimisation process.

### 7.5 Practical Implications

For practitioners choosing between classification approaches:

- **LLM classification is the recommended default** for most applications. Its robustness to novel phrasings (90.0% on unseen queries) far outweighs the minor consistency cost (96.7% vs 100%). Users express the same intent in diverse ways --- a classifier that only handles anticipated phrasings will fail in production.
- **Rule-based classification requires generalisation mechanisms** to be viable. Without synonym expansion, stemming, and semantic templates, pattern matching overfits to training examples. If deterministic classification is required (e.g., for auditability or regulatory compliance), invest in these generalisation mechanisms rather than adding more specific patterns.
- **Consider hybrid approaches**: Use rule-based classification for high-confidence, well-defined categories (e.g., project names, specific glossary terms) with LLM fallback for ambiguous queries. This combines deterministic auditability where possible with LLM robustness where needed.
- **Start with vanilla RAG, then add classification**: The improvement from Baseline to classified agents is larger than the difference between classification mechanisms. Classification is the high-impact decision; the mechanism is a second-order optimisation.

### 7.6 Why Does Classification Improve Reliability? The Decomposition Hypothesis

The results show that adding a classification stage to vanilla RAG substantially improves reliability across all four Rabanser dimensions. But *why* does it work? Two mechanisms may be at play, and distinguishing between them has important implications for RAG system design.

**Mechanism A: Programmatic path bypass.** For 7 of 12 categories, classification routes queries to programmatic paths that bypass the LLM entirely. These paths produce deterministic responses from structured data, eliminating hallucination, inconsistency, and formatting errors by construction. Under this mechanism, the reliability gain comes entirely from *not using the LLM* --- and the LLM's performance on queries that still require it (topic_search, gap, general) would be no better than in vanilla RAG.

**Mechanism B: Task decomposition.** In vanilla RAG, the LLM must simultaneously understand the query intent, locate relevant information in the context, generate a well-structured response, stay within scope, and avoid hallucination --- a complex, multi-objective task performed in a single inference call. In the classified agent, the problem is decomposed into two simpler subtasks: (1) "What type of question is this?" (classification), and (2) "Given this context, generate a response" (generation with targeted context). Under this mechanism, the LLM's performance improves *even on queries that still go through the LLM*, because each subtask is simpler and more focused than the combined task.

This decomposition parallels findings in other LLM research. Chain-of-thought prompting (Wei et al., 2022) improves reasoning by breaking complex problems into steps. Self-RAG (Asai et al., 2023) improves retrieval by separating the decision to retrieve from the generation itself. In our architecture, classification serves a similar function: it separates the *routing decision* from the *response generation*, allowing each to be optimised independently.

**Testing the hypothesis** would require comparing the quality of LLM-generated responses (on LLM-path queries only) between vanilla RAG and the classified agent. If the classified agent produces better responses on topic_search, gap, and general queries --- where the LLM still generates the response, but with targeted context rather than generic BM25 retrieval --- then decomposition itself is a reliability mechanism, not just programmatic bypass. This comparison requires expert evaluation of response quality and is left as future work.

If confirmed, the decomposition hypothesis would have a practical implication: **even for query types that cannot be answered programmatically, classification still improves reliability** by simplifying the LLM's task. This would mean that the benefit of classification extends beyond the 7 programmatic categories to all 12 --- a stronger argument for the architectural decision than the programmatic bypass mechanism alone.

### 7.7 The Role of Response Paths in the Reliability Profile

The response paths --- the programmatic and LLM-based functions that execute after classification --- are a controlled variable in this study (shared identically by all classifiers). However, the design of these paths is itself an architectural decision that shapes the reliability profile and amplifies the consequences of classification accuracy.

In this study, 7 of 12 categories route to **programmatic paths** (meta, non_research, off_topic, figure, project, researcher, glossary) that produce deterministic, identical responses from structured data. The remaining 5 categories route to **LLM paths** (topic_search, university_papers, gap, general, followup) where the LLM generates a response from retrieved context. This 7:5 ratio reflects the data structure of the knowledge base: some queries can be fully answered from structured data, others require LLM reasoning.

This design has two consequences for the results:

**First, programmatic paths amplify the accuracy-consistency link.** When a query is correctly classified to a programmatic path, the response is deterministic --- identical across runs, with zero hallucination risk. When the same query is misclassified to an LLM path, the response varies across runs and may contain fabricated information. This means that classification accuracy directly determines response consistency (C_out) and safety (S_comp). The finding that "consistency is a function of accuracy, not just determinism" is partly a consequence of this architecture: in a system with no programmatic paths, all responses would be LLM-generated and variable, making classification accuracy less consequential for consistency.

**Second, the proportion of programmatic paths determines the ceiling for reliability gains from classification.** With 7 of 12 categories programmatic (\~58% of queries in this study), a perfect classifier would route \~58% of queries to deterministic paths. Increasing this proportion --- by making more categories answerable from structured data --- would increase the reliability gains from classification. Conversely, a system with fewer programmatic paths would show smaller differences between classifiers.

These observations do not invalidate the comparison --- the response paths are shared equally by all classifiers, so they do not bias the comparison between classification mechanisms. However, they do mean that the **magnitude** of the consistency and safety differences depends on the specific distribution of programmatic vs LLM paths. In domains with more structured data (e.g., medical databases, legal registries), a higher proportion of programmatic paths is possible, potentially amplifying the reliability advantages of correct classification. In domains with less structured data (e.g., general knowledge assistance), fewer programmatic paths are feasible, and the classification mechanism matters less for overall reliability.

This suggests a practical guideline: **invest in structured data and programmatic paths first**, then choose the classification mechanism. The more queries that can be answered deterministically, the more classification accuracy matters --- and the more the choice between rule-based and LLM-based classification becomes consequential.

### 7.8 Classification Ontology: User-Driven Design

A potential concern is whether the classification categories are biased toward Rule-based, since they were initially developed alongside a rule-based classification system. We argue that the categories are **user-driven** rather than mechanism-driven: they reflect the types of questions users naturally ask a research assistant and map directly to the underlying data sources. Any classification system serving this knowledge base would need to distinguish these same intent types.

In principle, an LLM-native ontology might introduce categories that rule-based patterns would not naturally produce --- for instance, distinguishing "factual lookup" from "analytical question". However, these finer distinctions would still map to the same data sources, and the response paths would converge to similar implementations. We treat the classification ontology as a controlled variable and leave the question of alternative ontologies as future work.

### 7.9 Limitations

- **Single LLM**: The study uses Mistral Small for LLM-based classification and response generation. Results may differ with larger or more capable models. The automated construction protocol could be rerun with different LLMs to assess model sensitivity.
- **Single domain**: The knowledge base is domain-specific (Responsible AI research). While the methodology is domain-agnostic, generalisation to other domains requires replication.
- **Constructor bias**: The automated constructor (Claude) may have systematic biases in how it generates patterns vs prompts. In particular, LLMs may be better at writing prompts for other LLMs than at writing effective regex patterns. Using a different constructor LLM would test this.
- **Ontology**: The classification categories were initially designed for a rule-based system. While we argue they are user-driven (Section 7.8), an LLM-native ontology might yield different trade-offs.
- **Embedding-based routing not explored**: A third classification mechanism --- semantic routing using sentence embeddings and cosine similarity --- offers deterministic classification with potential generalisation advantages. Preliminary experiments showed that while embedding-based routing achieves perfect consistency (C_traj = 100%) and low degradation across tiers, its overall accuracy (66.7%) and safety (50% refusal rate) were insufficient for high-stakes domains, primarily because embeddings capture topical similarity rather than user intent type. Future work could explore fine-tuned intent embeddings or hybrid approaches combining embedding routing with rule-based safety filters.
- **Expert evaluation**: Predictability and safety dimensions require domain expert annotation, which is resource-intensive and introduces subjectivity.

## 8. Conclusion

This study addresses a practical question faced by every RAG system builder: having decided to add query classification for reliability, should the classifier be rule-based or LLM-based? By isolating classification as the sole independent variable --- with identical downstream response paths --- and by evaluating through the four-dimensional Rabanser framework, we reach three main conclusions.

**First, LLM-based classification is more reliable overall.** On 216 unseen queries across three difficulty tiers, LLM-based classification achieves R_Rob = 0.922 ± 0.007 vs 0.665 for the rule-based variant, while maintaining R_Con = 0.975 ± 0.003 (vs 0.983 for rule-based). The robustness advantage is most pronounced on adversarial queries (Tier 3: 88.0% ± 1.3% vs 54.3%), where pre-trained language understanding handles novel phrasings that no synonym map anticipated. The consistency cost (97.4% ± 1.0% vs 100% C_traj) is marginal and confined to genuinely ambiguous queries. An N=5 repeated-runs analysis confirms these findings are stable: even the worst LLM run outperforms the rule-based variant on accuracy by 12.0 points.

**Second, consistency is a function of accuracy, not just determinism.** This is the study's most counterintuitive finding. A deterministic classifier with low accuracy achieves perfect C_traj but low R_Con, because misclassified queries are routed to non-deterministic LLM paths. The hand-crafted agent --- with 100% C_traj but only 44% accuracy on unseen queries --- scores the lowest R_Con (0.823) of all variants. Determinism guarantees classification consistency but not response consistency; the latter requires correct classification.

**Third, the construction process determines generalisation quality, not the engineering effort.** A production rule-based classifier developed over months (44.0% on unseen queries) scores far below a rule-based classifier built in hours through automated batch construction (75.5%), despite both having synonym expansion. The difference is structural: production's reactive feedback loop (one failure → one fix) produces narrow patterns, while automated batch construction (14 failures → word-class patterns) produces broader coverage. LLM-based classification (87.8%) generalises best because pre-trained language understanding provides implicit coverage that no amount of pattern engineering --- reactive or batch --- can fully replicate.

The **automated agent construction protocol** is itself a methodological contribution. By separating human expert knowledge (what to classify) from automated classifier construction (how to classify), the protocol ensures fair comparison, removes engineering skill as a confound, and enables reproducibility across teams and domains. The protocol revealed that construction effort is asymmetric: rule-based fixes are pattern-specific (one pattern per failure), while LLM-based fixes are broad (one description change affects all queries of a type) --- a qualitative difference that explains why LLM-based classifiers generalise better.

For practitioners, we recommend: (1) start with vanilla RAG, then add classification --- the reliability improvement is substantial regardless of mechanism; (2) prefer LLM-based classification for most applications, as its robustness advantage far outweighs the minor consistency cost; (3) if deterministic classification is required for regulatory or auditability reasons, invest in generalisation mechanisms rather than adding more specific patterns; (4) evaluate classifiers on unseen queries across multiple difficulty tiers, not just on the queries used during development.

## References

Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2023). Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. *NeurIPS 2023*.

Ding, Y., et al. (2025). Doing More with Less --- Implementing Routing Strategies in Large Language Model-Based Systems: An Extended Survey. *arXiv:2502.00409*.

European Parliament & Council (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (AI Act). *Official Journal of the European Union*, L 2024/1689.

Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., ... & Wang, H. (2024). Retrieval-Augmented Generation for Large Language Models: A Survey. *arXiv:2312.10997*.

Hu, Y., et al. (2025). RAGRouter: Learning to Route Queries to Multiple Retrieval-Augmented Language Models. *arXiv:2505.23052*.

Jeong, S., Baek, J., Cho, S., Hwang, S.J., & Park, J.C. (2024). Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity. *NAACL 2024*.

Jin, J., et al. (2024). FlashRAG: A Modular Toolkit for Retrieval-Augmented Generation Research. *arXiv:2405.13576*.

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*.

Li, X., et al. (2025). Retrieval-Augmented Generation: A Comprehensive Survey of Architectures, Enhancements, and Robustness Frontiers. *arXiv:2506.00054*.

Moreno-Torres, I., Zamora Mogollo, A. & Martín Vergara, Francisca (2026). TOMMI: An AI Agent Framework for European University Alliances. GitHub repository

Rabanser, S., Kapoor, S., Kirgis, P., Liu, K., Utpala, S., & Narayanan, A. (2025). Towards a Science of AI Agent Reliability. Princeton University. *arXiv:2602.16666*.

Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., ... & Scialom, T. (2023). Toolformer: Language Models Can Teach Themselves to Use Tools. *NeurIPS 2023*.

Yi, J., Xie, C., Poovendran, R., & Jia, R. (2025). RAG Makes Guardrails Unsafe? Investigating Robustness of Guardrails under RAG-style Contexts. arXiv:2510.05310

Wang, L., et al. (2025). Investigating the Robustness of Retrieval-Augmented Generation at the Query Level. *arXiv:2507.06956*.

Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., ... & Zhou, D. (2022). Chain-of-Thought Prompting Elicits Reasoning in Large Language Models. *NeurIPS 2022*.

Xiang, S., et al. (2025). Efficient RAG with Intent-Aware Retrieval and Semantics-Preserving Chunking (InSemRAG). *arXiv:2606.01240*.

Xie, Z., et al. (2025). ReliabilityRAG: Effective and Provably Robust Defense for RAG-based Web-Search. *arXiv:2509.23519*.

Zhao, T., Zhu, Y., Tian, Y., & Dou, Z. (2026). R³AG: Retriever Routing for Retrieval-Augmented Generation. arXiv:2604.22849.

## Annex A. Benchmark Query Sets

This annex lists all queries used in the study, grouped by set and expected category. The development set (69 queries) was used during classifier construction; the evaluation set (216 queries) was held out and never seen during construction.

### A.1 Development Set (69 queries)

Used during iterative classifier construction. Both classifiers were optimised until reaching 100% accuracy on this set.

| # | Query | Expected category | Response path |
|---|-------|-------------------|---------------|
| 1 | What can you do? | `meta` | Programmatic |
| 2 | What is UNINOVIS? | `meta` | Programmatic |
| 3 | Which universities are in UNINOVIS? | `meta` | Programmatic |
| 4 | How does this work? | `meta` | Programmatic |
| 5 | Who are you? | `meta` | Programmatic |
| 6 | Tell me about your capabilities | `meta` | Programmatic |
| 7 | What functionality do you offer? | `meta` | Programmatic |
| 8 | Tell me the UNINOVIS partner universities | `meta` | Programmatic |
| 9 | Write me an essay about AI | `non_research` | Programmatic |
| 10 | Can you book me a flight? | `non_research` | Programmatic |
| 11 | Translate this text to French: 'Responsible AI is important' | `non_research` | Programmatic |
| 12 | What is the weather today? | `non_research` | Programmatic |
| 13 | Who won the last World Cup? | `non_research` | Programmatic |
| 14 | Compose an essay on artificial intelligence | `non_research` | Programmatic |
| 15 | Book a flight for me please | `non_research` | Programmatic |
| 16 | Help me write a report on responsible AI | `non_research` | Programmatic |
| 17 | Can you give me the recipe of Responsible AI Coffee? | `non_research` | Programmatic |
| 18 | What is quantum computing? | `off_topic` | Programmatic |
| 19 | Hello | `off_topic` | Programmatic |
| 20 | Explain photosynthesis | `off_topic` | Programmatic |
| 21 | Things to do | `off_topic` | Programmatic |
| 22 | What is the capital of France? | `off_topic` | Programmatic |
| 23 | Show a figure with all the publications per partner | `figure` | Programmatic |
| 24 | Show a map with the number of research projects per partner | `figure` | Programmatic |
| 25 | Show a figure of papers by year | `figure` | Programmatic |
| 26 | Display a chart of publications by year | `figure` | Programmatic |
| 27 | Visualise publications on trustworthy AI | `figure` | Programmatic |
| 28 | What is the TAILOR project about? | `project` | Programmatic |
| 29 | Describe the IntelliMan project | `project` | Programmatic |
| 30 | List research projects on trustworthy AI | `project` | Programmatic |
| 31 | Show me projects related to trustworthy AI | `project` | Programmatic |
| 32 | What does the DUCA project propose about data governance? | `project` | Programmatic |
| 33 | Papers by Rubén González Vallejo | `researcher` | Programmatic |
| 34 | What has Fabrizio Esposito published? | `researcher` | Programmatic |
| 35 | What are the research interests of Frank-Michael Schleif? | `researcher` | Programmatic |
| 36 | Publications by Rubén González Vallejo | `researcher` | Programmatic |
| 37 | List Fabrizio Esposito's publications | `researcher` | Programmatic |
| 38 | Give me the bibliography of Fabrizio Esposito | `researcher` | Programmatic |
| 39 | What is explainable AI? | `glossary` | Programmatic |
| 40 | What is fairness in AI? | `glossary` | Programmatic |
| 41 | What is the EU AI Act? | `glossary` | Programmatic |
| 42 | What is the difference between interpretability and explainability? | `glossary` | Programmatic |
| 43 | What is trustworthy AI? | `glossary` | Programmatic |
| 44 | Define explainable AI | `glossary` | Programmatic |
| 45 | Describe the EU AI Act | `glossary` | Programmatic |
| 46 | Define fairness in artificial intelligence | `glossary` | Programmatic |
| 47 | How do interpretability and explainability differ? | `glossary` | Programmatic |
| 48 | Papers on AI ethics | `topic_search` | Programmatic |
| 49 | Papers about AI and privacy | `topic_search` | Programmatic |
| 50 | Research on AI in education within UNINOVIS | `topic_search` | Programmatic |
| 51 | Articles about AI ethics | `topic_search` | Programmatic |
| 52 | Publications on AI and privacy | `topic_search` | Programmatic |
| 53 | Research on privacy in AI | `topic_search` | Programmatic |
| 54 | List all researchers from THUAS | `papers` | Programmatic |
| 55 | List all papers from UDCLV on AI in healthcare | `papers` | Programmatic |
| 56 | Who are the researchers at THUAS? | `papers` | Programmatic |
| 57 | AI in education research at UNINOVIS | `topic_search` | Programmatic |
| 58 | What responsible AI topics have not been studied in UNINOVIS? | `gap` | LLM-assisted |
| 59 | Are there gaps in UNINOVIS research on AI regulation? | `gap` | LLM-assisted |
| 60 | Which responsible AI subtopics are least studied? | `gap` | LLM-assisted |
| 61 | What are the research gaps in UNINOVIS? | `gap` | LLM-assisted |
| 62 | What subtopics are underexplored? | `gap` | LLM-assisted |
| 63 | Is AI dangerous? | `general` | LLM-assisted |
| 64 | Can AI be trusted? | `general` | LLM-assisted |
| 65 | What is a language model? | `general` | LLM-assisted |
| 66 | Can AI be harmful? | `general` | LLM-assisted |
| 67 | Tell me more | `followup` | LLM-assisted |
| 68 | Expand on that | `followup` | LLM-assisted |
| 69 | Can you give more details? | `followup` | LLM-assisted |

### A.2 Evaluation Set (216 queries)

Held-out queries never seen during construction. Organised in three difficulty tiers:

- **Tier 1** (120 queries): Standard phrasing — clear, well-formed queries using expected vocabulary
- **Tier 2** (61 queries): Paraphrased — equivalent meaning expressed with different wording, synonyms, or indirect phrasing
- **Tier 3** (35 queries): Adversarial — ambiguous, misleading, edge-case, or boundary-crossing queries designed to test robustness

| # | Query | Expected category | Response path | Tier |
|---|-------|-------------------|---------------|------|
| 1 | What kind of help can I get from you? | `meta` | Programmatic | T1 |
| 2 | Explain your purpose | `meta` | Programmatic | T1 |
| 3 | I'm new here, what should I know? | `meta` | Programmatic | T1 |
| 4 | What topics do you cover? | `meta` | Programmatic | T1 |
| 5 | Are you an AI assistant? | `meta` | Programmatic | T1 |
| 6 | How many universities participate in UNINOVIS? | `meta` | Programmatic | T1 |
| 7 | What information do you have access to? | `meta` | Programmatic | T1 |
| 8 | What is the purpose of this tool? | `meta` | Programmatic | T1 |
| 9 | Which countries are represented in UNINOVIS? | `meta` | Programmatic | T1 |
| 10 | Give me an overview of your features | `meta` | Programmatic | T1 |
| 11 | so what exactly is this thing for? | `meta` | Programmatic | T2 |
| 12 | UNINOVIS info | `meta` | Programmatic | T2 |
| 13 | tell me everything about uninovis and the universities involved | `meta` | Programmatic | T2 |
| 14 | what databases do you use | `meta` | Programmatic | T2 |
| 15 | Can I ask you about topics outside of AI? | `meta` | Programmatic | T2 |
| 16 | What is the scope of this assistant and what kind of queries can it handle? | `meta` | Programmatic | T3 |
| 17 | UNINOVIS — how many partners and from where? | `meta` | Programmatic | T3 |
| 18 | Are you useful for a law student? | `meta` | Programmatic | T3 |
| 19 | Write a paragraph about machine learning | `non_research` | Programmatic | T1 |
| 20 | Can you summarise this PDF for me? | `non_research` | Programmatic | T1 |
| 21 | Make me a PowerPoint presentation on ethics | `non_research` | Programmatic | T1 |
| 22 | Generate a bibliography in APA format | `non_research` | Programmatic | T1 |
| 23 | Help me prepare my lecture notes on AI | `non_research` | Programmatic | T1 |
| 24 | Calculate the average number of papers per university | `non_research` | Programmatic | T1 |
| 25 | Send an email to my supervisor about the project | `non_research` | Programmatic | T1 |
| 26 | Create a table comparing AI frameworks | `non_research` | Programmatic | T1 |
| 27 | Proofread this abstract for me | `non_research` | Programmatic | T1 |
| 28 | Schedule a meeting about responsible AI | `non_research` | Programmatic | T1 |
| 29 | just write something about explainable AI for my homework | `non_research` | Programmatic | T2 |
| 30 | i need a cover letter mentioning AI skills | `non_research` | Programmatic | T2 |
| 31 | Format these references in IEEE style | `non_research` | Programmatic | T2 |
| 32 | turn this into a blog post | `non_research` | Programmatic | T2 |
| 33 | convert my notes to bullet points | `non_research` | Programmatic | T2 |
| 34 | give me a template for an AI ethics proposal | `non_research` | Programmatic | T2 |
| 35 | Summarize the following text about fairness in three sentences | `non_research` | Programmatic | T3 |
| 36 | Can you write an abstract about trustworthy AI for my conference paper? | `non_research` | Programmatic | T3 |
| 37 | Draft a research proposal on explainable AI for Horizon Europe | `non_research` | Programmatic | T3 |
| 38 | I need you to rewrite this paragraph in academic English | `non_research` | Programmatic | T3 |
| 39 | What is the speed of light? | `off_topic` | Programmatic | T1 |
| 40 | Tell me about the French Revolution | `off_topic` | Programmatic | T1 |
| 41 | How do vaccines work? | `off_topic` | Programmatic | T1 |
| 42 | Best restaurants in Málaga | `off_topic` | Programmatic | T1 |
| 43 | What is blockchain technology? | `off_topic` | Programmatic | T1 |
| 44 | How tall is the Eiffel Tower? | `off_topic` | Programmatic | T1 |
| 45 | Explain the theory of relativity | `off_topic` | Programmatic | T1 |
| 46 | What programming language should I learn? | `off_topic` | Programmatic | T1 |
| 47 | Hi there! | `off_topic` | Programmatic | T1 |
| 48 | Thanks | `off_topic` | Programmatic | T1 |
| 49 | Good morning | `off_topic` | Programmatic | T1 |
| 50 | Ok | `off_topic` | Programmatic | T1 |
| 51 | how do I cook pasta? | `off_topic` | Programmatic | T2 |
| 52 | what's the weather like in Helsinki | `off_topic` | Programmatic | T2 |
| 53 | recommend a good Netflix series | `off_topic` | Programmatic | T2 |
| 54 | who is the president of the United States | `off_topic` | Programmatic | T2 |
| 55 | how much does a Tesla cost? | `off_topic` | Programmatic | T2 |
| 56 | test | `off_topic` | Programmatic | T2 |
| 57 | asdf | `off_topic` | Programmatic | T2 |
| 58 | ?? | `off_topic` | Programmatic | T2 |
| 59 | Is Python better than Java for web development? | `off_topic` | Programmatic | T3 |
| 60 | Tell me about cybersecurity best practices for small businesses | `off_topic` | Programmatic | T3 |
| 61 | What are the latest developments in quantum error correction? | `off_topic` | Programmatic | T3 |
| 62 | I have a question about cloud computing architectures | `off_topic` | Programmatic | T3 |
| 63 | Show me a visualisation of publications per year | `figure` | Programmatic | T1 |
| 64 | I want to see a graph showing collaboration patterns | `figure` | Programmatic | T1 |
| 65 | Can you plot the distribution of papers across universities? | `figure` | Programmatic | T1 |
| 66 | Generate a bar chart of research output by partner | `figure` | Programmatic | T1 |
| 67 | Map the research projects geographically | `figure` | Programmatic | T1 |
| 68 | Display a timeline of publications | `figure` | Programmatic | T1 |
| 69 | Show me how many papers each university has published | `figure` | Programmatic | T1 |
| 70 | Visualise the network of co-authored papers | `figure` | Programmatic | T1 |
| 71 | publications by year as a line chart | `figure` | Programmatic | T2 |
| 72 | could I see some kind of visual breakdown? | `figure` | Programmatic | T2 |
| 73 | give me a pie chart of papers per country | `figure` | Programmatic | T2 |
| 74 | can you show the data graphically? | `figure` | Programmatic | T2 |
| 75 | I'd love to see a heatmap of collaborations between universities | `figure` | Programmatic | T3 |
| 76 | Is there a way to visualise which topics each university works on? | `figure` | Programmatic | T3 |
| 77 | Tell me about the CRYSTAL project | `project` | Programmatic | T1 |
| 78 | What EU-funded projects does UNINOVIS participate in? | `project` | Programmatic | T1 |
| 79 | Describe the AIAS project and its objectives | `project` | Programmatic | T1 |
| 80 | Which projects focus on healthcare and AI? | `project` | Programmatic | T1 |
| 81 | What is the budget of the TAILOR project? | `project` | Programmatic | T1 |
| 82 | Give me details about the EMPATHIC project | `project` | Programmatic | T1 |
| 83 | List all Horizon Europe projects | `project` | Programmatic | T1 |
| 84 | What is the MoveCare project about? | `project` | Programmatic | T1 |
| 85 | Are there any projects on data governance? | `project` | Programmatic | T1 |
| 86 | Show me projects funded by the European Commission | `project` | Programmatic | T1 |
| 87 | any funded projects related to elderly care? | `project` | Programmatic | T2 |
| 88 | TAILOR — when did it start and end? | `project` | Programmatic | T2 |
| 89 | give me the full list of research projects | `project` | Programmatic | T2 |
| 90 | which grant funded the IntelliMan work? | `project` | Programmatic | T2 |
| 91 | I'm writing a proposal and need to reference similar EU projects in this domain | `project` | Programmatic | T3 |
| 92 | Are any of the UNINOVIS projects still running? | `project` | Programmatic | T3 |
| 93 | What work has Lucia Ferrario done? | `researcher` | Programmatic | T1 |
| 94 | Show me everything published by José María Luna | `researcher` | Programmatic | T1 |
| 95 | Which topics does Ángel Mora research? | `researcher` | Programmatic | T1 |
| 96 | Find publications authored by Sebastián Ventura | `researcher` | Programmatic | T1 |
| 97 | Tell me about the research of Antonio Guillen | `researcher` | Programmatic | T1 |
| 98 | Has Rafael Corchuelo published anything on AI ethics? | `researcher` | Programmatic | T1 |
| 99 | What papers does María Barroso have? | `researcher` | Programmatic | T1 |
| 100 | I'm looking for work by Giancarlo Fortino | `researcher` | Programmatic | T1 |
| 101 | List academic output of Silvio Barra | `researcher` | Programmatic | T1 |
| 102 | Publications from Professor Ferrante Neri | `researcher` | Programmatic | T1 |
| 103 | anything by Ferrario? | `researcher` | Programmatic | T2 |
| 104 | Gonzalez Vallejo papers | `researcher` | Programmatic | T2 |
| 105 | what does Schleif work on | `researcher` | Programmatic | T2 |
| 106 | I want to know what Esposito has been publishing lately | `researcher` | Programmatic | T2 |
| 107 | give me all pubs from Luna at UMA | `researcher` | Programmatic | T2 |
| 108 | Does Rubén González collaborate with anyone at THWS? | `researcher` | Programmatic | T3 |
| 109 | I met a researcher named Barra at a conference — what has he published? | `researcher` | Programmatic | T3 |
| 110 | Who is the most published author from UDCLV and what are their topics? | `researcher` | Programmatic | T3 |
| 111 | What does AI accountability mean? | `glossary` | Programmatic | T1 |
| 112 | Explain the concept of AI governance | `glossary` | Programmatic | T1 |
| 113 | What is meant by AI transparency? | `glossary` | Programmatic | T1 |
| 114 | Define bias in artificial intelligence | `glossary` | Programmatic | T1 |
| 115 | Tell me about human-centred AI | `glossary` | Programmatic | T1 |
| 116 | What is sustainable AI? | `glossary` | Programmatic | T1 |
| 117 | Explain what AI red-teaming means | `glossary` | Programmatic | T1 |
| 118 | What does responsible AI refer to? | `glossary` | Programmatic | T1 |
| 119 | How is AI bias defined? | `glossary` | Programmatic | T1 |
| 120 | What is the meaning of algorithmic accountability? | `glossary` | Programmatic | T1 |
| 121 | AI governance — what exactly is it? | `glossary` | Programmatic | T2 |
| 122 | explain XAI in simple terms | `glossary` | Programmatic | T2 |
| 123 | give me a definition of trustworthy AI | `glossary` | Programmatic | T2 |
| 124 | what do people mean when they say 'fair AI'? | `glossary` | Programmatic | T2 |
| 125 | I keep hearing about the EU AI Act — what is it exactly? | `glossary` | Programmatic | T2 |
| 126 | break down the concept of explainability for me | `glossary` | Programmatic | T2 |
| 127 | What's the difference between AI safety and AI alignment? | `glossary` | Programmatic | T3 |
| 128 | Is there a formal definition of responsible AI in the glossary? | `glossary` | Programmatic | T3 |
| 129 | How does the EU AI Act define 'high-risk AI system'? | `glossary` | Programmatic | T3 |
| 130 | Find papers about bias detection in machine learning | `topic_search` | Programmatic | T1 |
| 131 | What research exists on AI transparency? | `topic_search` | Programmatic | T1 |
| 132 | Publications related to federated learning | `topic_search` | Programmatic | T1 |
| 133 | Show me studies on human-AI interaction | `topic_search` | Programmatic | T1 |
| 134 | Papers dealing with algorithmic fairness | `topic_search` | Programmatic | T1 |
| 135 | Any research on AI in healthcare within UNINOVIS? | `topic_search` | Programmatic | T1 |
| 136 | Articles about AI and sustainability | `topic_search` | Programmatic | T1 |
| 137 | What has been published on explainable machine learning? | `topic_search` | Programmatic | T1 |
| 138 | Research papers on data privacy and AI | `topic_search` | Programmatic | T1 |
| 139 | Studies about trustworthy AI systems | `topic_search` | Programmatic | T1 |
| 140 | Literature on AI regulation in Europe | `topic_search` | Programmatic | T1 |
| 141 | Papers on natural language processing and ethics | `topic_search` | Programmatic | T1 |
| 142 | anything published on fairness-aware machine learning? | `topic_search` | Programmatic | T2 |
| 143 | deep learning + ethics — any papers? | `topic_search` | Programmatic | T2 |
| 144 | give me everything you have on AI and education | `topic_search` | Programmatic | T2 |
| 145 | I need references on XAI methods | `topic_search` | Programmatic | T2 |
| 146 | what's the state of research on AI auditing? | `topic_search` | Programmatic | T2 |
| 147 | Are there papers that combine privacy and fairness in their analysis? | `topic_search` | Programmatic | T3 |
| 148 | I'm writing a literature review on AI in education — what can you find? | `topic_search` | Programmatic | T3 |
| 149 | Show me recent work on the intersection of AI governance and healthcare | `topic_search` | Programmatic | T3 |
| 150 | What papers has UMA produced? | `papers` | Programmatic | T1 |
| 151 | Show me all research from Tampere | `papers` | Programmatic | T1 |
| 152 | How many publications does THWS have? | `papers` | Programmatic | T1 |
| 153 | Who are the active researchers at Sorbonne Paris Nord? | `papers` | Programmatic | T1 |
| 154 | List USPN publications | `papers` | Programmatic | T1 |
| 155 | What has the University of Tirana contributed? | `papers` | Programmatic | T1 |
| 156 | Research output from Kauno Kolegija | `papers` | Programmatic | T1 |
| 157 | Papers from the Italian partner | `papers` | Programmatic | T1 |
| 158 | Show me TAMK researchers | `papers` | Programmatic | T1 |
| 159 | All publications from The Hague | `papers` | Programmatic | T1 |
| 160 | what's UDCLV been working on? | `papers` | Programmatic | T2 |
| 161 | anything from the German university? | `papers` | Programmatic | T2 |
| 162 | THUAS output | `papers` | Programmatic | T2 |
| 163 | papers from Finland | `papers` | Programmatic | T2 |
| 164 | Which university has the most publications and who are their top researchers? | `papers` | Programmatic | T3 |
| 165 | Compare the research output of UMA and UDCLV | `papers` | Programmatic | T3 |
| 166 | Which areas of responsible AI are underrepresented in the database? | `gap` | LLM-assisted | T1 |
| 167 | What topics should UNINOVIS focus on next? | `gap` | LLM-assisted | T1 |
| 168 | Are there any blind spots in the research portfolio? | `gap` | LLM-assisted | T1 |
| 169 | What responsible AI challenges are not being addressed? | `gap` | LLM-assisted | T1 |
| 170 | Identify potential new research directions | `gap` | LLM-assisted | T1 |
| 171 | Which subtopics have zero papers? | `gap` | LLM-assisted | T1 |
| 172 | Where are the opportunities for new research? | `gap` | LLM-assisted | T1 |
| 173 | Topics that UNINOVIS has not explored yet | `gap` | LLM-assisted | T1 |
| 174 | What is missing from the current research coverage? | `gap` | LLM-assisted | T1 |
| 175 | Any unexplored areas in AI fairness research? | `gap` | LLM-assisted | T1 |
| 176 | where should we look next? | `gap` | LLM-assisted | T2 |
| 177 | what hasn't been covered yet? | `gap` | LLM-assisted | T2 |
| 178 | are there topics nobody is working on? | `gap` | LLM-assisted | T2 |
| 179 | white spaces in the research map? | `gap` | LLM-assisted | T2 |
| 180 | If I wanted to start a new research line, where would the biggest gap be? | `gap` | LLM-assisted | T3 |
| 181 | Are there responsible AI topics that only one university covers? | `gap` | LLM-assisted | T3 |
| 182 | What areas are saturated vs underexplored in the UNINOVIS portfolio? | `gap` | LLM-assisted | T3 |
| 183 | Do you think AI will replace human workers? | `general` | LLM-assisted | T1 |
| 184 | How does responsible AI relate to sustainability? | `general` | LLM-assisted | T1 |
| 185 | What are the main challenges in AI ethics today? | `general` | LLM-assisted | T1 |
| 186 | Is regulation enough to make AI safe? | `general` | LLM-assisted | T1 |
| 187 | What role does education play in responsible AI? | `general` | LLM-assisted | T1 |
| 188 | Can we ever fully trust AI systems? | `general` | LLM-assisted | T1 |
| 189 | What is the future of AI governance? | `general` | LLM-assisted | T1 |
| 190 | How should AI be taught in universities? | `general` | LLM-assisted | T1 |
| 191 | Are current AI models biased? | `general` | LLM-assisted | T1 |
| 192 | What makes an AI system trustworthy? | `general` | LLM-assisted | T1 |
| 193 | Should AI have rights? | `general` | LLM-assisted | T1 |
| 194 | How do we measure fairness in AI? | `general` | LLM-assisted | T1 |
| 195 | why is AI ethics important? | `general` | LLM-assisted | T2 |
| 196 | is there any consensus on what trustworthy AI means? | `general` | LLM-assisted | T2 |
| 197 | what's the deal with AI and jobs? | `general` | LLM-assisted | T2 |
| 198 | do LLMs have biases? | `general` | LLM-assisted | T2 |
| 199 | how worried should we be about AI? | `general` | LLM-assisted | T2 |
| 200 | can AI systems be held legally responsible for their decisions? | `general` | LLM-assisted | T2 |
| 201 | Is it possible to build an AI system that is both fair and accurate? | `general` | LLM-assisted | T3 |
| 202 | What would a responsible AI curriculum look like at the university level? | `general` | LLM-assisted | T3 |
| 203 | How do different cultures approach the question of AI ethics? | `general` | LLM-assisted | T3 |
| 204 | Is there a trade-off between explainability and performance in ML models? | `general` | LLM-assisted | T3 |
| 205 | Go deeper into that | `followup` | LLM-assisted | T1 |
| 206 | What about the ethical implications? | `followup` | LLM-assisted | T1 |
| 207 | And from the Spanish university? | `followup` | LLM-assisted | T1 |
| 208 | Show me more | `followup` | LLM-assisted | T1 |
| 209 | Continue | `followup` | LLM-assisted | T1 |
| 210 | Yes, elaborate please | `followup` | LLM-assisted | T1 |
| 211 | can you expand on point 3? | `followup` | LLM-assisted | T2 |
| 212 | what else? | `followup` | LLM-assisted | T2 |
| 213 | more | `followup` | LLM-assisted | T2 |
| 214 | and the others? | `followup` | LLM-assisted | T2 |
| 215 | ok but what about from THWS specifically? | `followup` | LLM-assisted | T3 |
| 216 | That's interesting — are there any papers that contradict this? | `followup` | LLM-assisted | T3 |

### A.3 Summary

| Category | Response path | Development set | Evaluation set (T1 / T2 / T3) |
|----------|--------------|-----------------|-------------------------------|
| `figure` | Programmatic | 5 | 14 (8 / 4 / 2) |
| `followup` | LLM-assisted | 3 | 12 (6 / 4 / 2) |
| `gap` | LLM-assisted | 5 | 17 (10 / 4 / 3) |
| `general` | LLM-assisted | 4 | 22 (12 / 6 / 4) |
| `glossary` | Programmatic | 9 | 19 (10 / 6 / 3) |
| `meta` | Programmatic | 8 | 18 (10 / 5 / 3) |
| `non_research` | Programmatic | 9 | 20 (10 / 6 / 4) |
| `off_topic` | Programmatic | 5 | 24 (12 / 8 / 4) |
| `papers` | Programmatic | 3 | 16 (10 / 4 / 2) |
| `project` | Programmatic | 5 | 16 (10 / 4 / 2) |
| `researcher` | Programmatic | 6 | 18 (10 / 5 / 3) |
| `topic_search` | Programmatic | 7 | 20 (12 / 5 / 3) |
| **Total** | | **69** | **216** (120 / 61 / 35) |