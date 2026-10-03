import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status

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
    summary="Get complete dataset analytics and AI synthesis for a specific product",
)
@router.post(
    "/{product_id}/analyze",
    response_model=ProductAnalysisResponse,
    summary="Analyze a product from real database reviews with Gemini AI",
)
def get_product_analysis(product_id: str, response: Response):
    """
    Retrieves real database statistics and grounded AI analysis for a product:
    - Factual metrics calculated directly from database reviews
    - Grounded Gemini AI synthesis strictly from retrieved reviews
    - Returns 404 with clear message if product has insufficient review data
    """
    t_start = time.perf_counter()
    if not ecommerce_db_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review dataset is currently indexing. Please try again shortly.",
        )

    clean_pid = str(product_id).strip()
    gemini_model = "gemini-3.8-flash"
    dataset_version = ecommerce_db_service.get_dataset_version(clean_pid)
    cached_check = gemini_summary_service.product_cache.get(clean_pid, dataset_version, gemini_model)
    cache_status = "HIT" if cached_check is not None else "MISS"

    t_db_start = time.perf_counter()
    analysis = ecommerce_db_service.get_product_analysis(clean_pid)
    db_ms = (time.perf_counter() - t_db_start) * 1000

    if not analysis or analysis.total_reviews == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    # Validate that product_id matches the requested product
    if str(analysis.product_id) != clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product ID mismatch in analysis response.",
        )

    if cached_check is not None:
        analysis.summary = cached_check.summary
        analysis.pros = cached_check.pros
        analysis.cons = cached_check.cons
        analysis.insights = cached_check.insights
        analysis.evidence = cached_check.evidence
        analysis.ai_available = True
        ai_ms = 0.0
    else:
        ai_ms = 0.0

        # Attempt AI analysis grounded strictly in retrieved database reviews
        sample_reviews = ecommerce_db_service.get_sample_reviews(clean_pid, limit=40)
        if sample_reviews:
            t_ai_start = time.perf_counter()
            try:
                ai_data = gemini_summary_service.generate_product_analysis(
                    product_id=clean_pid,
                    product_title=analysis.product_title,
                    category=analysis.category,
                    sample_reviews=sample_reviews,
                    dataset_version=dataset_version,
                )
                ai_ms = (time.perf_counter() - t_ai_start) * 1000
                if ai_data:
                    analysis.summary = ai_data.summary
                    analysis.pros = ai_data.pros
                    analysis.cons = ai_data.cons
                    analysis.insights = ai_data.insights
                    analysis.evidence = ai_data.evidence
                    analysis.ai_available = True
            except Exception:
                ai_ms = (time.perf_counter() - t_ai_start) * 1000
                # If Gemini fails, keep factual database metrics and mark AI analysis unavailable
                analysis.ai_available = False

    total_ms = (time.perf_counter() - t_start) * 1000

    if response is not None:
        response.headers["Server-Timing"] = f"db;dur={db_ms:.1f}, ai;dur={ai_ms:.1f}, total;dur={total_ms:.1f}"
        response.headers["X-Cache-Status"] = cache_status
        response.headers["X-Dataset-Version"] = dataset_version
        response.headers["X-Total-Duration-Ms"] = f"{total_ms:.1f}"

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

    clean_pid = str(product_id).strip()
    analysis = pros_cons_service.analyze_product_pros_cons(clean_pid)
    if not analysis or analysis.total_analyzed_reviews == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    # Validate that product_id matches
    if str(analysis.product_id) != clean_pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product ID mismatch in pros/cons response.",
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

    clean_pid = str(product_id).strip()
    return pros_cons_service.get_theme_reviews(
        product_id=clean_pid,
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

    clean_pid = str(product_id).strip()
    return recommendation_service.get_similar_products(clean_pid, limit=limit)


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

    clean_pid = str(product_id).strip()
    rec = recommendation_service.generate_recommendation(clean_pid, req)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
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

    clean_pid = str(product_id).strip()
    analysis = ecommerce_db_service.get_product_analysis(clean_pid)
    if not analysis or analysis.total_reviews == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    sample_reviews = ecommerce_db_service.get_sample_reviews(clean_pid, limit=40)
    if not sample_reviews:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    return gemini_summary_service.summarize_product_reviews(
        product_title=analysis.product_title,
        category=analysis.category,
        sample_reviews=sample_reviews,
    )

