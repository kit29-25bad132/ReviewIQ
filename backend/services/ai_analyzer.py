import json
import logging
import os
import re
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv

from models.review import ReviewAnalysis
from services.ai.contracts import AIGenerationRequest, ModelRef
from services.ai.errors import AIProviderError
from services.ai.gateway import AIGateway
from services.ai.providers.gemini import GeminiProvider
from services.ai.providers.groq import GroqProvider
from services.ai.providers.openrouter import OpenRouterProvider
from services.ai.registry import (
    DEFAULT_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
    GEMINI_PROVIDER,
    GROQ_PROVIDER,
    OPENROUTER_PROVIDER,
    TASK_REVIEW_ANALYSIS,
    model_registry,
)
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
from services.analysis_graph import (
    EmptyResponseError,
    SkipTargetError,
    run_analysis_graph,
)
from services.grounding_service import ground_analysis
from services.rag.config import RAGConfig
from services.rag.context_builder import RagContext, build_rag_context
from services.rag.prompting import build_analysis_prompt
from services.rag.retrieval import RagRetrievalResult, RagRetrievalService

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

    Kept for backwards compatibility (Gemini-only view of the chain); the
    analysis pipeline now uses the provider-qualified
    ``services.ai.routing.build_target_chain`` instead.
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

    Provider SDK/HTTP access is delegated to the AI Gateway/provider adapters;
    this service owns configuration, prompt construction, output parsing/
    validation, and evidence grounding — the provider-neutral parts of the
    pipeline.

    V2-P3: an optional best-effort RAG stage (disabled unless ``RAG_ENABLED``)
    retrieves similar reviews and builds a context block that shapes the
    prompt. Grounding remains original-review-only; retrieval failures never
    block analysis.

    V2-P5: fallback targets are provider-qualified ``ModelRef`` entries —
    Gemini's verified model chain, then Groq's model chain, then OpenRouter's
    single ``openrouter/free`` route — filtered to configured providers. An
    AUTHENTICATION/CONFIGURATION failure skips the remaining models of that
    provider; every other failure continues along the model chain.

    V2-P6: before falling back, ``services.ai.routing_policy`` picks the
    initial target from that chain (default ``gemini_first`` preserves P5
    order exactly; opt-in ``cost_aware`` only moves the chosen target to the
    head). Routing never replaces the fallback loop above.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        gateway: Optional[AIGateway] = None,
        *,
        rag_config: Optional[RAGConfig] = None,
        rag_service: Optional[RagRetrievalService] = None,
    ):
        self._api_key = api_key
        self._gateway = gateway
        self._rag_config = rag_config
        self._rag_service = rag_service

    @property
    def api_key(self) -> str:
        """Dynamically retrieve the API key from constructor or environment."""
        if self._api_key:
            return self._api_key.strip()
        load_dotenv(override=True)
        key = os.getenv("GEMINI_API_KEY", "")
        return key.strip() if key else ""

    def is_configured(self) -> bool:
        """True when at least one AI provider has usable credentials.

        Gemini/Groq/OpenRouter each count independently; a missing Groq or
        OpenRouter key never blocks analysis that Gemini can serve (and vice
        versa).
        """
        return any(
            provider.is_configured() for provider in self.gateway.providers.values()
        )

    @property
    def gateway(self) -> AIGateway:
        """The shared AI Gateway (all provider adapters wired to this service).

        Built lazily and cached; the Gemini adapter resolves its API key on
        every call (Groq/OpenRouter read their env vars per call) so
        environment changes are respected without rebuilding the gateway.
        Adapters without credentials are registered but filtered out of the
        fallback chain by ``services.ai.routing.build_target_chain``.
        """
        if self._gateway is None:
            gemini = GeminiProvider(api_key_provider=lambda: self.api_key)
            self._gateway = AIGateway(
                providers={
                    gemini.name: gemini,
                    GROQ_PROVIDER: GroqProvider(),
                    OPENROUTER_PROVIDER: OpenRouterProvider(),
                },
                registry=model_registry,
                default_provider=GEMINI_PROVIDER,
            )
        return self._gateway

    @property
    def rag_config(self) -> RAGConfig:
        """Resolved RAG settings (constructor override, else environment)."""
        if self._rag_config is not None:
            return self._rag_config
        return RAGConfig.from_env()

    def _retrieve_rag_context(
        self, review_text: str, service: RagRetrievalService
    ) -> Tuple[Optional[RagContext], Optional[RagRetrievalResult]]:
        """Best-effort RAG stage: never raises.

        Returns ``(context, retrieval_result)``; both are ``None`` only when
        the stage is disabled. Logged fields are limited to safe metadata
        (status/counts/thresholds) — the review text and query are never
        written to logs.
        """
        if not service.config.enabled:
            return None, None
        result = service.retrieve(review_text)
        context: Optional[RagContext] = None
        try:
            context = build_rag_context(result.results, service.config)
        except Exception:
            logger.warning(
                "RAG context construction failed; continuing without context.",
                exc_info=True,
            )
        meta = result.metadata
        logger.info(
            "RAG retrieval status=%s retrieved=%d top_k=%d threshold=%.4f "
            "context_reviews=%d context_chars=%d error_type=%s",
            meta.status,
            meta.retrieved_count,
            meta.top_k,
            meta.similarity_threshold,
            len(context.reviews) if context else 0,
            context.char_count if context else 0,
            meta.error_type,
        )
        return context, result

    def analyze_review(self, review_text: str) -> ReviewAnalysis:
        """
        Analyzes a customer review via the AI Gateway (any configured provider).
        Returns a validated ReviewAnalysis Pydantic instance.
        """
        if not self.is_configured():
            raise ValueError(
                "No AI provider API key is configured. Please set GEMINI_API_KEY "
                "(or GROQ_API_KEY / OPENROUTER_API_KEY) in backend/.env"
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
        """Run the analysis pipeline with LangGraph-orchestrated fallback.

        Retained name for backwards compatibility. Provider access now happens
        behind the AI Gateway; this method owns the provider-neutral workflow:
        optional RAG retrieval -> generation -> parsing -> Pydantic validation
        -> evidence grounding.

        V2-P5: the chain is a list of provider-qualified ``ModelRef`` targets
        (Gemini model chain -> Groq model chain -> OpenRouter route), filtered
        to configured providers. Each attempt sends the target's provider and
        model to the gateway; an AUTHENTICATION/CONFIGURATION failure marks
        that provider skipped so its remaining models are advanced past
        without further API calls.

        V2-P3: when the RAG stage is enabled, retrieval runs once inside the
        graph (before the first attempt); the retrieved context shapes every
        attempt's prompt while grounding stays original-review-only. When
        disabled or empty, prompts are byte-identical to V1/P2.

        V2-P6: before the first attempt, the routing policy
        (``services.ai.routing_policy``) selects the *initial* target from
        the already-built P5 chain and moves it to the head; every other
        target keeps its exact relative order, so the fallback tail is P5
        unchanged. Routing never builds a chain, never probes the network,
        and cannot bypass provider configuration checks. The retrieved RAG
        context (V2-P3) still runs once and is shared across every attempt;
        grounding and validation still run on every success.
        """
        gemini_primary = os.getenv("GEMINI_MODEL") or None
        targets = build_target_chain(
            self.gateway,
            primary=gemini_primary,
            capability=TASK_REVIEW_ANALYSIS,
            per_provider_limit=5,
        )
        decision = None
        if targets:
            decision = select_initial_target(
                targets,
                is_configured=provider_configured_checker(self.gateway),
                task=TASK_REVIEW_ANALYSIS,
                override=(
                    ModelRef(provider=GEMINI_PROVIDER, model=gemini_primary)
                    if gemini_primary
                    else None
                ),
            )
            targets = apply_route_decision(targets, decision)
            logger.info(
                "Routing decision: strategy=%s provider=%s model=%s reason=%s",
                decision.strategy,
                decision.selected.provider,
                decision.selected.model,
                decision.reason,
            )
        first_target = targets[0] if targets else None
        # Providers whose credentials/config failed: their remaining targets
        # are advanced past without API calls (error-aware provider skip).
        skipped_providers: set = set()

        rag_service = self._rag_service or RagRetrievalService(self.rag_config)
        # Context is shared between the graph's retrieval node and attempt_fn
        # via a per-request holder; attempt_fn keeps its two-argument signature.
        context_holder: Dict[str, Optional[RagContext]] = {}

        def retrieve_fn(text: str) -> Optional[RagContext]:
            context, _ = self._retrieve_rag_context(text, rag_service)
            context_holder["context"] = context
            return context

        def attempt_fn(text: str, target: ModelRef) -> ReviewAnalysis:
            if target.provider in skipped_providers:
                # Provider already failed at the provider level; skip its
                # remaining models without another API call or a new error.
                raise SkipTargetError(
                    f"Skipping remaining targets for provider '{target.provider}'."
                )
            prompt, system_instruction = build_analysis_prompt(
                text, context_holder.get("context"), SYSTEM_INSTRUCTION
            )
            request = AIGenerationRequest(
                prompt=prompt,
                provider=target.provider,
                model=target.model,
                system_instruction=system_instruction,
                temperature=0.2,
                response_schema=ReviewAnalysis,
                metadata={
                    "task": TASK_REVIEW_ANALYSIS,
                    "fallback": target != first_target,
                    # V2-P6 internal routing audit fields (server-side only;
                    # never serialized into the API response envelope).
                    **route_metadata(decision),
                },
            )
            # Provider-neutral error surface: the gateway/adapters return a
            # normalized failure instead of leaking SDK exceptions.
            try:
                response = self.gateway.generate(request)
            except AIProviderError as err:
                if skips_remaining_provider_models(err.error_type):
                    skipped_providers.add(target.provider)
                raise
            if not response.success:
                if skips_remaining_provider_models(response.error_type):
                    skipped_providers.add(target.provider)
                raise AIProviderError(
                    response.error_message or f"Model {target.model} failed.",
                    response.error_type,
                    provider=response.provider,
                    model=response.model,
                )
            content = (response.content or "").strip()
            if not content:
                # Empty output is an attempt failure that advances the model
                # index without replacing a previously recorded real error.
                raise EmptyResponseError(
                    f"Empty response received from model {target.model}."
                )
            logger.info(f"Review analysis succeeded using model: {target.model}")
            analysis = self._parse_and_validate(content)
            # Phase 2: deterministic evidence grounding against the original
            # review text. Unsupported evidence-backed items are filtered out
            # before the analysis is returned. Grounding never raises: a
            # filtered-but-valid analysis is success. Grounding runs for every
            # provider — no provider can bypass it.
            return ground_analysis(text, analysis)

        final_state = run_analysis_graph(
            review_text,
            targets,
            attempt_fn,
            retrieve_fn=retrieve_fn if rag_service.config.enabled else None,
        )
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
