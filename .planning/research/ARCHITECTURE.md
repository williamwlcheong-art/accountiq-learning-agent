# Architecture Research

## New Component Map

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (frontend/index.html) — extended with new tabs    │
│  Login/Register · Companies · Documents · Reports · Profile │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST (JSON)
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI API Layer — extended routes                        │
│  /auth  /users  /business-profiles  /reports  /payments     │
│  (existing: /companies /documents /financials /settings)    │
└──────────┬─────────────┬───────────────┬────────────────────┘
           │             │               │
┌──────────▼──┐  ┌───────▼──────┐  ┌────▼────────────────────┐
│  Auth Module │  │ Report       │  │ Payment Module          │
│  JWT tokens  │  │ Generation   │  │ Stripe PaymentIntent    │
│  passlib     │  │ Pipeline     │  │ Webhook verification    │
│  python-jose │  │ (background) │  └────────────────────────┘
└─────────────┘  └───────┬──────┘
                         │
              ┌──────────▼──────────┐
              │  Claude API          │
              │  Report prompts      │
              │  per report type     │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  PDF Renderer        │
              │  Jinja2 → WeasyPrint │
              │  Store to data/pdfs/ │
              └─────────────────────┘
```

---

## Data Model Changes

### New Tables

**`users`**
```sql
id          TEXT PRIMARY KEY  -- UUID
email       TEXT UNIQUE NOT NULL
password_hash TEXT NOT NULL
created_at  TEXT NOT NULL
is_active   INTEGER DEFAULT 1
```

**`business_profiles`**
```sql
id              TEXT PRIMARY KEY
company_id      INTEGER REFERENCES companies(id)
industry        TEXT           -- e.g. "Manufacturing", "Retail", "Professional Services"
sector_code     TEXT           -- internal classification for multiple lookup
description     TEXT           -- business overview narrative
management_json TEXT           -- JSON: [{name, title, bio}]
adjustments_json TEXT          -- JSON: [{label, amount, rationale}] EBITDA add-backs
created_at      TEXT NOT NULL
updated_at      TEXT NOT NULL
```

**`reports`**
```sql
id              TEXT PRIMARY KEY  -- UUID
company_id      INTEGER REFERENCES companies(id)
user_id         TEXT REFERENCES users(id)
report_type     TEXT NOT NULL  -- 'valuation'|'bank_credit'|'forecast'|'capital_raising'|'im'
status          TEXT NOT NULL  -- 'pending_payment'|'queued'|'generating'|'done'|'failed'
content_json    TEXT           -- structured report content (pre-render)
pdf_path        TEXT           -- relative path to generated PDF
error_message   TEXT
price_cents     INTEGER NOT NULL
created_at      TEXT NOT NULL
completed_at    TEXT
```

**`purchases`**
```sql
id                      TEXT PRIMARY KEY
report_id               TEXT REFERENCES reports(id)
user_id                 TEXT REFERENCES users(id)
stripe_payment_intent_id TEXT UNIQUE
stripe_status           TEXT   -- 'requires_payment'|'succeeded'|'failed'
amount_cents            INTEGER NOT NULL
currency                TEXT DEFAULT 'aud'
created_at              TEXT NOT NULL
confirmed_at            TEXT
```

### Existing Table Changes

**`companies`** — add `user_id TEXT REFERENCES users(id)` column
- All existing queries must add `WHERE user_id = :user_id` filter
- Migrate existing rows: assign to a seed/admin user or leave as shared data

**`documents`** — add `user_id TEXT REFERENCES users(id)` (denormalised for query performance)

---

## Build Order (dependency chain)

```
Phase 1 — Security & Auth Foundation
  ├── Fix existing security holes (CORS, filename, innerHTML XSS)
  ├── User registration + login (JWT)
  └── Middleware: require auth on all routes except /health, /auth/*

Phase 2 — Data Isolation
  ├── Add user_id to companies + documents
  ├── Migrate existing data
  └── All API routes filter by authenticated user_id

Phase 3 — Business Profile Intake
  ├── business_profiles table
  ├── POST/GET /business-profiles/{company_id}
  └── Frontend: profile intake form (new tab or modal)

Phase 4 — Extraction Quality
  ├── Fix sign convention, period attribution, multi-page handling
  ├── Extend to Word (.docx) ingestion
  └── Improve rule extractor for multi-page statements

Phase 5 — Report Generation Engine
  ├── Report prompt templates (one per report type)
  ├── Generation pipeline (background task + DB job state)
  ├── POST /reports (create + queue)
  └── GET /reports/{id}/status (poll)

Phase 6 — Payment Integration
  ├── Stripe PaymentIntent creation
  ├── Webhook handler (confirm → trigger generation)
  ├── purchases table
  └── Frontend: report selection + checkout flow

Phase 7 — PDF Rendering & Delivery
  ├── Jinja2 HTML templates (one per report type)
  ├── WeasyPrint PDF generation
  ├── GET /reports/{id}/pdf (download)
  └── Frontend: report viewer tab + download button
```

---

## Key Architectural Decisions

### Decision 1: JWT vs sessions for auth
**Recommendation: JWT (stateless)**
- No server-side session store needed (avoids Redis)
- Tokens stored in HTTP-only cookies (XSS protection)
- 7-day expiry with refresh token pattern
- Trade-off: token revocation requires a blocklist — accept this limitation for v1

### Decision 2: Payment → generation flow
**Recommendation: Stripe webhook triggers generation (not client callback)**
- Client payment completion is not reliable (browser close, network drop)
- Stripe sends webhook to `/payments/webhook` on confirmed payment
- Webhook handler sets report status → `queued` and triggers BackgroundTask
- Trade-off: 1-5s webhook delay before generation starts — acceptable

### Decision 3: Report storage
**Recommendation: Store generated content as JSON + render PDF on demand**
- `reports.content_json` holds structured report data
- PDF is rendered once, stored to `data/reports/{report_id}.pdf`
- GET /reports/{id}/pdf returns stored file (not re-render)
- Trade-off: disk storage grows; add cleanup job for old PDFs in v2

### Decision 4: SQLite concurrency under report generation load
**Observation:** SQLite WAL mode handles concurrent reads fine. Multiple simultaneous report generation jobs (each doing a 30-60s Claude call) will serialize on DB writes at the end — not a bottleneck for v1 volumes (<10 concurrent users).
**Watch for:** If more than ~10 users generate reports simultaneously, DB write locks will cause timeouts. Monitor and migrate to PostgreSQL if needed.

### Decision 5: Industry multiples source
**Recommendation: Static lookup table in DB (not live data feed)**
- Maintain a `industry_multiples` table seeded with curated EV/EBITDA ranges by sector
- Sufficient for first-draft quality
- Update quarterly via a seed script
- Trade-off: not real-time, but avoids licensing costs and API complexity

---

*Research date: 2026-05-04*
