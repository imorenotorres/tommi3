# RAG Architecture Study

## Research Question

How does each architectural layer of an AI agent affect its reliability?

This study isolates architectural variables by creating four agent variants that share the same domain (Responsible AI), the same LLM (Mistral), the same BM25 retrieval, and the same benchmark queries. Each variant adds exactly one layer, enabling controlled comparison.

## Study Design

| | V1: Baseline | V2: + LLM Reasoning | V3: + Procedural | V4: LLM-Guided |
|---|---|---|---|---|
| **Retrieval** | BM25 | BM25 | BM25 | BM25 |
| **Metadata** | No | Yes | Yes | Yes |
| **System prompt** | Simple | Complex (8 query type instructions) | Complex (rules + strict) | Complex (same as V3) |
| **Classification + response** | Fused (1 LLM call) | Fused (1 LLM call, guided by prompt) | Separated (code classifies first) | Separated (LLM classifies first) |
| **Can bypass LLM for response?** | No | No | Yes (8 query types) | Yes (8 query types) |
| **Post-processing** | None | Full (6 steps) | Full (6 steps) | Full (6 steps) |
| **Development effort** | Low | Medium (prompt design) | High (code + patterns + synonyms) | Medium (classification prompt + reuse code) |

### What stays constant

- Same LLM (Mistral)
- Same BM25 document chunks (chunk_db.json)
- Same structured data files (papers.json, researchers.json, projects, glossary)
- Same benchmark queries (100 queries, 3 user profiles)
- Same reliability evaluation framework (Rabanser et al., 2025)

## Hypotheses

### V1 vs V2: Effect of metadata + LLM reasoning + post-processing

**What changes**: V2 adds structured metadata (papers, researchers, glossary, projects), a complex prompt that instructs the LLM to classify query types, and a 6-step post-processing pipeline.

**Hypotheses**:
- **Correctness** ↑ vs V1: metadata provides verified data for factual queries (researcher lookups, project details, glossary definitions)
- **Robustness** ↑ vs V1: LLM handles different query types appropriately instead of treating everything the same
- **Safety** ↑ vs V1: post-processing catches hallucinated paper titles, overconfident claims, and unsolicited gap analysis
- **Predictability** ↑ vs V1: reliability cues become meaningful — different cue per query type
- **Overall reliability** ↑ vs V1

### V2 vs V3: Effect of separating classification from response (code classification + programmatic paths)

**What changes**: Instead of the LLM classifying and responding in a single call (fused), code classifies first using a 13-step pattern-matching chain with synonym expansion. For 8 query types, code generates the response directly from structured data without calling the LLM at all (programmatic paths).

**Hypotheses**:
- **Consistency** ↑ vs V2: deterministic classification — same query always gets the same response path
- **Correctness** ↑ vs V2: programmatic paths serve verified data without LLM interpretation (zero hallucination risk on those paths)
- **Predictability** ↑ vs V2: reliability cue assignment is deterministic, not dependent on LLM behaviour
- **Robustness** ↓? vs V2: pattern matching may miss novel phrasings that the LLM would handle naturally
- **Overall reliability** ↑ vs V2: gains in consistency and correctness are expected to outweigh the robustness risk

### V3 vs V4: Code patterns vs LLM classification (same paths, same post-processing)

**What changes**: The classification method changes from human-designed pattern matching (code) to LLM-based classification (a separate LLM call that returns a JSON category). The same programmatic paths execute after classification. Same post-processing pipeline.

**Hypotheses**:
- **Robustness** ↑ vs V3: LLM naturally handles paraphrases, synonyms, and multilingual queries without requiring explicit pattern lists or synonym maps
- **Consistency** ↓? vs V3: LLM classification is non-deterministic — the same query might get different classifications across runs due to sampling
- **Correctness** = vs V3: same programmatic paths execute after classification, so response quality is identical once correctly classified
- **Safety** = vs V3: same post-processing pipeline
- **Overall reliability**: depends on whether the robustness gain compensates the consistency loss

## Variant Details

### Variant 1: Baseline (Vanilla RAG)

**Folder**: `vanilla_rag/`

**Architecture**: BM25 retrieval → chunks + simple system prompt → LLM → response

The simplest RAG agent — like NotebookLM. Upload documents, ask questions, get answers. No metadata, no classification, no post-processing. Every query follows the same path: retrieve chunks, send to LLM, return response.

**Response paths**: 1 (every query follows the same path)

### Variant 2: LLM Reasoning

**Folder**: `llm_reasoning/`

**Architecture**: BM25 retrieval → chunks + metadata + complex prompt (with query type instructions) → LLM → post-processing → response

Same retrieval, plus structured metadata (papers, researchers, projects, glossary) injected into the LLM context. The system prompt instructs the LLM to classify queries into 8 categories (meta, non-research, off-topic, conceptual, researcher, topic search, gap analysis, follow-up) and respond differently for each. Classification and response happen in a single LLM call (fused). Full post-processing pipeline runs on the output.

**Response paths**: 1 (technically — the LLM handles all classification internally within a single call)

### Variant 3: Procedural

**Folder**: `procedural/`

**Architecture**: BM25 retrieval → code classification (13-step chain + synonym expansion + accent-insensitive matching) → programmatic path OR LLM with context → post-processing → response

Classification is separated from response generation. A deterministic code chain identifies the query type before any LLM call. For 8 query types (meta-question, non-research, off-topic, figure/map, project, researcher, glossary, disambiguation), code generates the response directly from structured data — no LLM involved, zero hallucination risk. For the remaining query types, the LLM is called with appropriate context. Full post-processing pipeline.

**Response paths**: 18 (13 classification steps + 5 content sub-steps)

### Variant 4: LLM-Guided Paths

**Folder**: `llm_guided/`

**Architecture**: LLM classification call (returns JSON category) → code dispatches to programmatic path OR LLM with context → post-processing → response

Same response paths and data access as Variant 3, but the classification decision is made by the LLM instead of pattern matching. A separate LLM call receives the user's query and returns a JSON object with the category and extracted entities. Code then dispatches to the same programmatic functions as Variant 3.

**Response paths**: 18 (same paths as Variant 3)

**Key difference from V3**: The LLM understands natural language natively — it doesn't need synonym maps or pattern lists. It might correctly classify queries that the human-designed patterns miss. But it introduces non-determinism (the same query might be classified differently across runs) and adds latency (extra LLM call for classification).

## Evaluation Framework

Based on Rabanser et al. (2025), "Towards a Science of AI Agent Reliability":

| Dimension | Definition | How we measure it |
|-----------|-----------|-------------------|
| **Consistency** | Same query → same answer? | Run each query K=5 times, measure classification and response variance |
| **Robustness** | Handles paraphrases and edge cases? | 44 paraphrase tests across query types |
| **Correctness** | Is the response factually accurate? | Expert evaluation of 100 benchmark responses |
| **Predictability** | Do reliability cues predict correctness? | Compare cue colour vs expert-rated correctness |
| **Safety** | When it fails, how bad is it? | Check for hallucinated papers, wrong affiliations, scope violations |

## File Structure

```
rag_study/
├── README.md                 # This file
├── vanilla_rag/              # V1: Baseline (BM25 + LLM)
├── llm_reasoning/            # V2: + metadata + LLM classification + post-processing
├── procedural/               # V3: + code classification + programmatic paths
└── llm_guided/               # V4: LLM classification → same code paths as V3
```

## References

[1] Rabanser, S., Kapoor, S., Kirgis, P., Liu, K., Utpala, S., & Narayanan, A. (2025). Towards a Science of AI Agent Reliability. Preprint, Princeton University. https://arxiv.org/abs/2602.16666
