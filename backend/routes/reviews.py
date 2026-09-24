from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from models.ecommerce import ReviewsPaginationResponse
from services.ecommerce_db_service import ecommerce_db_service

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
    Returns actual unmodified review_text rows from the dataset with full SQL-level pagination and filtering.
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    return ecommerce_db_service.get_product_reviews(
        product_id=product_id,
        page=page,
        limit=limit,
        rating=rating,
        sentiment=sentiment,
    )
