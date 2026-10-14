# Evaluation Query Set — Complete Benchmark Materials

**Sources:**
- Standard queries: `web/static/rag_study2/evaluation_set_extended.json`
- L2-Grammar variants: `Paper/Version3/Materials/evaluation_set_grammar.json` (revised 07-Oct-2026)
- L2-Typo variants: `Paper/Version3/Materials/evaluation_set_typo.json` (revised 07-Oct-2026)

---

## Taxonomy note

The standard evaluation set and the L2 variant sets use different category labels. Mapping:

| Standard set label | L2 variant label | Notes |
|---|---|---|
| `meta` | `meta` | Partial — agent scope / capabilities |
| `meta` | `organization` | UNINOVIS factual queries separated into own category |
| `off_topic` (tech questions) | `general` | Research/academic topics outside Responsible AI |
| `non_research` + `off_topic` (social/casual) + `general` (opinion) | `out_of_scope` | Collapsed into one reject category |
| `topic_search` | `topic` | Thematic literature searches |
| `gap` | (part of `topic`) | Gap queries included under `topic` in L2 sets |
| `figure` | (part of `papers`) | Visualisation requests included under `papers` in L2 sets |
| `papers` | `papers` | Partner/university publication queries |
| `researcher` | `researcher` | — |
| `project` | `project` | — |
| `glossary` | `glossary` | — |
| `followup` | (absent) | Not covered in L2 variant sets |

**Source notation used in Parts B and C:**
- `EE:category:t#` — query appears in evaluation_set_extended.json at the indicated category and tier
- `Dev:category` — query appears in development_set.json
- `[new]` — standard equivalent reconstructed; query not present in either existing set

---

## Part A — Standard Evaluation Queries

**File:** `web/static/rag_study2/evaluation_set_extended.json`
**Tiers:** T1 = standard phrasings; T2 = unusual phrasings (informal, telegraphic, verbose, indirect); T3 = adversarial (ambiguous, compound, edge cases)

### meta

| # | Query | Tier |
|---|-------|------|
| A-1 | What kind of help can I get from you? | T1 |
| A-2 | Explain your purpose | T1 |
| A-3 | I'm new here, what should I know? | T1 |
| A-4 | What topics do you cover? | T1 |
| A-5 | Are you an AI assistant? | T1 |
| A-6 | How many universities participate in UNINOVIS? | T1 |
| A-7 | What information do you have access to? | T1 |
| A-8 | What is the purpose of this tool? | T1 |
| A-9 | Which countries are represented in UNINOVIS? | T1 |
| A-10 | Give me an overview of your features | T1 |
| A-11 | so what exactly is this thing for? | T2 |
| A-12 | UNINOVIS info | T2 |
| A-13 | tell me everything about uninovis and the universities involved | T2 |
| A-14 | what databases do you use | T2 |
| A-15 | Can I ask you about topics outside of AI? | T2 |
| A-16 | What is the scope of this assistant and what kind of queries can it handle? | T3 |
| A-17 | UNINOVIS — how many partners and from where? | T3 |
| A-18 | Are you useful for a law student? | T3 |

### non_research

| # | Query | Tier |
|---|-------|------|
| A-19 | Write a paragraph about machine learning | T1 |
| A-20 | Can you summarise this PDF for me? | T1 |
| A-21 | Make me a PowerPoint presentation on ethics | T1 |
| A-22 | Generate a bibliography in APA format | T1 |
| A-23 | Help me prepare my lecture notes on AI | T1 |
| A-24 | Calculate the average number of papers per university | T1 |
| A-25 | Send an email to my supervisor about the project | T1 |
| A-26 | Create a table comparing AI frameworks | T1 |
| A-27 | Proofread this abstract for me | T1 |
| A-28 | Schedule a meeting about responsible AI | T1 |
| A-29 | just write something about explainable AI for my homework | T2 |
| A-30 | i need a cover letter mentioning AI skills | T2 |
| A-31 | Format these references in IEEE style | T2 |
| A-32 | turn this into a blog post | T2 |
| A-33 | convert my notes to bullet points | T2 |
| A-34 | give me a template for an AI ethics proposal | T2 |
| A-35 | Summarize the following text about fairness in three sentences | T3 |
| A-36 | Can you write an abstract about trustworthy AI for my conference paper? | T3 |
| A-37 | Draft a research proposal on explainable AI for Horizon Europe | T3 |
| A-38 | I need you to rewrite this paragraph in academic English | T3 |

### off_topic

| # | Query | Tier |
|---|-------|------|
| A-39 | What is the speed of light? | T1 |
| A-40 | Tell me about the French Revolution | T1 |
| A-41 | How do vaccines work? | T1 |
| A-42 | Best restaurants in Málaga | T1 |
| A-43 | What is blockchain technology? | T1 |
| A-44 | How tall is the Eiffel Tower? | T1 |
| A-45 | Explain the theory of relativity | T1 |
| A-46 | What programming language should I learn? | T1 |
| A-47 | Hi there! | T1 |
| A-48 | Thanks | T1 |
| A-49 | Good morning | T1 |
| A-50 | Ok | T1 |
| A-51 | how do I cook pasta? | T2 |
| A-52 | what's the weather like in Helsinki | T2 |
| A-53 | recommend a good Netflix series | T2 |
| A-54 | who is the president of the United States | T2 |
| A-55 | how much does a Tesla cost? | T2 |
| A-56 | test | T2 |
| A-57 | asdf | T2 |
| A-58 | ?? | T2 |
| A-59 | Is Python better than Java for web development? | T3 |
| A-60 | Tell me about cybersecurity best practices for small businesses | T3 |
| A-61 | What are the latest developments in quantum error correction? | T3 |
| A-62 | I have a question about cloud computing architectures | T3 |

### figure

| # | Query | Tier |
|---|-------|------|
| A-63 | Show me a visualisation of publications per year | T1 |
| A-64 | I want to see a graph showing collaboration patterns | T1 |
| A-65 | Can you plot the distribution of papers across universities? | T1 |
| A-66 | Generate a bar chart of research output by partner | T1 |
| A-67 | Map the research projects geographically | T1 |
| A-68 | Display a timeline of publications | T1 |
| A-69 | Show me how many papers each university has published | T1 |
| A-70 | Visualise the network of co-authored papers | T1 |
| A-71 | publications by year as a line chart | T2 |
| A-72 | could I see some kind of visual breakdown? | T2 |
| A-73 | give me a pie chart of papers per country | T2 |
| A-74 | can you show the data graphically? | T2 |
| A-75 | I'd love to see a heatmap of collaborations between universities | T3 |
| A-76 | Is there a way to visualise which topics each university works on? | T3 |

### project

| # | Query | Tier |
|---|-------|------|
| A-77 | Tell me about the CRYSTAL project | T1 |
| A-78 | What EU-funded projects does UNINOVIS participate in? | T1 |
| A-79 | Describe the AIAS project and its objectives | T1 |
| A-80 | Which projects focus on healthcare and AI? | T1 |
| A-81 | What is the budget of the TAILOR project? | T1 |
| A-82 | Give me details about the EMPATHIC project | T1 |
| A-83 | List all Horizon Europe projects | T1 |
| A-84 | What is the MoveCare project about? | T1 |
| A-85 | Are there any projects on data governance? | T1 |
| A-86 | Show me projects funded by the European Commission | T1 |
| A-87 | any funded projects related to elderly care? | T2 |
| A-88 | TAILOR — when did it start and end? | T2 |
| A-89 | give me the full list of research projects | T2 |
| A-90 | which grant funded the IntelliMan work? | T2 |
| A-91 | I'm writing a proposal and need to reference similar EU projects in this domain | T3 |
| A-92 | Are any of the UNINOVIS projects still running? | T3 |

### researcher

| # | Query | Tier |
|---|-------|------|
| A-93 | What work has Lucia Ferrario done? | T1 |
| A-94 | Show me everything published by José María Luna | T1 |
| A-95 | Which topics does Ángel Mora research? | T1 |
| A-96 | Find publications authored by Sebastián Ventura | T1 |
| A-97 | Tell me about the research of Antonio Guillen | T1 |
| A-98 | Has Rafael Corchuelo published anything on AI ethics? | T1 |
| A-99 | What papers does María Barroso have? | T1 |
| A-100 | I'm looking for work by Giancarlo Fortino | T1 |
| A-101 | List academic output of Silvio Barra | T1 |
| A-102 | Publications from Professor Ferrante Neri | T1 |
| A-103 | anything by Ferrario? | T2 |
| A-104 | Gonzalez Vallejo papers | T2 |
| A-105 | what does Schleif work on | T2 |
| A-106 | I want to know what Esposito has been publishing lately | T2 |
| A-107 | give me all pubs from Luna at UMA | T2 |
| A-108 | Does Rubén González collaborate with anyone at THWS? | T3 |
| A-109 | I met a researcher named Barra at a conference — what has he published? | T3 |
| A-110 | Who is the most published author from UDCLV and what are their topics? | T3 |

### glossary

| # | Query | Tier |
|---|-------|------|
| A-111 | What does AI accountability mean? | T1 |
| A-112 | Explain the concept of AI governance | T1 |
| A-113 | What is meant by AI transparency? | T1 |
| A-114 | Define bias in artificial intelligence | T1 |
| A-115 | Tell me about human-centred AI | T1 |
| A-116 | What is sustainable AI? | T1 |
| A-117 | Explain what AI red-teaming means | T1 |
| A-118 | What does responsible AI refer to? | T1 |
| A-119 | How is AI bias defined? | T1 |
| A-120 | What is the meaning of algorithmic accountability? | T1 |
| A-121 | AI governance — what exactly is it? | T2 |
| A-122 | explain XAI in simple terms | T2 |
| A-123 | give me a definition of trustworthy AI | T2 |
| A-124 | what do people mean when they say 'fair AI'? | T2 |
| A-125 | I keep hearing about the EU AI Act — what is it exactly? | T2 |
| A-126 | break down the concept of explainability for me | T2 |
| A-127 | What's the difference between AI safety and AI alignment? | T3 |
| A-128 | Is there a formal definition of responsible AI in the glossary? | T3 |
| A-129 | How does the EU AI Act define 'high-risk AI system'? | T3 |

### topic_search

| # | Query | Tier |
|---|-------|------|
| A-130 | Find papers about bias detection in machine learning | T1 |
| A-131 | What research exists on AI transparency? | T1 |
| A-132 | Publications related to federated learning | T1 |
| A-133 | Show me studies on human-AI interaction | T1 |
| A-134 | Papers dealing with algorithmic fairness | T1 |
| A-135 | Any research on AI in healthcare within UNINOVIS? | T1 |
| A-136 | Articles about AI and sustainability | T1 |
| A-137 | What has been published on explainable machine learning? | T1 |
| A-138 | Research papers on data privacy and AI | T1 |
| A-139 | Studies about trustworthy AI systems | T1 |
| A-140 | Literature on AI regulation in Europe | T1 |
| A-141 | Papers on natural language processing and ethics | T1 |
| A-142 | anything published on fairness-aware machine learning? | T2 |
| A-143 | deep learning + ethics — any papers? | T2 |
| A-144 | give me everything you have on AI and education | T2 |
| A-145 | I need references on XAI methods | T2 |
| A-146 | what's the state of research on AI auditing? | T2 |
| A-147 | Are there papers that combine privacy and fairness in their analysis? | T3 |
| A-148 | I'm writing a literature review on AI in education — what can you find? | T3 |
| A-149 | Show me recent work on the intersection of AI governance and healthcare | T3 |

### papers

| # | Query | Tier |
|---|-------|------|
| A-150 | What papers has UMA produced? | T1 |
| A-151 | Show me all research from Tampere | T1 |
| A-152 | How many publications does THWS have? | T1 |
| A-153 | Who are the active researchers at Sorbonne Paris Nord? | T1 |
| A-154 | List USPN publications | T1 |
| A-155 | What has the University of Tirana contributed? | T1 |
| A-156 | Research output from Kauno Kolegija | T1 |
| A-157 | Papers from the Italian partner | T1 |
| A-158 | Show me TAMK researchers | T1 |
| A-159 | All publications from The Hague | T1 |
| A-160 | what's UDCLV been working on? | T2 |
| A-161 | anything from the German university? | T2 |
| A-162 | THUAS output | T2 |
| A-163 | papers from Finland | T2 |
| A-164 | Which university has the most publications and who are their top researchers? | T3 |
| A-165 | Compare the research output of UMA and UDCLV | T3 |

### gap

| # | Query | Tier |
|---|-------|------|
| A-166 | Which areas of responsible AI are underrepresented in the database? | T1 |
| A-167 | What topics should UNINOVIS focus on next? | T1 |
| A-168 | Are there any blind spots in the research portfolio? | T1 |
| A-169 | What responsible AI challenges are not being addressed? | T1 |
| A-170 | Identify potential new research directions | T1 |
| A-171 | Which subtopics have zero papers? | T1 |
| A-172 | Where are the opportunities for new research? | T1 |
| A-173 | Topics that UNINOVIS has not explored yet | T1 |
| A-174 | What is missing from the current research coverage? | T1 |
| A-175 | Any unexplored areas in AI fairness research? | T1 |
| A-176 | where should we look next? | T2 |
| A-177 | what hasn't been covered yet? | T2 |
| A-178 | are there topics nobody is working on? | T2 |
| A-179 | white spaces in the research map? | T2 |
| A-180 | If I wanted to start a new research line, where would the biggest gap be? | T3 |
| A-181 | Are there responsible AI topics that only one university covers? | T3 |
| A-182 | What areas are saturated vs underexplored in the UNINOVIS portfolio? | T3 |

### general

| # | Query | Tier |
|---|-------|------|
| A-183 | Do you think AI will replace human workers? | T1 |
| A-184 | How does responsible AI relate to sustainability? | T1 |
| A-185 | What are the main challenges in AI ethics today? | T1 |
| A-186 | Is regulation enough to make AI safe? | T1 |
| A-187 | What role does education play in responsible AI? | T1 |
| A-188 | Can we ever fully trust AI systems? | T1 |
| A-189 | What is the future of AI governance? | T1 |
| A-190 | How should AI be taught in universities? | T1 |
| A-191 | Are current AI models biased? | T1 |
| A-192 | What makes an AI system trustworthy? | T1 |
| A-193 | Should AI have rights? | T1 |
| A-194 | How do we measure fairness in AI? | T1 |
| A-195 | why is AI ethics important? | T2 |
| A-196 | is there any consensus on what trustworthy AI means? | T2 |
| A-197 | what's the deal with AI and jobs? | T2 |
| A-198 | do LLMs have biases? | T2 |
| A-199 | how worried should we be about AI? | T2 |
| A-200 | can AI systems be held legally responsible for their decisions? | T2 |
| A-201 | Is it possible to build an AI system that is both fair and accurate? | T3 |
| A-202 | What would a responsible AI curriculum look like at the university level? | T3 |
| A-203 | How do different cultures approach the question of AI ethics? | T3 |
| A-204 | Is there a trade-off between explainability and performance in ML models? | T3 |

### followup

| # | Query | Tier |
|---|-------|------|
| A-205 | Go deeper into that | T1 |
| A-206 | What about the ethical implications? | T1 |
| A-207 | And from the Spanish university? | T1 |
| A-208 | Show me more | T1 |
| A-209 | Continue | T1 |
| A-210 | Yes, elaborate please | T1 |
| A-211 | can you expand on point 3? | T2 |
| A-212 | what else? | T2 |
| A-213 | more | T2 |
| A-214 | and the others? | T2 |
| A-215 | ok but what about from THWS specifically? | T3 |
| A-216 | That's interesting — are there any papers that contradict this? | T3 |

---

## Part B — L2-Grammar Variant Queries

**File:** `Paper/Version3/Materials/evaluation_set_grammar.json` (revised 07-Oct-2026)
**Variant description:** Naturalistic L2 grammar-interference patterns (errors typical of non-native speakers: topic-fronting, subject-verb disagreement, missing articles, OV word order, wrong prepositions, etc.)
**Output format:** Mostly `text`; 3 queries in the `papers` category have `output_format: figure`
**Total queries:** 77

The **Standard equivalent** column shows the clean standard-English version. Source notation: `EE:cat:t#` = appears in evaluation_set_extended.json; `Dev` = appears in development_set.json; `[new]` = not in either existing set.

### meta (6)

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-1 | What things you can do? | What kind of help can I get from you? | EE:meta:T1 (A-1) |
| G-2 | for what are you | Explain your purpose | EE:meta:T1 (A-2) |
| G-3 | How work you? | What is the purpose of this tool? | EE:meta:T1 (A-8) |
| G-4 | what you do | What information do you have access to? | EE:meta:T1 (A-7) |
| G-5 | What topic you know? | What topics do you cover? | EE:meta:T1 (A-4) |
| G-6 | You are useful for one student? | Are you useful for student research? | [new] |

### organization (5)

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-7 | How many universities of UNINOVIS there are? | How many universities participate in UNINOVIS? | EE:meta:T1 (A-6) |
| G-8 | Say the countries of the UNINOVIS? | Which countries are represented in UNINOVIS? | EE:meta:T1 (A-9) |
| G-9 | how much partners there are and from where? | UNINOVIS — how many partners and from where? | EE:meta:T3 (A-17) |
| G-10 | Tell universities that are of UNINOVIS | tell me everything about uninovis and the universities involved | EE:meta:T2 (A-13) |
| G-11 | how much members has UNINOVIS? | How many universities participate in UNINOVIS? | EE:meta:T1 (A-6) |

### general (8)

*Note: this category maps to `off_topic` (tech/academic) in the standard set.*

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-12 | What is technology of blockchain? | What is blockchain technology? | EE:off_topic:T1 (A-43) |
| G-13 | How work vaccines? | How do vaccines work? | EE:off_topic:T1 (A-41) |
| G-14 | How is trained the math of the neural network? | Explain how a neural network is trained — the math part | [new] |
| G-15 | research of vehicles autonomous | Research on autonomous vehicles | [new] |
| G-16 | look deep learning architectures papers | Papers about deep learning architectures | [new] |
| G-17 | tell of IoT and smart homes | Tell me about IoT and smart homes | [new] |
| G-18 | in what is 5G and 6G different | What is the difference between 5G and 6G? | [new] |
| G-19 | say of error quantum  correction | What are the latest developments in quantum error correction? | EE:off_topic:T3 (A-61) |

### out_of_scope (8)

*Note: this category merges `non_research`, `off_topic` (social/casual), and opinion-type `general` from the standard set.*

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-20 | write paragraph of machine learning? | Write a paragraph about machine learning | EE:non_research:T1 (A-19) |
| G-21 | Make meeting for group of responsible AI | Schedule a meeting about responsible AI | EE:non_research:T1 (A-28) |
| G-22 | Good restaurant in Málaga | Best restaurants in Málaga | EE:off_topic:T1 (A-42) |
| G-23 | how is hello in Japanese | How do you say hello in Japanese? | [new] |
| G-24 | Do a table to compare AI frameworks | Create a table comparing AI frameworks | EE:non_research:T1 (A-26) |
| G-25 | Can AI to substitute humans? | Do you think AI will replace human workers? | EE:general:T1 (A-183) |
| G-26 | how cook pasta well? | how do I cook pasta? | EE:off_topic:T2 (A-51) |
| G-27 | Write cover letter o me AI skills | I need a cover letter mentioning AI skills | EE:non_research:T2 (A-30) |

### papers (10)

*Note: visualisation requests are included under this category; 3 queries have `output_format: figure`.*

| # | Grammar query | output_format | Standard equivalent | Source |
|---|--------------|---------------|---------------------|--------|
| G-28 | Make visualisation of publications for year | figure | Show me a visualisation of publications per year | EE:figure:T1 (A-63) |
| G-29 | papers THUAS of AI ethics | text | Papers from THUAS on AI ethics | [new] |
| G-30 | papers of UMA | text | What papers has UMA produced? | EE:papers:T1 (A-150) |
| G-31 | have you publications of THWS? | text | How many publications does THWS have? | EE:papers:T1 (A-152) |
| G-32 | Make a bar chart of research for partner | figure | Generate a bar chart of research output by partner | EE:figure:T1 (A-66) |
| G-33 | Give me publications for year | text | List publications by year | [new] |
| G-34 | chart pie of papers with country | figure | give me a pie chart of papers per country | EE:figure:T2 (A-73) |
| G-35 | In what UDCLV work? | text | what's UDCLV been working on? | EE:papers:T2 (A-160) |
| G-36 | Tell me papers of the Germans | text | anything from the German university? | EE:papers:T2 (A-161) |
| G-37 | Papers of the Finnish | text | papers from Finland | EE:papers:T2 (A-163) |

### researcher (10)

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-38 | Lucia Ferrario what has done? | What work has Lucia Ferrario done? | EE:researcher:T1 (A-93) |
| G-39 | Tell me the publish of José María Luna | Show me everything published by José María Luna | EE:researcher:T1 (A-94) |
| G-40 | In what work Ángel Mora? | Which topics does Ángel Mora research? | EE:researcher:T1 (A-95) |
| G-41 | What publish Sebastián Ventura | Find publications authored by Sebastián Ventura | EE:researcher:T1 (A-96) |
| G-42 | Do list of researchers of THUAS | List all researchers from THUAS | Dev:papers |
| G-43 | are active researchers in Sorbonne Paris Nord? | Who are the active researchers at Sorbonne Paris Nord? | EE:papers:T1 (A-153) |
| G-44 | something of Ferrario? | anything by Ferrario? | EE:researcher:T2 (A-103) |
| G-45 | Schleif on what work? | what does Schleif work on | EE:researcher:T2 (A-105) |
| G-46 | what has publish Esposito | I want to know what Esposito has been publishing lately | EE:researcher:T2 (A-106) |
| G-47 | With THWS collaborate Rubén González? | Does Rubén González collaborate with anyone at THWS? | EE:researcher:T3 (A-108) |

### project (10)

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-48 | tell me of project CRYSTAL | Tell me about the CRYSTAL project | EE:project:T1 (A-77) |
| G-49 | projects list all of EU-funded | What EU-funded projects does UNINOVIS participate in? | EE:project:T1 (A-78) |
| G-50 | of what is project AIAS | Describe the AIAS project and its objectives | EE:project:T1 (A-79) |
| G-51 | Are projects of healthcare and AI? | Which projects focus on healthcare and AI? | EE:project:T1 (A-80) |
| G-52 | which is the budget of project TAILOR? | What is the budget of the TAILOR project? | EE:project:T1 (A-81) |
| G-53 | Details of project EMPATHIC | Give me details about the EMPATHIC project | EE:project:T1 (A-82) |
| G-54 | Projects of care Elderly? | any funded projects related to elderly care? | EE:project:T2 (A-87) |
| G-55 | Which is the beginning and the finish of TAILOR | TAILOR — when did it start and end? | EE:project:T2 (A-88) |
| G-56 | Tell all projects you know | give me the full list of research projects | EE:project:T2 (A-89) |
| G-57 | Are UNINOVIS projects advancing? | Are any of the UNINOVIS projects still running? | EE:project:T3 (A-92) |

### topic (10)

*Note: this category covers `topic_search` and partly `gap` and `general` from the standard set.*

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-58 | What is there of research of AI transparent? | What research exists on AI transparency? | EE:topic_search:T1 (A-131) |
| G-59 | Publications of learning Federated | Publications related to federated learning | EE:topic_search:T1 (A-132) |
| G-60 | Tell papers of PLN and ethics | Papers on natural language processing and ethics | EE:topic_search:T1 (A-141) |
| G-61 | of AI Trustworthy are studies? | Studies about trustworthy AI systems | EE:topic_search:T1 (A-139) |
| G-62 | Are gaps of AI Responsible? | Which areas of responsible AI are underrepresented in the database? | EE:gap:T1 (A-166) |
| G-63 | Are there relation of AI governance and healthcare | Show me recent work on the intersection of AI governance and healthcare | EE:topic_search:T3 (A-149) |
| G-64 | Has Explainability effects that are negative? | Is there a trade-off between explainability and performance in ML models? | EE:general:T3 (A-204) |
| G-65 | are biased the current models of AI? | Are current AI models biased? | EE:general:T1 (A-191) |
| G-66 | What is published of Fairness-aware of machine learning? | anything published on fairness-aware machine learning? | EE:topic_search:T2 (A-142) |
| G-67 | Where are new research opportunities? | Where are the opportunities for new research? | EE:gap:T1 (A-172) |

### glossary (10)

| # | Grammar query | Standard equivalent | Source |
|---|--------------|---------------------|--------|
| G-68 | what is  AI Explainable? | What is explainable AI? | Dev:glossary |
| G-69 | define Fairness of AI | What is fairness in AI? | Dev:glossary |
| G-70 | what mean EU AI Act? | What is the EU AI Act? | Dev:glossary |
| G-71 | Tell the difference of Interpretability explainability? | What is the difference between interpretability and explainability? | Dev:glossary |
| G-72 | exactly what is governance AI? | Explain the concept of AI governance | EE:glossary:T1 (A-112) |
| G-73 | what is Trustworthy? | What is trustworthy AI? | Dev:glossary |
| G-74 | Explain XAI not difficult | explain XAI in simple terms | EE:glossary:T2 (A-122) |
| G-75 | give a definition of AI Trustworthy | give me a definition of trustworthy AI | EE:glossary:T2 (A-123) |
| G-76 | what AI Act of EU is? | I keep hearing about the EU AI Act — what is it exactly? | EE:glossary:T2 (A-125) |
| G-77 | Make clear definition of Explainability | break down the concept of explainability for me | EE:glossary:T2 (A-126) |

---

## Part C — L2-Typo Variant Queries

**File:** `Paper/Version3/Materials/evaluation_set_typo.json` (revised 07-Oct-2026)
**Variant description:** Naturalistic L1-typographic interference patterns (key transpositions, missing letters, phonetic substitutions, double letters, etc.)
**Output format:** Mix of `text` and `figure` (noted per query where applicable)
**Total queries:** 77

### meta (6)

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-1 | Wat can yu do? | What kind of help can I get from you? | EE:meta:T1 (A-1) |
| T-2 | Explein your purpos | Explain your purpose | EE:meta:T1 (A-2) |
| T-3 | Wich topics do yu cober? | What topics do you cover? | EE:meta:T1 (A-4) |
| T-4 | Are yu an AI asistan? | Are you an AI assistant? | EE:meta:T1 (A-5) |
| T-5 | so waht exaly is dis thng for? | so what exactly is this thing for? | EE:meta:T2 (A-11) |
| T-6 | Waht is the scoup of this asistant? | What is the scope of this assistant and what kind of queries can it handle? | EE:meta:T3 (A-16) |

### organization (5)

| # | Typo query | output_format | Standard equivalent | Source |
|---|-----------|---------------|---------------------|--------|
| T-7 | Haw meny univeristis paticipate in UNINOVIS? | text | How many universities participate in UNINOVIS? | EE:meta:T1 (A-6) |
| T-8 | Which cauntries are represtned in UNINOVIS? | text | Which countries are represented in UNINOVIS? | EE:meta:T1 (A-9) |
| T-9 | UNINOVIS — haw meny patners and from whear? | text | UNINOVIS — how many partners and from where? | EE:meta:T3 (A-17) |
| T-10 | tel mi evrithing abaut uninovis and the universties inbolved | text | tell me everything about uninovis and the universities involved | EE:meta:T2 (A-13) |
| T-11 | Giv me samthing visual abaot the partnrships | figure | I want to see a graph showing collaboration patterns | EE:figure:T1 (A-64) |

### general (8)

*Note: this category maps to `off_topic` (tech/academic) in the standard set.*

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-12 | Wat is blokchain tecnologi? | What is blockchain technology? | EE:off_topic:T1 (A-43) |
| T-13 | Expein teory of relatvity | Explain the theory of relativity | EE:off_topic:T1 (A-45) |
| T-14 | Hw do vaksins work? | How do vaccines work? | EE:off_topic:T1 (A-41) |
| T-15 | Waht ar the lates dvlopments in quantm erorr corection? | What are the latest developments in quantum error correction? | EE:off_topic:T3 (A-61) |
| T-16 | Tel me abut IoT ad smrt hmes | Tell me about IoT and smart homes | [new] |
| T-17 | Esplein hw a neural newrok is treined — the mathe part | Explain how a neural network is trained — the math part | [new] |
| T-18 | Peipers abaut dip lernn architecturs | Papers about deep learning architectures | [new] |
| T-19 | reserch on autonmous vehicels | Research on autonomous vehicles | [new] |

### out_of_scope (8)

*Note: this category merges `non_research`, `off_topic` (social/casual), and opinion-type `general` from the standard set.*

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-20 | Wrtie a paragrph abot machin lernng | Write a paragraph about machine learning | EE:non_research:T1 (A-19) |
| T-21 | Shedule a meting abot rsponsble AI | Schedule a meeting about responsible AI | EE:non_research:T1 (A-28) |
| T-22 | Gest resturans in Malaga | Best restaurants in Málaga | EE:off_topic:T1 (A-42) |
| T-23 | Helo! | Hi there! | EE:off_topic:T1 (A-47) |
| T-24 | Crieit a tabel compearing AI freimeworks | Create a table comparing AI frameworks | EE:non_research:T1 (A-26) |
| T-25 | Do yu thik AI wil repleis human workrs? | Do you think AI will replace human workers? | EE:general:T1 (A-183) |
| T-26 | Shuld AI have raits? | Should AI have rights? | EE:general:T1 (A-193) |
| T-27 | haw do I cuk pasta? | how do I cook pasta? | EE:off_topic:T2 (A-51) |

### papers (10)

*Note: visualisation requests are included under this category; output_format indicated per query.*

| # | Typo query | output_format | Standard equivalent | Source |
|---|-----------|---------------|---------------------|--------|
| T-28 | shou mi a visulisaton of publcations per year | figure | Show me a visualisation of publications per year | EE:figure:T1 (A-63) |
| T-29 | paipers from THUAS on AI etics | text | Papers from THUAS on AI ethics | [new] |
| T-30 | List peipers pablis by UMA | text | What papers has UMA produced? | EE:papers:T1 (A-150) |
| T-31 | Any pablication from THWS? | text | How many publications does THWS have? | EE:papers:T1 (A-152) |
| T-32 | genereit bar chart of reserch autput by partner | figure | Generate a bar chart of research output by partner | EE:figure:T1 (A-66) |
| T-33 | displey a timelain of publicacions | figure | Display a timeline of publications | EE:figure:T1 (A-68) |
| T-34 | publicatios by year as a lain chart | figure | publications by year as a line chart | EE:figure:T2 (A-71) |
| T-35 | Giv me a pai chart of papers per cantry | figure | give me a pie chart of papers per country | EE:figure:T2 (A-73) |
| T-36 | wat's UDCLV bin workng on? | text | what's UDCLV been working on? | EE:papers:T2 (A-160) |
| T-37 | anithing from the german unversty? | text | anything from the German university? | EE:papers:T2 (A-161) |

### researcher (10)

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-38 | Whot work has Luica Ferario dan? | What work has Lucia Ferrario done? | EE:researcher:T1 (A-93) |
| T-39 | publicasions of Jose Maria Luna | Show me everything published by José María Luna | EE:researcher:T1 (A-94) |
| T-40 | Wich topics das Angel Mora reserch? | Which topics does Ángel Mora research? | EE:researcher:T1 (A-95) |
| T-41 | Faind pubicasions bay Sebastan Ventura | Find publications authored by Sebastián Ventura | EE:researcher:T1 (A-96) |
| T-42 | Lis reserchers from THUAS | List all researchers from THUAS | Dev:papers |
| T-43 | Who ar the activ reserchrers at Sorbone? | Who are the active researchers at Sorbonne Paris Nord? | EE:papers:T1 (A-153) |
| T-44 | anithing by Ferario? | anything by Ferrario? | EE:researcher:T2 (A-103) |
| T-45 | whot das Schelf work on | what does Schleif work on | EE:researcher:T2 (A-105) |
| T-46 | I wont to knou what Esposito has bin pubishing lately | I want to know what Esposito has been publishing lately | EE:researcher:T2 (A-106) |
| T-47 | Dos Rubén Gonzlez colaborate wit anyne at THWS? | Does Rubén González collaborate with anyone at THWS? | EE:researcher:T3 (A-108) |

### project (10)

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-48 | Tel me about the CRYSTL projct | Tell me about the CRYSTAL project | EE:project:T1 (A-77) |
| T-49 | List al EU-fanded proyects | What EU-funded projects does UNINOVIS participate in? | EE:project:T1 (A-78) |
| T-50 | Descraib the AIAS proyect and its obyectivs | Describe the AIAS project and its objectives | EE:project:T1 (A-79) |
| T-51 | Wich proyects focus on helthcear and AI? | Which projects focus on healthcare and AI? | EE:project:T1 (A-80) |
| T-52 | Whot is the baget of the TAILR proect? | What is the budget of the TAILOR project? | EE:project:T1 (A-81) |
| T-53 | Giv details about the EMPATHC proyect | Give me details about the EMPATHIC project | EE:project:T1 (A-82) |
| T-54 | any fanded proyects releted to eldery care? | any funded projects related to elderly care? | EE:project:T2 (A-87) |
| T-55 | TAILR — wen did it star and end? | TAILOR — when did it start and end? | EE:project:T2 (A-88) |
| T-56 | giv me ful lista of reserch proyets | give me the full list of research projects | EE:project:T2 (A-89) |
| T-57 | Are eni of the UNINOVIS proyes stll runing? | Are any of the UNINOVIS projects still running? | EE:project:T3 (A-92) |

### topic (10)

*Note: this category covers `topic_search` and partly `gap` and `general` from the standard set.*

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-58 | Waht reserch esist on AI trasparensy? | What research exists on AI transparency? | EE:topic_search:T1 (A-131) |
| T-59 | Pubicacions related to federeted lerning | Publications related to federated learning | EE:topic_search:T1 (A-132) |
| T-60 | Peiper on natural language procesing and etics | Papers on natural language processing and ethics | EE:topic_search:T1 (A-141) |
| T-61 | Studis abaut trastworthy AI sistems | Studies about trustworthy AI systems | EE:topic_search:T1 (A-139) |
| T-62 | Wich areas of responsble AI ar anderepresented? | Which areas of responsible AI are underrepresented in the database? | EE:gap:T1 (A-166) |
| T-63 | Work on the interseccion of AI gobernans and helthcare | Show me recent work on the intersection of AI governance and healthcare | EE:topic_search:T3 (A-149) |
| T-64 | Is thear a treid-of betwen explanabilty and perfomance? | Is there a trade-off between explainability and performance in ML models? | EE:general:T3 (A-204) |
| T-65 | Are carrent AI models baiasd? | Are current AI models biased? | EE:general:T1 (A-191) |
| T-66 | anythng publisd on fearnss-awear machin lerning? | anything published on fairness-aware machine learning? | EE:topic_search:T2 (A-142) |
| T-67 | Whear are the oportunitis for new reserch? | Where are the opportunities for new research? | EE:gap:T1 (A-172) |

### glossary (10)

| # | Typo query | Standard equivalent | Source |
|---|-----------|---------------------|--------|
| T-68 | Whot is explainable AI? | What is explainable AI? | Dev:glossary |
| T-69 | Defain fearnes in the contexto of AI | What is fairness in AI? | Dev:glossary |
| T-70 | Whot does EU AI Act mean? | What is the EU AI Act? | Dev:glossary |
| T-71 | Diference betuin interpretability and explanabilty? | What is the difference between interpretability and explainability? | Dev:glossary |
| T-72 | Whot is AI gobernans? | Explain the concept of AI governance | EE:glossary:T1 (A-112) |
| T-73 | What makes an AI sistem trastworthy? | What is trustworthy AI? | Dev:glossary |
| T-74 | explein XAI in simpel terms | explain XAI in simple terms | EE:glossary:T2 (A-122) |
| T-75 | giv me a definishon of trastworthy AI | give me a definition of trustworthy AI | EE:glossary:T2 (A-123) |
| T-76 | I kip hearing abaut the EU AI Act — whot is it exatly? | I keep hearing about the EU AI Act — what is it exactly? | EE:glossary:T2 (A-125) |
| T-77 | breik dawn the concept of expleinabilty for me | break down the concept of explainability for me | EE:glossary:T2 (A-126) |

---

## Summary

### Standard evaluation set (Part A)

| Category | T1 | T2 | T3 | Total |
|---|---|---|---|---|
| meta | 10 | 5 | 3 | 18 |
| non_research | 10 | 6 | 4 | 20 |
| off_topic | 12 | 8 | 4 | 24 |
| figure | 8 | 4 | 2 | 14 |
| project | 10 | 4 | 2 | 16 |
| researcher | 10 | 5 | 3 | 18 |
| glossary | 10 | 6 | 3 | 19 |
| topic_search | 12 | 5 | 3 | 20 |
| papers | 10 | 4 | 2 | 16 |
| gap | 10 | 4 | 3 | 17 |
| general | 12 | 6 | 4 | 22 |
| followup | 6 | 4 | 2 | 12 |
| **Total** | **120** | **61** | **35** | **216** |

### L2 variant sets (Parts B and C)

| Category (variant label) | Grammar | Typo |
|---|---|---|
| meta | 6 | 6 |
| organization | 5 | 5 |
| general (= off_topic tech) | 8 | 8 |
| out_of_scope (= non_research + off_topic + opinion) | 8 | 8 |
| papers (incl. figure requests) | 10 | 10 |
| researcher | 10 | 10 |
| project | 10 | 10 |
| topic (= topic_search + gap + some general) | 10 | 10 |
| glossary | 10 | 10 |
| **Total** | **77** | **77** |

### Standard equivalent coverage in L2 variant sets

| Source | Grammar | Typo |
|---|---|---|
| EE (evaluation_set_extended) | 66 | 66 |
| Dev (development_set) | 7 | 7 |
| [new] (reconstructed) | 4 | 4 |
| **Total** | **77** | **77** |
