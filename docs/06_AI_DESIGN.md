# ReviewIQ — AI Design

## AI Responsibilities
Gemini handles pros, cons, evidence, rating interpretation, rating-source classification, and summary generation.

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
Input normalization → prompt construction → Gemini request → structured response parsing → Pydantic validation → application validation → grounding checks → persistence.

## Reliability Controls
- Model and SDK configuration documented.
- Timeout and bounded retry policy.
- Schema validation.
- Rating range validation.
- Evidence presence and source-grounding checks.
- No persistence of invalid output.
- Safe external error mapping.
- Logging without secrets or sensitive payload leakage.

## Fine-Tuning
Fine-tuning is not required for V1. Establish a measured baseline first. Consider fine-tuning only if systematic failures are identified and a controlled comparison demonstrates meaningful improvement.
