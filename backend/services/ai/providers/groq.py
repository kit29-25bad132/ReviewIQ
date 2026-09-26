"""Groq adapter for the provider-neutral AI gateway (V2-P5).

Groq exposes an OpenAI-compatible HTTPS API, so this adapter is a thin
identity wrapper over the shared stdlib transport in ``openai_compat``: no
SDK, no new dependency. One call = one model request; the Gemini -> Groq ->
OpenRouter fallback chain lives above the gateway (LangGraph attempt loop).

Structured output: the adapter requests JSON mode
(``response_format: {"type": "json_object"}``) when the caller supplies a
response schema. This is a compatibility hint only — the application still
parses the returned text and validates it with Pydantic before grounding.
"""

from services.ai.providers.openai_compat import OpenAICompatProvider
from services.ai.registry import GROQ_PROVIDER


class GroqProvider(OpenAICompatProvider):
    """Provider adapter for Groq via its OpenAI-compatible chat API."""

    name = GROQ_PROVIDER
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    ENV_VAR = "GROQ_API_KEY"
    PLACEHOLDER_API_KEYS = frozenset(
        {"your_groq_api_key_here", "YOUR_GROQ_API_KEY_HERE"}
    )
