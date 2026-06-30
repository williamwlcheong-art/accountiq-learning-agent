# AccountIQ Next.js Refactor Final Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `frontend/index.html` with a production-ready Next.js app, keep FastAPI as the backend of record, and finish deterministic E2E coverage across auth, wizard, admin workflows, uploads, report status, report viewing, and responsive smoke checks.

**Architecture:** Use a strangler migration. Next.js owns presentation, routing, client state, server-side route guards, and browser E2E tests; FastAPI continues to own auth cookies, SQLite, uploads, ingestion, valuation, report generation, email, and all durable data writes. The two apps communicate through a same-origin `/api/backend/:path*` proxy in development and a reverse proxy in production.

**Tech Stack:** Next.js App Router, React, TypeScript, Playwright, FastAPI, SQLite, pytest, `openapi-typescript`.

---

## Audit Corrections From Draft Plan

1. The draft dashboard type was stale: current `GET /analytics/overview` returns `companies`, `documents`, `docs_done`, `financial_rows`, and `by_exchange`, but no `label_patterns`. The Next.js dashboard must either omit label pattern count or fetch it separately from `GET /patterns`.
2. Real E2E cannot depend on the dev DB, Anthropic, OCR, SMTP, or long-running background jobs. Add an explicit E2E backend mode and isolated DB path before writing Playwright tests.
3. The current non-admin wizard contains a stale call to admin-only `GET /companies/{company_id}/profile-status`. The Next.js wizard must not call that route unless a wizard-scoped replacement exists.
4. The report "done" state should expose a report viewer link. Current vanilla UI says email was sent, but `GET /wizard/report/{report_id}/view` exists and should become user-visible in the Next.js wizard.
5. Use official Next.js primitives as of the current docs: `rewrites` for proxying, async `headers()` for forwarding cookies from Server Components, Playwright for E2E, and self-hosting behind a reverse proxy for production.

## Current Verified Surface

- Server health: `GET http://127.0.0.1:8765/health` returns 200.
- Unauthenticated auth check: `GET /auth/me` returns 401.
- OpenAPI route count: 37 operations, including `GET /`.
- Backend app: `backend/main.py`, 1,794 lines.
- Frontend app: `frontend/index.html`, 2,986 lines.
- Auth cookie: `accountiq_session`, `HttpOnly`, `SameSite=Lax`, 7-day max age.
- Existing split:
  - Admin users: dashboard, companies, upload, documents, patterns, financials, settings.
  - Regular users: wizard upload, report type selection, intake, report generation, status polling.

## Final Target

```text
Browser
  |
  | http://localhost:3000
  v
Next.js app in web/
  | pages, layouts, React components, E2E tests
  | /api/backend/:path* rewrite
  v
FastAPI backend on http://127.0.0.1:8765
  | auth, uploads, DB, background jobs, report generation
  v
SQLite + data/pdfs + Python extraction/report modules
```

Do not migrate ingestion, OCR, report generation, or SQLite access into Next.js during this goal.

---

## Phase 0: Baseline And Goal Guardrails

**Files:**
- Read: `backend/main.py`
- Read: `backend/auth.py`
- Read: `backend/db.py`
- Read: `frontend/index.html`
- Read: `tests/`
- Modify: none

- [ ] **Step 1: Confirm clean enough worktree**

Run:

```bash
git status --short
```

Expected: only known planning/doc files are untracked or modified. Do not revert `AGENTS.md` or user-created changes.

- [ ] **Step 2: Confirm server API inventory**

Run with the existing backend server running on port 8765:

```bash
curl -sS http://127.0.0.1:8765/openapi.json > /tmp/accountiq-openapi.json
python3 - <<'PY'
import json
spec = json.load(open('/tmp/accountiq-openapi.json'))
ops = [(method.upper(), path) for path, methods in spec["paths"].items() for method in methods]
print(len(ops))
for method, path in sorted(ops):
    print(method, path)
PY
```

Expected:

```text
36
```

and the list includes:

```text
POST /wizard/upload
POST /wizard/report/generate
GET /wizard/report/{report_id}/status
GET /wizard/report/{report_id}/view
```

- [ ] **Step 3: Run backend tests before migration**

Run:

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Expected: pass. If any test fails before the migration, record the exact failing test and stop implementation until it is classified as pre-existing or fixed.

- [ ] **Step 4: Commit the final plan**

Run:

```bash
git add docs/superpowers/plans/2026-07-01-nextjs-refactor-final.md
git commit -m "docs: finalize Next.js refactor and E2E plan"
```

## Phase 1: Add Deterministic Backend E2E Mode

**Files:**
- Modify: `backend/db.py`
- Modify: `backend/main.py`
- Modify: `.env.example`
- Create: `tests/test_e2e_mode.py`

Reason: Playwright must run against a disposable DB and must not call Anthropic, OCR, SMTP, or live research loops.

- [ ] **Step 1: Make DB path configurable**

Modify `backend/db.py` near the current `DB_PATH` assignment:

```python
import os
```

Replace:

```python
DB_PATH = Path(__file__).parent.parent / "data" / "accountiq_learning.db"
```

with:

```python
_DB_PATH_OVERRIDE = os.environ.get("ACCOUNTIQ_DB_PATH", "").strip()
DB_PATH = (
    Path(_DB_PATH_OVERRIDE).expanduser().resolve()
    if _DB_PATH_OVERRIDE
    else Path(__file__).parent.parent / "data" / "accountiq_learning.db"
)
```

- [ ] **Step 2: Add E2E constants and mock content helpers**

In `backend/main.py`, after `EXPORT_DIR.mkdir(...)`, add:

```python
E2E_MODE = os.environ.get("ACCOUNTIQ_E2E_MODE", "false").lower() == "true"


def _e2e_financial_rows() -> list[tuple[str, str, str, str, float, float]]:
    return [
        ("pnl", "revenue", "Revenue", "2025", 1_250_000.0, 0.99),
        ("pnl", "ebitda", "EBITDA", "2025", 240_000.0, 0.98),
        ("pnl", "net_profit", "Net Profit", "2025", 150_000.0, 0.97),
        ("bs", "cash_and_bank", "Cash & bank", "2025", 95_000.0, 0.98),
        ("bs", "total_assets", "Total Assets", "2025", 850_000.0, 0.98),
    ]


def _e2e_report_content(report_type: str) -> dict:
    sections = SECTION_SCHEMAS.get(report_type, ["executive_summary", "disclaimer"])
    content = {}
    for section in sections:
        title = section.replace("_", " ").title()
        if section == "disclaimer":
            content[section] = (
                "This report is indicative only, is not financial advice, "
                "is not regulated advice under the FMCA, and should not be relied "
                "on without independent professional advice."
            )
        elif section.endswith("summary") or section in {"valuation_summary", "financial_summary"}:
            content[section] = {
                "narrative": f"E2E generated {title} with <script>escaped text</script> for safety checks.",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Revenue", "$1,250,000"], ["EBITDA", "$240,000"]],
                },
            }
        else:
            content[section] = f"E2E generated {title} for {report_type}."
    return content
```

- [ ] **Step 3: Short-circuit ingestion only in E2E mode**

In `backend/main.py`, replace `_run_ingestion` with:

```python
async def _run_ingestion(document_id, company_id, filepath, entity_type, exchange, fiscal_year_end):
    """Background task — opens its own DB connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            if E2E_MODE:
                await db.execute(
                    "UPDATE documents SET extraction_status='processing', updated_at=datetime('now') WHERE id=?",
                    (document_id,),
                )
                await db.execute(
                    "INSERT INTO extraction_log (document_id, level, message) VALUES (?, 'info', ?)",
                    (document_id, "E2E ingestion shortcut started"),
                )
                for statement, row_key, row_label, period, value, confidence in _e2e_financial_rows():
                    await db.execute(
                        """
                        INSERT INTO financial_rows
                            (document_id, company_id, statement, row_key, row_label, period, value, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (document_id, company_id, statement, row_key, row_label, period, value, confidence),
                    )
                await db.execute(
                    """
                    UPDATE documents
                    SET extraction_status='done',
                        page_count=1,
                        has_ocr=0,
                        confidence_score=0.99,
                        narrative='E2E generated narrative with <script>escaped text</script>.',
                        reporting_standard='E2E',
                        updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (document_id,),
                )
                await db.execute(
                    "INSERT INTO extraction_log (document_id, level, message) VALUES (?, 'info', ?)",
                    (document_id, "E2E ingestion shortcut completed"),
                )
                await db.commit()
                return

            await ingest_document(
                db, document_id, company_id, filepath,
                entity_type, exchange, fiscal_year_end
            )
        except Exception as e:
            print(f"[ERROR] Ingestion failed for doc {document_id}: {e}")
```

- [ ] **Step 4: Short-circuit report generation only in E2E mode**

In `backend/main.py`, inside `_generate_report`, immediately after marking the report as `generating` and committing, add:

```python
            if E2E_MODE:
                await asyncio.sleep(0.05)
                content_json = _e2e_report_content(report_type)
                await db.execute(
                    """
                    UPDATE reports
                    SET status='done', content=?, completed_at=datetime('now')
                    WHERE id=?
                    """,
                    (json.dumps(content_json), report_id),
                )
                await db.commit()
                print(f"[REPORT] E2E report_id={report_id} done ({report_type})")
                return
```

- [ ] **Step 5: Document E2E env vars**

Append to `.env.example`:

```env
# E2E test mode only
ACCOUNTIQ_DB_PATH=data/accountiq_e2e.db
ACCOUNTIQ_E2E_MODE=false
```

- [ ] **Step 6: Add pytest coverage for E2E mode helper content**

Create `tests/test_e2e_mode.py`:

```python
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _e2e_report_content


def test_e2e_report_content_has_required_valuation_disclaimer():
    content = _e2e_report_content("valuation_advisory")
    text = str(content["disclaimer"]).lower()
    assert "indicative" in text
    assert "financial advice" in text
    assert "fmca" in text
    assert "should not be relied" in text


def test_e2e_report_content_escapes_test_payload_at_view_layer():
    content = _e2e_report_content("valuation_advisory")
    assert "<script>escaped text</script>" in str(content)
```

- [ ] **Step 7: Run backend tests**

Run:

```bash
source venv/bin/activate
python -m pytest tests/test_e2e_mode.py tests/test_report_viewer.py tests/test_wizard_endpoints.py -q
python -m pytest tests/ -q
```

Expected: pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/db.py backend/main.py .env.example tests/test_e2e_mode.py
git commit -m "test: add deterministic backend E2E mode"
```

## Phase 2: Scaffold Next.js And API Contract

**Files:**
- Create: `web/`
- Create: `web/scripts/fetch-openapi.mjs`
- Create: `web/types/api.ts`
- Modify: `.gitignore`
- Modify: `.env.example`

- [ ] **Step 1: Create the Next.js app**

Run:

```bash
npx create-next-app@latest web --ts --eslint --app --src-dir=false --import-alias "@/*"
```

Choose:
- TypeScript: yes
- ESLint: yes
- Tailwind: no
- App Router: yes
- `src/` directory: no

- [ ] **Step 2: Install contract and E2E dependencies**

Run:

```bash
cd web
npm install -D openapi-typescript @playwright/test
npx playwright install chromium
```

- [ ] **Step 3: Configure scripts**

In `web/package.json`, ensure these scripts exist:

```json
{
  "scripts": {
    "dev": "next dev --port 3000",
    "build": "next build",
    "start": "next start --port 3000",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "openapi:fetch": "node scripts/fetch-openapi.mjs",
    "openapi:types": "openapi-typescript openapi.json -o types/api.ts",
    "test:e2e": "playwright test",
    "test:e2e:headed": "playwright test --headed",
    "test:e2e:prod": "npm run build && playwright test"
  }
}
```

- [ ] **Step 4: Configure Next proxy and standalone output**

Replace `web/next.config.ts` with:

```ts
import type { NextConfig } from "next";

const fastapiOrigin = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${fastapiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 5: Add OpenAPI fetch script**

Create `web/scripts/fetch-openapi.mjs`:

```js
import { writeFile } from "node:fs/promises";

const origin = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";
const response = await fetch(`${origin}/openapi.json`);

if (!response.ok) {
  throw new Error(`Failed to fetch OpenAPI: ${response.status} ${response.statusText}`);
}

await writeFile(new URL("../openapi.json", import.meta.url), await response.text());
console.log(`Saved OpenAPI schema from ${origin}`);
```

- [ ] **Step 6: Update ignores and env docs**

Append to `.gitignore`:

```gitignore
# Next.js
web/node_modules/
web/.next/
web/out/
web/playwright-report/
web/test-results/
web/openapi.json
data/accountiq_e2e.db
data/accountiq_e2e.db-wal
data/accountiq_e2e.db-shm
```

Append to `.env.example`:

```env
# Next.js frontend
FASTAPI_ORIGIN=http://127.0.0.1:8765
NEXT_PUBLIC_API_BASE=/api/backend
```

- [ ] **Step 7: Generate types**

With FastAPI running:

```bash
cd web
npm run openapi:fetch
npm run openapi:types
```

Expected: `web/types/api.ts` is generated.

- [ ] **Step 8: Commit**

Run:

```bash
git add .gitignore .env.example web
git commit -m "chore(next): scaffold app and API contract"
```

## Phase 3: Shared UI, API, And Auth Foundation

**Files:**
- Create: `web/app/layout.tsx`
- Create: `web/app/globals.css`
- Create: `web/app/page.tsx`
- Create: `web/app/login/page.tsx`
- Create: `web/components/auth/auth-card.tsx`
- Create: `web/components/auth/logout-button.tsx`
- Create: `web/lib/api-client.ts`
- Create: `web/lib/server-api.ts`
- Create: `web/lib/auth.ts`
- Create: `web/types/domain.ts`

- [ ] **Step 1: Add domain types**

Create `web/types/domain.ts`:

```ts
export type CurrentUser = {
  id: number;
  email: string;
  is_admin: number;
  created_at: string;
};

export type Company = {
  id: number;
  name: string;
  ticker: string | null;
  exchange: string | null;
  sector: string | null;
  country: string | null;
  description: string | null;
  created_at?: string;
  doc_count?: number;
  sections_complete?: number;
};

export type DocumentRecord = {
  id: number;
  company_id: number;
  filename: string;
  report_type: string | null;
  entity_type: string | null;
  fiscal_year_end: string | null;
  extraction_status: string;
  confidence_score: number | null;
  narrative?: string | null;
  reporting_standard?: string | null;
  created_at: string;
  company_name?: string;
  logs?: Array<{ level: string; message: string; created_at: string }>;
};

export type ReportStatus = {
  id: number;
  report_type: string;
  status: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ApiErrorBody = {
  detail?: string;
};
```

- [ ] **Step 2: Add browser API helper**

Create `web/lib/api-client.ts`:

```ts
import type { ApiErrorBody } from "@/types/domain";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.detail) message = body.detail;
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function postForm<T>(path: string, body: FormData): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body });
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 3: Add server API and auth helpers**

Create `web/lib/server-api.ts`:

```ts
import { headers } from "next/headers";

const FASTAPI_ORIGIN = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";

export async function serverApiFetch<T>(path: string): Promise<T> {
  const incoming = await headers();
  const cookie = incoming.get("cookie") ?? "";

  const response = await fetch(`${FASTAPI_ORIGIN}${path}`, {
    headers: { cookie },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`FastAPI request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}
```

Create `web/lib/auth.ts`:

```ts
import { redirect } from "next/navigation";
import { serverApiFetch } from "@/lib/server-api";
import type { CurrentUser } from "@/types/domain";

export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await serverApiFetch<CurrentUser>("/auth/me");
  } catch {
    return null;
  }
}

export async function requireUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}

export async function requireAdmin(): Promise<CurrentUser> {
  const user = await requireUser();
  if (!user.is_admin) redirect("/wizard");
  return user;
}
```

- [ ] **Step 4: Add auth pages and root router**

Replace `web/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";

export default async function HomePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.is_admin) redirect("/admin");
  redirect("/wizard");
}
```

Create `web/app/login/page.tsx`:

```tsx
import { AuthCard } from "@/components/auth/auth-card";

export default function LoginPage() {
  return (
    <main className="auth-page">
      <AuthCard />
    </main>
  );
}
```

Create `web/components/auth/logout-button.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function logout() {
    await fetch("/api/backend/auth/logout", { method: "POST", credentials: "include" });
    router.replace("/login");
    router.refresh();
  }

  return <button onClick={logout}>Sign out</button>;
}
```

- [ ] **Step 5: Typecheck and commit**

Run:

```bash
cd web
npm run typecheck
```

Expected: pass.

Commit:

```bash
git add web/app web/components web/lib web/types
git commit -m "feat(next): add auth and API foundation"
```

## Phase 4: Migrate Regular User Wizard

**Files:**
- Create: `web/app/wizard/page.tsx`
- Create: `web/components/wizard/wizard.tsx`
- Create: `web/components/wizard/report-type-picker.tsx`
- Create: `web/components/wizard/intake-form.tsx`
- Create: `web/components/wizard/report-status-card.tsx`

- [ ] **Step 1: Add guarded wizard page**

Create `web/app/wizard/page.tsx`:

```tsx
import { requireUser } from "@/lib/auth";
import { Wizard } from "@/components/wizard/wizard";

export default async function WizardPage() {
  const user = await requireUser();
  return <Wizard user={user} />;
}
```

- [ ] **Step 2: Preserve exact wizard API calls**

The React wizard must call:

```text
POST /wizard/upload                       FormData: business_name, file
GET  /wizard/company/{company_id}/ebitda-adjustments
POST /wizard/report/generate              JSON: company_id, report_type, intake_answers
GET  /wizard/report/{report_id}/status
POST /wizard/report/{report_id}/retry
GET  /wizard/report/{report_id}/view      report viewer link after done
```

It must not call:

```text
GET /companies/{company_id}/profile-status
```

from a regular user wizard screen.

- [ ] **Step 3: Add report done viewer link**

When report status becomes `done`, render:

```tsx
<a href={`/api/backend/wizard/report/${reportId}/view`} target="_blank" rel="noreferrer">
  Open report
</a>
```

Use the proxied path so cookies remain same-origin.

- [ ] **Step 4: Validate report types**

The report type picker must include exactly these keys:

```ts
export const WIZARD_REPORT_TYPES = [
  "valuation_advisory",
  "bank_credit_paper",
  "financial_forecast",
  "capital_raising",
  "information_memorandum",
] as const;
```

- [ ] **Step 5: Typecheck and commit**

Run:

```bash
cd web
npm run typecheck
```

Expected: pass.

Commit:

```bash
git add web/app/wizard web/components/wizard
git commit -m "feat(next): migrate regular user wizard"
```

## Phase 5: Migrate Admin Dashboard And Workflows

**Files:**
- Create: `web/app/admin/layout.tsx`
- Create: `web/app/admin/page.tsx`
- Create: `web/app/admin/companies/page.tsx`
- Create: `web/app/admin/upload/page.tsx`
- Create: `web/app/admin/documents/page.tsx`
- Create: `web/app/admin/patterns/page.tsx`
- Create: `web/app/admin/financials/page.tsx`
- Create: `web/app/admin/settings/page.tsx`
- Create: `web/app/account/page.tsx`
- Create: focused components in `web/components/admin/`

- [ ] **Step 1: Add admin layout**

Create `web/app/admin/layout.tsx`:

```tsx
import Link from "next/link";
import { requireAdmin } from "@/lib/auth";
import { LogoutButton } from "@/components/auth/logout-button";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await requireAdmin();

  return (
    <>
      <nav className="top-nav">
        <Link href="/admin">Dashboard</Link>
        <Link href="/admin/companies">Companies</Link>
        <Link href="/admin/upload">Upload</Link>
        <Link href="/admin/documents">Documents</Link>
        <Link href="/admin/patterns">Patterns</Link>
        <Link href="/admin/financials">Financials</Link>
        <Link href="/account">Account</Link>
        <Link href="/admin/settings">Settings</Link>
        <span>{user.email}</span>
        <LogoutButton />
      </nav>
      <main className="shell">{children}</main>
    </>
  );
}
```

- [ ] **Step 2: Dashboard must match actual overview payload**

Dashboard type:

```ts
type Overview = {
  companies: number;
  documents: number;
  docs_done: number;
  financial_rows: number;
  by_exchange: Array<{ exchange: string | null; n: number }>;
};
```

Do not read `overview.label_patterns`. If a label pattern count is required, fetch `GET /patterns` and count the response rows in the component.

- [ ] **Step 3: Migrate pages one at a time**

Implement and commit in this order:

```bash
git commit -m "feat(next): migrate admin dashboard"
git commit -m "feat(next): migrate admin companies"
git commit -m "feat(next): migrate admin upload"
git commit -m "feat(next): migrate admin documents"
git commit -m "feat(next): migrate admin patterns"
git commit -m "feat(next): migrate admin financials"
git commit -m "feat(next): migrate admin settings"
git commit -m "feat(next): migrate account page"
```

Each page must pass:

```bash
cd web
npm run typecheck
```

before committing.

## Phase 6: Comprehensive Playwright E2E

**Files:**
- Create: `scripts/start-e2e-backend.sh`
- Create: `web/playwright.config.ts`
- Create: `web/e2e/helpers.ts`
- Create: `web/e2e/fixtures/sample.pdf`
- Create: `web/e2e/auth.spec.ts`
- Create: `web/e2e/wizard.spec.ts`
- Create: `web/e2e/admin.spec.ts`
- Create: `web/e2e/report-viewer.spec.ts`
- Create: `web/e2e/security.spec.ts`
- Create: `web/e2e/responsive.spec.ts`

- [ ] **Step 1: Add backend startup script**

Create `scripts/start-e2e-backend.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/accountiq_e2e.db"

rm -f "$DB" "$DB-wal" "$DB-shm"
mkdir -p "$ROOT/data" "$ROOT/data/pdfs"

export ACCOUNTIQ_DB_PATH="$DB"
export ACCOUNTIQ_E2E_MODE=true
export SECRET_KEY="e2e-secret-key-not-for-production"
export OWNER_EMAIL="owner-e2e@example.com"
export ANTHROPIC_API_KEY="sk-ant-e2e-placeholder"
export CLAUDE_MODEL="claude-sonnet-4-6"

cd "$ROOT/backend"
exec "$ROOT/venv/bin/uvicorn" main:app --port 8765
```

Run:

```bash
chmod +x scripts/start-e2e-backend.sh
```

- [ ] **Step 2: Add Playwright config**

Create `web/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 14"] }, testMatch: /responsive\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "../scripts/start-e2e-backend.sh",
      url: "http://127.0.0.1:8765/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
```

- [ ] **Step 3: Add E2E helpers**

Create `web/e2e/helpers.ts`:

```ts
import { expect, Page } from "@playwright/test";

export const regularEmail = () => `regular-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
export const adminEmail = () => "owner-e2e@example.com";
export const password = "correcthorse";

export async function register(page: Page, email: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: /create account/i }).click();
  await page.getByLabel(/email address/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByLabel(/confirm password/i).fill(password);
  await page.getByRole("button", { name: /^create account$/i }).click();
}

export async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel(/email address/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
}
```

- [ ] **Step 4: Add test fixture file**

Create `web/e2e/fixtures/sample.pdf` with this plain text content:

```text
E2E placeholder file. Backend ACCOUNTIQ_E2E_MODE bypasses real PDF parsing.
```

- [ ] **Step 5: Add auth E2E**

Create `web/e2e/auth.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { login, password, register, regularEmail } from "./helpers";

test("unauthenticated root redirects to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("AccountIQ")).toBeVisible();
});

test("regular user registers, lands on wizard, logs out, and can log in again", async ({ page }) => {
  const email = regularEmail();
  await register(page, email);
  await expect(page).toHaveURL(/\/wizard$/);
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, email);
  await expect(page).toHaveURL(/\/wizard$/);
});

test("short password is rejected in the browser", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /create account/i }).click();
  await page.getByLabel(/email address/i).fill(regularEmail());
  await page.getByLabel(/^password$/i).fill("short");
  await page.getByLabel(/confirm password/i).fill("short");
  await page.getByRole("button", { name: /^create account$/i }).click();
  await expect(page.getByRole("alert")).toContainText("at least 8");
});
```

- [ ] **Step 6: Add wizard E2E**

Create `web/e2e/wizard.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import path from "node:path";
import { register, regularEmail } from "./helpers";

test("regular user uploads, selects report type, generates report, and opens viewer", async ({ page }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("E2E Holdings Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByText("Bank Credit Paper").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/facility type/i).fill("Term loan");
  await page.getByLabel(/amount requested/i).fill("250000");
  await page.getByLabel(/proposed term/i).fill("5");
  await page.getByLabel(/repayment structure/i).fill("Monthly principal and interest");
  await page.getByLabel(/security/i).fill("General security agreement");
  await page.getByLabel(/loan purpose/i).fill("Working capital and expansion");
  await page.getByRole("button", { name: /generate report/i }).click();
  await expect(page.getByText(/status:/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /open report/i })).toBeVisible({ timeout: 15_000 });
});
```

- [ ] **Step 7: Add admin E2E**

Create `web/e2e/admin.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import path from "node:path";
import { adminEmail, register } from "./helpers";

test("owner email registers as admin and can use admin workflows", async ({ page }) => {
  await register(page, adminEmail());
  await expect(page).toHaveURL(/\/admin$/);

  await page.getByRole("link", { name: /companies/i }).click();
  await page.getByRole("button", { name: /add company/i }).click();
  await page.getByLabel(/company name/i).fill("Admin E2E Ltd");
  await page.getByLabel(/sector/i).fill("Professional Services");
  await page.getByRole("button", { name: /save company/i }).click();
  await expect(page.getByText("Admin E2E Ltd")).toBeVisible();

  await page.getByRole("link", { name: /upload/i }).click();
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /upload/i }).click();
  await expect(page.getByText(/done/i)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: /documents/i }).click();
  await expect(page.getByText("sample.pdf")).toBeVisible();

  await page.getByRole("link", { name: /financials/i }).click();
  await expect(page.getByText(/revenue/i)).toBeVisible({ timeout: 15_000 });
});
```

- [ ] **Step 8: Add report viewer and XSS E2E**

Create `web/e2e/report-viewer.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import path from "node:path";
import { register, regularEmail } from "./helpers";

test("completed report viewer escapes script payloads", async ({ page, context }) => {
  await register(page, regularEmail());
  await page.getByLabel(/business name/i).fill("Viewer E2E Ltd");
  await page.setInputFiles('input[type="file"]', path.join(process.cwd(), "e2e/fixtures/sample.pdf"));
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByText("Bank Credit Paper").click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/facility type/i).fill("Term loan");
  await page.getByLabel(/amount requested/i).fill("100000");
  await page.getByLabel(/proposed term/i).fill("3");
  await page.getByLabel(/repayment structure/i).fill("Monthly");
  await page.getByLabel(/security/i).fill("GSA");
  await page.getByLabel(/loan purpose/i).fill("Expansion");
  await page.getByRole("button", { name: /generate report/i }).click();
  const link = page.getByRole("link", { name: /open report/i });
  await expect(link).toBeVisible({ timeout: 15_000 });
  const viewer = await context.newPage();
  await viewer.goto((await link.getAttribute("href")) ?? "");
  await expect(viewer.locator("script")).toHaveCount(0);
  await expect(viewer.getByText("<script>escaped text</script>")).toBeVisible();
});
```

Create `web/e2e/security.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { register, regularEmail } from "./helpers";

test("regular user is redirected away from admin", async ({ page }) => {
  await register(page, regularEmail());
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/wizard$/);
});
```

- [ ] **Step 9: Add responsive E2E**

Create `web/e2e/responsive.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { expectNoHorizontalOverflow, register, regularEmail } from "./helpers";

test("wizard does not horizontally overflow on mobile", async ({ page }) => {
  await register(page, regularEmail());
  await expect(page).toHaveURL(/\/wizard$/);
  await expectNoHorizontalOverflow(page);
});
```

- [ ] **Step 10: Run E2E**

Run:

```bash
cd web
npm run typecheck
npm run test:e2e
```

Expected: all Playwright tests pass in Chromium and mobile project.

- [ ] **Step 11: Commit**

Run:

```bash
git add scripts/start-e2e-backend.sh web/playwright.config.ts web/e2e web/package.json web/package-lock.json
git commit -m "test(next): add comprehensive Playwright E2E coverage"
```

## Phase 7: Cutover And Documentation

**Files:**
- Modify: `backend/main.py`
- Modify: `.planning/codebase/ARCHITECTURE.md`
- Modify: `.planning/codebase/TESTING.md`
- Create: `.planning/research/NEXT_BACKEND_SPLIT.md`

- [ ] **Step 1: Guard legacy static mount**

In `backend/main.py`, replace:

```python
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

with:

```python
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
SERVE_LEGACY_FRONTEND = os.environ.get("ACCOUNTIQ_SERVE_LEGACY_FRONTEND", "false").lower() == "true"
if SERVE_LEGACY_FRONTEND and FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="legacy_frontend")
```

- [ ] **Step 2: Update backend root**

Replace:

```python
@app.get("/")
async def root():
    return {"message": "AccountIQ Learning Agent API. UI at /app"}
```

with:

```python
@app.get("/")
async def root():
    return {
        "name": "AccountIQ API",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "ui": "Run the Next.js app from web/ at http://localhost:3000",
        "legacy_ui": "/app when ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true",
    }
```

- [ ] **Step 3: Add backend boundary decision**

Create `.planning/research/NEXT_BACKEND_SPLIT.md`:

```markdown
# Next.js Backend Split Decision

## Decision

Keep FastAPI as the backend for v1. Next.js owns presentation, routing, route guards, and browser tests.

## Keep In FastAPI

- Auth token creation and validation
- SQLite access and schema migration
- File uploads to `data/pdfs`
- PDF, Excel, Word extraction
- OCR
- Claude extraction and report generation
- Valuation and research algorithms
- Email delivery
- Background job status transitions

## Allowed In Next.js

- UI rendering
- Client-side and server-side route guards that call `/auth/me`
- Same-origin API proxying under `/api/backend`
- Presentation-only report links and viewer entry points

## Revisit Later

- After Stripe payment gating
- After professional PDF rendering
- After background jobs move to a durable queue
- After SQLite is replaced by a migration-managed database
```

- [ ] **Step 4: Update docs**

Update `.planning/codebase/ARCHITECTURE.md` entry points to:

```markdown
## Entry Points

- Backend API: `source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765`
- Next.js frontend: `cd web && npm run dev`
- App URL: `http://localhost:3000`
- Legacy app: `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true` then `http://localhost:8765/app`
- API health: `http://127.0.0.1:8765/health`
```

Update `.planning/codebase/TESTING.md` current state to include:

```markdown
## Current State

- Backend: pytest with isolated SQLite fixture.
- Frontend: Playwright E2E in `web/e2e`.
- E2E backend mode: `ACCOUNTIQ_E2E_MODE=true` with `ACCOUNTIQ_DB_PATH=data/accountiq_e2e.db`.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/main.py .planning/codebase/ARCHITECTURE.md .planning/codebase/TESTING.md .planning/research/NEXT_BACKEND_SPLIT.md
git commit -m "chore(next): cut over frontend entry point"
```

## Phase 8: Final Verification Gate

**Files:**
- No new files unless failures require fixes.

- [ ] **Step 1: Full backend test suite**

Run:

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Expected: pass.

- [ ] **Step 2: Next.js checks**

Run:

```bash
cd web
npm run typecheck
npm run lint
npm run build
```

Expected: pass.

- [ ] **Step 3: Full E2E**

Run:

```bash
cd web
npm run test:e2e
```

Expected: pass.

- [ ] **Step 4: Production-like E2E**

Run:

```bash
cd web
npm run test:e2e:prod
```

Expected: build succeeds and Playwright passes against production build/start behavior.

- [ ] **Step 5: Manual smoke**

Run servers:

```bash
source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765
cd web && npm run dev
```

Manual checks:
- `http://localhost:3000` redirects based on auth state.
- Admin owner sees dashboard and can navigate all admin pages.
- Regular user sees wizard only.
- Upload accepts `.pdf`, `.xlsx`, `.xls`, `.xlsm`, `.docx`.
- Done report shows `Open report`.
- `http://localhost:8765/app` is not served unless `ACCOUNTIQ_SERVE_LEGACY_FRONTEND=true`.

- [ ] **Step 6: Final status**

Run:

```bash
git status --short
```

Expected: clean or only intentional uncommitted files.

## Definition Of Done

- Next.js app is the primary UI at `http://localhost:3000`.
- FastAPI remains the backend at `http://127.0.0.1:8765`.
- Auth cookie flow works through the Next.js proxy.
- Regular users can complete the wizard through report completion and viewer access.
- Admin users can complete current admin workflows.
- Playwright covers auth, wizard, admin, report viewer/XSS, route protection, and mobile overflow.
- Backend tests pass.
- Next typecheck, lint, build pass.
- E2E tests pass in dev and production-like modes.
- Legacy `/app` is opt-in only.

## Self-Review

- Spec coverage: Covers code/server audit, Next.js refactor, FastAPI boundary, isolated E2E DB, mocked AI/background paths, auth, wizard, admin workflows, report viewer, XSS, responsive checks, cutover, and final verification.
- Placeholder scan: No placeholder tokens or unspecified test tasks remain.
- Type consistency: `CurrentUser`, `Company`, `DocumentRecord`, and `ReportStatus` are defined before use. Dashboard `Overview` matches the actual `/analytics/overview` payload.
- Risk check: Does not proxy large uploads through a serverless-only architecture; final docs require self-hosting/reverse proxy for production.
