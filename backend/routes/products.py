from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from models.ecommerce import (
    ProductSummary,
    ProductSearchResponse,
    ProductAnalysisResponse,
    AISummaryResponse,
    ProsConsAnalysisResponse,
    ReviewItem,
    UserRequirementRequest,
    PersonalizedRecommendationResponse,
)
from services.ecommerce_db_service import ecommerce_db_service
from services.gemini_summary_service import gemini_summary_service
from services.pros_cons_service import pros_cons_service
from services.recommendation_service import recommendation_service

router = APIRouter(prefix="/api/products", tags=["Product Search & Intelligence"])


@router.get(
    "/search",
    response_model=ProductSearchResponse,
    summary="Search products in the review dataset",
)
def search_products(
    q: Optional[str] = Query(None, description="Product title or keyword"),
    limit: int = Query(20, ge=1, le=100, description="Max products to return"),
):
    """
    Searches the 4M-row dataset using priority matching:
    1. Exact product title match
    2. Case-insensitive exact match
    3. Prefix match
    4. Substring match
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    products = ecommerce_db_service.search_products(q or "", limit=limit)

    if not products:
        return ProductSearchResponse(
            found=False,
            products=[],
            message="Product not found in the available review dataset.",
        )

    return ProductSearchResponse(
        found=True,
        products=products,
        message=None,
    )


@router.get(
    "/{product_id}/analysis",
    response_model=ProductAnalysisResponse,
    summary="Get complete dataset analytics for a specific product",
)
def get_product_analysis(product_id: str):
    """
    Retrieves real dataset statistics for a product:
    - Review count
    - Average rating
    - 1-5 star distributions
    - Sentiment distributions
    - Recent actual customer reviews
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    analysis = ecommerce_db_service.get_product_analysis(product_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in the available review dataset.",
        )

    return analysis


@router.get(
    "/{product_id}/pros-cons",
    response_model=ProsConsAnalysisResponse,
    summary="Get quantified product-level Pros and Cons with evidence tracing",
)
def get_product_pros_cons(product_id: str):
    """
    Analyzes reviews from the dataset for the selected product and generates:
    - Common Pros with review counts & percentages
    - Common Cons with review counts & percentages
    - Real evidence review examples
    - Overall customer synthesis & authenticity signals
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    analysis = pros_cons_service.analyze_product_pros_cons(product_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in the available review dataset.",
        )

    return analysis


@router.get(
    "/{product_id}/theme-reviews",
    response_model=List[ReviewItem],
    summary="Retrieve actual supporting reviews for a specific Pro/Con theme",
)
def get_theme_supporting_reviews(
    product_id: str,
    theme: str = Query(..., description="Theme name to find supporting reviews for"),
    sentiment: Optional[str] = Query(None, description="Filter sentiment ('positive' or 'negative')"),
    limit: int = Query(50, ge=1, le=200, description="Max supporting reviews to return"),
):
    """
    Returns actual unmodified review_text rows from the dataset supporting a specific Pro or Con theme.
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    return pros_cons_service.get_theme_reviews(
        product_id=product_id,
        theme=theme,
        sentiment=sentiment,
        limit=limit,
    )


@router.get(
    "/{product_id}/similar",
    response_model=List[ProductSummary],
    summary="Get similar products in the same category from the dataset",
)
def get_similar_products(
    product_id: str,
    limit: int = Query(3, ge=1, le=10, description="Max similar products"),
):
    """
    Finds peer products in the same dataset category for side-by-side comparison.
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    return recommendation_service.get_similar_products(product_id, limit=limit)


@router.post(
    "/{product_id}/recommendation",
    response_model=PersonalizedRecommendationResponse,
    summary="Generate personalized product recommendation and side-by-side comparison",
)
def get_personalized_recommendation(
    product_id: str,
    req: UserRequirementRequest,
):
    """
    Evaluates user priorities and compares the selected product against alternatives in the dataset.
    Provides evidence-based decision guidance and 'Is this suitable for you?' analysis.
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    rec = recommendation_service.generate_recommendation(product_id, req)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in the available review dataset.",
        )

    return rec


@router.post(
    "/{product_id}/ai-summary",
    response_model=AISummaryResponse,
    summary="Generate AI summary strictly from retrieved dataset reviews",
)
def generate_ai_summary(product_id: str):
    """
    Uses Google Gemini to synthesize ONLY reviews retrieved from the dataset for this product.
    Zero hallucination or fabricated reviews allowed.
    """
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    analysis = ecommerce_db_service.get_product_analysis(product_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found in the available review dataset.",
        )

    sample_reviews = ecommerce_db_service.get_sample_reviews(product_id, limit=40)
    return gemini_summary_service.summarize_product_reviews(
        product_title=analysis.product.product_title,
        category=analysis.product.category,
        sample_reviews=sample_reviews,
    )
