"""Model registry: provider-neutral metadata for selectable models.

This is the foundation for the V2 cost-aware router. This milestone records
capability, quality, structured-output, ordering, and enable/disable metadata
only. It deliberately implements **no** routing algorithm yet.

Cost and context-window fields stay ``None`` because the project does not have
verified values for them. They are configurable rather than hardcoded so the
routing milestone can populate real numbers instead of inventing prices.
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

    ``estimated_cost_*`` and ``context_window`` are intentionally optional: an
    unknown value must never be represented as a made-up number.
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


def build_default_registry() -> ModelRegistry:
    """Registry populated with the Gemini chain (verified, unchanged) plus the
    V2-P5 Groq and OpenRouter entries. Cost/context metadata stays ``None``:
    no verified values exist, so none are invented."""
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
        )
    ]
    for position, model in enumerate(FALLBACK_MODEL_NAMES, start=1):
        specs.append(
            ModelSpec(
                provider=GEMINI_PROVIDER,
                model=model,
                capabilities=_ALL_TASKS,
                quality_tier=QUALITY_LITE if model.endswith("lite") else QUALITY_STANDARD,
                priority=position,
                is_fallback_candidate=True,
            )
        )

    # V2-P5: Groq model chain (primary first, then fallback candidates).
    for position, model in enumerate(GROQ_MODEL_NAMES):
        is_primary = position == 0
        specs.append(
            ModelSpec(
                provider=GROQ_PROVIDER,
                model=model,
                capabilities=_ALL_TASKS,
                quality_tier=QUALITY_LITE if model == "openai/gpt-oss-20b" else QUALITY_STANDARD,
                priority=position,
                is_default_primary=is_primary,
                is_fallback_candidate=not is_primary,
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
        )
    )
    return ModelRegistry(specs)


# Shared default registry. Tests may construct their own isolated instances.
model_registry = build_default_registry()
