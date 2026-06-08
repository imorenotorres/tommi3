"""
RAG Study — Embedding-based Classification (Deterministic + Generalisable)

Semantic routing using sentence embeddings: the query is embedded and
compared to pre-computed embeddings of example queries per category.
Classification is deterministic (same embedding → same nearest category)
and generalises to paraphrases (semantic similarity, not lexical matching).

Architecture:
  1. Perception: receive query
  2. Reasoning: embed query → cosine similarity to category centroids
  3. Action: shared dispatch → programmatic response or LLM fallback
  4. Production: same paths as Rule-based and LLM-based variants
"""

import os
import sys
import json
import numpy as np

# Add paths
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_STUDY_DIR = os.path.dirname(os.path.dirname(_AGENT_DIR))
sys.path.insert(0, os.path.join(_STUDY_DIR, ".."))
sys.path.insert(0, os.path.join(_STUDY_DIR, "..", "..", "web"))
sys.path.insert(0, os.path.join(_STUDY_DIR, "shared"))

from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin
from dispatch import dispatch, build_llm_context

REASONING_LABEL = "embedding-based routing"

# ── Category examples from expert_input.md Phase A ─────────────────────────
# These are embedded once at load time and used for cosine similarity routing.

CATEGORY_EXAMPLES = {
    "meta": [
        "What can you do?",
        "What is UNINOVIS?",
        "Which universities are in UNINOVIS?",
        "How does this work?",
        "Who are you?",
        "Tell me about your capabilities",
        "What functionality do you offer?",
        "What topics do you cover?",
        "What information do you have access to?",
        "Explain your purpose",
    ],
    "non_research": [
        "Write me an essay about AI",
        "Can you book me a flight?",
        "Translate this text to French",
        "What is the weather today?",
        "Who won the last World Cup?",
        "Help me write a report",
        "Can you summarise this PDF for me?",
        "Make me a PowerPoint presentation",
        "Proofread this abstract for me",
        "Schedule a meeting",
    ],
    "off_topic": [
        "What is quantum computing?",
        "Hello",
        "Explain photosynthesis",
        "What is the speed of light?",
        "Tell me about the French Revolution",
        "How do vaccines work?",
        "What is blockchain technology?",
        "Good morning",
        "Thanks",
    ],
    "figure": [
        "Show a figure with all the publications per partner",
        "Show a map with the number of research projects per partner",
        "Show a figure of papers by year",
        "Display a chart of publications by year",
        "Visualise publications on trustworthy AI",
        "Can you plot the distribution of papers?",
        "Generate a bar chart of research output",
        "I want to see a graph showing collaboration patterns",
    ],
    "project": [
        "What is the TAILOR project about?",
        "Describe the IntelliMan project",
        "List research projects on trustworthy AI",
        "Show me projects related to trustworthy AI",
        "What does the DUCA project propose?",
        "Tell me about the CRYSTAL project",
        "What EU-funded projects does UNINOVIS participate in?",
        "Give me details about the EMPATHIC project",
        "Are there any projects on data governance?",
    ],
    "researcher": [
        "Papers by a specific researcher",
        "What has a researcher published?",
        "What are the research interests of a professor?",
        "Publications by a researcher",
        "List a researcher's publications",
        "Give me the bibliography of a researcher",
        "What work has a researcher done?",
        "Show me everything published by a researcher",
        "Find publications authored by a researcher",
        "Tell me about the research of a professor",
    ],
    "glossary": [
        "What is explainable AI?",
        "What is fairness in AI?",
        "What is the EU AI Act?",
        "What is the difference between interpretability and explainability?",
        "What is trustworthy AI?",
        "Define explainable AI",
        "What does AI accountability mean?",
        "Explain the concept of AI governance",
        "What is meant by AI transparency?",
        "Define bias in artificial intelligence",
    ],
    "topic_search": [
        "Papers on AI ethics",
        "Papers about AI and privacy",
        "Research on AI in education",
        "Articles about AI ethics",
        "Publications on AI and privacy",
        "Find papers about bias detection in machine learning",
        "What research exists on AI transparency?",
        "Publications related to federated learning",
        "Show me studies on human-AI interaction",
    ],
    "university_papers": [
        "List all researchers from THUAS",
        "List all papers from UDCLV",
        "What papers has UMA produced?",
        "Show me all research from Tampere",
        "List USPN publications",
        "Who are the researchers at a specific university?",
        "Research output from Kauno Kolegija",
        "Show me TAMK researchers",
    ],
    "gap": [
        "What responsible AI topics have not been studied in UNINOVIS?",
        "Are there gaps in UNINOVIS research on AI regulation?",
        "Which responsible AI subtopics are least studied?",
        "What are the research gaps?",
        "What subtopics are underexplored?",
        "Which areas are underrepresented in the database?",
        "What is missing from the current research coverage?",
        "Identify potential new research directions",
    ],
    "general": [
        "Is AI dangerous?",
        "Can AI be trusted?",
        "What is a language model?",
        "Can AI be harmful?",
        "Do you think AI will replace human workers?",
        "What are the main challenges in AI ethics today?",
        "Is regulation enough to make AI safe?",
        "Are current AI models biased?",
        "Should AI have rights?",
    ],
    "followup": [
        "Tell me more",
        "Expand on that",
        "Can you give more details?",
        "Go deeper into that",
        "Show me more",
        "Continue",
        "Yes, elaborate please",
        "What else?",
        "And the others?",
    ],
}


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    """Embedding-based classification → shared dispatch."""
    _AGENT_FILE = __file__

    def _post_init(self):
        """Load embedding model and pre-compute category centroids."""
        from sentence_transformers import SentenceTransformer

        print("[EMBEDDING] Loading embedding model...")
        self._embed_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Pre-compute centroid embeddings for each category
        self._category_centroids = {}
        self._category_examples_embedded = {}

        for cat, examples in CATEGORY_EXAMPLES.items():
            embeddings = self._embed_model.encode(examples, normalize_embeddings=True)
            self._category_centroids[cat] = np.mean(embeddings, axis=0)
            self._category_centroids[cat] /= np.linalg.norm(self._category_centroids[cat])
            self._category_examples_embedded[cat] = embeddings

        self._categories = list(CATEGORY_EXAMPLES.keys())
        print(f"[EMBEDDING] {len(self._categories)} categories, "
              f"{sum(len(v) for v in CATEGORY_EXAMPLES.values())} examples embedded")

    def _embedding_classify(self, query: str) -> dict:
        """Classify query by cosine similarity to category centroids."""
        query_embedding = self._embed_model.encode([query], normalize_embeddings=True)[0]

        # Method 1: Compare to centroids
        best_cat = None
        best_score = -1

        for cat in self._categories:
            centroid = self._category_centroids[cat]
            score = float(np.dot(query_embedding, centroid))
            if score > best_score:
                best_score = score
                best_cat = cat

        # Method 2: Also check nearest individual example (for edge cases)
        best_example_cat = None
        best_example_score = -1
        for cat in self._categories:
            examples = self._category_examples_embedded[cat]
            similarities = np.dot(examples, query_embedding)
            max_sim = float(np.max(similarities))
            if max_sim > best_example_score:
                best_example_score = max_sim
                best_example_cat = cat

        # Use nearest-example if it disagrees with centroid and has higher confidence
        if best_example_cat != best_cat and best_example_score > best_score + 0.05:
            best_cat = best_example_cat
            best_score = best_example_score

        return {
            "category": best_cat,
            "confidence": round(best_score, 4),
            "topic": "",
            "researcher": "",
            "university": "",
            "project": "",
        }

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        # Step 1: Embedding classification (deterministic)
        classification = self._embedding_classify(user_message)

        # Step 2: Shared dispatch (identical to Rule-based and LLM-based)
        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            return result + "\n\n" + trace

        # Step 3: LLM fallback (identical to other variants)
        system = build_llm_context(self, classification, user_message)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.complete(model=model, messages=messages, max_tokens=2048)
        return response.choices[0].message.content + "\n\n" + trace

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        model = kwargs.get('model_override') or self.model

        if not self._chromadb_initialized:
            self._init_chromadb()

        yield ("status", "Classifying query...")

        classification = self._embedding_classify(user_message)

        result, trace = dispatch(self, classification, user_message,
                                 reasoning_label=REASONING_LABEL)
        if result is not None:
            yield result
            if trace:
                yield ("trace", trace)
            return

        yield ("status", "Searching...")

        system = build_llm_context(self, classification, user_message)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        async for chunk in await self.client.chat.stream_async(model=model, messages=messages):
            if chunk.data.choices and chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content

        if trace:
            yield ("trace", trace)
