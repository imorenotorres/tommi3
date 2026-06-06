"""
RAG Study — Variant 1: Vanilla RAG (Vectorless)

Simplest architecture: BM25 retrieval + LLM, no classification chain,
no metadata, no programmatic paths. Every query follows the same path:
retrieve chunks → send to LLM → return response.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, SimpleRAGMixin, SimpleVectorlessMixin


class Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
