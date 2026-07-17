import hashlib
import json
from pathlib import Path

import aiosqlite
import pytest

from db import DB_PATH, init_db
from report_snapshots import (
    SnapshotIntegrityError,
    create_report_input_snapshot,
    load_report_input_snapshot,
)


async def _seed_snapshot_source(db):
    user = await db.execute(
        "INSERT INTO users (email, hashed_pw) VALUES ('snapshot@example.com', 'hash')"
    )
    user_id = user.lastrowid
    company = await db.execute(
        """
        INSERT INTO companies (name, exchange, user_id, sector, description)
        VALUES ('Snapshot Co', 'Private', ?, 'Services', 'Original profile')
        """,
        (user_id,),
    )
    company_id = company.lastrowid
    await db.execute(
        "INSERT INTO management_team (company_id, name, title, bio) VALUES (?, 'Alex', 'CEO', 'Founder')",
        (company_id,),
    )
    await db.execute(
        "INSERT INTO ebitda_adjustments (company_id, label, amount, rationale) VALUES (?, 'Owner wage', 12000, 'Market rate')",
        (company_id,),
    )
    document = await db.execute(
        """
        INSERT INTO documents
            (company_id, user_id, filename, filepath, extraction_status,
             extraction_completed_at, file_hash)
        VALUES (?, ?, 'accounts.pdf', '/tmp/snapshot-accounts.pdf', 'done',
                datetime('now'), ?)
        """,
        (company_id, user_id, "a" * 64),
    )
    document_id = document.lastrowid
    other_document = await db.execute(
        """
        INSERT INTO documents
            (company_id, user_id, filename, filepath, extraction_status, file_hash)
        VALUES (?, ?, 'other.pdf', '/tmp/snapshot-other.pdf', 'failed', ?)
        """,
        (company_id, user_id, "b" * 64),
    )
    await db.executemany(
        """
        INSERT INTO financial_rows
            (document_id, company_id, statement, row_key, row_label, period,
             value, currency, unit, source_text, confidence)
        VALUES (?, ?, ?, ?, ?, '2025', ?, 'NZD', 'thousands', ?, 0.95)
        """,
        [
            (document_id, company_id, "pnl", "revenue", "Revenue", 900, "Revenue 900"),
            (document_id, company_id, "pnl", "ebitda", "EBITDA", 180, "EBITDA 180"),
            (other_document.lastrowid, company_id, "pnl", "revenue", "Revenue", 999, "Revenue 999"),
        ],
    )
    await db.execute(
        """
        INSERT INTO document_authority (company_id, statement, period, document_id)
        VALUES (?, 'pnl', '2025', ?)
        """,
        (company_id, document_id),
    )
    report = await db.execute(
        "INSERT INTO reports (company_id, user_id, report_type, status) VALUES (?, ?, 'valuation_advisory', 'pending_payment')",
        (company_id, user_id),
    )
    report_id = report.lastrowid
    await db.execute(
        "INSERT INTO report_intake (report_id, answers) VALUES (?, ?)",
        (report_id, json.dumps({"forecast_horizon": 5, "normalisations": [{"amount": 1000, "rationale": "One-off"}]})),
    )
    await db.commit()
    return user_id, company_id, report_id


@pytest.mark.asyncio
async def test_snapshot_schema_is_idempotent_and_normalised(fresh_all_db):
    init_db()
    init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(report_input_snapshots)") as cur:
            snapshot_columns = {row[1] for row in await cur.fetchall()}
        async with db.execute("PRAGMA table_info(report_snapshot_rows)") as cur:
            row_columns = {row[1] for row in await cur.fetchall()}
        async with db.execute("PRAGMA index_list(report_input_snapshots)") as cur:
            indexes = {row[1] for row in await cur.fetchall()}

    assert {"report_id", "document_manifest", "frozen_inputs", "schema_version", "valuation_engine_version", "canonical_digest"}.issubset(snapshot_columns)
    assert {"snapshot_id", "document_id", "statement", "row_key", "period", "value", "currency", "unit", "source_text", "confidence"}.issubset(row_columns)
    assert "sqlite_autoindex_report_input_snapshots_1" in indexes


@pytest.mark.asyncio
async def test_snapshot_copies_only_authoritative_rows_and_is_immutable(fresh_all_db):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user_id, company_id, report_id = await _seed_snapshot_source(db)
        snapshot_id = await create_report_input_snapshot(db, report_id, company_id, user_id)
        original = await load_report_input_snapshot(db, report_id)

        await db.execute("UPDATE companies SET description='Changed later' WHERE id=?", (company_id,))
        await db.execute("UPDATE financial_rows SET value=1 WHERE company_id=?", (company_id,))
        await db.commit()
        loaded = await load_report_input_snapshot(db, report_id)
        duplicate_id = await create_report_input_snapshot(db, report_id, company_id, user_id)

    assert duplicate_id == snapshot_id
    assert loaded == original
    assert loaded["company"]["description"] == "Original profile"
    assert [row["value"] for row in loaded["financial_rows"]] == [180.0, 900.0]
    assert {row["document_hash"] for row in loaded["financial_rows"]} == {"a" * 64}


@pytest.mark.asyncio
async def test_snapshot_backfills_legacy_document_hash_from_retained_file(fresh_all_db, tmp_path):
    retained = tmp_path / "legacy.pdf"
    retained.write_bytes(b"legacy financial statement")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user_id, company_id, report_id = await _seed_snapshot_source(db)
        await db.execute(
            "UPDATE documents SET file_hash=NULL, filepath=? WHERE company_id=? AND extraction_status='done'",
            (str(retained), company_id),
        )
        await db.commit()

        await create_report_input_snapshot(db, report_id, company_id, user_id)
        loaded = await load_report_input_snapshot(db, report_id)

    expected = hashlib.sha256(retained.read_bytes()).hexdigest()
    assert loaded["document_manifest"][0]["file_hash"] == expected


@pytest.mark.asyncio
async def test_snapshot_digest_binds_stored_versions(fresh_all_db):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user_id, company_id, report_id = await _seed_snapshot_source(db)
        await create_report_input_snapshot(db, report_id, company_id, user_id)
        await db.execute(
            "UPDATE report_input_snapshots SET valuation_engine_version='tampered' WHERE report_id=?",
            (report_id,),
        )
        await db.commit()

        with pytest.raises(SnapshotIntegrityError, match="version"):
            await load_report_input_snapshot(db, report_id)


@pytest.mark.asyncio
async def test_snapshot_digest_tamper_fails_closed(fresh_all_db):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user_id, company_id, report_id = await _seed_snapshot_source(db)
        snapshot_id = await create_report_input_snapshot(db, report_id, company_id, user_id)
        await db.execute(
            "UPDATE report_snapshot_rows SET value=999999 WHERE snapshot_id=? AND row_key='revenue'",
            (snapshot_id,),
        )
        await db.commit()

        with pytest.raises(SnapshotIntegrityError, match="digest"):
            await load_report_input_snapshot(db, report_id)
