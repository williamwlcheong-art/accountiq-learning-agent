---
phase: 2
slug: multi-user-data-isolation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 + httpx 0.28.1 |
| **Config file** | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| **Quick run command** | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && python -m pytest tests/test_isolation.py -x -q` |
| **Full suite command** | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_isolation.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| schema-migration | 01 | 1 | AUTH-07, DATA-01 | T-2-01 | user_id column present; NULL rows invisible | integration | `pytest tests/test_isolation.py::test_null_user_rows_invisible -x` | ❌ W0 | ⬜ pending |
| route-filter-companies | 02 | 2 | AUTH-07 | T-2-02 | GET /companies returns only authed user's companies | integration | `pytest tests/test_isolation.py::test_cross_user_company_isolation -x` | ❌ W0 | ⬜ pending |
| route-filter-documents | 02 | 2 | AUTH-07 | T-2-02 | GET /documents returns only authed user's documents | integration | `pytest tests/test_isolation.py::test_cross_user_document_isolation -x` | ❌ W0 | ⬜ pending |
| route-filter-idor | 02 | 2 | AUTH-07 | T-2-03 | GET /companies/{id} returns 404 for cross-user IDs | integration | `pytest tests/test_isolation.py::test_cross_user_company_isolation -x` | ❌ W0 | ⬜ pending |
| route-filter-analytics | 02 | 2 | AUTH-07 | T-2-04 | /analytics/overview and /analytics/confidence scoped to user | integration | `pytest tests/test_isolation.py::test_list_endpoints_scoped -x` | ❌ W0 | ⬜ pending |
| smoke-test | 03 | 3 | AUTH-07 | T-2-02 | Cross-user IDOR returns 404 in full end-to-end flow | integration | `pytest tests/test_isolation.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_isolation.py` — cross-user isolation tests for AUTH-07 and DATA-01
- [ ] `tests/conftest.py` — extend with `fresh_all_db` fixture (clears users, companies, documents, financial_rows, extraction_log)

*Existing test infrastructure (pytest-asyncio, httpx AsyncClient, ASGITransport) is already in place — only new test file and fixture extension are needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SQLite UNIQUE(name, exchange, user_id) constraint allows two users to create identical company name | D-04 | Requires verifying schema in sqlite_master | Run `sqlite3 data/accountiq_learning.db ".schema companies"` and confirm UNIQUE includes user_id |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
