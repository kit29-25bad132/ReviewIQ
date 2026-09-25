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
