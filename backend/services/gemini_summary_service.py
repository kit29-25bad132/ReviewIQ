import json
import logging
import os
import re
from typing import List, Optional
from dotenv import load_dotenv

from models.ecommerce import AISummaryResponse
from services.ai.contracts import AIGenerationRequest
from services.ai.errors import AIProviderError
from services.ai.registry import GEMINI_PROVIDER, TASK_DATASET_SUMMARY
from services.ai_analyzer import _build_model_list, analyzer_service

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
            # Graceful fallback if Gemini API key is not configured
            return AISummaryResponse(
                summary=f"Analysis based on {len(sample_reviews)} reviews in the dataset. Configure GEMINI_API_KEY in backend/.env for AI executive insights.",
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
        # Same verified Gemini-only model pool as the analyzer (max 5,
        # GEMINI_MODEL first); generation goes through the AI Gateway so no
        # Gemini SDK detail is duplicated here.
        models_to_try = _build_model_list(os.getenv("GEMINI_MODEL"))

        last_error = None
        for index, model_name in enumerate(models_to_try):
            request = AIGenerationRequest(
                prompt=prompt,
                provider=GEMINI_PROVIDER,
                model=model_name,
                system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
                temperature=0.2,
                response_schema=AISummaryResponse,
                metadata={"task": TASK_DATASET_SUMMARY, "fallback": index > 0},
            )
            try:
                response = analyzer_service.gateway.generate(request)
            except ImportError:
                raise
            except Exception as e:
                logger.warning(f"Summary failed with model {model_name}: {e}")
                last_error = e
                continue

            if not response.success:
                last_error = AIProviderError(
                    response.error_message or f"Model {model_name} failed.",
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
