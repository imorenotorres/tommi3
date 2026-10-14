# Development Query Set

**Source file:** `Paper/Version3/Materials/development_set_9class.json`
**Role in study:** Construction set — seen by both classifiers (rule-based and LLM-based) during the Automated Agent Construction Protocol.
**Total queries:** 150 (50 base queries × 3 variants each)
**Variant types:** `standard`, `typo` (L1-typographic errors), `grammar` (L2-grammatical errors)

---

## Category taxonomy

| Category | Description |
|---|---|
| `meta` | Queries about the agent itself, its data sources or capabilities |
| `organization` | Factual queries about UNINOVIS or member institutions |
| `general` | Research/academic questions NOT related to Responsible AI |
| `out_of_scope` | Non-research queries: task requests, greetings, trivia, opinions |
| `papers` | Queries about publications at a specific university, or visualisation requests |
| `researcher` | Queries about specific researchers or lists of researchers |
| `project` | Queries about named research projects |
| `topic` | Thematic literature searches within Responsible AI (incl. gap analysis) |
| `glossary` | Definitional queries about a Responsible AI concept or term |

---

## Notes

- Each base query (`base_id`) has three variants: **standard**, **typo**, **grammar**.
- Tiers: T1 = standard phrasings; T2 = unusual/informal/indirect; T3 = adversarial/edge cases.
- `pap_6` queries request a visualisation (`output_format: figure`); all other queries are `output_format: text`.

---

## Queries

### meta (5 base queries × 3 variants = 15)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| meta_1 | T1 | What are your capabilities? | What are your capabilitis? | What capabilities you have? |
| meta_2 | T1 | Who are you? | Who are yu? | you are who? |
| meta_3 | T2 | What topics can you help me with? | What topics can you hel me with? | With what topics you can help me? |
| meta_4 | T2 | What is the scope of your knowledge? | What is the scop of your nowledge? | What is scope of your knowledge? |
| meta_5 | T2 | Do you have access to UNINOVIS publications? | Do you have acces to UNINOVIS publicacions? | Have you access to UNINOVIS publications? |

### organization (4 base queries × 3 variants = 12)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| org_1 | T1 | What is UNINOVIS? | What is UNINOIVS? | Whats UNINOVIS? |
| org_2 | T1 | Which universities belong to UNINOVIS? | Which universitis belon to UNINOVIS? | Which universities are belong to UNINOVIS? |
| org_3 | T1 | How many countries are part of UNINOVIS? | How many countris are part of UNINOVIS? | How many countries is part of UNINOVIS? |
| org_4 | T2 | What is UMA's role in the alliance? | What is UMA's rol in the aliance? | What the role of UMA in the alliance? |

### general (6 base queries × 3 variants = 18)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| gen_1 | T1 | What is machine learning? | What is machin learning? | What is learning machine? |
| gen_2 | T1 | Papers on deep learning for image recognition | Papers on deep lerning for imag recognition | Papers about deep learning for to recognize images |
| gen_3 | T1 | Research on compiler optimisation | Reserch on compiler optimisation | Research of compiler optimisation |
| gen_4 | T2 | What is the latest in quantum computing research? | What is the lates in kuantun computing reserch? | What is last in quantum computing research? |
| gen_5 | T2 | I need publications on neural machine translation | I need publications on neural machin translacion | I need  informations about neural machine translation |
| gen_6 | T3 | Are there any studies on NLP for code generation? | Are there any studis on NLP for kode yeneration? | There are studies of NLP for code generation? |

### out_of_scope (6 base queries × 3 variants = 18)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| oos_1 | T1 | Write me an essay about AI | Write me an esay about AI | Write a essay of AI |
| oos_2 | T1 | What is the weather today? | What is the whether today? | How is the weather? |
| oos_3 | T1 | Who won the last World Cup? | Who won the last World Cap? | Who had the last World Cup? |
| oos_4 | T1 | Can you book a flight to The Hague? | Can you book a flait to The Hague? | Can you to book a flight to The Hague? |
| oos_5 | T2 | Help me write a report on responsible AI | Help me write a repport on responsable IA | Help me for writing a report on responsible AI |
| oos_6 | T2 | What is your opinion on AI regulation? | What is your opinion on AI regulacion? | What your opinion about the AI regulation? |

### papers (6 base queries × 3 variants = 18)

*`pap_6` requests a visualisation (`output_format: figure`) in all three variants.*

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| pap_1 | T1 | List all papers from THUAS researchers | List all papers from THUAS reserchers | List all papers of THUAS researchers |
| pap_2 | T1 | How many papers has KK published? | How many peipers has KK published? | How many papers KK has published? |
| pap_3 | T1 | Show me publications from TAMK on AI ethics | Show me publicasions from TAMK on AI ethic | Show publications of TAMK about AI ethics |
| pap_4 | T2 | Any papers from Lithuanian researchers? | Any papers from Litanian reserchers? | Any papers of Lithuanian researchers? |
| pap_5 | T2 | Recent publications from UDCLV university | Recent publiccations from UDCLV universiti | What are the recent publications of UDCLV university? |
| pap_6 | T2 | Show me the publication timeline for UMA as a chart | Show me the publication taimline for UMA as a chart | Show me the publication timeline of UMA like a chart |

### researcher (6 base queries × 3 variants = 18)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| res_1 | T1 | Who are the main researchers at UMA? | Who are the main reserchers at UMA? | Who is the main researchers of UMA? |
| res_2 | T1 | What has Antonio Moreno published? | What has Antonio Moreno publised? | What is Antonio Moreno publications? |
| res_3 | T1 | Find publications by Giulio Iannello | Find publicacions by Gulio Ianello | Find publications of Giulio Iannello |
| res_4 | T2 | Researchers working on explainable AI in UNINOVIS | Reserchers working on explanable AI in UNINOVIS | Which researchers are working in explainable AI in UNINOVIS? |
| res_5 | T2 | List THWS researchers and their publication counts | List THWS reserchers and their publication counts | List the researchers of THWS and their number of publications |
| res_6 | T3 | Who in UNINOVIS works on both AI fairness and interpretability? | Who in UNINOVIS work on both AI fearness and interpretabilty? | Who in UNINOVIS is working in AI fairness and in interpretability? |

### project (5 base queries × 3 variants = 15)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| pro_1 | T1 | Tell me about the IntelliMan project | Tell me abaut de IntelliMan proyect | Tell me about IntelliMan project |
| pro_2 | T1 | What projects are funded by Horizon 2020? | What proyects are fanded by Horizon 2020? | What projects are funded from Horizon 2020? |
| pro_3 | T1 | Describe the DUCA project | Describe de DUCA proyect | Describe me the DUCA project |
| pro_4 | T2 | Are there any projects on elderly care and AI? | Are there any proyects on eldery care and AI? | There are projects about elderly care and AI? |
| pro_5 | T2 | What is the MenHir project about? | What is de MenHir proyect about? | What is about the MenHir project? |

### topic (6 base queries × 3 variants = 18)

*`top_3` queries are annotated `facet: gap`.*

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| top_1 | T1 | What research is there on AI accountability? | What reserch is there on AI acountability? | What research there is on AI accountability? |
| top_2 | T1 | Research on machine learning fairness | Reserch on machine lerning fearness | Research about machine learning fairness |
| top_3 | T1 | Research gaps in AI ethics | Reserch gaps in AI ethic | What are research gaps in AI ethics? |
| top_4 | T2 | Are there papers on regulatory compliance for AI? | Are there papers on regulatori compliance for AI? | There are papers about regulatory compliance for AI? |
| top_5 | T2 | Articles about the societal impact of AI | Artikels abaut the societal impact of IA | Articles about the impact of AI in the society |
| top_6 | T3 | What has been done on explainability in high-stakes AI decisions? | What has been done on explainabilty in haig-stake AI decisiones? | What has been made of explainability in high-stakes decisions of AI? |

### glossary (6 base queries × 3 variants = 18)

| base_id | Tier | Standard | Typo | Grammar |
|---|---|---|---|---|
| glo_1 | T1 | What is explainable AI? | What is explanable IA? | What is the explainable AI? |
| glo_2 | T1 | Define fairness in the context of AI | Define fearnes in the context of AI | Define the fairness of AI |
| glo_3 | T1 | What is AI interpretability? | What is AI interpretabilty? | What is the AI interpretability? |
| glo_4 | T2 | What does AI governance mean? | What does AI gobernance mean? | What AI governance means? |
| glo_5 | T2 | What is the difference between interpretability and explainability? | What is the diference between interpretabilty and explanabilty? | What is the difference of interpretability and explainability? |
| glo_6 | T2 | How is trustworthy AI different from responsible AI? | How is trustworthy AI diferent from responsable AI? | How trustworthy AI is different from responsible AI? |

---

## Summary

### Base queries per category

| Category | Base queries | Variants | Total |
|---|---|---|---|
| meta | 5 | 3 | 15 |
| organization | 4 | 3 | 12 |
| general | 6 | 3 | 18 |
| out_of_scope | 6 | 3 | 18 |
| papers | 6 | 3 | 18 |
| researcher | 6 | 3 | 18 |
| project | 5 | 3 | 15 |
| topic | 6 | 3 | 18 |
| glossary | 6 | 3 | 18 |
| **Total** | **50** | | **150** |

### Standard queries by tier

| Category | T1 | T2 | T3 | Total std |
|---|---|---|---|---|
| meta | 2 | 3 | 0 | 5 |
| organization | 3 | 1 | 0 | 4 |
| general | 3 | 2 | 1 | 6 |
| out_of_scope | 4 | 2 | 0 | 6 |
| papers | 3 | 3 | 0 | 6 |
| researcher | 3 | 2 | 1 | 6 |
| project | 3 | 2 | 0 | 5 |
| topic | 3 | 2 | 1 | 6 |
| glossary | 3 | 3 | 0 | 6 |
| **Total** | **27** | **20** | **3** | **50** |
