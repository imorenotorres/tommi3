# Glossary of Logistics & Cybersecurity Concepts

This glossary provides **comprehensive definitions** of key concepts in Logistics & Cybersecurity (logistics systems, cybersecurity, secure supply chains, digital infrastructure), curated for the UNINOVIS alliance. Each entry includes related concepts, academic references, and context for understanding. Contributions and corrections are welcome.

---

## Glossary Entries

---

### **Access Control**

Access control is the **selective restriction of access** to resources — systems, data, facilities, networks — based on identity, role, or policy. Models include **discretionary** (DAC, owner-defined), **mandatory** (MAC, system-enforced classifications), **role-based** (RBAC, access by job function), and **attribute-based** (ABAC, context-dependent rules). In logistics, access control protects **warehouse management systems**, **transportation management platforms**, **tracking data**, and **operational technology** from unauthorized use.

**Related concepts:** Authentication, Authorization, RBAC, Identity management, Zero trust, Least privilege

**References:**
- Sandhu, R., Coyne, E. J., Feinstein, H. L., & Youman, C. E. (1996). Role-based access control models. *IEEE Computer*, 29(2), 38–47.
- Hu, V. C., Ferraiolo, D., Kuhn, R., et al. (2014). *Guide to Attribute Based Access Control (ABAC) Definition and Considerations.* NIST Special Publication 800-162.

---

### **Anomaly Detection**

Anomaly detection identifies **patterns in data that deviate significantly** from expected behavior, indicating potential security threats, system faults, or fraud. Techniques include **statistical methods** (z-score, Grubbs' test), **machine learning** (isolation forest, one-class SVM, autoencoders), and **deep learning** (LSTM-based sequence anomaly detection). In logistics cybersecurity, anomaly detection monitors **network traffic**, **system logs**, **supply chain transactions**, and **IoT sensor data** for signs of intrusion, tampering, or operational failure.

**Related concepts:** Intrusion detection, Machine learning, Outlier detection, Network monitoring, Behavioral analysis

**References:**
- Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly detection: A survey. *ACM Computing Surveys*, 41(3), 1–58.
- Chalapathy, R., & Chawla, S. (2019). Deep learning for anomaly detection: A survey. *arXiv preprint arXiv:1901.03407*.

---

### **Blockchain for Supply Chain**

Blockchain for supply chain applies **distributed ledger technology** to create **immutable, transparent records** of transactions, product movements, and certifications across the supply chain. It enhances **traceability** (tracking product provenance), **authenticity verification** (combating counterfeiting), **compliance documentation**, and **multi-party trust** without central intermediaries. Smart contracts automate supply chain processes such as payment upon delivery confirmation. Challenges include **scalability**, **energy consumption**, **interoperability**, and **data privacy**.

**Related concepts:** Distributed ledger, Smart contracts, Traceability, Supply chain transparency, Provenance, Counterfeiting prevention

**References:**
- Kshetri, N. (2018). Blockchain's roles in meeting key supply chain management objectives. *International Journal of Information Management*, 39, 80–89.
- Saberi, S., Kouhizadeh, M., Sarkis, J., & Shen, L. (2019). Blockchain technology and its relationships to sustainable supply chain management. *International Journal of Production Research*, 57(7), 2117–2135.

---

### **Cyber-Physical Systems Security**

Cyber-physical systems (CPS) security addresses the **protection of systems** that integrate computational and physical components — industrial control systems, autonomous vehicles, smart grids, and automated logistics — from cyber attacks that can cause **physical consequences**. CPS security must protect both **IT** (information technology) and **OT** (operational technology) layers, addressing threats such as **sensor spoofing**, **actuator manipulation**, **firmware attacks**, and **communication interception**. The convergence of IT and OT in logistics creates new attack surfaces.

**Related concepts:** Industrial control systems, SCADA, OT security, IoT security, Critical infrastructure, Resilience

**References:**
- Humayed, A., Lin, J., Li, F., & Luo, B. (2017). Cyber-physical systems security — A survey. *IEEE Internet of Things Journal*, 4(6), 1802–1831.
- Cardenas, A. A., Amin, S., & Sastry, S. (2008). Secure control: Towards survivable cyber-physical systems. *Proceedings of ICDCS 2008 Workshops*, 495–500.

---

### **Cyber Threat Intelligence**

Cyber threat intelligence (CTI) is the **collection, analysis, and dissemination of information** about current and potential cyber threats — threat actors, their tactics, techniques, and procedures (TTPs), indicators of compromise (IoCs), and vulnerabilities. CTI enables **proactive defense** by informing security decisions, threat hunting, and incident response. Sources include **open-source intelligence (OSINT)**, **information sharing communities** (ISACs), **dark web monitoring**, and **vendor threat feeds**.

**Related concepts:** Threat modeling, Indicators of compromise, MITRE ATT&CK, Threat hunting, Information sharing, OSINT

**References:**
- Tounsi, W., & Rais, H. (2018). A survey on technical threat intelligence in the age of sophisticated cyber attacks. *Computers & Security*, 72, 212–233.
- Liao, X., Yuan, K., Wang, X., et al. (2016). Acing the IOC game: Toward automatic discovery and analysis of open-source cyber threat intelligence. *Proceedings of CCS 2016*, 755–766.

---

### **Data Loss Prevention**

Data loss prevention (DLP) encompasses **strategies, tools, and policies** to prevent sensitive data from being lost, stolen, or exposed through unauthorized access, exfiltration, or accidental disclosure. DLP systems monitor **data at rest** (stored), **data in motion** (network traffic), and **data in use** (endpoint activity), applying rules to detect and block sensitive data transfers. In logistics, DLP protects **customer data**, **trade secrets**, **pricing information**, **route data**, and **supplier contracts**.

**Related concepts:** Data protection, Encryption, Endpoint security, Network monitoring, Classification, Compliance

**References:**
- Alneyadi, S., Sithirasenan, E., & Muthukkumarasamy, V. (2016). A survey on data leakage prevention systems. *Journal of Network and Computer Applications*, 62, 137–152.
- Shabtai, A., Elovici, Y., & Rokach, L. (2012). *A Survey of Data Leakage Detection and Prevention Solutions.* Springer.

---

### **Digital Forensics**

Digital forensics is the **science of identifying, preserving, analyzing, and presenting digital evidence** from computers, networks, mobile devices, and cloud systems in a manner that is **legally admissible**. It supports **incident response**, **criminal investigations**, **regulatory compliance**, and **litigation**. Key areas include **network forensics** (analyzing traffic captures), **disk forensics** (recovering deleted data), **memory forensics** (analyzing RAM), and **cloud forensics**. In logistics, digital forensics investigates supply chain fraud, data breaches, and system compromises.

**Related concepts:** Incident response, Evidence preservation, Chain of custody, Malware analysis, Log analysis

**References:**
- Casey, E. (2011). *Digital Evidence and Computer Crime: Forensic Science, Computers, and the Internet* (3rd ed.). Academic Press.
- Garfinkel, S. L. (2010). Digital forensics research: The next 10 years. *Digital Investigation*, 7, S64–S73.

---

### **Encryption**

Encryption is the process of **converting plaintext data into ciphertext** using mathematical algorithms and keys, making it unreadable to unauthorized parties. **Symmetric encryption** (AES) uses the same key for encryption and decryption; **asymmetric encryption** (RSA, ECC) uses public-private key pairs. Encryption protects **data at rest** (disk encryption), **data in transit** (TLS/SSL), and **data in use** (homomorphic encryption). In logistics, encryption secures **shipment data**, **customer information**, **communications**, and **IoT device telemetry**.

**Related concepts:** Cryptography, Public key infrastructure, TLS/SSL, Key management, Data protection, AES

**References:**
- Katz, J., & Lindell, Y. (2020). *Introduction to Modern Cryptography* (3rd ed.). Chapman & Hall/CRC.
- Stallings, W. (2017). *Cryptography and Network Security: Principles and Practice* (7th ed.). Pearson.

---

### **Firewall and IDS/IPS**

Firewalls, intrusion detection systems (IDS), and intrusion prevention systems (IPS) are **network security devices** that monitor and control traffic based on security rules. Firewalls filter traffic by source, destination, port, and protocol. IDS **detects** malicious activity through signature matching or anomaly detection and generates alerts. IPS **actively blocks** detected threats. Modern **next-generation firewalls (NGFW)** integrate deep packet inspection, application awareness, and threat intelligence. These systems are the first line of defense for logistics network infrastructure.

**Related concepts:** Network security, Deep packet inspection, Anomaly detection, Signature-based detection, Network segmentation

**References:**
- Scarfone, K., & Mell, P. (2007). *Guide to Intrusion Detection and Prevention Systems (IDPS).* NIST Special Publication 800-94.
- Paxson, V. (1999). Bro: A system for detecting network intruders in real-time. *Computer Networks*, 31(23-24), 2435–2463.

---

### **Incident Response**

Incident response (IR) is the **organized approach** to detecting, containing, eradicating, and recovering from cybersecurity incidents — data breaches, ransomware attacks, insider threats, DDoS attacks. IR frameworks (NIST, SANS) define phases: **preparation**, **detection and analysis**, **containment**, **eradication**, **recovery**, and **post-incident review**. In logistics, rapid incident response is critical because supply chain disruptions can cascade across organizations, causing **operational downtime**, **financial loss**, and **reputational damage**.

**Related concepts:** Digital forensics, Security operations, Containment, Business continuity, Disaster recovery, CSIRT

**References:**
- Cichonski, P., Millar, T., Grance, T., & Scarfone, K. (2012). *Computer Security Incident Handling Guide.* NIST Special Publication 800-61 Rev. 2.
- Mitropoulos, S., Patsos, D., & Douligeris, C. (2006). On incident handling and response: A state-of-the-art approach. *Computers & Security*, 25(5), 351–370.

---

### **Industrial Control Systems Security**

Industrial control systems (ICS) security protects the **hardware and software** that monitor and control industrial processes — manufacturing, energy, water treatment, and logistics infrastructure. ICS include **SCADA** (Supervisory Control and Data Acquisition), **PLCs** (Programmable Logic Controllers), and **DCS** (Distributed Control Systems). ICS were historically isolated (air-gapped) but are increasingly connected to IT networks and the internet, exposing them to cyber threats. Notable incidents include Stuxnet and the Colonial Pipeline attack.

**Related concepts:** SCADA, OT security, Cyber-physical systems, Critical infrastructure, Air-gapped networks, PLC

**References:**
- Stouffer, K., Pillitteri, V., Lightman, S., Abrams, M., & Hahn, A. (2015). *Guide to Industrial Control Systems (ICS) Security.* NIST Special Publication 800-82 Rev. 2.
- McLaughlin, S., Konstantinou, C., Wang, X., et al. (2016). The cybersecurity landscape in industrial control systems. *Proceedings of the IEEE*, 104(5), 1039–1057.

---

### **IoT Security**

IoT security encompasses the **strategies, technologies, and practices** for protecting Internet of Things devices — sensors, actuators, gateways, and edge devices — from cyber threats. IoT security challenges include **constrained resources** (limited CPU, memory, battery), **diverse protocols**, **large attack surfaces**, **firmware vulnerabilities**, and **lack of standardization**. In logistics, IoT devices track shipments, monitor warehouse conditions, and control autonomous systems, making their security essential for operational integrity.

**Related concepts:** Embedded security, Firmware security, Device authentication, Edge security, Lightweight cryptography

**References:**
- Sicari, S., Rizzardi, A., Grieco, L. A., & Coen-Porisini, A. (2015). Security, privacy and trust in Internet of Things: The road ahead. *Computer Networks*, 76, 146–164.
- Neshenko, N., Bou-Harb, E., Crichigno, J., Kaddoum, G., & Ghani, N. (2019). Demystifying IoT security: An exhaustive survey on IoT vulnerabilities and a first empirical look on internet-scale IoT exploitations. *IEEE Communications Surveys & Tutorials*, 21(3), 2702–2733.

---

### **Malware Analysis**

Malware analysis is the process of **studying malicious software** — viruses, trojans, ransomware, worms, spyware — to understand its **functionality, origin, and impact**. **Static analysis** examines code without execution (disassembly, string analysis); **dynamic analysis** runs malware in sandboxed environments to observe behavior. **AI-based malware detection** uses machine learning on binary features, API call sequences, and network behavior to classify known and unknown malware. Malware targeting logistics systems can disrupt operations, steal data, or enable ransomware attacks.

**Related concepts:** Reverse engineering, Sandboxing, Threat intelligence, Ransomware, Antivirus, Behavioral analysis

**References:**
- Sikorski, M., & Honig, A. (2012). *Practical Malware Analysis: The Hands-On Guide to Dissecting Malicious Software.* No Starch Press.
- Ucci, D., Aniello, L., & Baldoni, R. (2019). Survey of machine learning techniques for malware analysis. *Computers & Security*, 81, 123–147.

---

### **Network Security**

Network security is the **practice of protecting computer networks** and their data from unauthorized access, misuse, modification, or denial of service. It encompasses **perimeter defenses** (firewalls, IDS/IPS), **network segmentation**, **VPNs**, **encryption of communications**, **access control**, and **monitoring**. In logistics, network security protects the communications between **warehouses, transportation systems, suppliers, and cloud services**, ensuring the confidentiality, integrity, and availability of operational data.

**Related concepts:** Firewall, IDS/IPS, VPN, Network segmentation, Zero trust, Encryption

**References:**
- Stallings, W. (2017). *Network Security Essentials: Applications and Standards* (6th ed.). Pearson.
- Bellovin, S. M. (2004). A look back at "Security Problems in the TCP/IP Protocol Suite." *Proceedings of ACSAC 2004*, 229–249.

---

### **Penetration Testing**

Penetration testing (pentesting) is the **authorized simulation of cyber attacks** against systems, networks, or applications to identify **security vulnerabilities** before malicious actors can exploit them. Pentesting methodologies include **black-box** (no prior knowledge), **white-box** (full access to source code and architecture), and **grey-box** (partial knowledge). Standards include **OWASP Testing Guide**, **PTES**, and **NIST SP 800-115**. In logistics, pentesting assesses the security of **supply chain platforms**, **warehouse systems**, **fleet management software**, and **IoT infrastructure**.

**Related concepts:** Vulnerability assessment, Ethical hacking, Security testing, Red teaming, OWASP, Bug bounty

**References:**
- Weidman, G. (2014). *Penetration Testing: A Hands-On Introduction to Hacking.* No Starch Press.
- Scarfone, K., Souppaya, M., Cody, A., & Orebaugh, A. (2008). *Technical Guide to Information Security Testing and Assessment.* NIST Special Publication 800-115.

---

### **Public Key Infrastructure**

Public key infrastructure (PKI) is a **framework of policies, procedures, and technologies** for managing digital certificates and public-key encryption. PKI enables **authentication** (verifying identity), **encryption** (protecting data confidentiality), **digital signatures** (ensuring integrity and non-repudiation), and **secure communication** (TLS/SSL). In logistics, PKI secures **electronic documents** (bills of lading, customs declarations), **device authentication** (IoT), **email communication**, and **API integrations** between supply chain partners.

**Related concepts:** Digital certificates, Certificate authority, TLS/SSL, Encryption, Authentication, Non-repudiation

**References:**
- Adams, C., & Lloyd, S. (2002). *Understanding PKI: Concepts, Standards, and Deployment Considerations* (2nd ed.). Addison-Wesley.
- Housley, R., & Polk, T. (2001). *Planning for PKI: Best Practices Guide for Deploying Public Key Infrastructure.* Wiley.

---

### **Ransomware**

Ransomware is **malicious software** that encrypts victims' data and demands payment (typically cryptocurrency) for the decryption key. Modern ransomware operations employ **double extortion** (threatening to publish stolen data), **ransomware-as-a-service (RaaS)** (criminal franchising), and **targeted attacks** on high-value organizations. Logistics and supply chain companies are frequent targets because operational disruptions pressure quick payment. Defense involves **backups**, **network segmentation**, **endpoint detection**, **patch management**, and **incident response planning**.

**Related concepts:** Malware, Incident response, Business continuity, Data backup, Endpoint security, Cyber insurance

**References:**
- Connolly, L. Y., & Wall, D. S. (2019). The rise of crypto-ransomware in a changing cybercrime landscape: Taxonomising countermeasures. *Computers & Security*, 87, 101568.
- Richardson, R., & North, M. M. (2017). Ransomware: Evolution, mitigation and prevention. *International Management Review*, 13(1), 10–21.

---

### **Risk Assessment**

Risk assessment in cybersecurity is the **systematic process** of identifying, analyzing, and evaluating **cyber risks** to an organization's assets, operations, and objectives. It involves **threat identification**, **vulnerability analysis**, **impact assessment**, **likelihood estimation**, and **risk prioritization**. Frameworks include **NIST RMF**, **ISO 27005**, **FAIR** (Factor Analysis of Information Risk), and **OCTAVE**. In logistics, risk assessment evaluates threats to **supply chain systems**, **customer data**, **operational technology**, and **third-party integrations**.

**Related concepts:** Risk management, Vulnerability assessment, Threat modeling, Business impact analysis, Compliance, NIST

**References:**
- NIST (2018). *Framework for Improving Critical Infrastructure Cybersecurity* (Version 1.1).
- Freund, J., & Jones, J. (2015). *Measuring and Managing Information Risk: A FAIR Approach.* Butterworth-Heinemann.

---

### **Secure Software Development**

Secure software development integrates **security practices** throughout the software development lifecycle (SDLC) — from requirements and design to coding, testing, and deployment. Practices include **threat modeling**, **secure coding standards** (OWASP), **static application security testing (SAST)**, **dynamic application security testing (DAST)**, **software composition analysis** (SCA, for open-source dependencies), and **DevSecOps** (integrating security into CI/CD pipelines). Secure development is essential for logistics software that handles sensitive supply chain data.

**Related concepts:** DevSecOps, OWASP, Code review, SAST, DAST, Software composition analysis, Shift-left security

**References:**
- McGraw, G. (2006). *Software Security: Building Security In.* Addison-Wesley.
- OWASP Foundation (2021). *OWASP Top Ten — 2021.* https://owasp.org/Top10/

---

### **SIEM (Security Information and Event Management)**

SIEM systems **collect, aggregate, correlate, and analyze** security event data from across an organization's IT infrastructure — firewalls, IDS/IPS, servers, applications, endpoints — to provide **real-time threat detection**, **investigation capabilities**, and **compliance reporting**. Modern SIEM platforms incorporate **machine learning** for anomaly detection, **SOAR** (Security Orchestration, Automation, and Response) for automated incident handling, and **threat intelligence** integration. SIEM is the operational backbone of security operations centers (SOCs).

**Related concepts:** Security operations, Log management, Anomaly detection, SOAR, Threat detection, Compliance

**References:**
- Bhatt, S., Manadhata, P. K., & Zomlot, L. (2014). The operational role of security information and event management systems. *IEEE Security & Privacy*, 12(5), 35–41.
- Gonzalez-Granadillo, G., Gonzalez-Zarzosa, S., & Diaz, R. (2021). Security information and event management (SIEM): Analysis, trends, and usage in critical infrastructures. *Sensors*, 21(14), 4759.

---

### **Supply Chain Attack**

A supply chain attack compromises a **trusted vendor, supplier, or service provider** to gain access to the ultimate target organization. Attack vectors include **software supply chain** (injecting malicious code into updates — e.g., SolarWinds), **hardware supply chain** (tampering with components), and **service supply chain** (compromising managed service providers). Supply chain attacks are particularly dangerous because they exploit **trust relationships** and can affect thousands of downstream organizations simultaneously.

**Related concepts:** Third-party risk, Software supply chain, Vendor management, Trojanized updates, Trust relationships

**References:**
- Ohm, M., Plate, H., Sykosch, A., & Meier, M. (2020). Backstabber's Knife Collection: A review of open source software supply chain attacks. *Proceedings of DIMVA 2020*, 23–43.
- ENISA (2021). *Threat Landscape for Supply Chain Attacks.* European Union Agency for Cybersecurity.

---

### **Supply Chain Risk Management**

Supply chain risk management (SCRM) is the **systematic identification, assessment, and mitigation** of risks that can disrupt supply chain operations — including **cyber risks**, **natural disasters**, **geopolitical events**, **supplier failures**, and **logistics disruptions**. Cyber SCRM specifically addresses risks from digital interconnections between supply chain partners. Frameworks include **NIST SP 800-161** (cyber supply chain risk management) and **ISO 28000** (supply chain security management).

**Related concepts:** Risk assessment, Business continuity, Supply chain resilience, Third-party risk, Contingency planning

**References:**
- Boyson, S. (2014). Cyber supply chain risk management: Revolutionizing the strategic control of critical IT systems. *Technovation*, 34(7), 342–353.
- NIST (2022). *Cybersecurity Supply Chain Risk Management Practices for Systems and Organizations.* NIST Special Publication 800-161 Rev. 1.

---

### **Vulnerability Assessment**

Vulnerability assessment is the **systematic identification and classification** of security weaknesses in systems, networks, applications, and configurations. It uses **automated scanning tools** (Nessus, Qualys, OpenVAS), **configuration auditing**, and **manual review** to discover known vulnerabilities (CVEs), misconfigurations, and policy violations. Unlike penetration testing, vulnerability assessment typically does not exploit vulnerabilities. In logistics, regular vulnerability assessments are essential for **compliance**, **patch prioritization**, and maintaining the security posture of diverse IT/OT environments.

**Related concepts:** Penetration testing, Patch management, CVE, Vulnerability scanning, Security hardening, Compliance

**References:**
- Mell, P., Scarfone, K., & Romanosky, S. (2007). *A Complete Guide to the Common Vulnerability Scoring System Version 2.0.* FIRST/NIST.
- Wack, J., Tracy, M., & Souppaya, M. (2003). *Guideline on Network Security Testing.* NIST Special Publication 800-42.

---

### **Zero Trust Architecture**

Zero trust architecture (ZTA) is a **security model** based on the principle of **"never trust, always verify"** — no user, device, or network segment is inherently trusted, regardless of location (inside or outside the network perimeter). Every access request is **authenticated, authorized, and continuously validated**. Key components include **micro-segmentation**, **identity-aware proxies**, **multi-factor authentication**, **least-privilege access**, and **continuous monitoring**. ZTA is increasingly adopted in logistics to protect distributed, multi-partner supply chain environments.

**Related concepts:** Network segmentation, Identity management, Multi-factor authentication, Least privilege, Micro-segmentation

**References:**
- Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero Trust Architecture.* NIST Special Publication 800-207.
- Kindervag, J. (2010). *No More Chewy Centers: Introducing the Zero Trust Model of Information Security.* Forrester Research.

---

### **AI-Driven Cybersecurity**

AI-driven cybersecurity applies **machine learning, deep learning, and NLP** to automate and enhance security operations — **threat detection** (identifying novel attacks), **malware classification**, **phishing detection**, **user and entity behavior analytics (UEBA)**, **automated incident response**, and **vulnerability prioritization**. AI addresses the challenge of **scale** (billions of events per day) and **sophistication** (zero-day attacks) that overwhelm human analysts. Adversarial AI — where attackers use AI to evade defenses — creates an ongoing arms race.

**Related concepts:** Machine learning, Anomaly detection, SIEM, Threat intelligence, Adversarial AI, Automation

**References:**
- Buczak, A. L., & Guven, E. (2016). A survey of data mining and machine learning methods for cyber security intrusion detection. *IEEE Communications Surveys & Tutorials*, 18(2), 1153–1176.
- Apruzzese, G., Colajanni, M., Ferretti, L., Guido, A., & Marchetti, M. (2018). On the effectiveness of machine and deep learning for cyber security. *Proceedings of CyberSA 2018*, 1–8.

---

## Summary Statistics

| **Category** | **Count** | **Examples** |
|---|---|---|
| Network & Infrastructure Security | 5 | Network Security, Firewall/IDS/IPS, Zero Trust, IoT Security, ICS Security |
| Threat Detection & Response | 5 | Anomaly Detection, Incident Response, SIEM, Cyber Threat Intelligence, AI-Driven Cybersecurity |
| Supply Chain Security | 4 | Supply Chain Attack, Supply Chain Risk Management, Blockchain for Supply Chain, CPS Security |
| Data Protection | 3 | Encryption, Access Control, Data Loss Prevention |
| Assessment & Testing | 3 | Risk Assessment, Vulnerability Assessment, Penetration Testing |
| Malware & Forensics | 3 | Malware Analysis, Digital Forensics, Ransomware |
| Secure Development & PKI | 2 | Secure Software Development, Public Key Infrastructure |
| **Total** | **25** | |
