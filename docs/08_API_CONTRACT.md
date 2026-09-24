# ReviewIQ — API Contract

Endpoints below reflect the **implemented** backend (`backend/main.py` routers). This document does not describe planned Phase 5 work as if it were live.

---

## `GET /health`

Service health probe. Never returns secrets.

### Response
```json
{
  "status": "ok",
  "service": "Product Review Analyzer Backend",
  "version": "1.0.0",
  "ai_provider": "Google Gemini",
  "ai_configured": true
}
```

---

## `POST /api/analyze-review`

Analyze a single customer review and return structured, validated analysis.

### Request
```json
{
  "review": "The camera is excellent but battery life is poor. I give it 3 stars."
}
```

- `review`: required string, 1–5000 characters after trim (whitespace-only rejected).

### Success response envelope
```json
{
  "success": true,
  "data": { "...": "ReviewAnalysis" },
  "error": null
}
```

### `ReviewAnalysis` (`data`)

Canonical definition: `backend/models/review.py` / `docs/07_AI_OUTPUT_SCHEMA.md`.

```json
{
  "sentiment": "mixed",
  "rating": 3,
  "rating_source": "explicit",
  "summary": "The review praises the camera but criticizes battery life.",
  "aspects": [
    {
      "aspect": "camera",
      "sentiment": "positive",
      "evidence": "camera is excellent"
    },
    {
      "aspect": "battery",
      "sentiment": "negative",
      "evidence": "battery life is poor"
    }
  ],
  "pros": [
    { "point": "Excellent camera", "evidence": "camera is excellent" }
  ],
  "cons": [
    { "point": "Poor battery life", "evidence": "battery life is poor" }
  ]
}
```

| Field | Type | Rules |
|---|---|---|
| `sentiment` | `"positive" \| "negative" \| "neutral" \| "mixed"` | Required |
| `rating` | `integer \| null` | When present: 1–5 only (never clamped/rounded). When `null`, `rating_source` must be `"not_found"` |
| `rating_source` | `"explicit" \| "inferred" \| "not_found"` | Cross-field consistent with `rating` |
| `summary` | `string` | Non-empty, faithful to the review |
| `aspects` | `AspectSentiment[]` | Each: `{ aspect, sentiment, evidence }` |
| `pros` / `cons` | `PointEvidence[]` | Each: `{ point, evidence }` — **objects, not plain strings** |

### Error responses

FastAPI `HTTPException` style: `detail` is a **safe client-facing message**. Provider/parser internals and raw model output are logged server-side only and are never returned.

```json
{
  "detail": "Review analysis failed validation. Please try again."
}
```

| Status | Example `detail` |
|---|---|
| `400` | Configuration issue for missing `GEMINI_API_KEY`, or generic validation failure |
| `422` | Request body failed request validation (e.g. missing `review`) |
| `500` | Categorized provider errors (rate limit / API key / timeout) or generic `"AI analysis failed. Please try again."` |

Never expose API keys, credentials, stack traces, model output, or provider secrets in `detail`.

---

## Other implemented routers

The app also mounts dataset/analytics/product routes (`/api/dataset/*`, `/api/analytics/*`, `/api/products/*`, `/api/evaluation/*`). Those are outside this analysis contract document and are not expanded here.
