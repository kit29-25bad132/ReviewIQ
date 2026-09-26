"""Model registry: provider-neutral metadata for selectable models.

Originally the foundation for the V2 cost-aware router (ADR-004); V2-P6
(ADR-008) now populates verified cost, context-window, and free-tier metadata
so ``services/ai/routing_policy.py`` can rank targets deterministically. The
registry still implements no routing algorithm itself.

Verified values are recorded in USD per 1K tokens (converted from published
per-1M prices) with the source documented in ADR-008. A field stays ``None``
when the project does not have a verified value — unknown metadata is never
invented and must never be treated as zero cost by consumers. This data is
time-sensitive: re-verify when provider pricing or free-tier policies change.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from services.ai.contracts import ModelRef

GEMINI_PROVIDER = "gemini"
GROQ_PROVIDER = "groq"
OPENROUTER_PROVIDER = "openrouter"

# Provider hierarchy for cross-provider fallback (V2-P5). This order is the
# contract: Gemini first (verified V1 chain), Groq second, OpenRouter last.
PROVIDER_ORDER: Tuple[str, ...] = (GEMINI_PROVIDER, GROQ_PROVIDER, OPENROUTER_PROVIDER)

# Task capability identifiers used by the registry.
TASK_REVIEW_ANALYSIS = "review_analysis"
TASK_DATASET_SUMMARY = "dataset_summary"

# Quality tiers (metadata only; no pricing or latency is implied).
QUALITY_STANDARD = "standard"
QUALITY_LITE = "lite"

# Pinned primary Gemini model, verified against the configured API key
# (models.list + generateContent smoke tests, 2026-09-24). Pinning a stable
# model keeps evaluation reproducible.
DEFAULT_MODEL_NAME = "gemini-3.8-flash"

# Verified Gemini-only fallback pool (deterministic order). No preview / Pro /
# 2.5-family / specialized models. No runtime discovery in V1/V2-foundation.
FALLBACK_MODEL_NAMES = [
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

# Groq model chain (V2-P5, exact locked IDs). Primary first; the rest are
# fallback candidates in priority order.
GROQ_DEFAULT_MODEL_NAME = "openai/gpt-oss-120b"
GROQ_MODEL_NAMES = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

# OpenRouter uses a single free route, not a hardcoded model list: the route
# resolves the actual model upstream, so nothing is pinned here.
OPENROUTER_MODEL_ROUTE = "openrouter/free"

_ALL_TASKS = frozenset({TASK_REVIEW_ANALYSIS, TASK_DATASET_SUMMARY})


@dataclass(frozen=True)
class ModelSpec:
    """Everything the application needs to know about one selectable model.

    ``estimated_cost_*``, ``context_window``, and ``free_tier`` are optional:
    an unknown value must never be represented as a made-up number. V2-P6
    populates them only from verified provider documentation (ADR-008);
    ``None`` means "unverified", never "zero" or "free".
    """

    provider: str
    model: str
    capabilities: frozenset = frozenset()
    quality_tier: str = QUALITY_STANDARD
    priority: int = 0
    enabled: bool = True
    supports_structured_output: bool = True
    context_window: Optional[int] = None
    estimated_cost_per_1k_input: Optional[float] = None
    estimated_cost_per_1k_output: Optional[float] = None
    # Verified free-tier availability: True = provider documents a free tier
    # for this model/account, False = verified paid-only, None = unverified.
    # Never inferred from a low paid price.
    free_tier: Optional[bool] = None
    # The model used when no explicit primary is configured for the provider.
    is_default_primary: bool = False
    # Whether the model participates in the provider's fallback pool.
    is_fallback_candidate: bool = True


class ModelRegistry:
    """An ordered, provider-keyed collection of :class:`ModelSpec` entries."""

    def __init__(self, specs: Iterable[ModelSpec] = ()) -> None:
        self._specs: Dict[Tuple[str, str], ModelSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ModelSpec) -> None:
        self._specs[(spec.provider, spec.model)] = spec

    def get(self, provider: str, model: str) -> Optional[ModelSpec]:
        return self._specs.get((provider, model))

    def is_available(self, provider: str, model: str) -> bool:
        spec = self.get(provider, model)
        return bool(spec and spec.enabled)

    def list_all(self) -> List[ModelSpec]:
        return list(self._specs.values())

    def list_provider(
        self,
        provider: str,
        capability: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[ModelSpec]:
        specs = [s for s in self._specs.values() if s.provider == provider]
        if enabled_only:
            specs = [s for s in specs if s.enabled]
        if capability is not None:
            specs = [s for s in specs if capability in s.capabilities]
        # Stable sort: equal priorities keep registration order.
        return sorted(specs, key=lambda s: s.priority)

    def default_primary(self, provider: str) -> Optional[str]:
        for spec in self.list_provider(provider):
            if spec.is_default_primary:
                return spec.model
        return None

    def chain(
        self,
        provider: str,
        primary: Optional[str] = None,
        capability: Optional[str] = None,
        limit: int = 5,
    ) -> List[str]:
        """Return a bounded model chain: primary first, then the fallback pool.

        The configured/primary model is tried first; registered fallback
        candidates follow in priority order. The result is deduplicated and
        capped at ``limit`` attempts. This centralizes model ordering so it is
        never hardcoded across the codebase.
        """
        primary_model = primary or self.default_primary(provider)
        chain: List[str] = []
        if primary_model:
            chain.append(primary_model)
        for spec in self.list_provider(provider, capability=capability):
            if spec.model == primary_model or not spec.is_fallback_candidate:
                continue
            if spec.model in chain:
                continue
            chain.append(spec.model)
            if len(chain) >= limit:
                break
        return chain[:limit]

    def chain_refs(
        self,
        provider_order: Sequence[str] = PROVIDER_ORDER,
        *,
        primary: Optional[str] = None,
        primary_provider: str = GEMINI_PROVIDER,
        capability: Optional[str] = None,
        is_configured: Optional[Callable[[str], bool]] = None,
        per_provider_limit: int = 5,
        limit: Optional[int] = None,
    ) -> List[ModelRef]:
        """Provider-qualified fallback chain (V2-P5): ``ModelRef`` targets.

        Walks ``provider_order`` (Gemini -> Groq -> OpenRouter by default) and,
        for each configured provider, appends that provider's model chain in
        the same order as :meth:`chain`. Providers that are not configured
        (``is_configured`` callback returns False, or not consulted at all
        when the callback is ``None``) contribute no targets and never raise —
        an unconfigured provider must not break startup or analysis.

        ``primary`` overrides the primary model of ``primary_provider`` only
        (the ``GEMINI_MODEL`` override stays Gemini-scoped).
        """
        targets: List[ModelRef] = []
        for provider in provider_order:
            if is_configured is not None and not is_configured(provider):
                continue
            provider_primary = primary if provider == primary_provider else None
            for model in self.chain(
                provider,
                provider_primary,
                capability=capability,
                limit=per_provider_limit,
            ):
                targets.append(ModelRef(provider=provider, model=model))
            if limit is not None and len(targets) >= limit:
                break
        return targets[:limit] if limit is not None else targets


# ---------------------------------------------------------------------------
# V2-P6 verified model metadata (ADR-008; official provider documentation,
# verified 2026-09-26). USD per 1K tokens, converted from published per-1M
# prices. Models without a clearly verified price/context keep None — values
# are never invented. Time-sensitive: re-verify when provider pricing or
# free-tier policies change.
# ---------------------------------------------------------------------------
# Gemini (per-1M published prices -> per-1K): gemini-3.8-flash $0.75/$3.75
# (introductory, through 2026-12-31); gemini-3.5-flash $1.50/$9.00;
# gemini-3.5-flash-lite $0.30/$2.50. No verified price is clearly published
# for gemini-3.6-flash or the gemini-flash-latest alias, so those stay None.
# Gemini free-tier access is listed as free for eligible models/accounts, so
# every registry Gemini model records free_tier=True (not inferred from
# price — from the documented free-tier availability).
_VERIFIED_GEMINI_COST_PER_1K = {
    DEFAULT_MODEL_NAME: (0.00075, 0.00375),
    "gemini-3.5-flash": (0.0015, 0.009),
    "gemini-3.5-flash-lite": (0.0003, 0.0025),
}
_VERIFIED_GEMINI_CONTEXT_WINDOW = {
    DEFAULT_MODEL_NAME: 1_000_000,
    "gemini-3.5-flash": 1_000_000,
    "gemini-3.5-flash-lite": 1_048_576,
}
# Groq (per-1M published prices -> per-1K): gpt-oss-120b $0.15/$0.60;
# gpt-oss-20b $0.075/$0.30; qwen3.8-27b $0.80/$4.00. Context windows per
# Groq model pages. free_tier stays None: no applicable free plan is
# established by the verified sources for these models.
_VERIFIED_GROQ_COST_PER_1K = {
    "openai/gpt-oss-120b": (0.00015, 0.0006),
    "openai/gpt-oss-20b": (0.000075, 0.0003),
    "qwen/qwen3.8-27b": (0.0008, 0.004),
}
_VERIFIED_GROQ_CONTEXT_WINDOW = {
    "openai/gpt-oss-120b": 131_072,
    "openai/gpt-oss-20b": 131_072,
    "qwen/qwen3.8-27b": 131_042,
}
# OpenRouter's free route: $0 input/$0 output, 200K context, verified free
# tier (officially limited, e.g. 50 requests/day). It is an opaque router
# that resolves the underlying model upstream — never a statically
# identifiable model.
_OPENROUTER_ROUTE_INPUT_COST = 0.0
_OPENROUTER_ROUTE_OUTPUT_COST = 0.0
_OPENROUTER_ROUTE_CONTEXT_WINDOW = 200_000


def _cost_fields(
    table: Dict[str, tuple], model: str
) -> Tuple[Optional[float], Optional[float]]:
    input_cost, output_cost = table.get(model, (None, None))
    return input_cost, output_cost


def build_default_registry() -> ModelRegistry:
    """Registry populated with the Gemini chain (verified, unchanged) plus the
    V2-P5 Groq and OpenRouter entries, annotated with V2-P6 verified
    cost/context/free-tier metadata. Unverified fields stay ``None``: no
    verified value exists, so none is invented."""
    primary_input, primary_output = _cost_fields(
        _VERIFIED_GEMINI_COST_PER_1K, DEFAULT_MODEL_NAME
    )
    specs = [
        ModelSpec(
            provider=GEMINI_PROVIDER,
            model=DEFAULT_MODEL_NAME,
            capabilities=_ALL_TASKS,
            quality_tier=QUALITY_STANDARD,
            priority=0,
            is_default_primary=True,
            # The default primary is a configuration value, not part of the
            # fallback pool (preserves V1 ordering semantics exactly).
            is_fallback_candidate=False,
            estimated_cost_per_1k_input=primary_input,
            estimated_cost_per_1k_output=primary_output,
            context_window=_VERIFIED_GEMINI_CONTEXT_WINDOW[DEFAULT_MODEL_NAME],
            free_tier=True,
        )
    ]
    for position, model in enumerate(FALLBACK_MODEL_NAMES, start=1):
        input_cost, output_cost = _cost_fields(_VERIFIED_GEMINI_COST_PER_1K, model)
        specs.append(
            ModelSpec(
                provider=GEMINI_PROVIDER,
                model=model,
                capabilities=_ALL_TASKS,
                quality_tier=QUALITY_LITE if model.endswith("lite") else QUALITY_STANDARD,
                priority=position,
                is_fallback_candidate=True,
                estimated_cost_per_1k_input=input_cost,
                estimated_cost_per_1k_output=output_cost,
                context_window=_VERIFIED_GEMINI_CONTEXT_WINDOW.get(model),
                free_tier=True,
            )
        )

    # V2-P5: Groq model chain (primary first, then fallback candidates).
    for position, model in enumerate(GROQ_MODEL_NAMES):
        is_primary = position == 0
        input_cost, output_cost = _cost_fields(_VERIFIED_GROQ_COST_PER_1K, model)
        specs.append(
            ModelSpec(
                provider=GROQ_PROVIDER,
                model=model,
                capabilities=_ALL_TASKS,
                quality_tier=QUALITY_LITE if model == "openai/gpt-oss-20b" else QUALITY_STANDARD,
                priority=position,
                is_default_primary=is_primary,
                is_fallback_candidate=not is_primary,
                estimated_cost_per_1k_input=input_cost,
                estimated_cost_per_1k_output=output_cost,
                context_window=_VERIFIED_GROQ_CONTEXT_WINDOW.get(model),
                free_tier=None,
            )
        )

    # V2-P5: OpenRouter final fallback — a single route, not a model list.
    specs.append(
        ModelSpec(
            provider=OPENROUTER_PROVIDER,
            model=OPENROUTER_MODEL_ROUTE,
            capabilities=_ALL_TASKS,
            quality_tier=QUALITY_STANDARD,
            priority=0,
            is_default_primary=True,
            is_fallback_candidate=False,
            estimated_cost_per_1k_input=_OPENROUTER_ROUTE_INPUT_COST,
            estimated_cost_per_1k_output=_OPENROUTER_ROUTE_OUTPUT_COST,
            context_window=_OPENROUTER_ROUTE_CONTEXT_WINDOW,
            free_tier=True,
        )
    )
    return ModelRegistry(specs)


# Shared default registry. Tests may construct their own isolated instances.
model_registry = build_default_registry()
