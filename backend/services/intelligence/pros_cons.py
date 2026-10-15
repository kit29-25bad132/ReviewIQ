"""Phase 5C — pros/cons with traceable evidence (AI + RAG).

Grounding rules, enforced by the application:

* retrieval is real: candidate reviews come from a pgvector similarity search
  scoped to the product and the canonical source;
* every claim's ``review_id`` must resolve to a real row in that product's
  reviews — a claim with no resolvable citation is DROPPED;
* every ``excerpt`` is sliced verbatim out of the resolved review text, so the
  model never supplies a paraphrase;
* ``support_count`` is the number of validated citations, never an
  extrapolated estimate (the legacy keyword service multiplied sample counts).

RAG is controlled by ``RAG_INTELLIGENCE_ENABLED`` (default ON). It is separate
from the global ``RAG_ENABLED`` so enabling product intelligence does not
change the single-review analysis path.
"""

import json
import logging
import os
import re
import time
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from models.intelligence import ClaimWithEvidence, EvidenceItem
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
from services.rag.config import RAGConfig
from services.rag.retrieval import RagRetrievalService, RagRetrievalStatus
from services.retrieval.contracts import CANONICAL_REVIEW_SOURCE
from services.retrieval.vector_repository import ReviewSearchFilters

logger = logging.getLogger(__name__)

CLAIMS_TEMPERATURE = 0.2
MAX_CLAIMS_PER_SIDE = 5
MAX_EVIDENCE_PER_CLAIM = 5
EXCERPT_MAX_CHARS = 240
RAG_TOP_K = 20
RAG_QUERY_ATTEMPTS = 2

_FALSE_VALUES = {"0", "false", "no", "off"}

PROS_CONS_SYSTEM_INSTRUCTION = """You produce pros and cons for a product from customer reviews.

Absolute rules:
1. Use ONLY the supplied reviews. Never invent a feature, specification, price, or opinion that is not stated in them.
2. Return at most 5 pros and at most 5 cons. Fewer is correct when the reviews do not support more; return an empty list rather than padding.
3. Every claim MUST cite the Review IDs of the supplied reviews that support it, in "evidence_review_ids". A claim you cannot cite must be omitted.
4. Cite only Review IDs that appear in the supplied reviews. Never invent an ID.
5. Do not restate the same claim twice in different words.
6. "pros" are things customers explicitly praise; "cons" are things customers explicitly complain about.
7. Return strictly structured JSON matching the requested schema.
"""


class ClaimDraft(BaseModel):
    """One model-proposed claim, citing supplied review ids."""

    claim: str = Field(..., min_length=1)
    evidence_review_ids: List[str] = Field(default_factory=list)


class ClaimsDraft(BaseModel):
    """The model's raw structured output for one product."""

    pros: List[ClaimDraft] = Field(default_factory=list)
    cons: List[ClaimDraft] = Field(default_factory=list)


def intelligence_rag_enabled() -> bool:
    """Resolve ``RAG_INTELLIGENCE_ENABLED``; default ON, explicit false wins."""
    raw = (os.getenv("RAG_INTELLIGENCE_ENABLED") or "").strip().lower()
    if not raw:
        return True
    return raw not in _FALSE_VALUES


def build_rag_service() -> RagRetrievalService:
    """Build a retrieval service for this stage only.

    Reuses the shared RAG config but forces ``enabled`` from the
    intelligence-specific flag and widens ``top_k`` for claim grounding.
    """
    base = RAGConfig.from_env()
    return RagRetrievalService(replace(base, enabled=intelligence_rag_enabled(), top_k=RAG_TOP_K))


def retrieve_evidence(
    source_product_id: str, queries: List[str]
) -> Tuple[List[Any], str]:
    """Semantic-search the product's reviews. Never raises.

    Returns ``(results, status)`` where ``status`` is the last retrieval
    status seen — ``RagRetrievalStatus.DISABLED.value`` when the flag is off.
    """
    service = build_rag_service()
    collected: List[Any] = []
    seen: set = set()
    status = RagRetrievalStatus.EMPTY.value

    for query in queries:
        outcome = service.retrieve(
            query,
            filters=ReviewSearchFilters(
                product_id=source_product_id, source=CANONICAL_REVIEW_SOURCE
            ),
        )
        status = str(outcome.metadata.status)
        for result in outcome.results:
            review_id = str(result.review_id)
            if review_id not in seen:
                seen.add(review_id)
                collected.append(result)

    return collected, status


def _strip_code_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def excerpt_of(review_text: str, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    """Slice a verbatim excerpt out of real review text (whitespace collapsed)."""
    collapsed = re.sub(r"\s+", " ", str(review_text or "")).strip()
    return collapsed[:max_chars].strip()


def excerpt_for_claim(
    claim: str, review_text: str, max_chars: int = EXCERPT_MAX_CHARS
) -> str:
    """Pick the most claim-relevant VERBATIM sentence from a cited review.

    A blind prefix can cite a review that talks about something else entirely.
    Preferring the sentence with the greatest overlap with the claim keeps the
    excerpt both verbatim (it is a real substring) and actually supportive.
    Falls back to the leading text when no sentence overlaps.
    """
    collapsed = re.sub(r"\s+", " ", str(review_text or "")).strip()
    if not collapsed:
        return ""

    terms = {word for word in re.findall(r"[a-z0-9]{4,}", str(claim).lower())}
    if terms:
        best_sentence: Optional[str] = None
        best_score = 0
        for sentence in re.split(r"(?<=[.!?])\s+", collapsed):
            lowered = sentence.lower()
            score = sum(1 for term in terms if term in lowered)
            if score > best_score:
                best_sentence, best_score = sentence, score
        if best_sentence is not None and best_score > 0:
            return best_sentence.strip()[:max_chars].strip()

    return collapsed[:max_chars].strip()


def build_claims(
    drafts: List[ClaimDraft],
    corpus_by_id: Dict[str, Dict[str, Any]],
    limit: int = MAX_CLAIMS_PER_SIDE,
) -> List[ClaimWithEvidence]:
    """Convert claim drafts into validated claims, dropping any unsupported one.

    Pure and deterministic: testable without a provider call.
    """
    claims: List[ClaimWithEvidence] = []
    seen_claims: set = set()

    for draft in drafts:
        claim_text = draft.claim.strip()
        key = claim_text.lower()
        if not claim_text or key in seen_claims:
            continue

        resolvable_ids: List[str] = []
        for review_id in draft.evidence_review_ids:
            candidate = str(review_id).strip()
            if candidate in corpus_by_id and candidate not in resolvable_ids:
                resolvable_ids.append(candidate)

        if not resolvable_ids:
            logger.info("Dropping claim %r: no resolvable evidence", claim_text[:60])
            continue

        # Build evidence defensively: a cited review with empty/unusable text
        # contributes no citation rather than raising, and the claim is dropped
        # if nothing usable remains.
        evidence: List[EvidenceItem] = []
        for review_id in resolvable_ids[:MAX_EVIDENCE_PER_CLAIM]:
            excerpt = excerpt_for_claim(
                claim_text, corpus_by_id[review_id].get("review_text", "")
            )
            if not excerpt:
                continue
            try:
                evidence.append(EvidenceItem(review_id=review_id, excerpt=excerpt))
            except ValidationError as exc:
                logger.info("Skipping unusable evidence for %s: %s", review_id, exc)

        if not evidence:
            logger.info("Dropping claim %r: no usable excerpt", claim_text[:60])
            continue

        try:
            claims.append(
                ClaimWithEvidence(
                    claim=claim_text,
                    evidence=evidence,
                    support_count=len(evidence),
                )
            )
        except ValidationError as exc:
            logger.info("Dropping claim %r: %s", claim_text[:60], exc)
            continue

        seen_claims.add(key)
        if len(claims) >= limit:
            break

    return claims


def _attempt_claims(prompt: str, target: Any, product_id: str) -> ClaimsDraft:
    """One generation attempt against one target. Raises on any failure."""
    request = AIGenerationRequest(
        prompt=prompt,
        provider=target.provider,
        model=target.model,
        system_instruction=PROS_CONS_SYSTEM_INSTRUCTION,
        temperature=CLAIMS_TEMPERATURE,
        response_schema=ClaimsDraft,
        timeout_seconds=resolve_request_timeout(),
        metadata={"task": "product_pros_cons", "product_id": product_id},
    )
    response = generate_with_retry(
        analyzer_service.gateway, request, resolve_retry_policy()
    )
    if not response.success:
        raise RuntimeError(response.error_message or "pros/cons generation failed")

    parsed = ClaimsDraft.model_validate(
        json.loads(_strip_code_fence(response.content or ""))
    )
    if not parsed.pros and not parsed.cons:
        raise ValueError("model returned no claims")
    return parsed


def _try_claims(prompt: str, product_id: str) -> Optional[ClaimsDraft]:
    targets = build_target_chain(
        analyzer_service.gateway,
        primary=os.getenv("GEMINI_MODEL") or None,
        capability=TASK_DATASET_SUMMARY,
        per_provider_limit=5,
    )
    if not targets:
        logger.warning("No configured AI target for pros/cons generation.")
        return None
    state = run_intelligence_graph(
        targets, lambda target: _attempt_claims(prompt, target, product_id)
    )
    return state.get("result")


def generate_pros_cons(
    product_id_or_source_id: str,
) -> Tuple[List[ClaimWithEvidence], List[ClaimWithEvidence]]:
    """Return ``(pros, cons)`` grounded in real, evidence-validated reviews."""
    product, reviews = load_product_corpus(product_id_or_source_id)
    if product is None or not reviews:
        return [], []

    source_product_id = str(product.get("source_product_id"))
    product_name = str(product.get("product_title") or source_product_id)
    category = str(product.get("category") or "product")

    if not analyzer_service.is_configured():
        logger.warning("AI provider not configured; no pros/cons for %s", source_product_id)
        return [], []

    corpus_by_id: Dict[str, Dict[str, Any]] = {
        str(r.get("source_review_id")): r for r in reviews
    }

    started = time.perf_counter()
    outcome = "failure"
    rag_status: Optional[str] = None

    try:
        # 1. RAG retrieval (real pgvector search over this product's reviews).
        retrieved, rag_status = retrieve_evidence(
            source_product_id,
            [
                f"What do customers praise most about the {product_name} {category}?",
                f"What do customers complain about with the {product_name} {category}?",
            ],
        )
        retrieved_ids = [str(r.review_id) for r in retrieved]

        # Grounding context: RAG hits when available, else the full corpus so a
        # retrieval outage degrades quality without inventing anything.
        context_reviews = [
            corpus_by_id[rid] for rid in retrieved_ids if rid in corpus_by_id
        ]
        if not context_reviews:
            logger.info(
                "RAG returned no usable context for %s (status=%s); using corpus",
                source_product_id,
                rag_status,
            )
            context_reviews = reviews

        formatted = "\n".join(
            f"- [Review {r.get('source_review_id')} | {r.get('sentiment', 'neutral')} | "
            f"{r.get('rating')}★] {r.get('review_text', '')}"
            for r in context_reviews
        )
        prompt = f"""Product: {product_name} ({category})

Reviews retrieved from the canonical dataset:
\"\"\"
{formatted}
\"\"\"

Produce pros and cons for this product using ONLY these reviews, following your
system instructions, and return structured JSON. Every claim must cite the
Review IDs shown above."""

        draft: Optional[ClaimsDraft] = None
        for _ in range(RAG_QUERY_ATTEMPTS):
            draft = _try_claims(prompt, source_product_id)
            if draft is not None:
                break

        if draft is None:
            return [], []

        pros = build_claims(draft.pros, corpus_by_id)
        cons = build_claims(draft.cons, corpus_by_id)
        outcome = "success" if (pros or cons) else "failure"
        return pros, cons
    except Exception as exc:
        logger.warning("Pros/cons generation failed for %s: %s", source_product_id, exc)
        return [], []
    finally:
        emit_ai_outcome(
            task="product_pros_cons",
            outcome=outcome,
            provider=None,
            model=None,
            fallback=None,
            retry_attempts=None,
            retry_count=None,
            cache="disabled",
            rag_status=rag_status,
            provider_latency_ms=None,
            total_ms=round((time.perf_counter() - started) * 1000),
        )
