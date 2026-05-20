# UNINOVIS Intranet — Concept Note

**Document type:** Concept Note / Discussion Paper
**Version:** 1.0 — May 2026
**Status:** Draft for internal discussion
**Prepared by:** UNINOVIS-UMA Technical Team 

---

## 1. Introduction

### 1.1 Background

The working plan for the UNINOVIS Digital Platform, proposed by UMA and approved by the alliance, is based on three key components:

- **Agora** — the central platform providing the key internal services for the alliance;
- **MetaCampus** — a combination of the eight existing Learning Management Systems (LMSs) at each partner university;
- **Web** — a public-facing information service for external communication and visibility.

Based on the analysis of the project proposal, 14 digital services were initially identified as part of this platform, most of which were to be provided, to which Authentication was subsequently added as a 15th service.

### 1.2 Current situation

Since the approval of Agora approximately eight months ago, two important developments have emerged:

1. **The approval and implementation of Authentication is being delayed** due to its intrinsic complexity. This delay may potentially impact important functionalities that require authenticated access — for example, tools to find collaboration partners or to propose joint research projects.

2. **Several new functionalities have been identified** that will possibly require independent implementation outside Agora. A notable example is the AI Agents service, recently approved within WP3. This means that a number digital tools might require independent development (outside Agora).

### 1.3 UMA's approach

In order to avoid that this situation causes a major impact on the UNINOVIS workplan, UMA has begun working on a practical solution that guarantees the alliance reaches its goals. Specifically, we have created:

1. **A web-based platform with authentication** — using a straightforward approach that is valid for the relatively small number of users (one to two hundred) involved in UNINOVIS management and coordination. This platform is currently hosted on a dedicated server at UMA (gloria.uma.es).

2. **A varied set of pilot applications** that serve two main goals:
   - They serve to **evaluate the needs** of specific functionalities — providing working prototypes that make discussion concrete rather than abstract, and enabling partners to assess whether a given tool meets their requirements before committing to definitive implementation.
   - They serve to **collect data** (e.g., the UNINOVIS staff directory, the event calendar) that can later be exported to other formats and integrated into AGORA or to any other platform the alliance might ultimately adopt.

The pilot applications described herein are **working prototypes** — they illustrate needed capabilities but are not intended as definitive implementations. Their purpose is to facilitate informed decision-making and to ensure that progress continues while Agora's authentication and other components are being finalised.

### 1.4 About this document

The present document describes the platform used — particularly the login system and the role-based access control — and the different tools developed to date. Each tool is presented with its current features and a set of discussion points for partner feedback.

**Feedback is most welcome on any of these tools.** Partners are invited to test the pilot at the provided URL and to share their comments, suggestions, and institutional constraints.

---

## 2. The Pilot Platform

### 2.1 Overview

The pilot platform is a web-based intranet hosted on a dedicated server at UMA (gloria.uma.es). It provides a centralised, authenticated entry point to a set of tools and services designed for the UNINOVIS community. The platform comprises three layers:

1. **Authentication and user management** — a login system with role-based access control, supporting multiple user types and dual roles.
2. **A personalised dashboard** — a single landing page that, after login, displays only the tools and sections relevant to the user's role(s).
3. **A set of integrated applications** — each accessible from the dashboard, sharing a common navigation bar and visual identity.

### 2.2 User Roles

The platform recognises four user profiles, each with differentiated access to tools:

| User Profile | Description | Primary Needs |
|---|---|---|
| **Students** | Students participating in UNINOVIS mobility, joint programmes, or BIPs | Virtual campus, academic records, enrolment |
| **Administrative Staff** | International relations officers, project managers, financial administrators | Directory, event tracking, mobility planning |
| **Teaching & Research Staff** | Academics, researchers, WP leaders | Grade conversion, researcher networking, AI agents |
| **System Administrators** | Technical staff, superusers | User management, system configuration |

Users may hold multiple roles simultaneously (e.g., a researcher who is also a WP coordinator has both teaching and administrative access). The system takes the union of all permissions granted by the user's roles.

### 2.3 Role-Based Dashboard

After authentication, the landing page displays tool cards organised in sections. Each section is only visible to users with the appropriate role(s):

| Section | Students | Admin Staff | Teaching/Research | Testers | Superusers |
|---|---|---|---|---|---|
| Campus | x | | | x | x |
| Administration | | x | x | x | x |
| Teaching & Research | | | x | x | x |
| AI Agents | | | x | x | x |
| System Administration | | | | | x |

### 2.4 Authentication System

The pilot uses a token-based session system with the following characteristics:

- **Role-based access control** with support for dual roles
- **Secure password storage** using PBKDF2-HMAC-SHA256 hashing
- **Session tokens** with server-side validation
- **Encrypted personal data** (Fernet symmetric encryption for personal events and user-specific files)
- **Integration-ready** for future SSO/SAML with institutional identity providers

This approach is deliberately simple and well-suited to the current scale (one to two hundred users). It can be replaced or augmented with institutional SSO once Agora's authentication becomes available.

### 2.5 Navigation

A persistent navigation bar appears at the top of every page, providing:

- **Breadcrumb-based location** (e.g., UNINOVIS / Administration / Event Tracker) so users always know where they are
- **One-click return** to the intranet dashboard from any application
- **User identity display** showing the authenticated user's name

All applications share a consistent visual design with the UNINOVIS colour scheme.

### 2.6 Self-Service Profile

All authenticated users can edit their own profile data in the Directory (name, telephone, notes) directly from the intranet landing page via the "Edit my profile" link, without requiring editor permissions.

---

## 3. Pilot Applications

The following sections describe each pilot application currently available on the platform.

### 3.1 UNINOVIS Directory

**Need addressed:** A shared, searchable directory of UNINOVIS staff involved in managerial tasks across all eight partner universities, organised by work packages, governance bodies, and task groups.

**Pilot features:**
- Staff profiles with contact information, roles, and notes
- Organisation by groups (WP1–WP5, Technical Body, Management Board, Executive Board, etc.) and subgroups (tasks, committees)
- Subgroup assignment independent of parent groups
- University-based filtering and sorting
- Group/subgroup membership management with bulk operations
- Email list copying for group communication
- Self-service profile editing for all authenticated users
- Custom fields configurable by administrators
- Notes field for additional context

**Discussion points:**
- What additional fields are needed (e.g., ORCID, departmental affiliation, languages)?
- Should there be a public-facing version for external visibility?

### 3.2 UNINOVIS Event Tracker

**Need addressed:** A shared calendar for tracking all alliance activities — work package meetings, BIPs, hackathons, governance sessions, and public events — with filtering, personal events, and integration with external calendar applications.

**Pilot features:**
- Multiple views: year, month, week, day, and sortable list view
- Category-based organisation:
  - **Internal:** WP1–WP5, Board of Presidents, Executive Council
  - **External:** BIPs, Hackathons, Other public events
- Grouping filters: "All Internal" and "All External"
- University-based filtering
- Event types: Virtual (with meeting URL) and Physical (with venue)
- Timezone annotation (CET/CEST and others)
- Recurring events with flexible rules (weekly, biweekly, monthly nth weekday)
- Series management (edit/delete all occurrences)
- Participant management linked to the Directory (by group or individual selection)
- Email list copying for all participants
- **Personal events** — private events stored in encrypted per-user files, visible only to the creator
- **iCalendar subscription** — subscribe from Apple Calendar, Google Calendar, or Outlook for automatic synchronisation
- Export (JSON, TSV) and import with filtering by date, university, and category
- Organising university field for each event

**Discussion points:**
- Should the Event Tracker integrate with the Agora Events Calendar for public events?
- What is the preferred approach for event approval workflows?
- Should there be automated reminders or notifications?
- How should the Event Tracker relate to institutional academic calendars?

### 3.3 UNIGRACON (Grade Converter)

**Need addressed:** A tool for converting grades between the different grading systems used by UNINOVIS partner universities, essential for student mobility and joint programme administration.

**Pilot features:**
- Conversion between all partner university grading systems
- Support for formula-based and table-based conversion methods
- Editor mode for authorised staff to update conversion rules
- User mode for general consultation

**Discussion points:**
- What governance process should approve changes to conversion rules?
- Should students have direct access to this tool?

### 3.4 Mobility Planner

**Need addressed:** A tool for computing call opening dates for mobility activities, accounting for administrative processing periods and holiday calendars across partner institutions.

**Pilot features:**
- Calculation of call opening dates based on configurable administrative periods
- Holiday calendar management per institution
- Support for different mobility activity types
- Pending: the vacation periods should be shared with UNINOVIS Event tracker (see 3.2)

**Discussion points:**
- Should the Mobility Planner integrate with institutional mobility management systems?
- What additional parameters are needed (e.g., visa processing times, insurance deadlines)?
- Should it generate reports for Erasmus+ compliance?

### 3.5 TOMMI AI Agents

**Need addressed:** AI-powered assistants that provide on-demand support for research, project management, and administrative tasks, drawing on alliance-specific knowledge and documents.

**Pilot features:**
- Up to eight specialised AI agents configurable for different domains
- Support for multiple LLM providers (cloud and local)
- Transparency controls (black box, grey box, crystal box) in accordance with the EU AI Act
- Agent configuration and testing interface
- Conversation logging for accountability
- Agent creation interface for authorised developers

**Discussion points:**
- Should AI agents be available to students, and if so, with what safeguards?

### 3.6 Services Catalogue

**Need addressed:** A comprehensive, discoverable catalogue of all digital services available to the UNINOVIS community, reducing the "where do I find this?" problem.

**Pilot features:**
- Categorised listing of all UNINOVIS digital services
- Links to administrative tools, AI agents, the Agora platform, and external services

**Discussion points:**
- What services from individual institutions should be linked?
- Should the catalogue include service status and availability information?

---


## 4. Technical Considerations

### 4.1 Current Pilot Stack
- **Backend:** Python / FastAPI
- **Frontend:** Vanilla HTML/CSS/JavaScript (no framework dependency)
- **Data storage:** JSON files (pilot), with path to database migration
- **Authentication:** Token-based sessions with PBKDF2 password hashing
- **Encryption:** Fernet symmetric encryption for personal data
- **Calendar standard:** iCalendar (RFC 5545) for subscription and export

### 4.2 Production Considerations
The pilot prioritises rapid iteration and discussion. A production deployment would additionally require:
- Migration to a proper database (PostgreSQL or similar)
- SSO/SAML integration with institutional identity providers
- HTTPS with proper certificate management
- Backup and disaster recovery procedures
- GDPR compliance review and Data Protection Impact Assessment
- Accessibility audit (WCAG 2.1 AA)
- Scalability assessment for the full alliance user base
- Hosting infrastructure decision (cloud vs. institutional hosting)

Note: UMA is currently in the process of acquiring a dedicated server with capacity to host the different services of the Digital Platform (excluding the Web). 

---

## 5. Governance and Next Steps

### 5.1 Decision Points for Partners (Technical Body/WP4/WP1)

This concept note and its pilot implementation are presented to facilitate discussion on the following key questions:

1. **Scope:** Which functionalities are essential? Which can wait?
2. **Build vs. integrate:** For each functionality, should UNINOVIS build a custom solution, adopt an existing tool, or integrate with institutional systems?
3. **Data governance:** What data can be shared across the alliance? What stays institutional?
4. **Relationship with Agora:** Should the applications be moved to Agora platform?
5. **Sustainability:** How will the applications be maintained beyond the project funding period?
6. **User management:** Duplication of user accounts (Agora/Gloria) should be avoided (Pending)


### 5.2 Feedback

Partners are invited to:
- **Test the pilot** at the provided URL
- **Comment on each functionality:** Is it needed? Is the approach right? What's missing?
- **Identify additional needs** not covered in this document
- **Share institutional constraints** that affect feasibility (technical, policy, or organisational)

---

*This document is intended for internal UNINOVIS discussion. The pilot applications are working prototypes developed to support informed decision-making. They represent one possible approach to meeting validated needs and are explicitly open to modification, replacement, or integration with alternative solutions based on partner feedback.*
