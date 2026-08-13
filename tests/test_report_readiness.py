from report_readiness import assess_credit_financial_readiness, report_follow_up_items


def test_credit_readiness_requires_pnl_and_balance_sheet():
    readiness = assess_credit_financial_readiness(
        [{"statement": "pnl", "row_key": "revenue", "period": "FY2025", "value": 1_000_000}]
    )

    assert readiness["ready"] is False
    assert "EBITDA or profit" in readiness["issues"]
    assert "a balance sheet" in readiness["issues"]
    assert readiness["follow_up_items"]


def test_credit_readiness_is_ready_but_keeps_lender_follow_ups_visible():
    readiness = assess_credit_financial_readiness(
        [
            {"statement": "pnl", "row_key": "revenue", "period": "FY2024", "value": 900_000},
            {"statement": "pnl", "row_key": "revenue", "period": "FY2025", "value": 1_000_000},
            {"statement": "pnl", "row_key": "ebitda", "period": "FY2025", "value": 180_000},
            {"statement": "bs", "row_key": "cash_and_bank", "period": "FY2025", "value": 80_000},
            {"statement": "bs", "row_key": "long_term_debt", "period": "FY2025", "value": 250_000},
        ]
    )

    assert readiness["ready"] is True
    assert any(item["label"] == "Debt schedule, payout letters and lender statements" for item in readiness["follow_up_items"])
    assert any(item["label"] == "A more recent balance sheet" for item in readiness["follow_up_items"])


def test_report_follow_ups_are_separated_by_report_type():
    follow_ups = report_follow_up_items(
        {"revenue_periods": ["FY2025"], "earnings_periods": ["FY2025"]},
        {"follow_up_items": [{"label": "Debt schedule", "impact": "Confirms debt."}]},
    )

    assert follow_ups["valuation_advisory"][0]["label"] == "Additional historical financial statements"
    assert follow_ups["bank_credit_paper"][0]["label"] == "Debt schedule"
