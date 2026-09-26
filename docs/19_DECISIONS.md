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
