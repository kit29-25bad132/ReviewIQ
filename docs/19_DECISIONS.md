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
