import argparse
import importlib.util
import json
import os
from pathlib import Path

import aiosqlite
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
async def test_runner_uses_existing_generation_and_private_render_boundaries(tmp_path, monkeypatch):
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

    calls = {"generation": 0, "pdf": 0}

    async def fake_generate(report_id, company_id, user_id, report_type, intake_answers):
        calls["generation"] += 1
        assert report_type == "valuation_advisory"
        async with aiosqlite.connect(database_path) as db:
            await db.execute(
                "UPDATE reports SET status='awaiting_review', content=? WHERE id=? AND status='queued'",
                (json.dumps(_valid_sections()), report_id),
            )
            await db.execute(
                "INSERT INTO reviews (report_id, status) VALUES (?, 'awaiting_review')",
                (report_id,),
            )
            await db.commit()

    def fake_write_pdf(html_text, output_path):
        calls["pdf"] += 1
        assert "Kauri Field Services Limited" in html_text
        output_path.write_bytes(b"%PDF-1.4 mocked UAT output")

    import report_rendering
    monkeypatch.setattr(main_module, "_generate_report", fake_generate)
    monkeypatch.setattr(report_rendering, "write_pdf", fake_write_pdf)

    evidence_path = await runner.run(argparse.Namespace(
        confirm_live_uat=True,
        fixture=FIXTURE_PATH,
        evidence_root=evidence_root,
    ))

    evidence = json.loads(evidence_path.read_text())
    assert calls == {"generation": 1, "pdf": 1}
    assert evidence["result"] == "passed"
    assert evidence["report_status"] == "awaiting_review"
    assert evidence["approval_performed"] is False
    assert evidence["email_performed"] is False
    assert evidence["stripe_performed"] is False
    assert evidence["configured_model"]
    assert "returned model metadata" in evidence["model_metadata_note"]
    assert (evidence_path.parent / "private-report.html").exists()
    assert (evidence_path.parent / evidence["pdf"]["filename"]).exists()
