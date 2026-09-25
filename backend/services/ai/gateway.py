"""Central AI Gateway.

Single boundary between the analysis pipeline and provider adapters:

    Analysis pipeline (LangGraph node)
        -> AI Gateway
        -> Provider adapter (Gemini today, others later)
        -> provider SDK

The gateway resolves the explicitly selected provider/model (or the sole
registered provider), validates the selection against the model registry,
invokes the adapter, and normalizes any unexpected provider failure into an
``AIResponse`` with a classified ``error_type``.

Model fallback order is decided *above* the gateway: the LangGraph node
iterates the registry's model chain, so adding a provider means registering an
adapter plus model specs and never editing the review analysis logic.
Cross-provider fallback is intentionally not implemented in this milestone;
the registry + gateway boundaries are its extension points.
"""

import logging
from typing import Dict, Mapping, Optional

from services.ai.contracts import AIGenerationRequest, AIResponse
from services.ai.errors import (
    AIConfigurationError,
    AIProviderError,
    ModelNotAvailableError,
    UnknownProviderError,
    classify_provider_error,
)
from services.ai.provider import AIProvider
from services.ai.registry import ModelRegistry

logger = logging.getLogger(__name__)


class AIGateway:
    """Resolves the selected provider and returns a normalized AI response."""

    def __init__(
        self,
        providers: Optional[Mapping[str, AIProvider]] = None,
        registry: Optional[ModelRegistry] = None,
        default_provider: Optional[str] = None,
    ) -> None:
        self._providers: Dict[str, AIProvider] = dict(providers or {})
        self._registry = registry
        self._default_provider = default_provider

    def register_provider(self, provider: AIProvider) -> None:
        """Register (or replace) a provider adapter by its ``name``."""
        self._providers[provider.name] = provider

    @property
    def providers(self) -> Mapping[str, AIProvider]:
        return dict(self._providers)

    @property
    def registry(self) -> Optional[ModelRegistry]:
        return self._registry

    def resolve_provider(self, provider_name: Optional[str]) -> AIProvider:
        """Return the adapter for ``provider_name`` or raise if unavailable."""
        name = provider_name or self._default_provider or self._single_provider_name()
        provider = self._providers.get(name)
        if provider is None:
            raise UnknownProviderError(
                f"No AI provider adapter registered for '{name}'.", provider=name
            )
        return provider

    def _single_provider_name(self) -> str:
        if len(self._providers) == 1:
            return next(iter(self._providers))
        raise AIConfigurationError(
            "An explicit AI provider is required when multiple providers are registered."
        )

    def _validate_selection(self, provider_name: str, model: Optional[str]) -> None:
        if not model or self._registry is None:
            return
        spec = self._registry.get(provider_name, model)
        if spec is None:
            raise ModelNotAvailableError(
                f"Model '{model}' is not registered for provider '{provider_name}'.",
                provider=provider_name,
                model=model,
            )
        if not spec.enabled:
            raise ModelNotAvailableError(
                f"Model '{model}' is disabled for provider '{provider_name}'.",
                provider=provider_name,
                model=model,
            )

    def generate(self, request: AIGenerationRequest) -> AIResponse:
        """Invoke the selected provider and return a normalized response."""
        provider = self.resolve_provider(request.provider)
        self._validate_selection(provider.name, request.model)

        try:
            return provider.generate(request)
        except (AIProviderError, ImportError):
            # Already-normalized failures and a missing SDK are configuration
            # problems, not retryable provider failures: let them propagate.
            raise
        except Exception as exc:  # safety net for an un-normalized adapter
            logger.warning(
                "AI provider '%s' raised an unexpected error: %s", provider.name, exc
            )
            return AIResponse.failure(
                provider=provider.name,
                model=request.model or "",
                error_type=classify_provider_error(exc),
                error_message=str(exc).strip() or f"{type(exc).__name__}",
            )
