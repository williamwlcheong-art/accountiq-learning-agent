---
phase: 1
slug: security-auth-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pytest.ini` — Wave 0 creates this |
| **Quick run command** | `cd /Users/William.Cheong/accountiq_learning && pytest tests/ -x -q` |
| **Full suite command** | `cd /Users/William.Cheong/accountiq_learning && pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green + manual browser XSS check
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-sec-01 | security-fixes | 1 | AUTH-01 | CORS wildcard | Cross-origin POST returns CORS error, not 200 | integration | `pytest tests/test_security.py::test_cors_restricted -x` | ❌ W0 | ⬜ pending |
| 1-sec-02 | security-fixes | 1 | AUTH-01 | — | Same-origin request to write endpoint succeeds | integration | `pytest tests/test_security.py::test_cors_allowed_origin -x` | ❌ W0 | ⬜ pending |
| 1-sec-03 | security-fixes | 1 | AUTH-02 | Path traversal | Upload with `../../evil.py` filename saves only basename | integration | `pytest tests/test_security.py::test_filename_traversal -x` | ❌ W0 | ⬜ pending |
| 1-sec-04 | security-fixes | 1 | AUTH-03 | XSS innerHTML | Narrative with `<script>` renders as text (no script exec) | manual | Browser DevTools check | N/A | ⬜ pending |
| 1-auth-01 | auth-backend | 2 | AUTH-04 | — | POST /auth/register with valid email+password returns 201 + cookie | integration | `pytest tests/test_auth.py::test_register_success -x` | ❌ W0 | ⬜ pending |
| 1-auth-02 | auth-backend | 2 | AUTH-04 | — | POST /auth/register with password < 8 chars returns 422 | integration | `pytest tests/test_auth.py::test_register_short_password -x` | ❌ W0 | ⬜ pending |
| 1-auth-03 | auth-backend | 2 | AUTH-04 | — | Duplicate email registration returns 409 | integration | `pytest tests/test_auth.py::test_register_duplicate -x` | ❌ W0 | ⬜ pending |
| 1-auth-04 | auth-backend | 2 | AUTH-05 | — | POST /auth/login sets httponly accountiq_session cookie | integration | `pytest tests/test_auth.py::test_login_sets_cookie -x` | ❌ W0 | ⬜ pending |
| 1-auth-05 | auth-backend | 2 | AUTH-05 | Session hijack | Cookie is httponly with 7-day max_age | integration | `pytest tests/test_auth.py::test_cookie_attributes -x` | ❌ W0 | ⬜ pending |
| 1-auth-06 | auth-backend | 2 | AUTH-05 | — | GET /auth/me with valid cookie returns user data | integration | `pytest tests/test_auth.py::test_me_authenticated -x` | ❌ W0 | ⬜ pending |
| 1-auth-07 | auth-backend | 2 | AUTH-05 | — | GET /auth/me without cookie returns 401 | integration | `pytest tests/test_auth.py::test_me_unauthenticated -x` | ❌ W0 | ⬜ pending |
| 1-auth-08 | auth-backend | 2 | AUTH-06 | — | POST /auth/logout clears the cookie | integration | `pytest tests/test_auth.py::test_logout -x` | ❌ W0 | ⬜ pending |
| 1-auth-09 | auth-backend | 2 | AUTH-06 | — | Protected route after logout returns 401 | integration | `pytest tests/test_auth.py::test_protected_after_logout -x` | ❌ W0 | ⬜ pending |
| 1-auth-10 | auth-backend | 2 | AUTH-08 | — | GET /auth/me returns id, email, created_at | integration | `pytest tests/test_auth.py::test_me_returns_user_fields -x` | ❌ W0 | ⬜ pending |
| 1-auth-11 | route-protection | 2 | — | Unauthenticated access | Unauthenticated request to /companies returns 401 | integration | `pytest tests/test_auth.py::test_protected_route_no_auth -x` | ❌ W0 | ⬜ pending |
| 1-auth-12 | route-protection | 2 | — | — | Authenticated request to /companies returns 200 | integration | `pytest tests/test_auth.py::test_protected_route_with_auth -x` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `pytest.ini` — configure `asyncio_mode = "auto"` for pytest-asyncio
- [ ] `tests/__init__.py` — empty, makes tests a package
- [ ] `tests/conftest.py` — test app with in-memory SQLite DB fixture
- [ ] `tests/test_auth.py` — stubs for AUTH-04/05/06/08
- [ ] `tests/test_security.py` — stubs for AUTH-01/02
- [ ] Install: `pip install pytest==9.0.3 pytest-asyncio==1.3.0 httpx==0.28.1`
- [ ] Install: `pip install pyjwt==2.12.1 "pwdlib[argon2]==0.3.0"`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Narrative text with `<script>` renders as plain text in modal | AUTH-03 | DOM rendering cannot be verified via API tests | Open browser, navigate to a document with AI narrative, open modal. In DevTools inspect `#narrative-body` — confirm children are `<p>` elements with `.textContent` (no child elements). Paste `<script>alert(1)</script>` as narrative content (via DB or dev mode) and confirm no alert fires. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
