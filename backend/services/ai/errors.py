"""Provider-neutral AI error classification.

V1 called Gemini directly, so provider SDK exception text had to be inspected
in the route layer to decide the user-facing message. V2 introduces an AI
Gateway: every provider failure is classified into the coarse categories below
at the provider/gateway boundary. Application code never inspects an SDK
exception, and API consumers never receive raw provider text (routes map
categories to fixed, safe messages).
"""

from enum import Enum
from typing import Optional


class AIErrorType(str, Enum):
    """Coarse failure categories shared by every AI provider."""

    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    INVALID_RESPONSE = "invalid_response"
    # The provider rejected the *request* (e.g. "invalid argument", HTTP 400).
    # Deliberately distinct from AUTHENTICATION: V2-P5 skips a provider's
    # remaining models only on AUTHENTICATION/CONFIGURATION, and a malformed
    # request is not evidence that the provider's credentials are wrong.
    INVALID_REQUEST = "invalid_request"
    MODEL_UNAVAILABLE = "model_unavailable"
    UNKNOWN = "unknown"


class AIProviderError(RuntimeError):
    """Normalized AI failure surfaced at the gateway/provider boundary.

    Subclasses ``RuntimeError`` on purpose: V1 callers (and the existing test
    suite) expect provider failures to surface as ``RuntimeError``. The added
    ``error_type`` lets the API layer map categories without string matching.
    """

    def __init__(
        self,
        message: str,
        error_type: AIErrorType = AIErrorType.UNKNOWN,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.model = model


class AIConfigurationError(AIProviderError):
    """Invalid or unavailable provider/model selection (not retryable)."""

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(
            message, AIErrorType.CONFIGURATION, provider=provider, model=model
        )


class UnknownProviderError(AIConfigurationError):
    """No adapter is registered for the requested provider."""


class ModelNotAvailableError(AIConfigurationError):
    """The requested model is unknown or disabled in the model registry."""


_RATE_LIMIT_HINTS = (
    "quota",
    "rate limit",
    "rate_limit",
    "ratelimit",
    "resourceexhausted",
    "too many requests",
    "429",
)
_AUTH_HINTS = (
    "api_key",
    "api key",
    "apikey",
    "unauthenticated",
    "unauthorized",
    "permission",
    "forbidden",
    "401",
    "403",
)
_TIMEOUT_HINTS = ("timeout", "timed out", "deadline", "deadlineexceeded")
_MODEL_HINTS = (
    "not found",
    "notfound",
    "does not exist",
    "unsupported",
    "model_not_found",
    "404",
)
_TRANSIENT_HINTS = (
    "unavailable",
    "overloaded",
    "connection",
    "server error",
    "internal",
    "503",
    "502",
    "500",
    "transient",
)
# A malformed *request* (not credentials). Checked last so more specific
# categories (rate limit / auth / timeout / model / transient) win when a
# message contains several hints, e.g. "invalid argument: model not found".
_INVALID_REQUEST_HINTS = (
    "invalid argument",
    "invalid_argument",
    "bad request",
    "400 bad request",
)


def classify_error_text(text: str) -> AIErrorType:
    """Classify a free-form provider error string (best-effort, deterministic)."""
    lowered = (text or "").lower()
    for hints, error_type in (
        (_RATE_LIMIT_HINTS, AIErrorType.RATE_LIMIT),
        (_AUTH_HINTS, AIErrorType.AUTHENTICATION),
        (_TIMEOUT_HINTS, AIErrorType.TIMEOUT),
        (_MODEL_HINTS, AIErrorType.MODEL_UNAVAILABLE),
        (_TRANSIENT_HINTS, AIErrorType.TRANSIENT),
        (_INVALID_REQUEST_HINTS, AIErrorType.INVALID_REQUEST),
    ):
        if any(hint in lowered for hint in hints):
            return error_type
    return AIErrorType.UNKNOWN


def classify_provider_error(exc: BaseException) -> AIErrorType:
    """Map a provider SDK exception to an internal category.

    Text hints win over exception type so provider-specific messages
    (``429``, ``UNAUTHENTICATED``, ``unavailable``) keep their meaning.
    """
    if isinstance(exc, AIProviderError):
        return exc.error_type
    if isinstance(exc, TimeoutError):
        return AIErrorType.TIMEOUT
    category = classify_error_text(str(exc))
    if category is not AIErrorType.UNKNOWN:
        return category
    if isinstance(exc, (ValueError, TypeError)):
        # Malformed / un-decodable provider output.
        return AIErrorType.INVALID_RESPONSE
    return AIErrorType.UNKNOWN
