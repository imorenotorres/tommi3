# Visual Agent Builder — Specification

## Vision

A web-based visual tool that allows non-programmers to design, configure, and deploy TOMMI agents through an interactive interface. The tool replaces manual editing of JSON files and Python code with a guided, visual workflow.

## Phase 1: Visual Config Editor (1-2 weeks)

### Goal
An enhanced "Create Agent" web form that generates all required files and creates a working agent with zero code editing.

### Interface

```
┌────────────────────────────────────────────────────────┐
│  Create New Agent                                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Agent ID: [robotics_ai________]                       │
│  Agent Name: [Robotics & AI Research___]               │
│  Type: [RAG Metadata Vectorless ▼]                     │
│  Description: [Research assistant for...__________]    │
│  Welcome Message: [Hello! I can help... __________]    │
│                                                        │
│  ── Alliance ──────────────────────────────────────    │
│  Alliance Name: [UNINOVIS___]                          │
│  Universities: [+ Add University]                      │
│    UMA  | Universidad de Málaga | Spain | 36.72, -4.42 │
│    USPN | Univ. Sorbonne Paris Nord | France | ...     │
│                                                        │
│  ── Data Sources ─────────────────────────────────     │
│  [📁 Upload papers.json]                               │
│  [📁 Upload researchers.json]                          │
│  [📁 Upload glossary.md]                               │
│  [📁 Upload project docs (folder)]                     │
│                                                        │
│  ── Prompt Design ────────────────────────────────     │
│  Identity: [You are {agent_name}, a research...]       │
│  Rules: [1. Answer only from context...]               │
│  Strict: [CRITICAL: Never present...]                  │
│  [💡 Suggest improvements]  [📋 Use template]          │
│                                                        │
│  ── Behaviour ────────────────────────────────────     │
│  Prompt level: [Stringent ▼]                           │
│  Reliability cues: [Shown ▼]                           │
│  Humility (prompt): [On ▼]                             │
│  Humility (post-processing): [Moderate ▼]              │
│  Scope terms: [AI ethics, fairness, XAI, ...]          │
│                                                        │
│  ── LLM ──────────────────────────────────────────     │
│  Provider: [Mistral ▼]                                 │
│  Model: [mistral-small-latest ▼]                       │
│                                                        │
│  [Preview config.json]  [Create Agent]                 │
└────────────────────────────────────────────────────────┘
```

### What it generates

```
agents/{agent_id}/
├── agent.py           # Standard 3-line wrapper (inherits from base)
├── app.py             # Standard FastAPI wrapper
├── config.json        # Generated from form
├── prompts.json       # Generated from form
├── .env               # LLM provider settings
└── data/
    ├── papers.json        # Uploaded
    ├── researchers.json   # Uploaded
    └── docs/
        ├── Glossary_*.md  # Uploaded
        └── project_docs/  # Uploaded
```

### Implementation

- **Frontend**: Single HTML page at `/static/create_agent_v2.html`
- **Backend**: Enhance existing `/api/create-agent` endpoint in `crear_agente.py`
- **Templates**: Pre-built prompt templates for common agent types (research assistant, campus support, course tutor)
- **Validation**: Client-side validation of JSON structure, server-side validation of file formats

### Existing infrastructure to reuse

- `apps/crear_agente.py` already generates agents from form data
- The current "Create Agent" page (`/static/create_agent.html`) handles the basic flow
- Agent templates are already defined in `crear_agente.py`

---

## Phase 2: Visual Decision Logic Editor (1-2 months)

### Goal
A block-based canvas where users design the agent's classification and context-building logic visually. The tool generates a `logic.json` that the agent reads at runtime.

### Key architectural change

Move the decision logic from Python code to a declarative configuration:

**Current (Python code in rag_metadata_mixin.py):**
```python
if self._is_meta_question(user_message):
    # answer from system prompt
elif self._is_conceptual_question(user_message):
    glossary_ctx = self._build_glossary_context(user_message)
elif ...
```

**Proposed (logic.json, interpreted at runtime):**
```json
{
  "classification_chain": [
    {
      "id": "meta",
      "label": "Meta-question",
      "detector": "meta_question",
      "context_builder": null,
      "cue": "none",
      "action": "answer_from_prompt"
    },
    {
      "id": "non_research",
      "label": "Non-research task",
      "detector": "non_research_task",
      "context_builder": null,
      "cue": "none",
      "action": "refuse"
    },
    {
      "id": "conceptual",
      "label": "Conceptual question",
      "detector": "conceptual_question",
      "context_builder": "glossary",
      "cue": "yellow",
      "cue_no_match": "yellow",
      "action": "llm_with_context"
    },
    {
      "id": "topic_search",
      "label": "Topic search",
      "detector": "has_topic",
      "context_builder": "topic_search",
      "cue": "green",
      "action": "factual_section_plus_commentary"
    }
  ],
  "post_processing": [
    {"step": "authority_sanitisation", "enabled": true},
    {"step": "name_correction", "enabled": true},
    {"step": "paper_verification", "enabled": true},
    {"step": "gap_detection", "enabled": true},
    {"step": "humility_rewriting", "enabled": true, "level": "moderate"}
  ]
}
```

### Interface concept

```
┌─────────────────────────────────────────────────────────┐
│  Agent Decision Logic Editor          [Save] [Preview]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐                                    │
│  │  User Query     │                                    │
│  └────────┬────────┘                                    │
│           │                                             │
│           ▼                                             │
│  ┌─────────────────┐     ┌──────────────────┐           │
│  │ 1. Meta-question│────▶│ System prompt    │  ⚪ None  │
│  │   [Configure ⚙] │  NO │                  │           │
│  └────────┬────────┘     └──────────────────┘           │
│           │ NO                                          │
│           ▼                                             │
│  ┌─────────────────┐     ┌──────────────────┐           │
│  │ 2. Off-topic    │────▶│ Refuse + suggest │  ⚪ None  │
│  │   [Configure ⚙] │ YES │                  │           │
│  └────────┬────────┘     └──────────────────┘           │
│           │ NO                                          │
│           ▼                                             │
│  ┌─────────────────┐     ┌──────────────────┐           │
│  │ 3. Glossary     │────▶│ Glossary context │  🟡 Yel   │
│  │   [Configure ⚙] │ YES │                  │           │
│  └────────┬────────┘     └──────────────────┘           │
│           │ NO                                          │
│           ▼                                             │
│     [+ Add Step]                                        │
│                                                         │
│  ── Post-Processing ─────────────────────────────────   │
│  ☑ Authority sanitisation                               │
│  ☑ Paper verification                                   │
│  ☑ Humility rewriting [Moderate ▼]                      │
│  ☐ Custom step: [_______________]                       │
│                                                         │
│  ── Reliability Cue Preview ─────────────────────────   │
│  [Test query: ________________]  [▶ Simulate]           │
│  Result: Step 3 (Glossary) → 🟡 Yellow                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Features

1. **Drag-and-drop reordering** — change the priority of classification steps
2. **Step configuration** — click ⚙ to edit detector keywords, thresholds, custom patterns
3. **Add/remove steps** — enable/disable classification categories
4. **Cue assignment** — set the reliability cue per step via dropdown
5. **Simulation** — type a test query and see which step catches it, which cue it gets, and what context would be built
6. **Post-processing toggles** — enable/disable each post-processing step
7. **Live preview** — see the generated `logic.json` in real time
8. **Export/import** — save and load logic configurations

### Detectors (built-in library)

| Detector ID | What it matches | Configurable parameters |
|-------------|----------------|------------------------|
| `meta_question` | Questions about the agent itself | Keyword list |
| `non_research_task` | Essays, translations, creative content | Pattern list |
| `topical_scope` | Whether the query is in the agent's domain | Scope terms, glossary terms |
| `conceptual_question` | "What is X?" definition questions | Pattern list |
| `topic_search` | Papers/research on a topic | Topic extraction phrases |
| `researcher_lookup` | Papers by a specific person | Researcher name matching logic |
| `project_query` | About a specific funded project | Project name matching |
| `gap_analysis` | Topics not studied, gaps | Gap phrases list |
| `figure_request` | "Show a figure/map" | Trigger words |
| `followup` | Continues previous conversation | Follow-up patterns |
| `custom_regex` | User-defined regex pattern | Regex + flags |

### Runtime engine

A new class `DeclarativeAgent` that reads `logic.json` and executes the chain:

```python
class DeclarativeAgent(BaseRAGAgent):
    def __init__(self):
        super().__init__()
        self._logic = self._load_logic_config()

    def _classify_query(self, user_message):
        for step in self._logic["classification_chain"]:
            detector = DETECTORS[step["detector"]]
            if detector.matches(user_message, step.get("params", {})):
                return step
        return self._logic.get("fallback", {"action": "rag_retrieval"})

    def _build_context(self, step, user_message):
        builder = CONTEXT_BUILDERS[step["context_builder"]]
        return builder.build(self, user_message)
```

### Migration path

Existing agents (Responsible AI3, Health & Wellbeing) would continue using the current Python code. New agents could choose between:
- **Code mode** — inherit from `MetadataRAGMixin` (current approach)
- **Declarative mode** — use `DeclarativeAgent` with `logic.json` (new approach)

Both modes share the same base classes, post-processing pipeline, and reliability cue system.

---

## Phase 3: Full No-Code Agent Builder (3-6 months)

### Goal
A complete platform for creating, testing, and deploying agents without writing any code. Combines Phase 1 + Phase 2 with additional tools.

### Additional features

1. **Data pipeline wizard**
   - Upload raw documents (PDF, DOCX, CSV)
   - Automatic extraction of papers, researchers, topics
   - Glossary creation assistant (suggest terms from document content)
   - Preview and edit extracted data before indexing

2. **Prompt design studio**
   - Template library (research assistant, campus support, course tutor)
   - A/B testing: compare two prompt versions side by side
   - Prompt quality score based on known best practices
   - Integration with the PROMPT Assistant agent for suggestions

3. **Test harness**
   - Upload a set of test queries with expected answers
   - Run benchmarks with one click
   - Visual comparison of results across prompt versions or models
   - Export test reports (PDF, CSV)

4. **Deployment dashboard**
   - One-click deploy to production
   - Rollback to previous version
   - Real-time monitoring (queries/hour, error rate, avg confidence)
   - Alerts for anomalies (sudden spike in low-confidence responses)

5. **Collaboration**
   - Multiple users can edit the same agent
   - Version history with diff view
   - Comments and review workflow
   - Share agent templates across UNINOVIS partners

### Architecture

```
┌─────────────────────────────────────────────────┐
│                Visual Agent Builder             │
│  (web/static/builder/)                          │
├──────────┬──────────┬──────────┬────────────────┤
│ Config   │ Logic    │ Prompt   │ Test           │
│ Editor   │ Editor   │ Studio   │ Harness        │
│ (Phase1) │ (Phase2) │ (Phase3) │ (Phase3)       │
├──────────┴──────────┴──────────┴────────────────┤
│              Builder API                        │
│  /api/builder/create, /api/builder/logic,       │
│  /api/builder/test, /api/builder/deploy         │
├─────────────────────────────────────────────────┤
│              TOMMI Core                         │
│  BaseRAGAgent, DeclarativeAgent, mixins         │
├─────────────────────────────────────────────────┤
│              LLM Layer                          │
│  Mistral, Ollama, vLLM                          │
└─────────────────────────────────────────────────┘
```

---

## Technical Requirements

### Phase 1
- Frontend: HTML/JS (no framework needed)
- Backend: Extend `crear_agente.py`
- Storage: File system (same as current)
- Auth: Superuser only

### Phase 2
- Frontend: HTML/JS with a lightweight canvas library (e.g., Drawflow, Rete.js, or custom SVG)
- Backend: New `DeclarativeAgent` class + logic parser
- Storage: `logic.json` per agent
- Auth: Superuser + tester (read-only for testers)
- Migration: Existing agents unaffected

### Phase 3
- Frontend: Vue.js or React SPA (justified by complexity)
- Backend: New `/api/builder/` endpoints
- Storage: SQLite for versions, collaboration metadata
- Auth: Role-based (viewer, editor, admin)
- Deployment: CI/CD integration for production deploys

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Declarative logic less flexible than Python | Medium | Keep code mode as fallback; add `custom_regex` detector |
| Visual editor complexity | High | Start with Phase 1 (simple form) and validate with users |
| Performance of runtime logic engine | Low | The chain is short (10-12 steps) — negligible overhead |
| Backward compatibility | Medium | Existing agents keep using Python; new agents choose mode |
| User adoption | Medium | Provide templates and guided wizards; test with UNINOVIS partners |

---

## Recommended Timeline

| Phase | Duration | Deliverable | Who benefits |
|-------|----------|-------------|-------------|
| **Phase 1** | 1-2 weeks | Visual config editor | Developers (faster agent creation) |
| **Phase 2** | 1-2 months | Decision logic editor + DeclarativeAgent | Developers + advanced testers |
| **Phase 3** | 3-6 months | Full no-code builder | Non-technical staff, UNINOVIS partners |

## Next Steps

1. **Validate Phase 1** with current users — does the existing "Create Agent" page need improvement?
2. **Prototype Phase 2** with a single agent — convert Responsible AI3's logic to `logic.json` and verify it produces identical results
3. **User interviews** — what do UNINOVIS partners actually need to build agents independently?
