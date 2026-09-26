"""Provider-neutral AI foundation: contracts, provider interface, model
registry, and the AI Gateway."""

from services.ai.contracts import (
    AIGenerationRequest,
    AIResponse,
    AIUsage,
    ModelRef,
)
from services.ai.errors import (
    AIConfigurationError,
    AIErrorType,
    AIProviderError,
    ModelNotAvailableError,
    UnknownProviderError,
)
from services.ai.gateway import AIGateway
from services.ai.provider import AIProvider
from services.ai.registry import ModelRegistry, ModelSpec, model_registry
from services.ai.retry_policy import (
    RetryPolicy,
    generate_with_retry,
    is_retryable,
    resolve_request_timeout,
    resolve_retry_policy,
)

__all__ = [
    "AIConfigurationError",
    "AIErrorType",
    "AIGateway",
    "AIGenerationRequest",
    "AIProvider",
    "AIProviderError",
    "AIResponse",
    "AIUsage",
    "ModelNotAvailableError",
    "ModelRef",
    "ModelRegistry",
    "ModelSpec",
    "RetryPolicy",
    "UnknownProviderError",
    "generate_with_retry",
    "is_retryable",
    "model_registry",
    "resolve_request_timeout",
    "resolve_retry_policy",
]
