# What is an AI Agent?

## A simple definition

An AI Agent is a software program that interacts with a user to accomplish tasks. At its core, every AI Agent follows four steps:

1. **Perception** — The agent receives a request from the user, typically in natural language ("Show me agreements in Italy") but also through clicks, form selections, or other interactions.

2. **Reasoning** — The agent analyses the request to understand what the user wants. This is the agent's *decision logic* — it classifies the request and decides which action to take.

3. **Action** — The agent performs one or more actions: querying a database, searching documents, calling a language model, generating a visualisation, or simply declining a request that is outside its scope.

4. **Production** — The agent formats the result and delivers it to the user: a text answer, a table, a map, a chart, or a message explaining why it cannot help.

```
          ┌──────────┐
          │   User   │
          └────┬─────┘
               │ question, click, or selection
               ▼
        ┌────────────────┐
        │ 1. Perception  │
        └───────┬────────┘
                │
                ▼
        ┌────────────────┐
        │  2. Reasoning   │  ◄── The agent's decision logic
        └───────┬────────┘
                │
                ▼
        ┌────────────────┐
        │   3. Action     │  ◄── Query DB, call LLM, generate map...
        └───────┬────────┘
                │
                ▼
        ┌────────────────┐
        │ 4. Production   │  ◄── Text, table, map, refusal...
        └───────┬────────┘
               │
               ▼
          ┌──────────┐
          │   User   │
          └──────────┘
```

Not every agent needs artificial intelligence in every step. Some agents use AI only for reasoning (understanding the question), others use it only for action (generating text), and some use no AI at all — relying instead on rules and structured data.

---

## Example 1: A Calculator Agent

The simplest possible agent. It receives a mathematical expression, evaluates it, and returns the result. No AI is involved at any stage.

```
User: "What is 15% of 230?"

  ┌────────────┐
  │ Perception  │  "What is 15% of 230?"
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Reasoning   │  Parse: operation = percentage, values = 15, 230
  │             │  (rule-based parsing, no AI)
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Action      │  Calculate: 230 × 0.15 = 34.5
  │             │  (arithmetic, no AI)
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Production  │  "15% of 230 is 34.5"
  └────────────┘
```

**Key point:** This agent has logic (it must parse "15% of 230" into a calculation), but no AI. The reasoning is rule-based.

---

## Example 2: A FAQ Chatbot

A slightly more complex agent. It receives a question, finds the most relevant answer from a list of predefined Q&A pairs, and returns it.

```
User: "What are your opening hours?"

  ┌────────────┐
  │ Perception  │  "What are your opening hours?"
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Reasoning   │  Match question against FAQ database
  │             │  using keyword similarity
  │             │  Best match: "Opening hours" → answer #12
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Action      │  Retrieve answer #12 from FAQ database
  │             │  (database lookup, no AI)
  └─────┬──────┘
        │
  ┌─────▼──────┐
  │ Production  │  "We are open Monday to Friday,
  │             │   9:00 to 17:00."
  └─────────────┘
```

**Key point:** The reasoning uses keyword matching (simple AI or just text similarity). The action is a database lookup. The production is a pre-written answer — no text generation.

---

## Example 3: Algoria Map (Mobility Agreements Explorer)

A real TOMMI agent that helps users explore university mobility agreements on an interactive map. It uses AI for reasoning (understanding the query) but not for the action (data comes directly from the database).

### Via the standalone web page (no AI at all):

```
User: selects "Italia" from Country dropdown

  ┌────────────┐
  │ Perception  │  Form selection: country = Italia
  └─────┬──────┘
        │
  ┌─────▼──────────┐
  │ Reasoning       │  Extract filter: {country: "Italia"}
  │                 │  (client-side code, no AI)
  └─────┬──────────┘
        │
  ┌─────▼──────────┐
  │ Action          │  Query SQLite: SELECT ... WHERE
  │                 │    destination_country = 'Italia'
  │                 │  Build map markers with coordinates
  │                 │  (database + geocoding, no AI)
  └─────┬──────────┘
        │
  ┌─────▼──────────┐
  │ Production      │  Render Leaflet map zoomed to Italy
  │                 │  with clustered university markers
  │                 │  (visualisation, no AI)
  └────────────────┘
```

### Via the chat interface (AI for reasoning only):

```
User: "Show agreements in Italy for Engineering"

  ┌────────────┐
  │ Perception  │  "Show agreements in Italy for Engineering"
  └─────┬──────┘
        │
  ┌─────▼──────────┐
  │ Reasoning       │  LLM extracts filters using tool calling:
  │                 │  {country: "Italia",
  │   ┌─────────┐  │   faculty: "Ingenierías Industriales"}
  │   │   LLM   │  │
  │   └─────────┘  │  (AI used here)
  └─────┬──────────┘
        │
  ┌─────▼──────────┐
  │ Action          │  Query SQLite with filters
  │                 │  Build map markers
  │                 │  (database, no AI)
  └─────┬──────────┘
        │
  ┌─────▼──────────┐
  │ Production      │  Render map + summary text
  │                 │  (visualisation, no AI)
  └────────────────┘
```

**Key point:** The same agent can work with or without AI. The standalone page uses form-based reasoning (no AI), while the chat interface uses an LLM to understand natural language. In both cases, the data comes directly from the database — the AI never touches the results.

---

## Example 4: A Course Tutor Agent

An educational agent that answers student questions from course materials. It uses AI for both reasoning and action.

```
User: "Explain the difference between TCP and UDP"

  ┌────────────┐
  │ Perception  │  "Explain the difference between TCP and UDP"
  └─────┬──────┘
        │
  ┌─────▼──────────┐
  │ Reasoning       │  Classify: conceptual question
  │                 │  Search course materials for
  │                 │  "TCP" and "UDP"
  │                 │  Found: Lecture 5 slides, Chapter 3
  │                 │  (keyword search, no AI)
  └─────┬──────────┘
        │
  ┌─────▼──────────┐
  │ Action          │  Send to LLM:
  │                 │    System: "You are a course tutor..."
  │   ┌─────────┐  │    Context: [Lecture 5 + Chapter 3]
  │   │   LLM   │  │    Question: "Explain the difference..."
  │   └─────────┘  │
  │                 │  LLM generates explanation from
  │                 │  course materials
  │                 │  (AI used here)
  └─────┬──────────┘
        │
  ┌─────▼──────────┐
  │ Production      │  "Based on your course materials:
  │                 │   TCP is a connection-oriented protocol
  │                 │   that guarantees delivery, while UDP
  │                 │   is connectionless and faster but
  │                 │   does not guarantee delivery..."
  │                 │
  │                 │  🟡 AI interpretation of course content
  └────────────────┘
```

**Key point:** The reasoning is rule-based (keyword search in course materials), but the action requires AI — the LLM reads the relevant slides and generates a human-readable explanation. The reliability cue (yellow) tells the student that the answer is an AI interpretation of real course content.

---

## Example 5: TOMMI Research Assistant (Metadata+RAG)

The most complex TOMMI agent. It combines multiple data sources, a sophisticated decision logic, and different response types depending on the question.

### Query: "Papers on AI ethics from UMA"

```
User: "Papers on AI ethics from UMA"

  ┌────────────┐
  │ Perception  │  "Papers on AI ethics from UMA"
  └─────┬──────┘
        │
  ┌─────▼───────────────┐
  │ Reasoning            │
  │                      │
  │  Classification:     │
  │  ✗ Meta-question?    │  No
  │  ✗ Off-topic?        │  No
  │  ✗ Conceptual?       │  No
  │  ✗ Project query?    │  No
  │  ✓ Topic search?     │  Yes! topic="AI ethics"
  │                      │         university=UMA
  │  (rule-based chain,  │
  │   no AI)             │
  └─────┬───────────────┘
        │
  ┌─────▼───────────────┐
  │ Action               │
  │                      │
  │  1. Search papers.json for "AI ethics"
  │     filtered by UMA
  │     → Found 8 papers (no AI)
  │                      │
  │  2. Build factual section with
  │     paper titles, authors, years
  │     → 🟢 Green banner (no AI)
  │                      │
  │  3. Send to LLM for commentary:
  │   ┌─────────┐       │
  │   │   LLM   │       │  "Analyse these 8 papers..."
  │   └─────────┘       │
  │     → 🟡 Yellow banner (AI)
  └─────┬───────────────┘
        │
  ┌─────▼───────────────┐
  │ Production           │
  │                      │
  │  🟢 Verified data:   │
  │  8 papers from UMA   │
  │  on AI ethics...     │
  │                      │
  │  🟡 AI Commentary:   │
  │  "The data suggests  │
  │  UMA focuses on..."  │
  └─────────────────────┘
```

### Query: "What is the weather today?"

```
User: "What is the weather today?"

  ┌────────────┐
  │ Perception  │  "What is the weather today?"
  └─────┬──────┘
        │
  ┌─────▼───────────────┐
  │ Reasoning            │
  │                      │
  │  Classification:     │
  │  ✗ Meta-question?    │  No
  │  ✓ Off-topic?        │  Yes!
  │                      │
  │  (rule-based, no AI) │
  └─────┬───────────────┘
        │
  ┌─────▼───────────────┐
  │ Action               │
  │                      │
  │  Action: Refuse      │
  │  (no database query, │
  │   no LLM call)       │
  └─────┬───────────────┘
        │
  ┌─────▼───────────────┐
  │ Production           │
  │                      │
  │  "This question is   │
  │  outside my scope.   │
  │  I can help with     │
  │  AI ethics research."│
  │                      │
  │  (no reliability cue │
  │   — refusal is not   │
  │   unreliable content)│
  └─────────────────────┘
```

**Key point:** The same agent handles both queries, but the decision logic routes them to completely different actions. The topic search uses the database and the LLM. The off-topic query uses neither — just a polite refusal. The reliability cues reflect this: green for verified data, yellow for AI interpretation, nothing for a refusal.

---

## Example 6: A Text-to-SQL Agent

An agent that translates natural language questions into database queries. The AI is used for translation (reasoning), but the data comes directly from the database (action).

```
User: "How many agreements require English B2?"

  ┌────────────┐
  │ Perception  │  "How many agreements require English B2?"
  └─────┬──────┘
        │
  ┌─────▼───────────────┐
  │ Reasoning            │
  │                      │
  │  Translate to SQL:   │
  │   ┌─────────┐       │
  │   │   LLM   │       │
  │   └─────────┘       │
  │  → SELECT COUNT(*)   │
  │    FROM destinations │
  │    WHERE lang_1_name │
  │    = 'INGLÉS'        │
  │    AND lang_1_level  │
  │    = 'B2'            │
  │                      │
  │  Verify SQL:         │
  │  ✓ Tables exist      │
  │  ✓ Columns valid     │
  │  ✓ Semantics match   │
  │  (AI + verification) │
  └─────┬───────────────┘
        │
  ┌─────▼───────────────┐
  │ Action               │
  │                      │
  │  Execute SQL against │
  │  SQLite database     │
  │  → Result: 522       │
  │  (database, no AI)   │
  └─────┬───────────────┘
        │
  ┌─────▼───────────────┐
  │ Production           │
  │                      │
  │  🟡 AI interpretation│
  │  (the translation    │
  │   step used AI)      │
  │                      │
  │  🟢 Verified data    │
  │  "522 agreements     │
  │   require English B2"│
  └─────────────────────┘
```

**Key point:** The AI is in the *reasoning* step (translating English to SQL), not in the data. The result (522) comes directly from the database. The reliability cues reflect this split: yellow for the AI translation risk, green for the verified database result. If the AI mistranslates the question, the SQL verification step catches the error.

---

## Summary: Where does AI appear in each example?

| Agent | Perception | Reasoning | Action | Production |
|-------|------------|-----------|--------|------------|
| Calculator | Text | Rules | Arithmetic | Text |
| FAQ Chatbot | Text | Keywords | DB lookup | Pre-written |
| Algoria Map (standalone) | Form | Rules | DB + map | Visualisation |
| Algoria Map (chat) | Text | **LLM** | DB + map | Visualisation |
| Course Tutor | Text | Keywords | **LLM** | Text + cue |
| Research Assistant | Text | Rules | DB + **LLM** | Text + cues |
| Text-to-SQL | Text | **LLM** + verify | DB | Text + cues |

The table shows that AI is a tool used in specific steps — not a blanket requirement. An agent's intelligence comes from its *decision logic* (the Reasoning step), which can be rule-based, AI-based, or a combination of both. The more complex the agent, the more steps may involve AI — but even the most complex agents use direct database access (no AI) for their most reliable outputs.

---

## What makes a good AI Agent?

A well-designed agent:

1. **Uses AI only where needed.** Direct database access is faster, cheaper, and more reliable than AI generation. Use AI for interpretation and synthesis, not for data retrieval.

2. **Is transparent about its sources.** When the answer comes from the database, say so (green). When AI interprets the data, say so (yellow). When AI speculates, say so (red). When the agent cannot help, say so with no misleading cue.

3. **Has clear decision logic.** The reasoning step should be predictable: the same question should always be routed to the same action. If the logic is unpredictable, the agent is unreliable.

4. **Fails gracefully.** When the agent does not know the answer, it should say so honestly — not fabricate information. A good refusal is more valuable than a confident hallucination.

5. **Separates concerns.** The decision logic, the actions, the prompts, and the data should be independent components that can be tested, replaced, and improved separately.
