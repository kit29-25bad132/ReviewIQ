"""Safe, bounded, resumable canonical embedding indexing.

Workflow (no step runs at import or startup; the CLI script drives it):

    canonical catalog rows
        -> build_canonical_records (stable R-ID / P-ID / verbatim text)
        -> plan_canonical_index (dry-run: zero provider calls, zero writes)
        -> run_canonical_index(limit, offset)  (explicit bound, one window)
            -> ReviewIndexingService.index (skip-existing, batched embed)
            -> delete superseded rows ONLY for review IDs whose replacement
               fingerprint is confirmed stored (insert-before-delete)
            -> abort (BLOCKED) on quota/credential errors, never hammer them

Identity contract: one embedding row per (canonical review, current text).
``review_fingerprint(product_id, normalized_text)`` is intentionally left
byte-stable — changing it would orphan all 1950 legacy rows into
re-embedding. Canonical and legacy rows are disjoint by product ID
(P01… vs ASINs), review ID (R00001… vs hex), and source identity, and every
canonical write/read is additionally scoped by source, so the corpora can
never collide or silently substitute for each other.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.embeddings.errors import EmbeddingErrorType
from services.retrieval.contracts import CANONICAL_REVIEW_SOURCE
from services.retrieval.deduplication import prepare_review
from services.retrieval.indexing_service import ReviewIndexingService
from services.retrieval.review_validation import validate_reviews

logger = logging.getLogger(__name__)

# Provider failures that must STOP a run instead of burning quota by
# retrying every remaining batch. Anything else is recorded per batch and
# the run continues; a rerun resumes the failed records idempotently.
ABORT_ERROR_TYPES = frozenset(
    {
        EmbeddingErrorType.RATE_LIMIT.value,
        EmbeddingErrorType.AUTHENTICATION.value,
    }
)

_DEFAULT_WINDOW_SIZE = 5000


def build_canonical_records(review_dicts: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Map canonical catalog rows to validation-ready records.

    Accepts both catalog shapes (``query_dataset_reviews`` and
    ``get_reviews`` keys). Review text passes through unmodified; provenance
    is the stable canonical ID pair plus the constant canonical source —
    never invented URLs.
    """
    records = []
    for row in review_dicts:
        review_id = row.get("source_review_id", row.get("id"))
        product_id = row.get("source_product_id", row.get("asin"))
        rating = row.get("rating", row.get("actual_rating"))
        sentiment = row.get("sentiment", row.get("actual_sentiment"))
        records.append(
            {
                "review_id": review_id,
                "product_id": product_id,
                "review_text": row.get("review_text"),
                "rating": rating,
                "sentiment": sentiment,
                "source": CANONICAL_REVIEW_SOURCE,
                "review_date": row.get("review_date"),
                "review_title": row.get("review_title", row.get("summary")),
            }
        )
    return records


def expected_fingerprints(
    records: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, str], List[Any]]:
    """Pure fingerprint computation: {review_id: fingerprint} + rejected rows.

    No IO, no provider calls. Uses the exact validate/prepare path the
    indexer uses, so dry-run expectations always agree with real runs.
    """
    validation = validate_reviews(list(records))
    expected: Dict[str, str] = {}
    for review in validation.accepted:
        prepared = prepare_review(review)
        rid = prepared.review_id
        if rid in expected and expected[rid] != prepared.fingerprint:
            continue  # first occurrence wins, mirroring dedupe_prepared
        expected.setdefault(rid, prepared.fingerprint)
    return expected, list(validation.rejected)


@dataclass(frozen=True)
class DryRunReport:
    """Read-only indexing plan: no provider calls, no database writes."""

    total_canonical: int
    valid_existing: int
    missing: int
    stale_rows: int
    stale_review_ids: int
    batches: int
    batch_size: int
    embedding_model: str
    embedding_dimension: int
    live_canonical_rows: int
    blockers: Tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)


@dataclass(frozen=True)
class RunReport:
    """Outcome of one bounded indexing window."""

    attempted: int
    skipped_already_indexed: int
    indexed: int
    updated: int
    failed: int
    stale_deleted: int
    invalid: int
    failed_review_ids: Tuple[str, ...] = ()
    blocked: bool = False
    block_reason: Optional[str] = None


def plan_canonical_index(
    catalog, repository, embedding_service, *, batch_size: Optional[int] = None
) -> DryRunReport:
    """Compute what a full canonical run would do, without doing it."""
    blockers: List[str] = []
    if not catalog.is_configured():
        blockers.append("canonical database is not configured (missing DATABASE_URL)")
    if not embedding_service.is_configured():
        blockers.append("embedding provider is not configured (missing GEMINI_API_KEY)")

    size = batch_size or embedding_service.batch_size
    model = embedding_service.model
    dimension = embedding_service.dimension

    total = 0
    rows: List[Dict[str, Any]] = []
    if catalog.is_configured():
        try:
            _, total = catalog.query_dataset_reviews(1, 0, None, None, None, None)
            if total:
                rows, _ = catalog.query_dataset_reviews(
                    min(total, _DEFAULT_WINDOW_SIZE), 0, None, None, None, None
                )
        except Exception as exc:
            blockers.append(f"canonical catalog read failed: {type(exc).__name__}")

    expected, _rejected = expected_fingerprints(build_canonical_records(rows))
    valid_existing = 0
    stale_rows = 0
    stale_ids = 0
    live_canonical_rows = 0
    if catalog.is_configured() and not any("catalog read failed" in b for b in blockers):
        try:
            stored = repository.fingerprints_by_review(CANONICAL_REVIEW_SOURCE)
            live_canonical_rows = sum(len(fps) for fps in stored.values())
            if expected:
                existing = repository.existing_fingerprints(list(expected.values()))
                valid_existing = len(set(expected.values()) & existing)
                for rid, fps in stored.items():
                    if rid in expected:
                        stale = fps - {expected[rid]}
                    else:
                        stale = set(fps)  # canonical-source row for an unknown review
                    if stale:
                        stale_ids += 1
                        stale_rows += len(stale)
        except Exception as exc:
            blockers.append(f"vector store read failed: {type(exc).__name__}")

    missing = max(0, len(expected) - valid_existing)
    batches = (missing + size - 1) // size if missing else 0
    return DryRunReport(
        total_canonical=total,
        valid_existing=valid_existing,
        missing=missing,
        stale_rows=stale_rows,
        stale_review_ids=stale_ids,
        batches=batches,
        batch_size=size,
        embedding_model=model,
        embedding_dimension=dimension,
        live_canonical_rows=live_canonical_rows,
        blockers=tuple(blockers),
    )


def run_canonical_index(
    catalog,
    repository,
    indexing_service: ReviewIndexingService,
    *,
    limit: int,
    offset: int = 0,
) -> RunReport:
    """Index one explicit window [offset, offset+limit) of canonical reviews.

    ``limit`` is REQUIRED and strictly positive: a run can never silently
    expand to the full corpus. Resume by re-invoking with the next offset;
    already-indexed fingerprints are skipped automatically, so rerunning any
    window (including after interruption) is safe and duplicate-free.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("A strictly positive explicit --limit is required (no unbounded runs).")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("offset must be a non-negative integer.")
    if not catalog.is_configured():
        return RunReport(0, 0, 0, 0, 0, 0, 0, (), True, "canonical database is not configured")
    if not indexing_service.embedding_service.is_configured():
        return RunReport(0, 0, 0, 0, 0, 0, 0, (), True, "embedding provider is not configured")

    rows, _total = catalog.query_dataset_reviews(limit, offset, None, None, None, None)
    records = build_canonical_records(rows)
    if not records:
        return RunReport(0, 0, 0, 0, 0, 0, 0, (), False, None)

    expected, _rejected = expected_fingerprints(records)
    pre_existing = repository.existing_fingerprints(list(expected.values()))

    report = indexing_service.index(records)

    post_existing = repository.existing_fingerprints(list(expected.values()))
    newly_persisted = set(post_existing) - set(pre_existing)
    indexed = int(report.indexed)
    updated = max(0, indexed - len(newly_persisted))

    failed_ids = tuple(report.failed_review_ids)

    # Stale replacement ONLY for review IDs whose current fingerprint is
    # confirmed stored (insert-before-delete). A failed batch keeps its old
    # rows untouched for a later retry.
    stale_deleted = 0
    for rid, fp in expected.items():
        if fp in post_existing:
            try:
                stale_deleted += repository.delete_stale_review_embeddings(
                    rid, fp, CANONICAL_REVIEW_SOURCE
                )
            except Exception:
                logger.warning("Stale cleanup failed for review %s; continuing.", rid, exc_info=True)

    blocked = False
    block_reason = None
    last_error = (report.metadata or {}).get("last_error_type")
    if report.failed and last_error in ABORT_ERROR_TYPES:
        blocked = True
        block_reason = f"provider {last_error}: stopping instead of burning quota"

    return RunReport(
        attempted=len(records),
        skipped_already_indexed=int(report.already_indexed),
        indexed=indexed,
        updated=updated,
        failed=int(report.failed),
        stale_deleted=stale_deleted,
        invalid=int(report.invalid),
        failed_review_ids=failed_ids,
        blocked=blocked,
        block_reason=block_reason,
    )
