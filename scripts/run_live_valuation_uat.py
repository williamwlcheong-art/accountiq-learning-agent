#!/usr/bin/env python3
"""Explicit, fail-closed valuation UAT and synthetic rehearsal runner.

Importing this module performs no UAT, database, network, payment, email or PDF work.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "valuation_uat" / "synthetic_nz_sme.json"
DEFAULT_DATABASE = ROOT / "data" / "accountiq_learning.db"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one guarded valuation UAT")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--confirm-live-uat", action="store_true",
        help="acknowledge that Anthropic calls incur cost",
    )
    mode.add_argument(
        "--synthetic-rehearsal", action="store_true",
        help="run the service pipeline with fixed no-network AI substitutes",
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--evidence-root", type=Path, required=True,
        help="new private evidence directory outside the repository",
    )
    return parser


def _load_fixture(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("UAT fixture root must be a JSON object")
    return value


async def _seed_database(
    database_path: Path,
    fixture: dict,
    insert_report_job,
    create_report_snapshot,
) -> tuple[int, int, int]:
    import aiosqlite

    async with aiosqlite.connect(database_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
            (fixture["uat_user"]["email"], "UAT-NO-LOGIN"),
        ) as cursor:
            user_id = cursor.lastrowid

        company = fixture["company"]
        async with db.execute(
            """
            INSERT INTO companies (name, exchange, sector, country, user_id, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                company["name"], company["exchange"], company["sector"],
                company["country"], user_id, company["description"],
            ),
        ) as cursor:
            company_id = cursor.lastrowid

        await db.executemany(
            "INSERT INTO management_team (company_id, name, title, bio) VALUES (?, ?, ?, ?)",
            [
                (company_id, person["name"], person["title"], person["bio"])
                for person in fixture["management_team"]
            ],
        )
        await db.executemany(
            "INSERT INTO ebitda_adjustments (company_id, label, amount, rationale) VALUES (?, ?, ?, ?)",
            [
                (company_id, adjustment["label"], adjustment["amount"], adjustment["rationale"])
                for adjustment in fixture["ebitda_adjustments"]
            ],
        )
        fixture_bytes = json.dumps(fixture, sort_keys=True).encode("utf-8")
        async with db.execute(
            """
            INSERT INTO documents
                (company_id, user_id, filename, filepath, extraction_status,
                 extraction_completed_at, file_hash)
            VALUES (?, ?, 'synthetic-uat-accounts.json', ?, 'done', datetime('now'), ?)
            """,
            (
                company_id,
                user_id,
                str(database_path.with_suffix(".synthetic-source.json")),
                hashlib.sha256(fixture_bytes).hexdigest(),
            ),
        ) as cursor:
            document_id = cursor.lastrowid
        await db.executemany(
            """
            INSERT INTO financial_rows
                (document_id, company_id, statement, row_key, row_label, period,
                 value, currency, unit, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'NZD', 'whole', 1.0)
            """,
            [
                (
                    document_id, company_id, row["statement"], row["row_key"],
                    row["row_label"], row["period"], row["value"],
                )
                for row in fixture["financial_rows"]
            ],
        )
        await db.executemany(
            """
            INSERT INTO document_authority (company_id, statement, period, document_id)
            VALUES (?, ?, ?, ?)
            """,
            [
                (company_id, statement, period, document_id)
                for statement, period in sorted({
                    (row["statement"], row["period"])
                    for row in fixture["financial_rows"]
                })
            ],
        )

        wacc = fixture["wacc_assumption_set"]
        await db.execute(
            """
            INSERT INTO wacc_assumption_sets (
                name, version, status, active, risk_free_rate,
                equity_risk_premium, beta, beta_type, cost_of_debt,
                target_debt_weight, target_equity_weight, additional_premium,
                scenario_spread, source_references, publisher, as_of_date,
                rationale, approved_at, approved_by_user_id
            ) VALUES (?, ?, 'approved', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                wacc["name"], wacc["version"], wacc["risk_free_rate"],
                wacc["equity_risk_premium"], wacc["beta"], wacc["beta_type"],
                wacc["cost_of_debt"], wacc["target_debt_weight"],
                wacc["target_equity_weight"], wacc["additional_premium"],
                wacc["scenario_spread"], wacc["source_references"],
                wacc["publisher"], wacc["as_of_date"], wacc["rationale"],
                wacc["approved_at"], user_id,
            ),
        )

        report_id = await insert_report_job(
            db,
            company_id=company_id,
            user_id=user_id,
            report_type="valuation_advisory",
            status="queued",
            intake_answers=fixture["intake_answers"],
        )
        await create_report_snapshot(db, report_id, company_id, user_id)
        await db.execute(
            """
            INSERT INTO purchases (report_id, user_id, amount_cents, currency, status, paid_at)
            VALUES (?, ?, 49500, 'nzd', 'paid', datetime('now'))
            """,
            (report_id, user_id),
        )
        await db.commit()
    return user_id, company_id, report_id


async def _load_result(database_path: Path, report_id: int) -> dict:
    import aiosqlite

    async with aiosqlite.connect(database_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT r.status, r.content, r.error_message, r.created_at,
                   c.name AS company_name, p.status AS purchase_status,
                   rv.status AS review_status
            FROM reports r
            JOIN companies c ON c.id=r.company_id
            JOIN purchases p ON p.report_id=r.id
            LEFT JOIN reviews rv ON rv.report_id=r.id
            WHERE r.id=?
            """,
            (report_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        raise RuntimeError(f"Generated report {report_id} was not found")
    return dict(row)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _synthetic_report_sections(section_names: list[str], table_sections: list[str]) -> dict:
    """Return narrative-only model output for the no-network rehearsal."""
    content = {
        section: (
            f"Synthetic rehearsal narrative for {section.replace('_', ' ')}. "
            "This text exists only to exercise AccountIQ report assembly and validation."
        )
        for section in section_names
    }
    for section in table_sections:
        content[section] = (
            f"Synthetic rehearsal narrative for {section.replace('_', ' ')}. "
            "The authoritative table is attached by the Python valuation pipeline."
        )
    content["disclaimer"] = (
        "This synthetic report is indicative only, is not financial advice under the FMCA, "
        "and should not be relied on without independent professional advice."
    )
    return content


async def _deterministic_evidence(
    database_path: Path,
    report_id: int,
    sections: dict,
    research_brief: dict,
) -> tuple[dict, list[dict[str, object]]]:
    """Recompute the frozen valuation and prove Python-owned output authority."""
    import aiosqlite
    from fcff_engine import ENGINE_VERSION, calculate_fcff, calculation_digest
    from report_prompts import TABLE_SECTIONS_VALUATION
    from report_snapshots import SNAPSHOT_SCHEMA_VERSION, load_report_input_snapshot
    from valuation import compute_multiples_crosscheck
    from valuation_inputs import build_valuation_inputs
    from valuation_tables import build_valuation_tables, valuation_table_sections

    async with aiosqlite.connect(database_path) as db:
        db.row_factory = aiosqlite.Row
        snapshot = await load_report_input_snapshot(db, report_id)
        async with db.execute(
            """
            SELECT COUNT(*) AS count
            FROM wacc_assumption_sets
            WHERE active=1 AND status='approved'
            """
        ) as cursor:
            active_wacc_count = (await cursor.fetchone())["count"]

    inputs = build_valuation_inputs(snapshot["financial_rows"], snapshot, require_fcff=True)
    result = calculate_fcff(inputs)
    multiples = compute_multiples_crosscheck(
        normalised_ebitda=float(inputs.normalised_ebitda.value),
        ev_ebitda_low=research_brief["ev_ebitda_low"],
        ev_ebitda_high=research_brief["ev_ebitda_high"],
    )
    table_authority = build_valuation_tables(
        snapshot["financial_rows"], inputs, result, multiples,
    )
    expected_tables = valuation_table_sections(table_authority)
    matched_table_count = sum(
        isinstance(sections.get(name), dict)
        and sections[name].get("table") == expected_tables[name]
        for name in TABLE_SECTIONS_VALUATION
    )
    tables_match = matched_table_count == len(TABLE_SECTIONS_VALUATION)
    reconciliations = {
        scenario.name: str(scenario.reconciliation_difference)
        for scenario in result.scenarios
    }

    def check(name: str, passed: bool, detail: str) -> dict[str, object]:
        return {"name": name, "passed": passed, "detail": detail}

    checks = [
        check(
            "snapshot_schema_v2",
            snapshot["schema_version"] == SNAPSHOT_SCHEMA_VERSION,
            snapshot["schema_version"],
        ),
        check(
            "decimal_fcff_engine",
            snapshot["valuation_engine_version"] == ENGINE_VERSION
            and result.engine_version == ENGINE_VERSION,
            result.engine_version,
        ),
        check(
            "one_active_approved_wacc",
            active_wacc_count == 1,
            str(active_wacc_count),
        ),
        check(
            "complete_confirmed_fcff_assumptions",
            all(value is not None for value in (
                inputs.forecast, inputs.tax, inputs.depreciation_policy,
                inputs.capex_policy, inputs.operating_nwc_policy,
            )),
            f"{inputs.forecast.horizon_years}-year forecast; tax policy {inputs.tax.policy_version}",
        ),
        check(
            "fcff_equity_reconciliation",
            all(scenario.reconciliation_difference == 0 for scenario in result.scenarios),
            ", ".join(f"{name}={value}" for name, value in reconciliations.items()),
        ),
        check(
            "python_owned_valuation_tables",
            tables_match,
            f"{matched_table_count}/{len(TABLE_SECTIONS_VALUATION)}",
        ),
    ]
    metadata = {
        "snapshot": {
            "schema_version": snapshot["schema_version"],
            "valuation_engine_version": snapshot["valuation_engine_version"],
            "canonical_digest": snapshot["canonical_digest"],
        },
        "fcff": {
            "engine_version": result.engine_version,
            "calculation_digest": calculation_digest(result),
            "scenario_reconciliations": reconciliations,
        },
        "table_authority": {
            "version": table_authority["version"],
            "rounding_policy": table_authority["rounding_policy"],
            "digest": table_authority["digest"],
            "section_names": list(expected_tables),
        },
        "approved_wacc": {
            "active_approved_count": active_wacc_count,
            "assumption_set_id": result.wacc.assumption_set_id,
            "name": result.wacc.assumption_set_name,
            "version": result.wacc.assumption_set_version,
            "as_of_date": result.wacc.as_of_date.isoformat(),
            "publisher": result.wacc.publisher,
            "source_references": result.wacc.source_references,
            "rationale": result.wacc.rationale,
            "approved_at": result.wacc.approved_at,
            "approved_by": result.wacc.approved_by,
        },
    }
    return metadata, checks


async def run(args: argparse.Namespace) -> Path:
    live_model = bool(getattr(args, "confirm_live_uat", False))
    synthetic_rehearsal = bool(getattr(args, "synthetic_rehearsal", False))
    if live_model == synthetic_rehearsal:
        raise RuntimeError(
            "Choose exactly one of --confirm-live-uat or --synthetic-rehearsal"
        )

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    # Match backend configuration loading before checking the complete effective
    # environment. This prevents repository-local settings appearing only after
    # the safety gate has passed.
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)

    from uat_safety import (
        evaluate_valuation_report,
        require_safe_uat_environment,
        write_immutable_json,
    )

    fixture_path = args.fixture.expanduser().resolve()
    fixture = _load_fixture(fixture_path)
    preflight = require_safe_uat_environment(
        fixture_path,
        fixture,
        default_database_path=DEFAULT_DATABASE,
        repository_root=ROOT,
        require_anthropic_key=live_model,
    )
    evidence_root = args.evidence_root.expanduser().resolve()
    if evidence_root.is_relative_to(ROOT):
        raise RuntimeError("--evidence-root must be outside the repository")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output_dir = evidence_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(output_dir, 0o700)
    evidence_path = output_dir / "evidence.json"

    # Backend modules are imported only after the environment has passed preflight.
    import db as db_module
    import main as main_module
    from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION
    from report_rendering import render_report_html, report_pdf_path, write_pdf
    from research_loop import CLAUDE_MODEL, WEB_SEARCH_TOOL, ResearchBrief

    if db_module.DB_PATH != preflight.database_path or main_module.DB_PATH != preflight.database_path:
        raise RuntimeError("Backend did not bind to the preflighted UAT database")
    if main_module.E2E_MODE:
        raise RuntimeError("Backend imported with E2E mode enabled")
    if not main_module._requires_admin_review("valuation_advisory"):
        raise RuntimeError("Backend imported with valuation admin review disabled")

    db_module.init_db()
    user_id, company_id, report_id = await _seed_database(
        preflight.database_path,
        fixture,
        main_module._insert_report_job,
        main_module.create_report_input_snapshot,
    )
    original_research = main_module.run_valuation_research
    original_report_call = main_module._call_claude_for_report
    captured_research: dict = {}
    boundary_calls = {"research": 0, "report_generation": 0}

    if synthetic_rehearsal:
        async def rehearsal_research(**_kwargs):
            boundary_calls["research"] += 1
            brief = ResearchBrief(**fixture["synthetic_research_brief"])
            captured_research.update(brief.model_dump())
            return brief

        async def rehearsal_report_call(_system_prompt, _user_message):
            boundary_calls["report_generation"] += 1
            return _synthetic_report_sections(
                SECTION_SCHEMAS["valuation_advisory"], TABLE_SECTIONS_VALUATION,
            )

        main_module.run_valuation_research = rehearsal_research
        main_module._call_claude_for_report = rehearsal_report_call
    else:
        async def captured_live_research(**kwargs):
            boundary_calls["research"] += 1
            brief = await original_research(**kwargs)
            captured_research.update(brief.model_dump())
            return brief

        async def captured_live_report_call(system_prompt, user_message):
            boundary_calls["report_generation"] += 1
            return await original_report_call(system_prompt, user_message)

        main_module.run_valuation_research = captured_live_research
        main_module._call_claude_for_report = captured_live_report_call

    try:
        await main_module._generate_report(report_id)
    finally:
        main_module.run_valuation_research = original_research
        main_module._call_claude_for_report = original_report_call

    result = await _load_result(preflight.database_path, report_id)
    sections = json.loads(result["content"]) if result["content"] else {}
    checks = evaluate_valuation_report(
        report_status=result["status"],
        sections=sections,
        purchase_status=result["purchase_status"],
        review_status=result["review_status"],
    )
    deterministic_metadata, deterministic_checks = await _deterministic_evidence(
        preflight.database_path,
        report_id,
        sections,
        captured_research or fixture["synthetic_research_brief"],
    )
    checks.extend(deterministic_checks)

    evidence = {
        "evidence_schema_version": 2,
        "run_id": run_id,
        "generation_mode": "live_model" if live_model else "synthetic_rehearsal",
        "report_id": report_id,
        "report_status": result["status"],
        "fixture_sha256": preflight.fixture_sha256,
        "configured_model": CLAUDE_MODEL,
        "configured_research_tool_type": WEB_SEARCH_TOOL.get("type"),
        "external_ai_calls_performed": live_model and any(boundary_calls.values()),
        "generation_boundary_calls": boundary_calls,
        "deterministic_authority": deterministic_metadata,
        "checks": checks,
    }

    if not all(check["passed"] for check in checks):
        evidence.update({"result": "failed", "error_message": result["error_message"]})
        write_immutable_json(evidence_path, evidence)
        raise RuntimeError(f"Valuation UAT failed deterministic checks; evidence: {evidence_path}")

    html_text = render_report_html(
        result["company_name"], "valuation_advisory", sections,
        result["created_at"], SECTION_SCHEMAS["valuation_advisory"],
    )
    html_path = output_dir / "private-report.html"
    html_path.write_text(html_text, encoding="utf-8")
    os.chmod(html_path, 0o600)
    pdf_path = report_pdf_path(output_dir, report_id)
    await asyncio.get_running_loop().run_in_executor(None, write_pdf, html_text, pdf_path)
    os.chmod(pdf_path, 0o600)

    evidence.update({
        "result": "passed",
        "fixture_id": fixture.get("fixture_id"),
        "database_filename": preflight.database_path.name,
        "origin": preflight.origin,
        "model_metadata_note": (
            "Configured values only; current generation boundaries do not expose returned model metadata."
            if live_model
            else "Configured model was not called; fixed synthetic substitutes exercised both AI boundaries."
        ),
        "section_keys": list(sections),
        "html": {"filename": html_path.name, "sha256": _file_sha256(html_path)},
        "pdf": {"filename": pdf_path.name, "sha256": _file_sha256(pdf_path)},
        "approval_performed": False,
        "email_performed": False,
        "stripe_performed": False,
    })
    write_immutable_json(evidence_path, evidence)
    return evidence_path


def main() -> int:
    args = _parser().parse_args()
    try:
        evidence_path = asyncio.run(run(args))
    except Exception as exc:
        print(f"[UAT ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[UAT] Passed. Sanitised evidence: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
