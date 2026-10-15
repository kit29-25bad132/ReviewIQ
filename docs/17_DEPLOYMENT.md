# ReviewIQ — Deployment

## Environments
- Local development
- Optional staging
- Production

## Deployment Flow
Local development → tests/build → GitHub PR → review/merge → frontend deployment on Vercel → backend deployment on Render → Supabase PostgreSQL connectivity → production smoke tests.

## Required Configuration
Document environment variables separately for frontend and backend. Only public, non-sensitive configuration may reach the frontend.

## Production Verification
- Frontend loads.
- Backend health endpoint responds.
- CORS works for approved origin.
- Gemini connectivity works.
- Database connectivity works.
- Analyze flow succeeds.
- History and insights work.
- Safe errors are returned.
- No secrets appear in source, logs, or client bundles.

## Database Setup & Migrations

- Canonical schema source of truth: `supabase_canonical_schema.sql` (repo root).
  `supabase_schema.sql` is historical — do not apply it (see its header banner).
- Apply migrations with the versioned runner (never hand-run DDL):
  - `python backend/scripts/migrate_supabase.py plan` — dry-run, lists ordered
    migrations, touches no database.
  - `python backend/scripts/migrate_supabase.py migrate` — applies all
    migrations in a single transaction (preconditions first; any failure
    rolls back; repeated runs are safe no-ops).
- The runner has NO destructive mode. There is no supported in-place
  destructive reset; staging resets are done by database/project recreation.
- The runner refuses to proceed while more than one dataset version is
  active; resolve the conflict per `docs/INCIDENT_2026-10_canonical_wipe.md`
  style per-row review before re-running.
- Canonical data loads only via `backend/scripts/ingest_canonical_dataset.py`
  (quality-gated, version-skipping, advisory-locked). Never point ingestion
  or test harnesses at production without explicit approval.

## Database Setup & Migrations

- Canonical schema source of truth: `supabase_canonical_schema.sql` (repo root).
  `supabase_schema.sql` is historical — do not apply it (see its header banner).
- Apply migrations with the versioned runner (never hand-run DDL):
  - `python backend/scripts/migrate_supabase.py plan` — dry-run, lists ordered
    migrations, touches no database.
  - `python backend/scripts/migrate_supabase.py migrate` — applies all
    migrations in a single transaction (preconditions first; any failure
    rolls back; repeated runs are safe no-ops).
- The runner has NO destructive mode. There is no supported in-place
  destructive reset; staging resets are done by database/project recreation.
- The runner refuses to proceed while more than one dataset version is
  active; resolve the conflict per `docs/INCIDENT_2026-10_canonical_wipe.md`
  style per-row review before re-running.
- Canonical data loads only via `backend/scripts/ingest_canonical_dataset.py`
  (quality-gated, version-skipping, advisory-locked). Never point ingestion
  or test harnesses at production without explicit approval.
