# HORIZON-CL4-2026-05-DIGITAL-EMERGING-02
# Next-Generation AI Agents for Real-World Applications

## Proposal Draft

---

## 1. Project Identity

| Field | Value |
|-------|-------|
| **Acronym** | TRANSPARENT |
| **Full title** | Trustworthy, Reliable, and Accountable Next-generation Smart Platforms for AI Agent Real-world Evaluation, Navigation and Testing |
| **Call** | HORIZON-CL4-2026-05-DIGITAL-EMERGING-02 |
| **Type of action** | RIA (Research and Innovation Action) |
| **Duration** | 36 months |
| **Requested EU contribution** | EUR 18.5 million |
| **TRL** | Start: TRL 3 → End: TRL 5 |
| **Partnership** | AI, Data and Robotics (ADRA) |

---

## 2. Consortium

| # | Partner | Acronym | Country | Role | Expertise |
|---|---------|---------|---------|------|-----------|
| 1 | Universidad de Malaga | UMA | ES | **Coordinator** | TOMMI platform, transparent AI agents, EU AI Act compliance |
| 2 | Tampere University of Applied Sciences | TAMK | FI | Partner | Applied AI in education, UNINOVIS validation |
| 3 | The Hague University of Applied Sciences | THUAS | NL | Partner | Responsible AI research hub, policy interface |
| 4 | Technical University of Applied Sciences Wurzburg-Schweinfurt | THWS | DE | Partner | Robotics & AI, manufacturing applications |
| 5 | Universite Sorbonne Paris Nord | USPN | FR | Partner | NLP, multilingual AI agents |
| 6 | University of Campania "Luigi Vanvitelli" | UDCLV | IT | Partner | AI in healthcare, data science |
| 7 | [AI Research Institute — e.g., DFKI or INRIA] | TBD | DE/FR | Partner | Frontier AI agent architectures, multi-agent systems |
| 8 | [Industry partner — AI/LLM provider] | TBD | EU | Partner | LLM infrastructure, scalability, benchmarking |
| 9 | [Legal/ethics partner — e.g., Tilburg or Bologna University] | TBD | NL/IT | Partner | AI Act implementation, ethics, impact assessment |
| 10 | [SME — AI tooling] | TBD | EU | Partner | AI developer tools, commercialisation pathway |

**Note:** Partners 1-6 are the UNINOVIS core. Partners 7-10 to be identified to strengthen the proposal with frontier AI research, industry, and legal expertise.

---

## 3. Excellence

### 3.1 Objectives

The overarching objective of TRANSPARENT is to develop and validate a next-generation AI agent platform that embeds trustworthiness, transparency, and EU AI Act compliance as core architectural principles — not as afterthoughts.

**Specific objectives:**

**SO1 — Advanced AI agent architectures with built-in transparency**
Develop next-generation AI agent architectures that combine RAG (Retrieval-Augmented Generation), structured metadata reasoning, SQL tool use, and multi-agent coordination, with graduated transparency at every layer.

**SO2 — Reliability verification and hallucination detection**
Advance the state of the art in real-time verification of AI agent outputs, including claim-level source attribution, hallucination detection, and confidence scoring that users can interpret and trust.

**SO3 — Multi-agent coordination with accountability**
Design and implement multi-agent frameworks where agents can collaborate on complex tasks while maintaining individual audit trails, source attribution, and accountability chains.

**SO4 — EU AI Act compliance-by-design toolkit**
Create a reusable, open-source toolkit for AI agent developers to build EU AI Act-compliant systems, including automated audit logging, risk classification, transparency reporting, and human oversight mechanisms.

**SO5 — Real-world validation across sectors**
Validate the platform in three real-world application domains: (a) research intelligence and academic knowledge management, (b) public administration decision support, and (c) healthcare information retrieval — demonstrating cross-sector applicability.

### 3.2 Relation to the Call

The call asks for "autonomous systems powered by large AI models that can plan, utilize tools and perform actions autonomously to achieve specified goals." TRANSPARENT addresses every aspect:

| Call requirement | TRANSPARENT response |
|---|---|
| Planning and reasoning | Multi-step query decomposition: RAG retrieval → metadata enrichment → tool use → response synthesis → verification |
| Memory management | Session-based conversation history with context preservation, per-agent persistent knowledge bases |
| Tool use | SQL querying (Text2SQL), semantic search (ChromaDB/RAG), structured metadata lookup, interactive map generation, document retrieval |
| Multi-agent frameworks | Multiple agent types (RAG, Metadata+RAG, Text2SQL, Oneshot) operating on shared infrastructure with role-based access |
| Validation and monitoring | Real-time reliability badges, claim-level source attribution, hallucination detection, audit logging — **this is TRANSPARENT's unique contribution** |
| Benchmarking and KPIs | Structured error taxonomy, tester protocol, quantitative reliability metrics |

### 3.3 Novelty — Beyond the State of the Art

Current AI agent frameworks (LangChain, AutoGen, CrewAI) focus on **capability** — making agents do more. TRANSPARENT focuses on **accountability** — making agents you can trust and verify.

| Current state of the art | TRANSPARENT advance |
|---|---|
| Agents generate answers without source attribution | Every claim is traced to its source (metadata, document, LLM, web) with colour-coded provenance |
| Hallucination detection is post-hoc and external | Built-in, real-time hallucination detection with paper/project title verification against the knowledge base |
| Transparency is binary (on/off) | Graduated Transparency Framework: crystal box (full detail) → grey box (essential indicators) → black box (no indicators, audit-only) |
| EU AI Act compliance requires manual documentation | Automated compliance toolkit: audit logging, risk classification, Design Cards, RoPA templates |
| Agent evaluation is ad-hoc | Structured testing methodology with error taxonomy (content/transparency/technical), severity levels, and tester protocol |
| Multi-agent systems lack individual accountability | Per-agent audit trails, per-agent reliability scoring, role-based access control |

### 3.4 Methodology

**Phase 1 — Architecture Extension (M1-M12)**

- WP1: Extend TOMMI's agent architecture with advanced planning (multi-step decomposition, sub-goal generation)
- WP2: Implement persistent memory (cross-session knowledge, user preference learning)
- WP3: Develop multi-agent coordination protocol with accountability chains

**Phase 2 — Verification & Trust (M6-M24)**

- WP4: Advance claim-level verification to handle complex multi-source reasoning
- WP5: Develop cross-agent hallucination detection (when Agent A cites Agent B's output)
- WP6: Create the EU AI Act compliance-by-design toolkit

**Phase 3 — Validation & Deployment (M18-M36)**

- WP7: Validation in research intelligence (UNINOVIS, 8 universities, 8 countries)
- WP8: Validation in public administration (partnership with local/regional governments)
- WP9: Validation in healthcare information (partnership with clinical institutions)
- WP10: Benchmarking, KPIs, and comparison with existing frameworks

---

## 4. Impact

### 4.1 Expected Outcomes (aligned with call)

**Outcome 1: Significant improvements in autonomy, robustness and reliability of AI agents**
- TRANSPARENT delivers agents that are not only autonomous but **verifiably reliable** — every response carries a quantitative reliability score backed by claim-level evidence
- Robustness demonstrated through structured testing across 3 sectors, 8+ countries, with standardised error taxonomy

**Outcome 2: Innovative multi-agent frameworks demonstrating effective coordination**
- Multi-agent coordination where RAG agents, metadata agents, and SQL agents collaborate on complex queries
- Each agent maintains its own audit trail; the orchestrator tracks the full accountability chain
- Open protocol for inter-agent communication with provenance tracking

### 4.2 Impact Pathways

| Impact | Pathway | KPI |
|--------|---------|-----|
| **Trustworthy AI adoption** | Open-source platform + compliance toolkit lowers the barrier for organisations to deploy AI Act-compliant agents | 50+ organisations piloting TRANSPARENT by M36 |
| **European AI ecosystem** | Results shared via AI-on-Demand Platform; interoperability with ADRA ecosystem | 3 TEF validations |
| **Policy input** | Evidence-based feedback on AI Act implementation from real deployments across 3 sectors | 2 policy briefs to EC |
| **Academic impact** | Publications on transparency-by-design, hallucination detection, graduated transparency | 15+ publications in top venues |
| **SME enablement** | Compliance toolkit reduces cost of AI Act adherence for SMEs deploying AI agents | Toolkit adopted by 20+ SMEs |
| **Cross-sector validation** | Demonstrated in research, public admin, and healthcare — proving generalisability | 3 sector-specific deployment guides |

### 4.3 Dissemination & Exploitation

- **Open source**: TOMMI platform released under permissive license (Apache 2.0 or similar)
- **AI-on-Demand Platform**: Results published and tools integrated
- **Standards contribution**: Input to CEN-CENELEC AI standardisation (transparency, testing)
- **Training materials**: Testing methodology documentation (already developed for UNINOVIS) adapted for broader use
- **Industry workshops**: Annual workshops with AI developers and deployers

---

## 5. Implementation

### 5.1 Work Packages

| WP | Title | Lead | M | PM | Budget (EUR) |
|----|-------|------|---|----|-------------|
| WP1 | Advanced Agent Architectures | UMA | 1-12 | 48 | 2,200,000 |
| WP2 | Persistent Memory & Context | USPN | 1-12 | 36 | 1,600,000 |
| WP3 | Multi-Agent Coordination | TBD (AI Institute) | 6-24 | 42 | 1,900,000 |
| WP4 | Claim Verification & Source Attribution | UMA | 6-24 | 36 | 1,700,000 |
| WP5 | Hallucination Detection at Scale | THUAS | 6-24 | 30 | 1,400,000 |
| WP6 | EU AI Act Compliance Toolkit | TBD (Legal) | 12-30 | 24 | 1,100,000 |
| WP7 | Validation: Research Intelligence | TAMK + UNINOVIS | 18-36 | 36 | 1,600,000 |
| WP8 | Validation: Public Administration | UDCLV | 18-36 | 30 | 1,400,000 |
| WP9 | Validation: Healthcare Information | THWS | 18-36 | 30 | 1,400,000 |
| WP10 | Benchmarking, KPIs & Assessment | TBD (Industry) | 24-36 | 24 | 1,100,000 |
| WP11 | Dissemination, Exploitation & Mgmt | UMA | 1-36 | 36 | 1,600,000 |
|  | **TOTAL** | | | **372** | **17,000,000** |

*Remaining EUR 1.5M allocated to subcontracting, travel, equipment, and indirect costs.*

### 5.2 Key Milestones

| MS | Title | Month | Verification |
|----|-------|-------|-------------|
| MS1 | Architecture design complete | M6 | Design document reviewed by advisory board |
| MS2 | Multi-agent protocol specification | M12 | Protocol published, reference implementation |
| MS3 | Verification engine v2.0 | M18 | Benchmark results on hallucination detection |
| MS4 | AI Act compliance toolkit beta | M24 | Toolkit tested with 10 external developers |
| MS5 | Cross-sector validation complete | M30 | Validation reports for 3 sectors |
| MS6 | Final platform release | M36 | Open source release, AI-on-Demand integration |

### 5.3 Deliverables (key)

| D | Title | WP | Month | Type |
|---|-------|-----|-------|------|
| D1.1 | TRANSPARENT Architecture Specification | WP1 | M6 | Report |
| D3.1 | Multi-Agent Coordination Protocol | WP3 | M12 | Report + Software |
| D4.1 | Claim Verification Engine v2.0 | WP4 | M18 | Software |
| D5.1 | Hallucination Detection Benchmark | WP5 | M18 | Dataset + Report |
| D6.1 | EU AI Act Compliance Toolkit | WP6 | M24 | Software + Documentation |
| D7.1 | Research Intelligence Validation Report | WP7 | M30 | Report |
| D8.1 | Public Administration Validation Report | WP8 | M30 | Report |
| D9.1 | Healthcare Validation Report | WP9 | M30 | Report |
| D10.1 | Benchmarking & Comparative Assessment | WP10 | M33 | Report |
| D11.1 | TRANSPARENT Platform v1.0 (open source) | WP1 | M36 | Software |

---

## 6. What TOMMI Already Brings (TRL 3-4 baseline)

TRANSPARENT does not start from zero. TOMMI provides a validated baseline:

### Already implemented

- Multi-type agent framework (RAG, Metadata+RAG, Text2SQL, Oneshot)
- Graduated Transparency with 3 levels (crystal/grey/black box)
- Reliability badges with quantitative source breakdown (metadata %, documents %, LLM %, web %)
- Inline claim-level highlighting with colour-coded provenance
- Real-time hallucination detection (paper title verification, project title verification, ID cross-checking)
- Structured error taxonomy with 4 categories and 12 error types
- Tester protocol with 7-phase evaluation and downloadable Excel review files
- EU AI Act compliance: audit logging (JSONL), RoPA, Agent Design Cards, GDPR/AI Act transparency notices
- Role-based access control (superuser/tester/user) with data sovereignty enforcement
- Self-registration with UNINOVIS institutional email validation
- Deployed and tested across 8 universities in 8 European countries

### To be developed in TRANSPARENT

- Advanced planning with sub-goal decomposition
- Persistent cross-session memory
- Multi-agent coordination with accountability chains
- Cross-agent hallucination detection
- Automated AI Act compliance checking (not just logging)
- Scalable deployment infrastructure
- Validation in public administration and healthcare (beyond research)
- Formal benchmarking against LangChain, AutoGen, CrewAI

---

## 7. Alignment with EU Strategies

| Strategy | Alignment |
|----------|-----------|
| **Apply AI Strategy (COM(2025) 723)** | Direct implementation — AI agents for real-world sectors with trustworthiness |
| **EU AI Act (Reg. 2024/1689)** | Compliance-by-design toolkit; transparency obligations (Art. 50); AI literacy (Art. 4) |
| **European Strategy for Data** | Data sovereignty — user data never leaves institutional infrastructure |
| **Digital Europe Programme** | Interoperability with AI-on-Demand Platform, TEFs, EDIHs |
| **European Education Area** | Validated in 8 UNINOVIS universities; AI literacy for researchers |

---

## 8. Budget Summary

| Category | Amount (EUR) | % |
|----------|-------------|---|
| Personnel costs | 11,500,000 | 62% |
| Subcontracting | 1,500,000 | 8% |
| Travel & meetings | 800,000 | 4% |
| Equipment & infrastructure | 1,200,000 | 6% |
| Other direct costs | 500,000 | 3% |
| Indirect costs (25% flat rate) | 3,000,000 | 16% |
| **Total** | **18,500,000** | **100%** |

---

## 9. Ethical Considerations

- All AI agents are informational only — no autonomous decisions affecting individuals
- GDPR-compliant data processing documented in RoPA (already prepared)
- Data sovereignty: end-user data processed exclusively on institutional infrastructure
- Gender dimension addressed in team composition and user testing
- Accessibility considerations in UI design
- No dual-use concerns — platform is for knowledge retrieval, not autonomous action

---

## 10. Risk Management

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM providers change API/terms | Medium | High | Multi-provider architecture (Mistral, Ollama, vLLM); local deployment option |
| Hallucination detection insufficient for new domains | Medium | Medium | Domain-specific knowledge bases; tester feedback loop for continuous improvement |
| Partner dropout | Low | High | UNINOVIS MoU; each partner has clear, self-contained WP |
| AI Act interpretation changes | Medium | Medium | Legal partner monitors regulatory evolution; toolkit designed for flexibility |
| Scalability challenges | Medium | Medium | Cloud-neutral architecture; progressive scaling from single-server to distributed |
| Low adoption outside academia | Medium | Medium | Industry partner drives exploitation; SME toolkit simplifies deployment |

---

*Draft prepared: April 2026*
*Based on: Horizon Europe Work Programme 2026-2027, Cluster 4 — Digital, Industry and Space, pp. 130-133*
*Building on: TOMMI Transparent Agents Platform (UMA/UNINOVIS, 2024-2026)*
