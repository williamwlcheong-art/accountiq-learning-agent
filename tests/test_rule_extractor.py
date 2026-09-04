"""Regression tests for no-key rule-based financial extraction."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from rule_extractor import BS_SYNS, rule_based_extract


def _row(parsed: dict, key: str) -> dict:
    return next(row for row in parsed["rows"] if row["canonical_key"] == key)


def test_rule_based_extract_preserves_decimal_amounts_and_ebitda_from_chequers_pnl():
    text = """
Profit and Loss
Towing And Recovery Limited
For the year ended 31 March 2026
                                                                      2026           2025           2024

TradingIncome
  Sales                                                       4,423,902.72   4,955,763.65   5,686,143.48
  TotalTradingIncome                                          4,423,902.72   4,955,763.65   5,686,143.48

Costof Sales
  Fuel                                                          186,498.50     199,276.72     318,360.49
  Wages&Salaries                                              1,648,147.73   1,707,082.14   2,026,330.30
  TotalCostofSales                                            2,191,826.18   2,258,075.25   2,843,926.50

GrossProfit                                                   2,232,076.54   2,697,688.40   2,842,216.98

OtherIncome
  SundryIncome                                                    1,153.79      70,857.68      34,002.87
  TotalOtherIncome                                                1,153.79      70,857.68      34,002.87

OperatingExpenses
  DepreciationExpenses                                          400,839.79     486,519.57     544,901.88
  Interest                                                       66,396.94     206,014.80     227,208.38
  OtherExpenses                                               1,002,385.40   1,165,996.33   1,310,753.59
  Rent                                                          228,053.51     237,979.13     195,276.25
  TotalOperatingExpenses                                      1,814,221.83   2,384,175.89   2,533,223.58

NetProfit                                                      419,008.50     384,370.19     342,996.27
EBITDA                                                         886,245.23   1,253,447.15   1,260,619.56
"""

    parsed = rule_based_extract([text])

    assert parsed["periods"] == ["2026", "2025", "2024"]
    assert _row(parsed, "revenue")["values"]["2026"] == 4_423_902.72
    assert _row(parsed, "revenue")["values"]["2025"] == 4_955_763.65
    assert _row(parsed, "ebitda")["values"]["2026"] == 886_245.23
    assert _row(parsed, "interest_expense")["values"]["2026"] == 66_396.94
    assert _row(parsed, "net_profit")["values"]["2024"] == 342_996.27


def test_balance_sheet_total_categories_are_not_misclassified_as_fixed_assets_or_debt():
    assert "total non current assets" not in BS_SYNS["fixed_assets_net"]
    assert "total noncurrent assets" not in BS_SYNS["fixed_assets_net"]
    assert "total non current assets" in BS_SYNS["other_noncurrent_assets"]
    assert "total noncurrent liabilities" not in BS_SYNS["long_term_debt"]
    assert "total noncurrent liabilities" in BS_SYNS["other_noncurrent_liab"]


def test_rule_based_extract_combines_multi_page_profit_and_loss_statements():
    pages = [
        """
        Statement of Profit or Loss
        2025 2024
        Revenue 1,000,000 900,000
        EBITDA 220,000 180,000
        """,
        """
        Statement of Profit or Loss
        2025 2024
        Net Profit (Loss) for the Year 145,000 110,000
        """,
        """
        Notes to the Financial Statements
        Revenue 9,999,999 9,999,999
        """,
    ]

    parsed = rule_based_extract(pages)

    assert _row(parsed, "revenue")["values"] == {"2025": 1_000_000.0, "2024": 900_000.0}
    assert _row(parsed, "ebitda")["values"] == {"2025": 220_000.0, "2024": 180_000.0}
    assert _row(parsed, "net_profit")["values"] == {"2025": 145_000.0, "2024": 110_000.0}
