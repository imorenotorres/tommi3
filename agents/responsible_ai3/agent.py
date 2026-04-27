"""
EH: Responsible AI (Vectorless) — Metadata-only agent.
Same data as responsible_ai2 but without ChromaDB/vector dependencies.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
