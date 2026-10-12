"""Phase 5G — product intelligence orchestration and error states.

Composes the real stages into one payload and makes every degenerate case
explicit rather than accidental:

* unknown product            -> ``product_not_found`` (route returns 404)
* product with 0 reviews     -> zeros + "Insufficient reviews" (HTTP 200)
* fewer than ``LOW_REVIEW_THRESHOLD`` reviews -> computed, flagged
  ``low_review_count``
* LLM unavailable/invalid    -> real statistics kept, ``ai_unavailable`` true,
  empty AI fields
* payload fails validation   -> a safe statistics-only fallback is returned;
  if even that cannot validate, a structured error is returned instead of a
  partial payload or a 500

Statistics are always computed first and never depend on the AI stages, which
is what makes the AI-optional behavior possible.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple

from models.intelligence import (
    INSUFFICIENT_REVIEWS_SUMMARY,
    AnalysisErrorResponse,
    AspectResult,
    ClaimWithEvidence,
    DateRange,
    ProductAnalysisResponse,
    ProductStatistics,
    validate_analysis_response,
)
from services.intelligence.aspects import extract_aspects
from services.intelligence.pros_cons import generate_pros_cons
from services.intelligence.statistics import ProductStatisticsData, compute_statistics
from services.intelligence.summary import generate_summary

logger = logging.getLogger(__name__)

#: Below this many reviews the analysis is flagged as low-confidence.
LOW_REVIEW_THRESHOLD = 5


def _to_contract_statistics(stats: ProductStatisticsData) -> ProductStatistics:
    return ProductStatistics(
        total_reviews=stats.total_reviews,
        average_rating=stats.average_rating,
        rating_distribution=stats.rating_distribution,
        sentiment_distribution=stats.sentiment_distribution,
        verified_purchase_pct=stats.verified_purchase_pct,
        date_range=DateRange(
            earliest=stats.date_range.earliest, latest=stats.date_range.latest
        ),
    )


def _assemble(
    stats: ProductStatisticsData,
    *,
    aspects: List[AspectResult],
    pros: List[ClaimWithEvidence],
    cons: List[ClaimWithEvidence],
    summary: str,
    best_for: str,
    review_count_used: int,
    ai_unavailable: bool,
) -> ProductAnalysisResponse:
    return ProductAnalysisResponse(
        product_id=stats.source_product_id,
        product_name=stats.product_name,
        statistics=_to_contract_statistics(stats),
        aspects=aspects,
        pros=pros,
        cons=cons,
        summary=summary,
        best_for=best_for,
        data_source="supabase",
        review_count_used=review_count_used,
        generated_at=datetime.now(timezone.utc),
        low_review_count=0 < stats.total_reviews < LOW_REVIEW_THRESHOLD,
        ai_unavailable=ai_unavailable,
    )


def _safe_fallback(
    stats: ProductStatisticsData,
) -> Tuple[Optional[ProductAnalysisResponse], Optional[AnalysisErrorResponse]]:
    """Statistics-only payload; used when the full payload fails validation."""
    try:
        fallback = _assemble(
            stats,
            aspects=[],
            pros=[],
            cons=[],
            summary=INSUFFICIENT_REVIEWS_SUMMARY if stats.total_reviews == 0 else "",
            best_for="",
            review_count_used=0 if stats.total_reviews == 0 else stats.total_reviews,
            ai_unavailable=stats.total_reviews > 0,
        )
        ProductAnalysisResponse.model_validate(fallback.model_dump())
        return fallback, None
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Statistics-only fallback failed for %s: %s", stats.source_product_id, exc)
        return None, AnalysisErrorResponse(
            code="validation_error",
            error="The product analysis could not be produced safely.",
            detail="Fallback payload also failed validation.",
        )


def _run_stage(
    fn: Callable[..., Any],
    product_id: str,
    label: str,
    default: Any,
    **kwargs: Any,
) -> Any:
    """Run one AI stage, degrading to ``default`` on any failure.

    No stage may take the whole request down: a failed summary means
    ``ai_unavailable``, not a 500.
    """
    try:
        return fn(product_id, **kwargs)
    except Exception as exc:
        logger.warning("%s stage crashed for %s: %s", label, product_id, exc)
        return default


def analyze_product(
    product_id_or_source_id: str,
) -> Tuple[Optional[ProductAnalysisResponse], Optional[AnalysisErrorResponse]]:
    """Produce the Phase 5 payload, or a structured error. Never raises."""
    clean_id = str(product_id_or_source_id).strip()

    # 1. Statistics first: always computable from the database, AI-independent.
    try:
        stats = compute_statistics(clean_id)
    except Exception as exc:
        # A database failure is a real infrastructure error, not a data state.
        logger.error("Statistics query failed for %s: %s", clean_id, exc)
        raise

    if stats is None:
        return None, AnalysisErrorResponse(
            code="product_not_found",
            error="Product not found.",
            detail=f"No canonical product matches '{clean_id}'.",
        )

    # 2. Zero reviews is a valid product with nothing to summarize.
    if stats.total_reviews == 0:
        response, error = _safe_fallback(stats)
        return response, error

    # 3. AI stages. Each degrades independently to an empty result.
    #
    # Aspect extraction and pros/cons are independent, and each costs a full
    # provider round trip (~25-30s), so they run concurrently. The summary
    # needs the aspects, so it necessarily follows. Sequential execution cost
    # ~96s end-to-end; this keeps the endpoint inside a browser timeout.
    with ThreadPoolExecutor(max_workers=2) as pool:
        aspects_future = pool.submit(_run_stage, extract_aspects, clean_id, "aspects", [])
        claims_future = pool.submit(
            _run_stage, generate_pros_cons, clean_id, "pros/cons", ([], [])
        )
        aspects = aspects_future.result()
        pros, cons = claims_future.result()

    draft = _run_stage(generate_summary, clean_id, "summary", None, aspects=aspects)

    # 4. No usable summary means the AI stage failed: keep statistics only.
    if draft is None:
        logger.warning(
            "AI unavailable for %s; returning database statistics only", clean_id
        )
        return _safe_fallback(stats)

    try:
        payload = _assemble(
            stats,
            aspects=aspects,
            pros=pros,
            cons=cons,
            summary=draft.summary,
            best_for=draft.best_for,
            review_count_used=stats.total_reviews,
            ai_unavailable=False,
        )
    except Exception as exc:
        # Unexpected assembly failure: degrade to real statistics rather than
        # surfacing an internal error to the user.
        logger.error("Payload assembly failed for %s: %s", clean_id, exc)
        return _safe_fallback(stats)

    # 5. Enforce the contract; never hand back a partially-invalid payload.
    validated = validate_analysis_response(payload.model_dump())
    if isinstance(validated, AnalysisErrorResponse):
        logger.error(
            "Product analysis payload failed validation for %s; using fallback",
            clean_id,
        )
        return _safe_fallback(stats)

    return validated, None
