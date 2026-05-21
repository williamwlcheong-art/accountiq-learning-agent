---
phase: 05-report-intake-questionnaires-generation-engine
plan: "01"
subsystem: database-schema + api-endpoints + background-task
tags:
  - schema-migration
  - sqlite
  - fastapi-routes
  - background-tasks
  - report-generation
dependency_graph:
  requires:
    - 03-business-profile-intake   # companies, management_team, ebitda_adjustments tables
    - 04-extraction-quality        # financial_rows table
  provides:
    - reports table (job state machine: queued/generating/done/failed)
    - report_intake table (FK to reports; stores JSON intake answers)
    - POST /wizard/report/generate (non-admin; queues background task)
    - GET /wizard/report/{id}/status (ownership-gated status poll)
    - POST /wizard/report/{id}/retry (failed-only reset + requeue)
    - _generate_report background task (full queued→generating→done/failed state machine)
    - send_report_ready_email() helper in report_email.py
  affects:
    - 05-02-PLAN.md  # intake questionnaire routes depend on reports/report_intake tables
    - 05-03-PLAN.md  # valuation algorithm called by _generate_report
    - 05-04-PLAN.md  # Claude narrative generation called by _generate_report
tech_stack:
  added:
    - smtplib (STARTTLS/SSL) for report-ready email notification
  patterns:
    - CREATE TABLE IF NOT EXISTS + try/except index creation in _migrate_db()
    - aiosqlite background task opens its own connection (same as _run_ingestion)
    - Request injection for JSON body parsing (avoids FastAPI body model limitation)
    - report_type allowlist via frozenset(_VALID_REPORT_TYPES)
    - Ownership enforcement via WHERE id=? AND user_id=? on all report queries
key_files:
  created:
    - backend/report_email.py
  modified:
    - backend/db.py
    - backend/main.py
    - tests/conftest.py
decisions:
  - D-04 (from 05-CONTEXT): Phase 5 bypasses payment gate — wizard path is non-admin; Phase 6 inserts the gate
  - D-05 (from 05-CONTEXT): report_type validated against frozenset allowlist of 5 types
  - D-06 (from 05-CONTEXT): manual retry only — POST /wizard/report/{id}/retry; status guard prevents double-queuing
  - D-impl-01: report_email.py named to avoid shadowing stdlib email module
  - D-impl-02: SMTP exceptions swallowed in send_report_ready_email() — email failure must not mark report as failed
  - D-impl-03: _generate_report loads its own aiosqlite connection (background tasks run outside FastAPI request context)
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-21"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 4
  commits: 3
---

# Phase 5 Plan 1: DB Tables + Job State Machine + Wizard API Routes Summary

**One-liner:** SQLite schema extended with `reports` and `report_intake` job tables, three wizard API endpoints added (generate/status/retry) with ownership enforcement, and a full `_generate_report` background task implementing the queued→generating→done/failed state machine ready for Plan 04 to wire in real Claude generation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add reports and report_intake tables to _migrate_db() in db.py | d751938 | backend/db.py, tests/conftest.py |
| 1b | Add report_email.py with send_report_ready_email() | 97602ce | backend/report_email.py |
| 2 | Add wizard report generation routes and background task to main.py | 185230b | backend/main.py |

## Changes Made

### Task 1: backend/db.py — _migrate_db() extended

Two new tables added immediately before the final `conn.commit()`:

**reports table** — job state machine:
```sql
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    user_id         INTEGER,
    report_type     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    content         TEXT,
    error_message   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
)
```

**report_intake table** — intake answers JSON blob:
```sql
CREATE TABLE IF NOT EXISTS report_intake (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    answers     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
)
```

Four indexes added (try/except wrapped for idempotency): `idx_reports_user`, `idx_reports_company`, `idx_reports_status`, `idx_intake_report`.

`tests/conftest.py` extended to truncate `report_intake` and `reports` in FK order before `documents`/`companies` in the `fresh_all_db` fixture.

### Task 1b: backend/report_email.py — created

`send_report_ready_email(user_email, user_name, report_type, report_id)` async function:
- Reads `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`, `APP_BASE_URL` from environment
- Silently skips when SMTP not configured (dev mode)
- Selects STARTTLS (port 587) or SSL (port 465) based on `SMTP_PORT`
- SMTP exceptions logged and swallowed — email failure must not affect report status

### Task 2: backend/main.py — 3 wizard routes + background task

**`POST /wizard/report/generate`** (status 201, non-admin):
- Parses JSON body via `Request.json()` (avoids FastAPI body model limitation)
- Validates `report_type` against `_VALID_REPORT_TYPES` frozenset (5 types)
- Verifies company ownership with `WHERE id=? AND user_id=?`
- Inserts `reports` row (status=queued) + `report_intake` row (JSON answers)
- Queues `_generate_report` via `background_tasks.add_task()`
- Returns `{"report_id": int, "status": "queued"}`

**`GET /wizard/report/{report_id}/status`** (non-admin):
- Ownership-gated: `WHERE id=? AND user_id=?`
- Returns `{id, report_type, status, error_message, created_at, completed_at}`
- 404 if not found or not owned by caller

**`POST /wizard/report/{report_id}/retry`** (non-admin):
- Ownership-gated + status guard: 409 if status != 'failed'
- Resets to `status='queued'`, clears `error_message` and `completed_at`
- Re-fetches original intake answers from `report_intake`
- Re-queues `_generate_report`
- Returns `{"report_id": int, "status": "queued"}`

**`async def _generate_report(...)`** background task:
- Opens its own `aiosqlite` connection (runs outside request context)
- State machine: `queued → generating → done` (or `→ failed` on exception)
- Sets `completed_at=datetime('now')` on done; stores Claude JSON in `content`
- Loads company profile, management team, EBITDA adjustments, financial rows
- Runs Python valuation algorithm for `report_type='valuation'` (graceful stub if valuation.py not present)
- Calls `_build_report_prompt()` + `_call_claude_for_report()` for narrative generation
- Calls `send_report_ready_email()` on completion

## Deviations from Plan

**main.py route consolidation:** The prior session left two conflicting `@app.post("/wizard/report/generate")` definitions — one calling a `NotImplementedError` placeholder and a second attempting `app.routes = [...]` (invalid in current FastAPI versions). Fixed by replacing both with a single clean implementation using `Request` injection and adding `Request` to the top-level FastAPI import.

## Known Stubs

- `_run_valuation_algorithm()` falls back to stub dict if `valuation.py` is absent — Plan 05-03 creates the real implementation
- `_build_report_prompt()` and `_call_claude_for_report()` are present and functional but the prompt templates will be refined in Plan 05-04

## Threat Surface

| Endpoint | Mitigation |
|----------|-----------|
| POST /wizard/report/generate | report_type allowlist; company ownership verified before insert |
| GET /wizard/report/{id}/status | WHERE user_id=? enforces ownership; no content returned |
| POST /wizard/report/{id}/retry | Ownership gate + status='failed' guard prevents double-queuing |
| intake_answers JSON | Stored as opaque string; not executed; Claude prompt builder serialises safely |

## Self-Check: PASSED

- [x] `CREATE TABLE IF NOT EXISTS reports` present in backend/db.py — d751938
- [x] `CREATE TABLE IF NOT EXISTS report_intake` present in backend/db.py — d751938
- [x] `idx_reports_user` index present in backend/db.py — d751938
- [x] `tests/conftest.py` updated with report_intake + reports in FK order — d751938
- [x] `backend/report_email.py` created with send_report_ready_email() — 97602ce
- [x] `POST /wizard/report/generate` route registered — 185230b
- [x] `GET /wizard/report/{report_id}/status` route registered — 185230b
- [x] `POST /wizard/report/{report_id}/retry` route registered — 185230b
- [x] `_generate_report` background task: queued→generating→done flow with completed_at — 185230b
- [x] `background_tasks.add_task(_generate_report, ...)` called in both generate + retry routes — 185230b
- [x] DB initialises without error: `python -c "from db import init_db; init_db()"` — verified
- [x] App imports cleanly: 3 wizard/report routes in `app.routes` — verified
- [x] 66 existing tests pass, 1 skipped, 0 failures — verified
