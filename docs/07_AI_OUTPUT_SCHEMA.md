# ReviewIQ — AI Output Schema

## Canonical Structure
```json
{
  "rating": 4,
  "rating_source": "explicit",
  "pros": [{"point": "Excellent camera", "evidence": "The camera takes amazing photos"}],
  "cons": [{"point": "Poor battery life", "evidence": "The battery barely lasts a day"}],
  "summary": "The review praises the camera but criticizes battery life."
}
```

## Rules
- `rating`: nullable integer, allowed values 1–5.
- `rating_source`: enum `explicit | inferred | not_found`.
- If `rating` is null, `rating_source` must be `not_found`.
- `pros`: array of objects with non-empty `point` and `evidence`.
- `cons`: array of objects with non-empty `point` and `evidence`.
- `summary`: non-empty string faithful to the review.
- Evidence must be traceable to the original review.
- Invalid values must be rejected before persistence.

## Invalid Example
```json
{"rating": 7}
```
This must fail schema/application validation.
