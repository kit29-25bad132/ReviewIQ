"""RAG retrieval stage (V2-P3): query -> semantic search -> structured result.

Wraps the P2 ``SemanticSearchService`` (reused, never duplicated) with
RAG-specific configuration and best-effort semantics: ``retrieve()`` never
raises. Failures are captured as metadata (``status`` + ``error_type``) so the
analysis pipeline always continues with an empty context.

Determinism: results are ordered by descending similarity with ``review_id``
as the tie-break, so repeated queries over the same data produce the same
context order.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.rag.config import RAGConfig
from services.retrieval.search_service import SemanticSearchService
from services.retrieval.vector_repository import ReviewSearchResult

logger = logging.getLogger(__name__)


class RagRetrievalStatus(str, Enum):
    """Outcome of one retrieval attempt (safe to log; no secrets)."""

    DISABLED = "disabled"
    OK = "ok"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True)
class RagRetrievalMetadata:
    """Structured metadata for one retrieval attempt (V2-P3 requirement)."""

    enabled: bool
    query: str
    top_k: int
    similarity_threshold: float
    retrieved_count: int
    status: str
    error_type: Optional[str] = None


@dataclass(frozen=True)
class RagRetrievalResult:
    """Retrieved reviews plus the metadata describing how they were obtained."""

    metadata: RagRetrievalMetadata
    results: Tuple[ReviewSearchResult, ...]


def _sort_key(result: ReviewSearchResult):
    similarity = getattr(result, "similarity", None)
    if not isinstance(similarity, (int, float)) or isinstance(similarity, bool):
        similarity = 0.0
    review_id = getattr(result, "review_id", None)
    return (-float(similarity), str(review_id) if review_id is not None else "")


class RagRetrievalService:
    """Best-effort semantic retrieval configured for the analysis pipeline."""

    def __init__(
        self,
        config: RAGConfig,
        *,
        search_service: Optional[SemanticSearchService] = None,
    ) -> None:
        self._config = config
        self._search_service = search_service

    @property
    def config(self) -> RAGConfig:
        return self._config

    @property
    def search_service(self) -> SemanticSearchService:
        """P2 search service (built lazily: no DB/SDK access until first use)."""
        if self._search_service is None:
            from services.retrieval.runtime import build_search_service

            self._search_service = build_search_service()
        return self._search_service

    def retrieve(self, query: str) -> RagRetrievalResult:
        """Run semantic search for ``query``; never raises."""
        config = self._config
        if not config.enabled:
            return self._build(query, (), RagRetrievalStatus.DISABLED)
        if not isinstance(query, str) or not query.strip():
            return self._build(
                query if isinstance(query, str) else "",
                (),
                RagRetrievalStatus.INVALID,
                EmbeddingErrorType.INVALID_INPUT,
            )
        try:
            outcome = self.search_service.search(
                query,
                top_k=config.top_k,
                similarity_threshold=config.similarity_threshold,
            )
        except EmbeddingError as err:
            status = (
                RagRetrievalStatus.INVALID
                if err.error_type is EmbeddingErrorType.INVALID_INPUT
                else RagRetrievalStatus.UNAVAILABLE
            )
            logger.warning(
                "RAG retrieval failed (%s): %s", err.error_type.value, err
            )
            return self._build(query, (), status, err.error_type)
        except Exception as err:  # best-effort stage: analysis must not break
            logger.warning("RAG retrieval failed unexpectedly: %s", err)
            return self._build(
                query, (), RagRetrievalStatus.UNAVAILABLE, EmbeddingErrorType.UNKNOWN
            )
        results = tuple(sorted(outcome.results, key=_sort_key))
        status = (
            RagRetrievalStatus.OK if results else RagRetrievalStatus.EMPTY
        )
        return self._build(query, results, status)

    def _build(
        self,
        query: str,
        results: Tuple[ReviewSearchResult, ...],
        status: RagRetrievalStatus,
        error_type: Optional[EmbeddingErrorType] = None,
    ) -> RagRetrievalResult:
        return RagRetrievalResult(
            metadata=RagRetrievalMetadata(
                enabled=self._config.enabled,
                query=query,
                top_k=self._config.top_k,
                similarity_threshold=self._config.similarity_threshold,
                retrieved_count=len(results),
                status=status.value,
                error_type=error_type.value if error_type else None,
            ),
            results=results,
        )
