"""V2-P9 application caching (disabled by default).

Two independent, fail-open caches built on the existing Supabase/PostgreSQL
infrastructure (no new dependency, no external service):

- ``services.cache.llm_cache``      — validated LLM analysis/summary results
- ``services.cache.embedding_cache`` — document and query embedding vectors

Supporting modules:

- ``services.cache.config``  — environment configuration (RAGConfig-style,
  resolved at call time, safe fallbacks, never raises)
- ``services.cache.keys``    — deterministic versioned SHA-256 cache keys
- ``services.cache.store``   — CacheStore abstraction (Postgres + Noop)

Design rules (ADR-011):

- The cache sits ABOVE routing, fallback, retry, grounding and the AI gateway;
  a hit bypasses all of them, a miss runs the existing pipeline unchanged.
- Cache keys are provider/model independent: the validated, grounded result is
  provider-neutral. Provider/model provenance is stored internally only and is
  never returned through the API.
- Failure policy: any cache/DB failure is a cache miss. The cache never turns a
  working request into an error. The single exception is RAG corpus-token
  verification, which fails CLOSED to a miss (never serve a possibly-stale RAG
  result).
- Never store: credentials, DSNs, prompts, retrieved context, provider error
  text, token counts, cost or billing data.

This package is deliberately independent from LangGraph, the AI Gateway,
provider adapters, routing, retry, grounding and the frontend.
"""

from services.cache.config import CacheConfig
from services.cache.embedding_cache import EmbeddingCache
from services.cache.keys import (
    CACHE_SCHEMA_VERSION,
    PREPROCESS_VERSION,
    PROMPT_VERSION,
    analysis_cache_key,
    canonical_key,
    embedding_cache_key,
    rag_config_digest,
    response_schema_identity,
    sha256_hex,
    summary_cache_key,
)
from services.cache.llm_cache import LLMCache

__all__ = [
    "CACHE_SCHEMA_VERSION",
    "PREPROCESS_VERSION",
    "PROMPT_VERSION",
    "CacheConfig",
    "EmbeddingCache",
    "LLMCache",
    "analysis_cache_key",
    "canonical_key",
    "embedding_cache_key",
    "rag_config_digest",
    "response_schema_identity",
    "sha256_hex",
    "summary_cache_key",
]
