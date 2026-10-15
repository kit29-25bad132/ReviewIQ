"""Product-scoped semantic review retrieval for the RAG query path (Phase 7D).

Composes the existing ``SemanticSearchService`` (never modified) with:

* product + canonical-source filtering (only the target product's reviews)
* a one-shot threshold fallback: when fewer than 3 results clear
  ``min_similarity`` (default 0.65) the query is retried once at 0.50
* retrieval-time near-duplicate suppression (token containment > 95%
  keeps only the higher-similarity copy — results arrive similarity-desc)

Never fabricates: an empty retrieval returns an empty list. Provider or
database failures raise ``EmbeddingError`` so callers can distinguish
unavailable from genuinely-empty.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.retrieval.contracts import CANONICAL_REVIEW_SOURCE
from services.retrieval.search_service import SemanticSearchService
from services.retrieval.vector_repository import ReviewSearchFilters, ReviewSearchResult

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 10
MAX_TOP_K = 20
DEFAULT_MIN_SIMILARITY = 0.65
FALLBACK_MIN_SIMILARITY = 0.5
MIN_RESULTS_BEFORE_FALLBACK = 3
DUPLICATE_OVERLAP_THRESHOLD = 0.95

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class RetrievedReview:
    """One review returned by retrieve_similar_reviews (real row, real score)."""

    review_id: str
    review_text: str
    similarity_score: float
    product_id: Optional[str]
    rating: Optional[int]
    source_review_id: str
    source: Optional[str] = None


@dataclass(frozen=True)
class RetrievalOutcome:
    """Reviews plus whether the 0.65 -> 0.50 threshold fallback fired (7F)."""

    reviews: Tuple[RetrievedReview, ...]
    fallback_triggered: bool


_search: Optional[SemanticSearchService] = None


def _search_service() -> SemanticSearchService:
    """Lazy singleton over the unchanged runtime builder (runtime.py)."""
    global _search
    if _search is None:
        from services.retrieval.runtime import build_search_service

        _search = build_search_service()
    return _search


def _text_overlap(a: str, b: str) -> float:
    """Containment of the shorter canonical token set in the longer one.

    overlap = |tokens(a) ∩ tokens(b)| / min(|tokens(a)|, |tokens(b)|)
    An empty side scores 0.0 (never a false duplicate).
    """
    tokens_a = set(_TOKEN_RE.findall((a or "").lower()))
    tokens_b = set(_TOKEN_RE.findall((b or "").lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def _deduplicate(
    results: List[ReviewSearchResult],
) -> Tuple[List[ReviewSearchResult], List[str]]:
    """Drop later results that share >95% token containment with a kept one.

    Input must already be sorted by descending similarity, so the kept copy
    is always the higher-similarity one.
    """
    kept: List[ReviewSearchResult] = []
    dropped_ids: List[str] = []
    for item in results:
        text = item.review_text or ""
        is_dup = any(
            _text_overlap(text, kept_item.review_text or "") > DUPLICATE_OVERLAP_THRESHOLD
            for kept_item in kept
        )
        if is_dup:
            dropped_ids.append(str(item.review_id))
            continue
        kept.append(item)
    return kept, dropped_ids


def _to_retrieved(item: ReviewSearchResult) -> RetrievedReview:
    review_id = str(item.review_id)
    return RetrievedReview(
        review_id=review_id,
        review_text=item.review_text or "",
        similarity_score=float(item.similarity),
        product_id=item.product_id if isinstance(item.product_id, str) else None,
        rating=item.rating if isinstance(item.rating, int) and not isinstance(item.rating, bool) else None,
        source_review_id=review_id,
        source=item.source if isinstance(item.source, str) else None,
    )


def retrieve_similar_reviews_detailed(
    query_text: str,
    product_id: str,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> RetrievalOutcome:
    """Same retrieval as retrieve_similar_reviews plus fallback metadata.

    Raises EmbeddingError for invalid input / provider / database failures.
    Returns an empty reviews tuple when nothing clears the threshold —
    never invents results.
    """
    if not isinstance(query_text, str) or not query_text.strip():
        raise EmbeddingError(
            "A non-empty query_text is required.", EmbeddingErrorType.INVALID_INPUT
        )
    if not isinstance(product_id, str) or not product_id.strip():
        raise EmbeddingError(
            "A non-empty product_id is required.", EmbeddingErrorType.INVALID_INPUT
        )
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_TOP_K:
        raise EmbeddingError(
            f"top_k must be an integer between 1 and {MAX_TOP_K}.",
            EmbeddingErrorType.INVALID_INPUT,
        )
    if not isinstance(min_similarity, (int, float)) or isinstance(min_similarity, bool):
        raise EmbeddingError(
            "min_similarity must be a number.", EmbeddingErrorType.INVALID_INPUT
        )
    if not -1.0 <= float(min_similarity) <= 1.0:
        raise EmbeddingError(
            "min_similarity must be between -1 and 1.",
            EmbeddingErrorType.INVALID_INPUT,
        )

    filters = ReviewSearchFilters(
        product_id=product_id.strip(), source=CANONICAL_REVIEW_SOURCE
    )
    service = _search_service()
    outcome = service.search(
        query_text,
        top_k=top_k,
        similarity_threshold=float(min_similarity),
        filters=filters,
    )
    results = list(outcome.results)

    fallback_triggered = False
    if (
        0 < len(results) < MIN_RESULTS_BEFORE_FALLBACK
        and float(min_similarity) > FALLBACK_MIN_SIMILARITY
    ):
        fallback_triggered = True
        logger.warning(
            "retrieve_similar_reviews: %d result(s) above %.2f for product %s; "
            "retrying once at threshold %.2f",
            len(results),
            float(min_similarity),
            product_id,
            FALLBACK_MIN_SIMILARITY,
        )
        outcome = service.search(
            query_text,
            top_k=top_k,
            similarity_threshold=FALLBACK_MIN_SIMILARITY,
            filters=filters,
        )
        results = list(outcome.results)

    kept, dropped_ids = _deduplicate(results)
    if dropped_ids:
        logger.info(
            "retrieve_similar_reviews: dropped %d near-duplicate result(s): %s",
            len(dropped_ids),
            ", ".join(dropped_ids),
        )
    return RetrievalOutcome(
        reviews=tuple(_to_retrieved(item) for item in kept),
        fallback_triggered=fallback_triggered,
    )


def retrieve_similar_reviews(
    query_text: str,
    product_id: str,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> List[RetrievedReview]:
    """Return the target product's most similar real reviews.

    Thin delegate over retrieve_similar_reviews_detailed; signature, return
    type, and behavior are unchanged from the 7D contract.
    """
    return list(
        retrieve_similar_reviews_detailed(
            query_text, product_id, top_k=top_k, min_similarity=min_similarity
        ).reviews
    )
