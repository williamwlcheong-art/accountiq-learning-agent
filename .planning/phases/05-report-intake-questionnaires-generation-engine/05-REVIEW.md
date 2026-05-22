---
phase: 05-report-intake-questionnaires-generation-engine
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/db.py
  - backend/main.py
  - backend/report_email.py
  - backend/valuation.py
  - frontend/index.html
  - backend/report_prompts.py
  - backend/email.py
  - tests/conftest.py
findings:
  critical: 3
  warning: 6
  info: 3
  total: 12
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-05-22T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 5 delivers report generation (5 report types), intake questionnaires, valuation algorithm, DSCR computations, email notification, and frontend wizard. The core algorithmic logic in `valuation.py` and `report_prompts.py` is solid and well-structured. The primary defects concentrate in two areas: a blocking I/O call in `report_email.py` that will deadlock the async event loop under real SMTP load, and a persistent XSS sink in the frontend intake form builder. Several secondary issues affect data correctness and reliability.

---

## Critical Issues

### CR-01: Blocking SMTP call inside async function blocks event loop

**File:** `backend/report_email.py:126-137`

**Issue:** `send_report_ready_email` is declared `async def` but performs synchronous blocking I/O (`smtplib.SMTP`, `smtplib.SMTP_SSL`, `server.starttls()`, `server.login()`, `server.sendmail()`) directly on the async event loop without wrapping in `run_in_executor`. An SMTP connection to an external server can block for seconds to minutes. During that time the entire FastAPI event loop is frozen — no other requests can be served and the background report-generation task that calls this function is stalled.

The companion file `backend/email.py` (the original implementation) correctly wraps `_send_smtp` in `loop.run_in_executor(None, _send_smtp, ...)` but `report_email.py` (the runtime alias used by `main.py`) does not.

**Fix:**
```python
import asyncio

async def send_report_ready_email(
    user_email: str,
    user_name: str,
    report_type: str,
    report_id: int,
) -> None:
    # ... env var loading and guard unchanged ...

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            _send_smtp_blocking,          # extract blocking logic to a sync helper
            smtp_host, smtp_port, smtp_user, smtp_password,
            from_email, user_email, subject, text_body, html_body,
        )
    except Exception as exc:
        logger.error("Failed to send report-ready email to %s: %s", user_email, exc)
```
Move the `smtplib` calls into a private synchronous helper function (same pattern as `email.py`'s `_send_smtp`).

---

### CR-02: XSS via innerHTML in valuation intake form builder

**File:** `frontend/index.html:2324-2368` (and lines 2371–2441)

**Issue:** `_buildIntakeForms()` constructs HTML strings by concatenating values from the `valCategories` / `WIZARD_REPORT_TYPES` arrays and injects them with `innerHTML`. The string values (`cat.name`, `qn.text`, `qn.opts[idx]`) are currently authored as JavaScript literals, but this is one refactor away from being data-driven (e.g., fetched from the server). More critically, the *option text* values contain characters like `>`, `≤`, `%`, `–` which are already encoded inconsistently. The pattern of building HTML via string concatenation and assigning to `innerHTML` violates the project's explicit security rule ("Always use `.textContent` or `.createTextNode()` for user-influenced text") and creates a maintenance trap where any future addition of a user-supplied label would instantly become an XSS vector.

The specific line:
```javascript
valHtml += '<summary style="...">' + cat.name + '</summary>';
valHtml += '<p ...><strong>Q' + qn.q + '.</strong> ' + qn.text + '</p>';
valHtml += '<label ...> ' + opt + ' (' + score + ')</label>';
```
...then at line 2368:
```javascript
document.getElementById('intake-valuation_advisory').innerHTML = valHtml;
```

**Fix:** Build the intake forms using `document.createElement` and `.textContent` assignments (as the rest of the codebase does). For example:
```javascript
const summary = document.createElement('summary');
summary.textContent = cat.name;
details.appendChild(summary);

const qText = document.createElement('p');
qText.appendChild(document.createTextNode(`Q${qn.q}. ${qn.text}`));
```
If retaining string building for performance, use a sanitisation function or switch to a `<template>` element approach before assigning to `innerHTML`.

---

### CR-03: `company_id` type not validated — SQL injection via non-integer JSON value

**File:** `backend/main.py:1029-1046`

**Issue:** In `wizard_report_generate`, `company_id` is extracted from the raw JSON body via `body.get("company_id")` with no type check. If the caller sends `{"company_id": "1 OR 1=1", ...}` the value is passed to the parameterised SQLite query as a string, which SQLite will coerce to integer 1 (not an injection vector for the query itself). However, the truthiness guard `if not company_id:` accepts `True`, `"abc"`, `[]`, and any other truthy non-integer value, allowing the value `True` (JSON boolean) to satisfy the guard and reach the DB as the integer `1` — matching any row with `id=1` regardless of the intended company. The correct fix is to assert the type.

```python
company_id = body.get("company_id")
if not isinstance(company_id, int) or company_id <= 0:
    raise HTTPException(400, "company_id must be a positive integer")
```

---

## Warnings

### WR-01: `label_patterns` stat referenced in frontend but not returned by API

**File:** `frontend/index.html:596` / `backend/main.py:834`

**Issue:** The dashboard stat card `#stat-patterns` displays `ov.label_patterns` (line 596), but `/analytics/overview` intentionally omits `label_patterns` from its response (see the comment at `main.py:832`). The result is `ov.label_patterns` is `undefined`, and `element.textContent = undefined` renders the literal string `"undefined"` to the user permanently in the dashboard stat card.

**Fix (Option A — display N/A):** Remove or blank out the stat card if label_patterns count is not provided:
```javascript
document.getElementById('stat-patterns').textContent =
    ov.label_patterns != null ? ov.label_patterns.toLocaleString() : '—';
```
**Fix (Option B — include count):** Add a global pattern count to the analytics response:
```python
async with db.execute("SELECT COUNT(*) as n FROM label_patterns") as cur:
    patterns = (await cur.fetchone())["n"]
return { ..., "label_patterns": patterns }
```

---

### WR-02: `event.currentTarget` is `null` when functions are called from `onclick` attributes

**File:** `frontend/index.html:2499, 2581`

**Issue:** `wizardSubmitGenerate()` and `wizardRetry()` are called via `onclick="wizardSubmitGenerate()"` HTML attributes (lines 532, 549). Inside these functions, `event.currentTarget` is used to grab the button reference for disabling. However, when a function is invoked from an `onclick` attribute (not an `addEventListener`), `event` is the global `Event` object but `event.currentTarget` is `null` because there is no listener registered on a specific element. This means `btn` is `null`, the `btn.disabled = true` line throws a TypeError, and the Generate button is never disabled — allowing double-clicks to queue multiple simultaneous report generation jobs.

Line 2225 has a partial workaround (`|| document.querySelector(...)`) but lines 2499 and 2581 do not.

**Fix:**
```javascript
// In HTML:
<button onclick="wizardSubmitGenerate(this)">Generate Report →</button>
<button onclick="wizardRetry(this)">Retry ↻</button>

// In JS:
async function wizardSubmitGenerate(btn) {
    // btn is the button element directly
    ...
}
```
Or use `addEventListener` in `showWizard()` / `_initWizardDropZone()` pattern already established in the file.

---

### WR-03: `compute_dcf` called with `years=0` causes `IndexError`

**File:** `backend/valuation.py:198`

**Issue:** If `intake_answers.get("forecast_years", 5)` is sent as `0` (the frontend has no `min` attribute on that field), `compute_dcf` is called with `years=0`. The loop `for yr in range(1, 0+1)` produces zero iterations, leaving `yearly` empty. Line 198 then executes `final_fcff = yearly[-1]["fcff"]` on an empty list, raising `IndexError`. This exception propagates to `compute_valuation`, which is called from `_run_valuation_algorithm`, which catches all exceptions and returns a degraded result — but the report is silently generated with `normalised_ebitda: None`, producing a broken valuation report rather than a rejected request.

**Fix:** Add input validation in `compute_dcf`:
```python
if years < 1:
    raise ValueError(f"forecast_years must be >= 1, got {years}")
```
And add a frontend `min="1"` attribute on the forecast_years input.

---

### WR-04: DSCR computed as `None` silently when `ebitda` key absent — misleads Claude

**File:** `backend/report_prompts.py:162-169`

**Issue:** `compute_bank_credit_figures` builds `years` from `ebitda_vals.keys()`. If no `ebitda` row was extracted (e.g., the company's statements use `operating_profit` instead), `years` is an empty list, `dscr_table` is empty, and `trend_table` is empty. The function returns successfully with empty dicts. Claude then receives `DSCR by year: {}` and must either invent values or produce a broken dscr_analysis section. Since the validation at `main.py:1274` only checks section key presence (not content), this silently results in a report with empty or hallucinated financial tables.

**Fix:** Add a fallback that tries `net_profit + depreciation_amortisation` when `ebitda` is missing (mirroring the pattern in `main.py:1379-1382`), or raise a clear error that surfaces as `error_message` on the report:
```python
if not ebitda_vals:
    # Try fallback: net_profit as proxy for EBITDA
    ebitda_vals = _get_values(financial_rows, "net_profit")
    if not ebitda_vals:
        return {"dscr_table": {}, "trend_table": {}, "sensitivity": {},
                "annual_principal": annual_principal,
                "warning": "No EBITDA data found — DSCR figures may be incomplete"}
```

---

### WR-05: `_migrate_db` `BEGIN`/`COMMIT` pattern can leave DB in inconsistent state

**File:** `backend/db.py:164-190`

**Issue:** `_migrate_db` calls `conn.execute("BEGIN")` and `conn.execute("COMMIT")`/`conn.execute("ROLLBACK")` manually. The `sqlite3.Connection` object uses an implicit transaction system — calling `conn.execute("BEGIN")` while a transaction is already open (which `executescript()` may have started) raises `OperationalError: cannot start a transaction within a transaction`. If `executescript(SCHEMA)` in `init_db` commits its implicit transaction cleanly, then `BEGIN` works, but this depends on the exact state after `executescript`. If the `conn.execute("ROLLBACK")` path is taken (due to an exception during the table rename), the already-committed ALTER TABLE changes from earlier in `_migrate_db` (adding `user_id`, `description`, `is_admin` columns) remain committed while the UNIQUE constraint rebuild is rolled back — leaving the schema in a partially-migrated state that will fail the migration check on next startup.

**Fix:** Move the ALTER TABLE statements and the table-rename block into a single explicit transaction using `with conn:` context manager, or separate the migration into idempotent steps that are each individually wrapped in their own savepoint.

---

### WR-06: Unchecked `response.content[0]` access in `_call_claude_for_report`

**File:** `backend/main.py:1455`

**Issue:** `raw_text = response.content[0].text if response.content else ""` — the guard checks `if response.content` (truthy list) but does not check `if response.content[0].type == "text"`. The Claude API can return a `tool_use` block or `thinking` block as `content[0]` when stop_reason is `tool_use` or when extended thinking is enabled. Accessing `.text` on a non-text block raises `AttributeError`, which propagates to mark the report as failed with an obscure error message.

**Fix:**
```python
raw_text = ""
for block in (response.content or []):
    if hasattr(block, "text"):
        raw_text = block.text
        break
```

---

## Info

### IN-01: Dead constant `_THREE_OPTION_QUESTIONS` never used in computation

**File:** `backend/valuation.py:35`

**Issue:** `_THREE_OPTION_QUESTIONS = {6, 8, 9}` is defined but never referenced in `compute_ev_ebitda_multiple` or any other function. The questionnaire correctly accepts scores 1, 3, or 5 for three-option questions (validated by `1 <= score <= 5`), but the intended special handling (e.g., mapping or weight adjustment) was never wired up. The frontend sends values `[1, 3, 5]` for three-option questions, which pass the `1–5` range check but the constant serves no purpose.

Additionally, the frontend marks Q7 (Fixed assets as % of sales) as `threeOpt: true`, but Q7 is absent from the backend `_THREE_OPTION_QUESTIONS = {6, 8, 9}` set. This is a documentation inconsistency if the constant ever gets used.

**Fix:** Either remove the constant or wire it into the validation/scoring logic to explicitly document the intended behaviour.

---

### IN-02: Commented-out dead import in `main.py`

**File:** `backend/main.py:54-58`

**Issue:** Lines 54–58 contain a commented-out import of `send_report_ready_email` from `email` with an explanatory block comment. While the comment is informative, the dead code increases cognitive load when reading the import block. The decision has been codified in `D-impl-01`; the comment itself could be a one-liner with a reference.

**Fix:** Replace the multi-line commented block with a single-line comment:
```python
# report_email.py is the runtime alias — see D-impl-01 in 05-01-SUMMARY.md
```

---

### IN-03: `stat-patterns` stat card visible but permanently shows "undefined"

**File:** `frontend/index.html:239`

**Issue:** (Linked to WR-01.) The "Label Patterns" stat card is visible in the dashboard for admin users but always displays `undefined` because `/analytics/overview` does not return `label_patterns`. This degrades trust in the dashboard's data accuracy. Removing the card or fixing the data source (WR-01) resolves this.

**Fix:** See WR-01 for remediation options.

---

_Reviewed: 2026-05-22T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
