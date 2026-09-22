# ReviewIQ — Error Handling

| Failure | Expected behavior |
|---|---|
| Empty review | Reject with validation error |
| Too-long review | Reject or enforce configured limit |
| Gemini timeout | Bounded retry, then safe error |
| Invalid JSON | Validate, optionally retry, then fail safely |
| Invalid rating | Reject output; do not persist |
| Missing rating | Return null and `not_found` |
| Database failure | Safe server error; internal logging |
| Network failure | Frontend error state with retry option |
| Missing resource | Return not-found response |
| Unexpected exception | Generic error without stack trace |

## Rules
- Never expose secrets or stack traces.
- Use stable error codes.
- Log correlation/request identifiers where available.
- Do not retry indefinitely.
- Do not persist partially validated results.
- Ensure frontend handles every documented error code.
