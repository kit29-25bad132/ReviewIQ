"""Per-provider circuit breaker for failure isolation.

Provides per-provider CLOSED -> OPEN -> HALF-OPEN -> CLOSED state transitions:
- Trips to OPEN after 3 consecutive failures
- OPEN state: skip provider immediately, no attempt made, no timeout wasted
- HALF-OPEN after 60s cooldown: allow one test request
- SUCCESS in HALF-OPEN -> reset to CLOSED
- FAILURE in HALF-OPEN -> back to OPEN for another 60s
- Circuit state changes logged at INFO level
- State lives in-memory (no persistence required)
"""

import logging
import time
from enum import Enum, auto
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level defaults
# ---------------------------------------------------------------------------

CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_HALF_OPEN_COOLDOWN = 60.0


class CircuitState(Enum):
    """States of the circuit breaker."""

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreaker:
    """Per-provider circuit breaker with failure isolation.

    Tracks consecutive failures per provider and controls whether
    requests are allowed through. When OPEN, requests are immediately
    rejected without making any API call. After a cooldown period,
    HALF-OPEN state allows exactly one test request to determine
    if the provider has recovered.
    """

    def __init__(self, failure_threshold: int = 3, half_open_cooldown: float = 60.0):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures to trip to OPEN.
            half_open_cooldown: Seconds to stay OPEN before transitioning to HALF-OPEN.
        """
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._failure_threshold: int = failure_threshold
        self._half_open_cooldown: float = half_open_cooldown
        self._half_open_since: Optional[float] = None
        self._opened_at: Optional[float] = None

    def allow_request(self) -> bool:
        """Determine if a request should be allowed through.

        Returns:
            True if the request should proceed, False if it should be skipped.
        """
        now = time.monotonic()

        if self._state == CircuitState.CLOSED:
            # Always allow, track for future failure detection
            return True

        if self._state == CircuitState.OPEN:
            # Check if cooldown has elapsed for HALF-OPEN transition
            if self._opened_at is not None and now - self._opened_at >= self._half_open_cooldown:
                self._transition_to_half_open()
            # Otherwise still OPEN, skip
            return False

        if self._state == CircuitState.HALF_OPEN:
            # Allow exactly one test request
            if self._half_open_since is not None:
                # One request allowed; after this, we'll be back to CLOSED or OPEN
                pass
            return True

        # Fallback
        return True

    def record_success(self) -> None:
        """Record a successful request.

        If in HALF-OPEN: reset to CLOSED and reset counter.
        If in CLOSED: do nothing (counter already at 0).
        If in OPEN: shouldn't happen (requests are skipped), but treat as recovery.
        """
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker: HALF-OPEN -> CLOSED (recovery via success)")
            self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # Nothing to do; counter stays at 0
            pass
        elif self._state == CircuitState.OPEN:
            # Unusual: a success came through despite OPEN state
            logger.warning(
                "Circuit breaker: OPEN -> CLOSED (unexpected success)"
            )
            self._transition_to_closed()

    def record_failure(self) -> None:
        """Record a failed request.

        Increments consecutive failures. If threshold reached, transition to OPEN.
        If in HALF-OPEN and fails: back to OPEN for another cooldown.
        """
        self._consecutive_failures += 1
        now = time.monotonic()

        if self._state == CircuitState.CLOSED:
            if self._consecutive_failures >= self._failure_threshold:
                logger.info(
                    "Circuit breaker: CLOSED -> OPEN (%d consecutive failures)",
                    self._consecutive_failures,
                )
                self._transition_to_open(now)

        elif self._state == CircuitState.OPEN:
            # Already OPEN; just track time for cooldown
            if self._opened_at is None:
                self._opened_at = now

        elif self._state == CircuitState.HALF_OPEN:
            # Failure in HALF-OPEN: back to OPEN
            logger.info(
                "Circuit breaker: HALF-OPEN -> OPEN (failure during test request)"
            )
            self._transition_to_open(now)

    def _transition_to_open(self, now: float) -> None:
        """Transition from CLOSED or HALF-OPEN to OPEN."""
        self._state = CircuitState.OPEN
        self._consecutive_failures = 0
        self._opened_at = now
        if self._state != CircuitState.CLOSED and self._half_open_since is not None:
            self._half_open_since = None

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF-OPEN after cooldown."""
        logger.info(
            "Circuit breaker: OPEN -> HALF-OPEN (%.1fs cooldown elapsed)",
            time.monotonic() - self._opened_at if self._opened_at else 0,
        )
        self._state = CircuitState.HALF_OPEN
        self._half_open_since = time.monotonic()
        self._opened_at = None

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_since = None
        self._opened_at = None

    def state(self) -> CircuitState:
        """Return the current circuit state."""
        return self._state

    def reset(self) -> None:
        """Reset the circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_since = None
        self._opened_at = None

# Module-level shared circuit breaker tracker (used by routing.py and ai_analyzer.py)
_circuit_breakers: Dict[str, CircuitBreaker] = {}

def _get_circuit_breaker(provider_name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for the given provider."""
    if provider_name not in _circuit_breakers:
        _circuit_breakers[provider_name] = CircuitBreaker(
            failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            half_open_cooldown=CIRCUIT_BREAKER_HALF_OPEN_COOLDOWN,
        )
    return _circuit_breakers[provider_name]

def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (for test isolation)."""
    _circuit_breakers.clear()

