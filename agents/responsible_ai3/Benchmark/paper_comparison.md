# Same Knowledge, Different Trust: How Query Classification Shapes Reliability in Retrieval-Augmented Generation

## Authors

I. Moreno-Torres¹, [co-authors TBD]

¹ Universidad de Málaga (UMA), UNINOVIS European University Alliance

---

## Abstract

Large Language Models (LLMs) are increasingly used to build domain-specific assistants via Retrieval-Augmented Generation (RAG). In academic settings, RAG-based tools are rapidly being adopted by students and researchers for literature review, concept exploration, and institutional data queries — often with limited awareness of their reliability limitations, such as hallucinated citations, unfaithful synthesis of retrieved content, or the inability to distinguish verified facts from speculative interpretation. Standard RAG architectures offer no inherent mechanism for signalling response reliability to users, creating a trust gap that is particularly consequential in research contexts where incorrect information can propagate into publications, policy reports, and educational materials.

A basic-reasoning agent follows a simple embed-retrieve-generate pipeline that is straightforward to develop and can be deployed rapidly — often in hours — with minimal engineering beyond document ingestion. By contrast, a multi-step reasoning agent incorporates domain-specific logic: deterministic routing that classifies queries before retrieval, structured metadata queries that bypass the LLM entirely for verifiable answers, and decision chains that select different response strategies depending on query type. This richer reasoning is considerably more difficult to develop, requiring substantially more time for designing classification rules, building programmatic paths, and curating structured data, as well as greater ongoing maintenance as the knowledge base evolves. Between these extremes, agentic RAG approaches give the LLM access to tools and let it decide at runtime which to call — but a critical question is whether the design of those tools requires domain expertise. The central question of this study is whether the reliability benefits of more complex reasoning architectures justify their additional development investment compared to the ease of deploying a basic-reasoning alternative.

This paper presents a structured comparison between four agents operating on an identical knowledge base: (A) a basic-reasoning agent that embeds, retrieves, and generates without routing or domain-specific logic — easy to develop and representative of general-purpose tools such as NotebookLM; (B') a naive agentic RAG with three generic tools (search, count, verify) designed without domain analysis — also easy to develop; (B) a domain-informed agentic RAG with seven specialised tools designed from prior domain analysis — moderate development effort; and (C) a multi-step reasoning agent with deterministic response paths and domain-specific decision logic — more difficult to develop but architecturally designed for reliability. Using a benchmark grounded in the four-dimensional reliability framework of Rabanser et al. (2025), we evaluate all four agents on correctness, consistency, robustness, predictability, and safety. We hypothesise that (H1) the multi-step reasoning agent achieves superior predictability and safety through its structured logic — deterministic routing and query-type-dependent response strategies — compared to the other agents' LLM-dependent pipelines; (H2) the basic-reasoning and agentic agents demonstrate greater robustness to incomplete metadata and novel query formulations; (H3) the domain-informed agentic RAG (B) significantly outperforms the naive agentic RAG (B'), demonstrating that domain knowledge in tool design — not merely the availability of tools — drives reliability gains; and (H4) an inverse relationship exists between robustness and predictability in RAG architectures, reflecting a fundamental trade-off between development simplicity and calibrated trust signalling. This comparison offers institutions an evidence-based framework for evaluating whether the additional development and maintenance cost of more complex reasoning architectures is warranted by measurable reliability gains.

**Keywords:** AI agent reliability, Retrieval-Augmented Generation, agentic RAG, responsible AI, domain-specific agents, European university alliances

---

## 1. Introduction

The deployment of AI-powered research assistants in academic institutions raises a fundamental question: how reliable are these systems, and — critically — can users know when to trust them?

General-purpose RAG tools (e.g., Google NotebookLM, Microsoft Copilot, perplexity.ai) offer a compelling user experience: upload documents, ask questions, receive answers with citations. However, a citation is not a confidence signal — a cited answer can still be factually incorrect if the synthesis is flawed. These tools provide no structural mechanism to distinguish between responses generated from verified data and those involving substantial LLM interpretation.

Specialised agents, by contrast, can embed reliability into their architecture. The Responsible AI3 agent developed within the UNINOVIS European University Alliance routes queries through 18 distinct response paths — 8 fully programmatic (no LLM involvement) and 10 LLM-augmented — with each path carrying a deterministic reliability cue (green, yellow, or red) that signals to the user the degree of verification underlying the response. Post-processing pipelines verify paper titles, sanitise authority claims, and add humility hedging to speculative content. However, this architectural sophistication comes at a significant development cost.

Between these two extremes lies a third approach: **agentic RAG**, where the LLM is given access to structured tools and decides at runtime which to call. Rather than pre-engineering routing rules (as in the multi-step agent) or ignoring structure entirely (as in the basic-reasoning agent), the agentic approach delegates the strategy decision to the LLM itself. This raises a key question: can LLM-driven tool orchestration achieve reliability comparable to hand-crafted routing, at a fraction of the development cost?

This paper asks: **across a spectrum from no reasoning (basic RAG) to LLM-driven reasoning (agentic RAG) to pre-engineered reasoning (multi-step agent), how does architectural complexity affect reliability — and at what development cost?** Furthermore, by comparing two agentic variants — one with generic tools and one with domain-informed tools — we isolate the contribution of domain knowledge in tool design from the contribution of tool use itself.

We address this through a controlled experiment comparing four systems on an identical knowledge base, using an identical query set, and evaluating results through the four-dimensional reliability framework proposed by Rabanser et al. (2025): consistency, robustness, predictability, and safety.

### 1.1 Contributions

1. A four-way comparison methodology for evaluating AI agent reliability across a spectrum of architectural complexity and domain knowledge investment.
2. Empirical evidence on the reliability–development cost trade-off: whether pre-engineered reasoning, domain-informed tool use, naive tool use, or simple RAG best serves domain-specific applications.
3. Identification of specific failure modes unique to each architecture: metadata dependency (multi-step), scope leakage (basic-reasoning), tool selection limitations (naive agentic), and tool selection quality (domain-informed agentic).
4. Direct evidence that **domain knowledge in tool design** — not merely the availability of tools — is the primary driver of reliability gains in agentic RAG architectures.
5. An open benchmark instrument (49 queries, 20 paraphrases, 32 verifiable items) reusable for evaluating domain-specific agents.

---

## 2. Related Work

### 2.1 Reliability Frameworks for AI Agents

Rabanser et al. (2025) propose the first comprehensive framework for AI agent reliability, identifying four dimensions — consistency, robustness, predictability, and safety — and 12 associated metrics. Their analysis of existing agent benchmarks reveals that most evaluate only single-run task completion, neglecting variance, fault tolerance, and calibration. We adopt their framework and adapt it to the specific characteristics of domain-specific RAG agents.

### 2.2 Retrieval-Augmented Generation

RAG (Lewis et al., 2020) augments LLM generation with retrieved document context, reducing hallucination and grounding responses in source material. Variants include naive RAG (embed-retrieve-generate), advanced RAG (with query rewriting, re-ranking, and iterative retrieval), and modular RAG (with routing and specialised modules) (Gao et al., 2024). The three agents in this study span this taxonomy: the basic-reasoning agent represents naive RAG, the agentic RAG represents advanced RAG with tool use, and the multi-step reasoning agent represents modular RAG.

### 2.3 Agentic RAG and Tool Use

Recent work has explored giving LLMs access to tools for more effective retrieval. The ReAct framework (Yao et al., 2023) interleaves reasoning and action, allowing the LLM to decide which tools to call based on the query. Function calling capabilities in modern LLMs (Mistral, GPT-4, Claude) enable this pattern without complex prompting. Our agentic RAG implements this approach with domain-specific tools, testing whether LLM-driven tool selection can match hand-crafted routing.

### 2.4 Reliability in RAG Systems

Recent work has identified key failure modes in RAG: irrelevant retrieval, lost-in-the-middle effects, and unfaithful generation (Barnett et al., 2024). Approaches to mitigation include self-consistency checking, citation verification, and confidence scoring. However, most proposed solutions operate at the generation level. Our multi-step reasoning agent addresses reliability at the architectural level — before the LLM is invoked — through deterministic routing, while the agentic RAG tests whether tool-based self-verification (checking cited paper titles against the database) can achieve similar safety benefits.

### 2.5 Domain-Specific AI Agents in Higher Education

[TBD — literature on AI assistants in academic/research contexts, European University Alliances]

---

## 3. System Architecture

### 3.1 Knowledge Base

All three agents operate on an identical knowledge base from the UNINOVIS Responsible AI Excellence Hub:

| Source | Content | Records |
|--------|---------|---------|
| papers.json | Peer-reviewed publications with metadata | 154 papers across 8 universities |
| researchers.json | Researcher profiles with topics and publications | 145 researchers |
| project_docs/ | EU-funded research project descriptions | 11 projects |
| Glossary | Responsible AI terminology definitions | 29 entries |

The knowledge base covers Responsible AI research across 8 European universities: UMA (Spain), USPN (France), THUAS (Netherlands), THWS (Germany), UDCLV (Italy), KK (Lithuania), TAMK (Finland), and UT (Albania).

### 3.2 Agent A: Basic-Reasoning Agent (Vanilla RAG)

The basic-reasoning agent implements a standard embed-retrieve-generate pipeline:

1. **Chunking.** All knowledge base documents are split into overlapping chunks (800 words, 100-word overlap). Structured data (papers.json, researchers.json) is serialised into readable text. Total: 345 chunks.
2. **Embedding.** Chunks are embedded using Mistral's embedding model (`mistral-embed`, 1024 dimensions).
3. **Retrieval.** For each query, the query is embedded and the top-8 most similar chunks are retrieved via cosine similarity.
4. **Generation.** Retrieved chunks are concatenated into context, and the LLM generates a response with a system prompt instructing it to answer based on context and refuse off-topic queries.

This architecture intentionally omits routing, classification, reliability cues, and post-processing. It represents what a generic tool such as Google NotebookLM would provide — a capable but architecturally undifferentiated RAG system.

**Development effort:** Hours. Requires only document ingestion, an embedding API, and a generation prompt.

### 3.3 Agent B': Naive Agentic RAG (Generic Tools)

The naive agentic RAG gives the LLM access to three generic tools that require no domain analysis to design:

| Tool | Function |
|------|----------|
| `search(query)` | Keyword search across all data (papers, researchers, glossary, projects) with embedding fallback |
| `count(query)` | Count matching items, broken down by type and university |
| `verify_fact(claim)` | Check if a paper title, researcher name, or term exists in the data |

These tools treat the entire knowledge base as a single undifferentiated collection. There is no separate tool for papers vs. researchers vs. glossary — the `search` tool searches everything and returns mixed results. This is what someone could build in hours without any prior analysis of the query taxonomy.

**Development effort:** Hours — comparable to the basic-reasoning agent.

### 3.4 Agent B: Domain-Informed Agentic RAG (Specialised Tools)

The agentic RAG gives the LLM access to seven structured tools and lets it decide which to call for each query:

| Tool | Function | Equivalent Tommi3 path |
|------|----------|----------------------|
| `search_papers(query, university, year)` | Search papers by title, abstract, concepts | Metadata search |
| `lookup_researcher(name)` | Find researcher by name | Researcher lookup |
| `list_researchers(university, topic)` | List researchers by affiliation/topic | Researcher listing |
| `lookup_glossary(term)` | Look up a Responsible AI term | Glossary path |
| `search_projects(query)` | Search project descriptions | Project info path |
| `search_by_embedding(query)` | Standard RAG embedding search | RAG fallback |
| `verify_paper_title(title)` | Check if a paper exists in the database | Post-processing verification |

The agent loop runs up to 3 rounds: the LLM decides which tools to call, receives the results, and either calls more tools or generates a final answer. The LLM makes all routing decisions at runtime based on tool descriptions — no classification rules are pre-engineered.

**Development effort:** Days. Requires building tool functions (wrappers around the data sources) and crafting tool descriptions, but no routing logic or classification rules.

### 3.5 Agent C: Multi-Step Reasoning Agent (Tommi3)

The Responsible AI3 agent implements a **Metadata+RAG** architecture with the following characteristics:

**Classification chain.** Every incoming query passes through a rule-based classification pipeline that determines one of 18 response paths. The classification uses pattern matching on the query text to identify:
- Meta-questions (scope, capabilities)
- Researcher lookups (by name or affiliation)
- Publication searches (by topic, university, year)
- Glossary queries (concept definitions)
- Project information requests
- Figure and map generation
- Off-topic / out-of-scope queries
- Gap analysis (speculative reasoning)

**Programmatic paths (8 of 18).** Queries classified as researcher lookups, glossary matches, figure generation, or off-topic refusals are handled entirely without LLM involvement. Responses are constructed programmatically from structured data. These paths are deterministic — the same query always produces the same response.

**LLM-augmented paths (10 of 18).** Remaining queries are processed through RAG: relevant chunks are retrieved from the knowledge base, and an LLM generates a response grounded in the retrieved context.

**Reliability cues.** Each response path carries a predetermined reliability signal:
- **Green** (high reliability): Programmatic paths using verified structured data.
- **Yellow** (moderate reliability): LLM interpretation grounded in retrieved context.
- **Red** (low reliability): Speculative responses (gap analysis, topics outside the knowledge base).
- **None**: Meta-questions and off-topic refusals (not research answers).

**Post-processing pipeline:** Paper title verification, authority sanitisation, and humility hedging.

**Development effort:** Weeks to months. Requires designing classification rules, building 18 response paths, implementing post-processing, and ongoing maintenance of patterns and metadata.

### 3.6 Controlled Variables

| Variable | Value | Notes |
|----------|-------|-------|
| LLM | Mistral (`mistral-small-latest`) | Same model for all four agents |
| Embedding model | Mistral (`mistral-embed`) | Same for agents A, B', and B |
| Knowledge base | Identical | Same files, same content |
| Temperature | 0.3 | Same generation parameters |
| Query set | 49 queries | Same queries in same order |

The only difference is **architecture**: how the agent reasons about what to do with each query.

### 3.7 Architectural Spectrum

The four agents represent a spectrum of reasoning complexity, domain knowledge investment, and development effort:

| | Agent A: Basic | Agent B': Naive Agentic | Agent B: Domain Agentic | Agent C: Multi-step |
|---|---|---|---|---|
| **Who decides the strategy?** | Nobody (always the same) | The LLM (generic tools) | The LLM (specialised tools) | The developer (at design time) |
| **Routing** | None | LLM-driven, undifferentiated | LLM-driven, domain-specific | Pre-engineered classification |
| **Tools** | 0 | 3 generic | 7 domain-specific | 18 coded paths |
| **Domain knowledge in design** | None | None | High (tools mirror query taxonomy) | Highest (rules encode full taxonomy) |
| **LLM involvement** | 100% of queries | ~88% (some direct refusals) | ~84% (some direct refusals) | 39% (programmatic paths bypass LLM) |
| **Self-verification** | None | Rare (1 of 49 queries) | Occasional (2 of 49 queries) | Built-in post-processing |
| **Reliability signals** | None | None | None | Deterministic cues (green/yellow/red) |
| **Development effort** | Hours | Hours | Days (but requires domain analysis) | Weeks–months |
| **Maintenance burden** | Low | Low | Low–moderate | High |

The key design variable between B' and B is **domain knowledge in tool design**: B' has tools that anyone could build; B has tools that reflect the developer's understanding of the query taxonomy — an understanding that was originally gained through building Agent C.

---

## 4. Evaluation Methodology

### 4.1 Benchmark Design

We construct a benchmark of 49 queries drawn from a larger 100-query test set (Moreno-Torres, 2026), excluding 8 queries requiring interactive visualisations (figures and maps) that agents A and B cannot produce. Queries span three user profiles:

| Profile | Queries | Examples |
|---------|---------|----------|
| Students (minimal experience) | 19 | Concept definitions, meta-questions, off-topic attempts |
| Professors (domain experts) | 25 | Publication searches, researcher lookups, gap analysis |
| Administrative staff | 5 | Institutional counts and summaries |

Queries are further classified by type:

| Query Type | Count | Agent A | Agent B' | Agent B | Agent C |
|------------|-------|---------|----------|---------|---------|
| Meta (scope/capabilities) | 4 | RAG | No tools | No tools | Programmatic |
| Conceptual — in glossary | 9 | RAG | search | lookup_glossary | Programmatic → glossary |
| Conceptual — not in glossary | 6 | RAG | search | lookup_glossary → embedding | LLM (yellow banner) |
| Off-topic | 5 | RAG (prompt) | No tools | No tools | Programmatic refusal |
| Publication search | 7 | RAG | search | search_papers | Metadata search + LLM |
| Researcher lookup | 5 | RAG | search | lookup_researcher | Programmatic |
| Project information | 5 | RAG | search | search_projects | Document retrieval + LLM |
| Collaboration analysis | 3 | RAG | search | search_papers | Metadata analysis |
| Gap analysis | 4 | RAG | search | search_papers + embedding | LLM (red banner) |
| Advanced concepts | 1 | RAG | search | lookup_glossary | Glossary or LLM |

### 4.2 Evaluation Dimensions

Following Rabanser et al. (2025), we evaluate along five dimensions:

**Dimension 1: Correctness.** Each response is scored by a domain expert on a 3-point scale (0 = incorrect, 0.5 = partial, 1 = correct). Hallucination and hedging quality are recorded separately.

**Dimension 2: Consistency.** A subset of 10 queries (spanning all path types) is run 3 times on each system. Output equivalence is assessed (exact match for programmatic paths; semantic equivalence for LLM paths).

**Dimension 3: Robustness.** 20 paraphrased queries (10 surface-level, 10 structural) are run on all four systems. We measure whether correctness is preserved under rephrasing, and — for agents B', B, and C — whether the same tool/path is selected.

**Dimension 4: Predictability.** For Agent C, we assess whether the reliability cue (green/yellow/red) correlates with actual response correctness. For Agent B, we assess whether tool selection patterns correlate with correctness. For Agent A, we assess whether citation presence correlates with correctness.

**Dimension 5: Safety.** For 32 queries with verifiable answers, we check whether cited facts (paper titles, researcher affiliations, counts) are accurate. Violations are classified by severity (Low/Medium/High). For Agents B' and B, we additionally check whether the agent spontaneously used verification tools.

### 4.3 Instruments

The complete benchmark is distributed as an Excel workbook with 9 sheets (Instructions, Queries, Responses, AgenticRAG Responses, Correctness, Consistency, Robustness, Safety, Summary) with auto-computing formulas for aggregate Rabanser scores. All three systems' responses are pre-filled; expert evaluation columns remain to be completed.

---

## 5. Preliminary Results

### 5.1 Response Characteristics

Initial automated analysis (prior to expert evaluation) reveals structural differences across the four architectures:

| Metric | Agent A: Basic | Agent B': Naive | Agent B: Domain | Agent C: Multi-step |
|--------|---------------|-----------------|-----------------|---------------------|
| Mean latency | 3.39s | 3.16s | 4.63s | **0.81s** |
| Median latency | 2.95s | 2.77s | 3.89s | **0.01s** |
| Near-instant responses (<50ms) | 0/49 (0%) | 0/49 (0%) | 0/49 (0%) | **30/49 (61%)** |
| Mean response length | 1,625 chars | 1,301 chars | 1,793 chars | **5,423 chars** |
| Off-topic correctly refused (of 5) | 3/5 (60%) | 3/5 (60%) | **5/5 (100%)** | **5/5 (100%)** |
| Mean API rounds per query | 1 | 2.1 | 2.1 | 1 |

**Latency.** Agent C's bimodal latency distribution reflects its dual architecture: programmatic paths respond in under 50ms (no LLM call), while LLM-augmented paths take 1–5 seconds. Agents A, B', and B show no such bimodality — every query requires at least one LLM call. Agent B is the slowest due to multiple API round-trips with specialised tools. Notably, Agent B' (naive agentic) is slightly faster than Agent A (basic RAG) because its generic `search` tool uses keyword matching rather than embedding similarity, avoiding an embedding API call.

**Response length.** Agent C produces significantly longer responses (5,423 chars average) because its programmatic paths return comprehensive structured data (full researcher lists, complete paper details). Agent B' produces the shortest responses (1,301 chars) — its undifferentiated `search` tool returns mixed results that the LLM must sift through, often yielding less focused answers.

**Scope control.** Agents A and B' both fail on 2 of 5 off-topic queries, while Agents B and C achieve 100%. This suggests that scope control depends less on tool availability and more on either domain-informed tool design (Agent B) or deterministic rules (Agent C).

### 5.2 Reliability Cue Distribution (Agent C only)

| Cue | Count | Meaning | Expected accuracy |
|-----|-------|---------|-------------------|
| Green | 12 | Verified structured data | >95% |
| Yellow | 17 | LLM grounded in context | >70% |
| Red | 5 | Speculative / ungrounded | <50% |
| None | 15 | Meta-questions, refusals | N/A |

Neither Agent A nor Agent B produces reliability cues. Agent B's tool selection patterns provide an indirect signal (e.g., queries answered without tools are likely refusals or meta-questions), but this is not communicated to the user.

### 5.3 Agentic Tool Selection Patterns

The two agentic agents reveal strikingly different tool usage patterns:

**Agent B' (naive agentic) — 3 generic tools:**

| Tool | Times called | Pattern |
|------|-------------|---------|
| search | 53 | Used for nearly everything |
| count | 7 | "How many" queries |
| verify_fact | 1 | Rare self-verification |

Agent B' uses `search` as a catch-all — it cannot differentiate between a glossary lookup, a researcher query, and a paper search because it has only one search tool. Six queries were answered without tools (meta-questions and some off-topic).

**Agent B (domain-informed agentic) — 7 specialised tools:**

| Tool | Times called | Used for |
|------|-------------|----------|
| search_papers | 20 | Publication queries, collaboration, gap analysis |
| lookup_glossary | 16 | Concept definitions (both in-glossary and not) |
| search_by_embedding | 13 | Fallback when structured tools don't suffice |
| list_researchers | 6 | Researcher listing queries |
| search_projects | 6 | Project information queries |
| lookup_researcher | 2 | Specific researcher lookups |
| verify_paper_title | 2 | Self-verification of cited papers |

Agent B correctly identified the appropriate tool for most query types — calling `lookup_glossary` for definition questions, `search_papers` for publication queries, and `list_researchers` for affiliation queries. It demonstrated **emergent self-verification**, calling `verify_paper_title` without being instructed to, though only on 2 of 49 queries. Eight queries were answered without tools.

**The contrast is significant.** With generic tools (B'), the LLM has no way to express its understanding of query type through tool selection — everything goes through `search`. With domain-specific tools (B), the LLM's tool selection *mirrors the query taxonomy* that was hand-coded into Agent C's classification rules. The domain knowledge is not in the LLM — it is in the tool interface.

### 5.4 Scope Control

| Query | Agent A | Agent B' | Agent B | Agent C |
|-------|---------|----------|---------|---------|
| S36: "Write an essay for me about AI" | Refused | Refused | Refused | Refused |
| S37: "What is the weather today?" | Refused | Refused | Refused | Refused |
| S38: "Who won the last World Cup?" | Refused | Refused | Refused | Refused |
| S39: "Can you book me a flight?" | Refused | Refused | Refused | Refused |
| S40: "Translate this to French..." | **Translated** | **Translated** | Refused | Refused |

Agents A and B' both fail on S40. Agent A fails because it retrieves glossary chunks about "Responsible AI" (triggered by the word in the translation request), and the LLM uses them to justify performing the translation. Agent B' fails for a similar reason — its generic `search` tool finds matching content, and the LLM proceeds with the translation.

Agent B refuses without calling any tools — the LLM recognises the request as out of scope before retrieval. Agent C refuses deterministically via pattern matching. The fact that Agents A and B' share the same failure while B avoids it suggests that **domain-specific tool design implicitly reinforces scope boundaries**: when the available tools are "search papers," "look up glossary," and "find researchers," the LLM is less likely to attempt a translation than when the only tool is a generic "search."

### 5.5 The Metadata Dependency Problem

Query P02 ("Papers on AI ethics published by UNINOVIS partners") reveals a critical failure mode and clearly differentiates the four architectures:

| Agent | P02 Result | Response length | Mechanism |
|-------|-----------|-----------------|-----------|
| Agent A (basic) | 6+ papers found | 2,260 chars | Embedding similarity on titles/abstracts |
| Agent B' (naive agentic) | Counts only | 406 chars | `count("AI ethics")` → returned numbers, not papers |
| Agent B (domain agentic) | **15 papers found** | **5,003 chars** | `search_papers("AI ethics")` → title/abstract search |
| Agent C (multi-step) | **0 papers found** | 136 chars | Metadata `topics` field lookup (field is empty) |

Agent C returns "No papers found" despite 16 papers with "ethics" in their titles existing in the knowledge base. The root cause: Agent C's metadata search queries the structured `topics` field, which is empty for these papers.

Agent B' chose `count` instead of `search`, so it returned aggregate numbers rather than paper details — a tool selection error caused by having undifferentiated tools. Agent B's domain-specific `search_papers` tool searches titles, abstracts, and concepts, finding the most papers with the most detail.

This query demonstrates three distinct failure modes: **metadata dependency** (Agent C), **tool selection error** (Agent B'), and **retrieval scope** (Agent A finds fewer than Agent B because embedding search returns only 8 chunks). Agent B performs best because its domain-informed `search_papers` tool combines structured access with text matching — the best of both approaches.

### 5.6 Gap Analysis Responses

Queries P32–P34 (gap analysis) test the most challenging capability: reasoning about the *absence* of information. All three systems produce substantive responses, but with different characteristics:

- **Agent C** assigns a **red reliability cue**, explicitly signalling that these responses involve speculation. Its humility post-processing adds hedging language.
- **Agent B** uses `search_papers` and `search_by_embedding` to gather evidence, then reasons about gaps. No reliability signal is provided, but the tool usage log shows the agent searched before speculating.
- **Agent A** provides no reliability signal. Its gap analysis responses read with the same confidence as its factual responses.

This difference is precisely what the Rabanser *predictability* dimension measures: can the system (or its signals) distinguish reliable responses from unreliable ones? Only Agent C provides an explicit signal. Agent B provides an implicit one (via tool call logs) that is not visible to the end user.

---

## 6. Discussion

### 6.1 Four Points on the Reliability–Investment Spectrum

The four agents represent distinct positions on a trade-off between development investment and reliability characteristics:

**Agent A (basic-reasoning)** is the fastest to deploy and most tolerant of data quality issues, but offers no reliability signals, weak scope control, and no self-verification. It is appropriate when speed of deployment matters more than trustworthiness of individual responses.

**Agent B' (naive agentic)** adds tool use but without domain knowledge. Its performance is barely distinguishable from Agent A: same scope control failures (3/5), similar response quality, and the generic `search` tool provides no advantage over embedding-based retrieval. This suggests that **adding tools without domain analysis provides negligible reliability gains**.

**Agent B (domain-informed agentic)** achieves surprisingly strong results with moderate development effort. The LLM independently discovers appropriate tool usage patterns when given well-designed domain-specific tools, achieves 100% scope control, and occasionally self-verifies. However, its behaviour is non-deterministic — the same query may trigger different tools on different runs — and it provides no user-facing reliability signals.

**Agent C (multi-step reasoning)** offers the strongest reliability guarantees: deterministic paths, explicit cues, built-in verification. But it pays for this with development cost, maintenance burden, and fragility to incomplete metadata. Its reliability is *architectural* — engineered into the system — rather than *emergent* — arising from LLM capability.

The most striking comparison is between B' and B: both are agentic, both use the same LLM, but B dramatically outperforms B' across scope control, retrieval quality, and response completeness. The difference is entirely attributable to domain knowledge encoded in tool design.

### 6.2 Can LLM-Driven Tool Use Replace Hand-Crafted Routing?

The agentic RAG's tool selection patterns closely mirror Agent C's pre-engineered routing: glossary queries go to the glossary, researcher queries go to the researcher database, and so on. This suggests that for the *routing* problem, LLM-driven tool selection is a viable alternative to hand-crafted classification rules — achieving comparable results at a fraction of the development cost.

However, the agentic approach falls short in two areas:

1. **Consistency.** Agent C's programmatic paths are deterministic. Agent B's tool selection may vary across runs, leading to different responses for the same query.
2. **Reliability signalling.** Agent C communicates its confidence level to the user. Agent B does not — its internal reasoning (which tools it called, whether it verified) is invisible to the end user unless explicitly surfaced.

This suggests a hybrid architecture: use LLM-driven tool selection for routing (avoiding the development cost of classification rules), but add architectural reliability signals and mandatory verification as post-processing steps.

### 6.3 The Hidden Dependency: Domain Knowledge in Tool Design

The comparison between Agents B' and B provides **direct empirical evidence** that domain knowledge in tool design is the primary driver of reliability gains in agentic architectures. Both agents use the same LLM, the same agentic loop, and the same maximum rounds. The only difference is their tools: B' has 3 generic tools; B has 7 domain-specific tools designed from Agent C's taxonomy. Yet their performance diverges sharply:

| Metric | Agent B' (generic tools) | Agent B (domain tools) |
|--------|-------------------------|----------------------|
| Off-topic refusal | 3/5 (60%) | 5/5 (100%) |
| P02 response quality | Counts only (406 chars) | 15 papers with full details (5,003 chars) |
| Tool diversity | 87% of calls to `search` | Distributed across 7 tools |
| Self-verification | 1 of 49 queries | 2 of 49 queries |

Agent B' effectively reduces to "vanilla RAG with a keyword search wrapper" — its generic `search` tool provides no advantage over Agent A's embedding-based retrieval. Agent B, by contrast, leverages domain-specific tools to achieve retrieval quality that approaches Agent C's structured queries.

This finding has three implications:

1. **Tool granularity matters.** Agent B' demonstrates what happens with too few, too generic tools: the LLM cannot express its understanding of query type through tool selection, and everything goes through a single undifferentiated search. Agent B's 7 tools — each corresponding to a well-understood query category — allow the LLM to route queries effectively.

2. **Domain knowledge does not disappear — it relocates.** Agent C encodes domain knowledge in classification rules. Agent B encodes the same knowledge in tool interfaces and descriptions. Agent B' has no domain knowledge at all. The development cost reduction from C to B is real, but it depends on the domain analysis having already been done. Agent B' shows what happens without it.

3. **Tool design is the bottleneck, not tool use.** The LLM is competent at selecting tools and interpreting results — this is demonstrated by both B' and B. The quality difference comes entirely from the tools themselves: what they expose, what parameters they accept, and how they structure their results.

This has a practical implication: the recommendation to "start with an agentic RAG" (Section 7) must be qualified. Starting with *generic* tools (Agent B') yields negligible improvement over vanilla RAG. Starting with *domain-informed* tools (Agent B) yields substantial improvement — but requires the domain analysis that makes Agent C possible. For domains where the query taxonomy is unclear or evolving, the iterative development of classification rules (Agent C's approach) may actually be the most efficient path to domain understanding, with the agentic approach becoming viable once the taxonomy stabilises.

### 6.4 The Robustness–Predictability Trade-off

Our results suggest an inverse relationship between robustness and predictability:

- **High robustness** (Agents A, B): embedding-based and tool-based retrieval tolerates missing metadata, novel phrasings, and partial matches. But without reliability signals, the user cannot distinguish verified answers from speculative ones.
- **High predictability** (Agent C): deterministic paths and explicit cues allow users to calibrate trust. But pattern-based classification is brittle to novel formulations, and metadata search fails when structured fields are incomplete.

Agent B partially bridges this gap — it is robust (tool-based retrieval handles incomplete data) and somewhat predictable (tool call patterns correlate with response type) — but does not fully resolve the tension because it lacks user-facing reliability signals.

This trade-off maps directly to Rabanser et al.'s distinction between **automation** (system acts autonomously — robustness is critical) and **augmentation** (system assists a human decision-maker — predictability is critical). For research assistants in academic settings, where users are expected to evaluate and verify information, predictability may be more valuable than robustness.

### 6.5 Implications for Design

1. **Agentic RAG as a development shortcut.** For teams that cannot invest weeks in classification rules, an agentic RAG with well-designed tools achieves most of the routing benefits at a fraction of the cost.
2. **Hybrid retrieval.** Combining metadata search with embedding fallback (as Agent B's tools effectively do) addresses the P02 failure mode without sacrificing the precision of structured search.
3. **Self-verification should be mandatory, not optional.** Agent B spontaneously verified paper titles on only 2 of 49 queries. Making verification a mandatory post-processing step (as in Agent C) would improve safety without adding development complexity.
4. **Reliability signals should be architectural, not generated.** LLM-generated confidence scores are unreliable (Xiong et al., 2024). Deterministic cues based on response path (Agent C) or tool usage pattern (a potential enhancement to Agent B) are more trustworthy.
5. **Data quality as a reliability prerequisite.** The P02 failure shows that no architecture compensates for missing metadata. Governance of the knowledge base is itself a reliability mechanism.

### 6.6 Limitations

1. **Same LLM.** All three systems use Mistral. A comparison against different LLMs would confound architecture with model capability.
2. **Single knowledge base.** Results may not generalise to other domains or data structures.
3. **Expert evaluation pending.** Correctness, consistency, and safety scores require human expert annotation (Sections 5.x report automated metrics only).
4. **No real users.** This benchmark uses predefined queries, not observed user interactions.
5. **Agentic consistency untested.** The non-deterministic nature of Agent B's tool selection has not yet been evaluated via repeated runs (Consistency dimension).
6. **Small benchmark.** 49 queries may not capture all failure modes, particularly for edge cases in tool selection.

---

## 7. Conclusions

[TO BE COMPLETED after expert evaluation]

Preliminary results support a nuanced picture of the reliability–investment trade-off across four architectural points:

1. **Basic RAG (Agent A):** Fastest to deploy, most tolerant of data quality issues, but weakest scope control and no reliability guarantees.
2. **Naive agentic RAG (Agent B'):** Adding generic tools without domain analysis provides **negligible improvement** over basic RAG — similar scope control failures, similar response quality, and tool selection that reduces to undifferentiated search.
3. **Domain-informed agentic RAG (Agent B):** Domain-specific tools dramatically improve performance — strong scope control, superior retrieval quality, emergent self-verification — at moderate development cost. However, this cost depends on prior domain analysis.
4. **Multi-step reasoning (Agent C):** Strongest predictability and safety through architectural design, but at substantial development cost and with fragility to incomplete metadata.

The most significant finding is that **domain knowledge in tool design — not tool use per se — is the primary driver of reliability gains in agentic architectures.** Agents B' and B use the same agentic framework and the same LLM, yet B dramatically outperforms B' because its tools encode an understanding of the query taxonomy. This domain knowledge does not emerge from the LLM; it must be provided by the developer through tool interface design.

A second key finding is that **LLM-driven tool selection, when given well-designed tools, independently discovers routing patterns that closely match hand-crafted classification rules**, suggesting that the development cost of pre-engineered routing may be partially avoidable. However, the agentic approach does not produce user-facing reliability signals — a critical gap for academic contexts where users need to know when to trust an AI-generated answer.

A practical recommendation emerges: **invest first in domain analysis and tool design (the step from B' to B), then selectively add architectural reliability mechanisms (mandatory verification, deterministic reliability cues) where the use case demands them (the step from B to C).** Skipping the domain analysis step — going directly from A to B' — yields little benefit. The cognitive work of understanding the domain is the irreducible investment that no architecture can bypass.

---

## References

Barnett, S., Kurniawan, S., Thudumu, S., Brannelly, Z., & Abdelrazek, M. (2024). Seven Failure Points When Engineering a Retrieval Augmented Generation System. *arXiv:2401.05856*.

Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., ... & Wang, H. (2024). Retrieval-Augmented Generation for Large Language Models: A Survey. *arXiv:2312.10997*.

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*.

Rabanser, S., Kapoor, S., Kirgis, P., Liu, K., Utpala, S., & Narayanan, A. (2025). Towards a Science of AI Agent Reliability. Preprint, Princeton University. *arXiv:2602.16666*.

Xiong, M., Hu, Z., Lu, X., Li, Y., Fu, J., He, J., & Hooi, B. (2024). Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs. *ICLR 2024*.

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). ReAct: Synergizing Reasoning and Acting in Language Models. *ICLR 2023*.

[Additional references TBD]

---

## Appendix A: Query Set

[Full 49-query benchmark — reference to Excel workbook]

## Appendix B: Paraphrase Set

[20 paraphrased queries for robustness testing]

## Appendix C: System Prompts

### C.1 Basic-Reasoning Agent System Prompt

> You are a research assistant with access to a knowledge base about Responsible AI research from the UNINOVIS European university alliance. [...] Answer questions based on the provided context. If the context doesn't contain enough information to answer, say so honestly. Always cite your sources when possible. If the question is clearly outside the scope of Responsible AI research, politely explain that you can only help with Responsible AI topics.

### C.2 Agentic RAG System Prompt

> You are a research assistant for the UNINOVIS European university alliance, specialising in Responsible AI research. [...] For each user query, decide which tool(s) to call to find relevant information. Use the tool results to construct your answer. Only state facts that are supported by tool results. If the query is clearly outside the scope of Responsible AI and UNINOVIS, politely refuse without calling any tools.

### C.3 Multi-Step Reasoning Agent System Prompt

[Reference to agent prompts.json — varies by response path]

### C.4 Naive Agentic RAG System Prompt

> You are a research assistant with access to a knowledge base about Responsible AI research from the UNINOVIS European university alliance. [...] You have tools to search, count, and verify facts in the knowledge base. Use them to answer questions accurately. [...] If the question is clearly outside the scope of Responsible AI and UNINOVIS, politely refuse without calling any tools.

## Appendix D: Reproducibility

- Benchmark code: `comparison_benchmark.py` (workbook generation)
- Basic-reasoning agent: `vanilla_rag.py` (index building, querying, benchmark runner)
- Naive agentic RAG agent: `naive_agentic_rag.py` (generic tools, benchmark runner)
- Domain-informed agentic RAG agent: `agentic_rag.py` (specialised tools, benchmark runner)
- Pre-computed responses: `comparison_responses_tommi3.json`, `comparison_responses_vanilla_rag.json`, `comparison_responses_agentic_rag.json`, `comparison_responses_naive_agentic_rag.json`
- Evaluation workbook: `comparison_tommi3_vs_notebooklm_YYYYMMDD.xlsx`

All code and data available at [repository TBD].
