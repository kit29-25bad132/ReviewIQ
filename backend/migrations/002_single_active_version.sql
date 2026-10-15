-- =========================================================
-- ReviewIQ migration 002 — single active dataset version
-- =========================================================
-- Enforces the global single-active invariant: the catalog serves exactly
-- one canonical corpus, so at most one dataset_versions row may carry
-- is_active = true (regardless of dataset_name — fixture rows included).
--
-- PRECONDITION (enforced by the runner before executing this file):
-- at most one row with is_active = true. If several are active, the
-- runner aborts with a diagnostic listing them; it never guesses which
-- row is canonical and never deactivates rows by itself. Resolve the
-- conflict with an approved per-row operation first, then re-run.
--
-- Repeatable: IF NOT EXISTS makes re-execution a no-op.
-- =========================================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_versions_single_active
    ON public.dataset_versions (is_active) WHERE is_active;
