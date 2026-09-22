import logging
from fastapi import APIRouter, HTTPException, status
from models.review import ReviewRequest, AnalyzeReviewResponse
from services.ai_analyzer import analyzer_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Review Analysis"])


@router.post(
    "/analyze-review",
    response_model=AnalyzeReviewResponse,
    summary="Analyze a customer review",
    description="Extracts structured sentiment, star rating (1-5), pros, cons, and summary using Gemini AI.",
)
async def analyze_review_endpoint(payload: ReviewRequest):
    """
    Accepts review text, delegates to AI analyzer, validates structured JSON,
    and returns sanitized analysis.
    """
    try:
        analysis = analyzer_service.analyze_review(payload.review)
        return AnalyzeReviewResponse(
            success=True,
            data=analysis,
            error=None
        )
    except ValueError as val_err:
        logger.warning(f"Validation or configuration error: {val_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Unexpected error during review analysis: {exc}", exc_info=True)
        exc_str = str(exc).lower()

        if "quota" in exc_str or "rate limit" in exc_str or "resourceexhausted" in exc_str or "429" in exc_str:
            error_msg = "API rate limit reached. Please try again in a few moments."
        elif "api_key" in exc_str or "auth" in exc_str or "permission" in exc_str or "unauthenticated" in exc_str or "invalid argument" in exc_str or "403" in exc_str or "401" in exc_str:
            error_msg = "Invalid or unauthenticated Gemini API key. Please check backend/.env"
        elif "timeout" in exc_str or "connection" in exc_str or "unavailable" in exc_str:
            error_msg = "Connection to AI service timed out or unavailable. Please verify your network connection."
        else:
            error_msg = f"AI analysis error: {str(exc)}"

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
