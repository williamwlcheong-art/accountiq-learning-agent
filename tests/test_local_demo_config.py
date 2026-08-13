"""Guardrails for local no-key demo setup."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_env_example_keeps_openai_key_blank_and_documents_demo_mode():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "OPENAI_API_KEY=sk-YOUR_KEY_HERE" not in env_example
    assert "\nOPENAI_API_KEY=\n" in env_example
    assert "ACCOUNTIQ_DEMO_MODE=false" in env_example
    assert "ACCOUNTIQ_AUTH_DISABLED=false" in env_example
    assert "scripts/start-demo-backend.sh" in env_example
    assert "without a live OpenAI key" in env_example
    assert "without registering" in env_example


def test_start_demo_backend_explicitly_enables_demo_and_local_auth_bypass_without_fake_key():
    script = (ROOT / "scripts" / "start-demo-backend.sh").read_text(encoding="utf-8")

    assert "export ACCOUNTIQ_DEMO_MODE=true" in script
    assert 'export ACCOUNTIQ_AUTH_DISABLED="${ACCOUNTIQ_AUTH_DISABLED:-true}"' in script
    assert "OPENAI_API_KEY" not in script
