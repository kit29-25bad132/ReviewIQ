# ReviewIQ — Architecture Decision Records

Record significant decisions using this format:

## ADR-XXX — [Decision Title]
- **Date:** YYYY-MM-DD
- **Status:** Proposed / Accepted / Superseded
- **Decision makers:** 
- **Context:** 
- **Decision:** 
- **Alternatives considered:** 
- **Reason:** 
- **Consequences:** 
- **Follow-up:** 

## Initial Locked Decisions
- Use FastAPI for the backend and keep AI logic separated from the frontend.
- Use Gemini as the single V1 LLM provider.
- Do not require fine-tuning for V1.
- Use structured output plus Pydantic validation.
- Use deterministic application code for analytics.
- Retain original review text for traceability.
- Do not allow AI coding agents to create automatic Git commits.

Future decisions must be added rather than silently changing the locked direction.

---

## ADR-003 — Use `google-genai` SDK only (legacy `google-generativeai` removed)
- **Date:** Reconstructed from implementation during Phase 4.5 documentation cleanup (original decision date not recorded)
- **Status:** Accepted
- **Decision makers:** Project team (per locked Gemini single-provider direction)
- **Context:** Early Gemini integration used the legacy `google-generativeai` client alongside/instead of the current Google GenAI SDK. Code and tests needed a single supported integration path for V1 structured outputs and multi-model fallback.
- **Decision:** The backend depends only on the `google-genai` package (`google.genai`). The legacy `google-generativeai` client path was removed and is not supported.
- **Alternatives considered:** Keep dual SDK support; keep legacy SDK only.
- **Reason:** One SDK reduces dependency drift, matches the pinned model/fallback verification work, and aligns with the locked “Gemini as the single V1 LLM provider” direction.
- **Consequences:** `backend/requirements.txt` lists `google-genai` only; analyzer code imports `google.genai`; tests note that no legacy ordering remains to cover.
- **Follow-up:** None. Revisit only if the provider SDK is retired upstream.

## ADR-004 — Provider-neutral AI gateway and model registry
- **Date:** 2026-09-25 (V2 foundation milestone)
- **Status:** Accepted
- **Decision makers:** Project team (V2 locked scope)
- **Context:** V1 called the Gemini SDK directly from `services/ai_analyzer.py` and duplicated that SDK usage in `services/gemini_summary_service.py`. V2 must add multi-provider fallback and cost-aware routing without scattering provider details through the analysis pipeline.
- **Decision:** Introduce a provider-neutral AI foundation under `services/ai/`: typed request/response contracts, an `AIProvider` interface, a `GeminiProvider` adapter, a model registry (`ModelSpec`/`ModelRegistry`), and an `AIGateway`. The analysis pipeline depends only on these abstractions. Model fallback order remains orchestrated by the existing LangGraph node, which now iterates a registry-owned model chain and generates through the gateway.
- **Alternatives considered:** Keep direct SDK calls and add providers later; move model fallback inside the gateway/provider.
- **Reason:** Keeps provider-specific logic in one place, preserves the existing LangGraph fallback and output/grounding contracts, and gives the next milestone (routing, RAG) stable seams without introducing fake providers or new dependencies.
- **Consequences:** Provider SDK access lives only in `services/ai/providers/`; provider errors are normalized into `AIErrorType` categories and mapped to fixed user-safe API messages; the registry holds capability/quality/ordering metadata with cost and context-window left unset until verified values exist. No routing algorithm is implemented yet.
- **Follow-up:** Cost-aware model routing and cross-provider fallback in later V2 milestones; populate verified cost/context metadata when available.

## ADR-005 — Cloud embeddings + pgvector semantic retrieval
- **Date:** 2026-09-25 (V2-P2 retrieval foundation milestone)
- **Status:** Accepted
- **Decision makers:** Project team (V2 locked scope)
- **Context:** V2 needs a retrieval foundation for RAG. The backend previously had no vector storage; its data layer is SQLite + CSV, while Supabase/PostgreSQL is the project's managed database and is currently frontend-only. Local inference is excluded by the locked V2 scope.
- **Decision:**
  - **Embeddings are provider-abstracted** (`services/embeddings/`): `EmbeddingRequest`/`EmbeddingResponse` contracts, an `EmbeddingProvider` interface, a Gemini adapter, and a provider-neutral `EmbeddingService` that owns batching and dimension validation. Application code never imports an embedding SDK directly.
  - **Provider/model:** Google Gemini via the existing `google-genai` dependency. Model `gemini-embedding-001` (verified available; `text-embedding-004` is retired). No new AI dependency was added.
  - **Dimension:** 768 (verified `output_dimensionality=768`). 1536/3072 are supported by the model but require a matching migration; dimension is validated at runtime and a mismatch fails loudly (never truncated/padded).
  - **Vector storage is isolated behind a repository** (`VectorRepository` + `PostgresVectorRepository`). All SQL lives in the data layer; services depend on the interface, not raw SQL.
  - **Store:** the runtime vector store is Supabase PostgreSQL + pgvector (`public.review_embeddings`, migration in `supabase_schema.sql`). No local vector database and no SQLite vector store.
  - **Metric:** cosine. pgvector operator `<=>` orders by cosine distance; the reported similarity is `1 - distance` throughout retrieval. One convention, no mixing of distance metrics.
  - **Metadata:** normalized columns (`product_id`, `rating`, `source`, `review_date`) for typed filtering, not an arbitrary JSON dump. Original review text is retained for later evidence grounding.
  - **Deduplication:** deterministic `sha256(product_id + NFKC/casefold/whitespace-canonicalized text)`. Product ID participates, so identical text for different products is stored separately. Fingerprints make upserts idempotent and skip redundant embedding work.
  - **Local embeddings are excluded** (no Ollama/LM Studio/llama.cpp/GGUF/quantization), consistent with the V2 cloud/API-first decision.
  - **RAG generation is intentionally deferred:** this milestone ends at reliable semantic retrieval; no RAG context builder or LLM-generated RAG answer.
- **Alternatives considered:** SQLite/pgvector-less in-process vector store (rejected by the explicit V2 runtime-storage decision); adding a Postgres driver plus a Python pgvector adapter (rejected — vectors are sent as `::vector` literals, so only `psycopg` is needed); local embedding models (excluded by scope).
- **Reason:** Keeps provider-specific embedding logic in one place, keeps SQL out of services, and matches the locked production topology (Vercel frontend → Render backend → Supabase PostgreSQL + pgvector).
- **Consequences:** `backend/requirements.txt` adds only `psycopg[binary]` (imported lazily so the offline suite runs without it). New modules: `services/embeddings/`, `services/retrieval/`, `models/retrieval.py`, `routes/retrieval.py` (`/api/v2/retrieval/*`). V1 code and contracts are untouched. The pgvector migration is additive and has **not** been verified against a live Supabase project.
- **Follow-up:** Verify the migration against the Supabase project and populate embeddings; then build the RAG retrieval pipeline, context builder, AI gateway integration, and cost-aware routing. Populate verified cost/context metadata when available.

## ADR-006 — RAG retrieval pipeline for review analysis (V2-P3)
- **Date:** 2026-09-26 (V2-P3 RAG pipeline milestone)
- **Status:** Accepted
- **Decision makers:** Project team (V2 locked scope)
- **Context:** ADR-005 delivered semantic retrieval and explicitly deferred RAG generation. The analysis pipeline sends only the review text to Gemini. V2-P3 must let analysis reuse retrieved similar reviews as context without changing V1/API contracts, weakening evidence grounding, or adding infrastructure.
- **Decision:**
  - **New package** `backend/services/rag/`: `config.py` (env-validated settings), `retrieval.py` (best-effort retrieval wrapper), `context_builder.py` (bounded, deterministic context block), `prompting.py` (context-aware prompt with byte-identical fallback).
  - **Reuse, not duplicate:** the stage calls the P2 `SemanticSearchService` through `RagRetrievalService`; query is the review text and preprocessing/validation stay inside the P2 search path.
  - **Disabled by default:** `RAG_ENABLED` defaults to false, so V1/P2 behavior (prompt, graph state shape, API response) stays byte-identical until an environment opts in. Settings: `RAG_ENABLED`, `RAG_TOP_K` (5), `RAG_SIMILARITY_THRESHOLD` (0.35), `RAG_MAX_CONTEXT_REVIEWS` (5), `RAG_MAX_CONTEXT_CHARS` (6000), `RAG_MAX_REVIEW_CHARS` (1000). Invalid or out-of-range values fall back to defaults and never crash analysis.
  - **Best-effort stage:** `retrieve()` never raises. Failures become structured metadata (`status`: disabled/ok/empty/unavailable/invalid + `error_type`) and analysis continues with an empty context. Ordering is deterministic: similarity descending, `review_id` tie-break.
  - **LangGraph:** optional `retrieve_fn` stage (`START -> retrieve_context -> attempt_model`); state key `rag_context` exists only when the stage runs; `attempt_fn` keeps its two-argument signature (context flows through a per-request closure holder). Retrieval runs once per request and is shared by all fallback attempts.
  - **Prompting:** with context, the original review stays verbatim in its own labeled section; retrieved reviews go into a separate "Retrieved contextual reviews" section with explicit system rules (background only; evidence must exist in the original review; the original wins on conflict). Without context, prompt and system instruction are byte-identical to V1.
  - **Grounding unchanged:** `ground_analysis()` still filters against the original review only; retrieved context is never treated as evidence.
  - **Metadata is internal:** retrieval metadata (`enabled`, `query`, `top_k`, `similarity_threshold`, `retrieved_count`, `status`, results) lives in `RagRetrievalResult` plus safe server logs (status/counts/thresholds only — review text/query never logged). The `AnalyzeReviewResponse` envelope is unchanged.
- **Alternatives considered:** default-on RAG (rejected — offline tests and existing callers would hit real embedding/database paths); exposing retrieval metadata in the API response (rejected — no consumer needs it and it risks contract drift); product-filtered retrieval (rejected — the analyze endpoint carries no product context); retrieving per attempt (rejected — one retrieval per request, shared across fallback attempts).
- **Reason:** delivers contextual RAG while keeping every existing contract (prompt, graph state, API envelope, grounding) untouched when disabled and best-effort-safe when enabled.
- **Consequences:** new modules under `services/rag/`, two new offline test files (31 tests), config documented in `backend/.env.example`. Live cloud verification passed 15/15: relevant synthetic review ranked first (cosine 0.7878), threshold/top_k/determinism/zero-result checks passed, context sections present in the real prompt, grounding original-review-only, RAG-enabled API call returned the exact V1 envelope, and synthetic rows were deleted.
- **Follow-up:** set `RAG_ENABLED=true` in the Render environment when RAG should be enabled in production; populate cost/context registry metadata when available (per ADR-004/ADR-005).

## ADR-007 — Multi-provider fallback: Gemini → Groq → OpenRouter (V2-P5)
- **Date:** 2026-09-26 (V2-P5 multi-provider fallback milestone)
- **Status:** Accepted
- **Decision makers:** Project team (V2 locked scope)
- **Context:** ADR-004 delivered the provider-neutral gateway/registry but only Gemini was registered, so any Gemini outage (including its model chain) failed the whole analysis. V2-P5 adds a second and third provider without new heavy SDKs, without touching the Gemini adapter (protected by fake-SDK tests), and without changing API contracts.
- **Decision:**
  - **Provider hierarchy:** exactly `Gemini → Groq → OpenRouter`, encoded once as `PROVIDER_ORDER` in the registry and consumed by the shared `build_target_chain()` in `services/ai/routing.py`. Both fallback paths (LangGraph review analysis and the product-summary loop) use it; no other providers exist.
  - **Model chains:** the Gemini chain is unchanged (5 models, `GEMINI_MODEL` first when set). Groq uses `openai/gpt-oss-120b` (primary), `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`. OpenRouter has a single route `openrouter/free`.
  - **Adapters:** `GroqProvider` and `OpenRouterProvider` subclass a shared `OpenAICompatProvider` base in `services/ai/providers/openai_compat.py`, implemented with stdlib `urllib` HTTPS (no new dependencies). Both send `response_format={"type":"json_object"}` and enforce `timeout_seconds` (the Gemini adapter's behavior is untouched). On HTTP 400 naming `response_format`, the transport retries exactly once without it; application-side JSON + Pydantic validation stays mandatory either way.
  - **Error-aware skip:** `AIErrorType.AUTHENTICATION`/`CONFIGURATION` on a provider's model skips the *remaining models of that provider* only (analysis path raises an internal `SkipTargetError` that preserves `last_error`); `RATE_LIMIT`, `TIMEOUT`, `TRANSIENT`, `MODEL_UNAVAILABLE`, `INVALID_RESPONSE`, `INVALID_REQUEST`, `UNKNOWN` continue the model chain normally. Skip logic lives above the gateway, so the gateway stays a single-shot resolver.
  - **Classification fix:** `INVALID_REQUEST` was added to `AIErrorType`, `"invalid argument"` was removed from the auth hints (V1 bug: a malformed request looked like bad credentials), and `_INVALID_REQUEST_HINTS` is checked last so more specific categories (rate limit / auth / timeout / model / transient) win.
  - **Configuration:** unset/empty `GROQ_API_KEY`/`OPENROUTER_API_KEY` removes that provider from the chain entirely (existing suites rely on this). `.env.example` documents both keys; the keys are backend-only.
  - **API safety:** error messages and routes are provider-neutral ("AI provider API key", not "Gemini API key"), so the same safe message maps regardless of which provider failed.
- **Alternatives considered:** provider-level retry inside the gateway (rejected — gateway stays single-shot per ADR-004); SDK-based clients for Groq/OpenRouter (rejected — adds dependencies for two REST endpoints); checking `INVALID_REQUEST` before model hints (rejected — "invalid argument: model not found" must stay `MODEL_UNAVAILABLE`).
- **Reason:** one shared chain builder keeps both fallback paths consistent; stdlib transport keeps the offline suite hermetic; the auth/invalid-request split fixes a real misclassification without weakening credential detection.
- **Consequences:** `backend/tests/test_multi_provider.py` adds 35 offline tests (386 total, all green). Live verification: Gemini is exercisable with the existing key; Groq/OpenRouter live checks were **not performed** (no credentials available). Registry cost/context metadata for the new models remains unset.
- **Follow-up:** live smoke tests for Groq and OpenRouter when keys are available; populate verified cost/context metadata; revisit routing weights when cost-aware routing (ADR-004 follow-up) lands.

## ADR-008 — Cost-aware initial-target routing (V2-P6)
- **Date:** 2026-09-26 (V2-P6 cost-effective model selection & routing milestone)
- **Status:** Accepted
- **Decision makers:** Project team (V2 locked scope)
- **Context:** ADR-004/ADR-007 delivered the provider-neutral gateway, the registry, and cross-provider fallback, but the *initial* target was always implicitly `chain[0]` and cost/free-tier metadata was deliberately unset (no verified values). V2-P6 adds an initial-model selection layer that must not replace, reorder, or weaken the P5 fallback architecture, must stay deterministic and offline, and must not invent pricing.
- **Decision:**
  - **Routing ≠ fallback:** new module `backend/services/ai/routing_policy.py` owns *initial-target selection only*; `backend/services/ai/routing.py` keeps P5 fallback-chain construction and provider-skip behavior unchanged (`PROVIDER_ORDER`, `build_target_chain()`, `SKIP_REMAINING_PROVIDER_ERRORS`, `SkipTargetError`, single-shot `AIGateway`, LangGraph mechanics all untouched).
  - **Flow:** build the existing P5 chain → `select_initial_target(chain, strategy, ..., override, task) -> RouteDecision` → `apply_route_decision()` moves the selected `ModelRef` to the head, preserving the exact relative order of every other target → the existing P5 fallback loop runs on the tail. If the head is selected, the result is byte-for-byte identical to P5.
  - **Strategies:** exactly `gemini_first` (default; preserves current behavior) and `cost_aware` (opt-in via `ROUTING_STRATEGY` in `backend/.env.example`). Invalid values fall back to `gemini_first` with a server-side warning only; configuration details are never exposed to API clients.
  - **`cost_aware` ranking (deterministic):** 1) verified `free_tier=True` first, 2) total verified cost (USD per 1K input + output; unknown/`None` cost ranks last and is **never** treated as zero), 3) quality tier (standard before lite on an equal-cost tie), 4) registry `priority`, 5) original chain order. Eligibility: configured provider, registered + enabled model, `supports_structured_output`, task capability. No randomness, no clock, no network calls, no live availability probing, no invented quality or latency scores (latency metadata intentionally absent; `AIResponse.latency_ms` stays measured runtime data).
  - **Verified metadata population:** `ModelSpec` gains `free_tier: Optional[bool]`; registry cost/context/free-tier fields are populated **only** from official provider documentation (per-1M prices converted to per-1K USD): Gemini 3.8 Flash `$0.75/$3.75` (introductory through 2026-12-31), 3.5 Flash `$1.50/$9.00`, 3.5 Flash-Lite `$0.30/$2.50`, contexts 1M/1M/1,048,576; Groq gpt-oss-120b `$0.15/$0.60`, gpt-oss-20b `$0.075/$0.30`, qwen3.8-27b `$0.80/$4.00`, contexts 131,072/131,072/131,042; `openrouter/free` `$0/$0`, context 200,000, free-tier true. No verified price exists for `gemini-3.6-flash`/`gemini-flash-latest` (stay `None`); Groq free-tier stays `None` (not established by the verified sources).
  - **OpenRouter is opaque:** `openrouter/free` is treated as a single verified free route (`$0/$0`, 200K context), never as a statically identifiable underlying model (the route resolves upstream and can change).
  - **Overrides:** the existing `GEMINI_MODEL` (Gemini-scoped) selection is passed as the explicit override and always beats policy; no new public/API parameter was introduced and API envelopes (`AnalyzeReviewResponse`, `AISummaryResponse`, error payloads) are unchanged.
  - **Integration:** both chain consumers — `services/ai_analyzer.py` (LangGraph analysis) and `services/gemini_summary_service.py` (product summary) — call the same policy with `provider_configured_checker()`; RAG retrieval still runs once shared across attempts, and grounding/Pydantic validation are untouched. Safe audit fields (`routing_strategy`, `routing_reason`, `selected_provider`, `selected_model`) are attached to server-side request metadata and conservative INFO logs only.
  - **Test isolation:** the hermetic autouse fixture in `backend/tests/conftest.py` also neutralizes `ROUTING_STRATEGY`, so the default strategy applies to every test unless it opts in explicitly.
- **Alternatives considered:** building a separate P6 chain (rejected — would duplicate/replace fallback); router-first provider hierarchy (rejected — `PROVIDER_ORDER` is a locked P5 contract); ranking by measured latency (rejected — no verified static latency data, and measurement would need network/runtime state); exposing routing metadata in API responses (rejected — contract drift and provider-internals leakage); defaulting to `cost_aware` (rejected — would reorder the existing deterministic suite and change production behavior silently).
- **Reason:** one pure policy function keeps routing auditable, deterministic, and offline while leaving every P5 guarantee intact; verified-only metadata keeps the registry honest (unknown stays `None`).
- **Consequences:** new `services/ai/routing_policy.py` + `backend/tests/test_routing_policy.py` (35 tests; suite total 421, all green, hermetic). `test_ai_foundation.py::test_registry_holds_expected_metadata` was legitimately updated to assert the newly verified values. `backend/.env.example` documents `ROUTING_STRATEGY=gemini_first`. Under `cost_aware` with all providers configured, `openrouter/free` (verified $0 free route) ranks as the initial target — intended by the free-tier-first policy; its official free-tier request limit (e.g. 50 requests/day) makes this an operational consideration, not a code defect.
- **Follow-up:** re-verify pricing/free-tier/context metadata whenever provider policies change (introductory Gemini pricing ends 2026-12-31); live smoke tests for Groq/OpenRouter when keys are available; consider optional per-provider rate-limit/quota metadata before any production rollout of `cost_aware`.

## ADR-009 — Application-level bounded retry above the single-shot AI gateway (V2-P7)
- **Date:** 2026-09-26 (V2-P7 reliability milestone)
- **Status:** Accepted
- **Decision makers:** Project team (V2 locked scope)
- **Context:** ADR-004/ADR-007 left the gateway single-shot and used "fallback" (advance to the next model/provider) as the only recovery mechanism. A transient failure (429, timeout, 5xx) therefore discarded the current target immediately, even though the same target would very likely have succeeded a moment later. Gemini also had no application-level timeout, and provider `Retry-After` headers were ignored.
- **Decision:**
  - **New module** `backend/services/ai/retry_policy.py` owns a dependency-free, deterministic retry layer: `RetryPolicy`, `is_retryable`, `compute_delay`, `generate_with_retry`, `resolve_retry_policy`, `resolve_request_timeout`.
  - **Retry ≠ fallback.** Retry repeats the **same** provider/model target; fallback advances to the **next** target. Retry lives BELOW the existing target loop and ABOVE the single-shot `AIGateway`. `generate_with_retry` never builds/reorders chains, never calls another provider, and never touches RAG/grounding/LangGraph. The gateway stays single-shot; `build_target_chain`, `PROVIDER_ORDER`, the P6 routing policy, and the LangGraph fallback mechanics are untouched.
  - **Retryable:** `RATE_LIMIT`, `TIMEOUT`, `TRANSIENT` only. **Non-retryable:** `AUTHENTICATION`, `CONFIGURATION`, `MODEL_UNAVAILABLE`, `INVALID_REQUEST`, `INVALID_RESPONSE`, `UNKNOWN`. Decisions use the classified `AIErrorType` — never fragile string matching.
  - **`INVALID_RESPONSE` is not retried** because a deterministic malformed/empty output is not expected to fix itself; retrying would burn tokens with no expected benefit. Empty responses continue to advance the chain via the existing `EmptyResponseError` path.
  - **Attempt semantics:** `RETRY_MAX_ATTEMPTS` counts TOTAL attempts per target (`1` = no retry, `2` = original + one retry — the default, `3` = original + two). The retry count is bounded, so no infinite loops are possible.
  - **Backoff:** deterministic exponential `delay = min(RETRY_BASE_DELAY_SECONDS * 2**(retry-1), RETRY_MAX_DELAY_SECONDS)`, with optional full jitter (uniform `0..delay`). Zero/negative configuration degrades safely to no delay.
  - **Retry-After:** the Groq/OpenRouter stdlib transport parses a `Retry-After` header (integer seconds, decimal seconds, or HTTP-date via `email.utils`) into a non-negative float stored on the normalized failure (`AIResponse.retry_after_seconds`). It is a server-suggested delay: preferred over the computed backoff but clamped to `RETRY_MAX_DELAY_SECONDS`; invalid values fall back to exponential backoff. It never appears in an API envelope. The pre-existing one-time HTTP 400 `response_format` compatibility retry is unchanged and remains distinct from this reliability retry.
  - **Timeout:** `AI_REQUEST_TIMEOUT_SECONDS` (default 30) is populated on every `AIGenerationRequest` by both call sites and enforced by all three adapters. Gemini uses `google-genai` `HttpOptions.timeout` (milliseconds). Invalid/non-positive configuration falls back to the default with a server-side warning and never crashes startup.
  - **Gemini SDK retry remains disabled:** `HttpOptions.retry_options` is never set, so the SDK keeps `stop_after_attempt(1)` and the application has exactly ONE retry layer. Configuring SDK retry would create duplicate retries.
  - **RAG invariant:** retrieval runs once per request before any attempt and is shared across retries and fallback; retry never re-runs retrieval, embeddings, or vector search.
  - **Product summary:** `services/gemini_summary_service.py` uses the same `generate_with_retry` + `RetryPolicy`; there is no separate retry implementation.
  - **Observability:** safe internal `AIResponse.metadata` only — `retry_attempts`, `retry_count`, `retryable`, `retry_reason`, `retry_delay_seconds` — plus conservative INFO logs (provider/model/category/attempt/delay). Never API keys, `Authorization`, prompts, review text, or headers; never serialized into `AnalyzeReviewResponse`/`AISummaryResponse`/error payloads.
  - **Configuration:** `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY_SECONDS`, `RETRY_MAX_DELAY_SECONDS`, `RETRY_JITTER`, `AI_REQUEST_TIMEOUT_SECONDS` documented in `backend/.env.example`. `backend/.env` itself is not modified.
  - **Test isolation:** the hermetic autouse fixture neutralizes `RETRY_MAX_ATTEMPTS` to `1`, so pre-existing fallback-count tests keep measuring fallback exactly as before; P7 tests opt in and use zero delays / injected sleep, so no test waits or reaches the network.
- **Alternatives considered:** retry inside `AIGateway` (rejected — breaks the single-shot gateway contract and tangles retry with provider resolution); retry by rebuilding the fallback chain (rejected — would duplicate the fallback system); retrying `INVALID_RESPONSE` (rejected — deterministic output will not self-heal); enabling the Gemini SDK's native retry (rejected — duplicate retry layers); honoring `Retry-After` without a clamp (rejected — a hostile/erroneous large value could stall a request indefinitely).
- **Reason:** a small, pure, injectable retry layer recovers the cheapest and most common failures without touching any P5/P6 guarantee, keeps fallback as the single source of target advancement, and gives exactly one bounded retry layer with no storm risk.
- **Consequences:** new `backend/services/ai/retry_policy.py` and `backend/tests/test_retry_policy.py` (39 tests; suite total 460, all green). `contracts.AIResponse` gains an internal `retry_after_seconds` field. `services/ai_analyzer.py` and `services/gemini_summary_service.py` call `generate_with_retry` and populate `timeout_seconds`. `services/ai/providers/gemini.py` applies the timeout; `services/ai/providers/openai_compat.py` extracts `Retry-After`. Existing test SDK fakes now accept the `http_options` kwarg. No public API or frontend contract changed.
- **Follow-up:** live smoke tests for Groq/OpenRouter when keys are available; consider optional per-provider rate-limit/quota metadata before any production rollout of `cost_aware`.
