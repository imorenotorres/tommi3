"""
EH: Responsible AI — RAG+Metadata agent.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, MetadataRAGMixin


class Agent(MetadataRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
