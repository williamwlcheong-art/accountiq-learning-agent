"""Tests for AUTH-04 (register), AUTH-05 (login/session), AUTH-06 (logout), AUTH-08 (account)."""
import pytest


# Helper — used across tests
async def _register(client, email="alice@example.com", password="correcthorse"):
    return await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )


async def _login(client, email="alice@example.com", password="correcthorse"):
    return await client.post(
        "/auth/login",
        data={"email": email, "password": password},
    )


# ------------------------------------------------------------------
# AUTH-04: Register
# ------------------------------------------------------------------

async def test_register_success(client, fresh_db):
    r = await _register(client)
    assert r.status_code in (200, 201), r.text
    cookies = r.headers.get("set-cookie", "")
    assert "accountiq_session=" in cookies, f"missing session cookie: {cookies!r}"


async def test_register_short_password(client, fresh_db):
    r = await _register(client, password="short7c")  # 7 chars
    assert r.status_code in (400, 422), r.text


async def test_register_duplicate(client, fresh_db):
    r1 = await _register(client, email="dup@example.com")
    assert r1.status_code in (200, 201)
    r2 = await _register(client, email="dup@example.com")
    assert r2.status_code == 409, r2.text


# ------------------------------------------------------------------
# AUTH-05: Login + session
# ------------------------------------------------------------------

async def test_login_sets_cookie(client, fresh_db):
    await _register(client, email="login@example.com")
    # Drop cookies from registration to test login independently
    client.cookies.clear()
    r = await _login(client, email="login@example.com")
    assert r.status_code == 200, r.text
    cookies = r.headers.get("set-cookie", "")
    assert "accountiq_session=" in cookies


async def test_cookie_attributes(client, fresh_db):
    """Cookie must be HttpOnly and have ~7-day max-age."""
    await _register(client, email="attr@example.com")
    client.cookies.clear()
    r = await _login(client, email="attr@example.com")
    cookie_header = r.headers.get("set-cookie", "").lower()
    assert "httponly" in cookie_header, f"cookie not httponly: {cookie_header!r}"
    # 7 days = 604800 seconds; allow exact match
    assert "max-age=604800" in cookie_header, (
        f"max-age not 7 days: {cookie_header!r}"
    )
    assert "samesite=lax" in cookie_header, f"samesite!=lax: {cookie_header!r}"


async def test_me_authenticated(client, fresh_db):
    await _register(client, email="me@example.com")
    # cookie should now be persisted on the AsyncClient instance
    r = await client.get("/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "me@example.com"


async def test_me_unauthenticated(client, fresh_db):
    client.cookies.clear()
    r = await client.get("/auth/me")
    assert r.status_code == 401


# ------------------------------------------------------------------
# AUTH-06: Logout
# ------------------------------------------------------------------

async def test_logout(client, fresh_db):
    await _register(client, email="out@example.com")
    r = await client.post("/auth/logout")
    assert r.status_code == 200, r.text
    # Cookie should be cleared (Set-Cookie with Max-Age=0 or expired)
    cookie_header = r.headers.get("set-cookie", "").lower()
    assert "accountiq_session=" in cookie_header
    assert ("max-age=0" in cookie_header) or ("expires=" in cookie_header)


async def test_protected_after_logout(client, fresh_db):
    await _register(client, email="plo@example.com")
    await client.post("/auth/logout")
    client.cookies.clear()
    r = await client.get("/auth/me")
    assert r.status_code == 401


# ------------------------------------------------------------------
# AUTH-08: Account details
# ------------------------------------------------------------------

async def test_me_returns_user_fields(client, fresh_db):
    await _register(client, email="fields@example.com")
    r = await client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert body["email"] == "fields@example.com"
    assert "created_at" in body


# ------------------------------------------------------------------
# Cross-cutting: protected route enforcement
# ------------------------------------------------------------------

async def test_protected_route_no_auth(client, fresh_db):
    """Unauthenticated GET /companies must return 401."""
    client.cookies.clear()
    r = await client.get("/companies")
    assert r.status_code == 401, r.text


async def test_protected_route_with_auth(client, fresh_db):
    await _register(client, email="prot@example.com")
    r = await client.get("/companies")
    assert r.status_code == 200, r.text


async def test_health_remains_public(client, fresh_db):
    """AUTH-* — /health must NOT be gated."""
    client.cookies.clear()
    r = await client.get("/health")
    assert r.status_code == 200
