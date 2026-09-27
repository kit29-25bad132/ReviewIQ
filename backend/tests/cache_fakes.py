"""Shared offline test doubles for the V2-P9 cache tests.

Not collected by pytest (no ``test_`` prefix). No network, no database, no
provider SDK required: every store here is in-memory and every failure mode is
explicitly scripted.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from models.ecommerce import AISummaryResponse
from models.review import ReviewAnalysis
from services.ai.gateway import AIGateway
from services.ai.registry import GEMINI_PROVIDER, model_registry
from services.cache.config import CacheConfig
from services.cache.embedding_cache import EmbeddingCache
from services.cache.llm_cache import ANALYSIS_KIND, SUMMARY_KIND, LLMCache
from services.cache.store import EMBEDDING_TABLE, RESPONSE_TABLE, CacheStore
from services.ai_analyzer import AIAnalyzerService

REVIEW = "The battery lasts all day."

VALID_ANALYSIS_PAYLOAD: Dict[str, Any] = {
    "sentiment": "positive",
    "rating": 5,
    "rating_source": "inferred",
    "summary": "Great battery life.",
    "aspects": [
        {
            "aspect": "battery",
            "sentiment": "positive",
            "evidence": "The battery lasts all day",
        },
    ],
    "pros": [{"point": "All-day battery", "evidence": "The battery lasts all day"}],
    "cons": [],
}

VALID_ANALYSIS_JSON = (
    '{"sentiment": "positive", "rating": 5, "rating_source": "inferred", '
    '"summary": "Great battery life.", "aspects": [{"aspect": "battery", '
    '"sentiment": "positive", "evidence": "The battery lasts all day"}], '
    '"pros": [{"point": "All-day battery", '
    '"evidence": "The battery lasts all day"}], "cons": []}'
)

SUMMARY_PAYLOAD: Dict[str, Any] = {
    "summary": "Customers praise the battery performance.",
    "common_pros": ["Battery life"],
    "common_cons": [],
    "key_themes": ["Battery"],
    "source_label": "Summary generated from dataset reviews",
}

SUMMARY_JSON = (
    '{"summary": "Customers praise the battery performance.", '
    '"common_pros": ["Battery life"], "common_cons": [], '
    '"key_themes": ["Battery"], '
    '"source_label": "Summary generated from dataset reviews"}'
)

#: Deterministic live corpus token used by the fake store (RAG tests override).
DEFAULT_CORPUS_TOKEN = "v1|3|2026-09-01T00:00:00+00:00"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_analysis(**overrides: Any) -> ReviewAnalysis:
    payload = {**VALID_ANALYSIS_PAYLOAD, **overrides}
    return ReviewAnalysis.model_validate(payload)


def make_summary(**overrides: Any) -> AISummaryResponse:
    payload = {**SUMMARY_PAYLOAD, **overrides}
    return AISummaryResponse.model_validate(payload)


class FakeCacheStore(CacheStore):
    """In-memory ``CacheStore`` with scripted failure modes.

    - ``fail_ops``: operation names that RAISE (backend down / misbehaving).
    - ``corpus_token_value = None``: the live RAG corpus token cannot be
      obtained (the fail-closed path).
    - ``calls`` counts every operation for bypass assertions.
    """

    def __init__(
        self,
        *,
        corpus_token_value: Optional[str] = DEFAULT_CORPUS_TOKEN,
        fail_ops: Sequence[str] = (),
    ) -> None:
        self.tables: Dict[str, Dict[str, Dict[str, Any]]] = {
            RESPONSE_TABLE: {},
            EMBEDDING_TABLE: {},
        }
        self.corpus_token_value = corpus_token_value
        self.fail_ops: Set[str] = set(fail_ops)
        self.calls: Dict[str, int] = {
            "get": 0,
            "get_many": 0,
            "put": 0,
            "delete": 0,
            "corpus_token": 0,
        }

    # -- introspection helpers ---------------------------------------------

    def rows(self, table: str) -> Dict[str, Dict[str, Any]]:
        return self.tables[table]

    def seed(self, table: str, key: str, row: Dict[str, Any]) -> Dict[str, Any]:
        stored = dict(row)
        stored["cache_key"] = key
        self.tables[table][key] = stored
        return stored

    def delete_row(self, table: str, key: str) -> None:
        self.tables[table].pop(key, None)

    # -- CacheStore contract ------------------------------------------------

    def get(self, table: str, cache_key: str) -> Optional[Dict[str, Any]]:
        self.calls["get"] += 1
        if "get" in self.fail_ops:
            raise RuntimeError("cache backend unavailable")
        row = self.tables.get(table, {}).get(cache_key)
        return dict(row) if row is not None else None

    def get_many(
        self, table: str, cache_keys: Sequence[str]
    ) -> List[Optional[Dict[str, Any]]]:
        """One batched read (counted separately from per-key ``get``)."""
        self.calls["get_many"] += 1
        if "get_many" in self.fail_ops or "get" in self.fail_ops:
            raise RuntimeError("cache backend unavailable")
        bucket = self.tables.get(table, {})
        return [dict(bucket[key]) if key in bucket else None for key in cache_keys]

    def put(self, table: str, row: Dict[str, Any]) -> None:
        self.calls["put"] += 1
        if "put" in self.fail_ops:
            raise RuntimeError("cache backend unavailable")
        self.tables.setdefault(table, {})[row["cache_key"]] = dict(row)

    def delete(self, table: str, cache_key: str) -> None:
        self.calls["delete"] += 1
        if "delete" in self.fail_ops:
            raise RuntimeError("cache backend unavailable")
        self.tables.get(table, {}).pop(cache_key, None)

    def corpus_token(self) -> Optional[str]:
        self.calls["corpus_token"] += 1
        if "corpus_token" in self.fail_ops:
            raise RuntimeError("cache backend unavailable")
        return self.corpus_token_value


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def analysis_row(
    analysis: ReviewAnalysis,
    *,
    created_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    corpus_token: Optional[str] = None,
    rag_context_digest: Optional[str] = None,
    payload: Any = "__default__",
    cache_schema: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a stored ``ai_response_cache`` row (``payload`` defaults valid)."""
    from services.cache.keys import CACHE_SCHEMA_VERSION

    created = created_at or utcnow()
    body = (
        {
            "kind": ANALYSIS_KIND,
            "cache_schema": CACHE_SCHEMA_VERSION if cache_schema is None else cache_schema,
            "result": analysis.model_dump(mode="json"),
        }
        if payload == "__default__"
        else payload
    )
    return {
        "cache_key": "seeded-key",
        "payload": body,
        "provenance": provenance or {"task": "review_analysis"},
        "rag_context_digest": rag_context_digest,
        "corpus_token": corpus_token,
        "created_at": created,
        "expires_at": expires_at or (created + timedelta(seconds=3600)),
    }


def summary_row(
    summary: AISummaryResponse,
    *,
    created_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    payload: Any = "__default__",
) -> Dict[str, Any]:
    from services.cache.keys import CACHE_SCHEMA_VERSION

    created = created_at or utcnow()
    body = (
        {
            "kind": SUMMARY_KIND,
            "cache_schema": CACHE_SCHEMA_VERSION,
            "result": summary.model_dump(mode="json"),
        }
        if payload == "__default__"
        else payload
    )
    return {
        "cache_key": "seeded-key",
        "payload": body,
        "provenance": {"task": "dataset_summary"},
        "rag_context_digest": None,
        "corpus_token": None,
        "created_at": created,
        "expires_at": expires_at or (created + timedelta(seconds=3600)),
    }


def embedding_row(
    vector: Sequence[float],
    *,
    dimension: int,
    task_type: str = "RETRIEVAL_DOCUMENT",
    model: str = "fake-embed",
    created_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    created = created_at or utcnow()
    return {
        "cache_key": "seeded-key",
        "vector": list(vector),
        "task_type": task_type,
        "model": model,
        "dimension": dimension,
        "created_at": created,
        "expires_at": expires_at or (created + timedelta(seconds=7776000)),
    }


# ---------------------------------------------------------------------------
# Configured cache instances (tests inject stores; no env/DB required)
# ---------------------------------------------------------------------------

def llm_cache(
    store: FakeCacheStore,
    *,
    enabled: bool = True,
    ttl_seconds: int = 604800,
    rag_ttl_seconds: int = 3600,
) -> LLMCache:
    return LLMCache(
        store=store,
        config=CacheConfig(
            llm_enabled=enabled,
            embedding_enabled=False,
            llm_ttl_seconds=ttl_seconds,
            llm_rag_ttl_seconds=rag_ttl_seconds,
        ),
    )


def embedding_cache(
    store: FakeCacheStore,
    *,
    enabled: bool = True,
    ttl_seconds: int = 7776000,
    query_ttl_seconds: int = 2592000,
) -> EmbeddingCache:
    return EmbeddingCache(
        store=store,
        config=CacheConfig(
            llm_enabled=False,
            embedding_enabled=enabled,
            embedding_ttl_seconds=ttl_seconds,
            embedding_query_ttl_seconds=query_ttl_seconds,
        ),
    )


def analyzer_with_cache(
    cache: LLMCache,
    providers: Dict[str, Any],
    *,
    rag_config: Any = None,
    rag_service: Any = None,
) -> AIAnalyzerService:
    """AIAnalyzerService wired to a fake gateway and an injected cache."""
    gateway = AIGateway(
        providers=providers,
        registry=model_registry,
        default_provider=GEMINI_PROVIDER,
    )
    return AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=gateway,
        rag_config=rag_config,
        rag_service=rag_service,
        llm_cache=cache,
    )
