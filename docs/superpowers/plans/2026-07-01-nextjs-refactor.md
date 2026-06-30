# AccountIQ Next.js Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-file vanilla HTML app with a typed Next.js application while preserving the working FastAPI ingestion, extraction, auth, report generation, and SQLite data layer.

**Architecture:** Use a strangler migration. Create a new `web/` Next.js App Router application that proxies API calls to the existing FastAPI server, then migrate the auth wall, non-admin wizard, and admin dashboard one workflow at a time. Keep Python as the system of record for PDF/Excel/Word ingestion, OCR, Claude calls, valuation algorithms, background jobs, and database access until the product is stable enough to consider deeper backend extraction.

**Tech Stack:** Next.js App Router, React, TypeScript, FastAPI, SQLite, `openapi-typescript`, Playwright, existing pytest suite.

---

## Current Codebase Map

**Server observed:** `GET /health` returns 200 from `http://127.0.0.1:8765`; unauthenticated `GET /auth/me` returns 401 as expected.

**Backend shape:**
- `backend/main.py`: 1,794 lines, FastAPI app, static `/app` mount, 36 OpenAPI operations.
- `backend/auth.py`: cookie JWT auth using `accountiq_session`, `HttpOnly`, `SameSite=Lax`, 7 day max age, `OWNER_EMAIL` admin promotion.
- `backend/db.py`: SQLite schema and manual migrations; `users`, `companies`, `documents`, `financial_rows`, `label_patterns`, `management_team`, `ebitda_adjustments`, `reports`, `report_intake`.
- `backend/ingestion.py`, `backend/rule_extractor.py`, `backend/research_loop.py`, `backend/valuation.py`: Python-heavy domain logic that should stay in FastAPI for now.

**Frontend shape:**
- `frontend/index.html`: 2,986 lines, inline CSS, inline HTML, inline JS.
- `const API = window.location.origin`, so the current app assumes same-origin API calls.
- Two user experiences are already present:
  - Admin: dashboard, companies, upload, documents, patterns, financials, account, settings.
  - Non-admin wizard: upload financials, select report type, intake questionnaire, queue report, poll status.

**Route inventory to preserve:**
- Public/auth: `/health`, `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`.
- Admin-only: `/companies`, `/companies/{id}`, `/companies/{id}/profile`, `/companies/{id}/profile-status`, management team CRUD, EBITDA adjustment CRUD, `/documents`, `/documents/upload`, `/documents/{id}/status`, `/documents/{id}/rows`, `/documents/{id}/retry`, `/financials/{company_id}`, `/patterns`, `/patterns/export`, `/analytics/overview`, `/analytics/confidence`, `/settings`.
- User wizard: `/wizard/upload`, `/wizard/report/generate`, `/wizard/report/{id}/status`, `/wizard/report/{id}/retry`, `/wizard/company/{id}/ebitda-adjustments`, `/wizard/report/{id}/view`.

## Recommendation

Do not rewrite the FastAPI backend into Next.js API routes yet.

Reasons:
- The backend depends on Python-native libraries: `pdfplumber`, `pandas`, `openpyxl`, `pytesseract`, `python-docx`, `aiosqlite`, and existing valuation/research modules.
- The app has long-running background workflows. Next.js route handlers are not the right home for OCR, file extraction, report generation, and local SQLite writes if deployment may become serverless.
- The current tests are Python pytest integration tests against the real FastAPI app. Keeping the API stable lets the UI migration proceed with lower risk.
- The frontend is the largest maintainability problem: a 3,000 line single-file SPA with global mutable state and inline handlers. Next.js gives the most leverage there first.

Target architecture:

```text
Browser
  |
  | http://localhost:3000
  v
Next.js web app in web/
  | /api/backend/:path* rewrite in development
  | same-origin cookies from the browser's perspective
  v
FastAPI backend on http://127.0.0.1:8765
  |
  v
SQLite + data/pdfs + Python ingestion/report workers
```

Production architecture:

```text
Single public domain
  /, /login, /wizard, /admin/*  -> Next.js
  /api/* or /api/backend/*      -> FastAPI
  /_next/*                      -> Next.js assets
```

Avoid proxying large file uploads through Vercel serverless functions. Self-host Next.js next to FastAPI, or put both behind a reverse proxy that sends upload routes directly to FastAPI.

## File Structure

Create:
- `web/package.json`: Node scripts and dependencies.
- `web/next.config.ts`: proxy `/api/backend/:path*` to FastAPI.
- `web/tsconfig.json`: TypeScript config.
- `web/.eslintrc.json`: lint config.
- `web/app/layout.tsx`: root document.
- `web/app/page.tsx`: server-side auth router.
- `web/app/login/page.tsx`: login/register entry page.
- `web/app/admin/layout.tsx`: admin guard and nav.
- `web/app/admin/page.tsx`: dashboard.
- `web/app/admin/companies/page.tsx`: companies table and profile entry point.
- `web/app/admin/upload/page.tsx`: admin upload workflow.
- `web/app/admin/documents/page.tsx`: documents table and retry/log UI.
- `web/app/admin/patterns/page.tsx`: pattern library.
- `web/app/admin/financials/page.tsx`: financial rows viewer.
- `web/app/admin/settings/page.tsx`: API key/model settings.
- `web/app/account/page.tsx`: account details and report history placeholder.
- `web/app/wizard/page.tsx`: non-admin wizard shell.
- `web/components/*`: focused React components split by workflow.
- `web/lib/api-client.ts`: browser API helper using `/api/backend`.
- `web/lib/server-api.ts`: server-side API helper forwarding cookie headers.
- `web/lib/auth.ts`: `getCurrentUser`, `requireUser`, `requireAdmin`.
- `web/types/api.ts`: generated OpenAPI types.
- `web/types/domain.ts`: hand-written narrow UI types.
- `web/e2e/*.spec.ts`: Playwright smoke tests.
- `docs/superpowers/plans/2026-07-01-nextjs-refactor.md`: this plan.

Modify:
- `.gitignore`: ignore `web/node_modules/`, `web/.next/`, `web/playwright-report/`, `web/test-results/`.
- `.env.example`: add `FASTAPI_ORIGIN=http://127.0.0.1:8765` and `NEXT_PUBLIC_API_BASE=/api/backend`.
- `backend/main.py`: late phase only, remove `/app` static mount after Next.js parity is verified.
- `backend/main.py`: optional late phase, add `/api` prefix or keep unprefixed routes behind a reverse proxy. Do not change this during the first UI migration.

Do not modify in the first pass:
- `backend/ingestion.py`
- `backend/research_loop.py`
- `backend/report_prompts.py`
- `backend/valuation.py`
- `backend/db.py` except for tests or API-contract support

---

### Task 1: Freeze The Current API Contract

**Files:**
- Create: `web/types/api.ts`
- Create: `web/scripts/fetch-openapi.mjs`
- Modify: `web/package.json`
- Test: existing `tests/`

- [ ] **Step 1: Capture the route inventory**

Run:

```bash
source venv/bin/activate
curl -sS http://127.0.0.1:8765/openapi.json > /tmp/accountiq-openapi.json
python3 - <<'PY'
import json
spec = json.load(open('/tmp/accountiq-openapi.json'))
for path, ops in sorted(spec['paths'].items()):
    for method in sorted(ops):
        print(method.upper(), path)
PY
```

Expected: output includes 36 operations and includes `/wizard/report/{report_id}/view`.

- [ ] **Step 2: Run backend tests before touching UI**

Run:

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Expected: all existing tests pass or failures are documented before the migration starts.

- [ ] **Step 3: Add OpenAPI generation after the Next app exists**

Add this script to `web/scripts/fetch-openapi.mjs`:

```js
import { writeFile } from "node:fs/promises";

const origin = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";
const response = await fetch(`${origin}/openapi.json`);

if (!response.ok) {
  throw new Error(`Failed to fetch OpenAPI: ${response.status} ${response.statusText}`);
}

const json = await response.text();
await writeFile(new URL("../openapi.json", import.meta.url), json);
console.log(`Saved OpenAPI schema from ${origin}`);
```

- [ ] **Step 4: Add package scripts**

Add these scripts to `web/package.json` after Task 2 scaffolds it:

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
    "test:e2e": "playwright test"
  }
}
```

- [ ] **Step 5: Commit**

Run:

```bash
git add web/scripts/fetch-openapi.mjs web/package.json web/openapi.json web/types/api.ts
git commit -m "chore(next): capture FastAPI contract"
```

### Task 2: Scaffold The Next.js App Beside The Existing App

**Files:**
- Create: `web/package.json`
- Create: `web/next.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/app/globals.css`
- Modify: `.gitignore`
- Modify: `.env.example`

- [ ] **Step 1: Create the app**

Run:

```bash
npx create-next-app@latest web --ts --eslint --app --src-dir=false --import-alias "@/*"
```

Choose:
- TypeScript: yes
- ESLint: yes
- Tailwind: no for the first pass
- App Router: yes
- `src/` directory: no

Expected: `web/package.json`, `web/app`, and `web/next.config.ts` exist.

- [ ] **Step 2: Configure API proxy**

Replace `web/next.config.ts` with:

```ts
import type { NextConfig } from "next";

const fastapiOrigin = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
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

- [ ] **Step 3: Update ignored files**

Append to `.gitignore`:

```gitignore
# Next.js
web/node_modules/
web/.next/
web/out/
web/playwright-report/
web/test-results/
web/openapi.json
```

- [ ] **Step 4: Update environment example**

Append to `.env.example`:

```env
# Next.js frontend
FASTAPI_ORIGIN=http://127.0.0.1:8765
NEXT_PUBLIC_API_BASE=/api/backend
```

- [ ] **Step 5: Add root layout**

Replace `web/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AccountIQ",
  description: "Financial intelligence report generation for SMEs",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: Add temporary root page**

Replace `web/app/page.tsx` with:

```tsx
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <h1>AccountIQ</h1>
      <p>Next.js migration shell is running.</p>
      <Link href="/login">Sign in</Link>
    </main>
  );
}
```

- [ ] **Step 7: Add base CSS**

Replace `web/app/globals.css` with:

```css
:root {
  --navy: #1a2a40;
  --blue: #2563eb;
  --green: #15803d;
  --red: #b42318;
  --amber: #b45309;
  --surface: #ffffff;
  --page: #f5f7fa;
  --border: #d8dee8;
  --muted: #64748b;
  --text: #172033;
}

* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  min-height: 100%;
  color: var(--text);
  background: var(--page);
  font-family: Arial, Helvetica, sans-serif;
}

button,
input,
select,
textarea {
  font: inherit;
}

a {
  color: var(--blue);
}

.shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 32px auto;
}
```

- [ ] **Step 8: Verify**

Run:

```bash
cd web
npm run dev
```

Expected: Next.js starts on `http://localhost:3000`; visiting it shows "Next.js migration shell is running."

- [ ] **Step 9: Commit**

Run:

```bash
git add .gitignore .env.example web
git commit -m "chore(next): scaffold frontend app"
```

### Task 3: Build Typed API Helpers And Auth Helpers

**Files:**
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

export type ApiErrorBody = {
  detail?: string;
};

export type Company = {
  id: number;
  name: string;
  ticker: string | null;
  exchange: string | null;
  sector: string | null;
  country: string | null;
  description: string | null;
  doc_count?: number;
  sections_complete?: number;
};

export type DocumentRow = {
  id: number;
  company_id: number;
  filename: string;
  report_type: string | null;
  entity_type: string | null;
  fiscal_year_end: string | null;
  extraction_status: "pending" | "processing" | "done" | "failed" | string;
  confidence_score: number | null;
  created_at: string;
  company_name?: string;
  exchange?: string | null;
};

export type ReportStatus = {
  id: number;
  report_type: string;
  status: "queued" | "generating" | "researching" | "done" | "failed" | string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
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

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function formPost<T>(path: string, formData: FormData): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: formData,
  });
}
```

- [ ] **Step 3: Add server API helper**

Create `web/lib/server-api.ts`:

```ts
import { headers } from "next/headers";

const FASTAPI_ORIGIN = process.env.FASTAPI_ORIGIN ?? "http://127.0.0.1:8765";

export async function serverApiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const incomingHeaders = await headers();
  const cookie = incomingHeaders.get("cookie") ?? "";

  const response = await fetch(`${FASTAPI_ORIGIN}${path}`, {
    ...init,
    headers: {
      ...Object.fromEntries(new Headers(init.headers).entries()),
      cookie,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`FastAPI request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}
```

- [ ] **Step 4: Add auth helper**

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

- [ ] **Step 5: Typecheck**

Run:

```bash
cd web
npm run typecheck
```

Expected: no TypeScript errors.

- [ ] **Step 6: Commit**

Run:

```bash
git add web/lib web/types
git commit -m "feat(next): add typed API and auth helpers"
```

### Task 4: Migrate Login, Register, Logout, And Root Routing

**Files:**
- Create: `web/app/login/page.tsx`
- Create: `web/components/auth/auth-card.tsx`
- Create: `web/components/auth/logout-button.tsx`
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Add root role routing**

Replace `web/app/page.tsx` with:

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

- [ ] **Step 2: Add auth card client component**

Create `web/components/auth/auth-card.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Mode = "login" | "register";

export function AuthCard() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError("");

    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }

    if (mode === "register") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirm) {
        setError("Passwords do not match.");
        return;
      }
    }

    const formData = new FormData();
    formData.append("email", email.trim());
    formData.append("password", password);

    setLoading(true);
    try {
      const response = await fetch(`/api/backend/auth/${mode}`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        if (response.status === 409) setError("An account with this email already exists.");
        else if (response.status === 401) setError("Incorrect email or password.");
        else setError("Authentication failed. Please try again.");
        return;
      }

      router.replace("/");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <h1>AccountIQ</h1>
      <p>Financial Intelligence Platform</p>
      {error ? <div role="alert" className="alert error">{error}</div> : null}
      <label>
        Email address
        <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" />
      </label>
      <label>
        Password
        <input
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
        />
      </label>
      {mode === "register" ? (
        <label>
          Confirm password
          <input
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            type="password"
            autoComplete="new-password"
          />
        </label>
      ) : null}
      <button onClick={submit} disabled={loading}>
        {loading ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
      </button>
      <button type="button" className="link-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Create account" : "Sign in instead"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Add login page**

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

- [ ] **Step 4: Add logout button**

Create `web/components/auth/logout-button.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function logout() {
    await fetch("/api/backend/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    router.replace("/login");
    router.refresh();
  }

  return <button onClick={logout}>Sign out</button>;
}
```

- [ ] **Step 5: Verify auth manually**

Run FastAPI and Next.js:

```bash
source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765
cd web && npm run dev
```

Open `http://localhost:3000/login`, register a new non-owner email with an 8 character password, and confirm the app redirects to `/wizard`.

- [ ] **Step 6: Commit**

Run:

```bash
git add web/app/page.tsx web/app/login web/components/auth
git commit -m "feat(next): migrate authentication shell"
```

### Task 5: Migrate The Non-Admin Wizard First

**Files:**
- Create: `web/app/wizard/page.tsx`
- Create: `web/components/wizard/wizard.tsx`
- Create: `web/components/wizard/report-type-picker.tsx`
- Create: `web/components/wizard/intake-form.tsx`
- Create: `web/components/wizard/report-status.tsx`

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

- [ ] **Step 2: Implement the wizard as a client component**

Port these existing functions from `frontend/index.html` into React state:
- `wizardFileChosen`
- `wizardSubmitStep1`
- `_renderReportTypeCards`
- `wizardShowIntake`
- `wizardSubmitGenerate`
- `_startReportPolling`
- `_updateStep3Status`
- `wizardRetry`
- `wizardReset`

Keep the API calls identical:
- `POST /wizard/upload` as `FormData`.
- `POST /wizard/report/generate` as JSON.
- `GET /wizard/report/{id}/status` every 3 seconds until `done` or `failed`.
- `POST /wizard/report/{id}/retry`.

Use this state shape in `web/components/wizard/wizard.tsx`:

```tsx
type WizardStep = "upload" | "report-type" | "intake" | "status";

type UploadResult = {
  company_id: number;
  document_id: number;
  status: string;
};

type WizardState = {
  step: WizardStep;
  businessName: string;
  file: File | null;
  upload: UploadResult | null;
  reportType: string | null;
  reportId: number | null;
};
```

- [ ] **Step 3: Fix the existing wizard profile-status bug during the port**

Current vanilla JS calls admin-only `/companies/{company_id}/profile-status` from the non-admin wizard. In React, do not call that route from the non-admin wizard. Either omit the warning for the first Next.js port, or add a backend wizard-scoped profile-status endpoint in a separate backend task before wiring it.

For the first port, omit the warning and keep report generation unblocked.

- [ ] **Step 4: Verify wizard upload and report queue**

Run:

```bash
cd web
npm run typecheck
```

Manual test:
- Log in as a non-admin user.
- Upload a `.pdf`, `.xlsx`, `.xls`, `.xlsm`, or `.docx`.
- Select `Valuation Advisory`.
- Complete required valuation fields.
- Submit.
- Confirm status polling shows `queued`, `generating`, `researching`, `done`, or `failed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add web/app/wizard web/components/wizard
git commit -m "feat(next): migrate user report wizard"
```

### Task 6: Migrate The Admin Layout And Dashboard

**Files:**
- Create: `web/app/admin/layout.tsx`
- Create: `web/app/admin/page.tsx`
- Create: `web/components/admin/admin-nav.tsx`
- Create: `web/components/admin/dashboard.tsx`

- [ ] **Step 1: Add admin guard layout**

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
        <Link href="/admin">AccountIQ</Link>
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

- [ ] **Step 2: Add dashboard data fetch**

Create `web/components/admin/dashboard.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

type Overview = {
  companies: number;
  documents: number;
  docs_done: number;
  financial_rows: number;
  label_patterns: number;
  by_exchange: Array<{ exchange: string | null; n: number }>;
};

type ConfidenceRow = {
  row_key: string;
  avg_conf: number;
};

export function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [confidence, setConfidence] = useState<ConfidenceRow[]>([]);

  useEffect(() => {
    apiFetch<Overview>("/analytics/overview").then(setOverview);
    apiFetch<ConfidenceRow[]>("/analytics/confidence").then(setConfidence);
  }, []);

  if (!overview) return <p>Loading...</p>;

  return (
    <section>
      <h1>Overview</h1>
      <div className="stats-row">
        <div><strong>{overview.companies}</strong><span>Companies</span></div>
        <div><strong>{overview.documents}</strong><span>Documents</span></div>
        <div><strong>{overview.docs_done}</strong><span>Processed</span></div>
        <div><strong>{overview.financial_rows.toLocaleString()}</strong><span>Financial Rows</span></div>
        <div><strong>{overview.label_patterns}</strong><span>Label Patterns</span></div>
      </div>
      <h2>Coverage by Exchange</h2>
      <ul>
        {overview.by_exchange.map((row) => (
          <li key={row.exchange ?? "Private"}>{row.exchange ?? "Private"}: {row.n}</li>
        ))}
      </ul>
      <h2>Lowest Confidence Rows</h2>
      <ul>
        {confidence.map((row) => (
          <li key={row.row_key}>{row.row_key}: {(row.avg_conf * 100).toFixed(0)}%</li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 3: Add page**

Create `web/app/admin/page.tsx`:

```tsx
import { Dashboard } from "@/components/admin/dashboard";

export default function AdminHomePage() {
  return <Dashboard />;
}
```

- [ ] **Step 4: Verify**

Log in as an admin and open `http://localhost:3000/admin`. Expected: dashboard numbers load or show empty states without a 401 or 403.

- [ ] **Step 5: Commit**

Run:

```bash
git add web/app/admin web/components/admin
git commit -m "feat(next): migrate admin dashboard shell"
```

### Task 7: Migrate Admin Workflows One Page At A Time

**Files:**
- Create: `web/app/admin/companies/page.tsx`
- Create: `web/app/admin/upload/page.tsx`
- Create: `web/app/admin/documents/page.tsx`
- Create: `web/app/admin/patterns/page.tsx`
- Create: `web/app/admin/financials/page.tsx`
- Create: `web/app/admin/settings/page.tsx`
- Create: focused components under `web/components/admin/`

- [ ] **Step 1: Companies**

Port:
- `loadCompanies`
- `addCompany`
- `loadProfilePanel`
- industry/description save
- management team CRUD
- EBITDA adjustment CRUD

Use these endpoints:
- `GET /companies`
- `POST /companies`
- `POST /companies/{id}/profile`
- `GET /companies/{id}/management-team`
- `POST /companies/{id}/management-team`
- `PUT /companies/{id}/management-team/{member_id}`
- `DELETE /companies/{id}/management-team/{member_id}`
- `GET /companies/{id}/ebitda-adjustments`
- `POST /companies/{id}/ebitda-adjustments`
- `PUT /companies/{id}/ebitda-adjustments/{adj_id}`
- `DELETE /companies/{id}/ebitda-adjustments/{adj_id}`

Run after port:

```bash
cd web
npm run typecheck
```

Manual expected result: admin can create a company and edit all four profile sections.

- [ ] **Step 2: Upload**

Port:
- `handleFileSelect`
- `_updateUploadCompanyNameVisibility`
- `populateCompanySelects`
- `uploadFile`
- `startJobPolling`
- `renderJobs`

Use:
- `GET /companies`
- `POST /documents/upload`
- `GET /documents/{id}/status`

Manual expected result: admin can upload a document, see polling logs, and see `done` or `failed`.

- [ ] **Step 3: Documents**

Port:
- `loadDocuments`
- `viewDocLog`
- `retryDoc`
- `viewNarrative`

Use:
- `GET /documents`
- `GET /documents?company_id={id}`
- `GET /documents/{id}/status`
- `POST /documents/{id}/retry`

Manual expected result: admin can filter documents, inspect logs, view narrative text as escaped text, and retry a failed document.

- [ ] **Step 4: Patterns**

Port:
- `loadPatterns`
- `exportPatterns`

Use:
- `GET /patterns`
- `GET /patterns?statement=pnl`
- `GET /patterns/export`

Manual expected result: admin can filter pattern groups and download JSON.

- [ ] **Step 5: Financials**

Port:
- `loadFinancials`
- table rendering by statement and period

Use:
- `GET /financials/{company_id}`
- `GET /financials/{company_id}?statement=pnl`
- `GET /financials/{company_id}?statement=bs`

Manual expected result: admin can select a company and statement type and see period columns.

- [ ] **Step 6: Settings**

Port:
- `loadSettings`
- `saveSettings`
- `checkApiKey`

Use:
- `GET /settings`
- `POST /settings`

Manual expected result: admin can see masked API key status and save an allowed model value.

- [ ] **Step 7: Commit each page separately**

Use commit messages:

```bash
git commit -m "feat(next): migrate admin companies"
git commit -m "feat(next): migrate admin upload"
git commit -m "feat(next): migrate admin documents"
git commit -m "feat(next): migrate admin patterns"
git commit -m "feat(next): migrate admin financials"
git commit -m "feat(next): migrate admin settings"
```

### Task 8: Add Browser Regression Tests

**Files:**
- Create: `web/playwright.config.ts`
- Create: `web/e2e/auth.spec.ts`
- Create: `web/e2e/wizard.spec.ts`
- Create: `web/e2e/admin.spec.ts`
- Modify: `web/package.json`

- [ ] **Step 1: Install Playwright**

Run:

```bash
cd web
npm install -D @playwright/test
npx playwright install chromium
```

- [ ] **Step 2: Add Playwright config**

Create `web/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "cd ../backend && uvicorn main:app --port 8765",
      url: "http://127.0.0.1:8765/health",
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
    },
  ],
});
```

- [ ] **Step 3: Add auth smoke test**

Create `web/e2e/auth.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("unauthenticated user sees login page", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("AccountIQ")).toBeVisible();
});
```

- [ ] **Step 4: Add wizard smoke test**

Create `web/e2e/wizard.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("regular user can reach wizard after registration", async ({ page }) => {
  const email = `wizard-${Date.now()}@example.com`;
  await page.goto("/login");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("correcthorse");
  await page.getByLabel("Confirm password").fill("correcthorse");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/wizard$/);
});
```

- [ ] **Step 5: Add admin route protection smoke test**

Create `web/e2e/admin.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("regular user is redirected away from admin", async ({ page }) => {
  const email = `regular-${Date.now()}@example.com`;
  await page.goto("/login");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("correcthorse");
  await page.getByLabel("Confirm password").fill("correcthorse");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/wizard$/);
});
```

- [ ] **Step 6: Run checks**

Run:

```bash
cd web
npm run typecheck
npm run test:e2e
```

Expected: typecheck passes and all Playwright tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add web/playwright.config.ts web/e2e web/package.json web/package-lock.json
git commit -m "test(next): add browser smoke coverage"
```

### Task 9: Cut Over From Static `/app` To Next.js

**Files:**
- Modify: `backend/main.py`
- Modify: project README or `.planning/codebase/ARCHITECTURE.md`

- [ ] **Step 1: Confirm parity**

Run:

```bash
source venv/bin/activate
python -m pytest tests/ -q
cd web
npm run typecheck
npm run test:e2e
npm run build
```

Expected: all checks pass.

- [ ] **Step 2: Remove FastAPI static frontend mount**

In `backend/main.py`, remove or guard this block:

```python
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

Use this transitional replacement:

```python
SERVE_LEGACY_FRONTEND = os.environ.get("SERVE_LEGACY_FRONTEND", "false").lower() == "true"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if SERVE_LEGACY_FRONTEND and FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

- [ ] **Step 3: Update root route**

Change `GET /` in `backend/main.py` to return API metadata instead of a frontend pointer:

```python
@app.get("/")
async def root():
    return {
        "name": "AccountIQ API",
        "health": "/health",
        "openapi": "/openapi.json",
    }
```

- [ ] **Step 4: Document dev commands**

Update `.planning/codebase/ARCHITECTURE.md` entry points:

```markdown
## Entry Points

- Backend API: `source venv/bin/activate && cd backend && uvicorn main:app --reload --port 8765`
- Next.js frontend: `cd web && npm run dev`
- App URL: `http://localhost:3000`
- API health: `http://127.0.0.1:8765/health`
```

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/main.py .planning/codebase/ARCHITECTURE.md
git commit -m "chore(next): cut over frontend entry point"
```

### Task 10: Decide Whether To Move Any Backend Logic Later

**Files:**
- Create: `.planning/research/NEXT_BACKEND_SPLIT.md`

- [ ] **Step 1: Write the decision record**

Create `.planning/research/NEXT_BACKEND_SPLIT.md`:

```markdown
# Next.js Backend Split Decision

## Decision

Keep FastAPI as the backend for v1.

## Keep In FastAPI

- Auth token creation and verification
- SQLite access and migrations
- File upload persistence to `data/pdfs`
- PDF, Excel, Word extraction
- OCR
- Claude extraction and report generation
- Email delivery
- Valuation algorithms
- Background job state transitions

## Allowed In Next.js

- UI rendering
- Client-side form state
- Server-side route guards that call FastAPI `/auth/me`
- Reverse proxying API requests under `/api/backend`
- Presentation-only report viewer replacement

## Revisit When

- Stripe checkout and webhooks are implemented
- PDF rendering and delivery are implemented
- Background jobs move to a durable queue
- SQLite is replaced or wrapped by a migration-managed database
```

- [ ] **Step 2: Commit**

Run:

```bash
git add .planning/research/NEXT_BACKEND_SPLIT.md
git commit -m "docs: record Next.js backend boundary"
```

---

## Migration Risks

1. **Cookies and same-origin behavior:** Current auth relies on same-origin browser calls. Use `/api/backend` rewrites or a production reverse proxy so the browser does not need cross-origin credentialed requests.
2. **Large file uploads:** Do not run upload traffic through a serverless Next.js deployment. Keep upload routes on FastAPI behind the same domain.
3. **Admin vs user route split:** Preserve `is_admin` behavior exactly. Non-admin users should land on `/wizard`; admin users should land on `/admin`.
4. **Background polling:** Keep 3 second polling for parity first. Replace with SSE or WebSockets only after the Next.js migration is stable.
5. **OpenAPI drift:** Generate TypeScript types from FastAPI OpenAPI after backend route changes.
6. **Legacy docs drift:** `.planning/codebase/TESTING.md` and some concern docs are stale. Update after cutover, not during initial scaffolding.

## Definition Of Done

- `http://localhost:3000` is the primary app URL.
- FastAPI still runs on `http://127.0.0.1:8765`.
- Login/register/logout work through Next.js.
- Regular users can complete the wizard through report queueing and status polling.
- Admin users can perform the current dashboard workflows.
- Python tests pass.
- Next.js typecheck passes.
- Playwright smoke tests pass.
- Legacy `frontend/index.html` is no longer the default app entry point.

## Self-Review

- Spec coverage: The plan covers server inspection, code inspection, auth/session preservation, API contract, UI migration, tests, cutover, and a backend-boundary decision.
- Placeholder scan: No task uses an unspecified implementation step. Each task names files, endpoints, commands, and expected results.
- Type consistency: `CurrentUser`, `Company`, `DocumentRow`, and `ReportStatus` names are defined before use. API helper names are consistent across tasks.

