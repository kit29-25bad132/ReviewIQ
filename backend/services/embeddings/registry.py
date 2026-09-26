"""Embedding model registry / configuration.

Keeps the embedding model, provider, and dimension in one place instead of
scattering magic numbers. The dimension recorded here must match the pgvector
column dimension created by ``supabase_schema.sql``.
"""

import os
from dataclasses import dataclass

GEMINI_EMBEDDING_PROVIDER = "gemini"

# Verified against the configured API key (models.list + embedContent smoke
# tests, 2026-09-25): gemini-embedding-001 is the stable embedding model
# available to this project. The older text-embedding-004 is retired.
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"

# gemini-embedding-001 supports MRL output dims: 768 (default choice), 1536, 3072.
DEFAULT_EMBEDDING_DIMENSION = 768
SUPPORTED_GEMINI_DIMENSIONS = frozenset({768, 1536, 3072})

# Bound for one provider call. Kept here (not hardcoded in the service) so the
# batch layer can respect provider limits.
DEFAULT_EMBEDDING_BATCH_SIZE = 100


@dataclass(frozen=True)
class EmbeddingModelSpec:
    """Provider-neutral description of the configured embedding model."""

    provider: str
    model: str
    dimension: int
    max_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE


def _positive_int(value: str, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def resolve_embedding_model_spec() -> EmbeddingModelSpec:
    """Resolve the configured embedding model/dimension from the environment.

    ``EMBEDDING_MODEL`` and ``EMBEDDING_DIMENSION`` are optional; the pinned
    defaults keep behavior deterministic. The dimension is validated by the
    ``EmbeddingService`` against the vectors actually returned by the provider.
    """
    model = (os.getenv("EMBEDDING_MODEL") or "").strip() or DEFAULT_EMBEDDING_MODEL
    dimension = _positive_int(
        os.getenv("EMBEDDING_DIMENSION") or "", DEFAULT_EMBEDDING_DIMENSION
    )
    batch_size = _positive_int(
        os.getenv("EMBEDDING_BATCH_SIZE") or "", DEFAULT_EMBEDDING_BATCH_SIZE
    )
    return EmbeddingModelSpec(
        provider=GEMINI_EMBEDDING_PROVIDER,
        model=model,
        dimension=dimension,
        max_batch_size=batch_size,
    )
