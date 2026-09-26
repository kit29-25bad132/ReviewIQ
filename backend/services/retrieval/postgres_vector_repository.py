"""Postgres + pgvector implementation of :class:`VectorRepository`.

All similarity search uses pgvector's cosine distance operator ``<=>`` with an
HNSW ``vector_cosine_ops`` index (see ``supabase_schema.sql``). Vectors are
sent as pgvector text literals cast with ``::vector`` so no extra Python
pgvector adapter dependency is required.

SQL errors are normalized into ``EmbeddingError(DATABASE_ERROR)``; provider
internals never reach API callers.
"""

import json
import re
from typing import List, Mapping, Optional, Sequence, Set

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.retrieval.database import PostgresDatabase
from services.retrieval.vector_repository import (
    ReviewSearchFilters,
    ReviewSearchResult,
    ReviewVectorRecord,
    VectorMetadata,
    VectorRepository,
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_UPSERT_SQL = """
INSERT INTO {table} (
    review_id, product_id, fingerprint, original_text, normalized_text,
    rating, source, review_date, embedding_model, embedding_dimension, embedding
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
ON CONFLICT (fingerprint) DO UPDATE SET
    review_id = EXCLUDED.review_id,
    product_id = EXCLUDED.product_id,
    original_text = EXCLUDED.original_text,
    normalized_text = EXCLUDED.normalized_text,
    rating = EXCLUDED.rating,
    source = EXCLUDED.source,
    review_date = EXCLUDED.review_date,
    embedding_model = EXCLUDED.embedding_model,
    embedding_dimension = EXCLUDED.embedding_dimension,
    embedding = EXCLUDED.embedding,
    updated_at = timezone('utc'::text, now())
"""

_SEARCH_SQL = """
SELECT
    review_id, product_id, original_text, normalized_text,
    rating, source, embedding_model,
    1 - (embedding <=> %s::vector) AS similarity
FROM {table}
WHERE {where}
ORDER BY embedding <=> %s::vector ASC
LIMIT %s
"""

_EXISTING_FINGERPRINTS_SQL = """
SELECT fingerprint FROM {table} WHERE fingerprint = ANY(%s)
"""

_METADATA_SQL = """
SELECT review_id, product_id, embedding_model, embedding_dimension,
       rating, source, updated_at
FROM {table}
WHERE review_id = %s
ORDER BY updated_at DESC
LIMIT 1
"""

_COUNT_SQL = "SELECT COUNT(*) FROM {table}"

_RESULT_COLUMNS = (
    "review_id",
    "product_id",
    "original_text",
    "normalized_text",
    "rating",
    "source",
    "embedding_model",
    "similarity",
)
_METADATA_COLUMNS = (
    "review_id",
    "product_id",
    "embedding_model",
    "embedding_dimension",
    "rating",
    "source",
    "updated_at",
)


def _validate_table_name(name: str) -> str:
    if not _IDENTIFIER_RE.match(name or ""):
        raise EmbeddingError(
            f"Invalid vector table identifier: {name!r}.",
            EmbeddingErrorType.CONFIGURATION,
        )
    return name


def _vector_literal(vector: Sequence[float]) -> str:
    """Format a vector as a pgvector text literal, e.g. ``[0.1,-0.2,0.3]``."""
    return json.dumps([float(value) for value in vector], separators=(",", ":"))


def _row_as_mapping(row: object, columns: Sequence[str]) -> Mapping[str, object]:
    if isinstance(row, Mapping):
        return row
    return dict(zip(columns, row))  # type: ignore[arg-type]


class PostgresVectorRepository(VectorRepository):
    """pgvector-backed review embedding store."""

    DEFAULT_TABLE = "review_embeddings"

    def __init__(
        self, database: Optional[PostgresDatabase] = None, table: str = DEFAULT_TABLE
    ) -> None:
        self._database = database or PostgresDatabase()
        self._table = _validate_table_name(table)

    @property
    def database(self) -> PostgresDatabase:
        return self._database

    # -- writes ------------------------------------------------------------

    def upsert(self, records: Sequence[ReviewVectorRecord]) -> int:
        records = list(records)
        if not records:
            return 0
        written = 0
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    for record in records:
                        self._validate_record(record)
                        cursor.execute(
                            _UPSERT_SQL.format(table=self._table),
                            self._upsert_params(record),
                        )
                        written += 1
                connection.commit()
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                "Vector store upsert failed.",
                EmbeddingErrorType.DATABASE_ERROR,
            ) from exc
        return written

    @staticmethod
    def _upsert_params(record: ReviewVectorRecord) -> tuple:
        return (
            record.review_id,
            record.product_id,
            record.fingerprint,
            record.original_text,
            record.normalized_text,
            record.rating,
            record.source,
            record.review_date,
            record.embedding_model,
            record.embedding_dimension,
            _vector_literal(record.embedding),
        )

    @staticmethod
    def _validate_record(record: ReviewVectorRecord) -> None:
        """Refuse to persist empty or wrong-size vectors (no truncation/padding)."""
        if not record.embedding:
            raise EmbeddingError(
                "Refusing to store an empty embedding vector.",
                EmbeddingErrorType.EMPTY_RESPONSE,
            )
        if len(record.embedding) != record.embedding_dimension:
            raise EmbeddingError(
                f"Embedding dimension mismatch: record declares "
                f"{record.embedding_dimension} but vector has "
                f"{len(record.embedding)} values.",
                EmbeddingErrorType.DIMENSION_MISMATCH,
            )

    # -- reads -------------------------------------------------------------

    def search(
        self,
        query_vector: Sequence[float],
        *,
        embedding_model: str,
        dimension: int,
        top_k: int,
        similarity_threshold: Optional[float] = None,
        filters: Optional[ReviewSearchFilters] = None,
    ) -> List[ReviewSearchResult]:
        if not query_vector:
            raise EmbeddingError(
                "Query vector is empty.", EmbeddingErrorType.EMPTY_RESPONSE
            )
        if len(query_vector) != dimension:
            raise EmbeddingError(
                f"Query vector dimension mismatch: expected {dimension}, "
                f"received {len(query_vector)}.",
                EmbeddingErrorType.DIMENSION_MISMATCH,
            )
        if top_k < 1:
            raise EmbeddingError(
                "top_k must be at least 1.", EmbeddingErrorType.INVALID_INPUT
            )

        vector_literal = _vector_literal(query_vector)
        where_parts = ["embedding_model = %s", "embedding_dimension = %s"]
        where_params: List[object] = [embedding_model, dimension]

        if filters is not None:
            if filters.product_id is not None:
                where_parts.append("product_id = %s")
                where_params.append(filters.product_id)
            if filters.min_rating is not None:
                where_parts.append("rating >= %s")
                where_params.append(filters.min_rating)
            if filters.max_rating is not None:
                where_parts.append("rating <= %s")
                where_params.append(filters.max_rating)
            if filters.source is not None:
                where_parts.append("source = %s")
                where_params.append(filters.source)
            if filters.review_date_from is not None:
                where_parts.append("review_date >= %s")
                where_params.append(filters.review_date_from)
            if filters.review_date_to is not None:
                where_parts.append("review_date <= %s")
                where_params.append(filters.review_date_to)

        if similarity_threshold is not None:
            # Similarity convention: 1 - cosine distance.
            where_parts.append("(1 - (embedding <=> %s::vector)) >= %s")
            where_params.extend([vector_literal, similarity_threshold])

        sql = _SEARCH_SQL.format(table=self._table, where=" AND ".join(where_parts))
        params = (vector_literal, *where_params, vector_literal, top_k)

        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall() or []
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                "Vector similarity search failed.",
                EmbeddingErrorType.DATABASE_ERROR,
            ) from exc
        return [self._to_result(row) for row in rows]

    @staticmethod
    def _to_result(row: object) -> ReviewSearchResult:
        data = _row_as_mapping(row, _RESULT_COLUMNS)
        similarity = float(data["similarity"])
        return ReviewSearchResult(
            review_id=str(data["review_id"]),
            product_id=data.get("product_id"),
            review_text=data["original_text"],
            normalized_text=data["normalized_text"],
            similarity=similarity,
            distance=1.0 - similarity,
            embedding_model=data["embedding_model"],
            rating=data.get("rating"),
            source=data.get("source"),
        )

    def existing_fingerprints(self, fingerprints: Sequence[str]) -> Set[str]:
        values = [fingerprint for fingerprint in fingerprints if fingerprint]
        if not values:
            return set()
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        _EXISTING_FINGERPRINTS_SQL.format(table=self._table),
                        (values,),
                    )
                    rows = cursor.fetchall() or []
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                "Vector store fingerprint lookup failed.",
                EmbeddingErrorType.DATABASE_ERROR,
            ) from exc
        return {str(row[0]) for row in rows}

    def get_metadata(self, review_id: str) -> Optional[VectorMetadata]:
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        _METADATA_SQL.format(table=self._table), (review_id,)
                    )
                    row = cursor.fetchone()
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                "Vector store metadata lookup failed.",
                EmbeddingErrorType.DATABASE_ERROR,
            ) from exc
        if row is None:
            return None
        data = _row_as_mapping(row, _METADATA_COLUMNS)
        return VectorMetadata(
            review_id=str(data["review_id"]),
            product_id=data.get("product_id"),
            rating=data.get("rating"),
            source=data.get("source"),
            embedding_model=data["embedding_model"],
            embedding_dimension=int(data["embedding_dimension"]),
            updated_at=data.get("updated_at"),
        )

    def count(self) -> int:
        try:
            with self._database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_COUNT_SQL.format(table=self._table))
                    row = cursor.fetchone()
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(
                "Vector store count failed.",
                EmbeddingErrorType.DATABASE_ERROR,
            ) from exc
        return int(row[0]) if row else 0
