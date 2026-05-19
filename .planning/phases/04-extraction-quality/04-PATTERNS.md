# Phase 4: Extraction Quality - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 6 new/modified files
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/ingestion.py` | service | transform (file-I/O → structured rows) | `backend/ingestion.py` itself (surgical edits) | exact — self |
| `backend/rule_extractor.py` | service | transform (text → structured rows) | `backend/rule_extractor.py` itself (additive edits) | exact — self |
| `backend/main.py` | controller | request-response | `backend/main.py` itself (`/wizard/upload` and `/documents/upload` edits) | exact — self |
| `backend/requirements.txt` | config | — | `backend/requirements.txt` itself | exact — self |
| `frontend/index.html` | component | — | `frontend/index.html` itself (accept attribute change) | exact — self |
| `tests/test_extraction.py` | test | unit | `tests/test_upload_auto.py` | role-match |

---

## Pattern Assignments

### `backend/ingestion.py` (service, transform — multiple surgical edits)

**Analog:** `backend/ingestion.py` (self — targeted changes to specific functions)

---

#### Edit 1 — Optional dependency guard (`HAS_PYTHON_DOCX`)

**Pattern source:** `backend/ingestion.py` lines 20–24 (existing `HAS_TESSERACT` guard)

```python
# Existing pattern to copy exactly (lines 20–24):
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
```

**New code copies this pattern:**
```python
try:
    from docx import Document as DocxDocument
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False
```

Place immediately after the `HAS_TESSERACT` block (before `import aiosqlite`).

---

#### Edit 2 — Raise `OCR_DPI` constant

**Pattern source:** `backend/ingestion.py` line 37

```python
OCR_DPI = 200   # line 37 — change to 300
```

---

#### Edit 3 — `_page_has_text()` threshold

**Pattern source:** `backend/ingestion.py` lines 168–170

```python
# Current (lines 168–170):
def _page_has_text(page) -> bool:
    text = page.extract_text() or ""
    return len(text.strip()) > 20   # change 20 → 100
```

---

#### Edit 4 — `extract_pdf_text()` page selection (D-05/D-06)

**Pattern source:** `backend/ingestion.py` lines 198–211 — the block being replaced

```python
# Current code (lines 197–211) — REPLACE this block:
from rule_extractor import _score_page, PNL_SYNS, BS_SYNS
scored = [((_score_page(pt, PNL_SYNS) + _score_page(pt, BS_SYNS)), i, pt)
          for i, pt in enumerate(all_pages)]
scored.sort(key=lambda x: -x[0])
claude_parts = []
total_chars = 0
for score, idx, pt in scored:
    chunk = f"--- PAGE {idx+1} ---\n{pt}"
    if total_chars + len(chunk) > MAX_TEXT_CHARS:
        break
    claude_parts.append((idx, chunk))
    total_chars += len(chunk)
claude_parts.sort(key=lambda x: x[0])
claude_text = "\n".join(c for _, c in claude_parts)
```

**Replacement pattern (D-05/D-06):**
```python
from rule_extractor import _score_page, PNL_SYNS, BS_SYNS, CF_SYNS, EQ_SYNS
scored = [(_score_page(pt, PNL_SYNS) + _score_page(pt, BS_SYNS)
           + _score_page(pt, CF_SYNS) + _score_page(pt, EQ_SYNS), i, pt)
          for i, pt in enumerate(all_pages)]
# D-05: filter score > 0, sort by page index (not by score)
selected = [(s, i, pt) for s, i, pt in scored if s > 0]
selected.sort(key=lambda x: x[1])
# D-06: if over 60K, drop lowest-scored pages first
total_chars = sum(len(f"--- PAGE {i+1} ---\n{pt}") for _, i, pt in selected)
while total_chars > MAX_TEXT_CHARS and len(selected) > 1:
    min_idx = min(range(len(selected)), key=lambda k: selected[k][0])
    removed = selected.pop(min_idx)
    total_chars -= len(f"--- PAGE {removed[1]+1} ---\n{removed[2]}")
claude_parts = [(i, f"--- PAGE {i+1} ---\n{pt}") for _, i, pt in selected]
claude_parts.sort(key=lambda x: x[0])
claude_text = "\n".join(c for _, c in claude_parts)
```

---

#### Edit 5 — `extract_excel_text()` as template for `extract_docx_text()`

**Pattern source:** `backend/ingestion.py` lines 226–242

```python
# Copy signature and structure from extract_excel_text() (lines 226–242):
def extract_excel_text(filepath: str) -> tuple[str, list[str], int, bool]:
    """Returns (claude_text, sheet_texts, sheet_count, used_ocr=False)."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for Excel ingestion: pip install pandas openpyxl")

    xl = pd.ExcelFile(filepath)
    sheets: list[str] = []
    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name, header=None)
        if df.empty:
            continue
        sheets.append(f"--- SHEET: {sheet_name} ---\n{df.to_string(index=False)}")

    combined = "\n\n".join(sheets)
    return combined[:MAX_TEXT_CHARS], sheets, len(xl.sheet_names), False
```

**New `extract_docx_text()` copies the same signature and return shape:**
```python
def extract_docx_text(filepath: str) -> tuple[str, list[str], int, bool]:
    """Returns (claude_text, [combined], 1, used_ocr=False)."""
    if not HAS_PYTHON_DOCX:
        raise ImportError("python-docx is required for Word ingestion: pip install python-docx")

    doc = DocxDocument(filepath)
    parts = []

    for i, table in enumerate(doc.tables):
        parts.append(f"--- TABLE {i+1} ---")
        for row in table.rows:
            # Deduplicate merged cells by _tc element identity (CRITICAL)
            seen = {}
            cells_text = []
            for cell in row.cells:
                cell_id = id(cell._tc)
                if cell_id not in seen:
                    seen[cell_id] = True
                    cells_text.append(cell.text.strip())
            parts.append("\t".join(cells_text))

    # Append non-table paragraphs after all tables (D-12)
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)

    combined = "\n".join(parts)
    return combined[:MAX_TEXT_CHARS], [combined], 1, False
```

Place this function immediately after `extract_excel_text()`.

---

#### Edit 6 — File extension dispatch in `ingest_document()`

**Pattern source:** `backend/ingestion.py` lines 403–407

```python
# Current dispatch (lines 403–407) — add .docx branch above .pdf:
fp_lower = filepath.lower()
if fp_lower.endswith((".xlsx", ".xls", ".xlsm")):
    claude_text, all_page_texts, page_count, used_ocr = extract_excel_text(filepath)
else:
    claude_text, all_page_texts, page_count, used_ocr = extract_pdf_text(filepath)
```

**Updated dispatch:**
```python
fp_lower = filepath.lower()
if fp_lower.endswith((".xlsx", ".xls", ".xlsm")):
    claude_text, all_page_texts, page_count, used_ocr = await asyncio.get_running_loop().run_in_executor(
        None, extract_excel_text, filepath
    )
elif fp_lower.endswith(".docx"):
    claude_text, all_page_texts, page_count, used_ocr = await asyncio.get_running_loop().run_in_executor(
        None, extract_docx_text, filepath
    )
else:
    claude_text, all_page_texts, page_count, used_ocr = await asyncio.get_running_loop().run_in_executor(
        None, extract_pdf_text, filepath
    )
```

Note: The existing Excel and PDF calls are NOT currently wrapped in `run_in_executor`. The CONVENTIONS.md requires sync lib calls be wrapped — wrap all three branches for consistency when making this change.

---

#### Edit 7 — `_ROW_SCHEMA` enum expansion (D-01)

**Pattern source:** `backend/ingestion.py` lines 133–143

```python
# Current (line 137):
"statement": {"type": "string", "enum": ["pnl", "bs"]},

# Change to:
"statement": {"type": "string", "enum": ["pnl", "bs", "cf", "eq"]},
```

---

#### Edit 8 — `ALL_ROWS` expansion (D-02, D-03)

**Pattern source:** `backend/ingestion.py` lines 39–73

```python
# Current PNL_ROWS / BS_ROWS / ALL_ROWS pattern (lines 39–73).
# Add after BS_ROWS:

CF_ROWS = [
    ("operating_cashflow",  "Cash flows from operating activities"),
    ("investing_cashflow",  "Cash flows from investing activities"),
    ("financing_cashflow",  "Cash flows from financing activities"),
    ("net_change_in_cash",  "Net change in cash and cash equivalents"),
]

EQ_ROWS = [
    ("opening_equity",          "Opening equity / balance at beginning"),
    ("net_profit",              "Net profit for the period"),
    ("dividends_paid",          "Dividends / distributions paid"),
    ("other_equity_movements",  "Other equity movements"),
    ("closing_equity",          "Closing equity / balance at end"),
]

# Update ALL_ROWS (line 72–73) to include cf and eq:
ALL_ROWS = (
    [("pnl", k, lbl) for k, lbl in PNL_ROWS]
    + [("bs",  k, lbl) for k, lbl in BS_ROWS]
    + [("cf",  k, lbl) for k, lbl in CF_ROWS]
    + [("eq",  k, lbl) for k, lbl in EQ_ROWS]
)
```

---

#### Edit 9 — `SYSTEM_PROMPT` CF/EQ sections

**Pattern source:** `backend/ingestion.py` lines 105–113 (existing canonical key sections)

```python
# Existing sections (lines 105–113) — append two new sections in same style:

## Canonical Cash Flow Keys (statement: "cf")
operating_cashflow, investing_cashflow, financing_cashflow, net_change_in_cash

## Canonical Equity Changes Keys (statement: "eq")
opening_equity, net_profit, dividends_paid, other_equity_movements, closing_equity
```

Also append to the `GAAP vs IFRS Terminology` table rows for CF/EQ canonical keys and add a sign convention note to the Extraction Rules section:

```
7. SIGN CONVENTION: Cost/expense keys (cogs, operating_expenses, depreciation,
   interest_expense, tax) must be returned as NEGATIVE numbers.
   Revenue and asset/equity keys must be POSITIVE.
   A post-processing layer will enforce this, but supply the correct sign.
```

---

#### Edit 10 — `_normalize_signs()` pure function + placement in `persist_extraction()`

**Pattern source:** `backend/ingestion.py` lines 312–368 (`persist_extraction`)

```python
# New pure function — place before persist_extraction():
_COST_KEYS = frozenset({"cogs", "operating_expenses", "depreciation", "interest_expense", "tax"})

def _normalize_signs(rows: list[dict]) -> list[dict]:
    """Return new row dicts with sign-corrected values for known cost keys.
    Only flips strictly positive values; leaves zero and None unchanged.
    Pure function — does not modify rows in place.
    """
    result = []
    for row in rows:
        key = row.get("canonical_key", "")
        if key in _COST_KEYS:
            new_values = {}
            for period, val in row.get("values", {}).items():
                if val is not None and val > 0:
                    new_values[period] = -val
                else:
                    new_values[period] = val
            result.append({**row, "values": new_values})
        else:
            result.append(row)
    return result
```

**Insertion point in `persist_extraction()` (line 324 — before the `for row in rows:` loop):**

```python
# Current (line 324):
rows = parsed.get("rows", [])

# Change to:
rows = _normalize_signs(parsed.get("rows", []))
```

---

### `backend/rule_extractor.py` (service, transform — additive edits)

**Analog:** `backend/rule_extractor.py` (self — additive synonym dicts and sign call)

---

#### Edit 1 — SME synonym additions to `PNL_SYNS`

**Pattern source:** `backend/rule_extractor.py` lines 14–71 (existing `PNL_SYNS` structure)

```python
# Existing PNL_SYNS["operating_expenses"] (lines 30–34):
"operating_expenses": [
    "total operating expenses", "total expenses", "total operating costs",
    "operating expenditure", "total expenditure", "total costs",
    "operating costs", "expenses", "total administration expenses",
],
```

**Additions to `PNL_SYNS["operating_expenses"]` (append to list):**
```python
    # AU/NZ SME additions
    "owners drawings", "drawings",
    "directors fees", "directors remuneration",
    "wages", "wages and salaries", "salaries and wages",
    "administration expenses", "admin expenses",
    "motor vehicle expenses", "vehicle costs",
```

**Additions to `PNL_SYNS["cogs"]` (append to list):**
```python
    # AU/NZ SME trade/construction additions
    "subcontractors", "subcontract costs", "contract labour",
```

**Additions to `PNL_SYNS["revenue"]` (append to list):**
```python
    # AU/NZ SME income additions
    "other income", "sundry income", "miscellaneous income",
```

---

#### Edit 2 — New `CF_SYNS` and `EQ_SYNS` dicts

**Pattern source:** `backend/rule_extractor.py` lines 14–147 (existing `PNL_SYNS` / `BS_SYNS` structure)

```python
# Add after BS_SYNS (before SUM_KEYS at line 149):

CF_SYNS: dict[str, list[str]] = {
    "operating_cashflow": [
        "cash flows from operating activities", "net cash from operations",
        "operating activities", "cash generated from operations",
    ],
    "investing_cashflow": [
        "cash flows from investing activities", "investing activities",
        "net cash used in investing",
    ],
    "financing_cashflow": [
        "cash flows from financing activities", "financing activities",
        "net cash from financing",
    ],
    "net_change_in_cash": [
        "net increase in cash", "net decrease in cash",
        "net change in cash and cash equivalents",
        "increase in cash held", "decrease in cash held",
    ],
}

EQ_SYNS: dict[str, list[str]] = {
    "opening_equity": [
        "balance at beginning", "opening balance", "balance brought forward",
        "equity at start of year",
    ],
    "net_profit": [
        "profit for the year", "net profit", "net income",
    ],
    "dividends_paid": [
        "dividends paid", "distributions paid", "drawings paid",
        "dividends declared", "owner distributions",
    ],
    "other_equity_movements": [
        "other comprehensive income", "other movements",
        "share capital issued",
    ],
    "closing_equity": [
        "balance at end", "closing balance", "equity at end of year",
        "total equity",
    ],
}
```

---

#### Edit 3 — Sign normalization call in `rule_based_extract()`

**Pattern source:** `backend/rule_extractor.py` lines 308–361 (`rule_based_extract`)
The `rows` list is assembled at lines 336–353. Apply `_normalize_signs()` from `ingestion.py` before returning.

Since `rule_extractor.py` cannot import from `ingestion.py` (circular), duplicate `_COST_KEYS` and `_normalize_signs()` in `rule_extractor.py`, or move `_normalize_signs()` to a shared utility. **Recommended approach:** import inline inside `rule_based_extract()`:

```python
# At the bottom of rule_based_extract(), before the return statement (line 355):
try:
    from ingestion import _normalize_signs
    rows = _normalize_signs(rows)
except ImportError:
    pass  # ingestion not available in unit-test environments
```

Alternatively (cleaner): define `_COST_KEYS` and `_normalize_signs()` in `rule_extractor.py` directly (since `rule_extractor.py` has no import from `ingestion.py` currently), and have `ingestion.py` import `_normalize_signs` from `rule_extractor`. The planner should decide which module owns the function; the pattern above is the safest non-circular option.

---

### `backend/main.py` (controller, request-response — two route edits)

**Analog:** `backend/main.py` lines 520–615 (`upload_document`) and lines 916–959 (`wizard_upload`)

---

#### Edit 1 — Add `.docx` to allowed extensions in `/documents/upload`

**Pattern source:** `backend/main.py` lines 532–535

```python
# Current (lines 532–535):
suffix = Path(file.filename).suffix.lower()
allowed = {".pdf", ".xlsx", ".xls", ".xlsm"}
if suffix not in allowed:
    raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {suffix}")

# Change to:
suffix = Path(file.filename).suffix.lower()
allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}
if suffix not in allowed:
    raise HTTPException(400, f"Only PDF, Excel, and Word files are accepted. Got: {suffix}")
```

---

#### Edit 2 — Add `.docx` to allowed extensions in `/wizard/upload`

**Pattern source:** `backend/main.py` lines 929–932

```python
# Current (lines 929–932):
suffix = Path(file.filename).suffix.lower()
allowed = {".pdf", ".xlsx", ".xls", ".xlsm"}
if suffix not in allowed:
    raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {suffix}")

# Change to:
suffix = Path(file.filename).suffix.lower()
allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx"}
if suffix not in allowed:
    raise HTTPException(400, f"Only PDF, Excel, and Word files are accepted. Got: {suffix}")
```

---

### `backend/requirements.txt` (config)

**Analog:** `backend/requirements.txt` (self — append one line)

```
# Add:
python-docx>=1.1.0
```

---

### `frontend/index.html` (component — two attribute edits)

**Analog:** `frontend/index.html` (self — two `accept` attribute changes)

**Pattern source:** `frontend/index.html` lines 338 and 497

```html
<!-- Line 338 — admin upload input (current): -->
<input type="file" id="up-file" accept=".pdf,.xlsx,.xls,.xlsm" .../>
<!-- Change to: -->
<input type="file" id="up-file" accept=".pdf,.xlsx,.xls,.xlsm,.docx" .../>

<!-- Line 497 — wizard upload input (current): -->
<input id="wiz-file" type="file" accept=".pdf,.xlsx,.xls,.xlsm" .../>
<!-- Change to: -->
<input id="wiz-file" type="file" accept=".pdf,.xlsx,.xls,.xlsm,.docx" .../>
```

Also update the JS-side `allowed` arrays at lines 1987 and 2094:

```javascript
// Line 1987 (current):
const allowed = ['.pdf','.xlsx','.xls','.xlsm'];
// Change to:
const allowed = ['.pdf','.xlsx','.xls','.xlsm','.docx'];

// Line 2094 (current):
const allowed = ['.pdf', '.xlsx', '.xls', '.xlsm'];
// Change to:
const allowed = ['.pdf', '.xlsx', '.xls', '.xlsm', '.docx'];
```

---

### `tests/test_extraction.py` (test, unit — new file)

**Analog:** `tests/test_upload_auto.py` (role-match — same pytest-asyncio framework and monkeypatch patterns)

---

#### Imports and fixture pattern

**Pattern source:** `tests/conftest.py` lines 1–96 and `tests/test_upload_auto.py` lines 1–59

```python
import io
import sys
from pathlib import Path
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

# Backend importable via conftest.py sys.path manipulation
# No need to add path again — conftest.py already does it
import sys
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
```

**Fixture pattern (copy from `tests/conftest.py` lines 52–96):**
```python
# Use the shared `fresh_all_db` and `client` fixtures from conftest.py.
# For pure unit tests (no HTTP), no fixture needed — import the function directly.

# Example unit test (no HTTP, no DB):
def test_normalize_signs_flips_positive_costs():
    from ingestion import _normalize_signs
    rows = [{"canonical_key": "cogs", "values": {"2025": 450000.0, "2024": 380000.0}}]
    result = _normalize_signs(rows)
    assert result[0]["values"]["2025"] == -450000.0
    assert result[0]["values"]["2024"] == -380000.0
```

**Monkeypatch pattern for docx (copy from `tests/test_upload_auto.py` line 149):**
```python
# Monkeypatch python-docx Document to avoid needing a real .docx file:
def test_docx_table_extraction(monkeypatch):
    from ingestion import extract_docx_text
    import ingestion as _ing

    mock_cell_1 = MagicMock(); mock_cell_1.text = "Revenue"; mock_cell_1._tc = object()
    mock_cell_2 = MagicMock(); mock_cell_2.text = "1000"; mock_cell_2._tc = object()
    mock_row = MagicMock(); mock_row.cells = [mock_cell_1, mock_cell_2]
    mock_table = MagicMock(); mock_table.rows = [mock_row]
    mock_doc = MagicMock()
    mock_doc.tables = [mock_table]
    mock_doc.paragraphs = []

    monkeypatch.setattr(_ing, "DocxDocument", lambda path: mock_doc)
    monkeypatch.setattr(_ing, "HAS_PYTHON_DOCX", True)

    claude_text, sheets, count, used_ocr = extract_docx_text("/fake/path.docx")
    assert "Revenue\t1000" in claude_text
    assert count == 1
    assert used_ocr is False
```

**Fake-bytes upload pattern for integration tests (copy from `tests/test_upload_auto.py` lines 34–57):**
```python
def _docx_file(name="financials.docx"):
    """Minimal docx-like bytes — enough to pass suffix check."""
    return (name, io.BytesIO(b"PK\x03\x04fake-docx"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@pytest.mark.asyncio
async def test_upload_routes_accept_docx(client, fresh_all_db):
    """Both upload routes should accept .docx without a 400 error."""
    await _register_admin(client, "docx-upload@test.com")
    # ... create company, then post with _docx_file()
```

---

## Shared Patterns

### `run_in_executor` wrapping for sync library calls

**Source:** `backend/main.py` lines 566–568 and `backend/ingestion.py` line 288
**Apply to:** `extract_docx_text()` call-site in `ingest_document()`

```python
# Pattern from main.py lines 566–568:
loop = asyncio.get_running_loop()
extracted = await loop.run_in_executor(
    None, _extract_company_name_from_pdf_sync, str(tmp_path)
)

# Pattern from ingestion.py line 288:
response = await loop.run_in_executor(None, lambda: client.messages.create(...))
```

All sync library calls (pdfplumber, pandas, python-docx) must be wrapped. Use `asyncio.get_running_loop().run_in_executor(None, func, *args)` or the lambda form.

---

### `try/except ImportError` optional dependency guard

**Source:** `backend/ingestion.py` lines 20–24
**Apply to:** `HAS_PYTHON_DOCX` guard in `ingestion.py`

```python
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
```

---

### Error handling in upload routes

**Source:** `backend/main.py` lines 534–535
**Apply to:** Both upload route allowed-extension checks

```python
if suffix not in allowed:
    raise HTTPException(400, f"Only PDF and Excel files are accepted. Got: {suffix}")
```

---

### `_migrate_db()` try/except per-statement pattern

**Source:** `backend/db.py` lines 120–136
**Apply to:** Any future schema comment updates (no migration SQL needed for Phase 4 — `statement TEXT` is unconstrained)

```python
def _migrate_db(conn: sqlite3.Connection):
    for sql in [...]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
```

---

### Background task / `_run_ingestion` pattern

**Source:** `backend/main.py` lines 618–629 and lines 603–605
**Apply to:** No new routes in Phase 4 — existing pattern used unchanged

```python
# Kick off background task:
background_tasks.add_task(
    _run_ingestion, document_id, company_id, str(dest),
    entity_type, exchange, fiscal_year_end
)

# Background task implementation:
async def _run_ingestion(document_id, company_id, filepath, entity_type, exchange, fiscal_year_end):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            await ingest_document(db, document_id, company_id, filepath, ...)
        except Exception as e:
            print(f"[ERROR] Ingestion failed for doc {document_id}: {e}")
```

---

### pytest unit test structure

**Source:** `tests/test_upload_auto.py` lines 47–58
**Apply to:** `tests/test_extraction.py` for all pure unit tests

```python
@pytest.mark.asyncio
async def test_<name>(client, fresh_all_db):
    await _register_admin(client, "unique-email@test.com")
    # ... test body
    assert r.status_code == <expected>
```

For pure unit tests (no HTTP), omit `@pytest.mark.asyncio`, `client`, and `fresh_all_db`:
```python
def test_<name>():
    from ingestion import _normalize_signs
    # ... pure function test
    assert <expected>
```

---

## No Analog Found

All files in Phase 4 have clear analogs in the existing codebase. No file requires falling back to RESEARCH.md patterns exclusively.

| File | Note |
|------|------|
| `tests/test_extraction.py` | New file — no exact analog, but `tests/test_upload_auto.py` provides the full framework pattern |

---

## Critical Anti-Patterns (Do NOT copy)

| Anti-Pattern | Location | Why Forbidden |
|--------------|----------|---------------|
| `scored.sort(key=lambda x: -x[0])` + greedy `break` | `ingestion.py` lines 201–208 | Drops continuation pages (D-05 fix) |
| `"enum": ["pnl", "bs"]` in `_ROW_SCHEMA` | `ingestion.py` line 137 | Blocks CF/EQ rows (D-01 fix) |
| `len(text.strip()) > 20` in `_page_has_text` | `ingestion.py` line 170 | Too low threshold for OCR trigger (D-15 fix) |
| `OCR_DPI = 200` | `ingestion.py` line 37 | Too low DPI for small-font tables (D-16 fix) |
| Naive `"\t".join(cell.text for cell in row.cells)` | (new code) | Merged cells produce doubled text — must deduplicate via `id(cell._tc)` |
| Renaming `depreciation` to `depreciation_amortisation` | `ingestion.py` `PNL_ROWS` | Breaks Phase 3 EBITDA bridge fallback at `main.py:240` |

---

## Metadata

**Analog search scope:** `backend/`, `tests/`, `frontend/`
**Files read:** `backend/ingestion.py`, `backend/rule_extractor.py`, `backend/main.py` (upload routes + wizard route), `backend/db.py` (migration pattern), `tests/conftest.py`, `tests/test_upload_auto.py`, `frontend/index.html` (accept attributes)
**Pattern extraction date:** 2026-05-19
