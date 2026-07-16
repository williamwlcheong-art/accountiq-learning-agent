#!/usr/bin/env python3
"""Explicit, fail-closed live valuation UAT runner.

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
    parser = argparse.ArgumentParser(description="Run one guarded live valuation UAT")
    parser.add_argument("--confirm-live-uat", action="store_true", help="acknowledge that Anthropic calls incur cost")
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


async def _seed_database(database_path: Path, fixture: dict, insert_report_job) -> tuple[int, int, int]:
    import aiosqlite

    async with aiosqlite.connect(database_path) as db:
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
        await db.executemany(
            """
            INSERT INTO financial_rows
                (company_id, statement, row_key, row_label, period, value, currency, unit, confidence)
            VALUES (?, ?, ?, ?, ?, ?, 'NZD', 'whole', 1.0)
            """,
            [
                (
                    company_id, row["statement"], row["row_key"], row["row_label"],
                    row["period"], row["value"],
                )
                for row in fixture["financial_rows"]
            ],
        )

        report_id = await insert_report_job(
            db,
            company_id=company_id,
            user_id=user_id,
            report_type="valuation_advisory",
            status="queued",
            intake_answers=fixture["intake_answers"],
        )
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


async def run(args: argparse.Namespace) -> Path:
    if not args.confirm_live_uat:
        raise RuntimeError("Refusing live UAT without --confirm-live-uat")

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
    )
    evidence_root = args.evidence_root.expanduser().resolve()
    if evidence_root.is_relative_to(ROOT):
        raise RuntimeError("--evidence-root must be outside the repository")

    # Backend modules are imported only after the environment has passed preflight.
    import db as db_module
    import main as main_module
    from report_prompts import SECTION_SCHEMAS
    from report_rendering import render_report_html, report_pdf_path, write_pdf
    from research_loop import CLAUDE_MODEL, WEB_SEARCH_TOOL

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
    )
    await main_module._generate_report(
        report_id,
        company_id,
        user_id,
        "valuation_advisory",
        fixture["intake_answers"],
    )
    result = await _load_result(preflight.database_path, report_id)
    sections = json.loads(result["content"]) if result["content"] else {}
    checks = evaluate_valuation_report(
        report_status=result["status"],
        sections=sections,
        purchase_status=result["purchase_status"],
        review_status=result["review_status"],
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output_dir = evidence_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(output_dir, 0o700)
    evidence_path = output_dir / "evidence.json"

    evidence = {
        "schema_version": 1,
        "run_id": run_id,
        "report_id": report_id,
        "report_status": result["status"],
        "fixture_sha256": preflight.fixture_sha256,
        "configured_model": CLAUDE_MODEL,
        "configured_research_tool_type": WEB_SEARCH_TOOL.get("type"),
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
        "model_metadata_note": "Configured values only; current generation boundaries do not expose returned model metadata.",
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
