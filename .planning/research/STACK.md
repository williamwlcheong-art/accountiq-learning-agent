# Stack Research

## Context

Existing stack: Python FastAPI + SQLite (aiosqlite) + Vanilla JS/HTML + Anthropic Claude API.
This research covers only what needs to be *added* to support auth, payments, PDF report generation, Word doc ingestion, and long-running report jobs.

---

## Recommended Additions

### Authentication

- **`python-jose[cryptography]`** ~3.3 — JWT encoding/decoding. Lightweight, no ORM dependency, works directly with aiosqlite.
  - Confidence: High
  - Alternative considered: `fastapi-users` — brings SQLAlchemy ORM dependency which conflicts with the existing aiosqlite/raw-SQL approach
- **`passlib[bcrypt]`** ~1.7 — Password hashing. bcrypt is the industry standard for stored password security.
  - Confidence: High
  - Alternative considered: `argon2-cffi` — slightly more modern but bcrypt has better FastAPI ecosystem support

Pattern: stateless JWT tokens in HTTP-only cookies or Authorization header. No server-side session store needed (avoids Redis).

### Payments

- **`stripe`** ~11.x — Stripe Python SDK. Stripe Checkout handles the full payment UI; server-side only needs to create a PaymentIntent and verify webhooks.
  - Confidence: High
  - Alternative considered: LemonSqueezy / Paddle — better for subscriptions, not one-off report purchases; more complex webhook handling

Key pattern: create PaymentIntent → user completes payment client-side → Stripe webhook confirms payment → server queues report generation. Never generate before payment confirmed.

### PDF Report Generation

- **`weasyprint`** ~62.x — Renders HTML/CSS templates to PDF. Best choice for narrative-heavy reports because:
  - Report templates are written as HTML+CSS (designers can iterate without touching Python)
  - Handles page breaks, headers/footers, table formatting natively
  - Outputs production-quality PDFs
  - Confidence: High
  - Alternative considered: `reportlab` — powerful but programmatic (all layout in Python code), much harder to maintain visually
  - Alternative considered: `fpdf2` — simpler but limited CSS/styling support for complex reports

- **`jinja2`** ~3.x — HTML template engine for report templates. FastAPI installs Jinja2 as a dependency already; no new install needed.
  - Confidence: High

Pattern: report content JSON → Jinja2 HTML template → WeasyPrint → PDF bytes → store to disk.

Note: WeasyPrint requires system libraries (`libpango`, `libcairo`, `libgdk-pixbuf`) on Linux. On macOS these are installed via Homebrew (`brew install pango`). Document this in setup.sh.

### Word Document Ingestion

- **`python-docx`** ~1.x — Read .docx files. Extracts paragraphs and tables. Financial statements in Word are usually in tables — iterate `doc.tables` to extract cell values.
  - Confidence: High
  - Alternative considered: `docx2txt` — text-only, loses table structure which is critical for financials

### Background Job Reliability

FastAPI BackgroundTasks is fire-and-forget with no retry, no monitoring, and no persistence across restarts. Report generation (30-60s Claude calls) needs durability.

**Recommendation: stay with BackgroundTasks for now, but add DB-backed job state.**

Add a `report_jobs` table with status (queued/processing/done/failed), started_at, error_message, retry_count. This gives:
- Visibility into job state (user can poll)
- Retry logic (re-queue failed jobs)
- No new infrastructure (Redis, Celery, ARQ all require additional services)

Defer to a proper queue (ARQ + Redis) only if concurrent report generation causes SQLite write contention in production.

- **`arq`** — async Redis-backed job queue — listed as the upgrade path, not for v1
  - Confidence: Low (defer to v2)

### Email Notifications

- **`resend`** Python SDK ~2.x — Transactional email. Simple API (one function call), no SMTP server needed, generous free tier.
  - Confidence: Medium
  - Alternative considered: `aiosmtplib` — requires SMTP server config; more friction for initial setup
  - Alternative considered: `sendgrid` — heavier SDK, more setup

Email is a nice-to-have for "your report is ready" notification. Can be deferred to v2 if report generation is fast enough for the user to wait.

---

## What NOT to Add

- **SQLAlchemy / Alembic** — ORM would require rewriting all existing raw SQL queries. Not worth the migration cost for SQLite. Use manual `ALTER TABLE` migrations as the existing pattern does.
- **Redis** — Adds infrastructure complexity. SQLite-backed job state is sufficient for v1 volume.
- **Celery** — Heavy, requires Redis or RabbitMQ. Overkill for this scale.
- **React/Vue/Next.js** — Frontend is vanilla JS; adding a framework is a major rewrite with no v1 benefit.
- **PostgreSQL** — SQLite is sufficient until concurrent write contention is observed in production.

---

## Version Pinning Note

Current `requirements.txt` uses `>=` constraints (not pinned). When adding new dependencies, pin to exact minor version (e.g., `stripe==11.4.0`) to prevent silent breaking changes. The existing unpinned dependencies are a known risk documented in CONCERNS.md.

---

*Research date: 2026-05-04*
