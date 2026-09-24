# ReviewIQ — API Contract

Endpoints below reflect the **implemented** backend (`backend/main.py` routers) as of Phase 5. This document does not describe planned future work as if it were live.

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
| `422` | Request body failed request validation (e.g. missing / empty / oversized `review`) |
| `500` | Categorized provider errors (rate limit / API key / timeout) or generic `"AI analysis failed. Please try again."` |

Never expose API keys, credentials, stack traces, model output, or provider secrets in `detail`.

---

## `GET /api/dataset/reviews`

Query the 4M-row review dataset with pagination and filters.

### Query parameters
| Name | Type | Default | Constraints |
|---|---|---|---|
| `limit` | int | 20 | 1–100 |
| `offset` | int | 0 | ≥ 0 |
| `search` | string | — | free text |
| `rating` | int | — | 1–5 |
| `sentiment` | enum | — | `positive` \| `neutral` \| `negative` |
| `product` | string | — | ASIN substring |

### Response
```json
{
  "items": [
    {
      "id": "…",
      "asin": "B00…",
      "product_name": null,
      "review_text": "…",
      "actual_rating": 5,
      "summary": "…",
      "review_date": "…",
      "helpful_yes": null,
      "total_vote": null,
      "actual_sentiment": "positive"
    }
  ],
  "total": 1234,
  "limit": 20,
  "offset": 0
}
```

### Errors
| Status | When |
|---|---|
| `422` | Invalid query parameter (limit/offset/rating/sentiment) |
| `503` | Dataset unavailable / unexpected service failure (safe generic `detail`) |

---

## `GET /api/analytics/overview`

Aggregate dataset statistics.

### Response
```json
{
  "total_reviews": 4000000,
  "average_rating": 4.12,
  "positive_reviews": 0,
  "neutral_reviews": 0,
  "negative_reviews": 0,
  "rating_distribution": { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 }
}
```

### Errors
| Status | When |
|---|---|
| `503` | Dataset/analytics unavailable (safe generic `detail`) |

---

## `GET /api/analytics/products`

Per-product (ASIN) aggregates.

### Query parameters
| Name | Type | Default | Constraints |
|---|---|---|---|
| `limit` | int | 100 | 1–500 |

### Response
Array of objects: `asin`, `product_name`, `review_count`, `average_actual_rating`, `average_ai_rating`, `positive_reviews`, `neutral_reviews`, `negative_reviews`, `helpful_votes`.

### Errors
| Status | When |
|---|---|
| `422` | Invalid `limit` |
| `503` | Dataset/analytics unavailable (safe generic `detail`) |

---

## `GET /api/evaluation`

Returns cached evaluation metrics, or `null` when no cache exists.

### Response
```json
null
```
or
```json
{
  "evaluated_reviews": 10,
  "rating_accuracy": 0.8,
  "rating_mae": 0.4,
  "sentiment_accuracy": 0.9,
  "confusion_matrix": [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 8, 2], [0, 0, 0, 1, 9]],
  "methodology": "…"
}
```

---

## `POST /api/evaluation/run`

Explicitly run (or refresh) the cached evaluation. Uses mocked/offline paths in tests; production requires a configured Gemini key.

### Query parameters
| Name | Type | Default | Constraints |
|---|---|---|---|
| `limit` | int | — | 1–4915 |
| `reanalyze` | bool | false | — |

### Errors
| Status | When |
|---|---|
| `422` | Invalid `limit` |
| `503` | Dataset unavailable, AI unavailable, or unexpected evaluation failure (safe generic `detail`) |

---

## `GET /api/products/search`

Search products in the dataset.

### Query parameters
| Name | Type | Default |
|---|---|---|
| `q` | string | — |
| `limit` | int (1–100) | 20 |

### Response
```json
{ "found": true, "products": [ { "product_id": "…", "product_title": "…", "category": "…", "review_count": 0, "average_rating": 0.0 } ], "message": null }
```
Empty search returns `found: false` with `products: []` and a message.

### Errors
| Status | When |
|---|---|
| `422` | Invalid `limit` |
| `503` | Dataset indexing / not ready |

---

## `GET /api/products/{product_id}/analysis`

Product statistics + recent reviews.

### Response
`{ product, statistics, recent_reviews }`

### Errors
| Status | When |
|---|---|
| `404` | Product not found |
| `503` | Dataset not ready |

---

## `GET /api/products/{product_id}/pros-cons`

Quantified pros/cons with evidence themes.

### Response
`ProsConsAnalysisResponse` (see `backend/models/ecommerce.py`).

### Errors
| Status | When |
|---|---|
| `404` | Product not found |
| `503` | Dataset not ready |

---

## `GET /api/products/{product_id}/theme-reviews`

Supporting dataset reviews for a pro/con theme.

### Query parameters
| Name | Type | Required | Constraints |
|---|---|---|---|
| `theme` | string | **yes** | — |
| `sentiment` | string | no | `positive` / `negative` |
| `limit` | int | no (50) | 1–200 |

### Response
Array of `ReviewItem`.

### Errors
| Status | When |
|---|---|
| `422` | Missing `theme` or invalid `limit` |
| `503` | Dataset not ready |

---

## `GET /api/products/{product_id}/similar`

Similar products in the same category.

### Query parameters
| Name | Type | Default | Constraints |
|---|---|---|---|
| `limit` | int | 3 | 1–10 |

### Response
Array of `ProductSummary`.

### Errors
| Status | When |
|---|---|
| `422` | Invalid `limit` |
| `503` | Dataset not ready |

---

## `POST /api/products/{product_id}/recommendation`

Personalized recommendation from user priorities.

### Request body (`UserRequirementRequest`, all optional)
```json
{
  "persona": null,
  "custom_requirements": "long battery",
  "priorities": ["battery life"],
  "budget": null
}
```

### Response
`PersonalizedRecommendationResponse` (see `backend/models/ecommerce.py`).

### Errors
| Status | When |
|---|---|
| `404` | Product not found |
| `422` | Invalid body shape |
| `503` | Dataset not ready |

---

## `POST /api/products/{product_id}/ai-summary`

Gemini summary constrained to retrieved dataset reviews for the product.

### Response
`AISummaryResponse`: `{ summary, common_pros, common_cons, key_themes, source_label }`.

### Errors
| Status | When |
|---|---|
| `404` | Product not found |
| `503` | Dataset not ready |

---

## `GET /api/products/{product_id}/reviews`

Paginated actual dataset reviews for a product.

### Query parameters
| Name | Type | Default | Constraints |
|---|---|---|---|
| `page` | int | 1 | ≥ 1 |
| `limit` | int | 20 | 1–100 |
| `rating` | int | — | 1–5 |
| `sentiment` | string | — | free filter |

### Response
```json
{ "items": [], "total": 0, "page": 1, "limit": 20, "total_pages": 0 }
```

### Errors
| Status | When |
|---|---|
| `422` | Invalid page/limit/rating |
| `503` | Dataset indexing / not ready |

---

## Error envelope notes (current architecture)

* **Route-level errors** (all endpoints above) use FastAPI's default `{"detail": "…"}` shape with **safe** client-facing messages. Full exception text stays in server logs.
* **Global unhandled-exception handler** (`backend/main.py`) returns a different fallback envelope:
  ```json
  { "success": false, "data": null, "error": "An unexpected internal server error occurred." }
  ```
* Successful contracts and documented status codes above are preserved; no API-wide error schema redesign was applied in Phase 5.

---

## Analysis history boundary (not a Phase 5 backend endpoint)

There is **no** backend `GET /api/reviews/history` (or similar) in the current architecture.

Analysis history is persisted and retrieved by the **frontend → Supabase** path (`frontend/src/services/historyStorage.ts` → table `public.reviews`). Backend Supabase persistence/retrieval remains a **Phase 6** concern if revisited.

Do not add backend Supabase clients or analysis-history endpoints under Phase 5.

---

## Full endpoint list

```
GET    /health
POST   /api/analyze-review

GET    /api/dataset/reviews

GET    /api/analytics/overview
GET    /api/analytics/products

GET    /api/evaluation
POST   /api/evaluation/run

GET    /api/products/search
GET    /api/products/{product_id}/analysis
GET    /api/products/{product_id}/pros-cons
GET    /api/products/{product_id}/theme-reviews
GET    /api/products/{product_id}/similar
POST   /api/products/{product_id}/recommendation
POST   /api/products/{product_id}/ai-summary
GET    /api/products/{product_id}/reviews
```
