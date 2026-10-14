"""Phase 7F — grounded RAG answer generation via the shared AI gateway.

Follows the exact Phase 5 summary pattern (services/intelligence/summary.py):
build_target_chain + generate_with_retry over the shared ``analyzer_service``.
No new provider call, no new client, no direct Gemini SDK usage.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.ai.contracts import AIGenerationRequest
from services.ai.registry import TASK_DATASET_SUMMARY
from services.ai.retry_policy import (
    generate_with_retry,
    resolve_request_timeout,
    resolve_retry_policy,
)
from services.ai.routing import build_target_chain
from services.ai_analyzer import analyzer_service
from services.observability import emit_ai_outcome

logger = logging.getLogger(__name__)

#: Quoted verbatim from the Phase 7F spec — must not drift.
RAG_ANSWER_SYSTEM_INSTRUCTION = (
    "Answer using only the review evidence provided. "
    "Cite each claim with [review_id]. "
    "If the evidence does not support a claim, omit it."
)

RAG_ANSWER_TEMPERATURE = 0.2


@dataclass(frozen=True)
class RAGAnswer:
    """One grounded answer plus the model that produced it."""

    answer: str
    model_used: str
    #: Provider that produced the answer (``None`` when the caller has no
    #: provider context — never guessed, ADR-012). Lets the RAG route report
    #: truthful provider/model metadata in the terminal outcome event it
    #: emits after citation validation (Gate 2).
    provider: Optional[str] = None


def build_answer_prompt(query: str, context_text: str) -> str:
    """User-turn prompt: the question plus the 7E-rendered evidence block."""
    return f"Question: {query}\n\nReview evidence:\n{context_text}"


def generate_rag_answer(
    query: str, context_text: str, *, emit_success_event: bool = True
) -> RAGAnswer:
    """Generate a grounded answer; raises RuntimeError when no target succeeds.

    Emits exactly ONE consolidated ``ai_request_outcome`` event (ADR-012) —
    success AND final failure alike — in ``finally``, so no exit path can skip
    it. With ``emit_success_event=False`` a successful return emits nothing
    here: the RAG route then performs its post-generation citation validation
    (which this function cannot know about) and emits the single terminal
    event itself, classified by whether the answer actually shipped. Failures
    are ALWAYS emitted here — they carry the per-target provider/model/retry
    metadata — so a deferred-success caller must never re-emit on failure
    (that would duplicate the event).

    All fields are fixed, safe metadata only: never the query, the context,
    prompts, response bodies or secrets. Emission failures are swallowed.
    """
    targets = build_target_chain(
        analyzer_service.gateway,
        primary=os.getenv("GEMINI_MODEL") or None,
        capability=TASK_DATASET_SUMMARY,
        per_provider_limit=5,
    )
    if not targets:
        # Pre-pipeline configuration error: no AI pipeline ran, so no
        # consolidated outcome event is emitted (same as the summary path).
        raise RuntimeError("No configured AI target for RAG answer generation.")

    started = time.perf_counter()
    # V2-P11 outcome holder: filled per target attempt (last target tried,
    # retry metadata, measured provider latency) and emitted in ``finally``.
    # Retrieval already ran upstream in the route, so this pipeline unit has
    # no RAG stage of its own — ``rag_status`` stays ``None``, never guessed.
    outcome: Dict[str, Any] = {
        "provider": None,
        "model": None,
        "fallback": None,
        "retry_attempts": None,
        "retry_count": None,
        "provider_latency_ms": None,
    }
    status = "failure"
    try:
        first_target = targets[0]
        last_error = "unknown"
        for target in targets:
            # Reset per target so a gateway-raised failure can never inherit
            # the previous target's numbers (ADR-012: values never guessed).
            outcome.update(
                {
                    "provider": target.provider,
                    "model": target.model,
                    "fallback": target != first_target,
                    "retry_attempts": None,
                    "retry_count": None,
                    "provider_latency_ms": None,
                }
            )
            request = AIGenerationRequest(
                prompt=build_answer_prompt(query, context_text),
                provider=target.provider,
                model=target.model,
                system_instruction=RAG_ANSWER_SYSTEM_INSTRUCTION,
                temperature=RAG_ANSWER_TEMPERATURE,
                timeout_seconds=resolve_request_timeout(),
                metadata={"task": "rag_query_answer"},
            )
            response = generate_with_retry(
                analyzer_service.gateway, request, resolve_retry_policy()
            )
            # Retry metadata + measured provider latency from the normalized
            # response (both success and returned-failure paths).
            retry_meta = getattr(response, "metadata", None)
            if isinstance(retry_meta, dict):
                outcome["retry_attempts"] = retry_meta.get("retry_attempts")
                outcome["retry_count"] = retry_meta.get("retry_count")
            outcome["provider_latency_ms"] = getattr(response, "latency_ms", None)
            if response.success and (response.content or "").strip():
                status = "success"
                return RAGAnswer(
                    answer=response.content.strip(),
                    model_used=response.model or target.model,
                    provider=response.provider or target.provider or None,
                )
            last_error = response.error_message or "empty response"
            logger.warning(
                "RAG answer attempt failed (%s/%s): %s",
                target.provider,
                target.model,
                last_error,
            )
        raise RuntimeError(f"RAG answer generation failed: {last_error}")
    finally:
        # Gate 2: a deferred-success caller (the RAG route) owns the terminal
        # event for a returned answer; failures are emitted unconditionally so
        # no path loses or duplicates the single event.
        if emit_success_event or status != "success":
            emit_ai_outcome(
                task="rag_query_answer",
                outcome=status,
                provider=outcome["provider"],
                model=outcome["model"],
                fallback=outcome["fallback"],
                retry_attempts=outcome["retry_attempts"],
                retry_count=outcome["retry_count"],
                cache="disabled",  # this path never consults the LLM cache
                rag_status=None,  # retrieval ran upstream in the route, not here
                provider_latency_ms=outcome["provider_latency_ms"],
                total_ms=round((time.perf_counter() - started) * 1000),
            )
