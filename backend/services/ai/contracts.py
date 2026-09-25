"""Provider-neutral AI generation contracts.

Everything above the provider adapters (the analysis pipeline, LangGraph
nodes, dataset summarization) depends only on these types. No Gemini SDK type
appears here, so a future OpenAI-compatible or free-tier provider can be added
without touching the review analysis logic.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from services.ai.errors import AIErrorType


@dataclass(frozen=True)
class ModelRef:
    """An explicit provider + model selection handed to the AI Gateway."""

    provider: str
    model: str


@dataclass
class AIGenerationRequest:
    """A single provider-neutral generation request."""

    prompt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    system_instruction: Optional[str] = None
    temperature: float = 0.2
    # When set, the provider must return content that validates against this
    # Pydantic schema (structured output). Parsing/validation still happens in
    # the application layer so the contract stays provider-neutral.
    response_schema: Optional[Type[BaseModel]] = None
    timeout_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def requires_structured_output(self) -> bool:
        return self.response_schema is not None


@dataclass
class AIUsage:
    """Token usage reported by a provider, when available."""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    # Only populated from verified pricing metadata; never guessed.
    estimated_cost_usd: Optional[float] = None


@dataclass
class AIResponse:
    """Provider-neutral generation result."""

    content: str = ""
    provider: str = ""
    model: str = ""
    success: bool = True
    error_type: Optional[AIErrorType] = None
    error_message: Optional[str] = None
    usage: Optional[AIUsage] = None
    latency_ms: Optional[float] = None
    fallback: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def failure(
        cls,
        *,
        provider: str,
        model: str,
        error_type: AIErrorType,
        error_message: str,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AIResponse":
        return cls(
            content="",
            provider=provider,
            model=model,
            success=False,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
