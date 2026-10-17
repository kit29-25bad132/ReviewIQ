"""Gate 14 — offline CORS configuration tests (no live network).

CORS origins are read ONCE at import time of ``backend/main.py`` and baked
into the middleware, so each test rebuilds the app from a patched
environment via ``importlib.reload`` with ``load_dotenv`` neutralized. That
keeps a developer's real ``backend/.env`` from injecting a live
``ALLOWED_ORIGINS`` value into the default-configuration tests.

All requests are dispatched in-process by FastAPI's TestClient (OPTIONS
preflights only) — no real Render/Vercel endpoints, no provider calls, no
database access, no new dependencies.

Other test modules resolve ``from main import app`` at collection time
(before execution), so they keep the original app instance regardless of the
reloads performed here; an autouse teardown reloads ``main`` once more with
the original environment so ``sys.modules["main"]`` ends in the same state
the suite originally imported.
"""

import importlib

import dotenv
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main

# Origins used by the assertions (repository-documented values only).
VERCEL_ORIGIN = "https://reviewiq-final.vercel.app"
FOREIGN_ORIGIN = "https://evil.example.test"
CONFIGURED_ORIGIN = "https://staging.example.test"

# A valid preflight for POST /api/analyze-review (a route that always exists).
PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


def _cors_app(monkeypatch, origins: str | None) -> FastAPI:
    """Rebuild ``main.app`` from a patched ``ALLOWED_ORIGINS`` environment.

    ``origins=None`` means "no override" — the code default in backend/main.py
    (loopback origins + loopback-only regex) applies.
    """
    # Neutralize backend/.env: python-dotenv never overrides an EXISTING var,
    # but it WOULD inject a value into a key we deleted, which would silently
    # break the default-config tests on machines with a real backend/.env.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    if origins is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", origins)
    return importlib.reload(main).app


@pytest.fixture(autouse=True)
def _restore_main_module():
    """After this module's tests, reload main with the original environment
    (monkeypatch already unwound) so later tests see the default config."""
    yield
    importlib.reload(main)


def _preflight(app: FastAPI, origin: str):
    """Dispatch an in-process CORS preflight (no sockets, no live network)."""
    client = TestClient(app)
    headers = {"Origin": origin, **PREFLIGHT_HEADERS}
    return client.options("/api/analyze-review", headers=headers)


def test_cors_allows_configured_origin(monkeypatch):
    """An origin listed in ALLOWED_ORIGINS passes the preflight."""
    app = _cors_app(monkeypatch, CONFIGURED_ORIGIN)
    resp = _preflight(app, CONFIGURED_ORIGIN)
    assert resp.status_code == 200
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin is not None, "preflight response must carry the allow-origin header"
    assert allow_origin == CONFIGURED_ORIGIN
    assert "POST" in resp.headers.get("access-control-allow-methods", "")


def test_cors_blocks_unconfigured_origin(monkeypatch):
    """A foreign origin is rejected under the default loopback config."""
    app = _cors_app(monkeypatch, None)
    resp = _preflight(app, FOREIGN_ORIGIN)
    # Starlette answers a disallowed preflight without ACAO headers.
    assert FOREIGN_ORIGIN not in (resp.headers.get("access-control-allow-origin") or "")


def test_cors_default_blocks_production_vercel_origin(monkeypatch):
    """Documents the Gate 13 gap: the DEFAULT configuration (loopback origins
    + loopback-only regex) does not allow the production Vercel origin. This
    is the known configuration risk, not a bug to fix here — the test fails if
    someone changes the default in an unintended way (e.g. widening the
    regex to all hosts), which is exactly the accidental "fix" it guards."""
    app = _cors_app(monkeypatch, None)
    resp = _preflight(app, VERCEL_ORIGIN)
    assert VERCEL_ORIGIN not in (resp.headers.get("access-control-allow-origin") or "")


def test_cors_allows_production_origin_when_configured(monkeypatch):
    """The documented repair works: setting ALLOWED_ORIGINS to the Vercel
    origin makes the preflight succeed."""
    app = _cors_app(monkeypatch, VERCEL_ORIGIN)
    resp = _preflight(app, VERCEL_ORIGIN)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == VERCEL_ORIGIN
