"""Phase 5D — grounded product summary + "best for" line.

The summary is generated only from the retrieved reviews and the aspects the
5B stage actually found, so it cannot describe a feature the reviews never
mention. Generation goes through LangGraph (``services.intelligence.graph``).
"""

import json
import logging
import os
import re
import time
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ValidationError

from models.intelligence import AspectResult
from services.ai.contracts import AIGenerationRequest
from services.ai.registry import TASK_DATASET_SUMMARY
from services.ai.retry_policy import (
    generate_with_retry,
    resolve_request_timeout,
    resolve_retry_policy,
)
from services.ai.routing import build_target_chain
from services.ai_analyzer import analyzer_service
from services.intelligence.corpus import load_product_corpus
from services.intelligence.graph import run_intelligence_graph
from services.observability import emit_ai_outcome

logger = logging.getLogger(__name__)

SUMMARY_TEMPERATURE = 0.2
SUMMARY_ATTEMPTS = 2
MAX_SUMMARY_SENTENCES = 4
MAX_CONTEXT_REVIEWS = 40

#: The grounding clause is quoted verbatim from the Phase 5 requirement, so it
#: cannot drift from the spec.
SUMMARY_SYSTEM_INSTRUCTION = """You write a factual product summary from customer reviews.

Only use information present in the provided reviews. Do not infer product specifications not mentioned in reviews. If the reviews are insufficient, say so.

Additional rules:
1. "summary" must be 2 to 4 sentences grounded directly in the supplied reviews, and must reference the recurring aspects that were actually identified.
2. "best_for" must be ONE short line naming the kind of buyer these reviews suggest the product suits. Base it only on what the reviews say.
3. Never invent features, specifications, prices, or comparisons. Never state a number that is not in the supplied reviews.
4. If the reviews are insufficient to support a recommendation, say so plainly in "best_for" instead of guessing.
5. Return strictly structured JSON matching the requested schema.
"""


class SummaryDraft(BaseModel):
    """The model's structured summary output."""

    summary: str = Field(..., min_length=1)
    best_for: str = Field(..., min_length=1)


def _strip_code_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def count_sentences(text: str) -> int:
    """Count sentences without importing an NLP dependency."""
    parts = [p for p in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if p.strip()]
    return len(parts)


def validate_summary(draft: SummaryDraft) -> SummaryDraft:
    """Reject rambling output; keeps the 2-4 sentence contract on the upper bound.

    The lower bound is deliberately not enforced: a sparse but accurate
    one-sentence summary is better than padding it with invented filler.
    """
    sentences = count_sentences(draft.summary)
    if sentences > MAX_SUMMARY_SENTENCES:
        raise ValueError(
            f"summary has {sentences} sentences; maximum is {MAX_SUMMARY_SENTENCES}"
        )
    return draft


def _attempt_summary(prompt: str, target: Any, product_id: str) -> SummaryDraft:
    """One generation attempt against one target. Raises on any failure."""
    request = AIGenerationRequest(
        prompt=prompt,
        provider=target.provider,
        model=target.model,
        system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
        temperature=SUMMARY_TEMPERATURE,
        response_schema=SummaryDraft,
        timeout_seconds=resolve_request_timeout(),
        metadata={"task": "product_summary_enriched", "product_id": product_id},
    )
    response = generate_with_retry(
        analyzer_service.gateway, request, resolve_retry_policy()
    )
    if not response.success:
        raise RuntimeError(response.error_message or "summary generation failed")

    parsed = SummaryDraft.model_validate(
        json.loads(_strip_code_fence(response.content or ""))
    )
    return validate_summary(parsed)


def _try_summary(prompt: str, product_id: str) -> Optional[SummaryDraft]:
    targets = build_target_chain(
        analyzer_service.gateway,
        primary=os.getenv("GEMINI_MODEL") or None,
        capability=TASK_DATASET_SUMMARY,
        per_provider_limit=5,
    )
    if not targets:
        logger.warning("No configured AI target for summary generation.")
        return None
    state = run_intelligence_graph(
        targets, lambda target: _attempt_summary(prompt, target, product_id)
    )
    return state.get("result")


def generate_summary(
    product_id_or_source_id: str,
    aspects: Optional[List[AspectResult]] = None,
) -> Optional[SummaryDraft]:
    """Generate a grounded ``summary`` + ``best_for``.

    Returns ``None`` when the AI is unavailable or its output stays invalid —
    the caller then marks ``ai_unavailable`` and keeps the factual statistics.
    """
    product, reviews = load_product_corpus(product_id_or_source_id)
    if product is None or not reviews:
        return None

    source_product_id = str(product.get("source_product_id"))
    product_name = str(product.get("product_title") or source_product_id)
    category = str(product.get("category") or "product")

    if not analyzer_service.is_configured():
        logger.warning("AI provider not configured; no summary for %s", source_product_id)
        return None

    started = time.perf_counter()
    outcome = "failure"

    try:
        formatted = "\n".join(
            f"- [Review {r.get('source_review_id')} | {r.get('sentiment', 'neutral')} | "
            f"{r.get('rating')}★] {r.get('review_text', '')}"
            for r in reviews[:MAX_CONTEXT_REVIEWS]
        )

        aspect_lines = (
            "\n".join(
                f"- {a.aspect_name} ({a.sentiment}, mentioned in {a.mention_count} reviews)"
                for a in (aspects or [])
            )
            or "- (no recurring aspects were identified)"
        )

        prompt = f"""Product: {product_name} ({category})

Recurring aspects identified from the reviews:
{aspect_lines}

Customer Reviews from the canonical dataset:
\"\"\"
{formatted}
\"\"\"

Summarize ONLY these reviews and the aspects above, following your system instructions, and return structured JSON."""

        draft: Optional[SummaryDraft] = None
        for _ in range(SUMMARY_ATTEMPTS):
            draft = _try_summary(prompt, source_product_id)
            if draft is not None:
                break

        if draft is None:
            return None

        outcome = "success"
        return draft
    except Exception as exc:
        logger.warning("Summary generation failed for %s: %s", source_product_id, exc)
        return None
    finally:
        emit_ai_outcome(
            task="product_summary_enriched",
            outcome=outcome,
            provider=None,
            model=None,
            fallback=None,
            retry_attempts=None,
            retry_count=None,
            cache="disabled",
            rag_status=None,
            provider_latency_ms=None,
            total_ms=round((time.perf_counter() - started) * 1000),
        )
