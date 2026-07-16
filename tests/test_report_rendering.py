"""Tests for professional PDF rendering helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber
from reportlab.lib.enums import TA_LEFT, TA_RIGHT


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_rendering import (
    _report_table,
    _right_aligned_pdf_columns,
    _running_header_label,
    _styles,
    dcf_value_build_visual,
    equity_bridge_visual,
    executive_valuation_highlights,
    financial_trend_visual,
    implied_multiple_reconciliation,
    normalised_ebitda_bridge_visual,
    report_display_date,
    report_reference_code,
    sensitivity_spread_visual,
    valuation_method_selection,
    valuation_reader_guidance,
    valuation_range_visual,
    valuation_basis_of_preparation,
    wacc_build_visual,
    write_report_pdf,
)


def test_report_reference_code_is_professional_and_stable():
    assert report_reference_code(42, "valuation_advisory") == "AIQ-VAL-000042"
    assert report_reference_code(42, "bank_credit_paper") == "AIQ-REP-000042"
    assert report_reference_code("not numeric", "valuation_advisory") == "AIQ-VAL-000000"


def test_report_display_date_uses_formal_report_date_format():
    assert report_display_date("2026-07-04 09:15:00") == "4 July 2026"
    assert report_display_date("2026-07-04T09:15:00Z") == "4 July 2026"
    assert report_display_date("") == "Prepared date"
    assert report_display_date("Valuation date to confirm") == "Valuation date to confirm"


def test_pdf_table_alignment_keeps_source_evidence_columns_left_aligned():
    headers = ["Evidence / transaction", "Date", "Metric or multiple", "Relevance and limitations", "Source"]
    rows = [
        [
            "Comparable company valuation",
            "2026",
            "5.0x EBITDA",
            "Broad sector benchmark; not directly comparable.",
            "https://example.com/source",
        ]
    ]

    assert _right_aligned_pdf_columns(headers, rows, len(headers)) == set()


def test_pdf_table_alignment_right_aligns_financial_measure_columns():
    headers = ["Indicative valuation", "High", "Mid", "Low"]
    rows = [
        ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
        ["Less: net debt", "$65,000", "$65,000", "$65,000"],
    ]

    assert _right_aligned_pdf_columns(headers, rows, len(headers)) == {1, 2, 3}


def test_pdf_table_alignment_keeps_rationale_text_left_but_amounts_right():
    headers = ["Label", "Amount ($)", "Rationale"]
    rows = [["Owner salary", "$50,000", "Above market salary adjustment"]]

    assert _right_aligned_pdf_columns(headers, rows, len(headers)) == {1}


def test_report_table_applies_right_aligned_paragraph_styles_to_financial_columns():
    table = _report_table(
        {
            "headers": ["Adjustment", "Amount ($)", "Rationale"],
            "rows": [["Owner salary", "$50,000", "Above market salary adjustment"]],
        },
        available_width=500,
        styles=_styles(),
    )

    assert table is not None
    assert table._cellvalues[0][1].style.alignment == TA_RIGHT
    assert table._cellvalues[1][1].style.alignment == TA_RIGHT
    assert table._cellvalues[0][2].style.alignment == TA_LEFT
    assert table._cellvalues[1][2].style.alignment == TA_LEFT


def test_running_header_label_includes_report_and_company_context():
    label = _running_header_label("Acme Holdings Limited", "Indicative Valuation Report")

    assert label == "Indicative Valuation Report | Acme Holdings Limited"


def test_running_header_label_truncates_long_company_names():
    label = _running_header_label(
        "Very Long Trading Company Name With Multiple Business Units And Regional Branches Limited",
        "Indicative Valuation Report",
        max_chars=48,
    )

    assert len(label) == 48
    assert label.endswith("...")


def test_executive_valuation_highlights_use_computed_summary_table():
    sections = {
        "executive_summary": {
            "table": {
                "headers": ["Indicative valuation", "High", "Mid", "Low"],
                "rows": [
                    ["Enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                    ["Less: net debt", "$65,000", "$65,000", "$65,000"],
                    ["Indicative equity value", "$2,766,000", "$2,249,000", "$1,833,000"],
                ],
            },
        },
    }

    highlights = executive_valuation_highlights(sections)
    range_title, range_rows = valuation_range_visual(sections)

    assert (
        "Enterprise value range",
        "$1,898,000 - $2,831,000",
        "Primary DCF valuation range after the private-company illiquidity adjustment.",
    ) in highlights
    assert (
        "Midpoint enterprise value",
        "$2,314,000",
        "Central indication before the net debt and surplus asset bridge.",
    ) in highlights
    assert (
        "Midpoint equity value",
        "$2,249,000",
        "Central shareholder-value indication after the enterprise-to-equity bridge.",
    ) in highlights
    assert (
        "Net debt adjustment",
        "$65,000",
        "Bridge item applied consistently across the valuation scenarios.",
    ) in highlights
    assert range_title == "Valuation range visual"
    assert range_rows[0]["label"] == "Enterprise value"
    assert range_rows[0]["low_label"] == "$1,898,000"
    assert range_rows[0]["mid_label"] == "$2,314,000"
    assert range_rows[0]["high_label"] == "$2,831,000"
    assert range_rows[0]["low_value"] == 1898000
    assert range_rows[0]["mid_value"] == 2314000
    assert range_rows[0]["high_value"] == 2831000
    assert range_rows[1]["label"] == "Indicative equity value"
    assert range_rows[1]["low_label"] == "$1,833,000"
    assert range_rows[1]["mid_label"] == "$2,249,000"
    assert range_rows[1]["high_label"] == "$2,766,000"


def test_financial_trend_visual_uses_computed_financial_performance_table():
    sections = {
        "financial_performance": {
            "table": {
                "headers": ["Year ending March", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                "rows": [
                    ["Revenue", "$980,000", "$1,110,000", "$1,250,000", "$1,350,000"],
                    ["Gross profit", "$588,000", "$682,600", "$787,500", "$850,500"],
                    ["EBITDA", "$165,000", "$205,000", "$240,000", "$259,000"],
                    ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                ],
            },
        }
    }

    title, rows = financial_trend_visual(sections)

    assert title == "Financial trend visual"
    assert rows[0]["period"] == "FY23 Actual"
    assert rows[0]["revenue_label"] == "$980,000"
    assert rows[0]["revenue_value"] == 980000
    assert rows[0]["ebitda_label"] == "$165,000"
    assert rows[0]["ebitda_value"] == 165000
    assert rows[0]["margin_label"] == "16.8%"
    assert rows[-1]["period"] == "FY26 Forecast"
    assert rows[-1]["revenue_label"] == "$1,350,000"
    assert rows[-1]["ebitda_label"] == "$259,000"


def test_sensitivity_spread_visual_uses_computed_sensitivity_matrix():
    sections = {
        "sensitivity_and_risks": {
            "table": {
                "headers": [
                    "Growth assumption",
                    "High valuation / 9.9% WACC",
                    "Mid valuation / 11.5% WACC",
                    "Low valuation / 13.4% WACC",
                ],
                "rows": [
                    ["6.0%", "$2,621,000", "$2,147,000", "$1,765,000"],
                    ["8.0% - base", "$2,831,000", "$2,314,000", "$1,898,000"],
                    ["10.0%", "$3,054,000", "$2,492,000", "$2,040,000"],
                ],
            },
        },
    }

    title, rows = sensitivity_spread_visual(sections)

    assert title == "Sensitivity spread visual"
    assert rows[0]["label"] == "Adjusted enterprise value sensitivity"
    assert rows[0]["low_label"] == "$1,765,000"
    assert rows[0]["mid_label"] == "$2,314,000"
    assert rows[0]["high_label"] == "$3,054,000"
    assert rows[0]["low_value"] == 1765000
    assert rows[0]["mid_value"] == 2314000
    assert rows[0]["high_value"] == 3054000
    assert "6.0% to 10.0%" in rows[0]["note"]


def test_equity_bridge_visual_uses_computed_balance_sheet_bridge():
    sections = {
        "balance_sheet_summary": {
            "table": {
                "headers": ["Balance sheet item", "Value"],
                "rows": [
                    ["Cash and bank", "$95,000"],
                    ["Interest-bearing debt", "$160,000"],
                    ["Net debt", "$65,000"],
                    ["Surplus assets", "$0"],
                    ["Midpoint enterprise value", "$2,314,000"],
                    ["Less: net debt", "($65,000)"],
                    ["Midpoint equity value", "$2,249,000"],
                ],
            },
        },
    }

    title, row = equity_bridge_visual(sections)

    assert title == "Enterprise-to-equity visual"
    assert row["enterprise_label"] == "$2,314,000"
    assert row["net_debt_label"] == "($65,000)"
    assert row["surplus_label"] == "$0"
    assert row["equity_label"] == "$2,249,000"
    assert row["enterprise_value"] == 2314000
    assert row["net_debt_value"] == -65000
    assert row["equity_value"] == 2249000
    assert "shareholder value" in row["note"]


def test_normalised_ebitda_bridge_visual_uses_confirmed_adjustments():
    sections = {
        "normalisations_schedule": {
            "table": {
                "headers": ["Adjustment", "Amount", "Rationale"],
                "rows": [
                    ["Owner remuneration above market", "$35,000", "Replace with an arm's-length management cost"],
                    ["One-off legal costs", "$12,000", "Non-recurring legal expenditure"],
                    ["Normalised FY25 EBITDA", "$287,000", "Reported EBITDA plus confirmed adjustments"],
                ],
            }
        }
    }

    visual = normalised_ebitda_bridge_visual(sections)

    assert visual is not None
    title, row = visual
    assert title == "Normalised EBITDA bridge"
    assert row["uploaded_ebitda_label"] == "$240,000"
    assert row["net_adjustment_label"] == "$47,000"
    assert row["normalised_ebitda_label"] == "$287,000"
    assert row["adjustment_count_label"] == "2 adjustments"
    assert "uploaded operating earnings" in row["note"]
    assert "uploaded accounts" in row["note"]
    assert "confirmed adjustment rows" in row["note"]
    assert "earnings-adjustment review" in row["note"]
    assert "same normalised EBITDA is carried into DCF and multiples" in row["note"]


def test_dcf_value_build_visual_uses_computed_dcf_and_cash_flow_schedule():
    sections = {
        "dcf_analysis": {
            "table": {
                "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [
                    ["Enterprise value before illiquidity", "$3,209,000", "$2,624,000", "$2,152,000"],
                    ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                    ["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                ],
            },
            "cash_flow_schedule": {
                "headers": ["Mid-case forecast", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
                "rows": [
                    ["Discounted free cash flow", "$178,234", "$172,639", "$167,220", "$161,971", "$156,887"],
                ],
            },
        },
    }

    title, row = dcf_value_build_visual(sections)

    assert title == "DCF value build visual"
    assert row["explicit_fcff_label"] == "$836,951"
    assert row["terminal_value_label"] == "$1,787,049"
    assert row["ev_before_illiquidity_label"] == "$2,624,000"
    assert row["illiquidity_discount_label"] == "$310,000"
    assert row["adjusted_ev_label"] == "$2,314,000"
    assert row["explicit_fcff_value"] == 836951
    assert row["terminal_value"] == 1787049
    assert row["illiquidity_discount_value"] == 310000
    assert "discounted cash flows and terminal value" in row["note"]


def test_wacc_build_visual_uses_computed_wacc_inputs_without_owner_assumptions():
    sections = {
        "wacc_assumptions": {
            "table": {
                "headers": ["Component", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [
                    ["Risk-free rate", "4.4%", "4.4%", "4.4%"],
                    ["Equity risk premium", "5.6%", "5.9%", "6.2%"],
                    ["Industry total beta", "1.05", "1.20", "1.35"],
                    ["WACC", "9.9%", "11.5%", "13.4%"],
                    ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                ],
            },
        },
    }

    title, row = wacc_build_visual(sections)

    assert title == "WACC build visual"
    assert row["risk_free_label"] == "4.4%"
    assert row["erp_label"] == "5.9%"
    assert row["beta_label"] == "1.20"
    assert row["beta_adjusted_premium_label"] == "7.1%"
    assert row["wacc_label"] == "11.5%"
    assert row["illiquidity_label"] == "11.8%"
    assert row["risk_free_value"] == 4.4
    assert round(row["beta_adjusted_premium_value"], 1) == 7.1
    assert row["wacc_value"] == 11.5
    assert "public market inputs" in row["note"]
    assert "1.20 total beta" in row["premium_note"]


def test_implied_multiple_reconciliation_compares_dcf_and_market_multiples():
    sections = {
        "multiples_crosscheck": {
            "table": {
                "headers": ["Input", "Low", "Mid", "High"],
                "rows": [
                    ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                    ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                    ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
                ],
            }
        },
        "valuation_summary": {
            "table": {
                "headers": ["Method / scenario", "Input", "Enterprise value", "Adjusted EV", "Equity value"],
                "rows": [
                    ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
                    ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
                    ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
                ],
            }
        },
    }

    visual = implied_multiple_reconciliation(sections)

    assert visual is not None
    title, row = visual
    assert title == "Implied multiple reconciliation"
    assert row["normalised_ebitda_label"] == "$287,000"
    assert row["market_range_label"] == "5.0x - 7.0x"
    assert row["dcf_post_range_label"] == "6.6x - 9.9x"
    assert row["dcf_pre_range_label"] == "7.5x - 11.2x"
    assert row["dcf_post_mid_label"] == "8.1x"
    assert row["midpoint_gap_label"] == "2.1x above market midpoint"


def test_valuation_method_selection_explains_adopted_and_rejected_approaches():
    sections = {
        "valuation_summary": {
            "table": {
                "headers": ["Method / scenario", "Input", "Enterprise value", "Adjusted EV", "Equity value"],
                "rows": [
                    ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
                    ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
                    ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
                ],
            }
        },
        "multiples_crosscheck": {
            "table": {
                "headers": ["Input", "Low", "Mid", "High"],
                "rows": [
                    ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                    ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                ],
            }
        },
        "balance_sheet_summary": {
            "table": {
                "headers": ["Balance sheet item", "Value"],
                "rows": [
                    ["Midpoint enterprise value", "$2,314,000"],
                    ["Less: net debt", "($65,000)"],
                    ["Midpoint equity value", "$2,249,000"],
                ],
            }
        },
    }

    visual = valuation_method_selection(sections)

    assert visual is not None
    title, rows = visual
    assert title == "Valuation approach selection"
    assert rows[0]["approach"] == "Income approach - DCF"
    assert rows[0]["role"] == "Adopted as primary"
    assert rows[0]["report_treatment"] == "Primary adjusted enterprise-value range: $1,898,000 - $2,831,000."
    assert rows[1]["approach"] == "Market approach - EV/EBITDA"
    assert rows[1]["role"] == "Reasonableness cross-check"
    assert "participant-specific context" in rows[1]["rationale"]
    assert "buyer context" not in rows[1]["rationale"]
    assert rows[1]["report_treatment"] == "Cross-check range: 5.0x - 7.0x EV/EBITDA."
    assert rows[2]["approach"] == "Asset approach / net assets"
    assert rows[2]["role"] == "Not primary"
    assert "midpoint equity value is $2,249,000" in rows[2]["report_treatment"]


def test_valuation_reader_guidance_explains_trading_normalisations_wacc_dcf_multiples_sources_and_equity_bridge():
    sections = {
        "financial_performance": {
            "table": {
                "headers": ["Year ending March", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                "rows": [
                    ["Revenue", "$980,000", "$1,110,000", "$1,250,000", "$1,350,000"],
                    ["Less: direct costs / cost of sales", "($392,000)", "($427,400)", "($462,500)", "($499,500)"],
                    ["Gross profit", "$588,000", "$682,600", "$787,500", "$850,500"],
                    ["Less: operating expenses before EBITDA", "($423,000)", "($477,600)", "($547,500)", "($591,500)"],
                    ["Key expense breakdown - wages and salaries", "($240,000)", "($272,000)", "($310,000)", "($335,000)"],
                    ["Key expense breakdown - rent and occupancy", "($84,000)", "($90,000)", "($96,000)", "($102,000)"],
                    ["Key expense breakdown - other operating expenses", "($54,000)", "($63,000)", "($81,500)", "($89,500)"],
                    ["EBITDA", "$165,000", "$205,000", "$240,000", "$259,000"],
                    ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                ],
            },
        },
        "financial_ratio_analysis": {
            "table": {
                "headers": ["Ratio", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                "rows": [
                    ["Revenue growth", "Not available", "13.3%", "12.6%", "8.0%"],
                    ["Gross margin", "60.0%", "61.5%", "63.0%", "63.0%"],
                    ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                    ["Net profit margin", "10.7%", "11.5%", "12.0%", "12.1%"],
                ],
            },
        },
        "normalisations_schedule": {
            "table": {
                "headers": ["Adjustment", "Amount", "Rationale"],
                "rows": [
                    ["Owner remuneration above market", "$35,000", "Replace with an arm's-length management cost"],
                    ["One-off legal costs", "$12,000", "Non-recurring legal expenditure"],
                    ["Normalised FY25 EBITDA", "$287,000", "Reported EBITDA plus confirmed adjustments"],
                ],
            },
        },
        "valuation_assumptions": {
            "table": {
                "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
                "rows": [
                    [
                        "Normalised EBITDA",
                        "$287,000",
                        "Uploaded financial statements plus management-confirmed earnings adjustments",
                        "Sets the maintainable earnings base for DCF and multiples cross-checks.",
                    ],
                    [
                        "Revenue and earnings growth",
                        "8.0%",
                        "Management outlook: modest growth",
                        "Sets the explicit forecast growth assumption.",
                    ],
                    [
                        "Terminal growth",
                        "2.5%",
                        "Public research: New Zealand inflation input",
                        "Supports the terminal value assumption.",
                    ],
                    [
                        "WACC scenarios: high / mid / low valuation",
                        "9.9% / 11.5% / 13.4%",
                        "Public research: RBNZ risk-free rate and Damodaran ERP/beta",
                        "Discounts the forecast cash flows.",
                    ],
                    [
                        "Explicit forecast period",
                        "5 years",
                        "AccountIQ valuation model convention",
                        "Keeps the forecast horizon consistent across reports.",
                    ],
                    [
                        "Owner or key-person dependency",
                        "Responsibility is shared across leadership and team",
                        "Management-confirmed private input",
                        "Informs specific risk commentary.",
                    ],
                    [
                        "Largest-customer concentration",
                        "10% to 25%",
                        "Management-confirmed private input",
                        "Highlights concentration risk that is not usually visible online.",
                    ],
                    [
                        "Revenue predictability",
                        "A mix of recurring and one-off revenue",
                        "Management-confirmed private input",
                        "Distinguishes contracted revenue from transactional or project income.",
                    ],
                    [
                        "Revenue outlook",
                        "Modest growth",
                        "Management-confirmed private input",
                        "Documents the short-term outlook used to support the growth assumption.",
                    ],
                ],
            },
        },
        "wacc_assumptions": {
            "table": {
                "headers": ["Component", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [
                    ["WACC", "9.9%", "11.5%", "13.4%"],
                    ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                ],
            },
        },
        "dcf_analysis": {
            "table": {
                "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
                "rows": [
                    ["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"],
                ],
            },
            "cash_flow_schedule": {
                "headers": ["Mid-case forecast", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
                "rows": [
                    ["Revenue", "$1,350,000", "$1,458,000", "$1,574,640", "$1,700,611", "$1,836,660"],
                    ["Free cash flow to firm", "$198,731", "$214,630", "$231,800", "$250,344", "$270,372"],
                ],
            },
        },
        "valuation_summary": {
            "table": {
                "headers": ["Method / scenario", "Input", "Enterprise value", "Adjusted EV", "Equity value"],
                "rows": [
                    ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
                    ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
                    ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
                    ["Multiples - low", "5.0x EBITDA", "$1,435,000", "$1,435,000", "$1,370,000"],
                    ["Multiples - midpoint", "6.0x EBITDA", "$1,722,000", "$1,722,000", "$1,657,000"],
                    ["Multiples - high", "7.0x EBITDA", "$2,009,000", "$2,009,000", "$1,944,000"],
                ],
            },
        },
        "sensitivity_and_risks": {
            "table": {
                "headers": [
                    "Growth assumption",
                    "High valuation / 9.9% WACC",
                    "Mid valuation / 11.5% WACC",
                    "Low valuation / 13.4% WACC",
                ],
                "rows": [
                    ["6.0%", "$2,621,000", "$2,147,000", "$1,765,000"],
                    ["8.0% - base", "$2,831,000", "$2,314,000", "$1,898,000"],
                    ["10.0%", "$3,054,000", "$2,492,000", "$2,040,000"],
                ],
            },
            "specific_risk_factors": {
                "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
                "rows": [
                    ["Owner or key-person transition", "Shared", "Transition risk", "Confirm handover depth"],
                    ["Customer concentration", "10% to 25%", "Retention risk", "Review top customers"],
                    ["Revenue predictability", "Mixed", "Cash-flow certainty", "Review recurring revenue"],
                    ["Revenue outlook and pipeline", "Modest growth", "Forecast support", "Confirm pipeline"],
                    ["Other private context", "Key contract renewal", "Private risk", "Reflect in diligence"],
                ],
            },
        },
        "comparable_evidence": {
            "table": {
                "headers": ["Evidence", "Date", "Metric / multiple", "Relevance and limitation", "Source"],
                "rows": [
                    [
                        "Business services sector dataset",
                        "Current dataset",
                        "EV/EBITDA benchmark",
                        "Broad listed-company evidence; larger and more liquid than the subject",
                        "Damodaran Online - https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                    ],
                    [
                        "NZ private-company valuation context",
                        "Valuation date",
                        "Risk-free and inflation inputs",
                        "Supports discount-rate inputs, not a transaction multiple",
                        "Reserve Bank of New Zealand - https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                    ],
                    [
                        "Subject company public profile",
                        "Valuation date",
                        "Operating and market context",
                        "Public profile information retained for company-fact corroboration",
                        "NZ Companies Office - https://companies-register.companiesoffice.govt.nz/",
                    ],
                ],
            },
        },
        "multiples_crosscheck": {
            "table": {
                "headers": ["Input", "Low", "Mid", "High"],
                "rows": [
                    ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                    ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                    ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
                ],
            },
        },
        "sources": {
            "table": {
                "headers": ["Source", "URL", "Supports / used for"],
                "rows": [
                    [
                        "Reserve Bank of New Zealand",
                        "https://www.rbnz.govt.nz/statistics",
                        "Risk-free-rate and discount-rate context",
                    ],
                    [
                        "RBNZ inflation",
                        "https://www.rbnz.govt.nz/inflation",
                        "Long-term inflation and terminal-growth context",
                    ],
                    [
                        "Companies Office",
                        "https://companies-register.companiesoffice.govt.nz",
                        "Company public-profile corroboration",
                    ],
                ],
            },
        },
        "balance_sheet_summary": {
            "table": {
                "headers": ["Balance sheet item", "Value"],
                "rows": [
                    ["Total current assets", "$370,000"],
                    ["Accounts receivable / trade debtors", "$210,000"],
                    ["Inventory / stock", "$65,000"],
                    ["Fixed assets (net)", "$185,000"],
                    ["Accounts payable / trade creditors", "$155,000"],
                    ["Short-term loans / current borrowings", "$60,000"],
                    ["Total current liabilities", "$260,000"],
                    ["Long-term loans / borrowings", "$100,000"],
                    ["Total assets", "$850,000"],
                    ["Total liabilities", "$420,000"],
                    ["Shareholders' equity / net assets", "$430,000"],
                    ["Net tangible operating assets (NTOA)", "$260,000"],
                    ["Midpoint enterprise value", "$2,314,000"],
                    ["Less: net debt", "($65,000)"],
                    ["Midpoint equity value", "$2,249,000"],
                ],
            },
        },
        "disclaimer": (
            "## Indicative purpose and reliance\n"
            "This report is indicative only and has been prepared solely for the stated valuation "
            "purpose. It does not constitute financial advice and should not be relied upon as a "
            "substitute for independent professional, legal, tax or accounting advice. No responsibility "
            "is accepted to any third party who obtains or relies on this report.\n\n"
            "## Information and valuation date\n"
            "The analysis relies on management-supplied information, extracted financial records and "
            "identified public sources. Those inputs have not been independently audited."
        ),
    }

    trading_title, trading_rows = valuation_reader_guidance(sections, "financial_performance")
    overview_title, overview_rows = valuation_reader_guidance(sections, "business_overview")
    market_title, market_rows = valuation_reader_guidance(sections, "market_position")
    methodology_title, methodology_rows = valuation_reader_guidance(sections, "valuation_methodology")
    ratio_title, ratio_rows = valuation_reader_guidance(sections, "financial_ratio_analysis")
    normalisations_title, normalisations_rows = valuation_reader_guidance(sections, "normalisations_schedule")
    assumptions_title, assumptions_rows = valuation_reader_guidance(sections, "valuation_assumptions")
    wacc_title, wacc_rows = valuation_reader_guidance(sections, "wacc_assumptions")
    dcf_title, dcf_rows = valuation_reader_guidance(sections, "dcf_analysis")
    valuation_summary_title, valuation_summary_rows = valuation_reader_guidance(sections, "valuation_summary")
    sensitivity_title, sensitivity_rows = valuation_reader_guidance(sections, "sensitivity_and_risks")
    multiples_title, multiples_rows = valuation_reader_guidance(sections, "multiples_crosscheck")
    comparable_title, comparable_rows = valuation_reader_guidance(sections, "comparable_evidence")
    sources_title, sources_rows = valuation_reader_guidance(sections, "sources")
    bridge_title, bridge_rows = valuation_reader_guidance(sections, "balance_sheet_summary")
    disclaimer_title, disclaimer_rows = valuation_reader_guidance(sections, "disclaimer")

    assert trading_title == "Trading performance at a glance"
    assert (
        "Revenue bridge",
        "$980,000 to $1,350,000",
        "Top-line progression across the historical and forecast period shown in the report.",
    ) in trading_rows
    assert (
        "Direct-cost bridge",
        "($392,000) to ($499,500)",
        "Shows the cost-of-sales deduction used to move from revenue to gross profit.",
    ) in trading_rows
    assert (
        "Gross profit bridge",
        "$588,000 to $850,500",
        "Shows the trading margin available before overheads and other operating expenses.",
    ) in trading_rows
    assert (
        "Operating expense bridge",
        "($423,000) to ($591,500)",
        "Shows the overhead deduction used to reconcile gross profit to EBITDA.",
    ) in trading_rows
    assert (
        "Wages and salaries",
        "($240,000) to ($335,000)",
        "Highlights the main people-cost component inside operating expenses.",
    ) in trading_rows
    assert (
        "Rent and occupancy",
        "($84,000) to ($102,000)",
        "Highlights the main premises or occupancy cost inside operating expenses.",
    ) in trading_rows
    assert (
        "Other operating expenses",
        "($54,000) to ($89,500)",
        "Residual or other material overheads shown so EBITDA is easier to trace.",
    ) in trading_rows
    assert (
        "EBITDA bridge",
        "$165,000 to $259,000",
        "Operating earnings progression before the normalisation schedule is applied.",
    ) in trading_rows
    assert (
        "Latest actual EBITDA",
        "$240,000",
        "Latest actual earnings reference point before forecast and valuation adjustments.",
    ) in trading_rows
    assert overview_title == "Business context at a glance"
    assert (
        "Owner or key-person dependency",
        "Responsibility is shared across leadership and team",
        "Management-supplied context used to frame transition and key-person risk.",
    ) in overview_rows
    assert (
        "Customer concentration",
        "10% to 25%",
        "Management-supplied context highlighting whether revenue is exposed to large customers.",
    ) in overview_rows
    assert (
        "Revenue predictability",
        "A mix of recurring and one-off revenue",
        "Management-supplied context distinguishing recurring, mixed and project-based revenue.",
    ) in overview_rows
    assert (
        "Revenue outlook",
        "Modest growth",
        "Management-supplied context used to support or derive the short-term growth assumption.",
    ) in overview_rows
    assert market_title == "Market context at a glance"
    assert (
        "Public sources retained",
        "6",
        "Source URLs are retained for market, profile and benchmark context.",
    ) in market_rows
    assert (
        "Benchmark evidence",
        "Public evidence supports sector or EV/EBITDA context",
        "Explains whether public evidence supports market or EV/EBITDA context.",
    ) in market_rows
    assert (
        "Public profile support",
        "Public sources support the company profile or operating context",
        "Explains whether public sources support company-profile or operating-context statements.",
    ) in market_rows
    assert (
        "Comparability caveat",
        "Limitations explain the evidence is contextual, not direct pricing",
        "Explains that public evidence is used for context and cross-checking, not a direct price.",
    ) in market_rows
    assert methodology_title == "Methodology at a glance"
    assert (
        "Primary valuation method",
        "Discounted cash flow",
        "Forecast free cash flows are the primary valuation basis.",
    ) in methodology_rows
    assert (
        "Discount-rate range",
        "9.9% - 13.4%",
        "High, midpoint and low WACC scenarios create the valuation range.",
    ) in methodology_rows
    assert (
        "Market cross-check",
        "5.0x - 7.0x EV/EBITDA",
        "Researched market multiples are used as a reasonableness check.",
    ) in methodology_rows
    assert (
        "Equity bridge",
        "$2,249,000",
        "Enterprise value is bridged to shareholder value using debt, cash and surplus assets.",
    ) in methodology_rows
    assert ratio_title == "Margin and growth at a glance"
    assert (
        "Latest revenue growth",
        "8.0%",
        "Latest growth rate shown in the uploaded-financials trend table.",
    ) in ratio_rows
    assert (
        "Gross margin bridge",
        "60.0% to 63.0%",
        "Shows whether direct-cost efficiency is improving, stable or weakening.",
    ) in ratio_rows
    assert (
        "EBITDA margin bridge",
        "16.8% to 19.2%",
        "Summarises operating leverage before valuation adjustments.",
    ) in ratio_rows
    assert normalisations_title == "Normalisation impact at a glance"
    assert (
        "Confirmed adjustments",
        "2",
        "Management-reviewed normalisation items included in the maintainable earnings bridge.",
    ) in normalisations_rows
    assert (
        "Net EBITDA adjustment",
        "$47,000",
        "Net add-back or deduction applied before the valuation earnings base.",
    ) in normalisations_rows
    assert (
        "Largest adjustment",
        "Owner remuneration above market - $35,000",
        "Largest individual normalisation item for adviser or management review.",
    ) in normalisations_rows
    assert (
        "Normalised EBITDA",
        "$287,000",
        "Maintainable earnings base used in the valuation analysis.",
    ) in normalisations_rows
    assert assumptions_title == "Assumption basis at a glance"
    assert (
        "Maintainable earnings base",
        "$287,000",
        "Normalised EBITDA used as the valuation earnings base.",
    ) in assumptions_rows
    assert (
        "Growth assumption",
        "8.0%",
        "Forecast growth assumption disclosed with its source.",
    ) in assumptions_rows
    assert (
        "Public research inputs",
        "2",
        "Assumptions supported by public market, inflation or discount-rate evidence.",
    ) in assumptions_rows
    assert (
        "Management-confirmed inputs",
        "5",
        "Management-supplied private inputs used for business-specific assumptions.",
    ) in assumptions_rows
    assert (
        "Technical model inputs",
        "1",
        "Valuation-model conventions disclosed with the assumption basis.",
    ) in assumptions_rows
    assert wacc_title == "How the discount rate drives the range"
    assert (
        "High valuation discount rate",
        "9.9%",
        "Lower WACC means forecast cash flows are discounted less heavily, producing the upper valuation case.",
    ) in wacc_rows
    assert (
        "Illiquidity discount",
        "11.8%",
        "Private-company marketability discount shown explicitly rather than hidden in the conclusion.",
    ) in wacc_rows
    assert dcf_title == "DCF forecast bridge at a glance"
    assert (
        "Adjusted enterprise value range",
        "$1,898,000 - $2,831,000",
        "DCF valuation range after the private-company illiquidity adjustment.",
    ) in dcf_rows
    assert (
        "Revenue forecast bridge",
        "$1,350,000 to $1,836,660",
        "Mid-case revenue progression across the explicit five-year forecast period.",
    ) in dcf_rows
    assert (
        "Free cash flow bridge",
        "$198,731 to $270,372",
        "Mid-case free cash flow to firm after tax, capex and working-capital reinvestment.",
    ) in dcf_rows
    assert valuation_summary_title == "Valuation range at a glance"
    assert (
        "Primary DCF range",
        "$1,898,000 - $2,831,000",
        "Primary enterprise-value range after the private-company illiquidity adjustment.",
    ) in valuation_summary_rows
    assert (
        "Midpoint equity value",
        "$2,249,000",
        "Central shareholder-value indication after the net-debt bridge.",
    ) in valuation_summary_rows
    assert (
        "Market cross-check range",
        "$1,370,000 - $1,944,000",
        "Market multiples provide an independent reasonableness check, not the selected conclusion.",
    ) in valuation_summary_rows
    assert (
        "DCF vs multiple midpoint",
        "$592,000 above",
        "Shows where the primary DCF midpoint sits relative to the market cross-check midpoint.",
    ) in valuation_summary_rows
    assert sensitivity_title == "Sensitivity takeaway at a glance"
    assert (
        "Base sensitivity case",
        "$2,314,000",
        "Midpoint case using the base growth assumption and mid WACC scenario.",
    ) in sensitivity_rows
    assert (
        "Quantified EV span",
        "$1,765,000 - $3,054,000",
        "Full adjusted enterprise-value span across the WACC and growth matrix.",
    ) in sensitivity_rows
    assert (
        "Growth cases tested",
        "6.0% to 10.0%",
        "Growth sensitivity range tested without asking management for extra valuation inputs.",
    ) in sensitivity_rows
    assert (
        "Specific risk factors",
        "5",
        "Qualitative risk factors carried into the report from the short management intake.",
    ) in sensitivity_rows
    assert comparable_title == "Comparable evidence at a glance"
    assert (
        "Evidence rows",
        "3",
        "Public benchmark and context rows retained in the comparable evidence appendix.",
    ) in comparable_rows
    assert (
        "Source URLs retained",
        "3",
        "Every evidence row should retain a URL so the reader can check the source trail.",
    ) in comparable_rows
    assert (
        "Market multiple support",
        "Market evidence supports the EV/EBITDA cross-check",
        "Explains whether researched public evidence supports the EV/EBITDA cross-check range.",
    ) in comparable_rows
    assert (
        "Comparability caveat",
        "Limitations explained as a reasonableness check",
        "Explains that public evidence is used for context and cross-checking, not as a direct private-company price.",
    ) in comparable_rows
    assert multiples_title == "How the market cross-check is used"
    assert (
        "Market multiple range",
        "5.0x - 7.0x",
        "Indicative EV/EBITDA range from researched comparable evidence.",
    ) in multiples_rows
    assert (
        "Implied enterprise value range",
        "$1,435,000 - $2,009,000",
        "Reasonableness range used to cross-check, not replace, the primary DCF conclusion.",
    ) in multiples_rows
    assert sources_title == "Source trail at a glance"
    assert (
        "Public URLs retained",
        "3",
        "Source links are retained so a reader can inspect the public evidence trail.",
    ) in sources_rows
    assert (
        "Discount-rate support",
        "Public sources retained for WACC inputs",
        "Explains whether public evidence supports the risk-free-rate, equity-risk-premium or beta inputs.",
    ) in sources_rows
    assert (
        "Terminal-growth support",
        "Inflation source retained for terminal growth",
        "Explains whether public evidence supports inflation or long-term growth assumptions.",
    ) in sources_rows
    assert (
        "Business context support",
        "Public profile sources retained for business context",
        "Explains whether public sources support company-profile or market-context statements.",
    ) in sources_rows
    assert disclaimer_title == "Reliance at a glance"
    assert (
        "Intended use",
        "Stated purpose only",
        "Reliance is limited to the valuation purpose stated in the report.",
    ) in disclaimer_rows
    assert (
        "Advice status",
        "Not advice",
        "The report is not a substitute for independent professional advice.",
    ) in disclaimer_rows
    assert (
        "Verification status",
        "Not audited",
        "The scope is an indicative valuation pack, not an audit or assurance engagement.",
    ) in disclaimer_rows
    assert (
        "Third-party reliance",
        "No responsibility accepted",
        "Third parties should not rely on the report without their own advice and diligence.",
    ) in disclaimer_rows
    assert bridge_title == "Enterprise-to-equity bridge"
    assert (
        "Operating asset detail",
        "$210,000 receivables, $65,000 stock and $185,000 fixed assets",
        "Shows the main operating asset items supporting the NTOA position.",
    ) in bridge_rows
    assert (
        "Operating liability detail",
        "$155,000",
        "Shows the main operating payable deducted in the NTOA position.",
    ) in bridge_rows
    assert (
        "Loan detail",
        "$60,000 current loans and $100,000 long-term loans",
        "Shows borrowings separately from operating assets and liabilities.",
    ) in bridge_rows
    assert (
        "NTOA position",
        "$260,000",
        "Net tangible operating assets before cash, interest-bearing debt and surplus assets.",
    ) in bridge_rows
    assert (
        "Net debt bridge",
        "($65,000)",
        "Debt exceeds cash by this amount, reducing the value attributable to shareholders.",
    ) in bridge_rows
    assert (
        "Midpoint equity value",
        "$2,249,000",
        "Central shareholder-value indication after the bridge from enterprise value.",
    ) in bridge_rows


def test_valuation_basis_of_preparation_documents_private_inputs_and_model_basis():
    basis = valuation_basis_of_preparation(
        demo_mode=False,
        valuation_purpose="Prepare for a sale or transaction",
        generated_at="2026-07-04 09:15:00",
        intake_answers={
            "valuation_purpose": "sale_or_transaction",
            "owner_dependency": "shared",
            "customer_concentration": "10_to_25",
            "revenue_quality": "mixed",
            "revenue_outlook": "not_sure",
        },
    )
    report_letter = basis["report_letter"]
    report_letter_text = " ".join(
        " ".join(row) for row in report_letter["table"]["rows"]
    )
    scope_text = " ".join(" ".join(row) for row in basis["scope_table"]["rows"])
    management_rows_text = " ".join(" ".join(row) for row in basis["management_input_table"]["rows"])
    rows_text = " ".join(" ".join(row) for row in basis["table"]["rows"])

    assert report_letter["title"] == "Report letter"
    assert "professional valuation report pack" in report_letter["narrative"]
    assert "without requiring the owner to complete a long technical valuation questionnaire" in report_letter["narrative"]
    assert "Prepared for The business reviewed" in report_letter_text
    assert "Prepared by AccountIQ valuation team" in report_letter_text
    assert "Preparer role Valuation report preparation and evidence synthesis" in report_letter_text
    assert "Organisation AccountIQ" in report_letter_text
    assert "Report channel Secure AccountIQ workspace and downloadable PDF" in report_letter_text
    assert "Report type Indicative Valuation Report" in report_letter_text
    assert "Purpose and reliance Prepare for a sale or transaction" in report_letter_text
    assert "Information relied upon Uploaded financial statements, five management-confirmed private inputs" in report_letter_text
    assert "Important limitation This is an indicative valuation report only and is not an audit or assurance engagement" in report_letter_text
    assert basis["management_input_table"]["headers"] == [
        "Management input",
        "Basis",
        "How it informs the report",
    ]
    assert "Technical assumptions such as discount rate" in basis["narrative"]
    assert "derived and disclosed rather than selected by management" in basis["narrative"]
    assert "requiring broad technical valuation inputs from the owner" not in basis["narrative"]
    assert "long expert questionnaire" not in basis["narrative"]
    assert "AccountIQ valuation calculations" in basis["narrative"]
    assert "model-computed" not in basis["narrative"]
    assert "Python-computed" not in basis["narrative"]
    assert "Valuation purpose Prepare for a sale or transaction" in scope_text
    assert "Valuation date 4 July 2026" in scope_text
    assert "Indicative fair-market value" in scope_text
    assert "Information basis" in scope_text
    assert "uploaded financial statements" in scope_text
    assert "earnings-adjustment review" in scope_text
    assert "public-source research" in scope_text
    assert "Scope exclusions" in scope_text
    assert "audit, assurance engagement, legal advice, tax advice" in scope_text
    assert "Five management-confirmed private inputs" in rows_text
    assert "Management input - Valuation purpose" not in rows_text
    assert management_rows_text.count("Management-confirmed private input") == 5
    assert "Management input - Valuation purpose" in management_rows_text
    assert "Prepare for a sale or transaction" in management_rows_text
    assert "Management input - Owner or key-person dependency" in management_rows_text
    assert "Responsibility is shared across leadership and team" in management_rows_text
    assert "Management input - Largest-customer concentration" in management_rows_text
    assert "10% to 25%" in management_rows_text
    assert "Management input - Revenue predictability" in management_rows_text
    assert "A mix of recurring and one-off revenue" in management_rows_text
    assert "Management input - Revenue outlook" in management_rows_text
    assert "No specific forecast provided; growth derived from uploaded financial history" in management_rows_text
    assert "when no specific forecast is supplied" in management_rows_text
    assert "Earnings-adjustment review" in rows_text
    assert "Optional public-source hints" in rows_text
    assert "not required from management" in rows_text
    assert "AccountIQ calculates the DCF valuation" in rows_text
    assert "discount-rate scenarios" in rows_text
    assert "Derived technical assumptions" in rows_text
    assert "Discount rate, terminal growth and forecast horizon" in rows_text
    assert "rather than selected by management" in rows_text
    assert "Questions intentionally not asked" in rows_text
    assert "not asked to choose the forecast horizon, WACC, terminal growth or discount-rate scenarios" in rows_text
    assert "Public research and source trail" in rows_text
    assert "Research hints provided" not in rows_text


def test_valuation_basis_of_preparation_summarises_optional_research_hints():
    basis = valuation_basis_of_preparation(
        demo_mode=False,
        intake_answers={
            "company_website": "https://example.co.nz",
            "company_location": "Auckland, New Zealand",
            "public_source_urls": [
                "https://example.co.nz/about",
                "https://companies-register.companiesoffice.govt.nz/example",
                "https://www.linkedin.com/company/example",
                "https://example.co.nz/news",
            ],
            "private_context": "A key contract renews next year.",
        },
    )
    rows_text = " ".join(" ".join(row) for row in basis["table"]["rows"])

    assert "Research hints provided" in rows_text
    assert "Website: https://example.co.nz" in rows_text
    assert "Location: Auckland, New Zealand" in rows_text
    assert "Public links: https://example.co.nz/about" in rows_text
    assert "plus 1 more" in rows_text
    assert "Private valuation context: A key contract renews next year." in rows_text


def test_valuation_basis_of_preparation_labels_demo_research():
    basis = valuation_basis_of_preparation(demo_mode=True)
    rows_text = " ".join(" ".join(row) for row in basis["table"]["rows"])

    assert "Simulated public research" in rows_text
    assert "Public research and source trail" not in rows_text


def test_valuation_basis_of_preparation_uses_report_identity_in_letter():
    basis = valuation_basis_of_preparation(
        company_name="Identity Limited",
        report_label="Demo Indicative Valuation Report",
        report_id=77,
        valuation_purpose="Finance or investment discussions",
    )
    report_letter_text = " ".join(
        " ".join(row) for row in basis["report_letter"]["table"]["rows"]
    )

    assert "Prepared for Identity Limited" in report_letter_text
    assert "Report type Demo Indicative Valuation Report" in report_letter_text
    assert "Reference AIQ-VAL-000077" in report_letter_text
    assert "Purpose and reliance Finance or investment discussions" in report_letter_text


def test_pdf_cover_includes_professional_report_brief(tmp_path):
    output_path = tmp_path / "cover-brief.pdf"

    write_report_pdf(
        output_path,
        company_name="Cover Brief Limited",
        report_label="Indicative Valuation Report",
        report_type="valuation_advisory",
        valuation_purpose="Prepare for a sale or transaction",
        sections={
            "introduction": "This report introduces the valuation scope and basis."
        },
        section_order=["introduction"],
        section_titles={"introduction": "Introduction"},
        report_id=42,
        generated_at="2026-07-04 09:15:00",
        demo_mode=False,
    )

    with pdfplumber.open(output_path) as pdf:
        first_page_text = " ".join((pdf.pages[0].extract_text() or "").split())

    assert "PREPARED FOR Cover Brief Limited" in first_page_text
    assert "PREPARED BY AccountIQ" in first_page_text
    assert "REPORT TYPE Indicative Valuation Report" in first_page_text
    assert "REFERENCE AIQ-VAL-000042" in first_page_text
    assert "VALUATION DATE 4 July 2026" in first_page_text
    assert "PURPOSE Prepare for a sale or transaction" in first_page_text
    assert "BASIS OF VALUE Indicative fair-market" in first_page_text
    assert "going-concern" in first_page_text
    assert "RELIANCE Indicative valuation support only" in first_page_text
    assert "REPORT BASIS" in first_page_text
    assert "Uploaded financials" in first_page_text
    assert "Five private inputs" in first_page_text
    assert "Public-source trail" in first_page_text
    assert "AccountIQ model" in first_page_text


def test_bank_credit_pdf_cover_uses_credit_paper_language_not_valuation_language(tmp_path):
    output_path = tmp_path / "bank-credit-cover.pdf"

    write_report_pdf(
        output_path,
        company_name="Credit Borrower Limited",
        report_label="Bank Credit Paper",
        report_type="bank_credit_paper",
        valuation_purpose="",
        sections={
            "executive_summary": {
                "narrative": "The credit paper summarises the requested facility and lender view.",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Requested debt", "$1,000,000"]],
                },
            }
        },
        section_order=["executive_summary"],
        section_titles={"executive_summary": "Executive Summary"},
        report_id=55,
        generated_at="2026-07-04 09:15:00",
        demo_mode=True,
    )

    with pdfplumber.open(output_path) as pdf:
        first_page_text = " ".join((pdf.pages[0].extract_text() or "").split())

    assert "REPORT TYPE Bank Credit Paper" in first_page_text
    assert "REFERENCE AIQ-REP-000055" in first_page_text
    assert "PREPARED DATE 4 July 2026" in first_page_text
    assert "PURPOSE Credit paper / lender screening" in first_page_text
    assert "CREDIT POSTURE Screening-only" in first_page_text
    assert "diligence and bank" in first_page_text
    assert "approval" in first_page_text
    assert "Lender inputs" in first_page_text
    assert "Debt-capacity model" in first_page_text
    assert "VALUATION DATE" not in first_page_text
    assert "BASIS OF VALUE" not in first_page_text
    assert "DCF, WACC, multiples" not in first_page_text


def test_bank_credit_pdf_body_does_not_render_valuation_reader_guidance(tmp_path):
    output_path = tmp_path / "bank-credit-body.pdf"

    write_report_pdf(
        output_path,
        company_name="Credit Borrower Limited",
        report_label="Bank Credit Paper",
        report_type="bank_credit_paper",
        valuation_purpose="",
        sections={
            "executive_summary": {
                "narrative": "The credit paper summarises the requested facility and lender view.",
                "table": {
                    "headers": ["Credit item", "Position", "Underwriting comment"],
                    "rows": [["Requested facility", "$1,000,000", "Indicative lender screen"]],
                },
            },
            "disclaimer": "This credit paper is indicative only and is not a bank approval or commitment.",
        },
        section_order=["executive_summary", "disclaimer"],
        section_titles={
            "executive_summary": "Executive Summary",
            "disclaimer": "Disclaimer",
        },
        report_id=56,
        generated_at="2026-07-04 09:15:00",
        demo_mode=True,
    )

    with pdfplumber.open(output_path) as pdf:
        document_text = " ".join(
            " ".join((page.extract_text() or "").split()) for page in pdf.pages
        )

    assert "ACCOUNTIQ BANK CREDIT PAPER" in document_text
    assert "This credit paper is indicative only" in document_text
    assert "Reliance at a glance" not in document_text
    assert "Valuation conclusion at a glance" not in document_text
    assert "valuation purpose" not in document_text.lower()
    assert "indicative valuation pack" not in document_text.lower()


def test_pdf_body_pages_repeat_report_reference_code(tmp_path):
    output_path = tmp_path / "body-reference.pdf"

    write_report_pdf(
        output_path,
        company_name="Reference Footer Limited",
        report_label="Indicative Valuation Report",
        report_type="valuation_advisory",
        valuation_purpose="Prepare for a sale or transaction",
        sections={
            "introduction": "This report introduces the valuation scope and basis.",
            "executive_summary": "The report summarises the valuation conclusion.",
        },
        section_order=["introduction", "executive_summary"],
        section_titles={
            "introduction": "Introduction",
            "executive_summary": "Executive Summary",
        },
        report_id=42,
        generated_at="2026-07-04 09:15:00",
        demo_mode=False,
    )

    with pdfplumber.open(output_path) as pdf:
        body_text = "\n".join(page.extract_text() or "" for page in pdf.pages[1:])

    assert "AccountIQ | AIQ-VAL-000042" in body_text


def test_pdf_basis_page_includes_optional_research_hints(tmp_path):
    output_path = tmp_path / "research-hints.pdf"

    write_report_pdf(
        output_path,
        company_name="Research Hints Limited",
        report_label="Indicative Valuation Report",
        report_type="valuation_advisory",
        valuation_purpose="Understand what the business may be worth",
        intake_answers={
            "company_website": "https://example.co.nz",
            "company_location": "Auckland, New Zealand",
            "public_source_urls": ["https://www.linkedin.com/company/example"],
            "private_context": "A key contract renews next year.",
        },
        sections={
            "introduction": (
                "## Client and report purpose\n"
                "This report introduces the valuation scope and basis for the reader."
            )
        },
        section_order=["introduction"],
        section_titles={"introduction": "Introduction"},
        report_id=77,
        generated_at="2026-07-04 09:15:00",
    )

    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    normalised_text = " ".join(text.split())

    assert "Research hints provided" in normalised_text
    assert "Website: https://example.co.nz" in normalised_text
    assert "Location: Auckland, New Zealand" in normalised_text
    assert "Public links: https://www.linkedin.com/company/example" in normalised_text
    assert "Private valuation context: A key contract renews next year." in normalised_text


def test_pdf_basis_page_renders_five_answer_management_trail_before_report_body(tmp_path):
    output_path = tmp_path / "basis-management-input-trail.pdf"

    write_report_pdf(
        output_path,
        company_name="Management Trail Limited",
        report_label="Indicative Valuation Report",
        report_type="valuation_advisory",
        valuation_purpose="Prepare for a sale or transaction",
        intake_answers={
            "valuation_purpose": "sale_or_transaction",
            "owner_dependency": "shared",
            "customer_concentration": "10_to_25",
            "revenue_quality": "mixed",
            "revenue_outlook": "not_sure",
        },
        sections={
            "introduction": {
                "narrative": "This report introduces the valuation scope and basis."
            }
        },
        section_order=["introduction"],
        section_titles={"introduction": "Introduction"},
        report_id=44,
        generated_at="2026-07-04 09:15:00",
    )

    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    normalised_text = " ".join(text.split())

    report_letter_index = normalised_text.index("Report letter")
    scope_exclusions_index = normalised_text.index("Scope exclusions")
    management_trail_index = normalised_text.index("Management input trail")
    evidence_basis_index = normalised_text.index("Evidence and model basis")
    introduction_index = normalised_text.rindex("01 Introduction")

    assert report_letter_index < scope_exclusions_index < management_trail_index
    assert management_trail_index < evidence_basis_index < introduction_index
    assert "Prepared for Management Trail Limited" in normalised_text
    assert "Prepared by AccountIQ valuation team" in normalised_text
    assert "Preparer role Valuation report preparation and evidence synthesis" in normalised_text
    assert "Report channel Secure AccountIQ workspace and downloadable PDF" in normalised_text
    assert "Purpose and reliance Prepare for a sale or transaction" in normalised_text
    assert "Important limitation This is an indicative valuation report only and is not an audit or assurance engagement" in normalised_text
    assert normalised_text.count("Management-confirmed private input") >= 5
    assert "Management input - Valuation purpose" in normalised_text
    assert "Management input - Owner or key-person" in normalised_text
    assert "Informs continuity, handover risk, transition risk and specific-risk commentary" in normalised_text
    assert "Management input - Largest-customer" in normalised_text
    assert "10% to 25%" in normalised_text
    assert "Management input - Revenue predictability" in normalised_text
    assert "Management input - Revenue outlook" in normalised_text


def test_pdf_includes_reader_guidance_for_valuation_mechanics(tmp_path):
    output_path = tmp_path / "reader-guidance.pdf"

    write_report_pdf(
        output_path,
        company_name="Reader Guidance Limited",
        report_label="Indicative Valuation Report",
        report_type="valuation_advisory",
        sections={
            "business_overview": {
                "narrative": "The business context combines public research with management-confirmed private inputs.",
            },
            "market_position": {
                "narrative": "Public market evidence is cross-checked against company operating context.",
            },
            "valuation_methodology": {
                "narrative": (
                    "Discounted cash flow is the primary method. Researched EV/EBITDA evidence "
                    "provides an independent reasonableness cross-check."
                ),
            },
            "financial_performance": {
                "narrative": "Revenue and EBITDA have grown over the observed period.",
                "table": {
                    "headers": ["Year ending March", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                    "rows": [
                        ["Revenue", "$980,000", "$1,110,000", "$1,250,000", "$1,350,000"],
                        ["Less: direct costs / cost of sales", "($392,000)", "($427,400)", "($462,500)", "($499,500)"],
                        ["Gross profit", "$588,000", "$682,600", "$787,500", "$850,500"],
                        ["Less: operating expenses before EBITDA", "($423,000)", "($477,600)", "($547,500)", "($591,500)"],
                        ["Key expense breakdown - wages and salaries", "($240,000)", "($272,000)", "($310,000)", "($335,000)"],
                        ["Key expense breakdown - rent and occupancy", "($84,000)", "($90,000)", "($96,000)", "($102,000)"],
                        ["Key expense breakdown - other operating expenses", "($54,000)", "($63,000)", "($81,500)", "($89,500)"],
                        ["EBITDA", "$165,000", "$205,000", "$240,000", "$259,000"],
                        ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                    ],
                },
            },
            "financial_ratio_analysis": {
                "narrative": "Historical ratios show improving scale and operating leverage.",
                "table": {
                    "headers": ["Ratio", "FY23 Actual", "FY24 Actual", "FY25 Actual", "FY26 Forecast"],
                    "rows": [
                        ["Revenue growth", "Not available", "13.3%", "12.6%", "8.0%"],
                        ["Gross margin", "60.0%", "61.5%", "63.0%", "63.0%"],
                        ["EBITDA margin", "16.8%", "18.5%", "19.2%", "19.2%"],
                        ["Net profit margin", "10.7%", "11.5%", "12.0%", "12.1%"],
                    ],
                },
            },
            "normalisations_schedule": {
                "narrative": "Normalisations isolate maintainable operating earnings.",
                "table": {
                    "headers": ["Adjustment", "Amount", "Rationale"],
                    "rows": [
                        ["Owner remuneration above market", "$35,000", "Replace with an arm's-length management cost"],
                        ["One-off legal costs", "$12,000", "Non-recurring legal expenditure"],
                        ["Normalised FY25 EBITDA", "$287,000", "Reported EBITDA plus confirmed adjustments"],
                    ],
                },
            },
            "valuation_assumptions": {
                "narrative": "The source trail distinguishes uploaded, management-confirmed, public and model inputs.",
                "table": {
                    "headers": ["Assumption / input", "Value used", "Primary source", "Why it matters"],
                    "rows": [
                        [
                            "Normalised EBITDA",
                            "$287,000",
                            "Uploaded financial statements plus management-confirmed earnings adjustments",
                            "Sets the maintainable earnings base for DCF and multiples cross-checks.",
                        ],
                        [
                            "Revenue and earnings growth",
                            "8.0%",
                            "Management outlook: modest growth",
                            "Sets the explicit forecast growth assumption.",
                        ],
                        [
                            "Terminal growth",
                            "2.5%",
                            "Public research: New Zealand inflation input",
                            "Supports the terminal value assumption.",
                        ],
                        [
                            "WACC scenarios: high / mid / low valuation",
                            "9.9% / 11.5% / 13.4%",
                            "Public research: RBNZ risk-free rate and Damodaran ERP/beta",
                            "Discounts the forecast cash flows.",
                        ],
                        [
                            "Explicit forecast period",
                            "5 years",
                            "AccountIQ valuation model convention",
                            "Keeps the forecast horizon consistent across reports.",
                        ],
                        [
                            "Owner or key-person dependency",
                            "Responsibility is shared across leadership and team",
                            "Management-confirmed private input",
                            "Informs specific risk commentary.",
                        ],
                        [
                            "Largest-customer concentration",
                            "10% to 25%",
                            "Management-confirmed private input",
                            "Highlights concentration risk that is not usually visible online.",
                        ],
                        [
                            "Revenue predictability",
                            "A mix of recurring and one-off revenue",
                            "Management-confirmed private input",
                            "Distinguishes contracted revenue from transactional or project income.",
                        ],
                        [
                            "Revenue outlook",
                            "Modest growth",
                            "Management-confirmed private input",
                            "Documents the short-term outlook used to support the growth assumption.",
                        ],
                    ],
                },
            },
            "wacc_assumptions": {
                "narrative": "The high valuation uses the lowest WACC; the low valuation uses the highest WACC.",
                "table": {
                    "headers": ["Component", "High valuation", "Mid valuation", "Low valuation"],
                    "rows": [
                        ["WACC", "9.9%", "11.5%", "13.4%"],
                        ["Illiquidity discount", "11.8%", "11.8%", "11.8%"],
                    ],
                },
            },
            "balance_sheet_summary": {
                "narrative": "The bridge converts enterprise value to equity value.",
                "table": {
                    "headers": ["Balance sheet item", "Value"],
                    "rows": [
                        ["Accounts receivable / trade debtors", "$210,000"],
                        ["Inventory / stock", "$65,000"],
                        ["Total current assets", "$370,000"],
                        ["Accounts payable / trade creditors", "$155,000"],
                        ["Short-term loans / current borrowings", "$60,000"],
                        ["Total current liabilities", "$260,000"],
                        ["Long-term loans / borrowings", "$100,000"],
                        ["Total assets", "$850,000"],
                        ["Total liabilities", "$420,000"],
                        ["Shareholders' equity / net assets", "$430,000"],
                        ["Net tangible operating assets (NTOA)", "$260,000"],
                        ["Midpoint enterprise value", "$2,314,000"],
                        ["Less: net debt", "($65,000)"],
                        ["Midpoint equity value", "$2,249,000"],
                    ],
                },
            },
            "multiples_crosscheck": {
                "narrative": "The market range is used as a reasonableness cross-check.",
                "table": {
                    "headers": ["Input", "Low", "Mid", "High"],
                    "rows": [
                        ["EV/EBITDA multiple", "5.0x", "6.0x", "7.0x"],
                        ["Normalised EBITDA", "$287,000", "$287,000", "$287,000"],
                        ["Indicated enterprise value", "$1,435,000", "$1,722,000", "$2,009,000"],
                    ],
                },
            },
            "dcf_analysis": {
                "narrative": "DCF bridge explains the forecast free cash flows.",
                "table": {
                    "headers": ["DCF item", "High valuation", "Mid valuation", "Low valuation"],
                    "rows": [["Adjusted enterprise value", "$2,831,000", "$2,314,000", "$1,898,000"]],
                },
                "cash_flow_schedule": {
                    "headers": ["Mid-case forecast", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
                    "rows": [
                        ["Revenue", "$1,350,000", "$1,458,000", "$1,574,640", "$1,700,611", "$1,836,660"],
                        ["Free cash flow to firm", "$198,731", "$214,630", "$231,800", "$250,344", "$270,372"],
                    ],
                },
            },
            "valuation_summary": {
                "narrative": "The DCF range is cross-checked against researched market multiples.",
                "table": {
                    "headers": ["Method / scenario", "Input", "Enterprise value", "Adjusted EV", "Equity value"],
                    "rows": [
                        ["DCF - high valuation", "9.9% WACC", "$3,209,000", "$2,831,000", "$2,766,000"],
                        ["DCF - midpoint", "11.5% WACC", "$2,624,000", "$2,314,000", "$2,249,000"],
                        ["DCF - low valuation", "13.4% WACC", "$2,152,000", "$1,898,000", "$1,833,000"],
                        ["Multiples - low", "5.0x EBITDA", "$1,435,000", "$1,435,000", "$1,370,000"],
                        ["Multiples - midpoint", "6.0x EBITDA", "$1,722,000", "$1,722,000", "$1,657,000"],
                        ["Multiples - high", "7.0x EBITDA", "$2,009,000", "$2,009,000", "$1,944,000"],
                    ],
                },
            },
            "sensitivity_and_risks": {
                "narrative": "Sensitivity and qualitative risk are considered separately.",
                "table": {
                    "headers": [
                        "Growth assumption",
                        "High valuation / 9.9% WACC",
                        "Mid valuation / 11.5% WACC",
                        "Low valuation / 13.4% WACC",
                    ],
                    "rows": [
                        ["6.0%", "$2,621,000", "$2,147,000", "$1,765,000"],
                        ["8.0% - base", "$2,831,000", "$2,314,000", "$1,898,000"],
                        ["10.0%", "$3,054,000", "$2,492,000", "$2,040,000"],
                    ],
                },
                "specific_risk_factors": {
                    "headers": ["Specific risk factor", "Management input", "Valuation relevance", "Report treatment"],
                    "rows": [
                    ["Owner or key-person transition", "Shared", "Transition risk", "Confirm handover depth"],
                        ["Customer concentration", "10% to 25%", "Retention risk", "Review top customers"],
                        ["Revenue predictability", "Mixed", "Cash-flow certainty", "Review recurring revenue"],
                        ["Revenue outlook and pipeline", "Modest growth", "Forecast support", "Confirm pipeline"],
                        ["Other private context", "Key contract renewal", "Private risk", "Reflect in diligence"],
                    ],
                },
            },
            "comparable_evidence": {
                "narrative": "Comparable public evidence is retained as a reasonableness cross-check.",
                "table": {
                    "headers": ["Evidence", "Date", "Metric / multiple", "Relevance and limitation", "Source"],
                    "rows": [
                        [
                            "Business services sector dataset",
                            "Current dataset",
                            "EV/EBITDA benchmark",
                            "Broad listed-company evidence; larger and more liquid than the subject",
                            "Damodaran Online - https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
                        ],
                        [
                            "NZ private-company valuation context",
                            "Valuation date",
                            "Risk-free and inflation inputs",
                            "Supports discount-rate inputs, not a transaction multiple",
                            "Reserve Bank of New Zealand - https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates",
                        ],
                    [
                        "Subject company public profile",
                        "Valuation date",
                        "Operating and market context",
                        "Public profile information retained for company-fact corroboration",
                        "NZ Companies Office - https://companies-register.companiesoffice.govt.nz/",
                    ],
                    ],
                },
            },
            "sources": {
                "narrative": "Sources support the valuation assumptions.",
                "table": {
                    "headers": ["Source", "URL", "Supports / used for"],
                    "rows": [
                        [
                            "Reserve Bank of New Zealand",
                            "https://www.rbnz.govt.nz/statistics",
                            "Risk-free-rate and discount-rate context",
                        ],
                        [
                            "RBNZ inflation",
                            "https://www.rbnz.govt.nz/inflation",
                            "Long-term inflation and terminal-growth context",
                        ],
                        [
                            "Companies Office",
                            "https://companies-register.companiesoffice.govt.nz",
                            "Company public-profile corroboration",
                        ],
                    ],
                },
            },
            "disclaimer": (
                "## Indicative purpose and reliance\n"
                "This report is indicative only and has been prepared solely for the stated valuation "
                "purpose. It does not constitute financial advice and should not be relied upon as a "
                "substitute for independent professional, legal, tax or accounting advice. No responsibility "
                "is accepted to any third party who obtains or relies on this report.\n\n"
                "## Information and valuation date\n"
                "The analysis relies on management-supplied information, extracted financial records and "
                "identified public sources. Those inputs have not been independently audited."
            ),
        },
        section_order=[
            "business_overview",
            "market_position",
            "valuation_methodology",
            "financial_performance",
            "financial_ratio_analysis",
            "normalisations_schedule",
            "valuation_assumptions",
            "wacc_assumptions",
            "dcf_analysis",
            "valuation_summary",
            "multiples_crosscheck",
            "balance_sheet_summary",
            "sensitivity_and_risks",
            "comparable_evidence",
            "sources",
            "disclaimer",
        ],
        section_titles={
            "business_overview": "Overview",
            "market_position": "Market Position",
            "valuation_methodology": "Valuation Methodology Adopted",
            "financial_performance": "Financial Performance",
            "financial_ratio_analysis": "Historical Ratio Analysis",
            "normalisations_schedule": "Normalisations",
            "valuation_assumptions": "Valuation Approach and Assumptions",
            "wacc_assumptions": "Weighted Average Cost of Capital",
            "dcf_analysis": "Discounted Cash Flow Analysis",
            "valuation_summary": "Indicative Valuation Summary",
            "multiples_crosscheck": "Multiples Cross-check",
            "balance_sheet_summary": "Balance Sheet Summary",
            "sensitivity_and_risks": "Sensitivity and Specific Risks",
            "comparable_evidence": "Comparable Evidence Appendix",
            "sources": "Sources and References",
            "disclaimer": "Disclaimer",
        },
        report_id=88,
        generated_at="2026-07-04 09:15:00",
    )

    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    normalised_text = " ".join(text.split())

    assert "Business context at a glance" in normalised_text
    assert "Owner or key-person dependency Responsibility is shared" in normalised_text
    assert "across leadership and team" in normalised_text
    assert "Customer concentration 10% to 25%" in normalised_text
    assert "Revenue predictability A mix of recurring and" in normalised_text
    assert "one-off revenue" in normalised_text
    assert "Revenue outlook Modest growth" in normalised_text
    assert "Market context at a glance" in normalised_text
    assert "Public sources retained 6" in normalised_text
    assert "Benchmark evidence Public evidence supports" in normalised_text
    assert "sector or EV/EBITDA context" in normalised_text or "sector or EV / EBITDA context" in normalised_text
    assert "Public profile support Public sources support" in normalised_text
    assert "the company profile or operating context" in normalised_text
    assert "Methodology at a glance" in normalised_text
    assert "Valuation approach selection" in normalised_text
    methodology_first_index = normalised_text.index("Valuation Methodology Adopted")
    methodology_index = normalised_text.index(
        "Valuation Methodology Adopted",
        methodology_first_index + 1,
    )
    methodology_panel_index = normalised_text.index("Methodology at a glance", methodology_index)
    method_selection_index = normalised_text.index("Valuation approach selection", methodology_index)
    assert methodology_panel_index < method_selection_index
    assert "Income approach - DCF" in normalised_text
    assert "Adopted as primary" in normalised_text
    assert "Market approach -" in normalised_text
    assert "EV/EBITDA cross-check" in normalised_text
    assert "Asset approach / net assets" in normalised_text
    assert "Primary valuation method Discounted cash flow" in normalised_text
    assert "Discount-rate range 9.9% - 13.4%" in normalised_text
    assert "Market cross-check 5.0x - 7.0x EV/EBITDA" in normalised_text
    assert "Trading performance at a glance" in normalised_text
    assert "Revenue bridge $980,000 to $1,350,000" in normalised_text
    assert "Direct-cost bridge ($392,000) to ($499,500)" in normalised_text
    assert "Gross profit bridge $588,000 to $850,500" in normalised_text
    assert "Operating expense bridge ($423,000) to ($591,500)" in normalised_text
    assert "EBITDA bridge $165,000 to $259,000" in normalised_text
    assert "Latest actual EBITDA $240,000" in normalised_text
    financial_first_index = normalised_text.index("Financial Performance")
    financial_index = normalised_text.index("Financial Performance", financial_first_index + 1)
    trading_panel_index = normalised_text.index(
        "Trading performance at a glance",
        financial_index,
    )
    financial_table_index = normalised_text.index("Year ending March", financial_index)
    assert trading_panel_index < financial_table_index
    assert "Margin and growth at a glance" in normalised_text
    assert "Latest revenue growth 8.0%" in normalised_text
    assert "Gross margin bridge 60.0% to 63.0%" in normalised_text
    assert "EBITDA margin bridge 16.8% to 19.2%" in normalised_text
    ratio_first_index = normalised_text.index("Historical Ratio Analysis")
    ratio_index = normalised_text.index("Historical Ratio Analysis", ratio_first_index + 1)
    margin_panel_index = normalised_text.index(
        "Margin and growth at a glance",
        ratio_index,
    )
    ratio_table_index = normalised_text.index("Ratio FY23", ratio_index)
    assert margin_panel_index < ratio_table_index
    assert "Normalised EBITDA bridge" in normalised_text
    assert "Uploaded EBITDA basis" in normalised_text
    assert "$240,000" in normalised_text
    assert "Net normalisation" in normalised_text
    assert "$47,000" in normalised_text
    assert "Normalisation impact at a glance" in normalised_text
    assert "Confirmed adjustments 2" in normalised_text
    assert "Net EBITDA adjustment $47,000" in normalised_text
    assert "Normalised EBITDA $287,000" in normalised_text
    normalisations_first_index = normalised_text.index("Normalisations")
    normalisations_index = normalised_text.index("Normalisations", normalisations_first_index + 1)
    normalisation_panel_index = normalised_text.index(
        "Normalisation impact at a glance",
        normalisations_index,
    )
    normalisations_table_index = normalised_text.index("Adjustment Amount Rationale", normalisations_index)
    assert normalisation_panel_index < normalisations_table_index
    assert "Assumption basis at a glance" in normalised_text
    assert "Maintainable earnings base $287,000" in normalised_text
    assert "Growth assumption 8.0%" in normalised_text
    assert "Public research inputs 2" in normalised_text
    assert "Management-confirmed inputs 5" in normalised_text
    assert "Technical model inputs 1" in normalised_text
    assert "How the discount rate drives the range" in normalised_text
    assert "High valuation discount rate 9.9%" in normalised_text
    assert "Illiquidity discount 11.8%" in normalised_text
    wacc_first_index = normalised_text.index("Weighted Average Cost of Capital")
    wacc_index = normalised_text.index("Weighted Average Cost of Capital", wacc_first_index + 1)
    wacc_panel_index = normalised_text.index(
        "How the discount rate drives the range",
        wacc_index,
    )
    wacc_table_index = normalised_text.index("Component High valuation", wacc_index)
    assert wacc_panel_index < wacc_table_index
    assert "How the market cross-check is used" in normalised_text
    assert "Market multiple range 5.0x - 7.0x" in normalised_text
    assert "Implied enterprise value range $1,435,000 - $2,009,000" in normalised_text
    assert "Implied multiple reconciliation" in normalised_text
    assert "DCF post-illiquidity range" in normalised_text
    assert "6.6x - 9.9x" in normalised_text
    assert "2.1x above market midpoint" in normalised_text
    multiples_first_index = normalised_text.index("Multiples Cross-check")
    multiples_index = normalised_text.index("Multiples Cross-check", multiples_first_index + 1)
    multiples_panel_index = normalised_text.index(
        "How the market cross-check is used",
        multiples_index,
    )
    multiples_table_index = normalised_text.index("Input Low Mid High", multiples_index)
    assert multiples_panel_index < multiples_table_index
    assert "DCF forecast bridge at a glance" in normalised_text
    assert "Adjusted enterprise value range $1,898,000 - $2,831,000" in normalised_text
    assert "Revenue forecast bridge $1,350,000 to $1,836,660" in normalised_text
    assert "Free cash flow bridge $198,731 to $270,372" in normalised_text
    dcf_first_index = normalised_text.index("Discounted Cash Flow Analysis")
    dcf_index = normalised_text.index("Discounted Cash Flow Analysis", dcf_first_index + 1)
    dcf_forecast_panel_index = normalised_text.index("DCF forecast bridge at a glance", dcf_index)
    dcf_table_index = normalised_text.index("DCF item High valuation", dcf_index)
    assert dcf_forecast_panel_index < dcf_table_index
    assert "Valuation range at a glance" in normalised_text
    assert "Primary DCF range $1,898,000 - $2,831,000" in normalised_text
    assert "Market cross-check range $1,370,000 - $1,944,000" in normalised_text
    assert "DCF vs multiple midpoint $592,000 above" in normalised_text
    valuation_summary_first_index = normalised_text.index("Indicative Valuation Summary")
    valuation_summary_index = normalised_text.index(
        "Indicative Valuation Summary",
        valuation_summary_first_index + 1,
    )
    valuation_range_panel_index = normalised_text.index(
        "Valuation range at a glance",
        valuation_summary_index,
    )
    valuation_summary_table_index = normalised_text.index(
        "Method / scenario",
        valuation_summary_index,
    )
    assert valuation_range_panel_index < valuation_summary_table_index
    assert "Sensitivity takeaway at a glance" in normalised_text
    assert "Base sensitivity case $2,314,000" in normalised_text
    assert "Quantified EV span $1,765,000 - $3,054,000" in normalised_text
    assert "Growth cases tested 6.0% to 10.0%" in normalised_text
    assert "Specific risk factors 5" in normalised_text
    sensitivity_first_index = normalised_text.index("Sensitivity and Specific Risks")
    sensitivity_index = normalised_text.index(
        "Sensitivity and Specific Risks",
        sensitivity_first_index + 1,
    )
    sensitivity_panel_index = normalised_text.index(
        "Sensitivity takeaway at a glance",
        sensitivity_index,
    )
    sensitivity_matrix_index = normalised_text.index(
        "Growth assumption High valuation",
        sensitivity_index,
    )
    assert sensitivity_panel_index < sensitivity_matrix_index
    assert "Comparable evidence at a glance" in normalised_text
    assert "Evidence rows 3" in normalised_text
    assert "Source URLs retained 3" in normalised_text
    assert "Market multiple support Market evidence supports" in normalised_text
    assert "the EV/EBITDA cross-check" in normalised_text
    assert "Comparability caveat Limitations explained as a" in normalised_text
    assert "reasonableness check" in normalised_text
    comparable_first_index = normalised_text.index("Comparable Evidence Appendix")
    comparable_index = normalised_text.index(
        "Comparable Evidence Appendix",
        comparable_first_index + 1,
    )
    comparable_panel_index = normalised_text.index(
        "Comparable evidence at a glance",
        comparable_index,
    )
    comparable_table_index = normalised_text.index("Evidence Date Metric", comparable_index)
    assert comparable_panel_index < comparable_table_index
    assert "Enterprise-to-equity bridge" in normalised_text
    assert "Current balance sheet position $370,000 current assets vs" in normalised_text
    assert "$260,000 current liabilities" in normalised_text
    assert "Total asset and liability base $850,000 total assets vs" in normalised_text
    assert "$420,000 total liabilities" in normalised_text
    assert "Reported net assets $430,000" in normalised_text
    assert "Net debt bridge ($65,000)" in normalised_text
    assert "Midpoint equity value $2,249,000" in normalised_text
    balance_first_index = normalised_text.index("Balance Sheet Summary")
    balance_index = normalised_text.index("Balance Sheet Summary", balance_first_index + 1)
    bridge_panel_index = normalised_text.index("Enterprise-to-equity bridge", balance_index)
    balance_table_index = normalised_text.index("Balance sheet item Value", balance_index)
    assert bridge_panel_index < balance_table_index
    assert "Source trail at a glance" in normalised_text
    assert "Public URLs retained 3" in normalised_text
    assert "Discount-rate support Public sources retained" in normalised_text
    assert "for WACC inputs" in normalised_text
    assert "Terminal-growth support Inflation source retained" in normalised_text
    assert "for terminal growth" in normalised_text
    assert "Business context support Public profile sources" in normalised_text
    assert "retained for business context" in normalised_text
    sources_first_index = normalised_text.index("Sources and References")
    sources_index = normalised_text.index("Sources and References", sources_first_index + 1)
    source_trail_panel_index = normalised_text.index("Source trail at a glance", sources_index)
    sources_table_index = normalised_text.index("Source URL Supports / used for", sources_index)
    assert source_trail_panel_index < sources_table_index
    assert "Reliance at a glance" in normalised_text
    assert "Intended use Stated purpose only" in normalised_text
    assert "Advice status Not advice" in normalised_text
    disclaimer_first_index = normalised_text.index("Disclaimer")
    disclaimer_index = normalised_text.index("Disclaimer", disclaimer_first_index + 1)
    reliance_panel_index = normalised_text.index("Reliance at a glance", disclaimer_index)
    disclaimer_narrative_index = normalised_text.index(
        "Indicative purpose and reliance",
        disclaimer_index,
    )
    assert reliance_panel_index < disclaimer_narrative_index
