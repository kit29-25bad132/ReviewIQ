"""Phase 7F — POST /api/products/{product_id}/rag-query.

End-to-end RAG over real canonical reviews: product-scoped retrieval (7D),
bounded context (7E), grounded answer via the shared AI gateway (answer_service).
Evidence excerpts are verbatim word-boundary slices of the FULL untruncated
review_text in reviews_used — never of the rendered context_text.
"""

import hashlib
import logging
import re
import time

from fastapi import APIRouter, HTTPException

from models.rag_query import EvidenceItem, RAGQueryRequest, RAGQueryResponse
from services.catalog.catalog_service import canonical_catalog
from services.intelligence.pros_cons import intelligence_rag_enabled
from services.observability import emit_ai_outcome
from services.rag.answer_service import generate_rag_answer
from services.rag.query_context import DEFAULT_MAX_TOKENS, build_rag_context
from services.rag.similar_reviews import (
    DEFAULT_MIN_SIMILARITY,
    retrieve_similar_reviews_detailed,
)

logger = logging.getLogger(__name__)

router = APIRouter()

EXCERPT_MAX_CHARS = 280

#: Hex chars kept of the SHA-256 digest of discarded LLM output (48 bits).
#: Enough to correlate repeated discards of identical output across logs
#: without revealing any of the content.
_ANSWER_DIGEST_PREFIX_LEN = 12


def _answer_digest_prefix(text: str) -> str:
    """Non-reversible fingerprint of discarded LLM output for safe logging."""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:_ANSWER_DIGEST_PREFIX_LEN]


def _verbatim_excerpt(text: str, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    """Verbatim slice at a word boundary — guaranteed substring of the text."""
    raw = str(text or "")
    if not raw.strip():
        return ""
    if len(raw) <= max_chars:
        return raw.strip()
    head = raw[:max_chars]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head.strip()


def _disabled_response() -> RAGQueryResponse:
    return RAGQueryResponse(
        answer="",
        evidence=[],
        retrieval_count=0,
        context_token_estimate=0,
        model_used="",
        rag_enabled=False,
        fallback_used=False,
    )


@router.post("/api/products/{product_id}/rag-query", response_model=RAGQueryResponse)
def rag_query(product_id: str, payload: RAGQueryRequest) -> RAGQueryResponse:
    # Gate 2: request-scoped clock for the terminal outcome events this route
    # emits (retrieval failure; post-generation verdict).
    started = time.perf_counter()
    clean_pid = str(product_id).strip()
    if not canonical_catalog.get_product_by_id(clean_pid):
        raise HTTPException(
            status_code=404, detail=f"Product '{product_id}' not found."
        )

    if not intelligence_rag_enabled():
        return _disabled_response()

    try:
        outcome = retrieve_similar_reviews_detailed(
            payload.query, clean_pid, top_k=payload.top_k, min_similarity=DEFAULT_MIN_SIMILARITY
        )
    except Exception as err:  # DB/embedding failure: degrade to the empty shape, never 500
        # Safe logging: never the raw exception text — a traceback frame would
        # print it too — only the operation and the exception class.
        logger.error(
            "RAG retrieval failed for product %s (error_type=%s)",
            clean_pid,
            type(err).__name__,
        )
        # Gate 2 Case A: the answer pipeline never runs on this path, so the
        # route emits the request's single terminal outcome event itself —
        # a failure, never success. No AI target ran: provider/model/retry/
        # latency stay None (ADR-012: unavailable values are never guessed).
        emit_ai_outcome(
            task="rag_query_answer",
            outcome="failure",
            provider=None,
            model=None,
            fallback=None,
            retry_attempts=None,
            retry_count=None,
            cache="disabled",
            rag_status=None,  # established rationale for this task, unchanged
            provider_latency_ms=None,
            total_ms=round((time.perf_counter() - started) * 1000),
        )
        return RAGQueryResponse(
            answer="",
            evidence=[],
            retrieval_count=0,
            context_token_estimate=0,
            model_used="",
            rag_enabled=True,
            fallback_used=False,
        )

    if not outcome.reviews:
        return RAGQueryResponse(
            answer="",
            evidence=[],
            retrieval_count=0,
            context_token_estimate=0,
            model_used="",
            rag_enabled=True,
            fallback_used=outcome.fallback_triggered,
        )

    context = build_rag_context(outcome.reviews, max_tokens=DEFAULT_MAX_TOKENS)

    try:
        # Gate 2 Case B: the service must NOT report success yet — only this
        # route knows whether the generated answer survives citation validation.
        # On generation failure the service's own ``finally`` already emitted
        # the single (failure) event, so the except below must not emit again.
        rag_answer = generate_rag_answer(
            payload.query, context.context_text, emit_success_event=False
        )
    except Exception as err:  # provider/target exhaustion: never crash, never invent
        logger.warning("RAG answer generation unavailable: %s", err)
        return RAGQueryResponse(
            answer="",
            evidence=[],
            retrieval_count=len(context.reviews_used),
            context_token_estimate=context.token_estimate,
            model_used="",
            rag_enabled=True,
            fallback_used=outcome.fallback_triggered,
        )

    evidence = [
        EvidenceItem(
            review_id=review.review_id,
            excerpt=_verbatim_excerpt(review.review_text),
            similarity_score=review.similarity_score,
            rating=review.rating,
        )
        for review in context.reviews_used
        if _verbatim_excerpt(review.review_text)
    ]

    answer = rag_answer.answer
    answer_discarded = False
    evidence_ids = {item.review_id for item in evidence}
    unknown_citations = sorted(
        {citation for citation in re.findall(r"\[([RP]\d{5})\]", answer) if citation not in evidence_ids}
    )
    if unknown_citations:
        # Runtime citation validation: never ship an answer whose citations
        # are not backed by the evidence list. Logs safe metadata only —
        # never the raw LLM output (it can quote review text verbatim).
        logger.warning(
            "RAG citation validation: unknown citation(s) %s; discarding answer "
            "(length=%d, sha256_prefix=%s)",
            unknown_citations,
            len(answer),
            _answer_digest_prefix(answer),
        )
        answer = ""
        answer_discarded = True

    if not evidence:
        # Uncited-answer guard: never ship an answer with no traceable
        # evidence. Logs safe metadata only — never the raw LLM output.
        logger.warning(
            "RAG uncited-answer guard: evidence empty; discarding answer "
            "(length=%d, sha256_prefix=%s)",
            len(answer),
            _answer_digest_prefix(answer),
        )
        answer = ""
        answer_discarded = True

    # Gate 2 Case B: this request's single terminal outcome event. The answer
    # service deferred its success emission (emit_success_event=False) because
    # only this point knows whether the generated answer actually shipped —
    # a discarded answer must never be recorded as a grounded success.
    # fallback/retry/latency are route-unavailable → None (ADR-012, never
    # guessed); provider/model come from the answer itself.
    emit_ai_outcome(
        task="rag_query_answer",
        outcome="failure" if answer_discarded else "success",
        provider=rag_answer.provider,
        model=rag_answer.model_used or None,
        fallback=None,
        retry_attempts=None,
        retry_count=None,
        cache="disabled",  # this path never consults the LLM cache
        rag_status=None,  # established rationale for this task, unchanged
        provider_latency_ms=None,
        total_ms=round((time.perf_counter() - started) * 1000),
    )

    return RAGQueryResponse(
        answer=answer,
        evidence=evidence,
        retrieval_count=len(context.reviews_used),
        context_token_estimate=context.token_estimate,
        model_used=rag_answer.model_used,
        rag_enabled=True,
        fallback_used=outcome.fallback_triggered,
    )
