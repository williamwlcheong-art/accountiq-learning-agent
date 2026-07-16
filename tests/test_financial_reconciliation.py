"""Tests for multi-file financial reconciliation and balance-sheet checks."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from financial_reconciliation import normalise_financial_period, reconcile_financial_rows


def _row(
    document_id: int,
    filename: str,
    statement: str,
    row_key: str,
    period: str,
    value: float,
    **extra,
) -> dict:
    return {
        "document_id": document_id,
        "filename": filename,
        "statement": statement,
        "row_key": row_key,
        "row_label": row_key.replace("_", " ").title(),
        "period": period,
        "value": value,
        "currency": "NZD",
        "unit": "whole",
        "confidence": 0.9,
        **extra,
    }


def test_normalise_financial_period_groups_common_fiscal_year_labels():
    assert normalise_financial_period("FY25") == "FY2025"
    assert normalise_financial_period("Year ended 31 March 2025") == "FY2025"
    assert normalise_financial_period("2024/25") == "FY2025"


def test_reconciliation_deduplicates_equivalent_values_after_unit_normalisation():
    result = reconcile_financial_rows(
        [
            _row(1, "annual-accounts.pdf", "pnl", "revenue", "FY25", 1_250, unit="thousands"),
            _row(2, "management-accounts.pdf", "pnl", "revenue", "31 March 2025", 1_250_000),
        ]
    )

    assert result["status"] == "ready"
    assert result["conflicts"] == []
    assert result["rows"] == [
        {
            "document_id": 1,
            "source_filename": "annual-accounts.pdf",
            "statement": "pnl",
            "row_key": "revenue",
            "row_label": "Revenue",
            "period": "FY2025",
            "value": 1_250_000.0,
            "currency": "NZD",
            "confidence": 0.9,
        }
    ]


def test_reconciliation_requires_source_selection_for_material_duplicate_year_difference():
    rows = [
        _row(1, "draft-accounts.pdf", "pnl", "revenue", "2025", 1_250_000, confidence=0.95),
        _row(2, "final-accounts.pdf", "pnl", "revenue", "FY2025", 1_100_000, confidence=0.85),
    ]

    unresolved = reconcile_financial_rows(rows)

    assert unresolved["status"] == "needs_review"
    assert unresolved["unresolved_conflict_ids"] == ["pnl:revenue:FY2025"]
    assert unresolved["conflicts"][0]["suggested_document_id"] == 1
    assert [source["filename"] for source in unresolved["conflicts"][0]["sources"]] == [
        "draft-accounts.pdf",
        "final-accounts.pdf",
    ]

    resolved = reconcile_financial_rows(rows, overrides={"pnl:revenue:FY2025": 2})

    assert resolved["status"] == "ready"
    assert resolved["unresolved_conflict_ids"] == []
    assert resolved["rows"][0]["source_filename"] == "final-accounts.pdf"
    assert resolved["rows"][0]["value"] == 1_100_000


def test_balance_sheet_review_classifies_core_lines_and_checks_accounting_identity():
    result = reconcile_financial_rows(
        [
            _row(1, "accounts.pdf", "bs", "cash_and_bank", "2025", 95_000),
            _row(1, "accounts.pdf", "bs", "trade_debtors", "2025", 210_000),
            _row(1, "accounts.pdf", "bs", "inventory", "2025", 65_000),
            _row(1, "accounts.pdf", "bs", "fixed_assets_net", "2025", 185_000),
            _row(1, "accounts.pdf", "bs", "trade_creditors", "2025", 155_000),
            _row(1, "accounts.pdf", "bs", "short_term_debt", "2025", 60_000),
            _row(1, "accounts.pdf", "bs", "long_term_debt", "2025", 100_000),
            _row(1, "accounts.pdf", "bs", "total_assets", "2025", 850_000),
            _row(1, "accounts.pdf", "bs", "total_liabilities", "2025", 420_000),
            _row(1, "accounts.pdf", "bs", "shareholders_equity", "2025", 430_000),
        ]
    )

    review = result["balance_sheet"]
    assert review["ready"] is True
    assert review["issues"] == []
    classification_labels = {item["label"] for item in review["periods"][0]["classifications"]}
    assert {
        "Cash and bank",
        "Accounts receivable",
        "Stock / inventory",
        "Fixed assets",
        "Accounts payable",
        "Short-term loans",
        "Long-term loans",
    } <= classification_labels
    assert review["periods"][0]["checks"] == [
        {
            "name": "Assets = liabilities + equity",
            "status": "balanced",
            "difference": 0.0,
        }
    ]


def test_balance_sheet_review_flags_an_unbalanced_statement():
    result = reconcile_financial_rows(
        [
            _row(1, "accounts.pdf", "bs", "total_assets", "2025", 850_000),
            _row(1, "accounts.pdf", "bs", "total_liabilities", "2025", 420_000),
            _row(1, "accounts.pdf", "bs", "shareholders_equity", "2025", 390_000),
        ]
    )

    assert result["balance_sheet"]["ready"] is False
    assert result["balance_sheet"]["issues"] == [
        "FY2025: total assets do not reconcile to total liabilities plus equity."
    ]
