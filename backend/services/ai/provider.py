"""AI provider interface.

The rest of ReviewIQ depends on this abstraction instead of a provider SDK.
Concrete adapters live in ``services/ai/providers/`` (Gemini today; future
OpenAI-compatible and free-tier providers later).
"""

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from services.ai.contracts import AIGenerationRequest, AIResponse


class AIProvider(ABC):
    """A provider of AI text generation.

    Implementations are expected to classify SDK failures into an
    ``AIResponse`` with ``success=False`` and a normalized ``error_type``
    rather than leaking SDK exception types to callers.
    """

    #: Stable provider identifier (e.g. "gemini"), used by the model registry.
    name: str = ""

    @abstractmethod
    def generate(self, request: AIGenerationRequest) -> AIResponse:
        """Execute one generation request and return a normalized response."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when the provider has the credentials it needs."""

    def supported_models(self) -> Optional[Sequence[str]]:
        """Optional runtime model list; ``None`` means 'use the registry'."""
        return None
