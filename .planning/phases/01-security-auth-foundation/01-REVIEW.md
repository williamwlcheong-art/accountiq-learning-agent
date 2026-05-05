---
phase: 01-security-auth-foundation
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - pytest.ini
  - tests/__init__.py
  - tests/conftest.py
  - tests/test_security.py
  - tests/test_auth.py
  - .env.example
  - backend/requirements.txt
  - backend/main.py
  - frontend/index.html
  - backend/auth.py
  - backend/db.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-05-06
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 1 delivers JWT/cookie auth, CORS hardening, filename sanitisation, and an auth wall. The architectural shape is correct — `get_current_user` dependency is consistently applied across all protected routes, cookies are HttpOnly, and the frontend uses `textContent`/`createTextNode` for server data in most places. However, four critical issues remain: the empty `SECRET_KEY` guard is missing at token *creation* time (register/login proceed with an insecure empty key), internal DB error messages are leaked verbatim to HTTP clients, the `env_file` path is exposed in the API response, and `claude_model` received from an authenticated user is written to disk and to the live process without any validation. Several secondary warnings also require attention.

---

## Critical Issues

### CR-01: Token creation succeeds when SECRET_KEY is empty — auth bypass on misconfigured deployments

**File:** `backend/auth.py:51-54` and `backend/auth.py:103-134`, `backend/auth.py:137-155`

**Issue:** `get_current_user` (line 80) refuses to decode a token when `SECRET_KEY` is the empty string. However, neither `/auth/register` nor `/auth/login` checks `SECRET_KEY` before calling `create_access_token`. When the server starts without `SECRET_KEY` set, `jwt.encode(payload, "", algorithm="HS256")` succeeds — it produces a valid-looking token signed with an empty secret. That token will then be rejected by `get_current_user` with a 500, but the user has already received a session cookie containing a JWT signed by an empty key. If the empty-key check in `get_current_user` is ever relaxed (e.g., during testing where the guard is bypassed), those tokens become fully valid. The server silently allows registration/login to complete and set a cookie, giving users false confidence they are authenticated.

**Fix:**
```python
# auth.py — add at top of register and login, before hash_password / DB query
if not SECRET_KEY:
    raise HTTPException(500, "Server auth not configured")
```
Or centralise the guard inside `create_access_token`:
```python
def create_access_token(data: dict) -> str:
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured")
    to_encode = dict(data)
    to_encode["exp"] = datetime.now(UTC) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

---

### CR-02: Internal exception message leaked verbatim to HTTP clients

**File:** `backend/auth.py:129`, `backend/main.py:115`

**Issue:** Both the `register` route (`auth.py:129`) and `create_company` route (`main.py:115`) fall through to `raise HTTPException(500, str(e))` for any unexpected DB error. This surfaces raw SQLite exception text — including table names, column names, schema details, and potentially partial query strings — in the 500 response body. Any authenticated user triggering an unusual DB error receives internal implementation details that assist enumeration and exploitation.

**Fix:**
```python
# auth.py:129 and main.py:115 — replace str(e) with a generic message
raise HTTPException(500, "An internal error occurred. Please try again.")
# Log the actual exception server-side instead:
import logging
logging.exception("Unexpected DB error")
```

---

### CR-03: .env file path exposed in GET /settings response

**File:** `backend/main.py:398`

**Issue:** The `/settings` endpoint returns `"env_file": str(ENV_PATH)` in its JSON response. This hands every authenticated user the absolute filesystem path to the `.env` file (e.g. `/Users/william.cheong/accountiq_learning/.env`). This is a server-side path disclosure that reveals the deployment directory, username, and project structure — information useful for targeted attacks, especially if combined with path traversal vulnerabilities elsewhere.

**Fix:**
```python
# Remove env_file from the response entirely
return {
    "api_key_set": bool(key and not key.startswith("sk-ant-YOUR")),
    "api_key_preview": (key[:12] + "…" + key[-4:]) if len(key) > 20 else ("" if not key else "set"),
    "claude_model": os.environ.get("CLAUDE_MODEL") or ing.CLAUDE_MODEL,
}
```

---

### CR-04: Unvalidated `claude_model` value persisted to .env and loaded into the live process

**File:** `backend/main.py:421-424`

**Issue:** The `/settings` POST endpoint accepts `claude_model: str = Form(None)` and immediately writes any non-empty string to the `.env` file via `set_key` and into `os.environ` and `ing.CLAUDE_MODEL` with no allowlist validation. An authenticated user can set `claude_model` to an arbitrary string including newlines, shell metacharacters, or an excessively long value. Writing malformed values into a `.env` file via `python-dotenv`'s `set_key` can corrupt the file. Injecting a newline into the value could also add spurious lines to `.env` that override other keys (e.g., `SECRET_KEY`). The model string is later interpolated directly into API calls and the settings message (`msg += f" Model set to {claude_model}."`).

**Fix:**
```python
ALLOWED_MODELS = {
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5-20251001",
}

if claude_model:
    if claude_model not in ALLOWED_MODELS:
        raise HTTPException(400, f"Unknown model: {claude_model!r}")
    set_key(str(ENV_PATH), "CLAUDE_MODEL", claude_model)
    os.environ["CLAUDE_MODEL"] = claude_model
    ing.CLAUDE_MODEL = claude_model
    msg += f" Model set to {claude_model}."
```

---

## Warnings

### WR-01: Authentication is opt-in per route rather than enforced by middleware — new routes will be unprotected by default

**File:** `backend/main.py:81,102,122,139,166,228,253,272,303,324,343,373,390,406,435`

**Issue:** The CLAUDE.md security rule states "JWT tokens must be validated on every protected route via middleware — no route-level opt-in." The implementation uses `current_user: dict = Depends(get_current_user)` as a parameter on every individual route handler. This opt-in model means any future route added without the dependency will be publicly accessible. The `/health` and `/` routes are intentionally public, but every other route depends on a developer remembering to add the dependency. The `@app.on_event("startup")` route also has no auth (acceptable for server events, but worth noting).

**Fix:** Wire a global middleware or use FastAPI's `dependencies` parameter on the router/app level to enforce authentication by default, then explicitly exempt `/health`, `/`, and `/auth/*`.
```python
# Option: Use app-level dependency with exclusions
from fastapi import Request
PUBLIC_PATHS = {"/health", "/", "/auth/login", "/auth/register", "/auth/logout"}

@app.middleware("http")
async def require_auth(request: Request, call_next):
    if request.url.path not in PUBLIC_PATHS and not request.url.path.startswith("/app"):
        # validate cookie early — or keep using Depends but document the requirement explicitly
        ...
```

---

### WR-02: `apiPost` hardcodes `upload-alert` as the error display container for all POST calls

**File:** `frontend/index.html:1051,1053`

**Issue:** `apiPost` always calls `showAlert('upload-alert', ...)` on HTTP errors and network failures. When `addCompany()` calls `apiPost('/companies', fd)` and the server returns a non-200 (e.g., 409 conflict, 500), the error is displayed into `#upload-alert` — a container on the Upload tab, not the Companies tab where the user is. The user sees no feedback. This also means the `#company-alert` container is only populated on local validation failure (empty name), never on server-side failure.

**Fix:** Refactor `apiPost` to accept an optional `alertContainerId` parameter:
```javascript
async function apiPost(path, formData, alertContainerId = 'upload-alert') {
  try {
    const res = await fetch(API + path, { method: 'POST', body: formData, credentials: 'include' });
    if (res.status === 401) { showAuthWall(true); return null; }
    const json = await res.json();
    if (!res.ok) { showAlert(alertContainerId, json.detail || 'Error', 'error'); return null; }
    return json;
  } catch(e) { showAlert(alertContainerId, e.message, 'error'); return null; }
}
// Call sites:
const res = await apiPost('/companies', fd, 'company-alert');
```

---

### WR-03: `load_dotenv(ENV_PATH, override=True)` in main.py will overwrite environment variables set by CI/production

**File:** `backend/main.py:20`

**Issue:** Using `override=True` means the `.env` file values silently replace any environment variable already set in the shell or deployment environment. In CI, secrets are typically injected as real environment variables (not via `.env`). With `override=True`, if a `.env` file is accidentally present in the deployment context (e.g., committed, copied as part of a Docker build), it overwrites the production `SECRET_KEY` with whatever is in the file. The test conftest uses `override=False` precisely to avoid this — production code should do the same.

**Fix:**
```python
load_dotenv(ENV_PATH, override=False)
```

---

### WR-04: `COOKIE_SECURE` defaults to `False` — cookies sent over HTTP in production unless explicitly configured

**File:** `backend/auth.py:28`

**Issue:** `COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"` defaults to `False`. An `HttpOnly` cookie without `Secure` is transmitted over plain HTTP, making it susceptible to interception on any non-HTTPS network path. There is no documentation or startup warning indicating this must be set to `true` in production. The `.env.example` does not include a `COOKIE_SECURE` entry.

**Fix:** Add `COOKIE_SECURE=true` to `.env.example` with a comment, and emit a startup warning if running in a non-localhost environment without `COOKIE_SECURE=true`:
```python
# auth.py
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
if not COOKIE_SECURE:
    import warnings
    warnings.warn("COOKIE_SECURE is False — session cookies will be sent over HTTP. Set COOKIE_SECURE=true in production.")
```

---

### WR-05: `fresh_db` fixture only truncates `users` — cross-test contamination in other tables

**File:** `tests/conftest.py:57-67`

**Issue:** The `fresh_db` fixture deletes rows from `users` only. Tests that create companies or upload documents (e.g., `test_filename_traversal_basename_only`) write rows into `companies` and `documents`. Because the test DB is a single shared file for the entire test session (created once in `conftest.py` at module level), rows in other tables accumulate across tests. If test execution order changes, a test that expects zero companies (`GET /companies` returning `[]`) can fail because earlier tests left company rows behind. The `test_protected_route_with_auth` test calls `GET /companies` and asserts `200` but not the body — however future assertions on company count would break non-deterministically.

**Fix:** Either expand `fresh_db` to truncate all tables (respecting FK order), or use a per-test DB by creating a new `tempfile.mkstemp` in the fixture rather than at module import time.
```python
@pytest_asyncio.fixture
async def fresh_db():
    import aiosqlite
    async with aiosqlite.connect(_TMP_DB_PATH) as conn:
        try:
            await conn.execute("DELETE FROM extraction_log")
            await conn.execute("DELETE FROM financial_rows")
            await conn.execute("DELETE FROM label_patterns")
            await conn.execute("DELETE FROM documents")
            await conn.execute("DELETE FROM companies")
            await conn.execute("DELETE FROM users")
            await conn.commit()
        except Exception:
            pass
    yield
```

---

## Info

### IN-01: `print()` used for auth event logging instead of structured logging

**File:** `backend/auth.py:133,150,154`, `backend/main.py:62,221`

**Issue:** Login success, login failure, and registration events are logged via `print()`. `print()` goes to stdout with no timestamp, no log level, no correlation ID, and cannot be filtered or redirected by production log aggregators. Login failure events (line 150) are particularly important to capture for security monitoring (brute-force detection).

**Fix:** Replace with `logging.getLogger(__name__).info(...)` / `.warning(...)`. For auth events at minimum:
```python
import logging
logger = logging.getLogger("accountiq.auth")
logger.warning("Login failed for: %s", email)   # line 150
logger.info("Login OK: %s", email)              # line 154
logger.info("User registered: %s", email)       # line 133
```

---

### IN-02: `@app.on_event("startup")` is deprecated in FastAPI

**File:** `backend/main.py:59-62`

**Issue:** `@app.on_event("startup")` has been deprecated since FastAPI 0.93 in favour of the `lifespan` context manager. While it still works in >=0.111.0, it will generate deprecation warnings in logs and will eventually be removed.

**Fix:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[STARTUP] AccountIQ Learning Agent ready.")
    yield

app = FastAPI(..., lifespan=lifespan)
```

---

### IN-03: External link missing `rel="noopener noreferrer"`

**File:** `frontend/index.html:361`

**Issue:** `<a href="https://console.anthropic.com/settings/keys" target="_blank">` opens a new tab without `rel="noopener noreferrer"`. This allows the opened page a reference to `window.opener`, which is a minor security practice issue (tabnapping).

**Fix:**
```html
<a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer">console.anthropic.com</a>
```

---

_Reviewed: 2026-05-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
