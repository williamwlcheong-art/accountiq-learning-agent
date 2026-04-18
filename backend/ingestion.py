"""
PDF ingestion pipeline:
  1. Extract text (pdfplumber + pytesseract for image pages)
  2. Send to Claude API with dynamic pattern library prompt
  3. Parse structured response → financial_rows
  4. Record new label patterns for future learning
"""
import os
import json
import re
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import anthropic
import pdfplumber
from PIL import Image

# Optional: pytesseract for OCR fallback
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

import aiosqlite
from db import record_patterns, get_pattern_library, normalise_label

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-opus-4-5"
MAX_TEXT_CHARS = 60_000      # truncate very large PDFs to stay in context window
OCR_DPI = 200

# Canonical row definitions (P&L + BS)
PNL_ROWS = [
    ("revenue",              "Revenue / Sales"),
    ("cogs",                 "Cost of goods sold (COGS)"),
    ("gross_profit",         "Gross profit"),
    ("operating_expenses",   "Total operating expenses"),
    ("ebitda",               "EBITDA"),
    ("depreciation",         "Depreciation & amortisation"),
    ("ebit",                 "EBIT / Operating profit"),
    ("interest_expense",     "Interest / finance costs"),
    ("pbt",                  "Profit before tax"),
    ("tax",                  "Income tax expense"),
    ("net_profit",           "Net profit / NPAT"),
]

BS_ROWS = [
    ("cash_and_bank",        "Cash & bank"),
    ("trade_debtors",        "Trade debtors / receivables"),
    ("inventory",            "Inventory / stock"),
    ("other_current_assets", "Other current assets"),
    ("total_current_assets", "Total current assets"),
    ("fixed_assets_net",     "Fixed assets (net PP&E)"),
    ("other_noncurrent_assets","Other non-current assets"),
    ("total_assets",         "Total assets"),
    ("trade_creditors",      "Trade creditors / payables"),
    ("short_term_debt",      "Short-term debt / current borrowings"),
    ("other_current_liab",   "Other current liabilities"),
    ("total_current_liab",   "Total current liabilities"),
    ("long_term_debt",       "Long-term debt / non-current borrowings"),
    ("other_noncurrent_liab","Other non-current liabilities"),
    ("total_liabilities",    "Total liabilities"),
    ("shareholders_equity",  "Shareholders equity / net assets"),
]

ALL_ROWS = [("pnl", k, lbl) for k, lbl in PNL_ROWS] + \
           [("bs",  k, lbl) for k, lbl in BS_ROWS]


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _page_has_text(page) -> bool:
    """Return True if pdfplumber finds any non-trivial text on the page."""
    text = page.extract_text() or ""
    return len(text.strip()) > 20


def _ocr_page(page) -> str:
    """Render a pdfplumber page to image and OCR it."""
    if not HAS_TESSERACT:
        return ""
    img = page.to_image(resolution=OCR_DPI).original
    return pytesseract.image_to_string(img, config="--psm 6")


def extract_pdf_text(filepath: str) -> tuple[str, list[str], int, bool]:
    """
    Returns (claude_text, all_page_texts, page_count, used_ocr).
    - all_page_texts: one string per page, no truncation (for rule-based extractor)
    - claude_text: smartly selected pages truncated to MAX_TEXT_CHARS (for Claude)
    """
    all_pages: list[str] = []
    used_ocr = False

    with pdfplumber.open(filepath) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            if _page_has_text(page):
                t = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            else:
                t = _ocr_page(page)
                if t.strip():
                    used_ocr = True
            all_pages.append(t)

    # For Claude: score pages and prefer financial statement pages
    from rule_extractor import _score_page, PNL_SYNS, BS_SYNS
    scored = []
    for i, pt in enumerate(all_pages):
        s = _score_page(pt, PNL_SYNS) + _score_page(pt, BS_SYNS)
        scored.append((s, i, pt))

    # Sort by score desc; build claude_text starting with highest-value pages
    scored.sort(key=lambda x: -x[0])
    claude_parts = []
    total_chars = 0
    for score, idx, pt in scored:
        chunk = f"--- PAGE {idx+1} ---\n{pt}"
        if total_chars + len(chunk) > MAX_TEXT_CHARS:
            break
        claude_parts.append((idx, chunk))
        total_chars += len(chunk)

    # Restore page order for readability
    claude_parts.sort(key=lambda x: x[0])
    claude_text = "\n".join(c for _, c in claude_parts)
    if not claude_text:
        # Fallback: just truncate
        claude_text = "\n".join(f"--- PAGE {i+1} ---\n{p}" for i, p in enumerate(all_pages))
        claude_text = claude_text[:MAX_TEXT_CHARS]

    return claude_text, all_pages, page_count, used_ocr


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def _build_row_list(rows: list[tuple]) -> str:
    return "\n".join(f'  - "{k}": {lbl}' for _, k, lbl in rows)


def _build_pattern_hints(pattern_lib: dict) -> str:
    """Format learned patterns as few-shot hints in the prompt."""
    hints = []
    for stmt in ("pnl", "bs"):
        for key, labels in (pattern_lib.get(stmt) or {}).items():
            top = labels[:6]  # top 6 most-seen
            hints.append(f'  {key} ({stmt}): {", ".join(top)}')
    if not hints:
        return "  (none yet — this is the first ingestion)"
    return "\n".join(hints)


def build_extraction_prompt(pdf_text: str, pattern_lib: dict,
                             entity_type: str, fiscal_year_end: str) -> str:
    row_list = _build_row_list(ALL_ROWS)
    pattern_hints = _build_pattern_hints(pattern_lib)

    return f"""You are a financial data extraction specialist. Extract financial data from the text of a {'listed company annual report' if entity_type == 'listed' else 'SME compilation report'} and return it as structured JSON.

## Document context
- Entity type: {entity_type.upper()}
- Fiscal year end: {fiscal_year_end or 'unknown'}

## Canonical rows to extract
Extract values for ALL of the following rows (use null if not found):
{row_list}

## Learned label patterns (from previously ingested documents)
These raw PDF labels have previously been mapped to canonical keys — use them as hints:
{pattern_hints}

## Output format
Return ONLY valid JSON, no markdown fences, in this exact structure:
{{
  "periods": ["2025", "2024"],          // fiscal years found, most recent first
  "currency": "NZD",                    // or AUD, USD, etc.
  "unit": "whole",                      // "whole" | "thousands" | "millions"
  "rows": [
    {{
      "statement": "pnl",               // "pnl" or "bs"
      "canonical_key": "revenue",
      "raw_label": "Total operating revenue",   // exact label from PDF
      "values": {{"2025": 1234567, "2024": 1100000}},  // null if not found
      "confidence": 0.95                // 0–1
    }}
  ],
  "extraction_notes": "Brief notes about any ambiguities or issues"
}}

Rules:
1. Numbers should be in the base unit specified (not divided by thousands/millions).
2. Negative values (losses, expenses shown as negatives) use negative numbers.
3. Dashes or blanks = null.
4. If a line is described as "(000s)" or "in thousands", set unit = "thousands".
5. For BS: derive Total assets = Total current assets + Fixed assets (net) + Other non-current.
6. Match synonyms flexibly — e.g. "Net revenue", "Sales", "Operating revenue" → revenue.
7. Report the raw_label exactly as it appears in the PDF for pattern learning.

## PDF text
{pdf_text}
"""


async def call_claude(prompt: str, model: str = None) -> str:
    # Read key + model fresh from env each call (supports runtime updates via /settings)
    key   = os.environ.get("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY
    model = model or os.environ.get("CLAUDE_MODEL") or CLAUDE_MODEL
    client = anthropic.Anthropic(api_key=key)
    # Run sync client in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    ))
    return response.content[0].text


def parse_claude_response(raw: str) -> dict:
    """Strip any accidental markdown fences and parse JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

async def persist_extraction(
    db: aiosqlite.Connection,
    document_id: int,
    company_id: int,
    parsed: dict,
    entity_type: str,
    exchange: Optional[str],
):
    """Write financial_rows and update label patterns from Claude's response."""
    periods  = parsed.get("periods", [])
    currency = parsed.get("currency", "NZD")
    unit     = parsed.get("unit", "whole")
    rows     = parsed.get("rows", [])

    new_patterns = []

    for row in rows:
        stmt   = row.get("statement", "")
        key    = row.get("canonical_key", "")
        raw_lbl = row.get("raw_label", "")
        values = row.get("values", {})
        conf   = row.get("confidence", 0.8)

        # Find display label
        display_lbl = next((lbl for _, k, lbl in ALL_ROWS if k == key), key)

        for period, value in values.items():
            await db.execute("""
                INSERT INTO financial_rows
                    (document_id, company_id, statement, row_key, row_label,
                     period, value, currency, unit, source_text, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (document_id, company_id, stmt, key, display_lbl,
                  period, value, currency, unit, raw_lbl, conf))

        # Queue pattern for learning
        if raw_lbl and key:
            new_patterns.append({
                "canonical_key": key,
                "statement":     stmt,
                "raw_label":     raw_lbl,
                "entity_type":   entity_type,
                "exchange":      exchange,
            })

    await db.commit()

    # Record patterns (upsert with match_count++)
    await record_patterns(db, new_patterns)

    return len(rows)


# ---------------------------------------------------------------------------
# Main ingestion entry point
# ---------------------------------------------------------------------------

async def ingest_document(
    db: aiosqlite.Connection,
    document_id: int,
    company_id: int,
    filepath: str,
    entity_type: str,       # 'listed' | 'sme'
    exchange: Optional[str],
    fiscal_year_end: str,
) -> dict:
    """
    Full ingestion pipeline. Returns summary dict.
    Updates document.extraction_status throughout.
    """
    async def log(level: str, msg: str):
        await db.execute(
            "INSERT INTO extraction_log (document_id, level, message) VALUES (?,?,?)",
            (document_id, level, msg)
        )
        await db.commit()
        print(f"[{level.upper()}] doc={document_id}: {msg}")

    result = {"document_id": document_id, "rows_saved": 0, "error": None}

    try:
        # Mark processing
        await db.execute(
            "UPDATE documents SET extraction_status='processing', updated_at=datetime('now') WHERE id=?",
            (document_id,)
        )
        await db.commit()

        # 1. Extract text
        await log("info", f"Extracting text from {filepath}")
        claude_text, all_page_texts, page_count, used_ocr = extract_pdf_text(filepath)
        await db.execute(
            "UPDATE documents SET page_count=?, has_ocr=?, updated_at=datetime('now') WHERE id=?",
            (page_count, int(used_ocr), document_id)
        )
        await db.commit()
        await log("info", f"Extracted {page_count} pages ({len(claude_text)} chars for Claude, {sum(len(p) for p in all_page_texts)} total)")

        # 2. Load current pattern library
        pattern_lib = await get_pattern_library(db)
        await log("info", f"Pattern library: {sum(len(v) for v in pattern_lib.values())} total patterns")

        # 3. Try Claude; fall back to rule-based extractor on billing/auth errors
        parsed = None
        extraction_method = "rule_based"
        live_model = os.environ.get("CLAUDE_MODEL") or CLAUDE_MODEL

        api_key = os.environ.get("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY
        if api_key and not api_key.startswith("sk-ant-YOUR"):
            try:
                await log("info", f"Calling Claude ({live_model})…")
                prompt = build_extraction_prompt(claude_text, pattern_lib, entity_type, fiscal_year_end)
                raw_response = await call_claude(prompt)
                parsed = parse_claude_response(raw_response)
                extraction_method = live_model
                periods = parsed.get("periods", [])
                await log("info", f"Claude extracted {len(parsed.get('rows',[]))} rows for periods {periods}")
                # Save raw response
                await db.execute("""
                    UPDATE documents SET
                        raw_claude_response = ?,
                        extraction_model    = ?,
                        updated_at          = datetime('now')
                    WHERE id = ?
                """, (raw_response, live_model, document_id))
                await db.commit()
            except Exception as claude_err:
                err_str = str(claude_err)
                if "credit balance" in err_str or "invalid x-api-key" in err_str or "authentication" in err_str.lower():
                    await log("warn", f"Claude unavailable ({err_str[:120]}) — falling back to rule-based extractor")
                    parsed = None
                else:
                    raise  # unexpected error — let it bubble up

        # Rule-based fallback — uses full un-truncated page list
        if parsed is None:
            from rule_extractor import rule_based_extract
            parsed = rule_based_extract(all_page_texts)
            extraction_method = "rule_based"
            periods = parsed.get("periods", [])
            await log("info", f"Rule-based extractor: {len(parsed.get('rows',[]))} rows for periods {periods}")
            await db.execute(
                "UPDATE documents SET extraction_model=?, updated_at=datetime('now') WHERE id=?",
                (extraction_method, document_id)
            )
            await db.commit()

        # 4. Persist rows + patterns
        rows_saved = await persist_extraction(
            db, document_id, company_id, parsed, entity_type, exchange
        )
        result["rows_saved"] = rows_saved
        result["periods"] = parsed.get("periods", [])

        # 5. Mark done
        avg_conf = sum(r.get("confidence", 0.8) for r in parsed.get("rows", [])) / max(len(parsed.get("rows", [])), 1)
        await db.execute("""
            UPDATE documents SET
                extraction_status = 'done',
                confidence_score  = ?,
                updated_at        = datetime('now')
            WHERE id = ?
        """, (avg_conf, document_id))
        await db.commit()
        await log("info", f"Done ({extraction_method}). {rows_saved} rows saved, avg confidence {avg_conf:.2f}")

    except Exception as e:
        result["error"] = str(e)
        await db.execute(
            "UPDATE documents SET extraction_status='failed', updated_at=datetime('now') WHERE id=?",
            (document_id,)
        )
        await db.commit()
        await log("error", str(e))
        raise

    return result
