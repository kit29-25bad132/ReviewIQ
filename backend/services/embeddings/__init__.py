"""Provider-neutral embedding foundation (contracts, provider, registry, service)."""

from services.embeddings.contracts import (
    EmbeddingModelRef,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingTaskType,
    EmbeddingUsage,
)
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.embeddings.provider import EmbeddingProvider
from services.embeddings.registry import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingModelSpec,
    resolve_embedding_model_spec,
)
from services.embeddings.service import EmbeddingService

__all__ = [
    "DEFAULT_EMBEDDING_DIMENSION",
    "DEFAULT_EMBEDDING_MODEL",
    "EmbeddingError",
    "EmbeddingErrorType",
    "EmbeddingModelRef",
    "EmbeddingModelSpec",
    "EmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "EmbeddingService",
    "EmbeddingTaskType",
    "EmbeddingUsage",
    "resolve_embedding_model_spec",
]
