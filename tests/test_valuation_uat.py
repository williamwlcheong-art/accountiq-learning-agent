import argparse
import importlib.util
import json
import os
from pathlib import Path

import pytest

import db as db_module
import main as main_module
from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION
from uat_safety import (
    UATSafetyError,
    evaluate_valuation_report,
    require_safe_uat_environment,
    sanitise_evidence,
    write_immutable_json,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "valuation_uat" / "synthetic_nz_sme.json"
DEFAULT_DB = ROOT / "data" / "accountiq_learning.db"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _safe_env(db_path: Path) -> dict[str, str]:
    return {
        "ACCOUNTIQ_UAT_MODE": "true",
        "ACCOUNTIQ_DB_PATH": str(db_path),
        "APP_BASE_URL": "http://127.0.0.1:9876",
        "ACCOUNTIQ_E2E_MODE": "false",
        "ANTHROPIC_API_KEY": "test-key-never-used",
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"ACCOUNTIQ_UAT_MODE": "false"}, "UAT_MODE"),
        ({"ACCOUNTIQ_ENV": "production"}, "production environment"),
        ({"ACCOUNTIQ_DB_PATH": str(DEFAULT_DB)}, "default application database"),
        ({"APP_BASE_URL": "https://accountiq.example"}, "loopback origin"),
        ({"ACCOUNTIQ_E2E_MODE": "true"}, "E2E_MODE"),
        ({"ACCOUNTIQ_REQUIRE_ADMIN_REVIEW": "false"}, "REQUIRE_ADMIN_REVIEW"),
        ({"STRIPE_SECRET_KEY": "sk_test_value"}, "payment/email"),
        ({"SMTP_HOST": "smtp.example"}, "payment/email"),
    ],
)
def test_preflight_refuses_unsafe_environment(tmp_path, change, message):
    env = _safe_env(tmp_path / "valuation-uat.db")
    env.update(change)

    with pytest.raises(UATSafetyError, match=message):
        require_safe_uat_environment(
            FIXTURE_PATH, _fixture(), environ=env, default_database_path=DEFAULT_DB
        )


def test_preflight_refuses_database_inside_repository():
    database_path = ROOT / "data" / "disposable-valuation-uat.db"
    env = _safe_env(database_path)

    with pytest.raises(UATSafetyError, match="outside the repository"):
        require_safe_uat_environment(
            FIXTURE_PATH,
            _fixture(),
            environ=env,
            default_database_path=DEFAULT_DB,
            repository_root=ROOT,
        )


def test_preflight_requires_synthetic_or_authorised_fixture_and_invalid_email(tmp_path):
    fixture = _fixture()
    fixture["fixture_classification"] = "customer"
    fixture["authorised_for_uat"] = False
    fixture["uat_user"]["email"] = "person@example.com"

    with pytest.raises(UATSafetyError) as exc_info:
        require_safe_uat_environment(
            FIXTURE_PATH,
            fixture,
            environ=_safe_env(tmp_path / "valuation-uat.db"),
            default_database_path=DEFAULT_DB,
        )

    message = str(exc_info.value)
    assert "synthetic or expressly authorised" in message
    assert ".invalid" in message


def test_preflight_allows_no_api_key_only_for_synthetic_rehearsal(tmp_path):
    env = _safe_env(tmp_path / "valuation-uat.db")
    env.pop("ANTHROPIC_API_KEY")

    with pytest.raises(UATSafetyError, match="ANTHROPIC_API_KEY"):
        require_safe_uat_environment(
            FIXTURE_PATH, _fixture(), environ=env, default_database_path=DEFAULT_DB
        )

    preflight = require_safe_uat_environment(
        FIXTURE_PATH,
        _fixture(),
        environ=env,
        default_database_path=DEFAULT_DB,
        require_anthropic_key=False,
    )
    assert preflight.database_path == Path(env["ACCOUNTIQ_DB_PATH"])


def _valid_sections() -> dict:
    sections = {key: f"Complete {key} narrative." for key in SECTION_SCHEMAS["valuation_advisory"]}
    for key in TABLE_SECTIONS_VALUATION:
        sections[key] = {
            "narrative": f"Complete {key} narrative.",
            "table": {"headers": ["Metric", "Value"], "rows": [["Example", "$1"]]},
        }
    sections["disclaimer"] = (
        "This report is indicative only and is not financial advice under the FMCA. "
        "It should not be relied on without independent professional advice."
    )
    return sections


def test_evaluator_rejects_placeholders_missing_tables_and_wrong_state():
    sections = _valid_sections()
    sections["introduction"] = "[Section 'introduction' not generated — please retry]"
    sections["financial_performance"]["table"]["rows"][0][1] = "[Generation error — please retry]"
    sections["valuation_summary"] = {"narrative": "Summary", "table": {}}

    checks = evaluate_valuation_report(
        report_status="done",
        sections=sections,
        purchase_status="paid",
        review_status=None,
    )
    failed = {check["name"] for check in checks if not check["passed"]}

    assert {"awaiting_review", "review_record", "report_validation"} <= failed


def test_evaluator_accepts_complete_private_draft():
    checks = evaluate_valuation_report(
        report_status="awaiting_review",
        sections=_valid_sections(),
        purchase_status="paid",
        review_status="awaiting_review",
    )
    assert all(check["passed"] for check in checks)


def test_evidence_is_sanitised_and_cannot_be_overwritten(tmp_path):
    path = tmp_path / "evidence.json"
    payload = {"api_key": "secret", "content": "private report", "result": "passed"}
    write_immutable_json(path, payload)
    evidence = json.loads(path.read_text())

    assert evidence["result"] == "passed"
    assert "api_key" not in evidence and "content" not in evidence
    assert evidence["api_key_sha256"] and evidence["content_sha256"]
    assert sanitise_evidence({"section_keys": ["summary", "disclaimer"]}) == {
        "section_keys": ["summary", "disclaimer"]
    }
    with pytest.raises(FileExistsError):
        write_immutable_json(path, payload)
    assert "secret" not in json.dumps(sanitise_evidence(payload))


def _load_runner_module():
    path = ROOT / "scripts" / "run_live_valuation_uat.py"
    spec = importlib.util.spec_from_file_location("run_live_valuation_uat_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_importing_runner_has_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _load_runner_module()
    assert list(tmp_path.iterdir()) == []


def test_runner_requires_explicit_evidence_root():
    runner = _load_runner_module()
    with pytest.raises(SystemExit):
        runner._parser().parse_args(["--confirm-live-uat"])


def test_runner_requires_exactly_one_generation_mode():
    runner = _load_runner_module()
    with pytest.raises(SystemExit):
        runner._parser().parse_args(["--evidence-root", "/tmp/evidence"])
    with pytest.raises(SystemExit):
        runner._parser().parse_args([
            "--confirm-live-uat", "--synthetic-rehearsal",
            "--evidence-root", "/tmp/evidence",
        ])


@pytest.mark.asyncio
async def test_runner_refuses_evidence_inside_repository(tmp_path, monkeypatch):
    runner = _load_runner_module()
    database_path = tmp_path / "disposable-valuation-uat.db"
    for key, value in _safe_env(database_path).items():
        monkeypatch.setenv(key, value)
    for key in (
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "SMTP_HOST", "SMTP_USER",
        "SMTP_PASSWORD", "FROM_EMAIL",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="evidence-root must be outside"):
        await runner.run(argparse.Namespace(
            confirm_live_uat=True,
            fixture=FIXTURE_PATH,
            evidence_root=ROOT / "data" / "valuation-uat-evidence",
        ))
    assert not database_path.exists()


@pytest.mark.asyncio
async def test_runner_runs_no_network_pipeline_and_private_render_boundaries(tmp_path, monkeypatch):
    runner = _load_runner_module()
    database_path = tmp_path / "disposable-valuation-uat.db"
    evidence_root = tmp_path / "evidence"
    env = _safe_env(database_path)
    for key in (
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "SMTP_HOST", "SMTP_USER",
        "SMTP_PASSWORD", "FROM_EMAIL",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(db_module, "DB_PATH", database_path)
    monkeypatch.setattr(main_module, "DB_PATH", database_path)
    monkeypatch.setattr(main_module, "E2E_MODE", False)

    calls = {"pdf": 0}

    def fake_write_pdf(html_text, output_path):
        calls["pdf"] += 1
        assert "Kauri Field Services Limited" in html_text
        output_path.write_bytes(b"%PDF-1.4 mocked UAT output")

    import report_rendering
    monkeypatch.setattr(report_rendering, "write_pdf", fake_write_pdf)

    evidence_path = await runner.run(argparse.Namespace(
        confirm_live_uat=False,
        synthetic_rehearsal=True,
        fixture=FIXTURE_PATH,
        evidence_root=evidence_root,
    ))

    evidence = json.loads(evidence_path.read_text())
    assert calls == {"pdf": 1}
    assert evidence["result"] == "passed"
    assert evidence["evidence_schema_version"] == 2
    assert evidence["generation_mode"] == "synthetic_rehearsal"
    assert evidence["external_ai_calls_performed"] is False
    assert evidence["generation_boundary_calls"] == {
        "report_generation": 1,
        "research": 1,
    }
    assert evidence["report_status"] == "awaiting_review"
    assert evidence["approval_performed"] is False
    assert evidence["email_performed"] is False
    assert evidence["stripe_performed"] is False
    assert evidence["configured_model"]
    assert "was not called" in evidence["model_metadata_note"]
    snapshot = evidence["deterministic_authority"]["snapshot"]
    assert snapshot["schema_version"] == "2"
    assert snapshot["valuation_engine_version"] == "fcff-decimal-v1"
    assert len(snapshot["canonical_digest"]) == 64
    approved_wacc = evidence["deterministic_authority"]["approved_wacc"]
    assert approved_wacc["active_approved_count"] == 1
    assert approved_wacc["name"] == "Synthetic NZ SME services"
    assert approved_wacc["approved_by"].endswith(".invalid")
    assert all(check["passed"] for check in evidence["checks"])
    assert (evidence_path.parent / "private-report.html").exists()
    assert (evidence_path.parent / evidence["pdf"]["filename"]).exists()
