# TommiEdu — Design Document

## 1. Vision

TommiEdu is an AI-powered educational support platform for the UNINOVIS alliance, inspired by platforms like LearnWise but built on European values: transparency, data sovereignty, and EU AI Act compliance. It provides course-aware AI tutoring, campus support, and institutional knowledge management for students, faculty, and staff across UNINOVIS partner universities.

TommiEdu reuses the architectural concepts proven in TOMMI3 (RAG agents, reliability cues, humility mechanisms, audit logging) but operates as an independent platform with its own codebase, user management, and frontend.

## 2. Deployment Architecture

### Same server, separate app (Option 1)

```
gloria.uma.es/              → TOMMI3 (research agents)
gloria.uma.es/edu/           → TommiEdu (educational platform)
```

Both run as independent FastAPI applications behind nginx:

```
nginx (port 443)
├── location /          → proxy_pass http://127.0.0.1:8000  (TOMMI3)
└── location /edu/      → proxy_pass http://127.0.0.1:8100  (TommiEdu)
```

### Shared resources
- **Server hardware**: same machine (gloria.uma.es)
- **LLM backend**: shared Mistral API key or shared Ollama instance
- **SSL certificate**: same wildcard or multi-domain cert

### Independent resources
- **Codebase**: separate Git repository (`tommi-edu/`)
- **Database**: separate user DB, course DB, content DB
- **Auth system**: independent (can integrate with university SSO later)
- **Static files**: own frontend at `/edu/static/`
- **Data storage**: own course materials, not shared with TOMMI3

## 3. Core Modules

### 3.1 AI Course Tutor

One RAG agent per course, automatically created when a faculty member uploads course materials.

**How it works:**
1. Faculty uploads syllabus, slides, readings (PDF, DOCX, MD)
2. System chunks and indexes documents (BM25 or vector)
3. Students ask questions → agent answers from course materials only
4. Reliability cues show whether answers come from course documents or LLM interpretation

**Key features:**
- Course-scoped: each agent only knows its own course materials
- Study aids: generate quiz questions, flashcards, summaries from course content
- Multi-language: responds in the student's language
- Transparency: students see which document/slide the answer comes from

**Data model:**
```
Course
├── id, name, code, semester
├── university (UNINOVIS partner)
├── faculty_owner (who created it)
├── materials/ (uploaded documents)
├── chunk_db.json (indexed content)
└── config.json (agent settings)
```

### 3.2 Campus Support Bot

A general-purpose agent per university that answers institutional questions from FAQs, regulations, and policies.

**Data sources:**
- Student handbook, academic regulations
- FAQ pages, admissions info
- Administrative procedures (enrollment, exams, Erasmus)
- Event calendar, deadlines

**Scope management:**
- Each university has its own campus bot with its own documents
- Cross-university questions (e.g., "How does Erasmus work between UMA and THUAS?") could be handled by a shared UNINOVIS bot

### 3.3 Faculty Dashboard

Web interface for faculty to:
- Create and manage course agents
- Upload/update course materials
- View student usage analytics (anonymized)
- Configure agent behavior (prompt level, reliability cues)
- Review and curate AI-generated quiz questions

### 3.4 Student Interface

Minimal, focused interface:
- Course selector (only enrolled courses)
- Chat with course tutor
- Study tools (quiz mode, flashcard mode, summary mode)
- Reliability cues to build AI literacy

## 4. User Roles and Authentication

| Role | Access | Description |
|------|--------|-------------|
| **Student** | Own enrolled courses only | Chat, study aids, view materials |
| **Faculty** | Own courses + dashboard | Create agents, upload materials, view analytics |
| **Admin** | All courses at their university | Manage campus bot, user management, compliance |
| **UNINOVIS Admin** | Cross-university | Alliance-wide analytics, shared resources |

### Authentication options (phased):
1. **Phase 1**: Username/password (like TOMMI3)
2. **Phase 2**: University SSO integration (SAML/CAS via each university's IdP)
3. **Phase 3**: LTI 1.3 integration (launch from Moodle/Canvas)

## 5. LMS Integration (LTI 1.3)

TommiEdu can be embedded inside Moodle, Canvas, or Blackboard as an LTI tool:

```
Student opens Moodle course → clicks "AI Tutor" →
  iframe loads TommiEdu → authenticated via LTI →
  shows course-specific agent
```

**LTI provides:**
- User identity (name, role, email)
- Course context (which course the student is in)
- Grade passback (for quiz scores, if desired)

**Implementation:**
- FastAPI LTI 1.3 library (e.g., `pylti1p3`)
- Platform registration per university's Moodle/Canvas instance
- Tool deployment as iframe within LMS

## 6. Transparency Features (Differentiator)

TommiEdu inherits TOMMI3's transparency framework, adapted for education:

| Feature | Educational Adaptation |
|---------|----------------------|
| **Reliability cues** | "This answer comes from your course slides" (green) vs "The AI is interpreting the material" (yellow) |
| **No banner for refusals** | "This question is outside the course scope" — no misleading cue |
| **Humility** | Hedging on uncertain answers: "Based on the lecture notes, it appears that..." |
| **Audit logging** | Track which topics students struggle with (anonymized) |
| **Source attribution** | Show which slide/page/section the answer comes from |

This is a **competitive advantage** over commercial platforms like LearnWise, which offer no transparency about AI reasoning.

## 7. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Backend** | FastAPI (Python) | Same as TOMMI3, proven stack |
| **Frontend** | HTML/JS (lightweight) or Vue.js | Phase 1: plain HTML like TOMMI3. Phase 2: SPA |
| **LLM** | Mistral (cloud) / Ollama (local) | European LLM, data sovereignty |
| **Indexing** | BM25 (vectorless) or ChromaDB | Course materials are small enough for BM25 |
| **Database** | SQLite (phase 1) / PostgreSQL (phase 2) | Users, courses, analytics |
| **Auth** | JWT sessions (phase 1) / SAML+LTI (phase 2) | Progressive complexity |
| **Deployment** | systemd + nginx | Same as TOMMI3 on gloria.uma.es |

## 8. Directory Structure

```
tommi-edu/
├── web/
│   ├── app.py                 # FastAPI main server
│   ├── auth.py                # Authentication (JWT, later SSO/LTI)
│   ├── lti.py                 # LTI 1.3 integration (phase 2)
│   ├── llm_client.py          # LLM abstraction (adapted from TOMMI3)
│   ├── .env                   # LLM keys, DB config
│   └── static/
│       ├── student.html       # Student chat interface
│       ├── faculty.html       # Faculty dashboard
│       └── admin.html         # Admin panel
├── agents/
│   ├── base/
│   │   ├── course_agent.py    # Base class for course tutors
│   │   ├── campus_agent.py    # Base class for campus support bots
│   │   ├── indexer.py         # Document chunking and indexing
│   │   ├── badges.py          # Reliability cues (adapted from TOMMI3)
│   │   └── humility.py       # Humility rewriter (adapted from TOMMI3)
│   └── courses/
│       └── {course_id}/       # Auto-created per course
│           ├── config.json
│           ├── materials/     # Uploaded documents
│           └── chunk_db.json  # Indexed content
├── data/
│   ├── users.db               # User accounts
│   ├── courses.db             # Course registry
│   └── analytics.db           # Usage analytics (anonymized)
├── scripts/
│   ├── setup.sh               # Installation script
│   └── create_course.py       # CLI course creation
└── README.md
```

## 9. Development Phases

### Phase 1: Course Tutor MVP (2-3 months)
- Faculty uploads PDFs → agent auto-created
- Students chat with course agent
- Reliability cues (green/yellow)
- Basic auth (username/password)
- Deploy on gloria.uma.es/edu/
- **Target: 2-3 pilot courses at UMA**

### Phase 2: Campus Support + LMS Integration (3-4 months)
- Campus support bot per university
- LTI 1.3 integration with Moodle
- University SSO (UMA first)
- Faculty dashboard with analytics
- Study aids (quiz generation, summaries)
- **Target: UMA-wide pilot**

### Phase 3: UNINOVIS Rollout (4-6 months)
- Multi-university deployment
- Cross-university features (shared courses, Erasmus info)
- Advanced analytics and compliance reporting
- Multi-language support optimization
- **Target: All 8 UNINOVIS partners**

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| **LLM hallucination in educational context** | Reliability cues + humility + strict prompt rules. Students learn to check sources. |
| **Data privacy (student data)** | Self-hosted, European LLMs, GDPR compliance by design, no external data sharing |
| **Faculty adoption** | Minimal setup (upload PDFs, done). No technical expertise required. |
| **Scalability** | BM25 indexing is lightweight. One Mistral API key serves many courses. |
| **Content quality** | Faculty curates materials. Agent only answers from uploaded content. |
| **Multilingual** | Mistral handles 100+ languages. Course materials may be in local language. |

## 11. Competitive Advantages over LearnWise

1. **Transparency**: Reliability cues show students exactly how trustworthy each answer is — no commercial platform offers this
2. **EU AI Act compliance**: Audit logging, explainability, and risk assessment built in from day one
3. **Data sovereignty**: Self-hosted on European infrastructure, European LLMs, no student data leaves the EU
4. **Open source**: Universities can inspect, modify, and extend the platform
5. **Research-backed**: Built by researchers who understand AI limitations and educational needs
6. **Cost**: No per-seat licensing fees — universities only pay for LLM API usage (or use free local models)
7. **UNINOVIS network effect**: Shared courses, cross-university tutoring, Erasmus integration

## 12. Next Steps

1. **Validate with stakeholders**: Present this design to UNINOVIS partners
2. **Prototype**: Build Phase 1 MVP with 1-2 pilot courses at UMA
3. **Funding**: Explore Erasmus+ KA2, Horizon Europe, or national digital education grants
4. **Team**: Identify developers at each partner university for collaborative development
