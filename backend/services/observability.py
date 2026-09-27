"""V2-P11 internal observability (log-only, additive) — ADR-012.

Two server-side responsibilities, neither ever serialized into an API
response:

1. **Request correlation ID.** ``request_id_var`` is a ``ContextVar`` set by
   the pure-ASGI middleware in ``main.py`` to a ``uuid4().hex`` per HTTP
   request and reset in ``finally``. The global logging formatter renders it
   (via ``RequestIdFilter``) on every record; background or internal
   execution with no request context resolves to ``"-"``.

2. **Consolidated outcome event.** ``emit_ai_outcome`` writes exactly one
   ``ai_request_outcome`` INFO line per AI pipeline run — success AND final
   failure alike — with a fixed, approved field set only.

Hard rules (ADR-012): never logs prompts, review text, RAG context,
provider response bodies, API keys, headers, PII or raw ``Retry-After``;
emission failures are swallowed so observability can never break a request;
no metrics endpoint, no aggregation, no persistence, no new dependencies.
"""

import contextvars
import logging
from typing import Optional

logger = logging.getLogger(__name__)

#: Correlation ID for the current request context; ``"-"`` when none.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "reviewiq_request_id", default="-"
)


def current_request_id() -> str:
    """Return the active correlation ID (``"-"`` outside a request)."""
    value = request_id_var.get()
    return value if value else "-"


def set_request_id(value: str):
    """Set the correlation ID; returns the token for :func:`reset_request_id`."""
    return request_id_var.set(value if value else "-")


def reset_request_id(token) -> None:
    """Restore the correlation ID to its previous state."""
    request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    """Attach the current correlation ID to every record (default ``"-"``).

    Installed on the root handlers by ``main.py`` so all loggers inherit the
    correlation suffix without touching their call sites.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = current_request_id()
        return True


def emit_ai_outcome(
    *,
    task: str,
    outcome: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    fallback: Optional[bool] = None,
    retry_attempts: Optional[int] = None,
    retry_count: Optional[int] = None,
    cache: Optional[str] = None,
    rag_status: Optional[str] = None,
    provider_latency_ms: Optional[float] = None,
    total_ms: Optional[int] = None,
) -> None:
    """Log one consolidated ``ai_request_outcome`` event (INFO, log-only).

    ``task`` is ``"review_analysis"`` or ``"product_summary"``; ``outcome``
    is ``"success"`` or ``"failure"``; ``cache`` is ``"hit"``, ``"miss"``,
    ``"disabled"`` or ``"unknown"``. Fields that do not apply or could not
    be safely determined are ``None`` — values are never guessed. The
    emission itself must never raise.
    """
    try:
        logger.info(
            "ai_request_outcome request_id=%s task=%s outcome=%s provider=%s "
            "model=%s fallback=%s retry_attempts=%s retry_count=%s cache=%s "
            "rag_status=%s provider_latency_ms=%s total_ms=%s",
            current_request_id(),
            task,
            outcome,
            provider,
            model,
            fallback,
            retry_attempts,
            retry_count,
            cache,
            rag_status,
            provider_latency_ms,
            total_ms,
        )
    except Exception:
        # Observability must never break the request (ADR-012).
        pass


__all__ = [
    "RequestIdFilter",
    "current_request_id",
    "emit_ai_outcome",
    "request_id_var",
    "reset_request_id",
    "set_request_id",
]
