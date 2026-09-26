"""V2 AI foundation tests: provider abstraction, model registry, AI Gateway.

Everything here is offline. Gemini's SDK is replaced with an in-memory fake
(no live API key, no network) and an in-process fake provider is used to test
the gateway/pipeline boundaries.
"""

import json
import sys
from typing import List
from unittest import mock

import pytest

from models.review import ReviewAnalysis
from services.ai.contracts import AIGenerationRequest, AIResponse
from services.ai.errors import (
    AIErrorType,
    AIProviderError,
    ModelNotAvailableError,
    UnknownProviderError,
)
from services.ai.gateway import AIGateway
from services.ai.provider import AIProvider
from services.ai.providers.gemini import GeminiProvider
from services.ai.registry import (
    DEFAULT_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
    GEMINI_PROVIDER,
    ModelRegistry,
    ModelSpec,
    model_registry,
)
from services.ai_analyzer import AIAnalyzerService, _build_model_list

VALID_PAYLOAD = {
    "sentiment": "positive",
    "rating": 5,
    "rating_source": "inferred",
    "summary": "Great battery life.",
    "aspects": [
        {"aspect": "battery", "sentiment": "positive", "evidence": "The battery lasts all day"}
    ],
    "pros": [{"point": "All-day battery", "evidence": "The battery lasts all day"}],
    "cons": [],
}
REVIEW = "The battery lasts all day."
VALID_JSON = json.dumps(VALID_PAYLOAD)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeProvider(AIProvider):
    """Scripted in-process provider: each call consumes one script entry."""

    name = "gemini"

    def __init__(self, script, name: str = "gemini"):
        self.name = name
        self.script = list(script)
        self.requests: List[AIGenerationRequest] = []

    def is_configured(self) -> bool:
        return True

    def generate(self, request: AIGenerationRequest) -> AIResponse:
        self.requests.append(request)
        index = len(self.requests) - 1
        step = self.script[index] if index < len(self.script) else self.script[-1]
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(request)
        return AIResponse(content=step, provider=self.name, model=request.model or "")


class _FakeResponse:
    def __init__(self, text, usage=None):
        self.text = text
        if usage is not None:
            self.usage_metadata = usage


class _FakeUsage:
    prompt_token_count = 11
    candidates_token_count = 22
    total_token_count = 33


class _FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.attempts: List[str] = []

    def generate_content(self, model, contents, config):
        self.attempts.append(model)
        index = len(self.attempts) - 1
        step = self.script[index] if index < len(self.script) else self.script[-1]
        if isinstance(step, BaseException):
            raise step
        return step


def _install_fake_genai(monkeypatch, script) -> _FakeModels:
    models = _FakeModels(script)

    class _Client:
        def __init__(self, api_key):
            self.models = models

    fake_genai = mock.MagicMock()
    fake_genai.Client = lambda api_key: _Client(api_key)
    fake_types = mock.MagicMock()
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    return models


def _gemini_provider() -> GeminiProvider:
    return GeminiProvider(api_key_provider=lambda: "test-key-not-real")


def _analyzer_with(provider: AIProvider) -> AIAnalyzerService:
    gateway = AIGateway(
        providers={provider.name: provider},
        registry=model_registry,
        default_provider=GEMINI_PROVIDER,
    )
    return AIAnalyzerService(api_key="test-key-not-real", gateway=gateway)


# ---------------------------------------------------------------------------
# 1. Provider interface can be invoked (through the gateway)
# ---------------------------------------------------------------------------

def test_provider_interface_can_be_invoked():
    provider = FakeProvider(["hello"])
    gateway = AIGateway(providers={provider.name: provider}, registry=model_registry)

    response = gateway.generate(
        AIGenerationRequest(prompt="hi", provider="gemini", model=DEFAULT_MODEL_NAME)
    )

    assert response.success is True
    assert response.content == "hello"
    assert response.provider == "gemini"
    assert provider.requests and provider.requests[0].prompt == "hi"


# ---------------------------------------------------------------------------
# 2. Gemini adapter returns the provider-neutral response
# ---------------------------------------------------------------------------

def test_gemini_adapter_returns_provider_neutral_response(monkeypatch):
    models = _install_fake_genai(monkeypatch, [_FakeResponse(VALID_JSON, usage=_FakeUsage())])

    response = _gemini_provider().generate(
        AIGenerationRequest(
            prompt="analyze",
            provider=GEMINI_PROVIDER,
            model=DEFAULT_MODEL_NAME,
            response_schema=ReviewAnalysis,
        )
    )

    assert isinstance(response, AIResponse)
    assert response.success is True
    assert response.provider == "gemini"
    assert response.model == DEFAULT_MODEL_NAME
    assert response.content == VALID_JSON
    assert response.usage is not None and response.usage.total_tokens == 33
    assert response.latency_ms is not None and response.latency_ms >= 0
    assert response.metadata["structured"] is True
    # Structured output was actually requested from the SDK.
    assert models.attempts == [DEFAULT_MODEL_NAME]


# ---------------------------------------------------------------------------
# 3. Gemini model selection works
# ---------------------------------------------------------------------------

def test_gateway_invokes_explicitly_selected_model(monkeypatch):
    models = _install_fake_genai(monkeypatch, [_FakeResponse("ok")])
    gateway = AIGateway(
        providers={GEMINI_PROVIDER: _gemini_provider()},
        registry=model_registry,
        default_provider=GEMINI_PROVIDER,
    )

    gateway.generate(
        AIGenerationRequest(prompt="p", provider=GEMINI_PROVIDER, model=FALLBACK_MODEL_NAMES[0])
    )

    assert models.attempts == [FALLBACK_MODEL_NAMES[0]]


# ---------------------------------------------------------------------------
# 4. Gemini model fallback still works through the abstraction
# ---------------------------------------------------------------------------

def test_pipeline_model_fallback_through_analyzer():
    provider = FakeProvider([RuntimeError("primary boom"), VALID_JSON])
    analyzer = _analyzer_with(provider)

    result = analyzer._call_google_genai(REVIEW)

    assert isinstance(result, ReviewAnalysis)
    assert [r.model for r in provider.requests] == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]


def test_registry_chain_preserves_v1_model_order():
    assert _build_model_list(None) == [DEFAULT_MODEL_NAME, *FALLBACK_MODEL_NAMES]
    assert _build_model_list("gemini-3.5-flash-lite") == [
        "gemini-3.5-flash-lite",
        "gemini-flash-latest",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]
    chain = _build_model_list(None)
    assert len(chain) <= 5 and len(chain) == len(set(chain))


# ---------------------------------------------------------------------------
# 5. Provider errors are normalized
# ---------------------------------------------------------------------------

def test_gemini_adapter_normalizes_rate_limit(monkeypatch):
    _install_fake_genai(monkeypatch, [RuntimeError("429 Quota exceeded for generateContent")])

    response = _gemini_provider().generate(
        AIGenerationRequest(prompt="p", provider=GEMINI_PROVIDER, model=DEFAULT_MODEL_NAME)
    )

    assert response.success is False
    assert response.error_type is AIErrorType.RATE_LIMIT


def test_gateway_normalizes_unclassified_provider_exception():
    provider = FakeProvider([RuntimeError("provider exploded")])
    gateway = AIGateway(providers={provider.name: provider}, registry=model_registry)

    response = gateway.generate(
        AIGenerationRequest(prompt="p", provider="gemini", model=DEFAULT_MODEL_NAME)
    )

    assert response.success is False
    assert response.error_type is AIErrorType.UNKNOWN
    assert response.provider == "gemini"


def test_pipeline_raises_normalized_error_after_exhaustion():
    provider = FakeProvider([RuntimeError("429 Quota exceeded for generateContent")])
    analyzer = _analyzer_with(provider)

    with pytest.raises(AIProviderError) as excinfo:
        analyzer._call_google_genai(REVIEW)

    assert excinfo.value.error_type is AIErrorType.RATE_LIMIT
    assert len(provider.requests) == 5


def test_pipeline_empty_responses_do_not_become_success():
    provider = FakeProvider([""])
    analyzer = _analyzer_with(provider)

    with pytest.raises(RuntimeError, match="Empty response"):
        analyzer._call_google_genai(REVIEW)
    assert len(provider.requests) == 5


# ---------------------------------------------------------------------------
# 6. Gateway correctly invokes the selected provider
# ---------------------------------------------------------------------------

def test_gateway_routes_to_selected_provider():
    gemini = FakeProvider(["from-gemini"], name="gemini")
    openai = FakeProvider(["from-openai"], name="openai-compatible")
    gateway = AIGateway(providers={gemini.name: gemini, openai.name: openai})

    response = gateway.generate(
        AIGenerationRequest(prompt="p", provider="openai-compatible")
    )

    assert response.content == "from-openai"
    assert gemini.requests == []
    assert len(openai.requests) == 1


def test_gateway_uses_sole_provider_when_none_selected():
    provider = FakeProvider(["only"])
    gateway = AIGateway(providers={provider.name: provider}, registry=model_registry)

    response = gateway.generate(AIGenerationRequest(prompt="p"))

    assert response.content == "only"


# ---------------------------------------------------------------------------
# 7. Invalid provider/model configuration fails safely
# ---------------------------------------------------------------------------

def test_unknown_provider_fails_safely():
    provider = FakeProvider(["x"])
    gateway = AIGateway(providers={provider.name: provider}, registry=model_registry)

    with pytest.raises(UnknownProviderError) as excinfo:
        gateway.generate(AIGenerationRequest(prompt="p", provider="does-not-exist"))
    assert excinfo.value.error_type is AIErrorType.CONFIGURATION


def test_unknown_model_fails_safely():
    provider = FakeProvider(["x"])
    gateway = AIGateway(providers={provider.name: provider}, registry=model_registry)

    with pytest.raises(ModelNotAvailableError):
        gateway.generate(
            AIGenerationRequest(prompt="p", provider="gemini", model="not-a-real-model")
        )
    assert provider.requests == []


def test_disabled_model_fails_safely():
    registry = ModelRegistry(
        [
            ModelSpec(
                provider="gemini",
                model="disabled-model",
                enabled=False,
                is_default_primary=True,
            )
        ]
    )
    provider = FakeProvider(["x"])
    gateway = AIGateway(providers={provider.name: provider}, registry=registry)

    with pytest.raises(ModelNotAvailableError):
        gateway.generate(
            AIGenerationRequest(prompt="p", provider="gemini", model="disabled-model")
        )
    assert provider.requests == []


def test_missing_sdk_is_not_swallowed_by_the_gateway(monkeypatch):
    # sys.modules["google"] = None makes "from google import genai" raise ImportError.
    monkeypatch.setitem(sys.modules, "google", None)
    gateway = AIGateway(
        providers={GEMINI_PROVIDER: _gemini_provider()},
        registry=model_registry,
    )

    with pytest.raises(ImportError):
        gateway.generate(
            AIGenerationRequest(prompt="p", provider=GEMINI_PROVIDER, model=DEFAULT_MODEL_NAME)
        )


# ---------------------------------------------------------------------------
# 8. Existing structured output validation still works
# ---------------------------------------------------------------------------

def test_structured_output_validated_through_pipeline():
    provider = FakeProvider([VALID_JSON])
    analyzer = _analyzer_with(provider)

    result = analyzer._call_google_genai(REVIEW)

    assert isinstance(result, ReviewAnalysis)
    # The structured-output schema was carried on the provider-neutral request.
    assert provider.requests[0].response_schema is ReviewAnalysis
    assert provider.requests[0].requires_structured_output is True
    ReviewAnalysis.model_validate(result.model_dump())


def test_invalid_schema_falls_back_to_next_model():
    invalid = json.dumps({"sentiment": "happy", "rating": 99, "rating_source": "not_found"})
    provider = FakeProvider([invalid, VALID_JSON])
    analyzer = _analyzer_with(provider)

    result = analyzer._call_google_genai(REVIEW)

    assert result.sentiment == "positive"
    assert [r.model for r in provider.requests] == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]


# ---------------------------------------------------------------------------
# 9. Existing evidence grounding still works
# ---------------------------------------------------------------------------

def test_evidence_grounding_runs_after_generation():
    payload = {
        **VALID_PAYLOAD,
        "pros": [
            {"point": "All-day battery", "evidence": "The battery lasts all day"},
            {"point": "Waterproof", "evidence": "The phone is fully waterproof"},
        ],
    }
    provider = FakeProvider([json.dumps(payload)])
    analyzer = _analyzer_with(provider)

    result = analyzer._call_google_genai(REVIEW)

    assert [p.point for p in result.pros] == ["All-day battery"]
    assert all("waterproof" not in p.evidence.lower() for p in result.pros)


# ---------------------------------------------------------------------------
# Registry metadata (foundation for future routing)
# ---------------------------------------------------------------------------

def test_registry_holds_expected_metadata():
    spec = model_registry.get(GEMINI_PROVIDER, DEFAULT_MODEL_NAME)
    assert spec is not None
    assert spec.enabled is True
    assert spec.supports_structured_output is True
    assert spec.is_default_primary is True
    # V2-P6: verified pricing/context (official docs, ADR-008) replaces the
    # earlier "unset rather than inventing values" state for this model.
    # gemini-3.8-flash: $0.75/$3.75 per 1M input/output -> per-1K below.
    assert spec.estimated_cost_per_1k_input == 0.00075
    assert spec.estimated_cost_per_1k_output == 0.00375
    assert spec.context_window == 1_000_000
    assert spec.free_tier is True
    # Unverified models keep None — never an invented number.
    unverified = model_registry.get(GEMINI_PROVIDER, "gemini-3.6-flash")
    assert unverified is not None
    assert unverified.estimated_cost_per_1k_input is None
    assert unverified.estimated_cost_per_1k_output is None
    assert unverified.context_window is None


def test_registry_enabled_only_filter():
    registry = ModelRegistry(
        [
            ModelSpec(provider="gemini", model="on", priority=0),
            ModelSpec(provider="gemini", model="off", priority=1, enabled=False),
        ]
    )
    assert [s.model for s in registry.list_provider("gemini", enabled_only=True)] == ["on"]
    assert {s.model for s in registry.list_provider("gemini", enabled_only=False)} == {"on", "off"}
