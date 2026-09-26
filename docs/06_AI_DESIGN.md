# ReviewIQ — AI Design

## AI Responsibilities
Gemini (primary), Groq (fallback 2), and OpenRouter (fallback 3) handle pros, cons, evidence, rating interpretation, rating-source classification, and summary generation.

## Prompt Requirements
- Analyze only the supplied review.
- Never invent a rating.
- Use `null` when no rating is supported.
- Use only `explicit`, `inferred`, or `not_found`.
- Every pro and con must have evidence from the review.
- Do not add outside knowledge.
- Keep the summary faithful and concise.
- Return the agreed structured schema only.

## Pipeline
Input normalization → prompt construction → provider request (Gemini → Groq → OpenRouter) → structured response parsing → Pydantic validation → application validation → grounding checks → persistence.

## Provider Fallback (V2-P5)
- Provider hierarchy is fixed: Gemini → Groq → OpenRouter (registry `PROVIDER_ORDER`).
- Gemini keeps its 5-model chain; Groq uses `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`; OpenRouter uses `openrouter/free`.
- One shared chain builder (`services/ai/routing.py`) drives both fallback paths: review analysis and product summary.
- An `authentication`/`configuration` error skips the remaining models of that failing provider only; every other error category continues the model chain.
- Groq/OpenRouter adapters use stdlib HTTPS (`services/ai/providers/openai_compat.py`), send `response_format: json_object`, and enforce the request timeout.
- A provider with no API key configured is removed from the chain entirely; unset keys never cause failed requests.
- Bound: at most 5 Gemini + 3 Groq + 1 OpenRouter attempts per request; no unbounded retries.

## Cost-Aware Routing (V2-P6)
- **Routing ≠ fallback.** Routing (`services/ai/routing_policy.py`) chooses the *initial* target; fallback (`services/ai/routing.py`, P5) handles failure afterwards. The P5 fallback order, provider-skip policy, single-shot gateway, and LangGraph loop are unchanged.
- Flow: build the existing P5 chain → `select_initial_target()` picks one target → `apply_route_decision()` moves it to the head (all other targets keep their exact relative order) → existing fallback runs on the tail.
- Strategies (`ROUTING_STRATEGY` in `backend/.env.example`):
  - `gemini_first` (default): selects the chain head — byte-for-byte P5 behavior.
  - `cost_aware` (opt-in): deterministic, offline ranking over verified registry metadata only: free-tier preference → total verified cost (USD per 1K input+output) → quality tier → priority → original chain order.
- Verified metadata only (ADR-008): cost/context/free-tier values come from official provider documentation; unknown values stay `None` and are never treated as zero cost, never inferred, never probed.
- `GEMINI_MODEL` remains the Gemini-scoped explicit override and always wins over policy.
- No network calls, no live availability probing, no randomness, no clock in routing decisions. Invalid `ROUTING_STRATEGY` values fall back to `gemini_first` with a server-side warning only.
- Routing audit metadata (`routing_strategy`, `selected_provider`, `selected_model`, `routing_reason`) rides in server-side request metadata only; it is never returned in `AnalyzeReviewResponse`, `AISummaryResponse`, or API error payloads.
- Pricing/free-tier data is time-sensitive: re-verify when provider policies change.

## Bounded Retry (V2-P7)
- **Retry ≠ fallback.** Retry (`services/ai/retry_policy.py`) repeats the **same** provider/model target; fallback (V2-P5, `services/ai/routing.py`) advances to the **next** target. Retry runs below the target loop and above the single-shot `AIGateway`.
- **Retryable:** only `rate_limit`, `timeout`, `transient`. **Not retryable:** `authentication`, `configuration`, `model_unavailable`, `invalid_request`, `invalid_response`, `unknown`. Retrying a malformed deterministic response would only burn tokens.
- **Attempt semantics:** `RETRY_MAX_ATTEMPTS` counts TOTAL attempts for one target (`1` = no retry, `2` = original + one retry — the default, `3` = original + two).
- **Backoff:** `delay = min(RETRY_BASE_DELAY_SECONDS * 2**(retry-1), RETRY_MAX_DELAY_SECONDS)`. `RETRY_JITTER=true` applies full jitter (uniform `0..delay`).
- **Retry-After:** a provider `Retry-After` header (integer seconds, decimal seconds, or HTTP-date) is preferred over the computed delay and clamped to `RETRY_MAX_DELAY_SECONDS`. Invalid values fall back to exponential backoff. The Groq/OpenRouter transport extracts it and stores it on the normalized failure; it never crosses into an API envelope.
- **Timeout:** every request carries a unified `AI_REQUEST_TIMEOUT_SECONDS` (default 30s). Gemini enforces it through the SDK `HttpOptions.timeout` (milliseconds); the Gemini SDK's native retry is deliberately left disabled so there is exactly **one** application retry layer.
- **RAG invariant:** retrieval runs once per request before any attempt and is shared across retries and fallback. Retry never re-runs retrieval, embeddings, or vector search.
- **Product summary:** the summary path uses the identical `generate_with_retry` helper and `RetryPolicy`; there is no separate retry implementation.
- **Observability:** safe internal `AIResponse.metadata` only — `retry_attempts`, `retry_count`, `retryable`, `retry_reason`, `retry_delay_seconds`. Never keys, headers, prompts, or review text. Retry metadata is never exposed through the public API.

## Aspect-Level Intelligence (V2-P8)
- **Aspects already exist** in the analysis contract: `ReviewAnalysis.aspects[]` of `AspectSentiment{aspect, sentiment, evidence}`. Per-aspect extraction, sentiment, evidence, grounding, dedupe, RAG provenance, provider compatibility, and validation were already implemented (P1–P4); P8 enhances rather than rebuilds them.
- **`support` is deterministic, not a model confidence.** `AspectSentiment.support` is an OPTIONAL `Literal["strong", "moderate", "weak"]` computed by `grounding_service.classify_aspect_support()` **after** grounding. The model is never trusted to supply it, and any model-emitted value is overwritten. It is not a probability and not calibrated.
- **Exact support rules** (application-known facts only; no fuzzy matching, no embeddings, no numeric score):
  - `strong` — evidence is grounded, is a verbatim substring of the original review, and mentions the aspect (normalized aspect and evidence share a token of length ≥ 2).
  - `moderate` — evidence is grounded only after normalization and mentions the aspect.
  - `weak` — evidence is grounded but does not mention the aspect. Unsupported evidence classifies as `weak` defensively; such aspects are removed by grounding and never emitted with a support status.
- **Grounding invariant preserved:** only the original review is authoritative. Grounding removes unsupported aspect evidence first, so unsupported evidence can never receive `strong`/`moderate`. RAG retrieved context can never become aspect evidence or support.
- **RAG provenance:** original review stays verbatim; retrieved reviews remain background only; retrieval runs once per request and is shared across fallback/retry attempts.
- **Providers:** Gemini keeps its native structured schema (new optional field included); Groq/OpenRouter keep `json_object` mode; app-side Pydantic validation stays authoritative. No provider-specific aspect logic.
- **Deliberately NOT added:** `positive_aspects`/`negative_aspects` arrays (`aspects[].sentiment` is canonical) and a dedicated pain-point schema (negative aspect sentiment + `cons` + dataset themes already express it; no severity numbers). Review-level aspects, dataset `ProConTheme` themes, and product-summary `key_themes` remain separate scopes.
- **Backward compatible:** `support` is optional (`None` by default), pre-P8 payloads validate, and the `AnalyzeReviewResponse` envelope is unchanged.

## Reliability Controls
- Model and SDK configuration documented.
- Unified request timeout plus bounded, exponential-backoff retry policy (ADR-009).
- Retry-After honored and clamped; invalid values fall back to computed backoff.
- Provider fallback with error-aware skip (ADR-007).
- Deterministic, offline initial-target routing with a safe default strategy (ADR-008).
- Schema validation.
- Rating range validation.
- Evidence presence and source-grounding checks.
- No persistence of invalid output.
- Safe external error mapping (provider-neutral messages; raw provider text never reaches clients).
- Logging without secrets or sensitive payload leakage.

## Fine-Tuning
Fine-tuning is not required for V1. Establish a measured baseline first. Consider fine-tuning only if systematic failures are identified and a controlled comparison demonstrates meaningful improvement.
