import logging
from fastapi import APIRouter, HTTPException, Query
from models.dataset import OverviewAnalytics, ProductAnalytics
from services.catalog.catalog_service import canonical_catalog
from services.dataset_service import DatasetUnavailableError
from services.evaluation_service import evaluation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview", response_model=OverviewAnalytics)
def overview():
    """Corpus-wide totals derived from the canonical Supabase reviews table
    in a single aggregate query. Served exclusively by
    CanonicalCatalogService; no CSV fallback. Sentiment counts are derived
    from stored metadata labels (unknown folded into neutral)."""
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Analytics service is currently unavailable. Please try again later.",
        )
    try:
        agg = canonical_catalog.get_overview_analytics()
        return OverviewAnalytics(
            total_reviews=agg["total_reviews"],
            average_rating=agg["average_rating"],
            positive_reviews=agg["positive_reviews"],
            neutral_reviews=agg["neutral_reviews"],
            negative_reviews=agg["negative_reviews"],
            rating_distribution=agg["rating_distribution"],
        )
    except DatasetUnavailableError as exc:
        logger.warning("Analytics overview unavailable: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Analytics service is currently unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.error("Unexpected analytics overview error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Analytics service is currently unavailable. Please try again later.",
        )


@router.get("/products", response_model=list[ProductAnalytics])
def products(limit: int = Query(100, ge=1, le=500)):
    """Per-product aggregates from the canonical Supabase catalog in a single
    grouped query. AI-rating predictions reuse the persisted evaluation
    cache, which is keyed by stable canonical review IDs; products without
    cached predictions honestly report null. No CSV fallback."""
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Analytics service is currently unavailable. Please try again later.",
        )
    try:
        rows = canonical_catalog.get_product_analytics(limit=limit)
        cache = evaluation_service._cache()
        result = []
        for row in rows:
            predictions = [
                cache[rid]["predicted_rating"]
                for rid in row["review_ids"]
                if rid in cache and isinstance(cache[rid].get("predicted_rating"), int)
            ]
            result.append(ProductAnalytics(
                asin=row["source_product_id"],
                product_name=row["product_name"],
                review_count=row["review_count"],
                average_actual_rating=row["average_rating"],
                average_ai_rating=round(sum(predictions) / len(predictions), 2) if predictions else None,
                positive_reviews=row["positive_reviews"],
                neutral_reviews=row["neutral_reviews"],
                negative_reviews=row["negative_reviews"],
                helpful_votes=row["helpful_votes"],
            ))
        return result
    except DatasetUnavailableError as exc:
        logger.warning("Product analytics unavailable: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Analytics service is currently unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.error("Unexpected product analytics error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Analytics service is currently unavailable. Please try again later.",
        )
