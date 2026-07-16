"""Tests for authenticated report PDF delivery."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import aiosqlite
import pdfplumber
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as main_module
from main import _e2e_report_content
from report_quality import ReportQualityAudit, ReportQualityIssue


async def _register_and_seed_report(
    client,
    email: str,
    status: str = "done",
    *,
    demo_mode: bool = False,
) -> int:
    response = await client.post(
        "/auth/register",
        data={"email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE email=?", (email,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO companies (name, exchange, user_id)
            VALUES (?, 'Private', ?)
            """,
            ("PDF Delivery Limited", user_id),
        ) as cur:
            company_id = cur.lastrowid
        async with db.execute(
            """
            INSERT INTO reports
                (company_id, user_id, report_type, status, content, completed_at, demo_mode)
            VALUES (?, ?, 'valuation_advisory', ?, ?, datetime('now'), ?)
            """,
            (
                company_id,
                user_id,
                status,
                json.dumps(_e2e_report_content("valuation_advisory", demo_mode=demo_mode)),
                int(demo_mode),
            ),
        ) as cur:
            report_id = cur.lastrowid
        await db.execute(
            """
            INSERT INTO report_intake (report_id, answers)
            VALUES (?, ?)
            """,
            (
                report_id,
                json.dumps(
                    {
                        "valuation_purpose": "sale_or_transaction",
                        "owner_dependency": "shared",
                        "customer_concentration": "10_to_25",
                        "revenue_quality": "mixed",
                        "revenue_outlook": "not_sure",
                    }
                ),
            ),
        )
        await db.commit()
    return report_id


@pytest.mark.asyncio
async def test_completed_report_downloads_as_pdf(client, fresh_all_db, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)
    report_id = await _register_and_seed_report(client, "pdf-owner@example.com")

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert (
        f"PDF-Delivery-Limited-AIQ-VAL-{report_id:06d}-indicative-valuation.pdf"
        in response.headers["content-disposition"]
    )
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 20_000
    assert (tmp_path / f"report-{report_id}.pdf").exists()
    with pdfplumber.open(tmp_path / f"report-{report_id}.pdf") as pdf:
        page_count = len(pdf.pages)
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    normalised_text = " ".join(text.split())
    assert page_count >= 23
    assert "Indicative Valuation Report | PDF Delivery Limited" in text
    assert "VALUATION SNAPSHOT" in text
    assert "Basis of preparation" in text
    assert text.count("Basis of preparation") >= 1
    assert "Valuation purpose" in text
    assert "Prepare for a sale or transaction" in text
    assert "Valuation date" in text
    assert "Indicative fair-market value" in text
    assert "Information basis" in text
    assert "uploaded financial statements" in text
    assert "earnings-adjustment review" in normalised_text
    assert "public-source research" in normalised_text
    assert "Scope exclusions" in text
    assert "audit, assurance engagement, legal advice, tax advice" in normalised_text
    assert "AccountIQ valuation calculations" in text
    assert "model-computed" not in text
    assert "Python-computed" not in text
    assert "Five management-confirmed private inputs" in text
    assert "Management input trail" in text
    assert "Management input - Valuation purpose" in text
    assert "Management input - Owner or key-person" in text
    assert "Responsibility is shared across leadership" in normalised_text
    assert "dependency and team. Informs continuity" in normalised_text
    assert "Management input - Largest-customer" in text
    assert "concentration diligence focus" in normalised_text
    assert "10% to 25%" in text
    assert "Management input - Revenue predictability" in text
    assert "A mix of recurring and one-off revenue" in text
    assert "Management input - Revenue outlook" in text
    assert "No specific forecast provided; growth derived from uploaded financial history" in normalised_text
    assert "Evidence and model basis" in text
    assert "Earnings-adjustment review" in text
    assert "Optional public-source hints" in text
    assert "not required from management" in text
    assert "AccountIQ calculates the DCF valuation" in text
    assert "discount" in text
    assert "scenarios" in text
    assert "Python computes the DCF" not in text
    assert "Derived technical assumptions" in text
    assert "01 Introduction" in text
    assert "02 Executive Summary" in text
    assert "Valuation conclusion at a glance" in text
    assert "Valuation range visual" in text
    assert "Mid $2,314,000" in text
    assert "Business context at a glance" in text
    assert "Revenue predictability" in text
    assert "Market context at a glance" in text
    assert "Benchmark evidence" in text
    assert "Methodology at a glance" in text
    assert "Valuation approach selection" in text
    assert "Income approach - DCF" in text
    assert "Adopted as primary" in text
    assert "Market approach -" in text
    assert "EV/EBITDA cross-check" in normalised_text
    assert "Asset approach / net assets" in text
    assert "Primary valuation method" in text
    assert "Enterprise value range" in text
    assert "$1,898,000 - $2,831,000" in text
    assert "Midpoint equity value" in text
    assert "How the discount rate drives the range" in text
    assert "WACC build visual" in text
    assert "Risk-free rate" in text
    assert "Beta-adjusted risk premium" in text
    assert "Mid WACC" in text
    assert "Technical inputs" in text
    assert "Derived" in text
    assert "DCF value build visual" in text
    assert "PV explicit FCFF" in text
    assert "$836,951" in text
    assert "PV terminal value" in text
    assert "$1,787,049" in text
    assert "DCF forecast bridge at a glance" in text
    assert "Valuation range at a glance" in text
    assert "DCF vs multiple midpoint" in text
    assert "Sensitivity spread visual" in text
    assert "Downside, base and upside adjusted enterprise value" in text
    assert "Sensitivity takeaway at a glance" in text
    assert "Specific risk factors" in text
    assert "How the market cross-check is used" in text
    assert "Implied multiple reconciliation" in text
    assert "DCF post-illiquidity range" in text
    assert "6.6x - 9.9x" in text
    assert "2.1x above market midpoint" in text
    assert "Enterprise-to-equity bridge" in text
    assert "Enterprise-to-equity visual" in text
    assert "Shows how operating-business value converts to shareholder value" in text
    assert "Source trail at a glance" in text
    assert "About Business Valuations" in text
    assert "Historical Ratio Analysis" in text
    assert "Comparable Evidence Appendix" in text
    assert "Comparable evidence at a glance" in text
    assert "Comparability caveat" in text
    assert "Reliance at a glance" in text
    assert "Third-party reliance" in text
    assert "General Principles" in text
    assert "Glossary" in text
    assert "Assumption basis at a glance" in text
    assert "Maintainable earnings base" in text
    assert "Public research inputs" in text
    assert "Assumption / input" in text
    assert "Management-confirmed private" in text
    assert "Owner or key-person dependency" in text
    assert "Trading performance at a glance" in text
    assert "Financial trend visual" in text
    assert "Revenue and EBITDA trend" in text
    assert "Margin and growth at a glance" in text
    assert "Normalised EBITDA bridge" in text
    assert "Uploaded EBITDA basis" in text
    assert "Net normalisation" in text
    assert "Normalisation impact at a glance" in text
    assert "Mid-case forecast cash-flow schedule" in text
    assert "Free cash flow to firm" in text
    assert "Specific risk factors" in text
    assert "Customer concentration" in text
    assert "Revenue outlook" in text
    assert "Supports / used for" in text
    assert "Risk-free-rate and discount-rate context" in text
    assert "(cid:" not in text
    assert "•" not in text
    assert "–" not in text
    assert "—" not in text


@pytest.mark.asyncio
async def test_report_pdf_refuses_delivery_when_professional_audit_fails(
    client,
    fresh_all_db,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)
    report_id = await _register_and_seed_report(client, "pdf-audit-fail@example.com")

    def fake_pdf_audit(path, *, demo_mode):
        assert path == tmp_path / f"report-{report_id}.pdf"
        assert demo_mode is False
        return ReportQualityAudit(
            artifact="valuation_report_pdf",
            issues=(
                ReportQualityIssue(
                    "missing_pdf_marker",
                    "PDF text is missing marker: Valuation range visual",
                ),
            ),
            metadata={"page_count": 22},
        )

    monkeypatch.setattr(main_module, "audit_valuation_report_pdf", fake_pdf_audit)

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 500
    assert "failed professional artifact quality checks" in response.json()["detail"]
    assert "missing_pdf_marker" in response.json()["detail"]
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_report_pdf_requires_completed_report(client, fresh_all_db, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)
    report_id = await _register_and_seed_report(
        client,
        "pdf-pending@example.com",
        status="generating",
    )

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_demo_pdf_is_unmistakably_labelled(client, fresh_all_db, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "EXPORT_DIR", tmp_path)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    report_id = await _register_and_seed_report(
        client,
        "pdf-demo@example.com",
        demo_mode=True,
    )

    response = await client.get(f"/wizard/report/{report_id}/pdf")

    assert response.status_code == 200, response.text
    assert (
        f"PDF-Delivery-Limited-AIQ-VAL-{report_id:06d}-demo-indicative-valuation.pdf"
        in response.headers["content-disposition"]
    )
    with pdfplumber.open(tmp_path / f"report-{report_id}.pdf") as pdf:
        page_count = len(pdf.pages)
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Demo Indicative Valuation Report" in text
    assert text.count("DEMO DATA - NOT FOR RELIANCE") >= page_count


@pytest.mark.asyncio
async def test_demo_html_viewer_is_unmistakably_labelled(client, fresh_all_db, monkeypatch):
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    report_id = await _register_and_seed_report(
        client,
        "html-demo@example.com",
        demo_mode=True,
    )

    response = await client.get(f"/wizard/report/{report_id}/view")

    assert response.status_code == 200, response.text
    assert 'href="./pdf"' in response.text
    assert 'href="#basis-of-preparation"' in response.text
    assert "a { color:var(--blue); text-decoration:none; overflow-wrap:anywhere; }" in response.text
    assert ".section-sources table.report-table td" in response.text
    assert "@page { size:A4; margin:0; }" in response.text
    assert (
        ".cover, .report-page, .report-section { width:210mm; min-height:297mm;"
        in response.text
    )
    assert "break-after:page; page-break-after:always;" in response.text
    assert "tr, p, li { break-inside:avoid; page-break-inside:avoid; }" in response.text
    assert ".viewer-toolbar { display:none; }" in response.text
    assert "Front matter" in response.text
    assert "Valuation purpose" in response.text
    assert "Prepare for a sale or transaction" in response.text
    assert "Valuation date" in response.text
    assert "Indicative fair-market value" in response.text
    assert "Download PDF" in response.text
    assert "PDF download ready" in response.text
    assert "Professional PDF export is ready" not in response.text
    assert "Use your browser's print command" not in response.text
    assert "Demo Indicative Valuation Report" in response.text
    assert "Demo data - not for reliance" in response.text
    assert "simulated" in response.text


@pytest.mark.asyncio
async def test_html_viewer_refuses_delivery_when_professional_audit_fails(
    client,
    fresh_all_db,
    monkeypatch,
):
    report_id = await _register_and_seed_report(client, "html-audit-fail@example.com")

    def fake_html_audit(html, *, demo_mode):
        assert "Indicative Valuation Report" in html
        assert demo_mode is False
        return ReportQualityAudit(
            artifact="valuation_report_html",
            issues=(
                ReportQualityIssue(
                    "missing_html_marker",
                    "Browser report HTML is missing marker: Valuation range visual",
                ),
            ),
            metadata={"url_count": 2},
        )

    monkeypatch.setattr(main_module, "audit_valuation_report_html", fake_html_audit)

    response = await client.get(f"/wizard/report/{report_id}/view")

    assert response.status_code == 500
    assert "failed professional artifact quality checks" in response.json()["detail"]
    assert "missing_html_marker" in response.json()["detail"]
    assert response.headers["content-type"].startswith("application/json")
