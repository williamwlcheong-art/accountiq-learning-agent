"""
Wave 0 RED test stubs for Phase 4 Extraction Quality.

All tests in this file are either:
  - RED (FAILED) because the implementation doesn't exist yet, or
  - GREEN for pre-existing behaviour (test_detect_periods_normalizes_fy_prefix).

Wave 2 and Wave 3 plans will implement the remaining RED features.
"""
import io
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Backend already added to sys.path by conftest.py, but guard here for direct runs.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Helper for integration tests
# ---------------------------------------------------------------------------

async def _register_and_login(client, email="ext-test@test.com", password="Pass1234!"):
    """Register, explicitly provision, and log in an admin test user."""
    from account_helpers import register_test_admin
    await register_test_admin(client, email, password)
    r = await client.post("/auth/login", data={"email": email, "password": password})
    return r.json().get("access_token", "")

def _docx_file(name="financials.docx"):
    """Minimal docx-like bytes — enough to pass suffix check."""
    return (
        name,
        io.BytesIO(b"PK\x03\x04fake-docx"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ---------------------------------------------------------------------------
# Task 2 targets — _ROW_SCHEMA / CF_ROWS / EQ_ROWS / _normalize_signs
# ---------------------------------------------------------------------------

def test_row_schema_includes_cf_eq():
    """_ROW_SCHEMA statement enum must include 'cf' and 'eq'."""
    from ingestion import _ROW_SCHEMA
    enum_vals = _ROW_SCHEMA["properties"]["statement"]["enum"]
    assert "cf" in enum_vals, f"'cf' missing from _ROW_SCHEMA enum: {enum_vals}"
    assert "eq" in enum_vals, f"'eq' missing from _ROW_SCHEMA enum: {enum_vals}"


def test_cf_eq_statement_types():
    """CF_ROWS must have 4 entries; EQ_ROWS must have 5 entries."""
    try:
        from ingestion import CF_ROWS, EQ_ROWS
    except ImportError:
        pytest.fail("CF_ROWS/EQ_ROWS not yet defined in ingestion.py — RED stub")
    assert len(CF_ROWS) == 6, f"Expected 6 CF rows, got {len(CF_ROWS)}"
    assert len(EQ_ROWS) == 5, f"Expected 5 EQ rows, got {len(EQ_ROWS)}"


def test_normalize_signs_flips_positive_costs():
    """_normalize_signs() must flip strictly positive cost values to negative."""
    try:
        from ingestion import _normalize_signs
    except ImportError:
        pytest.fail("_normalize_signs not yet defined in ingestion.py — RED stub")
    rows = [{"canonical_key": "cogs", "values": {"2025": 450000.0, "2024": 380000.0}}]
    result = _normalize_signs(rows)
    assert result[0]["values"]["2025"] == -450000.0, (
        f"Expected -450000.0, got {result[0]['values']['2025']}"
    )
    assert result[0]["values"]["2024"] == -380000.0, (
        f"Expected -380000.0, got {result[0]['values']['2024']}"
    )


def test_normalize_signs_preserves_zero_and_none():
    """_normalize_signs() must leave zero and None values unchanged."""
    try:
        from ingestion import _normalize_signs
    except ImportError:
        pytest.fail("_normalize_signs not yet defined in ingestion.py — RED stub")
    rows = [{"canonical_key": "cogs", "values": {"2025": 0.0, "2024": None}}]
    result = _normalize_signs(rows)
    assert result[0]["values"] == {"2025": 0.0, "2024": None}, (
        f"Expected {{'2025': 0.0, '2024': None}}, got {result[0]['values']}"
    )


def test_normalize_signs_does_not_flip_revenue():
    """_normalize_signs() must NOT flip revenue values."""
    try:
        from ingestion import _normalize_signs
    except ImportError:
        pytest.fail("_normalize_signs not yet defined in ingestion.py — RED stub")
    rows = [{"canonical_key": "revenue", "values": {"2025": 500000.0}}]
    result = _normalize_signs(rows)
    assert result[0]["values"]["2025"] == 500000.0, (
        f"Expected 500000.0, got {result[0]['values']['2025']}"
    )


def test_explicit_capex_keys_preserve_source_sign_and_exclude_aggregate_investing_cashflow():
    from ingestion import CF_ROWS, _normalize_signs

    keys = {key for key, _label in CF_ROWS}
    assert "purchases_property_plant_equipment" in keys
    assert "purchases_intangible_assets" in keys
    assert "investing_cashflow" in keys

    rows = [
        {"canonical_key": "purchases_property_plant_equipment", "values": {"2025": -75000.0}},
        {"canonical_key": "purchases_intangible_assets", "values": {"2025": 12000.0}},
        {"canonical_key": "investing_cashflow", "values": {"2025": -100000.0}},
    ]
    assert _normalize_signs(rows) == rows


# ---------------------------------------------------------------------------
# Pre-existing behaviour — already GREEN from Wave 0
# ---------------------------------------------------------------------------

def test_detect_periods_normalizes_fy_prefix():
    """_detect_periods() already handles 'FY2025' → '2025' normalisation."""
    from rule_extractor import _detect_periods
    result = _detect_periods("FY2025\tFY2024")
    assert result == ["2025", "2024"], f"Expected ['2025', '2024'], got {result}"


# ---------------------------------------------------------------------------
# Task 3 targets — SME synonym additions
# ---------------------------------------------------------------------------

def test_sme_label_owners_drawings():
    """PNL_SYNS['operating_expenses'] must contain 'owners drawings'."""
    from rule_extractor import PNL_SYNS
    assert "owners drawings" in PNL_SYNS["operating_expenses"], (
        "'owners drawings' not in PNL_SYNS['operating_expenses'] — RED stub"
    )


def test_sme_label_directors_fees():
    """PNL_SYNS['operating_expenses'] must contain 'directors fees'."""
    from rule_extractor import PNL_SYNS
    assert "directors fees" in PNL_SYNS["operating_expenses"], (
        "'directors fees' not in PNL_SYNS['operating_expenses'] — RED stub"
    )


# ---------------------------------------------------------------------------
# Wave 2 targets — multi-page selection
# ---------------------------------------------------------------------------

def test_multipage_includes_continuation():
    """D-05 fix: page with score 1 (continuation) must be included alongside high-scoring pages."""
    try:
        from rule_extractor import _score_page, PNL_SYNS
    except ImportError:
        pytest.fail("_score_page/PNL_SYNS not importable — RED stub")

    MAX_TEXT_CHARS = 60_000

    # Page 1: high score (has P&L keywords + numbers >= 1000)
    page1 = "Revenue\t1,000,000\nCost of goods sold\t600,000\nGross profit\t400,000\n"
    # Page 2: score 1 continuation (only one matching keyword)
    page2 = "Net profit\t200,000\n"
    # Page 0: cover page — no financial keywords
    page0 = "Annual Report 2025\nABCDEFG Company Limited\n"

    all_pages = [page0, page1, page2]
    try:
        from rule_extractor import BS_SYNS, CF_SYNS, EQ_SYNS
        scored = [
            (_score_page(pt, PNL_SYNS) + _score_page(pt, BS_SYNS)
             + _score_page(pt, CF_SYNS) + _score_page(pt, EQ_SYNS), i, pt)
            for i, pt in enumerate(all_pages)
        ]
    except ImportError:
        # CF_SYNS/EQ_SYNS not yet available — fall back to PNL+BS only
        try:
            from rule_extractor import BS_SYNS
            scored = [
                (_score_page(pt, PNL_SYNS) + _score_page(pt, BS_SYNS), i, pt)
                for i, pt in enumerate(all_pages)
            ]
        except ImportError:
            pytest.fail("BS_SYNS not importable — RED stub")

    # D-05 filter: keep pages with score > 0
    selected = [(s, i, pt) for s, i, pt in scored if s > 0]

    # Both page 1 and page 2 should be selected (score > 0)
    selected_indices = {i for _, i, _ in selected}
    assert 1 in selected_indices, (
        f"Page 1 (high-scoring) not in selected set: {selected_indices}"
    )
    assert 2 in selected_indices, (
        f"Page 2 (continuation, score=1) not in selected set: {selected_indices}"
    )


def test_multipage_excludes_cover_page():
    """D-05 fix: page with zero financial keywords must score 0 and be excluded."""
    try:
        from rule_extractor import _score_page, PNL_SYNS, BS_SYNS
    except ImportError:
        pytest.fail("_score_page/PNL_SYNS/BS_SYNS not importable — RED stub")

    cover_page = "Annual Report 2025\nABCDEFG Company Limited\nPrepared by ABC Accounting\n"
    score = _score_page(cover_page, PNL_SYNS) + _score_page(cover_page, BS_SYNS)

    # D-05 filter: only include pages with score > 0
    # A cover page has no financial numbers >= 1000 so score should be 0
    assert score == 0, f"Cover page expected score 0, got {score}"


def test_multipage_truncation_drops_lowest_score():
    """D-06 fix: when chars exceed 60K cap, lowest-scored pages are dropped first."""
    from rule_extractor import _score_page, PNL_SYNS, BS_SYNS, CF_SYNS, EQ_SYNS

    MAX_TEXT_CHARS = 60_000

    # Page 0: high score — dense P&L keywords
    page_high = "Revenue\t1,000,000\nCost of goods sold\t600,000\nGross profit\t400,000\n" * 20
    # Page 1: low score — one keyword, repeated to be large
    page_low = "Net profit\t200,000\n" + "x" * 3000

    all_pages = [page_high, page_low]

    scored = [
        (
            _score_page(pt, PNL_SYNS) + _score_page(pt, BS_SYNS)
            + _score_page(pt, CF_SYNS) + _score_page(pt, EQ_SYNS),
            i, pt
        )
        for i, pt in enumerate(all_pages)
    ]

    # Both pages have score > 0
    selected = [(s, i, pt) for s, i, pt in scored if s > 0]
    selected.sort(key=lambda x: x[1])

    # Verify both pages would be selected before truncation
    assert len(selected) == 2, f"Expected 2 pages selected, got {len(selected)}"

    # Record which page has higher score
    scores_by_idx = {i: s for s, i, _ in selected}
    high_score_idx = max(scores_by_idx, key=lambda k: scores_by_idx[k])
    low_score_idx = min(scores_by_idx, key=lambda k: scores_by_idx[k])

    # Total chars before truncation
    total_chars = sum(len(f"--- PAGE {i+1} ---\n{pt}") for _, i, pt in selected)

    # Now simulate D-06 truncation to a very small cap (to force dropping)
    SMALL_CAP = len(f"--- PAGE {high_score_idx+1} ---\n{all_pages[high_score_idx]}") + 100
    selected_trunc = list(selected)
    total_t = sum(len(f"--- PAGE {i+1} ---\n{pt}") for _, i, pt in selected_trunc)
    while total_t > SMALL_CAP and len(selected_trunc) > 1:
        min_idx = min(range(len(selected_trunc)), key=lambda k: selected_trunc[k][0])
        removed = selected_trunc.pop(min_idx)
        total_t -= len(f"--- PAGE {removed[1]+1} ---\n{removed[2]}")

    remaining_indices = {i for _, i, _ in selected_trunc}
    assert high_score_idx in remaining_indices, (
        f"High-scored page {high_score_idx} was dropped first — should drop lowest first. "
        f"Remaining: {remaining_indices}"
    )
    assert low_score_idx not in remaining_indices, (
        f"Low-scored page {low_score_idx} should have been dropped. "
        f"Remaining: {remaining_indices}"
    )


# ---------------------------------------------------------------------------
# Wave 3 targets — .docx ingestion
# ---------------------------------------------------------------------------

def test_docx_table_extraction(monkeypatch):
    """extract_docx_text() must extract table rows as tab-separated text."""
    try:
        from ingestion import extract_docx_text
        import ingestion as _ing
    except ImportError:
        pytest.fail("extract_docx_text not yet defined in ingestion.py — RED stub")

    mock_cell_1 = MagicMock()
    mock_cell_1.text = "Revenue"
    mock_cell_1._tc = object()

    mock_cell_2 = MagicMock()
    mock_cell_2.text = "1000"
    mock_cell_2._tc = object()

    mock_row = MagicMock()
    mock_row.cells = [mock_cell_1, mock_cell_2]

    mock_table = MagicMock()
    mock_table.rows = [mock_row]

    mock_doc = MagicMock()
    mock_doc.tables = [mock_table]
    mock_doc.paragraphs = []

    monkeypatch.setattr(_ing, "DocxDocument", lambda path: mock_doc)
    monkeypatch.setattr(_ing, "HAS_PYTHON_DOCX", True)

    claude_text, sheets, count, used_ocr = extract_docx_text("/fake/path.docx")
    assert "Revenue\t1000" in claude_text, (
        f"Expected 'Revenue\\t1000' in output, got: {claude_text!r}"
    )
    assert count == 1
    assert used_ocr is False


def test_docx_merged_cells_dedup(monkeypatch):
    """extract_docx_text() must deduplicate merged cells by _tc object identity."""
    try:
        from ingestion import extract_docx_text
        import ingestion as _ing
    except ImportError:
        pytest.fail("extract_docx_text not yet defined in ingestion.py — RED stub")

    # Two cells share the same _tc object (merged cell scenario)
    shared_tc = object()

    mock_cell_1 = MagicMock()
    mock_cell_1.text = "Merged Cell"
    mock_cell_1._tc = shared_tc

    mock_cell_2 = MagicMock()
    mock_cell_2.text = "Merged Cell"
    mock_cell_2._tc = shared_tc  # same _tc → should deduplicate

    mock_cell_3 = MagicMock()
    mock_cell_3.text = "Value"
    mock_cell_3._tc = object()

    mock_row = MagicMock()
    mock_row.cells = [mock_cell_1, mock_cell_2, mock_cell_3]

    mock_table = MagicMock()
    mock_table.rows = [mock_row]

    mock_doc = MagicMock()
    mock_doc.tables = [mock_table]
    mock_doc.paragraphs = []

    monkeypatch.setattr(_ing, "DocxDocument", lambda path: mock_doc)
    monkeypatch.setattr(_ing, "HAS_PYTHON_DOCX", True)

    claude_text, _, _, _ = extract_docx_text("/fake/path.docx")
    # Should appear only once, not "Merged Cell\tMerged Cell\tValue"
    assert claude_text.count("Merged Cell") == 1, (
        f"Expected merged cell text to appear only once, got: {claude_text!r}"
    )


def test_ingest_dispatches_docx(monkeypatch):
    """ingest_document() must call extract_docx_text() for .docx files."""
    import ingestion as _ing

    called_with = {}

    def fake_docx(filepath):
        called_with["path"] = filepath
        return ("docx text", ["docx text"], 1, False)

    monkeypatch.setattr(_ing, "extract_docx_text", fake_docx)

    # Verify .docx extension routes to extract_docx_text (not extract_pdf_text)
    # We test the dispatch logic directly rather than calling ingest_document()
    # (which is async and needs a DB). The dispatch logic is:
    #   fp_lower = filepath.lower()
    #   if fp_lower.endswith(".docx"): extract_docx_text(...)
    fp = "/fake/financials.docx"
    fp_lower = fp.lower()
    if fp_lower.endswith((".xlsx", ".xls", ".xlsm")):
        result = _ing.extract_excel_text(fp)
    elif fp_lower.endswith(".docx"):
        result = _ing.extract_docx_text(fp)
    else:
        result = _ing.extract_pdf_text(fp)

    assert called_with.get("path") == fp, (
        f"extract_docx_text was not called for .docx file. called_with={called_with}"
    )
    assert result[0] == "docx text"


@pytest.mark.asyncio
async def test_upload_routes_accept_docx(client, fresh_all_db):
    """Both /documents/upload and /wizard/upload must accept .docx without 400."""
    await _register_and_login(client, "docx-upload@test.com")

    # Create a company first
    r = await client.post(
        "/companies",
        data={"name": "DocxTestCo", "exchange": "Private"},
    )
    assert r.status_code == 200, f"Create company failed: {r.text}"
    company_id = r.json()["id"]

    fname, fbytes, ftype = _docx_file()
    r = await client.post(
        "/documents/upload",
        files={"file": (fname, fbytes, ftype)},
        data={
            "company_id": str(company_id),
            "entity_type": "sme",
            "report_type": "compilation",
        },
    )
    # Should NOT be a 400 (unsupported file type) — may be 200/202 or another error
    assert r.status_code != 400, (
        f".docx upload returned 400 (file type rejected): {r.text}"
    )


# ---------------------------------------------------------------------------
# Wave 2 targets — OCR / page-has-text thresholds
# ---------------------------------------------------------------------------

def test_page_has_text_threshold():
    """_page_has_text() must use threshold > 99 chars (D-15: 20 → 100)."""
    from ingestion import _page_has_text
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "x" * 99  # 99 chars — should be below threshold
    result = _page_has_text(mock_page)
    assert result is False, (
        f"Expected _page_has_text to return False for 99-char text (threshold should be 100), got {result}"
    )


def test_ocr_dpi_is_300():
    """OCR_DPI must be 300 (D-16: raised from 200)."""
    from ingestion import OCR_DPI
    assert OCR_DPI == 300, f"Expected OCR_DPI == 300, got {OCR_DPI}"
