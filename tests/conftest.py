"""Shared pytest fixtures for AccountIQ tests."""
import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure backend/ is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Ensure tests/ itself is importable so test modules can do `import conftest`
# to access shared test state like _TMP_DB_PATH.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

# Load .env before any module imports so SECRET_KEY and ANTHROPIC_API_KEY are available.
# Walk up from the tests/ dir to find the .env (handles both worktree and main-repo runs).
_HERE = Path(__file__).resolve().parent
for _candidate in [
    _HERE.parent / ".env",
    _HERE.parent.parent / ".env",
    _HERE.parent.parent.parent / ".env",
    _HERE.parent.parent.parent.parent / ".env",  # main repo root when running in a git worktree
]:
    if _candidate.exists():
        from dotenv import load_dotenv as _load_dotenv
        _load_dotenv(_candidate, override=False)  # override=False: env vars already set by CI take precedence
        break

# CRITICAL: override DB_PATH BEFORE importing main (which imports db at module level)
_TMP_DB_FD, _TMP_DB_PATH = tempfile.mkstemp(suffix="_test.db")
os.close(_TMP_DB_FD)

import db as _db_module  # noqa: E402
_db_module.DB_PATH = Path(_TMP_DB_PATH)

# Now safe to import main (it will use the patched DB_PATH)
import main as _main_module  # noqa: E402

# Also patch main.DB_PATH (main imports DB_PATH by value, not by reference)
_main_module.DB_PATH = Path(_TMP_DB_PATH)

# Initialise schema in the temp DB
_db_module.init_db()


@pytest_asyncio.fixture
async def client():
    """AsyncClient wired to the FastAPI app with isolated DB."""
    async with AsyncClient(
        transport=ASGITransport(app=_main_module.app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def fresh_db():
    """Truncate users table between tests that need a clean slate."""
    import aiosqlite
    async with aiosqlite.connect(_TMP_DB_PATH) as conn:
        # Best-effort: only DELETE if table exists (auth plan creates it)
        try:
            await conn.execute("DELETE FROM users")
            await conn.commit()
        except Exception:
            pass
    yield


@pytest_asyncio.fixture
async def fresh_all_db():
    """Truncate all tables between isolation tests.

    Deletion order respects FK constraints (children before parents):
    financial_rows and extraction_log reference documents;
    documents references companies; companies and documents reference users.
    """
    import aiosqlite
    async with aiosqlite.connect(_TMP_DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys=ON")
        for table in ["financial_rows", "extraction_log", "management_team", "ebitda_adjustments", "report_intake", "report_orders", "reports", "documents", "companies", "users"]:
            try:
                await conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        try:
            await conn.commit()
        except Exception:
            pass
    yield
