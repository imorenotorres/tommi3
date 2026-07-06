# Glossary of AI & Language Concepts

This glossary provides **comprehensive definitions** of key concepts in AI and Language (NLP, computational linguistics, multilingualism), curated for the UNINOVIS alliance. Each entry includes related concepts, academic references, and context for understanding. Contributions and corrections are welcome.

---

## Glossary Entries

---

### **Automatic Speech Recognition (ASR)**

Automatic speech recognition is the technology that converts **spoken language into text**. Modern ASR systems use deep learning models (recurrent neural networks, transformers) trained on large speech corpora. Key challenges include handling **accents**, **noise**, **speaker variability**, and **low-resource languages**. ASR is foundational for voice assistants, transcription services, and spoken dialogue systems.

**Related concepts:** Speech-to-text, Spoken language understanding, Language models, Acoustic models, Voice technology

**References:**
- Hinton, G., Deng, L., Yu, D., et al. (2012). Deep neural networks for acoustic modeling in speech recognition. *IEEE Signal Processing Magazine*, 29(6), 82–97.
- Radford, A., Kim, J. W., Xu, T., et al. (2023). Robust speech recognition via large-scale weak supervision (Whisper). *Proceedings of ICML 2023*.

---

### **Computational Linguistics**

Computational linguistics is the **interdisciplinary field** at the intersection of linguistics and computer science, concerned with the computational modeling of natural language. It encompasses both **theoretical work** (formal grammars, language models) and **applied work** (NLP systems, language tools). Unlike purely engineering-oriented NLP, computational linguistics maintains close ties with **linguistic theory**.

**Related concepts:** Natural language processing, Formal grammars, Parsing, Morphology, Syntax, Semantics, Pragmatics

**References:**
- Jurafsky, D., & Martin, J. H. (2024). *Speech and Language Processing* (3rd ed. draft). Prentice Hall.
- Manning, C. D., & Schutze, H. (1999). *Foundations of Statistical Natural Language Processing*. MIT Press.

---

### **Conversational AI**

Conversational AI encompasses systems designed to **engage in natural dialogue** with humans, including **chatbots**, **virtual assistants**, and **dialogue systems**. Modern approaches use large language models (LLMs) for open-domain conversation and combine them with **retrieval-augmented generation (RAG)** for knowledge-grounded responses. Key challenges include **coherence**, **factual accuracy**, **safety**, and **multilingual support**.

**Related concepts:** Dialogue systems, Chatbots, Question answering, LLMs, Virtual assistants, Task-oriented dialogue

**References:**
- Ni, J., Young, T., Panber, V., et al. (2023). Recent advances in deep learning based dialogue systems: A systematic survey. *Artificial Intelligence Review*, 56, 3055–3155.
- Brown, T. B., Mann, B., Ryder, N., et al. (2020). Language models are few-shot learners. *Advances in Neural Information Processing Systems*, 33, 1877–1901.

---

### **Corpus Linguistics**

Corpus linguistics is the study of language based on **large collections of naturally occurring text** (corpora). Computational corpus linguistics uses software tools to analyze **word frequency**, **collocations**, **concordances**, and **grammatical patterns** in corpora. It provides **empirical evidence** for linguistic theories and serves as the **data foundation** for NLP systems.

**Related concepts:** Annotated corpora, Text mining, Language resources, Concordance, Frequency analysis, Treebanks

**References:**
- McEnery, T., & Hardie, A. (2012). *Corpus Linguistics: Method, Theory and Practice*. Cambridge University Press.
- Biber, D., Conrad, S., & Reppen, R. (1998). *Corpus Linguistics: Investigating Language Structure and Use*. Cambridge University Press.

---

### **Cross-Lingual Transfer**

Cross-lingual transfer refers to techniques that leverage **knowledge from resource-rich languages** (e.g., English) to improve NLP performance on **resource-poor languages**. Approaches include **multilingual pre-trained models** (mBERT, XLM-R), **zero-shot cross-lingual transfer**, **translation-based methods**, and **typological feature mapping**. It is essential for extending NLP technology to the world's 7,000+ languages.

**Related concepts:** Multilingual NLP, Low-resource languages, Transfer learning, Zero-shot learning, Language typology

**References:**
- Conneau, A., Khandelwal, K., Goyal, N., et al. (2020). Unsupervised cross-lingual representation learning at scale (XLM-R). *Proceedings of ACL 2020*, 8440–8451.
- Pires, T., Schlinger, E., & Garrette, D. (2019). How multilingual is multilingual BERT? *Proceedings of ACL 2019*, 4996–5001.

---

### **Hate Speech Detection**

Hate speech detection is the automated identification of **offensive, discriminatory, or threatening language** targeting individuals or groups based on characteristics such as race, religion, gender, or sexual orientation. NLP approaches use **text classification** models trained on annotated datasets. Key challenges include **context sensitivity**, **sarcasm**, **multilingual hate speech**, and **bias in training data**.

**Related concepts:** Content moderation, Sentiment analysis, Text classification, Online safety, Misinformation detection, Bias in AI

**References:**
- Fortuna, P., & Nunes, S. (2018). A survey on automatic detection of hate speech in text. *ACM Computing Surveys*, 51(4), 1–30.
- Poletto, F., Basile, V., Sanguinetti, M., Bosco, C., & Patti, V. (2021). Resources and benchmark corpora for hate speech detection: A systematic review. *Language Resources and Evaluation*, 55, 477–523.

---

### **Information Extraction**

Information extraction (IE) is the task of automatically extracting **structured information** from unstructured text. Subtasks include **named entity recognition** (identifying persons, organizations, locations), **relation extraction** (finding relationships between entities), **event extraction**, and **temporal information extraction**. IE is fundamental for knowledge base construction, text mining, and question answering.

**Related concepts:** Named entity recognition, Relation extraction, Knowledge graphs, Text mining, Question answering

**References:**
- Sarawagi, S. (2008). Information extraction. *Foundations and Trends in Databases*, 1(3), 261–377.
- Nadeau, D., & Sekine, S. (2007). A survey of named entity recognition and classification. *Lingvisticae Investigationes*, 30(1), 3–26.

---

### **Knowledge Graphs**

A knowledge graph is a **structured representation of knowledge** as a graph of entities (nodes) and their relationships (edges). In NLP, knowledge graphs support **question answering**, **entity linking**, **relation extraction**, and **knowledge-grounded text generation**. Major knowledge graphs include **Wikidata**, **DBpedia**, and **ConceptNet**.

**Related concepts:** Ontology, Semantic web, Entity linking, Relation extraction, Question answering, Linked data

**References:**
- Hogan, A., Blomqvist, E., Cochez, M., et al. (2021). Knowledge graphs. *ACM Computing Surveys*, 54(4), 1–37.
- Ji, S., Pan, S., Cambria, E., Marttinen, P., & Yu, P. S. (2022). A survey on knowledge graphs: Representation, acquisition, and applications. *IEEE Transactions on Neural Networks and Learning Systems*, 33(2), 494–514.

---

### **Language Models**

A language model is a probabilistic model that assigns **probabilities to sequences of words**, capturing the statistical patterns of language. Modern language models based on the **transformer architecture** (BERT, GPT, T5, LLaMA) have revolutionized NLP by enabling **transfer learning**: a model pre-trained on large text corpora can be **fine-tuned** for specific tasks with relatively little data.

**Related concepts:** Large language models (LLMs), Transformers, Pre-training, Fine-tuning, BERT, GPT, Transfer learning

**References:**
- Vaswani, A., Shazeer, N., Parmar, N., et al. (2017). Attention is all you need. *Advances in Neural Information Processing Systems*, 30, 5998–6008.
- Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. *Proceedings of NAACL-HLT 2019*, 4171–4186.

---

### **Low-Resource Languages**

Low-resource languages are languages for which there is **limited digital text, annotated data, and NLP tools**. The vast majority of the world's ~7,000 languages are low-resource. Research in this area focuses on **data augmentation**, **cross-lingual transfer**, **unsupervised methods**, and **community-driven data collection** to extend NLP technology beyond the few dozen well-resourced languages.

**Related concepts:** Multilingualism, Cross-lingual transfer, Language documentation, Endangered languages, Data augmentation, Zero-shot learning

**References:**
- Joshi, P., Santy, S., Buber, A., et al. (2020). The state and fate of linguistic diversity and inclusion in the NLP world. *Proceedings of ACL 2020*, 6282–6293.
- Hedderich, M. A., Lange, L., Adel, H., Strotgen, J., & Klakow, D. (2021). A survey on recent approaches for natural language processing in low-resource scenarios. *Proceedings of NAACL 2021*, 2545–2568.

---

### **Machine Translation**

Machine translation (MT) is the automatic translation of text or speech from one **natural language** to another. The dominant paradigm is **neural machine translation (NMT)**, which uses encoder-decoder architectures with attention mechanisms. Key research areas include **low-resource translation**, **multilingual models**, **document-level translation**, **quality estimation**, and **human-in-the-loop post-editing**.

**Related concepts:** Neural machine translation, Statistical machine translation, Post-editing, BLEU score, Multilingual NLP, Parallel corpora

**References:**
- Bahdanau, D., Cho, K., & Bengio, Y. (2015). Neural machine translation by jointly learning to align and translate. *Proceedings of ICLR 2015*.
- Stahlberg, F. (2020). Neural machine translation: A review. *Journal of Artificial Intelligence Research*, 69, 343–418.

---

### **Morphological Analysis**

Morphological analysis is the computational study of **word structure** — how words are formed from smaller meaningful units (morphemes). Tasks include **stemming**, **lemmatization**, **morphological segmentation**, and **morphological generation**. It is especially important for **morphologically rich languages** (e.g., Finnish, Turkish, Arabic) where a single word can encode complex grammatical information.

**Related concepts:** Lemmatization, Stemming, Tokenization, Part-of-speech tagging, Inflection, Derivation

**References:**
- Cotterell, R., Muller, H., & Beinborn, L. (2019). Morphological analysis: Past, present and future. *Proceedings of EACL 2019 Tutorial*.
- Goldsmith, J. (2001). Unsupervised learning of the morphology of a natural language. *Computational Linguistics*, 27(2), 153–198.

---

### **Multilingual NLP**

Multilingual NLP develops systems that can process **multiple languages** within a single framework. Central to this effort are **multilingual pre-trained models** (mBERT, XLM-R, mT5) that learn shared representations across languages. Research topics include **zero-shot cross-lingual transfer**, **code-switching**, **transliteration**, and **typologically diverse evaluation**.

**Related concepts:** Cross-lingual transfer, Low-resource languages, Multilingualism, Language typology, Code-switching

**References:**
- Conneau, A., et al. (2020). Unsupervised cross-lingual representation learning at scale (XLM-R). *Proceedings of ACL 2020*.
- Xue, L., Constant, N., Roberts, A., et al. (2021). mT5: A massively multilingual pre-trained text-to-text transformer. *Proceedings of NAACL 2021*, 483–498.

---

### **Named Entity Recognition (NER)**

Named entity recognition is the task of identifying and classifying **named entities** in text into predefined categories such as **person**, **organization**, **location**, **date**, and **product**. NER is a fundamental component of information extraction, question answering, and knowledge graph construction. Modern NER systems use **sequence labeling** with neural models (BiLSTM-CRF, transformers).

**Related concepts:** Information extraction, Sequence labeling, Knowledge graphs, Entity linking, Part-of-speech tagging

**References:**
- Li, J., Sun, A., Han, J., & Li, C. (2020). A survey on deep learning for named entity recognition. *IEEE Transactions on Knowledge and Data Engineering*, 34(1), 50–70.
- Lample, G., Ballesteros, M., Subramanian, S., Kawakami, K., & Dyer, C. (2016). Neural architectures for named entity recognition. *Proceedings of NAACL 2016*, 260–270.

---

### **Question Answering**

Question answering (QA) is the task of automatically finding **answers to natural language questions**. QA systems range from **extractive** (selecting a text span from a document) to **abstractive** (generating an answer) and **knowledge-based** (querying structured data). Modern QA leverages **retrieval-augmented generation (RAG)** — combining document retrieval with language model generation for factual, grounded answers.

**Related concepts:** Reading comprehension, Information retrieval, Knowledge graphs, RAG, Dialogue systems

**References:**
- Rajpurkar, P., Zhang, J., Lopyrev, K., & Liang, P. (2016). SQuAD: 100,000+ questions for machine comprehension of text. *Proceedings of EMNLP 2016*, 2383–2392.
- Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *Advances in NeurIPS*, 33, 9459–9474.

---

### **Sentiment Analysis**

Sentiment analysis determines the **emotional tone** or **opinion** expressed in text — typically classifying it as positive, negative, or neutral. Advanced approaches detect **aspect-level sentiment**, **emotions**, **sarcasm**, and **stance**. It is widely used for **social media monitoring**, **product review analysis**, **political opinion tracking**, and **customer feedback**.

**Related concepts:** Opinion mining, Text classification, Social media analysis, Aspect-based sentiment analysis, Emotion detection

**References:**
- Liu, B. (2012). *Sentiment Analysis and Opinion Mining*. Morgan & Claypool.
- Pang, B., & Lee, L. (2008). Opinion mining and sentiment analysis. *Foundations and Trends in Information Retrieval*, 2(1-2), 1–135.

---

### **Sign Language Processing**

Sign language processing applies **computer vision and NLP techniques** to recognize, translate, and generate **sign languages**. Tasks include **sign language recognition** (video to gloss), **sign language translation** (video to spoken language text), and **sign language generation** (text to avatar signing). It is critical for **accessibility** and communication with the Deaf community.

**Related concepts:** Gesture recognition, Computer vision, Multimodal NLP, Accessibility, Video understanding

**References:**
- Bragg, D., Koller, O., Bellard, M., et al. (2019). Sign language recognition, generation, and translation: An interdisciplinary perspective. *Proceedings of ASSETS 2019*, 16–30.
- Camgoz, N. C., Hadfield, S., Koller, O., Ney, H., & Bowden, R. (2020). Sign language transformers: Joint end-to-end sign language recognition and translation. *Proceedings of CVPR 2020*.

---

### **Text Summarization**

Text summarization is the task of producing a **concise, informative summary** of a longer document. **Extractive** methods select key sentences from the source; **abstractive** methods generate new text that paraphrases the source. Evaluation metrics include **ROUGE** (recall-oriented) and human judgment. Applications include news summarization, scientific paper summarization, and meeting minutes generation.

**Related concepts:** Information extraction, Language generation, Reading comprehension, ROUGE metric, Document understanding

**References:**
- Nenkova, A., & McKeown, K. (2012). A survey of text summarization techniques. In C. C. Aggarwal & C. Zhai (Eds.), *Mining Text Data* (pp. 43–76). Springer.
- Zhang, J., Zhao, Y., Saleh, M., & Liu, P. (2020). PEGASUS: Pre-training with extracted gap-sentences for abstractive summarization. *Proceedings of ICML 2020*.

---

### **Tokenization**

Tokenization is the process of **breaking text into smaller units** (tokens) — words, subwords, or characters — as a preprocessing step for NLP. Modern subword tokenization methods (BPE, WordPiece, SentencePiece) balance **vocabulary size** and **coverage** and are used by all major language models. Tokenization choices significantly impact model performance, especially for **morphologically rich** and **low-resource languages**.

**Related concepts:** Subword segmentation, BPE, WordPiece, SentencePiece, Preprocessing, Morphological analysis

**References:**
- Sennrich, R., Haddow, B., & Birch, A. (2016). Neural machine translation of rare words with subword units (BPE). *Proceedings of ACL 2016*, 1715–1725.
- Kudo, T. (2018). Subword regularization: Improving neural network translation models with multiple subword candidates (SentencePiece). *Proceedings of ACL 2018*, 66–75.

---

### **Word Embeddings**

Word embeddings are **dense vector representations** of words in a continuous vector space, where semantically similar words are close together. Pre-trained embeddings (Word2Vec, GloVe, FastText) capture **distributional semantics** from large corpora. They serve as input features for downstream NLP tasks. Contextualized embeddings from transformer models (BERT, ELMo) represent words differently depending on their **context**.

**Related concepts:** Word2Vec, GloVe, FastText, Distributional semantics, Contextualized embeddings, Vector space models

**References:**
- Mikolov, T., Sutskever, I., Chen, K., Corrado, G., & Dean, J. (2013). Distributed representations of words and phrases and their compositionality. *Advances in NeurIPS*, 26, 3111–3119.
- Pennington, J., Socher, R., & Manning, C. (2014). GloVe: Global vectors for word representation. *Proceedings of EMNLP 2014*, 1532–1543.

---

## Summary Statistics

| **Category**               | **Count** | **Examples**                          |
|----------------------------|----------|---------------------------------------|
| Core NLP                   | 7        | Tokenization, NER, Parsing, Morphological Analysis |
| Language Models & Generation | 4      | Language Models, Conversational AI, Text Summarization |
| Translation & Multilingualism | 4     | Machine Translation, Cross-Lingual Transfer, Multilingual NLP, Low-Resource Languages |
| Text Analysis & Mining     | 4        | Sentiment Analysis, Information Extraction, Hate Speech Detection, QA |
| Language Resources          | 3        | Corpus Linguistics, Knowledge Graphs, Word Embeddings |
| Multimodal & Speech        | 3        | ASR, Sign Language Processing, Computational Linguistics |
| **Total**                  | **25**   |                                       |
