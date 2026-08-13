"""Integration coverage for no-key financial-statement ingestion."""
from __future__ import annotations

import sys
from pathlib import Path

import aiosqlite
import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import ingestion
import main as main_module


@pytest.mark.asyncio
async def test_ingestion_without_an_ai_key_persists_rule_based_financial_rows(fresh_all_db, monkeypatch):
    statement_text = """
Profit and Loss
Year ended 31 March 2025          2025       2024
Revenue                         1,000,000   900,000
EBITDA                            220,000   180,000
Net profit                        145,000   110,000
"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(ingestion, "OPENAI_API_KEY", "")
    monkeypatch.setattr(
        ingestion,
        "extract_pdf_text",
        lambda _filepath: (statement_text, [statement_text], 1, False),
    )

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
            ("no-key-ingestion@example.com", "unused"),
        ) as cur:
            user_id = cur.lastrowid
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, ?, ?)",
            ("No-key Ingestion Limited", "Private", user_id),
        ) as cur:
            company_id = cur.lastrowid
        async with db.execute(
            """
            INSERT INTO documents (company_id, user_id, filename, filepath, entity_type, extraction_status)
            VALUES (?, ?, ?, ?, 'sme', 'pending')
            """,
            (company_id, user_id, "accounts.pdf", "/tmp/accounts.pdf"),
        ) as cur:
            document_id = cur.lastrowid
        await db.commit()

        result = await ingestion.ingest_document(
            db,
            document_id,
            company_id,
            "/tmp/accounts.pdf",
            "sme",
            "Private",
            "2025-03-31",
        )

        async with db.execute(
            "SELECT extraction_status, extraction_model, narrative FROM documents WHERE id=?",
            (document_id,),
        ) as cur:
            document = await cur.fetchone()
        async with db.execute(
            "SELECT row_key, period, value FROM financial_rows WHERE document_id=? ORDER BY row_key, period DESC",
            (document_id,),
        ) as cur:
            rows = [dict(row) for row in await cur.fetchall()]

    assert result["rows_saved"] >= 3
    assert document["extraction_status"] == "done"
    assert document["extraction_model"] == "rule_based"
    assert any(row == {"row_key": "revenue", "period": "2025", "value": 1_000_000.0} for row in rows)
    assert any(row == {"row_key": "ebitda", "period": "2025", "value": 220_000.0} for row in rows)
