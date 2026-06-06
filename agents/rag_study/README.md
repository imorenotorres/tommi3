# RAG Architecture Study

## Research Question

How does each architectural layer of an AI agent affect its reliability?

This study isolates four architectural variables — retrieval, structured metadata, reasoning method, and classification approach — by creating five agent variants that share the same domain (Responsible AI), the same LLM (Mistral), and the same benchmark queries.

## Study Design

Each variant adds exactly one layer to the previous one, forming a progression:

| Variant | Name | Retrieval | Metadata | Reasoning | What it tests |
|---------|------|-----------|----------|-----------|---------------|
| 1 | **Baseline** | None | None | None | Pure LLM — what does the model know on its own? |
| 2 | **Vanilla RAG** | BM25 | None | None | Does grounding in documents improve reliability? |
| 3 | **LLM Reasoning** | BM25 | Yes | LLM decides (via prompt) | Does structured data improve reliability when the LLM manages it? |
| 4 | **Procedural** | BM25 | Yes | Code (13-step chain) | Does deterministic code classification improve reliability? |
| 5 | **LLM-Guided** | BM25 | Yes | LLM classifies → code executes | Can LLM classification surpass human-designed pattern matching? |

### Key comparisons

- **1 → 2**: Effect of retrieval (grounding)
- **2 → 3**: Effect of structured metadata
- **3 → 4**: Effect of programmatic reasoning vs LLM reasoning
- **4 vs 5**: Human-designed patterns vs LLM classification (same response paths)

### What stays constant

- Same LLM (Mistral)
- Same BM25 document chunks (chunk_db.json)
- Same structured data files (papers.json, researchers.json, projects, glossary)
- Same benchmark queries (100 queries, 3 user profiles)
- Same reliability evaluation framework (Rabanser et al., 2025)

## Variant Details

### Variant 1: Baseline (Oneshot)

**Architecture**: System prompt → LLM → response

The simplest possible agent. No retrieval, no metadata. The LLM answers from its general knowledge about Responsible AI, constrained only by the system prompt.

**Response paths**: 1 (every query follows the same path)

**Expected reliability profile**: Low correctness (no grounding), moderate consistency (deterministic prompt, stochastic LLM), low robustness (no classification), low predictability (no reliability cues meaningful).

### Variant 2: Vanilla RAG

**Architecture**: BM25 retrieval → chunks + system prompt → LLM → response (+ off-topic check)

Adds document retrieval. The LLM receives relevant chunks from the knowledge base alongside the system prompt. A simple off-topic check in production detects refusals.

**Response paths**: 2 (on-topic with Yellow cue, off-topic with no cue)

**Expected improvement over Variant 1**: Higher correctness (grounded in documents), similar consistency.

### Variant 3: LLM Reasoning

**Architecture**: BM25 retrieval → chunks + metadata + system prompt (with classification instructions) → LLM → response

Same retrieval as Variant 2, but the LLM also receives structured metadata (papers, researchers, projects, glossary) as context. The system prompt instructs the LLM to classify queries into 8 categories (meta, non-research, off-topic, conceptual, researcher, topic search, gap analysis, follow-up) and respond differently for each.

**Response paths**: 2 (technically — the LLM handles all classification internally)

**Expected improvement over Variant 2**: Better handling of structured queries (researcher lookups, project queries) thanks to metadata. But classification quality depends on the LLM following prompt instructions consistently.

### Variant 4: Procedural

**Architecture**: BM25 retrieval → code classification (13-step chain + synonym expansion) → programmatic paths OR LLM with context → post-processing pipeline → response

The full Metadata+RAG architecture. A deterministic classification chain in code identifies the query type before any LLM call. 8 of 18 response paths bypass the LLM entirely (programmatic responses from structured data). A post-processing pipeline checks for hallucinated papers, overconfident language, and unsolicited gap analysis.

**Response paths**: 18 (13 classification steps + 5 content sub-steps)

**Expected improvement over Variant 3**: Higher consistency (deterministic classification), higher correctness (programmatic paths for common queries), higher safety (post-processing catches errors). But potentially lower robustness (pattern matching misses novel phrasings).

### Variant 5: LLM-Guided Paths

**Architecture**: LLM classification call → code dispatches to programmatic path OR LLM with context → response

Same response paths and data access as Variant 4, but the classification decision is made by the LLM instead of pattern matching. The LLM receives the query and returns a JSON classification (category + extracted entities). Code then dispatches to the appropriate programmatic function.

**Response paths**: 18 (same paths as Variant 4)

**Key question**: Can the LLM classify queries better than human-designed patterns? The trade-off:
- **Advantages**: Naturally handles paraphrases, synonyms, and novel phrasings without explicit pattern lists. Language-agnostic.
- **Disadvantages**: Non-deterministic (LLM sampling may classify the same query differently across runs). Adds latency (extra LLM call). Less auditable.

## Evaluation Framework

Based on Rabanser et al. (2025), "Towards a Science of AI Agent Reliability":

| Dimension | What it measures | How we test it |
|-----------|-----------------|----------------|
| **Consistency** | Same query → same answer? | Run each query K=5 times, measure variance |
| **Robustness** | Handles paraphrases and edge cases? | 44 paraphrase tests across query types |
| **Predictability** | Do reliability cues predict correctness? | Compare cue colour vs expert-rated correctness |
| **Safety** | When it fails, how bad is it? | Check for hallucinated papers, wrong affiliations |

## File Structure

```
rag_study/
├── README.md                 # This file
├── baseline/                 # Variant 1: Oneshot
├── vanilla_rag/              # Variant 2: BM25 + LLM
├── llm_reasoning/            # Variant 3: BM25 + metadata + LLM classification
├── procedural/               # Variant 4: BM25 + metadata + code classification
└── llm_guided/               # Variant 5: LLM classification → code paths
```

## References

[1] Rabanser, S., Kapoor, S., Kirgis, P., Liu, K., Utpala, S., & Narayanan, A. (2025). Towards a Science of AI Agent Reliability. Preprint, Princeton University. https://arxiv.org/abs/2602.16666

[2] Russell, S. & Norvig, P. (1995). Artificial Intelligence: A Modern Approach. Prentice Hall.
