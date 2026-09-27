"""V2-P9 cache configuration.

Follows the same safe environment-parsing pattern as
``services.rag.config.RAGConfig`` and ``services.ai.retry_policy``:

- values resolve at call time (environments and tests can change settings
  without rebuilding services),
- invalid/missing values fall back to safe defaults with a server-side warning,
- configuration errors never raise and never block startup,
- only non-secret configuration metadata is ever logged.

Both caches are DISABLED by default (safe first rollout). Enabling requires
explicit environment opt-in:

    LLM_CACHE_ENABLED=true
    EMBEDDING_CACHE_ENABLED=true

TTL defaults (seconds):

- AI_CACHE_TTL_SECONDS                = 604800  (7 days, LLM non-RAG)
- AI_CACHE_TTL_RAG_SECONDS            = 3600    (1 hour, LLM with RAG)
- EMBEDDING_CACHE_TTL_SECONDS         = 7776000 (90 days, document vectors)
- EMBEDDING_QUERY_CACHE_TTL_SECONDS   = 2592000 (30 days, query vectors)

The embedding TTL is task-specific: RETRIEVAL_QUERY entries are short-lived
lookups and expire after 30 days, every other task type (including
RETRIEVAL_DOCUMENT) uses the 90-day hygiene TTL. Selection lives in the single
``CacheConfig.resolve_embedding_ttl`` helper — never duplicated elsewhere.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LLM_CACHE_ENABLED = False
DEFAULT_EMBEDDING_CACHE_ENABLED = False
DEFAULT_AI_CACHE_TTL_SECONDS = 604800  # 7 days
DEFAULT_AI_CACHE_TTL_RAG_SECONDS = 3600  # 1 hour
DEFAULT_EMBEDDING_CACHE_TTL_SECONDS = 7776000  # 90 days (documents)
DEFAULT_EMBEDDING_QUERY_CACHE_TTL_SECONDS = 2592000  # 30 days (queries)

# Floor for TTLs: a non-positive TTL would make every entry dead on arrival.
_MIN_TTL_SECONDS = 1

LLM_CACHE_ENABLED_ENV_VAR = "LLM_CACHE_ENABLED"
EMBEDDING_CACHE_ENABLED_ENV_VAR = "EMBEDDING_CACHE_ENABLED"
AI_CACHE_TTL_SECONDS_ENV_VAR = "AI_CACHE_TTL_SECONDS"
AI_CACHE_TTL_RAG_SECONDS_ENV_VAR = "AI_CACHE_TTL_RAG_SECONDS"
EMBEDDING_CACHE_TTL_SECONDS_ENV_VAR = "EMBEDDING_CACHE_TTL_SECONDS"
EMBEDDING_QUERY_CACHE_TTL_SECONDS_ENV_VAR = "EMBEDDING_QUERY_CACHE_TTL_SECONDS"

#: Task namespace whose entries use the shorter query TTL (enum ``.value`` or
#: plain string both normalize to this exact name).
_QUERY_TASK_NAME = "RETRIEVAL_QUERY"

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
    logger.warning("Invalid %s value; using default %s.", name, default)
    return default


def _env_ttl(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s value; using default %d.", name, default)
        return default
    if value < _MIN_TTL_SECONDS:
        logger.warning("Out-of-range %s; using default %d.", name, default)
        return default
    return value


@dataclass(frozen=True)
class CacheConfig:
    """Validated cache settings for one request/operation."""

    llm_enabled: bool = DEFAULT_LLM_CACHE_ENABLED
    embedding_enabled: bool = DEFAULT_EMBEDDING_CACHE_ENABLED
    llm_ttl_seconds: int = DEFAULT_AI_CACHE_TTL_SECONDS
    llm_rag_ttl_seconds: int = DEFAULT_AI_CACHE_TTL_RAG_SECONDS
    embedding_ttl_seconds: int = DEFAULT_EMBEDDING_CACHE_TTL_SECONDS
    embedding_query_ttl_seconds: int = DEFAULT_EMBEDDING_QUERY_CACHE_TTL_SECONDS

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Resolve settings from the environment (invalid values fall back)."""
        return cls(
            llm_enabled=_env_flag(
                LLM_CACHE_ENABLED_ENV_VAR, DEFAULT_LLM_CACHE_ENABLED
            ),
            embedding_enabled=_env_flag(
                EMBEDDING_CACHE_ENABLED_ENV_VAR, DEFAULT_EMBEDDING_CACHE_ENABLED
            ),
            llm_ttl_seconds=_env_ttl(
                AI_CACHE_TTL_SECONDS_ENV_VAR, DEFAULT_AI_CACHE_TTL_SECONDS
            ),
            llm_rag_ttl_seconds=_env_ttl(
                AI_CACHE_TTL_RAG_SECONDS_ENV_VAR, DEFAULT_AI_CACHE_TTL_RAG_SECONDS
            ),
            embedding_ttl_seconds=_env_ttl(
                EMBEDDING_CACHE_TTL_SECONDS_ENV_VAR,
                DEFAULT_EMBEDDING_CACHE_TTL_SECONDS,
            ),
            embedding_query_ttl_seconds=_env_ttl(
                EMBEDDING_QUERY_CACHE_TTL_SECONDS_ENV_VAR,
                DEFAULT_EMBEDDING_QUERY_CACHE_TTL_SECONDS,
            ),
        )

    def llm_ttl_for(self, rag_enabled: bool) -> int:
        """TTL for an LLM entry: shorter when RAG context is involved."""
        return self.llm_rag_ttl_seconds if rag_enabled else self.llm_ttl_seconds

    def resolve_embedding_ttl(self, task_type: Any) -> int:
        """Single source of embedding TTL policy (seconds).

        ``RETRIEVAL_QUERY`` -> ``embedding_query_ttl_seconds`` (30 days);
        every other task type (including ``RETRIEVAL_DOCUMENT``) ->
        ``embedding_ttl_seconds`` (90 days). Duck-typed over enum ``.value`` so
        callers may pass the enum or its plain string; deterministic and
        side-effect free (no environment access beyond ``from_env``).
        """
        name = str(getattr(task_type, "value", task_type))
        if name == _QUERY_TASK_NAME:
            return self.embedding_query_ttl_seconds
        return self.embedding_ttl_seconds
