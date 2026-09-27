"""V2-P9 tests: cache storage (PostgresCacheStore + NoopCacheStore), offline.

The store is exercised against an in-memory fake ``PostgresDatabase``: no
driver, no DSN, no network. What is verified here is the SQL contract, the
row mapping, the JSONB parameter adaptation, the corpus-token format, and —
above all — the fail-open failure policy (every backend failure is a miss or a
no-op, never an exception that could break a ReviewIQ request).
"""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from services.cache.store import (
    EMBEDDING_TABLE,
    RESPONSE_TABLE,
    CacheStore,
    NoopCacheStore,
    PostgresCacheStore,
    _jsonb,
    _validate_table,
    build_cache_store,
)


# ---------------------------------------------------------------------------
# Fake database (duck-typed like services.retrieval.database.PostgresDatabase)
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, results=()):
        self.results = list(results)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(str(sql).split()), params))

    def fetchone(self):
        return self.results.pop(0) if self.results else None

    def fetchall(self):
        rows, self.results = self.results, []
        return rows


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return _NullContext(self._cursor)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class _NullContext:
    def __init__(self, value):
        self._value = value

    def __enter__(self):
        return self._value

    def __exit__(self, *exc):
        return False


class _FakeDatabase:
    """Yields one shared fake connection; ``fail=True`` makes connect raise."""

    def __init__(self, results=(), *, fail=False):
        self.cursor = _FakeCursor(results)
        self.connection_obj = _FakeConnection(self.cursor)
        self.fail = fail
        self.connect_count = 0

    @contextmanager
    def connection(self):
        self.connect_count += 1
        if self.fail:
            raise RuntimeError("connection refused")
        try:
            yield self.connection_obj
        finally:
            self.connection_obj.close()


def _store(results=(), *, fail=False) -> PostgresCacheStore:
    return PostgresCacheStore(database=_FakeDatabase(results, fail=fail))


def _valid_response_row(key="k1"):
    now = datetime(2026, 9, 27, tzinfo=timezone.utc)
    return {
        "cache_key": key,
        "payload": {"kind": "review_analysis", "cache_schema": "1", "result": {}},
        "provenance": {"task": "review_analysis"},
        "rag_context_digest": None,
        "corpus_token": None,
        "created_at": now,
        "expires_at": now,
    }


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_maps_tuple_row_to_dict_with_datetime_coercion():
    now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    row = ("k1", {"a": 1}, None, None, None, "2026-09-27T12:00:00+00:00", now)
    store = _store(results=[row])
    data = store.get(RESPONSE_TABLE, "k1")
    assert data["cache_key"] == "k1"
    assert data["payload"] == {"a": 1}
    assert isinstance(data["created_at"], datetime)
    assert data["created_at"] == now
    assert isinstance(data["expires_at"], datetime)


def test_get_returns_none_when_row_missing():
    assert _store(results=[]).get(RESPONSE_TABLE, "nope") is None


def test_get_uses_expected_sql():
    database = _FakeDatabase(results=[])
    PostgresCacheStore(database=database).get(EMBEDDING_TABLE, "k1")
    sql, params = database.cursor.executed[0]
    assert sql.startswith("SELECT cache_key, vector, task_type, model, dimension")
    assert "FROM embedding_cache WHERE cache_key = %s" in sql
    assert params == ("k1",)


def test_get_rejects_unknown_or_injected_table_identifier():
    database = _FakeDatabase(results=[])
    store = PostgresCacheStore(database=database)
    assert store.get("ai_response_cache; drop table reviews", "k") is None
    assert store.get("", "k") is None
    assert _validate_table("reviews") is None
    assert database.connect_count == 0


def test_get_fail_open_when_connection_fails():
    assert _store(fail=True).get(RESPONSE_TABLE, "k1") is None


# ---------------------------------------------------------------------------
# get_many (batched lookup: one SELECT, never N)
# ---------------------------------------------------------------------------

def test_get_many_uses_one_batched_select_with_any():
    now = datetime(2026, 9, 27, tzinfo=timezone.utc)
    row1 = ("k1", {"a": 1}, None, None, None, now, now)
    row2 = ("k2", {"b": 2}, None, None, None, now, now)
    database = _FakeDatabase(results=[row1, row2])
    store = PostgresCacheStore(database=database)
    results = store.get_many(EMBEDDING_TABLE, ["k1", "k2", "k1"])
    assert len(database.cursor.executed) == 1  # ONE statement for the batch
    sql, params = database.cursor.executed[0]
    assert sql.startswith("SELECT cache_key, vector, task_type, model, dimension")
    assert "FROM embedding_cache WHERE cache_key = ANY(%s)" in sql
    assert params == (["k1", "k2"],)  # deduplicated, order preserved
    # Requested order kept, duplicates reuse the same row, hits are dicts.
    assert [row["cache_key"] for row in results if row is not None] == ["k1", "k2", "k1"]
    assert results[0] == results[2]
    assert isinstance(results[0]["expires_at"], datetime)


def test_get_many_maps_missing_keys_to_none_in_place():
    now = datetime(2026, 9, 27, tzinfo=timezone.utc)
    row = ("k2", {"b": 2}, None, None, None, now, now)
    store = _store(results=[row])
    results = store.get_many(RESPONSE_TABLE, ["k1", "k2", "k3"])
    assert results[0] is None
    assert results[1]["cache_key"] == "k2"
    assert results[2] is None


def test_get_many_fail_open_when_connection_fails():
    assert _store(fail=True).get_many(RESPONSE_TABLE, ["k1", "k2"]) == [None, None]


def test_get_many_rejects_unknown_table_without_connecting():
    database = _FakeDatabase(results=[])
    store = PostgresCacheStore(database=database)
    assert store.get_many("ai_response_cache; drop table reviews", ["k"]) == [None]
    assert store.get_many("reviews", ["k"]) == [None]
    assert database.connect_count == 0


def test_get_many_with_no_keys_is_empty_without_connecting():
    database = _FakeDatabase(results=[])
    store = PostgresCacheStore(database=database)
    assert store.get_many(EMBEDDING_TABLE, []) == []
    assert database.connect_count == 0
    assert database.cursor.executed == []


def test_noop_store_get_many_is_always_a_miss():
    assert NoopCacheStore().get_many(RESPONSE_TABLE, ["k1", "k2"]) == [None, None]


# ---------------------------------------------------------------------------
# put
# ---------------------------------------------------------------------------

def test_put_runs_cleanup_then_upsert_and_commits():
    database = _FakeDatabase()
    store = PostgresCacheStore(database=database)
    row = _valid_response_row()
    store.put(RESPONSE_TABLE, row)
    executed = database.cursor.executed
    assert len(executed) == 2
    cleanup_sql, cleanup_params = executed[0]
    assert cleanup_sql == "DELETE FROM ai_response_cache WHERE expires_at < %s"
    assert len(cleanup_params) == 1
    upsert_sql, upsert_params = executed[1]
    assert upsert_sql.startswith("INSERT INTO ai_response_cache")
    assert "ON CONFLICT (cache_key) DO UPDATE SET" in upsert_sql
    assert "payload = EXCLUDED.payload" in upsert_sql
    assert len(upsert_params) == 7
    assert database.connection_obj.committed is True


def test_put_wraps_jsonb_columns_with_psycopg_jsonb():
    jsonb = pytest.importorskip("psycopg.types.json").Jsonb
    database = _FakeDatabase()
    PostgresCacheStore(database=database).put(RESPONSE_TABLE, _valid_response_row())
    _, params = database.cursor.executed[1]
    payload_param, provenance_param = params[1], params[2]
    assert isinstance(payload_param, jsonb)
    assert isinstance(provenance_param, jsonb)


def test_put_rejects_incomplete_row_without_touching_the_db():
    database = _FakeDatabase()
    store = PostgresCacheStore(database=database)
    store.put(RESPONSE_TABLE, {"cache_key": "k1", "payload": {}})
    assert database.connect_count == 0
    assert database.cursor.executed == []


def test_put_rejects_unknown_table_without_touching_the_db():
    database = _FakeDatabase()
    store = PostgresCacheStore(database=database)
    store.put("reviews", dict(cache_key="k", payload={}))
    assert database.connect_count == 0


def test_put_fail_open_when_connection_fails():
    _store(fail=True).put(RESPONSE_TABLE, _valid_response_row())  # must not raise


def test_jsonb_adapter_wraps_dict_and_falls_back_to_json_text():
    jsonb = pytest.importorskip("psycopg.types.json").Jsonb
    wrapped = _jsonb({"a": 1})
    assert isinstance(wrapped, jsonb)
    assert _jsonb(None) is None


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_executes_and_commits():
    database = _FakeDatabase()
    PostgresCacheStore(database=database).delete(RESPONSE_TABLE, "k1")
    sql, params = database.cursor.executed[0]
    assert sql == "DELETE FROM ai_response_cache WHERE cache_key = %s"
    assert params == ("k1",)
    assert database.connection_obj.committed is True


def test_delete_fail_open_when_connection_fails():
    _store(fail=True).delete(RESPONSE_TABLE, "k1")  # must not raise


def test_delete_rejects_unknown_table_and_empty_key():
    database = _FakeDatabase()
    store = PostgresCacheStore(database=database)
    store.delete("reviews", "k1")
    store.delete(RESPONSE_TABLE, "")
    assert database.connect_count == 0


# ---------------------------------------------------------------------------
# corpus token (RAG safety-critical lookup)
# ---------------------------------------------------------------------------

def test_corpus_token_is_deterministic_representative_string():
    updated = datetime(2026, 9, 1, 8, 30, tzinfo=timezone.utc)
    store = _store(results=[(3, updated)])
    assert store.corpus_token() == "v1|3|2026-09-01T08:30:00+00:00"


def test_corpus_token_is_none_when_lookup_fails():
    assert _store(fail=True).corpus_token() is None


def test_corpus_token_is_none_when_no_row():
    assert _store(results=[]).corpus_token() is None


def test_corpus_token_never_raises_on_malformed_row():
    assert _store(results=[("only-one-column",)]).corpus_token() is None


# ---------------------------------------------------------------------------
# Noop store + factory
# ---------------------------------------------------------------------------

def test_noop_store_is_always_a_miss():
    store = NoopCacheStore()
    assert store.get(RESPONSE_TABLE, "k") is None
    assert store.corpus_token() is None
    store.put(RESPONSE_TABLE, _valid_response_row())  # no-op, must not raise
    store.delete(RESPONSE_TABLE, "k")  # no-op, must not raise


def test_build_cache_store_returns_postgres_store():
    store = build_cache_store()
    assert isinstance(store, PostgresCacheStore)
    assert isinstance(store, CacheStore)
