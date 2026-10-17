import logging
from fastapi import APIRouter, HTTPException, status
from models.review import ReviewRequest, AnalyzeReviewResponse
from services.ai.errors import AIErrorType, AIProviderError
from services.ai_analyzer import analyzer_service
from services.cache.keys import sha256_hex

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
    description="Extracts structured sentiment, star rating (1-5), pros, cons, and summary using AI.",
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
        # Privacy (ADR-012): Pydantic ValidationError (a ValueError subclass)
        # and parser errors can embed raw model output, so neither the message
        # nor the traceback is logged — a traceback frame would print it too.
        # Log a fixed category, the exception class and a non-reversible
        # digest prefix instead; the request correlation ID is added by the
        # logging filter. Response semantics are unchanged.
        lowered = str(val_err).lower()
        is_config_error = "gemini api key" in lowered or "provider api key" in lowered
        logger.warning(
            "Review analysis validation error (category=%s, error_type=%s, "
            "message_sha256_prefix=%s)",
            "configuration" if is_config_error else "validation",
            type(val_err).__name__,
            sha256_hex(str(val_err))[:12],
        )
        if is_config_error:
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
            error_msg = "AI provider authentication failed. Please check your API key configuration in backend/.env"
        elif "timeout" in exc_str or "connection" in exc_str or "unavailable" in exc_str:
            error_msg = "Connection to AI service timed out or unavailable. Please verify your network connection."
        else:
            error_msg = "AI analysis failed. Please try again."

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
