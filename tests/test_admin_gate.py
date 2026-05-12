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
