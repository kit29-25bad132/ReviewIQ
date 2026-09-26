"""V2-P6 routing policy tests: routing (initial target) != fallback (P5).

Every test here is pure/offline/deterministic: fake providers, custom
registries, no provider HTTP calls, no randomness, no clock, no live
availability probing. Sections A-I mirror the P6 test plan.
"""

import json
import logging
import socket
import urllib.request

import pytest

from services.ai.contracts import AIResponse, ModelRef
from services.ai.gateway import AIGateway
from services.ai.provider import AIProvider
from services.ai.registry import (
    DEFAULT_MODEL_NAME,
    GEMINI_PROVIDER,
    GROQ_PROVIDER,
    OPENROUTER_MODEL_ROUTE,
    OPENROUTER_PROVIDER,
    QUALITY_LITE,
    QUALITY_STANDARD,
    TASK_DATASET_SUMMARY,
    TASK_REVIEW_ANALYSIS,
    ModelRegistry,
    ModelSpec,
    model_registry,
)
from services.ai.routing_policy import (
    DEFAULT_STRATEGY,
    STRATEGY_COST_AWARE,
    STRATEGY_GEMINI_FIRST,
    apply_route_decision,
    resolve_strategy,
    route_metadata,
    select_initial_target,
)
from services.ai_analyzer import AIAnalyzerService, analyzer_service
from services.gemini_summary_service import gemini_summary_service

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

# Synthetic provider/model names used by the pure policy tests so results do
# not depend on the real registry's pricing metadata.
G1 = ModelRef(provider="gemini", model="g1")
G2 = ModelRef(provider="gemini", model="g2")
G3 = ModelRef(provider="gemini", model="g3")
R1 = ModelRef(provider="groq", model="r1")
R2 = ModelRef(provider="groq", model="r2")
O1 = ModelRef(provider="openrouter", model="openrouter/free")
CHAIN6 = [G1, G2, G3, R1, R2, O1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spec(provider, model, **overrides):
    base = dict(
        provider=provider,
        model=model,
        capabilities=frozenset({TASK_REVIEW_ANALYSIS, TASK_DATASET_SUMMARY}),
        quality_tier=QUALITY_STANDARD,
        priority=0,
    )
    base.update(overrides)
    return ModelSpec(**base)


def _reg(*specs):
    return ModelRegistry(list(specs))


def _always_configured(_provider):
    return True


def _select_gemini_first(chain, registry=None, configured=None, task=None):
    return select_initial_target(
        chain,
        STRATEGY_GEMINI_FIRST,
        registry=registry,
        is_configured=configured if configured is not None else _always_configured,
        task=task,
    )


def _select_cost_aware(chain, registry, configured=None, task=None, override=None):
    return select_initial_target(
        chain,
        STRATEGY_COST_AWARE,
        registry=registry,
        is_configured=configured if configured is not None else _always_configured,
        task=task,
        override=override,
    )


class _FakeProvider(AIProvider):
    """Scripted offline provider: each call consumes one script entry (the
    last entry repeats). Never performs I/O."""

    def __init__(self, name, script):
        self.name = name
        self.script = list(script)
        self.requests = []

    def is_configured(self):
        return True

    def generate(self, request):
        self.requests.append(request)
        step = self.script[min(len(self.requests) - 1, len(self.script) - 1)]
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(request)
        return AIResponse(content=step, provider=self.name, model=request.model or "")


def _gateway(providers):
    return AIGateway(
        providers=providers, registry=model_registry, default_provider=GEMINI_PROVIDER
    )


def _analyzer(providers):
    return AIAnalyzerService(api_key="test-key-not-real", gateway=_gateway(providers))


def _multi_providers(gemini_script, groq_script=None, openrouter_script=None):
    providers = {"gemini": _FakeProvider("gemini", gemini_script)}
    if groq_script is not None:
        providers["groq"] = _FakeProvider("groq", groq_script)
    if openrouter_script is not None:
        providers["openrouter"] = _FakeProvider("openrouter", openrouter_script)
    return providers


# ---------------------------------------------------------------------------
# A. gemini_first
# ---------------------------------------------------------------------------

def test_gemini_first_selects_chain_head():
    decision = _select_gemini_first(CHAIN6)
    assert decision.selected == CHAIN6[0]
    assert decision.strategy == STRATEGY_GEMINI_FIRST
    assert decision.reason == "chain_head"


def test_gemini_first_preserves_full_chain_order():
    decision = _select_gemini_first(CHAIN6)
    reordered = apply_route_decision(CHAIN6, decision)
    assert reordered == list(CHAIN6)
    assert [t.model for t in reordered] == ["g1", "g2", "g3", "r1", "r2", "openrouter/free"]


def test_default_strategy_is_gemini_first(monkeypatch):
    monkeypatch.delenv("ROUTING_STRATEGY", raising=False)
    assert DEFAULT_STRATEGY == STRATEGY_GEMINI_FIRST
    assert resolve_strategy(None) == STRATEGY_GEMINI_FIRST
    # With cost metadata that would prefer another target, the default still
    # picks the chain head — P5 behavior is preserved byte-for-byte.
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.001,
              estimated_cost_per_1k_output=0.001),
    )
    decision = select_initial_target(
        [G1, R1], None, registry=registry, is_configured=_always_configured
    )
    assert decision.strategy == STRATEGY_GEMINI_FIRST
    assert decision.selected == G1


# ---------------------------------------------------------------------------
# B. cost_aware eligibility + ranking
# ---------------------------------------------------------------------------

def test_cost_aware_selects_cheapest_verified_target():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=0.01,
              estimated_cost_per_1k_output=0.02, free_tier=False),
        _spec("gemini", "g2", estimated_cost_per_1k_input=0.001,
              estimated_cost_per_1k_output=0.002, free_tier=False),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.05,
              estimated_cost_per_1k_output=0.1, free_tier=False),
    )
    decision = _select_cost_aware([G1, G2, R1], registry)
    assert decision.selected == G2
    assert decision.reason == "cheapest_eligible"
    assert decision.tier == "paid"


def test_cost_aware_prefers_free_tier_over_cheaper_paid_target():
    # Free-tier model has a *higher* listed price than the paid model, but
    # verified free-tier preference ranks first.
    registry = _reg(
        _spec("groq", "r1", estimated_cost_per_1k_input=0.001,
              estimated_cost_per_1k_output=0.002, free_tier=False),
        _spec("gemini", "g1", estimated_cost_per_1k_input=0.5,
              estimated_cost_per_1k_output=1.0, free_tier=True),
    )
    decision = _select_cost_aware([R1, G1], registry)
    assert decision.selected == G1
    assert decision.tier == "free"


def test_cost_aware_excludes_unconfigured_provider():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=0.0,
              estimated_cost_per_1k_output=0.0, free_tier=True),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.5,
              estimated_cost_per_1k_output=0.5, free_tier=False),
    )
    configured = lambda provider: provider == GROQ_PROVIDER
    decision = _select_cost_aware([G1, R1], registry, configured=configured)
    assert decision.selected == R1
    # With the provider configured, the cheaper free target is chosen again.
    decision_configured = _select_cost_aware([G1, R1], registry)
    assert decision_configured.selected == G1


def test_cost_aware_excludes_disabled_model():
    registry = _reg(
        _spec("gemini", "g1", enabled=False,
              estimated_cost_per_1k_input=0.0, estimated_cost_per_1k_output=0.0),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.9,
              estimated_cost_per_1k_output=0.9, free_tier=False),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == R1


def test_cost_aware_excludes_model_without_structured_output():
    registry = _reg(
        _spec("gemini", "g1", supports_structured_output=False,
              estimated_cost_per_1k_input=0.0, estimated_cost_per_1k_output=0.0),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.9,
              estimated_cost_per_1k_output=0.9, free_tier=False),
    )
    decision = _select_cost_aware([G1, R1], registry, task=TASK_REVIEW_ANALYSIS)
    assert decision.selected == R1


def test_cost_aware_excludes_model_without_required_capability():
    registry = _reg(
        _spec("gemini", "g1", capabilities=frozenset({TASK_DATASET_SUMMARY}),
              estimated_cost_per_1k_input=0.0, estimated_cost_per_1k_output=0.0),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.9,
              estimated_cost_per_1k_output=0.9, free_tier=False),
    )
    decision = _select_cost_aware([G1, R1], registry, task=TASK_REVIEW_ANALYSIS)
    assert decision.selected == R1
    # The same target becomes eligible for the capability it does support.
    decision_summary = _select_cost_aware([G1, R1], registry, task=TASK_DATASET_SUMMARY)
    assert decision_summary.selected == G1


def test_cost_aware_tie_break_prefers_lower_priority():
    registry = _reg(
        _spec("gemini", "g1", priority=5, estimated_cost_per_1k_input=0.1,
              estimated_cost_per_1k_output=0.1),
        _spec("groq", "r1", priority=1, estimated_cost_per_1k_input=0.1,
              estimated_cost_per_1k_output=0.1),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == R1


def test_cost_aware_tie_break_prefers_standard_quality_on_equal_cost():
    registry = _reg(
        _spec("gemini", "g1", quality_tier=QUALITY_LITE,
              estimated_cost_per_1k_input=0.1, estimated_cost_per_1k_output=0.1),
        _spec("groq", "r1", quality_tier=QUALITY_STANDARD,
              estimated_cost_per_1k_input=0.1, estimated_cost_per_1k_output=0.1),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == R1


def test_cost_aware_tie_break_falls_back_to_original_chain_order():
    # Identical free-tier/cost/quality/priority metadata: chain order wins.
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=0.1,
              estimated_cost_per_1k_output=0.1, free_tier=True),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.1,
              estimated_cost_per_1k_output=0.1, free_tier=True),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == G1
    # Reversing the chain reverses the decision — no hidden preference.
    decision_reversed = _select_cost_aware([R1, G1], registry)
    assert decision_reversed.selected == R1


def test_cost_aware_without_eligible_target_keeps_chain_head():
    registry = _reg(_spec("gemini", "g1", enabled=False))
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == G1
    assert decision.reason == "no_eligible_target_chain_head"


# ---------------------------------------------------------------------------
# C. Override precedence
# ---------------------------------------------------------------------------

def test_explicit_override_beats_cost_aware_policy():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=9.0,
              estimated_cost_per_1k_output=9.0, free_tier=False),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.0,
              estimated_cost_per_1k_output=0.0, free_tier=True),
    )
    decision = _select_cost_aware([G1, R1], registry, override=G1)
    assert decision.selected == G1
    assert decision.reason == "explicit_override"
    # The override only moves itself; the fallback tail keeps P5 order.
    assert apply_route_decision([G1, R1], decision) == [G1, R1]


def test_override_not_present_in_chain_is_ignored():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=9.0,
              estimated_cost_per_1k_output=9.0, free_tier=False),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.0,
              estimated_cost_per_1k_output=0.0, free_tier=True),
    )
    ghost = ModelRef(provider="gemini", model="not-in-chain")
    decision = _select_cost_aware([G1, R1], registry, override=ghost)
    assert decision.selected == R1
    assert decision.reason == "cheapest_eligible"


def test_gemini_model_override_stays_gemini_scoped_under_cost_aware(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("ROUTING_STRATEGY", STRATEGY_COST_AWARE)
    providers = _multi_providers([VALID_JSON], groq_script=[VALID_JSON],
                                 openrouter_script=[VALID_JSON])
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    first = providers["gemini"].requests[0]
    # GEMINI_MODEL is the existing explicit override: it wins over the
    # cost-aware pick (which would otherwise select openrouter/free), and it
    # only reorders the Gemini-scoped primary — no new API parameter exists.
    assert first.provider == GEMINI_PROVIDER
    assert first.model == "gemini-3.5-flash"
    assert first.metadata["fallback"] is False
    assert first.metadata["routing_reason"] == "explicit_override"
    assert providers["openrouter"].requests == []


# ---------------------------------------------------------------------------
# D. Chain preservation (routing moves only the selected target)
# ---------------------------------------------------------------------------

def test_selected_target_moved_to_head_preserves_relative_order():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=False),
        _spec("gemini", "g2", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=False),
        _spec("gemini", "g3", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=False),
        _spec("groq", "r1", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=False),
        _spec("groq", "r2", estimated_cost_per_1k_input=0.0,
              estimated_cost_per_1k_output=0.0, free_tier=False),
        _spec("openrouter", "openrouter/free",
              estimated_cost_per_1k_input=0.5, estimated_cost_per_1k_output=0.5,
              free_tier=False),
    )
    decision = _select_cost_aware(CHAIN6, registry)
    assert decision.selected == R2

    reordered = apply_route_decision(CHAIN6, decision)
    assert reordered == [R2, G1, G2, G3, R1, O1]
    # Every non-selected target keeps its original relative order.
    non_selected = [t for t in reordered if t != R2]
    assert non_selected == [G1, G2, G3, R1, O1]
    # Exactly one occurrence of every target (no duplication, no loss).
    assert len(reordered) == len(CHAIN6)
    assert set(reordered) == set(CHAIN6)


def test_head_selection_returns_chain_unchanged():
    decision = _select_gemini_first(CHAIN6)
    assert apply_route_decision(CHAIN6, decision) == list(CHAIN6)
    # Same input, same object values: the result is a fresh list either way.
    assert apply_route_decision(CHAIN6, decision) is not CHAIN6


def test_apply_route_decision_with_unknown_selection_returns_unchanged():
    ghost_decision = select_initial_target(
        [G1], STRATEGY_GEMINI_FIRST, is_configured=_always_configured
    )
    assert apply_route_decision(CHAIN6, ghost_decision) == list(CHAIN6)


# ---------------------------------------------------------------------------
# E. No-network guarantee
# ---------------------------------------------------------------------------

def test_routing_policy_never_touches_the_network(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("routing policy must never make network calls")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket.socket, "connect", _boom)

    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.0,
              estimated_cost_per_1k_output=0.0, free_tier=True),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert apply_route_decision([G1, R1], decision) == [R1, G1]


# ---------------------------------------------------------------------------
# F. Invalid strategy handling
# ---------------------------------------------------------------------------

def test_invalid_strategy_falls_back_to_gemini_first(caplog):
    with caplog.at_level(logging.WARNING, logger="services.ai.routing_policy"):
        decision = select_initial_target(
            CHAIN6, "turbo", is_configured=_always_configured, task=None
        )
    assert decision.strategy == STRATEGY_GEMINI_FIRST
    assert decision.selected == CHAIN6[0]
    warnings = [r.getMessage() for r in caplog.records]
    assert any("ROUTING_STRATEGY" in w and "falling back" in w for w in warnings)


def test_invalid_env_strategy_falls_back_to_gemini_first(monkeypatch, caplog):
    monkeypatch.setenv("ROUTING_STRATEGY", "cheapest-random")
    with caplog.at_level(logging.WARNING, logger="services.ai.routing_policy"):
        decision = select_initial_target(
            CHAIN6, None, is_configured=_always_configured, task=None
        )
    assert decision.strategy == STRATEGY_GEMINI_FIRST
    assert decision.selected == CHAIN6[0]
    assert any("falling back" in r.getMessage() for r in caplog.records)


def test_resolve_strategy_accepts_valid_values_and_normalizes(monkeypatch):
    monkeypatch.delenv("ROUTING_STRATEGY", raising=False)
    assert resolve_strategy(STRATEGY_GEMINI_FIRST) == STRATEGY_GEMINI_FIRST
    assert resolve_strategy(STRATEGY_COST_AWARE) == STRATEGY_COST_AWARE
    assert resolve_strategy(" Cost_Aware ") == STRATEGY_COST_AWARE
    assert resolve_strategy("") == STRATEGY_GEMINI_FIRST
    monkeypatch.setenv("ROUTING_STRATEGY", STRATEGY_COST_AWARE)
    assert resolve_strategy(None) == STRATEGY_COST_AWARE


# ---------------------------------------------------------------------------
# G. Missing cost metadata is never ranked as zero
# ---------------------------------------------------------------------------

def test_unknown_cost_metadata_is_never_ranked_as_zero():
    registry = _reg(
        # Unknown cost: if treated as 0 it would wrongly win this ranking.
        _spec("gemini", "g1", estimated_cost_per_1k_input=None,
              estimated_cost_per_1k_output=None, free_tier=False),
        _spec("groq", "r1", estimated_cost_per_1k_input=0.0001,
              estimated_cost_per_1k_output=0.0001, free_tier=False),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == R1


def test_unknown_cost_still_loses_to_free_tier_but_ranks_by_order_am_equals():
    # All targets unknown-cost and unverified-free: ranking degrades
    # deterministically to quality -> priority -> chain order.
    registry = _reg(
        _spec("gemini", "g1", priority=1),
        _spec("groq", "r1", priority=0),
    )
    decision = _select_cost_aware([G1, R1], registry)
    assert decision.selected == R1  # lower priority wins
    assert decision.tier is None  # free-tier status unverified, not "free"


# ---------------------------------------------------------------------------
# H. OpenRouter free route
# ---------------------------------------------------------------------------

def test_openrouter_free_route_metadata_is_verified_free_opaque_route():
    spec = model_registry.get(OPENROUTER_PROVIDER, OPENROUTER_MODEL_ROUTE)
    assert spec is not None
    assert spec.free_tier is True
    assert spec.estimated_cost_per_1k_input == 0.0
    assert spec.estimated_cost_per_1k_output == 0.0
    assert spec.context_window == 200_000
    # A single opaque route, not a statically identifiable underlying model.
    openrouter_specs = model_registry.list_provider(OPENROUTER_PROVIDER)
    assert [s.model for s in openrouter_specs] == [OPENROUTER_MODEL_ROUTE]


def test_cost_aware_ranks_openrouter_free_route_as_free_zero_cost():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=0.00075,
              estimated_cost_per_1k_output=0.00375, free_tier=True),
        _spec("openrouter", "openrouter/free",
              estimated_cost_per_1k_input=0.0, estimated_cost_per_1k_output=0.0,
              free_tier=True),
    )
    decision = _select_cost_aware([G1, O1], registry)
    assert decision.selected == O1
    assert decision.tier == "free"
    # Selection used only registry metadata about the route itself — no
    # assumption about which underlying model the route resolves upstream.
    assert decision.reason == "cheapest_eligible"


# ---------------------------------------------------------------------------
# I. Determinism + audit metadata
# ---------------------------------------------------------------------------

def test_same_inputs_produce_identical_route_decisions():
    registry = _reg(
        _spec("gemini", "g1", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=True),
        _spec("groq", "r1", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=True),
        _spec("groq", "r2", estimated_cost_per_1k_input=1.0,
              estimated_cost_per_1k_output=1.0, free_tier=True),
        _spec("openrouter", "openrouter/free",
              estimated_cost_per_1k_input=0.5, estimated_cost_per_1k_output=0.5,
              free_tier=True),
    )
    decisions = [
        select_initial_target(
            CHAIN6, STRATEGY_COST_AWARE, registry=registry,
            is_configured=_always_configured,
        )
        for _ in range(5)
    ]
    assert all(d == decisions[0] for d in decisions)
    assert decisions[0].selected == O1  # free tier + lowest verified cost
    assert decisions[0].reason == "cheapest_eligible"


def test_route_metadata_is_stable_and_safe():
    registry = _reg(
        _spec("groq", "r1", estimated_cost_per_1k_input=0.0,
              estimated_cost_per_1k_output=0.0, free_tier=True),
    )
    decision = _select_cost_aware([R1], registry)
    metadata = route_metadata(decision)
    assert metadata == {
        "routing_strategy": STRATEGY_COST_AWARE,
        "routing_reason": "cheapest_eligible",
        "selected_provider": "groq",
        "selected_model": "r1",
    }
    # No keys, no secrets, no raw error text — safe for server-side metadata.
    assert not any("key" in k.lower() or "secret" in k.lower() for k in metadata)
    assert route_metadata(None) == {}


def test_empty_chain_raises_value_error():
    with pytest.raises(ValueError, match="empty target chain"):
        select_initial_target([], STRATEGY_GEMINI_FIRST)


# ---------------------------------------------------------------------------
# Verified registry metadata (P6 population — ADR-008)
# ---------------------------------------------------------------------------

def test_registry_holds_verified_p6_metadata():
    # Gemini: published per-1M prices converted to USD per 1K.
    flash = model_registry.get(GEMINI_PROVIDER, DEFAULT_MODEL_NAME)
    assert flash.estimated_cost_per_1k_input == 0.00075
    assert flash.estimated_cost_per_1k_output == 0.00375
    assert flash.context_window == 1_000_000
    assert flash.free_tier is True

    lite = model_registry.get(GEMINI_PROVIDER, "gemini-3.5-flash-lite")
    assert lite.estimated_cost_per_1k_input == 0.0003
    assert lite.estimated_cost_per_1k_output == 0.0025
    assert lite.context_window == 1_048_576
    assert lite.free_tier is True

    # Unverified models keep None — never invented.
    for unverified_model in ("gemini-3.6-flash", "gemini-flash-latest"):
        unverified = model_registry.get(GEMINI_PROVIDER, unverified_model)
        assert unverified.estimated_cost_per_1k_input is None
        assert unverified.estimated_cost_per_1k_output is None
        assert unverified.context_window is None

    # Groq: verified prices/context; free-tier unverified -> None.
    gpt120b = model_registry.get(GROQ_PROVIDER, "openai/gpt-oss-120b")
    assert gpt120b.estimated_cost_per_1k_input == 0.00015
    assert gpt120b.estimated_cost_per_1k_output == 0.0006
    assert gpt120b.context_window == 131_072
    assert gpt120b.free_tier is None

    gpt20b = model_registry.get(GROQ_PROVIDER, "openai/gpt-oss-20b")
    assert gpt20b.estimated_cost_per_1k_input == 0.000075
    assert gpt20b.estimated_cost_per_1k_output == 0.0003
    assert gpt20b.context_window == 131_072

    qwen = model_registry.get(GROQ_PROVIDER, "qwen/qwen3.8-27b")
    assert qwen.estimated_cost_per_1k_input == 0.0008
    assert qwen.estimated_cost_per_1k_output == 0.004
    assert qwen.context_window == 131_042


# ---------------------------------------------------------------------------
# Integration: analyzer + product summary use the same policy semantics
# ---------------------------------------------------------------------------

def test_default_strategy_keeps_p5_order_in_analyzer(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers([VALID_JSON], groq_script=[VALID_JSON],
                                 openrouter_script=[VALID_JSON])
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    first = providers["gemini"].requests[0]
    assert first.model == DEFAULT_MODEL_NAME
    assert first.metadata["fallback"] is False
    assert first.metadata["routing_strategy"] == STRATEGY_GEMINI_FIRST
    assert first.metadata["routing_reason"] == "chain_head"
    assert first.metadata["selected_provider"] == GEMINI_PROVIDER
    assert first.metadata["selected_model"] == DEFAULT_MODEL_NAME
    # Nothing else was touched: the P5 attempt sequence is unchanged.
    assert providers["groq"].requests == []
    assert providers["openrouter"].requests == []


def test_cost_aware_moves_selected_target_to_head_in_analyzer(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("ROUTING_STRATEGY", STRATEGY_COST_AWARE)
    providers = _multi_providers(
        [VALID_JSON],
        groq_script=[VALID_JSON],
        openrouter_script=[RuntimeError("service overloaded")],
    )
    analyzer = _analyzer(providers)

    analysis = analyzer.analyze_review(REVIEW)

    assert analysis.sentiment == "positive"
    # openrouter/free is the cheapest verified free target -> initial attempt.
    first = providers["openrouter"].requests[0]
    assert first.model == OPENROUTER_MODEL_ROUTE
    assert first.metadata["fallback"] is False
    assert first.metadata["routing_strategy"] == STRATEGY_COST_AWARE
    assert first.metadata["routing_reason"] == "cheapest_eligible"
    assert first.metadata["selected_provider"] == OPENROUTER_PROVIDER
    # Failure -> the existing P5 fallback tail in original relative order:
    # Gemini chain next (its head first), Groq untouched behind it.
    gemini_first = providers["gemini"].requests[0]
    assert gemini_first.model == DEFAULT_MODEL_NAME
    assert gemini_first.metadata["fallback"] is True
    assert providers["groq"].requests == []


def test_product_summary_uses_the_same_routing_policy(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("ROUTING_STRATEGY", STRATEGY_COST_AWARE)
    providers = _multi_providers(
        [SUMMARY_JSON],
        groq_script=[SUMMARY_JSON],
        openrouter_script=[RuntimeError("service overloaded")],
    )
    monkeypatch.setattr(analyzer_service, "_gateway", _gateway(providers))

    result = gemini_summary_service._generate_summary("prompt")

    assert result.summary == "Customer feedback highlights battery performance."
    first = providers["openrouter"].requests[0]
    assert first.model == OPENROUTER_MODEL_ROUTE
    assert first.metadata["fallback"] is False
    assert first.metadata["routing_strategy"] == STRATEGY_COST_AWARE
    assert first.metadata["task"] == TASK_DATASET_SUMMARY
    # Same policy semantics as analysis: fallback tail keeps P5 order.
    gemini_first = providers["gemini"].requests[0]
    assert gemini_first.model == DEFAULT_MODEL_NAME
    assert gemini_first.metadata["fallback"] is True
    assert gemini_first.metadata["task"] == TASK_DATASET_SUMMARY
    assert providers["groq"].requests == []


def test_product_summary_default_strategy_keeps_p5_head(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    providers = _multi_providers([SUMMARY_JSON])
    monkeypatch.setattr(analyzer_service, "_gateway", _gateway(providers))

    result = gemini_summary_service._generate_summary("prompt")

    assert result.summary == "Customer feedback highlights battery performance."
    first = providers["gemini"].requests[0]
    assert first.model == DEFAULT_MODEL_NAME
    assert first.metadata["routing_strategy"] == STRATEGY_GEMINI_FIRST
    assert first.metadata["fallback"] is False
