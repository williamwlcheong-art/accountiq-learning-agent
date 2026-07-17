"""Focused regression tests for database schema migrations."""
import sqlite3

import pytest

from db import _migrate_db


LEGACY_SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    ticker      TEXT,
    exchange    TEXT,
    sector      TEXT,
    country     TEXT    DEFAULT 'NZ',
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(name, exchange)
);

CREATE TABLE documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER REFERENCES companies(id),
    filename    TEXT NOT NULL,
    filepath    TEXT NOT NULL UNIQUE
);

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE,
    hashed_pw   TEXT NOT NULL
);
"""


def _legacy_connection(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "legacy.db")
    conn.executescript(LEGACY_SCHEMA)
    conn.execute(
        """
        INSERT INTO companies
            (id, name, ticker, exchange, sector, country, created_at)
        VALUES (7, 'Legacy Limited', 'LEG', 'Private', 'Services', 'NZ', '2024-01-02')
        """
    )
    conn.execute(
        """
        INSERT INTO documents (id, company_id, filename, filepath)
        VALUES (11, 7, 'accounts.pdf', '/tmp/accounts.pdf')
        """
    )
    conn.commit()
    return conn


def test_rebuilds_populated_legacy_companies_with_foreign_keys_enabled(tmp_path):
    conn = _legacy_connection(tmp_path)
    try:
        _migrate_db(conn)

        company = conn.execute(
            """
            SELECT id, name, ticker, exchange, sector, country, created_at,
                   user_id, description
            FROM companies
            """
        ).fetchone()
        assert company == (
            7,
            "Legacy Limited",
            "LEG",
            "Private",
            "Services",
            "NZ",
            "2024-01-02",
            None,
            None,
        )
        assert conn.execute(
            "SELECT id, company_id FROM documents"
        ).fetchone() == (11, 7)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO documents (company_id, filename, filepath) VALUES (999, 'bad.pdf', '/tmp/bad.pdf')"
            )

        conn.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES ('Legacy Limited', 'Private', 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO companies (name, exchange, user_id) VALUES ('Legacy Limited', 'Private', 1)"
            )
    finally:
        conn.close()


def test_migration_is_idempotent(tmp_path):
    conn = _legacy_connection(tmp_path)
    try:
        _migrate_db(conn)
        _migrate_db(conn)

        assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM document_authority"
        ).fetchone()[0] == 0
        document_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()
        }
        assert {
            "file_hash",
            "extraction_completed_at",
            "supersedes_document_id",
        } <= document_columns
        authority_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(document_authority)").fetchall()
        }
        assert "sqlite_autoindex_document_authority_1" in authority_indexes
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'companies_new'"
        ).fetchone() is None
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_migration_recovers_from_stale_companies_new_table(tmp_path):
    conn = _legacy_connection(tmp_path)
    try:
        conn.execute("CREATE TABLE companies_new (id INTEGER PRIMARY KEY, stale TEXT)")
        conn.execute("INSERT INTO companies_new VALUES (99, 'partial migration')")
        conn.commit()

        _migrate_db(conn)

        assert conn.execute(
            "SELECT id, name FROM companies"
        ).fetchall() == [(7, "Legacy Limited")]
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'companies_new'"
        ).fetchone() is None
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_migration_backfills_only_unambiguous_completed_sources(tmp_path):
    conn = sqlite3.connect(tmp_path / "authority-backfill.db")
    try:
        conn.executescript(
            """
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                exchange TEXT,
                user_id INTEGER,
                description TEXT,
                UNIQUE(name, exchange, user_id)
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL UNIQUE,
                extraction_status TEXT,
                user_id INTEGER
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
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                hashed_pw TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO companies VALUES (1, 'Legacy', 'Private', 1, NULL);
            INSERT INTO documents VALUES (10, 1, 'one.pdf', '/tmp/one.pdf', 'done', 1);
            INSERT INTO documents VALUES (11, 1, 'two.pdf', '/tmp/two.pdf', 'done', 1);
            INSERT INTO financial_rows VALUES (1, 10, 1, 'pnl', 'revenue', 'Revenue', '2024', 100);
            INSERT INTO financial_rows VALUES (2, 10, 1, 'pnl', 'revenue', 'Revenue', '2025', 110);
            INSERT INTO financial_rows VALUES (3, 11, 1, 'pnl', 'revenue', 'Revenue', '2025', 120);
            """
        )

        _migrate_db(conn)

        assert conn.execute(
            "SELECT statement, period, document_id FROM document_authority ORDER BY period"
        ).fetchall() == [("pnl", "2024", 10)]
    finally:
        conn.close()
