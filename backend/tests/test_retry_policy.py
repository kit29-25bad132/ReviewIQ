"""V2-P7 tests: application-level bounded retry (retry != fallback).

Fully offline and deterministic: fake gateways/providers, injected sleep and
RNG, no network, no real waiting. Categories A-Z mirror the P7 test plan.
"""

import datetime
import io
import json
import logging
import random
import sys
import urllib.error
from email.utils import format_datetime, parsedate_to_datetime
from typing import List
from unittest import mock

import pytest

from models.review import ReviewAnalysis
from services.ai.contracts import AIGenerationRequest, AIResponse
from services.ai.errors import AIErrorType, AIProviderError
from services.ai.gateway import AIGateway
from services.ai.providers import openai_compat
from services.ai.providers.gemini import GeminiProvider
from services.ai.providers.groq import GroqProvider
from services.ai.providers.openai_compat import (
    ChatCompletionResult,
    OpenAICompatError,
    _parse_retry_after,
    chat_completion_with_json_fallback,
)
from services.ai.registry import (
    DEFAULT_MODEL_NAME,
    GEMINI_PROVIDER,
    GROQ_MODEL_NAMES,
    model_registry,
)
from services.ai.retry_policy import (
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_JITTER,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_DELAY_SECONDS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    RetryPolicy,
    compute_delay,
    generate_with_retry,
    is_retryable,
    resolve_request_timeout,
    resolve_retry_policy,
)
from services.ai_analyzer import AIAnalyzerService
from services.gemini_summary_service import gemini_summary_service
from services.rag.config import RAGConfig
from services.rag.retrieval import RagRetrievalService
from tests.test_ai_foundation import FakeProvider
from tests.test_rag_analysis_integration import (
    CONTEXT_REVIEW_TEXT,
    REVIEW as RAG_REVIEW,
    _result,
    _ScriptedSearch,
)

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

class _Gateway:
    """Scripted single-target gateway: each call consumes one script entry
    (the last entry repeats). Never performs I/O."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: List[AIGenerationRequest] = []

    def generate(self, request: AIGenerationRequest) -> AIResponse:
        self.calls.append(request)
        step = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(request)
        return step


class _SleepRecorder:
    def __init__(self):
        self.delays: List[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def _fail(error_type, *, retry_after=None):
    return AIResponse.failure(
        provider="gemini",
        model="m",
        error_type=error_type,
        error_message="provider failure",
        retry_after_seconds=retry_after,
    )


def _ok():
    return AIResponse(content="{}", provider="gemini", model="m")


def _request():
    return AIGenerationRequest(prompt="p", provider="gemini", model="m")


def _policy(max_attempts=2, base=1.0, max_delay=8.0, jitter=False):
    return RetryPolicy(
        max_attempts=max_attempts,
        base_delay_seconds=base,
        max_delay_seconds=max_delay,
        jitter=jitter,
    )


def _enable_retry(monkeypatch, max_attempts=2):
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", str(max_attempts))
    monkeypatch.setenv("RETRY_BASE_DELAY_SECONDS", "0")
    monkeypatch.setenv("RETRY_MAX_DELAY_SECONDS", "8")
    monkeypatch.setenv("RETRY_JITTER", "false")


def _gateway(providers):
    return AIGateway(
        providers=providers, registry=model_registry, default_provider=GEMINI_PROVIDER
    )


def _analyzer(providers):
    return AIAnalyzerService(api_key="test-key-not-real", gateway=_gateway(providers))


# ---------------------------------------------------------------------------
# A. Policy defaults
# ---------------------------------------------------------------------------

def test_policy_defaults():
    policy = RetryPolicy()
    assert policy.max_attempts == DEFAULT_MAX_ATTEMPTS == 2
    assert policy.base_delay_seconds == DEFAULT_BASE_DELAY_SECONDS == 0.5
    assert policy.max_delay_seconds == DEFAULT_MAX_DELAY_SECONDS == 8.0
    assert policy.jitter is DEFAULT_JITTER is True
    assert policy.max_retries == 1


def test_resolve_retry_policy_defaults_and_override():
    assert resolve_retry_policy({}) == RetryPolicy()
    policy = resolve_retry_policy(
        {
            "RETRY_MAX_ATTEMPTS": "3",
            "RETRY_BASE_DELAY_SECONDS": "0.25",
            "RETRY_MAX_DELAY_SECONDS": "4",
            "RETRY_JITTER": "false",
        }
    )
    assert policy.max_attempts == 3
    assert policy.base_delay_seconds == 0.25
    assert policy.max_delay_seconds == 4.0
    assert policy.jitter is False


def test_resolve_retry_policy_invalid_configuration_is_safe(caplog):
    with caplog.at_level(logging.WARNING, logger="services.ai.retry_policy"):
        policy = resolve_retry_policy(
            {
                "RETRY_MAX_ATTEMPTS": "abc",
                "RETRY_BASE_DELAY_SECONDS": "-2",
                "RETRY_MAX_DELAY_SECONDS": "nope",
                "RETRY_JITTER": "maybe",
            }
        )
    assert policy.max_attempts == DEFAULT_MAX_ATTEMPTS
    assert policy.base_delay_seconds == 0.0
    assert policy.max_delay_seconds == DEFAULT_MAX_DELAY_SECONDS
    assert policy.jitter is DEFAULT_JITTER


def test_policy_clamps_negative_and_zero_configuration():
    policy = RetryPolicy(
        max_attempts=0, base_delay_seconds=-1, max_delay_seconds=-5, jitter=True
    )
    assert policy.max_attempts == 1
    assert policy.base_delay_seconds == 0.0
    assert policy.max_delay_seconds == 0.0


def test_resolve_request_timeout_default_and_invalid():
    assert resolve_request_timeout({}) == DEFAULT_REQUEST_TIMEOUT_SECONDS == 30.0
    assert resolve_request_timeout({"AI_REQUEST_TIMEOUT_SECONDS": "12.5"}) == 12.5
    assert resolve_request_timeout({"AI_REQUEST_TIMEOUT_SECONDS": "0"}) == 30.0
    assert resolve_request_timeout({"AI_REQUEST_TIMEOUT_SECONDS": "-3"}) == 30.0
    assert resolve_request_timeout({"AI_REQUEST_TIMEOUT_SECONDS": "abc"}) == 30.0


# ---------------------------------------------------------------------------
# B. Retry classification
# ---------------------------------------------------------------------------

def test_is_retryable_only_rate_limit_timeout_transient():
    assert is_retryable(AIErrorType.RATE_LIMIT) is True
    assert is_retryable(AIErrorType.TIMEOUT) is True
    assert is_retryable(AIErrorType.TRANSIENT) is True
    for error_type in (
        AIErrorType.AUTHENTICATION,
        AIErrorType.CONFIGURATION,
        AIErrorType.MODEL_UNAVAILABLE,
        AIErrorType.INVALID_REQUEST,
        AIErrorType.INVALID_RESPONSE,
        AIErrorType.UNKNOWN,
        None,
    ):
        assert is_retryable(error_type) is False


# ---------------------------------------------------------------------------
# C. Max-attempt semantics
# ---------------------------------------------------------------------------

def test_max_attempts_counts_total_attempts_and_retries_same_target():
    gateway = _Gateway([_fail(AIErrorType.TRANSIENT), _fail(AIErrorType.TRANSIENT), _ok()])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=3, base=1.0), sleep=sleep
    )
    assert response.success is True
    assert len(gateway.calls) == 3
    # Same provider/model repeated every attempt (never another target).
    assert {(r.provider, r.model) for r in gateway.calls} == {("gemini", "m")}
    assert sleep.delays == [1.0, 2.0]
    assert response.metadata["retry_attempts"] == 3
    assert response.metadata["retry_count"] == 2


def test_max_attempts_one_means_no_retry():
    gateway = _Gateway([_fail(AIErrorType.TRANSIENT), _ok()])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=1), sleep=sleep
    )
    assert response.success is False
    assert len(gateway.calls) == 1
    assert sleep.delays == []


# ---------------------------------------------------------------------------
# D. Exponential backoff
# ---------------------------------------------------------------------------

def test_exponential_backoff_values_and_cap():
    policy = _policy(base=0.5, max_delay=8.0, jitter=False)
    assert compute_delay(policy, 0) == 0.5
    assert compute_delay(policy, 1) == 1.0
    assert compute_delay(policy, 2) == 2.0
    assert compute_delay(policy, 3) == 4.0
    assert compute_delay(policy, 4) == 8.0
    assert compute_delay(policy, 5) == 8.0  # capped
    assert compute_delay(policy, -3) == 0.5  # negative index clamped to 0


def test_zero_base_and_zero_max_delay_are_safe():
    assert compute_delay(_policy(base=0.0, jitter=False), 0) == 0.0
    assert compute_delay(_policy(base=1.0, max_delay=0.0, jitter=False), 0) == 0.0


# ---------------------------------------------------------------------------
# E. Jitter
# ---------------------------------------------------------------------------

def test_jitter_is_bounded_and_deterministic_with_seeded_rng():
    policy = _policy(base=4.0, max_delay=8.0, jitter=True)
    first = compute_delay(policy, 0, rng=random.Random(1234))
    second = compute_delay(policy, 0, rng=random.Random(1234))
    assert 0.0 <= first <= 4.0
    assert first == second  # same seed -> identical delay


def test_jitter_disabled_is_exact():
    assert compute_delay(_policy(base=2.0, jitter=False), 0) == 2.0


# ---------------------------------------------------------------------------
# F/G. Retry-After (seconds + decimal)
# ---------------------------------------------------------------------------

def test_retry_after_seconds_is_preferred_over_backoff():
    policy = _policy(base=0.5, max_delay=8.0, jitter=False)
    assert compute_delay(policy, 0, retry_after=3.0) == 3.0


def test_retry_after_decimal_is_supported():
    policy = _policy(base=0.5, max_delay=8.0, jitter=False)
    assert compute_delay(policy, 0, retry_after=1.5) == 1.5


# ---------------------------------------------------------------------------
# H. Retry-After HTTP-date
# ---------------------------------------------------------------------------

def test_parse_retry_after_http_date():
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
    header = {"Retry-After": format_datetime(future, usegmt=True)}
    value = _parse_retry_after(header)
    assert value is not None
    assert 55.0 <= value <= 65.0


# ---------------------------------------------------------------------------
# I. Invalid Retry-After
# ---------------------------------------------------------------------------

def test_parse_retry_after_invalid_returns_none():
    assert _parse_retry_after({"Retry-After": "soon"}) is None
    assert _parse_retry_after({"Retry-After": ""}) is None
    assert _parse_retry_after({}) is None
    assert _parse_retry_after(None) is None
    # A past HTTP-date clamps to 0 (non-negative), never negative.
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
    assert _parse_retry_after({"Retry-After": format_datetime(past, usegmt=True)}) == 0.0


def test_invalid_retry_after_falls_back_to_backoff():
    policy = _policy(base=2.0, max_delay=8.0, jitter=False)
    # A non-numeric value is represented as None by the parser; explicit None
    # falls back to the computed exponential delay.
    assert compute_delay(policy, 0, retry_after=None) == 2.0


# ---------------------------------------------------------------------------
# J. Retry-After clamp
# ---------------------------------------------------------------------------

def test_retry_after_is_clamped_to_max_delay():
    policy = _policy(base=0.5, max_delay=8.0, jitter=False)
    assert compute_delay(policy, 0, retry_after=100.0) == 8.0


# ---------------------------------------------------------------------------
# K. Retry execution
# ---------------------------------------------------------------------------

def test_retry_success_repeats_same_target_then_succeeds():
    gateway = _Gateway([_fail(AIErrorType.TRANSIENT), _ok()])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=2, base=0.75), sleep=sleep
    )
    assert response.success is True
    assert len(gateway.calls) == 2
    assert sleep.delays == [0.75]
    assert response.metadata["retry_attempts"] == 2
    assert response.metadata["retry_count"] == 1
    assert response.metadata["retryable"] is False  # final outcome succeeded


# ---------------------------------------------------------------------------
# L. Retry exhaustion
# ---------------------------------------------------------------------------

def test_retry_exhaustion_returns_meaningful_last_failure():
    gateway = _Gateway([_fail(AIErrorType.RATE_LIMIT)])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=3, base=1.0), sleep=sleep
    )
    assert response.success is False
    assert response.error_type is AIErrorType.RATE_LIMIT
    assert len(gateway.calls) == 3
    assert sleep.delays == [1.0, 2.0]
    assert response.metadata["retry_attempts"] == 3
    assert response.metadata["retry_reason"] == "rate_limit"


# ---------------------------------------------------------------------------
# M. Non-retryable errors
# ---------------------------------------------------------------------------

def test_non_retryable_failures_are_not_retried():
    for error_type in (
        AIErrorType.AUTHENTICATION,
        AIErrorType.CONFIGURATION,
        AIErrorType.MODEL_UNAVAILABLE,
        AIErrorType.INVALID_REQUEST,
        AIErrorType.INVALID_RESPONSE,
        AIErrorType.UNKNOWN,
    ):
        gateway = _Gateway([_fail(error_type)])
        sleep = _SleepRecorder()
        response = generate_with_retry(
            gateway, _request(), _policy(max_attempts=5), sleep=sleep
        )
        assert response.success is False
        assert len(gateway.calls) == 1
        assert sleep.delays == []
        assert response.metadata["retryable"] is False


# ---------------------------------------------------------------------------
# N. Timeout
# ---------------------------------------------------------------------------

def test_timeout_is_retried():
    gateway = _Gateway([_fail(AIErrorType.TIMEOUT), _ok()])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=2, base=0.5), sleep=sleep
    )
    assert response.success is True
    assert len(gateway.calls) == 2


# ---------------------------------------------------------------------------
# O. Rate limit (+ Retry-After consumed)
# ---------------------------------------------------------------------------

def test_rate_limit_is_retried_and_honors_retry_after():
    gateway = _Gateway([_fail(AIErrorType.RATE_LIMIT, retry_after=4.0), _ok()])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=2, base=1.0), sleep=sleep
    )
    assert response.success is True
    assert len(gateway.calls) == 2
    assert sleep.delays == [4.0]
    assert response.metadata["retry_delay_seconds"] == 4.0


# ---------------------------------------------------------------------------
# P. Transient 5xx
# ---------------------------------------------------------------------------

def test_transient_is_retried():
    gateway = _Gateway([_fail(AIErrorType.TRANSIENT), _ok()])
    sleep = _SleepRecorder()
    response = generate_with_retry(
        gateway, _request(), _policy(max_attempts=2, base=1.0), sleep=sleep
    )
    assert response.success is True
    assert len(gateway.calls) == 2


# ---------------------------------------------------------------------------
# Q. Provider fallback after retry exhaustion
# ---------------------------------------------------------------------------

def test_provider_fallback_after_retry_exhaustion(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=2)
    gemini = FakeProvider([RuntimeError("service overloaded")], name="gemini")
    groq = FakeProvider([VALID_JSON], name="groq")
    analyzer = _analyzer({"gemini": gemini, "groq": groq})

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    # Every Gemini model retried once (5 models x 2 attempts) before fallback.
    assert len(gemini.requests) == 10
    assert len(groq.requests) == 1


def test_authentication_skips_without_retry(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=5)

    def _auth_failure(request):
        return AIResponse.failure(
            provider=request.provider,
            model=request.model,
            error_type=AIErrorType.AUTHENTICATION,
            error_message="401 unauthorized",
        )

    gemini = FakeProvider([_auth_failure], name="gemini")
    analyzer = _analyzer({"gemini": gemini})
    with pytest.raises(AIProviderError):
        analyzer.analyze_review(REVIEW)
    # Non-retryable -> exactly one Gemini call, provider skip preserved.
    assert len(gemini.requests) == 1


# ---------------------------------------------------------------------------
# R. Successful retry prevents fallback
# ---------------------------------------------------------------------------

def test_successful_retry_prevents_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=2)
    gemini = FakeProvider([RuntimeError("service overloaded"), VALID_JSON], name="gemini")
    groq = FakeProvider([VALID_JSON], name="groq")
    analyzer = _analyzer({"gemini": gemini, "groq": groq})

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    assert len(gemini.requests) == 2
    assert groq.requests == []


# ---------------------------------------------------------------------------
# S. RAG executes once across retries
# ---------------------------------------------------------------------------

def test_rag_retrieval_runs_once_across_retries(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=2)
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    search = _ScriptedSearch(results=(_result("ctx-1", CONTEXT_REVIEW_TEXT, 0.9),))
    service = RagRetrievalService(config, search_service=search)

    gemini = FakeProvider([RuntimeError("transient provider failure"), VALID_JSON], name="gemini")
    analyzer = AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=_gateway({"gemini": gemini}),
        rag_service=service,
    )

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    # Retrieval ran exactly once; the retry reused the same context.
    assert len(search.calls) == 1
    assert len(gemini.requests) == 2
    prompts = [r.prompt for r in gemini.requests]
    assert prompts[0] == prompts[1]


# ---------------------------------------------------------------------------
# T. Product summary retry
# ---------------------------------------------------------------------------

def test_product_summary_retries_same_target(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=2)
    gemini = FakeProvider([RuntimeError("service overloaded"), SUMMARY_JSON], name="gemini")
    groq = FakeProvider([SUMMARY_JSON], name="groq")
    monkeypatch.setattr(
        "services.gemini_summary_service.analyzer_service._gateway",
        _gateway({"gemini": gemini, "groq": groq}),
    )

    result = gemini_summary_service._generate_summary("prompt")

    assert result.summary == "Customer feedback highlights battery performance."
    assert len(gemini.requests) == 2  # original + one retry, same target
    assert groq.requests == []


# ---------------------------------------------------------------------------
# U. No secret leakage
# ---------------------------------------------------------------------------

def test_retry_logs_and_metadata_are_secret_free(caplog):
    gateway = _Gateway([_fail(AIErrorType.TRANSIENT), _ok()])
    request = AIGenerationRequest(
        prompt="PROMPT_SUPERSECRET_VALUE",
        provider="gemini",
        model="m",
        metadata={"task": "review_analysis"},
    )
    with caplog.at_level(logging.INFO, logger="services.ai.retry_policy"):
        response = generate_with_retry(
            gateway, request, _policy(base=1.0), sleep=_SleepRecorder()
        )
    log_text = " ".join(record.getMessage() for record in caplog.records)
    assert "PROMPT_SUPERSECRET_VALUE" not in log_text
    assert "Authorization" not in log_text
    assert "sk-" not in log_text
    serialized = json.dumps(response.metadata)
    assert "PROMPT_SUPERSECRET_VALUE" not in serialized
    for key in response.metadata:
        lowered = key.lower()
        assert "secret" not in lowered
        assert "authorization" not in lowered
        assert "prompt" not in lowered


# ---------------------------------------------------------------------------
# V. Gateway remains single-shot
# ---------------------------------------------------------------------------

def test_gateway_remains_single_shot():
    provider = FakeProvider(["placeholder"], name="gemini")
    gateway = _gateway({"gemini": provider})
    gateway.generate(
        AIGenerationRequest(prompt="p", provider="gemini", model=DEFAULT_MODEL_NAME)
    )
    assert len(provider.requests) == 1


def test_retry_helper_gateway_call_count_is_attempts_only():
    gateway = _Gateway([_fail(AIErrorType.UNKNOWN)])
    generate_with_retry(gateway, _request(), _policy(max_attempts=4))
    # Non-retryable -> exactly one gateway invocation; the helper never
    # multiplies calls beyond max_attempts.
    assert len(gateway.calls) == 1


# ---------------------------------------------------------------------------
# W/X. Gemini timeout + SDK retry disabled
# ---------------------------------------------------------------------------

def _install_capturing_genai(monkeypatch):
    captured = {}

    class _Models:
        def generate_content(self, model, contents, config):
            return mock.MagicMock(text="{}")

    class _Client:
        def __init__(self, api_key, http_options=None):
            captured["api_key"] = api_key
            captured["http_options"] = http_options
            self.models = _Models()

    def _client(api_key, http_options=None, **kwargs):
        captured["client_kwargs"] = kwargs
        captured["http_options"] = http_options
        return _Client(api_key, http_options)

    def _http_options(**kwargs):
        captured["http_options_kwargs"] = kwargs
        return kwargs

    fake_genai = mock.MagicMock()
    fake_genai.Client = _client
    fake_types = mock.MagicMock()
    fake_types.HttpOptions = _http_options
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    return captured


def test_gemini_adapter_applies_request_timeout(monkeypatch):
    captured = _install_capturing_genai(monkeypatch)
    provider = GeminiProvider(api_key_provider=lambda: "test-key")
    provider.generate(
        AIGenerationRequest(prompt="p", model=DEFAULT_MODEL_NAME, timeout_seconds=12.5)
    )
    # google-genai HttpOptions.timeout is milliseconds.
    assert captured["http_options_kwargs"] == {"timeout": 12500}


def test_gemini_adapter_uses_default_timeout_when_unset(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "30")
    captured = _install_capturing_genai(monkeypatch)
    provider = GeminiProvider(api_key_provider=lambda: "test-key")
    provider.generate(AIGenerationRequest(prompt="p", model=DEFAULT_MODEL_NAME))
    assert captured["http_options_kwargs"] == {"timeout": 30000}


def test_gemini_adapter_never_enables_sdk_retry(monkeypatch):
    captured = _install_capturing_genai(monkeypatch)
    provider = GeminiProvider(api_key_provider=lambda: "test-key")
    provider.generate(
        AIGenerationRequest(prompt="p", model=DEFAULT_MODEL_NAME, timeout_seconds=5)
    )
    assert "retry_options" not in captured["http_options_kwargs"]
    assert "retry_options" not in captured["client_kwargs"]


# ---------------------------------------------------------------------------
# Y. OpenAI-compatible Retry-After extraction
# ---------------------------------------------------------------------------

def _http_error(code, headers, body=b"{}"):
    return urllib.error.HTTPError("https://example.invalid", code, "err", headers, io.BytesIO(body))


def test_openai_compat_extracts_integer_retry_after(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise _http_error(429, {"Retry-After": "7"}, b'{"error":{"message":"rate limited"}}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = GroqProvider(api_key_provider=lambda: "k").generate(
        AIGenerationRequest(prompt="p", model=GROQ_MODEL_NAMES[0])
    )
    assert response.success is False
    assert response.error_type is AIErrorType.RATE_LIMIT
    assert response.retry_after_seconds == 7.0


def test_openai_compat_extracts_decimal_and_http_date_retry_after(monkeypatch):
    def decimal_urlopen(request, timeout=None):
        raise _http_error(503, {"Retry-After": "1.5"}, b'{"error":{"message":"unavailable"}}')

    monkeypatch.setattr("urllib.request.urlopen", decimal_urlopen)
    decimal_response = GroqProvider(api_key_provider=lambda: "k").generate(
        AIGenerationRequest(prompt="p", model=GROQ_MODEL_NAMES[0])
    )
    assert decimal_response.retry_after_seconds == 1.5

    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)

    def date_urlopen(request, timeout=None):
        raise _http_error(
            429,
            {"Retry-After": format_datetime(future, usegmt=True)},
            b'{"error":{"message":"rate limited"}}',
        )

    monkeypatch.setattr("urllib.request.urlopen", date_urlopen)
    date_response = GroqProvider(api_key_provider=lambda: "k").generate(
        AIGenerationRequest(prompt="p", model=GROQ_MODEL_NAMES[0])
    )
    assert date_response.retry_after_seconds is not None
    assert 55.0 <= date_response.retry_after_seconds <= 65.0


def test_openai_compat_invalid_retry_after_is_none(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise _http_error(429, {"Retry-After": "not-a-number"}, b'{"error":{"message":"x"}}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = GroqProvider(api_key_provider=lambda: "k").generate(
        AIGenerationRequest(prompt="p", model=GROQ_MODEL_NAMES[0])
    )
    assert response.retry_after_seconds is None


# ---------------------------------------------------------------------------
# Z. Existing response_format compatibility retry remains intact
# ---------------------------------------------------------------------------

def test_response_format_compatibility_retry_still_intact(monkeypatch):
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
