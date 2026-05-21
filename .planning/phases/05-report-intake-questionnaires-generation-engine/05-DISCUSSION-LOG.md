# Phase 5: Report Intake Questionnaires + Generation Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 5-Report-Intake-Questionnaires-Generation-Engine
**Areas discussed:** Wizard flow, Generation trigger vs payment state, Valuation algorithm scope, Report format + email scope

---

## Wizard flow

### Where does the intake questionnaire live?

| Option | Description | Selected |
|--------|-------------|----------|
| Step 2b — between type selection and confirmation | Keeps 3 named steps; intake is an inline sub-step shown after report type is selected | ✓ |
| Step 3 becomes intake, add Step 4 for confirmation | Renames Step 3 to Intake and adds Step 4 Confirmation; step counter becomes "4 of 4" | |
| Full-page intake replaces Step 3 entirely | Intake is Step 3; submitting shows a success banner inline — no separate confirmation | |

**User's choice:** Step 2b — between type selection and confirmation

---

### How does the intake form render?

| Option | Description | Selected |
|--------|-------------|----------|
| Single scrollable card per report type | All questions in one card; user scrolls, fills, clicks Generate; JS show/hides one div per type | ✓ |
| Stepped sub-questions — one question at a time | Each question is its own sub-step with Next/Back buttons | |
| Collapsible sections within the card | Questions grouped into 2–3 collapsible sections; reuses accordion pattern from Phase 3 | |

**User's choice:** Single scrollable card

---

### Incomplete business profile handling

| Option | Description | Selected |
|--------|-------------|----------|
| Amber warning banner — allow generation to proceed | Show "Some profile data is incomplete" warning but don't block submission | ✓ |
| Block generation with a message and link to profile | Error card if industry or EBITDA add-backs are missing; user cannot proceed | |
| Silently use whatever data is available | No validation at wizard; Claude uses whatever is in the DB | |

**User's choice:** Warning banner, no block

---

## Generation trigger vs payment state

### What happens when user submits intake in Phase 5?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip pending_payment — intake goes straight to queued | Phase 5 bypasses the state entirely; Phase 6 inserts the gate without touching generation | ✓ |
| Build full state machine now — pending_payment, generation deferred to Phase 6 | Accurate model but can't test generation until Phase 6 | |
| Feature flag — SKIP_PAYMENT=true in .env | Env var bypass for dev; Phase 6 sets it false in prod | |

**User's choice:** Skip pending_payment — go straight to queued

---

### DB schema scope for Phase 5

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal schema — extend in Phase 6 | reports + report_intake tables without payment columns; Phase 6 adds via ALTER TABLE | ✓ |
| Full schema now — payment columns with NULL allowed | Add stripe_payment_intent_id etc. now as nullable | |
| Claude's discretion | Standard async job queue schema | |

**User's choice:** Minimal schema

---

### Failed report retry approach

| Option | Description | Selected |
|--------|-------------|----------|
| Manual retry — Retry button in wizard, resets to queued | User-initiated; no automatic backoff | ✓ |
| Automatic exponential backoff — 3 attempts before marking failed | Retries on 429/529; marks failed after exhausting retries | |
| Both — automatic backoff + manual retry for hard failures | Two-layer resilience | |

**User's choice:** Manual retry only

---

## Valuation algorithm scope

### How is EV/EBITDA comparable range determined?

**User's response (free-text):** "I would like to run a questionnaire to help us establish what this valuation would be. we need to determine if the sector or the business requires a DCF or a multiples approach for valuation assessment."

**Interpretation:** The intake should start with diagnostic questions that determine the methodology, rather than assuming the user knows upfront.

---

### How does the Valuation Advisory intake determine methodology?

| Option | Description | Selected |
|--------|-------------|----------|
| Guided diagnostic questions — system recommends DCF/multiples/both | 3–4 business characteristic questions → recommendation → user confirms or overrides | ✓ |
| User picks methodology upfront | First question is "Which method?" — user expected to know | |
| Always run both — no selection | Collect all inputs, run both algorithms, Claude presents both | |

**User's choice:** Guided diagnostic questions

---

### What does the Python algorithm compute?

| Option | Description | Selected |
|--------|-------------|----------|
| Python computes numbers; Claude writes only the narrative | Python → EV outputs → Claude narrates; Claude does NOT estimate or adjust | ✓ |
| Python computes + validates; Claude writes narrative + methodology note | Claude also comments on whether methodology is appropriate | |
| Claude's discretion | Standard split | |

**User's choice:** Python computes, Claude writes narrative only

---

## Report format + email scope

### Report content storage format

| Option | Description | Selected |
|--------|-------------|----------|
| Structured JSON — dict of section name → content string | Stored as JSON TEXT; Phase 7 Jinja2 iterates by key | ✓ |
| Markdown string with ## headings | Phase 7 parses headings to split into sections | |
| Plain text | No structural metadata; renders as one block | |

**User's choice:** Structured JSON

---

### Email delivery scope in Phase 5

| Option | Description | Selected |
|--------|-------------|----------|
| Real email in Phase 5 using SMTP — Phase 6 swaps to Resend | Abstracted send_report_ready_email() in email.py; SC-8 fully met | ✓ |
| Stub email — logs "would send" but doesn't actually send | Wiring in place; SC-8 not met until Phase 6 | |
| Resend API directly in Phase 5 — Phase 6 only adds payment | Front-loads real email but changes Phase 6 scope | |

**User's choice:** Real email via SMTP in Phase 5; Phase 6 swaps to Resend

---

## Claude's Discretion

- Section key schema per report type (Valuation, Bank Credit, Forecast, Capital Raising, IM)
- Claude prompt structure for all 5 report types (system prompt design, section instruction, disclaimer enforcement)
- DSCR computation specifics for Bank Credit Paper (which financial_rows fields to use)
- Report link format in email (Phase 7 viewer route — placeholder `/app` for Phase 5)

## Deferred Ideas

- Automatic exponential backoff for transient Claude errors (429/529) — user chose manual retry
- Resend email API — Phase 6 will swap smtplib implementation
- Static EV/EBITDA industry lookup table — replaced by diagnostic questionnaire approach
- Claude methodology note section — deferred (Python computes, Claude narrates only)
- On-screen progress indicator — v2 requirement
