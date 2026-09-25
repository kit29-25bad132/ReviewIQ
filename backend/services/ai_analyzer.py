import json
import logging
import os
import re
from typing import Optional
from dotenv import load_dotenv

from models.review import ReviewAnalysis
from services.ai.contracts import AIGenerationRequest
from services.ai.errors import AIProviderError
from services.ai.gateway import AIGateway
from services.ai.providers.gemini import GeminiProvider
from services.ai.registry import (
    DEFAULT_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
    GEMINI_PROVIDER,
    TASK_REVIEW_ANALYSIS,
    model_registry,
)
from services.analysis_graph import EmptyResponseError, run_analysis_graph
from services.grounding_service import ground_analysis

load_dotenv()
logger = logging.getLogger(__name__)

# Model names live in the model registry (services/ai/registry.py) and are
# imported here (re-exported) for backwards compatibility with existing
# callers/tests: DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES.


def _build_model_list(primary: Optional[str]) -> list:
    """Bounded, provider-neutral model chain (configured/primary first, then
    the registry fallback pool, max 5 attempts, deduplicated).

    Model ordering is owned by the registry so it is never hardcoded across
    the codebase, and future providers can be added without touching callers.
    """
    return model_registry.chain(
        GEMINI_PROVIDER,
        primary or None,
        capability=TASK_REVIEW_ANALYSIS,
        limit=5,
    )


SYSTEM_INSTRUCTION = """You are a Product Review Analysis AI.
Analyze the provided customer review and extract ONLY information supported by the review text.

Return strictly structured JSON with these fields:

1. sentiment: Must be strictly one of "positive", "negative", "neutral", or "mixed".
   - If the review contains meaningful positive AND negative feedback, classify the overall sentiment as "mixed". Do not force "positive" or "negative" when both are materially present.
   - Use "neutral" for purely factual reviews with no clear positive or negative stance.
2. rating: An integer from 1 to 5, or null.
   - If the review explicitly mentions a rating (e.g. "5/5", "4 stars", "rating: 2"), use that exact integer and set rating_source to "explicit".
   - If no explicit rating is present but the overall sentiment clearly supports one, you may infer an integer 1-5 and set rating_source to "inferred".
   - If no reliable rating can be determined from the review, set rating to null and rating_source to "not_found". Do NOT invent a rating just to fill the field.
   - rating must NEVER be less than 1 or greater than 5 when non-null. Do not output fractional ratings (e.g. 4.5).
3. rating_source: Must be strictly one of "explicit", "inferred", or "not_found".
   - rating null requires rating_source "not_found".
   - rating 1-5 requires rating_source "explicit" or "inferred".
4. summary: Provide a concise, clear 1-2 sentence summary of the main points actually present in the review. Do not introduce information absent from the review, and do not contradict the review content.
5. aspects: Identify the distinct aspects actually discussed in the review (e.g. "battery", "camera", "display"). Assign each aspect its own sentiment independently — different aspects in the same review may have different sentiments. Example: for "The battery lasts all day, but the camera is disappointing." produce battery -> positive, camera -> negative, and overall sentiment -> mixed. Each aspect object has fields "aspect", "sentiment" (one of "positive", "negative", "neutral", "mixed"), and "evidence" (text from the review supporting that aspect sentiment). Include only aspects actually discussed in the review. If none, return [].
6. pros: List of objects with fields "point" (concise positive claim) and "evidence" (text from the review supporting the claim). List ONLY positive aspects actually supported by the review. If no clear pros exist, return [].
7. cons: List of objects with fields "point" (concise negative claim) and "evidence" (text from the review supporting the claim). List ONLY negative aspects actually supported by the review. If no clear cons exist, return [].
8. ANTI-HALLUCINATION RULE:
   - Do NOT invent or assume product features, accessories, or experiences not explicitly mentioned in the review.
   - Every "evidence" string must be text actually present in the review (minor case/whitespace/punctuation differences are acceptable).
9. Return strictly structured JSON matching the requested schema. Do NOT include markdown code fences, headers, or any text outside the JSON object.
"""


class AIAnalyzerService:
    """Service handling AI product review analysis with structured outputs.

    Gemini SDK access is delegated to the AI Gateway/provider adapter; this
    service owns configuration, prompt construction, output parsing/validation,
    and evidence grounding — the provider-neutral parts of the pipeline.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        gateway: Optional[AIGateway] = None,
    ):
        self._api_key = api_key
        self._gateway = gateway

    @property
    def api_key(self) -> str:
        """Dynamically retrieve the API key from constructor or environment."""
        if self._api_key:
            return self._api_key.strip()
        load_dotenv(override=True)
        key = os.getenv("GEMINI_API_KEY", "")
        return key.strip() if key else ""

    def is_configured(self) -> bool:
        """Check if a non-placeholder Gemini API key is configured."""
        key = self.api_key
        return bool(key and key != "YOUR_GEMINI_API_KEY_HERE" and key != "your_gemini_api_key_here")

    @property
    def gateway(self) -> AIGateway:
        """The shared AI Gateway (Gemini adapter wired to this service's key).

        Built lazily and cached; the adapter resolves the API key on every call
        so environment changes are respected without rebuilding the gateway.
        """
        if self._gateway is None:
            provider = GeminiProvider(api_key_provider=lambda: self.api_key)
            self._gateway = AIGateway(
                providers={provider.name: provider},
                registry=model_registry,
                default_provider=GEMINI_PROVIDER,
            )
        return self._gateway

    def analyze_review(self, review_text: str) -> ReviewAnalysis:
        """
        Analyzes a customer review using Google Gemini API.
        Returns a validated ReviewAnalysis Pydantic instance.
        """
        if not self.is_configured():
            raise ValueError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env"
            )

        # Modern google-genai SDK only (legacy google-generativeai support was
        # removed; see docs/19_DECISIONS.md ADR-003).
        try:
            return self._call_google_genai(review_text)
        except ImportError:
            raise RuntimeError(
                "The 'google-genai' SDK is not installed. "
                "Install backend dependencies with: pip install -r backend/requirements.txt"
            )

    def _call_google_genai(self, review_text: str) -> ReviewAnalysis:
        """Run the analysis pipeline with LangGraph-orchestrated model fallback.

        Retained name for backwards compatibility. Gemini SDK access now happens
        behind the AI Gateway; this method owns the provider-neutral workflow:
        generation -> parsing -> Pydantic validation -> evidence grounding.
        """
        models_to_try = _build_model_list(os.getenv("GEMINI_MODEL"))
        primary_model = models_to_try[0] if models_to_try else None

        def attempt_fn(text: str, model_name: str) -> ReviewAnalysis:
            request = AIGenerationRequest(
                prompt=f"Analyze this customer product review:\n\n\"\"\"\n{text}\n\"\"\"",
                provider=GEMINI_PROVIDER,
                model=model_name,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                response_schema=ReviewAnalysis,
                metadata={
                    "task": TASK_REVIEW_ANALYSIS,
                    "fallback": model_name != primary_model,
                },
            )
            # Provider-neutral error surface: the gateway/adapters return a
            # normalized failure instead of leaking SDK exceptions.
            response = self.gateway.generate(request)
            if not response.success:
                raise AIProviderError(
                    response.error_message or f"Model {model_name} failed.",
                    response.error_type,
                    provider=response.provider,
                    model=response.model,
                )
            content = (response.content or "").strip()
            if not content:
                # Empty output is an attempt failure that advances the model
                # index without replacing a previously recorded real error.
                raise EmptyResponseError(
                    f"Empty response received from model {model_name}."
                )
            logger.info(f"Review analysis succeeded using model: {model_name}")
            analysis = self._parse_and_validate(content)
            # Phase 2: deterministic evidence grounding against the original
            # review text. Unsupported evidence-backed items are filtered out
            # before the analysis is returned. Grounding never raises: a
            # filtered-but-valid analysis is success.
            return ground_analysis(text, analysis)

        final_state = run_analysis_graph(review_text, models_to_try, attempt_fn)
        analysis = final_state.get("analysis")
        if analysis is not None:
            return analysis
        last_error = final_state.get("last_error")
        if last_error:
            raise last_error
        raise RuntimeError("Empty response received from Gemini API.")

    def _parse_and_validate(self, raw_json: str) -> ReviewAnalysis:
        """Clean JSON response (strip any accidental fences) and validate with Pydantic."""
        cleaned = raw_json
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            raise ValueError(f"Failed to parse AI output as JSON: {err}. Raw output: {cleaned[:200]}")

        # Strict validation with Pydantic model
        return ReviewAnalysis.model_validate(data)


# Global singleton service instance
analyzer_service = AIAnalyzerService()
