# Phase 2: Multi-User Data Isolation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 02-multi-user-data-isolation
**Areas discussed:** Shared demo data access, Company name uniqueness, Analytics scope

---

## Shared Demo Data Access

| Option | Description | Selected |
|--------|-------------|----------|
| View-only | Users can browse demo companies but can't upload to them | |
| Upload allowed | Any user can upload to shared companies | |
| **User clarification** | **No demo companies at all — each user manages their own private clients' data** | ✓ |

**User's choice:** Corrected the premise — there are no demo companies. All data is private. Existing DB rows (pre-auth) are invisible via NULL user_id filtering, not shared.

**Notes:** User clarified: "there are no demo companies. each user uploads their own financial statements. the agent only stores these to learn from rather than they becoming available for others to review." This supersedes DATA-01 as written in REQUIREMENTS.md.

---

## Existing Orphaned Rows (follow-up from above)

| Option | Description | Selected |
|--------|-------------|----------|
| Hide them (NULL = invisible) | Rows with user_id IS NULL never returned | ✓ |
| Delete in migration | Permanent deletion of all orphaned rows | |
| Assign to dev account | Assign orphaned rows to a placeholder user | |

**User's choice:** Hide them — NULL user_id rows silently drop out of all queries.

---

## Pattern Library Isolation

| Option | Description | Selected |
|--------|-------------|----------|
| Global / shared | label_patterns cumulative across all users — best extraction quality | ✓ |
| Per-user private | Each user builds their own pattern library independently | |

**User's choice:** Global/shared — pattern learning benefits all users.

---

## Company Name Uniqueness

| Option | Description | Selected |
|--------|-------------|----------|
| Per-user unique | UNIQUE(name, exchange, user_id) — independent namespaces | ✓ |
| Keep global unique | UNIQUE(name, exchange) — first user to create a name locks it globally | |

**User's choice:** Per-user unique — each user manages their own portfolio independently.

---

## Analytics Scope

| Option | Description | Selected |
|--------|-------------|----------|
| User's own companies only | Analytics filtered to authenticated user's portfolio | ✓ |
| All companies (no filter) | Aggregate across all companies — leaks cross-user existence | |

**User's choice:** User's own companies only — consistent full isolation.

---

## Claude's Discretion

- SQLite ALTER TABLE migration approach (nullable user_id, no default)
- Document user_id always equals owning user's id, set at upload time
- financial_rows and extraction_log access derived from company/document ownership — no user_id column needed
- 404 (not 403) for unauthorized resource access to avoid existence leakage

## Deferred Ideas

None — discussion stayed within phase scope.
