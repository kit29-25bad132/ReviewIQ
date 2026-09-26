"""Vector repository abstraction.

Application services depend on this interface, never on raw SQL. The Postgres
pgvector implementation lives in ``postgres_vector_repository.py``.

Similarity convention: **cosine**, computed as ``1 - cosine_distance``.
pgvector's cosine distance operator ``<=>`` is used for ordering (ascending
distance == descending similarity) and the similarity score is reported in
``[-1, 1]``. This single convention is used everywhere in retrieval.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence, Set


@dataclass(frozen=True)
class ReviewVectorRecord:
    """Everything persisted for one embedded review."""

    review_id: str
    fingerprint: str
    original_text: str
    normalized_text: str
    embedding: List[float]
    embedding_model: str
    embedding_dimension: int
    product_id: Optional[str] = None
    rating: Optional[int] = None
    source: Optional[str] = None
    review_date: Optional[datetime] = None


@dataclass(frozen=True)
class ReviewSearchFilters:
    """Typed metadata filters for similarity search (all optional)."""

    product_id: Optional[str] = None
    min_rating: Optional[int] = None
    max_rating: Optional[int] = None
    source: Optional[str] = None
    review_date_from: Optional[datetime] = None
    review_date_to: Optional[datetime] = None

    def is_empty(self) -> bool:
        return not any(
            (
                self.product_id,
                self.min_rating,
                self.max_rating,
                self.source,
                self.review_date_from,
                self.review_date_to,
            )
        )


@dataclass(frozen=True)
class ReviewSearchResult:
    """One similar review returned by a vector search."""

    review_id: str
    review_text: str
    normalized_text: str
    similarity: float
    distance: float
    embedding_model: str
    product_id: Optional[str] = None
    rating: Optional[int] = None
    source: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VectorMetadata:
    """Embedding metadata for one stored review (no vector payload)."""

    review_id: str
    embedding_model: str
    embedding_dimension: int
    product_id: Optional[str] = None
    rating: Optional[int] = None
    source: Optional[str] = None
    updated_at: Optional[datetime] = None


class VectorRepository(ABC):
    """Persistence + similarity search for review embeddings."""

    @abstractmethod
    def upsert(self, records: Sequence[ReviewVectorRecord]) -> int:
        """Insert or update records by fingerprint; returns rows written."""

    @abstractmethod
    def search(
        self,
        query_vector: Sequence[float],
        *,
        embedding_model: str,
        dimension: int,
        top_k: int,
        similarity_threshold: Optional[float] = None,
        filters: Optional[ReviewSearchFilters] = None,
    ) -> List[ReviewSearchResult]:
        """Return the ``top_k`` most similar reviews (cosine), optional filters."""

    @abstractmethod
    def existing_fingerprints(self, fingerprints: Sequence[str]) -> Set[str]:
        """Return the subset of fingerprints already stored (skip re-embedding)."""

    @abstractmethod
    def get_metadata(self, review_id: str) -> Optional[VectorMetadata]:
        """Return embedding metadata for a review id, if present."""

    @abstractmethod
    def count(self) -> int:
        """Total number of stored review embeddings."""
