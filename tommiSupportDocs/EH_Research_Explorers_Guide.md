# Excellence Hub Research Explorers — Overview and Development Guide

## 1. Goal

The UNINOVIS alliance has identified eight Excellence Hubs, each representing a strategic research area shared across partner universities. To make the research output of these hubs accessible and discoverable, UMA is developing one **AI-powered Research Explorer** per hub.

Each Research Explorer is a conversational agent that allows users to search and explore the research produced by UNINOVIS partners in a specific domain. Users can ask questions about papers, researchers, projects, topics, and terminology, and the agent responds with sourced, transparent answers drawn from curated data.

The eight Excellence Hubs and their lead partners are:

| Excellence Hub | Lead Partner |
|---|---|
| Responsible AI | THUAS — The Hague, Netherlands |
| Health & Wellbeing Systems | UMA — Malaga, Spain |
| AI & Robotics | THWS — Wurzburg, Germany |
| ICT Technologies & Languages | UT — Tirana, Albania |
| Logistics & Data Science | UDCLV — Caserta, Italy |
| Smart & Sustainable Environments | USPN — Paris, France |
| Wellness Technologies & Services | TAMK — Tampere, Finland |
| Logistics & Cybersecurity | KK — Kaunas, Lithuania |

All Research Explorers are hosted on the UNINOVIS digital platform and can be accessed at [https://gloria.uma.es/research-explorers](https://gloria.uma.es/research-explorers).

---

## 2. Development Process

The development of each Research Explorer follows five stages. Stages 1 and 3 require input from the Excellence Hub partners; stages 2, 4, and 5 are coordinated by UMA.

### Stage 1: Initial Metadata Preparation

**Who**: Domain experts from the Excellence Hub (typically 1–2 people with broad knowledge of the field).

**Goal**: Provide the key information that allows UMA to collect the right data from public databases.

During stage 2, UMA will collect the data used by each agent from public databases on the Internet (OpenAlex and CORDIS mainly). In order for this process to work properly, each partner must provide some key information by reviewing three files:

#### 1.1 `scope_keywords.txt` — What is in scope?

This file lists keywords and phrases that define what the agent considers on-topic. If a user asks about a topic matching these keywords, the agent will attempt to answer; otherwise, it may refuse.

- Open the file in any text editor
- Add missing terms relevant to your Excellence Hub's research
- Remove terms that are too broad or misleading
- Lines starting with `#` are comments

#### 1.2 `out_of_scope_examples.txt` — What is out of scope?

Examples of topics the agent should refuse. These help the agent learn boundaries.

- Add topics that might seem related but are not (e.g., pure literary criticism without computational methods, general linguistics without AI)
- Remove examples that are actually in scope for your hub

#### 1.3 `Glossary` — Domain glossary

A draft glossary with entries covering core concepts in the hub's domain, AI/ML applications, and related fields. Each entry includes a definition, related concepts, and academic references.

- Verify definitions are accurate and reflect the state of the art
- Add entries for concepts central to your hub's research
- Remove or merge entries that are too generic
- Correct references where needed

**Deliverable**: Return the three reviewed files to the UMA-ICT team.

---

### Stage 2: Data Download

**Who**: UMA-ICT team.

**Goal**: Collect and pre-process research data from public sources using automated tools and APIs.

Using the keywords and scope definitions provided in Stage 1, UMA collects:

- **Papers**: from OpenAlex, filtered by UNINOVIS partner affiliations and domain keywords.
- **Researchers**: automatically extracted from paper author lists.
- **Projects**: from CORDIS (the EU research project database), using keyword searches.

After this stage, the data is ready for human review in Stage 3.

---

### Stage 3: Data Curation

**Who**: UMA (AI-assisted pre-curation) + Excellence Hub experts (manual review).

**Goal**: Ensure the automatically collected data is accurate and relevant.

UMA performs an initial AI-assisted review of the collected data, but a manual revision by Excellence Hub experts is strongly advisable to ensure high quality. Partners who invest time in this stage will have a noticeably better agent.

Typical review tasks include:

- **Papers**: Verify that each paper is genuinely related to the hub's domain. Check that author affiliations are correct. Optionally, provide full-text PDFs to improve the agent's ability to answer detailed questions.
- **Projects**: Verify partner involvement, add names of participating UNINOVIS researchers, and check that summaries and keywords are accurate.
- **Suggest additions**: Flag any relevant papers, projects, or researchers that were missed by the automated collection.

**Deliverable**: Return the reviewed files to the UMA-ICT team.

---

### Stage 4: Piloting by Selected Users

**Who**: Selected end users from the Excellence Hub, coordinated by UMA.

**Goal**: Test the agent with real users before public deployment.

Once data curation is complete and the agent is assembled, it enters a pilot phase. During this stage, selected users interact with the agent and provide feedback on its accuracy, usefulness, and any issues encountered.

Feedback can be provided to UMA in two ways:

1. **In-agent feedback**: Click the thumbs-down button that appears alongside agent responses and fill in the short form. This is the fastest way to report a specific incorrect or unsatisfactory answer.
2. **Written report**: Prepare a brief report summarising your experience and send it to **uninovis@uma.es**. This is useful for broader observations about coverage, missing data, or general suggestions.

---

### Stage 5: Deployment

**Who**: UMA, in coordination with the Excellence Hub lead and WP5.

**Goal**: Make the agent publicly available on the UNINOVIS digital platform.

Once pilot feedback has been addressed and the agent meets quality standards, it is published on the Research Explorers page. WP5 is informed so that the new agent can be communicated to the wider UNINOVIS community.

---

## 3. Current Status

| Excellence Hub | Stage | Next Step |
|---|---|---|
| Responsible AI (THUAS) | 4 — Piloting | All partners test and report |
| Health & Wellbeing Systems (UMA) | 3 — Data curation | UMA to curate data |
| AI & Robotics (THWS) | 1 — Metadata preparation | THWS to curate metadata |
| ICT Technologies & Languages (UT) | 1 — Metadata preparation | UT to curate metadata |
| Logistics & Data Science (UDCLV) | 1 — Metadata preparation | UDCLV to curate metadata |
| Smart & Sustainable Environments (USPN) | 1 — Metadata preparation | USPN to curate metadata |
| Wellness Technologies & Services (TAMK) | 1 — Metadata preparation | TAMK to curate metadata |
| Logistics & Cybersecurity (KK) | 1 — Metadata preparation | KK to curate metadata |

---

## 4. Questions?

Contact the UNINOVIS-UMA ICT Team at **uninovis@uma.es**.

---

*Built with TOMMI by the UNINOVIS-UMA ICT Team. Licensed under the EUPL v1.2.*
