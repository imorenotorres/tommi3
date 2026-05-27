"""
EH: Health and Wellbeing Systems (Vectorless) — Metadata-only agent.
Adapted from responsible_ai3 for Health and Wellbeing Systems domain.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, MetadataRAGMixin, VectorlessMixin


class Agent(VectorlessMixin, MetadataRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
