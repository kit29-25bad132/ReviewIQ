# ReviewIQ — User Flow

## Main Flow
Dashboard → Analyze Review → Enter Product → Enter Review → Client Validation → POST analysis request → FastAPI validation → AI service → Gemini → Pydantic validation → persistence → response → result screen → history/insights.

## Screens
1. Dashboard
2. Analyze Review
3. Processing
4. Result
5. History
6. Product Insights

## Alternative Flows
- Empty product or review: show client and server validation error.
- Review exceeds configured limit: reject with clear message.
- Gemini timeout: bounded retry, then safe failure response.
- Malformed model output: validate, retry if configured, otherwise fail safely.
- No rating: return `rating: null` and `rating_source: "not_found"`.
- No pros or cons: return empty arrays; do not invent content.
- Network failure: show retryable frontend error.
- Database failure: return generic server error and log internal details securely.
