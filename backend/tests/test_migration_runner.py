"""Stage 2A — migration runner safety (offline, no DB).

The script under test is loaded by path (repo precedent); the database is a
statement-capturing fake. Nothing here connects anywhere.
"""

import importlib.util
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_migrate():
    spec = importlib.util.spec_from_file_location(
        "migrate_supabase", BACKEND_DIR / "scripts" / "migrate_supabase.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeCursor:
    def __init__(self, active_versions=(), table_exists=True):
        self.statements = []
        self._actives = list(active_versions)
        self._table_exists = table_exists
        self._last_was_exists_check = False

    def execute(self, sql, params=None):
        self.statements.append(sql)
        norm = " ".join(sql.split()).upper()
        if "INFORMATION_SCHEMA" in norm and "DATASET_VERSIONS" in norm:
            self._last_was_exists_check = True
            self._rows = []
        elif "FROM PUBLIC.DATASET_VERSIONS" in norm and "IS_ACTIVE" in norm:
            self._last_was_exists_check = False
            self._rows = [
                (v["version_tag"], v["dataset_name"], v["row_count"],
                 v["product_count"], v["created_at"])
                for v in self._actives
            ]
        else:
            self._last_was_exists_check = False
            self._rows = []

    def fetchone(self):
        if self._last_was_exists_check:
            self._last_was_exists_check = False
            return (self._table_exists,)
        return None

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, cursor, fail_on=None):
        self._cursor = cursor
        self.fail_on = fail_on
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def _version(tag, name="product_reviews_dataset.csv"):
    return {"version_tag": tag, "dataset_name": name, "row_count": 1500,
            "product_count": 20, "created_at": "2026-01-01T00:00:00+00:00"}


def test_plan_lists_ordered_migrations_without_db():
    mod = _load_migrate()
    planned = mod.plan()
    assert [m.version for m in planned] == ["001", "002"]
    assert all(m.sql_path is not None for m in planned)


def test_migrate_applies_in_single_transaction(monkeypatch):
    mod = _load_migrate()
    cur = _FakeCursor(active_versions=[_version("hash_aaa")])
    conn = _FakeConn(cur)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/db")
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: conn)
    assert mod.run_migration() == ["001", "002"]
    assert conn.committed and not conn.rolled_back
    assert any("create table" in s.lower() for s in cur.statements)


def test_repeat_migrate_is_idempotent(monkeypatch):
    mod = _load_migrate()
    runs = []
    for _ in range(2):
        cur = _FakeCursor(active_versions=[_version("hash_aaa")])
        conn = _FakeConn(cur)
        monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/db")
        import psycopg
        monkeypatch.setattr(psycopg, "connect", lambda *a, **k: conn)
        runs.append(mod.run_migration())
    assert runs == [["001", "002"], ["001", "002"]]


def test_multiple_active_versions_fail_with_diagnostic(monkeypatch):
    mod = _load_migrate()
    cur = _FakeCursor(active_versions=[_version("hash_aaa"), _version("hash_bbb", "a.csv")])
    conn = _FakeConn(cur)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/db")
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: conn)
    with pytest.raises(mod.MigrationPreconditionError) as excinfo:
        mod.run_migration()
    assert "hash_aaa" in str(excinfo.value) and "hash_bbb" in str(excinfo.value)
    assert conn.rolled_back and not conn.committed
    assert not any("CREATE " in s.upper() for s in cur.statements), \
        "no DDL may execute after a precondition failure"


def test_precondition_skips_on_fresh_database_without_table(monkeypatch):
    # 8A regression guard: on a fresh database dataset_versions does not
    # exist yet, so the precondition must skip instead of raising
    # UndefinedTable, letting migration 001 create the table.
    mod = _load_migrate()
    cur = _FakeCursor(active_versions=[], table_exists=False)
    conn = _FakeConn(cur)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/db")
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: conn)
    assert mod.run_migration() == ["001", "002"]
    assert conn.committed and not conn.rolled_back


def test_unexpected_state_rolls_back_without_partial_effects(monkeypatch):
    mod = _load_migrate()

    class BoomCursor(_FakeCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "CREATE UNIQUE INDEX" in sql.upper():
                raise RuntimeError("mocked DDL failure")

    cur = BoomCursor(active_versions=[_version("hash_aaa")])
    conn = _FakeConn(cur)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/db")
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: conn)
    with pytest.raises(RuntimeError, match="mocked DDL failure"):
        mod.run_migration()
    assert conn.rolled_back and not conn.committed


def test_normal_path_contains_no_destructive_statements(monkeypatch):
    import re
    mod = _load_migrate()
    cur = _FakeCursor(active_versions=[])
    conn = _FakeConn(cur)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/db")
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: conn)
    mod.run_migration()
    destructive = re.compile(r"\b(DROP\s+TABLE|TRUNCATE|DELETE\s+FROM)\b", re.IGNORECASE)
    hits = [s for s in cur.statements if destructive.search(s)]
    assert hits == [], f"destructive statements reachable from normal path: {hits}"


def test_bare_and_unknown_commands_exit_nonzero_without_db():
    mod = _load_migrate()
    assert mod.main([]) == 2
    assert mod.main(["destroy"]) == 2
    assert mod.main(["migrate", "--destroy"]) == 2


def test_migrate_requires_dsn(monkeypatch):
    mod = _load_migrate()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        mod.run_migration()
    assert excinfo.value.code == 1
