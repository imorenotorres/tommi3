# Replication Package

## Study: Reliability of Query Classification in RAG Agents

This folder contains all materials needed to replicate the study. All paths are relative to the `rag_study2/` directory.

## 1. Expert Input (Phase A)

- `expert_input/expert_input.md` — Category definitions, examples, boundary rules provided by the domain expert. This is the shared starting point for all classifiers.

## 2. Knowledge Base

- `data/papers.json` — 154 research papers across 8 UNINOVIS universities
- `data/researchers.json` — 145 researchers with affiliations and topics
- `data/project_docs/` — 11 funded research projects
- `data/docs/` — PDF papers and Responsible AI glossary
- `data/chunk_db.json` — 19,942 BM25-indexed document chunks
- `data/metadata.json` — Document metadata for retrieval

## 3. Agent Variants

All agents are in `agents/`. Each contains `agent.py` (classification logic), `config.json`, and a symlink to the shared `data/` folder.

| Agent | Folder | Classification | Construction |
|---|---|---|---|
| Baseline (Vanilla RAG) | `agents/baseline/` | None | — |
| Production rule-based | `agents/production/` | Hand-crafted patterns (deterministic) | Months, reactive |
| Auto rule-based | `agents/auto_rule_based/` | Auto-built patterns (deterministic) | Hours, automated |
| Auto LLM-based | `agents/llm_based/` | LLM prompt (non-deterministic) | Hours, automated |

### Shared components

- `shared/dispatch.py` — Response paths shared by all classified agents (programmatic + LLM)

## 4. Benchmark Query Sets

- `benchmark/development_set.json` — 69 queries used during classifier construction
- `benchmark/evaluation_set_extended.json` — 216 unseen queries (T1=120, T2=61, T3=35) for final evaluation

## 5. Benchmark Scripts

- `benchmark/full_reliability_benchmark.py` — Main benchmark: runs all agents on the evaluation set, measures all four Rabanser dimensions
- `benchmark/nrun_benchmark.py` — N=5 repeated runs for variance estimation
- `benchmark/baseline_benchmark.py` — Baseline-specific evaluation (K=3 response consistency)

### Running the benchmarks

```bash
# Set environment variables
export MISTRAL_API_KEY=<your_key>
export LLM_PROVIDER=mistral
export MISTRAL_MODEL=mistral-small-latest

# Full reliability benchmark (all agents, 216 queries)
cd benchmark/
python3 full_reliability_benchmark.py --agents production,auto_rule_based,llm_based

# N-run variance analysis (LLM-based, 5 runs)
python3 nrun_benchmark.py --agents auto_rule_based,llm_based --n 5

# Baseline evaluation
python3 baseline_benchmark.py
```

## 6. Construction Trajectories

- `construction/constructor.py` — Automated agent construction protocol
- `construction/rule_based_trajectory/` — Iteration logs for auto rule-based construction
- `construction/llm_based_trajectory/` — Iteration logs for auto LLM-based construction

## 7. Results

- `results/full_reliability_20260607_190227.json` — Main benchmark results (216 queries, production + auto rule-based + LLM-based)
- `results/nrun_20260607_114630.json` — N=5 run results for LLM-based variance
- `results/baseline_20260607_211032.json` — Baseline evaluation results

## 8. Paper

- `paper/paper_draft.md` — Full paper (markdown)
- `paper/paper_draft_main.docx` — Full paper (Word)
- `paper/annex_queries.md` — Annex A: all 285 benchmark queries
- `paper/paper_draft_annex.docx` — Annex A (Word)
- `paper/figures/` — Generated figures
- `paper/generate_figures.py` — Figure generation script

## 9. Dependencies

- Python 3.10+
- Mistral API key (for LLM-based classification and response generation)
- Required packages: `mistralai`, `python-dotenv`, `httpx`

## 10. Platform

The study was conducted on [TOMMI](https://github.com/imorenotorres/tommi3), an educational AI agent platform developed by the UNINOVIS-UMA ICT Team, licensed under EUPL v1.2.
