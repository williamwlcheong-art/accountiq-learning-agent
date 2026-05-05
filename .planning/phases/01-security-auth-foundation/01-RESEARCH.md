# Phase 1: Security & Auth Foundation - Research

**Researched:** 2026-05-05
**Domain:** FastAPI JWT authentication, HTTP-only cookies, Python password hashing, XSS remediation, CORS hardening
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Auth wall — when unauthenticated, the entire app is hidden and only the login/register form is visible. No nav tabs, no content leakage.
- **D-02:** Login and register are on the same page, toggled by a "Create account" / "Back to login" link that swaps the form in place. No separate routes.
- **D-03:** After successful login/register, user lands on the Dashboard tab.
- **D-04:** Logout is a button in the top-right corner of the header alongside the user's email address. Always visible when authenticated.
- **D-05:** CORS: Replace `allow_origins=["*"]` with `["http://localhost:8765"]` for development.
- **D-06:** Filename: Replace `file.filename` with `Path(file.filename).name` at `main.py:166`.
- **D-07:** XSS: Replace all `element.innerHTML = serverData` patterns with `element.textContent` or `document.createTextNode()`. Claude narrative text and extraction log entries are primary vectors.
- Token storage: HTTP-only cookies, cookie name: `accountiq_session`.
- JWT expiry: 7 days. No refresh tokens in v1.
- Password minimum: 8 characters. No complexity rules.
- Auth middleware: FastAPI `Depends()` pattern extending `get_db`.
- `/health` remains public. All other routes require auth.
- `/settings` protected by same user auth, no admin-only gate.

### Claude's Discretion

- JWT library selection (PyJWT recommended — see research)
- Password hashing library (pwdlib with Argon2 recommended — see research)
- `users` table schema design
- `/auth/*` route structure
- Account page implementation detail (AUTH-08)

### Deferred Ideas (OUT OF SCOPE)

- Auto-refresh tokens before expiry
- Admin-only gate on `/settings`
- Email verification on registration
- "Remember me" / persistent sessions beyond 7 days
- Two-factor authentication
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | Platform restricts CORS to known origins (no wildcard `*` on write endpoints) | FastAPI `CORSMiddleware` with explicit `allow_origins` list; see CORS pattern below |
| AUTH-02 | File upload sanitises filename to basename only (no path traversal via `../../`) | One-line fix: `Path(file.filename).name` at `main.py:166` |
| AUTH-03 | Frontend renders all server/AI-generated text as plain text, not `innerHTML` | 19 innerHTML usages catalogued; high-risk ones identified; `textContent` / `createTextNode` / `DOMParser` strategies documented |
| AUTH-04 | User can create an account with email and password | `users` table + `POST /auth/register` endpoint with pwdlib Argon2 hashing |
| AUTH-05 | User can log in and remain logged in across browser sessions | `POST /auth/login` sets HTTP-only cookie; `GET /auth/me` validates on page load |
| AUTH-06 | User can log out from any page | `POST /auth/logout` clears cookie; frontend logout button in header |
| AUTH-08 | User can view their account details and report purchase history | `GET /auth/me` returns user data; account tab in frontend |
</phase_requirements>

---

## Summary

Phase 1 is a surgical hardening of an existing working FastAPI + Vanilla JS app. It splits into two tracks that can be partially parallelised: (1) three one-to-few-line security fixes — CORS origin restriction, filename basename sanitisation, and XSS innerHTML remediation — and (2) a full JWT authentication layer using HTTP-only cookies with register/login/logout/me endpoints and an auth wall in the frontend.

The security fixes (AUTH-01, AUTH-02, AUTH-03) are well-bounded. CORS is a single middleware argument change. The filename fix is one line. The XSS fix requires auditing all `innerHTML` assignments in `frontend/index.html` and distinguishing those that carry server/AI-generated user-influenced text (must be fixed) from those that only compose trusted HTML strings (lower priority). Nineteen `innerHTML` usages were identified; the six highest-risk ones (narrative body, log messages, pattern labels, company/document names, financial row labels) must use `createTextNode` or `textContent`.

The auth layer adds three new things to the backend: a `users` table, an `auth.py` module with route handlers, and a `get_current_user` dependency. Every existing route gets `current_user: dict = Depends(get_current_user)` added. The frontend receives an auth wall page, a `GET /auth/me` check on load, and a logout button. The current FastAPI docs (May 2026) recommend PyJWT (not python-jose, which is abandoned) and pwdlib with Argon2 (not passlib) for new projects — both libraries are confirmed available on PyPI.

**Primary recommendation:** Implement as three waves: Wave 0 (test scaffolding), Wave 1 (security fixes), Wave 2 (users table + auth backend), Wave 3 (auth wall + frontend integration). Keep all auth logic in a new `backend/auth.py` module to avoid polluting `main.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CORS policy enforcement | API / Backend | — | FastAPI middleware processes requests before route handlers |
| Filename sanitisation | API / Backend | — | Server-side, at the upload route, before disk write |
| XSS prevention | Frontend / Client | API (data source) | Browser renders HTML; fix is at the render site |
| JWT creation and signing | API / Backend | — | Secret key must never reach the client |
| JWT validation | API / Backend | — | HTTP-only cookie is unreadable by JS; server validates on each request |
| Password hashing | API / Backend | — | Hashing must happen server-side before any storage |
| Session state | Browser cookie | API (validates) | HTTP-only cookie is browser-managed; API validates on every request |
| Auth wall / UI gating | Frontend / Client | API (enforces) | JS hides the app; API refuses unauthenticated requests regardless |
| Login/register form | Frontend / Client | — | Purely UI; submits to API endpoints |
| Logout action | Frontend / Client | API (clears cookie) | Button in header triggers API which sets cookie expiry to past |

---

## Standard Stack

### Core Auth Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.12.1 | JWT encode/decode (HS256) | Official FastAPI docs recommendation as of 2025; python-jose abandoned |
| pwdlib[argon2] | 0.3.0 | Password hashing | Official FastAPI docs recommendation; Argon2 is OWASP-preferred algorithm |
| python-multipart | already installed | Form data parsing (already in requirements) | Required for FastAPI `Form()` — already in use |

### Supporting (already installed)

| Library | Version | Purpose |
|---------|---------|---------|
| aiosqlite | >=0.20.0 | Async SQLite for `users` table queries |
| python-dotenv | >=1.0.0 | Load `SECRET_KEY` from `.env` |
| fastapi | 0.136.1 | `Cookie()`, `Response.set_cookie()`, `Depends()` |

### Test Stack (Wave 0 additions)

| Library | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.3 | Test runner |
| pytest-asyncio | 1.3.0 | Async test support |
| httpx | 0.28.1 | FastAPI TestClient transport |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose 3.5.0 | python-jose last release was 3+ years ago; doesn't work cleanly on Python 3.10+; FastAPI docs migrated away from it |
| pwdlib[argon2] | passlib[bcrypt] | passlib last release was 1.7.4, no active maintenance; FastAPI docs migrated away; bcrypt 5.0.0 broke passlib's internal API |
| pwdlib[argon2] | bcrypt directly | More manual; pwdlib wraps with a clean verify/hash API and is the current recommendation |

**Installation (new dependencies only):**
```bash
pip install "pyjwt==2.12.1" "pwdlib[argon2]==0.3.0"
pip install "pytest==9.0.3" "pytest-asyncio==1.3.0" "httpx==0.28.1"
```

**Version verification:** [VERIFIED: pip3 index versions] — versions confirmed against PyPI on 2026-05-05.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (unauthenticated)
  │  GET /app  →  index.html
  │  JS: GET /auth/me  →  401
  │  Show: auth wall (login/register form only)
  │  Nav, pages hidden
  │
  │  POST /auth/register  →  201 + Set-Cookie: accountiq_session
  │  POST /auth/login     →  200 + Set-Cookie: accountiq_session
  │
Browser (authenticated — cookie present)
  │  JS: GET /auth/me  →  200 {id, email}
  │  Show: full app, Dashboard tab, user email + logout in header
  │
  │  All API calls include cookie automatically (credentials: 'include')
  │  GET /companies, GET /documents, POST /documents/upload ...
  │           │
  ┌───────────▼────────────────────────────────────────┐
  │  FastAPI backend/main.py                            │
  │                                                     │
  │  CORSMiddleware                                     │
  │    allow_origins=["http://localhost:8765"]          │
  │                                                     │
  │  /health  (public)                                  │
  │  /auth/register, /auth/login, /auth/logout          │
  │  /auth/me  (requires valid cookie)                  │
  │                                                     │
  │  All other routes: Depends(get_current_user)        │
  │    → reads Cookie("accountiq_session")              │
  │    → PyJWT decode → raises 401 if invalid           │
  │    → returns user dict to route handler             │
  │                                                     │
  │  File upload: Path(file.filename).name  (fix)       │
  └───────────────────┬─────────────────────────────────┘
                      │
              backend/auth.py
                      │
              ┌───────▼────────┐
              │  SQLite users  │
              │  table         │
              │  id, email,    │
              │  hashed_pw,    │
              │  created_at    │
              └────────────────┘
```

### Recommended Project Structure

```
backend/
├── main.py          # Add CORS fix, import auth router, add Depends(get_current_user) to all routes
├── auth.py          # NEW: users table init, register/login/logout/me routes, get_current_user dep
├── db.py            # Add users table to SCHEMA and init_db()
└── requirements.txt # Add PyJWT, pwdlib[argon2], pytest, pytest-asyncio, httpx

tests/
├── conftest.py      # NEW: test app fixture, test DB
├── test_auth.py     # NEW: register, login, logout, me, protected route tests
└── test_security.py # NEW: CORS, filename, XSS (backend assertions)
```

### Pattern 1: HTTP-only Cookie Set on Login

```python
# Source: https://fastapi.tiangolo.com/reference/responses (set_cookie API)
from fastapi import Response

@app.post("/auth/login")
async def login(response: Response, email: str = Form(...), password: str = Form(...), db = Depends(get_db)):
    user = await authenticate_user(db, email, password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token({"sub": str(user["id"]), "email": user["email"]})
    response.set_cookie(
        key="accountiq_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days in seconds
        secure=False,               # False for HTTP localhost; set True in production
    )
    return {"ok": True, "email": user["email"]}
```

### Pattern 2: get_current_user Dependency (Cookie-based)

```python
# Source: Context7 /websites/fastapi_tiangolo + /fastapi/fastapi (Cookie parameter)
# Adapted from FastAPI docs pattern — uses Cookie() instead of OAuth2PasswordBearer
from fastapi import Cookie
import jwt
from jwt.exceptions import InvalidTokenError

SECRET_KEY = os.environ.get("SECRET_KEY", "")
ALGORITHM = "HS256"

async def get_current_user(
    accountiq_session: str | None = Cookie(default=None),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    if not accountiq_session:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(accountiq_session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except InvalidTokenError:
        raise HTTPException(401, "Invalid or expired token")
    async with db.execute("SELECT id, email, created_at FROM users WHERE id=?", (user_id,)) as cur:
        user = await cur.fetchone()
    if not user:
        raise HTTPException(401, "User not found")
    return dict(user)
```

### Pattern 3: Password Hash/Verify with pwdlib

```python
# Source: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ (current docs)
from pwdlib import PasswordHash
password_hash = PasswordHash.recommended()  # defaults to Argon2

def hash_password(plain: str) -> str:
    return password_hash.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)
```

### Pattern 4: Adding Auth to Existing Routes

```python
# Source: [CITED: fastapi.tiangolo.com/tutorial/security/oauth2-jwt] — Depends() extension pattern
# Before (existing pattern):
@app.get("/companies")
async def list_companies(db: aiosqlite.Connection = Depends(get_db)):
    ...

# After — minimal change, consistent with existing Depends(get_db) pattern:
@app.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ...
```

### Pattern 5: XSS Fix Strategy for innerHTML

The 19 `innerHTML` usages in `frontend/index.html` fall into three categories:

**Category A — Trusted HTML only (safe as-is, no server strings interpolated into tag attributes or text content):**
- Line 403: `tbody.innerHTML = '<tr><td colspan="7"...static string...</td></tr>'` — empty state message, no server data
- Line 526: same pattern for documents empty state
- Line 614: `fin-table-wrap` empty state — static string
- Line 718/719: `showAlert` — message arg is local JS strings, not server data (BUT: verify callers)

**Category B — Server-user data interpolated into HTML (MUST fix — XSS vector):**

| Line | Element | Data Source | Fix |
|------|---------|-------------|-----|
| 375-380 | `exchange-list` | `e.exchange` (company name) from DB | Build DOM with `createElement` + `textContent` |
| 384-392 | `conf-list` | `r.row_key` (AI-extracted key) from DB | Build DOM with `createElement` + `textContent` |
| 404-412 | `companies-tbody` | `c.name`, `c.ticker`, `c.sector` from DB | Build rows with `createElement` + `textContent` |
| 454-458 | company `<select>` options | `c.name` from DB | Build `<option>` elements with `textContent` |
| 505-514 | `jobs-list` | `job.filename`, `l.message` (extraction log) | Build DOM nodes; escape log messages via `textContent` |
| 527-545 | `documents-tbody` | `d.filename`, `d.company_name`, `d.narrative` | Build rows with `createElement`; `encodeURIComponent` on narrative already done for onclick attr — verify |
| 583-598 | `pattern-grid` | `p.label` (raw PDF label — AI/user data) | Build DOM with `createElement` + `textContent` |
| 631-645 | `fin-table-wrap` | `r.label` (AI-extracted row label) from DB | Build `<td>` with `textContent` for label column |
| 745-750 | `narrative-body` | Claude narrative text (highest risk — AI output) | Use `DOMParser` or build `<p>` elements with `textContent` |

**The narrative body (line 745) is the highest-priority fix** — it directly renders Claude-generated text that reflects PDF content. The current approach splits on `\n\n` and injects with `innerHTML`. Fix: create `<p>` elements, set `.textContent` on each, append to container.

**Category C — Static HTML with server data in safe positions:**
- Line 656/659: `settings-status` — displays API key preview; `api_key_preview` is a masked string from the server. Should use `textContent` for the preview value even if rest is static HTML.

### Anti-Patterns to Avoid

- **Using `innerHTML` for dynamic content with server data:** Even "safe" server strings can contain `<script>` if the source is ever user-influenced. Use `createElement` + `textContent` for any server value.
- **Storing JWT in `localStorage` instead of HTTP-only cookie:** localStorage is readable by any JS, defeating XSS protection. The decision to use HTTP-only cookies is locked and correct.
- **Route-level opt-in for auth (no default protection):** Each new route would require remembering to add the dependency. The existing app adds `Depends(get_db)` to every route — auth follows the same pattern. This is not a FastAPI middleware that intercepts globally; it is a dependency that must be added to each route. The plan must explicitly enumerate all routes to protect.
- **Storing plain-text passwords or weak hashes (MD5, SHA-1):** Use Argon2 via pwdlib — it is OWASP-recommended and the current FastAPI standard.
- **Hardcoding `SECRET_KEY`:** Must come from `.env` via `python-dotenv`. Generate with `openssl rand -hex 32`. Add `SECRET_KEY` to `.env` as part of Wave 0 or Wave 2.
- **Using `secure=True` on cookie in HTTP dev:** The dev server runs on HTTP (`localhost:8765`). Setting `secure=True` will prevent the browser from sending the cookie. Use `secure=False` for dev; add env-based flag for production.
- **Not setting `samesite="lax"`:** Without SameSite, the cookie is sent on cross-site requests, enabling CSRF. `lax` is the browser default for new cookies but should be explicit.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt wrapper, MD5/SHA | `pwdlib[argon2]` | Argon2 is timing-safe, salted, OWASP-recommended; rolling own is error-prone |
| JWT encode/decode | Manual HMAC, custom token format | `PyJWT` | Handles expiry, algorithm selection, exception hierarchy; audited library |
| Timing-safe comparison | `==` on password strings | pwdlib's `verify()` | `verify()` uses constant-time comparison; `==` leaks timing |
| CORS | Manual `Access-Control-Allow-Origin` header in routes | `CORSMiddleware` | Handles preflight, method/header allowlists correctly |
| Cookie attributes | Manual `Set-Cookie` header | `response.set_cookie()` | Correct `httponly`, `samesite`, `max_age` attribute formatting |

**Key insight:** In auth, every custom implementation path has failure modes that are non-obvious and security-critical. Use audited library abstractions for every crypto operation.

---

## Common Pitfalls

### Pitfall 1: Python 3.10+ Deprecation Warning from passlib/python-jose
**What goes wrong:** If passlib or python-jose are accidentally used, they emit `DeprecationWarning: datetime.utcnow() is deprecated` on Python 3.10+. The project runs Python 3.13.6.
**Why it happens:** Both libraries call `datetime.utcnow()` internally, which is deprecated in Python 3.10.
**How to avoid:** Use PyJWT 2.12.1 and pwdlib 0.3.0 — both are Python 3.13 compatible.
**Warning signs:** `DeprecationWarning` in server logs referencing `utcnow`.

### Pitfall 2: HTTP-only Cookie Not Sent — Missing `credentials: 'include'`
**What goes wrong:** The frontend makes API calls that return 401 even after login, because the browser doesn't send the cookie.
**Why it happens:** Cookies are not sent with `fetch()` by default unless `credentials: 'include'` is set. The existing `apiFetch` and `apiPost` helpers do NOT include this.
**How to avoid:** Both `apiFetch` and `apiPost` must add `credentials: 'include'` to their fetch options. This is a one-line change in each helper — centralised, so all API calls get it automatically.
**Warning signs:** Cookie visible in DevTools Application tab but not appearing in request headers.

### Pitfall 3: CORS Blocks Cookie on Same-Origin App
**What goes wrong:** With HTTP-only cookies, `credentials: 'include'` requires `allow_credentials=True` in `CORSMiddleware` AND the `allow_origins` list must NOT be `["*"]` (a wildcard is invalid when credentials are enabled).
**Why it happens:** CORS spec prohibits `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials: true`.
**How to avoid:** Set `allow_origins=["http://localhost:8765"]` (explicit) AND `allow_credentials=True` when credentials are needed. Note: since the frontend is served from the same origin as the API, CORS is technically not needed for same-origin calls — but the middleware should be correct regardless.
**Warning signs:** Console error: "The value of the 'Access-Control-Allow-Origin' header in the response must not be the wildcard '*' when the request's credentials mode is 'include'."

### Pitfall 4: `secure=True` Cookie Not Sent on HTTP localhost
**What goes wrong:** Cookie is set successfully but never sent back by the browser.
**Why it happens:** `Secure` attribute means "HTTPS only". `localhost:8765` runs on HTTP.
**How to avoid:** Use `secure=False` for dev. In production, the cookie must be `secure=True`. Make this configurable via env var.
**Warning signs:** Login succeeds (201/200), but subsequent `/auth/me` returns 401.

### Pitfall 5: All Routes Need Explicit `Depends(get_current_user)` — No Global Middleware
**What goes wrong:** Some existing routes are left unprotected because the dependency was not added to their signature.
**Why it happens:** FastAPI's `Depends()` is route-level, not global. There is no automatic catch-all.
**How to avoid:** The plan must enumerate every route in `main.py` that needs protecting: `/companies` (GET, POST), `/companies/{id}` (GET), `/documents` (GET), `/documents/upload` (POST), `/documents/{id}/status` (GET), `/documents/{id}/rows` (GET), `/documents/{id}/retry` (POST), `/financials/{id}` (GET), `/patterns` (GET), `/patterns/export` (GET), `/analytics/overview` (GET), `/analytics/confidence` (GET), `/settings` (GET, POST).
**Warning signs:** Unauthenticated requests to a route succeed (200) instead of returning 401.

### Pitfall 6: XSS innerHTML — `encodeURIComponent` is Not Sanitisation
**What goes wrong:** Line 541 encodes the narrative for the `onclick` attribute but then decodes it with `decodeURIComponent` before passing to `innerHTML` on line 745. The encode/decode round-trip does not strip HTML tags.
**Why it happens:** `encodeURIComponent` is URL-encoding, not HTML escaping. `<script>alert(1)</script>` survives the round-trip.
**How to avoid:** The narrative body must use DOM creation with `textContent`, not `innerHTML`, after decoding. The `onclick` attribute interpolation of narrative content is a secondary vector if the string contains single quotes — the existing `replace(/'/g,"\\'")` helps but DOM-based approach is safer.
**Warning signs:** Narrative text with `<b>` or `<script>` renders as HTML in the modal.

### Pitfall 7: `SECRET_KEY` Not in `.env`
**What goes wrong:** JWT signing uses an empty or default secret, making all tokens trivially forgeable.
**Why it happens:** The key is only added to `.env` if explicitly planned.
**How to avoid:** Wave 0 or Wave 2 must include: generate key with `openssl rand -hex 32`, add `SECRET_KEY=<value>` to `.env`, add `SECRET_KEY=your-secret-here` placeholder to `.env.example` if one exists.

---

## XSS Fix Inventory (AUTH-03)

Complete audit of `frontend/index.html` `innerHTML` assignments:

| Line | Function | Data | Risk | Fix Strategy |
|------|----------|------|------|--------------|
| 375 | `loadDashboard` | `e.exchange` (server) | Medium | `createElement` + `textContent` |
| 384 | `loadDashboard` | `r.row_key` (AI data) | High | `createElement` + `textContent` |
| 403 | `loadCompanies` | Static empty-state string | None | Leave as-is |
| 404 | `loadCompanies` | `c.name`, `c.ticker`, `c.sector` (server) | High | `createElement` + `textContent` for data cells |
| 456-458 | `populateCompanySelects` | `c.name` (server) | High | `createElement('option')` + `textContent` |
| 505 | `renderJobs` | `job.filename`, `l.message` (server/AI) | High | `createElement` + `textContent` for text |
| 526 | `loadDocuments` | Static empty-state string | None | Leave as-is |
| 527 | `loadDocuments` | `d.filename`, `d.company_name` (server) | High | `createElement` + `textContent` for data cells |
| 583 | `loadPatterns` | `p.label` (raw PDF label = user-influenced) | High | `createElement` + `textContent` |
| 614 | `loadFinancials` | Static empty-state string | None | Leave as-is |
| 645 | `loadFinancials` | `r.label` (AI-extracted row label) | High | `createElement('td')` + `textContent` for label column |
| 656 | `loadSettings` | `s.api_key_preview` (server) | Low | Use `textContent` on the `<code>` element |
| 659 | `loadSettings` | Static string | None | Leave as-is |
| 718 | `showAlert` | `msg` param — callers pass local strings | Low | Review callers; `msg` from `json.detail` is server data → use `textContent` |
| 719 | `showAlert` | Same | Low | Same |
| 745 | `viewNarrative` | Claude narrative text (AI output from PDF) | **Critical** | Create `<p>` elements, set `.textContent`, append to `#narrative-body` |

**Note on table rows (lines 404, 527):** Building entire `<tr>` structures via `innerHTML` is common practice when the HTML skeleton is trusted and only leaf text nodes contain server data. The correct fix is either: (a) build the full row via DOM methods, or (b) build the HTML scaffold with safe static parts and insert server data only via `textContent` on the created elements. Option (b) is less verbose for complex rows. The plan should specify which approach.

---

## Code Examples

### users Table Schema
```sql
-- Source: [ASSUMED] — following existing db.py schema conventions
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT    NOT NULL UNIQUE,
    hashed_pw    TEXT    NOT NULL,
    created_at   TEXT    DEFAULT (datetime('now'))
);
```

### JWT Token Creation
```python
# Source: [CITED: fastapi.tiangolo.com/tutorial/security/oauth2-jwt]
import jwt
from datetime import datetime, timedelta, UTC

SECRET_KEY = os.environ.get("SECRET_KEY", "")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(UTC) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

### Frontend Auth Check on Page Load
```javascript
// Source: [ASSUMED] — follows existing apiFetch pattern + D-01/D-03 decisions
async function initApp() {
  const user = await apiFetch('/auth/me');  // apiFetch must have credentials: 'include'
  if (!user) {
    // 401 response — show auth wall
    document.getElementById('auth-page').style.display = 'flex';
    document.getElementById('main-app').style.display = 'none';
    return;
  }
  // Authenticated — show app
  document.getElementById('auth-page').style.display = 'none';
  document.getElementById('main-app').style.display = 'block';
  document.getElementById('user-email').textContent = user.email;
  showPage('dashboard');
}
```

### apiFetch / apiPost with credentials
```javascript
// Source: [ASSUMED] — standard fetch credentials pattern
// Add to both helpers: credentials: 'include'
async function apiFetch(path) {
  try {
    const res = await fetch(API + path, { credentials: 'include' });
    if (res.status === 401) { showAuthWall(); return null; }
    if (!res.ok) { console.error(await res.text()); return null; }
    return res.json();
  } catch(e) { console.error(e); return null; }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-jose` for JWT | `PyJWT` | FastAPI docs updated ~2024 (PR #11589) | python-jose incompatible with Python 3.10+ utcnow deprecation |
| `passlib[bcrypt]` for hashing | `pwdlib[argon2]` | FastAPI docs updated ~2024 | passlib maintenance stopped; bcrypt 4.x+ broke passlib internals |
| `datetime.utcnow()` | `datetime.now(UTC)` | Python 3.10 deprecation | Affects any auth library using `utcnow()` |
| Bearer token in Authorization header | HTTP-only cookie | Pattern shift for XSS-sensitive apps | Cookie not readable by JS — survives XSS attacks |

**Deprecated/outdated:**
- `python-jose`: Last release 3.5.0 ~3 years ago; FastAPI docs no longer recommend it. [VERIFIED: PyPI registry, GitHub discussion #11345]
- `passlib`: Last release 1.7.4 ~3 years ago; bcrypt 5.0.0 breaks passlib. [VERIFIED: pip3 index versions]
- `@app.on_event("startup")`: Already noted in CONCERNS.md as deprecated; not in scope for this phase but noted.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `users` table schema uses `email TEXT UNIQUE` as the primary identifier | Code Examples | If a `username` field is also needed, schema needs adjustment — low risk, email-only auth is standard |
| A2 | Frontend auth wall implemented as a separate `#auth-page` div toggled by JS `display` style | Architecture Patterns | If implemented differently (e.g., CSS class), JS snippets in patterns need adjustment |
| A3 | `showAlert` callers only pass locally-constructed strings (not raw server `detail` strings) | XSS Fix Inventory | If `json.detail` from API errors is passed to `showAlert`, it becomes a low-severity XSS vector via `innerHTML` |
| A4 | `secure=False` for dev cookie is acceptable project policy | Common Pitfalls | If team decides to run a local HTTPS proxy, flip to `True` |
| A5 | `SECRET_KEY` will be added to `.env` before testing (not pre-existing) | Code Examples | If forgotten, JWTs are signed with empty string and are trivially forgeable |

---

## Open Questions (RESOLVED)

1. **Account details page (AUTH-08)**
   - What we know: AUTH-08 requires user to view account details and report purchase history. No reports exist yet (Phase 5). The "purchase history" will be empty.
   - What's unclear: Does the planner implement a placeholder account page that shows just `email` + `created_at`, or defer the full page to Phase 5/6?
   - Recommendation: Implement a minimal account tab/page with email + registration date. Add a "No reports yet" placeholder for purchase history. This satisfies AUTH-08 without blocking on non-existent data.
   - RESOLVED: Plan 04 implements an Account tab showing `email` + `created_at` with a "No reports purchased yet" placeholder. AUTH-08 satisfied without dependency on Phase 5/6.

2. **CORS `allow_credentials` requirement**
   - What we know: HTTP-only cookies with `credentials: 'include'` require `allow_credentials=True` in `CORSMiddleware` when requests come from a different origin.
   - What's unclear: Since the frontend is served from the same origin (`localhost:8765/app`), same-origin requests do NOT trigger CORS. The `CORSMiddleware` with `allow_credentials=True` is only needed if the frontend is ever served separately.
   - Recommendation: Set `allow_credentials=True` now when restricting origins, as a future-proofing measure. It is harmless for same-origin requests and correct for any future separation.
   - RESOLVED: Plan 02 Task 1 sets `allow_credentials=True` alongside `allow_origins=["http://localhost:8765"]` as a future-proofing measure per the recommendation.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | PyJWT, pwdlib | ✓ | 3.13.6 | — |
| FastAPI | All routes | ✓ | 0.136.1 | — |
| aiosqlite | users table queries | ✓ | >=0.20.0 (in requirements) | — |
| PyJWT | JWT create/validate | ✗ (not installed) | 2.12.1 available on PyPI | — |
| pwdlib[argon2] | Password hashing | ✗ (not installed) | 0.3.0 available on PyPI | — |
| pytest | Test runner | ✗ (not installed) | 9.0.3 available on PyPI | — |
| pytest-asyncio | Async tests | ✗ (not installed) | 1.3.0 available on PyPI | — |
| httpx | TestClient transport | ✗ (not installed) | 0.28.1 available on PyPI | — |
| python-multipart | Form parsing | ✓ (in requirements) | >=0.0.9 | — |

**Missing dependencies with no fallback:**
- PyJWT, pwdlib[argon2] — required for auth implementation; must be installed in Wave 0.

**Missing dependencies with fallback:**
- None — all missing items are installable via pip with no alternative needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` — Wave 0 creates this |
| Quick run command | `cd /Users/William.Cheong/accountiq_learning && pytest tests/ -x -q` |
| Full suite command | `cd /Users/William.Cheong/accountiq_learning && pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Cross-origin POST to `/companies` returns CORS error | integration | `pytest tests/test_security.py::test_cors_restricted -x` | ❌ Wave 0 |
| AUTH-01 | Same-origin request to write endpoint succeeds (control) | integration | `pytest tests/test_security.py::test_cors_allowed_origin -x` | ❌ Wave 0 |
| AUTH-02 | Upload with `../../evil.py` filename saves only basename | integration | `pytest tests/test_security.py::test_filename_traversal -x` | ❌ Wave 0 |
| AUTH-03 | Narrative text with `<script>` renders as text in modal | manual | Browser test only — DOM manipulation not testable via pytest | manual |
| AUTH-04 | `POST /auth/register` with valid email+password returns 201 + cookie | integration | `pytest tests/test_auth.py::test_register_success -x` | ❌ Wave 0 |
| AUTH-04 | `POST /auth/register` with password < 8 chars returns 422 | integration | `pytest tests/test_auth.py::test_register_short_password -x` | ❌ Wave 0 |
| AUTH-04 | Duplicate email registration returns 409 | integration | `pytest tests/test_auth.py::test_register_duplicate -x` | ❌ Wave 0 |
| AUTH-05 | `POST /auth/login` sets `accountiq_session` cookie | integration | `pytest tests/test_auth.py::test_login_sets_cookie -x` | ❌ Wave 0 |
| AUTH-05 | Cookie is `httponly` and has 7-day `max_age` | integration | `pytest tests/test_auth.py::test_cookie_attributes -x` | ❌ Wave 0 |
| AUTH-05 | `GET /auth/me` with valid cookie returns user data | integration | `pytest tests/test_auth.py::test_me_authenticated -x` | ❌ Wave 0 |
| AUTH-05 | `GET /auth/me` without cookie returns 401 | integration | `pytest tests/test_auth.py::test_me_unauthenticated -x` | ❌ Wave 0 |
| AUTH-06 | `POST /auth/logout` clears the cookie | integration | `pytest tests/test_auth.py::test_logout -x` | ❌ Wave 0 |
| AUTH-06 | Protected route after logout returns 401 | integration | `pytest tests/test_auth.py::test_protected_after_logout -x` | ❌ Wave 0 |
| AUTH-08 | `GET /auth/me` returns `id`, `email`, `created_at` | integration | `pytest tests/test_auth.py::test_me_returns_user_fields -x` | ❌ Wave 0 |
| — | Unauthenticated request to `/companies` returns 401 | integration | `pytest tests/test_auth.py::test_protected_route_no_auth -x` | ❌ Wave 0 |
| — | Authenticated request to `/companies` returns 200 | integration | `pytest tests/test_auth.py::test_protected_route_with_auth -x` | ❌ Wave 0 |

AUTH-03 (XSS) is the only requirement that is manual-only — DOM rendering behaviour cannot be verified via API tests. Verification is: open browser DevTools, confirm `narrative-body` children are `<p>` elements with `.textContent` matching narrative text (no child elements).

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q` (fail-fast, quiet)
- **Per wave merge:** `pytest tests/ -v` (full verbose output)
- **Phase gate:** Full suite green before `/gsd-verify-work` + manual browser XSS check

### Wave 0 Gaps

- [ ] `pytest.ini` — configure asyncio_mode = "auto" for pytest-asyncio
- [ ] `tests/__init__.py` — empty, makes tests a package
- [ ] `tests/conftest.py` — test app with in-memory SQLite DB fixture
- [ ] `tests/test_auth.py` — all AUTH-04/05/06/08 test stubs
- [ ] `tests/test_security.py` — AUTH-01/02 test stubs
- [ ] Install: `pip install pytest==9.0.3 pytest-asyncio==1.3.0 httpx==0.28.1`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | PyJWT HS256, pwdlib Argon2, 8-char minimum password |
| V3 Session Management | yes | HTTP-only cookie, 7-day max_age, SameSite=lax, logout clears cookie |
| V4 Access Control | yes | `Depends(get_current_user)` on all protected routes; 401 for missing/invalid token |
| V5 Input Validation | yes | FastAPI `Form()` type validation; email format check on register; password length check |
| V6 Cryptography | yes | Argon2 via pwdlib (never hand-roll); HS256 JWT with env-loaded SECRET_KEY |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via innerHTML with AI-generated content | Tampering / Elevation of Privilege | Replace `innerHTML` with `textContent`/`createElement`; HTTP-only cookie survives XSS |
| Path traversal via uploaded filename | Tampering | `Path(file.filename).name` — basname only |
| Cross-origin forged write requests (CSRF-lite via CORS) | Spoofing | Restrict `allow_origins` to known origin; SameSite=lax on cookie |
| Stolen JWT from localStorage | Information Disclosure | Use HTTP-only cookie — not accessible to JS |
| Brute-force password attack | Elevation of Privilege | Argon2 is slow by design; rate limiting deferred to v2 |
| Weak or hardcoded SECRET_KEY | Spoofing / Elevation | Load from `.env`; generate with `openssl rand -hex 32`; never commit to git |
| Session fixation | Spoofing | Issue new JWT on login (not reuse existing); logout deletes cookie |

---

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/fastapi_tiangolo` — HTTP-only cookie `set_cookie` API, `Cookie()` parameter, `TestClient` usage
- Context7 `/fastapi/fastapi` — `Cookie()` parameter declaration
- Context7 `/mpdavis/python-jose` — JWT encode/decode patterns (referenced for comparison; PyJWT preferred)
- Context7 `/websites/passlib_readthedocs_io_en_stable` — bcrypt/CryptContext patterns (referenced for comparison; pwdlib preferred)
- [PyPI registry via pip3 index versions] — confirmed versions: PyJWT 2.12.1, pwdlib 0.3.0, pytest 9.0.3, pytest-asyncio 1.3.0, httpx 0.28.1
- [fastapi.tiangolo.com/tutorial/security/oauth2-jwt] — current docs use `PyJWT` and `pwdlib[argon2]` [VERIFIED: WebFetch 2026-05-05]
- [fastapi.tiangolo.com/reference/responses] — `set_cookie()` API signature [VERIFIED: Context7]

### Secondary (MEDIUM confidence)
- GitHub discussion fastapi/fastapi #11345 — confirmation that FastAPI officially moved from python-jose to PyJWT [VERIFIED: WebFetch]
- Codebase grep of `frontend/index.html` — all 19 `innerHTML` usages catalogued and categorised [VERIFIED: local grep]

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — library versions verified against PyPI registry; docs confirmed via WebFetch
- Architecture: HIGH — based on reading actual backend/main.py and frontend/index.html source
- Pitfalls: HIGH — grounded in code audit (actual lines cited) and verified library behaviour
- XSS inventory: HIGH — based on complete grep of all innerHTML usages with line numbers

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (stable libraries; PyJWT and pwdlib are not fast-moving)
