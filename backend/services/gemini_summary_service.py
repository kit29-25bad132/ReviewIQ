import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from models.ecommerce import AISummaryResponse, ProductAnalysisResponse
from pydantic import BaseModel, Field
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
from services.cache.llm_cache import LLMCache
from services.observability import emit_ai_outcome

load_dotenv()
logger = logging.getLogger(__name__)

# Sampling temperature for dataset summaries. Single source of truth: it is
# part of the P9 cache key material AND the request, so they can never drift.
SUMMARY_TEMPERATURE = 0.2

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

PRODUCT_ANALYSIS_SYSTEM_INSTRUCTION = """You are a strict Product Review Intelligence AI.
Analyze ONLY the supplied real customer reviews for the requested product.

Strict Rules:
1. NO HALLUCINATION RULE: Use ONLY facts, experiences, pros, and cons explicitly stated in the provided reviews. Do NOT invent features, issues, ratings, or opinions not found in the review text.
2. product_id: Must match the requested product_id exactly.
3. product_title: Must match the requested product_title exactly.
4. summary: Provide a factual 2-3 sentence executive summary synthesizing customer sentiment and experience.
5. pros: List 2-5 key strengths repeatedly praised in the reviews.
6. cons: List 2-5 key complaints or issues mentioned in the reviews. If no cons are mentioned, return [].
7. insights: List 2-4 key actionable observations or thematic patterns directly derived from the reviews.
8. evidence: List 2-5 short verbatim quotes or excerpts from the supplied reviews supporting your summary/pros/cons.
9. Return strictly structured JSON matching the requested schema.
"""


import hashlib
import threading
from collections import OrderedDict

PRODUCT_ANALYSIS_CACHE_TTL_SECONDS = int(os.getenv("PRODUCT_ANALYSIS_CACHE_TTL_SECONDS", "3600"))
PRODUCT_ANALYSIS_CACHE_MAX_ENTRIES = int(os.getenv("PRODUCT_ANALYSIS_CACHE_MAX_ENTRIES", "500"))


class AIStructuredProductAnalysis(BaseModel):
    product_id: str
    product_title: str
    summary: str
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class ProductAnalysisCache:
    """Thread-safe bounded in-memory cache for validated AI product analyses with TTL, LRU eviction, and dataset versioning."""

    def __init__(
        self,
        default_ttl: int = PRODUCT_ANALYSIS_CACHE_TTL_SECONDS,
        max_entries: int = PRODUCT_ANALYSIS_CACHE_MAX_ENTRIES,
    ):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._cache: OrderedDict[str, Tuple[AIStructuredProductAnalysis, float]] = OrderedDict()
        self._lock = threading.Lock()

    def _make_key(self, product_id: str, dataset_version: str, model: str, prompt_version: str) -> str:
        raw = f"{product_id}::{dataset_version}::{model}::{prompt_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, product_id: str, dataset_version: str, model: str, prompt_version: str = "v2") -> Optional[AIStructuredProductAnalysis]:
        key = self._make_key(product_id, dataset_version, model, prompt_version)
        now = time.time()
        with self._lock:
            if key in self._cache:
                data, expires_at = self._cache[key]
                if now < expires_at:
                    self._cache.move_to_end(key)
                    logger.info("Product analysis cache hit for product_id=%s (key=%s)", product_id, key[:8])
                    return data
                del self._cache[key]
        return None

    def put(
        self,
        product_id: str,
        dataset_version: str,
        model: str,
        data: AIStructuredProductAnalysis,
        prompt_version: str = "v2",
        ttl: Optional[int] = None,
    ) -> None:
        key = self._make_key(product_id, dataset_version, model, prompt_version)
        expires_at = time.time() + (ttl or self.default_ttl)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (data, expires_at)
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
            logger.info("Product analysis cached for product_id=%s (key=%s, ttl=%ds, entries=%d)", product_id, key[:8], ttl or self.default_ttl, len(self._cache))

    def invalidate(self, product_id: Optional[str] = None) -> None:
        with self._lock:
            if product_id is None:
                self._cache.clear()
            else:
                prefix = hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:4]
                keys_to_del = [k for k in list(self._cache.keys()) if k.startswith(prefix)]
                for k in keys_to_del:
                    del self._cache[k]


_inflight_locks: Dict[str, threading.Lock] = {}
_inflight_master_lock = threading.Lock()


def _get_product_inflight_lock(product_id: str) -> threading.Lock:
    with _inflight_master_lock:
        if product_id not in _inflight_locks:
            _inflight_locks[product_id] = threading.Lock()
        return _inflight_locks[product_id]


class GeminiSummaryService:
    """Dataset summary and product intelligence generation."""

    def __init__(
        self,
        *,
        llm_cache: Optional[LLMCache] = None,
        product_cache: Optional[ProductAnalysisCache] = None,
    ) -> None:
        self._llm_cache = llm_cache
        self._product_cache = product_cache or ProductAnalysisCache()

    @property
    def llm_cache(self) -> LLMCache:
        """V2-P9 LLM response cache (shared default instance unless injected)."""
        if self._llm_cache is None:
            self._llm_cache = LLMCache()
        return self._llm_cache

    @property
    def product_cache(self) -> ProductAnalysisCache:
        return self._product_cache

    def summarize_product_reviews(
        self, product_title: str, category: Optional[str], sample_reviews: List[str]
    ) -> AISummaryResponse:
        if not sample_reviews:
            return AISummaryResponse(
                summary="Insufficient review data available for this product.",
                common_pros=[],
                common_cons=[],
                key_themes=[],
                source_label="Summary generated from dataset reviews",
            )

        if not analyzer_service.is_configured():
            # Clean fallback when no AI provider key is configured
            return AISummaryResponse(
                summary=f"Analysis based on {len(sample_reviews)} reviews in the dataset. Configure GEMINI_API_KEY (or GROQ_API_KEY / OPENROUTER_API_KEY) in backend/.env for AI executive insights.",
                common_pros=[],
                common_cons=[],
                key_themes=[category] if category else [],
                source_label="Summary generated from dataset reviews",
            )

        # Build prompt with exact reviews (limit to 20 representative items)
        formatted_reviews = "\n".join(f"- {r}" for r in sample_reviews[:20])
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
                summary=f"Analysis of {len(sample_reviews)} dataset reviews available for {product_title}.",
                common_pros=[],
                common_cons=[],
                key_themes=[category] if category else [],
                source_label="Summary generated from dataset reviews",
            )

    def generate_product_analysis(
        self,
        product_id: str,
        product_title: str,
        category: Optional[str],
        sample_reviews: List[str],
        dataset_version: Optional[str] = None,
    ) -> AIStructuredProductAnalysis:
        if not sample_reviews:
            return AIStructuredProductAnalysis(
                product_id=product_id,
                product_title=product_title,
                summary="Insufficient review data available for this product.",
                pros=[],
                cons=[],
                insights=[],
                evidence=[],
            )

        if not analyzer_service.is_configured():
            return AIStructuredProductAnalysis(
                product_id=product_id,
                product_title=product_title,
                summary=f"Analysis based on {len(sample_reviews)} database customer reviews for {product_title}.",
                pros=[],
                cons=[],
                insights=[],
                evidence=[],
            )

        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        d_version = dataset_version or f"{len(sample_reviews)}"

        # 1. Check cache before locking
        cached = self.product_cache.get(product_id, d_version, gemini_model)
        if cached is not None:
            return cached

        # 2. Single-flight lock to coalesce concurrent requests
        lock = _get_product_inflight_lock(product_id)
        with lock:
            # Double check cache inside lock
            cached = self.product_cache.get(product_id, d_version, gemini_model)
            if cached is not None:
                return cached

            # Take high-signal slice (up to 20 representative reviews)
            selected_reviews = sample_reviews[:20]
            formatted_reviews = "\n".join(f"- {r}" for r in selected_reviews)
            prompt = f"""Product ID: {product_id}
Product Title: {product_title}
Category: {category or 'General'}

Customer Reviews from Dataset:
\"\"\"
{formatted_reviews}
\"\"\"

Synthesize ONLY these supplied reviews according to your system instructions into structured JSON."""

            try:
                result = self._generate_product_structured_analysis(prompt, product_id, product_title)
                if result and result.summary and result.product_id == product_id:
                    self.product_cache.put(product_id, d_version, gemini_model, result)
                return result
            except Exception as exc:
                logger.warning("AI product analysis error for %s: %s", product_id, exc)
                raise


    def _generate_summary(self, prompt: str) -> AISummaryResponse:
        """V2-P11 wrapper: one consolidated ``ai_request_outcome`` event per
        pipeline run (success AND final failure) in ``finally``, with fixed
        safe metadata only (ADR-012). Emission failures never break the
        request. Configuration/empty-input early returns in
        ``summarize_product_reviews`` run no AI pipeline and emit no event.
        """
        started = time.perf_counter()
        outcome: Dict[str, Any] = {
            "provider": None,
            "model": None,
            "fallback": None,
            "retry_attempts": None,
            "retry_count": None,
            "provider_latency_ms": None,
            "cache": None,
        }
        status = "failure"
        try:
            summary = self._summary_pipeline(prompt, outcome)
            status = "success"
            return summary
        finally:
            emit_ai_outcome(
                # Event task name is "product_summary" (ADR-012); the
                # internal cache/routing task id stays TASK_DATASET_SUMMARY.
                task="product_summary",
                outcome=status,
                provider=outcome["provider"],
                model=outcome["model"],
                fallback=outcome["fallback"],
                retry_attempts=outcome["retry_attempts"],
                retry_count=outcome["retry_count"],
                cache=outcome["cache"],
                rag_status=None,  # this path has no RAG stage (ADR-012)
                provider_latency_ms=outcome["provider_latency_ms"],
                total_ms=round((time.perf_counter() - started) * 1000),
            )

    def _summary_pipeline(
        self, prompt: str, outcome: Dict[str, Any]
    ) -> AISummaryResponse:
        # V2-P9: cache lookup happens BEFORE target-chain build, routing,
        # retry resolution and any provider call. A validated hit returns the
        # stored summary immediately; a miss runs the pipeline unchanged.
        llm_cache = self.llm_cache
        # V2-P11: cache state up front — a hit returns before any later stage.
        outcome["cache"] = "miss" if llm_cache.config.llm_enabled else "disabled"
        cached = llm_cache.get_summary(
            prompt=prompt,
            task=TASK_DATASET_SUMMARY,
            system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
            temperature=SUMMARY_TEMPERATURE,
        )
        if cached is not None:
            outcome["cache"] = "hit"
            logger.info(
                "Dataset summary served from cache; routing/retry/provider "
                "bypassed (task=%s).",
                TASK_DATASET_SUMMARY,
            )
            return cached

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
            # V2-P11: record the target being attempted (overwritten per
            # attempt, so the holder ends as the last target tried). Retry/
            # latency fields reset with each new target so a gateway-raised
            # failure can never inherit the previous target's numbers.
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
                prompt=prompt,
                provider=target.provider,
                model=target.model,
                system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
                temperature=SUMMARY_TEMPERATURE,
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

            # V2-P11: retry metadata + measured provider latency from the
            # normalized response (both success and returned-failure paths).
            retry_meta = getattr(response, "metadata", None)
            if isinstance(retry_meta, dict):
                outcome["retry_attempts"] = retry_meta.get("retry_attempts")
                outcome["retry_count"] = retry_meta.get("retry_count")
            outcome["provider_latency_ms"] = getattr(
                response, "latency_ms", None
            )
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
                summary = self._parse_json(text)
                # V2-P9: only a successfully generated AND Pydantic-validated
                # summary is cached (parse/validation failures raise above and
                # never reach this write).
                llm_cache.put_summary(
                    prompt=prompt,
                    task=TASK_DATASET_SUMMARY,
                    system_instruction=SUMMARY_SYSTEM_INSTRUCTION,
                    temperature=SUMMARY_TEMPERATURE,
                    summary=summary,
                    provider=target.provider,
                    model_name=target.model,
                    fallback=target != first_target,
                )
                return summary

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

    def _generate_product_structured_analysis(
        self, prompt: str, product_id: str, product_title: str
    ) -> AIStructuredProductAnalysis:
        started = time.perf_counter()
        outcome: Dict[str, Any] = {
            "provider": None,
            "model": None,
            "fallback": None,
            "retry_attempts": None,
            "retry_count": None,
            "provider_latency_ms": None,
            "cache": "disabled",
        }
        status = "failure"
        try:
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

            first_target = targets[0] if targets else None
            skipped_providers: set = set()
            retry_policy = resolve_retry_policy()
            request_timeout = resolve_request_timeout()

            last_error = None
            for target in targets:
                if target.provider in skipped_providers:
                    continue
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
                    prompt=prompt,
                    provider=target.provider,
                    model=target.model,
                    system_instruction=PRODUCT_ANALYSIS_SYSTEM_INSTRUCTION,
                    temperature=SUMMARY_TEMPERATURE,
                    response_schema=AIStructuredProductAnalysis,
                    timeout_seconds=request_timeout,
                    metadata={
                        "task": "product_analysis",
                        "product_id": product_id,
                        "fallback": target != first_target,
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
                    last_error = e
                    continue
                except Exception as e:
                    last_error = e
                    continue

                retry_meta = getattr(response, "metadata", None)
                if isinstance(retry_meta, dict):
                    outcome["retry_attempts"] = retry_meta.get("retry_attempts")
                    outcome["retry_count"] = retry_meta.get("retry_count")
                outcome["provider_latency_ms"] = getattr(
                    response, "latency_ms", None
                )
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
                    parsed = self._parse_product_analysis_json(text, product_id, product_title)
                    status = "success"
                    return parsed

            if last_error:
                raise last_error
            raise RuntimeError("Empty response from AI model for product analysis.")
        finally:
            emit_ai_outcome(
                task="product_analysis",
                outcome=status,
                provider=outcome["provider"],
                model=outcome["model"],
                fallback=outcome["fallback"],
                retry_attempts=outcome["retry_attempts"],
                retry_count=outcome["retry_count"],
                cache=outcome["cache"],
                rag_status=None,
                provider_latency_ms=outcome["provider_latency_ms"],
                total_ms=round((time.perf_counter() - started) * 1000),
            )

    def _parse_product_analysis_json(
        self, raw_text: str, expected_product_id: str, default_title: str
    ) -> AIStructuredProductAnalysis:
        cleaned = raw_text
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()
        data = json.loads(cleaned)
        # Validate that product_id matches requested product
        if not data.get("product_id") or str(data.get("product_id")) != str(expected_product_id):
            data["product_id"] = str(expected_product_id)
        if not data.get("product_title"):
            data["product_title"] = default_title
        return AIStructuredProductAnalysis.model_validate(data)


gemini_summary_service = GeminiSummaryService()

