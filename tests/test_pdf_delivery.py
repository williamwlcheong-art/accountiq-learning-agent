import json

import aiosqlite
import pytest

from db import DB_PATH
import main as main_module
from report_rendering import render_report_html


async def _register(client, email: str, password: str = "password123"):
    response = await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    me = await client.get("/auth/me")
    assert me.status_code == 200, me.text
    return me.json()


async def _insert_report(user_id: int, *, status: str = "done") -> int:
    content = {
        "valuation_summary": {
            "narrative": "Indicative valuation summary for review.",
            "table": {
                "headers": ["Metric", "Value"],
                "rows": [["Enterprise value", "$1,250,000"]],
            },
        },
        "disclaimer": (
            "This report is indicative only and is not financial advice. "
            "Seek independent professional advice before relying on it."
        ),
    }
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
            ("PDF Delivery Ltd", user_id),
        ) as cursor:
            company_id = cursor.lastrowid
        async with db.execute(
            """
            INSERT INTO reports (
                company_id,
                user_id,
                report_type,
                status,
                content,
                completed_at
            )
            VALUES (?, ?, 'valuation_advisory', ?, ?, datetime('now'))
            """,
            (company_id, user_id, status, json.dumps(content)),
        ) as cursor:
            report_id = cursor.lastrowid
        await db.commit()
    return report_id


@pytest.mark.asyncio
async def test_owner_can_download_completed_report_pdf(
    client,
    fresh_all_db,
    monkeypatch,
    tmp_path,
):
    user = await _register(client, "pdf-owner@example.com")
    report_id = await _insert_report(user["id"])
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)
    writes = 0

    def fake_write_pdf(html_text, output_path):
        nonlocal writes
        writes += 1
        assert "PDF Delivery Ltd" in html_text
        assert "#1B1464" in html_text
        assert "Indicative Only - Not Financial Advice" in html_text
        assert "Enterprise value" in html_text
        assert "&lt;script" not in html_text
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-1.7\naccountiq-test")

    monkeypatch.setattr(main_module, "write_pdf", fake_write_pdf, raising=False)

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert f"report-{report_id}.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-1.7")

    cached_response = await client.get(f"/wizard/report/{report_id}/pdf")
    assert cached_response.status_code == 200
    assert writes == 1


@pytest.mark.asyncio
async def test_user_cannot_download_another_users_pdf(client, fresh_all_db, monkeypatch, tmp_path):
    owner = await _register(client, "pdf-first-owner@example.com")
    report_id = await _insert_report(owner["id"])
    await _register(client, "pdf-other-user@example.com")
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_report_must_be_approved_before_pdf_download(client, fresh_all_db, monkeypatch, tmp_path):
    owner = await _register(client, "pdf-review-owner@example.com")
    report_id = await _insert_report(owner["id"], status="awaiting_review")
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 400
    assert "awaiting_review" in response.text


def test_report_html_is_branded_and_escapes_generated_content():
    rendered = render_report_html(
        "Example & Sons",
        "valuation_advisory",
        {
            "valuation_summary": {
                "narrative": "## Overview\n- <script>alert('xss')</script>\n- **Strong evidence**",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Enterprise value", "$1,250,000"]],
                },
            },
            "disclaimer": "Indicative only.",
        },
        "2026-07-12",
    )

    assert "#1B1464" in rendered
    assert "Indicative Only - Not Financial Advice" in rendered
    assert "Example &amp; Sons" in rendered
    assert "&lt;script&gt;alert" in rendered
    assert "<script>alert" not in rendered
    assert "<h3>Overview</h3>" in rendered
    assert "<ul>" in rendered
    assert "<strong>Strong evidence</strong>" in rendered
    assert "Enterprise value" in rendered
    assert "counter(page)" in rendered
