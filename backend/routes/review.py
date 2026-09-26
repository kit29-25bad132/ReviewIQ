import logging
from fastapi import APIRouter, HTTPException, status
from models.review import ReviewRequest, AnalyzeReviewResponse
from services.ai.errors import AIErrorType, AIProviderError
from services.ai_analyzer import analyzer_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Review Analysis"])

# Normalized provider error categories -> fixed, user-safe messages. Raw
# provider/SDK text is never echoed to API consumers.
_PROVIDER_ERROR_MESSAGES = {
    AIErrorType.RATE_LIMIT: "API rate limit reached. Please try again in a few moments.",
    AIErrorType.AUTHENTICATION: "Invalid or unauthenticated AI provider API key. Please check backend/.env",
    AIErrorType.CONFIGURATION: "AI analysis is unavailable. Please check the server configuration.",
    AIErrorType.TIMEOUT: "Connection to AI service timed out or unavailable. Please verify your network connection.",
    AIErrorType.TRANSIENT: "Connection to AI service timed out or unavailable. Please verify your network connection.",
    AIErrorType.MODEL_UNAVAILABLE: "No AI model is currently available to analyze this review. Please try again later.",
}
_DEFAULT_PROVIDER_ERROR_MESSAGE = "AI analysis failed. Please try again."
# Fixed configuration message for the "no provider key at all" ValueError.
_NO_KEY_DETAIL = (
    "No AI provider API key is configured. "
    "Please set GEMINI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY in backend/.env"
)


def _provider_error_message(error_type) -> str:
    return _PROVIDER_ERROR_MESSAGES.get(error_type, _DEFAULT_PROVIDER_ERROR_MESSAGE)


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
    except AIProviderError as provider_err:
        # Already classified by the AI Gateway: map the category to a fixed
        # message so no raw provider text reaches the client.
        logger.warning(
            f"AI provider error ({provider_err.error_type}): {provider_err}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_provider_error_message(provider_err.error_type),
        )
    except ValueError as val_err:
        # Log the full detail server-side; never echo parser/model-output text
        # (Pydantic ValidationError is a ValueError subclass and may embed raw output).
        logger.warning(f"Validation or configuration error: {val_err}", exc_info=True)
        lowered = str(val_err).lower()
        if "gemini api key" in lowered or "provider api key" in lowered:
            detail = _NO_KEY_DETAIL
        else:
            detail = "Review analysis failed validation. Please try again."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
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
            error_msg = "AI analysis failed. Please try again."

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
