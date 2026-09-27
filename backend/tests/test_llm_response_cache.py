"""V2-P9 tests: LLM response cache (keys, validation, RAG safety, consumers).

Fully offline: in-memory ``FakeCacheStore``, scripted ``FakeProvider`` and the
fake google-genai SDK (no network, no database, no real provider).

Coverage map (spec test plan A-V, LLM parts):

- cache key semantics (determinism, sensitivity, versioning, provider-neutral),
- validated read path (miss / hit / expiry / malformed / envelope checks),
- RAG safety (corpus-token fail-closed, write skip, digest metadata),
- TTL + provenance write path,
- analyzer integration (hit bypass, no failures cached, fallback provenance),
- summary service integration,
- public API contract (schemas and response envelope unchanged),
- logging/never-stored security rules,
- disabled-by-default hermetic configuration.
"""

import inspect
import json
import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from models.ecommerce import AISummaryResponse
from models.review import ReviewAnalysis
from services.ai.errors import AIErrorType, AIProviderError
from services.ai.gateway import AIGateway
from services.ai.registry import (
    GEMINI_PROVIDER,
    TASK_DATASET_SUMMARY,
    TASK_REVIEW_ANALYSIS,
    model_registry,
)
from services.ai_analyzer import (
    ANALYSIS_TEMPERATURE,
    SYSTEM_INSTRUCTION,
    AIAnalyzerService,
    analyzer_service,
)
from services.cache.config import (
    DEFAULT_AI_CACHE_TTL_RAG_SECONDS,
    DEFAULT_AI_CACHE_TTL_SECONDS,
    DEFAULT_EMBEDDING_CACHE_TTL_SECONDS,
    CacheConfig,
)
from services.cache.keys import (
    CACHE_SCHEMA_VERSION,
    analysis_cache_key,
    canonical_key,
    sha256_hex,
    summary_cache_key,
)
from services.cache.llm_cache import ANALYSIS_KIND, SUMMARY_KIND, LLMCache
from services.cache.store import RESPONSE_TABLE
from services.gemini_summary_service import (
    SUMMARY_SYSTEM_INSTRUCTION,
    GeminiSummaryService,
)
from services.rag.config import RAGConfig
from services.rag.context_builder import build_rag_context, render_context_block
from services.rag.retrieval import RagRetrievalService
from tests.cache_fakes import (
    DEFAULT_CORPUS_TOKEN,
    REVIEW,
    SUMMARY_JSON,
    VALID_ANALYSIS_JSON,
    FakeCacheStore,
    analysis_row,
    analyzer_with_cache,
    llm_cache,
    make_analysis,
    make_summary,
    summary_row,
    utcnow,
)
from tests.test_ai_foundation import FakeProvider
from tests.test_model_configuration import _FakeResponse, _install_fake_sdk
from tests.test_rag_analysis_integration import _result, _ScriptedSearch

RAG_REVIEW = "The battery lasts all day."
CONTEXT_TEXT = "The battery lasts all day and never dies."
ODD_REVIEW = "Quirky quantum zebras gallop"


def _boom(*args, **kwargs):
    raise AssertionError("cache hit must bypass this pipeline stage")


def _rag(**overrides) -> RAGConfig:
    return RAGConfig(**overrides)


def _key(cache, *, review_text=REVIEW, rag_config=None, task=TASK_REVIEW_ANALYSIS,
         system=SYSTEM_INSTRUCTION, temperature=ANALYSIS_TEMPERATURE):
    return cache.analysis_key(
        review_text=review_text,
        task=task,
        system_instruction=system,
        temperature=temperature,
        rag_config=rag_config if rag_config is not None else _rag(),
    )


def _get_analysis(cache, *, review_text=REVIEW, rag_config=None):
    return cache.get_analysis(
        review_text=review_text,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=rag_config if rag_config is not None else _rag(),
    )


def _only_row(store):
    rows = store.rows(RESPONSE_TABLE)
    assert len(rows) == 1
    return next(iter(rows.values()))


# ---------------------------------------------------------------------------
# A. Cache key semantics (pure)
# ---------------------------------------------------------------------------

def test_analysis_key_is_deterministic_for_identical_inputs():
    a = llm_cache(FakeCacheStore())
    b = llm_cache(FakeCacheStore())
    assert _key(a) == _key(b)
    assert len(_key(a)) == 64 and all(c in "0123456789abcdef" for c in _key(a))


def test_analysis_key_never_contains_review_text():
    key = _key(llm_cache(FakeCacheStore()), review_text=ODD_REVIEW)
    assert "quantum" not in key.lower()
    assert "zebras" not in key.lower()


def test_analysis_key_differs_for_different_review_text():
    cache = llm_cache(FakeCacheStore())
    assert _key(cache, review_text=REVIEW) != _key(cache, review_text=ODD_REVIEW)


def test_analysis_key_differs_for_different_system_instruction():
    cache = llm_cache(FakeCacheStore())
    base = _key(cache)
    changed = _key(cache, system=SYSTEM_INSTRUCTION + "\nExtra rule.")
    assert base != changed


def test_analysis_key_differs_for_different_temperature():
    cache = llm_cache(FakeCacheStore())
    assert _key(cache) != _key(cache, temperature=0.7)


def test_analysis_key_differs_for_different_task():
    cache = llm_cache(FakeCacheStore())
    assert _key(cache) != _key(cache, task="other_task")


def test_analysis_key_differs_when_prompt_version_bumps(monkeypatch):
    cache = llm_cache(FakeCacheStore())
    before = _key(cache)
    monkeypatch.setattr("services.cache.keys.PROMPT_VERSION", "2")
    assert _key(cache) != before


def test_analysis_key_differs_when_cache_schema_version_bumps(monkeypatch):
    cache = llm_cache(FakeCacheStore())
    before = _key(cache)
    monkeypatch.setattr("services.cache.keys.CACHE_SCHEMA_VERSION", "2")
    assert _key(cache) != before


def test_analysis_key_differs_when_rag_enabled_toggles():
    cache = llm_cache(FakeCacheStore())
    off = _key(cache, rag_config=_rag(enabled=False))
    on = _key(cache, rag_config=_rag(enabled=True))
    assert off != on


def test_analysis_key_differs_for_different_rag_config():
    cache = llm_cache(FakeCacheStore())
    a = _key(cache, rag_config=_rag(enabled=True, top_k=5))
    b = _key(cache, rag_config=_rag(enabled=True, top_k=7))
    assert a != b


def test_analysis_key_signature_has_no_provider_or_model_inputs():
    params = inspect.signature(LLMCache.analysis_key).parameters
    assert "provider" not in params and "model" not in params
    params = inspect.signature(LLMCache.summary_key).parameters
    assert "provider" not in params and "model" not in params


def test_canonical_key_is_order_insensitive():
    assert canonical_key({"a": 1, "b": 2}) == canonical_key({"b": 2, "a": 1})


def test_summary_key_is_deterministic_and_prompt_sensitive():
    cache = llm_cache(FakeCacheStore())
    kwargs = dict(
        prompt="Product: X",
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=0.2,
    )
    first = cache.summary_key(**kwargs)
    assert first == cache.summary_key(**dict(kwargs))
    assert first != cache.summary_key(**{**kwargs, "prompt": "Product: Y"})


def test_summary_key_differs_for_different_system_instruction():
    cache = llm_cache(FakeCacheStore())
    kwargs = dict(
        prompt="p",
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=0.2,
    )
    assert cache.summary_key(**kwargs) != cache.summary_key(
        **{**kwargs, "system_instruction": "Different."}
    )


def test_summary_key_matches_pure_summary_cache_key_helper():
    cache = llm_cache(FakeCacheStore())
    assert cache.summary_key(
        prompt="p",
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=0.2,
    ) == summary_cache_key(
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        response_schema=AISummaryResponse,
        temperature=0.2,
        prompt="p",
    )


def test_analysis_key_matches_pure_analysis_cache_key_helper():
    cache = llm_cache(FakeCacheStore())
    assert _key(cache) == analysis_cache_key(
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        response_schema=ReviewAnalysis,
        temperature=ANALYSIS_TEMPERATURE,
        normalized_review_text=REVIEW,
        rag_enabled=False,
        rag_config=_rag(),
    )


# ---------------------------------------------------------------------------
# B. Validated read path
# ---------------------------------------------------------------------------

def test_hit_returns_validated_analysis_instance():
    store = FakeCacheStore()
    cache = llm_cache(store)
    store.seed(RESPONSE_TABLE, _key(cache), analysis_row(make_analysis()))
    result = _get_analysis(cache)
    assert isinstance(result, ReviewAnalysis)
    assert result.rating == 5


def test_miss_when_no_row_exists():
    cache = llm_cache(FakeCacheStore())
    assert _get_analysis(cache) is None


def test_expired_entry_is_a_miss_and_is_deleted():
    store = FakeCacheStore()
    cache = llm_cache(store)
    key = _key(cache)
    store.seed(
        RESPONSE_TABLE,
        key,
        analysis_row(make_analysis(), expires_at=utcnow() - timedelta(seconds=1)),
    )
    assert _get_analysis(cache) is None
    assert store.rows(RESPONSE_TABLE) == {}


def test_fresh_entry_hits():
    store = FakeCacheStore()
    cache = llm_cache(store)
    store.seed(RESPONSE_TABLE, _key(cache), analysis_row(make_analysis()))
    assert _get_analysis(cache) is not None


def test_malformed_result_payload_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = llm_cache(store)
    key = _key(cache)
    store.seed(
        RESPONSE_TABLE,
        key,
        analysis_row(
            make_analysis(),
            payload={
                "kind": ANALYSIS_KIND,
                "cache_schema": CACHE_SCHEMA_VERSION,
                "result": {"sentiment": "not-a-sentiment"},
            },
        ),
    )
    assert _get_analysis(cache) is None
    assert store.rows(RESPONSE_TABLE) == {}


def test_non_object_payload_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = llm_cache(store)
    key = _key(cache)
    store.seed(RESPONSE_TABLE, key, analysis_row(make_analysis(), payload="garbage"))
    assert _get_analysis(cache) is None
    assert store.rows(RESPONSE_TABLE) == {}


def test_kind_mismatch_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = llm_cache(store)
    key = _key(cache)
    store.seed(
        RESPONSE_TABLE,
        key,
        analysis_row(
            make_analysis(),
            payload={
                "kind": SUMMARY_KIND,
                "cache_schema": CACHE_SCHEMA_VERSION,
                "result": make_analysis().model_dump(mode="json"),
            },
        ),
    )
    assert _get_analysis(cache) is None
    assert store.rows(RESPONSE_TABLE) == {}


def test_cache_schema_mismatch_is_deleted_and_missed():
    store = FakeCacheStore()
    cache = llm_cache(store)
    key = _key(cache)
    store.seed(
        RESPONSE_TABLE,
        key,
        analysis_row(make_analysis(), payload={
            "kind": ANALYSIS_KIND,
            "cache_schema": "999",
            "result": make_analysis().model_dump(mode="json"),
        }),
    )
    assert _get_analysis(cache) is None
    assert store.rows(RESPONSE_TABLE) == {}


def test_disabled_cache_never_touches_the_store():
    store = FakeCacheStore()
    cache = llm_cache(store, enabled=False)
    assert _get_analysis(cache) is None
    cache.put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(),
        analysis=make_analysis(),
    )
    assert store.calls == {"get": 0, "get_many": 0, "put": 0, "delete": 0, "corpus_token": 0}
    assert store.rows(RESPONSE_TABLE) == {}


def test_store_read_failure_is_a_fail_open_miss():
    store = FakeCacheStore(fail_ops=["get"])
    assert _get_analysis(llm_cache(store)) is None


def test_default_env_configuration_is_disabled():
    config = CacheConfig.from_env()  # conftest forces both flags off
    assert config.llm_enabled is False
    assert config.embedding_enabled is False
    assert config.llm_ttl_seconds == DEFAULT_AI_CACHE_TTL_SECONDS
    assert config.llm_rag_ttl_seconds == DEFAULT_AI_CACHE_TTL_RAG_SECONDS
    assert config.embedding_ttl_seconds == DEFAULT_EMBEDDING_CACHE_TTL_SECONDS


def test_default_llm_cache_never_builds_a_store_when_disabled():
    cache = LLMCache()  # no store, env-disabled (conftest)
    assert _get_analysis(cache) is None
    assert cache._store is None  # a disabled cache never opens a connection


def test_summary_hit_returns_validated_summary_instance():
    store = FakeCacheStore()
    cache = llm_cache(store)
    store.seed(
        RESPONSE_TABLE,
        cache.summary_key(
            prompt="p",
            task=TASK_DATASET_SUMMARY,
            system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
            temperature=0.2,
        ),
        summary_row(make_summary()),
    )
    result = cache.get_summary(
        prompt="p",
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=0.2,
    )
    assert isinstance(result, AISummaryResponse)
    assert result.source_label == "Summary generated from dataset reviews"


def test_summary_miss_when_prompt_differs():
    store = FakeCacheStore()
    cache = llm_cache(store)
    kwargs = dict(
        prompt="p",
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=0.2,
    )
    store.seed(RESPONSE_TABLE, cache.summary_key(**kwargs), summary_row(make_summary()))
    assert cache.get_summary(**kwargs) is not None
    assert cache.get_summary(**{**kwargs, "prompt": "other"}) is None


# ---------------------------------------------------------------------------
# C. RAG safety (corpus-token fail-closed)
# ---------------------------------------------------------------------------

def _seed_rag(store, cache, *, token=DEFAULT_CORPUS_TOKEN, digest=None, review_text=REVIEW):
    return store.seed(
        RESPONSE_TABLE,
        _key(cache, review_text=review_text, rag_config=_rag(enabled=True)),
        analysis_row(
            make_analysis(),
            corpus_token=token,
            rag_context_digest=digest,
        ),
    )


def test_rag_hit_requires_matching_live_corpus_token():
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store)
    _seed_rag(store, cache, token=DEFAULT_CORPUS_TOKEN)
    result = _get_analysis(cache, rag_config=_rag(enabled=True))
    assert result is not None


def test_rag_token_mismatch_is_a_miss_but_keeps_the_row():
    store = FakeCacheStore(corpus_token_value="v1|9|2026-09-02T00:00:00+00:00")
    cache = llm_cache(store)
    _seed_rag(store, cache, token=DEFAULT_CORPUS_TOKEN)
    assert _get_analysis(cache, rag_config=_rag(enabled=True)) is None
    assert store.rows(RESPONSE_TABLE)  # row retained: valid for unchanged corpus


def test_rag_token_lookup_failure_is_a_miss_but_keeps_the_row():
    store = FakeCacheStore(fail_ops=["corpus_token"])
    cache = llm_cache(store)
    _seed_rag(store, cache, token=DEFAULT_CORPUS_TOKEN)
    assert _get_analysis(cache, rag_config=_rag(enabled=True)) is None
    assert store.rows(RESPONSE_TABLE)


def test_rag_row_without_stored_token_is_a_miss():
    store = FakeCacheStore()
    cache = llm_cache(store)
    _seed_rag(store, cache, token=None)
    assert _get_analysis(cache, rag_config=_rag(enabled=True)) is None


def test_non_rag_read_ignores_corpus_token():
    store = FakeCacheStore()
    cache = llm_cache(store)
    store.seed(
        RESPONSE_TABLE, _key(cache, rag_config=_rag(enabled=False)),
        analysis_row(make_analysis(), corpus_token=None),
    )
    assert _get_analysis(cache, rag_config=_rag(enabled=False)) is not None


def test_rag_write_is_skipped_when_live_token_unavailable():
    store = FakeCacheStore(corpus_token_value=None)
    cache = llm_cache(store)
    cache.put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(enabled=True),
        analysis=make_analysis(),
    )
    assert store.rows(RESPONSE_TABLE) == {}
    assert store.calls["put"] == 0


def test_rag_write_stores_token_and_digest():
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store)
    digest = "a" * 64
    cache.put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(enabled=True),
        analysis=make_analysis(),
        rag_context_digest=digest,
    )
    row = _only_row(store)
    assert row["corpus_token"] == DEFAULT_CORPUS_TOKEN
    assert row["rag_context_digest"] == digest


def test_non_rag_write_stores_no_token_and_no_digest():
    store = FakeCacheStore()
    cache = llm_cache(store)
    cache.put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(enabled=False),
        analysis=make_analysis(),
        rag_context_digest="should-be-dropped",
    )
    row = _only_row(store)
    assert row["corpus_token"] is None
    assert row["rag_context_digest"] is None


# ---------------------------------------------------------------------------
# D. TTL + provenance write path
# ---------------------------------------------------------------------------

def test_put_analysis_uses_default_non_rag_ttl():
    store = FakeCacheStore()
    llm_cache(store).put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(),
        analysis=make_analysis(),
    )
    row = _only_row(store)
    assert row["expires_at"] - row["created_at"] == timedelta(
        seconds=DEFAULT_AI_CACHE_TTL_SECONDS
    )


def test_put_analysis_uses_short_rag_ttl():
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store, ttl_seconds=604800, rag_ttl_seconds=3600)
    cache.put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(enabled=True),
        analysis=make_analysis(),
    )
    row = _only_row(store)
    assert row["expires_at"] - row["created_at"] == timedelta(seconds=3600)


def test_put_analysis_stores_provenance_internally_not_in_payload():
    store = FakeCacheStore()
    cache = llm_cache(store)
    cache.put_analysis(
        review_text=ODD_REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(),
        analysis=make_analysis(),
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        fallback=True,
    )
    row = _only_row(store)
    assert row["provenance"] == {
        "task": TASK_REVIEW_ANALYSIS,
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback": True,
    }
    payload = json.dumps(row["payload"])
    assert "llama" not in payload and "groq" not in payload
    assert "quantum" not in payload  # review text is never stored
    assert "quantum" not in json.dumps(row, default=str)


def test_put_summary_stores_row_with_provenance():
    store = FakeCacheStore()
    cache = llm_cache(store)
    cache.put_summary(
        prompt="p",
        task=TASK_DATASET_SUMMARY,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=0.2,
        summary=make_summary(),
        provider="gemini",
        model_name="gemini-3.8-flash",
        fallback=False,
    )
    row = _only_row(store)
    assert row["payload"]["kind"] == SUMMARY_KIND
    assert row["provenance"]["provider"] == "gemini"


def test_write_failure_is_silent():
    store = FakeCacheStore(fail_ops=["put"])
    llm_cache(store).put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(),
        analysis=make_analysis(),
    )  # must not raise


def test_put_analysis_without_result_is_a_noop():
    store = FakeCacheStore()
    llm_cache(store).put_analysis(
        review_text=REVIEW,
        task=TASK_REVIEW_ANALYSIS,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=ANALYSIS_TEMPERATURE,
        rag_config=_rag(),
        analysis=None,
    )
    assert store.calls["put"] == 0


# ---------------------------------------------------------------------------
# E. Analyzer integration (miss -> pipeline -> write; hit -> bypass)
# ---------------------------------------------------------------------------

def _analyzer(cache, providers, *, rag_config=None, rag_service=None):
    return analyzer_with_cache(
        cache, providers, rag_config=rag_config, rag_service=rag_service
    )


def test_analyzer_miss_runs_pipeline_then_writes_cache():
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    result = analyzer._call_google_genai(REVIEW)
    assert isinstance(result, ReviewAnalysis)
    assert len(provider.requests) == 1
    row = _only_row(store)
    assert row["payload"]["kind"] == ANALYSIS_KIND
    assert row["provenance"]["provider"] == "gemini"
    assert row["provenance"]["fallback"] is False
    assert row["provenance"]["model"] == provider.requests[0].model


def test_analyzer_hit_bypasses_routing_retry_and_provider(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    first = analyzer._call_google_genai(REVIEW)
    assert len(provider.requests) == 1

    monkeypatch.setattr("services.ai_analyzer.build_target_chain", _boom)
    monkeypatch.setattr("services.ai_analyzer.resolve_retry_policy", _boom)
    monkeypatch.setattr("services.ai_analyzer.resolve_request_timeout", _boom)

    second = analyzer._call_google_genai(REVIEW)
    assert second.model_dump() == first.model_dump()
    assert len(provider.requests) == 1  # no provider call on the hit


def test_cached_result_is_provider_neutral():
    store = FakeCacheStore()
    cache = llm_cache(store)
    gemini = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    first = _analyzer(cache, {"gemini": gemini}, rag_config=_rag())
    written = first._call_google_genai(REVIEW)

    groq = FakeProvider([VALID_ANALYSIS_JSON], name="groq")
    second = _analyzer(cache, {"groq": groq}, rag_config=_rag())
    served = second._call_google_genai(REVIEW)
    assert groq.requests == []  # groq-only analyzer still gets the hit
    assert served.model_dump() == written.model_dump()


def test_analyzer_failures_are_never_cached():
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([RuntimeError("service overloaded")], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    with pytest.raises(RuntimeError):
        analyzer._call_google_genai(REVIEW)
    assert provider.requests
    assert store.rows(RESPONSE_TABLE) == {}


def test_analyzer_disabled_cache_never_reads_or_writes():
    store = FakeCacheStore()
    cache = llm_cache(store, enabled=False)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    result = analyzer._call_google_genai(REVIEW)
    assert result is not None
    assert len(provider.requests) == 1
    assert store.calls == {"get": 0, "get_many": 0, "put": 0, "delete": 0, "corpus_token": 0}


def test_analyzer_cache_backend_failure_still_returns_the_analysis():
    store = FakeCacheStore(fail_ops=["get", "put", "corpus_token"])
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    result = analyzer._call_google_genai(REVIEW)
    assert isinstance(result, ReviewAnalysis)
    assert len(provider.requests) == 1


def test_fallback_success_is_cached_with_fallback_provenance():
    store = FakeCacheStore()
    cache = llm_cache(store)
    gemini = FakeProvider(
        [AIProviderError("401 unauthorized", AIErrorType.AUTHENTICATION)],
        name="gemini",
    )
    groq = FakeProvider([VALID_ANALYSIS_JSON], name="groq")
    analyzer = _analyzer(cache, {"gemini": gemini, "groq": groq}, rag_config=_rag())
    result = analyzer._call_google_genai(REVIEW)
    assert isinstance(result, ReviewAnalysis)
    assert len(gemini.requests) == 1
    assert len(groq.requests) == 1
    row = _only_row(store)
    assert row["provenance"]["provider"] == "groq"
    assert row["provenance"]["fallback"] is True
    assert row["provenance"]["model"] == groq.requests[0].model


def test_second_identical_request_is_served_from_cache(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    first = analyzer.analyze_review(REVIEW)
    monkeypatch.setattr("services.ai_analyzer.build_target_chain", _boom)
    second = analyzer.analyze_review(REVIEW)
    assert second.model_dump() == first.model_dump()
    assert len(provider.requests) == 1


# ---------------------------------------------------------------------------
# F. Analyzer + RAG integration
# ---------------------------------------------------------------------------

def _rag_analyzer(cache, store, *, provider, rag_config, rag_service):
    return _analyzer(
        cache,
        {"gemini": provider},
        rag_config=rag_config,
        rag_service=rag_service,
    )


def test_rag_miss_runs_retrieval_and_caches_token_and_context_digest():
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_TEXT, 0.9),))
    rag_config = _rag(enabled=True, top_k=5, similarity_threshold=0.0)
    rag_service = RagRetrievalService(rag_config, search_service=search)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _rag_analyzer(
        cache, store, provider=provider, rag_config=rag_config, rag_service=rag_service
    )
    result = analyzer._call_google_genai(RAG_REVIEW)
    assert isinstance(result, ReviewAnalysis)
    assert search.calls  # retrieval ran on the miss
    row = _only_row(store)
    assert row["corpus_token"] == DEFAULT_CORPUS_TOKEN
    expected = sha256_hex(
        render_context_block(build_rag_context(search.results, rag_config))
    )
    assert row["rag_context_digest"] == expected


def test_rag_hit_skips_both_retrieval_and_provider(monkeypatch):
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_TEXT, 0.9),))
    rag_config = _rag(enabled=True, top_k=5, similarity_threshold=0.0)
    rag_service = RagRetrievalService(rag_config, search_service=search)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _rag_analyzer(
        cache, store, provider=provider, rag_config=rag_config, rag_service=rag_service
    )
    analyzer._call_google_genai(RAG_REVIEW)
    assert len(search.calls) == 1
    assert len(provider.requests) == 1

    monkeypatch.setattr("services.ai_analyzer.build_target_chain", _boom)
    monkeypatch.setattr("services.ai_analyzer.resolve_retry_policy", _boom)
    analyzer._call_google_genai(RAG_REVIEW)
    assert len(search.calls) == 1  # no retrieval on the hit
    assert len(provider.requests) == 1  # no provider on the hit


def test_rag_corpus_change_invalidates_the_hit():
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_TEXT, 0.9),))
    rag_config = _rag(enabled=True, top_k=5, similarity_threshold=0.0)
    rag_service = RagRetrievalService(rag_config, search_service=search)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _rag_analyzer(
        cache, store, provider=provider, rag_config=rag_config, rag_service=rag_service
    )
    analyzer._call_google_genai(RAG_REVIEW)
    assert len(search.calls) == 1

    # Corpus re-indexed -> live token changed -> stored RAG row must not serve.
    store.corpus_token_value = "v1|9|2026-09-02T00:00:00+00:00"
    analyzer._call_google_genai(RAG_REVIEW)
    assert len(search.calls) == 2  # miss -> normal pipeline re-ran
    assert len(provider.requests) == 2


def test_grounded_cached_result_is_served_only_through_revalidation(monkeypatch):
    """LOW-4 invariant: grounding runs BEFORE the cache write and the read
    path ALWAYS revalidates through ``ReviewAnalysis``.

    Proves the documented design: on a hit retrieval/provider are skipped,
    ``rag_context_digest`` stays diagnostic metadata (the corpus token is the
    authoritative freshness guard), and an invalid cached payload is rejected
    at the validation boundary — no ungrounded/invalid payload can bypass it.
    """
    store = FakeCacheStore(corpus_token_value=DEFAULT_CORPUS_TOKEN)
    cache = llm_cache(store)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_TEXT, 0.9),))
    rag_config = _rag(enabled=True, top_k=5, similarity_threshold=0.0)
    rag_service = RagRetrievalService(rag_config, search_service=search)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _rag_analyzer(
        cache, store, provider=provider, rag_config=rag_config, rag_service=rag_service
    )

    # Miss: pipeline runs, grounding is applied, THEN the row is written.
    first = analyzer._call_google_genai(RAG_REVIEW)
    assert isinstance(first, ReviewAnalysis)
    assert first.aspects and first.aspects[0].evidence  # grounded evidence kept
    assert _only_row(store)["corpus_token"] == DEFAULT_CORPUS_TOKEN

    # Hit: Pydantic revalidation only — retrieval and provider are skipped.
    monkeypatch.setattr("services.ai_analyzer.build_target_chain", _boom)
    monkeypatch.setattr("services.ai_analyzer.resolve_retry_policy", _boom)
    second = analyzer._call_google_genai(RAG_REVIEW)
    assert isinstance(second, ReviewAnalysis)
    assert second.model_dump() == first.model_dump()
    assert len(search.calls) == 1
    assert len(provider.requests) == 1

    # rag_context_digest is diagnostic metadata: without it a valid row still
    # serves (freshness rests on the corpus token, which still matches).
    key = _key(cache, review_text=RAG_REVIEW, rag_config=rag_config)
    store.rows(RESPONSE_TABLE)[key]["rag_context_digest"] = None
    assert isinstance(analyzer._call_google_genai(RAG_REVIEW), ReviewAnalysis)
    assert len(search.calls) == 1 and len(provider.requests) == 1

    # An invalid payload can never bypass the validation boundary: it is
    # rejected (deleted, treated as a miss) and raw JSON never escapes.
    store.rows(RESPONSE_TABLE)[key]["payload"]["result"]["sentiment"] = "unhinged"
    assert (
        cache.get_analysis(
            review_text=RAG_REVIEW,
            task=TASK_REVIEW_ANALYSIS,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=ANALYSIS_TEMPERATURE,
            rag_config=rag_config,
        )
        is None
    )
    assert key not in store.rows(RESPONSE_TABLE)

    # A re-seeded valid grounded row is served again — still only via
    # revalidation (the boom patches above would raise otherwise).
    store.seed(
        RESPONSE_TABLE,
        key,
        analysis_row(
            first,
            rag_context_digest="diagnostic",
            corpus_token=DEFAULT_CORPUS_TOKEN,
        ),
    )
    again = analyzer._call_google_genai(RAG_REVIEW)
    assert isinstance(again, ReviewAnalysis)
    assert again.model_dump() == first.model_dump()
    assert len(search.calls) == 1 and len(provider.requests) == 1


# ---------------------------------------------------------------------------
# G. Summary service integration
# ---------------------------------------------------------------------------

SUMMARY_PROMPT = "Product: Widget\nCategory: Tools\n\nReviews:\n- Great."


def _summary_service(monkeypatch, cache, providers):
    gateway = AIGateway(
        providers=providers, registry=model_registry, default_provider=GEMINI_PROVIDER
    )
    monkeypatch.setattr(
        "services.gemini_summary_service.analyzer_service._gateway", gateway
    )
    return GeminiSummaryService(llm_cache=cache)


def test_summary_miss_runs_pipeline_then_writes_cache(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([SUMMARY_JSON], name="gemini")
    service = _summary_service(monkeypatch, cache, {"gemini": provider})
    result = service._generate_summary(SUMMARY_PROMPT)
    assert isinstance(result, AISummaryResponse)
    assert len(provider.requests) == 1
    row = _only_row(store)
    assert row["payload"]["kind"] == SUMMARY_KIND
    assert row["provenance"]["task"] == TASK_DATASET_SUMMARY


def test_summary_hit_bypasses_chain_build_retry_and_provider(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([SUMMARY_JSON], name="gemini")
    service = _summary_service(monkeypatch, cache, {"gemini": provider})
    first = service._generate_summary(SUMMARY_PROMPT)
    assert len(provider.requests) == 1

    monkeypatch.setattr("services.gemini_summary_service.build_target_chain", _boom)
    monkeypatch.setattr("services.gemini_summary_service.resolve_retry_policy", _boom)
    second = service._generate_summary(SUMMARY_PROMPT)
    assert second.model_dump() == first.model_dump()
    assert len(provider.requests) == 1


def test_summary_failure_is_never_cached(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([RuntimeError("service overloaded")], name="gemini")
    service = _summary_service(monkeypatch, cache, {"gemini": provider})
    with pytest.raises(RuntimeError):
        service._generate_summary(SUMMARY_PROMPT)
    assert provider.requests
    assert store.rows(RESPONSE_TABLE) == {}


def test_summary_different_prompt_is_a_miss(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([SUMMARY_JSON, SUMMARY_JSON], name="gemini")
    service = _summary_service(monkeypatch, cache, {"gemini": provider})
    service._generate_summary(SUMMARY_PROMPT)
    service._generate_summary(SUMMARY_PROMPT + " extra reviews")
    assert len(provider.requests) == 2
    assert len(store.rows(RESPONSE_TABLE)) == 2


def test_summary_cache_result_is_provider_neutral(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store)
    gemini = FakeProvider([SUMMARY_JSON], name="gemini")
    first = _summary_service(monkeypatch, cache, {"gemini": gemini})
    written = first._generate_summary(SUMMARY_PROMPT)

    groq = FakeProvider([SUMMARY_JSON], name="groq")
    second = _summary_service(monkeypatch, cache, {"groq": groq})
    served = second._generate_summary(SUMMARY_PROMPT)
    assert groq.requests == []
    assert served.model_dump() == written.model_dump()


def test_summary_disabled_cache_never_touches_the_store(monkeypatch):
    store = FakeCacheStore()
    cache = llm_cache(store, enabled=False)
    provider = FakeProvider([SUMMARY_JSON], name="gemini")
    service = _summary_service(monkeypatch, cache, {"gemini": provider})
    service._generate_summary(SUMMARY_PROMPT)
    assert len(provider.requests) == 1
    assert store.calls == {"get": 0, "get_many": 0, "put": 0, "delete": 0, "corpus_token": 0}


# ---------------------------------------------------------------------------
# H. Public API contract (unchanged schemas and envelopes)
# ---------------------------------------------------------------------------

def test_review_analysis_schema_has_exactly_the_original_fields():
    props = ReviewAnalysis.model_json_schema()["properties"]
    assert set(props) == {
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    }


def test_summary_response_schema_has_exactly_the_original_fields():
    props = AISummaryResponse.model_json_schema()["properties"]
    assert set(props) == {
        "summary",
        "common_pros",
        "common_cons",
        "key_themes",
        "source_label",
    }


def test_analyze_review_envelope_schema_has_no_cache_fields():
    from models.review import AnalyzeReviewResponse

    props = AnalyzeReviewResponse.model_json_schema()["properties"]
    assert set(props) == {"success", "data", "error"}
    assert props["data"].get("anyOf") or props["data"].get("$ref")


def test_public_models_expose_no_cache_or_provider_fields():
    banned = ("cache", "provider", "model", "cost", "token", "hit")
    for props in (
        ReviewAnalysis.model_json_schema()["properties"],
        AISummaryResponse.model_json_schema()["properties"],
    ):
        for name in props:
            assert not any(word in name.lower() for word in banned), name


def test_cached_hit_returns_identical_public_payload():
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    miss = analyzer._call_google_genai(REVIEW)
    hit = analyzer._call_google_genai(REVIEW)
    assert miss.model_dump() == hit.model_dump()
    assert set(hit.model_dump()) == set(ReviewAnalysis.model_json_schema()["properties"])


def test_api_contract_unchanged_when_cache_enabled(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.setattr(_FakeResponse, "text", VALID_ANALYSIS_JSON)
    attempts: list = []
    _install_fake_sdk(monkeypatch, attempts)
    store = FakeCacheStore()
    monkeypatch.setattr(analyzer_service, "_llm_cache", llm_cache(store))

    client = TestClient(app, raise_server_exceptions=False)
    first = client.post("/api/analyze-review", json={"review": REVIEW})
    second = client.post("/api/analyze-review", json={"review": REVIEW})

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(attempts) == 1  # second request served entirely from cache
    body_first, body_second = first.json(), second.json()
    assert set(body_first) == {"success", "data", "error"}
    assert set(body_second) == {"success", "data", "error"}
    assert body_first == body_second
    assert set(body_first["data"]) == {
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    }
    assert "cache_hit" not in first.text
    assert "cache_hit" not in second.text


# ---------------------------------------------------------------------------
# I. Logging + never-stored security rules
# ---------------------------------------------------------------------------

def _cache_log_messages(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("services.cache")
    ]


def test_cache_logs_never_contain_review_prompt_payload_or_secrets(caplog):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    with caplog.at_level(logging.DEBUG, logger="services.cache"):
        analyzer._call_google_genai(REVIEW)  # miss + write
        analyzer._call_google_genai(REVIEW)  # hit

    cache_messages = "\n".join(_cache_log_messages(caplog))
    assert cache_messages  # hit/miss/write events were logged
    assert REVIEW not in cache_messages
    assert ODD_REVIEW not in cache_messages
    assert SYSTEM_INSTRUCTION[:60] not in cache_messages
    assert VALID_ANALYSIS_JSON not in cache_messages
    assert "postgresql://" not in cache_messages
    assert "DATABASE_URL" not in cache_messages
    assert "api_key" not in cache_messages.lower()
    # Nothing anywhere in the captured logs may leak the review text either.
    everything = "\n".join(r.getMessage() for r in caplog.records)
    assert REVIEW not in everything


def test_cache_rows_never_contain_credentials_or_dsn_material():
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=AIGateway(
            providers={"gemini": provider},
            registry=model_registry,
            default_provider=GEMINI_PROVIDER,
        ),
        rag_config=_rag(),
        llm_cache=cache,
    )
    analyzer._call_google_genai(ODD_REVIEW)
    dumped = json.dumps(store.rows(RESPONSE_TABLE), default=str)
    assert "test-key-not-real" not in dumped
    assert "api_key" not in dumped
    assert "DATABASE_URL" not in dumped
    assert "password" not in dumped
    assert "postgresql://" not in dumped
    assert "token_count" not in dumped
    assert "cost" not in dumped
    assert "billing" not in dumped


def test_provenance_is_never_returned_through_the_public_result():
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = _analyzer(cache, {"gemini": provider}, rag_config=_rag())
    analyzer._call_google_genai(REVIEW)
    result = analyzer._call_google_genai(REVIEW)
    dumped = json.dumps(result.model_dump())
    assert "groq" not in dumped
    assert "fallback" not in dumped
    assert "cache" not in dumped
    assert "provenance" not in dumped
