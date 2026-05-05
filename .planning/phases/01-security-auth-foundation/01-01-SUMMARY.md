---
phase: 01-security-auth-foundation
plan: "01"
subsystem: test-infrastructure
tags: [phase-1, auth, test-scaffold, dependencies, tdd]
dependency_graph:
  requires: []
  provides:
    - pytest test infrastructure with isolated DB
    - auth and test dependency pins
    - SECRET_KEY provisioning
    - RED test stubs for all Phase 1 auth requirements
  affects:
    - backend/requirements.txt
    - .env.example
    - tests/
tech_stack:
  added:
    - pyjwt==2.12.1
    - pwdlib[argon2]==0.3.0
    - pytest==9.0.3
    - pytest-asyncio==1.3.0
    - httpx==0.28.1
  patterns:
    - ASGITransport AsyncClient fixture for FastAPI testing
    - tempfile.mkstemp DB isolation via module-level DB_PATH monkeypatch
    - pytest-asyncio auto mode for async test functions
key_files:
  created:
    - pytest.ini
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_security.py
    - tests/test_auth.py
    - .env (gitignored — SECRET_KEY generated, not committed)
  modified:
    - backend/requirements.txt (5 new pinned deps)
    - .env.example (SECRET_KEY placeholder added)
decisions:
  - Monkeypatched both db.DB_PATH and main.DB_PATH before app import to handle the value-copy import pattern in main.py
  - Used tempfile.mkstemp (not mktemp) for temp DB to avoid race conditions
  - Generated SECRET_KEY as 64-char hex (openssl rand -hex 32) per D-07 / RESEARCH Pitfall 7
metrics:
  duration: "358s"
  completed: "2026-05-05"
  tasks_completed: 5
  files_created: 7
  files_modified: 2
  tests_collected: 16
  tests_red: 14
  tests_trivially_passing: 2
---

# Phase 1 Plan 01: Test Scaffold & Dependency Setup Summary

**One-liner:** pytest infrastructure with ASGITransport AsyncClient, isolated temp-file SQLite DB, JWT/argon2 dep pins, and 16 RED test stubs covering all Phase 1 auth requirements.

## Objective

Established the test foundation that every subsequent Phase 1 plan executes against. No production code was changed — this plan installs dependencies, provisions secrets, and creates failing test stubs that will turn GREEN as Plans 02-04 implement the actual fixes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add auth + test dependencies | 6420109 | backend/requirements.txt |
| 2 | Generate SECRET_KEY | e82714d | .env (gitignored), .env.example |
| 3 | Create pytest.ini, tests/ package, conftest | 870679c | pytest.ini, tests/__init__.py, tests/conftest.py |
| 4 | Create test_security.py RED stubs (AUTH-01/02) | cc03b15 | tests/test_security.py |
| 5 | Create test_auth.py RED stubs (AUTH-04/05/06/08) | b76da70 | tests/test_auth.py |

## Dependency Versions Installed

| Package | Version | Purpose |
|---------|---------|---------|
| pyjwt | 2.12.1 | JWT signing/verification (Plans 03-04) |
| pwdlib[argon2] | 0.3.0 | Argon2id password hashing (Plan 03) |
| pytest | 9.0.3 | Test runner |
| pytest-asyncio | 1.3.0 | Async test support (asyncio_mode=auto) |
| httpx | 0.28.1 | ASGITransport AsyncClient for FastAPI |

## Test Infrastructure

### DB Isolation

The conftest uses `tempfile.mkstemp(suffix="_test.db")` to create a temp SQLite DB. Both `db.DB_PATH` and `main.DB_PATH` are patched before app import — this is necessary because `main.py` imports `DB_PATH` by value (not by reference), so both must be updated.

Temp DB path pattern: `/var/folders/.../tmp*_test.db`

### AsyncClient Setup

```python
AsyncClient(transport=ASGITransport(app=_main_module.app), base_url="http://test")
```

Uses httpx 0.28.1 ASGITransport pattern (not deprecated `app=` kwarg).

## RED Test Count

Total collected: **16 tests**
- 3 tests in `tests/test_security.py` (AUTH-01 x2, AUTH-02 x1)
- 13 tests in `tests/test_auth.py` (AUTH-04 x3, AUTH-05 x4, AUTH-06 x2, AUTH-08 x1, cross-cutting x3)

Currently failing: **14 tests** (expected RED state)
Trivially passing: **2 tests**
- `test_health_remains_public`: `/health` already exists and returns 200
- `test_protected_route_with_auth`: `/companies` currently requires no auth (will correctly fail after Plan 03 adds auth middleware)

## SECRET_KEY

- Generated via `openssl rand -hex 32` (64 hex chars = 256 bits)
- Written to `.env` (gitignored — NOT committed)
- Placeholder added to `.env.example` (committed)
- Verified loadable via python-dotenv with length >= 32

## Deviations from Plan

None — plan executed exactly as written.

The only implementation decision required was the module-level DB_PATH dual-patch (both `_db_module.DB_PATH` and `_main_module.DB_PATH`), which was explicitly specified in the plan's Task 3 action section.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan adds only test files and dependency configuration. No threat flags.

## Self-Check: PASSED

Files verified:
- backend/requirements.txt: contains all 5 new pinned deps
- pytest.ini: exists with asyncio_mode=auto
- tests/__init__.py: exists (empty)
- tests/conftest.py: 40 lines, ASGITransport pattern, both DB_PATH patches
- tests/test_security.py: 3 collectable tests
- tests/test_auth.py: 13 collectable tests
- .env.example: SECRET_KEY placeholder present
- .env: SECRET_KEY present (gitignored)

Commits verified:
- 6420109: chore(01-01): add auth + test dependencies to requirements.txt
- e82714d: chore(01-01): add SECRET_KEY to .env.example and generate .env
- 870679c: test(01-01): create pytest.ini, tests package, and conftest fixture
- cc03b15: test(01-01): add RED test stubs for AUTH-01 CORS and AUTH-02 path traversal
- b76da70: test(01-01): add RED test stubs for AUTH-04/05/06/08 and protected route enforcement
