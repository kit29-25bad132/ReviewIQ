"""V2-P2 tests: pgvector repository SQL/filtering (offline, fake DB)."""

import sys
from contextlib import contextmanager

import pytest

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.retrieval.database import PostgresDatabase, resolve_database_dsn
from services.retrieval.postgres_vector_repository import PostgresVectorRepository
from services.retrieval.vector_repository import ReviewSearchFilters, ReviewVectorRecord


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.db.executed.append((sql, params))
        if self.db.fail_execute is not None:
            raise self.db.fail_execute
        self._rows = self.db.script.pop(0) if self.db.script else []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.db.commits += 1

    def close(self):
        self.db.closed += 1


class FakeDatabase:
    def __init__(self, script=None):
        self.script = list(script or [])
        self.executed = []
        self.commits = 0
        self.closed = 0
        self.fail_execute = None

    @contextmanager
    def connection(self):
        yield FakeConnection(self)


def _record(review_id="r1", fingerprint="fp1", embedding=(0.1, 0.2, 0.3, 0.4)):
    return ReviewVectorRecord(
        review_id=review_id,
        fingerprint=fingerprint,
        original_text="The battery lasts all day.",
        normalized_text="The battery lasts all day.",
        embedding=list(embedding),
        embedding_model="gemini-embedding-001",
        embedding_dimension=4,
        product_id="p1",
        rating=5,
        source="dataset",
    )


def _repository(script=None):
    db = FakeDatabase(script)
    return PostgresVectorRepository(database=db), db


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------

def test_upsert_writes_and_commits():
    repo, db = _repository()
    written = repo.upsert([_record()])
    assert written == 1
    assert db.commits == 1
    sql, params = db.executed[0]
    assert "INSERT INTO review_embeddings" in sql
    assert "ON CONFLICT (fingerprint) DO UPDATE" in sql
    assert "%s::vector" in sql
    assert params[-1] == "[0.1,0.2,0.3,0.4]"
    assert params[2] == "fp1"


def test_upsert_empty_returns_zero_without_db_call():
    repo, db = _repository()
    assert repo.upsert([]) == 0
    assert db.executed == []


def test_upsert_dimension_mismatch_rejected_before_db():
    repo, db = _repository()
    bad = ReviewVectorRecord(
        review_id="r1",
        fingerprint="fp1",
        original_text="x",
        normalized_text="x",
        embedding=[0.1, 0.2],
        embedding_model="m",
        embedding_dimension=4,
    )
    with pytest.raises(EmbeddingError) as excinfo:
        repo.upsert([bad])
    assert excinfo.value.error_type is EmbeddingErrorType.DIMENSION_MISMATCH
    assert db.executed == []


def test_upsert_empty_vector_rejected():
    repo, _ = _repository()
    bad = ReviewVectorRecord(
        review_id="r1", fingerprint="fp1", original_text="x",
        normalized_text="x", embedding=[], embedding_model="m", embedding_dimension=0,
    )
    with pytest.raises(EmbeddingError) as excinfo:
        repo.upsert([bad])
    assert excinfo.value.error_type is EmbeddingErrorType.EMPTY_RESPONSE


def test_upsert_database_error_normalized():
    repo, db = _repository()
    db.fail_execute = RuntimeError("connection reset by peer")
    with pytest.raises(EmbeddingError) as excinfo:
        repo.upsert([_record()])
    assert excinfo.value.error_type is EmbeddingErrorType.DATABASE_ERROR
    assert "connection reset" not in str(excinfo.value)  # raw driver text not echoed


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def _search_row(similarity=0.8):
    return ("r1", "p1", "The battery lasts all day.", "The battery lasts all day.",
            5, "dataset", "gemini-embedding-001", similarity)


def test_search_uses_cosine_ordering_and_limit():
    repo, db = _repository(script=[[_search_row()]])
    results = repo.search(
        [0.1, 0.2, 0.3, 0.4],
        embedding_model="gemini-embedding-001",
        dimension=4,
        top_k=5,
    )
    assert len(results) == 1
    sql, params = db.executed[0]
    assert "embedding <=> %s::vector" in sql
    assert "ORDER BY embedding <=> %s::vector ASC" in sql
    assert "LIMIT %s" in sql
    assert params[0] == "[0.1,0.2,0.3,0.4]"
    assert params[-1] == 5
    assert "gemini-embedding-001" in params and 4 in params


def test_search_maps_similarity_and_distance():
    repo, _ = _repository(script=[[_search_row(similarity=0.75)]])
    result = repo.search(
        [0.1] * 4, embedding_model="m", dimension=4, top_k=1
    )[0]
    assert result.review_id == "r1"
    assert result.product_id == "p1"
    assert result.review_text == "The battery lasts all day."
    assert result.similarity == pytest.approx(0.75)
    assert result.distance == pytest.approx(0.25)
    assert result.rating == 5
    assert result.source == "dataset"


def test_search_threshold_added_to_sql_and_params():
    repo, db = _repository(script=[[]])
    repo.search(
        [0.1] * 4,
        embedding_model="m",
        dimension=4,
        top_k=3,
        similarity_threshold=0.6,
    )
    sql, params = db.executed[0]
    assert "(1 - (embedding <=> %s::vector)) >= %s" in sql
    assert 0.6 in params


def test_search_metadata_filters_added_to_sql_and_params():
    repo, db = _repository(script=[[]])
    filters = ReviewSearchFilters(
        product_id="p1",
        min_rating=1,
        max_rating=3,
        source="dataset",
        review_date_from="2024-01-01T00:00:00",
        review_date_to="2024-12-31T00:00:00",
    )
    repo.search(
        [0.1] * 4, embedding_model="m", dimension=4, top_k=3, filters=filters
    )
    sql, params = db.executed[0]
    for clause in (
        "product_id = %s",
        "rating >= %s",
        "rating <= %s",
        "source = %s",
        "review_date >= %s",
        "review_date <= %s",
    ):
        assert clause in sql
    assert "p1" in params and 1 in params and 3 in params and "dataset" in params


def test_search_empty_vector_rejected():
    repo, _ = _repository()
    with pytest.raises(EmbeddingError) as excinfo:
        repo.search([], embedding_model="m", dimension=4, top_k=1)
    assert excinfo.value.error_type is EmbeddingErrorType.EMPTY_RESPONSE


def test_search_dimension_mismatch_rejected():
    repo, _ = _repository()
    with pytest.raises(EmbeddingError) as excinfo:
        repo.search([0.1, 0.2], embedding_model="m", dimension=4, top_k=1)
    assert excinfo.value.error_type is EmbeddingErrorType.DIMENSION_MISMATCH


def test_search_invalid_top_k_rejected():
    repo, _ = _repository()
    with pytest.raises(EmbeddingError) as excinfo:
        repo.search([0.1] * 4, embedding_model="m", dimension=4, top_k=0)
    assert excinfo.value.error_type is EmbeddingErrorType.INVALID_INPUT


def test_search_database_error_normalized():
    repo, db = _repository()
    db.fail_execute = RuntimeError("deadlock detected")
    with pytest.raises(EmbeddingError) as excinfo:
        repo.search([0.1] * 4, embedding_model="m", dimension=4, top_k=1)
    assert excinfo.value.error_type is EmbeddingErrorType.DATABASE_ERROR


def test_search_empty_result_is_empty_list():
    repo, _ = _repository(script=[[]])
    assert repo.search([0.1] * 4, embedding_model="m", dimension=4, top_k=5) == []


# ---------------------------------------------------------------------------
# fingerprints / metadata / count
# ---------------------------------------------------------------------------

def test_existing_fingerprints_returns_set():
    repo, _ = _repository(script=[[("fp1",), ("fp2",)]])
    assert repo.existing_fingerprints(["fp1", "fp2", "fp3"]) == {"fp1", "fp2"}


def test_existing_fingerprints_empty_input_skips_db():
    repo, db = _repository()
    assert repo.existing_fingerprints([]) == set()
    assert db.executed == []


def test_get_metadata_mapping_and_none():
    repo, _ = _repository(
        script=[[("r1", "p1", "gemini-embedding-001", 768, 5, "dataset", None)]]
    )
    meta = repo.get_metadata("r1")
    assert meta.review_id == "r1"
    assert meta.embedding_dimension == 768
    assert meta.product_id == "p1"

    repo_none, _ = _repository(script=[[]])
    assert repo_none.get_metadata("missing") is None


def test_count_returns_int():
    repo, _ = _repository(script=[[(42,)]])
    assert repo.count() == 42


def test_invalid_table_identifier_rejected():
    with pytest.raises(EmbeddingError) as excinfo:
        PostgresVectorRepository(database=FakeDatabase(), table="bad; drop table x")
    assert excinfo.value.error_type is EmbeddingErrorType.CONFIGURATION


# ---------------------------------------------------------------------------
# PostgresDatabase configuration
# ---------------------------------------------------------------------------

def test_database_not_configured_raises_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    assert resolve_database_dsn() == ""
    database = PostgresDatabase(dsn="")
    assert database.is_configured() is False
    with pytest.raises(EmbeddingError) as excinfo:
        with database.connection():
            pass
    assert excinfo.value.error_type is EmbeddingErrorType.CONFIGURATION


def test_missing_psycopg_driver_is_configuration_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    database = PostgresDatabase(dsn="postgresql://user:pass@localhost:5432/db")
    with pytest.raises(EmbeddingError) as excinfo:
        with database.connection():
            pass
    assert excinfo.value.error_type is EmbeddingErrorType.CONFIGURATION


def test_resolve_database_dsn_prefers_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://primary")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://secondary")
    assert resolve_database_dsn() == "postgresql://primary"
