"""V2-P5 tests: multi-provider fallback (Gemini -> Groq -> OpenRouter).

Fully offline: in-process fake providers and injected HTTP transports; no
network and no real provider keys are required for the normal suite.

Covers the P5 requirements: Groq/OpenRouter adapters, provider-qualified
registry chain, configured/disabled filtering, model + provider fallback,
error-aware provider skip, metadata/usage preservation, RAG context reuse,
grounding after fallback, product-summary switching, API error safety, and
the invalid-argument classification regression.
"""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from models.review import ReviewAnalysis
from services.ai.contracts import AIGenerationRequest, AIResponse, ModelRef
from services.ai.errors import (
    AIErrorType,
    AIProviderError,
    classify_error_text,
    classify_provider_error,
)
from services.ai.gateway import AIGateway
from services.ai.providers import openai_compat
from services.ai.providers.groq import GroqProvider
from services.ai.providers.openai_compat import (
    ChatCompletionResult,
    OpenAICompatError,
    chat_completion_with_json_fallback,
    classify_openai_compat_error,
)
from services.ai.providers.openrouter import OpenRouterProvider
from services.ai.registry import (
    DEFAULT_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
    GEMINI_PROVIDER,
    GROQ_MODEL_NAMES,
    GROQ_PROVIDER,
    OPENROUTER_MODEL_ROUTE,
    OPENROUTER_PROVIDER,
    TASK_DATASET_SUMMARY,
    ModelRegistry,
    ModelSpec,
    model_registry,
)
from services.ai.routing import (
    build_target_chain,
    skips_remaining_provider_models,
)
from services.ai_analyzer import AIAnalyzerService, analyzer_service
from services.gemini_summary_service import gemini_summary_service
from services.rag.config import RAGConfig
from services.rag.prompting import CONTEXT_HEADER, CONTEXT_SYSTEM_RULES
from services.rag.retrieval import RagRetrievalService
from tests.test_ai_foundation import FakeProvider
from tests.test_rag_analysis_integration import (
    CONTEXT_REVIEW_TEXT,
    REVIEW as RAG_REVIEW,
    _result,
    _ScriptedSearch,
)

client = TestClient(app, raise_server_exceptions=False)

REVIEW = "The battery lasts all day."

VALID_PAYLOAD = {
    "sentiment": "positive",
    "rating": 5,
    "rating_source": "inferred",
    "summary": "Great battery life.",
    "aspects": [
        {
            "aspect": "battery",
            "sentiment": "positive",
            "evidence": "The battery lasts all day",
        }
    ],
    "pros": [{"point": "All-day battery", "evidence": "The battery lasts all day"}],
    "cons": [],
}
VALID_JSON = json.dumps(VALID_PAYLOAD)

GEMINI_CHAIN = [DEFAULT_MODEL_NAME, *FALLBACK_MODEL_NAMES]
GROQ_CHAIN = list(GROQ_MODEL_NAMES)

SUMMARY_JSON = json.dumps(
    {
        "summary": "Customer feedback highlights battery performance.",
        "common_pros": ["Battery life"],
        "common_cons": [],
        "key_themes": ["Battery"],
        "source_label": "Summary generated from dataset reviews",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_failure(request):
    """Script step: normalized AUTHENTICATION failure (what adapters return)."""
    return AIResponse.failure(
        provider=request.provider,
        model=request.model,
        error_type=AIErrorType.AUTHENTICATION,
        error_message="401 unauthorized: invalid api key",
    )


def _gateway(providers):
    return AIGateway(
        providers=providers, registry=model_registry, default_provider=GEMINI_PROVIDER
    )


def _analyzer(providers):
    return AIAnalyzerService(api_key="test-key-not-real", gateway=_gateway(providers))


def _multi_providers(gemini_script, groq_script=None, openrouter_script=None):
    providers = {"gemini": FakeProvider(gemini_script, name="gemini")}
    if groq_script is not None:
        providers["groq"] = FakeProvider(groq_script, name="groq")
    if openrouter_script is not None:
        providers["openrouter"] = FakeProvider(openrouter_script, name="openrouter")
    return providers


def _usage_transport(content=VALID_JSON):
    def transport(**kwargs):
        return ChatCompletionResult(
            content=content, prompt_tokens=10, completion_tokens=20, total_tokens=30
        )

    return transport


# ---------------------------------------------------------------------------
# 1-6. Groq provider
# ---------------------------------------------------------------------------

def test_groq_provider_basic_successful_response():
    captured = {}
    provider = GroqProvider(
        api_key_provider=lambda: "gsk_test_key", transport=_usage_transport()
    )
    provider_name_capture = provider.API_URL

    original = provider._transport

    def transport(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    provider._transport = transport

    response = provider.generate(
        AIGenerationRequest(prompt="p", system_instruction="sys", model=GROQ_CHAIN[0])
    )

    assert response.success is True
    assert response.content == VALID_JSON
    assert response.provider == "groq"
    assert response.model == GROQ_CHAIN[0]
    assert response.latency_ms is not None and response.latency_ms >= 0
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["url"] == provider_name_capture
    assert captured["api_key"] == "gsk_test_key"


def test_groq_is_configured(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert GroqProvider().ENV_VAR == "GROQ_API_KEY"
    assert GroqProvider().is_configured() is False

    monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key_here")
    assert GroqProvider().is_configured() is False  # placeholder protection

    monkeypatch.setenv("GROQ_API_KEY", " gsk_real_key_value ")
    assert GroqProvider().is_configured() is True


def test_groq_authentication_error_normalization():
    def transport(**kwargs):
        raise OpenAICompatError(
            "HTTP 401 from provider endpoint",
            status=401,
            body='{"error":{"message":"Invalid API Key"}}',
        )

    provider = GroqProvider(api_key_provider=lambda: "bad", transport=transport)
    response = provider.generate(
        AIGenerationRequest(prompt="p", model=GROQ_CHAIN[0])
    )

    assert response.success is False
    assert response.error_type is AIErrorType.AUTHENTICATION
    assert response.provider == "groq"
    assert response.model == GROQ_CHAIN[0]


def test_groq_rate_limit_error_normalization():
    def transport(**kwargs):
        raise OpenAICompatError(
            "HTTP 429 from provider endpoint",
            status=429,
            body="rate limit reached for requests",
        )

    provider = GroqProvider(api_key_provider=lambda: "k", transport=transport)
    response = provider.generate(
        AIGenerationRequest(prompt="p", model=GROQ_CHAIN[0])
    )

    assert response.success is False
    assert response.error_type is AIErrorType.RATE_LIMIT


def test_groq_timeout_and_transient_error_normalization():
    def timeout_transport(**kwargs):
        raise OpenAICompatError("connection failed: TimeoutError", is_timeout=True)

    def transient_transport(**kwargs):
        raise OpenAICompatError("HTTP 503 from provider endpoint", status=503)

    timeout_response = GroqProvider(
        api_key_provider=lambda: "k", transport=timeout_transport
    ).generate(AIGenerationRequest(prompt="p", model=GROQ_CHAIN[0]))
    transient_response = GroqProvider(
        api_key_provider=lambda: "k", transport=transient_transport
    ).generate(AIGenerationRequest(prompt="p", model=GROQ_CHAIN[0]))

    assert timeout_response.success is False
    assert timeout_response.error_type is AIErrorType.TIMEOUT
    assert transient_response.success is False
    assert transient_response.error_type is AIErrorType.TRANSIENT


def test_groq_structured_output_request():
    captured = {}
    provider = GroqProvider(api_key_provider=lambda: "k", transport=_usage_transport())

    original = provider._transport

    def transport(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    provider._transport = transport

    response = provider.generate(
        AIGenerationRequest(
            prompt="analyze",
            system_instruction="sys instructions",
            provider=GROQ_PROVIDER,
            model=GROQ_CHAIN[1],
            temperature=0.3,
            timeout_seconds=7.5,
            response_schema=ReviewAnalysis,
            metadata={"task": "review_analysis"},
        )
    )

    payload = captured["payload"]
    assert payload["model"] == GROQ_CHAIN[1]
    assert payload["temperature"] == 0.3
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0] == {"role": "system", "content": "sys instructions"}
    assert payload["messages"][1]["role"] == "user"
    # The adapter enforces the contract's timeout instead of silently ignoring it.
    assert captured["timeout_seconds"] == 7.5
    # Application-side validation stays authoritative; structured flag is metadata.
    assert response.metadata["structured"] is True
    assert response.metadata["task"] == "review_analysis"
    ReviewAnalysis.model_validate(json.loads(response.content))


# ---------------------------------------------------------------------------
# 7-10. OpenRouter provider
# ---------------------------------------------------------------------------

def test_openrouter_provider_basic_successful_response():
    captured = {}
    provider = OpenRouterProvider(
        api_key_provider=lambda: "sk-or_test", transport=_usage_transport()
    )

    original = provider._transport

    def transport(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    provider._transport = transport

    response = provider.generate(
        AIGenerationRequest(prompt="p", model=OPENROUTER_MODEL_ROUTE)
    )

    assert response.success is True
    assert response.content == VALID_JSON
    assert response.provider == "openrouter"
    assert response.model == "openrouter/free"
    assert response.usage is not None and response.usage.total_tokens == 30
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["api_key"] == "sk-or_test"


def test_openrouter_is_configured(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert OpenRouterProvider().ENV_VAR == "OPENROUTER_API_KEY"
    assert OpenRouterProvider().is_configured() is False

    monkeypatch.setenv("OPENROUTER_API_KEY", "your_openrouter_api_key_here")
    assert OpenRouterProvider().is_configured() is False  # placeholder protection

    monkeypatch.setenv("OPENROUTER_API_KEY", " sk-or_real_value ")
    assert OpenRouterProvider().is_configured() is True


def test_openrouter_error_normalization_full_transport(monkeypatch):
    """HTTP errors from the real stdlib transport are normalized, not leaked."""

    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"missing authorization key"}}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenRouterProvider(api_key_provider=lambda: "bad-key")
    response = provider.generate(
        AIGenerationRequest(prompt="p", model=OPENROUTER_MODEL_ROUTE)
    )

    assert response.success is False
    assert response.error_type is AIErrorType.AUTHENTICATION
    assert response.provider == "openrouter"
    assert "bad-key" not in (response.error_message or "")
    assert "Traceback" not in (response.error_message or "")


def test_openrouter_malformed_response_is_invalid_response(monkeypatch):
    def fake_urlopen(request, timeout=None):
        class _Resp:
            def read(self):
                return b"<html>not json at all</html>"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = OpenRouterProvider(api_key_provider=lambda: "k").generate(
        AIGenerationRequest(prompt="p", model=OPENROUTER_MODEL_ROUTE)
    )

    assert response.success is False
    assert response.error_type is AIErrorType.INVALID_RESPONSE


def test_openrouter_structured_output_request():
    captured = {}
    provider = OpenRouterProvider(
        api_key_provider=lambda: "k", transport=_usage_transport()
    )

    original = provider._transport

    def transport(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    provider._transport = transport

    response = provider.generate(
        AIGenerationRequest(
            prompt="analyze",
            system_instruction="sys",
            model=OPENROUTER_MODEL_ROUTE,
            response_schema=ReviewAnalysis,
        )
    )

    payload = captured["payload"]
    assert payload["model"] == "openrouter/free"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0]["role"] == "system"
    assert response.metadata["structured"] is True
    # Application-side validation remains mandatory regardless of native support.
    ReviewAnalysis.model_validate(json.loads(response.content))


def test_response_format_rejection_retried_once_without_it(monkeypatch):
    calls = []

    def fake_chat_completion(*, url, api_key, payload, timeout_seconds=None):
        calls.append(dict(payload))
        if "response_format" in payload:
            raise OpenAICompatError(
                "HTTP 400 from provider endpoint",
                status=400,
                body="unsupported parameter: response_format",
            )
        return ChatCompletionResult(content="{}")

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat_completion)
    result = chat_completion_with_json_fallback(
        url="https://example.invalid/v1/chat/completions",
        api_key="k",
        payload={"model": "m", "response_format": {"type": "json_object"}},
    )

    assert result.content == "{}"
    assert len(calls) == 2
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]


# ---------------------------------------------------------------------------
# 11-13. Provider-qualified registry chain
# ---------------------------------------------------------------------------

def test_provider_qualified_registry_chain():
    targets = model_registry.chain_refs()

    assert targets == [
        ModelRef(GEMINI_PROVIDER, model) for model in GEMINI_CHAIN
    ] + [
        ModelRef(GROQ_PROVIDER, model) for model in GROQ_CHAIN
    ] + [
        ModelRef(OPENROUTER_PROVIDER, OPENROUTER_MODEL_ROUTE)
    ]
    assert len(targets) == 9 == len(set(targets))


def test_registry_chain_filters_unconfigured_providers():
    gemini_only = model_registry.chain_refs(
        is_configured=lambda p: p == GEMINI_PROVIDER
    )
    assert {t.provider for t in gemini_only} == {GEMINI_PROVIDER}
    assert [t.model for t in gemini_only] == GEMINI_CHAIN

    gemini_groq = model_registry.chain_refs(
        is_configured=lambda p: p in {GEMINI_PROVIDER, GROQ_PROVIDER}
    )
    assert {t.provider for t in gemini_groq} == {GEMINI_PROVIDER, GROQ_PROVIDER}
    assert [t.model for t in gemini_groq] == GEMINI_CHAIN + GROQ_CHAIN
    assert OPENROUTER_PROVIDER not in {t.provider for t in gemini_groq}


def test_registry_chain_filters_disabled_models():
    registry = ModelRegistry(
        [
            ModelSpec(
                provider=GEMINI_PROVIDER,
                model="g-on",
                priority=0,
                is_default_primary=True,
                is_fallback_candidate=False,
            ),
            ModelSpec(provider=GEMINI_PROVIDER, model="g-off", priority=1, enabled=False),
            ModelSpec(
                provider=GROQ_PROVIDER,
                model="q-on",
                priority=0,
                is_default_primary=True,
                is_fallback_candidate=False,
            ),
            ModelSpec(provider=GROQ_PROVIDER, model="q-off", priority=1, enabled=False),
        ]
    )
    targets = registry.chain_refs(is_configured=lambda p: True)

    assert [t.model for t in targets] == ["g-on", "q-on"]


# ---------------------------------------------------------------------------
# 14-18. Provider/model fallback through the analyzer
# ---------------------------------------------------------------------------

def test_gemini_to_groq_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [RuntimeError("429 rate limit exceeded")],
        groq_script=[VALID_JSON],
    )
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert len(providers["gemini"].requests) == 5
    assert len(providers["groq"].requests) == 1
    assert providers["groq"].requests[0].provider == "groq"
    assert providers["groq"].requests[0].model == GROQ_CHAIN[0]
    assert providers["gemini"].requests[0].metadata["fallback"] is False
    assert providers["groq"].requests[0].metadata["fallback"] is True


def test_gemini_model_fallback_remains_intact(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers([RuntimeError("primary boom"), VALID_JSON])
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    models = [r.model for r in providers["gemini"].requests]
    assert models == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]


def test_groq_model_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [_auth_failure],
        groq_script=[RuntimeError("429 rate limit"), VALID_JSON],
    )
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    # Gemini was skipped at the provider level after one auth failure.
    assert len(providers["gemini"].requests) == 1
    assert [r.model for r in providers["groq"].requests] == GROQ_CHAIN[:2]


def test_gemini_exhausted_then_groq_success(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [RuntimeError("service overloaded")],
        groq_script=[VALID_JSON],
    )
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert [r.model for r in providers["gemini"].requests] == GEMINI_CHAIN
    assert [r.model for r in providers["groq"].requests] == [GROQ_CHAIN[0]]


def test_gemini_exhausted_groq_exhausted_openrouter_success(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [RuntimeError("service overloaded")],
        groq_script=[RuntimeError("model not found")],
        openrouter_script=[VALID_JSON],
    )
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert [r.model for r in providers["gemini"].requests] == GEMINI_CHAIN
    assert [r.model for r in providers["groq"].requests] == GROQ_CHAIN
    assert [r.model for r in providers["openrouter"].requests] == [
        OPENROUTER_MODEL_ROUTE
    ]
    assert providers["openrouter"].requests[0].provider == "openrouter"


# ---------------------------------------------------------------------------
# 19-22. Error-aware provider skip + unconfigured filtering
# ---------------------------------------------------------------------------

def test_authentication_on_gemini_skips_remaining_gemini_models(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers([_auth_failure], groq_script=[VALID_JSON])
    analysis = _analyzer(providers).analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert len(providers["gemini"].requests) == 1  # G2..G5 never called
    assert len(providers["groq"].requests) == 1

    # With no other provider configured, the meaningful AUTH error survives.
    only_gemini = _multi_providers([_auth_failure])
    analyzer = _analyzer(only_gemini)
    with pytest.raises(AIProviderError) as excinfo:
        analyzer.analyze_review(REVIEW)
    assert excinfo.value.error_type is AIErrorType.AUTHENTICATION
    assert len(only_gemini["gemini"].requests) == 1


def test_authentication_on_groq_skips_remaining_groq_models(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [RuntimeError("service overloaded")],
        groq_script=[_auth_failure],
        openrouter_script=[VALID_JSON],
    )
    analysis = _analyzer(providers).analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert len(providers["gemini"].requests) == 5
    assert len(providers["groq"].requests) == 1  # Q2..Q3 never called
    assert len(providers["openrouter"].requests) == 1


def test_unconfigured_groq_is_skipped(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _explode(*args, **kwargs):
        raise AssertionError("an unconfigured provider must never be invoked")

    monkeypatch.setattr(GroqProvider, "generate", _explode)

    gemini = FakeProvider([VALID_JSON])
    gateway = _gateway(
        {
            "gemini": gemini,
            GROQ_PROVIDER: GroqProvider(),
            OPENROUTER_PROVIDER: OpenRouterProvider(),
        }
    )
    chain = build_target_chain(gateway)
    assert {t.provider for t in chain} == {GEMINI_PROVIDER}

    analyzer = AIAnalyzerService(api_key="test-key-not-real", gateway=gateway)
    analysis = analyzer.analyze_review(REVIEW)
    assert analysis.sentiment == "positive"


def test_unconfigured_openrouter_is_skipped(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _explode(*args, **kwargs):
        raise AssertionError("an unconfigured provider must never be invoked")

    monkeypatch.setattr(OpenRouterProvider, "generate", _explode)

    gemini = FakeProvider([RuntimeError("service overloaded")])
    gateway = _gateway(
        {
            "gemini": gemini,
            GROQ_PROVIDER: GroqProvider(),
            OPENROUTER_PROVIDER: OpenRouterProvider(),
        }
    )
    chain = build_target_chain(gateway)
    assert OPENROUTER_PROVIDER not in {t.provider for t in chain}

    analyzer = AIAnalyzerService(api_key="test-key-not-real", gateway=gateway)
    with pytest.raises(AIProviderError):
        analyzer.analyze_review(REVIEW)
    # Only Gemini's 5 models ran; neither unconfigured provider was touched.
    assert len(gemini.requests) == 5


# ---------------------------------------------------------------------------
# 23-24. Metadata + usage preservation
# ---------------------------------------------------------------------------

def test_provider_model_metadata_survives_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [RuntimeError("service overloaded")],
        groq_script=[VALID_JSON],
    )
    analyzer = _analyzer(providers)
    analysis = analyzer.analyze_review(REVIEW)
    assert analysis.sentiment == "positive"

    gemini_request = providers["gemini"].requests[0]
    groq_request = providers["groq"].requests[0]
    assert (gemini_request.provider, gemini_request.model) == (
        GEMINI_PROVIDER,
        GEMINI_CHAIN[0],
    )
    assert (groq_request.provider, groq_request.model) == (
        GROQ_PROVIDER,
        GROQ_CHAIN[0],
    )

    # Gateway-level response metadata for a successful Groq/OpenRouter call
    # (real adapters with injected transports; FakeProvider carries no metadata).
    gateway = _gateway(
        {
            "groq": GroqProvider(
                api_key_provider=lambda: "k", transport=_usage_transport()
            ),
            "openrouter": OpenRouterProvider(
                api_key_provider=lambda: "k", transport=_usage_transport()
            ),
        }
    )
    groq_response = gateway.generate(
        AIGenerationRequest(
            prompt="p", provider="groq", model=GROQ_CHAIN[1],
            response_schema=ReviewAnalysis,
        )
    )
    openrouter_response = gateway.generate(
        AIGenerationRequest(
            prompt="p", provider="openrouter", model=OPENROUTER_MODEL_ROUTE,
            response_schema=ReviewAnalysis,
        )
    )
    assert groq_response.success is True
    assert (groq_response.provider, groq_response.model) == (GROQ_PROVIDER, GROQ_CHAIN[1])
    assert groq_response.metadata["structured"] is True
    assert openrouter_response.success is True
    assert (openrouter_response.provider, openrouter_response.model) == (
        OPENROUTER_PROVIDER,
        OPENROUTER_MODEL_ROUTE,
    )


def test_usage_metadata_survives_fallback_where_available(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    gemini = FakeProvider([RuntimeError("service overloaded")])
    real_groq = GroqProvider(api_key_provider=lambda: "k", transport=_usage_transport())
    gateway = _gateway({"gemini": gemini, "groq": real_groq})
    analyzer = AIAnalyzerService(api_key="test-key-not-real", gateway=gateway)

    analysis = analyzer.analyze_review(REVIEW)
    assert analysis.sentiment == "positive"
    assert len(gemini.requests) == 5

    # Real adapter: usage is carried through the gateway without fabrication.
    response = gateway.generate(
        AIGenerationRequest(prompt="p", provider="groq", model=GROQ_CHAIN[0])
    )
    assert response.usage is not None
    assert (
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        response.usage.total_tokens,
    ) == (10, 20, 30)
    assert response.usage.estimated_cost_usd is None  # never fabricated

    # Fake adapter without usage: None stays None (no fabricated zeros).
    fake_only = _gateway({"groq": FakeProvider([VALID_JSON], name="groq")})
    no_usage = fake_only.generate(
        AIGenerationRequest(prompt="p", provider="groq", model=GROQ_CHAIN[0])
    )
    assert no_usage.success is True
    assert no_usage.usage is None


# ---------------------------------------------------------------------------
# 25-26. RAG + grounding across provider fallback
# ---------------------------------------------------------------------------

def test_rag_context_identical_across_provider_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_REVIEW_TEXT, 0.9),))
    service = RagRetrievalService(config, search_service=search)

    providers = _multi_providers(
        [RuntimeError("transient provider failure")],
        groq_script=[VALID_JSON],
    )
    analyzer = AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=_gateway(providers),
        rag_service=service,
    )

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    # Retrieval ran once, before any attempt — even across providers.
    assert len(search.calls) == 1
    assert len(providers["gemini"].requests) == 5
    assert len(providers["groq"].requests) == 1

    prompts = [r.prompt for r in providers["gemini"].requests]
    prompts += [r.prompt for r in providers["groq"].requests]
    assert all(p == prompts[0] for p in prompts)
    assert CONTEXT_HEADER in providers["groq"].requests[0].prompt
    assert providers["groq"].requests[0].system_instruction.endswith(
        CONTEXT_SYSTEM_RULES
    )
    assert REVIEW in providers["groq"].requests[0].prompt


def test_grounding_removes_unsupported_evidence_after_provider_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_REVIEW_TEXT, 0.9),))
    service = RagRetrievalService(config, search_service=search)

    # The fallback provider mixes original-supported and context-only evidence.
    payload = json.dumps(
        {
            "sentiment": "positive",
            "rating": 5,
            "rating_source": "explicit",
            "summary": "Bright screen with an all-day battery.",
            "aspects": [],
            "pros": [
                {"point": "Bright screen", "evidence": "screen is bright"},
                {"point": "All-day battery", "evidence": CONTEXT_REVIEW_TEXT},
            ],
            "cons": [],
        }
    )
    providers = _multi_providers(
        [RuntimeError("service overloaded")],
        groq_script=[payload],
    )
    analyzer = AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=_gateway(providers),
        rag_service=service,
    )

    analysis = analyzer.analyze_review(RAG_REVIEW)

    # Context-only evidence produced by the fallback provider is removed.
    assert [p.point for p in analysis.pros] == ["Bright screen"]
    assert analysis.pros[0].evidence == "screen is bright"
    assert "battery lasts all day" not in json.dumps(analysis.model_dump())


# ---------------------------------------------------------------------------
# 27. Product-summary fallback path
# ---------------------------------------------------------------------------

def test_product_summary_fallback_supports_provider_switch(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers([_auth_failure], groq_script=[SUMMARY_JSON])
    monkeypatch.setattr(analyzer_service, "_gateway", _gateway(providers))

    result = gemini_summary_service._generate_summary("prompt")

    assert result.summary == "Customer feedback highlights battery performance."
    assert result.source_label == "Summary generated from dataset reviews"
    # Gemini auth failure skipped its remaining models; Groq served the call.
    assert len(providers["gemini"].requests) == 1
    groq_request = providers["groq"].requests[0]
    assert groq_request.provider == "groq"
    assert groq_request.model == GROQ_CHAIN[0]
    assert groq_request.metadata["task"] == TASK_DATASET_SUMMARY
    assert groq_request.metadata["fallback"] is True


# ---------------------------------------------------------------------------
# 28-29. API safety + exhaustion
# ---------------------------------------------------------------------------

def test_api_auth_error_from_provider_does_not_leak():
    error = AIProviderError(
        "401 unauthorized key=gsk_SUPERSECRET_VALUE",
        AIErrorType.AUTHENTICATION,
        provider="groq",
        model=GROQ_CHAIN[0],
    )
    with patch.object(analyzer_service, "analyze_review", side_effect=error):
        resp = client.post("/api/analyze-review", json={"review": REVIEW})

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail == (
        "Invalid or unauthenticated AI provider API key. Please check backend/.env"
    )
    assert "gsk_SUPERSECRET_VALUE" not in resp.text
    assert "401 unauthorized" not in detail


def test_api_no_provider_key_error_is_safe_and_mentions_env():
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=ValueError(
            "No AI provider API key is configured. Please set GEMINI_API_KEY "
            "(or GROQ_API_KEY / OPENROUTER_API_KEY) in backend/.env"
        ),
    ):
        resp = client.post("/api/analyze-review", json={"review": REVIEW})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "GEMINI_API_KEY" in detail
    assert "backend/.env" in detail


def test_fallback_exhaustion_across_all_providers_is_safe(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers(
        [RuntimeError("429 rate limit exceeded")],
        groq_script=[RuntimeError("429 rate limit exceeded")],
        openrouter_script=[RuntimeError("429 rate limit exceeded")],
    )
    analyzer = _analyzer(providers)

    with pytest.raises(AIProviderError) as excinfo:
        analyzer.analyze_review(REVIEW)

    assert excinfo.value.error_type is AIErrorType.RATE_LIMIT
    # Bounded: 5 Gemini + 3 Groq + 1 OpenRouter, no retry storms.
    assert len(providers["gemini"].requests) == 5
    assert len(providers["groq"].requests) == 3
    assert len(providers["openrouter"].requests) == 1


# ---------------------------------------------------------------------------
# 30. Error classification regression (invalid argument != authentication)
# ---------------------------------------------------------------------------

def test_invalid_argument_is_not_classified_as_authentication():
    assert (
        classify_error_text("Invalid argument: response_format must be a JSON object")
        is AIErrorType.INVALID_REQUEST
    )
    # "unsupported" is a model hint and wins by precedence, but such a message
    # must never be mistaken for a credential failure (the original V1 bug).
    assert (
        classify_error_text("Invalid argument: unsupported response_format")
        is not AIErrorType.AUTHENTICATION
    )
    assert (
        classify_error_text("invalid_argument: bad request body")
        is AIErrorType.INVALID_REQUEST
    )
    # Text hints win over the exception type, as with every other category.
    assert (
        classify_provider_error(ValueError("Invalid argument: nope"))
        is AIErrorType.INVALID_REQUEST
    )
    # More specific categories still win over the generic request hint.
    assert (
        classify_error_text("invalid argument: quota exceeded")
        is AIErrorType.RATE_LIMIT
    )
    assert (
        classify_error_text("invalid argument: model not found")
        is AIErrorType.MODEL_UNAVAILABLE
    )
    # Real authentication messages keep their classification.
    assert (
        classify_error_text("API key not valid. Please pass a valid API key.")
        is AIErrorType.AUTHENTICATION
    )
    assert classify_error_text("UNAUTHENTICATED invalid api key") is (
        AIErrorType.AUTHENTICATION
    )
    # HTTP-status fallback in the OpenAI-compatible transport.
    assert (
        classify_openai_compat_error(
            OpenAICompatError("HTTP 400 from provider endpoint", status=400)
        )
        is AIErrorType.INVALID_REQUEST
    )


def test_provider_skip_predicate_matches_spec():
    assert skips_remaining_provider_models(AIErrorType.AUTHENTICATION) is True
    assert skips_remaining_provider_models(AIErrorType.CONFIGURATION) is True
    for error_type in (
        AIErrorType.RATE_LIMIT,
        AIErrorType.TIMEOUT,
        AIErrorType.TRANSIENT,
        AIErrorType.MODEL_UNAVAILABLE,
        AIErrorType.INVALID_RESPONSE,
        AIErrorType.INVALID_REQUEST,
        AIErrorType.UNKNOWN,
    ):
        assert skips_remaining_provider_models(error_type) is False
    assert skips_remaining_provider_models(None) is False


# ---------------------------------------------------------------------------
# Timeout contract coverage for both new adapters
# ---------------------------------------------------------------------------

def test_new_adapters_enforce_timeout_seconds():
    for provider_cls, key in ((GroqProvider, "k"), (OpenRouterProvider, "k")):
        captured = {}

        def transport(**kwargs):
            captured.update(kwargs)
            return ChatCompletionResult(content=VALID_JSON)

        provider = provider_cls(api_key_provider=lambda: key, transport=transport)
        provider.generate(
            AIGenerationRequest(
                prompt="p", model="m", timeout_seconds=12.5,
                response_schema=ReviewAnalysis,
            )
        )
        assert captured["timeout_seconds"] == 12.5
