import os
import sys

import pytest

# Allow imports like "from services.ai_analyzer import ..." when running
# pytest from the repository root.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@pytest.fixture(autouse=True)
def hermetic_provider_env(monkeypatch):
    """Keep every test free of real fallback-provider credentials.

    backend/.env carries real GROQ_API_KEY / OPENROUTER_API_KEY values that land
    in os.environ at import time, and AIAnalyzerService.api_key re-injects them
    via load_dotenv(override=True) on every access. Block that re-injection and
    neutralize both fallback keys for each test so no chain ever reaches a real
    provider endpoint. GEMINI_API_KEY is left untouched: Gemini-only tests
    configure or remove it explicitly to match their scenario.

    ROUTING_STRATEGY is also neutralized so every test starts from the
    gemini_first default; V2-P6 routing tests opt in explicitly via
    monkeypatch.setenv (which runs after this fixture).
    """
    monkeypatch.setattr("services.ai_analyzer.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ROUTING_STRATEGY", raising=False)
