"""Phase 5B — aspect/theme extraction.

The model proposes aspects; the APPLICATION decides whether they are real:

* every aspect must cite a ``review_id`` that exists in the retrieved corpus,
* its quote must be a verbatim snippet of that review's stored text,
* its ``mention_count`` is counted by the application over the real reviews —
  the model's own count is never trusted.

An aspect that fails any of these is dropped. If the model cannot be reached,
or its output will not validate after one retry, the result is an empty list —
never an invented aspect.

Generation goes through Gemini via LangGraph (``services.intelligence.graph``),
matching the orchestration style of the review pipeline.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from models.intelligence import AspectResult, EvidenceItem
from services.ai.contracts import AIGenerationRequest
from services.ai.registry import TASK_DATASET_SUMMARY
from services.ai.retry_policy import (
    generate_with_retry,
    resolve_request_timeout,
    resolve_retry_policy,
)
from services.ai.routing import build_target_chain
from services.ai_analyzer import analyzer_service
from services.intelligence.corpus import format_review_samples, load_product_corpus
from services.intelligence.graph import run_intelligence_graph
from services.observability import emit_ai_outcome

logger = logging.getLogger(__name__)

#: Deterministic sampling. Part of the prompt contract, not a tuning knob.
ASPECT_TEMPERATURE = 0.2

#: The spec asks for 4-8 recurring themes; this is the hard upper bound.
MAX_ASPECTS = 8

#: Retries of the whole extraction (not per target) before returning [].
EXTRACTION_ATTEMPTS = 2

ASPECT_SYSTEM_INSTRUCTION = """You extract recurring product aspects from customer reviews.

Absolute rules:
1. Use ONLY the supplied reviews. Never invent an aspect, feature, specification, or opinion that is not stated in them.
2. Return between 4 and 8 aspects that recur across MULTIPLE reviews. If fewer than 4 genuinely recur, return only the ones that do — never pad the list.
3. "sentiment" must be exactly one of "positive", "negative", or "mixed", describing how the supplied reviews discuss that aspect overall.
4. "quote_review_id" must be the exact Review ID printed for one of the supplied reviews.
5. "quote_excerpt" must be a VERBATIM snippet copied from that review's text — not a paraphrase, not a summary, not a rewrite.
6. Return strictly structured JSON matching the requested schema.
"""

#: Function words ignored when deriving an aspect's literal search terms.
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "this", "that", "from", "into", "its",
        "was", "were", "are", "has", "have", "had", "not", "but", "very",
        "overall", "general", "other", "some", "any", "all", "more", "most",
        "than", "then", "when", "how", "what", "which", "who", "why",
        "aspect", "issue", "issues", "point", "points", "experience",
    }
)


class AspectExtractionItem(BaseModel):
    """One model-proposed aspect, before application grounding."""

    aspect_name: str = Field(..., min_length=1)
    sentiment: str = Field(..., min_length=1)
    quote_review_id: str = Field(..., min_length=1)
    quote_excerpt: str = Field(..., min_length=1)


class AspectExtraction(BaseModel):
    """The model's raw structured output for one product."""

    aspects: List[AspectExtractionItem] = Field(default_factory=list)


def _strip_code_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _normalize(text: str) -> str:
    """Case-fold and collapse whitespace for verbatim comparison."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def aspect_terms(aspect_name: str) -> List[str]:
    """Literal terms used to count how many real reviews mention an aspect."""
    words = re.findall(r"[a-z0-9]{3,}", str(aspect_name).lower())
    terms = [w for w in words if w not in _STOPWORDS]
    return terms or [str(aspect_name).strip().lower()]


def count_mentions(terms: List[str], lowered_reviews: List[str]) -> int:
    """Count real reviews whose text mentions any of ``terms``."""
    return sum(1 for text in lowered_reviews if any(term in text for term in terms))


def ground_aspects(
    extraction: AspectExtraction,
    reviews: List[Dict[str, Any]],
) -> List[AspectResult]:
    """Convert model proposals into grounded aspects, dropping everything fake.

    Pure and deterministic: given the same extraction and corpus it always
    returns the same list, so it can be tested without any provider call.
    """
    by_id: Dict[str, Dict[str, Any]] = {
        str(r.get("source_review_id")): r for r in reviews
    }
    lowered_reviews = [_normalize(r.get("review_text", "")) for r in reviews]

    grounded: List[AspectResult] = []
    seen: set = set()

    for item in extraction.aspects:
        name = item.aspect_name.strip()
        key = name.lower()
        if not key or key in seen:
            continue

        review = by_id.get(item.quote_review_id)
        if review is None:
            logger.info(
                "Dropping aspect %r: quote_review_id %r is not in the corpus",
                name,
                item.quote_review_id,
            )
            continue

        excerpt = item.quote_excerpt.strip()
        if not excerpt or _normalize(excerpt) not in _normalize(review.get("review_text", "")):
            logger.info(
                "Dropping aspect %r: quote is not verbatim text from %s",
                name,
                item.quote_review_id,
            )
            continue

        mention_count = count_mentions(aspect_terms(name), lowered_reviews)
        if mention_count < 1:
            logger.info("Dropping aspect %r: no real review mentions it", name)
            continue

        try:
            grounded.append(
                AspectResult(
                    aspect_name=name,
                    sentiment=item.sentiment.strip().lower(),
                    mention_count=mention_count,
                    representative_quote=EvidenceItem(
                        review_id=item.quote_review_id, excerpt=excerpt
                    ),
                )
            )
        except ValidationError as exc:
            logger.info("Dropping aspect %r: %s", name, exc)
            continue

        seen.add(key)

    # Most-mentioned first, then alphabetical for a deterministic order.
    grounded.sort(key=lambda a: (-a.mention_count, a.aspect_name.lower()))
    return grounded[:MAX_ASPECTS]


def _attempt_extraction(
    samples: List[str],
    target: Any,
    product_id: str,
) -> AspectExtraction:
    """One generation attempt against one target. Raises on any failure."""
    formatted = "\n".join(f"- {s}" for s in samples)
    prompt = f"""Product: {product_id}

Customer Reviews from the canonical dataset:
\"\"\"
{formatted}
\"\"\"

Extract the recurring product aspects from ONLY these reviews, following your system instructions, and return structured JSON."""

    request = AIGenerationRequest(
        prompt=prompt,
        provider=target.provider,
        model=target.model,
        system_instruction=ASPECT_SYSTEM_INSTRUCTION,
        temperature=ASPECT_TEMPERATURE,
        response_schema=AspectExtraction,
        timeout_seconds=resolve_request_timeout(),
        metadata={"task": "product_aspects", "product_id": product_id},
    )

    response = generate_with_retry(
        analyzer_service.gateway, request, resolve_retry_policy()
    )
    if not response.success:
        raise RuntimeError(response.error_message or "aspect extraction failed")

    parsed = AspectExtraction.model_validate(
        json.loads(_strip_code_fence(response.content or ""))
    )
    if not parsed.aspects:
        raise ValueError("model returned no aspects")
    return parsed


def _try_extraction(
    samples: List[str], product_id: str
) -> Optional[AspectExtraction]:
    """Run one full pass over the provider chain. Returns None if all fail."""
    targets = build_target_chain(
        analyzer_service.gateway,
        primary=os.getenv("GEMINI_MODEL") or None,
        capability=TASK_DATASET_SUMMARY,
        per_provider_limit=5,
    )
    if not targets:
        logger.warning("No configured AI target for aspect extraction.")
        return None

    state = run_intelligence_graph(
        targets, lambda target: _attempt_extraction(samples, target, product_id)
    )
    return state.get("result")


def extract_aspects(product_id_or_source_id: str) -> List[AspectResult]:
    """Extract grounded, recurring aspects for a product from real reviews.

    Returns an empty list when there is nothing real to work with (unknown
    product, no reviews, no AI provider, or repeated invalid model output).
    """
    product, reviews = load_product_corpus(product_id_or_source_id)
    if product is None or not reviews:
        return []

    source_product_id = str(product.get("source_product_id"))
    if not analyzer_service.is_configured():
        logger.warning(
            "AI provider not configured; returning no aspects for %s", source_product_id
        )
        return []

    samples = format_review_samples(reviews)
    started = time.perf_counter()
    outcome = "failure"
    extraction: Optional[AspectExtraction] = None

    try:
        for _ in range(EXTRACTION_ATTEMPTS):
            extraction = _try_extraction(samples, source_product_id)
            if extraction is not None:
                break

        if extraction is None:
            return []

        grounded = ground_aspects(extraction, reviews)
        outcome = "success" if grounded else "failure"
        return grounded
    except Exception as exc:
        logger.warning(
            "Aspect extraction failed for %s: %s", source_product_id, exc
        )
        return []
    finally:
        emit_ai_outcome(
            task="product_aspects",
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
