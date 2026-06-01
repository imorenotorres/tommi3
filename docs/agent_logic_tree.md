# Responsible AI3 Agent — Decision Logic Tree

## 1. Query Classification (what type of question is this?)

```
User Query
│
├─ Meta-question? ("What can you do?", "What is UNINOVIS?")
│  → Answer from system prompt
│  → NO banner
│  → NO paper verification
│
├─ Non-research task? ("Write an essay", "Translate this")
│  → Refuse politely
│  → NO banner
│
├─ Off-topic? ("What's the weather?", "Book a flight")
│  → Refuse, suggest in-scope topics
│  → NO banner
│
├─ Disambiguation follow-up? (user replied "1", "2" to a researcher list)
│  → Look up stored candidate, build researcher context
│  → NO banner
│
├─ Web expansion? ("Search the web for...")
│  → Combine web search + local RAG context
│  → 🟡 Yellow banner
│
├─ Follow-up? ("Expand on point 1", "Tell me more")
│  → Use conversation history
│  → 🟡 Yellow banner
│
├─ Figure/Map request? (contains "figure" or "map")
│  → Generate map link (no data context needed)
│  → See Section 3 for map type selection
│
├─ Gap analysis? ("topics not studied", "least studied", "gaps")
│  → Use metadata + LLM reasoning
│  → 🔴 Red banner (speculation)
│
├─ Otherwise → Content query (see Section 2)
```

## 2. Content Query — Context Building Chain

```
Content Query
│
│  Each step is tried in order. If a step produces context,
│  later steps are SKIPPED (first match wins).
│
├─ 1. Conceptual question? ("What is fairness in AI?")
│     │  Excluded if: project query, researcher query
│     │  → Build glossary context
│     │  → 🟡 Yellow banner
│     │  → If term in glossary: "According to the glossary..."
│     │  → If term NOT in glossary: "Not defined in glossary, but based on papers..."
│     │
│     └─ STOP (skip steps 2-7)
│
├─ 2. Project query? ("What is TAILOR project?", "grants on AI")
│     │  → Build project context from project_docs/
│     │  → 🟡 Yellow banner
│     │
│     └─ STOP (skip steps 3-7)
│
├─ 3. Affiliation/researcher listing? ("List researchers from THUAS")
│     │  → Build affiliation context from researchers.json
│     │  → 🟡 Yellow banner
│     │
│     └─ STOP (skip steps 4-7)
│
├─ 4. Shared topics between universities? ("Topics shared by UMA and USPN")
│     │  → Build cross-university topic comparison
│     │  → 🟢 Green banner (programmatic factual section)
│     │
│     └─ STOP (skip steps 5-7)
│
├─ 5. University paper listing? ("List papers from UMA", no topic)
│     │  → Build from *_papers.json (authoritative)
│     │  → 🟢 Green banner (programmatic)
│     │
│     └─ STOP (skip steps 6-7)
│
├─ 6. Topic search? ("Papers on AI ethics", "Research on fairness")
│     │  Excluded if: researcher query detected
│     │  → search_papers_by_topic() from papers.json
│     │  → Programmatic factual section:
│     │     ├─ ≤30 papers: full list with details
│     │     └─ >30 papers: summary per university, top 3 cited
│     │  → 🟢 Green banner (factual) + 🟡 Yellow (LLM commentary)
│     │
│     └─ STOP (skip step 7)
│
├─ 7. Researcher lookup? ("Papers by Rubén González")
│     │  → Match researcher name in researchers.json:
│     │     ├─ Exact match → build full context
│     │     ├─ Single partial match → build full context
│     │     ├─ Multiple partial matches → disambiguation list
│     │     │    → NO banner, ask user to choose
│     │     └─ No match → "" (fall through to RAG)
│     │  → NO banner (structured database data)
│     │
│     └─ STOP
│
└─ 8. Fallback: RAG retrieval
      → Retrieve chunks from document database
      → 🟡 Yellow banner (AI interpretation)
```

## 3. Figure/Map Type Selection

```
Query contains "figure" or "map"?
│
├─ About PROJECTS? ("project", "grant", "funding")
│  ├─ Specific topic mentioned? → PROJECT-TOPIC map
│  └─ No topic (all projects)? → PROJECTS map
│
├─ About COLLABORATIONS? → COLLABORATION map
│
├─ About PAPERS?
│  ├─ Specific topic mentioned? → TOPIC map
│  └─ No topic (all publications)? → PUBLICATIONS map
│
└─ Optional filters: ?year=YEAR, ?topic=TOPIC
```

## 4. Reliability Cue Logic

```
Response ready — which banner?
│
├─ Meta-question → NO BANNER
├─ Non-research task refusal → NO BANNER
├─ Off-topic refusal → NO BANNER
├─ Researcher disambiguation → NO BANNER
├─ Researcher lookup (definitive match) → NO BANNER
│
├─ Gap analysis → 🔴 RED (speculation beyond data)
├─ Attribution not verified (⚠️ markers) → 🟡 YELLOW (check flagged items)
│
├─ Programmatic factual section → 🟢 GREEN (verified, no AI)
│  (topic search, university papers, shared topics)
│
├─ Conceptual/glossary → 🟡 YELLOW (AI interprets glossary)
├─ Project data → 🟡 YELLOW (AI interprets project docs)
├─ RAG retrieval → 🟡 YELLOW (AI interprets documents)
├─ Follow-up → 🟡 YELLOW (AI uses conversation history)
├─ Web expansion → 🟡 YELLOW (external sources)
│
├─ "How many" query → 🟡 YELLOW + count approximation note
│
└─ reliability_cues = "hidden" → NO BANNER (all suppressed)
```

## 5. Post-Processing Pipeline

```
LLM Response
│
├─ 1. Humility (system prompt) — if humility_prompt = "on"
│     Pre-generation hedging instructions based on context quality
│
├─ 2. Authority sanitization — always
│     Replace "has not been studied" → "does not appear in the indexed database"
│     Replace "well-known" → "commonly discussed"
│
├─ 3. Paper verification — if not meta-question, not off-topic
│     Check quoted titles against papers.json
│     Flag unrecognised titles with ⚠️
│     Verify paper IDs match titles
│
├─ 4. Unsolicited gap injection — if user didn't ask about gaps
│     Detect LLM volunteering gap analysis
│     Inject 🔴 red banner before speculative section
│
├─ 5. Off-topic detection — check first 300 chars
│     If refusal detected → remove any banner
│
├─ 6. Humility (post-processing) — if humility_postprocessing ≠ "off"
│     Add hedging prefixes to ungrounded claims
│     Moderate: hedge LLM-only claims
│     Strict: hedge LLM + web claims, add disclaimer
│
└─ Final response sent to user
```

## 6. Researcher Name Matching

```
User mentions a name
│
├─ Exact full name in message? ("Rubén González Vallejo")
│  → Exact match → show papers directly
│
├─ Surname match? (≥4 chars: "Vallejo", "Schleif")
│  → Partial match
│
├─ First + any surname combo? (≥9 chars: "Rubén González")
│  → Partial match
│
├─ First name only? (≥5 chars: "Rubén", "Frank-Michael")
│  → Partial match
│
└─ Partial match results:
   ├─ 1 match → treat as definitive, show papers
   ├─ >1 matches → disambiguation list, ask user to choose
   └─ 0 matches → no researcher context, fall through to RAG
```
