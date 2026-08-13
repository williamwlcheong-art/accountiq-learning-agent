"""Tests for Phase 3.5: Admin Gate + User Wizard Shell (AUTH-09, UX-01)."""
import pytest
import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register(client, email="alice@example.com", password="correcthorse"):
    return await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )


async def _register_admin(client, email="admin@example.com", password="correcthorse"):
    """Register a user as admin by patching the module-level OWNER_EMAIL constant."""
    import auth as _auth_module
    original = _auth_module.OWNER_EMAIL
    _auth_module.OWNER_EMAIL = email.lower()
    try:
        r = await client.post(
            "/auth/register",
            data={"email": email, "password": password},
        )
    finally:
        _auth_module.OWNER_EMAIL = original
    return r


# ---------------------------------------------------------------------------
# AUTH-09: is_admin assignment at registration
# ---------------------------------------------------------------------------

async def test_owner_email_gets_admin(client, fresh_all_db):
    """AUTH-09: OWNER_EMAIL registration grants is_admin=1."""
    r = await _register_admin(client, "admin@example.com")
    assert r.status_code == 201, r.text
    me = await client.get("/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["is_admin"] == 1


async def test_regular_user_not_admin(client, fresh_all_db):
    """AUTH-09: non-OWNER_EMAIL registration gets is_admin=0."""
    await _register(client, "user@example.com")
    me = await client.get("/auth/me")
    assert me.json()["is_admin"] == 0


async def test_me_returns_is_admin(client, fresh_all_db):
    """AUTH-09: /auth/me response includes is_admin field."""
    await _register(client, "user@example.com")
    me = await client.get("/auth/me")
    assert "is_admin" in me.json()


# ---------------------------------------------------------------------------
# AUTH-09: admin gate on existing routes (Plan 02 will make these green)
# ---------------------------------------------------------------------------

async def test_regular_user_companies_403(client, fresh_all_db):
    """AUTH-09: non-admin GET /companies returns 403."""
    await _register(client, "user@example.com")
    r = await client.get("/companies")
    assert r.status_code == 403, r.text


async def test_regular_user_financials_403(client, fresh_all_db):
    """AUTH-09: non-admin GET /financials/1 returns 403."""
    await _register(client, "user@example.com")
    r = await client.get("/financials/1")
    assert r.status_code == 403, r.text


async def test_regular_user_patterns_403(client, fresh_all_db):
    """AUTH-09: non-admin GET /patterns returns 403."""
    await _register(client, "user@example.com")
    r = await client.get("/patterns")
    assert r.status_code == 403, r.text


async def test_regular_user_settings_403(client, fresh_all_db):
    """AUTH-09: non-admin GET /settings returns 403."""
    await _register(client, "user@example.com")
    r = await client.get("/settings")
    assert r.status_code == 403, r.text


async def test_admin_user_companies_200(client, fresh_all_db):
    """AUTH-09: admin user GET /companies returns 200."""
    await _register_admin(client, "admin@example.com")
    r = await client.get("/companies")
    assert r.status_code == 200, r.text


async def test_admin_settings_explains_demo_mode_without_treating_placeholder_as_live_key(
    client,
    fresh_all_db,
    monkeypatch,
):
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-e2e-placeholder")

    response = await client.get("/settings")

    assert response.status_code == 200, response.text
    assert response.json()["demo_mode"] is True
    assert response.json()["demo_mode_forced"] is True
    assert response.json()["api_key_set"] is False
    assert response.json()["api_key_preview"] == ""


def test_admin_live_research_setup_error_names_evidence_and_live_key_paths():
    import main as main_module

    detail = main_module._live_research_connection_error_detail({"is_admin": 1})

    assert "evidence mode" in detail
    assert "commercial AI key" in detail
    assert "OpenAI API key" in detail


async def test_admin_settings_reports_explicit_demo_mode_without_live_key(
    client,
    fresh_all_db,
    monkeypatch,
):
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setenv("ACCOUNTIQ_DEMO_MODE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = await client.get("/settings")

    assert response.status_code == 200, response.text
    assert response.json()["demo_mode"] is True
    assert response.json()["demo_mode_configured"] is True
    assert response.json()["demo_mode_forced"] is False
    assert response.json()["api_key_set"] is False


async def test_admin_can_save_openai_key_and_model(client, fresh_all_db, monkeypatch, tmp_path):
    """The primary settings form persists the OpenAI configuration names."""
    import ingestion
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "ENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(ingestion, "OPENAI_API_KEY", "")
    monkeypatch.setattr(ingestion, "OPENAI_MODEL", "gpt-5.4-mini")

    response = await client.post(
        "/settings",
        data={"api_key": "sk-proj-settings-test", "openai_model": "gpt-5.4"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert "API key saved." in response.json()["message"]
    assert "Model set to gpt-5.4." in response.json()["message"]
    saved = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY='sk-proj-settings-test'" in saved
    assert "OPENAI_MODEL='gpt-5.4'" in saved


async def test_regular_user_ai_connection_check_403(client, fresh_all_db):
    """Only admins can verify the live AI connection."""
    await _register(client, "user@example.com")
    response = await client.post("/settings/ai-connection/check")
    assert response.status_code == 403, response.text


async def test_admin_ai_connection_check_reports_demo_mode(
    client,
    fresh_all_db,
    monkeypatch,
):
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setenv("ACCOUNTIQ_DEMO_MODE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = await client.post("/settings/ai-connection/check")

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["status"] == "demo_mode"
    assert "continue testing" in response.json()["message"]
    assert response.json()["demo_mode"] is True
    assert response.json()["api_key_set"] is False


async def test_admin_ai_connection_check_reports_evidence_mode_when_live_key_is_missing(
    client,
    fresh_all_db,
    monkeypatch,
):
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = await client.post("/settings/ai-connection/check")

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["status"] == "evidence_mode"
    assert "evidence-mode reports" in response.json()["message"]
    assert response.json()["demo_mode"] is False
    assert response.json()["api_key_set"] is False


async def test_admin_ai_connection_check_runs_live_preflight(
    client,
    fresh_all_db,
    monkeypatch,
):
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-admin-connection-pass")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-mini")
    main_module._live_research_preflight_cache.clear()

    calls: list[tuple[str, str]] = []

    def pass_preflight(api_key, model):
        calls.append((api_key, model))

    monkeypatch.setattr(
        main_module,
        "_openai_live_research_preflight_sync",
        pass_preflight,
    )

    response = await client.post("/settings/ai-connection/check")

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["status"] == "verified"
    assert response.json()["cached"] is False
    assert response.json()["model"] == "gpt-5.4-mini"
    assert calls == [("sk-admin-connection-pass", "gpt-5.4-mini")]


async def test_admin_ai_connection_check_reports_failure_without_provider_leak(
    client,
    fresh_all_db,
    monkeypatch,
):
    import main as main_module

    await _register_admin(client, "admin@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-admin-connection-fail")
    main_module._live_research_preflight_cache.clear()

    def fail_preflight(_api_key, _model):
        raise RuntimeError(
            "OpenAI invalid_request_error with sk-secret"
        )

    monkeypatch.setattr(
        main_module,
        "_openai_live_research_preflight_sync",
        fail_preflight,
    )

    response = await client.post("/settings/ai-connection/check")

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is False
    assert response.json()["status"] == "failed"
    message = response.json()["message"]
    assert "could not be verified" in message
    lowered = message.lower()
    for forbidden in ("invalid_request_error", "sk-secret"):
        assert forbidden not in lowered


async def test_unauthenticated_returns_401_not_403(client, fresh_all_db):
    """AUTH-09: no-cookie request to admin-gated route returns 401, not 403."""
    client.cookies.clear()
    r = await client.get("/companies")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# UX-01: wizard upload (Plan 03 will make these green)
# ---------------------------------------------------------------------------

async def test_wizard_upload_creates_company_and_document(client, fresh_all_db):
    """UX-01: POST /wizard/upload returns 201 with company_id, document_id, status."""
    await _register(client, "user@example.com")
    import io
    fd = {
        "business_name": (None, "My Test Business"),
        "file": ("financials.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
    }
    r = await client.post("/wizard/upload", files=fd)
    assert r.status_code == 201, r.text
    body = r.json()
    assert "company_id" in body
    assert "document_id" in body
    assert body["status"] == "processing"
    assert isinstance(body["demo_mode"], bool)


async def test_wizard_upload_requires_auth(client, fresh_all_db):
    """UX-01: /wizard/upload without session returns 401."""
    client.cookies.clear()
    import io
    fd = {
        "business_name": (None, "My Test Business"),
        "file": ("financials.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
    }
    r = await client.post("/wizard/upload", files=fd)
    assert r.status_code == 401, r.text


async def test_wizard_upload_not_admin_gated(client, fresh_all_db):
    """UX-01: non-admin user can POST /wizard/upload (201, not 403)."""
    await _register(client, "user@example.com")
    import io
    fd = {
        "business_name": (None, "My Test Business"),
        "file": ("financials.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
    }
    r = await client.post("/wizard/upload", files=fd)
    assert r.status_code == 201, r.text
