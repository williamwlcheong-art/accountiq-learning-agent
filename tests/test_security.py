"""Tests for AUTH-01 (CORS) and AUTH-02 (filename sanitisation)."""
import io
import pytest


# ------------------------------------------------------------------
# AUTH-01: CORS hardening
# ------------------------------------------------------------------

async def test_cors_restricted_unknown_origin(client):
    """A preflight from an unknown origin must NOT receive ACAO header echo."""
    r = await client.options(
        "/companies",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    # After fix: ACAO must be absent OR not equal to the evil origin
    acao = r.headers.get("access-control-allow-origin", "")
    assert acao != "https://evil.example", (
        f"Unknown origin was echoed in ACAO: {acao!r}"
    )
    assert acao != "*", "Wildcard ACAO must be removed"


async def test_cors_allowed_origin_localhost(client):
    """Preflight from http://localhost:8765 must succeed with credentials."""
    r = await client.options(
        "/companies",
        headers={
            "Origin": "http://localhost:8765",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8765"
    assert r.headers.get("access-control-allow-credentials") == "true"


# ------------------------------------------------------------------
# AUTH-02: Filename path traversal
# ------------------------------------------------------------------

async def test_filename_traversal_basename_only(client, tmp_path, monkeypatch):
    """Uploading with filename '../../evil.py' must save to basename 'evil.py' only."""
    # Need a company first — create one (this also exercises auth in later phases)
    cr = await client.post(
        "/companies",
        data={"name": "TraversalTest Co", "exchange": "NZX"},
    )
    # Accept 200/201 OR 401 (after auth lands). For Plan 01 RED, current code returns 200.
    # This test will be revisited once auth is wired (Plan 03).
    if cr.status_code in (401, 403):
        pytest.skip("Auth gate active — re-run after authenticated upload helper added")
    company_id = cr.json()["id"]

    evil_name = "../../evil.py"
    files = {"file": (evil_name, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r = await client.post(
        "/documents/upload",
        data={
            "company_id": str(company_id),
            "report_type": "annual_report",
            "entity_type": "listed",
            "fiscal_year_end": "",
        },
        files=files,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    # Filename returned to client should be basename only (no path components)
    assert "/" not in body["filename"], (
        f"filename leaked path: {body['filename']!r}"
    )
    assert ".." not in body["filename"], (
        f"filename leaked traversal: {body['filename']!r}"
    )
    assert body["filename"] == "evil.py"
