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
