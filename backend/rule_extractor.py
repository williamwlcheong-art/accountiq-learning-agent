"""
Rule-based financial extractor — no API credits needed.
Uses synonym dictionaries + column detection, same approach as the AccountIQ SPA.
Falls back gracefully when Claude API is unavailable.
"""
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Synonym dictionaries
# ---------------------------------------------------------------------------

PNL_SYNS: dict[str, list[str]] = {
    "revenue": [
        "total revenue", "total revenues", "total operating revenue", "total operating revenues",
        "revenue", "revenues", "net revenue", "net revenues", "sales", "net sales",
        "operating revenue", "operating revenues", "total income", "total sales",
        "gross revenue", "turnover", "total turnover", "net turnover",
        "total fees", "fee revenue", "service revenue", "contract revenue",
        # AU/NZ SME income additions
        "other income", "sundry income", "miscellaneous income",
    ],
    "cogs": [
        "cost of goods sold", "cost of sales", "cost of revenue", "cost of services",
        "direct costs", "direct cost of sales", "cogs", "cost of products sold",
        "cost of providing services", "cost of materials", "materials and direct costs",
        # AU/NZ SME trade/construction additions
        "subcontractors", "subcontract costs", "contract labour",
    ],
    "gross_profit": [
        "gross profit", "gross margin", "gross profit margin", "gross income",
    ],
    "operating_expenses": [
        "total operating expenses", "total expenses", "total operating costs",
        "operating expenditure", "total expenditure", "total costs",
        "operating costs", "expenses", "total administration expenses",
        # AU/NZ SME additions
        "owners drawings", "drawings",
        "directors fees", "directors remuneration",
        "wages", "wages and salaries", "salaries and wages",
        "administration expenses", "admin expenses",
        "motor vehicle expenses", "vehicle costs",
    ],
    "ebitda": [
        "ebitda", "earnings before interest tax depreciation amortisation",
        "earnings before interest taxes depreciation and amortization",
        "operating profit before depreciation",
    ],
    "depreciation": [
        "depreciation and amortisation", "depreciation and amortization",
        "depreciation amortisation", "depreciation", "amortisation", "amortization",
        "d&a", "depreciation & amortisation",
    ],
    "ebit": [
        "ebit", "operating profit", "profit from operations", "loss from operations",
        "earnings before interest and tax", "earnings before interest and taxes",
        "operating income", "operating loss",
    ],
    "interest_expense": [
        "interest expense", "finance costs", "finance cost", "interest costs",
        "net interest expense", "borrowing costs", "interest and finance charges",
        "interest paid", "net finance costs",
    ],
    "pbt": [
        "profit before tax", "loss before tax", "profit before income tax",
        "loss before income tax", "earnings before tax", "net profit before tax",
        "profit before taxation", "net income before tax",
    ],
    "tax": [
        "income tax expense", "income tax", "tax expense", "income tax benefit",
        "tax on profit", "tax on continuing operations", "tax charge",
        "current tax", "deferred tax", "income taxes",
    ],
    "net_profit": [
        "net profit", "net loss", "profit for the year", "loss for the year",
        "profit after tax", "net profit after tax", "npat", "net income",
        "profit attributable", "total comprehensive income",
        "profit for the period", "net earnings", "net profit for the year",
    ],
}

BS_SYNS: dict[str, list[str]] = {
    "cash_and_bank": [
        "cash and cash equivalents", "cash and bank", "cash at bank",
        "total cash and bank", "cash on hand", "cash and bank balances",
        "bank accounts", "bank current account", "cash",
    ],
    "trade_debtors": [
        "trade and other receivables", "trade receivables", "trade debtors",
        "accounts receivable", "debtors", "receivables", "net receivables",
        "trade receivables and other debtors",
    ],
    "inventory": [
        "inventories", "inventory", "stock", "stock on hand",
        "total inventory", "finished goods", "raw materials",
    ],
    "other_current_assets": [
        "other current assets", "prepayments", "other receivables",
        "prepayments and other current assets", "other assets",
        "accrued income", "contract assets",
    ],
    "total_current_assets": [
        "total current assets", "total currentassets", "current assets total",
    ],
    "fixed_assets_net": [
        "property plant and equipment", "property, plant and equipment",
        "total property plant and equipment", "fixed assets", "net book value",
        "right of use assets", "right-of-use assets",
        "total non current assets", "total noncurrent assets",
        "plant equipment and vehicles", "capital assets",
    ],
    "other_noncurrent_assets": [
        "intangible assets", "goodwill", "other non-current assets",
        "deferred tax assets", "investments",
    ],
    "total_assets": [
        "total assets",
    ],
    "trade_creditors": [
        "trade and other payables", "trade payables", "trade creditors",
        "accounts payable", "creditors", "payables",
    ],
    "short_term_debt": [
        "current portion of borrowings", "current borrowings",
        "bank overdraft", "overdraft", "current portion of loans",
        "loans hire purchase", "loans and hire purchase",
    ],
    "other_current_liab": [
        "other current liabilities", "accrued liabilities", "accrued expenses",
        "gst payable", "income tax payable", "employee entitlements",
        "provisions", "deferred revenue", "contract liabilities",
    ],
    "total_current_liab": [
        "total current liabilities", "total currentliabilities", "current liabilities total",
    ],
    "long_term_debt": [
        "term loans", "term loan", "non-current borrowings", "borrowings",
        "long term loans", "long-term loans", "mortgage",
        "total non current liabilities", "total noncurrent liabilities",
        "finance lease", "hire purchase", "shareholder loans",
        "related party loans", "loans payable", "loans",
    ],
    "other_noncurrent_liab": [
        "other non-current liabilities", "deferred tax liabilities",
        "non-current provisions",
    ],
    "total_liabilities": [
        "total liabilities",
    ],
    "shareholders_equity": [
        "total equity", "net assets", "shareholders equity", "shareholders funds",
        "owners equity", "total shareholders equity", "total owners equity",
        "share capital and retained earnings", "retained earnings and share capital",
        "equity attributable to owners",
    ],
}

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

# Rows that should SUM multiple matched lines (not last-wins)
SUM_KEYS = {"other_current_liab", "other_noncurrent_assets", "other_noncurrent_liab"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_numbers(line: str) -> list[Optional[float]]:
    """Extract numbers preserving None for dashes (null values)."""
    tokens = re.findall(r'\([\d,]+\)|[-\u2013\u2014](?=\s|$)|\d[\d,]*', line)
    result = []
    for t in tokens:
        if re.match(r'^[-\u2013\u2014]$', t):
            result.append(None)
        elif t.startswith('(') and t.endswith(')'):
            num = float(t[1:-1].replace(',', ''))
            result.append(-num)
        else:
            result.append(float(t.replace(',', '')))
    return result


def _detect_periods(page_text: str) -> list[str]:
    """Find fiscal years mentioned in column headers."""
    year_re = re.compile(r'\b(FY\s?\d{2,4}|20\d{2})\b')
    for line in page_text.split('\n'):
        matches = year_re.findall(line)
        if len(matches) >= 2:
            years = []
            for m in matches:
                m = m.replace(' ', '')
                if m.startswith('FY'):
                    yr = '20' + m[-2:]
                else:
                    yr = m
                if yr not in years:
                    years.append(yr)
            if years:
                return years
    # Fallback: find any 4-digit years >= 2000
    all_years = sorted(set(re.findall(r'\b(20\d{2})\b', page_text)), reverse=True)
    return all_years[:3] if all_years else []


def _match_row(label_norm: str, syns: dict[str, list[str]]) -> Optional[str]:
    """Return canonical key for a normalised label, longest-match first."""
    best_key = None
    best_len = 0
    for key, synonyms in syns.items():
        for syn in synonyms:
            sn = _norm(syn)
            if sn in label_norm or label_norm in sn:
                if len(sn) > best_len:
                    best_len = len(sn)
                    best_key = key
    return best_key


# ---------------------------------------------------------------------------
# Score pages to find P&L and BS pages
# ---------------------------------------------------------------------------

def _score_page(page_text: str, syns: dict) -> int:
    score = 0
    nums = _extract_numbers(page_text)
    if not any(v is not None and abs(v) >= 1000 for v in nums):
        return 0
    for line in page_text.split('\n'):
        ln = _norm(line)
        for key, synonyms in syns.items():
            if any(_norm(s) in ln for s in synonyms):
                score += 1
                break
    return score


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def _extract_statement(pages: list[str], syns: dict[str, list[str]]) -> dict:
    """
    Find the best page for a statement, extract values, return:
    { canonical_key: { period: value } }
    """
    # Score all pages
    scores = [_score_page(p, syns) for p in pages]
    best_idx = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0

    if scores[best_idx] < 2:
        return {}

    best_page = pages[best_idx]
    periods = _detect_periods(best_page)
    if not periods:
        return {}

    n_cols = len(periods)
    rows: dict[str, dict[str, Optional[float]]] = {k: {} for k in syns}

    lines = best_page.split('\n')
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        # Strip trailing numbers to get label
        label_only = re.sub(r'[\d,.()\-\u2013\u2014\s]+$', '', clean).strip()
        label_norm = _norm(label_only or clean)
        if not label_norm:
            continue

        key = _match_row(label_norm, syns)
        if not key:
            continue

        nums = _extract_numbers(clean)
        if not nums:
            continue

        # Take the last N columns
        cols = nums[-n_cols:] if len(nums) >= n_cols else nums

        # Pad left with None if fewer cols than periods
        while len(cols) < n_cols:
            cols = [None] + cols

        # Must have at least one real value ≥ 100
        real_vals = [v for v in cols if v is not None and abs(v) >= 100]
        if not real_vals:
            continue

        if key in SUM_KEYS:
            # Accumulate
            for i, period in enumerate(periods):
                if i < len(cols) and cols[i] is not None:
                    rows[key][period] = (rows[key].get(period) or 0) + cols[i]
        else:
            # Last-match for totals, first-match otherwise
            is_total = label_norm.startswith('total')
            existing = rows[key]
            if is_total or not existing:
                for i, period in enumerate(periods):
                    if i < len(cols):
                        rows[key][period] = cols[i]

    return {k: v for k, v in rows.items() if v}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def rule_based_extract(text_pages: list[str]) -> dict:
    """
    Run rule-based extraction on all pages.
    Returns a dict shaped like Claude's JSON response.
    """
    # Determine periods from all pages combined
    combined = "\n".join(text_pages)
    periods = _detect_periods(combined)

    # Extract P&L and BS
    pnl_data = _extract_statement(text_pages, PNL_SYNS)
    bs_data  = _extract_statement(text_pages, BS_SYNS)

    # Detect currency
    currency = "NZD"
    if re.search(r'\bA\$|AUD\b', combined):
        currency = "AUD"
    elif re.search(r'\bUS\$|USD\b', combined):
        currency = "USD"

    # Detect unit
    unit = "whole"
    if re.search(r'\$000|in thousands|thousands of dollars', combined, re.I):
        unit = "thousands"
    elif re.search(r'in millions|millions of dollars', combined, re.I):
        unit = "millions"

    rows = []
    for key, vals in pnl_data.items():
        if vals:
            rows.append({
                "statement":     "pnl",
                "canonical_key": key,
                "raw_label":     key.replace("_", " "),
                "values":        vals,
                "confidence":    0.70,
            })
    for key, vals in bs_data.items():
        if vals:
            rows.append({
                "statement":     "bs",
                "canonical_key": key,
                "raw_label":     key.replace("_", " "),
                "values":        vals,
                "confidence":    0.70,
            })

    return {
        "periods":           periods,
        "currency":          currency,
        "unit":              unit,
        "rows":              rows,
        "extraction_notes":  "Rule-based extraction (no Claude API). Accuracy ~70-80%. Top up credits for Claude-powered extraction.",
    }
