"""Phase 5 intelligence endpoint.

``GET /api/products/{product_id}/intelligence`` is the canonical Phase 5
surface. It is additive: the legacy ``/analysis`` endpoint keeps working until
the frontend has been rewired (5H) and the old shape is removed.

Error mapping:
* unknown product            -> 404 with a clear message
* product with 0 reviews      -> 200, zeros + "Insufficient reviews"
* fewer than 5 reviews        -> 200 with ``low_review_count: true``
* AI unavailable              -> 200 with ``ai_unavailable: true`` and empty AI
  fields, keeping the real database statistics
* payload validation failure  -> 200 with a structured error body (never a
  partial payload, never a 500)
"""

import logging
from typing import Union

from fastapi import APIRouter, HTTPException, status

from models.intelligence import AnalysisErrorResponse, ProductAnalysisResponse
from services.catalog.catalog_service import canonical_catalog
from services.intelligence.analyzer import analyze_product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["Product Intelligence"])


@router.get(
    "/{product_id}/intelligence",
    response_model=Union[ProductAnalysisResponse, AnalysisErrorResponse],
    summary="Real product intelligence: statistics, aspects, pros/cons, and a grounded summary",
)
def get_product_intelligence(product_id: str):
    """Serve the full Phase 5 payload built exclusively from real review data.

    Served solely by the canonical Supabase catalog; there is no SQLite
    fallback. Database errors propagate to the global handler (HTTP 500)
    rather than being masked by legacy data.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
        )

    response, error = analyze_product(product_id)

    if error is not None:
        if error.code == "product_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error.error,
            )
        # A validation failure still returns a structured body, never a 500.
        logger.error("Intelligence analysis returned a structured error: %s", error.code)
        return error

    return response
