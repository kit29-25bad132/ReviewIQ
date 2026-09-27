"""Embedding vector cache for documents and queries (V2-P9).

Caches *post-preprocessing* embedding vectors in the ``embedding_cache`` table
so duplicate provider calls disappear:

    validated text(s)
        -> preprocessing (existing, never cached itself)
        -> embedding cache (RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY namespace)
        -> provider (only cache misses)
        -> dimension-validated vectors -> cache write

Invariants:

- The cache sits AFTER preprocessing: raw, un-preprocessed text is never used
  as key material and is never stored.
- ``task_type`` is a mandatory key namespace: RETRIEVAL_DOCUMENT and
  RETRIEVAL_QUERY NEVER share a cache entry, even for identical text.
- Every cached vector is re-validated on read (numeric structure + expected
  dimension). Malformed entries are deleted and regenerated; cache/DB failures
  degrade to a miss so the existing embedding pipeline continues unchanged.
- Vector search itself is NOT cached: HNSW search is cheap and must stay
  fresh. Document fingerprinting/deduplication in the indexing pipeline is
  untouched — this layer only reduces duplicate provider calls on top of it.

Configuration: ``EMBEDDING_CACHE_ENABLED`` (default false). Hygiene TTLs are
task-specific and resolved at call time through the single
``CacheConfig.resolve_embedding_ttl`` helper: ``EMBEDDING_CACHE_TTL_SECONDS``
(default 90 days) for RETRIEVAL_DOCUMENT and every other task type,
``EMBEDDING_QUERY_CACHE_TTL_SECONDS`` (default 30 days) for RETRIEVAL_QUERY.

Reads are batched: ``get_many`` builds all keys first and issues ONE store
lookup for the whole batch (a single indexed ``WHERE cache_key = ANY(...)``
on Postgres), then reconstructs results in the original input order. Partial
hits, duplicate inputs, per-row validation and fail-open behavior are
identical to the single-key path.

Never stored: credentials, DSNs, prompts, provider error text, token counts,
cost/billing/rate data. Logging is limited to operation type, task namespace,
and a short key hash prefix — never text, vectors, or payloads.
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from services.cache.config import CacheConfig
from services.cache.keys import embedding_cache_key

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _task_name(task_type: Any) -> str:
    """Stable namespace string (``.value`` for enums, ``str`` otherwise)."""
    value = getattr(task_type, "value", task_type)
    return str(value)


def validate_cached_vector(raw: Any, dimension: int) -> Optional[List[float]]:
    """Return a clean ``list[float]`` or ``None`` when the entry is malformed.

    Rejects wrong lengths, non-numeric entries, booleans, NaN and infinities —
    a malformed cached vector must never reach storage or the API.
    """
    if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != dimension:
        return None
    vector: List[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        value = float(item)
        if not math.isfinite(value):
            return None
        vector.append(value)
    return vector


class EmbeddingCache:
    """Reads/writes embedding vectors in the ``embedding_cache`` table.

    ``store``/``config`` are injectable for tests; by default the store is
    built lazily on first *enabled* operation (a disabled cache never opens a
    database connection) and configuration is resolved from the environment on
    every call.
    """

    def __init__(self, store: Any = None, config: Optional[CacheConfig] = None) -> None:
        self._store = store
        self._config = config

    @property
    def config(self) -> CacheConfig:
        return self._config if self._config is not None else CacheConfig.from_env()

    @property
    def enabled(self) -> bool:
        return self.config.embedding_enabled

    @property
    def store(self) -> Any:
        if self._store is None:
            # Lazy + local: no retrieval/DB import (and no connection) until a
            # live operation actually runs with caching enabled.
            from services.cache.store import build_cache_store

            self._store = build_cache_store()
        return self._store

    # -- reads --------------------------------------------------------------

    def get_vector(
        self,
        *,
        text: str,
        task_type: Any,
        provider: str,
        model: str,
        dimension: int,
    ) -> Optional[List[float]]:
        if not self.enabled:
            return None
        key = embedding_cache_key(
            text=text,
            task_type=_task_name(task_type),
            provider=provider,
            model=model,
            dimension=dimension,
        )
        return self._get(key=key, dimension=dimension)

    def get_many(
        self,
        texts: Sequence[str],
        *,
        task_type: Any,
        provider: str,
        model: str,
        dimension: int,
    ) -> List[Optional[List[float]]]:
        """Partial-hit lookup: one entry per input, ``None`` for each miss.

        One batched store read for the whole batch (never one SELECT per
        text); results are validated per row and returned in input order.
        Duplicates reuse the same key/row. Any store failure degrades the
        whole batch to misses (fail open), matching the single-key path.
        """
        if not self.enabled:
            return [None] * len(texts)
        if not texts:
            return []
        keys = [
            embedding_cache_key(
                text=text,
                task_type=_task_name(task_type),
                provider=provider,
                model=model,
                dimension=dimension,
            )
            for text in texts
        ]
        try:
            from services.cache.store import EMBEDDING_TABLE

            rows = self.store.get_many(EMBEDDING_TABLE, keys)
        except Exception as exc:  # fail open: a failed batch read == misses
            logger.warning(
                "Embedding cache batch read failed (%s).", type(exc).__name__
            )
            return [None] * len(texts)
        if len(rows) != len(keys):
            # Defensive: a store violating the batch contract must not
            # misalign vectors with inputs — treat the whole batch as misses.
            logger.warning("Embedding cache batch read returned an unexpected size.")
            return [None] * len(texts)
        results: List[Optional[List[float]]] = []
        for row in rows:
            if row is None:
                results.append(None)
                continue
            try:
                results.append(self._row_to_vector(row, dimension=dimension))
            except Exception as exc:  # one bad row must not sink the batch
                logger.warning(
                    "Embedding cache read failed (%s).", type(exc).__name__
                )
                results.append(None)
        return results

    def _get(self, *, key: str, dimension: int) -> Optional[List[float]]:
        try:
            from services.cache.store import EMBEDDING_TABLE

            row = self.store.get(EMBEDDING_TABLE, key)
            if row is None:
                return None
            return self._row_to_vector(row, dimension=dimension)
        except Exception as exc:  # fail open: any failure == cache miss
            logger.warning("Embedding cache read failed (%s).", type(exc).__name__)
            return None

    def _row_to_vector(
        self, row: Dict[str, Any], *, dimension: int
    ) -> Optional[List[float]]:
        """Validate one stored row; delete it when unusable.

        Shared by the single-key and batched read paths so both apply the
        exact same rules: datetime expiry (expired rows are lazily deleted),
        stored-dimension agreement, and full numeric vector validation.
        Malformed rows are deleted and reported as a miss (regenerated).
        """
        from services.cache.store import EMBEDDING_TABLE

        key = row.get("cache_key")
        expires = row.get("expires_at")
        if not isinstance(expires, datetime):
            self._delete(EMBEDDING_TABLE, key)
            return None
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= _utcnow():
            # Expired: lazily delete and regenerate.
            self._delete(EMBEDDING_TABLE, key)
            return None
        if row.get("dimension") != dimension:
            self._delete(EMBEDDING_TABLE, key)
            return None
        vector = validate_cached_vector(row.get("vector"), dimension)
        if vector is None:
            # Malformed cached vector: delete, treat as miss, regenerate.
            self._delete(EMBEDDING_TABLE, key)
            logger.info("Embedding cache miss/malformed (key=%s).", str(key)[:12])
            return None
        return vector

    # -- writes -------------------------------------------------------------

    def put_vector(
        self,
        *,
        text: str,
        task_type: Any,
        provider: str,
        model: str,
        dimension: int,
        vector: Sequence[float],
    ) -> None:
        if not self.enabled:
            return
        try:
            from services.cache.store import EMBEDDING_TABLE

            validated = validate_cached_vector(list(vector), dimension)
            if validated is None:
                # Never cache a vector we would refuse to serve later.
                logger.warning("Embedding cache write skipped (invalid vector).")
                return
            key = embedding_cache_key(
                text=text,
                task_type=_task_name(task_type),
                provider=provider,
                model=model,
                dimension=dimension,
            )
            now = _utcnow()
            self.store.put(
                EMBEDDING_TABLE,
                {
                    "cache_key": key,
                    "vector": validated,
                    "task_type": _task_name(task_type),
                    "model": model,
                    "dimension": dimension,
                    "created_at": now,
                    "expires_at": now
                    + timedelta(
                        seconds=self.config.resolve_embedding_ttl(task_type)
                    ),
                },
            )
            logger.info(
                "Embedding cache write (%s, key=%s).",
                _task_name(task_type),
                key[:12],
            )
        except Exception as exc:  # a failed write must never block embedding
            logger.warning("Embedding cache write failed (%s).", type(exc).__name__)

    def put_many(
        self,
        texts: Sequence[str],
        *,
        task_type: Any,
        provider: str,
        model: str,
        dimension: int,
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if not self.enabled:
            return
        if len(texts) != len(vectors):
            logger.warning("Embedding cache batch write skipped (length mismatch).")
            return
        for text, vector in zip(texts, vectors):
            self.put_vector(
                text=text,
                task_type=task_type,
                provider=provider,
                model=model,
                dimension=dimension,
                vector=vector,
            )

    def _delete(self, table: str, key: str) -> None:
        try:
            self.store.delete(table, key)
        except Exception as exc:
            logger.warning("Embedding cache delete failed (%s).", type(exc).__name__)


__all__ = ["EmbeddingCache", "validate_cached_vector"]
