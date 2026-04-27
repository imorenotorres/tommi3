# Testing TOMMI Agents -- Tester Guide

> **Who is this document for?**
>
> This guide is for **testers, QA staff, and project managers** who evaluate TOMMI agents before deployment. You should be an **expert on the topic** the agent covers — you need to assess whether the agent's responses are factually correct, complete, and properly sourced, not just whether they "look right."
>
> **The role of the tester** is to identify failures, flaws, and limitations of the AI Agent and report them to the developer following the error reporting procedure described in this guide (see [Section 7](#error-reporting-procedure)).

## 1. Introduction

This guide is intended for **testers, QA staff, and project managers** who need to evaluate TOMMI agents before deployment. It covers the practical aspects of verifying agent quality, tuning runtime parameters, interpreting reliability data, checking claim accuracy, and **reporting errors to the developer**.

**Role of testers:** Your job is to identify failures, flaws, and limitations — not to fix them. Specifically:

1. **Detect** — find cases where the agent gives wrong, incomplete, or misleading answers
2. **Classify** — categorise the error by type: transparency (1.x), prompt enforcement (2.x), content (3.x), or other (4.x) — see [Section 7](#error-reporting-procedure)
3. **Document** — record the exact query, agent response, and expected behaviour
4. **Report** — submit a structured error report to the developer

Testing should be performed on a local server before any agent is made available to end users.

**Testing should cover:**

- Response quality and factual accuracy
- Reliability badge correctness (does the badge reflect what the response actually contains?)
- Transparency levels (does each level show the right amount of detail?)
- Prompt level behaviour (does constraining the prompt actually change the agent's responses?)
- LLM selection (do different models produce acceptable quality?)
- Error reporting (can every failure be classified and reported?)

---

## 2. Agent Tuning Options

TOMMI agents expose three runtime controls (LLM, Transparency, and Prompt) that affect response quality, detail, and behaviour. All three can be changed live from the web interface without restarting the server.

### 2.1 LLM Selection

Click the **LLM badge** in the sidebar to cycle through available models. The badge is colour-coded:

| Colour | Badge | Meaning |
|--------|-------|---------|
| Green | Local | Using a local LLM (Ollama or vLLM). Data stays on your machine. |
| Yellow/Orange | Cloud (small) | Using a small cloud model (e.g., mistral-small). Lower cost. |
| Red | Cloud (large) | Using a large cloud model (e.g., mistral-large). Higher cost and quality. |

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

### 2.2 Transparency Levels

Click the **transparency badge** (above the example queries) to cycle through levels: Crystal box, Grey box, Black box. The change takes effect immediately for the next query.

- **Crystal box** -- full transparency for developers and testers:
  - For scaffolded agents (Metadata+RAG Vectorless): procedural badges (🟢 Verified data / 🟡 AI Commentary / 🔴 Unverified) and hallucination detection
  - For non-scaffolded agents: reliability badge with source percentages, confidence score, inline claim highlights
  - For Text2SQL agents: AI interpretation badge with SQL query (Crystal) or plain-language explanation (Grey), plus Verified data badge before results

- **Grey box** -- minimal for end users:
  - For non-scaffolded agents: reliability label and confidence only
  - For scaffolded agents: Grey box is not available (use Crystal or Black box)
  - For Text2SQL agents: AI interpretation badge with plain-language explanation (no SQL shown)

- **Black box** -- no transparency shown:
  - The response appears without any badges, highlights, or procedural indicators
  - The **audit log still records everything** -- all decision data is logged for compliance and analysis
  - Useful for A/B testing, expert users, or researching user trust behaviour

**Testing tip:** Always use Crystal box during testing so you can see the full detail. Then verify that Grey box and Black box correctly hide the expected elements. After testing, decide which level is appropriate for end users.

### 2.3 Prompt Levels

Click the **prompt badge** to cycle through levels. The prompt level controls how much of the system prompt is active:

- **🟢 Stringent** -- all 3 prompt sections active: identity + rules + strict. The agent is constrained to use only curated database content. LLM involvement is minimal. The agent follows all configured rules, including partner recognition, gap analysis constraints, and domain restrictions.

- **🟡 Tolerant** -- sections 1 and 2 only: identity + rules. The agent uses curated data but the LLM interprets and connects it. The agent still follows general rules but is not subject to strict constraints.

- **🔴 Lax** -- section 1 only: identity only. The agent can freely use all data sources including unconstrained LLM generation. Use with caution -- the agent may go off-topic, hallucinate more freely, or ignore domain boundaries.

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

## 3. The Transparency Pipeline

The transparency system works as a three-step pipeline. Each step can succeed or fail independently, and testers should evaluate each one separately.

```
Response text
     │
     ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Step 1:         │     │ Step 2:         │     │ Step 3:         │
│ Claim           │────▶│ Claim           │────▶│ Confidence      │
│ Identification  │     │ Categorization  │     │ Computation     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
  "What are the           "Where does each       "How reliable is
   verifiable facts?"      claim come from?"       the response?"
```

### 3.1 Step 1 — Claim Identification

**Goal:** Extract verifiable factual claims from the LLM response.

Claim identification uses a **bidirectional approach** that combines two complementary techniques:

#### Phase A — Response-driven extraction (regex patterns)

The system scans the response text using pattern matching to identify fragments that look like verifiable facts. The following patterns are recognized, in order:

| # | Pattern | Example | Minimum length |
|---|---------|---------|----------------|
| 1 | Quoted strings | "Explainable AI in Healthcare" | 10 characters |
| 2 | Bold markdown text | **AI Ethics** | 5 characters |
| 3 | Author / proper-noun names | García-López, Van der Berg | 2 words |
| 4 | Years | 2024 | exact 4 digits |
| 5 | University acronyms (Metadata+RAG only) | UMA, THUAS, TAMK | from config |
| 6 | Paper IDs (Metadata+RAG only) | W4405602662 | 7+ digits |
| 7 | Technical terms (ALL_CAPS 3+ chars, compound) | RAG, RAG+Metadata, Text2SQL | 3 characters |

**Filters applied** — the following are excluded even if they match a pattern above:

- Bold text that starts with an instruction verb (e.g., "Modify the...", "Use the...", "If you...")
- Bold text that is a question (ends with "?")
- Bold text longer than 8 words (likely a heading or sentence, not a factual claim)
- Author-like matches starting with common English words (e.g., "If you", "The system", "However...")
- Claims shorter than 2 characters
- Duplicates (only the first occurrence is kept)

**Limitation:** This phase only catches claims that fit predefined regex patterns. Domain-specific terms that are not in bold, not quoted, and not ALL_CAPS will be missed. For example, in a Responsible AI agent, terms like "transparency", "fairness", or "AI-generated content" in plain text would not be identified by regex alone.

#### Phase B — Context-driven extraction (bidirectional)

To address the limitation above, the system also works in reverse: it extracts significant terms from the **context** (metadata and RAG documents) and checks whether those terms appear in the response.

How it works:

1. **Context tokenization:** The metadata and RAG context text is split into tokens. Stop words and very short words (< 4 characters) are removed.
2. **N-gram generation:** Single words and 2–3 word phrases (n-grams) are generated from the context tokens. These represent the agent's domain vocabulary.
3. **Response scanning:** Each context-derived term is searched for in the response text. Only terms that were NOT already identified in Phase A are added.
4. **Overlap prevention:** Longer phrases are matched first. If "AI-generated content" is matched, the shorter "AI-generated" inside it is not double-counted.

**Example:** If the metadata context contains "AI ethics, explainable AI, transparency, accountability, responsible AI" and the response mentions "transparency of AI-generated content", Phase B identifies "transparency", "AI-generated content", and "responsible AI" as claims — even though they are in plain text without any special formatting.

**Key property:** Claims found via Phase B are automatically grounded, because they were extracted *from* the context. This means they are classified as metadata or database claims in Step 2 without further matching.

#### Combined result

The final claim set is the union of Phase A (regex) and Phase B (context-driven) claims, deduplicated. This bidirectional approach significantly improves coverage for domain-specific content.

**What testers should check:**

- Are the right things being identified as claims? Look at the inline highlights in Crystal box mode.
- Are important factual statements being missed? If a key fact is not highlighted, it was not recognized as a claim by either phase.
- Are non-factual fragments (headings, instructions, suggestions) incorrectly marked as claims?
- For Phase B: are trivial or very generic terms from the context being over-matched in the response? (The minimum length and stop-word filters should prevent this, but edge cases may occur.)

### 3.2 Step 2 — Claim Categorization

**Goal:** Determine where each identified claim comes from — the agent's data or the LLM's own knowledge.

Claims from **Phase A** (regex-extracted) need to be matched against context to determine their source. Claims from **Phase B** (context-derived) are already categorized, since they were found *in* the context.

#### Categorization of Phase A claims

Each regex-extracted claim is checked (case-insensitive) against the context pools that were provided to the LLM:

**Context pools (in priority order):**

| Pool | Available in | Contains |
|------|-------------|----------|
| Metadata context | Metadata+RAG agents | Structured data: topic summaries, researcher indexes, paper lists, collaboration data |
| RAG context | All RAG agents | Text chunks retrieved from ChromaDB via semantic similarity search |
| (no match) | — | Claim is categorized as LLM-generated |

**Matching logic:**

1. **Exact substring match** — the full claim text (lowercased) is searched within the context. If found, the claim is categorized under that pool.
2. **Fuzzy match** (for multi-word claims only) — if the exact match fails, the system extracts significant words (longer than 3 characters) and checks whether a **majority** (more than 50%) of them appear in the context. This handles minor variations in phrasing.

**Categorization priority:** Metadata is checked first, then RAG. A claim found in metadata is always categorized as "metadata" even if it also appears in the RAG context. Claims not found in any pool are categorized as "LLM."

#### Categorization of Phase B claims

Claims identified via the context-driven approach (Phase B) are **pre-categorized** — no additional matching is needed:

- Terms found in the **metadata context** → categorized as **Metadata**
- Terms found in the **RAG context** (and not in metadata) → categorized as **Database**

This is because Phase B extracts terms directly from the context, so by definition they are grounded.

#### Result

Each claim (from either phase) is assigned to one of three categories:

| Category | Colour (Crystal box) | Meaning |
|----------|---------------------|---------|
| Metadata | Green | Claim found in structured metadata — highest confidence |
| Database (RAG) | Yellow | Claim found in retrieved document chunks |
| LLM | Red (italic) | Claim not found in any data source — generated by the LLM |

For simple RAG agents (without metadata), only two categories exist: Database and LLM.

**What testers should check:**

- Are claims categorized correctly? A claim from the database should not appear as LLM (red).
- Are there false positives? A generic word like "system" matching in the context can cause incorrect grounding. Phase B mitigates this with stop-word filtering and minimum length requirements, but edge cases may occur.
- Are there false negatives? A correct claim may be marked as LLM because the exact phrasing differs (e.g., hyphenation, accent marks, abbreviations). Phase B helps here by matching domain terms that regex would miss.

### 3.3 Step 3 — Confidence Computation

**Goal:** Aggregate the per-claim categorizations into an overall reliability score.

**Computation:**

- **Confidence %** = percentage of claims classified as metadata or database (i.e., not LLM)
- **LLM %** = percentage of claims classified as LLM-generated
- The reliability label is determined by comparing LLM % against configurable thresholds:

| Reliability label | Badge colour | Default condition |
|-------------------|-------------|-------------------|
| **High** | Green | LLM % ≤ 20% |
| **Good** | Yellow | 20% < LLM % < 50% |
| **Poor** | Red | LLM % ≥ 50% |

**Source breakdown display:**

- **Metadata+RAG agents (3-way):** `Metadata: X% | Database: Y% | LLM: Z%`
- **RAG agents (2-way):** `Database: X% | LLM: Y%`

**Small claim count rule:** When total claims < 3, absolute counts are shown instead of percentages (e.g., `Metadata: 2/2 | LLM: 0/2`) because percentages from 1–2 data points are misleading.

**Coverage metric:** In addition to confidence, the system computes a **coverage percentage** — the fraction of response words that are part of identified claims. This answers: "how much of this response was actually checked?"

- **Coverage ≥ 15%:** Normal — a meaningful portion of the response has been verified. The confidence score is trustworthy.
- **Coverage < 15%:** A warning is shown: *"⚠️ Low verifiability: only X% of the response could be checked."* The confidence score may be technically correct for the claims found, but most of the response remains unverified.
- **Coverage = 0% (no claims):** A stronger warning is shown: *"⚠️ No verifiable claims found — this response could not be checked."* This typically happens when the response is completely off-topic (e.g., a recipe from a research agent) or when the LLM produces content that doesn't match any extraction pattern.

**What testers should check:**

- Does the reliability label make sense? A response that is clearly well-grounded should not show "Poor."
- Is the confidence percentage consistent with what you see in the inline highlights?
- Is the coverage adequate? A response with "High" reliability but only 5% coverage is not truly verified.
- Are the thresholds appropriate for this agent's domain? Agents covering broad topics may need different thresholds than narrow-domain agents.

**What the badge shows at each transparency level:**

| Element | Crystal box | Grey box | Black box |
|---------|-------------|----------|-----------|
| Reliability label | ✓ | ✓ | Hidden |
| Source breakdown (%) | ✓ | Hidden | Hidden |
| Confidence + claim count | ✓ | Confidence only | Hidden |
| Coverage warning (when low) | ✓ | Hidden | Hidden |
| LLM model name & provider | ✓ | ✓ | Hidden |
| Prompt level | ✓ | Hidden | Hidden |
| Inline highlights | ✓ | Hidden | Hidden |
| Colour legend | ✓ | Hidden | Hidden |

### 3.4 Known Limitations and Common Issues

**In Step 1 (Claim Identification):**

- *Phase A:* Short or unusual proper nouns may not be detected (e.g., single-word technical terms that are not ALL_CAPS). Very long responses produce many claims, most of which are correctly identified, but occasional false extractions (e.g., a heading mistaken for a claim) may occur.
- *Phase B:* The context-driven approach compensates for most Phase A gaps by matching domain-specific terms directly. However, it depends on the richness of the context — if the metadata or RAG context is sparse, fewer terms will be found.
- *Both phases:* When the response is completely off-topic (e.g., a chocolate cake recipe from a Responsible AI agent in Lax mode), neither phase may identify any claims. The badge will show "0 claims verified" — testers should treat this as a signal that the response could not be verified at all.

**In Step 2 (Claim Categorization):**

- **False positives:** A common word in a Phase A claim happens to appear in the context, causing incorrect grounding. Example: "Machine Learning" matches because "Learning" appears in an unrelated chunk. Phase B claims are less prone to this because of stop-word filtering.
- **False negatives:** The exact phrase or a majority of significant words do not appear in the context, even though the information is correct. Example: "García-López" in the response vs. "Garcia Lopez" (without accents or hyphen) in the database.

**In Step 3 (Confidence Computation):**

- Very few claims (1–2) make percentages unreliable. The absolute count display mitigates this but does not eliminate the problem.
- Zero claims is a special case: the badge defaults to "100% metadata" which may be misleading. Testers should note the "(0 claims verified)" indicator — a response with 0 verifiable claims is not necessarily reliable.
- The thresholds (20% / 50%) are defaults. They may need adjustment for agents where the LLM is expected to contribute more (e.g., summarization tasks) or less (e.g., strict factual lookup).

**Special case — Gap analysis queries:**
Gap analysis ("list topics NOT studied") uses the LLM to reason about what is absent from the data. The badge reflects the actual claim breakdown, which will typically show high LLM content — this is expected and correct for this type of query.

### 3.5 Post-Response Verification (Metadata+RAG Agents)

In addition to the three-step transparency pipeline (which analyses claims in any response), Metadata+RAG agents have a **post-response verification system** that specifically targets LLM hallucinations in paper references. This runs automatically after every response and performs three checks:

#### Pass 1a — Title verification

Every paper title in the response (extracted from quoted or bold text that is followed by author/year metadata) is checked against the full database of known papers.

- **If a title is not found** in any university's paper list, it is flagged inline: `"Fake Paper Title" **⚠️ [not found in database]**`
- Matching uses a 4-word sliding window, so minor variations in phrasing are tolerated.
- Non-title quoted text (e.g., "12 papers on AI & Ethics from UMA") is automatically excluded — only text that appears in a paper-listing format (followed by Authors/Year/PDF) is checked.

#### Pass 1b — Fake PDF removal

For papers that exist in the database but have **no PDF available**, the LLM sometimes fabricates a PDF link using a real paper ID from a completely different paper. This pass detects and removes these fake references.

- If a paper title is recognised but the real paper has no PDF (`pdf_url` and `local_pdf_path` are both empty), any `PDF: W...` reference near the title is replaced with: `PDF: not available for this paper`
- This prevents users from clicking a PDF link that leads to an unrelated paper.

#### Pass 2 — ID-title mismatch detection

Every paper ID (`W` followed by 7+ digits) in the response is cross-checked against the surrounding text (500 characters before the ID) to verify that the title and authors match the actual paper.

- **If the ID exists but the title/authors don't match**, a correction is shown inline:
  `⚠️ Correction — actual paper for W1234567890: "Real Title" by Real Author (Year, University)`
- **If the ID doesn't exist** in any university's paper list, it is marked: `W9999999999 **(not in database)**`

#### Verification summary note

When any issues are detected, a summary note appears at the end of the response:

> ⚠️ **Verification note:**
> **1 fake PDF link(s) removed** — the paper(s) have no PDF available in the database.
> **1 paper title(s) not found in the database — may be hallucinated:**
> - "Fake Paper Title Here"
> **1 paper ID(s) had incorrect titles/authors** — corrections shown inline above.

**What testers should check:**

- After asking for a paper listing, verify that all flagged titles are genuinely not in the database (not false positives from title matching).
- After asking to "expand" a specific paper, verify that the PDF link (if any) points to the correct paper.
- For papers without PDFs, verify the "not available" message appears instead of a fake link.

### 3.6 Decision Flow for Metadata+RAG (EH) Agents

Metadata+RAG agents (Responsible AI, AI & Robotics, Health & Social AI) follow a multi-stage decision flow for every query. Understanding this flow is essential for testers, as each stage determines what data the LLM receives and how the response is evaluated.

#### Stage 1 — Query Classification

The system analyses the user's query to determine its type. Each type triggers a different data pathway:

```
User query
    │
    ├── Affiliation query? ──────────── "List researchers from UMA"
    │   (mentions university + researchers/authors)
    │
    ├── University paper listing? ───── "Papers from TAMK"
    │   (mentions university + papers, no specific topic)
    │
    ├── Topic query? ────────────────── "Papers on AI ethics"
    │   (mentions a research topic/keyword)
    │
    ├── Researcher query? ───────────── "Papers by García López"
    │   (mentions a specific author name)
    │
    ├── Figure/map request? ─────────── "Show a figure of collaborations"
    │   (contains "figure" or "map")
    │
    ├── Gap analysis? ───────────────── "What topics have not been studied?"
    │   (asks about missing/unstudied topics)
    │
    ├── Follow-up? ──────────────────── "Tell me more", "Expand on #3"
    │   (short continuation of previous conversation)
    │
    └── General/content query ───────── "What does this paper say about XAI?"
        (everything else)
```

These checks are applied in priority order — the first match wins. For example, "List researchers from UMA working on AI ethics" matches **affiliation query** (first check), not topic query.

#### Stage 2 — Context Selection

Based on the query type, the system selects which data sources to include in the LLM's context:

| Query type | Metadata context | RAG context | Source type |
|---|---|---|---|
| **Affiliation** | ✓ Researcher list from researchers.json | — | Metadata |
| **University papers** | ✓ Paper list from papers.json | — | Metadata |
| **Topic** | ✓ Topic-specific papers from papers.json | — | Metadata |
| **Researcher** | ✓ Researcher publications | — | Metadata |
| **Figure/map** | — (map generated from structured data) | — | Metadata |
| **Gap analysis** | ✓ Top research topics list | — | Metadata |
| **Follow-up** | — (uses conversation history) | — | RAG |
| **General/content** | — | ✓ ChromaDB semantic search | RAG |

**Key principle:** When structured metadata is available (affiliation, papers, topics, researchers), it is used **instead of** RAG. RAG is only used as a fallback for general content queries where no structured data matches.

**Always included:** The system always adds `_build_metadata_context()` (aggregate statistics: total papers, top topics, cross-university collaborations) to the system prompt, regardless of query type.

#### Stage 3 — System Prompt Assembly

The system prompt is built from three layers:

1. **Prompt sections** (from `prompts.json`) — identity + rules + strict restrictions, filtered by the current prompt level (stringent/tolerant/lax)
2. **Metadata context** — aggregate statistics always included
3. **Query-specific context** — the data selected in Stage 2

```
System prompt = prompts.json sections (filtered by prompt level)
              + Metadata context (always)
              + Affiliation / Papers / Topic / Researcher context (if applicable)
              + RAG context (if no structured data matched)
```

#### Stage 4 — LLM Call

The assembled system prompt + conversation history + user query are sent to the LLM (cloud or local, as configured). The LLM generates a response.

#### Stage 5 — Post-Processing

After the LLM responds, several post-processing steps are applied:

```
LLM response
    │
    ├── 1. Strip map links (if not a figure request)
    │      Removes markdown map links the LLM may have added
    │      despite the "figure/map only" instruction
    │
    ├── 2. Verify paper references (Crystal box / Grey box only)
    │      ├── Pass 1a: Title verification (flag unknown titles)
    │      ├── Pass 1b: Fake PDF removal (papers without PDFs)
    │      └── Pass 2:  ID-title mismatch detection
    │
    ├── 3. Claim extraction (bidirectional)
    │      ├── Phase A: Regex patterns (bold, names, acronyms, etc.)
    │      └── Phase B: Context-derived terms (domain vocabulary)
    │
    ├── 4. Claim categorization
    │      ├── Metadata match → green
    │      ├── Database match → yellow
    │      └── No match → red (LLM)
    │
    ├── 5. Confidence computation
    │      ├── Raw confidence = grounded claims / total claims
    │      └── Penalized confidence = raw - (hallucinations × 20%)
    │
    └── 6. Badge rendering
           ├── Agent tuning line
           ├── Sources line (with verification stats)
           └── Reliability score (based on penalized confidence)
```

#### Stage 6 — Response Delivery

The final response is composed of:
1. **Badge** (HTML above the response text) — Crystal box: 3 lines; Grey box: 3 lines without inline highlights; Black box: nothing
2. **Response text** (with inline claim highlights in Crystal box mode)
3. **Verification notes** (if hallucinations were detected)
4. **Claim highlight data** (sent as a separate SSE event for frontend rendering)

#### Decision Flow Summary

```
Query → Classify → Select context → Build prompt → LLM → Post-process → Badge + Response
         │                │              │                    │
         │                │              │                    ├── Verify papers
         │                │              │                    ├── Extract claims
         │                │              │                    ├── Categorize claims
         │                │              │                    └── Compute confidence
         │                │              │
         │                │              └── prompt level (stringent/tolerant/lax)
         │                │
         │                └── Metadata vs RAG (based on query type)
         │
         └── affiliation / papers / topic / researcher / figure / gap / followup / general
```

**What testers should check at each stage:**

- **Stage 1:** Ask the same question phrased differently and verify it's classified the same way. For example, "researchers at UMA" and "UMA researchers" should both trigger the affiliation path.
- **Stage 2:** Verify that metadata queries don't fall through to RAG (they should show "Metadata" as source type, not "RAG").
- **Stage 3:** Test with all three prompt levels to verify the prompt sections are correctly included/excluded.
- **Stage 5:** Check that hallucinated papers are flagged, fake PDFs are removed, and claims are correctly categorized.
- **Stage 6:** Verify the badge displays correctly at all three transparency levels.

---

## 4. Testing Checklist

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

### Text2SQL-specific verification tests

- [ ] **Schema verification:** Ask a question that should produce a valid query. In crystal_box mode, verify the reliability badge shows high confidence and no unknown tables/columns.
- [ ] **Semantic mismatch detection:** Ask about a specific topic (e.g. "Show agreements with Libya") and check if the generated SQL actually references that topic. If the LLM hallucinates a different query, verify the system blocks it in stringent mode with a "Semantic mismatch" message.
- [ ] **Cross-language equivalences:** Ask in English about a concept stored in Spanish (e.g. "agreements requiring English" when the database uses "INGLÉS"). Verify the semantic check does not flag this as a mismatch.
- [ ] **Broad query detection:** Ask a very generic question (e.g. "Show everything"). Verify the badge flags the query as overly broad if it returns >70% of all rows.
- [ ] **Transparency levels:** Test that SQL is shown in crystal_box and grey_box modes, but hidden in black_box mode.
- [ ] **Tolerant vs stringent:** In tolerant mode, verify that semantic warnings appear but the query still executes. In stringent mode, verify mismatched queries are blocked.

---

## 5. Interpreting the Audit Log

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
| `coverage_pct` | Percentage of response words covered by identified claims (0–100). Low values indicate most of the response could not be verified |
| `total_claims` | Number of verifiable claims extracted from the response |
| `breakdown` | Per-source percentages. RAG+Metadata: `metadata_pct`, `database_pct`, `llm_pct`. RAG: `database_pct`, `llm_pct` |
| `context_sources` | Which context builders were used (RAG+Metadata only) |
| `transparency_level` | Active transparency level at the time of the query |
| `prompt_level` | Active prompt level (`stringent`, `tolerant`, or `lax`) |
| `model` | LLM model name used for this query |
| `is_local_llm` | Whether a local model was used (`true`/`false`) |

**Practical uses for testers:**

- **Tracking badge distribution:** After running a batch of test queries, count how many produced High/Good/Poor labels. If all queries produce the same label, the reliability thresholds may need adjustment.
- **Debugging unexpected responses:** If a response seems wrong, check the audit log for the `source_type` and `breakdown` to understand where the content came from.
- **Comparing models:** Run the same test queries with different LLMs and compare the `confidence` and `breakdown` values across log entries.
- **Compliance verification:** The audit log provides the record-keeping required by the EU AI Act (Article 12). Verify it is enabled (`audit_log_enabled: true` in `config.json`) before deployment.

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

## 6. Model Quality Comparison

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

**Hardware reference for local models:**

| Model | Parameters | Minimum RAM (4-bit) | GPU VRAM needed |
|-------|-----------|--------------------:|:----------------|
| Mistral-7B | 7B | 4–6 GB | Optional (runs on CPU, faster with GPU) |
| Qwen-14B | 14B | 8–10 GB | Recommended (6+ GB VRAM) |
| Mixtral-8x7B | 47B (MoE) | 10–12 GB | Yes (12+ GB VRAM) |
| Mistral-large | ~120B | 30–40 GB | Yes (24+ GB VRAM or multi-GPU) |

**Common hardware and what they can run:**

| Hardware | RAM / VRAM | Max model (4-bit) | Notes |
|----------|-----------|-------------------|-------|
| **Apple M1/M2 (8 GB)** | 8 GB shared | 7B | Runs 7B models slowly via CPU. Suitable for testing only. |
| **Apple M1/M2 Pro (16 GB)** | 16 GB shared | 7B comfortably, 14B tight | Apple Silicon uses unified memory — Ollama leverages the GPU cores automatically. |
| **Apple M1/M2 Max (32 GB)** | 32 GB shared | 14B comfortably, 30B tight | Good for most mid-size models. Response times: ~5–10 tokens/sec for 14B. |
| **Apple M1/M2 Ultra (64+ GB)** | 64–192 GB shared | 70B+ | Can run large models like Mixtral-8x7B and even Mistral-large (with 128 GB+). |
| **Intel Core i7/i9 (32 GB, no GPU)** | 32 GB RAM, no VRAM | 7B (CPU only) | Very slow inference (~1–3 tokens/sec). Not recommended for production use. |
| **Intel Core i9 + RTX 3060 (12 GB)** | 32 GB RAM + 12 GB VRAM | 7B on GPU, 14B offloaded | The 12 GB VRAM handles 7B models well. 14B requires partial CPU offloading (slower). |
| **Intel Core i9 + RTX 4070 Ti (16 GB)** | 32 GB RAM + 16 GB VRAM | 14B on GPU | Good mid-range setup. 14B models run at ~10–15 tokens/sec. |
| **Intel Core i9 + RTX 4090 (24 GB)** | 32 GB RAM + 24 GB VRAM | 30B on GPU, 47B offloaded | Best consumer GPU. Runs Mixtral-8x7B (47B MoE) with partial offloading. ~15–20 tokens/sec for 14B. |
| **Workstation with 2× RTX 4090** | 64 GB RAM + 48 GB VRAM | 70B+ | Can run Mistral-large with model parallelism across GPUs. |
| **Cloud (NVIDIA A100 80 GB)** | 80 GB VRAM | 120B+ | Full Mistral-large at high speed. Typical for research/production deployments. |

**Key takeaways:**

- **For testing:** Any machine with 16+ GB RAM can run 7B models via Ollama (CPU mode). Response quality is lower than larger models but sufficient for functional testing.
- **For production (on-premise):** An RTX 4090 (24 GB) is the best consumer option — it handles 14B models at good speed and can run 30B models acceptably. For 70B+ models, server-grade GPUs or Apple Ultra are needed.
- **Without a GPU:** Intel/AMD CPUs can run 7B models but inference is very slow. This is only suitable for development/debugging, not user-facing deployments.
- **Apple Silicon advantage:** Unified memory means the full RAM is available for model loading (no separate VRAM limit). An M2 Max with 32 GB outperforms an Intel + RTX 3060 for 14B models.

---

## 7. Error Reporting Procedure

When a tester identifies a failure, flaw, or limitation, it must be documented and reported to the developer in a structured way. This section defines the error types and the reporting format.

### 7.1 Error Types

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

### 7.2 Error Report Format

Each error report should include the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| **Date** | Yes | Date of the test |
| **Agent** | Yes | Agent ID and name (e.g. `responsible_ai2 — EH: Responsible AI`) |
| **Error type** | Yes | Code from the table above (e.g. 1.2.1, 2.1, 3.1, 4.3) |
| **Severity** | Yes | **Critical** (agent unusable), **Major** (wrong results), **Minor** (cosmetic/usability) |
| **Query** | Yes | The exact question typed by the tester |
| **Agent response** | Yes | The full response (or a screenshot) |
| **Expected behaviour** | Yes | What the correct response should have been |
| **Agent tuning** | Yes | LLM model, transparency level, prompt level at the time of the test |
| **Steps to reproduce** | If applicable | Any specific sequence of actions needed to trigger the issue |
| **Notes** | Optional | Additional context, related issues, or suggested fix |

### 7.3 Report Template

```
DATE:               2026-04-17
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

### 7.4 Reporting Workflow

```
Tester finds issue
      │
      ▼
Classify error type (1.x / 2.x / 3.x / 4.x)
      │
      ▼
Assess severity (Critical / Major / Minor)
      │
      ▼
Fill in error report template
      │
      ▼
Submit report to developer
      │
      ▼
Developer acknowledges and assigns priority
      │
      ▼
Developer fixes and notifies tester
      │
      ▼
Tester re-tests and closes the issue
```

### 7.5 User Feedback Integration

In addition to structured tester reports, end-users can provide feedback on agent responses using the **feedback widget** that appears after every response (thumbs up / thumbs down + optional category: Incomplete, Wrong, Irrelevant). This feedback is logged to `web/data/feedback_log.jsonl` and can be reviewed by testers and developers to identify recurring issues.

To analyse user feedback:

```bash
# Count feedback by rating
cat web/data/feedback_log.jsonl | jq -r '.rating' | sort | uniq -c

# Show all negative feedback with categories
cat web/data/feedback_log.jsonl | jq 'select(.rating == "down")'

# Filter by agent
cat web/data/feedback_log.jsonl | jq 'select(.agent_id == "responsible_ai2")'
```

User feedback categories map to error types as follows:

| User feedback | Likely error type |
|---------------|-------------------|
| 👎 **Wrong** | 3.2 (Wrong information) or 1.3.1 (Hallucination undetected) |
| 👎 **Incomplete** | 3.1 (Missing information) |
| 👎 **Irrelevant** | 3.3 (Irrelevant response) or 2.3 (SQL mismatch) |
