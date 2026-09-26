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
