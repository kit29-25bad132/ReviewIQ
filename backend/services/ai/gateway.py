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
import time
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

logger = logging.getLogger(__name__)# Per-gateway request start time, shared across all generate() calls.
# Initialized lazily on first generate() call; tracked monotonically so
# the global deadline spans the entire request including retries and fallback.
# immune to clock shifts.
# NOTE: stored on the instance so it persists across multiple generate()
# calls (e.g. retries in generate_with_retry, or different providers in the
# fallback chain).
_per_gateway_start_time: Optional[float] = None

def _get_per_gateway_start_time() -> float:
    """Return the per-gateway start time, initializing on first call."""
    global _per_gateway_start_time
    if _per_gateway_start_time is None:
        _per_gateway_start_time = time.monotonic()
    return _per_gateway_start_time

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
        # Per-gateway request start time, shared across all generate() calls.
        # Initialized lazily on first generate() call.
        self._request_start_time: Optional[float] = None
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
            )        return provider
    def _single_provider_name(self) -> str:
        if len(self._providers) == 1:
            return next(iter(self._providers))
        raise AIConfigurationError(
            "An explicit AI provider is required when multiple providers are registered."        )
    def _validate_selection(self, provider_name: str, model: Optional[str]) -> None:
        if not model or self._registry is None:
            return
        spec = self._registry.get(provider_name, model)
        if spec is None:
            raise ModelNotAvailableError(
                f"Model '{model}' is not registered for provider '{provider_name}'.",
                provider=provider_name,
                model=model,
            )        if not spec.enabled:
            raise ModelNotAvailableError(
                f"Model '{model}' is disabled for provider '{provider_name}'.",
                provider=provider_name,
                model=model,
            )    def generate(self, request: AIGenerationRequest) -> AIResponse:
        """Invoke the selected provider and return a normalized AI response.

        Enforces per-provider timeout (from ``request.timeout_seconds``) and
        global deadline (tracked monotonically across ALL generate() calls on
        this gateway instance, including retries and fallback transitions).
        On global deadline expiry returns a structured timeout response, never a
        raw exception.
        """
        from services.ai.retry_policy import resolve_global_deadline, resolve_per_provider_timeout

        provider = self.resolve_provider(request.provider)
        self._validate_selection(provider.name, request.model)
        # Initialize request start time on first generate() call.
        if self._request_start_time is None:
            self._request_start_time = time.monotonic()
        # Check global deadline since request started.
        global_deadline = resolve_global_deadline()
        elapsed = time.monotonic() - self._request_start_time
        if elapsed >= global_deadline:
            logger.warning(
                f"Global AI deadline of {global_deadline}s exceeded "
                f"(elapsed={elapsed:.1f}s). Returning structured timeout response.",
            )
            return AIResponse.failure(
                provider=provider.name,
                model=request.model or "",
                error_type=AIErrorType.TIMEOUT,
                error_message=
                "AI analysis timed out globally. Please try again in a few minutes.",
            )
        # Enforce per-provider timeout via the request timeout_seconds.
        # The provider adapter (e.g. Gemini) is responsible for honoring this.
        # We also verify the per-provider config is less than the global deadline.        per_provider_to = resolve_per_provider_timeout(provider.name)
        if per_provider_to >= global_deadline:
            logger.warning(
                f"Per-provider timeout {per_provider_to}s is not strictly less "
                f"than global deadline {global_deadline}s; clamping per-provider timeout.",            )            # Clamp: ensure per-provider timeout is at most global_deadline - 1s            per_provider_to = max(1.0, global_deadline - 1.0)
        request.timeout_seconds = min(
            request.timeout_seconds or per_provider_to,
            per_provider_to,
        )        try:            return provider.generate(request)        except (AIProviderError, ImportError):            # Already-normalized failures and a missing SDK are configuration            # problems, not retryable provider failures: let them propagate.            raise        except Exception as exc:  # safety net for an un-normalized adapter            logger.warning(
                f"AI provider '{provider.name}' raised an unexpected error: {exc}"            )            return AIResponse.failure(
                provider=provider.name,
                model=request.model or "",
                error_type=classify_provider_error(exc),
                error_message=str(exc).strip() or f"{type(exc).__name__}",
            )

