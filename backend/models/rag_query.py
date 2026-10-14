"""Phase 7F — RAG query endpoint contracts."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RAGQueryRequest(BaseModel):
    """Request body for POST /api/products/{product_id}/rag-query."""

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, v: str) -> str:
        """Reject whitespace-only queries with 422 at validation time.

        ``min_length=1`` only counts characters, so ``"   "`` passes the field
        constraint yet can never embed or retrieve anything. Rejecting here
        keeps blank input out of the route entirely — no catalog lookup, no
        embedding call, no retrieval. Unlike ``ReviewRequest.strip_and_validate_review``
        the value is returned UNCHANGED: this contract never trims or rewrites
        a non-empty query.
        """
        if not v.strip():
            raise ValueError("query must contain at least one non-whitespace character.")
        return v


class EvidenceItem(BaseModel):
    """One retrieved review backing the answer (verbatim excerpt)."""

    review_id: str = Field(..., min_length=1)
    excerpt: str = Field(..., min_length=1)
    similarity_score: float
    rating: Optional[int] = None


class RAGQueryResponse(BaseModel):
    """Grounded answer plus retrieval metadata.

    ``evidence`` is intentionally NOT constrained with min_length: disabled
    and empty-retrieval responses legitimately return an empty list (spec
    7F / test_rag_fallback_on_empty_retrieval). The route enforces the
    non-empty invariant whenever ``answer`` is non-empty.
    """

    answer: str
    evidence: List[EvidenceItem]
    retrieval_count: int
    context_token_estimate: int
    model_used: str
    rag_enabled: bool
    fallback_used: bool
