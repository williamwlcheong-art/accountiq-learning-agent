# Phase 1: Security & Auth Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 01-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 1-Security & Auth Foundation
**Areas discussed:** Login UI

---

## Login UI

### Question 1: What does an unauthenticated user see?

| Option | Description | Selected |
|--------|-------------|----------|
| Auth wall | App hides everything — only login/register form visible until authenticated | ✓ |
| Login tab | Login/Register as a new nav tab; other tabs show "please log in" | |
| Modal overlay | App loads briefly, then login modal appears on top | |

**User's choice:** Auth wall
**Notes:** Clean, secure, no UI leakage — user confirmed this is the right approach.

---

### Question 2: Login + register relationship

| Option | Description | Selected |
|--------|-------------|----------|
| Toggle on same page | Login form with "Create account" link that swaps to register form in place | ✓ |
| Separate pages | /login and /register as distinct views | |
| Register-first | New users land on registration by default | |

**User's choice:** Toggle on same page
**Notes:** Single screen, minimal friction — standard SaaS pattern.

---

### Question 3: Post-login landing

| Option | Description | Selected |
|--------|-------------|----------|
| Dashboard tab | Land on Dashboard — natural home showing companies and recent activity | ✓ |
| Companies tab | Land directly on Companies — primary action is uploading documents | |
| Last visited tab | Resume where they left off via localStorage | |

**User's choice:** Dashboard tab

---

### Question 4: Logout placement

| Option | Description | Selected |
|--------|-------------|----------|
| Top-right corner | User email + logout button fixed in header — always visible | ✓ |
| Settings tab | Logout buried in Settings alongside API key config | |
| You decide | Claude picks conventional placement | |

**User's choice:** Top-right corner

---

## Gray Areas Not Selected for Discussion

The following gray areas were identified but the user chose not to discuss them (Claude applied sensible defaults):

- **Token storage** — Defaulted to HTTP-only cookies for better XSS posture
- **Session expiry UX** — Defaulted to redirect to auth wall with "session expired" message on 401
- **Settings endpoint protection** — Defaulted to same auth as all routes; no admin-only gate in v1

## Claude's Discretion

- JWT expiry: 7 days, no refresh token in v1
- Password minimum: 8 characters, no complexity rules
- Cookie name: `accountiq_session`
- `/health` endpoint remains public; all other routes require auth

## Deferred Ideas

- Auto-refresh tokens — not needed for 7-day expiry
- Email verification on registration — would require SMTP/email before payment phase
- "Remember me" / persistent sessions — v2
- Two-factor authentication — out of scope
- Admin-only gate on `/settings` — single-user context assumed for v1
