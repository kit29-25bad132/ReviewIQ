"""V2-P7 application-level bounded retry (retry != fallback).

Reliability layer for a *single* provider/model target. It sits BELOW the
existing fallback target loop (``services/ai_analyzer.py``,
``services/gemini_summary_service.py``) and ABOVE the single-shot
``AIGateway``:

    target loop (fallback: next provider/model)
      -> generate_with_retry()   (retry: SAME provider/model)
      -> AIGateway.generate()    (single-shot)
      -> provider adapter

Retry re-attempts the *same* target; fallback advances to the *next* target.
This module never builds or reorders a chain, never calls another provider,
never touches RAG/grounding/LangGraph, and never invokes the gateway more than
once per attempt. The gateway stays single-shot (ADR-009).

Only ``RATE_LIMIT``, ``TIMEOUT`` and ``TRANSIENT`` are retryable. Credential,
configuration, model-availability, invalid-request, invalid-response and
unknown failures are terminal for retry (they advance the chain exactly as
before). ``INVALID_RESPONSE`` is deliberately not retried: a deterministic
malformed output is not expected to fix itself, and retrying it would burn
tokens for no benefit.

Everything here is dependency-free, offline and deterministic: the sleep
function, the RNG and (if needed) the clock are injectable, so tests never
wait and never hit the network.
"""

import logging
import os
import random as _random
import time
from dataclasses import dataclass
from typing import Callable, FrozenSet, Mapping, Optional

from services.ai.contracts import AIGenerationRequest, AIResponse
from services.ai.errors import AIErrorType

logger = logging.getLogger(__name__)

#: Exactly three coarse categories are safe to retry on the same target.
RETRYABLE_ERROR_TYPES: FrozenSet[AIErrorType] = frozenset(
    {
        AIErrorType.RATE_LIMIT,
        AIErrorType.TIMEOUT,
        AIErrorType.TRANSIENT,
    }
)

# Defaults (documented in backend/.env.example).
DEFAULT_MAX_ATTEMPTS = 2  # total attempts per target: original + one retry
DEFAULT_BASE_DELAY_SECONDS = 0.5
DEFAULT_MAX_DELAY_SECONDS = 8.0
DEFAULT_JITTER = True
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0

RETRY_MAX_ATTEMPTS_ENV_VAR = "RETRY_MAX_ATTEMPTS"
RETRY_BASE_DELAY_SECONDS_ENV_VAR = "RETRY_BASE_DELAY_SECONDS"
RETRY_MAX_DELAY_SECONDS_ENV_VAR = "RETRY_MAX_DELAY_SECONDS"
RETRY_JITTER_ENV_VAR = "RETRY_JITTER"
REQUEST_TIMEOUT_ENV_VAR = "AI_REQUEST_TIMEOUT_SECONDS"


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry configuration for a single provider/model target.

    ``max_attempts`` counts TOTAL attempts for one target: ``1`` means no
    retry, ``2`` means the original attempt plus one retry, ``3`` means the
    original plus two retries. Invalid (non-positive / negative) values are
    clamped to a safe minimum in ``__post_init__`` so a bad configuration can
    never create an unbounded loop or a negative delay.
    """

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS
    jitter: bool = DEFAULT_JITTER
    retryable_error_types: FrozenSet[AIErrorType] = RETRYABLE_ERROR_TYPES

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_attempts", max(1, int(self.max_attempts)))
        object.__setattr__(
            self, "base_delay_seconds", max(0.0, float(self.base_delay_seconds))
        )
        object.__setattr__(
            self, "max_delay_seconds", max(0.0, float(self.max_delay_seconds))
        )
        object.__setattr__(self, "jitter", bool(self.jitter))
        object.__setattr__(
            self,
            "retryable_error_types",
            frozenset(self.retryable_error_types or ()),
        )

    @property
    def max_retries(self) -> int:
        """Number of retries after the original attempt (>= 0)."""
        return self.max_attempts - 1

    def is_retryable(self, error_type: Optional[AIErrorType]) -> bool:
        return is_retryable(error_type, self)

    def compute_delay(
        self,
        retry_index: int,
        *,
        retry_after: Optional[float] = None,
        rng=None,
    ) -> float:
        return compute_delay(
            self, retry_index, retry_after=retry_after, rng=rng
        )


def is_retryable(
    error_type: Optional[AIErrorType], policy: Optional[RetryPolicy] = None
) -> bool:
    """True ONLY for ``RATE_LIMIT``, ``TIMEOUT`` and ``TRANSIENT``.

    Retry decisions use the classified :class:`AIErrorType` (never fragile
    string matching). ``None``/unknown/terminal categories return False.
    """
    if policy is None:
        policy = RetryPolicy()
    return error_type in policy.retryable_error_types


def compute_delay(
    policy: RetryPolicy,
    retry_index: int,
    *,
    retry_after: Optional[float] = None,
    rng=None,
) -> float:
    """Deterministic exponential backoff with optional full jitter.

    ``delay = min(base_delay_seconds * 2 ** retry_index, max_delay_seconds)``
    with ``retry_index`` starting at ``0`` for the first retry. A valid
    server-suggested ``Retry-After`` (non-negative) is preferred over the
    computed delay and clamped to ``max_delay_seconds``. Invalid values fall
    back to the computed delay. When jitter is enabled the result is a uniform
    random value in ``[0, delay]`` (full jitter). The result is always a
    finite, non-negative number, so ``max_delay=0`` / ``base_delay=0`` /
    jitter-disabled all degrade safely.
    """
    max_delay = policy.max_delay_seconds
    if max_delay <= 0:
        return 0.0

    if isinstance(retry_after, (int, float)) and not isinstance(retry_after, bool):
        if retry_after >= 0:
            delay = min(float(retry_after), max_delay)
        else:
            delay = min(policy.base_delay_seconds * (2 ** max(0, int(retry_index))), max_delay)
    else:
        index = max(0, int(retry_index))
        delay = min(policy.base_delay_seconds * (2 ** index), max_delay)

    if policy.jitter and delay > 0:
        generator = rng if rng is not None else _random
        delay = generator.uniform(0.0, delay)

    return max(0.0, min(float(delay), max_delay))


# ---------------------------------------------------------------------------
# Configuration resolution (hermetic: reads env at call time, falls back
# safely on invalid values with a server-side warning — never raises).
# ---------------------------------------------------------------------------

def _env(source: Optional[Mapping[str, str]]):
    return os.environ if source is None else source


def _parse_int(raw, default: int, minimum: int, name: str) -> int:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; using default %r.", name, raw, default)
        return default
    if value < minimum:
        logger.warning("Out-of-range %s=%r; clamping to %r.", name, raw, minimum)
        return minimum
    return value


def _parse_float(raw, default: float, minimum: float, name: str) -> float:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; using default %r.", name, raw, default)
        return default
    if value < minimum:
        logger.warning("Out-of-range %s=%r; clamping to %r.", name, raw, minimum)
        return minimum
    return value


def _parse_bool(raw, default: bool, name: str) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    logger.warning("Invalid %s=%r; using default %r.", name, raw, default)
    return default


def resolve_retry_policy(source: Optional[Mapping[str, str]] = None) -> RetryPolicy:
    """Build a :class:`RetryPolicy` from the environment (deterministic).

    Invalid/negative values fall back to defaults (or safe clamps) with a
    server-side warning only; this never raises and never blocks startup.
    """
    env = _env(source)
    return RetryPolicy(
        max_attempts=_parse_int(
            env.get(RETRY_MAX_ATTEMPTS_ENV_VAR),
            DEFAULT_MAX_ATTEMPTS,
            minimum=1,
            name=RETRY_MAX_ATTEMPTS_ENV_VAR,
        ),
        base_delay_seconds=_parse_float(
            env.get(RETRY_BASE_DELAY_SECONDS_ENV_VAR),
            DEFAULT_BASE_DELAY_SECONDS,
            minimum=0.0,
            name=RETRY_BASE_DELAY_SECONDS_ENV_VAR,
        ),
        max_delay_seconds=_parse_float(
            env.get(RETRY_MAX_DELAY_SECONDS_ENV_VAR),
            DEFAULT_MAX_DELAY_SECONDS,
            minimum=0.0,
            name=RETRY_MAX_DELAY_SECONDS_ENV_VAR,
        ),
        jitter=_parse_bool(
            env.get(RETRY_JITTER_ENV_VAR),
            DEFAULT_JITTER,
            name=RETRY_JITTER_ENV_VAR,
        ),
    )


def resolve_request_timeout(source: Optional[Mapping[str, str]] = None) -> float:
    """Resolve the unified request timeout (seconds), default 30s.

    Invalid / non-positive values fall back to the default with a
    server-side warning; never raises.
    """
    env = _env(source)
    raw = env.get(REQUEST_TIMEOUT_ENV_VAR)
    if raw is None or str(raw).strip() == "":
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s=%r; using default %r.",
            REQUEST_TIMEOUT_ENV_VAR,
            raw,
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    if value <= 0:
        logger.warning(
            "Out-of-range %s=%r; using default %r.",
            REQUEST_TIMEOUT_ENV_VAR,
            raw,
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    return value


# ---------------------------------------------------------------------------
# Execution helper
# ---------------------------------------------------------------------------

def _attach_retry_metadata(
    response: AIResponse,
    attempt: int,
    last_delay: Optional[float],
    *,
    retryable: bool,
) -> None:
    """Attach safe, internal retry metadata to an AIResponse.

    Only stable, non-sensitive values: attempt counts, retryability, the
    classified error category and the applied delay. Never keys, headers,
    prompts or review text. Never serialized into an API envelope.
    """
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    metadata["retry_attempts"] = attempt
    metadata["retry_count"] = max(0, attempt - 1)
    metadata["retryable"] = bool(retryable)
    if response.error_type is not None:
        metadata["retry_reason"] = response.error_type.value
    if last_delay is not None:
        metadata["retry_delay_seconds"] = last_delay
    response.metadata = metadata


def generate_with_retry(
    gateway,
    request: AIGenerationRequest,
    policy: Optional[RetryPolicy] = None,
    *,
    sleep: Optional[Callable[[float], None]] = None,
    rng=None,
) -> AIResponse:
    """Run ONE target through the single-shot gateway with bounded retry.

    Repeats the SAME ``request`` (same provider/model) while the classified
    failure is retryable and attempts remain, then returns the final
    ``AIResponse`` (success or the meaningful last failure). On retry
    exhaustion the caller's existing fallback loop advances to the next target
    unchanged.

    If the gateway itself raises ``AIProviderError`` (configuration/unknown
    provider/model) it propagates immediately: those are terminal, not
    retryable. ``generate_with_retry`` never builds chains, never calls another
    provider, and never invokes RAG/grounding/LangGraph.
    """
    policy = policy or resolve_retry_policy()
    sleep_fn = sleep if sleep is not None else time.sleep
    generator = rng if rng is not None else _random

    attempt = 0
    last_delay: Optional[float] = None

    while True:
        attempt += 1
        # May raise AIProviderError (terminal configuration) / ImportError:
        # let those propagate — they are not retryable failures.
        response = gateway.generate(request)

        if response.success:
            _attach_retry_metadata(response, attempt, last_delay, retryable=False)
            return response

        retryable = policy.is_retryable(response.error_type)
        if attempt >= policy.max_attempts or not retryable:
            _attach_retry_metadata(response, attempt, last_delay, retryable=retryable)
            return response

        delay = compute_delay(
            policy,
            attempt - 1,
            retry_after=getattr(response, "retry_after_seconds", None),
            rng=generator,
        )
        last_delay = delay
        # Safe server-side log only: provider/model/category/attempt/delay.
        logger.info(
            "Retrying provider=%s model=%s error_type=%s attempt=%d/%d delay=%.3fs",
            response.provider,
            response.model,
            response.error_type.value if response.error_type else "unknown",
            attempt + 1,
            policy.max_attempts,
            delay,
        )
        if delay > 0:
            sleep_fn(delay)


__all__ = [
    "DEFAULT_BASE_DELAY_SECONDS",
    "DEFAULT_JITTER",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_MAX_DELAY_SECONDS",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS",
    "RETRYABLE_ERROR_TYPES",
    "RetryPolicy",
    "compute_delay",
    "generate_with_retry",
    "is_retryable",
    "resolve_request_timeout",
    "resolve_retry_policy",
]
