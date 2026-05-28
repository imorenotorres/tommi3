"""
Tommi Virtual Tutor — Simple vectorless RAG agent with procedural banners.
All behavior from config.json + base classes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from base import BaseRAGAgent, SimpleRAGMixin
from base.simple_vectorless_mixin import SimpleVectorlessMixin


class Agent(SimpleVectorlessMixin, SimpleRAGMixin, BaseRAGAgent):
    _AGENT_FILE = __file__
