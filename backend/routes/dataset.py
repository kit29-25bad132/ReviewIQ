import logging
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from models.dataset import DatasetReviewsResponse
from services.dataset_service import DatasetUnavailableError, dataset_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dataset", tags=["Dataset"])


@router.get("/reviews", response_model=DatasetReviewsResponse)
def get_reviews(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), search: Optional[str] = None, rating: Optional[int] = Query(None, ge=1, le=5), sentiment: Optional[Literal["positive", "neutral", "negative"]] = None, product: Optional[str] = None):
    try:
        items, total = dataset_service.query(limit, offset, search, rating, sentiment, product)
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
