"""Cache storage abstraction (V2-P9).

``CacheStore`` covers five operations — ``get``, ``get_many``, ``put``,
``delete`` and ``corpus_token`` — over two additive tables
(``supabase_schema.sql``):

- ``ai_response_cache``  — validated LLM results (JSONB payload + provenance)
- ``embedding_cache``    — embedding vectors (JSONB vector, dimension checked)

Implementations:

- ``PostgresCacheStore`` — the existing Supabase/PostgreSQL connection
  (``services.retrieval.database.PostgresDatabase``). Lazy: no connection or
  driver import happens until an operation runs.
- ``NoopCacheStore``     — always a miss; used when caching is disabled.

FAILURE POLICY (except the corpus token, below): every failure — missing DSN,
missing driver, connection error, SQL error — is swallowed into "cache miss"
(``get``/``corpus_token`` return ``None``; ``put``/``delete`` do nothing). The
cache never turns a working ReviewIQ request into an error.

EXCEPTION: ``corpus_token()`` returning ``None`` means the live RAG corpus
token could not be obtained. Callers MUST treat that as a cache MISS and run
the normal pipeline (fail closed — never serve a possibly-stale RAG result).

Logging is limited to operation + exception class name: never payloads, keys
in full, prompts, DSNs, credentials or provider error bodies.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from services.retrieval.database import PostgresDatabase

logger = logging.getLogger(__name__)

RESPONSE_TABLE = "ai_response_cache"
EMBEDDING_TABLE = "embedding_cache"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Fixed column layouts per table (never user input; table names are validated).
_COLUMNS: Dict[str, tuple] = {
    RESPONSE_TABLE: (
        "cache_key",
        "payload",
        "provenance",
        "rag_context_digest",
        "corpus_token",
        "created_at",
        "expires_at",
    ),
    EMBEDDING_TABLE: (
        "cache_key",
        "vector",
        "task_type",
        "model",
        "dimension",
        "created_at",
        "expires_at",
    ),
}

# Opportunistic cleanup bound, applied on every write (no cron / pg_cron).
_CLEANUP_SQL = "DELETE FROM {table} WHERE expires_at < %s"

# Columns stored as JSONB: psycopg3 cannot adapt dict/list natively, so these
# parameters are wrapped in psycopg's Jsonb before execution.
_JSONB_COLUMNS: Dict[str, tuple] = {
    RESPONSE_TABLE: ("payload", "provenance"),
    EMBEDDING_TABLE: ("vector",),
}

_GET_SQL = "SELECT {columns} FROM {table} WHERE cache_key = %s"
# One indexed round-trip for a batch of keys (PK btree; no table scan).
_GET_MANY_SQL = "SELECT {columns} FROM {table} WHERE cache_key = ANY(%s)"
_PUT_SQL = """
INSERT INTO {table} ({columns})
VALUES ({placeholders})
ON CONFLICT (cache_key) DO UPDATE SET {updates}
"""
_DELETE_SQL = "DELETE FROM {table} WHERE cache_key = %s"

# Derived from the existing review_embeddings corpus: cheap (count + max) and
# deterministic for an unchanged corpus.
_CORPUS_TOKEN_SQL = (
    "SELECT count(*) AS corpus_count, max(updated_at) AS corpus_updated "
    "FROM review_embeddings"
)

_DATETIME_FIELDS = frozenset({"created_at", "expires_at"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_table(name: str) -> Optional[str]:
    if name in _COLUMNS and _IDENTIFIER_RE.match(name or ""):
        return name
    logger.warning("Rejected unknown cache table identifier.")
    return None


def _as_datetime(value: Any) -> Optional[datetime]:
    """Coerce a stored timestamp to an aware datetime (None when invalid)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _row_mapping(row: Any, columns: Sequence[str]) -> Dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return dict(zip(columns, row))


def _jsonb(value: Any) -> Any:
    """Adapt a JSON-shaped value to a JSONB parameter.

    psycopg3 adapts Python ``dict`` (and lists destined for JSONB) only through
    ``psycopg.types.json.Jsonb``. The driver import is lazy and guarded: if it
    is unavailable we fall back to a JSON string, and the surrounding
    ``put()`` converts any failure into a no-op write (fail open).
    """
    if value is None:
        return None
    try:
        from psycopg.types.json import Jsonb  # noqa: PLC0415 - lazy, optional

        return Jsonb(value)
    except Exception:  # driver missing or value not JSON-shaped
        return json.dumps(value, default=str)



class CacheStore:
    """Minimal cache storage contract (get/get_many/put/delete/corpus_token)."""

    def get(self, table: str, cache_key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def get_many(
        self, table: str, cache_keys: Sequence[str]
    ) -> List[Optional[Dict[str, Any]]]:
        """Fetch several keys; one entry per requested key, input order kept.

        Default implementation reads one key at a time. Stores with batched
        support (``PostgresCacheStore``) override this with a single query —
        callers should always prefer ``get_many`` over looping ``get``.
        """
        return [self.get(table, cache_key) for cache_key in cache_keys]

    def put(self, table: str, row: Mapping[str, Any]) -> None:
        raise NotImplementedError

    def delete(self, table: str, cache_key: str) -> None:
        raise NotImplementedError

    def corpus_token(self) -> Optional[str]:
        raise NotImplementedError


class NoopCacheStore(CacheStore):
    """Always a miss. Used when caching is disabled (and by tests)."""

    def get(self, table: str, cache_key: str) -> Optional[Dict[str, Any]]:
        return None

    def put(self, table: str, row: Mapping[str, Any]) -> None:
        return None

    def delete(self, table: str, cache_key: str) -> None:
        return None

    def corpus_token(self) -> Optional[str]:
        return None


class PostgresCacheStore(CacheStore):
    """Supabase/PostgreSQL-backed cache store (existing psycopg infrastructure)."""

    def __init__(self, database: Optional[PostgresDatabase] = None) -> None:
        self._database = database or PostgresDatabase()

    # -- reads -------------------------------------------------------------

    def get(self, table: str, cache_key: str) -> Optional[Dict[str, Any]]:
        validated = _validate_table(table)
        if validated is None or not cache_key:
            return None
        columns = _COLUMNS[validated]
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        _GET_SQL.format(
                            table=validated, columns=", ".join(columns)
                        ),
                        (cache_key,),
                    )
                    row = cursor.fetchone()
            if row is None:
                return None
            data = _row_mapping(row, columns)
            for field in _DATETIME_FIELDS & set(data):
                data[field] = _as_datetime(data[field])
            return data
        except Exception as exc:  # any failure == cache miss
            logger.warning("Cache store get failed (%s).", type(exc).__name__)
            return None

    def get_many(
        self, table: str, cache_keys: Sequence[str]
    ) -> List[Optional[Dict[str, Any]]]:
        """One ``WHERE cache_key = ANY(...)`` round-trip for the whole batch.

        Duplicate requested keys resolve to the same row; missing keys map to
        ``None``. Any failure degrades every entry to ``None`` (fail open,
        same policy as ``get``). SQL stays index-friendly: only the primary
        key on ``cache_key`` is touched, never a table scan.
        """
        validated = _validate_table(table)
        requested = list(cache_keys)
        if validated is None:
            return [None] * len(requested)
        if not requested:
            return []
        columns = _COLUMNS[validated]
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        _GET_MANY_SQL.format(
                            table=validated, columns=", ".join(columns)
                        ),
                        (list(dict.fromkeys(requested)),),
                    )
                    rows = cursor.fetchall()
        except Exception as exc:  # any failure == cache miss
            logger.warning("Cache store get_many failed (%s).", type(exc).__name__)
            return [None] * len(requested)
        by_key: Dict[str, Dict[str, Any]] = {}
        for row in rows or ():
            data = _row_mapping(row, columns)
            for field in _DATETIME_FIELDS & set(data):
                data[field] = _as_datetime(data[field])
            key = data.get("cache_key")
            if isinstance(key, str):
                by_key[key] = data
        return [by_key.get(cache_key) for cache_key in requested]

    def corpus_token(self) -> Optional[str]:
        """Live freshness token of the review_embeddings corpus.

        ``None`` means the token could not be obtained — callers must fail
        closed to a cache miss (never serve a possibly-stale RAG result).
        """
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_CORPUS_TOKEN_SQL)
                    row = cursor.fetchone()
                    if row is None:
                        return None
                    count, updated = row[0], row[1]
        except Exception as exc:
            logger.warning("Cache corpus token lookup failed (%s).", type(exc).__name__)
            return None
        updated_text = _as_datetime(updated)
        return f"v1|{count}|{updated_text.isoformat() if updated_text else ''}"

    # -- writes ------------------------------------------------------------

    def put(self, table: str, row: Mapping[str, Any]) -> None:
        validated = _validate_table(table)
        if validated is None:
            return
        columns = _COLUMNS[validated]
        missing = [name for name in columns if name not in row]
        if missing:
            logger.warning("Cache store put rejected an incomplete row.")
            return
        placeholders = ", ".join(["%s"] * len(columns))
        updates = ", ".join(
            f"{name} = EXCLUDED.{name}" for name in columns if name != "cache_key"
        )
        jsonb_columns = set(_JSONB_COLUMNS[validated])
        try:
            params = tuple(
                _jsonb(row[name]) if name in jsonb_columns else row[name]
                for name in columns
            )
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    # Opportunistic expiry cleanup on write (no cron needed).
                    cursor.execute(_CLEANUP_SQL.format(table=validated), (_utcnow(),))
                    cursor.execute(
                        _PUT_SQL.format(
                            table=validated,
                            columns=", ".join(columns),
                            placeholders=placeholders,
                            updates=updates,
                        ),
                        params,
                    )
                connection.commit()
        except Exception as exc:
            logger.warning("Cache store put failed (%s).", type(exc).__name__)

    def delete(self, table: str, cache_key: str) -> None:
        validated = _validate_table(table)
        if validated is None or not cache_key:
            return
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        _DELETE_SQL.format(table=validated), (cache_key,)
                    )
                connection.commit()
        except Exception as exc:
            logger.warning("Cache store delete failed (%s).", type(exc).__name__)


def build_cache_store() -> CacheStore:
    """Default production store (Postgres; every failure degrades to a miss)."""
    return PostgresCacheStore()


__all__ = [
    "EMBEDDING_TABLE",
    "RESPONSE_TABLE",
    "CacheStore",
    "NoopCacheStore",
    "PostgresCacheStore",
    "build_cache_store",
]
