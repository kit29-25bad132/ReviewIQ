"""Versioned, non-destructive Supabase migration runner for ReviewIQ.

Commands (an explicit subcommand is REQUIRED — bare invocation only prints
usage and exits non-zero, so migrations can never run accidentally):

    python backend/scripts/migrate_supabase.py plan      # dry-run: list steps, no DB access
    python backend/scripts/migrate_supabase.py migrate   # apply in one transaction

Design:
- Ordered, versioned migrations; every statement is idempotent
  (``CREATE ... IF NOT EXISTS``), so repeated runs are safe no-ops.
- All statements execute inside a SINGLE transaction: any failure
  (including a precondition failure) rolls everything back — no partial state.
- Preconditions run before any DDL within that transaction. Migration 002
  refuses to proceed while more than one dataset version is active, listing
  the conflicting rows instead of guessing which is canonical.
- There is deliberately NO destructive reset path in this runner. The legacy
  ``DROP TABLE ... CASCADE`` behavior was a one-time legacy-shape upgrade
  whose triggering condition no longer exists. Staging resets are served by
  database/project recreation, not by in-script DROPs. No statement in the
  normal path drops, truncates, or deletes user data.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
MIGRATIONS_DIR = BASE_DIR / "migrations"
load_dotenv(BASE_DIR / ".env")


class MigrationPreconditionError(RuntimeError):
    """A target-database precondition failed; nothing was applied."""


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    sql_path: Optional[Path] = None
    sql_text: Optional[str] = None

    def statements(self) -> List[str]:
        if self.sql_text is not None:
            return [self.sql_text]
        if self.sql_path is not None:
            return [self.sql_path.read_text(encoding="utf-8")]
        raise MigrationPreconditionError(f"Migration {self.version} has no SQL source.")


def get_migrations() -> List[Migration]:
    """Ordered migration list. Pure function of the repository layout."""
    return [
        Migration(
            version="001",
            description="Canonical schema baseline (products, reviews, embeddings, ingestion metadata).",
            sql_path=ROOT_DIR / "supabase_canonical_schema.sql",
        ),
        Migration(
            version="002",
            description="Enforce at most one active dataset version.",
            sql_path=MIGRATIONS_DIR / "002_single_active_version.sql",
        ),
    ]


def check_single_active_precondition(cur) -> None:
    """Fail closed when several versions are active.

    Lists every conflicting row so the operator can resolve identity
    deliberately. Never deactivates rows automatically.
    Skips silently on a fresh database where the table does not exist yet.
    """
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'dataset_versions'
        )
    """)
    if not cur.fetchone()[0]:
        return  # table doesn't exist yet — fresh install, skip precondition
    cur.execute("""
        SELECT version_tag, dataset_name, row_count, product_count, created_at
        FROM public.dataset_versions
        WHERE is_active = true
        ORDER BY created_at;
    """)
    active = list(cur.fetchall() or [])
    if len(active) > 1:
        lines = "\n".join(
            f"  - version_tag={row[0]!r} dataset={row[1]!r} "
            f"rows={row[2]} products={row[3]} created={row[4]}"
            for row in active
        )
        raise MigrationPreconditionError(
            "Refusing migration 002: more than one dataset version is active.\n"
            f"{lines}\n"
            "Deactivate all but the intended canonical version with an approved "
            "per-row operation, then re-run."
        )


def plan() -> List[Migration]:
    """Dry-run: return ordered migrations, verifying SQL sources exist. No DB access."""
    migrations = get_migrations()
    for migration in migrations:
        if migration.sql_path is not None and not migration.sql_path.is_file():
            raise MigrationPreconditionError(
                f"Migration {migration.version} SQL file missing: {migration.sql_path}"
            )
    return migrations


def apply_all(cur) -> List[str]:
    """Run preconditions then all migration statements on one cursor.

    The caller owns the transaction: commit on success, rollback on any
    error (including precondition failure), so a failed run leaves no
    partial state. Returns applied migration versions.
    """
    check_single_active_precondition(cur)
    applied = []
    for migration in plan():
        for statement in migration.statements():
            cur.execute(statement)
        applied.append(migration.version)
    return applied


def run_migration() -> List[str]:
    import psycopg

    dsn = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not dsn:
        print("ERROR: DATABASE_URL or SUPABASE_DB_URL environment variable is required.")
        sys.exit(1)

    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg.connect(dsn)
    try:
        cur = conn.cursor()
        applied = apply_all(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Migration applied successfully: {applied}")
    return applied


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("plan", "migrate"):
        print(__doc__)
        print("Usage: python backend/scripts/migrate_supabase.py [plan|migrate]")
        return 2
    if args[0] == "plan":
        if len(args) != 1:
            print(__doc__)
            print("Usage: python backend/scripts/migrate_supabase.py [plan|migrate]")
            return 2
        for migration in plan():
            source = str(migration.sql_path) if migration.sql_path else "<inline>"
            print(f"{migration.version}: {migration.description} [{source}]")
        return 0
    if len(args) != 1:  # unknown flags (e.g. --destroy) never reach migration
        print(__doc__)
        print("Usage: python backend/scripts/migrate_supabase.py [plan|migrate]")
        return 2
    run_migration()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
