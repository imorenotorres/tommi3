# Glossary of Health & Wellbeing Systems Concepts

This glossary provides **comprehensive definitions** of key concepts in Health & Wellbeing Systems (digital health, AI diagnostics, wearable monitoring, precision medicine), curated for the UNINOVIS alliance. Each entry includes related concepts, academic references, and context for understanding. Contributions and corrections are welcome.

---

## Glossary Entries

---

### **AI-Assisted Diagnosis**

AI-assisted diagnosis uses machine learning and deep learning models to **support clinical decision-making** by analyzing patient data — medical images, lab results, clinical notes — and suggesting diagnoses or flagging abnormalities. These systems serve as **decision support tools** that augment clinician expertise rather than replace it. Performance has reached or exceeded human experts in specific tasks such as **diabetic retinopathy detection**, **skin cancer classification**, and **chest X-ray interpretation**.

**Related concepts:** Clinical decision support, Computer-aided detection, Medical image analysis, Deep learning, Diagnostic accuracy

**References:**
- Topol, E. J. (2019). High-performance medicine: The convergence of human and artificial intelligence. *Nature Medicine*, 25(1), 44–56.
- Rajpurkar, P., Chen, E., Banerjee, O., & Topol, E. J. (2022). AI in health and medicine. *Nature Medicine*, 28(1), 31–38.

---

### **Biomedical Signal Processing**

Biomedical signal processing applies **signal analysis techniques** to physiological signals such as electrocardiograms (ECG), electroencephalograms (EEG), electromyograms (EMG), and photoplethysmography (PPG). Modern approaches use **deep learning** for automated feature extraction and classification, enabling applications in **arrhythmia detection**, **seizure prediction**, **sleep staging**, and **emotion recognition**. Wearable sensors have expanded signal processing from clinical to ambulatory settings.

**Related concepts:** ECG analysis, EEG analysis, Wearable sensors, Feature extraction, Time series classification

**References:**
- Sopic, D., Aminifar, A., & Atienza, D. (2018). Real-time event-driven classification technique for early detection and prevention of myocardial infarction on wearable systems. *IEEE Transactions on Biomedical Circuits and Systems*, 12(5), 982–992.
- Craik, A., He, Y., & Bhatt, J. L. (2019). Deep learning for electroencephalogram (EEG) classification tasks: A review. *Journal of Neural Engineering*, 16(3), 031001.

---

### **Clinical Decision Support Systems**

Clinical decision support systems (CDSS) are **health information technology systems** that provide clinicians with knowledge, patient data, and analytics to enhance decision-making at the point of care. Modern AI-powered CDSS use **machine learning models** trained on electronic health records to generate alerts, diagnostic suggestions, treatment recommendations, and risk predictions. Key challenges include **alert fatigue**, **integration with clinical workflows**, **validation**, and **liability**.

**Related concepts:** AI-assisted diagnosis, Electronic health records, Evidence-based medicine, Clinical guidelines, Alert fatigue

**References:**
- Sutton, R. T., Pincock, D., Baumgart, D. C., et al. (2020). An overview of clinical decision support systems: Benefits, risks, and strategies for success. *NPJ Digital Medicine*, 3, 17.
- Shortliffe, E. H., & Sepulveda, M. J. (2018). Clinical decision support in the era of artificial intelligence. *JAMA*, 320(21), 2199–2200.

---

### **Clinical NLP**

Clinical NLP applies **natural language processing techniques** to clinical text — discharge summaries, radiology reports, clinical notes, pathology reports — to extract structured information from unstructured narrative. Tasks include **named entity recognition** (medications, diagnoses, procedures), **relation extraction**, **negation detection**, **temporal reasoning**, and **de-identification**. Clinical NLP enables secondary use of clinical data for research, quality improvement, and clinical decision support.

**Related concepts:** Biomedical text mining, Electronic health records, Information extraction, De-identification, Medical ontologies

**References:**
- Wang, Y., Wang, L., Rastegar-Mojarad, M., et al. (2018). Clinical information extraction applications: A literature review. *Journal of Biomedical Informatics*, 77, 34–49.
- Wu, S., Roberts, K., Datta, S., et al. (2020). Deep learning in clinical natural language processing: A methodical review. *Journal of the American Medical Informatics Association*, 27(3), 457–470.

---

### **Computer-Aided Detection**

Computer-aided detection (CADe) systems use **image analysis algorithms** to identify potentially abnormal regions in medical images and flag them for radiologist review. Unlike computer-aided diagnosis (CADx), which suggests specific diagnoses, CADe focuses on **detection and localization** of lesions. Applications include **mammography screening**, **lung nodule detection** in CT scans, and **polyp detection** in colonoscopy. Deep learning has substantially improved CADe sensitivity while reducing false positives.

**Related concepts:** Medical image analysis, AI-assisted diagnosis, Radiology AI, Convolutional neural networks, Sensitivity/specificity

**References:**
- Litjens, G., Kooi, T., Bejnordi, B. E., et al. (2017). A survey on deep learning in medical image analysis. *Medical Image Analysis*, 42, 60–88.
- McKinney, S. M., Sieniek, M., Godbole, V., et al. (2020). International evaluation of an AI system for breast cancer screening. *Nature*, 577(7788), 89–94.

---

### **Digital Biomarkers**

Digital biomarkers are **quantifiable physiological and behavioral measures** collected through digital devices (smartphones, wearables, sensors) that serve as indicators of health states, disease progression, or treatment response. Examples include **gait speed** (neurological conditions), **voice features** (depression), **typing patterns** (cognitive decline), and **heart rate variability** (cardiovascular health). Digital biomarkers enable **continuous, objective, and remote** health monitoring outside clinical settings.

**Related concepts:** Wearable health technology, Remote patient monitoring, Biomedical signal processing, Phenotyping, mHealth

**References:**
- Coravos, A., Khozin, S., & Mandl, K. D. (2019). Developing and adopting safe and effective digital biomarkers to improve patient outcomes. *NPJ Digital Medicine*, 2, 14.
- Dorsey, E. R., Papapetropoulos, S., Xiong, M., & Kieburtz, K. (2017). The first frontier: Digital biomarkers for neurodegenerative disorders. *Digital Biomarkers*, 1(1), 6–13.

---

### **Digital Health**

Digital health is the broad field encompassing the use of **digital technologies** — mobile health (mHealth), health information technology, wearable devices, telehealth, and AI — to improve health outcomes, healthcare delivery, and public health. It spans the continuum from **wellness and prevention** to **clinical care and population health**. Digital health is characterized by the convergence of healthcare with data science, connectivity, and consumer technology.

**Related concepts:** eHealth, mHealth, Telemedicine, Health informatics, Health IT, Digital therapeutics

**References:**
- Steinhubl, S. R., Muse, E. D., & Topol, E. J. (2015). The emerging field of mobile health. *Science Translational Medicine*, 7(283), 283rv3.
- WHO (2021). *Global Strategy on Digital Health 2020-2025.* World Health Organization.

---

### **Digital Therapeutics**

Digital therapeutics (DTx) are **evidence-based therapeutic interventions** delivered through software programs to prevent, manage, or treat medical disorders. Unlike general wellness apps, DTx are **clinically validated** through randomized controlled trials and may require regulatory approval (e.g., FDA clearance). Applications include cognitive behavioral therapy for insomnia, substance use disorders, diabetes management, and ADHD. DTx can be used independently or in conjunction with medications and other therapies.

**Related concepts:** mHealth, Behavior change technology, Clinical validation, Health apps, Prescription digital therapeutics

**References:**
- Sverdlov, O., van Dam, J., Hannesdottir, K., & Arnold, S. E. (2018). Digital therapeutics: An integral component of digital innovation in drug development. *Clinical Pharmacology & Therapeutics*, 104(1), 72–80.
- Dang, A., Arora, D., & Rane, P. (2020). Role of digital therapeutics and the changing future of healthcare. *Journal of Family Medicine and Primary Care*, 9(5), 2207–2213.

---

### **Electronic Health Records**

Electronic health records (EHRs) are **digital versions of patients' medical histories** maintained by healthcare providers, containing diagnoses, medications, treatment plans, immunization records, lab results, and imaging data. EHRs enable **data-driven healthcare** by providing structured and unstructured data for clinical decision support, quality measurement, and research. AI applications on EHR data include **predictive modeling** (readmission, deterioration), **phenotyping**, and **clinical NLP**.

**Related concepts:** Health informatics, Clinical data, Interoperability, FHIR, HL7, Data quality

**References:**
- Rajkomar, A., Oren, E., Chen, K., et al. (2018). Scalable and accurate deep learning with electronic health records. *NPJ Digital Medicine*, 1, 18.
- Adler-Milstein, J., & Jha, A. K. (2017). HITECH Act drove large gains in hospital electronic health record adoption. *Health Affairs*, 36(8), 1416–1422.

---

### **Federated Learning in Healthcare**

Federated learning in healthcare enables **collaborative model training** across multiple hospitals or institutions without sharing patient data. Each institution trains models locally and shares only model updates, preserving **patient privacy** and complying with data protection regulations. Applications include multi-institutional **tumor segmentation**, **mortality prediction**, and **drug discovery**. Healthcare-specific challenges include **data heterogeneity** across institutions, **regulatory compliance**, and **model validation**.

**Related concepts:** Privacy-preserving AI, Differential privacy, Multi-site studies, Data governance, GDPR

**References:**
- Rieke, N., Hancox, J., Li, W., et al. (2020). The future of digital health with federated learning. *NPJ Digital Medicine*, 3, 119.
- Sheller, M. J., Edwards, B., Reina, G. A., et al. (2020). Federated learning in medicine: Facilitating multi-institutional collaborations without sharing patient data. *Scientific Reports*, 10, 12598.

---

### **Health Informatics**

Health informatics is the **interdisciplinary field** that studies the effective use of data, information, and knowledge to improve healthcare delivery, public health, and biomedical research. It encompasses **clinical informatics**, **bioinformatics**, **public health informatics**, and **consumer health informatics**. Health informatics professionals design and evaluate health information systems, develop standards for data exchange, and apply data science methods to health data.

**Related concepts:** Biomedical informatics, Clinical informatics, Health IT, EHR, Data standards, Interoperability

**References:**
- Hersh, W. R. (2009). A stimulus to define informatics and health information technology. *BMC Medical Informatics and Decision Making*, 9, 24.
- Shortliffe, E. H., & Cimino, J. J. (Eds.) (2014). *Biomedical Informatics: Computer Applications in Health Care and Biomedicine* (4th ed.). Springer.

---

### **Medical Image Analysis**

Medical image analysis uses **computational methods** to extract clinically relevant information from medical images — X-rays, CT scans, MRIs, ultrasound, histopathology slides, and retinal images. Deep learning, particularly **convolutional neural networks**, has achieved breakthrough performance in tasks such as **tumor detection**, **organ segmentation**, **disease grading**, and **image registration**. The field addresses challenges including **limited labeled data**, **class imbalance**, **domain shift**, and **clinical validation**.

**Related concepts:** Computer-aided detection, Radiology AI, Pathology AI, Segmentation, Classification, Transfer learning

**References:**
- Litjens, G., Kooi, T., Bejnordi, B. E., et al. (2017). A survey on deep learning in medical image analysis. *Medical Image Analysis*, 42, 60–88.
- Esteva, A., Robicquet, A., Ramsundar, B., et al. (2019). A guide to deep learning in healthcare. *Nature Medicine*, 25(1), 24–29.

---

### **Mental Health Technology**

Mental health technology encompasses **digital tools and AI systems** designed to support the prevention, detection, and treatment of mental health conditions. Applications include **AI-based screening** (detecting depression or anxiety from text, voice, or behavior), **digital cognitive behavioral therapy (CBT)**, **chatbot-based counseling**, **mood tracking apps**, and **crisis intervention tools**. Key challenges include **clinical validation**, **user engagement**, **privacy**, and **equity of access**.

**Related concepts:** Digital therapeutics, mHealth, Chatbots for health, Sentiment analysis, Behavioral monitoring

**References:**
- Torous, J., Buber, M. E., & Onnela, J.-P. (2021). New dimensions and new tools to realize the potential of digital mental health. *World Psychiatry*, 20(2), 218–224.
- Abd-Alrazaq, A. A., Rababeh, A., Alajlani, M., et al. (2020). Effectiveness and safety of using chatbots to improve mental health: Systematic review and meta-analysis. *Journal of Medical Internet Research*, 22(7), e16021.

---

### **mHealth (Mobile Health)**

mHealth refers to the use of **mobile devices** — smartphones, tablets, and wearable sensors — for health-related purposes, including **health monitoring**, **disease management**, **health education**, and **clinical data collection**. mHealth apps can track physical activity, medication adherence, vital signs, and symptoms. The field leverages smartphone capabilities (GPS, accelerometer, camera, microphone) as health sensing tools, enabling **scalable, low-cost** health interventions in both high- and low-resource settings.

**Related concepts:** Digital health, Wearable technology, Health apps, Point-of-care testing, Telemedicine

**References:**
- Piwek, L., Ellis, D. A., Andrews, S., & Joinson, A. (2016). The rise of consumer health wearables: Promises and barriers. *PLoS Medicine*, 13(2), e1001953.
- Steinhubl, S. R., Muse, E. D., & Topol, E. J. (2015). The emerging field of mobile health. *Science Translational Medicine*, 7(283), 283rv3.

---

### **Personalized Medicine**

Personalized medicine (also precision medicine) tailors **medical treatment to individual patient characteristics** — genomic profile, biomarkers, lifestyle, and environment — rather than applying population-average approaches. AI and machine learning enable personalized medicine by identifying **patient subgroups**, predicting **treatment response**, optimizing **drug dosing**, and discovering **biomarkers** from multi-omics data. The field is transforming oncology, pharmacology, and chronic disease management.

**Related concepts:** Precision medicine, Genomics, Pharmacogenomics, Biomarkers, Patient stratification, Companion diagnostics

**References:**
- Collins, F. S., & Varmus, H. (2015). A new initiative on precision medicine. *New England Journal of Medicine*, 372(9), 793–795.
- Miotto, R., Wang, F., Wang, S., Jiang, X., & Dudley, J. T. (2018). Deep learning for healthcare: Review, opportunities and challenges. *Briefings in Bioinformatics*, 19(6), 1236–1246.

---

### **Predictive Analytics in Healthcare**

Predictive analytics in healthcare uses **statistical and machine learning methods** to forecast clinical events — hospital readmission, patient deterioration, disease onset, treatment outcomes — from historical patient data. Models range from **logistic regression** to **deep learning** on multimodal data (EHR, imaging, genomics). Applications include **early warning scores**, **risk stratification**, **resource allocation**, and **clinical trial optimization**. Validation and fairness across patient subgroups are critical challenges.

**Related concepts:** Clinical decision support, Electronic health records, Risk scoring, Machine learning, Prognostic models

**References:**
- Rajkomar, A., Dean, J., & Kohane, I. (2019). Machine learning in medicine. *New England Journal of Medicine*, 380(14), 1347–1358.
- Obermeyer, Z., & Emanuel, E. J. (2016). Predicting the future — Big data, machine learning, and clinical medicine. *New England Journal of Medicine*, 375(13), 1216–1219.

---

### **Remote Patient Monitoring**

Remote patient monitoring (RPM) uses **digital technologies** to collect patient health data outside of clinical settings and transmit it to healthcare providers for assessment. RPM devices include **blood pressure monitors**, **glucose meters**, **pulse oximeters**, **weight scales**, and **wearable sensors**. AI enhances RPM by enabling **automated anomaly detection**, **trend analysis**, and **predictive alerts**. RPM has expanded significantly since the COVID-19 pandemic, demonstrating benefits for chronic disease management and post-surgical care.

**Related concepts:** Telemedicine, Wearable health technology, Digital biomarkers, IoT in healthcare, Chronic disease management

**References:**
- Noah, B., Keller, M. S., Mosadeghi, S., et al. (2018). Impact of remote patient monitoring on clinical outcomes: An updated meta-analysis of randomized controlled trials. *NPJ Digital Medicine*, 1, 20172.
- Vegesna, A., Tran, M., Zheng, M., & Yu, H. (2017). Remote patient monitoring via non-invasive digital technologies: A systematic review. *Telemedicine and e-Health*, 23(1), 3–17.

---

### **Smart Sensors for Health**

Smart sensors for health are **intelligent sensing devices** that combine physical sensors with embedded processing and connectivity to continuously monitor physiological parameters. They include **biosensors** (measuring biochemical markers), **inertial sensors** (motion and activity), **optical sensors** (heart rate, SpO2), and **environmental sensors** (temperature, humidity). Smart sensors enable real-time health monitoring in wearables, smart textiles, and ambient environments, forming the sensing layer of digital health ecosystems.

**Related concepts:** Wearable technology, IoT, Biomedical signal processing, Edge AI, Biosensors, Ambient sensing

**References:**
- Dias, D., & Paulo Silva Cunha, J. (2018). Wearable health devices — Vital sign monitoring, systems and technologies. *Sensors*, 18(8), 2414.
- Kim, J., Campbell, A. S., de Avila, B. E.-F., & Wang, J. (2019). Wearable biosensors for healthcare monitoring. *Nature Biotechnology*, 37(4), 389–406.

---

### **Telemedicine**

Telemedicine is the delivery of **healthcare services at a distance** using telecommunications technology. It encompasses **synchronous** (real-time video consultations), **asynchronous** (store-and-forward transmission of images and data), and **remote monitoring** modalities. Telemedicine improves **access to care** for rural and underserved populations, reduces costs, and enables specialist consultations across geographic boundaries. AI enhances telemedicine through automated triage, diagnostic support, and remote monitoring analytics.

**Related concepts:** Telehealth, Remote patient monitoring, Virtual care, Digital health, mHealth

**References:**
- Dorsey, E. R., & Topol, E. J. (2016). State of telehealth. *New England Journal of Medicine*, 375(2), 154–161.
- Hollander, J. E., & Carr, B. G. (2020). Virtually perfect? Telemedicine for COVID-19. *New England Journal of Medicine*, 382(18), 1679–1681.

---

### **Wearable Health Technology**

Wearable health technology encompasses **body-worn electronic devices** that continuously or periodically monitor physiological parameters — heart rate, physical activity, sleep, skin temperature, blood oxygen — and transmit data for analysis. Consumer wearables (smartwatches, fitness trackers) coexist with medical-grade devices (continuous glucose monitors, Holter monitors). AI algorithms applied to wearable data enable **atrial fibrillation detection**, **fall detection**, **stress assessment**, and **activity recognition**.

**Related concepts:** mHealth, Smart sensors, Digital biomarkers, Biosensors, Activity recognition, Fitness tracking

**References:**
- Dunn, J., Runge, R., & Snyder, M. (2018). Wearables and the medical revolution. *Personalized Medicine*, 15(5), 429–448.
- Perez, M. V., Mahaffey, K. W., Hedlin, H., et al. (2019). Large-scale assessment of a smartwatch to identify atrial fibrillation. *New England Journal of Medicine*, 381(20), 1909–1917.

---

### **Well-being AI**

Well-being AI refers to AI systems designed to **promote and monitor human well-being** across physical, mental, and social dimensions. Applications include **personalized health coaching**, **stress management**, **social connectedness tools**, **workplace well-being analytics**, and **positive psychology interventions**. The field draws on **affective computing** (emotion recognition), **behavioral modeling**, and **recommendation systems** to deliver timely, personalized well-being interventions.

**Related concepts:** Digital wellness, Affective computing, Health coaching, Positive psychology, Behavioral analytics

**References:**
- Calvo, R. A., & Peters, D. (2014). *Positive Computing: Technology for Wellbeing and Human Potential.* MIT Press.
- De Choudhury, M., Counts, S., & Horvitz, E. (2013). Social media as a measurement tool of depression in populations. *Proceedings of WebSci 2013*, 47–56.

---

### **Clinical Trials and AI**

AI is transforming clinical trials by enabling **patient recruitment optimization**, **protocol design**, **site selection**, **adverse event prediction**, and **real-world evidence generation**. Machine learning models can identify eligible patients from EHRs, predict enrollment rates, detect safety signals earlier, and support **adaptive trial designs**. AI also enables **synthetic control arms** and **digital endpoints** from wearable data, potentially reducing trial duration and cost.

**Related concepts:** Predictive analytics, Electronic health records, Digital biomarkers, Drug development, Real-world evidence

**References:**
- Harrer, S., Shah, P., Antony, B., & Hu, J. (2019). Artificial intelligence for clinical trial design. *Trends in Pharmacological Sciences*, 40(8), 577–591.
- Fogel, D. B. (2018). Factors associated with clinical trials that fail and opportunities for improving the likelihood of success: A review. *Contemporary Clinical Trials Communications*, 11, 156–164.

---

### **Interoperability in Health IT**

Interoperability in health IT refers to the ability of different health information systems to **exchange, interpret, and use health data** seamlessly. Standards such as **HL7 FHIR** (Fast Healthcare Interoperability Resources), **DICOM** (medical imaging), and **SNOMED CT** (clinical terminology) enable interoperability. Effective interoperability is essential for **care coordination**, **public health surveillance**, **clinical research**, and **AI model development** across institutions. Achieving true interoperability remains one of health IT's greatest challenges.

**Related concepts:** Health informatics, Electronic health records, FHIR, HL7, Data standards, Data governance

**References:**
- Lehne, M., Sass, J., Essenwanger, A., Schepers, J., & Thun, S. (2019). Why digital medicine depends on interoperability. *NPJ Digital Medicine*, 2, 79.
- Bender, D., & Sartipi, K. (2013). HL7 FHIR: An agile and RESTful approach to healthcare information exchange. *Proceedings of CBMS 2013*, 326–331.

---

## Summary Statistics

| **Category** | **Count** | **Examples** |
|---|---|---|
| AI Diagnostics & Imaging | 4 | AI-Assisted Diagnosis, Computer-Aided Detection, Medical Image Analysis, Clinical Decision Support |
| Digital Health Foundations | 4 | Digital Health, Electronic Health Records, Health Informatics, Interoperability |
| Monitoring & Sensing | 4 | Wearable Health Technology, Remote Patient Monitoring, Smart Sensors, Digital Biomarkers |
| Precision & Predictive | 3 | Personalized Medicine, Predictive Analytics, Clinical Trials and AI |
| Mental Health & Wellbeing | 3 | Mental Health Technology, Well-being AI, Digital Therapeutics |
| Data & Privacy | 2 | Federated Learning in Healthcare, Clinical NLP |
| Care Delivery | 2 | Telemedicine, mHealth |
| Signal & Data Processing | 3 | Biomedical Signal Processing, Clinical NLP, Predictive Analytics |
| **Total** | **25** | |
