# Glossary of Responsible AI Concepts

This glossary provides **comprehensive definitions** of key concepts in Responsible AI (explainability, fairness, governance, ethics, trustworthiness), curated for the UNINOVIS alliance. Each entry includes related concepts, academic references, and context for understanding. Contributions and corrections are welcome.

---

## Glossary Entries

---

### **Accountability in AI**

Accountability in AI refers to the principle that **individuals and organizations** developing or deploying AI systems must be answerable for the outcomes of those systems. It encompasses the ability to **identify responsible parties** when AI systems cause harm, the obligation to **explain decisions**, and the establishment of **redress mechanisms** for affected individuals. Accountability frameworks typically address the full AI lifecycle, from design and training data selection to deployment and monitoring.

**Related concepts:** Algorithmic auditing, Transparency, AI governance, Liability, Redress mechanisms

**References:**
- Diakopoulos, N. (2015). Algorithmic accountability. *Digital Journalism*, 3(3), 398–415.
- Wieringa, M. (2020). What to account for when accounting for algorithms: A systematic literature review on algorithmic accountability. *Proceedings of FAT* 2020*, 1–18.

---

### **Adversarial Robustness**

Adversarial robustness is the ability of AI models to maintain correct predictions when inputs are **intentionally perturbed** by an adversary. Adversarial examples — small, often imperceptible modifications to inputs — can cause state-of-the-art classifiers to produce incorrect outputs with high confidence. Research in this area focuses on **attack methods** (FGSM, PGD, C&W), **defense strategies** (adversarial training, certified defenses), and **robustness evaluation**. Adversarial robustness is a key component of trustworthy AI, particularly in safety-critical applications.

**Related concepts:** AI safety, AI security, Robustness, Adversarial attacks, Certified defenses

**References:**
- Goodfellow, I. J., Shlens, J., & Szegedy, C. (2015). Explaining and harnessing adversarial examples. *Proceedings of ICLR 2015*.
- Madry, A., Makelov, A., Schmidt, L., Tsipras, D., & Vladu, A. (2018). Towards deep learning models resistant to adversarial attacks. *Proceedings of ICLR 2018*.

---

### **AI Auditing**

AI auditing is the **systematic evaluation** of AI systems to assess their compliance with ethical principles, legal requirements, and organizational policies. Audits can be **internal** (conducted by the developing organization) or **external** (by independent third parties). They typically examine fairness, accuracy, robustness, privacy, and transparency. AI auditing is becoming a regulatory requirement under frameworks such as the EU AI Act.

**Related concepts:** Algorithmic accountability, Compliance, AI governance, Model cards, Risk assessment

**References:**
- Raji, I. D., Smart, A., White, R. N., et al. (2020). Closing the AI accountability gap: Defining an end-to-end framework for internal algorithmic auditing. *Proceedings of FAT* 2020*, 33–44.
- Metaxa, D., Park, J. S., Landay, J. A., & Hancock, J. (2021). Auditing algorithms: Understanding algorithmic systems from the outside in. *Foundations and Trends in Human-Computer Interaction*, 14(4), 272–344.

---

### **AI Governance**

AI governance encompasses the **policies, regulations, standards, and institutional arrangements** that guide the development, deployment, and use of AI systems. It operates at multiple levels: organizational (internal AI ethics boards, review processes), national (AI strategies, regulations), and international (OECD AI Principles, UNESCO Recommendation). Effective AI governance balances **innovation promotion** with **risk mitigation** and **rights protection**.

**Related concepts:** AI regulation, AI policy, EU AI Act, AI standards, Risk management

**References:**
- Jobin, A., Ienca, M., & Vayena, E. (2019). The global landscape of AI ethics guidelines. *Nature Machine Intelligence*, 1(9), 389–399.
- Cath, C., Wachter, S., Mittelstadt, B., Taddeo, M., & Floridi, L. (2018). Artificial intelligence and the 'good society': The US, EU, and UK approach. *Science and Engineering Ethics*, 24(2), 505–528.

---

### **AI Safety**

AI safety is the research field concerned with ensuring that AI systems operate **reliably, beneficially, and without causing unintended harm**. It addresses both near-term challenges (robustness, specification problems, reward hacking) and long-term concerns (alignment of advanced AI with human values). Key research areas include **reward modeling**, **scalable oversight**, **interpretability for safety**, and **safe exploration** in reinforcement learning.

**Related concepts:** AI alignment, Robustness, Adversarial robustness, Value alignment, Trustworthy AI

**References:**
- Amodei, D., Olah, C., Steinhardt, J., et al. (2016). Concrete problems in AI safety. *arXiv preprint arXiv:1606.06565*.
- Russell, S. (2019). *Human Compatible: Artificial Intelligence and the Problem of Control.* Viking.

---

### **Algorithmic Bias**

Algorithmic bias refers to **systematic and unfair discrimination** in AI systems' outputs, arising from biased training data, flawed model design, or inappropriate deployment contexts. Bias can manifest as **representation bias** (underrepresentation of groups in training data), **measurement bias** (proxies that correlate with protected attributes), **aggregation bias** (one-size-fits-all models), and **evaluation bias** (benchmarks that favor certain groups). Addressing algorithmic bias is central to responsible AI.

**Related concepts:** Algorithmic fairness, Bias mitigation, Discrimination, Protected attributes, Disparate impact

**References:**
- Mehrabi, N., Morstatter, F., Saxena, N., Lerman, K., & Galstyan, A. (2021). A survey on bias and fairness in machine learning. *ACM Computing Surveys*, 54(6), 1–35.
- Barocas, S., & Selbst, A. D. (2016). Big data's disparate impact. *California Law Review*, 104(3), 671–732.

---

### **Algorithmic Fairness**

Algorithmic fairness seeks to ensure that AI systems treat individuals and groups **equitably**, without unjust discrimination. Multiple mathematical definitions of fairness exist, including **demographic parity** (equal positive rates across groups), **equalized odds** (equal true/false positive rates), and **individual fairness** (similar individuals receive similar treatment). These definitions are often **mutually incompatible**, making fairness a context-dependent, sociotechnical challenge.

**Related concepts:** Algorithmic bias, Bias mitigation, Protected attributes, Disparate impact, Equal opportunity

**References:**
- Chouldechova, A. (2017). Fair prediction with disparate impact: A study of bias in recidivism prediction instruments. *Big Data*, 5(2), 153–163.
- Dwork, C., Hardt, M., Pitassi, T., Reingold, O., & Zemel, R. (2012). Fairness through awareness. *Proceedings of ITCS 2012*, 214–226.

---

### **Algorithmic Impact Assessment**

An algorithmic impact assessment (AIA) is a **structured process** for evaluating the potential effects of an AI system on individuals, communities, and society **before deployment**. Inspired by environmental impact assessments, AIAs examine risks related to fairness, privacy, safety, and human rights. They typically involve **stakeholder consultation**, **risk scoring**, **mitigation planning**, and **ongoing monitoring**. Several jurisdictions (Canada, EU) have adopted or proposed mandatory AIAs for high-risk AI systems.

**Related concepts:** AI auditing, Risk assessment, AI governance, Stakeholder engagement, Due diligence

**References:**
- Selbst, A. D. (2021). An institutional view of algorithmic impact assessments. *Harvard Journal of Law & Technology*, 35(1), 117–191.
- Reisman, D., Schultz, J., Crawford, K., & Whittaker, M. (2018). *Algorithmic Impact Assessments: A Practical Framework for Public Agency Accountability.* AI Now Institute.

---

### **Algorithmic Transparency**

Algorithmic transparency is the principle that the **logic, data, and decision criteria** of AI systems should be **accessible and understandable** to relevant stakeholders — users, regulators, and affected individuals. It ranges from **process transparency** (how the system was developed) to **outcome transparency** (why a particular decision was made). Transparency is a prerequisite for accountability and is mandated by regulations such as the GDPR's right to explanation.

**Related concepts:** Explainable AI, Right to explanation, Model documentation, Open-source AI, Accountability

**References:**
- Doshi-Velez, F., & Kim, B. (2017). Towards a rigorous science of interpretable machine learning. *arXiv preprint arXiv:1702.08608*.
- Goodman, B., & Flaxman, S. (2017). European Union regulations on algorithmic decision-making and a "right to explanation." *AI Magazine*, 38(3), 50–57.

---

### **Automated Decision-Making**

Automated decision-making (ADM) refers to decisions made **entirely or substantially by algorithmic systems** without human intervention. ADM is used in credit scoring, hiring, criminal justice, welfare allocation, and content moderation. The GDPR grants individuals the **right not to be subject** to purely automated decisions with significant effects, and requires the ability to obtain **human review**. Ensuring fairness, transparency, and contestability of ADM is a core challenge of responsible AI.

**Related concepts:** Human-in-the-loop, Right to explanation, Algorithmic transparency, AI governance, Contestability

**References:**
- Citron, D. K., & Pasquale, F. (2014). The scored society: Due process for automated predictions. *Washington Law Review*, 89(1), 1–33.
- Veale, M., & Zuiderveen Borgesius, F. (2021). Demystifying the Draft EU Artificial Intelligence Act. *Computer Law & Security Review*, 22(4), 1–6.

---

### **Bias Mitigation**

Bias mitigation encompasses **techniques and strategies** for reducing unfair bias in AI systems. Approaches are categorized by their stage in the ML pipeline: **pre-processing** (rebalancing training data, reweighting samples), **in-processing** (adding fairness constraints to the learning algorithm), and **post-processing** (adjusting model outputs to satisfy fairness criteria). Effective bias mitigation requires understanding the **source and nature** of bias and the **context of deployment**.

**Related concepts:** Algorithmic fairness, Algorithmic bias, Fair machine learning, Resampling, Adversarial debiasing

**References:**
- Bellamy, R. K. E., Dey, K., Hind, M., et al. (2019). AI Fairness 360: An extensible toolkit for detecting and mitigating algorithmic bias. *IBM Journal of Research and Development*, 63(4/5), 4:1–4:15.
- Friedler, S. A., Scheidegger, C., Venkatasubramanian, S., et al. (2019). A comparative study of fairness-enhancing interventions in machine learning. *Proceedings of FAT* 2019*, 329–338.

---

### **Counterfactual Explanations**

Counterfactual explanations answer the question: **"What would need to change for a different outcome?"** They provide minimal, actionable changes to input features that would flip an AI system's decision — e.g., "If your income were €5,000 higher, your loan would have been approved." Counterfactuals are considered particularly **user-friendly** because they are intuitive, actionable, and do not require understanding the model's internals.

**Related concepts:** Explainable AI, Interpretability, Right to explanation, Algorithmic recourse, Contrastive explanations

**References:**
- Wachter, S., Mittelstadt, B., & Russell, C. (2017). Counterfactual explanations without opening the black box: Automated decisions and the GDPR. *Harvard Journal of Law & Technology*, 31(2), 841–887.
- Karimi, A.-H., Barthe, G., Balle, B., & Valera, I. (2020). Model-agnostic counterfactual explanations for consequential decisions. *Proceedings of AISTATS 2020*, 895–905.

---

### **Data Protection**

Data protection refers to the **legal and technical frameworks** for safeguarding personal data from unauthorized access, use, and disclosure. In the AI context, data protection governs how training data is collected, processed, and stored. The **General Data Protection Regulation (GDPR)** is the primary framework in Europe, establishing principles of **lawfulness, purpose limitation, data minimization, accuracy, storage limitation**, and **accountability**. AI-specific data protection challenges include training on personal data, re-identification risks, and the right to erasure.

**Related concepts:** GDPR, Privacy, Data minimization, Anonymization, Consent, Personal data

**References:**
- Voigt, P., & von dem Bussche, A. (2017). *The EU General Data Protection Regulation (GDPR): A Practical Guide.* Springer.
- Mantelero, A. (2018). AI and Big Data: A blueprint for a human rights, social and ethical impact assessment. *Computer Law & Security Review*, 34(4), 754–772.

---

### **Differential Privacy**

Differential privacy is a **mathematical framework** that provides formal guarantees about the privacy of individuals in a dataset. A mechanism satisfies differential privacy if its output is **statistically indistinguishable** whether or not any single individual's data is included. It is implemented by adding **calibrated noise** to queries or model parameters. Differential privacy is used in AI for **private model training** (DP-SGD), **data release**, and **federated learning**, enabling useful analysis while protecting individual privacy.

**Related concepts:** Privacy-preserving AI, Federated learning, Data anonymization, Noise injection, DP-SGD

**References:**
- Dwork, C., & Roth, A. (2014). *The Algorithmic Foundations of Differential Privacy.* Foundations and Trends in Theoretical Computer Science, 9(3-4), 211–407.
- Abadi, M., Chu, A., Goodfellow, I., et al. (2016). Deep learning with differential privacy. *Proceedings of CCS 2016*, 308–318.

---

### **EU AI Act**

The EU AI Act is the **first comprehensive legal framework** for AI regulation, adopted by the European Union. It establishes a **risk-based classification** of AI systems: unacceptable risk (banned), high risk (subject to conformity assessments, documentation, and monitoring), limited risk (transparency obligations), and minimal risk (no specific requirements). High-risk categories include AI in biometric identification, critical infrastructure, education, employment, law enforcement, and border control. The Act also addresses **general-purpose AI models** and foundation models.

**Related concepts:** AI governance, AI regulation, Risk classification, Conformity assessment, CE marking for AI

**References:**
- European Commission (2021). *Proposal for a Regulation laying down harmonised rules on artificial intelligence (Artificial Intelligence Act).* COM(2021) 206 final.
- Veale, M., & Zuiderveen Borgesius, F. (2021). Demystifying the Draft EU Artificial Intelligence Act. *Computer Law & Security Review*, 22(4), 1–6.

---

### **Explainable AI (XAI)**

Explainable AI encompasses methods and techniques that make AI systems' **decisions and reasoning processes understandable** to humans. XAI approaches include **intrinsically interpretable models** (decision trees, linear models, rule-based systems) and **post-hoc explanation methods** applied to black-box models (SHAP, LIME, attention visualization, saliency maps). The need for explainability is driven by regulatory requirements (GDPR), ethical considerations, and the practical need for **debugging, trust, and accountability**.

**Related concepts:** Interpretability, Transparency, SHAP, LIME, Counterfactual explanations, Model-agnostic explanations

**References:**
- Arrieta, A. B., Diaz-Rodriguez, N., Del Ser, J., et al. (2020). Explainable Artificial Intelligence (XAI): Concepts, taxonomies, opportunities and challenges toward responsible AI. *Information Fusion*, 58, 82–115.
- Guidotti, R., Monreale, A., Ruggieri, S., et al. (2018). A survey of methods for explaining black box models. *ACM Computing Surveys*, 51(5), 1–42.

---

### **Federated Learning**

Federated learning is a **distributed machine learning approach** where a model is trained across multiple decentralized devices or servers holding local data, **without exchanging raw data**. Each participant trains the model locally and shares only model updates (gradients), which are aggregated centrally. This preserves **data privacy** and **data sovereignty** while enabling collaborative model training. Challenges include **communication efficiency**, **heterogeneous data** (non-IID), **security against adversarial participants**, and **fairness across participants**.

**Related concepts:** Privacy-preserving AI, Differential privacy, Distributed learning, Data sovereignty, Edge AI

**References:**
- McMahan, B., Moore, E., Ramage, D., Hampson, S., & y Arcas, B. A. (2017). Communication-efficient learning of deep networks from decentralized data. *Proceedings of AISTATS 2017*, 1273–1282.
- Kairouz, P., McMahan, H. B., Avent, B., et al. (2021). Advances and open problems in federated learning. *Foundations and Trends in Machine Learning*, 14(1-2), 1–210.

---

### **Human-in-the-Loop**

Human-in-the-loop (HITL) refers to AI system designs that include **meaningful human oversight and intervention** in the decision-making process. HITL can take the form of **human review** of AI recommendations before action, **human approval** for high-stakes decisions, **active learning** (humans labeling uncertain cases), and **override capabilities**. HITL is a key principle of trustworthy AI and is required for high-risk AI systems under the EU AI Act.

**Related concepts:** Human oversight, Human agency, Automated decision-making, Active learning, Human-AI collaboration

**References:**
- Mosqueira-Rey, E., Hernandez-Pereira, E., Alonso-Rios, D., Bobes-Bascaran, J., & Fernandez-Leal, A. (2023). Human-in-the-loop machine learning: A state of the art. *Artificial Intelligence Review*, 56, 3005–3054.
- Amershi, S., Cakmak, M., Knox, W. B., & Kulesza, T. (2014). Power to the people: The role of humans in interactive machine learning. *AI Magazine*, 35(4), 105–120.

---

### **Interpretable Machine Learning**

Interpretable machine learning refers to models whose **internal logic and decision-making** can be directly understood by humans without additional explanation tools. Interpretable models include **linear/logistic regression**, **decision trees**, **rule lists**, **generalized additive models (GAMs)**, and **scoring systems**. The field argues that for high-stakes decisions, interpretable models are preferable to black-box models with post-hoc explanations, as they provide **faithful** rather than approximate explanations.

**Related concepts:** Explainable AI, Transparency, Decision trees, Rule-based models, Model complexity

**References:**
- Rudin, C. (2019). Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead. *Nature Machine Intelligence*, 1(5), 206–215.
- Molnar, C. (2022). *Interpretable Machine Learning: A Guide for Making Black Box Models Explainable.* (2nd ed.). christophm.github.io/interpretable-ml-book.

---

### **Model Cards**

Model cards are **structured documentation** accompanying trained machine learning models, providing essential information about the model's **intended use, performance, limitations, and ethical considerations**. A model card typically includes: model details, intended use cases, factors (demographic, environmental), performance metrics across subgroups, training data, evaluation data, ethical considerations, and caveats. Model cards promote **transparency and informed deployment** of AI systems.

**Related concepts:** AI documentation, Datasheets for datasets, Transparency, AI auditing, Responsible deployment

**References:**
- Mitchell, M., Wu, S., Zaldivar, A., et al. (2019). Model cards for model reporting. *Proceedings of FAT* 2019*, 220–229.
- Gebru, T., Morgenstern, J., Vecchione, B., et al. (2021). Datasheets for datasets. *Communications of the ACM*, 64(12), 86–92.

---

### **Privacy-Preserving AI**

Privacy-preserving AI encompasses techniques that enable **training and deploying AI models** while protecting the privacy of individuals in the training data. Key techniques include **differential privacy** (adding noise to guarantee indistinguishability), **federated learning** (training without centralizing data), **secure multi-party computation** (computing on encrypted data), and **homomorphic encryption** (performing operations on ciphertext). These techniques are essential for AI applications in sensitive domains such as healthcare, finance, and government.

**Related concepts:** Differential privacy, Federated learning, Homomorphic encryption, Secure computation, Data protection

**References:**
- Boulemtafes, A., Derhab, A., & Challal, Y. (2020). A review of privacy-preserving techniques for deep learning. *Neurocomputing*, 384, 21–45.
- Li, T., Sahu, A. K., Talwalkar, A., & Smith, V. (2020). Federated learning: Challenges, methods, and future directions. *IEEE Signal Processing Magazine*, 37(3), 50–60.

---

### **Responsible Innovation**

Responsible innovation (RI) is a **governance framework** emphasizing that innovation processes should be guided by **anticipation** (foreseeing impacts), **reflexivity** (questioning assumptions), **inclusion** (engaging stakeholders), and **responsiveness** (adapting to emerging concerns). In the AI context, RI calls for proactive consideration of societal impacts throughout the AI development lifecycle, from research to deployment. It originated in science and technology studies and has been adopted as a principle in EU research funding (Horizon Europe).

**Related concepts:** AI governance, Stakeholder engagement, Ethics by design, Anticipatory governance, Societal impact

**References:**
- Stilgoe, J., Owen, R., & Macnaghten, P. (2013). Developing a framework for responsible innovation. *Research Policy*, 42(9), 1568–1580.
- von Schomberg, R. (2013). A vision of responsible research and innovation. In R. Owen, J. Bessant, & M. Heintz (Eds.), *Responsible Innovation* (pp. 51–74). Wiley.

---

### **SHAP and LIME**

SHAP (SHapley Additive exPlanations) and LIME (Local Interpretable Model-agnostic Explanations) are two widely used **post-hoc explanation methods** for machine learning models. LIME explains individual predictions by fitting a **local interpretable model** (e.g., linear regression) in the neighborhood of the instance. SHAP uses **Shapley values** from cooperative game theory to assign each feature a contribution to the prediction, providing **consistency and local accuracy** guarantees. Both methods are **model-agnostic** and can be applied to any classifier or regressor.

**Related concepts:** Explainable AI, Feature importance, Model-agnostic explanations, Post-hoc explanations, Interpretability

**References:**
- Ribeiro, M. T., Singh, S., & Guestrin, C. (2016). "Why should I trust you?" Explaining the predictions of any classifier. *Proceedings of KDD 2016*, 1135–1144.
- Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. *Advances in NeurIPS*, 30, 4765–4774.

---

### **Trustworthy AI**

Trustworthy AI is an AI system that is **lawful** (complies with applicable laws), **ethical** (adheres to ethical principles), and **robust** (performs reliably from a technical and social perspective). The EU's High-Level Expert Group on AI identified seven key requirements: human agency and oversight, technical robustness and safety, privacy and data governance, transparency, diversity/non-discrimination/fairness, societal and environmental well-being, and accountability. Trustworthy AI serves as the **overarching framework** integrating all aspects of responsible AI.

**Related concepts:** Responsible AI, AI ethics, AI governance, EU AI Act, Robustness, Fairness, Transparency

**References:**
- High-Level Expert Group on AI (2019). *Ethics Guidelines for Trustworthy AI.* European Commission.
- Floridi, L., Cowls, J., Beltrametti, M., et al. (2018). AI4People — An ethical framework for a good AI society: Opportunities, risks, principles, and recommendations. *Minds and Machines*, 28(4), 689–707.

---

### **Value-Sensitive Design**

Value-sensitive design (VSD) is a **design methodology** that accounts for **human values** — such as privacy, fairness, autonomy, trust, and well-being — throughout the technology design process. VSD uses **conceptual investigations** (identifying stakeholders and values), **empirical investigations** (studying how technology affects values), and **technical investigations** (designing systems that support identified values). In AI, VSD is applied to ensure that algorithmic systems align with the values of all affected stakeholders.

**Related concepts:** Ethics by design, Human-centered design, AI alignment, Participatory design, Stakeholder analysis

**References:**
- Friedman, B., Hendry, D. G., & Borning, A. (2017). A survey of value sensitive design methods. *Foundations and Trends in Human-Computer Interaction*, 11(2), 63–125.
- Friedman, B., & Hendry, D. G. (2019). *Value Sensitive Design: Shaping Technology with Moral Imagination.* MIT Press.

---

## Summary Statistics

| **Category** | **Count** | **Examples** |
|---|---|---|
| Explainability & Interpretability | 5 | XAI, SHAP & LIME, Counterfactual Explanations, Interpretable ML, Model Cards |
| Fairness & Bias | 3 | Algorithmic Fairness, Algorithmic Bias, Bias Mitigation |
| Governance & Regulation | 4 | AI Governance, EU AI Act, Algorithmic Impact Assessment, Automated Decision-Making |
| Privacy & Security | 4 | Data Protection, Differential Privacy, Federated Learning, Privacy-Preserving AI |
| Trust, Safety & Robustness | 3 | Trustworthy AI, AI Safety, Adversarial Robustness |
| Ethics & Society | 3 | Responsible Innovation, Value-Sensitive Design, Accountability in AI |
| Oversight & Documentation | 3 | AI Auditing, Algorithmic Transparency, Human-in-the-Loop |
| **Total** | **25** | |
