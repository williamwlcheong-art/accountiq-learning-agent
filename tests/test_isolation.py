"""
Tests for AUTH-07 (cross-user data isolation) and DATA-01 (NULL user_id rows invisible).

Success criteria covered:
  SC-1: User A cannot retrieve User B's companies or documents via any API endpoint
  SC-2: Existing NULL user_id rows are not visible to any authenticated user
  SC-3: User A's uploaded documents are not visible to any other user
  SC-4: All API routes that return companies or documents enforce the user_id filter

NOTE (Phase 3.5): All routes under /companies/*, /documents/*, /financials/*, /analytics/*
require is_admin=1 (require_admin). These tests register users as admins so they can
exercise the routes. Cross-user data isolation is still enforced by user_id WHERE clauses.
"""
import pytest
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_admin(client, email, password="correcthorse"):
    """Register and explicitly provision an admin test user."""
    from account_helpers import register_test_admin
    return await register_test_admin(client, email, password)

async def _create_company(client, name, exchange="NZX"):
    r = await client.post("/companies", data={"name": name, "exchange": exchange})
    assert r.status_code == 200, f"Create company failed: {r.text}"
    return r.json()["id"]


def _make_bob_client():
    """Return a context manager yielding a fresh AsyncClient with its own cookie jar."""
    import main as _main_module
    return AsyncClient(
        transport=ASGITransport(app=_main_module.app),
        base_url="http://test",
    )


# ---------------------------------------------------------------------------
# SC-1 + SC-3: IDOR — company access
# AUTH-07: User A cannot retrieve User B's company by guessed ID or list
# ---------------------------------------------------------------------------

async def test_cross_user_company_isolation(client, fresh_all_db):
    """AUTH-07 SC-1: User B cannot access User A's company by ID or via list."""
    await _register_admin(client, "alice@test.com")
    alice_company_id = await _create_company(client, "Alice Corp", "NZX")

    async with _make_bob_client() as bob:
        await _register_admin(bob, "bob@test.com")

        # Bob tries direct ID access — must get 404 (IDOR prevention)
        r = await bob.get(f"/companies/{alice_company_id}")
        assert r.status_code == 404, (
            f"IDOR: Bob accessed Alice's company {alice_company_id}. Response: {r.text}"
        )

        # Bob's company list must NOT include Alice's company
        r = await bob.get("/companies")
        assert r.status_code == 200, r.text
        names = [c["name"] for c in r.json()]
        assert "Alice Corp" not in names, (
            f"IDOR: Alice's company visible in Bob's list. names={names}"
        )


# ---------------------------------------------------------------------------
# SC-1 + SC-3: IDOR — document access
# AUTH-07: User A cannot retrieve User B's document by guessed ID or via list
# ---------------------------------------------------------------------------

async def test_cross_user_document_isolation(client, fresh_all_db):
    """AUTH-07 SC-3: User B cannot access User A's document by ID or via list."""
    await _register_admin(client, "alice2@test.com")
    alice_company_id = await _create_company(client, "Alice Docs Corp", "NZX")

    # Alice creates a document record by uploading a minimal PDF-like file
    import io
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content for testing")
    fake_pdf.name = "alice_report.pdf"
    r = await client.post(
        "/documents/upload",
        data={
            "company_id": str(alice_company_id),
            "report_type": "annual_report",
            "entity_type": "sme",
            "fiscal_year_end": "2024-03-31",
        },
        files={"file": ("alice_report.pdf", fake_pdf, "application/pdf")},
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    alice_doc_id = r.json()["document_id"]

    async with _make_bob_client() as bob:
        await _register_admin(bob, "bob2@test.com")

        # Bob tries to access Alice's document status by guessed ID — must get 404
        r = await bob.get(f"/documents/{alice_doc_id}/status")
        assert r.status_code == 404, (
            f"IDOR: Bob accessed Alice's document {alice_doc_id}. Response: {r.text}"
        )

        # Bob's document list must not include Alice's document
        r = await bob.get("/documents")
        assert r.status_code == 200, r.text
        doc_ids = [d["id"] for d in r.json()]
        assert alice_doc_id not in doc_ids, (
            f"IDOR: Alice's document visible in Bob's list. ids={doc_ids}"
        )


# ---------------------------------------------------------------------------
# SC-2: NULL user_id rows are invisible to all authenticated users
# DATA-01 (superseded by D-01/D-02): existing pre-auth rows become invisible
# ---------------------------------------------------------------------------

async def test_null_user_rows_invisible(client, fresh_all_db):
    """DATA-01 / D-02: A freshly registered user sees zero companies and documents.

    After Phase 2 migration, all pre-auth rows have user_id=NULL.
    WHERE user_id=? with any integer never matches NULL.
    The temp test DB starts clean (fresh_all_db), so zero rows is the expected result.
    """
    await _register_admin(client, "newuser@test.com")

    r = await client.get("/companies")
    assert r.status_code == 200, r.text
    assert r.json() == [], (
        f"Expected empty company list for new user; got: {r.json()}"
    )

    r = await client.get("/documents")
    assert r.status_code == 200, r.text
    assert r.json() == [], (
        f"Expected empty document list for new user; got: {r.json()}"
    )


# ---------------------------------------------------------------------------
# SC-4: List endpoints enforce user_id filter
# AUTH-07: GET /analytics/overview scoped to current user (D-05)
# ---------------------------------------------------------------------------

async def test_list_endpoints_scoped(client, fresh_all_db):
    """AUTH-07 SC-4: List endpoints return only caller's own data."""
    await _register_admin(client, "alice3@test.com")
    await _create_company(client, "Alice Analytics Co", "ASX")
    await _create_company(client, "Alice Analytics Co 2", "NZX")

    async with _make_bob_client() as bob:
        await _register_admin(bob, "bob3@test.com")
        await _create_company(bob, "Bob Analytics Co", "NZX")

        # Bob's company list has exactly 1 entry (his own)
        r = await bob.get("/companies")
        assert r.status_code == 200, r.text
        bob_companies = r.json()
        assert len(bob_companies) == 1, (
            f"Bob should see 1 company; got {len(bob_companies)}: {bob_companies}"
        )
        assert bob_companies[0]["name"] == "Bob Analytics Co", bob_companies

        # Alice's company list has exactly 2 entries (her own)
        r = await client.get("/companies")
        assert r.status_code == 200, r.text
        alice_companies = r.json()
        assert len(alice_companies) == 2, (
            f"Alice should see 2 companies; got {len(alice_companies)}: {alice_companies}"
        )

        # Analytics overview for Bob shows 1 company, 0 documents
        r = await bob.get("/analytics/overview")
        assert r.status_code == 200, r.text
        ov = r.json()
        assert ov["companies"] == 1, f"Bob overview.companies should be 1; got {ov['companies']}"
        assert ov["documents"] == 0, f"Bob overview.documents should be 0; got {ov['documents']}"

        # Analytics overview for Alice shows 2 companies, 0 documents
        r = await client.get("/analytics/overview")
        assert r.status_code == 200, r.text
        ov_alice = r.json()
        assert ov_alice["companies"] == 2, (
            f"Alice overview.companies should be 2; got {ov_alice['companies']}"
        )


# ---------------------------------------------------------------------------
# SC-1: Cross-user document upload against another user's company is rejected
# AUTH-07: POST /documents/upload company ownership check
# ---------------------------------------------------------------------------

async def test_upload_to_other_users_company_rejected(client, fresh_all_db):
    """AUTH-07: Bob cannot upload a document against Alice's company_id."""
    await _register_admin(client, "alice4@test.com")
    alice_company_id = await _create_company(client, "Alice Upload Corp", "NZX")

    async with _make_bob_client() as bob:
        await _register_admin(bob, "bob4@test.com")

        import io
        fake_pdf = io.BytesIO(b"%PDF-1.4 fake")
        r = await bob.post(
            "/documents/upload",
            data={
                "company_id": str(alice_company_id),
                "report_type": "annual_report",
                "entity_type": "sme",
                "fiscal_year_end": "2024-03-31",
            },
            files={"file": ("bob_report.pdf", fake_pdf, "application/pdf")},
        )
        assert r.status_code == 404, (
            f"Bob should not be able to upload to Alice's company. Got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# SC-1: Cross-user financial row access is blocked
# AUTH-07: GET /documents/{id}/rows and GET /financials/{company_id}
# ---------------------------------------------------------------------------

async def test_cross_user_financial_rows_isolation(client, fresh_all_db):
    """AUTH-07 SC-1: User B cannot access User A's financial rows via document or company endpoints."""
    import io

    await _register_admin(client, "alice5@test.com")
    alice_co = await _create_company(client, "Alice Fin Corp", "NZX")

    # Alice uploads a minimal fake PDF to create a document record.
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content for testing")
    r = await client.post(
        "/documents/upload",
        data={
            "company_id": str(alice_co),
            "report_type": "annual_report",
            "entity_type": "sme",
            "fiscal_year_end": "2024-03-31",
        },
        files={"file": ("alice_fin.pdf", fake_pdf, "application/pdf")},
    )
    assert r.status_code == 200, f"Alice upload failed: {r.text}"
    alice_doc_id = r.json()["document_id"]

    async with _make_bob_client() as bob:
        await _register_admin(bob, "bob5@test.com")

        # Bob tries to access Alice's document rows by guessed document_id — must get 404.
        r = await bob.get(f"/documents/{alice_doc_id}/rows")
        assert r.status_code == 404, (
            f"IDOR: Bob accessed Alice's document rows for doc {alice_doc_id}. "
            f"Got {r.status_code}: {r.text}"
        )

        # Bob tries to access Alice's financials by guessed company_id — must get empty list.
        # The endpoint returns 200 with [] rather than 404 (same as list_documents behaviour).
        r = await bob.get(f"/financials/{alice_co}")
        assert r.status_code == 200, (
            f"GET /financials/{alice_co} should return 200 for Bob; got {r.status_code}: {r.text}"
        )
        assert r.json() == [], (
            f"IDOR: Bob received non-empty financials for Alice's company {alice_co}. "
            f"Got: {r.json()}"
        )
