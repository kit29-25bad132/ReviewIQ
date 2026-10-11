"""Gate 5 — versioned reproducible quality reports.

Change 2 (pure quality gate, no DB, no repo file I/O beyond pytest tmp_path):
repeat evaluations of identical input must be byte-identical modulo
timestamp/ingestion_run_id, versions must be present, and changed input must
change the version hash.

Change 3 (DB history integrity via a faithful fake-transaction harness):
two runs on different input must append two separate quality-report rows
(plain INSERT history, never an upsert), each with a distinct created_at and
the correct dataset_version; a mocked mid-run failure must leave zero new
rows anywhere (failed transaction rolls back on close, mirroring psycopg).

Requires the same environment as test_data_quality_pipeline.py
(pandas/pandera/duckdb). No Supabase access: psycopg.connect is faked and
DATABASE_URL points at an invalid host, so a missed mock cannot touch prod.
"""

import copy
import csv
import importlib.util
import itertools
import json
import os
import threading
from pathlib import Path

import pytest

from services.quality.quality_gate import quality_gate_runner
from tests.db_guard import require_ephemeral_test_target

BACKEND_DIR = Path(__file__).resolve().parent.parent

COLUMNS = [
    "review_id", "product_id", "product_name", "brand", "category",
    "price_inr", "rating", "review_title", "review_text", "language",
    "sentiment", "verified_purchase", "helpful_votes", "review_date",
    "word_count",
]


def _base_rows():
    return [
        ["R1", "P01", "Alpha One", "BrandA", "Phones", 999, 5, "Great",
         "Alpha battery lasts for days on end.", "en", "positive", True, 3, "2024-01-01", 7],
        ["R2", "P01", "Alpha One", "BrandA", "Phones", 999, 2, "Flicker",
         "Alpha screen flickers in low light daily.", "en", "negative", True, 1, "2024-01-02", 7],
        ["R3", "P02", "Beta Two", "BrandB", "Audio", 199, 4, "Sturdy",
         "Beta build feels sturdy and premium.", "en", "positive", True, 5, "2024-01-03", 6],
        ["R4", "P02", "Beta Two", "BrandB", "Audio", 199, 1, "Melted",
         "Beta charger melted on first use today.", "en", "negative", False, 0, "2024-01-04", 7],
    ]


def _write_csv(path: Path, rows) -> Path:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path


def _dump(report) -> str:
    return json.dumps(report.model_dump(exclude={"timestamp", "ingestion_run_id"}),
                      sort_keys=True, default=str)


# ---------------- Change 2: deterministic repeat runs ----------------

def test_repeat_runs_byte_identical_excluding_timestamp_and_run_id(tmp_path):
    csv_path = _write_csv(tmp_path / "dataset.csv", _base_rows())
    passed1, report1 = quality_gate_runner.evaluate_csv(csv_path)
    passed2, report2 = quality_gate_runner.evaluate_csv(csv_path)
    assert passed1 and passed2
    assert _dump(report1) == _dump(report2)
    assert report1.dataset_version and report2.dataset_version
    assert report1.dataset_version == report2.dataset_version


def test_version_present_and_changes_with_input(tmp_path):
    csv_a = _write_csv(tmp_path / "a.csv", _base_rows())
    _, report_a = quality_gate_runner.evaluate_csv(csv_a)
    assert report_a.dataset_version and report_a.dataset_version.startswith("hash_")

    altered = _base_rows()
    altered[3] = list(altered[3])
    altered[3][8] = "Beta charger melted on second use today."
    csv_b = _write_csv(tmp_path / "b.csv", altered)
    _, report_b = quality_gate_runner.evaluate_csv(csv_b)
    assert report_b.dataset_version
    assert report_b.dataset_version != report_a.dataset_version


# ---------------- Change 3: DB history integrity ----------------

# Advisory-lock registry for the fake harness, keyed by id(store). Real
# PostgreSQL serializes holders inside the server; the fake mirrors that
# with one lock per store so interleaving tests are deterministic.
_advisory_locks = {}
_advisory_holders = {}


def _advisory_acquire(store, owner_id, timeout=30.0) -> None:
    key = id(store)
    lock = _advisory_locks.setdefault(key, threading.Lock())
    if not lock.acquire(timeout=timeout):
        raise AssertionError("fake advisory lock timed out: would deadlock in production")
    _advisory_holders[key] = owner_id


def _advisory_release(store, owner_id) -> None:
    key = id(store)
    if _advisory_holders.get(key) == owner_id:
        _advisory_holders.pop(key, None)
        lock = _advisory_locks.get(key)
        if lock is not None:
            try:
                lock.release()
            except RuntimeError:
                pass  # already released


class _FakeClock:
    """Monotonic timestamps so test-created rows are strictly ordered,
    mirroring DB now() without wall-clock flakiness."""

    def __init__(self):
        self._ticks = itertools.count()

    def tick(self) -> str:
        return f"2026-01-01T00:00:{next(self._ticks):02d}+00:00"


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._fetch = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _staged(self):
        return self._conn.staged

    def execute(self, sql, params=None):
        params = params or ()
        norm = " ".join(sql.split()).upper()
        store = self._staged()
        if norm.startswith("INSERT INTO PUBLIC.DATA_INGESTION_RUNS"):
            run_id = f"run-{len(store['ingestion_runs']) + 1}"
            store["ingestion_runs"].append({
                "id": run_id, "dataset_name": params[0], "dataset_version": params[1],
                "validation_status": "PENDING", "quality_status": "PENDING",
                "metrics": json.loads(params[6]), "completed_at": None,
                "accepted_rows": 0,
            })
            self._fetch = [(run_id,)]
        elif norm.startswith("SELECT VERSION_TAG"):
            versions = store["dataset_versions"]
            self._fetch = [(versions[-1]["version_tag"],)] if versions else None
        elif norm.startswith("SELECT PG_ADVISORY"):
            # Keyed by the SHARED store, not the per-connection staged copy:
            # server-side advisory locks are global to the database, so two
            # connections staging different copies must still contend.
            _advisory_acquire(self._conn._store, id(self._conn))
            self._fetch = [(True,)]
        elif norm.startswith("UPDATE PUBLIC.DATA_INGESTION_RUNS"):
            payload, run_id = params[0], params[-1]
            data = json.loads(payload) if isinstance(payload, str) else payload
            for row in store["ingestion_runs"]:
                if row["id"] == run_id:
                    if "VALIDATED" in sql or "FAILED" in sql:
                        row["validation_status"] = "VALIDATED" if "VALIDATED" in sql else "FAILED"
                        row["quality_status"] = "PASSED" if "PASSED" in sql else "FAILED"
                        if "accepted_rows" in sql:
                            row["accepted_rows"] = params[0] if isinstance(params[0], int) else row["accepted_rows"]
                    if isinstance(data, dict):
                        merged = dict(row.get("metrics") or {})
                        merged.update(data)
                        row["metrics"] = merged
                    row["completed_at"] = self._conn.clock.tick()
            self._fetch = None
        elif norm.startswith("DELETE FROM PUBLIC.REVIEWS"):
            store["reviews"] = []
        elif norm.startswith("DELETE FROM PUBLIC.PRODUCTS"):
            store["products"] = []
        elif norm.startswith("INSERT INTO PUBLIC.PRODUCTS"):
            pid = params[0]
            for row in store["products"]:
                if row["source_product_id"] == pid:  # upsert keeps the stable id
                    row.update({"name": params[1], "brand": params[2], "category": params[3]})
                    self._fetch = [(row["id"], pid)]
                    break
            else:
                new_id = f"uuid-{pid}"
                store["products"].append({
                    "id": new_id, "source_product_id": pid,
                    "name": params[1], "brand": params[2], "category": params[3],
                })
                self._fetch = [(new_id, pid)]
        elif norm.startswith("INSERT INTO PUBLIC.DATA_QUALITY_REPORTS"):
            store["quality_reports"].append({
                "dataset_version": params[0], "ingestion_run_id": params[1],
                "status": params[2], "created_at": self._conn.clock.tick(),
            })
        elif norm.startswith("INSERT INTO PUBLIC.DATASET_VERSIONS"):
            if self._conn.fail_versions:
                raise RuntimeError("mocked activation failure")
            tag = params[0]
            # Mirror migration 002's partial unique index: at most one
            # is_active=true row may exist when the new row activates.
            actives = [r for r in store["dataset_versions"] if r.get("is_active")]
            if actives and not any(r["version_tag"] == tag for r in actives):
                raise RuntimeError(
                    'duplicate key value violates unique constraint '
                    '"uq_dataset_versions_single_active"')
            for row in store["dataset_versions"]:
                if row["version_tag"] == tag:
                    row.update({"is_active": True})
                    break
            else:
                store["dataset_versions"].append(
                    {"version_tag": tag, "is_active": True,
                     "created_at": self._conn.clock.tick()})
        elif norm.startswith("UPDATE PUBLIC.DATASET_VERSIONS"):
            # Deactivate-first activation switch (same transaction as the
            # INSERT above): retire every active version; the subsequent
            # INSERT activates exactly one, satisfying the partial index.
            for row in store["dataset_versions"]:
                if row.get("is_active"):
                    row["is_active"] = False
        else:
            raise AssertionError(f"Fake cursor hit unexpected SQL: {sql[:80]}")

    def executemany(self, sql, seq):
        norm = " ".join(sql.split()).upper()
        if norm.startswith("INSERT INTO PUBLIC.REVIEWS"):
            if self._conn.fail_reviews:
                raise RuntimeError("mocked mid-run DB failure")
            store = self._staged()
            for params in seq:
                s_rid = params[2]
                for row in store["reviews"]:
                    if row["source_review_id"] == s_rid:
                        break
                else:
                    store["reviews"].append({"source_review_id": s_rid})
        else:
            raise AssertionError(f"Fake cursor hit unexpected executemany: {sql[:80]}")

    def fetchone(self):
        if not self._fetch:
            return None
        return self._fetch[0]


class _FakeConnection:
    """Mimics psycopg transactional discipline: writes stage privately and
    persist only on commit(); close() without commit discards everything."""

    def __init__(self, store, clock, fail_reviews=False, fail_versions=False):
        self._store = store
        self.clock = clock
        self.fail_reviews = fail_reviews
        self.fail_versions = fail_versions
        self.staged = None

    def _ensure_staged(self):
        if self.staged is None:
            self.staged = copy.deepcopy(self._store)
        return self.staged

    @property
    def staged_view(self):
        return self._ensure_staged()

    def cursor(self):
        self._ensure_staged()
        return _FakeCursor(self)

    def commit(self):
        if self.staged is None:
            return
        for key in self._store:
            self._store[key] = self.staged[key]
        _advisory_release(self._store, id(self))

    def close(self):
        self.staged = None
        _advisory_release(self._store, id(self))


def _load_ingest_module():
    spec = importlib.util.spec_from_file_location(
        "ingest_canonical_dataset", BACKEND_DIR / "scripts" / "ingest_canonical_dataset.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fresh_store():
    return {"ingestion_runs": [], "products": [], "reviews": [],
            "quality_reports": [], "dataset_versions": []}


def _reset_pool():
    """Drop the process-wide connection pool so each fake-ingest run builds
    a fresh pool through the patched psycopg.connect.

    Cause being fixed: PostgresDatabase._pool is class-level and survives
    across tests. In any session where a live test opened the real pool
    first, _get_pool() returns it without ever calling psycopg.connect —
    silently bypassing this file's monkeypatch and running REAL ingestion
    against production (this exact failure wiped the canonical tables on
    2026-10-11). Resetting before AND after each run confines the fake pool
    to the test and restores lazy live-pool behavior afterwards.
    """
    from services.retrieval.database import PostgresDatabase
    pool, PostgresDatabase._pool = PostgresDatabase._pool, None
    if pool is not None:
        try:
            pool.close()
        except Exception:
            pass


def _run_ingest(monkeypatch, store, clock, csv_path, fail_reviews=False, fail_versions=False):
    import psycopg

    def fake_connect(*args, **kwargs):
        return _FakeConnection(store, clock, fail_reviews=fail_reviews,
                               fail_versions=fail_versions)

    _reset_pool()
    try:
        monkeypatch.setattr(psycopg, "connect", fake_connect)
        monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/reviewiq")
        # Fail-closed target guard: proves the DSN cannot be production before
        # any write-capable step runs (pool-reset below handles reuse bypass).
        require_ephemeral_test_target(os.environ["DATABASE_URL"])
        module = _load_ingest_module()
        return module.ingest_canonical_dataset(csv_path)
    finally:
        _reset_pool()


def test_two_runs_append_two_history_rows_with_versions(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    csv_a = _write_csv(tmp_path / "a.csv", _base_rows())
    altered = _base_rows()
    altered[3] = list(altered[3])
    altered[3][8] = "Beta charger melted on second use today."
    csv_b = _write_csv(tmp_path / "b.csv", altered)

    assert _run_ingest(monkeypatch, store, clock, csv_a) is True
    assert _run_ingest(monkeypatch, store, clock, csv_b) is True

    quality = store["quality_reports"]
    assert len(quality) == 2, "reruns must APPEND history rows, never upsert/overwrite"
    assert quality[0]["dataset_version"] != quality[1]["dataset_version"]
    assert quality[0]["created_at"] != quality[1]["created_at"]
    assert all(q["dataset_version"] for q in quality)
    # Reload semantics preserved: second run replaced, not duplicated, the corpus.
    assert len(store["products"]) == 2
    assert len(store["reviews"]) == 4


def test_mid_run_failure_inserts_zero_rows(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    csv_a = _write_csv(tmp_path / "a.csv", _base_rows())
    assert _run_ingest(monkeypatch, store, clock, csv_a) is True
    snapshot = copy.deepcopy(store)

    # A third input variant (new version hash) forces a real reload attempt
    # — reusing csv_a would take the version-skip path and prove nothing.
    doomed = _base_rows()
    doomed[0] = list(doomed[0])
    doomed[0][8] = "Alpha battery lasts for weeks on end, honestly."
    csv_c = _write_csv(tmp_path / "c.csv", doomed)
    with pytest.raises(RuntimeError, match="mocked mid-run DB failure"):
        _run_ingest(monkeypatch, store, clock, csv_c, fail_reviews=True)

    # Failed transaction rolled back on close: no partial quality row,
    # no wiped-then-half-reloaded corpus. Pre-existing rows byte-identical.
    assert store["quality_reports"] == snapshot["quality_reports"]
    assert store["products"] == snapshot["products"]
    assert store["reviews"] == snapshot["reviews"]
    # The run row was pre-committed before the main transaction (Gate 3 amendment),
    # so the failure-audit UPDATE always finds its row. Verify it was marked FAILED.
    failed_runs = [
        r for r in store["ingestion_runs"]
        if r["validation_status"] == "FAILED" and r["quality_status"] == "FAILED"
    ]
    assert len(failed_runs) == 1, "failed run must persist a FAILED/FAILED audit row"
    assert failed_runs[0]["completed_at"] is not None
