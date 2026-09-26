"""Review indexing service (synchronous batch).

Pipeline per call:

    raw reviews
        -> validation (explicit outcomes)
        -> preprocessing + deduplication (deterministic fingerprints)
        -> skip fingerprints already stored  (avoid redundant embedding work)
        -> embedding provider (batched, dimension-validated)
        -> vector repository upsert

Duplicates are not re-embedded, and a failed batch is reported by review id
rather than silently dropped. No job queue is introduced in this milestone.
"""

import logging
from typing import List, Optional, Sequence

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.embeddings.service import EmbeddingService
from services.embeddings.contracts import EmbeddingTaskType
from services.retrieval.contracts import (
    IndexingReport,
    PreparedReview,
    ValidatedReview,
)
from services.retrieval.deduplication import dedupe_prepared, prepare_review
from services.retrieval.review_validation import validate_reviews
from services.retrieval.vector_repository import ReviewVectorRecord, VectorRepository

logger = logging.getLogger(__name__)


class ReviewIndexingService:
    """Validates, deduplicates, embeds, and stores reviews."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_repository: VectorRepository,
        *,
        batch_size: Optional[int] = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_repository = vector_repository
        self._batch_size = batch_size or embedding_service.batch_size

    @property
    def embedding_service(self) -> EmbeddingService:
        return self._embedding_service

    def index(self, records: Sequence[object]) -> IndexingReport:
        raw_records = list(records)
        validation = validate_reviews(raw_records)

        prepared = [prepare_review(review) for review in validation.accepted]
        dedup = dedupe_prepared(prepared)

        accepted_fingerprints = [item.fingerprint for item in dedup.accepted]
        already = self._vector_repository.existing_fingerprints(accepted_fingerprints)
        to_embed = [
            item for item in dedup.accepted if item.fingerprint not in already
        ]
        already_indexed = len(dedup.accepted) - len(to_embed)

        indexed = 0
        failed_ids: List[str] = []
        last_error_type: Optional[EmbeddingErrorType] = None

        for start in range(0, len(to_embed), self._batch_size):
            batch = to_embed[start : start + self._batch_size]
            try:
                vectors = self._embedding_service.embed_batch(
                    [item.normalized_text for item in batch],
                    task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
                )
                if len(vectors) != len(batch):
                    raise EmbeddingError(
                        f"Embedding provider returned {len(vectors)} vectors for "
                        f"{len(batch)} reviews.",
                        EmbeddingErrorType.INVALID_RESPONSE,
                    )
                records_to_store = [
                    self._build_record(item, vector)
                    for item, vector in zip(batch, vectors)
                ]
                indexed += self._vector_repository.upsert(records_to_store)
            except EmbeddingError as exc:
                # Partial failure: report the affected reviews, keep going.
                last_error_type = exc.error_type
                failed_ids.extend(item.review_id for item in batch)
                logger.warning(
                    "Indexing batch failed (%s): %s", exc.error_type.value, exc
                )

        return IndexingReport(
            received=len(raw_records),
            accepted=len(validation.accepted),
            duplicates=len(dedup.duplicates),
            invalid=len(validation.rejected),
            already_indexed=already_indexed,
            indexed=indexed,
            failed=len(failed_ids),
            rejected=validation.rejected,
            failed_review_ids=tuple(failed_ids),
            embedding_model=self._embedding_service.model,
            embedding_dimension=self._embedding_service.dimension,
            metadata=(
                {"last_error_type": last_error_type.value}
                if last_error_type is not None
                else {}
            ),
        )

    def _build_record(
        self, prepared: PreparedReview, vector: Sequence[float]
    ) -> ReviewVectorRecord:
        review: ValidatedReview = prepared.review
        return ReviewVectorRecord(
            review_id=prepared.review_id,
            product_id=review.product_id,
            fingerprint=prepared.fingerprint,
            original_text=review.review_text,
            normalized_text=prepared.normalized_text,
            embedding=list(vector),
            embedding_model=self._embedding_service.model,
            embedding_dimension=self._embedding_service.dimension,
            rating=review.rating,
            source=review.source,
            review_date=review.review_date,
        )
