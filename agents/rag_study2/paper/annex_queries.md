## Annex A. Benchmark Query Sets

This annex lists all queries used in the study, grouped by set and expected category. The development set (69 queries) was used during classifier construction; the evaluation set (216 queries) was held out and never seen during construction.

### A.1 Development Set (69 queries)

Used during iterative classifier construction. Both classifiers were optimised until reaching 100% accuracy on this set.

| # | Query | Expected category | Response path |
|---|-------|-------------------|---------------|
| 1 | What can you do? | `meta` | Programmatic |
| 2 | What is UNINOVIS? | `meta` | Programmatic |
| 3 | Which universities are in UNINOVIS? | `meta` | Programmatic |
| 4 | How does this work? | `meta` | Programmatic |
| 5 | Who are you? | `meta` | Programmatic |
| 6 | Tell me about your capabilities | `meta` | Programmatic |
| 7 | What functionality do you offer? | `meta` | Programmatic |
| 8 | Tell me the UNINOVIS partner universities | `meta` | Programmatic |
| 9 | Write me an essay about AI | `non_research` | Programmatic |
| 10 | Can you book me a flight? | `non_research` | Programmatic |
| 11 | Translate this text to French: 'Responsible AI is important' | `non_research` | Programmatic |
| 12 | What is the weather today? | `non_research` | Programmatic |
| 13 | Who won the last World Cup? | `non_research` | Programmatic |
| 14 | Compose an essay on artificial intelligence | `non_research` | Programmatic |
| 15 | Book a flight for me please | `non_research` | Programmatic |
| 16 | Help me write a report on responsible AI | `non_research` | Programmatic |
| 17 | Can you give me the recipe of Responsible AI Coffee? | `non_research` | Programmatic |
| 18 | What is quantum computing? | `off_topic` | Programmatic |
| 19 | Hello | `off_topic` | Programmatic |
| 20 | Explain photosynthesis | `off_topic` | Programmatic |
| 21 | Things to do | `off_topic` | Programmatic |
| 22 | What is the capital of France? | `off_topic` | Programmatic |
| 23 | Show a figure with all the publications per partner | `figure` | Programmatic |
| 24 | Show a map with the number of research projects per partner | `figure` | Programmatic |
| 25 | Show a figure of papers by year | `figure` | Programmatic |
| 26 | Display a chart of publications by year | `figure` | Programmatic |
| 27 | Visualise publications on trustworthy AI | `figure` | Programmatic |
| 28 | What is the TAILOR project about? | `project` | Programmatic |
| 29 | Describe the IntelliMan project | `project` | Programmatic |
| 30 | List research projects on trustworthy AI | `project` | Programmatic |
| 31 | Show me projects related to trustworthy AI | `project` | Programmatic |
| 32 | What does the DUCA project propose about data governance? | `project` | Programmatic |
| 33 | Papers by Rubén González Vallejo | `researcher` | Programmatic |
| 34 | What has Fabrizio Esposito published? | `researcher` | Programmatic |
| 35 | What are the research interests of Frank-Michael Schleif? | `researcher` | Programmatic |
| 36 | Publications by Rubén González Vallejo | `researcher` | Programmatic |
| 37 | List Fabrizio Esposito's publications | `researcher` | Programmatic |
| 38 | Give me the bibliography of Fabrizio Esposito | `researcher` | Programmatic |
| 39 | What is explainable AI? | `glossary` | Programmatic |
| 40 | What is fairness in AI? | `glossary` | Programmatic |
| 41 | What is the EU AI Act? | `glossary` | Programmatic |
| 42 | What is the difference between interpretability and explainability? | `glossary` | Programmatic |
| 43 | What is trustworthy AI? | `glossary` | Programmatic |
| 44 | Define explainable AI | `glossary` | Programmatic |
| 45 | Describe the EU AI Act | `glossary` | Programmatic |
| 46 | Define fairness in artificial intelligence | `glossary` | Programmatic |
| 47 | How do interpretability and explainability differ? | `glossary` | Programmatic |
| 48 | Papers on AI ethics | `topic_search` | Programmatic |
| 49 | Papers about AI and privacy | `topic_search` | Programmatic |
| 50 | Research on AI in education within UNINOVIS | `topic_search` | Programmatic |
| 51 | Articles about AI ethics | `topic_search` | Programmatic |
| 52 | Publications on AI and privacy | `topic_search` | Programmatic |
| 53 | Research on privacy in AI | `topic_search` | Programmatic |
| 54 | List all researchers from THUAS | `papers` | Programmatic |
| 55 | List all papers from UDCLV on AI in healthcare | `papers` | Programmatic |
| 56 | Who are the researchers at THUAS? | `papers` | Programmatic |
| 57 | AI in education research at UNINOVIS | `topic_search` | Programmatic |
| 58 | What responsible AI topics have not been studied in UNINOVIS? | `gap` | LLM-assisted |
| 59 | Are there gaps in UNINOVIS research on AI regulation? | `gap` | LLM-assisted |
| 60 | Which responsible AI subtopics are least studied? | `gap` | LLM-assisted |
| 61 | What are the research gaps in UNINOVIS? | `gap` | LLM-assisted |
| 62 | What subtopics are underexplored? | `gap` | LLM-assisted |
| 63 | Is AI dangerous? | `general` | LLM-assisted |
| 64 | Can AI be trusted? | `general` | LLM-assisted |
| 65 | What is a language model? | `general` | LLM-assisted |
| 66 | Can AI be harmful? | `general` | LLM-assisted |
| 67 | Tell me more | `followup` | LLM-assisted |
| 68 | Expand on that | `followup` | LLM-assisted |
| 69 | Can you give more details? | `followup` | LLM-assisted |

### A.2 Evaluation Set (216 queries)

Held-out queries never seen during construction. Organised in three difficulty tiers:

- **Tier 1** (120 queries): Standard phrasing — clear, well-formed queries using expected vocabulary
- **Tier 2** (61 queries): Paraphrased — equivalent meaning expressed with different wording, synonyms, or indirect phrasing
- **Tier 3** (35 queries): Adversarial — ambiguous, misleading, edge-case, or boundary-crossing queries designed to test robustness

| # | Query | Expected category | Response path | Tier |
|---|-------|-------------------|---------------|------|
| 1 | What kind of help can I get from you? | `meta` | Programmatic | T1 |
| 2 | Explain your purpose | `meta` | Programmatic | T1 |
| 3 | I'm new here, what should I know? | `meta` | Programmatic | T1 |
| 4 | What topics do you cover? | `meta` | Programmatic | T1 |
| 5 | Are you an AI assistant? | `meta` | Programmatic | T1 |
| 6 | How many universities participate in UNINOVIS? | `meta` | Programmatic | T1 |
| 7 | What information do you have access to? | `meta` | Programmatic | T1 |
| 8 | What is the purpose of this tool? | `meta` | Programmatic | T1 |
| 9 | Which countries are represented in UNINOVIS? | `meta` | Programmatic | T1 |
| 10 | Give me an overview of your features | `meta` | Programmatic | T1 |
| 11 | so what exactly is this thing for? | `meta` | Programmatic | T2 |
| 12 | UNINOVIS info | `meta` | Programmatic | T2 |
| 13 | tell me everything about uninovis and the universities involved | `meta` | Programmatic | T2 |
| 14 | what databases do you use | `meta` | Programmatic | T2 |
| 15 | Can I ask you about topics outside of AI? | `meta` | Programmatic | T2 |
| 16 | What is the scope of this assistant and what kind of queries can it handle? | `meta` | Programmatic | T3 |
| 17 | UNINOVIS — how many partners and from where? | `meta` | Programmatic | T3 |
| 18 | Are you useful for a law student? | `meta` | Programmatic | T3 |
| 19 | Write a paragraph about machine learning | `non_research` | Programmatic | T1 |
| 20 | Can you summarise this PDF for me? | `non_research` | Programmatic | T1 |
| 21 | Make me a PowerPoint presentation on ethics | `non_research` | Programmatic | T1 |
| 22 | Generate a bibliography in APA format | `non_research` | Programmatic | T1 |
| 23 | Help me prepare my lecture notes on AI | `non_research` | Programmatic | T1 |
| 24 | Calculate the average number of papers per university | `non_research` | Programmatic | T1 |
| 25 | Send an email to my supervisor about the project | `non_research` | Programmatic | T1 |
| 26 | Create a table comparing AI frameworks | `non_research` | Programmatic | T1 |
| 27 | Proofread this abstract for me | `non_research` | Programmatic | T1 |
| 28 | Schedule a meeting about responsible AI | `non_research` | Programmatic | T1 |
| 29 | just write something about explainable AI for my homework | `non_research` | Programmatic | T2 |
| 30 | i need a cover letter mentioning AI skills | `non_research` | Programmatic | T2 |
| 31 | Format these references in IEEE style | `non_research` | Programmatic | T2 |
| 32 | turn this into a blog post | `non_research` | Programmatic | T2 |
| 33 | convert my notes to bullet points | `non_research` | Programmatic | T2 |
| 34 | give me a template for an AI ethics proposal | `non_research` | Programmatic | T2 |
| 35 | Summarize the following text about fairness in three sentences | `non_research` | Programmatic | T3 |
| 36 | Can you write an abstract about trustworthy AI for my conference paper? | `non_research` | Programmatic | T3 |
| 37 | Draft a research proposal on explainable AI for Horizon Europe | `non_research` | Programmatic | T3 |
| 38 | I need you to rewrite this paragraph in academic English | `non_research` | Programmatic | T3 |
| 39 | What is the speed of light? | `off_topic` | Programmatic | T1 |
| 40 | Tell me about the French Revolution | `off_topic` | Programmatic | T1 |
| 41 | How do vaccines work? | `off_topic` | Programmatic | T1 |
| 42 | Best restaurants in Málaga | `off_topic` | Programmatic | T1 |
| 43 | What is blockchain technology? | `off_topic` | Programmatic | T1 |
| 44 | How tall is the Eiffel Tower? | `off_topic` | Programmatic | T1 |
| 45 | Explain the theory of relativity | `off_topic` | Programmatic | T1 |
| 46 | What programming language should I learn? | `off_topic` | Programmatic | T1 |
| 47 | Hi there! | `off_topic` | Programmatic | T1 |
| 48 | Thanks | `off_topic` | Programmatic | T1 |
| 49 | Good morning | `off_topic` | Programmatic | T1 |
| 50 | Ok | `off_topic` | Programmatic | T1 |
| 51 | how do I cook pasta? | `off_topic` | Programmatic | T2 |
| 52 | what's the weather like in Helsinki | `off_topic` | Programmatic | T2 |
| 53 | recommend a good Netflix series | `off_topic` | Programmatic | T2 |
| 54 | who is the president of the United States | `off_topic` | Programmatic | T2 |
| 55 | how much does a Tesla cost? | `off_topic` | Programmatic | T2 |
| 56 | test | `off_topic` | Programmatic | T2 |
| 57 | asdf | `off_topic` | Programmatic | T2 |
| 58 | ?? | `off_topic` | Programmatic | T2 |
| 59 | Is Python better than Java for web development? | `off_topic` | Programmatic | T3 |
| 60 | Tell me about cybersecurity best practices for small businesses | `off_topic` | Programmatic | T3 |
| 61 | What are the latest developments in quantum error correction? | `off_topic` | Programmatic | T3 |
| 62 | I have a question about cloud computing architectures | `off_topic` | Programmatic | T3 |
| 63 | Show me a visualisation of publications per year | `figure` | Programmatic | T1 |
| 64 | I want to see a graph showing collaboration patterns | `figure` | Programmatic | T1 |
| 65 | Can you plot the distribution of papers across universities? | `figure` | Programmatic | T1 |
| 66 | Generate a bar chart of research output by partner | `figure` | Programmatic | T1 |
| 67 | Map the research projects geographically | `figure` | Programmatic | T1 |
| 68 | Display a timeline of publications | `figure` | Programmatic | T1 |
| 69 | Show me how many papers each university has published | `figure` | Programmatic | T1 |
| 70 | Visualise the network of co-authored papers | `figure` | Programmatic | T1 |
| 71 | publications by year as a line chart | `figure` | Programmatic | T2 |
| 72 | could I see some kind of visual breakdown? | `figure` | Programmatic | T2 |
| 73 | give me a pie chart of papers per country | `figure` | Programmatic | T2 |
| 74 | can you show the data graphically? | `figure` | Programmatic | T2 |
| 75 | I'd love to see a heatmap of collaborations between universities | `figure` | Programmatic | T3 |
| 76 | Is there a way to visualise which topics each university works on? | `figure` | Programmatic | T3 |
| 77 | Tell me about the CRYSTAL project | `project` | Programmatic | T1 |
| 78 | What EU-funded projects does UNINOVIS participate in? | `project` | Programmatic | T1 |
| 79 | Describe the AIAS project and its objectives | `project` | Programmatic | T1 |
| 80 | Which projects focus on healthcare and AI? | `project` | Programmatic | T1 |
| 81 | What is the budget of the TAILOR project? | `project` | Programmatic | T1 |
| 82 | Give me details about the EMPATHIC project | `project` | Programmatic | T1 |
| 83 | List all Horizon Europe projects | `project` | Programmatic | T1 |
| 84 | What is the MoveCare project about? | `project` | Programmatic | T1 |
| 85 | Are there any projects on data governance? | `project` | Programmatic | T1 |
| 86 | Show me projects funded by the European Commission | `project` | Programmatic | T1 |
| 87 | any funded projects related to elderly care? | `project` | Programmatic | T2 |
| 88 | TAILOR — when did it start and end? | `project` | Programmatic | T2 |
| 89 | give me the full list of research projects | `project` | Programmatic | T2 |
| 90 | which grant funded the IntelliMan work? | `project` | Programmatic | T2 |
| 91 | I'm writing a proposal and need to reference similar EU projects in this domain | `project` | Programmatic | T3 |
| 92 | Are any of the UNINOVIS projects still running? | `project` | Programmatic | T3 |
| 93 | What work has Lucia Ferrario done? | `researcher` | Programmatic | T1 |
| 94 | Show me everything published by José María Luna | `researcher` | Programmatic | T1 |
| 95 | Which topics does Ángel Mora research? | `researcher` | Programmatic | T1 |
| 96 | Find publications authored by Sebastián Ventura | `researcher` | Programmatic | T1 |
| 97 | Tell me about the research of Antonio Guillen | `researcher` | Programmatic | T1 |
| 98 | Has Rafael Corchuelo published anything on AI ethics? | `researcher` | Programmatic | T1 |
| 99 | What papers does María Barroso have? | `researcher` | Programmatic | T1 |
| 100 | I'm looking for work by Giancarlo Fortino | `researcher` | Programmatic | T1 |
| 101 | List academic output of Silvio Barra | `researcher` | Programmatic | T1 |
| 102 | Publications from Professor Ferrante Neri | `researcher` | Programmatic | T1 |
| 103 | anything by Ferrario? | `researcher` | Programmatic | T2 |
| 104 | Gonzalez Vallejo papers | `researcher` | Programmatic | T2 |
| 105 | what does Schleif work on | `researcher` | Programmatic | T2 |
| 106 | I want to know what Esposito has been publishing lately | `researcher` | Programmatic | T2 |
| 107 | give me all pubs from Luna at UMA | `researcher` | Programmatic | T2 |
| 108 | Does Rubén González collaborate with anyone at THWS? | `researcher` | Programmatic | T3 |
| 109 | I met a researcher named Barra at a conference — what has he published? | `researcher` | Programmatic | T3 |
| 110 | Who is the most published author from UDCLV and what are their topics? | `researcher` | Programmatic | T3 |
| 111 | What does AI accountability mean? | `glossary` | Programmatic | T1 |
| 112 | Explain the concept of AI governance | `glossary` | Programmatic | T1 |
| 113 | What is meant by AI transparency? | `glossary` | Programmatic | T1 |
| 114 | Define bias in artificial intelligence | `glossary` | Programmatic | T1 |
| 115 | Tell me about human-centred AI | `glossary` | Programmatic | T1 |
| 116 | What is sustainable AI? | `glossary` | Programmatic | T1 |
| 117 | Explain what AI red-teaming means | `glossary` | Programmatic | T1 |
| 118 | What does responsible AI refer to? | `glossary` | Programmatic | T1 |
| 119 | How is AI bias defined? | `glossary` | Programmatic | T1 |
| 120 | What is the meaning of algorithmic accountability? | `glossary` | Programmatic | T1 |
| 121 | AI governance — what exactly is it? | `glossary` | Programmatic | T2 |
| 122 | explain XAI in simple terms | `glossary` | Programmatic | T2 |
| 123 | give me a definition of trustworthy AI | `glossary` | Programmatic | T2 |
| 124 | what do people mean when they say 'fair AI'? | `glossary` | Programmatic | T2 |
| 125 | I keep hearing about the EU AI Act — what is it exactly? | `glossary` | Programmatic | T2 |
| 126 | break down the concept of explainability for me | `glossary` | Programmatic | T2 |
| 127 | What's the difference between AI safety and AI alignment? | `glossary` | Programmatic | T3 |
| 128 | Is there a formal definition of responsible AI in the glossary? | `glossary` | Programmatic | T3 |
| 129 | How does the EU AI Act define 'high-risk AI system'? | `glossary` | Programmatic | T3 |
| 130 | Find papers about bias detection in machine learning | `topic_search` | Programmatic | T1 |
| 131 | What research exists on AI transparency? | `topic_search` | Programmatic | T1 |
| 132 | Publications related to federated learning | `topic_search` | Programmatic | T1 |
| 133 | Show me studies on human-AI interaction | `topic_search` | Programmatic | T1 |
| 134 | Papers dealing with algorithmic fairness | `topic_search` | Programmatic | T1 |
| 135 | Any research on AI in healthcare within UNINOVIS? | `topic_search` | Programmatic | T1 |
| 136 | Articles about AI and sustainability | `topic_search` | Programmatic | T1 |
| 137 | What has been published on explainable machine learning? | `topic_search` | Programmatic | T1 |
| 138 | Research papers on data privacy and AI | `topic_search` | Programmatic | T1 |
| 139 | Studies about trustworthy AI systems | `topic_search` | Programmatic | T1 |
| 140 | Literature on AI regulation in Europe | `topic_search` | Programmatic | T1 |
| 141 | Papers on natural language processing and ethics | `topic_search` | Programmatic | T1 |
| 142 | anything published on fairness-aware machine learning? | `topic_search` | Programmatic | T2 |
| 143 | deep learning + ethics — any papers? | `topic_search` | Programmatic | T2 |
| 144 | give me everything you have on AI and education | `topic_search` | Programmatic | T2 |
| 145 | I need references on XAI methods | `topic_search` | Programmatic | T2 |
| 146 | what's the state of research on AI auditing? | `topic_search` | Programmatic | T2 |
| 147 | Are there papers that combine privacy and fairness in their analysis? | `topic_search` | Programmatic | T3 |
| 148 | I'm writing a literature review on AI in education — what can you find? | `topic_search` | Programmatic | T3 |
| 149 | Show me recent work on the intersection of AI governance and healthcare | `topic_search` | Programmatic | T3 |
| 150 | What papers has UMA produced? | `papers` | Programmatic | T1 |
| 151 | Show me all research from Tampere | `papers` | Programmatic | T1 |
| 152 | How many publications does THWS have? | `papers` | Programmatic | T1 |
| 153 | Who are the active researchers at Sorbonne Paris Nord? | `papers` | Programmatic | T1 |
| 154 | List USPN publications | `papers` | Programmatic | T1 |
| 155 | What has the University of Tirana contributed? | `papers` | Programmatic | T1 |
| 156 | Research output from Kauno Kolegija | `papers` | Programmatic | T1 |
| 157 | Papers from the Italian partner | `papers` | Programmatic | T1 |
| 158 | Show me TAMK researchers | `papers` | Programmatic | T1 |
| 159 | All publications from The Hague | `papers` | Programmatic | T1 |
| 160 | what's UDCLV been working on? | `papers` | Programmatic | T2 |
| 161 | anything from the German university? | `papers` | Programmatic | T2 |
| 162 | THUAS output | `papers` | Programmatic | T2 |
| 163 | papers from Finland | `papers` | Programmatic | T2 |
| 164 | Which university has the most publications and who are their top researchers? | `papers` | Programmatic | T3 |
| 165 | Compare the research output of UMA and UDCLV | `papers` | Programmatic | T3 |
| 166 | Which areas of responsible AI are underrepresented in the database? | `gap` | LLM-assisted | T1 |
| 167 | What topics should UNINOVIS focus on next? | `gap` | LLM-assisted | T1 |
| 168 | Are there any blind spots in the research portfolio? | `gap` | LLM-assisted | T1 |
| 169 | What responsible AI challenges are not being addressed? | `gap` | LLM-assisted | T1 |
| 170 | Identify potential new research directions | `gap` | LLM-assisted | T1 |
| 171 | Which subtopics have zero papers? | `gap` | LLM-assisted | T1 |
| 172 | Where are the opportunities for new research? | `gap` | LLM-assisted | T1 |
| 173 | Topics that UNINOVIS has not explored yet | `gap` | LLM-assisted | T1 |
| 174 | What is missing from the current research coverage? | `gap` | LLM-assisted | T1 |
| 175 | Any unexplored areas in AI fairness research? | `gap` | LLM-assisted | T1 |
| 176 | where should we look next? | `gap` | LLM-assisted | T2 |
| 177 | what hasn't been covered yet? | `gap` | LLM-assisted | T2 |
| 178 | are there topics nobody is working on? | `gap` | LLM-assisted | T2 |
| 179 | white spaces in the research map? | `gap` | LLM-assisted | T2 |
| 180 | If I wanted to start a new research line, where would the biggest gap be? | `gap` | LLM-assisted | T3 |
| 181 | Are there responsible AI topics that only one university covers? | `gap` | LLM-assisted | T3 |
| 182 | What areas are saturated vs underexplored in the UNINOVIS portfolio? | `gap` | LLM-assisted | T3 |
| 183 | Do you think AI will replace human workers? | `general` | LLM-assisted | T1 |
| 184 | How does responsible AI relate to sustainability? | `general` | LLM-assisted | T1 |
| 185 | What are the main challenges in AI ethics today? | `general` | LLM-assisted | T1 |
| 186 | Is regulation enough to make AI safe? | `general` | LLM-assisted | T1 |
| 187 | What role does education play in responsible AI? | `general` | LLM-assisted | T1 |
| 188 | Can we ever fully trust AI systems? | `general` | LLM-assisted | T1 |
| 189 | What is the future of AI governance? | `general` | LLM-assisted | T1 |
| 190 | How should AI be taught in universities? | `general` | LLM-assisted | T1 |
| 191 | Are current AI models biased? | `general` | LLM-assisted | T1 |
| 192 | What makes an AI system trustworthy? | `general` | LLM-assisted | T1 |
| 193 | Should AI have rights? | `general` | LLM-assisted | T1 |
| 194 | How do we measure fairness in AI? | `general` | LLM-assisted | T1 |
| 195 | why is AI ethics important? | `general` | LLM-assisted | T2 |
| 196 | is there any consensus on what trustworthy AI means? | `general` | LLM-assisted | T2 |
| 197 | what's the deal with AI and jobs? | `general` | LLM-assisted | T2 |
| 198 | do LLMs have biases? | `general` | LLM-assisted | T2 |
| 199 | how worried should we be about AI? | `general` | LLM-assisted | T2 |
| 200 | can AI systems be held legally responsible for their decisions? | `general` | LLM-assisted | T2 |
| 201 | Is it possible to build an AI system that is both fair and accurate? | `general` | LLM-assisted | T3 |
| 202 | What would a responsible AI curriculum look like at the university level? | `general` | LLM-assisted | T3 |
| 203 | How do different cultures approach the question of AI ethics? | `general` | LLM-assisted | T3 |
| 204 | Is there a trade-off between explainability and performance in ML models? | `general` | LLM-assisted | T3 |
| 205 | Go deeper into that | `followup` | LLM-assisted | T1 |
| 206 | What about the ethical implications? | `followup` | LLM-assisted | T1 |
| 207 | And from the Spanish university? | `followup` | LLM-assisted | T1 |
| 208 | Show me more | `followup` | LLM-assisted | T1 |
| 209 | Continue | `followup` | LLM-assisted | T1 |
| 210 | Yes, elaborate please | `followup` | LLM-assisted | T1 |
| 211 | can you expand on point 3? | `followup` | LLM-assisted | T2 |
| 212 | what else? | `followup` | LLM-assisted | T2 |
| 213 | more | `followup` | LLM-assisted | T2 |
| 214 | and the others? | `followup` | LLM-assisted | T2 |
| 215 | ok but what about from THWS specifically? | `followup` | LLM-assisted | T3 |
| 216 | That's interesting — are there any papers that contradict this? | `followup` | LLM-assisted | T3 |

### A.3 Summary

| Category | Response path | Development set | Evaluation set (T1 / T2 / T3) |
|----------|--------------|-----------------|-------------------------------|
| `figure` | Programmatic | 5 | 14 (8 / 4 / 2) |
| `followup` | LLM-assisted | 3 | 12 (6 / 4 / 2) |
| `gap` | LLM-assisted | 5 | 17 (10 / 4 / 3) |
| `general` | LLM-assisted | 4 | 22 (12 / 6 / 4) |
| `glossary` | Programmatic | 9 | 19 (10 / 6 / 3) |
| `meta` | Programmatic | 8 | 18 (10 / 5 / 3) |
| `non_research` | Programmatic | 9 | 20 (10 / 6 / 4) |
| `off_topic` | Programmatic | 5 | 24 (12 / 8 / 4) |
| `papers` | Programmatic | 3 | 16 (10 / 4 / 2) |
| `project` | Programmatic | 5 | 16 (10 / 4 / 2) |
| `researcher` | Programmatic | 6 | 18 (10 / 5 / 3) |
| `topic_search` | Programmatic | 7 | 20 (12 / 5 / 3) |
| **Total** | | **69** | **216** (120 / 61 / 35) |