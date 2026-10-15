import math
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status

from models.ecommerce import ReviewItem
from models.intelligence import ReviewPage
from services.catalog.catalog_service import canonical_catalog

router = APIRouter(prefix="/api/products", tags=["Product Reviews"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.get(
    "/{product_id}/reviews",
    response_model=ReviewPage,
    summary="Get paginated actual reviews for a product from the dataset",
)
def get_product_reviews(
    product_id: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: Optional[int] = Query(
        None, ge=1, le=MAX_PAGE_SIZE, description="Items per page"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=MAX_PAGE_SIZE, description="Deprecated alias of page_size"
    ),
    sort: Literal["rating_desc", "rating_asc", "date_desc", "date_asc"] = Query(
        "date_desc",
        description="Sort order: rating_desc, rating_asc, date_desc, or date_asc",
    ),
    filter_rating: Optional[int] = Query(
        None, ge=1, le=5, description="Only reviews with this exact 1-5 star rating"
    ),
    rating: Optional[int] = Query(
        None, ge=1, le=5, description="Deprecated alias of filter_rating"
    ),
    sentiment: Optional[str] = Query(
        None, description="Filter by sentiment ('positive', 'neutral', 'negative')"
    ),
):
    """
    Returns actual unmodified canonical review_text rows with SQL-level
    filtering, sorting, and pagination — no in-memory filtering. Served
    exclusively by CanonicalCatalogService; unknown products return 404
    (distinct from a valid product with zero reviews, which returns an empty
    page). Database errors propagate to the global handler (HTTP 500) rather
    than being masked by legacy data.

    5E accepts the canonical ``page_size`` / ``sort`` / ``filter_rating``
    parameters. The legacy ``limit`` and ``rating`` aliases remain accepted
    (the canonical name wins when both are supplied) so existing clients keep
    working until 5H rewires them.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
        )

    resolved_page_size = page_size if page_size is not None else (limit or DEFAULT_PAGE_SIZE)
    resolved_rating = filter_rating if filter_rating is not None else rating

    clean_pid = str(product_id).strip()
    product = canonical_catalog.get_product_by_id(clean_pid)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    reviews, total = canonical_catalog.get_reviews(
        clean_pid,
        rating=resolved_rating,
        sentiment=sentiment,
        page=page,
        page_size=resolved_page_size,
        sort_by=sort,
        product=product,
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

    total_pages = math.ceil(total / resolved_page_size) if total > 0 else 0

    return ReviewPage(
        items=items,
        total_count=total,
        page=page,
        page_size=resolved_page_size,
        total_pages=total_pages,
        total=total,
        limit=resolved_page_size,
    )
