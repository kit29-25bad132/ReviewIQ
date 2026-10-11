import logging
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from models.dataset import DatasetReview, DatasetReviewsResponse
from services.catalog.catalog_service import canonical_catalog
from services.dataset_service import DatasetUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dataset", tags=["Dataset"])


@router.get("/reviews", response_model=DatasetReviewsResponse)
def get_reviews(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), search: Optional[str] = None, rating: Optional[int] = Query(None, ge=1, le=5), sentiment: Optional[Literal["positive", "neutral", "negative"]] = None, product: Optional[str] = None):
    """Explores the canonical Supabase review corpus with search, filters,
    and pagination. Record IDs and product IDs are the stable canonical
    identifiers. Served exclusively by CanonicalCatalogService; no CSV
    fallback. `total_vote` has no canonical counterpart and is null."""
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Review dataset is currently unavailable. Please try again later.",
        )
    try:
        rows, total = canonical_catalog.query_dataset_reviews(limit, offset, search, rating, sentiment, product)
        items = [
            DatasetReview(
                id=r["id"],
                asin=r["asin"],
                product_name=r["product_name"],
                review_text=r["review_text"],
                actual_rating=r["actual_rating"],
                summary=r["summary"],
                review_date=r["review_date"],
                helpful_yes=r["helpful_yes"],
                total_vote=r["total_vote"],
                actual_sentiment=r["actual_sentiment"],
            )
            for r in rows
        ]
        return DatasetReviewsResponse(items=items, total=total, limit=limit, offset=offset)
    except DatasetUnavailableError as exc:
        logger.warning("Dataset unavailable: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Review dataset is currently unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.error("Unexpected dataset query error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Review dataset is currently unavailable. Please try again later.",
        )
