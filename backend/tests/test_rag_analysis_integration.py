"""V2-P3 integration: graph retrieval stage, analyzer prompt wiring, API contract.

Offline: scripted in-process provider (tests.test_ai_foundation.FakeProvider)
captures the exact prompt/system instruction the AI would receive; the HTTP
test reuses the fake google-genai SDK from tests.test_model_configuration.
"""

import json

from fastapi.testclient import TestClient

from main import app
from models.review import ReviewAnalysis
from services.ai.gateway import AIGateway
from services.ai.registry import GEMINI_PROVIDER, model_registry
from services.ai_analyzer import (
    AIAnalyzerService,
    SYSTEM_INSTRUCTION,
    analyzer_service,
)
from services.analysis_graph import run_analysis_graph
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.rag.config import RAGConfig
from services.rag.prompting import CONTEXT_HEADER, CONTEXT_SYSTEM_RULES
from services.rag.retrieval import RagRetrievalService
from services.retrieval.search_service import SemanticSearchOutcome
from services.retrieval.vector_repository import ReviewSearchResult
from tests.test_ai_foundation import FakeProvider
from tests.test_model_configuration import _FakeResponse, _install_fake_sdk

REVIEW = "The screen is bright and the colors pop."
CONTEXT_REVIEW_TEXT = "The battery lasts all day and never dies."

VALID_ANALYSIS = json.dumps(
    {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "explicit",
        "summary": "Bright screen with vivid colors.",
        "aspects": [],
        "pros": [{"point": "Bright screen", "evidence": "screen is bright"}],
        "cons": [],
    }
)

PLAIN_PROMPT = f'Analyze this customer product review:\n\n"""\n{REVIEW}\n"""'


def _analysis() -> ReviewAnalysis:
    return ReviewAnalysis(
        sentiment="positive",
        rating=5,
        rating_source="explicit",
        summary="Bright screen.",
        aspects=[],
        pros=[{"point": "Bright screen", "evidence": "screen is bright"}],
        cons=[],
    )


def _result(review_id, text, similarity, **kwargs):
    return ReviewSearchResult(
        review_id=review_id,
        review_text=text,
        normalized_text=text,
        similarity=similarity,
        distance=1.0 - similarity,
        embedding_model="fake-embed",
        **kwargs,
    )


class _ScriptedSearch:
    """Duck-typed SemanticSearchService: fixed results or a fixed failure."""

    def __init__(self, results=(), error=None):
        self.results = tuple(results)
        self.error = error
        self.calls = []

    def search(self, query, *, top_k=None, similarity_threshold=None, filters=None):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "filters": filters,
            }
        )
        if self.error is not None:
            raise self.error
        return SemanticSearchOutcome(
            query_text=query,
            normalized_query=query,
            results=self.results,
            top_k=top_k or 0,
            similarity_threshold=similarity_threshold,
            embedding_model="fake-embed",
            embedding_dimension=16,
        )


def _analyzer(provider, rag_config=None, rag_service=None) -> AIAnalyzerService:
    gateway = AIGateway(
        providers={provider.name: provider},
        registry=model_registry,
        default_provider=GEMINI_PROVIDER,
    )
    return AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=gateway,
        rag_config=rag_config,
        rag_service=rag_service,
    )


# ---------------------------------------------------------------------------
# LangGraph stage
# ---------------------------------------------------------------------------

def test_graph_without_retrieval_keeps_original_state_shape():
    state = run_analysis_graph(REVIEW, ["model-a"], lambda text, model: _analysis())
    assert "rag_context" not in state
    assert state["analysis"] is not None
    assert state["attempts"] == 1


def test_graph_runs_retrieval_before_first_attempt():
    calls = []
    sentinel = {"ctx": 1}

    def retrieve_fn(text):
        calls.append(("retrieve", text))
        return sentinel

    def attempt(text, model):
        calls.append(("attempt", text, model))
        return _analysis()

    state = run_analysis_graph(
        REVIEW, ["model-a"], attempt, retrieve_fn=retrieve_fn
    )
    assert calls == [("retrieve", REVIEW), ("attempt", REVIEW, "model-a")]
    assert state["rag_context"] is sentinel
    assert state["analysis"] is not None


def test_graph_retrieval_failure_never_blocks_analysis():
    def retrieve_fn(text):
        raise RuntimeError("db down")

    state = run_analysis_graph(
        REVIEW, ["model-a"], lambda text, model: _analysis(),
        retrieve_fn=retrieve_fn,
    )
    assert state["rag_context"] is None
    assert state["analysis"] is not None


# ---------------------------------------------------------------------------
# Analyzer prompt wiring
# ---------------------------------------------------------------------------

def test_analyzer_without_rag_uses_v1_prompt_and_system(monkeypatch):
    monkeypatch.delenv("RAG_ENABLED", raising=False)
    provider = FakeProvider([VALID_ANALYSIS])
    analyzer = _analyzer(provider, rag_config=RAGConfig())

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    request = provider.requests[0]
    assert request.prompt == PLAIN_PROMPT
    assert request.system_instruction == SYSTEM_INSTRUCTION


def test_analyzer_with_rag_sends_context_section_and_rules():
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    search = _ScriptedSearch(
        results=(
            _result(
                "ctx-1",
                CONTEXT_REVIEW_TEXT,
                0.87,
                rating=2,
                source="live",
                product_id="p9",
            ),
        )
    )
    service = RagRetrievalService(config, search_service=search)
    provider = FakeProvider([VALID_ANALYSIS])
    analyzer = _analyzer(provider, rag_service=service)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    request = provider.requests[0]
    assert REVIEW in request.prompt
    assert f'"""\n{REVIEW}\n"""' in request.prompt
    assert CONTEXT_HEADER in request.prompt
    assert CONTEXT_REVIEW_TEXT in request.prompt
    assert "review_id=ctx-1" in request.prompt
    assert request.system_instruction == SYSTEM_INSTRUCTION + CONTEXT_SYSTEM_RULES
    # Retrieval used the P2 search contract with RAG config values.
    assert search.calls[0]["query"] == REVIEW
    assert search.calls[0]["top_k"] == 3
    assert search.calls[0]["similarity_threshold"] == 0.0


def test_analyzer_retrieval_failure_or_empty_context_uses_plain_prompt():
    cases = [
        _ScriptedSearch(
            error=EmbeddingError("no key", EmbeddingErrorType.AUTHENTICATION)
        ),
        _ScriptedSearch(results=()),
    ]
    for search in cases:
        config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
        service = RagRetrievalService(config, search_service=search)
        provider = FakeProvider([VALID_ANALYSIS])
        analyzer = _analyzer(provider, rag_service=service)

        analysis = analyzer.analyze_review(REVIEW)

        assert analysis.sentiment == "positive"
        request = provider.requests[0]
        assert request.prompt == PLAIN_PROMPT
        assert request.system_instruction == SYSTEM_INSTRUCTION


def test_grounding_still_ignores_context_only_evidence():
    """Context may contain a claim; grounding must still use the original."""
    payload = json.dumps(
        {
            "sentiment": "positive",
            "rating": 5,
            "rating_source": "explicit",
            "summary": "Great battery and screen.",
            "aspects": [],
            "pros": [
                {"point": "Bright screen", "evidence": "screen is bright"},
                {"point": "All-day battery", "evidence": "battery lasts all day"},
            ],
            "cons": [],
        }
    )
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_REVIEW_TEXT, 0.9),))
    service = RagRetrievalService(config, search_service=search)
    provider = FakeProvider([payload])
    analyzer = _analyzer(provider, rag_service=service)

    analysis = analyzer.analyze_review(REVIEW)

    points = [pro.point for pro in analysis.pros]
    assert points == ["Bright screen"]


def test_retrieval_runs_once_across_model_fallback():
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_REVIEW_TEXT, 0.9),))
    service = RagRetrievalService(config, search_service=search)
    provider = FakeProvider([RuntimeError("transient provider failure"), VALID_ANALYSIS])
    analyzer = _analyzer(provider, rag_service=service)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert len(search.calls) == 1
    assert len(provider.requests) == 2
    assert CONTEXT_HEADER in provider.requests[0].prompt
    assert CONTEXT_HEADER in provider.requests[1].prompt


# ---------------------------------------------------------------------------
# API contract with RAG enabled
# ---------------------------------------------------------------------------

def test_api_contract_unchanged_when_rag_enabled(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(_FakeResponse, "text", VALID_ANALYSIS)
    attempts: list = []
    _install_fake_sdk(monkeypatch, attempts)

    config = RAGConfig(enabled=True, top_k=2, similarity_threshold=0.0)
    stub = RagRetrievalService(config, search_service=_ScriptedSearch(results=()))
    monkeypatch.setattr(analyzer_service, "_rag_service", stub)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/analyze-review", json={"review": REVIEW})

    assert resp.status_code == 200
    assert attempts  # real generation path ran through the fake SDK
    body = resp.json()
    assert set(body.keys()) == {"success", "data", "error"}
    assert body["success"] is True
    assert body["error"] is None
    assert set(body["data"].keys()) == {
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    }
    assert body["data"]["pros"][0]["evidence"] == "screen is bright"
