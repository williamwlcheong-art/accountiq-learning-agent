"""Tests for the reproducible sample bank credit-paper pack."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "sample_credit_report.py"
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_quality import audit_bank_credit_report_pdf  # noqa: E402


def _load_module():
    spec = importlib.util.spec_from_file_location("sample_credit_report", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sample_credit_report"] = module
    spec.loader.exec_module(module)
    return module


def test_sample_credit_pdf_is_audited_and_contains_lender_pack_spine(tmp_path):
    module = _load_module()

    output_path = module.generate_sample_pdf(tmp_path / "sample-credit.pdf", report_id=42)

    assert output_path.exists()
    audit = audit_bank_credit_report_pdf(output_path, demo_mode=True)
    assert audit.passed is True
    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        page_count = len(pdf.pages)

    assert page_count >= 16
    assert "Demo Bank Credit Paper | AccountIQ Sample Services Limited" in text
    assert "DEMO DATA - NOT FOR RELIANCE" in text
    assert "Transaction Summary" in text
    assert "Sources & Uses" in text
    assert "Facilities Requested" in text
    assert "Sponsor bridge" in text
    assert "DSCR" in text
    assert "ICR" in text
    assert "NTOA" in text
    assert "Proposed Covenants" in text
    assert "Conditions Precedent" in text
    assert "Screening-only" in text or "screening-only" in text
    assert "AIQ-REP-000042" in text


def test_sample_credit_html_is_audited_and_uses_same_sections(tmp_path):
    module = _load_module()

    output_path = module.generate_sample_html(tmp_path / "sample-credit.html", report_id=43)
    html = output_path.read_text(encoding="utf-8")

    audit = module.audit_bank_credit_report_html(html, demo_mode=True)
    assert audit.passed is True
    assert '<section class="cover">' in html
    assert '<section class="report-page contents">' in html
    assert 'aria-label="Report basis"' in html
    assert 'href="./pdf"' in html
    assert "Demo data - not for reliance" in html
    assert "Transaction Summary" in html
    assert "Facilities Requested" in html
    assert "Sponsor bridge" in html
    assert "AIQ-REP-000043" in html
    assert "<script" not in html.lower()
