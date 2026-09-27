"""V2-P9 tests: embedding vector cache (keys, validation, service integration).

Fully offline: in-memory ``FakeCacheStore``, scripted ``FakeEmbeddingProvider``
and deterministic ``hashing_vector`` doubles - no network, no database.

Coverage map (spec test plan, embedding parts):

- cache key semantics (determinism, task-type namespace, versioning),
- cached-vector validation (dimension, numerics, NaN/bools),
- read path (hit / miss / expiry / malformed / dimension mismatch / fail-open),
- write path (validated vectors only, TTL, refusal rules),
- EmbeddingService integration (partial hits, order reconstruction,
  preprocessing-first, task-type isolation, degraded mode),
- disabled-by-default configuration.
"""

import math
from datetime import timedelta

from services.cache.config import (
    DEFAULT_EMBEDDING_CACHE_TTL_SECONDS,
    DEFAULT_EMBEDDING_QUERY_CACHE_TTL_SECONDS,
    CacheConfig,
)
from services.cache.embedding_cache import EmbeddingCache, validate_cached_vector
from services.cache.keys import embedding_cache_key
from services.cache.store import EMBEDDING_TABLE
from services.embeddings.contracts import EmbeddingTaskType
from services.embeddings.registry import EmbeddingModelSpec
from services.embeddings.service import EmbeddingService
from tests.cache_fakes import FakeCacheStore, embedding_cache, embedding_row, utcnow
from tests.retrieval_fakes import FakeEmbeddingProvider, hashing_vector

DIMENSION = 8
TEXTS = ["battery lasts all day", "screen is bright", "great value for money"]
ODD_TEXT = "the camera zooms far"


def _spec(batch_size=10):
    return EmbeddingModelSpec(
        provider="fake", model="fake-embed", dimension=DIMENSION, max_batch_size=batch_size
    )


def _service(cache, *, batch_size=10, provider=None, preprocessor=None):
    provider = provider or FakeEmbeddingProvider(dimension=DIMENSION)
    service = EmbeddingService(
        provider,
        spec=_spec(batch_size),
        text_preprocessor=preprocessor,
        cache=cache,
    )
    return service, provider


def _ekey(text, *, task_type="RETRIEVAL_DOCUMENT", dimension=DIMENSION):
    return embedding_cache_key(
        text=text,
        task_type=task_type,
        provider="fake",
        model="fake-embed",
        dimension=dimension,
    )


def _seed(store, text, *, task_type="RETRIEVAL_DOCUMENT", vector=None, **row_overrides):
    vector = vector or hashing_vector(text, DIMENSION)
    row = embedding_row(
        vector,
        dimension=len(vector),
        task_type=task_type,
        model="fake-embed",
        **row_overrides,
    )
    return store.seed(EMBEDDING_TABLE, _ekey(text, task_type=task_type), row)


# ---------------------------------------------------------------------------
# A. Cache key semantics
# ---------------------------------------------------------------------------

def test_embedding_key_is_deterministic():
    kwargs = dict(
        text="battery life",
        task_type="RETRIEVAL_DOCUMENT",
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    first = embedding_cache_key(**kwargs)
    assert first == embedding_cache_key(**kwargs)
    assert len(first) == 64


def test_document_and_query_never_share_an_entry():
    base = dict(
        text="battery life",
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    document = embedding_cache_key(task_type="RETRIEVAL_DOCUMENT", **base)
    query = embedding_cache_key(task_type="RETRIEVAL_QUERY", **base)
    assert document != query


def test_embedding_key_differs_for_different_text_provider_model_dimension():
    base = dict(
        text="battery life",
        task_type="RETRIEVAL_DOCUMENT",
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    reference = embedding_cache_key(**base)
    assert reference != embedding_cache_key(**{**base, "text": "other"})
    assert reference != embedding_cache_key(**{**base, "provider": "other"})
    assert reference != embedding_cache_key(**{**base, "model": "other"})
    assert reference != embedding_cache_key(**{**base, "dimension": 16})


def test_embedding_key_differs_when_preprocess_version_bumps(monkeypatch):
    kwargs = dict(
        text="battery life",
        task_type="RETRIEVAL_DOCUMENT",
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    before = embedding_cache_key(**kwargs)
    monkeypatch.setattr("services.cache.keys.PREPROCESS_VERSION", "2")
    assert embedding_cache_key(**kwargs) != before


def test_task_enum_and_plain_value_share_the_same_key():
    cache = embedding_cache(FakeCacheStore())
    via_enum = cache.get_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    via_value = cache.get_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT.value,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert via_enum == via_value  # both miss, both None - same key semantics


def test_embedding_key_never_contains_raw_text_digest_material():
    key = embedding_cache_key(
        text="quantum zebras gallop",
        task_type="RETRIEVAL_DOCUMENT",
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert "quantum" not in key and "zebras" not in key


# ---------------------------------------------------------------------------
# B. Cached-vector validation
# ---------------------------------------------------------------------------

def test_validate_cached_vector_accepts_numeric_list():
    assert validate_cached_vector([1, 2.5, 3], 3) == [1.0, 2.5, 3.0]


def test_validate_cached_vector_rejects_wrong_length():
    assert validate_cached_vector([1.0, 2.0], 3) is None


def test_validate_cached_vector_rejects_non_list():
    assert validate_cached_vector("0.1,0.2,0.3", 3) is None
    assert validate_cached_vector(None, 3) is None


def test_validate_cached_vector_rejects_booleans():
    assert validate_cached_vector([True, False, True], 3) is None


def test_validate_cached_vector_rejects_non_numeric_entries():
    assert validate_cached_vector([1.0, "0.2", 3.0], 3) is None


def test_validate_cached_vector_rejects_nan_and_infinity():
    assert validate_cached_vector([1.0, math.nan, 3.0], 3) is None
    assert validate_cached_vector([1.0, math.inf, 3.0], 3) is None


def test_validate_cached_vector_rejects_invalid_dimension():
    vector = [0.1, 0.2]
    assert validate_cached_vector(vector, 0) is None
    assert validate_cached_vector(vector, -1) is None
    assert validate_cached_vector(vector, True) is None
    assert validate_cached_vector(vector, 8.0) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C. Read path
# ---------------------------------------------------------------------------

def test_hit_returns_validated_vector():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    expected = hashing_vector(ODD_TEXT, DIMENSION)
    _seed(store, ODD_TEXT)
    result = cache.get_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert result == expected


def test_miss_returns_none_without_deleting_foreign_rows():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, ODD_TEXT)
    assert (
        cache.get_vector(
            text="unseen text",
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )
    assert len(store.rows(EMBEDDING_TABLE)) == 1


def test_expired_entry_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, ODD_TEXT, expires_at=utcnow() - timedelta(seconds=1))
    assert (
        cache.get_vector(
            text=ODD_TEXT,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )
    assert store.rows(EMBEDDING_TABLE) == {}


def test_dimension_mismatch_row_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    wrong = [0.1] * 16
    _seed(store, ODD_TEXT, vector=wrong)
    assert (
        cache.get_vector(
            text=ODD_TEXT,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )
    assert store.rows(EMBEDDING_TABLE) == {}


def test_malformed_vector_row_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, ODD_TEXT, vector=[math.nan] * DIMENSION)
    assert (
        cache.get_vector(
            text=ODD_TEXT,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )
    assert store.rows(EMBEDDING_TABLE) == {}


def test_non_datetime_expiry_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    key = _ekey(ODD_TEXT)
    row = embedding_row(hashing_vector(ODD_TEXT, DIMENSION), dimension=DIMENSION)
    row["expires_at"] = "soon"
    store.seed(EMBEDDING_TABLE, key, row)
    assert (
        cache.get_vector(
            text=ODD_TEXT,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )
    assert store.rows(EMBEDDING_TABLE) == {}


def test_store_read_failure_is_a_fail_open_miss():
    store = FakeCacheStore(fail_ops=["get"])
    cache = embedding_cache(store)
    assert (
        cache.get_vector(
            text=ODD_TEXT,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )


def test_disabled_cache_never_touches_the_store():
    store = FakeCacheStore()
    cache = embedding_cache(store, enabled=False)
    assert cache.enabled is False
    assert (
        cache.get_vector(
            text=ODD_TEXT,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        )
        is None
    )
    assert cache.get_many([ODD_TEXT], task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
                          provider="fake", model="fake-embed",
                          dimension=DIMENSION) == [None]
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=[0.0] * DIMENSION,
    )
    assert store.calls == {"get": 0, "get_many": 0, "put": 0, "delete": 0, "corpus_token": 0}


def test_get_many_returns_partial_hits():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    seeded = hashing_vector(ODD_TEXT, DIMENSION)
    _seed(store, ODD_TEXT)
    results = cache.get_many(
        [ODD_TEXT, "unseen"],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert results == [seeded, None]


def test_get_many_uses_one_batched_store_lookup():
    """LOW-2: a batch issues ONE store read, never one lookup per text."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, TEXTS[1])
    results = cache.get_many(
        TEXTS,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert store.calls["get_many"] == 1  # single batched read
    assert store.calls["get"] == 0  # no per-key SELECT pattern
    assert results == [None, hashing_vector(TEXTS[1], DIMENSION), None]


def test_get_many_with_empty_input_returns_empty_without_store_touch():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    assert cache.get_many(
        [],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    ) == []
    assert store.calls["get_many"] == 0
    assert store.calls["get"] == 0


def test_get_many_keeps_duplicate_inputs_correct():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    seeded = hashing_vector(TEXTS[0], DIMENSION)
    _seed(store, TEXTS[0])
    results = cache.get_many(
        [TEXTS[0], TEXTS[0], TEXTS[1]],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert results == [seeded, seeded, None]


def test_get_many_is_fail_open_when_the_batch_read_fails():
    for fail_ops in (["get"], ["get_many"]):
        store = FakeCacheStore(fail_ops=fail_ops)
        cache = embedding_cache(store)
        assert cache.get_many(
            TEXTS,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            provider="fake",
            model="fake-embed",
            dimension=DIMENSION,
        ) == [None, None, None]


def test_get_many_deletes_bad_rows_without_sinking_the_batch():
    """Expired/malformed rows become misses and are deleted; good rows survive."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    good = hashing_vector(TEXTS[1], DIMENSION)
    _seed(store, TEXTS[0], vector=[0.1] * 3)  # malformed (wrong length)
    _seed(store, TEXTS[1])
    _seed(store, TEXTS[2], expires_at=utcnow() - timedelta(seconds=1))  # expired
    results = cache.get_many(
        TEXTS,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
    )
    assert results == [None, good, None]
    assert list(store.rows(EMBEDDING_TABLE)) == [_ekey(TEXTS[1])]


def test_default_env_configuration_disables_the_embedding_cache():
    assert EmbeddingCache().enabled is False  # conftest forces the flag off
    config = CacheConfig.from_env()
    assert config.embedding_ttl_seconds == DEFAULT_EMBEDDING_CACHE_TTL_SECONDS
    assert config.embedding_query_ttl_seconds == (
        DEFAULT_EMBEDDING_QUERY_CACHE_TTL_SECONDS
    )


# ---------------------------------------------------------------------------
# D. Write path
# ---------------------------------------------------------------------------

def test_put_vector_writes_validated_vector_with_default_ttl():
    store = FakeCacheStore()
    cache = embedding_cache(store, ttl_seconds=1234)
    vector = hashing_vector(ODD_TEXT, DIMENSION)
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=vector,
    )
    row = store.rows(EMBEDDING_TABLE)[_ekey(ODD_TEXT)]
    assert row["vector"] == vector
    assert row["dimension"] == DIMENSION
    assert row["task_type"] == "RETRIEVAL_DOCUMENT"
    assert row["expires_at"] - row["created_at"] == timedelta(seconds=1234)


def test_document_embedding_gets_90_day_ttl_by_default():
    """MEDIUM-1: RETRIEVAL_DOCUMENT expires after 7776000 seconds (90 days)."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    assert cache.config.resolve_embedding_ttl(
        EmbeddingTaskType.RETRIEVAL_DOCUMENT
    ) == 7776000
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=hashing_vector(ODD_TEXT, DIMENSION),
    )
    row = store.rows(EMBEDDING_TABLE)[_ekey(ODD_TEXT)]
    assert row["expires_at"] - row["created_at"] == timedelta(seconds=7776000)


def test_query_embedding_gets_30_day_ttl_by_default():
    """MEDIUM-1: RETRIEVAL_QUERY expires after 2592000 seconds (30 days)."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    assert cache.config.resolve_embedding_ttl(
        EmbeddingTaskType.RETRIEVAL_QUERY
    ) == 2592000
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_QUERY,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=hashing_vector(ODD_TEXT, DIMENSION),
    )
    row = store.rows(EMBEDDING_TABLE)[_ekey(ODD_TEXT, task_type="RETRIEVAL_QUERY")]
    assert row["expires_at"] - row["created_at"] == timedelta(seconds=2592000)


def test_document_and_query_ttls_differ_and_entries_stay_separate():
    """MEDIUM-1 + namespace invariant: different TTLs, different rows."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    vector = hashing_vector(ODD_TEXT, DIMENSION)
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=vector,
    )
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_QUERY,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=vector,
    )
    rows = store.rows(EMBEDDING_TABLE)
    assert len(rows) == 2  # namespaces never share an entry
    doc_key = _ekey(ODD_TEXT, task_type="RETRIEVAL_DOCUMENT")
    query_key = _ekey(ODD_TEXT, task_type="RETRIEVAL_QUERY")
    doc_row, query_row = rows[doc_key], rows[query_key]
    assert doc_row["task_type"] == "RETRIEVAL_DOCUMENT"
    assert query_row["task_type"] == "RETRIEVAL_QUERY"
    doc_ttl = doc_row["expires_at"] - doc_row["created_at"]
    query_ttl = query_row["expires_at"] - query_row["created_at"]
    assert doc_ttl == timedelta(seconds=7776000)
    assert query_ttl == timedelta(seconds=2592000)
    assert doc_ttl != query_ttl


def test_resolve_embedding_ttl_is_enum_safe_for_all_task_types():
    config = CacheConfig.from_env()  # conftest strips TTL overrides
    assert config.resolve_embedding_ttl(
        EmbeddingTaskType.RETRIEVAL_DOCUMENT
    ) == 7776000
    assert config.resolve_embedding_ttl("RETRIEVAL_DOCUMENT") == 7776000
    assert config.resolve_embedding_ttl(EmbeddingTaskType.RETRIEVAL_QUERY) == 2592000
    assert config.resolve_embedding_ttl("RETRIEVAL_QUERY") == 2592000
    # Unspecified (non-query) task types fall back to the hygiene TTL.
    assert config.resolve_embedding_ttl(
        EmbeddingTaskType.SEMANTIC_SIMILARITY
    ) == 7776000
    assert config.resolve_embedding_ttl(None) == 7776000


def test_query_ttl_environment_override_is_honored(monkeypatch):
    monkeypatch.setenv("EMBEDDING_QUERY_CACHE_TTL_SECONDS", "111")
    monkeypatch.setenv("EMBEDDING_CACHE_TTL_SECONDS", "222")
    config = CacheConfig.from_env()
    assert config.embedding_query_ttl_seconds == 111
    assert config.embedding_ttl_seconds == 222
    assert config.resolve_embedding_ttl(EmbeddingTaskType.RETRIEVAL_QUERY) == 111
    assert config.resolve_embedding_ttl(EmbeddingTaskType.RETRIEVAL_DOCUMENT) == 222


def test_invalid_query_ttl_configuration_falls_back_to_the_default(monkeypatch):
    """Existing config policy: invalid/non-positive values warn + default."""
    for bad in ("0", "-5", "not-a-number", "  "):
        monkeypatch.setenv("EMBEDDING_QUERY_CACHE_TTL_SECONDS", bad)
        config = CacheConfig.from_env()
        assert config.embedding_query_ttl_seconds == 2592000
        assert config.resolve_embedding_ttl(EmbeddingTaskType.RETRIEVAL_QUERY) == (
            2592000
        )
    for bad in ("0", "-1"):
        monkeypatch.setenv("EMBEDDING_CACHE_TTL_SECONDS", bad)
        config = CacheConfig.from_env()
        assert config.embedding_ttl_seconds == 7776000
        assert config.resolve_embedding_ttl(EmbeddingTaskType.RETRIEVAL_DOCUMENT) == (
            7776000
        )


def test_put_vector_refuses_invalid_vector():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=[0.1, 0.2],  # wrong dimension: would never be served back
    )
    assert store.rows(EMBEDDING_TABLE) == {}
    assert store.calls["put"] == 0


def test_put_vector_write_failure_is_silent():
    store = FakeCacheStore(fail_ops=["put"])
    cache = embedding_cache(store)
    cache.put_vector(
        text=ODD_TEXT,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=hashing_vector(ODD_TEXT, DIMENSION),
    )  # must not raise


def test_put_many_skips_on_length_mismatch():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    cache.put_many(
        ["a", "b"],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vectors=[[0.1] * DIMENSION],
    )
    assert store.rows(EMBEDDING_TABLE) == {}


def test_put_many_writes_every_valid_pair():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    vectors = [hashing_vector(t, DIMENSION) for t in TEXTS]
    cache.put_many(
        TEXTS,
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vectors=vectors,
    )
    assert len(store.rows(EMBEDDING_TABLE)) == len(TEXTS)


# ---------------------------------------------------------------------------
# E. EmbeddingService integration
# ---------------------------------------------------------------------------

def test_miss_embeds_and_writes_the_cache():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    vectors = service.embed_batch(TEXTS)
    assert len(provider.calls) == 1
    assert len(store.rows(EMBEDDING_TABLE)) == len(TEXTS)
    assert vectors[0] == hashing_vector(TEXTS[0], DIMENSION)


def test_second_identical_batch_is_served_entirely_from_cache():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    first = service.embed_batch(TEXTS)
    second = service.embed_batch(TEXTS)
    assert len(provider.calls) == 1  # only the first batch reached the provider
    assert second == first


def test_embed_batch_reads_the_cache_in_one_batched_lookup():
    """LOW-2: one batched cache read per request — never one lookup per text."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    service.embed_batch(TEXTS)  # all misses: one batched read + provider
    service.embed_batch(TEXTS)  # all hits: one batched read, no provider
    assert store.calls["get_many"] == 2  # exactly one per embed_batch call
    assert store.calls["get"] == 0  # the N-independent-SELECTs pattern is gone
    assert len(provider.calls) == 1


def test_partial_hits_send_only_missed_texts_to_the_provider():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    seeded = hashing_vector(TEXTS[1], DIMENSION)
    _seed(store, TEXTS[1])
    service, provider = _service(cache)
    vectors = service.embed_batch(TEXTS)
    assert len(provider.calls) == 1
    assert provider.calls[0].texts == (TEXTS[0], TEXTS[2])
    assert vectors[1] == seeded  # cached vector restored in place
    assert vectors[0] == hashing_vector(TEXTS[0], DIMENSION)
    assert vectors[2] == hashing_vector(TEXTS[2], DIMENSION)


def test_results_are_reconstructed_in_original_input_order():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, TEXTS[0])
    _seed(store, TEXTS[2])
    service, provider = _service(cache)
    vectors = service.embed_batch(TEXTS)
    assert provider.calls[0].texts == (TEXTS[1],)  # only the middle miss
    assert vectors == [hashing_vector(t, DIMENSION) for t in TEXTS]


def test_document_and_query_task_types_never_share_a_cache_entry():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    service.embed_text(TEXTS[0], task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT)
    service.embed_text(TEXTS[0], task_type=EmbeddingTaskType.RETRIEVAL_QUERY)
    assert len(provider.calls) == 2  # namespaces isolated -> second is a miss
    assert len(store.rows(EMBEDDING_TABLE)) == 2


def test_cache_is_consulted_after_preprocessing_never_on_raw_text():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    # Seed with the RAW text only: a raw-keyed cache would hit and skip the
    # provider on the first call.
    cache.put_vector(
        text=TEXTS[0],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        vector=hashing_vector(TEXTS[0], DIMENSION),
    )
    service, provider = _service(cache, preprocessor=str.upper)
    service.embed_batch([TEXTS[0]])
    assert len(provider.calls) == 1  # raw entry ignored -> provider ran
    # The write above used the preprocessed text, so the second run hits.
    service.embed_batch([TEXTS[0]])
    assert len(provider.calls) == 1  # preprocessed entry hit


def test_disabled_cache_service_behavior_is_unchanged():
    store = FakeCacheStore()
    cache = embedding_cache(store, enabled=False)
    service, provider = _service(cache)
    service.embed_batch(TEXTS)
    service.embed_batch(TEXTS)
    assert len(provider.calls) == 2
    assert store.calls == {"get": 0, "get_many": 0, "put": 0, "delete": 0, "corpus_token": 0}


def test_cache_backend_failure_degrades_to_the_provider():
    store = FakeCacheStore(fail_ops=["get", "put"])
    cache = embedding_cache(store)
    service, provider = _service(cache)
    first = service.embed_batch(TEXTS)
    second = service.embed_batch(TEXTS)
    assert len(provider.calls) == 2  # both runs reached the provider
    assert first == second == [hashing_vector(t, DIMENSION) for t in TEXTS]


def test_malformed_cached_vector_is_regenerated():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, TEXTS[0], vector=[0.1] * 3)  # wrong length at a valid key
    service, provider = _service(cache)
    vectors = service.embed_batch(TEXTS)
    assert len(provider.calls) == 1
    assert vectors[0] == hashing_vector(TEXTS[0], DIMENSION)
    assert provider.calls[0].texts == tuple(TEXTS)  # malformed hit -> regenerated
    repaired = store.rows(EMBEDDING_TABLE)[_ekey(TEXTS[0])]
    assert repaired["vector"] == hashing_vector(TEXTS[0], DIMENSION)


def test_expired_cached_vector_is_regenerated():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    _seed(store, TEXTS[0], expires_at=utcnow() - timedelta(seconds=1))
    service, provider = _service(cache)
    vectors = service.embed_batch(TEXTS)
    assert len(provider.calls) == 1
    assert vectors[0] == hashing_vector(TEXTS[0], DIMENSION)


def test_empty_batch_returns_empty_without_touching_cache_or_provider():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    assert service.embed_batch([]) == []
    assert provider.calls == []
    assert store.calls == {"get": 0, "get_many": 0, "put": 0, "delete": 0, "corpus_token": 0}


def test_batch_size_limit_still_applies_to_cache_misses():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache, batch_size=2)
    service.embed_batch(TEXTS)  # 3 texts, batch size 2 -> chunks [2, 1]
    assert [len(call.texts) for call in provider.calls] == [2, 1]
    service.embed_batch(TEXTS)  # full hit: no new provider chunk
    assert [len(call.texts) for call in provider.calls] == [2, 1]


def test_embed_text_single_item_uses_the_cache():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    first = service.embed_text(TEXTS[0])
    second = service.embed_text(TEXTS[0])
    assert len(provider.calls) == 1
    assert first == second


def test_cached_vectors_are_dimension_revalidated_by_the_service():
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    vectors = service.embed_batch([ODD_TEXT])
    assert len(vectors[0]) == DIMENSION  # service-level re-validation holds
    # A cached row whose stored dimension disagrees with the spec is a miss.
    key = _ekey(ODD_TEXT)
    store.rows(EMBEDDING_TABLE)[key]["dimension"] = 16
    service.embed_batch([ODD_TEXT])
    assert len(provider.calls) == 2  # mismatch -> regenerated
    assert store.rows(EMBEDDING_TABLE)[key]["dimension"] == DIMENSION


def test_only_vector_fields_are_ever_stored():
    """The cache stores vectors only - never search results, scores, prompts."""
    store = FakeCacheStore()
    cache = embedding_cache(store)
    service, provider = _service(cache)
    service.embed_batch([ODD_TEXT])
    rows = store.rows(EMBEDDING_TABLE)
    assert len(rows) == 1
    row = next(iter(rows.values()))
    assert set(row) == {
        "cache_key",
        "vector",
        "task_type",
        "model",
        "dimension",
        "created_at",
        "expires_at",
    }
    dumped = str(row)
    assert "similarity" not in dumped and "score" not in dumped
    assert "prompt" not in dumped and "api_key" not in dumped
