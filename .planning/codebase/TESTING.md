---
last_mapped: 2026-05-04
---

# Testing

## Current State

**No tests exist.** There are no test files anywhere in the codebase:
- No `test_*.py` or `*_test.py` files
- No `conftest.py`
- No `pytest.ini` or `pyproject.toml`
- No test runner configuration
- No CI pipeline

The project is entirely untested at this time.

## Recommended Approach (when tests are added)

Given the stack (Python/FastAPI/aiosqlite), the natural fit is:

**Framework:** `pytest` + `pytest-asyncio` for async route testing

**FastAPI testing:** `httpx.AsyncClient` with `asgi_transport` (recommended over deprecated `TestClient` for async apps):

```python
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
```

**Database:** Use an in-memory SQLite or temp-file DB per test — override `DB_PATH` or use FastAPI dependency overrides for `get_db`.

**Key areas to test when adding tests:**

| Area | What to test |
|------|-------------|
| `db.py` | Schema creation, `record_patterns` upsert, `get_pattern_library` ordering |
| `rule_extractor.py` | `_norm`, `_detect_periods`, `_extract_numbers`, `rule_based_extract` with fixture PDFs |
| `ingestion.py` | `extract_pdf_text`, `_build_pattern_hints`, `persist_extraction` |
| API routes | CRUD for companies/documents, upload endpoint, status polling |
| Settings | API key save/mask behavior |

**Test data:** The `data/pdfs/` directory already has 2 real PDFs that can serve as fixtures.

## Install Commands (when ready)

```bash
pip install pytest pytest-asyncio httpx
```
