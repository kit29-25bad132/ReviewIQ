import math
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from models.ecommerce import ReviewItem, ReviewsPaginationResponse
from services.catalog.catalog_service import canonical_catalog

router = APIRouter(prefix="/api/products", tags=["Product Reviews"])


@router.get(
    "/{product_id}/reviews",
    response_model=ReviewsPaginationResponse,
    summary="Get paginated actual reviews for a product from the dataset",
)
def get_product_reviews(
    product_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by exact 1-5 star rating"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment ('positive', 'neutral', 'negative')"),
):
    """
    Returns actual unmodified canonical review_text rows with SQL-level
    pagination and filtering. Served exclusively by CanonicalCatalogService;
    unknown products return 404 (distinct from a valid product with zero
    reviews, which returns an empty page). Database errors propagate to the
    global handler (HTTP 500) rather than being masked by legacy data.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
        )

    clean_pid = str(product_id).strip()
    product = canonical_catalog.get_product_by_id(clean_pid)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    reviews, total = canonical_catalog.get_reviews(
        clean_pid,
        rating=rating,
        sentiment=sentiment,
        page=page,
        page_size=limit,
    )

    items = [
        ReviewItem(
            id=str(r["source_review_id"]),
            product_id=str(r["source_product_id"]),
            product_title=str(product["product_title"]),
            category=product["category"],
            review_text=str(r["review_text"]),
            rating=int(r["rating"]),
            sentiment=str(r.get("sentiment", "neutral")),
        )
        for r in reviews
    ]

    total_pages = math.ceil(total / limit) if total > 0 else 0

    return ReviewsPaginationResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )
