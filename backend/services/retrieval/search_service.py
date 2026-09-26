"""Semantic similarity search over stored review embeddings.

    query text
        -> preprocess
        -> embedding provider (RETRIEVAL_QUERY)
        -> vector repository (cosine, top-k, optional threshold + filters)
        -> structured results

No LLM is called and no retrieval-augmented generation happens here; this is
pure retrieval infrastructure.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from services.embeddings.contracts import EmbeddingTaskType
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.embeddings.service import EmbeddingService
from services.retrieval.preprocessing import preprocess_review_text
from services.retrieval.vector_repository import (
    ReviewSearchFilters,
    ReviewSearchResult,
    VectorRepository,
)

# Bounds for configurable top_k. Enforced here (not deep in the repository) so
# the RAG milestone can choose its own retrieval strategy within safe limits.
DEFAULT_TOP_K = 10
MAX_TOP_K = 100


@dataclass(frozen=True)
class SemanticSearchOutcome:
    """Result of one semantic search (empty tuple when nothing matches)."""

    query_text: str
    normalized_query: str
    results: Tuple[ReviewSearchResult, ...]
    top_k: int
    similarity_threshold: Optional[float]
    embedding_model: str
    embedding_dimension: int


class SemanticSearchService:
    """Embeds a query and returns the most similar stored reviews."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_repository: VectorRepository,
        *,
        default_top_k: int = DEFAULT_TOP_K,
        max_top_k: int = MAX_TOP_K,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_repository = vector_repository
        self._default_top_k = default_top_k
        self._max_top_k = max_top_k

    def search(
        self,
        query_text: str,
        *,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[ReviewSearchFilters] = None,
    ) -> SemanticSearchOutcome:
        if not isinstance(query_text, str) or not query_text.strip():
            raise EmbeddingError(
                "A non-empty query is required.", EmbeddingErrorType.INVALID_INPUT
            )

        resolved_top_k = self._default_top_k if top_k is None else top_k
        if not isinstance(resolved_top_k, int) or isinstance(resolved_top_k, bool):
            raise EmbeddingError(
                "top_k must be an integer.", EmbeddingErrorType.INVALID_INPUT
            )
        if not 1 <= resolved_top_k <= self._max_top_k:
            raise EmbeddingError(
                f"top_k must be between 1 and {self._max_top_k}.",
                EmbeddingErrorType.INVALID_INPUT,
            )
        if similarity_threshold is not None and not (
            -1.0 <= similarity_threshold <= 1.0
        ):
            raise EmbeddingError(
                "similarity_threshold must be between -1 and 1.",
                EmbeddingErrorType.INVALID_INPUT,
            )

        normalized_query = preprocess_review_text(query_text)
        query_vector = self._embedding_service.embed_text(
            normalized_query, task_type=EmbeddingTaskType.RETRIEVAL_QUERY
        )
        results = self._vector_repository.search(
            query_vector,
            embedding_model=self._embedding_service.model,
            dimension=self._embedding_service.dimension,
            top_k=resolved_top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
        )
        return SemanticSearchOutcome(
            query_text=query_text,
            normalized_query=normalized_query,
            results=tuple(results),
            top_k=resolved_top_k,
            similarity_threshold=similarity_threshold,
            embedding_model=self._embedding_service.model,
            embedding_dimension=self._embedding_service.dimension,
        )
