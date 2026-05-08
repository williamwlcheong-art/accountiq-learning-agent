---
phase: 3
slug: business-profile-intake
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio |
| **Config file** | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| **Quick run command** | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && pytest tests/test_profile.py -x -q` |
| **Full suite command** | `cd /Users/William.Cheong/accountiq_learning && source venv/bin/activate && pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_profile.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PROF-01, PROF-02 | T-03-01 | 404 (not 403) for unowned company on profile save | integration | `pytest tests/test_profile.py::test_save_industry -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | PROF-01 | T-03-01 | Ownership enforcement: `WHERE id=? AND user_id=?` | integration | `pytest tests/test_profile.py::test_profile_ownership_403 -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | PROF-02 | — | Description >= 50 chars saved and returned | integration | `pytest tests/test_profile.py::test_save_description -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | PROF-03 | T-03-01 | Add member + list returns it; unowned 404 | integration | `pytest tests/test_profile.py::test_management_team_crud -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | PROF-03 | T-03-01 | DELETE member; re-fetch returns 404 | integration | `pytest tests/test_profile.py::test_management_team_delete -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | PROF-04 | T-03-01 | Add adjustment + list returns it; amount negative ok | integration | `pytest tests/test_profile.py::test_ebitda_adjustments_crud -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 2 | PROF-04 | — | profile-status ebitda_complete=true after first adjustment | integration | `pytest tests/test_profile.py::test_profile_status_gate -x` | ❌ W0 | ⬜ pending |
| 03-02-05 | 02 | 2 | PROF-04 (D-06) | — | profile-status can_generate=false when sector null or no adjustments | integration | `pytest tests/test_profile.py::test_profile_status_blocked -x` | ❌ W0 | ⬜ pending |
| 03-02-06 | 02 | 2 | PROF-04 (D-05) | — | reported_ebitda correct in profile-status when financial_rows exist | integration | `pytest tests/test_profile.py::test_ebitda_bridge_calculation -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_profile.py` — stubs for PROF-01 through PROF-04 and D-05/D-06 logic (all rows above marked "Wave 0")
- [ ] `tests/conftest.py` — update `fresh_all_db` fixture to include `management_team` and `ebitda_adjustments` in deletion list (before `companies`, to respect FK ordering)

*Wave 0 must be written in the first plan's tasks before any backend code.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Edit Profile accordion opens and shows pre-populated fields | PROF-01, PROF-02 | Requires browser DOM interaction | Open Companies tab → click "Edit Profile" → verify sector dropdown pre-selected and description pre-populated |
| Profile completion badge updates after saving each section | PROF-01–04 | Requires browser reload verification | Save each section → reload page → verify badge count increases |
| EBITDA bridge updates after add/edit/remove add-back | PROF-04 | Requires browser DOM interaction | Add adjustment → verify bridge recalculates; remove → verify bridge updates |
| Legacy free-text sector value falls back gracefully | PROF-01 | Requires legacy DB state | Set company.sector to "Aviation" → open accordion → verify dropdown shows empty (no selection) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
