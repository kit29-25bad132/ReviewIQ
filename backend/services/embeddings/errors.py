"""Normalized embedding + vector-store errors.

Follows the V2-P1 pattern exactly (``RuntimeError`` subclass carrying an
``error_type`` enum), and reuses ``services.ai.errors.classify_provider_error``
as the single source of truth for classifying provider SDK exceptions. This is
the one error hierarchy for the retrieval domain: provider failures map the
shared AI categories; dimension/input/database failures add retrieval-specific
categories.
"""

from enum import Enum
from typing import Optional

from services.ai.errors import AIErrorType, classify_provider_error


class EmbeddingErrorType(str, Enum):
    """Coarse failure categories for embeddings + vector retrieval."""

    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    INVALID_RESPONSE = "invalid_response"
    MODEL_UNAVAILABLE = "model_unavailable"
    # Retrieval-specific categories.
    DIMENSION_MISMATCH = "dimension_mismatch"
    EMPTY_RESPONSE = "empty_response"
    INVALID_INPUT = "invalid_input"
    DATABASE_ERROR = "database_error"
    UNKNOWN = "unknown"


class EmbeddingError(RuntimeError):
    """Normalized embedding/vector-store failure.

    Subclasses ``RuntimeError`` to stay consistent with ``AIProviderError`` and
    so callers can depend on one failure shape across the AI/retrieval stack.
    """

    def __init__(
        self,
        message: str,
        error_type: EmbeddingErrorType = EmbeddingErrorType.UNKNOWN,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.model = model


# Shared provider categories (V2-P1) -> retrieval categories.
_AI_TO_EMBEDDING = {
    AIErrorType.CONFIGURATION: EmbeddingErrorType.CONFIGURATION,
    AIErrorType.AUTHENTICATION: EmbeddingErrorType.AUTHENTICATION,
    AIErrorType.RATE_LIMIT: EmbeddingErrorType.RATE_LIMIT,
    AIErrorType.TIMEOUT: EmbeddingErrorType.TIMEOUT,
    AIErrorType.TRANSIENT: EmbeddingErrorType.TRANSIENT,
    AIErrorType.INVALID_RESPONSE: EmbeddingErrorType.INVALID_RESPONSE,
    AIErrorType.MODEL_UNAVAILABLE: EmbeddingErrorType.MODEL_UNAVAILABLE,
    AIErrorType.UNKNOWN: EmbeddingErrorType.UNKNOWN,
}


def classify_embedding_error(exc: BaseException) -> EmbeddingErrorType:
    """Classify an embedding provider SDK exception using the shared classifier."""
    if isinstance(exc, EmbeddingError):
        return exc.error_type
    return _AI_TO_EMBEDDING.get(
        classify_provider_error(exc), EmbeddingErrorType.UNKNOWN
    )
