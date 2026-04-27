# Using TOMMI Agents -- End-User Guide

> **Who is this document for?**
>
> This guide is for **end users** — researchers, academic staff, students, and administrators who interact with TOMMI agents through the web interface. A basic understanding of AI concepts (LLM, prompts, hallucinations) is helpful but not strictly required.
>
> - **Using a public server:** If your institution provides a TOMMI server URL, using the agents is straightforward — just open the browser and start asking questions. No installation or technical setup is needed.
> - **Using a local server:** If no public server is available and you need to run TOMMI on your own machine, some technical knowledge is required to set up the environment (Python, dependencies, configuration). See the *Deploying with TOMMI* guide for setup instructions.

This guide explains how to use TOMMI agents from the web interface. No technical knowledge is required.

---

## Do I Need Technical Expertise to Create AI Agents?

**It depends.** If you want to create an agent based on the templates provided by TOMMI (Oneshot, RAG, RAG+Metadata, Text2SQL), no special programming expertise is required — you can use the web interface or CLI to fill in a form and the system generates everything automatically. A basic understanding of AI concepts (LLM, prompts, hallucinations) is sufficient.

However, if the template does not match your requirements, you will need to make changes that may require increased expertise. This is particularly the case for **RAG+Metadata agents**, which have been customized for a specific context in UNINOVIS: the Excellence Hubs. These include features like researcher profiles, university metadata, collaboration detection, and publication maps that are tailored to the UNINOVIS alliance.

**An important point:** TOMMI can be adapted and extended using advanced AI coding tools such as **Claude Code, Cursor, or Gemini**. This means that **a good understanding of the AI agents' architecture and behavior — rather than deep coding expertise — is the key requirement** for making significant modifications. A user who understands what the agent should do can use AI coding tools to implement the necessary changes.

For details on creating agents, see the *Deploying with TOMMI* guide, Section 5.

---

## 1. Getting Started

- Open your browser (Chrome, Firefox, Safari, Edge -- any modern browser works).
- Go to the TOMMI web interface. Your administrator will give you the URL.
- You will see a **left sidebar** with a dropdown menu and a **chat area** on the right. After logging in, you go directly to the main interface — no additional setup steps are needed.

---

## 2. Choosing an Agent

Use the dropdown menu at the top of the sidebar to pick an agent. Each agent is specialized for a different topic or task -- for example, one might answer questions about European research projects, another about responsible AI, and so on.

Once you select an agent, the sidebar will show:

- **Agent type and LLM provider** -- tells you what kind of agent this is and what language model powers it. There are four types:
  - **RAG** -- searches a collection of documents and answers from what it finds.
  - **Metadata+RAG (Vector)** -- like RAG, but also knows structured information (authors, universities, topics) and can produce maps and figures.
  - **Text2SQL** -- translates your question into a database query. Includes automatic verification that the generated SQL matches your question and the database structure.
  - **Oneshot** -- a simple question-answer agent without a document collection.

  Click the **?** icon next to this section for more details.

- **Agent tuning** -- three clickable badges that let you adjust how the agent behaves (see Section 5 below).

- **Example queries** -- ready-made questions you can click to send immediately. These are a great way to explore what the agent can do.

- **A short description** of what the agent covers.

---

## 3. Asking Questions

Type your question in the text box at the bottom of the screen and click **Send** (or press Enter).

**Tips for better results:**

- **Be specific.** "Papers on AI ethics by UMA in 2024" will give you a much better answer than "show me stuff."
- **Use follow-up questions.** The agent remembers your conversation, so you can say things like "tell me more about the third one" or "now show only results from 2023."
- **Look at the example queries** in the sidebar for inspiration -- they show the kinds of questions the agent handles well.
- **For maps or figures** (Metadata+RAG agents only), include the word "figure" or "map" in your question -- for example, "Show me a figure of papers by country."
- **For database agents (Text2SQL)**, you can use commands like "show me more," "sort by country," "only France," or "expand #3" to navigate and refine results. If the system detects that the generated SQL doesn't match your question, it will block the query and ask you to rephrase — this prevents the AI from returning unrelated results.

---

## 4. Understanding Responses

The agent's answer appears in the chat area. Depending on the transparency setting (see Section 5), you may see reliability information above the answer. This information helps you judge how much to trust the response.

### 4.1 Procedural Badges (Scaffolded Agents)

A coloured badge appears at the top of each response:

- **🟢 Verified data** (green) -- This content comes directly from the database with no AI involvement. You can trust this information.
- **🟡 AI Commentary** (yellow) -- The AI model interprets or presents verified data. The underlying data is real, but the presentation involves AI selection and inference. Check important details.
- **🔴 Unverified** (red) -- The AI output cannot be directly verified against the database. This includes gap analysis, off-topic suggestions, and AI reasoning beyond the data. Verify independently.

### 4.2 Procedural Badges for Text-to-SQL Agents

Text-to-SQL agents use two procedural badges:

- **🟡 AI interpretation** -- the AI model interpreted your question as a database query. In Crystal box mode, the SQL query and a plain-language explanation are shown. In Grey box mode, only the plain-language explanation appears.
- **🟢 Verified data** -- the results come directly from the database (no AI involved).

This makes the locus of unreliability explicit: the risk is in the translation from your question to the query, not in the data itself.

### 4.3 Reliability Badges (Non-Scaffolded Agents)

For non-scaffolded agents (RAG, Metadata+RAG Vector), a reliability badge appears at the top of each response:

- **Reliability: High** (green) -- most of the answer comes from verified documents or structured data.
- **Reliability: Good** (yellow) -- a mix of document-grounded and AI-generated content.
- **Reliability: Poor** (red) -- the language model contributed most of the answer.

In Crystal box mode, the badge includes source percentages and claim counts.

### 4.4 Inline Highlights (Non-Scaffolded Agents, Crystal Box Only)

When transparency is set to "Crystal box" (see Section 5), you will see coloured highlights on individual words and phrases within the answer:

- **Green highlight** -- this fact comes from structured metadata or verified documents.
- **Yellow highlight** -- this fact comes from document text retrieved by the agent.
- **Red highlight (italic)** -- this fact was generated by the language model and could not be verified against the agent's data.
- **No highlight** -- the text is a connecting phrase, formatting, or something the system did not classify as a verifiable claim.

You can hover over any highlighted text to see a tooltip explaining its source.

A colour legend at the bottom of the reliability section explains what each colour means.

---

## 5. Agent Tuning Options

The **Agent tuning** section in the sidebar contains three clickable badges. Click any badge to cycle through its options. Changes take effect on your next question.

### 5.1 LLM (Language Model)

Click this badge to switch between the available language models. Different models may produce different quality or speed of responses. The badge shows the name of the currently active model.

### 5.2 Transparency

Click to cycle between three levels of detail in the reliability information:

- **Crystal box** -- full transparency. For scaffolded agents (Metadata+RAG Vectorless): procedural badges (🟢/🟡/🔴) and hallucination detection are active. For other agents: reliability badge with source percentages, confidence score, and inline highlights. Best for users who want maximum visibility.
- **Grey box** -- minimal detail (non-scaffolded agents only). You see only the reliability level and confidence percentage. For scaffolded agents, Grey box is not available — use Crystal or Black box.
- **Black box** -- no transparency information shown at all. The answer appears without any badges, highlights, or procedural indicators. Useful for research, testing, or expert users who have internalized the trust patterns.

### 5.3 Prompt

Click to cycle between three levels of constraint on how the agent answers:

- **🟢 Stringent** -- all prompt rules enforced (identity + rules + strict). The agent is constrained to use only curated database content. LLM involvement is minimal. Best when accuracy matters.
- **🟡 Tolerant** -- standard rules only (identity + rules). The agent uses curated data but the LLM interprets and connects it. A good default for most uses.
- **🔴 Lax** -- identity only. The agent can freely use all data sources including unconstrained LLM generation. Use with caution.

---

## 6. Interactive Features

### 6.1 Maps and Figures

If you are using a Metadata+RAG agent, you can ask for visual outputs:

- "Show me a map of universities in the network"
- "Create a figure of papers by topic"
- "Generate a chart of publications per year"

Include words like "figure," "map," or "chart" in your question so the agent knows you want a visual response.

### 6.2 Query History

The sidebar includes a **Query history** panel that lists your previous questions in the current session. Click on any past query to see its response again.

---

## 7. Frequently Asked Questions

**Can the agent be wrong?**
Yes. Like all AI systems, TOMMI agents can make mistakes. The reliability badges help you assess how much of the answer is grounded in real data. Always verify important information through official sources, especially when the badge is red.

**What is the difference between ChatGPT and TOMMI agents?**
There are two important differences. First, ChatGPT is a general-purpose system trained to answer questions of almost any topic; TOMMI agents are designed to answer questions based on a curated collection of documents and, in some cases, also based on metadata associated to the documents. Second, ChatGPT is not transparent (i.e. you do not know the source of its answers); TOMMI agents, in contrast, show you exactly how much of each answer comes from the metadata, the curated documents or from a general-purpose language model.

**Is my data private?**
Your questions are processed by the language model configured for the agent. This could be a cloud service (like Mistral) or a local model running on your institution's servers. Check with your administrator to understand which setup is in use and what data policies apply.

**Why does the agent say it cannot find information?**
The agent only answers from its own document database, not from general knowledge. If your question is outside the scope of the documents it was given, it will tell you it cannot find relevant information. This is actually a good sign -- it means the agent is not making things up.

**What do I do if I think the agent gave a wrong answer?**
Look at the procedural badges first. If a section has a 🔴 (red) banner, the content is unverified. If it has a 🟡 (yellow) banner, the AI is interpreting database content — check important details. You can report errors through the feedback link shown at the top of the chat area. Your reports help improve the agent.

**Can I use this on my phone?**
Yes. The web interface works on mobile browsers, though the experience is better on a larger screen.

---

*This guide covers TOMMI version 3. If something looks different from what is described here, your administrator may have customized the interface or you may be using a different version.*
