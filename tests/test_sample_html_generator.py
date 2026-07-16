"""Tests for the reproducible sample valuation browser HTML generator."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_sample_valuation_html.py"
NON_ASCII_DASHES = ("‐", "‑", "‒", "–", "—", "−")


class _FailedAudit:
    passed = False

    def as_dict(self):
        return {
            "artifact": "valuation_report_content",
            "passed": False,
            "issues": [{"code": "incomplete_cash_flow_schedule"}],
        }


def _load_generator_module():
    spec = importlib.util.spec_from_file_location("generate_sample_valuation_html", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sample_html_generator_creates_current_browser_report_pack(tmp_path):
    generator = _load_generator_module()

    assert "demo" in generator.DEFAULT_OUTPUT.name

    output_path = generator.generate_sample_html(
        tmp_path / "sample-valuation.html",
        company_name="Sample Browser Limited",
        prepared_at="2026-07-04 09:45:00",
        valuation_purpose="Finance or investment discussions",
        report_id=43,
    )

    html = output_path.read_text(encoding="utf-8")
    audit = generator.audit_generated_html(output_path, demo_mode=True)

    assert output_path.exists()
    assert audit.passed is True
    assert audit.issues == ()
    assert audit.metadata["url_count"] >= 2
    assert "<!DOCTYPE html>" in html
    assert '<main class="report">' in html
    assert '<section class="cover">' in html
    assert 'aria-label="Report basis"' in html
    assert "Uploaded financials" in html
    assert "Five private inputs" in html
    assert "Public-source trail" in html
    assert "AccountIQ model" in html
    assert '<section class="report-page contents">' in html
    assert 'id="basis-of-preparation"' in html
    assert 'href="./pdf"' in html
    assert ".report a { overflow-wrap:anywhere; }" in html
    assert ".report-table caption" in html
    assert "caption-side:top" in html
    assert ".section-sources .report-table td" in html
    assert "word-break:break-word" in html
    assert "<caption>Sources and References detailed schedule</caption>" in html
    assert "<caption>Mid-case forecast cash-flow schedule</caption>" in html
    assert "<script" not in html.lower()
    assert "Demo Indicative Valuation Report" in html
    assert "Sample Browser Limited" in html
    assert "Finance or investment discussions" in html
    assert "Report letter" in html
    assert "Prepared for" in html
    assert "Prepared by" in html
    assert "AccountIQ valuation team" in html
    assert "Preparer role" in html
    assert "Report channel" in html
    assert "AIQ-VAL-000043" in html
    assert "Purpose and reliance" in html
    assert "Important limitation" in html
    assert "Demo data - not for reliance" in html
    assert "Demo data only - not for reliance" in html
    assert "Management input - Valuation purpose" in html
    assert "Management input - Revenue outlook" in html
    assert "Sources and References" in html
    assert "Glossary" in html
    assert not any(dash in html for dash in NON_ASCII_DASHES)


def test_sample_html_generator_creates_live_label_browser_report_pack(tmp_path):
    generator = _load_generator_module()

    output_path = generator.generate_sample_html(
        tmp_path / "live-sample-valuation.html",
        company_name="Sample Live Label Limited",
        prepared_at="2026-07-04 10:15:00",
        valuation_purpose="Prepare for a sale or transaction",
        report_id=44,
        demo_mode=False,
    )

    html = output_path.read_text(encoding="utf-8")
    audit = generator.audit_generated_html(output_path, demo_mode=False)

    assert audit.passed is True
    assert audit.issues == ()
    assert "Indicative Valuation Report" in html
    assert "Sample Live Label Limited" in html
    assert "Prepare for a sale or transaction" in html
    assert "Report letter" in html
    assert "Prepared for" in html
    assert "Prepared by" in html
    assert "AccountIQ valuation team" in html
    assert "Preparer role" in html
    assert "Report channel" in html
    assert "AIQ-VAL-000044" in html
    assert "Purpose and reliance" in html
    assert "Important limitation" in html
    assert "Confidential - indicative only" in html
    assert 'aria-label="Report basis"' in html
    assert "Five private inputs" in html
    assert "Demo data - not for reliance" not in html
    assert "Demo data only - not for reliance" not in html
    assert "This demo indicative valuation" not in html
    assert "sample public-source research" not in html
    assert "The sample company" not in html
    assert "Demo figures" not in html
    assert "simulated research" not in html
    assert "sample report" not in html
    assert "Management input trail" in html
    assert "Management input - Owner or key-person dependency" in html
    assert "Derived technical assumptions" in html
    assert not any(dash in html for dash in NON_ASCII_DASHES)


def test_sample_html_generator_audits_structured_content_before_rendering(monkeypatch):
    generator = _load_generator_module()

    monkeypatch.setattr(generator, "audit_valuation_report_content", lambda _sections: _FailedAudit())

    with pytest.raises(RuntimeError, match="incomplete_cash_flow_schedule"):
        generator.render_sample_html()
