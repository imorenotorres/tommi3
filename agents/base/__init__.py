"""
TOMMI Agent Base Classes and Mixins

Provides shared functionality for all TOMMI agents:
- BaseRAGAgent: core config, ChromaDB, prompt assembly, document indexing
- SimpleRAGMixin: chat/chat_stream for plain RAG agents
- MetadataRAGMixin: chat/chat_stream + metadata, maps, researchers for EH agents
- ReliabilityBadge, AuditLogger: transparency badges and EU AI Act audit logging
- HumilityRewriter: post-processing to soften ungrounded claims
"""

from .base_RAGagent import BaseRAGAgent
from .rag_mixin import SimpleRAGMixin
from .rag_metadata_mixin import MetadataRAGMixin
from .vectorless_mixin import VectorlessMixin
from .simple_vectorless_mixin import SimpleVectorlessMixin
from .badges import ReliabilityBadge, AuditLogger
from .humility import HumilityRewriter

__all__ = [
    "BaseRAGAgent",
    "SimpleRAGMixin",
    "MetadataRAGMixin",
    "VectorlessMixin",
    "SimpleVectorlessMixin",
    "ReliabilityBadge",
    "AuditLogger",
    "HumilityRewriter",
]
