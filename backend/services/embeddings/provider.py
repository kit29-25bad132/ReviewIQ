"""Embedding provider interface.

The rest of ReviewIQ depends on this abstraction instead of a specific cloud
embedding SDK. Concrete adapters live in ``services/embeddings/providers/``.
"""

from abc import ABC, abstractmethod
from typing import Sequence

from services.embeddings.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingTaskType,
)


class EmbeddingProvider(ABC):
    """A provider of text embeddings.

    Implementations classify SDK failures into an ``EmbeddingResponse`` with
    ``success=False`` and a normalized ``error_type`` rather than leaking SDK
    exception types to callers.
    """

    #: Stable provider identifier (e.g. "gemini").
    name: str = ""

    @abstractmethod
    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Embed one or more texts and return a normalized response."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when the provider has the credentials it needs."""

    def embed_text(
        self,
        text: str,
        *,
        model: str = None,
        dimension: int = None,
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> EmbeddingResponse:
        """Embed a single text."""
        return self.embed(
            EmbeddingRequest.single(
                text, model=model, dimension=dimension, task_type=task_type
            )
        )

    def embed_batch(
        self,
        texts: Sequence[str],
        *,
        model: str = None,
        dimension: int = None,
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> EmbeddingResponse:
        """Embed a batch of texts (aligned by index with ``texts``)."""
        return self.embed(
            EmbeddingRequest(
                texts=tuple(texts),
                model=model,
                dimension=dimension,
                task_type=task_type,
            )
        )
