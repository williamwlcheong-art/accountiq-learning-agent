"""
Tests for Phase 3: Business Profile Intake (PROF-01 through PROF-04, D-05, D-06).

All tests are RED stubs created in Plan 03-01 (Wave 0).
Plan 03-02 implements the backend routes that turn these GREEN.

Routes exercised:
  POST /companies/{id}/profile               (sector + description patch)
  GET/POST/PUT/DELETE /companies/{id}/management-team[/{member_id}]
  GET/POST/PUT/DELETE /companies/{id}/ebitda-adjustments[/{adj_id}]
  GET /companies/{id}/profile-status
"""
import pytest
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers — copied from tests/test_isolation.py for consistency
# ---------------------------------------------------------------------------

async def _register(client, email, password="correcthorse"):
    r = await client.post("/auth/register", data={"email": email, "password": password})
    assert r.status_code in (200, 201), f"Register failed for {email!r}: {r.text}"
    return r


async def _create_company(client, name, exchange="Private"):
    r = await client.post("/companies", data={"name": name, "exchange": exchange})
    assert r.status_code == 200, f"Create company failed: {r.text}"
    return r.json()["id"]


def _make_other_client():
    """Fresh AsyncClient with its own cookie jar."""
    import main as _main_module
    return AsyncClient(
        transport=ASGITransport(app=_main_module.app),
        base_url="http://test",
    )


# ---------------------------------------------------------------------------
# PROF-01: Industry / sector save
# ---------------------------------------------------------------------------

async def test_save_industry(client, fresh_all_db):
    """PROF-01: sector saved to company via POST /companies/{id}/profile."""
    await _register(client, "alice-prof01@test.com")
    cid = await _create_company(client, "ProfileTest Co")
    r = await client.post(f"/companies/{cid}/profile", data={"sector": "Technology & Software"})
    assert r.status_code == 200, f"profile save failed: {r.text}"
    body = r.json()
    assert body["sector"] == "Technology & Software", body


async def test_profile_ownership_403(client, fresh_all_db):
    """PROF-01: unowned company returns 404 (not 403) on profile save."""
    await _register(client, "owner-prof@test.com")
    cid = await _create_company(client, "Owner Profile Co")
    async with _make_other_client() as other:
        await _register(other, "other-prof@test.com")
        r = await other.post(f"/companies/{cid}/profile", data={"sector": "Retail"})
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# PROF-02: Description save
# ---------------------------------------------------------------------------

async def test_save_description(client, fresh_all_db):
    """PROF-02: description saved via POST /companies/{id}/profile (>=50 chars)."""
    await _register(client, "alice-prof02@test.com")
    cid = await _create_company(client, "DescTest Co")
    desc = "A small accountancy firm serving SMEs across NZ since 2018."  # > 50 chars
    assert len(desc) >= 50
    r = await client.post(f"/companies/{cid}/profile", data={"description": desc})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == desc, body


# ---------------------------------------------------------------------------
# PROF-03: Management team CRUD
# ---------------------------------------------------------------------------

async def test_management_team_crud(client, fresh_all_db):
    """PROF-03: add a management team member; list returns it."""
    await _register(client, "alice-prof03@test.com")
    cid = await _create_company(client, "MgmtTest Co")
    # Add member
    r = await client.post(
        f"/companies/{cid}/management-team",
        data={"name": "Jane Smith", "title": "CEO", "bio": "Founder, 12y experience"},
    )
    assert r.status_code == 201, f"add member failed: {r.text}"
    member = r.json()
    assert member["name"] == "Jane Smith"
    assert member["title"] == "CEO"
    assert "id" in member
    # List members
    r = await client.get(f"/companies/{cid}/management-team")
    assert r.status_code == 200, r.text
    members = r.json()
    assert len(members) == 1
    assert members[0]["name"] == "Jane Smith"


async def test_management_team_delete(client, fresh_all_db):
    """PROF-03: DELETE returns 204; member disappears from list."""
    await _register(client, "alice-prof03del@test.com")
    cid = await _create_company(client, "MgmtDel Co")
    r = await client.post(
        f"/companies/{cid}/management-team",
        data={"name": "Bob Jones", "title": "COO"},
    )
    assert r.status_code == 201, r.text
    member_id = r.json()["id"]
    # DELETE — must return 204 No Content (no body)
    r = await client.delete(f"/companies/{cid}/management-team/{member_id}")
    assert r.status_code == 204, f"delete returned {r.status_code}: {r.text}"
    # List must be empty
    r = await client.get(f"/companies/{cid}/management-team")
    assert r.status_code == 200, r.text
    assert r.json() == []


# ---------------------------------------------------------------------------
# PROF-04: EBITDA adjustments CRUD
# ---------------------------------------------------------------------------

async def test_ebitda_adjustments_crud(client, fresh_all_db):
    """PROF-04: add EBITDA adjustment; list returns it. Amount can be negative."""
    await _register(client, "alice-prof04@test.com")
    cid = await _create_company(client, "AdjTest Co")
    # Positive add-back
    r = await client.post(
        f"/companies/{cid}/ebitda-adjustments",
        data={"label": "Owner salary above market", "amount": "80000", "rationale": "Owner takes 80k above market"},
    )
    assert r.status_code == 201, f"add adjustment failed: {r.text}"
    body = r.json()
    assert body["label"] == "Owner salary above market"
    assert body["amount"] == 80000.0
    # Negative adjustment (subtraction — e.g. one-time windfall)
    r = await client.post(
        f"/companies/{cid}/ebitda-adjustments",
        data={"label": "One-time windfall", "amount": "-15000", "rationale": "Removed"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["amount"] == -15000.0
    # List
    r = await client.get(f"/companies/{cid}/ebitda-adjustments")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2
    assert {row["label"] for row in rows} == {"Owner salary above market", "One-time windfall"}


# ---------------------------------------------------------------------------
# PROF-04 / D-06: profile-status gate logic
# ---------------------------------------------------------------------------

async def test_profile_status_gate(client, fresh_all_db):
    """PROF-04 / D-06: profile-status ebitda_complete=true after first adjustment."""
    await _register(client, "alice-status@test.com")
    cid = await _create_company(client, "StatusTest Co")
    # Initially no adjustments
    r = await client.get(f"/companies/{cid}/profile-status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ebitda_complete"] is False, body
    # Add one adjustment
    r = await client.post(
        f"/companies/{cid}/ebitda-adjustments",
        data={"label": "Owner salary", "amount": "50000"},
    )
    assert r.status_code == 201
    # Now ebitda_complete should be true
    r = await client.get(f"/companies/{cid}/profile-status")
    body = r.json()
    assert body["ebitda_complete"] is True, body


async def test_profile_status_blocked(client, fresh_all_db):
    """PROF-04 / D-06: can_generate=false when sector null OR no adjustments."""
    await _register(client, "alice-blocked@test.com")
    cid = await _create_company(client, "BlockTest Co")
    # No sector, no adjustments — should be blocked
    r = await client.get(f"/companies/{cid}/profile-status")
    body = r.json()
    assert body["can_generate"] is False, f"expected blocked, got {body}"
    # Add sector only — still blocked (no adjustments)
    await client.post(f"/companies/{cid}/profile", data={"sector": "Retail"})
    r = await client.get(f"/companies/{cid}/profile-status")
    body = r.json()
    assert body["sector_complete"] is True, body
    assert body["can_generate"] is False, "still need adjustments"
    # Add an adjustment — now unblocked
    await client.post(
        f"/companies/{cid}/ebitda-adjustments",
        data={"label": "Owner salary", "amount": "50000"},
    )
    r = await client.get(f"/companies/{cid}/profile-status")
    body = r.json()
    assert body["can_generate"] is True, body


# ---------------------------------------------------------------------------
# PROF-04 / D-05: EBITDA bridge calculation
# ---------------------------------------------------------------------------

async def test_ebitda_bridge_calculation(client, fresh_all_db):
    """PROF-04 / D-05: reported_ebitda = net_profit + depreciation_amortisation
       from financial_rows max period. has_financials=False when no rows exist."""
    await _register(client, "alice-bridge@test.com")
    cid = await _create_company(client, "BridgeTest Co")
    # No financial_rows yet — has_financials should be false
    r = await client.get(f"/companies/{cid}/profile-status")
    body = r.json()
    assert body["has_financials"] is False, body
    assert body["reported_ebitda"] is None, body
    # Insert financial_rows directly via DB to simulate prior extraction
    # Use the patched DB_PATH from the db module (set by conftest before test startup)
    import aiosqlite
    import db as _db_module
    db_path = _db_module.DB_PATH
    async with aiosqlite.connect(db_path) as conn:
        # Need a document_id — insert a dummy document
        cur = await conn.execute(
            "INSERT INTO documents (company_id, filename, filepath, user_id) VALUES (?, ?, ?, ?)",
            (cid, "dummy.pdf", f"/tmp/dummy-{cid}.pdf", 1),
        )
        doc_id = cur.lastrowid
        # net_profit = 200_000, depreciation_amortisation = 50_000 — bridge = 250_000
        await conn.execute(
            "INSERT INTO financial_rows (document_id, company_id, statement, row_key, row_label, period, value) VALUES (?, ?, 'pnl', 'net_profit', 'Net Profit', '2024', 200000)",
            (doc_id, cid),
        )
        await conn.execute(
            "INSERT INTO financial_rows (document_id, company_id, statement, row_key, row_label, period, value) VALUES (?, ?, 'pnl', 'depreciation_amortisation', 'D&A', '2024', 50000)",
            (doc_id, cid),
        )
        await conn.commit()
    # Now profile-status should return reported_ebitda = 250_000
    r = await client.get(f"/companies/{cid}/profile-status")
    body = r.json()
    assert body["has_financials"] is True, body
    assert body["reported_ebitda"] == 250000, f"expected 250000, got {body.get('reported_ebitda')}"
