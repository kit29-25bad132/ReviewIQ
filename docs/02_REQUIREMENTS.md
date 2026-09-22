# ReviewIQ — Requirements

## Functional Requirements
- **FR-001:** Accept product name and review text.
- **FR-002:** Validate required fields and length limits.
- **FR-003:** Extract an explicit or supported inferred rating.
- **FR-004:** Classify rating source as `explicit`, `inferred`, or `not_found`.
- **FR-005:** Extract pros with grounded evidence.
- **FR-006:** Extract cons with grounded evidence.
- **FR-007:** Generate a faithful summary.
- **FR-008:** Return structured JSON.
- **FR-009:** Validate AI output with Pydantic.
- **FR-010:** Persist only validated results.
- **FR-011:** Retrieve review history.
- **FR-012:** Provide product-level deterministic analytics.
- **FR-013:** Return safe, consistent errors.
- **FR-014:** Support automated unit, API, frontend, integration, and E2E tests.

## Non-Functional Requirements
- **NFR-001 Reliability:** Fail safely when AI, network, or database services fail.
- **NFR-002 Security:** Keep secrets server-side and avoid sensitive error leakage.
- **NFR-003 Maintainability:** Separate routes, services, AI logic, and data access.
- **NFR-004 Performance:** Enforce input limits, timeouts, and bounded retries.
- **NFR-005 Usability:** Show clear loading, success, empty, and error states.
- **NFR-006 Testability:** Make AI, database, and external calls mockable.
- **NFR-007 Traceability:** Retain original review text with analyzed output.
