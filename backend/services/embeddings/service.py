"""Embedding service.

Coordinates the provider-neutral embedding flow:

    validated text(s)
        -> optional preprocessing (injected)
        -> embedding cache (V2-P9, optional; NEVER caches raw input)
        -> embedding provider (batched; cache misses only)
        -> dimension-validated vectors
        -> embedding cache write (validated vectors only)

Returns clean Python vectors and normalizes every failure into an
``EmbeddingError``. Provider/model/dimension come from the registry so no magic
values are scattered around.

V2-P9: an optional content-addressed cache (disabled by default) sits between
preprocessing and the provider. Partial batch hits are supported via ONE
batched cache lookup per request: only the missed texts reach the provider
and the result is reconstructed in the original order. The task type is part
of the key, so RETRIEVAL_DOCUMENT and RETRIEVAL_QUERY never share an entry.
Cache/DB failures degrade to a miss and the existing pipeline continues
unchanged; existing validation (empty input, dimension, vector count) is
untouched and re-applied to cached vectors.
"""

import logging
from typing import Callable, List, Optional, Sequence

from services.cache.embedding_cache import EmbeddingCache
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
        cache: Optional[EmbeddingCache] = None,
    ) -> None:
        self._provider = provider
        self._spec = spec or resolve_embedding_model_spec()
        self._batch_size = batch_size or self._spec.max_batch_size
        # Injected so this module never imports the retrieval layer (keeps the
        # embeddings package dependency-free and prevents circular imports).
        self._text_preprocessor = text_preprocessor
        # V2-P9 embedding cache: built by default but resolved lazily — a
        # disabled cache (the default) never opens a database connection.
        self._cache = cache if cache is not None else EmbeddingCache()

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def cache(self) -> EmbeddingCache:
        """V2-P9 post-preprocessing embedding cache."""
        return self._cache

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
        """Embed many texts, preserving order and respecting provider batch limits.

        V2-P9: the cache is consulted AFTER preprocessing (never on raw input).
        Partial hits are supported — only the missed texts are sent to the
        provider (existing batch/chunk behavior preserved) and the final result
        is reconstructed in the original input order.
        """
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

        results: List[Optional[List[float]]] = [None] * len(prepared)
        cache_enabled = self._cache.enabled
        if cache_enabled:
            # Partial-hit lookup: ONE batched cache read for the whole request
            # (never one lookup per text); each position gets a validated
            # cached vector or None (miss / expired / malformed / unavailable).
            hits = self._cache.get_many(
                prepared,
                task_type=task_type,
                provider=self._provider.name,
                model=self._spec.model,
                dimension=self._spec.dimension,
            )
            for index, hit in enumerate(hits):
                if hit is not None:
                    results[index] = hit

        missing = [index for index, vector in enumerate(results) if vector is None]
        if missing:
            miss_texts = [prepared[index] for index in missing]
            vectors: List[List[float]] = []
            for start in range(0, len(miss_texts), self._batch_size):
                chunk = miss_texts[start : start + self._batch_size]
                vectors.extend(self._embed_chunk(chunk, task_type))
            if len(vectors) != len(missing):
                # Defensive: _embed_chunk already enforces the count contract.
                raise EmbeddingError(
                    f"Embedding provider returned {len(vectors)} vectors for "
                    f"{len(miss_texts)} texts.",
                    EmbeddingErrorType.INVALID_RESPONSE,
                    provider=self._provider.name,
                    model=self._spec.model,
                )
            if cache_enabled:
                # Validated vectors only (re-checked by the cache before write).
                self._cache.put_many(
                    miss_texts,
                    task_type=task_type,
                    provider=self._provider.name,
                    model=self._spec.model,
                    dimension=self._spec.dimension,
                    vectors=vectors,
                )
            for index, vector in zip(missing, vectors):
                results[index] = vector

        final: List[List[float]] = []
        for vector in results:
            if vector is None:
                # Unreachable by construction (every miss is filled above);
                # fail loudly rather than silently misaligning the result.
                raise EmbeddingError(
                    "Embedding result could not be assembled for every input.",
                    EmbeddingErrorType.INVALID_RESPONSE,
                    provider=self._provider.name,
                    model=self._spec.model,
                )
            final.append(vector)
        return final

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
