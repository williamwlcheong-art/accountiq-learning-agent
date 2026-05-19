---
phase: 04-extraction-quality
reviewed: 2026-05-19T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - backend/ingestion.py
  - backend/main.py
  - backend/requirements.txt
  - backend/rule_extractor.py
  - frontend/index.html
  - tests/test_extraction.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-19
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 4 delivers multi-format text extraction (PDF/OCR/Excel/Word), multi-page scoring and selection, Claude tool-use extraction with rule-based fallback, and sign normalisation for cost keys. The implementation is generally well-structured and the security posture (CORS locked to localhost, parameterised queries, `.textContent` throughout the frontend) is solid.

Three blockers were found: an `IndexError` crash when `rule_based_extract` is called with an empty page list, a `dashboard` stat card that always displays `undefined` because `label_patterns` is absent from the `/analytics/overview` response, and `asyncio.get_event_loop()` used inside an already-running async context in `call_claude` — deprecated in Python 3.10+ and raises a `DeprecationWarning` (and will error in future Python). Additionally, `rule_based_extract` silently omits CF and EQ extraction despite CF/EQ synonym dictionaries existing, a filename collision race in the PDF-upload temp path exists, and the FY year normalisation has an off-by-one for 3-digit FY strings.

---

## Critical Issues

### CR-01: IndexError crash when `_extract_statement` called with empty page list

**File:** `backend/rule_extractor.py:295-297`

**Issue:** When `pages` is empty, `scores` is also empty. The `if scores else 0` guard sets `best_idx = 0`, but the very next line `scores[best_idx]` raises `IndexError: list index out of range` because the list is empty. This crashes the rule-based fallback path and will bubble up to mark the document as `failed`.

```python
# Current (line 295-297)
scores = [_score_page(p, syns) for p in pages]
best_idx = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
if scores[best_idx] < 2:   # IndexError when scores == []
```

**Fix:**
```python
scores = [_score_page(p, syns) for p in pages]
if not scores:
    return {}
best_idx = max(range(len(scores)), key=lambda i: scores[i])
if scores[best_idx] < 2:
    return {}
```

---

### CR-02: Dashboard "Label Patterns" stat always shows `undefined`

**File:** `frontend/index.html:562` / `backend/main.py:800-806`

**Issue:** The frontend reads `ov.label_patterns` from the `/analytics/overview` response, but the backend explicitly omits that key (with a comment at line 798-799 noting it is intentional to avoid leaking cross-user data volume). The result is `undefined` is set as `textContent`, showing "undefined" or NaN to the user on every dashboard load — a permanent visual bug.

```javascript
// frontend line 562 — reads a field that does not exist
document.getElementById('stat-patterns').textContent = ov.label_patterns;
```

The backend response (`main.py:800-806`) contains only: `companies`, `documents`, `docs_done`, `financial_rows`, `by_exchange`. `label_patterns` is never included.

**Fix (option A — remove the stat card):** Delete the "Label Patterns" stat card from the HTML and the assignment at line 562.

**Fix (option B — fetch separately):** After `loadDashboard()` fetches `/analytics/overview`, make a second call to `/patterns` and count the results:
```javascript
const patterns = await apiFetch('/patterns');
document.getElementById('stat-patterns').textContent = patterns ? patterns.length : '—';
```

---

### CR-03: `asyncio.get_event_loop()` used inside a running event loop

**File:** `backend/ingestion.py:372`

**Issue:** `call_claude` is an `async` function called from within an already-running asyncio event loop. `asyncio.get_event_loop()` is deprecated inside a running loop since Python 3.10 (`DeprecationWarning`) and raises a `RuntimeError` in Python 3.12+. The correct call is `asyncio.get_running_loop()`, which is already used correctly elsewhere in the same file (line 517). This will silently emit warnings on Python 3.10/3.11 and hard-crash on Python 3.12.

```python
# Line 372 — wrong
loop = asyncio.get_event_loop()
```

**Fix:**
```python
loop = asyncio.get_running_loop()
```

---

## Warnings

### WR-01: `rule_based_extract` never extracts CF or EQ statements

**File:** `backend/rule_extractor.py:369-405`

**Issue:** `CF_SYNS` and `EQ_SYNS` are defined (lines 159–199) and are used for page scoring in `extract_pdf_text` (via `ingestion.py` import), but `rule_based_extract` only calls `_extract_statement` for `PNL_SYNS` and `BS_SYNS`. Cash flow and equity movements data is silently omitted from the rule-based fallback. For Claude-extracted documents this is fine (Claude returns `cf`/`eq` rows), but when falling back to rule-based extraction users get incomplete data with no warning.

**Fix:** Add CF and EQ extraction calls:
```python
cf_data = _extract_statement(text_pages, CF_SYNS)
eq_data = _extract_statement(text_pages, EQ_SYNS)

for key, vals in cf_data.items():
    if vals:
        rows.append({"statement": "cf", "canonical_key": key,
                     "raw_label": key.replace("_", " "), "values": vals, "confidence": 0.65})
for key, vals in eq_data.items():
    if vals:
        rows.append({"statement": "eq", "canonical_key": key,
                     "raw_label": key.replace("_", " "), "values": vals, "confidence": 0.65})
```

---

### WR-02: Filename collision race in PDF upload temp path

**File:** `backend/main.py:561-573` / `backend/main.py:586-589`

**Issue:** When `company_id` is `None` for a PDF upload, the file is saved to `data/pdfs/_tmp/<safe_name>` (line 561). If two concurrent uploads arrive with the same filename (e.g. two users both upload `financial_report.pdf`), the second write truncates the first file before `_extract_company_name_from_pdf_sync` has read it. The subsequent `shutil.move` also moves the wrong (corrupted) file to the company directory.

Additionally, if name extraction fails and `resolved_name` falls back to `Path(file.filename).stem` (line 570), the tmp file is still present but the `shutil.move` at line 589 uses `safe_name` (the original filename), so a race between two uploads of different PDFs whose filenames map to different company dirs won't collide — but two uploads of the same filename for different users will corrupt each other.

**Fix:** Use a UUID-prefixed temp filename or Python's `tempfile.mkstemp` to guarantee uniqueness:
```python
import uuid
tmp_path = tmp_dir / f"{uuid.uuid4().hex}_{Path(file.filename).name}"
```
And propagate `tmp_path` through to the `shutil.move` instead of recomputing from `safe_name`.

---

### WR-03: FY 3-digit year produces wrong centuries

**File:** `backend/rule_extractor.py:239-241`

**Issue:** The regex `FY\s?\d{2,4}` matches 2–4 digit suffixes. The normalisation at line 240–241 always takes the last two characters: `'20' + m[-2:]`. For a 4-digit FY (`FY2025`) this gives `2025` correctly. For a 2-digit FY (`FY25`) this also gives `2025` correctly. But for a 3-digit FY string (`FY202`) — which can appear in some OCR-corrupted documents — it yields `2002` instead of a parse error or `2202`. While rare, a document with garbled OCR could produce this path, silently inserting data under the wrong year key.

**Fix:** Reject 3-digit FY tokens by updating the normalisation guard:
```python
m = m.replace(' ', '')
if m.startswith('FY'):
    suffix = m[2:]  # digits after 'FY'
    if len(suffix) == 2:
        yr = '20' + suffix
    elif len(suffix) == 4:
        yr = suffix
    else:
        continue  # skip malformed FY tokens
else:
    yr = m
```

---

### WR-04: `innerHTML` with template literals containing server-provided integer counts

**File:** `frontend/index.html:1740,1745`

**Issue:** Two `wrap.innerHTML` assignments use template literal interpolation with `processing.length` and `failed.length` (lines 1740 and 1745). These values are derived from `docs.filter(...)` on server-returned JSON, so the counts are integers from the API response — not user-controlled strings. In the current implementation the values are JavaScript array lengths (always integers), making actual XSS impossible here. However, the pattern violates the project's explicit rule ("Never use `.innerHTML`...for user-influenced text") and sets a precedent that could be copied for genuinely unsafe fields.

**Fix:** Replace with DOM construction:
```javascript
const div = document.createElement('div');
div.className = 'empty';
div.textContent = `Extraction in progress for ${processing.length} document(s) — check back in a moment.`;
wrap.appendChild(div);
```

---

### WR-05: `@app.on_event("startup")` is deprecated

**File:** `backend/main.py:60-63`

**Issue:** `@app.on_event("startup")` was deprecated in FastAPI 0.93 and removed in later versions. The project uses `fastapi>=0.111.0`, where this decorator still works but emits a `DeprecationWarning`. The idiomatic replacement is a `lifespan` context manager.

**Fix:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[STARTUP] AccountIQ Learning Agent ready.")
    yield

app = FastAPI(
    title="AccountIQ Learning Agent",
    lifespan=lifespan,
    ...
)
```

---

## Info

### IN-01: `rule_based_extract` always sets `raw_label` to the synthetic key name

**File:** `backend/rule_extractor.py:393,402`

**Issue:** The rule-based extractor sets `raw_label` to `key.replace("_", " ")` (e.g. `"cost of goods sold"` → `"cogs"` → `"cogs"`). The system prompt states "Preserve the exact original label in raw_label — this is used for pattern learning." Because the raw label is synthetic rather than the actual document label, the pattern library learns nothing useful from rule-based extractions. This is a silent quality gap — not a crash — but it means the learning feedback loop only works for Claude-based extractions.

**Fix:** In `_extract_statement`, capture the original matched line's `label_only` alongside the matched key, and return it as part of the result dict so `rule_based_extract` can use the real document label.

---

### IN-02: `_build_pattern_hints` only reads `pnl` and `bs` from the pattern library

**File:** `backend/ingestion.py:336`

**Issue:** The `for stmt in ("pnl", "bs"):` loop on line 336 omits `cf` and `eq` patterns. Claude's prompt is never primed with learned cash-flow or equity label patterns, even once the library accumulates them. This reduces extraction accuracy for those statement types.

**Fix:**
```python
for stmt in ("pnl", "bs", "cf", "eq"):
```

---

### IN-03: `_extract_company_name_from_pdf_sync` silences all exceptions including `KeyboardInterrupt`-equivalent

**File:** `backend/main.py:472-499`

**Issue:** The bare `except Exception: return ""` at line 498 swallows every failure mode silently — including API auth errors, network timeouts, and malformed PDFs — with no logging. In production this makes it impossible to diagnose why company name extraction is failing for certain documents.

**Fix:** Log the error before returning the empty string:
```python
except Exception as e:
    print(f"[WARN] Company name extraction failed: {e}")
    return ""
```

---

_Reviewed: 2026-05-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
