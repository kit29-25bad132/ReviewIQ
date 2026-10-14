# ReviewIQ — Progress Tracker

Update this file after meaningful work. Use the status values `Not Started`, `In Progress`, `Blocked`, `Done`.

| Phase | Owner | Status | Date | Notes |
|---|---|---|---|---|
| 0 Repository Foundation | Shared | Done | | Repo, docs skeleton, `.gitignore`, `.env.example` |
| 1 Application Skeleton | Sri/Alshifa | Done | | FastAPI health endpoint, frontend client, local setup |
| 2 Gemini Fundamentals | Rishi | Done | | google-genai config, timeout/failure handling, model decision record |
| 3 Structured AI | Rishi | Done | | Pydantic contract, prompt, grounding, rating honesty tests |
| 4 Analysis Service | Rishi | Done | | Gemini 5-model fallback + LangGraph orchestration (commit `1f4f17d`) |
| 4.5 Integration Consistency & Reliability Cleanup | Shared | Done | | Safe API errors, frontend contract alignment, Supabase schema/persistence, docs refresh |
| 5 Backend API Formalization, Error Mapping & API Tests | Sri | Done | 2026-09-24 | 15 endpoints documented in `08_API_CONTRACT.md`; dataset/analytics/evaluation routes return safe 503s (no raw `str(exc)`); 6 new API test modules (61 new tests, 183 total, all green); `npm run build` PASS |
| 6 Database | Sri | Done | 2026-09-24 | `supabase_schema.sql` (incl. `rating_source`, `aspects`), frontend `historyStorage` read/write symmetry, delete/clear error handling, legacy row normalization |
| 7 Frontend | Alshifa | Done | | Dashboard, analysis UI, history, dataset explorer, product intelligence, evaluation views |
| 7 RAG Query Endpoint (V2 Phase 7) | Shared | Done | 2026-10-13 | `POST /api/products/{id}/rag-query`: gemini-embedding-001 retrieval (0.65/0.50 thresholds), bounded context, LLM answer via shared AI gateway, verbatim evidence traceability with runtime citation validation; 3 P1 audit findings fixed; P2/P3 findings open (ADR-014); frontend surface "Ask the Reviews" (`RagQueryPanel.tsx`, Phase 7 Gates 4–5: query UI, cause-neutral empty states, mobile nav reachability, FastAPI 422 parsing, form/aria accessibility) verified: 62 frontend vitest + `npm run build` PASS + 20 hermetic endpoint tests |
| 8 Integration | Shared | Done | | Frontend ↔ FastAPI ↔ Supabase persistence boundary; safe API error contracts |
| 9 Testing & QA | Rishi/Shared | Done | 2026-09-24 | Offline suite: **187** backend pytest + **27** frontend vitest; `npm run build` PASS |
| 10 Deployment | Sri/Alshifa | Not Started | | |
| 11 Evaluation Preparation | Shared/Rishi | Done | 2026-09-27 | P10: fixed `evaluation_set.json` (40 records), pure `compute_metrics`, metric/dataset/baseline/adversarial test modules, retry→grounding ordering test, results dir gitignored, `14_AI_EVALUATION.md` rewritten; 632 → **687** backend tests green |

## Update Rules
Record completed tasks, blockers, test evidence, decisions, and next actions. Keep this file synchronized with actual repository state.
