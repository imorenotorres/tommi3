"""
Tommi Virtual Tutor (Vectorless) — Simple RAG agent with BM25 retrieval.
Uses procedural badges instead of claim-level reliability.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, SimpleRAGMixin, SimpleVectorlessMixin


class Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
