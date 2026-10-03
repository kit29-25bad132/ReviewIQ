"""Provider-aware routing helpers shared by both fallback paths (V2-P5).

Two places iterate the fallback chain — the analysis pipeline
(``services/ai_analyzer.py``, LangGraph-orchestrated) and the product-summary
path (``services/gemini_summary_service.py``). This module keeps the chain
construction and the provider-skip policy in one place so the two paths cannot
drift apart, without moving any fallback loop into the gateway (the gateway
stays single-shot; LangGraph stays the analysis orchestrator).
"""

from typing import Callable, List, Optional

from services.ai.contracts import ModelRef
from services.ai.errors import AIErrorType
from services.ai.gateway import AIGateway
from services.ai.registry import (
    TASK_REVIEW_ANALYSIS,
    model_registry,
)

# Provider-level failures: the credentials or the provider configuration are
# wrong, so every remaining model of THAT provider would fail identically —
# skip them instead of burning the model chain. All other categories
# (rate limit, timeout, transient, model unavailable, invalid response,
# invalid request, unknown) continue along the model-level chain, and provider
# fallback happens when the provider's usable models are exhausted.
SKIP_REMAINING_PROVIDER_ERRORS = frozenset(
    {AIErrorType.AUTHENTICATION, AIErrorType.CONFIGURATION}
)


def skips_remaining_provider_models(error_type: Optional[AIErrorType]) -> bool:
    """True when ``error_type`` means "skip the rest of this provider"."""
    return error_type in SKIP_REMAINING_PROVIDER_ERRORS


def provider_configured_checker(gateway: AIGateway) -> Callable[[str], bool]:
    """A provider counts as configured only when it is *registered on the
    gateway* and its adapter reports configured credentials. Registering an
    adapter without a key never breaks the chain — the provider is skipped."""

    def _is_configured(provider_name: str) -> bool:
        provider = gateway.providers.get(provider_name)
        return bool(provider is not None and provider.is_configured())

    return _is_configured


def build_target_chain(
    gateway: AIGateway,
    *,
    primary: Optional[str] = None,
    capability: str = TASK_REVIEW_ANALYSIS,
    per_provider_limit: int = 5,
    limit: Optional[int] = None,
) -> List[ModelRef]:
    """Provider-qualified fallback chain for one task.

    Gemini (model chain) -> Groq (model chain) -> OpenRouter (single route),
    filtered to providers that are registered and configured. Unconfigured
    providers contribute nothing and never raise.
    """
    return model_registry.chain_refs(
        primary=primary,
        capability=capability,
        is_configured=provider_configured_checker(gateway),
        per_provider_limit=per_provider_limit,
        limit=limit,
    )
