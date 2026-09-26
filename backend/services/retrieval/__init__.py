"""Retrieval foundation: review validation, preprocessing, deduplication,
vector storage, indexing, and semantic search."""

from services.retrieval.contracts import (
    IndexingReport,
    PreparedReview,
    RejectedReview,
    ValidatedReview,
    ValidationOutcome,
    ValidationReport,
)
from services.retrieval.deduplication import (
    dedupe_prepared,
    prepare_review,
    review_fingerprint,
)
from services.retrieval.preprocessing import preprocess_review_text
from services.retrieval.review_validation import validate_review, validate_reviews
from services.retrieval.search_service import SemanticSearchOutcome, SemanticSearchService
from services.retrieval.vector_repository import (
    ReviewSearchFilters,
    ReviewSearchResult,
    ReviewVectorRecord,
    VectorMetadata,
    VectorRepository,
)

__all__ = [
    "IndexingReport",
    "PreparedReview",
    "RejectedReview",
    "ReviewSearchFilters",
    "ReviewSearchResult",
    "ReviewVectorRecord",
    "SemanticSearchOutcome",
    "SemanticSearchService",
    "ValidatedReview",
    "ValidationOutcome",
    "ValidationReport",
    "VectorMetadata",
    "VectorRepository",
    "dedupe_prepared",
    "prepare_review",
    "preprocess_review_text",
    "review_fingerprint",
    "validate_review",
    "validate_reviews",
]
