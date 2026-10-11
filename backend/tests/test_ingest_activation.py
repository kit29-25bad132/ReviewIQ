"""Stage 2A — ingest activation, retirement, skip, failure, concurrency.

Offline: reuses the fake-transaction harness from
test_quality_report_reproducibility (in-memory stores, tmp CSVs, no DB, no
provider calls). Same environment requirements (pandas/pandera/duckdb).

Covers the version-invariant contract:
- first ingest activates exactly one version;
- replacement retires the previous version atomically in the same transaction;
- identical reruns skip with actives untouched;
- failures (mid-run and during activation) preserve the previous active;
- concurrent runs serialize on the advisory lock (deterministic, bounded);
- write-capable tests refuse non-disposable database targets.
"""

import threading
import time

import pytest

from tests.db_guard import TEST_DSN_ENV_VAR, require_ephemeral_test_target, database_allowed
from tests.test_quality_report_reproducibility import (
    _base_rows,
    _FakeConnection,
    _fresh_store,
    _FakeClock,
    _run_ingest,
    _write_csv,
)


def _altered_rows():
    rows = [list(r) for r in _base_rows()]
    rows[0][2] = "Alpha One v2"
    rows[3] = list(rows[3])
    rows[3][8] = "Beta charger melted on second use today."
    return rows


def _actives(store):
    return [r for r in store["dataset_versions"] if r.get("is_active")]


def _product_names(store):
    return sorted(r.get("name", "?") for r in store["products"])


def test_first_ingest_activates_single_version(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    assert _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "a.csv", _base_rows())) is True
    actives = _actives(store)
    assert len(actives) == 1
    assert actives[0]["version_tag"].startswith("hash_")
    assert len(store["products"]) == 2
    assert len(store["reviews"]) == 4


def test_replacement_retires_previous_atomically(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    assert _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "a.csv", _base_rows())) is True
    first_tag = _actives(store)[0]["version_tag"]
    assert "Alpha One v2" not in _product_names(store)

    assert _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "b.csv", _altered_rows())) is True
    actives = _actives(store)
    assert len(actives) == 1, "exactly one version may be active after replacement"
    assert actives[0]["version_tag"] != first_tag
    assert "Alpha One v2" in _product_names(store)
    # History preserved: both version rows exist, old one retired.
    assert len(store["dataset_versions"]) == 2
    assert len(store["quality_reports"]) == 2


def test_identical_rerun_skips_and_preserves_actives(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    csv_a = _write_csv(tmp_path / "a.csv", _base_rows())
    assert _run_ingest(monkeypatch, store, clock, csv_a) is True
    before_versions = [dict(r) for r in store["dataset_versions"]]
    before_quality = len(store["quality_reports"])
    assert _run_ingest(monkeypatch, store, clock, csv_a) is True
    assert _actives(store) == [r for r in before_versions if r.get("is_active")]
    assert len(store["quality_reports"]) == before_quality
    assert [r["version_tag"] for r in store["dataset_versions"]] == [r["version_tag"] for r in before_versions]


def test_failed_ingest_preserves_previous_active(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    assert _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "a.csv", _base_rows())) is True
    good_tag = _actives(store)[0]["version_tag"]
    with pytest.raises(RuntimeError, match="mocked mid-run DB failure"):
        _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "c.csv", _altered_rows()),
                    fail_reviews=True)
    actives = _actives(store)
    assert len(actives) == 1 and actives[0]["version_tag"] == good_tag
    assert "Alpha One v2" not in _product_names(store)


def test_activation_failure_preserves_previous_active(tmp_path, monkeypatch):
    store, clock = _fresh_store(), _FakeClock()
    assert _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "a.csv", _base_rows())) is True
    good_tag = _actives(store)[0]["version_tag"]
    with pytest.raises(RuntimeError, match="mocked activation failure"):
        _run_ingest(monkeypatch, store, clock, _write_csv(tmp_path / "c.csv", _altered_rows()),
                    fail_versions=True)
    # Version insert failed before retire/update: previous active untouched,
    # no new version row, no new quality row, corpus unchanged.
    actives = _actives(store)
    assert len(actives) == 1 and actives[0]["version_tag"] == good_tag
    assert [r["version_tag"] for r in store["dataset_versions"]] == [good_tag]
    assert len(store["quality_reports"]) == 1
    assert "Alpha One v2" not in _product_names(store)


def test_concurrent_second_ingest_waits_for_lock(tmp_path, monkeypatch):
    import psycopg

    store, clock = _fresh_store(), _FakeClock()
    csv_a = _write_csv(tmp_path / "a.csv", _base_rows())
    csv_b = _write_csv(tmp_path / "b.csv", _altered_rows())
    assert _run_ingest(monkeypatch, store, clock, csv_a) is True
    assert [r["version_tag"] for r in _actives(store)] != []

    # Main thread holds the advisory lock directly, like a running ingest.
    holder = _FakeConnection(store, clock)
    holder.cursor().execute("SELECT pg_advisory_xact_lock(hashtext('reviewiq_canonical_ingest_v1'))")

    outcome, errors = {}, {}

    def run_b():
        try:
            outcome["rc"] = _run_ingest(monkeypatch, store, clock, csv_b)
        except Exception as exc:  # noqa: BLE001 - surfaced below
            errors["e"] = exc

    worker = threading.Thread(target=run_b, daemon=True)
    worker.start()
    time.sleep(2.0)
    # B cannot have passed the lock: no new version, no data change
    # (its pre-lock audit row is the only permitted addition).
    assert [r["version_tag"] for r in _actives(store)] != []
    assert "Alpha One v2" not in _product_names(store)
    assert len(store["quality_reports"]) == 1
    holder.close()  # releases the advisory lock; B proceeds
    worker.join(timeout=120)
    assert not worker.is_alive(), "worker did not finish after lock release"
    assert "e" not in errors, f"worker failed: {errors.get('e')!r}"
    assert outcome.get("rc") is True
    actives = _actives(store)
    assert len(actives) == 1
    assert "Alpha One v2" in _product_names(store)


@pytest.mark.parametrize("dsn,env,expected", [
    ("", None, True),
    ("   ", None, True),
    ("postgresql://localhost/mydb", None, True),
    ("postgresql://127.0.0.1:5432/x", None, True),
    ("postgresql://test.invalid/reviewiq", None, True),
    ("postgresql://db.internal.test/db", None, True),
    ("postgresql://db.abc123.supabase.co:5432/postgres", None, False),
    ("postgresql://db.abc123.supabase.co:5432/postgres",
     "postgresql://db.abc123.supabase.co:5432/postgres", True),
    ("postgresql://db.abc123.supabase.co:5432/postgres",
     "postgresql://db.other.supabase.co:5432/postgres", False),
    ("postgresql://example.com/db", None, False),
    ("not-a-dsn", None, False),
    ("postgresql://user:secret@db.abc123.supabase.co:5432/postgres", None, False),
])
def test_database_allowlist_table(monkeypatch, dsn, env, expected):
    monkeypatch.delenv(TEST_DSN_ENV_VAR, raising=False)
    if env is not None:
        monkeypatch.setenv(TEST_DSN_ENV_VAR, env)
    assert database_allowed(dsn) is expected
    if expected:
        require_ephemeral_test_target(dsn)  # must not raise
    else:
        with pytest.raises(RuntimeError):
            require_ephemeral_test_target(dsn)
