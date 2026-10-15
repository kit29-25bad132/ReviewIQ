"""PostgreSQL connection provider for the retrieval layer.

Connects to the project's Supabase PostgreSQL database (with pgvector) through
the server-side connection string from the environment. The connection string
must never reach the frontend.

``psycopg`` is imported lazily inside ``connection()`` so importing this module
— and therefore the backend test suite — never requires the driver to be
installed. Missing configuration or a missing driver surfaces as a normalized
``EmbeddingError`` rather than an import-time crash.
"""

import os
import queue
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from pathlib import Path
from dotenv import load_dotenv

_base = Path(__file__).resolve().parent.parent.parent
load_dotenv(_base / ".env")
load_dotenv(_base.parent / ".env")

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType

#: Environment variables checked, in order, for the Postgres connection string.
DSN_ENV_VARS = ("DATABASE_URL", "SUPABASE_DB_URL")


def resolve_database_dsn() -> str:
    """Return the configured Postgres DSN, or an empty string when unset."""
    for name in DSN_ENV_VARS:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


class _SimpleConnectionPool:
    """Minimal LIFO pool reusing handshakes across short-lived queries.

    Deliberately built on the existing ``psycopg.connect`` choke point
    (rather than ``psycopg_pool``, which is not an installed dependency):
    every connection is still created through the one call the test suite
    already fakes, so offline doubles keep working unchanged. Validates
    checkouts via ``closed`` (duck-typed: doubles without the attribute are
    treated as usable) and resets transactions on checkin; broken checkouts
    are discarded and replaced.
    """

    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10,
                 timeout: float = 30.0) -> None:
        self._dsn = dsn
        self._max_size = max_size
        self._timeout = timeout
        self._idle: "queue.Queue[object]" = queue.Queue()
        self._lock = threading.Lock()
        self._total = 0
        self._closed = False
        for _ in range(min_size):
            self._idle.put(self._new_connection())
            with self._lock:
                self._total += 1

    def _new_connection(self):
        import psycopg  # noqa: PLC0415 - lazy so the driver stays optional
        return psycopg.connect(self._dsn)

    @staticmethod
    def _is_usable(connection) -> bool:
        return not bool(getattr(connection, "closed", False))

    def _discard(self, connection) -> None:
        try:
            connection.close()
        except Exception:
            pass
        finally:
            with self._lock:
                self._total -= 1

    def acquire(self):
        """Check out a connection, creating or waiting within limits."""
        while True:
            try:
                candidate = self._idle.get_nowait()
            except queue.Empty:
                candidate = None
            if candidate is not None:
                if self._is_usable(candidate):
                    return candidate
                self._discard(candidate)
                continue
            with self._lock:
                may_create = self._total < self._max_size and not self._closed
                if may_create:
                    self._total += 1
            if may_create:
                try:
                    return self._new_connection()
                except Exception:
                    with self._lock:
                        self._total -= 1
                    raise
            if self._closed:
                from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
                raise EmbeddingError(
                    "Database connection pool is closed.",
                    EmbeddingErrorType.CONFIGURATION,
                )
            try:
                candidate = self._idle.get(timeout=self._timeout)
            except queue.Empty:
                from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
                raise EmbeddingError(
                    "Timed out waiting for a database connection from the pool.",
                    EmbeddingErrorType.TIMEOUT,
                )
            if self._is_usable(candidate):
                return candidate
            self._discard(candidate)

    def release(self, connection) -> None:
        """Return a connection; resets its transaction, discards if broken/closed."""
        if self._closed:
            try:
                connection.close()
            except Exception:
                pass
            return
        try:
            connection.rollback()
        except Exception:
            self._discard(connection)
            return
        try:
            self._idle.put_nowait(connection)
        except queue.Full:  # pragma: no cover - cannot happen while accounting holds
            self._discard(connection)

    def close(self) -> None:
        """Drain the pool; checkout after close raises. Idempotent."""
        self._closed = True
        while True:
            try:
                connection = self._idle.get_nowait()
            except queue.Empty:
                break
            try:
                connection.close()
            except Exception:
                pass
        with self._lock:
            self._total = 0


class PostgresDatabase:
    """Provides short-lived connections to the Supabase Postgres database.

    Connections come from one process-wide pool, so repeated short queries —
    including cache-HIT paths — reuse handshakes instead of opening a fresh
    TCP+TLS connection per call. The DSN is environment-global in practice,
    which is what makes a shared pool coherent. The pool is built on the
    existing ``psycopg.connect`` choke point (no new dependency), so offline
    doubles keep working unchanged.
    """

    _pool = None
    _pool_lock = threading.Lock()

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn

    @property
    def dsn(self) -> str:
        return (
            self._dsn if self._dsn is not None else resolve_database_dsn()
        ).strip()

    def is_configured(self) -> bool:
        return bool(self.dsn)

    def _get_pool(self) -> "_SimpleConnectionPool":
        """Lazily open the shared pool. No driver import here, so the pool
        layer itself never makes the module unimportable."""
        if self._pool is None:
            with PostgresDatabase._pool_lock:
                if self._pool is None:
                    PostgresDatabase._pool = _SimpleConnectionPool(self.dsn)
        return self._pool

    @contextmanager
    def connection(self) -> Iterator[object]:
        """Yield a pooled Postgres connection (returned to the pool on exit)."""
        dsn = self.dsn
        if not dsn:
            raise EmbeddingError(
                "Database is not configured. Set one of "
                f"{', '.join(DSN_ENV_VARS)} in the backend environment.",
                EmbeddingErrorType.CONFIGURATION,
            )
        try:
            import psycopg  # noqa: PLC0415 - lazy so the driver stays optional
        except ImportError as exc:
            raise EmbeddingError(
                "psycopg is not installed. Install backend dependencies with: "
                "pip install -r backend/requirements.txt",
                EmbeddingErrorType.CONFIGURATION,
            ) from exc

        pool = self._get_pool()
        connection = pool.acquire()
        try:
            yield connection
        finally:
            pool.release(connection)

    def close(self) -> None:
        """Drain the shared pool (app shutdown / test teardown). Idempotent."""
        pool, PostgresDatabase._pool = PostgresDatabase._pool, None
        if pool is not None:
            pool.close()
