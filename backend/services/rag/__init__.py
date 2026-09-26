"""V2-P3 RAG pipeline: retrieval, context building, and context-aware prompting.

Disabled by default (``RAG_ENABLED`` unset/false); when enabled the analysis
pipeline retrieves similar reviews, builds a bounded context block, and sends a
context-aware prompt while keeping grounding original-review-only.
"""

from services.rag.config import RAGConfig
from services.rag.context_builder import (
    ContextReview,
    RagContext,
    build_rag_context,
    render_context_block,
)
from services.rag.prompting import build_analysis_prompt
from services.rag.retrieval import (
    RagRetrievalMetadata,
    RagRetrievalResult,
    RagRetrievalService,
    RagRetrievalStatus,
)

__all__ = [
    "ContextReview",
    "RAGConfig",
    "RagContext",
    "RagRetrievalMetadata",
    "RagRetrievalResult",
    "RagRetrievalService",
    "RagRetrievalStatus",
    "build_analysis_prompt",
    "build_rag_context",
    "render_context_block",
]
