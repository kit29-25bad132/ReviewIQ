# ReviewIQ — API Contract

## POST `/api/reviews/analyze`
### Request
```json
{"product_name": "Example Phone", "review_text": "The camera is excellent but battery life is poor. I give it 3 stars."}
```

### Response
```json
{
  "id": "uuid",
  "product_name": "Example Phone",
  "rating": 3,
  "rating_source": "explicit",
  "pros": [],
  "cons": [],
  "summary": "The review praises the camera but criticizes battery life."
}
```

## GET `/api/reviews`
Returns paginated review history.

## GET `/api/reviews/{id}`
Returns one review, original text, extracted points, and metadata.

## GET `/api/insights/{product}`
Returns deterministic review count, average rating, rating distribution, top pros, and top cons.

## Error Format
```json
{"error": "VALIDATION_ERROR", "message": "Review text is required."}
```

## Error Codes
- `VALIDATION_ERROR`
- `AI_ANALYSIS_FAILED`
- `AI_OUTPUT_INVALID`
- `DATABASE_ERROR`
- `NOT_FOUND`
- `INTERNAL_ERROR`

Never expose API keys, credentials, stack traces, or provider secrets.
