"""Provider-neutral embedding contracts.

Application code (the retrieval/indexing services) depends only on these types.
No Gemini SDK type appears here, so a future cloud embedding provider can be
added without touching the review processing or search logic.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.embeddings.errors import EmbeddingErrorType


class EmbeddingTaskType(str, Enum):
    """Retrieval task hint passed to providers that support it.

    Gemini uses this to produce better-matched document vs. query vectors.
    """

    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    CLASSIFICATION = "CLASSIFICATION"
    CLUSTERING = "CLUSTERING"


@dataclass(frozen=True)
class EmbeddingModelRef:
    """An explicit embedding provider/model/dimension selection."""

    provider: str
    model: str
    dimension: int


@dataclass(frozen=True)
class EmbeddingRequest:
    """A single provider-neutral embedding request (one or many texts)."""

    texts: Tuple[str, ...]
    model: Optional[str] = None
    dimension: Optional[int] = None
    task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def single(
        cls,
        text: str,
        *,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> "EmbeddingRequest":
        return cls(texts=(text,), model=model, dimension=dimension, task_type=task_type)


@dataclass
class EmbeddingUsage:
    """Token usage reported by an embedding provider, when available."""

    input_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


@dataclass
class EmbeddingResponse:
    """Provider-neutral embedding result.

    ``vectors`` is aligned by index with ``EmbeddingRequest.texts``.
    Dimension validation is intentionally left to ``EmbeddingService`` so the
    provider stays a thin transport adapter.
    """

    vectors: List[List[float]] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    dimension: int = 0
    success: bool = True
    error_type: Optional[EmbeddingErrorType] = None
    error_message: Optional[str] = None
    usage: Optional[EmbeddingUsage] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def failure(
        cls,
        *,
        provider: str,
        model: str,
        error_type: EmbeddingErrorType,
        error_message: str,
        latency_ms: Optional[float] = None,
    ) -> "EmbeddingResponse":
        return cls(
            vectors=[],
            provider=provider,
            model=model,
            dimension=0,
            success=False,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
        )
