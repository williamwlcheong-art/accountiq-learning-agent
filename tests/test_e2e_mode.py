"""Tests for deterministic backend E2E mode."""
import json
import os
import subprocess
import sys
from pathlib import Path

import aiosqlite
import pytest

import db as _db_module
import main as _main_module
from report_prompts import SECTION_SCHEMAS


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


def test_db_path_can_be_overridden_by_env(tmp_path):
    """ACCOUNTIQ_DB_PATH lets Playwright/dev runs use an isolated database."""
    db_path = tmp_path / "accountiq-e2e.db"
    env = os.environ.copy()
    env["ACCOUNTIQ_DB_PATH"] = str(db_path)
    env["PYTHONPATH"] = str(BACKEND_DIR)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import db; print(db.DB_PATH)",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == str(db_path)


@pytest.mark.asyncio
async def test_e2e_ingestion_inserts_mock_financial_rows(fresh_all_db, monkeypatch):
    """E2E ingestion should complete without parsing PDFs or calling Claude."""
    monkeypatch.setattr(_main_module, "E2E_MODE", True, raising=False)

    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        user_cur = await conn.execute(
            "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
            ("e2e-ingestion@example.com", "x"),
        )
        user_id = user_cur.lastrowid
        company_cur = await conn.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
            ("E2E Trading Co", user_id),
        )
        company_id = company_cur.lastrowid
        doc_cur = await conn.execute(
            """
            INSERT INTO documents (company_id, filename, filepath, user_id, extraction_status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (company_id, "missing-fixture.pdf", "/tmp/missing-fixture.pdf", user_id),
        )
        document_id = doc_cur.lastrowid
        await conn.commit()

    await _main_module._run_ingestion(
        document_id,
        company_id,
        "/tmp/missing-fixture.pdf",
        "sme",
        "Private",
        "",
    )

    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT extraction_status, extraction_model, confidence_score FROM documents WHERE id=?",
            (document_id,),
        ) as cur:
            document = await cur.fetchone()
        async with conn.execute(
            "SELECT row_key, period, value FROM financial_rows WHERE document_id=?",
            (document_id,),
        ) as cur:
            rows = [dict(row) for row in await cur.fetchall()]
        async with conn.execute(
            "SELECT message FROM extraction_log WHERE document_id=? ORDER BY id",
            (document_id,),
        ) as cur:
            logs = [row["message"] for row in await cur.fetchall()]

    assert document["extraction_status"] == "done"
    assert document["extraction_model"] == "accountiq-e2e-fixture"
    assert document["confidence_score"] == 1.0
    assert len(rows) >= 8
    assert {"revenue", "ebitda", "net_profit", "cash_and_bank"}.issubset(
        {row["row_key"] for row in rows}
    )
    assert any("E2E" in message for message in logs)


@pytest.mark.asyncio
async def test_e2e_report_generation_stores_full_schema_without_claude(
    fresh_all_db,
    monkeypatch,
):
    """E2E reports should be immediately viewable and should not call external AI services."""
    monkeypatch.setattr(_main_module, "E2E_MODE", True, raising=False)

    async def fail_research(*args, **kwargs):
        raise AssertionError("E2E mode must not call valuation research")

    async def fail_claude(*args, **kwargs):
        raise AssertionError("E2E mode must not call Claude report generation")

    monkeypatch.setattr(_main_module, "run_valuation_research", fail_research)
    monkeypatch.setattr(_main_module, "_call_claude_for_report", fail_claude)

    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        user_cur = await conn.execute(
            "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
            ("e2e-report@example.com", "x"),
        )
        user_id = user_cur.lastrowid
        company_cur = await conn.execute(
            """
            INSERT INTO companies (name, exchange, sector, description, user_id)
            VALUES (?, 'Private', 'Professional Services', ?, ?)
            """,
            (
                "E2E Advisory Co",
                "A professional services firm used for deterministic E2E report generation.",
                user_id,
            ),
        )
        company_id = company_cur.lastrowid
        report_cur = await conn.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status)
            VALUES (?, ?, 'valuation_advisory', 'queued')
            """,
            (company_id, user_id),
        )
        report_id = report_cur.lastrowid
        await conn.execute(
            "INSERT INTO report_intake (report_id, answers) VALUES (?, ?)",
            (report_id, json.dumps({"purpose": "Owner planning"})),
        )
        await conn.commit()

    await _main_module._generate_report(
        report_id,
        company_id,
        user_id,
        "valuation_advisory",
        {"purpose": "Owner planning"},
    )

    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT status, content, error_message, completed_at FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            report = await cur.fetchone()

    assert report["status"] == "done"
    assert report["error_message"] is None
    assert report["completed_at"] is not None

    content = json.loads(report["content"])
    assert set(SECTION_SCHEMAS["valuation_advisory"]).issubset(content.keys())
    assert "E2E Advisory Co" in content["business_overview"]
    disclaimer = content["disclaimer"].lower()
    assert "indicative" in disclaimer
    assert "financial advice" in disclaimer
    assert "fmca" in disclaimer or "financial markets conduct" in disclaimer
    assert "not relied" in disclaimer or "should not be relied" in disclaimer
