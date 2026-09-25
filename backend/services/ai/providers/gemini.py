"""Gemini adapter for the provider-neutral AI gateway.

Wraps the ``google-genai`` SDK usage that previously lived in
``services/ai_analyzer.py`` and ``services/gemini_summary_service.py``.
Existing configuration, structured-output behavior, and error semantics are
preserved; only the SDK interaction moved behind the provider interface.
"""

import logging
import os
import time
from typing import Callable, Optional

from services.ai.contracts import AIGenerationRequest, AIResponse, AIUsage
from services.ai.errors import classify_provider_error
from services.ai.provider import AIProvider
from services.ai.registry import GEMINI_PROVIDER

logger = logging.getLogger(__name__)

PLACEHOLDER_API_KEYS = frozenset(
    {"your_gemini_api_key_here", "YOUR_GEMINI_API_KEY_HERE"}
)


def _env_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    return key.strip() if key else ""


def _as_int(value: object) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _response_text(response: object) -> str:
    try:
        text = getattr(response, "text", None)
    except Exception:  # real SDK raises when the response has no candidates
        return ""
    return text or ""


def _extract_usage(response: object) -> Optional[AIUsage]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    prompt = _as_int(getattr(meta, "prompt_token_count", None))
    completion = _as_int(getattr(meta, "candidates_token_count", None))
    total = _as_int(getattr(meta, "total_token_count", None))
    if prompt is None and completion is None and total is None:
        return None
    return AIUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)


class GeminiProvider(AIProvider):
    """Provider adapter for Google Gemini via the ``google-genai`` SDK."""

    name = GEMINI_PROVIDER

    def __init__(self, api_key_provider: Optional[Callable[[], str]] = None) -> None:
        # The key resolver is injected so the analyzer stays the single owner of
        # API-key resolution (including the .env reload semantics the tests rely
        # on) instead of duplicating it inside the adapter.
        self._api_key_provider = api_key_provider or _env_api_key

    @property
    def api_key(self) -> str:
        return (self._api_key_provider() or "").strip()

    def is_configured(self) -> bool:
        key = self.api_key
        return bool(key and key not in PLACEHOLDER_API_KEYS)

    def generate(self, request: AIGenerationRequest) -> AIResponse:
        # Imported lazily so the SDK stays optional: a missing install surfaces
        # as a clear configuration error at call time, not an import crash.
        from google import genai
        from google.genai import types

        model = request.model or ""
        started = time.perf_counter()
        client = genai.Client(api_key=self.api_key)

        config = types.GenerateContentConfig(
            system_instruction=request.system_instruction,
            response_mime_type=(
                "application/json" if request.requires_structured_output else None
            ),
            response_schema=request.response_schema,
            temperature=request.temperature,
        )

        try:
            response = client.models.generate_content(
                model=model,
                contents=request.prompt,
                config=config,
            )
        except Exception as exc:  # normalized; raw SDK error never leaves here
            latency_ms = (time.perf_counter() - started) * 1000
            error_type = classify_provider_error(exc)
            logger.warning(
                "Gemini model %s failed (%s): %s", model, error_type.value, exc
            )
            return AIResponse.failure(
                provider=self.name,
                model=model,
                error_type=error_type,
                error_message=str(exc).strip() or f"{type(exc).__name__}",
                latency_ms=latency_ms,
            )

        return AIResponse(
            content=_response_text(response),
            provider=self.name,
            model=model,
            success=True,
            usage=_extract_usage(response),
            latency_ms=(time.perf_counter() - started) * 1000,
            metadata={
                "structured": request.requires_structured_output,
                **dict(request.metadata),
            },
        )
