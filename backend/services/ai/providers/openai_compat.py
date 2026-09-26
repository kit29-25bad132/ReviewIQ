"""Shared stdlib HTTPS transport for OpenAI-compatible chat-completions APIs.

V2-P5: used by the Groq and OpenRouter adapters so both get one dependency-
free JSON POST implementation (``urllib.request`` — no SDK, no third-party
HTTP client) and one error-normalization path.

Guarantees:
* Raw HTTP/provider errors never escape un-normalized: callers receive an
  ``OpenAICompatError`` with a truncated, key-free message plus a status, and
  :func:`classify_openai_compat_error` maps it to the shared ``AIErrorType``
  categories.
* The request timeout (``AIGenerationRequest.timeout_seconds``) is enforced by
  the transport; an unset timeout falls back to ``DEFAULT_TIMEOUT_SECONDS``.
* Structured-output support is a compatibility hint, not a trust boundary: the
  application still parses and Pydantic-validates the returned text. If an
  endpoint rejects ``response_format`` outright (HTTP 400 naming it), the
  request is retried exactly once without it — a request-compatibility
  fallback, not a retry storm.
"""

import datetime
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, Optional

from services.ai.contracts import AIGenerationRequest, AIResponse, AIUsage
from services.ai.errors import AIErrorType, classify_error_text, classify_provider_error
from services.ai.provider import AIProvider

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_ERROR_BODY_CHARS = 500

# HTTP status codes whose ``Retry-After`` header is meaningful to honour.
_RETRY_AFTER_STATUS_CODES = frozenset({429, 503})


def _parse_retry_after(headers) -> Optional[float]:
    """Parse an HTTP ``Retry-After`` value into non-negative seconds.

    Supports integer seconds, decimal seconds, and the HTTP-date form
    (RFC 7231, via stdlib ``email.utils``). Returns ``None`` when the header
    is absent or unparseable so the caller can fall back to exponential
    backoff. Only the header value is read — request headers (including
    ``Authorization``) are never inspected or stored here.
    """
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except Exception:  # defensive: unknown header container
        return None
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        seconds = (when - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    if seconds < 0:
        return 0.0
    return seconds


class OpenAICompatError(RuntimeError):
    """Normalized failure from an OpenAI-compatible endpoint.

    ``body`` is a truncated copy of the provider's error payload (used for
    classification only) and never contains the Authorization header.
    ``retry_after_seconds`` is the server-suggested delay parsed from a
    ``Retry-After`` header, when present and valid.
    """

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        body: str = "",
        is_timeout: bool = False,
        error_type: Optional[AIErrorType] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.is_timeout = is_timeout
        # Explicit classification for structural failures decided in code
        # (e.g. malformed response shape); None means "classify from text".
        self.error_type = error_type
        self.retry_after_seconds = retry_after_seconds

    @property
    def classification_text(self) -> str:
        return f"{self} {self.body or ''}".strip().lower()


@dataclass
class ChatCompletionResult:
    """Provider-neutral chat-completion outcome (text + usage when present)."""

    content: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


def _as_int(value: object) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def classify_openai_compat_error(exc: OpenAICompatError) -> AIErrorType:
    """Map a transport/API failure to the shared error categories.

    Text hints win (matching ``classify_provider_error``'s philosophy) so
    provider-specific bodies like "rate limit exceeded" keep their meaning;
    the HTTP status is the fallback when the body carries no recognizable
    hint.
    """
    if exc.error_type is not None:
        return exc.error_type
    if exc.is_timeout:
        return AIErrorType.TIMEOUT
    category = classify_error_text(exc.classification_text)
    if category is not AIErrorType.UNKNOWN:
        return category
    status = exc.status
    if status is not None:
        if status in (400, 422):
            return AIErrorType.INVALID_REQUEST
        if status in (401, 403):
            return AIErrorType.AUTHENTICATION
        if status == 404:
            return AIErrorType.MODEL_UNAVAILABLE
        if status == 429:
            return AIErrorType.RATE_LIMIT
        if status >= 500:
            return AIErrorType.TRANSIENT
    return AIErrorType.UNKNOWN


def chat_completion(
    *,
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout_seconds: Optional[float] = None,
) -> ChatCompletionResult:
    """POST one chat-completions request and return normalized text + usage."""
    body_bytes = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    timeout = (
        timeout_seconds
        if timeout_seconds is not None and timeout_seconds > 0
        else DEFAULT_TIMEOUT_SECONDS
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        # HTTPError is also a URLError: must be caught first.
        retry_after = None
        if exc.code in _RETRY_AFTER_STATUS_CODES:
            retry_after = _parse_retry_after(getattr(exc, "headers", None))
        try:
            error_body = (
                exc.read()[:_MAX_ERROR_BODY_CHARS].decode("utf-8", "replace")
            )
        except Exception:
            error_body = ""
        raise OpenAICompatError(
            f"HTTP {exc.code} from provider endpoint",
            status=exc.code,
            body=error_body,
            retry_after_seconds=retry_after,
        ) from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        is_timeout = isinstance(reason, (TimeoutError, socket.timeout))
        raise OpenAICompatError(
            f"connection failed: {type(reason).__name__}",
            body=str(reason)[:_MAX_ERROR_BODY_CHARS],
            is_timeout=is_timeout,
        ) from None
    except (TimeoutError, socket.timeout):
        raise OpenAICompatError("request timed out", is_timeout=True) from None

    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise OpenAICompatError(
            "provider returned malformed JSON",
            error_type=AIErrorType.INVALID_RESPONSE,
        ) from None

    if not isinstance(data, dict):
        raise OpenAICompatError(
            "provider returned an unexpected response shape",
            error_type=AIErrorType.INVALID_RESPONSE,
        )

    # Some OpenAI-compatible endpoints return HTTP 200 with an error object.
    error = data.get("error")
    if error:
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise OpenAICompatError(
            "provider reported an error",
            body=str(message)[:_MAX_ERROR_BODY_CHARS],
        )

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAICompatError(
            "provider response contained no choices",
            error_type=AIErrorType.INVALID_RESPONSE,
        )
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise OpenAICompatError(
            "provider response content was not text",
            error_type=AIErrorType.INVALID_RESPONSE,
        )

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return ChatCompletionResult(
        content=content,
        prompt_tokens=_as_int(usage.get("prompt_tokens")),
        completion_tokens=_as_int(usage.get("completion_tokens")),
        total_tokens=_as_int(usage.get("total_tokens")),
    )


def chat_completion_with_json_fallback(
    *,
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout_seconds: Optional[float] = None,
) -> ChatCompletionResult:
    """:func:`chat_completion`, tolerating endpoints that reject ``response_format``.

    Exactly one retry, only when the endpoint answered HTTP 400 and named
    ``response_format`` in its error body — a request-shape compatibility
    fallback for OpenAI-compatible endpoints with uneven structured-output
    support. Every other failure propagates unchanged (no retry storms).
    """
    try:
        return chat_completion(
            url=url, api_key=api_key, payload=payload, timeout_seconds=timeout_seconds
        )
    except OpenAICompatError as exc:
        if (
            exc.status != 400
            or "response_format" not in payload
            or "response_format" not in exc.classification_text
        ):
            raise
        retry_payload = {
            key: value for key, value in payload.items() if key != "response_format"
        }
        return chat_completion(
            url=url,
            api_key=api_key,
            payload=retry_payload,
            timeout_seconds=timeout_seconds,
        )


class OpenAICompatProvider(AIProvider):
    """Shared adapter base for OpenAI-compatible providers (Groq, OpenRouter).

    Subclasses only declare identity and endpoint metadata. One generation
    request maps to one HTTP call — model/provider fallback stays outside the
    adapter, orchestrated by the LangGraph attempt loop above the gateway.
    """

    #: Stable provider identifier (set by subclasses).
    name: str = ""
    #: Official provider endpoint (never user-supplied).
    API_URL: str = ""
    #: Environment variable holding the API key.
    ENV_VAR: str = ""
    #: Placeholder values that must never count as configured.
    PLACEHOLDER_API_KEYS = frozenset()

    def __init__(
        self,
        api_key_provider: Optional[Callable[[], str]] = None,
        transport: Optional[Callable[..., ChatCompletionResult]] = None,
    ) -> None:
        self._api_key_provider = api_key_provider or self._env_api_key
        # Injectable transport keeps the adapter fully testable offline.
        self._transport = transport or chat_completion_with_json_fallback

    def _env_api_key(self) -> str:
        key = os.getenv(self.ENV_VAR, "")
        return key.strip() if key else ""

    @property
    def api_key(self) -> str:
        return (self._api_key_provider() or "").strip()

    def is_configured(self) -> bool:
        key = self.api_key
        return bool(key and key not in self.PLACEHOLDER_API_KEYS)

    @staticmethod
    def _messages(request: AIGenerationRequest) -> list:
        messages = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    def generate(self, request: AIGenerationRequest) -> AIResponse:
        model = request.model or ""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": self._messages(request),
            "temperature": request.temperature,
        }
        if request.requires_structured_output:
            # Compatibility hint only: application-side JSON parsing and
            # Pydantic validation remain mandatory and never trust this.
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            result = self._transport(
                url=self.API_URL,
                api_key=self.api_key,
                payload=payload,
                timeout_seconds=request.timeout_seconds,
            )
        except OpenAICompatError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            error_type = classify_openai_compat_error(exc)
            # Server-side log only: status/body-classification text, never keys.
            logger.warning(
                "%s model %s failed (%s): %s",
                self.name,
                model,
                error_type.value,
                exc,
            )
            return AIResponse.failure(
                provider=self.name,
                model=model,
                error_type=error_type,
                error_message=str(exc),
                latency_ms=latency_ms,
                retry_after_seconds=exc.retry_after_seconds,
            )
        except Exception as exc:  # safety net; raw text never reaches clients
            latency_ms = (time.perf_counter() - started) * 1000
            error_type = classify_provider_error(exc)
            logger.warning(
                "%s model %s raised an unexpected error: %s", self.name, model, exc
            )
            return AIResponse.failure(
                provider=self.name,
                model=model,
                error_type=error_type,
                error_message=str(exc).strip() or type(exc).__name__,
                latency_ms=latency_ms,
            )

        return AIResponse(
            content=result.content,
            provider=self.name,
            model=model,
            success=True,
            usage=AIUsage(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            ),
            latency_ms=(time.perf_counter() - started) * 1000,
            metadata={
                "structured": request.requires_structured_output,
                **dict(request.metadata),
            },
        )
