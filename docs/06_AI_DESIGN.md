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

## Reliability Controls
- Model and SDK configuration documented.
- Timeout and bounded retry policy.
- Provider fallback with error-aware skip (ADR-007).
- Schema validation.
- Rating range validation.
- Evidence presence and source-grounding checks.
- No persistence of invalid output.
- Safe external error mapping (provider-neutral messages; raw provider text never reaches clients).
- Logging without secrets or sensitive payload leakage.

## Fine-Tuning
Fine-tuning is not required for V1. Establish a measured baseline first. Consider fine-tuning only if systematic failures are identified and a controlled comparison demonstrates meaningful improvement.
