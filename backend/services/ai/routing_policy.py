"""V2-P6 initial-target routing policy (routing != fallback).

Routing chooses the *initial* target for a request. Fallback (V2-P5, owned by
``services/ai/routing.py``) handles failure *after* that target fails. This
module deliberately does neither of the P5 jobs: it never builds a chain,
never reorders a chain beyond moving the selected target to the head, never
probes the network, and never inspects live provider availability.

Flow (both call sites — review analysis and product summary)::

    request
      -> build the existing P5 target chain (services/ai/routing.py)
      -> select_initial_target() picks the initial target (this module)
      -> apply_route_decision() moves it to the head, preserving the exact
         relative order of every other target
      -> the existing P5 fallback loop handles failures unchanged

Strategies:
- ``gemini_first`` (default): select the chain head. Byte-for-byte
  equivalent to P5 behavior; the existing suite passes unchanged.
- ``cost_aware`` (opt-in via ``ROUTING_STRATEGY``): select the most
  cost-effective *eligible* target from the existing chain using verified
  registry metadata only. Deterministic ranking (in order):
  1. free-tier preference (verified ``free_tier=True`` first),
  2. total verified cost (USD per 1K input + output; unknown/``None`` cost
     ranks last — never as zero),
  3. quality tier (``standard`` before ``lite`` on an equal-cost tie),
  4. priority (lower first),
  5. original chain order.

All metadata comes from the model registry and is verified/static only:
no invented prices, no invented quality or latency scores, no randomness,
no clock, no network calls. Strategy configuration errors fall back safely
to ``gemini_first`` with a server-side warning that never reaches API
clients.
"""

import logging
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from services.ai.contracts import ModelRef
from services.ai.registry import (
    QUALITY_STANDARD,
    TASK_REVIEW_ANALYSIS,
    ModelRegistry,
    model_registry,
)

logger = logging.getLogger(__name__)

# Accepted ROUTING_STRATEGY values. Anything else falls back to
# DEFAULT_STRATEGY with a server-side warning (never an API error).
STRATEGY_GEMINI_FIRST = "gemini_first"
STRATEGY_COST_AWARE = "cost_aware"
DEFAULT_STRATEGY = STRATEGY_GEMINI_FIRST
VALID_STRATEGIES = frozenset({STRATEGY_GEMINI_FIRST, STRATEGY_COST_AWARE})

ROUTING_STRATEGY_ENV_VAR = "ROUTING_STRATEGY"

#: Stable routing tier/category derived from verified ``free_tier`` metadata.
TIER_FREE = "free"
TIER_PAID = "paid"


@dataclass(frozen=True)
class RouteDecision:
    """Internal, deterministic outcome of initial-target routing.

    Safe internal values only (no keys, no raw provider text). Attached to
    server-side request metadata and logs; never exposed through
    ``AnalyzeReviewResponse``/``AISummaryResponse`` or API error payloads.
    """

    selected: ModelRef
    strategy: str
    reason: str
    # "free" | "paid" | None (None = free-tier status unverified/unknown).
    tier: Optional[str] = None


def resolve_strategy(value: Optional[str] = None) -> str:
    """Resolve a routing strategy safely.

    ``value is None`` reads ``ROUTING_STRATEGY`` from the environment at call
    time (monkeypatch/hermetic friendly). An explicit ``value`` wins over the
    environment. Empty/unset means the default; any other unrecognized value
    logs a server-side warning and falls back to ``gemini_first``.
    """
    if value is None:
        value = os.getenv(ROUTING_STRATEGY_ENV_VAR, "")
    normalized = (value or "").strip().lower()
    if normalized in VALID_STRATEGIES:
        return normalized
    if normalized:
        logger.warning(
            "Invalid %s=%r; falling back to %r.",
            ROUTING_STRATEGY_ENV_VAR,
            value,
            DEFAULT_STRATEGY,
        )
    return DEFAULT_STRATEGY


def _tier_for(spec) -> Optional[str]:
    if spec is None or spec.free_tier is None:
        return None
    return TIER_FREE if spec.free_tier else TIER_PAID


def _total_verified_cost(spec) -> float:
    """Sum of verified per-1K costs; unknown metadata ranks last (never 0)."""
    if (
        spec.estimated_cost_per_1k_input is None
        or spec.estimated_cost_per_1k_output is None
    ):
        return float("inf")
    return spec.estimated_cost_per_1k_input + spec.estimated_cost_per_1k_output


def _eligible(
    ref: ModelRef,
    registry: ModelRegistry,
    is_configured: Optional[Callable[[str], bool]],
    task: Optional[str],
):
    """Eligibility gate for cost_aware: configured, registered, enabled,
    structured-output capable, and task-capable. No network, no probing."""
    if is_configured is not None and not is_configured(ref.provider):
        return None
    spec = registry.get(ref.provider, ref.model)
    if spec is None or not spec.enabled:
        return None
    if not spec.supports_structured_output:
        return None
    if task is not None and task not in spec.capabilities:
        return None
    return spec


def select_initial_target(
    chain: Sequence[ModelRef],
    strategy: Optional[str] = None,
    *,
    registry: Optional[ModelRegistry] = None,
    is_configured: Optional[Callable[[str], bool]] = None,
    override: Optional[ModelRef] = None,
    task: Optional[str] = TASK_REVIEW_ANALYSIS,
) -> RouteDecision:
    """Choose the initial target from an already-built P5 chain.

    Args:
        chain: The P5 fallback chain (``build_target_chain`` output). This
            function never builds or regenerates a chain.
        strategy: Explicit strategy; ``None`` reads ``ROUTING_STRATEGY``.
        registry: Model metadata source (defaults to the shared registry).
        is_configured: Provider-configuration checker — reuse
            ``services.ai.routing.provider_configured_checker``. Unconfigured
            providers are excluded from cost-aware eligibility.
        override: Explicit provider/model override (the existing Gemini-
            scoped ``GEMINI_MODEL`` selection). When present in the chain it
            always wins, regardless of strategy.
        task: Capability gate for cost-aware eligibility (``None`` disables).

    Returns:
        A :class:`RouteDecision` describing the selected target, the
        strategy used, a stable reason, and the verified routing tier.
        ``ValueError`` is raised only for an empty chain (nothing to route).
    """
    targets = list(chain)
    if not targets:
        raise ValueError("Cannot route an empty target chain.")

    reg = registry if registry is not None else model_registry
    resolved = resolve_strategy(strategy)

    # Explicit override precedence: an existing explicit selection always
    # beats policy (it must actually be part of the chain to be attemptable).
    if override is not None and override in targets:
        spec = reg.get(override.provider, override.model)
        return RouteDecision(
            selected=override,
            strategy=resolved,
            reason="explicit_override",
            tier=_tier_for(spec),
        )

    if resolved == STRATEGY_COST_AWARE:
        selected, reason = _select_cost_aware(targets, reg, is_configured, task)
    else:
        # gemini_first: never reorders — the chain head is the P5 primary.
        selected, reason = targets[0], "chain_head"

    return RouteDecision(
        selected=selected,
        strategy=resolved,
        reason=reason,
        tier=_tier_for(reg.get(selected.provider, selected.model)),
    )


def _select_cost_aware(
    targets: List[ModelRef],
    registry: ModelRegistry,
    is_configured: Optional[Callable[[str], bool]],
    task: Optional[str],
):
    best: Optional[ModelRef] = None
    best_key = None
    for index, ref in enumerate(targets):
        spec = _eligible(ref, registry, is_configured, task)
        if spec is None:
            continue
        key = (
            # 1. verified free-tier preference (unverified never counts free)
            0 if spec.free_tier is True else 1,
            # 2. total verified cost (unknown ranks last, never as zero)
            _total_verified_cost(spec),
            # 3. quality tier on an equal-cost tie (standard before lite)
            0 if spec.quality_tier == QUALITY_STANDARD else 1,
            # 4. existing priority metadata
            spec.priority,
            # 5. original chain order
            index,
        )
        if best_key is None or key < best_key:
            best, best_key = ref, key

    if best is None:
        # Nothing eligible (defensive): keep the P5 head so routing can never
        # break analysis; the gateway's own validation still applies.
        return targets[0], "no_eligible_target_chain_head"
    return best, "cheapest_eligible"


def apply_route_decision(
    chain: Sequence[ModelRef], decision: RouteDecision
) -> List[ModelRef]:
    """Move ``decision.selected`` to the head of ``chain``.

    Every other target keeps its exact original relative order, so the P5
    fallback tail is preserved byte-for-byte. When the selected target is
    already the head (or is not in the chain), the order is returned
    unchanged.
    """
    targets = list(chain)
    if not targets:
        return targets
    try:
        index = targets.index(decision.selected)
    except ValueError:
        return targets
    if index == 0:
        return targets
    selected = targets.pop(index)
    targets.insert(0, selected)
    return targets


def route_metadata(decision: Optional[RouteDecision]) -> Dict[str, str]:
    """Safe internal audit fields for request metadata.

    Contains only stable routing identifiers — never API keys, provider
    secrets, raw exception text, or request data. The values ride along in
    server-side request/response metadata only; API envelopes never serialize
    them.
    """
    if decision is None:
        return {}
    return {
        "routing_strategy": decision.strategy,
        "routing_reason": decision.reason,
        "selected_provider": decision.selected.provider,
        "selected_model": decision.selected.model,
    }
