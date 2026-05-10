"""
Tests for auto-company-resolution on document upload.

Covers:
  - Excel upload without company_id requires company_name (400)
  - Excel upload with company_name creates company and links document
  - Excel upload with company_name matching an existing company reuses it (case-insensitive)
  - Upload with explicit company_id uses that company (existing path)
  - PDF upload with no company_id falls back to extracted name (mocked) or filename stem
"""
import io
import pytest
import pytest_asyncio


async def _register(client, email, password="correcthorse"):
    r = await client.post("/auth/register", data={"email": email, "password": password})
    assert r.status_code in (200, 201), f"Register failed: {r.text}"


async def _create_company(client, name):
    r = await client.post("/companies", data={"name": name, "exchange": "Private"})
    assert r.status_code == 200, f"Create company failed: {r.text}"
    return r.json()["id"]


def _excel_file(name="financials.xlsx"):
    """Minimal xlsx-like bytes — enough to pass filename check; ingestion runs async so we don't care about content."""
    return (name, io.BytesIO(b"PK\x03\x04fake-xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _pdf_file(name="report.pdf"):
    return (name, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


# ---------------------------------------------------------------------------
# Excel upload: company_name required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_excel_upload_requires_company_name(client, fresh_all_db):
    """Excel upload without company_id or company_name returns 400."""
    await _register(client, "upload-excel-noname@test.com")
    fname, fbytes, ftype = _excel_file()
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={"entity_type": "sme", "report_type": "compilation"},
    )
    assert r.status_code == 400, r.text
    assert "company name" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_excel_upload_creates_company(client, fresh_all_db):
    """Excel upload with company_name auto-creates the company and links the document."""
    await _register(client, "upload-excel-create@test.com")
    fname, fbytes, ftype = _excel_file()
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={"entity_type": "sme", "report_type": "compilation", "company_name": "Acme Ltd"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_name"] == "Acme Ltd"
    assert isinstance(body["company_id"], int)
    assert body["document_id"] is not None

    # Company should now appear in the company list
    companies = (await client.get("/companies")).json()
    names = [c["name"] for c in companies]
    assert "Acme Ltd" in names


@pytest.mark.asyncio
async def test_excel_upload_reuses_existing_company_case_insensitive(client, fresh_all_db):
    """Excel upload with a name matching an existing company (case-insensitive) reuses it."""
    await _register(client, "upload-excel-reuse@test.com")
    cid = await _create_company(client, "Beta Corp")

    fname, fbytes, ftype = _excel_file()
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={"entity_type": "sme", "report_type": "compilation", "company_name": "beta corp"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == cid, "Should reuse existing company, not create a new one"


# ---------------------------------------------------------------------------
# Explicit company_id path (existing behaviour preserved)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_with_explicit_company_id(client, fresh_all_db):
    """Upload with explicit company_id links document to that company (pre-existing path)."""
    await _register(client, "upload-explicit@test.com")
    cid = await _create_company(client, "Explicit Co")

    fname, fbytes, ftype = _excel_file("q4.xlsx")
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={"entity_type": "listed", "company_id": cid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_id"] == cid


@pytest.mark.asyncio
async def test_upload_with_wrong_company_id_returns_404(client, fresh_all_db):
    """Upload with a company_id that belongs to another user returns 404."""
    await _register(client, "owner-upload@test.com")
    cid = await _create_company(client, "Owner Co")

    # Re-register as a different user (new cookie jar via fresh login)
    import main as _m
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=_m.app), base_url="http://test") as other:
        await other.post("/auth/register", data={"email": "intruder-upload@test.com", "password": "correcthorse"})
        fname, fbytes, ftype = _excel_file()
        r = await other.post(
            "/documents/upload",
            files={"file": (fname, fbytes, ftype)},
            data={"entity_type": "sme", "company_id": cid},
        )
        assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# PDF auto-extraction with mocked extractor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_upload_uses_extracted_name(client, fresh_all_db, monkeypatch):
    """PDF upload without company_id uses the mocked extracted name to resolve/create company."""
    import main as _m
    monkeypatch.setattr(_m, "_extract_company_name_from_pdf_sync", lambda path: "Gamma Solutions")

    await _register(client, "upload-pdf-extract@test.com")
    fname, fbytes, ftype = _pdf_file("annual_report.pdf")
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={"entity_type": "listed", "report_type": "annual_report"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_name"] == "Gamma Solutions"

    companies = (await client.get("/companies")).json()
    assert any(c["name"] == "Gamma Solutions" for c in companies)


@pytest.mark.asyncio
async def test_pdf_upload_falls_back_to_filename_stem(client, fresh_all_db, monkeypatch):
    """PDF upload where extraction returns empty string falls back to the filename stem."""
    import main as _m
    monkeypatch.setattr(_m, "_extract_company_name_from_pdf_sync", lambda path: "")

    await _register(client, "upload-pdf-fallback@test.com")
    fname, fbytes, ftype = _pdf_file("delta_industries_2024.pdf")
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={"entity_type": "sme"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_name"] == "delta_industries_2024"
