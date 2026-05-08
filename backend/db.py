"""
Database schema and connection management for AccountIQ Learning Agent.
SQLite via aiosqlite for async FastAPI compatibility.
"""
import sqlite3
import aiosqlite
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "accountiq_learning.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Companies master table
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    ticker      TEXT,                        -- e.g. "AIR" for Air NZ
    exchange    TEXT,                        -- NZX / ASX / Private
    sector      TEXT,
    country     TEXT    DEFAULT 'NZ',
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(name, exchange)
);

-- Every uploaded PDF document
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER REFERENCES companies(id),
    filename        TEXT    NOT NULL,
    filepath        TEXT    NOT NULL UNIQUE,
    report_type     TEXT,                    -- 'annual_report' | 'compilation' | 'management_accounts'
    entity_type     TEXT,                    -- 'listed' | 'sme'
    fiscal_year_end TEXT,                    -- e.g. '2025-03-31'
    page_count      INTEGER,
    has_ocr         INTEGER DEFAULT 0,       -- 1 if OCR was needed
    extraction_status TEXT DEFAULT 'pending', -- pending | processing | done | failed
    extraction_model  TEXT,                  -- claude model used
    raw_claude_response TEXT,               -- full JSON from Claude
    confidence_score  REAL,                 -- 0–1 overall confidence
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- Individual financial rows extracted (P&L + BS rows)
CREATE TABLE IF NOT EXISTS financial_rows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    company_id  INTEGER REFERENCES companies(id),
    statement   TEXT    NOT NULL,    -- 'pnl' | 'bs'
    row_key     TEXT    NOT NULL,    -- canonical key e.g. 'revenue', 'cash_and_bank'
    row_label   TEXT    NOT NULL,    -- display label e.g. 'Revenue', 'Cash & bank'
    period      TEXT    NOT NULL,    -- e.g. '2025', '2024'
    value       REAL,                -- null = not found / dash
    currency    TEXT    DEFAULT 'NZD',
    unit        TEXT    DEFAULT 'whole',  -- 'whole' | 'thousands' | 'millions'
    source_text TEXT,                -- raw line from PDF that produced this value
    confidence  REAL,                -- per-row confidence 0–1
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Label patterns: what raw PDF labels map to canonical row keys
CREATE TABLE IF NOT EXISTS label_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key   TEXT    NOT NULL,   -- e.g. 'revenue'
    statement       TEXT    NOT NULL,   -- 'pnl' | 'bs'
    raw_label       TEXT    NOT NULL,   -- normalised label found in PDF
    entity_type     TEXT,               -- 'listed' | 'sme' | null (any)
    exchange        TEXT,               -- 'NZX' | 'ASX' | null (any)
    match_count     INTEGER DEFAULT 1,  -- how many docs confirmed this mapping
    last_seen       TEXT    DEFAULT (datetime('now')),
    UNIQUE(canonical_key, raw_label)
);

-- Per-document extraction log for debugging
CREATE TABLE IF NOT EXISTS extraction_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    level       TEXT    DEFAULT 'info',   -- info | warn | error
    message     TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Authenticated users
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    hashed_pw   TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_fin_rows_doc    ON financial_rows(document_id);
CREATE INDEX IF NOT EXISTS idx_fin_rows_company ON financial_rows(company_id);
CREATE INDEX IF NOT EXISTS idx_fin_rows_key    ON financial_rows(row_key, period);
CREATE INDEX IF NOT EXISTS idx_patterns_key    ON label_patterns(canonical_key);
CREATE INDEX IF NOT EXISTS idx_patterns_raw    ON label_patterns(raw_label);
CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);
"""


def get_sync_conn() -> sqlite3.Connection:
    """Synchronous connection used for one-off setup."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def get_db() -> aiosqlite.Connection:
    """Async dependency for FastAPI routes."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


def _migrate_db(conn: sqlite3.Connection):
    """Add columns introduced in v2/v3 — safe to run on an existing database."""
    for sql in [
        "ALTER TABLE documents ADD COLUMN narrative TEXT",
        "ALTER TABLE documents ADD COLUMN reporting_standard TEXT DEFAULT 'UNKNOWN'",
        # Phase 2: user ownership columns
        "ALTER TABLE companies ADD COLUMN user_id INTEGER",
        "ALTER TABLE documents ADD COLUMN user_id INTEGER",
        # Phase 3: business profile description
        "ALTER TABLE companies ADD COLUMN description TEXT",
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Phase 2: rebuild companies UNIQUE constraint to include user_id.
    # SQLite cannot ALTER a UNIQUE constraint — must use table-rename pattern.
    # Idempotency guard: skip if UNIQUE(name, exchange, user_id) already present.
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='companies'"
    )
    schema_row = cur.fetchone()
    schema_sql = schema_row[0] if schema_row else ""

    if "UNIQUE(name, exchange, user_id)" not in schema_sql:
        # Clean up any failed previous attempt — use try/except so a missing
        # companies_new table doesn't abort the whole migration.
        try:
            cur2 = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='companies_new'"
            )
            if cur2.fetchone():
                conn.execute("DROP TABLE companies_new")
        except sqlite3.OperationalError:
            pass

        # Use individual conn.execute() calls inside an explicit transaction so
        # the ALTER TABLE changes made above are NOT committed before this block
        # runs.  executescript() issues an implicit COMMIT before it starts,
        # which can leave the DB partially migrated on a crash between the two
        # phases.
        conn.execute("BEGIN")
        try:
            conn.execute("""
                CREATE TABLE companies_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    ticker      TEXT,
                    exchange    TEXT,
                    sector      TEXT,
                    country     TEXT    DEFAULT 'NZ',
                    created_at  TEXT    DEFAULT (datetime('now')),
                    user_id     INTEGER,
                    UNIQUE(name, exchange, user_id)
                )
            """)
            conn.execute("""
                INSERT INTO companies_new
                    SELECT id, name, ticker, exchange, sector, country, created_at, user_id
                    FROM companies
            """)
            conn.execute("DROP TABLE companies")
            conn.execute("ALTER TABLE companies_new RENAME TO companies")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # Phase 2: indexes for user_id query performance
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_companies_user ON companies(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_documents_user  ON documents(user_id)",
    ]:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError:
            pass

    # Phase 3: business profile child tables (ownership via company_id, no user_id column)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS management_team (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            title       TEXT,
            bio         TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ebitda_adjustments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            label       TEXT NOT NULL,
            amount      REAL NOT NULL,
            rationale   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    # Index for fast child-list queries by company
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_mgmt_team_company ON management_team(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_ebitda_adj_company ON ebitda_adjustments(company_id)",
    ]:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()


def init_db():
    """Create all tables if they don't exist (called at startup)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_sync_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_db(conn)
        print(f"[DB] Initialised at {DB_PATH}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

def normalise_label(text: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation for matching."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def record_patterns(db: aiosqlite.Connection, mappings: list[dict]):
    """
    Upsert label→canonical_key patterns learned from a document.
    mappings: [{"canonical_key": str, "statement": str, "raw_label": str,
                "entity_type": str|None, "exchange": str|None}]
    """
    for m in mappings:
        raw = normalise_label(m["raw_label"])
        if not raw:
            continue
        await db.execute("""
            INSERT INTO label_patterns (canonical_key, statement, raw_label, entity_type, exchange)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(canonical_key, raw_label) DO UPDATE SET
                match_count = match_count + 1,
                last_seen   = datetime('now')
        """, (m["canonical_key"], m["statement"], raw,
              m.get("entity_type"), m.get("exchange")))
    await db.commit()


async def get_pattern_library(db: aiosqlite.Connection) -> dict:
    """
    Return pattern library as {statement: {canonical_key: [raw_labels]}}
    ordered by match_count descending.
    """
    async with db.execute("""
        SELECT statement, canonical_key, raw_label, match_count
        FROM label_patterns
        ORDER BY match_count DESC
    """) as cur:
        rows = await cur.fetchall()

    lib: dict = {}
    for row in rows:
        stmt = row["statement"]
        key  = row["canonical_key"]
        lib.setdefault(stmt, {}).setdefault(key, []).append(row["raw_label"])
    return lib
