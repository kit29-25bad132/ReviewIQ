"""V2-P11 tests: observability events and request correlation (ADR-012).

Fully offline and hermetic. Covers the P11 spec groups:

1. correlation middleware (unique per request, default "-", reset/isolated),
2. global formatter + filter carrying the correlation ID,
3. consolidated ``ai_request_outcome`` event on success (exact field set),
4. ``ai_request_outcome`` event on final failure (still emitted),
5. cache hit/miss/disabled states and the correlation ID inside the event,
6. product-summary outcome event (``task=product_summary``),
7. analysis-graph fallback INFO transition (safe fields, no raw errors),
8. ``ai_retry_exhausted`` log-only event (exhausted vs terminal),
9. secret/content scan of every new log line,
10. public API contracts unchanged (no observability fields leak),
11. emission failures never break a request.
"""

import io
import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import LOG_FORMAT, RequestCorrelationMiddleware, app
from models.ecommerce import AISummaryResponse
from models.review import ReviewAnalysis
from services.ai.contracts import AIGenerationRequest, AIResponse
from services.ai.errors import AIErrorType, AIProviderError
from services.ai.gateway import AIGateway
from services.ai.registry import GEMINI_PROVIDER, model_registry
from services.ai.retry_policy import generate_with_retry
from services.ai_analyzer import AIAnalyzerService
from services.gemini_summary_service import gemini_summary_service
from services.observability import (
    RequestIdFilter,
    current_request_id,
    reset_request_id,
    set_request_id,
)
from services.rag.config import RAGConfig
from tests.cache_fakes import (
    SUMMARY_JSON,
    VALID_ANALYSIS_JSON,
    FakeCacheStore,
    analyzer_with_cache,
    llm_cache,
)
from tests.test_ai_foundation import REVIEW, VALID_JSON, FakeProvider
from tests.test_model_configuration import _FakeResponse, _install_fake_sdk
from tests.test_retry_policy import _Gateway, _SleepRecorder, _fail, _policy

#: The ONLY fields the outcome event may ever carry (spec-approved set).
OUTCOME_FIELDS = {
    "request_id",
    "task",
    "outcome",
    "provider",
    "model",
    "fallback",
    "retry_attempts",
    "retry_count",
    "cache",
    "rag_status",
    "provider_latency_ms",
    "total_ms",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gateway(providers):
    return AIGateway(
        providers=providers, registry=model_registry, default_provider=GEMINI_PROVIDER
    )


def _analyzer(providers):
    return AIAnalyzerService(
        api_key="test-key-not-real",
        gateway=_gateway(providers),
        rag_config=RAGConfig(),  # explicit: RAG disabled for these tests
    )


def _outcome_events(caplog):
    """Parse every ``ai_request_outcome`` message into a dict of fields."""
    events = []
    for record in caplog.records:
        message = record.getMessage()
        if message.startswith("ai_request_outcome "):
            body = message[len("ai_request_outcome "):]
            events.append(dict(part.split("=", 1) for part in body.split(" ")))
    return events


def _messages(caplog, logger_name):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == logger_name
    ]


# ---------------------------------------------------------------------------
# 1. Correlation middleware
# ---------------------------------------------------------------------------

def _middleware_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestCorrelationMiddleware)

    @test_app.get("/rid")
    async def rid():
        return {"rid": current_request_id()}

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("handler exploded")

    return test_app


def test_middleware_assigns_unique_correlation_id_per_request():
    client = TestClient(_middleware_app())
    first = client.get("/rid").json()["rid"]
    second = client.get("/rid").json()["rid"]
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert re.fullmatch(r"[0-9a-f]{32}", second)
    assert first != second


def test_middleware_id_is_scoped_to_the_request_and_reset_afterwards():
    assert current_request_id() == "-"
    client = TestClient(_middleware_app())
    seen = client.get("/rid").json()["rid"]
    assert seen != "-"
    # No leakage into the caller's (or a later request's) context.
    assert current_request_id() == "-"


def test_middleware_resets_context_even_when_the_handler_raises():
    client = TestClient(_middleware_app(), raise_server_exceptions=True)
    with pytest.raises(RuntimeError):
        client.get("/boom")
    assert current_request_id() == "-"


def test_request_id_filter_defaults_and_uses_active_context():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "m", None, None)
    request_filter = RequestIdFilter()
    assert request_filter.filter(record) is True
    assert record.request_id == "-"

    token = set_request_id("0123456789abcdef0123456789abcdef")
    try:
        fresh = logging.LogRecord("t", logging.INFO, __file__, 1, "m", None, None)
        assert request_filter.filter(fresh) is True
        assert fresh.request_id == "0123456789abcdef0123456789abcdef"
    finally:
        reset_request_id(token)


# ---------------------------------------------------------------------------
# 2. Global formatter carries the correlation ID
# ---------------------------------------------------------------------------

def test_global_log_format_includes_the_correlation_id():
    assert "%(request_id)s" in LOG_FORMAT

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    probe = logging.getLogger("test.observability.rid")
    probe.handlers = [handler]
    probe.propagate = False
    probe.setLevel(logging.INFO)
    token = set_request_id("aaaabbbbccccddddeeeeffff00001111")
    try:
        probe.info("in-request line")
    finally:
        reset_request_id(token)
    probe.info("background line")

    output = stream.getvalue()
    assert "[rid=aaaabbbbccccddddeeeeffff00001111]" in output
    assert "[rid=-]" in output


def test_filter_is_installed_on_all_active_root_handlers():
    """Re-running main's install loop must attach the filter to EVERY
    active root handler (not merely instantiate the filter class)."""
    import importlib

    import main as main_module

    importlib.reload(main_module)
    root_handlers = logging.getLogger().handlers
    assert root_handlers, "root logger must have active handlers"
    missing = [
        handler
        for handler in root_handlers
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters)
    ]
    assert missing == []


def test_no_root_handler_can_format_request_id_without_the_filter():
    """Invariant: any formatter referencing %(request_id)s lives on a
    handler that carries RequestIdFilter - so no handler can raise a
    KeyError formatting a record, and none can omit a required ID."""
    for handler in logging.getLogger().handlers:
        fmt = handler.formatter._fmt if handler.formatter else None
        if fmt and "%(request_id)s" in fmt:
            assert any(
                isinstance(f, RequestIdFilter) for f in handler.filters
            ), f"handler {handler!r} formats %(request_id)s without the filter"


# ---------------------------------------------------------------------------
# 3. Outcome event — success (review analysis)
# ---------------------------------------------------------------------------

def test_outcome_event_success_carries_only_approved_fields(caplog):
    provider = FakeProvider([VALID_JSON])
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.observability"):
        result = analyzer.analyze_review(REVIEW)

    assert isinstance(result, ReviewAnalysis)
    events = _outcome_events(caplog)
    assert len(events) == 1
    event = events[0]
    assert set(event) == OUTCOME_FIELDS
    assert event["request_id"] == "-"  # no request context in this test
    assert event["task"] == "review_analysis"
    assert event["outcome"] == "success"
    assert event["provider"] == "gemini"
    assert event["model"]
    assert event["fallback"] == "False"
    assert event["retry_attempts"] == "1"
    assert event["retry_count"] == "0"
    assert event["cache"] == "disabled"  # conftest forces LLM cache off
    assert event["rag_status"] == "disabled"
    # FakeProvider does not measure latency; None, never a guessed number.
    assert event["provider_latency_ms"] == "None"
    assert float(event["total_ms"]) >= 0


def test_outcome_event_failure_is_still_emitted(caplog):
    provider = FakeProvider([RuntimeError("provider down")])
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.observability"):
        with pytest.raises(RuntimeError):
            analyzer.analyze_review(REVIEW)

    events = _outcome_events(caplog)
    assert len(events) == 1
    event = events[0]
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "review_analysis"
    assert event["outcome"] == "failure"
    assert event["provider"] == "gemini"  # last target attempted
    assert event["model"]
    assert event["cache"] == "disabled"
    assert float(event["total_ms"]) >= 0


def test_outcome_event_success_on_second_target_reports_fallback(caplog):
    provider = FakeProvider([RuntimeError("primary boom"), VALID_JSON])
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.observability"):
        analyzer.analyze_review(REVIEW)

    (event,) = _outcome_events(caplog)
    assert event["outcome"] == "success"
    assert event["fallback"] == "True"


# ---------------------------------------------------------------------------
# 4b. Fallback flag is per-target, and retry is NOT fallback
# ---------------------------------------------------------------------------

def _enable_retry(monkeypatch, max_attempts=2):
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", str(max_attempts))
    monkeypatch.setenv("RETRY_BASE_DELAY_SECONDS", "0")
    monkeypatch.setenv("RETRY_MAX_DELAY_SECONDS", "8")
    monkeypatch.setenv("RETRY_JITTER", "false")


def _rate_limited(request):
    return AIResponse.failure(
        provider=request.provider,
        model=request.model or "",
        error_type=AIErrorType.RATE_LIMIT,
        error_message="429 rate limited",
    )


def test_retry_on_the_first_target_is_not_reported_as_fallback(
    monkeypatch, caplog
):
    """fallback is evaluated per attempted target: a retry on the FIRST
    target keeps fallback=False (P7: retry != fallback), while retry
    counters report that target's real attempt counts."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=2)
    provider = FakeProvider([_rate_limited, VALID_JSON], name="gemini")
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.observability"):
        analyzer.analyze_review(REVIEW)

    (event,) = _outcome_events(caplog)
    assert event["outcome"] == "success"
    assert len(provider.requests) == 2  # original + retry, SAME target
    assert event["fallback"] == "False"
    assert event["retry_attempts"] == "2"
    assert event["retry_count"] == "1"


def test_failed_previous_target_cannot_contaminate_retry_counters(
    monkeypatch, caplog
):
    """Target 1 exhausts its retry (retry_attempts=2 recorded, then raised);
    target 2 resets the holder and raises at the gateway before producing a
    response. The final event must show target 2's state - None counters -
    never the exhausted target's numbers."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _enable_retry(monkeypatch, max_attempts=2)
    provider = FakeProvider(
        [
            _rate_limited,  # target 1, attempt 1 (retryable)
            _rate_limited,  # target 1, attempt 2 -> exhausted, then raised
            AIProviderError("bad credentials", AIErrorType.AUTHENTICATION),
        ],
        name="gemini",
    )
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.observability"):
        with pytest.raises(RuntimeError):
            analyzer.analyze_review(REVIEW)

    (event,) = _outcome_events(caplog)
    assert event["outcome"] == "failure"
    assert event["fallback"] == "True"  # past the first target
    # The last attempted target raised before any response: counters are
    # None - the previous target's "2" must not leak through.
    assert event["retry_attempts"] == "None"
    assert event["retry_count"] == "None"
    assert event["provider_latency_ms"] == "None"


def test_provider_latency_is_the_measured_provider_value_not_total(
    caplog,
):
    """provider_latency_ms is copied verbatim from the provider response's
    measured latency_ms; total_ms comes from the pipeline-wide perf_counter
    span. They are independent values with independent sources."""
    measured = 123.0

    def _measured_ok(request):
        return AIResponse(
            content=VALID_JSON,
            provider=request.provider,
            model=request.model or "",
            latency_ms=measured,
        )

    provider = FakeProvider([_measured_ok], name="gemini")
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.observability"):
        analyzer.analyze_review(REVIEW)

    (event,) = _outcome_events(caplog)
    # Exactly the response's measured value - not derived from the timer.
    assert event["provider_latency_ms"] == "123.0"
    # total_ms is an integer milliseconds span of the whole pipeline, so it
    # can never take the response's "123.0" form or be copied from it.
    assert re.fullmatch(r"\d+", event["total_ms"])
    assert int(event["total_ms"]) >= 0


# ---------------------------------------------------------------------------
# 5. Cache state + correlation ID inside the event
# ---------------------------------------------------------------------------

def test_outcome_event_reports_cache_miss_then_hit(caplog):
    store = FakeCacheStore()
    cache = llm_cache(store)
    provider = FakeProvider([VALID_ANALYSIS_JSON], name="gemini")
    analyzer = analyzer_with_cache(cache, {"gemini": provider}, rag_config=RAGConfig())

    with caplog.at_level(logging.INFO, logger="services.observability"):
        analyzer.analyze_review(REVIEW)  # miss
        analyzer.analyze_review(REVIEW)  # hit

    events = _outcome_events(caplog)
    assert len(events) == 2
    miss, hit = events
    assert miss["cache"] == "miss"
    assert miss["outcome"] == "success"
    assert hit["cache"] == "hit"
    assert hit["outcome"] == "success"
    # A hit bypasses routing entirely: no target was attempted.
    assert hit["provider"] == "None"
    assert hit["model"] == "None"
    assert hit["fallback"] == "None"
    assert hit["rag_status"] == "disabled"


def test_outcome_event_carries_the_active_correlation_id(caplog):
    provider = FakeProvider([VALID_JSON])
    analyzer = _analyzer({"gemini": provider})

    token = set_request_id("89abcdef0123456789abcdef89abcdef")
    try:
        with caplog.at_level(logging.INFO, logger="services.observability"):
            analyzer.analyze_review(REVIEW)
    finally:
        reset_request_id(token)

    (event,) = _outcome_events(caplog)
    assert event["request_id"] == "89abcdef0123456789abcdef89abcdef"


# ---------------------------------------------------------------------------
# 6. Product summary outcome event
# ---------------------------------------------------------------------------

def test_summary_outcome_event_success(monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    provider = FakeProvider([SUMMARY_JSON], name="gemini")
    monkeypatch.setattr(
        "services.gemini_summary_service.analyzer_service._gateway",
        _gateway({"gemini": provider}),
    )

    with caplog.at_level(logging.INFO, logger="services.observability"):
        summary = gemini_summary_service._generate_summary("Product: X")

    assert summary.summary
    (event,) = _outcome_events(caplog)
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "product_summary"
    assert event["outcome"] == "success"
    assert event["provider"] == "gemini"
    assert event["fallback"] == "False"
    assert event["cache"] == "disabled"
    assert event["rag_status"] == "None"  # this path has no RAG stage
    assert float(event["total_ms"]) >= 0


def test_summary_outcome_event_failure(monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    provider = FakeProvider([RuntimeError("summary provider down")], name="gemini")
    monkeypatch.setattr(
        "services.gemini_summary_service.analyzer_service._gateway",
        _gateway({"gemini": provider}),
    )

    with caplog.at_level(logging.INFO, logger="services.observability"):
        with pytest.raises(RuntimeError):
            gemini_summary_service._generate_summary("Product: X")

    (event,) = _outcome_events(caplog)
    assert event["task"] == "product_summary"
    assert event["outcome"] == "failure"
    assert event["provider"] == "gemini"


# ---------------------------------------------------------------------------
# 7. Analysis-graph fallback INFO transition
# ---------------------------------------------------------------------------

def test_graph_fallback_transition_is_logged_with_safe_fields_only(caplog):
    provider = FakeProvider([RuntimeError("primary boom"), VALID_JSON])
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.analysis_graph"):
        analyzer.analyze_review(REVIEW)

    fallbacks = [
        message
        for message in _messages(caplog, "services.analysis_graph")
        if message.startswith("Graph fallback ")
    ]
    assert len(fallbacks) == 1
    (line,) = fallbacks
    assert "from_provider=gemini" in line
    assert "from_model=" in line
    assert "to_provider=gemini" in line
    assert "to_model=" in line
    assert "error_type=" in line
    # Safe category only: the raw exception text is never logged (ADR-012).
    assert "primary boom" not in line


def test_graph_logs_no_transition_for_the_terminal_target(caplog):
    provider = FakeProvider([RuntimeError("every model failed")])
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.INFO, logger="services.analysis_graph"):
        with pytest.raises(RuntimeError):
            analyzer.analyze_review(REVIEW)

    fallbacks = [
        message
        for message in _messages(caplog, "services.analysis_graph")
        if message.startswith("Graph fallback ")
    ]
    # Intermediate transitions only; the last target has no next target.
    models_tried = len(provider.requests)
    assert len(fallbacks) == max(0, models_tried - 1)


# ---------------------------------------------------------------------------
# 8. Retry exhaustion event
# ---------------------------------------------------------------------------

def test_retry_exhaustion_is_logged_with_fixed_fields(caplog):
    gateway = _Gateway([_fail(AIErrorType.TRANSIENT)])
    request = AIGenerationRequest(prompt="p", provider="gemini", model="m")

    with caplog.at_level(logging.INFO, logger="services.ai.retry_policy"):
        response = generate_with_retry(
            gateway, request, _policy(max_attempts=2), sleep=_SleepRecorder()
        )

    assert response.success is False
    exhausted = [
        message
        for message in _messages(caplog, "services.ai.retry_policy")
        if message.startswith("ai_retry_exhausted ")
    ]
    assert len(exhausted) == 1
    (line,) = exhausted
    fields = dict(part.split("=", 1) for part in line[len("ai_retry_exhausted "):].split(" "))
    assert fields["provider"] == "gemini"
    assert fields["model"] == "m"
    assert fields["error_type"] == "transient"
    assert fields["attempt"] == "2"
    assert fields["max_attempts"] == "2"


def test_no_exhaustion_event_for_a_terminal_non_retryable_failure(caplog):
    gateway = _Gateway([_fail(AIErrorType.AUTHENTICATION)])
    request = AIGenerationRequest(prompt="p", provider="gemini", model="m")

    with caplog.at_level(logging.INFO, logger="services.ai.retry_policy"):
        response = generate_with_retry(
            gateway, request, _policy(max_attempts=2), sleep=_SleepRecorder()
        )

    assert response.success is False
    assert len(gateway.calls) == 1  # terminal: no retry attempted
    assert not any(
        message.startswith("ai_retry_exhausted ")
        for message in _messages(caplog, "services.ai.retry_policy")
    )


def test_no_exhaustion_event_when_a_retry_succeeds(caplog):
    gateway = _Gateway([_fail(AIErrorType.RATE_LIMIT), _ok_response()])
    request = AIGenerationRequest(prompt="p", provider="gemini", model="m")

    with caplog.at_level(logging.INFO, logger="services.ai.retry_policy"):
        response = generate_with_retry(
            gateway, request, _policy(max_attempts=2), sleep=_SleepRecorder()
        )

    assert response.success is True
    assert not any(
        message.startswith("ai_retry_exhausted ")
        for message in _messages(caplog, "services.ai.retry_policy")
    )


def _ok_response():
    from services.ai.contracts import AIResponse

    return AIResponse(content="{}", provider="gemini", model="m")


# ---------------------------------------------------------------------------
# 9. Secret/content scan of every new log line
# ---------------------------------------------------------------------------

def test_new_observability_logs_contain_no_content_or_secrets(caplog):
    canary = "CANARY_REVIEW_MARKER_42 " + REVIEW
    provider = FakeProvider([VALID_JSON])
    analyzer = _analyzer({"gemini": provider})

    with caplog.at_level(logging.DEBUG):
        analyzer.analyze_review(canary)

    everything = "\n".join(record.getMessage() for record in caplog.records)
    assert canary not in everything
    assert "CANARY_REVIEW_MARKER_42" not in everything
    assert "test-key-not-real" not in everything
    assert "Authorization" not in everything
    assert "sk-" not in everything
    assert "postgresql://" not in everything
    # The structured event never carries prompt/system-instruction content.
    for event in _outcome_events(caplog):
        joined = " ".join(event.values())
        assert "CANARY" not in joined
        assert "Product Review Analysis AI" not in joined


# ---------------------------------------------------------------------------
# 10. Public API contracts unchanged (no observability fields leak)
# ---------------------------------------------------------------------------

def test_public_api_contract_unchanged_by_observability(monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.setattr(_FakeResponse, "text", VALID_ANALYSIS_JSON)
    attempts: list = []
    _install_fake_sdk(monkeypatch, attempts)

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="services.observability"):
        first = client.post("/api/analyze-review", json={"review": REVIEW})
        second = client.post("/api/analyze-review", json={"review": REVIEW})

    assert first.status_code == 200
    assert second.status_code == 200
    body_first, body_second = first.json(), second.json()
    assert set(body_first) == {"success", "data", "error"}
    assert set(body_second) == {"success", "data", "error"}
    assert set(body_first["data"]) == {
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    }
    # No observability material in any response.
    for text in (first.text, second.text):
        assert "request_id" not in text
        assert "ai_request_outcome" not in text
        assert "rid=" not in text

    # Schemas unchanged.
    assert set(AISummaryResponse.model_json_schema()["properties"]) == {
        "summary",
        "common_pros",
        "common_cons",
        "key_themes",
        "source_label",
    }
    assert set(ReviewAnalysis.model_json_schema()["properties"]) == {
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    }

    # End-to-end: one outcome event per request, each with its own
    # correlation ID assigned by the middleware.
    events = _outcome_events(caplog)
    assert len(events) == 2
    first_rid, second_rid = events[0]["request_id"], events[1]["request_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", first_rid)
    assert re.fullmatch(r"[0-9a-f]{32}", second_rid)
    assert first_rid != second_rid


# ---------------------------------------------------------------------------
# 11. Emission failures never break the request
# ---------------------------------------------------------------------------

def test_outcome_emission_failure_never_breaks_the_request(monkeypatch):
    def _exploding_info(*args, **kwargs):
        raise RuntimeError("logger is broken")

    monkeypatch.setattr("services.observability.logger.info", _exploding_info)
    provider = FakeProvider([VALID_JSON])
    analyzer = _analyzer({"gemini": provider})

    result = analyzer.analyze_review(REVIEW)

    assert isinstance(result, ReviewAnalysis)
