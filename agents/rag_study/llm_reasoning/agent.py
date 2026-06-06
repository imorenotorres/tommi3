"""
RAG Study — Variant 2: RAG + LLM Reasoning

Same BM25 retrieval as Vanilla RAG, but the system prompt instructs the LLM
to classify the query type and respond differently for each type.
All reasoning is done by the LLM (via prompt instructions), not by code.

The classification chain exists only in the prompt — there are no programmatic
paths, no metadata lookups, no post-processing pipeline.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from base import BaseRAGAgent, SimpleRAGMixin, SimpleVectorlessMixin


class Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
