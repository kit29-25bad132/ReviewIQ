# ReviewIQ — Testing Strategy

## Testing Layers
1. Unit tests
2. AI/schema validation tests
3. API tests
4. Integration tests
5. End-to-end tests
6. Regression and release checks

## Test Scenarios
- Explicit rating
- Missing rating
- Inferred rating
- Positive review
- Negative review
- Mixed review
- Multiple pros/cons
- No pros or cons
- Empty input
- Very long input
- Malformed JSON
- Invalid rating
- Missing fields
- Hallucinated evidence
- Gemini timeout/failure
- Database failure
- Network failure
- Retrieval and insights
- Frontend loading and error states

## Test Principles
- External AI and database calls should be mockable.
- Tests must assert behavior, not only status codes.
- Do not claim coverage or accuracy without measurement.
- Keep regression cases for every discovered failure.
