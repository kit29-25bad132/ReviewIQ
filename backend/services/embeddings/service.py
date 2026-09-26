"""Embedding service.

Coordinates the provider-neutral embedding flow:

    validated text(s)
        -> optional preprocessing (injected)
        -> embedding provider (batched)
        -> dimension-validated vectors

Returns clean Python vectors and normalizes every failure into an
``EmbeddingError``. Provider/model/dimension come from the registry so no magic
values are scattered around.
"""

import logging
from typing import Callable, List, Optional, Sequence

from services.embeddings.contracts import EmbeddingRequest, EmbeddingTaskType
from services.embeddings.errors import (
    EmbeddingError,
    EmbeddingErrorType,
    classify_embedding_error,
)
from services.embeddings.provider import EmbeddingProvider
from services.embeddings.registry import EmbeddingModelSpec, resolve_embedding_model_spec

logger = logging.getLogger(__name__)

TextPreprocessor = Callable[[str], str]


class EmbeddingService:
    """Turns text into validated embedding vectors through a provider."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        spec: Optional[EmbeddingModelSpec] = None,
        *,
        batch_size: Optional[int] = None,
        text_preprocessor: Optional[TextPreprocessor] = None,
    ) -> None:
        self._provider = provider
        self._spec = spec or resolve_embedding_model_spec()
        self._batch_size = batch_size or self._spec.max_batch_size
        # Injected so this module never imports the retrieval layer (keeps the
        # embeddings package dependency-free and prevents circular imports).
        self._text_preprocessor = text_preprocessor

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def model(self) -> str:
        return self._spec.model

    @property
    def dimension(self) -> int:
        return self._spec.dimension

    @property
    def batch_size(self) -> int:
        return self._batch_size

    def is_configured(self) -> bool:
        return self._provider.is_configured()

    def embed_text(
        self,
        text: str,
        *,
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> List[float]:
        """Embed a single text and return one dimension-validated vector."""
        vectors = self.embed_batch([text], task_type=task_type)
        return vectors[0]

    def embed_batch(
        self,
        texts: Sequence[str],
        *,
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> List[List[float]]:
        """Embed many texts, preserving order and respecting provider batch limits."""
        if not texts:
            return []

        prepared: List[str] = []
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingError(
                    "Cannot embed empty or whitespace-only text.",
                    EmbeddingErrorType.INVALID_INPUT,
                    provider=self._provider.name,
                    model=self._spec.model,
                )
            normalized = (
                self._text_preprocessor(text)
                if self._text_preprocessor is not None
                else text
            )
            if not normalized.strip():
                raise EmbeddingError(
                    "Text became empty after preprocessing.",
                    EmbeddingErrorType.INVALID_INPUT,
                    provider=self._provider.name,
                    model=self._spec.model,
                )
            prepared.append(normalized)

        vectors: List[List[float]] = []
        for start in range(0, len(prepared), self._batch_size):
            chunk = prepared[start : start + self._batch_size]
            vectors.extend(self._embed_chunk(chunk, task_type))
        return vectors

    def _embed_chunk(
        self, chunk: Sequence[str], task_type: EmbeddingTaskType
    ) -> List[List[float]]:
        try:
            response = self._provider.embed(
                EmbeddingRequest(
                    texts=tuple(chunk),
                    model=self._spec.model,
                    dimension=self._spec.dimension,
                    task_type=task_type,
                )
            )
        except EmbeddingError:
            raise
        except Exception as exc:  # safety net for an un-normalized adapter
            logger.warning(
                "Embedding provider '%s' raised an unexpected error: %s",
                self._provider.name,
                exc,
            )
            raise EmbeddingError(
                str(exc).strip() or type(exc).__name__,
                classify_embedding_error(exc),
                provider=self._provider.name,
                model=self._spec.model,
            ) from exc
        if not response.success:
            raise EmbeddingError(
                response.error_message or "Embedding provider call failed.",
                response.error_type or EmbeddingErrorType.UNKNOWN,
                provider=response.provider or self._provider.name,
                model=response.model or self._spec.model,
            )
        if len(response.vectors) != len(chunk):
            # Never silently drop or misassociate review text and vectors.
            raise EmbeddingError(
                f"Embedding provider returned {len(response.vectors)} vectors "
                f"for {len(chunk)} texts.",
                EmbeddingErrorType.INVALID_RESPONSE,
                provider=response.provider or self._provider.name,
                model=response.model or self._spec.model,
            )
        validated = []
        for vector in response.vectors:
            self._validate_dimension(vector, response.provider, response.model)
            validated.append(list(vector))
        return validated

    def _validate_dimension(
        self, vector: Sequence[float], provider: str, model: str
    ) -> None:
        """Fail clearly on empty/wrong-size vectors; never truncate or pad."""
        if not vector:
            raise EmbeddingError(
                "Embedding provider returned an empty vector.",
                EmbeddingErrorType.EMPTY_RESPONSE,
                provider=provider or self._provider.name,
                model=model or self._spec.model,
            )
        if len(vector) != self._spec.dimension:
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected {self._spec.dimension}, "
                f"received {len(vector)}. Refusing to store a corrupted vector.",
                EmbeddingErrorType.DIMENSION_MISMATCH,
                provider=provider or self._provider.name,
                model=model or self._spec.model,
            )
