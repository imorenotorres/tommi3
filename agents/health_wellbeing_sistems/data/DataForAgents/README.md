# Data Collection for the Health & Wellbeing Systems Research Explorer

This folder contains the data files needed to complete the Health & Wellbeing Systems agent. The data collection follows three stages, each with a clear goal and responsible actors.

---

## Stage 1: Domain Definition (Excellence Hub experts)

**Goal**: Ensure the agent understands what Health & Wellbeing Systems means in the UNINOVIS context.

**Who**: Domain experts from the Health & Wellbeing Systems Excellence Hub (typically 1-2 people with broad knowledge of the field).

**Files to review**:

### 1.1 `scope_keywords.txt` — What is in scope?

This file lists keywords and phrases that define what the agent considers on-topic. If a user asks about a topic matching these keywords, the agent will attempt to answer; otherwise, it may refuse.

- Open the file in any text editor
- Add missing terms relevant to your Excellence Hub's research
- Remove terms that are too broad or misleading
- Lines starting with `#` are comments

### 1.2 `out_of_scope_examples.txt` — What is out of scope?

Examples of topics the agent should refuse. These help the agent learn boundaries.

- Add topics that might seem related but are not (e.g., pure pharmaceutical research without AI, general biology without computational methods)
- Remove examples that are actually in scope for your hub

### 1.3 `Glossary_Health_Wellbeing.md` — Domain glossary

A draft glossary with 25 entries covering digital health, AI diagnostics, wearable monitoring, precision medicine, and health informatics. Each entry includes a definition, related concepts, and academic references.

- Verify definitions are accurate and reflect the state of the art
- Add entries for concepts central to your hub's research
- Remove or merge entries that are too generic
- Correct references where needed

**Deliverable**: Return the three reviewed files to the UMA-ICT team.

---

## Stage 2: AI-Assisted Data Collection (UMA-ICT team)

**Goal**: Collect and pre-process research data from public sources using automated tools.

**Who**: UMA-ICT team, using AI tools and APIs.

**What happens**:

- **Papers**: Collected from OpenAlex using the keywords from Stage 1. Pre-populated in `health_wellbeing_papers.xlsx`.
- **Researchers**: Automatically extracted from paper author lists.
- **Projects**: Collected from CORDIS using keyword searches. One markdown file per project in `health_wellbeing_projects/`.

After this stage, the data will be ready for human review in Stage 3.

**Files produced**:

| File | Description | Status |
|---|---|---|
| `health_wellbeing_papers.xlsx` | Publications (9 sheets: All + one per university) | To be collected |
| `health_wellbeing_projects/` | CORDIS project files (one `.md` per project) | To be collected |

---

## Stage 3: Human Review (University contacts)

**Goal**: Ensure the automatically collected data is accurate and relevant.

**Who**: One contact person per university, ideally with knowledge of their institution's Health & Wellbeing Systems research.

### 3.1 Review papers — `health_wellbeing_papers.xlsx`

Open your university's sheet and review each paper:

| Column | What to do |
|---|---|
| **Relevant?** (I) | Mark `Yes` if the paper is genuinely related to Health & Wellbeing Systems. Leave blank or `No` otherwise. Many papers may have been captured by broad keyword matching. |
| **Authors (UNINOVIS only)** (E) | Verify that listed authors are actually affiliated with your university. OpenAlex affiliations can be imprecise. |
| **PDF** (H) | If you have access to the full text, place the PDF in the `docs/` folder named by Paper ID (e.g., `W4389624963.pdf`) and enter the filename here. |

**Do not modify**: University, Paper ID, Title, Year, All Authors, Abstract, DOI.

### 3.2 Review projects — `health_wellbeing_projects/`

For each project file involving your university:

- Verify the **UNINOVIS partners** field is correct
- Add **UNINOVIS Researchers** — names of researchers from your university participating in the project
- Verify the **Summary** and **Keywords** are accurate

### 3.3 Suggest additions

If you know of relevant papers, projects, or researchers missing from the data, note them and send to the UMA-ICT team.

**Deliverable**: Return the reviewed Excel file and any corrected project files.

---

## Summary

| Stage | Who | What | Files |
|---|---|---|---|
| 1. Domain Definition | EH experts | Keywords, glossary, scope | `scope_keywords.txt`, `out_of_scope_examples.txt`, `Glossary_Health_Wellbeing.md` |
| 2. AI Data Collection | UMA-ICT team | Papers, researchers, projects from APIs | `health_wellbeing_papers.xlsx`, `health_wellbeing_projects/` |
| 3. Human Review | University contacts | Verify relevance, authors, affiliations | `health_wellbeing_papers.xlsx`, `health_wellbeing_projects/` |

---

## Project file format

For reference, each project in `health_wellbeing_projects/` follows this format (one `.md` file per project, named `{GrantID}_{ShortName}.md`):

```markdown
# Project Title

**Grant ID:** 101070136
**Funder:** European Commission
**Programme:** Horizon Europe / Digital, Industry and Space
**Period:** 2022-09-01 — 2026-04-30
**Status:** SIGNED
**Total cost:** 4509303 (funded: 4509303) EUR
**Website:** https://cordis.europa.eu/project/id/101070136

**UNINOVIS partners:** THWS, UMA

## UNINOVIS Researchers

- Prof. John Smith (THWS) — Work Package 3 lead
- Dr. Maria Garcia (UMA) — Task 2.1

## Summary

[Copy from CORDIS project page]

**Keywords:** keyword1, keyword2, keyword3

## Participants

- PARTNER INSTITUTION 1
- PARTNER INSTITUTION 2
```

---

## Questions?

Contact the UNINOVIS-UMA ICT Team for support.
