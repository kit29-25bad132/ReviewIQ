"""Fail-closed test-database targeting for write-capable tests.

A test may only touch a database it can prove is disposable:

- empty/missing DSN  -> offline (fakes only): allowed;
- localhost / loopback / RFC-2606 special-use hosts (.invalid, .localhost,
  .test) -> disposable by DNS semantics: allowed;
- anything else (including ``*.supabase.co``) -> allowed ONLY when the
  operator explicitly opts in via ``REVIEWIQ_TEST_DSN`` set to the EXACT
  same DSN string.

Rationale: neither a fake-connection patch nor an invalid DSN alone is
sufficient, because an already-open pool can bypass both. Every
write-capable test must call :func:`require_ephemeral_test_target` with the
DSN it is about to use. The helper never logs or returns the DSN.
"""

import os
from urllib.parse import urlparse

#: Set this to the EXACT DSN of an approved disposable database to allow
#: write-capable tests against it. Never point it at production.
TEST_DSN_ENV_VAR = "REVIEWIQ_TEST_DSN"


def database_allowed(dsn) -> bool:
    """Return True only for targets that cannot be production data."""
    if not (dsn or "").strip():
        return True
    try:
        host = (urlparse(dsn.strip()).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    if (
        host.endswith(".invalid")
        or host.endswith(".localhost")
        or host.endswith(".test")
    ):
        return True
    explicit = (os.getenv(TEST_DSN_ENV_VAR) or "").strip()
    return bool(explicit) and dsn.strip() == explicit


def require_ephemeral_test_target(dsn) -> None:
    """Raise before any write-capable test step unless the target is safe."""
    if not database_allowed(dsn):
        raise RuntimeError(
            "Refusing write-capable test: database target is not an approved "
            f"disposable target. Set {TEST_DSN_ENV_VAR} to the exact test DSN "
            "to opt in explicitly. (DSN value withheld from this message.)"
        )
