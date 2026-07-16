"""Tests for the reproducible sample valuation PDF generator."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pdfplumber
import pytest


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_sample_valuation_pdf.py"
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_quality import audit_valuation_report_pdf

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
    spec = importlib.util.spec_from_file_location("generate_sample_valuation_pdf", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sample_pdf_generator_creates_current_report_pack(tmp_path):
    generator = _load_generator_module()

    assert "demo" in generator.DEFAULT_OUTPUT.name

    output_path = generator.generate_sample_pdf(
        tmp_path / "sample-valuation.pdf",
        company_name="Sample Generator Limited",
        prepared_at="2026-07-04 09:45:00",
        valuation_purpose="Finance or investment discussions",
        report_id=42,
    )

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF-")
    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        contents_text = pdf.pages[1].extract_text() or ""
        page_count = len(pdf.pages)

    assert page_count >= 23
    assert "Demo Indicative Valuation Report | Sample Generator Limited" in text
    assert "Cover and valuation snapshot" in contents_text
    assert "Front matter - Report letter and basis of preparation" in contents_text
    assert "Report letter" in text
    assert "Prepared for Sample Generator Limited" in text
    assert "Prepared by AccountIQ valuation team" in text
    assert "Preparer role Valuation report preparation and evidence synthesis" in text
    assert "Report channel Secure AccountIQ workspace and downloadable PDF" in text
    assert "Purpose and reliance Finance or investment discussions" in text
    assert "Important limitation" in text
    assert "FM Basis of preparation" not in contents_text
    assert re.search(r"Cover and valuation snapshot\s+(\.\s+)+1", contents_text)
    assert "Valuation purpose" in text
    assert "Finance or investment discussions" in text
    assert "Basis of preparation" in text
    assert "VALUATION SNAPSHOT" in text
    assert "01 Introduction" in text
    assert "Client and report purpose" in text
    assert "Valuation date and basis of value" in text
    assert "Sources of information" in text
    assert "Liability, confidentiality and compliance" in text
    assert "21 Glossary" in text
    assert "DEMO DATA - NOT FOR RELIANCE" in text
    assert not any(dash in text for dash in NON_ASCII_DASHES)


def test_sample_pdf_generator_creates_live_label_report_pack(tmp_path):
    generator = _load_generator_module()

    output_path = generator.generate_sample_pdf(
        tmp_path / "live-sample-valuation.pdf",
        company_name="Sample Live Label Limited",
        prepared_at="2026-07-04 10:15:00",
        valuation_purpose="Prepare for a sale or transaction",
        report_id=44,
        demo_mode=False,
    )

    audit = audit_valuation_report_pdf(output_path, demo_mode=False)
    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert audit.passed is True
    assert audit.issues == ()
    assert "Indicative Valuation Report | Sample Live Label Limited" in text
    assert "Prepare for a sale or transaction" in text
    assert "Indicative valuation support only; obtain" in text
    assert "independent professional advice before" in text
    assert "Management input trail" in text
    assert "Management input - Owner or key-person" in text
    assert "dependency" in text
    assert "Management-confirmed private input" in text
    assert "Derived technical assumptions" in text
    assert "DEMO DATA - NOT FOR RELIANCE" not in text
    assert "This demo indicative valuation" not in text
    assert "sample public-source research" not in text
    assert "The sample company" not in text
    assert "Demo figures" not in text
    assert "simulated research" not in text
    assert "sample report" not in text
    assert not any(dash in text for dash in NON_ASCII_DASHES)


def test_sample_pdf_generator_audits_structured_content_before_rendering(monkeypatch, tmp_path):
    generator = _load_generator_module()
    render_calls = []

    monkeypatch.setattr(generator, "audit_valuation_report_content", lambda _sections: _FailedAudit())
    monkeypatch.setattr(generator, "write_report_pdf", lambda *args, **kwargs: render_calls.append((args, kwargs)))

    with pytest.raises(RuntimeError, match="incomplete_cash_flow_schedule"):
        generator.generate_sample_pdf(tmp_path / "sample-valuation.pdf")

    assert render_calls == []


def test_sample_pdf_generator_audits_rendered_pdf_after_writing(monkeypatch, tmp_path):
    generator = _load_generator_module()
    audit_calls = []

    def fake_write_report_pdf(output_path, **_kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"%PDF-1.4\n% sample\n")

    def fake_audit_generated_pdf(path, *, demo_mode):
        audit_calls.append((path, demo_mode))
        return object()

    monkeypatch.setattr(generator, "write_report_pdf", fake_write_report_pdf)
    monkeypatch.setattr(generator, "audit_generated_pdf", fake_audit_generated_pdf)

    output_path = generator.generate_sample_pdf(tmp_path / "sample-valuation.pdf", demo_mode=False)

    assert output_path.exists()
    assert audit_calls == [(output_path, False)]
