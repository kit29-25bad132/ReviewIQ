import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status

from models.ecommerce import (
    ProductSummary,
    ProductSearchResponse,
    ProductAnalysisResponse,
    ProductStatistics,
    AISummaryResponse,
    ProsConsAnalysisResponse,
    ReviewItem,
    UserRequirementRequest,
    PersonalizedRecommendationResponse,
)
from services.catalog.catalog_service import canonical_catalog
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
    Searches the canonical Supabase product catalog by name, brand,
    category, or product ID (ILIKE match), ordered by review count.
    Served exclusively by CanonicalCatalogService; there is no SQLite
    fallback. Database errors propagate to the global handler (HTTP 500)
    rather than being masked by legacy data.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
        )

    product_dicts, _ = canonical_catalog.get_products(search=q or "", limit=limit)
    products = [
        ProductSummary(
            product_id=d["product_id"],
            product_title=d["product_title"],
            category=d["category"],
            review_count=d["review_count"],
            average_rating=d["average_rating"],
        )
        for d in product_dicts
    ]

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


def format_canonical_samples(review_dicts: List[dict]) -> List[str]:
    """Formats canonical review dicts into the grounded sample strings the
    product AI consumes: "[Review <stable-id> | <sentiment> | <rating>★] text".

    The review text itself is passed through unmodified so evidence
    grounding validates against verbatim canonical content.
    """
    samples = []
    for r in review_dicts:
        samples.append(
            f"[Review {r.get('source_review_id')} | {r.get('sentiment', 'neutral')} | {r.get('rating')}★] {r.get('review_text', '')}"
        )
    return samples


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
    Retrieves canonical statistics and grounded AI analysis for a product:
    - Factual metrics calculated directly from canonical Supabase reviews
    - Grounded Gemini AI synthesis strictly from retrieved canonical reviews
    - Returns 404 with clear message if product has insufficient review data
    Served exclusively by CanonicalCatalogService; there is no SQLite
    fallback. Database errors propagate to the global handler (HTTP 500)
    rather than being masked by legacy data.
    """
    t_start = time.perf_counter()
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
        )

    clean_pid = str(product_id).strip()
    gemini_model = "gemini-3.8-flash"
    dataset_version = canonical_catalog.get_dataset_version()
    cached_check = gemini_summary_service.product_cache.get(clean_pid, dataset_version, gemini_model)
    cache_status = "HIT" if cached_check is not None else "MISS"

    t_db_start = time.perf_counter()
    # Resolve once: the statistics and review calls below reuse this product
    # instead of each re-resolving it (one connection saved per call).
    resolved_product = canonical_catalog.get_product_by_id(clean_pid)
    stats = (
        canonical_catalog.get_product_statistics(clean_pid, product=resolved_product)
        if resolved_product is not None
        else None
    )
    db_ms = (time.perf_counter() - t_db_start) * 1000

    if not stats or stats["total_reviews"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    product = stats["product"]

    # Validate that the resolved product matches the requested product
    if clean_pid not in (str(product["id"]), str(product["source_product_id"])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product ID mismatch in analysis response.",
        )

    canonical_rating = stats["rating_distribution"]
    analysis = ProductAnalysisResponse(
        product_id=str(product["source_product_id"]),
        product_title=str(product["product_title"]),
        category=product["category"],
        total_reviews=int(stats["total_reviews"]),
        average_rating=float(stats["average_rating"]),
        rating_distribution={str(star): int(canonical_rating.get(f"star_{star}", 0)) for star in range(1, 6)},
        sentiment={k: int(v) for k, v in stats["sentiment_distribution"].items()},
        pros=[],
        cons=[],
        summary=f"Analysis of {stats['total_reviews']} canonical dataset reviews for {product['product_title']}.",
        insights=[],
        evidence=[],
        ai_available=False,
        product=ProductSummary(
            product_id=str(product["source_product_id"]),
            product_title=str(product["product_title"]),
            category=product["category"],
            review_count=int(stats["total_reviews"]),
            average_rating=float(stats["average_rating"]),
        ),
        statistics=ProductStatistics(
            review_count=int(stats["total_reviews"]),
            average_rating=float(stats["average_rating"]),
            rating_distribution={str(star): int(canonical_rating.get(f"star_{star}", 0)) for star in range(1, 6)},
            sentiment_distribution={k: int(v) for k, v in stats["sentiment_distribution"].items()},
        ),
        recent_reviews=[],
    )

    canonical_reviews, _ = canonical_catalog.get_reviews(
        clean_pid, page=1, page_size=5, product=product
    )
    analysis.recent_reviews = [
        ReviewItem(
            id=str(r["source_review_id"]),
            product_id=str(r["source_product_id"]),
            product_title=str(product["product_title"]),
            category=product["category"],
            review_text=str(r["review_text"]),
            rating=int(r["rating"]),
            sentiment=str(r.get("sentiment", "neutral")),
        )
        for r in canonical_reviews
    ]

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

        # Attempt AI analysis grounded strictly in retrieved canonical reviews
        sample_pool, _ = canonical_catalog.get_reviews(
            clean_pid, page=1, page_size=40, product=product
        )
        sample_reviews = format_canonical_samples(sample_pool)
        if sample_reviews:
            t_ai_start = time.perf_counter()
            try:
                ai_data = gemini_summary_service.generate_product_analysis(
                    product_id=str(product["source_product_id"]),
                    product_title=str(product["product_title"]),
                    category=product["category"],
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
                # If Gemini fails, keep factual canonical metrics and mark AI analysis unavailable
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
    Served exclusively by the canonical Supabase catalog via
    ProsConsService; there is no SQLite fallback.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
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
    Returns actual unmodified canonical review_text rows supporting a
    specific Pro or Con theme. Served exclusively via ProsConsService on the
    canonical catalog; there is no SQLite fallback.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
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
    Served exclusively via the canonical Supabase catalog; there is no
    SQLite fallback.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
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
    Served exclusively via the canonical Supabase catalog; there is no
    SQLite fallback.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
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
    Served exclusively via the canonical Supabase catalog; there is no
    SQLite fallback.
    """
    if not canonical_catalog.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canonical product catalog is currently unavailable. Please try again shortly.",
        )

    clean_pid = str(product_id).strip()
    stats = canonical_catalog.get_product_statistics(clean_pid)
    if not stats or stats["total_reviews"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    product = stats["product"]
    sample_pool, _ = canonical_catalog.get_reviews(clean_pid, page=1, page_size=5)
    sample_reviews = format_canonical_samples(sample_pool)
    if not sample_reviews:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient review data for this product.",
        )

    return gemini_summary_service.summarize_product_reviews(
        product_title=str(product["product_title"]),
        category=product["category"],
        sample_reviews=sample_reviews,
    )

