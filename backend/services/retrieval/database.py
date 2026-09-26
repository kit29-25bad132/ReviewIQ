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
from contextlib import contextmanager
from typing import Iterator, Optional

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


class PostgresDatabase:
    """Provides short-lived connections to the Supabase Postgres database."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn

    @property
    def dsn(self) -> str:
        return (
            self._dsn if self._dsn is not None else resolve_database_dsn()
        ).strip()

    def is_configured(self) -> bool:
        return bool(self.dsn)

    @contextmanager
    def connection(self) -> Iterator[object]:
        """Yield a Postgres connection, closing it on exit."""
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

        connection = psycopg.connect(dsn)
        try:
            yield connection
        finally:
            connection.close()
