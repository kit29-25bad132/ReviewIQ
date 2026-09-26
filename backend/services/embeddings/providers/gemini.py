"""Gemini embedding adapter for the provider-neutral embedding interface.

Reuses the existing ``google-genai`` SDK and API key (no new dependency). Only
the embedding transport lives here; dimension validation and batching live in
``EmbeddingService``.
"""

import logging
import os
import time
from typing import Callable, Optional

from services.embeddings.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
)
from services.embeddings.errors import EmbeddingErrorType, classify_embedding_error
from services.embeddings.provider import EmbeddingProvider
from services.embeddings.registry import (
    GEMINI_EMBEDDING_PROVIDER,
    EmbeddingModelSpec,
    resolve_embedding_model_spec,
)

logger = logging.getLogger(__name__)

PLACEHOLDER_API_KEYS = frozenset(
    {"your_gemini_api_key_here", "YOUR_GEMINI_API_KEY_HERE"}
)


def _env_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    return key.strip() if key else ""


def _extract_usage(response: object) -> Optional[EmbeddingUsage]:
    embeddings = getattr(response, "embeddings", None) or []
    total = 0
    found = False
    for embedding in embeddings:
        stats = getattr(embedding, "statistics", None)
        count = getattr(stats, "token_count", None) if stats is not None else None
        if isinstance(count, int) and not isinstance(count, bool):
            total += count
            found = True
    return EmbeddingUsage(input_tokens=total, total_tokens=total) if found else None


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding adapter for Google Gemini via the ``google-genai`` SDK."""

    name = GEMINI_EMBEDDING_PROVIDER

    def __init__(
        self,
        api_key_provider: Optional[Callable[[], str]] = None,
        spec: Optional[EmbeddingModelSpec] = None,
    ) -> None:
        self._api_key_provider = api_key_provider or _env_api_key
        self._spec = spec or resolve_embedding_model_spec()

    @property
    def api_key(self) -> str:
        return (self._api_key_provider() or "").strip()

    def is_configured(self) -> bool:
        key = self.api_key
        return bool(key and key not in PLACEHOLDER_API_KEYS)

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        # Imported lazily so the SDK stays optional: a missing install surfaces
        # as a clear configuration error at call time, not an import crash.
        from google import genai
        from google.genai import types

        model = request.model or self._spec.model
        dimension = request.dimension or self._spec.dimension
        started = time.perf_counter()
        client = genai.Client(api_key=self.api_key)
        config = types.EmbedContentConfig(
            task_type=request.task_type.value,
            output_dimensionality=dimension,
        )

        try:
            response = client.models.embed_content(
                model=model,
                contents=list(request.texts),
                config=config,
            )
        except Exception as exc:  # normalized; raw SDK error never leaves here
            latency_ms = (time.perf_counter() - started) * 1000
            error_type = classify_embedding_error(exc)
            logger.warning(
                "Gemini embedding model %s failed (%s): %s",
                model,
                error_type.value,
                exc,
            )
            return EmbeddingResponse.failure(
                provider=self.name,
                model=model,
                error_type=error_type,
                error_message=str(exc).strip() or type(exc).__name__,
                latency_ms=latency_ms,
            )

        latency_ms = (time.perf_counter() - started) * 1000
        embeddings = getattr(response, "embeddings", None) or []
        vectors = []
        for embedding in embeddings:
            values = getattr(embedding, "values", None)
            if not values:
                return EmbeddingResponse.failure(
                    provider=self.name,
                    model=model,
                    error_type=EmbeddingErrorType.EMPTY_RESPONSE,
                    error_message="Embedding provider returned an empty vector.",
                    latency_ms=latency_ms,
                )
            vectors.append(list(values))

        if not vectors:
            return EmbeddingResponse.failure(
                provider=self.name,
                model=model,
                error_type=EmbeddingErrorType.EMPTY_RESPONSE,
                error_message="Embedding provider returned no vectors.",
                latency_ms=latency_ms,
            )

        return EmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            dimension=dimension,
            success=True,
            usage=_extract_usage(response),
            latency_ms=latency_ms,
            metadata={
                "task_type": request.task_type.value,
                "requested_dimension": dimension,
            },
        )
