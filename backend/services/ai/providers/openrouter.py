"""OpenRouter adapter for the provider-neutral AI gateway (V2-P5).

Final provider fallback. OpenRouter exposes an OpenAI-compatible HTTPS API at
its official endpoint, so this adapter uses the shared stdlib transport in
``openai_compat`` — no SDK, no new dependency, and the endpoint is fixed in
the adapter (never user-supplied).

Why a route instead of a model list: ``openrouter/free`` is OpenRouter's
free-model routing slug. The concrete model served is chosen upstream and can
change over time, so this project deliberately does **not** maintain a
hand-written list of OpenRouter free models. The registry stores exactly one
target for this provider: ``openrouter/free``.

Structured output: JSON mode is requested when a response schema is present
(forwarded upstream "where supported by the route"); if the endpoint rejects
``response_format`` the shared transport retries exactly once without it.
Application-side JSON parsing and Pydantic validation remain mandatory.
"""

from services.ai.providers.openai_compat import OpenAICompatProvider
from services.ai.registry import OPENROUTER_PROVIDER


class OpenRouterProvider(OpenAICompatProvider):
    """Provider adapter for OpenRouter's OpenAI-compatible chat API."""

    name = OPENROUTER_PROVIDER
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    ENV_VAR = "OPENROUTER_API_KEY"
    PLACEHOLDER_API_KEYS = frozenset(
        {"your_openrouter_api_key_here", "YOUR_OPENROUTER_API_KEY_HERE"}
    )
