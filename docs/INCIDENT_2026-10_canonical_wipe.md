# Incident record — canonical tables replaced by fixture data (2026-10)

## Status

Recorded from read-only evidence. No remediation executed under this record.
Remaining unknowns are listed explicitly; nothing here attributes the event
to a person.

## Confirmed facts

- Live `public.products` held 2 rows (`P01/Alpha One`, `P02/Beta Two`) and
  `public.reviews` held 4 rows (`R1`–`R4`) instead of the 20-product /
  1,500-review canonical corpus.
- The replacement rows are byte-identical in shape and content to the
  `a.csv` / `b.csv` / `c.csv` fixtures in
  `backend/tests/test_quality_report_reproducibility.py`.
- `data_ingestion_runs` held matching `VALIDATED`/`PASSED` rows for those
  filenames; `dataset_versions` held matching 4-row/2-product fixture
  version rows, all with `is_active = true`.
- Mechanism confirmed in code: `PostgresDatabase._pool` is class-level
  (`backend/services/retrieval/database.py`). Once any test in a session
  opens the real pool, later `connection()` calls reuse it without ever
  calling `psycopg.connect` — silently bypassing that file's
  `monkeypatch.setattr(psycopg, "connect", fake)` and running REAL ingestion
  against production (including its unconditional wipe-and-load).
- Test-side guard added: `_reset_pool()` before and after each fake-ingest
  run, plus fail-closed `tests/db_guard.py` target check wired into the
  ingest test helper.

## Previously reported but not independently confirmed

- The exact wall-clock time of the wipe and the exact invoking command.
- That the wiping run was specifically the Gate 5 test module rather than
  another runner of the same code path in a pandas-enabled environment.

## Unknowns

- Responsible actor (not attributed — no evidence identifies one).
- Cause of the earlier legacy-embedding absence (1,950 rows): no backup,
  export, or second copy has been found; recovery availability is unknown.
- Whether any downstream consumer cached the fixture rows.

## Recovery status

- Canonical corpus re-ingested by an unknown party afterward (20 products /
  1,500 reviews verified live; version tag matches the current worktree CSV
  hash). Fixture rows no longer present in `products`/`reviews`.
- Fixture `dataset_versions` rows and their ingestion/report audit rows
  remain (intentionally untouched pending approval).
- Legacy embeddings remain absent.

## Safeguards present

- Pool-reset + target-guard in the fake-ingest harness (regression-tested).
- Single-commit transactional ingest (failed runs roll back data; run-row
  and failure audit persist separately).
- Version-skip on identical content; advisory-lock serialization; atomic
  retire/activate (see `backend/scripts/ingest_canonical_dataset.py`).

## Remaining limitations

- No test-target allowlist enforced suite-wide (only the ingest helper is
  guarded); other write-capable tests rely on fake/patched seams.
- Concurrent ingestion is serialized by advisory lock, proven only against
  fakes, not against live PostgreSQL contention.
- No backup/restore procedure exists for Supabase-hosted canonical data.
