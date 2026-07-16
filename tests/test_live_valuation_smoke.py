"""Tests for the live valuation smoke-test harness.

The real script is intentionally manual because it calls Anthropic. These tests
mock the provider and PDF renderer so CI verifies the harness wiring without
making network calls.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "run_live_valuation_smoke.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("run_live_valuation_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_live_smoke_inputs_include_report_quality_evidence():
    module = _load_smoke_module()

    inputs = module.build_smoke_inputs()
    valuation_result = inputs["valuation_result"]

    assert inputs["intake_answers"]["valuation_purpose"] == "understand_value"
    assert valuation_result["forecast_cash_flow_schedule"]["headers"] == [
        "Mid-case forecast",
        "Year 1",
        "Year 2",
        "Year 3",
        "Year 4",
        "Year 5",
    ]
    assert any(
        "https://www.rbnz.govt.nz/statistics" in json.dumps(row)
        for row in valuation_result["sources_table"]["rows"]
    )
    assert any(
        "Owner or key-person dependency" in json.dumps(row)
        for row in valuation_result["assumption_source_trail"]["rows"]
    )
    assert len(valuation_result["specific_risk_factors"]["rows"]) >= 5


@pytest.mark.asyncio
async def test_live_smoke_refuses_to_run_without_real_key(tmp_path, monkeypatch):
    module = _load_smoke_module()
    monkeypatch.setattr(module, "_demo_mode_enabled", lambda: False)
    monkeypatch.setattr(module, "_live_anthropic_key_configured", lambda: False)

    with pytest.raises(RuntimeError, match="real Anthropic API key"):
        await module.run_live_valuation_smoke(
            output_json=tmp_path / "smoke.json",
            output_pdf=None,
        )


@pytest.mark.asyncio
async def test_live_smoke_runs_preflight_validators_and_writes_artifacts(
    tmp_path,
    monkeypatch,
):
    module = _load_smoke_module()
    monkeypatch.setattr(module, "_demo_mode_enabled", lambda: False)
    monkeypatch.setattr(module, "_live_anthropic_key_configured", lambda: True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-live-smoke-test")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    calls: dict[str, object] = {}

    async def fake_preflight(api_key, model):
        calls["preflight"] = (api_key, model)
        return True

    async def fake_call_claude(system_prompt, user_message, sections):
        calls["prompt"] = {
            "system_prompt": system_prompt,
            "user_message": user_message,
            "sections": sections,
        }
        return {section: f"Generated section for {section} with sufficient content." for section in sections}

    def fake_validate_content(content, report_type):
        calls["validate_content"] = (report_type, sorted(content))

    def fake_validate_figures(content, valuation_result):
        calls["validate_figures"] = valuation_result["forecast_cash_flow_schedule"]["headers"]

    class FakeAudit:
        passed = True
        issues = ()

        def __init__(self, artifact):
            self.artifact = artifact

        def as_dict(self):
            return {
                "artifact": self.artifact,
                "passed": True,
                "issues": [],
                "metadata": {},
            }

    def fake_content_audit(content):
        calls["content_audit"] = sorted(content)
        return FakeAudit("valuation_report_content")

    def fake_html_audit(html, *, demo_mode):
        calls["html_audit"] = (html, demo_mode)
        return FakeAudit("valuation_report_html")

    def fake_pdf_audit(output_path, *, demo_mode):
        calls["pdf_audit"] = (str(output_path), demo_mode)
        return FakeAudit("valuation_report_pdf")

    def fake_write_report_pdf(output_path, **kwargs):
        calls["pdf"] = {
            "output_path": str(output_path),
            "company_name": kwargs["company_name"],
            "demo_mode": kwargs["demo_mode"],
        }
        output_path.write_bytes(b"%PDF-1.4\n% mocked live smoke pdf\n")

    monkeypatch.setattr(module, "_run_live_research_preflight", fake_preflight)
    monkeypatch.setattr(module, "_call_claude_for_report", fake_call_claude)
    monkeypatch.setattr(module, "_validate_generated_report_content", fake_validate_content)
    monkeypatch.setattr(module, "_validate_valuation_report_figures", fake_validate_figures)
    monkeypatch.setattr(module, "audit_valuation_report_content", fake_content_audit)
    monkeypatch.setattr(module, "audit_valuation_report_html", fake_html_audit)
    monkeypatch.setattr(module, "audit_valuation_report_pdf", fake_pdf_audit)
    monkeypatch.setattr(module, "write_report_pdf", fake_write_report_pdf)

    result = await module.run_live_valuation_smoke(
        output_json=tmp_path / "smoke.json",
        output_html=tmp_path / "smoke.html",
        output_pdf=tmp_path / "smoke.pdf",
        prepared_at="2026-07-04 10:00:00",
    )

    assert result["status"] == "passed"
    assert result["preflight_fresh"] is True
    assert result["sections"] == len(module.SECTION_SCHEMAS["valuation_advisory"])
    assert Path(result["json_path"]).exists()
    assert Path(result["html_path"]).exists()
    assert Path(result["pdf_path"]).exists()
    assert calls["preflight"] == ("sk-ant-live-smoke-test", "claude-sonnet-4-6")
    assert calls["validate_content"][0] == "valuation_advisory"
    assert calls["validate_figures"] == [
        "Mid-case forecast",
        "Year 1",
        "Year 2",
        "Year 3",
        "Year 4",
        "Year 5",
    ]
    assert calls["content_audit"] == sorted(module.SECTION_SCHEMAS["valuation_advisory"])
    assert calls["html_audit"][1] is False
    assert "<!DOCTYPE html>" in calls["html_audit"][0]
    assert 'href="./pdf"' in calls["html_audit"][0]
    assert "Live Smoke Indicative Valuation Report" in calls["html_audit"][0]
    assert 'id="basis-of-preparation"' in calls["html_audit"][0]
    assert "Derived technical assumptions" in calls["html_audit"][0]
    assert calls["pdf_audit"] == (result["pdf_path"], False)
    assert result["content_audit"]["passed"] is True
    assert result["html_audit"]["passed"] is True
    assert result["pdf_audit"]["passed"] is True
    assert calls["pdf"]["company_name"] == "AccountIQ Sample Limited"
    assert calls["pdf"]["demo_mode"] is False

    payload = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert payload["metadata"]["purpose"] == "AccountIQ live valuation smoke test"
    assert payload["metadata"]["model"] == "claude-sonnet-4-6"
    assert "AccountIQ-Calculated DCF Analysis Table" in calls["prompt"]["user_message"]
