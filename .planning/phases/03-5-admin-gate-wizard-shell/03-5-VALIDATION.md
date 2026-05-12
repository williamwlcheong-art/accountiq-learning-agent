---
phase: 3.5
slug: admin-gate-wizard-shell
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 3.5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio |
| **Config file** | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| **Quick run command** | `pytest tests/test_admin_gate.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_admin_gate.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-5-01-01 | 01 | 1 | AUTH-09 | T-03-5-01 | OWNER_EMAIL gets is_admin=1 on registration | unit | `pytest tests/test_admin_gate.py::test_owner_email_gets_admin -x` | ❌ W0 | ⬜ pending |
| 03-5-01-02 | 01 | 1 | AUTH-09 | — | Regular user gets is_admin=0 | unit | `pytest tests/test_admin_gate.py::test_regular_user_not_admin -x` | ❌ W0 | ⬜ pending |
| 03-5-01-03 | 01 | 1 | AUTH-09 | — | /auth/me returns is_admin field | unit | `pytest tests/test_admin_gate.py::test_me_returns_is_admin -x` | ❌ W0 | ⬜ pending |
| 03-5-02-01 | 02 | 2 | AUTH-09 | T-03-5-01 | Non-admin GET /companies returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_companies_403 -x` | ❌ W0 | ⬜ pending |
| 03-5-02-02 | 02 | 2 | AUTH-09 | T-03-5-01 | Non-admin GET /financials/{id} returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_financials_403 -x` | ❌ W0 | ⬜ pending |
| 03-5-02-03 | 02 | 2 | AUTH-09 | T-03-5-01 | Non-admin GET /patterns returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_patterns_403 -x` | ❌ W0 | ⬜ pending |
| 03-5-02-04 | 02 | 2 | AUTH-09 | T-03-5-01 | Non-admin GET /settings returns 403 | integration | `pytest tests/test_admin_gate.py::test_regular_user_settings_403 -x` | ❌ W0 | ⬜ pending |
| 03-5-02-05 | 02 | 2 | AUTH-09 | T-03-5-01 | Admin passes 403 gate on /companies | integration | `pytest tests/test_admin_gate.py::test_admin_user_companies_200 -x` | ❌ W0 | ⬜ pending |
| 03-5-02-06 | 02 | 2 | AUTH-09 | — | Unauthenticated returns 401 (not 403) | integration | `pytest tests/test_admin_gate.py::test_unauthenticated_returns_401_not_403 -x` | ❌ W0 | ⬜ pending |
| 03-5-03-01 | 03 | 3 | UX-01 | T-03-5-02 | /wizard/upload creates company + document | integration | `pytest tests/test_admin_gate.py::test_wizard_upload_creates_company_and_document -x` | ❌ W0 | ⬜ pending |
| 03-5-03-02 | 03 | 3 | UX-01 | T-03-5-02 | /wizard/upload requires auth (401 if no cookie) | integration | `pytest tests/test_admin_gate.py::test_wizard_upload_requires_auth -x` | ❌ W0 | ⬜ pending |
| 03-5-03-03 | 03 | 3 | UX-01 | — | /wizard/upload is NOT admin-gated (non-admin 201) | integration | `pytest tests/test_admin_gate.py::test_wizard_upload_not_admin_gated -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_admin_gate.py` — 12 test stubs for AUTH-09 and UX-01 (all rows above marked "Wave 0")
- [ ] `tests/conftest.py` update — add `_register_admin(client, fresh_db)` helper that sets `OWNER_EMAIL` env var before calling register

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin UI shows full tab navigation after login | UX-01 | Requires browser DOM verification | Log in as admin user → verify Companies, Documents, Patterns, Financials, Settings tabs are visible |
| Regular user sees wizard (not tabs) after login | UX-01 | Requires browser DOM verification | Log in as non-admin → verify wizard step 1 renders; no tab nav visible |
| Wizard step 1 → step 2 → step 3 flow | UX-01 | Requires browser DOM interaction | Upload a PDF with a business name → confirm step 2 appears with 5 report type cards → select one → confirm step 3 shows "we'll email you" message |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
