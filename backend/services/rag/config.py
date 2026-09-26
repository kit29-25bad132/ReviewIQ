"""RAG configuration (V2-P3).

Environment-driven with safe, validated defaults, following the same pattern
as ``services/embeddings/registry.py``: values are resolved at call time so
environments and tests can change settings without rebuilding services.

The RAG stage is disabled by default so V1/P1/P2 behavior stays identical
until ``RAG_ENABLED`` is explicitly turned on.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_RAG_ENABLED = False
DEFAULT_RAG_TOP_K = 5
DEFAULT_RAG_SIMILARITY_THRESHOLD = 0.35
DEFAULT_RAG_MAX_CONTEXT_REVIEWS = 5
DEFAULT_RAG_MAX_CONTEXT_CHARS = 6000
DEFAULT_RAG_MAX_REVIEW_CHARS = 1000

RAG_TOP_K_BOUNDS = (1, 20)
RAG_SIMILARITY_THRESHOLD_BOUNDS = (-1.0, 1.0)
RAG_MAX_CONTEXT_REVIEWS_BOUNDS = (1, 20)
RAG_MAX_CONTEXT_CHARS_BOUNDS = (500, 50_000)
RAG_MAX_REVIEW_CHARS_BOUNDS = (100, 10_000)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    logger.warning("Invalid %s value %r; using default %s.", name, raw, default)
    return default


def _env_number(name: str, default, bounds, cast):
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = cast(raw.strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s value %r; using default %s.", name, raw, default)
        return default
    low, high = bounds
    if not low <= value <= high:
        logger.warning(
            "%s value %r is outside [%s, %s]; using default %s.",
            name, raw, low, high, default,
        )
        return default
    return value


@dataclass(frozen=True)
class RAGConfig:
    """Validated settings for one RAG stage (retrieval + context building)."""

    enabled: bool = DEFAULT_RAG_ENABLED
    top_k: int = DEFAULT_RAG_TOP_K
    similarity_threshold: float = DEFAULT_RAG_SIMILARITY_THRESHOLD
    max_context_reviews: int = DEFAULT_RAG_MAX_CONTEXT_REVIEWS
    max_context_chars: int = DEFAULT_RAG_MAX_CONTEXT_CHARS
    max_review_chars: int = DEFAULT_RAG_MAX_REVIEW_CHARS

    @classmethod
    def from_env(cls) -> "RAGConfig":
        """Resolve settings from the environment (invalid values fall back)."""
        return cls(
            enabled=_env_flag("RAG_ENABLED", DEFAULT_RAG_ENABLED),
            top_k=_env_number(
                "RAG_TOP_K", DEFAULT_RAG_TOP_K, RAG_TOP_K_BOUNDS, int
            ),
            similarity_threshold=_env_number(
                "RAG_SIMILARITY_THRESHOLD",
                DEFAULT_RAG_SIMILARITY_THRESHOLD,
                RAG_SIMILARITY_THRESHOLD_BOUNDS,
                float,
            ),
            max_context_reviews=_env_number(
                "RAG_MAX_CONTEXT_REVIEWS",
                DEFAULT_RAG_MAX_CONTEXT_REVIEWS,
                RAG_MAX_CONTEXT_REVIEWS_BOUNDS,
                int,
            ),
            max_context_chars=_env_number(
                "RAG_MAX_CONTEXT_CHARS",
                DEFAULT_RAG_MAX_CONTEXT_CHARS,
                RAG_MAX_CONTEXT_CHARS_BOUNDS,
                int,
            ),
            max_review_chars=_env_number(
                "RAG_MAX_REVIEW_CHARS",
                DEFAULT_RAG_MAX_REVIEW_CHARS,
                RAG_MAX_REVIEW_CHARS_BOUNDS,
                int,
            ),
        )
