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
