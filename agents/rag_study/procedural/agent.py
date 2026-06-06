"""
RAG Study — Variant 3: Procedural (Metadata + RAG + Procedural Reasoning)

Full Metadata+RAG architecture with 13-step classification chain,
programmatic paths, synonym expansion, and post-processing pipeline.
This is the baseline — identical to Responsible_AI3.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
