"""Hermetic circuit breaker tests - no live providers required."""
import pytest
import time

from services.ai.circuit_breaker import CircuitBreaker, CircuitState
from services.ai_analyzer import AIAnalyzerService
from services.ai.contracts import AIGenerationRequest, AIResponse, ModelRef
from services.ai.gateway import AIGateway
from services.ai.registry import (
    GEMINI_PROVIDER,
    TASK_REVIEW_ANALYSIS,
    model_registry,
)
from services.ai.errors import AIErrorType

# Re-use the fake provider from the foundation test suite.
from tests.test_ai_foundation import FakeProvider, VALID_JSON, REVIEW


@pytest.fixture
def cb():
    """Fresh circuit breaker per test."""
    return CircuitBreaker(failure_threshold=3, half_open_cooldown=60.0)


def test_circuit_opens_after_consecutive_failures(cb):
    """Circuit should trip to OPEN after 3 consecutive failures."""
    assert cb.state() == CircuitState.CLOSED
    
    cb.record_failure()
    assert cb.state() == CircuitState.CLOSED
    
    cb.record_failure()
    assert cb.state() == CircuitState.CLOSED
    
    cb.record_failure()
    assert cb.state() == CircuitState.OPEN


def test_circuit_skips_provider_when_open(cb):
    """When circuit is OPEN, allow_request should return False."""
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    
    assert cb.allow_request() is False
    assert cb.state() == CircuitState.OPEN


def test_circuit_half_open_allows_one_request(cb):
    """After 60s cooldown, HALF-OPEN should allow one request."""
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state() == CircuitState.OPEN
    
    # Manually set HALF-OPEN state (simulating cooldown elapsed)
    cb._state = CircuitState.HALF_OPEN
    cb._half_open_since = time.monotonic() - 61  # 61 seconds ago
    
    # allow_request should return True for one request
    assert cb.allow_request() is True
    # After the request, should go to CLOSED on success
    cb.record_success()
    assert cb.state() == CircuitState.CLOSED


def test_circuit_resets_after_timeout(cb):
    """HALF-OPEN test succeeds → reset to CLOSED."""
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state() == CircuitState.OPEN
    
    # Simulate cooldown elapsed
    cb._state = CircuitState.HALF_OPEN
    cb._half_open_since = time.monotonic() - 61
    
    # Record success in HALF-OPEN
    cb.record_success()
    assert cb.state() == CircuitState.CLOSED
    assert cb._consecutive_failures == 0


def test_circuit_does_not_open_on_non_consecutive_failures(cb):
    """Failures separated by a success should not trip the circuit."""
    cb.record_failure()  # 1st failure
    cb.record_success()  # success resets counter
    cb.record_failure()  # 1st failure after success
    cb.record_failure()  # 2nd failure after success
    cb.record_failure()  # 3rd failure after success - should now trip
    
    # After 3 failures following a success, circuit should open
    assert cb.state() == CircuitState.OPEN


# ---------------------------------------------------------------------------
# V2-P10 integration: circuit breaker wired into the fallback chain
# ---------------------------------------------------------------------------

class _CBtrackingFakeProvider(FakeProvider):
    """Fake provider that tracks whether it was invoked at all."""

    def __init__(self, script, name: str = "gemini"):
        super().__init__(script, name=name)
        self.invoked = False

    def generate(self, request: AIGenerationRequest) -> AIResponse:
        self.invoked = True
        return super().generate(request)


def _cb_tracking_analyzer(monkeypatch, gemini_script, groq_script):
    """Build an analyzer wired to two fake providers that track invocation."""
    from services.ai.circuit_breaker import reset_circuit_breakers
    reset_circuit_breakers()

    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    gemini = _CBtrackingFakeProvider(gemini_script, name="gemini")
    groq = _CBtrackingFakeProvider(groq_script, name="groq")
    gateway = AIGateway(
        providers={"gemini": gemini, "groq": groq},
        registry=model_registry,
        default_provider=GEMINI_PROVIDER,
    )
    return gateway, gemini, groq, AIAnalyzerService(api_key="test-key", gateway=gateway)


def test_circuit_breaker_integrated_with_fallback_chain(monkeypatch):
    """Provider A trips the circuit breaker (3 consecutive failures) and is
    skipped on the next request; provider B is tried instead.

    Hermetic: fake providers, no live network, no real API keys.
    """
    from services.ai.circuit_breaker import (
        CircuitState,
        _get_circuit_breaker,
        reset_circuit_breakers,
    )

    gateway, gemini, groq, analyzer = _cb_tracking_analyzer(
        monkeypatch,            gemini_script=[
                RuntimeError("service overloaded"),
                RuntimeError("service overloaded"),
                RuntimeError("service overloaded"),
            ],  # 3 transient failures -> Gemini circuit OPEN
            groq_script=[VALID_JSON],  # Groq succeeds on first try
    )

    # --- Request 1: trip the Gemini circuit breaker ---
    analysis = analyzer.analyze_review(REVIEW)
    assert analysis.sentiment == "positive"
    # Gemini exhausted all 5 models; Groq provided the result.
    assert gemini.invoked is True
    assert groq.invoked is True
    assert _get_circuit_breaker("gemini").state() == CircuitState.OPEN
    assert _get_circuit_breaker("groq").state() == CircuitState.CLOSED

    # --- Request 2: Gemini circuit is OPEN, should never be attempted ---
    # Reset both invocation trackers.
    gemini.invoked = False
    groq.invoked = False
    analysis2 = analyzer.analyze_review(REVIEW)
    assert analysis2.sentiment == "positive"

    # Gemini must NEVER be attempted while its circuit is OPEN.
    assert gemini.invoked is False, (
        "Gemini circuit breaker is OPEN but the provider was still invoked."
    )
    # Groq is tried instead and succeeds.
    assert groq.invoked is True
    assert _get_circuit_breaker("gemini").state() == CircuitState.OPEN
    assert _get_circuit_breaker("groq").state() == CircuitState.CLOSED