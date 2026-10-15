"""V2-P3 RAG pipeline: retrieval, context building, and context-aware prompting.

Disabled by default (``RAG_ENABLED`` unset/false); when enabled the analysis
pipeline retrieves similar reviews, builds a bounded context block, and sends a
context-aware prompt while keeping grounding original-review-only.

Two distinct functions are named ``build_rag_context``:

* ``services.rag.context_builder.build_rag_context(reviews, config)`` —
  analysis-time context (ADR-006), rendered by ``render_context_block``.
* ``services.rag.query_context.build_rag_context(reviews, max_tokens)`` —
  query-time bounded context for ``POST /rag-query`` (ADR-014).

They have different signatures and contracts, so the package root exports them
under explicit aliases only. The bare name ``services.rag.build_rag_context``
is intentionally NOT exported: importing it would silently resolve to one of
the two and hide the ambiguity. Import from the owning module instead.
"""

from services.rag.config import RAGConfig
from services.rag.context_builder import (
    ContextReview,
    RagContext,
    build_rag_context as build_analysis_rag_context,
    render_context_block,
)
from services.rag.prompting import build_analysis_prompt
from services.rag.query_context import (
    RAGContext as QueryRAGContext,
    build_rag_context as build_query_rag_context,
)
from services.rag.retrieval import (
    RagRetrievalMetadata,
    RagRetrievalResult,
    RagRetrievalService,
    RagRetrievalStatus,
)

__all__ = [
    "ContextReview",
    "QueryRAGContext",
    "RAGConfig",
    "RagContext",
    "RagRetrievalMetadata",
    "RagRetrievalResult",
    "RagRetrievalService",
    "RagRetrievalStatus",
    "build_analysis_prompt",
    "build_analysis_rag_context",
    "build_query_rag_context",
    "render_context_block",
]
