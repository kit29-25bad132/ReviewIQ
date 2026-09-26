import json
import logging
import os
import re
from typing import List, Optional
from dotenv import load_dotenv

from models.ecommerce import AISummaryResponse
from services.ai.contracts import AIGenerationRequest, ModelRef
from services.ai.errors import AIProviderError
from services.ai.registry import GEMINI_PROVIDER, TASK_DATASET_SUMMARY
from services.ai.routing import (
    build_target_chain,
    provider_configured_checker,
    skips_remaining_provider_models,
)
from services.ai.routing_policy import (
    apply_route_decision,
    route_metadata,
    select_initial_target,
)
from services.ai.retry_policy import (
    generate_with_retry,
    resolve_request_timeout,
    resolve_retry_policy,
)
from services.ai_analyzer import analyzer_service

load_dotenv()
logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_INSTRUCTION = """You are a strict Product Review Intelligence AI.
Analyze ONLY the supplied real customer reviews from the product review dataset.

Strict Rules:
1. NO HALLUCINATION RULE: Use ONLY facts, experiences, pros, and cons explicitly stated in the provided reviews. Do NOT invent features, issues, ratings, or opinions not found in the review text.
2. summary: Provide a factual 2-3 sentence executive summary synthesizing the customer feedback.
3. common_pros: List 2-5 positive points repeatedly mentioned by customers in these reviews.
4. common_cons: List 2-5 negative complaints or issues repeatedly mentioned by customers. If no cons are mentioned, return [].
5. key_themes: List 3-6 key attributes discussed (e.g., "Build Quality", "Battery Life", "Value for Money", "Ease of Use").
6. source_label: Must be exactly "Summary generated from dataset reviews".
7. Return strictly structured JSON matching the requested schema.
"""


class GeminiSummaryService:
    def summarize_product_reviews(
        self, product_title: str, category: Optional[str], sample_reviews: List[str]
    ) -> AISummaryResponse:
        if not sample_reviews:
            return AISummaryResponse(
                summary="No customer reviews are available in the dataset for this product.",
                common_pros=[],
                common_cons=[],
                key_themes=[],
                source_label="Summary generated from dataset reviews",
            )

        if not analyzer_service.is_configured():
            # Graceful fallback when no AI provider key is configured
            return AISummaryResponse(
                summary=f"Analysis based on {len(sample_reviews)} reviews in the dataset. Configure GEMINI_API_KEY (or GROQ_API_KEY / OPENROUTER_API_KEY) in backend/.env for AI executive insights.",
                common_pros=["Dataset reviews available for manual inspection below"],
                common_cons=[],
                key_themes=[category or "General"],
                source_label="Summary generated from dataset reviews",
            )

        # Build prompt with exact reviews
        formatted_reviews = "\n".join(f"- {r}" for r in sample_reviews[:40])
        prompt = f"""Product: {product_title}
Category: {category or 'General'}

Customer Reviews from Dataset:
\"\"\"
{formatted_reviews}
\"\"\"

Synthesize these dataset reviews according to your system instructions into structured JSON."""

        try:
            return self._generate_summary(prompt)
        except Exception as exc:
            logger.warning(f"AI summarization error: {exc}", exc_info=True)
            return AISummaryResponse(
                summary=f"Analysis of {len(sample_reviews)} dataset reviews available. Full reviews listed below.",
                common_pros=[],
                common_cons=[],
                key_themes=[category or "General"],
                source_label="Summary generated from dataset reviews",
            )

    def _generate_summary(self, prompt: str) -> AISummaryResponse:
        # Same provider-qualified pool as the analyzer (V2-P5): Gemini models
        # -> Groq models -> OpenRouter route, filtered to configured
        # providers; generation goes through the AI Gateway so no provider
        # SDK/HTTP detail is duplicated here.
        #
        # V2-P6: the same routing policy as review analysis selects the
        # initial target from this already-built chain (default
        # gemini_first = P5 order unchanged); the fallback loop below and its
        # provider-skip semantics are untouched.
        gemini_primary = os.getenv("GEMINI_MODEL") or None
        targets = build_target_chain(
            analyzer_service.gateway,
            primary=gemini_primary,
            capability=TASK_DATASET_SUMMARY,
            per_provider_limit=5,
        )
        decision = None
        if targets:
            decision = select_initial_target(
                targets,
                is_configured=provider_configured_checker(analyzer_service.gateway),
                task=TASK_DATASET_SUMMARY,
                override=(
                    ModelRef(provider=GEMINI_PROVIDER, model=gemini_primary)
                    if gemini_primary
                    else None
                ),
            )
            targets = apply_route_decision(targets, decision)
            logger.info(
                "Routing decision (dataset summary): strategy=%s provider=%s "
                "model=%s reason=%s",
                decision.strategy,
                decision.selected.provider,
                decision.selected.model,
                decision.reason,
            )
        first_target = targets[0] if targets else None
        skipped_providers: set = set()
        # V2-P7: same reliability layer as review analysis — retry the SAME
        # target below the loop, then fall back to the next target unchanged.
        retry_policy = resolve_retry_policy()
        request_timeout = resolve_request_timeout()

        last_error = None
        for target in targets:
            if target.provider in skipped_providers:
                # Provider-level failure already recorded; skip its remaining
                # models without another API call.
                continue
            request = AIGenerationRequest(
                prompt=prompt,
                provider=target.provider,
                model=target.model,
                system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
                temperature=0.2,
                response_schema=AISummaryResponse,
                timeout_seconds=request_timeout,
                metadata={
                    "task": TASK_DATASET_SUMMARY,
                    "fallback": target != first_target,
                    # V2-P6 internal routing audit fields (server-side only;
                    # never serialized into the API response envelope).
                    **route_metadata(decision),
                },
            )
            try:
                response = generate_with_retry(
                    analyzer_service.gateway, request, retry_policy
                )
            except ImportError:
                raise
            except AIProviderError as e:
                if skips_remaining_provider_models(e.error_type):
                    skipped_providers.add(target.provider)
                logger.warning(
                    "Summary failed with %s model %s: %s",
                    target.provider,
                    target.model,
                    e,
                )
                last_error = e
                continue
            except Exception as e:
                logger.warning(
                    "Summary failed with %s model %s: %s",
                    target.provider,
                    target.model,
                    e,
                )
                last_error = e
                continue

            if not response.success:
                if skips_remaining_provider_models(response.error_type):
                    skipped_providers.add(target.provider)
                last_error = AIProviderError(
                    response.error_message or f"Model {target.model} failed.",
                    response.error_type,
                    provider=response.provider,
                    model=response.model,
                )
                continue

            text = (response.content or "").strip()
            if text:
                return self._parse_json(text)

        if last_error:
            raise last_error
        raise RuntimeError("Empty response from Gemini model.")

    def _parse_json(self, raw_text: str) -> AISummaryResponse:
        cleaned = raw_text
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()
        data = json.loads(cleaned)
        return AISummaryResponse.model_validate(data)


gemini_summary_service = GeminiSummaryService()
