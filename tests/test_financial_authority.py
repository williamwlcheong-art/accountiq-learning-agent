"""Focused tests for authoritative financial-document selection."""
import asyncio

import aiosqlite
import pytest

from financial_authority import (
    AuthorityConflictError,
    authoritative_financial_rows,
    claim_document_retry,
    complete_document_authority,
    promote_document_authority,
)


async def _insert_document(
    db,
    *,
    company_id: int,
    document_id: int,
    status: str = "done",
    supersedes_document_id: int | None = None,
):
    await db.execute(
        """
        INSERT INTO documents
            (id, company_id, filename, filepath, extraction_status,
             extraction_completed_at, supersedes_document_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            company_id,
            f"accounts-{document_id}.pdf",
            f"/tmp/accounts-{document_id}.pdf",
            status,
            "2026-07-17 12:00:00" if status == "done" else None,
            supersedes_document_id,
        ),
    )


async def _insert_row(db, document_id: int, company_id: int, statement: str, period: str, value: float):
    await db.execute(
        """
        INSERT INTO financial_rows
            (document_id, company_id, statement, row_key, row_label, period, value)
        VALUES (?, ?, ?, 'revenue', 'Revenue', ?, ?)
        """,
        (document_id, company_id, statement, period, value),
    )


@pytest.mark.asyncio
async def test_only_done_documents_can_be_promoted(tmp_path):
    async with aiosqlite.connect(tmp_path / "authority.db") as db:
        db.row_factory = aiosqlite.Row
        await db.execute("CREATE TABLE companies (id INTEGER PRIMARY KEY)")
        await db.execute("INSERT INTO companies VALUES (1)")
        await db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(db, company_id=1, document_id=10, status="failed")
        await _insert_row(db, 10, 1, "pnl", "2025", 100)
        await db.commit()

        with pytest.raises(ValueError, match="completed extraction"):
            await promote_document_authority(db, 10)

        row = await (await db.execute("SELECT COUNT(*) FROM document_authority")).fetchone()
        assert row[0] == 0


@pytest.mark.asyncio
async def test_overlapping_completed_document_surfaces_conflict_without_replacing_authority(tmp_path):
    async with aiosqlite.connect(tmp_path / "authority.db") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(db, company_id=1, document_id=10)
        await _insert_document(db, company_id=1, document_id=11)
        await _insert_row(db, 10, 1, "pnl", "2025", 100)
        await _insert_row(db, 11, 1, "pnl", "2025", 200)
        await db.commit()

        await promote_document_authority(db, 10)
        with pytest.raises(AuthorityConflictError) as exc_info:
            await promote_document_authority(db, 11)

        assert exc_info.value.conflicts == [
            {"statement": "pnl", "period": "2025", "document_id": 10}
        ]
        row = await (await db.execute(
            "SELECT document_id FROM document_authority WHERE company_id=1 AND statement='pnl' AND period='2025'"
        )).fetchone()
        assert row[0] == 10


@pytest.mark.asyncio
async def test_completed_replacement_promotes_only_slots_owned_by_superseded_revision(tmp_path):
    async with aiosqlite.connect(tmp_path / "authority.db") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(db, company_id=1, document_id=10)
        await _insert_row(db, 10, 1, "pnl", "2025", 100)
        await db.commit()
        await promote_document_authority(db, 10)

        await _insert_document(db, company_id=1, document_id=11, status="processing", supersedes_document_id=10)
        await _insert_row(db, 11, 1, "pnl", "2025", 200)
        await db.commit()

        rows_before = await authoritative_financial_rows(db, 1)
        assert rows_before[0]["value"] == 100

        await db.execute(
            "UPDATE documents SET extraction_status='done', extraction_completed_at=datetime('now') WHERE id=11"
        )
        await db.commit()
        await promote_document_authority(db, 11)

        rows_after = await authoritative_financial_rows(db, 1)
        assert rows_after[0]["value"] == 200
        assert rows_after[0]["document_id"] == 11


@pytest.mark.asyncio
async def test_failed_intermediate_revision_does_not_block_later_successful_replacement(tmp_path):
    async with aiosqlite.connect(tmp_path / "authority.db") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(db, company_id=1, document_id=10)
        await _insert_row(db, 10, 1, "pnl", "2025", 100)
        await db.commit()
        await promote_document_authority(db, 10)

        await _insert_document(db, company_id=1, document_id=11, status="failed", supersedes_document_id=10)
        await _insert_document(db, company_id=1, document_id=12, supersedes_document_id=11)
        await _insert_row(db, 12, 1, "pnl", "2025", 300)
        await db.commit()

        await promote_document_authority(db, 12)

        rows = await authoritative_financial_rows(db, 1)
        assert rows[0]["document_id"] == 12
        assert rows[0]["value"] == 300


@pytest.mark.asyncio
async def test_reader_rejects_unassigned_overlap_instead_of_choosing_newest(tmp_path):
    async with aiosqlite.connect(tmp_path / "authority.db") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(db, company_id=1, document_id=10)
        await _insert_document(db, company_id=1, document_id=11)
        await _insert_row(db, 10, 1, "pnl", "2025", 100)
        await _insert_row(db, 11, 1, "pnl", "2025", 200)
        await db.commit()

        with pytest.raises(AuthorityConflictError):
            await authoritative_financial_rows(db, 1)


@pytest.mark.asyncio
async def test_late_completion_cannot_promote_when_newer_revision_exists(tmp_path):
    async with aiosqlite.connect(tmp_path / "authority.db") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(db, company_id=1, document_id=10)
        await _insert_document(db, company_id=1, document_id=11, supersedes_document_id=10)
        await _insert_row(db, 10, 1, "pnl", "2025", 100)
        await _insert_row(db, 11, 1, "pnl", "2025", 200)
        await db.commit()

        await promote_document_authority(db, 11)
        with pytest.raises(ValueError, match="newer document revision"):
            await promote_document_authority(db, 10)

        rows = await authoritative_financial_rows(db, 1)
        assert rows[0]["document_id"] == 11
        assert rows[0]["value"] == 200


@pytest.mark.asyncio
async def test_concurrent_unrelated_promotions_do_not_silently_replace(tmp_path):
    database_path = tmp_path / "authority.db"
    async with aiosqlite.connect(database_path) as setup_db:
        setup_db.row_factory = aiosqlite.Row
        await setup_db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT,
                filepath TEXT UNIQUE,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL,
                currency TEXT DEFAULT 'NZD',
                unit TEXT DEFAULT 'whole',
                confidence REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            """
        )
        await _insert_document(setup_db, company_id=1, document_id=10)
        await _insert_document(setup_db, company_id=1, document_id=11)
        await _insert_row(setup_db, 10, 1, "pnl", "2025", 100)
        await _insert_row(setup_db, 11, 1, "pnl", "2025", 200)
        await setup_db.commit()

    first = aiosqlite.connect(database_path)
    second = aiosqlite.connect(database_path)
    async with first as first_db, second as second_db:
        first_db.row_factory = aiosqlite.Row
        second_db.row_factory = aiosqlite.Row
        results = await asyncio.gather(
            promote_document_authority(first_db, 10),
            promote_document_authority(second_db, 11),
            return_exceptions=True,
        )

    assert sum(result is None for result in results) == 1
    conflicts = [result for result in results if isinstance(result, AuthorityConflictError)]
    assert len(conflicts) == 1

    async with aiosqlite.connect(database_path) as verify_db:
        row = await (await verify_db.execute(
            "SELECT document_id FROM document_authority"
        )).fetchone()
    assert row[0] in {10, 11}


@pytest.mark.asyncio
async def test_concurrent_retry_claims_only_one_document(tmp_path):
    database_path = tmp_path / "retry.db"
    async with aiosqlite.connect(database_path) as setup_db:
        await setup_db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                extraction_status TEXT,
                updated_at TEXT
            );
            CREATE TABLE document_authority (
                document_id INTEGER NOT NULL
            );
            INSERT INTO documents VALUES (10, 7, 'failed', NULL);
            """
        )

    first = aiosqlite.connect(database_path)
    second = aiosqlite.connect(database_path)
    async with first as first_db, second as second_db:
        results = await asyncio.gather(
            claim_document_retry(first_db, 10, 7),
            claim_document_retry(second_db, 10, 7),
        )

    assert sorted(results) == [False, True]
    async with aiosqlite.connect(database_path) as verify_db:
        status = await (await verify_db.execute(
            "SELECT extraction_status FROM documents WHERE id=10"
        )).fetchone()
    assert status[0] == "processing"


@pytest.mark.asyncio
async def test_completion_publishes_done_status_with_authority_atomically(tmp_path):
    database_path = tmp_path / "completion.db"
    async with aiosqlite.connect(database_path) as setup_db:
        setup_db.row_factory = aiosqlite.Row
        await setup_db.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                extraction_status TEXT,
                extraction_completed_at TEXT,
                confidence_score REAL,
                updated_at TEXT,
                supersedes_document_id INTEGER
            );
            CREATE TABLE financial_rows (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                company_id INTEGER,
                statement TEXT,
                row_key TEXT,
                row_label TEXT,
                period TEXT,
                value REAL
            );
            CREATE TABLE document_authority (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                period TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, statement, period)
            );
            INSERT INTO documents VALUES (10, 1, 'processing', NULL, NULL, NULL, NULL);
            INSERT INTO financial_rows VALUES (1, 10, 1, 'pnl', 'revenue', 'Revenue', '2025', 100);
            """
        )

    writer = aiosqlite.connect(database_path)
    reader = aiosqlite.connect(database_path)
    async with writer as writer_db, reader as reader_db:
        writer_db.row_factory = aiosqlite.Row
        reader_db.row_factory = aiosqlite.Row
        await complete_document_authority(writer_db, 10, 0.9)
        row = await (await reader_db.execute(
            """
            SELECT d.extraction_status, da.document_id
            FROM documents d
            LEFT JOIN document_authority da ON da.document_id=d.id
            WHERE d.id=10
            """
        )).fetchone()

    assert tuple(row) == ("done", 10)
