# Expert Input Specification — Phase A

This document is the sole human expert input for the Automated Agent Construction Protocol. It defines WHAT the classifier should learn, not HOW. Both V3 (rule-based) and V4 (LLM-based) classifiers are constructed from this specification.

---

## 1. Agent Identity

- **Domain**: Responsible AI (explainable AI, AI ethics, trustworthy AI, AI fairness, AI governance, etc.)
- **Organisation**: UNINOVIS — a European university alliance of 8 universities across 8 countries
- **Partners**: UMA (Spain), THUAS (Netherlands), USPN (France), UDCLV (Italy), THWS (Germany), TAMK (Finland), KK (Lithuania), UT (Albania)
- **Purpose**: Research assistant that helps users search papers, look up researchers, explore projects, and answer conceptual questions about Responsible AI within UNINOVIS

---

## 2. Data Sources

| Source | Content | Format |
|---|---|---|
| `papers.json` | 154 research papers across 8 universities | Structured JSON: title, authors, year, topics, university, DOI |
| `researchers.json` | 145 researchers across 8 universities | Structured JSON: name, topics, papers, affiliations |
| `Glossary.md` | ~40 Responsible AI terms with definitions | Markdown: heading (term) + definition paragraph |
| `project_docs/` | 11 funded research projects | Markdown: title, funder, grant ID, duration, partners, description |
| `chunk_db.json` | 19,942 document chunks from all papers | BM25-indexed text passages |

---

## 3. Classification Categories

Each category represents a **user intent type** and maps to a specific data source and response strategy.

### 3.1 Programmatic paths (no LLM in response)

| Category | User intent | Data source | Response strategy |
|---|---|---|---|
| **meta** | Questions about the agent itself: what it can do, what UNINOVIS is, which universities | `config.json` | Pre-built response listing capabilities and partners |
| **non_research** | Requests to perform a task: write essays, translate, book flights, get recipes, report weather, sports results | None | Fixed refusal message explaining scope |
| **off_topic** | Knowledge questions clearly outside Responsible AI: cooking, sports, quantum physics, greetings | None | Fixed refusal message with suggested in-scope topics |
| **figure** | Requests for data visualisations: charts, maps, graphs of publications or collaborations | Map generator | Interactive map/figure link |
| **project** | Questions about specific funded research projects, or requests to list projects | `project_docs/` | Formatted project details (title, funder, grant ID, duration, description) |
| **researcher** | Questions about a specific person's publications or research interests | `researchers.json` + `papers.json` | Formatted researcher profile with paper list |
| **glossary** | Conceptual "What is X?" questions about well-defined Responsible AI terms that appear in the glossary | `Glossary.md` | Formatted glossary definition |

### 3.2 LLM paths (LLM generates response with context)

| Category | User intent | Context provided to LLM | Response strategy |
|---|---|---|---|
| **topic_search** | Search for papers on a specific research topic | `papers.json` filtered by topic + BM25 chunks | LLM summarises findings with paper list |
| **university_papers** | List papers or researchers from a specific university | `papers.json` filtered by university | LLM summarises with structured data |
| **gap** | Questions about research gaps, unexplored topics, missing areas | Full metadata (all papers, all topics) | LLM reasons about what is absent |
| **general** | Broad or ambiguous Responsible AI questions not matching other categories | BM25 chunks | LLM generates response from retrieved context |
| **followup** | Short follow-ups referring to previous conversation context | Conversation history | LLM continues from prior context |

---

## 4. Representative Examples (3–5 per category)

### meta
- "What can you do?"
- "What is UNINOVIS?"
- "Which universities are in UNINOVIS?"
- "How does this work?"
- "Who are you?"

### non_research
- "Write me an essay about AI"
- "Can you book me a flight?"
- "Translate this text to French: 'Responsible AI is important'"
- "What is the weather today?"
- "Who won the last World Cup?"

### off_topic
- "What is quantum computing?"
- "Hello"
- "Explain photosynthesis"

### figure
- "Show a figure with all the publications per partner"
- "Show a map with the number of research projects per partner"
- "Show a figure of papers by year"

### project
- "What is the TAILOR project about?"
- "Describe the IntelliMan project"
- "List research projects on trustworthy AI"

### researcher
- "Papers by [researcher name]"
- "What has [researcher name] published?"
- "What are the research interests of [researcher name]?"

### glossary
- "What is explainable AI?"
- "What is fairness in AI?"
- "What is the EU AI Act?"
- "What is the difference between interpretability and explainability?"
- "What is trustworthy AI?"

### topic_search
- "Papers on AI ethics"
- "Papers about AI and privacy"
- "Research on AI in education within UNINOVIS"

### university_papers
- "List all researchers from THUAS"
- "List all papers from UDCLV on AI in healthcare"

### gap
- "What responsible AI topics have not been studied in UNINOVIS?"
- "Are there gaps in UNINOVIS research on AI regulation?"
- "Which responsible AI subtopics are least studied?"

### general
- "Is AI dangerous?"
- "Can AI be trusted?"
- "What is a language model?"

### followup
- "Tell me more"
- "Expand on that"
- "Can you give more details?"

---

## 5. Boundary Rules

These rules clarify cases where categories overlap:

1. **non_research vs off_topic**: If the user asks to **perform a task** (write, translate, book, cook, calculate), classify as `non_research`. If the user asks a **knowledge question** outside scope, classify as `off_topic`. "Can you book me a flight?" → non_research. "What is quantum computing?" → off_topic.

2. **glossary vs general**: Only use `glossary` for well-defined Responsible AI terms that have entries in the glossary (explainable AI, fairness, EU AI Act, trustworthy AI, etc.). For broad, ambiguous, or opinion questions ("Is AI dangerous?", "Can AI be trusted?") and for terms not in the glossary ("quantum computing", "language model"), use `general` or `off_topic`.

3. **project vs topic_search**: If the query mentions "project(s)" or a specific project name (TAILOR, IntelliMan, DUCA), classify as `project`. If it asks for "papers" or "publications" on a topic, classify as `topic_search`. "List research projects on trustworthy AI" → project. "Papers on trustworthy AI" → topic_search.

4. **researcher vs topic_search**: If the query mentions a specific person's name, classify as `researcher`. If it asks about a topic without naming anyone, classify as `topic_search`. "Papers by [researcher name]" → researcher. "Papers on AI ethics" → topic_search.

5. **university_papers vs topic_search**: If the query mentions a specific university (by name or acronym), classify as `university_papers`. If no university is mentioned, classify as `topic_search`. "Papers from UDCLV on healthcare" → university_papers. "Papers on healthcare" → topic_search.

6. **meta vs glossary**: Questions about the agent itself ("What can you do?", "What is UNINOVIS?") are `meta`. Questions about AI concepts ("What is explainable AI?") are `glossary`.

7. **followup**: Only for short, context-dependent utterances that make no sense without prior conversation ("tell me more", "expand on that", "and from THUAS?"). If the query is self-contained, classify based on its content.

---

## 6. Response Path Specifications

### Programmatic paths (deterministic, no LLM)

- **meta**: List agent capabilities and partner universities from config.
- **non_research**: Return: "I am a research assistant specialised in [topic]. I can help you search papers, researchers, and projects within this domain, but I cannot perform this type of task."
- **off_topic**: Return: "This question is outside my scope. I specialise in [topic]." + list of in-scope topics.
- **figure**: Generate interactive map/figure link based on query parameters.
- **project**: Format project details from project_docs/ (title, funder, grant, duration, partners, description).
- **researcher**: Format researcher profile from researchers.json (name, university, topics, paper list with titles, years, and DOIs).
- **glossary**: Format glossary definition from Glossary.md (heading + definition text).

### LLM paths (LLM generates with context)

- **topic_search**: Provide paper list from papers.json filtered by topic as context. LLM summarises.
- **university_papers**: Provide paper/researcher list filtered by university. LLM summarises.
- **gap**: Provide full metadata (all topics, all universities). LLM reasons about gaps.
- **general**: Provide BM25-retrieved chunks as context. LLM responds.
- **followup**: Provide conversation history. LLM continues.
