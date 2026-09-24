# ReviewIQ — AI Output Schema

## Canonical Structure

The canonical `ReviewAnalysis` contract (Pydantic model in `backend/models/review.py`):

```json
{
  "sentiment": "mixed",
  "rating": 4,
  "rating_source": "explicit",
  "summary": "The review praises battery life and the bright display but criticizes weak low-light camera performance.",
  "aspects": [
    {
      "aspect": "battery",
      "sentiment": "positive",
      "evidence": "The battery lasts all day"
    },
    {
      "aspect": "camera",
      "sentiment": "negative",
      "evidence": "the camera is weak at night"
    }
  ],
  "pros": [
    {
      "point": "All-day battery life",
      "evidence": "The battery lasts all day"
    }
  ],
  "cons": [
    {
      "point": "Weak low-light camera",
      "evidence": "the camera is weak at night"
    }
  ]
}
```

## Field Definitions

### `sentiment`
- Enum: `positive | negative | neutral | mixed`.
- Overall review sentiment. Use `mixed` when both meaningful positive and negative feedback are present.

### `rating`
- Nullable integer (`int | null`), allowed values 1–5 only.
- Invalid values (0, 6, 7, 4.5, non-integers) are rejected — never clamped or rounded.

### `rating_source`
- Enum: `explicit | inferred | not_found`.
- Cross-field rules:
  - `rating` is `null` → `rating_source` must be `not_found`.
  - `rating` is 1–5 → `rating_source` must be `explicit` or `inferred`.

### `summary`
- Non-empty string, 1–2 sentences, faithful to the review content.

### `aspects` (AspectSentiment)
- Array of objects. Each object:
  - `aspect` (string): product attribute discussed (e.g. `"battery"`, `"camera"`).
  - `sentiment` (enum `positive | negative | neutral | mixed`): sentiment for that aspect, assigned independently — different aspects may differ.
  - `evidence` (string): supporting text from the review.
- Default: `[]` when no aspects are discussed.

### `pros` (PointEvidence)
- Array of objects. Each object:
  - `point` (string): concise positive claim.
  - `evidence` (string): supporting text from the review.
- Default: `[]`.

### `cons` (PointEvidence)
- Array of objects. Each object:
  - `point` (string): concise negative claim.
  - `evidence` (string): supporting text from the review.
- Default: `[]`.

## Rules

- `rating`: nullable integer, allowed values 1–5; null only with `rating_source = "not_found"`.
- `rating_source`: enum `explicit | inferred | not_found`.
- `pros` / `cons`: arrays of `PointEvidence` objects with non-empty `point` and `evidence`.
- `aspects`: array of `AspectSentiment` objects with non-empty `aspect`, valid `sentiment`, and non-empty `evidence`.
- `summary`: non-empty string faithful to the review.
- Evidence must be traceable to the original review (deterministic grounding removes unsupported evidence-backed items before the response is returned).
- Invalid values must be rejected by Pydantic validation before any response is returned.

## Invalid Examples

```json
{"rating": 7}
```
```json
{"rating": 4, "rating_source": "not_found"}
```
```json
{"rating": null, "rating_source": "explicit"}
```
```json
{"sentiment": "happy"}
```
```json
{"pros": ["plain string instead of PointEvidence object"]}
```

These must all fail schema/application validation.
