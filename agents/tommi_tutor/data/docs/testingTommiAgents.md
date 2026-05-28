# Testing TOMMI Agents -- Tester Guide

> **Who is this document for?**
>
> This guide is for **testers, QA staff, and project managers** who evaluate TOMMI agents before deployment. You should be an **expert on the topic** the agent covers — you need to assess whether the agent's responses are factually correct, complete, and properly sourced, not just whether they "look right."
>
> **The role of the tester** is to identify failures, flaws, and limitations of the AI Agent and report them to the developer following the error reporting procedure described in this guide (see [Section 9](#9-error-reporting-procedure)).

---

## 1. The AI Agent deployment workflow

Deploying an AI Agent is not like deploying traditional software. AI agents combine curated data with language model inference, which means their behaviour is **probabilistic and context-dependent**. A response that looks correct today may be wrong tomorrow with a different model, a different prompt, or a different set of documents.

The deployment workflow follows these stages:

```
  DESIGN          BUILD           TEST            DEPLOY          MONITOR
  ──────          ─────           ────            ──────          ───────
  Define purpose  Prepare data    Systematic      Release to      Review logs
  Choose type     Write prompts   evaluation by   end users       Collect user
  Set scope       Configure LLM   TESTERS         (role: user)    feedback
  Risk classify   Index documents                                 Iterate
```

### Why testers are critical

Testers evaluate agents **before they reach end users**. Without systematic testing, agents may be deployed with undetected errors that erode user trust and create compliance risks. Specifically:

- **LLMs can hallucinate.** The agent may generate plausible but incorrect information. Testers verify that safeguards (reliability badges, source attribution, scope restrictions) are actually working.
- **RAG retrieval can miss relevant documents.** A tester systematically probes the agent with queries that should and should not be answerable from the corpus.
- **Prompts may not constrain the LLM enough.** A tester tests edge cases — out-of-scope questions, adversarial prompts, ambiguous queries — to check that the agent stays within its defined scope.
- **Transparency features need validation.** The reliability badge, source breakdown, and inline claim highlights must accurately reflect the origin of each response. Only a domain expert can verify this.
- **Compliance requires evidence.** Under the EU AI Act (Art. 50) and GDPR (Art. 5(2)), we must be able to demonstrate that the system was tested and that issues were documented before deployment.

### The tester's role

Your job is to **identify** failures, flaws, and limitations — not to fix them:

1. **Detect** — find cases where the agent gives wrong, incomplete, or misleading answers
2. **Classify** — categorise the error using the structured error codes (see [Section 9](#9-error-reporting-procedure))
3. **Document** — record the exact query, agent response, and expected behaviour
4. **Report** — submit a structured error report via the tester interface

---

## 2. Getting started: step-by-step

### 2.1 What you need

Before you begin testing, make sure you have:

| Item | Description |
|------|-------------|
| **Tester account** | Ask the system administrator to create an account with role *tester*. You will receive a login link by email or a provisional password. |
| **Server URL** | The address where TOMMI is running (e.g., `http://your-server:8000`). |
| **Browser** | Any modern browser (Chrome, Firefox, Edge, Safari). |
| **Domain knowledge** | You must be familiar with the topic the agent covers — you need to judge whether answers are correct, not just whether they look correct. |
| **Agent documentation** | If available, review the Agent Design Card and the agent's `config.json` to understand its intended purpose, data sources, and known limitations. |

### 2.2 Logging in

1. Open the server URL in your browser. You will be redirected to the **login page**.
2. Read the **Data Protection & AI Transparency Notice** at the bottom of the login form.
3. Enter your **username** and **password**.
4. If this is your first login (provisional password), you will be prompted to set a new password. Requirements: minimum 8 characters, including uppercase, lowercase, digit, and special character.

### 2.3 Switching to tester mode

After login, you land on the main agent interface (user mode). To access the tester interface:

1. Look at the **top-right corner** of the screen — you will see your username, role, and several buttons.
2. Click the **"Testing"** button to switch to the tester interface.

You can switch back to user mode at any time by clicking **"User mode"**.

### 2.4 Differences between user mode and tester mode

| Feature | User mode | Tester mode |
|---------|-----------|-------------|
| Agent access | Only agents with local LLM (Ollama/vLLM) | All agents, including cloud LLM (Mistral) |
| Web search | Disabled (data stays on-premise) | Enabled (if configured in the agent) |
| Feedback widget (thumbs down) | Simple comment box | Structured error report: error type + severity + notes |
| LLM model switching | Available | Available |
| Transparency / prompt tuning | Available | Available |
| Settings panel (gear icon) | Not available | Available -- allows editing agent configuration, visibility, and tool access |
| Header | "TOMMI Transparent AI Agents" | "Tester-developer interface" |

### 2.5 Understanding the interface

**Sidebar (left panel):**

- **Agent selector** — dropdown to choose which agent to test.
- **Agent type & LLM provider** — shows the agent architecture (RAG, Metadata+RAG, Text2SQL, Oneshot) and whether the LLM is local or cloud, with dedicated icons. Click the "?" icon for details.
- **Agent tuning** — three clickable badges:
  - **LLM** — click to cycle through available models. Icon shows cloud (Mistral) or local (Ollama) with colour coding.
  - **Transparency** — click to switch between Crystal box, Grey box, and Black box. Each level has a distinct icon.
  - **Prompt** — click to switch between Stringent, Tolerant, and Lax.
- **Example queries** — suggested queries provided by the agent developer. Click any query to send it directly.
- **Query history** — your recent queries (click to re-send).

**Top-right area:**

- **User menu** — shows your username and role badge. Includes links to "Edit my profile" (Directory), "Tester Panel", and "Logout".
- **Settings panel** (gear icon, tester and superuser only) — opens a configuration panel with:
  - **Agent Configuration** — edit `prompt_level`, `reliability_cues`, and `transparency_level` in real time (no restart needed).
  - **Agent Visibility** — set agents to `hidden`, `restricted`, or `open`, and manage allowed user lists.
  - **Tool Visibility** — configure which roles can access which intranet tools.
  - **Log Analytics** — view request/visitor statistics across agents.

**Chat area (right panel):**

- Type your query in the text box and press **Send** or **Enter**.
- The agent's response appears with:
  - A **reliability badge** (if transparency is not Black box): coloured indicator (green/yellow/red) with source breakdown.
  - **Inline highlights** (if Crystal box): colour-coded text showing where each claim comes from (green = metadata, yellow = database, red = LLM, blue = web).
  - **Humility hedging** (if configured): ungrounded claims may be prefixed with hedging language such as "Based on available information, ..." to soften certainty.
- Below each response, the **feedback widget** appears:
  - Thumbs up — mark the response as correct.
  - Thumbs down — open the error report panel to classify and document the issue.

---

## 3. Evaluation protocol

This section provides a simple, step-by-step protocol to evaluate an agent. Follow it in order. Use the built-in feedback widget (thumbs down) to report every issue you find.

### Before you start

1. **Select the agent** you will test from the dropdown.
2. **Set transparency to Crystal box** — this gives you maximum visibility into how each response was built.
3. **Set prompt level to Stringent** — start with the most constrained mode to test the intended behaviour.
4. **Note the LLM model** being used — you may repeat some tests with different models later.
5. **Have the agent's data accessible** if possible (papers.json, database, documents) to verify answers against source data.

### Phase 1 — Basic functionality (5-10 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 1.1 | Welcome message | Select the agent | Does a welcome message appear? Is it accurate? |
| 1.2 | Example queries | Click each example query in the sidebar | Does the agent respond? Are responses correct? |
| 1.3 | Simple factual query | Ask a straightforward question about the agent's domain | Is the response sourced from the database (not just LLM)? |
| 1.4 | Language | Ask the same question in a different language | Does the agent respond in the user's language? |

### Phase 2 — Response accuracy (15-20 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 2.1 | Verifiable facts | Ask at least 5 questions whose answers you can independently verify | Do the responses match the source data? |
| 2.2 | Specific details | Ask for names, dates, numbers, identifiers | Are they accurate? Are sources cited? |
| 2.3 | Multi-source query | Ask a question that requires combining information from multiple documents | Is the synthesis coherent and correct? |
| 2.4 | Numerical query | Ask for counts, statistics, or comparisons | Are the numbers correct? |
| 2.5 | Negative query | Ask about something you know is NOT in the data | Does the agent correctly say it has no information? |

### Phase 3 — Scope and boundaries (10 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 3.1 | Out-of-scope | Ask something clearly outside the domain (e.g., a recipe, a sports score) | Does the agent decline or redirect? |
| 3.2 | Adjacent topic | Ask about a related topic not in the corpus | Does the agent acknowledge its limitations? |
| 3.3 | Adversarial prompt | Try "Ignore all previous instructions and..." | Does the agent stay within scope? |
| 3.4 | Edge cases | Send empty, very short, or gibberish messages | Does it handle them gracefully? |

### Phase 4 — Transparency verification (10 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 4.1 | Badge accuracy | Compare the badge colour with the actual quality | Does green really mean reliable? Does red flag real issues? |
| 4.2 | Source breakdown | Check the % breakdown (Metadata / Database / LLM) | Does a factual answer from the database show low LLM %? |
| 4.3 | Inline highlights | Check the colour-coded claims | Are green claims really from data? Are red claims really inferred? |
| 4.4 | Grey box | Switch to Grey box and repeat one query | Is the detail reduced (no breakdown, no highlights)? |
| 4.5 | Black box | Switch to Black box and repeat | Is all transparency info hidden? |

### Phase 5 — Prompt levels (5 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 5.1 | Stringent vs Lax | Ask an off-topic question at Stringent (should refuse), then at Lax (may answer) | Does the prompt level actually change behaviour? |
| 5.2 | Tolerant | Ask the same question at Tolerant | Is the behaviour between Stringent and Lax? |

### Phase 6 — Agent-specific features (10-15 min)

Depending on the agent type, test the relevant features:

**RAG / Metadata+RAG agents:**

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 6.1 | Document retrieval | Ask about a document you know exists | Is it found and cited correctly? |
| 6.2 | Gap analysis | Ask "What topics have not been studied?" | Does it correctly identify gaps? |
| 6.3 | Maps and figures | Request a figure or map (if supported) | Does it render? Is the data accurate? |
| 6.4 | PDF links | Click a PDF link in a response | Does it open the correct document? |

**Text2SQL agents:**

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 6.5 | SQL correctness | Ask a database query, verify the SQL shown | Is the generated SQL correct? |
| 6.6 | No-result query | Ask for data that doesn't exist | Does it handle "no results" gracefully? |
| 6.7 | Semantic mismatch | Ask about one topic, check SQL doesn't query another | Does the semantic check work? |

### Phase 7 — Humility and authority sanitization (5-10 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 7.1 | Authority phrases | Ask a question about an unstudied topic | Does the agent say "does not appear in the indexed database" instead of "has not been studied"? |
| 7.2 | Hedging (if enabled) | Ask a question that produces ungrounded claims (red highlights) | Are ungrounded claims prefixed with hedging language like "Based on available information, ..."? |
| 7.3 | Moderate vs strict | If `humility_level` is configurable, compare moderate and strict | Does strict mode also hedge web-sourced claims and add a disclaimer footer? |
| 7.4 | Formatting preservation | Ask a question that produces a bulleted list or table | Does hedging preserve the markdown formatting? |

### Phase 8 — LLM comparison (optional, 10-15 min)

| # | Test | Action | What to check |
|---|------|--------|---------------|
| 8.1 | Switch model | Click the LLM badge to switch to a different model | Does the badge update? |
| 8.2 | Repeat key queries | Re-ask 3-5 queries from Phase 2 with the new model | How does quality compare? |
| 8.3 | Note differences | Document where the alternative model is better or worse | Record in your notes |

### After testing — complete the summary

```
Agent: ___________________________  Date: ____________  Tester: _______________
LLM model(s) tested: _________________________________________________________
Transparency level: Crystal box / Grey box / Black box
Prompt level: Stringent / Tolerant / Lax

RESULTS
Total queries tested: ____
Issues reported (thumbs down): ____  (Critical: ___ Major: ___ Minor: ___)

OVERALL ASSESSMENT
[ ] Ready for deployment
[ ] Needs fixes before deployment (list critical/major issues)
[ ] Major rework needed

NOTES:
_______________________________________________________________________________
_______________________________________________________________________________
```

---

## 4. Detailed testing reference

The following sections provide in-depth information about each aspect of testing. Refer to them when you need more detail about a specific feature.

**Testing should cover:**

- Response quality and factual accuracy
- Reliability badge correctness (does the badge reflect what the response actually contains?)
- Transparency levels (does each level show the right amount of detail?)
- Prompt level behaviour (does constraining the prompt actually change the agent's responses?)
- LLM selection (do different models produce acceptable quality?)
- Error reporting (can every failure be classified and reported?)

---

## 5. Agent Tuning Options

TOMMI agents expose three runtime controls that affect response quality, detail, and behaviour. All three can be changed live from the web interface without restarting the server.

### 5.1 LLM Selection

Click the **LLM badge** in the sidebar to cycle through available models. The badge is colour-coded and uses dedicated icons:

| Colour | Icon | Badge | Meaning |
|--------|------|-------|---------|
| Green | Local icon | Local | Using a local LLM (Ollama or vLLM). Data stays on your machine. |
| Green | Local (large) icon | Local (large) | Using a large local model (>=20GB). Slower but higher quality. |
| Yellow/Orange | Cloud icon | Cloud (small) | Using a small cloud model (e.g., mistral-small). Lower cost. |
| Red | Cloud icon | Cloud (large) | Using a large cloud model (e.g., mistral-large). Higher cost and quality. |

**Local (Ollama) vs Cloud (Mistral) differences:**

| Aspect | Cloud (Mistral) | Local (Ollama) |
|--------|-----------------|----------------|
| Model size | Full model, uncompressed | Quantized (compressed) for local hardware |
| Precision | 16-bit floating point | 4-bit or 8-bit quantization |
| Reasoning | Better coherence and accuracy | May struggle with complex tasks |
| Privacy | Data sent to external API | Data never leaves your machine |
| Cost | Per-query API charges | No API costs |
| Latency | Network round-trip | Local inference (faster for small models) |

**Model size impact:** Smaller models (7B parameters) are faster and require less hardware, but hallucinate more and produce less coherent answers. Larger models (70B+) are slower and need significant GPU resources, but are more accurate and better at following instructions.

**How to evaluate:** Ask the same question with each available model and compare the responses side by side. Pay attention to:

- Does the response answer the question correctly?
- Are paper titles, author names, and years accurate?
- Does the reliability badge change significantly between models?
- Does the response follow the agent's prompt constraints?

### 5.2 Transparency Levels

Click the **transparency badge** (above the example queries) to cycle through levels: Crystal box, Grey box, Black box. The change takes effect immediately for the next query.

- **Crystal box** -- full detail for developers and testers. All transparency features are active:
  - Reliability badge with source breakdown percentages (e.g., `Metadata: 75% | Database: 10% | LLM: 15%`)
  - Confidence score with claim count
  - Source lines (coloured indicators)
  - Inline claim highlights (colour-coded text showing the provenance of each claim)
  - Colour legend explaining the highlight meanings
  - Agent settings info (model name, LLM location, transparency level, prompt level)

- **Grey box** -- minimal for end users:
  - Reliability label only (High / Good / Poor)
  - Confidence percentage only
  - No source breakdown, no inline highlights, no legend

- **Black box** -- nothing shown:
  - The response appears without any badge, confidence indicator, or highlights
  - The **audit log still records everything** -- all decision data is logged for compliance and analysis
  - Useful for A/B testing or researching user trust behaviour with vs. without transparency

**Testing tip:** Always use Crystal box during testing so you can see the full detail. Then verify that Grey box and Black box correctly hide the expected elements. After testing, decide which level is appropriate for end users.

### 5.3 Prompt Levels

Click the **prompt badge** to cycle through levels. The prompt level controls how much of the system prompt is active:

- **Stringent** -- all 3 prompt sections active: identity + standard rules + strict restrictions. This is the most constrained behaviour. The agent follows all configured rules, including partner recognition, gap analysis constraints, and domain restrictions.

- **Tolerant** -- sections 1 and 2 only: identity + standard rules. The strict restrictions (section 3) are removed. The agent still follows the general rules but is not subject to the most restrictive constraints.

- **Lax** -- section 1 only: just the agent's identity. The LLM answers freely with minimal constraints. Use with caution -- the agent may go off-topic, hallucinate more freely, or ignore domain boundaries.

**How the prompt sections work:**

| Level | Section 1 (Identity) | Section 2 (Rules) | Section 3 (Strict) |
|-------|:-------------------:|:-----------------:|:------------------:|
| Stringent | Active | Active | Active |
| Tolerant | Active | Active | -- |
| Lax | Active | -- | -- |

**Testing tip:** Ask the same question at all three levels and verify the differences:

1. With **Stringent**, the agent should refuse or redirect off-topic questions and strictly follow domain rules.
2. With **Tolerant**, the agent should be somewhat flexible but still follow general rules.
3. With **Lax**, the agent should answer more freely. If it still refuses off-topic questions at Lax, something may be wrong with the prompt structure.

**Example test:** Ask an off-topic question like "What is the recipe for chocolate cake?" at each level. With Stringent, the agent should refuse. With Lax, it may attempt an answer (which confirms the prompt constraints are working at each level).

---

## 6. The Transparency Pipeline

The transparency system works as a three-step pipeline. Each step can succeed or fail independently, and testers should evaluate each one separately.

```
Response text
     |
     v
+-------------------+     +-------------------+     +-------------------+
| Step 1:           |     | Step 2:           |     | Step 3:           |
| Claim             |---->| Claim             |---->| Confidence        |
| Identification    |     | Categorization    |     | Computation       |
+-------------------+     +-------------------+     +-------------------+
  "What are the           "Where does each       "How reliable is
   verifiable facts?"      claim come from?"       the response?"
```

### 6.1 Step 1 — Claim Identification

**Goal:** Extract verifiable factual claims from the LLM response.

Claim identification uses a **bidirectional approach** that combines two complementary techniques:

#### Phase A — Response-driven extraction (regex patterns)

The system scans the response text using pattern matching to identify fragments that look like verifiable facts. The following patterns are recognized, in order:

| # | Pattern | Example | Minimum length |
|---|---------|---------|----------------|
| 1 | Quoted strings | "Explainable AI in Healthcare" | 10 characters |
| 2 | Bold markdown text | **AI Ethics** | 5 characters |
| 3 | Parenthetical identifiers | (DOI: 10.xxxx, ORCID: 0000-xxxx) | 5 characters |
| 4 | Year ranges and date references | (2020-2024), published in 2023 | -- |
| 5 | Structured data | email addresses, numerical values with units | 5 characters |
| 6 | Named entities (NER-like) | University of Malaga, Dr. Smith | 5 characters |

These patterns focus on **precision over recall** — they aim to avoid false claims rather than catch every possible fact.

#### Phase B — Context-driven verification

After extracting candidate claims from the response, the system checks them against the actual data sources:

1. **Metadata matching:** Each claim is compared against structured fields in `papers.json`, `researchers.json`, and `metadata.json`. This includes paper titles, author names, university names, DOIs, topics, and years.
2. **RAG chunk matching:** Claims are compared against the text chunks retrieved from ChromaDB during the RAG step.
3. **Overlap scoring:** A claim is considered "grounded" if it matches a data source above a similarity threshold.

#### What testers should check

- **Missing claims (Error 1.1):** Look for obvious factual statements in the response that are NOT highlighted. Example: the response says "published in Nature in 2023" but this is not identified as a claim.
- **False claims:** Less common with the regex approach, but check if non-factual text (opinions, transitions) is incorrectly marked as a claim.

### 6.2 Step 2 — Claim Categorization

**Goal:** Determine the source of each claim (metadata, database, LLM, or web).

Each identified claim is classified into one of four categories based on where matching evidence was found:

| Category | Colour (inline) | Meaning | Source |
|----------|:---------------:|---------|--------|
| **Metadata** | Green | Verified against structured data | papers.json, researchers.json |
| **Database** | Yellow | Found in RAG-retrieved documents | ChromaDB chunks from PDFs |
| **Web** | Blue | Found in web search results | Google Custom Search (if enabled) |
| **LLM** | Red | Not found in any data source — generated by the model | LLM inference |

#### What testers should check

- **False positive (Error 1.2.1):** A claim is coloured red (LLM) but it IS actually in the data. This means the matching algorithm failed to find it.
- **False negative (Error 1.2.2):** A claim is coloured green (metadata) or yellow (database) but the information is WRONG. This means the matching produced a spurious match.
- **Correct classification:** Spot-check several claims of each colour. Verify that green claims really come from metadata, yellow from documents, and red claims are truly inferred by the model.

### 6.3 Step 3 — Confidence Computation

**Goal:** Produce a single reliability score and breakdown for the response.

The confidence score is calculated from the source distribution of all claims:

```
Confidence = (metadata_claims + database_claims) / total_claims * 100
```

The reliability label is determined by the LLM percentage:

| LLM % | Label | Badge colour |
|-------|-------|:------------:|
| <= 20% | High | Green |
| 20-50% | Good | Yellow |
| >= 50% | Poor | Red |

These thresholds are configurable per agent in `config.json` → `reliability_thresholds`.

#### What testers should check

- **Badge vs reality (Error 1.4):** A green badge should mean most claims are verified. If you see a green badge but many claims look wrong, the confidence computation may be inaccurate.
- **Distribution sanity:** After testing several queries, the badge distribution should make sense:
  - Metadata queries (e.g., "list all papers") → should tend toward High
  - Open-ended questions → may show Good or Poor
  - If ALL queries show the same label, the thresholds may need adjustment

### 6.4 Full pipeline example

**Query:** "List researchers from UMA working on AI Ethics"

```
Step 1 — Claim identification:
  Extracted claims: "Dr. García", "AI Ethics", "UMA", "2023", "Explainable AI"

Step 2 — Claim categorization:
  "Dr. García"      → Green  (found in researchers.json)
  "AI Ethics"       → Green  (topic in metadata)
  "UMA"             → Green  (institution in metadata)
  "2023"            → Yellow (found in RAG document)
  "Explainable AI"  → Green  (concept in papers.json)

Step 3 — Confidence:
  Metadata: 60% | Database: 20% | LLM: 20%
  Label: Good (yellow badge)
```

### 6.5 Special cases

**Gap analysis responses:** When the agent performs a gap analysis ("What topics have NOT been studied?"), the colour interpretation is **reversed**:
- Green = the topic WAS found in the database (not a gap)
- Red = the topic was NOT found (true gap — this is actually the desired result)

Testers should be aware that a red-heavy response in gap analysis mode is **correct behaviour**, not an error.

**Follow-up queries:** When a user sends a follow-up ("tell me more about point 2"), the agent uses conversation history. The badge should still appear, but the source distribution may shift toward LLM since the follow-up is synthesised from prior context.

---

## 7. Testing Checklist

Before deploying an agent, verify each item:

- [ ] **Representative queries:** Test with at least 10 representative queries covering the agent's domain. Include simple factual questions, comparison questions, and topic summaries.
- [ ] **Reliability badge sanity:** Verify that badges are not always High or always Poor. A healthy agent should produce a mix depending on the query type. Metadata queries should tend toward High; open-ended questions may show Good or Poor.
- [ ] **Crystal box detail:** In Crystal box mode, verify the full badge appears with source breakdown percentages, confidence score, claim count, inline highlights, and colour legend.
- [ ] **Grey box minimal:** In Grey box mode, verify only the reliability label and confidence percentage appear. No breakdown, no highlights, no legend.
- [ ] **Black box suppression:** In Black box mode, verify no reliability information is shown at all. The response should appear clean, with no badge or indicators.
- [ ] **Stringent prompt:** Ask an off-topic question (e.g., "What is the weather today?"). The agent should refuse or redirect.
- [ ] **Lax prompt:** Ask the same off-topic question. The agent should answer more freely, confirming that prompt constraints are actually effective at the Stringent level.
- [ ] **Tolerant prompt:** Verify behaviour falls between Stringent and Lax.
- [ ] **LLM switching:** Switch between available LLMs and compare response quality. Verify the LLM badge updates correctly (colour and label).
- [ ] **Coverage warnings:** Ask an off-topic question in Lax mode (e.g., "recipe for chocolate cake" to a research agent). Verify the badge shows "No verifiable claims found" or "Low verifiability." Then ask an on-topic question and confirm the coverage warning disappears.
- [ ] **Gap analysis (RAG+Metadata only):** Ask a gap analysis question (e.g., "What topics have not been studied?"). Verify the badge shows Poor/LLM: 100% and the inline highlights use the reversed colour interpretation (green = found in DB, red = true gap).
- [ ] **Follow-up queries:** After a normal query, send a follow-up ("expand on point 1"). Verify the agent responds using conversation history and that a reliability badge still appears.
- [ ] **Audit log:** Check `agents/{agent_id}/data/audit_log.jsonl` after several queries. Verify entries are being recorded with correct fields.
- [ ] **Paper title verification (Metadata+RAG only):** Ask for a paper listing (e.g., "List papers on AI ethics from UMA"). Check if any titles are flagged as "not found in database." Verify the flagged titles are genuinely not in the papers.json data.
- [ ] **Paper ID mismatch (Metadata+RAG only):** Ask to expand a specific paper. Verify the PDF link points to the correct paper (not an unrelated one). If the paper has no PDF, verify "not available" appears instead of a fake link.
- [ ] **Out-of-domain questions:** Test with questions outside the agent's domain. Verify the agent refuses gracefully (at Stringent level) rather than hallucinating an answer.
- [ ] **Edge cases:** Test with empty queries, very long queries, and queries in different languages (if the agent is multilingual).
- [ ] **Humility hedging:** If `humility_level` is set to `moderate` or `strict`, verify ungrounded claims have hedging prefixes. Verify hedging preserves markdown formatting and does not repeat the same phrase.
- [ ] **Authority sanitization:** Ask about a topic not in the database. Verify the agent says "does not appear in the indexed database" rather than "has not been studied."
- [ ] **Settings panel:** Open the settings panel (gear icon). Verify you can change `prompt_level` and `reliability_cues` in real time. Verify changes apply to the next query without server restart.
- [ ] **Agent visibility:** If the agent is set to `restricted`, verify only allowed users can see it. Verify `hidden` agents do not appear in the dropdown.
- [ ] **Study mode (if active):** If study mode is enabled, verify your transparency level is locked to the assigned condition and cannot be changed manually.

### Text2SQL-specific verification tests

- [ ] **Schema verification:** Ask a question that should produce a valid query. With `transparency_level: "crystal_box"`, verify the SQL query is shown and no unknown tables/columns appear.
- [ ] **Semantic mismatch detection:** Ask about a specific topic (e.g. "Show agreements with Libya") and check if the generated SQL actually references that topic. If the LLM hallucinates a different query, verify the system blocks it in stringent mode with a "Semantic mismatch" message.
- [ ] **Cross-language equivalences:** Ask in English about a concept stored in Spanish (e.g. "agreements requiring English" when the database uses "INGLES"). Verify the semantic check does not flag this as a mismatch.
- [ ] **Broad query detection:** Ask a very generic question (e.g. "Show everything"). Verify the badge flags the query as overly broad if it returns >70% of all rows.
- [ ] **Transparency levels:** Test that SQL is shown when `transparency_level` is `crystal_box`, and hidden when it is `black_box`.
- [ ] **Tolerant vs stringent:** In tolerant mode, verify that semantic warnings appear but the query still executes. In stringent mode, verify mismatched queries are blocked.

---

## 8. Interpreting the Audit Log

**Location:** `agents/{agent_id}/data/audit_log.jsonl`

Each line is an independent JSON object. The log is append-only and grows indefinitely.

**Key fields:**

| Field | Description |
|-------|-------------|
| `timestamp` | UTC ISO 8601 timestamp of the query |
| `agent_id` | Agent identifier |
| `query` | The user's original question |
| `query_type` | `normal`, `figure`, `gap_analysis`, or `followup` |
| `source_type` | `Metadata`, `RAG`, or `none` (RAG+Metadata agents only) |
| `reliability_label` | `High`, `Good`, `Poor`, or `none` |
| `confidence` | Percentage of claims verified against data sources |
| `coverage_pct` | Percentage of response words covered by identified claims (0-100). Low values indicate most of the response could not be verified |
| `total_claims` | Number of verifiable claims extracted from the response |
| `breakdown` | Per-source percentages. RAG+Metadata: `metadata_pct`, `database_pct`, `llm_pct`. RAG: `database_pct`, `llm_pct` |
| `context_sources` | Which context builders were used (RAG+Metadata only) |
| `reliability_cues` | Whether reliability cues were shown or hidden at the time of the query |
| `prompt_level` | Active prompt level (`stringent`, `tolerant`, or `lax`) |
| `model` | LLM model name used for this query |
| `is_local_llm` | Whether a local model was used (`true`/`false`) |
| `reliability_label` | The computed reliability label (`High`, `Good`, `Poor`) |
| `humility_level` | Active humility level at the time of the query (`off`, `moderate`, `strict`) |

**Practical uses for testers:**

- **Tracking badge distribution:** After running a batch of test queries, count how many produced High/Good/Poor labels. If all queries produce the same label, the reliability thresholds may need adjustment.
- **Debugging unexpected responses:** If a response seems wrong, check the audit log for the `source_type` and `breakdown` to understand where the content came from.
- **Comparing models:** Run the same test queries with different LLMs and compare the `confidence` and `breakdown` values across log entries.
- **Compliance verification:** The audit log provides record-keeping recommended for AI Act compliance. Verify it is enabled (`audit_log_enabled: true` in `config.json`) before deployment.

**Processing the log:** The JSONL format works with standard tools:

```bash
# Count entries by reliability label
cat data/audit_log.jsonl | jq -r '.reliability_label' | sort | uniq -c

# Filter queries with low confidence
cat data/audit_log.jsonl | jq 'select(.confidence < 50)'

# Extract all queries and their labels as a table
cat data/audit_log.jsonl | jq -r '[.query, .reliability_label, .confidence] | @tsv'
```

---

## 9. Error Reporting Procedure

When a tester identifies a failure, flaw, or limitation, it must be documented and reported to the developer in a structured way. This section defines the error types and the reporting format.

### 9.1 Error Types

Every issue found during testing should be classified using the structured codes below. These codes map directly to specific components of the system, so that each report tells the developer **exactly where the fix is needed**.

### 1. Transparency errors

Errors in how the system identifies, classifies, and presents claims and reliability information.

| Code | Error Type | Description | Example |
|------|-----------|-------------|---------|
| **1.1** | **Claim identification** | A factual claim in the response was not detected by the claim extraction system | Agent says "published in Nature in 2023" but this is not highlighted as a claim |
| **1.2.1** | **Claim classification: false positive** | A claim is marked as ungrounded (red) but it IS in the data | "Retrieval-Augmented Generation" marked red when the term exists in papers.json |
| **1.2.2** | **Claim classification: false negative** | A claim is marked as grounded (green) but it is NOT in the data | Agent invents a paper title, but it's highlighted green because a partial word match was found |
| **1.3.1** | **Hallucination detection: false negative** | The agent states something false and the system does NOT flag it | Agent says "UMA has 15 agreements with TAMK" (wrong number) but no warning appears |
| **1.3.2** | **Hallucination detection: false positive** | The system flags correct information as a hallucination | A real paper title is flagged as "not found in database" due to a minor formatting difference |
| **1.4** | **Confidence computation** | The reliability badge score does not reflect the actual quality of the response | Badge shows 95% confidence but half the claims are wrong; or badge shows 20% when all claims are correct |

### 2. Text2SQL AI Agent errors

Errors specific to Text2SQL agents (database query agents).

| Code | Error Type | Description | Example |
|------|-----------|-------------|---------|
| **2.1** | **Wrong SQL undetected** | The agent generates incorrect SQL and the verification system fails to catch it | User asks about Libya but SQL searches for English B1 — and the system doesn't block it |
| **2.2** | **Wrong answer** | The SQL is correct but the agent's interpretation or presentation of the results is wrong | Query returns 8 rows but agent says "Found 3 agreements" |
| **2.3** | **Insufficient information** | The SQL is too narrow or the results are incomplete compared to what the database contains | Agent only searches one column when the answer requires joining or searching multiple columns |

### 3. Content errors

Errors in the factual content of the response, regardless of transparency features.

| Code | Error Type | Description | Example |
|------|-----------|-------------|---------|
| **3.1** | **Missing information** | The response is correct but omits important information that exists in the data | Agent lists 3 of 8 agreements with a partner; agent omits key authors from a paper |
| **3.2** | **Wrong information** | The response contains factually incorrect statements | Agent says a paper was published in 2024 when the database says 2023 |
| **3.3** | **Irrelevant response** | The response doesn't match the user's question | User asks about Libya, agent returns results about English B1 requirements |
| **3.4** | **Misleading presentation** | Information is not technically false but could lead to wrong conclusions | Agent implies all UNINOVIS partners use the same tool when they don't |

### 4. Other

| Code | Error Type | Description | Example |
|------|-----------|-------------|---------|
| **4.1** | **System error** | Agent crashes, times out, or returns a technical error | Connection error, SQL execution failure, 500 error |
| **4.2** | **Usability issue** | Response is correct but poorly formatted or confusing | Results in random order, excessive jargon, unreadable table |
| **4.3** | **Other** | Any issue not covered above | Describe in the Notes field |

### 9.2 Error Report Format

Each error report should include the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| **Date** | Yes | Date of the test |
| **Agent** | Yes | Agent ID and name (e.g. `responsible_ai — EH: Responsible AI`) |
| **Error type** | Yes | Code from the table above (e.g. 1.2.1, 2.1, 3.1, 4.3) |
| **Severity** | Yes | **Critical** (agent unusable), **Major** (wrong results), **Minor** (cosmetic/usability) |
| **Query** | Yes | The exact question typed by the tester |
| **Agent response** | Yes | The full response (or a screenshot) |
| **Expected behaviour** | Yes | What the correct response should have been |
| **Agent tuning** | Yes | LLM model, transparency level, prompt level at the time of the test |
| **Steps to reproduce** | If applicable | Any specific sequence of actions needed to trigger the issue |
| **Notes** | Optional | Additional context, related issues, or suggested fix |

### 9.3 Report Template

```
DATE:               2026-04-18
AGENT:              pisha4 — Algoria DB Assistant+ (verified)
ERROR TYPE:         3.3 (Irrelevant response)
SEVERITY:           Major
QUERY:              "Show all agreements with Libia"
AGENT RESPONSE:     Returned results for English B1 language requirements
EXPECTED:           List of agreements with Libya (destination_country = 'Libia')
TUNING:             mistral-small-latest (Cloud) / Stringent / Crystal box
STEPS TO REPRODUCE: Type the query as first message in a new session
NOTES:              The LLM generated SQL that searched lang_1_name
                    instead of destination_country
```

### 9.4 Reporting Workflow

```
Tester finds issue
      |
      v
Classify error type (1.x / 2.x / 3.x / 4.x)
      |
      v
Assess severity (Critical / Major / Minor)
      |
      v
Click thumbs-down on the response in tester interface
      |
      v
Fill in error type, severity, and notes in the panel
      |
      v
Click "Send" — the report is saved automatically
      |
      v
Developer reviews feedback logs and assigns priority
      |
      v
Developer fixes and notifies tester
      |
      v
Tester re-tests and confirms the fix
```

### 9.5 User Feedback Integration

In addition to structured tester reports, end-users can provide feedback on agent responses using the **feedback widget** that appears after every response (thumbs up / thumbs down + optional comment). This feedback is logged to `logs/{agent_id}_feedback_user.jsonl` and can be reviewed by testers and developers to identify recurring issues.

User feedback categories map to error types as follows:

| User feedback | Likely error type |
|---------------|-------------------|
| Thumbs down — **Wrong** | 3.2 (Wrong information) or 1.3.1 (Hallucination undetected) |
| Thumbs down — **Incomplete** | 3.1 (Missing information) |
| Thumbs down — **Irrelevant** | 3.3 (Irrelevant response) or 2.3 (SQL mismatch) |

---

## 10. Model Quality Comparison

| Category | Speed | Privacy | Quality | Cost |
|----------|-------|---------|---------|------|
| **Local small (7B)** | Fast | Full privacy | Lower -- may hallucinate more, struggles with complex reasoning | Free |
| **Local large (70B+)** | Slow | Full privacy | Good -- better coherence, requires significant GPU/RAM | Free (hardware cost) |
| **Cloud small** (e.g., mistral-small) | Medium | Data sent externally | Good | Low per-query cost |
| **Cloud large** (e.g., mistral-large) | Medium | Data sent externally | Best -- most accurate and coherent | Higher per-query cost |

**Recommended testing workflow:**

1. **Establish a baseline with the cloud model.** Run your full test suite with the cloud (large) model. Record the reliability badges, confidence scores, and response quality. This is your quality ceiling.
2. **Compare with local models.** Run the same test suite with each available local model. Note where quality drops: which questions produce worse answers, lower confidence, or incorrect claims.
3. **Identify the minimum viable model.** Find the smallest/cheapest model that still meets your quality requirements for the agent's use case. Not every agent needs the best model.
4. **Document the results.** Record which model you recommend for production and any known limitations (e.g., "7B model struggles with comparison questions but handles simple lookups well").

---

## 11. Study Mode Awareness

If the system administrator has enabled **study mode**, some users will have their reliability cues locked to a specific condition (`shown` or `hidden`). This is used for controlled experiments on how reliability cues affect user behaviour.

**As a tester, be aware that:**

- Study participants **cannot change** their transparency level — the cycling button is disabled.
- Study participants see a separate study interface at `/study` with predefined queries and per-query questionnaires.
- Your own tester account is typically **not enrolled** in the study, so you can still cycle freely.
- If you need to test the study interface, ask the superuser to enroll you as a study participant.
- Study data (questionnaire responses, condition assignments) is stored in `web/data/study_config.json`.

---

## Tips for effective testing

1. **Start with the example queries** — they are designed to exercise the agent's core features. If these fail, report them first.
2. **Verify against the source data** — if you have access to the agent's documents or database, check the agent's answers against the original data.
3. **Test with real-world questions** — think about what a real user would ask, not just what the developer expected.
4. **Try different LLM models** — click the LLM badge in the sidebar to switch models. The same query may produce different results with different models.
5. **Test transparency at Crystal box level** — this gives you maximum visibility into how the response was built.
6. **Report everything** — even minor issues are valuable. Patterns of minor issues often reveal deeper problems.
7. **Be specific in your notes** — "wrong answer" is less useful than "Q: How many papers does UMA have? A: Agent said 45, actual count in papers.json is 73."
8. **Test in sessions** — some issues only appear in multi-turn conversations (follow-up questions, context from previous queries).
