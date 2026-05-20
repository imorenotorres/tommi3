# Glossary of Responsible AI Concepts

This glossary provides definitions of key concepts in Responsible AI, curated for the UNINOVIS alliance research context. Each entry includes academic references where available.

---

## Responsible AI

Responsible AI refers to the practice and processes of designing, developing, and deploying artificial intelligence systems in a manner that is ethical, transparent, fair, and accountable. It includes maintenance, algorithmic audits, and accountability, as well as a broad set of principles aimed at ensuring that AI technologies benefit individuals and society while minimising potential harms.

*Responsibility in this case is understood as a description of the user's use of AI, rather than an adjective of the system itself. The principles that characterise responsible AI are: privacy, accountability, safety and security, transparency and explainability, fairness and non-discrimination, human control of technology, professional responsibility, and promotion of human values.*

**Related concepts:** Trustworthy AI; AI Ethics; Fairness in AI; Transparency in AI; Accountability in AI; AI Governance; Explainable Artificial Intelligence (XAI); Human-Centred AI

**References:**

- Baeza-Yates, R. (2024). Introduction to Responsible AI. *WSDM '24: Proceedings of the 17th ACM International Conference on Web Search and Data Mining*, 1114--1117. <https://doi.org/10.1145/3616855.3636455>
- Dignum, V. (2019). *Responsible Artificial Intelligence: How to Develop and Use AI in a Responsible Way*. Springer. <https://doi.org/10.1007/978-3-030-30371-6>
- Fjeld, J., Achten, N., Hilligoss, H., Nagy, A., & Srikumar, M. (2020). Principled Artificial Intelligence: Mapping Consensus in Ethical and Rights-Based Approaches to Principles for AI. *Berkman Klein Center Research Publication*. <https://doi.org/10.2139/ssrn.3518482>

---

## Trustworthy AI

Trustworthy AI refers to AI systems that are lawful, ethical, and robust, ensuring they operate reliably and safely in real-world contexts. According to the European Commission's High-Level Expert Group on AI (the first comprehensive legal framework for trustworthy AI), trustworthy AI must satisfy seven key requirements: human agency and oversight, technical robustness and safety, privacy and data governance, transparency, diversity, non-discrimination and fairness, societal and environmental well-being, and accountability. Mentions to both trustworthiness and responsibility are in reference to the use of AI, as these concepts cannot be qualities of a being that in principle is not autonomous or accountable, at least as currently AI capabilities are conceived and implemented.

**Related concepts:** Responsible AI; AI Ethics; Transparency in AI; Fairness in AI; Accountability in AI; Robustness in AI; EU AI Act; Human-Centred AI

**References:**

- European Commission, High-Level Expert Group on AI (2019). *Ethics Guidelines for Trustworthy AI*. <https://digital-strategy.ec.europa.eu/en/library/ethics-guidelines-trustworthy-ai>
- European Parliament and Council (2024). Regulation (EU) 2024/1689 (AI Act). <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- Thiebes, S., Lins, S., & Sunyaev, A. (2021). Trustworthy artificial intelligence. *Electronic Markets*, 31, 447--464. <https://doi.org/10.1007/s12525-020-00441-4>
- Li, B., Qi, P., Liu, B., Di, S., Liu, J., Pei, J., Yi, J., & Zhou, B. (2023). Trustworthy AI: From Principles to Practices. *ACM Computing Surveys*, 55(9), 1--46. <https://doi.org/10.1145/3555803>

---

## Explainable Artificial Intelligence (XAI)

Explainable AI (XAI) refers to a collection of machine learning techniques that enables human users to understand, appropriately trust, and effectively manage the emerging generation of artificially intelligent partners. In other words it refers to the methods and techniques that make the behaviour and outputs of AI systems understandable to humans. XAI aims to bridge the gap between high-performing but opaque models (such as deep neural networks) and the need for human interpretability, enabling users, developers, and regulators to understand why an AI system made a particular decision. Explainability covers the techniques used to convert a non-interpretable model into an explainable one, by producing details or reasons to make its functioning clear or easy to understand.

The general principles to help create effective, more human-understandable AI systems: ability to explain its capabilities and understandings; what it has done, what it is doing now, and what will happen next; and disclose the salient information that it is acting on.

Key XAI methods include LIME (Local Interpretable Model-agnostic Explanations), SHAP (SHapley Additive exPlanations), attention mechanisms, saliency maps, and concept-based explanations.

**Related concepts:** AI Ethics; Transparency in AI; Accountability in AI; Trustworthy AI; Interpretability vs. Explainability; Human-Centred AI; Responsible AI

**References:**

- Arrieta, A. B., Diaz-Rodriguez, N., Del Ser, J., et al. (2020). Explainable Artificial Intelligence (XAI): Concepts, taxonomies, opportunities and challenges toward responsible AI. *Information Fusion*, 58, 82--115. <https://doi.org/10.1016/j.inffus.2019.12.012>
- Gunning, D., Stefik, M., Choi, J., Miller, T., Stumpf, S., & Yang, G.-Z. (2019). XAI---Explainable artificial intelligence. *Science Robotics*, 4(37), eaay7120. <https://doi.org/10.1126/scirobotics.aay7120>

---

## AI Ethics

AI Ethics is the branch of applied ethics that examines the moral implications related to AI systems. It addresses questions about the values embedded in AI design, the societal impact of AI deployment, and the responsibilities of developers, deployers, and users. Core concerns (coming from traditional bioethics principles) include beneficence, non-maleficence, autonomy, justice; and new enabling principles for AI such as explicability. Other principles and themes often mentioned in guidelines, proposals and recommendations are transparency, responsibility, bias and discrimination, privacy, autonomy, informed consent, the digital divide, and the environmental impact of AI, amongst many others.

**Related concepts:** Responsible AI; Fairness in AI; Bias in AI; Transparency in AI; Accountability in AI; Explainable Artificial Intelligence (XAI); AI Governance; Privacy and Data Governance in AI; Sustainable AI

**References:**

- Jobin, A., Ienca, M., & Vayena, E. (2019). The global landscape of AI ethics guidelines. *Nature Machine Intelligence*, 1(9), 389--399. <https://doi.org/10.1038/s42256-019-0088-2>
- Floridi, L., Cowls, J., Beltrametti, M., et al. (2018). AI4People---An Ethical Framework for a Good AI Society: Opportunities, Risks, Principles, and Recommendations. *Minds and Machines*, 28, 689--707. <https://doi.org/10.1007/s11023-018-9482-5>
- Hagendorff, T. (2020). The Ethics of AI Ethics: An Evaluation of Guidelines. *Minds and Machines*, 30, 99--120. <https://doi.org/10.1007/s11023-020-09517-8>

---

## Fairness in AI

Fairness in AI concerns the design and evaluation of AI systems to ensure they do not produce bias, understood as any prejudice or favouritism towards an individual or group based on their inherent or acquired characteristics. It is the moral lens through which we examine decisions made by AI systems that do not produce discriminatory outcomes across different groups defined by protected attributes such as race, gender, age, or disability, amongst other characteristics. With more than twenty different notions of fairness proposed in the last few years, fairness is a complex and debated topic. It has been tried to be defined, in the field of ethics and technology, through multiple mathematical formalisms, including demographic parity, equalised odds, and individual fairness, which are often mutually incompatible.

**Related concepts:** Bias in AI; AI Ethics; Accountability in AI; Responsible AI; Algorithmic Auditing; Transparency in AI

**References:**

- Mehrabi, N., Morstatter, F., Saxena, N., Lerman, K., & Galstyan, A. (2021). A Survey on Bias and Fairness in Machine Learning. *ACM Computing Surveys*, 54(6), 1--35. <https://doi.org/10.1145/3457607>
- Barocas, S., Hardt, M., & Narayanan, A. (2023). *Fairness and Machine Learning: Limitations and Opportunities*. MIT Press. <https://fairmlbook.org/>
- Verma, S. & Rubin, J. (2018). Fairness Definitions Explained. *IEEE/ACM International Workshop on Software Fairness (FairWare)*, 1--7. <https://doi.org/10.1145/3194770.3194776>

---

## Bias in AI

Bias is a broad concept studied across many disciplines including social science, cognitive psychology or law, and encompasses phenomena such as confirmation bias and other cognitive biases, as well as systemic, discriminatory outcomes, or harms. Bias in AI refers to systematic errors or prejudices in AI system outputs that arise from biased training data, flawed model design, or biased human decisions during development. Types of AI bias include: Data to Algorithm (Aggregation Bias, Measurement Bias, Omitted Variable Bias, Representation Bias, Sampling Bias...); Algorithm to User (Algorithmic Bias, User Interaction Bias, Popularity Bias, Emergent Bias, Evaluation Bias); or User to Data (Historical Bias, Population Bias, Self-selection Bias, Social Bias, Behavioral Bias, Temporal Bias, Content Production Bias).

**Related concepts:** Fairness in AI; AI Ethics; Algorithmic Auditing; Accountability in AI; Responsible AI; Transparency in AI

**References:**

- Mehrabi, N., Morstatter, F., Saxena, N., Lerman, K., & Galstyan, A. (2021). A Survey on Bias and Fairness in Machine Learning. *ACM Computing Surveys*, 54(6), 1--35. <https://doi.org/10.1145/3457607>
- Olteanu, A., Castillo, C., Diaz, F., & Kiciman, E. (2019). Social Data: Biases, Methodological Pitfalls, and Ethical Boundaries. *Frontiers in Big Data*, 2, 13. <https://doi.org/10.3389/fdata.2019.00013>

---

## Transparency in AI

Transparency can be broadly understood as the availability of information about an actor allowing other actors to monitor the workings or performance of this actor. It can also refer to explainability, interpretability, openness, accessibility, and visibility, amongst others. Transparency in AI refers to the degree to which the workings, decisions, and data usage of an AI system can be understood and examined by stakeholders. Thus, in AI it necessarily entails a relational perspective, conceived not as an individual characteristic but as a relation between an agent and a recipient.

As defined by the European Parliament, transparency in AI is what enables appropriate traceability and explainability of AI systems, ensures that individuals are made aware when they are communicating or interacting with an AI, and duly informs deployers of the system's capabilities and limitations, as well as affected persons of their rights. Transparency is a prerequisite for accountability and is mandated in the EU AI Act for high-risk AI systems.

**Related concepts:** Explainable Artificial Intelligence (XAI); Accountability in AI; Trustworthy AI; AI Ethics; Responsible AI; EU AI Act; Interpretability vs. Explainability

**References:**

- Felzmann, H., Villaronga, E. F., Lutz, C., & Tamo-Larrieux, A. (2020). Towards Transparency by Design for Artificial Intelligence. *Science and Engineering Ethics*, 26, 3333--3361. <https://doi.org/10.1007/s11948-020-00276-4>
- European Parliament and Council (2024). Regulation (EU) 2024/1689 (AI Act), Articles 13--14 on transparency obligations. <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>

---

## Accountability in AI

Accountability in AI refers to the obligation to justify its decisions and take responsibility for the outcomes and impacts of AI systems. It requires clear identification of who is responsible for the outcomes. In this sense it relates to the expectation that designers, developers, and deployers will comply with standards and legislation to ensure the proper functioning of AIs during their lifecycle, and thus spans individual, organisational, and regulatory levels. The features of accountability in AI include: context; range; agent; forum; standards; process; and implications.

**Related concepts:** Transparency in AI; AI Ethics; AI Governance; Algorithmic Auditing; Responsible AI; Trustworthy AI; EU AI Act

**References:**

- Novelli, C., Taddeo, M., & Floridi, L. (2023). Accountability in artificial intelligence: What it is and how it works. *AI & Society*, 39, 1871--1882. <https://doi.org/10.1007/s00146-023-01635-y>
- Raji, I. D., Smart, A., White, R. N., et al. (2020). Closing the AI accountability gap: Defining an end-to-end framework for internal algorithmic auditing. *Proceedings of ACM FAT*, 33--44. <https://doi.org/10.1145/3351095.3372873>

---

## Privacy and Data Governance in AI

Privacy in AI involves protecting personal and sensitive information from unauthorized access and ensuring that data is used by AI systems responsibly throughout the AI lifecycle, including data collection, storage, processing, and model deployment. Regulations and standards, such as the General Data Protection Regulation (GDPR) in the European Union, play a significant role in shaping AI ethics by setting strict guidelines for data use.

Differential privacy (a strong standard for privacy guarantees for algorithms on aggregate databases), federated learning (a machine learning setting where many clients collaboratively train a model under the orchestration of a central server, while keeping the training data decentralized), and data minimisation are amongst some of the technical approaches to preserving privacy in AI systems.

Data governance is the exercise of authority, decision making and control over the management of data. It defines the decision rights and accountabilities that determine how, by whom, and under what conditions information-related processes are carried out. Thus the goals of data governance are ensuring the quality and proper use of data, meeting compliance requirements, and helping utilize data to create public value.

Key challenges for privacy and data governance include the re-identification risk from anonymised datasets, the privacy implications of large-scale data collection for training, and the tension between data utility and privacy protection.

**Related concepts:** AI Ethics; AI Governance; Trustworthy AI; Responsible AI; Data Sovereignty; EU AI Act

**References:**

- Janssen, M., Brous, P., Barbosa, L., Janowski, T. (2020). Data governance: Organizing data for trustworthy Artificial Intelligence. *Government Information Quarterly*, 37(3). <https://doi.org/10.1016/j.giq.2020.101493>
- Radanliev, P. (2025). AI Ethics: Integrating Transparency, Fairness, and Privacy in AI Development. *Applied Artificial Intelligence*, 39(1). <https://doi.org/10.1080/08839514.2025.2463722>
- Abadi, M., Chu, A., Goodfellow, I., et al. (2016). Deep Learning with Differential Privacy. *Proceedings of ACM CCS*, 308--318. <https://doi.org/10.1145/2976749.2978318>
- Kairouz, P., McMahan, H. B., et al. (2021). Advances and Open Problems in Federated Learning. *Foundations and Trends in Machine Learning*, 14(1--2), 1--210. <https://doi.org/10.1561/2200000083>

---

## Human-Centred AI

Human-Centred AI (HCAI) is an approach to AI design that focuses on understanding purposes, human values, and desired AI properties in the creation of AI systems by applying Human-Centered Design practices. HCAI seeks to augment human capabilities while maintaining human control over AI systems, by considering the necessity, context, and ethical and legal conditions of the AI system as well as promoting individual and societal well-being. It emphasises that AI systems should augment and empower humans rather than replace them, and that human oversight should be maintained throughout the AI lifecycle. HCAI draws on principles from human-computer interaction (HCI), participatory design, and cognitive science.

**Related concepts:** Responsible AI; Trustworthy AI; AI Ethics; Explainable Artificial Intelligence (XAI); Transparency in AI; AI Safety

**References:**

- Schmager, S., Pappas, I. O., & Vassilakopoulou, P. (2025). Understanding Human-Centred AI: a review of its defining elements and a research agenda. *Behaviour & Information Technology*, 44(15), 3771--3810. <https://doi.org/10.1080/0144929X.2024.2448719>
- Shneiderman, B. (2022). *Human-Centered AI*. Oxford University Press. <https://doi.org/10.1093/oso/9780192845290.001.0001>
- Xu, W. (2019). Toward human-centered AI: a perspective from human-computer interaction. *Interactions*, 26(4), 42--46. <https://doi.org/10.1145/3328485>

---

## AI Safety

AI Safety is the field concerned with ensuring that AI systems operate as intended without causing unintended harm, as machine learning becomes more widely used, especially in areas where safety and security are critical. With the aim to mitigate risks, it focuses on technical solutions to ensure that AI systems operate safely and reliably. More specifically, it aims to identify causes of unintended behavior in machine learning systems and develop tools to ensure these systems work safely and reliably, addressing problems of robustness, assurance, and specification. Problems in AI safety can be grouped into three categories: robustness, assurance, and specification.

**Related concepts:** Robustness in AI; Trustworthy AI; AI Ethics; Responsible AI; Human-Centred AI; AI Governance

**References:**

- Rudner, T., & Toner, H. (2021). Key Concepts in AI Safety: An Overview. *Center for Security and Emerging Technology*. <https://doi.org/10.51593/20190040>
- Hendrycks, D., Mazeika, M., & Woodside, T. (2023). An Overview of Catastrophic AI Risks. *arXiv preprint arXiv:2306.12001*. <https://doi.org/10.48550/arXiv.2306.12001>
- Russell, S. (2019). *Human Compatible: Artificial Intelligence and the Problem of Control*. Viking.

---

## Algorithmic Auditing

Algorithmic auditing is the systematic evaluation of AI systems to assess their compliance with policy, industry standards or regulations. It is done by repeatedly and systematically querying an algorithm with inputs and observing the corresponding outputs in order to draw inferences about its opaque inner workings. Audits may examine bias, data quality, model fairness, transparency, security, and societal impact. Auditing can be internal (conducted by the developing organisation) or external (conducted by independent third parties or regulators).

**Related concepts:** Accountability in AI; Fairness in AI; Bias in AI; Transparency in AI; AI Governance; AI Ethics; EU AI Act

**References:**

- Raji, I. D., Smart, A., White, R. N., et al. (2020). Closing the AI accountability gap: Defining an end-to-end framework for internal algorithmic auditing. *Proceedings of ACM FAT*, 33--44. <https://doi.org/10.1145/3351095.3372873>
- Metaxa, D., Park, J. S., Karahalios, K., Sandvig, C., & Eslami, M. (2021). Auditing Algorithms: Understanding Algorithmic Systems from the Outside In. *Foundations and Trends in Human--Computer Interaction*, 14(4), 272--344. <https://doi.org/10.1561/1100000083>
- Mokander, J., Morley, J., Taddeo, M., & Floridi, L. (2021). Ethics-Based Auditing of Automated Decision-Making Systems: Nature, Scope, and Limitations. *Science and Engineering Ethics*, 27, 44. <https://doi.org/10.1007/s11948-021-00319-4>

---

## AI Governance

AI Governance refers to the frameworks, policies, institutions, and practices that guide the development, deployment, and oversight of AI systems. It spans organisational governance (internal AI policies, ethics boards), national governance (legislation, regulatory bodies), and international governance (treaties, standards, multilateral agreements).

**Related concepts:** AI Ethics; Accountability in AI; EU AI Act; Responsible AI; Trustworthy AI; Algorithmic Auditing; Privacy and Data Governance in AI

**References:**

- Cihon, P. (2019). Standards for AI Governance: International Standards to Enable Global Coordination in AI Research & Development. *Future of Humanity Institute, University of Oxford*.
- European Parliament and Council (2024). Regulation (EU) 2024/1689 (AI Act). <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- OECD (2019). Recommendation of the Council on Artificial Intelligence (OECD AI Principles). <https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0449>
- UNESCO (2021). Recommendation on the Ethics of Artificial Intelligence. <https://unesdoc.unesco.org/ark:/48223/pf0000381137>

---

## Robustness in AI

Robustness in AI refers to the ability of AI systems to maintain reliable performance when confronted with unexpected inputs, adversarial attacks, distribution shifts, or noisy data. A robust AI system should degrade gracefully rather than fail catastrophically when operating outside its training distribution.

**Related concepts:** AI Safety; Trustworthy AI; Responsible AI; Bias in AI

**References:**

- Goodfellow, I. J., Shlens, J., & Szegedy, C. (2015). Explaining and Harnessing Adversarial Examples. *Proceedings of ICLR*. <https://doi.org/10.48550/arXiv.1412.6572>
- Hendrycks, D. & Dietterich, T. (2019). Benchmarking Neural Network Robustness to Common Corruptions and Perturbations. *Proceedings of ICLR*. <https://doi.org/10.48550/arXiv.1903.12261>
- Szegedy, C., Zaremba, W., Sutskever, I., et al. (2014). Intriguing properties of neural networks. *Proceedings of ICLR*. <https://doi.org/10.48550/arXiv.1312.6199>

---

## AI and Healthcare

AI in Healthcare refers to the application of AI techniques to medical and health-related domains, including clinical decision support, medical image analysis, drug discovery, patient monitoring, and health system optimisation. Responsible AI in healthcare is particularly critical due to the high stakes involved, requiring rigorous validation, transparency, fairness across patient demographics, and compliance with medical regulations.

**Related concepts:** AI Ethics; Fairness in AI; Bias in AI; Explainable Artificial Intelligence (XAI); Privacy and Data Governance in AI; Responsible AI

**References:**

- Topol, E. J. (2019). High-performance medicine: the convergence of human and artificial intelligence. *Nature Medicine*, 25, 44--56. <https://doi.org/10.1038/s41591-018-0300-7>
- Kelly, C. J., Karthikesalingam, A., Suleyman, M., Corrado, G., & King, D. (2019). Key challenges for delivering clinical impact with artificial intelligence. *BMC Medicine*, 17, 195. <https://doi.org/10.1186/s12916-019-1426-2>
- WHO (2021). *Ethics and governance of artificial intelligence for health: WHO guidance*. <https://www.who.int/publications/i/item/9789240029200>

---

## Interpretability vs. Explainability

Interpretability and explainability are related but distinct concepts. Interpretability refers to the degree to which a human can understand the internal mechanics of a model (intrinsic property of the model itself). Explainability refers to the ability to provide post-hoc explanations for a model's outputs, even when the model itself is not inherently interpretable. Inherently interpretable models include decision trees and linear regression; post-hoc explanation methods include LIME, SHAP, and saliency maps applied to black-box models.

**Related concepts:** Explainable Artificial Intelligence (XAI); Transparency in AI; Trustworthy AI; Human-Centred AI

**References:**

- Lipton, Z. C. (2018). The Mythos of Model Interpretability. *Queue*, 16(3), 31--57. <https://doi.org/10.1145/3236386.3241340>
- Rudin, C. (2019). Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead. *Nature Machine Intelligence*, 1, 206--215. <https://doi.org/10.1038/s42256-019-0048-x>
- Molnar, C. (2022). *Interpretable Machine Learning: A Guide for Making Black Box Models Explainable* (2nd ed.). <https://christophm.github.io/interpretable-ml-book/>

---

## Data Sovereignty

Data sovereignty is the principle that data is subject to the laws and governance structures of the country or region in which it is collected or processed. In the context of AI, data sovereignty is critical for ensuring compliance with data protection regulations (such as GDPR in the EU), preventing unauthorised cross-border data transfers, and maintaining control over sensitive research data.

**Related concepts:** Privacy and Data Governance in AI; AI Governance; EU AI Act; AI Ethics

**References:**

- European Parliament and Council (2016). Regulation (EU) 2016/679 (General Data Protection Regulation, GDPR). <https://eur-lex.europa.eu/eli/reg/2016/679/oj>
- Hummel, P., Braun, M., Tretter, M., & Dabrock, P. (2021). Data sovereignty: A review. *Big Data & Society*, 8(1). <https://doi.org/10.1177/2053951720982012>
- European Commission (2020). A European Strategy for Data. <https://digital-strategy.ec.europa.eu/en/policies/strategy-data>

---

## EU AI Act

The EU AI Act (Regulation 2024/1689) is the first comprehensive legal framework for artificial intelligence worldwide. It establishes a risk-based classification of AI systems into four categories: unacceptable risk (banned), high risk (subject to strict requirements), limited risk (transparency obligations), and minimal risk (no specific obligations). The regulation applies to providers, deployers, importers, and distributors of AI systems operating within the EU market.

**Related concepts:** AI Governance; Trustworthy AI; Accountability in AI; Transparency in AI; Algorithmic Auditing; Responsible AI; Privacy and Data Governance in AI

**References:**

- European Parliament and Council (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (AI Act). <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- Veale, M. & Zuiderveen Borgesius, F. (2021). Demystifying the Draft EU Artificial Intelligence Act. *Computer Law Review International*, 22(4), 97--112. <https://doi.org/10.9785/cri-2021-220402>
- Edwards, L. (2022). The EU AI Act: a summary of its significance and scope. *Ada Lovelace Institute*. <https://www.adalovelaceinstitute.org/resource/eu-ai-act/>

---

## Sustainable AI

Sustainable AI addresses the environmental impact of AI systems, including the energy consumption of training and deploying large models, the carbon footprint of data centres, and the electronic waste from hardware. It also encompasses the use of AI to support sustainability goals such as climate modelling, resource optimisation, and environmental monitoring.

**Related concepts:** AI Ethics; Responsible AI; AI Governance

**References:**

- Strubell, E., Ganesh, A., & McCallum, A. (2019). Energy and Policy Considerations for Deep Learning in NLP. *Proceedings of ACL*, 3645--3650. <https://doi.org/10.18653/v1/P19-1355>
- Schwartz, R., Dodge, J., Smith, N. A., & Etzioni, O. (2020). Green AI. *Communications of the ACM*, 63(12), 54--63. <https://doi.org/10.1145/3381831>
- van Wynsberghe, A. (2021). Sustainable AI: AI for sustainability and the sustainability of AI. *AI and Ethics*, 1, 213--218. <https://doi.org/10.1007/s43681-021-00043-6>

---

## Generative AI and Responsibility

Generative AI refers to AI systems capable of creating new content, including text, images, audio, video, and code. Responsible deployment of generative AI raises specific concerns including hallucination (generating plausible but false content), deepfakes, intellectual property rights, misinformation amplification, and the environmental cost of training large generative models.

**Related concepts:** AI Ethics; Responsible AI; Transparency in AI; AI Safety; Bias in AI; Sustainable AI; EU AI Act

**References:**

- Weidinger, L., Mellor, J., Rauh, M., et al. (2021). Ethical and social risks of harm from Language Models. *arXiv preprint arXiv:2112.04359*. <https://doi.org/10.48550/arXiv.2112.04359>
- Bender, E. M., Gebru, T., McMillan-Major, A., & Shmitchell, S. (2021). On the Dangers of Stochastic Parrots: Can Language Models Be Too Big? *Proceedings of ACM FAccT*, 610--623. <https://doi.org/10.1145/3442188.3445922>
- Bommasani, R., Hudson, D. A., Adeli, E., et al. (2021). On the Opportunities and Risks of Foundation Models. *arXiv preprint arXiv:2108.07258*. <https://doi.org/10.48550/arXiv.2108.07258>
